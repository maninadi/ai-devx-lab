
from types import SimpleNamespace as NS

import pytest

from agent.output_contract import (
    AnswerState,
    RepositoryAnswer,
)
from agent.structured_output_request import (
    with_repository_answer_format,
)
from agent.structured_response_gateway import (
    OutputContractError,
    OutputOutcome,
    StructuredResponseGateway,
    validate_response,
)


def response(
    text=None,
    *,
    status="completed",
    refusal=False,
):
    if refusal:
        content = [NS(
            type="refusal",
            refusal="Cannot comply",
        )]
    elif text is not None:
        content = [NS(
            type="output_text",
            text=text,
        )]
    else:
        content = []

    return NS(
        id="resp_day43",
        status=status,
        output=[NS(
            type="message",
            content=content,
        )],
    )


VALID = (
    '{"state":"answered",'
    '"answer":"Found in agent/loop.py",'
    '"citations":[{"path":"agent/loop.py",'
    '"start_line":10,"end_line":15}]}'
)


def test_valid_answer():
    result = validate_response(
        response(VALID)
    )
    assert isinstance(result, RepositoryAnswer)
    assert result.state == AnswerState.ANSWERED
    assert result.citations[0].start_line == 10


def test_valid_abstention():
    result = validate_response(response(
        '{"state":"abstained",'
        '"answer":"","citations":[]}'
    ))
    assert result.state == AnswerState.ABSTAINED


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        '{"state":"answered"}',
        '{"state":"answered","answer":"x",'
        '"citations":[]}',
        '{"state":"answered","answer":"x",'
        '"citations":[{"path":"x",'
        '"start_line":8,"end_line":2}]}',
        '{"state":"answered","answer":"x",'
        '"citations":[{"path":"x",'
        '"start_line":"1","end_line":2}]}',
        '{"state":"abstained","answer":"x",'
        '"citations":[]}',
        '{"state":"abstained","answer":"",'
        '"citations":[],"unexpected":true}',
    ],
)
def test_invalid_payloads(payload):
    with pytest.raises(
        OutputContractError
    ) as exc:
        validate_response(response(payload))

    assert exc.value.outcome == (
        OutputOutcome.INVALID
    )


def test_refusal():
    with pytest.raises(
        OutputContractError
    ) as exc:
        validate_response(
            response(refusal=True)
        )

    assert exc.value.outcome == (
        OutputOutcome.REFUSED
    )


def test_incomplete_response():
    with pytest.raises(
        OutputContractError
    ) as exc:
        validate_response(response(
            VALID,
            status="incomplete",
        ))

    assert exc.value.outcome == (
        OutputOutcome.INCOMPLETE
    )


def test_missing_output():
    with pytest.raises(
        OutputContractError
    ) as exc:
        validate_response(response())

    assert exc.value.outcome == (
        OutputOutcome.INVALID
    )


def test_format_does_not_mutate_input():
    request = {
        "model": "fake",
        "input": "Find a function",
    }
    formatted = with_repository_answer_format(
        request
    )

    assert "text" not in request
    assert formatted["text"]["format"][
        "strict"
    ] is True


def test_gateway_returns_validated_answer():
    calls = []

    class FakeGateway:
        def create(self, request):
            calls.append(request)
            return response(VALID), "preflight-ok"

    gateway = StructuredResponseGateway(
        FakeGateway()
    )

    answer, decision = gateway.create({
        "model": "fake",
        "input": "Find a function",
    })

    assert answer.state == AnswerState.ANSWERED
    assert decision == "preflight-ok"
    assert len(calls) == 1
    assert calls[0]["text"]["format"][
        "type"
    ] == "json_schema"
