
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from agent.deadline_gateway import DeadlineBudget
from agent.durable_generation_factory import (
    build_durable_gateway,
)
from agent.generation_attempt_journal import (
    AttemptConflict,
    AttemptState,
    GenerationAttemptJournal,
)


class FakeClient:
    def __init__(self, *, fail_generation=False):
        self.fail_generation = fail_generation
        self.generation_calls = 0

    def with_options(self, **options):
        parent = self

        class TokenCounter:
            def count(self, **kwargs):
                return NS(input_tokens=20)

        class Responses:
            input_tokens = TokenCounter()

            def create(self, **kwargs):
                parent.generation_calls += 1

                if parent.fail_generation:
                    raise RuntimeError(
                        "Simulated crash after submission"
                    )

                return NS(
                    id="resp-test",
                    status="completed",
                )

        return NS(responses=Responses())


def payload():
    return {
        "model": "test-model",
        "input": "Hello",
        "max_output_tokens": 100,
    }


def make_gateway(
    client,
    journal_root: Path,
    operation_id: str,
):
    return build_durable_gateway(
        client,
        operation_id=operation_id,
        journal_root=journal_root,
        context_window=1000,
        safety_reserve_tokens=100,
        budget=DeadlineBudget.start(10),
    )


def test_intent_is_durable(tmp_path):
    operation_id = uuid4().hex
    journal = GenerationAttemptJournal(
        tmp_path, operation_id
    )

    journal.record_submission_intent()

    recovered = GenerationAttemptJournal(
        tmp_path, operation_id
    ).load()

    assert recovered.state == AttemptState.SUBMISSION_INTENT


def test_duplicate_intent_blocked(tmp_path):
    journal = GenerationAttemptJournal(
        tmp_path, uuid4().hex
    )
    journal.record_submission_intent()

    with pytest.raises(AttemptConflict):
        journal.record_submission_intent()


def test_response_requires_intent(tmp_path):
    journal = GenerationAttemptJournal(
        tmp_path, uuid4().hex
    )

    with pytest.raises(AttemptConflict):
        journal.record_response(
            "resp-test", "completed"
        )


def test_success_persists_response(tmp_path):
    operation_id = uuid4().hex
    client = FakeClient()

    gateway = make_gateway(
        client, tmp_path, operation_id
    )

    response, _ = gateway.create(payload())

    recovered = GenerationAttemptJournal(
        tmp_path, operation_id
    ).load()

    assert response.id == "resp-test"
    assert recovered.state == AttemptState.RESPONSE_RECEIVED
    assert recovered.response_id == "resp-test"
    assert client.generation_calls == 1


def test_crash_after_submission_remains_ambiguous(tmp_path):
    operation_id = uuid4().hex
    client = FakeClient(fail_generation=True)

    gateway = make_gateway(
        client, tmp_path, operation_id
    )

    with pytest.raises(RuntimeError):
        gateway.create(payload())

    recovered = GenerationAttemptJournal(
        tmp_path, operation_id
    ).load()

    assert recovered.state == AttemptState.SUBMISSION_INTENT
    assert client.generation_calls == 1


def test_restart_blocks_automatic_replay(tmp_path):
    operation_id = uuid4().hex
    client = FakeClient(fail_generation=True)

    gateway = make_gateway(
        client, tmp_path, operation_id
    )

    with pytest.raises(RuntimeError):
        gateway.create(payload())

    recovered_client = FakeClient()

    with pytest.raises(RuntimeError, match="reconciliation"):
        make_gateway(
            recovered_client,
            tmp_path,
            operation_id,
        )

    assert recovered_client.generation_calls == 0


def test_invalid_operation_id_rejected(tmp_path):
    with pytest.raises(ValueError):
        GenerationAttemptJournal(
            tmp_path,
            "../unsafe",
        )


def test_failed_intent_write_prevents_generation(
    tmp_path, monkeypatch
):
    operation_id = uuid4().hex
    client = FakeClient()

    def fail_write(self, record):
        raise OSError("Simulated disk failure")

    monkeypatch.setattr(
        GenerationAttemptJournal,
        "_write",
        fail_write,
    )

    gateway = make_gateway(
        client, tmp_path, operation_id
    )

    with pytest.raises(OSError):
        gateway.create(payload())

    assert client.generation_calls == 0


def test_response_record_cannot_be_overwritten(tmp_path):
    journal = GenerationAttemptJournal(
        tmp_path, uuid4().hex
    )

    journal.record_submission_intent()
    journal.record_response(
        "resp-first", "completed"
    )

    with pytest.raises(AttemptConflict):
        journal.record_response(
            "resp-second", "completed"
        )

    assert journal.load().response_id == "resp-first"
