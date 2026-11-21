
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent.generation_attempt_journal import (
    AttemptRecord,
    AttemptState,
)
from agent.output_diagnostics import (
    OutputDiagnostic,
    ReceiptState,
)
from agent.provider_correlation import (
    ProviderCorrelation,
)


class TraceStatus(str, Enum):
    CONSISTENT = "consistent"
    INCOMPLETE = "incomplete"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TraceAudit:
    status: TraceStatus
    reason: str
    operation_id: str
    client_request_id: str | None = None
    response_id: str | None = None


def audit_output_trace(
    *,
    operation_id: str,
    diagnostic: OutputDiagnostic | None,
    attempt: AttemptRecord | None,
    correlation: ProviderCorrelation | None,
) -> TraceAudit:
    def result(
        status: TraceStatus,
        reason: str,
        response_id: str | None = None,
    ) -> TraceAudit:
        return TraceAudit(
            status=status,
            reason=reason,
            operation_id=operation_id,
            client_request_id=(
                correlation.client_request_id
                if correlation is not None
                and correlation.operation_id == operation_id
                else None
            ),
            response_id=response_id,
        )

    for record in (diagnostic, attempt, correlation):
        if (
            record is not None
            and record.operation_id != operation_id
        ):
            return result(
                TraceStatus.CONFLICT,
                "Operation identity mismatch",
            )

    if attempt is None or correlation is None:
        return result(
            TraceStatus.UNAVAILABLE,
            "Authoritative record missing",
        )

    if diagnostic is None:
        return result(
            TraceStatus.INCOMPLETE,
            "Diagnostic record missing",
        )

    if attempt.state == AttemptState.SUBMISSION_INTENT:
        if correlation.response_id is not None:
            return result(
                TraceStatus.CONFLICT,
                "Response correlation conflicts with intent",
            )

        if diagnostic.receipt_state != ReceiptState.INTENT_ONLY:
            return result(
                TraceStatus.CONFLICT,
                "Diagnostic intent state mismatch",
            )

        return result(
            TraceStatus.CONSISTENT,
            "Intent-only records agree; outcome remains unknown",
        )

    if attempt.state == AttemptState.RESPONSE_RECEIVED:
        if (
            not attempt.response_id
            or not attempt.response_status
        ):
            return result(
                TraceStatus.CONFLICT,
                "Invalid response receipt",
            )

        if (
            correlation.response_id is not None
            and correlation.response_id != attempt.response_id
        ):
            return result(
                TraceStatus.CONFLICT,
                "Provider response ID mismatch",
            )

        if (
            diagnostic.receipt_state != ReceiptState.RECEIVED
            or diagnostic.response_id != attempt.response_id
        ):
            return result(
                TraceStatus.CONFLICT,
                "Diagnostic response ID mismatch",
            )

        return result(
            TraceStatus.CONSISTENT,
            "Response identifiers agree",
            response_id=attempt.response_id,
        )

    return result(
        TraceStatus.CONFLICT,
        "Unknown attempt state",
    )
