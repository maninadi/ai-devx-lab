
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from agent.output_diagnostics import (
    DiagnosticKind,
    FailureCategory,
    OutputDiagnostic,
    ReceiptState,
)
from agent.output_failure_policy import OutputAction


class DiagnosticConflict(RuntimeError):
    pass


MAX_RECORD_BYTES = 4096

_FIELDS = {
    "version",
    "operation_id",
    "kind",
    "receipt_state",
    "response_id",
    "action",
    "failure_category",
}


def _encode(event: OutputDiagnostic) -> bytes:
    data = {
        "version": 1,
        "operation_id": event.operation_id,
        "kind": event.kind.value,
        "receipt_state": event.receipt_state.value,
        "response_id": event.response_id,
        "action": (
            event.action.value
            if event.action is not None
            else None
        ),
        "failure_category": (
            event.failure_category.value
            if event.failure_category is not None
            else None
        ),
    }
    payload = json.dumps(
        data, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    if len(payload) > MAX_RECORD_BYTES:
        raise DiagnosticConflict("Diagnostic too large")
    return payload


def _decode(payload: bytes) -> OutputDiagnostic:
    if len(payload) > MAX_RECORD_BYTES:
        raise DiagnosticConflict("Diagnostic too large")

    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("Not an object")
        if set(data) != _FIELDS:
            raise ValueError("Invalid fields")
        if type(data["version"]) is not int:
            raise ValueError("Invalid version")
        if data["version"] != 1:
            raise ValueError("Unsupported version")

        event = OutputDiagnostic(
            operation_id=data["operation_id"],
            kind=DiagnosticKind(data["kind"]),
            receipt_state=ReceiptState(
                data["receipt_state"]
            ),
            response_id=data["response_id"],
            action=(
                OutputAction(data["action"])
                if data["action"] is not None
                else None
            ),
            failure_category=(
                FailureCategory(
                    data["failure_category"]
                )
                if data["failure_category"] is not None
                else None
            ),
        )
        # Reject extra coercion or noncanonical JSON.
        if _encode(event) != payload:
            raise ValueError("Noncanonical record")
        return event
    except (ValueError, TypeError, KeyError) as exc:
        raise DiagnosticConflict(
            "Invalid diagnostic record"
        ) from exc


def _sync_directory(path: Path) -> None:
    fd = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class DurableOutputDiagnosticStore:
    """Single-writer, one-event-per-operation store."""

    def __init__(self, root: Path, operation_id: str):
        # Reuse the event's existing ID validation.
        OutputDiagnostic(
            operation_id=operation_id,
            kind=DiagnosticKind.POLICY_DECIDED,
            receipt_state=ReceiptState.UNKNOWN,
        )
        self.root = Path(root)
        self.operation_id = operation_id
        self.path = self.root / f"{operation_id}.json"

    def load(self) -> OutputDiagnostic | None:
        if self.path.is_symlink():
            raise DiagnosticConflict("Symlink rejected")

        try:
            with self.path.open("rb") as file:
                payload = file.read(MAX_RECORD_BYTES + 1)
        except FileNotFoundError:
            return None

        event = _decode(payload)
        if event.operation_id != self.operation_id:
            raise DiagnosticConflict(
                "Operation identity mismatch"
            )
        return event

    def write(self, event: OutputDiagnostic) -> None:
        if event.operation_id != self.operation_id:
            raise DiagnosticConflict(
                "Operation identity mismatch"
            )

        payload = _encode(event)
        existing = self.load()
        if existing is not None:
            if existing == event:
                return
            raise DiagnosticConflict(
                "Conflicting diagnostic event"
            )

        self.root.mkdir(
            parents=True, exist_ok=True, mode=0o700
        )

        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.root,
                prefix=".diagnostic-",
                delete=False,
            ) as file:
                temporary = Path(file.name)
                os.chmod(temporary, 0o600)
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())

            # Single-writer assumption:
            # no competing writer between load and replace.
            os.replace(temporary, self.path)
            temporary = None
            _sync_directory(self.root)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
