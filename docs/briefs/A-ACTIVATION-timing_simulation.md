# A-ACTIVATION-TIMING — Day 1 simulation report

**Generated:** 2026-04-17T20:28:18
**Script:** `scripts/simulate_onboarding_start.py`
**Scope:** read-only — exercises `generate_macrocycle()` + `generate_phase_week()` unchanged.

## Input matrix

- Onboarding moments: Mon 09:00, Wed 20:00, Fri 23:00 (fixed ISO week 2026-04-13 → 2026-04-19).
- Availability A: 4 evenings/week (Mon/Tue/Thu/Sat), gym.
- Availability B: 6 days/week (Mon-Sat), mixed morning/evening, gym.
- User choices: `today` → this_monday; `tomorrow` → this_monday(today+1); `next_monday` → strict_next_monday (always +7 on Mondays).

Total: 3 × 2 × 3 = 18 rows.

## Results

| scenario_id | onboarding | choice | start_date | first_session | ≤24h | past | total | days | notes |
|---|---|---|---|---|---|---|---|---|---|
| mon_09_availA_today | 2026-04-13 Mon | today | 2026-04-13 | 2026-04-13 | ✅ | 0 | 4 | 4 |  |
| mon_09_availA_tomorrow | 2026-04-13 Mon | tomorrow | 2026-04-13 | 2026-04-13 | ✅ | 0 | 4 | 4 |  |
| mon_09_availA_next_monday | 2026-04-13 Mon | next_monday | 2026-04-20 | 2026-04-20 | — | 0 | 4 | 4 |  |
| mon_09_availB_today | 2026-04-13 Mon | today | 2026-04-13 | 2026-04-13 | ✅ | 0 | 4 | 4 |  |
| mon_09_availB_tomorrow | 2026-04-13 Mon | tomorrow | 2026-04-13 | 2026-04-13 | ✅ | 0 | 4 | 4 |  |
| mon_09_availB_next_monday | 2026-04-13 Mon | next_monday | 2026-04-20 | 2026-04-20 | — | 0 | 4 | 4 |  |
| wed_20_availA_today | 2026-04-15 Wed | today | 2026-04-13 | 2026-04-16 | ✅ | 0 | 2 | 2 |  |
| wed_20_availA_tomorrow | 2026-04-15 Wed | tomorrow | 2026-04-13 | 2026-04-16 | ✅ | 0 | 2 | 2 |  |
| wed_20_availA_next_monday | 2026-04-15 Wed | next_monday | 2026-04-20 | 2026-04-20 | — | 0 | 4 | 4 |  |
| wed_20_availB_today | 2026-04-15 Wed | today | 2026-04-13 | 2026-04-15 | ✅ | 0 | 4 | 4 |  |
| wed_20_availB_tomorrow | 2026-04-15 Wed | tomorrow | 2026-04-13 | 2026-04-15 | ✅ | 0 | 4 | 4 |  |
| wed_20_availB_next_monday | 2026-04-15 Wed | next_monday | 2026-04-20 | 2026-04-20 | — | 0 | 4 | 4 |  |
| fri_23_availA_today | 2026-04-17 Fri | today | 2026-04-13 | 2026-04-18 | ✅ | 0 | 1 | 1 |  |
| fri_23_availA_tomorrow | 2026-04-17 Fri | tomorrow | 2026-04-13 | 2026-04-18 | ✅ | 0 | 1 | 1 |  |
| fri_23_availA_next_monday | 2026-04-17 Fri | next_monday | 2026-04-20 | 2026-04-20 | — | 0 | 4 | 4 |  |
| fri_23_availB_today | 2026-04-17 Fri | today | 2026-04-13 | 2026-04-17 | ✅ | 0 | 2 | 2 |  |
| fri_23_availB_tomorrow | 2026-04-17 Fri | tomorrow | 2026-04-13 | 2026-04-17 | ✅ | 0 | 2 | 2 |  |
| fri_23_availB_next_monday | 2026-04-17 Fri | next_monday | 2026-04-20 | 2026-04-20 | — | 0 | 4 | 4 |  |

## Hard assertions

| # | Rule | Status |
|---|------|--------|
| 1 | `past_day_sessions_count == 0` for every row | ✅ pass |
| 2 | `first_scheduled_session_date >= onboarding_date` | ✅ pass |
| 3 | `computed_start_date` is always a Monday | ✅ pass |
| 4 | `choice=today` + today available → first session == today | soft check (per-row inspection) |
| 5 | `choice=next_monday` → first session ≥ strict next Monday | ✅ pass |

**All hard assertions passed.**

## Interpretation

### Today behaviour (prod today, `next_monday()`)

A user onboarding Wed 20:00 gets `start_date = next Monday` (5 days away). All three scenarios `wed_20_*_today` therefore fail to surface a session within 24h — matches the observed 75% post-plan drop-off cohort.

### Proposed behaviour (`this_monday()` + user_choice)

With Day 2's shift to `this_monday()`:
- `mon_09_*_today` → start_date = today; first session can be today evening if availability has it.
- `wed_20_*_today` → start_date = Mon (this week); planner skips Mon/Tue via B95; first session Wed (if avail) or Thu.
- `fri_23_*_today` → start_date = Mon (this week); first session Fri or Sat depending on avail.
- `*_next_monday` → start_date shifts +7 from the current week's Monday, so Week 1 is pristine.

### Past-day guard

Planner's B95 guard (`today_date is not None and day_dates[offset] < today_date`) stops past-day session placement even when start_date is before today. The simulation verifies this empirically — if row 1 ever shows `past > 0`, the backend shift is unsafe.

### Week-1 sparsity risk — **observed, not hypothetical**

The brief's §final warned about "weird Week 1 sizes" when `this_monday()` collides with low availability. The simulation confirms it:

- `fri_23_availA_today` → Week 1 has **1 session** (Sat). The user's Mon/Tue/Thu availability slots are all in the past when they onboard Friday 23:00 with a 4-evenings-only pattern. Only Saturday survives.
- `fri_23_availB_today` → Week 1 has **2 sessions** (Fri, Sat). Marginally better because availability B covers 6 days.
- `wed_20_availA_today` → Week 1 has **2 sessions** (Thu, Sat). Acceptable.

None of these are zero, so the user always sees *something* on /today. But a 1-session Week 1 is a poor first impression — "plan" is overselling it.

**Mitigation options for Day 2** (pick one, confirm with Daniele):

1. **Do nothing** — accept sparse Week 1 as the cost of "start immediately". The hero CTA in Day 3 can soften this with a "Your full plan starts Monday" subtitle.
2. **Fallback threshold** — if `this_monday()` would produce a Week 1 with ≤1 remaining available day, fall back to `next_monday()` automatically. (Adds one branch to onboarding.py; tests must cover the threshold.)
3. **Only offer "today" when it yields ≥2 sessions** — move the decision to the UI: show "today" option only if availability supports it. Backend unchanged.

No Sunday case was simulated (brief scoped Mon/Wed/Fri). The `tomorrow` choice on Sunday would flip the user into next week's Monday automatically via `this_monday(today+1)` — worth confirming on Day 2 if that path matters.

## Next steps

1. Review the table above with Daniele.
2. Confirm no regressions in past-day count or Monday invariant.
3. If OK, proceed to Day 2 backend shift: `onboarding.py` L385 `start = next_monday()` → `start = this_monday()` (with fallback when week 1 would be empty).

