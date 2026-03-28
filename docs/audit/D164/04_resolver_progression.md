# D164 Audit — Resolver, Progression & Exercise Ordering

**Date:** 2026-03-27
**Scope:** `resolve_session.py`, `progression_v1.py`, `adaptation/closed_loop.py`, `exercise_ordering.py`, `equipment_utils.py`, `cluster_utils.py`
**Auditor:** Claude Opus 4.6

---

## 1. P0 Filter Chain (`pick_best_exercise_p0`)

### Filter order (verified correct)
1. Location allowed (hard)
2. Equipment required subset (hard)
3. Equipment required any (hard)
4. Block-level equipment preference (soft — falls back)
5. Finger device preference (soft — partitions pool correctly since B126 fix)
6. Age gate (hard — `age_minimum`)
7. Experience gate — advanced hangboard (hard — `< 2 years`)
8. Experience gate — generic `experience_minimum_years` (hard)
9. Role (hard ANY-match) — **returns None if empty**
10. Dedup exclude_ids (soft — only if alternatives exist)
11. Domain (soft — only if doesn't zero candidates)
12. Pattern (soft — only if doesn't zero candidates)
13. Limitation severe (hard filter)
14. Limitation active (soft — only if alternatives remain)
15. Scoring + deterministic tie-break

### Empty candidate handling
- After role filter (stage 3): returns `(None, trace)` immediately. OK.
- After limitation severe (stage 6): if `base3` is empty, returns `(None, trace)`. OK.
- All soft filters protect against zeroing with `if base_X:` guards. OK.

### Findings

**[P3] Double `expand_equipment()` call — harmless but wasteful.**
`get_location_equipment()` calls `expand_equipment()` at line 642. Then `resolve_session()` calls it again at line 1207 on the already-expanded list. The function is idempotent (checks `not in eq_set` before appending), so no bug, but it's unnecessary work.

**[P3] `expand_equipment()` missing `homewall` in BOULDER_SURFACES implication.**
`homewall` is in `BOULDER_SURFACES` and correctly implies `gym_boulder`. However, note that the implication is one-directional: having `gym_boulder` does NOT imply any specific surface. This is correct by design (exercises with `equipment_required: [gym_boulder]` can be satisfied by any boulder surface).

**[P2] `_apply_load_override` mutates `user_state` via `setdefault`.**
Lines 75-76: `user_state.setdefault("overrides", {})` and `.setdefault("per_exercise", {})` create keys in the caller's `user_state` dict. This is a side effect inside what should be a pure prescription-transformation function. If `user_state` is a shared reference (e.g., when resolving multiple sessions in the same week plan), this mutation leaks across calls. In practice, it only adds empty dicts, so no functional bug — but violates the determinism principle.

**[P3] `score_exercise()` called with empty prefs dict in P0 tie-breaking.**
Line 527-530: `prefs_empty: Dict[str, Any] = {}` is passed. This means the preference bonus arms (+10/+5 for edge/grip match) are never activated inside `pick_best_exercise_p0`. Scoring effectively reduces to recency penalties only. This is likely intentional (prefs are a legacy path), but worth documenting.

---

## 2. Cooldown Logic

### How it works
- `_cooldown_until_date()` reads `user_state["cooldowns"]["per_cluster"][cluster_key]["until_date"]`.
- Cooldown is cluster-based (domain + role + equipment + pattern), not exercise_id-based. This is correct — prevents swapping to a nearly identical exercise.
- Applied only when `block_type == "main"` (or `module_role in ("primary", "main")` for inline blocks). Warmup/cooldown/prehab exercises bypass cooldown. Correct.

### Fallback when all exercises on cooldown
- `_find_cooldown_fallback()` looks for an exercise in the same cluster with non-main role (assistant/secondary), or same domain+equipment with assistant/secondary role.
- If no fallback found: a `cluster_cooldown_downshift` note is set, and the original exercise is kept but with multiplier *= 0.9. **This means cooldown is NOT strictly enforced** — the exercise is still used, just at reduced intensity.

### Findings

**[P3] Cooldown fallback search doesn't check location.**
`_find_cooldown_fallback()` checks equipment compatibility but not `location_allowed`. In theory, a fallback exercise could be selected that isn't allowed at the current location. In practice, the original selected exercise already passed location filtering, and the fallback must match domain+equipment, so this is unlikely to surface.

**[OK] Cooldown correctly set from closed_loop.**
`update_user_state_adjustments()` in `closed_loop.py` sets cooldown of 2 days for `fail`/`too_hard` and 1 day for `hard`. Uses `cluster_key_for_exercise()` for the key. Correct.

---

## 3. Progression / Load Calculation

### Multiplier bounds (closed_loop.py)
- `min_multiplier: 0.85`, `max_multiplier: 1.15`. Clamped via `_clamp()`. **Verified correct.**
- Delta percentages: `too_easy: +2.5%`, `easy: +1%`, `ok: 0%`, `hard: -2.5%`, `too_hard/fail: -5%`.
- These are multiplicative: `next = current * (1 + delta)`. At worst case (fail at 1.15): `1.15 * 0.95 = 1.0925`, still in bounds. At best (too_easy at 0.85): `0.85 * 1.025 = 0.87125`, still in bounds. **No bound escape possible.**

### Streak handling

**[P2] Streak is stored but never used in `compute_next_multiplier`.**
Line 51 in `closed_loop.py`: `_ = streak  # reserved for future rules`. The streak counter increments on hard feedback and resets on easy, but it has zero effect on the multiplier calculation. This is dead code that could mislead developers into thinking streak affects progression. The comment says "reserved for future rules" — acceptable if intentional, but the streak still accumulates in user_state indefinitely.

### `inject_targets()` edge cases

**[P2] Zero bodyweight leads to division by zero in pulling ratio.**
`progression_v1.py` line ~1150 (in `_update_test_from_log` for weighted_pullup): `pulling_ratio = round((total_2rm / bodyweight) * 100, 1) if bodyweight > 0 else 0.0`. This is guarded. However, in `_hangboard_suggested()` and `_max_hang_suggested()`, `bodyweight` is used as `target_total - bodyweight` without checking if `bodyweight == 0`. If bodyweight is 0 (which `_get_bodyweight` can return — it defaults to `0.0`), `suggested_external_load_kg` becomes the full target_total, which would be nonsensical but not a crash. Similar issue in `_loading_pin_suggested()` which doesn't use bodyweight directly.

**[P2] Missing hangboard baseline + missing grade + missing pullup test = silent no-targets.**
In `_hangboard_suggested()`, if there's no hangboard baseline, no grade, and no pullup test, the function falls through to `max_total = bodyweight * 1.10` (the fallback ratio). If bodyweight is also 0, suggested load is 0kg. No error raised, no warning logged. The user gets a prescription with 0kg suggested load.

**[P3] `_pick_hangboard_baseline` fallback to `baselines[0]` ignores edge_mm/grip/hang_seconds.**
Line 119 in `resolve_session.py`: if no exact match is found, it returns `baselines[0]` regardless of whether the edge/grip/duration match. This could suggest a load calibrated for 20mm half-crimp 7s when the exercise is using a different grip or edge size. Currently the system only stores one baseline entry, so this is a theoretical concern.

---

## 4. Exercise Ordering

### Phase-aware sorting
- 13 sort categories + 1 fallback (`main_unclassified`).
- 5 phase maps covering all macrocycle phases.
- `sort_exercises_by_phase()` uses `sorted()` with a compound key `(priority, exercise_id)`. Stable sort + deterministic secondary key = **fully deterministic**. Correct.

### P0 invariant: never lose exercises
- Both `sort_exercises_by_phase()` and `enforce_ordering_constraints()` compare `ids_before` vs `ids_after` sets and fall back to input on mismatch. **Correct and defensive.**

### Ordering constraints

**[P2] Constraint 3 (ARC before pump) can conflict with Constraint 5 (accessories after main).**
Consider: `[warmup, core, aerobic_pure, pe_intervals, cooldown]`. Constraint 5 moves `core` after `pe_intervals`. Constraint 3 moves `aerobic_pure` before `pe_intervals`. Since constraints are applied sequentially (3 before 5), Constraint 5 could re-introduce `core` between `aerobic_pure` and `pe_intervals`, but only if `core` is classified as accessory (it is). The sequential application means the final order depends on execution order. In practice, `core` would be moved after `pe_intervals` by Constraint 5, which is correct. No actual bug found, but the sequential nature of constraints means adding new constraints requires careful analysis.

**[P3] `enforce_ordering_constraints` Constraint 3: `next()` call can raise StopIteration.**
Line 360: `first_pump = next(i for i, ex in enumerate(others) if _cat(ex) in ("threshold", "pe_intervals"))`. This runs only when `pump_indices` is non-empty, but the indices are computed from `result` before aerobics were removed into `others`. After partitioning, if all pump exercises were removed (impossible since they're in `others`, not `aerobics`), `next()` could raise. In practice, pump exercises are always in `others`, so this is safe. Same pattern at line 370 for Constraint 4.

### Category inference

**[P3] `strength_general` with non-pull pattern maps to `antagonist_prehab`.**
Line 159 in `exercise_ordering.py`: if domain is `strength_general` and pattern is not `pull_vertical`/`pull_horizontal`, it defaults to `antagonist_prehab`. This means exercises like bench press (domain=`strength_general`, pattern=`push_horizontal`) are sorted as prehab. In the current catalog, this may be correct (general strength exercises as accessories), but it conflates supplementary strength with prehab.

---

## 5. Prehab Injection

### Zone-to-prehab mapping
- `ZONE_TO_CONTRAINDICATION`: `{elbow: elbow_sensitive, finger: finger_sensitive, shoulder: shoulder_sensitive, wrist: wrist_sensitive}`.
- `_inject_prehab_for_limitations()` looks for exercises with `domain == "prehab_{zone}"` (e.g., `prehab_elbow`).
- Only injects if the zone's prehab domain is NOT already present in the session.
- Correctly checks location and equipment compatibility.

### Findings

**[OK] Prehab injection is deterministic.** Candidates sorted by `exercise_id`, first picked. Correct.

**[P3] Prehab injection doesn't apply limitation load modifiers to injected exercises.**
`_inject_prehab_for_limitations()` creates the instance but never calls `_apply_limitation_to_instance()` on the prehab exercise itself. Since prehab exercises are specifically for the injured zone, they typically shouldn't have contraindications for that zone — but if they do, the load modifier won't be applied.

**[P3] No prehab injection for `monitor` severity.**
The function iterates all zones in `limitation_map`, which includes `monitor` severity. However, for `monitor`, no exercises are filtered out (only `severe` and `active` trigger filtering), and prehab is still injected. This means a `monitor`-level limitation gets a prehab exercise added. This may be intentionally conservative (early prehab), but it's undocumented.

---

## 6. Determinism

### Verified deterministic patterns
- All sorting uses `sorted()` with explicit key functions. No reliance on insertion order.
- No `random` imports anywhere in scope.
- `set()` used only for membership testing, never for iteration order.
- `dict.fromkeys()` used for ordered dedup (line 572). Correct in Python 3.7+.
- `_working_entries()` calls `.sort()` after every append. Correct.
- `_enqueue_test()` calls `.sort()` after every append. Correct.

### Findings

**[P3] `datetime.now()` used in `now_iso()` and `_now_iso()`.**
These are used for `generated_at` and `last_update` timestamps. Not a determinism issue for the core logic (loads, exercises), but means the output includes non-deterministic timestamps. Acceptable — these are metadata, not decision inputs.

**[OK] `id(ex)` used as fallback in `ids_before`/`ids_after` sets.**
In `exercise_ordering.py` lines 285, 300: `ex.get("exercise_id", id(ex))`. This is only used for the P0 invariant check (set equality before/after sort), not for ordering. Since `sorted()` is stable and the exercises are the same objects, `id()` values are consistent within a single call. Correct.

---

## 7. `score_exercise()` Balance Analysis

| Signal | Value | Condition |
|--------|-------|-----------|
| Recency penalty (last 5) | -30 | exercise_id in last 5 selections |
| Recency penalty (last 15) | -15 | exercise_id in last 6-15 |
| Recency penalty (older) | -5 | exercise_id in older history |
| Recency group penalty | -15 | recency_group of exercise seen recently |
| Edge preference bonus | +10 | edge_mm matches preferred (20mm) |
| Grip preference bonus | +5 | grip matches preferred (half_crimp) |

### Analysis

**[P2] Preference bonus can be overwhelmed by recency penalty, but the reverse is also problematic.**
A recently-used exercise with perfect preferences scores: -30 + 10 + 5 = -15.
A never-used exercise with no preference match scores: 0.
This means recency always wins over preferences, which is the correct behavior for variety.

However, consider an exercise that matches the recency_group (-15) but has perfect preferences (+15). Net score: 0. It's treated identically to a never-used exercise with no preference match. The recency_group penalty exactly cancels both preference bonuses, which may not be intentional.

**[P3] Recency window is fixed at last 5/15/all — not time-based.**
The `recent_ex_ids` list is populated from the last `RECENCY_LOOKBACK_WEEKS = 3` weeks of completed sessions. Within that window, the list preserves chronological order. An exercise used 3 weeks ago in position > 15 gets only -5 penalty, while one used yesterday in position 5 gets -30. This is reasonable but means the penalty depends on training frequency — a user training 6x/week has ~18 exercises in last 3 weeks, while a user training 3x/week has ~9. The latter's exercises decay faster through the penalty tiers.

---

## Summary Table

| ID | Severity | Module | Finding |
|----|----------|--------|---------|
| R1 | P2 | resolve_session | `_apply_load_override` mutates `user_state` via `setdefault` (side effect) |
| R2 | P2 | closed_loop | Streak stored but never used — dead code |
| R3 | P2 | progression_v1 | Zero bodyweight produces 0kg suggested load without warning |
| R4 | P2 | progression_v1 | Missing all baselines + zero BW = silent 0kg targets |
| R5 | P2 | exercise_ordering | Constraint interaction (sequential application) requires careful analysis for future additions |
| R6 | P2 | score_exercise | recency_group penalty (-15) exactly cancels preference bonuses (+10+5), possibly unintentional |
| R7 | P3 | resolve_session | Double `expand_equipment()` call — harmless but wasteful |
| R8 | P3 | resolve_session | `score_exercise()` prefs always empty in P0 path |
| R9 | P3 | resolve_session | Cooldown fallback doesn't check location_allowed |
| R10 | P3 | resolve_session | `_pick_hangboard_baseline` fallback ignores edge/grip/duration |
| R11 | P3 | exercise_ordering | `strength_general` non-pull mapped to `antagonist_prehab` |
| R12 | P3 | resolve_session | Prehab injection skips limitation load modifier on injected exercises |
| R13 | P3 | resolve_session | Prehab injected for `monitor` severity (undocumented) |
| R14 | P3 | score_exercise | Recency window is count-based, not time-based — varies with training frequency |

**Total: 0 P1, 6 P2, 8 P3.**

No P1 issues found. The resolver and progression system are well-structured with strong defensive patterns (P0 invariant checks, soft filter fallbacks, deterministic tie-breaking). The P2 items are primarily about edge cases (zero bodyweight), dead code (streak), and subtle scoring balance.
