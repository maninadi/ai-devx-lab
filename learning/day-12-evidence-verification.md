# Day 12 — Evidence Tracking and Claim Verification

**Date:** 2026-10-16
**Status:** Complete after verification

## Objective

Build an application-owned evidence ledger
and verify final-answer citation provenance.

## Official Reading

1. OpenAI Function Calling
   https://developers.openai.com/api/docs/guides/function-calling

2. OpenAI Evaluation Best Practices
   https://developers.openai.com/api/docs/guides/evaluation-best-practices

3. Python hashlib
   https://docs.python.org/3/library/hashlib.html

## Architecture

Explain:

- Candidate evidence
- Observed evidence
- Evidence provenance
- Semantic claim verification

## Implementation

New module:
src/ai_devx_lab/agent/evidence_ledger.py

Components:

- Evidence
- EvidenceLedger
- SHA-256 source fingerprinting
- Citation parser
- Provenance checker

## Integration

Describe where evidence is recorded
in the agent execution loop.

Explain why truncated observations
are not accepted as complete evidence.

## Experiment

Developer question:

Files searched:

Line ranges inspected:

Evidence records created:

Claims in final answer:

Claims with valid citation provenance:

Verification warnings:

## Tests

Evidence ledger tests:

Full pytest suite:

Real OpenAI execution:

## Architectural Decisions

1. Why must evidence records originate from tool execution?
2. Why is a model-generated citation insufficient?
3. Why reject truncated observations?
4. What does the SHA-256 fingerprint establish?
5. Why can an incorrect claim pass provenance verification?

## Remaining Limitations

- No semantic entailment checking
- No exhaustive claim extraction
- No file-change detection
- No durable evidence store
- No evidence sufficiency evaluation

## Reflection

What would be required before treating
this verification system as a production
quality gate?
