
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.deadline_gateway import (
    DeadlineAwareGateway,
    DeadlineBudget,
)
from agent.durable_generation_gateway import (
    DurableGenerationGateway,
)
from agent.submission_admission import SubmissionAdmission


def build_admitted_gateway(
    client: Any,
    *,
    operation_id: str,
    token: int,
    repo_root: Path,
    checkpoint_root: Path,
    fencing_root: Path,
    identity_root: Path,
    journal_root: Path,
    context_window: int,
    budget: DeadlineBudget,
    safety_reserve_tokens: int = 1024,
) -> DurableGenerationGateway:
    admission = SubmissionAdmission(
        repo_root=repo_root,
        checkpoint_root=checkpoint_root,
        fencing_root=fencing_root,
        identity_root=identity_root,
        journal_root=journal_root,
        operation_id=operation_id,
    )

    def on_stage(stage: str) -> None:
        if stage == "generation_submission_started":
            admission.admit(token)

    gateway = DeadlineAwareGateway(
        client,
        context_window=context_window,
        budget=budget,
        safety_reserve_tokens=safety_reserve_tokens,
        on_stage=on_stage,
    )

    return DurableGenerationGateway(
        gateway,
        admission.journal,
    )
