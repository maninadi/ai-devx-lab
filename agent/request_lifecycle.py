
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)


class RequestOutcome(str, Enum):
    COMPLETED = "completed"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2

    def __post_init__(self):
        if (
            type(self.max_attempts) is not int
            or self.max_attempts < 1
        ):
            raise ValueError(
                "max_attempts must be positive"
            )


@dataclass(frozen=True)
class LifecycleResult:
    outcome: RequestOutcome
    attempts: int
    response: Any | None
    reason: str


class RequestLifecycle:
    def __init__(
        self,
        gateway: Any,
        *,
        policy: RetryPolicy | None = None,
        can_retry: Callable[[Exception], bool] | None = None,
    ):
        self.gateway = gateway
        self.policy = policy or RetryPolicy()
        self.can_retry = can_retry or (
            lambda exc: False
        )

    def execute(self, request: dict) -> LifecycleResult:
        for attempt in range(
            1,
            self.policy.max_attempts + 1,
        ):
            try:
                response, _decision = (
                    self.gateway.create(request)
                )

            except (
                APITimeoutError,
                APIConnectionError,
            ):
                return LifecycleResult(
                    outcome=RequestOutcome.AMBIGUOUS,
                    attempts=attempt,
                    response=None,
                    reason="transport_outcome_unknown",
                )

            except APIStatusError as exc:
                # Retry only when the caller explicitly
                # certifies the failure as safe to replay.
                if (
                    attempt < self.policy.max_attempts
                    and self.can_retry(exc)
                ):
                    continue

                return LifecycleResult(
                    outcome=RequestOutcome.REJECTED,
                    attempts=attempt,
                    response=None,
                    reason=f"http_{exc.status_code}",
                )

            # Preflight failures and unexpected errors
            # deliberately propagate to the caller.

            status = getattr(
                response,
                "status",
                None,
            )

            if status == "completed":
                return LifecycleResult(
                    outcome=RequestOutcome.COMPLETED,
                    attempts=attempt,
                    response=response,
                    reason="completed",
                )

            return LifecycleResult(
                outcome=RequestOutcome.INCOMPLETE,
                attempts=attempt,
                response=response,
                reason=f"model_status_{status}",
            )

        raise AssertionError(
            "Unreachable retry state"
        )
