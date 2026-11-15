
from __future__ import annotations

from typing import Any

from agent.provider_correlation import (
    ProviderCorrelationStore,
)


class CorrelatedGenerationGateway:
    def __init__(
        self,
        gateway: Any,
        correlation: ProviderCorrelationStore,
    ):
        self.gateway = gateway
        self.correlation = correlation

    def create(self, request: dict) -> Any:
        record = self.correlation.load()

        if record is None:
            raise RuntimeError(
                "Correlation must be prepared first"
            )

        # The underlying gateway must enforce Day 40
        # admission and durable submission intent.
        result = self.gateway.create(request)

        response_id = getattr(result, "id", None)
        if not response_id:
            raise RuntimeError(
                "Provider response ID unavailable"
            )

        self.correlation.record_response(response_id)
        return result
