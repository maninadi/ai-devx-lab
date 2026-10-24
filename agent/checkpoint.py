from __future__ import annotations

import json
import os
import tempfile

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from pathlib import Path
from typing import Callable


class RecoveryBlocked(RuntimeError):
    """
    Execution cannot safely resume automatically.
    """


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: str

    def __post_init__(self) -> None:
        if (
            not self.call_id
            or not self.name
            or not isinstance(self.arguments, str)
        ):
            raise ValueError("Invalid tool call")


@dataclass
class BatchCheckpoint:
    run_id: str
    response_id: str
    turn: int
    calls: list[ToolCall]

    outputs: dict[str, str] = field(
        default_factory=dict
    )

    in_flight: str | None = None

    stage: str = "tool_execution"

    version: int = 1

    def __post_init__(self) -> None:

        if (
            self.version != 1
            or not self.run_id
            or not self.response_id
            or self.turn < 1
        ):
            raise ValueError(
                "Invalid checkpoint header"
            )

        if self.stage not in {
            "tool_execution",
            "ready_for_model",
        }:
            raise ValueError(
                "Invalid checkpoint stage"
            )

        ids = [
            call.call_id
            for call in self.calls
        ]

        if (
            not ids
            or len(ids) != len(set(ids))
        ):
            raise ValueError(
                "Tool call IDs must be unique"
            )

        if not set(self.outputs).issubset(ids):
            raise ValueError(
                "Unknown completed call ID"
            )

        if any(
            not isinstance(value, str)
            for value in self.outputs.values()
        ):
            raise ValueError(
                "Tool outputs must be strings"
            )

        if self.in_flight is not None:
            if (
                self.in_flight not in ids
                or self.in_flight in self.outputs
            ):
                raise ValueError(
                    "Invalid in-flight call"
                )

        if self.stage == "ready_for_model":
            if (
                len(self.outputs) != len(ids)
                or self.in_flight is not None
            ):
                raise ValueError(
                    "Incomplete checkpoint"
                )

    def ordered_outputs(
        self,
    ) -> list[dict[str, str]]:

        if len(self.outputs) != len(self.calls):
            raise RecoveryBlocked(
                "Not all tool results are durable"
            )

        return [
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": self.outputs[
                    call.call_id
                ],
            }
            for call in self.calls
        ]


class CheckpointStore:

    def __init__(self, path: Path):
        self.path = Path(path)

    def save(
        self,
        checkpoint: BatchCheckpoint,
    ) -> None:

        checkpoint.__post_init__()

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".checkpoint-",
                suffix=".tmp",
                delete=False,
            ) as file:

                temporary = file.name

                os.chmod(
                    temporary,
                    0o600,
                )

                json.dump(
                    asdict(checkpoint),
                    file,
                    sort_keys=True,
                )

                file.flush()

                os.fsync(
                    file.fileno()
                )

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

    def load(
        self,
    ) -> BatchCheckpoint | None:

        if not self.path.exists():
            return None

        if (
            self.path.stat().st_size
            > 4_000_000
        ):
            raise ValueError(
                "Checkpoint exceeds size limit"
            )

        data = json.loads(
            self.path.read_text(
                encoding="utf-8"
            )
        )

        data["calls"] = [
            ToolCall(**item)
            for item in data["calls"]
        ]

        return BatchCheckpoint(**data)


class ToolBatchJournal:

    def __init__(
        self,
        store: CheckpointStore,
    ):
        self.store = store

    def begin(
        self,
        *,
        run_id: str,
        response_id: str,
        turn: int,
        calls: list[ToolCall],
    ) -> None:

        previous = self.store.load()

        if (
            previous is not None
            and previous.stage
            != "ready_for_model"
        ):
            raise RecoveryBlocked(
                "An unfinished tool batch exists"
            )

        checkpoint = BatchCheckpoint(
            run_id=run_id,
            response_id=response_id,
            turn=turn,
            calls=calls,
        )

        self.store.save(checkpoint)

    def start_call(
        self,
        call_id: str,
    ) -> None:

        checkpoint = self._active()

        known_ids = {
            call.call_id
            for call in checkpoint.calls
        }

        if (
            call_id not in known_ids
            or call_id in checkpoint.outputs
        ):
            raise ValueError(
                "Unknown or completed call ID"
            )

        if checkpoint.in_flight not in (
            None,
            call_id,
        ):
            raise RecoveryBlocked(
                "Another call is in flight"
            )

        checkpoint.in_flight = call_id

        self.store.save(checkpoint)

    def complete_call(
        self,
        call_id: str,
        output: str,
    ) -> None:

        checkpoint = self._active()

        if (
            checkpoint.in_flight != call_id
            or not isinstance(output, str)
        ):
            raise ValueError(
                "Complete only the in-flight "
                "call with string output"
            )

        checkpoint.outputs[call_id] = output

        checkpoint.in_flight = None

        self.store.save(checkpoint)

    def finish(
        self,
    ) -> list[dict[str, str]]:

        checkpoint = self._active()

        if (
            checkpoint.in_flight is not None
            or len(checkpoint.outputs)
            != len(checkpoint.calls)
        ):
            raise RecoveryBlocked(
                "Tool batch has incomplete results"
            )

        checkpoint.stage = "ready_for_model"

        self.store.save(checkpoint)

        return checkpoint.ordered_outputs()

    def _active(
        self,
    ) -> BatchCheckpoint:

        checkpoint = self.store.load()

        if (
            checkpoint is None
            or checkpoint.stage
            != "tool_execution"
        ):
            raise RecoveryBlocked(
                "No active tool batch"
            )

        return checkpoint


READ_ONLY_TOOLS = frozenset({
    "list_files",
    "read_file",
    "read_file_range",
    "search_repository",
    "review_constant",
})


def recover_readonly_batch(
    store: CheckpointStore,
    execute: Callable[[ToolCall], str],
    *,
    allow_replay_inflight: bool = False,
) -> list[dict[str, str]]:

    checkpoint = store.load()

    if checkpoint is None:
        raise RecoveryBlocked(
            "No checkpoint exists"
        )

    if checkpoint.stage == "ready_for_model":
        return checkpoint.ordered_outputs()

    if (
        checkpoint.in_flight is not None
        and not allow_replay_inflight
    ):
        raise RecoveryBlocked(
            "In-flight outcome unknown; "
            "explicit replay required"
        )

    journal = ToolBatchJournal(store)

    for call in checkpoint.calls:

        if call.call_id in checkpoint.outputs:
            continue

        if call.name not in READ_ONLY_TOOLS:
            raise RecoveryBlocked(
                f"Cannot automatically replay: "
                f"{call.name}"
            )

        journal.start_call(
            call.call_id
        )

        result = execute(call)

        journal.complete_call(
            call.call_id,
            result,
        )

    return journal.finish()
