

import json
from types import SimpleNamespace

import pytest

from agent.trace import RunTrace
from agent.request_observability import (
    ObservableGateway,
    RequestContext,
    execute_observed,
    safe_provider_request_id,
)
from agent.request_lifecycle import (
    RequestLifecycle,
    RequestOutcome,
)


class FakeGateway:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def create(self, model_request):
        self.calls += 1
        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome, SimpleNamespace(
            input_tokens=40
        )


def fake_response(status="completed"):
    return SimpleNamespace(
        id="resp-test",
        _request_id="req-test-123",
        status=status,
        usage=SimpleNamespace(
            input_tokens=40,
            output_tokens=12,
        ),
    )


def read_events(trace):
    return [
        json.loads(line)
        for line in trace.path.read_text().splitlines()
    ]


def test_context_has_unique_operation_ids():
    first = RequestContext.create("test-model")
    second = RequestContext.create("test-model")

    assert first.operation_id != second.operation_id
    assert first.model == "test-model"


def test_success_emits_correlated_events(tmp_path):
    trace = RunTrace(tmp_path)
    context = RequestContext.create("test-model")

    gateway = ObservableGateway(
        FakeGateway([fake_response()]),
        trace,
        context,
    )

    lifecycle = RequestLifecycle(gateway)

    result = execute_observed(
        lifecycle,
        {"model": "test-model"},
        trace,
        context,
    )

    assert result.outcome == RequestOutcome.COMPLETED

    events = read_events(trace)

    assert [e["event"] for e in events] == [
        "model_operation_started",
        "model_attempt_started",
        "model_attempt_returned",
        "model_operation_finished",
    ]

    assert all(
        e["operation_id"] == context.operation_id
        for e in events
    )

    assert all(
        e["run_id"] == trace.run_id
        for e in events
    )


def test_usage_and_provider_id_recorded(tmp_path):
    trace = RunTrace(tmp_path)
    context = RequestContext.create("test-model")

    gateway = ObservableGateway(
        FakeGateway([fake_response()]),
        trace,
        context,
    )

    gateway.create({"model": "test-model"})

    event = read_events(trace)[-1]

    assert event["input_tokens"] == 40
    assert event["output_tokens"] == 12
    assert event["preflight_input_tokens"] == 40
    assert event["provider_request_id"] == "req-test-123"


def test_failure_records_type_not_message(tmp_path):
    trace = RunTrace(tmp_path)
    context = RequestContext.create("test-model")

    gateway = ObservableGateway(
        FakeGateway([
            ValueError("secret-prompt-content")
        ]),
        trace,
        context,
    )

    with pytest.raises(ValueError):
        gateway.create({
            "model": "test-model",
            "input": "private input",
        })

    raw = trace.path.read_text()

    assert "model_attempt_failed" in raw
    assert "ValueError" in raw
    assert "secret-prompt-content" not in raw
    assert "private input" not in raw


def test_incomplete_outcome_is_traced(tmp_path):
    trace = RunTrace(tmp_path)
    context = RequestContext.create("test-model")

    gateway = ObservableGateway(
        FakeGateway([
            fake_response(status="incomplete")
        ]),
        trace,
        context,
    )

    result = execute_observed(
        RequestLifecycle(gateway),
        {"model": "test-model"},
        trace,
        context,
    )

    assert result.outcome == RequestOutcome.INCOMPLETE

    events = read_events(trace)

    assert events[-1]["outcome"] == "incomplete"
    assert events[-1]["attempts"] == 1


def test_provider_id_validation():
    assert (
        safe_provider_request_id(
            SimpleNamespace(_request_id="req-123")
        )
        == "req-123"
    )

    assert safe_provider_request_id(
        SimpleNamespace(_request_id="bad\nid")
    ) is None
