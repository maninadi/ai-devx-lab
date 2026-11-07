
from __future__ import annotations


import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)


from agent.retry_timing import BackoffPolicy


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
        backoff: BackoffPolicy | None = None,
        deadline_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = lambda: 0.5,
        reconcile: Callable[[dict], Any | None] | None = None,
    ):
        if deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")

        self.gateway = gateway
        self.policy = policy or RetryPolicy()
        self.can_retry = can_retry or (lambda exc: False)
        self.backoff = backoff or BackoffPolicy()
        self.deadline_seconds = deadline_seconds
        self.clock = clock
        self.sleep = sleep
        self.random_value = random_value
        self.reconcile = reconcile

    def execute(self, request: dict) -> LifecycleResult:
        deadline = self.clock() + self.deadline_seconds

        for attempt in range(
            1,
            self.policy.max_attempts + 1,
        ):
            if self.clock() >= deadline:
                return LifecycleResult(
                    outcome=RequestOutcome.REJECTED,
                    attempts=attempt - 1,
                    response=None,
                    reason="deadline_exhausted_before_attempt",
                )

            try:
                response, _decision = self.gateway.create(request)

            except (APITimeoutError, APIConnectionError):
                # Never replay an ambiguous generation.
                if self.reconcile is not None:
                    recovered = self.reconcile(request)
                    if recovered is not None:
                        status = getattr(recovered, "status", None)
                        if status == "completed":
                            return LifecycleResult(
                                outcome=RequestOutcome.COMPLETED,
                                attempts=attempt,
                                response=recovered,
                                reason="reconciled_completed",
                            )

                return LifecycleResult(
                    outcome=RequestOutcome.AMBIGUOUS,
                    attempts=attempt,
                    response=None,
                    reason="transport_outcome_unknown",
                )

            except APIStatusError as exc:
                if (
                    attempt >= self.policy.max_attempts
                    or not self.can_retry(exc)
                ):
                    return LifecycleResult(
                        outcome=RequestOutcome.REJECTED,
                        attempts=attempt,
                        response=None,
                        reason=f"http_{exc.status_code}",
                    )

                delay = self.backoff.delay(
                    attempt,
                    random_value=self.random_value,
                )

                remaining = deadline - self.clock()

                if remaining <= delay:
                    return LifecycleResult(
                        outcome=RequestOutcome.REJECTED,
                        attempts=attempt,
                        response=None,
                        reason="retry_deadline_exhausted",
                    )

                self.sleep(delay)
                continue

            status = getattr(response, "status", None)

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

        raise AssertionError("Unreachable retry state")
