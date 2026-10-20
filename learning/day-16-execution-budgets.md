# Day 16 — Execution Budgets, Deadlines & Loop Prevention

Date: 2026-10-20
Status: Complete after verification

## Objective

Implement deterministic execution budgets for
tool requests, repeated operations, and elapsed time.

## Official Reading

- OpenAI Function Calling:
  https://developers.openai.com/api/docs/guides/function-calling

- Python time.monotonic:
  https://docs.python.org/3.12/library/time.html

- OpenAI Rate Limits:
  https://developers.openai.com/api/docs/guides/rate-limits

- Python concurrent.futures:
  https://docs.python.org/3.12/library/concurrent.futures.html

## Architecture

Explain:

1. Model-turn budget
2. Tool-call budget
3. Repetition detection
4. Execution deadline
5. Finalization reserve

## Implementation

New module:
agent/execution_budget.py

Components:
- BudgetPolicy
- BudgetDecision
- ExecutionBudget
- fingerprint()
- admit()
- should_finalize()

## Integration

Describe interactions with:

- Agent loop
- Tool recovery
- Context budgeting
- Evidence ledger
- Final-answer gate
- Execution tracing

## Test Results

Tool budget exhaustion:
Repeated request detection:
JSON argument normalization:
Deadline expiration:
Finalization reserve:
Different request handling:
Invalid configuration:

Full pytest suite:
Fake-client integration:

## Real Model Experiment

Question:

Model turns:

Tool requests admitted:

Tool requests blocked:

Retries performed:

Elapsed time:

Final status:

## Remaining Limitations

- No hard cancellation of running tools.
- No per-tool execution deadline.
- No semantic progress detection.
- No token-based execution budget.
- No monetary cost budget.
- No durable budget across process restarts.
- Repetition detection uses exact normalized arguments.
- Internal retries are tracked separately from tool requests.

## Reflection

How would you distinguish a productive
investigation from a runaway agent loop?
