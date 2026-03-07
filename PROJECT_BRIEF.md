# climb-agent — Project Brief

> Counters auto-updated by `python scripts/sync_status.py`
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
| Tests (passing) | 799 |
| Exercises | 153 |
| Sessions (active) | 29 |
| Templates | 23 |
| API endpoints | 37 |
| Frontend pages | 25 |
| Frontend components | 45 |
<!-- STATUS_TABLE_END -->

---

## Architecture: the full flow

```
Assessment (6 dimensions → radar profile 0-100)
  → Goal (lead_grade or boulder_grade, target + deadline)
  → Macrocycle (Hörst 4-3-2-1 + DUP, 10-13 weeks, 5 phases)
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
| Persistence (current) | JSON/JSONL files on Railway persistent volume |
| Persistence (production) | Supabase Postgres (planned) |
| Frontend | Next.js 14 + React + Tailwind CSS + shadcn/ui (PWA mobile-first) |
| Periodization | Hörst 4-3-2-1 with DUP concurrent training |
| Assessment | 6-axis profile, benchmarks by target grade, periodic retesting |
| Deload | Mixed: programmed + adaptive + pre-trip |
| Feedback | Granular per exercise (5 levels: very_easy → very_hard) |
| Equipment | `equipment_required` for essential gear only, optional in notes |
| Multi-user (current) | UUID in localStorage + X-User-ID header |
| Auth (production) | Clerk (planned) |
| Payments | Stripe (planned) |
| App store | Capacitor wrapping PWA (planned) |
| LLM Coach | Claude Sonnet conversational layer (planned, Phase 3.5) |

---

## Repo structure

```
backend/
  engine/              # Core: assessment, macrocycle, planner, resolver, replanner,
                       # progression, closed-loop, adaptation, reports, outdoor, quotes
  api/                 # FastAPI REST API (14 routers)
    routers/           # state, catalog, onboarding, assessment, macrocycle, week,
                       # session, replanner, feedback, outdoor, reports, quotes, user, admin
  catalog/             # JSON data: exercises, sessions, templates (versioned under v1/)
  data/                # user_state.json + JSON schemas for log validation
  tests/               # pytest test suite with fixtures/
frontend/              # Next.js 14 PWA (React, Tailwind, shadcn/ui)
  src/app/             # Pages: main views + onboarding wizard + guided session
  src/components/      # layout, onboarding, training, guided, settings, whats-next, ui
  src/lib/             # api.ts, types.ts, hooks/
docs/                  # Design docs, glossary, roadmap, literature reviews
scripts/               # sync_status.py (auto-update counters)
_archive/              # Legacy scripts, docs, config (do not modify)
```

---

## Deployment

| Service | Platform | URL |
|---------|----------|-----|
| Backend | Railway | https://web-production-fb1e9.up.railway.app |
| Frontend | Vercel | https://climb-agent.vercel.app |

Both auto-deploy on push to main (~2-3 min).

**Environment variables (Railway):**
- `DATA_DIR` — Persistent volume path (`/data/climb-agent`)
- `ADMIN_SECRET` — Key for admin endpoints (never commit)
- `PORT` — Set by Railway (8080, do not override)

---

## Non-negotiable principles

1. **Total determinism**: same inputs → same outputs, zero random
2. **user_state.json** is the user source of truth (no parallel files)
3. **Append-only logs**, invalid entries quarantined, never deleted
4. **Official maxes** updated only from explicit test sessions
5. **Closed vocabulary** (`docs/vocabulary_v1.md`) — no new values without update
6. **P0 hard filters** in the resolver are not changed without explicit request

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
