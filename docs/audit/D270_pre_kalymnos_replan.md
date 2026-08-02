# D270 — Pre-Kalymnos replan (analysis + applied plan)

**Type:** D (analysis) + data-only intervention on Daniele's production state
**Date:** 2026-08-02 · **User:** `7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e`
**Code touched:** none. Every write went through the public API (`PUT /api/state`,
`POST /api/replanner/override`, `PUT /api/weekly-override/{week}`).

---

## 1. Situation

Trip to Kalymnos departs **2026-08-20**, 20 days of outdoor lead. Calendar: 3–9/8 home with
full availability, 10–16/8 mountains (long easy multipitch), 17–19/8 home and working, then
departure.

The plan as it stood: macrocycle 18/05 → **09/08**, 12 weeks, week 12 (3–9/8) = `deload`,
and **nothing at all after the 9th** — `week_num_to_phase_context` raises past the sum of
phase durations, so the days before departure were unplannable. `trips` was empty: the trip
was not in the system.

## 2. What the training history actually says

Adherence by phase, from 87 logged sessions:

| Phase | Weeks | Done | Skipped |
|---|---|---|---|
| base | w1–2 | 10 | 2 |
| strength_power | w3–6 | 11 | 0 |
| power_endurance | w7–9 | 8 | 0 |
| performance | w10–11 | 7 | 7 |

With seven evenings available per week, the PE and performance phases ran at **2–4 sessions a
week**, and several "done" entries carry implausible durations (0, 2, 3, 13 minutes). The gym
plan was executed at roughly half strength.

**The real training was outdoor**: 11 distinct days at Berdorf/Paderno in July alone
(load 14–39), about 2.5 lead days a week — specific, sub-maximal, continuous.

**The last week was not light.** Six of seven days active: 27/7 Paderno, 28/7 custom 60',
30/7 custom 45' + limit boulder, 31/7 custom 53', 1/8 custom 71', and **2/8 Berdorf at load
39 — the heaviest outdoor day in two months, the day before this analysis.**

**Fatigue signal: absent, not negative.** `fatigue_proxy` is `{}`, and all 87 sessions are
marked `ok` — zero `hard`, zero `easy`. The subjective channel carries no information, so the
recommendation rests on observed load, not on self-report. Worth stating plainly rather than
dressing the conclusion as better-evidenced than it is.

**Profile decides the content:** finger_strength **100**, pulling_strength **96**,
power_endurance **53**, endurance **51**, technique **30**. Kalymnos rewards the low axes.
Fingers and pulling are already maxed and cannot be built in 18 days anyway.

## 3. Decision: structure (b), moderated

Keeping the deload (option a) would have spent the **last full-availability week** on recovery
from a block that was never fully executed — and then handed him a second consecutive
easy week, because 10–16/8 in the mountains *is* an active deload (aerobic volume, low
intensity, no maximal finger loading). Two scarico weeks back-to-back before 20 performance
days is detraining, not freshness.

But "train hard from Monday" was wrong too: he arrives off six consecutive active days.
So the week opens easy and carries **one** hard day.

Approved by Daniele, who then asked to extend the plan to 20/8 rather than handle the tail
outside the app — the better call, since it makes 17–19/8 real plan instead of a verbal note.

## 4. What was written

**Macrocycle extended 12 → 14 weeks** (`PUT /api/state`, deep-merge replaces the `phases`
array wholesale):

| # | Phase | Before | After |
|---|---|---|---|
| 1–3 | base / strength_power / power_endurance | w1–9 | unchanged |
| 4 | performance | 2w (w10–11) | **3w (w10–12)** |
| 5 | deload | w12 | **w13** (10–16/8, the mountains) |
| 6 | performance *(new)* | — | **w14** (17–23/8, sharpening) |

`total_weeks` 14, `end_date` 2026-08-23.

**Why this is safe for the past:** a week's phase is derived *only* from the running sum of
`duration_weeks` in order (`deps.py:week_num_to_phase_context`). The first four phases keep
their cumulative durations through w9 and `performance` still starts at w10, so extending it
from 2 to 3 weeks moves only what comes *after*. No lived week changes phase. `phase_id`
repeated twice is fine — resolution is positional, never by id.

**Week 12 (3–9/8)** regenerated as `performance`, then aligned day by day with
`POST /api/replanner/override`. The generated week was too much on its own: load 375, three
hard days, two `max` sessions and a `high`/finger session on Tuesday.

| Day | Session | Rationale |
|---|---|---|
| Mon 3 | `yoga_recovery` (home) | absorbs Sunday's load-39 Berdorf day |
| Tue 4 | `prehab_maintenance` (home) | home day, no load |
| Wed 5 | `power_endurance_gym` (**high**) | the axis at 53 — the one that decides Kalymnos |
| Thu 6 | `technique_focus_gym` (medium) | axis at 30, cheap |
| Fri 7 | `endurance_aerobic_gym` (medium) | axis at 51, specific endurance |
| Sat 8 | **outdoor lead** | his actual pattern, most specific stimulus |
| Sun 9 | `regeneration_easy` (home) | rest |

One hard day, 48h+ clear of the Saturday outdoor day.

**Week 13 (10–16/8, mountains)** — availability restricted to Tue + Fri at home via
`PUT /api/weekly-override/2026-08-10`, so the planner leaves five days free for the multipitch
instead of filling seven evenings, two of them in a gym he will not be near. Result:
`flexibility_full` and `prehab_maintenance`, both bodyweight, both at home.

**Week 14 (17–23/8, sharpening)** — availability Mon/Tue/Wed only.

| Day | Session | Rationale |
|---|---|---|
| Mon 17 | `power_contact_gym` (max) | short and intense: sharpen without volume |
| Tue 18 | `flexibility_full` (home) | mobility only |
| Wed 19 | `prehab_maintenance` (home) | shoulders/elbows before 20 climbing days |
| Thu 20 – Sun 23 | empty | departure; Daniele's explicit choice |

The generated week had put `finger_strength_home` (high, finger) on Tuesday the 18th —
precisely the load a taper must not carry, two days out, on the axis already at 100.
Overridden.

## 5. Invariant check (post-write)

Snapshot fingerprinted **before** any write and compared field by field after:

| Structure | Result |
|---|---|
| `session_completion_log` (87) | ✅ identical |
| `feedback_log` (7) | ✅ identical |
| `outdoor_log` (32) | ✅ identical |
| `working_loads` | ✅ identical |
| `free_sessions` (10) | ✅ identical |
| `week_plans` for past weeks (20/07, 27/07) | ✅ identical |

Nothing completed was touched. Backup of the full pre-intervention state kept alongside the
snapshot. Backend suite: **3018 passed**.

Two mechanisms did the protecting, not just care: `apply_day_override` refuses (B120) to
overwrite a `done`/`skipped` session, and `POST /api/replanner/override` rejects (B257) any
week whose Monday is in the past. Week 12 had not started, so neither guard needed to fire.

## 6. Findings recorded, not fixed here

- **WEEKLY-OVERRIDE-SHORT-KEYS** — `PUT /api/weekly-override/{week}` accepts day keys in
  either form and answers `{"status": "ok"}`, but `merge_override_into_availability` only maps
  **long** names (`monday`…); short ones (`mon`…) hit `if short is None: continue` and are
  dropped silently. Cost me one wrong week-13 generation: the API confirmed a save that had no
  effect. The payload should be validated at the edge, or the merge should accept both.
- **OVERRIDE-LOSES-LOAD-SCORE** — sessions created by `apply_day_override` carry no
  `estimated_load_score` (the `new_session` dict simply doesn't set it), so after a day
  override `weekly_load_summary.total_load` no longer reflects the week. Pre-existing
  behaviour, not introduced here, but visible on any replanned week.

## 7. Left open

`trips` is still empty — the Kalymnos trip is not registered as a trip object. Not needed for
this replan, but it means the next macrocycle (goal 8b by 24/10, to be generated on return
around 9/9) will not know the trip happened.
