
# Day 26 — Immutable Recovery Generations & Crash Consistency

Status: In progress

## Objective

Preserve the last committed checkpoint generation
when a newer generation is only partially persisted.

## Official Resources

- https://docs.python.org/3/library/os.html#os.replace
- https://docs.python.org/3/library/os.html#os.fsync
- https://docs.python.org/3/library/tempfile.html
- https://git-scm.com/docs/git-update-ref
- https://docs.pytest.org/en/stable/how-to/monkeypatch.html

## Implementation

Created:
- agent/recovery_generations.py
- tests/test_recovery_generations.py

Existing modules reused:
- agent/recovery_manifest.py
- agent/run_recovery.py
- agent/checkpoint.py
- agent/working_memory.py
- agent/evidence_archive.py

## Invariants

1. Never overwrite a committed generation.
2. Write all artifacts before publishing CURRENT.
3. Validate the new generation before publication.
4. CURRENT changes through atomic replacement.
5. Incomplete generations must not replace CURRENT.
6. A corrupt CURRENT generation blocks recovery.
7. Never silently fall back for automatic model replay.
8. Generation validation does not authorize execution.

## Test Results

Generation tests:
Manifest tests:
Full pytest suite:

## Reflection

1. What is the difference between a manifest and a
   generation commit pointer?

2. Why can a failed publish still result in a
   successfully committed generation?

3. Why should recovery not automatically select an
   older generation when CURRENT is corrupt?

4. What happens if two processes publish concurrently?

5. Why does preserving checkpoint data not guarantee
   exactly-once model or tool execution?

## Remaining Risks

- No concurrent-writer lock or compare-and-swap.
- No garbage collection of abandoned generations.
- No authenticated checkpoint storage.
- No atomic snapshot of concurrently changing sources.
- No automatic recovery of provider conversation state.
- No replay authorization.
- Generation publishing is not yet wired into run_agent.

## Design Decision

Describe the safest next step for integrating immutable
generations into the running agent without permitting
duplicate model calls or tool side effects.
