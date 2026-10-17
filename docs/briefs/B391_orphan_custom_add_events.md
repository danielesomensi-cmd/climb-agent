# B391 — `add_custom_session` entries in the adaptations log with no session in the plan

**Type:** B (data hygiene) · **Status:** Phase 1 (analysis) — **STOP**, waiting for Daniele's OK
**Origin:** out-of-scope finding of [[B382]] (2026-10-17) · **STOP-gated module:** none for the
recommended option (a prod data clean-up; no engine code)

## What is there (prod, Daniele, read-only, state of 2026-10-17 14:16)

Every future week from 19/10 to 23/11 (6 weeks) carries the same 4 log entries:

```
{"type":"event","event":{"event_type":"add_custom_session","custom_session_id":"cs_…",
 "target_date":"<Mon|Tue|Wed|Thu>","slot":"lunch","gym_id":"3c7f08e0","location":"gym"}}
```

(Mon `cs_1f679d81`, Tue `cs_16a9b267`, Wed `cs_61a28d9a`, Thu `cs_8885003e`), while those lunch slots
hold the engine's lunches (A300/A318 rotation). **24 orphan entries** in the future weeks; 11 more
in the past weeks 05/10 and 12/10, mixed with legitimate ones (a custom later skipped is replaced by
its `regeneration_easy` stub: also "orphan" by this definition, and history).

## Root cause — not a code bug

1. From 07/09 the four Work lunches were custom sessions placed **by hand** in every week of the
   macrocycle (`POST /api/replanner/events`, `add_custom_session`, one call per day/week), which
   is what wrote the log entries.
2. On **2026-10-05 13:44**, when A300 took over the weekly structure ("the planner builds it — do
   not paste customs by hand", `climb-coach/profilo/atleta.md`), a dev session removed those
   lunch customs from the weeks ≥ 12/10 with a `PUT /api/state` that rewrote the days' `sessions`,
   **deliberately without a removal record** — a `remove_session` would have told A300 that the
   user had emptied those lunches, and the planner would never fill them again
   (`user_owned.removal_records`: a removed lunch consumes its family).
3. The `add_custom_session` entries were left in `adaptations`, and every later regeneration
   carries the log forward unchanged (`replanner_v1._merge_user_content` ≈ 808-816, B369: "the
   user's removals stay on record").

## Impact — none today

No reader uses an `add_custom_session` log entry to decide anything:

- `user_owned.removal_records` / `removed_refs` / `slot_emptied` read only `remove_session`,
  `move_session`, day overrides, `add_outdoor` / `remove_outdoor`, `auto_reschedule_declined`.
- `complementary_v1` (≈ 536-580) and `retest_policy._locked_by_merge` (≈ 805-830) read the
  removal records and the sessions, not the add events.
- `key_sessions_v1` reads `adaptive_replan` (≈ 622), `remove_session` without ref (≈ 1537) and,
  in a dry run, only the entries the dry run itself appended (≈ 1688).
- `report_engine` (B389) and `athlete_context` read the sessions and the completion log.
- No frontend reader of `adaptations` except `phase-rationales.ts` (unrelated types).

Verified by grep on `add_custom_session` across `backend/`, `scripts/`, `frontend/src`, and
`climb-coach/tools`. The cost is confusion: whoever reads the raw log (debugging, the coach, an
audit like B382's) sees four customs "added" each week that are not there, and ~3 KB per week.

## Options

**A — one-off clean-up of the future weeks (recommended).** Remove from the `adaptations` of the
weeks with `start_date` ≥ the current Monday + 7 (19/10 onward) every `add_custom_session` entry
whose target slot does not hold that custom. Script with `--dry-run` listing every entry, full
state backup in `~/backups/` (not in the repo), `updated_at` optimistic check, re-read after.
The current week and the past ones are history and stay as they are. Before applying, the dry run
also checks that the regenerated weeks are byte-identical with and without the entries (they must
be: nothing reads them).

**B — leave them.** Harmless; document the reason in the coach runbook.

**C — code guard.** A merge that drops log entries with no session behind them. Not recommended:
it would touch `replanner_v1` (STOP gate) to fix a one-off, and a user-visible event log should
not be rewritten by the engine.

In every case, a runbook rule for whoever writes to prod by hand (`climb-coach/runbook/scrivere-in-app.md`):
*taking sessions out with a `PUT /api/state` leaves the log behind — strip the matching
`add_*` entries in the same write, or use `remove_session` when a removal record is wanted.*

## Decisions for Daniele

1. **Option A** (clean the 24 future entries, past weeks untouched), or **B** (leave them)?
2. OK for the runbook rule in climb-coach?
