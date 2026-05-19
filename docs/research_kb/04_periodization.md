# Topic 04 — Periodization: Science, Models, Deload, Tapering

> **Project:** climb-agent knowledge base
> **Scope:** Periodization models, evidence base, deload science, tapering, supercompensation, phase design
> **Status:** DRAFT v1 — research compilation
> **Date:** 2026-03-16
> **Language:** English
> **Cross-references:** `DESIGN_GOAL_MACROCICLO_v1_1.md` (engine implementation), `literature_review_climbing_training.md` §5 (model comparison, phase weights)

---

## Executive Summary

Periodization is the backbone of climb-agent's training engine (Hörst 4-3-2-1 + DUP concurrent). The scientific evidence supports our approach: periodized training produces moderately better strength gains than non-periodized training (ES = 0.31-0.43, multiple meta-analyses), and **undulating periodization is slightly superior to linear for trained individuals** (ES = 0.61 for trained, Moesgaard 2022). However, the effect on hypertrophy is negligible regardless of model. For climbing specifically, no RCTs compare periodization models — all evidence is extrapolated from general strength/sports science.

**Key findings for our engine:**
- Periodization vs. no periodization: moderate effect (ES 0.43, Williams 2017)
- DUP vs. Linear: similar for beginners, DUP slightly better for trained (Moesgaard 2022)
- LP vs. DUP for hypertrophy: no difference (Cohen's d = −0.02, Grgic 2017)
- Consuegra 2023 (climbing-specific): recommends ATR block model for multiple peak phases
- Deload: every 3-6 weeks, reduce volume 50-75%, maintain intensity and frequency
- Taper: reduce volume 60-90%, maintain intensity, reduce frequency ≤20% (Mujika & Padilla 2003)
- Taper produces ~2-6% performance improvement; progressive nonlinear taper > step taper
- Our 4-3-2-1 + DUP hybrid is well-supported but could benefit from more flexible phase durations

---

## 1. The Science of Periodization

### 1.1 What Periodization Actually Is

Periodization is the systematic organization of training into sequential phases and cyclical time periods to:
- Maximize specific performance adaptations
- Minimize risk of overtraining and injury
- Allow for peak performance at planned times
- Manage the competing demands of multiple fitness qualities

The hierarchy: **Macrocycle** (full plan, 10-52 weeks) → **Mesocycle** (phase, 2-6 weeks) → **Microcycle** (week)

### 1.2 Meta-Analyses — The Hard Numbers

**Williams et al. 2017** (*Sports Medicine*) — The definitive meta-analysis:
- 81 effect sizes from 18 studies (1988-2015)
- Periodized > non-periodized for 1RM strength: **ES = 0.43** (95% CI 0.27-0.58, P < 0.001)
- **Undulating programs more favorable** than linear (β = 0.51, P = 0.001)
- Untrained participants showed greater gains than trained (β = −0.59, P = 0.031)
- Longer studies and higher training frequency = larger improvements
- "Variation in training stimuli appears to be vital for increasing maximal strength"

**Moesgaard et al. 2022** (*Sports Medicine*) — Updated, volume-equated:
- 35 studies, 1187 participants
- Periodized > non-periodized for 1RM: **ES = 0.31** (P = 0.02)
- UP > LP for 1RM: **ES = 0.31** (P = 0.04)
- Subgroup: UP > LP only for **trained** (ES = 0.61), not untrained (ES = 0.06)
- No difference in hypertrophy between ANY models (ES = 0.05-0.13, all non-significant)
- "Effects of periodization on maximal strength may be related to neurophysiological adaptations"

**Grgic et al. 2017** (*PeerJ*) — LP vs. DUP for hypertrophy:
- 13 studies
- Cohen's d = −0.02 (P = 0.848) — virtually identical
- "When LP and DUP are volume-equated, there is no evidence that one outperforms the other for hypertrophy"

**Harries et al. 2015** (*J Strength Cond Res*) — LP vs. UP for strength:
- No significant differences between LP and UP for upper- or lower-body strength

### 1.3 Key Takeaways from the Evidence

| Finding | Confidence | Implication for climb-agent |
|---------|-----------|---------------------------|
| Periodized > non-periodized for strength | High (multiple MAs) | Our engine is justified vs. "just climb" approach |
| DUP ≥ LP for trained athletes (strength) | Moderate-High | Our DUP concurrent approach is correct for intermediate+ |
| LP = DUP for beginners | High | Engine could simplify to linear for beginners |
| No model difference for hypertrophy | High | Periodization choice doesn't matter for muscle size; focus on volume |
| Longer training periods = larger effects | Moderate | Multi-macrocycle thinking is important; 10 weeks alone won't transform |
| Higher frequency = larger gains | Moderate | 3-4x/week better than 2x/week for finger training |

---

## 2. Periodization Models for Climbing

### 2.1 Linear Periodization (LP / Traditional / Matveyev)

**Structure:** Volume decreases linearly, intensity increases linearly across the macrocycle.
- General → Specific preparation → Competition → Transition

**Pros for climbing:**
- Simple to understand and follow
- Builds strong base before specialization
- Lower injury risk (progressive approach)
- Best for beginners (evidence: LP and DUP produce same results in untrained)

**Cons for climbing:**
- Single peak — only one "performance window" per cycle
- Detraining of qualities not being trained in current phase
- Long time to reach peak form
- Not recommended for advanced athletes (Matveyev's own model has been criticized)

### 2.2 Block Periodization (ATR Model — Issurin)

**Structure:** Short, concentrated blocks focusing on one quality, with maintenance doses of others.
- **A**ccumulation → **T**ransmutation → **R**ealization
- Each block: 2-4 weeks (shorter than traditional phases)

**Pros for climbing:**
- Multiple peaks possible per season (critical for outdoor climbers with multiple trips)
- Concentrated stimulus = strong adaptation signal
- Maintenance doses prevent detraining
- Consuegra (2023) specifically recommends this for climbing

**Cons for climbing:**
- Requires careful planning to maintain all qualities
- More complex to implement in an automated system
- Risk of overtraining if accumulation blocks are too aggressive

### 2.3 Daily Undulating Periodization (DUP / Non-Linear)

**Structure:** Volume and intensity vary daily or weekly within each week.
- Example: Monday = strength, Wednesday = power endurance, Friday = endurance

**Pros for climbing:**
- Maintains all qualities simultaneously
- Avoids detraining
- Evidence-supported for trained athletes (ES = 0.61 vs LP, Moesgaard 2022)
- Psychologically varied (reduces boredom)
- Bechtel and Hörst both advocate this for advanced climbers

**Cons for climbing:**
- Potentially diluted stimulus per quality (jack of all trades concern)
- Complex fatigue management (need HIGH/LOW alternation)
- Not clearly superior for beginners

### 2.4 Our Model: Hörst 4-3-2-1 + DUP Concurrent (Hybrid)

climb-agent uses a **hybrid approach** that combines:
- **Sequential phases** (LP element): Base → Strength → PE → Performance → Deload
- **Concurrent training** (DUP element): Within each phase, ALL qualities are trained but at different percentages

**This is well-supported because:**
1. The sequential phases ensure focused adaptation periods (block-like)
2. The DUP concurrent element prevents detraining (DUP advantage)
3. Phase weights shift gradually (not binary on/off for any quality)
4. Deload is programmed (recovery science)
5. The model simplifies block periodization without requiring ATR-level complexity

**What the literature suggests could improve:**
- Phase durations could be more flexible (currently somewhat rigid at 2-4 weeks)
- A more explicit "overreach → taper" protocol before Performance phase
- Beginner-specific simplification (fewer phases, longer base, simpler DUP)

---

## 3. Deload Science

### 3.1 What a Deload Is

A deload is a planned period of reduced training stress (typically 1 week) designed to:
- Dissipate accumulated fatigue
- Allow tissue repair (especially tendons: 24-72h for muscle, days-weeks for tendons)
- Mental recovery and motivation reset
- Enable supercompensation before next training block

### 3.2 Evidence for Deloads

**The uncomfortable truth:** There is almost no direct research on deload weeks specifically (Hooper's Beta 2024). Most evidence is extrapolated from taper research.

**What we know:**
- Supercompensation is a real phenomenon: after training stress and adequate recovery, performance temporarily exceeds baseline
- The fitness-fatigue model (Bannister 1976) explains why: fitness decays slowly, fatigue decays fast → net performance peaks after fatigue dissipates
- Training produces both fitness gains and fatigue accumulation simultaneously
- Without planned recovery periods, fatigue accumulates faster than fitness gains (overreaching → overtraining)

**What Hooper's Beta (2024) argues:**
- Deloads have "no research to show they necessarily lead to better training outcomes"
- Only one study compared deload vs. non-deload groups → non-deload performed better (but methodological issues)
- "If you need deloads, it might be a sign of poor programming" — controversial but worth noting
- Recommends tapers before competitions/trips instead of routine deloads

### 3.3 Practical Deload Guidelines

Despite limited direct evidence, coaching consensus is strong:

| Parameter | Deload Guideline | Source |
|-----------|-----------------|--------|
| Frequency | Every 3-6 weeks (4 weeks most common) | Hörst, Lattice, Bechtel, general S&C |
| Volume reduction | 50-75% | Hooper's Beta, general consensus |
| Intensity | Maintain (do NOT reduce intensity significantly) | Mujika & Padilla 2003, all sources |
| Frequency | Maintain or slight reduction (drop 1 session) | Mujika et al., climbing consensus |
| Duration | 3-7 days (1 week typical) | General consensus |
| Content | Easy climbing, technique work, mobility, prehab | Hörst, Lattice |
| What to avoid | Max efforts, limit bouldering, PE circuits | General consensus |

**climb-agent current implementation:** Deload at end of each macrocycle + adaptive deload if fatigue proxy exceeds threshold + pre-trip deload. This is well-aligned with the evidence.

### 3.4 Adaptive Deloading (Listen to the Body)

The more sophisticated approach (Israetel, Galpin, Nelson):
- Don't deload on a calendar schedule alone
- Monitor fatigue markers: session RPE trends, performance decline, sleep quality, motivation
- Deload when cumulative fatigue reaches a threshold, not after arbitrary 4 weeks
- "Stressor banking" concept (Galpin): track total stress load, trigger deload at threshold

**climb-agent already does this** with the adaptive deload system (fatigue proxy > threshold → mini-deload). This is more advanced than most coaching apps.

---

## 4. Tapering for Peak Performance

### 4.1 The Science of Tapering

**Mujika & Padilla 2003** (*Med Sci Sports Exerc*) — The gold standard review:
- Performance improvements of **0.5-6%** from proper tapering
- Best achieved by: maintaining intensity, reducing volume 60-90%, reducing frequency ≤20%
- Optimal taper duration: 4-28 days (sport-dependent)
- **Progressive nonlinear tapers > step tapers** (exponential decay of volume)
- Maintaining frequency is critical (Mujika 2012: 30% frequency reduction = no performance change)

### 4.2 Tapering Protocol for Climbing

From Hooper's Beta (2024) and climbing-specific coaching:

**Competition taper (3 weeks):**
1. Week -3: Gentle overreach (slightly increase volume and intensity)
2. Week -2: Reduce volume 25%, maintain intensity >85% max
3. Week -1: Reduce volume 50%, maintain intensity similar to week -2

**Trip taper (1 week):**
- Maintain climbing intensity up to ~85% normal max
- Cut volume by 50%
- Reduce or eliminate supplemental strength training (hangboard, weights)
- Focus on technique and light climbing

**climb-agent already implements pre-trip taper** (volume scales down 4-5 days before outdoor trip). Could benefit from the 3-week competition taper protocol for events.

### 4.3 Supercompensation Model

The theoretical framework:
1. **Training stimulus** → temporary performance decrease (fatigue)
2. **Recovery** → return to baseline
3. **Supercompensation** → performance temporarily exceeds baseline (window of ~48-96h)
4. **Detraining** → if no new stimulus, returns to baseline

**Key principle:** The next training session should ideally coincide with the supercompensation window. Too soon = overtraining; too late = detraining.

**For climbing:** This is why 48h between intense finger sessions is recommended (Topic 02) — it aligns with the PCr resynthesis timeline and supercompensation window for the finger flexor muscles.

---

## 5. Phase Design — Evidence-Based Durations

### 5.1 Current climb-agent Phase Structure

| Phase | Duration | Focus |
|-------|----------|-------|
| Base/Endurance | 3-4 weeks | ARC, technique, general conditioning |
| Strength & Power | 2-3 weeks | Max hangs, limit bouldering, pulling |
| Power Endurance | 2-3 weeks | 4×4, route intervals, repeaters |
| Performance | 1-2 weeks | Project climbing, outdoor, redpoint attempts |
| Deload | 1 week | Recovery, mobility, easy climbing |
| **Total** | **10-13 weeks** | |

### 5.2 Evidence on Phase Duration

| Finding | Source | Implication |
|---------|--------|------------|
| Neural adaptations peak at 2-8 weeks | General S&C | Strength phases of 2-3 weeks are on the short side; 3-4 may be better |
| Hypertrophy requires 4-6 weeks minimum | General S&C | If hypertrophy is a goal, phases need to be longer |
| Tendon adaptation requires months | Nelson, López | No single phase is long enough for tendon change; multi-cycle commitment needed |
| ARC adaptations (capillarization) begin at 3-4 weeks | Hörst, Bechtel | Base phase of 3-4 weeks is minimum for meaningful capillary adaptation |
| Detraining begins after 2-3 weeks without stimulus | General S&C | DUP maintenance doses prevent detraining during focused phases |
| López: 4-week cycles for finger training | López PhD | Aligns with our 2-4 week phases + DUP maintenance |
| Consuegra: ATR blocks of 3-4 weeks each | Consuegra 2023 | Similar to our structure, slightly longer per phase |

### 5.3 What Could Change

**Potential improvements based on evidence:**

1. **Longer Strength phase for beginners** (4 weeks instead of 2-3) — they need more time for neural adaptations to solidify
2. **Overreach week before Performance phase** — planned brief overreach (increased volume/intensity for 1 week) followed by taper, producing supercompensation peak
3. **More flexible phase transitions** — current system uses "readiness to advance" which is good; could add "minimum phase duration" to prevent premature advancement
4. **Multiple macrocycles per year** — the literature and Consuegra (2023) suggest 2-4 macrocycles per year for experienced climbers with seasonal goals

---

## 6. Climbing-Specific Periodization Considerations

### 6.1 The Specificity Problem

Climbing is unique among sports:
- Performance depends on both physical AND technical/mental qualities
- The "terrain" dictates what matters (crimpy vs. sloper, slab vs. roof)
- Indoor and outdoor climbing have different demands
- Grades are subjective and route-specific
- There is NO climbing-specific periodization RCT in the literature

**This means:** All our periodization decisions are extrapolated from general S&C science, modified by climbing-specific coaching wisdom (Hörst, Bechtel, Lattice, López).

### 6.2 Discipline-Specific Periodization

| Aspect | Boulder Focus | Lead Focus |
|--------|-------------|------------|
| Base phase emphasis | Moderate ARC + board climbing | Long ARC + route mileage |
| Strength phase | Longer (3-4 weeks), limit boulder, campus | Standard (2-3 weeks), max hangs |
| PE phase | Shorter (2 weeks), board circuits | Longer (3-4 weeks), route intervals |
| Performance phase | Project sessions, 1-move sequences | Redpoint attempts, full routes |
| Energy system priority | Alactic > Glycolytic > Aerobic | Aerobic > Glycolytic > Alactic |

**climb-agent already handles this** via the goal_type (lead_grade vs boulder_grade) affecting phase weights. Evidence supports this differentiation.

### 6.3 Year-Round vs. Seasonal Planning

**Seasonal climbers** (outdoor performance goal):
- 2-3 macrocycles per year aligned with outdoor seasons
- Taper before each trip/comp
- Off-season = extended base + strength building

**Year-round climbers** (continuous improvement):
- Continuous rolling macrocycles (10-13 weeks)
- Less dramatic peaks, more consistent progress
- Our current model works well for this

### 6.4 Consuegra 2023 — "The Science of Climbing Training"

Key climbing-specific periodization insights:
- A well-designed training plan can improve performance by 1.5-2.3% (Muñoz 2017 reference)
- Recommends ATR (Accumulation-Transmutation-Realization) block model
- ATR allows multiple points of peak form per season
- Each block: 3-4 weeks focused, with maintenance of other qualities
- General preparation precedes specific preparation (Matveyev principle preserved)
- Transition periods (off-season) are essential for long-term health

---

## 7. Reference List

### Meta-Analyses on Periodization
1. Williams TD et al. (2017). "Comparison of Periodized and Non-Periodized Resistance Training on Maximal Strength: A Meta-Analysis." *Sports Med* 47(10):2083-2100.
2. Moesgaard L et al. (2022). "Effects of Periodization on Strength and Muscle Hypertrophy in Volume-Equated Resistance Training Programs: A Systematic Review and Meta-analysis." *Sports Med* 52(7):1647-1666.
3. Grgic J et al. (2017). "Effects of LP and DUP on muscle hypertrophy: a systematic review and meta-analysis." *PeerJ* 5:e3695.
4. Harries SK et al. (2015). "Systematic review and meta-analysis of LP and UP on muscular strength." *J Strength Cond Res*.

### Deload and Tapering Science
5. Mujika I, Padilla S. (2003). "Scientific bases for precompetition tapering strategies." *Med Sci Sports Exerc* 35(7):1182-1187.
6. Mujika I et al. (2012). Effects of frequency reduction on running performance. (Cited in climbing deload article)
7. Hooper's Beta. (2024). "Deload Weeks: Progression Hack or Harmful Crutch?" (Video + article, evidence review)
8. Pyne D, Mujika I, Reilly T. (2009). "Peaking for optimal performance: Research limitations and future directions." *J Sports Sci* 27:195-202.

### Climbing-Specific Periodization
9. Consuegra S. (2023). "The Science of Climbing Training: An evidence-based guide." (Book, excerpted in Climbing Magazine)
10. Hörst E. "Training for Climbing" (3rd ed.) — macrocycle design chapters
11. Bechtel S. "Logical Progression" — DUP for climbing frameworks
12. López E. Blog Guide III: "Program design and Periodization of MaxHangs, IntHangs and SubHangs." (2018)
13. TrainingBeta. "Periodized Training for Climbing: Different Types and Pros & Cons." (2017)

### General Sports Science
14. Issurin VB. (2010). "New horizons for the methodology and physiology of training periodization." *Sports Med* 40(3):189-206. (Block periodization review)
15. Bompa TO, Buzzichelli CA. "Periodization: Theory and Methodology of Training." (6th ed.) — foundational text
16. Stronger by Science. "Periodization: What the Data Say." (2020, comprehensive analysis)

### Cross-references
17. `DESIGN_GOAL_MACROCICLO_v1_1.md` §4 — Current engine implementation
18. `literature_review_climbing_training.md` §5 — Phase weights and model comparison
19. Topic 02 — López 4-week finger training cycles
20. Topic 03 — Energy system mapping to phases

---

## 8. Decision Log — Topic 04

| # | Decision | Rationale | Action | Owner |
|---|----------|-----------|--------|-------|
| D19 | **Simplify to linear for beginners** | Evidence: DUP = LP for untrained (Moesgaard 2022, ES = 0.06). Beginners benefit from simplicity. | Add level-aware macrocycle generation: if level < intermediate, use simplified linear phases | Claude Code |
| D20 | **Add overreach + taper protocol before Performance phase** | Supercompensation science + Hooper's Beta competition taper. Current engine goes straight to Performance. | Brief: 1 week overreach (vol +10-15%) → 1 week taper (vol −50%, maintain intensity) before Performance | Claude Code |
| D21 | **Add minimum phase duration constraint** | Prevent premature phase advancement. Neural adaptations need 2+ weeks minimum. | Engine: readiness_to_advance should not trigger before min_weeks for phase | Claude Code |
| D22 | **Implement 3-week competition taper protocol** | Hooper's Beta: overreach → 25% vol cut → 50% vol cut. Evidence-based, 2-6% performance gain. | Add as "competition_prep" mode alongside existing pre-trip taper | Roadmap (v2) |
| D23 | **Document multi-macrocycle seasonal planning** | Consuegra: 2-4 macrocycles/year for seasonal climbers. Current engine supports 1 cycle at a time. | Future: allow chaining macrocycles with seasonal targets | Roadmap (v2) |

---

## 9. Test & Exercise Watchlist (Topic 04 additions)

| Item | Type | Source | Priority |
|------|------|--------|----------|
| **Overreach week template** | Session planning | Supercompensation science | ⭐⭐⭐ Add to engine |
| **Competition taper protocol (3 weeks)** | Planner mode | Hooper's Beta, Mujika 2003 | ⭐⭐ v2 feature |
| **Fatigue monitoring questionnaire** | Assessment | Israetel, Galpin concepts | ⭐⭐ Could supplement fatigue proxy |
| **Seasonal macrocycle chaining** | Planning feature | Consuegra 2023 | ⭐⭐ v2 feature |

---

*End of Topic 04 — Periodization*
*Next: Topic 05 (Fear, Psychology, Mental Training, Visualization)*
