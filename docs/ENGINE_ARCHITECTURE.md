# ENGINE_ARCHITECTURE.md — How the Engine Works

> **Last verified:** 2026-03-27 (D163); §3 Macrocycle and §4 Weekly Planner re-verified against the code on 2026-11-12 (D287)
> This doc explains the **implementation** of the engine — the "how and where."
> For methodology and rationale → see `DESIGN_GOAL_MACROCICLO_v1.1.md`
> For canonical enum values and schemas → see `vocabulary_v1.md`

---

## Table of Contents

1. [Data Flow Overview](#1-data-flow-overview)
2. [Assessment Module](#2-assessment-module)
3. [Macrocycle Generator](#3-macrocycle-generator)
4. [Weekly Planner](#4-weekly-planner-planner_v2)
5. [Session Resolver](#5-session-resolver)
6. [Exercise Selection — P0 Filter Chain](#6-exercise-selection--p0-filter-chain)
7. [Progression Engine](#7-progression-engine)
8. [Closed-Loop Adaptation](#8-closed-loop-adaptation)
9. [Replanner](#9-replanner)
10. [Exercise Ordering](#10-exercise-ordering)
11. [Catalog File Structure](#11-catalog-file-structure)
12. [Key Data Structures Reference](#12-key-data-structures-reference)
13. [Cross-Module Dependencies](#13-cross-module-dependencies)

---

## 1. Data Flow Overview

```
user_state.assessment + user_state.goal
    │
    ▼
compute_assessment_profile()          ← assessment_v1.py
    │  reads: assessment.tests, assessment.body, assessment.grades, goal
    │  writes: 5-axis profile {finger_strength, pulling_strength, power_endurance, technique, endurance}
    ▼
generate_macrocycle()                 ← macrocycle_v1.py
    │  reads: goal, assessment_profile, user_state.trips, start_date
    │  writes: macrocycle dict (phases[], domain_weights, session_pools, intensity_caps)
    ▼
generate_phase_week()                 ← planner_v2.py  (called per week)
    │  reads: macrocycle phase, availability, gyms, equipment, planning_prefs
    │  writes: week_plan dict (7 days × sessions with session_id, slot, location, gym_id)
    ▼
resolve_session()                     ← resolve_session.py  (called per session)
    │  reads: session JSON → template JSONs → exercises.json + user_state
    │  writes: resolved session (exercise_instances with prescriptions)
    ▼
inject_targets()                      ← progression_v1.py
    │  reads: user_state.baselines, user_state.adjustments, exercise load_models
    │  writes: suggested loads, target grades, working load entries into instances
    ▼
sort_exercises_by_phase()             ← exercise_ordering.py
    │  reorders exercise_instances by phase-aware priority
    ▼
[user performs session via guided UI]
    │
    ▼
apply_feedback()                      ← progression_v1.py
    │  reads: exercise outcomes (difficulty, actual loads)
    │  writes: user_state.baselines, test results, working_loads (per-exercise
    │          load progression — the reactive load adjustment)
    ▼
[next week → generate_phase_week() uses updated user_state]
```

---

## 2. Assessment Module (`assessment_v1.py`)

**Entry point:** `compute_assessment_profile(assessment, goal) → Dict[str, int]`

**Input fields read from `user_state`:**
- `assessment.tests.max_hang_20mm_7s_total_kg` (or 5s variant)
- `assessment.tests.max_weighted_pullup_2rm_kg`
- `assessment.tests.max_pullups_bw`
- `assessment.tests.repeater_7_3_reps`
- `assessment.body.bodyweight_kg`
- `assessment.grades.current_lead` / `current_boulder`
- `assessment.grades.onsight_lead` / `onsight_boulder`
- `assessment.experience.climbing_years`
- `assessment.self_eval.*` (per-axis self-assessment 1-5)
- `goal.target_grade`

**Output:** 5-axis profile dict, each axis 0-100:
```python
{"finger_strength": 72, "pulling_strength": 58, "power_endurance": 45, "technique": 63, "endurance": 51}
```

**How normalization works:**
1. Each axis has a benchmark table indexed by `target_grade` (hardcoded in `assessment_v1.py:_FINGER_BENCHMARK`, `:_PULLING_BENCHMARK`, `:_PE_REPEATER_BENCHMARK`).
2. The user's test result is compared to the benchmark for their target grade as a ratio.
3. The ratio is scaled to 0-100 via `_clamp()`.
4. When test data is missing, self-eval (1-5 scale) provides a coarser estimate.
5. `technique` is computed from the onsight-vs-redpoint grade gap + self-eval.
6. `endurance` combines power_endurance score, climbing experience, self-eval, and optional test data.
7. `brzycki_1rm()` estimates 1RM from 2RM test data (Brzycki formula, `assessment_v1.py:line ~160`).

**Cross-ref:** `DESIGN_GOAL_MACROCICLO_v1.1.md §2` for why these 5 axes were chosen and the scientific rationale.

---

## 3. Macrocycle Generator (`macrocycle_v1.py`)

**Entry point:** `generate_macrocycle(goal, assessment_profile, user_state, start_date, total_weeks, *, from_phase) → Dict`

### What it reads
- `goal.goal_type`, `goal.discipline` (`lead` / `boulder` / `all_round` / `both`; missing → `lead` with a warning), `goal.target_grade`, `goal.target_boulder_grade`, `goal.current_grade`, `goal.deadline`
- `assessment_profile` — 5-axis scores (0-100); durations and weights read four of them (`technique` is no longer an input, A270)
- `user_state.planning_prefs.phase_weeks` — per-phase week counts the athlete asked for (A284)
- `user_state.trips` — only for the `pretrip_deload` annotation of a phase (see *Deload and trips*)
- `user_state.macrocycle` — when `from_phase` is set (incremental regeneration)

### What it produces
A macrocycle dict with:
- `macrocycle_version`, `generated_at`, `start_date`, `end_date`, `total_weeks`
- `phases[]` — ordered list of 5 phase dicts
- Each phase: `{phase_id, phase_name, start_week, end_week, duration_weeks, energy_system, domain_weights, session_pool, intensity_cap, notes}` (+ `pretrip_deload` when a trip starts in or near it)
- `goal_snapshot`, `assessment_snapshot` — frozen copies at generation time
- `warnings` — only when `_validate_goal` returns some

### Phase duration logic

`_compute_phase_durations(profile, total_weeks, discipline, *, phases, phase_overrides)`. Hardcoded tables in `macrocycle_v1.py` — `boulder` has its own, every other discipline uses the lead ones:

| | base | strength_power | power_endurance | performance | deload |
|---|---|---|---|---|---|
| Lead default (`_BASE_DURATIONS_LEAD`, 12 weeks) | 4 | 3 | 2 | 2 | 1 |
| Lead cap (`_PHASE_CAPS_LEAD`) | 4 | 4 | 3 | 3 | 2 |
| Lead floor (`_PHASE_FLOORS_LEAD`) | 2 | 2 | 2 | 2 | 1 |
| Boulder default (`_BASE_DURATIONS_BOULDER`, 10 weeks) | 2 | 4 | 1 | 2 | 1 |
| Boulder cap (`_PHASE_CAPS_BOULDER`) | 4 | 5 | 3 | 3 | 2 |
| Boulder floor (`_PHASE_FLOORS_BOULDER`) | 2 | 2 | 1 | 2 | 1 |

For a full cycle `total_weeks` must be at least 11 for lead (`_MIN_TOTAL_WEEKS_LEAD`) and 8 for boulder (`_MIN_TOTAL_WEEKS_BOULDER`); in every scope it must lie between the sum of the floors and the sum of the caps of the phases in scope (a pinned phase counts for its fixed size) and never exceed 16 (`_MAX_TOTAL_WEEKS`) — otherwise `ValueError`.

Steps, in order:
1. **Defaults** for the phases in scope.
2. **Overrides (A284):** `planning_prefs.phase_weeks` = `{phase_id: weeks}`, each an int within [floor, cap] (else `ValueError`). An overridden phase is **locked**: steps 3–4 never move it.
3. **Weakness shift** (`_WEAKNESS_ADJUSTMENTS`): `_find_weakest_axis` reads `power_endurance`, `endurance`, `finger_strength`, `pulling_strength` (missing = 50). If the weakest scores < 50, one phase gets +1 week and another −1:
   ```python
   "power_endurance"  → extend power_endurance, shrink strength_power
   "endurance"        → extend base, shrink strength_power
   "finger_strength"  → extend strength_power, shrink base
   "pulling_strength" → extend strength_power, shrink base
   ```
   Only when both phases are in scope and unlocked, the extended one stays ≤ its cap and the shrunk one ≥ its **auto floor** (`_AUTO_FLOORS_*` = the floors, except lead `base` = 4: the athlete may ask for a 2-week base, the engine never shortens it by itself). Otherwise a clean no-op — on lead only the `power_endurance` shift can apply, because `base` sits at both its cap and its auto floor. The table still carries a `technique` row that nothing reaches (A270).
4. **Surplus / shortfall:** the weeks missing to `total_weeks` are handed out in `_SURPLUS_PRIORITY_*` order up to the caps (lead: performance, strength_power, power_endurance, deload — never `base`; boulder: performance, strength_power, power_endurance, base, deload); weeks in excess are taken back in the reverse order down to the auto floors. There is no flex phase; `ValueError` when it does not fit.

### from_phase="current" behavior

When regenerating from a specific phase (the router `backend/api/routers/macrocycle.py` resolves `"current"` to the phase in progress with `current_phase_and_week()`; the engine receives a phase id):
1. Phases before `from_phase` (in `PHASE_ORDER`) are **kept verbatim** from the existing macrocycle.
2. `_compute_phase_durations(..., phases=<from_phase onward>, phase_overrides=...)` allocates `total_weeks` minus the weeks of the kept phases — the same steps as above, restricted to the phases in scope.
3. The start week continues from where kept phases ended.

`ValueError` when there is no existing macrocycle or the phase id is unknown.

### Monday invariant

`start_date` is auto-adjusted to the previous Monday if it's not already one:
```python
if start.weekday() != 0:
    start -= timedelta(days=start.weekday())
```
This happens in both `generate_macrocycle()` and `generate_phase_week()`.

### Domain weight adjustment

`_adjust_domain_weights(base_weights, profile)` modifies the phase's base weights (`_BASE_WEIGHTS`; `_BASE_WEIGHTS_BOULDER` for `boulder`), per axis (missing = 50):
- Score < 35 → +0.10 to the relevant domain
- Score 35–49 → +0.05
- Score > 75 → -0.03 (min 0.02)
- Then renormalize to sum = 1.0 (3 decimals)

Axis-to-weight mapping:
```python
"finger_strength"  → "finger_strength"
"pulling_strength" → "pulling_strength"
"power_endurance"  → "power_endurance"
"endurance"        → "volume_climbing"
```
The `technique` and `core_prehab` weights are fixed per phase — only the renormalization moves them. The technique axis stopped driving the weights with A270 / D266.

### Session pool construction

`_build_session_pool(phase_id, discipline, assessment_profile)` returns an ordered list: **primary** sessions (sorted alphabetically) first, then **available** sessions (same order). The pool definitions are hardcoded in `_SESSION_POOL` (lead) and `_SESSION_POOL_BOULDER`; `all_round` / `both` merge the two (primary in either stays primary). A258 (`_PROFILE_CONDITIONAL_SESSIONS`): `pulling_strength_gym` joins the `strength_power` pool as primary when `pulling_strength` < `WEAK_AXIS_THRESHOLD` (50), in every discipline.

### Deload and trips

- **The deload form (A328, D288 R3 — decided 2026-11-13).** The terminal deload keeps a reduced dose of each key stimulus instead of removing all hard work (one week of cessation costs strength, Coleman 2024; strength is kept on a low volume if the relative load is kept, Spiering 2021 — engineering constants, no climbing data). `macrocycle_v1.DELOAD_*`:
  - **the same climbing days as a normal week** of the same availability: PASS 1 fills every kept day that has a climbing venue with the form — `DELOAD_TECHNIQUE_SESSION` (`technique_focus_gym`, ×1), then the easy fillers `DELOAD_FILLERS` (`easy_climbing_deload` ×4, `regeneration_easy` ×2: weekly limits valid in the deload only), budget one pool rotation per weekday;
  - **one finger exposure** `DELOAD_FINGER_SESSION` (`deload_finger_touch`: finger warm-up, 3 × 7 s `max_hang_7s`, easy climbing pinned with `pin_exhausted: skip` so it is skipped at home, finger prehab) — only when `generate_phase_week(deload_finger_exposure=True)`, which `week.py` passes for an athlete with a tested hang max (`anchored_load.is_anchored_and_tested`). Placed BEFORE PASS 1 on the first valid day from Monday: never in the last `DELOAD_TOUCH_LAST_DAYS` (3) days of the week (the 72 h before a test opening the next cycle), never within the finger gap of a finger day (previous week B161, lived days B390, crag days B382, the user's sessions B414). No day fits → `unmet_stimulus` row `{stimulus: "finger_strength", phase_id: "deload"}`. Meta: `finger` (48 h gap), not `hard` (the hard cap stays 0), intensity `medium`;
  - **sets × 0.5**: the technique drills declare `deload_sets: 0.5` (A312's factor form, `resolve_session._apply_deload_sets`: a value in (0, 1) multiplies the picked exercise's own sets, rounded up, at least 1); the finger exposure has 3 sets (5 × 0.5 rounded up); the native deload sessions keep their light doses; the lunches keep A312 (no second cut); the bodyweight ladders keep their deload dose (−1 set);
  - **no** power-endurance intervals, tests, work to failure or weighted pull-ups (Daniele, 2026-11-13: heavy pulling stays out of the deload). `finger_aerobic_base` leaves the complementary pool when the finger exposure is there.
  - **Where the form lives:** in code, read whenever `phase_id == "deload"`, whatever the saved pool and cap say — an existing macrocycle keeps its old `session_pool` / `intensity_cap: low` in `phases[]`. Two sources then exist: the form (climbing days) and the saved pool (complementary sessions); the deload week's `profile_snapshot.session_pool` records both (form first). `_SESSION_POOL[...]["deload"]` lists the two sessions too, for new macrocycles; `DELOAD_ABOVE_CAP` names the two sessions placed above the `low` cap.
  - **Load and closed loop:** see §8.1 (the deload hang = the previous phase's anchored load × `DELOAD_LOAD_FACTOR` 0.90, feedback frozen).
- `apply_deload_week(week_plan)` — called by `generate_phase_week` when `phase_id == "deload"`, as a safety net: drops every session tagged `hard` (none is placed), sets `phase = "deload"` and `targets = {hard_days: 0, finger_days: <days with a finger session>}`. A328: no session cap any more (B160c capped the week at 5 sessions, which cut the climbing days R3 keeps); nothing is replaced.
- **Reduced week on a trigger (R3-b, A328 b) — `reduced_week.py`, alert only.** Inside the cycle there is no calendar unload. `suggestion(state, today, requested=False)` (pure, no clock, no writes) → `{suggested, week_start, reasons[], skipped, detail, form}`. Reasons: `very_hard_7d` (≥ `VERY_HARD_MIN` 2 sessions with `difficulty: very_hard` in `session_completion_log` in the `VERY_HARD_WINDOW_D` 7 days up to today — not `feedback_log`, which keeps 7 entries), `pain_block` (a `progression_counters.pain_blocks` block active today with score ≥ 2, any site — `anchored_load.pain_for`'s reading), `athlete_request` (the caller says so: only the coach, `scripts/athlete_context.py --reduced-week`; no app path, R3-c out of scope). Silent (`skipped`) with `recent_taper` (an A281 taper window [T−14, T−1] in the `TAPER_LOOKBACK_D` 35 days up to today, or running) or `deload_soon` (this week or the suggested one is the terminal deload). `week_start` = the first Monday on or after today; `form` = the deload form as data (same days, sets × 0.5, one finger exposure −10 %, short limit or technique, no PE, no test). Readers: `athlete_context` (`reduced_week`, warnings `REDUCED_WEEK_SUGGESTED` / `REDUCED_WEEK_SKIPPED`), the in-app coach block (`render_coach_block`, one line), `GET /api/week` (sibling `reduced_week` of the current week, only when suggested, with `message` = `alert_text`). Never persisted, never applied (A301 / B369): the athlete decides, through the coach's usual custom / remove flow.
- **Trip taper (A281)** — `compute_taper_windows(trips, week_start, week_end)` → `{"volume": {date: multiplier}, "no_hard": [dates]}`: volume ×0.6 on T-14..T-8 and ×0.4 on T-7..T-1 (`TAPER_WEEK1_VOLUME` / `TAPER_WEEK2_VOLUME`; the lower multiplier wins when trips overlap), no hard / max session on T-2..T (`TAPER_NO_HARD_DAYS` = 3). `backend/api/routers/week.py` passes `no_hard` to the planner as `pretrip_dates` and `volume` as `taper_volume`; the multiplier travels on the day (`taper_volume_multiplier`) and scales the sets of training work at resolution (`week.py::_apply_taper_volume`).
- The older 5-day helpers — `compute_pretrip_dates()`, `check_pretrip_deload()` and the `pretrip_deload` annotation `generate_macrocycle` puts on a phase (`_check_pretrip_overlap`) — are still in the module but no longer feed the planner.
- No adaptive phase duration: there is no feedback-driven phase extension or emergency deload. Overreach is handled per exercise by the closed loop (§8).

**Cross-ref:** `DESIGN_GOAL_MACROCICLO_v1.1.md §4` for Hörst 4-3-2-1 rationale, `§8` for deload model.

---

## 4. Weekly Planner (`planner_v2.py`)

The most complex module. Generates a 7-day plan for a single macrocycle week.

**Entry point:** `generate_phase_week(*, phase_id, domain_weights, session_pool, start_date, availability, ...) → Dict`

### `_SESSION_META` — The session metadata registry

Hardcoded dict in `planner_v2.py`. Maps every `session_id` to its planning properties:

| Field | Type | Meaning |
|-------|------|---------|
| `hard` | bool | Counts against the weekly hard-day cap; subject to the hard gap |
| `finger` | bool | Subject to the finger gap from other finger sessions (calendar days, see *Limits shared by the passes*) |
| `pulling` | bool? | Trains pulling — read by PASS 2.6 |
| `intensity` | str | `"low"` / `"medium"` / `"high"` / `"max"` — gated by phase cap |
| `climbing` | bool | **Hardcoded.** True = placed in Pass 1 alongside hard sessions |
| `location` | tuple | Allowed locations, e.g. `("gym",)`, `("home", "gym")` |
| `required_equipment` | list? | Equipment the session needs (e.g. `["hangboard"]`, `["gym_boulder"]`) |
| `preferred_equipment` | list? | Soft preference — defers to better-equipped days (B160d) |
| `max_per_week` | int? | Anti-repetition cap (default 1 if absent) |
| `test` | bool? | Assessment session — bypasses intensity cap in Pass 3 |
| `supplementary` | bool? | (In session JSON, not META.) Excluded from auto-planning, quick-add only |

`_SESSION_META` is the source of the planning flags of the engine's own sessions: PASS 1 – 2.6 and the legacy PASS 3 read `hard`, `finger`, `pulling`, `climbing`, `intensity` from it to choose and place them. A session with no entry (a custom session) is seen only by the code that reads `stimulus.session_flag` — the session's own `tags` first, else `_SESSION_META`: PASS 3a, PASS 2.7, the user / crag / lived-day anchors, the previous-week seed (B161, since B415), the presence check of the PASS 2.5 / 2.6 floors (B415) and `guards_v1`. Session JSONs may carry their own `supplementary` flag.

### `_INTENSITY_TO_LOAD`

Fallback load scores for unresolved sessions:
```python
{"low": 20, "medium": 40, "high": 65, "max": 85}
```
Used in `_make_session_entry()` to set `estimated_load_score` before resolution.

### Limits shared by the passes

Computed once, before PASS 1:

- **Intensity cap:** `intensity_cap`, else `PHASE_INTENSITY_CAP[phase_id]` (base `medium`, strength_power `max`, power_endurance `high`, performance `max`, deload `low`), filters the pool; what is left is split into `primary_pool` (`hard` or `climbing`, `_is_primary_session`) and `complementary_pool`. Tests and the phase-declared candidates of PASS 2.7 bypass it. A328: in deload the primary pool is the deload form (§3 *Deload and trips*: technique + easy fillers, the finger exposure placed first), above the `low` cap for `DELOAD_ABOVE_CAP` only; the `low` cap still filters the complementary sessions.
- **Hard-day cap:** `effective_hard_cap = min(hard_cap_per_week, planning_prefs.hard_day_cap_per_week)` — the argument defaults to 3 and `week.py` passes the same preference — and `0` in deload. Declared crag days (B382), lived hard days (B390) and the user's own hard sessions (B414) count against it before PASS 1.
- **Gaps are calendar days, not hours:** `hard_gap_days = finger_gap_days = ceil(1 × planning_prefs.recovery_multiplier)` (D83; default 1.0 → 1). A placement is refused when the distance in days from a hard (resp. finger-HIGH) day is `<= gap`: by default never on consecutive days. The slots are not read, so this is not a 48 h guarantee — an evening session and a morning one two days later are allowed. PASS 1 / 1.5 look backwards at the last hard / finger day (and at the anchors on both sides, `_near_anchor`); the later passes check any distance.
- **Finger-load tiers (A327, D288 R1):** `_SESSION_META.finger_load` (`high` on every finger entry, `low` on `finger_aerobic_base`; `finger ⇔ finger_load` pinned). `finger_day_offsets` holds the HIGH days only — the calendar rule above, unchanged. A LOW session needs `retest_policy.FINGER_LOW_GAP_H` (6 h) × `recovery_multiplier` from any finger session on the `complementary_v1.SLOT_HOUR` clock (a crag day is high 08:00-18:00), at most `FINGER_LOW_MAX_PER_DAY` (2) a day: one gate, `_finger_clock_ok(offset, slot, tier)`, read by every placement site once its slot is known (PASS 1, 1.5, 2, 2.2, the floors, 2.6, 3a through `_test_clock_ok` on the merged week, legacy PASS 3), against `finger_low_slots` / `finger_high_times`; a replaced low session leaves the clock (`_unbook_low`). Seeds read `stimulus.finger_load_of` (previous week, lived days, the user's sessions: a high user session is a calendar anchor, a low one sits on the clock). PASS 2.7 reads high for its calendar check and refuses any `finger_low_gap` through its alert check. **PASS 2 fix (D288 §1.3-1):** it placed finger sessions with no gap and no booking; it now applies the high calendar rule, the clock gate and books what it places. `targets.finger_days` still counts high + low.
- **Training days vs sessions:** `target_training_days_per_week` (default 4; under 18 capped at 4, D81) is how many **days** are kept — the others are pruned by *Day scoring for cap* (`day_pruned_but_available`). `target_sessions_per_week` (A283: an int 1–21, else ignored; raised to the target days; under 18 = the target days) is how many **sessions**, and only PASS 2.2 reads it.

### The multi-pass algorithm

Stages of `generate_phase_week` in execution order (the pass numbers are historical, not the order):

| # | Stage | `explain` label | What it does |
|---|-------|-----------------|--------------|
| 0 | PASS 1 (deload) | `pass1:deload_finger` | A328: the deload's finger exposure, tested athletes only |
| 1 | PASS 1 | `pass1:primary` | One primary session per kept day |
| 2 | PASS 1.5 | `pass1.5:climbing_fallback` | Climbing fallback on gym days without routes |
| 3 | PASS 2 | `pass2:complementary` | Complementary session on the empty kept days |
| 4 | PASS 2.2 | `pass2.2:extra_slot` | A second, non-hard session on multi-slot days |
| 5 | PASS 2.5 | `pass2.5:finger_floor` | Finger quality floor |
| 6 | PASS 2.6 | `pass2.6:pulling_maintenance` | Weekly pulling stimulus |
| 7 | PASS 3a | `pass3:retest_policy` | Tests decided by the retest policy (§8.2) |
| 8 | PASS 3 | `pass3:test_session`, `pass3:test_session_empty_day` | Legacy test injection |
| 9 | PASS 2.7 | `pass2.7:key_stimulus` | Key stimuli |
| 10 | A281 sweep | — | Drops hard / max sessions on pre-trip no-hard days |
| 11 | Plan build, deload | — | Day entries and summary; `apply_deload_week` in deload |
| 12 | Complementary pass | — | Fills the `role: "complementary"` slots (A300) |

#### PASS 1 — Primary sessions (hard + climbing)

**Day ordering:** Gym-available days first, then home-only, preserving weekday order within groups. This ensures climbing sessions (which need gym) get placed before home-only days are considered.

**Session iteration:** Round-robin through `primary_pool` (at most two cycles, one session per day) with constraint checks per session × day:
1. **Anti-repetition:** `max_per_week` cap (permanent skip, burns uses).
2. **Other-activity intensity reduction:** No hard sessions on days with other sports.
3. **Pre-trip deload:** No hard/max sessions on pretrip dates.
4. **Hard day cap:** `hard_days >= effective_hard_cap` (permanent skip).
5. **Finger spacing:** A finger-high session not within `finger_gap_days` of the last finger-high day; once the slot is known, the A327 clock gate (6 h around a low session).
6. **Anchors (B382 / B414):** Not within the gaps of a declared crag day or of a finger / hard session of the user's, on either side (`_near_anchor`).
7. **Hard spacing:** Not within `hard_gap_days` of the last hard day.
8. **Preferred equipment deferral (B160d):** If a session has `preferred_equipment` and this day's gym lacks it, check if a later day has it — if yes, defer.

On success: `_find_best_slot()` finds the best available slot (evening > morning > lunch for primary; a slot with `max_minutes` refuses a longer session), `_make_session_entry()` builds the plan entry.

**B161:** Previous week's trailing sessions seed the spacing constraints (negative offsets -7 to -1). A catalog session seeds with its meta AND its stored tags (unchanged); a session with no `_SESSION_META` entry — custom, coach ad-hoc, generated add — seeds with its own tags (`stimulus.session_flag`, as guards_v1 / B390 / B414 read it) unless it is `skipped` (B415, D287 C1: before, it was dropped, and a Sunday max-hang custom left Monday to limit_boulder_gym, which the guards then flagged).

#### PASS 1.5 — Climbing fallback

Triggers only when the pool has climbing sessions that all require `gym_routes` but the day's gym only has `gym_boulder`, on a day PASS 1 left empty. Injects fallback sessions from `_CLIMBING_FALLBACKS` = `("technique_focus_gym", "easy_climbing_deload")`.

#### PASS 2 — Complementary sessions

Fills remaining empty days (up to `target_training_days_per_week`) with non-primary sessions (round-robin through `complementary_pool`, `max_per_week` and slot fit only). Slot preference is reversed: lunch > morning > evening.

#### PASS 2.2 — Extra slot filling (B121 / A283)

When total sessions < `session_target` = `min(target_sessions_per_week or target days, available slots on the kept days)` AND a day that already has a session has an unused slot, places an additional **non-hard** session there (`max_per_week`, finger gap). At most one extra session per day: it covers the lunch + evening split, not three sessions a day.

#### PASS 2.5 — Finger quality floor (A282)

Outside deload, when the phase's `domain_weights.finger_strength` ≥ `QUALITY_FLOOR_WEIGHT` (0.10) and the week carries no `finger` session: places one, trying `finger_maintenance_home`, `finger_maintenance_gym`, then the other non-test finger sessions of the pool. `_place_quality_floor` goes from the least invasive option:
1. an empty day among those kept;
2. in place of a non-primary session that does not carry the tag, on a kept day;
3. a day the target-days pruning dropped (`day_pruned_but_available`), non-hard sessions only — a deliberate day beyond `target_training_days_per_week` (decided 2026-09-05).

The hard cap, the hard gap and the finger gap always hold, and outdoor days are skipped. A hard session the floor places is a hard day for the passes after it (`hard_days`, `hard_day_offsets`), as for every other pass (B415, D287 C3: before, only its finger day was booked, and PASS 2.6 / PASS 3 could open a hard day next to it or past the cap). Nothing placeable → `unmet_stimulus` row `{stimulus: "finger_strength", phase_id, weight, reason}`. (Until A282 this was a `power_endurance`-only guarantee.)

**What the week already carries (B415, D287 C2).** The presence check of both floors (`_week_carries`) reads the week as the B369 merge will save it: this run's placements, the days already lived (B390: `done` sessions up to `today`) and the user's own sessions from `today` on (B414: not skipped) — `_kept_sessions`. Finger: `session_flag(s, "finger")`. Pulling: the catalog `pulling` flag for a catalog id; a session with no meta (custom, generated) counts with a `pulling` tag or a `pulling_max` stimulus (weighted pull-ups among its exercises, `session_stimuli`), else it stays unseen. A declared crag day satisfies neither floor. A floor met that way places nothing and writes no `unmet_stimulus` row. Before B415 the check read this run's placements only: the user's finger custom got a second finger dose, and a week whose finger / pulling work was already done said it "didn't fit" (UnmetStimulusCard; key_sessions_v1 turned the finger key unplaceable). Consequence, in line with A282 (the extra day exists only to keep the finger quality off zero): step 3's extra day is no longer opened when the finger work is already in the week, so a key stimulus PASS 2.7 used to put on that day can now be reported unmet instead; likewise a pulling row can appear when the dose the floor no longer adds was the week's only `pulling` session (`finger_maintenance_home`). Weeks without a plan of the same week being regenerated: the same check as before.

#### PASS 2.6 — Weekly pulling stimulus (B308)

Outside deload, when the week carries no `pulling` session (no weight threshold; read like PASS 2.5's, B415): places one non-test `pulling` session of the pool on a kept day — an empty one, or in place of a non-primary session. It does not use the cascade above (never a pruned day). Hard cap, hard gap and finger gap hold; nothing placeable → `unmet_stimulus` row `{stimulus: "pulling", phase_id, reason}`. The check runs before PASS 2.7, so a pulling session PASS 2.7 places later (`boulder_circuit_gym` as a power-endurance carrier) does not cancel a row already written.

#### PASS 3a — Tests decided by the retest policy (A289)

Active when `retest_decisions` is passed and `inject_tests` is false: places the tests the policy requires on the week as the B369 merge will save it (`_merge_preview`). The policy, the day rules and the reporting are in §8.2. The axes it owns are skipped by PASS 3.

#### PASS 3 — Test session injection (legacy)

Runs when `inject_tests=True`, on the last week of `base` or `strength_power`, or when a `test_queue` entry is due (`recommended_by_date` within the week, B346).

**Test schedule:**
1. `test_max_hang_7s` (or `test_lp_max_5s` if `finger_device == "loading_pin"`) — finger test, required
2. `test_repeater_7_3` (or `test_lp_repeater`) — repeater test, required
3. Pulling test, optional — `test_max_weighted_pullup` or `test_pullup_bw` (B128: routed by `_pick_pulling_test_session()`; A319: when no day takes the 2RM with weights, `test_pullup_bw` on the first day the 2RM passed every pass-1 rule but found no weights — where it went before A319)
4. Queued tests not already listed (`_TEST_QUEUE_SESSION`), required

**Phase gate (D92 / B191):** `_PHASE_TEST_MAP` — `base` and `power_endurance` test the repeater only, `strength_power` all three axes, `performance` and `deload` none. Bypassed by `inject_tests`, by a queued test, and for an axis last tested `MAX_WEEKS_UNTESTED` (12) weeks ago or more; a gated test goes to `skipped_tests`.

**Freshness filter (B128):** Tests completed within `TEST_FRESHNESS_DAYS` = 42 days are skipped (not with `inject_tests`, B210).

Tests bypass the phase intensity cap. Placement is **two-pass** (B297 / D211-F9):
- **Pass 1 — replace:** a test replaces an existing session (prefer complementary targets, fall back to last session on the day). The victim is chosen before the slot (B359); the finger / hard gap is checked unless the victim already carries that flag, then the hard cap.
- **Pass 2 — empty-day fill (`required` only):** a `required` test that Pass 1 could not place may occupy an empty available day (adds a session, +1 weekly volume), still honoring finger/hard spacing, the hard cap, and outdoor/pre-trip exclusions. Optional tests stay replace-only.

Any test that still cannot be placed is recorded in `week_plan.skipped_tests` with `reason="no_placement_slot"` (plus `required`), instead of being silently dropped. The `/week` view surfaces the `required` ones so the user can free up a day.

#### PASS 2.7 — Key stimuli (A305, `planner_v2._key_stimulus_pass`)

Runs after the tests (3a / 3), before the A281 no-hard sweep, the deload transform and the complementary pass.
Requirements come from `key_sessions_v1.phase_requirements` — the rows A294 reads — restricted to those that
declare **`floor_candidates`** (phase-level fields of `key_stimuli.json`, ignored by A294: status and proposals
unchanged). `floor_target` overrides the count (power_endurance: 2 PE sessions), `floor_alternate` rotates the
candidates by the parity of `key_pass_week_index(start)` = `(Monday.toordinal() - 1) // 7` (power_endurance
limit: `limit_boulder_gym` / `power_contact_gym` week by week; the planner places it every week, A294 keeps its
12-day `max_gap_days` for "not due"). Phase-declared candidates bypass the phase intensity cap (the PE limit is
`max` under a `high` cap) like tests do. Rows: base technique; SP limit / technique / try-hard; PE power
endurance (×2) / limit / technique / try-hard; performance project / technique / try-hard; deload none (A328:
the deload form places its finger exposure and technique session itself; PASS 2.7 skips the deload).

Order: requirements by `priority`, candidates in catalog order with phase-pool sessions first, then for each
candidate the least invasive place: an empty day kept by `target_training_days_per_week`, else in place of a
victim — `KEY_PASS_VOLUME_VICTIMS` (`endurance_aerobic_gym`, `route_endurance_gym`, `boulder_circuit_gym`),
the most duplicated first, then `KEY_PASS_SECONDARY_VICTIMS` (conditioning: core, handstand, weights…). Never
prehab / recovery (`guards_v1.REST_DAY_SESSION_IDS`), a test, a complementary lunch (not in the primary view),
a session PASS 2.2 put in an extra slot (`pass2.2:extra_slot`, B121), a victim that carries the same key, or
the last carrier of another key / of the week's pulling or finger stimulus. Third tier (review): a NON-hard
session whose every key is in surplus of its target, and only for a `critical` key (D154: S&P keeps its hard
sessions; a warning key never thins the limit work). A rope candidate (`gym_routes`) is used only when the phase pool climbs routes (never for a
boulder pool). Guards, all on the week as the B369 merge will rebuild it — every view is the real
`replanner_v1._merge_user_content` of the candidate days with `existing_week_plan` (same week), so lived
days, today with something done, user-owned sessions and skipped stubs count, and a placement the merge
would drop is refused; the slots the user emptied (`removal_records`, a slot-less removal resolved to the
slot of the fresh engine session it names, `whole_day_override_dates`) are blocked, because the merge filters
a removal by session id and a NEW id would slip in. Previous week and next week's first days count too:
hard cap, hard gap, finger gap, one climbing / hard session per day (a climbing or hard candidate is never
stacked next to the day's climbing or hard session), a victim is replaced in its own slot only, a max
session never leaves the lunch rotation without a HIIT-safe day (`hiit_near_max`; days next to a
complementary lunch are also the last choice), no hard / finger key session in `KEY_PASS_PRE_TEST_DAYS` (3)
before a test nor on a test day, no hard / max on pre-trip or other-sport days, A294 `_heavy_pull_clash`, and
no new `guards_v1` alert. A requirement still short → `unmet_stimulus` row
`{stimulus, label, phase_id, target, placed, source: "key_stimulus_pass", reason}`; a requirement no candidate
can carry with the equipment (or the pool's discipline) is left to A294's hint. Entries carry
`explain: ["pass2.7:key_stimulus", "key:<key>", "replaced:<victim>"]`.

#### A281 no-hard sweep

After every placement pass above: on each `pretrip_dates` day, any session tagged `hard` or with `intensity == "max"` is dropped, without replacement. PASS 1 already refuses those sessions; the sweep catches what the later passes (floors, tests, key stimuli) put back.

#### Plan build and deload transform

Day entries carry `outdoor_slot` (outdoor availability), `pretrip_deload` (a `pretrip_dates` day), `taper_volume_multiplier` (from `taper_volume`, when < 1.0), `other_activities` and `prev_other_activity_reduce`. The plan carries `profile_snapshot` (phase, weights, pool, intensity cap, locations, `hard_cap_per_week` = the effective cap, `recovery_multiplier`, and `retest_decisions` when passed), `weekly_load_summary`, `weeks[0].targets = {hard_days: effective_hard_cap, finger_days}`, `skipped_tests` and `unmet_stimulus` (the rows of PASS 2.5, 2.6 and 2.7). In the `deload` phase `apply_deload_week()` (§3) then runs on the built plan and the load summary is recomputed.

#### Complementary pass (A300, `complementary_v1.place_complementary`)

Runs **last**, after the deload transform. A slot with `role: "complementary"` is hidden from every pass above
(and from the A294 proposals) by `_primary_view`; this pass fills it with one session of a focus family
(`legs`, `hiit`, `z2`, `upper_push_arms` → C274 catalog sessions; A318 adds the opt-in `arms_shoulders` →
`arms_shoulders_handstand_lunch`, outside `DEFAULT_ROTATION`), own budget outside target days, pruning,
hard cap and deload cap. The family ↔ slot pairing is the minimum-penalty permutation over the week's real
primaries (HIIT not on/before a max day and ≤ 1/week, biceps not ≤ 24 h before a heavy pull, legs not ≤ 48 h
before a limit/outdoor day or a trip departure; HIIT also not before an outdoor day; HIIT/legs not on pre-trip
no-hard days), ties broken by rotation order. The week is read as the B369 merge will return it (the user's
sessions, removals and outdoor days count; a lunch the user filled or emptied is never refilled). Violations →
`secondary_warnings` (recomputed after the merge and on every `persist_week_plan` by
`refresh_secondary_warnings`), unfillable slots / leftover families → `unmet_secondary`. No complementary slot →
no-op, plan byte-identical. See vocabulary §5.7.3.

### Availability normalization

`_normalize_availability()` handles 13 input cases:
- Missing day → rest
- `day: True` → available with home fallback
- `{available: False}` → rest
- Per-slot dicts with `preferred_location`, `gym_id`, `locations`
- `preferred_location: "other_sport"` → slot unavailable
- A300: valid `role` (≠ `any`), `max_minutes`, `focus` copied onto the slot only when present

**Emptied slots and crag days (B382, 2026-10-17).** (a) "I took a session out" means *that slot stays empty*. `apply_events` `remove_session` logs `removed_slot` (the slot the session really sat in — the app sends the id only) and `removed_owned`; `user_owned.slot_emptied(removal_records(plan))` returns the `(date, slot)` pairs with a slot that are not the removal of the user's own session (removals, move sources, overrides, key re-schedules). The planner sets those slots `available: False` in `normalized` (same week, from `today` on) so no pass fills them, and `_merge_user_content` drops any engine session in them whatever its id. The removed session may land on another day (D1) — not a retest-policy test: removing or replacing it declines it for that week (A320, §8.2), and the regeneration does not put it back elsewhere. Legacy removals with no slot keep the by-id reading. D2: a `remove_outdoor` cancels the `removed` records of that day logged before its last `add_outdoor` (or before the event, with no `add_outdoor` on record) — the day returns to the engine. (b) A declared crag day (an engine-free day declared outdoor, done or not past; the previous week's declared days done or not past, as negative offsets) counts in `hard_days` before PASS 1 and joins `hard_day_offsets` / `finger_day_offsets` after PASS 1.5; PASS 1 / 1.5 check it symmetrically (`_near_crag`), PASS 3a counts it in `_hard_ok` / `_test_day_ok`, PASS 2.7 in `_has` and in the guards view (`crag_fields`). `finger_days` in the summary excludes the seeded crag offsets.

**A change of gym survives the regeneration (B414, B369-P6 point 2, Option B).** `change_gym` stamps no user marker (the session stays the engine's), so before B414 the next regeneration of the week put the default gym back. `user_owned.gym_changes(plan)` reads the plan's own `change_gym` adaptations — `{date: {slot | None: {location, gym_id}}}`, log order, the last record of a date wins, a record with a `slot` sets that slot only (`change_gym` honours `slot` since B414; the app sends none = whole day). Right after the B382(a) block, for each date of the same week from `today` on, every available slot of that day (or the named slot) takes `locations: [loc]`, `preferred_location: loc`, `gym_id` (None at home) in `normalized` — and in `normalized_full` when the week has complementary slots (A300 identity kept: the same object when there are none). Every pass then chooses for that place's equipment (`_location_has_equipment` with the slot's `gym_id`; PASS 3a checks the combined test's equipment at the slot). Not applied: a place outside the allowed locations (home with `home_enabled` false) and a gym no longer in the list. Weeks without a record are byte-identical; the merge carries the records forward (`adaptations`).

**The user's sessions are anchors on a regeneration (B414, B369-P6 point 1).** The user's own sessions of the same week from `today` on — `user_owned.is_user_owned` (custom, quick-add forced or not, override, moved, key re-schedule, generated add), not skipped, not done (a done one is B390's lived day), plus (B414 review) any session marked done on a day after `today` (done ahead of its date: no lived day yet, but the merge keeps it) — read with `session_flag` like guards_v1: `_user_finger` / `_user_hard` offsets. PASS 1 / 1.5 check them on both sides, the same day included (`_near_anchor`, generalised from B382(b)'s `_near_crag`): no engine finger session within `finger_gap_days`, no hard one within `hard_gap_days`, none stacked on the user's finger / hard day. A user hard day not already counted (crag, lived) counts in `hard_days` before PASS 1 (`_user_hard_new`, also in PASS 3a's recount); after PASS 1.5 the offsets join `finger_day_offsets` / `hard_day_offsets` (any-distance checks of the later passes) and stay out of `targets.finger_days`. Decided 2026-11-07: those three rules only — no slot is blocked, the target days do not change. The merge no longer probes the result (`regeneration_guard_warnings` removed; an old record is dropped on the next merge). Weeks without such sessions are byte-identical.

**Days the user owns wholesale (B379).** When `generate_phase_week` receives `existing_week_plan` for the same week, every day from `today` on that is in `user_owned.engine_free_dates(existing_week_plan)` — a whole-day / outdoor override, or an outdoor day the user declared on the plan (spot, `outdoor_plan`, outdoor block planned/done; `user_owned.is_declared_outdoor_day`, which `stimulus` delegates to) — is treated like an outdoor-only availability day: no session from any pass (primary, complementary, PASS 2.7 key pass via its `blocked` slots, tests), and the spacing/caps of the other days are computed without it. The day does **not** get `outdoor_slot` (that marker means availability). The complementary pass (`place_complementary`) and the retest policy (`_locked_by_merge` → `locked_dates`) read the same predicate. B379 also closed a B297 gap: PASS 3 pass 2 never places a required test on a day before `today` (the merge would have dropped it silently) — it is reported as `no_placement_slot` instead.

### Day scoring for cap

When available days exceed `target_training_days_per_week`, days are scored (summed over the day's available slots) and the top N kept, ties to the earlier weekday:
- Gym preferred: +100
- Gym available: +50
- Evening slot: +10
- Home-only: +1

A day dropped here is remembered as `day_pruned_but_available` — the day the last step of the PASS 2.5 cascade may use.

### Youth cap (D81)

Users under 18: `target_days = min(target_days, 4)`.

### Recovery multiplier (D83)

`recovery_multiplier` from `planning_prefs` extends the minimum gaps between hard and finger sessions: `hard_gap_days = finger_gap_days = ceil(1 * recovery_multiplier)`, in calendar days (see *Limits shared by the passes*).

### Homewall expansion (B137/B159)

`_expand_session_locations()` adds `"home"` to a session's locations if the user's home equipment satisfies all required equipment (e.g., homewall with `gym_boulder`). B208: only for sessions that require a wall surface (`BOULDER_SURFACES` or `gym_routes`) — a gym session that needs only a hangboard, a bar or weights stays at the gym.

---

## 5. Session Resolver (`resolve_session.py`)

**Entry point:**
```python
resolve_session(
    repo_root, session_path, templates_dir, exercises_path, out_path,
    *, user_state_override, write_output, user_id, phase
) → Dict[str, Any]
```

### Resolution flow (step by step)

1. **Load inputs:** session JSON, user_state, exercises catalog.
2. **Determine context:** `get_location_equipment()` resolves location (gym/home) and available equipment from user_state + session context. Equipment is expanded via `expand_equipment()`.
3. **Load recency:** `load_recent_exercise_ids()` extracts exercise IDs from the last `RECENCY_LOOKBACK_WEEKS` = 3 weeks of completed sessions in `user_state.week_plans`.
4. **Build recency groups:** Maps recent exercise IDs to their `recency_group` values for family-level dedup.
5. **Iterate modules:** For each module in session JSON:
   - **Inline block** (has `block_id` + `selection`, no `template_id`): → `_resolve_inline_block()` → `pick_best_exercise_p0()`.
   - **Template reference** (has `template_id`): Load template JSON → iterate its `blocks[]`.
6. **Per block resolution:**
   - **Explicit exercise** (`exercise_id` in block): Direct lookup, bypass P0 filters. B414: the pin is a chain — `_resolve_pin_chain` (both branches) takes the first of `exercise_id` + `fallback_exercise_ids` whose equipment is available (equipment only); when none passes, `pin_exhausted` decides: `p0` (default: P0 with the block's filters, B261), `skip` or `fail` (`pin_strict` = `fail`); a test pin that cannot run is always skipped. Without the new keys the output is the pre-B414 one.
   - **Instruction-only** (`mode: "instruction_only"`): No exercise selection, pass through.
   - **P0 selection** (has `role`): → `pick_best_exercise_p0()` with block's `role`, `domain`, `pattern`.
7. **Cooldown fallback:** For main/primary blocks, if the selected exercise is in cooldown (via `_cooldown_until_date()`), swap to a cluster fallback or apply 0.9 multiplier downshift.
8. **Prescription merging:** `exercise.prescription_defaults` ← overridden by `block.prescription` ← overridden by `_apply_load_override()` (user per-exercise overrides).
9. **Prehab injection (B38):** `_inject_prehab_for_limitations()` auto-adds one prehab exercise per limitation zone if not already present.
10. **Progression injection:** `inject_targets()` enriches instances with suggested loads, target grades.
    **Bodyweight ladders (A298, B413):** for a tested athlete `_bw_ladder_stage` replaces a P0 pick on a ladder family with the athlete's level and dose (`prescription.source: "bw_ladder"`), and a pinned inline block that declares `ladder_pin` (B413 D4: the floor-core blocks of the four catalog lunches) takes the athlete's level of its listed families — `level_offset` −1 on the Tuesday HIIT lateral row (A2), never a hanging or heavy-pull level, one family per session, a seeded level never below the catalog dose (pin floor). Untested athletes, or no entry: the catalog pin, bit for bit. The ladders read the archived weeks through `archived_weeks` (§8.5).
11. **Phase-aware ordering (A121):** `sort_exercises_by_phase()` + `enforce_ordering_constraints()`.
12. **Load score:** Sum of `fatigue_cost` × 1.5, capped at 85 — formula in `engine/load_score.py` (B312: single source of truth, shared with the add/remove-exercise router).
13. **Force deload:** If 2+ zones are `severe`, flag the session.

### Prescribed vs actual load (B312)

Two numbers, never conflated:

| Field | Where | Written by | Meaning |
|-------|-------|-----------|---------|
| `session_load_score` | `slot["resolved"]` | `resolve_session`, add/remove-exercise | **Prescribed.** Frozen once the session starts — the denominator of `load_ratio`. |
| `session_load_actual` | `slot` (next to `actual_exercises`) | `POST /api/feedback` | **Actual.** Same formula over the exercises whose feedback item says `completed: true`. |

`effective_session_load()` is the only reader any consumer should use (weekly
report, monthly heatmap, coach prompt): it cascades actual → prescribed →
`estimated_load_score` and looks each key up on the slot *and* on the resolved
payload. Absent a `completed` flag nothing is subtracted (the `/today` and
`/week` dialogs carry no skip signal); an explicit `completed: false` is the only
thing that lowers the load. A `session_load_actual` of 0 is honoured; a
*prescribed* 0 means the resolver produced no instances and still falls through.

**Which prescription the actual load is scored against (B414, B312-LOAD-ACTUAL-VS-FROZEN).**
An engine session that `/feedback` itself marks done (the guided player) is
scored on the prescription GET showed — the B413 D2 freeze computed at step 1
(key `(date, slot, session_id)`), the same `resolved` step 7b writes. A pending
engine session is stored without `resolved`, so before B414 the guided player's
sessions never got a `session_load_actual`. A session already done (the
`/today` flow: `/events` writes the freeze, then the dialog posts), a custom or
a body-part session falls back to the stored `resolved` as before. Full
completion = the frozen `session_load_score`; nothing is recomputed for
sessions already played.

### Output structure

```python
{
    "session_instance_version": "1.1",
    "context": {"location", "gym_id", "available_equipment"},
    "session": {"session_id", "session_name", "session_version", "source_path"},
    "resolved_session": {
        "resolver_version": "0.2",
        "modules": [...],
        "blocks": [...],         # P0 trace for each block
        "exercise_instances": [...]  # The exercises to perform
    },
    "resolution_status": "success" | "failed",
    "session_load_score": int
}
```

---

## 6. Exercise Selection — P0 Filter Chain

**Entry point:** `pick_best_exercise_p0(*, exercises, location, available_equipment, role_req, domain_req, pattern_req, ...) → Tuple[Optional[Dict], Dict]`

The P0 filter chain is a staged pipeline. Each stage narrows the candidate pool. Stages are either **hard** (zero candidates → None) or **soft** (zero candidates → skip filter, keep previous pool).

### Filter stages in order

| Stage | Name | Type | Logic |
|-------|------|------|-------|
| 0 | Start | — | Full exercise catalog |
| 1 | **Location** | Hard | `location_allowed` must include the session location |
| 2 | **Equipment required** | Hard | `equipment_required` ⊆ `available_equipment` |
| 2 | **Equipment required_any** | Hard | `equipment_required_any` ∩ `available_equipment` ≠ ∅ |
| 2b | Block equipment pref | Soft | If block specifies `equipment`, prefer exercises that require it |
| 2c | **Finger device pref** | Soft | Splits pool into finger-device and non-finger exercises. Among finger-device exercises only, prefers user's chosen device (`hangboard` or `loading_pin`). **Non-finger exercises are untouched** (B126 fix). |
| 2d | Age gate (D80) | Hard | `age_minimum` ≤ `user_age` |
| 2e | Hangboard experience (D35) | Hard | Blocks 6 advanced hangboard exercises for users with < 2 years experience. Test exercises (`role: ["test"]`) are never blocked. |
| 2f | Experience minimum (B159a) | Hard | `experience_minimum_years` ≤ user's experience |
| 3 | **Role** | Hard | `exercise.role` ∩ `role_req` ≠ ∅ (ANY match) |
| 3b | Dedup | Soft | Exclude already-used `exercise_id`s (only if alternatives exist) |
| 4 | **Domain** | Soft | `exercise.domain` ∩ `domain_req` ≠ ∅ (doesn't zero candidates) |
| 5 | **Pattern** | Soft | `exercise.pattern` ∩ `pattern_req` ≠ ∅ (doesn't zero candidates) |
| 6a | **Limitation (severe)** | Hard | Exclude exercises with contraindications matching severe limitations |
| 6b | **Limitation (active)** | Soft | Prefer exercises without active-zone contraindications |

### Tie-breaking

After all filters, candidates are sorted by:
1. `score_exercise()` descending — recency-aware scoring
2. `_variety_key(exercise_id, variety_seed)` ascending — deterministic final tie-break (B274)

The variety seed is the ISO Monday of the week of `context.target_date`
(`_variety_seed_from_date()`): same week → same rotation (stable re-resolution),
new week → the tied pool rotates via `md5(exercise_id | seed)`, removing the
alphabetical bias that starved late-sorting ids (all `tech_*` drills). Callers
with no date in context get `seed=None` → legacy alphabetical `exercise_id`
tie-break, unchanged.

### Recency scoring (`score_exercise()`)

```python
# Exercise-level recency penalty
if ex_id in recent[-5:]  → -30
if ex_id in recent[-15:] → -15
if ex_id in recent        → -5

# Recency group penalty (B159b)
if recency_group in recent_groups → -15

# Preference bonus
if edge_mm matches → +10
if grip matches    → +5
```

### Trace output

Every selection produces a `trace` dict with counts at each stage, enabling production debugging when `TRACE_RESOLVE=true` is set.

### 6.1 Phase-anchor rotation (`phase_anchor.py`, A290)

**Scope:** only athletes with a TESTED baseline on the finger or the pulling
axis (`retest_policy.is_tested`: a `tests.*` entry, source test/test_session,
at any age since B414 — model A, the 90-day expiry switches nothing off).
Otherwise `build_rotation_context()` returns `None` and every new
P0 kwarg keeps its default: the resolver is bit-for-bit the pre-A290 one
(golden `backend/tests/fixtures/a290_untested_golden.json`).

The catalog declares a **rotation class** per block, as top-level keys of a
template block or of an inline session module (never inside `selection`):

| Class | Pick | History |
|---|---|---|
| `phase_anchor` | first candidate in the priority list (`anchor_priority`, overridden by `anchor_priority_by_phase[phase]`; `tested` / `untested` list by `anchor_axis`); ids outside the list follow by md5(id \| phase \| effective phase start) | none — fixed for the phase |
| `ab` | pool ordered by md5(id \| phase \| phase start \| session \| block); A = pool[0], B = pool[1]; choice = `(week_idx + occurrence_idx) % 2` | none — `occurrence_idx` counts the same session earlier in the ISO week, **status agnostic** (marking Monday done never changes Thursday) |
| *(none)* | free: the chain above + recency score + weekly md5 tie-break | yes |

- **Phase window** from `macro_position` (pause-aware): `phase_id` = the
  resolver's `phase` kwarg (else the phase on `target_date`), start =
  `start_date + pause.offset_days + 7 × earlier phases`. `phases[].start_date`
  is never read. `week_idx = (target_date − phase_start) // 7`.
- **Tested list** per axis: fingers total/BW ≥ 1.35 (20 mm, 7 s; a 5 s test is
  converted), pulling 2RM total/BW ≥ 1.45 — from `official_max` (tests.*, the
  test's own bodyweight), never from the estimated baselines. ENGINEERING
  CONSTANTS.
- **Heavy slot** (`heavy_slot: true` on `strength_long.pulling_compound`,
  `finger_strength_home.pulling_maintenance`,
  `pulling_strength_compound.weighted_pullup_main`): heavy (phase_anchor on
  the weighted list) only for the first 2 heavy-slot sessions of the ISO week
  in strength_power, 1 elsewhere — counting only the earlier occurrences that
  were really heavy (one a spacing guard turned light does not use a slot;
  each is re-judged on the pull days strictly before its own day and on its
  own tomorrow). A heavy occurrence is downgraded to `ab`
  without external load (`load_model` not total/external) when: a weighted
  pull was done < 48 h before (`heavy_pull_48h`), 2 heavy-pull days in the
  last 7 (`heavy_pull_7d_cap`), or a limit_boulder / power_contact /
  strength_long is planned tomorrow (`pre_limit_24h`; the core also drops
  front levers that day). When no plan covers tomorrow (Sunday, next week not
  generated — and once it is, the Sunday session is past and immutable) the
  same weekday of the target's own ISO week stands in (`pre_limit_source:
  weekday_proxy` in the trace).
- **Max-hang spacing:** a finger_max exposure (tests included) < 72 h before
  switches a block that declares `spacing_step_down` (the finger_max_strength
  main) to a real step-down (`anchor_list: spacing`, `max_hang_72h`): its own
  domain/pattern (sub-maximal hangs: lopez_subhangs, long_duration_hang,
  sub_max_capacity_hang), a HARD exclusion of every max-load finger exercise
  (`phase_anchor.FINGER_MAX_LOAD_IDS` = the finger_max family + the
  finger-fatigue hangs, plus `intensity_level: max` / fingers stress `high`;
  nothing left → block skipped, never a max hang) and the block's
  max-intensity prescription dropped.
- **Finger level on finger-loaded anchors:** the limit and campus blocks
  declare `anchor_axis: finger` with a tested/untested split (untested: wall
  limit first, gentlest campus drills, campus_max_ladders excluded). Campus is
  anchored in strength_power only: a block with only
  `anchor_priority_by_phase` is free in the phases it does not list.
- **Core floor** (`rotation_exclude`): only for an athlete above a tested
  threshold on either axis (`RotationContext.advanced`).
  Fatigue = done sessions only (F0 `stimulus.exposure_dates`, custom sessions
  with logged sets included); a skipped session never counts.
- **P0 fixes for tested athletes:** Stage 0 drops `active: false`; Stage 2e
  exempts a test exercise only in a block that asks for role `test` (D35:
  max_hang_7s is role main+test); Stage 3b (history dedup) runs after Stage 6
  for free blocks, so a saturated history cannot push a pick out of the
  target domain/pattern. The variety recency excludes the main instances of
  test sessions, includes done custom sessions and has no 100-id cap.
- **Dose by phase:** `anchor_priority_by_phase.power_endurance.tested_prescription_overrides`
  — PE finger session = max_hang_7s maintenance at 3 sets (B364's
  `anchored_load` gives the 85-90 % load).
- Trace: `blocks[].p0_trace.rotation` `{rotation, anchor_list, anchor_axis,
  anchor_rank, phase_seed, week_idx, ab_slot, occurrence_idx, ab_pair,
  heavy_slot, heavy_rank, spacing_downgrade, pre_limit_source,
  hard_excluded_max_finger, selected}` (additive).
- `resolve_session(..., week_plan=...)`: the plan being resolved (week and
  replanner `_auto_resolve` pass it) is the structural truth for occurrences;
  without it the state's hot week plans are read.

---

## 7. Progression Engine (`progression_v1.py`)

### `inject_targets(resolved_day, user_state) → Dict`

Called after resolution to enrich exercise instances with working loads. Handles multiple `load_model` types:

| load_model | Source | Logic |
|------------|--------|-------|
| `total_load` | `user_state.baselines.hangboard[]` | `target = intensity_pct × max_total_load_kg`; computes `added_weight_kg` or `assistance_kg` |
| `external_load` | `user_state.baselines.working_loads{}` | Phase/intensity → %1RM from `PULLING_1RM_PCT` table; scaled by `PULLING_EXTERNAL_SCALING` per exercise |
| `loading_pin` | `LOADING_PIN_DEFAULT_INTENSITY_PCT` | 6 LP exercises with specific intensity %BW |
| `grade_based` | `user_state.assessment.grades` | Grade offset via `step_grade()` based on phase |
| `bodyweight_only` | — | No load injection needed |

### `apply_feedback(log_entry, user_state) → Dict`

Processes post-session exercise feedback:
1. Updates `user_state.baselines.working_loads` with actual loads used.
2. Updates test results (max hang, pullup, repeater) if test exercises are in the log.
3. Calls `_enqueue_test()` to auto-schedule retests when feedback is extreme.

### Key constants

- `PULLING_1RM_PCT` (`progression_v1.py`): Phase × intensity → %1RM (range 0.525-0.845).
- `HANGBOARD_DEFAULT_INTENSITY_PCT`: 11 hangboard exercises → default intensity %.
- `GRADE_TO_HANG_OFFSET`: Grade → kg offset for max hang load estimation (-10 to +45).
- `_SIMILARITY_GROUPS` (B90): 2 groups (push, pull — the squat group was removed by B363) for cross-exercise load transfer when baseline is missing. Since B380 the coefficients compare **whole loads** (see *Load units* below).
- `DEFAULT_ADJUSTMENT_POLICY`: Maps feedback labels to % adjustment ranges.

### Load units (B380)

Every external-load exercise declares in the catalog what its kg counts — `load_unit` (`backend/engine/load_units.py`): `per_dumbbell` (a pair of dumbbells, the number is ONE dumbbell: dumbbell bench press, dumbbell row, overhead press, curls, lateral raises…), `implement` (one dumbbell / kettlebell / plate: goblet squat, overhead triceps extension, wrist work…) or `total` (barbell, cable, machine; also the meaning of a missing field). Progression never reads it — feedback steps are percentages of the number the athlete logged, in whatever unit. It matters in two places: the display (`suggested.load_unit`, written by `inject_targets` when it is not `total`, and `load_unit` on custom / ad-hoc / body-part / user-added rows → "34 kg per dumbbell"), and the transfer between a barbell lift and its dumbbell twin (`bench_press` ↔ `dumbbell_bench_press`, `barbell_row` ↔ `dumbbell_row`): `_transfer_load` and `check_load_coherence` convert both sides to the whole load (`to_total`: per dumbbell × 2) and back (`from_total`: ÷ 2), rounded to 0.5 kg — bench 70 → dumbbell bench 35 per dumbbell, dumbbell bench 34 → bench 68. The transfer still applies only when the target has no fresh load of its own. Cold-start fallbacks of per-dumbbell exercises are per dumbbell (dumbbell bench 0.17 × BW, dumbbell row 0.15 × BW / 0.30 × pulling max, overhead press 0.125 × BW; curls 0.23 × BW per dumbbell — 18 kg at 78 kg).

### Load coherence check

`check_load_coherence(user_state, date_value, freshness_days)` returns warnings when baselines are stale or missing.

---

## 8. Closed-Loop Adaptation

The **only** closed-loop adaptation in the engine is per-exercise load
progression: `progression_v1.apply_feedback` reads each exercise's difficulty +
actual load and adjusts `user_state.working_loads` (see §7). There is no
separate adaptation module.

> **REMOVED (B299, 2026-07-22):** a dormant per-cluster cooldown system
> (`adaptation/closed_loop.py` → `record_cluster_cooldown`, plus the resolver's
> `cluster_cooldown_fallback` / `cluster_cooldown_downshift` branches and
> `user_state.cooldowns.per_cluster`) was deleted. It never had a production
> caller — the writer was never invoked, so the reader never found an entry and
> the two branches never fired for any user. Rather than wire it (which would
> have double-penalised after a `fail`: the load cut from `apply_feedback` **and**
> a cluster substitution/×0.9 downshift), the mechanism was removed to simplify
> the P0 resolver. The reactive-recovery need it targeted is already covered by
> the proactive schedule (finger gap in calendar days, DUP spacing, hard caps) and the
> live load progression; injury spacing for fingers lives in
> `replanner_v1._enforce_finger_gap` and is untouched.
>
> A245 E-4 had earlier removed a separate multiplier system
> (`adjustments.per_exercise`, `compute_next_multiplier`, `apply_multiplier`)
> from the same module for the same reason (zero production readers).

> **Stimulus balance in the weekly report (B377, 2026-10-17):** «days since
> last» per stimulus category is **derived at read time** by
> `report_engine._derived_last_done` from `session_completion_log` (status
> `done`, dated before the report week) and the catalog categories
> (`closed_loop_v1._session_categories`, A291). **Since B383** custom /
> generated sessions count, categorised from their exercises
> (`report_engine.exercise_stimulus_categories`: A288 family first, then the
> catalog domains through the A291 goal table; warm-ups add nothing,
> conditioning is complementaries), and a crag day the athlete climbed counts
> (lead → endurance, boulder → boulder_power, never finger_strength). The
> closed-loop writers still ignore custom sessions (A240). The stored `user_state.stimulus_recency` / `fatigue_proxy`
> counters (written by `closed_loop_v1.apply_day_result_to_user_state` on the
> `/events` mark_done/mark_skipped path only, non-idempotent) are **legacy**:
> no reader is left. The writers were left untouched on purpose.

### 8.1 Official max vs working load — `anchored_load.py` (B364)

Two numbers, never mixed:

- **Official max** — `tests.*` / `baselines`, written ONLY by
  `_update_test_from_log`, read ONLY through `retest_policy.official_max` (the
  freshest test, hang durations converted at 0.015/s). Feedback never moves it.
  B156 fix: a `test_*` item added to a training session makes only the `test_*`
  items measurements.
- **Working load** — `working_loads.entries[]`, the load the athlete trains
  with: `next = used + step` in kg (labels; measured `last_set_reps` /
  `hang_held_s` / `hang_margin` first), with the phase and intensity of the log.

`anchored_load(state, exercise_id, date=…)` is the ONE prescription of the four
anchored exercises (weighted_pullup, weighted_chinup, max_hang_5s/7s) for a
**tested** athlete (persisted state, a real test at any age — B414 model A); `None` otherwise and the
pre-B364 branches run unchanged (golden-tested, B363 `e2rm_total_kg` re-base
included; "tested" = a `tests.*` entry or a `test_session` baseline — an
onboarding self-report persisted as `source: test` does not count). Consumers: `inject_targets`,
`body_part_picker.apply_resolver_light`, `adhoc_prescription` (builder proposal
and A253 anchor), `session_composer._decorate_engine_fields`,
`adhoc_builder`, custom sessions resolved at read (`resolve_custom_exercises`:
`GET /api/custom-session/{id}?date=`, `GET /api/week` on a response copy), the
coach prompt.

Clamp order: start (working load converted by NON-rounded rep factor, seconds,
phase/intensity; else phase target) → structural cap (pull: min(Prilepin band,
(r+2)RM); hang: 3 s of reserve, phase cap) — B413 (A4): no re-entry factor any
more, after a gap the cap is the full phase cap; B414 (2026-11-07): no re-entry
at all — the 5-set max-hang cap after a ≥ 14-day gap is gone with
`retest_policy.reentry_step`, `anchored_load.ramp_for` and the `ramp` key (the
sets are the prescribed ones; legacy `anchored.ramp` / `reentry_sets` in stored
prescriptions are read as stored) → pain
(`pain_blocks`, R4; the phase floor is cut by the same 0.90) → guards (2 heavy pulls / 7 days, same-session finger,
finger-hard day in the 2 days before) → `floor_eff = min(floor, cap_eff)` →
fatigue (3 hard / 14 days → floor). All engineering constants are labelled in
the module.

A328 (D288 R3, 2026-11-13 — supersedes the deload row of the D282 §6 cap table
for hangs): a max hang in the **deload** is `_deload_hang` — the previous
phase's prescription (`deload_source_phase`: the last non-deload phase of the
macrocycle, `performance` in a full cycle) at intensity `hard` on the same date
(its working load or cold target, pain / guards / fatigue applied) ×
`macrocycle_v1.DELOAD_LOAD_FACTOR` (0.90), never above that prescription's
structural cap (3 s of reserve); output `phase_id: "deload"` plus
`deload: {factor, from_phase, from_total, from_clamped}` (also in
`anchor_summary`). Daniele 02/12: performance 110 kg (the 0.95 cap of 116) →
**99 kg (+21)**, 85.3 % of the max — the old deload cap (0.70 → 81 kg) no
longer applies to hangs. `hang_write_cap` (the non-anchored hangs) reads the
same source phase in a deload. **Closed loop:** in a deload a hang's feedback
never rewrites the working load (frozen like the bodyweight ladders; a
`hard` / `very_hard` label still lands in `hard_labels`), otherwise an entry
logged with phase `deload` (pct 0.65) would come back × 1.23 in the next base.
Pulls are unchanged (no pull in the deload form). The deload rows of
`HANG_PHASE_*` stay only to convert a legacy entry logged in a deload.

B413 (D3): a DONE exercise with no rating and no measure is an `ok`, and it
never rewrites the memory lower than what `anchored_load(...,
temporary_cuts=False)` proposed for that session (no heavy-pull / same-session
/ finger-hard guard, no fatigue floor): the entry stays, only its date moves
(`progression_v1._keep_unrated_memory`). The same rule holds for the other
loads and the grades (endurance, limit — whose B365 re-entry −½ grade is gone,
A4: after a gap the limit target is the memory).

`apply_feedback` also writes the ONE exposure registry
(`progression_counters.stimulus_exposures`, read by `stimulus.exposures`), the
measured early-retest evidence (`retest_signals`, never an enqueue — labels no
longer touch `test_queue`) and the fatigue days (`hard_labels`).

### 8.2 Retest policy — who schedules a test (A289)

Only `retest_policy.retest_decisions(state, week_start, ...)` schedules tests of
a **covered** axis (finger with a hangboard, pulling; covered = a real test, at
any age since B414). `GET /api/week` computes it when it GENERATES a week (archived weeks and
outdoor rows read fail-soft) and passes it to `generate_phase_week(retest_decisions=...)`:

```
retest_decisions  → week-level: trigger (end_of_phase | cycle_start |
                    maintenance | early_retest), gap 42 d after any test
                    (A319; 28 d only for early_retest), phase / trip /
                    very_hard day blockers, external finger-hard + heavy-pull
                    days, already-scheduled; the athlete's declines (A320:
                    skipped declined | postponed, the axis stays covered)
planner PASS 3a   → day-level against the week AS THE B369 MERGE WILL SAVE IT
                    (B400): < 72 h finger-hard (hang; 3 calendar days, inclusive),
                    never a slot the regen merge refills (locked_slots /
                    locked_dates), < 48 h heavy pull (pull-up), 48 h finger gap,
                    hard cap + hard spacing, never an other-sport day;
                    paired day, hang slot before pull-up slot — else ONE slot
                    with the combined test_max_hang_pullup (A319), else the
                    hang alone + pull-up blocked:no_paired_slot
planner PASS 3    → historical, only for the axes the policy does not cover
retest_status     → live on every GET: official max, confidence, trend (±5 %),
                    valid_until / expired / expiring (B414; tested_until = the
                    same day), next test (planned with reason | projected),
                    live blockers
```

`None` (untested athlete) leaves the planner byte-identical and `GET /api/week`
without `retest_status`. A cached week is never regenerated for the policy; the
live status flags a planned test that became too close to a hard session
instead of moving it.

**The expiry switches nothing off (B414, model A — decision of 2026-11-07).**
`official_max(...).tested` is "a real test" (a `tests.*` entry, or a baseline a
test log wrote) at ANY age. Before B414 it also required an age < 90 days, and
that one gate turned off, on day 90, the ladders (`bw_ladders.tested_gate`), the
anchored loads and their closed loop (`anchored_load` → the legacy branch),
the A290 rotation, the A292 PE anchor, the tested coach and the policy's
coverage. Now the 90 days are the max's **validity**, informational only:
`official_max` returns `valid_until` (test day + `TEST_FRESH_DAYS` − 1),
`expired` and `expiring` (from `EXPIRY_WARNING_D` = 14 days before; never in the
`POSTPONE_QUIET_D` = 14 days after the latest postpone's `declined_at`), and so does
`retest_status` per axis. The axis stays covered: from `MAINTENANCE_RETEST_D`
the maintenance trigger proposes the test in every week the phase allows (never
in performance / deload, never after the end of the macrocycle — the projection
stops there with `next_test_reason: after_cycle_end`). An onboarding
self-report is still never a test. Nothing is written: the readings change, no
stored field does.

**"Postpone the expiry" and "Do the test" (B414-2, B414-3).** Both are records
of `retest_declines`. A postpone's `until` also extends `valid_until` (trigger
`expiry` when nothing was pending; at most 42 days past the validity per
postpone; a new one replaces the axis' active ones). A `kind: request` record
(the athlete's "Do the test") gives the trigger `requested` from its day, ahead
of every natural trigger and in every phase but the deload (hard cap 0); the
gap and the day guards still apply, and PASS 3a places it like any policy
test (stamp `retest:requested`, so A294/A315 never replace it). Every reader
of the list filters by kind. A246: the reminder's confirm names next week
(`initial_tests_requested` = its Monday), so `week.py` injects the tests there
also mid-cycle.

**A test done in its week closes it (B414, A289-TEST-DONE-IN-WEEK).** The
decision reads the official max on the Monday of the week, so a test logged
from Tuesday on did not move `last`: the week stayed `due`, a mid-week
regeneration put the test back in the days left (or wrote `no_placement_slot`)
and `retest_status` said `missed` / `not_in_plan` until Sunday.
`_test_done_in_week` now runs before the declines, the triggers and the gap: a
real test dated in the week (max read at the end of the week for this check
only), or a test session of the axis marked `done` with no values
(`result_missing: true`, the max stays the old one), makes the week `not_due` +
`done_in_week`. A skipped test session does not count; the coverage is still
read on Monday. planner_v2 is unchanged (it receives no required test).

**One gap, no slip, one test day (A319, 2026-10-20).** From climb-coach's
bug-inbox of 2026-10-18 ("tests too close together"): Daniele's low-confidence
tests of 24/09 were due again 28 days later, the end-of-SP test slipped one week
and the pair was split over two hard evenings (22/10 + 24/10). Now:
- `retest_gap_days` is `HIGH_CONF_RETEST_D` (42) after any test — the
  confidence is computed and shown, it moves no date. `LOW_CONF_RETEST_D` (28)
  is only the floor of `early_retest` (two measured signals), whose row says
  `gap_days: 28`. `retest_status.earliest_retest` = test + 42, or, with the
  early-retest evidence, the early retest's first day (test + 28, the day after
  the last signal) when that comes sooner — the "not before" never contradicts
  a projected test.
- No slip: an end-of-phase week the gap keeps out of reach is `blocked:gap`;
  the next test comes with the next trigger. `end_of_phase_slipped`,
  `slipped:gap` and `slipped_to_week` are never produced; the snapshots written
  before A319 still carry them and are read as stored (`_planned_reason`,
  `_generated_week_skip`: pure passthrough, no closed-set check).
- The pair is never split over two days. No day with two ordered slots →
  PASS 3a tries ONE slot of one of the shared allowed days with
  `test_max_hang_pullup` (max hang 7 s, then the 2RM after a full rest, then
  the secondary measurements; its two max blocks pinned `order: after_warmup`
  so the instance sort keeps them first), through the same `_place` /
  `_test_day_ok` / `_hard_ok` machinery: it is a finger test AND a pull-up
  test (72 h finger-hard, 48 h finger gap, same-day finger-hard and
  pulling-hard, 48 h heavy pull) and its slot needs hangboard + pull-up bar +
  weights. Two snapshot rows, one per axis, `session_id: test_max_hang_pullup`,
  same `placed_date` / `placed_slot`, `combined: true`, `paired_with: null`;
  the entry's explain carries `retest:finger:<trigger>` and
  `retest:pulling:<trigger>`. Still nothing → the hang alone and the pull-up
  `blocked:no_paired_slot` (no new reason codes). The combined id is in
  `AXIS_TEST_SESSIONS_ALL` under both axes (already-scheduled, planned
  next_test, removed-ref locks), in `SESSION_FALLBACK_STIMULI` (finger_max +
  pulling_max for the unresolved slot), `_RD_PULL_TEST_SIDS`, the phase-anchor
  pull-test prefixes and athlete_context's `pull_test_soon`; PASS 3a's
  `_test_sid_axes` reads it as both axes (`_kept_test_date`, `_pair_order_ok`).
  One test log writes both official maxes (progression_v1 unchanged: the
  `test_` prefix / `tags.test` gate, then per exercise id). Out of scope: the
  historical PASS 3 and `inject_tests` never use it.
- A319 review — the partner of a kept test: a test of one axis the week keeps
  (the user's, or on a day the merge copies back — the policy's
  `already_scheduled` row or PASS 3a's own B400 one) takes its partner on its
  day only, in the pair's slot order; else the pull-up `blocked:no_paired_slot`,
  the hang `no_placement_slot`. Before, the partner went alone on any allowed
  day: "regenerate from tomorrow" on the lone hang's day put the 2RM two
  evenings later.
- A319 review — a trigger the gap keeps out of the week (`end_of_phase`,
  `cycle_start`) yields to `early_retest` when the early retest's own first
  day (last test + 28, the day after the last signal) falls in the week;
  before, the measured evidence waited one more week.
- `test_max_weighted_pullup` requires `pullup_bar` + `weight` (dumbbell /
  kettlebell / barbell imply it): without weights its 2RM block resolved to a
  non-test pull (B261 non-test fallback) and wrote no max. The historical
  PASS 3 (pass 1) gives the 2RM a day with weights when one passes its rules;
  else `test_pullup_bw` on the first day the 2RM passed every rule but found
  no weights (review: decided on the outcome — weights only on the day the
  finger test took used to lose the pull test silently). `change_gym` reads
  the same catalog requirement: a 2RM moved to a gym without weights becomes
  `complementary_conditioning`. B414 (A319-CHANGE-GYM): the combined moved
  where the hangboard is but not the weights becomes `test_max_hang_7s`
  (equipment only, never the catalog location; the finger stamp
  `retest:finger:<t>` becomes `retest:<t>`, the `retest:pulling:*` one goes, no
  `lost_finger`, warning "the pull-up test waits for its next turn"); without
  a hangboard it still becomes `complementary_conditioning` + `lost_finger` —
  never the 2RM alone (A326 leaves tests out of its stimulus-aware
  replacement, so a test never becomes a training session of its key).
  `retest_status` then reads the pull-up's week as
  `blocked:no_paired_slot` (`_generated_week_skip`, snapshot row `combined` +
  a finger test alone at its `placed_date`/`placed_slot`), never "planned".

**PASS 3a on the merged week (B400, 2026-10-18).** The rules above used to read
only the sessions the planner had just generated; the merge then put the user's
own sessions back byte-identical (prod: a hang test the morning after the
user's key re-scheduled `route_projecting_gym`). Now every rule reads
`planner_v2._merge_preview(existing_week_plan, …)` — the real
`replanner_v1._merge_user_content`, exactly as A305's `_week_view` (PASS 2.7):
the user's sessions in their slot, lived days and today with a done session
copied wholesale, the engine sessions the merge drops gone. A candidate day is
previewed with its victims removed (the merge works day by day); the view is
cached until `_commit` changes the week. Before today only done sessions count
(B390, so the hard cap and spacing finally include the days already lived — a
cap of 2 with Monday + Tuesday done hard no longer gets a third hard day from
the tests); from today on everything but a skipped stub (malformed entries are
ignored). "Today" is the policy's `as_of` (the server's day the decisions were
taken on) when it comes before the planner's `today`: with "regenerate from
tomorrow / next Monday" the planner's `today` is the merge floor, and the days
before it are copied wholesale but still ahead. A failed preview logs and falls
back to the generated week. On the policy side `_planned_axis_tests(exclude_week)`
keeps the tests the merge puts back (the user's, or on a day copied wholesale)
as `already_scheduled`, so no second test is placed next to them; PASS 3a does
the same on its merged view for the tests the policy cannot see (a day between
`as_of` and the floor), with a snapshot `already_scheduled` row instead of a
`no_placement_slot`. The partner of a kept test comes alone and keeps the hang
first on a shared day — A319 review: on that day only, or it waits. The
historical PASS 3 and PASS 1/2 read the user's sessions as anchors since B414
(below, B369-P6 point 1); the post-merge probe `regeneration_guard_warnings`
is gone.

**Declines (A320, 2026-10-23).** From climb-coach's bug-inbox of 2026-10-18 ("a
retest cannot be declined"). `POST /api/retest/decline` stores a record in
`state.retest_declines` (endpoint-owned; record management in the pure
`retest_declines.py`); `_axis_week_decision` reads the ACTIVE ones (same axis,
`official_date` = the official max it reads — a new test makes them inert):
- a `decline` suppresses its own trigger kind (`_trigger_for_week(..., skip)`,
  the default `()` is the pre-A320 reading): end_of_phase / cycle_start only
  in the macrocycle declined in; the early retest by any active decline until
  2 measured signals are dated after `declined_at` (also in A319's gap →
  early fallback); another kind still fires;
- a `postpone`: weeks entirely before `until` skipped `postponed`; from the
  week holding `until` on, due from `until` with trigger `postponed` (a natural
  trigger that is not declined keeps its name); `until` must come after the
  pending test's own day (a postpone never brings a test forward), and a later
  `decline` ends the axis' postpones (`retest_declines.upsert`: the athlete's
  latest word wins — kept, the postpone brought the declined test straight
  back as `postponed`);
- implicit: a policy test the athlete removed or replaced in week K (the
  plan's removal records, not a move, not an automatic A315 re-schedule:
  `plan_edit_removal`) declines the axis for K only (`source: plan_edit`); a
  test of the axis the athlete puts back in K (an explicit add, still to do
  from today on) lifts it; taking back an extra test of their own declines
  nothing while the policy's test is still in K. This reading comes before a
  stored decline or postpone of the same week, so the regenerated snapshot
  carries the `plan_edit` view (a slot-only removal — a whole-day override —
  keeps matching through it, and a DELETE never reopens K).
All are decided BEFORE the phase / gap / already-scheduled checks and return
`skipped` (`declined` / `postponed`, with the `declined` view: reason code from
a closed set, never the note) — never `None`: the axis stays covered, so the
historical PASS 3 / `test_queue` never take it and the 6-week reminder stays
hidden. The snapshot copies the row unchanged, `skipped_tests` its reason
(planner_v2 unchanged). The endpoint removes the engine's planned tests of the
axis dated from the later of the server's and the athlete's today (both
copies: `week_plans[K]` and `current_week_plan`), with no adaptation event (a
`remove_session` record would empty the slot, B382), stamps the revision and
marks those weeks stale — and the cached week the test now belongs to (a
postpone's `until`, the next trigger of another kind: `week_to_reopen`), which
a cache never regenerates on its own: the next `GET /api/week` regenerates
them under the decline (the freed slot gets a normal engine session). The
athlete's own planned tests are kept and reported. `DELETE
/api/retest/decline/{axis}` removes the records, takes out the engine's tests
placed under a postpone (snapshot trigger `postponed`: nothing backs them
once it is undone — kept, the original week saw them "already scheduled" and
the next regeneration of their own week dropped them) and marks stale those
weeks and the weeks generated under the records. `retest_status`: `declines`,
`plan_edit_declines` (the weeks whose decision is the implicit decline),
`next_test_reason` `declined` | `postponed` (outranks the other reasons), and a
`_stale` week is projected like a week not generated yet (`_hot_plan` itself
unchanged: `_locked_by_merge` still reads stale plans).
`key_sessions_v1._replaceable` never takes the slot of a test the policy
placed (`is_policy_test`: PASS 3a's `retest:` stamp — A294 proposals, A315
automatic application); a test of an uncovered axis is read as before, so an
untested athlete stays byte-identical. The coach block puts the retest section
before the guards when it carries a decline, so a budget cut never drops it.
`inject_tests` bypasses the policy by design: declines are not consulted there.

---

### 8.3 Key sessions — `key_sessions_v1.py` (A294)

The single owner of "which sessions of the week carry the phase's key stimuli". **Derived at read, never persisted**: `compute_key_status(state, today, ...)` reads the week plan (hot + archived), the outdoor logs, the free sessions and the completion log, and returns a status that the API attaches as `key_status` **beside** `week_plan` (so nothing can write it back). Data: `backend/catalog/key_stimuli/v1/key_stimuli.json`.

- **Satisfied by dose, not presence.** For `finger_max` / `pulling_max` a session counts as full only when the main exercise reaches the anchored floor of the phase on that day (`anchored_load(...).floor`) with ≥ 4 sets; otherwise it is `partial` (no ✓, debt stays). Everything else counts on presence.
- **Debt** = target − full-dose days − valid future planned days, current week only (a past week's miss is lost, not carried).
- **Technique by drills, added up over the week (A325).** The technique key is a technique session or two qualifying feet / positioning drills. Drills done outside a technique session are summed across the week's sessions (`_technique_week`); a pending session counts only drills it is committed to (a custom / generated session's own `exercises`, or an instance with `source == "user_added"` — never what the resolver happened to pick). One drill short → `resolution: "topup"` and an entry in `status["topups"]` (`_technique_topup`): the missed drill added after the warm-up of a planned climbing session through `/api/session/add-exercise` — a separate list from `proposals`, because every `proposals` entry is applied as a replanner event by clients already installed. No host that fits (equipment, intensity `low`/`medium`, not a custom, not a test) → the usual whole-session proposal.
- **Session duration is a measure only while plausible (A325)**: `session_duration.plausible_duration` (≤ `MAX_SESSION_DURATION_S`, 5 h). `/api/feedback` drops an implausible value instead of refusing the feedback; `keep_longest` (the B197 rule) never lets an implausible stored value win; report, coach and `/week` readers skip it.
- **One "done" rule (B414)**: a logged row is done by `stimulus.row_done` — the same rule the ladders and the closed loop read (`bw_ladders.ladder_row_done` delegates to it; `logged_entry_counts` / `counted_entries` wrap it). A catalog row closed with Done without the set timer (1×1 lead drills, fall practice, timed work stopped while running), logged from the dialog or posted without a `completed` flag is done; custom / generated rows need a counted set; `completed: false` counts with the full dose. Read-time only: the past is re-read, never rewritten (the week of 02/11 shows try-hard and technique done). `load_score` is not on this rule.
- **Proposals** are validated, not guessed: the candidate goes through the replanner's own `apply_events` on a deep copy (new event `add_planned_session`, catalog session, no day+1 ripple), then the 7 days are diffed. A proposal that downshifts itself or touches a key / custom / forced / done / skipped session is dropped; any other change is shown as a side effect. **A301:** `apply_events` no longer downshifts anything, so a candidate that would ADD a `guards_v1` alert to the week is rejected (`guard_alert`) instead. The finger gap is checked on a unified timeline (plan + outdoor-hard days + free limit sessions, previous and next week), 72 h before a pending max test is off-limits, and a catch-up that would sit next to next week's key becomes `deferred_next`. Very hard feedback or an adaptive replan in the last 72 h → `deferred_fatigue`, no proposal.
- **Insertion check** (`check_insertion`): what a custom / generated session would do to the keys, behind `POST /api/replanner/events` `dry_run: true` — used by the app before adding a custom (confirm, never block) and by `scripts/athlete_context.py --simulate`.
- **Coach**: a compact `## Key sessions this week` block in the dynamic prompt (never the cached static block), and `composer_guard` drops finger-hard lines near a finger key / heavy pulls before a pull-up test from the composer pool (A259 extension). Since A297 the chat block is folded into the single `## Athlete context` block (below); `_key_section` remains only as the fallback when that block cannot be built.
- **Recent exercises (A314)**: `athlete_context.recent_exercises` lists the exercises of the DONE sessions in the 3 days up to the target day (target day included; `counted_entries` rule), grouped per exercise with sets done/prescribed, load and feedback, and the `no_repeat` list (strength_accessory / core / prehab / complementary done in the last 48 h). `repeated_exercises` feeds the `--simulate` alert «ripetizione: X fatto il D» (warm-up / cool-down categories exempt). Context key `recent_exercises`; CLI section «Esercizi fatti negli ultimi 3 giorni».
- **Athlete context in the coach (A297, R7b)**: `backend/coach/athlete_block.py` is the one integration point of the engine's athlete data into an LLM prompt. It gathers archived weeks (only when a week of the 63-day window is cold) and outdoor rows, calls the pure `athlete_context.build_athlete_context` (no proposals, no next week for the composer) and renders it in English: `render_coach_block` for the chat (replaces the key block and the B364 baseline lines), `render_composer_block` placed after the literal request in the ad-hoc composer. `composer_guard_view` turns the day's guard row into pool exclusions (finger-hard ids, front-lever variants; weighted pulls ≥ 85 % 1RM re-checked after validation by `drop_heavy_pulls`), every exclusion listed in `dropped`; the deterministic builder ranks with `_rank_key_ctx` (phase affinity → intensity gap → least recently used → id) on the `variety` collector. Behind `COACH_ATHLETE_CONTEXT` (default on, only `0` disables); off = pre-A297 byte for byte.
- **Replanner additions** (additive): `apply_events(prev_days=)` + a `reconcile` adaptation with the downshifts it used to discard; `downshifted_from` stamped by every downshift; `mark_skipped` stubs keep `skipped_session_id` / `skipped_tags`.
- **Review fixes (A294):** `/events` passes `today` to `apply_events` → `_reconcile(frozen_before=today)`: past days are counted, never rewritten (the Sunday→Monday seed used to downshift an unticked past Monday). Proposals are validated cumulatively and against the heavy-pulling rules (24 h before limit / strength_long, ≤ 2 per 7 days); candidates outside the phase pool are allowed after the in-pool ones. Try-hard needs a fall-practice block (or outdoor-hard / free limit), technique needs feet / positioning drills (outdoor no longer counts) and can turn critical. The coach block sits behind `COACH_ATHLETE_CONTEXT`.
- **Try-hard in the catalog (C276)**: `lead_tryhard_gym` (falls + 2 lead routes with a declared rule) and `route_projecting_gym` (2-3 falls after the warm-up) carry a pinned, strict fall block. `try_hard.session_ids` lists them: `tryhard_hit` counts them by id only while unresolved (no exercise entries), then the fall exercise itself decides. `try_hard.propose` stays empty, so A294 proposals are unchanged; the session is in no phase pool until A305 places it.
- Known divergence: `closed_loop_v1.stimulus_recency` still classifies by session id/tags; the key status reads the A288 exposure view. Not unified in A294.
- **Automatic re-schedule (A315)**: `_propose_for` runs two passes. Pass 1 is the A294 search over free slots, unchanged. Only when it finds nothing, pass 2 tries to **replace** a planned engine session that holds no key role (`key_index`) and that the user does not own (`user_owned.is_preservable` false: never custom, done/skipped, forced, edited, quick-added, moved, overridden, an earlier re-schedule) — A320: never a test the retest policy placed (`retest_policy.is_policy_test`: the `retest:` stamp of PASS 3a; a test of an uncovered axis is read as before); the replacement is a declared side effect (`replaces`, `side_effects`) and is rejected when any other key of the week would owe more (`_week_debts` before/after, reason `key_worse`) or the group gains nothing (`no_gain`). The event is `add_planned_session` + `replace_session_ref`, re-checked in the replanner, which keeps the replaced session in `replaced_original` and logs `replaced_session_id` (so `user_owned.removed_refs` keeps a regeneration from bringing it back). `backend/api/auto_reschedule.py` applies the proposals **only after a write** (`/events` without dry run, `/override`) and only for the keys whose debt went **up** in that call (an old debt the user let go is never re-applied by an unrelated write), never for a key the user undid that week (`auto_reschedule_declined`); the session carries `auto_reschedule` + `auto_reschedule_id` and the week an `auto_reschedule` adaptation. `undo_auto_reschedule {adaptation_id}` takes it back while the session is untouched (planned, not edited, date ≥ today) and puts `replaced_original` back byte for byte. Response field `auto_reschedules[]` (`would_auto_reschedule[]` on a dry run); `adjustments` stays empty. Kill switch `KEY_AUTO_RESCHEDULE=0` (call time); fail-soft (any error leaves only the user's own action). **Why this is not what A301 forbade:** A301 stopped the engine from rewriting the plan *in reaction to the guards*; this is the application of a proposal validated to add no guard alert and to leave no other key worse off, declared in the response and undone with one tap.

### 8.4 Measured feedback — `measured_feedback.py` (A295)

Feedback that measures something instead of a default "ok". `log_entry.feedback_contract: 2`: an untouched exercise has no `feedback_label` and is **not rated** (a legacy `ok` without the contract too). `apply_feedback` reads `feedback_rating(item, contract)`; `None` stays out of difficulty, feedback log and fatigue labels. B413 (D3, A1): a DONE unrated item (`unrated_done`) is an `ok` for every progression — ladders +1 step, loads and grades never written below the memory's own proposal, the endurance streak reset as on `ok`.

- **Measures** (allowlists in `measure_kind`, exposed as `suggested.measure`): `last_set_reps` on pulls (consumed by `anchored_load.apply_anchored_feedback`, which already had the bands and the `retest_signals` rule from B364; A295 adds "fewer sets than prescribed never raises" and the pain freeze), `hang_margin` / `hang_held_s` on max hangs (anchored path, plus a mirror for the non-anchored hangs — untested max hangs, 10 s, Hörst — with the same kg bands and a +5 % rolling-7-day rise cap), `dp_reps` on reps accessories.
- **Double progression** (`progression_v1._apply_dp_feedback`): measured success → target +1 rep, at the top of the range → load +2.5 % (fingers +1.25 %) and back to `lo`; no measure → easy +5 % / very_easy +10 % (a stored `adjustment_policy` still wins); per-hand items read the weaker hand. Idempotent via `applied {key, base_before}`.
- **Pain** (`record_pain` at write, `pain_adjust_suggested` / `anchored_load.pain_for` at read, by date): `progression_counters.pain_blocks[site]`; −10 % on the zone, hang caps 0.85 / 0.80, upward steps and retest signals frozen. Nothing is removed from the plan.
- **Difficulty** (`derive_session_difficulty`): rated items only, ≥ 50 % of the fatigue cost, else absent — `check_adaptive_replan` rule 2 cannot fire on one tapped warm-up.
- **Clamp order** stays the single one of §8.1 (pain before the floor).

### 8.5 Bodyweight ladders — archive, frozen prescription, done without feedback (B413)

The ladder closed loop (`bw_progression.py`, rules in `docs/vocabulary_v1.md`
§4.8) has three API-side pieces, all in `backend/api/`:

- **Archive loader** — `ladder_archive.load(state, user_id, refs, write=…)` /
  `for_plan(...)`: the A221 cold-store weeks of the ONE Monday-aligned ladder
  window (`bw_ladders.archive_window_start`, 120 d), read once per request with
  an open end (`OPEN_END`). No read for an athlete the tested gate keeps out,
  nor when every archivable week of the window is still hot. The retest
  policy and the key status serve their own narrower ranges from the same read
  (`ladder_archive.read_range` → `storage_memo.find`), so a tested athlete costs
  at most one archive range read per request (B376 memo). `write_state` no
  longer clears the request memo (no memoised read depends on the users row;
  archive, outdoor and delete writes still clear it). A failed read: GET
  serves the recent-weeks view and persists nothing derived from it (no B375
  cache); a write that freezes or consumes a ladder dose (`/feedback`,
  `/events`, `PUT /bw-progression/{family}`, `POST .../promotion`,
  `POST /session/surface-override`) answers 503 `archive_unavailable` before
  writing anything. The `/events` dry run loads no archive.
- **Frozen prescription (D2)** — `plan_revision.freeze_played_resolved`
  (`compute_played_resolved` + `write_played_resolved`): at the planned → done
  transition of an engine session the server stores the `resolved` GET would
  show (`week._auto_resolve` with `stop_after`: B268 order, A281 taper,
  user_added rows, the phase of the week) on the plan before the "done", the
  state before the feedback and the same archive. `/events` freezes from the
  stored plan of the week (not a stale client copy); `/feedback` (B216 path
  included) writes it after `apply_feedback`, so the closed-loop inputs are
  unchanged. Fail-soft; B375 stays the fallback for old records.
- **Done without feedback (D3)** — `/events` `mark_done`: the ladder rows of
  the frozen prescription go through `apply_bw_item` as done, unrated rows
  (`bw_progression.mark_done_items`); a later feedback replays from `_prev`
  (idempotent); `mark_planned` (undo) reverts the families the session still
  owns (`revert_session`). Loads are never touched.

The engine stays pure: every ladder reader takes `archived_weeks` as an
argument (None = hot weeks, the pre-B413 behaviour).

## 9. Replanner (`replanner_v1.py`)

Handles runtime modifications to the week plan after initial generation.

### Intent system

**15 indoor intents** (mapped via `INTENT_TO_SESSION`):
```
aerobic_endurance, core, endurance, finger_maintenance, finger_max,
flexibility, hard, power, power_endurance, prehab, projecting,
recovery, rest, strength, technique
```

**4 outdoor intents** (mapped via `OUTDOOR_INTENT_TO_DISCIPLINE`):
```
outdoor_boulder, outdoor_easy, outdoor_projecting, outdoor_volume
```

### Key operations

**`apply_day_override(plan, *, intent, location, target_date, slot, phase_id, gym_id, gyms, session_index)`**

Resolves intent to session_id, finds the target day (B157: searches all weeks, not just first), and replaces or adds the session. Equipment-aware: `_resolve_intent_for_equipment()` implements a fallback chain (B96) when the gym lacks required equipment.

**`apply_events(plan, events, *, availability, planning_prefs, gyms)`**

Processes event lists. Supported event types:
- `mark_done` / `mark_skipped` / `mark_planned` — status transitions (B414: a `mark_done` whose `session_ref` / `slot`
  match nothing on that day raises `SessionNotInPlan`, a `ValueError` → 422 at `/events`, like the "session not found"
  of `mark_skipped`; `/feedback` refuses the same case first — 409 `session_not_in_plan` before any write, same
  `_session_matches` on the plan the inline mark_done writes — and never retries it on another week)
- `move_session` — relocate within the week
- `remove_session` — delete from day
- `complete_other_activity` / `add_other_activity` — non-climbing activities
- `add_outdoor` / `complete_outdoor` / `undo_outdoor` / `remove_outdoor` — outdoor sessions (`undo_outdoor` only un-ticks the day: since B403 the router no longer deletes the day's `outdoor_logs`)
- `change_gym` — equipment-aware session replacement via `_find_gym_change_replacement()` (A319: a 2RM test moved to a gym without weights is replaced too; B414: the combined keeps its max hang where the hangboard is — see the A319 notes of §8.2). B414: to home it checks the event's `home_equipment`, else the saved kit `apply_events(home_equipment=state.equipment.home)` (None = unknown, not checked; a list, even empty, is what is there); the /events dry run (`check_insertion`, `_simulate_add`) passes the same gyms and home kit as the write.
  **A326 (D287 E1/E2) — the replacement keeps the stimulus.** One fit check, `_venue_check`, for the session that moves and for every candidate, aligned with planner_v2: the gym's equipment with the implicit pull-up bar (`_gym_equipment`, as `_equipment_for_location`; an unknown `gym_id` still has none), the catalog location widened by `_expand_session_locations` (a home wall / board hosts a wall session at home), then `required_equipment`. A session that does not fit gets, in order (`_stimulus_replacement`, the first hit wins; the note is the third `explain` entry):
  1. `kept_key=<key>` — a key of the phase the session carries (`key_sessions_v1.session_keys`, on the session as it is, resolved exercises included): the first `floor_candidates` then `session_ids` of that requirement (key_stimuli.json) that fits — a route endurance session resolved with linked laps keeps the PE key as `power_endurance_gym` at a boulder gym;
  2. `same_load` — primary sessions only (hard or climbing, `_is_primary_session`): the first primary session of the phase pool (`profile_snapshot.session_pool`, else `_build_session_pool`) with the same hard / finger tags, within the phase intensity cap — `route_projecting_gym` at Bkl becomes `limit_boulder_gym`, `lead_tryhard_gym` at a boulder gym `technique_focus_gym`, a limit evening at home `finger_strength_home`;
  3. home, primary sessions only: `open_key=<keys>` — a home session for a key still open in the event's week (`_keys_open_this_week`: presence via `session_delivers`, a done session counts, a planned one from `today` on, a skipped one never; candidates in the requirement's `propose` / `floor_candidates` / `session_ids` order, the one covering most open keys wins — `strength_long` when finger max and max pulling are both owed), within the cap; else `strength_maintenance` (`finger_maintenance_home`);
  4. the B414 chain, unchanged (`complementary_conditioning`, else `regeneration_easy`).
  Not touched: a test (it measures; the combined keeps its hang, otherwise the B414 chain — never a training session of its key), a session that is not primary for steps 2-3 (a complementary lunch keeps the B414 chain, so a whole-day change never puts a key session on the lunch), done / skipped sessions, any other slot or day. A replaced session keeps the user's markers and loses the engine constraints of the session that left (`carry_user_markers(s, [])`: `auto_reschedule` goes, `key_reschedule` / `user_moved` stay — marker semantics unchanged); `missing_equipment={…}` is printed sorted. Guards are not consulted (A301: finger gap, heavy pulls, hard cap stay alerts). Known limits: no boulder session delivers `try_hard` or `project` and only finger / pull keys are deliverable at home, so those keys still go (the dry run reports `key_removed`); the next regeneration of the week re-picks the slot for its place (B414 Option B), so an engine session's replacement is not pinned
- `set_availability` — **retired in B367**: `ValueError` in the engine, 422 at `/events`. It regenerated the week with a fraction of the `GET /api/week` inputs (no tests, retest decisions, taper, finger device) and overwrote the snapshot; availability changes go through settings / `PUT /api/weekly-override/{week_start}`

**Tags of a user-authored session (B345, B392, B405, B414, B416).** `add_custom_session` stores the tags
`session_tags.derive_session_tags` computes once from the exercises (`add_generated_session` merges them with the
declared ones, only escalating). `hard` = a finger-hard id (B405), or any `max` exercise, or two `high` exercises that are climbing, pulling or pushing load — B416: core / conditioning / complementary / prehab / mobility exercises, handstand skill work and leg patterns (squat, lunge, hinge, calf raise, hip isolation) count as medium, while the heavy-pull ladder ids (front lever family, `bw_ladders.heavy_pull_exercise_ids`) always count. `finger` comes from the finger-loading patterns / domains (not a light warm-up);
B414 (rule E2): a sub-max hang (pattern `repeater_hang` / `isometric_hang` / `hang`, intensity ≤ medium, not
finger-hard by itself, not a test, catalog finger stress not `high` — so `test_repeater_7_3_to_failure` is not one) does **not** make the session `finger` when it has PE intervals (role main,
`climbing_intervals`, PE / anaerobic domain) and no other finger load — the custom then equals `power_endurance_gym`
(`finger: False`). Stored tags are never rewritten; a rule change surfaces as `STALE_CUSTOM_TAGS` (B395).

**`apply_day_add(plan, *, session_id, target_date, slot, location, phase_id, gym_id) → tuple`**

Quick-add flow: places a session in a specific slot. Used by the quick-add UI.

**`suggest_sessions(plan, target_date, location, *, session_pool, max_suggestions) → List`**

Returns up to N session suggestions for quick-add, filtered by location and equipment compatibility.

### Guards after a user action: alerts, not rewrites (A301)

Since A301 (2026-10-05, Daniele: "se voglio fare sovrallenamento lo faccio, decisione mia, tu solo segnala
alert") no user action rewrites a session the user did not touch. `apply_day_add`, `apply_events` and
`apply_day_override` no longer call `_reconcile`; the recovery ripples (B366), `_compensate_finger` and
`_protected_neighbor_guard` are gone. What the guards object to is computed at read time by
**`guards_v1.evaluate(plan, prev_days, today, state)`** (pure, deterministic, never persisted) and returned as a
`guard_warnings[]` sibling of `week_plan` on `GET /api/week` and every replanner response (codes `finger_gap`,
`finger_test_72h`, `heavy_pull_7d`, `hiit_near_max`, `hard_cap`, `pre_trip`, `post_outdoor`, `hard_back_to_back`;
A327 adds `finger_hard_cap`, `max_hang_cap`, `crag_block` — see below).
The week-level `low_rest_days` of A305 is NOT in that list: `evaluate(..., include_week=True)` /
`guards_v1.evaluate_week()` return it, and `GET /api/week` sends it as a separate `week_guard_warnings[]`
sibling — the client matches `guard_warnings` per session with a null slot as a wildcard. See
`docs/vocabulary_v1.md` §5.7.1). Only sessions that can still change are flagged; history counts. Since B372
an outdoor day (declared and still ahead, logged hard, big load, or completed without a route log —
`stimulus.outdoor_fatigue_days`; the planner's bare `outdoor_slot` is availability and does not count) is a hard, finger-loading day for these alerts and for the `athlete_context`
guards; nothing is rewritten and planner-generated weeks do not change.

- `_enforce_caps()` / `_enforce_no_consecutive_finger()` (via `_reconcile`): B414 removed their last engine
  caller, the post-merge `regeneration_guard_warnings` probe of B369 (the planner now respects the gaps and the
  cap around the user's sessions, B369-P6 point 1); they stay pinned by their tests (b287, b165b, b367). Their
  counting rules (done counts, skipped not, frozen past, `recovery_multiplier` gap) are the same definitions
  `guards_v1` reads.
- Override replaces only the targeted slot — an inferred target replaces engine sessions only, never the
  user's; `whole_day` (default for `rest` with no index/slot, the "Skip day" button) replaces every engine
  session of the day; `move_session` refuses a done/skipped destination; quick-add `force`
  is a no-op.
- The planner (`generate_phase_week`), building a week on its own, still respects every guard; the A294 key
  re-schedule proposals reject a candidate that would add a guard alert (`reason: guard_alert`). A315 applies
  those proposals automatically after a write that lost a key (toast + Undo) — see §8.3: nothing is rewritten
  in reaction to a guard, and the replaced session (never the user's, never a key) comes back on Undo.
- `_recovery_gap(plan)`: Helper (B165b) — reads `profile_snapshot.recovery_multiplier` and returns `ceil(1 * multiplier)`. Same formula used by the planner.

**Weekly finger caps and crag blocks (A327 step A, D288 R1 + R2).** Three alerts, ENGINEERING CONSTANTS in
`retest_policy` (low confidence, `docs/audit/D288_kb_research_r1_r8.md` Q1 / Q2):
- `finger_hard_cap` — more than `FINGER_HARD_WEEKLY_MAX` (3) finger-hard days in the calendar week, a crag day that
  counts (B372) included (Daniele, 2026-11-13). Unit: `stimulus.is_finger_hard_exposure` — the exercises decide
  when the session has a list (finger_max / limit_power family, `FINGER_FATIGUE_EXTRA_IDS`,
  `FINGER_HARD_LIBRARY_IDS`, `FINGER_HARD_CLIMB_IDS`), a planned catalog slot its finger + hard flags. Narrower than
  `is_finger_hard_session`: repeaters / intermittent hangs at 60-80 % to failure stay in the 48 h spacing but are not
  an exposure (answer 2). Flagged like `hard_cap` (latest sessions past the cap; `count`, `cap`; a count code).
- `max_hang_cap` — more than `MAX_HANG_WEEKLY_MAX` (2) max-hang days (`stimulus.is_max_hang_session`: finger_max
  family, the max-hang tests through `SESSION_FALLBACK_STIMULI`).
- `crag_block` — a run of ≥ `CRAG_BLOCK_MIN_DAYS` (2) consecutive crag days that count (`guards_v1.crag_runs` over the
  B372 days, across the week boundary): c+1 a true rest day (`is_rest_day_session`: a complementary lunch — HIIT,
  legs — or recovery keeps it), c+2 no hard session, no finger session before `CRAG_BLOCK_FINGER_H` (72 h) after
  the last crag day ends at `complementary_v1.OUTDOOR_END_HOUR` (18:00) on the `SLOT_HOUR` clock. `detail` ∈
  `rest_day | no_hard | finger_72h` (one alert per session, that precedence), `crag_days`, `finger_ok_from`;
  `post_outdoor` leaves c+1 to it. After a crag weekend nothing is regenerated (answer 3).
- **Indoor redpoint attempts are finger-high (answer 4):** `stimulus.FINGER_HARD_CLIMB_IDS`
  (`route_redpoint_attempt`) is read by `is_finger_hard_session` / `is_finger_hard_exposure` and by
  `session_tags` (finger + hard on its own, the B405 rule) — a redpoint custom counts like the catalog
  `route_projecting_gym`. The composer's pool lists (`athlete_context._finger_hard_ids`) do not read it.
- `athlete_context` gives the same rules as `guards.days[].day_warnings` / `day_warning_codes` (codes
  `finger_hard_cap | max_hang_cap | crag_block`), plus `guards.finger_cap` and `guards.crag_blocks` — advisories
  only, never a reason of `finger_max_ok`, so the composer pool never loses an exercise for them (decision 3).
- **Step D — the planner enforces them on its own placements** (never on the user's: they count and are never
  moved). Crag days: `generate_phase_week(crag_hard_dates=)` — GET /api/week passes the alerts' log reading
  (`stimulus.outdoor_fatigue_days` over the previous week + this one, `outdoor_logs` rows); `None` falls back on
  B382(b)'s declared reading. **Caps:** `_fh_cap_ok(offset, sid, victim)` counts the finger-hard exposure days and
  max-hang days of the week (engine sessions, lived days, the user's own sessions, the crag days); a day already
  holding one adds nothing, replacing one is neutral; read by PASS 1, 1.5, 2, 2.2, the floors, 2.6, 2.7 (callback)
  and legacy PASS 3; PASS 3a uses `_test_cap_ok` on the merged week. **Answer 1:** in strength_power, when the crag
  days / the user's finger-hard days leave ONE finger-hard day and the pool holds a limit_power session the equipment
  can host, that day is reserved for it (`_reserve_for_limit`: max hangs wait). **R2:** `guards_v1.crag_runs` over
  the hard crag days (previous week included): c+1 leaves the engine's days before the pruning (`day_crag_rest`;
  a complementary lunch is still placed — decision 2), c+2 is a no-hard day (`_no_hard`: PASS 1, 1.5, 2.7, 3a, the
  floors, 2.6, legacy PASS 3), and `crag_windows` (c 18:00 → +72 h) block a finger-high placement in
  `_finger_clock_ok` / `_test_clock_ok` / PASS 2.7. After a crag weekend nothing regenerates the next week (answer
  3): the anchor acts when the week is generated after it. Weeks without crag days or user sessions: unchanged.
- **Step C — tiers and the 6 h spacing:** `stimulus.finger_load_of(session)` is THE tier reading (stored
  `tags.finger_load` → `_SESSION_META[sid].finger_load` unless `tags.finger` is an explicit False → old `finger`
  tags = high → finger-hard exercises under stale tags = high → None). `session_tags.derive_finger_load`
  (same exercises as the `finger` tag: B392 warm-ups ignored, B414 E2 sub-max hangs after PE intervals only next
  to other finger load; a finger-hard id → high; else the highest catalog tier, missing = high) is stored once at
  insertion (`add_custom_session`, `add_generated_session` raised to a declared tier) via
  `tags_with_finger_load`. `finger_gap` is high–high; `finger_low_gap` (new) covers low–high / low–low < 6 h ×
  multiplier and > 2 low a day (`detail` gap | per_day, `gap_h`, `low_count`); `post_outdoor`, the crag-block 72 h
  and `hard_back_to_back`'s crag side read high; `is_finger_hard_session`'s finger ∧ hard clause skips a low tier
  (a ramp-up + weighted-pull custom no longer blocks the 72 h test). `athlete_context`: `_session_view.finger_load`,
  the spacing reasons read high only, B395 compares the tier (absent with finger True = high).
  `suggest_sessions` −1000 only high next to high; `_stimulus_replacement` keeps (hard, tier); key proposals check
  the gap for a high candidate. The composer's pool is unchanged.
- **Step B — `finger_load` in the exercise catalog:** `high | low` on the 57 exercises that load the finger flexors
  for `session_tags` (and the finger-hard ids). `low` = ≤ 50 %, no failure, ≤ 10 min under load, by a pinned rule
  (`docs/vocabulary_v1.md` §2.5.1); everything else `high`. `finger_aerobic_base` is made honest: the template
  `finger_aerobic_endurance` picks its main hang with `pattern: [hang, isometric_hang]` (never the 55-65 %
  intermittent hangs). No golden key moved.

### Completed session preservation

**Immutability invariant (B369):** `_is_preservable()` = status `done`/`skipped` **or** `user_owned.is_user_owned()` (forced, custom, quick-add, override, key re-schedule, moved, custom/generated add, `_user_edited`). Preservable sessions are **never** modified or dropped by regeneration.

`regenerate_preserving_completed(old_plan, new_plan, preserve_before)` and `merge_prev_week_sessions(prev_plan, new_plan, preserve_before)` are the same merge, `_merge_user_content`, for the SAME week only (exact-date matching; a plan of another week is discarded — no weekday fallback): days before `preserve_before` (and that day if it holds a done session) are copied wholesale; on every other day the old plan's preservable sessions are put back in their slot, and an engine session leaves the day only through a removal logged in `adaptations` (`remove_session`, the source of `move_session` and the session a move overwrote, the session / slots a `day_override` replaced, the whole date of an outdoor override) — a slot shared by a user session and an engine session keeps both, a slot the user's session took over does not get the engine's back; B414: the merged week is no longer probed (the planner respects the finger gap, the hard gap and the hard cap around the user's sessions; the old `regeneration_guard_warnings` record is dropped); B379: a day in `user_owned.engine_free_dates(old_plan)` (whole-day/outdoor override, or an outdoor day declared on the plan through `add_outdoor` / `set_outdoor_plan` / an override) is copied wholesale from `preserve_before` on too — sessions, outdoor block, status — so a planned crag day never receives engine sessions (before B379 the generated sessions landed there and `_DAY_LEVEL_FIELDS` put the outdoor back on top); `planned_load` comes from the old plan only when days of the week were skipped; the outdoor/other-activity day fields are kept, and `adaptations` is carried forward. Invalidations do not delete cached weeks: `deps.mark_weeks_stale` flags them `_stale` and `GET /api/week` regenerates them through this merge; a failed regeneration or merge serves the cached plan and saves nothing (`regeneration_failed`).

**Adaptive replan (B369):** `check_adaptive_replan` (very_hard/fail → next hard session, or a recovery day after two in 3 days) only feeds `build_adaptive_suggestion`, returned by `/api/feedback` as `adaptive_suggestion`. The plan is never changed.

---

## 10. Exercise Ordering (`exercise_ordering.py`)

### 14 sort categories

Derived from exercise `role`, `domain`, `pattern` via `infer_sort_category()`:

```
warmup → activation → aerobic_pure → threshold → strength_neural → power →
pe_intervals → finger_endurance → pulling_supplementary → technique →
core → antagonist_prehab → cooldown    [+ main_unclassified fallback]
```

**Derivation priority:**
1. `role: "prehab"` (and not "main") → `antagonist_prehab`
2. `role: "warmup"` → `warmup`; `role: "cooldown"` → `cooldown`; `role: "activation"` → `activation`
3. `role: "technique"` or `domain: "technique_*"` → `technique`
4. Domain-based mapping (see `exercise_ordering.py:lines 108-173`). B414: a sub-max hang whose first domain is `finger_aerobic_endurance` (pattern `repeater_hang` / `isometric_hang` / `hang`: `sub_max_capacity_hang`, `intermittent_dead_hangs`, `bar_dead_hang`…) is `finger_endurance`, not `aerobic_pure` — so constraint 3 no longer puts it before the PE intervals; the ARC on the wall (`aerobic_capacity`) stays `aerobic_pure`
5. Fallback: `main_unclassified`

### Phase sort order

`PHASE_SORT_ORDER` (`exercise_ordering.py:lines 180-261`) defines priority per phase. The principle: **neural/high-intensity work first, endurance/accessories last.**

Example — `strength_power` phase priority:
```
warmup(0) → activation(1) → strength_neural(2) → power(3) →
pulling(4) → finger_endurance(5) → threshold(6) → technique(7) →
aerobic(8) → core(9) → antagonist_prehab(10) → cooldown(11)
```

### 6 hard constraints (`enforce_ordering_constraints()`)

Applied **after** the phase sort. Auto-fix with logging when violated:

1. **Warmup always first** — warmup exercises before all others
2. **Cooldown always last** — cooldown exercises after all others
3. **ARC before pump** — `aerobic_pure` before `threshold`/`pe_intervals`
4. **Max hangs before pulling** — `strength_neural` before `pulling_supplementary`
5. **Accessories after main** — `core`/`antagonist_prehab` after all main work categories
6. **Declared "after warm-up" blocks (C276)** — an instance whose catalog block declares `"order": "after_warmup"` (`source.order`, set by the resolver only where declared) moves right after the leading warm-up / activation exercises. Applied last. Declared today by the fall blocks of `lead_tryhard_gym` and `route_projecting_gym` (falls while fresh, athlete_plan §5 — without it the phase sort put them after the redpoint attempts), by the press of `arms_shoulders_handstand_lunch` (A318) and by the finger warm-up, max hang and 2RM blocks of `test_max_hang_pullup` (A319).
7. **Declared "last" blocks (B417)** — an instance whose catalog block declares `"order": "last"` moves to the end of the work, in its sorted order, ahead of any trailing cooldown (constraint 2 holds). Applied after constraint 6. Declared today by the handstand pair of `arms_shoulders_handstand_lunch` (Daniele 2026-10-25: «Handstand solo alla fine» — toe pulls, then the wall hold).

### P0 invariant

Both `sort_exercises_by_phase()` and `enforce_ordering_constraints()` verify that no exercises are lost during reordering. On detection of loss, they return the original unsorted list as a safe fallback.

---

## 11. Catalog File Structure

### Session JSON (`backend/catalog/sessions/v1/`)

Annotated example (`strength_long.json`):
```json
{
  "id": "strength_long",                          // Unique session_id
  "name": "Strength Day (Long Session)",           // Display name
  "version": "2.0",                                // Session version
  "intent": {                                      // What this session targets
    "primary_goal": "finger_max_strength",
    "secondary_goals": ["climbing_movement", "pulling_strength", "core_tension", "joint_health"]
  },
  "compatibility": {
    "slot": ["long"],                              // Which time slots fit
    "sports": ["climbing"]
  },
  "required_equipment": ["hangboard"],             // Hard equipment requirement
  "context": {"location": "gym"},                  // Default location
  "time_budget": {"target_duration_min": 90, "hard_cap_min": 120},
  "modules": [                                     // Ordered list of modules
    {"template_id": "warmup_climbing", "required": true, "priority": 100, "module_role": "general_warmup"},
    {"template_id": "finger_max_strength", "required": true, "priority": 90, "module_role": "primary"},
    {                                              // Inline block (no template_id)
      "block_id": "climbing_movement",
      "required": false, "priority": 80, "module_role": "secondary",
      "selection": {"primary": {"filters": {"role": ["technique"], "domain": ["technique_boulder"]}}}
    },
    {"template_id": "antagonist_prehab", "required": true, "priority": 65, "module_role": "secondary"},
    {"template_id": "cooldown_stretch", "required": false, "priority": 40, "module_role": "cooldown"}
  ]
}
```

Sessions reference templates via `template_id` or define inline blocks with `block_id` + `selection`.

### Module template JSON (`backend/catalog/templates/v1/`)

Annotated example (`warmup_climbing.json`):
```json
{
  "id": "warmup_climbing",
  "name": "Climbing Warm-up (Module)",
  "category": "warmup_module",
  "stress_tags": {"fingers": "none", "cns": "low", "elbow": "low", "skin": "none"},
  "blocks": [                                      // Ordered exercise selection blocks
    {
      "block_id": "pulse_raise",
      "type": "warmup_general",
      "mode": "select_one",                        // Also: "instruction_only"
      "exercise_id": "general_pulse_raise",        // Explicit exercise → bypass P0
      "role": ["warmup"],                          // Used by P0 if no explicit exercise_id
      "domain": ["aerobic_capacity"]
    },
    {
      "block_id": "upper_activation",
      "type": "activation",
      "mode": "select_one",
      "role": ["warmup", "prehab"],                // P0 role filter (ANY match)
      "domain": ["prehab_shoulder"],               // P0 domain filter (soft)
      "prescription": {"sets_range": [2, 3], "reps_range": [8, 15]}  // Overrides exercise defaults
    }
  ]
}
```

Blocks with `exercise_id` → direct lookup. Blocks with `role` → P0 filter selection.

### Exercise JSON (`backend/catalog/exercises/v1/exercises.json`)

Single file with `{"version": "2.1", "exercises": [...]}`. Each exercise:
```json
{
  "id": "max_hang_7s",
  "name": "Max Hang (7s)",
  "category": "main_strength",
  "role": ["main", "test"],                        // P0 role matching
  "domain": ["finger_strength", "finger_max_strength"],  // P0 domain matching
  "pattern": "isometric_hang",                     // P0 pattern matching
  "intensity_level": "max",
  "fatigue_cost": 9,                               // Used for session load score
  "recency_group": "finger_max_hang",              // Family-level recency dedup (B159b)
  "equipment_required": ["hangboard"],             // P0 hard filter
  "location_allowed": ["home", "gym"],             // P0 hard filter
  "contraindications": ["elbow_sensitive", "finger_sensitive"],  // P0 limitation filter
  "load_model": "total_load",                      // Drives progression injection
  "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.9},
  "prescription_defaults": {"sets": 5, "work_seconds": 7, "rest_between_sets_seconds": 180},
  "stress_tags": {"fingers": "high", "elbow": "medium", "cns": "medium"},
  "cues": ["Edge/weight you can hold exactly 10s max", ...],
  "video_url": "https://..."
}
```

See `vocabulary_v1.md` for the complete field specification of all exercise, template, and session schema fields.

### Reference chain

```
session JSON
  └─ modules[].template_id ──→ template JSON (backend/catalog/templates/v1/{id}.json)
       └─ blocks[].exercise_id ──→ exercise (exercises.json, by id)
       └─ blocks[].role/domain ──→ P0 filter → exercise selection
```

---

## 12. Key Data Structures Reference

### `_SESSION_META` — complete listing

35 sessions registered (in `_SESSION_META`; 35 session JSON files on disk). See `planner_v2.py:lines 38-72` for the full dict.

Key session categories:
- **Hard + climbing:** `strength_long`, `power_contact_gym`, `limit_boulder_gym`, `power_endurance_gym`
- **Hard + non-climbing:** `finger_strength_home`, `pulling_strength_gym`
- **Finger maintenance:** `finger_maintenance_home`, `finger_maintenance_gym`, `finger_endurance_short`, `finger_aerobic_base`
- **Complementary:** `prehab_maintenance`, `flexibility_full`, `yoga_recovery`, `handstand_practice`, `complementary_conditioning`, `regeneration_easy`
- **Climbing easy:** `endurance_aerobic_gym`, `technique_focus_gym`, `easy_climbing_deload`, `route_endurance_gym`, `boulder_circuit_gym`
- **Supplementary (quick-add only):** `pulling_strength_gym`, `heavy_conditioning_gym`, `lower_body_gym`, `upper_body_weights`, `legs_strength`, `core_training`
- **Tests:** `test_max_hang_5s`, `test_max_hang_7s`, `test_lp_max_5s`, `test_repeater_7_3`, `test_lp_repeater`, `test_max_weighted_pullup`, `test_pullup_bw`, `test_max_hang_pullup` (A319: both max tests in one session, PASS 3a only)
- **Deload:** `deload_recovery`, `deload_finger_touch` (A328: the deload's finger exposure — finger, not hard)

### Week plan structure (in `user_state.week_plans`)

```python
user_state["week_plans"]["2026-03-24"] = {
    "plan_version": "planner.v2",
    "generated_at": "...",
    "start_date": "2026-03-24",
    "profile_snapshot": {
        "phase_id": "strength_power",
        "domain_weights": {"finger_strength": 0.35, ...},
        "intensity_cap": "max",
        "allowed_locations": ["gym", "home"],
        "hard_cap_per_week": 3
    },
    "weekly_load_summary": {"total_load": 285, "hard_days_count": 3, "recovery_days_count": 2},
    "weeks": [{
        "week_index": 1,
        "phase": "strength_power",
        "targets": {"hard_days": 3, "finger_days": 2, "deload_factor": 1.0},
        "days": [
            {
                "date": "2026-03-24", "weekday": "mon",
                "sessions": [{
                    "slot": "evening",
                    "session_id": "strength_long",
                    "location": "gym",
                    "gym_id": "palestra_1",
                    "phase_id": "strength_power",
                    "intensity": "max",
                    "estimated_load_score": 85,
                    "tags": {"hard": true, "finger": true},
                    "explain": ["phase=strength_power", "slot=evening", "day=mon", "pass1:primary"],
                    "status": "planned",          // added at runtime: planned/done/skipped
                    "resolved": { ... }            // added after resolve_session()
                }]
            },
            // ... 6 more days
        ]
    }]
}
```

### Resolved session exercise instance

```python
{
    "instance_id": "main_01",
    "exercise_id": "max_hang_7s",
    "name": "Max Hang (7s)",
    "category": "main_strength",
    "video_url": "https://...",
    "cues": ["..."],
    "variant": {},
    "prescription": {"sets": 5, "work_seconds": 7, "rest_between_sets_seconds": 180},
    "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.9},
    "load_model": "total_load",
    "unilateral": false,
    "block_uid": "finger_max_strength.main",
    "source": {"picked_by": "resolver_v0.2/p0_hard_filters", "template_id": "finger_max_strength", "block_id": "main"},
    "suggested": {                                 // Injected by progression_v1
        "target_total_load_kg": 72.5,
        "added_weight_kg": 2.5,
        "intensity_pct_of_total_load": 0.9,
        "based_on": {"max_total_load_kg": 80.5, "bodyweight_kg": 70.0}
    }
}
```

Cardio instances whose catalog exercise has an `hr_target` (A316) carry it
unchanged — `{"basis": "hr_max", "work_pct": [90, 95], "recovery_pct": [65, 75]}`.
The resolver only copies it; bpm are computed at display time from
`body.hr_max_bpm` (see `vocabulary_v1.md` §2.1). Instances without a band keep
their shape.

> The `adjustments.per_exercise` multiplier structure (A245 E-4) and the
> `cooldowns.per_cluster` structure (B299) that used to be documented here were
> both removed — neither was ever written in production. Reactive adaptation is
> `working_loads` load progression alone (see the `suggested` block above and §7).

---

## 13. Cross-Module Dependencies

### Import map

```
planner_v2.py
  ├── equipment_utils.expand_equipment
  └── macrocycle_v1.{PHASE_INTENSITY_CAP, PHASE_ORDER, _build_session_pool, apply_deload_week}

replanner_v1.py
  ├── equipment_utils.expand_equipment
  ├── macrocycle_v1.{PHASE_ORDER, PHASE_INTENSITY_CAP, _build_session_pool}
  └── planner_v2.{_SESSION_META, generate_phase_week, _normalize_availability, ...}

resolve_session.py
  ├── equipment_utils.expand_equipment
  ├── cluster_utils.parse_date
  ├── progression_v1.inject_targets
  └── exercise_ordering.{sort_exercises_by_phase, enforce_ordering_constraints}  (lazy import)

macrocycle_v1.py
  └── assessment_v1.{_GRADE_INDEX, grade_gap}

progression_v1.py
  └── assessment_v1.{grade_index, brzycki_1rm, ...}

exercise_ordering.py
  └── (no engine imports — standalone)

assessment_v1.py
  └── (no engine imports — standalone)

macro_position.py                     (A288 — pure; backend.api.deps delegates to it)
  └── (no engine imports — standalone)

stimulus.py                           (A288 — family table + exposure views, read-only)
  ├── assessment_v1.GRADE_ORDER, free_session.FONT_GRADES
  └── planner_v2._SESSION_META  (lazy import)

retest_policy.py                      (A288 — official_max / test_confidence;
                                       A289 — retest_decisions / retest_status)
  ├── stimulus.{exposure_dates, count_exposures, session_flag, ...}
  └── progression_v1.estimate_1rm_from_2rm  (lazy import)

retest_declines.py                    (A320 — decline / postpone records, pure; the policy
                                       reads them, POST/DELETE /api/retest/decline write them)
  ├── retest_policy.{axis_official, axis_declines, _axis_week_decision, _hot_plan, ...}
  └── user_owned.is_user_owned  (lazy import)
```

### Shared constants

| Constant | Defined in | Consumed by |
|----------|-----------|-------------|
| `_SESSION_META` | `planner_v2.py` | `planner_v2`, `replanner_v1` |
| `_INTENSITY_TO_LOAD` | `planner_v2.py` | `planner_v2` |
| `PHASE_ORDER` | `macrocycle_v1.py` | `macrocycle_v1`, `planner_v2`, `replanner_v1`, `resolve_session` (lazy) |
| `PHASE_INTENSITY_CAP` | `macrocycle_v1.py` | `macrocycle_v1`, `planner_v2`, `replanner_v1` |
| `SORT_CATEGORIES` | `exercise_ordering.py` | `exercise_ordering` |
| `PHASE_SORT_ORDER` | `exercise_ordering.py` | `exercise_ordering` |
| `RECENCY_LOOKBACK_WEEKS` | `resolve_session.py` | `resolve_session` |

### Circular dependency: planner_v2 ↔ replanner_v1

`replanner_v1` imports from `planner_v2` (`_SESSION_META`, `generate_phase_week`, `_normalize_availability`, `SLOTS`, `WEEKDAYS`, `_INTENSITY_TO_LOAD`). `planner_v2` does **not** import from `replanner_v1`, so the dependency is one-directional at the Python level. However, both modules share `_SESSION_META` as the source of truth for session properties, creating a logical coupling.

> **Note:** R143 proposes extracting `_SESSION_META` to a shared module (`session_registry.py`) to make this dependency explicit and break the conceptual coupling.

### user_state access patterns

| Module | Reads | Writes |
|--------|-------|--------|
| `assessment_v1` | `assessment.*`, `goal` | — (returns profile) |
| `macrocycle_v1` | `goal`, `trips`, `macrocycle` (for from_phase) | — (returns macrocycle) |
| `planner_v2` | `availability`, `equipment`, `planning_prefs`, `preferences` | — (returns week plan) |
| `resolve_session` | `equipment`, `context`, `baselines`, `limitations`, `preferences`, `overrides`, `week_plans`, `body`, `assessment` | — (returns resolved session) |
| `progression_v1` | `baselines`, `assessment`, `working_loads`, `body` | `baselines`, `tests`, `working_loads` (via apply_feedback) |
| `replanner_v1` | Full user_state (passes to planner) | — (modifies plan in-place) |

All engine modules receive `user_state` as a parameter — none read it directly from disk (that happens in the API layer).
