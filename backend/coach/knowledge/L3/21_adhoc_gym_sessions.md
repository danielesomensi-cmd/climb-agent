# L3 — Adhoc Gym Sessions (on-request session composition)

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC24 (commercial/general-gym session composition) + UC25 (off-plan swap trade-off). NEW file (A237, Adhoc Coach v0).
> **Token target:** ~3,800.
> **Status:** v1.0 — conversational only. The coach composes a session AS TEXT; it does not create, schedule, or log anything.
> **Source files distilled:** the climb-agent exercise catalog (`backend/catalog/exercises/v1/exercises.json`, incl. the C258 commercial-gym batch), CLAUDE.md core principles (deterministic engine, equipment-based filtering, past sessions immutable, D55 spine-safe core), Hörst *Training for Climbing* Ch.6/Ch.8 (antagonist + general-strength programming), plus practical synthesis.

> **Suggest-only firewall (CRITICAL).** You are proposing a session in chat, nothing more. You cannot add it to the plan, schedule it, or log it. Never say or imply you have. When the user wants it saved, point them to the **Session Builder** (custom-session) in the app — that is the only place a session can be stored, and even there logging loads is done by the user. See [[L0_safety_hard_rules]] and the runtime instruction block.

> **Safety firewall (CRITICAL).** A composed session never overrides a safety rule. Warm-up is mandatory before loading fingers or shoulders. Core work is **spine-safe only** (D55): no loaded spinal-flexion crunches or sit-ups, no ballistic loaded rotation — use anti-extension / anti-rotation / compression / hip-hinge patterns. Prescribe load as **RPE/RIR only, never absolute kilograms** — the engine does not know the user's 1RM and neither do you.

---

## Quick reference

Two questions land here:

1. **"I'm at a commercial/general gym — build me a session."** The user is at a barbell/dumbbell/cable/machine gym (a work gym, a hotel gym), not a climbing wall. Compose an antagonist / general-strength session from the catalog's commercial-gym exercises (§5), harmonized with their macrocycle phase (§3) and the surrounding week (§4).
2. **"I don't feel like today's planned session — I'd rather do X."** Do not just bless the swap. Give an honest trade-off between what the plan *needs* today and what the user *wants* (§1, intent B), then compose the alternative if they still want it — always suggest-only, never replanner language.

Compose using the structure in §2, cite **only real catalog exercises** by name (§5 — you have no other exercise vocabulary; do not invent exercises), and keep loads in RPE.

---

## Core findings

### 1. The two intents

**Intent A — commercial-gym session.** The user has equipment but no wall. This is antagonist and general-strength work: it supports climbing (push/pull balance, leg drive, trunk stiffness, prehab) without being climbing-specific. Frame it honestly as *support work*, not a replacement for climbing or finger training. Ask (or infer from context) three things: available time, rough energy today, and any body area they want to hit. Then compose from §5.

**Intent B — off-plan swap.** The user wants to do something other than the planned session. Your job is a trade-off, not rubber-stamping:
- State what today's planned session trains and why it sits where it does in the phase (you can see the plan — see [[01_periodization]]).
- Name the cost of skipping it (e.g. "route-endurance is your power-endurance stimulus this week; dropping it loses that").
- Offer a middle path when one exists ("do a short version of the planned work, then the hangboard you're craving").
- If they still want the swap, compose it — but remind them the plan is unchanged and, to make it count, they can log it as a free/custom session. You are **not** rescheduling anything.

### 2. Session structure

Every composed session follows the same skeleton. Pull sets/reps from each exercise's `prescription_defaults`; state load as RPE/RIR.

1. **Warm-up (5–10 min).** General raise + the specific pattern to be loaded. Before any pressing/pulling: light band or scapular work (`band_pull_apart`, `scapular_pullup`). Before legs: bodyweight squats/hinges. Never skip.
2. **Main blocks (2–4 exercises).** The bulk of the session. Compound first (`back_squat`, `deadlift`, `bench_press`, `overhead_press`, `pullup`/`chinup`), isolation after (`leg_extension`, `leg_curl`, `lateral_raise`, `bicep_curl`, `skullcrusher`, `triceps_cable_pushdown`). 3–4 sets each; RPE 7–8 for strength, RPE 6–7 for accessory, leaving 2–3 reps in reserve.
3. **Optional core / prehab finisher (5–10 min).** One or two spine-safe core items (§6) and/or rotator-cuff prehab (`dumbbell_external_rotation`, `band_external_rotation`, `face_pull`).

Keep total volume matched to the stated time: ~30 min → warm-up + 2 mains; ~60 min → warm-up + 3–4 mains + finisher.

### 3. Phase awareness

Adapt emphasis to the macrocycle phase the coach already receives in context (see [[01_periodization]]):

- **Base / strength_power:** heavier compounds, lower reps (RPE 7–8, 4–6 reps), full rest. This is where general strength fits best — lean into `back_squat`, `deadlift`, `bench_press`, weighted pulls.
- **Power_endurance:** keep gym work lighter and shorter — it is support, not the main stimulus. Higher reps (10–15), shorter rest, RPE 6–7. Do not add heavy CNS-taxing lifts that compete with the phase's climbing work.
- **Performance / taper:** minimise novel loading. Light antagonist + prehab only; nothing that leaves the user sore for a send day (see [[13_tapering_redpoint]]).
- **Deload:** very light, low volume, technique/mobility bias. Do not use a "free gym day" to sneak in hard volume during a deload.

### 4. Harmonization with the surrounding week

You can see the current week plan (each day as a session label) and the last 14 days of logs. Use them:

- **Yesterday (from logs):** if yesterday was high crimp/finger load or hard pulling, go antagonist/general today — push, legs, prehab — and keep pulling volume low. If yesterday was legs, do upper body.
- **Tomorrow (from the week plan — you see the session label/ID, not its exercises):** if tomorrow's session is a finger-strength / max-hangs / hard-pulling day, keep today's pulling and grip volume low so you arrive fresh. If tomorrow is rest, you have more headroom.
- **Never** stack heavy pulling the day before a finger or pulling session; **never** compose something that would leave the user too sore for a planned outdoor/performance day.

You see tomorrow only as a session name — infer its demand from the name plus [[01_periodization]]; do not claim to know its exact exercises.

### 5. Commercial-gym exercise menu (catalog-real only)

Compose ONLY from these. Use the display names; the ID is in backticks.

**Push (chest/shoulders/triceps):** `bench_press` (Bench Press), `dumbbell_bench_press` (Dumbbell Bench Press), `dumbbell_fly` (Dumbbell Fly), `overhead_press` (Overhead Press), `lateral_raise` (Lateral Raise), `skullcrusher` (Lying Triceps Extension / Skullcrusher), `triceps_cable_pushdown` (Triceps Cable Pushdown), `overhead_tricep_extension` (Overhead Tricep Extension), `weighted_dip` (Weighted Dip), `ring_pushup` (Ring Push-up).

**Pull (back/biceps):** `pullup` (Pull-up), `chinup` (Chin-up), `weighted_pullup` (Weighted Pull-up), `weighted_chinup` (Weighted Chin-up), `barbell_row` (Barbell Row), `bicep_curl` (Bicep Curl), `hammer_curl` (Hammer Curl), `reverse_barbell_curl` (Reverse Barbell Curl). (Pulls are climbing-specific — keep them light on antagonist days and near finger/pulling sessions.)

**Legs:** `back_squat` (Back Squat), `goblet_squat` (Goblet Squat), `split_squat` (Split Squat), `deadlift` (Conventional Deadlift), `romanian_deadlift` (Romanian Deadlift), `leg_extension` (Leg Extension, machine), `leg_curl` (Leg Curl, machine), `nordic_curl` (Nordic Hamstring Curl), `standing_calf_raise_loaded` (Loaded Standing Calf Raise).

**Shoulder / elbow prehab:** `dumbbell_external_rotation` (Dumbbell External Rotation), `band_external_rotation` (Band External Rotation), `face_pull` (Face Pull), `band_pull_apart` (Band Pull-apart), `scapular_pullup` (Scapular Pull-up).

**Loaded carries + general:** `farmers_carry` (Farmer's Carry), `suitcase_carry` (Suitcase Carry), `turkish_getup` (Turkish Get-up).

**Core (spine-safe — see §6):** `weighted_plank` (Weighted Plank), `plank` (Plank), `side_plank` (Side Plank), `pallof_press` (Pallof Press), `cable_woodchop` (Cable Woodchop), `back_extension` (Back Extension), `hanging_leg_raise` (Hanging Leg Raise), `weighted_hanging_leg_raise` (Weighted Hanging Leg Raise), `ab_wheel_rollout` (Ab Wheel Rollout).

If the user asks for an exercise not in this menu, offer the closest listed equivalent — do not invent an entry.

### 6. Spine-safe core stance (D55)

The catalog has **no** loaded crunch or sit-up by design (D55: loaded spinal flexion is contraindicated). When composing core, use anti-extension (`plank`, `weighted_plank`, `ab_wheel_rollout`), anti-rotation (`pallof_press`, `cable_woodchop`), compression (`hanging_leg_raise`, `weighted_hanging_leg_raise`), or controlled extension (`back_extension`). If a user asks for weighted crunches, explain the spine-safe swap rather than prescribing them.

### 7. Save / log bridge

If the user wants to keep the session: point them to the **Session Builder** (custom-session) in the app, where they can assemble and save it, then run it with timers. Be honest about today's limitation: the builder does not yet auto-fill loads or log per-exercise results, so the RPE targets you gave are a guide the user enters themselves. You cannot save or log it for them.

---

## Worked example (Intent A, base phase, ~45 min, commercial gym, yesterday was hard crimp bouldering)

*Because yesterday was high finger load, this goes push + legs + prehab and keeps pulling minimal.*

- **Warm-up (8 min):** `band_pull_apart` 2×15; bodyweight squats 2×10; light `bench_press` ramp-up set.
- **Main:**
  - `bench_press` — 4×5, RPE 7–8 (2–3 reps in reserve)
  - `back_squat` — 3×5, RPE 7–8
  - `overhead_press` — 3×8, RPE 7
  - `leg_curl` — 3×10, RPE 7
- **Finisher (7 min):** `dumbbell_external_rotation` 3×15 light (RPE 5–6); `weighted_plank` 3×30s, RPE 7.

*This is antagonist/general support — not a replacement for your climbing or finger work. Want to keep it? Build it in the Session Builder. I can't log it for you.*
