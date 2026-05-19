# Topic 06 — Nutrition, Recovery, Sleep, Supplements

> **Project:** climb-agent knowledge base
> **Scope:** What nutritional, recovery, and sleep factors affect climbing performance? What should the engine educate about vs. prescribe?
> **Status:** DRAFT v1
> **Date:** 2026-03-16
> **Language:** English (knowledge base standard)

---

## ⚠️ DISCLAIMER

**climb-agent is NOT a nutrition or medical advisor.** This topic provides educational context only. The engine must:
- Never prescribe specific diets, caloric targets, or weight loss plans
- Never comment on a user's body weight or body fat percentage
- Always recommend consulting a registered sports dietitian for personalised nutrition advice
- Flag signs of RED-S or disordered eating if detected in user patterns (e.g., chronic fatigue, declining performance despite increased training)
- Use a "food first" approach for all supplement discussion (Close et al., 2022)

---

## Executive Summary

Climbing-specific nutrition research is still in its infancy compared to other sports. Key findings: climbers frequently under-eat (low energy availability), disordered eating is a documented risk in climbing culture, and climbing-specific supplement evidence is limited. For the engine, the role of this topic is primarily **educational** — providing context and guardrails rather than prescriptive plans. The three most impactful factors for climbing recovery are: (1) adequate energy availability, (2) sleep quality/duration, and (3) protein timing around training. Supplement evidence is strongest for vitamin C + hydrolysed collagen for tendon health, and weakest for most other commonly used supplements.

---

## 1. Energy Availability and Climbing

### 1.1 The Problem: Low Energy Availability in Climbers

Regulska-Ilow et al. (2023) studied 106 sport climbers and found low energy availability (EA) across both genders and all levels, with significant differences between male climbing levels (p < 0.001). The drive for low body weight — reinforced by climbing culture's emphasis on strength-to-weight ratio — puts climbers at particular risk.

Gibson-Smith et al. (2024, Frontiers in Nutrition) assessed 50 senior competition climbers (26M, 24F) and found mean nutrition knowledge scored only "average" (53.5 ± 11.1%), with considerable individual variation. Intentional weight loss for competition was common, with most athletes losing approximately 3-8% bodyweight over 2+ weeks.

### 1.2 RED-S (Relative Energy Deficiency in Sport)

RED-S is a syndrome caused by insufficient energy intake relative to exercise energy expenditure. It affects both males and females and can cause: impaired metabolic rate, hormonal dysfunction (amenorrhoea in women, low testosterone in men), decreased bone mineral density, weakened immune system, increased injury susceptibility, and impaired psychological function.

**Climbing-specific data:**
- Joubert et al. (2020): assessed 498 international sport lead climbers. Disordered eating prevalence was significant, with the "lighter the better" mentality identified as a cultural risk factor.
- Joubert et al. (2022): 15.8% of 114 elite female competition climbers presented with current amenorrhoea (past 12 months), even with relatively normal BMIs. Some currently struggled with one or more eating disorders.
- The IFSC now uses BMI critical margins to screen competitors, but Joubert et al. argue more medical supervision is needed.
- CLIMB study protocol (2023): 2-year longitudinal Swedish study on disordered eating, mental health, overuse injuries, body image, RED-S indicators, compulsive training, perfectionism, sleep quality, and bone density in competitive climbers.

### 1.3 Body Composition Reference Data

From Consuegra Ch.8 (Couceiro, 2010 PhD — already in our synthesis):

| Group | Weight | Body fat % |
|-------|--------|-----------|
| Elite male | 65.8 ± 7.5 kg | 8.8 ± 2.6% |
| Advanced male | 67.2 ± 5.5 kg | 9.9 ± 4% |
| Female (all levels combined) | 51.6 ± 4.5 kg | 19.26 ± 3.5% |

Ginszt et al. (2023, J Strength Cond Res, systematic review): body composition parameters are more critical than anthropometric parameters for climbing performance. Low body fat (<10% in males) with higher lean muscle mass allows better ergonomic movement and less strain. Higher bone density observed in upper limbs of climbers vs non-climbers.

**Engine approach:** Body weight is used ONLY as an input for ratio calculations (finger strength %BW, pull-up %BW). The engine never comments on weight, body fat, or suggests weight loss. This aligns with D01 (remove body_composition axis).

---

## 2. Macronutrient Guidelines for Climbers

### 2.1 General Recommendations

Smith et al. (2017) and Ranchordas et al. (2019, Cogent Medicine) provide the most comprehensive climbing-specific nutrition review:

- **Energy expenditure:** approximately 10-11 kcal/min while climbing
- **Carbohydrates:** 3-7 g/kg BM/day (varies by training volume and phase)
- **Protein:** 1.4-2.0 g/kg BM/day for athletes (ISSN position stand); timing around training sessions matters for recovery
- **Fat:** adequate to support hormonal function; no specific climbing recommendations, general athlete guidelines of 20-35% of energy intake
- **Hydration:** approximately 250 mL/hr of water or sports drink while climbing; individualise based on sweat rate and environment

### 2.2 Periodised Nutrition

Stellingwerff et al. (2019, Int J Sport Nutr Exerc Metab) propose a framework for periodised nutrition aligned to training phases:
- Higher carbohydrate intake during high-volume/endurance training phases (Base/ARC)
- Higher protein intake during strength-focused phases (Build)
- Competition day nutrition planning: glycogen loading, pre-climb meals, between-attempt fuelling

### 2.3 Climbing-Specific Considerations

- Competition format requires climbing multiple routes in quick succession — demands rapid glycogen replenishment between attempts
- Outdoor climbing (multi-pitch, all-day cragging) requires portable nutrition planning
- Consuegra Ch.8 insight: cardio is hugely inefficient for fat loss (max ~111g/hour at extreme intensity). Better approach for body composition is insulin management through macronutrient balance.

---

## 3. Sleep and Recovery

### 3.1 Sleep and Athletic Performance

Charest and Grandner (2020, Sleep Med Clin): comprehensive review of sleep's role in athletic performance. Key findings:

- **Growth hormone:** surge during deep sleep (N3 stage) — critical for tissue repair, protein synthesis, muscle growth. Single night without sleep can reduce testosterone by ~25%.
- **Chronic sleep deficiency:** elevated cortisol → increased protein breakdown, limited recovery capacity
- **Cognitive effects:** impaired decision-making, motor coordination, reaction time — all critical for climbing (route reading, move execution, risk assessment)
- **Injury risk:** poor sleep is a predictor for injuries. Adolescent athletes sleeping <8 hours had significantly increased injury rates.
- **Minimum recommendation:** at least 7 hours for adults (IOC consensus); 8-10 hours for adolescent athletes

### 3.2 Sleep Interventions for Athletes

Cunha et al. (2023, Sports Med Open, systematic review): analysed sleep interventions in athletes. Key findings:
- Sleep extension and naps were the most effective strategies to improve sleep and subsequent performance
- Sleep hygiene education alone had limited effects
- Mindfulness and light manipulation showed promising results but need more research
- Cold water immersion showed no effects on sleep

### 3.3 Recovery Modalities

**Between sessions (from Consuegra Ch.8, already documented):**
- PCr recovery: 84% at 2 min, 89% at 4 min, 97% at 8 min (Billat, 2002)
- CNS fatigue: 24-48h rest after max strength training (Zatsiorsky, 1995)
- Deadhang frequency: max 2×/week, 48-72h between sessions (López-Rivera, 2018c)

**Active recovery:**
- Easy traversing > walking > sitting for between-attempt recovery (Valenzuela et al., 2015)
- Shaking out on rests: no bearing on recovery with full vascular occlusion (Green and Stannard, 2010)

**Sleep-nutrition interaction:**
Driller et al. (2023, Current Sleep Med Reports): chrononutrition (relationship between food intake and circadian clock) is an emerging area. Training adaptations can be maximised by optimal nutrition both pre- and post-exercise, and nutrition also affects sleep quality.

---

## 4. Supplements — Evidence Review

### 4.1 Evidence Framework

Following the IOC consensus (Maughan et al., 2018) and the "food first but not always food only" approach (Close et al., 2022), supplements are classified by evidence level. Climbing-specific supplement research is extremely limited — most evidence is extrapolated from general sports science.

### 4.2 Strongest Evidence — Vitamin C + Hydrolysed Collagen for Tendon Health

**Shaw et al. (2017, Am J Clin Nutr):** 15g vitamin C-enriched gelatin consumed 60 min before exercise increased collagen synthesis markers (mean +20% in procollagen). However: small sample (n=8), significant individual variability, placebo was sugar (not protein).

**Lattice Training review (2023):** summarises the evidence as:
1. Reasonable evidence that hydrolysed collagen can improve connective tissue healing, joint pain, and functionality
2. Exercise + vitamin C aids collagen synthesis; 15g/day more effective than 5g/day
3. Consume ~60 min before exercise to maximise collagen synthesis

**Hooper's Beta critical review (2022):** notes that collagen companies over-cite the Shaw et al. study while ignoring a reanalysis of the same data that reached more cautious conclusions. The evidence is promising but not definitive, especially from in vivo human studies on tendons specifically.

**Vitamin C scoping review (2022, Nutrients):** vitamin C supplementation is potentially useful for tendinopathy recovery. Combined products (mucopolysaccharides + type I collagen + vitamin C) showed 69% pain reduction in Achilles tendinopathy, 83% in tennis elbow, 75% in supraspinatus tendinopathy — associated with structural improvements.

**Engine approach:** can mention collagen + vitamin C as the supplement with the most climbing-relevant evidence, with appropriate caveats. Recommended protocol from literature: 10-15g hydrolysed collagen + vitamin C, 30-60 min before targeted loading exercise.

### 4.3 Moderate Evidence — Beta-Alanine, Caffeine

**Beta-alanine (ISSN position stand, 2015):**
- 4-6g/day for 2-4+ weeks significantly augments muscle carnosine (intracellular pH buffer)
- Most effective for exercise lasting 1-4 minutes (climbing-relevant for boulder problems and crux sequences)
- Could theoretically help delay forearm pump by buffering H+ accumulation
- Side effect: paraesthesia (tingling), mitigated by divided doses (1.6g) or sustained-release formulas
- Climbing-specific evidence: none. Theoretical relevance based on mechanism.

**Caffeine:**
- Well-established ergogenic aid across many sports
- Improves alertness, reaction time, power output
- Climbing-relevant: could aid focus and power on hard attempts
- Climbing-specific evidence: limited

### 4.4 Weak/Conflicting Evidence — Creatine for Climbing

**Creatine:** the most researched sports supplement. Proven benefits for strength, power, and high-intensity performance. However, for climbing:
- Primary concern: fluid retention and weight gain (1-3 kg typical in loading phase) may negate performance benefits by worsening strength-to-weight ratio
- Theoretical benefit: could support PCr replenishment between crux attempts
- Climbing-specific research: essentially none
- Current consensus: some climbers may benefit, but weight gain side effect is a significant concern in a sport where strength-to-weight ratio is paramount

### 4.5 Commonly Used But Low Evidence

Regulska-Ilow et al. (2023) found the most common supplements among climbers were: isolated protein, vitamin C, vitamin D, magnesium, and amino acid blends (BCAAs/EAAs). Climbers rarely used supplements with stronger evidence for climbing performance (beta-alanine, nitrates, sodium bicarbonate).

**BCAAs:** largely considered unnecessary if total protein intake is adequate. ISSN position: whole protein sources are preferable.

**Vitamin D and Magnesium:** important for general health, bone density, and muscle function, but supplementation only beneficial if deficient. Common deficiencies in athletes warrant testing before supplementing.

---

## 5. Implications for climb-agent

| Finding | Impact | Priority |
|---------|--------|----------|
| RED-S risk documented in climbing population (Joubert 2020, 2022) | Engine must NEVER encourage weight loss, calorie restriction, or comment on body composition | v1, CRITICAL |
| Low EA common across all climbing levels (Regulska-Ilow 2023) | Educational content: fuel training adequately, especially during high-volume phases | v1 |
| Sleep: minimum 7h adults, 8-10h adolescents; GH surge during deep sleep | Recovery tips in session feedback: prioritise sleep as #1 recovery tool | v1 |
| PCr recovery timelines + CNS fatigue rules | Already captured in Consuegra Ch.8 decisions (D12 recovery, hangboard frequency) | v1, done |
| Collagen + vitamin C: most climbing-relevant supplement evidence | Can mention in educational content with appropriate caveats; "food first" approach | v1, educational |
| Beta-alanine: theoretical relevance for pump buffering, no climbing-specific evidence | Mention only if user asks about supplements; do not proactively recommend | v2 |
| Creatine: weight gain concern outweighs potential benefits for most climbers | If asked: explain trade-off honestly, recommend consulting sports dietitian | Educational |
| Periodised nutrition aligns to training phases | Engine could suggest general nutrition focus per phase (more carbs in Base, more protein in Build) | v2 |
| Cardio inefficient for fat loss (Consuegra Ch.8) | Engine should not recommend cardio for weight management | v1 |

### New Decisions

| # | Decision | Rationale | Action |
|---|----------|-----------|--------|
| D64 | **Add RED-S awareness guardrails** | Joubert (2020, 2022): 15.8% amenorrhoea in elite female climbers, widespread disordered eating culture. Engine must never encourage weight manipulation. | Hard safety rule: no weight loss advice, no body fat commentary, flag fatigue+performance decline patterns |
| D65 | **Include sleep education in recovery guidance** | IOC consensus + Charest & Grandner (2020): sleep is the #1 recovery tool. Minimum 7h adults, 8-10h adolescents. GH/testosterone suppression with sleep deprivation. | Add sleep tips to post-session and rest day guidance |
| D66 | **Add "fuel your training" educational messaging** | Low EA documented across climbing levels. Educational approach: more volume = more fuel needed. Phase-aligned general guidance (not caloric targets). | Educational content in onboarding and phase transitions |
| D67 | **Add collagen + vitamin C as evidence-based supplement mention (educational only)** | Shaw et al. (2017), Lattice review (2023), vitamin C scoping review (2022): best climbing-relevant supplement evidence for tendon health. | Educational mention with caveats; 10-15g collagen + vitamin C, 30-60 min before loading. Not a prescription. |

---

## 6. Watchlist

| Item | Source | Status |
|------|--------|--------|
| CLIMB longitudinal study (Sweden, 2-year) | Protocol published 2023, results pending | Monitor for 2025-2026 publications |
| Climbing-specific beta-alanine RCT | No studies exist yet | Would be first direct evidence |
| RED-S screening tools validated for climbing | Only general athlete tools available | Monitor for climbing-specific validation |
| Periodised nutrition for climbing guide | No comprehensive climbing-specific guide exists | MacLeod (MSc nutrition) may cover in "9 Out of 10" |

---

## 7. References

1. Regulska-Ilow B et al. (2023). "Energy availability and dietary nutrient intake of sport climbers at different climbing levels." *Int J Environ Res Public Health* 20(6):5176.
2. Gibson-Smith E et al. (2024). "Nutrition knowledge, weight loss practices, and supplement use in senior competition climbers." *Front Nutr* 10:1277623.
3. Joubert LM et al. (2020). "Prevalence of disordered eating among international sport lead rock climbers." *J Sport Health Sci*.
4. Joubert LM et al. (2022). "Prevalence of amenorrhea in elite female competitive climbers." *Front Sports Act Living*.
5. Ginszt M et al. (2023). "Body composition, anthropometric parameters, and strength-endurance characteristics of sport climbers: a systematic review." *J Strength Cond Res* 37(6):1339-1348.
6. Ranchordas MK et al. (2019). "Physiological demands and nutritional considerations for Olympic-style competitive rock climbing." *Cogent Medicine* 6(1):1667199.
7. Charest J, Grandner MA (2020). "Sleep and athletic performance." *Sleep Med Clin* 15(1):41-57.
8. Cunha LA et al. (2023). "The impact of sleep interventions on athletic performance: a systematic review." *Sports Med Open* 9:58.
9. Shaw G et al. (2017). "Vitamin C-enriched gelatin supplementation before intermittent activity augments collagen synthesis." *Am J Clin Nutr* 105(1):136-143.
10. Lattice Training (2023). "Collagen supplements — what does the research say?" Blog review.
11. Hooper's Beta (2022). "Should climbers take collagen supplements?" Research review.
12. Nutrients (2022). "Effect of vitamin C on tendinopathy recovery: a scoping review." *Nutrients* 14(13):2663.
13. Maughan RJ et al. (2018). "IOC consensus statement: dietary supplements and the high-performance athlete." *Br J Sports Med*.
14. Close GL et al. (2022). "Food first but not always food only: recommendations for using dietary supplements in sport." *Int J Sport Nutr Exerc Metab*.
15. Stellingwerff T et al. (2019). "A framework for periodized nutrition for athletics." *Int J Sport Nutr Exerc Metab* 29:141-151.
16. ISSN (2015). "International society of sports nutrition position stand: Beta-Alanine." *J Int Soc Sports Nutr*.
17. CLIMB study protocol (2023). "Protocol for a 2-year longitudinal study of eating disturbances, mental health problems and overuse injuries in rock climbers." *BMJ Open Sport Exerc Med*.
18. Couceiro P (2010). PhD thesis on body composition in climbers (cited in Consuegra 2023).
19. DePhillipo NN et al. (2018). "Efficacy of vitamin C supplementation on collagen synthesis and oxidative stress after musculoskeletal injuries: a systematic review." *Orthop J Sports Med*.

---

*End of Topic 06 — 4 new decisions (D64-D67), 19 references*
