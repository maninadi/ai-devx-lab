import json

from pathlib import Path
from types import SimpleNamespace

import agent.loop as agent_loop
import pytest
from agent.loop import run_agent


class FakeResponses:

    def __init__(self, tool_requests=1, final_answer=None):
        self.requests = []
        self.counter = 0
        self.tool_requests = tool_requests
        self.final_answer = final_answer

    def create(self, **kwargs):
        self.requests.append(kwargs)
        self.counter += 1

        if self.counter <= self.tool_requests:

            tool_call = SimpleNamespace(
                type="function_call",
                name="read_file_range",
                arguments=json.dumps({
                    "path": "pricing.md",
                    "start_line": 1,
                    "end_line": 1,
                }),
                call_id=f"call_{self.counter:03d}",
            )

            return SimpleNamespace(
                id=f"resp_{self.counter:03d}",
                status="completed",
                output=[tool_call],
                output_text="",
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=20,
                ),
            )

        return SimpleNamespace(
            id=f"resp_{self.counter:03d}",
            status="completed",
            output=[],
            output_text=self.final_answer or (
                "- Gold customers receive a 15% discount. "
                "[[pricing.md:L1-L1]]"
            ),
            usage=None,
        )


class FakeClient:

    def __init__(self, tool_requests=1, final_answer=None):
        self.responses = FakeResponses(tool_requests, final_answer)


def test_agent_records_execution_trace(tmp_path):

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    (repo_root / "pricing.md").write_text(
        "Gold discount: 15%"
    )

    trace_dir = tmp_path / "traces"

    client = FakeClient()

    answer = run_agent(
        task="Explain Gold discounts",
        repo_root=repo_root,
        client=client,
        trace_dir=trace_dir,
    )

    assert "15%" in answer
    assert "[[pricing.md:L1-L1]]" in answer

    trace_files = list(
        trace_dir.glob("*.jsonl")
    )

    assert len(trace_files) == 1

    events = [
        json.loads(line)
        for line in trace_files[0].read_text().splitlines()
    ]

    event_types = [
        event["event"]
        for event in events
    ]

    assert "run_started" in event_types
    assert "model_request" in event_types
    assert "model_response" in event_types
    assert "tool_requested" in event_types
    assert "tool_completed" in event_types
    assert "run_finished" in event_types
    assert "evidence_recorded" in event_types
    assert "final_reviewed" in event_types

    assert events[-1]["status"] == "cited"

    assert (
        client.responses.requests[1]
        ["previous_response_id"]
        == "resp_001"
    )

    # Raw tool contents should not be persisted
    # in our trace file.
    assert (
        "Gold discount: 15%"
        not in trace_files[0].read_text()
    )

    tool_outputs = (
        client.responses.requests[1]["input"]
    )

    assert all(
        len(item["output"]) <= 3500
        for item in tool_outputs
    )


def test_agent_retries_tool_timeout(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pricing.md").write_text("Gold discount: 15%")
    trace_dir = tmp_path / "traces"
    client = FakeClient()
    calls = []
    execute_tool = agent_loop.execute_tool

    def flaky_dispatch(*, name, arguments, repo_root):
        calls.append((name, arguments, repo_root))
        if len(calls) == 1:
            raise TimeoutError()
        return execute_tool(
            name=name,
            arguments=arguments,
            repo_root=repo_root,
        )

    monkeypatch.setattr(agent_loop, "execute_tool", flaky_dispatch)

    answer = run_agent(
        task="Explain Gold discounts",
        repo_root=repo_root,
        client=client,
        trace_dir=trace_dir,
    )

    assert calls == [
        ("read_file_range", {
            "path": "pricing.md", "start_line": 1, "end_line": 1,
        }, repo_root),
    ] * 2
    assert answer == (
        "- Gold customers receive a 15% discount. [[pricing.md:L1-L1]]"
    )
    assert len(client.responses.requests) == 2
    tool_outputs = client.responses.requests[1]["input"]
    assert len(tool_outputs) == 1
    assert tool_outputs[0]["call_id"] == "call_001"
    assert json.loads(tool_outputs[0]["output"])["ok"] is True

    trace_files = list(trace_dir.glob("*.jsonl"))
    assert len(trace_files) == 1
    events = [
        json.loads(line)
        for line in trace_files[0].read_text().splitlines()
    ]
    recovery_events = [
        event for event in events
        if event["event"] in {"tool_attempted", "tool_retry_scheduled"}
    ]
    assert [
        (event["event"], event["attempt"])
        for event in recovery_events
    ] == [
        ("tool_attempted", 1),
        ("tool_retry_scheduled", 1),
        ("tool_attempted", 2),
    ]
    assert recovery_events[1]["error_code"] == "transient_error"
    decision = next(
        event for event in events
        if event["event"] == "tool_recovery_decided"
    )
    assert decision["decision"] == "continue"
    assert decision["attempts"] == 2
    assert any(
        event["event"] == "tool_completed" and event["success"]
        for event in events
    )
    assert events[-1]["status"] == "cited"


@pytest.mark.parametrize("final_answer", [
    "- Gold customers receive a 15% discount. [[pricing.md:L1-L1]]",
    "ABSTAIN: No further investigation is available.",
])
def test_agent_blocks_third_identical_request(tmp_path, monkeypatch, final_answer):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pricing.md").write_text("Gold discount: 15%")
    trace_dir = tmp_path / "traces"
    client = FakeClient(tool_requests=3, final_answer=final_answer)
    calls = []
    execute_tool = agent_loop.execute_tool
    policy = agent_loop.BudgetPolicy(max_tool_calls=8, max_repeats=2)
    monkeypatch.setattr(agent_loop, "BudgetPolicy", lambda **kwargs: policy)

    def recording_dispatch(*, name, arguments, repo_root):
        calls.append((client.responses.counter, name, arguments, repo_root))
        return execute_tool(name=name, arguments=arguments, repo_root=repo_root)

    monkeypatch.setattr(agent_loop, "execute_tool", recording_dispatch)

    answer = run_agent(
        task="Explain Gold discounts",
        repo_root=repo_root,
        client=client,
        trace_dir=trace_dir,
    )

    assert calls == [
        (turn, "read_file_range", {
            "path": "pricing.md", "start_line": 1, "end_line": 1,
        }, repo_root)
        for turn in (1, 2)
    ]
    requests = client.responses.requests
    assert len(requests) == 4
    assert all(request["tool_choice"] != "none" for request in requests[:3])
    assert requests[3]["tool_choice"] == "none"
    for turn, request in enumerate(requests[1:], start=1):
        assert request["previous_response_id"] == f"resp_{turn:03d}"
        assert len(request["input"]) == 1
        output = request["input"][0]
        assert output["call_id"] == f"call_{turn:03d}"
        result = json.loads(output["output"])
        assert result["ok"] is (turn < 3)
        if turn == 3:
            assert result["error"]["code"] == "repeated_request"
            assert result["recovery"] == "stop"

    trace_files = list(trace_dir.glob("*.jsonl"))
    assert len(trace_files) == 1
    events = [json.loads(line) for line in trace_files[0].read_text().splitlines()]
    checks = [event for event in events if event["event"] == "budget_checked"]
    assert [
        (event["turn"], event["allowed"], event["reason"], event["calls_used"])
        for event in checks
    ] == [
        (1, True, "allowed", 1),
        (2, True, "allowed", 2),
        (3, False, "repeated_request", 2),
    ]
    assert [
        event["turn"] for event in events if event["event"] == "tool_attempted"
    ] == [1, 2]
    assert answer == final_answer
    review = next(event for event in events if event["event"] == "final_reviewed")
    assert review["accepted"] is True
    if answer.startswith("ABSTAIN:"):
        assert events[-1]["status"] == "abstained"
    else:
        assert any(
            event["event"] == "answer_provenance_checked" and event["provenance_ok"]
            for event in events
        )
        assert events[-1]["status"] == "cited"
