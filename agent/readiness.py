from dataclasses import dataclass

from agent.state import (
    AgentState,
    StepStatus,
)

from agent.verification import (
    CheckResult,
    CompletionStatus,
    evaluate_completion,
)


@dataclass(frozen=True)
class CompletionAssessment:
    verdict: CompletionStatus
    can_claim_complete: bool
    reasons: tuple[str, ...]


def assess_completion(
    state: AgentState,
    pricing: CheckResult,
    suite: CheckResult,
) -> CompletionAssessment:

    verdict = evaluate_completion(pricing, suite)
    reasons = []

    if not state.steps:
        reasons.append("No execution steps recorded")

    for step in state.steps:

        if step.status in (
            StepStatus.PENDING,
            StepStatus.IN_PROGRESS,
            StepStatus.BLOCKED,
        ):
            reasons.append(
                f"Unfinished step: {step.description}"
            )

        if (
            step.status == StepStatus.VERIFIED
            and not step.evidence
        ):
            reasons.append(
                f"Missing evidence: {step.description}"
            )

        if (
            step.status == StepStatus.ABANDONED
            and not step.evidence
        ):
            reasons.append(
                f"Missing abandonment reason: {step.description}"
            )

    if verdict != CompletionStatus.VERIFIED:
        reasons.append(
            f"Verification status: {verdict.value}"
        )

    return CompletionAssessment(
        verdict=verdict,
        can_claim_complete=not reasons,
        reasons=tuple(reasons),
    )