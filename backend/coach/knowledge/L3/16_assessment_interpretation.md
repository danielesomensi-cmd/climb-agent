# L3 — Assessment Interpretation

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC18.
> **Token target:** ~4,000.
> **Status:** v1.0 — ready, with two documented coverage gaps (see below). NEW file.
> **Source files distilled:** `docs/research_kb/01_performance_determinants.md` (T01 — five-axis, Lattice n=901 + Mountain Project percentiles + r/climbharder + Hörst self-assessment), `docs/research_kb/02_finger_strength.md` (T02 — Berta 2025 normative + Lattice benchmarks), `docs/research_kb/literature_review_climbing_training.md` §6 (hangboard protocols underpinning the tests), decision consolidation D83, D85, D86. NEW file — synthesized rather than 1:1 distilled.
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table, row `16_assessment_interpretation`).

> **v1.0 coverage gap (engine-internal scope):** the audit lists D88 (test scheduling cadence + L-sit benchmarks) and D90 (which max-hang protocol the engine selects) as inputs for this file. Both are engine-internal: they govern *when* a test fires and *which protocol the engine selects under the hood*, not what the user is supposed to do with the result. The coach reads test outputs but does **not** reference the scheduling/protocol-selection layer; the engine has already done that work by the time a user asks "what does my score mean?". If a user asks "when do I retest?" or "why this protocol?", the answer is in the engine's session output, not in this file.

> **v1.0 coverage gap (norms):** Lattice's full age-stratified norm tables (n=901 dataset is partially public; the deep cuts by sex × age × discipline live behind their coaching service) are not in the KB. The benchmark tables below are synthesized from the publicly available subset (T01 §3.1, §3.7) + Berta 2025 + strengthclimbing.com's Lattice-derived approximations. The numbers are usable as orientation; do not present them as percentile-precise. v1.1 will fold in Lattice's published age curves once available.

---

## Quick reference

The 5-axis radar (finger_strength, pulling_strength, power_endurance, technique, endurance) is **diagnostic, not prescriptive in isolation**. A score's meaning lives in (1) where it sits against population norms for the user's target grade, (2) how it ranks against the user's *other* axes, and (3) whether the gap between axes points to a trainable bottleneck. The single most useful question a user can ask is not "is my score good?" but "is this my weakest axis?" — MacLeod's "missing 20%" framing (Magiera 2013 confirms the same statistically: no single variable dominates above ~50% variance; the *combination* is what drives grade). Two firewalls: (a) body composition is **not** an action axis (D64); (b) age and sex shift baseline expectations but never license skipping work (D83 multiplier is recovery, not a strength discount).

---

## Core findings

### 1. The 5 axes and what each one actually measures

The engine scores each axis 0-100. The number is a position on the population distribution for the user's discipline (lead or boulder), tuned by the chosen target grade. It is *not* a percentile in the strict statistical sense — it's a min-max projection onto a benchmark band. When the coach talks about "your finger axis is 65," what's being claimed is: "for your target grade, you're middle-of-pack on this capacity."

| Axis | What the test measures | Engine test | Primary literature anchor |
|---|---|---|---|
| **finger_strength** | Forearm flexor MVC through 20 mm half-crimp hang | `test_max_hang` (MVC-7, total load incl. body mass) | Michailov 2018, Berta 2025, Lattice (Tom Randall public data) |
| **pulling_strength** | Upper-body lat / bicep / scapular pulling force | `test_pullup_bw` (gate) → `test_max_weighted_pullup` (1RM via Brzycki) | MacKenzie 2020, Baláš 2012 |
| **power_endurance** | Repeated near-max effort capacity (anaerobic glycolytic + buffering) | engine PE test (proxy via session feedback if not directly testable) | Bergua 2018, Bechtel/Consuegra varied-interval framework |
| **technique** | Movement economy — proxied through OS/RP grade gap | derived, not directly tested | Magiera 2013 (canonical weight 0.370), Seifert 2014 (jerk metric, not in engine) |
| **endurance** | Aerobic + capillarisation capacity in forearm flexors | duration / repeater proxy + ARC tolerance | López-Rivera 2014, Fryer 2016 |

**Body composition** is intentionally absent (D01 + D64). It's a mediator that surfaces through finger strength relative to body mass (the strength-to-weight ratio is *already inside* the finger axis score). Talking about it as a "training axis" is methodologically wrong (Mermier 2000: 0.3% variance) and behaviorally risky (RED-S, see [[14_female_age_youth]] §6 and [[08_nutrition]]). See [[L0_safety_hard_rules]] D64.

### 2. The single biggest interpretive error: reading one axis in isolation

Magiera 2013 (n=30, OS 7b+ / RP 8a) ran canonical analysis on 43 variables; **seven** were needed to explain 77% of climbing performance variance. The top variable (relative finger strength) had canonical weight 0.490 — meaningful but not deterministic. The implication for axis interpretation: no single number predicts grade. Two finger-strength-equal climbers can differ by three V-grades because of technique, mental endurance, or pulling strength.

**Operative rule.** When a user asks "is my finger axis good?", reframe to: "compared to your other axes, where does it rank?" The weakest axis is the high-leverage one to train (MacLeod's "missing 20%" — strong climbers tend to ignore their worst axis and train their best, which compounds the imbalance).

**Power Company "outlier space"** (Hampton, 600+ climber dataset) makes this geometric:
- **Upper outlier** = strong fingers, lower-than-predicted grade → technique or mental is the bottleneck. Don't add hangboard volume; go to [[06_technique_movement]] / [[07_mental_fear_focus]].
- **Lower outlier** = lower fingers, higher-than-predicted grade → exceptional technique compensating. Don't chase finger numbers exclusively; protect technique (often eroded if hangboard volume crowds out climbing).

### 3. Benchmark tables — synthesized, use as orientation

Tables below are merged from Lattice public data (Tom Randall benchmarks, n=901 blog), Mountain Project percentiles (Shaun McCarthy 2022), Berta 2025 normative, and the multivariate models (MacKenzie 2020, Baláš 2012). **These are not percentile-precise** — they're synthesized from the publicly disclosed subset. Use as orientation, not as outcome predictions.

**Finger strength — MVC-7 on 20 mm (% bodyweight, total load incl. BW):**

| Target grade | Approx % BW (M) | Approx % BW (F) | Position |
|---|---|---|---|
| 6b+ / V3 | ~110 | ~100 | Recreational |
| 7a+ / V5 | ~128 | ~118 | Intermediate |
| 7c+ / V8 | ~152 | ~140 | Advanced |
| 8a+ / V10 | ~170 | ~155 | Strong advanced |
| 8c / V13 | ~190 | ~170 | Elite |

Source: strengthclimbing.com Lattice approximation + Berta 2025. Rough heuristic: ~6% per V-grade V4→V11, ~5% V11→V14, ~4% V14→V17 (Randall public statements).

**Weighted pull-up 1RM (% BW including bodyweight):**

| Target grade | Approx 1RM (M) | Approx 1RM (F) |
|---|---|---|
| 6b+ / V3 | ~110 | ~100 |
| 7a+ / V5 | ~125 | ~115 |
| 7c+ / V8 | ~150 | ~135 |
| 8a+ / V10 | ~165 | ~150 |
| 8c / V13 | ~180+ | ~165+ |

(See [[03_pulling_strength]] for the BW-gate / weighted-test architecture and the Brzycki estimation.)

**Outdoor sport-grade percentiles** (Mountain Project tick analysis, McCarthy 2022, US crags):

| Grade | Approx percentile of active outdoor climbers |
|---|---|
| 6a / 5.9 | ~50th |
| 6c / 5.10d | ~75th |
| 7a+ / 5.11d | ~91st (top 9%) |
| 7c / 5.12d | ~97th (top 3%) |
| 8a+ / 5.13+ | ~99th (top 1%) |

This is the *real* population sample, not the elite-skewed online polls. A user targeting 7c+ is aiming for the top 3% of active outdoor sport climbers — relevant for honest goal calibration (see [[15_goal_setting_motivation]]).

### 4. Why pulling and finger are tested differently

Common user question. The answer is partly architectural (D85 / D86 specify the finger tests; the pulling tests live in [[03_pulling_strength]] §3) and partly physiological.

- **Finger MVC** is best captured as a brief (5-7 s) max-recruitment effort because finger strength is dominated by neural drive into the forearm flexors. A longer hang would shift the signal toward endurance. 20 mm half-crimp is the standardised edge depth (Lattice / Berta 2025) — large enough to be safe at near-max load, small enough that grip technique can't compensate.
- **Pulling strength** uses a two-stage gate (D84b — covered in [[03_pulling_strength]]): bodyweight reps to failure first (an endurance/capacity measure, also a gate to weighted testing), then weighted 1RM estimated from sub-max AMRAP via Brzycki (D38). Why two stages? A single test can't capture both ends of the user range cleanly.

The honest answer to "why aren't they tested the same way?" is: the underlying capacities are different (isometric finger force vs. multi-joint dynamic pulling), and conflating the test protocol would degrade the signal of both. Keep the two scores distinct in interpretation.

### 5. Axis priority logic — how the engine picks training focus

The macrocycle planner reads the user's axis vector and weighs the **gap between the weakest axis and the strongest axis**. A user with finger=80 / endurance=45 gets a Base phase that biases capillary + strength-endurance work to close the gap. The coach can surface this transparently:

> *"Your endurance axis sits 0.3 SD below finger — that's why the engine prescribed repeaters this mesocycle. The big-picture rule (MacLeod, confirmed by Magiera 2013): your weakest axis is where the next grade jump comes from, not your strongest."*

**What the coach should NOT say:**
- "Your finger axis is bad" → reframe to relative position ("it's your second-weakest; the engine is addressing endurance first").
- "Your pulling axis is great so you don't need to train it" → maintenance volume is still required; detraining starts at 2-4 weeks (see [[20_return_to_training]]).
- "Focus on what you're good at" → contradicts the evidence. MacLeod, Hörst, Lattice all converge on weakness-first programming for intermediate-and-up climbers.

### 6. Age-adjusted interpretation (D83 — recovery, not score)

The engine applies a **recovery multiplier** (1.25-1.75× by age band) for users 40+ (D83 — full table in [[14_female_age_youth]] §9). What this means *for assessment interpretation*: the score numbers themselves are not age-discounted. A 50-year-old at finger axis 70 is genuinely at finger axis 70 — the engine doesn't soften the metric. What changes is *recovery between sessions*, which means a 50-year-old climber at axis 70 may be able to *demonstrate* that score consistently only with longer inter-session recovery than a 25-year-old at the same score.

**What the coach should NOT do:** present older climbers with "adjusted" benchmarks that suggest they're stronger than the raw number indicates. Honest framing: "the number is the number; the recovery overhead is different, and the engine is already accounting for that."

For under-16 / under-18 users, the recovery multiplier interaction is replaced by hard tool restrictions (D80 / D81 — see [[L0_safety_hard_rules]] + [[14_female_age_youth]] §3-5). Assessment scoring still runs, but advanced finger tests (MaxHangs, weighted hangs) are *not eligible* under D80, so the engine fills the finger axis from the climbing-volume + light bodyweight subset, with explicit caveats.

### 7. The OS/RP gap as a technique proxy

The engine doesn't have a direct technique sensor (Seifert 2014's jerk metric, CM-PAT — both deferred, see audit §4.1 UC6). It infers technique from the gap between **on-sight grade** and **redpoint grade**:

- Small gap (≤1.5 grades) at intermediate level → climber can read and execute most beta on first read; technique is keeping pace with physical capacity.
- Large gap (≥3 grades) at the same level → climber can grind a project but struggles to execute on first read. Most often: tactical / movement-vocabulary gap rather than physical (see [[06_technique_movement]]).
- Small gap *and* low physical scores → climber is technique-limited *and* physically under-resourced; the engine prioritises physical Base.

Hörst (Ch.2 self-assessment) frames the same diagnostic as the four-domain question: did the project fail because of physical inability (run out of pump, couldn't hold the hold) or mental quit (climbed past the move you can do)? That's the conversational version of the OS/RP-gap inference.

### 8. The "what's a good score for my age?" question

Users ask this version of the question often. Honest framing has three parts:

1. **The benchmark tables above are not age-stratified at the precision needed to answer this directly.** What we *do* know (Berta 2025; Lattice public data): finger strength peaks in the late 20s to mid 30s in untrained climbers; trained climbers can hold or grow past 40 with appropriate volume. D83 acknowledges *recovery* changes after 40, not absolute capacity.
2. **Comparison should be to the user's own past scores**, not to age peers. Assessment is most useful as a trend line. A 45-year-old retesting at the same finger MVC as 12 months ago is gaining (because untrained peers are losing); the engine reports the trend, not just the point.
3. **For under-16 / under-18**, comparison to adult benchmarks is misleading. The growth-plate epidemiology (Schöffl 2015: 600% increase in epiphyseal fractures; Hochholzer 2005: 23:1 boys-to-girls non-traumatic fracture ratio — covered in [[14_female_age_youth]] §2) means the comparison frame for youth is "is this within safe age-appropriate load," not "is this comparable to a 25-year-old."

---

## How the engine applies this

- **D85** — `test_max_hang` defines the finger MVC test (MVC-7 on 20 mm, total load incl. BW). User-facing test instruction surfaces in the session output, not via this coach file.
- **D86** — `test_max_hang_duration_20mm` defines the bodyweight duration endurance test. Same surfacing pattern.
- **D84b** — two-stage pulling test (`test_pullup_bw` gate → `test_max_weighted_pullup` 1RM via Brzycki D38). Detail lives in [[03_pulling_strength]] §3.
- **D83** — recovery multiplier (1.25-1.75×) applied for users 40+. Does not alter raw axis scores; alters inter-session recovery. Detail in [[14_female_age_youth]] §9.
- **D80 / D81** — for users under 16 / under 18, advanced finger tests are not eligible; the engine fills the finger axis from the climbing-volume + light bodyweight subset and surfaces this caveat to the user explicitly.
- **Axis priority** — macrocycle planner reads the axis vector, computes the gap between weakest and strongest, biases Base + Build phase content toward the weakest axis.
- **OS/RP gap** — engine uses the gap as a technique proxy; the gap drives the size of the technique-allocation slice in the weekly plan (D73 already gives beginners 30%+ technique time; advanced users get less, modulated by the gap).
- **What the engine does NOT do (v1):** age-stratified percentile reporting, sex-stratified benchmark interpolation across all axes, Critical Force as a primary endurance axis (D89 deferred — see [[05_aerobic_endurance_arc]]). These belong to v1.1 or v2.

---

## When user asks…

**"My finger axis is 65 / 100. Is that good?"**

Reframe to relative position. "65 is middle-of-pack for your target grade and middle-of-pack against the public Lattice subset. The more useful question: where does it sit against your other axes? If endurance is at 45, finger isn't your bottleneck — endurance is, and that's what the engine is prescribing this cycle. If everything else is at 75-80, *then* finger is the limiter." Avoid categorical good/bad framing; use relative-position framing.

**"My MVC-7 on 20 mm is 1.6× bodyweight. What grade does that predict?"**

From the table in §3: roughly the 7c+ / V8 range, advanced. But — the table is orientation, not prediction. MacKenzie 2020 found combined physical-axis models explain ~62-77% of grade variance; the remaining 23-38% is technique + mental + tactical + how-many-sessions-projecting (Mountain Project / r/climbharder data confirm wide spread at every finger-strength bin). "Predicted grade" from one test is a probability cloud, not a target. Useful for orientation: "you have the *finger basis* for ~7c+ if the other axes are also there and you put in projecting time."

**"My pulling axis is 80 but my finger axis is 50. What do I train?"**

Finger is the bottleneck. Specifically: the user can pull more than the fingers can grip, which means real-climbing failure modes are at the contact point, not at the pull. Prescription: hangboard work biased to the finger axis (protocol per [[02_finger_strength]] and the user's experience gate D35), with pulling held at maintenance (1 session/week, EL 7 — enough to retain, not enough to grow). Expected retest window: 4-6 weeks for measurable finger MVC change at the neural level; structural change is months. See [[01_periodization]] for the phase logic.

**"Why is my endurance score low if I climb routes every weekend?"**

Two possibilities. (1) Weekend route climbing is volume but not intensity-targeted endurance — the engine's endurance axis reflects the *capacity to sustain near-CP intensity for the duration the route demands*, not pure mileage. If you spend the weekend on 6a routes when you target 7a, you're below the threshold that triggers capillary + mitochondrial adaptation (López-Rivera 2014 — see [[05_aerobic_endurance_arc]]). (2) The test the engine ran is a finger endurance proxy (BW duration hang on 20 mm), which under-weights upper-body / cardiovascular endurance. Possible solutions: ARC sessions inside the climbing volume + targeted repeater protocols if Base phase is active.

**"I'm 45. Should I compare to climbers my age or to the general benchmark?"**

Honest answer: we don't have a precise age-stratified benchmark to give you a "45-year-old percentile" (v1.0 coverage gap). What we do: (1) the engine applies a 1.25-1.5× recovery multiplier (D83) so your between-session recovery accounts for age — that's the operational adjustment. (2) The most useful comparison is *your* trend line: are you holding, growing, or losing axis scores over 12 months? At 45+, holding is gaining (untrained peers are losing). See [[14_female_age_youth]] §9 for the 40+ training adjustments.

**"My OS grade is 6b and my RP grade is 7c. What does that gap mean?"**

A gap of ~4 grades is large. At your physical level the engine reads this as a technique/tactical bias, not a physical capacity gap. You can grind a project (the *physical* capacity is there for 7c) but you read and execute slower on first attempts (the *tactical-cognitive* capacity is the lag). Prescription: more onsight mileage at grades 1-2 below your RP (the engine biases the next cycle toward this), structured route-preview practice (D75 — see [[07_mental_fear_focus]]), and intentional flash attempts. See [[06_technique_movement]] for the drill catalog.

**"When does the engine retest me?"**

That's an engine-internal scheduling question (the firewall keeps the cadence logic out of this file). The session output will surface the next test as a scheduled session. If you're missing your reassessment window, that's a question for the macrocycle view, not a coach question. Generally: tests recur at the boundary between major phases (start of Base, start of Performance), not arbitrarily.

---

## Sources

- Magiera A et al. 2013. The structure of performance of a sport rock climber. *J Hum Kinet* 36:107-117.
- MacKenzie R et al. 2020. Physical and physiological determinants of rock climbing. *Int J Sports Physiol Perform* 15(2):168-179.
- Baláš J et al. 2012. Hand-arm strength and endurance as climbing performance predictors. *Eur J Sport Sci* 12(1):16-25.
- Michailov M et al. 2018. Reliability and validity of finger strength and endurance measurements in rock climbing. *Res Q Exerc Sport* 89(2):246-254.
- Berta P et al. 2025. Validity and normative scores of finger flexor strength and endurance tests. *J Sports Sci* 43(3):245-255.
- Mermier C et al. 2000. Physiological and anthropometric determinants of sport climbing performance. *Br J Sports Med* 34(5):359-366.
- López-Rivera E, González-Badillo JJ. 2014. Hangboard protocol comparison.
- Hörst EJ. 2022. *Training for Climbing* (3rd ed.), Ch.2 — Self-assessment framework.
- MacLeod D. 2010. *9 Out of 10 Climbers Make the Same Mistakes* — weakness-first principle (book not in primary KB; v1.1 will deepen).
- Lattice Training. 2025. *Predictors for bouldering performance by ability level*, n=901. Blog.
- Power Company Climbing. 2023+. *600+ climber dataset* (Hampton / Shortino / Wilson) — outlier space framing.
- McCarthy S. 2022. *Mountain Project tick distribution analysis*, 5 US crags.
- Saul D et al. 2019. Determinants for success in climbing — SR. *J Exerc Sci Fit* 17(3):91-100.

---

## Cross-references

- [[L0_safety_hard_rules]] — D64 absolute (no body-composition guidance from score interpretation); D80/D81 (youth test eligibility restrictions).
- [[01_periodization]] — how the weakest-axis output drives phase content.
- [[02_finger_strength]] — what `test_max_hang` actually measures + protocol depth.
- [[03_pulling_strength]] — D84b two-stage pulling test architecture (BW gate → Brzycki 1RM).
- [[05_aerobic_endurance_arc]] — endurance axis underpinnings + Critical Force v2 caveat.
- [[06_technique_movement]] — what to do when OS/RP gap flags technique as bottleneck.
- [[07_mental_fear_focus]] — D75 route preview protocol referenced in OS/RP gap interpretation.
- [[14_female_age_youth]] — D83 recovery multiplier table, D80/D81 youth restrictions, female-specific assessment caveats.
- [[15_goal_setting_motivation]] — honest goal calibration once benchmarks are read (Mountain Project percentiles).
- [[17_readiness_overtraining]] — interpreting axis-score regression across retests (declining scores as overreaching signal).
- [[20_return_to_training]] — reassessment timing after a break.
