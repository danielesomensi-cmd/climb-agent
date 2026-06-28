# D217 — Body Part Picker: Catalog Audit + Design Spec

> **Type:** D (read-only audit + design)
> **Status:** Draft pending Daniele's review
> **Author:** Claude Code (Opus 4.7)
> **Date:** 2026-04-21
> **Feeds:** A-type implementation brief (A213+) + possible C-type catalog expansion (C207+)
> **Scope:** strength-focused Body Part Training generator, accessed from Free Session. v1 excludes flexibility/mobility (v2).
> **Catalog snapshot:** `backend/catalog/exercises/v1/exercises.json` — **198 exercises**.
> **Brief numbering note:** the source brief used the label "D211", but `next_brief.py` flagged D211 as already taken by `D-TESTUSER-VERIFY` residuals (Priority 1.27). The next free audit number is **D217**; this document uses D217 throughout.

---

## 0. Executive summary

- **Catalog mapping** (Task 1): 198 exercises → **156 classified** across the 11 body parts (87 unique exercises, many multi-category), **88 excluded** (53 climbing/flexibility/technique/test/warmup-only + 35 climbing-surface).
- **Launch blocker** (Task 2): only 2 categories fail the `≥3 per tier` threshold in a way that cannot be papered over — **`hips` = 1 exercise total** (MVP-blocking), **`chest` gym tier = 1 exercise** (MVP-borderline). All other gaps are explainable (e.g. hangboard = "home" tier — fingers are intentionally home-heavy).
- **Equipment selector** (Task 3): can be implemented by reusing `expand_equipment()` + `get_location_equipment()` with zero engine changes. Add a new "bodyweight" virtual location that forces `equipment=["floor"]`.
- **Warmup/cooldown** (Task 4): reuse `general_warmup` template as-is; cooldown stays optional. A body-part-aware warmup is not worth the complexity in v1.
- **Resolver light** (Task 5): a ~200-line module that reuses `prescription_defaults` + `_apply_load_override` + `suggest_max_hang_load`. No closed-loop, no feedback-driven progression. Phase-aware intensity multiplier optional for v1.
- **Duration formula** (Task 6): deterministic, derived from `prescription_defaults` via existing `estimate_custom_session_duration()` (A205 helper — already in production).
- **Logging format** (Task 7): **`session_mode: "custom_build"` is NOT new** — it already exists in A205/A207 Session Builder. Body Part Picker should reuse the same storage path. Add a `build_kind: "body_parts" | "manual"` sub-discriminator to distinguish from manual Session Builder.
- **Vocabulary** (Task 8): `docs/vocabulary_v1.md` §6.10 is stale (doesn't list `custom_build`). 11 new body-part category IDs need to be declared. No schema changes on exercises.

### Launch-blocking findings

1. **`hips` category has 1 exercise** (`hip_flexor_strengthening`). Needs C-type expansion before feature can launch.
2. **`chest` gym tier has 1 exercise** (`bench_press`). Acceptable if fallback to home/bodyweight tier is permitted, but ≥2 gym chest exercises is strongly recommended.
3. **`session_mode: "custom_build"` is already wired** for A205/A207. The brief mis-documented it as a new value — the implementation spec must reuse the existing path, not invent a parallel one.

---

## 1. Task 1 — Catalog mapping (11 body-part tables)

### Method

- Source: `backend/catalog/exercises/v1/exercises.json` (schema v2, 198 entries).
- Rules applied:
  - **Exclude** exercises whose `role` is a pure subset of `{test, warmup, cooldown, technique}` with no strength component (main/accessory/prehab).
  - **Exclude** exercises whose `pattern ∈ {climbing_continuous, climbing_intervals, climbing_routes, climbing_limit_boulder, campus_ladder}` — climbing-surface work is not body-part strength.
  - **Exclude** pure flexibility (`domain == ["flexibility"]` or `pattern ∈ {flexibility_passive, flexibility_active, static_stretch, self_massage}`) — v1 is strength-only; flexibility deferred to v2.
  - **Classify** by `domain` → category, then `pattern` → category, then apply name-based multi-category refinement (e.g. `chinup` → `back_pulling` + `biceps`, `dip` → `triceps` + `chest`).
- **Equipment tier** computed per exercise:
  - `bodyweight` = `equipment_required == []`
  - `home` = all items in `{pullup_bar, band, resistance_band, hangboard, hangboard_20mm, rings, dumbbell, loading_pin, pinch_block}`
  - `gym` = any item in `{weight, barbell, cable_machine, bench, board_kilter, board_moonboard, board_other, campus_board, gym_boulder, gym_routes, spraywall, homewall}`

### Summary table

| Category | Total | Bodyweight | Home | Gym | Equipment combos |
|---|---:|---:|---:|---:|---|
| `fingers` | 32 | 2 | 21 | 9 | —, campus_board, gym_boulder, hangboard, hangboard+band, loading_pin, pinch_block |
| `forearms` | 12 | 6 | 4 | 2 | —, dumbbell, hangboard, resistance_band, weight |
| `back_pulling` | 21 | 1 | 17 | 3 | —, campus_board, pullup_bar, pullup_bar+band, pullup_bar+weight, resistance_band, weight |
| `biceps` | 8 | 2 | 3 | 3 | —, dumbbell, hangboard, pullup_bar, weight |
| `triceps` | 8 | 4 | 2 | 2 | —, dumbbell, rings, weight |
| `chest` | 5 | 2 | 2 | 1 | —, dumbbell, rings, weight |
| `shoulders` | 14 | 7 | 5 | 2 | —, dumbbell, pullup_bar, resistance_band, weight |
| `core` | 30 | 20 | 10 | 0 | —, pullup_bar, resistance_band |
| `glutes` | 7 | 4 | 0 | 3 | —, weight |
| `hips` | **1** | 1 | 0 | 0 | — |
| `legs` | 8 | 5 | 0 | 3 | —, weight |

_Classification artefact saved to `/tmp/d217_matrix.json` (not committed) for re-use by the implementation brief._

### Per-category detail

See Appendix A for the full per-exercise tables.

---

## 2. Task 2 — Gap analysis

**MVP threshold (per brief): each category must have ≥3 exercises for bodyweight AND ≥3 exercises for gym tier.**

The "home" tier is not listed as a threshold in the brief, but it matters in practice because that is where most users actually train (hangboard at home, pull-up bar, band, dumbbells).

### Per-category verdict

| Category | BW ≥3 | Gym ≥3 | Home ≥3 | Verdict | Notes |
|---|---|---|---|---|---|
| `fingers` | ❌ 2 | ✅ 9 | ✅ 21 | **OK** | Fingers intrinsically need hangboard. BW=2 (`finger_extensor_band`, `finger_tendon_glides`) is enough for accessory/prehab. Users without hangboard will accept this. |
| `forearms` | ✅ 6 | ❌ 2 | ✅ 4 | **OK** | Gym users can fall back to home-tier (dumbbell wrist curls work in a gym). No real block. |
| `back_pulling` | ❌ 1 | ✅ 3 | ✅ 17 | **OK** | Only BW candidate is `inverted_row`. Back-pulling inherently needs a bar — BW-only users should be told "add a pull-up bar" rather than generate a session with one exercise. |
| `biceps` | ❌ 2 | ✅ 3 | ✅ 3 | **OK** | Borderline BW. Curl variants naturally need load. |
| `triceps` | ✅ 4 | ❌ 2 | ❌ 2 | **Borderline** | BW is strong (dip, pike pushup, pushup, handstand pushup). Gym tier of 2 (`bench_press`, `overhead_press`) is thin — add a third (e.g. `tricep_rope_pushdown`, cable). |
| `chest` | ❌ 2 | ❌ 1 | ❌ 2 | **MVP-borderline** | `bench_press` only gym-tier chest. Add `dumbbell_bench_press` to gym tier (already in home, reuse) and `incline_pushup` / `decline_pushup` variants for BW. |
| `shoulders` | ✅ 7 | ❌ 2 | ✅ 5 | **OK** | Gym tier thin; rest of tiers strong. |
| `core` | ✅ 20 | ✅ 0 | ✅ 10 | **OK** | Core is equipment-light by nature — gym=0 is correct and expected. |
| `glutes` | ✅ 4 | ✅ 3 | ❌ 0 | **Borderline** | No home-tier glute exercise — home users have to fall back to BW. OK for MVP. Could add `band_glute_bridge`, `single_leg_hip_thrust`. |
| `hips` | ❌ 1 | ❌ 0 | ❌ 0 | **BLOCKER** | Only `hip_flexor_strengthening`. Entire category below MVP in every tier. **Must ship a C-type brief before this feature can launch.** |
| `legs` | ✅ 5 | ✅ 3 | ❌ 0 | **OK** | Home tier 0 (same pattern as glutes) — BW fallback is fine. Add 2-3 dumbbell-based leg exercises later if desired. |

### Missing exercises — concrete catalog suggestions

These are the minimum additions to unblock launch + close borderline gaps. For the A213 implementation brief, these should be split into a **C207 Body Part Catalog expansion** brief.

**Hips (CRITICAL — must add before launch; target ≥3 per tier, minimum 4 total):**

| Proposed `exercise_id` | Domain | Pattern | `equipment_required` | Tier | Notes |
|---|---|---|---|---|---|
| `standing_hip_abduction` | `strength_general` | `shoulder_isolation`† | `[]` | bodyweight | Side-lying or standing, can add band. |
| `side_lying_hip_abduction` | `strength_general` | `shoulder_isolation`† | `[]` | bodyweight | Gluteus medius work. |
| `band_hip_adduction` | `strength_general` | `shoulder_isolation`† | `[resistance_band]` | home | Cable-alternative at home. |
| `copenhagen_adductor_raise` | `strength_general` | `anti_lateral_flexion` | `[]` | bodyweight | Already classified as core — could be re-tagged hips too. |
| `hip_circles_active` | `mobility` | (needs new `hip_mobility` pattern) | `[]` | bodyweight | Borderline flexibility — keep in v2 if policy holds. |
| `seated_leg_raise` | `strength_general` | `compression` | `[]` | bodyweight | Hip flexor strength, complements existing `hip_flexor_strengthening`. |
| `goblet_squat_wide_stance` | `strength_general` | `squat` | `[weight]` | gym | Adductor-biased squat. Could tag existing `goblet_squat` as multi-cat hips. |

† _The `shoulder_isolation` pattern is a catalog misnomer for "isolation work on a single joint". Consider adding a new `hip_isolation` pattern in the catalog vocabulary, or repurpose existing. Design question for the C-type brief._

**Chest (borderline — add 1-2 for comfort):**

| `exercise_id` | Domain | Pattern | Equipment | Tier |
|---|---|---|---|---|
| `incline_pushup` | `strength_general` | `push` | `[]` | bodyweight |
| `decline_pushup` | `strength_general` | `push` | `[]` | bodyweight |
| `cable_fly` | `strength_general` | `push` | `[cable_machine]` or `[weight]` | gym |
| `dumbbell_fly` | `strength_general` | `push` | `[dumbbell]` | home |

**Triceps (borderline gym tier):**

| `exercise_id` | Domain | Pattern | Equipment | Tier |
|---|---|---|---|---|
| `tricep_rope_pushdown` | `strength_general` | `push` | `[cable_machine]` or `[weight]` | gym |
| `skull_crusher` | `strength_general` | `push` | `[dumbbell]` or `[weight]` | home/gym |

**Shoulders (borderline gym tier):**

Add cable-based `face_pull_cable`, `cable_lateral_raise` if cable_machine vocabulary enables it. Otherwise acceptable as-is.

**Legs/glutes home tier:**

- `band_glute_bridge` — `[resistance_band]` — home
- `single_leg_hip_thrust` — `[]` — bodyweight (tag glutes)
- `dumbbell_goblet_squat_home` — rename existing `goblet_squat` tier if equipment can be home (`weight` tag is ambiguous; `[dumbbell]` would be home-tier).

### Recommendation for A213

Launch v1 **after** a C207 mini-catalog-expansion ships at least 3 new `hips` exercises and 1 additional `chest` gym-tier exercise. Everything else is green.

---

## 3. Task 3 — Equipment selector spec

### Existing building blocks (reusable)

| Component | Location | Purpose | Reuse verdict |
|---|---|---|---|
| `expand_equipment()` | `backend/engine/equipment_utils.py:57` | Expands equipment list: `weight` implied by `dumbbell/kettlebell/barbell`; `pullup_bar` implied by `hangboard`; boulder surfaces imply `gym_boulder`. | **Reuse as-is.** |
| `get_location_equipment()` | `backend/engine/resolve_session.py:596` | Resolves (location, equipment) from `user_state.context.location` + `session.context` + `user_state.equipment`. Hard-coded to `home`/`gym` binary. | **Partial reuse.** Needs a new `bodyweight` pseudo-location. |
| `compatible_with_location()` | `backend/engine/resolve_session.py:829` | Per-exercise equipment gate: `ex.equipment_required ⊆ available_equipment`. | **Reuse as-is.** |
| `KNOWN_EQUIPMENT_KEYS` | `backend/engine/equipment_utils.py:42` | Registry of allowed equipment keys. | **Reuse as-is.** |

### Selector → equipment mapping (design)

| UI selector option | Resolved `equipment_mode` | Equipment list passed to selector | How it's derived |
|---|---|---|---|
| **Bodyweight** | `"bodyweight"` | `["floor"]` (nothing else) | Hard-coded in new handler. Bypasses `user_state.equipment`. |
| **Home** | `"home"` | `expand_equipment(user_state.equipment.home) + ["floor"]` | Direct call to existing flow; reuse `get_location_equipment` with `location="home"`. |
| **Gym X** (user picks which) | `"gym"` + `gym_id` | `expand_equipment(user_state.equipment.gyms[gym_id].equipment) + ["floor"]` | Reuse `get_location_equipment` with `location="gym"` and inject `gym_id` into `session.context`. |
| **Show All** | `"all"` | `list(KNOWN_EQUIPMENT_KEYS)` (ignore user state) | New branch — bypass user equipment entirely. |

### Minimal integration

A new helper in `backend/engine/body_part_picker.py`:

```python
def resolve_equipment_mode(
    mode: str,                           # "bodyweight" | "home" | "gym" | "all"
    user_state: dict,
    gym_id: str | None = None,
) -> list[str]:
    """Return expanded equipment list for the chosen mode.

    - bodyweight → ["floor"]
    - home       → expand_equipment(user_state.equipment.home) + ["floor"]
    - gym        → expand_equipment(user_gym[gym_id].equipment) + ["floor"]
    - all        → list(KNOWN_EQUIPMENT_KEYS)
    """
```

No changes needed in `resolve_session.py` or `equipment_utils.py`. The new helper is strictly additive.

---

## 4. Task 4 — Warmup/cooldown recommendation

### Existing templates surveyed

| Template | Path | Fit for body-part session? |
|---|---|---|
| `general_warmup` | `backend/catalog/templates/v1/general_warmup.json` | **✅ Best fit.** 3 blocks: pulse raise, dynamic mobility, shoulder activation. No climbing-specific progression. `equipment_any_of = [none, band, mat, floor]`. 2026 build-quality. |
| `warmup_strength` | `backend/catalog/templates/v1/warmup_strength.json` | Only for finger-strength sessions — includes `hang_rampup_progressive`. Not appropriate for generic body-part session. |
| `warmup_climbing` | `backend/catalog/templates/v1/warmup_climbing.json` | Climbing-specific, includes `warmup_easy_boulders`. Definitely not. |
| `cooldown_stretch` | `backend/catalog/templates/v1/cooldown_stretch.json` | Passive stretches (forearm/wrist, hip pigeon, generic flexibility). **Optional reuse.** |

### Recommendation

- **Warmup:** reuse `general_warmup` unmodified. It is equipment-light (no hangboard required, no wall) and sport-agnostic enough. Resolver-side: call `_resolve_inline_block()` (resolve_session.py:919) on its block list as-is.
- **Cooldown:** keep `cooldown_stretch` as **optional**. Design suggestion: present it as a post-session toggle ("Add cooldown? [Yes / Skip]") in the frontend. The catalog block already exists — no new data needed.
- **Body-part-specific warmup:** **not worth it in v1.** It would require a new template per category (11× work) or conditional logic that queries stress tags. The selected body part will be mobilized implicitly during the first light set of each main exercise. Defer to v2 after user feedback.

### Warmup duration invariant

`general_warmup` has 3 blocks. Observed typical prescription:
- `pulse_raise` — ~3 min
- `mobility` — ~2-3 min
- `shoulder_activation` — 2-3 sets × 8-15 reps × ~30-60s rest → ~3-4 min

**Total warmup ≈ 8-10 minutes.** Round to **10 min** for the duration counter.

### Cooldown duration invariant

`cooldown_stretch` has 3 blocks. Each block is 20-60s hold × 1-2 sets.

**Total cooldown ≈ 4-5 minutes.** Round to **5 min** for the duration counter.

---

## 5. Task 5 — Resolver light spec

### Where prescription defaults come from

Every exercise carries `prescription_defaults` inline. Example from `pullup`:

```json
{
  "sets": 3,
  "reps": 3,
  "work_seconds": null,
  "rest_between_reps_seconds": null,
  "rest_between_sets_seconds": 120
}
```

Keys observed across the catalog: `sets`, `reps`, `work_seconds`, `hold_seconds`, `hold_seconds_range`, `rest_between_reps_seconds`, `rest_between_sets_seconds`, `notes`, `intensity_pct_of_total_load`, `grade_ref`, `grade_offset`.

### How working maxes are looked up in the full resolver

Two independent systems feed load suggestions:

1. **Per-exercise override** — `_apply_load_override()` (resolve_session.py:63): reads `user_state.overrides.per_exercise[exercise_id]` with `{mode: "absolute_load_kg" | "delta_kg" | "multiplier", value, expires}`. Used for user-driven load nudges.
2. **Hangboard baseline** — `suggest_max_hang_load()` (resolve_session.py:127): for exercises with `load_model: total_load`, reads `user_state.baselines.hangboard[].max_total_load_kg` to suggest `added_weight_kg = intensity% × max_total − bodyweight`.
3. **Working loads registry** — `user_state.working_loads.entries[]`: the closed-loop system updates `next_external_load_kg` based on feedback. Keyed by `exercise_id` (or `cluster_key`). Not read directly by `resolve_session.py` for non-hangboard exercises — the current flow routes through `progression_v1.py` / `closed_loop_v1.py`.
4. **Pulling baseline** — `user_state.baselines.pulling`: estimated 1RM for `weighted_pullup` / `barbell_row` etc. Used as a scaling anchor.

### Minimum viable resolver light

**Pipeline (per selected exercise):**

```
1. Copy prescription_defaults from catalog entry.
2. If user_state.overrides.per_exercise[exercise_id] exists → apply via _apply_load_override.
3. If user_state.working_loads.entries[exercise_id].next_external_load_kg exists → set prescription.load_kg = that.
4. Else if load_model == "total_load" and hangboard baseline present → call suggest_max_hang_load().
5. Else if load_model == "external_load" and pulling baseline present → scale from baselines.pulling.
6. Else → leave load_kg unset (show "as able" in UI).
```

Steps 1, 2, 4 reuse **existing resolver functions verbatim**. Step 3 is a new ~5-line lookup. Step 5 needs a small helper but is already implemented inside `progression_v1._estimate_pulling_baseline`.

**No closed-loop feedback writes.** The Body Part Picker session logs feedback the same way any custom_build session does (via `/api/feedback`), but the closed-loop adapter should be configured to **skip** `session_mode=="custom_build"` payloads, or to only update `working_loads.entries` without touching the macrocycle planner. Verify at implementation time.

### Function signature (proposed)

```python
# backend/engine/body_part_picker.py

def generate_body_part_session(
    body_parts: list[str],        # subset of 11 category IDs
    equipment_mode: str,          # "bodyweight" | "home" | "gym" | "all"
    gym_id: str | None,
    user_state: dict,
    exercises_catalog: list[dict],
    seed: int | None = None,      # for deterministic testing
) -> dict:
    """Generate a strength-focused session from selected body parts.

    Pipeline:
      1. Resolve equipment list via resolve_equipment_mode().
      2. Build exercise pool: classify_by_body_part(catalog) ∩ equipment-compatible.
      3. For each body_part in body_parts (order preserved):
         - Pick N_PER_BODY_PART (default 2) exercises via select_exercises_for_part().
         - Exclude already-picked exercise IDs (dedup across body parts).
         - Apply resolver-light to each: prescription_defaults + load override.
      4. Prepend warmup blocks (general_warmup template resolved).
      5. Append cooldown (cooldown_stretch, optional — wire via a flag).
      6. Compute session-level metadata:
         - estimated_duration_minutes  (see Task 6)
         - estimated_load_score        (reuse compute_custom_session_load)
         - body_parts_selected         (input echo)
         - equipment_mode, gym_id      (input echo)

    Returns a dict matching the session shape used by replanner_v1 `add_custom_session`
    branch (replanner_v1.py:1217) so the session can flow through the existing
    week_plan → session_logs pipeline.
    """
```

### Selection policy (design decision)

| Option | Behavior | Pro | Con |
|---|---|---|---|
| **A. Random from filtered pool** | Shuffle with optional `seed` | Simple, variety | Non-deterministic per user → bad for reproducibility |
| **B. Scored (recency-aware)** | Reuse `score_exercise()` + `load_recent_exercise_ids()` | Consistent with main resolver | More complex, requires session_logs history |
| **C. Scored + user preferences** | B + user-flagged favorites | Best UX | Adds schema changes |

**Recommendation for v1:** **B.** Reuse existing scoring helpers. Rationale:
- The Body Part Picker is a "paid-user power tool" — deterministic behaviour is a feature, not a bug.
- `score_exercise()` already takes into account intensity/phase/recency; calling it with an empty recent-id set yields plausible variety.
- If a user picks the same body parts twice in a row, `load_recent_exercise_ids()` naturally rotates selections.

### Exercises per body part

**Recommendation: 2 primary + 1 optional accessory.** Makes the duration counter predictable (2 × ~10 min ≈ 20 min per body part including rest), and respects the "user decides length" principle (no upper bound on body parts selected).

Make `N_PER_BODY_PART` a constant in the module (not configurable in v1); revisit after beta feedback.

### Output format

Reuse the custom-build session shape from `replanner_v1.py:1217-1234`:

```python
{
  "slot": slot,
  "session_id": f"custom_{generated_id}",
  "custom_session_id": generated_id,
  "session_mode": "custom_build",
  "build_kind": "body_parts",             # NEW: sub-discriminator
  "is_custom": True,
  "name": f"Body Part Training — {body_parts_joined}",
  "location": location,
  "gym_id": gym_id,
  "status": "planned",
  "intensity": "medium",
  "estimated_load_score": <computed>,
  "target_duration_min": <computed>,
  "exercises": [<resolved exercise instances>],
  "tags": {"hard": False, "finger": "fingers" in body_parts},
  "constraints_applied": ["custom_add", "body_parts"],
  "explain": [f"body_parts={body_parts}", f"equipment_mode={equipment_mode}"],

  # NEW metadata:
  "body_parts_selected": body_parts,
  "equipment_mode": equipment_mode,
  "generated_at": <iso_ts>,
  "generator_version": "body_part_picker.v1",
}
```

The `build_kind` sub-field distinguishes Body Part Picker output from A205/A207 Session Builder manual output. This is important for analytics and for the closed-loop adapter's skip logic.

---

## 6. Task 6 — Duration formula

### Existing helper (reusable)

`backend/engine/custom_session.py:14` — `estimate_custom_session_duration(exercises)` already computes:

```
for each exercise:
  work_per_set = work_seconds OR reps × 4s OR 30s fallback
  rest_per_set = rest_between_sets_seconds OR 60s
  total += sets × work_per_set + max(0, sets-1) × rest_per_set
return max(1, round(total_seconds / 60))
```

This is **sufficient** for the main-block portion of the Body Part Picker session. The A205/A207 Session Builder already uses it in production.

### Full formula for live counter

```
total_minutes = warmup_minutes                             # constant 10
              + Σ estimate_custom_session_duration(exs)     # per body part
              + Σ transition_minutes                        # 1 min per body-part switch
              + cooldown_minutes                            # constant 5 (if enabled, else 0)
```

### Per-body-part estimation cheat-sheet (for UI stub before exercises are picked)

For the live counter that updates **as the user selects** body parts (before the actual exercises are resolved), the UI can use a rough per-body-part constant:

| Category | Typical time per body part (min) | Rationale |
|---|---|---|
| `fingers` | 15 | Long rest (3-5 min) × 3-5 hang sets |
| `back_pulling` | 12 | 3 sets × 3-5 reps × 2 min rest |
| `core` | 8 | Short holds, short rest |
| `chest / triceps / biceps` | 10 | 3-4 sets × 8-12 reps × 60-90s rest |
| `shoulders / forearms` | 8 | Lighter loads, shorter rest |
| `legs / glutes / hips` | 10 | 3-4 sets × 8-12 reps × 90s rest |

Implementation: store these in a dict in `body_part_picker.py`:

```python
PER_BODY_PART_STUB_MIN = {
    "fingers": 15, "back_pulling": 12,
    "chest": 10, "triceps": 10, "biceps": 10, "legs": 10, "glutes": 10, "hips": 10,
    "shoulders": 8, "forearms": 8, "core": 8,
}
OVERHEAD_MIN = {"warmup": 10, "cooldown": 5, "transition": 1}
```

Once the session is actually generated (user clicks "Generate"), replace the stub total with the precise `estimate_custom_session_duration()` result.

---

## 7. Task 7 — Session logging format

### Current state: `custom_build` already exists

Grep of `session_mode` across backend (output truncated):

- `backend/engine/replanner_v1.py:1221` — writes `session_mode: "custom_build"` in `add_custom_session` branch of `apply_events`.
- `backend/tests/test_a207_custom_session_integration.py:104` — asserts `added["session_mode"] == "custom_build"`.
- `backend/api/routers/free_session.py:140, 142, 144, 181, 184, 206, 309, 359` — handles `"template"`, `"free"`, `"circuit"` via `VALID_SESSION_MODES` (custom_build is NOT listed here because free_session is a different entry point).

**Verdict: `custom_build` is already a live value in the week_plan session storage.** The Body Part Picker should reuse the same path.

### Storage architecture

Three layers:

1. **Week plan (ephemeral)** — `user_state.week_plans[monday].weeks[0].days[].sessions[]`. Custom-build sessions sit here until completion. This is what the frontend reads for Today/Week views.
2. **Session logs (permanent)** — Supabase `session_logs` table (or `session_logs.jsonl` for file-mode). Written on session completion via the feedback flow. Queried by `report_engine.py` → `storage.read_session_logs()`.
3. **Custom session templates** — `user_state.custom_sessions[]`. A205 Session Builder stores user-saved templates here. Body Part Picker sessions are **one-off** (not templates), so they do **not** write to this list.

### Recommended logging flow for Body Part Picker

```
1. User selects body parts + equipment → frontend POSTs /api/body-part-picker/generate
2. Backend calls generate_body_part_session(...) → returns the session dict
3. Frontend shows the session preview (exercises, duration, load).
4. User taps "Start" → frontend POSTs /api/replanner/events with:
     event_type: "add_custom_session"
     custom_session_id: <newly-minted uuid>
     session_payload: <the generated session dict>
     target_date: today
     slot: auto-pick first free slot
5. Backend persists the one-off session via replanner.apply_events (same branch as A205).
6. On completion, the existing feedback path fires → writes to session_logs.
```

**Alternative: introduce a new `event_type: "add_generated_session"` branch** in `replanner_v1.apply_events` that accepts a **full session dict** instead of a `custom_session_id` reference to `user_state.custom_sessions`. This keeps user_state lean (no one-off templates persisted).

**Recommendation: the alternative.** Body-part-picker sessions have no reason to be saved as reusable templates. An explicit `add_generated_session` branch is cleaner than hacking `add_custom_session` to accept inline payloads.

### Metadata stored

Beyond the standard custom-build fields, add:

| Field | Where | Purpose |
|---|---|---|
| `build_kind` | session dict | `"body_parts"` vs `"manual"` (A205 output) |
| `body_parts_selected` | session dict + session_log | List of selected categories — enables analytics ("most popular body parts") |
| `equipment_mode` | session dict + session_log | Selector value at generate time |
| `generator_version` | session dict | `"body_part_picker.v1"` — enables future regeneration logic |
| `duration_actual` | session_log (via feedback) | Already captured by B217 `session_duration_seconds` flow |

### Weekly reports integration

`backend/engine/report_engine.py` currently reads `session_logs` for adherence/load tallies. Body-part sessions will appear naturally in the weekly report **as long as the completion flow writes the same shape** (with `session_mode: "custom_build"` and `session_id: "custom_…"`). Add a small filter in `report_engine` to group by `build_kind` if we want a "Body Part Training usage" breakdown — low priority, can ship post-launch.

---

## 8. Task 8 — Vocabulary additions

### `docs/vocabulary_v1.md` changes needed

1. **§6.10 Session mode — add `custom_build`:**

   ```markdown
   - `custom_build` — user-built session (Session Builder A205/A207 or Body Part Picker)
   ```

   This is a **documentation catch-up**, not a new value. The code already writes it.

2. **New §6.11 Custom build kind** (new subsection):

   ```markdown
   ### 6.11 Custom build kind

   When `session_mode == "custom_build"`, the `build_kind` field distinguishes origin:

   - `manual` — user picked individual exercises via Session Builder (A205/A207)
   - `body_parts` — system generated from body-part selection (A213+)
   ```

3. **New §3.X Body part categories** (under domain taxonomy):

   ```markdown
   ### 3.X Body part categories (Body Part Picker — A213+)

   11 coarse-grained training targets for the Body Part Picker generator:

   - `fingers` — hangboard, pinch, crimp work
   - `forearms` — wrist curls, pronation, prehab
   - `back_pulling` — pull-up, row, lock-off
   - `biceps` — curl variations
   - `triceps` — dips, extensions, push-down
   - `chest` — push-up, bench press
   - `shoulders` — rotator cuff, lateral raise, stability
   - `core` — hollow, plank, anti-rotation, L-sit
   - `glutes` — bridge, hip thrust
   - `hips` — hip flexor, adductors, abductors
   - `legs` — calves, squat, lunge

   Orthogonal to `domain` and `pattern`: a body part category is a UI-level grouping,
   not an engine classification. Mapping is computed by
   backend/engine/body_part_picker.py::classify_exercise_body_parts().
   ```

### Exercise schema changes needed

**None required for v1.** Classification is computed at runtime from existing `domain` + `pattern` + `role` + `id` fields. A future enhancement could add an explicit `body_parts: [...]` field on the exercise schema to make multi-category membership data-driven instead of code-driven — defer this to v2.

### New API endpoints

| Method | Path | Purpose | Protected? |
|---|---|---|---|
| `GET` | `/api/body-part-picker/surfaces` | Return 11 body part categories with labels + per-tier counts for the current user | yes — subscription gated |
| `GET` | `/api/body-part-picker/equipment-options` | Return `["bodyweight", "home", "all"]` + `user.equipment.gyms[].id` | yes |
| `POST` | `/api/body-part-picker/preview` | Generate session preview (pure function, no state write) | yes |
| `POST` | `/api/body-part-picker/start` | Persist the generated session to today's plan via `add_generated_session` event | yes |

Total: **+4 endpoints** (63 → 67). All under `/api/body-part-picker/`. The `start` endpoint can be replaced by an extension of `/api/replanner/events` if we avoid adding a new router — decision for the implementation brief.

---

## 9. Open questions for Daniele

1. **Hips catalog gap** — should C207 (catalog expansion) be a prerequisite brief, or can A213 ship with the feature hidden until C207 lands? Recommend: A213 ships with `hips` disabled in the UI; C207 follows immediately.
2. **Flexibility in v1 vs v2** — the brief says v1 is strength-only, but Christie-type users will reasonably expect a "Hips" pick to include some active mobility work. Consider allowing `pattern: flexibility_active` exercises (active — not passive stretching) as fallback when a category has no strength exercises available. Decision affects ~20 excluded exercises.
3. **Closed-loop interaction** — should completed body-part-picker sessions update `working_loads.entries[]`? Pro: feedback improves load suggestions next time. Con: noise pollutes the progression system that was designed around the weekly plan. Recommend: **yes, but skip the `progression_v1` adaptation step** (update only `next_external_load_kg`, don't trigger phase re-evaluation).
4. **Session storage** — confirm the "inline session dict" approach (`add_generated_session` event) vs. the "ephemeral custom_session template + add_custom_session event" approach. Recommend the former to keep `user_state.custom_sessions` clean.
5. **Brief number** — confirm D217 as the correct audit number (auto-selected by `next_brief.py`), and that this audit should be followed by **A213** (implementation) and optionally **C207** (catalog expansion for hips).

---

## Appendix A — Full per-category exercise tables

The full per-exercise classification tables (generated deterministically from the catalog) are embedded below. Total: 11 tables, 156 exercise rows.

_(Generated from `/tmp/d217_matrix.json` — reproducible by re-running the classifier in the implementation brief.)_

<!-- BEGIN_CATEGORY_TABLES -->
<!-- Inlined from /tmp/d217_category_tables.md — keep in sync if the classifier changes -->

### fingers
Exercises found: **32** (bw=2 home=21 gym=9)
Equipment combos: `[—, campus_board, gym_boulder, hangboard, hangboard+band, loading_pin, pinch_block]`
Bodyweight-only count: **2**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `finger_extensor_band` | Finger Extensor Band Extensions | — | bodyweight_only | very_low | bodyweight |
| `finger_tendon_glides` | Finger Tendon Gliding Exercises | — | bodyweight_only | very_low | bodyweight |
| `lp_density_lifts` | Loading Pin Density Lifts | loading_pin | external_load | medium | gym |
| `lp_max_lift_10s` | Loading Pin Max Lift (10s) | loading_pin | external_load | high | gym |
| `lp_max_lift_5s` | Loading Pin Max Lift (5s) | loading_pin | external_load | max | gym |
| `lp_max_lift_7s` | Loading Pin Max Lift (7s) | loading_pin | external_load | max | gym |
| `lp_repeater_lifts` | Loading Pin Repeater Lifts | loading_pin | external_load | medium | gym |
| `lp_short_lifts` | Loading Pin Short Lifts (Recruitment) | loading_pin | external_load | max | gym |
| `pangullich_ladders_easy` | Campus Board Ladders (Controlled) | campus_board | bodyweight_only | high | gym |
| `pinch_block_training` | Pinch Block Training | pinch_block | total_load | high | gym |
| `power_slap_drill` | Power Slap / Deadpoint Drill | gym_boulder | bodyweight_only | high | gym |
| `active_finger_curls` | Active Finger Curls (Dynamic Tendon Loading) | hangboard | bodyweight_only | low | home |
| `density_hangs` | Density Hangs (Tyler Nelson) | hangboard | total_load | high | home |
| `grip_transitions_half_to_open` | Grip Transitions (Half-Crimp to Open-Hand) | hangboard | bodyweight_only | high | home |
| `hangboard_moving_hangs` | Hangboard Moving Hangs (HMH) | hangboard | total_load | low | home |
| `horst_7_53` | Hörst 7-53 Protocol | hangboard | total_load | high | home |
| `intermittent_dead_hangs` | Intermittent Dead Hangs | hangboard | total_load | medium | home |
| `long_duration_hang` | Long Duration Hang (Tendon Health) | hangboard | total_load | medium | home |
| `long_interval_repeaters` | Long-Interval Repeaters | hangboard | total_load | low | home |
| `lopez_subhangs` | López Submaximal Hangs | hangboard | total_load | medium | home |
| `max_hang_10s` | Max Hang 10s (Hypertrophy) | hangboard | total_load | high | home |
| `max_hang_5s` | Max Hang (5s) | hangboard | total_load | max | home |
| `max_hang_7s` | Max Hang (7s) | hangboard | total_load | max | home |
| `max_hang_ladder` | Bechtel 3-6-9 Ladder | hangboard | total_load | max | home |
| `min_edge_hang` | Minimum Edge Hang (MED) | hangboard | bodyweight_only | max | home |
| `one_arm_hang_assisted` | One-Arm Hang (Assisted) | hangboard,band | total_load | max | home |
| `overcoming_isometric_pull` | Overcoming Isometric Pull | hangboard | bodyweight_only | max | home |
| `repeater_15_15` | Repeater Hang 15/15 (IntHangs) | hangboard | total_load | medium | home |
| `repeater_hang_7_3` | Hangboard Repeaters 7/3 (Strength-Endurance) | hangboard | total_load | high | home |
| `repeater_sub_max_endurance` | Sub-Max Repeaters (Endurance Variant) | hangboard | total_load | medium | home |
| `rfd_explosive_pulls` | RFD Explosive Finger Pulls | hangboard | bodyweight_only | max | home |
| `sub_max_capacity_hang` | Sub-Max Capacity Hang | hangboard | total_load | medium | home |

### forearms
Exercises found: **12** (bw=6 home=4 gym=2)
Equipment combos: `[—, dumbbell, hangboard, resistance_band, weight]`
Bodyweight-only count: **6**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `elbow_eccentric_curl` | Elbow Eccentric Curl (Tyler Twist) | — | external_load | low | bodyweight |
| `farmers_carry` | Farmer's Carry | — | external_load | medium | bodyweight |
| `finger_extensor_band` | Finger Extensor Band Extensions | — | bodyweight_only | very_low | bodyweight |
| `finger_extensor_training` | Finger Extensor Training (Rubber Band) | — | bodyweight_only | low | bodyweight |
| `finger_tendon_glides` | Finger Tendon Gliding Exercises | — | bodyweight_only | very_low | bodyweight |
| `forearm_pronation_supination` | Forearm Pronation/Supination | — | external_load | low | bodyweight |
| `reverse_wrist_curl` | Reverse Wrist Curl (Extension) | weight | external_load | low | gym |
| `wrist_curl` | Wrist Curl (Flexion) | weight | external_load | low | gym |
| `active_finger_curls` | Active Finger Curls (Dynamic Tendon Loading) | hangboard | bodyweight_only | low | home |
| `elbow_wrist_extensor_eccentric` | Wrist Extensor Eccentrics | dumbbell | bodyweight_only | low | home |
| `pronator_terres_isometric_hold` | Pronator Teres Isometric Hold | resistance_band | bodyweight_only | low | home |
| `stick_pronation_supination_eccentric` | Stick Pronation/Supination Eccentrics | dumbbell | bodyweight_only | low | home |

### back_pulling
Exercises found: **21** (bw=1 home=17 gym=3)
Equipment combos: `[—, campus_board, pullup_bar, pullup_bar+band, pullup_bar+weight, resistance_band, weight]`
Bodyweight-only count: **1**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `inverted_row` | Inverted Row | — | bodyweight_only | medium | bodyweight |
| `barbell_row` | Barbell Row | weight | external_load | medium | gym |
| `pangullich_ladders_easy` | Campus Board Ladders (Controlled) | campus_board | bodyweight_only | high | gym |
| `weighted_pullup` | Weighted Pull-up | pullup_bar,weight | total_load | high | gym |
| `archer_pullup` | Archer Pull-up | pullup_bar | bodyweight_only | high | home |
| `band_assisted_pullup` | Band-assisted Pull-up | pullup_bar,band | bodyweight_only | medium | home |
| `chinup` | Chin-up | pullup_bar | bodyweight_only | medium | home |
| `eccentric_pullup` | Eccentric Pull-Up (Negative) | pullup_bar | bodyweight_only | medium | home |
| `face_pull` | Face Pull (Band) | resistance_band | external_load | low | home |
| `frenchies` | Frenchies (Isometric Pull-up Intervals) | pullup_bar | bodyweight_only | high | home |
| `front_lever_one_leg` | Front Lever (One Leg Extended) | pullup_bar | bodyweight_only | high | home |
| `front_lever_straddle` | Front Lever (Straddle) | pullup_bar | bodyweight_only | high | home |
| `front_lever_tuck` | Front Lever (Tuck Progression) | pullup_bar | bodyweight_only | high | home |
| `l_sit_pullup` | L-Sit Pull-up | pullup_bar | bodyweight_only | high | home |
| `lock_off_isometric` | Lock-off Isometric (Multi-Angle) | pullup_bar | bodyweight_only | high | home |
| `one_arm_pullup_assisted` | One-Arm Pull-up (Assisted) | pullup_bar,band | bodyweight_only | max | home |
| `power_pullups_explosive` | Explosive Pull-ups (Power) | pullup_bar | bodyweight_only | high | home |
| `pullup` | Pull-up | pullup_bar | bodyweight_only | high | home |
| `scapular_pullup` | Scapular Pull-up | pullup_bar | bodyweight_only | low | home |
| `typewriter_pullup` | Typewriter Pull-up | pullup_bar | bodyweight_only | high | home |
| `uneven_grip_pullup` | Uneven-Grip Pull-up (One-Arm Progression) | pullup_bar | bodyweight_only | high | home |

### biceps
Exercises found: **8** (bw=2 home=3 gym=3)
Equipment combos: `[—, dumbbell, hangboard, pullup_bar, weight]`
Bodyweight-only count: **2**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `elbow_eccentric_curl` | Elbow Eccentric Curl (Tyler Twist) | — | external_load | low | bodyweight |
| `inverted_row` | Inverted Row | — | bodyweight_only | medium | bodyweight |
| `barbell_row` | Barbell Row | weight | external_load | medium | gym |
| `reverse_wrist_curl` | Reverse Wrist Curl (Extension) | weight | external_load | low | gym |
| `wrist_curl` | Wrist Curl (Flexion) | weight | external_load | low | gym |
| `active_finger_curls` | Active Finger Curls (Dynamic Tendon Loading) | hangboard | bodyweight_only | low | home |
| `bicep_curl` | Bicep Curl | dumbbell | external_load | low | home |
| `chinup` | Chin-up | pullup_bar | bodyweight_only | medium | home |

_Note: `reverse_wrist_curl` and `wrist_curl` are classifier noise — they're forearm exercises, not biceps. Multi-category overlap via the `elbow_flexion` pattern matcher. A213 should tighten the rule (e.g. require `pattern == "elbow_flexion"` + not in forearms pool)._

### triceps
Exercises found: **8** (bw=4 home=2 gym=2)
Equipment combos: `[—, dumbbell, rings, weight]`
Bodyweight-only count: **4**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `dip` | Dip | — | bodyweight_only | high | bodyweight |
| `handstand_pushup_wall` | Handstand Push-up (Wall) | — | bodyweight_only | high | bodyweight |
| `pike_pushup` | Pike Push-up | — | bodyweight_only | medium | bodyweight |
| `pushup` | Push-up | — | bodyweight_only | medium | bodyweight |
| `bench_press` | Bench Press | weight | external_load | medium | gym |
| `overhead_press` | Overhead Press | weight | external_load | medium | gym |
| `dumbbell_bench_press` | Dumbbell Bench Press | dumbbell | external_load | medium | home |
| `ring_pushup` | Ring Push-up | rings | bodyweight_only | medium | home |

### chest
Exercises found: **5** (bw=2 home=2 gym=1)
Equipment combos: `[—, dumbbell, rings, weight]`
Bodyweight-only count: **2**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `dip` | Dip | — | bodyweight_only | high | bodyweight |
| `pushup` | Push-up | — | bodyweight_only | medium | bodyweight |
| `bench_press` | Bench Press | weight | external_load | medium | gym |
| `dumbbell_bench_press` | Dumbbell Bench Press | dumbbell | external_load | medium | home |
| `ring_pushup` | Ring Push-up | rings | bodyweight_only | medium | home |

### shoulders
Exercises found: **14** (bw=7 home=5 gym=2)
Equipment combos: `[—, dumbbell, pullup_bar, resistance_band, weight]`
Bodyweight-only count: **7**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `freestanding_handstand_practice` | Freestanding Handstand Practice | — | bodyweight_only | medium | bodyweight |
| `handstand_pushup_wall` | Handstand Push-up (Wall) | — | bodyweight_only | high | bodyweight |
| `handstand_shoulder_taps` | Handstand Shoulder Taps (Wall) | — | bodyweight_only | high | bodyweight |
| `pike_pushup` | Pike Push-up | — | bodyweight_only | medium | bodyweight |
| `turkish_getup` | Turkish Get-up | — | external_load | medium | bodyweight |
| `wall_handstand_hold` | Wall Handstand Hold (Belly-to-Wall) | — | bodyweight_only | medium | bodyweight |
| `wall_walk_up` | Wall Walk-up | — | bodyweight_only | medium | bodyweight |
| `bench_press` | Bench Press | weight | external_load | medium | gym |
| `overhead_press` | Overhead Press | weight | external_load | medium | gym |
| `band_external_rotation` | Band External Rotation | resistance_band | bodyweight_only | low | home |
| `dumbbell_bench_press` | Dumbbell Bench Press | dumbbell | external_load | medium | home |
| `face_pull` | Face Pull (Band) | resistance_band | external_load | low | home |
| `lateral_raise` | Lateral Raise | dumbbell | external_load | low | home |
| `scapular_pullup` | Scapular Pull-up | pullup_bar | bodyweight_only | low | home |

### core
Exercises found: **30** (bw=20 home=10 gym=0)
Equipment combos: `[—, pullup_bar, resistance_band]`
Bodyweight-only count: **20**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `ab_wheel_rollout` | Ab Wheel Rollout | — | bodyweight_only | medium | bodyweight |
| `bear_crawl` | Bear Crawl | — | bodyweight_only | low | bodyweight |
| `copenhagen_plank` | Copenhagen Plank | — | bodyweight_only | medium | bodyweight |
| `core_hollow_hold` | Hollow Body Hold | — | bodyweight_only | medium | bodyweight |
| `core_l_sit` | L-Sit (Floor) | — | bodyweight_only | medium | bodyweight |
| `dead_bug` | Dead Bug | — | bodyweight_only | low | bodyweight |
| `farmers_carry` | Farmer's Carry | — | external_load | medium | bodyweight |
| `freestanding_handstand_practice` | Freestanding Handstand Practice | — | bodyweight_only | medium | bodyweight |
| `handstand_pushup_wall` | Handstand Push-up (Wall) | — | bodyweight_only | high | bodyweight |
| `handstand_shoulder_taps` | Handstand Shoulder Taps (Wall) | — | bodyweight_only | high | bodyweight |
| `hip_flexor_strengthening` | Hip Flexor Strengthening | — | bodyweight_only | low | bodyweight |
| `kneeling_superman` | Bird-Dog (Kneeling Superman) | — | bodyweight_only | low | bodyweight |
| `plank` | Plank | — | bodyweight_only | low | bodyweight |
| `plank_shoulder_tap` | Plank Shoulder Tap | — | bodyweight_only | low | bodyweight |
| `side_plank` | Side Plank | — | bodyweight_only | medium | bodyweight |
| `suitcase_carry` | Suitcase Carry | — | total_load | medium | bodyweight |
| `turkish_getup` | Turkish Get-up | — | external_load | medium | bodyweight |
| `v_up` | V-Up | — | bodyweight_only | medium | bodyweight |
| `wall_handstand_hold` | Wall Handstand Hold (Belly-to-Wall) | — | bodyweight_only | medium | bodyweight |
| `wall_walk_up` | Wall Walk-up | — | bodyweight_only | medium | bodyweight |
| `front_lever_one_leg` | Front Lever (One Leg Extended) | pullup_bar | bodyweight_only | high | home |
| `front_lever_straddle` | Front Lever (Straddle) | pullup_bar | bodyweight_only | high | home |
| `front_lever_tuck` | Front Lever (Tuck Progression) | pullup_bar | bodyweight_only | high | home |
| `hanging_leg_raise` | Hanging Leg Raise | pullup_bar | bodyweight_only | medium | home |
| `knees_to_elbows` | Knees to Elbows (Hanging) | pullup_bar | bodyweight_only | medium | home |
| `l_sit_pullup` | L-Sit Pull-up | pullup_bar | bodyweight_only | high | home |
| `lock_off_isometric` | Lock-off Isometric (Multi-Angle) | pullup_bar | bodyweight_only | high | home |
| `pallof_press` | Pallof Press (Anti-Rotation) | resistance_band | bodyweight_only | medium | home |
| `toes_to_bar` | Toes to Bar | pullup_bar | bodyweight_only | high | home |
| `windshield_wipers` | Windshield Wipers (Hanging) | pullup_bar | bodyweight_only | high | home |

### glutes
Exercises found: **7** (bw=4 home=0 gym=3)
Equipment combos: `[—, weight]`
Bodyweight-only count: **4**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `glute_bridge` | Glute Bridge | — | bodyweight_only | low | bodyweight |
| `nordic_curl` | Nordic Hamstring Curl | — | bodyweight_only | medium | bodyweight |
| `pistol_squat_progression` | Pistol Squat Progression (Chair → Full) | — | bodyweight_only | medium | bodyweight |
| `reverse_lunge` | Reverse Lunge | — | bodyweight_only | moderate | bodyweight |
| `goblet_squat` | Goblet Squat | weight | external_load | medium | gym |
| `romanian_deadlift` | Romanian Deadlift (RDL) | weight | external_load | medium | gym |
| `split_squat` | Split Squat (Single-leg) | weight | external_load | medium | gym |

### hips
Exercises found: **1** (bw=1 home=0 gym=0)
Equipment combos: `[—]`
Bodyweight-only count: **1**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `hip_flexor_strengthening` | Hip Flexor Strengthening | — | bodyweight_only | low | bodyweight |

**⚠️ MVP blocker.** See Task 2 for catalog expansion proposal.

### legs
Exercises found: **8** (bw=5 home=0 gym=3)
Equipment combos: `[—, weight]`
Bodyweight-only count: **5**

| exercise_id | name | equipment_required | load_model | intensity_level | tier |
|---|---|---|---|---|---|
| `nordic_curl` | Nordic Hamstring Curl | — | bodyweight_only | medium | bodyweight |
| `pistol_squat_progression` | Pistol Squat Progression (Chair → Full) | — | bodyweight_only | medium | bodyweight |
| `reverse_lunge` | Reverse Lunge | — | bodyweight_only | moderate | bodyweight |
| `single_leg_calf_raise` | Single Leg Calf Raise | — | bodyweight_only | low | bodyweight |
| `step_ups` | Step-Ups (Weighted) | — | external_load | medium | bodyweight |
| `goblet_squat` | Goblet Squat | weight | external_load | medium | gym |
| `romanian_deadlift` | Romanian Deadlift (RDL) | weight | external_load | medium | gym |
| `split_squat` | Split Squat (Single-leg) | weight | external_load | medium | gym |

<!-- END_CATEGORY_TABLES -->

---

## Appendix B — Excluded exercises (by reason)

Total excluded: **88** (53 test/warmup/cooldown/technique-only, 35 climbing-surface/board, 20 flexibility — some overlap counted once).

- **Climbing-surface exercises (35)** — correctly excluded; they're session-type exercises, not body-part strength work. Examples: `arc_training`, `limit_bouldering`, `four_by_four_bouldering`, `route_intervals`, `campus_bumps`, `board_limit_boulders`.
- **Flexibility v2 (20)** — excluded per brief's strength-only scope. Examples: `hip_opener_flow`, `cooldown_hip_pigeon`, `forearm_stretches`, `active_hip_mobility`, `flexibility_cossack_squat`.
- **Test/warmup/cooldown/technique-only (33)** — exercises with no strength role. Examples: `finger_warmup_generic`, `silent_feet_drill`, `dead_hang_easy`, `general_pulse_raise`, `dynamic_mobility_flow`.

Full list (with reason tags) saved to `/tmp/d217_excluded.json` (not committed; re-runnable by the classifier).

---

## STOP

This is a D-type (read-only) brief.

- Nothing has been implemented.
- No files modified except this report.
- Waiting for Daniele's review + open-question decisions before spawning **A213** (implementation) and — if go-ahead — **C207** (hips catalog expansion).

Next step: Daniele reviews §9 (open questions), green-lights or adjusts the spec, and assigns A213.
