
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import ValidationError

from agent.output_contract import RepositoryAnswer
from agent.structured_output_request import (
    with_repository_answer_format,
)


class OutputOutcome(str, Enum):
    VALID = "valid"
    REFUSED = "refused"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


class OutputContractError(RuntimeError):
    def __init__(self, outcome: OutputOutcome):
        self.outcome = outcome
        super().__init__(outcome.value)


def validate_response(
    response: Any,
) -> RepositoryAnswer:
    if getattr(response, "status", None) != "completed":
        raise OutputContractError(
            OutputOutcome.INCOMPLETE
        )

    output = getattr(response, "output", None)
    if not isinstance(output, list):
        raise OutputContractError(
            OutputOutcome.INVALID
        )

    texts = []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue

        for content in getattr(item, "content", []):
            kind = getattr(content, "type", None)

            if kind == "refusal":
                raise OutputContractError(
                    OutputOutcome.REFUSED
                )

            if kind == "output_text":
                value = getattr(content, "text", None)
                if not isinstance(value, str):
                    raise OutputContractError(
                        OutputOutcome.INVALID
                    )
                texts.append(value)

    # Exactly one complete JSON payload.
    if len(texts) != 1:
        raise OutputContractError(
            OutputOutcome.INVALID
        )

    try:
        return RepositoryAnswer.model_validate_json(
            texts[0],
            strict=True,
        )
    except ValidationError as exc:
        raise OutputContractError(
            OutputOutcome.INVALID
        ) from exc


class StructuredResponseGateway:
    def __init__(self, gateway: Any):
        self.gateway = gateway

    def create(
        self,
        request: dict,
    ) -> tuple[RepositoryAnswer, Any]:
        formatted_request = (
            with_repository_answer_format(request)
        )

        response, decision = self.gateway.create(
            formatted_request
        )

        answer = validate_response(response)
        return answer, decision
