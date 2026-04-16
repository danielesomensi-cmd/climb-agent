# B203 — Handle `customer.deleted` webhook + error retry policy

**Severity:** P1
**Scope:** Add webhook handler for `customer.deleted` → set status="canceled", clear stripe IDs. Change generic `except Exception` to return 500 on unexpected errors (enables Stripe retry). Keep 200 for handled events.
**Pre-conditions:** None. Can ship independently.
