# climb-agent — Vocabulary v1 (Canonical)

This document defines the canonical vocabulary and schema constraints for the climb-agent repository.
No new values may be introduced outside of this vocabulary without updating this document.

Last updated: 2026-02-10

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
- `pangullich`
- `spraywall`
- `board_kilter`
- `gym_boulder` *(gym has a boulder area with set problems; not board, not spraywall)*

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
- `technique_boulder`
- `technique_lead`
- `technique_footwork`

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

### 2.3 Role (phase of session)

`role` describes *where the exercise sits within a session* (phase), not what it trains.

Allowed `role` values:
- `warmup`
- `activation`
- `main`
- `accessory`
- `conditioning`
- `technique`
- `prehab`
- `cooldown`

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

- `climbing_limit_boulder`
- `climbing_intervals`
- `climbing_continuous`
- `climbing_routes`


---

### 2.5 Intensity level

`intensity_level` is a coarse control to prevent incorrect block selection (e.g., warmup selecting strength).

Allowed values:

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

## 3) Templates schema (panoramic, v1)

Templates are reusable modules. A template MUST be self-contained (i.e., it can produce a full session_instance by itself).

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
