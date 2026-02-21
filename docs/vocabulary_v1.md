# climb-agent — Vocabulary v1 (Canonical)

This document defines the canonical vocabulary and schema constraints for the climb-agent repository.
No new values may be introduced outside of this vocabulary without updating this document.

Last updated: 2026-02-20

---

## 1) Core enums (closed sets)

### 1.1 Location

Canonical `location` values:

- `home`
- `gym`
- `outdoor`

Notes:
- `gym` is a generic location class. A specific gym must be provided via `context.gym_id` (see §2.3).

---

### 1.2 Equipment (canonical IDs)

Equipment IDs are **singular** and **canonical**. Do not introduce plural variants.
An exercise with no equipment requirement uses `equipment_required: []`.

Allowed `equipment` values:

- `hangboard`
- `pullup_bar`
- `band`
- `weight` *(canonical generic weight: counterweight, dumbbells, kettlebells, barbells)*
- `dumbbell` *(subtype; prefer `weight` unless strictly required)*
- `kettlebell` *(subtype; prefer `weight` unless strictly required)*
- `campus_board` *(campus board / pangullich — `pangullich` is a legacy alias that maps to this ID)*
- `foam_roller`
- `resistance_band` *(generic elastic band; distinct from `band` which is for pull-up assistance)*
- `ab_wheel`
- `bench` *(flat/incline bench for pressing and rows)*
- `barbell` *(subtype; prefer `weight` unless strictly required)*
- `rings` *(gymnastic rings)*
- `pinch_block` *(loadable pinch training block)*
- `spraywall`
- `board_kilter`
- `board_moonboard`
- `gym_boulder` *(gym has a boulder area with set problems; not board, not spraywall)*
- `gym_routes` *(gym has route walls / rope climbing terrain)*
- `cable_machine` *(cable pulley machine for antagonist and general strength work)*
- `leg_press` *(machine for lower-body pressing; useful for antagonist/conditioning)*

Rules:
- Do **not** use `"none"` as an equipment value. Use an empty list: `equipment_required: []`.
- Do **not** use `"floor"` as an equipment value (it is implicit).
- Prefer `weight` for generic loading. Use `dumbbell/kettlebell/barbell` only if the exercise truly requires that implement.
- User inventory may list subtypes; resolver may expose canonical `weight` when any subtype is present.
- User inventory MUST use these canonical IDs (no aliases in v1).

---

## 2) Exercise schema (canonical fields)

In v1, selection semantics must rely on **structured fields**, not free-form tags.

### 2.1 Role (function in the session)

`role` describes the function of an exercise within a session block.

Allowed `role` values:

- `warmup`
- `activation`
- `main`
- `accessory`
- `cooldown`
- `prehab`
- `technique`
- `conditioning`
- `test` *(assessment / benchmark exercises — e.g., critical force test, MED test)*

Notes:
- `role` can be an array if an exercise is legitimately reusable across roles (e.g., scapular control).

---

### 2.2 Domain (capacity / training goal)

`domain` describes *what is being trained*.

Allowed `domain` values (v1.1, backwards-compatible):

- `finger_strength`  *(legacy umbrella; OK to keep)*
- `finger_max_strength`
- `finger_strength_endurance`
- `finger_aerobic_endurance`
- `power`
- `power_endurance`
- `strength_general` *(antagonists + legs + general strength work)*
- `aerobic_capacity`
- `anaerobic_capacity`
- `core`
- `mobility`
- `prehab_elbow`
- `prehab_shoulder`
- `prehab_wrist`
- `contact_strength` *(rate of force development — campus board exercises)*
- `regeneration` *(ultra-easy climbing for active recovery)*
- `flexibility` *(passive and active stretching, yoga)*
- `handstand_skill` *(inversion skill and overhead stability)*
- `technique_boulder`
- `technique_lead`
- `technique_footwork`
- `technique_body_position` *(hip rotation, flagging, centre of gravity)*
- `technique_constraint` *(constraint drills — hover hands, one-hand climbing, three-limb)*
- `technique_movement` *(movement quality — slow climbing, sloth/monkey)*
- `technique_relaxation` *(breathing awareness, tension management)*
- `endurance` *(general endurance capacity — used in test protocols)*
- `climbing_routes` *(route climbing — lead routes, redpoint attempts)*

Guidelines:
- Use `domain` for the *primary adaptation* (capacity/skill), not for individual muscles.
- Use `pattern` (e.g., `push`, `squat`, `hinge`) to target “chest/shoulders/legs” without exploding the domain vocabulary.
- Technique drills (e.g., silent feet, “use both feet”, no readjust) should use:
  - `domain: technique_footwork`
  - `role: technique`
  - `pattern: technique_drill`

---
### 2.3 Gym specificity (context)

Because `gym` must become a specific gym, gym specificity is expressed in the session context, not in `location`.

Canonical context fields:

- `context.location`: `home | gym | outdoor`
- `context.gym_id`: string (required when `context.location = "gym"`)
  - examples: `"blocx"`, `"bkl"`, `"arlon"`, `"coque"` (IDs are repo-defined)

Rule:
- If `location="gym"`, `gym_id` MUST be present for downstream policies.

---

### 2.4 Pattern (movement / protocol shape)

`pattern` encodes the movement/protocol shape; used for variation control and reporting.

Allowed `pattern` values:

- `isometric_hang`
- `repeater_hang`
- `pull_vertical`
- `pull_horizontal`
- `push`
- `hinge`
- `squat`
- `carry`
- `rotation`
- `anti_extension`
- `anti_rotation`
- `anti_lateral_flexion`
- `scapular_control`
- `wrist_extension`
- `wrist_flexion`
- `forearm_pronation`
- `forearm_supination`
- `mobility_spine`
- `mobility_shoulders`
- `mobility_hips`
- `technique_drill`
- `campus_ladder` *(campus board movement patterns)*
- `handstand` *(inversions, overhead push)*
- `compression` *(pike, L-sit to pike, toes-to-bar, hanging leg raise)*
- `flexibility_passive` *(static stretching, yin yoga)*
- `flexibility_active` *(active mobility, CARs, dynamic flow)*
- `locomotion` *(cardio/locomotion patterns: jump rope, bear crawl, running)*

- `climbing_limit_boulder`
- `climbing_intervals`
- `climbing_continuous`
- `climbing_routes`


---

### 2.5 Intensity level

`intensity_level` is a coarse control to prevent incorrect block selection (e.g., warmup selecting strength).

Allowed values:

- `very_low`
- `low`
- `medium`
- `high`
- `max`

Guidelines:
- Warmup blocks MUST restrict to `<= low` (except explicitly defined activation micro-dose).
- Max hangs and limit bouldering should be `max`.

---

### 2.6 Fatigue cost

`fatigue_cost` is an integer from 0 to 10 and supports load management and multi-session interaction.

Allowed range: `0..10`

Guidelines (non-binding, recommended):
- 0–2: mobility / light warmup
- 3–5: core / accessories / prehab
- 6–8: main strength / power-endurance
- 9–10: max strength / performance

---

### 2.7 Recency group (family-level anti-repeat)

`recency_group` groups exercises into “families” for recency penalty and non-randomness.

Format:
- lowercase snake_case string
- examples:
  - `finger_max_hang`
  - `finger_repeaters`
  - `core_anti_extension`
  - `prehab_elbow_extensors`
  - `prehab_shoulder_rotator_cuff`
  - `board_limit_boulders`

Rules:
- Every exercise MUST have exactly one `recency_group`.
- Recency penalty is applied at the group level (not only exercise_id) once implemented.

---

### 2.8 Equipment requirement in exercises

Canonical exercise fields:

- `equipment_required`: array of canonical equipment IDs (may be empty; AND semantics)
- `equipment_required_any`: optional array of canonical equipment IDs (OR semantics)
- `location_allowed`: array of `home|gym|outdoor` (or omit to mean all)

Rules:
- `equipment_required` (if present) must be a subset of available equipment.
- `equipment_required_any` (if present and non-empty) requires at least one listed item to be available.
- If both are present, exercises must satisfy both constraints (`ALL` from `equipment_required` AND `ANY` from `equipment_required_any`).

---

### 2.9 Safety flags (optional but standardized)

Optional canonical fields:

- `contraindications`: array of
  - `elbow_sensitive`
  - `shoulder_sensitive`
  - `wrist_sensitive`

If present, resolver must avoid selecting these exercises when user_state indicates the corresponding sensitivity.

---

### 2.10 Load model

`load_model` describes how external load is prescribed and progressed for an exercise.

Allowed values:

- `total_load` *(body weight + added weight; e.g., max hangs, weighted pull-ups)*
- `external_load` *(only the added weight matters; e.g., dumbbell curls, wrist curls)*
- `grade_relative` *(intensity is expressed as a climbing grade; e.g., limit bouldering, route intervals)*
- `bodyweight_only` *(no external loading; e.g., hollow hold, dead bug)*
- `null` *(load model not applicable or not yet assigned)*

---

### 2.10.1 Grade prescription fields (`prescription_defaults` extensions)

When `load_model` is `grade_relative`, two optional fields in `prescription_defaults` control how the target grade is computed from the user's assessment grades.

#### `grade_ref`

Reference grade key from `user_state.assessment.grades`. If null or absent, `grade_offset` is not read by the engine.

Canonical values:

- `boulder_max_rp` — `assessment.grades.boulder_max_rp` (max boulder redpoint)
- `boulder_max_os` — `assessment.grades.boulder_max_os` (max boulder onsight)
- `lead_max_os` — `assessment.grades.lead_max_os` (max lead onsight)
- `lead_max_rp` — `assessment.grades.lead_max_rp` (max lead redpoint)

#### `grade_offset`

Integer offset from the reference grade. Range: **-6 to +1**.

Unit: whole Font/UIAA grades (no half-grades). Scale: 6a=0, 6b=1, 6c=2, 7a=3, 7b=4, 7c=5, 8a=6, ...
The "+" modifier is not an increment — 6a+ falls between 6a and 6b.

Examples:
- `lead_max_os=7c`, offset=-2 → prescribed grade: **7a**
- `boulder_max_rp=6A`, offset=-2 → prescribed grade: **5C**

Reference values (from literature):

| offset | meaning | typical exercises |
|--------|---------|-------------------|
| 0 | at limit | limit bouldering |
| -1 | one grade below | threshold, OTM |
| -2 | two grades below | 4x4, route intervals, technique drills |
| -3 | three grades below | linked circuits, moderate volume |
| -4 | four grades below | continuity, progressive ARC |
| -5 | five grades below | ARC, regeneration — trivially easy |

Semantics for boulder exercises: when `grade_relative` and the exercise uses problems/attempts, `reps` = max attempts per problem. The user may stop earlier if quality drops.

---

### 2.11 Category

`category` is a coarse grouping for UI display and reporting. It is NOT used for selection filtering.

Allowed values:

- `warmup_general`
- `warmup_specific`
- `main_strength`
- `strength_accessory`
- `power_endurance`
- `endurance`
- `core`
- `prehab`
- `mobility`
- `flexibility`
- `technique`
- `conditioning`
- `complementary`
- `test`

---

### 2.12 Focus (technique drills)

`focus` describes the primary technical focus of a technique drill exercise. Only exercises with `role: ["technique"]` use this field.

Allowed values:

- `footwork`
- `body_position`
- `movement`
- `constraint`
- `relaxation`

---

## 3) Templates schema (panoramic, v1)

Templates are reusable modules. A template MUST be self-contained (i.e., it can produce a full session_instance by itself).

### Canonical template_ids (19)

- `antagonist_prehab`
- `cooldown_stretch`
- `core_short`
- `core_standard`
- `deload_recovery`
- `finger_aerobic_endurance`
- `finger_max_strength`
- `finger_strength_endurance`
- `general_strength_accessories`
- `general_warmup`
- `gym_aerobic_endurance`
- `gym_power_bouldering`
- `gym_power_endurance`
- `gym_technique_boulder`
- `pulling_endurance`
- `pulling_strength`
- `warmup_climbing`
- `warmup_recovery`
- `warmup_strength`

---

## 4) Progression / feedback vocabulary (v1)

### 4.1 Feedback labels

Canonical `feedback_label` values:

- `very_easy`
- `easy`
- `ok`
- `hard`
- `very_hard`

These values are used by `actual.exercise_feedback_v1[]` and by progression state (`last_feedback_label`).

Legacy compatibility is deterministic and one-way (`difficulty` is legacy, `feedback_label` is canonical):
- `too_easy` -> `very_easy`
- `easy` -> `easy`
- `ok` -> `ok`
- `hard` -> `hard`
- `too_hard` -> `very_hard`
- `fail` -> `very_hard`
- legacy booleans (`too_hard=true` or `fail=true`) -> `very_hard`
- unknown/missing feedback -> `ok`

### 4.2 Grade surfaces

Canonical boulder surfaces for progression targeting:

- `board_kilter`
- `board_moonboard`
- `spraywall`
- `gym_boulder`

Used in:
- `suggested.suggested_boulder_target.surface_options[]`
- `suggested.suggested_boulder_target.surface_selected`
- progression keying for grade-based updates.

### 4.3 Test queue contract keys

When present, `user_state.test_queue[]` entries use canonical keys:

- `test_id`
- `recommended_by_date` (`YYYY-MM-DD`)
- `reason`
- `created_at` (`YYYY-MM-DD`, derived from feedback/log date; no wall-clock)

Current canonical `test_id` introduced in v1:
- `max_hang_5s_total_load`

### 3.1 Template structure

Required fields:

- `template_id`: string
- `version`: string (SemVer recommended, e.g., `1.0.0`)
- `goal_domains`: array of `domain` values (primary goals)
- `blocks`: array of blocks (see §3.2)

Optional fields:

- `required_context`: constraints on location/equipment (future hardening)
- `notes`: free text

---

### 3.2 Block structure

Required fields:

- `block_id`: string
- `role`: one canonical `role`
- `must_select`: boolean
  - `true` for `role="main"` blocks
  - `false` for purely optional blocks (e.g., extra mobility)
- `selection_mode`: one of:
  - `instruction_only` (no exercise selection; text/prescription only)
  - `select_one`
  - `select_many`
- `selection`: selection spec (see §3.3)

Optional fields:

- `count`: `{ "min": int, "max": int }` (required for `select_many`)
- `prescription_schema`: placeholder describing reps/time scheme (format only; not used for filtering)

---

### 3.3 Selection spec (Mode B + fallback)

Selection is deterministic. It must specify:

- `primary.filters`: hard constraints
- `primary.prefer`: ranking hints (not hard constraints)
- `fallbacks[]`: ordered fallback steps (each has `filters` and optional `prefer`)

Canonical filter keys (v1):

- `role`: array of roles
- `domain`: array of domains
- `pattern`: array of patterns
- `intensity_max`: one of `low|medium|high|max`
- `equipment_any`: array of equipment (hard filter: must be all present in v1)
- `location_any`: array of locations

Example (illustrative only):

```json
{
  "primary": {
    "filters": {
      "role": ["warmup"],
      "domain": ["mobility", "prehab_shoulder"],
      "intensity_max": "low",
      "location_any": ["home", "gym", "outdoor"]
    },
    "prefer": {
      "pattern": ["scapular_control"]
    }
  },
  "fallbacks": [
    {
      "filters": {
        "role": ["warmup"],
        "domain": ["mobility"],
        "intensity_max": "low"
      }
    }
  ]
}

---

## 5) Goal & Assessment vocabulary (v1)

### 5.1 Goal types

Allowed `goal_type` values:

- `lead_grade` *(implemented in v1)*
- `boulder_grade` *(future)*
- `all_round` *(future)*
- `outdoor_season` *(future)*
- `maintenance` *(future)*

### 5.2 Target styles

Allowed `target_style` values:

- `redpoint`
- `onsight`

### 5.3 Override modes

Allowed `override_mode` values:

- `null` *(no override)*
- `force_phase`
- `force_deload`

### 5.4 Self-evaluation weakness options

Allowed `self_eval` weakness values (used in `assessment.self_eval.primary_weakness` and `secondary_weakness`):

- `pump_too_early` — forearm pump limits climbing before strength does
- `cant_hold_hard_moves` — lack of max strength or power on crux moves
- `cant_read_routes` — poor route reading and beta finding
- `technique_errors` — falling due to poor body positioning or movement quality
- `fingers_give_out` — finger strength is the limiting factor
- `cant_manage_rests` — poor ability to recover on rests during routes
- `lack_power` — insufficient explosive power for dynamic moves
- `injury_prone` — frequent injuries or niggles limiting training

### 5.5 Macrocycle phases

Allowed `phase_id` values:

- `base` — Endurance Base (aerobic, volume, technique)
- `strength_power` — Strength & Power (max hang, limit boulder, general strength)
- `power_endurance` — Power Endurance (4x4, intervals, threshold)
- `performance` — Performance (limit climbing, projecting, outdoor)
- `deload` — Deload (recovery, mobility, prehab)

### 5.6 Outdoor spots

`outdoor_spots.discipline` values:
- `lead`
- `boulder`
- `both`

`outdoor_spots.typical_days` values: standard weekday keys (`mon`, `tue`, ..., `sun`).

`availability.*.location` value `"outdoor"` marks a slot as outdoor-only. The planner assigns
no sessions to outdoor slots. Outdoor days appear in the week plan with `outdoor_slot: true`.

Outdoor session logging conditions:
- `conditions.humidity`: `low | medium | high`
- `conditions.rock_condition`: `dry | damp | wet`
- `conditions.wind`: `none | light | strong`

### 5.7 Assessment profile axes

The 6 normalized axes (0-100) of the assessment radar:

- `finger_strength`
- `pulling_strength`
- `power_endurance`
- `technique`
- `endurance`
- `body_composition`
