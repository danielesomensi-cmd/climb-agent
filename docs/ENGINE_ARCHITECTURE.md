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
    │  writes: user_state.baselines, test results
    ▼
update_user_state_adjustments()       ← adaptation/closed_loop.py
    │  reads: per-exercise difficulty
    │  writes: user_state.adjustments.per_exercise (multiplier, streak, cooldowns)
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

Tests **replace** existing sessions (prefer complementary targets, fall back to last session on the day). Tests bypass the phase intensity cap.

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
12. **Load score:** Sum of `fatigue_cost` × 1.5, capped at 85.
13. **Force deload:** If 2+ zones are `severe`, flag the session.

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
2. `exercise_id` ascending — deterministic final tie-break

### Recency scoring (`score_exercise()`)

```python
# Exercise-level recency penalty
if ex_id in recent[-5:]  → -100
if ex_id in recent[-15:] → -25
if ex_id in recent        → -5

# Recency group penalty (B159b)
if recency_group in recent_groups → -15

# Preference bonus
if edge_mm matches → +10
if grip matches    → +5
```

### Trace output

Every selection produces a `trace` dict with counts at each stage, enabling production debugging when `TRACE_RESOLVE=true` is set.

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

## 8. Closed-Loop Adaptation (`adaptation/closed_loop.py`)

### Multiplier system

**Entry point:** `update_user_state_adjustments(user_state, exercise_id, outcome, *, exercises_by_id, feedback_date) → Dict`

Each exercise gets a per-exercise multiplier in `user_state.adjustments.per_exercise[exercise_id]`:

```python
{"multiplier": 1.025, "streak": 0, "last_update": "2026-03-25T18:30:00"}
```

**`compute_next_multiplier(multiplier, difficulty, streak, config)`:**

Default delta rules (`DEFAULT_RULES`):
```python
"too_easy":  +2.5%
"easy":      +1.0%
"ok":         0.0%
"hard":      -2.5%
"too_hard":  -5.0%
"fail":      -5.0%
```

Formula: `next = current × (1.0 + delta_pct)`, clamped to `[0.85, 1.15]`.

### Streak tracking

- Hard difficulties (`hard`, `too_hard`, `fail`) increment the streak counter.
- Easy difficulties (`too_easy`, `easy`, `ok`) reset it to 0.
- Streak is reserved for future rules (currently unused beyond tracking).

### Cooldown system

When difficulty is `fail` or `too_hard`: 2-day cooldown on the exercise's cluster.
When `hard`: 1-day cooldown.

Cooldowns are stored in `user_state.cooldowns.per_cluster[cluster_key]`:
```python
{"until_date": "2026-03-27", "reason": "difficulty:too_hard", "last_updated": "2026-03-25"}
```

The resolver checks cooldowns via `_cooldown_until_date()` and swaps to a cluster fallback or applies a 0.9 downshift.

### Multiplier application

`apply_multiplier(load_kg, multiplier, rounding_step)` → `round(load × multiplier / step) × step`.

---

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

### Adaptation multiplier structure

```python
user_state["adjustments"]["per_exercise"]["max_hang_7s"] = {
    "multiplier": 1.025,      // 0.85 – 1.15 range
    "streak": 0,               // consecutive hard-difficulty count
    "last_update": "2026-03-25T18:30:00"
}
```

### Cooldown structure

```python
user_state["cooldowns"]["per_cluster"]["finger_strength|isometric_hang|hangboard"] = {
    "until_date": "2026-03-27",
    "reason": "difficulty:too_hard",
    "last_updated": "2026-03-25"
}
```

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
  ├── cluster_utils.{cluster_key_for_exercise, parse_date}
  ├── progression_v1.inject_targets
  └── exercise_ordering.{sort_exercises_by_phase, enforce_ordering_constraints}  (lazy import)

macrocycle_v1.py
  └── assessment_v1.{_GRADE_INDEX, grade_gap}

progression_v1.py
  └── assessment_v1.{grade_index, brzycki_1rm, ...}

adaptation/closed_loop.py
  └── cluster_utils.{cluster_key_for_exercise, parse_date}

exercise_ordering.py
  └── (no engine imports — standalone)

assessment_v1.py
  └── (no engine imports — standalone)
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
| `progression_v1` | `baselines`, `assessment`, `adjustments`, `body` | `baselines`, `tests` (via apply_feedback) |
| `closed_loop.py` | `adjustments`, `cooldowns` | `adjustments.per_exercise`, `cooldowns.per_cluster` |
| `replanner_v1` | Full user_state (passes to planner) | — (modifies plan in-place) |

All engine modules receive `user_state` as a parameter — none read it directly from disk (that happens in the API layer).
