# Analysis D271 — `test_endurance_intermittent`

**Type:** D (analysis, read-only) · **Date:** 2026-08-06 · **Status:** ANALYSIS ONLY — no application code written.
**Implements:** D261 (rev B), D263, D264, D267 — `docs/research/assessment_scoring_research_2026-08.md`
**Closes on approval:** roadmap item D260-P1a
**STOP gate:** `assessment_v1.py` → `macrocycle_v1.py`. Nothing here may be implemented without Daniele's explicit OK.

---

## 0. Executive summary

The test is implementable, but **three findings change what should ship first**, and two of them are
decisions only Daniele can take.

1. **The adoption gate is worse than the brief assumed, and it is measurable.** 60% of the max-hang
   total is below bodyweight for anyone under **166.7% BW**. Of the 18 production profiles, **10 have
   a usable max-hang base at all**; of those 10, **eight need to be unloaded** (by 2.8 kg to 37.6 kg),
   one lands at exactly bodyweight, and the only user who would *add* weight is `e60d7a0c`, whose
   finger data is already flagged as internally incoherent (A266-P1). In practice **no production
   user can perform this test today with added weight only.** Without an unloading mechanism the test
   ships to nobody.
2. **The scored outcome carries finger strength multiplicatively.** At a fixed *relative* load of 60%,
   `impulse = 0.6 × (max_hang_total / BW) × time_to_failure`. The strength term spans **1.95×** across
   our own users (0.90 → 1.76 × BW). Holding time-to-failure constant at 100 s, impulse alone spans
   **54 → 106 kg·s·kg⁻¹** — the entire Berta scale, crossed by strength with zero endurance
   information. This is structurally the same contamination D263 rejected the bodyweight hang for,
   arriving through a different door. **The spec is not redesigned here** (the brief forbids it), but
   the finding is on the table and §5.4 proposes what to store so the decision stays open.
3. **An absolute band→score mapping cannot honestly ship in v1.** Our protocol produces impulses
   around 90–105 kg·s·kg⁻¹ for a strong climber where Berta's 8b–9a+ median is 58.5. The protocols
   differ by roughly 1.6×, exactly as D267 predicted. Mapping our numbers onto their bands would put
   most users at a clamped 100 on day one.

**Recommended shape:** ship the test in **two stages** — Stage 1 collects and displays, keeps the
Endurance axis explicitly `estimated`; Stage 2 flips it to measured once ~30 own results exist to
calibrate on. Details and the alternative in §5.

---

## 1. Insertion point in the assessment flow

### 1.1 Where tests are collected today

Three paths write `assessment.tests`:

| Path | File | Notes |
|---|---|---|
| Onboarding wizard, step `tests` | `frontend/src/app/onboarding/tests/`, `POST /api/onboarding/complete` | `TEST_DESCRIPTIONS` in `backend/api/routers/onboarding.py:126` drives the copy; `_build_tests_source` stamps every entered scalar `"measured"` |
| Settings editor | `frontend/src/components/settings/profile-assessment-editor.tsx` | Free edit of the same scalars |
| In-app test sessions | `planner_v2` pass 3 → guided session → `progression_v1._TEST_FIELDS` | `test_max_hang_7s`, `test_repeater_7_3`, `test_lp_max_5s`, `test_lp_repeater`, `test_max_weighted_pullup`, `test_pullup_bw` |

The in-app path is the one that matters: `planner_v2._PHASE_TEST_MAP` (line 80) gates *which* axes get
retested per phase, `TEST_FRESHNESS_DAYS = 42` prevents retesting inside 6 weeks, and
`MAX_WEEKS_UNTESTED = 12` forces a maintenance retest regardless of phase.

### 1.2 Recommended order — LAST, and in its own session

**Within a test session, place it last.** The test needs the athlete warm and it is a to-failure
effort, so anything scheduled after it is compromised. But the stronger recommendation is that it
should **not share a session with `test_max_hang_7s`**: the max hang *is* the source of the 60% base,
and a max-hang effort minutes earlier both invalidates the base (a fatigued max is low) and depresses
the endurance result. Two options, in preference order:

- **(a) Own test session `test_endurance_intermittent`** (recommended), scheduled by pass 3 like the
  others, with its own catalog entry mirroring `backend/catalog/sessions/v1/test_repeater_7_3.json`
  (that file is 40 lines: `required_equipment`, two modules — `general_warmup` + a primary template —
  `tags.test: true`, `test_id`). A dedicated session also lets the safety gates in §4 live in the
  session rather than being bolted onto an existing one.
- **(b) Appended to the existing repeater test session.** Cheaper, but the repeater is *itself* run at
  60% of the max hang to failure — running both in one session measures the second one's recovery,
  not its endurance. Not recommended.

### 1.3 Which field supplies the 60% base

Same precedence `_compute_finger_strength` already uses (`assessment_v1.py:326`):

```
max_hang_20mm_7s_total_kg  →  max_hang_20mm_5s_total_kg  →  loading_pin_two_hand_equivalent(tests, bw)
```

The loading-pin branch matters: 4 of the 10 users with a usable base have **only** a pin number
(A266). Note the pin equivalent is itself a conversion (×1.85 on the two-hand average), so the 60%
target for those users inherits that conversion's uncertainty — worth recording alongside the result
(§2).

### 1.4 Staleness rule for the base

`TEST_FRESHNESS_DAYS = 42` is the repo's existing answer to "how old is too old" and there is no
reason to invent a second number. Proposal:

- Base age ≤ 42 days → use it.
- Base age 43–84 days → use it, but store `base_stale: true` on the result so a later recalibration
  can exclude those rows.
- Base age > 84 days (= `MAX_WEEKS_UNTESTED` at 12 weeks) or `tests_source != "measured"` → **do not
  offer the test**. A 60% target computed from a grade-estimated max hang is a fabricated load applied
  to real tendons. `_build_tests_source` (`onboarding.py:253`) already gives us this signal for free:
  missing key ⇒ readers default to `"estimated"`.

---

## 2. Data model — additive only

Nothing existing changes shape. Three additions, all new JSONB paths:

```
assessment.tests.endurance_intermittent_impulse        : float   # kg·s·kg⁻¹, the scored outcome
assessment.tests_source.endurance_intermittent_impulse : "measured"

tests.endurance_intermittent : [                       # append-only history, mirrors
  {                                                    # tests.repeater_strength_endurance
    "date": "2026-09-14",
    "scoring_version": "endurance_v0_raw",
    "impulse_kg_s_per_kg": 92.5,
    "reps_completed": 12,
    "work_seconds": 96,
    "load_kg_total": 73.2,                  # what was ACTUALLY on the fingers
    "load_kg_target": 73.2,                 # what 60% asked for
    "assistance_kg": 2.8,                   # >0 = unloaded; 0 = bodyweight; <0 = added
    "assistance_method": "pulley_system" | "band" | "added_weight" | "bodyweight",
    "bodyweight_kg": 76.0,
    "base_max_hang_total_kg": 122.0,
    "base_source": "max_hang_20mm_7s_total_kg" | "loading_pin_equivalent",
    "base_measured_at": "2026-08-20",
    "base_stale": false,
    "edge_mm": 20,
    "grip": "half_crimp" | "open",
    "termination": "grip_opened" | "user_stopped" | "aborted_pain"
  }
]
```

Two points that are not optional:

- **`load_kg_total` is the actual load, not the target.** A band gives whatever it gives; rounding to
  available plates gives whatever it gives. Recording the intent instead of the reality makes every
  future recalibration (D267) meaningless.
- **`scoring_version` on every row.** D267 requires it. See §7.

`assessment.profile.endurance` keeps its current key and range. Nothing in `user_state`'s existing
schema is modified, so no migration is needed for users mid-cycle (§9).

---

## 3. The assistance problem — this is the adoption gate

### 3.1 The arithmetic, on real users

60% of the max-hang total is ≥ bodyweight only when `max_hang_total ≥ BW / 0.6 = 166.7% BW`.

| user | BW | max-hang total | %BW | 60% target | as %BW | what the athlete must do |
|---|---|---|---|---|---|---|
| `e60d7a0c` | 67.0 | 117.9 (pin) | 176.0 | 70.8 | 105.6 | **add 3.8 kg** — but this profile is flagged incoherent (A266-P1) |
| `7208f92f` | 72.0 | 120.0 | 166.7 | 72.0 | 100.0 | bodyweight exactly |
| `7ea9f0ee` (author) | 76.0 | 122.0 | 160.5 | 73.2 | 96.3 | **unload 2.8 kg** |
| `5a98187c` | 66.0 | 90.0 | 136.4 | 54.0 | 81.8 | unload 12.0 kg |
| `22080848` | 68.0 | 92.0 | 135.3 | 55.2 | 81.2 | unload 12.8 kg |
| `f8ff8569` | 66.0 | 85.1 (pin) | 128.9 | 51.1 | 77.4 | unload 14.9 kg |
| `f49678eb` | 68.0 | 87.0 | 127.9 | 52.2 | 76.8 | unload 15.8 kg |
| `79fadc50` | 68.0 | 67.5 (pin) | 99.3 | 40.5 | 59.6 | unload 27.5 kg |
| `d7f6083e` | 65.0 | 62.9 (pin) | 96.8 | 37.7 | 58.1 | unload 27.3 kg |
| `9e4154d4` | 82.0 | 74.0 | 90.2 | 44.4 | 54.1 | unload 37.6 kg |

The remaining **8 of 18** profiles have no max hang and no pin number at all — for them the test does
not exist regardless of equipment.

The author's own case is the mild one and still needs unloading. **The test is unavailable to
essentially the entire current user base unless we solve unloading.**

### 3.2 Equipment — reuse `band`, add `pulley_system`

The brief proposes two new entries. Only one is new:

- **`assistance_band` already exists as `band`.** `docs/vocabulary_v1.md:36` defines `band` and
  `onboarding.py:90` labels it *"Assistance band — elastic band for assistance or resistance"*.
  The vocabulary explicitly forbids introducing variants of a canonical ID. **Adding
  `assistance_band` would be a duplicate.**
- **Real gap found:** `band` is in `EQUIPMENT_HOME` but **not in `EQUIPMENT_GYM`**
  (`onboarding.py:99` vs `104–125`). A user who only trains at a gym cannot declare it. That is a
  one-line catalog fix and a prerequisite for this test.
- **`pulley_system` is genuinely new** and must be added to `KNOWN_EQUIPMENT_KEYS`
  (`backend/engine/equipment_utils.py:51`), `docs/vocabulary_v1.md` §1.2, `EQUIPMENT_HOME` and
  `EQUIPMENT_GYM`. No implication rule needed (it implies nothing and nothing implies it).

**They are not interchangeable, and the difference matters for a measurement:**

| | `pulley_system` (counterweight) | `band` |
|---|---|---|
| Assistance profile | Constant through the hang | Varies with stretch |
| Quantifiable | Yes — the counterweight is a number | Only nominally ("15 kg band" is a range) |
| Suitable for a **scored** test | Yes | Marginal — record it, flag it |

Recommendation: `pulley_system` makes the test **scorable**; `band` makes it **performable**. A result
obtained on a band should carry `assistance_method: "band"` and be excluded from the calibration
dataset in §7, while still being shown to the user.

### 3.3 Behaviour when the target is below BW and no assistance equipment exists

```
if target_load < bodyweight and not (pulley_system or band available):
    → test is NOT offered (not scheduled by pass 3, not shown in the wizard)
    → assessment.profile.endurance keeps its current derivation (0.8 × PE + tenure + hang duration)
    → assessment.profile_source.endurance = "estimated"
```

`profile_source` is the piece that does not exist yet. Today `tests_source` records provenance for
*inputs* (D214) but nothing records it for *axes* — which is D260 finding #7, the "50 problem": a
silent default is indistinguishable from a measurement downstream. Introducing
`assessment.profile_source: {axis: "measured" | "estimated"}` here **finally makes D260's hidden
default honest**, and Package 3 already built the UI half: `A267`'s radar renders a null axis as a
greyed em dash with an explicit "no benchmark" line rather than a number. The same grey treatment
should apply to an `estimated` axis in Goal mode.

**This is a decision point for Daniele:** introducing `profile_source` touches every axis, not just
endurance, and makes visible on four other axes that they are estimates too. That is the honest
outcome and it is also a visible product change.

### 3.4 Rounding and tolerance

- Round the target to the nearest **0.5 kg** when a pulley/plate stack allows it, **1 kg** otherwise.
- Accept anything within **±5%** of the target as a valid test; outside that, store it but mark
  `base_stale`-style with an explicit `off_target: true` and exclude from calibration.
- Always store `load_kg_total` (actual) next to `load_kg_target` (§2). The score is computed from the
  actual, never from the target — otherwise a 15% band error silently becomes a 15% score error.

---

## 4. Safety gates

The test is a to-failure finger effort at moderate load for ~90–110 s. The existing safety furniture
to reuse rather than reinvent:

- `resolve_session.py` Stage 2e blocks advanced hangboard work for `climbing_years < 2`, and
  explicitly **never blocks test sessions** (`docs/vocabulary_v1.md:336`). That exemption was written
  for single maximal measurements. **A to-failure endurance hang is a different animal** and the
  exemption should be reviewed for this test specifically — recommend gating it on
  `climbing_years ≥ 2` like training hangboard work.
- `limitations` already carries per-area entries (`finger` among them, `onboarding.py` limitation
  areas).

Proposed gates, in order:

1. **Warm-up confirmation step, mandatory.** The guided session must not advance to the primary block
   until the athlete taps a confirmation. Copy: *"Fingers warm? This is a to-failure hang — a cold
   start is how pulleys get hurt. Confirm you've done the warm-up above."*
2. **Contraindication screen before the first rep.** If `limitations` contains a finger/pulley entry
   with an onset inside the last 12 weeks, or the athlete answers yes to *"Any finger pain in the last
   4 weeks?"* → **skip the test**, do not reschedule this cycle, and set
   `profile_source.endurance = "estimated"`. A skipped test must never read as a bad result.
3. **Abort-on-grip-opening copy.** The termination criterion is the grip opening, not the athlete
   letting go from pain. Copy: *"Stop the moment the grip starts to open — that is the result. If you
   feel a sharp or localised pain instead, stop and tap Abort: it is not a result and we will not
   score it."* → `termination: "aborted_pain"` stores the row and marks it unscored.
4. **No adjacency to other max finger work.** `planner_v2` already enforces a 48 h finger gap
   (`_reconcile`, B287) and hard-day caps. This test must be registered as a **hard, finger-domain**
   session so it inherits those rules automatically — not added as a low-cost extra. Additionally it
   must not be scheduled in the same week as `test_max_hang_7s`/`test_lp_max_5s`, because a fresh max
   hang is its input, not its neighbour (see §1.2).
5. **Phase gating.** `_PHASE_TEST_MAP` already models this. The endurance test belongs where the
   repeater already sits — `base: True`, `power_endurance: True`, `strength_power: True`,
   `performance: False`, `deload: False`.

---

## 5. Scoring proposal

### 5.1 The band table, as data

The Berta bands (C267 §2) must live in a **versioned data table**, not as literals in a formula —
the same lesson D260 §7 recorded when it found `_PE_REPEATER_BENCHMARK` unsourced in the code:

```python
# backend/catalog/assessment/endurance_bands_v1.json  (proposed location)
{
  "version": "endurance_bands_v1",
  "source": "Berta et al. 2025, J Sports Sci 43(3):245-255, supplementary data",
  "protocol": "one hand, 23mm, dynamometer — NOT climb-agent's protocol (D267)",
  "metric": "intermittent impulse, kg.s.kg-1",
  "bands": [
    {"from": "5a",  "to": "6b+", "p10": 20.0, "p50": 29.5, "p90": 46.5},
    {"from": "6c",  "to": "7b",  "p10": 23.2, "p50": 37.3, "p90": 52.0},
    {"from": "7b+", "to": "8a+", "p10": 33.1, "p50": 48.9, "p90": 65.7},
    {"from": "8b",  "to": "9a+", "p10": 47.9, "p50": 58.5, "p90": 79.4}
  ]
}
```

### 5.2 The mapping, coherent with Finger/Pulling

Finger and Pulling both do `score = (measured / benchmark_for_target_grade) × 100`, clamped. The
coherent endurance analogue is:

```
score = (impulse / p50_of_band_containing(target_grade)) × 100      clamped [0, 100]
```

100 therefore means "at the median of climbers who operate at your target grade" — the same sentence
B304 already puts under the radar ("100 means you're already there").

### 5.3 Why this cannot ship as-is in v1 — worked examples

| athlete | target | band p50 | plausible impulse | raw score |
|---|---|---|---|---|
| **author** `7ea9f0ee`, BW 76, hang 122 | 8b | 58.5 | 0.6 × 1.605 × 96 s = **92.5** | 158 → **clamped 100** |
| a 6c user (`ce8914f0` shape), BW 68, hang ~68 | 7b | 37.3 | 0.6 × 1.00 × 96 s = **57.6** | 154 → **clamped 100** |
| no-equipment user (`3fc2a699`, no hang at all) | 7b | — | — | **test unavailable → `estimated`** |

Both scorable users clamp to 100 on day one. That is not a coincidence and not a bug in the examples:
Berta's protocol is a maximal intermittent effort on a **dynamometer, one hand, 23 mm**; ours is a
**two-arm 20 mm hang at 60% of the athlete's own max**, and the design target is 90–110 s of work.
The two produce numbers roughly 1.6× apart. Mapping ours onto their percentiles reproduces exactly
the ceiling-saturation failure D260 documented for Finger and Pulling — this time on day one, for
everyone. **D267 anticipated this; the numbers confirm it.**

### 5.4 Finding E-1 — the metric carries finger strength

At a fixed *relative* load:

```
impulse = load × work_seconds / BW = 0.6 × (max_hang_total / BW) × time_to_failure
```

`max_hang_total / BW` spans **0.902 → 1.760 (1.95×)** across the ten production users who have a
base. Holding time-to-failure at 100 s, impulse alone would span **54 → 106 kg·s·kg⁻¹** — wider than
the whole Berta table — with **zero** endurance signal in it.

D263 excluded the bodyweight hang from this axis precisely because 65% M / 80% F of its variance is
finger strength. The same mechanism is present here, structurally, because the load is defined as a
fraction of finger strength. In Berta's protocol impulse is a legitimate composite because the effort
is maximal, not relative; in ours the relative-load normalisation is undone by multiplying the load
back into the score.

The brief forbids redesigning the spec and this analysis does not. What it recommends instead:

- **Store `work_seconds` and `reps_completed` on every row** (already in §2). Time-to-failure at a
  fixed relative intensity is the strength-free half of the measurement, and it costs nothing to keep.
- **Put the choice in front of Daniele explicitly** (§10, Q3): score on impulse as decided, on
  time-to-failure, or on both with impulse displayed and time-to-failure driving the axis.

### 5.5 Recommendation — two stages

**Stage 1 (ships with the test).**
- Collect, store the full row from §2 with `scoring_version: "endurance_v0_raw"`.
- **Display** to the athlete: reps completed, work seconds, impulse, and their position within their
  *own current* grade band, described in words ("above the median for climbers at your grade") — a
  descriptive band position is defensible where an absolute score is not.
- The Endurance **axis stays derived** (`0.8 × PE + tenure + hang duration`) and is flagged
  `profile_source.endurance = "estimated"` for everyone. That flag is the honest part: it is true
  today and nobody is told.
- **No macrocycle change at all.** Zero risk to live plans.

**Stage 2 (after ~30 valid results, `assistance_method != "band"`, `off_target: false`).**
- Fit a single documented `PROTOCOL_TRANSFER_FACTOR` from our own data against the band medians, or
  replace the Berta medians outright with our own p50 per band if the sample allows.
- Bump to `scoring_version: "endurance_v1"`, flip the axis to measured, `profile_source` → `measured`.
- Applies **from the next assessment onward only** (§6, §9). No retroactive rescoring.

**The alternative** (ship §5.2 immediately, accept that most users clamp at 100, version it and
recalibrate later) is faster and gives the axis a number now. It is worse for exactly the reason
D260 documented: a clamped 100 carries no signal, reads to the user as a bug, and — unlike the
strength axes, where 100 at least means "you met your target benchmark" — here it would mean nothing
at all. Recommended against, but it is Daniele's call.

---

## 6. Macrocycle impact

### 6.1 Where Endurance enters

Two levers, both in `macrocycle_v1.py`, both read `profile["endurance"]`:

- **`_adjust_domain_weights` (line 423):** `endurance → volume_climbing`. `< 35` → +0.10, `< 50` →
  +0.05, `> 75` → −0.03, then renormalise.
- **`_find_weakest_axis` (line 289) → `_WEAKNESS_ADJUSTMENTS` (line 236):** `endurance → (extend
  "base", shrink "strength_power")`, fired only when endurance is the single lowest axis **and** < 50.

A third, indirect: `_profile_conditional_additions` (line 498) unlocks sessions for axes below
`WEAK_AXIS_THRESHOLD` — check whether any rule keys on `endurance` before changing its distribution.

### 6.2 Snapshot vs live — global rule 3 verified

`generate_macrocycle` writes `assessment_snapshot` (line 760) into the macrocycle, and
`planner_v2`/`planner_v1` write `profile_snapshot` into each week plan. `replanner_v1` reads
`plan["profile_snapshot"]` in **eleven** places and never re-reads `assessment.profile`.
`state_checks.py:33` compares the live profile against `assessment_snapshot` only to *report*
staleness (`is_macrocycle_stale`), never to mutate.

**Conclusion: an active macrocycle is not re-weighted in place by a changed axis score.** The new
score reaches the plan only through an explicit regeneration — the user tapping regenerate on `/plan`,
or `start-new-cycle`. This satisfies global rule 3 without any new guard. It must be **re-verified**
if the implementation ever recomputes the profile inside a week-generation path.

### 6.3 Expected weight shifts — author + 4 testers

Computed by calling the real `_adjust_domain_weights` on each user's stored profile, varying only the
endurance axis. `volume_climbing` is the only weight endurance moves.

| user | disc / target | EN now | vol now (base / strength / PE / perf) | EN<35 | EN 35–49 | EN 50–75 | EN>75 |
|---|---|---|---|---|---|---|---|
| `7ea9f0ee` (author) | lead 8b | 51 | .229 / .096 / .144 / .240 | .294 / .175 / .219 / .307 | .263 / .138 / .183 / .275 | **.229 / .096 / .144 / .240** | .208 / .069 / .119 / .218 |
| `79fadc50` | lead 8a | 52 | .238 / .100 / .150 / .250 | .304 / .182 / .227 / .318 | .273 / .143 / .190 / .286 | **.238 / .100 / .150 / .250** | .216 / .072 / .124 / .227 |
| `9e4154d4` | all_round 7a+ | 34 | .312 / .187 / .234 / .327 | **.312 / .187 / .234 / .327** | .280 / .147 / .196 / .294 | .245 / .103 / .155 / .258 | .222 / .074 / .128 / .234 |
| `f8ff8569` | boulder 9a | 54 | .333 / .095 / .190 / .286 | .391 / .174 / .261 / .348 | .364 / .136 / .227 / .318 | **.333 / .095 / .190 / .286** | .314 / .069 / .167 / .265 |
| `e60d7a0c` | boulder 8a | 64 | .318 / .091 / .182 / .273 | .375 / .167 / .250 / .333 | .348 / .130 / .217 / .304 | **.318 / .091 / .182 / .273** | .299 / .065 / .159 / .252 |

Read: **four of the five sit in the 50–75 dead band today**, so a real endurance score changes nothing
unless it lands below 50 or above 75. `9e4154d4` is already below 35. The largest single move is
`strength_power`'s `volume_climbing` going from .096 to .175 (+7.9 pp) if the author's endurance
turned out to be under 35 — comparable in size to the technique distortion D260 flagged.

Note also how narrow the current margin is: author 51, `79fadc50` 52, `f8ff8569` 54 all sit **1–4
points above the < 50 cliff**, on a derived number. A real measurement landing at 48 instead of 51
flips a real weight decision. That fragility is D260 issue #5 and it is not fixed by this test — it is
made more consequential by it.

### 6.4 Phase durations

| user | discipline | EN now | durations now | durations if EN < 50 |
|---|---|---|---|---|
| `7ea9f0ee`, `79fadc50` | lead | 51, 52 | 4/3/2/2/1 | **4/3/2/2/1 — unchanged** |
| `9e4154d4` | all_round (lead durations) | 34 | 4/3/2/2/1 | **4/3/2/2/1 — unchanged** |
| `f8ff8569` | boulder | 54 | 2/5/1/3/1 | **3/4/1/3/1** — Base +1, Strength −1 |
| `e60d7a0c` | boulder | 64 | 2/5/1/3/1 | **3/4/1/3/1** (only if endurance becomes the *single* lowest — pulling is 43 today) |

**Lead is a silent no-op** because `_PHASE_FLOORS_LEAD["base"] == _PHASE_CAPS_LEAD["base"] == 4`: the
shift is discarded by the clamp at `macrocycle_v1.py:372`. This is D260 issue #5 restated — for lead
athletes the endurance axis can never move a phase duration, no matter what it measures. **For
boulder athletes it can, and it costs a week of Strength/Power.** Worth stating plainly to Daniele
before a real number starts driving it.

---

## 7. Versioning plan for `scoring_version`

`scoring_version` does not exist anywhere in the codebase today (`user_state.json` has
`schema_version`, which is a different thing). Proposal:

- **Scope: per-result, not global.** It lives on each row of `tests.endurance_intermittent`, so a
  recalibration never silently reinterprets old rows. This is what D267 asks for.
- **Values:** `endurance_v0_raw` (Stage 1 — stored, displayed, not scored into the axis),
  `endurance_v1` (Stage 2 — calibrated on own data). The band table carries its own independent
  `endurance_bands_v1` version so a table swap and a formula change are distinguishable.
- **Recomputation policy:** **never retroactive.** Existing rows keep their version and their stored
  score. A new version applies from the next assessment onward — the same rule global constraint 2
  states and the same one D260 open question 1 asks about for Finger/Pulling.
- **Coordination with D272.** The gap demotion changes Technique and Power Endurance scoring. If both
  ship, they must share **one** profile-level version stamp, e.g.
  `assessment.profile_scoring_version`, so that "which rules produced this radar" is answerable with
  one field instead of five. Recommend introducing that field with whichever of the two lands first,
  and treating `profile_source` (§3.3) as its companion.

---

## 8. Test plan

### 8.1 Unit — scoring (`test_d271_endurance_scoring.py`)

- Band lookup: every grade in `GRADE_ORDER` maps to exactly one band; boundaries (`6b+`/`6c`,
  `7b`/`7b+`, `8a+`/`8b`) land on the intended side; a Font boulder grade resolves through
  `resolve_grade` first (the B321 lesson).
- Score monotonic in impulse; clamped at 0 and 100; above-median clamps rather than overflows.
- Missing impulse → axis falls back to the derived value **and** `profile_source == "estimated"`.
- `assistance_method == "band"` → row stored, excluded from calibration set.
- `termination == "aborted_pain"` → row stored, **not** scored, axis stays `estimated`.
- Actual load ≠ target load → score uses the actual.

### 8.2 Fixtures that do not exist yet — including the elite one

D260 §7 (B.6) found that saturation shipped because *"there is no fixture of an elite user with a
matching high target where the score is expected to still discriminate at the top."* Required
fixtures:

| fixture | purpose |
|---|---|
| **Elite** — target 9a, hang 200% BW, high impulse | asserts the score **discriminates** at the top, not merely that it is ≤ 100 |
| **Author** — `7ea9f0ee` exact production payload | regression against a real profile, as B321 did |
| **Loading-pin only** — `79fadc50` payload | base comes from the pin conversion; needs 27.5 kg assistance |
| **No base** — `3fc2a699` payload | test never offered; axis `estimated`; nothing crashes |
| **Beginner** — `climbing_years: 1` | safety gate blocks the test |
| **Finger limitation** | contraindication screen path |

### 8.3 Integration

- Pass 3 scheduling: the endurance test appears in `base`/`power_endurance`/`strength_power`, never in
  `performance`/`deload`; never in the same week as a max-hang test; respects
  `TEST_FRESHNESS_DAYS = 42` and the 48 h finger gap.
- **Past-session immutability** (global rule 1): generate a plan, complete sessions, submit an
  endurance test result, regenerate — assert `session_completion_log`, `feedback_log`, past
  `week_plans`, `working_loads` are byte-identical. This is the invariant CLAUDE.md requires after
  any change that triggers regeneration.
- **Snapshot isolation** (global rule 3): change `assessment.profile.endurance`, assert the live
  macrocycle's `assessment_snapshot` and every `profile_snapshot` are unchanged and the plan's domain
  weights do not move until an explicit regeneration.
- Equipment: a user with neither `pulley_system` nor `band` and a sub-bodyweight target is never
  offered the test, at any entry point.

---

## 9. Migration and compatibility

- **Users mid-cycle:** nothing to migrate. All additions are new keys; absent keys behave exactly as
  today (`_compute_endurance` already treats missing tests as "no modifier"). A user halfway through a
  12-week plan sees no change until they regenerate.
- **`profile_source` back-fill:** do **not** back-fill it as `"measured"`. Absent ⇒ `"estimated"`,
  matching how `tests_source` already behaves (`_build_tests_source` docstring: *"Missing keys are
  omitted — readers default to `estimated`"*). Anything else would claim measurements we never made.
- **Radar display, coordinated with A267.** Package 3 already renders an axis with no data as a greyed
  em dash plus an explicit reason line, in Elite mode. The same treatment should extend to Goal mode
  for `estimated` axes — one shared "greyed axis" presentation, two reasons (no elite benchmark / not
  measured). The component change is small because `axisValue()` already returns `number | null` and
  the null branch is built.
- **Coach:** the coach payload includes the axis scores. When `profile_source.endurance ==
  "estimated"` the payload should say so, or the coach will speak about an endurance measurement that
  does not exist — the same class of fabrication B305 fixed in the ad-hoc composer.

---

## 10. Open questions for Daniele

1. **Assistance equipment — ship it, or ship the test to nobody?** Adding `pulley_system` (and putting
   the existing `band` into the gym list) is the difference between 0 and ~8 of 18 users being able to
   take the test. Confirm both catalog changes.
2. **`profile_source` — make estimation visible?** It is the honest fix to D260's "50 problem", and it
   will grey out or caveat axes on radars that today show confident numbers for four other axes too.
   Product decision.
3. **Score on impulse, on time-to-failure, or both (§5.4)?** As specified, the metric multiplies
   finger strength back into an endurance axis. Not redesigned here; needs a decision.
4. **Stage 1 + Stage 2, or ship the absolute mapping now (§5.5)?** The two-stage plan gives an honest
   axis later; the direct mapping gives a clamped-100 axis now.
5. **Lead athletes can never move a phase duration on this axis (§6.4).** Base is floor == cap == 4
   for lead. Accept, or revisit `_PHASE_FLOORS_LEAD` — which is a `macrocycle_v1` change and a
   separate high-risk brief (see also T1/D44 in the KB consolidation, deferred since C263).
6. **Does the ≥ 2 years hangboard gate apply to this test?** Test sessions are currently exempt by
   design (`vocabulary_v1.md:336`), an exemption written for single maximal efforts, not to-failure
   ones (§4).

---

*End of analysis D271. No application code written. Awaiting Daniele's decisions before any implementation brief.*
