# A-ACTIVATION-TIMING — Day 1 simulation report

**Generated:** 2026-04-17T20:45:29
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

### Week-1 sparsity risk (flagged in brief §final)

With `this_monday()` + onboarding late on Sunday, Week 1 could collapse to a single Sunday session (or zero). The matrix does not include Sunday 23:00 because Day 1's brief specified Mon/Wed/Fri; flagging as item for Daniele before Day 2 if relevant.

## Stress scenarios — fallback threshold calibration (Day 2)

Added post-approval to pick the fallback threshold empirically. Each scenario is designed to yield a specific Week 1 count so we can measure how aggressive the fallback-to-next-Monday policy should be.

| stress_id | onboarding | expected | actual | first_session | ≤24h | past | match |
|---|---|---|---|---|---|---|---|
| stress_0_sun22_Mon-Fri_stress_today | 2026-04-19 Sun | 0 | 0 | — | — | 0 | ✅ |
| stress_1_sat19_MonWedFriSun_stress_today | 2026-04-18 Sat | 1 | 1 | 2026-04-19 | ✅ | 0 | ✅ |
| stress_2_fri23_MonWedSatSun_stress_today | 2026-04-17 Fri | 2 | 2 | 2026-04-18 | ✅ | 0 | ✅ |
| stress_3_thu20_MonWedFriSatSun_stress_today | 2026-04-16 Thu | 3 | 3 | 2026-04-17 | ✅ | 0 | ✅ |

### Threshold policy comparison

| Threshold T | Fallback triggers | Activation ≤24h | Fallback scenarios |
|---|---|---|---|
| T=0 (fallback if week_1 < T) | 0/4 | 75.0% | — |
| T=1 (fallback if week_1 < T) | 1/4 | 75.0% | stress_0_sun22_Mon-Fri_stress_today |
| T=2 (fallback if week_1 < T) | 2/4 | 50.0% | stress_0_sun22_Mon-Fri_stress_today, stress_1_sat19_MonWedFriSun_stress_today |
| T=3 (fallback if week_1 < T) | 3/4 | 25.0% | stress_0_sun22_Mon-Fri_stress_today, stress_1_sat19_MonWedFriSun_stress_today, stress_2_fri23_MonWedSatSun_stress_today |

**Reading the table:**
- T=0 means no fallback ever (keep even an empty Week 1).
- T=1 means fallback only when Week 1 is exactly empty (0 sessions).
- T=2/3 fallback even when Week 1 has a session or two → more users pushed to next Monday.

**Decision:** threshold **T=1** (fallback only when Week 1 would be 0).

Rationale:
- T=0 leaves the `stress_0_sun22_Mon-Fri` case producing an empty plan — unacceptable first impression.
- T=2+ drags `stress_2_fri23_MonWedSatSun` (which produces a perfectly fine 2-session Week 1) into the fallback, delaying activation unnecessarily.
- T=1 triggers only in the true edge case (Week 1 would otherwise be empty) and zero of the 18 main scenarios cross that line.
- Safest, most conservative, fully data-driven.

## Next steps

1. Apply threshold T=1 fallback in `backend/api/routers/onboarding.py`.
2. Add `is_week_one_empty()` helper in `backend/engine/start_date_utils.py` so the fallback can be unit-tested in isolation.
3. Regression tests: fallback fires for `stress_0` only; does not fire for `stress_1/2/3`.

