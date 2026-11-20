
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from agent.output_failure_policy import OutputAction


class DiagnosticKind(str, Enum):
    POLICY_DECIDED = "policy_decided"
    PROVIDER_EXCEPTION = "provider_exception"
    OBSERVATION_FAILED = "observation_failed"


class ReceiptState(str, Enum):
    NOT_RECORDED = "not_recorded"
    INTENT_ONLY = "intent_only"
    RECEIVED = "received"
    UNKNOWN = "unknown"


class FailureCategory(str, Enum):
    TIMEOUT = "timeout"
    RUNTIME = "runtime"
    OTHER = "other"


@dataclass(frozen=True)
class OutputDiagnostic:
    operation_id: str
    kind: DiagnosticKind
    receipt_state: ReceiptState
    response_id: str | None = None
    action: OutputAction | None = None
    failure_category: FailureCategory | None = None

    def __post_init__(self):
        if (
            not isinstance(self.operation_id, str)
            or len(self.operation_id) != 32
            or any(
                c not in "0123456789abcdef"
                for c in self.operation_id
            )
        ):
            raise ValueError("Invalid operation ID")

        if (
            self.response_id is not None
            and (
                not isinstance(self.response_id, str)
                or not self.response_id
            )
        ):
            raise ValueError("Invalid response ID")

        if (
            self.receipt_state != ReceiptState.RECEIVED
            and self.response_id is not None
        ):
            raise ValueError(
                "Response ID requires received state"
            )


DiagnosticSink = Callable[[OutputDiagnostic], None]


def classify_exception(
    error: Exception,
) -> FailureCategory:
    if isinstance(error, TimeoutError):
        return FailureCategory.TIMEOUT

    if isinstance(error, RuntimeError):
        return FailureCategory.RUNTIME

    return FailureCategory.OTHER
