from agent.tool_recovery import (
    run_tool_safely,
)


def run(dispatch, raw='{"path":"pricing.py"}'):

    return run_tool_safely(
        name="read_file_range",
        raw_arguments=raw,
        dispatch=dispatch,
        sleep_fn=lambda _: None,
    )


def test_success():

    outcome = run(
        lambda name, args: {
            "ok": True,
            "content": "hello",
        }
    )

    assert outcome.decision == "continue"
    assert outcome.attempts == 1


def test_transient_retry():

    calls = []

    def dispatch(name, args):

        calls.append(1)

        if len(calls) == 1:
            raise TimeoutError()

        return {"ok": True}

    outcome = run(dispatch)

    assert outcome.decision == "continue"
    assert outcome.attempts == 2

    assert any(
        event["event"] == "tool_retry_scheduled"
        for event in outcome.events
    )


def test_retry_exhaustion():

    def dispatch(name, args):
        raise ConnectionError()

    outcome = run(dispatch)

    assert outcome.decision == "replan"
    assert outcome.attempts == 2

    assert (
        outcome.result["error"]["code"]
        == "transient_exhausted"
    )


def test_permission_failure():

    def dispatch(name, args):
        raise PermissionError()

    outcome = run(dispatch)

    assert outcome.decision == "stop"
    assert outcome.attempts == 1


def test_invalid_json():

    outcome = run(
        lambda name, args: {"ok": True},
        raw="{bad",
    )

    assert outcome.decision == "replan"
    assert outcome.attempts == 0


def test_invalid_result():

    outcome = run(
        lambda name, args: "unexpected"
    )

    assert outcome.decision == "stop"

    assert (
        outcome.result["error"]["code"]
        == "invalid_tool_result"
    )


def test_tool_reported_failure():

    outcome = run(
        lambda name, args: {
            "ok": False,
            "error": "File not found",
        }
    )

    assert outcome.decision == "replan"
    assert outcome.attempts == 1


def test_internal_error_is_not_exposed():

    def dispatch(name, args):
        raise RuntimeError(
            "Internal secret information"
        )

    outcome = run(dispatch)

    assert outcome.decision == "stop"

    assert (
        "Internal secret information"
        not in str(outcome.result)
    )
