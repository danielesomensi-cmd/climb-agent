# D215 — Chronological trace 2026-04-20 12:53–12:58 CEST

User: `7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e` (daniele.somensi@gmail.com)
Sources: `users.updated_at`, `session_completion_log[*].completed_at`, `feedback_log[*]`, `working_loads[*].updated_at`, `macrocycle.generated_at`, `week_plans[*].generated_at` — all from `docs/audit/D215/snapshot_pre_fix.json`.

Note: `ts`, `completed_at` are stored in **UTC**. Daniele reported times are **CEST (UTC+2)**. Mapping: UTC + 2h = CEST. All inferred below.

---

## T-3 days context (2026-04-17)

- `10:45:59 UTC (12:45 CEST)` — `macrocycle.generated_at`. Someone (most likely the user via Settings → regenerate) triggered `POST /api/macrocycle/generate`, probably with `from_phase="current"` (start_date preserved at 2026-02-23). No phases structurally altered.
- `10:46:02 UTC (12:46 CEST)` — `current_week_plan.generated_at` for the Apr 13–19 plan. The `GET /api/week/0` that followed the macrocycle regen produced a fresh week plan for the current week (which was Apr 13–19 at that moment). Cached to both `week_plans["2026-04-13"]` and `current_week_plan`.
- `11:20:08 UTC (13:20 CEST)` — `session_completion_log[?]` — handstand_practice done. Last completion before the Apr 20 weekend.

## T-1 day context (2026-04-19 Sunday)

- `10:17:21 UTC (12:17 CEST)` — `week_plans["2026-04-27"].generated_at`. Frontend (or user navigating the week view to next week) triggered `GET /api/week/10` → cache miss → fresh generation for Apr 27 week.
- `12:14:20 UTC (14:14 CEST)` — **`week_plans["2026-04-20"].generated_at`**. User (navigating to next week, or frontend prefetch) triggered `GET /api/week/9` → cache miss → fresh generation for **the Apr 20 week**. This plan contains the two sessions for Apr 20 that Daniele saw in the morning: `upper_body_weights` and `technique_focus_gym`.
  - **Critical:** the `GET /api/week/9` call populated `week_plans["2026-04-20"]` but this was NOT the "current week" on Apr 19 yet (macrocycle-current was still Apr 13–19). So `is_current_week=False` in `week.py:262`, and `state["current_week_plan"]` was NOT overwritten. ✅ Correct at that moment.
- `12:14:44 UTC (14:14 CEST)` — `week_plans["2026-05-04"]` generated.
- `12:15:05 UTC (14:15 CEST)` — `week_plans["2026-05-11"]` generated.

Multiple `add_custom_session` events logged on Apr 19 (7 occurrences in `current_week_plan.adaptations[]`) — user trying to quick-add the "Pull DANI" custom session (`cs_e638e562`). Probably UI friction with the custom-session flow, eventually succeeded.

## Incident window (2026-04-20 Monday)

### Before ~12:49 CEST (user observation phase)

- User opens the PWA. Frontend fires `GET /api/week/0`. Backend:
  - `macrocycle.start_date = 2026-02-23`, `today = 2026-04-20` (Monday).
  - `current_phase_and_week` returns `(pi=2, wi=1)` → `week_num=9`, `ctx.start_date="2026-04-20"`.
  - `is_current_week = True` (week_num=0).
  - Cache lookup: `week_plans["2026-04-20"]` exists (generated yesterday at 14:14 CEST) and its `start_date` matches → **cache hit**.
  - **Bug A (week.py:270-289 — confirmed)**: cache-hit branch does NOT write `state["current_week_plan"] = cached`. `current_week_plan` stays at Apr 13–19. No save_state.
  - Backend returns the Apr 20–26 plan with 2 sessions for today. HTTP 200.

- Frontend renders:
  - Today view: reads returned `week_plan.weeks[0].days[0].sessions` → shows `upper_body_weights` + `technique_focus_gym`, total Load=230 ("2 sessions planned"). ✓
  - Week view header: possibly reads `current_week_plan.start_date` from a separate state slice (TanStack Query keyed off a different endpoint, or a selector that picks `state.current_week_plan` from `GET /api/state`). That value is still `2026-04-13` → header shows "Week 9/12 · 13/04-19/04". Meanwhile the displayed sessions list is correct for Apr 20 — the two data sources are out of sync. This is what Daniele captured in the first screenshot batch at ~12:53.

### 12:49:28.460 CEST — Feedback submit begins

*(`session_completion_log[-1].completed_at = 2026-04-20T10:49:28.460392+00:00` = 12:49:28 CEST)*

Daniele taps ▶ on Upper Body Antagonist in the guided flow. Runs through it. Taps "OK (done)" on the "8 exercises not completed" dialog. Taps "Submit & finish".

Frontend POSTs `/api/feedback` with `log_entry.date="2026-04-20"`, `log_entry.session_id="upper_body_weights"`, `log_entry.actual.exercise_feedback_v1=[…10 items…]`, `session_duration_seconds=1868`.

Backend handler (`feedback.py:48-277`) executes (see findings §2.3 for full path):

1. `week_plan = state.get("current_week_plan")` → the stale Apr 13–19 plan.
2. `apply_events(week_plan, [mark_done 2026-04-20 upper_body_weights])` → `_find_day` raises `ValueError`. **Silently swallowed at feedback.py:82-89.** `logger.warning(…)` emitted.
3. `session_completion_log.append(…)` — ✅ **completed_at=2026-04-20T10:49:28.460Z written.** This is the timestamp we see.
4. `progression_v1.apply_feedback(...)` — ✅ updates `working_loads.entries[*]` (all UBA exercises stamped `updated_at=2026-04-20`).
5. `apply_day_result_to_user_state` — skipped (req.resolved_day not sent, consistent with the user's history of empty `stimulus_recency`/`fatigue_proxy`).
6. `append_feedback_log` — ✅ new entry `{date:2026-04-20, session_id:upper_body_weights, difficulty:ok, exercise_feedback:{…}, session_duration_seconds:1868}`.
7. `actual_exercises` persistence — loops current_week_plan.days (Apr 13–19), `target_date=2026-04-20` matches nothing → silent no-op.
8. `check_adaptive_replan` — no very_hard/fail entries in feedback_log → `actions=[]`, no-op.
9. `persist_week_plan(current_week_plan, state, user_id)`:
   - `start_key = current_week_plan.start_date = "2026-04-13"`.
   - `state["week_plans"]["2026-04-13"] = current_week_plan` (self-assign, no change).
   - Computes `current_start = mc_start + weeks(7+1) = 2026-04-20`. `start_key ≠ current_start` → **`state["current_week_plan"]` NOT refreshed**.
   - `save_state` — Supabase write.

### 12:58:13.546 CEST — State write lands

`users.updated_at = 2026-04-20T10:58:13.546535+00:00` = 12:58:13 CEST.

Gap of ~8.75s between `session_completion_log[-1].completed_at` (12:49:28) and `users.updated_at` (12:58:13). Several explanations possible:

- The completed_at is set in-memory when the log entry is built (feedback.py:113); the DB write happens at the end of the handler (feedback.py:266 → supabase upsert). Network latency + Railway cold start + Supabase round-trip could account for up to a couple seconds, but 8.75s is long.
- More likely: the POST happened at 12:58 CEST wall-clock (Daniele's phone), and the `completed_at = datetime.now(timezone.utc)` at feedback.py:113 **also** should read 12:58, not 12:49 — but it reads 12:49. **That suggests the frontend sent a `log_entry` with a stale timestamp that ended up preserved somewhere, OR the guided session persisted a `startedAt`/`completedAt` payload from the earlier session run and the handler used that.**
- Alternate read: the 12:49:28 timestamp is computed by `datetime.now(timezone.utc)` server-side inside `feedback.py:113`. That is authoritative. If that fired at 12:49:28 UTC-aware and the DB write at 12:58:13, the 8.75s gap is server-internal (unusual but not impossible — e.g. a synchronous Stripe guard check, Supabase pooling stall, or logger flush).

**Not load-bearing for the audit.** The critical fact is that both timestamps lie within the ~5-minute window Daniele reports, and they correspond to exactly one POST /api/feedback invocation.

### ~12:58 CEST — Frontend refetches (post-submit screenshots)

After the mutation completes, the frontend invalidates week / state caches and refetches:

- `GET /api/week/0` → same cache logic, same `ctx.start_date="2026-04-20"`, cache hit on `week_plans["2026-04-20"]` (still unchanged — status=None, no mark_done landed). Returns it.
- `GET /api/state` → returns the freshly saved state where `current_week_plan.start_date=2026-04-13` is still pointing to last week.

Frontend renders the second screenshot batch:

- Week view header: now shows "Week 9/12 · 20/04-26/04" — because `/api/week/0` returned a plan with `start_date=2026-04-20`, and the component bound the displayed range to that field. ✓ (correct).
- "Previous" navigation: triggers `GET /api/week/8` → returns `week_plans["2026-04-13"]` (the Apr 13–19 plan). The frontend mislabels this as "Week 9/12" (should be "Week 8/12") — likely an off-by-one in the header that derives label from `phase.start_week`/`end_week`. This produces the "two Week 9s" complaint.
- Today view: reads `state.current_week_plan` → covers Apr 13–19; today (Apr 20) outside range → "No sessions planned this week" fallback string. Also triggers the generic availability warning.
- Upper Body Antagonist still shown as Planned: the Apr 20 week plan returned by `GET /api/week/0` has `sessions[0].status=None` — because the `mark_done` in the feedback handler silently failed.

---

## Summary — what changed on the server during the window

Between 12:49:28 and 12:58:13 UTC, exactly these fields changed in `state`:

| Field | Change |
|---|---|
| `session_completion_log` | +1 entry (Apr 20 upper_body_weights) |
| `feedback_log` | +1 entry (trimmed oldest to stay at 7) |
| `working_loads.entries[*]` | updated_at=2026-04-20 on ~10 entries |
| `progression_counters.max_hang_5s_*_streak` | reset to 0 (upper_body exercises don't count for hang streaks, but `_ensure_test_queue` may have touched counters) |
| `test_queue` | possibly re-seeded by `_ensure_test_queue` |
| `week_plans["2026-04-13"]` | re-assigned to `current_week_plan` object (content identical) |
| `users.updated_at` | 2026-04-20T10:58:13Z |

**No change** to:
- `macrocycle.start_date` (still 2026-02-23)
- `macrocycle.generated_at` (still 2026-04-17T10:45:59)
- `macrocycle.phases[*]` (structurally identical)
- `week_plans["2026-04-20"]` (still status=None for upper_body_weights)
- `current_week_plan.start_date` (still 2026-04-13)

The "apparent shift" the user saw was purely a frontend display transition, not a server-side data change. The server has never moved the macrocycle start_date in this session; the only mutation that actually corresponds to the incident is a partially-successful feedback persist.
