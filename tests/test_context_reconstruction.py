
from dataclasses import replace

import pytest

import agent.loop as agent_loop

from agent.checkpoint import RecoveryBlocked
from agent.context import ContextPolicy
from agent.context_reconstruction import (
    compaction_advice,
    reconstruct_local_context,
)
from agent.run_recovery import RunSnapshotStore
from agent.working_memory import MemoryCapsuleStore

from tests.test_week3_integration import (
    ScriptedClient,
    response,
    setup_repo,
    stores,
    tool,
)


@pytest.fixture
def safe_boundary(tmp_path, monkeypatch):
    repo = setup_repo(tmp_path)

    client = ScriptedClient(
        response(
            "resp-1",
            calls=[tool("call-a", "pricing.md")],
        ),
    )

    original_save = RunSnapshotStore.save

    def interrupt_before_next_request(self, snapshot):
        if snapshot.model_request_started:
            raise RuntimeError(
                "simulated pre-request crash"
            )

        return original_save(self, snapshot)

    monkeypatch.setattr(
        RunSnapshotStore,
        "save",
        interrupt_before_next_request,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated pre-request crash",
    ):
        agent_loop.run_agent(
            "Review Gold discount",
            repo,
            client=client,
        )

    snapshot_store, checkpoint_store = stores(repo)
    snapshot = snapshot_store.load()

    memory_store = MemoryCapsuleStore(
        repo
        / ".agent-checkpoints"
        / f"{snapshot.run_id}.memory.json"
    )

    return (
        repo,
        snapshot_store,
        checkpoint_store,
        memory_store,
    )


def audit(boundary, policy=None):
    repo, snapshot_store, checkpoint_store, memory_store = boundary

    return reconstruct_local_context(
        repo,
        snapshot_store,
        checkpoint_store,
        memory_store,
        context_policy=policy or ContextPolicy(),
    )


def test_validated_evidence_and_budget(safe_boundary):
    report = audit(safe_boundary)
    capsule = safe_boundary[3].load()

    assert report.evidence_ledger.covers(
        "pricing.md", 1, 1
    )

    assert (
        report.context_budget.used_chars
        == capsule.context_chars_used
    )

    assert report.model_resume_allowed is False


def test_changed_source_blocks_reconstruction(safe_boundary):
    (safe_boundary[0] / "pricing.md").write_text(
        "Gold discount: 10%\n"
    )

    with pytest.raises(
        RecoveryBlocked,
        match="changed",
    ):
        audit(safe_boundary)


def test_capsule_identity_mismatch_blocks(safe_boundary):
    store = safe_boundary[3]

    store.save(
        replace(
            store.load(),
            response_id="wrong-response",
        )
    )

    with pytest.raises(
        RecoveryBlocked,
        match="boundary mismatch",
    ):
        audit(safe_boundary)


def test_omitted_evidence_blocks_full_reconstruction(
    safe_boundary,
):
    store = safe_boundary[3]

    store.save(
        replace(
            store.load(),
            unique_evidence=2,
            omitted_evidence=1,
        )
    )

    with pytest.raises(
        RecoveryBlocked,
        match="omitted evidence",
    ):
        audit(safe_boundary)


def test_ambiguous_model_request_blocks(
    safe_boundary,
    monkeypatch,
):
    monkeypatch.undo()

    snapshot_store = safe_boundary[1]

    snapshot_store.save(
        replace(
            snapshot_store.load(),
            model_request_started=True,
        )
    )

    with pytest.raises(
        RecoveryBlocked,
        match="model request may already have started",
    ):
        audit(safe_boundary)


def test_context_policy_mismatch_blocks(safe_boundary):
    with pytest.raises(
        RecoveryBlocked,
        match="Context policy differs",
    ):
        audit(
            safe_boundary,
            ContextPolicy(
                max_total_tool_chars=15000
            ),
        )


def test_compaction_review_is_advisory(safe_boundary):
    capsule = safe_boundary[3].load()

    assert compaction_advice(capsule) == "monitor"

    assert compaction_advice(
        replace(
            capsule,
            context_chars_used=9000,
            pressure="high",
        )
    ) == "manual_review"

    assert compaction_advice(
        replace(
            capsule,
            context_chars_used=12000,
            pressure="exhausted",
        )
    ) == "finalize_or_stop"

    assert compaction_advice(
        replace(
            capsule,
            unique_evidence=2,
            omitted_evidence=1,
        )
    ) == "manual_review"
