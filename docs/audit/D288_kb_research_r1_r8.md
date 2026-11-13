# D287 — Research session: evidence 2020–2026 for eight planner questions

> **Date:** 2026-11-13 · **Type:** research compile (KB authority → brief input for Claude Code) · **Status:** decisions taken 2026-11-13 (see the end of this file); saved in the repo by D288
> **Scope:** the eight questions of `D287_planner_audit.md` §6. Engine state read from `ENGINE_ARCHITECTURE.md`, `key_stimuli.json`, `athlete_plan.md`, `D280_methodology_vs_literature.md`, `D287_planner_audit.md` (these win over `_MIRROR_consolidated.md`).
> **Verification marks:** ✔ full text opened today · ◐ abstract or publisher page of the primary record read today (numbers quoted are from the abstract) · ○ secondary record only. Nothing here was run against the code.
> **Rule namespace:** rules are labelled R1–R8. No D-number is assigned; they become decisions only when Daniele adopts them.

## 0. Read this first

1. **Direct climbing evidence exists for almost none of the eight questions.** Most rules below are engineering constants bounded by indirect evidence. Each one says so.
2. **Three rules challenge the current design** (details in the sections): the deload removes all hard work (Q3); the KB text for older climbers assumes slower recovery from age 40 (Q6); the boolean `finger` flag cannot express low-load finger work (Q1).
3. **Corrections to earlier project files found while re-opening sources**
   - `D280` source list cites the deload survey as "Bell et al. 2024". The first author is **Rogerson** (Rogerson, Nolan, Androulakis Korakakis, Immonen, Wolf, Bell 2024; same DOI).
   - `D280` B10 says the experimental sources find that adding or omitting an unload "does not change adaptations". Coleman 2024 did find a difference: the group that stopped training for one week gained **less** lower-body strength.
   - `D280` C2 uses Javorský 2023 as a maintenance recipe for a trip. The sample was lower-grade to intermediate climbers doing no other climbing (lockdown). It does not show that an 8a+ climber keeps finger strength on that dose.
   - `10_female_age_youth.md` §3.2 ("a 45-year-old may need 72 h+") carries no source, and the 2025 meta-analysis below does not support it.
4. **High-risk modules.** R1, R2, R3, R5 touch `planner_v2.py` / `macrocycle_v1.py`: STOP gate before any brief.

Evidence levels used: SR/MA > RCT > controlled or crossover trial > cohort / cross-sectional > expert / practice survey.

---

## Q1 — Finger-load tiers: spacing and weekly count

### Evidence

| Source | Design, sample | What was measured | Result |
|---|---|---|---|
| ✔ Gilmore, Klimek, Abrahamsson, Baar 2024, *Sports Med Open* 10:125, doi:10.1186/s40798-024-00793-7 | Retrospective cohort of app users, n=526 (21 women), two max-hang tests 4–16 weeks apart | Change in max-hang strength-to-weight ratio by self-selected protocol | Climbing only 0%; low-load only (~40%, feet on ground, 10 min, ≥3/wk) +2.5% (d=0.29 vs climbing only, p=0.12); max hangs only (≥0.5/wk) +3.2% (d=0.45); both +5.8% (d=0.79) |
| ◐ Feldmann, Lehmann, Wittmann, Wolf, Baláš, Erlacher 2022, *J Sci Sport Exerc* 4(2):145–155, doi:10.1007/s42978-021-00139-9 | Controlled, 21 climbers (IRCRA 23.5 ± 3.5), 4 × 5-min exhaustive climbing | Finger-flexor MVC, sustained and intermittent contraction tests pre, post, 24 h | MVC −18% post, −3% at 24 h; sustained −55% → −16%; intermittent −59% → −22% |
| ✔ Gáspari et al. 2024, *Front Sports Act Living* 6:1251047, doi:10.3389/fspor.2024.1251047 | Observational, 9 national-team climbers, boulder championship | Hand-grip dynamometry, forearm pain, tiredness, readiness up to 60 h | Grip −6.4% at 12 h, baseline at 24 h; pain baseline at 24 h; tiredness at 48 h; readiness to climb hard only at 60 h |
| ◐ Stien et al. 2021, *J Sports Sci Med* 20:438–447, doi:10.52082/jssm.2021.438 | RCT, 16 advanced–elite men, 5 weeks, campus 2 vs 4 sessions/wk, volume equated | Bouldering performance, isometric pull-up force, RFD, campus tests | No difference between frequencies (p=0.107–1.000); 2/wk beat control on bouldering, 4/wk on RFD |
| ◐ Quarmby et al. 2023, *Front Sports Act Living* 5:1269870, doi:10.3389/fspor.2023.1269870 | SR, 34 studies | Risk factors for overuse injury | Higher climbing intensity, bouldering, low finger strength, crimp grip, previous injury raise risk; training volume conflicting |
| ◐ Hermans et al. 2022, *Front Sports Act Living*, doi:10.3389/fspor.2022.888158 · ○ Devise et al. 2022, doi:10.3389/fspor.2022.862782 · ○ Mundry et al. 2021, *Sci Rep* 11:13530 | Hangboard RCTs | Dose used | 2 hangboard sessions/wk on top of climbing (Hermans: 2 × 48 min, read today; the other two as reported in D280 Part B) |

### Not evidenced
- No study compared spacings (6 h vs 24 h vs 48 h) between low-load and maximal finger work. The "≥6 h" in Gilmore is the app's advice; real spacing was not tracked, the low load was self-chosen and unmeasured, injuries were not an outcome, and two authors own the protocol and the app.
- No study counted weekly finger-hard exposures (crag days included) against injury or performance.
- No hangboard RCT used more than 2 max-hang sessions per week.

### R1 — proposed rule
Replace the boolean `finger` with `finger_load ∈ {high, low}`:
- **high** = hangs or tests at ≥ 85% of max (PE-phase maintenance 3 × 7 s included), limit / board / campus sessions, `three_attempt_comp`, a crag day with attempts at ≥ RP−2.
- **low** = ≤ 50% of max, no set to failure, ≤ 10 min under load per session (feet-on no-hangs, aerobic hangs far from failure, ramp-ups).
- **Gaps:** high–high ≥ 48 h (unchanged: never consecutive days). low–high ≥ 6 h in either order. low–low ≥ 6 h, at most 2 per day.
- **Sub-maximal work to failure** (repeaters, intermittent hangs at 60–80%) is **not** low: it stays under the hard gap, and a key PE session should not follow an exhaustive day by less than 48 h.
- **Weekly:** ≤ 3 finger-high exposures, of which ≤ 2 max-hang sessions. Whether crag-hard days sit inside this cap is Daniele's call (see Q2); the conservative reading counts them inside.

**Confidence: low–medium** for the two-tier idea (one retrospective cohort with conflict of interest, effect consistent with the 24 h strength-recovery data); **low** for 6 h and for the weekly cap (no evidence, engineering constants).
**Would change it:** a randomized trial adding low-load work to max hangs with spacing and injury tracking; a prospective exposure–injury cohort.
**Engine:** challenges the boolean flag (already tracked as A-FINGER-LOAD-TIERS). Side effect worth having: PASS 2 can keep placing truly low sessions (`finger_aerobic_base`) on consecutive days, while `finger_maintenance_*` (max hangs) must obey the high gap. **P1 · M · STOP (`planner_v2`)**

---

## Q2 — Crag days

### Evidence
| Source | Design, sample | Measured | Result |
|---|---|---|---|
| ◐ Feldmann 2022 (above) | — | — | Strength back within 24 h, local endurance still −16% / −22% at 24 h |
| ✔ Gáspari 2024 (above) | — | — | Readiness for hard climbing back only at 60 h; authors list "single competition, not consecutive days" as a limitation |
| ◐ Yu, Lowe, Millon, Tran, Coffey 2023, *Front Sports Act Living* 5:1224581, doi:10.3389/fspor.2023.1224581 | Field, n=36, 24 h continuous climbing event | Grip strength, static hang time | Grip −14.7 to −15.1%, hang time −71.2%; no recovery follow-up |

### Not evidenced
- **No evidence** on finger or pulley load of an outdoor limit day versus an indoor session.
- **No evidence** on recovery after 2–3 consecutive climbing days. Every recovery study covers one day.

### R2 — proposed rule
- A crag day with ≥ 1 attempt at ≥ RP−2 counts as **1 hard day and 1 finger-high exposure** (current B372 / B382 behaviour, kept). An easy crag day (all pitches ≤ OS−2) is neither hard nor finger-high unless its logged load is high (existing `outdoor_fatigue_days` rule), and is never a rest day.
- After **one** hard crag day: next finger-high session ≥ 48 h later; no key PE session for 48 h.
- After **≥ 2 consecutive** hard crag days: 2 non-hard days, the first a true rest day; next finger-high session ≥ 72 h after the last crag day; tests ≥ 72 h (existing guard).
- Each hard crag day uses one unit of the weekly hard cap.

**Confidence: low.** Extrapolated from single-day studies with n = 9–21 and non-specific grip measures; nothing on multi-day trips.
**Would change it:** any multi-day field study with climbing-specific force at 24 / 48 / 72 h.
**Engine:** validates B372 / B382 as conservative; adds the multi-day rule, which the engine lacks. **P2 · S · STOP (`planner_v2` anchors) or alert-only in `guards_v1` (no STOP)**

---

## Q3 — Deload

### Evidence
| Source | Design, sample | Measured | Result |
|---|---|---|---|
| ◐ Coleman et al. 2024, *PeerJ* 12:e16777, doi:10.7717/peerj.16777 | RCT, 39 resistance-trained adults, 9 weeks, one week of **no training** at midpoint vs continuous | Muscle thickness, isometric and dynamic lower-body strength, power, endurance | No difference in size, power, endurance; continuous training gained **more** strength |
| ○ Pancar et al. 2026, *Sci Rep* 16:10299, doi:10.1038/s41598-026-40612-5 | Within-subject, 19 untrained men, 8 weeks, volume and frequency cut in weeks 4 and 8 (≈ 18% less total volume) | Muscle thickness, 10RM | No difference between conditions |
| ◐ Rogerson et al. 2024, *Sports Med Open* 10:26, doi:10.1186/s40798-024-00691-y | Survey, 246 strength / physique athletes | Self-reported practice | 6.4 ± 1.7 days every 5.6 ± 2.3 weeks; volume down, frequency unchanged, load and effort down |
| ◐ Bell et al. 2023, *Sports Med Open* 9:87, doi:10.1186/s40798-023-00633-0 | Delphi, 34 → 29 → 21 coaches | Expert consensus | Definition and design principles (full statements not opened: access blocked) |
| ◐ Bell et al. 2022, *Front Sports Act Living* 4:1073223, doi:10.3389/fspor.2022.1073223 | Interviews, 18 coaches | Practice | 5–7 days every 4–6 weeks |
| ◐ Spiering, Mujika, Sharp, Foulis 2021, *J Strength Cond Res* 35(5):1449–1458, doi:10.1519/JSC.0000000000003964 | Narrative review | Minimal maintenance dose | Strength kept for up to 32 weeks on 1 session/wk, 1 set per exercise, **if relative load is kept**; insufficient data for athletes |

### Not evidenced
- **No evidence** in climbers. No trial compared "reduced volume, kept intensity" against "no hard work" directly. The 4–6 week cadence is practice only (surveys, interviews).

### R3 — proposed rule
- **Inside an 11–14 week cycle: no calendar unload.** One optional reduced week, only on a trigger: ≥ 2 `very_hard` sessions in 7 days, or an active pain block, or the athlete asks. Skip it when a trip taper (A281) fell within the previous 5 weeks.
- **Form (optional week and terminal deload alike):** keep the number of climbing days and one exposure to each key stimulus; sets × 0.5; one finger exposure of 2–3 sets at the phase working load −10% with ≥ 3 s in reserve; one short limit or flash-level technique session; no PE intervals, no tests, no work to failure.
- **Do not remove all hard work.**

**Confidence: medium** that a week of complete cessation gives nothing and costs some strength (one RCT in trained adults, consistent with the maintenance literature); **low** for cadence and for transfer to finger strength (lower-body lifting data only).
**Would change it:** a trial comparing volume-cut and cessation deloads in trained athletes; any climbing data.
**Engine:** **challenges current design.** `apply_deload_week` drops every `hard` session and sets `hard_days: 0, finger_days: 0`, which is the cessation model for hard work. Low urgency: it is one week at cycle end. Note that D280 already rejected raising the deload intensity cap to `high`; R3 does not ask for that, it asks for one low-volume exposure. **P2 · M · STOP (`macrocycle_v1.apply_deload_week`)**

---

## Q4 — Concurrent lunch training

### Evidence
| Source | Design, sample | Measured | Result |
|---|---|---|---|
| ◐ Schumann et al. 2022, *Sports Med* 52:601–612, doi:10.1007/s40279-021-01587-7 | SR/MA, 43 studies | Max strength, explosive strength, hypertrophy: concurrent vs strength only | Max strength SMD −0.06 (ns); hypertrophy −0.01 (ns); explosive strength −0.28 (p=0.007), attenuated in same-session designs, not with ≥ 3 h separation |
| ◐ Petré et al. 2021, *Sports Med* 51:991–1010, doi:10.1007/s40279-021-01426-9 | SR/MA, 27 studies, lower-body 1RM | Effect of training status and session separation | Trained ES −0.35; same session −0.66; different sessions −0.10 (ns) |
| ◐ Markov et al. 2022, *Sports Med* 52:1385–1398, doi:10.1007/s40279-021-01615-6 | SR/MA, 15 studies, trained men | Lower-limb strength and power right after aerobic exercise | Strength SMD 0.79; moderate–high intensity 0.65 (p=0.020), low intensity ns; > 30 min larger; cycling > running; power unchanged |
| ✔ Mathieu, Robineau, Piscione, Babault 2022, *Sports* 10(5):75, doi:10.3390/sports10050075 | Crossover, 25 rugby players, sprint intervals then strength 4 h later | Bench-press and squat bar velocity, wellness at 24–48 h | No effect on bench or squat velocity at 4 h; perceived fatigue worse for 24–48 h after running sprints |

### Not evidenced
- **No evidence** with finger or pulling strength, or climbing, as the outcome. Nearly all outcomes are lower-limb; the only upper-body datum is one n=25 study with a sprint format that is not 4×4.
- **No evidence** on legs or upper-push sessions before climbing. **No evidence** on whether HIIT should count as a hard day in a climbing week.

### R4 — proposed rule
- **Zone 2 (≤ 45 min) and upper-push:** allowed on any day, ≥ 3 h before climbing, a max session included.
- **HIIT 4×4:** ≤ 1 per week; ≥ 6 h before a non-max evening session (evidence floor 3–4 h; lunch-to-evening already gives ≥ 6 h); ≥ 24 h before a max / limit / test session (current B405, kept: conservative against the data, which would allow about 4–6 h for upper-body strength).
- **Legs strength:** ≥ 48 h before a limit or outdoor day (current, kept as an engineering constant).
- **Hard-day accounting:** HIIT does **not** use the climbing hard cap (no finger or pulling load). A day with HIIT or legs is not a true rest day (see R5).

**Confidence: medium** for "separate by ≥ 3 h, low intensity is harmless" (three meta-analyses, same direction); **low** for transfer to finger and pull strength and for the HIIT accounting.
**Would change it:** any concurrent-training study with upper-body pulling or grip outcomes.
**Engine:** validates the A300 / B405 pairing rules. Explosive strength is the quality that suffers from proximity, which supports protecting limit and campus sessions more than max hangs. **P2 · XS (confirm, document)**

---

## Q5 — Hard-day cap and rest days (advanced lead climber, 6–7 available days)

### Evidence
| Source | Design, sample | Measured | Result |
|---|---|---|---|
| ◐ Stien 2021 campus RCT (Q1) | — | — | Same weekly volume in 2 or 4 sessions: no difference between groups |
| ✔ Lattice Training 2026, "How many days should I train per week for climbing?" (coaching data, not peer reviewed) | App logs, ≈ 2,250 users | Logged training days per week by boulder grade | Mean 3 days at V4, 4 at V12+; interquartile range ≈ 3–4 for V5–V11; rest and hard days not reported; survivorship bias stated |
| ◐ Saeterbakken, Bratland, Andersen, Stien 2024, *Front Physiol* 15:1461820, doi:10.3389/fphys.2024.1461820 | RCT baseline data, 31 advanced–elite boulderers | Habitual sessions | 2.5–3.1 bouldering sessions per week |
| ✔ Gáspari 2024 (Q1) | — | — | Readiness for hard climbing back at 60 h after a maximal day |
| ◐ Quarmby 2023 (Q1) | — | — | Intensity is a more consistent overuse-injury factor than volume |

### Verdict
**"Max 3 hard days, at least 2 true rest days" is not evidence-based: no study has tested it.** It is compatible with the readiness lag after a maximal day, with what engaged climbers actually log, and with intensity being the clearer injury factor.

### R5 — proposed rule
- Hard cap default **3 per week**, user-adjustable to 4. Hard = finger-high, max / limit, PE to failure, crag-hard.
- **≥ 2 rest days per week**, defined: no climbing, no HIIT, no legs strength, no heavy pulling. Zone 2 ≤ 45 min, mobility and prehab are allowed. At least one rest day directly follows the hardest day or crag block.
- With 6–7 available days: ≤ 5 climbing or training days.

**Confidence: low** (no direct evidence).
**Would change it:** a prospective cohort linking weekly hard-session counts to injury or performance. The app can produce the within-athlete version: `very_hard` and pain flags against the hard-day count of the previous 7 days.
**Engine:** validates the default cap; adds an explicit content rule for a "true rest day" (today `low_rest_days` is a week-level alert built on `guards_v1.REST_DAY_SESSION_IDS`; whether a HIIT or legs lunch breaks a rest day there was not checked in code). **P2 · S · STOP if enforced in `planner_v2`; none if alert-only**

---

## Q6 — Age 40–49

### Evidence
| Source | Design, sample | Measured | Result |
|---|---|---|---|
| ◐ Fernandes et al. 2025, *J Aging Phys Act*, doi:10.1123/japa.2024-0165 | SR/MA + meta-regression, 36 studies, older vs younger adults | Muscle function, soreness, CK after damaging exercise | Function loss not different; soreness and 24 h CK **lower** in older adults (age cut-offs not confirmed in the primary) |
| ◐ *Front Physiol* 2022;13:916924, doi:10.3389/fphys.2022.916924 (Gepner group) | Controlled, 28 amateur male endurance athletes, young vs middle-aged, muscle-damaging aerobic protocol | Damage markers, performance to 48 h | No between-group difference in recovery |
| ◐ Hayes et al. 2023, *Sports Med Open* 9:51, doi:10.1186/s40798-023-00597-1 | Scoping review, 27 studies, ≥ 65 years | Recovery from resistance exercise | Inconsistent; no recommendation possible. Not the 40–49 band |
| ✔ Lazarczuk et al. 2022, *Sports Med* 52:2405–2429, doi:10.1007/s40279-022-01695-y | SR/MA, 61 studies, n=763, lower-limb tendons | Tendon stiffness, modulus, CSA after loading | High-intensity training: adults 18–59 stiffness SMD 0.91, modulus 1.05; ≥ 60 years 0.40 and 0.21; ages 40–49 not analysed separately |
| Context, pre-2020: ◐ Lutter et al. 2019, *Wilderness Environ Med*, doi:10.1016/j.wem.2019.06.008 | Clinic series, climbers ≥ 35 years, 275 injuries | Injury type by age | 68% overuse; age not correlated with overuse injury overall, weakly with degenerative conditions |

### Not evidenced
- **No evidence** on finger flexor tendons or pulleys by age. **No evidence** on frequency of maximal stimuli or progression rate by age in climbers.

### R6 — proposed rule
- **No automatic age modifier at 40–49:** `recovery_multiplier` 1.0, same gaps, same hard cap, same ≤ 2 max-hang sessions per week, same escalation cap (+5% of official max per 7 days).
- Modifiers stay **signal-driven** (existing pain rule: grade 2 → −10% and hangs ≤ 85% for 7 days), not birth-year-driven. The multiplier remains user-adjustable.

**Confidence: medium** for muscular recovery (meta-analysis, but mostly untrained, non-climbing samples); **low** for tendon (no finger data, band not isolated).
**Would change it:** tendon or pulley adaptation data in climbers over 40; a recovery study in trained middle-aged athletes using upper-limb isometric work.
**Engine:** validates the code (automatic multiplier from 50, B165b) against the KB text (D83 "40+", `10_female_age_youth.md` §3.2). **Fix the KB, not the engine.** D280 B8 (rate limit for over-40s) stays an unproven heuristic. **P2 · XS (KB edit)**

---

## Q7 — Limit bouldering, try-hard, fall practice

### Evidence
| Source | Design, sample | Measured | Result |
|---|---|---|---|
| ✔ Stien et al. 2021, *Front Sports Act Living* 3:661167, doi:10.3389/fspor.2021.661167 | RCT, 14 intermediate–advanced, 5 weeks, 2 prioritized sessions + 1 easy maintenance session (RPE ≤ 3) per week | Lead and boulder performance, force, endurance | Performance in the non-prioritized discipline unchanged |
| ◐ Saeterbakken et al. 2024, *Front Physiol* 15:1461820 | RCT, 31 advanced–elite boulderers, 3 added dynamic finger sessions/wk, 5 weeks | Bouldering performance, finger strength | Neither group improved bouldering performance |
| ◐ Stien 2021 campus RCT (Q1) | — | — | 2 sessions/wk for 5 weeks improved bouldering versus control |
| ◐ Javorský, Saeterbakken, Andersen, Baláš 2023, *Front Sports Act Living* 5:1256136, doi:10.3389/fspor.2023.1256136 | Crossover, 13 lower-grade–intermediate climbers, no other climbing, 2 sessions/wk × 5 weeks, 6 × 1 min at 7:3, 60% or 30% + BFR | MVC, critical force, W′ | All maintained |
| ◐ Spiering 2021 (Q3) | — | — | 1 session/wk maintains strength if load is kept |
| ◐ Garrido-Palomino & España-Romero 2023, *J Sports Sci* 41(16), doi:10.1080/02640414.2023.2281157 | Three-group trial, women with fear of falling (n and dose not confirmed) | Self-reported ability, anxiety | Ability up in the psychological and the training group; somatic anxiety down only with psychological training |

### Not evidenced
- **No evidence** on weekly dose of limit bouldering by phase. **No evidence** on try-hard or attempt-budget training. **No evidence** on a dose of practice falls.

### R7 — proposed rule
- **Strength-power:** 1 limit key per week (a second only inside the hard and finger caps), 4–6 problems, ≤ 5 attempts each, 3–5 min rest.
- **Power-endurance:** one short limit exposure (2–3 problems, same intensity) every 7 days preferred, **12 days maximum** (current `max_gap_days`, kept).
- **Performance:** the project session is the limit exposure.
- **Try-hard and falls:** keep 1 exposure per week and 2–3 falls at the start of each lead day as **engineering constants**.

**Confidence: low** for limit dose; **low–medium** for the maintenance gap (three small studies and one review agree on "once a week, keep intensity"; none on limit bouldering in advanced climbers; nothing beyond 7 days); **no evidence** for try-hard and falls.
**Would change it:** a trial manipulating limit-session frequency; fall-exposure dose data.
**Engine:** validates `key_stimuli.json` (PE limit as `warning`, alternating weekly, 12-day bound). **P2 · XS (document)**

---

## Q8 — Technique for a feet / positioning limiter

### Evidence
| Source | Design, sample | Measured | Result |
|---|---|---|---|
| ◐ Hacques, Komar, Seifert 2021, *Atten Percept Psychophys* 83:2303–2319, doi:10.3758/s13414-021-02288-z | 7 novices, 10 sessions | Exploratory hand movements, gaze, on learning and transfer routes | Exploration fell with practice on both |
| ◐ Hacques, Dicks, Komar, Seifert 2022, *PLoS One* 17(6):e0269794, doi:10.1371/journal.pone.0269794 | Novices, constant vs imposed vs self-chosen variability | Climbing fluency, gaze | Constant practice best on the trained route; no fluency difference on the transfer route; imposed variability gave more proactive gaze |
| ◐ Seifert, Hacques, Komar 2022, *Int J Environ Res Public Health* (PMC8910696) | Narrative review | — | Framework for constraint-led practice; no dose |

### Not evidenced
- **No evidence** on minutes or drills per week. **No evidence** in advanced climbers. **No evidence** on footwork or positioning drills against any outcome. **No evidence** on indoor-to-rock transfer.

### R8 — proposed rule
- Keep the current key as an engineering constant: **1 per week = ≥ 30 min of technique-constrained climbing at flash to RP−2, or ≥ 2 different feet / positioning drills** (A325), done fresh at the start of a session.
- **Outdoor day:** counts for the technique key **only when a measurable target is logged** for that day (foot slips per attempt, or re-adjustments on a sample pitch, as in `athlete_plan.md` §7). Unlogged, it does not count (current A294).

**Confidence: low / no evidence.** The outdoor question is about verifiability, not physiology.
**Would change it:** a dose trial with a precision outcome in advanced climbers. Meanwhile the tracked P and Q scale metrics over 8–12 weeks are the best available within-athlete evidence.
**Engine:** resolves the tension between A294 (outdoor never counts) and `athlete_plan.md` §3 (the outdoor weekend is the main technique session). **P2 · S (`key_sessions_v1`, not a STOP module)**

---

## Summary

| Q | Rule | Confidence | Main source | Tag |
|---|---|---|---|---|
| 1 | `finger_load` high / low; high–high ≥ 48 h; low–high ≥ 6 h; ≤ 3 finger-high per week, ≤ 2 max-hang sessions | low–medium (tiers), low (numbers) | Gilmore 2024; Feldmann 2022 | P1 · M · STOP |
| 2 | Crag-hard = 1 hard + 1 finger-high; 48 h after one day; 72 h and 2 non-hard days after ≥ 2 days | low | Feldmann 2022; Gáspari 2024 | P2 · S |
| 3 | No calendar unload in 11–14 weeks; triggered only; sets × 0.5, keep one exposure per key stimulus | medium (no cessation), low (cadence) | Coleman 2024; Rogerson 2024 | P2 · M · STOP |
| 4 | Z2 / push ≥ 3 h before climbing; HIIT ≥ 6 h before non-max, ≥ 24 h before max, outside the hard cap | medium (separation), low (transfer) | Schumann 2022; Petré 2021; Markov 2022 | P2 · XS |
| 5 | Cap 3 hard days; ≥ 2 rest days with a defined content | low | none direct; Gáspari 2024; Lattice 2026 | P2 · S |
| 6 | No automatic modifier at 40–49; signal-driven only | medium (muscle), low (tendon) | Fernandes 2025; Lazarczuk 2022 | P2 · XS |
| 7 | SP 1 limit key per week; PE one short exposure every 7–12 days; falls and try-hard as constants | low; no evidence for falls | Stien 2021; Spiering 2021 | P2 · XS |
| 8 | 1 technique key per week (≥ 30 min or ≥ 2 drills); outdoor counts only with a logged target | low / no evidence | Hacques 2021, 2022 | P2 · S |

**Rules resting on a single small study:** the 6 h low–high gap (R1, one retrospective cohort, advice not measured); 48–60 h after a hard day (R2, R5, n=9); upper-body strength unaffected 4 h after sprints (R4, n=25).

## Decisions for Daniele
1. Crag-hard days inside the cap of 3 finger-high exposures, or on top of it (`athlete_plan.md` §5 reads as "on top").
2. Deload: accept one low-volume exposure per key stimulus instead of zero hard work.
3. KB wording for 40+: align to the code (no automatic change before 50).
4. Outdoor technique credit when a target is logged.

## Not verified today
- Every ◐ row: numbers come from the abstract or the publisher page, not from the full text.
- Devise 2022 and Mundry 2021 session frequencies (from D280 Part B); Pancar 2026 (aggregator abstract and trial registry only).
- Bell 2023 Delphi statements (page blocked); Garrido-Palomino 2023 sample size and protocol; Fernandes 2025 age cut-offs.
- Markov 2022 volume and pages, and Seifert 2022 volume, are from indexing records.

---

## Decisioni di Daniele (2026-11-13) e stato delle regole — D288

1. **Falesia dura dentro il tetto** dei 3 stimoli dita forti a settimana (R1/R2). `athlete_plan.md` §5 diceva «più l'outdoor duro»: corretto.
2. **Deload (R3) accettato**: una dose ridotta per ogni stimolo chiave invece di zero lavoro duro.
3. **KB 40+ (R6) allineata al codice**: nessun modificatore automatico prima dei 50 anni.
4. **Tecnica outdoor (R8) accettata**: conta solo con un target misurabile registrato.
5. **Riposo (R5)**: un pranzo HIIT o gambe **non** rompe il giorno di riposo (resta la definizione di `guards_v1._low_rest_days`).

| Regola | Stato |
|---|---|
| R1 livelli di carico dita + tetto settimanale | Fase 1 → `D288_phase1_R1_R2.md`, attende OK (STOP `planner_v2`) |
| R2 falesia su più giorni | Fase 1 → `D288_phase1_R1_R2.md`, attende OK |
| R3 deload con dose ridotta | Fase 1 → `D288_phase1_R3_R8.md`, attende OK (STOP `macrocycle_v1`) |
| R4 pranzi concorrenti | ✅ confermate le regole attuali (A300/B405), nessun codice |
| R5 tetto giorni duri e riposi | ✅ invariato: tetto di default 3 (Daniele 5 per scelta sua), riposo come oggi (decisione 5) |
| R6 età 40-49 | ✅ testi KB corretti (`10_female_age_youth.md` §3.2, D83) |
| R7 dose di limit / try-hard / cadute | ✅ confermato `key_stimuli.json` (PE limit ogni 7-12 giorni) |
| R8 tecnica outdoor con target | Fase 1 → `D288_phase1_R3_R8.md`, attende OK (campo nuovo nel log outdoor) |

Correzioni applicate alle fonti del progetto: `D280` (primo autore Rogerson; Coleman 2024; ambito di Javorský 2023), `10_female_age_youth.md` §3.2, D83 in `decision_consolidation_D01_D91.md`.

