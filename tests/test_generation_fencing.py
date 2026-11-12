
import json

import pytest

from agent.generation_fencing import (
    FencingBlocked,
    GenerationFencing,
)

from tests.test_evidence_archive import archive_boundary
from tests.test_recovery_generations import generation_setup


@pytest.fixture
def fencing(tmp_path):
    root = tmp_path / "fencing"
    root.mkdir()
    return GenerationFencing(root)


def test_claims_increase_monotonically(fencing):
    first = fencing.claim()
    second = fencing.claim()

    assert first == 1
    assert second == 2


def test_new_owner_fences_old_owner(fencing):
    old = fencing.claim()
    new = fencing.claim()

    with pytest.raises(FencingBlocked):
        fencing.require_current(old)

    fencing.require_current(new)


def test_stale_action_never_executes(fencing):
    old = fencing.claim()
    fencing.claim()

    calls = []

    with pytest.raises(FencingBlocked):
        fencing.guarded(
            old,
            lambda: calls.append("published"),
        )

    assert calls == []


def test_current_owner_can_execute(fencing):
    token = fencing.claim()
    calls = []

    fencing.guarded(
        token,
        lambda: calls.append("published"),
    )

    assert calls == ["published"]


def test_restart_preserves_epoch(fencing):
    first = fencing.claim()

    restarted = GenerationFencing(fencing.root)
    second = restarted.claim()

    assert second > first


def test_corrupted_state_blocks_claim(fencing):
    fencing.claim()
    fencing.state_path.write_text(
        '{"version": 1, "token": "bad"}'
    )

    with pytest.raises(FencingBlocked):
        fencing.claim()


def test_failed_stale_publication_is_not_invoked(
    fencing, monkeypatch, tmp_path
):
    from agent.fenced_generation_publisher import (
        FencedGenerationPublisher,
    )

    publisher = FencedGenerationPublisher(
        checkpoint_root=tmp_path / "checkpoints",
        fencing_root=fencing.root,
    )

    called = []

    def fake_publish(*args, **kwargs):
        called.append(True)

    monkeypatch.setattr(
        publisher.store,
        "publish",
        fake_publish,
    )

    stale = fencing.claim()
    fencing.claim()

    with pytest.raises(FencingBlocked):
        publisher.publish(
            token=stale,
            repo_root=tmp_path,
            source_manifest=None,
            source_snapshot=None,
            source_checkpoint=None,
            source_memory=None,
            source_evidence=None,
        )

    assert called == []


def test_real_generation_publication_fences_stale_owner(
    generation_setup,
):
    from agent.fenced_generation_publisher import (
        FencedGenerationPublisher,
    )

    repo, store, sources = generation_setup
    fencing_root = store.root / "fencing"
    fencing_root.mkdir()
    fencing = GenerationFencing(fencing_root)
    publisher = FencedGenerationPublisher(
        checkpoint_root=store.root,
        fencing_root=fencing.root,
    )
    publication = dict(
        repo_root=repo,
        **dict(zip(
            (
                "source_manifest",
                "source_snapshot",
                "source_checkpoint",
                "source_memory",
                "source_evidence",
            ),
            sources,
            strict=True,
        )),
    )

    first_token = fencing.claim()
    assert first_token == 1
    first = publisher.publish(token=first_token, **publication)
    assert store.current(repo).generation_id == first.generation_id
    original_pointer = store.pointer.read_bytes()

    second_token = fencing.claim()
    assert second_token == 2

    with pytest.raises(FencingBlocked, match="Stale fencing token"):
        publisher.publish(token=first_token, **publication)

    assert store.pointer.read_bytes() == original_pointer
    assert store.current(repo).generation_id == first.generation_id

    second = publisher.publish(token=second_token, **publication)

    assert second.generation_id != first.generation_id
    assert store.current(repo).generation_id == second.generation_id
    assert store.pointer.read_bytes() != original_pointer
