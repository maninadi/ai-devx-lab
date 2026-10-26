import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

import agent.loop as agent_loop

from agent.agent_state import AgentPhase
from agent.checkpoint import (
    CheckpointStore,
    RecoveryBlocked,
)
from agent.cost_accounting import TokenRates
from agent.execution_budget import BudgetPolicy
from agent.run_recovery import (
    RunSnapshotStore,
    restore_run,
)


def tool(call_id, path):
    return SimpleNamespace(
        type="function_call",
        call_id=call_id,
        name="read_file_range",
        arguments=json.dumps({
            "path": path,
            "start_line": 1,
            "end_line": 1,
        }),
    )


def response(response_id, *, calls=(), answer=""):
    return SimpleNamespace(
        id=response_id,
        status="completed",
        output=list(calls),
        output_text=answer,
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            input_tokens_details=SimpleNamespace(
                cached_tokens=0,
            ),
            output_tokens_details=SimpleNamespace(
                reasoning_tokens=0,
            ),
        ),
    )


class ScriptedClient:
    def __init__(self, *steps):
        self.steps = list(steps)
        self.requests = []
        self.responses = self

    def create(self, **kwargs):
        self.requests.append(kwargs)

        step = self.steps.pop(0)

        if isinstance(step, Exception):
            raise step

        return step


def setup_repo(tmp_path):
    (tmp_path / "pricing.md").write_text(
        "Gold discount: 15%\n"
    )

    (tmp_path / "policy.md").write_text(
        "Maximum discount: 20%\n"
    )

    return tmp_path


def stores(repo_root):
    paths = list(
        (repo_root / ".agent-checkpoints").glob(
            "*.run.json"
        )
    )

    assert len(paths) == 1

    run_path = paths[0]

    batch_path = run_path.with_name(
        run_path.name.removesuffix(".run.json")
        + ".json"
    )

    return (
        RunSnapshotStore(run_path),
        CheckpointStore(batch_path),
    )


def events(repo_root):
    traces = list(
        (repo_root / ".agent-traces").glob(
            "*.jsonl"
        )
    )

    assert len(traces) == 1

    return [
        json.loads(line)
        for line in traces[0].read_text().splitlines()
    ]


def test_multi_tool_batch_is_durable_and_final_reviewed(
    tmp_path,
):
    repo = setup_repo(tmp_path)

    client = ScriptedClient(
        response(
            "resp-1",
            calls=[
                tool("call-a", "pricing.md"),
                tool("call-b", "policy.md"),
            ],
        ),
        response(
            "resp-2",
            answer=(
                "- Gold discount: 15%. "
                "[[pricing.md:L1-L1]]\n"
                "- Maximum discount: 20%. "
                "[[policy.md:L1-L1]]"
            ),
        ),
    )

    answer = agent_loop.run_agent(
        "Review discount policy",
        repo,
        client=client,
    )

    assert "Maximum discount: 20%" in answer

    run_store, batch_store = stores(repo)

    checkpoint = batch_store.load()

    assert checkpoint.stage == "ready_for_model"

    assert [
        call.call_id
        for call in checkpoint.calls
    ] == ["call-a", "call-b"]

    assert (
        client.requests[1]["input"]
        == checkpoint.ordered_outputs()
    )

    snapshot = run_store.load()

    assert snapshot.calls_used == 2
    assert snapshot.model_request_started is True
    assert snapshot.cost_state["response_count"] == 1

    trace = events(repo)

    assert len([
        event
        for event in trace
        if event["event"] == "run_finished"
    ]) == 1

    assert trace[-1]["status"] == "cited"

    transitions = [
        (event["from_state"], event["to_state"])
        for event in trace
        if event["event"] == "agent_state_transition"
    ]

    assert transitions == [
        ("ready", "model_request"),
        ("model_request", "tool_execution"),
        ("tool_execution", "model_request"),
        ("model_request", "answer_review"),
        ("answer_review", "finished"),
    ]


def test_safe_boundary_restores_controls(
    tmp_path,
    monkeypatch,
):
    repo = setup_repo(tmp_path)

    client = ScriptedClient(
        response(
            "resp-1",
            calls=[tool("call-a", "pricing.md")],
        ),
    )

    original_save = RunSnapshotStore.save

    def interrupt_before_mark(self, snapshot):
        if snapshot.model_request_started:
            raise RuntimeError(
                "simulated crash before model request"
            )

        return original_save(self, snapshot)

    monkeypatch.setattr(
        RunSnapshotStore,
        "save",
        interrupt_before_mark,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated crash",
    ):
        agent_loop.run_agent(
            "Investigate Gold discounts",
            repo,
            client=client,
        )

    # The second model request never started.
    assert len(client.requests) == 1

    run_store, batch_store = stores(repo)

    rates = TokenRates(
        Decimal("0.40"),
        Decimal("0.10"),
        Decimal("1.60"),
    )

    restored = restore_run(
        run_store,
        batch_store,
        budget_policy=BudgetPolicy(),
        token_rates=rates,
        expected_model="gpt-4.1-mini",
        max_cost_usd=Decimal("0.02"),
        cost_reserve_usd=Decimal("0.005"),
    )

    assert (
        restored.state_machine.phase
        == AgentPhase.MODEL_REQUEST
    )

    assert restored.execution_budget.calls_used == 1
    assert restored.cost_ledger.response_count == 1

    assert (
        restored.previous_response_id
        == "resp-1"
    )

    assert (
        restored.pending_tool_outputs
        == batch_store.load().ordered_outputs()
    )

    assert restored.final_only is False


def test_ambiguous_model_request_is_not_replayed(
    tmp_path,
):
    repo = setup_repo(tmp_path)

    client = ScriptedClient(
        response(
            "resp-1",
            calls=[tool("call-a", "pricing.md")],
        ),
        RuntimeError(
            "simulated interruption during model request"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="simulated interruption",
    ):
        agent_loop.run_agent(
            "Investigate Gold discounts",
            repo,
            client=client,
        )

    run_store, batch_store = stores(repo)

    assert (
        run_store.load().model_request_started
        is True
    )

    with pytest.raises(
        RecoveryBlocked,
        match="model request may already have started",
    ):
        restore_run(
            run_store,
            batch_store,
            budget_policy=BudgetPolicy(),
            token_rates=TokenRates(
                Decimal("0.40"),
                Decimal("0.10"),
                Decimal("1.60"),
            ),
            expected_model="gpt-4.1-mini",
        )


def test_unobserved_citation_fails_closed(
    tmp_path,
):
    repo = setup_repo(tmp_path)

    client = ScriptedClient(
        response(
            "resp-1",
            calls=[tool("call-a", "pricing.md")],
        ),
        response(
            "resp-2",
            answer=(
                "- Gold discount: 15%. "
                "[[pricing.md:L2-L2]]"
            ),
        ),
    )

    answer = agent_loop.run_agent(
        "Investigate Gold discounts",
        repo,
        client=client,
    )

    assert answer.startswith("ABSTAIN:")

    trace = events(repo)

    assert [
        event["status"]
        for event in trace
        if event["event"] == "run_finished"
    ] == ["unverified"]


def test_finalization_tool_request_is_terminal(
    tmp_path,
    monkeypatch,
):
    repo = setup_repo(tmp_path)

    client = ScriptedClient(
        response(
            "resp-1",
            calls=[tool("call-a", "pricing.md")],
        ),
        response(
            "resp-2",
            calls=[tool("call-b", "policy.md")],
        ),
    )

    def deny(**kwargs):
        raise PermissionError("read denied")

    monkeypatch.setattr(
        agent_loop,
        "execute_tool",
        deny,
    )

    answer = agent_loop.run_agent(
        "Investigate Gold discounts",
        repo,
        client=client,
    )

    assert answer.startswith("ABSTAIN:")

    assert (
        client.requests[1]["tool_choice"]
        == "none"
    )

    trace = events(repo)

    assert [
        event["status"]
        for event in trace
        if event["event"] == "run_finished"
    ] == ["abstained"]

    assert trace[-1]["event"] == "run_finished"
