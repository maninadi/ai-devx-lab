
from types import SimpleNamespace

import httpx2

from openai import APIStatusError, APITimeoutError

from agent.retry_timing import BackoffPolicy
from agent.request_lifecycle import (
    RequestLifecycle,
    RequestOutcome,
    RetryPolicy,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeGateway:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def create(self, request):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, None


def response(status="completed"):
    return SimpleNamespace(status=status, id="resp-test")


def status_error(code):
    req = httpx2.Request(
        "POST", "https://api.openai.com/v1/responses"
    )
    return APIStatusError(
        "simulated",
        response=httpx2.Response(code, request=req),
        body=None,
    )


def timeout_error():
    req = httpx2.Request(
        "POST", "https://api.openai.com/v1/responses"
    )
    return APITimeoutError(request=req)


def test_backoff_doubles_without_jitter():
    policy = BackoffPolicy(
        base_delay=1,
        max_delay=8,
        jitter_fraction=0,
    )
    assert [
        policy.delay(n) for n in range(1, 6)
    ] == [1, 2, 4, 8, 8]


def test_jitter_is_bounded():
    policy = BackoffPolicy(
        base_delay=2,
        max_delay=8,
        jitter_fraction=0.25,
    )
    assert policy.delay(
        1, random_value=lambda: 0
    ) == 2
    assert policy.delay(
        1, random_value=lambda: 1
    ) == 1.5


def test_retry_waits_before_next_attempt():
    fake_time = FakeClock()
    gateway = FakeGateway([
        status_error(503),
        response(),
    ])

    result = RequestLifecycle(
        gateway,
        policy=RetryPolicy(max_attempts=2),
        can_retry=lambda exc: exc.status_code == 503,
        backoff=BackoffPolicy(
            base_delay=1,
            max_delay=8,
            jitter_fraction=0,
        ),
        deadline_seconds=10,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
    ).execute({})

    assert result.outcome == RequestOutcome.COMPLETED
    assert gateway.calls == 2
    assert fake_time.sleeps == [1]


def test_deadline_blocks_retry():
    fake_time = FakeClock()
    gateway = FakeGateway([
        status_error(503),
        response(),
    ])

    result = RequestLifecycle(
        gateway,
        policy=RetryPolicy(max_attempts=2),
        can_retry=lambda exc: True,
        backoff=BackoffPolicy(
            base_delay=2,
            max_delay=8,
            jitter_fraction=0,
        ),
        deadline_seconds=1,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
    ).execute({})

    assert result.reason == "retry_deadline_exhausted"
    assert gateway.calls == 1
    assert fake_time.sleeps == []


def test_timeout_never_replays():
    fake_time = FakeClock()
    gateway = FakeGateway([
        timeout_error(),
        response(),
    ])

    result = RequestLifecycle(
        gateway,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
    ).execute({})

    assert result.outcome == RequestOutcome.AMBIGUOUS
    assert gateway.calls == 1


def test_reconciliation_recovers_completed_response():
    fake_time = FakeClock()
    gateway = FakeGateway([
        timeout_error(),
        response(),
    ])

    result = RequestLifecycle(
        gateway,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
        reconcile=lambda request: response(),
    ).execute({})

    assert result.outcome == RequestOutcome.COMPLETED
    assert result.reason == "reconciled_completed"
    assert gateway.calls == 1


def test_unresolved_reconciliation_stays_ambiguous():
    fake_time = FakeClock()
    gateway = FakeGateway([
        timeout_error(),
        response(),
    ])

    result = RequestLifecycle(
        gateway,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
        reconcile=lambda request: None,
    ).execute({})

    assert result.outcome == RequestOutcome.AMBIGUOUS
    assert gateway.calls == 1
