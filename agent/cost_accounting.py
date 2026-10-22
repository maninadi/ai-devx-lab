from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


MILLION = Decimal("1000000")


def token_count(
    obj: Any,
    field: str,
    default: int | None = None,
) -> int:
    value = getattr(obj, field, default)

    if type(value) is not int or value < 0:
        raise ValueError(
            f"Invalid token count: {field}"
        )

    return value


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0

    @classmethod
    def from_openai_response(
        cls,
        response: Any,
    ) -> TokenUsage | None:

        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is None:
            return None

        details = getattr(
            usage,
            "input_tokens_details",
            None,
        )

        output_details = getattr(
            usage,
            "output_tokens_details",
            None,
        )

        input_tokens = token_count(
            usage,
            "input_tokens",
        )

        cached_tokens = token_count(
            details,
            "cached_tokens",
            0,
        )

        output_tokens = token_count(
            usage,
            "output_tokens",
        )

        reasoning_tokens = token_count(
            output_details,
            "reasoning_tokens",
            0,
        )

        cache_write_tokens = token_count(
            details,
            "cache_write_tokens",
            0,
        )

        # Today's rate card does not price
        # separately billed cache writes.

        if cache_write_tokens != 0:
            raise ValueError(
                "Cache-write pricing is not configured"
            )

        if cached_tokens > input_tokens:
            raise ValueError(
                "Cached tokens exceed input tokens"
            )

        if reasoning_tokens > output_tokens:
            raise ValueError(
                "Reasoning tokens exceed output tokens"
            )

        total = getattr(
            usage,
            "total_tokens",
            None,
        )

        if (
            total is not None
            and total != input_tokens + output_tokens
        ):
            raise ValueError(
                "Inconsistent total token count"
            )

        return cls(
            input_tokens=input_tokens,
            cached_input_tokens=cached_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        )

    @property
    def uncached_input_tokens(self) -> int:
        return (
            self.input_tokens
            - self.cached_input_tokens
        )


@dataclass(frozen=True)
class TokenRates:
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal

    def __post_init__(self):

        for rate in (
            self.input_per_million,
            self.cached_input_per_million,
            self.output_per_million,
        ):
            if (
                not isinstance(rate, Decimal)
                or not rate.is_finite()
                or rate < 0
            ):
                raise ValueError(
                    "Rates must be finite, "
                    "nonnegative Decimal values"
                )

    def calculate(
        self,
        usage: TokenUsage,
    ) -> Decimal:

        uncached_cost = (
            Decimal(
                usage.uncached_input_tokens
            )
            * self.input_per_million
        )

        cached_cost = (
            Decimal(
                usage.cached_input_tokens
            )
            * self.cached_input_per_million
        )

        output_cost = (
            Decimal(
                usage.output_tokens
            )
            * self.output_per_million
        )

        return (
            uncached_cost
            + cached_cost
            + output_cost
        ) / MILLION


class CostLedger:
    """
    Tracks API-reported token usage for one run.

    Estimated cost covers configured model
    token rates only.

    It is not an authoritative billing ledger.
    """

    def __init__(
        self,
        *,
        model: str,
        rates: TokenRates,
    ):
        self.model = model
        self.rates = rates

        self.response_ids: set[str] = set()

        self.response_count = 0
        self.unknown_usage_count = 0

        self.input_tokens = 0
        self.cached_input_tokens = 0
        self.output_tokens = 0

        self.estimated_cost_usd = Decimal("0")

    def record(
        self,
        response: Any,
    ) -> tuple[str, Decimal | None]:

        response_id = getattr(
            response,
            "id",
            None,
        )

        if (
            not isinstance(response_id, str)
            or not response_id
        ):
            self.unknown_usage_count += 1
            return "unpriced", None

        if response_id in self.response_ids:
            return "duplicate", None

        self.response_ids.add(response_id)
        self.response_count += 1

        try:
            actual_model = getattr(
                response,
                "model",
                None,
            )

            if (
                actual_model is not None
                and actual_model != self.model
                and not actual_model.startswith(
                    self.model + "-"
                )
            ):
                raise ValueError(
                    "Response model does not match rate card"
                )

            usage = TokenUsage.from_openai_response(
                response
            )

        except (ValueError, AttributeError):
            self.unknown_usage_count += 1
            return "unpriced", None

        if usage is None:
            self.unknown_usage_count += 1
            return "missing_usage", None

        cost = self.rates.calculate(usage)

        self.input_tokens += usage.input_tokens

        self.cached_input_tokens += (
            usage.cached_input_tokens
        )

        self.output_tokens += usage.output_tokens

        self.estimated_cost_usd += cost

        return "recorded", cost

    def should_finalize(
        self,
        *,
        max_cost_usd: Decimal | None,
        reserve_usd: Decimal = Decimal("0"),
    ) -> bool:

        if max_cost_usd is None:
            return False

        if (
            not max_cost_usd.is_finite()
            or not reserve_usd.is_finite()
            or max_cost_usd <= 0
            or reserve_usd < 0
            or reserve_usd >= max_cost_usd
        ):
            raise ValueError(
                "Invalid cost budget"
            )

        # Unknown usage prevents reliable
        # enforcement of a cost threshold.

        if self.unknown_usage_count:
            return True

        threshold = (
            max_cost_usd - reserve_usd
        )

        return (
            self.estimated_cost_usd
            >= threshold
        )
