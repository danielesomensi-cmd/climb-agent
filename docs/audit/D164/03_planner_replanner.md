# D164 Audit — Planner & Replanner

**Scope:** `backend/engine/planner_v2.py`, `backend/engine/replanner_v1.py`
**Date:** 2026-03-27
**Auditor:** Claude (read-only)

---

## 1. _SESSION_META Consistency

### F-01 — `test_max_hang_7s` in catalog but missing from _SESSION_META (P2)

**File:** `backend/catalog/sessions/v1/test_max_hang_7s.json` exists but has no entry in `_SESSION_META`.

`planner_v2.py` silently skips sessions not in META (`if meta is None: continue`), so this session can never be scheduled by the planner. It is referenced in the legacy `planner_v1.py` (line 30, 289) and several tests (`test_session_1b.py`, `test_planner_v1.py`, `test_resolve_real_sessions.py`).

**Impact:** If the 7s variant is ever needed (e.g., for different test protocols), the planner won't find it. Low risk today because `test_max_hang_5s` is the active test, but the orphaned catalog file creates confusion.

**Recommendation:** Either add `test_max_hang_7s` to `_SESSION_META` or archive the catalog JSON to `_archive/`.

### F-02 — `regeneration_easy` equipment mismatch between catalog and META (P2)

**Files:**
- Catalog (`regeneration_easy.json`): `required_equipment: ["gym_boulder"]`
- META: `required_equipment: None` (key absent), `location: ("home", "gym", "outdoor")`

The planner uses META and will schedule `regeneration_easy` at home or outdoor without checking equipment. The session resolver then reads the catalog JSON and finds `required_equipment: ["gym_boulder"]`, which may cause degraded exercise selection when resolved at home (exercises requiring gym_boulder get filtered out).

The replanner also uses `regeneration_easy` extensively as a universal fallback (e.g., `_find_gym_change_replacement`, `_build_fill_session`, `_enforce_caps`, `_enforce_no_consecutive_finger`), always assuming it needs no equipment.

**Impact:** Home-only users may get `regeneration_easy` sessions that resolve to a minimal subset of exercises, since the catalog says it needs gym_boulder but the planner placed it at home. Not a crash but potentially a poor user experience.

**Recommendation:** Align META and catalog. If the session is intended to be universal (the META intent), remove `required_equipment` from the catalog JSON. If it truly needs gym_boulder, add `required_equipment: ["gym_boulder"]` to META and restrict its location.

---

## 2. Planner Edge Cases

### F-03 — 0 gyms (home-only user): OK, no issues found (P3)

Verified: with `allowed_locations=["home"]` and the base phase pool, at least 8 sessions are available at home with no equipment requirements (prehab_maintenance, flexibility_full, yoga_recovery, handstand_practice, complementary_conditioning, deload_recovery, upper_body_weights, legs_strength, core_training). The planner will not produce 0 sessions.

With a hangboard at home, finger sessions also become available. Without any home equipment, the planner still has enough complementary sessions to fill 4+ training days.

### F-04 — 1 available day: OK, handled correctly (P3)

The planner caps `available_day_count` to `target_days` (line 685) and iterates all 7 days. With only 1 available day, Pass 1 places 1 primary session and Pass 2 is skipped (already >= target or no more days). The plan produces 1 day with 1 session, which is correct.

### F-05 — 7 available days: OK, capped by target_days (P3)

When all 7 days are available, the planner's day-selection scoring (lines 685-700) picks the top `target_days` days by gym-priority score, disabling the rest. This prevents over-scheduling.

### F-06 — Deload phase: OK, correct behavior (P3)

- `effective_hard_cap` is forced to 0 (line 552)
- Intensity cap is "low" (from `PHASE_INTENSITY_CAP`)
- All deload pool sessions are low intensity and non-hard
- `apply_deload_week()` further filters, capping at 5 sessions and removing any hard
- Load summary is recomputed after deload transformation (lines 1334-1343)

### F-07 — Phase transitions: No explicit transition logic (P3)

The planner has no special handling for phase boundaries beyond `is_last_week_of_phase` (triggers test injection). There is no ramp-up/ramp-down between phases. The macrocycle module handles phase assignment per week, and each week is planned independently with its phase's intensity cap and session pool.

This is by design (the DUP model handles load variation within phases), but could be noted as a future enhancement area.

### F-08 — Youth cap (under 18): OK, enforced (P3)

Line 572: `if user_age is not None and user_age < 18: target_days = min(target_days, 4)`. This correctly caps training days at 4 for youth users. However, the hard_cap is NOT reduced for youth — they can still get up to `effective_hard_cap` hard sessions in those 4 days. Literature suggests youth should have fewer high-intensity sessions.

**Observation (not a bug):** Consider also capping `effective_hard_cap` at 2 for youth users.

### F-09 — Recovery multiplier (40+): Planner respects it, replanner does NOT (P1)

**Planner** (lines 576-578):
```python
recovery_mult = float(prefs.get("recovery_multiplier", 1.0))
hard_gap_days = math.ceil(1 * recovery_mult)
finger_gap_days = math.ceil(1 * recovery_mult)
```
For a 45-year-old with `recovery_multiplier=1.3`, gaps become `ceil(1.3) = 2` days.

**Replanner** `_enforce_no_consecutive_finger()` (line 728):
```python
if has_finger and last_finger_date and (cur - last_finger_date).days <= 1:
```
This is hardcoded to 1-day gap. After a replanner override or quick-add, `_reconcile()` calls `_enforce_no_consecutive_finger()` which uses the weaker 1-day check, potentially allowing finger sessions with only a 1-day gap for 40+ users who need a 2-day gap.

Similarly, `suggest_sessions()` (line 247) checks finger adjacency with `abs(days) <= 1` regardless of recovery multiplier.

And `_compensate_finger()` (line 1115) uses `abs(days) <= 1` for spacing.

**Impact:** 40+ users with `recovery_multiplier > 1.0` get correct spacing from initial planning but may get insufficient spacing after replanning actions (overrides, quick-adds, gym changes, outdoor ripple). This is a real recovery risk for the target demographic.

**Recommendation:** Pass `recovery_multiplier` (or the computed gap values) to all replanner functions and use it in `_enforce_no_consecutive_finger()`, `_compensate_finger()`, `suggest_sessions()`, and the ripple logic in `apply_day_add()`.

---

## 3. Replanner Correctness

### F-10 — Past/completed session preservation: Correct, thoroughly enforced (P3)

Multiple guard layers:
1. `_is_preservable()` checks `status in ("done", "skipped")` or `quick_add` constraint
2. `merge_prev_week_sessions()` copies days before `preserve_before` wholesale
3. `regenerate_preserving_completed()` independently implements the same logic
4. All event handlers (`move_session`, `remove_session`, `apply_day_override`) check for `done/skipped` status and raise `ValueError` if attempting to modify
5. Ripple effects (day+1, day+2) skip sessions with `status in ("done", "skipped")` (B120)
6. `change_gym` event skips sessions with `done/skipped` status

This is comprehensive and well-tested. The immutability pillar is respected.

### F-11 — Equipment change mid-week (change_gym event): Mostly correct, one edge case (P2)

The `change_gym` handler (lines 1165-1240):
1. Loads gym equipment via `expand_equipment`
2. Checks each session for location + equipment compatibility
3. Replaces incompatible sessions via `_find_gym_change_replacement()`
4. Triggers finger compensation if a finger session was lost

**Edge case:** `_find_gym_change_replacement()` (lines 39-53) has a narrow fallback chain:
1. `complementary_conditioning` (if location-compatible)
2. `regeneration_easy` (universal fallback)

The function signature accepts `is_finger_session` but never uses it for routing. The comment mentions `finger_strength_home` as a fallback for finger sessions going home, but that branch was removed or never implemented. The parameter is dead code.

**Impact:** When a gym change removes a finger session and the user is going home with a hangboard, the function always falls back to `complementary_conditioning` or `regeneration_easy` instead of `finger_strength_home`. The `_compensate_finger()` function partially mitigates this by trying to place finger_maintenance on a later day, but the immediate replacement is suboptimal.

### F-12 — Gym removal: No special handling (P3)

There is no `remove_gym` event type. If a user removes a gym from their profile, the planner regenerates with the updated gym list. The replanner's `merge_prev_week_sessions` / `regenerate_preserving_completed` preserves past sessions. Future sessions get replanned with the remaining gyms. This is correct behavior — the gym removal triggers a full regeneration through the API layer, not a replanner event.

### F-13 — Day swap respects hard/finger gaps: Partially (P2)

`apply_events` with `move_session` (lines 762-780) extracts a session from one day and inserts it on another. It does NOT check:
- Whether the target day already has a finger session (violating 48h gap)
- Whether the target day is adjacent to a hard day (violating hard gap)
- Whether the move creates back-to-back hard or finger days

The `_reconcile()` call at the end (line 815) catches consecutive finger days (with the hardcoded 1-day check, see F-09) and hard cap violations, but does NOT check hard-day spacing.

**Impact:** A user could move a hard session to a day adjacent to another hard day, and `_reconcile()` would not catch it (only caps are checked, not spacing). This is mitigated by the fact that users manually choose the target day, but the system should at minimum warn.

**Recommendation:** Add spacing validation to `move_session` or enhance `_reconcile()` to check hard-day spacing.

---

## 4. Test Scheduling

### F-14 — Freshness filter (42 days): Correct (P3)

Lines 1157-1160: `TEST_FRESHNESS_DAYS = 42`. Tests completed within the last 42 days are skipped from the schedule. The check correctly compares `week_start - last_test_date` against the threshold.

### F-15 — Test pairs respect 48h gap: Correct (P3)

Pass 3 (lines 1212-1220) checks finger spacing:
```python
if test_meta["finger"] and not day_has_finger and finger_day_offsets:
    if any(abs(offset - fo) <= finger_gap_days for fo in finger_day_offsets):
        continue
```
This correctly uses `finger_gap_days` (which includes recovery multiplier) for test scheduling. Both finger tests (`test_max_hang_5s` and `test_repeater_7_3`) are finger-tagged, so they respect the 48h gap from each other and from regular finger sessions.

### F-16 — Loading pin routing: Correct (P3)

Lines 1166-1167: When `finger_device == "loading_pin"`, tests are routed to `test_lp_max_5s` and `test_lp_repeater` (both require `loading_pin` equipment). When not loading_pin, they route to `test_max_hang_5s` and `test_repeater_7_3` (require `hangboard`). The equipment requirements in META match.

### F-17 — Tests only replace existing sessions, never fill empty days (P2)

Pass 3 (line 1228): `if not day_sessions[offset]: continue`. Tests can only be placed on days that already have sessions from Pass 1/2. If the planner could not place any sessions (extremely rare but theoretically possible with very restrictive availability), tests silently fail to schedule.

**Edge case scenario:** User has 2 available days, both home-only with no equipment, in base phase (intensity cap = medium). Both days get complementary sessions. Pass 3 replaces them with tests. But the test sessions require equipment (hangboard/pullup_bar). `_find_best_slot` would return None because the home location lacks the required equipment. The test is silently dropped.

**Impact:** Low — requires a very specific combination of constraints. But the user might expect tests and never get them without explanation.

**Recommendation:** Log a warning when test sessions can't be placed due to equipment/location constraints.

---

## 5. Logical Issues

### F-18 — Planner cannot produce back-to-back hard days (within a week): Correct (P3)

Pass 1 enforces hard-day spacing (lines 765-768):
```python
if meta["hard"] and hard_day_offsets:
    last_hard_offset = hard_day_offsets[-1]
    if (offset - last_hard_offset) <= hard_gap_days:
        skip = True
```
With `hard_gap_days >= 1`, hard sessions are always at least 2 calendar days apart.

B161 cross-week seeding ensures hard sessions from Sunday of the previous week are considered when planning Monday of the current week.

### F-19 — No infinite loop risk in Pass 1 (P3)

Pass 1 has two termination guards:
1. `primary_uses >= max_primary_uses` (max 2 cycles through pool)
2. `attempts < len(primary_pool)` (max one full scan per day)

The `while` loop increments either `primary_idx` or breaks on placement. The outer `for` loop iterates once per day. Total iterations are bounded by `7 * len(primary_pool) * 2`.

### F-20 — Planner CAN produce 0 sessions for the week (P3)

If the user has 0 available days (all days marked unavailable), the planner produces a valid plan structure with empty sessions arrays for all 7 days. This is correct behavior — the user said they're not available.

If the user has available days but the session pool is empty after filtering (theoretically impossible given current phase pools), passes 1 and 2 would produce 0 sessions. The plan structure is still valid.

### F-21 — `_enforce_caps` only checks hard cap, not hard spacing (P2)

`_enforce_caps()` (line 699) counts hard days and downgrades excess hard sessions by iterating in reverse. But it does NOT check spacing between the remaining hard sessions. If somehow two adjacent hard sessions remain under the cap, they won't be caught.

In practice, the planner never creates this situation (F-18), but replanner actions (override + quick-add on adjacent days, both hard) could create it. `_reconcile()` calls `_enforce_caps()` but not a hard-spacing check.

**Recommendation:** Add a `_enforce_no_consecutive_hard()` function to `_reconcile()`, mirroring `_enforce_no_consecutive_finger()`.

### F-22 — Pass 2 complementary sessions burn uses on permanent skips (P3)

In Pass 2 (lines 942-945), when a session is skipped due to `max_per_week` exhaustion, `comp_uses += 1` is incremented. This is intentional — it prevents infinite cycling through the complementary pool. The `max_comp_uses = len(pool) * 2` budget is generous enough to handle typical pools (6-8 sessions * 2 = 12-16 uses for typically 1-3 complementary slots).

---

## Summary

| ID | Severity | Area | Description |
|----|----------|------|-------------|
| F-01 | P2 | META | `test_max_hang_7s` in catalog but missing from `_SESSION_META` |
| F-02 | P2 | META | `regeneration_easy` equipment mismatch (catalog vs META) |
| F-09 | P1 | Planner/Replanner | Recovery multiplier ignored in replanner finger/hard spacing |
| F-11 | P2 | Replanner | `_find_gym_change_replacement` has dead `is_finger_session` param |
| F-13 | P2 | Replanner | `move_session` doesn't validate hard/finger spacing |
| F-17 | P2 | Test scheduling | Tests silently dropped when no sessions exist or equipment missing |
| F-21 | P2 | Replanner | `_reconcile` enforces finger spacing but not hard-day spacing |

**P1 count:** 1
**P2 count:** 6
**P3 count:** 15 (informational, no action needed)
