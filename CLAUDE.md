# CLAUDE.md — climb-agent

## Project context

climb-agent is a deterministic climbing training engine. It generates personalised weekly training plans, resolves abstract sessions into concrete exercises with sets/reps/load, and adapts progression through closed-loop feedback. No LLM is used at runtime — all logic is rule-based and testable.

## Principles

- **Deterministic**: Given the same user state and inputs, output is always the same.
- **Closed-loop**: Every session outcome feeds back into user state for future planning.
- **Data-driven**: Sessions, exercises, and templates are JSON catalogs — logic is separate from data.
- **Test-first**: All engine behaviour is covered by pytest. Tests must pass before merging.

## Key commands

```bash
# Run all tests (188 green)
source .venv/bin/activate && python -m pytest backend/tests -q

# Run a single test file
python -m pytest backend/tests/test_planner_v1.py -q

# Start API dev server (port 8000)
uvicorn backend.api.main:app --reload

# Start frontend dev server (port 3000)
cd frontend && npm run dev

# Type-check (if mypy is installed)
mypy backend/engine/
```

## Repository structure

```
backend/
  engine/            # Core logic: planner, resolver, replanner, progression, closed-loop
    adaptation/      # Closed-loop adaptation (multiplier-based adjustments)
  api/               # FastAPI REST API (9 routers, 15 endpoints)
    main.py          # App setup, CORS, router mounting
    models.py        # Pydantic request/response models
    deps.py          # Shared deps (load_state, save_state, next_monday)
    routers/         # state, catalog, onboarding, assessment, macrocycle, week, session, replanner, feedback
  catalog/           # JSON data: exercises, sessions, templates (versioned under v1/)
  data/              # user_state.json + JSON schemas for log validation
  tests/             # 188 pytest tests with fixtures/
frontend/            # Next.js 14 PWA (React, Tailwind, shadcn/ui)
  src/app/           # 19 pages: 5 main views + 12 onboarding steps + root + index
  src/components/    # layout (TopBar, BottomNav), onboarding (RadarChart), training (DayCard, SessionCard, etc.)
  src/lib/           # api.ts (14 endpoint functions), types.ts, hooks/
docs/                # vocabulary_v1.md, DESIGN_GOAL_MACROCICLO_v1.1.md, BACKLOG.md, e2e_test_results.md
_archive/            # Legacy scripts, docs, config (do not modify)
```

## Import conventions

All Python imports use the `backend.` prefix:

```python
from backend.engine.planner_v1 import generate_week_plan
from backend.engine.resolve_session import resolve_session
```

Data paths are relative to the repo root:

```python
"backend/catalog/sessions/v1/strength_long.json"
"backend/data/user_state.json"
```

## API (Phase 3)

FastAPI app with 9 routers and 15 endpoints + health check.

```bash
# Start
uvicorn backend.api.main:app --reload

# Test
source .venv/bin/activate && python -m pytest backend/tests/test_api.py -q
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/state` | Get full user state |
| PUT | `/api/state` | Deep-merge patch into state |
| DELETE | `/api/state` | Reset state to empty |
| GET | `/api/catalog/exercises` | List all exercises |
| GET | `/api/catalog/sessions` | List all session metadata |
| GET | `/api/onboarding/defaults` | Option lists for onboarding form |
| POST | `/api/onboarding/complete` | Atomic: save state + assessment + macrocycle |
| POST | `/api/assessment/compute` | Recompute 6-axis profile |
| POST | `/api/macrocycle/generate` | Generate new macrocycle |
| GET | `/api/week/{week_num}` | Generate week plan (auto-resolves sessions) |
| POST | `/api/session/resolve` | Resolve a single session to exercises |
| POST | `/api/replanner/override` | Apply day override (intent-based, auto-resolves sessions) |
| POST | `/api/replanner/events` | Apply events (done/skipped) to week plan |
| POST | `/api/feedback` | Submit session feedback |

## Frontend (Phase 3)

Next.js 14 App Router + Tailwind CSS + shadcn/ui. Mobile-first dark-mode PWA.

```bash
cd frontend && npm run dev    # http://localhost:3000
```

### Tech stack
- **Framework**: Next.js 14 (App Router, "use client" for all pages)
- **Styling**: Tailwind CSS + shadcn/ui components
- **State**: React hooks (useUserState, useOnboarding context)
- **API client**: Typed fetch wrapper in `src/lib/api.ts`
- **PWA**: manifest.json + service worker

### Pages
- `/today` — Today's sessions (or any day via `?date=YYYY-MM-DD`), mark done/skipped, post-session feedback
- `/week` — 7-day grid + scrollable day detail cards + "View day" / "Change plan" buttons + replan dialog
- `/plan` — Assessment radar chart + macrocycle timeline + phase details
- `/session/[id]` — Resolved exercises with prescription details
- `/settings` — Profile summary, regenerate assessment/macrocycle, reset
- `/onboarding/*` — 10-step wizard: welcome → profile → experience → grades → goals → weaknesses → tests → limitations → locations → availability → trips → review

## Catalog status (post Phase 0 expansion)

- **Exercises**: 102 in `backend/catalog/exercises/v1/exercises.json`
- **Sessions**: 29 in `backend/catalog/sessions/v1/` (28 original + finger_maintenance_home)
- **Templates**: 11 in `backend/catalog/templates/v1/` (unchanged)

### Exercise categories covered
- Finger strength: max hang, repeaters, long duration, min edge, pinch, density, one-arm
- Power & contact strength: campus (laddering, bumps, dynos), limit bouldering, board bouldering
- Power endurance: 4x4, linked boulders, route intervals, ARC, threshold
- Endurance/regeneration: continuity climbing, easy laps, easy traverse
- Pulling strength: pullup variants (weighted, L-sit, archer, typewriter, one-arm), rows, lock-offs
- Push/antagonist: pushups, dips, pike pushup, shoulder press, ring pushup, bench, face pull
- Core: hollow hold, L-sit, front lever, hanging leg raise, ab wheel, pallof, side plank, dead bug, windshield wipers, toes-to-bar
- Prehab: wrist curls, forearm rotation, rotator cuff, scapular pullups, finger extensors, elbow eccentrics, shoulder CARs
- Technique drills: silent feet, no readjust, downclimbing, slow climbing, flag practice
- Flexibility: hip opener, shoulder stretch, forearm stretch, full body flow, active hip mobility
- Complementary - handstand: wall hold, wall walk-up, shoulder taps, freestanding, HSPU
- Complementary - conditioning: jump rope, TGU, farmer carry, bear crawl, band pull-apart

### Equipment note
`pangullich` has been renamed to `campus_board` as canonical equipment ID.
Equipment marked in `equipment_required` is truly mandatory (cannot do the exercise without it).
Optional equipment is mentioned in `prescription_defaults.notes` only.

## Macrocycle engine (Phase 1 + Phase 1.5 E2E fixes)

The macrocycle engine implements Hörst 4-3-2-1 adaptive periodization with DUP.
Post-E2E test (14 findings, 13 resolved in Cluster 1+2): 179 tests green.

### Modules

- `backend/engine/assessment_v1.py` — 6-axis profile computation (finger_strength, pulling_strength, power_endurance, technique, endurance, body_composition). Each axis 0-100, benchmark-based when test data available, grade-estimated otherwise. PE score uses repeater test (40%) + RP-OS gap (40%) + self_eval (20%) to avoid double counting.
- `backend/engine/macrocycle_v1.py` — Macrocycle generator. Produces a 10-13 week periodized plan with 5 phases (base → strength_power → power_endurance → performance → deload). Includes deload logic (programmed, adaptive, pre-trip), goal validation (warns if target ≤ current), and min 2-week floor per non-deload phase.
- `backend/engine/planner_v2.py` — Phase-aware weekly planner. 2-pass algorithm: pass 1 places primary/climbing sessions with spacing, pass 2 fills complementary. Supports `pretrip_dates` to block hard sessions before trips. Pool cycling with max 2 full cycles.
- `backend/engine/replanner_v1.py` — Phase-aware replanner. 12 intents mapped to planner_v2 sessions (was 7 from planner_v1). `apply_day_override` accepts `phase_id`. Imports `_SESSION_META` from planner_v2 (no longer depends on planner_v1 SESSION_LIBRARY).
- `backend/engine/resolve_session.py` — Session resolver. Supports both template_id references and inline blocks with selection spec. All 29 session files resolve correctly. Falls back to assessment test data for suggested loads when baselines are empty.

### Flow

```
user_state.assessment + user_state.goal
    → compute_assessment_profile()    [assessment_v1]
    → generate_macrocycle()           [macrocycle_v1]
    → generate_phase_week()           [planner_v2, per week]
    → resolve_session()               [resolve_session, per session]
```

### Schema additions (user_state.json v1.5)

- `goal`: goal_type, discipline, target_grade, target_style, current_grade, deadline
- `assessment`: body, experience, grades, tests (incl. repeater_7_3_max_sets_20mm), self_eval, profile (6-axis)
- `trips[]`: name, start_date, end_date, discipline, priority
- `macrocycle`: null until generated

## Testing

Tests live in `backend/tests/`. The `conftest.py` adds the repo root to `sys.path` so `import backend.*` works. Run with:

```bash
source .venv/bin/activate && python -m pytest backend/tests -q
```

## Workflow

Always push at end of session:

```bash
git add -A && git commit -m 'description' && git push
```
