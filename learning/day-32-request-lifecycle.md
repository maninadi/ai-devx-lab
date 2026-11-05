
# Day 32 — Request Lifecycle, Timeouts,
# Retries & Idempotency

Status: In progress

## Official resources
- https://developers.openai.com/api/docs/guides/error-codes
- https://developers.openai.com/api/docs/guides/rate-limits
- https://github.com/openai/openai-python
- https://docs.python.org/3/library/time.html

## Concepts learned
- Completed vs rejected vs ambiguous vs incomplete
- Transient error vs replay authorization
- Timeout and unknown execution outcome
- SDK retries vs application retries
- Idempotency and duplicate generation risks

## Implementation
- agent/request_lifecycle.py
- tests/test_request_lifecycle.py

## Test results
New lifecycle tests:
Full regression suite:

## Architecture decisions
1. Preflight remains separate from generation.
2. Ambiguous transport failures are not replayed.
3. Retries require explicit authorization.
4. Retry attempts are bounded.
5. Incomplete responses do not trigger replay.
6. Existing run_agent() remains unchanged.

## Reflection
1. Why is a timeout not proof that a request failed?
2. Why can automatic retries duplicate work?
3. What is the difference between a retryable error
   and a replay-safe operation?
4. Why must the SDK and application retry policies
   be coordinated?
5. How should the checkpoint journal record an
   ambiguous model request?

## Remaining limitations
- No backoff or jitter
- No monotonic retry deadline
- No automatic reconciliation
- No live integration into run_agent()
- No durable lifecycle record

