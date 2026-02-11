# Progression v1 (deterministic working targets + test separation)

## Scope
Progression v1 defines a deterministic two-layer progression model:

1. **Official tests / baselines** (`user_state.tests`, `user_state.baselines`) = long-term capability truth.
2. **Working targets** (`user_state.working_loads.entries`) = short-term next-session prescription tuning.

Official max values are **not** rewritten by normal hard/easy session feedback.
They are updated only by explicit test sessions (`test_*`) with valid test outcomes.

## Deterministic keying (progression identity)

### Load-based
Key = `(exercise_id + setup fields)`.

Current v1 setup key for `max_hang_5s`:
- `edge_mm`
- `grip`
- `load_method`

Stored as deterministic entry fields:
- `exercise_id`
- `setup`
- `key`
- `next_external_load_kg` / `next_total_load_kg`
- `last_feedback_label`
- `updated_at`

### Grade-based
Key = `(exercise_id + surface)` where `surface` is one of:
- `board_kilter`
- `spraywall`
- `gym_boulder`

For `gym_limit_bouldering`, progression stores:
- `surface_selected`
- `last_used_grade`
- `next_target_grade`
- `last_feedback_label`
- `updated_at`

## inject_targets contract (override layering)

For each resolved exercise instance:

1. Compute deterministic baseline target from official data.
2. If a matching fresh `working_loads` entry exists (freshness window: 60 days), override with `next_*`.
3. Emit suggested payload with stable schema keys.

### `max_hang_5s`
- Baseline comes from `baselines.hangboard[0].max_total_load_kg` + `intensity_pct_of_total_load`.
- Output:
  - `schema_version: "progression_targets.v1"`
  - `suggested_total_load_kg`
  - `suggested_external_load_kg`
  - `suggested_rep_scheme`

### `gym_limit_bouldering`
- Baseline grade from performance benchmark + intensity offset rules.
- Output (`suggested_boulder_target`):
  - `schema_version: "boulder_grade_font_v0"`
  - `surface_options`
  - `surface_selected` (deterministic)
  - `target_grade`
  - `intensity_label`

## Feedback contract (canonical + legacy mapping)

Canonical field is `feedback_label` in:
- `very_easy|easy|ok|hard|very_hard`

`difficulty` / `difficulty_label` are legacy-compat only and are deterministically mapped:
- `too_easy -> very_easy`
- `easy -> easy`
- `ok -> ok`
- `hard -> hard`
- `too_hard|fail -> very_hard`
- unknown/missing -> `ok`

## apply_feedback contract

Input: `log_entry.actual.exercise_feedback_v1[]`.

### Load-based feedback
Requires either:
- `used_total_load_kg`, or
- `used_external_load_kg` (+ bodyweight for derived total).

Applies deterministic midpoint percentage from:
- `user_state.working_loads.rules.adjustment_policy[feedback_label].pct_range`

Writes matching progression entry with updated `next_*` values.

### Grade-based feedback
Requires:
- `used_grade` (Font)

Surface selection priority:
1. feedback `surface_selected`
2. planned target `surface_selected`
3. gym equipment deterministic fallback order

Grade stepper is deterministic (`very_hard -> -2`, `hard -> -1`, `ok -> 0`, `easy -> +1`, `very_easy -> +2`).

## Test boundary rule (critical)

- Normal training feedback updates **working targets only**.
- Official max/baseline updates occur only when a test session is logged and includes valid test result fields.

For `test_max_hang_5s` with `used_total_load_kg`:
- append to `user_state.tests.max_strength`
- update `user_state.baselines.hangboard[0].max_total_load_kg`

## Minimal retest trigger (v1)

`apply_feedback` tracks deterministic rolling streak counters:
- `progression_counters.max_hang_5s_hard_streak`
- `progression_counters.max_hang_5s_easy_streak`

Queue policy:
- `hard|very_hard` x2 -> enqueue `max_hang_5s_total_load` retest (recommended by +7d)
- `easy|very_easy` x2 -> enqueue optional retest (recommended by +14d)

Queued records:
- `test_id`
- `recommended_by_date`
- `reason`
- `created_at` (equal to feedback/log date, deterministic)

Deterministic dedupe policy (simple): skip enqueue for the same `test_id` if an existing queue item has `created_at` within ±21 days.

## Determinism guarantees
- stable key construction
- stable sort order for entries/queue
- no random offsets
- no wall-clock dependent branching in progression math
