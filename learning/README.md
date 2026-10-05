# AI-Native DevX Engineering Curriculum

A 24-week / 168-day hands-on curriculum for moving from using AI
developer tools to designing and building AI-native developer platforms
and coding-agent systems.

The curriculum is cumulative. Concepts developed during earlier days
are progressively incorporated into the `ai-devx-lab` platform.

## Progress

**Current curriculum day:** Day 4  
**Completed:** 3 / 168  
**In progress:** Day 4  
**Current phase:** Coding Agent Foundations

Day 4 study is complete. Hands-on work continues next session.

---

## Curriculum Phases

| Days | Phase |
|---|---|
| 1–28 | Coding-agent internals, context engineering, prompting, reusable skills/instructions, task decomposition, verification and workflows |
| 29–49 | Model/API fundamentals, structured outputs, streaming, context/state and model behavior |
| 50–70 | Tool calling, permissions, MCP servers/clients and enterprise integrations |
| 71–91 | Retrieval/RAG and grounded developer knowledge |
| 92–119 | Agent loops, orchestration, automation, approvals and workflow design |
| 120–140 | Evals, observability, security, reliability, cost and production operations |
| 141–168 | DevX capstone |

---

# Learning Log

## Phase 1 — Coding Agent Foundations

| Day | Topic | Key Concept | Artifact | Status |
|---|---|---|---|---|
| 1 | Coding Agent Architecture | Agent quality ≠ model quality | [Day 1](day-01-agent-loop.md) | ✅ Complete |
| 2 | Context Engineering | Available information ≠ active context | [Day 2](day-02-context-engineering.md) | ✅ Complete |
| 3 | Instruction Architecture | Authority, scope and relevance | [Day 3](day-03-instruction-architecture.md) | ✅ Complete |
| 4 | Prompt Contracts | Define observable success and evidence | [Day 4](day-04-prompt-contracts.md) | 🟡 Study complete |
| 5 | Task Decomposition & Planning | — | — | ⏳ Upcoming |

---

# Mental Model

The architecture being developed throughout the curriculum:

    Developer
        │
        ↓
    Task / Intent
        │
        ↓
    Instruction System
        │
        ↓
    Context Construction
        │
        ↓
       Model
        │
        ↓
    Action Request
        │
        ↓
      Harness
        │
        ↓
    Policy / Permissions
        │
        ↓
       Tools
        │
        ↓
    Environment
        │
        ↓
    Observation
        │
        └──────────→ Model

This model will evolve as prompt contracts, skills, retrieval, MCP,
state, orchestration, evals and observability are introduced.

---

# Principles Learned

## Day 1 — Coding Agent Architecture

> **Agent quality ≠ model quality.**

The model is one component of an agent system. Harness behavior,
tools, context, environment and verification all affect overall
agent quality.

## Day 2 — Context Engineering

> **Give the agent a map, not the entire manual.**

Relevant information should be discoverable rather than permanently
placed into every inference.

## Day 3 — Instruction Architecture

> **Specificity ≠ authority.**

Instruction scope determines where an instruction applies, not
necessarily whether it may override another instruction.

> **Prompts guide behavior; controls enforce boundaries.**

Critical capability and security boundaries should ultimately be
enforced by the system.

---

# Platform Evolution

Current conceptual components:

    ai-devx-lab/
    │
    ├── AGENTS.md
    │     └── instruction architecture
    │
    ├── docs/
    │     └── authoritative knowledge
    │
    ├── learning/
    │     └── experiments and architectural understanding
    │
    ├── prompts/
    │     └── reusable task contracts
    │
    ├── src/
    │     └── implementation / agent environment
    │
    └── tests/
          └── machine-verifiable evidence

---

# Architecture Decisions

## ADR-001 — Keep domain truth outside agent instructions

Business and domain facts belong in authoritative documentation or
systems of record.

Agent instructions should primarily tell agents how to locate and use
that information.

## ADR-002 — Layer instructions by scope

Repository-wide invariants belong at the root.

Subsystem-specific instructions specialize those rules close to the
relevant implementation.

## ADR-003 — Separate guidance from enforcement

Prompts and instructions guide model behavior.

Security, permissions and critical capability boundaries should be
enforced by the harness or execution environment.

## ADR-004 — Treat retrieved content as data

Documentation, tool results and externally retrieved content can inform
reasoning but should not automatically acquire instruction authority.

---

# Current Work

## Day 4 — Prompt Contracts

**Status:** 🟡 Study complete; hands-on pending.

Next session begins directly with the Day 4 experiments:

    Activity prompt
          vs
    Procedural prompt
          vs
    Outcome contract

The goal is to understand:

    Intent
       ↓
    Constraints
       ↓
    Success criteria
       ↓
    Evidence
       ↓
    Verification
       ↓
    Definition of done