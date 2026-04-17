# A-ACTIVATION-TIMING — Parked items

Issues surfaced during Phase 1 that are NOT in scope for this brief. Logged
here so they don't get lost; triage at next roadmap planning.

## 1. `pending_checkout` "Pending" label ambiguity (Settings)

**Symptom:** After the 2026-04-17 bug, Daniele's Settings page shows
"Subscription: Pending" because `backend/api/routers/subscription.py:155`
speculatively writes `subscription_status = "pending_checkout"` the moment
`/subscribe/checkout` is called — before Stripe confirms anything.

If the user abandons the Stripe checkout page, that marker persists in
`user_state.json` and Settings keeps displaying "Pending" indefinitely,
which looks like a billing limbo state.

**Day 2 decision:** Not fixed here — the start-week gate fix (Task 21)
prevents paying users from hitting the speculative write in the first place.
But the stale marker problem is a separate UX bug worth addressing.

**Proposed remediation (future brief):**
- Option A: rename the label to "Awaiting Stripe confirmation" when status
  is `pending_checkout` (clearer than "Pending").
- Option B: 24h auto-cleanup — a scheduled job (or a lazy check on
  `/api/subscription/status`) that resets `pending_checkout` → `none` if no
  Stripe webhook event arrived within 24h. Matches Stripe Checkout Session
  default expiry (24h).
- Option C: stop writing `pending_checkout` speculatively — let the webhook
  be the single source of truth. Riskier (silent failures if webhook drops).

Recommend Option B (lightweight, self-healing) bundled with Option A label
fix. Estimated: B-class brief, <1 day.

## 2. Week 1 sparsity UX (soft handling)

**Context:** With Day 2's shift to `this_monday()`, users onboarding late in
the week get a sparse Week 1 (e.g. Fri 23:00 user with 4-day/week
availability → 1–2 sessions in Week 1). The planner is correct (B95 guard
blocks past days), but from the user's POV Week 1 looks "half empty".

**Current mitigation:** Fallback to strict next Monday fires only when
Week 1 would be EXACTLY 0 sessions (T=1 threshold, see simulation §stress).
Users with 1–3 sessions in Week 1 still get the short week.

**Not a bug** — by design, per simulation stress-scenario analysis. But the
UX could be softer. Options considered:
- Copy on `/today` hero: "Week 1 is short because you're starting mid-week
  — next week is your first full week."
- Onboarding review screen already shows `start_date`; could add "Your first
  week will have N sessions" preview.

**Day 2 decision:** Day 3 of this brief adds an empty-state hero CTA on
`/today`. If that hero already covers "no sessions today yet" copy, the
sparsity concern is partially addressed. Re-evaluate after Day 3 ships.
If still a concern, spin off as a B-class UX brief.

## 3. Subscription gate audit — no other unconditional redirects found

**Scope of Day 2 audit:** grep'd `useSubscription` importers across
`frontend/src/`. Result: 4 files import the hook, and all usage sites
already check `canInteract` before routing/enabling paid features. The
only unconditional `router.push("/subscribe")` was in
`onboarding/start-week/page.tsx` (the file we fixed).

**Conclusion:** audit clean. No follow-up needed. Noted here to prevent
re-investigation in a future brief.
