# B390 — a mid-week regeneration ignores the hard sessions already done this week

**Type:** B (bugfix) · **Status:** Phase 1 (analysis) — **STOP**, waiting for Daniele's OK
**Origin:** out-of-scope finding of [[B382]] (2026-10-17) · **STOP-gated module:** `planner_v2.py` (yes)

## Symptom

When the current week is regenerated mid-week (availability saved, profile edited, `force=true`,
a stale week), the planner places the remaining days **as if nothing had happened since Monday**:
the hard / finger sessions already done on the past days of the week count neither toward the
weekly hard-day cap, nor toward the 48 h hard / finger gaps, nor toward anti-repetition.

The merge (`_merge_user_content`) then puts the done days back unchanged, so the saved week can
hold more hard days than the cap and two finger-hard days back to back — and `guards_v1`, which
reads the whole week, immediately raises `hard_cap` / `finger_gap` alerts against the engine's
own placements.

## Reproduction

**Synthetic (the B382 fixture, strength_power, cap 3)**: plan generated Monday, Mon–Wed marked
done, the user did `strength_long` (hard, finger) on Wednesday evening. Regeneration on Thursday:

| Day | After the Thursday regeneration |
|---|---|
| Mon | `limit_boulder_gym` done (H, F) |
| Tue | lunch HIIT done · `lead_tryhard_gym` done |
| Wed | `strength_long` **done (H, F)** |
| Thu | **`limit_boulder_gym` (H, F)** ← 24 h after Wednesday's finger session, and the second limit of the week |
| Fri | lunch |
| Sat | `power_contact_gym` (H, F) |
| Sun | `technique_focus_gym` |

4 hard days against a cap of 3, finger back to back Wed→Thu, `limit_boulder_gym` twice.
Script: session scratchpad `b390/synth.py` (synthetic fixture only).

**Prod (Daniele, read-only, week 12/10)**: the 17/10 09:45 regeneration (Saturday, profile edit)
placed `test_repeater_7_3` on Saturday with `power_contact_gym` (14/10) and `strength_long` (15/10)
already done. It did no damage that time — Daniele's cap is 5 and Thursday→Saturday respects the
48 h gap — and B379 later took that session off the crag day anyway. But nothing in the planner
prevented it: had the regeneration run on Friday with a Friday evening available, the same code
would have put a finger session 24 h after the max-strength day.

## Root cause

`backend/engine/planner_v2.py`, `generate_phase_week`:

- **1580-1583** — `hard_days = 0`, `finger_day_offsets = []`, `hard_day_offsets = []`,
  `session_count = {}`: the week starts empty.
- **1587-1597** — B161 seeds the spacing from the **previous week**'s trailing days (negative
  offsets). Nothing seeds it from the **same week**'s days before today.
- **1629-1632** — B95: days before today are skipped (`day_has_available_slot = False`), which is
  right for placement, but their sessions are never read.
- **1662-1687** — B382(b) already counts a declared crag day of this week (done, or not past) in
  `hard_days` and in the gaps: the same idea, limited to outdoor days.
- The cap / gap checks that read those counters: **1805** (PASS 1), **1950** (fallback), **2185**,
  **2367** (PASS 2.x), **2912 / 2980** (PASS 3 tests), and the `_commit` recount at **2675**
  (PASS 3a retest, which recounts only `day_sessions`, i.e. engine sessions from today on).
- Not affected: the A305 key pass (≈ 940-1000) works on the **merged** view of the week
  (`_merge_user_content` preview), so it already sees the done days; A300's lunch rotation and
  HIIT cap read `existing_week_plan` too.

So two parts of the same planner disagree: the key pass and the alerts see the whole week, the
primary / secondary / test passes see only today onward.

## Call sites and consumers

- `GET /api/week/{n}` (`backend/api/routers/week.py` ≈ 812-846) — the only caller that passes
  `existing_week_plan` + `today` for the current week (regeneration: force, stale, availability
  save, profile edit, weekly-override). Future weeks have no past days → unaffected.
- `replanner_v1._merge_user_content` copies the past days back wholesale (B369/B114) — unchanged.
- `guards_v1._hard_cap` / `_finger_gap` (≈ 420-450, 300-320) — read the merged week, will simply
  stop firing on the planner's own placements.
- `weekly_load_summary.hard_days_count` (≈ 3115) counts only the generated days (it reported 1 on
  the prod repro with 2 hard sessions done): cosmetic, same fix.

## Tests that cover the area

`test_b382_slot_empty_crag_hard.py` (fixture and `_regen` helper to reuse), `test_b161_*`
(cross-week spacing), `test_a300_complementary_slots.py`, `test_a305_key_stimulus_pass.py`,
`test_b369_*`, `test_b379_*`, the C272 / A290 golden files and the A300 identity digests.
Weeks generated without `existing_week_plan`, or with `today` = Monday, have no past days → the
golden files and digests must stay byte-identical (that is the regression guard).

## Fix options

**A — seed the counters from the past days of the same week (recommended).** Right after the B161
seed: for every day of `existing_week_plan` with date < today (and today itself when its session is
done, already copied wholesale by the merge), for every session with `status == "done"`:
hard → `hard_days += 1` (once per day) and `hard_day_offsets.append(offset)`; finger →
`finger_day_offsets.append(offset)`; `session_count[sid] += 1`. Tags from the session itself
(`tags`, B345-derived for customs), falling back to `_SESSION_META` — the same reading as B161
and as `guards_v1._counts_as_hard`. Skipped sessions and past days never marked do not count (the
athlete did not train). One block, ~25 lines, plus the `hard_days_count` summary.

**B — spacing only, not the cap.** Avoids "losing" a hard session late in the week, but keeps the
engine generating weeks the alerts then flag as over the cap.

**C — alert only.** Already the case today (guards). Leaves the planner producing violations.

## Decisions for Daniele

1. **Option A** (cap + gaps + anti-repetition) — or B / C?
2. **What counts as "done"**: only sessions marked done (recommended), or also past sessions
   never marked (assumed done)?
3. **Free sessions and outdoor logs off the plan** (free climbing session, crag day logged without
   a planned day) — count them too, or plan sessions only for now (recommended: plan only, a
   separate item if needed)?

Phase 2 after the OK: implement A in `planner_v2` only, tests (synthetic fixture above as the
failing test, golden / digests unchanged, past-sessions-immutable invariant, determinism), full
suite twice, prod read-only check that Daniele's current weeks do not change.
