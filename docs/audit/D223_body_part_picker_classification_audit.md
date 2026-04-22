# D223 — Body Part Picker: main vs warmup classification audit

**Date:** 2026-04-22
**Scope:** Read-only. Investigate why a warmup exercise (`finger_warmup_generic`) can be picked as a main-slot exercise inside a body-part block.
**Repro (user screenshot):** Home equipment, Fingers block → generator returned `finger warmup generic` (1×300s) + `finger recruitment pulls` (3×5 rest 45s). Both are catalog `role: ["warmup", "activation"]`, not `role: ["main"]`.

---

## TL;DR

**Two compounding root causes.**

1. **Primary (the target of this brief)** — `backend/engine/body_part_picker.py` does **NOT** use the catalog `role` field anywhere in the candidate-pool / selection pipeline. The only `role` filter in the codebase is the P0 hard filter in `resolve_session.py:454-461`, which is driven by block-template `role: [...]` entries and is never invoked by the light resolver. Consequence: every exercise whose body-part classification matches fingers (domain/pattern rules) is a valid candidate for the "main" slot, including `warmup`/`activation`/`prehab`/`test` roles.

2. **Secondary (discovered during the repro trace, out-of-scope for fix but worth flagging)** — `score_exercise()` in `resolve_session.py:875,886-888` uses `norm_str(None)` which returns the literal string `"none"` rather than `None`. When a user has no `preferences.preferred_grip` set (the default for users who only completed onboarding without customizing prefs), **every warmup/prehab exercise without `attributes.grip` in the catalog gets a phantom +5.0 bonus**, because both sides become `"none"` and the equality check passes. This actively ranks warmups ABOVE mains when the user has no grip preference. Daniele's local dev state (`preferences.preferred_grip=None`, no recent_sessions) triggers this exact condition.

The primary fix (enforce `role: "main"` filter in the light resolver) closes both symptoms in one stroke: even with the bonus bug still alive, warmups would no longer be in the candidate pool.

---

## Step 0 — Files

- `backend/engine/body_part_picker.py` — light resolver + body-part selection.
- `backend/catalog/exercises/v1/exercises.json` — the only file containing `finger_warmup_generic` and `finger_recruitment_pulls`.
- `backend/engine/resolve_session.py` — full resolver, `apply_P0_hard_filter` (role enforcement), `score_exercise` (scoring used by light resolver too).
- `backend/catalog/sessions/v1/finger_strength_home.json` — example session that delegates role filtering to block templates.
- `backend/catalog/templates/v1/finger_max_strength.json` — example template with `"role": ["main"]` on its main block.

---

## Step 1 — Fingers candidate pool inventory

Classification rules for Fingers are at `body_part_picker.py:50-71`:

```
domains:  finger_strength, finger_max_strength, finger_strength_endurance,
          finger_aerobic_endurance, contact_strength
patterns: isometric_hang, repeater_hang, grip_transition, isometric_lift,
          repeater_lift, isometric_explosive, explosive_brief
include_ids: pinch_block_training, power_slap_drill
```

Reconstructing `build_body_part_index()` yields **38 raw candidates** for the Fingers pool. After equipment filter for Home (user has `hangboard`): **27 candidates remain**.

| exercise_id | role | domain | pattern | intensity | equipment_required | hangboard_gate (D35) |
|---|---|---|---|---|---|---|
| active_finger_curls | prehab | prehab_finger | finger_extension | low | hangboard | no |
| dead_hang_easy | warmup | finger_strength | isometric_hang | low | hangboard | no |
| density_hangs | main | finger_strength | isometric_hang | high | hangboard | no |
| **finger_recruitment_pulls** | **warmup \| activation** | finger_strength | pull_vertical | low | hangboard | no |
| **finger_warmup_generic** | **warmup \| activation** | finger_strength | wrist_extension | low | — | no |
| grip_transitions_half_to_open | activation | finger_strength | grip_transition | high | hangboard | no |
| hang_rampup_progressive | warmup | finger_strength | isometric_hang | low | hangboard | no |
| hangboard_moving_hangs | main | finger_strength_endurance | isometric_hang | low | hangboard | no |
| horst_7_53 | main | finger_strength, finger_max_strength | isometric_hang | high | hangboard | no |
| intermittent_dead_hangs | main | finger_strength_endurance | isometric_hang | medium | hangboard | no |
| long_duration_hang | main | finger_strength, finger_max_strength | isometric_hang | medium | hangboard | no |
| long_interval_repeaters | main | finger_aerobic_endurance | isometric_hang | low | hangboard | no |
| lopez_subhangs | main | finger_strength, finger_max_strength | isometric_hang | medium | hangboard | no |
| lp_* (7 exercises) | — | — | — | — | loading_pin | — (dropped by home filter) |
| max_hang_10s | main | finger_strength, finger_max_strength | isometric_hang | high | hangboard | **yes** |
| max_hang_5s | main | finger_strength, finger_max_strength | isometric_hang | max | hangboard | **yes** |
| max_hang_7s | main \| test | finger_strength, finger_max_strength | isometric_hang | max | hangboard | **yes** |
| max_hang_ladder | main | finger_strength, finger_max_strength | isometric_hang | max | hangboard | **yes** |
| min_edge_hang | main | finger_max_strength | isometric_hang | max | hangboard | **yes** |
| one_arm_hang_assisted | main | finger_max_strength | isometric_hang | max | hangboard, band | **yes** (dropped by home) |
| overcoming_isometric_pull | main | finger_strength, finger_max_strength | isometric_hang | max | hangboard | no |
| pinch_block_training | main | finger_strength | isometric_hang | high | pinch_block | no (dropped by home) |
| repeater_15_15 | main | finger_aerobic_endurance | repeater_hang | medium | hangboard | no |
| repeater_hang_7_3 | main | finger_strength_endurance | repeater_hang | high | hangboard | no |
| repeater_sub_max_endurance | main | finger_strength_endurance | isometric_hang | medium | hangboard | no |
| rfd_explosive_pulls | main | contact_strength | isometric_explosive | max | hangboard | no |
| sub_max_capacity_hang | main | finger_strength_endurance | isometric_hang | medium | hangboard | no |
| test_max_hang_duration_20mm | test | — | isometric_hang | max | hangboard | no |
| test_repeater_7_3_to_failure | test | — | repeater_hang | medium | hangboard | no |
| warmup_repeaters_large | warmup | finger_strength | isometric_hang | very_low | hangboard | no |

**Home+hangboard pool role breakdown:** 17 pure `main`, 1 `main|test`, 2 `test`, 3 `warmup`, 2 `warmup|activation`, 1 `activation`, 1 `prehab`. **There is no pool-size scarcity** — 17 main exercises are available.

`hangboard_gate applies?` column refers to `_ADVANCED_HANGBOARD_IDS` at `resolve_session.py:436-445` (blocks max_hang_{5,7,10}s, max_hang_ladder, min_edge_hang, one_arm_hang_assisted for users with <2 years experience). **This gate is NOT applied in `body_part_picker.py`** — it only lives in `apply_P0_hard_filter`.

---

## Step 2 — `apply_resolver_light()` / `select_exercises_for_part()` selection logic

### 2.1 Pool construction — `build_body_part_index()` (lines 309-331)

```python
def build_body_part_index(catalog):
    index = {cat: set() for cat in BODY_PART_CATEGORIES}
    for ex in catalog:
        if _is_climbing_surface_exercise(ex):
            continue
        ex_id = ex.get("id")
        if not ex_id:
            continue
        for cat, meta in BODY_PART_CATEGORIES.items():
            if _match_category_raw(ex, meta["classification_rules"]):
                index[cat].add(ex_id)

    index["forearms"] -= index["fingers"]
    index["biceps"] -= index["forearms"]
    return index
```

Matching is via `_match_category_raw()` at lines 265-296:

```python
def _match_category_raw(exercise, rules):
    ex_id = exercise.get("id")
    if ex_id in rules.get("exclude_ids", []):
        return False
    ex_patterns = _ex_patterns(exercise)
    exclude_patterns = rules.get("exclude_patterns", [])
    if any(p in exclude_patterns for p in ex_patterns):
        return False
    if ex_id in rules.get("include_ids", []):
        return True
    ex_domain_list = _ex_domains(exercise)
    if any(d in rules.get("domains", []) for d in ex_domain_list):
        return True
    if any(p in rules.get("patterns", []) for p in ex_patterns):
        return True
    push_tokens = rules.get("push_name_match") or []
    if push_tokens and "push" in ex_patterns:
        name_lower = (exercise.get("name") or "").lower()
        if any(tok.lower() in name_lower for tok in push_tokens):
            return True
    return False
```

**`role` is never referenced.** Matching is purely on `id`, `domain`, `pattern`, `exclude_patterns`, `push_name_match`.

### 2.2 Filtering — `select_exercises_for_part()` (lines 458-493)

```python
def select_exercises_for_part(body_part, exercises_pool, equipment, already_selected,
                              user_state, n=N_PER_BODY_PART, seed=None):
    if body_part not in BODY_PART_CATEGORIES:
        return []
    by_id = {e["id"]: e for e in exercises_pool if "id" in e}
    index = build_body_part_index(exercises_pool)
    candidate_ids = index.get(body_part, set()) - already_selected
    candidates = [by_id[i] for i in candidate_ids if i in by_id]
    candidates = [c for c in candidates if _exercise_fits_equipment(c, equipment)]
    if not candidates:
        return []
    ...
```

Only two filters:
1. `- already_selected` — soft de-dup across body parts within the same session.
2. `_exercise_fits_equipment()` — hard equipment filter (line 396: `req = exercise.get("equipment_required") ...`).

**No filter on `role`. No filter on `intensity_level`. No D35 hangboard experience gate. No age gate.**

### 2.3 Ranking / picking — continuing `select_exercises_for_part()`

```python
    prefs = (user_state.get("preferences") or {})
    recent_ids = _recent_exercise_ids(user_state)
    recent_groups = _recent_recency_groups(user_state)

    rng = random.Random(seed)
    scored = []
    for ex in candidates:
        base = score_exercise(ex, prefs, recent_ids, recent_groups)
        jitter = rng.random() * 0.1
        scored.append((base + jitter, ex))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [ex for _, ex in scored[:n]]
```

Scoring delegates to `resolve_session.score_exercise` (lines 842-890):
- Recency penalties on `exercise_id` (−30 / −15 / −5).
- B159b recency_group penalty (−15).
- `preferred_edge_mm` match → **+10**.
- `preferred_grip` match → **+5**.
- No `role`-based term.

The final pick is top-N by score + jitter (0.1 tiebreaker).

### 2.4 Role handling inside `body_part_picker.py` (`grep role`)

Only 2 hits in the entire module:

```
668:        winst["module_role"] = "warmup"
675:            inst["module_role"] = "main"
```

Both are **post-selection labels** in `generate_body_part_session()` — they tag the instance based on whether it came from the global warmup prepend (line 663-670, introduced by B218 Bug 4) or the body-part block (line 672-677). They do NOT read the catalog `role` field to inform selection.

### 2.5 N value

```python
N_PER_BODY_PART: int = 2      # line 36
```

Used as the default for `select_exercises_for_part(..., n=N_PER_BODY_PART)` (line 464) and the direct pass in `generate_body_part_session()` (line 652). It is **hardcoded** — no config, no per-category override.

---

## Step 3 — How the full resolver enforces `role: main`

### 3.1 P0 hard filter (the enforcement point)

`resolve_session.py:454-461` — Stage 3 of `apply_P0_hard_filter`:

```python
# Stage 3: role (ANY match)
base3 = base2
if role_set:
    base3 = []
    for e in base2:
        if not set(ex_roles(e)).isdisjoint(role_set):
            base3.append(e)
trace["counts"]["after_role"] = len(base3)
```

If the block asks for `role: ["main"]`, only exercises whose catalog `role` intersects `{main}` survive. `ex_roles()` is defined at lines 210-213 and reads both `role` and legacy `roles`.

### 3.2 The template declares `role: ["main"]`

`backend/catalog/templates/v1/finger_max_strength.json:175-180` (main block):

```json
{
  "block_id": "main",
  "type": "main_set",
  "selection": { ... },
  "prescription": { ... },
  "role": ["main"],
  "domain": ["finger_strength"],
  "pattern": ["isometric_hang"]
}
```

### 3.3 The resolver reads the block and passes `role_req`

`resolve_session.py:1441-1460`:

```python
# P0: hard-filter only selection based on v1 schema (role/domain/pattern)
role_req = b.get("role")   # P0 requires explicit block.role; block.type is NOT a selector input
...
if role_req is None:
    logger.warning(
        "resolve_session: block missing 'role' in template — block will be skipped (session=%s)",
        ...
    )
    chosen_by = "p0_missing_role"
    trace = {"counts": {}, "domain_filter_applied": None, "error": "Missing block.role (P0 requires role for selection)."}
...
else:
    ...
    ex = apply_P0_hard_filter(
        ...,
        role_req=role_req,
        ...
    )
```

**Session templates that forget `role` get skipped** by design. The full resolver treats role as mandatory structural input for selection.

The light resolver has **no equivalent** concept of "block.role → filter pool by catalog.role".

---

## Step 4 — Reproduction trace (Daniele, Home, Fingers)

User state (local dev, matches the screenshot scenario):
- `preferences = {"finger_training_device": ...}` — **no `preferred_edge_mm`, no `preferred_grip`**.
- `recent_sessions = []` — no recency penalties.
- `stimulus_recency = {}` — empty.
- Equipment = `["hangboard"]` (Home).

Walk-through of `select_exercises_for_part("fingers", ...)`:

1. **Pool construction** — `build_body_part_index(catalog)` returns 38 IDs for fingers. Cross-category subtractions (`forearms -= fingers`, `biceps -= forearms`) don't remove anything from fingers.
2. **Already selected** — empty set (fingers is first body-part in the session).
3. **Equipment filter** — drops 11 exercises (7 `lp_*` require `loading_pin`, `one_arm_hang_assisted` requires `hangboard + band`, `pinch_block_training` requires `pinch_block`, 1 outlier). Pool down to **27**.
4. **Scoring** — `score_exercise(ex, prefs, [], set())`:
   - No recency penalty.
   - No recency_group penalty.
   - `pref_edge = None` → no +10 bonus anywhere.
   - `pref_grip = norm_str(None) = "none"` (line 875, via `norm_str: str(x).strip().lower()` at `resolve_session.py:53-54`).
   - For each candidate: `ex_grip = norm_str(ex_attrs.get("grip"))`.
     - Exercises **without** `attributes.grip` get `ex_grip = "none"` → condition `pref_grip and ex_grip` passes (both are `"none"`, both truthy) → `"none" == "none"` → **+5.0**.
     - Exercises **with** `attributes.grip = "half_crimp"` get `ex_grip = "half_crimp"` → `"half_crimp" == "none"` → no bonus.
   - **Fingers pool verdict**: 5 exercises (`finger_warmup_generic`, `finger_recruitment_pulls`, `hang_rampup_progressive`, `warmup_repeaters_large`, `active_finger_curls`) end at **5.0**; all 22 others (including every `role: main` entry) end at **0.0**.
5. **Jitter** — adds [0, 0.1). Ordering among the 5.0 band is randomized; the 0.0 band never catches up.
6. **Top-2 picks** — both come from the 5.0 band. Warmup-family exercises win 100% of the time with this state.

Verified empirically: running `select_exercises_for_part` across seeds 0-9 returned **zero main exercises** in 20 picks.

**Root cause observation**: at no point does the code see `role: ["warmup"]` on `finger_warmup_generic` and treat it differently. The classification system and the scorer both operate on `domain`, `pattern`, `attributes`, and recency — never on `role`.

---

## Step 5 — Gap analysis

1. **Is `role` used as a filter in `apply_resolver_light()` / `select_exercises_for_part()`?**
   **No.** Zero references. The two `role` strings in `body_part_picker.py` (lines 668, 675) assign `module_role` to instances **after** selection and are unrelated to catalog role filtering.

2. **What would need to change for the light resolver to pick only `role: main`?**
   Add a role filter in `select_exercises_for_part()` between the equipment filter and the scoring step. Something shaped like:
   ```python
   candidates = [c for c in candidates if "main" in (c.get("role") or [])]
   ```
   (Exact wording + helper choice is implementation — not done here.)

3. **Fallback if filtered pool has <N mains?**
   Not currently an issue for fingers (17 mains at Home). Potential edge cases: Biceps bodyweight-only (home has no gym → small pool), Hips bodyweight-only. Proposed fallback order (to confirm during fix brief, not here):
   - Prefer `role: main`.
   - Allow `role: accessory` as secondary fill (explicitly present in catalog for `lp_repeater_lifts`).
   - Never fall back to `warmup`, `warmup|activation`, `activation`, `prehab`, or `test` — these have separate semantic meaning.
   - If still <N after `main + accessory`, return fewer exercises (e.g. 1 or 0) rather than polluting with warmup/test. The global warmup prepend (B218 Bug 4) already covers warmup duties.

4. **Is N=2 hardcoded?**
   Yes, at `body_part_picker.py:36`:
   ```python
   N_PER_BODY_PART: int = 2
   ```
   Single constant, no overrides, no config layer.

5. **Does the current code use `role` at all in the body-part selection path?**
   No. `grep -n role backend/engine/body_part_picker.py` → only lines 668 and 675 (post-selection instance tagging).

### Bonus finding — `norm_str(None) → "none"` bug in `score_exercise`

Strictly out-of-scope for the body-part-picker fix, but documented because the reproduction trace surfaced it. `resolve_session.py:875,886-888`:

```python
pref_grip = norm_str(prefs.get("preferred_grip"))   # None → "none"
ex_attrs = ex.get("attributes") or {}
ex_grip = norm_str(ex_attrs.get("grip"))            # None → "none"
if pref_grip and ex_grip:
    if ex_grip == pref_grip:
        s += 5.0
```

Users with no `preferred_grip` + exercises with no `attributes.grip` both get `"none"` and match → phantom +5.0 that disproportionately favors warmups/prehab (which usually don't declare a grip). Even if the body-part picker did everything else right, this quietly mis-ranks candidates elsewhere too. Worth filing as a separate low-risk bug after the body-part-picker fix lands (affects `pick_best_exercise` used by the full resolver fallback path as well).

---

## Step 6 — Out-of-scope sanity check

Fixing the primary finding requires changes **only** inside `backend/engine/body_part_picker.py`. No changes to:

- `resolve_session.py` — already correct; the full resolver enforces role.
- `planner_v2.py` / `replanner_v1.py` — not involved in body-part generation.
- Exercise catalog — every exercise in the pool already has a correct `role` field. No catalog edits required.
- Frontend UI — the fix is server-side; rendering layer consumes whatever the backend returns.
- Progression / closed-loop modules — body-part sessions bypass closed-loop (`build_kind="body_parts"` at `body_part_picker.py:10-12`).

The companion `norm_str(None)` bug fix (if pursued) would touch `resolve_session.py` and is called out as a separate follow-up, not part of this fix scope.

---

## Summary for the fix brief

| Finding | Severity | Location | Fix shape |
|---|---|---|---|
| Light resolver never filters candidate pool by catalog `role` | **Primary** | `body_part_picker.py:458-493` | Filter `candidates` to `"main" in (c.get("role") or [])` before scoring; decide fallback order if pool <N. |
| N_PER_BODY_PART hardcoded | Minor | `body_part_picker.py:36` | Leave as-is unless fallback logic demands per-category override. |
| `norm_str(None) == "none"` phantom bonus in `score_exercise` | Secondary | `resolve_session.py:875,886-888` | Separate brief — guard with `is not None` before stringifying, or short-circuit when `pref_grip is None`. |

No STOP gate needed for the fix brief itself (change is isolated to `body_part_picker.py`). Suggest Sonnet.
