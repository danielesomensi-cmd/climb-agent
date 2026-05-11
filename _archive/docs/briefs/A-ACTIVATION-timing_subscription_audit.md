# A-ACTIVATION-TIMING — Day 1 subscription gate audit

**Date:** 2026-04-17
**Scope:** read-only. No code changes. Purpose: map how the subscription
gate actually behaves across the 5 key states and identify the specific
bug observed by Daniele on 2026-04-17.

---

## 1. Gate architecture (code references)

### Backend

- **`backend/engine/subscription_guard.py`**
  - L120: `_ACTIVE_STATUSES = {"trialing", "active"}` — the only statuses that grant access.
  - L154–155: dev bypass — when `STRIPE_SECRET_KEY` is empty OR `STORAGE_BACKEND != "supabase"` → `ALLOW_ALL`.
  - L158–159: founder/beta bypass — `BYPASS_USER_IDS` env list → `ALLOW_ALL`.
  - L162–163: fail-closed — if Stripe is live and no subscription row exists → `DENY_ALL`.
  - L186–188: `can_interact = (status in {"trialing", "active"})`.

- **`backend/api/routers/subscription.py`**
  - L99–104: B212 short-circuit — `/checkout` returns `already_active=true` when the user is already `trialing/active`. Prevents re-checkout from wiping a live trial.
  - L155: **`upsert_subscription(user_id, {"status": "pending_checkout"})`** — writes `pending_checkout` immediately after creating the Stripe Checkout Session, BEFORE the user actually completes payment. This is where the "Pending" label comes from.

- **`backend/api/routers/onboarding.py`**
  - L403–426: `POST /api/onboarding/start-week` is unprotected (no subscription guard dep). Anyone who reached this state can call it.

### Frontend

- **`frontend/src/lib/hooks/use-subscription.ts`**
  - Exposes `canInteract: data.can_interact` (backend-driven).
  - Fail-closed on fetch error (B202): network failure → `canInteract=false`.
  - 5-minute refresh interval (value is slightly stale between refreshes).

- **`frontend/src/app/(main)/today/page.tsx`**
  - L356, L381, L994: `if (!canInteract) { router.push("/subscribe"); return; }` — coherent guard.

- **`frontend/src/app/(guided)/guided/[date]/[sessionId]/page.tsx`**
  - L67–74: `useSubscription` + redirect on `!canInteract` — coherent guard.

- **`frontend/src/app/(main)/settings/page.tsx`**
  - L762–763: renders `"Pending"` label when `subStatus === "pending_checkout"`.
  - L774: Subscribe button → `/subscribe` (explicit user action, not a guard).

- **`frontend/src/app/onboarding/start-week/page.tsx`**
  - L72 (Continue): `router.push("/subscribe")` — **unconditional, no `canInteract` check**.
  - L74 (error path): same unconditional push.
  - L111 (Skip button): same unconditional push.
  - **No import of `useSubscription`. No gate at all.**

- **`frontend/src/components/layout/trial-banner.tsx`**
  - L39, L55: explicit Subscribe CTAs inside the banner (user-initiated, not a guard).

---

## 2. Behavioural matrix (actual vs expected)

| # | User state | `status` value | Expected behaviour | Actual behaviour | Bug? |
|---|-----------|----------------|--------------------|------------------|------|
| 1 | Fresh signup, never touched Stripe | no row (returns `none`) | Redirect to `/subscribe` | `/subscribe` via multiple paths ✓ | — |
| 2 | Clicked Subscribe → created Checkout Session → abandoned Stripe | `pending_checkout` (our own marker) | Redirect to `/subscribe`, allow retry | `/subscribe` ✓ (canInteract=false) — BUT Settings shows "Pending" which is confusing | Soft bug (UX copy) |
| 3 | Completed Checkout, trial active | `trialing` | Full app access, NO /subscribe redirect | Today/Guided/Session routes: ✅ pass. **`/onboarding/start-week` still redirects to `/subscribe`** | ❌ **Hard bug** |
| 4 | Paid past trial | `active` | Full app access | Today/Guided/Session: ✅ pass. Start-week: same unconditional redirect → would re-route them mid-onboarding | ❌ **Same bug** |
| 5 | Canceled | `canceled` | Redirect to `/subscribe` for reactivation | ✓ — canInteract=false | — |

---

## 3. Daniele's 2026-04-17 reproduction trace

### Sequence observed

1. Review page → "Start training now" → `handleGenerate` → `completeOnboarding(data)` → `router.push("/onboarding/start-week")`.
2. Start-week page → user clicks Continue (or Skip) → **`router.push("/subscribe")` unconditional** (`start-week/page.tsx:72,74,111`). No subscription status was ever checked.
3. User lands on `/subscribe` → Clicks "Start Free Trial" → `POST /api/subscription/checkout` → creates Stripe Checkout Session → backend writes `{"status": "pending_checkout"}` (`subscription.py:155`) → returns `checkout_url` → frontend redirects to Stripe.
4. User opens Settings (maybe before clicking) → sees **"Pending"** (rendered by the `pending_checkout` branch in `settings/page.tsx:762`).
5. User clicks a session → `today/page.tsx:356/381` → `canInteract` is false (`pending_checkout` ∉ `_ACTIVE_STATUSES`) → redirect to `/subscribe` → creates NEW checkout session (existing `pending_checkout` row is not active so B212 short-circuit at `subscription.py:99` does not fire) → Stripe Checkout.
6. User cancels from Stripe side → returns to app with `pending_checkout` unchanged (no webhook signals anything; `checkout.session.completed` only fires on success).
7. Eventually user completes checkout → webhook sets status to `trialing` → canInteract becomes true → session click succeeds. The "succeeds somehow" is the normal post-payment path.

### Root causes identified

- **RC-1 (hard):** `/onboarding/start-week/page.tsx` pushes to `/subscribe` regardless of subscription status. A user who is already `trialing` and re-enters the onboarding flow (e.g. via browser back, or by running the review flow again after recovery) is trapped on `/subscribe` instead of `/today`. Same for any currently-active subscriber. **This is the screenshot case.**
- **RC-2 (soft):** The status label `"Pending"` (for internal `pending_checkout`) implies to the user "Stripe is processing something", when it actually means "you clicked Subscribe but never completed". A clearer label + a "Retry checkout" prompt would remove the confusion. Scope-tagged for a follow-up brief.
- **RC-3 (architectural, out of scope):** `pending_checkout` is written speculatively on `/checkout`. If the user abandons Stripe, there is no TTL or cleanup, so the row lingers until the user retries and completes (or admin deletes). Also out of scope.

---

## 4. Proposed minimal fix (Day 2 scope only)

### Fix A — start-week gate coherence (mandatory for Day 2)

File: `frontend/src/app/onboarding/start-week/page.tsx`

Change: import `useSubscription`. After `setStartWeek` succeeds (or on Skip), route based on subscription status:

```ts
import { useSubscription } from "@/lib/hooks/use-subscription";
...
const { canInteract, loading: subLoading } = useSubscription();
...
const goNext = () => {
  if (subLoading) return;                 // wait for status
  if (canInteract) router.push("/today"); // trialing/active → straight to training
  else router.push("/subscribe");         // none/canceled/pending → paywall
};
```

Apply to all three push sites (Continue success, Continue error, Skip).

No backend changes needed.

### Decision required — what to do about `pending_checkout`

Daniele's explicit question: "Pending/incomplete — pass or redirect?"

Options:

1. **Keep current behavior: `pending_checkout` → redirect to `/subscribe`.** Safe, matches dev intent (user hasn't paid). Downside: user never lands on Today until they complete Stripe. No UX harm for first-time users; mildly annoying for "came back after abandoning Stripe" users.
2. **Grant grace access** (`pending_checkout` → `can_interact=True` for N hours). Dangerous — allows unpaid usage. Rejected by the fail-closed B202 rule.
3. **Add a proactive "finish your checkout" banner on Today** when `status == "pending_checkout"`. User can interact or retry from one place. More work than Day 2 scope allows.

**Recommendation:** Option 1 for Day 2. Keeps gate coherent, zero new code paths, zero risk. Leave Option 3 as a parked UX improvement (log in `docs/briefs/A-ACTIVATION-timing_parked.md` if needed).

### Out of Day 2 scope (confirm with Daniele)

- Do NOT change `_ACTIVE_STATUSES` definition.
- Do NOT redesign the Stripe flow.
- Do NOT add new subscription states.
- Do NOT change the "Pending" copy in Settings (follow-up brief).
- Do NOT add TTL cleanup for stale `pending_checkout` rows (follow-up brief).

---

## 5. Call-site audit — every place that redirects to `/subscribe`

From `grep router\.push\(.?/subscribe` in `frontend/src`:

| Path | Line | Guard present? | Status after fix |
|------|------|----------------|------------------|
| `components/layout/trial-banner.tsx` | 39 | User-initiated click | ✅ keep (intentional) |
| `components/layout/trial-banner.tsx` | 55 | User-initiated click | ✅ keep (intentional) |
| `app/onboarding/start-week/page.tsx` | 72 | **none** | ❌ add gate (Day 2) |
| `app/onboarding/start-week/page.tsx` | 74 | **none** | ❌ add gate (Day 2) |
| `app/onboarding/start-week/page.tsx` | 111 | **none** | ❌ add gate (Day 2) |
| `app/(main)/today/page.tsx` | 356 | `if (!canInteract)` ✅ | — |
| `app/(main)/today/page.tsx` | 381 | `if (!canInteract)` ✅ | — |
| `app/(main)/today/page.tsx` | 994 | `if (!canInteract)` ✅ | — |
| `app/(main)/settings/page.tsx` | 774 | User-initiated click | ✅ keep (intentional) |

Only the three `start-week` lines are broken. The audit is complete.

---

## 6. Test matrix for Day 2 (backend-side + frontend-side, 10 cases)

| # | Case | Path | Expected |
|---|------|------|----------|
| 1 | Fresh signup, status=none, click Continue on start-week | start-week → subscribe | `/subscribe` |
| 2 | Fresh signup, status=none, click Skip on start-week | start-week → subscribe | `/subscribe` |
| 3 | Trialing user enters start-week (browser back), click Continue | start-week → today | **`/today`** (fix) |
| 4 | Active user enters start-week, click Continue | start-week → today | **`/today`** (fix) |
| 5 | Canceled user enters start-week | start-week → subscribe | `/subscribe` |
| 6 | pending_checkout user enters start-week | start-week → subscribe | `/subscribe` |
| 7 | Trialing user on Today clicks session | today → guided | `/guided/...` |
| 8 | Canceled user on Today clicks session | today → subscribe | `/subscribe` |
| 9 | Trialing user on Settings | settings status row | "Trial (Nd left)" |
| 10 | pending_checkout user Settings | settings status row | "Pending" (unchanged label; separate brief) |

---

## 7. STOP — waiting for Daniele

Before Day 2 I need confirmation on:

1. **Option 1 vs 3 for `pending_checkout`.** Recommendation: Option 1 (redirect).
2. **Is the fix limited to `start-week/page.tsx`?** Audit says yes.
3. **Is the Settings "Pending" label acceptable for now?** Recommendation: yes, separate brief.
