
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


@pytest.mark.parametrize("crash_before_correlation", [False, True])
def test_correlated_gateway_order_and_receipt_recovery(
    setup, monkeypatch, tmp_path, crash_before_correlation,
):
    from agent.admitted_generation_factory import build_admitted_gateway
    from agent.deadline_gateway import DeadlineBudget
    from agent.provider_correlation import ProviderCorrelationStore
    from agent.provider_outcome_policy import OutcomeAction, decide_outcome
    from agent.recovery_generations import GenerationStore

    admission, fencing, token, current = setup
    monkeypatch.setattr(GenerationStore, "current", lambda self, root: current)
    correlation_root = tmp_path / "correlations"
    operation_id = admission.journal.operation_id
    events = []
    client = FakeClient()

    def journal():
        return GenerationAttemptJournal(admission.journal.root, operation_id)

    def correlation():
        return ProviderCorrelationStore(correlation_root, operation_id)

    def build(provider, ownership):
        return build_admitted_gateway(
            provider,
            operation_id=operation_id,
            token=ownership,
            repo_root=admission.repo_root,
            checkpoint_root=admission.generations.root,
            fencing_root=fencing.root,
            identity_root=admission.identity.root,
            journal_root=admission.journal.root,
            correlation_root=correlation_root,
            context_window=1000,
            safety_reserve_tokens=100,
            budget=DeadlineBudget.start(10, clock=FakeClock()),
        )

    gateway = build(client, token)
    validate = GenerationFencing._validate
    intent = GenerationAttemptJournal.record_submission_intent
    receipt = GenerationAttemptJournal.record_response
    correlate = ProviderCorrelationStore.record_response
    with_options = client.with_options

    class SimulatedCrash(BaseException):
        pass

    def checked_validate(self, ownership):
        validate(self, ownership)
        events.append("fencing validation")

    def checked_intent(self):
        result = intent(self)
        assert journal().load().state == AttemptState.SUBMISSION_INTENT
        events.append("durable submission intent")
        return result

    def checked_options(**options):
        stage_client = with_options(**options)
        create = stage_client.responses.create

        def checked_create(**request):
            assert journal().load().state == AttemptState.SUBMISSION_INTENT
            assert request["extra_headers"]["X-Client-Request-Id"] == (
                correlation().load().client_request_id
            )
            events.append("provider call")
            return create(**request)

        monkeypatch.setattr(stage_client.responses, "create", checked_create)
        return stage_client

    def checked_receipt(self, response_id, status):
        result = receipt(self, response_id, status)
        persisted = journal().load()
        assert persisted.state == AttemptState.RESPONSE_RECEIVED
        assert persisted.response_id == response_id
        assert correlation().load().response_id is None
        events.append("durable response receipt")
        return result

    def checked_correlation(self, response_id):
        assert journal().load().response_id == response_id
        if crash_before_correlation:
            raise SimulatedCrash()
        correlate(self, response_id)
        assert correlation().load().response_id == response_id
        events.append("correlation update")

    with monkeypatch.context() as hooks:
        hooks.setattr(GenerationFencing, "_validate", checked_validate)
        hooks.setattr(GenerationAttemptJournal, "record_submission_intent", checked_intent)
        hooks.setattr(GenerationAttemptJournal, "record_response", checked_receipt)
        hooks.setattr(ProviderCorrelationStore, "record_response", checked_correlation)
        hooks.setattr(client, "with_options", checked_options)
        if crash_before_correlation:
            with pytest.raises(SimulatedCrash):
                gateway.create(payload())
        else:
            response, _ = gateway.create(payload())
            assert response.id == "resp-test"

    expected = [
        "fencing validation",
        "durable submission intent",
        "provider call",
        "durable response receipt",
        "fencing validation",
    ]
    if not crash_before_correlation:
        expected.append("correlation update")
    assert events == expected
    assert client.generation_calls == 1

    if crash_before_correlation:
        # Reopen stores and use a new owner/client, as after a restart.
        recovered = journal().load()
        assert recovered.state == AttemptState.RESPONSE_RECEIVED
        assert recovered.response_id == "resp-test"
        assert recovered.response_status == "completed"
        assert correlation().load().response_id is None
        assert decide_outcome(
            submission_intent_exists=True,
            response_id=recovered.response_id,
        ) == OutcomeAction.INSPECT_RESPONSE

        recovered_client = FakeClient()
        recovered_token = fencing.claim()
        restarted_gateway = build(recovered_client, recovered_token)
        with pytest.raises(SubmissionAdmissionBlocked, match="reconciliation"):
            restarted_gateway.create(payload())
        assert recovered_client.generation_calls == 0
        assert client.generation_calls == 1
        assert journal().load() == recovered
