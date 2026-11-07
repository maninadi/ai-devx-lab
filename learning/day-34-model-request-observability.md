
# Day 34 — Model Request Observability & Correlation IDs

Status: In progress

## Learning objectives

- Understand run IDs, operation IDs, and provider request IDs.
- Instrument model attempts without changing lifecycle behavior.
- Record structured, privacy-conscious events.
- Correlate retries and lifecycle outcomes.
- Test observability without live API calls.

## Official resources

- https://developers.openai.com/api/docs/guides/production-best-practices
- https://github.com/openai/openai-python
- https://opentelemetry.io/docs/concepts/signals/traces/
- https://docs.python.org/3/library/unittest.mock.html

## Implementation

Created:
- agent/request_observability.py
- tests/test_request_observability.py

Reused:
- agent/trace.py
- agent/request_lifecycle.py
- agent/model_request_gateway.py

## Test results

Observability tests: [record result]
Full regression suite: [record result]

## Sample trace

Run ID: [record]
Operation ID: [record]
Event count: [record]
Final outcome: [record]

## Architecture decisions

1. Preserve the existing RunTrace recorder.
2. Decorate the gateway rather than modify lifecycle logic.
3. Use stable operation IDs across attempts.
4. Record metadata, not prompt or response content.
5. Preserve the original exception on failure.
6. Keep tracing separate from business logic.

## Reflection

1. Why do run_id and operation_id need separate identities?
2. Why might one logical operation have several provider request IDs?
3. Why shouldn't exception messages be logged automatically?
4. How would you correlate a request after a process crash?
5. How can observability accidentally leak sensitive information?

## Known limitations

- No separate preflight/generation stage events
- No durable attempt journal
- No error-header request ID extraction
- No strict event schema for every field
- No direct integration into run_agent()

