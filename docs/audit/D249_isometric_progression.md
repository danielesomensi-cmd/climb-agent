# D249 — Isometric / Generic Exercise Progression Audit

**Type:** D (audit, read-only)
**Date:** 2026-06-26
**Status:** ✅ Done — findings only. Implementation deferred to a separate A-brief (STOP gate at end).
**Scope:** `closed_loop_v1.py`, `progression_v1.py`, `resolve_session.py`, feedback router, catalog (analysis only, NO writes).

> Read-only audit. No engine, catalog, state, or test file was modified. The only file created is this report.

---

## 1. One-line verdict

**NO.** Giving `easy` / `very_easy` feedback on **Side Plank** (or any `bodyweight_only` exercise) changes **nothing** in the next prescription.

**Single decisive reason:** `progression_v1.apply_feedback()` dispatches per-exercise feedback on `fb_load_model` through an `if/elif` chain that handles only `total_load`, `external_load`, and `grade_relative` — there is **no `bodyweight_only` branch and no `else`**, so the iteration computes `feedback_label` and then silently falls through to a no-op.

> `backend/engine/progression_v1.py:1439-1562`
> ```python
> if fb_load_model == "total_load":
>     ...
> elif fb_load_model == "external_load" and not fb_unilateral:
>     ...
> elif fb_load_model == "grade_relative" and exercise_id == "limit_bouldering":
>     ...
> elif fb_load_model == "external_load" and fb_unilateral:
>     ...
> # (no `elif "bodyweight_only"`, no `else`)
> ```

`side_plank` is `load_model: "bodyweight_only"` → matches none → discarded.

---

## 2. Feedback flow diagram (generic exercise, e.g. Side Plank)

```
[Frontend]
  feedback-dialog.tsx / guided-exercise-step.tsx
  → user picks one of 5 levels (very_easy|easy|ok|hard|very_hard)  ← all 5 shown, NO generic 3-level split
  → builds log_entry.actual.exercise_feedback_v1 = [{exercise_id:"side_plank", feedback:"easy", completed:true, ...}]
        │  POST /api/feedback   (FeedbackRequest {log_entry, resolved_day, status})
        ▼
[Endpoint]  backend/api/routers/feedback.py:78  post_feedback()
        │
        ├─ (2) apply_feedback(log_entry, state)        progression_v1.py:1409
        │        └─ loop over exercise_feedback_v1
        │             └─ fb_load_model = "bodyweight_only"  → NO matching branch → NO-OP
        │                 (feedback_label computed at :1428, then dropped)
        │        └─ no working_loads entry written, no counter, no test enqueued
        │
        ├─ (3) apply_day_result_to_user_state(...)     closed_loop_v1.py:117
        │        └─ updates SESSION-level stimulus_recency + fatigue_proxy ONLY
        │           (categories: finger_strength|boulder_power|endurance|complementaries)
        │           NEVER reads the per-exercise feedback level
        │
        ├─ (4) append_feedback_log(...)                adaptive_replan
        │        └─ persists raw item into state["feedback_log"]  ← STORED, never re-read for bodyweight progression
        │
        ├─ (4b) session slot "actual_exercises" = exercise_feedback_v1   feedback.py:222
        │        └─ raw audit trail only
        │
        └─ (5) check_adaptive_replan(...)              session-difficulty heuristic, not per-exercise duration
                                                       (operates on session feedback aggregates, not isometric load)
```

**Net effect for Side Plank:** the `easy` rating is *recorded* (feedback_log + session slot) but never *consumed* to change a future prescription.

---

## 3. Table of all feedback consumers

### `progression_v1.py` — `apply_feedback()` (the only per-exercise feedback consumer)

| Location | Branch / gate | What it adjusts | Non-loaded (`bodyweight_only`) included? |
|---|---|---|---|
| `1439` | `fb_load_model == "total_load"` | `working_loads` next external/total kg; max_hang streak counters | ❌ skipped |
| `1483` | `fb_load_model == "external_load" and not unilateral` | `working_loads` next external kg | ❌ skipped |
| `1504` | `fb_load_model == "grade_relative"` (`limit_bouldering`) | next target Font grade | ❌ skipped |
| `1531` | `fb_load_model == "external_load" and unilateral` | per-hand `working_loads` next kg | ❌ skipped |
| `1571-1586` | `max_hang_*` hard/easy streak ≥ 2 | enqueue finger re-test | ❌ (test exercises only) |
| `1588` | `_update_test_from_log()` | persist test results (max_hang/repeater/pulling) | ❌ (test exercises only) |
| `1428` | `feedback_label = canonical_feedback_label(item)` | computed for **every** item… | …then dropped for bodyweight (no branch consumes it) |

### `closed_loop_v1.py` — feedback consumers

| Location | What it reads | What it adjusts | Per-exercise level used? |
|---|---|---|---|
| `apply_day_result_to_user_state` `117-144` | session `status` (done/skipped) + derived `categories` | `stimulus_recency[cat]` counts/dates, `fatigue_proxy` totals | ❌ never reads exercise feedback level |
| `build_log_entry` `84-114` | `outcomes.exercise_feedback_v1` | copies into `actual_feedback_v1` (storage) | ⚠️ stored, not consumed |
| `_session_categories` `64-81` | `session_id` / `intent` / `tags` | category tagging | ❌ |

**Conclusion:** zero code paths in either module branch on a `bodyweight_only` exercise's feedback level to produce a future change. The `module_role`/category machinery operates at the **session** granularity, never at the **isometric exercise** granularity.

---

## 4. Isometric modeling summary

### How `2×20s` is stored
`side_plank.prescription_defaults` in `backend/catalog/exercises/v1/exercises.json`:
```json
"load_model": "bodyweight_only",
"prescription_defaults": {
  "sets": 2, "reps": null, "work_seconds": 20,
  "rest_between_reps_seconds": null, "rest_between_sets_seconds": 30,
  "notes": "Each side. Stack feet or stagger. Hips high."
}
```

| Prescription type | Representation | Example |
|---|---|---|
| Time-based isometric | `sets` + `work_seconds` (int), `reps: null` | `side_plank` 2×20s |
| Reps-based | `sets` + `reps` (int), `work_seconds: null` | `pallof_press` 3×8 |
| Loaded | `load_model` (`total_load`/`external_load`) + `intensity_pct` attr | hangboard/weighted work |

### Which layer owns it
`resolve_session.py:1718-1723` builds the resolved prescription by a **static merge** — catalog `prescription_defaults` overlaid by any template block `prescription` override:
```python
ex_defaults = selected_ex.get("defaults") or selected_ex.get("prescription_defaults") or {}
merged = {}
if isinstance(ex_defaults, dict):   merged.update(ex_defaults)
if isinstance(prescription, dict):  merged.update(prescription)
```
`work_seconds`/`sets` for Side Plank are **static catalog values**. The only per-user mutation downstream is `_apply_load_override` (kg only) and `suggest_max_hang_load` (fires only when `attributes.intensity_pct` is set — loaded test exercises). **No layer computes or progresses isometric duration/sets per user.**

### Is duration / sets engine-mutable?
- `work_seconds` and `sets` are **first-class numeric fields** the engine *could* increment — but **nothing writes them per-user today**. They are read-only catalog constants at resolve time.
- There is **no `working_loads`-equivalent store for duration**. `working_loads.entries[]` only ever holds kg / grade keys (written exclusively by the loaded branches of `apply_feedback`).

### Hard variants: selectable IDs or text-only cues?
**Text-only cues.** Side Plank's progressions/regressions live in `cues[]`, not as selectable exercise_ids:
```json
"cues": [
  "Regression: bottom knee bent to shorten the lever",
  "Progression: top arm overhead, or top foot raised"
]
```
Sibling exercise_ids exist (`plank`, `copenhagen_plank`, `plank_shoulder_tap`, `copenhagen_adductor_plank`) but these are **distinct exercises**, not graded difficulty variants of `side_plank` that the engine can auto-select. There is no variant ladder the resolver can step up/down.

### Feedback enum split (design-doc claim) — verification
- **Backend:** only `VALID_FEEDBACK = {"very_easy","easy","ok","hard","very_hard"}` (`progression_v1.py:145`). The claimed generic `easy/ok/hard` enum is **NOT FOUND**.
- **Frontend:** both feedback UIs render all **5** levels **unconditionally** — `feedback-dialog.tsx:27-33` (`DIFFICULTY_LEVELS`) and `guided-exercise-step.tsx:23-29` (`FEEDBACK_OPTIONS`). No conditional 3-level path for generic/bodyweight exercises.
- **Validation:** `FeedbackRequest` (`backend/api/models.py:130-134`) is an unvalidated `Dict[str, Any]`. The feedback level is **enforced nowhere** (neither frontend gating nor backend validation). A user *can* and *will* submit `very_easy` on Side Plank; it is accepted, stored, and ignored.

### `supports_load_progression` / `supports_band_assistance`
**NOT FOUND** in any catalog schema, loader, backend, or frontend file. The two flags appear **only** in `docs/ROADMAP_CURRENT.md:1032` (the backlog spec). Confirmed: 0 files in `backend/` or `frontend/`.

---

## 5. Gap statement

The existing v2+ backlog item **"Bodyweight exercises — load and band progression"** (`docs/ROADMAP_CURRENT.md:1025-1038`, origin: beta feedback Daniele 2026-03-31) is scoped to **external-load** bodyweight exercises:

> "Exercises like dip, push-up, pull-up… When feedback is 'too easy', the engine should suggest **adding external load (weight belt + disc)**. When feedback is 'hard'/'failed', it should suggest **resistance band assistance**."
> Implementation: add `supports_load_progression` / `supports_band_assistance` flags; extend closed-loop to read them "**Same pattern as existing external_load progression**".

**Side Plank coverage under that backlog item as specified: UNCOVERED.**

- The lever it adds is **external kg** (belt + disc) or **band assistance** — neither applies to a time-based isometric. You don't add a weight disc to a side plank, and "band assistance" has no meaning for an oblique hold.
- Its mechanism explicitly reuses the `external_load` progression pattern (→ `working_loads` kg). Side Plank's progression lever is **duration / sets / lever-length / variant**, none of which that pattern touches.
- Net: even after the 2026-03-31 backlog item ships, `easy` on Side Plank would **still be a no-op**. Time-based isometric progression is a **separate, currently-unscoped gap**.

`pallof_press` is a useful contrast for the parallel Pallof feature: it is `load_model: "bodyweight_only"` **despite** `equipment_required: ["resistance_band"]`. So even the band-based core exercise is invisible to load progression today — relevant to the separate "log the cable/band weight" A-brief, not acted on here.

---

## 6. Decision inputs for the future A-brief (options only — NOT implemented)

Three candidate progression levers for time-based isometrics, ranked by risk:

### Option A — Increment `work_seconds` (LOWEST risk) ⭐ recommended starting point
- **Idea:** on repeated `easy`/`very_easy`, bump the resolved `work_seconds` (e.g. 20s → 25s → 30s) up to a cap; on `hard`, hold/regress.
- **Files touched:**
  - `progression_v1.py` — add a `bodyweight_only` branch in `apply_feedback` writing a duration field to a per-user store (mirror of `working_loads`, e.g. `working_durations` keyed by exercise_id).
  - `resolve_session.py:1718-1723` — after the static merge, overlay the stored per-user `work_seconds` (new read, analogous to `_apply_load_override`).
- **Risk:** localized; reuses the existing feedback→store→resolve pattern. No variant catalog work. Bounded by a cap to avoid runaway (e.g. ≤45s).
- **Invariant note:** must write **future** prescriptions only; never rewrite logged Side Plank durations (past sessions immutable).

### Option B — Add a set (MEDIUM risk)
- **Idea:** escalate volume `2×20s → 3×20s` on sustained `easy`.
- **Files touched:** same two modules as Option A (store `sets` instead of/alongside `work_seconds`).
- **Risk:** changes session **duration/fatigue budget** → can ripple into `time_min`, slot-fit, and `fatigue_cost` accounting; needs interaction check with planner volume caps. Higher than A.

### Option C — Promote to a harder variant exercise_id (HIGHEST risk)
- **Idea:** model a difficulty ladder (`side_plank` → `side_plank_top_leg_raised` → …) and have the resolver step up on `easy`.
- **Files touched:**
  - **Catalog:** author N new exercise_ids + a variant-ladder schema field (currently progressions are free-text cues only — net-new modeling).
  - `resolve_session.py` — variant-selection logic (new concept; today the resolver picks one exercise, no intra-exercise laddering).
  - `progression_v1.py` — track ladder position per user.
- **Risk:** new catalog schema + new resolver concept + recency/substitution interactions. Largest surface; defer.

**Cross-cutting prerequisites the A-brief must also decide (independent of lever):**
1. **Feedback enum:** keep 5 levels for isometrics, or introduce the design-doc generic `easy/ok/hard`? Today neither layer enforces a split — a decision, not a bug to "fix" silently.
2. **Trigger policy:** single `easy` vs streak (e.g. 2 consecutive, mirroring `max_hang_*_easy_streak` at `progression_v1.py:1476-1586`).
3. **Storage shape:** new `working_durations` store vs extending `working_loads` entries with a duration field.

**Risk ranking:** A (low) < B (medium) < C (high). Recommended scope for a first A-brief: **Option A**, streak-triggered, with a hard cap, writing future-only — smallest blast radius on the high-risk engine modules.

---

## STOP gate

Report complete. **No code written, no branch opened.** Bring to claude.ai chat to decide scope; any implementation is a separate A-brief with its own STOP gate (touches `progression_v1.py` + `resolve_session.py` — high-risk).
