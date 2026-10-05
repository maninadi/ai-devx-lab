# Day 2 — Context Engineering

**Status:** ✅ Complete
**Phase:** Coding Agent Foundations

## Objective

Understand the difference between information available to an agent
system and information actually present in the model's active context.

## Study Resources

1. [Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
   - Provider: OpenAI
   - Focus: Construction of model input from instructions, environment,
     tools, and observations.
   - Key takeaway: Repository information existing does not mean it is
     present in active model context.

2. [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
   - Provider: OpenAI
   - Focus: Repository knowledge and navigational context.
   - Key takeaway: Give agents a map to authoritative information rather
     than loading everything into every inference.

## Mental Model

    Available information
           │
      ┌────┼────┐
      ↓    ↓    ↓
     code docs tools
      └────┼────┘
           ↓
    Context selection
           ↓
      Active context
           ↓
         Model
           ↓
        Action
           ↓
      Observation
           │
           └────→ updated context

## Available Information vs Active Context

**Available information** is everything the agent could potentially
access.

**Active context** is the information supplied to the model for the
current inference.

## Hands-On Experiments

### Experiment A — Minimal context

Provided only:

> The Gold customer discount is incorrect. Fix it and verify the change.

Observed how the agent discovered relevant implementation, tests,
and policy.

### Experiment B — Stuffed context

Explicitly supplied locations, policy information, and relevant facts.

The task became easier, but the developer effectively became the
retrieval system.

### Experiment C — Navigational context

Used `AGENTS.md` to tell the agent where source, tests, and authoritative
business policies lived without copying the business facts themselves
into the instructions.

### Experiment D — Context pollution

Added many plausible but irrelevant instructions and observed whether
important guidance became harder for the agent to follow.

## Key Findings

- Context capacity is not the same as understanding.
- Context selection is an engineering problem.
- Irrelevant context competes with relevant context.
- Domain truth should remain in its authoritative system of record.
- Instructions can teach an agent how to discover information instead
  of containing that information.

## Completion Artifact

Compared minimal, stuffed, and navigational context strategies.

## Key Principle

> **Give the agent a map, not the entire manual.**