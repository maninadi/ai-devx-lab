
# Day 35 — Week 5 Integration & Review

Status: In progress

## Scope
Integration of Days 29–34:
- Model protocol
- Token counting and preflight
- Request lifecycle
- Deadlines and conservative retry policy
- Correlation IDs and observability

## Official resources
- https://developers.openai.com/api/docs/guides/text
- https://github.com/openai/openai-python
- https://opentelemetry.io/docs/concepts/signals/traces/
- https://docs.pytest.org/en/stable/how-to/monkeypatch.html

## Implementation
- agent/model_execution_pipeline.py
- tests/test_week5_integration.py

## Test results
Integration tests:
Full regression suite:

## Safety invariants
1. Oversized requests never reach generation.
2. Token count failures fail closed.
3. Incomplete responses are not protocol-accepted.
4. Malformed tool calls are rejected.
5. Tool calls are never executed by the pipeline.
6. Correlation IDs link lifecycle events.

## Architecture limitations
- SDK retry configuration is external.
- Deadline does not forcibly cancel an in-flight request.
- No durable generation-attempt journal.
- No direct run_agent() integration.
- Preflight and generation stages need distinct events.

## Reflection
1. What belongs in the gateway versus lifecycle?
2. Why is a completed response not always valid?
3. Which failures are safe to retry?
4. Where should durable checkpoint writes occur?
5. What must be true before integrating into run_agent()?

