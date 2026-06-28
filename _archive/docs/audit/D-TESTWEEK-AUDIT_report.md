# D-TESTWEEK-AUDIT — Why is `test_max_hang_7s` not scheduled by "Do a test week first"?

**Status:** COMPLETE
**Date:** 2026-04-19
**Type:** D (read-only audit)
**Risk:** NONE — no code / database mutations

---

## §1 User context

Test user identified by profile match (Finger 23, Pulling 22, Power Endurance 50, Technique 40, Endurance 50) and most-recently-updated Supabase row.

| Field | Value |
|-------|-------|
| Email | `daniele.somensi@ferrero.com` |
| Internal UUID | `98f77487-5f4d-4d74-bd24-90661bbfa3da` |
| Clerk ID | `user_3BGiLKKNuuxxzpBcPanOlxm82xw` |
| Supabase `updated_at` | `2026-04-18T08:13:24Z` |
| discipline | `lead` |
| macrocycle.start_date | `2026-04-20` (A-ACTIVATION-TIMING post-merge, T=1 fallback applied correctly) |
| macrocycle.total_weeks | 12 |
| assessment.profile | finger=23, pulling=22, power_endurance=50, technique=40, endurance=50 |
| assessment.tests | `{}` (empty — no in-app tests run) |
| session_completion_log | `[]` (0 sessions completed) |
| **initial_tests_requested** | **`True`** ← clicked "Do a test week first" |
| test_queue | `None` (never populated — confirmed H-B claim) |
| preferences.finger_training_device | `hangboard` (not `loading_pin`) |
| equipment.gyms[0].equipment | `[]` (no gym equipment recorded) |
| equipment.home | `['hangboard', 'homewall', 'dumbbell', 'band', 'loading_pin', 'pullup_bar', 'kettlebell', 'resistance_band', 'foam_roller']` |
| baselines.hangboard[0] | `{grip: half_crimp, edge_mm: 20, grade_used: 6b, hang_seconds: 7, max_total_load_kg: 45.0, source: "estimated_from_grade", estimated_at: "2026-04-18"}` |
| baselines.pulling | *(absent)* |
| tests (history) | `{}` |

Equipment gate: user has `hangboard` at home — **H-A is false** (no equipment-based exclusion possible for finger tests).

---

## §2 Expected test-week composition

Per the onboarding intent ("Do a test week first" → `initial_tests_requested = True`) and the design doc (`vocabulary_v1.md §4.3`), a user who explicitly requests initial tests should see, in Week 1 of a new macrocycle:

- **Finger max strength test** — current primary is `test_max_hang_7s` (MVC-7s @ 20 mm, per D85). Legacy is `test_max_hang_5s`.
- **Repeater strength-endurance test** — `test_repeater_7_3` (hangboard) or `test_lp_repeater` (loading_pin).
- **Pulling strength test** — `test_max_weighted_pullup` (for users with pulling baseline) or `test_pullup_bw` (BW assessment path, D84).

Expected canonical test_ids: `max_hang_7s_total_load` · `weighted_pullup_2rm` / `max_pullups_bw` · `repeater_7_3_max_sets_20mm`.

---

## §3 Actual test-week composition

Dump of `state.week_plans` (3 weeks generated):

### Week 1 — start 2026-04-20 (base, week 1 of phase)

| Date | Weekday | Slot | Session |
|------|---------|------|---------|
| 2026-04-21 | tue | evening | `test_pullup_bw` |
| 2026-04-22 | wed | lunch | `test_repeater_7_3` |
| 2026-04-23 | thu | evening | `technique_focus_gym` |
| 2026-04-24 | fri | evening | `boulder_circuit_gym` |

Targets: `hard_days=4, finger_days=1`. Hard-day count: 1. `skipped_tests = None`.

### Week 2 — start 2026-04-27

| Date | Weekday | Slot | Session |
|------|---------|------|---------|
| 2026-04-28 | tue | evening | `boulder_circuit_gym` |
| 2026-04-29 | wed | lunch | `finger_maintenance_home` |
| 2026-04-30 | thu | evening | `technique_focus_gym` |
| 2026-05-01 | fri | evening | `boulder_circuit_gym` |

### Week 3 — start 2026-05-04

| Date | Weekday | Slot | Session |
|------|---------|------|---------|
| 2026-05-05 | tue | evening | `boulder_circuit_gym` |
| 2026-05-06 | wed | lunch | `test_repeater_7_3` |
| 2026-05-07 | thu | evening | `technique_focus_gym` |
| 2026-05-08 | fri | evening | `boulder_circuit_gym` |

**Missing entirely from all 3 weeks: any finger max-strength test** (`test_max_hang_5s` OR `test_max_hang_7s` OR `test_lp_max_5s`).

---

## §4 Hypothesis testing

### H-A — Equipment gate blocks test ❌ **FALSE**

User's `equipment.home` includes `"hangboard"`. `test_max_hang_5s.json` and `test_max_hang_7s.json` both declare `required_equipment = ["hangboard"]`. The P0 equipment filter would pass. (Note: the planner's Pass 3 never references `test_max_hang_7s` — see H-C — so this gate is never consulted for the 7s variant anyway.)

### H-B — `test_queue` not populated ⚠️ **TRUE but orthogonal**

Confirmed: `state.test_queue = None`. Onboarding does NOT populate `test_queue` (it only sets `state.initial_tests_requested = True`; see `backend/api/routers/onboarding.py:386`). But **`test_queue` is not the mechanism that drives initial-week test injection** — that mechanism is `inject_tests=True` → Pass 3 of `generate_phase_week`, which reads `state.baselines` and `state.tests`, not `test_queue`. So while the empty `test_queue` is a real observation, it is not the cause of the missing max-hang test.

### H-C — "Do a test week first" bypasses max_hang by design / code path ✅ **PARTIALLY CONFIRMED — this is the primary root cause for the 7s variant**

Full flow traced from button click to session placement:

1. Frontend onboarding sets `test_week_requested=True` on the review step.
2. `POST /api/onboarding/complete` → `backend/api/routers/onboarding.py:385-386`:
   ```python
   if data.test_week_requested:
       state["initial_tests_requested"] = True
   ```
3. Frontend later loads `/today`, which calls `GET /api/week/{num}` → `backend/api/routers/week.py:307-312`:
   ```python
   want_tests = (
       state.get("initial_tests_requested")
       and ctx.get("is_first_week_of_phase")
       and ctx["phase_id"] == "base"
       and not is_last
   )
   ```
4. Week router calls `generate_phase_week(..., inject_tests=want_tests, ...)` (line 361).
5. Inside `generate_phase_week` (`backend/engine/planner_v2.py:1261-1284`), Pass 3 runs because `inject_tests=True`. The test session list is built:
   ```python
   _finger_test_sid = "test_lp_max_5s" if finger_device == "loading_pin" else "test_max_hang_5s"
   _repeater_test_sid = "test_lp_repeater" if finger_device == "loading_pin" else "test_repeater_7_3"
   _pulling_test_sid = _pick_pulling_test_session(pulling_baseline, max_pullups_bw)
   _test_schedule = [
       (_finger_test_sid, True),
       (_repeater_test_sid, True),
       (_pulling_test_sid, False),
   ]
   ```
6. The **only** finger test referenced is `test_max_hang_5s` (or `test_lp_max_5s`). `test_max_hang_7s` is **never** an option.

Additionally, the standalone `generate_test_week` function (`planner_v2.py:1496`, `:1555`) also hardcodes `test_max_hang_5s`. That function is currently **not wired up** — grep confirms no router calls `generate_test_week`; the test-week intent runs entirely through Pass 3 of the phase-week generator.

`_SESSION_META` (`planner_v2.py:53`) registers only `test_max_hang_5s`. There is no `_SESSION_META` entry for `test_max_hang_7s`, so even if a caller tried to route the 7s variant through the Pass-3 placer, meta lookup would fail (`test_meta is None` at line 1329, `continue`).

**Conclusion:** the 7s catalog file (`backend/catalog/sessions/v1/test_max_hang_7s.json`) is an orphan. Created by D85 but never wired into the planner. Every finger-test injection path uses the 5s variant.

### H-D — Placed in a later week ❌ **FALSE**

Confirmed by inspection: no `test_max_hang_*` session appears in Week 1, Week 2, or Week 3 of the user's macrocycle. Phase gating of `_PHASE_TEST_MAP["base"]["finger"] = False` would also suppress finger-test retest in a normal (non-initial) base-phase week anyway, so even later base weeks would not carry it. (Strength/power phase would re-enable it at week 5-ish, but that's 5 weeks out — not "scheduled later in Week 1 intent".)

### H-E — Catalog bug ❌ **FALSE**

`backend/catalog/sessions/v1/test_max_hang_7s.json` exists, parses cleanly, declares:
- `id = "test_max_hang_7s"`
- `required_equipment = ["hangboard"]`
- `test_id = "max_hang_7s_total_load"` (canonical per D85)
- one module `finger_max_strength_test`, schema-valid.

The file is well-formed. The bug is upstream of the catalog — **the planner never references this file**.

### H-F (new) — Freshness check misuses `estimated_at` for finger axis ⚠️ **SECONDARY BUG, ALSO TRUE**

Even if H-C were fixed and the planner had referenced `test_max_hang_7s` (or even `test_max_hang_5s`), Pass 3 would still **skip the finger test in Week 1** for this user. Reason:

`backend/api/routers/week.py:323-328` populates the freshness map:
```python
_hb_baselines = (state.get("baselines") or {}).get("hangboard") or []
if _hb_baselines:
    # B191/Finding-A: check updated_at (real test) then estimated_at (onboarding estimate)
    _hb_ts = _hb_baselines[0].get("updated_at") or _hb_baselines[0].get("estimated_at")
    if _hb_ts:
        _recent_test_dates["finger"] = _hb_ts
```

For the ferrero user: no `updated_at` exists (no real test completed), so it falls back to `estimated_at = "2026-04-18"` — a timestamp set at onboarding by `backend/engine/progression_v1.py:722` when `_estimate_hangboard_baseline` populates the baseline from the user's declared RP grade (`source = "estimated_from_grade"`).

Then in Pass 3 freshness check (`planner_v2.py:1315-1323`):
```python
last_date_str = _recent.get(test_type) if test_type else None
if last_date_str:
    try:
        days_ago = (_week_start - _parse_date(last_date_str)).days
        if 0 <= days_ago < TEST_FRESHNESS_DAYS:  # TEST_FRESHNESS_DAYS = 42
            continue  # Skip — test completed recently
```

Math for ferrero: `_week_start = 2026-04-20`, `last = 2026-04-18`, `days_ago = 2`. `2 < 42` → **finger test skipped as "recent"**.

Contrast with pulling (`week.py:338-340`):
```python
_pulling_bl = (state.get("baselines") or {}).get("pulling") or {}
if _pulling_bl.get("updated_at"):
    _recent_test_dates["pulling"] = _pulling_bl["updated_at"]
```
Only `updated_at` is read for pulling (no `estimated_at` fallback). Since ferrero has no pulling baseline at all, `_recent_test_dates["pulling"]` is absent → freshness check is skipped → `test_pullup_bw` IS placed in Week 1. ✅

Same for repeater (`week.py:329-337`): reads from `tests.repeater_strength_endurance[-1].date` or falls back to macrocycle start_date *only* if an assessment test value exists. For ferrero, neither is set → freshness map absent → `test_repeater_7_3` IS placed. ✅

So three axes, three freshness behaviors — asymmetric, by accident of which fallback logic was added in B191. **Only the finger axis uses `estimated_at` as a freshness proxy, which conflates "I guessed your baseline from your declared grade" with "you actually did this test 2 days ago".**

---

## §5 Root cause

The user's observation ("max-hang test is missing") has **two compounding root causes**, either of which is individually sufficient to hide `test_max_hang_7s` specifically:

### RC1 (for the 7s variant): orphan catalog
`test_max_hang_7s.json` was added (presumably by D85) but no planner code path references it. Every finger-test injection site hardcodes `test_max_hang_5s`:
- `planner_v2.py:1276` — Pass 3 of `generate_phase_week` (the live path for onboarding + periodic reminders)
- `planner_v2.py:1496, :1555` — standalone `generate_test_week` (currently not wired)
- `planner_v2.py:53` — `_SESSION_META` registration

Even if the Pass-3 freshness bug (RC2) were fixed tomorrow, **the user would get `test_max_hang_5s` — not `test_max_hang_7s`**. The 7s catalog is dead code at the planner level.

### RC2 (for any finger test in Week 1 for this user): freshness-check false positive
Pass 3 skips the finger test because `baselines.hangboard[0].estimated_at = 2026-04-18` is interpreted as a recent test completion, even though it was set at onboarding from an *estimate* (`source = "estimated_from_grade"`), not from a real test. Intentional `inject_tests=True` bypasses phase gating (`planner_v2.py:1288`) but does **not** bypass freshness (`:1315`).

This is why `test_pullup_bw` and `test_repeater_7_3` DID appear in Week 1 for ferrero (neither has an `estimated_at` fallback in the freshness map), but no max-hang session did.

---

## §6 Recommended fix

Two separate briefs. Sequencing matters: fix RC2 first (makes finger tests work at all), then fix RC1 (upgrades the chosen finger test from 5s to 7s).

### Brief A (fix RC2) — freshness check must bypass `estimated_from_grade` baselines

**Type:** B (bugfix). **Effort:** S. **Risk:** LOW (scoped to one fallback in `week.py`, plus one regression test). **Touches engine:** YES → follows the STOP-gate protocol from CLAUDE.md.

Options:
1. **Preferred.** In `week.py:323-328`, drop the `estimated_at` fallback entirely: only use `updated_at` (the "real test completed" timestamp), matching the pulling and repeater paths. Asymmetry resolved.
2. Alternative: preserve the fallback but honor `source`: if `source == "estimated_from_grade"`, do not populate `_recent_test_dates["finger"]`.
3. Alternative: in Pass 3, when `inject_tests=True`, also bypass the freshness check (not just the phase gate). Matches the semantic of "user explicitly asked for an initial test week".

Option 1 is the cleanest — it removes the asymmetry between axes. Option 3 is more targeted but widens the exception surface.

Regression test: user with `initial_tests_requested=True` + `baselines.hangboard[0].source="estimated_from_grade"` + `estimated_at=today()` → Week 1 includes `test_max_hang_5s` (or whichever ID is chosen after Brief B).

### Brief B (fix RC1) — wire `test_max_hang_7s` into the planner

**Type:** B (bugfix) or C (catalog migration). **Effort:** S. **Risk:** MEDIUM (changes the test id stored in `baselines.hangboard[0]` after test completion; downstream progression code reads `hang_seconds` to interpret). **Touches engine:** YES → STOP-gate.

Scope:
1. Add `test_max_hang_7s` to `_SESSION_META` (`planner_v2.py:53` area) with the same fields as `test_max_hang_5s`.
2. Decide: is the 5s variant deprecated entirely (D85 migration), or do both coexist (e.g., 5s for novices, 7s for advanced)? This is a design call — design doc v1.1 says MVC-7 is the primary; treat 5s as legacy-only.
3. Assuming 7s-only going forward:
   - Replace `"test_max_hang_5s"` with `"test_max_hang_7s"` at `:1276` and `:1496` and `:1555`.
   - Keep `"test_lp_max_5s"` for loading-pin users (orthogonal — pin protocol is unrelated to hang time).
   - Remove `test_max_hang_5s` from `_SESSION_META`, OR leave it for backwards compat reading of old logs but never schedule it.
4. Update `_test_type_map` at `:1267` so `test_max_hang_7s` maps to axis `finger`.
5. Verify `update_test_from_log` (used by feedback router) writes the correct `test_id` for 7s results (`max_hang_7s_total_load` per D85 and vocabulary §4.3).
6. Test: existing `test_planner_v1.py:137` asserts `test_id == "max_hang_7s_total_load"` for a scheduled finger test — confirm which session id drives that and whether the test is currently green (grep suggests yes via a different path).

Estimated effort combined: M (engine touch × 2 briefs, requires STOP gates). Risk: LOW–MEDIUM. Observable on first post-fix onboarding.

---

## §7 Related issues (parked, not fixed by this audit)

1. **`generate_test_week` is dead code.** `planner_v2.py:1504-1674` implements a standalone 1-week test plan generator, but no router calls it. The live path uses `generate_phase_week(inject_tests=True)`. Either delete `generate_test_week` in a cleanup brief, or wire it to a new "standalone test week" use case. Current risk: drift between the two implementations (e.g., RC1/RC2 must be fixed in both places).

2. **`test_queue` is never initialized by onboarding.** Observed for ferrero (`test_queue = None`). Used by periodic test reminders (`should_show_test_reminder`), but the reminder code does not depend on `test_queue` contents — it triggers on `(current_week_num + 1) % 6 == 0`. If `test_queue` is intended for anything else, the onboarding init is missing. If unused, consider removing from the schema.

3. **`_finger_test_sid` decision ignores the user's actual hangboard vs loading_pin preference depth.** `preferences.finger_training_device == "hangboard"` → 5s variant. A user with BOTH `hangboard` and `loading_pin` available (ferrero's case) gets the hangboard default. Fine for now, but verify against D120 (finger device preference) that this is the intended default.

4. **`assessment.tests = {}` for ferrero.** The assessment flow computed a profile (Finger=23, Pulling=22…) but did not store the underlying test values. This is the same onboarding — if test values *are* supposed to be stored, `assessment.tests` should not be empty after a successful assessment. Possibly related to a change in how onboarding flows populate that key.

5. **`macrocycle.phases[0]` has `start_date=None, total_weeks=None, week_indices=None`.** Not a cause of this bug, but the phase object is underpopulated at serialization time (the planner reconstructs these at runtime from the macrocycle root `start_date`). Cosmetic concern — low priority.

6. **`equipment.gyms[0].equipment = []`.** Ferrero declared gym availability but no gym equipment, so every gym session falls back to the default bouldering pool. Could surface wrong-surface session issues in other scenarios. Not directly in scope.

---

```
═══════════════════════════════════════════════
  D-TESTWEEK-AUDIT COMPLETE — STOP
═══════════════════════════════════════════════
Root cause:      TWO compounding bugs.
                 RC1 — planner hardcodes test_max_hang_5s (7s file is orphan)
                 RC2 — freshness check treats onboarding "estimated_at"
                       as a real test timestamp, skipping finger test
                       for 42 days after onboarding.
Recommended fix: Brief A (B, S, low risk) — drop estimated_at fallback
                   in week.py freshness map → finger tests actually run.
                 Brief B (B/C, S, med risk) — wire test_max_hang_7s
                   into _SESSION_META and replace 5s references → users
                   get the D85 primary protocol instead of legacy.
                 Both briefs touch planner_v2.py → STOP-gate protocol.
Effort:          S + S ≈ M combined.
Ready for Daniele to decide: open briefs or park.
```
