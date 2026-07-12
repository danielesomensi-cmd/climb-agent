# B-COACH-CONTEXT-FIX — Coach context inventory audit

> Phase 1 deliverable (read-only). Date: 2026-07-12.
> Scope: what the coach's user-context block (`backend/coach/prompt_builder.py::build_user_context`) actually contains vs. what the engine knows.
> Origin: field test 2026-07-12 — coach blind to a planned outdoor day (Berdorf) + mixed-language reply.

## Context block today (A-COACH-V1a)

Sections assembled by `build_user_context`: **Athlete profile** (`_profile_section`), **Goal & plan position** (`_plan_section`), **Current week plan** (`_week_section`), **Today's session detail** (`_today_section`), **Training logs last 14d** (`_logs_section`), **Equipment** (`_equipment_section`).

## Inventory table

| # | Data domain | Available in engine (where) | In coach context | Verdict |
|---|---|---|---|---|
| 1 | **Profile: grades, body, age** | `assessment.grades` (lead/boulder RP+OS, Font), `assessment.body` / `body` | **Yes** — `_profile_section` | OK. Note: `performance.current_level` (evolving level, updated by logs) is NOT included — only onboarding-time assessment grades. Minor staleness risk. |
| 2 | **Assessment / radar** | `assessment.profile` (5-axis 0-100), `assessment.last_assessed` | **Partial** — axes + 2 weakest axes in; **assessment date missing** | GAP (minor). Coach can't say "your assessment is 3 months old". +~10 tok. Relevance **M**. |
| 3 | **Baselines / maximals** | `baselines.hangboard` (list: edge_mm, grip, hang_seconds, max_total_load_kg, source, estimated_at), `baselines.pulling`, `assessment.tests` (e.g. `max_hang_20mm_7s_total_kg`) | **No** | **GAP**. Coach discusses finger strength with zero actual numbers. +~60–120 tok. Relevance **H**. |
| 4 | **Progression state / working loads** | `working_loads.entries` (per-exercise current load, written by `progression_v1`) | **No** | **GAP**. Coach can't answer "what load am I on for max hangs?". Variable size — cap needed (e.g. 15 most recent entries). +~100–200 tok. Relevance **M/H**. |
| 5 | **Macrocycle** | `goal`, `macrocycle` (phases, start/end, total_weeks) | **Yes** — `_plan_section` (goal, deadline, phase seq, week N of M, paused flag) | OK. |
| 6 | **Week plan (guided sessions)** | `read_week_plan()` → `days[].sessions[]` with status | **Yes** — `_week_section` | OK for guided sessions only — see #7. |
| 7 | **Outdoor days (planned)** — **BUG-1** | Day-level fields on week-plan days: `outdoor_spot_name`, `outdoor_discipline`, `outdoor_session_status` (set by replanner `add_outdoor` / outdoor intents) + `outdoor_slot` (planner, availability-driven). Also `state.trips` (future trips), `pretrip_deload`, `other_activity`/`other_activity_name` | **No** — `_week_section` and `_today_section` iterate only `day["sessions"]`; a day with an outdoor plan and no guided session renders as **"rest"** | **CRITICAL GAP — root cause of BUG-1 confirmed.** The coach is not hallucinating; the data never reaches it. Same blindness for `other_activity` days (yoga etc.) and `pretrip_deload`. +~30–60 tok. Relevance **H**. Pre-approved fix. |
| 8 | **Today's resolved session** | `sessions[].resolved.resolved_session.exercise_instances` with prescriptions | **Yes** — `_today_section` (sets/reps/load per exercise) | OK (guided only; outdoor today invisible → covered by FIX-1). |
| 9 | **Logs (last 14d)** | `session_completion_log` + `feedback_log` enrichment; `free_sessions`; outdoor logs via `storage.read_outdoor_logs` | **Yes** — all three sources in `_logs_section` | OK — **logged** outdoor already visible; the gap is only **planned** outdoor (#7). `other_activity` completions not logged anywhere → out of scope. |
| 10 | **Equipment profile** | `equipment.home`, `equipment.gyms[].equipment`, `preferences.finger_training_device` | **Yes** — `_equipment_section` | OK. |
| 11 | **Weather** | `/api/weather` (OpenWeatherMap live, `weather_v1.condition_band` deterministic bands) — shown on `/today` | **No** | GAP (inventory only — fix deferred to **A-COACH-V1b** per brief). Injection feasible: needs lat/lon (spot or user location) + async HTTP call in prompt path (latency + failure handling). +~40 tok. Relevance **M** (H on outdoor days). |
| 12 | **Fatigue / readiness** | `feedback_log` difficulty labels (partially in via #9), `fatigue_proxy` + `stimulus_recency` (closed_loop internals), `weekly_load_summary.planned_load` | **Partial** — per-session "felt" labels ride the log lines; no aggregate signal, no load-vs-target | GAP (minor). `fatigue_proxy`/`stimulus_recency` are engine-internal — surfacing raw values risks the D-ID firewall spirit. A one-line planned-load summary would be cheap (+~20 tok). Relevance **M/L**. |

Also not in context (unrequested but noted): `availability` / `planning_prefs` (+~30 tok, relevance L/M — coach can't reason "you train 3 days/week"), `trips` (+~20 tok/trip, relevance M — ties into #7), `limitations` (already in ✓).

## Proposed fixes

| Fix | Domains | Status |
|---|---|---|
| FIX-1: planned outdoor days in week + today sections (spot, discipline, status), incl. `other_activity` and `pretrip_deload` day markers; trips line in plan section | #7 | **Pre-approved** |
| FIX-2: language rule — match user's language (Option A, recommended) or reinforced English-only (Option B); single language per reply | BUG-2 | **Pre-approved**, A/B choice at STOP gate |
| FIX-3: baselines/maximals section | #3 | Needs OK |
| FIX-4: working loads (capped) | #4 | Needs OK |
| FIX-5: assessment date line | #2 | Needs OK |
| FIX-6: planned-load week summary line | #12 | Needs OK |
| Weather injection | #11 | Deferred to A-COACH-V1b (note added to roadmap item) |

Total added cost if ALL approved: ~250–400 tokens on a ~3–5k dynamic block — well inside the 25k budget guard.

## Phase 3 — live re-test (before/after)

Same failing conversation replicated locally (state with a planned outdoor day at Berdorf today, lead, status planned; query **"Cosa faccio oggi?"**; real LLM call, COACH_MODEL default).

**Before (field test 2026-07-12, prod):** context rendered the day as *"rest"* → coach replied *"Today is a rest day"* and, when challenged, doubled down (*"There's no Berdorf session in the plan"*). Replies mixed Italian and English.

**After (fix, 2026-07-12):** context today-section renders:

```
## Today's session detail
- OUTDOOR climbing at Berdorf [planned, lead]
  (This planned outdoor day IS today's main session — never tell the user today is a rest day.)
```

Coach reply opens with *"Oggi sei a Berdorf — è la tua sessione principale della settimana 1 di Base."* and gives an outdoor-day structure (warm-up, volume range, technical cue, stop criteria). Entirely in Italian, single language. **PASS** on all three criteria: outdoor day acknowledged, no rest-day claim, language matched.

Approved scope at the STOP gate (2026-07-12): FIX-1, FIX-2 **Option A**, FIX-3, FIX-4, FIX-5, FIX-6 — all implemented. Test suite: 2386 passed (7 new).

## BUG-2 note (language)

`INSTRUCTION_BLOCK` line: *"Always respond in English, regardless of the language the user writes in."* Field test shows the instruction doesn't hold against Italian input (mixed-language replies). Option A (match user language) aligns instruction with observed model behaviour instead of fighting it.
