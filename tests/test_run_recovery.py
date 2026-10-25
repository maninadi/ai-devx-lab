from datetime import (
    datetime,
    timedelta,
    timezone,
)

from decimal import Decimal

import pytest

from agent.agent_state import (
    AgentPhase,
    AgentStateMachine,
)

from agent.execution_budget import (
    BudgetPolicy,
)

from agent.cost_accounting import (
    TokenRates,
)

from agent.run_recovery import (
    RunSnapshot,
    RunSnapshotStore,
    restore_state_machine,
    restore_execution_budget,
    restore_cost_ledger,
)

from agent.checkpoint import RecoveryBlocked


RATES = TokenRates(
    input_per_million=Decimal("0.40"),
    cached_input_per_million=Decimal("0.10"),
    output_per_million=Decimal("1.60"),
)


def make_snapshot():

    machine = AgentStateMachine()

    machine.move(
        AgentPhase.MODEL_REQUEST,
        "run_started",
    )

    machine.move(
        AgentPhase.TOOL_EXECUTION,
        "model_requested_tools",
    )

    machine.move(
        AgentPhase.FINAL_REQUEST,
        "budget_reached",
    )

    deadline = (
        datetime.now(timezone.utc)
        + timedelta(seconds=60)
    )

    return RunSnapshot(
        version=1,
        run_id="run-1",
        response_id="resp-1",
        turn=3,
        phase=AgentPhase.FINAL_REQUEST.value,
        transitions=[
            {
                "sequence": item.sequence,
                "source": item.source.value,
                "target": item.target.value,
                "reason": item.reason,
            }
            for item in machine.history
        ],
        deadline_utc=deadline.isoformat(),
        calls_used=2,
        request_counts={
            "fingerprint-a": 1,
            "fingerprint-b": 1,
        },
        cost_state={
            "model": "gpt-4.1-mini",
            "response_ids": [
                "resp-0",
                "resp-1",
            ],
            "response_count": 2,
            "unknown_usage_count": 0,
            "input_tokens": 5000,
            "cached_input_tokens": 1000,
            "output_tokens": 500,
            "estimated_cost_usd": "0.002",
        },
    )


def test_snapshot_round_trip(tmp_path):

    store = RunSnapshotStore(
        tmp_path / "run.json"
    )

    snapshot = make_snapshot()

    store.save(snapshot)

    loaded = store.load()

    assert loaded.run_id == snapshot.run_id
    assert loaded.calls_used == 2
    assert loaded.phase == "final_request"


def test_state_machine_restoration():

    snapshot = make_snapshot()

    restored = restore_state_machine(
        snapshot
    )

    assert (
        restored.phase
        == AgentPhase.FINAL_REQUEST
    )

    assert len(restored.history) == 3


def test_budget_counters_are_preserved():

    snapshot = make_snapshot()

    budget = restore_execution_budget(
        snapshot,
        policy=BudgetPolicy(
            max_tool_calls=8,
            max_repeats=2,
            max_seconds=90,
            finalization_reserve_seconds=15,
        ),
    )

    assert budget.calls_used == 2

    assert (
        budget.request_counts["fingerprint-a"]
        == 1
    )


def test_expired_deadline_blocks_recovery():

    snapshot = make_snapshot()

    future = (
        datetime.now(timezone.utc)
        + timedelta(hours=1)
    )

    with pytest.raises(RecoveryBlocked):
        restore_execution_budget(
            snapshot,
            policy=BudgetPolicy(),
            now_utc=future,
        )


def test_cost_ledger_is_preserved():

    snapshot = make_snapshot()

    ledger = restore_cost_ledger(
        snapshot,
        rates=RATES,
        expected_model="gpt-4.1-mini",
    )

    assert ledger.response_count == 2

    assert ledger.input_tokens == 5000

    assert (
        ledger.estimated_cost_usd
        == Decimal("0.002")
    )


def test_model_mismatch_blocks_recovery():

    snapshot = make_snapshot()

    with pytest.raises(RecoveryBlocked):
        restore_cost_ledger(
            snapshot,
            rates=RATES,
            expected_model="another-model",
        )


def test_invalid_counter_is_rejected():

    snapshot = make_snapshot()

    snapshot.request_counts[
        "fingerprint-a"
    ] = 99

    with pytest.raises(RecoveryBlocked):
        snapshot.validate()


def test_invalid_state_history_blocks_restore():

    snapshot = make_snapshot()

    snapshot.transitions[1]["source"] = (
        "finished"
    )

    with pytest.raises(RecoveryBlocked):
        restore_state_machine(snapshot)
