
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.model_protocol import (
    ModelReply,
    ModelProtocolError,
    inspect_response,
)
from agent.model_request_gateway import ModelRequestGateway
from agent.request_lifecycle import (
    RequestLifecycle,
    RequestOutcome,
    RetryPolicy,
)
from agent.request_observability import (
    ObservableGateway,
    RequestContext,
    execute_observed,
)
from agent.trace import RunTrace


@dataclass(frozen=True)
class PipelineResult:
    outcome: RequestOutcome
    attempts: int
    reply: ModelReply | None
    operation_id: str
    reason: str


def execute_model_request(
    client: Any,
    request: dict,
    trace: RunTrace,
    *,
    context_window: int,
    safety_reserve_tokens: int = 1024,
    deadline_seconds: float = 30.0,
) -> PipelineResult:
    """
    Compose preflight, lifecycle, tracing,
    and protocol validation.

    This function does not execute tool calls.
    """

    model = request.get("model")

    if not isinstance(model, str) or not model:
        raise ValueError("Request must specify a model")

    context = RequestContext.create(model)

    gateway = ModelRequestGateway(
        client,
        context_window=context_window,
        safety_reserve_tokens=safety_reserve_tokens,
    )

    observable = ObservableGateway(
        gateway,
        trace,
        context,
    )

    # Conservative integration policy:
    # no application-level automatic replay yet.
    lifecycle = RequestLifecycle(
        observable,
        policy=RetryPolicy(max_attempts=1),
        deadline_seconds=deadline_seconds,
    )

    result = execute_observed(
        lifecycle,
        request,
        trace,
        context,
    )

    if result.outcome != RequestOutcome.COMPLETED:
        return PipelineResult(
            outcome=result.outcome,
            attempts=result.attempts,
            reply=None,
            operation_id=context.operation_id,
            reason=result.reason,
        )

    try:
        reply = inspect_response(result.response)

        # The requested model must match the returned
        # model for this strict integration exercise.
        if reply.model != model:
            raise ModelProtocolError(
                "Response model mismatch"
            )

    except ModelProtocolError:
        trace.emit(
            "model_protocol_rejected",
            operation_id=context.operation_id,
            error_type="ModelProtocolError",
        )
        raise

    trace.emit(
        "model_protocol_accepted",
        operation_id=context.operation_id,
        response_id=reply.response_id,
        requires_tools=reply.requires_tools,
        has_final_text=reply.has_final_text,
    )

    return PipelineResult(
        outcome=result.outcome,
        attempts=result.attempts,
        reply=reply,
        operation_id=context.operation_id,
        reason="validated_completed",
    )
