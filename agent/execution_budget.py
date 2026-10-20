from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from time import monotonic
from typing import Callable


@dataclass(frozen=True)
class BudgetPolicy:
    max_tool_calls: int = 8
    max_repeats: int = 2
    max_seconds: float = 90.0
    finalization_reserve_seconds: float = 15.0

    def __post_init__(self):
        if self.max_tool_calls < 1:
            raise ValueError("Invalid tool budget")

        if self.max_repeats < 1:
            raise ValueError("Invalid repeat budget")

        if self.max_seconds <= 0:
            raise ValueError("Invalid time budget")

        if not (
            0 <= self.finalization_reserve_seconds
            < self.max_seconds
        ):
            raise ValueError(
                "Invalid finalization reserve"
            )


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str
    calls_used: int


class ExecutionBudget:
    """
    Per-run execution limits.

    Tracks model-requested tool operations,
    repeated requests, and elapsed time.

    Does not execute or cancel tools.
    """

    def __init__(
        self,
        policy: BudgetPolicy,
        clock: Callable[[], float] = monotonic,
    ):
        self.policy = policy
        self.clock = clock

        self.started_at = clock()
        self.deadline = (
            self.started_at + policy.max_seconds
        )

        self.calls_used = 0
        self.request_counts: dict[str, int] = {}

    def remaining_seconds(self) -> float:
        return max(
            0.0,
            self.deadline - self.clock(),
        )

    def expired(self) -> bool:
        return self.remaining_seconds() <= 0

    def should_finalize(self) -> bool:
        return (
            self.calls_used
            >= self.policy.max_tool_calls
            or self.remaining_seconds()
            <= self.policy.finalization_reserve_seconds
        )

    @staticmethod
    def fingerprint(
        name: str,
        raw_arguments: str,
    ) -> str:
        """
        Normalize JSON arguments so equivalent
        requests have the same fingerprint.
        """

        try:
            arguments = json.loads(raw_arguments)

            normalized = json.dumps(
                arguments,
                sort_keys=True,
                separators=(",", ":"),
            )

        except (ValueError, TypeError):
            normalized = str(raw_arguments)

        payload = f"{name}:{normalized}"

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def admit(
        self,
        name: str,
        raw_arguments: str,
    ) -> BudgetDecision:
        """
        Decide whether a requested tool operation
        may execute.

        Budget is charged when a request is admitted,
        regardless of its eventual success.
        """

        if self.expired():
            return BudgetDecision(
                False,
                "deadline_exceeded",
                self.calls_used,
            )

        if self.should_finalize():
            return BudgetDecision(
                False,
                "budget_exhausted",
                self.calls_used,
            )

        key = self.fingerprint(
            name,
            raw_arguments,
        )

        previous = self.request_counts.get(
            key,
            0,
        )

        if previous >= self.policy.max_repeats:
            return BudgetDecision(
                False,
                "repeated_request",
                self.calls_used,
            )

        self.calls_used += 1

        self.request_counts[key] = previous + 1

        return BudgetDecision(
            True,
            "allowed",
            self.calls_used,
        )
