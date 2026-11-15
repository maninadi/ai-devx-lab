
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent.generation_attempt_journal import (
    AttemptRecord,
    AttemptState,
)
from agent.provider_correlation import (
    ProviderCorrelation,
)


class RecoveryDisposition(str, Enum):
    BLOCK = "block"
    RECONCILE = "reconcile"
    INSPECT_RESPONSE = "inspect_response"


@dataclass(frozen=True)
class RecoveryAudit:
    disposition: RecoveryDisposition
    reason: str
    response_id: str | None = None


def audit_generation(
    *,
    operation_id: str,
    attempt: AttemptRecord | None,
    correlation: ProviderCorrelation | None,
) -> RecoveryAudit:
    # This function is read-only. It never submits
    # another provider request.

    if correlation is None:
        return RecoveryAudit(
            RecoveryDisposition.BLOCK,
            "Correlation record missing",
        )

    if correlation.operation_id != operation_id:
        return RecoveryAudit(
            RecoveryDisposition.BLOCK,
            "Correlation identity mismatch",
        )

    if attempt is None:
        return RecoveryAudit(
            RecoveryDisposition.BLOCK,
            "Submission intent not established",
        )

    if attempt.operation_id != operation_id:
        return RecoveryAudit(
            RecoveryDisposition.BLOCK,
            "Attempt identity mismatch",
        )

    if attempt.state == AttemptState.SUBMISSION_INTENT:
        if correlation.response_id is not None:
            return RecoveryAudit(
                RecoveryDisposition.BLOCK,
                "Correlation receipt conflicts with intent",
            )

        return RecoveryAudit(
            RecoveryDisposition.RECONCILE,
            "Provider submission outcome unknown",
        )

    if attempt.state == AttemptState.RESPONSE_RECEIVED:
        if not attempt.response_id:
            return RecoveryAudit(
                RecoveryDisposition.BLOCK,
                "Invalid response receipt",
            )

        if (
            correlation.response_id is not None
            and correlation.response_id != attempt.response_id
        ):
            return RecoveryAudit(
                RecoveryDisposition.BLOCK,
                "Conflicting response IDs",
            )

        return RecoveryAudit(
            RecoveryDisposition.INSPECT_RESPONSE,
            "Durable response receipt exists",
            response_id=attempt.response_id,
        )

    return RecoveryAudit(
        RecoveryDisposition.BLOCK,
        "Unrecognized attempt state",
    )
