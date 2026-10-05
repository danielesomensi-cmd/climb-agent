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
- **Location vs equipment (D1, A225).** The project rule "filter by `required_equipment`, not by `location_type`" governs **session/exercise filtering** — never gate a trainable session on where you are; gate it on the gear available. **Outdoor-day _detection_ is a deliberate, documented exception**: an outdoor day is identified by `availability.*.location == "outdoor"` (see §5.6), because "outdoor" is a venue with no indoor-equipment profile to filter on, not a session that competes for equipment. The planner therefore reads the outdoor flag to *exclude* the day from indoor session assignment (`planner_v2` `day_is_outdoor`), and does **not** apply equipment filtering to it. This is context-based by design and required **no `planner_v2` change** in A225.

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
- `treadmill` *(C274: gym treadmill for Zone 2 and interval cardio; required by the lunch cardio sessions `treadmill_hiit_4x4` and `treadmill_zone2_cardio`)*
- `loading_pin` *(alternative to hangboard for finger strength training; unilateral (one hand at a time); treated as hangboard alias in v1)*

Rules:
- Do **not** use `"none"` as an equipment value. Use an empty list: `equipment_required: []`.
- Do **not** use `"floor"` as an equipment value (it is implicit).
- Prefer `weight` for generic loading. Use `dumbbell/kettlebell/barbell` only if the exercise truly requires that implement.
- User inventory may list subtypes; resolver may expose canonical `weight` when any subtype is present.
- User inventory MUST use these canonical IDs (no aliases in v1).

---

### 1.2b Axis provenance (`assessment.profile_source`, A269)

Records, per assessment axis, **what the score was derived from** — not how good it is.

Allowed values:

- `measured` — every input to the axis comes from a test recorded as `measured` in
  `assessment.tests_source`.
- `partial` — at least one measured input, plus derived (grade-based) or self-reported terms.
- `estimated` — no measured input at all; the axis is inferred from declared grades, tenure and
  self-evaluation.

Rules:

- **A missing key means `estimated`.** Same convention as `assessment.tests_source` (D214): a reader
  must never be able to interpret silence as a measurement.
- Provenance is derived from `tests_source`, **never** from the presence of a value in
  `assessment.tests` — an onboarding estimate is present but not measured.
- `technique` is always `estimated`: no test feeds it.
- A loading-pin finger number is `measured` even though it is converted (`LP_ONE_ARM_TO_TWO_HAND`,
  A266); `tests_source` still records which key was the origin.

`assessment.profile_scoring_version` names the rules that produced the profile — `profile_v1` today.
It is never applied retroactively: a stored profile keeps its version and its numbers, and a new
version takes effect from the next assessment or the next explicit regeneration.

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
- `ladder` *(C272 — a level of a bodyweight ladder in `backend/catalog/progressions/v1/bw_ladders.json`; library-only)*
- `library` *(C272 — technique / positioning / try-hard / pocket drill or protocol; library-only)*

Notes:
- `role` can be an array if an exercise is legitimately reusable across roles (e.g., scapular control).
- **Library-only roles (C272).** `ladder` and `library` are never requested by a template block, so `resolve_session` never selects them; `backend/engine/catalog_roles.is_library_only()` removes them explicitly from the other engine-built pools (body-part picker, ad-hoc builder, coach composer pool). They are visible to the custom-session builder and to Claude Code (`/custom-session`, `scripts/athlete_context.py`). A library-only exercise carries ONLY that role, never mixed with an engine role.

#### Optional descriptive fields (C272)

On library-only exercises (allowed on any exercise, never read by the engine):

- `progression` — how the drill gets harder (one lever at a time).
- `measure` — the one number logged per session (e.g. foot readjustments on a sample problem, hover x/5, FALL vs TAKE + LET_GO).
- `sources` — citations (URLs or bibliographic strings).
- `protocol_refs` — ids of protocols in `bw_ladders.json` → `protocols` that apply to this exercise (set on the four limit exercises → `limit_weak_style`, on `hang_rampup_progressive` → `pocket_warmup`). The resolver does not copy it into a session.

#### Progressions file (`backend/catalog/progressions/v1/bw_ladders.json`, C272)

- `families[]` — 16 bodyweight families: `family`, `axis_default` (`reps` | `seconds`), `stimulus_ref` (`null` or a `stimulus.py` family), `heavy_pull` / `heavy_pull_from_level`, `hanging` / `hanging_from_level`, `skill_family` (60-day history window instead of 120), `lower_back_risk_from_level` (manual only from that level until a lower-back pain zone exists), `floor_level_advanced`, `entry_seed[]` (`{test, min, max?, level, target | target_from_test{divisor|factor}, ramp?, requires_equipment?}`), `gates[]`, `terminal` (`kind`: `tempo` | `load` | `handoff` | `cap`), `variants[]`, `extras[]`, `levels[]` (`level_idx` from 0, `exercise_id`, `axis`, `sets`, `band{lo,hi,step}`, `advance_sessions`, `rest_s`).
- `technique_ladders[]` — `feet` (P1-P4), `positions` (Q1-Q4), `falls` (F1-F3): levels with drills, `advance`, `regress`, `measure`. The athlete's current technique level lives in the athlete plan notes, not in `user_state`.
- `protocols{}` — `limit_weak_style`, `template_warmup`, `outdoor_technique_day`, `pocket_warmup`.
- `history_aliases[]` — `hanging_leg_raise` counts as `toes_to_bar` for every log (its catalog note says "straight legs to bar"); an alias may carry an optional `before` cut-off date. The to-horizontal level is `hanging_leg_raise_horizontal`.
- `heavy_pull_exercise_ids()` (bw_ladders.py) — the ladder heavy pulls (front lever: every level, variants, raise/row; `pull_bw` from L3). `athlete_context` adds a day carrying one of them to the heavy-pull days of a **tested** athlete; `retest_policy.is_heavy_pulling_session` does not read them.
- `FINGER_HARD_LIBRARY_IDS` (stimulus.py) — library drills that make a session finger-hard without being a stimulus exposure (`three_attempt_comp`). Every library-only exercise with `stress_tags.fingers == "high"` must be finger-hard (test-pinned).
- Read by `backend/engine/bw_ladders.py`: `family_of()` and the read-only `seed_levels()` (sources `state` | `history` | `test` | `none` | `catalog` | `not_applicable`). No `bw_progression` key exists in `user_state` yet (BW-PROGRESSION brief).

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
- `lead_pe_anchor` — **derived, not stored** (A292, R6-PE): `max(lead_max_os, lead_max_rp − 3 half grades)`
  (`progression_v1.lead_pe_anchor`, constant `PE_ANCHOR_RP_HALF_STEPS = −3`, an engineering constant).
  **Tested athletes only** (`progression_v1.pe_anchor_applies`: tested official max < 90 days on fingers
  or pulling, the A290 gate); an untested athlete gets `lead_max_os` and the output reports `grade_ref:
  "lead_max_os"`, exactly as before A292.
  Used by the lead power-endurance drills `route_intervals`, `route_linked_laps`, `route_on_the_minute`,
  `threshold_climbing`; aerobic/ARC work stays on `lead_max_os`. A tie goes to the OS, so a climber whose
  onsight is within 3 half grades of the redpoint gets the same grade as with `lead_max_os`. Either grade
  missing or off the ladder → the other one; both → no `suggested_grade`. `inject_targets` also emits
  `suggested.grade_anchor_from` = `lead_max_os` | `lead_max_rp` (dropped when the endurance memory
  overrides the anchor). Example: OS 7a+, RP 8a+ → anchor 7c → route intervals (−1) **7b** (was 6c+).

#### `grade_offset`

Integer offset from the reference grade. Range: **-6 to +1**.

Unit: **one letter** (6a → 6b), i.e. **2 half grades** — the catalog values below
are unchanged. Since A291 (R6a) the arithmetic runs on the **half-grade ladder**,
where the "+" IS a step: `6a, 6a+, 6b, 6b+, …`. The ladder is the anchor's own
scale (`grade_scale_for_ref`): `french` = `assessment_v1.GRADE_ORDER` (5a … 9a+) for
`lead_*`, `font` = `FONT_GRADES` (5A … 8C+) for `boulder_*`. Results clamp to the
ends of the ladder. Helper: `progression_v1.step_grade_scaled(grade, letter_offset,
scale)` (`step_grade_half` for half-grade steps); output canonical uppercase (B344).

Examples:
- `lead_max_os=7c`, offset=-2 → prescribed grade: **7a**
- `lead_max_os=7a+`, offset=-1 → **6c+** (before A291: 6c — the "+" was stripped first)
- `lead_max_os=9a`, offset=-1 → **8c** (before A291: anything off the Font list became 6C-relative)
- `boulder_max_rp=6A`, offset=-2 → prescribed grade: **5B**

A reference grade that is not on its ladder (e.g. `V9`, an empty string) emits **no**
`suggested_grade` (plus a log warning) — it used to fall back silently to 6C.
`step_grade` (whole letters, strips the "+") is kept only as a legacy helper; no
engine path calls it.

**Pencil-edited sessions (A291, DECISIONS "Grades").** `_auto_resolve` never re-resolves a
`_user_edited` session (B153b), so `engine/target_refresh.refresh_edited_session_targets`
re-runs `inject_targets` on its engine-placed instances and copies back **only** the
grade-target keys (`GRADE_TARGET_KEYS`: `suggested_grade`, `grade_ref`, `grade_offset`,
`grade_scale`, `grade_source`, `suggested_boulder_target`; a key the fresh run no longer
emits is removed). Exercises, prescriptions, loads and `user_added` instances do not move.
Only pending sessions dated today or later: done/skipped/past sessions are never touched.

**Units by module** (they differ on purpose — check before reusing a number):

| where | unit |
|-------|------|
| `prescription_defaults.grade_offset` (exercise catalog) | letters (×2 half grades) |
| limit-family feedback delta (`_grade_delta_for_feedback`) | half grades: very_easy +2, easy +1, ok 0, hard −1, very_hard −2 |
| endurance memory step (B289 group B, 2 concordant feedbacks) | ±1 half grade |
| limit memory (`LIMIT_*` constants, B365) | half grades |
| free-session presets (`free_session.offset_grade`) | half grades, Font ladder |
| outdoor pitch ladder (A265) | half grades |

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

#### Taper fields (A281)

Emitted when a trip is declared, on the two weeks before `trip.start_date`.

| field | where | meaning |
|-------|-------|---------|
| `taper_volume_multiplier` | week-plan **day** | 0.6 (days T-14..T-8) or 0.4 (T-7..T-1). Absent = no taper. |
| `pretrip_deload` | week-plan **day** | day inside the 3-day no-hard window (T-2..T). Pre-existing field, window narrowed from 6 days by A281. |
| `taper_scaled_from` | resolved **prescription** | the catalog set count before scaling, so the reduction is auditable. |

Constants live in `macrocycle_v1`: `TAPER_TOTAL_DAYS` 14, `TAPER_WEEK1_VOLUME`
0.6, `TAPER_WEEK2_VOLUME` 0.4, `TAPER_NO_HARD_DAYS` 3.

**What the taper scales, and what it must not.** Only `sets`, and only for
exercises whose catalog `role` includes one of `main`, `accessory`,
`conditioning`, `technique`. Loads, grades and intensity percentages are never
touched — holding intensity while cutting volume *is* the taper (Bosquet et al.
2007, Med Sci Sports Exerc: −41/−60% volume, intensity and frequency constant,
ES 0.72 ± 0.36). Sets never fall below 1: frequency is the other thing a taper
must hold. A test session is exempt as a whole — its protocol is fixed.

Note the role check is an **allow-list**, deliberately: `max_hang_7s` carries
`role: ["main", "test"]`, so a deny-list on `"test"` would have exempted max
hangs from the taper everywhere — the one kind of work that most needs it.

---

#### `grade_scale` (emitted, render-only — B344)

The whole-grade ladder above is shared by Font and French (`6a/6b/6c/7a` ≡
`6A/6B/6C/7A`), so `step_grade` is correct for both — but it returns the
**canonical uppercase** value, and on a rope drill anchored to `lead_max_os`
that surfaced in the UI as `"6C"`. Uppercase `6C` reads as a Font *boulder*
grade (≈ 7a+ French): the string said something far harder than the `6c` French
actually prescribed.

`inject_targets` therefore also emits `suggested.grade_scale`, derived
deterministically from `grade_ref`:

| grade_ref | grade_scale |
|-----------|-------------|
| `lead_max_os`, `lead_max_rp`, `lead_pe_anchor` | `french` |
| `boulder_max_os`, `boulder_max_rp` | `font` |
| absent | `font` |

Same contract as `displayBoulderGrade`: the engine keeps its convention on the
wire, the client picks the casing (`displayPrescribedGrade` in `gradeUtils.ts`).
Nothing downstream branches on it, and an older cached payload without the field
renders exactly as before.

✅ **Changed in A291 (R6a, decision Daniele 2026-10-04):** the `+` of the
reference grade is no longer stripped before the offset — `lead_max_os = 7a+`
and offset −1 gives `6C+` (rendered `6c+`), not `6C`. Closes
B-LEAD-HALF-GRADE-ROUNDING, which B344 had left open as a methodology decision.

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

#### Anchored entries (B364)

For the four **anchored** exercises (`weighted_pullup`, `weighted_chinup`, `max_hang_5s`, `max_hang_7s`) of a **tested** athlete the entry is the WORKING load, never a max. `next_total_load_kg = last_total_load_kg + step` (kg label steps, measured fields first), plus the additive fields:

| Field | Meaning |
|---|---|
| `last_reps` | reps per set of the logged session (pulls) |
| `last_set_reps` | measured reps of the last set (AMRAP, stop one before failure), when given |
| `last_work_seconds` | hang duration of the logged session (hangs) |
| `last_hang_held_s` | measured hold of the last hang, when given |
| `phase_id_at_log`, `intensity_at_log` | phase and session intensity of the log — the read normalises the working load to today's phase/intensity |
| `escalation_anchor` | `{date, total_kg}` — start of the rolling 7-day window of the finger rise limit (≤ +5 % of the max) |
| `anchored` | `true` |

**`e2rm_total_kg`** (the B363 training re-base of the 2RM) is no longer written or read for a TESTED athlete (`scripts/migrate_b364.py` pops it there). For an untested athlete it stays the pre-B364 pull-up progression (written by `_apply_weighted_pullup_feedback`, read by `pullup_reference_2rm`), bit for bit. An entry is read only if `updated_at` is strictly after the official test date and ≤ 60 days old.

#### Anchored prescription (`suggested.anchored`, B364)

`inject_targets` (and every other consumer through `anchored_load`) writes `load_source: "anchored"` and `anchored: {source: working_load|phase_target, phase_id, intensity, floor, cap, clamped: cap|floor|fatigue_floor|null, pct_of_official, ramp: {n, factor, gap_days, source}, official: {protocol, total, one_rm?, total_at_duration?, date, source, age_days, confidence, converted}, guards: [{guard: heavy_pull_week|same_session_finger|finger_hard_recent|reentry_sets, …}], pain?, fatigue?, no_date}`, plus `ceiling_note` when an easy label hits the cap. The resolver fields `target_total_load_kg` / `added_weight_kg` / `assistance_kg` are overwritten with the same numbers. A tested athlete's assisted hang (non-anchored, tested < 30 days) gets `load_assist_kg` instead of the "re-test" `load_warning`.

#### `progression_counters` (B364)

- `stimulus_exposures: {finger_max|pulling_max|limit_power|power_endurance: [{date, exercise_id, session_id, total_kg, sets_done, sets_prescribed, is_test, evidence}]}` — the ONE persisted exposure registry, written by `apply_feedback`, one row per (date, exercise_id), pruned to 120 days.
- `retest_signals: {exercise_id: {count, last_date, dates, official_date}}` — measured early-retest evidence since the official test (reset when the test changes). Never enqueues a test.
- `hard_labels: {pulling|finger: [YYYY-MM-DD]}` — hard/very_hard days on anchored exercises (28 days kept); 3 in 14 days = fatigue → load at the phase floor.
- `pain_blocks: {fingers|elbow|shoulder|other: {score, from, until, source?, prev?}}` — read here, written by A295 (`source` = `date|session_id` of the log that wrote it, `prev` = the block it replaced).
- **Removed:** `max_hang_5s_hard_streak`, `max_hang_5s_easy_streak` (labels never schedule tests).

#### Custom session exercise `load_mode` (B364)

`custom_sessions[].exercises[].load_mode`: `anchored` | `fixed`, only meaningful for the anchored exercises; missing = `anchored`. `anchored` → the load is recomputed by `anchored_load` on the day played (`GET /api/custom-session/{id}?date=`, `GET /api/week`), with `stored_load_kg`, `load_source: anchored`, `suggested_external_load_kg`, `suggested_total_load_kg` added at read (plus `anchored`, `ceiling_note`, and `stored_sets` when the re-entry ramp caps max hangs at 5 sets); `fixed` → the user's kg, `load_source: user_fixed`. The builder exposes the choice as «Auto / Fixed kg» and saves it.

**Tested gate (B364).** `retest_policy.official_max(...).tested` is true only for a `tests.*` entry (written by a test log) or, as fallback, a baseline with `source: test_session`, younger than 90 days. A baseline-only `source: test` is an onboarding/assessment self-report persisted by `estimate_missing_baselines` (`from_baseline: true`) and is NOT tested.

#### Limit-boulder family entries (B365)

Entries of the `climbing_limit_boulder` family (`limit_bouldering`, `board_limit_boulders`, `spray_wall_limit`, `system_board_limit`) are keyed `<exercise_id>|surface=<surface>` and carry `last_used_grade`, `next_target_grade` (Font) and `surface_selected`. The read side (`inject_targets`) treats the family as **one memory per surface**: the newest entry of any family exercise on the selected surface wins.

- **Trust window:** 180 days (the rest of `working_loads` keeps the 60-day gate). An older entry is not read as a grade, but still proves the athlete has climbed limit on that surface.
- **Re-entry:** if the newest entry is ≥14 days old (or older than 180 days), the target is `base − 1 half grade` for 2 sessions; `base` = the entry's `next_target_grade` (past 180 days: the LOWER of the anchor and that stale grade, so a longer absence never gives a harder target). A new gap ≥14 days during an open re-entry restarts it from zero. A first-ever limit session on a surface is the plain anchor, no re-entry.
- **Additive re-entry fields**, written only by `apply_feedback`: `reentry_base_grade` (Font), `reentry_exposures` (1 or 2), `reentry_started_at`, `reentry_last_at` (YYYY-MM-DD). While re-entering, `next_target_grade` stays equal to the base (the discount is applied at read, never stored); the 2nd session closes the re-entry with `next_target_grade = base ± label delta`. An entry without these fields = no open re-entry (no migration).
- **Anchor without memory:** `boulder_max_rp + grade_offset` on `gym_boulder`; 2 half grades lower on boards (`board_kilter`, `board_moonboard`, `board_other`, `spraywall`). Not applied to the Kilter benchmark fallback.
- **Floor/ceiling:** ±2 half grades around the best `last_used_grade` (grades actually climbed, never a target not yet sent) on that surface in the last 180 days. It clamps the BASE (memory or re-entry base) before the re-entry discount, so it never cancels the discount. After a hard/very_hard at grade X the floor is at most X − 1 half grade: one bad session is absorbed, a run of failures walks the target down instead of pinning it.
- **Read-only consumers** (coach prompt, weekly report progression) quote `limit_next_target()` — the grade the card prescribes — not the raw `next_target_grade`, which is the base during a re-entry.
- **Band:** `target_grade_low = target_grade − 2 half grades`, computed from the final target.

`suggested_boulder_target` gains two additive fields: `target_source` (`anchor` | `memory` | `reentry`) and, while re-entering, `reentry: {base_grade, exposures_done, exposures_required, started_at}`. All the thresholds above are engineering constants (`LIMIT_*` in `progression_v1.py`), not literature values. Since A291 the limit feedback delta is in half grades too (easy on 7A → 7A+, it was 7B), and a re-entry that closes applies that half-grade delta to the base. The anchor keeps the "+" of `boulder_max_rp` (7B+ + 0 → 7B+).

#### `working_loads.rules.adjustment_policy`

Default values (used when user has no custom policy):

| label | pct_range | midpoint |
|-------|-----------|----------|
| very_easy | [0.10, 0.20] | +15% |
| easy | [0.05, 0.10] | +7.5% |
| ok | **[0.00, 0.00]** | **0%** |
| hard | [-0.05, 0.00] | -2.5% |
| very_hard | [-0.15, -0.05] | -10% |

**B344 — `ok` is neutral.** It used to be `[0.00, 0.05]`, i.e. +2.5% on every
session. `ok` is not merely the modal answer: it is the value submitted at
**zero user input** (`feedback-dialog.tsx`: "Unrated exercises default to Ok";
`buildDialogFeedbackItems` ships `feedback_label ?? "ok"`), so closing a session
without rating anything signed a load increase on every exercise. With ~2 finger
sessions/week that compounds to ~+5%/week, against a ~2%/week adaptation rate
(Devise et al. 2022). "Giusto così" now means "same load next time".

A user who has a **stored** `adjustment_policy` keeps their own values — the
change is to the default only, and `_rule_midpoint_pct` prefers the stored rule.

**B344 — minimum step.** `next_external_load_kg` is `base × (1 + pct)` rounded to
0.5 kg, with one guard: when `pct > 0` and the multiplier cannot move the value,
the load advances by `MIN_EXTERNAL_LOAD_STEP_KG` (0.5 kg) instead. Without it
`0.0 kg` was an **absorbing state** (0 × anything = 0, `very_easy` included), and
the whole small-load prehab regime was frozen (1.0 kg + `easy` = 1.075 → 1.0).
Deliberately **asymmetric**: there is no downward floor, because prehab loads are
already minimal. `last_external_load_kg` is unaffected — 0 kg remains a
legitimate recorded answer (B288).

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
| `grade_relative` (endurance: `climbing_intervals`/`climbing_continuous`) | `suggested_grade`, `grade_ref`, `grade_offset`, `grade_source` | working_loads memory (B289) → assessment.grades + prescription_defaults |
| `grade_relative` (limit family: pattern `climbing_limit_boulder`) | `suggested_boulder_target` (with surface) | surface-keyed working_loads memory → boulder_max_rp anchor (B289 extends beyond limit_bouldering) |
| `grade_relative` (technique: pattern `technique_drill`) | `suggested_grade` (static only) | assessment.grades + prescription_defaults — no memory by design (B289 group C) |
| `bodyweight_only` | — | no suggestion needed |

#### Feedback fields required per load_model (UI-24)

When submitting `exercise_feedback_v1`, the frontend must include load/grade data for the engine to update working_loads:

| load_model | required feedback fields | notes |
|------------|------------------------|-------|
| `total_load` | `used_total_load_kg` **or** `used_external_load_kg` | engine derives the other from bodyweight |
| `external_load` | `used_external_load_kg` | — |
| `grade_relative` (limit family) | `used_grade`, `surface_selected` | surface-keyed entry, steps ±1/±2 per feedback |
| `grade_relative` (endurance) | `used_grade` | exercise_id-keyed entry; target steps ±1 only after 2 consecutive concordant feedbacks (B289) |
| `grade_relative` (technique drills) | — | `used_grade` accepted but deliberately not stored (B289 group C: the drill grade is comfort terrain, not a progression lever) |
| `bodyweight_only` | — | feedback_label only |

If these fields are missing, `apply_feedback` does a silent skip (no crash, no update).

---

### 2.10.2b Grade provenance and onsight evidence (A292, R6b)

Written **only** by `POST /api/assessment/confirm-grade` (and, for `manual`, by `PUT /api/state`):

| field | shape |
|-------|-------|
| `assessment.grades_source.lead_max_os` | `{source: "outdoor_confirmed" \| "manual", date, previous, evidence?: [{key, date, spot_name, name, grade, style: "onsight" \| "flash"}]}`. Absent = the onboarding value. |
| `assessment.grade_evidence_dismissed.lead_max_os` | the grade the athlete declined (lowercase French). Blocks proposals ≤ it, not harder ones. |
| `assessment.grade_evidence_worked_routes` | route keys (`"<spot name>\|<route name>"`, casefolded, B362 normalisation; a later explicit onsight/flash of an already-seen name gets `"…@<date>"`, `"…@<date>#n"` on the same day) the athlete marked **worked**: never evidence again. Capped at 500. |

Evidence route (`engine/grade_evidence.is_onsight_evidence`): lead (route `discipline`, else the
session's), exactly one attempt with `result: "sent"`, `style` ∈ {absent, `onsight`, `flash`}, grade on
`GRADE_ORDER`, and — only when `style` is absent (inferred) — first appearance of its key in the
date-sorted log; an explicit `onsight`/`flash` is trusted over a name collision. The shared lower-level
predicate `is_first_go_send` also drives `compute_outdoor_stats`' onsight auto-detect.
Proposal: highest G with ≥ `MIN_ROUTES` (2) routes ≥ G on ≥ 2 distinct dates or spot names
(engineering constants); only if G > current OS, ≤ `lead_max_rp`, > dismissed. `all_in_trip` (every
supporting route inside a declared trip) is reported, not enforced. The outdoor log is never rewritten.
Confirm answer per route: `onsight` | `flash` | `worked`.

### 2.10.2c Limit log (A296, R6c)

`user_state.limit_log[]` — top level, append-only, capped at `LIMIT_LOG_CAP` (200, oldest dropped).
Written **only** by `progression_v1.apply_feedback` (limit-boulder family) and by
`POST /api/free-session/{id}/finish`; **not** in the `PUT /api/state` allowlist. A resubmitted
`(date, session_id, exercise_id)` replaces its entry (B197). Module: `backend/engine/limit_log.py`.

| field | shape |
|-------|-------|
| `date`, `session_id`, `exercise_id` | key of the entry (`exercise_id: null` for a free session) |
| `surface` | limit surface (`board_kilter`, `gym_boulder`, …) |
| `target_grade` | Font target prescribed that day (planned instance → this entry on resubmit → `_limit_target_state`) |
| `problems[]` | `{grade (Font), attempts 1-10, outcome: "sent" \| "high_point" \| "no_progress", sent_on_attempt?, crux_moves?, surface?, name?}`, max 8 per item (invalid rows dropped one by one) |
| `source` | `planned` \| `custom` (`custom_*`) \| `adhoc` (`generated_*`) \| `free` |
| `feedback_label`, `used_grade`, `next_target_grade` | what the item carried and the memory written |
| `reference_grade`, `step` (−1/0/+1), `step_reason`, `hard_attempts`, `warning?` | present when problems decided the step |
| `qualifies` | ≥ 2 problems at ≥ target (sent or high point) |
| `rp_proposal?` | `{grade, current}`: a send above `boulder_max_rp` on a non-board surface — proposed, **never written** |
| `qualifying`, `reason` | free entries only (`threshold` \| `toggle`) |

`step_reason` ∈ `sent_above_target` | `two_sends_at_target` | `progress_at_target` |
`first_session_without_progress` | `two_sessions_without_progress` | `hard_attempts_guard` | `reentry`.

Feedback item field `problems[]` (`exercise_feedback_v1`, limit family): with at least one valid row
the problems decide the step at reference R (the day's target; the re-entry BASE when the session
closes a B365 re-entry; during an open re-entry the memory stays the base): +1 half grade with ≥ 1
send at ≥ R+1 half or ≥ 2 sends at ≥ R; hold on any progress (send at ≥ R−1 half, high point at ≥ R,
crux moves at ≥ R); −1 half grade **only** when this session and the previous non-free entry on the
same surface both made no progress; never more than one half grade; more than
`HARD_ATTEMPTS_GUARD` (20) attempts at ≥ R−1 half → never up, `warning: hard_attempts_guard`.
Without problems the label path of §2.10.2 applies unchanged. All thresholds are ENGINEERING
CONSTANTS (no published source).

Free sessions: `free_sessions[].limit_session = {counted, reason: threshold | toggle | below_threshold
| no_target, target_grade, qualifying, toggled}` is stamped at finish on boulder surfaces
(`FreeSessionFinishRequest.is_limit_session` = the toggle). Climbs map to problems as
flash/sent → `sent`, attempted → `high_point`. Counted (≥ 2 climbs at ≥ the limit target of that
surface, or the toggle) → a `source: free` entry. A free entry never moves the target, never writes
`stimulus_recency` (A240/A213). Deleting the free session removes its entry.

Consumers: `stimulus.exposures` (a free entry IS the free `limit_power` exposure for a stamped
session — legacy unstamped sessions keep the RP − 2 threshold rule; a non-free entry with problems
is a fallback `source: "limit_log"` row, dropped when the week plan covers the day);
`stimulus.finger_hard_days` (a stamped free session that did not count is still finger-hard with
≥ 2 climbs at the OUTDOOR-HARD threshold); `key_sessions_v1.session_dose` (`dose: "limit_log"` on
`limit_power`: a custom/adhoc session with problems is full only when it `qualifies`, else partial
`limit_log_below_target`; catalog sessions and unlogged customs stay full on presence).
Read-time target outside the planner: `progression_v1.limit_grade_target` (custom `GET ?date=`,
builder proposal `grade_target`, adhoc/composer previews) and `limit_target_on_surface` (free).
`suggested_boulder_target.log_problems: true` tells the players to show the problem logger.
`limit_grade_target` also returns `surface_targets: {surface: {target_grade, target_grade_low, reentry?}}`
for every `surface_options` entry (review A296): a custom session has no gym, so the custom player
shows a surface picker and posts the chosen `surface_selected`. In the players a problem row starts
with **no outcome** (`LimitProblemDraft.outcome = null`) and an unrated row is never sent;
`crux_moves` is editable on `high_point` / `no_progress` rows (dropped on a send). In one feedback
the day target is fixed per surface by the first limit-family item, so a second limit exercise on
the same surface is judged against the same target.

A299: the read-time target is attached also by `GET /api/week` to not-yet-played custom / generated
slots (`week._with_custom_anchored_loads` → `custom_session.attach_limit_targets`, same as `GET
custom ?date=`), so every player recomputes it; it is never stored (a value round-tripped by the
client is recomputed). The coach adhoc preview carries `resolved_for_date` (the day its read-time
values were computed for; the client shows a preview target only when it equals its own today).
Weekly report section `limit_sends[]` = `limit_log.sends_by_surface(state, free_sessions, since,
until)`: `{surface, max_grade_sent, sends, sources[], target_grade}` per boulder surface, from
non-free limit-log problems with outcome `sent` + finished free boulder climbs `flash`/`sent` (free
log entries skipped: they copy the same climbs); `target_grade` = target of the last non-free entry
of the week on that surface. The post-session dialog sends `used_grade` / `problems` /
`surface_selected` through the same `limitFeedbackFields` as the guided player.

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

### 3.0 Canonical session template_ids (39)

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
- `legs_maintenance_lunch` *(strength_general, gym — C274 lunch: goblet squat, RDL, foot-strength block)*
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
- `treadmill_hiit_4x4` *(conditioning, gym — C274 lunch: 4x4 VO2max intervals, `tags.hiit`)*
- `treadmill_zone2_cardio` *(conditioning, gym — C274 lunch: Zone 2 incline walk + hip mobility)*
- `test_lp_max_5s` *(finger_max_strength, test)*
- `test_lp_repeater` *(finger_strength_endurance, test)*
- `test_max_hang_5s` *(finger_max_strength, test — legacy 5s)*
- `test_max_hang_7s` *(finger_max_strength, test — MVC-7, D85)*
- `test_max_weighted_pullup` *(pulling_strength, test)*
- `test_pullup_bw` *(pulling_strength, test)*
- `test_repeater_7_3` *(finger_strength_endurance, test)*
- `upper_body_weights` *(strength_general, home)*
- `upper_push_arms_lunch` *(strength_general, gym — C274 lunch: chest press, triceps, biceps)*
- `yoga_recovery` *(flexibility, home)*

#### Session-level optional fields

- `supplementary`: `bool` (default `false`). Non-climbing session offered in the Quick-Add "supplementary" list (`_get_supplementary_sessions`), filtered by `_SESSION_META.location`. In no phase pool: the planner never places it on its own.
- `tags`: `object` (default `{}`). Planner-facing flags of the catalog session, copied onto the resolved session: `test` (a test session), `hard`, `finger`, and **`hiit`** (C274) — a systemically hard interval session with no finger load. `hiit` lives **only** in the catalog (not in `_SESSION_META`), so every reader has one source; it does **not** count toward the hard / finger cap. Only `treadmill_hiit_4x4` carries it. **Read it only through `stimulus.is_hiit_session(session)`**: plan slots carry only hard/finger/test, so `session_flag(s, "hiit")` returns False for it; the accessor checks an explicit slot `tags.hiit`, then the catalog tag by `session_id`, then any exercise with `recency_group: conditioning_hiit` (custom / ad-hoc sessions). `treadmill_hiit_4x4` is also the one allowlisted exception to `_SESSION_META` `hard == intensity in {high, max}`.
- `intent.primary_goal: "conditioning"` (C274): general cardio (treadmill Zone 2 / HIIT). Not in the A291 map, so its closed-loop category is `complementaries` — treadmill cardio is not climbing endurance.
- `compatibility.slot`: `lunch_short` marks a session that fits a 45-minute gross lunch break (`time_budget.target_duration_min` ≤ 35, `hard_cap_min` 45 for the C274 sessions).
- **`selection.primary.pin_strict`** (C274, boolean, default absent = false): when the pinned `exercise_id` needs equipment that is not available, the block is **failed** (block `status: failed`, `chosen_by: pin_strict_incompatible_failed`, session `resolution_status: failed`) instead of being delegated to P0. For blocks where any substitute would change the session's meaning. Today only `treadmill_hiit_4x4.hiit_intervals` (without it P0 picked an easy incline walk and reported success).
- **Pinning a library entry** (C274): a library-only exercise (role `library`, C272) may enter a catalog session only through an explicit `selection.primary.exercise_id` pin — never through a role / domain / pattern filter. Today: `toe_flexor_isometric` and `edge_calf_raise_bigtoe` in `legs_maintenance_lunch` (pinned by `test_c269_exercise_reachability`).
- `boulder_fallback`: `string | null` (default `null`). Session_id of a boulder-discipline equivalent session, used when the user triggers the ephemeral "Boulder only" override (A210) on a rope-dependent session. Allowed values: any valid session_id in the boulder pool, or `null`. Only non-null for sessions whose core block requires `gym_routes` (currently: `endurance_aerobic_gym` → `boulder_circuit_gym`, `route_endurance_gym` → `boulder_circuit_gym`, `route_projecting_gym` → `limit_boulder_gym`).

### Canonical module template_ids (19)

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
- `general_warmup`
- `pulling_strength_compound`
- `route_projecting_main`
- `pulling_strength_test`
- `pulling_strength_test_bw`
- `warmup_climbing`
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
- unknown/missing feedback -> `ok` **for display only** (`canonical_feedback_label`). A295: progression, difficulty, feedback log, report and coach read `measured_feedback.feedback_rating(item, contract)` instead, where missing feedback is **not rated** (`None`).

**Feedback contract (A295, R4)** — `log_entry.feedback_contract`:
- `2` (every current client): `feedback_label` is OMITTED when the athlete did not rate the exercise (never `null`, never a default `ok`). The router drops `null` / unknown labels with a warning.
- absent (legacy client): a legacy `ok` is the old zero-input default and counts as **not rated**; other labels keep their meaning.
- **Not rated** = working load held at the load used (`next = used`), `last_feedback_label: null`, `last_rated: false`; left out of the session difficulty, `feedback_log.exercise_feedback`, fatigue `hard_labels`, the endurance grade streak and the report distribution.

**Measured fields per item (optional, A295)**: `last_set_reps` (int 0..20; pull-ups: AMRAP stopping one short of failure on the last set; double progression), `hang_margin` (`failed` | `0-2` | `3-5` | `>5` seconds left on the last hang), `hang_held_s` (number, guided player only: timed overhold of the last rep, capped client-side at target + 6 s), `target_reps` (int, the double-progression target the client showed). Router-attached: `prescribed_sets`, `prescribed_work_seconds` (with `prescribed_reps`, same three sources). `completed_reps` is sent only by the repeater tests (B133) — no longer a copy of `completed_sets`. Out-of-range values are dropped with a warning (200, never a 4xx: an outbox retry must not stick).

**Measure kind** (`measured_feedback.measure_kind`, explicit allowlists; exposed as `suggested.measure` by `inject_targets` and as `exercise.measure` on custom / generated rows at read time, never stored):
- `last_set_reps`: `weighted_pullup`, `weighted_chinup` (not in a test session);
- `hang_margin`: `max_hang_5s`, `max_hang_7s`, `max_hang_10s`, `horst_7_53` (not in a test session);
- `dp_reps` (double progression): external_load / total_load prescribed in reps without a work time, not a hang pattern, not loading-pin, not a test, not the pulls above. Never: `pinch_block_training`, `one_arm_hang_assisted`, `max_hang_ladder`.
- `dp_reps` also exposes `suggested.target_reps` + `suggested.dp_range [lo, hi]` (`lo` = prescribed reps, `hi = lo + max(2, round(0.25·lo))`) and `suggested_rep_scheme` `"{sets}x{target}"` when the target is above `lo`.

**Session pain (A295)** — `log_entry.pain = {score: 0..3, site: fingers | elbow | shoulder | other | null}` (site only from score 2; null → `other`). Written to `progression_counters.pain_blocks[site] = {score, from, until}`: score 2 → 7 days, score 3 → 14 days (a milder later report never shortens a block); score 1 is only recorded (`session_completion_log[].pain`, `feedback_log[].pain`). Zones: `fingers` = `stress_tags.fingers` medium/high (limit bouldering included), `elbow` = `stress_tags.elbow` medium/high, `shoulder` = `shoulder_sensitive` contraindication + weighted pull-up / chin-up / dip, `other` = every loaded exercise (the anchored four included). Read side (by date, deterministic): −10 % on the zone's suggested load, finger hangs ≤ 85 % (score 2) / 80 % (score 3) of the official 7 s max, `suggested.pain_flag: true` + `suggested.pain`; anchored exercises through `anchored_load` (pain before the floor). Upward double-progression steps, upward anchored steps and `retest_signals` are frozen on the zone. Score 3 adds a `limitation_suggestions[]` row with `source: "pain"` (B38 mechanism).
*A295 review:* every upward step on the zone is frozen (measured / labelled hangs outside the anchored four and the plain label path included). Loading-pin per-hand loads (`suggested.right_hand|left_hand`) get the same cut, finger lifts capped at 85/80 % of that hand's max. **No compounding:** under a block the write holds the pre-block value — `working_loads.entries[].pain_hold = {key: date|session_id, next_before}` (snapshot for idempotent replays); the pre-block value is the load used with exactly the read-side cut undone (ratio of the reads of that date without/with the block), bounded by the load used and the unpained read; down steps (hard, failed) apply to it. **Correction:** a log carrying `pain` first strips from every block chain what its own `date|session_id` wrote, then applies the new score (0/1 clears it); a log without `pain` leaves the blocks untouched. Test sessions get `pain_flag` without a cut (`flag_only`). The retest policy adds day blocker `blocked:pain` / `blockers[].code: "pain"` (pain ≥ 2 on the axis zone in the 7 days before, or a block still running; finger = fingers/other, pulling = elbow/shoulder/other).

**Working-load entry fields added by A295**: `last_rated`, `last_set_reps`, `dp_target_reps`, `dp_range`, `dp_last_outcome` (`reps_up` | `load_up` | `hold` | `label_up` | `label_down` | `pain_freeze` | `not_completed`), `applied {key: "date|session_id", base_before}` (idempotency: the same session recomputes from the snapshot, so a replay is a no-op and a pencil correction applies), `last_hang_margin`, `last_hang_held_s`, `escalation_anchor` (non-anchored hangs too). An out-of-order log (older than the entry) never rewrites a measured entry.

**Session difficulty (A295)** — `measured_feedback.derive_session_difficulty`: fatigue-cost-weighted mean of the **rated** items only, written only when they cover ≥ 50 % of the session's fatigue cost (skipped items excluded); otherwise `difficulty` is absent from `feedback_log[]` / `session_completion_log[]`, `GET /api/week` sets no `feedback_summary`, and a resubmit without a rating never erases a rated one. Weekly report: `difficulty.avg_label` is `null` when nothing was rated, `difficulty.unrated_count` counts the sessions without a difficulty; monthly `feedback_summary` uses the bucket `unrated` instead of a fake `ok`.

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

**B364:** feedback labels no longer write this queue (the two-hard / two-easy max-hang enqueue is removed); only the retest policy (A289) schedules tests, from `progression_counters.retest_signals` and the calendar.

Current canonical `test_id` values:
- `max_hang_7s_total_load` (D85: was `max_hang_5s_total_load`)
- `weighted_pullup_2rm` (D84: was `weighted_pullup_1rm`)
- `max_pullups_bw` (D84b: bodyweight pull-up gate test)
- `repeater_7_3_max_sets_20mm`
- `lp_max_lift_5s`
- `lp_repeater_7_3`

### 4.4 Stimulus families, exposures and the retest primitives (A288)

Defined once in `backend/engine/stimulus.py` and `backend/engine/retest_policy.py`
(pure, read-only). Every later brief imports these values instead of redefining them.

**Stimulus family** (`stimulus.EXERCISE_FAMILY`, one family per exercise, derived from the catalog):

| Family | Rule | Members |
|---|---|---|
| `finger_max` | domain `finger_max_strength` on a defined edge | max_hang_5s, max_hang_7s, max_hang_ladder, horst_7_53, one_arm_hang_assisted, lp_max_lift_5s, lp_max_lift_7s, lp_short_lifts, lp_max_test_5s (NOT min_edge_hang, max_hang_10s, lp_max_lift_10s) |
| `pulling_max` | externally loaded vertical pulls | weighted_pullup, weighted_chinup |
| `limit_power` | pattern `climbing_limit_boulder` (no warm-up) + `campus_ladder` (no campus_sprint_endurance) | limit_bouldering, board_limit_boulders, spray_wall_limit, system_board_limit, campus_* |
| `power_endurance` | domain `power_endurance` | four_by_four_bouldering, linked_boulders(_circuit), route_intervals, threshold_climbing, emom/otm_bouldering, thirty_thirty_intervals, route_linked_laps, route_on_the_minute |

**Exposure row** (`stimulus.exposures`): `{date, family, exercise_id, session_id, source, evidence, is_test, sets_done, sets_prescribed, used_total_load_kg, used_external_load_kg}`.
- `source`: `week_plan` | `archive` (A221 `week_archive`) | `free` | `registry` (`progression_counters.stimulus_exposures`, written from B364 on).
- `evidence`: `measured` (logged entry) | `planned` (done session without logged entries).
- Exposures are counted in distinct **days**. Outdoor days are not family exposures.

**Finger-hard day** (`stimulus.finger_hard_days`), `reason`: `finger_hard_session` (tags/`_SESSION_META` finger+hard, or a session delivering `finger_max`/`limit_power` — custom sessions included — or carrying a `FINGER_FATIGUE_EXTRA_IDS` hang: min_edge_hang, max_hang_10s, lp_max_lift_10s, which are finger-hard but not `finger_max` exposures) | `outdoor_hard` (a route with no discipline in a `both`/unset outing is classified by grade scale: uppercase Font letter = boulder) | `free_limit` (finished free sessions only: `finished_at: None` is skipped). Logged entries count only when really done (`stimulus.counted_entries`), for heavy pulling too.

**Hard-climb threshold** (OUTDOOR-HARD): redpoint − `HARD_CLIMB_GRADE_STEPS` (2) steps on the engine ladder, `+` grades included (lead 8a+ → 7c+, boulder 7C → 7B). A free boulder session is a `limit_power` exposure with ≥ `FREE_LIMIT_MIN_PROBLEMS` (2) climbs at/above it.

**Retest primitives** (`retest_policy`):
- Protocols: `max_hang_7s_total_load`, `max_hang_5s_total_load`, `weighted_pullup_2rm`.
- `official_max(...)` → `{protocol, family, total_kg, date, age_days, fresh, tested, source, test_id, seconds, source_seconds, converted, one_rm_kg, bodyweight_kg, edge_mm, grip, stored_confidence}`. `tested` = source `test`/`test_session` and age < `TEST_FRESH_DAYS` (90).
- `test_confidence(...)` → `confidence`: `high` | `low` (computed: < 2 exposure days in the 21 days before) | `None` (no family, e.g. repeater). The stored `confidence` field is informational only. From B364 the test log stores the computed value on `tests.*[]` (+ `confidence_basis {exposures, window_start, window_end, min_required}`, `delta_pct`, `trend`: `stable` (|Δ| < 5 %) | `up` | `down`, `previous_date`) and on the baseline (`baselines.hangboard[0].confidence`, `bodyweight_at_test_kg`; `baselines.pulling.confidence`).
- `reentry_step(...)` → `{n, factor, gap_days, run_start, last_exposure, run_dates, in_reentry}`; gap `REENTRY_GAP_D` = 14; factor 0.90 (n ≤ 1) / 0.95 (n = 2) / 1.0 (n ≥ 3). `extra_dates` (B364) adds days the view cannot see (the `tests.*` dates).
- Constants: `FINGER_GAP_H` 48, `RETEST_BLOCK_H` 72, `PULL_TEST_BLOCK_H` 48, `HEAVY_PULL_PCT_1RM` 0.85, `LOW_CONF_RETEST_D` 28, `VERY_HARD_BLOCK_D` 3, `PRE_TRIP_BLOCK_D` 10, `RETEST_BLOCKED_PHASES` (performance, deload), `HANG_PCT_PER_S` 0.015.

### 4.4b Closed-loop stimulus categories (`stimulus_recency`, A291)

`closed_loop_v1.STIMULUS_CATEGORIES` (closed set): `finger_strength` | `boulder_power` | `endurance` | `complementaries`. Written by `apply_day_result_to_user_state` into `stimulus_recency.<category>`; read by `report_engine` (stimulus balance) and `body_part_picker` — never by the planner. Not the same thing as the A288 stimulus **families** above.

Since A291 a session's categories come from the session catalog's `intent.primary_goal` (planned sessions in the week plan carry `intent: null`, so the old intent branch never fired):

| primary_goal | categories |
|---|---|
| `limit_projecting`, `contact_strength` | boulder_power + finger_strength |
| `finger_max_strength`, `finger_strength_endurance` | finger_strength |
| `power_endurance`, `aerobic_capacity`, `aerobic_endurance` | endurance |
| `route_projecting` | endurance + complementaries |
| anything else (technique_*, strength_general, core, regeneration, …) | complementaries |

The 2 catalog sessions without a primary_goal are mapped explicitly: `finger_aerobic_base`, `finger_endurance_short` → finger_strength + endurance. The planner tag `finger` always adds finger_strength. Ids the catalog does not know (custom, ad-hoc, outdoor) use the legacy substring rule, where `power` no longer matches `power_endurance` (power_endurance_gym used to count as boulder_power).

### 4.5 Retest decisions and retest status (A289)

`retest_policy.retest_decisions(state, week_start, *, today, finger_device, archived_weeks, outdoor_rows)` — the only scheduler of tests of a **covered** axis (`finger` with a hangboard, `pulling`; covered = `official_max(...).tested`, i.e. a test < 90 days). `None` when nothing is covered (planner byte-identical). Output stored, with the placement outcome, in `week_plans[*].profile_snapshot.retest_decisions` `{version, week_start, applied, covered_axes, required_sessions[], skipped[], already_scheduled[]}`.

- `required_sessions[]`: `{kind: "test", axis, session_id, protocol, trigger, reason, earliest_date, allowed_dates, required: true, order, paired_with, last_test_date, confidence, gap_days}`; in the snapshot each one also carries `status: placed|skipped`, `placed_date`, `placed_slot` or `skip_reason`.
- `trigger` (closed set): `end_of_phase` (last week of strength_power) | `end_of_phase_slipped` (the week after, once, when the gap kept the whole end-of-phase week out of reach) | `cycle_start` (first week of a macrocycle) | `maintenance` (`MAINTENANCE_RETEST_D` = 84 days after the last test) | `early_retest` (`EARLY_RETEST_SIGNALS` = 2 measured days in `progression_counters.retest_signals` against the current official test; earliest = last test + 28 days, the day after the last signal).
- Gap: `LOW_CONF_RETEST_D` 28 after a low-confidence test, `HIGH_CONF_RETEST_D` 42 otherwise. Confidence: the stored one when it carries `confidence_basis` (computed by a test log or by the B364 migration), else `test_confidence` with the archived weeks.
- `skipped[].skip_reason` / `week_plans[*].skipped_tests[].reason` (with `source: "retest_policy"`, `required: true`, `trigger`): `slipped:gap` | `blocked:gap` | `blocked:phase` (performance, deload) | `blocked:trip` (≤ 10 days before a trip or during it) | `blocked:very_hard` (very_hard feedback in the 3 days before) | `blocked:pain` (A295: pain ≥ 2 on the axis zone in the 7 days before, or a pain block still running) | `no_placement_slot` (PASS 3a found no day/slot) | `blocked:no_paired_slot` (the hang was placed but the pull-up found no later day).
- Day blockers (hours → whole calendar days, slot ignored): hang test — no finger-hard day (`stimulus.finger_hard_days`, customs and outdoor-hard included) in the **3** days before (inclusive: a finger-hard evening 3 days earlier is ~60 h, A289 review), no finger-hard session left on the same day; the historical PASS 3 also keeps its finger tests (repeater) out of those 3 days; pull-up test — no heavy pulling (`retest_policy.is_heavy_pulling_session`) the day before or on the same day. For the pull-up, 48 h exactly (two days earlier) does not block.
- `locked_slots[]` `{date, slot}` / `locked_dates[]` (A289 review): slots that `regenerate_preserving_completed` will refill with the old plan's done/skipped sessions, and today when it holds a done session (copied wholesale). PASS 3a never places a test there.
- `skip_reason: deferred:earlier_week` (+ `deferred_to_week`): the test was already due in an earlier week (from the current one) that is not generated yet — it waits for that week, so the week a test lands in does not depend on which week is opened first.
- Paired test day: when both axes are due, one day, hang in an earlier slot than the pull-up.

`retest_policy.retest_status(state, today, ...)` → `GET /api/week/{n}.retest_status` (additive, live on every GET, absent when the athlete has no test): `{as_of, stable_band_pct: 5.0, covered_axes, axes: {finger|pulling: {axis, covered, protocol, official_total_kg, test_date, age_days, confidence, confidence_exposures, confidence_min_exposures, trend: stable|up|down|null, delta_pct, previous_date, earliest_retest, signals: {count, needed}, fatigue, next_test, next_test_reason}}}`. `next_test`: `{date, session_id, source: planned|projected, trigger, reason, week_start?, blockers[]}`; `blockers[].code`: `very_hard` | `trip` | `recent_finger` | `heavy_pull` | `pain` (live flags on a planned test — the engine never moves it). `next_test_reason` when `next_test` is null: `not_tested_recently` | `blocked:phase` | `blocked:gap` | `blocked:trip` | `blocked:very_hard` | `not_due_within_horizon` (`STATUS_HORIZON_WEEKS` = 16) | `no_placement_slot` / `blocked:no_paired_slot` (read from the snapshot of a generated week) | `not_in_plan` (the week is generated without the test, e.g. before A289 — a cached week is never regenerated, so it is not projected there) | `missed` (placed on a day already past, not done). Only axes whose official max comes from a real test appear (`tests.*`, or a `test_session` baseline): an onboarding estimate never produces a row. The manual 6-week reminder is hidden only when **both** axes are covered.

**Macrocycle position** (`backend/engine/macro_position.position_on`): `{phase_index, phase_id, week_in_phase, phase_weeks, abs_week, total_weeks, phase_start, phase_end, is_last_week_of_phase, next_phase_id, before_start, after_end, paused}` — pause-aware (A223), same rule as `deps.current_phase_and_week`.

### 4.6 Athlete context for Claude Code (A293)

`backend/engine/athlete_context.build_athlete_context(state, today, archived_weeks=, outdoor_rows=, catalog=)` is pure and read-only. It is printed by `scripts/athlete_context.py` and is NOT persisted in `user_state` and not served by the API.

Top-level keys: `version` (`a293.1`), `as_of`, `constants`, `athlete_plan`, `position`, `maxima`, `anchors`, `retest`, `key_sessions`, `key_sessions_next_week`, `upcoming`, `recent`, `guards`, `variety`, `working_loads`, `try_hard`, `limits`, `trips`, `work_checks`, `warnings`.

- **`maxima`**: keyed by protocol (`max_hang_7s_total_load`, `max_hang_5s_total_load`, `weighted_pullup_2rm`).
  - Each row has `confidence` + `confidence_basis` (`stored` | `computed`) from `retest_policy.axis_confidence`.
  - `stored_confidence` is informational only.
- **`anchors.exercises.<id>`**: the `anchored_load` prescription of the day (custom intensity), copied verbatim.
- **`key_sessions`** / **`key_sessions_next_week`**: A294's `key_sessions_v1.compute_key_status` for the current and the next week (`source: "a294"`, see §4.7). The A293 fallback is gone; a failure gives `source: "error"` + warning `KEY_SESSIONS_ERROR`. The rows keep `last_done` as an alias of `last_full_date`.
- **`guards.days[]`**: `{date, finger_max_ok, finger_reasons[], finger_hard_today, finger_spacing_gap_d, heavy_pull_ok, front_lever_ok, pull_reasons[], hiit_ok, hiit_reasons[]}`. Built from session properties only, never from the load score.
  - Finger: finger-hard days ±1, hang test within 72 h, and the replanner's spacing — any `finger`-tagged session within `finger_spacing_gap_d` = `ceil(recovery_multiplier)` days.
  - Heavy pull / front lever (same rule): every rolling 7-day window containing the day, planned days included; 24 h before limit/strength_long; pull test within 48 h.
  - Both: deload phase, and the week's hard cap reached when the day is not already hard.
  - `guards.hard_cap`: `{week_start, cap, hard_days, count, at_cap}`. `cap` = snapshot `hard_cap_per_week` (0 is valid) else `planning_prefs.hard_day_cap_per_week`.
- **`working_loads[].flags`**: `STALE` (> 60 days) | `TEST_COPY` (last external load = a test's external load ± 0.5 kg).
- **`try_hard`**: counts of `SEND` | `FALL` | `TAKE` | `LET_GO` tokens in the outdoor notes of the last 28 days (format `T1 M7 FALL +1`), plus `fall_pct_of_non_send`. A296 replaces it with the limit log.
- **`work_checks[]`**: `HIIT_ON_GUARD_DAY` (a planned HIIT on a `hiit_ok: false` day) and `WORK_RECURRENCE_PHASE_CHANGE` (phase change within 14 days with "Work —" sessions already planned in the next phase). Also copied into `warnings`.
- **`warnings[].code`**: `KEY_SESSIONS_ERROR` | `KEY_CONFLICT` | `SKIP_WITHOUT_ID` | `REMOVED_UNKNOWN` | `KEY_MISSING` | `STALE` | `TEST_COPY` | `LOW_CONFIDENCE_TEST` | `MAX_NOT_TESTED` | `AT_CEILING` | `HIIT_ON_GUARD_DAY` | `WORK_RECURRENCE_PHASE_CHANGE`.
- **Athlete notes**: the block between `<!-- athlete-context:notes -->` and `<!-- /athlete-context:notes -->` in `docs/training/athlete_plan.md` (ladder levels, pocket notes, current project) is printed by the CLI.

### 4.7 Key sessions (A294)

`backend/engine/key_sessions_v1.compute_key_status(state, today, archived_weeks=, outdoor_rows=, week_start=, with_proposals=True)` — pure, derived at read, **never persisted**. Returned as `key_status`, a **sibling** of `week_plan`, by `GET /api/week/{n}`, `POST /api/replanner/events|quick-add|override`. Catalog: `backend/catalog/key_stimuli/v1/key_stimuli.json` (`stimuli` + `phases`).

- **Stimulus** (`KeyStimulus`): `finger_max` | `finger_maintenance` | `limit_power` | `pulling_max` | `power_endurance` | `project` | `technique` | `try_hard`. Per phase: SP `finger_max` p1, `limit_power` p1, `pulling_max` p3 (max severity warning); PE `power_endurance` p1, `finger_maintenance` p2, `limit_power` p3 with `max_gap_days` 12; performance `project` p1; `technique` in every phase (deload: max severity `info`); `try_hard` in SP, PE and performance only — it rides on its host key (`attached_to`: `limit_power`, `project` in performance) and goes `not_due` with it (A294 review: removed from base, no limit key there).
- **Requirement row**: `{key, label, why, priority, max_severity, target, status, resolution, severity, debt, done[], partial[], planned[], skipped[], lost[], exposures_21d?, last_full_date?, due_by?, next_key?, hint?, rejections?}`. `debt = max(0, target − full-dose done days − valid planned days)`.
  - `status`: `done` | `planned` | `partial` (only partial-dose sessions: no ✓, debt stays, severity ≤ warning) | `missing` | `not_due` (max-gap requirement due after the week) | `unplaceable` (`unmet_stimulus` finger_strength: debt 0, the B361 card speaks).
  - `resolution` (debt only): `proposal` | `deferred_next` (catch-up would break next week's key → `next_key`) | `deferred_fatigue` (very_hard feedback or adaptive replan in the last 72 h) | `let_go` | `missed` (past week) | `null` + `hint` (no catalog session can carry it with the athlete's equipment — A294 review, never a false `let_go`).
  - `severity`: `none` | `info` (deferred) | `warning` | `critical` (max_severity critical — technique included since the A294 review, any priority — and ≥ 50 % of the phase weeks so far without a full exposure, or the last week of the phase with none).
  - `lost[]`: skips, plus downshifts (`downshifted_from`) **only while the requirement still has debt** (A294 review).
- **Dose** (`done[].dose`, `dose_reason`): `full` | `partial`. Measured only for the anchored stimuli (`finger_max`, `pulling_max`): main exercise load ≥ the anchored floor of the phase on that day (`anchored_load(...).floor`, ramp and pain applied, 0.25 kg tolerance) and ≥ `MIN_FULL_SETS` (4) sets. Catalog sessions and tests are full (an untested athlete's logged catalog session too — A294 review); custom exercises in `load_mode: anchored` are full when the athlete is tested; untested custom → `no_tested_max` (partial). Reasons: `presence` | `test` | `catalog_session` | `not_anchored` | `anchored_prescription` | `at_or_above_floor` | `below_floor` | `too_few_sets` | `no_tested_max` | `load_unknown` | `no_main_exercise`.
- **Evidence beyond the plan**: outdoor-hard day (A288 rule) → `try_hard`, `project`; free boulder session with ≥ 2 problems ≥ threshold → `limit_power`, `try_hard`. Tests count for `finger_max` / `pulling_max` / `finger_maintenance`. A294 review: an outdoor day no longer counts as technique (not verifiable).
- **Technique key**: `technique_focus_gym`, or ≥ 2 distinct technique-category drills excluding the warm-up drills and the recency groups `TECHNIQUE_EXCLUDED_RECENCY` (`technique_pacing_drills`, `technique_relaxation_drills`, `technique_route_reading`, `technique_lead_specific`).
- **Try-hard**: a session containing `fall_practice` (a limit session alone no longer counts — A294 review), an outdoor-hard day or a free limit session.
- **`sessions[]`** (roles, NOT inside the week plan): `{date, slot, session_id, status, role, keys[], supporting[], downgraded_from?}`; `role`: `key` (the minimal set covering the target: done-full first, catalog before custom, `propose` order, date) | `supporting` | `optional` (finger-hard supporting session in a re-entry week: < 2 exposures of the family in 21 days) | `skipped` | `downgraded`.
- **`proposals[]`** (current week only, at most one finger-hard catch-up): `{keys[], date, slot, session_id, session_name, location, gym_id, reduced_reentry_dose, side_effects[{date, slot, from, to, reason}], checks, apply: {endpoint: "/api/replanner/events", event: {event_type: "add_planned_session", ...}}}`. Validated by applying the event on a copy through `apply_events` (prev_days seeded): rejected when the added session is downshifted or a key / custom / forced / done / skipped session changes; any other change is a declared side effect. Candidate days skip the past, outdoor days, pretrip / other-activity days and the day the stimulus was skipped; finger gap on the unified timeline (plan + outdoor + free, next week included); no hard/finger work within 72 h before a pending `test_max_*`. `strength_long` covers `finger_max` + `pulling_max` together. Re-entry: `power_contact_gym` (campus) is never proposed. A294 review: a pending test later the same day blocks too; heavy pulling rules (`_heavy_pull_clash`, pulling_max family read as heavy by `retest_policy`): no heavy pull within 24 h before a limit / strength_long session (and no limit candidate after one), at most `MAX_HEAVY_PULL_7D` (2) in any 7 days — rejection reasons `heavy_pull_before_limit` | `heavy_pull_cap`, `checks.heavy_pulling_ok`; proposals are validated **cumulatively** (each on the plan with the earlier ones applied; later ones carry `assumes[{date, slot, session_id}]`); candidates outside the planner's session pool are allowed after the in-pool ones (PE limit, deload technique).
- **`conflicts[]`** (warnings, never blocks): `key_downgraded` (high) | `pre_test_fatigue` (high) | `finger_gap` (medium) | `pulling_overlap` (medium: heavy pull within 24 h before a limit / strength_long key).
- **`check_insertion(state, today, plan=, events=, ...)`** → `/api/replanner/events` with `dry_run: true` (+ `custom_session_payload` for a custom that does not exist yet): `{week_plan, adjustments, key_status, key_conflicts}`, nothing written. `key_conflicts[].code`: `key_removed` (high; `replace_key`, `partial_replacement`) | `key_replaced` (medium; the insertion delivers the same stimulus, `replace_key: true`) | `test_downgraded` (high) | `pre_test_fatigue` (high) | `finger_gap` (high since the A294 review — read on the plan after the insertion, so it is a finger-hard day the reconcile could not move; the app asks for a confirm).
- **`composer_guard(state, target_date)`** (coach, A259 extension): `{exclude_ids[], warnings[{code: near_finger_key | pre_test, message}]}` — a finger key within the recovery gap counts whether done or pending, the same day included (A294 review); the composer pool and `adhoc_builder` drop `intent.key_guard_exclude_ids`; the preview carries `key_warnings`. `POST /api/coach/adhoc-session` accepts `target_date`. Env `COACH_ATHLETE_CONTEXT` (default on; only `0` disables) is owned by A297 (below).
- **`COACH_ATHLETE_CONTEXT`** (env, A297): default on, only the literal `0` disables, read at call time. On: the coach chat prompt carries ONE `## Athlete context` block (`athlete_context.render_coach_block`) instead of the A294 key block and the B364 baseline lines, and the ad-hoc composer / builder read the athlete context of the session day. Off: everything as before A297, byte for byte.
- **`athlete_context` A297 additions** (`version: "a297.1"`): `guards.days[].finger_codes|pull_codes|hiit_codes` — `[{code, detail}]`, codes `finger_hard_adjacent | finger_spacing | hang_test_soon | heavy_pull_week | pre_limit | pull_test_soon | deload | hard_cap | max_session_adjacent` (one per Italian reason); `variety.exercise_last_date` `{exercise_id: YYYY-MM-DD}`; `load_flags {pain: {axis: block}, fatigue: {axis: …}}` (A295 / B364 helpers); `limit_log[]` (newest 4 A296 entries, summarised: problems, sent, best_sent, next_target_grade…). Renderers `render_coach_block(ctx)` (≤ 3 500 chars) and `render_composer_block(ctx, state=, day=)` (≤ 2 500 chars), English and neutral.
- **`composer_guard_view(state, ctx, day, catalog)`** (A297): `{day, finger_max_ok, heavy_pull_ok, hiit_ok, exclude_ids[], builder_exclude_ids[], heavy_pull_check, dropped[], reasons{finger?, pull?}, pain_axes[]}` — pool exclusions from the day's guards (finger_max + limit_power + finger-fatigue hangs + `intensity_level: max` finger exercises; front-lever variants + `intensity_level: max` pulling exercises; for the builder also weighted pulls ≥ 85 % 1RM at the catalog scheme). An active A295 pain block (score ≥ 2) on an axis sets that axis to not-ok and is listed in `pain_axes` (`finger` | `pulling`), even outside the guard horizon. `athlete_is_tested(ctx)`: at least one tested (< 90 d) official max — only then the intensity ranking, the `intensity=` pool markers and `MAX_FINGER_HARD_PER_SESSION` (2; `_LOW_ENERGY` 1, enforced by the builder and by `cap_finger_hard` on the LLM path) apply; an untested athlete keeps the pre-A297 builder selection. `drop_heavy_pulls(state, exercises, view)` re-checks composed weighted pulls at their own reps (untested → not verifiable, kept).
- **Ad-hoc preview payload, A297 (additive, optional):** `athlete_context_version`, `athlete_guards {day, finger_max_ok, heavy_pull_ok, hiit_ok, reasons}`, `dropped[]` (now also on the deterministic builder, guard lines prefixed `guard:`), `effort_band` from `effort_band_for(phase, energy, guards)`.
- **Replanner additive fields (persisted):** session `downshifted_from` (reconcile / ripple / protected-neighbour / adaptive replan downgrade); `mark_skipped` stub `skipped_session_id` + `skipped_tags`; adaptation `{type: "reconcile", adjustments}` (only when non-empty); constraint `key_reschedule` on sessions added by `add_planned_session`. `apply_events(..., prev_days=, today=)` — `today` (A294 review) freezes every day before it for the final reconcile (`_reconcile(frozen_before=)`): a past session not ticked yet still constrains, never gets rewritten; `POST /api/replanner/events` passes the client-local day. `OverrideRequest.today` / `QuickAddRequest.today`: client-local day for the returned `key_status`. `session_completion_log[].session_id` now comes from the session the event hit when the event had no `session_ref`.

### 4.8 Bodyweight progression — closed loop on the ladders (A298)

`backend/engine/bw_progression.py` — pure except the four writers (`apply_bw_item`, `apply_technique_measures`, `set_level`, `resolve_promotion`), the only time input is the session date (`ref_date`). Ladders: `backend/catalog/progressions/v1/bw_ladders.json` (C272, `level_idx` from 0).

- **State `user_state.bw_progression`** (top level, own key — never `working_loads.entries`; in the PUT `/api/state` allowlist, default `{}`, validated as an object on import): `{<family>: entry, "technique": {feet|falls: tech_entry}}`. Entry: `{family, exercise_id, level_idx, axis: reps|seconds, sets, target, tempo_level, added_kg, top_streak, vh_streak, pending_promotion: {to_level_idx, exercise_id, target?, since} | null, ramp?: {sessions_left, then_level, then_target}, last_session_date, source: seed_history|seed_test|feedback|user_edit, seeded_from?, last_outcome: {kind, message, date}, _prev: {session_key, entry}}` (`_prev` = pre-session snapshot: resubmitting the same `date|session_id` replays from it, B197). Tech entry: `{level: P1..P4 | F1..F3, good_streak, bad_streak, last_value, last_session_date, tracked, _prev}`. Official maxima are never written (R9).
- **Seed at read** (`entries_for`): persisted entry, else `bw_ladders.seed_levels` (history: last clean dose − 1 step; else the L-sit test log < 90 d). **Tested athletes only** (`bw_ladders.tested_gate`): untested → `{}` and every consumer is a no-op. A seed is persisted only by the first feedback that moves it.
- **Label steps** (`LABEL_STEPS`): `very_easy +2`, `easy +1`, `ok 0`, `hard −1`, `very_hard −2` band steps — never a level jump. Not rated (A295: no label, legacy `ok`) and no measure → entry unchanged (R3). Skipped (completed false, nothing else) → unchanged.
- **Measures** (R0, the measure is the base, the label the delta): `last_set_reps` (reps axis: clean reps on the weakest set), `held_s` (seconds axis: seconds held on the weakest set; a hold stopped at the target counts as the target; `held_to_failure` → × `TEST_HOLD_FACTOR` 0.80). Client measure kinds `bw_reps` / `bw_hold` (only on the row at the athlete's level).
- **R1** very_hard (or not completed with an answer): tempo off first, then −10 % added kg (min the distal step / 1 kg), else −2 steps; level −1 (at `hi − step`) after `VH_STREAK_LEVEL_DOWN` = 2 consecutive very_hard or a failure already at `lo`; never below `floor_level_advanced` (→ `floor_warning`).
- **R6 promotion**: a session PERFORMED at the top of the band (target already at `hi`, or a measure ≥ `hi`, or at the R10 cap) whose projection passes it → `top_streak + 1` (target stays at `hi`); a projection past the top from below (very_easy one step under, measure + label) only reaches `hi`, streak 0 (R5: no level jump); at `advance_sessions` (1, 2 on risky levels: FL from advanced tuck, dragon flag, standing rollout, Copenhagen long, ring dip, one-arm) → next level at `lo`. In a custom `ladder` row → `pending_promotion` (the tap applies it). **R7 terminal**: `tempo` (3 s → 5 s eccentric, target restarts `hi − 2 steps` = `TERMINAL_RESTART_STEPS`) then `load` (distal 1 kg / upper 2.5 / lower 5) | `load` | `handoff` (message only) | `cap` (front lever: raise / row, never added kg). When the family names a `handoff_exercise_id` (compression_floor → weighted_l_sit, lateral → weighted_side_plank, posterior_chain → back_extension, push_horizontal → weighted_pushup, compression_hang after its tempo steps → weighted_hanging_leg_raise) a `load` terminal is a **handoff** (outcome `{kind: handoff, handoff_exercise_id, start_kg}`, message "move on to X, start at +N kg"): kg are never piled onto the last bodyweight level. Only a family without a named variant (single_leg_squat) adds kg; the dose then carries `tempo_ecc_s` / `added_kg` into `prescription.tempo` / `prescription.load_kg` (engine) and `tempo` / `load_kg` (custom ladder rows, stored value in `stored_load_kg`).
- **R-PHASE** (`FROZEN_PHASES` = performance, deload): no promotion, no tempo/load/target step up, dose −1 set (min 2); regressions stay. **R11 re-entry**: gap > 120 d (60 d skill families) since `last_session_date` → level −1 at `lo` (read and feedback). A custom `ladder` row saved at the stored level keeps that level at `lo` of its band (`reentry_at_stored_level`, `ladder.reentry.kept_level`), and its feedback is applied — otherwise the row sat "above level" and the family froze. **R12**: levels ≥ `lower_back_risk_from_level` are never assigned or promoted to by the engine (`auto_ceiling`; no `lower_back` limitation zone exists yet → `has_lower_back_zone` False) — only `PUT /api/bw-progression/{family}`. An entry above the ceiling with source `user_edit` / `feedback` (`MANUAL_SOURCES`: the athlete put it there) is honoured by the resolver stage; seeds are capped.
- **Feedback routing**: the ladder branch of `apply_feedback` runs for every ladder level, whatever its load model — four levels are `external_load` (back_extension, pallof_press, pallof_press_standing_pause, weighted_hollow_hold): their level moves and the item then falls through to its kg branch. The history seed used by the first feedback of a family excludes the session being logged (`entries_for(exclude_session_key=…)`, `bw_ladders.seed_levels(exclude_sessions=…)`). The dose source tag `bw_ladder` (`engine | ladder | fixed`) comes from the client (guided player / dialog: `prescription.source == "bw_ladder"` → `engine`, because an unplayed planned session is not cached server-side), else from `log_entry.planned`, the stored plan or the custom definition; unknown values are dropped. A rated `ok` answers "Same dose next time: …"; "Not rated" only when no label and no measure came back.
- **Recovery sessions** (`is_recovery_session`: `intent.primary_goal` regeneration / recovery / flexibility / mobility, or `phase_tags` deload): no ladder stage — catalog pick and dose (technique measures only).
- **Outcome kinds** (`OUTCOME_KINDS`): `hold | step_up | step_down | promoted | promotion_proposed | top_streak | frozen | manual_only | tempo_up | load_up | tempo_down | load_down | level_down | floor_warning | handoff | cap | ramp | reentry`; `POST /api/feedback` returns `bw_ladder_updates[] {family, exercise_id, kind, message, date}` (toast).
- **Resolver stage** (`resolve_session._bw_ladder_stage`, after P0 and the A290 rotation, template and inline blocks, P0 picks only — pins untouched): an engine pick on a ladder family is replaced by the athlete's level (capped by R12), then lower levels, first that passes every block filter (`_bw_candidate_ok`: location, equipment, age, experience, role — a `ladder`-role level counts as the block's role —, intensity_max, active/severe contraindications, domain, pattern, phase_affinity). The original pick, when it is one of those levels, always passes; none → the pick, no dose. A mastered lower level gets the top of its band. Dose in `prescription` (`sets`, `reps`|`work_seconds`, `rest_between_sets_seconds`, `tempo`, `added_load_kg`, `source: "bw_ladder"`, `*_range` removed); audit in `suggested.bw_ladder {ladder, dose}`, `suggested.measure`. One family per session (second block keeps its pick). Untested: `build_resolve_context` → `None`, bit for bit.
- **Custom rows** (`progress_mode: ladder | fixed`, stored only when set; missing = `fixed`, i.e. every row saved before A298; the builder defaults new ladder rows to `ladder`): `resolve_custom_ladder_rows` on `GET /api/custom-session/{id}?date=` and the custom slots of `GET /api/week` — dose of the day (stored values in `stored_sets|stored_reps|stored_work_seconds`), `progress_source: "bw_ladder"`, `ladder {family, family_label, level_idx, n_levels, level_name, band, dose, next_exercise_id, next_name, frozen, manual_only_next, gate, proposal: {kind: promotion|switch, to_level_idx, to_exercise_id, to_name} | null, entry_level_idx, above_level?, source}`. `switch` = the row sits below the athlete's level. Feedback context (`attach_feedback_context`, router): item `bw_ladder: engine | ladder | fixed` — a `fixed` row moves the memory only with the ladder's dose (`prescribed_sets` + reps/seconds) or a measure; a row on another level never does.
- **Endpoints**: `GET /api/bw-progression?date=` (view: families, dose, pending promotion, last outcome, technique), `PUT /api/bw-progression/{family}` `{level_idx, confirm?, date?}` (source `user_edit`; > current + 1 needs `confirm`, else 409), `POST /api/bw-progression/{family}/promotion` `{accept, date?, custom_session_id?}` (accept: entry up + 'ladder' rows of that family below the new level rewritten in the custom session and its not-yet-played slots from `date`; decline: proposal and top streak cleared).
- **Front lever = heavy pull** (DECISIONS): `key_sessions_v1._is_heavy_pull` and the `pulling_overlap` conflict count any ladder heavy-pull id (`bw_ladders.heavy_pull_exercise_ids`) for a tested athlete.
- **Technique ladders (minimal)**: measure kinds `feet_readjust` (field `sample_readjust`, 0-30, on the feet-ladder drills) and `fear_max` (0-10, on `fall_ladder`), asked of tested athletes only, one number per session (min readjustments / max fear). Feet: only the drills of the athlete's CURRENT level carry and feed the measure (`current_feet_drills`; the "benchmark B1 stable" half of the advance criterion is not checked — no benchmark logging yet). Feet: ≤ `FEET_GOOD_MAX` 1 twice → up, ≥ `FEET_BAD_MIN` 3 twice → down. Falls: ≤ `FEAR_GOOD_MAX` 3 twice → up, one ≥ `FEAR_BAD_MIN` 7 → down. Positions (hover x/5) not tracked.
- **ENGINEERING CONSTANTS**: `TEST_HOLD_FACTOR` 0.80, `LOAD_DOWN_PCT` 0.10, `TERMINAL_RESTART_STEPS` 2, `VH_STREAK_LEVEL_DOWN` 2, `FROZEN_MIN_SETS` 2, the technique thresholds above, caps 30 reps / 60 s (`bw_ladders.json` `caps`).
- **Migration** `scripts/migrate_bw_ladders.py` (dry-run default): prints the level of every family; sets `progress_mode: ladder` on the ladder rows without a mode of tested users' customs and their not-yet-played slots.

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

### 3.4 Rotation class (A290)

Top-level keys of a template block or an inline session module — **never inside
`selection`** (catalog test). Read only for athletes with a tested baseline
(`backend/engine/phase_anchor.py`, `docs/ENGINE_ARCHITECTURE.md` §6.1).

- `rotation` (closed set): `phase_anchor` (fixed for the phase) | `ab` (stable A/B
  alternation) | absent = `free` (pre-A290 selection).
- `anchor_axis`: `finger` | `pulling` — which tested level picks the list.
- `anchor_priority`: `[ids]` (axis-free) or `{tested: [ids], untested: [ids]}`.
- `anchor_priority_by_phase`: `{phase_id: {tested?, untested?, anchor_exclude?, tested_prescription_overrides?}}`.
- `anchor_exclude`: `{tested?: [ids], untested?: [ids]}` (soft: ignored if it would empty the block).
- `heavy_slot`: `true` on the weighted-pull blocks (weekly heavy-pull slot).
- `ab_pool`: `[ids]` preferred A/B pool; `unloaded_only`: `true` → no `total_load` / `external_load` exercise.
- `rotation_exclude`: `[ids]` soft exclusion for athletes above a tested threshold on either axis (core floor: plank, dead_bug, plank_shoulder_tap).
- `spacing_step_down`: `{domain: [..], pattern: [..], priority: [ids], prescription_overrides?}` — the sub-maximal
  selection used after a max-hang exposure < 72 h (finger_max_strength main). Max-load finger exercises are a hard
  exclusion there; the block prescription is dropped.

Trace `blocks[].p0_trace.rotation.spacing_downgrade` (closed set):
`not_heavy_occurrence` | `heavy_pull_48h` | `heavy_pull_7d_cap` | `pre_limit_24h` | `max_hang_72h`.
`anchor_list`: `tested` | `untested` | `spacing`. `ab_slot`: `A` | `B`.
`pre_limit_source`: `plan` | `weekday_proxy` (no plan covers tomorrow: same weekday of the target's week).

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

### 5.7.1 Replanner adjustments (B287/R-5, B366)

```
Adjustment: { date, slot, action: "downgraded", reason, previous_session_id, session_id }
  reason ∈ finger_spacing_downshift | hard_cap_downshift        (reconcile, B287)
         | quick_add_ripple                                     (quick-add day+1, B366)
         | recovery_ripple_proportional | recovery_ripple       (hard override day+1 / day+2, B366)
         | outdoor_ripple                                       (completed outdoor ≥ 65 load, day+1, B366)
  reason always equals the constraints_applied value stamped on the rewritten session.
```

Where they surface: `POST /api/replanner/quick-add` → `adjustments[]` + `warnings[]` (reconcile first, ripple last);
`POST /api/replanner/override` → `adjustments[]` + `warnings[]` (additive, B366 review: the override's own
reconcile downshifts first, then the ripple); `week_plan.adaptations[]` → `{type: "quick_add", adjustments}`,
`{type: "day_override", …, adjustments, warnings}`, `{type: "outdoor_ripple", date, adjustments, kept_protected?}`
(only when something was rewritten or kept). `kept_protected: [{date, slot, session_id}]` names the hard/finger
custom or forced sessions on day+1 the outdoor ripple had to leave in place.
A ripple never rewrites done/skipped, `forced` or `is_custom` sessions (`_is_rewritable`). Since it spares
them, `_protected_neighbor_guard` checks the added/overriding session against them instead: a non-skipped
protected finger session within `_recovery_gap` days AFTER it downshifts the added session
(`finger_spacing_downshift`, unless it was forced); a protected hard session on day+1 adds the warning
"Back-to-back hard days: …" (no rewrite — no rule forbids back-to-back hard days).

### 5.7.2 User-owned sessions and stale weeks (B369)

```
is_user_owned(session)    (backend/engine/user_owned.py — the ONE predicate of every regeneration path)
  = forced | is_custom | _user_edited
    | constraints_applied ∩ {quick_add, user_forced, manual_override, key_reschedule,
                             custom_add, generated_add, user_moved} ≠ ∅
is_preservable(session)   = status ∈ {done, skipped} | is_user_owned(session)
```

- **`user_moved`** (constraint, B369): stamped by `move_session` on the moved session. The logged event gains
  `moved_session_id` (what left the source slot).
- **`day_override.whole_day`** (adaptation, B369): `true` when the override replaced every session of the day.
- **`day_override.replaced_slots`** (adaptation, B369 review): whole-day override → the slots the day held at
  override time (a slot added later by a new structure still gets the engine's session).
  **`replaced_session_id` / `replaced_slot`**: partial override (`session_index`) → the one session it replaced.
  A partial override with no `slot` in the request takes the replaced session's slot (`OverrideRequest.slot` is
  now optional; whole-day default stays `evening`).
- **`move_session` event `replaced_session_id`** (B369 review): the session the move overwrote in the target slot.
- **User removals** = `adaptations[]` events `remove_session` (`date`, `session_ref`/`slot`), the source side of
  `move_session` (`from_date`, `session_ref` or `moved_session_id`, `from_slot`) and its `replaced_session_id` at
  `to_date`/`to_slot`, `day_override` `replaced_session_id`/`replaced_slot` and `replaced_slots`, and the whole
  date for an outdoor override or a pre-review `whole_day` one without `replaced_slots`. Read by
  `user_owned.removed_refs` / `whole_day_override_dates`; the merge carries `adaptations[]` forward so the next
  regeneration still honours them. An engine session leaves a regenerated day only through a removal: a slot
  shared by a user session and an engine session keeps both; a slot the user's session took over (skip stub,
  done, edit) does not get the engine's session back.
- **`regeneration_guard_warnings`** (adaptation, B369 review): `{type, warnings: [{date, slot, action:
  "guard_alert", reason: finger_spacing_downshift | hard_cap_downshift, previous_session_id, session_id}]}` —
  what the guards would downshift in a regenerated week once the merge put the user's sessions back. Alert
  only, nothing rewritten; recomputed at each regeneration (never piled up); absent for a week without user
  sessions.
- **Ownership markers survive guard rewrites** (B369 review): reconcile / ripple / protected-neighbour rewrites
  keep the user markers in `constraints_applied` (`user_owned.carry_user_markers`), so a rewritten user session
  is still kept by the next regeneration; finger compensation never swaps out a user-owned session.
- **`_stale`** (week plan flag, B369): set by `deps.mark_weeks_stale` on the cached current/future weeks (never a
  past week) by `invalidate_week_cache` (macrocycle generate, onboarding, start-week, test-reminder confirm),
  `PUT /api/state` when `availability` / `planning_prefs` / `weekly_overrides` actually change,
  `PUT`/`DELETE /api/weekly-override/{week}` (that week only), `start-new-cycle` (weeks ≥ the new start) and
  resume (weeks ≥ this Monday). The current week's frozen floor is `max(preserve_before, client today)` — the
  client cannot lower it below its own today (B369 review). `weekly_load_summary.planned_load` is restored from
  the old plan only when the regeneration skipped days of the week. `GET /api/week` regenerates a stale week through
  `regenerate_preserving_completed` and saves it without the flag; `persist_week_plan` keeps the flag on an edit.
  Replaces the deletions and the `_prev_week_plan` stash (no longer written; a legacy stash is merged only when it
  is the same week, else discarded).
- **`regeneration_failed: true`** (GET `/api/week` response, additive): the regeneration or the merge raised —
  the cached plan is served unchanged, nothing is saved, the week stays stale.
- **Resume response:** `weeks_marked_stale` (new); `weeks_shifted` / `weeks_dropped` kept, always 0.
- **`adaptive_suggestion`** (`POST /api/feedback` response, additive, B369): `{kind: lighten_next_hard |
  recovery_day, target_date, reason, plan_changed: false, message, session_id?, session_name?, user_owned?}`.
  The adaptive replan after very_hard/fail no longer changes the plan; `apply_adaptive_replan` is gone and no
  `{type: "adaptive_replan"}` adaptation is written any more.
- **`plan_revision`** after a merge = `max(old, new) + 1` (monotonic across regenerations).

### 5.7.3 Slot roles and complementary rotation (A300)

```
availability.<weekday>.<slot>  (all optional; absent ⇒ planner byte-identical to pre-A300)
  role:         "primary" | "complementary" | "any"        (default "any")
  max_minutes:  int 10..240 — sessions whose catalog time_budget.hard_cap_min
                (else target_duration_min) is longer never go on this slot (every pass)
  focus:        FocusFamily — pins the family of a complementary slot

planning_prefs
  complementary_rotation:           list[FocusFamily]   (default legs, hiit, z2, upper_push_arms)
  complementary_rotation_by_phase:  { phase_id: list[FocusFamily] }  (replaces the rotation of that phase)

FocusFamily → catalog sessions (first that fits slot equipment, max_minutes, max_per_week)
  legs             legs_maintenance_lunch | legs_strength | lower_body_gym
  hiit             treadmill_hiit_4x4
  z2               treadmill_zone2_cardio
  upper_push_arms  upper_push_arms_lunch (carries the biceps curl) | upper_body_weights
Phase variant (default): deload → hiit becomes z2.
```

- **`complementary`** slots are invisible to every placement pass of `planner_v2` (PASS 1/1.5/2/2.2/2.5/2.6/3a/3,
  test week) and to the A294 re-schedule proposals (`planner_v2._primary_view`): primaries, quality floors,
  tests and substitutions never land there. They are filled last (after the deload transform) by
  `complementary_v1.place_complementary`, one session per slot, with their own budget — outside
  `target_training_days_per_week`, the target-days pruning, the hard cap and the deload 5-session cap.
  `primary` / `any` slots are used by the primary passes exactly as before; the complementary pass never uses them.
- **Adaptive pairing** family ↔ slot, by minimum penalty over the week's actual primaries **and the user's own
  sessions** (ties → rotation order, deterministic; the catalog `max_per_week` is counted along each pairing):
  HIIT not the same day as / the day before a max day (finger-hard, pulling-hard, test, `intensity: max`) or an
  outdoor day (outdoor slot, day-level `outdoor_spot_*` / `outdoor_plan` / `outdoor_session_status`, trip
  departure); HIIT and legs not on a pre-trip no-hard day; at most **1 HIIT/week** (`stimulus.is_hiit_like`; HIIT is `hard: false`, never consumes
  the hard-day cap); biceps not within 24 h before a heavy pull (`is_pulling_hard_session`); legs not within
  48 h before a limit session (`limit_power` or max-intensity climbing on a wall) or an outdoor day; Z2
  anywhere. Time model: morning 08:00, lunch 13:00, evening 19:00, outdoor day from 08:00.
- **Penalties, never blocks.** Generated session fields: `slot_role: "complementary"`, `focus`, explain
  `pass_complementary:a300`. Week plan fields (only when a complementary slot exists):
  `secondary_warnings: [{date, slot, session_id, focus, code, with}]` with
  `code ∈ hiit_near_max | biceps_before_heavy_pull | legs_before_limit | hiit_weekly_cap | pretrip_no_hard`, and
  `unmet_secondary: [{date, slot, focus, reason, candidates?}]` with
  `reason ∈ no_focus | rotation_exhausted | no_session_fits | rotation_overflow` (`rotation_overflow`: a family
  of the week's rotation with no slot left, `date`/`slot` null). Warnings cover the engine lunches and every
  user-owned session of a family (custom "Work — HIIT", forced, moved) — alerts only; done/skipped are history.
  A pinned `focus` ignores the catalog `max_per_week` (user decision → `hiit_weekly_cap` alert).
- **Regeneration** (`generate_phase_week(existing_week_plan=…)`, GET `/api/week` passes the cached plan on
  force / stale): the week is read as the B369 merge will put it back. Lived days (before `today`, or `today`
  with a done session) count what is there; on the other days every preservable session (`is_preservable`)
  stays, and a complementary slot holding one, or emptied by the user (`user_owned.removal_records`:
  `removed` / `replaced` consume the family, `moved` is counted where it landed; a whole-day override), is
  **never refilled**. A skip stub counts as the session it replaced (`skipped_original` /
  `skipped_session_id`) — consumed, not a HIIT done. Families and HIITs found there count toward the week.
- **Beyond the week**: `trip_start_dates` (`complementary_v1.trip_start_dates(trips, week_start)`, departures up
  to the Tuesday after) and `next_week_plan` (its first two days) feed the rules.
- **Alerts after edits**: `complementary_v1.refresh_secondary_warnings(week_plan, state)` recomputes
  `secondary_warnings` on the stored week — after the B369 merge in GET `/api/week` and in
  `persist_week_plan` (move, quick-add, key re-schedule, feedback…). No-op for a week without the key.
- **HIIT single source** (`stimulus.is_hiit_like`): catalog `tags.hiit` / `conditioning_hiit` exercises
  (`is_hiit_session`), the `HIIT|VO2` name regex only for legacy customs without an explicit `tags.hiit`.
  Used by the complementary pass and by `athlete_context` (`hiit` of a session view, `HIIT_ON_GUARD_DAY`).
- **Validation**: `PUT /api/state` and `POST /api/onboarding/complete` answer 422 on an unknown `role` /
  `focus`, an out-of-range `max_minutes` or an unknown family/phase in the rotation
  (`complementary_v1.validate_structure`). A weekly override of a slot keeps its `role` / `max_minutes` / `focus`.

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
- `mobility` — guided stretching/release session (A230, requires surface `mobility_stretching`)

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

Note: `repeat` is NOT a valid free-session `climb_style` (`VALID_CLIMB_STYLES` in `free_session.py` rejects it). It exists only for outdoor route logging (`outdoor_log.py`).

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

Non-climbing add-on surfaces (non-circuit):
- `mobility_stretching` — Stretching & Mobility pool (A230, session_mode `mobility`; superseded the planned `circuit_stretching`)

Future (not in v1):
- `circuit_warmup` — dynamic warmup circuit
- `circuit_cardio` — bodyweight cardio circuit

### 6.10 Session mode (updated)

Allowed `session_mode` values:
- `template` — user selected a preset
- `free` — no structure, only phase tip
- `circuit` — timer-guided exercise circuit
- `mobility` — guided stretching/release session (A230)
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

### 6.14 Mobility pool vocabulary (A230)

Catalog: `backend/catalog/mobility/v1/mobility.json` — separate from `exercises.json` by design; never reachable by the climbing-session resolver.

`body_region` (11 values, picker sort order):
`forearms_wrists` → `hips_glutes` → `chest_anterior_shoulder` → `thoracic_spine` → `hip_flexors_quads` → `adductors_groin` → `lats` → `shoulders_scapula` → `hamstrings` → `calves_ankles` → `spine_rotation_obliques`

`mode`:
- `timed_hold` — countdown from `prescription_defaults.work_seconds` (editable when `hold_seconds_editable`)
- `untimed_release` — guided self-massage/pin-and-stretch, open stopwatch, no forced countdown

`type` (informational): `static` | `release` | `flow`

`priority`: `high` | `medium` | `low` (within-region sort: `untimed_release` first, then holds by priority)

Flags:
- `unilateral` — per-side entry; mandates `rest_between_reps_seconds: 10` (L→R transition)
- `pre_performance_blocked` — GATE-2: soft warning in `/pool`; **excluded** from `/generate` flows when a session is still planned the same day (when the system picks, it picks safely — A231)
- `ux_flow` — continuous breath-paced movement ("slow flow" copy), not a fixed hold
- `pnf_capable` — PNF-suitable (flag only in v1, no PNF UI)
- `kb_validated` — `false` = pending literature validation at next KB refresh

`recency_group` convention: `mobility_<body_region>`.

Guided flow generation (`/api/mobility/generate`, A231):
- `pace`: `quick` (holds ×0.7) | `standard` (×1.0) | `deep` (×1.4); holds rounded to 5s, min 10s
- `minutes`: 5–45 (hard fit — total never exceeds the budget); `rest`: 5–30s between steps
- Selection: round-robin by rank across selected regions (picker order), each region's list pre-sorted releases-first then priority — deterministic, same inputs → same flow
- `untimed_release` entries get a timed slot (45s base × pace) inside generated flows; the runner lets the user skip ahead early
