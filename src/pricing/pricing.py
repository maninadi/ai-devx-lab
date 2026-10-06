import math
from typing import Literal

from .enterprise import EnterprisePricingProvider

CustomerTier = Literal["standard", "silver", "gold", "enterprise"]


def calculate_discount(
    subtotal: float,
    customer_tier: CustomerTier,
    *,
    customer_id: str | None = None,
    enterprise_provider: EnterprisePricingProvider | None = None,
) -> float:
    """Enterprise provider rates are fractions: 0.12 represents 12%."""
    if subtotal <= 0:
        return 0

    if customer_tier == "enterprise":
        if not customer_id or enterprise_provider is None:
            raise ValueError("Enterprise pricing requires a customer ID and provider")
        rate = enterprise_provider.get_discount_rate(customer_id)
        if isinstance(rate, bool) or not math.isfinite(rate) or not 0 <= rate <= 1:
            raise ValueError("Enterprise discount rate must be a finite fraction from 0 to 1")
        return subtotal * min(rate, 0.20)

    if customer_tier == "gold":
        discount_percent = 15
        if subtotal > 1000:
            discount_percent += 2
        return subtotal * min(discount_percent, 20) / 100

    if customer_tier == "silver":
        return subtotal * 0.05

    return 0
