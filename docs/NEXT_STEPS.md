# NEXT STEPS — climb-agent

> Generated: 2026-02-16
> Based on: PROJECT_BRIEF.md, CLAUDE.md, BACKLOG.md, full codebase analysis

---

## 1. CURRENT STATE

### What works end-to-end

| Layer | Status | Detail |
|-------|--------|--------|
| **Assessment** | Working | 6-axis profile (0-100), grade-based benchmarks, repeater test integration |
| **Macrocycle** | Working | Hörst 4-3-2-1 + DUP, 5 phases, 10-13 weeks, deload (programmed + adaptive + pre-trip) |
| **Weekly planner** | Working | planner_v2: 2-pass phase-aware, domain weights, session pool cycling, hard cap + finger spacing |
| **Session resolver** | Working | 29 sessions resolve to concrete exercises from 102-exercise catalog, 11 templates, inline blocks + template refs |
| **Replanner** | Working | 12 intents, day override with ripple, mark_done/skipped, move_session, set_availability. `_reconcile()` enforces constraints on all codepaths |
| **Feedback** | Partial | POST /api/feedback updates working_loads + stimulus_recency + fatigue_proxy. Does NOT trigger replanning (B25) |
| **Progression** | Working | Load-based (hangboard, weighted pullup) and grade-based (bouldering) progression with feedback-driven adjustments |
| **Adaptation** | Partial | Multiplier-based system exists (`adaptation/closed_loop.py`) but not fully integrated into the main feedback→replan flow |
| **Week plan caching** | Working | `current_week_plan` persisted in user_state.json, survives navigation. Cache invalidation on macrocycle/onboarding |
| **API** | Working | FastAPI, 9 routers, 15 endpoints + health, CORS for Next.js |
| **Frontend** | Working | Next.js 14 PWA, 19 pages: onboarding (12 steps), today, week, plan, session, settings. Dark mode, mobile-first |
| **Tests** | 188 green | Fixture-isolated (B26), covers engine + API + resolver + replanner |

### The full loop a user experiences today

1. Onboarding wizard (12 steps) → assessment profile + macrocycle generated
2. `/today` shows today's session with resolved exercises (sets/reps/load)
3. User marks done or skipped → status persists across navigation
4. User can replan any day (override intent) or skip
5. `/week` shows 7-day grid with all sessions
6. `/plan` shows radar chart + macrocycle timeline
7. `/settings` allows regenerate assessment/macrocycle or reset
8. POST /api/feedback records session outcome → updates working_loads for next resolve

### What's missing in the loop

- **No plan-level adaptation after feedback** — feedback updates loads but doesn't restructure the week (B25)
- **No guided execution** — user sees exercises but has no timer/rest tracking
- **Evening sessions are thin** — 2-3 blocks instead of literature-recommended 5-7 (B8)
- **No outdoor logging** — can't record crag sessions (B2)

---

## 2. OPEN BACKLOG

| ID | Title | Priority | Effort | Dependencies | Notes |
|----|-------|----------|--------|--------------|-------|
| **B1** | Standalone core session | Medium | Small | None | Subsumed by B8 |
| **B2** | Outdoor sessions / logging | Low | Large | Trip planning, feedback schema | Phase 2, different schema from resolved sessions |
| **B3** | Plan validation vs literature | Medium | Small | None | Documentary, subsumed by B8 |
| **B4** | Load score / weekly fatigue | Medium | Medium | Session load hints | Subsumed by B8, needed for adaptive deload |
| **B8** | Session enrichment + modules | **High** | **Large** | Resolver inline blocks (done), exercise catalog (partial) | Umbrella for B1+B3+B4. Evening 5-7 blocks, new templates |
| **B10** | Outdoor climbing spots | Low | Medium | B2 | Depends on outdoor session support |
| **B11** | Configurable test protocols | Medium | Small | None | 5s vs 7s hang, 1RM vs 2RM pullup conversions |
| **B19** | Quick-add session | Medium | Medium | Replanner events (done) | New event type + frontend dialog |
| **B20** | Edit availability from Settings | Medium | Small | Settings page (done), set_availability (done) | Frontend form + API call |
| **B25** | Adaptive replanning after feedback | **High** | **Medium** | Feedback system (done), replanner (done) | Closes the feedback→plan loop |

**Summary**: 10 open items. 2 high priority (B8, B25), 5 medium, 3 low.

---

## 3. CANDIDATE NEXT PHASES

### Candidate A: Adaptive Replanning / Closed-Loop Feedback (B25)

**What it delivers to the user:**
After completing a session and submitting feedback ("that was way too hard"), the week plan automatically adjusts — next hard day might become recovery, or intensity drops. The app stops being a static schedule and becomes a reactive coach.

**Scope:**

| Area | Changes |
|------|---------|
| `backend/api/routers/feedback.py` | After `apply_feedback` + `apply_day_result_to_user_state`, evaluate whether replanning is needed (fatigue threshold, hard-feedback streak) |
| `backend/engine/replanner_v1.py` | New function: `adapt_after_feedback(plan, state)` — checks fatigue_proxy + recent feedback, may downgrade next hard sessions or insert recovery |
| `backend/engine/adaptation/closed_loop.py` | Integrate multiplier system into resolve-time `inject_targets()` so load adjustments compound correctly |
| `backend/api/routers/week.py` | No change needed (cached plan already updated via replanner) |
| Frontend: `FeedbackDialog` | Show "Plan adjusted" toast when feedback triggers replanning |
| New tests | ~8-10: feedback triggers replan, fatigue threshold, no-op on mild feedback, edge cases |

**Estimated files**: 4-5 modified, 0-1 new. ~8-10 new tests.
**New API endpoints**: 0 (extends existing POST /api/feedback).
**Risk**: Medium. The hard part is defining the threshold — when should feedback trigger replanning vs just adjusting loads? Over-reactive replanning could feel chaotic. Under-reactive defeats the purpose. Needs clear rules (e.g., "2+ very_hard in 3 days → downgrade next hard session").

---

### Candidate B: Guided Session Timer Mode

**What it delivers to the user:**
A step-by-step workout execution screen with automatic timers, rest tracking, and color-coded rest feedback. User opens a session and follows along exercise-by-exercise — the app beeps when hang time is up, counts rest periods, and logs actual vs planned.

**Scope:**

| Area | Changes |
|------|---------|
| Frontend: new page `/session/[id]/guided` | Full guided mode UI: exercise display → start → timer/chronometer → rest timer (green/yellow/red) → next exercise → session complete |
| Frontend: components | `TimerDisplay`, `RestTimer`, `ExerciseStep`, `SessionProgress` |
| Frontend: `types.ts` | `GuidedSessionState` type (current_exercise, current_set, timer_state, actual_durations) |
| `backend/api/routers/feedback.py` | Accept richer `actual` payload with per-exercise timing data |
| `backend/api/models.py` | Extend `FeedbackRequest.log_entry.actual` schema for timing data |
| `backend/data/schemas/` | Update JSON schema for log validation |
| New tests | ~5-6: timing data round-trip, feedback with timing, guided session state management |

**Estimated files**: 6-8 new (frontend components + page), 2-3 modified (backend). ~5-6 new tests.
**New API endpoints**: 0 (uses existing feedback endpoint with richer payload).
**Risk**: Low-medium. Mostly frontend work. The timer logic is self-contained. Main risk is getting the UX right (vibration/beep on mobile PWA, background timer behavior, screen-off handling). No engine changes needed — it consumes the already-resolved session data.

**Dependencies**: None hard. Works with existing resolved sessions.

---

### Candidate C: Exercise Catalog Expansion + Session Enrichment (B1, B3, B4, B8)

**What it delivers to the user:**
Evening sessions go from 2-3 blocks to 5-7 blocks, matching real climbing training structure: warmup → finger → pulling strength → wall climbing → core → antagonist/prehab → cooldown. New templates for pulling strength (weighted pullup, lock-off), antagonist/prehab (push-up, dip, rotator cuff), and limit bouldering. Core and antagonists become standard in every evening session.

**Scope:**

| Area | Changes |
|------|---------|
| `backend/catalog/exercises/v1/exercises.json` | Add ~15-20 exercises: more pulling variants, antagonist exercises, additional core progressions |
| `backend/catalog/templates/v1/` | 3-4 new templates: `pulling_strength.json`, `antagonist_prehab.json`, `limit_bouldering.json`, `core_standard.json` |
| `backend/catalog/sessions/v1/` | Rewrite evening sessions to 5-7 modules: `strength_long.json`, `power_contact_gym.json`, `power_endurance_gym.json`, etc. Add `core_conditioning_home.json` (B1) |
| `backend/engine/planner_v2.py` | Update `_SESSION_META` if new sessions added, adjust session pool per phase |
| `backend/engine/replanner_v1.py` | Update `INTENT_TO_SESSION` if new intents needed |
| `docs/vocabulary_v1.md` | Add any new equipment IDs, domains, or patterns |
| Load score (B4) | Add `estimated_load_score` field to session metadata or compute from modules |
| Literature validation (B3) | Document alignment with Hörst, Lattice, Eva López in session-level comments |
| New tests | ~15-20: resolver tests for new templates, session enrichment validation, load score computation |

**Estimated files**: 20-30 modified/new (mostly catalog JSON). ~15-20 new tests.
**New API endpoints**: 0.
**Risk**: Medium-high. This is the largest scope. Risk of breaking existing resolver tests if session structure changes significantly. Needs careful migration — all 29 existing sessions must continue to resolve. The exercise catalog expansion is safe (additive), but session restructuring needs a plan for backwards compatibility with any cached `current_week_plan`.

**Dependencies**: Resolver inline blocks (done). Pulling/antagonist exercise catalog (partial — needs expansion first).

---

## 4. RECOMMENDATION

### Tackle Candidate A (B25: Adaptive Replanning) next.

**Reasoning:**

1. **Closes the most critical gap in the user experience.** Right now the app generates a plan and the user executes it, but feedback doesn't change the plan. This is the #1 thing that makes the app feel "dumb" — you tell it you're exhausted and tomorrow's plan stays the same. Fixing this delivers the core promise of "closed-loop" training.

2. **Smallest scope with highest user impact.** ~4-5 files, ~8-10 new tests, no new API endpoints, no frontend pages to build. Compare to Candidate C (20-30 files) or Candidate B (6-8 new frontend files). The ROI is the best.

3. **Infrastructure already exists.** `closed_loop_v1.py` tracks fatigue_proxy and stimulus_recency. `progression_v1.py` already adjusts loads. `adaptation/closed_loop.py` has the multiplier system. The replanner's `apply_events` already handles plan modifications. All the pieces are there — they just need to be wired together.

4. **Unblocks future phases.** Candidate C (session enrichment) benefits from having adaptive replanning in place — richer sessions generate more feedback signals that the adaptation system can act on. Candidate B (guided timer) also benefits — it captures richer actual-vs-planned data that feeds directly into the adaptation loop.

5. **Low risk.** The main design decision (when to trigger replanning) can start conservative: only trigger on `very_hard` or `very_easy` feedback, only affect the next 1-2 days, and only downgrade (never upgrade) without user confirmation. This is safe to ship and iterate on.

**Suggested implementation order within B25:**
1. Define feedback-to-replan trigger rules in engine (threshold logic)
2. Wire `feedback.py` to call replanner after `apply_day_result_to_user_state`
3. Integrate `adaptation/closed_loop.py` multiplier into `inject_targets()` at resolve time
4. Add frontend toast notification when feedback triggers replanning
5. Write tests for all trigger/no-trigger scenarios

**After B25**, the natural next step is **Candidate C** (session enrichment) to make the sessions themselves richer, then **Candidate B** (guided timer) to complete the execution experience.
