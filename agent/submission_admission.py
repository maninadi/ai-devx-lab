
from __future__ import annotations

from pathlib import Path

from agent.attempt_identity import (
    AttemptIdentityStore,
    IdentityConflict,
)
from agent.generation_attempt_journal import (
    AttemptConflict,
    GenerationAttemptJournal,
)
from agent.generation_fencing import (
    FencingBlocked,
    GenerationFencing,
)
from agent.recovery_generations import GenerationStore


class SubmissionAdmissionBlocked(RuntimeError):
    """Provider submission must not begin."""


class SubmissionAdmission:
    def __init__(
        self,
        *,
        repo_root: Path,
        checkpoint_root: Path,
        fencing_root: Path,
        identity_root: Path,
        journal_root: Path,
        operation_id: str,
    ):
        self.repo_root = repo_root
        self.generations = GenerationStore(checkpoint_root)
        self.fencing = GenerationFencing(fencing_root)
        self.identity = AttemptIdentityStore(
            identity_root, operation_id
        )
        self.journal = GenerationAttemptJournal(
            journal_root, operation_id
        )

    def admit(self, token: int) -> None:
        """Authorize one local submission attempt.

        The lock covers ownership validation, generation
        verification, and durable intent publication.
        """

        def action() -> None:
            generation = self.generations.current(
                self.repo_root
            )
            identity = self.identity.load()

            if identity.run_id != generation.run_id:
                raise SubmissionAdmissionBlocked(
                    "Run identity mismatch"
                )

            if (
                identity.generation_id
                != generation.generation_id
            ):
                raise SubmissionAdmissionBlocked(
                    "Generation changed before submission"
                )

            if self.journal.load() is not None:
                raise SubmissionAdmissionBlocked(
                    "Existing attempt requires reconciliation"
                )

            # Must finish durably before the provider call.
            self.journal.record_submission_intent()

        try:
            self.fencing.guarded(token, action)
        except (
            FencingBlocked,
            IdentityConflict,
            AttemptConflict,
        ) as exc:
            raise SubmissionAdmissionBlocked(
                "Submission admission failed closed"
            ) from exc
