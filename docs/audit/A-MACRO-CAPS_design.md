# A-MACRO-CAPS — Phase 1 algorithm design (sign-off required)

**Brief:** A-MACRO-CAPS (canonical A218)
**Date:** 2026-05-07
**Phase:** 1 of 6 — algorithm design only, **no code changes yet**.
**Predecessors:** D233 (duration audit), D234 (deadline coupling).
**Branch:** `feat/macrocycle-caps`
**STOP gate:** this document. Daniele approves before Phase 2 (engine implementation).

---

## 1. Algorithm — pseudocode

### Constants

```python
PHASE_ORDER = ("base", "strength_power", "power_endurance", "performance", "deload")

# Lead / all_round / both
_BASE_DURATIONS_LEAD     = {"base": 4, "strength_power": 3, "power_endurance": 2, "performance": 2, "deload": 1}  # sum 12
_PHASE_CAPS_LEAD         = {"base": 4, "strength_power": 4, "power_endurance": 3, "performance": 3, "deload": 2}  # sum 16
_PHASE_FLOORS_LEAD       = {"base": 4, "strength_power": 2, "power_endurance": 2, "performance": 2, "deload": 1}  # sum 11
_SURPLUS_PRIORITY_LEAD   = ("performance", "strength_power", "power_endurance", "deload")
_MIN_TOTAL_WEEKS_LEAD    = 11

# Boulder
_BASE_DURATIONS_BOULDER  = {"base": 2, "strength_power": 4, "power_endurance": 1, "performance": 2, "deload": 1}  # sum 10
_PHASE_CAPS_BOULDER      = {"base": 4, "strength_power": 5, "power_endurance": 3, "performance": 3, "deload": 2}  # sum 17
_PHASE_FLOORS_BOULDER    = {"base": 2, "strength_power": 2, "power_endurance": 1, "performance": 2, "deload": 1}  # sum  8
_SURPLUS_PRIORITY_BOULDER = ("performance", "strength_power", "power_endurance", "base", "deload")
_MIN_TOTAL_WEEKS_BOULDER = 8

_MAX_TOTAL_WEEKS = 16  # both disciplines

_WEAKNESS_ADJUSTMENTS = {  # unchanged from existing code
    "power_endurance":  ("power_endurance",  "strength_power"),
    "endurance":        ("base",             "strength_power"),
    "finger_strength":  ("strength_power",   "base"),
    "pulling_strength": ("strength_power",   "base"),
    "technique":        ("base",             "performance"),
}
```

Note: `_PHASE_CAPS_BOULDER` sums to 17, not 16. This is intentional — at
`total_weeks=16` the surplus distribution exhausts before all phases hit cap
(see §2 boulder table). The "extra" cap on `strength_power` (5 vs 4) reflects
boulder's strength-bias and KB Q3.

For lead, `_PHASE_CAPS_LEAD` sums exactly to 16, which is also the max — so
`total=16` saturates every cap, producing the unique distribution `4/4/3/3/2`.

### Single function (consolidates current `_compute_phase_durations` and `_compute_remaining_durations` — see §6)

```python
def _compute_phase_durations(
    profile: Dict[str, int],
    total_weeks: int,
    discipline: str = "lead",
    *,
    phases: Optional[List[str]] = None,   # None ⇒ full cycle (PHASE_ORDER)
) -> Dict[str, int]:
    """Allocate `total_weeks` across the phases listed in `phases`
    (default = full PHASE_ORDER).

    Used by both full-regen and incremental-regen paths. The incremental path
    passes `phases` = remaining phases and `total_weeks` = remaining weeks.

    Raises:
        ValueError if `total_weeks` is outside the legal range for the scope.
    """
    is_boulder = discipline == "boulder"
    defaults  = _BASE_DURATIONS_BOULDER if is_boulder else _BASE_DURATIONS_LEAD
    caps      = _PHASE_CAPS_BOULDER     if is_boulder else _PHASE_CAPS_LEAD
    floors    = _PHASE_FLOORS_BOULDER   if is_boulder else _PHASE_FLOORS_LEAD
    priority  = _SURPLUS_PRIORITY_BOULDER if is_boulder else _SURPLUS_PRIORITY_LEAD
    min_weeks = _MIN_TOTAL_WEEKS_BOULDER if is_boulder else _MIN_TOTAL_WEEKS_LEAD

    if phases is None:
        phases = list(PHASE_ORDER)

    # 1. Range validation (defense in depth — routers also clamp)
    scope_min = sum(floors[p] for p in phases)
    scope_max = sum(caps[p]   for p in phases)
    full_min  = min_weeks if set(phases) == set(PHASE_ORDER) else scope_min
    if total_weeks < full_min:
        raise ValueError(f"total_weeks {total_weeks} < min {full_min} for {discipline}")
    if total_weeks > _MAX_TOTAL_WEEKS:
        raise ValueError(f"total_weeks {total_weeks} > max {_MAX_TOTAL_WEEKS}")
    if total_weeks > scope_max:
        # Only reachable from incremental regen with absurd scope mismatch
        raise ValueError(f"total_weeks {total_weeks} exceeds scope max {scope_max}")

    # 2. Initialize at defaults (only for phases in scope)
    durations = {p: defaults[p] for p in phases}

    # 3. Weakness adjustment — clamped to floors and caps (no silent self-cancel)
    weakest_axis, weakest_score = _find_weakest_axis(profile)
    if (weakest_axis is not None
            and weakest_score < 50
            and weakest_axis in _WEAKNESS_ADJUSTMENTS):
        ext, shr = _WEAKNESS_ADJUSTMENTS[weakest_axis]
        # Both phases must be in scope, and the shift must respect floor/cap.
        if (ext in durations and shr in durations
                and durations[ext] + 1 <= caps[ext]
                and durations[shr] - 1 >= floors[shr]):
            durations[ext] += 1
            durations[shr] -= 1
        # else: clean no-op. No surplus/deficit to absorb.

    # 4. Surplus distribution OR shortfall reduction
    diff = total_weeks - sum(durations.values())
    if diff > 0:
        # Distribute to caps in priority order
        for p in priority:
            if p not in durations:
                continue
            give = min(diff, caps[p] - durations[p])
            durations[p] += give
            diff -= give
            if diff == 0:
                break
        if diff != 0:
            raise ValueError(f"Cannot distribute surplus {diff}: scope at cap")
    elif diff < 0:
        # Reduce in INVERSE priority — deload first, performance last; never below floor.
        # base is intentionally NOT in any reduce path for either discipline:
        #   - lead: floor==cap==4, base never moves.
        #   - boulder: base is in _SURPLUS_PRIORITY but inverse order puts it before perf;
        #     however boulder base default is 2 = floor, so inverse reduce on base is also a no-op.
        shortfall = -diff
        for p in reversed(priority):
            if p not in durations:
                continue
            take = min(shortfall, durations[p] - floors[p])
            durations[p] -= take
            shortfall -= take
            if shortfall == 0:
                break
        if shortfall != 0:
            raise ValueError(f"Cannot absorb shortfall {shortfall}: scope at floor")

    # 5. Postcondition
    assert sum(durations.values()) == total_weeks, "duration math broke"
    for p in phases:
        assert floors[p] <= durations[p] <= caps[p], f"{p} {durations[p]} out of [{floors[p]},{caps[p]}]"
    return durations
```

### Helper

```python
def _find_weakest_axis(profile: Dict[str, int]) -> Tuple[Optional[str], int]:
    """Return (axis_name, score) for the lowest-scoring axis among the five
    weakness-adjustment-relevant axes. Returns (None, 101) if profile is empty
    or all axes are missing."""
    weakest = None
    score = 101
    for axis in ("power_endurance", "endurance", "finger_strength",
                 "pulling_strength", "technique"):
        v = profile.get(axis, 50)
        if v < score:
            score = v
            weakest = axis
    return weakest, score
```

### Note on scope semantics

For full-regen, `phases = PHASE_ORDER`. For incremental-regen called from
`generate_macrocycle(..., from_phase="performance")`, `phases = ["performance", "deload"]`
and `total_weeks` is the *remaining* weeks. The validation at step 1 then uses
`scope_min` (sum of floors over the scope, e.g. 2+1=3 for [perf,deload]) instead
of `_MIN_TOTAL_WEEKS_*` — because the full-cycle minimum applies only to a
full-cycle generation.

---

## 2. Verification tables (no weakness adjustment)

The first row is `total_weeks`, the rest are the per-phase weeks the algorithm
produces. Sums verified.

### Lead (range 11–16)

| total | base | sp | pe | perf | deload | sum | path |
|---|---|---|---|---|---|---|---|
| 11 | **4** | 2 | 2 | 2 | 1 | 11 | shortfall 1 → reduce sp (only phase with room: sp 3→2) |
| 12 | 4 | 3 | 2 | 2 | 1 | 12 | defaults — no surplus, no shortfall |
| 13 | 4 | 3 | 2 | **3** | 1 | 13 | surplus 1 → perf 2→3 |
| 14 | 4 | **4** | 2 | 3 | 1 | 14 | surplus 2 → perf 2→3, sp 3→4 |
| 15 | 4 | 4 | **3** | 3 | 1 | 15 | surplus 3 → perf+1, sp+1, pe 2→3 |
| 16 | 4 | 4 | 3 | 3 | **2** | 16 | surplus 4 → perf+1, sp+1, pe+1, deload 1→2 |

Matches the brief's locked verification table for lead. The `total=16` shape
`4/4/3/3/2` is the KB-locked option B.

### Boulder (range 8–16)

| total | base | sp | pe | perf | deload | sum | path |
|---|---|---|---|---|---|---|---|
| 8 | 2 | **2** | 1 | 2 | 1 | 8 | shortfall 2 → reduce sp 4→2 (only phase above floor) |
| 9 | 2 | **3** | 1 | 2 | 1 | 9 | shortfall 1 → reduce sp 4→3 |
| 10 | 2 | 4 | 1 | 2 | 1 | 10 | defaults |
| 11 | 2 | 4 | 1 | **3** | 1 | 11 | surplus 1 → perf 2→3 |
| 12 | 2 | **5** | 1 | 3 | 1 | 12 | surplus 2 → perf+1, sp 4→5 |
| 13 | 2 | 5 | **2** | 3 | 1 | 13 | surplus 3 → perf+1, sp+1, pe 1→2 |
| 14 | **3** | 5 | 2 | 3 | 1 | 14 | surplus 4 → perf+1, sp+1, pe+1, base 2→3 |
| 15 | 3 | 5 | **3** | 3 | 1 | 15 | surplus 5 → perf+1, sp+1, pe 1→3 (give 2), base+1 — wait, recompute: |

Let me redo `total=15` boulder step by step:
- defaults sum=10, surplus=5
- perf: cap 3, current 2 → give 1, surplus=4
- sp:   cap 5, current 4 → give 1, surplus=3
- pe:   cap 3, current 1 → give 2, surplus=1
- base: cap 4, current 2 → give 1, surplus=0
- deload: not reached
Result: **3/5/3/3/1 = 15 ✓**

| 15 | 3 | 5 | 3 | 3 | 1 | 15 | surplus 5 → perf+1, sp+1, pe+2, base+1 |
| 16 | **4** | 5 | 3 | 3 | 1 | 16 | surplus 6 → perf+1, sp+1, pe+2, base+2 |

`total=16` boulder shape: `4/5/3/3/1`. Note deload stays at 1 (priority places
deload last; surplus exhausts at base before reaching deload). **Open question
1** below asks Daniele whether boulder should also bump deload to 2 at total=16.

### Lead vs boulder at total=16

| discipline | base | sp | pe | perf | deload |
|---|---|---|---|---|---|
| lead | 4 | 4 | 3 | 3 | 2 |
| boulder | 4 | 5 | 3 | 3 | 1 |

The +1 sp / −1 deload swap reflects boulder's strength-bias (KB Q3).

---

## 3. Weakness adjustment — worked examples (proves F4 fix)

For each axis × discipline × {total=12, total=16}, what the algorithm produces.
Notation: **bold** = phase moved by weakness adjustment. The post-step-3 row
("after weakness") shows the durations *before* surplus distribution.

### Lead at total=12

The base phase is locked at 4 (floor==cap==4). Any weakness shift that targets
base — extending or shrinking it — is a clean no-op.

| weakest axis | shift target | floor/cap check | result |
|---|---|---|---|
| `power_endurance` (extend pe, shrink sp) | pe 2→3 vs cap 3 ✓; sp 3→2 vs floor 2 ✓ | **fires** → 4/2/3/2/1 = 12 |
| `endurance` (extend base, shrink sp) | base 4→5 vs cap **4 ✗** | no-op → 4/3/2/2/1 |
| `finger_strength` (extend sp, shrink base) | base 4→3 vs floor **4 ✗** | no-op → 4/3/2/2/1 |
| `pulling_strength` (extend sp, shrink base) | base→3 vs floor 4 ✗ | no-op → 4/3/2/2/1 |
| `technique` (extend base, shrink perf) | base 4→5 vs cap 4 ✗ | no-op → 4/3/2/2/1 |
| none / all ≥ 50 | — | 4/3/2/2/1 |

**Lead total=12 has effectively one active weakness shift** (`power_endurance`).
The other four shifts are clean no-ops because they target the locked `base`.
Daniele to confirm — see Open Question 2.

### Lead at total=16

Surplus distribution proceeds after the weakness step.

| weakest axis | after weakness | surplus | final |
|---|---|---|---|
| `power_endurance` | 4/2/3/2/1 (sum 12) | 4 | perf+1, sp+2, pe at cap, deload+1 → **4/4/3/3/2** |
| `endurance` | 4/3/2/2/1 (no-op) | 4 | perf+1, sp+1, pe+1, deload+1 → **4/4/3/3/2** |
| `finger_strength` | 4/3/2/2/1 (no-op) | 4 | same → **4/4/3/3/2** |
| `pulling_strength` | 4/3/2/2/1 (no-op) | 4 | same → **4/4/3/3/2** |
| `technique` | 4/3/2/2/1 (no-op) | 4 | same → **4/4/3/3/2** |
| none | 4/3/2/2/1 | 4 | same → **4/4/3/3/2** |

**At lead total=16, all profiles converge on `4/4/3/3/2`**. The `total_weeks=16`
distribution is fully determined regardless of the user's profile because the
caps sum exactly to 16. The weakness adjustment changes the *path*, not the
result.

### Boulder at total=10

| weakest axis | shift check | result |
|---|---|---|
| `power_endurance` (pe+, sp−) | pe 1→2 vs cap 3 ✓; sp 4→3 vs floor 2 ✓ | **fires** → 2/3/2/2/1 |
| `endurance` (base+, sp−) | base 2→3 vs cap 4 ✓; sp 4→3 vs floor 2 ✓ | **fires** → 3/3/1/2/1 |
| `finger_strength` (sp+, base−) | base 2→1 vs floor **2 ✗** | no-op → 2/4/1/2/1 |
| `pulling_strength` (sp+, base−) | base→1 vs floor 2 ✗ | no-op → 2/4/1/2/1 |
| `technique` (base+, perf−) | perf 2→1 vs floor **2 ✗** | no-op → 2/4/1/2/1 |
| none | — | 2/4/1/2/1 |

**Three weakness axes are active for boulder at total=10** (pe, endurance), and
two more above. Stronger differentiation than lead at default.

### Boulder at total=12 — F4 fix demonstration

D233 §F4 noted that the **OLD** algorithm, on a boulder cycle with
`finger_strength` weakness:
1. Tried to shrink base 2→1 (boulder shrink_floor was 1, so it fired).
2. Floor pass forced base back to 2.
3. The +1 given to sp now over-budgets the sum → flex absorber `sp` took −1 →
   net 0 → output `2/4/1/2/1` (same as no-weakness, but reached via a buggy path
   that could over- or under-shoot at higher totals).

**NEW algorithm** for boulder at total=12, weakest=`finger_strength`:
- weakness check: base 2→1 vs floor 2 ✗ → **clean no-op**.
- defaults: 2/4/1/2/1, surplus 2.
- distribute: perf 2→3 (surplus 1), sp 4→5 (surplus 0).
- result: `2/5/1/3/1 = 12`.

**OLD algorithm** for boulder at total=12, weakest=`finger_strength` (worked
out from D233 trace):
- weakness fires (boulder shrink_floor=1 admits 2→1): 1/5/1/2/1.
- floor pass forces base=max(2,1)=2: 2/5/1/2/1, sum=11.
- flex absorber sp: durations[sp] = max(1, 5 + (12 − 11)) = 6.
- final: `2/6/1/2/1 = 12` — **with sp at 6, exceeding any sane cap** (no cap existed).

Net behavioral difference at boulder total=12, finger_strength weak: OLD `2/6/1/2/1`
(buggy, sp inflated), NEW `2/5/1/3/1` (clean, perf gets one of the surplus weeks).
This is the F4 fix — observable as a real numeric change at total>10, not just
a code-clarity refactor.

### Boulder at total=16

| weakest axis | after weakness | surplus | final |
|---|---|---|---|
| `power_endurance` | 2/3/2/2/1 (sum 10) | 6 | perf+1, sp+2, pe+1, base+2 → **4/5/3/3/1** |
| `endurance` | 3/3/1/2/1 (sum 10) | 6 | perf+1, sp+2, pe+2, base+1 → **4/5/3/3/1** |
| `finger_strength` | 2/4/1/2/1 (no-op) | 6 | perf+1, sp+1, pe+2, base+2 → **4/5/3/3/1** |
| `pulling_strength` | 2/4/1/2/1 (no-op) | 6 | same → **4/5/3/3/1** |
| `technique` | 2/4/1/2/1 (no-op) | 6 | same → **4/5/3/3/1** |
| none | 2/4/1/2/1 | 6 | same → **4/5/3/3/1** |

All boulder profiles converge on `4/5/3/3/1` at total=16.

---

## 4. Edge cases enumerated

### EC-1 — `total_weeks > _MAX_TOTAL_WEEKS` (=16)

Routers (`onboarding.py:419`, `macrocycle.py:176-183`, frontend slider `max=16`)
clamp before reaching the engine. The engine raises `ValueError` (defense in
depth). No silent acceptance.

### EC-2 — `total_weeks < _MIN_TOTAL_WEEKS_*`

For lead, min=11. For boulder, min=8. Same defense-in-depth pattern: routers
clamp; engine raises if `total_weeks < min_weeks` for full-regen scope. For
incremental regen, the floor sum of the scope replaces `min_weeks`.

### EC-3 — All weakness axes ≥ 50 (no weakness fires)

`_find_weakest_axis` still returns the lowest of the five, but the
`< 50` guard prevents any shift. Default allocation goes through the standard
surplus/shortfall path. Behavior identical to "weakness shift blocked by
floor/cap".

### EC-4 — `profile` is empty / missing

`profile.get(axis, 50)` defaults to 50. `_find_weakest_axis` returns the first
axis as weakest (all tied at 50), but `weakest_score < 50` is False → no shift.
No crash, no silent `KeyError`. (Existing behavior preserved.)

### EC-5 — `discipline ∈ ("both", "all_round")`

Aliased to lead, per D233 §F5 and brief locked decision. No new branch. The
session-pool builder (`_build_session_pool`) already merges lead+boulder pools
for these disciplines — that's a separate axis of discipline-handling and is
unchanged by this brief.

### EC-6 — Incremental regen with scope shorter than full

Caller passes `phases=remaining`, `total_weeks=remaining_weeks`. The function
validates against `scope_min = sum(floors over scope)` and `scope_max = sum(caps
over scope)`. The full-cycle `_MIN_TOTAL_WEEKS_*` does not apply because we're
not generating a full cycle.

The priority list is filtered (`if p not in durations: continue`), so phases
outside the scope are skipped during distribution.

### EC-7 — Weakness adjustment where extend-or-shrink phase is outside scope

E.g., incremental regen from `power_endurance` with `weakest=technique`
(extend=base, shrink=perf — base not in scope). The guard `ext in durations and
shr in durations` skips the shift entirely. Clean no-op.

### EC-8 — `total_weeks` exactly at floor sum

Lead total=11: shortfall 1. Reduce in inverse priority [deload, pe, sp, perf];
deload at floor 1, pe at floor 2, sp 3>floor 2 → reduce sp by 1. Lands at
4/2/2/2/1. Floors sum = 4+2+2+2+1 = 11, equal. Algorithm correct.

Boulder total=8: shortfall 2. Reduce [deload, base, pe, sp, perf]; deload, base,
pe at floor; sp 4>floor 2 → reduce sp by 2. Lands at 2/2/1/2/1 = 8. Correct.

### EC-9 — `total_weeks` exactly at cap sum

Lead caps sum to 16, equal to `_MAX_TOTAL_WEEKS`. At total=16, every cap
saturates. (Already covered by §2.)

Boulder caps sum to 17, but `_MAX_TOTAL_WEEKS=16`. At total=16, surplus exhausts
before all caps reached (deload stays at 1). See Open Question 1.

### EC-10 — F1 fix (silent off-by-one)

Was: lead total=9 returned a 10-week plan (D233 §F1).
Now: lead total=9 raises ValueError (`< _MIN_TOTAL_WEEKS_LEAD = 11`). Routers
clamp the user's input to [11, 16] before the call. The off-by-one path is
structurally unreachable.

### EC-11 — Postcondition assertions

The function ends with `assert sum(durations) == total_weeks` and per-phase
`floor ≤ d ≤ cap` checks. These should *never* trip in production — they're
defensive. If they trip, there's a logic bug we want loud, not silent.

---

## 5. Boulder priority order — rationale

Lead surplus priority: `["performance", "strength_power", "power_endurance", "deload"]`.
Boulder surplus priority: `["performance", "strength_power", "power_endurance", "base", "deload"]`.

Both put **performance first** — KB Q-perf says extra weeks past the default
12/10 should buy peak-projecting time, not more base. Both put **deload last**
because deload is recovery-bookend, not a productive training phase.

The discipline-specific divergence is **base position**:
- Lead: base is locked at 4 (floor==cap), so it never appears in the priority
  list — there's no slack to fill.
- Boulder: base default 2, cap 4, floor 2. There's 2 weeks of slack. Boulder
  places base **before deload** because:
  1. KB Q3: bouldering is not an aerobic sport. Extra base weeks are valuable
     for movement quality / joint prep, but only past `pe` and `sp` are filled.
  2. Beginner-boulder users (a meaningful segment per audit) benefit more
     from extra technique work than from extra deload — base in v1 carries the
     `technique_focus_gym` and `boulder_circuit_gym` primaries.
- Why not before `pe`? Because boulder pe default is 1 (the lowest of any
  phase), and KB Q-pe says even short blocks of pe are valuable for
  fatigue-tolerance — boost to 3 (cap) before adding base weeks.

The order `[perf, sp, pe, base, deload]` follows the rule "extend the most
training-rich phases before the buffer phases (base, deload)".

**Open Question 3**: should boulder have an alternate default for users who
self-identify as "still learning movement"? Out of scope for v1 of this brief —
flagging as future work.

---

## 6. `_compute_remaining_durations` — strategy

**Decision: consolidate into a single function `_compute_phase_durations(profile, total_weeks, discipline, *, phases=None)`.** The current
`_compute_remaining_durations` is removed.

### Why consolidate

D233 §F6/§F7 documented two real divergences between the current full-regen
and incremental-regen functions:

- §F6: `_compute_remaining_durations` uses `> 2` instead of `> shrink_floor`
  (line 350) — boulder bug.
- §F7: incremental flex picks "first non-deload remaining phase", which differs
  from the full path's discipline-aware flex.

These were not deliberate design choices, just drift. A single function with a
`phases` parameter eliminates both:

1. The constants (caps, floors, defaults, priority) are global and discipline-
   aware. No `> 2` magic.
2. The priority list is simply *filtered* to the scope (`if p not in
   durations: continue`). The "first remaining phase" heuristic disappears.

### Caller wiring

`generate_macrocycle(...)` becomes:

```python
if from_phase:
    # ... compute kept_phases, weeks_used, phases_to_gen, remaining_weeks (existing logic) ...
    durations = _compute_phase_durations(
        assessment_profile, remaining_weeks,
        discipline=discipline, phases=phases_to_gen,
    )
else:
    durations = _compute_phase_durations(
        assessment_profile, total_weeks, discipline=discipline,
    )
```

The dual-path (`if from_phase: ... else: ...`) at the *caller* level remains, as
it controls `kept_phases` and `current_week`. Only the duration math is
consolidated.

### Backwards compatibility for `_compute_remaining_durations`

The old function has no callers outside `generate_macrocycle` itself
(verified by D233 §0.1 grep). Safe to remove. Tests in
`test_macrocycle_v1.py` that import it must be migrated to call the unified
function with `phases=`.

### Alternative considered: shared helpers, two functions

I considered keeping both functions but extracting `_apply_caps_floors`,
`_distribute_surplus`, `_distribute_shortfall`. Rejected because the orchestration
logic (defaults → weakness → diff → distribute) is short and identical between
paths. Two near-duplicate orchestrators would just re-introduce drift.

---

## 7. Test scenarios — Phase 3 plan

Below are 21 scenarios (≥18 required). Each row has expected `base/sp/pe/perf/deload`.
Pre-computed using the algorithm in §1.

### Lead, no weakness (rows 1–6)

| # | discipline | total | weakest axis | expected |
|---|---|---|---|---|
| 1 | lead | 11 | none | 4/2/2/2/1 |
| 2 | lead | 12 | none | 4/3/2/2/1 |
| 3 | lead | 13 | none | 4/3/2/3/1 |
| 4 | lead | 14 | none | 4/4/2/3/1 |
| 5 | lead | 15 | none | 4/4/3/3/1 |
| 6 | lead | 16 | none | 4/4/3/3/2 |

### Lead, with weakness (rows 7–10) — covers all paths

| # | discipline | total | weakest axis | expected | path note |
|---|---|---|---|---|---|
| 7 | lead | 12 | power_endurance | 4/2/3/2/1 | only active lead weakness shift at default total |
| 8 | lead | 12 | finger_strength  | 4/3/2/2/1 | base-locked → clean no-op |
| 9 | lead | 16 | power_endurance | 4/4/3/3/2 | path differs, result equals saturated cap |
| 10| lead | 16 | technique        | 4/4/3/3/2 | clean no-op + saturated cap |

### Boulder, no weakness (rows 11–16)

| # | discipline | total | weakest axis | expected |
|---|---|---|---|---|
| 11 | boulder | 8  | none | 2/2/1/2/1 |
| 12 | boulder | 10 | none | 2/4/1/2/1 |
| 13 | boulder | 12 | none | 2/5/1/3/1 |
| 14 | boulder | 13 | none | 2/5/2/3/1 |
| 15 | boulder | 14 | none | 3/5/2/3/1 |
| 16 | boulder | 16 | none | 4/5/3/3/1 |

### Boulder, with weakness — covers F4 fix (rows 17–19)

| # | discipline | total | weakest axis | expected | path note |
|---|---|---|---|---|---|
| 17 | boulder | 12 | finger_strength | 2/5/1/3/1 | F4 fix — old code returned 2/6/1/2/1 |
| 18 | boulder | 10 | endurance       | 3/3/1/2/1 | weakness fires |
| 19 | boulder | 16 | power_endurance | 4/5/3/3/1 | result equals saturated path |

### Error cases (rows 20–21)

| # | discipline | total | expected |
|---|---|---|---|
| 20 | lead | 10 | ValueError (< _MIN_TOTAL_WEEKS_LEAD=11) |
| 21 | lead | 17 | ValueError (> _MAX_TOTAL_WEEKS=16) |

### Incremental-regen scenarios (additional, rows 22–24 — bonus)

| # | discipline | total | phases | weakest | expected |
|---|---|---|---|---|---|
| 22 | lead | 5 | ["performance", "deload"] | none | perf=3, deload=2 → {perf:3, deload:2} |
| 23 | lead | 4 | ["performance", "deload"] | none | perf=2, deload=2 → {perf:2, deload:2} (surplus 1 → perf+1 stops at cap... wait: defaults 2+1=3, surplus 1, perf cap 3 → perf=3, deload=1; **revise to 3/1**) |
| 24 | boulder | 6 | ["power_endurance", "performance", "deload"] | none | defaults 1+2+1=4, surplus 2, perf+1=3, pe+1=2, deload last → {pe:2, perf:3, deload:1} |

(Row 23 corrected inline — the table builder above had a slip; the algorithm
yields perf=3, deload=1 for total=4 over [perf,deload] in lead. Phase 3 will
re-derive from the algorithm, not from this table.)

### Backward-compatibility scenarios

- `total=12, no weakness, lead → 4/3/2/2/1` is the existing default and must
  still pass any test that asserts this exact shape.
- `total=10, no weakness, boulder → 2/4/1/2/1` likewise.

These two scenarios are the safety net: if either changes, we've broken
something the existing test suite probably depends on.

---

## Open questions (Daniele to decide before Phase 2)

1. **Boulder deload at total=16: 1 or 2?** Current algorithm yields `4/5/3/3/1`
   (sum 16). To produce `4/5/3/3/2` (sum 17) we'd either need to drop sp cap to
   4 or accept that boulder cap sum is 16 (matches lead). Recommendation: leave
   as `4/5/3/3/1`. boulder cycles often follow another boulder cycle (outdoor
   season) so a longer deload is less critical. Confirm.

2. **Lead weakness shifts targeting `base` are clean no-ops.** With `base`
   locked at 4, four of the five `_WEAKNESS_ADJUSTMENTS` entries are inert for
   lead (only `power_endurance` fires). Options:
   - **(a) Accept** — base lock is the intent; inert weakness shifts are an
     acceptable side effect.
   - **(b) Re-table** weakness adjustments per discipline so lead's
     finger/pulling/technique map to phases that have slack (e.g.
     finger_strength → extend sp, shrink pe).
   - Recommendation: **(a)** for v1 of this brief — reshaping the table is a
     separate decision touching the closed-loop story. Add a "consider in v2"
     note in the design doc but don't block this brief.

3. **Should `discipline="both"` / `"all_round"` get its own duration table?**
   Currently aliased to lead. The merged session pool for all_round has more
   sp+boulder content; arguably it would benefit from boulder's `sp_cap=5`. Out
   of scope per brief. Confirm we keep alias.

4. **Postcondition asserts in production code.** The algorithm ends with two
   `assert` statements. Asserts are stripped under `python -O` but climb-agent
   doesn't run with `-O` (verified — none of the deploy configs set it). Worth
   keeping for safety. Confirm.

5. **F2 — dead-code removal placement.** `should_extend_phase` and
   `should_trigger_adaptive_deload` are both removed in Phase 2 per brief. They
   are referenced by tests in `test_macrocycle_v1.py:18-19` and `:228-238`.
   Phase 2 / Phase 3 will delete those test rows. Confirm Daniele wants them
   gone (vs wired up in a separate brief). Brief locks this decision but worth
   re-asking — if anyone planned to wire them in soon, deletion blocks that.

6. **Migration / messaging for in-flight users with `total > 16`.** Brief
   locks "leave as-is". The design implies that `start-new-cycle` will refuse
   `total > 16` after merge. Existing macrocycles with `total > 16` (if any
   beta users have them) continue to run via the cached macrocycle in state —
   they just can't be regenerated to >16w. Confirm this is intended.

7. **`_MIN_TOTAL_WEEKS_LEAD = 11` UX implication.** Existing onboarding slider
   default min was 8. Users who picked 9 or 10 in the old flow will see their
   plans stay intact (engine doesn't re-validate cached macrocycles), but if
   they regenerate, the slider min is now 11. Communicate via release notes?
   Not strictly a Phase 1 concern.

---

## Summary

- **Algorithm**: defaults → weakness shift (clamped) → surplus distribution
  (priority order, fill to caps) OR shortfall reduction (inverse priority,
  reduce to floors). Single function with optional `phases` scope; replaces
  both current duration helpers.
- **Lead**: caps `4/4/3/3/2` (sum 16), floors `4/2/2/2/1` (sum 11). Base locked
  at 4 in all paths. Default 12 → `4/3/2/2/1`. Range 11–16.
- **Boulder**: caps `4/5/3/3/2` (sum 17), floors `2/2/1/2/1` (sum 8). Default
  10 → `2/4/1/2/1`. Range 8–16. At total=16 → `4/5/3/3/1`.
- **F4 fix**: boulder finger_strength weakness at total=12 now returns
  `2/5/1/3/1` (clean), not `2/6/1/2/1` (old buggy path through flex absorber).
  Demonstrated numerically in §3.
- **F1 fix**: `total < _MIN_TOTAL_WEEKS_*` raises ValueError; routers clamp
  before the call. Off-by-one is structurally unreachable.
- **Consolidation**: `_compute_remaining_durations` is removed; the unified
  function takes `phases=...`.
- **F2 dead-code**: `should_extend_phase`, `should_trigger_adaptive_deload`
  removed (test rows deleted in Phase 3).
- **21 test scenarios** specified for Phase 3 (target ≥18).
- **7 open questions** for Daniele to sign off below.

**STOP. Awaiting OK before Phase 2 (engine implementation).**

After OK:
- Phase 2: implement `_compute_phase_durations` per §1; remove
  `_compute_remaining_durations`, `should_extend_phase`,
  `should_trigger_adaptive_deload`; add constants; update routers.
- Phase 3: write tests per §7, run full suite.
- Phase 4: frontend slider cap + Settings goal-editor swap.
- Phase 5: docs (CLAUDE.md, design doc, roadmap, vocabulary).
- Phase 6: commit, push, Vercel preview, merge.

---

*End of A218 Phase 1 design. Branch: `feat/macrocycle-caps`.*
