from __future__ import annotations

import json
import os
import tempfile
import time

from dataclasses import (
    asdict,
    dataclass,
)

from datetime import (
    datetime,
    timezone,
)

from decimal import Decimal
from pathlib import Path
from typing import Any

from agent.agent_state import (
    AgentPhase,
    AgentStateMachine,
)

from agent.execution_budget import (
    BudgetPolicy,
    ExecutionBudget,
)

from agent.cost_accounting import (
    CostLedger,
    TokenRates,
)

from agent.checkpoint import (
    CheckpointStore,
    RecoveryBlocked,
)


@dataclass(frozen=True)
class RunSnapshot:
    version: int

    run_id: str
    response_id: str
    turn: int

    phase: str
    transitions: list[dict[str, Any]]

    deadline_utc: str

    calls_used: int
    request_counts: dict[str, int]

    cost_state: dict[str, Any]

    model_request_started: bool = False

    def validate(self) -> None:

        if self.version != 1:
            raise RecoveryBlocked(
                "Unsupported recovery snapshot version"
            )

        if not self.run_id or not self.response_id:
            raise RecoveryBlocked(
                "Missing run or response identifier"
            )

        if type(self.turn) is not int or self.turn < 1:
            raise RecoveryBlocked(
                "Invalid saved turn"
            )

        if self.phase not in {
            AgentPhase.MODEL_REQUEST.value,
            AgentPhase.FINAL_REQUEST.value,
        }:
            raise RecoveryBlocked(
                "Snapshot is not at a resumable boundary"
            )

        if (
            type(self.calls_used) is not int
            or self.calls_used < 0
        ):
            raise RecoveryBlocked(
                "Invalid tool-call count"
            )

        if not isinstance(self.request_counts, dict):
            raise RecoveryBlocked(
                "Invalid repetition counters"
            )

        if any(
            not isinstance(key, str)
            or type(value) is not int
            or value < 1
            for key, value in self.request_counts.items()
        ):
            raise RecoveryBlocked(
                "Invalid repetition counter entry"
            )

        if sum(self.request_counts.values()) != self.calls_used:
            raise RecoveryBlocked(
                "Tool-call accounting mismatch"
            )

        if type(self.model_request_started) is not bool:
            raise RecoveryBlocked(
                "Invalid model-request status"
            )

        if not isinstance(self.transitions, list):
            raise RecoveryBlocked(
                "Invalid transition history"
            )

        if not isinstance(self.cost_state, dict):
            raise RecoveryBlocked(
                "Invalid cost state"
            )

        try:
            deadline = datetime.fromisoformat(
                self.deadline_utc
            )

            if deadline.tzinfo is None:
                raise ValueError(
                    "Timezone is required"
                )

        except (TypeError, ValueError) as exc:
            raise RecoveryBlocked(
                "Invalid UTC deadline"
            ) from exc


class RunSnapshotStore:

    def __init__(self, path: Path):
        self.path = Path(path)

    def save(
        self,
        snapshot: RunSnapshot,
    ) -> None:

        snapshot.validate()

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".run-snapshot-",
                suffix=".tmp",
                delete=False,
            ) as file:

                temporary = file.name

                os.chmod(
                    temporary,
                    0o600,
                )

                json.dump(
                    asdict(snapshot),
                    file,
                    sort_keys=True,
                )

                file.flush()
                os.fsync(file.fileno())

            os.replace(
                temporary,
                self.path,
            )

            temporary = None

        finally:
            if temporary is not None:
                Path(temporary).unlink(
                    missing_ok=True
                )

    def load(self) -> RunSnapshot:

        if not self.path.is_file():
            raise RecoveryBlocked(
                "Recovery snapshot not found"
            )

        if self.path.stat().st_size > 4_000_000:
            raise RecoveryBlocked(
                "Recovery snapshot too large"
            )

        try:
            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                ),
                parse_constant=lambda value: (
                    _reject_json_constant(value)
                ),
            )

            snapshot = RunSnapshot(**data)

            snapshot.validate()

        except (
            ValueError,
            TypeError,
            KeyError,
        ) as exc:
            raise RecoveryBlocked(
                "Invalid recovery snapshot"
            ) from exc

        return snapshot


def _reject_json_constant(value: str):
    raise ValueError(
        f"Nonstandard JSON constant: {value}"
    )


def restore_state_machine(
    snapshot: RunSnapshot,
) -> AgentStateMachine:

    machine = AgentStateMachine()

    for saved in snapshot.transitions:

        try:
            source = AgentPhase(
                saved["source"]
            )

            target = AgentPhase(
                saved["target"]
            )

            reason = saved["reason"]

            sequence = saved["sequence"]

        except (
            KeyError,
            ValueError,
            TypeError,
        ) as exc:
            raise RecoveryBlocked(
                "Invalid saved transition"
            ) from exc

        if machine.phase != source:
            raise RecoveryBlocked(
                "State history is inconsistent"
            )

        try:
            transition = machine.move(
                target,
                reason,
            )

        except (
            RuntimeError,
            ValueError,
            TypeError,
        ) as exc:
            raise RecoveryBlocked(
                "Illegal saved state transition"
            ) from exc

        if transition.sequence != sequence:
            raise RecoveryBlocked(
                "Transition sequence mismatch"
            )

    if machine.phase.value != snapshot.phase:
        raise RecoveryBlocked(
            "Final state does not match snapshot"
        )

    return machine


def restore_execution_budget(
    snapshot: RunSnapshot,
    *,
    policy: BudgetPolicy,
    clock=time.monotonic,
    now_utc: datetime | None = None,
) -> ExecutionBudget:

    now_utc = (
        now_utc
        if now_utc is not None
        else datetime.now(timezone.utc)
    )

    if now_utc.tzinfo is None:
        raise ValueError(
            "Recovery requires timezone-aware time"
        )

    deadline = datetime.fromisoformat(
        snapshot.deadline_utc
    )

    remaining = (
        deadline - now_utc
    ).total_seconds()

    if remaining <= 0:
        raise RecoveryBlocked(
            "Original execution deadline expired"
        )

    if snapshot.calls_used > policy.max_tool_calls:
        raise RecoveryBlocked(
            "Saved tool usage exceeds current policy"
        )

    if any(
        count > policy.max_repeats
        for count in snapshot.request_counts.values()
    ):
        raise RecoveryBlocked(
            "Saved repetition count exceeds policy"
        )

    budget = ExecutionBudget(
        policy,
        clock=clock,
    )

    # Reconstruct the remaining monotonic
    # deadline without granting a new
    # full execution period.

    current_tick = clock()

    budget.started_at = current_tick

    budget.deadline = (
        current_tick + remaining
    )

    budget.calls_used = (
        snapshot.calls_used
    )

    budget.request_counts = dict(
        snapshot.request_counts
    )

    return budget


def restore_cost_ledger(
    snapshot: RunSnapshot,
    *,
    rates: TokenRates,
    expected_model: str,
) -> CostLedger:

    state = snapshot.cost_state

    try:
        if state["model"] != expected_model:
            raise RecoveryBlocked(
                "Model changed during recovery"
            )

        response_ids = state["response_ids"]

        if (
            not isinstance(response_ids, list)
            or not all(
                isinstance(item, str) and item
                for item in response_ids
            )
            or len(response_ids)
            != len(set(response_ids))
        ):
            raise ValueError(
                "Invalid response identifiers"
            )

        response_count = state["response_count"]

        if (
            type(response_count) is not int
            or response_count != len(response_ids)
        ):
            raise ValueError(
                "Invalid response count"
            )

        numeric_fields = (
            "unknown_usage_count",
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
        )

        for field in numeric_fields:
            value = state[field]

            if type(value) is not int or value < 0:
                raise ValueError(
                    f"Invalid cost field: {field}"
                )

        if (
            state["cached_input_tokens"]
            > state["input_tokens"]
        ):
            raise ValueError(
                "Cached tokens exceed input tokens"
            )

        estimated_cost = Decimal(
            state["estimated_cost_usd"]
        )

        if (
            not estimated_cost.is_finite()
            or estimated_cost < 0
        ):
            raise ValueError(
                "Invalid estimated cost"
            )

        ledger = CostLedger(
            model=expected_model,
            rates=rates,
        )

        ledger.response_ids = set(
            response_ids
        )

        ledger.response_count = (
            response_count
        )

        ledger.unknown_usage_count = (
            state["unknown_usage_count"]
        )

        ledger.input_tokens = (
            state["input_tokens"]
        )

        ledger.cached_input_tokens = (
            state["cached_input_tokens"]
        )

        ledger.output_tokens = (
            state["output_tokens"]
        )

        ledger.estimated_cost_usd = (
            estimated_cost
        )

    except (
        KeyError,
        ValueError,
        TypeError,
        ArithmeticError,
    ) as exc:
        raise RecoveryBlocked(
            "Invalid saved cost accounting"
        ) from exc

    return ledger


def validate_recovery_boundary(
    snapshot: RunSnapshot,
    checkpoint_store: CheckpointStore,
) -> list[dict[str, str]]:

    snapshot.validate()

    if snapshot.model_request_started:
        raise RecoveryBlocked(
            "A model request may already have started"
        )

    checkpoint = checkpoint_store.load()

    if checkpoint is None:
        raise RecoveryBlocked(
            "Tool checkpoint missing"
        )

    if checkpoint.stage != "ready_for_model":
        raise RecoveryBlocked(
            "Tool batch is not complete"
        )

    if checkpoint.run_id != snapshot.run_id:
        raise RecoveryBlocked(
            "Run identifier mismatch"
        )

    if checkpoint.response_id != snapshot.response_id:
        raise RecoveryBlocked(
            "Model response identifier mismatch"
        )

    if checkpoint.turn != snapshot.turn:
        raise RecoveryBlocked(
            "Model turn mismatch"
        )

    if checkpoint.in_flight is not None:
        raise RecoveryBlocked(
            "A tool is still in flight"
        )

    return checkpoint.ordered_outputs()


@dataclass
class RestoredRun:
    state_machine: AgentStateMachine
    execution_budget: ExecutionBudget
    cost_ledger: CostLedger

    previous_response_id: str
    next_turn: int

    pending_tool_outputs: list[
        dict[str, str]
    ]

    final_only: bool


def restore_run(
    snapshot_store: RunSnapshotStore,
    checkpoint_store: CheckpointStore,
    *,
    budget_policy: BudgetPolicy,
    token_rates: TokenRates,
    expected_model: str,
    max_cost_usd: Decimal | None = None,
    cost_reserve_usd: Decimal = Decimal("0"),
    now_utc: datetime | None = None,
) -> RestoredRun:

    snapshot = snapshot_store.load()

    outputs = validate_recovery_boundary(
        snapshot,
        checkpoint_store,
    )

    machine = restore_state_machine(
        snapshot
    )

    budget = restore_execution_budget(
        snapshot,
        policy=budget_policy,
        now_utc=now_utc,
    )

    ledger = restore_cost_ledger(
        snapshot,
        rates=token_rates,
        expected_model=expected_model,
    )

    final_only = (
        machine.phase == AgentPhase.FINAL_REQUEST
        or budget.should_finalize()
        or ledger.should_finalize(
            max_cost_usd=max_cost_usd,
            reserve_usd=cost_reserve_usd,
        )
    )

    return RestoredRun(
        state_machine=machine,
        execution_budget=budget,
        cost_ledger=ledger,
        previous_response_id=(
            snapshot.response_id
        ),
        next_turn=snapshot.turn + 1,
        pending_tool_outputs=outputs,
        final_only=final_only,
    )
