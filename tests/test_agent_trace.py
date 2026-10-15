import json

from pathlib import Path
from types import SimpleNamespace

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
                name="read_file",
                arguments=json.dumps({
                    "path": "pricing.md"
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
            output_text="Gold discount is 15%.",
            usage=SimpleNamespace(
                input_tokens=150,
                output_tokens=30,
            ),
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

    assert events[-1]["status"] == "completed"

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