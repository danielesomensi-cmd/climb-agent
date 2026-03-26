# B157 — Orphan Exercise Leak Fix

**Date:** 2026-03-26
**Type:** B (bugfix) + D (audit)
**Status:** Done

## Problem

`critical_force_test` appeared in resolved sessions despite being deferred to v2 (D89).

**Root cause:** Three concurrent bugs:
1. `critical_force_test` was the only exercise with `domain: ["endurance"]` (all other endurance exercises use `aerobic_capacity`, `power_endurance`, `regeneration`)
2. `finger_maintenance_gym.json` inline block `easy_climbing_post_finger` had `domain: ["endurance"]` filter but NO `role` filter — allowing test exercises into the candidate pool
3. `intensity_max: "low"` in the filter was never enforced by `pick_best_exercise_p0()`

## Changes

1. **Removed `critical_force_test` from catalog** — deferred to v2/D89
   - `backend/catalog/exercises/v1/exercises.json`: removed entry
   - `backend/engine/progression_v1.py`: removed from `HANGBOARD_DEFAULT_INTENSITY_PCT`
   - `backend/tests/test_session_1b.py`: flipped assertion to verify removal
   - `backend/tests/test_exercises_v2.py`: updated count (180 → 179), removed from ID sets

2. **Added `role: ["main"]` filter to `easy_climbing_post_finger` block**
   - `backend/catalog/sessions/v1/finger_maintenance_gym.json`: added role filter

3. **Added 4 catalog validation tests** (`backend/tests/test_catalog_validation.py`):
   - `test_all_exercise_domains_are_canonical` — vocabulary §2.2 enforcement
   - `test_all_exercise_roles_are_canonical` — vocabulary §2.1 enforcement
   - `test_no_test_exercise_selected_by_non_test_block` — orphan leak prevention
   - `test_template_domain_filters_use_canonical_values` — filter hygiene

## Audit Results (Phase 0)

- 180 exercises scanned → 0 domain violations, 0 role violations
- 25 templates + 34 sessions scanned → 0 filter violations
- 1 orphan test exercise found: `critical_force_test` (now removed)
- 1 vulnerable inline block found: `easy_climbing_post_finger` (now fixed)
- `intensity_max` not enforced in resolver (noted, P2 — no other leak currently)
