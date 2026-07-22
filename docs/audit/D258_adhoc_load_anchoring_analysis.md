# D258 — Phase 1 Analysis: Anchor Adhoc Load Proposals via progression_v1 (STOP-GATED)

**Type:** D→A (this doc = Phase 1, read-only). Becomes **A253** if Phase 2 is approved.
**Risk:** HIGH — reuses `progression_v1` load-anchoring inside the adhoc path.
**Date:** 2026-07-22 · **Status:** ⏸️ STOP — awaiting Daniele's OK before any code.
**Accepted corrections (from review):** (1) crude fallbacks `PCT_BW`/`FIXED_KG` never surface as a proposal → empty field; (2) reconcile with A242, boundary "computed-from-max ≠ invented"; (3) Phase 2 scoped to genuine anchors only.

> **No code was written.** This is the analysis + coverage table. Phase 2 does not start without explicit approval.

---

## TL;DR

- The planned path's load intelligence lives in **`inject_targets(resolved_day, user_state)`** (`progression_v1.py:920`). It is **already caller-safe** — line 922 does `user_state = deepcopy(user_state)` before anything, so it never mutates the caller's state. But it operates on a whole `resolved_day` and, on its copy, calls `estimate_missing_baselines` (line 923) which *would* fabricate grade-estimated baselines.
- The **per-exercise anchor helpers** it delegates to — `_transfer_load`, `_hangboard_suggested`, `_loading_pin_suggested`, `_max_hang_suggested`, `_get_pulling_baseline`, `_best_entry` — are **pure reads** of `user_state` (verified: no `user_state[...] =`, no `setdefault`; `_best_entry` was made non-mutating in A242). Safe to call from adhoc.
- There is a **clean discriminator already in the code**: the `load_source` tag. Genuine anchors set `load_source ∈ {transferred, baselines.pulling, working_loads}` (external) or leave it unset-but-real for hangboard/lp when a **test** baseline exists. Crude fallbacks (`FIXED_KG`, `PCT_BW`) set **no** `load_source`; grade/BW estimates set `load_source="estimated"`. Correction #1 = surface a proposal **only** when `load_source` is genuine.
- **Coverage is narrow and — critically — misses the audit's pain point.** Of the 68 loadable exercises, only **~8 have an unconditional genuine anchor** (barbell_row, face_pull, weighted_pullup/chinup/dip via `baselines.pulling`; +3 conditional transfer: bench_press, dumbbell_bench_press, goblet_squat). ~17 hangboard total_load exercises anchor **only if the user has a real hangboard test baseline** (finger sessions). **Every plain barbell/dumbbell accessory — back_squat, deadlift, curls, presses, raises, leg machines — stays EMPTY** under correction #1, because their sole "anchor" is the misleading `0.15×bodyweight`. Back Squat, the exercise that triggered the whole audit, is in this empty bucket.
- **Recommendation:** the honest incremental value of Phase 2 over B298 is small and concentrated on **finger/hangboard + weighted-pull** work — not the general-strength barbell sessions where the pain was. Ship it only if finger/pull adhoc sessions are a real use-case; otherwise B298's honest-empty field already covers ~90% of the value. If we do it: **thin adapter (Option A′)**, reusing the pure helpers, gated on genuine `load_source`, never calling `inject_targets`/`estimate_missing_baselines`.

---

## Phase 1 — the 7 questions

### 1. Extraction point — what inputs does the anchor need, and where do they live?

Anchors are computed from **`user_state.baselines`** (populated at onboarding/assessment by `estimate_missing_baselines`) plus per-exercise constants:

| Anchor kind | Input (in `user_state`) | Constants | Helper |
|---|---|---|---|
| Hangboard / finger `total_load` | `baselines.hangboard[0].max_total_load_kg` (+ `_get_bodyweight`) | `HANGBOARD_DEFAULT_INTENSITY_PCT` | `_hangboard_suggested` (`:658`), `_max_hang_suggested` (`:636`) |
| Loading-pin finger lifts | `baselines.loading_pin[].max_load_kg` (per hand); else hangboard-conversion | `LOADING_PIN_DEFAULT_INTENSITY_PCT` | `_loading_pin_suggested` (`:703`) |
| Weighted pull / row / face_pull | `baselines.pulling.max_external_load_kg` | `PULLING_EXTERNAL_SCALING`, `PULLING_1RM_PCT` | inline (`:1094-1101`), `_get_pulling_baseline` (`:277`) |
| Similarity transfer | a **donor**'s `working_loads.next_external_load_kg` | `_SIMILARITY_GROUPS` | `_transfer_load` (`:569`) |
| Grade fallback (hangboard) | `assessment.grades.redpoint_french` | `_FINGER_BENCHMARK` | inside `_hangboard_suggested` → tagged `estimated` |
| **Crude fallbacks** | `_get_bodyweight` only | `EXTERNAL_LOAD_FALLBACK_PCT_BW` (default 0.15), `EXTERNAL_LOAD_FALLBACK_FIXED_KG` | inline (`:1091-1109`) |

Decision order for `external_load` (bilateral), from `inject_targets` (`:1064-1116`):
`working_loads` → `_transfer_load` → `FIXED_KG` → `PULLING_EXTERNAL_SCALING`(needs pulling baseline) → `PCT_BW 0.15`.

### 2. Reusability — can the anchoring be called in isolation?

**Yes, at the helper level.** `_transfer_load`, `_hangboard_suggested`, `_loading_pin_suggested`, `_max_hang_suggested`, `_get_pulling_baseline` each take `user_state` + a `prescription` dict and return a suggestion dict. They do **not** depend on macrocycle phase, week plan, or closed-loop state (the phase only affects `PULLING_1RM_PCT` selection, which the crude/pulling branch reads from a passed `phase_id`; the adhoc composer already knows the current phase). They can be called standalone.

**The full `inject_targets` is *also* isolatable** (it deepcopies state), but it expects a `resolved_day` structure and pulls in `estimate_missing_baselines` — heavier and it fabricates grade-estimated baselines we then must discard.

### 3. Purity / side effects

- **Helpers: pure.** Grep for `user_state[` inside `:636-752` → none. No `setdefault`. `_best_entry` (`:541`) is non-mutating by A242's explicit design.
- **`inject_targets`: caller-safe but self-mutating on a copy.** `:922 user_state = deepcopy(user_state)` then `:923 estimate_missing_baselines(user_state)` mutates the **copy** only. The caller's `user_state` is untouched. So even Option B does not violate read-only — but it does compute grade-estimated baselines internally.
- **`estimate_missing_baselines` (`:755`): MUTATES in-place.** Must **never** be called by the adhoc path on the real state. Callers today: onboarding, assessment (legit, post-test), and `inject_targets` (on its copy). Adhoc must not add a fourth call site.

**Verdict:** the adhoc adapter must call only the pure helpers on the real `user_state`, reading `baselines` as already persisted. It must not call `inject_targets` or `estimate_missing_baselines` directly on caller state.

### 4. Immutability guarantee

Nothing in the pure-helper path regenerates or edits sessions — they compute a number from `baselines`/`working_loads` and return it. They touch neither `week_plans`, nor completed sessions, nor progression memory (no `apply_feedback`, no `_find_working_load_entry` write). Confirmed: proposing a load is a **read**. (The only write remains the user's own log on the CTA, which already flows through B298's `apply_feedback` path — unchanged.)

### 5. Coverage — the 68 loadable exercises

Verdict legend: **GENUINE** = surfaces a proposal (computed-from-max, per correction #2). **CONDITIONAL** = genuine only when a transfer donor is logged. **BASELINE-DEP** = genuine only if the user has a *real test* hangboard/lp baseline (else `estimated` → EMPTY). **EMPTY** = crude-only, stays empty per correction #1. **TEST** = test-role, excluded from adhoc composition anyway.

| load_model | id | Phase-2 verdict |
|---|---|---|
| external_load | barbell_row | **GENUINE** (baselines.pulling) |
| external_load | face_pull | **GENUINE** (baselines.pulling) |
| total_load | weighted_pullup | **GENUINE** (baselines.pulling) |
| total_load | weighted_chinup | **GENUINE** (baselines.pulling) |
| total_load | weighted_dip | **GENUINE** (baselines.pulling) |
| external_load | bench_press | CONDITIONAL (transfer donor) |
| external_load | dumbbell_bench_press | CONDITIONAL (transfer donor) |
| external_load | goblet_squat | CONDITIONAL (transfer donor) |
| total_load | density_hangs, hangboard_moving_hangs, horst_7_53, intermittent_dead_hangs, long_duration_hang, long_interval_repeaters, lopez_subhangs, max_hang_10s, max_hang_ladder, one_arm_hang_assisted, pinch_block_training, repeater_15_15, repeater_hang_7_3, repeater_sub_max_endurance, sub_max_capacity_hang, wide_pinch_extended_wrist_hold | BASELINE-DEP (hangboard test) |
| total_load | suitcase_carry | BASELINE-DEP\* (mis-tagged: a carry, not a hang — would read hangboard baseline; treat EMPTY) |
| external_load (uni) | lp_density_lifts, lp_max_lift_5s, lp_max_lift_7s, lp_max_lift_10s, lp_repeater_lifts, lp_short_lifts | BASELINE-DEP (loading_pin test) |
| external_load (uni) | lp_duration_test, lp_max_test_5s, lp_repeater_test | TEST (excluded from adhoc) |
| total_load | max_hang_5s, max_hang_7s, test_repeater_7_3_to_failure | TEST (excluded from adhoc) |
| external_load (uni) | split_squat | **EMPTY** (caveat: unilateral leg mis-routed through the finger loading-pin branch → nonsense/0; force empty) |
| external_load | back_squat, deadlift, romanian_deadlift, overhead_press, bicep_curl, hammer_curl, reverse_barbell_curl, skullcrusher, overhead_tricep_extension, triceps_cable_pushdown, lateral_raise, dumbbell_fly, leg_curl, leg_extension, standing_calf_raise_loaded, step_ups, farmers_carry, turkish_getup, back_extension, cable_woodchop, weighted_hanging_leg_raise, weighted_plank, heavy_reverse_wrist_curl, wrist_roller | **EMPTY** (PCT_BW 0.15 — crude) |
| external_load | elbow_eccentric_curl, forearm_pronation_supination, pallof_press, reverse_wrist_curl, wrist_curl | **EMPTY** (FIXED_KG — crude prehab) |

**Realistic adhoc tally** (excluding TEST role, which the composer never picks):
- **~5 unconditional GENUINE** that plausibly appear in a general/pull adhoc session: `barbell_row`, `face_pull`, `weighted_pullup`, `weighted_chinup`, `weighted_dip`.
- **+3 CONDITIONAL** (transfer): `bench_press`, `dumbbell_bench_press`, `goblet_squat` — only when the user has logged a group donor.
- **~16 BASELINE-DEP hangboard + ~6 lp** — genuine only inside a **finger** adhoc session *and* only if a real finger test baseline exists.
- **~30 EMPTY** — the entire plain barbell/dumbbell accessory set, including **back_squat** (the audit's trigger).

### 6. Fallback contract (correction #1, made precise)

Surface a pre-filled proposal **iff** the resolved suggestion carries a genuine `load_source`:
- external: `load_source ∈ {transferred, baselines.pulling}` (or `working_loads`, already handled by A242's memory read).
- total_load / hangboard / lp: a suggestion whose `load_source` is **not** `"estimated"`/`"grade_fallback"` **and** backed by a baseline whose `source == "test"` (not a grade-estimate written by `estimate_missing_baselines`).

Otherwise → **no proposal, empty editable field** (B298 behavior). Never surface `FIXED_KG`, `PCT_BW`, grade-estimated, or hangboard-conversion-from-nothing values. This is the boundary for correction #2: a %-of-a-real-max is *computed*; `0.15×BW` is *invented*.

### 7. Risk assessment + recommended shape

**Option A′ — thin adapter in `adhoc_prescription.py` (RECOMMENDED, smallest blast radius).**
Extend A242's `propose_exercise_prescription` with an anchor fallback that, when `working_loads` memory is absent, dispatches by `load_model` to the **existing pure helpers** and returns the value **only** if `load_source` is genuine (§6). Reuses the actual anchor math (tables + helpers) — only the ~15-line dispatch/gate is new. No call to `inject_targets`/`estimate_missing_baselines`. Reads `baselines` as persisted. Drift risk: low (math is reused; only decision order is mirrored, and it mirrors `:1064-1116`).
- *Pro:* no state mutation, no deepcopy cost, honors correction #1 by construction (never reaches the crude branches), reconciles cleanly with A242 (it's the same module).
- *Con:* mirrors the decision-order (~15 lines) rather than importing it → a future re-order of `:1064-1116` must be echoed. Mitigate with a test that pins parity against `inject_targets` for a genuine-anchor exercise.

**Option B — reuse `inject_targets` on a synthetic 1-exercise `resolved_day`.**
Zero logic duplication (calls the real pipeline), and it is caller-safe (deepcopies). But it fabricates grade-estimated baselines internally (discarded by the §6 gate), is heavier (deepcopy of full state per proposal), and is a fake-resolved_day hack. Prefer only if we want *zero* drift and accept the cost.

**Recommendation:** **Option A′**, scoped (correction #3) to the genuine buckets only, plus the `split_squat` caveat forced to empty. Estimated size: ~1 helper + gate in `adhoc_prescription.py`, wire into `_to_custom_exercise`'s `load_kg` prefill (adhoc_builder), + tests. `progression_v1` **not modified** (read-only reuse).

---

## Decision for Daniele (STOP gate)

Two real options, given coverage:

- **(a) Ship Phase 2 (Option A′)** — genuine value for finger/hangboard + weighted-pull adhoc sessions (~8 unconditional + finger sessions). Back Squat & the barbell bulk stay empty (honest). ~1 module change, read-only reuse, low risk.
- **(b) Don't ship — close A253 as won't-do.** B298 already delivers the loggable-empty-field minimum for 100% of loadable exercises; the genuine-anchor set (a) adds a nicety only where finger/pull baselines exist, which the audit's general-strength scenario didn't touch. Save the complexity.

My lean: **(a) only if finger/pull adhoc composition is a use-case you expect users to hit; otherwise (b).** The audit pain (Back Squat, no field) is already fixed by B298 — Phase 2 does not improve that case (correctly stays empty rather than inventing 12kg).

**No implementation until you pick (a) or (b).**

---

## Resolution (2026-07-22)

Daniele chose **(a), scoped to fingers/hangboard + weighted-pull**. Implemented as **A253** (Option A′, backend-only):
- New pure `anchor_adhoc_load(exercise, user_state, phase)` in `adhoc_prescription.py` — genuine anchor only for: hangboard `total_load` (% of a **test** max-hang baseline), `weighted_pullup` (% of pulling 1RM test), `barbell_row`/`face_pull` (pulling max-external × scaling). Gated on baseline `source ∈ {test, test_session}`; negative (counterweight) results suppressed → empty.
- Wired into `adhoc_builder._to_custom_exercise`: used **only when working_loads memory is absent** (memory always wins). The value flows through the existing `load_kg` → `suggested.externalLoadKg` prefill (B298), so no frontend change.
- Crude fallbacks (`PCT_BW`, `FIXED_KG`) and grade-estimated baselines are never surfaced → `back_squat` and the barbell/dumbbell bulk stay empty (B298). Read-only: verified no mutation of `user_state`/`baselines`/`working_loads`; `progression_v1` unchanged.
- Tests: `test_a253_adhoc_load_anchor.py` (12). Suite 2779 → 2791.
