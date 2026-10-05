# Day 1 — Coding Agent Architecture

**Status:** ✅ Complete
**Phase:** Coding Agent Foundations

## Objective

Understand what actually makes a coding agent an agent, and separate
the responsibilities of the model, harness, tools, and execution
environment.

## Study Resources

1. [Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
   - Provider: OpenAI
   - Focus: Model/harness/tool interaction and the iterative
     action-observation loop.
   - Key takeaway: The model proposes actions while the harness
     executes tools and returns observations.

2. [Sandbox Agents](https://openai.com/index/introducing-updates-to-codex/)
   - Provider: OpenAI
   - Focus: Separation between orchestration and execution environments.
   - Key takeaway: Model reasoning, harness orchestration, and environment
     execution are separate architectural concerns.

## Mental Model

    User goal
        ↓
      Harness
        ↓
    Context construction
        ↓
    Model inference
        ↓
    Action request
        ↓
    Policy / permission
        ↓
    Tool execution
        ↓
    Environment
        ↓
    Observation
        └────────→ next inference

## Hands-On Experiments

### Experiment 1 — Tool-enabled debugging

Created a trivial defect in `average()` and asked the coding agent to:

1. inspect implementation and tests;
2. form a hypothesis;
3. identify verification;
4. make the smallest fix;
5. verify the result.

Observed the model → action → observation loop.

### Experiment 2 — No tools

Asked the model to diagnose the same problem without reading files,
running commands, or modifying the environment.

Compared model reasoning with environment-grounded reasoning.

### Experiment 3 — Incorrect user hypothesis

Provided an intentionally incorrect hypothesis:

> `reduce()` is skipping the first element.

Asked the agent to verify the hypothesis before accepting it.

Observed whether the agent relied on user-provided assumptions or
converted uncertainty into observable evidence.

## Key Findings

- The model proposes actions; the harness executes them.
- Repository state exists outside the model.
- Tool results become observations for subsequent inference.
- Agents can convert uncertain beliefs into observable evidence.
- Correct reasoning depends on more than model capability.

## Failure Boundaries

**Model failure:** Incorrect reasoning despite sufficient evidence.

**Context failure:** Necessary information never reaches the model.

**Tool failure:** Environment interaction returns incorrect or
incomplete information.

**Harness failure:** Incorrect orchestration, state, permissions,
or tool routing.

## Reflection

The model itself did not execute shell commands or modify files.
Those capabilities came from the surrounding agent system.

Test results became agent knowledge only after the tool result was
returned as an observation and incorporated into subsequent model
context.

## Completion Artifact

Reconstructed an agent run as a sequence of model decisions, tool
requests, environment observations, and subsequent inference.

## Key Principle

> **Agent quality ≠ model quality.**