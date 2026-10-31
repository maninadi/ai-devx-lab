
from dataclasses import replace
import shutil
import subprocess

import pytest

from agent.checkpoint import RecoveryBlocked
from agent.context import ContextPolicy
from agent.context_reconstruction import reconstruct_local_context
from agent.recovery_manifest import (
    RecoveryManifestStore,
    repository_pin,
    verify_recovery_manifest,
)

from tests.test_evidence_archive import archive_boundary


def stores_for(boundary):
    repo, snapshot, checkpoint, memory, evidence = boundary
    run_id = snapshot.load().run_id

    manifest = RecoveryManifestStore(
        repo
        / ".agent-checkpoints"
        / f"{run_id}.manifest.json"
    )

    return manifest, snapshot, checkpoint


def verify(boundary):
    manifest, snapshot, checkpoint = stores_for(boundary)

    return verify_recovery_manifest(
        boundary[0],
        manifest,
        snapshot,
        checkpoint,
    )


def test_manifest_seals_complete_generation(archive_boundary):
    manifest = verify(archive_boundary)

    assert manifest.turn == 2
    assert set(manifest.artifact_sha256) == {
        "tool", "run", "memory", "evidence"
    }

    assert manifest.git_head is None


def test_manifest_allows_valid_evidence_audit(archive_boundary):
    manifest, snapshot, checkpoint = stores_for(
        archive_boundary
    )

    report = reconstruct_local_context(
        archive_boundary[0],
        snapshot,
        checkpoint,
        archive_boundary[3],
        context_policy=ContextPolicy(),
        evidence_store=archive_boundary[4],
        manifest_store=manifest,
    )

    assert len(report.evidence_ledger.records) == 6
    assert report.model_resume_allowed is False


def test_unobserved_file_change_blocks(archive_boundary):
    # policy.md was not one of the six observed files.
    (archive_boundary[0] / "policy.md").write_text(
        "Changed policy\n"
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Repository revision changed",
    ):
        verify(archive_boundary)


def test_new_source_file_blocks(archive_boundary):
    (archive_boundary[0] / "new_module.py").write_text(
        "ENABLED = True\n"
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Repository revision changed",
    ):
        verify(archive_boundary)


def test_torn_memory_checkpoint_blocks(archive_boundary):
    # Still valid JSON, but no longer the sealed bytes.
    path = archive_boundary[3].path
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(
        RecoveryBlocked,
        match="Checkpoint generation is torn",
    ):
        verify(archive_boundary)


def test_missing_manifest_blocks(archive_boundary):
    manifest, _, _ = stores_for(archive_boundary)
    manifest.path.unlink()

    with pytest.raises(
        RecoveryBlocked,
        match="Recovery manifest unavailable",
    ):
        verify(archive_boundary)


def test_rewritten_snapshot_blocks(archive_boundary):
    snapshot_store = archive_boundary[1]

    snapshot_store.save(
        replace(
            snapshot_store.load(),
            deadline_utc="2099-01-01T00:00:00+00:00",
        )
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Checkpoint generation is torn",
    ):
        verify(archive_boundary)


def test_git_head_change_is_detected(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("Git executable unavailable")

    def git(*args):
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
        )

    git("init")
    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.invalid")

    (tmp_path / "sample.py").write_text("VALUE = 1\n")
    git("add", "sample.py")
    git("commit", "-m", "first")

    first_head, first_tree = repository_pin(tmp_path)

    git("commit", "--allow-empty", "-m", "second")

    second_head, second_tree = repository_pin(tmp_path)

    assert first_head != second_head
    assert first_tree == second_tree
