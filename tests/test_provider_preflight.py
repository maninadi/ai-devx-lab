
from types import SimpleNamespace

import pytest

from agent.model_request_gateway import (
    ModelRequestGateway,
)
from agent.provider_token_counter import (
    ProviderTokenCountError,
    countable_request,
)
from agent.token_budget import (
    TokenBudgetExceeded,
    TokenCountUnavailable,
)


class FakeInputTokens:
    def __init__(self, tokens):
        self.tokens = tokens
        self.calls = []

    def count(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            input_tokens=self.tokens
        )


class FakeResponses:
    def __init__(self, tokens):
        self.input_tokens = FakeInputTokens(tokens)
        self.generation_calls = []

    def create(self, **kwargs):
        self.generation_calls.append(kwargs)

        return SimpleNamespace(
            id="resp-test",
            status="completed",
            usage=SimpleNamespace(
                input_tokens=self.input_tokens.tokens,
                output_tokens=5,
            ),
        )


class FakeClient:
    def __init__(self, tokens):
        self.responses = FakeResponses(tokens)


@pytest.fixture
def model_request():
    return {
        "model": "gpt-4.1-mini",
        "instructions": "Answer briefly.",
        "input": "What is a token?",
        "max_output_tokens": 200,
        "store": False,
    }


def test_count_payload_omits_generation_fields(model_request):
    payload = countable_request(model_request)

    assert payload["model"] == "gpt-4.1-mini"
    assert payload["input"] == "What is a token?"
    assert "max_output_tokens" not in payload
    assert "store" not in payload


def test_unknown_fields_rejected(model_request):
    model_request["unknown_new_field"] = "value"

    with pytest.raises(ProviderTokenCountError):
        countable_request(model_request)


def test_allowed_request_generates(model_request):
    client = FakeClient(tokens=400)

    gateway = ModelRequestGateway(
        client,
        context_window=1000,
        safety_reserve_tokens=100,
    )

    response, decision = gateway.create(model_request)

    assert decision.allowed
    assert response.id == "resp-test"
    assert len(client.responses.generation_calls) == 1


def test_overflow_never_generates(model_request):
    client = FakeClient(tokens=701)

    gateway = ModelRequestGateway(
        client,
        context_window=1000,
        safety_reserve_tokens=100,
    )

    with pytest.raises(TokenBudgetExceeded):
        gateway.create(model_request)

    assert client.responses.generation_calls == []


def test_missing_count_never_generates(model_request):
    client = FakeClient(tokens=None)

    gateway = ModelRequestGateway(
        client,
        context_window=1000,
        safety_reserve_tokens=100,
    )

    with pytest.raises(TokenCountUnavailable):
        gateway.create(model_request)

    assert client.responses.generation_calls == []


def test_tools_and_history_reach_counter(model_request):
    model_request["previous_response_id"] = "resp-previous"
    model_request["tools"] = [
        {
            "type": "function",
            "name": "lookup",
            "description": "Look up a value",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    ]

    client = FakeClient(tokens=450)

    gateway = ModelRequestGateway(
        client,
        context_window=1000,
        safety_reserve_tokens=100,
    )

    gateway.create(model_request)

    counted = client.responses.input_tokens.calls[0]

    assert counted["previous_response_id"] == "resp-previous"
    assert counted["tools"] == model_request["tools"]


def test_exact_boundary_generates(model_request):
    client = FakeClient(tokens=700)

    gateway = ModelRequestGateway(
        client,
        context_window=1000,
        safety_reserve_tokens=100,
    )

    _, decision = gateway.create(model_request)

    assert decision.remaining_tokens == 0
    assert len(client.responses.generation_calls) == 1
