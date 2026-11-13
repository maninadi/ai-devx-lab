
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agent.attempt_identity import (
    AttemptIdentity,
    AttemptIdentityStore,
)
from agent.generation_attempt_journal import (
    AttemptState,
    GenerationAttemptJournal,
)
from agent.generation_fencing import GenerationFencing
from agent.submission_admission import (
    SubmissionAdmission,
    SubmissionAdmissionBlocked,
)

from tests.test_deadline_gateway import FakeClock
from tests.test_generation_attempt_journal import FakeClient, payload


@pytest.fixture
def setup(tmp_path, monkeypatch):
    fencing_root = tmp_path / "fencing"
    identity_root = tmp_path / "identities"
    journal_root = tmp_path / "journals"

    for root in (
        fencing_root, identity_root, journal_root
    ):
        root.mkdir()

    operation_id = uuid4().hex
    run_id = uuid4().hex
    generation_id = uuid4().hex

    identity = AttemptIdentityStore(
        identity_root, operation_id
    )
    identity.save_new(
        AttemptIdentity(
            operation_id=operation_id,
            run_id=run_id,
            generation_id=generation_id,
        )
    )

    admission = SubmissionAdmission(
        repo_root=tmp_path,
        checkpoint_root=tmp_path / "checkpoints",
        fencing_root=fencing_root,
        identity_root=identity_root,
        journal_root=journal_root,
        operation_id=operation_id,
    )

    current = SimpleNamespace(
        run_id=run_id,
        generation_id=generation_id,
    )
    monkeypatch.setattr(
        admission.generations,
        "current",
        lambda root: current,
    )

    fencing = GenerationFencing(fencing_root)
    token = fencing.claim()

    return admission, fencing, token, current


def test_valid_admission_records_intent(setup):
    admission, fencing, token, current = setup

    admission.admit(token)

    record = admission.journal.load()
    assert record.state == AttemptState.SUBMISSION_INTENT


def test_stale_worker_cannot_record_intent(setup):
    admission, fencing, token, current = setup
    fencing.claim()

    with pytest.raises(SubmissionAdmissionBlocked):
        admission.admit(token)

    assert admission.journal.load() is None


def test_generation_change_blocks_admission(setup):
    admission, fencing, token, current = setup

    admission.generations.current = lambda root: (
        SimpleNamespace(
            run_id=current.run_id,
            generation_id=uuid4().hex,
        )
    )

    with pytest.raises(SubmissionAdmissionBlocked):
        admission.admit(token)

    assert admission.journal.load() is None


def test_duplicate_admission_is_blocked(setup):
    admission, fencing, token, current = setup

    admission.admit(token)

    with pytest.raises(SubmissionAdmissionBlocked):
        admission.admit(token)


def test_missing_identity_blocks_admission(setup):
    admission, fencing, token, current = setup

    admission.identity.path.unlink()

    with pytest.raises(SubmissionAdmissionBlocked):
        admission.admit(token)

    assert admission.journal.load() is None


def test_gateway_fences_submission_and_persists_intent_before_provider(
    setup, monkeypatch,
):
    from agent.admitted_generation_factory import build_admitted_gateway
    from agent.deadline_gateway import DeadlineBudget
    from agent.recovery_generations import GenerationStore

    admission, fencing, stale_token, current = setup
    valid_token = fencing.claim()
    monkeypatch.setattr(
        GenerationStore,
        "current",
        lambda self, root: current,
    )

    clock = FakeClock()
    client = FakeClient()
    with_options = client.with_options
    observed_states = []

    def checked_options(**options):
        stage_client = with_options(**options)
        create = stage_client.responses.create

        def checked_create(**request):
            # Read persisted state at the provider boundary, before
            # delegating to the existing Day 37 fake provider.
            record = GenerationAttemptJournal(
                admission.journal.root,
                admission.journal.operation_id,
            ).load()
            assert record is not None
            assert record.state == AttemptState.SUBMISSION_INTENT
            observed_states.append(record.state)
            return create(**request)

        monkeypatch.setattr(
            stage_client.responses, "create", checked_create,
        )
        return stage_client

    monkeypatch.setattr(client, "with_options", checked_options)

    def gateway(token):
        return build_admitted_gateway(
            client,
            operation_id=admission.journal.operation_id,
            token=token,
            repo_root=admission.repo_root,
            checkpoint_root=admission.generations.root,
            fencing_root=fencing.root,
            identity_root=admission.identity.root,
            journal_root=admission.journal.root,
            context_window=1000,
            safety_reserve_tokens=100,
            budget=DeadlineBudget.start(10, clock=clock),
        )

    with pytest.raises(SubmissionAdmissionBlocked):
        gateway(stale_token).create(payload())

    assert client.generation_calls == 0
    assert observed_states == []
    assert admission.journal.load() is None

    response, _ = gateway(valid_token).create(payload())

    assert client.generation_calls == 1
    assert observed_states == [AttemptState.SUBMISSION_INTENT]
    assert response.id == "resp-test"
    record = admission.journal.load()
    assert record.state == AttemptState.RESPONSE_RECEIVED
    assert record.response_id == response.id
