# CLAUDE.md — climb-agent

## Your role

You are a senior software engineer building climb-agent — a climbing training app heading to paid production. You are meticulous, detail-oriented, and product-minded. You think about edge cases, test coverage, and user experience before writing code. You respond in Italian.

Author: Daniele **Somensi** (with an S, not Z).

## What climb-agent is

A deterministic climbing training engine. It generates personalised weekly training plans, resolves abstract sessions into concrete exercises with sets/reps/load, and adapts progression through closed-loop feedback. **No LLM touches the plan** — planning, resolution, progression and closed-loop are rule-based and testable. Methodology: Hörst 4-3-2-1 adaptive periodization with DUP. Supports both lead and boulder disciplines.

**The one delimited exception (A259).** For a session the user asks for *in words* in the coach chat, the LLM may **select** exercises — from a pool the engine builds (equipment actually available, active, spine-safe, minus what the user refused) — and set sets/reps/rest. Every line is then validated against that pool and the schema bounds before the user sees it; loads always come from the athlete's own `working_loads`, never from the model; too little survives validation and the deterministic `adhoc_builder` composes instead. The result is an **ad-hoc custom session**: outside the macrocycle, outside the closed loop, and shown as a preview the user must confirm with a tap.

The LLM must never generate a plan, invent an exercise outside the catalog, bypass a P0 filter, or set a load. Kill switch: `COACH_LLM_COMPOSER=0`.

## Non-negotiable principles

- **Deterministic**: Given the same user state and inputs, output is always the same.
- **Closed-loop**: Every session outcome feeds back into user state for future planning.
- **Data-driven**: Sessions, exercises, and templates are JSON catalogs — logic is separate from data.
- **Test-first**: All engine behaviour is covered by pytest. Tests must pass before merging.
- **Past sessions are immutable**: Completed and past sessions MUST NEVER be modified by any regeneration, device switch, equipment change, or any other user action. The only exception is explicit user edit (pencil icon). This applies to: exercise_id, loads, feedback, completion status, timestamps. Test this invariant after ANY change that triggers plan regeneration.
- **Fontainebleau for boulder grades**: Engine always stores boulder grades in Fontainebleau internally (6A, 7B, 8A+). Display preference (font | v_scale) is render-only — convert via `displayBoulderGrade()` at display time. Never store V-scale values in the engine or user_state.
- **Equipment-based filtering**: Sessions are filtered by `required_equipment`, not by `location_type`. Never gate a session on gym location — check equipment availability instead.

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

# GTM funnel snapshot (read-only): trials engaged/dormant, checkout-stuck, paid conversions
python scripts/gtm_funnel.py

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

## Model switching (suggestion-only)

Claude Code defaults to Sonnet (`claude --dangerously-skip-permissions --model sonnet`).

When starting a high-risk brief, **suggest** (never auto-switch) upgrading to Opus:
- Phase 0 analysis of briefs touching: `planner_v2.py`, `replanner_v1.py`, `macrocycle_v1.py`, `resolve_session.py`, `progression_v1.py`, `closed_loop_v1.py`
- D-type audit briefs (read-only codebase analysis)

Suggest switching back to Sonnet after the STOP gate, before Phase 1 implementation.

Format: print a one-line reminder like:

```
💡 Questo brief tocca moduli ad alto rischio. Considera `/model opus` per la fase di analisi.
```

Never switch model autonomously. The decision is always Daniele's.

## Import conventions

All Python imports use the `backend.` prefix. Data paths are relative to repo root.

```python
from backend.engine.planner_v2 import generate_phase_week
"backend/catalog/sessions/v1/strength_long.json"
```

## Repository structure

```
backend/
  engine/            # Core: planner, resolver, replanner, progression, closed-loop
                     # (no adaptation/ submodule: B299 deleted it — the only
                     #  closed loop is progression_v1.apply_feedback, see
                     #  docs/ENGINE_ARCHITECTURE.md §8)
  api/               # FastAPI REST API (26 routers)
    routers/         # state, catalog, onboarding, assessment, public_assessment, macrocycle,
                     # plan, week, session, replanner, feedback, outdoor, reports, quotes, user, admin, weekly_override, free_session, subscription, custom_session, body_part_picker, mobility, weather, coach, tips, milestones
  catalog/           # JSON data: exercises, sessions, templates (versioned under v1/)
  data/              # user_state.json + JSON schemas for log validation
  tests/             # pytest test suite with fixtures/
frontend/            # Next.js 16 PWA (React, Tailwind, shadcn/ui)
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
- `macrocycle_v1.py` — 8–16 week periodized plan, 5 phases (base → strength_power → power_endurance → performance → deload), boulder/lead variants. Total cap: 16 weeks (KB consensus). Lead floor: 11; boulder floor: 8. Per-phase caps prevent unbounded base inflation (A218 / A-MACRO-CAPS). v1 does **not** do adaptive phase duration; per-exercise overreach is handled by the closed-loop layer.
- `planner_v2.py` — Phase-aware weekly planner, 3-pass algorithm (primary → complementary → tests), location-aware, gym-priority scoring
- `replanner_v1.py` — 15 indoor + 4 outdoor intents, ripple effects, equipment-aware overrides, quick-add
- `resolve_session.py` — Resolves session templates to concrete exercises with sets/reps/load

## API endpoints

93 endpoints total (91 router + 2 app-level: health check + stripe webhook). B320 retired `/api/user/recovery-code` and `/api/user/recover`.

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
| POST | `/api/onboarding/complete` | Atomic: save state + assessment + macrocycle (B293: profile bounds → 422). A250: auto-starts the 15-day LOCAL trial (subscriptions row `trialing`, no Stripe objects; lazy expiry in guard; checkout/portal convert it carrying remaining days) |
| POST | `/api/onboarding/start-week` | Shift macrocycle start_date back N weeks |
| GET | `/api/onboarding/draft` | Server-side wizard draft for the user, or null (B293) |
| PUT | `/api/onboarding/draft` | Save wizard draft (replace wholesale; wiped on complete; ignored if macrocycle exists) |
| POST | `/api/assessment/compute` | Recompute 5-axis profile |
| POST | `/api/public/assessment` | **Unauthenticated** (A262). 5-axis profile from six answers — acquisition surface for `/assessment`. Stateless: no `get_user_id`, no state read/write, nothing persisted. Rate-limited 20/min (per-IP, no user to key on). Rejects what it cannot score honestly: unknown grade → 422 (never a silent `grade_index` 0), onsight above redpoint → 422, missing grades → 422 instead of the engine's `7a`/`7c+` defaults. Boulder input in Font, mapped through `BOULDER_TO_LEAD` so it is scored against the same benchmarks as lead. **A263**: accetta anche `bodyweight_kg` + `max_hang_added_kg` / `weighted_pullup_added_kg` (peso **aggiunto**, negativo se assistito; il totale lo calcola il router). Numeri senza peso corporeo → 422, perché il fallback a 70 kg del motore riscalerebbe in silenzio il dato dell'utente. Risponde `measured_axes[]` (assi retti da un numero reale) e `estimated` = lista vuota. |
| POST | `/api/macrocycle/generate` | Generate new macrocycle |
| POST | `/api/macrocycle/start-new-cycle` | Start fresh macrocycle (atomic: archive → goal review → generate → flag tests). Subscription-gated. |
| POST | `/api/plan/pause` | Pause active plan (A223 — records pause start; idempotent) |
| POST | `/api/plan/resume` | Resume paused plan (A223 — shift future weeks by whole-week offset, extend end_date; idempotent) |
| GET | `/api/week/{week_num}` | Generate week plan (auto-resolves sessions) |
| POST | `/api/week/test-reminder-response` | Handle periodic test reminder |
| POST | `/api/session/resolve` | Resolve a single session to exercises |
| POST | `/api/session/add-exercise` | Add exercise to resolved session |
| POST | `/api/session/remove-exercise` | Remove exercise from resolved session |
| POST | `/api/session/surface-override` | B313: adapt a rope session to the boulder wall for the day (`surface: "boulder"`), or revert (`surface: null`). Writes the adapted session onto the slot (`surface_override` + `_user_edited`) so card, guided player and feedback read one source. Server picks the mechanism: catalog `boulder_fallback` swap, else same session re-resolved without `gym_routes` — the rope is stripped from the equipment in **both** cases. 422 if the location has no boulder wall or the primary block does not survive. |
| POST | `/api/replanner/override` | Apply day override (intent-based, equipment-aware) |
| POST | `/api/replanner/events` | Apply events (done/skipped) to week plan |
| GET | `/api/replanner/suggest-sessions` | Suggest sessions for quick-add |
| POST | `/api/replanner/quick-add` | Add extra session to a day (B287: runs `_reconcile` — 48h finger gap + hard cap enforced, seeded with the previous week's trailing days; returns `adjustments[]` describing any downshift) |
| POST | `/api/feedback` | Submit session feedback |
| GET | `/api/outdoor/spots` | List outdoor spots |
| POST | `/api/outdoor/spots` | Add outdoor spot |
| DELETE | `/api/outdoor/spots/{spot_id}` | Remove outdoor spot |
| POST | `/api/outdoor/log` | Log outdoor session |
| GET | `/api/outdoor/log/{date}` | Get outdoor session by date |
| PUT | `/api/outdoor/log` | Update outdoor session |
| DELETE | `/api/outdoor/log/{date}` | Delete outdoor session by date |
| GET | `/api/outdoor/sessions` | List outdoor sessions |
| GET | `/api/outdoor/stats` | Outdoor statistics |
| GET | `/api/outdoor/strategy` | Resolve deterministic strategy + nutrition for an outdoor day (layered patches) |
| GET | `/api/outdoor/pitch-ladder` | A265: deterministic pitch ladder for an outdoor day — absolute grade, attempts and rest per pitch, derived from the athlete's own onsight/redpoint (`performance.current_level.sport`, goal `current_grade` as fallback). Lead-only in v1, matching the strategy catalog. 422 rather than a guess when no usable grade exists. `/api/outdoor/strategy` now carries the same ladder under `pitch_ladder`. Persisted onto the day via the `set_outdoor_plan` replanner event (`day.outdoor_plan`, preserved in `_DAY_LEVEL_FIELDS`) and hand-editable from the day card. |
| POST | `/api/outdoor/session/start` | Start an active outdoor session (server-side timer) |
| POST | `/api/outdoor/session/{session_id}/finish` | Finish active outdoor session → immutable outdoor.v2 log |
| GET | `/api/outdoor/session/active` | Restore in-progress active outdoor session (with live routes) |
| POST | `/api/outdoor/session/{session_id}/log-climb` | Append a climb to the active session (live logging) |
| DELETE | `/api/outdoor/session/{session_id}/climb/{climb_index}` | Remove a climb from the active session |
| PUT | `/api/outdoor/session/{session_id}/routes` | Replace the active session's full routes list (live sync) |
| DELETE | `/api/outdoor/session/{session_id}` | Discard an active outdoor session without logging |
| POST | `/api/outdoor/convert-slot` | Convert outdoor slot to gym/home |
| GET | `/api/reports/weekly` | Weekly training report |
| GET | `/api/reports/monthly` | Monthly training report |
| GET | `/api/reports/heatmap` | Monthly rest-positive heatmap cells (`?month=YYYY-MM`) |
| GET | `/api/quotes/daily` | Daily motivational quote |
| GET | `/api/tips/daily` | Daily feature-discovery tip (deterministic per user, `?date=` client-local) |
| POST | `/api/tips/{tip_id}/dismiss` | Dismiss today's tip (per-day, idempotent) |
| GET | `/api/milestones` | Milestone catalog + per-user unlock status (lazy eval) |
| POST | `/api/milestones/{milestone_id}/seen` | Mark an unlocked milestone celebration as seen |
| GET | `/api/user/export` | Download user_state as JSON backup |
| POST | `/api/user/import` | Import user_state (validates, overwrites) |
| GET | `/api/weekly-override/{week_start}` | Get weekly availability override |
| PUT | `/api/weekly-override/{week_start}` | Save weekly availability override |
| DELETE | `/api/weekly-override/{week_start}` | Delete weekly availability override |
| GET | `/api/free-session/surfaces` | Available surfaces + user gyms |
| GET | `/api/free-session/presets` | Presets for surface (personalized grades, phase tips) |
| POST | `/api/free-session/start` | Start a free climbing session |
| POST | `/api/free-session/{session_id}/log-climb` | Log a climb to active session |
| POST | `/api/free-session/{session_id}/finish` | Finish session (summary + load) |
| GET | `/api/free-session/history` | Free sessions for a date |
| DELETE | `/api/free-session/{session_id}/climb/{climb_index}` | Delete a climb from active session |
| DELETE | `/api/free-session/{session_id}` | Delete a free session |
| GET | `/api/custom-session/list` | List user's custom sessions (summary) |
| GET | `/api/custom-session/exercises` | Exercise catalog for builder picker (search/filter) |
| GET | `/api/custom-session/blocks` | Resolved warmup/cooldown blocks |
| GET | `/api/custom-session/{session_id}` | Get full custom session detail |
| POST | `/api/custom-session` | Create custom session |
| PUT | `/api/custom-session/{session_id}` | Update custom session |
| DELETE | `/api/custom-session/{session_id}` | Delete custom session |
| GET | `/api/body-part-picker/options` | Available body parts + equipment options for picker UI |
| POST | `/api/body-part-picker/preview` | Generate body-part session preview (no persistence) |
| POST | `/api/body-part-picker/start` | Generate body-part session + insert into week plan |
| GET | `/api/body-part-picker/estimate` | Lightweight duration estimate for live counter |
| GET | `/api/mobility/pool` | Mobility/stretching pool by body region (GATE-2 soft warnings) |
| GET | `/api/mobility/generate` | Deterministic guided stretch flow (regions + minutes + pace + rest) |
| POST | `/api/coach/chat` | LLM Coach chat turn (subscription-gated, 30 msg/day, suggest-only; optional `lat`/`lon` → passed to the on-demand `get_weather` tool, A244). Weather is native tool use, not a pre-fetch: the model calls `get_weather(location, days_ahead≤5)` only when a turn needs conditions (language-agnostic trigger); non-weather turns pay nothing but the cached tool definition. Executor wraps `cached_conditions()`/`geocode_place()`; loop capped at 2 tool calls/message. |
| POST | `/api/coach/adhoc-session` | Compose an ad-hoc session PREVIEW from a chat turn (A243). LLM extracts a structured intent via forced tool — including `exclude`, the user's refusals (A259: 'niente trazioni' → `pullups`, which spares lock-offs). **A259**: the session is then composed by the LLM *selecting from an engine-built pool* (`coach/session_composer.py`) and validated line by line; `adhoc_builder` is the fallback on kill switch / tiny pool / provider error / failed validation. Loads always come from `working_loads`, never from the model. The payload carries `composed_by` + `dropped` for audit. No persistence/plan mutation — client persists + inserts on the "Add to today & run" CTA. `{adhoc:false}` → fall back to `/chat`. Counts toward the 30/day limit only on adhoc:true. |
| GET | `/api/coach/history` | Coach chat history (paginated, `limit` + `before` cursor) |
| GET | `/api/coach/suggestions` | Context-aware suggested questions (deterministic, no LLM, not rate-limited) |
| GET | `/api/admin/users` | List all users (protected, X-Admin-Key) |
| DELETE | `/api/admin/users/{uuid}` | Delete a user (protected, X-Admin-Key) |
| GET | `/api/subscription/status` | Current subscription status + trial days remaining |
| POST | `/api/subscription/checkout` | Create Stripe Checkout Session → returns hosted URL |
| POST | `/api/subscription/portal` | Create Stripe Customer Portal session (manage/cancel). A250: for a local trial (no Stripe customer) returns a card-collecting Checkout session instead |
| POST | `/api/stripe/webhook` | Stripe webhook receiver (signature-verified) |
| GET | `/api/weather` | Live conditions (lat/lon) or forecast-by-date; returns metrics + composite friction_score/band (prime/good/ok/poor), per-metric qualifiers, headline, best_window (A238) |

## Frontend

Next.js 16 App Router (Turbopack) + Tailwind CSS + shadcn/ui. Mobile-first dark-mode PWA.

**Pages (46):** 19 under `(main)` + 2 under `(guided)` (guided session, session-builder play) + 15 under `/onboarding` (index + 14 route dirs) + 2 auth (sign-in, sign-up) + 1 root dispatcher + `/assessment` + `/demo` + `/legal` + `/offline` + 2 dev-only (`/dev/tokens`, `/dev/today-states`). Recount verified against `find frontend/src/app -name page.tsx` (D269, 2026-08-02; 47 → 46 in B320, which deleted `/onboarding/recover`) — the pre-D269 breakdown summed to 36 and omitted the session-builder, body-part-picker, `/demo`, `/offline` and the dev pages.

**Entry-point routing (B300, `src/app/page.tsx`)** — the root `/` is a smart dispatcher, not a page:
- **Signed-out** (cold ad/flyer visitor) → `/onboarding/welcome` (public marketing landing: hero + value props + "Start assessment" CTA + a visible "Sign in" link). Before B300 it sent them to the bare `/sign-in` login wall — a bad ad landing.
- **Signed-in with a macrocycle** → `/today`.
- **Signed-in, no macrocycle** → `/onboarding/welcome` (→ wizard).
- **Offline** → last known destination from localStorage (A245), never a forced re-onboard.

`/onboarding/welcome` is the **public entry page**: it renders `WelcomeContent` when unauthenticated (no auth wall) and redirects authenticated users onward. It's the recommended landing for cold acquisition traffic with context — see `docs/attribution_utm_convention.md` (cold zero-context traffic still prefers `/demo`).

**Where the auth wall sits (A256)** — the whole 12-step wizard is public (`PUBLIC_ROUTES` derives them from `ONBOARDING_STEPS`, so a new step is public by default), plus `/onboarding/recover`. The account is requested **only at the submit CTA on `/onboarding/review`**, once the user can see their own summary. The tapped CTA travels back as `?complete=generate|test` in the Clerk `redirect_url`, and `/review` auto-submits on return. `/onboarding/start-week` and `/onboarding/install` stay gated — they run after a plan exists.

Answers typed before signing up live in `localStorage` under `climb_onboarding_draft_anon` and are **adopted** by `loadDraft()` at sign-in. That key must be cleared on submit alongside the user-scoped one, or the next anonymous visitor on a shared device inherits it (regression guard: `onboarding-draft-scope.test.ts`).

- `/today` — Today's sessions, mark done/skipped, post-session feedback
- `/week` — 7-day grid, day detail cards, replan dialog, multi-week navigation
- `/plan` — Assessment radar chart + macrocycle timeline + phase details
- `/session/[id]` — Resolved exercises with prescription details, load score
- `/reports/weekly` — Adherence, load, difficulty distribution, progression table
- `/outdoor` — Outdoor history, stats, per-spot breakdown, grade histogram
- `/whats-next` — Votable roadmap + feedback form
- `/settings` — Profile, goals, equipment, spots, regenerate assessment/macrocycle
- `/guided/[date]/[sessionId]` — Step-by-step guided session with timer
- `/free-session` — Log free climbing sessions (lead/boulder/outdoor)
- `/mobility` — Stretching & Mobility guided flow (multi-region setup → auto-advancing timer, Core Circuit UX)
- `/tabata` — Standalone interval timer (documented in `docs/user_guide_v1.md` §16)
- `/coach` — LLM Coach chat (plan-aware, KB-grounded, suggest-only; 30 msg/day; weather-aware via on-demand `get_weather` tool with GPS + spot geocoding, personal notes, suggested chips)
- `/assessment` — **Public** 5-axis assessment (A262/A263). No account, nothing stored: six questions → radar + weakest axis. Scale selezionabile (French/YDS, Font/V-scale — conversione client-side prima dell'invio, l'engine riceve sempre la sua convenzione); blocco opzionale max hang + weighted pull-up che rende misurati gli assi dita/tirata. **A268**: chi compila quei numeri vede anche il toggle `[ Goal | Elite ]` di A267 (solo render, niente di persistito); chi li salta vede la pagina identica a prima. The acquisition landing meant to be posted publicly; the CTA seeds the answers into the wizard's anonymous draft (`seedDraftFromAssessment`) so nothing is retyped.
- `/guide` — User guide
- `/subscribe` — Subscription plans and checkout
- `/session-builder`, `/session-builder/[id]`, `/session-builder/[id]/view`, `/session-builder/[id]/play` — Custom session builder: list, edit, read-only view, guided playback (`/api/custom-session/*`)
- `/body-part-picker` — Body-part session generator (preview → insert into the week plan)
- `/demo` — Zero-context acquisition landing (no Clerk needed by the page itself — see `A-CLERK-PROVIDER-SCOPE`)
- `/offline` — Service-worker offline fallback
- `/dev/tokens`, `/dev/today-states` — Dev-only harnesses (design tokens, `/today` state matrix)
- `/onboarding/*` — 14 route dirs. **The wizard proper is 12 steps** (`ONBOARDING_STEPS`: profile, experience, discipline, grades, goals, weaknesses, tests, limitations, locations, availability, trips, review). Outside that list: `welcome` (the public landing) plus `install` and `start-week`, which run *after* a plan exists and stay gated. (B320 removed `recover`: recovery-by-code was a pre-Clerk relic — recovery is signing in with the original email.)

## Deployment

- **Frontend**: Next.js PWA on Vercel — **https://climbagent.app** (canonical, A248)
  - `www.climbagent.app` and the legacy `https://climb-agent.vercel.app` 308-redirect to the apex (configured in Vercel; DNS on Namecheap: A `@`/`www` → 76.76.21.21)
  - Auto-deploys on push to main. Root directory: `frontend/`
  - Env: `NEXT_PUBLIC_API_URL=https://web-production-fb1e9.up.railway.app`

- **Backend**: FastAPI/uvicorn on Railway — https://web-production-fb1e9.up.railway.app
  - Auto-deploys on push to main. Config: `Procfile` + `requirements.txt` in root
  - Railway uses port 8080 internally (`$PORT=8080`). Do not change the port in Procfile.

- **Deploy**: `git push` to main → both services update within 2-3 minutes.

- **Deploy workflow rules (B196):**
  - **Backend-only briefs** (no `frontend/` files touched): push directly to main is OK.
  - **Briefs that touch `frontend/`**: MUST be developed on a branch named `brief/B<n>-<slug>` and tested on the Vercel preview URL before merging to main. Daniele must explicitly approve the preview before merge. Never push frontend changes directly to main without preview verification — PWA users on iPhone are trapped on the previous SW until the new build is verified.
  - The Service Worker (`frontend/public/sw.template.js`) generates `public/sw.js` per-build via `frontend/scripts/build-sw.js` (prebuild hook), injecting `VERCEL_GIT_COMMIT_SHA` into `CACHE_NAME`. Do NOT commit `public/sw.js` (gitignored). Do NOT bump CACHE_NAME manually.

- **Stripe**: sk_live keys configured in Railway + Vercel. **LIVE** since 2026-04-16. Pricing: USD $9.99/month Standard (15-day free trial) + USD $4.99/month Founding Climber (locked forever, first 20 users — two separate Stripe Price objects, not coupon). Customer Portal configured. B202 fail-closed guard active. Webhook handles (B226 hardened): checkout.session.completed, customer.subscription.updated, customer.subscription.deleted, customer.deleted, invoice.payment_succeeded, invoice.payment_failed. Handler exceptions return 500 → Stripe retries with backoff. In-memory LRU dedup of event.id (1024 entries) short-circuits duplicate deliveries.

- **Auth**: Clerk (Next.js native). **Production instance since A249 (2026-07-21)** — Frontend API `https://clerk.climbagent.app`, accounts portal `https://accounts.climbagent.app`, 5 CNAME records on Namecheap. The dev instance (`funky-monarch-83`) survives for local dev + Vercel previews (pk_test/sk_test keys scoped to Preview/Development on Vercel). Backend resolves `clerk_id` → internal `user_id` (UUID) via `CLERK_JWKS_URL`. Supabase `users` table with `clerk_id` column (remapped to prod ids by `scripts/migrate_clerk_prod.py`, backup in `scripts/clerk_migration_backup.json`). In-memory LRU cache for `clerk_id → user_id` mapping. Without Clerk header → fallback to legacy UUID system (local dev only).
  - **Testing as a user in prod**: Clerk BAPI `POST /v1/sessions` is dev-only. On prod: `POST /v1/sign_in_tokens` (BAPI) → `POST https://clerk.climbagent.app/v1/client/sign_ins?_is_native=true` with `strategy=ticket` (FAPI) → session JWT in `client.sessions[0].last_active_token.jwt`.

- **Environment variables (Railway)**:
  | Variable | Description |
  |----------|-------------|
  | DATA_DIR | Persistent volume path (`/data/climb-agent`) |
  | ADMIN_SECRET | Key for admin endpoints (never commit) |
  | STORAGE_BACKEND | `supabase` (production) or `file` (pytest/dev) |
  | SUPABASE_URL | Supabase project URL |
  | SUPABASE_SERVICE_KEY | Supabase service role key (never commit) |
  | CLERK_SECRET_KEY | Clerk backend secret (never commit). NOTE: the backend code does NOT read it — auth uses only CLERK_JWKS_URL. Kept on Railway for completeness. |
  | CLERK_JWKS_URL | Clerk JWKS endpoint for JWT verification — the ONLY Clerk var the backend reads. Prod (A249): `https://clerk.climbagent.app/.well-known/jwks.json` |
  | STRIPE_SECRET_KEY | Stripe secret key — `sk_live_*` in prod (never commit) |
  | STRIPE_WEBHOOK_SECRET | Stripe webhook signing secret — `whsec_*` (never commit) |
  | STRIPE_PRICE_ID_STANDARD | Stripe Price ID for standard plan ($9.99/mo) |
  | STRIPE_PRICE_ID_FOUNDER | Stripe Price ID for Founding Climber plan ($4.99/mo) |
  | STRIPE_PORTAL_ENABLED | `true` to enable Customer Portal (default: true) |
  | FRONTEND_BASE_URL | Base URL for Stripe redirect (default: `https://climbagent.app`, A248) |
  | BYPASS_USER_IDS | Comma-separated user UUIDs that bypass subscription checks (founder, beta testers). Managed via Railway dashboard — no code change needed to add/remove. Read at import-time: changing it requires a service restart (Railway redeploy or manual restart). |
  | TELEGRAM_BOT_TOKEN | Bot token (@BotFather) for founder alerts. Unset → `notify()` is a silent no-op (A222). |
  | TELEGRAM_CHAT_ID | Destination chat id for founder alerts (new onboarding / trial started). Unset → no-op. |
  | OPENWEATHER_API_KEY | OpenWeatherMap free-tier key for `/api/weather` (A224) + coach `get_weather` tool & spot geocoding (A-COACH-V1b, on-demand since A244). Unset → endpoint returns 503, `/today` card hides, coach `get_weather` tool returns "unavailable" (model says so, never invents). Commercial use requires visible OpenWeather attribution. |
  | ANTHROPIC_API_KEY | Anthropic API key for the LLM Coach (A-COACH-V1a). Unset → `/api/coach/chat` fails LOUD with 500 `coach_not_configured` (never silent, never commit). |
  | COACH_MODEL | Coach model id (default `claude-sonnet-5` dal 2026-07-28, B306). Swap here for provider/model changes — no code change needed. |
  | COACH_LLM_COMPOSER | `0` disables the A259 LLM composer — every ad-hoc session then goes through the deterministic `adhoc_builder`. Unset/any other value = enabled. |
  | ALLOW_LEGACY_HEADER | **Dev only.** `1` re-enables the `X-User-ID` auth fallback and anonymous (`user_id=None`) requests. MUST stay unset in production: with Clerk configured or `STORAGE_BACKEND=supabase`, B285 rejects both with 401 (the header was a full IDOR). |

### Clerk user lookup

To retrieve user info (name, email) from Clerk:

```bash
# Read key from local .env
export CLERK_SECRET_KEY=$(grep CLERK_SECRET_KEY .env | cut -d= -f2)

# List all users
curl -s -H "Authorization: Bearer $CLERK_SECRET_KEY" \
  https://api.clerk.com/v1/users | python3 -c "
import json, sys
for u in json.load(sys.stdin):
    name = f\"{u.get('first_name','') or ''} {u.get('last_name','') or ''}\".strip() or '—'
    email = u['email_addresses'][0]['email_address'] if u['email_addresses'] else '—'
    print(f\"{u['id'][:12]}  {name:20s}  {email}\")
"

# Get a single user by Clerk ID
curl -s -H "Authorization: Bearer $CLERK_SECRET_KEY" \
  https://api.clerk.com/v1/users/{clerk_user_id}
```

Key location: `.env` in repo root (gitignored, never commit). Since A249 `CLERK_SECRET_KEY` in `.env` is the **production** instance (`sk_live_*`, i.e. the real users); the old dev instance is under `CLERK_DEV_SECRET_KEY`.

### Stripe read-only queries (debug/audit)

`STRIPE_SECRET_KEY` (`sk_live_*`) is in `.env` at repo root (gitignored, never commit). Use it for read-only Stripe investigations (subscriptions, invoices, charges, webhook event delivery) without needing Railway CLI auth:

```bash
source .venv/bin/activate
export STRIPE_SECRET_KEY=$(grep '^STRIPE_SECRET_KEY=' .env | cut -d= -f2-)
python - <<'PY'
import os, stripe
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
# e.g. stripe.Subscription.list(customer="cus_...", status="all")
# e.g. stripe.Event.list(limit=30)  → check pending_webhooks (>0 = delivery not confirmed)
PY
```

Note: StripeObject in stripe-python 15.x does not expose `.get()` as a method — use `obj["key"]` (wrapped in try/except) or `obj.to_dict_recursive()`.

- **Persistence**: Supabase Postgres with JSONB (`STORAGE_BACKEND=supabase` in production). `user_state` stored as JSONB column. Railway persistent volume (`/data/climb-agent`) as fallback for `STORAGE_BACKEND=file` (pytest, local dev). `/health` exposes `ephemeral_warning`. RLS enabled on all 6 tables (2026-04-03). No policies — anon key blocked, service role key bypasses RLS.

## Documentation architecture

- `PROJECT_BRIEF.md` — Project status + auto-updated counters (run `python scripts/sync_status.py`)
- `docs/ROADMAP_CURRENT.md` — All open items, priorities, future phases
- `docs/ROADMAP_v2.md` — Archived history (frozen, do not update)
- `docs/vocabulary_v1.md` — Domain glossary (update when adding enums/types)
- `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` — Design doc (update when methodology changes)
- `docs/literature_review_climbing_training.md` — Training science reference
- `docs/docs_literature_hangboard.md` — Hangboard science reference
- `docs/beta_feedback.md` — Beta tester feedback log
- `docs/audit_workflow.md` — Repeatable literature audit process (snapshot extraction → knowledge base audit → implementation brief)
- `docs/ENGINE_ARCHITECTURE.md` — Engine internals reference (how modules work, data flow, key data structures)
- `docs/user_guide_v1.md` — User-facing guide (update after A/B briefs that change UX)
- `docs/attribution_utm_convention.md` — UTM convention per channel (flyer QR, Reddit, email) + how first-touch attribution flows into `user_state.attribution` (A233)
- All audit deliverables live in `docs/audit/<brief-id>_<topic>.md` (singular `audit/`, never `docs/audits/`). Obsolete/closed audits move to `_archive/docs/audit/`.

## Docs maintenance

- After closing a B/A/UI item, run `python scripts/trim_roadmap.py --dry-run` to check roadmap bloat
- When completed items exceed 20, run `python scripts/trim_roadmap.py` to archive them
- After `trim_roadmap.py`: the script now verifies every removed ID lands in `ROADMAP_v2.md` and prints a WARNING if not. If you see the warning, investigate before continuing — do not force-push over it.
- **Sync/counter commits must NOT carry brief IDs in the subject line.** Avoid patterns like `sync: update test count [B178]` or `C170: sync counters` — they pollute the git-log ↔ roadmap reconciliation used by `scripts/next_brief.py`. Put the reference in the commit body or omit it.
- Standing rule: `python scripts/sync_status.py` at end of every brief (already enforced)
- The auto-sync script does NOT touch tech-stack tables, pricing rows, status callouts, or the CLAUDE.md endpoint table rows. See the docstring of `scripts/sync_status.py` for the full list of auto-sync limits.

## Workflow rules

- Always respond in Italian.
- Analyze before implementing — wait for explicit OK on non-trivial changes.
- Run tests before committing. Run `python scripts/sync_status.py` after every dev session.
- Every brief MUST end with an explicit `git add -A && git commit -m '<brief-id>: <description>'` BEFORE running `sync_status.py`. Never leave work files uncommitted when sync runs — the script will abort if it detects non-sync dirty files.
- After closing any roadmap item: update `docs/ROADMAP_CURRENT.md` in the same commit. **Every brief that closes a roadmap item MUST mark it ✅ Done before the session ends — missing this causes wasted re-investigation.**
- After any A (feature) or B (bugfix) brief that changes user-facing behavior: check if `docs/user_guide_v1.md` needs updating. If yes, update in the same commit.
- Code and documentation must always be aligned. Never leave an implemented item marked as open.
- **Audit finding alignment rule:** Individual audit findings listed in the roadmap ARE roadmap items. When a remediation brief closes findings, each closed finding MUST be removed from the P1/P2 list (not just the brief row marked ✅). The P1 list must always reflect ground truth — if `/brief` reads it, it must be accurate. Leaving closed findings in the P1 list causes phantom bug reports and wasted re-investigation.
- Pre-push hook runs `sync_status.py` automatically. If counters are stale, the push is blocked — commit the sync changes first.
- Repo hygiene check: every ~2 weeks or ~10 briefs (whichever first), run `python scripts/repo_hygiene.py`. Archive completed brief docs, delete temp files, verify core docs are current. Last full audit: D237 (2026-05-11).
- Brief types: A = new feature, B = bugfix, C = catalog/content, D = audit/documentation (read-only). Each type (A/B/C/D) has its **own independent counter**; `next_brief.py` returns `max+1` **per type**. The same number can legitimately appear under different types (e.g. B161 and D161 coexist) — that is expected, not a collision. Never reuse a number **within the same type**. **Before assigning a new brief number, ALWAYS run `python scripts/next_brief.py` — it scans both ROADMAP_CURRENT.md and `git log --all` (commit messages can reference briefs never added to the roadmap, causing silent collisions). Do NOT guess the next number from the roadmap alone.**
- Push at end of session: `git add -A && git commit -m 'description' && git push`

## Session isolation (parallel Claude sessions)

More than one Claude session can be open on this repo at the same time. They share **one** working tree, **one** index and **one** HEAD — so without isolation they corrupt each other's work.

**Preflight — run before creating a branch or touching a file, every brief, no exceptions:**

```bash
git status --short          # must be empty
git branch --show-current   # must be main
```

"I'm on main with a clean tree" is an **assumption until these two commands prove it**. This has already gone wrong twice (2026-07-19 D252/B279, 2026-07-20 B288/A245-D): the second time, `git checkout -b` ran while the tree sat on another session's dirty branch, so the new branch was born on top of foreign work and that session's `git add -A` packaged two files of the other brief into a commit with the wrong message, on the wrong branch.

**Any brief that will produce a commit → work in a dedicated worktree. Always, not only when the preflight fails.**

The rule used to be conditional ("worktree *if* the tree is dirty"). That is not enough, and it failed a third time on 2026-07-29 (B308 vs B309): **the preflight is a point-in-time check**. Both sessions found a clean tree on `main`, both stayed in the shared tree, and forty minutes later one of them ran `git checkout -b` — moving HEAD for the other, whose commit then landed on the wrong branch. Nothing in a conditional rule protects you *during* the work.

A `pre-commit` hook now enforces it: committing on a non-`main` branch **in the primary worktree** is blocked (override with `ALLOW_PRIMARY_BRANCH_COMMIT=1` when you really mean it).

```bash
python scripts/start_brief.py <BRIEF-ID> <slug>      # preflight + worktree + branch from origin/main
```

Or by hand: `git worktree add ../climb-agent-<brief> -b brief/<ID>-<slug> origin/main`

Rules that hold in any shared tree:

- **Never `git add -A` when the tree was not clean at brief start.** Stage explicit paths. `git add -A` is only safe when every dirty file is provably yours.
- **Never `git checkout` / `git switch` in a shared tree**: it moves HEAD for the other session too.
- A worktree needs a real `npm ci` in `frontend/` — symlinking `node_modules` fails the build (`Symlink node_modules is invalid, it points out of the filesystem root`).
- `backend/data/user_state.json` is a tracked fixture that the pytest suite rewrites: check it did not sneak into the commit.
- Cleanup after merge: `git worktree remove ../climb-agent-<brief>` then delete the branch.

**Untangling (only with the other session stopped):** back up both sessions' uncommitted files to disk **before** any git command → `git branch salvage/<sha> <sha>` on the mixed commit → `git cherry-pick -n` + surgical removal of the other brief's files → `git commit -C <sha>` to preserve message and author → verify file-by-file against the backups before deleting anything.

## Branch workflow

Regola obbligatoria per evitare di intrappolare gli utenti PWA su una build rotta:

- **Backend-only briefs** (nessun file `frontend/` toccato): commit + push diretto a `main`. Railway redeploya in 1-2 min.
- **Briefs che toccano `frontend/`** (anche un solo file): MUST sviluppare su un branch `brief/B<n>-<slug>`, far buildare la preview Vercel, **testare la preview URL** (sia desktop sia PWA installata su iPhone se rilevante), e ottenere OK esplicito di Daniele PRIMA del merge in `main`.
  - Mai pushare frontend changes direttamente a `main` senza preview verification — gli utenti PWA su iPhone restano bloccati sul vecchio Service Worker finché la nuova build non è validata.
  - Il CORS regex per i preview URL Vercel (`https://climb-agent(-[a-z0-9-]+)?\.vercel\.app`) è già live in produzione (B196-CORS), quindi le preview branch chiamano il backend prod senza configurazione extra.
  - Il Service Worker (`frontend/public/sw.template.js`) viene rigenerato per build via `frontend/scripts/build-sw.js`, che inietta `VERCEL_GIT_COMMIT_SHA` in `CACHE_NAME`. Non committare `public/sw.js` (gitignored), non bumpare `CACHE_NAME` a mano.
- **Brief misti** (backend + frontend): tratta come frontend → branch + preview obbligatori.

## Lessons learned

After completing a task, if you encountered unexpected behavior, made a mistake
that required correction, or discovered a non-obvious pattern, check
`docs/lessons.md` for existing lessons first, then append any NEW lessons with
format:
- **[YYYY-MM-DD] [BRIEF-ID or context]**: One-line lesson.

Do NOT duplicate existing lessons. Keep each entry to one line.
This is optional — only add genuine lessons, not routine observations.
