
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agent.generation_attempt_journal import (
    GenerationAttemptJournal,
)
from agent.provider_correlation import (
    ProviderCorrelation,
    ProviderCorrelationStore,
)
from agent.generation_recovery_audit import (
    RecoveryDisposition,
    audit_generation,
)
from agent.durable_generation_gateway import (
    DurableGenerationGateway,
)
from agent.correlated_generation_gateway import (
    CorrelatedGenerationGateway,
)
from tests.test_submission_admission import setup
from tests.test_evidence_archive import archive_boundary
from tests.test_recovery_generations import generation_setup


def make_operation(tmp_path):
    operation_id = uuid4().hex

    journal = GenerationAttemptJournal(
        tmp_path / "journal",
        operation_id,
    )

    correlation = ProviderCorrelationStore(
        tmp_path / "correlation",
        operation_id,
    )

    correlation.prepare(
        ProviderCorrelation(
            operation_id=operation_id,
            client_request_id=str(uuid4()),
        )
    )

    return operation_id, journal, correlation


def inspect(operation_id, journal, correlation):
    return audit_generation(
        operation_id=operation_id,
        attempt=journal.load(),
        correlation=correlation.load(),
    )


def test_crash_before_submission(tmp_path):
    op, journal, correlation = make_operation(
        tmp_path
    )

    result = inspect(op, journal, correlation)

    assert result.disposition == (
        RecoveryDisposition.BLOCK
    )


def test_crash_after_intent(tmp_path):
    op, journal, correlation = make_operation(
        tmp_path
    )

    journal.record_submission_intent()

    result = inspect(op, journal, correlation)

    assert result.disposition == (
        RecoveryDisposition.RECONCILE
    )


def test_crash_after_durable_receipt(tmp_path):
    op, journal, correlation = make_operation(
        tmp_path
    )

    journal.record_submission_intent()
    journal.record_response(
        "resp_123",
        "completed",
    )

    # Correlation update did not happen.
    result = inspect(op, journal, correlation)

    assert result.disposition == (
        RecoveryDisposition.INSPECT_RESPONSE
    )
    assert result.response_id == "resp_123"


def test_conflicting_response_ids_block(tmp_path):
    op, journal, correlation = make_operation(
        tmp_path
    )

    journal.record_submission_intent()
    journal.record_response(
        "resp_first",
        "completed",
    )
    correlation.record_response("resp_second")

    result = inspect(op, journal, correlation)

    assert result.disposition == (
        RecoveryDisposition.BLOCK
    )


def test_successful_gateway_contract(tmp_path):
    op, journal, correlation = make_operation(
        tmp_path
    )

    calls = []

    class FakeProviderGateway:
        def create(self, request):
            journal.record_submission_intent()
            calls.append(request)

            return (
                SimpleNamespace(
                    id="resp_ok",
                    status="completed",
                ),
                SimpleNamespace(allowed=True),
            )

    durable = DurableGenerationGateway(
        FakeProviderGateway(),
        journal,
    )

    correlated = CorrelatedGenerationGateway(
        durable,
        correlation,
    )

    response, decision = correlated.create(
        {"model": "fake"}
    )

    assert response.id == "resp_ok"
    assert decision.allowed is True
    assert len(calls) == 1

    result = inspect(op, journal, correlation)

    assert result.disposition == (
        RecoveryDisposition.INSPECT_RESPONSE
    )


def test_timeout_is_not_replayed(tmp_path):
    op, journal, correlation = make_operation(
        tmp_path
    )

    calls = []

    class TimeoutProviderGateway:
        def create(self, request):
            journal.record_submission_intent()
            calls.append(request)
            raise TimeoutError("Response lost")

    durable = DurableGenerationGateway(
        TimeoutProviderGateway(),
        journal,
    )

    correlated = CorrelatedGenerationGateway(
        durable,
        correlation,
    )

    with pytest.raises(TimeoutError):
        correlated.create({"model": "fake"})

    assert len(calls) == 1

    result = inspect(op, journal, correlation)

    assert result.disposition == (
        RecoveryDisposition.RECONCILE
    )


def test_full_stack_admitted_generation_and_recovery(setup, generation_setup):
    from agent.admitted_generation_factory import build_admitted_gateway
    from agent.attempt_identity import AttemptIdentity, AttemptIdentityStore
    from agent.deadline_gateway import DeadlineBudget
    from agent.generation_attempt_journal import AttemptState
    from agent.generation_fencing import GenerationFencing
    from agent.submission_admission import SubmissionAdmissionBlocked
    from tests.test_deadline_gateway import FakeClock

    admission, fencing, _, _ = setup
    repo, generations, sources = generation_setup
    generation = generations.publish(repo, *sources)
    assert generations.current(repo) == generation

    # Runtime state belongs beneath the checkpoint directory, which is excluded
    # from source fingerprints. The setup fixture's original files stay intact.
    runtime = generations.root / "full-stack"
    identity_root = runtime / admission.identity.root.name
    fencing_root = runtime / fencing.root.name
    identity_root.mkdir(parents=True)
    fencing_root.mkdir()
    fencing = GenerationFencing(fencing_root)

    # Use a fresh operation bound to the actual published checkpoint.
    operation_id = uuid4().hex
    identity = AttemptIdentityStore(identity_root, operation_id)
    identity.save_new(AttemptIdentity(
        operation_id=operation_id,
        run_id=generation.run_id,
        generation_id=generation.generation_id,
    ))
    token = fencing.claim()
    correlation = ProviderCorrelationStore(
        runtime / "correlation", operation_id,
    )
    original_client_request_id = str(uuid4())
    fencing.guarded(token, lambda: correlation.prepare(ProviderCorrelation(
        operation_id=operation_id,
        client_request_id=original_client_request_id,
    )))
    journal = GenerationAttemptJournal(runtime / admission.journal.root.name, operation_id)
    fake_generation_calls = 0
    counting_requests = []
    stage_options = []
    generation_requests = []

    class FakeSDK:
        def with_options(self, **options):
            stage_options.append(options)

            def count(**request):
                counting_requests.append(request)
                return SimpleNamespace(input_tokens=20)

            def create(**request):
                nonlocal fake_generation_calls
                fake_generation_calls += 1
                generation_requests.append(request)
                assert journal.load().state == AttemptState.SUBMISSION_INTENT
                return SimpleNamespace(id="resp-full-stack", status="completed")

            return SimpleNamespace(responses=SimpleNamespace(
                input_tokens=SimpleNamespace(count=count), create=create,
            ))

    gateway = build_admitted_gateway(
        FakeSDK(),
        operation_id=operation_id,
        token=token,
        repo_root=repo,
        checkpoint_root=generations.root,
        fencing_root=fencing.root,
        identity_root=identity.root,
        journal_root=journal.root,
        correlation_root=correlation.root,
        context_window=1000,
        safety_reserve_tokens=100,
        budget=DeadlineBudget.start(10, clock=FakeClock()),
    )
    request = {
        "model": "fake", "input": "Hello", "max_output_tokens": 100,
    }
    response, _ = gateway.create(request)

    assert fake_generation_calls == 1
    receipt = journal.load()
    saved_correlation = correlation.load()
    assert receipt.state == AttemptState.RESPONSE_RECEIVED
    assert receipt.response_id == response.id
    assert receipt.response_status == "completed"
    assert saved_correlation.response_id == response.id
    assert saved_correlation.client_request_id == original_client_request_id
    assert generation_requests[0]["extra_headers"]["X-Client-Request-Id"] == (
        original_client_request_id
    )
    assert counting_requests == [{"model": "fake", "input": "Hello"}]
    assert stage_options == [
        {"timeout": 10, "max_retries": 0},
        {"timeout": 10, "max_retries": 0},
    ]
    audit = audit_generation(
        operation_id=operation_id,
        attempt=receipt,
        correlation=saved_correlation,
    )
    assert audit.disposition == RecoveryDisposition.INSPECT_RESPONSE

    reopened_journal = GenerationAttemptJournal(journal.root, operation_id)
    reopened_correlation = ProviderCorrelationStore(correlation.root, operation_id)
    recovered_audit = audit_generation(
        operation_id=operation_id,
        attempt=reopened_journal.load(),
        correlation=reopened_correlation.load(),
    )
    assert recovered_audit.disposition == RecoveryDisposition.INSPECT_RESPONSE
    assert recovered_audit.response_id == response.id

    # The SDK permits more calls; durable admission must prevent generation.
    with pytest.raises(
        SubmissionAdmissionBlocked, match="Existing attempt requires reconciliation",
    ):
        gateway.create(request)
    assert fake_generation_calls == 1
    assert len(counting_requests) == 2  # Preflight precedes admission.
    assert reopened_journal.load() == receipt
    assert reopened_correlation.load() == saved_correlation
