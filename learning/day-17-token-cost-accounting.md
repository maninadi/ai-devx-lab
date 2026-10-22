# Day 17 — Token Usage, Cost Accounting & Resource-Aware Decisions

Date: 2026-10-21
Status: In progress

## Objective

Track actual model-reported token usage,
estimate model-token costs, and introduce
cost-aware execution decisions.

## Official Resources

- OpenAI Responses API:
  https://developers.openai.com/api/reference/resources/responses/methods/create

- GPT-4.1 Mini pricing:
  https://developers.openai.com/api/docs/models/gpt-4.1-mini

- OpenAI Prompt Caching:
  https://developers.openai.com/api/docs/guides/prompt-caching

- Python Decimal:
  https://docs.python.org/3.12/library/decimal.html

- Claude Messages API:
  https://platform.claude.com/docs/en/api/messages

## Architecture

Describe:

1. Provider usage extraction
2. Normalized token accounting
3. Pricing configuration
4. Cumulative cost ledger
5. Cost-aware finalization

## Implementation

New module:
agent/cost_accounting.py

Components:
- TokenUsage
- TokenRates
- CostLedger

## Integration

Explain interactions with:

- Model responses
- Execution budgets
- Tool recovery
- Context budgeting
- Evidence ledger
- Final-answer gate
- JSONL tracing

## Test Results

Usage extraction:
Cost calculation:
Cumulative accounting:
Duplicate prevention:
Missing usage:
Cost threshold:
Unknown usage:
Model mismatch:
Cache-write validation:

Full pytest suite:
Fake-client integration:

## Real Model Experiment

Question:

Model:
Pricing configuration:
Model requests:
Input tokens:
Cached input tokens:
Output tokens:
Estimated model cost:
Final answer status:

## Remaining Limitations

- Soft cost limit, not guaranteed maximum.
- No pre-request output-cost reservation based on
  a known maximum token count.
- No authoritative billing reconciliation.
- No separate tool-service charges.
- No generalized cache-write pricing.
- No multi-model rate catalog.
- No durable cross-run accounting.
- Missing usage may make totals incomplete.
- No task-value or marginal-utility estimation.

## Reflection

When should an agent stop investigating
because the expected benefit of additional
work no longer justifies its cost?
