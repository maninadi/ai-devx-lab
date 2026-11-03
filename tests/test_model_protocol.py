
from types import SimpleNamespace as NS

import pytest

from agent.model_protocol import (
    ModelProtocolError,
    inspect_response,
)


def fake_response(
    *,
    status="completed",
    output=None,
    usage=None,
):
    return NS(
        id="resp_29",
        model="gpt-4.1-mini",
        status=status,
        output=[] if output is None else output,
        usage=usage,
    )


def message(text):
    return NS(
        type="message",
        content=[NS(type="output_text", text=text)],
    )


def tool_call():
    return NS(
        type="function_call",
        name="read_file",
        call_id="call_1",
        arguments='{"path":"README.md"}',
    )


def token_usage():
    return NS(
        input_tokens=120,
        output_tokens=30,
        total_tokens=150,
        input_tokens_details=NS(cached_tokens=20),
        output_tokens_details=NS(reasoning_tokens=0),
    )


def test_text_response():
    reply = inspect_response(
        fake_response(
            output=[message("READY")],
            usage=token_usage(),
        )
    )

    assert reply.text == "READY"
    assert reply.has_final_text
    assert not reply.requires_tools
    assert reply.usage.input_tokens == 120
    assert reply.usage.cached_input_tokens == 20


def test_tool_call_is_not_final_answer():
    reply = inspect_response(
        fake_response(output=[tool_call()])
    )

    assert reply.requires_tools
    assert not reply.has_final_text
    assert reply.tool_call_names == ("read_file",)


def test_mixed_output_is_not_final():
    reply = inspect_response(
        fake_response(
            output=[message("Checking"), tool_call()]
        )
    )

    assert reply.text == "Checking"
    assert not reply.has_final_text


def test_reasoning_item_is_not_user_text():
    reply = inspect_response(
        fake_response(
            output=[
                NS(type="reasoning"),
                message("Result"),
            ]
        )
    )

    assert reply.text == "Result"
    assert reply.output_types == (
        "reasoning",
        "message",
    )


def test_incomplete_response_is_rejected():
    with pytest.raises(
        ModelProtocolError,
        match="not completed",
    ):
        inspect_response(
            fake_response(status="incomplete")
        )


def test_missing_usage_is_not_zero():
    reply = inspect_response(
        fake_response(output=[message("READY")])
    )

    assert reply.usage is None


def test_invalid_usage_is_rejected():
    bad_usage = token_usage()
    bad_usage.total_tokens = 999

    with pytest.raises(
        ModelProtocolError,
        match="Invalid token usage",
    ):
        inspect_response(
            fake_response(
                output=[message("READY")],
                usage=bad_usage,
            )
        )


def test_refusal_is_not_final_text():
    refusal = NS(
        type="message",
        content=[NS(type="refusal")],
    )

    with pytest.raises(
        ModelProtocolError,
        match="refusal",
    ):
        inspect_response(
            fake_response(output=[refusal])
        )
