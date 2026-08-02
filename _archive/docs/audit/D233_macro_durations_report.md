# D233 — Macrocycle phase-duration audit (Phase 0, read-only)

**Brief:** D-MACRO-DURATIONS (D233)
**Date:** 2026-05-07
**Mode:** Read-only — no source/state mutations.
**Scope:** Map and trace the formula that allocates weeks to macrocycle phases, as
input to a follow-up A-brief that will:
1. Hard-cap total macrocycle duration at 16 weeks.
2. Hard-cap base phase at 3–4 weeks (final value pending KB).
3. Raise performance phase floor for advanced lead + redpoint to 3 weeks.

KB has already validated (2026-05-06) that the current behaviour on long cycles
(e.g. 21 → 12/4/2/2/1) is not literature-supported. This report explains the
formula that produces it.

---

## Step 0.1 — File / function map

### Primary engine module

`backend/engine/macrocycle_v1.py` (835 lines).

| Symbol | Lines | Purpose |
|---|---|---|
| `PHASE_ORDER` | 18 | `("base", "strength_power", "power_endurance", "performance", "deload")` |
| `_BASE_DURATIONS` | 244–247 | Lead defaults: `{base:4, strength_power:3, power_endurance:2, performance:2, deload:1}` (sum=12) |
| `_BASE_DURATIONS_BOULDER` | 221–224 | Boulder defaults: `{base:2, strength_power:4, power_endurance:1, performance:2, deload:1}` (sum=10) |
| `_WEAKNESS_ADJUSTMENTS` | 233–239 | `axis → (extend_phase, shrink_phase)` table; 5 entries |
| `_MIN_TOTAL_WEEKS` | 242 | `9` (lead floor; `5` for boulder, hardcoded inline) |
| `_compute_phase_durations(profile, total_weeks=12, discipline="lead")` | 250–316 | Full-cycle allocation. Single source of truth for new generates. |
| `_compute_remaining_durations(profile, remaining_weeks, remaining_phases, *, discipline)` | 319–392 | Partial allocation for incremental regen (`from_phase` path). |
| `_adjust_domain_weights(...)` | 395–433 | Adjusts the per-phase domain weight vector — **not** the duration. |
| `_build_session_pool(phase_id, discipline)` | 436–458 | Phase session pools — independent of duration. |
| `generate_macrocycle(goal, profile, state, start_date, total_weeks=12, *, from_phase=None)` | 513–657 | Main entry point. Branches on `from_phase` and calls one of the two duration helpers. |
| `_phase_notes(phase_id)` | 660–668 | Static descriptive text; no duration logic. |
| `should_extend_phase(...)` | 772–786 | Heuristic for "feedback hard 2 weeks → extend". **Dead in production code** (only referenced by tests; see Findings §F2). |
| `should_trigger_adaptive_deload(...)` | 789–801 | Heuristic for "5 consecutive very_hard". **Dead in production code** (Findings §F2). |
| `compute_new_macrocycle_start_date(state, today)` | 809–835 | Resolves the next Monday for `start-new-cycle`; no duration math. |

### Helper module

`backend/engine/macrocycle_archive.py` (180 lines) — snapshots `state["macrocycle"]`
into `state["macrocycle_history"]`. Reads `macrocycle.total_weeks`,
`phases[].duration_weeks`, `phases[].phase_id`. Stores a **deep copy** of the
generated macrocycle, so any change to duration output flows into history
naturally — no migration concerns for *new* archive entries (existing entries
are immutable historical records).

### Callers of `generate_macrocycle`

| File:line | Path | `total_weeks` source |
|---|---|---|
| `backend/api/routers/onboarding.py:420` | `POST /api/onboarding/complete` (initial generate during onboarding) | `goal.total_weeks` (UI slider) → clamped to `[5/9, 52]` (line 419). Default 10 (boulder) / 12 (lead) (line 416). |
| `backend/api/routers/onboarding.py:428` | Same router, fallback path when Week 1 would be empty | Re-uses the same `total_weeks` |
| `backend/api/routers/macrocycle.py:90` | `POST /api/macrocycle/generate` | `req.total_weeks` (default 12 from `MacrocycleRequest`) OR `old_mc.total_weeks` if `from_phase` is set |
| `backend/api/routers/macrocycle.py:247` | `POST /api/macrocycle/start-new-cycle` (A-NEW-MACRO) | `req.total_weeks` if provided, else discipline default (`_DEFAULT_TOTAL_WEEKS_LEAD=12` / `_DEFAULT_TOTAL_WEEKS_BOULDER=10` at `macrocycle.py:113-114`); validated `[9/5, 52]` at `macrocycle.py:176-183` |

### Callers of `_compute_phase_durations` / `_compute_remaining_durations`

Only `generate_macrocycle` itself (lines 576, 583). No external callers.

### Frontend touchpoints (read-only consumers of the output)

| File:line | Use |
|---|---|
| `frontend/src/lib/types.ts:16,25` | Type definitions — `Phase.duration_weeks: number`, `Macrocycle.total_weeks: number` |
| `frontend/src/components/training/macrocycle-timeline.tsx:42,56,71,93,107` | Renders phases as proportional segments (`width = duration_weeks / total_weeks * 100`) |
| `frontend/src/app/(main)/plan/page.tsx:194,286` | Displays `total_weeks` and per-phase `duration_weeks` |
| `frontend/src/app/(main)/week/page.tsx:172,180` | Iterates phases × `duration_weeks` to enumerate weeks |
| `frontend/src/app/onboarding/start-week/page.tsx:29,39` | Cumulative-week math for the offset slider |
| `frontend/src/components/shared/deadline-weeks-selector.tsx:36-37` | Slider range: **min=8, max=24** (default-injected); see Step 0.4 |

The frontend treats `duration_weeks` as opaque numeric data. Nothing assumes
a specific value or count. **Safe to change durations server-side without frontend
edits**, except the slider max (24) which exceeds the new 16-week cap.

---

## Step 0.2 — Trace table for scenarios A–G

The formula in `_compute_phase_durations` is:

```
1. base = _BASE_DURATIONS[discipline].copy()           # lead=4/3/2/2/1, boulder=2/4/1/2/1
2. weakest_axis = argmin over (power_endurance, endurance, finger_strength,
                               pulling_strength, technique)
3. if weakest_score < 50 and weakest_axis ∈ _WEAKNESS_ADJUSTMENTS:
       extend, shrink = _WEAKNESS_ADJUSTMENTS[weakest_axis]
       if base[shrink] > shrink_floor:
           base[extend] += 1
           base[shrink] -= 1
   # shrink_floor = 1 (boulder) or 2 (lead)
4. floor enforcement: base ≥ 2; sp/pe/perf ≥ floor (1 boulder / 2 lead); deload ≥ 1
5. flex_phase = "strength_power" (boulder) or "base" (lead)
6. diff = total_weeks - sum(durations)
   durations[flex_phase] = max(floor, durations[flex_phase] + diff)
7. (re-applied once if step 6 hit the floor and didn't sum)
```

The scenarios provide `discipline`, `total_weeks`, `climbing_years`,
`target_grade`, `current_grade` — but **none of these directly enter the duration
formula**. Only `discipline` and `total_weeks` enter directly. The rest reach the
formula indirectly via the assessment **profile** (`finger_strength`,
`pulling_strength`, `power_endurance`, `technique`, `endurance` — each 0–100). The
profile drives only one branch: the ±1 weakness adjustment.

Without re-running `compute_assessment_profile` (read-only audit), I report the
**deterministic baseline** (no weakness firing) and the **adjusted variant** for
the most likely weakness. For each scenario, both rows sum to `total_weeks`.

| # | discipline | total | flex absorber | (no adj) base / sp / pe / perf / deload | (with weakness adj) variant |
|---|---|---|---|---|---|
| **A** | lead | 9 | base | 4/3/2/2/1 = 12 → diff=−3, base=max(2, 4−3)=**2** → **2/3/2/2/1 = 10** | **engine returns 10, not 9** — see §F1 |
| **B** | lead | 12 | base | 4/3/2/2/1 = 12 → diff=0 → **4/3/2/2/1** | adj fires? then 3/4/2/2/1 (e.g. weak finger_strength) |
| **C** | lead | 16 | base | 4/3/2/2/1 = 12 → diff=4, base=4+4=8 → **8/3/2/2/1** | with weak finger → 7/4/2/2/1 (base shrinks 1, sp grows 1, then base absorbs +4) |
| **D** | lead | 21 | base | 4/3/2/2/1 = 12 → diff=9, base=4+9=13 → **13/3/2/2/1** | with weak finger → **12/4/2/2/1** ← the KB-flagged shape |
| **E** | lead | 12 | base | 4/3/2/2/1 = 12 → **4/3/2/2/1** | a 1-yr beginner (target 6c from 6a+) almost always has weakest_axis < 50; depending on which axis: technique → base+1, performance−1 → **5/3/2/1/1**? no — perf floor=2 blocks shrink (`if shrink_phase > shrink_floor`). Result: floor blocks, no adjustment → **4/3/2/2/1**. See §F3 |
| **F** | boulder | 10 | strength_power | 2/4/1/2/1 = 10 → diff=0 → **2/4/1/2/1** | finger_strength weak → ext=sp, shr=base; base=2 not > 1 (boulder shrink_floor=1) — **wait**: shrink_floor=1 for boulder, and base=2 > 1 → fires: 1/5/1/2/1 = 10. **But final floor pass forces `base ≥ 2`** → durations["base"]=max(2,1)=2. Sum becomes 11; the "scale to total_weeks" loop runs once and does flex[sp] = max(1, 5+(10−11)) = 4. Final: **2/4/1/2/1** (adjustment effectively cancelled). See §F4 |
| **G** | boulder | 16 | strength_power | 2/4/1/2/1 = 10 → diff=6, sp=4+6=**10** → **2/10/1/2/1** | with finger weak → same cancellation as F at the floor pass; sp absorbs 6 → **2/10/1/2/1** |

Key observations from the trace:

- **Scenarios D and G show the failure mode the brief flags:** the flex absorber
  (base for lead, strength_power for boulder) takes on *all* surplus weeks
  beyond the 12/10 baseline, with no upper bound. 21-week lead → 12-13 weeks
  of base. 16-week boulder → 10 weeks of strength_power.
- **Scenario A reveals a silent under-allocation bug:** lead with `total_weeks=9`
  (the documented minimum) returns a 10-week plan. See Findings §F1.
- **Scenario E reveals a beginner-floor interaction:** for a low-experience
  user where the weakest axis would shrink performance, the floor blocks the
  shift and the plan stays flat. The literature implication ("3-week
  performance phase for advanced users") is unrelated — but it shows the
  shrink mechanism *already silently fails* in some real cases.
- **Scenario F reveals an adjustment-cancellation bug:** for boulder, the post-
  adjustment `base ≥ 2` floor effectively reverts the weakness shift because
  the flex absorber has to give the +1 back to keep the sum correct. See §F4.
- **Discipline branching is binary** (`lead` vs `boulder`). `discipline="both"` /
  `"all_round"` falls into the lead branch at line 268 (`is_boulder =
  discipline == "boulder"`). See §F5.

---

## Step 0.3 — Caps / floors / constants inventory

| File:line | Constant / guard | Value | Purpose |
|---|---|---|---|
| `macrocycle_v1.py:18` | `PHASE_ORDER` | 5 phases, fixed order | Ordering used by `from_phase` index lookup |
| `macrocycle_v1.py:221-224` | `_BASE_DURATIONS_BOULDER` | `2/4/1/2/1` (sum=10) | Boulder discipline default allocation |
| `macrocycle_v1.py:233-239` | `_WEAKNESS_ADJUSTMENTS` | 5 axis→(extend, shrink) entries | Drives the ±1 weakness shift |
| `macrocycle_v1.py:242` | `_MIN_TOTAL_WEEKS` | `9` | Lead floor; raises ValueError if `total_weeks < 9` |
| `macrocycle_v1.py:244-247` | `_BASE_DURATIONS` | `4/3/2/2/1` (sum=12) | Lead/all_round discipline default allocation |
| `macrocycle_v1.py:269` | `min_weeks = 5 if is_boulder else _MIN_TOTAL_WEEKS` | 5 boulder / 9 lead | Lower bound check before allocation |
| `macrocycle_v1.py:282` | `profile.get(axis, 50)` default | 50 | Missing axis defaults to neutral, never triggers `< 50` |
| `macrocycle_v1.py:288` | `shrink_floor` | 1 boulder / 2 lead | Minimum the weakness adjustment will leave a phase at |
| `macrocycle_v1.py:289` | weakness threshold | `< 50` | Score below which weakness fires |
| `macrocycle_v1.py:297` | `floor` (non-deload, non-base) | 1 boulder / 2 lead | Per-phase minimum after adjustment |
| `macrocycle_v1.py:298` | base floor | `max(2, base)` | Base ≥ 2 for ALL disciplines |
| `macrocycle_v1.py:301` | deload floor | `max(1, deload)` | Deload ≥ 1 |
| `macrocycle_v1.py:305` | `flex_phase` | `"strength_power"` boulder / `"base"` lead | The phase that absorbs surplus/deficit |
| `macrocycle_v1.py:309,314` | flex re-floor | `max(floor, flex+diff)` | Applied twice; can over- or under-shoot the target |
| `macrocycle_v1.py:347` | weakness threshold (incremental regen) | `< 50` | Same as full path |
| `macrocycle_v1.py:350` | `durations[shr] > 2` (incremental) | hard-coded **2**, not `shrink_floor` | Mismatch with full-regen path; see §F6 |
| `macrocycle_v1.py:355` | `non_deload_floor` (incremental) | 1 boulder / 2 lead | Same as full path |
| `macrocycle_v1.py:359-362` | floor selection (incremental) | base=2, deload=1, else=`non_deload_floor` | Same as full path |
| `macrocycle_v1.py:372` | `alloc = min(2, left)` (incremental shortfall) | hard-coded **2** | Used when remaining_weeks < min_needed; gives ≤2 per non-deload phase |
| `macrocycle_v1.py:380` | `flex` (incremental) | first non-deload remaining phase | Different policy from full path (boulder uses sp, lead uses base) |
| `macrocycle_v1.py:383,389` | flex floor (incremental) | hard-coded **2** unless flex==deload | Lead-style floor applied even for boulder; see §F7 |
| `macrocycle_v1.py:548-550` | start-date Monday auto-fix | `start -= timedelta(days=start.weekday())` | Silent — invariant enforced before allocation |
| `routers/macrocycle.py:110-114` | `_TOTAL_WEEKS_MIN_LEAD = 9`, `_TOTAL_WEEKS_MIN_BOULDER = 5`, `_TOTAL_WEEKS_MAX = 52`, `_DEFAULT_TOTAL_WEEKS_LEAD = 12`, `_DEFAULT_TOTAL_WEEKS_BOULDER = 10` | as named | Router-level guards for `start-new-cycle` |
| `routers/macrocycle.py:176-183` | `total_weeks ∈ [min_weeks, 52]` | range check | HTTP 400 if outside (start-new-cycle only) |
| `routers/onboarding.py:418-419` | `min_weeks = 5 if discipline=="boulder" else 9; total_weeks = max(min_weeks, min(total_weeks, 52))` | range clamp | Silent clamp during onboarding |
| `api/models.py:36` | `MacrocycleRequest.total_weeks: int = 12` | default 12 | Hardcoded — no boulder-aware default at this layer |
| `frontend/.../deadline-weeks-selector.tsx:36-37` | `min=8, max=24` | UI slider | **Will need to be 16 after the cap change.** Note `min=8` is below the engine lead floor of 9 — the onboarding goals page (line 252) does not pass `min`, accepting the default 8, then the backend silently clamps to 9 |

### Hardcoded **12** elsewhere (not duration math but worth noting)

- `macrocycle_v1.py:79` — `MAX_WEEKS_UNTESTED = 12` in `planner_v2.py` actually
  (not macrocycle). Coincidental.
- `macrocycle_v1.py:518,529` — default param `total_weeks: int = 12` on
  `generate_macrocycle`. Kept for backward compatibility.
- `macrocycle_archive.py:151` — `"total_weeks": 12` in a docstring example only.
- `frontend/src/components/onboarding/onboarding-context.tsx:11` — initial state
  `total_weeks: 12`.

---

## Step 0.4 — Integration points

### Test scheduling (Pass 3 in `planner_v2`)

`backend/engine/planner_v2.py:1262`:

```python
_run_pass3 = inject_tests or (is_last_week_of_phase and phase_id in ("base", "strength_power"))
```

`is_last_week_of_phase` is computed in `backend/api/deps.py:298` as
`week_in_phase == duration - 1`. This depends only on the *relative* position
within a phase, not on the absolute number of weeks. Test placement therefore
remains coherent under any duration change — tests still fire at the end of
base and end of strength_power.

`MAX_WEEKS_UNTESTED = 12` (planner_v2.py:107) is a separate *time-since-last-test*
freshness window, not a phase-duration cap. **However**, this constant becomes
relevant if the new design produces a base phase ≥ 12 weeks (today's
`scenario D` shape, 13 base weeks). The "12-weeks-untested fallback" already
silently fires inside such a phase. Capping base at 3–4 weeks resolves this
implicitly — flagging only because removing the long-base regime also removes
the only context where this fallback was needed.

`_PHASE_TEST_MAP` (planner_v2.py:80) maps `phase_id → {test_type → bool}`. No
duration coupling.

### Macrocycle archive snapshot (A-NEW-MACRO)

`backend/engine/macrocycle_archive.py:130-180` — `archive_current_macrocycle`
deep-copies the entire macrocycle dict (including every phase's
`duration_weeks`) and stores it under `state["macrocycle_history"]` with
`total_weeks` and `weeks_completed`. This is a *snapshot* — historical entries
are immutable and reflect whatever the engine produced at that time. **No
migration is needed**; all future archives will simply embed the new shape.

### Frontend rendering

- `macrocycle-timeline.tsx`: phase widths are proportional to
  `duration_weeks / total_weeks`. Layout is robust to any duration profile.
- `plan/page.tsx`, `week/page.tsx`: render `phase.duration_weeks` as labels and
  use it to enumerate weeks. No assumed value.
- `onboarding/start-week/page.tsx`: cumulative-week math for the
  "start at week N" offset slider. Robust to any phase shape.
- `deadline-weeks-selector.tsx`: hard-coded `min=8, max=24`. **Must drop max
  to 16 in the implementation A-brief**, plus tighten min to 9 (lead) / 5
  (boulder) since onboarding currently silently clamps min from 8 → 9.

### Closed-loop adaptation

`backend/engine/closed_loop_v1.py` and `backend/engine/adaptation/closed_loop.py`:
**no references** to `phase.duration_weeks`, `total_weeks`, or `phase_id`-driven
duration logic. The closed loop adjusts loads/multipliers per session, decoupled
from phase-duration math. Safe to change.

`should_extend_phase` (macrocycle_v1.py:772) and `should_trigger_adaptive_deload`
(macrocycle_v1.py:789) **exist but are not called from production code**
(only `backend/tests/test_macrocycle_v1.py` references them). See §F2.

### Other consumers of `duration_weeks`

- `backend/engine/progression_v1.py:256` — phase resolution from a date,
  iterates `cumulative += phase.duration_weeks`. Robust.
- `backend/engine/free_session.py:215` — same iteration pattern. Robust.
- `backend/engine/resolve_session.py:1743` — same iteration pattern (effective-
  phase computation for ordering). Robust.
- `backend/engine/report_engine.py:105-113` — exposes
  `phase_total_weeks` and `macrocycle_total_weeks` to the report context.
  Robust; downstream consumers display whatever number they receive.

### API request models

- `models.py:36` — `MacrocycleRequest.total_weeks: int = 12`. Hardcoded default;
  callers always pass an explicit value, but if a future caller relies on the
  default for a boulder cycle they get 12 instead of 10. Cosmetic.
- `models.py:56` — `StartNewCycleRequest.total_weeks: Optional[int] = None`.
  Falls back to the discipline default in the router. Clean.

---

## Step 0.5 — Existing helps

The current code does **not** branch on user level (`experience.climbing_years`,
target grade gap, profile axis scores) when allocating durations. The only
per-user signal that reaches the formula is the weakness ±1 shift — and even
that is independent of climbing experience.

What does exist that could be leveraged:

1. **Profile axes are present.** `assessment_profile` already arrives at
   `_compute_phase_durations` with five 0-100 scores. A level-aware policy can
   read these directly without plumbing changes.
2. **`_WEAKNESS_ADJUSTMENTS` table is the only existing per-user lever.** It
   currently shifts ±1 between exactly two phases. Extending it to a per-user
   target-shape lookup (e.g., "advanced redpoint → performance ≥ 3") is a
   contained edit if we keep the table-driven style.
3. **Discipline branching is already in place** for base allocation, flex
   absorber choice, and floors. Adding a per-discipline cap is a one-line
   addition next to `_BASE_DURATIONS_BOULDER`.
4. **`grade_gap(target, current)` and `_GRADE_INDEX`** (assessment_v1.py) are
   already imported by `macrocycle_v1.py:11` and used in `_validate_goal`
   (warnings only). They can drive a target-difficulty branch with no new
   imports.
5. **Total-weeks clamping is already done at three layers** (frontend slider,
   onboarding router, start-new-cycle router) — adding a 16-week cap at all
   three layers is mechanical. The `_MIN_TOTAL_WEEKS` pattern already shows
   where to put a `_MAX_TOTAL_WEEKS` peer constant.
6. **`MacrocycleRequest` already accepts `from_phase`**, so the planner already
   knows how to regenerate durations for a partial cycle — useful if we want
   a one-time migration helper that re-flattens existing long base phases for
   in-flight users. (Not in scope of the current redesign, but the rail
   exists.)

What does **not** exist:

- No `total_weeks` upper cap (anywhere) — `52` is the only enforced max, well
  beyond the upcoming 16.
- No per-phase upper cap — base can grow unbounded; strength_power can grow
  unbounded for boulder.
- No level-aware branching at all in macrocycle generation. (`compute_assessment_profile`
  uses `climbing_years` to score endurance, but nothing in macrocycle reads it.)
- No "target performance phase length" parameter. Performance defaults to 2
  and only falls below via floor pathology, never grows from a per-user signal.
- No reuse of `goal.target_style` (`redpoint` / `onsight`) in duration math.

---

## Findings

### F1 — `total_weeks=9` (lead) silently returns a 10-week plan
**Severity:** real bug.
The lead floor `_MIN_TOTAL_WEEKS = 9` admits 9, but the base-allocation sum is
12. With `diff = 9 - 12 = −3` and `flex_phase = "base"`,
`durations["base"] = max(2, 4 − 3) = max(2, 1) = 2`. Sum = 2+3+2+2+1 = **10**.
The final re-flexer (line 314) runs once more: `durations["base"] = max(2, 2 + (9 − 10)) = 2`. Still 10. The function returns a dict whose sum exceeds
`total_weeks` by 1. `generate_macrocycle` at line 636 then computes
`end_date = start + total_weeks × 7 days`, but the phase ranges (lines 612–613)
walk forward by `duration_weeks`, ending one week past `end_date`.
The same pathology applies to **lead total_weeks ∈ {9, 10}** and **boulder
total_weeks ∈ {5, 6}** because in those cases the floors block enough
flex-shrink to hit the target.

### F2 — Dead code: `should_extend_phase`, `should_trigger_adaptive_deload`
**Severity:** doc/clarity.
Both functions are tested in `test_macrocycle_v1.py` but **never called from
production code** (`backend/api/`, `backend/engine/` outside the file itself,
or any router). The "if 2 weeks of hard feedback, extend by +2 weeks" doctring
sounds load-bearing for the adaptive replan story but is not wired in. Either
they should be removed or wired into the closed-loop pipeline. Worth flagging
because the brief mentions adaptive periodization — these functions look like
the place where it would live, but they don't run.

### F3 — Weakness adjustment is silently floor-blocked for beginners
**Severity:** behaviour worth verifying.
For lead with weakest axis = `technique` (often the case for low-experience
users), `_WEAKNESS_ADJUSTMENTS["technique"] = ("base", "performance")`. Shrink
phase = performance (default value 2). The condition
`durations[shrink_phase] > shrink_floor` (line 291) becomes `2 > 2` = False. No
adjustment fires. Same blockage for `power_endurance` weakness (shrink =
strength_power, default 3, *would* fire — only blocked at value 2). The result
is asymmetric: weakness shifts on the "extend base / shrink other" axis are
quiet for already-low default phases.

### F4 — Boulder weakness adjustment self-cancels at the floor pass
**Severity:** subtle bug.
In `_compute_phase_durations`, the floor pass at line 298 forces
`durations["base"] = max(2, base)` *after* the adjustment. For a boulder cycle
where the weakness adjustment shrunk base from 2 → 1, the floor lifts it
back to 2, so the +1 given to the extend phase is now over-budget. The flex
absorber (`strength_power`) takes the −1 back, undoing the entire shift.
Net effect for boulder: the weakness adjustment table line for
`finger_strength`, `pulling_strength` (both shrink base) silently doesn't apply.
Only `endurance` (extend=base, shrink=strength_power) and `power_endurance`
(extend=power_endurance, shrink=strength_power) and `technique` (extend=base,
shrink=performance) can actually move durations for boulder.

### F5 — `discipline="all_round"` falls through to the lead branch
**Severity:** behaviour worth confirming.
Line 268 sets `is_boulder = discipline == "boulder"`. Anything else — including
`"both"` and `"all_round"` — gets `_BASE_DURATIONS` (4/3/2/2/1) and
`flex_phase = "base"`. The session-pool builder (`_build_session_pool`) merges
lead+boulder pools for `"both"` / `"all_round"`, so there's a structural mix at
the session layer but **not** at the duration layer. Worth deciding whether
all_round should be its own discipline-class for durations or stay aliased to
lead.

### F6 — Incremental-regen path uses different magic numbers
**Severity:** clarity / consistency.
`_compute_remaining_durations` (line 319) hard-codes the shrink threshold as
`> 2` (line 350) — not `> shrink_floor`. For boulder this means weakness
adjustments behave differently in incremental regen vs. full regen. Same
function uses `2` as the per-phase allocation when remaining_weeks is below
floor (line 372), and `2` as the flex floor on lines 383/389 — without
checking discipline. The full-regen and incremental-regen formulas have
drifted; the brief's refactor is a chance to converge them.

### F7 — Incremental-regen `flex` selection picks the first non-deload phase
**Severity:** behaviour worth confirming.
Line 380: `flex = next((p for p in remaining_phases if p != "deload"), remaining_phases[0])`.
Independent of discipline. For an incremental regen *from* `power_endurance`
onward, the flex phase becomes `power_endurance`, not `strength_power` (boulder)
or `base` (lead). Means the absorber depends on which phase you regen from —
and any extra weeks go into the *first remaining* phase. This may surprise.

### F8 — `MacrocycleRequest.total_weeks` defaults to 12 even for boulder
**Severity:** cosmetic.
`backend/api/models.py:36`. `POST /api/macrocycle/generate` without an explicit
`total_weeks` for a boulder user produces a 12-week boulder cycle (vs. the
discipline default of 10 used elsewhere). Real callers always pass it
explicitly, but the inconsistency is worth fixing in the same A-brief.

### F9 — Frontend slider min=8 vs engine lead floor=9
**Severity:** UX glitch — already mitigated by silent backend clamp.
`deadline-weeks-selector.tsx:36` defaults `min=8`; `onboarding/goals/page.tsx`
does not override. Backend onboarding silently clamps to 9. Slider can land
on 8, the user types `8`, the response shows a 9-week cycle. Fix in the
implementation brief alongside the new max=16.

### F10 — No upper cap on flex absorber
**Severity:** the bug the brief is fixing.
The cause of the 21 → 12/4/2/2/1 shape is line 309 + 314: the flex absorber
takes 100% of the surplus once defaults and weakness shifts have been applied.
There is *no* per-phase upper cap. Implementation brief should introduce
per-phase caps (especially `base ≤ 4` and `strength_power ≤ ~5`).

---

## Open questions for the implementation phase

1. **Where exactly does the 16-week hard cap live?**
   Options: (a) raise ValueError in `_compute_phase_durations`, (b) clamp at
   each router (3 places), (c) clamp at the engine entry `generate_macrocycle`.
   Recommend (c) + frontend slider cap, with a single `_MAX_TOTAL_WEEKS_*`
   constant per discipline. Caller-side clamp leaves engine resilient.

2. **Base hard cap: 3 or 4?**
   Pending KB. The new policy must also decide: cap is *per-discipline* or
   global? Currently base default = 4 (lead) and 2 (boulder). KB cap of 4 means
   lead default stays put; cap of 3 means lead default drops by 1.

3. **What is the "advanced lead + redpoint" trigger for performance ≥ 3?**
   Candidates: `goal.target_style == "redpoint"` AND `assessment.profile.power_endurance ≥ X` AND
   `grade_gap(target, current) ≥ Y` AND `experience.climbing_years ≥ Z`.
   Decide which signals constitute "advanced" — climbing_years is currently
   used only in endurance scoring; we'd be introducing it as a duration
   signal for the first time.

4. **What is the new flex-absorber policy after caps?**
   With `base ≤ 4` and `total_weeks ≤ 16`, lead surplus over default 12 is at
   most 4 weeks. If base is capped, where do extra weeks go? Candidates: split
   strength_power (cap ~5) and power_endurance (cap ~3); or add a second base
   block at the end ("re-base"); or extend deload to 2.

5. **How do we treat `discipline="both"` / `"all_round"`?**
   Today aliased to lead for durations. With new caps this matters more — a
   16-week all_round plan will look different from a lead one only via the
   merged session pool, not via the phase shape. Confirm desired behaviour.

6. **Existing in-flight users with long base phases.**
   Should the implementation A-brief offer a one-time migration that
   regenerates remaining phases (`generate_macrocycle(..., from_phase="current")`),
   or do we let existing cycles ride out and only apply new caps to *new*
   cycles via `start-new-cycle`? Recommend the latter — past sessions are
   immutable per CLAUDE.md, so any in-flight regen has to be `from_phase=current`
   and that respects past weeks but reshuffles upcoming ones, which is
   acceptable but wants a UX prompt.

7. **`_compute_remaining_durations` also needs to learn the new caps.**
   Otherwise an incremental regen circumvents them. The two functions should
   be consolidated.

8. **Bug F1 (9-week lead returns 10) — fix here or separate B-brief?**
   Recommend folding into the same A-brief since the cap rewrite touches the
   same lines.

9. **Should the fixed dead functions (F2) be removed or wired in?**
   Out of scope of duration redesign, but the brief mentions adaptive
   periodization — worth a one-line decision.

---

## Summary

- **Single source of truth for duration**: `_compute_phase_durations`
  (`macrocycle_v1.py:250-316`) — a 67-line function with a documented but
  imperfect 7-step formula. Its sibling `_compute_remaining_durations`
  (lines 319-392) handles incremental regen with subtly different magic
  numbers.
- **Drivers of the formula**: only `discipline` and `total_weeks` directly;
  `assessment_profile` indirectly via the ±1 weakness shift. Climbing years,
  target grade, and grade gap are **not** consulted.
- **Failure mode the brief is fixing (F10)**: no per-phase upper cap; the flex
  absorber (base for lead, strength_power for boulder) takes 100% of the
  surplus, producing literature-incompatible long base or long
  strength_power phases on `total_weeks > 12-13`.
- **Side findings**: F1 (off-by-one in 9-week lead), F4 (boulder weakness
  cancellation), F2 (dead adaptive functions), F6 / F7 (formula drift between
  full-regen and incremental-regen paths), F5 (all_round aliased to lead),
  F8 / F9 (cosmetic API/frontend inconsistencies). All of these are worth
  bundling into the same A-brief if the rewrite touches these regions.
- **Integration points**: archive (snapshot — no migration), planner Pass 3
  (uses `is_last_week_of_phase`, robust to any duration), frontend
  (proportional render, robust except the 24-week slider max), closed-loop
  (no coupling). **The rewrite is largely self-contained inside the engine
  module** — frontend needs only the slider cap drop.

---

*End of D233 Phase 0 audit. Awaiting OK before any Phase 2 implementation work.*
