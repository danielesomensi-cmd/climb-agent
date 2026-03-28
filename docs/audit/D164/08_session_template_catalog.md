# D164 Audit — Session & Template Catalog Integrity

**Date:** 2026-03-27
**Scope:** `backend/catalog/sessions/v1/`, `backend/catalog/templates/v1/`
**Cross-referenced:** `planner_v2.py` (`_SESSION_META`), `macrocycle_v1.py` (`_SESSION_POOL`, `_SESSION_POOL_BOULDER`), `exercises/v1/exercises.json`

---

## Summary

| Metric | Count |
|--------|-------|
| Session JSON files | 35 |
| Template JSON files | 27 |
| Exercises in catalog | 185 |
| Sessions in `_SESSION_META` | 35 |
| Sessions in `_SESSION_POOL` (lead, unique) | 23 |
| Sessions in `_SESSION_POOL_BOULDER` (unique) | 18 |

**Verdict:** No P1 issues. Several P2 schema inconsistencies and one P2 legacy-format session. Eight orphan templates (P3). Overall catalog is well-structured and functional.

---

## 1. Session JSON Validity

### 1.1 Required fields check

Expected fields: `id`, `name`, `version`, `intent`, `compatibility`, `required_equipment`, `context`, `time_budget`, `modules`.

| Session | Missing Fields | Severity |
|---------|---------------|----------|
| `easy_climbing_deload` | `compatibility`, `context`, `intent`, `time_budget`, `version` | **P2** |
| `deload_recovery` | `compatibility`, `intent`, `required_equipment` | **P2** |
| `complementary_conditioning` | `required_equipment` | P3 |
| `flexibility_full` | `required_equipment` | P3 |
| `handstand_practice` | `required_equipment` | P3 |
| `prehab_maintenance` | `required_equipment` | P3 |
| `yoga_recovery` | `required_equipment` | P3 |
| `finger_aerobic_base` | `compatibility`, `intent` | P3 |
| `finger_endurance_short` | `compatibility`, `intent` | P3 |
| `test_max_hang_5s` | `context` | P3 |
| `test_max_hang_7s` | `context` | P3 |
| `test_lp_max_5s` | `context` | P3 |
| `test_lp_repeater` | `context` | P3 |
| `test_max_weighted_pullup` | `context` | P3 |
| `test_pullup_bw` | `context` | P3 |
| `test_repeater_7_3` | `context` | P3 |

### 1.2 `easy_climbing_deload` — Legacy schema (P2)

This session uses a completely different schema from all other sessions:

- Has `type`, `location`, `duration_minutes`, `intensity`, `phase_tags`, `session_id`, `description` (non-standard fields)
- Missing `version`, `intent`, `compatibility`, `context`, `time_budget`
- Appears to be from an older session format that was never migrated

The resolver may still handle it (it has `modules` with `template_id` references), but it is the only session with this schema shape. Recommend migrating to current schema.

### 1.3 `test_max_hang_5s` vs `test_max_hang_7s` — Near-duplicate (P3)

Both sessions:
- Have `name: "Test Max Hang 7s"`
- Reference the same template (`finger_max_strength_test`)
- Have the same `test_id: "max_hang_7s_total_load"`
- Differ only in `id` and `version` (5s is v1.1, 7s is v1.0)

The `test_max_hang_5s` id is kept for backward compatibility (noted in its `intent.notes`). This is intentional but worth documenting: they are functionally identical.

### 1.4 Module template references — All valid

Every `template_id` referenced in session modules maps to an existing template file. **19 unique templates** are referenced across all 35 sessions. No broken references.

---

## 2. Template JSON Validity

### 2.1 Required fields

All 27 templates have the required fields: `id`, `version`, `blocks`. All templates also have `category` and `name`. No issues.

### 2.2 Block structure

All template blocks use recognized structures (explicit `exercise_id`, `pool` arrays, or `exercises` arrays with selection logic). No malformed blocks detected.

### 2.3 Schema variation across templates

Templates have inconsistent optional fields — some have `required_environment`, `sport`, `stress_tags`, `compatible_slots`, `disciplines`, `goals`, `module_notes`, `schedule_rules`. This is not a functional issue (the resolver handles missing fields gracefully) but reduces schema predictability.

| Field | Templates with it | Templates without |
|-------|-------------------|-------------------|
| `sport` | 19 | 8 |
| `stress_tags` | 22 | 5 |
| `category` | 27 | 0 |
| `required_environment` | 8 | 19 |

**Severity:** P3

---

## 3. Cross-Reference Integrity

### 3.1 `_SESSION_META` vs JSON files

**Perfect 1:1 mapping.** All 35 sessions in `_SESSION_META` have a corresponding JSON file, and all 35 JSON files are represented in `_SESSION_META`.

### 3.2 `_SESSION_POOL` vs `_SESSION_META`

All sessions in both `_SESSION_POOL` (lead) and `_SESSION_POOL_BOULDER` are present in `_SESSION_META`. No broken references.

### 3.3 Sessions in `_SESSION_META` but not in any `_SESSION_POOL`

12 sessions exist in `_SESSION_META` but are never placed by the phase-pool system:

| Session | Reason |
|---------|--------|
| `test_max_hang_5s` | Test — injected via Pass 3 |
| `test_max_hang_7s` | Test — injected via Pass 3 |
| `test_lp_max_5s` | Test — injected via Pass 3 |
| `test_lp_repeater` | Test — injected via Pass 3 |
| `test_max_weighted_pullup` | Test — injected via Pass 3 |
| `test_pullup_bw` | Test — injected via Pass 3 |
| `test_repeater_7_3` | Test — injected via Pass 3 |
| `pulling_strength_gym` | Used via replanner intent-fallbacks |
| `heavy_conditioning_gym` | Available via replanner/quick-add |
| `lower_body_gym` | Available via replanner/quick-add |
| `upper_body_weights` | Available via replanner/quick-add |
| `legs_strength` | Available via replanner/quick-add |

**Verdict:** All accounted for. Test sessions bypass the pool (correct). Conditioning/strength sessions are reachable through the replanner. **No orphan sessions.** P3 — `core_training` is in `_SESSION_POOL_BOULDER` but NOT in `_SESSION_POOL` (lead). It is also the only `_ALWAYS_SUGGESTIBLE` session in the replanner. Intentional but worth noting for lead users who rely on quick-add.

### 3.4 Orphan templates (not referenced by any session)

8 templates exist but are not referenced by any session's `modules`:

| Template | Category |
|----------|----------|
| `general_strength_accessories` | strength |
| `gym_aerobic_endurance` | climbing |
| `gym_power_bouldering` | climbing |
| `gym_power_endurance` | climbing |
| `gym_technique_boulder` | climbing |
| `pulling_endurance` | pulling |
| `pulling_strength` | pulling |
| `warmup_recovery` | warmup |

These may be legacy templates from earlier session designs, or reserved for future use. They are inert (no runtime impact) but add catalog bloat.

**Severity:** P3

### 3.5 Exercise references from templates — All valid

All 24 unique `exercise_id` values referenced in template blocks exist in `exercises/v1/exercises.json`. No broken exercise references.

---

## 4. Phase Coverage

### 4.1 Lead discipline (`_SESSION_POOL`)

| Phase | Primary | Available | Total |
|-------|---------|-----------|-------|
| base | 6 | 6 | 12 |
| strength_power | 5 | 7 | 12 |
| power_endurance | 2 | 6 | 8 |
| performance | 3 | 8 | 11 |
| deload | 4 | 3 | 7 |

All phases have adequate coverage. `power_endurance` has fewest sessions (8) but includes the critical `power_endurance_gym` as primary.

### 4.2 Boulder discipline (`_SESSION_POOL_BOULDER`)

| Phase | Primary | Available | Total |
|-------|---------|-----------|-------|
| base | 4 | 4 | 8 |
| strength_power | 5 | 5 | 10 |
| power_endurance | 2 | 4 | 6 |
| performance | 3 | 6 | 9 |
| deload | 4 | 3 | 7 |

`power_endurance` is thinnest (6 sessions). Note: boulder PE uses `boulder_circuit_gym` as primary (no dedicated PE session like lead's `power_endurance_gym`).

### 4.3 Deload phase — shared between disciplines

Both lead and boulder share the same deload pool. This is correct since deload sessions are discipline-agnostic.

---

## 5. Equipment Feasibility

### 5.1 Gym-only sessions (require gym-specific equipment)

14 sessions require gym-specific equipment and cannot be done at home:

- `gym_boulder`: boulder_circuit_gym, easy_climbing_deload, limit_boulder_gym, power_contact_gym, power_endurance_gym, regeneration_easy, technique_focus_gym
- `gym_routes`: endurance_aerobic_gym, route_endurance_gym, route_projecting_gym
- `dumbbell`: heavy_conditioning_gym, lower_body_gym
- `loading_pin`: test_lp_max_5s, test_lp_repeater

### 5.2 Home-only user feasibility (hangboard + pullup_bar)

| Phase (lead) | Home-feasible sessions | Adequate? |
|--------------|----------------------|-----------|
| base | 8 (finger_maintenance_home, finger_maintenance_gym, prehab_maintenance, flexibility_full, handstand_practice, complementary_conditioning, finger_endurance_short, finger_aerobic_base) | Yes |
| strength_power | 8 (strength_long, finger_strength_home, prehab_maintenance, flexibility_full, handstand_practice, complementary_conditioning, finger_maintenance_gym, finger_endurance_short) | Yes |
| power_endurance | 4 (prehab_maintenance, finger_strength_home, flexibility_full, handstand_practice) | Marginal |
| performance | 4 (prehab_maintenance, finger_strength_home, flexibility_full, handstand_practice) | Marginal |
| deload | 5 (flexibility_full, yoga_recovery, prehab_maintenance, deload_recovery, finger_aerobic_base) | Yes |

**Finding (P3):** Home-only users in `power_endurance` and `performance` phases have only 4 sessions available, and only 1 is training-focused (`finger_strength_home`). The others are low-intensity complementary sessions. This is a known limitation — climbing-focused phases inherently need a gym. The planner handles this gracefully by filling with available sessions.

### 5.3 `required_equipment` field consistency

5 sessions are missing the `required_equipment` field entirely: `complementary_conditioning`, `flexibility_full`, `handstand_practice`, `prehab_maintenance`, `yoga_recovery`. These are all no-equipment sessions, so the missing field is functionally equivalent to `[]`, but it should be explicit for schema consistency.

**Severity:** P3

---

## 6. Session Field Consistency

### 6.1 Standard schema (30 sessions)

30 of 35 sessions follow the standard schema: `id`, `name`, `version`, `intent`, `compatibility`, `required_equipment`, `context`, `time_budget`, `modules`. Some also have `coach_notes`, `supplementary`, `tags`, `test_id`.

### 6.2 Non-standard schemas

| Session | Issue | Severity |
|---------|-------|----------|
| `easy_climbing_deload` | Completely different schema (legacy format with `type`, `location`, `duration_minutes`, `intensity`, `phase_tags`, `session_id`, `description`) | **P2** |
| `deload_recovery` | Missing `compatibility`, `intent`, `required_equipment` | **P2** |
| `finger_aerobic_base` | Missing `compatibility`, `intent` | P3 |
| `finger_endurance_short` | Missing `compatibility`, `intent` | P3 |

### 6.3 Extra fields on some sessions

- `coach_notes`: heavy_conditioning_gym, lower_body_gym, strength_long
- `supplementary`: heavy_conditioning_gym, legs_strength, lower_body_gym, pulling_strength_gym, upper_body_weights

These are legitimate extensions used by the resolver for supplementary exercise injection. No issue.

---

## Findings Summary

### P2 (should fix)

| # | Finding | Location |
|---|---------|----------|
| 1 | `easy_climbing_deload` uses legacy schema — completely different field set from all other sessions | `sessions/v1/easy_climbing_deload.json` |
| 2 | `deload_recovery` missing `compatibility`, `intent`, `required_equipment` | `sessions/v1/deload_recovery.json` |

### P3 (low priority / cosmetic)

| # | Finding | Location |
|---|---------|----------|
| 3 | 5 sessions missing `required_equipment` field (should be `[]`) | complementary_conditioning, flexibility_full, handstand_practice, prehab_maintenance, yoga_recovery |
| 4 | 7 test sessions missing `context` field | All `test_*.json` files |
| 5 | `finger_aerobic_base` and `finger_endurance_short` missing `compatibility` and `intent` | sessions/v1/ |
| 6 | 8 orphan templates not referenced by any session | templates/v1/ (general_strength_accessories, gym_aerobic_endurance, gym_power_bouldering, gym_power_endurance, gym_technique_boulder, pulling_endurance, pulling_strength, warmup_recovery) |
| 7 | `test_max_hang_5s` and `test_max_hang_7s` are functionally identical (both name "Test Max Hang 7s", same template, same test_id) | sessions/v1/ |
| 8 | Template optional fields are inconsistent across files (sport, stress_tags, required_environment presence varies) | templates/v1/ |
| 9 | Home-only users have marginal session variety in power_endurance and performance phases (4 sessions, only 1 training-focused) | macrocycle_v1.py `_SESSION_POOL` |
| 10 | `core_training` is in boulder pool but absent from lead pool | macrocycle_v1.py |

### No issues found

- All `_SESSION_META` entries have matching JSON files (35/35)
- All JSON files are in `_SESSION_META` (35/35)
- All template references from sessions resolve correctly (19/19)
- All exercise references from templates exist in exercises.json (24/24)
- All `_SESSION_POOL` entries exist in `_SESSION_META`
- All 5 phases covered in both lead and boulder disciplines
- Gym users have full session coverage across all phases
