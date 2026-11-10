
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
from agent.generation_attempt_journal import (
    GenerationAttemptJournal,
)


def build_durable_gateway(
    client: Any,
    *,
    operation_id: str,
    journal_root: Path,
    context_window: int,
    budget: DeadlineBudget,
    safety_reserve_tokens: int = 1024,
) -> DurableGenerationGateway:
    journal = GenerationAttemptJournal(
        journal_root,
        operation_id,
    )

    # Do not start an already-recorded operation.
    if journal.load() is not None:
        raise RuntimeError(
            "Existing operation requires reconciliation"
        )

    def on_stage(stage: str) -> None:
        if stage == "generation_submission_started":
            journal.record_submission_intent()

    gateway = DeadlineAwareGateway(
        client,
        context_window=context_window,
        budget=budget,
        safety_reserve_tokens=safety_reserve_tokens,
        on_stage=on_stage,
    )

    return DurableGenerationGateway(
        gateway,
        journal,
    )
