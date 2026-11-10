
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AttemptState(str, Enum):
    SUBMISSION_INTENT = "submission_intent"
    RESPONSE_RECEIVED = "response_received"


class AttemptConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class AttemptRecord:
    operation_id: str
    state: AttemptState
    response_id: str | None = None
    response_status: str | None = None


def _safe_id(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(c in "0123456789abcdef" for c in value)
    )


def _sync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(
        os, "O_DIRECTORY", 0
    )
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class GenerationAttemptJournal:
    """
    Durable record for one logical generation operation.

    Single-writer design; concurrent writers require
    an external lock or compare-and-swap mechanism.
    """

    def __init__(self, root: Path, operation_id: str):
        if not _safe_id(operation_id):
            raise ValueError("Invalid operation ID")

        self.root = Path(root)
        self.operation_id = operation_id
        self.path = self.root / f"{operation_id}.json"

    def load(self) -> AttemptRecord | None:
        if self.path.is_symlink():
            raise AttemptConflict("Journal path is a symlink")

        try:
            raw = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            return None

        if not isinstance(raw, dict) or set(raw) != {
            "version",
            "operation_id",
            "state",
            "response_id",
            "response_status",
        }:
            raise AttemptConflict("Invalid journal schema")

        if (
            type(raw["version"]) is not int
            or raw["version"] != 1
            or raw["operation_id"] != self.operation_id
        ):
            raise AttemptConflict("Journal identity mismatch")

        try:
            state = AttemptState(raw["state"])
        except (ValueError, TypeError):
            raise AttemptConflict("Invalid attempt state") from None

        response_id = raw["response_id"]
        response_status = raw["response_status"]

        if state == AttemptState.SUBMISSION_INTENT:
            if response_id is not None or response_status is not None:
                raise AttemptConflict("Invalid intent record")
        elif (
            not isinstance(response_id, str)
            or not response_id
            or not isinstance(response_status, str)
            or not response_status
        ):
            raise AttemptConflict("Invalid receipt record")

        return AttemptRecord(
            operation_id=self.operation_id,
            state=state,
            response_id=response_id,
            response_status=response_status,
        )

    def _write(self, record: AttemptRecord) -> None:
        self.root.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        data = {
            "version": 1,
            "operation_id": record.operation_id,
            "state": record.state.value,
            "response_id": record.response_id,
            "response_status": record.response_status,
        }

        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=".attempt-",
                delete=False,
            ) as file:
                temporary = Path(file.name)
                os.chmod(temporary, 0o600)
                json.dump(data, file)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.path)
            temporary = None
            _sync_directory(self.root)

        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def record_submission_intent(self) -> AttemptRecord:
        if self.load() is not None:
            raise AttemptConflict(
                "Operation already has a durable record"
            )

        record = AttemptRecord(
            operation_id=self.operation_id,
            state=AttemptState.SUBMISSION_INTENT,
        )
        self._write(record)
        return record

    def record_response(
        self,
        response_id: str,
        response_status: str,
    ) -> AttemptRecord:
        current = self.load()

        if (
            current is None
            or current.state != AttemptState.SUBMISSION_INTENT
        ):
            raise AttemptConflict(
                "Response requires submission intent"
            )

        if (
            not isinstance(response_id, str)
            or not response_id
            or not isinstance(response_status, str)
            or not response_status
        ):
            raise ValueError("Invalid response metadata")

        record = AttemptRecord(
            operation_id=self.operation_id,
            state=AttemptState.RESPONSE_RECEIVED,
            response_id=response_id,
            response_status=response_status,
        )
        self._write(record)
        return record
