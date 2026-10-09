# Day 6 — Verification, Evidence, and Agent Termination

**Date:** 2026-10-07
**Status:** Complete
**Phase:** Coding Agent Foundations

## Objective

Understand the difference between an agent's completion
claim and independently observable verification evidence.

## Study Resources

1. OpenAI — Harness engineering
   - Focus: Feedback loops, environment observability,
     and agent validation.
   - Key takeaway:

2. Anthropic — Demystifying evals for AI agents
   - Focus: Outcome evaluation and agent behavior.
   - Key takeaway:

## Mental Model

Agent action
    ↓
Tool observation
    ↓
Structured verification result
    ↓
Completion evaluation
    ↓
Evidence-backed completion claim

## Experiment A — Verification Runner

Pricing result:

Full-suite result:

Completion verdict:

## Experiment B — Partial Verification

Pricing result:

Full-suite result:

Completion verdict:

What could the verifier legitimately claim?

## Experiment C — Test Coverage

Why could the original promotional test pass
while the implementation was incorrect?

What additional behaviors did the new tests verify?

## Key Findings

...

## Reflection

...

## Completion Artifacts

- src/ai_devx_lab/agent/verification.py
- scripts/verify.py
- tests/test_verification.py
- learning/day-06-verification.md

## Key Principle

A model's completion claim is not verification evidence.

Verification must be based on observable results and
must preserve uncertainty when evidence is incomplete.