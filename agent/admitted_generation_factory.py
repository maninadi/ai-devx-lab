
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from agent.deadline_gateway import (
    DeadlineAwareGateway,
    DeadlineBudget,
)
from agent.durable_generation_gateway import (
    DurableGenerationGateway,
)
from agent.submission_admission import SubmissionAdmission

from agent.provider_correlation import (
    ProviderCorrelation,
    ProviderCorrelationStore,
    CorrelationConflict,
)
from agent.correlated_generation_gateway import (
    CorrelatedGenerationGateway,
)
from agent.generation_fencing import GenerationFencing


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
    correlation_root: Path | None = None,
) -> Any:
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

    durable_gateway = DurableGenerationGateway(
        gateway,
        admission.journal,
    )

    if correlation_root is None:
        return durable_gateway

    correlation = ProviderCorrelationStore(
        correlation_root,
        operation_id,
    )

    fencing = GenerationFencing(
        fencing_root
    )

    def prepare_correlation() -> None:
        existing = correlation.load()

        if existing is not None:
            if existing.response_id is not None:
                raise CorrelationConflict(
                    "Operation already has a response"
                )

            if existing.operation_id != operation_id:
                raise CorrelationConflict(
                    "Correlation already exists for a different operation"
                )

            return
        correlation.prepare(
            ProviderCorrelation(
                operation_id=operation_id,
                client_request_id=str(uuid4()),
            )
        )

    fencing.guarded(token, prepare_correlation)

    return CorrelatedGenerationGateway(
        durable_gateway,
        correlation,
        fencing=fencing,
        token=token,
    )
