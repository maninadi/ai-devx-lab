
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import time

from agent.provider_token_counter import (
    OpenAIProviderTokenCounter,
)
from agent.request_preflight import (
    preflight_model_request,
)


class DeadlineExhausted(RuntimeError):
    """No time remains to begin a provider stage."""


@dataclass(frozen=True)
class DeadlineBudget:
    expires_at: float
    clock: Callable[[], float]

    @classmethod
    def start(
        cls,
        seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> "DeadlineBudget":
        if seconds <= 0:
            raise ValueError("Deadline must be positive")

        return cls(
            expires_at=clock() + seconds,
            clock=clock,
        )

    def remaining(self) -> float:
        return max(0.0, self.expires_at - self.clock())

    def require_remaining(self) -> float:
        remaining = self.remaining()

        if remaining <= 0:
            raise DeadlineExhausted(
                "Operation deadline exhausted"
            )

        return remaining


class DeadlineAwareGateway:
    """
    Preflight and generation share one deadline.

    Each SDK call receives the remaining budget.
    Internal SDK retries are disabled.
    """

    def __init__(
        self,
        client: Any,
        *,
        context_window: int,
        budget: DeadlineBudget,
        safety_reserve_tokens: int = 1024,
        on_stage: Callable[[str], None] | None = None,
    ):
        self.client = client
        self.context_window = context_window
        self.budget = budget
        self.safety_reserve_tokens = (
            safety_reserve_tokens
        )
        self.on_stage = on_stage or (lambda stage: None)

    def _stage_client(self) -> Any:
        remaining = self.budget.require_remaining()

        return self.client.with_options(
            timeout=remaining,
            max_retries=0,
        )

    def create(self, request: dict):
        # Stage 1: token counting only.
        self.on_stage("preflight_started")

        counting_client = self._stage_client()

        decision = preflight_model_request(
            request,
            context_window=self.context_window,
            safety_reserve_tokens=(
                self.safety_reserve_tokens
            ),
            count_tokens=OpenAIProviderTokenCounter(
                counting_client
            ),
        )

        self.on_stage("preflight_completed")

        # Stage 2: generation submission.
        # Recalculate remaining time AFTER preflight.
        generation_client = self._stage_client()

        self.on_stage("generation_submission_started")

        response = generation_client.responses.create(
            **request
        )

        self.on_stage("generation_response_received")

        return response, decision
