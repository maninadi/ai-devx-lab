# Day 19 — Agent Checkpoints, Resumability & Crash Recovery

Date: 2026-10-23
Status: In progress

## Objective

Implement durable tool-batch checkpoints and
conservative recovery for interrupted agent execution.

## Official Resources

- OpenAI Conversation State:
  https://developers.openai.com/api/docs/guides/conversation-state

- Python os:
  https://docs.python.org/3.12/library/os.html

- Python JSON:
  https://docs.python.org/3.12/library/json.html

- pytest tmp_path:
  https://docs.pytest.org/en/stable/how-to/tmp_path.html

## Architecture

Explain:

1. Checkpoint versus execution trace
2. Write-ahead tool intent
3. Atomic checkpoint replacement
4. Persisted tool results
5. In-flight operation recovery
6. Read-only replay restrictions

## Implementation

New module:
agent/checkpoint.py

Components:
- ToolCall
- BatchCheckpoint
- CheckpointStore
- ToolBatchJournal
- recover_readonly_batch

## Integration

Document exact changes made to agent/loop.py.

Explain where checkpoints are saved:

- Before tool execution
- Before individual tool calls
- After completed tool results
- After the entire tool batch

## Test Results

Checkpoint persistence:
Completed-result recovery:
In-flight recovery:
Unsafe replay rejection:
Checkpoint overwrite protection:
Schema validation:

Full pytest suite:

## Real Model Experiment

Question:

Model:
Tool calls:
Checkpoint path:
Checkpoint stage:
Completed outputs:
In-flight call:

## Remaining Limitations

- Full agent-run resume is not implemented.
- Execution budgets are not restored.
- Cost ledger is not restored.
- Evidence ledger is not restored.
- State-machine history is not restored.
- Repository changes can invalidate replay assumptions.
- External side effects are not exactly-once.
- Concurrent checkpoint writers are not supported.
- Power-loss durability is not fully guaranteed.
- Checkpoints require secure local storage.

## Reflection

What would be required to safely resume an
agent after an interrupted model request
or an ambiguous external tool operation?
