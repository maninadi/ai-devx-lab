
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import time
import uuid

from agent.trace import RunTrace


@dataclass(frozen=True)
class RequestContext:
    operation_id: str
    model: str

    @classmethod
    def create(cls, model: str) -> "RequestContext":
        if not model:
            raise ValueError("Model must be provided")

        return cls(
            operation_id=uuid.uuid4().hex,
            model=model,
        )


def safe_provider_request_id(
    response: Any,
) -> str | None:
    value = getattr(
        response,
        "_request_id",
        None,
    )

    if not isinstance(value, str):
        return None

    # Keep only a bounded, single-line identifier.
    if not value or len(value) > 128:
        return None

    if not all(
        char.isascii()
        and (char.isalnum() or char in "-_")
        for char in value
    ):
        return None

    return value


class ObservableGateway:
    """
    Decorates an existing model request gateway.

    One instance represents one logical operation.
    Multiple create() calls represent its attempts.
    """

    def __init__(
        self,
        gateway: Any,
        trace: RunTrace,
        context: RequestContext,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.gateway = gateway
        self.trace = trace
        self.context = context
        self.clock = clock
        self.attempts = 0

    def create(self, request: dict):
        self.attempts += 1
        attempt = self.attempts
        start = self.clock()

        self.trace.emit(
            "model_attempt_started",
            operation_id=self.context.operation_id,
            attempt=attempt,
            model=self.context.model,
        )

        try:
            result = self.gateway.create(request)

        except Exception as exc:
            elapsed_ms = max(
                0.0,
                (self.clock() - start) * 1000,
            )

            self.trace.emit(
                "model_attempt_failed",
                operation_id=self.context.operation_id,
                attempt=attempt,
                elapsed_ms=round(elapsed_ms, 2),
                error_type=type(exc).__name__,
            )

            raise

        elapsed_ms = max(
            0.0,
            (self.clock() - start) * 1000,
        )

        response, decision = result

        usage = getattr(response, "usage", None)

        self.trace.emit(
            "model_attempt_returned",
            operation_id=self.context.operation_id,
            attempt=attempt,
            elapsed_ms=round(elapsed_ms, 2),
            response_id=getattr(
                response, "id", None
            ),
            provider_request_id=(
                safe_provider_request_id(response)
            ),
            response_status=getattr(
                response, "status", None
            ),
            input_tokens=getattr(
                usage, "input_tokens", None
            ),
            output_tokens=getattr(
                usage, "output_tokens", None
            ),
            preflight_input_tokens=getattr(
                decision, "input_tokens", None
            ),
        )

        return result


def execute_observed(
    lifecycle: Any,
    request: dict,
    trace: RunTrace,
    context: RequestContext,
):
    """
    Record the final lifecycle decision.

    The lifecycle must already be configured with
    an ObservableGateway for attempt-level events.
    """
    trace.emit(
        "model_operation_started",
        operation_id=context.operation_id,
        model=context.model,
    )

    try:
        result = lifecycle.execute(request)

    except Exception as exc:
        trace.emit(
            "model_operation_failed",
            operation_id=context.operation_id,
            error_type=type(exc).__name__,
        )
        raise

    trace.emit(
        "model_operation_finished",
        operation_id=context.operation_id,
        outcome=result.outcome.value,
        attempts=result.attempts,
        reason=result.reason,
    )

    return result
