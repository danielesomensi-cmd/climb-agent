# climb-agent — Project Brief

> Counters auto-updated by `python scripts/sync_status.py`
> For full technical reference, see `CLAUDE.md`
> Open items: `docs/ROADMAP_CURRENT.md`
> Full history: `docs/ROADMAP_v2.md` (archived)

---

## What it is

Climbing training planning engine. Deterministic (same inputs → same outputs), closed-loop (feedback → adaptation), no LLM in the decision loop. Answers the question: **"Given my goal, my weaknesses, and my available time, what should I do today?"**

---

## Current status

<!-- STATUS_TABLE_START -->
| Metric | Count |
|--------|-------|
| Tests (passing) | 3369 |
| Exercises | 263 |
| Sessions (active) | 35 |
| Templates | 19 |
| API endpoints | 93 |
| Frontend pages | 46 |
| Frontend components | 112 |
<!-- STATUS_TABLE_END -->

**Current phase: personal tool, marketing paused** (decided 2026-08-13, on the evidence of D274). The app stays
live and fully operational at **https://climbagent.app** (canonical domain since A248, 2026-07-21 —
legacy `climb-agent.vercel.app` 308-redirects with query preserved). **Nothing is being switched
off:** Stripe stays LIVE (sk_live keys on Railway + Vercel), the B202 fail-closed subscription
guard stays deployed, and both plans stay purchasable. What stopped is the *acquisition effort*,
not the product. Build for the athlete using it; growth work is out of scope unless Daniele
reopens it.

**Funnel (audit `docs/audit/D274_gtm_cohort_audit.md`, 2026-08-10):** 20 accounts ever, of which
**11 are real external users** (the rest: the author, 3 of his test accounts, 4 beta testers, 1
orphan row). Of those 11 — **11 completed the 12-step wizard and generated a macrocycle, 1 ever
completed a session, 0 reached three, 0 are paying.** The drop is **−91% at "macrocycle generated
→ first session"**; the last session completed by a non-author was **2026-04-21**. **Lifetime net
revenue: −€0.47** — the only payment ever taken ($4.99, 2026-06-14) was refunded four hours later
by a user with zero completed sessions, and Stripe kept the fee. Reddit is exhausted (banned from
r/climbharder, 2026-08-08). Cause analysis of the activation gap: `docs/audit/D273_first_session_activation.md`.

**Reopening condition (`GTM-07`):** one non-author user completing **3 sessions within 14 days**.
It has never happened. Check monthly with `python scripts/gtm_funnel.py` — no other GTM work is
scheduled.

**Persistence:** Supabase JSONB live in production (6 tables: users, session_logs, outdoor_logs, event_logs, recovery_codes, subscriptions). RLS enabled on all 6 tables (no policies, service role key bypasses).

**Pricing (live, not promoted):** USD $9.99/month Standard (15-day free trial) + USD $4.99/month Founding Climber (locked forever, first 20 users). Stripe LIVE.

- Pricing tax_behavior: **exclusive** (net prices, VAT added at Stripe Tax activation). Decision date: 2026-04-28. Locked-in for consistency at future Stripe Tax activation.

---

## Architecture: the full flow

```
Assessment (5 dimensions → radar profile 0-100)
  → Goal (lead_grade or boulder_grade, target + deadline)
  → Macrocycle (Hörst 4-3-2-1 + DUP, 11–16 weeks lead / 8–16 weeks boulder, 5 phases)
  → Week (planner_v2 phase-aware, domain weights + session pool)
  → Session (resolver selects concrete exercises with loads)
  → Feedback (granular per exercise, plan vs actual)
  → Adaptation (closed-loop, multiplier-based)
```

In code:

```
compute_assessment_profile()    [assessment_v1]
→ generate_macrocycle()         [macrocycle_v1]
→ generate_phase_week()         [planner_v2, per week]
→ resolve_session()             [resolve_session, per session]
```

---

## Tech stack and decisions

| Decision | Choice |
|----------|--------|
| Runtime logic | Pure Python, deterministic, no LLM |
| Persistence | Supabase Postgres + JSONB (production), JSON files (dev/test) |
| Auth | Clerk (Next.js native + backend verification) |
| Frontend | Next.js 16 + React + Tailwind CSS + shadcn/ui (PWA mobile-first, Turbopack) |
| Periodization | Hörst 4-3-2-1 with DUP concurrent training |
| Assessment | 5-axis profile, benchmarks by target grade, periodic retesting |
| Deload | Mixed: programmed + adaptive + pre-trip |
| Feedback | Granular per exercise (5 levels: very_easy → very_hard) |
| Equipment | `equipment_required` for essential gear only, optional in notes |
| Payments | Stripe LIVE since 2026-04-16, sk_live keys on Railway + Vercel |
| App store | Capacitor wrapping PWA (planned) |
| LLM Coach | Claude Sonnet conversational layer (planned, Phase 3.5) |

---

## Completed phases

| Phase | Highlights |
|-------|------------|
| 0: Catalog | Exercise + session + template JSON catalogs |
| 1: Macrocycle engine | Assessment, macrocycle, planner_v2 |
| 1.5: Post-E2E fixes | 14 findings resolved |
| 1.75: Session enrichment | Load scores, test scheduling, ripple fix |
| 2: Tracking + outdoor | Outdoor logging, reports, motivational quotes |
| 2.5: Catalog audit | Exercise enrichment, grade_ref, working loads |
| 3: UI (Next.js PWA) | Mobile-first dark PWA, 14 routers |
| 3.1-3.2: Bug fixes + polish | 22+ bugs fixed, adaptive replanning, quick-add, equipment |
| 4a: Multi-user + deploy | UUID multi-user, Railway/Vercel deploy |
| 4b: Guided session + beta | Step-by-step session mode, settings editors, dirty-state |
