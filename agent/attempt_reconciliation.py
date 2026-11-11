
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from agent.attempt_identity import (
    AttemptIdentityStore,
    IdentityConflict,
)
from agent.generation_attempt_journal import (
    AttemptConflict,
    AttemptState,
    GenerationAttemptJournal,
)
from agent.recovery_generations import GenerationStore
from agent.checkpoint import RecoveryBlocked


class RecoveryDecision(str, Enum):
    BLOCK = "block"
    INSPECT_CHECKPOINT = "inspect_checkpoint"
    RECONCILE_RESPONSE = "reconcile_response"


@dataclass(frozen=True)
class ReconciliationResult:
    decision: RecoveryDecision
    reason: str
    response_id: str | None = None


def assess_attempt_recovery(
    *,
    repo_root: Path,
    checkpoint_root: Path,
    identity_root: Path,
    journal_root: Path,
    operation_id: str,
) -> ReconciliationResult:
    """
    Read-only assessment. Never retries or executes tools.

    All exceptions indicating missing, invalid, or
    inconsistent recovery evidence fail closed.
    """
    try:
        generation = GenerationStore(
            checkpoint_root
        ).current(repo_root)

        identity = AttemptIdentityStore(
            identity_root, operation_id
        ).load()

        if identity.run_id != generation.run_id:
            return ReconciliationResult(
                RecoveryDecision.BLOCK,
                "run_identity_mismatch",
            )

        if identity.generation_id != generation.generation_id:
            return ReconciliationResult(
                RecoveryDecision.BLOCK,
                "generation_identity_mismatch",
            )

        record = GenerationAttemptJournal(
            journal_root, operation_id
        ).load()

        if record is None:
            return ReconciliationResult(
                RecoveryDecision.INSPECT_CHECKPOINT,
                "no_submission_record",
            )

        if record.state == AttemptState.SUBMISSION_INTENT:
            return ReconciliationResult(
                RecoveryDecision.BLOCK,
                "generation_outcome_ambiguous",
            )

        if record.state == AttemptState.RESPONSE_RECEIVED:
            return ReconciliationResult(
                RecoveryDecision.RECONCILE_RESPONSE,
                "response_receipt_available",
                response_id=record.response_id,
            )

        return ReconciliationResult(
            RecoveryDecision.BLOCK,
            "unknown_attempt_state",
        )

    except (
        RecoveryBlocked,
        IdentityConflict,
        AttemptConflict,
        ValueError,
        OSError,
    ):
        return ReconciliationResult(
            RecoveryDecision.BLOCK,
            "recovery_evidence_invalid",
        )
