# Analysis D272 — Demoting the redpoint − onsight gap

**Type:** D (analysis, read-only) · **Date:** 2026-08-06 · **Status:** ANALYSIS ONLY — no application code written.
**Implements:** D266 — `docs/research/assessment_scoring_research_2026-08.md`
**Closes on approval:** roadmap item D260-P1b
**STOP gate:** `assessment_v1.py` → `macrocycle_v1.py`. Nothing here may be implemented without Daniele's explicit OK.

---

## 0. Executive summary

The gap has exactly **two** consumers in the whole codebase — `_compute_power_endurance` and
`_compute_technique`, both in `assessment_v1.py`, both through the single helper
`_redpoint_onsight_gap`. Demoting it is a small, contained change. What it *exposes* is not small.

- **Recommendation: option (c)** — Technique & Tactics becomes a `self_reported` axis, greyed like
  A267's benchmark-less axes and excluded from the weight and duration machinery. It fixes the
  double-counting, it removes the largest plan distortion D260 found, and it is the only option that
  does not require inventing a cap out of thin air.
- **Reversing D260's finding, quantified on the author's real profile:** technique's domain weight in
  the Base phase falls from **.275 back to .202 (−7.3 pp)**, and by −7.1 to −8.6 pp in every other
  phase. That is the distortion D260 called *"the actual distortion… applied in every phase, driven
  entirely by TT 30."*
- **Power Endurance improves rather than collapses — for the three users who have a repeater.** With
  the gap gone, the author's objective repeater stops being diluted 40/40 and PE goes **53 → 70**.
  But **only 3 of 18 production users have a repeater on file**. For the other 15, PE after the
  demotion measures *nothing* and must say so (`estimated`), not quietly sit at 50.
- **Endurance moves with PE** (it is `0.8 × PE`), so D271 and D272 interact. `79fadc50` crosses the
  `< 50` weight cliff on both PE (54 → 49) and Endurance (52 → 48) purely as a knock-on. The two
  briefs must land together or in a stated order (§7).
- **One implementation trap:** `_find_weakest_axis` defaults a *missing* axis to 50
  (`macrocycle_v1.py:299`). Deleting `technique` from the profile does not remove it from
  consideration — it turns it into a phantom 50 that can win the "weakest" title. It must be removed
  from the tuple at line 297, explicitly.

---

## 1. Full consumer map

### 1.1 The gap itself

`_redpoint_onsight_gap(grades)` — `backend/engine/assessment_v1.py:206`. Tries
`lead_max_rp`/`lead_max_os`, then `boulder_max_rp`/`boulder_max_os` (B321), resolving Font → lead.
Returns `None` when neither pair is complete.

**Call sites: two. Both in the same file.**

| Consumer | File:line | Use |
|---|---|---|
| `_compute_power_endurance` | `assessment_v1.py:392` | `gap_score` buckets 75/55/40/30; weighted 40% (with repeater) or 60% (without); the self-eval term is `(gap_score + eval_modifier)`, i.e. the gap is inside the self-eval term too |
| `_compute_technique` | `assessment_v1.py:434` | `gap_score` buckets 80/60/40/30, then `+ _weakness_penalty(self_eval, "technique")`. **Nothing else.** |

**Everything else that touches redpoint/onsight grades is unrelated to the gap** and must not be
disturbed:

| Site | What it does |
|---|---|
| `api/deps.py:603–614` | Mirrors grades into `performance.current_level` |
| `engine/outdoor_pitch_ladder.py` (via `routers/outdoor.py:416,447`) | A265 pitch ladder — uses onsight/redpoint **absolutely**, not as a gap |
| `engine/milestones_v1.py:181–343` | Onsight milestones from the outdoor log |
| `coach/prompt_builder.py:130–132` | Prints RP and OS in the athlete-profile block |
| `routers/public_assessment.py:118` | Rejects OS > RP with 422 — and its comment already names the coupling: *"the gap drives both technique and power-endurance"* |
| `frontend/.../onboarding/grades/page.tsx:114,133` and `assessment/page.tsx:359` | Copy telling the user the gap "reveals technique and power endurance" — **must be rewritten**, it will no longer be true |

### 1.2 The Technique & Tactics score

| Consumer | File:line | Effect |
|---|---|---|
| `_adjust_domain_weights` | `macrocycle_v1.py:439` | `technique → technique` weight. `< 35` → +0.10, `< 50` → +0.05, `> 75` → −0.03, then renormalise. **This is the largest single lever D260 found.** |
| `_find_weakest_axis` | `macrocycle_v1.py:297` | `technique` in the candidate tuple; if it is the single lowest **and** `< 50`, `_WEAKNESS_ADJUSTMENTS["technique"] = ("base", "performance")` extends Base by 1 week at Performance's expense |
| `_PROFILE_CONDITIONAL_SESSIONS` | `macrocycle_v1.py:475` | Only rule today keys on `pulling_strength`. **No technique rule — nothing to change here**, but a future rule must not be added without revisiting this. |
| `state_checks._PROFILE_AXES` | `state_checks.py:15` | `technique` counts toward `is_macrocycle_stale` (any axis moving ≥ 5 points flags the plan stale) |
| `coach/prompt_builder._profile_section` | `prompt_builder.py:140–145` | Prints all five axes and names the two weakest |
| `routers/public_assessment.py:52,59` | `_AXIS_PRIORITY` puts technique **last** in tie-breaks — the public page already treats it as the least actionable answer |
| Frontend | `gradeUtils.ts:178,186,249`, `radar-chart.tsx:29`, `plan/page.tsx:39`, `eliteAnchors.ts:87`, `types.ts:9` | Labels, radar axis, tooltip copy; A267 already renders it permanently greyed in Elite mode |

**Not a consumer:** no session template, no resolver filter and no replanner intent reads
`profile.technique`. The `technique_focus_gym` session is selected by *domain weight*, not by the
axis directly. So the blast radius of changing the axis is: domain weights, phase durations, staleness
flag, coach text, radar display. That is all.

### 1.3 The double-counting, stated precisely

`_compute_technique` = `gap_bucket + weakness_penalty`. The weakness penalty fires on
`technique_errors`, `cant_read_routes`, `poor_body_tension`, `poor_problem_reading`,
`poor_dynamic_movement` (`_AXIS_WEAKNESS_PENALTIES`, line 192). A climber whose onsight lags their
redpoint is *very likely* to also tick "technique errors" or "can't read routes" — the two inputs are
not independent, they are two readings of the same self-perception. The author is exactly this case:
gap 5 → 40, minus 10 for a self-declared `technique_errors` → **30**.

In PE the double-count is structurally worse: the formula is
`repeater*0.4 + gap*0.4 + (gap + eval)*0.2` — the gap appears in **two** of the three terms, so it
carries 60% of the score (weight 0.4 + 0.2) while the only objective input carries 40%.

---

## 2. Post-gap Technique & Tactics — three options

Common to all three: `_compute_technique` stops calling `_redpoint_onsight_gap`.

### (a) Self-report only, with a hard cap on weight influence

TT = neutral 50 + `_weakness_penalty(self_eval, "technique")` → range **40–50** (−10 primary, −5
secondary, 0 otherwise). Then cap the technique weight delta at **±0.02** so no single subjective
input can move a weight anywhere near 7.5 pp.

- ✅ Keeps an axis on the radar with a number.
- ✅ Fixes double-counting (only one input remains).
- ❌ **The cap is invented.** ±0.02 is not derived from anything; it is a number chosen to be small.
  That is the same species of unsourced constant D260 §7 criticised.
- ❌ **It changes scores in both directions.** On real data: `e60d7a0c` goes **75 → 45**, which
  *increases* their technique weight by +1.4 pp — the demotion makes them look worse, not better.
  `79fadc50` and `f8ff8569` go 60 → 50 and become the reported "weakest axis" (§4).
- ❌ A 40–50 range with three possible values is *less* discriminating than the 7 values D260 already
  called "heavily quantized".

### (b) Weight-neutral informational axis

TT is computed and displayed, but removed from `axis_to_weight` in `_adjust_domain_weights` and from
the tuple in `_find_weakest_axis`. Weights redistribute over the four measured axes via the existing
renormalisation.

- ✅ No invented constant. No plan distortion.
- ✅ Fixes double-counting by making the score consequence-free.
- ❌ Displays a confident 0–100 number that drives nothing — the user cannot tell it is inert. That
  is a *new* honesty problem, adjacent to the "50 problem" D260 §3.6 flagged.

### (c) `self_reported` and greyed — **RECOMMENDED**

Same weight behaviour as (b), plus the axis is marked
`assessment.profile_source.technique = "self_reported"` and rendered greyed with an explicit reason,
mirroring what A267 already does for benchmark-less axes and what D271 §3.3 proposes for `estimated`.

- ✅ Everything (b) gives.
- ✅ **Says what is true**: this axis is your own opinion of yourself, so it informs the coach and
  not the plan. No invented cap, no inert-looking number.
- ✅ The UI already exists: `RadarChart.axisValue()` returns `number | null` and the null branch
  renders an em dash plus a reason line (A267). One shared "greyed axis" presentation, three reasons:
  *no elite benchmark* / *not measured* / *self-reported*.
- ⚠️ The radar visibly loses a fifth data point in Goal mode. With D271's endurance also `estimated`,
  a user with no tests could see three of five axes greyed. That is accurate, and it is a strong
  argument for the tests — but it is a visible product change and Daniele should see it before it
  ships.
- ⚠️ Requires `profile_source`, shared with D271 §3.3.

**Why (c) over (a):** (a) keeps a number by attaching it to the single input D260 showed is the
*less* reliable half — the user's self-diagnosis, which is also what deepened the author's score to
30 in the first place. A cap makes it harmless, not correct. (c) is the same amount of work and
stops the app from asserting something it cannot measure.

---

## 3. Power Endurance after the demotion

### 3.1 What PE would actually measure

```
with repeater:   PE = repeater_score + weakness_penalty(self_eval, "power_endurance")
without:         PE is unmeasured
```

`repeater_score = (reps / _PE_REPEATER_BENCHMARK[target]) × 100`, clamped — the existing objective
input, now undiluted.

### 3.2 "Almost nothing" is the honest answer for most users

**3 of 18 production profiles have `repeater_7_3_max_sets_20mm` on file.** For the other 15, removing
the gap leaves PE with no input at all. Handling that as a silent 50 would recreate exactly the
failure D260 §3.6 named: *"a real 'average' score and 'no data' are indistinguishable downstream."*

Proposal: PE without a repeater →
`assessment.profile_source.power_endurance = "estimated"`, axis greyed with the same treatment as (c),
and the weight machinery treats an `estimated` axis as neutral (no bump, no cut) rather than reading
its placeholder value.

**Note the second-order effect:** the repeater test is already scheduled by `planner_v2` pass 3
(`test_repeater_7_3` / `test_lp_repeater`, both `required=True`, allowed in `base`, `strength_power`
and `power_endurance`). So the 15 users without one will acquire one within their first cycle —
the greyed state is a starting condition, not a permanent one. That is a good argument for (c)'s
greyed presentation across the board: it resolves itself by the user doing the tests.

### 3.3 Real effect on the three users who have a repeater

| user | target | repeater | benchmark | PE now | PE after | Δ |
|---|---|---|---|---|---|---|
| `7ea9f0ee` (author) | 8b | 25 | 34 | 53 | **70** | **+17** |
| `79fadc50` | 8a | 16 | 30 | 54 | **49** | −5 — **crosses the < 50 weight cliff** |
| `22080848` | 8a | 27 | 30 | 67 | 86 | +19 |

The author's case is the one D260 predicted verbatim: *"the objective repeater says 78/100, but it is
diluted 40/40 with the subjective RP-OS gap and dragged to 54."* Undiluting it is the fix.

### 3.4 Endurance moves too — the D271 coupling

`_compute_endurance` is `0.8 × pe_score + tenure + eval + hang-duration`. Changing PE changes Endurance
mechanically:

| user | EN now | EN after | note |
|---|---|---|---|
| `7ea9f0ee` | 51 | **65** | leaves the < 50 cliff neighbourhood entirely |
| `79fadc50` | 52 | **48** | **crosses the < 50 cliff** — endurance becomes a weight-bumped axis |
| `9e4154d4`, `f8ff8569`, `e60d7a0c` | 34 / 54 / 64 | unchanged | no repeater → PE `estimated` → endurance derivation unchanged |

So a brief that only demotes the gap still moves the Endurance axis for repeater users. If D271 ships
first and Endurance becomes measured, this coupling disappears; if D272 ships first, it is live.
**Ordering matters — see §7.**

---

## 4. Counterfactual weight table

Computed by evaluating the real `_adjust_domain_weights` logic on each user's stored production
profile (base weights from `_BASE_WEIGHTS` / `_BASE_WEIGHTS_BOULDER`). Only the `technique` weight is
shown; the other five absorb the change through renormalisation.

| user | TT now | phase | technique **now** | option **(a)** | option **(b)/(c)** |
|---|---|---|---|---|---|
| **`7ea9f0ee`** (lead 8b) | **30** | base | .275 | .218 (−5.7 pp) | **.202 (−7.3 pp)** |
| | | strength_power | .192 | .125 (−6.7 pp) | **.106 (−8.6 pp)** |
| | | power_endurance | .240 | .177 (−6.3 pp) | **.160 (−8.0 pp)** |
| | | performance | .337 | .281 (−5.6 pp) | **.266 (−7.1 pp)** |
| `79fadc50` (lead 8a) | 60 | all four | .190 / .100 / .150 / .250 | unchanged | unchanged |
| `9e4154d4` (all_round 7a+) | 60 | all four | .179 / .093 / .140 / .234 | unchanged | unchanged |
| `f8ff8569` (boulder 9a) | 60 | all four | .190 / .095 / .095 / .238 | unchanged | unchanged |
| `e60d7a0c` (boulder 8a) | 75 | base | .182 | **.196 (+1.4 pp)** | .182 (0.0) |
| | | strength_power | .091 | .107 (+1.6 pp) | .091 (0.0) |

Where the author's weight goes under (b)/(c), Base phase: finger .156→.172, pulling .110→.121,
power_endurance .138→.152, volume_climbing .229→.253 — the +7.3 pp comes back distributed across the
four axes that are actually measured.

**Honest reading of this table.** Only one of the five users is affected at all, because the other
four sit inside the 50–75 dead band where `_adjust_domain_weights` does nothing. The change is
nonetheless **structural, not personal**: any user whose gap lands in the ≥ 7 bucket (score 30) or the
5–6 bucket with a self-declared technique weakness (score 30–40) gets the same +7.5 pp every phase.
D260 measured 7 distinct TT values across 16 users; the two lowest both cross the `< 50` threshold.

**Phase durations.** Under (b)/(c) the technique-driven shift (`base` +1 / `performance` −1)
disappears. For the author it was already a silent no-op (`_PHASE_FLOORS_LEAD["base"] == cap == 4`),
so nothing changes for lead athletes; for boulder athletes `base` has room (floor 2, cap 4) and the
shift is real, so a boulder athlete with a wide gap currently loses a week of Performance to Base for
a proxy reason. That stops.

**Implementation trap (repeat of §0).** Under (b)/(c), simply omitting `technique` from the profile is
**not** enough: `_find_weakest_axis` does `profile.get(axis, 50)` at line 299, so an absent axis
becomes a phantom 50 and — as the computation confirms — is returned as the weakest axis for
`79fadc50` and `f8ff8569`. It scores exactly 50 so it never trips the `< 50` duration shift, but it
would be reported as the weakest axis to the coach and to any future consumer. `technique` must be
removed from the tuple at line 297 explicitly.

---

## 5. The gap as a hint

The gap is not deleted — it is reclassified. It remains a genuinely useful *tactical* observation:
a wide gap in a redpoint specialist is a **style**, and telling that person their technique is weak is
wrong. A wide gap in someone who says they want to onsight is a real, actionable finding.

### 5.1 In the coach — extend, do not rebuild

`coach/prompt_builder._profile_section` (line 122) already prints all four grades. It does **not**
compute or name the gap. One derived line, inside the block that already exists:

```
- Onsight gap: 5 half-grades (lead RP 8a / OS 7a+). Tactics/style signal, NOT a technique
  measurement — the plan does not weight it. A wide gap in a redpoint-focused climber is a style
  choice; only call it a weakness if the athlete says they want to onsight.
```

No new payload, no new section, no new endpoint. The guardrail sentence matters: without it the model
will read a number labelled "gap" and diagnose technique — the exact failure B305 fixed when the coach
imitated a format string and fabricated a build.

The goal already records the intent the hint needs: `goal.target_style` is
`Literal["redpoint", "onsight"]` (`api/models.py:54`). A wide gap plus `target_style == "onsight"` is
the case worth surfacing; a wide gap plus `redpoint` is worth staying quiet about.

### 5.2 In the UI

A single insight line, not a new axis and not a card. Natural home is `/plan` under the radar,
alongside the existing "Readiness for …" framing:

> *Your onsight is 5 half-grades below your redpoint. That is normal for a redpoint-focused
> climber — it says more about how you climb than about how well. If onsighting is a goal, it is
> where the fastest gains are.*

Gate it on a gap ≥ 4 half-grades and on `target_style`, so it reads as an observation rather than a
verdict. Copy must not use the word "weakness".

---

## 6. Test plan

### 6.1 Scoring (`test_d272_gap_demotion.py`)

- `_compute_technique` no longer calls `_redpoint_onsight_gap`: two profiles identical except for
  their RP/OS grades produce the **same** TT.
- Under (c): `profile["technique"]` is absent or `None`, and `profile_source["technique"] ==
  "self_reported"`.
- `_compute_power_endurance` with a repeater = `repeater_score + eval`, invariant to the gap.
- Without a repeater: `profile_source["power_endurance"] == "estimated"`, no silent 50 fed to weights.
- Author's exact production payload → PE 70, EN 65 (regression fixture, the B321 pattern).
- `79fadc50` payload → PE 49, EN 48: pins the cliff crossing so it can never happen unnoticed again.
- Boulder path: a Font-only athlete keeps working (`resolve_grade`, B321) — the gap helper stays in
  the file even with no callers in PE/TT, because `_redpoint_onsight_gap` becomes the coach hint's
  source.

### 6.2 Weight bounds — the regression tests that matter

- **No single self-reported input may move any domain weight by more than 2 pp.** Property test:
  for every `primary_weakness` × `secondary_weakness` × phase × discipline combination, with all
  measured axes held fixed, assert `max |Δweight| ≤ 0.02`. This is the test that would have caught
  the +7.5 pp distortion when it shipped.
- Weights always sum to 1.0 ± 1e-6 and every weight stays ≥ 0.02 after renormalisation, for every
  profile in the 18-user production corpus.
- `technique` is not in `_find_weakest_axis`'s tuple: a profile with every other axis at 80 and no
  technique key returns `(None, 101)`, not `("technique", 50)`.
- Phase durations are byte-identical to today for every lead profile (the technique shift was already
  a no-op there) and lose exactly the technique-driven shift for boulder profiles.

### 6.3 Invariants

- **Past sessions immutable** (global rule 1): recompute the profile, regenerate, assert
  `session_completion_log`, `feedback_log`, past `week_plans`, `working_loads` are byte-identical.
- **Snapshot isolation** (global rule 3): as verified in D271 §6.2, `assessment_snapshot` and
  `profile_snapshot` are written once and only read; an axis score change never re-weights a live
  macrocycle. Re-assert it here with a technique-specific fixture.
- **No retroactive rescoring** (global rule 2): stored profiles are not recomputed on read.
  `is_macrocycle_stale` will start returning `true` for affected users (technique moves ≥ 5 points) —
  that is the correct behaviour, it surfaces the banner that lets the user choose to regenerate. It
  must be confirmed that the banner path preserves completed sessions (it does today, via
  `preserve_before`).

---

## 7. Versioning and ordering, coordinated with D271

- **One shared field**, not two: `assessment.profile_scoring_version` alongside
  `assessment.profile_source` (D271 §3.3, §7). Whichever brief lands first introduces both.
- Proposed values: `profile_v1` (today), `profile_v2_gap_demoted` (this brief),
  `profile_v3_endurance_measured` (D271 Stage 2).
- **Never retroactive.** Stored profiles keep their version and their numbers. A new version applies
  at the next assessment or the next explicit regeneration.
- **Recommended order: D272 first, then D271.** Rationale: D272 is a pure scoring change with no new
  test, no new equipment and no new UI surface beyond the greyed axis — it can ship and be observed.
  D271 needs an equipment decision, a new test session and a data-collection stage before it changes
  any score at all. Shipping D272 first also means the PE→Endurance coupling of §3.4 is resolved
  before D271 replaces the Endurance derivation entirely, rather than both moving at once.
- If they ship together, the counterfactual table in §4 and the one in D271 §6.3 must be recomputed
  jointly — they are not additive, because both feed the same renormalisation.

---

## 8. Open questions for Daniele

1. **Option (a), (b) or (c)?** Recommendation is (c). (a) requires inventing a cap and changes scores
   in both directions on real users; (b) leaves a confident number that drives nothing.
2. **Is a greyed axis acceptable on the radar?** With (c) plus D271's `estimated` endurance, a user
   with no tests could see three of five axes greyed. Accurate, and a strong nudge toward doing the
   tests — but visible.
3. **PE without a repeater — grey it, or keep a neutral number?** 15 of 18 current users are in this
   state today. The repeater is already scheduled in their first cycle, so the grey is temporary.
4. **Onboarding copy.** `onboarding/grades/page.tsx` and the public `/assessment` page both tell the
   user the gap "reveals technique and power endurance". After this change that is false. Do the
   grades stay a required question? They still feed the pitch ladder (A265), milestones and the coach
   hint, so yes — but the copy must change.
5. **Ordering vs D271** (§7). Recommendation: D272 first.

---

*End of analysis D272. No application code written. Awaiting Daniele's decisions before any implementation brief.*
