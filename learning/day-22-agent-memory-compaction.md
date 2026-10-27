# Day 22 — Agent Memory & Context Compaction

Date: 2026-10-26
Status: In progress

## Objective
Build bounded, provenance-aware working memory
for long-running repository investigations.

## Official Reading
- https://developers.openai.com/api/docs/guides/conversation-state
- https://developers.openai.com/api/docs/guides/compaction
- https://developers.openai.com/api/docs/guides/token-counting
- https://docs.pytest.org/en/stable/how-to/tmp_path.html

## Architecture
Explain the difference between:
- Provider conversation state
- Tool observation character budget
- Authoritative evidence ledger
- Bounded working-memory capsule

## Changes
Created:
- agent/working_memory.py
- tests/test_working_memory.py

Modified:
- agent/loop.py
- tests/test_week3_integration.py

## Test Results
Working memory:
Week 3 integration:
Full pytest suite:

## Important Limitations
- No provider-side context reduction yet
- No full evidence restoration from capsule
- No reset of context budget after compaction
- No semantic validation of source claims
- No atomic multi-file recovery transaction
- No automatic long-running model continuation

## Reflection
1. Why can't the evidence ledger be replaced
   with a short model-generated summary?

2. Why is a character budget different from
   a model token budget?

3. What information must survive compaction?

4. Why must omitted evidence remain
   distinguishable from verified evidence?

5. When should an agent finalize rather than
   attempt further context compaction?
