
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from agent.generation_attempt_journal import (
    AttemptRecord,
    AttemptState,
)
from agent.output_diagnostics import OutputDiagnostic
from agent.output_trace_audit import (
    TraceStatus,
    audit_output_trace,
)
from agent.provider_correlation import (
    ProviderCorrelation,
)


class RetentionReason(str, Enum):
    ELIGIBLE = "eligible"
    TOO_RECENT = "too_recent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_FINALIZED = "not_finalized"


@dataclass(frozen=True)
class RetentionCandidate:
    operation_id: str
    created_at: datetime
    diagnostic: OutputDiagnostic | None
    attempt: AttemptRecord | None
    correlation: ProviderCorrelation | None
    finalized: bool = False


@dataclass(frozen=True)
class RetentionDecision:
    operation_id: str
    eligible: bool
    reason: RetentionReason


@dataclass(frozen=True)
class RetentionPlan:
    decisions: tuple[RetentionDecision, ...]

    @property
    def eligible_ids(self) -> tuple[str, ...]:
        return tuple(
            d.operation_id
            for d in self.decisions
            if d.eligible
        )

    @property
    def protected_ids(self) -> tuple[str, ...]:
        return tuple(
            d.operation_id
            for d in self.decisions
            if not d.eligible
        )


def plan_diagnostic_retention(
    candidates: list[RetentionCandidate],
    *,
    now: datetime,
    minimum_age: timedelta,
    max_candidates: int = 1000,
) -> RetentionPlan:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    if minimum_age < timedelta(0):
        raise ValueError("minimum_age must be nonnegative")

    if max_candidates < 1:
        raise ValueError("Invalid candidate limit")

    if len(candidates) > max_candidates:
        raise ValueError("Candidate limit exceeded")

    seen: set[str] = set()
    decisions: list[RetentionDecision] = []

    for item in sorted(
        candidates,
        key=lambda c: c.operation_id,
    ):
        if item.operation_id in seen:
            raise ValueError("Duplicate operation ID")
        seen.add(item.operation_id)

        if (
            item.created_at.tzinfo is None
            or item.created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be aware")

        audit = audit_output_trace(
            operation_id=item.operation_id,
            diagnostic=item.diagnostic,
            attempt=item.attempt,
            correlation=item.correlation,
        )

        if audit.status != TraceStatus.CONSISTENT:
            reason = RetentionReason.INCONSISTENT
        elif (
            item.attempt is None
            or item.attempt.state
            != AttemptState.RESPONSE_RECEIVED
        ):
            reason = RetentionReason.UNRESOLVED
        elif not item.finalized:
            reason = RetentionReason.NOT_FINALIZED
        elif now - item.created_at < minimum_age:
            reason = RetentionReason.TOO_RECENT
        else:
            reason = RetentionReason.ELIGIBLE

        decisions.append(
            RetentionDecision(
                operation_id=item.operation_id,
                eligible=(
                    reason == RetentionReason.ELIGIBLE
                ),
                reason=reason,
            )
        )

    return RetentionPlan(tuple(decisions))
