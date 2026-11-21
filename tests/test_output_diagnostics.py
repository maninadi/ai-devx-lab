
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from agent.diagnostic_structured_gateway import (
    DiagnosticStructuredGateway,
)
from agent.generation_attempt_journal import (
    AttemptState,
    GenerationAttemptJournal,
)
from agent.output_diagnostics import (
    DiagnosticKind,
    FailureCategory,
    ReceiptState,
)
from agent.output_failure_policy import OutputAction
from agent.policy_structured_gateway import (
    PolicyStructuredGateway,
)
from agent.structured_response_gateway import (
    StructuredResponseGateway,
)


VALID = (
    '{"state":"answered","answer":"Found",'
    '"citations":[{"path":"agent/loop.py",'
    '"start_line":1,"end_line":3}]}'
)


def provider_response(text, *, refusal=False):
    content = (
        [NS(type="refusal", refusal="Declined")]
        if refusal
        else [NS(type="output_text", text=text)]
    )

    return NS(
        id="resp_day45",
        status="completed",
        output=[
            NS(type="message", content=content)
        ],
    )


def build_stack(
    tmp_path,
    *,
    payload=VALID,
    refusal=False,
    timeout=False,
    sink=None,
):
    operation_id = uuid4().hex
    journal = GenerationAttemptJournal(
        tmp_path / "journal",
        operation_id,
    )
    events = []
    calls = []

    class FakeProvider:
        def create(self, request):
            calls.append(request)
            journal.record_submission_intent()

            if timeout:
                raise TimeoutError("secret request content")

            response = provider_response(
                payload,
                refusal=refusal,
            )
            journal.record_response(
                response.id,
                response.status,
            )
            return response, "preflight-ok"

    gateway = DiagnosticStructuredGateway(
        PolicyStructuredGateway(
            StructuredResponseGateway(FakeProvider())
        ),
        operation_id=operation_id,
        journal=journal,
        sink=sink if sink is not None else events.append,
    )

    return gateway, journal, events, calls


def test_valid_answer_emits_policy_event(tmp_path):
    gateway, journal, events, calls = build_stack(
        tmp_path
    )

    result = gateway.create({
        "model": "fake",
        "input": "secret prompt",
    })

    assert result.policy.action == (
        OutputAction.DELIVER_TO_EVIDENCE_GATE
    )
    assert len(calls) == 1
    assert len(events) == 1

    event = events[0]
    assert event.kind == DiagnosticKind.POLICY_DECIDED
    assert event.action == (
        OutputAction.DELIVER_TO_EVIDENCE_GATE
    )
    assert event.receipt_state == ReceiptState.RECEIVED
    assert event.response_id == "resp_day45"


@pytest.mark.parametrize(
    ("payload", "refusal", "expected"),
    [
        ("not-json", False, OutputAction.QUARANTINE),
        (VALID, True, OutputAction.STOP_REFUSAL),
    ],
)
def test_failure_events(
    tmp_path, payload, refusal, expected
):
    gateway, journal, events, calls = build_stack(
        tmp_path,
        payload=payload,
        refusal=refusal,
    )

    result = gateway.create({"model": "fake"})

    assert result.policy.action == expected
    assert events[0].action == expected
    assert events[0].response_id == "resp_day45"
    assert len(calls) == 1


def test_timeout_preserves_original_exception(tmp_path):
    gateway, journal, events, calls = build_stack(
        tmp_path,
        timeout=True,
    )

    with pytest.raises(
        TimeoutError,
        match="secret request content",
    ):
        gateway.create({"model": "fake"})

    assert len(calls) == 1
    assert journal.load().state == (
        AttemptState.SUBMISSION_INTENT
    )
    assert len(events) == 1
    assert events[0].kind == (
        DiagnosticKind.PROVIDER_EXCEPTION
    )
    assert events[0].failure_category == (
        FailureCategory.TIMEOUT
    )
    assert events[0].receipt_state == (
        ReceiptState.INTENT_ONLY
    )


def test_diagnostics_exclude_sensitive_content(tmp_path):
    gateway, journal, events, calls = build_stack(
        tmp_path,
        payload="secret model output",
    )

    gateway.create({
        "model": "fake",
        "input": "secret prompt",
    })

    event = events[0]
    serialized = repr(event)

    assert "secret prompt" not in serialized
    assert "secret model output" not in serialized
    assert "not-json" not in serialized
    assert event.action == OutputAction.QUARANTINE


def test_sink_failure_does_not_retry(tmp_path):
    calls_to_sink = []

    def broken_sink(event):
        calls_to_sink.append(event)
        raise OSError("telemetry unavailable")

    gateway, journal, events, calls = build_stack(
        tmp_path,
        sink=broken_sink,
    )

    result = gateway.create({"model": "fake"})

    assert result.policy.action == (
        OutputAction.DELIVER_TO_EVIDENCE_GATE
    )
    assert len(calls) == 1
    assert len(calls_to_sink) == 1
    assert journal.load().response_id == "resp_day45"


def test_sink_failure_does_not_mask_timeout(tmp_path):
    def broken_sink(event):
        raise OSError("telemetry unavailable")

    gateway, journal, events, calls = build_stack(
        tmp_path,
        timeout=True,
        sink=broken_sink,
    )

    with pytest.raises(TimeoutError):
        gateway.create({"model": "fake"})

    assert len(calls) == 1


def test_journal_identity_mismatch_rejected(tmp_path):
    first = uuid4().hex
    second = uuid4().hex
    journal = GenerationAttemptJournal(
        tmp_path / "journal",
        first,
    )

    with pytest.raises(ValueError):
        DiagnosticStructuredGateway(
            object(),
            operation_id=second,
            journal=journal,
            sink=lambda event: None,
        )


def test_missing_receipt_is_not_invented(tmp_path):
    operation_id = uuid4().hex
    journal = GenerationAttemptJournal(
        tmp_path / "journal",
        operation_id,
    )
    events = []

    class FakeGateway:
        def create(self, request):
            return NS(
                policy=NS(action=OutputAction.QUARANTINE)
            )

    gateway = DiagnosticStructuredGateway(
        FakeGateway(),
        operation_id=operation_id,
        journal=journal,
        sink=events.append,
    )

    gateway.create({"model": "fake"})

    assert events[0].receipt_state == (
        ReceiptState.NOT_RECORDED
    )
    assert events[0].response_id is None


def test_day46_durable_sink_integration(tmp_path):
    from agent.durable_output_diagnostics import (
        DurableOutputDiagnosticStore,
    )

    # build_stack generates its own operation ID.
    # Use a delegating sink to initialize the store
    # from the first event's verified identity.
    stores = []

    def durable_sink(event):
        store = DurableOutputDiagnosticStore(
            tmp_path / "diagnostics",
            event.operation_id,
        )
        store.write(event)
        stores.append(store)

    gateway, journal, events, calls = build_stack(
        tmp_path,
        sink=durable_sink,
    )

    result = gateway.create({
        "model": "fake",
        "input": "private question",
    })

    assert len(calls) == 1
    assert result.policy.action == (
        OutputAction.DELIVER_TO_EVIDENCE_GATE
    )
    assert len(stores) == 1

    persisted = stores[0].load()
    assert persisted.operation_id == journal.operation_id
    assert persisted.response_id == "resp_day45"

    # Reopen from disk, simulating a new process.
    reopened = DurableOutputDiagnosticStore(
        tmp_path / "diagnostics",
        journal.operation_id,
    )
    assert reopened.load() == persisted
