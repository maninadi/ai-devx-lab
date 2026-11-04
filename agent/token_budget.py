
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class TokenBudgetExceeded(RuntimeError):
    """Request exceeds the configured context budget."""


class TokenCountUnavailable(RuntimeError):
    """No trustworthy token count was provided."""


@dataclass(frozen=True)
class TokenPolicy:
    context_window: int
    max_output_tokens: int
    safety_reserve_tokens: int = 1024

    def __post_init__(self):
        for name in (
            "context_window",
            "max_output_tokens",
            "safety_reserve_tokens",
        ):
            value = getattr(self, name)

            if type(value) is not int or value < 0:
                raise ValueError(
                    f"{name} must be a nonnegative integer"
                )

        if self.context_window == 0:
            raise ValueError(
                "context_window must be positive"
            )

        if self.max_output_tokens == 0:
            raise ValueError(
                "max_output_tokens must be positive"
            )

        if (
            self.max_output_tokens
            + self.safety_reserve_tokens
            >= self.context_window
        ):
            raise ValueError(
                "No input capacity remains"
            )

    @property
    def max_input_tokens(self) -> int:
        return (
            self.context_window
            - self.max_output_tokens
            - self.safety_reserve_tokens
        )


@dataclass(frozen=True)
class TokenDecision:
    allowed: bool
    input_tokens: int
    input_limit: int
    remaining_tokens: int
    utilization: float
    reason: str


class TokenBudget:
    def __init__(
        self,
        policy: TokenPolicy,
        count_tokens: Callable[[object], int],
    ):
        self.policy = policy
        self.count_tokens = count_tokens

    def inspect(self, request: object) -> TokenDecision:
        try:
            count = self.count_tokens(request)
        except Exception as exc:
            raise TokenCountUnavailable(
                "Token counting failed"
            ) from exc

        if type(count) is not int or count < 0:
            raise TokenCountUnavailable(
                "Invalid token count"
            )

        limit = self.policy.max_input_tokens
        remaining = limit - count
        allowed = remaining >= 0

        return TokenDecision(
            allowed=allowed,
            input_tokens=count,
            input_limit=limit,
            remaining_tokens=max(0, remaining),
            utilization=count / limit,
            reason=(
                "within_budget"
                if allowed
                else "input_budget_exceeded"
            ),
        )

    def require_fit(self, request: object) -> TokenDecision:
        decision = self.inspect(request)

        if not decision.allowed:
            raise TokenBudgetExceeded(
                "Input requires "
                f"{decision.input_tokens} tokens; "
                f"limit is {decision.input_limit}"
            )

        return decision
