# D257 — Audit: Adhoc Session Builder + Missing Loads (READ-ONLY)

**Type:** D (audit / read-only) · **Status:** ✅ Findings complete — no code changed
**Date:** 2026-07-22
**Scope:** Explain 4 field anomalies in a coach-generated adhoc session + sweep the catalog for loadable-but-loadless exercises.

> **This brief made no code changes.** All fixes are deferred to the follow-up briefs proposed at the end. Two of them are STOP-gated (high-risk modules).

---

## TL;DR

- **A1 + A2 share ONE root cause: the intent schema.** The whole adhoc pipeline is `1 chat turn → 1 LLM intent → 1 session`. The intent (`backend/coach/adhoc_intent.py`) can hold exactly **one** `equipment_set`, **one** `focus`, **one** optional `secondary_focus`, **one** `minutes`. It structurally cannot represent "two sessions" (A1) nor "chest/triceps/biceps/abs" muscle-level targets (A2 — the `focus` vocabulary has only 9 coarse values, none muscle-specific). The deterministic builder faithfully composes what the impoverished intent contains.
- **A3 is NOT a catalog bug.** Back Squat renders no kg simply because the user has never logged a Back Squat load. The adhoc builder sources load **only** from `working_loads` memory (`backend/engine/adhoc_prescription.py:68`); `load_kg` stays `0.0` when there is no direct entry. Bench Press / Barbell Row showed kg only because Daniele had logged them before. The three exercises are **identical** in the catalog (`load_model=external_load`, no numeric anchor field exists at all).
- **A3-EXTENDED:** there is no "load reference / 1RM anchor" field in the exercise catalog to be missing — the premise doesn't map. Instead, **all 68 loadable exercises (45 `external_load` + 23 `total_load`) render with blank kg in an adhoc session until the user logs each one at least once.** This is a uniform architectural gap, not a per-exercise / newest-batch omission.
- **A4:** `/week` and `/today` use the **same** `SessionCard`. The divergence is a single branch keyed on `session.is_custom`: normal sessions render the rich nested `resolved.…exercise_instances[]` (with `suggested{}` loads/grades and instruction blocks); custom/adhoc sessions render a flat `exercises[]` list with none of that.

---

## A1 — Two requests collapsed into one session

**Verdict: architectural limit (schema-level), not a builder bug and not a prompt-loss you can fix with wording.**

### The pipeline is 1→1→1

```
POST /api/coach/adhoc-session            (backend/api/routers/coach.py:81)
  → service.handle_adhoc_compose         (backend/coach/service.py:121)
      → adhoc_intent.extract_intent      (backend/coach/adhoc_intent.py:108)   ← LLM, forced single tool call
      → compose_adhoc_session            (backend/engine/adhoc_builder.py:248)  ← one session out
  → {adhoc: True, session: <one preview>}
```

### Where the second session is dropped

At **intent extraction**, not in the builder. The forced tool `extract_adhoc_intent` (`adhoc_intent.py:39-80`) has a **flat, single-session schema**:

```
is_adhoc_request, equipment_set, focus, secondary_focus, gym_name, minutes, energy
```

There is no array, no `sessions[]`, no second location/time slot. When the user asks for two sessions at two places/times, the LLM is forced to jam both into this one object — it cannot emit two. `extract_intent` returns a single flat dict (`adhoc_intent.py:118-125`), and `compose_adhoc_session` returns exactly one session dict (`adhoc_builder.py:432-451`).

**This is by design (A243 decision: "compose does NOT persist … returns a preview").** The single-session assumption is baked into the tool schema, the service handler, the builder signature, and the client payload (`AdhocSessionPreview`, `frontend/src/lib/api.ts:1065`). Rewording the prompt cannot fix it — there is nowhere for a second session to go.

**Root cause:** intent schema is single-session by construction. → shared with A2.

---

## A2 — Requested muscle groups ignored (squat + row instead of chest/abs/triceps)

**Verdict: catalog-compose (not template-pick), but the compose axis is too coarse to represent muscles. Same root as A1: the intent schema/vocabulary.**

### It composes, it does not pick a canned template

`compose_adhoc_session` builds the session live from the catalog (`adhoc_builder.py:293-406`): warmup → primary-focus block → optional secondary-focus block → core finisher, each filtered by equipment + spine-safety + phase affinity + recency. There is **no "general strength + core" stored template** returned as-is.

### Why the muscles were ignored

The composition axis is the **`focus`** slot, mapped to catalog domains by `FOCUS_DOMAINS` (`adhoc_builder.py:43-53`). The entire vocabulary is 9 coarse values:

```
fingers · pull · power · endurance · core · general_strength · technique · mobility · prehab
```

There is **no** `chest`, `triceps`, `biceps`, `abs`, `back`, `legs`. So "chest + abs + triceps" has no representable focus and the LLM falls back to the documented default `focus=general_strength` (`adhoc_intent.py:34-36`; builder default `adhoc_builder.py:269`).

`general_strength` → domain `strength_general` → `_candidates(...)` returns every `strength_general` exercise the equipment allows. Ranked by phase-affinity → not-recent → id (`_rank_key`, `adhoc_builder.py:117-126`), the top picks are compound barbell lifts: **Back Squat, Barbell Row, Bench Press** — none muscle-targeted, because the composer was never told a muscle. `secondary_focus=core` produced the Ab Wheel / Back Extension / Cable Woodchop block; biceps was lost entirely (no slot could carry it).

**A1 and A2 share one root cause:** the intent schema. It can hold neither a second session (A1) nor muscle-level targets (A2). Note the app *does* have muscle-level targeting elsewhere — `backend/engine/body_part_picker.py` and `/api/body-part-picker/*` — but the adhoc builder does not use it; it only consumes the coarse `focus`.

### Title / location / equipment mismatch (as flagged)

- The **title** `"Adhoc general strength + core (gym)"` comes from `equipment_set` (`adhoc_builder.py:434`): the LLM set `equipment_set=gym`, so the builder filtered to gym equipment (hence barbell movements) and titled it `(gym)`.
- The builder emits **no time-of-day and no location/slot field** — only `tags` and `equipment_set` (verified: `adhoc_builder.py:432-451`). The **"Home / Evening"** label is applied **client-side at insertion** into the week/day slot, downstream of the builder.
- Nothing reconciles `equipment_set` (drives title + equipment filter, here `gym`) with the slot the client dropped it into (`home/evening`). So a gym-equipment session with barbell lifts can be shown under a Home/Evening slot — divergence between builder equipment context and client placement, never cross-checked.

---

## A3 — Back Squat missing load (kg) while Bench Press / Barbell Row resolve

**Verdict: hypothesis (b) — the exercise is loadable but the user has no stored load for it. Hypotheses (a), (c), (d) rejected.**

### Exact cause — file + field

`backend/engine/adhoc_prescription.py:46-91`, function `propose_exercise_prescription`:

- Line **68**: `entry = _best_entry(user_state, exercise_id, {}, today, freshness_days=None)` — reads only the user's `working_loads.entries` for that exact `exercise_id`.
- Lines **71-80**: `load_kg` stays `0.0` unless `entry["last_external_load_kg"]` exists and is `> 0`.
- The builder copies it through verbatim: `_to_custom_exercise` → `"load_kg": float(load) if isinstance(load, (int,float)) else 0` (`adhoc_builder.py:199`).
- The frontend renders no kg when `load_kg == 0` (custom branch, `session-card.tsx:984`).

So: **Daniele had a `working_loads` entry for `bench_press` and `barbell_row` (logged previously) → kg shown. He had none for `back_squat` → `load_kg=0` → blank.** The load is 100% memory-based and "never invented" — this is the documented A242 invariant, not a defect.

### Why the other hypotheses are rejected

The three exercises are **identical** in all load-relevant catalog metadata:

| id | domain | category | load_model | intensity_level |
|----|--------|----------|-----------|-----------------|
| back_squat | strength_general | strength_accessory | external_load | medium |
| bench_press | strength_general | strength_accessory | external_load | medium |
| barbell_row | strength_general | strength_accessory | external_load | medium |

- **(a) "no load reference / 1RM anchor in catalog"** — rejected: **no such field exists in the schema for any exercise.** The full catalog key set has no per-exercise numeric load/1RM/weight anchor. `load_model` classifies *how* load applies (`external_load` = user supplies weight), it carries no value.
- **(c) "builder never called load resolution"** — rejected: `_to_custom_exercise` calls `propose_exercise_prescription` for every exercise (`adhoc_builder.py:179`).
- **(d) "catalog metadata mismatch"** — rejected: back_squat's metadata is byte-for-byte equivalent to bench_press/barbell_row on every load field.

### Secondary observation

Even the planned path's cross-exercise fallback couldn't have rescued Back Squat: `back_squat` is **not a member of any `_SIMILARITY_GROUPS`** (`progression_v1.py:66-79` — the `squat` group is `split_squat` + `goblet_squat` only). And the adhoc builder doesn't call that fallback anyway (it uses `_best_entry` directly, not `_similar_exercise`).

---

## A3-EXTENDED — Sweep for loadable-but-loadless exercises (highest-value output)

**Reframed premise:** the brief expected "newer exercises added without a load reference/1RM anchor." **That field does not exist** — no exercise has a numeric load anchor. Load for adhoc sessions comes exclusively from user `working_loads` memory. Therefore **every loadable exercise renders blank kg in an adhoc session until the user logs it at least once.** This is uniform and architectural, not a newest-batch omission — git archaeology on individual exercises is moot because the mechanism is identical for all of them.

### The full loadable set (68 exercises)

- **45 `external_load`** (user supplies barbell/dumbbell/cable/pin weight)
- **23 `total_load`** (bodyweight + added weight — weighted hangs, weighted pull-ups/dips, carries)
- (146 `bodyweight_only` correctly show no kg; 40 `grade_relative` are grade-based, not kg.)

All 68 render `load_kg=0` (blank) in an adhoc session with no prior direct log. Only **6** appear in a `_SIMILARITY_GROUPS` donor pair — and even those are not rescued by the adhoc path (which never calls the similarity fallback), only by the planned/progression path.

#### `external_load` (45)

| exercise_id | display_name | in similarity group |
|---|---|---|
| back_extension | Back Extension (Hyperextension) | no |
| **back_squat** | **Back Squat** | **no** |
| barbell_row | Barbell Row | yes |
| bench_press | Bench Press | yes |
| bicep_curl | Bicep Curl | no |
| cable_woodchop | Cable Woodchop (Anti-Rotation) | no |
| deadlift | Conventional Deadlift | no |
| dumbbell_bench_press | Dumbbell Bench Press | yes |
| dumbbell_external_rotation | Dumbbell External Rotation | no |
| dumbbell_fly | Dumbbell Fly | no |
| elbow_eccentric_curl | Elbow Eccentric Curl (Tyler Twist) | no |
| farmers_carry | Farmer's Carry | no |
| forearm_pronation_supination | Forearm Pronation/Supination | no |
| goblet_squat | Goblet Squat | yes |
| hammer_curl | Hammer Curl | no |
| heavy_reverse_wrist_curl | Heavy Reverse Wrist Curl | no |
| lateral_raise | Lateral Raise | no |
| leg_curl | Leg Curl (Machine) | no |
| leg_extension | Leg Extension (Machine) | no |
| lp_density_lifts | Loading Pin Density Lifts | no |
| lp_duration_test | Loading Pin Duration Test (20mm) | no |
| lp_max_lift_10s | Loading Pin Max Lift (10s) | no |
| lp_max_lift_5s | Loading Pin Max Lift (5s) | no |
| lp_max_lift_7s | Loading Pin Max Lift (7s) | no |
| lp_max_test_5s | Loading Pin Max Test (5s) | no |
| lp_repeater_lifts | Loading Pin Repeater Lifts | no |
| lp_repeater_test | Loading Pin Repeater Test (7/3) | no |
| lp_short_lifts | Loading Pin Short Lifts (Recruitment) | no |
| overhead_press | Overhead Press | no |
| overhead_tricep_extension | Overhead Tricep Extension | no |
| pallof_press | Pallof Press (Anti-Rotation) | no |
| reverse_barbell_curl | Reverse Barbell Curl | no |
| reverse_wrist_curl | Reverse Wrist Curl (Extension) | no |
| romanian_deadlift | Romanian Deadlift (RDL) | no |
| skullcrusher | Lying Triceps Extension (Skullcrusher) | no |
| split_squat | Split Squat (Single-leg) | yes |
| standing_calf_raise_loaded | Loaded Standing Calf Raise | no |
| step_ups | Step-Ups (Weighted) | no |
| triceps_cable_pushdown | Triceps Cable Pushdown | no |
| turkish_getup | Turkish Get-up | no |
| weighted_hanging_leg_raise | Weighted Hanging Leg Raise | no |
| weighted_plank | Weighted Plank | no |
| wrist_curl | Wrist Curl (Flexion) | no |
| wrist_roller | Wrist Roller | no |

#### `total_load` (23)

| exercise_id | display_name |
|---|---|
| density_hangs | Density Hangs (Tyler Nelson) |
| hangboard_moving_hangs | Hangboard Moving Hangs (HMH) |
| horst_7_53 | Hörst 7-53 Protocol |
| intermittent_dead_hangs | Intermittent Dead Hangs |
| long_duration_hang | Long Duration Hang (Tendon Health) |
| long_interval_repeaters | Long-Interval Repeaters |
| lopez_subhangs | López Submaximal Hangs |
| max_hang_10s | Max Hang 10s (Hypertrophy) |
| max_hang_5s | Max Hang (5s) |
| max_hang_7s | Max Hang (7s) |
| max_hang_ladder | Bechtel 3-6-9 Ladder |
| one_arm_hang_assisted | One-Arm Hang (Assisted) |
| pinch_block_training | Pinch Block Training |
| repeater_15_15 | Repeater Hang 15/15 (IntHangs) |
| repeater_hang_7_3 | Hangboard Repeaters 7/3 (Strength-Endurance) |
| repeater_sub_max_endurance | Sub-Max Repeaters (Endurance Variant) |
| sub_max_capacity_hang | Sub-Max Capacity Hang |
| suitcase_carry | Suitcase Carry |
| test_repeater_7_3_to_failure | Repeater Test 7/3 (To Failure) |
| weighted_chinup | Weighted Chin-up |
| weighted_dip | Weighted Dip |
| weighted_pullup | Weighted Pull-up |
| wide_pinch_extended_wrist_hold | Wide Pinch + Extended Wrist Hold |

**Would-render-kg? = would render kg only if the user has a direct `working_loads` entry for that exact id.** For a fresh user, all 68 render blank in an adhoc session. Contrast: the **planned** path (`resolve_session` + `progression_v1`) can anchor loads without prior logging via `%`-of-max, grade offsets, pulling baselines, and the B90 similarity transfer — which is exactly the capability the adhoc builder lacks.

---

## A4 — Custom vs normal sessions render differently in Week/Today

**Verdict: frontend — one shared component, one `is_custom` branch, two data shapes.**

### The two render paths (actually one component)

`/week` (`week/page.tsx:826`) and `/today` (`today/page.tsx:1241`) both render `<DayCard>` → `<SessionCard>` (`frontend/src/components/training/session-card.tsx:632`). There is no separate week-card vs today-card — the divergence is entirely inside `SessionCard`, keyed on the boolean **`session.is_custom`** (`frontend/src/lib/types.ts:110`). Custom sessions also short-circuit `sessionResolutionState(...)` to `"ok"` and never touch the resolver (`session-card.tsx:679-684`).

### The diverging data shape

- **Normal (planned):** rich nested payload under `session.resolved.resolved_session.exercise_instances[]` + `.blocks[]` (`session-card.tsx:699-702, 1014-1095`). Each `ResolvedExerciseInstance` (`types.ts:207`) carries `prescription{}`, **`suggested{}`** (`suggested_external_load_kg`, `suggested_total_load_kg`, `suggested_grade`, `load_source`, per-hand loads, boulder targets), `attributes{}`, `category`, `name`, `cues`, `video_url`, plus `instruction_only` warmup/mobility rows. Rendered through the full `<ExerciseCard>`.
- **Custom/adhoc:** **no `resolved` object at all** — a flat `session.exercises[]` of `CustomSessionExercise` (`types.ts:883-893`), rendered by the `is_custom` branch at `session-card.tsx:972-1013` as a thin inline list, not via `<ExerciseCard>`.

### Fields the custom card lacks (why it looks thinner)

`CustomSessionExercise` has only `exercise_id, sets, reps, work_seconds, rest_between_sets_seconds, rest_between_reps_seconds, load_kg, notes, cues?`. Missing vs the resolved path:

- **`name`** — custom rows de-underscore `exercise_id` (`session-card.tsx:990`) instead of a proper resolved name.
- **`suggested{}` entirely** — no coach-suggested/adaptive load, no `suggested_grade`/boulder target, no `load_source`. The custom row shows only raw `load_kg` (blank when 0 — see A3).
- **No `blocks` / `instruction_only`** — no warmup/mobility instruction rows or module grouping.
- **No `prescription.tempo`, no per-hand (unilateral) load, no `category`/test treatment.**
- **Duration badge** — the "~N min" badge reads `resolved.session.target_duration_min` (`session-card.tsx:903`), which custom sessions lack; their top-level `target_duration_min` (`types.ts:115`) isn't read there, so custom cards usually omit the badge.

---

## Recommended follow-up briefs (prioritized — DO NOT implement here)

1. **[A — high value, LOW risk] Muscle-level focus for the adhoc builder.**
   Extend the intent `focus` vocabulary (or add a `muscle_targets[]` slot) and route it through the existing `body_part_picker` targeting instead of the coarse `FOCUS_DOMAINS`. Fixes A2 directly. Isolated to `adhoc_intent.py` + `adhoc_builder.py` + prompt. **Not STOP-gated** (does not touch planner/replanner/resolve_session/progression).

2. **[A — high value, LOW risk] Multi-session adhoc intent.**
   Make the extraction tool emit `sessions[]` and have `handle_adhoc_compose` loop `compose_adhoc_session` per element, returning a list of previews. Fixes A1. Touches `adhoc_intent.py`, `coach/service.py`, `adhoc_builder` caller, `coach.py` router, and the client `AdhocSessionPreview` shape (frontend → branch + preview verification per B196). **Not STOP-gated**, but frontend-touching → branch + Vercel preview.

3. **[A/B — high value, ⚠️ STOP-GATED] Anchor adhoc loads for unlogged external_load / total_load exercises.**
   Give the adhoc builder a real starting load when memory is empty — reuse `progression_v1` estimators (%-of-max, `_similar_exercise`/B90 transfer, pulling baselines) instead of falling to 0. Fixes A3 + A3-EXTENDED for all 68 exercises. **This reads/reuses `progression_v1` and possibly `resolve_session` load logic → mandatory Phase-0 analysis + STOP gate.** Also worth: add `back_squat` (and other common lifts) to `_SIMILARITY_GROUPS` so the transfer has a donor.
   - Cheaper interim (LOW risk, B): if no anchor, render a "no target — tap to set" affordance in the custom card instead of a blank/absent kg, so a `load_kg=0` reads as "unset" not "bodyweight".

4. **[B — LOW risk, frontend] Custom-session card parity.**
   Enrich the `is_custom` branch in `session-card.tsx` to show the duration badge (from top-level `target_duration_min`) and, once brief #3 lands, the suggested load. Fixes A4's visible thinness. Frontend-only → branch + preview.

5. **[B — LOW risk] Reconcile adhoc `equipment_set` with the client insertion slot.**
   Surface/settle the title-vs-location mismatch (gym-equipment session dropped into a Home/Evening slot). Small; frontend + a note on the builder's emitted metadata.

**Suggested order:** #1 and #2 first (pure adhoc, no STOP gate, biggest UX win), then #3 (STOP-gated, needs Daniele's OK on the analysis), then #4/#5 cleanup.
