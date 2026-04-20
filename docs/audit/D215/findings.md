# D215 — Audit: macrocycle start_date shift + session completion loss on founder account

**Brief:** D215 (placeholder in original brief was D213; next_brief.py returned D215)
**Type:** D (read-only audit, no code changes)
**Date:** 2026-04-20
**User:** daniele.somensi@gmail.com · `7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e`
**Snapshot:** `docs/audit/D215/snapshot_pre_fix.json` (2.25 MB, redacted)
**Branch / commit:** `main` · `03202e8` (at time of audit)

> **Read-only.** Zero state mutations, zero code changes. All findings below are derived from the forensic snapshot + code inspection. No production regeneration has been run. Awaiting explicit OK before proposing a B-type fix brief.

---

## Section 1 — Current state snapshot

### 1.1 Macrocycle

| Field | Value |
|---|---|
| `macrocycle.start_date` | **2026-02-23** (Monday ✓) |
| `macrocycle.generated_at` | **2026-04-17T10:45:59** (3 days before incident) |
| `macrocycle.total_weeks` | 12 |
| `macrocycle.end_date` | (present, 12 weeks from start) |
| `macrocycle.discipline` | *None* (field not populated — not a pillar key; engine defaults apply) |
| `current_macrocycle` (legacy) | **not present** — only `macrocycle` top-level key in use |

Computed from `start_date=2026-02-23`:

| Phase | duration | macrocycle weeks | calendar range |
|---|---|---|---|
| base | 4 | 1–4 | 2026-02-23 → 2026-03-22 |
| strength_power | 3 | 5–7 | 2026-03-23 → 2026-04-12 |
| **power_endurance** | **2** | **8–9** | **2026-04-13 → 2026-04-26** |
| performance | 2 | 10–11 | 2026-04-27 → 2026-05-10 |
| deload | 1 | 12 | 2026-05-11 → 2026-05-17 |

So **today (2026-04-20) is macrocycle-week-9, the LAST week of power_endurance**. This is consistent with the "after-submit" screenshots (Week 9/12 · 20/04–26/04 · Power Endurance; Week 10/12 · 27/04–03/05 · Performance).

Phase objects contain `phase_id`, `phase_name`, `duration_weeks`, `start_week`, `end_week`, `domain_weights`, `energy_system`, `intensity_cap`, `session_pool`, `notes`. They do **not** carry per-phase `start_date`/`end_date` — those are computed on the fly in `current_phase_and_week()` and `week_num_to_phase_context()` (`backend/api/deps.py:234,263`).

### 1.2 `week_plans`

Keyed by **ISO date string** (week_start Monday). 15 entries total:

```
2026-02-23 (Mon)   2026-02-24 (Tue) ⚠
2026-03-02 (Mon)   2026-03-03 (Tue) ⚠   2026-03-10 (Tue) ⚠
2026-03-09 (Mon)
2026-03-16 (Mon)
2026-03-23 (Mon)
2026-03-30 (Mon)
2026-04-06 (Mon)
2026-04-13 (Mon)   — power_endurance week 1 (actual macrocycle-week 8)
2026-04-20 (Mon)   — power_endurance week 2 (actual macrocycle-week 9)
2026-04-27 (Mon)
2026-05-04 (Mon)
2026-05-11 (Mon)
```

⚠ **Three Tuesday keys** (`02-24`, `03-03`, `03-10`) are stale artifacts: before B119 landed, a macrocycle with `start_date=2026-02-24` produced those keys; after ensure_monday() was applied, start became `2026-02-23` but the Tuesday entries were never garbage-collected. They are **orphaned** (never read by `GET /api/week/{n}` because the week router always asks for the Monday key derived from `macrocycle.start_date`). Not related to today's incident.

### 1.3 `current_week_plan`

| Field | Value |
|---|---|
| `start_date` | **2026-04-13** (⚠ last week, not today's week) |
| `generated_at` | 2026-04-17T10:46:02 |
| `plan_revision` | 22 |
| `weeks[0].phase` | power_endurance |
| `weeks[0].week_index` | 1 |
| `adaptations[]` length | 21 (all tied to Apr 19 — mostly `add_custom_session` retries for `cs_e638e562`) |
| Completed sessions inside | Apr 14, 15, 16 (x2), 17 — all `status=done`, full `resolved`/`actual_exercises`/`feedback_summary` |
| Planned session inside | Apr 19 custom `Pull DANI` (`cs_e638e562`, never completed) |

**`current_week_plan` is stale.** It still points to the Apr 13–19 week even though today is Apr 20 and the macrocycle-derived current week is Apr 20–26. This is the root mismatch (see §5).

### 1.4 `pending_events`

Field **does not exist** in user_state. No array, no dict. The replanner uses per-plan `adaptations[]` for audit trail; events are applied inline via `apply_events()` rather than queued.

### 1.5 Completion / feedback logs

- `session_completion_log` (list, 32 entries, stable shape): last entry =
  ```json
  {
    "date": "2026-04-20",
    "session_id": "upper_body_weights",
    "status": "done",
    "completed_at": "2026-04-20T10:49:28.460392+00:00",
    "difficulty": "ok",
    "exercise_count": 10,
    "session_duration_seconds": 1868
  }
  ```
- `feedback_log` (list, 7 entries — trimmed by `append_feedback_log`, `backend/engine/adaptive_replan.py:148-150`): last entry = `{date: 2026-04-20, session_id: upper_body_weights, difficulty: ok, exercise_feedback: {...}, session_duration_seconds: 1868}`. All 7 entries are `difficulty=ok` (including today's). **No `hard`/`very_hard` aggregates anywhere.**
- `recent_sessions`: empty list.
- `history_index`: `{session_log_format: "jsonl", session_log_paths: ["data/logs/sessions_2026.jsonl"]}` — legacy pointer to file-backed logs (not used with `STORAGE_BACKEND=supabase`).

### 1.6 Closed-loop / progression state

- `stimulus_recency = {}` (empty dict — never seeded).
- `fatigue_proxy = {}` (empty dict — never seeded).
- `progression_counters = {max_hang_5s_easy_streak, max_hang_5s_hard_streak}` (only hangboard streaks).
- `working_loads.entries[]`: many entries, most with `updated_at` ∈ {Apr 14, 15, 16, 17, 20} — clear trace that progression.apply_feedback ran on every submit including today's.

The empty `stimulus_recency`/`fatigue_proxy` means `apply_day_result_to_user_state()` (`closed_loop_v1.py:117`) never ran on any submit. Either `FeedbackRequest.resolved_day` is never sent by the frontend, or this path was bypassed throughout the user's history. **Not a regression today** — it's been this way across 32 sessions. Separate finding, not part of the Apr 20 incident.

### 1.7 DB row metadata

- `users.updated_at = 2026-04-20T10:58:13.546535+00:00` → **12:58 CEST**. Matches exactly the "after-submit" timestamp in the screenshots. Only ONE state write at 12:58; the 12:49 `session_completion_log.completed_at` is the in-memory timestamp set by the handler, not a separate DB write.

---

## Section 2 — Session completion trace for 2026-04-20 Upper Body Antagonist

### 2.1 Where the feedback landed

| Store | Populated? | Evidence |
|---|---|---|
| `session_completion_log` | ✅ | `{date: 2026-04-20, session_id: upper_body_weights, status: done, completed_at: 2026-04-20T10:49:28Z, ...}` |
| `feedback_log` | ✅ | `{date: 2026-04-20, session_id: upper_body_weights, difficulty: ok, exercise_feedback: {...}}` |
| `working_loads.entries[*]` | ✅ | entries for Upper Body exercises have `updated_at=2026-04-20` |
| `current_week_plan.weeks[0].days[?].sessions[?].status` | ❌ | current_week_plan covers Apr 13–19; Apr 20 is outside its range — nothing matched |
| `week_plans["2026-04-20"].weeks[0].days[0].sessions[0]` (upper_body_weights) | ❌ | `status=None` (not "done"), `resolved=None`, `actual_exercises=None`, `feedback_summary=None` |
| `week_plans["2026-04-20"].weeks[0].days[0].sessions[1]` (technique_focus_gym) | ❌ | also untouched (user only submitted UBA) |
| `stimulus_recency` / `fatigue_proxy` | ❌ | empty (pre-existing condition, see §1.6) |

### 2.2 Supabase log tables

`session_logs` and `event_logs` tables exist in the Supabase project but are **empty across all users** (not just Daniele). They are not wired into the current runtime. All per-session / per-event state lives inside `users.state` JSONB (→ `session_completion_log`, `feedback_log`, `week_plans[*].adaptations`).

### 2.3 POST /api/feedback handler trace (`backend/api/routers/feedback.py:48-277`)

The handler executes eight numbered blocks. With Daniele's inputs on Apr 20 (`target_date="2026-04-20"`, `target_sid="upper_body_weights"`):

1. **L59-95 — mark_done on `current_week_plan`** (A194):
   - L59: `week_plan = state.get("current_week_plan")` → the stale Apr 13–19 plan.
   - L65-75: `apply_events(week_plan, [{event_type:"mark_done", date:"2026-04-20", session_ref:"upper_body_weights"}], ...)`.
   - Inside `replanner_v1.apply_events` the `mark_done` branch calls `_find_day(updated, "2026-04-20")` (`replanner_v1.py:864`).
   - `_find_day` (`replanner_v1.py:130-146`) walks all `weeks[].days[]` looking for `day.date == "2026-04-20"`. Not found. Raises `ValueError("Date not present in plan: 2026-04-20 (plan covers 2026-04-13..2026-04-19). …")`.
   - L82-89 in feedback.py: `except Exception as e:` → **silently swallowed**, logged as a WARNING, execution continues. **This is the session-loss mechanism.**
   - The `state["week_plans"][start_key] = week_plan` sync (L79-81) runs with the stale start_key=`2026-04-13`, overwriting/re-sealing week_plans["2026-04-13"] (no-op because they are already the same content).

2. **L97-114 — session_completion_log append**: independent of week_plan, runs unconditionally. Entry written ✅.

3. **L117-121 — `progression_v1.apply_feedback(log_entry, state)`**: updates `working_loads.entries[*]`, `progression_counters.max_hang_5s_*`, `test_queue` (seed). No touching of macrocycle/phases/start_date/week_plans. ✅.

4. **L124-133 — `closed_loop_v1.apply_day_result_to_user_state(...)`**: only runs if `req.resolved_day` is truthy. Snapshot suggests frontend doesn't send it → branch skipped. No side effects.

5. **L136-137 — `adaptive_replan.append_feedback_log`**: appends to `feedback_log`, trims to 7 most-recent. ✅.

6. **L147-170 — `actual_exercises` persistence**: iterates `current_week_plan.weeks[].days[].sessions[]` looking for `day.date==target_date AND session.session_id==target_sid`. Current plan covers Apr 13–19; no match. Then syncs to `week_plans[current_week_plan.start_date="2026-04-13"]` — same story, no match. **Silent no-op.**

7. **L173-199 — stale_exercise_warning guard**: builds `_resolved_exercise_ids` from current_week_plan; none match (different date); `_stale_ids` ends up empty because `_resolved_exercise_ids` is empty → guard does nothing.

8. **L202-215 — `check_adaptive_replan(plan, feedback_history, "2026-04-20")`**: iterates feedback_log, filters `difficulty in {"very_hard","fail"}`. All 7 entries have `difficulty=ok`. → `actions=[]`. No-op. (Also: this function reads `plan["weeks"][0]["days"]` so it would only ever adjust days within current_week_plan, which is Apr 13–19 — out of scope for Apr 20.)

9. **L264-268 — `persist_week_plan(final_plan=current_week_plan, state, user_id)`**:
   - `start_key = current_week_plan.start_date = "2026-04-13"`.
   - `state["week_plans"]["2026-04-13"] = current_week_plan`.
   - L89-99: compute `current_start = mc_start + weeks(cumulative + wi) = 2026-02-23 + 8*7 = 2026-04-20`. `start_key="2026-04-13" ≠ current_start="2026-04-20"` → **`state["current_week_plan"]` NOT updated**.
   - `save_state(state, user_id)` → this is the 12:58 CEST DB write.

### 2.4 What the user saw, reconciled

| Frontend element | Source | After submit |
|---|---|---|
| Week view header "Week 9/12 — Power Endurance · 20/04-26/04" | GET /api/week/0 → backend returns `week_plans["2026-04-20"]` (cache hit) + computed `week_num=9`. | Correct — matches post-submit screenshot. |
| "Previous" week navigation shows "Week 9/12 · 13/04-19/04" | GET /api/week/8 (macrocycle week 8). Backend returns `week_plans["2026-04-13"]` but **labels it "Week 9" because the frontend probably takes week_num from the route param `/api/week/{week_num}`. Actually backend returns `{week_num: 8, ...}` for n=8, so this is a pure frontend relabel.** OR: frontend uses `macrocycle.phases` to compute Week N/12 independently and mislabels week 8 as "week 9" because `phases[2]` (power_endurance) has `start_week=8` — off-by-one label. | Two apparent "Week 9"s — a label bug, NOT a data bug. |
| Today view "No sessions planned this week" + "Your availability may be too tight for the current phase" | Frontend reads `current_week_plan` (still Apr 13–19) and filters by `today == 2026-04-20` → empty. Falls back to the generic availability warning. | Session loss symptom. |
| Upper Body Antagonist still shown as "Planned" | Frontend shows session from `week_plans["2026-04-20"]` with `status=None`. | Direct consequence of the silent `mark_done` failure in §2.3-1. |

---

## Section 3 — Regeneration trigger map

### 3.1 `generate_macrocycle(` call sites

| File:Line | Context | Preserves `start_date`? | `from_phase="current"` preserved? |
|---|---|---|---|
| `backend/engine/macrocycle_v1.py:512` | **definition** | n/a | n/a |
| `backend/api/routers/macrocycle.py:82` | `POST /api/macrocycle/generate` | **Yes** when `req.from_phase` set (L69 `start_date = old_mc["start_date"]`); **No** on full regen (L78 `this_monday() if req.start_date is None`). `from_phase="current"` translated correctly at L65-67. | ✅ |
| `backend/api/routers/onboarding.py:427,435` | `POST /api/onboarding/complete` | full regen; `start_date` set from onboarding input via `ensure_monday`. | n/a (initial creation) |
| `backend/tests/test_*` | 30+ test call sites | test fixtures — irrelevant | n/a |

**Only two production paths mutate the macrocycle**: `POST /api/macrocycle/generate` and `POST /api/onboarding/complete`. Daniele confirms neither was invoked today. `macrocycle.generated_at=2026-04-17` corroborates this. → H4 (background regeneration) and H2-macrocycle-branch are ruled out.

### 3.2 `mc["start_date"] =` in-place writes

| File:Line | Context |
|---|---|
| `backend/api/routers/onboarding.py:463` | `POST /api/onboarding/start-week` — user-initiated shift from the onboarding wizard (N weeks back). Not invoked during incident. |
| `backend/api/routers/state.py:69` | `PUT /api/state` — `mc_patch["start_date"] = ensure_monday(mc_patch["start_date"])` **only** when the caller's deep-merge payload includes a macrocycle patch with a start_date. Not triggered without explicit caller intent. |

`onboarding.py:463` is the only path that can *retroactively* shift `start_date` backwards. The earlier Tuesday→Monday shift (§1.2) most plausibly came through this endpoint on or before 2026-02-24, combined with an early `ensure_monday()` rollout (B119). Not today's issue.

### 3.3 `generate_phase_week(` call sites

| File:Line | Caller | Respects `start_date`? |
|---|---|---|
| `backend/engine/planner_v2.py:643` | internal helper `_apply_regeneration` | derives from `prev["start_date"]` — safe. |
| `backend/engine/replanner_v1.py:1141` | `regenerate_preserving_completed` | uses `updated["start_date"]` — safe. |
| `backend/api/routers/week.py:363-385` | `GET /api/week/{n}` cache miss | uses `ctx["start_date"]` computed deterministically from `macrocycle.start_date` — safe. |

### 3.4 Phase-extension / re-phasing logic

| Symbol | Location | Wired in production? |
|---|---|---|
| `should_extend_phase` | `macrocycle_v1.py:771` | **No** — only referenced by `test_macrocycle_v1.py:228-235`. **Dead code.** |
| `should_trigger_adaptive_deload` | `macrocycle_v1.py:788` | **No** — only referenced by `test_macrocycle_v1.py:237-248`. **Dead code.** |
| `extend_phase` (local var, weakness adjustment) | `macrocycle_v1.py:289-291` | Active, but runs *inside* `generate_macrocycle` once at macrocycle creation. Uses weakest axis to add 1 week to one phase and shrink another. Never fires post-creation. |
| `shift`, `adjust_macrocycle`, `recompute_phases`, `rephase` | n/a | **No symbols with those names exist** in `backend/`. |

→ **There is no closed-loop path from hard/very_hard feedback to macrocycle structure.** User's mental model validated (§4).

---

## Section 4 — Closed-loop behavior on hard / very_hard feedback

### 4.1 What runs per submit, by label

| Label | Progression (`apply_feedback`) | Adaptive replan | Closed loop | Macrocycle |
|---|---|---|---|---|
| `very_easy` / `easy` | updates `last_*_load_kg` / `next_*_load_kg` via `_rule_midpoint_pct` | no | recency.done_count++ (if `resolved_day` sent) | — |
| `ok` | same | no | same | — |
| `hard` | same (negative `pct` via `_rule_midpoint_pct`) — working_loads **decrease** | no (needs very_hard/fail) | same | — |
| `very_hard` / `fail` | same, stronger negative pct | **yes**: `check_adaptive_replan` → Rule 1 (single) downgrades next hard day in the same week to `complementary_conditioning`; Rule 2 (2+ in 3 days) inserts `regeneration_easy` on next day in the same week. Both operate within `plan["weeks"][0]["days"]` only. | same | — |

### 4.2 Fields written on hard/very_hard feedback

Exactly these:

- `working_loads.entries[*]` (updated, including `last_feedback_label`, `next_external_load_kg`, `next_total_load_kg`, `updated_at`).
- `progression_counters.max_hang_5s_hard_streak` / `max_hang_5s_easy_streak` (only for `max_hang_5s` / `max_hang_7s` exercises).
- `session_completion_log[-1].difficulty` (aggregate label).
- `feedback_log[*].difficulty` + `exercise_feedback`.
- `stimulus_recency[*]`, `fatigue_proxy` (only if `resolved_day` provided).

And adaptive_replan can rewrite sessions **only within the current week plan**:
- Swaps a future-day session with `tags.hard=true` to `complementary_conditioning` (Rule 1).
- Or replaces the sessions array on the next future day with a single `regeneration_easy` (Rule 2).

**Nothing in this pipeline touches `macrocycle`, `macrocycle.phases`, `macrocycle.start_date`, or any other week_plans entry besides the current one.**

### 4.3 Divergence from design doc §4.4

`docs/DESIGN_GOAL_MACROCICLO_v1.1.md` §4.4 specifies: *"Feedback ancora 'hard' → estendi fase di 1 settimana"* (2 consecutive hard-weeks → +1 week to current phase, cap +2 weeks).

**Current code does NOT implement this feature.** The predicate `should_extend_phase` (`macrocycle_v1.py:771-785`) exists and matches the design rule, but is never called in production paths (only in unit tests). No router, engine function, or closed-loop module consumes it.

**User's mental model ("hard feedback only changes the load") is correct per current code.** Design doc and code have diverged since the doc was written. Either the code needs to catch up (new brief to wire up `should_extend_phase`) or the doc needs an amendment noting the feature is deferred.

---

## Section 5 — Root cause ranking

### Ranked hypotheses

| Rank | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| **H1** | Frontend / stale client-state bug: `current_week_plan` lags the macrocycle's current week across a Monday rollover. | **TRUE — primary cause.** | `current_week_plan.start_date=2026-04-13` while macrocycle-derived current week is `2026-04-20` (`current_phase_and_week` returns pi=2, wi=1 for today with start=Feb 23). |
| **H5** | `apply_events(mark_done)` fails silently because `target_date` is outside `current_week_plan`'s day range. | **TRUE — direct cause of the session-loss symptom.** | `feedback.py:82-89` catches all Exceptions from `apply_events`; `_find_day` raises `ValueError` for out-of-range dates (`replanner_v1.py:143`). Swallowed, completion never propagates to `week_plans["2026-04-20"]`. |
| H2 | `/api/feedback` regenerates the macrocycle. | **FALSE.** | Handler never imports or calls `generate_macrocycle`. `macrocycle.generated_at=2026-04-17T10:45:59` is pre-existing. |
| H3 | Closed-loop / progression extends a phase or shifts start_date on hard feedback. | **FALSE (feature not implemented).** | `should_extend_phase` / `should_trigger_adaptive_deload` are defined but **only referenced by tests** — never wired into any router or runtime code. Additionally, feedback_log has no `hard`/`very_hard` entries — trigger wouldn't fire anyway. |
| H4 | Background / cron regeneration. | **FALSE.** | No scheduler, no `APScheduler`, no `BackgroundTasks` in the repo. `macrocycle.generated_at` is 3 days old. |
| H6 | Other: frontend labels weeks using `phases[i].start_week` as a 1-based display offset, causing Apr 13–19 (macrocycle-week 8, power_endurance week 1) to show as "Week 9" — an off-by-one in label derivation. | **PLAUSIBLE contributing factor** (compounds H1 visually). Not load-bearing for the data loss — the session never moved, only the label. | `phases[2]` (power_endurance) has `start_week=8, end_week=9`. The frontend likely renders "Week {phase.end_week or start_week+week_index_in_phase}". |

### Primary root cause — exact path

The **load-bearing defect** is the interaction of three issues:

1. **`week.py:270-289` cache-hit short-circuit never refreshes `current_week_plan`.**
   When a user hits `GET /api/week/0` on Monday morning and `week_plans["2026-04-20"]` already exists (pre-generated Sunday by `generate_phase_week`), the handler returns it from cache but does **not** also set `state["current_week_plan"] = cached`. The fresh-generation branch at L419-420 is the only place that writes current_week_plan, and it's skipped on cache hit. → current_week_plan stays at the previous week's data indefinitely.

2. **`feedback.py:59-89` trusts `current_week_plan` as the target plan for `mark_done`.**
   With current_week_plan at Apr 13–19, a submit for Apr 20 date-mismatches inside `apply_events → mark_done → _find_day` (`replanner_v1.py:134,143`) — raises ValueError, swallowed at `feedback.py:82`.

3. **`feedback.py:148-170` replicates the same bug for `actual_exercises` persistence.**
   Iterates current_week_plan's days looking for `target_date`; no match; silent no-op; same broken week_plans sync at L158-169.

Exact code path:

```
feedback.py:59 (read current_week_plan)
  → current_week_plan.start_date = "2026-04-13"  (stale)
feedback.py:65 → replanner_v1.py:794 apply_events
  → replanner_v1.py:864 mark_done branch
  → replanner_v1.py:130 _find_day(plan, "2026-04-20")
  → replanner_v1.py:143 raise ValueError
feedback.py:82 except Exception → swallowed, logger.warning
feedback.py:97-114 session_completion_log append (still runs — partial success)
feedback.py:148-169 actual_exercises iterates CWP days, no match — silent skip
feedback.py:264 persist_week_plan(current_week_plan, state, user_id)
  → replanner.py:87 state["week_plans"]["2026-04-13"] = current_week_plan  (wrong key)
  → replanner.py:94-99 current_start = Apr 20 ≠ start_key Apr 13 → no CWP refresh
  → replanner.py:103 save_state
```

**Net effect on state:**
- ✅ `session_completion_log` appended
- ✅ `feedback_log` appended
- ✅ `working_loads` updated
- ❌ `week_plans["2026-04-20"].sessions[upper_body_weights].status` remains `None`
- ❌ `current_week_plan` remains frozen at Apr 13–19

---

## Section 6 — Immutability invariant check

### 6.1 Past completed sessions (Apr 13–19) — data integrity

All six `done` sessions in `week_plans["2026-04-13"]` / `current_week_plan` (they are currently deep-equal but distinct objects — confirmed via identity check) still carry their `status`, `resolved`, `actual_exercises`, `feedback_summary`, and `exercise_feedback` payloads. Each matches its `session_completion_log` entry by `(date, session_id)` and the `completed_at` timestamp is preserved.

**Conclusion:** the CLAUDE.md invariant ("Past sessions are immutable — never modified by regeneration, device switch, equipment change, or any other user action") **is still upheld for past days**. No corruption of Apr 14–17 records observed.

### 6.2 The Apr 20 submit does NOT violate the invariant, but exposes a structural gap

The submit did not *modify* any past session. It *failed to persist* today's session's done-state into the correct week_plans entry. Past sessions are still intact; today's session is missing its completion flag.

This is a subtly different class of bug from "device switch corrupted past data" — it's "state write went to the wrong week_plans key". The immutability rule is observed; the **consistency** rule (completion_log + feedback_log + week_plans must agree on session status) is violated.

### 6.3 Existing test coverage for this invariant

Tests that touch the neighborhood:

- `test_b114_preserve_past_weeks.py::test_past_week_done_sessions_survive_full_regen` — covers macrocycle regen → merge_prev_week_sessions preserves `status=done` on past days. Does NOT cover feedback submit with stale current_week_plan.
- `test_adaptive_replan.py` — covers `check_adaptive_replan` / `apply_adaptive_replan` semantics. Does NOT cover the week-rollover sync gap.
- `test_a_activation_timing.py` — tests the onboarding start-date shift and `from_phase="current"` invariants. Does NOT cover the rollover bug.
- `test_api.py::test_start_week_shifts_start_date` — covers the user-initiated start-week shift.

**No test exercises the precise scenario: `current_week_plan.start_date < today's week_start AND POST /api/feedback for today's session`.** That is the test-coverage gap driving this incident.

---

## Proposed fix strategy (prose only — no code)

Two must-have fixes, one nice-to-have cleanup, and a state-repair plan for Daniele's account. All require their own B/D briefs — this audit is read-only.

1. **[PRIMARY] Refresh `current_week_plan` on cache-hit in `GET /api/week/{n}`.**
   In `week.py:270-289`, after a cache hit that yields a `week_plan`, if `is_current_week` is true, set `state["current_week_plan"] = week_plan` and `save_state`. Idempotent. Prevents the rollover drift root cause.

2. **[PRIMARY] Make `feedback.py` robust to target_date outside current_week_plan.**
   Replace the bare `except Exception` at `feedback.py:82-89` with a targeted handling:
   - Detect ValueError from `apply_events`/`_find_day` specifically (introduce a typed exception like `DateNotInPlan` in `replanner_v1.py` if one doesn't exist).
   - On detection, look up `week_plans[ensure_monday(target_date)]`, apply `mark_done` there, and persist via the same `persist_week_plan` path.
   - Apply the same redirect to the `actual_exercises` persistence block (`feedback.py:148-170`).
   - Alternatively (stricter): return HTTP 409 "session plan out of sync, refresh the week view" — but silent failure must end either way.

3. **[NICE] Delete orphaned Tuesday `week_plans` keys** (`2026-02-24`, `2026-03-03`, `2026-03-10`) in a one-shot migration. Safe: they are never read under `ensure_monday()`-derived lookups. Purely cosmetic cleanup.

4. **[STATE REPAIR — separate brief, requires Daniele's OK]** To restore Daniele's account *after* the fix ships:
   - Set `state["current_week_plan"] = state["week_plans"]["2026-04-20"]` (structured copy).
   - In `week_plans["2026-04-20"].weeks[0].days[0].sessions[0]` (upper_body_weights): set `status="done"`, attach `actual_exercises` from `feedback_log[0].exercise_feedback` + exercise IDs from `session_completion_log[-1]`, attach `feedback_summary="ok"`, `session_duration_seconds=1868`.
   - Re-mirror into `current_week_plan` (same object) and save_state.
   - Leave `session_completion_log` and `feedback_log` untouched — already consistent.
   - **Do NOT regenerate the macrocycle.** start_date is already correct (2026-02-23, Monday, matches phase math).

---

## Recommended tests to add (names + assertion intent)

Each test name is in Python test-module style (`test_<module>.py::test_<scenario>`). Do not implement inside this audit; list is for the follow-up B brief.

1. **`test_week_rollover.py::test_get_week_cache_hit_refreshes_current_week_plan`**
   Arrange a state with `macrocycle.start_date=2026-02-23`, `current_week_plan.start_date=2026-04-13`, `week_plans["2026-04-20"]` pre-populated with 2 sessions. Patch "today" to 2026-04-20. Call `GET /api/week/0`. Assert `state["current_week_plan"].start_date == "2026-04-20"` after the call.

2. **`test_feedback_rollover.py::test_feedback_submit_persists_when_current_week_plan_is_stale`**
   Arrange same as (1). POST `/api/feedback` for session `upper_body_weights` on 2026-04-20 with `exercise_feedback_v1`. Assert `week_plans["2026-04-20"].weeks[0].days[0].sessions[0].status == "done"` AND `actual_exercises == <submitted items>` AND `feedback_summary == "ok"`.

3. **`test_feedback_rollover.py::test_feedback_submit_never_silently_drops_mark_done`**
   Arrange a request where `target_date` is present in neither current_week_plan nor any week_plans entry. Assert the handler returns HTTP 409 (or the chosen contract), **not** 200, and does **not** append to session_completion_log.

4. **`test_apply_events.py::test_mark_done_on_out_of_range_date_raises_typed_exception`**
   Call `apply_events(plan, [{mark_done, date outside range}])` → assert a dedicated exception type (e.g. `DateNotInPlan`), distinct from generic `ValueError`, so feedback.py can narrow its except clause.

5. **`test_immutability.py::test_feedback_submit_never_mutates_past_completed_sessions`**
   Snapshot week_plans for all weeks before POST /api/feedback, submit feedback for today's session, diff snapshot after — assert equality for every session with `status in {done, skipped}` in any week_plans entry other than the target.

6. **`test_phase_extension_not_wired.py::test_should_extend_phase_is_not_called_in_production_paths`**
   Static check (grep-style) asserting `should_extend_phase` and `should_trigger_adaptive_deload` are **not** imported outside `backend/tests/`. Protects against accidental wiring that would silently re-enable phase extension and shift start_date via hard feedback.

---

## Deliverables

- `docs/audit/D215/snapshot_pre_fix.json` — redacted Supabase snapshot (PII fields nulled). **[written]**
- `docs/audit/D215/findings.md` — this document. **[written]**
- `docs/audit/D215/trace.md` — chronological reconstruction. **[written]**

## Next step

**STOP.** No code changes, no state repair, no regeneration of Daniele's macrocycle until an explicit OK from Daniele. The natural follow-up is two briefs, in this order:

1. **B<next>** — fix the two primary defects (week rollover sync + feedback handler robustness) with the regression tests from this report.
2. **D<next>** — scripted state repair for Daniele's account, dry-run first, audit log appended to `docs/audit/D215/`.
