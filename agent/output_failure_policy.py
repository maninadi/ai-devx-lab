
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent.output_contract import (
    AnswerState,
    RepositoryAnswer,
)
from agent.structured_response_gateway import (
    OutputOutcome,
)


class OutputAction(str, Enum):
    DELIVER_TO_EVIDENCE_GATE = "deliver_to_evidence_gate"
    RETURN_ABSTENTION = "return_abstention"
    STOP_REFUSAL = "stop_refusal"
    INSPECT_RECORDED_RESPONSE = "inspect_recorded_response"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class OutputPolicyDecision:
    action: OutputAction
    reason: str
    may_resubmit: bool = False


def decide_output_policy(
    *,
    outcome: OutputOutcome,
    answer: RepositoryAnswer | None = None,
) -> OutputPolicyDecision:
    if outcome == OutputOutcome.VALID:
        if answer is None:
            return OutputPolicyDecision(
                OutputAction.QUARANTINE,
                "Valid outcome missing validated answer",
            )

        if answer.state == AnswerState.ABSTAINED:
            return OutputPolicyDecision(
                OutputAction.RETURN_ABSTENTION,
                "Model explicitly abstained",
            )

        return OutputPolicyDecision(
            OutputAction.DELIVER_TO_EVIDENCE_GATE,
            "Validated answer requires provenance checks",
        )

    if answer is not None:
        return OutputPolicyDecision(
            OutputAction.QUARANTINE,
            "Failure outcome contains unexpected answer",
        )

    if outcome == OutputOutcome.REFUSED:
        return OutputPolicyDecision(
            OutputAction.STOP_REFUSAL,
            "Provider returned a refusal",
        )

    if outcome == OutputOutcome.INCOMPLETE:
        return OutputPolicyDecision(
            OutputAction.INSPECT_RECORDED_RESPONSE,
            "Response was not completed",
        )

    if outcome == OutputOutcome.INVALID:
        return OutputPolicyDecision(
            OutputAction.QUARANTINE,
            "Response violates output contract",
        )

    raise ValueError(
        f"Unhandled output outcome: {outcome!r}"
    )
