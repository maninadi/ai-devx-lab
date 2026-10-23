# Day 18 — Agent State Machines & Explicit Transitions

Date: 2026-10-22
Status: In progress

## Objective

Introduce explicit execution states and
legal transitions into the cumulative
Python coding-agent harness.

## Official Reading

- OpenAI Function Calling:
  https://developers.openai.com/api/docs/guides/function-calling

- Python Enum:
  https://docs.python.org/3.12/library/enum.html

- Python Dataclasses:
  https://docs.python.org/3.12/library/dataclasses.html

- pytest Parametrization:
  https://docs.pytest.org/en/stable/how-to/parametrize.html

## State Model

Document the six states:

1. READY
2. MODEL_REQUEST
3. TOOL_EXECUTION
4. FINAL_REQUEST
5. ANSWER_REVIEW
6. FINISHED

## Transition Rules

Describe:

- Normal model execution
- Tool execution and continuation
- Budget-driven finalization
- Fatal termination
- Answer review
- Invalid transitions

## Implementation

New module:
agent/agent_state.py

Components:
- AgentPhase
- StateTransition
- InvalidTransition
- AgentStateMachine

## Agent Integration

Explain interactions with:

- Model request loop
- Tool execution
- Day 15 recovery
- Day 16 execution budgets
- Day 17 cost accounting
- Day 14 final-answer gate
- JSONL tracing

## Test Results

Legal execution paths:
Illegal transition rejection:
Terminal-state enforcement:
Finalization enforcement:
Transition history:
State mutation safety:

Full pytest suite:
Fake-client integration:

## Real Model Experiment

Question:

Model turns:

Tool calls:

State transitions:

Finalization reason:

Final state:

Answer review status:

## Remaining Limitations

- State exists only in process memory.
- No durable execution checkpoint.
- No crash recovery.
- No resumable model/tool execution.
- No parallel execution state management.
- No state-version migration.
- No event replay.
- State transitions alone do not enforce
  authorization or evidence correctness.

## Reflection

How should the application recover if
the process crashes after a tool succeeds
but before its result is returned to the model?
