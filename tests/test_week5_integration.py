
import json
from types import SimpleNamespace as NS

import pytest

from agent.model_execution_pipeline import (
    execute_model_request,
)
from agent.model_protocol import ModelProtocolError
from agent.token_budget import (
    TokenBudgetExceeded,
    TokenCountUnavailable,
)
from agent.request_lifecycle import RequestOutcome
from agent.trace import RunTrace


def make_response(
    *,
    status="completed",
    model="test-model",
    output=None,
):
    if output is None:
        output = [
            NS(
                type="message",
                content=[
                    NS(
                        type="output_text",
                        text="Integration successful",
                    )
                ],
            )
        ]

    return NS(
        id="resp-integration",
        model=model,
        status=status,
        output=output,
        _request_id="req-integration",
        usage=NS(
            input_tokens=30,
            output_tokens=10,
        ),
    )


class FakeTokenCounter:
    def __init__(self, client):
        self.client = client

    def count(self, **kwargs):
        self.client.count_calls += 1

        if self.client.count_error:
            raise RuntimeError("count unavailable")

        return NS(input_tokens=self.client.token_count)


class FakeResponses:
    def __init__(self, client):
        self.client = client
        self.input_tokens = FakeTokenCounter(client)

    def create(self, **kwargs):
        self.client.create_calls += 1

        if self.client.generation_error:
            raise self.client.generation_error

        return self.client.response


class FakeClient:
    def __init__(
        self,
        *,
        token_count=100,
        response=None,
        count_error=False,
        generation_error=None,
    ):
        self.token_count = token_count
        self.response = response or make_response()
        self.count_error = count_error
        self.generation_error = generation_error
        self.count_calls = 0
        self.create_calls = 0
        self.responses = FakeResponses(self)


def request_payload():
    return {
        "model": "test-model",
        "input": "Explain this code",
        "max_output_tokens": 100,
    }


def read_events(trace):
    return [
        json.loads(line)
        for line in trace.path.read_text().splitlines()
    ]


def test_happy_path_end_to_end(tmp_path):
    client = FakeClient()
    trace = RunTrace(tmp_path)

    result = execute_model_request(
        client,
        request_payload(),
        trace,
        context_window=1000,
        safety_reserve_tokens=100,
    )

    assert result.outcome == RequestOutcome.COMPLETED
    assert result.attempts == 1
    assert result.reply.text == "Integration successful"
    assert client.count_calls == 1
    assert client.create_calls == 1

    events = read_events(trace)
    names = [event["event"] for event in events]

    assert names == [
        "model_operation_started",
        "model_attempt_started",
        "model_attempt_returned",
        "model_operation_finished",
        "model_protocol_accepted",
    ]

    assert all(
        event["operation_id"] == result.operation_id
        for event in events
    )


def test_oversized_request_never_generates(tmp_path):
    client = FakeClient(token_count=900)
    trace = RunTrace(tmp_path)

    with pytest.raises(TokenBudgetExceeded):
        execute_model_request(
            client,
            request_payload(),
            trace,
            context_window=1000,
            safety_reserve_tokens=100,
        )

    assert client.count_calls == 1
    assert client.create_calls == 0

    names = [
        event["event"]
        for event in read_events(trace)
    ]

    assert "model_attempt_failed" in names
    assert "model_operation_failed" in names
    assert "model_attempt_returned" not in names


def test_count_failure_never_generates(tmp_path):
    client = FakeClient(count_error=True)

    with pytest.raises(TokenCountUnavailable):
        execute_model_request(
            client,
            request_payload(),
            RunTrace(tmp_path),
            context_window=1000,
            safety_reserve_tokens=100,
        )

    assert client.create_calls == 0


def test_incomplete_response_not_validated(tmp_path):
    client = FakeClient(
        response=make_response(status="incomplete")
    )
    trace = RunTrace(tmp_path)

    result = execute_model_request(
        client,
        request_payload(),
        trace,
        context_window=1000,
        safety_reserve_tokens=100,
    )

    assert result.outcome == RequestOutcome.INCOMPLETE
    assert result.reply is None

    names = [
        event["event"]
        for event in read_events(trace)
    ]

    assert "model_protocol_accepted" not in names


def test_malformed_completed_response_rejected(tmp_path):
    client = FakeClient(
        response=make_response(
            output=[NS(type="function_call", name="search")]
        )
    )
    trace = RunTrace(tmp_path)

    with pytest.raises(ModelProtocolError):
        execute_model_request(
            client,
            request_payload(),
            trace,
            context_window=1000,
            safety_reserve_tokens=100,
        )

    names = [
        event["event"]
        for event in read_events(trace)
    ]

    assert "model_protocol_rejected" in names
    assert "model_protocol_accepted" not in names


def test_tool_call_is_not_executed(tmp_path):
    response = make_response(
        output=[
            NS(
                type="function_call",
                name="search_repository",
                call_id="call-123",
                arguments='{"query":"test"}',
            )
        ]
    )

    client = FakeClient(response=response)

    result = execute_model_request(
        client,
        request_payload(),
        RunTrace(tmp_path),
        context_window=1000,
        safety_reserve_tokens=100,
    )

    assert result.reply.requires_tools is True
    assert result.reply.has_final_text is False
    assert client.create_calls == 1
