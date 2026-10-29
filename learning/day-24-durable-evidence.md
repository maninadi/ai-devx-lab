
# Day 24 — Durable Evidence Restoration & Repository Consistency

Date: 2026-10-28
Status: In progress

## Objective

Preserve all verified evidence metadata across interruptions,
detect changes in observed source files, and reconstruct the
complete evidence ledger at a safe recovery boundary.

## Official Resources

- https://docs.python.org/3/library/hashlib.html
- https://git-scm.com/book/en/v2/Git-Internals-Git-Objects
- https://docs.python.org/3/library/os.html#os.replace
- https://docs.pytest.org/en/stable/how-to/tmp_path.html
- https://developers.openai.com/api/docs/guides/compaction

## Repository Baseline

Branch: main
Commit: f0d984550d88e0b4be5c01d1fd1662ce770e6dcf

## Implementation

Created:
- agent/evidence_archive.py
- tests/test_evidence_archive.py

Modified:
- agent/loop.py
- agent/context_reconstruction.py

## Recovery Invariants

1. Archive, capsule, and snapshot boundaries must agree.
2. Every original evidence observation must be preserved.
3. Compact working-memory metadata must reconcile with
   the complete archive.
4. Observed source files must match saved fingerprints.
5. Exact source excerpts must still match saved digests.
6. Missing, stale, or inconsistent archives block recovery.
7. Local evidence restoration does not authorize model execution.

## Test Results

Evidence archive tests:
Context reconstruction tests:
Week 3 integration tests:
Complete pytest suite:

## Reflection

1. Why do we need both excerpt hashes and whole-file hashes?
2. Why is a Git commit ID insufficient for validating
   an uncommitted working tree?
3. Why must an archive preserve duplicate observations?
4. What happens if a crash occurs between archive and
   run-snapshot persistence?
5. What additional state is required before safe
   automatic model continuation?

## Remaining Risks

- Unobserved files are not fingerprinted.
- Repository changes can race with validation.
- Checkpoint files are not authenticated.
- Multi-file checkpoint writes are not transactional.
- Provider conversation and literal fact index are not restored.

## Design Decision

Explain whether the next recovery milestone should prioritize:
- Repository revision pinning
- Transactional checkpoint manifests
- Literal fact-index restoration
- Provider conversation reconstruction

Justify the choice.
