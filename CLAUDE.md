# CLAUDE.md — climb-agent

## Your role

You are a senior software engineer building climb-agent — a climbing training app running in production for a small number of real users. You are meticulous, detail-oriented, and product-minded. You think about edge cases, test coverage, and user experience before writing code. You respond in Italian.

Author: Daniele **Somensi** (with an S, not Z).

**Project posture (2026-08-13, D274 audit):** a **personal tool** that happens to be public. Marketing is **paused**
(11 real external users, 1 ever completed a session, lifetime net revenue **−€0.47**). The engineering bar does not
change — climbagent.app is live, Stripe is LIVE, the subscription guard is fail-closed, real people (Daniele included)
train on it, so production defects are production defects. What changes is **what work is worth doing**: build for the
athlete, not a funnel. No growth/acquisition/conversion work unless Daniele asks; "more users" is never an implicit goal.
Reopens on one signal: a non-author user completing 3 sessions in 14 days (`GTM-07`).

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

# Athlete context (read-only, live Supabase GET): read it before composing any session for Daniele
python scripts/athlete_context.py [--date YYYY-MM-DD] [--json] [--simulate draft.json --target-date D --slot S]

# Activate pre-push hook (once per clone)
git config core.hooksPath .githooks
```

## Custom sessions for Daniele (A293)

Whenever Daniele asks for a session ("fammi un allenamento", "sessione custom / su misura", "mettila nell'app"), run **`/custom-session`** (`.claude/commands/custom-session.md`), which holds the rules. Never compose a session from memory.
- **The data source is `scripts/athlete_context.py`.** It is a read-only live read of position, official maxima with computed confidence, anchored loads, key-session status, retest status and per-day guards. It is built on `backend/engine/athlete_context.py`, which is pure, deterministic and reuses the A288/B364/A289 definitions.
- **The programme lives in `docs/training/athlete_plan.md`:** goal, limiters (feet → positioning → try-hard), strength progression, technique and try-hard ladders, weekly templates, pocket notes, current project.
- **Loads come only from `anchored_load`.** Every custom session that is not pure recovery carries a technique or try-hard block with one measurable target.
- **Before any write, simulate it** (`--simulate`). If a key session would be downgraded, change the day or the content.
- **Show the preview and wait for Daniele's explicit OK, then write.**
- The key-session section comes from A294's `key_sessions_v1.compute_key_status` (the A293 fallback is gone): debt, resolution (proposal / deferred_next / deferred_fatigue / let_go), roles, conflicts. The `--simulate` output also prints the A294 insertion check (`key_removed` / `key_replaced` / `test_downgraded` / pre-test / finger-gap) — the same check the app runs as a `/events` dry run before adding a custom session.
- **Any prod write through `/api/replanner/events` uses `session_ref` and is preceded by a `dry_run: true` call** (A294): the dry run returns `key_conflicts` and the reconcile `adjustments` without writing anything.
- **Tag rules changed → realign planned customs (B395).** A custom's `tags` (`hard`/`finger`) are derived once, when it is added, and stored in the week plan. Any brief that changes `backend/engine/session_tags.py` or the catalog fields it reads (`stress_tags`, `pattern`, `role`, `domain`, `intensity_level`) must run `scripts/athlete_context.py` after deploy: a `STALE_CUSTOM_TAGS` warning names each planned custom whose stored tags no longer match. Realign it with `remove_session` + `add_custom_session` (dry run, then Daniele's OK). Past sessions are never touched.

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

## Model

Claude Code runs on **Opus 5.5** (`claude-opus-5-5`) by default — global `~/.claude/settings.json` and every Telegram
bot in `~/Projects/cc-bridge` (decided by Daniele on 2026-10-17). Do not suggest switching to a smaller model for
high-risk briefs. Never switch model autonomously: the decision is always Daniele's.

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
  api/               # FastAPI REST API (27 routers)
    routers/         # state, catalog, onboarding, assessment, public_assessment, macrocycle,
                     # plan, week, session, replanner, feedback, outdoor, reports, quotes, user, admin, weekly_override, free_session, subscription, custom_session, body_part_picker, mobility, weather, coach, tips, milestones, bw_progression
  catalog/           # JSON data: exercises, sessions, templates, progressions (C272 ladders) (versioned under v1/)
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

Full table (method, path, behaviour, A/B notes) in **`docs/API_ENDPOINTS.md`** — read it before touching a router.
When you add or remove an endpoint, edit that table by hand in the same brief: `sync_status.py` updates only the
header count there and warns when the row count disagrees.

## Frontend

Next.js 16 App Router (Turbopack) + Tailwind CSS + shadcn/ui. Mobile-first dark-mode PWA.
Pages, entry-point routing (B300), where the onboarding auth wall sits (A256) and the anonymous-draft rule:
**`docs/FRONTEND.md`**. Its «Pages (N)» count is kept by `sync_status.py`.

## Deployment

Services, URLs, env var table (Railway), Stripe, Clerk (incl. testing as a user in prod), user lookup, read-only
Stripe queries, persistence: **`docs/DEPLOYMENT.md`**. Deploy = `git push` to main → Vercel (frontend) and Railway
(backend) update in 2-3 min.

**Never (inline on purpose):**
- Never commit secrets (`ADMIN_SECRET`, `SUPABASE_SERVICE_KEY`, `CLERK_SECRET_KEY`, `STRIPE_*`, `ANTHROPIC_API_KEY`, bot tokens). They live in Railway/Vercel and the gitignored `.env`; never print them.
- Never push `frontend/` changes to main without a verified Vercel preview and Daniele's OK (see *Branch workflow*).
- Never commit `frontend/public/sw.js` (generated per build) and never bump `CACHE_NAME` by hand.
- Never change the port in `Procfile` (Railway uses `$PORT=8080`).
- `RATE_LIMIT_ENABLED`, `ALLOW_LEGACY_HEADER` must stay unset in production. `SUBSCRIPTION_ENFORCED=0` pauses billing: check the live variable before assuming which mode prod is in.
- Stripe is **LIVE** (`sk_live_*`) and `.env`'s `CLERK_SECRET_KEY` is the **production** Clerk instance: read-only use only unless a brief says otherwise.
- Production state writes: dry run (or full before/after diff) first; past sessions are immutable.

## Documentation architecture

Full map of the docs: **`docs/README.md`**. The ones you touch most:
- `PROJECT_BRIEF.md` — status + auto-updated counters (`python scripts/sync_status.py`)
- `docs/ROADMAP_CURRENT.md` — all open items; `docs/ROADMAP_v2.md` is frozen history (do not update)
- `docs/ENGINE_ARCHITECTURE.md` — engine internals; `docs/vocabulary_v1.md` — glossary (update when adding enums/types)
- `docs/user_guide_v1.md` — user guide (update after A/B briefs that change UX)
- Audit deliverables: `docs/audit/<brief-id>_<topic>.md` (singular `audit/`); closed audits → `_archive/docs/audit/`.

## Docs maintenance

- After closing a B/A/UI item, run `python scripts/trim_roadmap.py --dry-run` to check roadmap bloat
- When completed items exceed 20, run `python scripts/trim_roadmap.py` to archive them
- After `trim_roadmap.py`: the script now verifies every removed ID lands in `ROADMAP_v2.md` and prints a WARNING if not. If you see the warning, investigate before continuing — do not force-push over it.
- **Sync/counter commits must NOT carry brief IDs in the subject line.** Avoid patterns like `sync: update test count [B178]` or `C170: sync counters` — they pollute the git-log ↔ roadmap reconciliation used by `scripts/next_brief.py`. Put the reference in the commit body or omit it.
- Standing rule: `python scripts/sync_status.py` at end of every brief (already enforced)
- The auto-sync script does NOT touch tech-stack tables, pricing rows, status callouts, or the endpoint table rows in `docs/API_ENDPOINTS.md`. See the docstring of `scripts/sync_status.py` for the full list of auto-sync limits.

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
- Brief types: A = feature, B = bugfix, C = catalog/content, D = audit/docs. Each type has its **own counter** (B161 and D161 can coexist; never reuse a number within a type). **Always get the number from `python scripts/next_brief.py`** — it scans the roadmap and `git log --all`; never guess from the roadmap alone.
- Push at end of session: `git add -A && git commit -m 'description' && git push`

## Session isolation (parallel Claude sessions)

More than one Claude session can be open on this repo: they share **one** working tree, index and HEAD.
Incident history behind these rules: `docs/SESSION_ISOLATION.md`.

- **Preflight every brief:** `git status --short` (must be empty) and `git branch --show-current` (must be `main`). It is a point-in-time check, not protection.
- **Any brief that will produce a commit → dedicated worktree, always:** `python scripts/start_brief.py <BRIEF-ID> <slug>` (or `git worktree add ../climb-agent-<brief> -b brief/<ID>-<slug> origin/main`). The `pre-commit` hook blocks commits on a non-`main` branch in the primary worktree (override `ALLOW_PRIMARY_BRANCH_COMMIT=1` only when you mean it).
- **Never `git add -A` when the tree was not clean at brief start** — stage explicit paths.
- **Never `git checkout` / `git switch` in a shared tree** — it moves HEAD for the other session.
- A worktree needs a real `npm ci` in `frontend/` (symlinked `node_modules` fails the build).
- `backend/data/user_state.json` is a tracked fixture the suite rewrites: keep it out of commits.
- Cleanup after merge: `git worktree remove ../climb-agent-<brief>`, then delete the branch.
- Untangling mixed commits (other session stopped): procedure in `docs/SESSION_ISOLATION.md`.

## Branch workflow

Obbligatorio, per non intrappolare gli utenti PWA su una build rotta:

- **Backend-only** (nessun file `frontend/`): commit + push diretto a `main`. Railway redeploya in 1-2 min.
- **Tocca `frontend/`** (anche un file solo) o **misto**: branch `brief/B<n>-<slug>`, preview Vercel buildata e **testata** (desktop e, se rilevante, PWA su iPhone), **OK esplicito di Daniele PRIMA del merge**. Senza preview gli utenti iPhone restano sul vecchio Service Worker.
- Le preview chiamano il backend prod senza configurazione: il CORS regex `https://climb-agent(-[a-z0-9-]+)?\.vercel\.app` è live (B196-CORS).
- Service Worker: `frontend/public/sw.template.js` → `public/sw.js` per build (`frontend/scripts/build-sw.js` inietta `VERCEL_GIT_COMMIT_SHA` in `CACHE_NAME`). Non committare `sw.js`, non bumpare `CACHE_NAME` a mano.

## Lessons learned

After completing a task, if you encountered unexpected behavior, made a mistake
that required correction, or discovered a non-obvious pattern, check
`docs/lessons.md` (recent) and `docs/lessons/` (monthly archive) for existing lessons first, then append any NEW lessons to `docs/lessons.md` with
format:
- **[YYYY-MM-DD] [BRIEF-ID or context]**: One-line lesson.

Do NOT duplicate existing lessons. Keep each entry to one line.
This is optional — only add genuine lessons, not routine observations.
