
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

import agent.durable_output_diagnostics as durable
from agent.durable_output_diagnostics import (
    DiagnosticConflict,
    DurableOutputDiagnosticStore,
)
from agent.diagnostic_retention import (
    RetentionCandidate,
    RetentionReason,
    plan_diagnostic_retention,
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
from agent.provider_correlation import ProviderCorrelation


NOW = datetime(
    2026, 11, 20, tzinfo=timezone.utc
)


def records(*, received=True, finalized=True, days_old=30):
    op = uuid4().hex

    diagnostic = OutputDiagnostic(
        operation_id=op,
        kind=DiagnosticKind.POLICY_DECIDED,
        receipt_state=(
            ReceiptState.RECEIVED
            if received else ReceiptState.INTENT_ONLY
        ),
        response_id="resp_47" if received else None,
        action=OutputAction.QUARANTINE,
    )

    attempt = AttemptRecord(
        operation_id=op,
        state=(
            AttemptState.RESPONSE_RECEIVED
            if received else AttemptState.SUBMISSION_INTENT
        ),
        response_id="resp_47" if received else None,
        response_status="completed" if received else None,
    )

    correlation = ProviderCorrelation(
        operation_id=op,
        client_request_id="client_47",
        response_id="resp_47" if received else None,
    )

    candidate = RetentionCandidate(
        operation_id=op,
        created_at=NOW - timedelta(days=days_old),
        diagnostic=diagnostic,
        attempt=attempt,
        correlation=correlation,
        finalized=finalized,
    )
    return candidate


def test_old_finalized_response_is_eligible():
    candidate = records()
    plan = plan_diagnostic_retention(
        [candidate],
        now=NOW,
        minimum_age=timedelta(days=14),
    )
    assert plan.eligible_ids == (
        candidate.operation_id,
    )


def test_intent_only_operation_is_protected():
    candidate = records(received=False)
    plan = plan_diagnostic_retention(
        [candidate],
        now=NOW,
        minimum_age=timedelta(days=14),
    )
    assert plan.protected_ids == (
        candidate.operation_id,
    )
    assert plan.decisions[0].reason == (
        RetentionReason.UNRESOLVED
    )


def test_received_but_not_finalized_is_protected():
    candidate = records(finalized=False)
    plan = plan_diagnostic_retention(
        [candidate],
        now=NOW,
        minimum_age=timedelta(days=14),
    )
    assert plan.decisions[0].reason == (
        RetentionReason.NOT_FINALIZED
    )


def test_recent_record_is_protected():
    candidate = records(days_old=2)
    plan = plan_diagnostic_retention(
        [candidate],
        now=NOW,
        minimum_age=timedelta(days=14),
    )
    assert plan.decisions[0].reason == (
        RetentionReason.TOO_RECENT
    )


def test_mismatched_response_is_protected():
    candidate = records()
    changed = replace(
        candidate,
        diagnostic=replace(
            candidate.diagnostic,
            response_id="resp_wrong",
        ),
    )
    plan = plan_diagnostic_retention(
        [changed],
        now=NOW,
        minimum_age=timedelta(days=14),
    )
    assert plan.decisions[0].reason == (
        RetentionReason.INCONSISTENT
    )


def test_missing_diagnostic_is_protected():
    candidate = records()
    changed = replace(candidate, diagnostic=None)
    plan = plan_diagnostic_retention(
        [changed],
        now=NOW,
        minimum_age=timedelta(days=14),
    )
    assert plan.protected_ids == (
        candidate.operation_id,
    )


def test_duplicate_operation_rejected():
    candidate = records()
    with pytest.raises(ValueError):
        plan_diagnostic_retention(
            [candidate, candidate],
            now=NOW,
            minimum_age=timedelta(days=1),
        )


def test_candidate_limit_enforced():
    with pytest.raises(ValueError):
        plan_diagnostic_retention(
            [records(), records()],
            now=NOW,
            minimum_age=timedelta(days=1),
            max_candidates=1,
        )


def test_replace_failure_leaves_no_committed_record(
    tmp_path, monkeypatch
):
    candidate = records()
    store = DurableOutputDiagnosticStore(
        tmp_path / "diagnostics",
        candidate.operation_id,
    )

    def fail_replace(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(
        durable.os, "replace", fail_replace
    )

    with pytest.raises(OSError):
        store.write(candidate.diagnostic)

    assert store.load() is None
    assert not list(
        store.root.glob(".diagnostic-*")
    )


def test_directory_sync_failure_has_ambiguous_durability(
    tmp_path, monkeypatch
):
    candidate = records()
    store = DurableOutputDiagnosticStore(
        tmp_path / "diagnostics",
        candidate.operation_id,
    )

    def fail_sync(path):
        raise OSError("simulated directory sync failure")

    monkeypatch.setattr(
        durable, "_sync_directory", fail_sync
    )

    with pytest.raises(OSError):
        store.write(candidate.diagnostic)

    # Replacement occurred before directory sync.
    # The file may be visible even though durability
    # could not be confirmed.
    assert store.load() == candidate.diagnostic


def test_corrupt_record_cannot_be_overwritten(
    tmp_path,
):
    candidate = records()
    store = DurableOutputDiagnosticStore(
        tmp_path / "diagnostics",
        candidate.operation_id,
    )
    store.write(candidate.diagnostic)

    store.path.write_bytes(b"corrupt")

    with pytest.raises(DiagnosticConflict):
        store.write(candidate.diagnostic)

    assert store.path.read_bytes() == b"corrupt"


def test_retention_planning_does_not_delete_files(
    tmp_path,
):
    candidate = records()
    store = DurableOutputDiagnosticStore(
        tmp_path / "diagnostics",
        candidate.operation_id,
    )
    store.write(candidate.diagnostic)

    plan = plan_diagnostic_retention(
        [candidate],
        now=NOW,
        minimum_age=timedelta(days=14),
    )

    assert plan.eligible_ids
    assert store.load() == candidate.diagnostic
    assert store.path.exists()
