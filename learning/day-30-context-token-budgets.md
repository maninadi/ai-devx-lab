# Day 30 — Context Windows, Token Budgets & Truncation Semantics

**Phase:** 2 — Model/API Fundamentals
**Status:** In Progress
**Duration:** 90 minutes

## 1. Learning Objectives

- Understand how model context windows constrain input and output tokens.
- Distinguish characters, tokens, and token usage.
- Implement token-aware request admission.
- Reserve capacity for model output and a safety margin.
- Reject oversized requests before execution.
- Preserve existing character-based tool-output controls.
- Understand why provider-side token counting is needed for production accuracy.

## 2. Official Learning Resources

1. [OpenAI — Counting Tokens](https://developers.openai.com/api/docs/guides/token-counting)
2. [OpenAI — Conversation State](https://developers.openai.com/api/docs/guides/conversation-state)
3. [OpenAI — Text Generation](https://developers.openai.com/api/docs/guides/text)
4. [Python — Dataclasses](https://docs.python.org/3/library/dataclasses.html)

## 3. Concepts Learned

### Context Window

A model's context window defines how much information it can process within its supported limits, including input context and generated output.

Application-level admission budget:

```text
Max Input Budget =
    Context Window
    - Reserved Output Tokens
    - Safety Reserve
```

Example:

```text
Context window:        32,000
Reserved output:        6,000
Safety reserve:         4,000
--------------------------------
Maximum input:         22,000
```

This is a hypothetical configuration, not the published context limit of a specific model.

### Characters vs. Tokens

Character count is not an accurate substitute for token count.

Tokenization depends on the text, language, code syntax, punctuation, and model tokenizer.

The existing `ToolContextBudget` protects against excessively large serialized tool outputs, but it does not measure actual model token usage.

### Truncation vs. Admission Control

**Truncation:** Reduces the amount of content supplied, potentially losing information. Truncated repository evidence must be treated as incomplete.

**Admission control:** Evaluates whether a request fits the configured budget and rejects it if it does not.

Day 30 introduces admission control without silently truncating repository evidence.

## 4. Implementation

### New Files

| File | Purpose |
|---|---|
| `agent/token_budget.py` | Token-budget policy, decisions, and validation |
| `agent/request_preflight.py` | Adapter for checking model requests |
| `tests/test_token_budget.py` | Unit tests for token-budget behavior |

### Existing Files Preserved

- `agent/context.py`
- `agent/loop.py`
- `agent/model_protocol.py`

### Important Components

**TokenPolicy**

Defines the context-window size, maximum output allowance, and safety reserve.

**TokenDecision**

Records whether the request fits, the input count, the configured limit, remaining capacity, and utilization.

**TokenBudget**

Uses an injected token-counting function to evaluate a request.

**preflight_model_request()**

Provides an adapter for checking a complete request before execution.

### Architecture Decision

Day 30 does not modify `run_agent()` directly.

The preflight component is implemented separately because production integration requires reliable token counts, verified model limits, and correct handling of conversation history.

## 5. Test Results

Run:

```bash
uv run pytest -q tests/test_token_budget.py -v
uv run pytest -q
```

Record actual results:

Record actual results:

Test

Expected behavior

Actual result

Available input capacity

Calculates 700 tokens



Request within budget

Allowed



Exact boundary

Allowed



Input overflow

Rejected



Missing token count

Rejected



Counter exception

Rejected



Invalid policy

Rejected



Boolean token count

Rejected



Token-budget tests: Fill in actual pass/fail result.

Full pytest suite: Fill in actual pass/fail result.

6. Key Engineering Decisions

Unknown token counts must not be interpreted as zero.

Input admission must reserve capacity for output.

Token limits and character limits serve different purposes.

A rejected request must not reach the model API.

Truncation must not silently invalidate evidence completeness.

Token counting should be testable independently of the model provider.

Production request preflight requires a trustworthy count of the complete effective request.

7. Reflection Questions and Answers

Q1. Why isn't character count sufficient to enforce a context-window limit?

Because tokenization is variable. Equal-length strings may produce different token counts, and a complete model request includes additional content beyond the visible prompt.

Q2. Why reserve output tokens before admitting input?

Because generated output also consumes context capacity. Without an output allowance, a request might leave insufficient room for the intended response.

Q3. What happens when previous_response_id references a long conversation?

The effective input context may include prior conversation state. Counting only the latest input can underestimate the context required by the next request.

Q4. Why is an unknown token count different from zero?

Zero is a measurement. Unknown means the system cannot establish the request size. Treating unknown as zero could allow an oversized request through admission control.

Q5. Why didn't we modify run_agent() directly?

The current implementation uses an injected counter. We have not yet integrated provider-side counting of the complete effective request, verified the selected model's limits, or tested its interaction with the agent's recovery logic.

8. Remaining Limitations

No real provider-side token counter is integrated.

No model-specific context-window configuration is loaded automatically.

No exact accounting of provider-managed conversation history.

No multimodal token accounting.

No automatic context compaction or summarization.

No live token preflight enforcement in run_agent().

An application safety reserve does not guarantee the provider will accept a request.

9. Day 31 Preparation

Next: Exact Token Counting & Provider-Side Request Preflight

Planned work:

Use the OpenAI token-counting API for supported request types.

Count complete model requests, including relevant tool definitions.

Compare estimated and provider-reported usage.

Connect token preflight to the existing request-building architecture.

Test that rejected requests never invoke model generation.

10. Completion Summary

Implementation: Completed / Incomplete
Unit tests: Actual result
Full regression suite: Actual result
Learning artifact committed: Yes / No

Git commit: Add commit hash after pushing.

Key takeaway: Token-aware admission control is a separate reliability layer from character-based tool-output truncation. A production agent should use trustworthy request token counts and fail safely when capacity cannot be established.
