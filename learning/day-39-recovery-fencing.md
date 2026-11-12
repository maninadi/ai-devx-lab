# Day 39 — Local Recovery Generation Fencing

## Official resources

- [Python fcntl](https://docs.python.org/3/library/fcntl.html): Unix file locking.
- [Python os.replace](https://docs.python.org/3/library/os.html#os.replace): atomic pointer replacement.
- [Python os.fsync](https://docs.python.org/3/library/os.html#os.fsync): flushing ownership metadata.
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html): controlled failures and replacement of test dependencies.

## Architecture

`GenerationFencing` uses an exclusive `flock()` on a shared, stable
`FENCE.lock` file. `claim()` increments the persisted ownership token.
It writes a temporary state file, flushes and fsyncs it, replaces
`FENCE.json`, then syncs the containing directory.

`guarded()` validates the token and holds the same lock throughout the
protected local action. A claim cannot interleave between validation and
publication. Atomic replacement of CURRENT alone provides no ownership
check; a lease alone cannot prevent a paused worker from resuming after
its ownership expires.

The Day 26 invariants still apply: validate artifacts before publishing,
preserve committed generations, and replace CURRENT atomically.

## Code changes

- `agent/generation_fencing.py`: durable token claims, validation, and guarded actions.
- `agent/fenced_generation_publisher.py`: guarded wrapper around the existing publication API.
- `tests/test_generation_fencing.py`: token, restart, corruption, stale-action, and real-generation checks.

The original `GenerationStore.publish()` signature remains unchanged.
The wrapper does not integrate fencing into gateway construction or
external request admission.

## Test results

Executed using the existing virtual environment:

```text
.venv/bin/python -m pytest -q tests/test_generation_fencing.py -v
8 passed

.venv/bin/python -m pytest -q tests/test_generation_fencing.py tests/test_recovery_generations.py tests/test_attempt_reconciliation.py
22 passed

.venv/bin/python -m pytest -q
247 passed, 11 subtests passed
```

The integration test reuses Day 26's `generation_setup` and its real
recovery artifacts. Token 1 publishes G1; claiming token 2 invalidates
token 1. A stale publication raises `FencingBlocked`, leaves CURRENT's
bytes unchanged, and still resolves to G1. Token 2 then publishes a
distinct G2, which CURRENT resolves to successfully. Fencing state lives
under the checkpoint directory to preserve the fixture's repository pin.

## Race scenarios

1. A publishes G1 with token 1. B claims token 2. A resumes and tries to
   publish: validation rejects A before publication; B can publish G2.
2. A starts a guarded publication while current. B's claim must wait
   until A releases the lock. B can then claim the next token.
3. A checks ownership, releases the lock, then pauses. B claims ownership
   before A's next action. A's earlier check cannot authorize that action.

The integration test deterministically checks scenario 1 in sequence.
The current tests do not exercise simultaneous processes or prove lock
blocking under contention; scenario 2 describes the implementation's
locking boundary.

## Limitations

- `flock()` is advisory: all writers must use the same coordinator.
  Direct calls to `GenerationStore.publish()` bypass fencing.
- Scope is cooperating processes on one host with reliable local
  filesystem locking, rename, and fsync semantics. Network filesystem
  guarantees require separate validation. This is a teaching implementation,
  not a production-ready distributed coordination service.
- Provision the trusted fencing directory durably before starting workers.
  Never delete or reset the token state or replace the lock file during
  normal operation. Missing state currently initializes the epoch at zero,
  so deleting persisted state can allow token reuse.
- No guarantee of exactly-once provider calls, cancellation of requests
  already submitted, or an atomic boundary between gateway generation
  selection and provider submission. Do not hold the filesystem lock
  across an external API call.

## Quiz score

Not assessed; no quiz answers have been graded.

## Reflection

**Why is a token check before an external API call insufficient to
guarantee the worker remains current?**

The worker can pause after the check and another worker can claim a newer
token before the request reaches the provider. The provider does not
participate in the local lock or enforce its tokens. Local ownership
checks cannot undo submitted requests. Provider-supported idempotency,
where available, can address duplicate operations, but does not itself
prove current ownership; submission admission and outcome reconciliation
need a separate design.

**What additional protection would be required across multiple machines?**

A shared, strongly consistent coordinator must issue durable monotonic
epochs, and the protected storage must atomically reject stale epochs
when committing writes, for example through a transaction or conditional
update. A distributed lease without enforcement at the resource still
allows stale writes. External effects additionally require provider-side
deduplication or idempotency where supported, plus durable operation
identity and reconciliation for uncertain outcomes.
