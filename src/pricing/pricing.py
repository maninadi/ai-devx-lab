from typing import Literal

CustomerTier = Literal["standard", "silver", "gold"]


def calculate_discount(
    subtotal: float,
    customer_tier: CustomerTier,
) -> float:
    if subtotal <= 0:
        return 0

    if customer_tier == "gold":
        discount_percent = 15
        if subtotal > 1000:
            discount_percent += 2
        return subtotal * min(discount_percent, 20) / 100

    if customer_tier == "silver":
        return subtotal * 0.05

    return 0
