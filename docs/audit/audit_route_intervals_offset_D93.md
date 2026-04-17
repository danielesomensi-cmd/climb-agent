# D93 v2 — Grade Offset Catalog Audit: `route_intervals`

> **Type:** D (audit — read-only)
> **Date:** 2026-04-16
> **Status:** STOP — pending review, no changes applied
> **Author:** Claude Code (Opus 4.6)

---

## Task 1 — Locate `grade_offset = -2` for `route_intervals`

### Authoritative source (single source of truth)

**File:** `backend/catalog/exercises/v1/exercises.json`, lines 2458–2506

```json
{
  "id": "route_intervals",
  "name": "Route Intervals (Timed Rest)",
  "category": "main_strength",
  "domain": ["power_endurance"],
  "pattern": "climbing_intervals",
  "intensity_level": "high",
  "equipment_required": ["gym_routes"],
  "prescription_defaults": {
    "sets": 4,
    "work_seconds": 60,
    "rest_between_sets_seconds": 60,
    "notes": "Climb route sections with timed rest. Grade 1-2 below onsight. Focus sustained effort.",
    "grade_ref": "lead_max_os",
    "grade_offset": -2
  },
  "cues": [
    "Route at ~80% max: should pump but not fail",
    "Rest equal to or less than climb time between reps",
    "Focus on efficient movement and resting on route",
    "Log time per ascent to track improvement",
    "3-5 intervals per session, progressive overload via rest reduction"
  ],
  "load_model": "grade_relative"
}
```

### Self-consistency issue in the exercise definition itself

The `notes` field says "Grade 1-2 below onsight" (ambiguous — -1 or -2?), while `grade_offset` is hard-coded to `-2`. Meanwhile, the first cue says "Route at ~80% max" which maps to **-1** (near-onsight), not -2. The `notes` text is ambiguous; the cue text directly contradicts `-2`.

### Secondary references

No secondary locations override this value. The `grade_offset` is stored **only** in the exercise catalog `prescription_defaults`. Session templates select exercises by filter criteria (pattern, domain, equipment) — they don't carry per-exercise offset overrides. The resolver reads `prescription_defaults` directly from the exercise catalog at resolve-time.

---

## Task 2 — Full-Catalog Offset Enumeration

### Complete table: all 31 exercises with `grade_offset`

All use `load_model: "grade_relative"`.

| # | exercise_id | grade_ref | current offset | domain(s) | category | pattern | notes |
|---|---|---|---|---|---|---|---|
| 1 | `limit_bouldering` | boulder_max_rp | **0** | power, technique_boulder | main_strength | climbing_limit_boulder | At limit — correct |
| 2 | `board_limit_boulders` | boulder_max_rp | **0** | power | main_strength | climbing_limit_boulder | At limit — correct |
| 3 | `spray_wall_limit` | boulder_max_rp | **0** | power, technique_boulder | main_strength | climbing_limit_boulder | At limit — correct |
| 4 | `system_board_limit` | boulder_max_rp | **0** | power | main_strength | climbing_limit_boulder | At limit — correct |
| 5 | `threshold_climbing` | lead_max_os | **-1** | power_endurance | endurance | climbing_continuous | PE sustained route — correct |
| 6 | `route_on_the_minute` | lead_max_os | **-1** | power_endurance | endurance | climbing_continuous | PE route OTM — correct |
| 7 | `route_linked_laps` | lead_max_os | **-1** | power_endurance | endurance | climbing_continuous | PE route laps — correct |
| 8 | `otm_bouldering` | boulder_max_os | **-1** | power_endurance, anaerobic_capacity | power_endurance | climbing_intervals | Boulder OTM — correct |
| 9 | `threshold_long_intervals` | lead_max_os | **-1** | aerobic_capacity | endurance | climbing_continuous | Aerobic threshold — correct |
| 10 | `one_on_one_off_intervals` | lead_max_os | **-1** | aerobic_capacity | endurance | climbing_continuous | Lattice protocol — correct |
| 11 | `timed_route_preview` | lead_max_os | **-1** | technique_lead | technique | climbing_drills | Technique near-limit — correct |
| 12 | **`route_intervals`** | **lead_max_os** | **-2** ⚠️ | **power_endurance** | **main_strength** | **climbing_intervals** | **FLAGGED — should be -1 per PE cohort** |
| 13 | `four_by_four_bouldering` | boulder_max_rp | **-2** | power_endurance, anaerobic_capacity | main_strength | climbing_intervals | 4×4 multi-problem cascade — correct |
| 14 | `emom_bouldering` | boulder_max_os | **-2** | power_endurance, anaerobic_capacity | power_endurance | climbing_intervals | EMOM boulder — see note¹ |
| 15 | `thirty_thirty_intervals` | boulder_max_rp | **-2** | power_endurance, anaerobic_capacity | power_endurance | climbing_intervals | 30/30 intervals — correct |
| 16 | `aerobic_pyramid_intervals` | lead_max_os | **-2** | aerobic_capacity | endurance | climbing_continuous | Aerobic pyramid — correct |
| 17 | `gym_technique_boulder_drills` | boulder_max_os | **-2** | technique_boulder, technique_footwork | strength_accessory | climbing_drills | Technique — correct |
| 18 | `silent_feet_drill` | boulder_max_os | **-2** | technique_footwork | technique | climbing_drills | Technique — correct |
| 19 | `no_readjust_drill` | boulder_max_os | **-2** | technique_footwork | technique | climbing_drills | Technique — correct |
| 20 | `downclimbing_drill` | boulder_max_os | **-2** | technique_footwork | technique | climbing_drills | Technique — correct |
| 21 | `slow_climbing` | boulder_max_os | **-2** | technique_lead | technique | climbing_drills | Technique — correct |
| 22 | `flag_practice` | boulder_max_os | **-2** | technique_boulder | technique | climbing_drills | Technique — correct |
| 23 | `heel_hook_specific_drill` | boulder_max_rp | **-2** | technique_footwork | technique | climbing_drills | Technique — correct |
| 24 | `freeze_drill` | boulder_max_os | **-2** | technique_body_position | technique | climbing_drills | Technique — correct |
| 25 | `twist_lock_drill` | boulder_max_os | **-2** | technique_body_position | technique | climbing_drills | Technique — correct |
| 26 | `linked_boulders_circuit` | boulder_max_rp | **-3** | power_endurance, anaerobic_capacity | power_endurance | climbing_intervals | Linked circuit — correct |
| 27 | `continuity_climbing` | lead_max_os | **-4** | regeneration | endurance | climbing_continuous | Regeneration — correct |
| 28 | `arc_training_progressive` | lead_max_os | **-4** | aerobic_capacity, regeneration | endurance | climbing_continuous | Progressive ARC — correct |
| 29 | `gym_arc_easy_volume` | lead_max_os | **-5** | aerobic_capacity | endurance | climbing_continuous | ARC easy — correct |
| 30 | `arc_training` | lead_max_os | **-5** | aerobic_capacity | endurance | climbing_continuous | ARC — correct |
| 31 | `regeneration_climbing` | lead_max_os | **-5** | regeneration | endurance | climbing_continuous | Regeneration — correct |

**¹ Note on `emom_bouldering`:** Uses `boulder_max_os` (onsight) with offset -2. Given EMOM's high intensity demand (RPE 8-9 for the work interval), this could be a candidate for -1, similar to `otm_bouldering`. However, EMOM typically uses slightly easier problems than OTM due to the fixed 1-minute cycle constraint. Deferred for separate review.

### Offset distribution summary

| Offset | Count | Exercise classes |
|--------|-------|------------------|
| 0 | 4 | Limit bouldering (all surfaces) |
| -1 | 7 | PE route-sustained, OTM boulder, aerobic threshold, technique near-limit |
| -2 | 14 | 4×4/EMOM/30-30 intervals, technique drills, **route_intervals (flagged)** |
| -3 | 1 | Linked boulder circuit |
| -4 | 2 | Continuity, progressive ARC |
| -5 | 3 | ARC, regeneration |

---

## Task 3 — Catalog ↔ Vocabulary Consistency Check

### Vocabulary reference table (from `docs/vocabulary_v1.md` lines 398-405)

| offset | meaning | typical exercises (per vocabulary) |
|--------|---------|-------------------------------------|
| 0 | at limit | limit bouldering |
| -1 | one grade below | threshold, OTM |
| -2 | two grades below | 4x4, **route intervals**, technique drills |
| -3 | three grades below | linked circuits, moderate volume |
| -4 | four grades below | continuity, progressive ARC |
| -5 | five grades below | ARC, regeneration — trivially easy |

### Discrepancy list

| exercise_id | catalog offset | vocabulary-implied offset | discrepancy? | severity | rationale |
|---|---|---|---|---|---|
| **`route_intervals`** | **-2** | **-1** (per PE cohort: threshold, OTM, route_linked_laps all at -1; Hörst "near-onsight" prescription; ~80% max cue) | **YES** | **MEDIUM** | Sub-threshold PE intensity. Literature, cue text, and PE cohort all say -1. Vocabulary says -2 but vocabulary is wrong here (it was written based on the catalog value, not cross-checked against literature). |
| `emom_bouldering` | -2 | possibly -1 (same RPE 8-9 as OTM, which is at -1) | **POSSIBLE** | LOW | EMOM's fixed 1-min cycle may justify slightly easier problems than OTM. Needs KB review to confirm. Not actionable in this brief. |

**All other exercises:** CONSISTENT — no discrepancies found between catalog offsets and their expected values per training domain and vocabulary semantics.

### Vocabulary table accuracy note

The vocabulary table at `docs/vocabulary_v1.md:402` lists `route intervals` in the -2 row. This was likely transcribed from the catalog (descriptive) rather than prescribed by literature (normative). If the patch in §3 is approved, the vocabulary table should be updated in a follow-up brief to move `route intervals` from the -2 row to the -1 row alongside threshold and OTM.

---

## Task 4 — Shared Configuration Check

### Does the patch leak to other exercises?

**No.** The `grade_offset` is stored per-exercise in `prescription_defaults` within `exercises.json`. There is:

- **No shared default offset** at the session template level — templates select exercises by filter criteria (pattern, domain, equipment) but don't carry offset overrides.
- **No inheritance or merge logic** — the resolver reads `prescription_defaults` directly from the matched exercise catalog entry.
- **No `prescription_defaults` block** at the session level that would propagate changes.

Changing `route_intervals.prescription_defaults.grade_offset` from -2 to -1 affects **only** `route_intervals`. Zero leakage risk.

### Confirmation via code path

In `progression_v1.py:889`:
```python
grade_offset = int(prescription.get("grade_offset") or 0)
```

The `prescription` dict comes from the individual exercise's `prescription_defaults` — not shared state.

---

## Task 5 — Test Coverage

### Tests that assert `grade_offset = -2` for `route_intervals`

These tests **must be updated** atomically with the catalog patch:

| File | Test function | Line | Current assertion | Required update |
|---|---|---|---|---|
| `test_feedback_loop_e2e.py` | `test_e2e_grade_relative_loop()` | 243, 248 | `grade_offset: -2`, expects `"7A"` from `lead_max_os="7c"` | Change to `grade_offset: -1`, expect `"7B"` |
| `test_feedback_loop_e2e.py` | `test_e2e_grade_ref_with_plus()` | 282, 287 | `grade_offset: -2`, expects `"7A"` from `lead_max_os="7c+"` | Change to `grade_offset: -1`, expect `"7B"` |

### Tests that indirectly reference `route_intervals` (no offset assertion — unaffected)

| File | Test function | Impact |
|---|---|---|
| `test_session_enrichment.py` | `test_pe_gym_with_routes_selects_route_intervals()` | No grade assertion — only checks exercise selection. **Unaffected.** |
| `test_session_enrichment.py` | `test_pe_gym_without_routes_still_resolves()` | No grade assertion — checks equipment filtering. **Unaffected.** |

### Test gap: no test asserts `route_intervals` target grade from catalog defaults

The existing E2E tests in `test_feedback_loop_e2e.py` hard-code the `grade_offset` in the test fixture rather than resolving from catalog. There is **no integration test** that:
1. Reads the catalog value of `grade_offset` for `route_intervals`
2. Resolves a session containing `route_intervals`
3. Asserts the resulting `suggested_grade` matches the catalog offset

**Recommendation:** Add a new test that resolves `route_intervals` end-to-end from the catalog (not from a test fixture) and asserts the target grade. This would catch future offset regressions.

### Proposed new test cases (for the patch brief)

```python
def test_route_intervals_target_grade_7a_onsight():
    """lead_max_os=7a + route_intervals (offset -1) → target_grade = 6c."""
    us = _make_user_state(grades={"lead_max_os": "7a"})
    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1})
    day = inject_targets(day, us)
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    assert s["suggested_grade"] == "6C"

def test_route_intervals_target_grade_8a_onsight():
    """lead_max_os=8a + route_intervals (offset -1) → target_grade = 7c."""
    us = _make_user_state(grades={"lead_max_os": "8a"})
    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1})
    day = inject_targets(day, us)
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    assert s["suggested_grade"] == "7C"

def test_route_intervals_target_grade_6b_onsight():
    """lead_max_os=6b + route_intervals (offset -1) → target_grade = 6a."""
    us = _make_user_state(grades={"lead_max_os": "6b"})
    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1})
    day = inject_targets(day, us)
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    assert s["suggested_grade"] == "6A"

def test_route_intervals_target_grade_6a_clamp():
    """lead_max_os=6a + route_intervals (offset -1) → target_grade = 5c (clamp at scale minimum)."""
    us = _make_user_state(grades={"lead_max_os": "6a"})
    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1})
    day = inject_targets(day, us)
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    # step_grade("6A", -1) → index 3 - 1 = 2 → "5C"
    assert s["suggested_grade"] == "5C"
```

**Edge case analysis for `lead_max_os=6a`:**
- `step_grade("6A", -1)` → index `_WHOLE_GRADE_TO_INDEX["6A"]` = 3, offset -1 → index 2 → `WHOLE_FONT_GRADES[2]` = `"5C"`
- The engine clamps at index 0 (`"5A"`), so no crash. Result: `"5C"` — valid behavior.

---

## Task 6 — `step_grade()` Sanity Check

### Implementation (from `progression_v1.py:275-286`)

```python
WHOLE_FONT_GRADES = [
    "5A", "5B", "5C",
    "6A", "6B", "6C",
    "7A", "7B", "7C",
    "8A", "8B", "8C",
]

def step_grade(grade: str, steps: int) -> str:
    cleaned = str(grade).strip().upper().replace(' ', '').replace('+', '')
    if cleaned not in _WHOLE_GRADE_TO_INDEX:
        cleaned = '6C'
    idx = _WHOLE_GRADE_TO_INDEX[cleaned] + int(steps)
    idx = max(0, min(len(WHOLE_FONT_GRADES) - 1, idx))
    return WHOLE_FONT_GRADES[idx]
```

### Verification against vocabulary §2.10.1

| Property | Vocabulary spec | Implementation | Match? |
|----------|----------------|----------------|--------|
| Scale | 6a=0, 6b=1, 6c=2, 7a=3, ... | `WHOLE_FONT_GRADES` index: 5A=0, 5B=1, 5C=2, 6A=3, 6B=4, 6C=5, 7A=6, 7B=7, 7C=8, 8A=9, 8B=10, 8C=11 | ✅ Consistent (vocabulary uses 6a=0 as reference point but the scale extends down to 5A) |
| `+` not an increment | "6a+ falls between 6a and 6b" | `.replace('+', '')` strips `+` before lookup | ✅ PASS |
| Letter-only output | whole grades only | Returns from `WHOLE_FONT_GRADES` (no `+` in array) | ✅ PASS |
| Clamping | implied by range [-6, +1] | `max(0, min(11, idx))` | ✅ PASS |
| Case handling | uppercase Font | `.upper()` normalizes input | ✅ PASS |

### Spot-check examples

| Input | Offset | Expected (per vocabulary) | `step_grade()` result | Match? |
|-------|--------|---------------------------|------------------------|--------|
| "7C" | -2 | 7A | 7A | ✅ |
| "6A" | -2 | 5B | 5B | ✅ |
| "7A+" | -2 | 6B (strips + → 7A, -2 → 6B) | 6B | ✅ |
| "8B" | -5 | 6C | 6C | ✅ |
| "5A" | -10 | 5A (clamped) | 5A | ✅ |

### Result: ✅ PASS

`step_grade()` is correct and consistent with `vocabulary_v1.md`. No issues found. The patch in §3 is not invalidated.

---

## Task 7 — Target-Grade Materialization Audit

### When `target_grade` gets its concrete value

**At resolve-time**, inside `resolve_session()` → `inject_targets()`.

Call chain:
1. `GET /api/week/{week_num}` → `_auto_resolve()` (week.py:43)
2. `_auto_resolve()` → `resolve_session()` for each non-completed, non-user-edited session (week.py:88)
3. `resolve_session()` → `inject_targets(pseudo_day, user_state)` (resolve_session.py:1601)
4. `inject_targets()` reads `prescription_defaults.grade_ref` + `grade_offset` from the exercise, looks up `user_state.assessment.grades[grade_ref]`, calls `step_grade()`, writes result to `exercise_instance["suggested"]["suggested_grade"]` (progression_v1.py:889-891)

### Where it is persisted

| Storage | When | Mutable? |
|---------|------|----------|
| `exercise_instance["suggested"]["suggested_grade"]` | At resolve-time, in the API response | Yes — re-computed on every `GET /api/week/{week_num}` for non-completed sessions |
| `user_state.week_plans[week_key]` (cached plan) | Only for done/skipped sessions via `_cache_completed_resolved()` (week.py:112) | No — frozen once session is marked done/skipped |
| `user_state.working_loads.entries[].next_target_grade` | After feedback submission | No — records the progression target, not the original prescription |

### How it is refreshed after a catalog change

**Non-completed sessions:** Re-resolved on every `GET /api/week/{week_num}` call. The resolver reads `grade_offset` from the catalog (exercises.json) at call-time. A catalog change takes effect **immediately** on the next API call for any non-completed session.

**Completed sessions (done/skipped):** Their resolved data is frozen in `user_state.week_plans` via `_cache_completed_resolved()` (week.py:112-134). The guard at week.py:53-60 skips re-resolution:

```python
if (
    session_entry.get("status") in ("done", "skipped")
    and session_entry.get("resolved")
) or (
    session_entry.get("_user_edited")
    and session_entry.get("resolved")
):
    continue  # skip re-resolution
```

### Post-patch behavior evaluation

| Session state | Behavior after patch | Correct? |
|---|---|---|
| **Already completed** (done/skipped) | Untouched — cached in `week_plans`, skipped by resolver | ✅ Correct — immutable principle respected |
| **Resolved but not yet executed** (current week, status=null) | **Re-resolved on next `GET /api/week/`** with new `grade_offset = -1` → new `suggested_grade` | ✅ Correct — this is the desired behavior |
| **Not yet generated** (future weeks) | Will use new offset when generated | ✅ Correct |

### Silent mid-week re-materialization concern

**Confirmed: non-completed sessions DO re-materialize on every API call.** This is by design in the current architecture — the resolver always re-resolves non-completed sessions. For `route_intervals`, this means:

- If a user has a week plan with `route_intervals` scheduled for Thursday (not yet done), and the catalog patch is deployed on Wednesday, the user will see the **new** target grade (e.g., 6c instead of 6b for a 7a onsighter) when they load the week on Thursday.
- This is **not a UX regression** — it's an improvement (correct intensity). The user sees the updated grade before executing the session.
- There is **no path** where a completed session silently flips its grade.

### Conclusion

The "natural regeneration only, no migration" policy holds. The architecture already handles this correctly:
- Completed sessions: immutable (cached, skipped by resolver)
- Non-completed sessions: re-resolved with current catalog values (desired behavior)
- No migration script needed.

---

## Blast Radius

### Session templates that can select `route_intervals`

`route_intervals` is selected by the resolver when filter criteria match: `pattern: "climbing_intervals"` + `domain: ["power_endurance"]` + `equipment: ["gym_routes"]`.

| Session template | Block | Can select `route_intervals`? | Notes |
|---|---|---|---|
| `power_endurance_gym` | `pe_routes` (line 35) | **YES** — primary selection path | Filters: `pattern=climbing_intervals`, `equipment=gym_routes`. This is the intended and most common selection path. |
| `power_endurance_gym` | `pe_boulder` (line 52) | **NO** — no equipment filter | No `equipment: ["gym_routes"]` constraint, but `route_intervals` requires `gym_routes` in its own `equipment_required`. P0 hard filter would exclude it. |
| `boulder_circuit_gym` | `boulder_circuit_main` (line 31) | **Theoretically possible** — broad filter | Filter includes `climbing_intervals` pattern, but `route_intervals`'s `equipment_required: ["gym_routes"]` would only match if the gym has routes. Unlikely in practice (boulder circuit sessions are typically at boulder-only gyms). |

### Downstream impact of offset change

| Impact area | Effect |
|---|---|
| Target grade display | Higher by 1 whole grade (e.g., 6b → 6c for 7a onsighter) |
| RPE perception | Closer to ~80% max — matches cue text |
| Fatigue cost | Unchanged (`fatigue_cost: 7` is exercise-level, not grade-dependent) |
| Progression tracking | `working_loads.entries[]` for `route_intervals` will track from the new baseline. No retroactive impact on existing entries. |

---

## Proposed Diff

**DO NOT APPLY** — review only.

### Change 1: Exercise catalog

```diff
--- a/backend/catalog/exercises/v1/exercises.json
+++ b/backend/catalog/exercises/v1/exercises.json
@@ -2485,7 +2485,7 @@
         "notes": "Climb route sections with timed rest. Grade 1-2 below onsight. Focus sustained effort.",
         "grade_ref": "lead_max_os",
-        "grade_offset": -2
+        "grade_offset": -1
       },
```

**Note:** The `notes` field ("Grade 1-2 below onsight") should be updated to "Grade 1 below onsight" for consistency, but this is a cosmetic change. Recommend including it in the patch:

```diff
-        "notes": "Climb route sections with timed rest. Grade 1-2 below onsight. Focus sustained effort.",
+        "notes": "Climb route sections with timed rest. Grade 1 below onsight (~80% max). Focus sustained effort.",
```

### Change 2: Test updates (existing tests)

```diff
--- a/backend/tests/test_feedback_loop_e2e.py
+++ b/backend/tests/test_feedback_loop_e2e.py
@@ -240,10 +240,10 @@
 def test_e2e_grade_relative_loop():
-    """route_intervals: grade_ref + grade_offset resolves correctly."""
+    """route_intervals: grade_ref + grade_offset -1 resolves correctly."""
     us = _make_user_state(grades={"lead_max_os": "7c"})
 
-    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -2})
+    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1})
     day = inject_targets(day, us)
     s = day["sessions"][0]["exercise_instances"][0]["suggested"]
     print(f"Suggested grade: {s.get('suggested_grade')}")
-    # "7c" → upper "7C" → step_grade("7C", -2) → "7A"
-    assert s["suggested_grade"] == "7A"
+    # "7c" → upper "7C" → step_grade("7C", -1) → "7B"
+    assert s["suggested_grade"] == "7B"
 
@@ -278,10 +278,10 @@
 def test_e2e_grade_ref_with_plus():
     """step_grade strips '+' before applying offset."""
     us = _make_user_state(grades={"lead_max_os": "7c+"})
 
-    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -2})
+    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1})
     day = inject_targets(day, us)
     s = day["sessions"][0]["exercise_instances"][0]["suggested"]
     print(f"Suggested grade: {s.get('suggested_grade')}")
-    # "7c+" → upper "7C+" → step_grade strips "+" → "7C", offset -2 → "7A"
-    assert s["suggested_grade"] == "7A"
+    # "7c+" → upper "7C+" → step_grade strips "+" → "7C", offset -1 → "7B"
+    assert s["suggested_grade"] == "7B"
```

### Change 3: New test cases (add to `test_feedback_loop_e2e.py`)

See proposed tests in Task 5 above. Four new test cases covering:
- `lead_max_os=7a` → `6C`
- `lead_max_os=8a` → `7C`
- `lead_max_os=6b` → `6A`
- `lead_max_os=6a` → `5C` (clamp edge case)

---

## Deferred Siblings

Exercises flagged during the audit but **not patched** in this brief:

| exercise_id | current offset | possible correct offset | severity | rationale for deferral |
|---|---|---|---|---|
| `emom_bouldering` | -2 | possibly -1 | LOW | Same RPE domain as `otm_bouldering` (-1), but EMOM's fixed 1-min cycle may justify easier problems. Needs KB review — the difference is protocol-specific, not a clear misclassification. Separate brief if confirmed. |

**No other exercises were flagged.** All 30 remaining exercises are consistent with their expected offset per training domain, vocabulary semantics, and exercise class.

### Vocabulary table update (deferred)

`docs/vocabulary_v1.md` line 402 currently lists `route intervals` in the -2 row. After the patch, it should move to the -1 row. This is a documentation-only change — recommend including it in the implementation brief or as a separate D-type brief.

---

## Summary

| Task | Finding | Status |
|---|---|---|
| 1. Locate offset | `exercises.json:2488`, `grade_offset: -2`, single source of truth | ✅ |
| 2. Full catalog table | 31 exercises enumerated, all offsets documented | ✅ |
| 3. Vocabulary cross-check | 1 confirmed discrepancy (`route_intervals`), 1 possible (`emom_bouldering`) | ✅ |
| 4. Shared config check | No shared defaults, no leakage risk — change is isolated | ✅ |
| 5. Test coverage | 2 tests need updating, 4 new tests proposed, 1 test gap flagged | ✅ |
| 6. `step_grade()` sanity | PASS — letter-only, `+` stripped, clamped correctly | ✅ |
| 7. Materialization audit | Natural regeneration works — completed sessions frozen, non-completed re-resolved | ✅ |

**STOP GATE — Awaiting review before implementation.**
