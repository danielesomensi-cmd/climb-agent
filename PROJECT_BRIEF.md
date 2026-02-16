# climb-agent — Project Brief

> Last updated: 2026-02-16 (post Phase 3.1 — bug fixes)
> Detailed source of truth: `docs/DESIGN_GOAL_MACROCICLO_v1.1.md`

---

## What it is

Climbing training planning engine. Deterministic (same inputs → same outputs), closed-loop (feedback → adaptation), no LLM in the decision loop.

Answers the question: **"Given my goal, my weaknesses, and my available time, what should I do today?"**

---

## Current state

| Area | Count | Notes |
|------|-------|-------|
| Exercises | 102 | 12 categories (finger, power, PE, endurance, pull, push, core, prehab, technique, flexibility, handstand, conditioning) |
| Sessions | 29 | gym evening, home lunch, recovery, flexibility, prehab, conditioning, finger maintenance |
| Templates | 11 | unchanged from v1 |
| Tests | 183 | all green (post Phase 3.1) |
| user_state | v1.5 | goal, assessment (6 axes + repeater test), trips, macrocycle |
| API endpoints | 14 | 9 routers + health (FastAPI, CORS for Next.js) |
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
    exercises/v1/           ← 102 exercises (JSON)
    sessions/v1/            ← 29 sessions (JSON)
    templates/v1/           ← 11 templates (JSON)
  data/
    user_state.json         ← User source of truth (v1.5)
    schemas/                ← JSON schemas for log validation
  tests/                    ← 179 pytest tests
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
  DESIGN_GOAL_MACROCICLO_v1.1.md ← Complete design + roadmap
  BACKLOG.md                ← Feature backlog (B1-B24)
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
# Backend tests (183 green)
source .venv/bin/activate && python -m pytest backend/tests -q

# API dev server
uvicorn backend.api.main:app --reload

# Frontend dev server
cd frontend && npm run dev

# Import convention
from backend.engine.X import Y
```

---

## Roadmap

### Phase 0: Catalog ✅
- 102 exercises, 29 sessions, vocabulary updated
- pangullich → campus_board, guided session mode spec

### Phase 1: Macrocycle engine ✅
- assessment_v1.py, macrocycle_v1.py, planner_v2.py
- user_state v1.5 (goal, assessment, trips, macrocycle)

### Phase 1.5: Post-E2E fixes ✅
- 14 findings from manual E2E test, 13 resolved in 2 clusters
- Resolver inline blocks, planner 2-pass, PE with repeater test
- Replanner phase-aware (12 intents), goal validation, real pre-trip deload
- 155 tests green (from 115)

### Phase 1.75: Session enrichment 🔲
- Evening sessions with 5-7 blocks, new templates (pulling, antagonist, limit boulder)
- Core and antagonists standard, load score, literature validation

### Phase 2: Tracking + extras 🔲
- Granular feedback, climbing logging, trip planning
- Motivational quotes, report engine

### Phase 3: UI (Next.js PWA) ✅
- FastAPI REST API: 9 routers, 14 endpoints, CORS for Next.js
- Onboarding wizard: 10-step flow generating assessment + macrocycle
- Main views: Today (mark done/skipped + feedback), Week (grid + detail), Plan (radar + timeline), Session (resolved exercises), Settings (regenerate/reset)
- 6 live-testing fixes: auto-resolve sessions, English translation, 7-day availability, gym priority, preview next day, day click navigation
- 4 usability fixes: gym name display, full prescription format (× @ — Rest mm:ss), date query parameter (?date=), replan dialog with auto-resolve
- Mobile-first with shadcn/ui components, dark mode, PWA manifest

### Phase 3.1: Bug fixes ✅
- B21: Done button keeps session with status "done" (was removing it)
- B22: Events endpoint auto-resolves sessions (was missing `_auto_resolve`)
- B23: Skip sets day status to "skipped" (was staying "planned")
- B24: Gym equipment labels corrected

### Phase 3.2: UI polish + outdoor + equipment 🔲
- B9: Add cable_machine, leg_press to gym equipment
- B10: Outdoor climbing spots as location type
- B11: Configurable test protocols
- B19: Quick-add session from week view
- B20: Edit availability from Settings

### Phase 3.5: LLM Coach 🔲
- Claude Sonnet conversational layer on top of deterministic engine

### Phase 4: Evolution 🔲
- More goal types, annual report, multi-macrocycle, notifications

---

## How we work

- **Claude Code (Mac terminal)**: implementation, files, commit, push
- **Claude.ai (chat)**: planning, discussion, review
- Each phase → update this file + all tests green
