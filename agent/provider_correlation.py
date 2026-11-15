
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


class CorrelationConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderCorrelation:
    operation_id: str
    client_request_id: str
    response_id: str | None = None


class ProviderCorrelationStore:
    def __init__(self, root: Path, operation_id: str):
        UUID(hex=operation_id)
        self.operation_id = operation_id
        self.root = Path(root)
        self.path = self.root / f"{operation_id}.json"

    def load(self) -> ProviderCorrelation | None:
        if not self.path.exists():
            return None

        data = json.loads(self.path.read_text("utf-8"))
        record = ProviderCorrelation(**data)
        if record.operation_id != self.operation_id:
            raise CorrelationConflict(
                "Correlation operation identity mismatch"
            )
        if not isinstance(record.client_request_id, str) or not record.client_request_id:
            raise CorrelationConflict(
                "Invalid correlation client request ID"
            )

        if record.response_id is not None and (not isinstance(record.response_id, str) or not record.response_id):
            raise CorrelationConflict(
                "Invalid provider response ID"
            )
        return record

    def _write(self, record: ProviderCorrelation) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.root,
                delete=False,
            ) as file:
                temporary = Path(file.name)
                json.dump(record.__dict__, file)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.path)
            temporary = None

            fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def prepare(
        self,
        record: ProviderCorrelation,
    ) -> None:
        if self.load() is not None:
            raise CorrelationConflict(
                "Correlation already exists"
            )

        self._write(record)

    def record_response(self, response_id: str) -> None:
        current = self.load()
        if current is None:
            raise CorrelationConflict(
                "Missing correlation"
            )

        if not response_id:
            raise ValueError("Empty response ID")

        if current.response_id is not None:
            raise CorrelationConflict(
                "Response already recorded"
            )

        self._write(
            ProviderCorrelation(
                operation_id=current.operation_id,
                client_request_id=current.client_request_id,
                response_id=response_id,
            )
        )
