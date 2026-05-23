# L3 — Female / Age / Youth

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC14.
> **Token target:** ~5,000.
> **Status:** v1.0 — ready, with documented coverage gap on menstrual cycle (see below).
> **Source files distilled:** `docs/research_kb/10_female_age_youth.md` (T10), `horst_ch13_injury_synthesis.md` (youth content §3.8 + §8), decision consolidation D80, D81, D82, D83.
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table, row `14_female_age_youth`).

> **v1.0 coverage gap (menstrual cycle):** Bruinvels 2022 (cycle transitions vs phases) and the Phillips/Colenso-Semple 2023 umbrella review are referenced in the audit as deepening sources. T10 already integrates the headline conclusions of both — the gap is depth of distillation, not direction. **More critical scope constraint:** D82 (menstrual cycle tracking + adjustment) is **v2 in the engine**. In v1, this file presents the existing evidence and the autonomy-respecting default ("track symptoms, not phases") as **educational reference**, NOT as prescription. Coach must not recommend cycle-phase-based programming as if the engine implemented it. v1.1 will deepen the Bruinvels detail; v2 will ship the optional cycle-tracking feature with the engine adaptation.

---

## Quick reference

Three populations require specific engine awareness: (1) **youth climbers <16-18** carry vulnerable growth plates and need hard restrictions on campus, max hangboard, and weekly volume; (2) **female climbers** face elevated RED-S risk and may benefit from individual symptom tracking, but cycle-phase prescription is **not evidence-based** and the engine does **not** prescribe by phase; (3) **older climbers 40+** need extended recovery windows because tendon adaptation and HGH-dependent repair both slow with age. The two hard safety rules: D80 (youth <16 block campus/max hangboard/hypergravity, no exceptions) and D81 (≤4 training days/week through age 18). D64 (no body-composition guidance) is non-negotiable across all populations, particularly relevant for female climbers given the documented RED-S risk in the discipline.

---

## Core findings

### 1. Youth climbers (<18) — the structural risk

Youth climbing has a unique injury risk profile: **growth plate (epiphyseal) fractures in the fingers**, which can permanently deform joint architecture. Two data points anchor the urgency:

- **Schöffl 2015:** 600% increase in growth plate fractures in youth climbers over the previous decade. The trend reflects rising training intensity (campus, fingerboard, hypergravity) reaching younger climbers.
- **Schöffl 2023 prospective analysis:** 45% of all injuries in adolescent climbers were growth plate-related (T10 §2.1).

**Why growth plates matter:** the epiphysis (cartilaginous growth zone at finger bone ends) closes around age 17 in most climbers. Until closure, the growth plate is mechanically weaker than the surrounding bone and the supporting ligaments — under high crimp load it fractures before either of those tissues fails. Once damaged, the fracture can cause permanent angular deformity (Hörst Ch.13 §3.8). There is no rehabilitation that grows the plate back.

**Peak risk window:** ages 10-14 for girls, 12-16 for boys — the rapid growth velocity phase (Schöffl, Hörst Ch.13). Most growth plate fractures cluster in ages 13-15.

**Hochholzer 2005:** of 24 junior climbers with non-traumatic epiphyseal fractures, only one was a girl. Boys are at substantially higher risk under the current evidence — but the lower female rate may reflect lower training volume rather than biological protection. The conservative default applies to both sexes.

**Only 15% of surveyed adolescent climbers correctly identified growth plate injuries as the most common youth-specific injury** (Meyers 2020). The coach's role: name the risk explicitly when working with a sub-16 user or their parent, because the surrounding climbing culture often won't.

### 2. D80 — Youth <16 hard restrictions

The L0 rule (see [[L0_safety_hard_rules]]):

> **D80 — Users <16:** block campus board, MaxHangs, hypergravity, weighted hangs, one-arm hang training. No exceptions.

The rationale isn't conservatism; it's irreversibility. The full prohibition list (Schöffl + Hörst Ch.13 consensus):

| Training tool | Under 16 | 16-18 | Over 18 |
|---|---|---|---|
| Campus board, double dynos | ❌ never | ⚠️ caution, post-skeletal-maturity assessment | ✅ with [[02_finger_strength]] + D41 prerequisites |
| Campus board, large-hold laddering | ⚠️ small amounts, 1-2×/wk, smooth movements only | ✅ with prerequisites | ✅ with prerequisites |
| Max-weight hangboard | ❌ never | ⚠️ only after 2 yr systematic training (D35) | ✅ with D35 prerequisites |
| Min-edge hangboard | ❌ never | ⚠️ only after 2 yr systematic | ✅ with prerequisites |
| Hypergravity (added weight on climbing/board) | ❌ never | ⚠️ caution | ✅ progressive |
| Full crimp grip | ⚠️ avoid; favor open-hand | ⚠️ minimize; favor open-hand | ⚠️ minimize on hangboard (D72) |

**Why no exceptions:** parents and competitive contexts will sometimes push back ("but my child is exceptionally talented / already strong / training with a coach"). The coach's response: growth plate fractures don't care about talent or coaching quality. The two leading causes — campus training and intensive fingerboard work — are the exercises being requested. The mechanism is mechanical, not training-quality-mediated.

**What youth climbers CAN do (positive prescription):** unrestricted climbing volume on terrain that doesn't repeatedly load full crimp at limit; technique drills; antagonist and mobility work ([[12_antagonist_postural]]); aerobic conditioning; second-sport development.

### 3. D81 — Youth ≤4 training days/week

The L0 rule:

> **D81 — Users <18:** max 4 climbing or training days/week. Remaining 3 are full rest or non-climbing activity.

This is **harder for users and parents to accept than D80** because it sounds like "do less when motivated to do more." The evidence framing (Hörst Ch.13 §8):

- Chronic overuse, not acute injury, is the leading cause of youth-climber injuries that derail long-term careers.
- During growth spurts (ages 13-15 for most), >10-12 h/week climbing significantly elevates injury risk.
- Hörst's framing: *"the youth athletes who actually peak as adults are the ones who train less in their teens"* — the cap protects long-term career length, not weekly commitment.
- Off-season recommendation: 1-4 months/year with little or no climbing (Hörst, Schöffl).
- Second-sport participation through age 16 is strongly recommended (motor-skill diversification, joint loading variation).

**During the steepest growth-spurt year (typically ages 13-15):** drop to **3 days/week max** during the highest growth velocity months. The engine doesn't currently auto-detect growth-spurt timing; the coach raises it when the user's onboarded age + reported height/weight history suggest active growth.

### 4. D80 + D81 + D68 chain for youth onboarding

If onboarding flags age <18, the engine enforces:

1. **D80 prohibitions** (campus, MaxHangs, hypergravity, weighted hangs, one-arm) — these exercises don't appear in session generation.
2. **D81 day cap** (≤4 days/week, ≤3 during growth spurt) — week planner won't schedule more.
3. **Open-hand grip preference** carried through into hangboard sessions where allowed.
4. **D68 (injury history as permanent gate)** — any prior finger pain at PIP joint, growth plate symptom, or campus-related injury history → additional restrictions retained even after the user turns 18.

The coach surfaces the rationale on first encounter ("I see you're 15 — here's why the plan doesn't include campus or weighted hangboard yet") rather than waiting for the user to ask why their plan looks different from a friend's.

**Hard-and-fast rule from Hörst Ch.13:** *any youth climber with chronic finger pain ceases climbing for a few weeks and consults a doctor if pain persists.* Particular flag: dorsal finger pain at the PIP joint = potential growth plate stress, immediate medical attention.

### 5. Youth nutrition and sleep (no body-comp guidance)

Hörst Ch.13 §8 anchors:

- **Calorie restriction is inappropriate in almost all situations for adolescents** — direct quote intent. Coach must reinforce this if a youth user or parent raises weight as a performance lever.
- Three meals a day with fruits, vegetables, lean meats, low-fat dairy. Climbing-time snacks (energy bars, bagels, low-fat chocolate milk).
- Sleep: 9-10 h/night optimal, 8 h minimum.
- Deliberate underweight for competition = harmful to developing bodies.

[[L0_safety_hard_rules]] D64 (no body-composition guidance) applies with even greater weight to youth users. Any conversation about weight or body composition pivots to fueling for performance + recommendation to involve a sports dietitian familiar with adolescent athletes.

### 6. Female climbers — the menstrual cycle question (v2 in engine)

> ⚠️ **v1 scope constraint:** the engine does **not** implement cycle-phase-based training in v1.0. D82 is v2. This section describes the existing evidence and the autonomy-respecting framework as **educational reference**, so the coach can answer informed questions without prescribing what the engine doesn't actually adapt.

**The evidence is inconclusive on phase-based prescription.**

- **Phillips et al. 2023 umbrella review** (*Front Sports Act Living* 5:1054542): no influence of menstrual cycle phase on acute strength performance or longer-term strength/hypertrophic adaptations to resistance training. The reviewed literature is highly variable, mostly due to inconsistent methodology.
- **McNulty et al. meta-analysis (51 studies):** exercise performance may be trivially reduced only in the early follicular phase (days 1-5). That's the only signal that survived meta-analysis.
- **Niering 2024 SR+MA + Hackney 2025 historical review** (per audit §4.3): reinforce the umbrella conclusion.

**Individual symptom experience, however, is real and common.**

- Lattice Training Female Climber Series: ~93% of athletes report some menstrual cycle-related symptoms; ~65% report symptoms affecting training.
- Bruinvels et al. 2021 Strava analysis (n>14,000): two-thirds of women report training-affecting cycle symptoms; the variation is across *individuals*, not predictable by phase universally.
- Bruinvels et al. 2022 (referenced in audit): cycle *transitions* (the days entering or leaving menstruation, or shifting between phases) may matter more than the phases themselves for individual experience.

**The autonomy-respecting framework (KB default position):**

| Approach | Status |
|---|---|
| Track individual symptoms (energy, RPE, fatigue) over 3-6 months | Optional, useful for self-knowledge |
| Adjust intensity by symptom self-report (low energy day → reduce intensity 20%, higher RPE than expected → shorter session) | Evidence-aligned (responds to actual state, not predicted phase) |
| Schedule lighter days during reported symptomatic period | User's call, respects autonomy |
| Prescribe higher-intensity work in follicular phase, lower-intensity in luteal | **Not evidence-based** — coach must not prescribe this as if the science backs it |
| Sync deload weeks to cycle | Possible self-experiment, not engine-prescribed |

The Lattice and Climbing Doctor protocols sometimes appear to prescribe by phase. The honest summary is that they're describing patterns reported by some athletes — not patterns the controlled evidence supports as causal. The engine's coach voice should not contradict Lattice but should be explicit about the evidence boundary.

### 7. RED-S risk in female climbers (D64 absolute)

Already covered in [[08_nutrition]]. Critical climbing-specific data:

- **15.8% amenorrhoea prevalence** in elite female competition climbers (Joubert et al. 2022). For context, the general athletic population baseline is 2-5%.
- **Climbing culture's "lighter = better" narrative** is a documented risk factor.
- **Missing 3+ menstrual cycles** = significantly elevated injury risk (Lattice; in line with IOC RED-S consensus).
- IFSC uses BMI margins for competition eligibility but the medical infrastructure is judged insufficient by the sports medicine community.

**The engine's response (D64, [[L0_safety_hard_rules]]):**

- Never suggest weight loss.
- Never comment on body composition.
- Never imply a target weight.
- Flag amenorrhoea or persistently irregular cycles (if the user volunteers the information) as a potential RED-S indicator requiring medical / sports-dietitian consultation.
- Pivot any weight-related conversation to fueling for performance.

This applies to female and male climbers; the prevalence difference doesn't change the rule, only the salience for population-level framing.

### 8. Sex collected at onboarding — what for and what NOT for

The engine asks sex at onboarding. The legitimate uses (v1):

- **Assessment benchmarking** — Lattice n=901 normative ranges differ by sex; percentile placement on finger strength tests uses the correct reference distribution.
- **Population context** (e.g. RED-S salience for female users, growth plate prevalence framing for sub-16 male users).
- **Future cycle tracking** if/when D82 ships in v2 (opt-in only).

The **non-uses** (the engine does NOT do these):

- Differential phase weights by sex.
- Different exercise prescriptions by sex outside the assessment normative reference.
- Auto-applied cycle-phase adjustments (D82 is v2).
- Any body-composition-derived recommendation.

When asked "why are you asking my sex," the answer is the legitimate-use list. If sex is collected for a v2 feature not yet shipped, the coach should be honest about that.

### 9. Older climbers (40+) — recovery timeline shifts

D83 anchors the engine's age-based recovery multiplier:

| Age band | Recovery multiplier (vs younger baseline) |
|---|---|
| 40-50 | 1.25× |
| 50-60 | 1.5× |
| 60+ | 1.75× |

The biology (T10 §3.1):

- **Recovery slows from age 40 onward.** Subjective: more lingering soreness, more day-after-day-after fatigue.
- **Sarcopenia** (age-related muscle loss) starts at age 30-35; Type II fibers preferentially lost. Mitigated by continued strength training + adequate sleep.
- **Tendon adaptation already slowest tissue, becomes more vulnerable with age.** Volume progression even more conservative than the D71 ≤10%/week default.
- **HGH (growth hormone) secretion decreases with age**, further slowing recovery. Deep sleep (HGH is sleep-dependent) becomes the #1 modifiable recovery factor.
- **Bone density** is a concern post-menopause for female climbers. Strength training has a protective effect — *don't deload strength work entirely* in older female users; protect it.

**Engine adjustments active in v1 for users 40+:**

- Extended inter-session recovery: where a 25-year-old might recover from a hangboard session in 48 h, a 45-year-old may need 72+ h. Session-spacing in the week planner respects this.
- Conservative volume progression: D71 ≤10% weekly is the floor; for older users, the engine biases toward 5-7% week-on-week as the default.
- Warm-up emphasis: longer warm-ups in session generation for 40+ users (reduced tissue elasticity increases warm-up requirements; see [[12_antagonist_postural]]).
- Strength work is preserved through training cycles, not de-prioritized.

**Older climbers ask one question often:** *"Am I just done improving?"* The honest answer: no — strength gains are possible into the 60s, multiple case studies of climbers progressing well past 50 exist. What changes: the rate is slower, the recovery cost of each gain is higher, the injury cost of a mistake is also higher. The plan trades aggressive progression for sustainability.

### 10. Older climbers — additional considerations

- **Joint health:** glucosamine sulfate has evidence for older athletes (Reginster 2001 referenced in Hörst integration audit); omega-3 (2-4 g/day) has anti-inflammatory and tendon-supportive evidence (Maroon 2006). Both are v2 coaching cues, not v1 engine prescriptions, but coach can mention if user asks about supplements.
- **Sleep is the dominant lever.** Insist on 8+ h. Watson 2017 (<7 h = injury risk) applies more sharply with age.
- **Hydration sensitivity rises** with age; baseline thirst signal weakens. Coach can mention; don't be prescriptive.
- **Heart rate at fixed intensity rises with age** (max HR drops ~1 bpm/year past 30); RPE-based intensity targeting is more reliable than HR-based targeting for older climbers.

### 11. Female + age + youth — the overlap cases

- **Female youth (under 18):** D80 + D81 + D64 apply with combined weight. The growth plate risk applies equally to girls and boys despite the lower observed fracture rate (Hochholzer 2005 may reflect lower volume more than biological protection).
- **Female 40+:** D83 recovery multiplier + bone density consideration (preserve strength training) + RED-S salience continues (perimenopausal hormonal shifts can complicate signal interpretation — recommend medical/dietary consultation, don't try to interpret in-app).
- **Male youth (under 18):** D80 + D81 — and the growth plate fracture rate (boys 23:1 in Hochholzer) makes the coach's warning particularly load-bearing. Don't soften.
- **Male 40+:** D83 recovery multiplier + cardiovascular screening recommendation for newly-returning climbers. Not engine-prescribed, but coach surfaces if user is restarting after long break.

---

## How the engine applies this

- **D80 (youth <16 prohibitions):** session generation filters out campus, MaxHangs, hypergravity, weighted hangs, one-arm. The session catalog respects the age filter at planner output level.
- **D81 (≤4 days/week for <18):** week planner caps scheduled days at 4 (3 during reported growth spurt period if the coach surfaces it from user history).
- **D68 (injury history permanent gate):** youth-onboarding injury entries persist forever — turning 18 doesn't reset them.
- **D82 (menstrual cycle adjustment) is v2** — not implemented in v1.0 engine. Coach surfaces the educational framework above when asked, but **does not pretend the engine adapts to cycle phase**.
- **D83 (40+ recovery multiplier):** session-spacing in the week planner scales rest days by the age-band multiplier; volume progression caps tighten from D71 ≤10% to ≤5-7%/week.
- **D64 (no body-composition guidance):** absolute across all populations, applies in every conversation regardless of trigger.
- **Sex at onboarding** is used for Lattice normative comparison in [[16_assessment_interpretation]] and for population-context framing; not for differential phase weights in v1.

---

## When user asks…

**"My 14-year-old wants to start hangboarding — what's the protocol?"**

D80 + Hörst Ch.13 §3.8. The honest answer: at 14, no MaxHangs, no min-edge work, no hypergravity, no weighted hangs. The growth plate fracture rate has increased 600% in a decade, driven by exactly these protocols (Schöffl 2015). What's appropriate: climbing volume itself (the supporting tissues adapt at the right pace), open-hand grip preference over full crimp, no campus, ≤4 days/week. If the user wants any hangboarding at all, the most conservative version is light open-hand work on a 20mm edge at bodyweight only, infrequently (1×/wk max), as a movement-pattern familiarization. Real hangboard protocols revisit at 16-18, with 2 years systematic experience (D35). Frame it positively: the climbers who peak as adults trained less in their teens.

**"I'm 15 and I've been crushing it, I want to do campus board like everyone in my gym."**

Direct, no waffling: at 15, campus is off the table. Not because of skill or talent — because of growth plate biology. Schöffl 2015 documented a 600% increase in growth plate fractures, with campus as one of the leading mechanisms. The damage is permanent (you don't regrow growth plates), and the injury rate spikes in the 13-15 range when the plates haven't ossified yet. The 7c-or-whatever you've climbed doesn't change the bone biology. We revisit at 16-18, when D35 (2 years systematic) and the campus prerequisite gate (D41) both apply. Until then, max climbing days and crushing limit boulders on real terrain is the right plan.

**"Should I train differently during my period?"**

Honest evidence summary first: the umbrella review (Phillips/Colenso-Semple 2023) finds no consistent effect of cycle phase on strength performance or training adaptations. The McNulty meta-analysis found at most a trivial reduction in the early follicular days. So evidence does not support cycle-phase-based prescription. What does work: track your own energy and RPE for 3-6 months — if you notice consistent patterns, adjust intensity by symptom, not by phase. If you have low energy on a given day, drop intensity 20%; if RPE is higher than expected, shorten the session. The engine doesn't auto-adjust by cycle phase in v1 — that's a v2 feature with opt-in tracking. Anyone telling you "you must train harder in follicular and easier in luteal" is going beyond what the evidence supports. Your individual experience is the data that matters.

**"My periods stopped 4 months ago and I'm climbing well — is this a problem?"**

Yes, it is, and the conversation matters. Amenorrhoea (3+ missed cycles) is a RED-S (Relative Energy Deficiency in Sport) signal — the body shutting down reproductive function because available energy is below requirements. This pattern carries elevated injury risk (Lattice; IOC RED-S consensus). Even if performance currently feels good, the cumulative trajectory is fragility — bone density loss, eventual finger or stress-fracture injuries. This is outside what a training app can address: please book a sports dietitian or sports medicine doctor familiar with female athletes. It's worth doing now, while you still feel strong. Don't wait for an injury to force the conversation.

**"I'm 52, just got back into climbing after 15 years — how should I think about plans?"**

A few simultaneous things. Recovery: at 52, expect 1.5× the inter-session recovery a 25-year-old needs — the engine accounts for this. Tendons: the slowest-adapting tissue is now slower again; volume progression caps below D71's 10%/week default (we target 5-7% as the operating ceiling). Strength work: keep it in the plan — sarcopenia and (if you're female, post-menopausal bone density) both benefit from continued strength training. Sleep: 8+ h is non-negotiable, not aspirational. The good news: capable improvement is realistic into your 60s. The shape of progress shifts from "how hard can I push" to "how consistently can I show up without breaking" — and that shift suits climbing well. The user who climbs 4 days/week intelligently in their 50s beats the user who climbs 6 days/week and reinjures every 4 months.

**"Why is the engine asking my sex?"**

Two reasons in v1: (1) assessment benchmarking — the Lattice n=901 dataset has different normative ranges by sex, so your finger strength percentile uses the correct reference distribution; (2) population context — RED-S risk salience is meaningfully higher in female climbers, growth plate fracture patterns differ in youth. The engine does **not** use sex to differentially weight your training phases, prescribe different exercises, or auto-adjust to menstrual cycle phase. Cycle-aware programming is a v2 feature that will be opt-in if you want it.

---

## Sources

- Schöffl V et al. 2022. Diagnostic-therapeutic algorithm for finger epiphyseal growth plate stress injuries. *Am J Sports Med* 50(1):229-237.
- Schöffl V et al. 2015. Documenting the 600% increase in growth plate fractures over the prior decade.
- Schöffl V et al. 2023. Prospective analysis: 45% of youth injuries are growth plate-related.
- Hochholzer T 2005. 24 junior climbers with non-traumatic epiphyseal fractures (23 boys, 1 girl).
- Meyers RN et al. 2020. Adolescent climbers' awareness of youth-specific injuries. *Int J Environ Res Public Health* 17(3):812.
- Morrison A, Schöffl V 2007. Literature review: recommendations for climbers <16. *Br J Sports Med* 41:852-861.
- Hörst EJ 2022. *Training for Climbing* 3rd ed. — Ch.13 §3.8 (growth plate), §8 (youth special section), youth nutrition.
- Consuegra S 2023. *The Science of Climbing Training* — Ch.8: López-Rivera contraindications (<16, <2 yr systematic).
- Phillips SM et al. 2023. Umbrella review on menstrual cycle and resistance exercise. *Front Sports Act Living* 5:1054542.
- McNulty KL et al. Meta-analysis of menstrual cycle and exercise performance (51 studies). *Sports Med.*
- Bruinvels G et al. 2021. Strava menstrual-cycle symptoms analysis (n>14,000).
- Bruinvels G 2022. Cycle transitions vs phases — symptom patterns.
- Niering M et al. 2024. SR+MA reinforcing the no-phase-effect conclusion (per audit §4.3).
- Hackney AC 2025. Historical review of menstrual cycle and exercise (per audit §4.3).
- Joubert LM et al. 2022. Amenorrhoea prevalence in elite female competition climbers (15.8%).
- Lattice Training 2023/2024. "The Female Climber" series; "The Effect of Your Menstrual Cycle on Your Training" (2025).
- Climbing Doctor 2023/2024. "Training with your Cycle" + "Hormone Cycles and the Female Rock Climber."
- Reginster JY 2001. Glucosamine sulfate for joint health (older athletes).
- Maroon JC 2006. Omega-3 anti-inflammatory dosing (2-4 g/day).
- Watson AM 2017. Sleep <7 h elevates injury risk in athletes.

**Pending v1.1:** deeper Bruinvels 2022 distillation (cycle transition patterns); structured perimenopausal training literature review (gap in current KB).

---

## Cross-references

- [[L0_safety_hard_rules]] — D80 (youth <16 hard block), D81 (youth ≤4 days/wk), D64 (no body-comp guidance), D72 (open-hand default), D35 (hangboard experience gate), D68 (injury history permanent gate).
- [[08_nutrition]] — RED-S detail, youth nutrition, fueling for performance reframe.
- [[09_recovery_sleep]] — extended recovery for 40+, sleep priority.
- [[10_injuries_fingers]] — growth plate fracture detail (cross-reference here is identical).
- [[11_injuries_shoulder_elbow]] — antagonist work for shoulder protection (especially post-40).
- [[12_antagonist_postural]] — warm-up emphasis for 40+, mobility for all populations.
- [[16_assessment_interpretation]] — sex-stratified Lattice normative data.
