# Day 40 — Submission Admission

## Objectives

- Extend Day 39 fencing to local submission admission.
- Validate ownership and exact run/generation identity before generation.
- Persist submission intent before invoking the provider.
- Distinguish atomic local coordination from uncertain external effects.
- Block repeat admission until the existing attempt is reconciled.

## Official resources

- [Python fcntl.flock](https://docs.python.org/3/library/fcntl.html#fcntl.flock): exclusive Unix file locks.
- [Python os.replace](https://docs.python.org/3/library/os.html#os.replace): atomic file replacement.
- [Python os.fsync](https://docs.python.org/3/library/os.html#os.fsync): flushing durable state.
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html): controlled dependency replacement for tests.

## Architecture

`build_admitted_gateway()` connects the deadline-aware gateway's
`generation_submission_started` callback to `SubmissionAdmission.admit()`.
Token counting happens before this admission boundary.

Admission holds the shared fencing lock while validating the current
ownership token, reading and verifying CURRENT, loading the operation's
immutable identity, comparing its run and generation IDs, and checking
that no attempt record exists. It then durably records submission intent
before releasing the lock. Cooperating claims and fenced publishers
cannot interleave with these checks and the intent write.

After admission returns, the gateway invokes `responses.create()` without
holding the filesystem lock. `DurableGenerationGateway` validates response
metadata and persists a response receipt before returning to its caller.
The Day 37 policy remains: an existing attempt requires reconciliation;
journal inspection alone does not authorize replay.

Atomicity here means serialization of the local admission decision against
cooperating operations. It does not mean rollback of every filesystem
effect on failure, or a transaction spanning local storage and the provider.

## Files changed

- `agent/submission_admission.py`: guarded ownership, generation, identity,
  and prior-attempt checks followed by durable intent publication.
- `agent/admitted_generation_factory.py`: wires admission into the existing
  deadline and durable gateway wrappers.
- `tests/test_submission_admission.py`: valid, stale, changed-generation,
  duplicate, missing-identity, and fake-provider boundary tests.
- `learning/day-40-submission-admission.md`: this study record.

Existing Day 36–39 gateway, journal, identity, and fencing modules are
reused. Their public APIs remain unchanged.

## Test results

Executed using the existing virtual environment:

```text
.venv/bin/python -m pytest -q tests/test_submission_admission.py tests/test_deadline_gateway.py tests/test_generation_attempt_journal.py
20 passed

.venv/bin/python -m pytest -q
253 passed, 11 subtests passed
```

The admission module has six tests. Its fake-provider test reuses the
Day 36 `FakeClock` and Day 37 `FakeClient` and `payload` helpers. A stale
token leaves the journal empty and generation call count at zero. With
the valid token, a fresh journal reader observes `SUBMISSION_INTENT` at
the provider boundary before delegating to the fake provider. A successful
response then produces `RESPONSE_RECEIVED`.

The admission fixture mocks CURRENT; this test does not validate real
generation artifacts. Tests make no live provider requests or power-loss
durability claims.

## Crash matrix

These are recovery implications derived from the write order, not a claim
that every crash point has been fault-injected.

| Crash or failure boundary | Local evidence | Provider outcome | Recovery implication |
| --- | --- | --- | --- |
| Before admission or rejected admission | No new intent | Generation call has not begun through this path | Resolve the rejection; any later attempt must pass fresh admission. |
| During intent persistence | Intent may be absent, visible, or invalid depending on failure point | Generation call has not begun through this path | Inspect and validate storage; propagate failure and do not call the provider. |
| After durable intent, before provider invocation | Submission intent | Request has not yet been sent, but restart cannot infer this from intent alone | Treat as ambiguous and block automatic resubmission. |
| During request or after provider acceptance, before response receipt | Submission intent | Unknown; provider may have completed work | Reconcile externally before considering retry. |
| Response received, before receipt is durably stored | Submission intent, or a receipt whose durability is uncertain | Response existed but may be lost locally | Reconcile; failure to store receipt does not make retry safe. |
| After durable receipt, before returning to caller | Response ID and status | Provider returned the recorded metadata | Inspect the receipt; do not automatically repeat the operation. |

## Known limitations

- Advisory locking protects cooperating local processes using the same
  stable coordinator. Direct publication or submission can bypass it.
- Ownership or CURRENT may change after admission releases the lock and
  before the provider receives the request. Admission does not revoke an
  already admitted request or an in-flight request.
- A generation change does not automatically invalidate an older
  operation's journal; external effects still require reconciliation.
- No provider-side fencing, idempotency integration, automatic provider
  lookup, response-body restoration, or exactly-once guarantee is implemented.
- Keep the lock off network calls. A stalled request must not prevent a
  local ownership claim indefinitely.
- Trusted directories must be provisioned durably. Fencing state and the
  lock file must not be reset or replaced during normal operation.
- Reliable local flock, rename, and fsync semantics are assumed. This is
  not a distributed coordination service or live `run_agent()` integration.
- Tests cover controlled ordering, not simultaneous process contention,
  network partitions, or hardware crash durability.

## Quiz answers

Study answers below are ungraded; no quiz score has been assigned.

1. **What is protected by the lock?** Token validation, current-generation
   verification, identity matching, prior-attempt rejection, and durable
   intent publication form one serialized local admission operation.
2. **Why persist intent before calling the provider?** A crash after
   submission must leave evidence that an external effect may have begun.
   Intent records uncertainty; it does not prove provider acceptance.
3. **Why reject an existing attempt?** It may represent an accepted request
   whose response was lost. Blind resubmission could duplicate work.
4. **Does a valid token guarantee safe retry?** No. Ownership validation
   neither deduplicates provider work nor resolves an earlier unknown result.
5. **Why release the lock before the request?** Network duration is
   uncertain; holding it would block local ownership changes without
   making the provider participate in fencing.

## Reflection

**Why is the local admission operation atomic but the provider request is not?**

All cooperating local ownership changes and fenced publications use the
same lock. Admission holds it across its checks and durable intent write,
so those operations cannot change the relevant state halfway through the
decision. The provider does not participate in that lock or a shared
transaction. After release, another worker can take ownership while the
admitted worker pauses or sends its request. Network failures can also
hide whether a request was accepted. Local serialization therefore cannot
make the remote effect and local receipt commit atomically.

**What would a provider need to support to make safe retry and reconciliation stronger?**

A provider could accept a stable client operation/idempotency key and
atomically deduplicate submissions against it, bind the key to a request
digest, reject conflicting payloads, and return the original operation
for repeated submissions. Its contract would need explicit scope and
retention guarantees covering the recovery window.

Durable lookup by that client key is especially useful when the first
response containing the provider's ID is lost. Authoritative status and
retrievable results would distinguish pending, completed, failed, and
unaccepted work. To reject stale owners as well as duplicates, the provider
would additionally need to enforce monotonic ownership epochs at acceptance
within an agreed resource scope. These are desired capabilities, not
claims about support in the current client or provider. Local recovery
would still need to persist identities and reconcile uncertain outcomes.
