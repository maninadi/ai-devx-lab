# Day 4 — Prompt Contracts

**Status:** 🟡 In Progress
**Phase:** Coding Agent Foundations

## Objective

Understand how explicit success criteria, constraints,
evidence requirements, and verification change an agent's
ability to determine whether a task is complete.

## Study Resources

1. [OpenAI — Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering)
   - Provider: OpenAI
   - Focus: Prompt structure, coding-agent instructions,
     testing, validation, and prompt lifecycle.
   - Key takeaway: Prompts are application behavior and should
     be versioned, tested, and evaluated.

2. [Anthropic — Prompting best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables)
   - Provider: Anthropic
   - Focus: Clear instructions, success criteria, verification,
     and agentic prompting.
   - Key takeaway: Specify the desired outcome clearly while
     avoiding unnecessary micromanagement of capable agents.

## Mental Model

    Intent
      ↓
    Constraints
      ↓
    Success Criteria
      ↓
    Evidence
      ↓
    Verification
      ↓
    Completion Claim

## Hands-On Experiments

### Experiment A — Activity Prompt

Prompt:

    Fix the failing pricing test.

Observations:

- Files inspected:
- Files changed:
- Policy consulted:
- Verification performed:
- Agent completion claim:

### Experiment B — Procedural Prompt

Observations:

- Files inspected:
- Files changed:
- Policy consulted:
- Verification performed:
- Agent completion claim:

### Experiment C — Outcome Contract

Observations:

- Strategy selected by agent:
- Evidence gathered:
- Files changed:
- Verification performed:
- Agent completion claim:

### Experiment D — Partial Verification

Targeted pricing verification:

Full-suite verification:

Unrelated failures:

Agent completion claim:

Was the claim supported by available evidence?

## Comparison

| Dimension | Activity | Procedural | Outcome Contract |
|---|---|---|---|
| Goal clarity | | | |
| Agent autonomy | | | |
| Verification clarity | | | |
| Risk of wrong interpretation | | | |
| Developer micromanagement | | | |

## Key Findings

Complete after experiments.

## Reflection

### 1. Why can "all tests pass" still be insufficient evidence?

...

### 2. Why can a failing full suite still be insufficient evidence that the requested task failed?

...

### 3. Which should normally be more stable: procedure or success criteria?

...

### 4. What did the agent decide itself in Experiment C that the prompt prescribed in Experiment B?

...

### 5. Where should a truly machine-enforceable constraint live?

...

## Completion Artifact

`prompts/task-contract.md`

## Key Principle

> Verification is evidence supporting a completion claim,
> not a ceremonial command at the end of a task.