
from __future__ import annotations

import json
import os
import tempfile

from dataclasses import asdict, dataclass
from pathlib import Path

from agent.evidence_ledger import Evidence


class InvalidMemoryCapsule(ValueError):
    pass


@dataclass(frozen=True)
class MemoryCapsule:
    version: int
    run_id: str
    response_id: str
    turn: int

    context_chars_used: int
    context_chars_limit: int

    unique_evidence: int
    omitted_evidence: int
    recent_evidence: tuple[Evidence, ...]

    pressure: str

    def validate(self) -> None:
        if (
            self.version != 1
            or not self.run_id
            or not self.response_id
        ):
            raise InvalidMemoryCapsule(
                "Invalid capsule identity or version"
            )

        if type(self.turn) is not int or self.turn < 1:
            raise InvalidMemoryCapsule("Invalid turn")

        if (
            type(self.context_chars_used) is not int
            or type(self.context_chars_limit) is not int
            or not 0 <= self.context_chars_used <= self.context_chars_limit
            or self.context_chars_limit <= 0
        ):
            raise InvalidMemoryCapsule(
                "Invalid context counters"
            )

        if (
            type(self.unique_evidence) is not int
            or type(self.omitted_evidence) is not int
            or self.unique_evidence < len(self.recent_evidence)
            or self.omitted_evidence
            != self.unique_evidence - len(self.recent_evidence)
            or len(self.recent_evidence) > 8
        ):
            raise InvalidMemoryCapsule(
                "Invalid evidence counts"
            )

        expected = (
            "exhausted"
            if self.context_chars_used == self.context_chars_limit
            else "high"
            if 4 * self.context_chars_used >= 3 * self.context_chars_limit
            else "normal"
        )

        if self.pressure != expected:
            raise InvalidMemoryCapsule(
                "Inconsistent context pressure"
            )

        if not all(
            isinstance(item, Evidence)
            for item in self.recent_evidence
        ):
            raise InvalidMemoryCapsule(
                "Invalid evidence entry"
            )


class WorkingMemory:
    def __init__(self, max_recent: int = 5):
        if (
            type(max_recent) is not int
            or not 1 <= max_recent <= 8
        ):
            raise ValueError(
                "max_recent must be between 1 and 8"
            )

        self.max_recent = max_recent

        self._observed: dict[
            tuple[str, int, int, str],
            Evidence,
        ] = {}

    def observe(self, evidence: Evidence) -> None:
        if not isinstance(evidence, Evidence):
            raise TypeError(
                "Only Evidence records are accepted"
            )

        key = (
            evidence.path,
            evidence.start_line,
            evidence.end_line,
            evidence.sha256,
        )

        # Deduplicate and move repeated evidence
        # to the most-recent position.
        self._observed.pop(key, None)
        self._observed[key] = evidence

    def capsule(
        self,
        *,
        run_id: str,
        response_id: str,
        turn: int,
        context_chars_used: int,
        context_chars_limit: int,
    ) -> MemoryCapsule:
        unique = tuple(self._observed.values())
        recent = unique[-self.max_recent:]

        pressure = (
            "exhausted"
            if context_chars_used == context_chars_limit
            else "high"
            if 4 * context_chars_used >= 3 * context_chars_limit
            else "normal"
        )

        capsule = MemoryCapsule(
            version=1,
            run_id=run_id,
            response_id=response_id,
            turn=turn,
            context_chars_used=context_chars_used,
            context_chars_limit=context_chars_limit,
            unique_evidence=len(unique),
            omitted_evidence=len(unique) - len(recent),
            recent_evidence=recent,
            pressure=pressure,
        )

        capsule.validate()
        return capsule


class MemoryCapsuleStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, capsule: MemoryCapsule) -> None:
        capsule.validate()

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
                prefix=".memory-",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary = file.name

                os.chmod(temporary, 0o600)

                json.dump(
                    asdict(capsule),
                    file,
                    sort_keys=True,
                )

                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.path)
            temporary = None

        finally:
            if temporary is not None:
                Path(temporary).unlink(
                    missing_ok=True
                )

    def load(self) -> MemoryCapsule:
        if (
            not self.path.is_file()
            or self.path.stat().st_size > 65536
        ):
            raise InvalidMemoryCapsule(
                "Missing or oversized capsule"
            )

        try:
            data = json.loads(
                self.path.read_text(encoding="utf-8")
            )

            if not isinstance(data, dict):
                raise TypeError(
                    "Capsule must be an object"
                )

            data["recent_evidence"] = tuple(
                Evidence(**entry)
                for entry in data["recent_evidence"]
            )

            capsule = MemoryCapsule(**data)
            capsule.validate()
            return capsule

        except (ValueError, TypeError, KeyError) as exc:
            raise InvalidMemoryCapsule(
                "Invalid saved memory capsule"
            ) from exc
