
import pytest

from agent.token_budget import (
    TokenBudget,
    TokenBudgetExceeded,
    TokenCountUnavailable,
    TokenPolicy,
)


@pytest.fixture
def policy():
    return TokenPolicy(
        context_window=1000,
        max_output_tokens=200,
        safety_reserve_tokens=100,
    )


def test_available_input_capacity(policy):
    assert policy.max_input_tokens == 700


def test_request_within_budget(policy):
    budget = TokenBudget(
        policy,
        count_tokens=lambda request: 500,
    )

    decision = budget.require_fit({"input": "hello"})

    assert decision.allowed
    assert decision.remaining_tokens == 200
    assert decision.reason == "within_budget"


def test_exact_boundary_is_allowed(policy):
    budget = TokenBudget(
        policy,
        count_tokens=lambda request: 700,
    )

    decision = budget.require_fit({})

    assert decision.allowed
    assert decision.remaining_tokens == 0


def test_overflow_is_rejected(policy):
    budget = TokenBudget(
        policy,
        count_tokens=lambda request: 701,
    )

    with pytest.raises(
        TokenBudgetExceeded,
        match="701 tokens",
    ):
        budget.require_fit({})


def test_missing_count_fails_closed(policy):
    budget = TokenBudget(
        policy,
        count_tokens=lambda request: None,
    )

    with pytest.raises(TokenCountUnavailable):
        budget.require_fit({})


def test_counter_exception_fails_closed(policy):
    def broken_counter(request):
        raise ConnectionError("counter unavailable")

    budget = TokenBudget(policy, broken_counter)

    with pytest.raises(TokenCountUnavailable):
        budget.require_fit({})


def test_invalid_policy_rejected():
    with pytest.raises(
        ValueError,
        match="No input capacity",
    ):
        TokenPolicy(
            context_window=1000,
            max_output_tokens=900,
            safety_reserve_tokens=100,
        )


def test_boolean_count_is_rejected(policy):
    budget = TokenBudget(
        policy,
        count_tokens=lambda request: True,
    )

    with pytest.raises(TokenCountUnavailable):
        budget.require_fit({})
