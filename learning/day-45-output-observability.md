
# Day 45 — Output Validation Observability

## Objective
Add privacy-conscious diagnostic events to the
structured output validation pipeline.

## Official reading
- OpenTelemetry traces
- OpenTelemetry GenAI conventions
- Python logging
- OpenAI Structured Outputs

## Architecture
DiagnosticStructuredGateway
  -> PolicyStructuredGateway
    -> StructuredResponseGateway
      -> Existing generation gateway

## Event contract
Fields:
- operation_id
- kind
- receipt_state
- response_id
- action
- failure_category

## Privacy decisions
What is intentionally excluded from events?

Why are raw exception strings excluded?

Are response IDs sensitive operational metadata?

## Failure semantics
- Provider exceptions propagate.
- Sink failures are best-effort.
- Diagnostic failures never authorize retries.
- Journal records are never modified by the observer.

## Tests
Focused tests:
Full regression:
Fault injection:
Failures and fixes:

## Design limitations
- No production entry point yet
- No durable telemetry outbox
- No guaranteed event delivery
- No OpenTelemetry exporter
- No automated response retrieval
- No provenance authorization from diagnostics

## Reflection
1. Why is a durable journal different from a
   diagnostic event?
2. What happens if the sink fails after a
   successful provider response?
3. Why must telemetry not initiate retries?
4. How would you detect missing diagnostic events?
5. What would be required for audit-grade logging?

