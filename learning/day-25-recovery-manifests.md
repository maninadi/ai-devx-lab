
# Day 25 — Repository Revision Pinning & Recovery Manifests

Date: 2026-10-29
Status: In progress

## Objective

Bind a completed tool-batch recovery boundary to
a repository revision and a consistent set of
durable checkpoint artifacts.

## Official Reading

- https://git-scm.com/docs/git-rev-parse
- https://git-scm.com/docs/git-status
- https://docs.python.org/3/library/os.html#os.replace
- https://docs.python.org/3/library/tempfile.html
- https://docs.python.org/3/library/hashlib.html
- https://developers.openai.com/api/docs/guides/conversation-state

## Repository Baseline

Commit: dfe22c031ef5882449d271698507b63c84402b75

## Implementation

Created:
- agent/recovery_manifest.py
- tests/test_recovery_manifest.py

Modified:
- agent/loop.py
- agent/context_reconstruction.py

## Recovery Invariants

1. A manifest is sealed only after all four artifacts exist.
2. Artifact digests must match exactly.
3. Run, response, and turn identifiers must agree.
4. Git HEAD must match the saved revision when available.
5. Eligible working-tree contents must match the saved fingerprint.
6. Missing or partially updated generations block recovery.
7. Manifest validation never authorizes model continuation.

## Test Results

Manifest tests:
Evidence archive tests:
Context reconstruction tests:
Full test suite:

## Reflection

1. Why is Git HEAD alone insufficient for revision pinning?
2. Why must the manifest be written last?
3. What happens if the process crashes after the run snapshot
   is updated but before the manifest is sealed?
4. Why is a manifest digest not a security signature?
5. Why can a valid manifest still be unsafe for automatic
   model continuation?

## Remaining Risks

- No multi-file atomic transaction.
- No authenticated checkpoints.
- No concurrency lock.
- No complete provider conversation restoration.
- Bounded repository source fingerprint.
- Repository state may change after validation.

## Design Decision

Would you prioritize a generation-based immutable
checkpoint directory, a recovery lock, or provider
conversation reconstruction next?

Explain the trade-off.
