# CLAUDE.md — climb-agent

## Your role

You are a senior software engineer building climb-agent — a climbing training app heading to paid production. You are meticulous, detail-oriented, and product-minded. You think about edge cases, test coverage, and user experience before writing code. You respond in Italian.

Author: Daniele **Somensi** (with an S, not Z).

## What climb-agent is

A deterministic climbing training engine. It generates personalised weekly training plans, resolves abstract sessions into concrete exercises with sets/reps/load, and adapts progression through closed-loop feedback. No LLM is used at runtime — all logic is rule-based and testable. Methodology: Hörst 4-3-2-1 adaptive periodization with DUP. Supports both lead and boulder disciplines.

## Non-negotiable principles

- **Deterministic**: Given the same user state and inputs, output is always the same.
- **Closed-loop**: Every session outcome feeds back into user state for future planning.
- **Data-driven**: Sessions, exercises, and templates are JSON catalogs — logic is separate from data.
- **Test-first**: All engine behaviour is covered by pytest. Tests must pass before merging.

## Commands

```bash
# Run all tests
source .venv/bin/activate && python -m pytest backend/tests -q

# Run a single test file
python -m pytest backend/tests/test_planner_v1.py -q

# Start API dev server (port 8000)
uvicorn backend.api.main:app --reload --reload-exclude "backend/data/*" --port 8000

# Start frontend dev server (port 3000)
cd frontend && npm run dev

# Sync project counters into PROJECT_BRIEF.md
python scripts/sync_status.py
```

## Import conventions

All Python imports use the `backend.` prefix. Data paths are relative to repo root.

```python
from backend.engine.planner_v1 import generate_week_plan
"backend/catalog/sessions/v1/strength_long.json"
```

## Repository structure

```
backend/
  engine/            # Core: planner, resolver, replanner, progression, closed-loop
    adaptation/      # Closed-loop adaptation (multiplier-based adjustments)
  api/               # FastAPI REST API (14 routers)
    routers/         # state, catalog, onboarding, assessment, macrocycle, week,
                     # session, replanner, feedback, outdoor, reports, quotes, user, admin
  catalog/           # JSON data: exercises, sessions, templates (versioned under v1/)
  data/              # user_state.json + JSON schemas for log validation
  tests/             # pytest test suite with fixtures/
frontend/            # Next.js 14 PWA (React, Tailwind, shadcn/ui)
  src/app/           # Pages: main views + onboarding wizard + guided session
  src/components/    # layout, onboarding, training, guided, settings, whats-next, ui
  src/lib/           # api.ts, types.ts, hooks/
docs/                # Design docs, glossary, roadmap, literature reviews
scripts/             # sync_status.py (auto-update counters)
_archive/            # Legacy scripts, docs, config (do not modify)
```

See `PROJECT_BRIEF.md` for current counts (tests, exercises, sessions, endpoints, pages, components).

## Engine architecture

```
user_state.assessment + user_state.goal
    → compute_assessment_profile()    [assessment_v1]
    → generate_macrocycle()           [macrocycle_v1]
    → generate_phase_week()           [planner_v2, per week]
    → resolve_session()               [resolve_session, per session]
```

**Key modules:**
- `assessment_v1.py` — 6-axis profile (finger_strength, pulling_strength, power_endurance, technique, endurance, body_composition), 0-100 per axis
- `macrocycle_v1.py` — 10-13 week periodized plan, 5 phases (base → strength_power → power_endurance → performance → deload), boulder/lead variants
- `planner_v2.py` — Phase-aware weekly planner, 3-pass algorithm (primary → complementary → tests), location-aware, gym-priority scoring
- `replanner_v1.py` — 13 indoor + 3 outdoor intents, ripple effects, equipment-aware overrides, quick-add
- `resolve_session.py` — Resolves session templates to concrete exercises with sets/reps/load

## API endpoints

38 endpoints total (37 router + 1 app-level health check).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/state` | Get full user state |
| PUT | `/api/state` | Deep-merge patch into state |
| GET | `/api/state/status` | Dirty-state check (is_macrocycle_stale) |
| DELETE | `/api/state` | Reset state to empty |
| GET | `/api/catalog/exercises` | List all exercises |
| GET | `/api/catalog/sessions` | List all session metadata |
| GET | `/api/onboarding/defaults` | Option lists for onboarding form |
| POST | `/api/onboarding/complete` | Atomic: save state + assessment + macrocycle |
| POST | `/api/onboarding/start-week` | Shift macrocycle start_date back N weeks |
| POST | `/api/onboarding/test-week` | Generate test week plan |
| POST | `/api/onboarding/test-week-complete` | Recompute profile + macrocycle, clear test week |
| POST | `/api/assessment/compute` | Recompute 6-axis profile |
| POST | `/api/macrocycle/generate` | Generate new macrocycle |
| GET | `/api/week/{week_num}` | Generate week plan (auto-resolves sessions) |
| POST | `/api/week/test-reminder-response` | Handle periodic test reminder |
| POST | `/api/session/resolve` | Resolve a single session to exercises |
| POST | `/api/replanner/override` | Apply day override (intent-based, equipment-aware) |
| POST | `/api/replanner/events` | Apply events (done/skipped) to week plan |
| GET | `/api/replanner/suggest-sessions` | Suggest sessions for quick-add |
| POST | `/api/replanner/quick-add` | Add extra session to a day |
| POST | `/api/feedback` | Submit session feedback |
| GET | `/api/outdoor/spots` | List outdoor spots |
| POST | `/api/outdoor/spots` | Add outdoor spot |
| DELETE | `/api/outdoor/spots/{id}` | Remove outdoor spot |
| POST | `/api/outdoor/log` | Log outdoor session |
| GET | `/api/outdoor/sessions` | List outdoor sessions |
| GET | `/api/outdoor/stats` | Outdoor statistics |
| POST | `/api/outdoor/convert-slot` | Convert outdoor slot to gym/home |
| GET | `/api/reports/weekly` | Weekly training report |
| GET | `/api/reports/monthly` | Monthly training report |
| GET | `/api/quotes/daily` | Daily motivational quote |
| GET | `/api/user/export` | Download user_state as JSON backup |
| POST | `/api/user/import` | Import user_state (validates, overwrites) |
| POST | `/api/user/recovery-code` | Get or create recovery code (CLIMB-XXXX) |
| POST | `/api/user/recover` | Recover account from recovery code |
| GET | `/api/admin/users` | List all users (protected, X-Admin-Key) |
| DELETE | `/api/admin/users/{uuid}` | Delete a user (protected, X-Admin-Key) |

## Frontend

Next.js 14 App Router + Tailwind CSS + shadcn/ui. Mobile-first dark-mode PWA.

**Pages (25):** 9 main views + 14 onboarding steps + 1 root + 1 onboarding index.

- `/today` — Today's sessions, mark done/skipped, post-session feedback
- `/week` — 7-day grid, day detail cards, replan dialog, multi-week navigation
- `/plan` — Assessment radar chart + macrocycle timeline + phase details
- `/session/[id]` — Resolved exercises with prescription details, load score
- `/reports/weekly` — Adherence, load, difficulty distribution, progression table
- `/outdoor` — Outdoor history, stats, per-spot breakdown, grade histogram
- `/whats-next` — Votable roadmap + feedback form
- `/settings` — Profile, goals, equipment, spots, regenerate assessment/macrocycle
- `/guided/[date]/[sessionId]` — Step-by-step guided session with timer
- `/onboarding/*` — 14-step wizard: welcome, profile, experience, grades, goals, weaknesses, tests, limitations, locations, availability, trips, review, start-week, recover

## Deployment

- **Frontend**: Next.js PWA on Vercel — https://climb-agent.vercel.app
  - Auto-deploys on push to main. Root directory: `frontend/`
  - Env: `NEXT_PUBLIC_API_URL=https://web-production-fb1e9.up.railway.app`

- **Backend**: FastAPI/uvicorn on Railway — https://web-production-fb1e9.up.railway.app
  - Auto-deploys on push to main. Config: `Procfile` + `requirements.txt` in root
  - Railway uses port 8080 internally (`$PORT=8080`). Do not change the port in Procfile.

- **Deploy**: `git push` to main → both services update within 2-3 minutes.

- **Multi-user**: UUID from `crypto.randomUUID()` stored in localStorage as `climb_user_id`, sent as `X-User-ID` header. State: `backend/data/users/{user_id}/user_state.json`. Without header → fallback to `backend/data/user_state.json` (local dev).

- **Environment variables (Railway)**:
  | Variable | Description |
  |----------|-------------|
  | DATA_DIR | Persistent volume path (`/data/climb-agent`) |
  | ADMIN_SECRET | Key for admin endpoints (never commit) |

- **Persistence**: Railway persistent volume at `/data/climb-agent`. User data survives redeploys. `/health` exposes `ephemeral_warning`.

## Documentation architecture

- `PROJECT_BRIEF.md` — Project status + auto-updated counters (run `python scripts/sync_status.py`)
- `docs/ROADMAP_CURRENT.md` — All open items, priorities, future phases
- `docs/ROADMAP_v2.md` — Archived history (frozen, do not update)
- `docs/vocabulary_v1.md` — Domain glossary (update when adding enums/types)
- `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` — Design doc (update when methodology changes)
- `docs/literature_review_climbing_training.md` — Training science reference
- `docs/docs_literature_hangboard.md` — Hangboard science reference
- `docs/audit_location_equipment.md` — Equipment mapping reference
- `docs/beta_feedback.md` — Beta tester feedback log

## Workflow rules

- Always respond in Italian.
- Analyze before implementing — wait for explicit OK on non-trivial changes.
- Run tests before committing. Run `python scripts/sync_status.py` after every dev session.
- After closing any roadmap item: update `docs/ROADMAP_CURRENT.md` in the same commit.
- Code and documentation must always be aligned. Never leave an implemented item marked as open.
- Push at end of session: `git add -A && git commit -m 'description' && git push`
