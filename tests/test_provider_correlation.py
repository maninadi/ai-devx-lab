
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agent.provider_correlation import (
    ProviderCorrelation,
    ProviderCorrelationStore,
    CorrelationConflict,
)
from agent.provider_outcome_policy import (
    OutcomeAction,
    decide_outcome,
)
from agent.correlated_generation_gateway import (
    CorrelatedGenerationGateway,
)


def make_store(tmp_path):
    operation_id = uuid4().hex
    store = ProviderCorrelationStore(
        tmp_path, operation_id
    )
    store.prepare(
        ProviderCorrelation(
            operation_id=operation_id,
            client_request_id=str(uuid4()),
        )
    )
    return store


def test_correlation_survives_restart(tmp_path):
    store = make_store(tmp_path)
    reopened = ProviderCorrelationStore(
        tmp_path, store.load().operation_id
    )
    assert reopened.load() == store.load()


def test_duplicate_preparation_rejected(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(CorrelationConflict):
        store.prepare(store.load())


def test_response_id_persisted(tmp_path):
    store = make_store(tmp_path)
    store.record_response("resp_123")
    assert store.load().response_id == "resp_123"


def test_ambiguous_outcome_requires_reconciliation():
    assert decide_outcome(
        submission_intent_exists=True,
        response_id=None,
    ) == OutcomeAction.RECONCILE_PROVIDER


def test_known_response_requires_inspection():
    assert decide_outcome(
        submission_intent_exists=True,
        response_id="resp_123",
    ) == OutcomeAction.INSPECT_RESPONSE


def test_gateway_records_response(tmp_path):
    store = make_store(tmp_path)

    class FakeGateway:
        def create(self, request):
            return SimpleNamespace(id="resp_abc"), None

    gateway = CorrelatedGenerationGateway(
        FakeGateway(), store
    )

    result, decision = gateway.create({"model": "fake"})
    assert result.id == "resp_abc"
    assert store.load().response_id == "resp_abc"


def test_provider_timeout_does_not_create_receipt(tmp_path):
    store = make_store(tmp_path)

    class TimeoutGateway:
        def create(self, request):
            raise TimeoutError("Lost response")

    gateway = CorrelatedGenerationGateway(
        TimeoutGateway(), store
    )

    with pytest.raises(TimeoutError):
        gateway.create({})

    assert store.load().response_id is None
