# AI-Native DevX Engineering Lab

A cumulative lab for understanding and building developer-facing
AI agent systems.

## Core Principles So Far

1. Agent quality ≠ model quality.

2. Give the agent a map, not the entire manual.

3. Prompts guide behavior; controls enforce boundaries.

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
