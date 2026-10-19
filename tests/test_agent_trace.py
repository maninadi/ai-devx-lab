import json

from pathlib import Path
from types import SimpleNamespace

import agent.loop as agent_loop
from agent.loop import run_agent


class FakeResponses:

    def __init__(self):
        self.requests = []
        self.counter = 0

    def create(self, **kwargs):
        self.requests.append(kwargs)
        self.counter += 1

        if self.counter == 1:

            tool_call = SimpleNamespace(
                type="function_call",
                name="read_file_range",
                arguments=json.dumps({
                    "path": "pricing.md",
                    "start_line": 1,
                    "end_line": 1,
                }),
                call_id="call_001",
            )

            return SimpleNamespace(
                id="resp_001",
                status="completed",
                output=[tool_call],
                output_text="",
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=20,
                ),
            )

        return SimpleNamespace(
            id="resp_002",
            status="completed",
            output=[],
            output_text=(
                "- Gold customers receive a 15% discount. "
                "[[pricing.md:L1-L1]]"
            ),
            usage=None,
        )


class FakeClient:

    def __init__(self):
        self.responses = FakeResponses()


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
