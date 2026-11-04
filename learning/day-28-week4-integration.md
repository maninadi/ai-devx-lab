
# Day 28 — Week 4 Integration & Recovery Review

Status: In progress

## Objective

Validate recovery consistency across working memory,
evidence archives, repository manifests, and immutable
checkpoint generations.

## Resources

- https://docs.pytest.org/en/stable/how-to/fixtures.html
- https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- https://docs.python.org/3/library/os.html#os.replace
- https://git-scm.com/docs/git-status

## Integration Tests

- Valid committed checkpoint:
- Crash before pointer publication:
- Crash after pointer publication:
- Corrupted CURRENT:
- Repository revision drift:
- Ambiguous model request:

## Test Results

Recovery suite:
Full pytest suite:

## Architecture Review

What is durable:
What is integrity-checked:
What is still advisory:
What blocks recovery:
What could cause duplicate execution:

## Remaining Gaps

1. Concurrent writer ownership and ordering
2. Provider request replay reconciliation
3. Side-effecting tool idempotency
4. Crash testing beyond Python fault injection
5. Dependency and environment revision pinning

## Reflection

1. Which invariant is the most important?
2. Why is a valid generation not automatically
   a safe point for model execution?
3. What would need to change before allowing
   automatic recovery in production?

## Week 4 Outcome

Summarize what the agent can safely recover,
what it can only audit, and what remains unsafe.
