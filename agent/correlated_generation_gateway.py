
from __future__ import annotations

from typing import Any

from agent.provider_correlation import (
    ProviderCorrelationStore,
)

from agent.generation_fencing import GenerationFencing


class CorrelatedGenerationGateway:
    def __init__(
        self,
        gateway: Any,
        correlation: ProviderCorrelationStore,
        fencing: GenerationFencing | None = None,
        token: int | None = None,
    ):
        self.gateway = gateway
        self.correlation = correlation
        self.fencing = fencing
        self.token = token

    def create(self, request: dict) -> Any:
        record = self.correlation.load()

        if record is None:
            raise RuntimeError(
                "Correlation must be prepared first"
            )

        headers = request.get("extra_headers", {})

        if "X-Client-Request-Id" in headers:
            if headers["X-Client-Request-Id"] != record.client_request_id:
                raise RuntimeError(
                    "conflicting client request ID"
                )

        coorelated_request = {
            **request,
            "extra_headers": {
                **headers,
                "X-Client-Request-Id": record.client_request_id,
            },
        }

        response, decision = self.gateway.create(coorelated_request)

        response_id = getattr(response, "id", None)

        if not isinstance(response_id, str) or not response_id:
            raise RuntimeError(
                "Provider response ID unavailable"
            )

        if self.fencing is None or self.token is None:
            self.correlation.record_response(response_id)
        else:
            self.fencing.guarded(self.token, lambda: self.correlation.record_response(response_id))

        return response, decision
