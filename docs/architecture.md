# Architecture

This TypeScript learning lab targets Node.js 22 or newer.

- `src/pricing/pricing.ts` calculates totals according to `pricing-rules.md`,
  without I/O or input mutation.
- `src/notifications/email.ts` formats messages; callers handle delivery.
- `src/system-info.ts` is the original standalone system-information script.
- `tests/pricing.test.ts` uses Node's built-in test runner.
- `learning/` contains starter exercises for days 1–3, based on the requested
  titles rather than the unavailable linked conversation.

TypeScript compiles source and tests into `dist/`, preserving directories.
`npm start` runs `dist/src/system-info.js`; `npm test` runs the compiled tests.
There are no runtime dependencies, external services, or databases.
