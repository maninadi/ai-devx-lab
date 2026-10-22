from decimal import Decimal
from types import SimpleNamespace

from agent.cost_accounting import (
    CostLedger,
    TokenRates,
    TokenUsage,
)


RATES = TokenRates(
    input_per_million=Decimal("0.40"),
    cached_input_per_million=Decimal("0.10"),
    output_per_million=Decimal("1.60"),
)


def fake_response(
    response_id="resp_1",
    input_tokens=1000,
    cached_tokens=200,
    output_tokens=500,
):

    return SimpleNamespace(
        id=response_id,
        model="gpt-4.1-mini",
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            input_tokens_details=SimpleNamespace(
                cached_tokens=cached_tokens,
            ),
            output_tokens=output_tokens,
            output_tokens_details=SimpleNamespace(
                reasoning_tokens=0,
            ),
            total_tokens=(
                input_tokens + output_tokens
            ),
        ),
    )


def test_usage_extraction():

    usage = TokenUsage.from_openai_response(
        fake_response()
    )

    assert usage.input_tokens == 1000
    assert usage.cached_input_tokens == 200
    assert usage.uncached_input_tokens == 800
    assert usage.output_tokens == 500


def test_cost_calculation():

    usage = TokenUsage.from_openai_response(
        fake_response()
    )

    cost = RATES.calculate(usage)

    assert cost == Decimal("0.00114")


def test_cumulative_cost():

    ledger = CostLedger(
        model="gpt-4.1-mini",
        rates=RATES,
    )

    ledger.record(
        fake_response("resp_1")
    )

    ledger.record(
        fake_response("resp_2")
    )

    assert ledger.response_count == 2
    assert ledger.input_tokens == 2000

    assert (
        ledger.estimated_cost_usd
        == Decimal("0.00228")
    )


def test_duplicate_response_not_counted():

    ledger = CostLedger(
        model="gpt-4.1-mini",
        rates=RATES,
    )

    response = fake_response()

    ledger.record(response)

    status, cost = ledger.record(response)

    assert status == "duplicate"
    assert cost is None

    assert ledger.response_count == 1


def test_missing_usage_is_not_free():

    ledger = CostLedger(
        model="gpt-4.1-mini",
        rates=RATES,
    )

    response = SimpleNamespace(
        id="resp_missing",
        model="gpt-4.1-mini",
        usage=None,
    )

    status, cost = ledger.record(response)

    assert status == "missing_usage"
    assert cost is None
    assert ledger.unknown_usage_count == 1


def test_cost_budget_finalization():

    ledger = CostLedger(
        model="gpt-4.1-mini",
        rates=RATES,
    )

    ledger.record(
        fake_response(
            input_tokens=10000,
            cached_tokens=0,
            output_tokens=1000,
        )
    )

    assert ledger.should_finalize(
        max_cost_usd=Decimal("0.006"),
        reserve_usd=Decimal("0.001"),
    )


def test_unknown_usage_forces_finalization():

    ledger = CostLedger(
        model="gpt-4.1-mini",
        rates=RATES,
    )

    ledger.record(
        SimpleNamespace(
            id="resp_unknown",
            usage=None,
        )
    )

    assert ledger.should_finalize(
        max_cost_usd=Decimal("0.02"),
    )


def test_model_mismatch_is_unpriced():

    ledger = CostLedger(
        model="gpt-4.1-mini",
        rates=RATES,
    )

    response = fake_response()
    response.model = "another-model"

    status, cost = ledger.record(response)

    assert status == "unpriced"
    assert cost is None


def test_cache_write_not_silently_underpriced():

    ledger = CostLedger(
        model="gpt-4.1-mini",
        rates=RATES,
    )

    response = fake_response()

    response.usage.input_tokens_details.cache_write_tokens = 100

    status, cost = ledger.record(response)

    assert status == "unpriced"
    assert cost is None
