# Architecture

This Python learning lab requires Python 3.10 or newer and has no third-party dependencies.

- `src/pricing/pricing.py` contains pure pricing helpers.
- `src/notifications/email.py` formats typed dictionaries; callers handle delivery.
- `src/system_info.py` prints host information. Memory and uptime use Linux `/proc`;
  those fields display `unavailable` on unsupported systems.
- `tests/test_pricing.py` uses the standard-library `unittest` runner.

Run `python3 -m unittest discover -s tests -v` from the repository root.
There is no compilation step, database, or external service.

## Existing pricing discrepancy

The tier policy in `pricing-rules.md` specifies standard 0%, silver 5%, gold 15%.
The migrated `calculate_discount` preserves the original implementation: gold 10%,
all other tiers 0%. Its regression test verifies migration parity, not policy compliance.

The original tests referenced an absent `calculatePrice` function. The migration
adds `calculate_price` to support their percentage-based contract: integer cents,
positive quantities, safe integer arithmetic bounded by 2**53 - 1, and a finite
0–100% discount rounded once with positive half-up rounding.
This separate helper does not implement customer-tier policy.
