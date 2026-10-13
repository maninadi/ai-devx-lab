# AI-Native DevX Engineering Lab

A cumulative lab for understanding and building developer-facing
AI agent systems.

## Core Principles So Far

1. Agent quality ≠ model quality.

2. Give the agent a map, not the entire manual.

3. Prompts guide behavior; controls enforce boundaries.

## Learning notes

- [Day 1 — Agent Loop](learning/day-01-agent-loop.md) — ✅ Complete
- [Day 2 — Context Engineering](learning/day-02-context-engineering.md) — ✅ Complete
- [Day 3 — Instruction Architecture](learning/day-03-instruction-architecture.md) — ✅ Complete
- [Day 4 — Prompt Contracts](learning/day-04-prompt-contracts.md) — ✅ Complete
- [Day 5 — Planning and State](learning/day-05-planning-and-state.md) — ✅ Complete
- [Day 6 — Verification](learning/day-06-verification.md) — ✅ Complete
- [Day 7 — Week One Integration](learning/day-07-week-one-integration.md) — ✅ Complete
- [Day 8 — Building Our First Python Agent](learning/day-08-agent-loop.md) — ✅ Complete
- [Day 9 — Model Adapters and Agent State](learning/day-09-model-adapters-and-agent-state.md) — ⏳ Upcoming

See the [curriculum overview](learning/README.md) for the learning log.

## Python setup

Requires Python 3.10 or newer. No dependencies need installing.
Project metadata and the Python requirement are defined in `pyproject.toml`.
Run these commands from the repository root:

```sh
python3 src/system_info.py
python3 -m unittest discover -s tests -v
```

Python code lives in `src/pricing/pricing.py`, `src/notifications/email.py`, and
`src/system_info.py`; tests live in `tests/test_pricing.py`.
See `docs/architecture.md` for the existing pricing-policy discrepancy and the
percentage-based helper added to make the migrated tests runnable.
Historical learning notes retain their original TypeScript examples and commands.
