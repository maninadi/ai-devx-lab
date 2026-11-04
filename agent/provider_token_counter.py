
from __future__ import annotations

from typing import Any, Mapping


class ProviderTokenCountError(RuntimeError):
    """Provider could not establish a valid input count."""


# Explicit allowlist of fields supported by our
# counting adapter. Do not blindly forward all
# generation-only request parameters.
COUNT_FIELDS = frozenset({
    "model",
    "input",
    "instructions",
    "tools",
    "previous_response_id",
    "conversation",
    "text",
    "reasoning",
    "truncation",
})


def countable_request(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise ProviderTokenCountError(
            "Request must be a mapping"
        )

    if not request.get("model"):
        raise ProviderTokenCountError(
            "Missing model"
        )

    if "input" not in request:
        raise ProviderTokenCountError(
            "Missing input"
        )

    # A strict policy prevents accidentally
    # omitting future token-affecting fields.
    supported_generation_fields = (
        COUNT_FIELDS
        | {
            "max_output_tokens",
            "tool_choice",
            "store",
            "stream",
            "metadata",
            "temperature",
            "top_p",
            "parallel_tool_calls",
        }
    )

    unknown = set(request) - supported_generation_fields

    if unknown:
        raise ProviderTokenCountError(
            f"Unreviewed request fields: {sorted(unknown)}"
        )

    return {
        key: value
        for key, value in request.items()
        if key in COUNT_FIELDS
    }


class OpenAIProviderTokenCounter:
    def __init__(self, client: Any):
        self.client = client

    def __call__(
        self,
        request: Mapping[str, Any],
    ) -> int:
        payload = countable_request(request)

        try:
            result = (
                self.client.responses
                .input_tokens.count(**payload)
            )
        except Exception as exc:
            raise ProviderTokenCountError(
                "Provider token count failed"
            ) from exc

        count = getattr(
            result,
            "input_tokens",
            None,
        )

        if type(count) is not int or count < 0:
            raise ProviderTokenCountError(
                "Provider returned invalid count"
            )

        return count
