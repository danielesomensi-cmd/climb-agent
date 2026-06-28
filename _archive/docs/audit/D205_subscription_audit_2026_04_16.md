# D205 — Subscription Status Leak & Webhook Robustness Audit

**Date:** 2026-04-16
**Author:** Claude (Opus 4.6) — read-only audit
**Trigger:** After deleting a Stripe test customer, Settings page still shows "Status: Active"

---

## Executive Summary

- **Root cause confirmed: H3 (fail-open).** `check_subscription()` returns `_ALLOW_ALL` (status="active", can_interact=true) when NO subscription row exists in Supabase. This is by design for onboarding, but creates a **status leak** when a subscription row is deleted (manually or via unhandled webhook).
- **"Manage subscription" button:** fails with 404 because `stripe_customer_id` is NULL/missing after row deletion. The frontend shows a generic error or does nothing visible.
- **`customer.deleted` webhook is NOT handled.** Only 5 of 10 critical event types are implemented. When a customer is deleted from Stripe Dashboard, nothing happens in our DB.
- **B188 beta bypass:** was frontend-only (routing `/plan` instead of `/subscribe`), already reverted in GTM-04. No backend whitelist exists.
- **Launch-blocker:** YES — the fail-open design means any user who cancels (and whose row gets deleted or corrupted) regains full access.

---

## Schema & Code Map

### Supabase: subscription-related tables

**Table: `subscriptions`** (only source of truth for billing state)

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | TEXT PK | Internal UUID, matches `users.id` |
| `stripe_customer_id` | TEXT UNIQUE | Stripe Customer ID (`cus_...`) |
| `stripe_subscription_id` | TEXT | Stripe Subscription ID (`sub_...`) |
| `status` | TEXT | `trialing`, `active`, `past_due`, `canceled`, `expired`, `pending_checkout` |
| `trial_start` | TEXT | ISO-8601 |
| `trial_end` | TEXT | ISO-8601 |
| `current_period_start` | TEXT | ISO-8601 |
| `current_period_end` | TEXT | ISO-8601 |
| `cancel_at_period_end` | BOOL | |

No other table stores subscription/billing state. `user_state` (JSONB in `users` table) does NOT contain subscription fields.

### Backend endpoints touching subscription state

| Endpoint | File | Reads | Writes |
|----------|------|-------|--------|
| `GET /api/subscription/status` | `subscription.py:43` | `subscriptions` | — |
| `POST /api/subscription/checkout` | `subscription.py:65` | `subscriptions` | `subscriptions` (pending_checkout) |
| `POST /api/subscription/portal` | `subscription.py:150` | `subscriptions` | — (clears stale customer_id on error) |
| `POST /api/stripe/webhook` | `stripe_webhook.py:38` | `subscriptions` | `subscriptions` (all status fields) |

### Frontend components reading subscription state

| Component | File | Hook | Gating field | Fail-open? |
|-----------|------|------|-------------|------------|
| Settings page | `settings/page.tsx:63` | `useSubscription()` | `isActive` for display, `subActive` for button | Yes |
| Trial banner | `trial-banner.tsx:7` | `useSubscription()` | `isTrialing`, `status` | Yes (hidden on error) |
| Guided session | `guided/[date]/[sessionId]/page.tsx:70` | `useSubscription()` | `canInteract` | Yes (redirect skipped on error) |
| Today page | `today/page.tsx:87` | `useSubscription()` | `canInteract` | Yes (actions allowed on error) |

---

## Root Cause: "Active" Status Leak

**Confirmed hypothesis: H3 — fail-open on missing subscription row.**

### Trace

1. User `98f77487...` had a `subscriptions` row with `status=trialing` linked to `cus_ULWYZLIpdHSAfA`.
2. Daniele deleted the Stripe customer from Dashboard. Stripe sends `customer.deleted` webhook.
3. **`customer.deleted` is NOT handled** (`stripe_webhook.py:93-94`) — logged as "unhandled event type", returns 200.
4. Daniele manually `DELETE`d the `subscriptions` row in Supabase.
5. `GET /api/subscription/status` calls `check_subscription("98f77487...")`.
6. `check_subscription()` at `subscription_guard.py:139-142`:
   ```python
   row = get_subscription_row(user_id)
   if row is None:
       # No row = not onboarded yet = full access
       return _ALLOW_ALL.copy()
   ```
7. Returns `{"status": "active", "is_active": true, "can_interact": true}`.
8. Frontend `useSubscription()` maps this to `isActive=true`, displays "Active".

### The design flaw

The comment says "No row = not onboarded yet = full access". This was correct during onboarding-only flow, but now that Stripe is live, a missing row can also mean:
- Row was deleted (manual cleanup)
- Row was never created (webhook failure)
- Row was corrupted

All these cases get **full access** instead of being gated.

### Double fail-open

Even if the backend returned an error, the frontend `use-subscription.ts:48-50` catches all errors and returns `_ALLOW` (status="active", canInteract=true). So there are **two independent fail-open layers**.

---

## Root Cause: "Manage Subscription" Button

### Failure mode

After the `subscriptions` row was deleted:

1. Settings page shows `isActive=true` (from fail-open above).
2. "Manage subscription" button is visible (shown when `subActive === true`, `settings/page.tsx:777`).
3. Click calls `createBillingPortal()` → `POST /api/subscription/portal`.
4. Backend at `subscription.py:158-164`:
   ```python
   row = get_subscription_row(user_id)
   customer_id = row.get("stripe_customer_id") if row else None
   if not customer_id:
       raise HTTPException(status_code=404, detail="No active subscription found.")
   ```
5. Returns 404. Frontend `api.ts` throws error. Settings page shows no visible feedback (error not caught in portal handler at `settings/page.tsx:782-789` — only sets loading state, doesn't handle errors visually).

### Expected behavior

When no subscription row exists, "Manage subscription" button should NOT be shown. Instead, "Subscribe" CTA should appear. The bug is that fail-open makes the UI think the user is active.

---

## Webhook Robustness Audit

### Event handling matrix

| Event | Handled? | Handler | Idempotent? | Handles missing obj? | On error | Writes |
|-------|----------|---------|-------------|---------------------|----------|--------|
| `checkout.session.completed` | YES | `stripe_webhook.py:83,106-158` | Yes (upsert) | Yes (fallback chain) | Returns 200 | status, customer_id, sub_id, trial dates |
| `customer.subscription.updated` | YES | `stripe_webhook.py:85,161-195` | Yes (upsert) | Partial | Returns 200 | status, period dates, cancel_at_period_end |
| `customer.subscription.deleted` | YES | `stripe_webhook.py:87,198-217` | Yes (upsert) | Partial | Returns 200 | status="canceled" |
| `invoice.payment_succeeded` | YES | `stripe_webhook.py:89,220-248` | Yes (upsert) | Partial | Returns 200 | status="active", period dates |
| `invoice.payment_failed` | YES | `stripe_webhook.py:91,251-269` | Yes (upsert) | Partial | Returns 200 | status="past_due" |
| `customer.created` | **NO** | — | — | — | Returns 200 (silent) | — |
| `customer.deleted` | **NO** | — | — | — | Returns 200 (silent) | — |
| `customer.updated` | **NO** | — | — | — | Returns 200 (silent) | — |
| `customer.subscription.created` | **NO** | — | — | — | Returns 200 (silent) | — |
| `customer.subscription.trial_will_end` | **NO** | — | — | — | Returns 200 (silent) | — |

### Critical gaps

**Gap 1 — `customer.deleted` not handled (P0).** This is the exact scenario that triggered this audit. When a Stripe customer is deleted (admin action, fraud, Stripe cleanup), our DB retains stale data. Combined with fail-open, this creates a status leak.

**Gap 2 — All errors swallowed with 200 (`stripe_webhook.py:95-98`).** The `except Exception` block catches all errors, logs them, and returns 200. This means Stripe will NOT retry on failure. If a webhook handler crashes (e.g., Supabase down), the event is lost silently.

**Gap 3 — `customer.subscription.created` not handled.** Relies on `checkout.session.completed` to create the row. If checkout webhook fails, the subscription exists in Stripe but not in our DB. Combined with fail-open, user gets access without us knowing they subscribed (can't track trial end, can't enforce cancellation).

---

## B188 Beta Bypass Analysis

**Finding: NO backend bypass exists.**

B188 was a **frontend-only routing change** in `onboarding/start-week/page.tsx`:
- Changed `router.push("/subscribe")` to `router.push("/plan")` in 3 places.
- Reverted in GTM-04 (commit `41adca9`).
- No backend whitelist, no feature flag, no user-id allowlist.

The "Active" status for Daniele is NOT from a beta bypass. It's from the fail-open design in `check_subscription()`.

---

## Proposed Follow-up Briefs

### B202: Fix fail-open subscription check (P0 — launch-blocker)

**Scope:** Change `check_subscription()` to fail-closed when Stripe is configured. When `STRIPE_SECRET_KEY` is set AND `STORAGE_BACKEND=supabase`, a missing subscription row should return `status="none", is_active=false, can_interact=false`. Keep fail-open ONLY for dev/pytest (no Stripe key).

**Frontend counterpart:** `use-subscription.ts` error fallback should return `canInteract=false` (or at minimum, `loading=true` to avoid flash) when the backend is expected to be available.

**Pre-condition:** Must handle existing beta testers (Christie, Cesar, Paolo, Agustin) — they need `subscriptions` rows with `status=active` created before this change ships, otherwise they lose access.

### B203: Handle `customer.deleted` webhook + error retry policy (P1)

**Scope:** Add handler for `customer.deleted` → set `status="canceled"` + clear `stripe_customer_id` and `stripe_subscription_id`. Also: change the generic `except Exception` block to return 500 for unexpected errors (triggers Stripe retry) while keeping 200 for "handled successfully" and known-benign errors.

**Pre-condition:** None. Can ship independently.

### B204: "Manage subscription" button error handling (P2)

**Scope:** Settings page portal button should catch 404 errors and show a user-friendly message ("No subscription found") instead of silently failing. Also: hide "Manage subscription" button when status is "none" or missing.

**Pre-condition:** Depends on B202 (fail-closed) to surface the correct status.

---

## Open Questions for Daniele

1. **Beta testers access:** Before B202 (fail-closed) ships, do you want to create complimentary `subscriptions` rows for Christie/Cesar/Paolo/Agustin? Or keep fail-open until they subscribe?
2. **Stripe Customer Portal:** Is it configured in **live mode** (not just test)? Settings > Billing > Customer portal in Stripe Dashboard.
3. **Error retry policy:** Current design swallows all webhook errors (returns 200). Changing to 500 on unexpected errors means Stripe retries up to ~16 times over 3 days. OK with this?
4. **Your current subscription row:** After the manual DELETE, do you want me to re-create a clean row, or will you re-test checkout from scratch?
