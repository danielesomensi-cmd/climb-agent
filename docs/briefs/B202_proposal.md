# B202 — Fix fail-open subscription check

**Severity:** P0 (launch-blocker)
**Scope:** Change `check_subscription()` to fail-closed when Stripe is configured + STORAGE_BACKEND=supabase. Missing row → `status="none", can_interact=false`. Frontend `use-subscription.ts` error fallback → `canInteract=false`.
**Pre-conditions:** Create complimentary `subscriptions` rows for existing beta testers BEFORE deploying, otherwise they lose access instantly.
