
from types import SimpleNamespace as NS

import pytest

from agent.output_contract import (
    AnswerState,
    RepositoryAnswer,
)
from agent.output_failure_policy import (
    OutputAction,
    decide_output_policy,
)
from agent.policy_structured_gateway import (
    PolicyStructuredGateway,
)
from agent.structured_response_gateway import (
    OutputOutcome,
    StructuredResponseGateway,
)


VALID = (
    '{"state":"answered","answer":"Found",'
    '"citations":[{"path":"agent/loop.py",'
    '"start_line":1,"end_line":3}]}'
)

ABSTAINED = (
    '{"state":"abstained","answer":"",'
    '"citations":[]}'
)


def provider_response(
    text=None,
    *,
    status="completed",
    refusal=False,
):
    if refusal:
        content = [
            NS(type="refusal", refusal="Declined")
        ]
    elif text is not None:
        content = [
            NS(type="output_text", text=text)
        ]
    else:
        content = []

    return NS(
        id="resp_day44",
        status=status,
        output=[
            NS(type="message", content=content)
        ],
    )


def run_with_fake(response):
    calls = []

    class FakeGateway:
        def create(self, request):
            calls.append(request)
            return response, "preflight-ok"

    structured = StructuredResponseGateway(
        FakeGateway()
    )

    policy_gateway = PolicyStructuredGateway(
        structured
    )

    result = policy_gateway.create({
        "model": "fake",
        "input": "Find a function",
    })

    return result, calls


def test_valid_answer_routes_to_evidence_gate():
    result, calls = run_with_fake(
        provider_response(VALID)
    )

    assert result.policy.action == (
        OutputAction.DELIVER_TO_EVIDENCE_GATE
    )
    assert result.answer.state == AnswerState.ANSWERED
    assert result.preflight_decision == "preflight-ok"
    assert result.policy.may_resubmit is False
    assert len(calls) == 1


def test_abstention_is_not_failure():
    result, calls = run_with_fake(
        provider_response(ABSTAINED)
    )

    assert result.policy.action == (
        OutputAction.RETURN_ABSTENTION
    )
    assert result.answer.state == AnswerState.ABSTAINED
    assert len(calls) == 1


def test_refusal_stops():
    result, calls = run_with_fake(
        provider_response(refusal=True)
    )

    assert result.policy.action == (
        OutputAction.STOP_REFUSAL
    )
    assert result.answer is None
    assert result.policy.may_resubmit is False
    assert len(calls) == 1


def test_incomplete_requires_inspection():
    result, calls = run_with_fake(
        provider_response(
            VALID,
            status="incomplete",
        )
    )

    assert result.policy.action == (
        OutputAction.INSPECT_RECORDED_RESPONSE
    )
    assert result.answer is None
    assert len(calls) == 1


@pytest.mark.parametrize(
    "text",
    [
        "not-json",
        '{"state":"answered"}',
        '{"state":"answered","answer":"x",'
        '"citations":[]}',
    ],
)
def test_invalid_output_quarantined(text):
    result, calls = run_with_fake(
        provider_response(text)
    )

    assert result.policy.action == (
        OutputAction.QUARANTINE
    )
    assert result.answer is None
    assert result.policy.may_resubmit is False
    assert len(calls) == 1


def test_transport_timeout_is_not_swallowed():
    calls = []

    class TimeoutGateway:
        def create(self, request):
            calls.append(request)
            raise TimeoutError("Ambiguous submission")

    policy_gateway = PolicyStructuredGateway(
        StructuredResponseGateway(
            TimeoutGateway()
        )
    )

    with pytest.raises(TimeoutError):
        policy_gateway.create({
            "model": "fake",
            "input": "Hello",
        })

    assert len(calls) == 1


def test_invalid_policy_state_fails_closed():
    decision = decide_output_policy(
        outcome=OutputOutcome.VALID,
        answer=None,
    )

    assert decision.action == OutputAction.QUARANTINE
    assert decision.may_resubmit is False


def test_failure_cannot_carry_valid_answer():
    answer = RepositoryAnswer.model_validate_json(
        VALID,
        strict=True,
    )

    decision = decide_output_policy(
        outcome=OutputOutcome.INVALID,
        answer=answer,
    )

    assert decision.action == OutputAction.QUARANTINE
