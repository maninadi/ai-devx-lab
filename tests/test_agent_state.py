import pytest

from agent.agent_state import (
    AgentPhase,
    AgentStateMachine,
    InvalidTransition,
)


@pytest.mark.parametrize(
    "path",
    [
        [
            AgentPhase.MODEL_REQUEST,
            AgentPhase.ANSWER_REVIEW,
            AgentPhase.FINISHED,
        ],
        [
            AgentPhase.MODEL_REQUEST,
            AgentPhase.TOOL_EXECUTION,
            AgentPhase.MODEL_REQUEST,
            AgentPhase.ANSWER_REVIEW,
            AgentPhase.FINISHED,
        ],
        [
            AgentPhase.MODEL_REQUEST,
            AgentPhase.TOOL_EXECUTION,
            AgentPhase.FINAL_REQUEST,
            AgentPhase.ANSWER_REVIEW,
            AgentPhase.FINISHED,
        ],
        [
            AgentPhase.FINAL_REQUEST,
            AgentPhase.ANSWER_REVIEW,
            AgentPhase.FINISHED,
        ],
        [
            AgentPhase.MODEL_REQUEST,
            AgentPhase.TOOL_EXECUTION,
            AgentPhase.FINISHED,
        ],
    ],
)
def test_legal_execution_paths(path):

    machine = AgentStateMachine()

    for phase in path:
        machine.move(
            phase,
            "test_transition",
        )

    assert machine.finished


def test_illegal_transition_rejected():

    machine = AgentStateMachine()

    with pytest.raises(
        InvalidTransition
    ):
        machine.move(
            AgentPhase.TOOL_EXECUTION,
            "tool_before_model",
        )


def test_cannot_execute_after_finished():

    machine = AgentStateMachine()

    machine.move(
        AgentPhase.FINISHED,
        "terminated",
    )

    with pytest.raises(
        InvalidTransition
    ):
        machine.move(
            AgentPhase.MODEL_REQUEST,
            "unexpected_restart",
        )


def test_finalization_disallows_tools():

    machine = AgentStateMachine()

    machine.move(
        AgentPhase.FINAL_REQUEST,
        "finalization_required",
    )

    with pytest.raises(
        InvalidTransition
    ):
        machine.move(
            AgentPhase.TOOL_EXECUTION,
            "unexpected_tool_request",
        )


def test_transition_history():

    machine = AgentStateMachine()

    first = machine.move(
        AgentPhase.MODEL_REQUEST,
        "run_started",
    )

    second = machine.move(
        AgentPhase.ANSWER_REVIEW,
        "answer_received",
    )

    assert first.sequence == 1
    assert second.sequence == 2

    assert (
        second.source
        == AgentPhase.MODEL_REQUEST
    )

    assert (
        second.target
        == AgentPhase.ANSWER_REVIEW
    )

    assert second.reason == "answer_received"


def test_invalid_transition_does_not_mutate_state():

    machine = AgentStateMachine()

    with pytest.raises(
        InvalidTransition
    ):
        machine.move(
            AgentPhase.ANSWER_REVIEW,
            "invalid",
        )

    assert machine.phase == AgentPhase.READY
    assert machine.history == []


def test_transition_reason_required():

    machine = AgentStateMachine()

    with pytest.raises(ValueError):
        machine.move(
            AgentPhase.MODEL_REQUEST,
            "",
        )
