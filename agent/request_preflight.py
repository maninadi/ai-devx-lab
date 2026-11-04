
from __future__ import annotations

from typing import Callable

from agent.token_budget import (
    TokenBudget,
    TokenDecision,
    TokenPolicy,
)


def preflight_model_request(
    request: dict,
    *,
    context_window: int,
    safety_reserve_tokens: int,
    count_tokens: Callable[[object], int],
) -> TokenDecision:
    """Validate request capacity before model execution."""

    output_limit = request.get("max_output_tokens")

    if type(output_limit) is not int:
        raise ValueError(
            "Request must define max_output_tokens"
        )

    policy = TokenPolicy(
        context_window=context_window,
        max_output_tokens=output_limit,
        safety_reserve_tokens=safety_reserve_tokens,
    )

    return TokenBudget(
        policy,
        count_tokens,
    ).require_fit(request)
