
# Day 43 — Model Output Contracts

## Objective
Enforce a typed application contract over
OpenAI Responses API output.

## Key concepts
- JSON syntax vs schema validity
- Provider-side Structured Outputs
- Pydantic local validation
- Refusals and incomplete responses
- Semantic validation
- Provenance and downstream authorization

## Architecture
Existing admitted gateway
  -> Provider response
  -> StructuredResponseGateway
  -> RepositoryAnswer
  -> Existing evidence and final-answer gates

## Files created
- agent/output_contract.py
- agent/structured_output_request.py
- agent/structured_response_gateway.py
- tests/test_structured_response_gateway.py

## Failure matrix
| Condition | Handling |
|---|---|
| Valid answer | Return typed result |
| Valid abstention | Return typed abstention |
| Malformed JSON | Reject |
| Missing field | Reject |
| Wrong type | Reject |
| Semantic contradiction | Reject |
| Provider refusal | Refused outcome |
| Incomplete response | Incomplete outcome |

## Design decisions
Why not trust JSON mode alone?

Why validate even with strict Structured Outputs?

Why should validation failures not automatically
trigger provider resubmission?

How does this interact with the evidence ledger?


