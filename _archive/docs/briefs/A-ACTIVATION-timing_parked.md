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

## 4. `/week?date=X` scroll-to-date parameter

**Context:** Day 3 hero "Preview first session" CTA for pre-start users
navigates to `/week?date=<first_session_date>`. Inspection of
`frontend/src/app/(main)/week/page.tsx` shows the page does NOT read
`?date=` — it always renders `weekNum=0` (the current/first macrocycle
week).

**Day 4 decision:** PARKED, not needed. For pre-start users the
macrocycle's Week 1 IS the week of the first session, so the default
`weekNum=0` view already shows the first session in the grid without
any scroll. The `?date=` param is harmless (ignored) but the link works
as intended.

**Future consideration:** if we ever support navigating to arbitrary
dates from the hero (e.g. a "mid-cycle pre-start" scenario), wire
`useSearchParams()` in `/week/page.tsx` to derive `weekNum` from the
ISO date. Low priority — no current UX need.

## 5. `/dev/today-states` flash of "Not available"

**Symptom:** On first paint the dev page briefly shows nothing
(`allowed === null`), then either renders the harness or "Not
available." The gate runs in `useEffect`, so there's a one-frame flash
on Vercel preview.

**Day 3 decision:** Accepted. The dev page is not user-facing; a
one-frame flash during Vercel preview QA is not worth hardening. If we
later need a true server-side block, add a check in
`frontend/src/middleware.ts` (or `proxy.ts` — B-NEXT16 rename) to
redirect `/dev/*` on production hostname.

## 6. `/guided` preview mode for pre-start users

**Context:** The pre-start hero offers "Preview first session" which
links to `/week?date=…`. There is currently no way for a pre-start
user to open the guided-session flow in "preview/read-only" mode — the
guided session page assumes `status = planned` and expects to mutate
state.

**Parked.** Not a regression (pre-Day-3 users had no preview either),
but a pre-start user might reasonably want to click through the full
guided flow to set expectations. Would require a `?preview=true` flag
that disables all writes + a visual "Preview" banner. Future A-class
brief if user feedback surfaces the need.

## 7. Email infra for retrofit / onboarding nudges

**Context:** Day 4 brief originally considered emailing the 2 retrofit
users ("your plan has been shifted"). Deferred because climb-agent
has no transactional email infrastructure today (no SendGrid, no
Clerk-templated emails for custom events, no cron runner).

**Parked.** If we ever add in-app notifications or email infra, the
retrofit script could be extended to emit a notification event. Until
then, the retrofit is silent — acceptable for a 2-user one-shot. For
any future retrofit touching >10 users, build notification infra
first.

## 8. `diagnose_dropoff.py` latency metrics

**Context:** `scripts/diagnose_dropoff.py` currently reports stage
drop-off counts but not time-to-first-session distribution or median
gap between onboarding and first completed session. Would help
validate that A-ACTIVATION-TIMING actually reduced the gap (not just
the count).

**Parked.** Post-retrofit, re-run `diagnose_dropoff.py` after ≥20
post-Stripe users to get a new baseline. If the drop-off stays high,
add latency metrics (onboarding_completed_at → first
session_completion_log entry). Not worth building before the baseline
exists.
