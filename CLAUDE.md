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
- **Past sessions are immutable**: Completed and past sessions MUST NEVER be modified by any regeneration, device switch, equipment change, or any other user action. The only exception is explicit user edit (pencil icon). This applies to: exercise_id, loads, feedback, completion status, timestamps. Test this invariant after ANY change that triggers plan regeneration.

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

# Sync project counters into PROJECT_BRIEF.md, CLAUDE.md, README.md
python scripts/sync_status.py

# Activate pre-push hook (once per clone)
git config core.hooksPath .githooks
```

## Execution model

This project runs with `--dangerously-skip-permissions`. Claude Code executes without interactive approval prompts. Safety is enforced through brief structure and mandatory stop points.

### When you can proceed freely

- Bug fixes isolated to a single module with no planner/replanner/macrocycle impact
- Catalog additions (exercises, sessions, templates)
- Test additions or fixes
- Documentation updates
- Frontend-only changes (components, pages, styles)
- Running tests, linting, `sync_status.py`

### When you MUST stop and wait for OK

Any change touching these modules requires a **mandatory analysis phase** before implementation:

- `planner_v2.py` or `replanner_v1.py`
- `macrocycle_v1.py` or `generate_macrocycle()`
- `resolve_session.py` (P0 hard filters, template resolution logic)
- `progression_v1.py` or `closed_loop_v1.py`
- Any function that calls `generate_macrocycle()` — verify `from_phase="current"` is preserved
- Any change to `start_date` handling — verify Monday invariant via `ensure_monday()`
- Schema changes to `user_state.json`
- Multi-module refactors

**Protocol for high-risk changes:**

1. **Phase 1 — Analysis:** Read all affected files. List every call site, every consumer, every test. Print the full analysis.
2. **STOP.** Wait for Daniele's explicit OK before proceeding.
3. **Phase 2 — Implementation:** Apply changes only after approval.
4. **Phase 3 — Verification:** Run full test suite. Print diff summary of all changed files.

Never skip the STOP between Phase 1 and Phase 2 — even if the change looks trivial.

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
  api/               # FastAPI REST API (16 routers)
    routers/         # state, catalog, onboarding, assessment, macrocycle, week,
                     # session, replanner, feedback, outdoor, reports, quotes, user, admin, weekly_override, free_session
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
- `assessment_v1.py` — 5-axis profile (finger_strength, pulling_strength, power_endurance, technique, endurance), 0-100 per axis
- `macrocycle_v1.py` — 10-13 week periodized plan, 5 phases (base → strength_power → power_endurance → performance → deload), boulder/lead variants
- `planner_v2.py` — Phase-aware weekly planner, 3-pass algorithm (primary → complementary → tests), location-aware, gym-priority scoring
- `replanner_v1.py` — 13 indoor + 3 outdoor intents, ripple effects, equipment-aware overrides, quick-add
- `resolve_session.py` — Resolves session templates to concrete exercises with sets/reps/load

## API endpoints

50 endpoints total (49 router + 1 app-level health check).

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
| POST | `/api/assessment/compute` | Recompute 5-axis profile |
| POST | `/api/macrocycle/generate` | Generate new macrocycle |
| GET | `/api/week/{week_num}` | Generate week plan (auto-resolves sessions) |
| POST | `/api/week/test-reminder-response` | Handle periodic test reminder |
| POST | `/api/session/resolve` | Resolve a single session to exercises |
| POST | `/api/session/add-exercise` | Add exercise to resolved session |
| POST | `/api/session/remove-exercise` | Remove exercise from resolved session |
| POST | `/api/replanner/override` | Apply day override (intent-based, equipment-aware) |
| POST | `/api/replanner/events` | Apply events (done/skipped) to week plan |
| GET | `/api/replanner/suggest-sessions` | Suggest sessions for quick-add |
| POST | `/api/replanner/quick-add` | Add extra session to a day |
| POST | `/api/feedback` | Submit session feedback |
| GET | `/api/outdoor/spots` | List outdoor spots |
| POST | `/api/outdoor/spots` | Add outdoor spot |
| DELETE | `/api/outdoor/spots/{id}` | Remove outdoor spot |
| POST | `/api/outdoor/log` | Log outdoor session |
| GET | `/api/outdoor/log/{date}` | Get outdoor session by date |
| PUT | `/api/outdoor/log` | Update outdoor session |
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
| GET | `/api/weekly-override/{week_start}` | Get weekly availability override |
| PUT | `/api/weekly-override/{week_start}` | Save weekly availability override |
| DELETE | `/api/weekly-override/{week_start}` | Delete weekly availability override |
| GET | `/api/free-session/surfaces` | Available surfaces + user gyms |
| GET | `/api/free-session/presets` | Presets for surface (personalized grades, phase tips) |
| POST | `/api/free-session/start` | Start a free climbing session |
| POST | `/api/free-session/{session_id}/log-climb` | Log a climb to active session |
| POST | `/api/free-session/{session_id}/finish` | Finish session (summary + load) |
| GET | `/api/free-session/history` | Free sessions for a date |
| DELETE | `/api/free-session/{session_id}` | Delete a free session |
| GET | `/api/admin/users` | List all users (protected, X-Admin-Key) |
| DELETE | `/api/admin/users/{uuid}` | Delete a user (protected, X-Admin-Key) |

## Frontend

Next.js 14 App Router + Tailwind CSS + shadcn/ui. Mobile-first dark-mode PWA.

**Pages (31):** 9 main views + 15 onboarding steps + 1 root + 1 onboarding index + 2 auth (sign-in, sign-up) + 1 tabata + 1 legal.

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

- **Auth**: Clerk (Next.js native). Backend resolves `clerk_id` → internal `user_id` (UUID). Supabase `users` table with `clerk_id` column. In-memory LRU cache for `clerk_id → user_id` mapping. Without Clerk header → fallback to legacy UUID system (local dev only).

- **Environment variables (Railway)**:
  | Variable | Description |
  |----------|-------------|
  | DATA_DIR | Persistent volume path (`/data/climb-agent`) |
  | ADMIN_SECRET | Key for admin endpoints (never commit) |
  | STORAGE_BACKEND | `supabase` (production) or `file` (pytest/dev) |
  | SUPABASE_URL | Supabase project URL |
  | SUPABASE_SERVICE_KEY | Supabase service role key (never commit) |
  | CLERK_SECRET_KEY | Clerk backend secret (never commit) |

- **Persistence**: Supabase Postgres with JSONB (`STORAGE_BACKEND=supabase` in production). `user_state` stored as JSONB column. Railway persistent volume (`/data/climb-agent`) as fallback for `STORAGE_BACKEND=file` (pytest, local dev). `/health` exposes `ephemeral_warning`.

## Documentation architecture

- `PROJECT_BRIEF.md` — Project status + auto-updated counters (run `python scripts/sync_status.py`)
- `docs/ROADMAP_CURRENT.md` — All open items, priorities, future phases
- `docs/ROADMAP_v2.md` — Archived history (frozen, do not update)
- `docs/vocabulary_v1.md` — Domain glossary (update when adding enums/types)
- `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` — Design doc (update when methodology changes)
- `docs/literature_review_climbing_training.md` — Training science reference
- `docs/docs_literature_hangboard.md` — Hangboard science reference
- `docs/beta_feedback.md` — Beta tester feedback log

## Docs maintenance

- After closing a B/A/UI item, run `python scripts/trim_roadmap.py --dry-run` to check roadmap bloat
- When completed items exceed 20, run `python scripts/trim_roadmap.py` to archive them
- Standing rule: `python scripts/sync_status.py` at end of every brief (already enforced)

## Workflow rules

- Always respond in Italian.
- Analyze before implementing — wait for explicit OK on non-trivial changes.
- Run tests before committing. Run `python scripts/sync_status.py` after every dev session.
- After closing any roadmap item: update `docs/ROADMAP_CURRENT.md` in the same commit.
- After any A (feature) or B (bugfix) brief that changes user-facing behavior: check if `docs/user_guide_v1.md` needs updating. If yes, update in the same commit.
- Code and documentation must always be aligned. Never leave an implemented item marked as open.
- Pre-push hook runs `sync_status.py` automatically. If counters are stale, the push is blocked — commit the sync changes first.
- Repo hygiene check: every ~2 weeks or ~10 briefs (whichever first), run `python scripts/repo_hygiene.py`. Archive completed brief docs, delete temp files, verify core docs are current. Last full audit: D156 (2026-03-25).
- Push at end of session: `git add -A && git commit -m 'description' && git push`
