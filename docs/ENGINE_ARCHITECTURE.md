# ENGINE_ARCHITECTURE.md — How the Engine Works

> **Last verified:** 2026-03-27 (D163)
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
- `goal.goal_type`, `goal.discipline` (lead/boulder), `goal.target_grade`, `goal.current_grade`
- `assessment_profile` — 5-axis scores (0-100)
- `user_state.trips` — for pre-trip deload windows
- `user_state.macrocycle` — when `from_phase` is set (incremental regeneration)

### What it produces
A macrocycle dict with:
- `phases[]` — ordered list of 5 phase dicts
- Each phase: `{phase_id, phase_name, start_week, end_week, duration_weeks, energy_system, domain_weights, session_pool, intensity_cap, notes}`
- `goal_snapshot`, `assessment_snapshot` — frozen copies at generation time

### Phase duration logic

**Base durations** (hardcoded, `macrocycle_v1.py:_BASE_DURATIONS`):
- Lead: `base:4, strength_power:3, power_endurance:2, performance:2, deload:1` = 12 weeks
- Boulder: `base:2, strength_power:4, power_endurance:1, performance:2, deload:1` = 10 weeks

**Weakness adjustment** (`_WEAKNESS_ADJUSTMENTS`): If the weakest axis scores < 50, the relevant phase gets +1 week and another phase gets -1 week:
```python
"power_endurance" → extend power_endurance, shrink strength_power
"endurance"       → extend base, shrink strength_power
"finger_strength" → extend strength_power, shrink base
"pulling_strength" → extend strength_power, shrink base
"technique"       → extend base, shrink performance
```

**Flex scaling:** After adjustment, the total is scaled to `total_weeks`. The flex phase absorbs the surplus/deficit (lead: `base`; boulder: `strength_power`).

**Floor enforcement:** Min 2 weeks per non-deload phase (lead), min 1 (boulder), min 1 for deload.

### from_phase="current" behavior

When regenerating from a specific phase:
1. Phases before `from_phase` are **kept verbatim** from the existing macrocycle.
2. `_compute_remaining_durations()` allocates the remaining weeks among the phases from `from_phase` onward.
3. The start week continues from where kept phases ended.

### Monday invariant

`start_date` is auto-adjusted to the previous Monday if it's not already one:
```python
if start.weekday() != 0:
    start -= timedelta(days=start.weekday())
```
This happens in both `generate_macrocycle()` and `generate_phase_week()`.

### Domain weight adjustment

`_adjust_domain_weights(base_weights, profile)` modifies the phase's base weights:
- Score < 50 → +0.05 to the relevant domain
- Score > 75 → -0.03 (min 0.02)
- Then renormalize to sum = 1.0

Axis-to-weight mapping (`macrocycle_v1.py:line ~390`):
```python
"finger_strength"  → "finger_strength"
"pulling_strength" → "pulling_strength"
"power_endurance"  → "power_endurance"
"technique"        → "technique"
"endurance"        → "volume_climbing"
```

### Session pool construction

`_build_session_pool(phase_id, discipline)` returns an ordered list: **primary** sessions (sorted alphabetically) first, then **available** sessions. The pool definitions are hardcoded in `_SESSION_POOL` (lead) and `_SESSION_POOL_BOULDER` (`macrocycle_v1.py:lines 69-208`).

### Deload and trips

- `apply_deload_week()` strips hard/max sessions, caps at 5 sessions total.
- `compute_pretrip_dates()` computes which dates in a week fall within the 5-day pre-trip window.
- `should_extend_phase()` / `should_trigger_adaptive_deload()` provide feedback-driven phase extension and emergency deload triggers.

**Cross-ref:** `DESIGN_GOAL_MACROCICLO_v1.1.md §4` for Hörst 4-3-2-1 rationale, `§8` for deload model.

---

## 4. Weekly Planner (`planner_v2.py`)

The most complex module. Generates a 7-day plan for a single macrocycle week.

**Entry point:** `generate_phase_week(*, phase_id, domain_weights, session_pool, start_date, availability, ...) → Dict`

### `_SESSION_META` — The session metadata registry

Hardcoded dict at `planner_v2.py:lines 38-72`. Maps every `session_id` to its planning properties:

| Field | Type | Meaning |
|-------|------|---------|
| `hard` | bool | Counts against `hard_cap_per_week`; subject to spacing constraints |
| `finger` | bool | Requires 48h gap from other finger sessions |
| `intensity` | str | `"low"` / `"medium"` / `"high"` / `"max"` — gated by phase cap |
| `climbing` | bool | **Hardcoded.** True = placed in Pass 1 alongside hard sessions |
| `location` | tuple | Allowed locations, e.g. `("gym",)`, `("home", "gym")` |
| `required_equipment` | list? | Equipment the session needs (e.g. `["hangboard"]`, `["gym_boulder"]`) |
| `preferred_equipment` | list? | Soft preference — defers to better-equipped days (B160d) |
| `max_per_week` | int? | Anti-repetition cap (default 1 if absent) |
| `test` | bool? | Assessment session — bypasses intensity cap in Pass 3 |
| `supplementary` | bool? | (In session JSON, not META.) Excluded from auto-planning, quick-add only |

`_SESSION_META` is the **sole source of truth** for planning flags. Session JSONs may carry their own `supplementary` flag, but the planner reads `hard`, `finger`, `climbing`, `intensity` exclusively from `_SESSION_META`.

### `_INTENSITY_TO_LOAD`

Fallback load scores for unresolved sessions (`planner_v2.py:line 77`):
```python
{"low": 20, "medium": 40, "high": 65, "max": 85}
```
Used in `_make_session_entry()` to set `estimated_load_score` before resolution.

### The multi-pass algorithm

#### PASS 1 — Primary sessions (hard + climbing)

**Day ordering:** Gym-available days first, then home-only, preserving weekday order within groups. This ensures climbing sessions (which need gym) get placed before home-only days are considered.

**Session iteration:** Round-robin through `primary_pool` with constraint checks per session × day:
1. **Anti-repetition:** `max_per_week` cap (permanent skip, burns uses).
2. **Other-activity intensity reduction:** No hard sessions on days with other sports.
3. **Pre-trip deload:** No hard/max sessions on pretrip dates.
4. **Hard day cap:** `hard_days >= effective_hard_cap` (permanent skip).
5. **Finger spacing:** 48h gap from last finger session (extended by `recovery_multiplier`).
6. **Hard spacing:** No consecutive hard/max days (extended by `recovery_multiplier`).
7. **Preferred equipment deferral (B160d):** If a session has `preferred_equipment` and this day's gym lacks it, check if a later day has it — if yes, defer.

On success: `_find_best_slot()` finds the best available slot (evening > morning > lunch for primary), `_make_session_entry()` builds the plan entry.

**B161:** Previous week's trailing sessions seed the spacing constraints (negative offsets -7 to -1).

#### PASS 1.5 — Climbing fallback

Triggers only when the pool has climbing sessions that all require `gym_routes` but the day's gym only has `gym_boulder`. Injects fallback sessions from `_CLIMBING_FALLBACKS` = `("technique_focus_gym", "easy_climbing_deload")`.

#### PASS 2 — Complementary sessions

Fills remaining empty days (up to `target_training_days_per_week`) with non-primary sessions. Slot preference is reversed: lunch > morning > evening.

#### PASS 2.2 — Extra slot filling (B121)

When total sessions < target AND a day has unused slots, places additional **non-hard** sessions in the extra slots. This handles multi-slot days (e.g., lunch + evening available).

#### PASS 2.5 — PE finger maintenance guarantee

In `power_endurance` phase: if no `finger_maintenance_*` session was placed, forcibly injects one — either replacing a complementary session or filling an empty day.

#### PASS 3 — Test session injection

Triggers on the last week of `base` or `strength_power` phase, or when `inject_tests=True`.

**Test schedule:**
1. `test_max_hang_5s` (or `test_lp_max_5s` if `finger_device == "loading_pin"`) — finger test
2. Pulling test — `test_max_weighted_pullup` or `test_pullup_bw` (B128: routed by `_pick_pulling_test_session()`)
3. `test_repeater_7_3` (or `test_lp_repeater`) — finger test, 48h gap from #1

**Freshness filter (B128):** Tests completed within `TEST_FRESHNESS_DAYS` = 42 days are skipped.

Tests bypass the phase intensity cap. Placement is **two-pass** (B297 / D211-F9):
- **Pass 1 — replace:** a test replaces an existing session (prefer complementary targets, fall back to last session on the day). This is the historical path, unchanged.
- **Pass 2 — empty-day fill (`required` only):** a `required` test that Pass 1 could not place may occupy an empty available day (adds a session, +1 weekly volume), still honoring finger/hard spacing, the hard cap, and outdoor/pre-trip exclusions. Optional tests stay replace-only.

Any test that still cannot be placed is recorded in `week_plan.skipped_tests` with `reason="no_placement_slot"` (plus `required`), instead of being silently dropped. The `/week` view surfaces the `required` ones so the user can free up a day.

### Availability normalization

`_normalize_availability()` handles 13 input cases (`planner_v2.py:lines 237-326`):
- Missing day → rest
- `day: True` → available with home fallback
- `{available: False}` → rest
- Per-slot dicts with `preferred_location`, `gym_id`, `locations`
- `preferred_location: "other_sport"` → slot unavailable

### Day scoring for cap

When available days exceed `target_training_days_per_week`, days are scored and the top N kept:
- Gym preferred: +100
- Gym available: +50
- Evening slot: +10
- Home-only: +1

### Youth cap (D81)

Users under 18: `target_days = min(target_days, 4)`.

### Recovery multiplier (D83)

`recovery_multiplier` from `planning_prefs` extends the minimum gaps between hard and finger sessions: `hard_gap_days = ceil(1 * recovery_multiplier)`.

### Homewall expansion (B137/B159)

`_expand_session_locations()` adds `"home"` to a session's locations if the user's home equipment satisfies all required equipment (e.g., homewall with `gym_boulder`).

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
   - **Explicit exercise** (`exercise_id` in block): Direct lookup, bypass P0 filters.
   - **Instruction-only** (`mode: "instruction_only"`): No exercise selection, pass through.
   - **P0 selection** (has `role`): → `pick_best_exercise_p0()` with block's `role`, `domain`, `pattern`.
7. **Cooldown fallback:** For main/primary blocks, if the selected exercise is in cooldown (via `_cooldown_until_date()`), swap to a cluster fallback or apply 0.9 multiplier downshift.
8. **Prescription merging:** `exercise.prescription_defaults` ← overridden by `block.prescription` ← overridden by `_apply_load_override()` (user per-exercise overrides).
9. **Prehab injection (B38):** `_inject_prehab_for_limitations()` auto-adds one prehab exercise per limitation zone if not already present.
10. **Progression injection:** `inject_targets()` enriches instances with suggested loads, target grades.
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
< 90 days). Otherwise `build_rotation_context()` returns `None` and every new
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
- `_SIMILARITY_GROUPS` (B90): 3 groups (push, squat, pull) for cross-exercise load transfer when baseline is missing.
- `DEFAULT_ADJUSTMENT_POLICY`: Maps feedback labels to % adjustment ranges.

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
> the proactive schedule (finger 48h hard gap, DUP spacing, hard caps) and the
> live load progression; injury spacing for fingers lives in
> `replanner_v1._enforce_finger_gap` and is untouched.
>
> A245 E-4 had earlier removed a separate multiplier system
> (`adjustments.per_exercise`, `compute_next_multiplier`, `apply_multiplier`)
> from the same module for the same reason (zero production readers).

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
**tested** athlete (persisted state, test < 90 days); `None` otherwise and the
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
(r+2)RM); hang: 3 s of reserve, phase cap) × re-entry factor
(`retest_policy.reentry_step`, tests counted via `extra_dates`) → pain
(`pain_blocks`, R4; the phase floor is cut by the same 0.90) → guards (2 heavy pulls / 7 days, same-session finger,
finger-hard day in the 2 days before) → `floor_eff = min(floor, cap_eff)` →
fatigue (3 hard / 14 days → floor). All engineering constants are labelled in
the module.

`apply_feedback` also writes the ONE exposure registry
(`progression_counters.stimulus_exposures`, read by `stimulus.exposures`), the
measured early-retest evidence (`retest_signals`, never an enqueue — labels no
longer touch `test_queue`) and the fatigue days (`hard_labels`).

### 8.2 Retest policy — who schedules a test (A289)

Only `retest_policy.retest_decisions(state, week_start, ...)` schedules tests of
a **covered** axis (finger with a hangboard, pulling; covered = a test < 90
days). `GET /api/week` computes it when it GENERATES a week (archived weeks and
outdoor rows read fail-soft) and passes it to `generate_phase_week(retest_decisions=...)`:

```
retest_decisions  → week-level: trigger (end_of_phase | end_of_phase_slipped |
                    cycle_start | maintenance | early_retest), gap by confidence
                    (28 / 42 d), phase / trip / very_hard day blockers,
                    external finger-hard + heavy-pull days, already-scheduled
planner PASS 3a   → day-level against the week's own sessions: < 72 h finger-hard
                    (hang; 3 calendar days, inclusive), never a slot the regen
                    merge refills (locked_slots / locked_dates), < 48 h heavy pull (pull-up), 48 h finger gap, hard cap;
                    paired day, hang slot before pull-up slot
planner PASS 3    → historical, only for the axes the policy does not cover
retest_status     → live on every GET: official max, confidence, trend (±5 %),
                    next test (planned with reason | projected), live blockers
```

`None` (untested athlete) leaves the planner byte-identical and `GET /api/week`
without `retest_status`. A cached week is never regenerated for the policy; the
live status flags a planned test that became too close to a hard session
instead of moving it.

---

### 8.3 Key sessions — `key_sessions_v1.py` (A294)

The single owner of "which sessions of the week carry the phase's key stimuli". **Derived at read, never persisted**: `compute_key_status(state, today, ...)` reads the week plan (hot + archived), the outdoor logs, the free sessions and the completion log, and returns a status that the API attaches as `key_status` **beside** `week_plan` (so nothing can write it back). Data: `backend/catalog/key_stimuli/v1/key_stimuli.json`.

- **Satisfied by dose, not presence.** For `finger_max` / `pulling_max` a session counts as full only when the main exercise reaches the anchored floor of the phase on that day (`anchored_load(...).floor`) with ≥ 4 sets; otherwise it is `partial` (no ✓, debt stays). Everything else counts on presence.
- **Debt** = target − full-dose days − valid future planned days, current week only (a past week's miss is lost, not carried).
- **Proposals** are validated, not guessed: the candidate goes through the replanner's own `apply_events` on a deep copy (new event `add_planned_session`, catalog session, no day+1 ripple), then the 7 days are diffed. A proposal that downshifts itself or touches a key / custom / forced / done / skipped session is dropped; any other change is shown as a side effect. The finger gap is checked on a unified timeline (plan + outdoor-hard days + free limit sessions, previous and next week), 72 h before a pending max test is off-limits, and a catch-up that would sit next to next week's key becomes `deferred_next`. Very hard feedback or an adaptive replan in the last 72 h → `deferred_fatigue`, no proposal.
- **Insertion check** (`check_insertion`): what a custom / generated session would do to the keys, behind `POST /api/replanner/events` `dry_run: true` — used by the app before adding a custom (confirm, never block) and by `scripts/athlete_context.py --simulate`.
- **Coach**: a compact `## Key sessions this week` block in the dynamic prompt (never the cached static block), and `composer_guard` drops finger-hard lines near a finger key / heavy pulls before a pull-up test from the composer pool (A259 extension).
- **Replanner additions** (additive): `apply_events(prev_days=)` + a `reconcile` adaptation with the downshifts it used to discard; `downshifted_from` stamped by every downshift; `mark_skipped` stubs keep `skipped_session_id` / `skipped_tags`.
- Known divergence: `closed_loop_v1.stimulus_recency` still classifies by session id/tags; the key status reads the A288 exposure view. Not unified in A294.

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
- `mark_done` / `mark_skipped` / `mark_planned` — status transitions
- `move_session` — relocate within the week
- `remove_session` — delete from day
- `complete_other_activity` / `add_other_activity` — non-climbing activities
- `add_outdoor` / `complete_outdoor` / `undo_outdoor` / `remove_outdoor` — outdoor sessions
- `change_gym` — equipment-aware session replacement via `_find_gym_change_replacement()`
- `set_availability` — re-plan a day with new availability

**`apply_day_add(plan, *, session_id, target_date, slot, location, phase_id, gym_id) → tuple`**

Quick-add flow: places a session in a specific slot. Used by the quick-add UI.

**`suggest_sessions(plan, target_date, location, *, session_pool, max_suggestions) → List`**

Returns up to N session suggestions for quick-add, filtered by location and equipment compatibility.

### Ripple effects

- `_enforce_caps()`: After changes, deterministic downshift removes lowest-priority sessions if hard cap is exceeded.
- `_enforce_no_consecutive_finger()`: Checks finger gap using `recovery_multiplier` from `plan.profile_snapshot` (B165b). Default gap=1 day (48h); with multiplier=1.25+ the gap increases to 2+ days. Violating sessions are deterministically downshifted to `regeneration_easy`.
- `_compensate_finger()`: If a finger session is lost, auto-injects `finger_maintenance` on a safe day. Respects recovery gap from `recovery_multiplier`.
- **Recovery ripples (B366)** — quick-add (day+1), hard day override (day+1 proportional, day+2 forced recovery) and a completed outdoor day with `outdoor_load_score ≥ 65` (day+1) ease the following days. All three go through `_apply_ripple_to_day`, which consults `_is_rewritable`: done/skipped, `forced` (A254) and `is_custom` (B345) sessions are never rewritten. The quick-add and override ripples are kept only if the session that triggered them survived `_reconcile` (`_added_session_survived`): they are tried on a copy in the historical order (ripple → [compensation] → reconcile, so an eased hard day+1 still frees a cap slot) and dropped if reconcile downshifted the triggering session. Every rewrite is reported with the `_adjustment` shape: quick-add appends it to the returned `adjustments` (reason `quick_add_ripple`); override stores it in the `day_override` adaptation's `adjustments` (reasons `recovery_ripple_proportional` / `recovery_ripple`); outdoor appends an `outdoor_ripple` adaptation (reason `outdoor_ripple`, plus `kept_protected` for the hard/finger custom/forced sessions it had to spare). Because the ripple now spares protected sessions, `_protected_neighbor_guard` runs after `_reconcile` on quick-add and override: `_enforce_no_consecutive_finger` scans forward and cannot downshift backwards, so a finger custom/forced session within `_recovery_gap` days AFTER the added session would otherwise leave both finger-hard. The guard downshifts the added session (`finger_spacing_downshift`, skipped if the user forced it); a protected hard session on day+1 only yields a warning. The override response now returns `adjustments` + `warnings` like quick-add.
- `_recovery_gap(plan)`: Helper (B165b) — reads `profile_snapshot.recovery_multiplier` and returns `ceil(1 * multiplier)`. Same formula used by the planner.

### Completed session preservation

**Immutability invariant:** `_is_preservable()` checks if a session has status `done` or `skipped`. Preservable sessions are **never** modified by regeneration.

`regenerate_preserving_completed(old_plan, new_plan, preserve_before)` and `merge_prev_week_sessions(prev_plan, new_plan, preserve_before)` enforce this by keeping completed sessions from the old plan.

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
4. Domain-based mapping (see `exercise_ordering.py:lines 108-173`)
5. Fallback: `main_unclassified`

### Phase sort order

`PHASE_SORT_ORDER` (`exercise_ordering.py:lines 180-261`) defines priority per phase. The principle: **neural/high-intensity work first, endurance/accessories last.**

Example — `strength_power` phase priority:
```
warmup(0) → activation(1) → strength_neural(2) → power(3) →
pulling(4) → finger_endurance(5) → threshold(6) → technique(7) →
aerobic(8) → core(9) → antagonist_prehab(10) → cooldown(11)
```

### 5 hard constraints (`enforce_ordering_constraints()`)

Applied **after** the phase sort. Auto-fix with logging when violated:

1. **Warmup always first** — warmup exercises before all others
2. **Cooldown always last** — cooldown exercises after all others
3. **ARC before pump** — `aerobic_pure` before `threshold`/`pe_intervals`
4. **Max hangs before pulling** — `strength_neural` before `pulling_supplementary`
5. **Accessories after main** — `core`/`antagonist_prehab` after all main work categories

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
- **Tests:** `test_max_hang_5s`, `test_lp_max_5s`, `test_repeater_7_3`, `test_lp_repeater`, `test_max_weighted_pullup`, `test_pullup_bw`
- **Deload:** `deload_recovery`

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

retest_policy.py                      (A288 — official_max / test_confidence / reentry_step;
                                       A289 — retest_decisions / retest_status)
  ├── stimulus.{exposure_dates, count_exposures, session_flag, ...}
  └── progression_v1.estimate_1rm_from_2rm  (lazy import)
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
