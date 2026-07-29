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
| Tests (passing) | 2871 |
| Exercises | 259 |
| Sessions (active) | 35 |
| Templates | 19 |
| API endpoints | 92 |
| Frontend pages | 46 |
| Frontend components | 102 |
<!-- STATUS_TABLE_END -->

**Current phase:** Paid launch prep. Production live at **https://climbagent.app** (canonical domain since A248, 2026-07-21 — legacy `climb-agent.vercel.app` 308-redirects with query preserved). Stripe LIVE (sk_live keys on Railway + Vercel). B202 fail-closed subscription guard deployed. Founding Climber ($4.99/mo) and Standard ($9.99/mo) plans active. 4 beta testers (Christie, Cesar, Paolo, Agustin) — will need to subscribe after B202.

**Persistence:** Supabase JSONB live in production (6 tables: users, session_logs, outdoor_logs, event_logs, recovery_codes, subscriptions). RLS enabled on all 6 tables (no policies, service role key bypasses).

**Pricing at launch:** USD $9.99/month Standard (15-day free trial) + USD $4.99/month Founding Climber (locked forever, first 20 users). Stripe LIVE.

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
