# D223 — Full Resolver Impact: Reclassifying 23 Accessory Exercises to Multi-Role

**Date:** 2026-04-23  
**Scope:** Read-only investigation. Assess impact on `backend/engine/resolve_session.py` full resolver (P0 hard-filter stage) if 23 exercises are reclassified from `role: ["accessory"]` to `role: ["main", "accessory"]` (multi-role).

**Methodology:** 
1. Analyzed `resolve_session.py:454–461` role-filtering logic (ANY-match on exercise role array)
2. Enumerated all 12 `role: ["main"]` blocks across 8 template files
3. Categorized blocks by filter type: explicit exercise_id (3 blocks) vs. P0 hard filter (8 blocks, affected by role change)
4. Matched 23 candidates against P0 filters (domain + pattern constraints)
5. Assessed current main-role pool size for affected blocks

---

## Executive Summary

**Impact on full resolver:** **MINIMAL AND LOCALIZED**

- **22 of 23 candidates:** Zero impact. Their domain/pattern profiles do NOT match any `role: ["main"]` block filter.
- **1 candidate (chinup):** Would gain entry to 3 pulling blocks (`pulling_strength_compound` main variants) — a **BENEFICIAL** change, not harmful.
- **Risk level:** **LOW**. No climbing-specific blocks are affected. No thin or degraded pools result.
- **Recommendation:** **Safe to proceed.** Reclassification is non-disruptive and slightly improves resolver pool diversity for general-strength pulling blocks.

---

## Step 1: Role-Filtering Mechanism in Resolve Session

### Key Code: `apply_P0_hard_filter()` (lines 454–461)

```python
# Stage 3: role (ANY match)
base3 = base2
if role_set:
    base3 = []
    for e in base2:
        if not set(ex_roles(e)).isdisjoint(role_set):  # <-- ANY overlap
            base3.append(e)
```

**Logic:** If block specifies `role: ["main"]`, the resolver keeps only exercises where **at least one role overlaps** with the block's role set.  
**Current behavior:** `"main" in exercise.role` → passes filter.  
**Post-reclassification:** `"main" in ["main", "accessory"]` → still passes filter. Multi-role exercises are NOT penalized.

**Applies to:** 8 blocks in templates that use P0 filter (no explicit `exercise_id`). Three templates have explicit exercise IDs and thus skip P0 filtering entirely:
- `pulling_strength_test/main` → `exercise_id: "weighted_pullup"` (bypasses P0)
- `finger_max_strength_test/main` → `exercise_id: "max_hang_7s"` (bypasses P0)
- `finger_max_strength_test_lp/main` → `exercise_id: "lp_max_test_5s"` (bypasses P0)
- `finger_strength_endurance_test_lp/main` → `exercise_id: "lp_repeater_test"` (bypasses P0)

---

## Step 2: Enumeration of Main-Role Blocks (P0 filter–using)

| File | Template ID | Block ID | Filters (domain + pattern) | Current Main Pool Size |
|---|---|---|---|---|
| pulling_strength_compound.json | pulling_strength_compound | weighted_pullup_main | domain=[strength_general], pattern=[pull_vertical] | 9 |
| pulling_strength_compound.json | pulling_strength_compound | lock_off_hold | domain=[strength_general], pattern=[pull_vertical] | 9 |
| pulling_strength_compound.json | pulling_strength_compound | typewriter_unilateral | domain=[strength_general], pattern=[pull_vertical] | 9 |
| finger_max_strength.json | finger_max_strength | main | domain=[finger_strength], pattern=[isometric_hang] | 17 |
| finger_strength_endurance.json | finger_strength_endurance | main | domain=[finger_strength_endurance], pattern=None | 6 |
| finger_aerobic_endurance.json | finger_aerobic_endurance | main | domain=[finger_aerobic_endurance], pattern=None | 5 |
| route_projecting_main.json | route_projecting_main | redpoint_attempts | domain=[climbing_routes], pattern=None | 2 |
| route_projecting_main.json | route_projecting_main | crux_work | domain=[climbing_routes, technique_lead], pattern=None | 3 |

**Current main pool sizes:** Ranging from 2–17 exercises per block. No scarcity detected.

---

## Step 3: Candidate Classification and Domain Analysis

All 23 candidates currently have `role: ["accessory"]` (one exception: `nordic_curl` has `role: ["accessory", "prehab"]`).

**Domain breakdown:**

| Domain Group | Count | Exercises |
|---|---|---|
| strength_general (only) | 15 | bench_press, dumbbell_bench_press, overhead_press, pushup, incline_pushup, pike_pushup, ring_pushup, chinup, romanian_deadlift, nordic_curl, pistol_squat_progression, goblet_squat, bulgarian_split_squat, step_ups, cossack_squat |
| core (only) | 7 | front_lever_straddle, front_lever_one_leg, toes_to_bar, knees_to_elbows, hanging_leg_raise, ab_wheel_rollout, windshield_wipers |
| handstand_skill + strength_general | 1 | handstand_pushup_wall |

---

## Step 4: Intersection Analysis — Would Reclassification Add Candidates to Any Main Block?

### Cross-Match Results

For each P0 filter block, candidates match if:
1. Block domain is empty (no domain filter), OR candidate domain overlaps block domain
2. Block pattern is None (no pattern filter), OR candidate pattern matches block pattern

**Matching table (only rows with > 0 candidates shown):**

#### pulling_strength_compound (all 3 variants: weighted_pullup_main, lock_off_hold, typewriter_unilateral)
- **Block filters:** domain=[strength_general], pattern=[pull_vertical]
- **Candidates that match:** 
  - **chinup** (domain=[strength_general], pattern=pull_vertical) → **HIT**
- **Impact:** Adds 1 exercise to a 9-item pool

#### finger_max_strength
- **Block filters:** domain=[finger_strength], pattern=[isometric_hang]
- **Candidates:** None match (none are finger_strength domain)

#### finger_strength_endurance
- **Block filters:** domain=[finger_strength_endurance], pattern=None
- **Candidates:** None match (none are finger_strength_endurance domain)

#### finger_aerobic_endurance
- **Block filters:** domain=[finger_aerobic_endurance], pattern=None
- **Candidates:** None match (none are finger_aerobic_endurance domain)

#### route_projecting_main (both variants: redpoint_attempts, crux_work)
- **Block filters:** domain=[climbing_routes] or [climbing_routes, technique_lead]
- **Candidates:** None match (none are climbing_routes or technique_lead domain)

### Summary
- **Total blocks examined:** 8
- **Blocks with candidate intersections:** 1 (pulling_strength_compound ×3 block variants)
- **Total candidate additions:** 1 unique exercise (chinup)
- **Zero-impact candidates:** 22 of 23

---

## Step 5: Impact Assessment for Chinup

### Current Context
- **chinup** current role: [accessory]
- **chinup** domain: [strength_general]
- **chinup** pattern: pull_vertical
- **Current usage:** Not explicitly pinned in any session template. Would only appear if resolver selected it via body_part_picker light resolver for accessory blocks.

### Post-Reclassification Context
- **chinup** new role: [main, accessory]
- **Would gain access to:** 3 blocks in `pulling_strength_compound` template
  - weighted_pullup_main (4 sets × 4 reps, heavy)
  - lock_off_hold (3 sets × 3 reps, controlled)
  - typewriter_unilateral (3 sets × 5 reps, optional)

### Current Pool for Pulling Strength (strength_general + pull_vertical + role=main)

| Exercise ID | Role | Pattern | Notes |
|---|---|---|---|
| archer_pullup | main | pull_vertical | Advanced pulling variation |
| eccentric_pullup | main, accessory | pull_vertical | Already multi-role |
| l_sit_pullup | main | pull_vertical | Combined strength + core |
| lock_off_isometric | main | pull_vertical | Isometric hold variant |
| one_arm_pullup_assisted | main | pull_vertical | Unilateral progression |
| power_pullups_explosive | main | pull_vertical | Explosive variant |
| pullup | main | pull_vertical | Bodyweight standard |
| typewriter_pullup | main | pull_vertical | Lateral movement variation |
| weighted_pullup | main | pull_vertical | Primary template exercise (pinned) |

**Pool size:** 9 current main exercises.  
**Proposed addition:** chinup (a fundamental pulling compound, distinct from the 9).  
**New pool size:** 10.

### Risk Assessment: Harmfulness vs. Benefit

**Harmful?** No.
- Chinup is a legitimate strength-general pulling compound
- It's different from weighted_pullup (its likely competitor in selection)
- The pulling_strength_compound template is NOT a climbing-specific block (it's general strength)
- Pool has no scarcity (9 → 10 is healthy expansion)
- No climbing-specific pulling blocks (e.g., finger strength, climbing routes) are affected

**Beneficial?** Yes.
- Adds a **bodyweight-only** option to the pulling block (chinup has no equipment_required)
- All current main pulling exercises require pullup_bar or weight
- Users with only a pullup_bar (no rings, bands, weights) would have an additional choice
- Increases resolver optionality without degrading block specificity

**Neutral (zero net effect)?** 22 other candidates.
- None match any main-block filter, so they remain completely unaffected

---

## Step 6: Edge Cases and Tie-Breaker Considerations

### Could Multi-Role Affect Scoring or Tie-Breaking?

Checked `resolve_session.py:875–920` scoring logic. Multi-role status does **NOT** enter any scoring calculation:
- Scoring is based on: recency, equipment match, pattern specificity, grip preference, age gate, experience gate
- Role is a **hard filter only** (Stage 3), not a soft preference or scoring bonus

**Conclusion:** Adding "main" to an exercise role does not shift scoring; it only makes the exercise eligible for candidate pools it currently cannot enter.

### Weighting and Depth of the Resolver

The P0 hard filter is the **only** role check in `resolve_session.py`. No secondary role-based weighting occurs post-selection. Thus:
- Reclassification → inclusion in candidate pool
- Inclusion → subject to normal tie-break rules (exercise_id lexicographic order if score-tied)

### Session Template Usage

Verified: No session template (`.json` in `backend/catalog/sessions/v1/`) explicitly references the 23 candidates. All candidate selections would come from P0 filter or body_part_picker.

---

## Summary Triage Table

| Candidate | Current Role | Domain | Would Match P0 Block? | Block Name | Impact Classification |
|---|---|---|---|---|---|
| bench_press | accessory | strength_general | No | — | Neutral |
| dumbbell_bench_press | accessory | strength_general | No | — | Neutral |
| overhead_press | accessory | strength_general | No | — | Neutral |
| pushup | accessory | strength_general | No | — | Neutral |
| incline_pushup | accessory | strength_general | No | — | Neutral |
| pike_pushup | accessory | strength_general | No | — | Neutral |
| ring_pushup | accessory | strength_general | No | — | Neutral |
| handstand_pushup_wall | accessory | strength_general + handstand_skill | No | — | Neutral |
| **chinup** | **accessory** | **strength_general** | **Yes** | **pulling_strength_compound ×3** | **Beneficial** |
| front_lever_straddle | accessory | core | No | — | Neutral |
| front_lever_one_leg | accessory | core | No | — | Neutral |
| toes_to_bar | accessory | core | No | — | Neutral |
| knees_to_elbows | accessory | core | No | — | Neutral |
| hanging_leg_raise | accessory | core | No | — | Neutral |
| ab_wheel_rollout | accessory | core | No | — | Neutral |
| windshield_wipers | accessory | core | No | — | Neutral |
| romanian_deadlift | accessory | strength_general | No | — | Neutral |
| nordic_curl | accessory + prehab | strength_general | No | — | Neutral |
| pistol_squat_progression | accessory | strength_general | No | — | Neutral |
| goblet_squat | accessory | strength_general | No | — | Neutral |
| bulgarian_split_squat | accessory | strength_general | No | — | Neutral |
| step_ups | accessory | strength_general | No | — | Neutral |
| cossack_squat | accessory | strength_general | No | — | Neutral |

**Legend:**
- **Neutral:** Reclassification has zero impact (no P0 filter match).
- **Beneficial:** Reclassification improves resolver optionality (adds to a healthy pool without degrading specificity).

---

## Conclusion

### Will Reclassification Break or Degrade Full Resolver Selections?

**No.** 

- 22 of 23 candidates are wholly unaffected by P0 filters.
- 1 candidate (chinup) is affected in a **beneficial** way: it gains entry to a 9-item general-strength pulling pool.
- No climbing-specific blocks are polluted.
- No blocks experience pool shrinkage or degradation.
- Role reclassification is not used in scoring, so relative rankings remain unchanged.

### Will It Improve the Full Resolver for Existing Session Templates?

**Marginally yes, for pulling_strength_compound users.**

- Users who can access `pulling_strength_compound` (e.g., in a 4-week strength cycle) now have a bodyweight-only pulling option (chinup)
- This is strictly an **expansion**, not a replacement
- No existing sessions are broken or degraded

### Risk Assessment

**Risk Level: LOW**

**Justification:**
1. Only 1 of 23 candidates intersects P0 filter blocks
2. That intersection is with a general-strength block, not climbing-specific
3. The pool is healthy (9 → 10) and no scarcity is created
4. No scoring or tie-breaking changes
5. No explicitly pinned exercises in templates are affected

### Recommendation

**Safe to implement.** Reclassifying the 23 exercises from `role: ["accessory"]` to `role: ["main", "accessory"]` poses no degradation risk to the full resolver and offers mild pool-expansion benefits for general-strength blocks.

---

## Appendix: Files Analyzed

- **Backend engine:** `/Users/danielesomensi/Projects/climb-agent/backend/engine/resolve_session.py`
- **Exercise catalog:** `/Users/danielesomensi/Projects/climb-agent/backend/catalog/exercises/v1/exercises.json` (212 exercises, 23 candidates)
- **Templates (8 main-role blocks):**
  - pulling_strength_compound.json (3 blocks)
  - finger_max_strength.json (1 block)
  - finger_strength_endurance.json (1 block)
  - finger_aerobic_endurance.json (1 block)
  - route_projecting_main.json (2 blocks)
- **Previous audit:** `docs/audit/D223_body_part_picker_classification_audit.md` (commit 9412dd6)

**Analysis Date:** 2026-04-23  
**Analyst:** Claude Code (read-only investigation)
