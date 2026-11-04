# Day 31 — Exact Token Counting & Provider-Side Request Preflight

**Phase:** 2 — Model/API Fundamentals
**Status:** In progress

## Learning objectives

- Use provider-side input token counting.
- Preserve the Day 30 token-budget policy.
- Reject oversized requests before model generation.
- Compare preflight counts with actual usage.
- Test provider failures without live API calls.

## Official resources

- https://developers.openai.com/api/docs/guides/token-counting
- https://developers.openai.com/api/docs/guides/conversation-state
- https://developers.openai.com/api/docs/api-reference/responses/create
- https://github.com/openai/openai-python

## Implementation

Created:

- `agent/provider_token_counter.py`
- `agent/model_request_gateway.py`
- `tests/test_provider_preflight.py`
- `scripts/day31_probe.py`

Existing components reused:

- `agent/token_budget.py`
- `agent/request_preflight.py`

## Test results

Provider preflight tests: [record result]

Full regression suite: [record result]

## Live API experiment

Model: [record model]

Published context limit: [record limit and source]

Preflight input tokens: [record]

Actual input tokens: [record]

Actual output tokens: [record]

Difference between preflight and actual input: [record]

## Architecture decisions

1. Counting is separated from admission.
2. Admission is separated from generation.
3. Unknown token counts fail closed.
4. Rejected requests never reach generation.
5. Provider-managed conversation state must be represented in the count.
6. Production integration into `run_agent()` remains deferred pending recovery and checkpoint tests.

## Reflection

1. Why is provider counting preferable to character estimation?
2. Why does a request with tools potentially cost more input tokens?
3. What happens if the counting API fails?
4. Why must preflight precede the model-request side-effect boundary?
5. What recovery risk appears if preflight is added incorrectly to the existing checkpointed agent loop?

## Limitations

- No live integration into `run_agent()` yet.
- Provider counting is not a guarantee of generation success.
- Supported request fields depend on API and SDK capabilities.
- Counting calls have latency and operational overhead.
- Model limits must be configured accurately.

## Completion

Implementation: [completed / incomplete]

Tests: {
  "model": "gpt-4.1-mini",
  "response_status": "completed",
  "preflight_input_tokens": 30,
  "actual_input_tokens": 30,
  "actual_output_tokens": 17,
  "input_limit": 998848,
  "remaining_budget": 998818,
  "answer": "Token preflight verifies and prepares authentication tokens before executing actions in a coding agent."
}

Git commit: [75c01f8]

**Key takeaway:** A reliable coding agent should measure its proposed model input, enforce a configured capacity policy, and prevent oversized requests from reaching generation.
