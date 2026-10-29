
from dataclasses import replace

import pytest

import agent.loop as agent_loop

from agent.checkpoint import RecoveryBlocked
from agent.context import ContextPolicy
from agent.context_reconstruction import reconstruct_local_context
from agent.evidence_archive import EvidenceArchiveStore
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
def archive_boundary(tmp_path, monkeypatch):
    repo = setup_repo(tmp_path)

    for number in range(6):
        (repo / f"file_{number}.md").write_text(
            f"Value {number}\nOriginal second line\n",
            encoding="utf-8",
        )

    client = ScriptedClient(
        response(
            "resp-1",
            calls=[
                tool(f"call-{n}", f"file_{n}.md")
                for n in range(3)
            ],
        ),
        response(
            "resp-2",
            calls=[
                tool(f"call-{n}", f"file_{n}.md")
                for n in range(3, 6)
            ],
        ),
    )

    original_save = RunSnapshotStore.save

    def interrupt_before_third_request(self, snapshot):
        if (
            snapshot.response_id == "resp-2"
            and snapshot.model_request_started
        ):
            raise RuntimeError("simulated pre-request crash")

        return original_save(self, snapshot)

    monkeypatch.setattr(
        RunSnapshotStore,
        "save",
        interrupt_before_third_request,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated pre-request crash",
    ):
        agent_loop.run_agent(
            "Review six repository files",
            repo,
            client=client,
        )

    assert len(client.requests) == 2

    snapshot_store, checkpoint_store = stores(repo)
    snapshot = snapshot_store.load()

    assert snapshot.response_id == "resp-2"
    assert snapshot.model_request_started is False

    base = repo / ".agent-checkpoints"

    memory_store = MemoryCapsuleStore(
        base / f"{snapshot.run_id}.memory.json"
    )

    evidence_store = EvidenceArchiveStore(
        base / f"{snapshot.run_id}.evidence.json"
    )

    return (
        repo,
        snapshot_store,
        checkpoint_store,
        memory_store,
        evidence_store,
    )


def audit(boundary, *, with_archive=True):
    repo, snapshot, checkpoint, memory, evidence = boundary

    return reconstruct_local_context(
        repo,
        snapshot,
        checkpoint,
        memory,
        context_policy=ContextPolicy(),
        evidence_store=evidence if with_archive else None,
    )


def test_restores_all_six_observations(archive_boundary):
    report = audit(archive_boundary)
    archive = archive_boundary[4].load()
    capsule = archive_boundary[3].load()

    assert len(archive.records) == 6
    assert len(archive.file_hashes) == 6

    assert capsule.unique_evidence == 6
    assert capsule.omitted_evidence == 1

    assert len(report.evidence_ledger.records) == 6
    assert report.evidence_ledger.covers("file_0.md", 1, 1)
    assert report.evidence_ledger.covers("file_5.md", 1, 1)

    assert report.model_resume_allowed is False


def test_old_capsule_only_audit_still_blocks(archive_boundary):
    with pytest.raises(
        RecoveryBlocked,
        match="omitted evidence",
    ):
        audit(archive_boundary, with_archive=False)


def test_unobserved_line_change_blocks(archive_boundary):
    repo = archive_boundary[0]

    # The agent inspected line 1 only.
    # Change line 2 while leaving line 1 untouched.
    (repo / "file_0.md").write_text(
        "Value 0\nChanged second line\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RecoveryBlocked,
        match="Observed file changed",
    ):
        audit(archive_boundary)


def test_archive_identity_mismatch_blocks(archive_boundary):
    store = archive_boundary[4]

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
        audit(archive_boundary)


def test_missing_archive_blocks(archive_boundary):
    store = archive_boundary[4]
    store.path.unlink()

    with pytest.raises(
        RecoveryBlocked,
        match="Evidence archive missing",
    ):
        audit(archive_boundary)


def test_incomplete_archive_blocks(archive_boundary):
    store = archive_boundary[4]
    archive = store.load()

    removed_path = archive.records[-1].path

    store.save(
        replace(
            archive,
            records=archive.records[:-1],
            file_hashes={
                path: digest
                for path, digest in archive.file_hashes.items()
                if path != removed_path
            },
        )
    )

    with pytest.raises(
        RecoveryBlocked,
        match="archive and capsule disagree",
    ):
        audit(archive_boundary)


def test_ambiguous_model_request_still_blocks(
    archive_boundary,
):
    snapshot_store = archive_boundary[1]

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
        audit(archive_boundary)
