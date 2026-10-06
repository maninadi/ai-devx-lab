from typing import Protocol

class EnterprisePricingProvider(Protocol):
    def get_discount_rate(self, customer_id: str) -> float:
        ...