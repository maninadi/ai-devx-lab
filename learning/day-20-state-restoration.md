# Day 20 — Durable Agent State Restoration

Date: 2026-10-24
Status: In progress

## Objective

Restore execution-control state from durable
snapshots without resetting budgets or
bypassing recovery policies.

## Official Resources

- OpenAI Conversation State:
  https://developers.openai.com/api/docs/guides/conversation-state

- OpenAI Function Calling:
  https://developers.openai.com/api/docs/guides/function-calling

- Python time:
  https://docs.python.org/3.12/library/time.html

- Python JSON:
  https://docs.python.org/3.12/library/json.html

## Architecture

Explain:

1. Tool checkpoint versus run snapshot
2. State-machine reconstruction
3. Deadline restoration
4. Tool-budget restoration
5. Cost-ledger restoration
6. Recovery-boundary validation
7. Model-request ambiguity

## Implementation

New:
- agent/run_recovery.py
- tests/test_run_recovery.py

Modified:
- agent/loop.py

## Recovery Policies

Document the behavior for:

- Completed tool batch
- Incomplete tool batch
- Expired deadline
- Exhausted cost budget
- Invalid state history
- Mismatched response IDs
- Interrupted model request

## Test Results

Snapshot round-trip:
State restoration:
Budget restoration:
Deadline enforcement:
Cost restoration:
Model mismatch:
Counter validation:
State-history validation:
Checkpoint integration:

Full pytest suite:

## Remaining Limitations

- No automatic end-to-end model continuation.
- Evidence ledger still requires rehydration.
- Context-budget state still requires restoration.
- Model requests may have ambiguous outcomes.
- Snapshot and checkpoint are separate files.
- No multi-process writer coordination.
- No cross-host clock trust.
- No pricing-policy migration.
- No exactly-once external side effects.

## Reflection

What conditions must hold before a
recovered agent is allowed to make
another model request?
