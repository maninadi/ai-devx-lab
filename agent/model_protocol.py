
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.cost_accounting import TokenUsage


class ModelProtocolError(ValueError):
    """Response cannot safely be interpreted."""


@dataclass(frozen=True)
class ModelReply:
    response_id: str
    model: str
    status: str
    text: str
    tool_call_names: tuple[str, ...]
    output_types: tuple[str, ...]
    usage: TokenUsage | None

    @property
    def requires_tools(self) -> bool:
        return bool(self.tool_call_names)

    @property
    def has_final_text(self) -> bool:
        return bool(self.text.strip()) and not self.requires_tools


def inspect_response(response: Any) -> ModelReply:
    response_id = getattr(response, "id", None)
    model = getattr(response, "model", None)
    status = getattr(response, "status", None)
    output = getattr(response, "output", None)

    if not isinstance(response_id, str) or not response_id:
        raise ModelProtocolError("Missing response ID")

    if not isinstance(model, str) or not model:
        raise ModelProtocolError("Missing response model")

    if status != "completed":
        raise ModelProtocolError(
            f"Response is not completed: {status}"
        )

    if not isinstance(output, (list, tuple)):
        raise ModelProtocolError("Invalid output collection")

    text_parts: list[str] = []
    tool_names: list[str] = []
    output_types: list[str] = []

    for item in output:
        item_type = getattr(item, "type", None)

        if not isinstance(item_type, str):
            raise ModelProtocolError("Output item missing type")

        output_types.append(item_type)

        if item_type == "function_call":
            name = getattr(item, "name", None)
            call_id = getattr(item, "call_id", None)
            arguments = getattr(item, "arguments", None)

            if (
                not isinstance(name, str)
                or not name
                or not isinstance(call_id, str)
                or not call_id
                or not isinstance(arguments, str)
            ):
                raise ModelProtocolError(
                    "Malformed function call"
                )

            # Do not execute or trust arguments here.
            tool_names.append(name)

        elif item_type == "message":
            content = getattr(item, "content", None)

            if not isinstance(content, (list, tuple)):
                raise ModelProtocolError(
                    "Invalid message content"
                )

            for part in content:
                part_type = getattr(part, "type", None)

                if part_type == "refusal":
                    raise ModelProtocolError(
                        "Model returned a refusal"
                    )

                if part_type == "output_text":
                    text = getattr(part, "text", None)

                    if not isinstance(text, str):
                        raise ModelProtocolError(
                            "Invalid output text"
                        )

                    text_parts.append(text)

        # Other output item types are preserved in
        # output_types but not interpreted as final text.

    try:
        usage = TokenUsage.from_openai_response(
            response
        )
    except (ValueError, AttributeError) as exc:
        raise ModelProtocolError(
            "Invalid token usage"
        ) from exc

    return ModelReply(
        response_id=response_id,
        model=model,
        status=status,
        text="\n".join(text_parts),
        tool_call_names=tuple(tool_names),
        output_types=tuple(output_types),
        usage=usage,
    )
