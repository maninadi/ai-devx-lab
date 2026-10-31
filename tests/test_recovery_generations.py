
import json

import pytest

from agent.checkpoint import RecoveryBlocked
from agent.recovery_generations import GenerationStore
from agent.recovery_manifest import RecoveryManifestStore

from tests.test_evidence_archive import archive_boundary


@pytest.fixture
def generation_setup(archive_boundary):
    repo, snapshot, checkpoint, memory, evidence = (
        archive_boundary
    )

    run_id = snapshot.load().run_id
    base = repo / ".agent-checkpoints"

    manifest = RecoveryManifestStore(
        base / f"{run_id}.manifest.json"
    )

    store = GenerationStore(base)

    sources = (
        manifest,
        snapshot,
        checkpoint,
        memory,
        evidence,
    )

    return repo, store, sources


def publish(setup, fail_at=None):
    repo, store, sources = setup

    return store.publish(
        repo,
        *sources,
        fail_at=fail_at,
    )


def test_first_generation_is_committed(generation_setup):
    repo, store, _ = generation_setup

    committed = publish(generation_setup)
    current = store.current(repo)

    assert current.generation_id == committed.generation_id
    assert current.directory.is_dir()
    assert len(list(current.directory.iterdir())) == 5


def test_crash_after_copy_preserves_previous(
    generation_setup,
):
    repo, store, _ = generation_setup

    previous = publish(generation_setup)

    with pytest.raises(
        RuntimeError,
        match="Injected crash after copy",
    ):
        publish(generation_setup, "after_copy")

    current = store.current(repo)

    assert current.generation_id == previous.generation_id


def test_crash_before_pointer_preserves_previous(
    generation_setup,
):
    repo, store, _ = generation_setup

    previous = publish(generation_setup)

    with pytest.raises(
        RuntimeError,
        match="Injected crash before pointer",
    ):
        publish(generation_setup, "before_pointer")

    current = store.current(repo)

    assert current.generation_id == previous.generation_id


def test_crash_after_pointer_selects_new_generation(
    generation_setup,
):
    repo, store, _ = generation_setup

    previous = publish(generation_setup)

    with pytest.raises(
        RuntimeError,
        match="Injected crash after pointer",
    ):
        publish(generation_setup, "after_pointer")

    current = store.current(repo)

    assert current.generation_id != previous.generation_id
    assert previous.directory.exists()


def test_corrupted_current_generation_blocks(
    generation_setup,
):
    repo, store, _ = generation_setup

    current = publish(generation_setup)

    snapshot_path = (
        current.directory
        / f"{current.run_id}.run.json"
    )

    snapshot_path.write_bytes(
        snapshot_path.read_bytes() + b"\n"
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Checkpoint generation is torn",
    ):
        store.current(repo)


def test_pointer_path_traversal_is_rejected(
    generation_setup,
):
    repo, store, _ = generation_setup

    publish(generation_setup)

    store.pointer.write_text(
        json.dumps({
            "version": 1,
            "generation_id": "../outside",
            "run_id": "a" * 32,
        })
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Invalid checkpoint generation identity",
    ):
        store.current(repo)


def test_source_revision_change_blocks_publish(
    generation_setup,
):
    repo, store, _ = generation_setup

    (repo / "new_policy.py").write_text(
        "ALLOWED = False\n"
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Repository revision changed",
    ):
        publish(generation_setup)


def test_immutable_previous_generation_remains(
    generation_setup,
):
    repo, store, _ = generation_setup

    first = publish(generation_setup)

    original_bytes = {
        path.name: path.read_bytes()
        for path in first.directory.iterdir()
    }

    second = publish(generation_setup)

    assert first.generation_id != second.generation_id

    assert {
        path.name: path.read_bytes()
        for path in first.directory.iterdir()
    } == original_bytes

    assert store.current(repo).generation_id == (
        second.generation_id
    )
