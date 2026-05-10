# climb-agent — Vocabulary v1 (Canonical)

This document defines the canonical vocabulary and schema constraints for the climb-agent repository.
No new values may be introduced outside of this vocabulary without updating this document.

Last updated: 2026-03-28

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

- `hangboard` *(generic hangboard — any edge depth; A193: implies `pullup_bar` — a hangboard is always mounted on a bar)*
- `hangboard_20mm` *(20mm edge variant used for standardised testing; subset of hangboard; A193: implies `pullup_bar`)*
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
- `board_other` *(any training board not specifically Kilter or MoonBoard — Tension, Grasshopper, custom, etc.)*
- `homewall` *(home climbing wall — any size or board type; implies `gym_boulder` capability at home)*
- `gym_boulder` *(gym has a boulder area with set problems; not board, not spraywall)*
- `gym_routes` *(gym has route walls / rope climbing terrain)*
- `cable_machine` *(cable pulley machine for antagonist and general strength work)*
- `leg_press` *(machine for lower-body pressing; useful for antagonist/conditioning)*
- `loading_pin` *(alternative to hangboard for finger strength training; unilateral (one hand at a time); treated as hangboard alias in v1)*

Rules:
- Do **not** use `"none"` as an equipment value. Use an empty list: `equipment_required: []`.
- Do **not** use `"floor"` as an equipment value (it is implicit).
- Prefer `weight` for generic loading. Use `dumbbell/kettlebell/barbell` only if the exercise truly requires that implement.
- User inventory may list subtypes; resolver may expose canonical `weight` when any subtype is present.
- User inventory MUST use these canonical IDs (no aliases in v1).

---

### 1.3 Finger training device

Allowed `finger_training_device` values:
- `hangboard` (default)
- `loading_pin`

When `loading_pin` is selected:
- Resolver selects `lp_*` exercises instead of hangboard equivalents
- Test scheduling uses `lp_max_test_5s` instead of `max_hang_7s_total_load` (D85: was max_hang_5s_total_load)
- Repeater test uses `lp_repeater_test` (test_lp_repeater session) instead of `repeater_hang_7_3`
- Duration test uses `lp_duration_test` instead of `test_max_hang_duration_20mm`
- Baselines use `baselines.loading_pin` (per-hand)

### 1.4 Boulder grade display system

Allowed `grade_system_boulder` values:
- `font` (default) — Fontainebleau scale (6A, 7B, 8A+)
- `v_scale` — Hueco/V-scale (V4, V8, V11)

Engine always stores grades in Fontainebleau. This preference is render-only — the frontend converts at display time via `displayBoulderGrade()`.

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
- `recovery` *(active recovery exercises — regeneration climbing, light mobility)*

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
- `prehab_finger`
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
- `lock_off_endurance` *(lock-off hold capacity — typewriter, one-arm lock-off)*
- `strength_pulling` *(general pulling strength — rows, pull-up variations)*

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
- `lunge` *(unilateral lunge patterns: reverse lunge, forward lunge, split stance)*
- `calf_raise` *(calf raise patterns: single-leg, bilateral, weighted)*
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
- `mobility_shoulders`
- `mobility_flow` *(dynamic mobility sequences)*
- `technique_drill`
- `campus_ladder` *(campus board movement patterns)*
- `isometric_explosive` *(overcoming isometric pulls — max force against fixed resistance; hangboard fallback for campus)*
- `explosive_brief` *(very short explosive pulls targeting RFD; hangboard fallback for campus)*
- `explosive_touch` *(explosive deadpoint/power slap drills on boulder wall)*
- `handstand` *(inversions, overhead push)*
- `compression` *(pike, L-sit to pike, toes-to-bar, hanging leg raise)*
- `flexibility_passive` *(static stretching, yin yoga)*
- `flexibility_active` *(active mobility, CARs, dynamic flow)*
- `locomotion` *(cardio/locomotion patterns: jump rope, bear crawl, running)*
- `elbow_flexion` *(bicep curl / elbow flexion isolation)*
- `shoulder_isolation` *(lateral raise / medial deltoid isolation)*
- `hip_isolation` *(hip abduction/adduction isolation work)*

- `finger_extension` *(finger extensor isolation)*
- `isometric_hold` *(static hold — hollow, plank, L-sit)*
- `isometric_lift` *(static lift — loading pin)*
- `repeater_lift` *(repeater protocol on loading pin)*
- `self_massage` *(foam rolling, lacrosse ball)*
- `static_stretch` *(passive static stretching)*
- `tendon_glide` *(finger tendon glide exercises)*

- `climbing_limit_boulder`
- `climbing_intervals`
- `climbing_continuous`
- `climbing_routes`
- `grip_transition` *(hangboard grip transition protocols)*


---

### 2.5 Intensity level

`intensity_level` is a coarse control to prevent incorrect block selection (e.g., warmup selecting strength).

Allowed values:

- `very_low`
- `low`
- `medium`
- `high`
- `very_high`
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
  - `hip_abduction`
  - `hip_adduction`
  - `hip_flexor`
  - `push_horizontal`
  - `push_tricep`
  - `squat_lateral`
  - `hip_rotation`

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

### 2.9 Safety flags and limitation system

#### 2.9.1 Exercise contraindications

`contraindications`: array of canonical values:
- `elbow_sensitive`
- `elbow_injury` *(acute elbow injury — stricter than sensitive)*
- `finger_sensitive`
- `finger_injury` *(acute finger injury — stricter than sensitive)*
- `shoulder_sensitive`
- `wrist_sensitive`
- `knee_injury` *(knee injury — excludes impact/jump exercises)*

Zone-to-contraindication mapping: `elbow` -> `elbow_sensitive`, `finger` -> `finger_sensitive`, `shoulder` -> `shoulder_sensitive`, `wrist` -> `wrist_sensitive`. Injury variants (`*_injury`) map from `severity: severe` limitations.

Note: `knee`, `back`, and `other` are valid limitation zones (tracked in user state). `knee` maps to `knee_injury` when severe; `back` and `other` have no contraindication mapping — they are informational only.

#### 2.9.2 Limitation severity levels

- `monitor` -- warning only + auto-inject prehab for that zone
- `active` -- substitute with non-contraindicated variant if available, else reduce load (-20% multiplier) + prehab
- `severe` -- exclude all contraindicated exercises, replace with zone-specific prehab; if 2+ zones are `severe` simultaneously, flag force-deload

#### 2.9.3 Hangboard experience gate (D35)

Users with `assessment.experience.climbing_years < 2` are blocked from advanced hangboard training exercises: `max_hang_5s`, `max_hang_7s`, `max_hang_10s`, `max_hang_ladder`, `min_edge_hang`, `one_arm_hang_assisted`. The resolver automatically substitutes with lower-level protocols (repeaters, density hangs). Test sessions (`test_max_hang_*`) are NEVER blocked — tests are single measurements, not training load. Gate implemented as Stage 2e in P0 pipeline (`resolve_session.py`).

Severity migration from legacy values: `mild` / `lieve` -> `monitor`, `moderate` / `moderato` -> `active`, `severe` -> `severe`.

#### 2.9.3 Limitation schema (user_state.limitations)

Current format (dict with `active_flags` + `details`):

```json
{
  "limitations": {
    "active_flags": ["elbow_left"],
    "details": [
      {
        "area": "elbow",
        "side": "left",
        "severity": "active",
        "notes": "Optional free text",
        "updated_at": "2026-03-01"
      }
    ]
  }
}
```

Also accepted: list-of-dicts format with `zone`/`severity` keys, or legacy list-of-strings (e.g. `["elbow_sensitive"]`, migrated to `active` severity).

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
- `boulder_max_rp=6A`, offset=-2 → prescribed grade: **5B**

Reference values (from literature):

| offset | meaning | typical exercises |
|--------|---------|-------------------|
| 0 | at limit | limit bouldering |
| -1 | one grade below | threshold, OTM, route intervals |
| -2 | two grades below | 4x4, technique drills |
| -3 | three grades below | linked circuits, moderate volume |
| -4 | four grades below | continuity, progressive ARC |
| -5 | five grades below | ARC, regeneration — trivially easy |

Semantics for boulder exercises: when `grade_relative` and the exercise uses problems/attempts, `reps` = max attempts per problem. The user may stop earlier if quality drops.

---

### 2.10.2 Working loads schema and feedback fields

The engine stores per-exercise progression state in `user_state.working_loads`.

#### `working_loads.entries[]` schema

Each entry tracks the last feedback and next suggested load for one exercise (optionally scoped by setup):

```json
{
  "exercise_id": "barbell_row",
  "key": "barbell_row",
  "setup": {},
  "last_completed": true,
  "last_feedback_label": "easy",
  "last_external_load_kg": 25.0,
  "next_external_load_kg": 27.0,
  "updated_at": "2026-01-05"
}
```

For `total_load` exercises (hangboard, weighted_pullup), entries also include `last_total_load_kg` and `next_total_load_kg`.

#### `working_loads.rules.adjustment_policy`

Default values (used when user has no custom policy):

| label | pct_range | midpoint |
|-------|-----------|----------|
| very_easy | [0.10, 0.20] | +15% |
| easy | [0.05, 0.10] | +7.5% |
| ok | [0.00, 0.05] | +2.5% |
| hard | [-0.05, 0.00] | -2.5% |
| very_hard | [-0.15, -0.05] | -10% |

#### `baselines.hangboard[]`

Shared baseline for all hangboard exercises:

```json
{
  "max_total_load_kg": 102.0,
  "edge_mm": 20,
  "grip": "half_crimp",
  "hang_seconds": 5,
  "load_method": "added_weight"
}
```

#### `baselines.pulling`

Shared baseline for pulling exercises (B121). Created from `assessment.tests.weighted_pullup_1rm_total_kg`:

```json
{
  "weighted_pullup_1rm_total_kg": 130.0,
  "bodyweight_kg": 77.0,
  "max_external_load_kg": 53.0,
  "source": "assessment",
  "updated_at": "2026-03-13"
}
```

Fields:
- `weighted_pullup_1rm_total_kg` — from `assessment.tests.weighted_pullup_1rm_total_kg`
- `bodyweight_kg` — from `bodyweight_kg`
- `max_external_load_kg` — derived: `1rm_total - bodyweight`
- `source` — `"assessment"` (estimated), `"test_session"` (from explicit test feedback)
- `updated_at` — ISO date

Affects:
- `weighted_pullup` (total_load): phase × intensity → % of 1RM
- `barbell_row` (external_load): `max_external_load_kg × 0.60`
- `face_pull` (external_load): `max_external_load_kg × 0.15`

#### Suggestion fields per load_model

| load_model | suggested fields | source |
|------------|-----------------|--------|
| `total_load` | `suggested_total_load_kg`, `suggested_external_load_kg`, `suggested_rep_scheme` | baselines.hangboard / baselines.pulling → working_loads |
| `external_load` | `suggested_external_load_kg`, `suggested_rep_scheme` | working_loads → transfer → baselines.pulling → BW% fallback |
| `grade_relative` | `suggested_grade`, `grade_ref`, `grade_offset` | assessment.grades + prescription_defaults |
| `grade_relative` (limit_bouldering) | `suggested_boulder_target` (with surface) | special surface-aware logic |
| `bodyweight_only` | — | no suggestion needed |

#### Feedback fields required per load_model (UI-24)

When submitting `exercise_feedback_v1`, the frontend must include load/grade data for the engine to update working_loads:

| load_model | required feedback fields | notes |
|------------|------------------------|-------|
| `total_load` | `used_total_load_kg` **or** `used_external_load_kg` | engine derives the other from bodyweight |
| `external_load` | `used_external_load_kg` | — |
| `grade_relative` (limit_bouldering) | `used_grade`, `surface_selected` | — |
| `bodyweight_only` | — | feedback_label only |

If these fields are missing, `apply_feedback` does a silent skip (no crash, no update).

---

### 2.10.3 Test source taxonomy (`assessment.tests_source`)

Every scalar in `assessment.tests.*` has a companion entry in `assessment.tests_source` recording whether the value came from a real measurement or an estimate. The sidecar shape is parallel to `assessment.tests`: same keys, one of two string values.

Allowed values:

- `measured` — scalar came from a real test (in-app test session, or user-entered value at onboarding).
- `estimated` — scalar was derived from a grade table, pullup 1RM conversion, or another proxy. Also the silent default when the key is absent.

Default policy: readers MUST treat missing keys as `estimated`. No migration is run — legacy state without `assessment.tests_source` behaves exactly as if every key were `estimated`. Writers only mark the specific key they touch; unrelated keys are left alone.

Example state blob:

```json
"assessment": {
  "tests": {
    "max_hang_20mm_7s_total_kg": 150.0,
    "max_hang_20mm_5s_total_kg": 150.0,
    "repeater_7_3_max_sets_20mm": 20
  },
  "tests_source": {
    "max_hang_20mm_7s_total_kg": "measured",
    "max_hang_20mm_5s_total_kg": "measured",
    "repeater_7_3_max_sets_20mm": "measured"
  }
}
```

Writer sites:

- `onboarding.py::_build_tests_source` — marks every user-entered scalar at onboarding; dual-writes the 7s/5s hang sibling (they share a single input in the form).
- `progression_v1.py::_update_test_from_log` — every branch that writes a scalar to `assessment.tests` calls `_mark_measured(key, ...)` alongside it.

Reader sites that gate on source:

- `progression_v1.py::_estimate_hangboard_baseline` Priority 0 — if `tests_source["max_hang_20mm_7s_total_kg"] == "measured"`, use the scalar as baseline directly (stamping `source="test"` + `updated_at`). Otherwise fall back to grade / pullup estimate (writing `source="estimated_from_*"` + `estimated_at`).
- `week.py::get_week` freshness map — `_recent_test_dates` is populated for finger / repeater / pulling axes only when the corresponding `tests_source` entry is `"measured"`. Estimated scalars never suppress legitimate retests.

Reader sites intentionally source-agnostic:

- `assessment_v1.compute_assessment_profile` (all 5 axes) — radar math stays source-blind. An estimated scalar is better than `None` for UI.
- `resolve_session.suggest_max_hang_load` fallback — builds a baseline-shaped dict when `baselines.hangboard` is empty. Gating would downgrade UX (no suggestion at all); keep source-blind.
- `planner_v2._pick_pulling_test_session` — uses `max_pullups_bw` presence as a routing signal (BW vs weighted pull-up), not a freshness signal.

Origin: D214 / D-TESTUSER-VERIFY §5 (F1 + F3 closure).

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
- `test_measurement` *(specific measurement/benchmark exercises within test sessions)*

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

### 2.13 Unilateral flag

`unilateral`: boolean. When true, the exercise is performed one limb at a time.
The resolver must prescribe sets for each hand separately.
Working loads and baselines are tracked per-hand when unilateral is true.

Currently used by: loading pin exercises (`lp_*`).

---

## 3) Templates schema (panoramic, v1)

Session templates define complete training sessions. Module templates define reusable blocks within sessions.

Verify with: `python _archive/scripts/audit_templates.py`

### 3.0 Canonical session template_ids (35)

Sessions live in `backend/catalog/sessions/v1/`. Each produces a full resolved session.

- `boulder_circuit_gym` *(volume_climbing, gym)*
- `complementary_conditioning` *(strength_general, home)*
- `core_training` *(core, home)*
- `deload_recovery` *(home)*
- `easy_climbing_deload` *(gym — light climbing for deload weeks)*
- `endurance_aerobic_gym` *(aerobic_capacity, gym)*
- `finger_aerobic_base` *(home)*
- `finger_endurance_short` *(home)*
- `finger_maintenance_gym` *(finger_strength_endurance, gym)*
- `finger_maintenance_home` *(finger_strength_endurance, home)*
- `finger_strength_home` *(finger_max_strength, home)*
- `flexibility_full` *(flexibility, home)*
- `handstand_practice` *(handstand_skill, home)*
- `heavy_conditioning_gym` *(strength_general, gym)*
- `legs_strength` *(strength_general, home)*
- `limit_boulder_gym` *(limit_projecting, gym)*
- `lower_body_gym` *(strength_general, gym)*
- `power_contact_gym` *(contact_strength, gym)*
- `power_endurance_gym` *(power_endurance, gym)*
- `prehab_maintenance` *(prehab_shoulder, home)*
- `pulling_strength_gym` *(pulling_strength, gym)*
- `regeneration_easy` *(regeneration, gym)*
- `route_endurance_gym` *(aerobic_capacity, gym)*
- `route_projecting_gym` *(route_projecting, gym)*
- `strength_long` *(finger_max_strength, gym)*
- `technique_focus_gym` *(technique_footwork, gym)*
- `test_lp_max_5s` *(finger_max_strength, test)*
- `test_lp_repeater` *(finger_strength_endurance, test)*
- `test_max_hang_5s` *(finger_max_strength, test — legacy 5s)*
- `test_max_hang_7s` *(finger_max_strength, test — MVC-7, D85)*
- `test_max_weighted_pullup` *(pulling_strength, test)*
- `test_pullup_bw` *(pulling_strength, test)*
- `test_repeater_7_3` *(finger_strength_endurance, test)*
- `upper_body_weights` *(strength_general, home)*
- `yoga_recovery` *(flexibility, home)*

#### Session-level optional fields

- `boulder_fallback`: `string | null` (default `null`). Session_id of a boulder-discipline equivalent session, used when the user triggers the ephemeral "Boulder only" override (A210) on a rope-dependent session. Allowed values: any valid session_id in the boulder pool, or `null`. Only non-null for sessions whose core block requires `gym_routes` (currently: `endurance_aerobic_gym` → `boulder_circuit_gym`, `route_endurance_gym` → `boulder_circuit_gym`, `route_projecting_gym` → `limit_boulder_gym`).

### Canonical module template_ids (27)

Module templates live in `backend/catalog/templates/v1/`. These are reusable blocks composed into session templates.

- `antagonist_prehab`
- `cooldown_stretch`
- `core_short`
- `core_standard`
- `deload_recovery`
- `finger_aerobic_endurance`
- `finger_max_strength`
- `finger_max_strength_test`
- `finger_max_strength_test_lp`
- `finger_strength_endurance`
- `finger_strength_endurance_test`
- `finger_strength_endurance_test_lp`
- `general_strength_accessories`
- `general_warmup`
- `gym_aerobic_endurance`
- `gym_power_bouldering`
- `gym_power_endurance`
- `gym_technique_boulder`
- `pulling_endurance`
- `pulling_strength`
- `pulling_strength_compound`
- `route_projecting_main`
- `pulling_strength_test`
- `pulling_strength_test_bw`
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
- `board_other`
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

Current canonical `test_id` values:
- `max_hang_7s_total_load` (D85: was `max_hang_5s_total_load`)
- `weighted_pullup_2rm` (D84: was `weighted_pullup_1rm`)
- `max_pullups_bw` (D84b: bodyweight pull-up gate test)
- `repeater_7_3_max_sets_20mm`
- `lp_max_lift_5s`
- `lp_repeater_7_3`

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

- `lead_grade` — discipline = lead
- `boulder_grade` — discipline = boulder (10-week macrocycle, boulder session pool)
- `all_round` — discipline = both (lead durations + merged lead/boulder session pool, DD-B3)
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

**Universal (all disciplines):**

- `fingers_give_out` — finger strength is the limiting factor *(maps to finger_strength axis, -15/-8)*
- `cant_hold_hard_moves` — lack of max strength or power on crux moves *(maps to pulling_strength axis, -10/-5)*
- `technique_errors` — falling due to poor body positioning or movement quality *(maps to technique axis, -10/-5)*
- `lack_power` — insufficient explosive power for dynamic moves *(not mapped to axis in v1)*
- `injury_prone` — frequent injuries or niggles limiting training *(not mapped to axis in v1)*

**Lead-only:**

- `pump_too_early` — forearm pump limits climbing before strength does *(maps to power_endurance axis, -8/-4 weighted; endurance axis, -10/-5)*
- `cant_read_routes` — poor route reading and beta finding *(maps to technique axis, -10/-5)*
- `cant_manage_rests` — poor ability to recover on rests during routes *(maps to endurance axis, -10/-5)*

**Boulder-only:**

- `poor_body_tension` — can't maintain tension on steep terrain, feet cut *(maps to technique axis, -10/-5)*
- `poor_dynamic_movement` — can't execute coordination/dynamic moves *(maps to power_endurance axis, -8/-4 weighted; technique axis, -10/-5)*
- `weak_on_slopers` — struggle on rounded/open-hand holds *(maps to finger_strength axis, -15/-8)*
- `poor_problem_reading` — can't read sequences or find beta efficiently *(maps to technique axis, -10/-5)*

**Discipline scope:** Universal options apply to all disciplines. Lead-only options shown for lead and both. Boulder-only options shown for boulder and both. `Both` discipline shows all options.

### 5.5 Macrocycle phases

Allowed `phase_id` values:

- `base` — Endurance Base (aerobic, volume, technique)
- `strength_power` — Strength & Power (max hang, limit boulder, general strength)
- `power_endurance` — Power Endurance (4x4, intervals, threshold)
- `performance` — Performance (limit climbing, projecting, outdoor)
- `deload` — Deload (recovery, mobility, prehab)

### 5.5.1 Macrocycle invariants

- `macrocycle.start_date` **MUST be a Monday** (ISO weekday 0). Enforced by `ensure_monday()` in all setters (onboarding, macrocycle generate, state PUT, start-week shift). Non-Monday values are auto-corrected to the previous Monday.
- `macrocycle.total_weeks` is bounded by `[_MIN_TOTAL_WEEKS_*, _MAX_TOTAL_WEEKS]` per discipline: lead = `[11, 16]`, boulder = `[8, 16]`, both/all_round alias to lead. The 16-week cap is intentional (A218 / KB consensus 2026-05-07 — Hörst dose-response + Lattice + Consuegra). Longer training horizons require multiple sequential macrocycles, started manually via `POST /api/macrocycle/start-new-cycle`. Block-stacking is **not** automatic in v1.
- Per-phase weeks respect floor/cap inequalities defined in `_PHASE_FLOORS_*` / `_PHASE_CAPS_*` (`backend/engine/macrocycle_v1.py`). Lead `base` is locked at 4 (floor==cap). The weakness adjustment can shift ±1 between two phases only when both endpoints respect the floor/cap of the new shape; otherwise it's a clean no-op.

### 5.5.2 Macrocycle history (A-NEW-MACRO)

`state.macrocycle_history` is an append-only list populated by `POST /api/macrocycle/start-new-cycle`. Each entry is a snapshot taken at the moment the previous macrocycle was retired:

```json
{
  "archived_at": "2026-05-05T15:30:00+00:00",
  "macrocycle": { "...full snapshot of state.macrocycle..." },
  "goal_at_archive": { "...snapshot of state.goal at archive time..." },
  "weeks_completed": 11,
  "total_weeks": 12,
  "completion_summary": {
    "sessions_done": 47,
    "sessions_skipped": 8,
    "sessions_planned": 60,
    "tests_completed": [{"session_id": "test_max_hang_7s", "date": "2026-02-05"}],
    "phases_completed": ["base", "strength_power", "power_endurance", "performance", "deload"]
  }
}
```

Invariants:

- Append-only from the caller's perspective. The helper `archive_current_macrocycle(state)` is NOT idempotent — calling it twice writes two entries. The endpoint guards against this by mutating a deep-copy and committing once.
- `goal_at_archive` may differ from `macrocycle.goal_snapshot`: the snapshot is taken at *generation* time; `goal_at_archive` at *archive* time (after any goal edits made mid-cycle without regenerating).
- `target_grade` is auto-remapped via `BOULDER_TO_LEAD` / `LEAD_TO_BOULDER` (highest-boulder-per-lead) whenever `goal.discipline` flips via `PUT /api/state` or via `POST /api/macrocycle/start-new-cycle`. The mapping module is `backend.engine.grade_mapping`.
- Storage cost: ~5 KB per archived cycle (~20 KB/year). No size cap in v1.

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

### 5.7 Weekly overrides

```
weekly_overrides: dict[str, WeekOverride]
  Key: week start_date as ISO string (always a Monday)
  Value: { days: dict[weekday_long, DayOverride], created_at: ISO datetime }

DayOverride: { available: bool, location: "gym"|"outdoor"|"home"|"rest", gym_id?: string }
  Only days that differ from settings defaults are stored.
  Missing days in override = use settings defaults.
  Weekday keys use full names: monday, tuesday, ..., sunday.
```

The override is a **temporary layer** — it never modifies `state.availability`.
The planner merges the override into availability before planning (in `week.py`).
Past-week overrides are kept for history but are never read by the planner.

---

### 5.8 Exercise sort category (A121)

Derived at resolution time from `role`, `domain`, and `pattern` fields — NOT stored in exercise JSON.
Used to reorder exercises within a resolved session based on macrocycle phase.

14 values:
- `warmup` — general/specific warm-up
- `activation` — scapular, rotator cuff activation
- `aerobic_pure` — ARC, continuous climbing, regeneration
- `threshold` — threshold climbing, route volume
- `strength_neural` — max hangs, contact strength, finger max strength
- `power` — limit bouldering, explosive pulling
- `pe_intervals` — 4×4, linked boulders, route intervals
- `finger_endurance` — repeaters, density hangs, Lopez subhangs
- `pulling_supplementary` — weighted pull-ups, rows, lock-offs
- `technique` — drills (footwork, body position, constraints)
- `core` — hollow hold, L-sit, front lever, handstand
- `antagonist_prehab` — push exercises, prehab (elbow/finger/shoulder/wrist)
- `cooldown` — stretching, flexibility, mobility
- `main_unclassified` — fallback (priority 6), never discarded

Sort order varies by phase. See `backend/engine/exercise_ordering.py:PHASE_SORT_ORDER`.

---

### 5.9 Assessment profile axes

The 5 normalized axes (0-100) of the assessment radar:

- `finger_strength`
- `pulling_strength`
- `power_endurance`
- `technique`
- `endurance`

---

## 6) Free Climbing Session vocabulary (A136)

### 6.1 Free session context

`context` describes the relationship of the free session to the planned training day.

Allowed values:
- `standalone` — rest day or no planned session
- `add_on` — after a completed planned session
- `replacement` — replaces a planned session (marks it as skipped)

### 6.2 Free session mode

`session_mode` describes whether the user follows a template or climbs freely.

Allowed values:
- `template` — user selected a preset (grade target, rest, climb count)
- `free` — no structure, only phase tip
- `circuit` — timer-guided exercise circuit

### 6.3 Climb status (boulder)

`climb_status` describes the outcome of a single boulder problem.

Allowed values:
- `flash` — sent first try (attempts must be 1)
- `sent` — sent after multiple tries (attempts must be >= 2)
- `attempted` — not sent (attempts must be >= 1)

### 6.4 Climb style (lead only)

`climb_style` describes the style of a route attempt. Only used when `surface == "gym_routes"`.

Allowed values:
- `onsight` — first attempt, no beta
- `flash` — first attempt, with beta
- `redpoint` — sent after previous attempts
- `project` — working a route, not yet sent
- `repeat` — re-climbing a previously sent route

### 6.5 Free session surfaces

Allowed `surface` values for free climbing sessions:

- `gym_boulder` — gym boulder area
- `board_kilter` — Kilter Board
- `board_moonboard` — MoonBoard
- `board_other` — other training board (Tension, Grasshopper, custom)
- `gym_routes` — lead / top-rope routes

Note: all surfaces are always available (no equipment filter).

### 6.6 Overall feel

`overall_feel` describes the user's subjective feeling after the session.

Allowed values:
- `easy`
- `good`
- `hard`

### 6.7 Free session preset IDs

Boulder presets:
- `free_volume` — high volume, moderate grade
- `free_projecting` — few climbs at limit grade
- `free_endurance` — many easy boulders, short rest
- `free_technique` — easy problems, focus on footwork

Lead presets:
- `free_lead_volume` — many routes at moderate grade
- `free_lead_projecting` — 1-2 routes at limit
- `free_lead_endurance` — long easy routes, short rest

### 6.8 Phase compatibility

Preset phase compatibility values:
- `recommended` — good match for current phase
- `caution` — can do, but be mindful
- `not_recommended` — avoid in this phase

### 6.9 Circuit surfaces

Allowed `surface` values for circuit sessions:

- `circuit_core` — bodyweight core circuit

Future (not in v1):
- `circuit_warmup` — dynamic warmup circuit
- `circuit_stretching` — post-session stretching circuit
- `circuit_cardio` — bodyweight cardio circuit

### 6.10 Session mode (updated)

Allowed `session_mode` values:
- `template` — user selected a preset
- `free` — no structure, only phase tip
- `circuit` — timer-guided exercise circuit
- `custom_build` — user-assembled strength session (custom builder A206 or body-part picker A213). Rendered via the same custom-session path; distinguished by `build_kind`.

### 6.11 Build kind (custom_build discriminator)

When `session_mode == "custom_build"`, the `build_kind` field identifies how the session was assembled:

- `manual` — custom session built via A206 Session Builder (user picks exercises directly)
- `body_parts` — session generated by A213 Body Part Picker (user picks body parts, engine picks exercises)

Both variants share `is_custom=true` and the same rendering path; only closed-loop progression differs (`body_parts` bypasses `apply_day_result_to_user_state` to keep ad-hoc strength days out of long-term planning).

### 6.12 Body part categories

Allowed `body_part` IDs for Body Part Picker (A213):

- `fingers` — hangboard-based finger strength
- `forearms` — wrist/forearm conditioning (excludes fingers)
- `biceps` — arm flexion work (excludes forearms)
- `triceps` — arm extension work
- `shoulders` — shoulder stability and pressing
- `back_pulling` — back and pulling strength
- `chest` — horizontal pushing
- `core` — abdominal and trunk stability
- `legs` — quads, hamstrings, calves
- `glutes` — posterior chain isolation
- `hips` — hip mobility and isolation (abduction/adduction/flexor/rotation)

### 6.13 Body Part Picker equipment modes

Allowed `equipment_mode` values for `/api/body-part-picker/*`:

- `bodyweight` — no equipment at all
- `home` — expands from `state.equipment.home` (implies `weight` when loose weights are present)
- `gym` — expands from a specific gym's equipment list (requires `gym_id`)
- `all` — union of all known equipment keys (used for default UI counts before the user picks)
