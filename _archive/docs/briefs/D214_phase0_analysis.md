# D214 — Phase 0 Analysis (read-only)

**Model:** Opus
**Status:** Phase 0 complete — **STOP gate active, awaiting explicit `OK Phase 1` from Daniele**
**Companion brief:** [`D214_source_taxonomy_normalization.md`](./D214_source_taxonomy_normalization.md)
**Date:** 2026-04-20

All line numbers refer to `main` @ current HEAD. No code has been modified.

---

## 3.1 — Writer inventory (every site that writes `assessment.tests.*`)

| Module:line | Writer function | Test field(s) written | Trigger context | Intended `tests_source` label |
|---|---|---|---|---|
| onboarding.py:244 | `_build_user_state_from_onboarding` | `assessment.tests = _normalize_test_keys(data.tests)` (bulk copy from form) | User submits onboarding form | **`measured`** for every key the user actually filled in the form; keys the user left blank are absent (not written) |
| onboarding.py:193–200 | `_normalize_test_keys` | dual-writes `max_hang_20mm_7s_total_kg` and `max_hang_20mm_5s_total_kg` from the single value the user typed (D85 compat) | Called from `_build_user_state_from_onboarding` | **`measured`** on both keys (same origin scalar) |
| progression_v1.py:1126 | `_update_test_from_log` (`max_hang_7s` branch) | `max_hang_20mm_7s_total_kg` + legacy `max_hang_20mm_5s_total_kg` | User completes a test session containing `max_hang_7s` | **`measured`** |
| progression_v1.py:1163 | `_update_test_from_log` (`max_hang_5s` legacy branch) | `max_hang_20mm_5s_total_kg` | Legacy test completion (5s protocol) | **`measured`** |
| progression_v1.py:1185 | `_update_test_from_log` (`repeater_hang_7_3` / `test_repeater_7_3_to_failure`) | `repeater_7_3_max_sets_20mm` | Repeater test completion | **`measured`** |
| progression_v1.py:1192 | `_update_test_from_log` (`test_max_hang_duration_20mm`) | `max_hang_duration_20mm_seconds` | Max-hang-duration test completion | **`measured`** |
| progression_v1.py:1199 | `_update_test_from_log` (`test_l_sit_hold`) | `l_sit_hold_seconds` | L-sit hold test completion | **`measured`** |
| progression_v1.py:1206 | `_update_test_from_log` (`test_hip_flexibility`) | `hip_flexibility_cm` | Hip flexibility test completion | **`measured`** |
| progression_v1.py:1236–1240 | `_update_test_from_log` (`weighted_pullup`) | `weighted_pullup_2rm_total_kg`, `weighted_pullup_1rm_estimated_kg`, `pulling_ratio_pct`, `weighted_pullup_1rm_total_kg` (legacy compat alias) | Weighted pull-up test completion (D84 2RM protocol) | **`measured`** on all 4 keys — they're all direct outcomes of the measurement |
| progression_v1.py:1260 | `_update_test_from_log` (`test_max_pullup_bw`) | `max_pullups_bw` | BW pull-up max test completion | **`measured`** |
| progression_v1.py:1268 | `_update_test_from_log` (`lp_duration_test`) | `lp_duration_test_{hand}_seconds` | Loading pin duration test | **`measured`** (out of D214 scope but trivial to include for completeness) |
| progression_v1.py:1295 | `_update_test_from_log` (`lp_max_test_5s`) | `lp_max_lift_5s_{hand}_kg` | Loading pin max 5s test | **`measured`** (same note as above) |

**Writers that do NOT write `assessment.tests` but could seem to:**

- `progression_v1.py:665 _estimate_hangboard_baseline` — writes `baselines.hangboard[0]`, **reads** `assessment.tests.weighted_pullup_1rm_*`. No `assessment.tests.*` write.
- `progression_v1.py:740 _estimate_pulling_baseline` — writes `baselines.pulling`, **reads** `assessment.tests.weighted_pullup_1rm_*`. No `assessment.tests.*` write. **But** it stamps `baselines.pulling.updated_at = today` even on estimate → this is the F3 root cause (see §3.3).
- `progression_v1.py:1117, 1242` — writes `baselines.hangboard[0]` and `baselines.pulling` from test completion. Those baseline writes already carry `source: "test"` / `source: "test_session"`. Out of D214 scope.

**Ground-truth anchor:** every row above corresponds to a `grep`-verified site (see Phase 0 commands in §3.2 of this doc's production). No memory-based rows.

---

## 3.2 — Reader inventory (every site that reads `assessment.tests.*`)

| Module:line | Reader function | Test field(s) read | What it does with the value | Should gate on `tests_source`? |
|---|---|---|---|---|
| progression_v1.py:703–704 | `_estimate_hangboard_baseline` (Priority 2 fallback) | `weighted_pullup_1rm_estimated_kg` OR `weighted_pullup_1rm_total_kg` | Multiplies by 0.85 → writes `baselines.hangboard[0].max_total_load_kg` when no lead grade. No consultation of user-entered `max_hang_*` scalars. | **YES — new Priority 0** needed: when `max_hang_20mm_7s_total_kg` is present AND `tests_source[that]=="measured"`, use it directly. This closes **F1**. |
| progression_v1.py:756–757 | `_estimate_pulling_baseline` | `weighted_pullup_1rm_estimated_kg` OR `weighted_pullup_1rm_total_kg` | Writes `baselines.pulling` with `updated_at: today` | Partial: writer path needs a companion change — either stop writing `updated_at` on estimate, or switch reader (week.py freshness) to gate on `tests_source`. The prompt mandates the reader-side fix (see week.py row below). |
| resolve_session.py:153–154 | `suggest_max_hang_load` (fallback when no `baselines.hangboard`) | `max_hang_20mm_7s_total_kg` OR `max_hang_20mm_5s_total_kg` | Builds a baseline-shaped fallback dict used to compute suggested load | **Optional — recommended.** If the scalar source is `"estimated"` this fallback produces the same grade-derived 33 kg (ferrero case) number users already see. Gating would downgrade the suggestion to "no suggestion" — possibly worse UX. **Decision for STOP gate:** keep reader source-blind; F1 closure in progression_v1 already means the baseline is populated correctly for measured values. Document in `docs/vocabulary_v1.md`. |
| assessment_v1.py:123 | `_compute_finger_strength` | `max_hang_20mm_7s_total_kg` OR `max_hang_20mm_5s_total_kg` | Computes radar finger score | **NO.** Radar math is source-agnostic by design — an estimated value is better than none for the radar. Keep as-is. |
| assessment_v1.py:154, 158–159 | `_compute_pulling_strength` | `weighted_pullup_1rm_total_kg`, `pullup_submaximal_reps`, `pullup_submaximal_load_kg` | Computes radar pulling score | **NO** (same reason). |
| assessment_v1.py:216 | `_compute_power_endurance` | `repeater_7_3_max_sets_20mm` | Computes radar PE score | **NO** (same reason). |
| assessment_v1.py:297 | `_compute_endurance` | `max_hang_duration_20mm_seconds` | Modifies radar endurance score | **NO** (same reason). |
| week.py:318 | `get_week` → planner wiring | `max_pullups_bw` | Routes pulling test session ID (BW vs weighted) via `_pick_pulling_test_session` | **NO — logical gate, not freshness.** Presence of the scalar is the user-intent signal. Source doesn't change which variant to schedule. |
| week.py:323–328 | `get_week` freshness map — finger axis | (post-B210) reads `baselines.hangboard[0].updated_at` only | Populates `_recent_test_dates["finger"]` for planner freshness gate | **YES — switch to source.** Gate should be: `_recent_test_dates["finger"]` populated **only if** `tests_source.get("max_hang_20mm_7s_total_kg")=="measured"` AND `baselines.hangboard[0].updated_at` is present. B210 already half-fixed this by dropping `estimated_at`; D214 finishes the job by making the gate source-aware instead of relying on absence of `updated_at` (which the pulling path breaks — see next row). |
| week.py:332–337 | `get_week` freshness map — repeater axis | `repeater_7_3_max_sets_20mm` presence | Falls back to macrocycle `start_date` as proxy when no test history | **YES — switch to source.** If `tests_source.get("repeater_7_3_max_sets_20mm")=="measured"`, use `tests.repeater_strength_endurance[-1].date` as today. If `"estimated"` (onboarding-only), DO NOT populate `_recent_test_dates["repeater"]` — currently populates with macrocycle start_date which (post-B210) is now fine because `inject_tests` bypasses freshness; but on periodic retests (not Week-1) the start_date proxy still blocks the Week-3 repeater retest. D214 makes the gate semantically correct. |
| week.py:338–340 | `get_week` freshness map — pulling axis | `baselines.pulling.updated_at` | Populates `_recent_test_dates["pulling"]` | **YES — switch to source.** This is the F3 site. Current behaviour: onboarding estimate writes `updated_at=today` → freshness gate skips pulling retest for 42 days. New behaviour: populate `_recent_test_dates["pulling"]` only if `tests_source.get("weighted_pullup_1rm_total_kg")=="measured"` (or its 2RM sibling). |

**Readers that do NOT need source gating:**

- `compute_assessment_profile` (entire `assessment_v1.py`) — radar math is deliberately source-agnostic. An estimated value produces a plausible score, which is better than `None` for the UI.
- `suggest_max_hang_load` fallback path in `resolve_session.py:153–154` — see table row for rationale. Flag in vocabulary docs; do NOT gate.
- `_pick_pulling_test_session` (`planner_v2.py:564–593`) — uses `max_pullups_bw` presence/count as a routing signal, not a freshness signal.

---

## 3.3 — F1 + F3 closure proof

### F1 — user-entered `max_hang_20mm_7s_total_kg=150` ignored at onboarding

**Current code (pre-refactor):**

```python
# progression_v1.py:682–708 (condensed)
def _estimate_hangboard_baseline(user_state):
    ...
    # Priority 1: estimate from lead_max_rp grade
    lead_rp = (user_state["assessment"]["grades"] or {}).get("lead_max_rp", "")
    if lead_rp and lead_rp in GRADE_TO_HANG_OFFSET:
        estimated = bodyweight + GRADE_TO_HANG_OFFSET[lead_rp]
        grade_used = lead_rp
        source = "estimated_from_grade"
    else:
        # Priority 2: estimate from pullup 1RM
        tests_data = (user_state["assessment"]["tests"] or {})
        pullup_1rm_total = tests_data.get("weighted_pullup_1rm_estimated_kg") or tests_data.get("weighted_pullup_1rm_total_kg")
        if pullup_1rm_total is not None:
            estimated = float(pullup_1rm_total) * 0.85
            source = "estimated_from_pullup"
    ...
```

The user-entered `max_hang_20mm_7s_total_kg` in `assessment.tests` is **never read**. For ferrero, Priority 1 hits (`lead_max_rp=6c` → offset 0) and `baselines.hangboard[0].max_total_load_kg = 33.0`, overriding the measured 150 kg.

**Post-refactor (D214):**

```python
# progression_v1.py _estimate_hangboard_baseline — new Priority 0 (pseudo)
tests_data = (user_state["assessment"]["tests"] or {})
tests_src = (user_state["assessment"]["tests_source"] or {})

direct_value = tests_data.get("max_hang_20mm_7s_total_kg") or tests_data.get("max_hang_20mm_5s_total_kg")
direct_src = tests_src.get("max_hang_20mm_7s_total_kg") or tests_src.get("max_hang_20mm_5s_total_kg") or "estimated"

if direct_value is not None and direct_src == "measured":
    estimated = float(direct_value)
    source = "test"               # baseline source — matches "test" semantics
    grade_used = None
elif lead_rp and lead_rp in GRADE_TO_HANG_OFFSET:
    # existing Priority 1 (unchanged)
    ...
else:
    # existing Priority 2 (unchanged)
    ...
```

**Why this closes F1:**

- Onboarding writer (onboarding.py:244 call site in this brief) additionally writes `assessment.tests_source["max_hang_20mm_7s_total_kg"] = "measured"` because the user typed the value.
- New Priority 0 fires, `direct_value=150.0`, `direct_src=="measured"` → baseline populated with `max_total_load_kg=150.0` + `source="test"`.
- `_estimate_hangboard_baseline` is idempotent: next call sees `source=="test"` and early-returns (line 675), preserving the correct value.

### F3 — pulling baseline `updated_at=today` masks need for retest

**Current code (pre-refactor):**

```python
# progression_v1.py:765–772
new_pulling = {
    ...
    "source": "assessment",
    "updated_at": today,          # ← F3 root cause: stamped on estimate
}
```

```python
# week.py:338–340 (post-B210)
_pulling_bl = (state.get("baselines") or {}).get("pulling") or {}
if _pulling_bl.get("updated_at"):
    _recent_test_dates["pulling"] = _pulling_bl["updated_at"]
```

Week-1 injection path bypasses freshness (B210), so new users see Week-1 pulling test. But periodic retests and last-week-of-phase retests (no `inject_tests`) read the freshness map verbatim → `_recent_test_dates["pulling"]=today` → pulling retest suppressed for 42 days.

**Post-refactor (D214):**

```python
# week.py:338–340 (pulling freshness) — new
_tests_src = ((state.get("assessment") or {}).get("tests_source") or {})
_pulling_bl = (state.get("baselines") or {}).get("pulling") or {}
# Gate on source: only trust updated_at as "real test timestamp" when the
# underlying scalar was measured, not estimated at onboarding.
_pulling_measured = (
    _tests_src.get("weighted_pullup_1rm_total_kg") == "measured"
    or _tests_src.get("weighted_pullup_2rm_total_kg") == "measured"
)
if _pulling_measured and _pulling_bl.get("updated_at"):
    _recent_test_dates["pulling"] = _pulling_bl["updated_at"]
```

Finger freshness gets the symmetric treatment (line 323–328):

```python
# week.py:323–328 (finger freshness) — new
_finger_measured = (
    _tests_src.get("max_hang_20mm_7s_total_kg") == "measured"
    or _tests_src.get("max_hang_20mm_5s_total_kg") == "measured"
)
_hb_baselines = (state.get("baselines") or {}).get("hangboard") or []
if _hb_baselines and _finger_measured:
    _hb_ts = _hb_baselines[0].get("updated_at")
    if _hb_ts:
        _recent_test_dates["finger"] = _hb_ts
```

**Why this closes F3:**

- New user onboards: `tests_source["weighted_pullup_1rm_total_kg"]="measured"` (if user typed it) or `"estimated"` (if absent); `_estimate_pulling_baseline` still writes `updated_at=today` (writer path unchanged for simplicity — the reader gate is sufficient).
- On the natural Week-N retest path (no `inject_tests`), if the scalar was only estimated at onboarding → `_recent_test_dates["pulling"]` is **absent** → freshness gate skipped → retest scheduled. Correct behaviour.
- If the user later completes a real pulling test, `_update_test_from_log` writes `tests_source["weighted_pullup_1rm_total_kg"]="measured"` AND `baselines.pulling.updated_at=date_of_test` → freshness gate correctly suppresses retest until 42 days elapse.

---

## 3.4 — Retro-compat plan

**Policy:** no migration script, no one-shot backfill. Silent default everywhere.

- **Reader default:** whenever any module reads `assessment.tests_source[key]`, absence of the key → treat as `"estimated"`.
- **Writer backfill:** `_update_test_from_log` sets `tests_source[key]="measured"` only for the specific field it writes in that invocation. Fields it doesn't touch are left untouched (may stay missing, default to `"estimated"`).
- **Legacy user state on disk:** no `assessment.tests_source` key present → first read by the new code silently defaults to `"estimated"` for every scalar. No panic, no schema mismatch.
- **Pytest regression:** new test `test_source_taxonomy.py::test_legacy_state_without_tests_source_defaults_to_estimated` loads a blob that matches the pre-D214 shape (no `tests_source`) and asserts the freshness gate treats every scalar as estimated → pulling retest not blocked.
- **Rollback safety:** if D214 is reverted, existing `assessment.tests_source` keys in Supabase become dead data (harmless). No destructive write.

---

## 3.5 — Test plan

Grouped by module. Each item = one new/modified test case name. Minimum-set only; implementation phase will add more as gaps surface.

### `backend/tests/test_source_taxonomy.py` (new file)

- `test_onboarding_user_entered_hang_sets_tests_source_measured` — submit onboarding form with `max_hang_20mm_7s_total_kg=150` → asserts `assessment.tests_source["max_hang_20mm_7s_total_kg"]=="measured"` AND `assessment.tests_source["max_hang_20mm_5s_total_kg"]=="measured"` (dual-write).
- `test_onboarding_absent_scalar_leaves_tests_source_missing` — submit form without `repeater_7_3_max_sets_20mm` → asserts key absent from both `tests` and `tests_source`.
- `test_update_test_from_log_sets_source_measured_on_max_hang_7s` — feedback log for `max_hang_7s` completion → asserts `tests_source["max_hang_20mm_7s_total_kg"]=="measured"`.
- `test_update_test_from_log_sets_source_measured_on_weighted_pullup` — feedback log for weighted pull-up → asserts `tests_source` entries for all 4 scalars written (`weighted_pullup_2rm_total_kg`, `weighted_pullup_1rm_estimated_kg`, `weighted_pullup_1rm_total_kg`, `pulling_ratio_pct`).
- `test_legacy_state_without_tests_source_defaults_to_estimated` — load fixture blob with no `tests_source` key → calls `_estimate_hangboard_baseline` → asserts Priority 1 (grade) path taken, legacy behaviour preserved.

### `backend/tests/test_estimate_hangboard_baseline.py` (new or extension of existing)

- `test_f1_measured_max_hang_used_directly` — state with `tests.max_hang_20mm_7s_total_kg=150` + `tests_source[...]="measured"` + `lead_max_rp=6c` → `_estimate_hangboard_baseline` → asserts `baselines.hangboard[0].max_total_load_kg==150.0` AND `source=="test"` (grade path NOT taken).
- `test_estimated_max_hang_ignored_uses_grade` — same state but `tests_source[...]="estimated"` → asserts existing grade path fires, baseline = bodyweight + offset.

### `backend/tests/test_estimate_pulling_baseline.py` (new or extension)

- `test_f3_writer_behavior_unchanged_for_backcompat` — `_estimate_pulling_baseline` with measured input still writes `updated_at=today` (writer path unchanged — reader-side fix).
- `test_f3_freshness_check_ignores_estimated_pulling` — week.py freshness map: input state with `tests_source["weighted_pullup_1rm_total_kg"]="estimated"` + `baselines.pulling.updated_at=today` → asserts `_recent_test_dates.get("pulling")` is None.
- `test_f3_freshness_check_respects_measured_pulling` — same state but `tests_source[...]="measured"` → asserts `_recent_test_dates["pulling"]==today`.

### `backend/tests/test_week_freshness_sources.py` (new, or folded into existing freshness tests)

- `test_finger_freshness_gated_on_source` — Week 1 generation with `inject_tests=False`, `baselines.hangboard[0].updated_at=today`, `tests_source[...]="estimated"` → asserts finger test still scheduled (not blocked).
- `test_finger_freshness_respects_measured` — same but `tests_source[...]="measured"` → asserts finger test NOT scheduled (freshness honored).
- `test_repeater_freshness_gated_on_source` — symmetric test for repeater axis (includes the macrocycle start_date proxy path).

### Existing tests to audit (expected minor updates, not rewrites)

- `backend/tests/test_update_test_from_log.py` — add assertions on `tests_source` alongside existing `assessment.tests` scalar assertions. Ballpark: 6–10 assertions added across existing test functions, no structural change.
- `backend/tests/test_test_session_e2e.py` — same pattern.
- `backend/tests/test_planner_v1.py` / `test_planner_v2.py` — verify no regression on Week-1 injection path (B210 bypass still works when `inject_tests=True`).

Target coverage delta: +12–15 focused assertions, zero deletions.

---

## 3.6 — Commit plan

**Target: 3 atomic commits, in order. No squash. Each pushable independently. Each message ≤ 72-char subject.**

### Commit 1 — refactor (core code change)

**Subject:** `D214: introduce assessment.tests_source sidecar (F1 + F3 closure)`

**Files touched:**

- `backend/api/routers/onboarding.py` — `_build_user_state_from_onboarding` sets `assessment.tests_source[key]="measured"` for every key copied from `data.tests`; `_normalize_test_keys` mirrors both 7s and 5s source labels.
- `backend/engine/progression_v1.py`:
  - `_estimate_hangboard_baseline`: add new Priority 0 consulting `assessment.tests_source["max_hang_20mm_{7s,5s}_total_kg"]`.
  - `_update_test_from_log`: every branch that writes `at[key] = value` also writes `assessment.tests_source[key] = "measured"` (helper fn to avoid repetition).
- `backend/api/routers/week.py`:
  - Lines 323–328 (finger freshness): gate `_recent_test_dates["finger"]` on `tests_source.get("max_hang_20mm_7s_total_kg") == "measured"` (or 5s alias).
  - Lines 329–337 (repeater freshness): gate `_recent_test_dates["repeater"]` on `tests_source.get("repeater_7_3_max_sets_20mm") == "measured"`.
  - Lines 338–340 (pulling freshness): gate `_recent_test_dates["pulling"]` on `tests_source.get("weighted_pullup_1rm_total_kg") == "measured"` (or 2rm alias).

**Out-of-scope in commit 1 (explicit non-changes):**

- No change to `_estimate_pulling_baseline` writer (still stamps `updated_at=today` — reader-side gate is sufficient and less risky).
- No change to `assessment_v1.py` (radar math stays source-agnostic).
- No change to `resolve_session.py:153–154` fallback (documented in commit 3).
- No change to `baselines.*.source` values (different layer).

### Commit 2 — tests

**Subject:** `D214: tests for tests_source sidecar (F1 + F3 regression)`

**Files touched:**

- `backend/tests/test_source_taxonomy.py` — new file, 5 tests (see §3.5).
- `backend/tests/test_estimate_hangboard_baseline.py` — new or extension (2 tests).
- `backend/tests/test_estimate_pulling_baseline.py` — new or extension (3 tests).
- `backend/tests/test_week_freshness_sources.py` — new file, 3 tests.
- `backend/tests/test_update_test_from_log.py` — assertions added to existing tests (no new tests).
- `backend/tests/test_test_session_e2e.py` — same pattern.

Expected delta: +4 new test files, +~12–15 assertion additions across existing tests. Expected runtime: < 2 s added to `pytest` run.

### Commit 3 — docs

**Subject:** `D214: document assessment.tests_source in vocabulary v1`

**Files touched:**

- `docs/vocabulary_v1.md`: new subsection §2.10.3 (or §2.10.2 extension) formally defining `assessment.tests_source` schema, allowed values `{"estimated", "measured"}`, default policy (silent `"estimated"` on missing key), example state blob, list of writer/reader sites.
- `docs/ROADMAP_CURRENT.md`: mark D214 ✅ Done, move from P1 list.
- `docs/briefs/D214_source_taxonomy_normalization.md` — unchanged (this brief).
- `docs/briefs/D214_phase0_analysis.md` — unchanged (this file).

No catalog changes, no frontend changes, no schema migration.

---

## 4. Summary

F1 and F3 are both closed by this refactor:

- **F1** is closed by commit 1's new Priority 0 in `_estimate_hangboard_baseline`, gated on `tests_source=="measured"`.
- **F3** is closed by commit 1's source-gating in `week.py`'s pulling freshness map — the writer path (`_estimate_pulling_baseline`) stays untouched for retro-compat simplicity; the reader now correctly discriminates estimated from measured.

Retro-compatibility is guaranteed by the silent `"estimated"` default on missing `tests_source` keys. No migration, no schema bump, no breaking changes.

---

## STOP — waiting for `OK Phase 1`

```
═══════════════════════════════════════════════
  D214 PHASE 0 COMPLETE — HARD STOP
═══════════════════════════════════════════════
Risk:          LOW–MEDIUM (touches planner-adjacent reader in week.py +
               two estimators in progression_v1.py).
Commit count:  3 atomic (refactor / tests / docs), no squash.
Closure:       F1 + F3 fully closed. F2/F4/F5–F9 parked (per D-TESTUSER-VERIFY
               scope note).
Protocol:      Awaiting explicit "OK Phase 1" from Daniele before ANY code
               change. Revisions to this analysis are expected if anything
               is unclear — re-enter Phase 0, re-STOP, re-wait.
```
