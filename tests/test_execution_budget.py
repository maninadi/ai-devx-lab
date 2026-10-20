from agent.execution_budget import (
    BudgetPolicy,
    ExecutionBudget,
)


def test_tool_budget_exhaustion():

    budget = ExecutionBudget(
        BudgetPolicy(
            max_tool_calls=2,
            max_repeats=3,
        )
    )

    assert budget.admit(
        "search_repository",
        '{"query":"pricing"}',
    ).allowed

    assert budget.admit(
        "search_repository",
        '{"query":"discount"}',
    ).allowed

    result = budget.admit(
        "search_repository",
        '{"query":"customers"}',
    )

    assert not result.allowed
    assert result.reason == "budget_exhausted"


def test_repeated_request_blocked():

    budget = ExecutionBudget(
        BudgetPolicy(
            max_tool_calls=8,
            max_repeats=2,
        )
    )

    args = '{"path":"pricing.py"}'

    assert budget.admit(
        "read_file",
        args,
    ).allowed

    assert budget.admit(
        "read_file",
        args,
    ).allowed

    result = budget.admit(
        "read_file",
        args,
    )

    assert not result.allowed
    assert result.reason == "repeated_request"
    assert budget.calls_used == 2


def test_json_argument_order_normalized():

    budget = ExecutionBudget(
        BudgetPolicy(max_repeats=1)
    )

    first = '{"path":"pricing.py","start_line":1}'
    second = '{"start_line":1,"path":"pricing.py"}'

    assert budget.admit(
        "read_file_range",
        first,
    ).allowed

    assert not budget.admit(
        "read_file_range",
        second,
    ).allowed


def test_deadline_exceeded():

    current_time = [100.0]

    budget = ExecutionBudget(
        BudgetPolicy(
            max_seconds=30,
            finalization_reserve_seconds=5,
        ),
        clock=lambda: current_time[0],
    )

    current_time[0] = 131.0

    assert budget.expired()

    result = budget.admit(
        "search_repository",
        '{"query":"pricing"}',
    )

    assert not result.allowed
    assert result.reason == "deadline_exceeded"


def test_finalization_reserve():

    current_time = [100.0]

    budget = ExecutionBudget(
        BudgetPolicy(
            max_seconds=30,
            finalization_reserve_seconds=10,
        ),
        clock=lambda: current_time[0],
    )

    current_time[0] = 121.0

    assert budget.should_finalize()
    assert not budget.expired()

    result = budget.admit(
        "search_repository",
        '{"query":"pricing"}',
    )

    assert not result.allowed
    assert result.reason == "budget_exhausted"


def test_different_requests_allowed():

    budget = ExecutionBudget(
        BudgetPolicy(max_repeats=1)
    )

    assert budget.admit(
        "read_file_range",
        '{"path":"pricing.py","start_line":1}',
    ).allowed

    assert budget.admit(
        "read_file_range",
        '{"path":"pricing.py","start_line":20}',
    ).allowed


def test_invalid_policy():

    try:
        BudgetPolicy(max_tool_calls=0)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Invalid budget should be rejected"
        )
