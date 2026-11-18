
# Day 44 — Structured Output Failure Policies

## Objective
Implement explicit, fail-closed policies for
structured model output failures.

## Official reading
- OpenAI Structured Outputs
- OpenAI Responses API
- OpenAI Python SDK retries
- Python Enum

## Architecture
PolicyStructuredGateway
  -> StructuredResponseGateway
    -> Existing generation gateway

## Policy matrix

| Outcome | Action | Automatic resubmission |
|---|---|---|
| Valid answer | Evidence gate | No |
| Valid abstention | Return abstention | No |
| Refusal | Stop | No |
| Incomplete | Inspect recorded response | No |
| Invalid schema | Quarantine | No |
| Transport timeout | Propagate to recovery | No |

## Design invariants
1. Invalid output never authorizes resubmission.
2. Durable provider receipts remain intact.
3. Refusals are distinct from abstentions.
4. Incomplete output is not a valid answer.
5. Validated content still requires provenance checks.
6. Transport failures are not swallowed by output policy.

## Files created
- agent/output_failure_policy.py
- agent/policy_structured_gateway.py
- tests/test_output_failure_policy.py

## Existing tests extended
- tests/test_week6_integration.py

## Reflection
1. Why is a refusal different from abstention?
2. Why can't a schema failure automatically trigger retry?
3. Why does the output policy not modify the journal?
4. What additional checks are needed before publishing an answer?
5. What happens if a provider timeout occurs before a response is received?

