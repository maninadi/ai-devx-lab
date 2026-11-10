
# Day 37 — Generation Submission Boundaries & Durable Attempt Records

Status: In progress

## Official resources

- https://docs.python.org/3/library/os.html#os.fsync
- https://docs.python.org/3/library/os.html#os.replace
- https://github.com/openai/openai-python
- https://docs.pytest.org/en/stable/how-to/tmp_path.html

## Implementation

Created:
- agent/generation_attempt_journal.py
- agent/durable_generation_gateway.py
- agent/durable_generation_factory.py
- tests/test_generation_attempt_journal.py

## Architecture decisions

1. Persist submission intent before invoking generation.
2. Persist response receipt before returning to the caller.
3. Treat missing response receipts as ambiguous.
4. Block replay of an existing logical operation.
5. Keep journal persistence independent of JSONL tracing.
6. Defer concurrent-writer and recovery-generation integration.

## Test results

Focused tests:
Full regression suite:

## Crash-consistency observations

Crash before durable intent:
Crash after durable intent:
Crash after provider response but before receipt:
Crash after durable receipt:

## Reflection

1. Why does write-ahead intent need fsync?
2. Why is submission intent not proof of provider receipt?
3. Why doesn't a response ID prove successful recovery?
4. What happens if two processes use the same operation ID?
5. How should this journal relate to GenerationStore.CURRENT?

## Known limitations

- Single-writer implementation
- No automatic provider reconciliation
- No response-body archival
- No integration into run_agent()
- No atomic coupling to immutable recovery generations


