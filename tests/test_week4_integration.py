
from dataclasses import replace

import pytest

from agent.checkpoint import (
    RecoveryBlocked,
)
from agent.context import ContextPolicy
from agent.context_reconstruction import (
    reconstruct_local_context,
)
from agent.recovery_generations import GenerationStore
from agent.recovery_manifest import RecoveryManifestStore
from agent.run_recovery import validate_recovery_boundary

from tests.test_evidence_archive import archive_boundary


@pytest.fixture
def committed_boundary(archive_boundary):
    repo, snapshot, checkpoint, memory, evidence = (
        archive_boundary
    )

    run_id = snapshot.load().run_id
    root = repo / ".agent-checkpoints"

    manifest = RecoveryManifestStore(
        root / f"{run_id}.manifest.json"
    )

    store = GenerationStore(root)

    sources = (
        manifest,
        snapshot,
        checkpoint,
        memory,
        evidence,
    )

    first = store.publish(repo, *sources)

    return repo, store, sources, first


def audit(repo, generation):
    manifest, snapshot, checkpoint, memory, evidence = (
        generation.stores()
    )

    return reconstruct_local_context(
        repo,
        snapshot,
        checkpoint,
        memory,
        context_policy=ContextPolicy(),
        evidence_store=evidence,
        manifest_store=manifest,
    )


def test_committed_generation_restores_evidence(
    committed_boundary,
):
    repo, store, _, first = committed_boundary

    current = store.current(repo)
    report = audit(repo, current)

    assert current.generation_id == first.generation_id
    assert report.response_id == "resp-2"
    assert len(report.evidence_ledger.records) == 6
    assert report.model_resume_allowed is False


def test_crash_before_commit_keeps_previous_auditable(
    committed_boundary,
):
    repo, store, sources, first = committed_boundary

    with pytest.raises(
        RuntimeError,
        match="Injected crash before pointer",
    ):
        store.publish(
            repo,
            *sources,
            fail_at="before_pointer",
        )

    current = store.current(repo)

    assert current.generation_id == first.generation_id
    assert len(audit(repo, current).evidence_ledger.records) == 6


def test_crash_after_commit_selects_new_generation(
    committed_boundary,
):
    repo, store, sources, first = committed_boundary

    with pytest.raises(
        RuntimeError,
        match="Injected crash after pointer",
    ):
        store.publish(
            repo,
            *sources,
            fail_at="after_pointer",
        )

    current = store.current(repo)

    assert current.generation_id != first.generation_id
    assert first.directory.exists()
    assert audit(repo, current).model_resume_allowed is False


def test_corrupt_current_blocks_without_fallback(
    committed_boundary,
):
    repo, store, sources, first = committed_boundary

    second = store.publish(repo, *sources)

    # Damage only the currently selected generation.
    path = (
        second.directory
        / f"{second.run_id}.memory.json"
    )
    path.write_bytes(path.read_bytes() + b"\n")

    # Previous committed data is still present.
    assert first.directory.exists()

    # But recovery must not silently choose it.
    with pytest.raises(
        RecoveryBlocked,
        match="Checkpoint generation is torn",
    ):
        store.current(repo)


def test_repository_drift_blocks_audit(
    committed_boundary,
):
    repo, store, _, _ = committed_boundary

    # The original evidence excerpts are untouched.
    (repo / "unexpected_change.py").write_text(
        "FEATURE_ENABLED = False\n"
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Repository revision changed",
    ):
        store.current(repo)


def test_ambiguous_request_cannot_be_replayed(
    committed_boundary,
):
    repo, store, _, _ = committed_boundary

    current = store.current(repo)
    _, snapshot_store, checkpoint_store, _, _ = (
        current.stores()
    )

    ambiguous = replace(
        snapshot_store.load(),
        model_request_started=True,
    )

    with pytest.raises(
        RecoveryBlocked,
        match="model request may already have started",
    ):
        validate_recovery_boundary(
            ambiguous,
            checkpoint_store,
        )
