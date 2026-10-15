# Day 10 — Context Construction and Tool-Result Management

**Date:** 2026-10-14
**Status:** Complete

## Objective

Introduce an explicit context-management boundary
between tool execution and model consumption.

## Official Reading

1. Conversation State
   https://developers.openai.com/api/docs/guides/conversation-state

2. Function Calling
   https://developers.openai.com/api/docs/guides/function-calling

3. Prompt Caching
   https://developers.openai.com/api/docs/guides/prompt-caching

## Architecture

Explain the difference between:

- Available repository information
- Tool observations
- Model context

## Implementation

New module:
src/ai_devx_lab/agent/context.py

Policy:
- Maximum characters per tool result:
- Maximum cumulative observation characters:

Integration:
- Tool execution
- Context preparation
- Model observation
- Trace metadata

## Experiment

Repository question:

Tools invoked:

Largest raw observation:

Largest prepared observation:

Any truncation:

Final answer quality:

## Testing

Context unit tests:

Agent integration test:

Full pytest suite:

## Limitations

- Character budget versus token budget
- Truncation versus relevance selection
- New observations versus accumulated context
- Sensitive-data handling

## Reflection

1. Why should the harness control tool-result size?
2. Why is truncation metadata necessary?
3. When could truncation make an answer less accurate?
4. Why doesn't a per-result limit solve context growth?
5. How would you design relevance-aware context selection?

## Completion

Day 10 completed.