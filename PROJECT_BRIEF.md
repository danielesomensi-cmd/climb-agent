# climb-agent — Project Brief

> Last updated: 2026-02-19 (Phase 2 complete)
> Detailed source of truth: `docs/DESIGN_GOAL_MACROCICLO_v1.1.md`

---

## What it is

Climbing training planning engine. Deterministic (same inputs → same outputs), closed-loop (feedback → adaptation), no LLM in the decision loop.

Answers the question: **"Given my goal, my weaknesses, and my available time, what should I do today?"**

---

## Current state

| Area | Count | Notes |
|------|-------|-------|
| Exercises | 103 | 12 categories + cooldown stretches + active flexibility |
| Sessions | 33 | gym evening (enriched), home lunch, recovery, flexibility, prehab, conditioning, finger maintenance, core standalone, test (repeater, weighted pullup), easy_climbing_deload |
| Templates | 19 | 11 original + 8 new (warmup, pulling, antagonist, core, cooldown) |
| Tests | ~360 | all green (post Phase 2) |
| user_state | v1.5 | goal, assessment (6 axes + repeater test), trips, macrocycle |
| API endpoints | 26 | 12 routers + health (FastAPI, CORS for Next.js) |
| Frontend pages | 19 | 5 main views + 12 onboarding steps + root + onboarding index |

---

## Architecture: the full flow

```
Assessment (6 dimensions → radar profile 0-100)
  → Goal (lead_grade v1, target + deadline)
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

## Repo structure

```
backend/
  engine/
    assessment_v1.py       ← 6-axis profile (0-100) with grade-based benchmarks
    macrocycle_v1.py        ← Hörst 4-3-2-1 + DUP + deload generator
    planner_v1.py           ← Original weekly planner (mode-based)
    planner_v2.py           ← Phase-aware planner (uses macrocycle)
    resolve_session.py      ← Session resolver → concrete exercises
    progression_v1.py       ← Load progression
    replanner_v1.py         ← Replanning (day override + ripple)
    closed_loop_v1.py       ← Closed-loop feedback processing
    adaptation/             ← Closed-loop (multiplier-based adjustments)
  api/
    main.py                 ← FastAPI app (12 routers + health)
    models.py               ← Pydantic request/response models
    deps.py                 ← Shared dependencies (state loading, date helpers)
    routers/
      state.py              ← GET/PUT/DELETE /api/state
      catalog.py            ← GET /api/catalog/exercises, /api/catalog/sessions
      onboarding.py         ← GET /api/onboarding/defaults, POST /api/onboarding/complete
      assessment.py         ← POST /api/assessment/compute
      macrocycle.py         ← POST /api/macrocycle/generate
      week.py               ← GET /api/week/{week_num} (auto-resolves sessions)
      session.py            ← POST /api/session/resolve
      replanner.py          ← POST /api/replanner/override, /events, /quick-add + GET /suggest-sessions
      feedback.py           ← POST /api/feedback
      outdoor.py            ← GET/POST/DELETE /api/outdoor/spots, POST /log, GET /sessions, /stats, POST /convert-slot
      reports.py            ← GET /api/reports/weekly, /monthly
      quotes.py             ← GET /api/quotes/daily
  catalog/
    exercises/v1/           ← 103 exercises (JSON)
    sessions/v1/            ← 33 sessions (JSON)
    templates/v1/           ← 19 templates (JSON)
  data/
    user_state.json         ← User source of truth (v1.5)
    schemas/                ← JSON schemas for log validation
  tests/                    ← ~362 pytest tests
frontend/
  src/
    app/
      layout.tsx            ← Root layout (lang="en", dark mode)
      page.tsx              ← Entry point (redirects to /today or /onboarding)
      (main)/               ← Authenticated pages (with bottom nav)
        today/page.tsx      ← Today's sessions with mark done/skipped
        week/page.tsx       ← Weekly grid + day detail cards
        plan/page.tsx       ← Macrocycle timeline + radar chart
        session/[id]/       ← Session detail with resolved exercises
        settings/page.tsx   ← Profile, goal, equipment, actions
      onboarding/           ← 12-step onboarding wizard
        welcome → profile → experience → grades → goals →
        weaknesses → tests → limitations → locations →
        availability → trips → review (generates plan)
    components/
      layout/               ← TopBar, BottomNav, DarkModeToggle
      onboarding/           ← OnboardingContext, RadarChart, StepIndicator
      training/             ← DayCard, SessionCard, ExerciseCard, WeekGrid,
                              MacrocycleTimeline, FeedbackDialog
    lib/
      api.ts                ← API client (25 endpoint functions)
      types.ts              ← TypeScript interfaces
      hooks/use-state.ts    ← useUserState hook
docs/
  vocabulary_v1.md          ← Closed vocabulary (updated §5.1-5.6)
  DESIGN_GOAL_MACROCICLO_v1.1.md ← Complete design (the "why")
  ROADMAP_v2.md             ← Consolidated roadmap + backlog + audit (authoritative)
  audit_post_fix.md         ← Historic: post-fix audit results
  e2e_test_results.md       ← Historic: E2E test findings
_archive/                   ← Legacy scripts, docs, config (do not modify)
PROJECT_BRIEF.md            ← This file
CLAUDE.md                   ← Context for Claude Code
```

---

## Approved technical decisions

| Decision | Choice |
|----------|--------|
| Persistence | JSON/JSONL (no database) |
| Frontend | Next.js 14 + React + Tailwind CSS + shadcn/ui (PWA mobile-first) |
| Assessment | Every 6 weeks, benchmarks by target grade |
| Periodization | Hörst 4-3-2-1 with DUP concurrent training |
| Deload | Mixed: programmed + adaptive + pre-trip |
| Outdoor logging | Integrated in day view |
| Feedback | Granular per exercise (5 levels: very_easy → very_hard) |
| LLM Coach | Claude Sonnet as conversational layer (Phase 3.5) |
| Equipment | `equipment_required` only for essential gear, optional in notes |
| Guided Session Mode | Timer UI with colored rest timer (spec in design doc, Phase 4) |

---

## Non-negotiable principles

1. **Total determinism**: same inputs → same outputs, zero random
2. **user_state.json** is the user source of truth (no parallel files)
3. **Append-only logs**, invalid entries quarantined, never deleted
4. **Official maxes** updated ONLY from explicit test sessions
5. **Closed vocabulary** (`docs/vocabulary_v1.md`) — no new values without update
6. **P0 hard filters** in the resolver are not changed without explicit request

---

## Commands

```bash
# Backend tests (~360 green)
source .venv/bin/activate && python -m pytest backend/tests -q

# API dev server (exclude data dir from reload)
uvicorn backend.api.main:app --reload --reload-exclude "backend/data/*" --port 8000

# Frontend dev server
cd frontend && npm run dev

# Import convention
from backend.engine.X import Y
```

---

## Roadmap

> Dettagli completi: `docs/ROADMAP_v2.md`

| Phase | Status | Highlights |
|-------|--------|------------|
| 0: Catalog | ✅ | 102 exercises, 29 sessions |
| 1: Macrocycle engine | ✅ | assessment, macrocycle, planner_v2 |
| 1.5: Post-E2E fixes | ✅ | 14 findings, 13 resolved, 155→188 tests |
| 3: UI (Next.js PWA) | ✅ | 15 endpoints, 19 pages, mobile-first dark PWA |
| 3.1: Bug fixes | ✅ | B21-B24, B9, B26 |
| 1.75: Session enrichment + fix | ✅ | B8 enrichment, B4 load score, NEW-F3a test scheduling, NEW-F4 ripple fix, F6 projecting intent. NEW-F1 → Phase 2.5. |
| UI test fixes (Batch 1-2) | ✅ | 22 bugs fixed, 3 FRs implemented, planner slot/location/dedup/gym-priority |
| **3.2: UI polish + adaptive** | ✅ | B25 adaptive replanning, B19 quick-add, B20 edit availability, B27 equipment labels, NEW-F6/F7. B11 → Phase 2.5 |
| 2: Tracking + outdoor | ✅ | Outdoor logging, reports, motivational quotes |
| 2.5: Catalog audit + loads | 🔲 | Exercise audit vs literature, UI-18 working loads, B11 test protocols, UI-9, UI-20 |
| 3.5: LLM Coach | 🔲 | Claude Sonnet conversational layer |
| 4: Evolution | 🔲 | Multi-goal, annual report, notifications |

---

## How we work

- **Claude Code (Mac terminal)**: implementation, files, commit, push
- **Claude.ai (chat)**: planning, discussion, review
- Each phase → update this file + all tests green
