# D164 — Exercise Catalog Audit

**Date:** 2026-03-27
**Scope:** `backend/catalog/exercises/v1/exercises.json` (v2.1, 185 exercises), `docs/vocabulary_v1.md`
**Type:** READ-ONLY audit. No files modified.

---

## 1. Schema Compliance

**Required fields:** `id`, `name`, `category`, `role` (array), `domain` (array), `description`, `cues` (array), `prescription_defaults` (object).

**Result: PASS** — All 185 exercises have all required fields with correct types.

No missing fields, no type violations (role/domain/cues are arrays, prescription_defaults is object in all cases).

---

## 2. Vocabulary Compliance

### P1 — Unknown values

| Exercise | Field | Invalid Value | Note |
|----------|-------|---------------|------|
| `fall_practice` | `equipment_required_any` | `lead_wall` | Not in vocabulary_v1.md. Should be `gym_routes` or new canonical ID |
| `grip_transitions_half_to_open` | `pattern` | `grip_transition` | Not in vocabulary_v1.md pattern list. Needs addition to vocabulary or remapping |

### P2 — Non-canonical contraindications

| Exercise(s) | Value | Note |
|-------------|-------|------|
| All 10 campus exercises | `age_under_16` | Not in vocabulary_v1.md contraindication list (valid values: `elbow_sensitive`, `elbow_injury`, `finger_sensitive`, `finger_injury`, `shoulder_sensitive`, `wrist_sensitive`, `knee_injury`). The age gate is enforced via `age_minimum` field instead; `age_under_16` in contraindications is redundant and non-canonical |

**Affected campus exercises:** `pangullich_ladders_easy`, `campus_laddering_feet_off`, `campus_laddering_feet_on`, `campus_bumps`, `campus_double_dyno`, `campus_touches`, `campus_max_ladders`, `campus_switches`, `campus_sprint_endurance`, `campus_laddering_down`

**Action needed:** Either add `age_under_16` to vocabulary_v1.md section 2.9.1 or remove it from contraindications (since `age_minimum: 16` already enforces the gate).

---

## 3. Video URL Validation

**96 exercises** have a `video_url` (51.9%). **41 unique URLs** tested.

### 404 Errors (8 unique URLs, 22 exercises affected)

| HTTP | URL | Exercises Affected |
|------|-----|--------------------|
| 404 | `https://www.hoopersbeta.com/library/footwork-drills` | `gym_technique_boulder_drills` |
| 404 | `https://www.hoopersbeta.com/library/pull-ups-for-climbers` | `chinup`, `band_assisted_pullup` |
| 404 | `https://trainingforclimbing.com/the-best-climbing-exercise-youre-not-doing/` | `scapular_pullup` |
| 404 | `https://www.hoopersbeta.com/library/antagonist-training` | `inverted_row`, `pushup`, `pike_pushup`, `bench_press`, `overhead_press`, `barbell_row`, `ring_pushup` |
| 404 | `https://www.hoopersbeta.com/library/shoulder-mobility-for-climbers` | `mobility_thoracic_shoulders_flow`, `shoulder_stretch_flow`, `cooldown_shoulder_chest`, `lat_overhead_stretch` |
| 404 | `https://www.hoopersbeta.com/library/forearm-stretching` | `forearm_stretches`, `cooldown_forearm_wrist_stretch` |
| 404 | `https://www.hoopersbeta.com/library/flexibility-for-climbers` | `full_body_stretch_flow` |
| 404 | `https://www.hoopersbeta.com/library/hip-mobility-for-climbers` | `active_hip_mobility`, `cooldown_deep_squat_hold` |

**P2** — All 7 `hoopersbeta.com/library/*` subpath URLs return 404. The site has likely restructured. The generic `https://www.hoopersbeta.com/library` (no subpath) returns 200, but 11 exercises point to it as a placeholder — not useful as exercise-specific video reference.

**P2** — `trainingforclimbing.com` has 1 broken URL (`the-best-climbing-exercise-youre-not-doing`).

### Generic placeholder URLs (P3)

11 exercises point to `https://www.hoopersbeta.com/library` (generic library page, no exercise-specific content):
`slow_climbing`, `flag_practice`, `breathing_awareness`, `hip_rotation_drill`, `hover_hands`, `one_hand_climbing`, `sloth_monkey`, `straight_arms`, `tap_and_place`, `three_limb_drill`, `heel_hook_specific_drill`

---

## 4. Cue Quality

| Severity | Exercise | Issue |
|----------|----------|-------|
| **P2** | `finger_warmup_generic` | 0 cues (empty array) |

No cues duplicate their exercise description. No very short cues found (<10 chars).

**Result:** 184/185 exercises have cues. Only 1 exercise has zero cues.

---

## 5. Description Quality

| Severity | Exercise | Issue |
|----------|----------|-------|
| **P2** | `finger_warmup_generic` | Description is `null` |

No short descriptions (<20 chars) found. 184/185 exercises have substantive descriptions.

---

## 6. Duplicate Detection

### Identical names: None found.

### Identical prescription_defaults (P3, informational):

| Group | Exercises | Likely Intentional? |
|-------|-----------|---------------------|
| Max hang variants | `max_hang_5s` + `lp_max_lift_5s`, `max_hang_7s` + `lp_max_lift_7s`, `max_hang_10s` + `lp_max_lift_10s` | Yes — hangboard/loading_pin equivalents |
| Technique drills | `freeze_drill` + `twist_lock_drill` | Probably OK — same drill structure |
| Push variants | `pushup` + `goblet_squat`, `pike_pushup` + `overhead_press` | Coincidental — different exercises |
| Pull variants | `split_squat` + `scapular_pullup` | Coincidental — different exercises |

No action needed. Shared prescriptions are either intentional (LP/hangboard pairs) or coincidental (different exercises that happen to share sets/reps).

---

## 7. Orphan Detection

**Result: PASS** — All 185 exercises are reachable by at least one session/module template block filter or explicit `exercise_id` reference.

- 35 session templates, 27 module templates scanned
- 26 explicit `exercise_id` references found
- 64 filter combinations extracted
- 0 orphans

---

## 8. Equipment Consistency

**2 issues found** (see section 2):

| Severity | Exercise | Field | Value | Issue |
|----------|----------|-------|-------|-------|
| **P1** | `fall_practice` | `equipment_required_any` | `lead_wall` | Not a canonical equipment ID |
| OK | All others | `equipment_required` / `equipment_required_any` | — | All values in vocabulary |

---

## 9. Campus Gates (B159a)

**Result: PASS** — All 10 campus exercises have both `experience_minimum_years` and `age_minimum` fields.

| Exercise | experience_minimum_years | age_minimum | intensity_level |
|----------|------------------------|-------------|-----------------|
| `campus_laddering_feet_on` | 1 | 16 | high |
| `campus_touches` | 1 | 16 | high |
| `pangullich_ladders_easy` | 2 | 16 | high |
| `campus_laddering_feet_off` | 2 | 16 | high |
| `campus_switches` | 2 | 16 | high |
| `campus_sprint_endurance` | 2 | 16 | high |
| `campus_laddering_down` | 2 | 16 | high |
| `campus_bumps` | 3 | 16 | high |
| `campus_max_ladders` | 3 | 16 | high |
| `campus_double_dyno` | 3 | 16 | max |

**Note:** The `age_under_16` contraindication value used by all campus exercises is not in the canonical contraindication vocabulary (see section 2). The age gate is already enforced via the dedicated `age_minimum` field, so the contraindication is redundant.

---

## 10. Recency Groups

**Result: PASS** — All 185 exercises have a `recency_group`.

- **118 unique recency groups**
- **90 singleton groups** (1 exercise each) — acceptable for unique exercises
- **Largest groups:**
  - `finger_max_hang`: 10 exercises
  - `pullup_variants`: 8 exercises
  - `campus_ladders`: 6 exercises
  - `technique_footwork_drills`: 6 exercises
  - `gym_arc`: 5 exercises
  - `technique_body_position_drills`: 5 exercises

Groupings are logical — exercises in the same recency group are genuine variants of each other.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total exercises | 185 |
| Catalog version | 2.1 |
| Exercises with video_url | 96 (51.9%) |
| Exercises with null description | 1 |
| Exercises with 0 cues | 1 |
| Exercises with recency_group | 185/185 (100%) |
| Unique recency groups | 118 |
| Orphan exercises | 0 |
| Campus exercises with gates | 10/10 (100%) |

### Category Distribution

| Category | Count |
|----------|-------|
| main_strength | 43 |
| strength_accessory | 22 |
| technique | 20 |
| endurance | 18 |
| prehab | 17 |
| flexibility | 17 |
| core | 12 |
| conditioning | 8 |
| warmup_specific | 6 |
| complementary | 5 |
| power_endurance | 5 |
| test_measurement | 4 |
| test | 4 |
| warmup_general | 3 |
| mobility | 1 |

### Load Model Distribution

| Load Model | Count |
|------------|-------|
| bodyweight_only | 111 |
| grade_relative | 31 |
| external_load | 26 |
| total_load | 17 |

---

## Issue Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **P1** | 2 | Unknown vocabulary values: `lead_wall` equipment, `grip_transition` pattern |
| **P2** | 14 | 10x `age_under_16` non-canonical contraindication, 8 broken video URLs (22 exercises), 1 null description, 1 zero cues |
| **P3** | 18 | 11 generic placeholder video URLs, 7 coincidental duplicate prescriptions |
| **Total** | 34 | |

### Recommended Actions

1. **P1** — Add `lead_wall` to canonical equipment vocabulary or remap `fall_practice.equipment_required_any` to `gym_routes`
2. **P1** — Add `grip_transition` to canonical patterns in vocabulary_v1.md or remap `grip_transitions_half_to_open.pattern` to an existing value (e.g., `isometric_hang`)
3. **P2** — Decide on `age_under_16` contraindication: add to vocabulary or remove from campus exercises (redundant with `age_minimum` field)
4. **P2** — Replace or remove 8 broken `hoopersbeta.com/library/*` URLs and 1 broken `trainingforclimbing.com` URL
5. **P2** — Add description and cues to `finger_warmup_generic`
6. **P3** — Replace 11 generic `hoopersbeta.com/library` placeholder URLs with exercise-specific links or set to `null`
