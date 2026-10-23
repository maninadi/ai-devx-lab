from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentPhase(StrEnum):
    READY = "ready"
    MODEL_REQUEST = "model_request"
    TOOL_EXECUTION = "tool_execution"
    FINAL_REQUEST = "final_request"
    ANSWER_REVIEW = "answer_review"
    FINISHED = "finished"


ALLOWED_TRANSITIONS: dict[
    AgentPhase,
    frozenset[AgentPhase],
] = {

    AgentPhase.READY: frozenset({
        AgentPhase.MODEL_REQUEST,
        AgentPhase.FINAL_REQUEST,
        AgentPhase.FINISHED,
    }),

    AgentPhase.MODEL_REQUEST: frozenset({
        AgentPhase.TOOL_EXECUTION,
        AgentPhase.FINAL_REQUEST,
        AgentPhase.ANSWER_REVIEW,
        AgentPhase.FINISHED,
    }),

    AgentPhase.TOOL_EXECUTION: frozenset({
        AgentPhase.MODEL_REQUEST,
        AgentPhase.FINAL_REQUEST,
        AgentPhase.FINISHED,
    }),

    AgentPhase.FINAL_REQUEST: frozenset({
        AgentPhase.ANSWER_REVIEW,
        AgentPhase.FINISHED,
    }),

    AgentPhase.ANSWER_REVIEW: frozenset({
        AgentPhase.FINISHED,
    }),

    AgentPhase.FINISHED: frozenset(),
}


class InvalidTransition(RuntimeError):
    pass


@dataclass(frozen=True)
class StateTransition:
    sequence: int
    source: AgentPhase
    target: AgentPhase
    reason: str


class AgentStateMachine:
    """
    Tracks the legal execution lifecycle
    of one agent run.

    Provider-neutral and independent of
    model, tool, and tracing implementations.
    """

    def __init__(self):
        self.phase = AgentPhase.READY

        self.history: list[
            StateTransition
        ] = []

    @property
    def finished(self) -> bool:
        return (
            self.phase
            == AgentPhase.FINISHED
        )

    def can_transition(
        self,
        target: AgentPhase,
    ) -> bool:

        return (
            isinstance(target, AgentPhase)
            and target in ALLOWED_TRANSITIONS[
                self.phase
            ]
        )

    def move(
        self,
        target: AgentPhase,
        reason: str,
    ) -> StateTransition:

        if not isinstance(target, AgentPhase):
            raise TypeError(
                "Target must be an AgentPhase"
            )

        if (
            not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ValueError(
                "Transition reason is required"
            )

        if not self.can_transition(target):
            raise InvalidTransition(
                f"Illegal transition: "
                f"{self.phase.value} -> "
                f"{target.value}"
            )

        transition = StateTransition(
            sequence=len(self.history) + 1,
            source=self.phase,
            target=target,
            reason=reason,
        )

        self.phase = target

        self.history.append(
            transition
        )

        return transition
