# D232 — Audit: "Start New Macrocycle" feature scoping

**Date:** 2026-05-05
**Type:** D (audit, read-only)
**Risk:** HIGH (touches `macrocycle_v1`, `planner_v2`, `assessment_v1`, Settings flow)
**Status:** Phase 1 — analysis complete. **No code changes.**
**Goal:** map current behavior so the implementation brief can be written without ambiguity.

---

## 1. Executive summary

1. The existing **"Restart Macrocycle"** button in Settings → Danger Zone overwrites `state.macrocycle` via `POST /api/macrocycle/generate` with `from_phase=None`, sets `start_date = this_monday()`, and **preserves all historical data** (`feedback_log`, `session_completion_log`, `outdoor_log`, `working_loads`, `official_maxes`, etc.). It does NOT re-prompt for goal or tests.
2. **Top 3 gaps** for "Start New Macrocycle":
   - **Goal re-set** is not part of any existing flow — current Restart silently keeps the existing `goal`.
   - **Test injection in week 1** requires `state.initial_tests_requested = True`, but `/api/macrocycle/generate` line 90 **explicitly removes** that flag. After a Restart, no tests are scheduled in week 1.
   - **No "next macrocycle" semantics** — `start_date` always defaults to `this_monday()`, never to `current_macrocycle.end_date + 1 day`. End-of-cycle continuation must be added.
3. **Recommended architecture**: build a **distinct, parallel button** alongside existing Restart (do not extend Restart). The new flow needs goal-review + retest opt-in + start-date picker — three steps that the existing Restart's two-confirm dialog and `RegeneratePlanSheet` cannot host without semantic confusion.

---

## 2. Existing "Restart Macrocycle" flow trace

### 2.1 Frontend — Settings page

Click handler chain in `frontend/src/app/(main)/settings/page.tsx`:

| Line | Element / function | Behavior |
|---|---|---|
| `966-984` | `<Card>` "Restart Macrocycle" in Danger Zone | Renders the destructive button, copy: *"Discard the current plan and generate a new one from week 1. Progression data is kept."* |
| `978` | `onClick={() => setRestartMacroDialogOpen(true)}` | Opens first confirmation `<Dialog>` |
| `1020-1048` | `<Dialog>` first confirmation | Copy: *"This will discard your entire current plan and generate a brand new macrocycle starting from week 1. All phase progress will be lost. Are you sure?"* — buttons: Cancel / Yes, continue |
| `1051-1076` | `<Dialog>` second confirmation | Copy: *"The current macrocycle will be replaced with a new one starting from this Monday. This cannot be undone. Proceed?"* — buttons: Cancel / Restart from week 1 |
| `260-264` | `handleRestartMacro()` | Sets `pendingRegenAction = "restart"` and opens `RegeneratePlanSheet` (the 3-option drawer: today / tomorrow / next_monday) |
| `267-294` | `handleRegenSheetConfirm(option)` | Unified handler — for `"restart"`: calls `generateMacrocycle(undefined, 12, undefined)` then `getWeek(0, true, preserveBefore)` then `refresh()` |

Key code at `settings/page.tsx:281-285`:

```ts
// "restart" = full regen from week 1; everything else = incremental
const fromPhase = action === "restart" ? undefined : "current";
await generateMacrocycle(undefined, 12, fromPhase);
await getWeek(0, true, preserveBefore);
await refresh();
```

### 2.2 API client signatures (`frontend/src/lib/api.ts`)

- `generateMacrocycle(startDate?: string, totalWeeks = 12, fromPhase?: string)` — `api.ts:111-123`. POST `/api/macrocycle/generate` body `{ start_date, total_weeks, from_phase }`.
- `getWeek(weekNum, force?, preserveBefore?)` — `api.ts:126-130`. GET `/api/week/{n}?force=true&preserve_before=YYYY-MM-DD`.

### 2.3 Backend — `/api/macrocycle/generate` (`backend/api/routers/macrocycle.py`)

Full handler is 70 lines. Sequence:

| Line | Action |
|---|---|
| `33` | `state = load_state(user_id)` |
| `35-37` | Reject if `goal` missing → 422 |
| `39-41` | Reject if `assessment.profile` missing → 422 |
| `44-54` | Validate goal `deadline` not in past → 400 |
| `57-79` | Resolve `from_phase` → `start_date` and `total_weeks`. **For `from_phase=None` (Restart): `start_date = this_monday()`**, `total_weeks = req.total_weeks` (= 12). For `from_phase="current"`: keeps existing `old_mc["start_date"]` and `old_mc["total_weeks"]`. |
| `82-85` | `macrocycle = generate_macrocycle(goal, profile, state, start_date, total_weeks, from_phase=from_phase)` |
| `89` | `state["macrocycle"] = macrocycle` — **OVERWRITES entire macrocycle** |
| `90` | `state.pop("initial_tests_requested", None)` — **REMOVES the test-injection flag** |
| `91` | `invalidate_week_cache(state)` |
| `92` | `save_state(state, user_id)` |
| `94` | Returns `{"macrocycle": macrocycle}` |

**Subscription guard:** `/api/macrocycle/generate` has **no `require_active_subscription` dependency** (verified vs `session.py`, `feedback.py`, `replanner.py`). An expired-trial user can call it. They cannot use the resulting plan because session/feedback/replanner endpoints do gate on subscription.

### 2.4 `invalidate_week_cache()` — `backend/api/deps.py:53-68`

```python
def invalidate_week_cache(state):
    old = state.get("current_week_plan")
    if old:
        state["_prev_week_plan"] = old        # B114: stash for date-based merge
    state["current_week_plan"] = None
    today_str = datetime.now().strftime("%Y-%m-%d")
    old_plans = state.get("week_plans") or {}
    state["week_plans"] = {
        k: v for k, v in old_plans.items() if k < today_str
    }
```

- Past weeks (`week_plans` keyed by Monday < today) are kept verbatim.
- Current/future weeks are cleared.
- The just-cleared `current_week_plan` is stashed in `_prev_week_plan` for B114 merge logic in `week.py:425-433`.

### 2.5 What lands in the user after click

Sequence the user sees:
1. Click → first dialog → "Yes, continue"
2. Second dialog → "Restart from week 1"
3. Drawer → pick "today" / "tomorrow" / "next_monday" (sets `preserveBefore`)
4. Spinner → backend regenerates macrocycle, frontend refetches `/api/week/0?force=true&preserve_before=...`
5. `qc.invalidateQueries({queryKey: queryKeys.weekAll})` — React Query cache cleared
6. User stays on `/settings` (no redirect). They must navigate to `/plan` or `/week` to see the new macrocycle.

---

## 3. State preservation matrix

Built by code-reading the existing Restart flow (`/api/macrocycle/generate` with `from_phase=None`). "Preserved" means the field is not touched by the handler chain. "Recomputed" means a downstream handler (e.g. `_ensure_profile_fresh` in `deps.py:153-192`) may rewrite it on next save.

| Field | Status | Notes |
|---|---|---|
| `assessment.profile` (5-axis) | **Preserved** | `_ensure_profile_fresh` recomputes on save IF inputs changed (deps.py:179) — fingerprint includes target/current grade, body, tests, grades, self_eval, experience |
| `assessment.tests_source` (D214 sidecar) | Preserved | Untouched |
| `assessment.last_assessed` | Preserved | Set only by `/api/onboarding/complete` (line 403) and `/api/assessment/compute` |
| `assessment.tests` | Preserved | Append-only history of test results |
| `assessment.grades` | Preserved | User-edited via `ProfileAssessmentEditor` |
| `assessment.body` | Preserved | Weight/height/age |
| `assessment.self_eval` | Preserved | Weakness self-eval |
| `assessment.experience` | Preserved | Years climbing, etc. |
| `goal` | Preserved | **NOT prompted to re-set** — current Restart silently reuses existing goal |
| `macrocycle` | **Overwritten** | Line 89: `state["macrocycle"] = macrocycle`. Old macrocycle (incl. `assessment_snapshot`, `goal_snapshot`, `phases`, `start_date`, `end_date`) is lost — no archive |
| `current_week_plan` (B216 cache) | **Reset to None** | `invalidate_week_cache` line 62 — but old value is stashed at `_prev_week_plan` |
| `week_plans` | **Partial reset** | Past weeks (`k < today_str`) kept; current + future cleared (deps.py:65-67) |
| `_prev_week_plan` | **Populated** | From old `current_week_plan` — consumed by `week.py:425-433` `merge_prev_week_sessions` then popped |
| `working_loads.entries` (history) | Preserved | Append-only per-cluster log |
| `working_loads.entries[].next_external_load_kg` | Preserved | **Closed-loop multipliers carry through restart** — new week 1 inherits per-cluster loads |
| `working_loads.rules` | Preserved | DEFAULT_CONFIG (`adaptation/closed_loop.py:18-22`) |
| `cooldowns.per_cluster` | Preserved | `adaptation/closed_loop.py:113-120` — cluster-level cooldowns |
| `official_maxes` | Preserved | Not touched. Per-test timestamps preserved |
| `feedback_log` (append-only) | Preserved | Not touched. Per CLAUDE.md immutability invariant |
| `session_completion_log` | Preserved | Not touched. NB: per B192/D215 lesson this field IS mutable elsewhere (cleared in `mark_planned`), but not by Restart |
| `outdoor_log` (JSONL files) | Preserved | Files on disk untouched. `_clear_outdoor_logs()` is only called by DELETE `/api/state` (state.py:88-90) |
| `weekly_overrides` | Preserved | Not touched |
| `custom_sessions` (A-SESSION-BUILDER) | Preserved | Not touched |
| `limitations` | Preserved | Not touched |
| `availability` | Preserved | Not touched |
| `equipment.gyms` / `outdoor_spots` | Preserved | Not touched |
| `equipment.home` / `home_enabled` | Preserved | Not touched |
| `preferences.finger_training_device` | Preserved | Not touched |
| `preferences.grade_system_boulder` | Preserved | Not touched |
| `planning_prefs.target_training_days_per_week` | Preserved | Not touched |
| `planning_prefs.hard_day_cap_per_week` | Preserved | Not touched |
| `trips` | Preserved | Not touched. `generate_macrocycle()` re-reads them for pretrip windows |
| `stimulus_recency` | Preserved | Not touched |
| `fatigue_proxy` | Preserved | Not touched |
| `quote_history` | Preserved | Not touched |
| `free_sessions` | Preserved | Not touched |
| `subscription` / `trial` (Supabase) | Preserved | Stripe-webhook-only writes; not in `_ALLOWED_STATE_KEYS` of PUT (state.py:41-51) |
| `initial_tests_requested` | **Removed** | Line 90: `state.pop(...)` — kills any pending test-injection request |
| `test_reminder_postponed_to` / `test_reminder_skipped_until` | Preserved | Not touched. Cleared only by `/api/week/test-reminder-response` |
| `baselines.hangboard` / `baselines.pulling` | Preserved | Not touched |
| `tests` (in-app history) | Preserved | Not touched. `tests.repeater_strength_endurance[]` etc. |
| `progression_counters` | Preserved | Not touched |
| `progression_config` | Preserved | Not touched |

**Summary:** the existing Restart is fully *preservation-positive* on user history. The only destructive moves are (a) `macrocycle` overwrite and (b) `initial_tests_requested` pop. There is no archive of the discarded macrocycle.

---

## 4. `generate_macrocycle()` reference

### 4.1 Signature — `backend/engine/macrocycle_v1.py:512-535`

```python
def generate_macrocycle(
    goal: Dict[str, Any],
    assessment_profile: Dict[str, int],
    user_state: Dict[str, Any],
    start_date: str,             # YYYY-MM-DD, must be Monday (auto-corrected)
    total_weeks: int = 12,
    *,
    from_phase: Optional[str] = None,  # PHASE_ORDER value or None
) -> Dict[str, Any]
```

`PHASE_ORDER = ("base", "strength_power", "power_endurance", "performance", "deload")` — `macrocycle_v1.py:17`.

### 4.2 `from_phase` semantics

- `None` (full regen): `kept_phases = []`, `phases_to_gen = list(PHASE_ORDER)`, durations from `_compute_phase_durations(profile, total_weeks, discipline)` — `macrocycle_v1.py:580-584`.
- `"current"` (router-level only): the **router** resolves it via `current_phase_and_week(old_mc)` to a specific phase_id BEFORE calling the engine — see `macrocycle.py:65-67`. The engine itself does NOT understand `"current"` — passing `"current"` to the engine raises `ValueError("Unknown phase_id")` at line 562.
- Specific phase_id (e.g. `"strength_power"`): engine keeps phases of `old_mc` strictly before `from_phase`'s position in `PHASE_ORDER` (line 567-570), then regenerates from `from_phase` onwards using `_compute_remaining_durations()`.

### 4.3 Output shape — `macrocycle_v1.py:637-656`

```python
{
    "macrocycle_version": "macrocycle.v1",
    "generated_at": <iso timestamp>,
    "start_date": <Monday YYYY-MM-DD>,
    "end_date": <YYYY-MM-DD>,                  # = start + total_weeks - 1 day
    "goal_snapshot": {                          # subset of goal at gen time
        "goal_type", "discipline", "target_grade",
        "target_boulder_grade", "current_grade", "deadline",
    },
    "assessment_snapshot": dict(profile),        # used by is_macrocycle_stale
    "total_weeks": <int>,
    "phases": [
        {phase_id, phase_name, start_week, end_week, duration_weeks,
         energy_system, domain_weights, session_pool, intensity_cap,
         notes, [pretrip_deload]}
    ],
    [warnings]: [str]                           # if goal validation has issues
}
```

### 4.4 All call sites

Production code:
| File | Line | Context |
|---|---|---|
| `backend/api/routers/macrocycle.py` | 82 | POST `/api/macrocycle/generate` — both incremental and full regen |
| `backend/api/routers/onboarding.py` | 427 | POST `/api/onboarding/complete` — first generation, `from_phase` not passed |
| `backend/api/routers/onboarding.py` | 435 | Same handler — fallback retry with `strict_next_monday` if Week 1 would be empty |
| `backend/engine/start_date_utils.py` | (probe call site — used by onboarding to test placeability) | Probes Week 1 placement quality without saving |

Scripts (not exercised in production traffic, but maintained):
| File | Line | Purpose |
|---|---|---|
| `scripts/retrofit_coldstart_users.py` | 189 | One-off backfill for users without macrocycle |
| `scripts/simulate_onboarding_start.py` | 293 | Onboarding simulation harness |
| `scripts/extract_audit_snapshot.py` | 249 | Doc-only string reference |

Tests (45 occurrences across 6 files): `test_macrocycle_v1.py`, `test_macrocycle_boulder.py`, `test_a_activation_timing.py`, `test_p0_fixes.py`, `test_discipline_all_round.py`. Multiple tests cover `from_phase` incremental regen — see `test_macrocycle_v1.py:445-446`.

### 4.5 Goal/profile coupling

The engine **does not auto-recompute** the assessment profile inside `generate_macrocycle()`. It accepts whatever `assessment_profile` dict is passed in. The router pulls it from `state["assessment"]["profile"]` (`macrocycle.py:39`). So if the goal changes but the profile hasn't been recomputed, the new macrocycle is built on **stale 5-axis weights**. This is masked in practice by:

- `_ensure_profile_fresh()` (`deps.py:153-192`) which recomputes on every `save_state()` if any input changed (fingerprint = body + grades + tests + self_eval + experience + target_grade + current_grade).
- The Settings goal-edit flow which calls `computeAssessment()` before triggering `generateMacrocycle()` (`settings/page.tsx:222-228`).

For a "Start New Macrocycle" flow, the recompute must be explicit and ordered: goal save → profile recompute → macrocycle gen.

---

## 5. Test injection logic reference

### 5.1 Pass 3 in `generate_phase_week()` — `backend/engine/planner_v2.py:1259-1394`

```python
_run_pass3 = inject_tests or (is_last_week_of_phase and phase_id in ("base", "strength_power"))
```

So Pass 3 runs in two cases:
- **Explicit:** caller passes `inject_tests=True`. Bypasses phase-aware gate (`_phase_map` set to `{}`, line 1289) and bypasses 42-day freshness window (line 1318: `if last_date_str and not inject_tests`).
- **Implicit:** end-of-base or end-of-strength_power week. Subject to phase-aware gate (D92/B191) and 42-day freshness (B128).

### 5.2 Test schedule (planner_v2.py:1281-1285)

Three tests in priority order:
1. **Finger** — `test_lp_max_5s` (loading pin) or `test_max_hang_7s` (hangboard) — required.
2. **Repeater** — `test_lp_repeater` or `test_repeater_7_3` — required.
3. **Pulling** — resolved by `_pick_pulling_test_session(pulling_baseline, max_pullups_bw)` (line 564) → `test_max_weighted_pullup` or `test_pullup_bw`. Optional.

Test selection respects `state.preferences.finger_training_device` (A120) and pulling baseline (B128).

### 5.3 Freshness gate — `TEST_FRESHNESS_DAYS = 42` (line 1266)

42 days = 6 weeks. Sources cited in code: Hörst, Lattice, Eva López. Skipped when `not last_date_str` or `not inject_tests` (B210 override).

### 5.4 `recent_test_dates` build — `week.py:341-377`

The week router builds `_recent_test_dates` from:
- `baselines.hangboard[0].updated_at` — only if `tests_source.max_hang_*` is `"measured"` (D214 gate)
- `tests.repeater_strength_endurance[-1].date` — or fallback to `macrocycle.start_date` if onboarding-only
- `baselines.pulling.updated_at` — only if `tests_source.weighted_pullup_*` is `"measured"`

D214 ensures onboarding *estimates* don't mask the need for first real measurement.

### 5.5 Wire-up: `inject_tests` in `/api/week/{n}` — `week.py:326-332`

```python
want_tests = (
    state.get("initial_tests_requested")
    and ctx.get("is_first_week_of_phase")
    and ctx["phase_id"] == "base"
    and not is_last
)
```

Conditions:
1. `state.initial_tests_requested == True`
2. Current week is week 1 of its phase
3. Phase is `base` (the only phase that hosts week-1 tests)
4. Not the last week of phase (defensive — base normally has ≥2 weeks)

### 5.6 Where the flag gets set / cleared

| Where | Action |
|---|---|
| `onboarding.py:407` | Set to `True` if `data.test_week_requested` (user opt-in checkbox) |
| `week.py:484` | Set to `True` by `/api/week/test-reminder-response` with `option="confirm"` (periodic reminder) |
| `macrocycle.py:90` | **Removed** by `/api/macrocycle/generate` — every Restart |
| (no consumer pops it after use) | The flag stays `True` across week regenerations until macrocycle restart pops it |

### 5.7 Critical implication for "Start New Macrocycle"

If we want week-1 tests in the new macrocycle, the new endpoint MUST **set `initial_tests_requested = True` after** the macrocycle generation, NOT before. Otherwise it gets popped at line 90.

A clean alternative: do not call `/api/macrocycle/generate` at all. Build a new endpoint that does the full atomic flow (goal save + profile recompute + macrocycle gen + flag set + cache invalidate + save) in the same handler, mirroring `/api/onboarding/complete`.

---

## 6. Goal edit flow reference

### 6.1 UI — `frontend/src/components/settings/goal-editor.tsx`

Two-step Dialog: "form" → "confirm". Captures `discipline`, `target_style`, `target_grade`, `deadline`. Discipline can be `lead | boulder | both`. Boulder grades are uppercase Font; lead grades are lowercase.

### 6.2 Wired in Settings page — `settings/page.tsx:218-234`

```ts
async function handleGoalConfirm(newGoal) {
  await putState({ goal: newGoal });
  await computeAssessment(state?.assessment, newGoal);
  setGoalEditorOpen(false);
  setPendingGoal(newGoal);
  setPendingRegenAction("goal");
  setRegenSheetOpen(true);    // opens RegeneratePlanSheet
}
```

Then on sheet confirm (`handleRegenSheetConfirm`, line 267): calls `generateMacrocycle(undefined, 12, "current")` — incremental regen from current phase.

### 6.3 `is_macrocycle_stale` — `backend/engine/state_checks.py:20-47`

Pure function. Compares `state.assessment.profile` against `state.macrocycle.assessment_snapshot` axis-by-axis (5 axes). Returns `True` if **any** axis differs by ≥ `DIRTY_STATE_THRESHOLD = 5` points.

Trigger conditions:
- A goal change that shifts target grade significantly → profile recomputation → axis deltas
- Self-eval change in Profile editor → axis deltas
- Test results entered (e.g. new max hang) → axis deltas

NOT triggered by:
- Equipment/availability/limitations changes
- Discipline change alone (until profile is recomputed)
- Trips changes

### 6.4 Frontend dirty-state UI

`frontend/src/lib/api.ts:72`: `getStateStatus()` → `{ is_macrocycle_stale: boolean }`. Searched call sites — see `frontend/src/lib/`. The boolean is used by `/plan` and `/today` to display a "your plan needs updating" banner (verify in implementation; copy may have shifted).

### 6.5 PUT `/api/state` — `state.py:54-78`

- Deep-merge (`_deep_merge`, line 24-31): recurses into nested dicts; otherwise overwrites scalar/list values. **Lists are replaced wholesale** — there is no list-append semantic.
- 27 `_ALLOWED_STATE_KEYS` (line 41-51). Unknown keys → 422.
- Auto-corrects `macrocycle.start_date` to Monday (line 67-69).
- Calls `invalidate_future_week_cache(state)` (NOT `invalidate_week_cache`) when `availability` is in patch — preserves current week.
- Calls `save_state` which auto-fires `_ensure_profile_fresh`.

---

## 7. Onboarding parallels (`POST /api/onboarding/complete`)

### 7.1 Steps performed by `onboarding.py:333-444`

1. **Validate equipment keys** (line 343).
2. **Build user_state from onboarding payload** (line 348, calls `_build_user_state_from_onboarding`).
3. **Estimate missing baselines** (line 351, `estimate_missing_baselines`) — pulls from grade + pullup count.
4. **Derive `goal.goal_type` from `goal.discipline`** if missing (line 360-365).
5. **Map boulder grades to lead** for assessment computation (line 369-377: `_BOULDER_TO_LEAD`).
6. **Default `goal.current_grade`** from `assessment.grades.lead_max_rp` / `boulder_max_rp` (line 379-385).
7. **Boulder-only special case**: store `target_boulder_grade` separately, map `target_grade` to lead equivalent (line 388-392).
8. **Compute assessment profile** (line 397, `compute_assessment_profile`).
9. **Persist profile + last_assessed** (line 402-403): `state["assessment"]["profile"] = profile`, `state["assessment"]["last_assessed"] = next_monday()`.
10. **Set `initial_tests_requested = True`** if user opted in (line 406-407).
11. **Compute start_date** (line 419-421): `ensure_monday(this_monday(today))`. Default `total_weeks`: 10 boulder, 12 lead. Clamp `[5..52]` boulder, `[9..52]` lead.
12. **Generate macrocycle** (line 427).
13. **Threshold-1 fallback** (line 429-435): if `is_week_one_empty(state, mc, today)`, regenerate with `strict_next_monday(today)`.
14. **Save** (line 440-442): `state["macrocycle"] = mc`, `invalidate_week_cache(state)`, `save_state(state, user_id)`.

### 7.2 Steps that repeat for "Start New Macrocycle"

Mandatory:
- (4-7) Goal normalization — discipline, derived `goal_type`, boulder→lead mapping
- (8) Assessment profile recompute (because target grade may shift)
- (9) Persist new `last_assessed` (so the new cycle is timestamped)
- (10) Set `initial_tests_requested = True` if user opts in
- (11-13) start_date + macrocycle generation + week-1-empty fallback
- (14) Save + cache invalidate

Skippable (already in state):
- (1) Equipment validation — equipment unchanged
- (2) Build user_state from scratch — we keep existing
- (3) Baseline estimation — already populated; user can retest if desired

### 7.3 Onboarding wizard pages — `frontend/src/app/onboarding/`

Page list: `welcome`, `install`, `profile`, `discipline`, `experience`, `grades`, `goals`, `weaknesses`, `tests`, `limitations`, `locations`, `availability`, `trips`, `review`, `start-week`, `recover`.

For partial re-onboarding, conceptually relevant pages:
- `goals` — REQUIRED (confirmed product decision)
- `discipline` — implicit in `goals` (can be flipped there)
- `weaknesses` — OPTIONAL (drives self_eval → profile axes)
- `tests` — OPTIONAL (the retest-week opt-in)
- `start-week` — REQUIRED (when does the new cycle begin?)
- `review` — REQUIRED (final confirmation)

Skippable:
- `welcome`, `install` (PWA install) — not needed
- `profile` (name, weight, height, age) — already known
- `experience` — slow-changing, optional
- `grades` — could be reviewed (user may have improved during macrocycle)
- `limitations` — slow-changing, accessible from Settings already
- `locations`, `availability`, `trips` — accessible from Settings already
- `recover` — auth-only flow

**Note**: this is mapping, not designing. The implementation brief decides flow shape.

---

## 8. Edge cases observed

For each Area-9 question, current code behavior:

### 8.1 Mid-week restart (current behavior)

Sequence when user clicks Restart on Wednesday with 2 sessions already done in the current week:

1. Backend overwrites `state.macrocycle` (new week 1 starts on **this Monday** — same Monday the in-progress week is in).
2. `invalidate_week_cache` keeps `week_plans[k]` for `k < today_str` (Wednesday) — so Monday's `week_plans[<this_monday>]` IS cleared (since this_monday <= today_str only if today is Monday).
   - **Wait — let me verify**: `today_str = "Wed 2026-04-22"`. Cache key is the Monday `"2026-04-20"`. `"2026-04-20" < "2026-04-22"` → string compare, true → kept. So **the in-progress week's cached plan IS preserved** in `week_plans`. Only `current_week_plan` (the legacy single-pointer cache) is wiped.
3. Frontend then calls `getWeek(0, true, preserveBefore)` with `preserveBefore = today | tomorrow | next_monday` (user-picked).
4. `week.py:319-321`: `effective_preserve = preserveBefore or today_str`.
5. `week.py:411-418`: if `old_plan` (from `week_plans[<this_monday>]`) matches new `week_plan.start_date`, calls `regenerate_preserving_completed(old_plan, new_plan, preserve_before=effective_preserve)`.
6. `replanner_v1.py:646-739` preserves: days strictly before `preserve_before` → wholesale copy; today with completed sessions → wholesale copy; future days → fresh + merge `done`/`skipped` sessions slot-by-slot.

**Net effect**: completed Mon/Tue sessions survive. Future Thu-Sun gets the new plan from the new macrocycle's week 1. The user's Mon/Tue "feedback_log" entries are untouched.

**Important quirk**: the new macrocycle's `start_date` is `this_monday()` — the SAME Monday as the in-progress week. So week 1 of the new macrocycle is anchored on the same date as the OLD week being interrupted. The surviving Mon/Tue sessions belong to the OLD plan but live on dates within NEW week 1 — `regenerate_preserving_completed` handles this via date-keyed merge, not session-id matching.

### 8.2 `start_date` Monday invariant

- `this_monday()` (`deps.py:223-231`) — returns Monday ≤ today (going backward). Default for Restart.
- `next_monday()` (`deps.py:214-220`) — returns Monday ≥ today (going forward). Used by onboarding `last_assessed`.
- `ensure_monday(d)` (`deps.py:205-211`) — rounds DOWN: any date → previous Monday.
- `generate_macrocycle()` engine self-corrects: `if start.weekday() != 0: start -= timedelta(days=start.weekday())` (line 547-549).

For the new feature: if the user wants the new macrocycle to start AFTER the current one ends, `start_date = ensure_monday(current_macrocycle.end_date + 1 day)` is the natural default. There is no helper for this — would need to be computed in the new endpoint.

### 8.3 iOS PWA cache after Restart

- The Service Worker has nothing to do with macrocycle data — that's API-driven, refetched on demand.
- React Query cache: `qc.invalidateQueries({ queryKey: queryKeys.weekAll })` (settings/page.tsx:62, called via `invalidateWeek()` after regen) — covers all week views.
- No known SW-related restart bug in the lessons file or roadmap.
- B196 branch policy applies: any frontend change to add the new button MUST go through a `brief/B<n>-<slug>` branch + Vercel preview.

### 8.4 Subscription gating

- `/api/macrocycle/generate` — **NOT gated** by `require_active_subscription`. An expired user can hit it.
- `/api/session/*`, `/api/feedback`, `/api/replanner/*` — **gated** (verified line numbers above). Expired user gets 402 when trying to actually use the plan.
- `/api/onboarding/complete` — also NOT gated (it's the entry point).
- Implication for new feature: the new endpoint should match. If we want to keep parity with existing Restart, leave the new endpoint ungated. If we want to push expired users to subscribe before regenerating, add the guard. **Decision belongs to the implementation brief.**

### 8.5 Discipline switch (lead → boulder)

- `generate_macrocycle()` reads `goal.discipline` (line 550): if `None`, defaults to `"lead"` with a warning log.
- It selects boulder pools (`_SESSION_POOL_BOULDER`, `_BASE_WEIGHTS_BOULDER`) when `discipline == "boulder"` (line 596).
- Boulder requires `assessment.grades.boulder_max_rp` to drive the profile — if missing, profile computation may produce defaults.
- The ONLY place that maps `target_boulder_grade` → `target_grade` (lead-equivalent for benchmark calibration) is `onboarding.py:387-392`. **`PUT /api/state` does not do this mapping.** So if a user changes `goal.discipline = "boulder"` via Settings goal editor without re-running through onboarding semantics, the assessment may compute on stale `target_grade` until corrected.
- This is a real gap that the new feature must handle.

### 8.6 Closed-loop multipliers under Restart

- `working_loads.entries[]` is **preserved** through Restart (no code path touches it).
- Each entry has `next_external_load_kg` set by `progression_v1.py:1453, 1486` based on closed-loop deltas (`adaptation/closed_loop.py:36-52`, `_clamp(value, min=0.85, max=1.15)`).
- Implication: a user who entered "too_hard" feedback for hangboard during current macrocycle's strength_power phase carries that 0.95× multiplier into new macrocycle's base phase, where the volume is lower — possibly under-loading.
- This is potentially desired (carry strength gains, avoid blank-slate regression) or undesired (full reset for "fresh start" semantics).
- **Decision belongs to the implementation brief.** Either way, the choice must be explicit in the endpoint, not inherited by accident.

---

## 9. Macrocycle history / archive

Searched repo for `macrocycle_history`, `prev_macrocycle`, `previous_macrocycle`, `archived.*macrocycle`, `past_macrocycle`. **Zero matches** in `backend/`, `frontend/src/`.

There is no concept of macrocycle history. After Restart, the previous macrocycle is **lost** (overwritten at `macrocycle.py:89`).

The user can inspect `assessment_snapshot` and `goal_snapshot` only for the **current** macrocycle (via `/plan` UI or `GET /api/state`).

**This is a confirmed gap.** The new feature could:
- Add a `macrocycle_history: List[Macrocycle]` array (each entry = full macrocycle dict at time of replacement)
- OR add a `previous_macrocycle` single-slot pointer (only last)
- OR leave it out entirely (status quo)

Storage size: a single macrocycle dict is ~10 KB. 5 stored cycles = 50 KB per user. Cheap.

Decision belongs to the implementation brief.

---

## 10. Settings frontend architecture

### 10.1 File tree

- Single page: `frontend/src/app/(main)/settings/page.tsx` (1200 lines).
- Components: `frontend/src/components/settings/` — `availability-editor.tsx`, `equipment-editor.tsx`, `goal-editor.tsx`, `limitations-editor.tsx`, `profile-assessment-editor.tsx`. No subdirectories.
- Reused components from `frontend/src/components/training/regenerate-plan-sheet.tsx`.

### 10.2 Settings page section order

1. Profile & Maxes (Card)
2. Goal (Card)
3. Equipment (Card / EquipmentEditor)
4. Finger Training Device (Card)
5. Injuries & Limitations (Card / LimitationsEditor)
6. Availability (Card / AvailabilityEditor)
7. Outdoor Spots (Card)
8. Subscription (Card)
9. Account (Card with `<UserButton>` from Clerk)
10. Session preferences (Card with voice cues toggle)
11. Display preferences (Card with grade system toggle)
12. Backup & Restore (Card)
13. **Separator**
14. **Danger zone** — heading + 2 cards (Restart Macrocycle, Reset & Restart) + legal link

### 10.3 Dialog and drawer infrastructure

- `<Dialog>` (`@/components/ui/dialog`) — used for confirmations (8 instances on this page).
- `<AlertDialog>` (`@/components/ui/alert-dialog`) — used for destructive confirmations (delete spot, import data).
- `<Drawer>` (`@/components/ui/drawer`) — used by `RegeneratePlanSheet`.

### 10.4 Reusable patterns

- Two-step `<Dialog>` pattern (warning → final-confirmation) — already used by Restart and Reset. Could be extended to a 3-step (warning → goal-edit → final-confirmation), but a separate page or a multi-step dialog would be cleaner.
- `RegeneratePlanSheet` (`training/regenerate-plan-sheet.tsx`) — emits `RegenerateStartOption = "today" | "tomorrow" | "next_monday"`. Useful for picking start date semantics; would need extension for "after current cycle ends".
- `GoalEditor` (`settings/goal-editor.tsx`) — already self-contained dialog with form + confirm steps. Reusable as-is.

### 10.5 Where the new button should live (recommendation)

**Three options:**

| Option | Pro | Con |
|---|---|---|
| (A) Add to Danger Zone alongside Restart | Discoverable; same location as existing | Semantically wrong — new flow preserves history, NOT destructive |
| (B) New section "Season Planning" between Backup&Restore and Danger Zone | Correct semantic placement; clear "future cycle" mental model | New section to design; +1 visual card |
| (C) Separate `/settings/new-macrocycle` page (multi-step like onboarding) | Mirrors onboarding; more room for explainer copy + retest opt-in + dates picker | Two extra clicks; more boilerplate |

**Recommendation: B for v1**, with a Card titled e.g. "Plan Next Cycle" or "Start New Macrocycle" containing a single button that opens a multi-step dialog (goal review → retest opt-in → start-date picker → final confirm). Keep existing Restart in Danger Zone unchanged. This keeps the destructive/non-destructive semantics clean.

If (and only if) UX feedback shows the multi-step dialog is too cramped on iPhone PWA, fall back to (C) and route to a dedicated page.

---

## 11. Gap list (what's missing for the desired feature)

In rough priority order:

1. **No goal re-set in Restart flow.** Existing Restart silently reuses `state.goal`. New feature requires explicit goal review.
2. **`initial_tests_requested` flag is auto-popped on every macrocycle generate** (`macrocycle.py:90`). Any "tests in week 1 of new cycle" path must set the flag AFTER the generate, OR a new endpoint must inline the entire flow.
3. **No "after current cycle ends" semantics.** `start_date` always defaults to `this_monday()` (Restart) or `next_monday()` (onboarding `last_assessed`). End-of-cycle continuation requires `current_macrocycle.end_date + 1 day → ensure_monday(...)`.
4. **No discipline-switch sanitization in goal-edit path.** Boulder→lead grade mapping (`_BOULDER_TO_LEAD`) only happens in `/api/onboarding/complete`. PUT `/api/state` does not normalize. New feature must handle discipline change cleanly.
5. **No macrocycle archive.** Restart silently destroys the previous macrocycle. Users have no record of past phases / snapshots. Optional but desirable for a v1 of "Start New Macrocycle" — distinguishes the feature from Restart.
6. **No closed-loop reset option.** `working_loads.entries` always carry over. The product decision is "should a fresh cycle reset multipliers?" — needs an explicit choice. Default suggestion: keep multipliers (preserve gains), but offer an "advanced: reset progression" toggle.
7. **No retest opt-in UI in Settings.** The retest checkbox exists in onboarding (`tests` page) but not in Settings. Needs to be added.
8. **No "are you sure your current macrocycle is finished?" guardrail.** If user clicks the new button mid-cycle, current Restart's two-confirm dialog handles it — but the copy needs to be different (this is normal end-of-cycle flow, not destructive).
9. **No subscription consideration.** Decision: should an expired user be allowed to start a new cycle? Restart currently allows it. Implementation brief decides.
10. **No automatic recompute order.** Today's Settings goal-edit flow is `putState({goal}) → computeAssessment()`. The new flow must enforce ordering: goal save → assessment recompute → macrocycle gen.
11. **No tracking of "user requested next cycle"** for analytics. Could be a Vercel Analytics event in the new flow.

---

## 12. Architecture recommendation

**Build a new, parallel button — do NOT extend the existing Restart.**

Justification (code evidence):

- Existing Restart's frontend handler `handleRegenSheetConfirm` (`settings/page.tsx:267-294`) uses a single boolean (`action === "restart"`) to flip `from_phase`. Adding a third action (`"new_cycle"`) would force the handler to also set `initial_tests_requested` post-call, mutate goal beforehand, and pick a different default `start_date` — three branching responsibilities in one handler is brittle.
- Existing Restart's two-`<Dialog>` confirmation chain (lines 1020-1076) hardcodes destructive copy ("All phase progress will be lost", "This cannot be undone"). The new flow has the OPPOSITE semantics — preserve everything, opt in to retest, plan the next chapter. Reusing those dialogs would confuse users.
- The backend handler `/api/macrocycle/generate` is already overloaded (incremental regen + full restart + onboarding fallback). Adding a fourth code path would push it past comfortable complexity. A new endpoint, e.g. `POST /api/macrocycle/start-new-cycle`, can mirror `/api/onboarding/complete`'s atomic structure cleanly.

**Proposed shape (NOT a design — for the implementation brief to refine):**

- New endpoint: `POST /api/macrocycle/start-new-cycle` with body `{ goal, total_weeks?, request_tests, reset_progression?, start_after_current? }`.
- Atomic flow: validate goal → boulder/lead mapping → `putState({goal})` semantics → recompute profile → resolve `start_date` → call `generate_macrocycle()` → set `initial_tests_requested` if `request_tests` → optionally clear `working_loads.entries` if `reset_progression` → optionally archive old macrocycle to `state.macrocycle_history[]` → `invalidate_week_cache` → save.
- New frontend section in Settings: "Plan Next Cycle" Card with a button that opens a multi-step `<Dialog>` (goal review → retest opt-in → start date picker → confirm). Reuse `<GoalEditor>` for step 1.

---

## 13. Risk callouts (for the implementation brief)

1. **`initial_tests_requested` ordering.** The new endpoint must set this flag AFTER calling `generate_macrocycle()` (or skip `/api/macrocycle/generate` and inline the flow). The pop at `macrocycle.py:90` will silently kill the request otherwise.
2. **`from_phase=None` semantics on `generate_macrocycle`.** When called for "new cycle starting now", do NOT pass `from_phase`. Tests covering this path are in `test_macrocycle_v1.py` and `test_a_activation_timing.py` — write parallel tests for the new endpoint.
3. **`current_week_plan` legacy cache (B216).** `_prev_week_plan` is consumed by `merge_prev_week_sessions` (`week.py:425-433`) and popped. If the new flow runs concurrently with an in-flight week regen, the stash could be lost. Tests should cover restart with ongoing week-fetch.
4. **`assessment_snapshot` immutability.** `is_macrocycle_stale` compares `assessment.profile` vs `macrocycle.assessment_snapshot`. If the new cycle's profile differs from the OLD snapshot but has not been recomputed before the new generate, `is_macrocycle_stale` could flicker. Solution: enforce profile recompute BEFORE generate inside the new endpoint, then the new snapshot becomes the new baseline.
5. **Goal validation.** `_validate_goal` (`macrocycle_v1.py:486-509`) only warns on grade-gap issues — it does NOT block. The new endpoint should propagate warnings to UI so the user can decide.
6. **Past-session immutability invariant.** Whatever the new endpoint does, **add a regression test** asserting that for a user with completed sessions in `feedback_log` and `session_completion_log`, calling `start-new-cycle` does NOT modify any of those entries. Per CLAUDE.md non-negotiable principle.
7. **Boulder-only flow.** `target_boulder_grade` ↔ `target_grade` mapping is duplicated logic between `onboarding.py` and any new endpoint. Extract to a shared helper to avoid drift.
8. **Subscription guard.** Decide explicitly whether `start-new-cycle` requires `require_active_subscription`. Both choices are defensible — write the decision in the implementation brief, not by accident.
9. **Concurrency.** A user double-tapping the confirm button could fire two simultaneous generates. Existing routes don't handle this explicitly — current behavior is "last writer wins" via `save_state`. Not a regression risk but worth a note.
10. **iOS PWA testing.** Per CLAUDE.md B196 branch workflow, frontend changes must go on `brief/B<n>-<slug>` and verify via Vercel preview before merging to main. The two-confirm + sheet pattern interacts with iOS PWA quirks (haptics, back-button) — preview QA on iPhone is mandatory.
11. **Test-injection freshness gate.** When `initial_tests_requested=True` is set, the planner's freshness check is bypassed (B210). If the user retested 10 days ago via the periodic reminder and now starts a new cycle with retest=True, they will retest TWICE within 10 days. Probably acceptable (user explicitly opted in twice) but worth surfacing in the UI ("you tested 10 days ago — retest now?").

---

**End of report.** Awaiting Daniele's review before any implementation brief is drafted.
