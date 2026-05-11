# B214 + B215 — Phase 0 analysis

**Scope:** close remaining Bundle B items on `backend/engine/progression_v1.py`.
**Model used for analysis:** Opus.
**STOP gate:** after this doc, wait for Daniele's explicit *OK Phase 1* before any code change.

---

## 1. B214 — axis dispatch consolidation

### 1.1 Premise re-check

The brief says:

> `progression_v1.py` has if/elif chains dispatching on `test_id` to determine
> axis/baseline_key/field, replicated across multiple functions
> (`_update_test_from_log`, `_estimate_*_baseline`, etc.)

Grepping the module surfaces a slightly different picture. The full scope is listed below — read it before we decide whether the brief proceeds as written.

### 1.2 Actual dispatch sites (verified)

Command: `rg -n 'exercise_id\s*(==|in)\s*\("?(max_hang|weighted_pullup|repeater|test_l_sit|test_hip|test_max_hang_duration|test_max_pullup|lp_duration|lp_max)'`

| Function | Line | Branches | Nature of dispatch |
|---|---|---|---|
| `_relevant_setup` | 237, 243 | `max_hang_5s/7s`, `limit_bouldering` | setup-key shape (edge_mm/grip/load_method vs surface) |
| `_setup_key` | 254, 260 | same two | serializer for working-load entry key |
| `inject_targets` | 823 | `max_hang_5s/7s` | special `_max_hang_suggested` call + working-load lookup |
| `inject_targets` | 847 | `weighted_pullup` | pulling-baseline-anchored load suggestion |
| `inject_targets` | 956 | exclusion guard `not in (max_hang_5s/7s, weighted_pullup)` | generic total_load branch |
| `_update_test_from_log` | 1122 | `max_hang_7s` | history + baseline + 2 scalars + dual `_mark_measured` |
| `_update_test_from_log` | 1160 | `max_hang_5s` | history + baseline + 1 scalar + dual `_mark_measured` |
| `_update_test_from_log` | 1197 | `repeater_hang_7_3`, `test_repeater_7_3_to_failure` | history + 1 scalar + `_mark_measured` |
| `_update_test_from_log` | 1220 | `test_max_hang_duration_20mm` | 1 scalar + `_mark_measured` |
| `_update_test_from_log` | 1228 | `test_l_sit_hold` | 1 scalar + `_mark_measured` |
| `_update_test_from_log` | 1236 | `test_hip_flexibility` | 1 scalar + `_mark_measured` |
| `_update_test_from_log` | 1244 | `weighted_pullup` | history + baseline + 4 scalars + 1RM estimation + `_mark_measured` |
| `_update_test_from_log` | 1297 | `test_max_pullup_bw` | 1 scalar + `_mark_measured` |
| `_update_test_from_log` | 1305 | `lp_duration_test` | per-hand scalar + `_mark_measured` |
| `_update_test_from_log` | 1314 | `lp_max_test_5s` | per-hand baseline list mutate + per-hand scalar + `_mark_measured` |
| `apply_feedback` | 1405 | `max_hang_5s/7s` | streak counter bookkeeping (`max_hang_hard_streak` etc.) |

**Dispatch key:** `exercise_id`, **not** `test_id`. The namespaces are distinct:

- `exercise_id` → catalog exercise, dispatched on in `progression_v1.py`.
- `test_id` → appended to history entries (`"max_hang_7s_total_load"`, `"weighted_pullup_2rm"`) and to `test_queue[]` items (vocabulary §4.3).
- `assessment.tests` scalar keys → third namespace (`max_hang_20mm_7s_total_kg`, `weighted_pullup_1rm_total_kg`, …).

No function in `progression_v1.py` dispatches on `test_id` directly. A `_TEST_TYPE_MAP` keyed by `test_id` — as the brief sketched — would not match any existing call site.

### 1.3 Nature of the branches

The 10 branches in `_update_test_from_log` are **not** pure field lookups. Each does at least one of:

- heterogeneous scalar writes (1–4 keys, sometimes with dual-key compat)
- optional append to a history tier (`tests.max_strength`, `tests.repeater_strength_endurance`, `tests.pulling_strength`)
- optional baseline mutation (`baselines.hangboard[0]`, `baselines.pulling`, `baselines.loading_pin[hand]`)
- per-hand routing (`lp_*`) — not expressible as a static map without extra indirection
- 1RM estimation from 2RM (`weighted_pullup` only)

A map of shape `{exercise_id: {axis, baseline_key, field}}` would capture ~40% of the branch body and leave the other 60% still in if-elif. It doesn't shrink the call sites to "look it up and write"; it adds a lookup step per branch without eliminating the branch.

### 1.4 Realistic refactor options

**Option A — declarative scalar-write map (narrow scope, recommended).**
Extract only the part that's genuinely duplicated: the `_mark_measured(*keys)` call. Today each branch maintains its own hand-picked list of keys to mark. A writer that adds a new scalar without calling `_mark_measured` silently drifts from D214's contract.

```python
_TEST_EXERCISE_SCALARS: dict[str, tuple[str, ...]] = {
    "max_hang_7s": ("max_hang_20mm_7s_total_kg", "max_hang_20mm_5s_total_kg"),
    "max_hang_5s": ("max_hang_20mm_5s_total_kg", "max_hang_20mm_7s_total_kg"),
    "repeater_hang_7_3": ("repeater_7_3_max_sets_20mm",),
    "test_repeater_7_3_to_failure": ("repeater_7_3_max_sets_20mm",),
    "test_max_hang_duration_20mm": ("max_hang_duration_20mm_seconds",),
    "test_l_sit_hold": ("l_sit_hold_seconds",),
    "test_hip_flexibility": ("hip_flexibility_cm",),
    "weighted_pullup": (
        "weighted_pullup_2rm_total_kg",
        "weighted_pullup_1rm_estimated_kg",
        "pulling_ratio_pct",
        "weighted_pullup_1rm_total_kg",
    ),
    "test_max_pullup_bw": ("max_pullups_bw",),
    # per-hand keys (lp_duration_test, lp_max_test_5s) stay inline — format string
}
```

- Each branch still does its bespoke work (history/baseline), but the `_mark_measured` call becomes a single line: `_mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])`.
- Unit test: every key in the map is a canonical `assessment.tests.*` key (cross-check against a hard-coded list inside the test; no need for a new vocabulary constant).
- Unit test: every `exercise_id` branch in `_update_test_from_log` has a matching entry in the map (introspect via `ast`, or a runtime decorator — whichever is simpler).

**Option B — full axis+baseline declarative map (brief as written).**
Replicates axis/baseline routing in the map. Given 1.3 it does not actually shrink the branches and adds an indirection layer. **Not recommended.**

**Option C — do nothing, add invariant test only.**
Write a pytest that replays the current behaviour and asserts `tests_source` is set for every `assessment.tests` key after a synthetic feedback log. Catches drift without refactoring. Low code churn but leaves the `_mark_measured` duplication in place.

### 1.5 Recommendation

**Go with Option A, re-scoped brief.** It closes the actual drift risk (scalar-marking drift) without over-engineering. Acceptance criteria become:

- `_TEST_EXERCISE_SCALARS` map exists, keys match all `exercise_id` branches in `_update_test_from_log`.
- Every branch calls `_mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])` instead of hand-listing keys.
- Unit test asserts map keys == branch labels (no drift).
- Unit test asserts every value in the map is a valid `assessment.tests.*` scalar key (whitelist verified against vocabulary §2.10 / onboarding form).
- Existing tests pass unchanged (no behavior change).

Import-time invariant vs vocabulary §4.3: **not applicable**. §4.3 lists `test_queue[].test_id` values, not `exercise_id` or `assessment.tests.*` scalar keys. Adding a new constant for `assessment.tests.*` keys is a larger undertaking (needs doc + tests) — defer to a follow-up if drift becomes a problem.

### 1.6 Post-refactor sample (max_hang_7s branch)

Before (lines 1122–1157):

```python
if exercise_id == "max_hang_7s":
    # ... compute total / external / append history / mutate baselines ...
    at["max_hang_20mm_7s_total_kg"] = total
    at["max_hang_20mm_5s_total_kg"] = total
    _mark_measured("max_hang_20mm_7s_total_kg", "max_hang_20mm_5s_total_kg")
```

After:

```python
if exercise_id == "max_hang_7s":
    # ... compute total / external / append history / mutate baselines ...
    at["max_hang_20mm_7s_total_kg"] = total
    at["max_hang_20mm_5s_total_kg"] = total
    _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])
```

Delta: 1 line per branch, identical semantics, centralised source of truth.

---

## 2. B215 — pulling fallback chain symmetry

### 2.1 Current state

`_estimate_pulling_baseline` (lines 763–799):

```python
def _estimate_pulling_baseline(user_state: Dict[str, Any]) -> None:
    pulling = (user_state.get("baselines") or {}).get("pulling") or {}
    if pulling.get("source") in ("test", "test_session"):
        return                                           # guard: never overwrite real test

    bodyweight = _get_bodyweight(user_state)
    if bodyweight <= 0:
        return

    tests_data = ((user_state.get("assessment") or {}).get("tests") or {})
    pullup_1rm_total = (
        tests_data.get("weighted_pullup_1rm_estimated_kg")    # D84 preferred
        or tests_data.get("weighted_pullup_1rm_total_kg")     # legacy
    )
    if pullup_1rm_total is None:
        return

    pullup_1rm_total = float(pullup_1rm_total)
    max_external = _round_half_step(pullup_1rm_total - bodyweight)
    today = datetime.now().strftime("%Y-%m-%d")

    new_pulling: Dict[str, Any] = {
        "weighted_pullup_1rm_total_kg": _round_half_step(pullup_1rm_total),
        "bodyweight_kg": bodyweight,
        "max_external_load_kg": max_external,
        "source": "assessment",
        "updated_at": today,
    }
    user_state["baselines"]["pulling"] = new_pulling
```

- No Priority 0 source-gated read. Every call writes `source="assessment"` + `updated_at=today` regardless of whether the scalar is `measured` or `estimated`.
- F3 was closed reader-side in `week.py::get_week` (freshness gate ignores the baseline unless `tests_source == "measured"`).

### 2.2 Asymmetry vs `_estimate_hangboard_baseline`

Hangboard (lines 665–760) has:

- Priority 0 — measured scalar → `source="test"` + `updated_at`
- Priority 1 — grade estimate → `source="estimated_from_grade"` + `estimated_at`
- Priority 2 — pullup proxy → `source="estimated_from_pullup"` + `estimated_at`

Pulling has a single path, always stamping `source="assessment"` + `updated_at`. A new reader that checks `baselines.pulling.source in {"test", "test_session"}` to decide freshness would incorrectly treat estimates as real tests. The reader-side gate in `week.py` is load-bearing.

### 2.3 Post-refactor body (proposed)

```python
def _estimate_pulling_baseline(user_state: Dict[str, Any]) -> None:
    pulling = (user_state.get("baselines") or {}).get("pulling") or {}
    if pulling.get("source") in ("test", "test_session"):
        return

    bodyweight = _get_bodyweight(user_state)
    if bodyweight <= 0:
        return

    tests_data = ((user_state.get("assessment") or {}).get("tests") or {})
    tests_src = ((user_state.get("assessment") or {}).get("tests_source") or {})

    pullup_1rm_total = (
        tests_data.get("weighted_pullup_1rm_estimated_kg")
        or tests_data.get("weighted_pullup_1rm_total_kg")
    )
    if pullup_1rm_total is None:
        return

    pullup_1rm_total = float(pullup_1rm_total)
    max_external = _round_half_step(pullup_1rm_total - bodyweight)
    today = datetime.now().strftime("%Y-%m-%d")

    # B215: symmetry with _estimate_hangboard_baseline. If the user-entered 1RM
    # was marked measured at onboarding (D214), stamp source="test" + updated_at
    # so future readers can gate on baseline source without consulting tests_source.
    measured_1rm = (
        tests_src.get("weighted_pullup_1rm_estimated_kg") == "measured"
        or tests_src.get("weighted_pullup_1rm_total_kg") == "measured"
        or tests_src.get("weighted_pullup_2rm_total_kg") == "measured"
    )

    new_pulling: Dict[str, Any] = {
        "weighted_pullup_1rm_total_kg": _round_half_step(pullup_1rm_total),
        "bodyweight_kg": bodyweight,
        "max_external_load_kg": max_external,
    }
    if measured_1rm:
        new_pulling["source"] = "test"
        new_pulling["updated_at"] = today
    else:
        new_pulling["source"] = "estimated_from_assessment"
        new_pulling["estimated_at"] = today

    if not user_state.get("baselines"):
        user_state["baselines"] = {}
    user_state["baselines"]["pulling"] = new_pulling
```

### 2.4 Behavior delta

| Onboarding input | Pre-B215 | Post-B215 |
|---|---|---|
| User enters `weighted_pullup_1rm_total_kg = 130` | `source="assessment"`, `updated_at=today` | `source="test"`, `updated_at=today` |
| Grade-based estimate (no 1RM entered) — currently not implemented (estimator returns early) | no baseline | no baseline |
| 1RM absent entirely | no baseline | no baseline |
| Previous call wrote `source="test_session"` from a real test | guard returns early — unchanged | guard returns early — unchanged |

The only observable semantic change is the `source` value for user-entered 1RM: `"assessment"` → `"test"` for measured, new `"estimated_from_assessment"` for the (currently-uncovered) estimated path. Key change: `updated_at` → `estimated_at` field for estimated path.

### 2.5 Downstream impact check

Grep for readers of `baselines.pulling.source`:

- `inject_targets` (line 857) reads `pulling.weighted_pullup_1rm_total_kg` directly. Source-blind. **OK.**
- `week.py` freshness gate reads `tests_source["weighted_pullup_1rm_total_kg"]`, not the baseline source. **OK.**
- `_estimate_pulling_baseline` itself checks `source in ("test", "test_session")` — now also blocks on a previously-measured onboarding value, which is desired (don't re-estimate what the user entered). **OK.**

No external reader depends on the old `"assessment"` sentinel. Safe to replace.

### 2.6 F3 regression guarantee

`test_freshness_map_gating` in `backend/tests/test_source_taxonomy.py` (D214) replays the `week.py` freshness logic inline and asserts pulling retests are NOT suppressed when `tests_source.weighted_pullup_1rm_total_kg != "measured"`. B215 doesn't touch `week.py`; this test stays green.

Empirical (ferrero) regression: same reasoning — F3's proof is that `test_pullup_bw` got scheduled because the pulling scalar is absent. B215 doesn't affect that scheduling.

---

## 3. Test plan

### 3.1 B214 tests (new file `backend/tests/test_axis_dispatch.py`)

| Test | What it asserts |
|---|---|
| `test_TEST_EXERCISE_SCALARS_covers_branches` | Every `exercise_id` branch in `_update_test_from_log` has an entry in `_TEST_EXERCISE_SCALARS`. Uses `ast.parse` on the source file. |
| `test_TEST_EXERCISE_SCALARS_values_are_valid_keys` | Every value in the map is in the hand-curated `_CANONICAL_ASSESSMENT_TEST_KEYS` whitelist. |
| `test_update_test_from_log_max_hang_7s_still_marks_measured` | Regression: after refactor, `tests_source` keys for max_hang_7s branch are still set. |
| `test_update_test_from_log_weighted_pullup_still_marks_all_four` | Regression: all 4 pullup scalars still get `_mark_measured`. |

### 3.2 B215 tests (extend `backend/tests/test_estimate_pulling_baseline.py` — create if missing)

| Test | What it asserts |
|---|---|
| `test_measured_pullup_1rm_stamps_source_test` | User enters 130kg + `tests_source["weighted_pullup_1rm_total_kg"]="measured"` → `baselines.pulling.source == "test"`, `updated_at` present. |
| `test_estimated_pullup_1rm_stamps_source_estimated_from_assessment` | Scalar present but `tests_source` missing → `source == "estimated_from_assessment"`, `estimated_at` present (not `updated_at`). |
| `test_f3_regression_freshness_still_gates_on_tests_source` | Import-test that `week.py` freshness logic (replay from test_source_taxonomy) still passes when baseline is estimated. |
| `test_existing_test_session_source_still_protected` | Baseline with `source="test_session"` from a real test is NOT overwritten by a re-estimate pass. |

### 3.3 Existing suite regression

Run full `backend/tests` after each commit. Target: 1721 → 1727-ish (adds 4 B214 + 4 B215 = 8 new tests; no deletions).

---

## 4. Commit plan

| # | Subject | Files touched |
|---|---|---|
| 1 | `B214: consolidate scalar-write map in _update_test_from_log` | `backend/engine/progression_v1.py`, `backend/tests/test_axis_dispatch.py` (new) |
| 2 | `B215: mirror Priority 0 source gate in _estimate_pulling_baseline` | `backend/engine/progression_v1.py`, `backend/tests/test_estimate_pulling_baseline.py` (new) |
| 3 | `docs: close Bundle B (B214+B215) in ROADMAP_CURRENT` | `docs/ROADMAP_CURRENT.md`, `PROJECT_BRIEF.md`, `README.md` (sync_status output) |

Separate commits (no squash). Run full test suite before each commit. Push direct to `main` (backend-only, no frontend).

---

## 5. Scope-flag callout for Daniele

Two things are different from the brief-as-written — both explicit here so you can approve or redirect:

1. **B214 is re-scoped from full axis dispatch to scalar-mark consolidation (Option A).**
   Reason: dispatch is on `exercise_id`, not `test_id`; branch bodies are heterogeneous; a `_TEST_TYPE_MAP` of the original shape would not replace the branches. Option A closes the only genuine drift risk (forgetting `_mark_measured`) without churning ~250 LOC for zero behavior change.

2. **No new vocabulary §4.3 constant / import-time assertion vs canonical set.**
   Reason: §4.3 lists `test_queue[].test_id` values — different namespace from `exercise_id` or `assessment.tests.*` keys. Creating a third canonical list for `assessment.tests.*` scalars is a meaningful doc+test undertaking, not justified by current drift rate. Option A's map self-documents the covered keys and the new tests prevent drift.

If you want the full axis+baseline refactor (Option B from §1.4) or a new canonical-keys constant, tell me and I'll re-scope to a larger brief — don't silently escalate.

**B215 is small and linear.** Proceeds as brief-written, modulo the exact code shown in §2.3.

---

## 6. STOP — await OK Phase 1

Next action is yours, Daniele. Reply with one of:

- **"OK Phase 1"** → proceed with B214 Option A + B215 as specified.
- **"OK Phase 1 but do Option B for B214"** → full axis+baseline declarative map, larger commit.
- **"Re-scope / split / defer"** → tell me what to change.
