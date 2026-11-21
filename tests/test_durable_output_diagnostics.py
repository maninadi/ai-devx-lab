
import json
from dataclasses import replace
from uuid import uuid4

import pytest

from agent.durable_output_diagnostics import (
    DiagnosticConflict,
    DurableOutputDiagnosticStore,
)
from agent.generation_attempt_journal import (
    AttemptRecord,
    AttemptState,
)
from agent.output_diagnostics import (
    DiagnosticKind,
    OutputDiagnostic,
    ReceiptState,
)
from agent.output_failure_policy import OutputAction
from agent.output_trace_audit import (
    TraceStatus,
    audit_output_trace,
)
from agent.provider_correlation import (
    ProviderCorrelation,
)


def fixture_records():
    op = uuid4().hex

    diagnostic = OutputDiagnostic(
        operation_id=op,
        kind=DiagnosticKind.POLICY_DECIDED,
        receipt_state=ReceiptState.RECEIVED,
        response_id="resp_46",
        action=OutputAction.QUARANTINE,
    )

    attempt = AttemptRecord(
        operation_id=op,
        state=AttemptState.RESPONSE_RECEIVED,
        response_id="resp_46",
        response_status="completed",
    )

    correlation = ProviderCorrelation(
        operation_id=op,
        client_request_id="client_46",
        response_id="resp_46",
    )

    return op, diagnostic, attempt, correlation


def test_persistence_survives_reopen(tmp_path):
    op, diagnostic, _, _ = fixture_records()
    root = tmp_path / "diagnostics"

    store = DurableOutputDiagnosticStore(root, op)
    store.write(diagnostic)

    reopened = DurableOutputDiagnosticStore(root, op)
    assert reopened.load() == diagnostic


def test_duplicate_write_is_idempotent(tmp_path):
    op, diagnostic, _, _ = fixture_records()
    store = DurableOutputDiagnosticStore(
        tmp_path, op
    )

    store.write(diagnostic)
    store.write(diagnostic)

    assert store.load() == diagnostic


def test_conflicting_write_rejected(tmp_path):
    op, diagnostic, _, _ = fixture_records()
    store = DurableOutputDiagnosticStore(
        tmp_path, op
    )

    store.write(diagnostic)

    changed = replace(
        diagnostic,
        action=OutputAction.STOP_REFUSAL,
    )

    with pytest.raises(DiagnosticConflict):
        store.write(changed)

    assert store.load() == diagnostic


def test_corruption_rejected(tmp_path):
    op, diagnostic, _, _ = fixture_records()
    store = DurableOutputDiagnosticStore(
        tmp_path, op
    )

    store.write(diagnostic)
    store.path.write_text(
        '{"broken":true}', encoding="utf-8"
    )

    with pytest.raises(DiagnosticConflict):
        store.load()


def test_oversized_record_rejected(tmp_path):
    op, diagnostic, _, _ = fixture_records()
    store = DurableOutputDiagnosticStore(
        tmp_path, op
    )

    store.write(diagnostic)
    store.path.write_bytes(b"x" * 5000)

    with pytest.raises(DiagnosticConflict):
        store.load()


def test_persisted_record_excludes_content(tmp_path):
    op, diagnostic, _, _ = fixture_records()
    store = DurableOutputDiagnosticStore(
        tmp_path, op
    )

    store.write(diagnostic)
    raw = store.path.read_text("utf-8")
    data = json.loads(raw)

    assert "prompt" not in data
    assert "output_text" not in data
    assert "exception_message" not in data
    assert data["response_id"] == "resp_46"


def test_trace_correlation_consistent():
    op, diagnostic, attempt, correlation = (
        fixture_records()
    )

    audit = audit_output_trace(
        operation_id=op,
        diagnostic=diagnostic,
        attempt=attempt,
        correlation=correlation,
    )

    assert audit.status == TraceStatus.CONSISTENT
    assert audit.response_id == "resp_46"
    assert audit.client_request_id == "client_46"


def test_trace_conflict_detected():
    op, diagnostic, attempt, correlation = (
        fixture_records()
    )

    changed = replace(
        diagnostic,
        response_id="resp_wrong",
    )

    audit = audit_output_trace(
        operation_id=op,
        diagnostic=changed,
        attempt=attempt,
        correlation=correlation,
    )

    assert audit.status == TraceStatus.CONFLICT


def test_missing_diagnostic_is_incomplete():
    op, _, attempt, correlation = fixture_records()

    audit = audit_output_trace(
        operation_id=op,
        diagnostic=None,
        attempt=attempt,
        correlation=correlation,
    )

    assert audit.status == TraceStatus.INCOMPLETE


def test_intent_only_does_not_claim_response():
    op = uuid4().hex

    diagnostic = OutputDiagnostic(
        operation_id=op,
        kind=DiagnosticKind.PROVIDER_EXCEPTION,
        receipt_state=ReceiptState.INTENT_ONLY,
    )
    attempt = AttemptRecord(
        operation_id=op,
        state=AttemptState.SUBMISSION_INTENT,
    )
    correlation = ProviderCorrelation(
        operation_id=op,
        client_request_id="client_46",
    )

    audit = audit_output_trace(
        operation_id=op,
        diagnostic=diagnostic,
        attempt=attempt,
        correlation=correlation,
    )

    assert audit.status == TraceStatus.CONSISTENT
    assert audit.response_id is None
    assert "unknown" in audit.reason


def test_operation_identity_mismatch():
    op, diagnostic, attempt, correlation = (
        fixture_records()
    )

    changed = replace(
        diagnostic,
        operation_id=uuid4().hex,
    )

    audit = audit_output_trace(
        operation_id=op,
        diagnostic=changed,
        attempt=attempt,
        correlation=correlation,
    )

    assert audit.status == TraceStatus.CONFLICT
