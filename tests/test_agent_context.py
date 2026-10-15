import json

import pytest

from agent.context import (
    ContextBudgetExceeded,
    ContextPolicy,
    ToolContextBudget,
)


def test_small_result_is_preserved():

    budget = ToolContextBudget()

    result = {
        "ok": True,
        "content": "Gold discount is 15%",
    }

    prepared, metadata = budget.prepare(
        "read_file",
        result,
    )

    assert json.loads(prepared) == result
    assert metadata["truncated"] is False
    assert metadata["sent_chars"] <= 3500


def test_large_result_is_truncated():

    budget = ToolContextBudget(
        ContextPolicy(
            max_tool_result_chars=800,
            max_total_tool_chars=2000,
        )
    )

    result = {
        "ok": True,
        "content": "Gold discount is 15%. " * 500,
    }

    prepared, metadata = budget.prepare(
        "read_file",
        result,
    )

    parsed = json.loads(prepared)

    assert len(prepared) <= 800
    assert parsed["truncated"] is True
    assert parsed["original_chars"] > 800

    assert metadata["truncated"] is True
    assert metadata["sent_chars"] <= 800


def test_cumulative_budget_is_enforced():

    budget = ToolContextBudget(
        ContextPolicy(
            max_tool_result_chars=500,
            max_total_tool_chars=600,
        )
    )

    large_result = {
        "ok": True,
        "content": "X" * 2000,
    }

    budget.prepare(
        "read_file",
        large_result,
    )

    with pytest.raises(
        ContextBudgetExceeded
    ):
        budget.prepare(
            "read_file",
            large_result,
        )


def test_truncation_does_not_claim_full_evidence():

    budget = ToolContextBudget(
        ContextPolicy(
            max_tool_result_chars=600,
            max_total_tool_chars=2000,
        )
    )

    result = {
        "ok": True,
        "content": (
            "Ordinary pricing rules.\n" * 100
            + "Enterprise discount is 22%."
        ),
    }

    prepared, _ = budget.prepare(
        "read_file",
        result,
    )

    parsed = json.loads(prepared)

    assert parsed["truncated"] is True

    # The model must not assume the preview
    # contains the complete original file.
    assert "Enterprise discount is 22%" not in prepared