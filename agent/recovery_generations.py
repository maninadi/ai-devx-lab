
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from agent.checkpoint import CheckpointStore, RecoveryBlocked
from agent.evidence_archive import EvidenceArchiveStore
from agent.recovery_manifest import (
    RecoveryManifestStore,
    verify_recovery_manifest,
)
from agent.run_recovery import RunSnapshotStore
from agent.working_memory import MemoryCapsuleStore


GEN_ID = re.compile(r"[0-9a-f]{32}")
RUN_ID = re.compile(r"[0-9a-f]{32}")

SUFFIXES = {
    "tool": ".json",
    "run": ".run.json",
    "memory": ".memory.json",
    "evidence": ".evidence.json",
    "manifest": ".manifest.json",
}


@dataclass(frozen=True)
class Generation:
    generation_id: str
    directory: Path
    run_id: str

    def stores(self):
        base = self.directory
        run = self.run_id

        return (
            RecoveryManifestStore(
                base / f"{run}.manifest.json"
            ),
            RunSnapshotStore(
                base / f"{run}.run.json"
            ),
            CheckpointStore(
                base / f"{run}.json"
            ),
            MemoryCapsuleStore(
                base / f"{run}.memory.json"
            ),
            EvidenceArchiveStore(
                base / f"{run}.evidence.json"
            ),
        )


def sync_directory(path: Path) -> None:
    """Best-effort Unix directory metadata durability."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)

    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class GenerationStore:
    def __init__(self, checkpoint_root: Path):
        self.root = Path(checkpoint_root)
        self.generations = self.root / "generations"
        self.pointer = self.root / "CURRENT"

    def _generation(
        self,
        generation_id: str,
        run_id: str,
    ) -> Generation:
        if (
            GEN_ID.fullmatch(generation_id) is None
            or RUN_ID.fullmatch(run_id) is None
        ):
            raise RecoveryBlocked(
                "Invalid checkpoint generation identity"
            )

        directory = self.generations / generation_id

        if directory.is_symlink():
            raise RecoveryBlocked(
                "Generation directory is a symlink"
            )

        return Generation(
            generation_id,
            directory,
            run_id,
        )

    def verify(
        self,
        repo_root: Path,
        generation: Generation,
    ) -> None:
        manifest, snapshot, checkpoint, _, _ = (
            generation.stores()
        )

        if not generation.directory.is_dir():
            raise RecoveryBlocked(
                "Checkpoint generation missing"
            )

        verified = verify_recovery_manifest(
            repo_root,
            manifest,
            snapshot,
            checkpoint,
        )

        if verified.run_id != generation.run_id:
            raise RecoveryBlocked(
                "Generation run identity mismatch"
            )

    def current(
        self,
        repo_root: Path,
    ) -> Generation:
        if self.pointer.is_symlink():
            raise RecoveryBlocked(
                "CURRENT pointer is a symlink"
            )

        try:
            if self.pointer.stat().st_size > 512:
                raise RecoveryBlocked(
                    "CURRENT pointer too large"
                )

            data = json.loads(
                self.pointer.read_text("utf-8")
            )

            if (
                not isinstance(data, dict)
                or set(data) != {
                    "version",
                    "generation_id",
                    "run_id",
                }
                or type(data["version"]) is not int
                or data["version"] != 1
            ):
                raise RecoveryBlocked(
                    "Invalid CURRENT pointer"
                )

            generation = self._generation(
                data["generation_id"],
                data["run_id"],
            )

        except (
            FileNotFoundError,
            ValueError,
            KeyError,
            TypeError,
            UnicodeError,
        ) as exc:
            raise RecoveryBlocked(
                "CURRENT pointer unavailable or invalid"
            ) from exc

        self.verify(repo_root, generation)
        return generation

    def publish(
        self,
        repo_root: Path,
        source_manifest: RecoveryManifestStore,
        source_snapshot: RunSnapshotStore,
        source_checkpoint: CheckpointStore,
        source_memory: MemoryCapsuleStore,
        source_evidence: EvidenceArchiveStore,
        *,
        fail_at: str | None = None,
    ) -> Generation:
        """Copy a verified boundary, then atomically publish it.

        fail_at is a deterministic test-only fault injection point.
        """
        if fail_at not in {
            None,
            "after_copy",
            "before_pointer",
            "after_pointer",
        }:
            raise ValueError("Unknown failure injection point")

        # Never publish an invalid source checkpoint set.
        source = verify_recovery_manifest(
            repo_root,
            source_manifest,
            source_snapshot,
            source_checkpoint,
        )

        if (
            source_memory.load().run_id != source.run_id
            or source_evidence.load().run_id != source.run_id
        ):
            raise RecoveryBlocked(
                "Source generation identity mismatch"
            )

        self.generations.mkdir(
            parents=True,
            exist_ok=True,
        )

        generation = self._generation(
            uuid4().hex,
            source.run_id,
        )

        generation.directory.mkdir(
            mode=0o700,
            exist_ok=False,
        )

        sources = {
            "tool": source_checkpoint.path,
            "run": source_snapshot.path,
            "memory": source_memory.path,
            "evidence": source_evidence.path,
            "manifest": source_manifest.path,
        }

        # Copy data files first and the manifest last.
        for name in (
            "tool",
            "run",
            "memory",
            "evidence",
            "manifest",
        ):
            original = sources[name]
            destination = (
                generation.directory
                / f"{source.run_id}{SUFFIXES[name]}"
            )

            if original.is_symlink():
                raise RecoveryBlocked(
                    "Source artifact is a symlink"
                )

            with original.open("rb") as src:
                with destination.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
                    dst.flush()
                    os.fsync(dst.fileno())

        sync_directory(generation.directory)

        if fail_at == "after_copy":
            raise RuntimeError("Injected crash after copy")

        # Detect source mutation during copying.
        self.verify(repo_root, generation)

        # Revalidate the source before publication.
        verify_recovery_manifest(
            repo_root,
            source_manifest,
            source_snapshot,
            source_checkpoint,
        )

        if fail_at == "before_pointer":
            raise RuntimeError("Injected crash before pointer")

        pointer_data = {
            "version": 1,
            "generation_id": generation.generation_id,
            "run_id": generation.run_id,
        }

        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=".current-",
                delete=False,
            ) as file:
                temporary = Path(file.name)
                os.chmod(temporary, 0o600)
                json.dump(pointer_data, file)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.pointer)
            temporary = None

            sync_directory(self.root)

        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

        if fail_at == "after_pointer":
            raise RuntimeError("Injected crash after pointer")

        return generation
