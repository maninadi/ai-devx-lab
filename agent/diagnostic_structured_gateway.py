
from __future__ import annotations

from typing import Any

from agent.generation_attempt_journal import (
    AttemptState,
    GenerationAttemptJournal,
)
from agent.output_diagnostics import (
    DiagnosticKind,
    DiagnosticSink,
    OutputDiagnostic,
    ReceiptState,
    classify_exception,
)


class DiagnosticStructuredGateway:
    def __init__(
        self,
        gateway: Any,
        *,
        operation_id: str,
        journal: GenerationAttemptJournal,
        sink: DiagnosticSink,
    ):
        if operation_id != journal.operation_id:
            raise ValueError(
                "Journal operation ID mismatch"
            )

        self.gateway = gateway
        self.operation_id = operation_id
        self.journal = journal
        self.sink = sink

    def _receipt(self) -> tuple[ReceiptState, str | None]:
        try:
            record = self.journal.load()
        except Exception:
            # Diagnostics cannot safely assume
            # that a failed read means no receipt.
            return ReceiptState.UNKNOWN, None

        if record is None:
            return ReceiptState.NOT_RECORDED, None

        if record.state == AttemptState.SUBMISSION_INTENT:
            return ReceiptState.INTENT_ONLY, None

        if record.state == AttemptState.RESPONSE_RECEIVED:
            return ReceiptState.RECEIVED, record.response_id

        return ReceiptState.UNKNOWN, None

    def _emit(
        self,
        *,
        kind: DiagnosticKind,
        action=None,
        failure_category=None,
    ) -> None:
        state, response_id = self._receipt()

        event = OutputDiagnostic(
            operation_id=self.operation_id,
            kind=kind,
            receipt_state=state,
            response_id=response_id,
            action=action,
            failure_category=failure_category,
        )

        self.sink(event)

    def create(self, request: dict):
        try:
            result = self.gateway.create(request)
        except Exception as exc:
            # Do not turn a provider failure
            # into an output validation result.
            try:
                self._emit(
                    kind=DiagnosticKind.PROVIDER_EXCEPTION,
                    failure_category=classify_exception(exc),
                )
            except Exception:
                # Preserve the original exception.
                # Never retry the provider request here.
                pass
            raise

        # Successful provider/policy handling.
        # Observability is best-effort; its failure
        # must not change the provider execution.
        try:
            self._emit(
                kind=DiagnosticKind.POLICY_DECIDED,
                action=result.policy.action,
            )
        except Exception:
            pass

        return result
