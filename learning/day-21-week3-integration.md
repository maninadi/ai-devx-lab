# Day 21 — Week 3 Integration & Review

Date: 2026-10-25
Status: In progress

## Objective

Verify that the agent's recovery, execution-budget,
cost-accounting, state-machine, checkpointing, and
restoration mechanisms work together.

## Official Resources

- OpenAI Function Calling:
  https://developers.openai.com/api/docs/guides/function-calling

- OpenAI Conversation State:
  https://developers.openai.com/api/docs/guides/conversation-state

- pytest Monkeypatch:
  https://docs.pytest.org/en/stable/how-to/monkeypatch.html

- pytest tmp_path:
  https://docs.pytest.org/en/stable/how-to/tmp_path.html

## Repository Baseline

Branch: main
Baseline commit: d437cefb28cc93f23c4778aebb1bdc677844d051

## Integration Findings

1. Duplicate run_finished event
2. Missing terminal event during unexpected finalization
3. Remaining full-run restoration limitations

## Changes

Modified:
- agent/loop.py

Created:
- tests/test_week3_integration.py

## Integration Tests

Multi-tool batch:
Safe-boundary restoration:
Ambiguous model request:
Invalid citation:
Unexpected finalization tool:

Full pytest suite:

## Architecture Review

Explain how these modules interact:

- agent/tool_recovery.py
- agent/execution_budget.py
- agent/cost_accounting.py
- agent/agent_state.py
- agent/checkpoint.py
- agent/run_recovery.py
- agent/loop.py

## Remaining Risks

- Evidence ledger is not restored.
- Context budget is not restored.
- Literal fact index is not restored.
- Repository changes can invalidate prior evidence.
- Ambiguous model requests require reconciliation.
- Side-effecting tools are not exactly-once.
- Snapshot and checkpoint updates are not atomic together.
- Model pricing policy needs versioning.
- Concurrent writers are unsupported.

## Reflection

1. Why are integration tests necessary after unit tests?
2. Why must all tool results from one model response
   be persisted before the next model request?
3. Why does restoring a cost ledger require response IDs?
4. Why is an ambiguous model request unsafe to replay?
5. What must be restored before full agent continuation
   can be enabled?

## Week 3 Assessment

What is the most important reliability invariant
you learned this week?

What would you improve before using this agent
in a production developer workflow?
