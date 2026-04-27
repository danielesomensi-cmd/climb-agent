# B227 — Phase 0 Findings

**Date:** 2026-04-27
**Brief:** B227 — Resolver `intensity_max` enforcement (3-tier cascade, hard filter)
**Status:** Phase 0 read-only. **STOP gate — awaiting Daniele OK before Phase 1.**
**Author:** Claude (Opus 4.7)

---

## Executive summary

Audit finding F1 **fully confirmed** with concrete reproduction.

- **9 sessions × 22 inline blocks** declare `intensity_max` in `selection.primary.filters`.
- **Resolver silently ignores it** (`resolve_session.py:952` — only reads `role/domain/pattern/equipment`).
- **Active bug, not latent**: 3 violations reproduced across 28 declared-intensity-block resolutions in a 9-session × 4-equipment-profile matrix.
- **Worst case observed**: `finger_maintenance_gym/easy_climbing_post_finger` (declared `intensity_max=low`) selects `dip` (intensity=high) at home, and `archer_pullup` (high) at home with full equipment.
- **Catalog parity drift confirmed**: `regeneration_easy` `_SESSION_META.required_equipment=[]` vs JSON `["gym_boulder"]`. Already warned by `_validate_session_meta_equipment()` (D172-17) but not enforced.
- **Past-sessions invariant**: protected by `B120 + B153b` guards in `week.py:51-60`. Re-resolution skipped for `done/skipped` sessions with cached `resolved`. **Safe to land B227 fix without violating immutability.**
- **Test baseline**: 1832 passed; 24 test files touch resolver, 8 reference regen/intensity. No existing test asserts intensity_max enforcement.

---

## P0.1 — Catalog inventory: 9 sessions × meta vs JSON parity

| session_id | meta.intensity | meta.req_eq | json.req_eq | mismatch | inline blocks with intensity_max |
|---|---|---|---|---|---|
| `regeneration_easy` | low | `[]` | `["gym_boulder"]` | **MISMATCH** | continuity_main(low), light_stretch(low) |
| `yoga_recovery` | low | `[]` | `[]` | ok | stretch_flow(low) |
| `flexibility_full` | low | `[]` | `[]` | ok | 6 blocks (all low) |
| `prehab_maintenance` | low | `[]` | `[]` | ok | 4 blocks (all low) |
| `complementary_conditioning` | medium | `[]` | `[]` | ok | conditioning_main(medium), conditioning_secondary(medium) |
| `handstand_practice` | medium | `[]` | `[]` | ok | wrist_warmup(low), shoulder_prehab(low) |
| `finger_maintenance_gym` | medium | `["hangboard"]` | `["hangboard"]` | ok | easy_climbing_post_finger(low), finger_extensor_prehab(low) |
| `finger_maintenance_home` | medium | `["hangboard"]` | `["hangboard"]` | ok | finger_warmup(low), finger_extensor_prehab(low) |
| `finger_strength_home` | high | `["hangboard"]` | `["hangboard"]` | ok | finger_warmup(low), finger_extensor_prehab(low) |

**Summary:** 22 declared inline blocks (20 low + 2 medium). 1 parity mismatch (`regeneration_easy`).

**Note:** The session-level `meta.intensity` is not the same field as block-level `intensity_max`. Several sessions declare a high/medium session-level intensity but mandate `intensity_max=low` for warmup/cooldown blocks. This per-block granularity is correct and must be preserved by B227.

---

## P0.2 — Exercise inventory: intensity distribution

> **CORRECTION 2026-04-27 (R3 follow-up)**: initial distribution count was incomplete. The catalog uses a **7-value enum**, not 3. Real distribution below.

**Catalog: 218 exercises. Zero missing `intensity_level`** — but enum is wider than `{low, medium, high}` and has 2 drift singletons.

### Full intensity_level distribution

| Level | Count | Notes |
|---|---|---|
| `very_low` | 5 | Legitimate — `regeneration_climbing`, `finger_extensor_band`, `finger_tendon_glides`, `warmup_repeaters_large`, `timed_route_preview` |
| `low` | 89 | Standard |
| `moderate` | **1** | **DRIFT singleton** — `reverse_lunge` (semantically `medium`) |
| `medium` | 55 | Standard |
| `high` | 48 | Standard |
| `very_high` | **1** | **DRIFT singleton** — `thirty_thirty_intervals` (semantically `high`) |
| `max` | 19 | Limit-strength: `max_hang_*`, `min_edge_hang`, `limit_bouldering`, `campus_double_dyno`, etc. **Above `high`** |
| `<missing>` | 0 | Clean dataset — no missing values |

**Implication for ordinal mapping**: B227 must order all 7 values. Proposed:

```python
_INTENSITY_ORDER = {
    "very_low": 0, "low": 1,
    "moderate": 2, "medium": 2,    # equate
    "high": 3, "very_high": 3,     # equate
    "max": 4,                      # above high
}
```

**Effect on enforcement**:
- `intensity_max=low` declared in JSON → pass `{very_low, low}`. Block 6 levels including 19 `max` exercises (correct: a recovery never sees `max_hang_5s`).
- `intensity_max=medium` → pass `{very_low, low, moderate, medium}`. Block `{high, very_high, max}`.
- Blocks without `intensity_max` (param defaults to `None`) → unchanged behavior.

**Drift singleton normalization** (`moderate→medium`, `very_high→high`) → out of scope for B227, separate C-brief. Ordinal mapping above absorbs them safely.

**Original (incomplete) summary kept below for context — replaced by table above.**

~~Global distribution: low=89, medium=55, high=48 (22 in test/conditioning roles excluded).~~

**Per-role × intensity (`role=main` is the relevant tier-2/3 cascade pool):**

| role | total | low | medium | high |
|---|---|---|---|---|
| main | 77 | **11** | **12** | **37** |
| accessory | 71 | 23 | 38 | 9 |
| prehab | 18 | 15 | 1 | 0 |
| warmup | 18 | 17 | 0 | 0 |
| cooldown | 15 | 14 | 0 | 0 |
| technique | 21 | 18 | 2 | 0 |
| activation | 4 | 3 | 0 | 1 |

**Critical:** 37/77 = **48% of `role=main` exercises are high-intensity**. The current non-zeroing fallback exposes this entire pool to recovery sessions.

**Per-domain × intensity (recovery-relevant):**

| domain | total | low | medium | high |
|---|---|---|---|---|
| regeneration | 5 | 4 | 0 | 0 |
| flexibility | 19 | 19 | 0 | 0 |
| mobility | 14 | 14 | 0 | 0 |
| prehab_* | 16 | 16 | 0 | 0 |
| aerobic_capacity | 10 | 10 | 0 | 0 |
| prehab_finger | 2 | 0 | 0 | 0 (both `very_low`, see correction above) |

**Tier 1 pool (Tier 1 = domain match + intensity ceiling)** — for `regeneration_easy.continuity_main` (`domain=regeneration, role=main, intensity_max=low`):
- 3 candidates: `continuity_climbing`, `easy_route_laps`, `arc_training_progressive` (all wall-required → empty at home).

**Tier 2 pool (drop domain, keep `intensity_max=low`)** — `role=main + intensity=low`:
- 11 candidates, all climbing/aerobic-capacity. **None work without a wall** (home + no wall → still empty).

**Tier 3 pool (drop domain, allow medium)** — `role=main + intensity ∈ {low,medium}`:
- 23 candidates. Includes `complementary_conditioning` and other non-climbing low/medium options.

**Skip risk**: at home + no wall, all 3 tiers may legitimately be empty for `regeneration_easy.continuity_main`. **Skip is the correct outcome** in that scenario — methodology says home recovery should map to `yoga_recovery`, not `regeneration_easy`.

---

## P0.3 — Resolver code path verification

### `pick_best_exercise_p0` (line 338)

Current signature reads `role_req, domain_req, pattern_req, required_equipment`. **No `intensity_max` parameter.**

**Stage ordering inside the function:**
- Stage 0: start
- Stage 1: location_allowed (line 380)
- Stage 2: equipment hard constraints (line 384)
- Stage 2b: block-level equipment preference (soft) (line 396)
- Stage 2c: finger device preference (soft) (line 408)
- Stage 2d-2f: age/experience gates (line 429)
- Stage 3: role (HARD, ANY-match) (line 456)
- Stage 3b: exclude already-used (soft, line 469)
- **Stage 4: domain (NON-ZEROING ANY-match)** (line 479-491) ← root cause of pool widening
- Stage 5: pattern (NON-ZEROING ANY-match) (line 497)
- Stage 6: limitation filtering (line 512)
- Tie-break + score (line 530)

**Insertion point for `intensity_max`:** between Stage 3 (role) and Stage 4 (domain). Rationale:
- Must be **HARD** (zeroing) per the brief: "NEVER `high` in a session declaring `intensity_max=low`".
- Apply **before domain non-zeroing fallback** so it survives the domain-widen step. If applied after Stage 4, the domain fallback would already have widened the pool.
- The 3-tier cascade is implemented as wrapper logic on top of `pick_best_exercise_p0`, calling it 1-3 times with progressively widened intensity ceilings.

### Callers

Only **2 call sites**, both in `resolve_session.py`:

| Caller | Line | Reads `intensity_max`? | Notes |
|---|---|---|---|
| `_resolve_inline_block` | 989 | ❌ No | The fix scope — reads `filters.get("intensity_max")` is missing. |
| Template-block resolver | 1456 | ❌ No | No template currently declares `intensity_max` (`grep` empty). Backward-compat: pass `None` from this caller. |

**Recommendation**: add `intensity_max` parameter with `default=None` (no filter). Update only the inline caller to pass it from `filters.get("intensity_max")`. Template caller unchanged.

### Past-sessions invariant

`week.py:51-60` (B120 + B153b):

```python
if (
    session_entry.get("status") in ("done", "skipped")
    and session_entry.get("resolved")
) or (
    session_entry.get("_user_edited")
    and session_entry.get("resolved")
):
    continue
```

**Verified**: completed/skipped sessions with cached `resolved` payload are NEVER re-resolved. User-edited sessions also protected. **B227 fix does not affect past sessions** — only future/today resolutions.

**Edge case**: a `done/skipped` session that somehow has no `resolved` payload (cache miss / corrupted state) WOULD be re-resolved with the new behavior. This is a pre-existing edge case, not introduced by B227. Leave as-is, document in tests.

---

## P0.4 — Reproduction

### Setup

9 declaring sessions × 4 equipment profiles (`home_none`, `home_pullup`, `home_full`, `gym_full`) × current resolver.

### Result: **3 violations / 28 declared-intensity-block resolutions**

| Session | Block | Profile | Selected exercise | declared_max | actual | role | domain |
|---|---|---|---|---|---|---|---|
| `finger_maintenance_gym` | `easy_climbing_post_finger` | home_none | `dip` | low | **high** | main | strength_general |
| `finger_maintenance_gym` | `easy_climbing_post_finger` | home_pullup | `dip` | low | **high** | main | strength_general |
| `finger_maintenance_gym` | `easy_climbing_post_finger` | home_full | `archer_pullup` | low | **high** | main | strength_general |

**Mechanism (verified)**:
1. Block declares `domain=regeneration` (or aerobic_capacity), `role=main`, `intensity_max=low`.
2. At home, climbing exercises filtered out at Stage 1 (location).
3. Stage 4 domain fallback (line 479-491): `base4=[]` → keep all `role=main` candidates.
4. **`intensity_max` never applied** → high-intensity exercises eligible.
5. Scoring picks `dip` / `archer_pullup` deterministically.

**Audit was directionally correct** (path is open) but cited the wrong session: real exposure is `finger_maintenance_gym`, not `regeneration_easy`. `regeneration_easy.continuity_main` happens to skip cleanly at home because all `role=main + domain=regeneration + intensity=low` exercises are wall-required (Tier 1 + Tier 2 + Tier 3 all empty without a wall). `finger_maintenance_gym` fails because its `easy_climbing_post_finger` block has wall-implying domain but the cascade does not stop the high-intensity strength exercises from leaking in.

**No violations under `gym_full` profile** — Tier 1 succeeds for all sessions. Bug primarily affects home/equipment-limited setups.

**Classification**: **active bug**, user-facing. A recovery-day session resolved at home today selects a high-intensity strength exercise. Methodology violation (Hörst, Lattice both explicit on hard ceilings during recovery).

---

## P0.5 — Test surface inventory

**Total baseline: 1832 tests across 104 files.** All pass on `main` (verified locally).

**Files touching resolver (24):** key regression files —
- `test_resolver_p0.py`
- `test_resolver_enhancements.py`
- `test_resolve_real_sessions.py`
- `test_session_enrichment.py`
- `test_warmup_b93.py`
- `test_b157_pe_equipment_gate.py`
- `test_addon_sessions.py`
- `test_hangboard_gates.py`
- `test_loading_pin.py`
- `test_age_gates.py`
- `test_baseline_session_under_test.py`
- `test_d154_sp_climbing_fix.py`
- `test_manual_override_mvp.py`
- `test_a193_hangboard_implies_pullup_bar.py`
- `test_p1_75_closing.py`
- `test_b173_silent_fallback_warnings.py`

**Sub-suite verified clean**: `test_resolver_p0 + test_resolver_enhancements + test_resolve_real_sessions + test_session_enrichment + test_warmup_b93` → 75 pass.

**Files touching regen/intensity_max/intensity_level (8):**
- `test_session_enrichment.py`
- `test_adaptive_replan.py`
- `test_quick_add.py`
- `test_b165b_recovery_multiplier.py`
- `test_replanning_v1.py`
- `test_p1_75_closing.py`
- `test_exercises_v2.py` — only validates intensity_level enum canonicality
- `test_api.py`

**No existing test asserts `intensity_max` enforcement.** Net-new test surface in B227.

**Risk areas**:
- `test_replanning_v1.py` — replanner intent → session resolution. If B227 changes `regeneration_easy` resolution at home, this could cascade.
- `test_b165b_recovery_multiplier.py` — closed-loop recovery. Likely indirect, low risk.
- `test_resolve_real_sessions.py` — runs all sessions through resolver. **High likelihood of breakage** if `finger_maintenance_gym` resolution changes. Will need fixture audit during Phase 1.

---

## Risks & open questions for Daniele — RESOLVED

### R1. Catalog parity fix scope — DECIDED: meta → JSON

> **2026-04-27**: Daniele chose **opzione B**: add `gym_boulder` to `_SESSION_META["regeneration_easy"].required_equipment`. Do NOT remove from JSON.
>
> **Rationale**: removing from JSON would let the planner schedule regen at home → resolver finds empty pool at all 3 tiers → session skipped entirely. Worse UX than the original bug (user sees regen with zero exercises). Adding to meta is the correct fix until the catalog has home-compatible regen exercises. Catalog expansion → C-brief post-B227.
>
> **Principle**: meta is canonical, JSON aligns to meta. When meta is incomplete, fix meta.

### R2. Test breakage acceptance — DECIDED: 3-tier policy

> **2026-04-27**: Daniele's policy:
>
> - **Auto-fix without asking** if test is obviously stale (obsolete fixture, mock signature drift, import path).
> - **Batch-report at end of Phase 1** if test reveals legitimate behavior change ("regen now picks X instead of Y"). List in chat, Daniele decides.
> - **Immediate STOP** if test reveals invariant violation (past sessions modified, determinism broken, idempotency lost). Don't wait for end of Phase 1.
>
> Final report: list fixed tests with one-line changelog + list pending-decision tests.

### R3. `prehab_finger` exercises with no intensity_level

> **RESOLVED 2026-04-27**: original finding was incorrect. `finger_extensor_band` and `finger_tendon_glides` already declare `intensity_level="very_low"` (verified by direct catalog read). The P0.2 count "0 unrated" was an artifact of treating all non-`{low,medium,high}` values as missing.
>
> **No backfill needed.** Catalog is internally consistent.
>
> **Side discovery**: 2 drift singletons (`reverse_lunge`=`moderate`, `thirty_thirty_intervals`=`very_high`) and 19 `max`-level exercises. Ordinal mapping in P0.2 absorbs all of them. Singleton normalization → separate C-brief, post-B227.

### R4. Telemetry / observability — DECIDED: WARNING/INFO + structured

> **2026-04-27**: Daniele confirmed:
> - WARNING for `cascade_skip`
> - INFO for `cascade_tier=2|3`
> - **Structured logging** (no free text), via `extra={}`:
>
> ```python
> logger.info(
>     "resolver.cascade",
>     extra={
>         "session_id": session_id,
>         "block_id": block_id,
>         "cascade_tier": tier,        # 1 | 2 | 3 | "skip"
>         "intensity_max": intensity_max,
>         "pool_size": len(pool),
>     }
> )
> ```
>
> Rationale: if `cascade_tier=3` spikes in production, we know exactly where to expand the catalog.

---

## Proposed Phase 1 implementation plan (for review)

### Step 1 — Refactor inline caller (`_resolve_inline_block`)

Wrap the current single `pick_best_exercise_p0` call (line 989) with the 3-tier cascade. Pseudo-code:

```python
intensity_max_req = filters.get("intensity_max")  # NEW: read from JSON

def try_pick(intensity_max, drop_domain=False, drop_pattern=False):
    return pick_best_exercise_p0(
        ...,
        domain_req=None if drop_domain else domain_req,
        pattern_req=None if drop_pattern else pattern_req,
        intensity_max=intensity_max,
    )

if intensity_max_req == "low":
    selected, trace = try_pick("low")
    if not selected:
        selected, trace = try_pick("low", drop_domain=True, drop_pattern=True)
        if selected: trace["cascade_tier"] = 2
    if not selected:
        selected, trace = try_pick("medium", drop_domain=True, drop_pattern=True)
        if selected: trace["cascade_tier"] = 3
elif intensity_max_req == "medium":
    selected, trace = try_pick("medium")
    if not selected:
        selected, trace = try_pick("medium", drop_domain=True, drop_pattern=True)
        if selected: trace["cascade_tier"] = 2
    # No tier 3 for medium — already at ceiling
else:
    # No intensity_max declared — current behavior unchanged
    selected, trace = try_pick(None)
```

If `selected is None`, log `cascade_skip=True` with session_id + block_id and return None.

### Step 2 — Add `intensity_max` parameter to `pick_best_exercise_p0`

Default `None` (no filter). When set: insert filter between Stage 3 (role) and Stage 4 (domain). Filter logic uses the **7-value ordinal mapping** discovered in P0.2 correction:

```python
_INTENSITY_ORDER = {
    "very_low": 0, "low": 1,
    "moderate": 2, "medium": 2,    # equate (drift singleton absorbed)
    "high": 3, "very_high": 3,     # equate (drift singleton absorbed)
    "max": 4,                      # above high
}

if intensity_max is not None:
    ceiling = _INTENSITY_ORDER.get(intensity_max)
    if ceiling is None:
        # Unknown intensity_max value in JSON — log warning, treat as no filter
        logger.warning("Unknown intensity_max value %r — skipping filter", intensity_max)
    else:
        # R3 policy: missing intensity_level → exclude (more strict)
        base3 = [
            e for e in base3
            if e.get("intensity_level") in _INTENSITY_ORDER
            and _INTENSITY_ORDER[e["intensity_level"]] <= ceiling
        ]
        if not base3:
            return None, trace  # zeroing
```

**R3 missing-policy**: exercises with no `intensity_level` are **excluded** from any pool with `intensity_max` set. Today this affects 0 exercises (clean dataset), but acts as defense-in-depth for future catalog additions.

### Step 3 — Catalog parity fix (R1 = meta → JSON)

Add `"required_equipment": ["gym_boulder"]` to `_SESSION_META["regeneration_easy"]` in `backend/engine/planner_v2.py:51`.

Do NOT modify `backend/catalog/sessions/v1/regeneration_easy.json` (`required_equipment: ["gym_boulder"]` stays as-is — it was already correct).

### Step 4 — Tests

Per brief P1.3 (8 tests, file `test_resolve_session_intensity_max.py`).

**Add 2 extra fixtures** beyond brief:
- `test_finger_maintenance_gym_at_home_no_dip` — exact repro from P0.4. Asserts no high-intensity exercise selected.
- `test_intensity_max_zero_pool_returns_none` — when ceiling kills all candidates, returns None (skip), not falls back to higher intensity.

### Step 5 — Verify suite

Target: 1832 → ≥1840 (8 new). Any breakage in existing tests reported individually.

---

## Phase 0 closure — APPROVED

> **2026-04-27**: Daniele approved Phase 1 with the decisions captured above (R1=meta→JSON, R2=3-tier policy, R3=no backfill needed, R4=structured logging WARNING/INFO).
>
> Phase 1 in progress. No code changes yet — pending second STOP gate on R3 follow-up (see chat).

All 4 risks resolved:

| | Decision |
|---|---|
| **R1** | meta → JSON. Add `gym_boulder` to `_SESSION_META["regeneration_easy"].required_equipment`. |
| **R2** | 3-tier breakage policy: auto-fix stale, batch-report behavioral changes, STOP on invariant violation. |
| **R3** | No backfill — prehab_finger already `very_low`. 7-value ordinal mapping handles drift singletons. |
| **R4** | Structured logging via `extra={}`. WARNING on skip, INFO on tier 2/3. |
