
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from agent.checkpoint import CheckpointStore, RecoveryBlocked
from agent.evidence import allowed_files
from agent.evidence_archive import EvidenceArchiveStore
from agent.run_recovery import (
    RunSnapshotStore,
    validate_recovery_boundary,
)
from agent.working_memory import MemoryCapsuleStore


HEX64 = re.compile(r"[0-9a-f]{64}")
HEX_HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
PARTS = {"tool", "run", "memory", "evidence"}


def repository_pin(repo_root: Path) -> tuple[str | None, str]:
    """Pin Git HEAD and the eligible working-tree source contents."""
    root = Path(repo_root).resolve()

    def git(*args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RecoveryBlocked("Git inspection unavailable") from exc

    top = git("rev-parse", "--show-toplevel")

    if top.returncode != 0:
        if (root / ".git").exists():
            raise RecoveryBlocked("Invalid Git repository")
        head = None  # Explicitly unversioned test repositories
    else:
        if Path(top.stdout.strip()).resolve() != root:
            raise RecoveryBlocked("Repository root changed")

        revision = git("rev-parse", "--verify", "HEAD")

        if (
            revision.returncode != 0
            or HEX_HEAD.fullmatch(revision.stdout.strip()) is None
        ):
            raise RecoveryBlocked("Git HEAD unavailable")

        head = revision.stdout.strip()

    digest = hashlib.sha256()
    count = 0

    try:
        for path in allowed_files(root):
            count += 1

            # allowed_files caps results at 500.
            # Refuse a possibly incomplete scan.
            if count >= 500:
                raise RecoveryBlocked(
                    "Repository fingerprint scan limit reached"
                )

            relative = path.relative_to(root).as_posix()
            file_digest = hashlib.sha256(path.read_bytes()).digest()

            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(file_digest)
            digest.update(b"\0")

    except OSError as exc:
        raise RecoveryBlocked(
            "Repository changed during fingerprinting"
        ) from exc

    return head, digest.hexdigest()


@dataclass(frozen=True)
class RecoveryManifest:
    version: int
    run_id: str
    response_id: str
    turn: int
    git_head: str | None
    source_tree_sha256: str
    artifact_sha256: dict[str, str]

    def validate(self) -> None:
        if (
            self.version != 1
            or re.fullmatch(r"[0-9a-f]{32}", self.run_id) is None
            or not isinstance(self.response_id, str)
            or not self.response_id
            or type(self.turn) is not int
            or self.turn < 1
            or (
                self.git_head is not None
                and (
                    not isinstance(self.git_head, str)
                    or HEX_HEAD.fullmatch(self.git_head) is None
                )
            )
            or HEX64.fullmatch(self.source_tree_sha256) is None
            or not isinstance(self.artifact_sha256, dict)
            or set(self.artifact_sha256) != PARTS
            or any(
                not isinstance(value, str)
                or HEX64.fullmatch(value) is None
                for value in self.artifact_sha256.values()
            )
        ):
            raise RecoveryBlocked("Invalid recovery manifest")


class RecoveryManifestStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, manifest: RecoveryManifest) -> None:
        manifest.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".manifest-",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary = file.name
                os.chmod(temporary, 0o600)
                json.dump(asdict(manifest), file, sort_keys=True)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.path)
            temporary = None

        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def load(self) -> RecoveryManifest:
        if (
            self.path.is_symlink()
            or not self.path.is_file()
            or self.path.stat().st_size > 65536
        ):
            raise RecoveryBlocked("Recovery manifest unavailable")

        try:
            data = json.loads(self.path.read_text("utf-8"))
            manifest = RecoveryManifest(**data)
            manifest.validate()
            return manifest
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise RecoveryBlocked(
                "Invalid saved recovery manifest"
            ) from exc


def artifact_paths(
    store: RecoveryManifestStore,
    run_id: str,
) -> dict[str, Path]:
    base = store.path.parent

    if store.path.name != f"{run_id}.manifest.json":
        raise RecoveryBlocked("Manifest path mismatch")

    return {
        "tool": base / f"{run_id}.json",
        "run": base / f"{run_id}.run.json",
        "memory": base / f"{run_id}.memory.json",
        "evidence": base / f"{run_id}.evidence.json",
    }


def artifact_digests(paths: dict[str, Path]) -> dict[str, str]:
    digests = {}

    for name, path in paths.items():
        try:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size > 4_000_000
            ):
                raise RecoveryBlocked(
                    f"Checkpoint artifact unavailable: {name}"
                )

            digests[name] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()

        except OSError as exc:
            raise RecoveryBlocked(
                f"Cannot read checkpoint artifact: {name}"
            ) from exc

    return digests


def seal_recovery_boundary(
    repo_root: Path,
    manifest_store: RecoveryManifestStore,
    snapshot_store: RunSnapshotStore,
    checkpoint_store: CheckpointStore,
    memory_store: MemoryCapsuleStore,
    evidence_store: EvidenceArchiveStore,
) -> RecoveryManifest:
    """Seal a completed boundary after all four files are saved."""
    snapshot = snapshot_store.load()
    validate_recovery_boundary(snapshot, checkpoint_store)

    capsule = memory_store.load()
    archive = evidence_store.load()

    identity = (
        snapshot.run_id,
        snapshot.response_id,
        snapshot.turn,
    )

    if identity != (
        capsule.run_id,
        capsule.response_id,
        capsule.turn,
    ) or identity != (
        archive.run_id,
        archive.response_id,
        archive.turn,
    ):
        raise RecoveryBlocked("Checkpoint generation mismatch")

    paths = artifact_paths(manifest_store, snapshot.run_id)

    if (
        paths["tool"] != checkpoint_store.path
        or paths["run"] != snapshot_store.path
        or paths["memory"] != memory_store.path
        or paths["evidence"] != evidence_store.path
    ):
        raise RecoveryBlocked("Checkpoint store path mismatch")

    head, tree_digest = repository_pin(repo_root)

    manifest = RecoveryManifest(
        version=1,
        run_id=snapshot.run_id,
        response_id=snapshot.response_id,
        turn=snapshot.turn,
        git_head=head,
        source_tree_sha256=tree_digest,
        artifact_sha256=artifact_digests(paths),
    )

    manifest_store.save(manifest)
    return manifest


def verify_recovery_manifest(
    repo_root: Path,
    manifest_store: RecoveryManifestStore,
    snapshot_store: RunSnapshotStore,
    checkpoint_store: CheckpointStore,
) -> RecoveryManifest:
    """Validate the sealed generation; never authorize execution."""
    manifest = manifest_store.load()
    snapshot = snapshot_store.load()

    validate_recovery_boundary(snapshot, checkpoint_store)

    if (
        manifest.run_id,
        manifest.response_id,
        manifest.turn,
    ) != (
        snapshot.run_id,
        snapshot.response_id,
        snapshot.turn,
    ):
        raise RecoveryBlocked("Manifest boundary mismatch")

    paths = artifact_paths(manifest_store, manifest.run_id)

    if artifact_digests(paths) != manifest.artifact_sha256:
        raise RecoveryBlocked("Checkpoint generation is torn")

    head, tree_digest = repository_pin(repo_root)

    if (
        head != manifest.git_head
        or tree_digest != manifest.source_tree_sha256
    ):
        raise RecoveryBlocked("Repository revision changed")

    return manifest
