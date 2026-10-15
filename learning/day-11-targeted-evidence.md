
# Day 11 — Targeted File Reading and Evidence Selection

**Date:** 2026-10-15
**Status:** Complete after verification

## Objective
Replace broad file reading with targeted repository search
and line-range evidence collection.

## Official Reading
- https://developers.openai.com/api/docs/guides/function-calling
- https://docs.python.org/3/library/pathlib.html
- https://docs.python.org/3/library/re.html

## Implementation
- search_repository
- read_file_range
- Tool dispatcher integration
- OpenAI function schemas
- Evidence-focused agent instructions

## Experiment
Developer question:

Search queries generated:

Files discovered:

Line ranges inspected:

Was the answer properly grounded?

Did context truncation occur?

## Test Results
Evidence tests:
Full pytest suite:
Real OpenAI execution:

## Architectural Decisions
1. Why use discovery before inspection?
2. Why return line numbers?
3. Why limit the number of matches?
4. Why validate paths in Python rather than trusting the model?
5. What does a limited search result tell us about completeness?

## Remaining Limitations
- No semantic search
- No symbol-aware indexing
- No cross-file dependency analysis
- No durable evidence store
- No guarantee of exhaustive repository search

## Reflection
What improved compared with Day 10?
What still makes evidence collection unreliable?
```

Commit after verification:

```bash
git add src/ai_devx_lab/agent tests learning
git commit -m "day-11: add targeted repository evidence tools"
```

## Done when

- [ ] Read the three official documentation resources.
- [ ] Implement `search_repository` with line-numbered results.
- [ ] Implement `read_file_range` with bounded excerpts.
- [ ] Validate paths and reject hidden files and symlinks.
- [ ] Register both tools with OpenAI.
- [ ] Preserve Day 10 context budgeting and Day 9 tracing.
- [ ] Pass all evidence tests and the full pytest suite.
- [ ] Run a real repository investigation.
- [ ] Verify the final answer cites relevant file paths and lines.
- [ ] Complete `learning/day-11-targeted-evidence.md` and commit.

---

### Next: Day 12 — Evidence Tracking and Claim Verification

Tomorrow we'll tackle a deeper problem: **How can the harness verify that the agent's claims are actually supported by the evidence it collected?**

We'll begin implementing an application-owned evidence ledger that tracks source paths, line ranges, and supporting observations, then connects those records to the final answer.

For now, **10 of 168 lessons are complete**. Day 11 will be marked complete when you confirm the implementation and tests are finished.
