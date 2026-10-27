
# Day 23 — Context Reconstruction & Safe Compaction Boundaries

Date: 2026-10-27
Status: In progress

## Objective

Reconstruct a validated local evidence index and observation
counter at a safe recovery boundary without automatically
resuming model execution.

## Official Resources

- https://developers.openai.com/api/docs/guides/conversation-state
- https://developers.openai.com/api/docs/guides/compaction
- https://docs.python.org/3/library/hashlib.html
- https://docs.pytest.org/en/stable/how-to/tmp_path.html

## Repository Baseline

Branch: main
Commit: 9683cc5d82663d352baf33ad5607d7cfb4bc584f

## Implementation

Created:
- agent/context_reconstruction.py
- tests/test_context_reconstruction.py

Modified:
- agent/loop.py
- tests/test_week3_integration.py

## Recovery Invariants

1. Snapshot and checkpoint must match.
2. No ambiguous model request can be replayed.
3. Memory capsule identity must match the snapshot.
4. Saved context policy must match the expected policy.
5. No omitted evidence is accepted for full reconstruction.
6. Source ranges must still be readable.
7. SHA-256 digests must match.
8. Local validation never authorizes automatic model continuation.

## Test Results

Context reconstruction tests:
Week 3 integration tests:
Full pytest suite:

## Limitations

- Local checkpoints are not authenticated.
- The repository is not locked during validation.
- The original provider conversation is not restored.
- Literal fact-index state is not restored.
- Only retained evidence references can be reconstructed.
- Full model token accounting remains unavailable.
- Multi-file checkpoint updates are not transactional.

## Reflection

1. Why must source content be re-read during recovery?
2. Why does matching a digest not prove semantic correctness?
3. Why should omitted evidence block full reconstruction?
4. Why does a successful local audit not authorize model continuation?
5. When is finalization safer than compaction?

## Design Decision

Describe the conditions under which your agent should:
- Continue its current execution
- Request manual compaction review
- Finalize or stop
- Block recovery completely
```

Answer the reflection questions in your own words, then change the artifact's status to `Completed` once the work is verified.

### Step 10 — Commit your changes

```bash
git status --short

git add agent/context_reconstruction.py
git add agent/loop.py
git add tests/test_context_reconstruction.py
git add tests/test_week3_integration.py
git add learning/day-23-context-reconstruction.md

git commit -m "day-23: validate context reconstruction boundaries"
git push origin main
```

---

## Day 23 — Done when

- [ ] Complete the 25-minute official reading.
- [ ] Create `agent/context_reconstruction.py`.
- [ ] Implement the snapshot/checkpoint/capsule identity gate.
- [ ] Revalidate retained evidence using exact source-range SHA-256 digests.
- [ ] Reconstruct the local evidence index and observation counter.
- [ ] Reject missing evidence, stale sources, changed policies, and ambiguous model requests.
- [ ] Add compaction recommendations to the trace without enabling automatic compaction.
- [ ] Pass all seven new tests and the existing integration suite.
- [ ] Pass the complete pytest suite.
- [ ] Complete the Day 23 learning artifact and push the changes.

## Next — Day 24: Durable Evidence Restoration & Repository Consistency

We'll address the limitation exposed today: Day 22's capsule can omit older evidence, so it cannot reliably reconstruct the entire evidence index. Day 24 will focus on preserving complete evidence metadata durably, validating repository consistency, and distinguishing recoverable state from stale or incomplete state.

**Progress: 22/168 completed (13.1%). Day 23 is delivered and remains in progress until you confirm completion.**
