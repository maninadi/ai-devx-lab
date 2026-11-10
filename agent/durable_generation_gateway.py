
from __future__ import annotations

from typing import Any

from agent.generation_attempt_journal import (
    GenerationAttemptJournal,
)


class DurableGenerationGateway:
    """
    Wraps a deadline-aware gateway.

    Requires an on_stage callback wired to
    record_submission_intent() before generation.
    """

    def __init__(
        self,
        gateway: Any,
        journal: GenerationAttemptJournal,
    ):
        self.gateway = gateway
        self.journal = journal

    def create(self, request: dict):
        response, decision = self.gateway.create(request)

        response_id = getattr(response, "id", None)
        status = getattr(response, "status", None)

        if (
            not isinstance(response_id, str)
            or not response_id
            or not isinstance(status, str)
            or not status
        ):
            # Preserve submission intent as ambiguous.
            raise RuntimeError(
                "Response metadata unavailable"
            )

        self.journal.record_response(
            response_id,
            status,
        )

        return response, decision
