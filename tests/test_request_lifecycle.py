
from types import SimpleNamespace

import httpx2
import pytest

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)

from agent.request_lifecycle import (
    RequestLifecycle,
    RequestOutcome,
    RetryPolicy,
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

        return outcome, None


def fake_response(status="completed"):
    return SimpleNamespace(
        id="resp-test",
        status=status,
    )


def http_error(status_code):
    req = httpx2.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    )
    response = httpx2.Response(
        status_code,
        request=req,
    )

    return APIStatusError(
        "simulated HTTP error",
        response=response,
        body=None,
    )


def timeout_error():
    req = httpx2.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    )
    return APITimeoutError(request=req)


def connection_error():
    req = httpx2.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    )
    return APIConnectionError(request=req)


def test_completed_response():
    gateway = FakeGateway([
        fake_response(),
    ])

    result = RequestLifecycle(
        gateway
    ).execute({})

    assert result.outcome == RequestOutcome.COMPLETED
    assert result.attempts == 1
    assert gateway.calls == 1


def test_timeout_is_ambiguous():
    gateway = FakeGateway([
        timeout_error(),
        fake_response(),
    ])

    result = RequestLifecycle(
        gateway
    ).execute({})

    assert result.outcome == RequestOutcome.AMBIGUOUS
    assert gateway.calls == 1


def test_connection_error_is_ambiguous():
    gateway = FakeGateway([
        connection_error(),
        fake_response(),
    ])

    result = RequestLifecycle(
        gateway
    ).execute({})

    assert result.outcome == RequestOutcome.AMBIGUOUS
    assert gateway.calls == 1


def test_status_error_no_retry_by_default():
    gateway = FakeGateway([
        http_error(429),
        fake_response(),
    ])

    result = RequestLifecycle(
        gateway
    ).execute({})

    assert result.outcome == RequestOutcome.REJECTED
    assert gateway.calls == 1


def test_explicitly_authorized_retry():
    gateway = FakeGateway([
        http_error(503),
        fake_response(),
    ])

    lifecycle = RequestLifecycle(
        gateway,
        policy=RetryPolicy(max_attempts=2),
        can_retry=lambda exc: (
            isinstance(exc, APIStatusError)
            and exc.status_code == 503
        ),
    )

    result = lifecycle.execute({})

    assert result.outcome == RequestOutcome.COMPLETED
    assert result.attempts == 2
    assert gateway.calls == 2


def test_retry_is_bounded():
    gateway = FakeGateway([
        http_error(503),
        http_error(503),
        fake_response(),
    ])

    lifecycle = RequestLifecycle(
        gateway,
        policy=RetryPolicy(max_attempts=2),
        can_retry=lambda exc: exc.status_code == 503,
    )

    result = lifecycle.execute({})

    assert result.outcome == RequestOutcome.REJECTED
    assert result.attempts == 2
    assert gateway.calls == 2


def test_incomplete_response_not_retried():
    gateway = FakeGateway([
        fake_response("incomplete"),
        fake_response(),
    ])

    result = RequestLifecycle(
        gateway
    ).execute({})

    assert result.outcome == RequestOutcome.INCOMPLETE
    assert gateway.calls == 1


def test_preflight_failure_propagates():
    gateway = FakeGateway([
        ValueError("invalid preflight"),
    ])

    with pytest.raises(
        ValueError,
        match="invalid preflight",
    ):
        RequestLifecycle(gateway).execute({})

    assert gateway.calls == 1


def test_invalid_retry_policy():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
