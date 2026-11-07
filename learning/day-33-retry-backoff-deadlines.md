
# Day 33 — Retry Backoff, Deadlines & Request Reconciliation

Status: In progress

## Official resources
- https://developers.openai.com/api/docs/guides/rate-limits
- https://github.com/openai/openai-python
- https://docs.python.org/3/library/time.html#time.monotonic
- https://docs.python.org/3/library/random.html#random.uniform

## Implementation
- agent/retry_timing.py
- agent/request_lifecycle.py
- tests/test_retry_timing.py

## Test results
New tests:
Full suite:

## Architecture decisions
1. Retry delay is exponential and bounded.
2. Jitter reduces synchronized retry bursts.
3. A monotonic deadline prevents late retries.
4. Ambiguous requests are never automatically replayed.
5. Reconciliation is explicit and injected.
6. SDK request timeout enforcement remains separate.

## Reflection
1. Why use monotonic time instead of wall-clock time?
2. Why does jitter help distributed systems?
3. Why isn't a deadline check enough to stop a blocked API call?
4. What evidence is required to reconcile a timed-out request?
5. Where should lifecycle attempt records live in the
   existing durable checkpoint architecture?

## Limitations
- No durable attempt journal yet
- No Retry-After handling
- No hard SDK timeout propagation
- No integration into run_agent()

