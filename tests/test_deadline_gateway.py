
from types import SimpleNamespace as NS

import pytest

from agent.deadline_gateway import (
    DeadlineAwareGateway,
    DeadlineBudget,
    DeadlineExhausted,
)
from agent.token_budget import TokenCountUnavailable


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeClient:
    def __init__(
        self,
        clock,
        *,
        preflight_duration=0,
        fail_count=False,
    ):
        self.clock = clock
        self.preflight_duration = preflight_duration
        self.fail_count = fail_count

        self.options = []
        self.count_calls = 0
        self.generation_calls = 0

    def with_options(self, **options):
        self.options.append(options)

        parent = self

        class TokenCounter:
            def count(self, **kwargs):
                parent.count_calls += 1
                parent.clock.advance(
                    parent.preflight_duration
                )

                if parent.fail_count:
                    raise RuntimeError(
                        "Simulated counting failure"
                    )

                return NS(input_tokens=50)

        class Responses:
            input_tokens = TokenCounter()

            def create(self, **kwargs):
                parent.generation_calls += 1
                return NS(status="completed")

        return NS(responses=Responses())


def payload():
    return {
        "model": "test-model",
        "input": "Hello",
        "max_output_tokens": 100,
    }


def make_gateway(client, clock, seconds, stages=None):
    return DeadlineAwareGateway(
        client,
        context_window=1000,
        safety_reserve_tokens=100,
        budget=DeadlineBudget.start(
            seconds,
            clock=clock,
        ),
        on_stage=(
            stages.append
            if stages is not None
            else None
        ),
    )


def test_generation_gets_remaining_budget():
    clock = FakeClock()
    client = FakeClient(
        clock,
        preflight_duration=2,
    )

    gateway = make_gateway(client, clock, 10)
    gateway.create(payload())

    assert client.options == [
        {"timeout": 10.0, "max_retries": 0},
        {"timeout": 8.0, "max_retries": 0},
    ]
    assert client.generation_calls == 1


def test_deadline_exhausted_after_preflight():
    clock = FakeClock()
    client = FakeClient(
        clock,
        preflight_duration=10,
    )
    stages = []

    gateway = make_gateway(
        client, clock, 10, stages
    )

    with pytest.raises(DeadlineExhausted):
        gateway.create(payload())

    assert client.count_calls == 1
    assert client.generation_calls == 0
    assert "generation_submission_started" not in stages


def test_count_failure_never_generates():
    clock = FakeClock()
    client = FakeClient(
        clock,
        fail_count=True,
    )
    stages = []

    gateway = make_gateway(
        client, clock, 10, stages
    )

    with pytest.raises(TokenCountUnavailable):
        gateway.create(payload())

    assert client.generation_calls == 0
    assert stages == ["preflight_started"]


def test_expired_before_preflight():
    clock = FakeClock()
    client = FakeClient(clock)

    gateway = make_gateway(client, clock, 5)
    clock.advance(6)

    with pytest.raises(DeadlineExhausted):
        gateway.create(payload())

    assert client.count_calls == 0
    assert client.generation_calls == 0


def test_stage_order_on_success():
    clock = FakeClock()
    client = FakeClient(clock)
    stages = []

    gateway = make_gateway(
        client, clock, 10, stages
    )

    gateway.create(payload())

    assert stages == [
        "preflight_started",
        "preflight_completed",
        "generation_submission_started",
        "generation_response_received",
    ]
