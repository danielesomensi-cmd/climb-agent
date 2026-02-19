# climb-agent — Project Brief

> Last updated: 2026-02-17 (post Phase 1.75 — P1 items closed)
> Detailed source of truth: `docs/DESIGN_GOAL_MACROCICLO_v1.1.md`

---

## What it is

Climbing training planning engine. Deterministic (same inputs → same outputs), closed-loop (feedback → adaptation), no LLM in the decision loop.

Answers the question: **"Given my goal, my weaknesses, and my available time, what should I do today?"**

---

## Current state

| Area | Count | Notes |
|------|-------|-------|
| Exercises | 113 | 12 categories + cooldown stretches + active flexibility |
| Sessions | 32 | gym evening (enriched), home lunch, recovery, flexibility, prehab, conditioning, finger maintenance, core standalone, test (repeater, weighted pullup) |
| Templates | 19 | 11 original + 8 new (warmup, pulling, antagonist, core, cooldown) |
| Tests | 233 | all green (post Phase 1.75 P1 closure + doc audit) |
| user_state | v1.5 | goal, assessment (6 axes + repeater test), trips, macrocycle |
| API endpoints | 15 | 9 routers + health (FastAPI, CORS for Next.js) |
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
    main.py                 ← FastAPI app (9 routers + health)
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
      replanner.py          ← POST /api/replanner/override, /api/replanner/events
      feedback.py           ← POST /api/feedback
  catalog/
    exercises/v1/           ← 113 exercises (JSON)
    sessions/v1/            ← 32 sessions (JSON)
    templates/v1/           ← 19 templates (JSON)
  data/
    user_state.json         ← User source of truth (v1.5)
    schemas/                ← JSON schemas for log validation
  tests/                    ← 233 pytest tests
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
      onboarding/           ← 10-step onboarding wizard
        welcome → profile → experience → grades → goals →
        weaknesses → tests → limitations → locations →
        availability → trips → review (generates plan)
    components/
      layout/               ← TopBar, BottomNav, DarkModeToggle
      onboarding/           ← OnboardingContext, RadarChart, StepIndicator
      training/             ← DayCard, SessionCard, ExerciseCard, WeekGrid,
                              MacrocycleTimeline, FeedbackDialog
    lib/
      api.ts                ← API client (14 endpoint functions)
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
| Guided Session Mode | Timer UI with colored rest timer (spec in design doc, Phase 3) |

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
# Backend tests (233 green)
source .venv/bin/activate && python -m pytest backend/tests -q

# API dev server
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
| **1.75: Session enrichment + fix** | ✅ | B8 enrichment, B4 load score, NEW-F3a test scheduling, NEW-F4 ripple fix, F6 projecting intent. NEW-F1 → Phase 2.5. |
| 3.2: UI polish + adaptive | 🔲 | B25 adaptive replanning, B19/B20 UI features |
| 2: Tracking + outdoor | 🔲 | Outdoor logging, reports, motivational quotes |
| 3.5: LLM Coach | 🔲 | Claude Sonnet conversational layer |
| 4: Evolution | 🔲 | Multi-goal, annual report, notifications |

---

## How we work

- **Claude Code (Mac terminal)**: implementation, files, commit, push
- **Claude.ai (chat)**: planning, discussion, review
- Each phase → update this file + all tests green
