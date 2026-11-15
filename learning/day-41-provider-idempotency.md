# Day 41 — Provider Idempotency and Correlation

## Objectives

- Distinguish tracing evidence from provider deduplication guarantees.
- Persist correlation before submission and receipts before correlation updates.
- Recover uncertain outcomes without automatically submitting twice.

## Official reading — 25 minutes

| Time | Official resource | Study focus |
| --- | --- | --- |
| 8 min | [Responses API reference](https://developers.openai.com/api/reference/python/resources/responses) | Response IDs, creation, retrieval and response lifecycle |
| 7 min | [OpenAI production best practices](https://platform.openai.com/docs/guides/production-best-practices) | Request IDs, timeout behavior and production diagnostics |
| 5 min | [OpenAI Python SDK retries](https://github.com/openai/openai-python#retries) | Automatic retries and `max_retries=0` |
| 5 min | [Python fsync](https://docs.python.org/3/library/os.html#os.fsync) | Persisting correlation evidence before network calls |

Companion reference: [API request debugging](https://developers.openai.com/api/reference/overview#debugging-requests)
documents the distinction between server request IDs and client-supplied request IDs.
The reading times are a study plan, not a record of time spent.

## Three identifier types

| Identifier | Assigned by | Purpose | What it does not prove |
| --- | --- | --- | --- |
| Client request ID (`X-Client-Request-Id`) | Our application; persisted before submission | Correlate a request with local evidence and assist provider investigation when a response is lost | Acceptance, completion, or deduplication |
| Provider request ID (`x-request-id`, exposed as SDK `_request_id`) | Provider, for an API request | Diagnose a particular API request | A retrievable response object or permission to replay |
| Provider response ID (`response.id`) | Provider, for a response resource | Identify a candidate for `responses.retrieve(response_id)` and subsequent validation | Successful business completion or permanent retrieval availability |

Our local `operation_id` links identity, journal, and correlation files; it is
separate from these three API identifiers. A fencing token is a local ownership
epoch, not a provider identifier. The current correlation record stores the
client request ID and response ID; it does not capture the server request ID.

## Implementation notes

- `agent/provider_correlation.py` persists the operation/client ID mapping and
  later the response ID. Writes flush and fsync the temporary file, atomically
  replace the destination, and fsync the directory. Trusted storage with reliable
  local filesystem semantics is required.
- `agent/admitted_generation_factory.py` prepares correlation under fencing before
  invoking the gateway. Existing correlation is reused for investigation, not as
  authorization to submit again.
- `agent/correlated_generation_gateway.py` injects `X-Client-Request-Id`, rejects
  a conflicting supplied value, and wraps the durable gateway. It reads the ID
  from `response`, preserves `(response, decision)`, and updates correlation
  through `fencing.guarded()` when fencing and token are supplied.
- `agent/provider_token_counter.py` accepts `extra_headers` as a generation
  option but excludes it from the token-count payload. Unknown fields remain
  rejected under the adapter's explicit allowlist policy.
- Day 40 admission validates ownership and run/generation identity and persists
  submission intent before generation. The durable gateway validates response
  metadata and persists a receipt before the outer correlation update.
- `DeadlineAwareGateway` gives each SDK stage the remaining deadline and sets
  `max_retries=0`. The official SDK otherwise retries selected failures by
  default; hidden retries would weaken our control over submission attempts.
- Recovery follows `agent/provider_outcome_policy.py` and the Day 40 admission
  rule: inspect a known response; reconcile an ambiguous submission; reject
  another admission for an operation with an existing journal record.

The observed generation order is:

```text
fencing validation
→ durable submission intent
→ provider call
→ durable response receipt
→ fencing validation
→ correlation update
```

Correlation preparation and token preflight precede this sequence. The second
fencing check protects the correlation write. The local lock is not held across
the provider call and cannot revoke an already admitted remote request.

## Tests

`tests/test_provider_correlation.py` covers correlation surviving restart,
duplicate preparation rejection, persisted response IDs, outcome decisions,
gateway receipt recording, and a provider timeout leaving correlation without
a response ID.

The parameterized integration test
`test_correlated_gateway_order_and_receipt_recovery` in
`tests/test_submission_admission.py` reuses the Day 40 admission setup and its
existing `FakeClient`, `payload`, and `FakeClock` helpers. It runs twice:

1. Success: wrappers call the real persistence methods, reopen stores to check
   disk-visible state, check the outgoing client request ID, and assert the exact
   event order plus one generation call.
2. Crash: an injected `BaseException` interrupts execution after receipt
   persistence but before correlation is written. Fresh store objects find the
   completed receipt. Outcome policy selects `INSPECT_RESPONSE`. A new fencing
   owner and client rebuild the gateway; admission rejects another submission,
   the new client makes zero generation calls, and the receipt remains intact.

This verifies receipt discovery and replay prevention. It does not implement
automatic correlation repair or provider retrieval. CURRENT is mocked; no live
provider, subprocess termination, or hardware power-loss test is performed.

Regression command:

```bash
.venv/bin/python -m pytest -q
```

Executed against the current working tree: **262 passed, 11 subtests passed**.
This includes the existing Day 41 implementation changes and the integration
test edits in `tests/test_submission_admission.py`.

## Failure cases

| Failure | Safe interpretation |
| --- | --- |
| Timeout with submission intent | Outcome unknown; do not replay automatically |
| Provider response ID recorded | Candidate for retrieval and validation |
| Correlation ID exists, no receipt | Useful for investigation; insufficient for replay |
| Response receipt exists, correlation update missing | Reconcile from receipt; no second submission |
| Stale fencing token | Reject new local work |

## Crash matrix

These implications follow from the write order. Only the receipt-to-correlation
gap is explicitly crash-injected by the new integration test.

| Crash boundary | Durable evidence | Safe recovery |
| --- | --- | --- |
| Before correlation preparation finishes | Correlation may be absent or incomplete | Validate storage and ownership; do not infer acceptance |
| Correlation prepared, no submission intent | Client request ID only | Investigate; correlation alone does not authorize replay |
| Intent persisted, before provider call | Intent and client request ID | Restart cannot distinguish this from a lost response; block automatic replay |
| During provider call or timeout | Intent; response receipt absent | Outcome unknown; reconcile with provider evidence |
| Provider returned, receipt not durable | Intent; response ID may exist only in memory | Reconcile; a failed receipt write does not make retry safe |
| Receipt durable, correlation update missing | Response ID and status in journal | Use receipt as the recovery source; no second submission |
| Correlation update durable, caller has not received result | Receipt and correlation response ID | Inspect existing response; do not generate again |
| Ownership changes before a guarded action | Existing evidence remains; token is stale | Reject new local work; an in-flight provider call may still complete |

## Design decision record: Why client request IDs are not idempotency keys.

**Status:** Accepted for the current integration.

**Context:** A timeout can hide whether generation was accepted. A stable client
request ID helps connect local evidence to provider diagnostics. The official
request-debugging documentation describes tracing and support lookup; it does
not establish a deduplication contract for that header.

**Decision:** Treat client request IDs as correlation evidence. Do not infer
idempotency from the name or reuse of the header. Persist intent before submission
and a receipt before correlation updates; require reconciliation after ambiguous
outcomes. A provider response ID enables attempted retrieval, subject to storage,
retention and access, followed by identity, status and output validation.

**Consequences:** Local fencing and journals prevent the tested automatic replay
path, but cannot guarantee exactly-once provider execution. Stronger retry safety
would require an explicit provider contract covering atomic deduplication,
payload conflicts, key scope, retention, and lookup after a lost response.
Automatic receipt-based correlation repair and provider retrieval remain future
work. Optional fencing must be configured with both coordinator and token;
the current wrapper's partial-configuration fallback is not a substitute for
ownership validation.
