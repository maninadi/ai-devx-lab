
from __future__ import annotations

from typing import Any

from agent.provider_token_counter import (
    OpenAIProviderTokenCounter,
)
from agent.request_preflight import (
    preflight_model_request,
)


class ModelRequestGateway:
    def __init__(
        self,
        client: Any,
        *,
        context_window: int,
        safety_reserve_tokens: int = 1024,
    ):
        self.client = client
        self.context_window = context_window
        self.safety_reserve_tokens = (
            safety_reserve_tokens
        )

        self.counter = OpenAIProviderTokenCounter(
            client
        )

    def create(self, request: dict):
        decision = preflight_model_request(
            request,
            context_window=self.context_window,
            safety_reserve_tokens=(
                self.safety_reserve_tokens
            ),
            count_tokens=self.counter,
        )

        # Reaching this line means preflight passed.
        response = self.client.responses.create(
            **request
        )

        return response, decision
