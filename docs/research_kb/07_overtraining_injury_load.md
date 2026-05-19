# Topic 07 — Overtraining, Injury Prevention, Load Management

> **Project:** climb-agent knowledge base
> **Scope:** How to prevent injuries, detect overtraining, and manage training load in climbers
> **Status:** DRAFT v1
> **Date:** 2026-03-16
> **Language:** English (knowledge base standard)
> **Note:** Significant overlap with Consuegra Ch.8 (sections 8.25-8.27, already in synthesis). This topic adds systematic review evidence, load management frameworks, and overtraining detection.

---

## ⚠️ DISCLAIMER

**climb-agent is NOT a medical or physiotherapy tool.** Injury rehabilitation requires healthcare professionals. The engine focuses on **prevention** (training design that reduces injury risk) and **detection** (flagging warning signs). It never diagnoses or prescribes rehabilitation protocols.

---

## Executive Summary

Climbing injuries are predominantly (up to 93%) chronic overuse injuries affecting the upper body, with finger pulley injuries the most common specific diagnosis. The key risk factors are: higher climbing intensity, bouldering, crimp grip use, reduced grip/finger strength relative to demands, and previous injury. The strongest evidence-based prevention strategies are: progressive load management, strength training (especially antagonist/eccentric work), proper warm-up, and avoiding full crimp grip under maximal load. The engine's role is to build programs that respect tissue adaptation timelines, enforce progressive overload, detect overreaching patterns, and include antagonist/injury-prevention exercises in every program.

---

## 1. Injury Epidemiology in Climbing

### 1.1 Key Statistics

- **Incidence:** 2.71 ± 4.49 injuries per 1,000 hours of climbing (Jones et al., 2018); ~4.2 per 1,000 hours including both traumatic and overuse (Quarmby et al., 2023 citing earlier reviews)
- **One-year prevalence:** ~50% of climbers report at least one injury in the previous year (Jones et al., 2008)
- **Point prevalence:** 22.8% (Quarmby et al., 2023)
- **Location:** 63-90% of all injuries occur in the upper body (2024 systematic review cited in secondary source). Lower extremity injuries are more commonly from falls.

### 1.2 Injury Distribution (Schöffl et al., 2015)

| Body Part | Percentage |
|-----------|-----------|
| Fingers | 52% |
| Shoulders | 17.2% |
| Hands | 13.1% |
| Elbows | 9.1% |

**Finger injury subtypes:**
- Pulley injuries: 15.4% (most common — mainly C4, A4, A2, A3 pulleys)
- Capsulitis: 9.5%
- Tenosynovitis: 8.8%

### 1.3 Three Types of Climbing Injury (Consuegra Ch.8)

1. **Chronic/overuse injuries (most common):** significant correlation with climbing grade. Higher-grade climbers, especially boulderers, have higher rates due to overuse and excessive load (Grønhaug 2018, Jones et al. 2008).
2. **Trauma (10%):** falls, bumps, blows. 28% of trauma injuries are caused by moves that are too difficult or demanding.
3. **Postural changes from training:** "climber's back" (Förster et al., 2009) — kyphosis + lordosis, more pronounced in advanced climbers. Misaligned joints become less efficient and more injury-prone.

---

## 2. Risk Factors — Systematic Review Evidence

### 2.1 Quarmby et al. (2023) — First SR on Risk Factors and Prevention

**Citation:** Quarmby A et al. "Risk factors and injury prevention strategies for overuse injuries in adult climbers: a systematic review." *Front Sports Act Living* 2023;5:1269870.

**Scope:** 34 studies included from 1,183 records.

**Confirmed risk factors (consistent evidence):**
- Higher climbing intensity (grade)
- Bouldering (vs lead/sport climbing)
- Reduced grip/finger strength relative to climbing demands
- Use of "crimp" grip (full crimp specifically)
- Previous injury (strongest predictor of future injury)

**Not associated with injury risk (surprising):**
- BMI/body weight
- Warm-up/cool-down routines (no direct evidence of protective effect on injury rates — though warm-up improves performance per Fradkin et al. 2010)
- Stretching
- Taping
- Hydration

**Conflicting evidence:**
- Training volume (some studies find higher volume = more injury, others find no association)
- Age/years of climbing experience
- Sex

**Prevention strategies with evidence:**
- Strength training intervention prevented shoulder and elbow injuries
- Load management and climbing technique could be targeted in prevention programs

### 2.2 Pulley Injury Mechanisms

**Crimp grip = primary mechanism (Miro et al., 2021):**
- A2, A3, and A4 pulleys at highest risk, especially when loaded eccentrically (e.g., foot slip while crimping)
- Forces on the pulley can be up to 4× the force applied at the fingertip
- Schöffl classification: Grade I (strain), Grade II (complete rupture A4 or partial A2), Grade III (complete rupture A2 or A3), Grade IV (multiple ruptures or combined with lumbricalis/collateral ligament damage)
- Grade I-III: conservative treatment (immobilisation, H-tape, protective splint). Grade IV: surgical repair.

**Key prevention insight:** warming up increases physiologic bowstringing and is thought to help prevent injury. Open-hand grip distributes load more safely than full crimp.

---

## 3. Overtraining Spectrum

### 3.1 The Continuum (Meeusen et al., 2013; Firestone 2022)

| Stage | Timeline | Symptoms | Recovery |
|-------|----------|----------|----------|
| **Acute fatigue** | Days after training | Normal tiredness from training stimulus | Hours to days |
| **Functional Overreach (FOR)** | Days to weeks | Generally tired, temporary performance stall/decrease | Few extra rest days |
| **Non-Functional Overreach (NFOR)** | Weeks to months | Very fatigued, resting HR/BP changes noticeable, consistently stagnant or declining performance | Weeks to months |
| **Overtraining Syndrome (OTS)** | Months to years | Chronic under-recovery, sleep and mood disturbance, consistent performance decrease, increased illness | Months to years; may require medical intervention |

### 3.2 Warning Signs for Climbers (Hooper's Beta, Firestone)

1. **Mood changes:** irritability, depression, anger, low motivation for climbing
2. **Persistent fatigue:** waking up not feeling fresh, too tired to train effectively
3. **Chronic pain/soreness:** pain that doesn't resolve after normal recovery period
4. **Performance plateau/decline:** consistently unable to hit expected numbers on familiar tests (e.g., hangboard, known boulder problems)
5. **Reduced coordination:** form deterioration, more falls on familiar terrain
6. **Increased illness frequency:** elevated cortisol suppresses T-cell proliferation → weakened immune response

### 3.3 Engine Detection Approach

The engine can monitor for overtraining patterns through:
- **Performance tracking:** if hangboard test results decline over 2+ consecutive tests despite training, flag potential overreaching
- **Subjective feedback:** post-session RPE tracking; consistently higher RPE for same workload = red flag
- **Session completion rate:** if user consistently can't complete prescribed sessions, load may be too high
- **Rest day compliance:** if user is skipping prescribed rest days, flag risk

---

## 4. Load Management Framework

### 4.1 Acute:Chronic Workload Ratio (ACWR)

The ACWR is the ratio between workload in the past 7 days (acute) and the average weekly workload over the past 28 days (chronic). Originally developed in team sports (Gabbett et al., 2016; Hulin et al., 2015) but the principles apply to climbing.

**Sweet spot:** ACWR of 0.8-1.3 = lowest injury risk
- Below 0.8: undertraining, detraining risk
- 1.0: training at the level you're accustomed to
- Above 1.3: training spike, increased injury risk
- Above 1.5: "danger zone" — significantly elevated injury risk

**Key principle (Gabbett 2016):** high training workloads alone do not cause injuries — it's how you get there. Rapid spikes in load are the primary risk factor, not absolute load. A high chronic workload can actually be protective if loads are built progressively.

**Weekly increase guideline:** limit weekly training load increases to <10% (general sports medicine recommendation).

### 4.2 Climbing-Specific Load Calculation

For the engine, training load can be estimated as: **Session Duration (min) × Session RPE (1-10)**

This gives "arbitrary units" (AU) that can be tracked over time. Example:
- Monday: 90 min climbing session, RPE 7 → 630 AU
- Wednesday: 60 min hangboard + conditioning, RPE 8 → 480 AU
- Friday: 120 min outdoor session, RPE 6 → 720 AU
- Week total (acute load): 1830 AU
- If 4-week average (chronic load) is 1700 AU → ACWR = 1830/1700 = 1.08 (safe)

### 4.3 Tissue Adaptation Timelines

Critical for the engine's progressive overload logic:

| Tissue | Adaptation timeline | Implication |
|--------|-------------------|-------------|
| Muscle | 2-4 weeks for hypertrophy, days for neural adaptation | Fastest to adapt — strength gains come first |
| Tendon | 3-6 months for meaningful structural adaptation | Much slower than muscle — main injury risk area |
| Bone | 6-12 months | Slowest to adapt |
| Capillaries | 1-2 weeks (angiogenesis), 6+ weeks (mitochondrial biogenesis) | From Consuegra Ch.8 / D44 |

The muscle-tendon adaptation mismatch is the primary mechanism for climbing overuse injuries: muscles get stronger faster than tendons can adapt to the new loads, leading to tendon overload. This is why progressive loading and experience minimums (D35: 2+ years before advanced hangboard protocols) are essential.

### 4.4 Consuegra Tendon Injury Cascade (Ch.8)

Already documented in synthesis — summary:
1. Repeated loading → fatigue damage
2. Insufficient recovery → tendon cells increase in number and water content (NOT inflammatory response — ice/NSAIDs ineffective)
3. Continued loading → extra collagen and proteoglycans → pathological thickening
4. Continued further → cell death, new blood vessel growth, discontinuous fibres → 97% of cases lead to tendon rupture (Cook et al., 2017)

---

## 5. Prevention Strategies — Engine Implementation

### 5.1 Already Decided (from previous topics + Consuegra Ch.8)

| Decision | Description | Status |
|----------|-------------|--------|
| D33 | Warm-up protocol generation | v1 |
| D35 | Gate hangboard protocols behind experience check | v1 |
| D41 | Campus board prerequisites and auto-stop rules | v1 |
| D55 | Exercise safety blacklist | v1 |
| D56 | Nordic curl mandatory in injury prevention | v1 |
| D57 | Comprehensive lower body exercise catalog | v1 |
| D58 | Postural correction exercises (anti-climber's-back) | v1 |
| D59 | Hypertonic/inhibited muscle reference table | v1 |
| D60 | Wrist extension protocol for epicondylitis prevention | v1 |

### 5.2 Additional Prevention Principles

**From Quarmby et al. (2023) SR:**
- Strength training is the only intervention with direct evidence of preventing shoulder and elbow injuries in climbers
- Previous injury is the strongest predictor → engine should ask about injury history in onboarding and adjust load accordingly
- Crimp grip carries highest pulley injury risk → engine should recommend open-hand or half-crimp for training (already in D: deadhang technique, Smith and Blumenthal 2016)

**From Consuegra Ch.8:**
- Max strength training >80% 1RM = most efficient injury prevention method (reduces relative stress at submaximal loads)
- Eccentric training (Nordic curl, eccentric pull-ups) builds high strength levels efficiently — best strategy for tendon strengthening
- Earp et al. (2016): training at maximum speed actually reduces tendon damage vs. slow speeds

**Grip safety hierarchy for training:**
1. Open hand (safest, recommended for most training)
2. Half crimp (acceptable)
3. Full crimp (highest pulley injury risk — avoid in hangboard training, use sparingly on wall)

---

## 6. Implications for climb-agent

| Finding | Impact | Priority |
|---------|--------|----------|
| Previous injury = strongest predictor of future injury (Quarmby 2023) | Engine should collect injury history in onboarding and reduce load/add prehab for affected areas | v1 |
| ACWR sweet spot 0.8-1.3; spikes >1.5 = danger zone (Gabbett 2016, Hulin 2015) | Engine can track session RPE × duration and flag load spikes | v1 |
| Muscle adapts in weeks, tendon in months → mismatch is main injury mechanism | Engine must enforce progressive overload timeline, especially for hangboard protocols | v1 |
| Overtraining continuum: FOR → NFOR → OTS | Engine should detect declining performance + elevated RPE as overreaching signals | v1 |
| Crimp grip = primary pulley injury mechanism (Miro et al. 2021) | Engine should recommend open-hand or half-crimp for hangboard, warn against full crimp | v1 |
| Strength training prevents shoulder and elbow injuries (Quarmby 2023) | Antagonist exercises in every program (D58 already covers this) | v1 |
| Weekly load increase <10% guideline | Engine should flag if prescribed volume increases >10% week-over-week | v1 |

### New Decisions

| # | Decision | Rationale | Action |
|---|----------|-----------|--------|
| D68 | **Collect injury history in onboarding** | Quarmby et al. (2023): previous injury is the strongest predictor of future injury. Engine needs this data to adjust load and add targeted prehab. | Add injury history questions to onboarding flow: which body parts, how recently, current pain level |
| D69 | **Implement ACWR-based load monitoring** | ACWR 0.8-1.3 = safe zone. Session RPE × duration gives a simple, trackable metric. Flag when acute load spikes above 1.3× chronic average. | Track session_load = duration × RPE; compute rolling 7-day vs 28-day average; alert if ACWR > 1.3 |
| D70 | **Add overtraining detection heuristics** | Overtraining continuum (FOR → NFOR → OTS) is detectable through performance decline + elevated RPE + session completion rate. Early detection prevents chronic issues. | Flag if: (a) 2+ consecutive test declines, (b) RPE consistently elevated for same workload, (c) sessions frequently incomplete |
| D71 | **Enforce <10% weekly volume increase rule** | General sports medicine guideline for progressive overload. Rapid spikes in load are the primary injury risk factor (Gabbett 2016). | Engine auto-checks week-over-week volume increase; flags or adjusts if >10% |
| D72 | **Default to open-hand grip for all hangboard training** | Full crimp is the primary mechanism for pulley injuries (Miro et al. 2021). Open-hand recommended, half-crimp acceptable, full crimp only on-wall and sparingly. | All hangboard protocols prescribe open-hand or half-crimp by default; full crimp never prescribed on hangboard |

---

## 7. References

1. Quarmby A et al. (2023). "Risk factors and injury prevention strategies for overuse injuries in adult climbers: a systematic review." *Front Sports Act Living* 5:1269870.
2. Miro PH et al. (2021). "Finger flexor pulley injuries in rock climbers." *Wilderness Environ Med* 32(2):259-272.
3. Schöffl V et al. (2015). Study on most common climbing injuries (cited in Consuegra Ch.8). Finger injuries 52%, shoulder 17.2%.
4. Jones et al. (2018). Injury rate 2.71 ± 4.49 per 1,000 hours.
5. Jones et al. (2008). 50% one-year injury prevalence.
6. Grønhaug (2018). Correlation between injury probability and climbing grade.
7. Förster et al. (2009). "Climber's back" — kyphosis + lordosis.
8. Cook et al. (2017). Tendon injury cascade — 97% rupture if load continues.
9. Gabbett TJ (2016). "High training workloads alone do not cause sports injuries: how you get there is the real issue." *Br J Sports Med* 50:444-445.
10. Hulin BT et al. (2015). "The acute:chronic workload ratio predicts injury." *Br J Sports Med* 50:231-236.
11. Meeusen R et al. (2013). European College of Sport Science position statement on overtraining.
12. Hooper's Beta (2022). "6 signs training load is too high."
13. Firestone J (2022). "Overtraining in climbers: what it is, how to spot it, and how to deal with it."
14. Earp JE et al. (2016). Effects of lifting speed on tendon compression and activation (cited in Consuegra Ch.8).
15. Fradkin AJ et al. (2010). Warm-up meta-analysis: 79% of performance factors affected (cited in Consuegra Ch.8).
16. Smith and Blumenthal (2016). Correct deadhang technique (cited in Consuegra Ch.8).
17. Van Dyk et al. (2019). Nordic curl SR: 51% lower injury rate (cited in Consuegra Ch.8).
18. Artiaco S et al. (2023). "Flexor tendon pulley injuries: a systematic review." *J Hand Microsurg* 15(4):247-252.

---

*End of Topic 07 — 5 new decisions (D68-D72), 18 references. Much content cross-referenced from Consuegra Ch.8 synthesis.*
