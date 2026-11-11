
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from agent.attempt_identity import (
    AttemptIdentity,
    AttemptIdentityStore,
)
from agent.attempt_reconciliation import (
    RecoveryDecision,
    assess_attempt_recovery,
)
from agent.generation_attempt_journal import (
    GenerationAttemptJournal,
)

from tests.test_evidence_archive import archive_boundary
from tests.test_recovery_generations import generation_setup, publish


@pytest.fixture
def ids():
    return NS(
        operation_id=uuid4().hex,
        run_id=uuid4().hex,
        generation_id=uuid4().hex,
    )


def assess(tmp_path, ids):
    return assess_attempt_recovery(
        repo_root=tmp_path,
        checkpoint_root=tmp_path,
        identity_root=tmp_path / "identities",
        journal_root=tmp_path / "attempts",
        operation_id=ids.operation_id,
    )


def prepare(tmp_path, ids):
    identity_root = tmp_path / "identities"
    identity_root.mkdir()

    store = AttemptIdentityStore(
        identity_root, ids.operation_id
    )
    store.save_new(
        AttemptIdentity(
            ids.operation_id,
            ids.run_id,
            ids.generation_id,
        )
    )

    journal_root = tmp_path / "attempts"
    journal_root.mkdir()

    return GenerationAttemptJournal(
        journal_root, ids.operation_id
    )


def mock_current(monkeypatch, ids):
    from agent import attempt_reconciliation

    monkeypatch.setattr(
        attempt_reconciliation.GenerationStore,
        "current",
        lambda self, repo_root: NS(
            run_id=ids.run_id,
            generation_id=ids.generation_id,
        ),
    )


def test_no_submission_requires_checkpoint_inspection(
    tmp_path, ids, monkeypatch
):
    mock_current(monkeypatch, ids)
    prepare(tmp_path, ids)

    result = assess(tmp_path, ids)

    assert result.decision == RecoveryDecision.INSPECT_CHECKPOINT


def test_submission_intent_blocks_replay(
    tmp_path, ids, monkeypatch
):
    mock_current(monkeypatch, ids)
    journal = prepare(tmp_path, ids)
    journal.record_submission_intent()

    result = assess(tmp_path, ids)

    assert result.decision == RecoveryDecision.BLOCK
    assert result.reason == "generation_outcome_ambiguous"


def test_response_receipt_requires_reconciliation(
    tmp_path, ids, monkeypatch
):
    mock_current(monkeypatch, ids)
    journal = prepare(tmp_path, ids)
    journal.record_submission_intent()
    journal.record_response("resp-123", "completed")

    result = assess(tmp_path, ids)

    assert result.decision == RecoveryDecision.RECONCILE_RESPONSE
    assert result.response_id == "resp-123"


def test_generation_mismatch_blocks(
    tmp_path, ids, monkeypatch
):
    prepare(tmp_path, ids)

    from agent import attempt_reconciliation

    monkeypatch.setattr(
        attempt_reconciliation.GenerationStore,
        "current",
        lambda self, repo_root: NS(
            run_id=ids.run_id,
            generation_id=uuid4().hex,
        ),
    )

    result = assess(tmp_path, ids)

    assert result.decision == RecoveryDecision.BLOCK
    assert result.reason == "generation_identity_mismatch"


def test_missing_identity_blocks(
    tmp_path, ids, monkeypatch
):
    mock_current(monkeypatch, ids)

    result = assess(tmp_path, ids)

    assert result.decision == RecoveryDecision.BLOCK


def test_submission_intent_blocks_replay_across_published_generations(
    generation_setup,
):
    repo, store, _ = generation_setup
    generation = publish(generation_setup)
    ids = NS(
        operation_id=uuid4().hex,
        run_id=generation.run_id,
        generation_id=generation.generation_id,
    )
    journal = prepare(store.root, ids)
    journal.record_submission_intent()

    recovery_args = dict(
        repo_root=repo,
        checkpoint_root=store.root,
        identity_root=store.root / "identities",
        journal_root=store.root / "attempts",
        operation_id=ids.operation_id,
    )
    result = assess_attempt_recovery(**recovery_args)

    assert result.decision == RecoveryDecision.BLOCK
    assert result.reason == "generation_outcome_ambiguous"

    replacement = publish(generation_setup)
    assert replacement.generation_id != generation.generation_id

    result = assess_attempt_recovery(**recovery_args)

    assert result.decision == RecoveryDecision.BLOCK
    assert result.reason == "generation_identity_mismatch"
