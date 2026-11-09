
# Day 36 — Provider Timeout Propagation & Request Safety

Status: In progress

## Official resources
- https://github.com/openai/openai-python
- https://developers.openai.com/api/docs/guides/error-codes
- https://docs.python.org/3/library/time.html#time.monotonic
- https://docs.pytest.org/en/stable/how-to/monkeypatch.html

## Implementation
- agent/deadline_gateway.py
- tests/test_deadline_gateway.py
- scripts/day36_probe.py

## Design decisions
1. Preflight and generation share one deadline.
2. Each provider call receives the remaining budget.
3. SDK automatic retries are disabled.
4. Generation does not begin after preflight failure.
5. Stage events distinguish preflight from submission.

## Test results
Focused tests:
Full regression suite:

## Reflection
1. Why isn't SDK timeout a hard wall-clock deadline?
2. Why must preflight and generation share a budget?
3. Why disable hidden SDK retries?
4. What makes a generation timeout ambiguous?
5. Which stage boundaries need durable checkpoints?

## Known limitations
- No direct integration into execute_model_request()
- No durable stage checkpoint yet
- No hard cancellation guarantee
- No real provider timeout test

