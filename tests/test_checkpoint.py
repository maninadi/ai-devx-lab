import json

import pytest

from agent.checkpoint import (
    CheckpointStore,
    RecoveryBlocked,
    ToolBatchJournal,
    ToolCall,
    recover_readonly_batch,
)


def setup_batch(tmp_path):

    store = CheckpointStore(
        tmp_path / "checkpoint.json"
    )

    journal = ToolBatchJournal(store)

    journal.begin(
        run_id="run-1",
        response_id="resp-1",
        turn=2,
        calls=[
            ToolCall(
                "call-1",
                "read_file",
                '{"path":"a.py"}',
            ),
            ToolCall(
                "call-2",
                "search_repository",
                '{"query":"gold"}',
            ),
        ],
    )

    return store, journal


def test_persists_and_orders(tmp_path):

    store, journal = setup_batch(tmp_path)

    journal.start_call("call-1")
    journal.complete_call(
        "call-1",
        '{"ok":true}',
    )

    journal.start_call("call-2")
    journal.complete_call(
        "call-2",
        '{"ok":false}',
    )

    results = journal.finish()

    assert [
        item["call_id"]
        for item in results
    ] == ["call-1", "call-2"]

    assert (
        store.load().stage
        == "ready_for_model"
    )

    assert (
        json.loads(
            store.path.read_text()
        )["version"]
        == 1
    )


def test_recovery_skips_completed(tmp_path):

    store, journal = setup_batch(tmp_path)

    journal.start_call("call-1")

    journal.complete_call(
        "call-1",
        "saved",
    )

    called = []

    def execute(call):
        called.append(call.call_id)
        return "replayed"

    results = recover_readonly_batch(
        store,
        execute,
    )

    assert called == ["call-2"]

    assert [
        item["output"]
        for item in results
    ] == [
        "saved",
        "replayed",
    ]


def test_inflight_requires_explicit_replay(
    tmp_path,
):

    store, journal = setup_batch(tmp_path)

    journal.start_call("call-1")

    with pytest.raises(RecoveryBlocked):
        recover_readonly_batch(
            store,
            lambda call: "replayed",
        )

    results = recover_readonly_batch(
        store,
        lambda call: "replayed",
        allow_replay_inflight=True,
    )

    assert len(results) == 2


def test_unsafe_tool_is_not_replayed(
    tmp_path,
):

    store = CheckpointStore(
        tmp_path / "checkpoint.json"
    )

    journal = ToolBatchJournal(store)

    journal.begin(
        run_id="run-2",
        response_id="resp-2",
        turn=1,
        calls=[
            ToolCall(
                "call-3",
                "delete_file",
                "{}",
            ),
        ],
    )

    with pytest.raises(RecoveryBlocked):
        recover_readonly_batch(
            store,
            lambda call: "unexpected",
        )


def test_unfinished_batch_not_overwritten(
    tmp_path,
):

    store, journal = setup_batch(tmp_path)

    with pytest.raises(RecoveryBlocked):
        journal.begin(
            run_id="run-3",
            response_id="resp-3",
            turn=3,
            calls=[
                ToolCall(
                    "call-4",
                    "read_file",
                    "{}",
                ),
            ],
        )


def test_unknown_schema_rejected(tmp_path):

    store, journal = setup_batch(tmp_path)

    data = json.loads(
        store.path.read_text()
    )

    data["version"] = 99

    store.path.write_text(
        json.dumps(data)
    )

    with pytest.raises(ValueError):
        store.load()
