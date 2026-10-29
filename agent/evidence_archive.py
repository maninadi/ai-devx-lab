
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from agent.checkpoint import RecoveryBlocked
from agent.evidence import read_file_range, validate_path
from agent.evidence_ledger import Evidence, EvidenceLedger
from agent.working_memory import MemoryCapsule, WorkingMemory

_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class EvidenceArchive:
    version: int
    run_id: str
    response_id: str
    turn: int
    records: tuple[Evidence, ...]
    file_hashes: dict[str, str]

    def validate(self) -> None:
        if (
            self.version != 1
            or not isinstance(self.run_id, str)
            or not self.run_id
            or not isinstance(self.response_id, str)
            or not self.response_id
            or type(self.turn) is not int
            or self.turn < 1
            or not isinstance(self.records, tuple)
            or len(self.records) > 1000
            or not isinstance(self.file_hashes, dict)
        ):
            raise RecoveryBlocked("Invalid evidence archive header")

        paths = set()

        for item in self.records:
            if (
                not isinstance(item, Evidence)
                or not isinstance(item.path, str)
                or not item.path
                or type(item.start_line) is not int
                or type(item.end_line) is not int
                or not 1 <= item.start_line <= item.end_line
                or item.end_line - item.start_line >= 40
                or not isinstance(item.sha256, str)
                or _DIGEST.fullmatch(item.sha256) is None
            ):
                raise RecoveryBlocked("Invalid evidence archive record")

            paths.add(item.path)

        if set(self.file_hashes) != paths or any(
            not isinstance(digest, str)
            or _DIGEST.fullmatch(digest) is None
            for digest in self.file_hashes.values()
        ):
            raise RecoveryBlocked("Invalid observed-file fingerprints")


class EvidenceArchiveStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, archive: EvidenceArchive) -> None:
        archive.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".evidence-",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary = file.name
                os.chmod(temporary, 0o600)
                json.dump(asdict(archive), file, sort_keys=True)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.path)
            temporary = None

        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def load(self) -> EvidenceArchive:
        if not self.path.is_file():
            raise RecoveryBlocked("Evidence archive missing")

        if self.path.stat().st_size > 1_000_000:
            raise RecoveryBlocked("Evidence archive too large")

        try:
            data = json.loads(
                self.path.read_text(encoding="utf-8")
            )

            if not isinstance(data, dict):
                raise TypeError("Expected JSON object")

            data["records"] = tuple(
                Evidence(**item)
                for item in data["records"]
            )

            archive = EvidenceArchive(**data)
            archive.validate()
            return archive

        except (
            ValueError,
            TypeError,
            KeyError,
            UnicodeError,
            OSError,
        ) as exc:
            raise RecoveryBlocked(
                "Invalid saved evidence archive"
            ) from exc


def capture_evidence_archive(
    repo_root: Path,
    *,
    run_id: str,
    response_id: str,
    turn: int,
    ledger: EvidenceLedger,
) -> EvidenceArchive:
    fingerprints = {}

    for path in sorted({item.path for item in ledger.records}):
        try:
            file_path = validate_path(repo_root, path)
            fingerprints[path] = hashlib.sha256(
                file_path.read_bytes()
            ).hexdigest()

        except (ValueError, OSError) as exc:
            raise RecoveryBlocked(
                "Observed file unavailable at checkpoint"
            ) from exc

    archive = EvidenceArchive(
        version=1,
        run_id=run_id,
        response_id=response_id,
        turn=turn,
        records=tuple(ledger.records),
        file_hashes=fingerprints,
    )

    archive.validate()
    return archive


def restore_evidence_archive(
    repo_root: Path,
    store: EvidenceArchiveStore,
    capsule: MemoryCapsule,
) -> EvidenceLedger:
    capsule.validate()
    archive = store.load()

    if (
        archive.run_id,
        archive.response_id,
        archive.turn,
    ) != (
        capsule.run_id,
        capsule.response_id,
        capsule.turn,
    ):
        raise RecoveryBlocked(
            "Evidence archive boundary mismatch"
        )

    # Reconstruct the Day 22 working-memory view
    # from every archived observation.
    memory = WorkingMemory(max_recent=5)

    for item in archive.records:
        memory.observe(item)

    expected = memory.capsule(
        run_id=capsule.run_id,
        response_id=capsule.response_id,
        turn=capsule.turn,
        context_chars_used=capsule.context_chars_used,
        context_chars_limit=capsule.context_chars_limit,
    )

    if (
        expected.unique_evidence != capsule.unique_evidence
        or expected.omitted_evidence != capsule.omitted_evidence
        or expected.recent_evidence != capsule.recent_evidence
    ):
        raise RecoveryBlocked(
            "Evidence archive and capsule disagree"
        )

    # Detect changes anywhere in an observed file,
    # not just within a cited excerpt.
    for path, saved_digest in archive.file_hashes.items():
        try:
            current = hashlib.sha256(
                validate_path(repo_root, path).read_bytes()
            ).hexdigest()

        except (ValueError, OSError) as exc:
            raise RecoveryBlocked(
                "Observed file unavailable"
            ) from exc

        if current != saved_digest:
            raise RecoveryBlocked(
                "Observed file changed since checkpoint"
            )

    # Re-read each exact source range and rebuild
    # the authoritative ledger in original order.
    ledger = EvidenceLedger()

    for item in archive.records:
        result = read_file_range(
            repo_root=repo_root,
            path=item.path,
            start_line=item.start_line,
            end_line=item.end_line,
        )

        if (
            result.get("ok") is not True
            or result.get("path") != item.path
            or result.get("start_line") != item.start_line
            or result.get("end_line") != item.end_line
            or not ledger.record(
                "read_file_range",
                result,
                truncated=False,
            )
            or ledger.records[-1] != item
        ):
            raise RecoveryBlocked(
                "Observed excerpt changed or unavailable"
            )

    return ledger
