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

**Catalog: 218 exercises. Zero missing `intensity_level`** — clean dataset, no need to decide on default treatment for missing fields.

**Global distribution:** low=89, medium=55, high=48 (22 in test/conditioning roles excluded).

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
| prehab_finger | 2 | 0 | 0 | 0 (both unrated) |

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

## Risks & open questions for Daniele

### R1. Catalog parity fix scope

**Found**: `regeneration_easy` meta `[]` vs json `["gym_boulder"]`. Brief P1.2 says fix the JSON to match meta (meta canonical). But **meta is what the planner uses to decide eligibility** — meta says "this session is allowed at home/gym/outdoor with no equipment", while JSON `required_equipment=["gym_boulder"]` would gate it to gym only.

**The mismatch is what allowed the bug to fire**: planner schedules `regeneration_easy` at home (per meta), then resolver runs at home with no climbing, falls back. **If we sync JSON → meta**, the home scheduling stays open (and the cascade fix protects intensity). **If we sync meta → JSON**, the planner stops scheduling regen at home (B227 cascade still useful as defense-in-depth).

**Question**: which way to sync? My recommendation: **JSON → meta** (drop `gym_boulder` from the JSON), trusting the cascade as defense-in-depth — because the methodology arguably allows passive stretching at home as "regeneration" too. But this is a product call.

### R2. Test breakage acceptance

`test_resolve_real_sessions.py` exercises all 35 sessions. If any current assertion captures the buggy resolution (e.g., expects `dip` to appear in a recovery session), it will break. Brief says: "Do not silently update fixtures: a breaking test is signal that the cascade changed an existing resolution. Daniele must validate."

**Question**: do you want me to surface every breakage as a separate decision point during Phase 1, or batch-report at the end?

### R3. `prehab_finger` exercises with no intensity_level

Found: 2 prehab_finger exercises lack `intensity_level`. These are not in the cascade pool (role=prehab, not main), so not directly impacted. But it's a small data-quality gap.

**Question**: in scope for B227 (set them to `low`), or separate C-brief?

### R4. Telemetry / observability

Brief P1.1.5 specifies `cascade_tier=2|3` and `cascade_skip=True` logging. Should this be at WARNING level (visible in Railway logs) or INFO (verbose only)? In production with `sk_live`, WARNING gives us a signal if a recovery session can't resolve cleanly.

**My recommendation**: WARNING for cascade_skip, INFO for tier=2/3. Confirm.

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

Default `None` (no filter). When set: insert filter between Stage 3 (role) and Stage 4 (domain). Filter logic:
```python
if intensity_max is not None:
    order = {"low": 0, "medium": 1, "high": 2}
    ceiling = order.get(intensity_max, 2)
    base3 = [e for e in base3 if order.get(e.get("intensity_level") or "medium", 1) <= ceiling]
    if not base3:
        return None, trace  # zeroing
```

Note: missing `intensity_level` defaults to `medium` (most charitable read; no exercise in catalog actually has missing). Flagged in P0.2.

### Step 3 — Catalog parity fix (per R1 decision)

If JSON → meta: drop `"required_equipment": ["gym_boulder"]` from `regeneration_easy.json`.
If meta → JSON: add `"required_equipment": ["gym_boulder"]` to `_SESSION_META["regeneration_easy"]`.

### Step 4 — Tests

Per brief P1.3 (8 tests, file `test_resolve_session_intensity_max.py`).

**Add 2 extra fixtures** beyond brief:
- `test_finger_maintenance_gym_at_home_no_dip` — exact repro from P0.4. Asserts no high-intensity exercise selected.
- `test_intensity_max_zero_pool_returns_none` — when ceiling kills all candidates, returns None (skip), not falls back to higher intensity.

### Step 5 — Verify suite

Target: 1832 → ≥1840 (8 new). Any breakage in existing tests reported individually.

---

## STOP — awaiting approval

Phase 0 deliverable complete. **No code changes.** Ready for Phase 1 on Daniele's OK.

Specific questions to resolve before Phase 1:
1. **R1**: catalog parity direction — JSON → meta (drop gym_boulder) or meta → JSON (add gym_boulder)?
2. **R2**: how to handle test breakages during Phase 1 (per-decision or batched)?
3. **R3**: include prehab_finger intensity backfill in B227 or defer?
4. **R4**: log levels — confirm WARNING for skip, INFO for tier 2/3?

When you OK, I'll proceed with Phase 1 in the order listed above.
