# Topic 05 — Fear, Psychology, Mental Training, Visualization

> **Project:** climb-agent knowledge base
> **Scope:** Fear of falling, anxiety-performance, route preview, flow state, mental training, visualization
> **Status:** DRAFT v1 — research compilation, pending book integration (Rock Warrior's Way, MacLeod)
> **Date:** 2026-03-16
> **Language:** English
> **Cross-references:** Topic 01 §2.1 (Magiera: mental endurance = #2 performance factor)

---

## Executive Summary

Psychology is the second most important factor in climbing performance (Magiera 2013: canonical weight −0.410, behind only finger strength). Yet it is the least studied and most difficult to train systematically. The first comprehensive systematic review of climbing psychology (Mangan et al. 2024, 83 studies) confirms that flow, confidence, anxiety facilitation, and perception are key performance mediators. Fear of falling directly impairs performance (multiple studies), but psychological training interventions can reduce anxiety and improve climbing ability, particularly in women (Garrido-Palomino 2023). Route previewing is a trainable cognitive-motor skill that reduces stops, improves fluency, and benefits expert climbers most (Sanchez 2012, Seifert 2017, Medernach 2024).

**Key insight for climb-agent:** Psychology is currently a roadmap item (D04, v3). This topic provides the evidence base for when we implement it. The most actionable findings for now are (1) route preview as a teachable tactic and (2) structured self-reflection as a mental skill, both of which the LLM Coach could facilitate.

---

## 1. The Landmark Review — Mangan et al. 2024

- **Citation:** Mangan K, Andrews K, Miles B, Draper N. "The psychology of rock climbing: A systematic review." *Psychol Sport Exerc* 2025;76:102763.
- **Scope:** Scopus, PsycINFO, SPORTDiscus, July 2023. 504 records screened → 83 studies included.
- **Key findings:**
  - Climbers are conscientious, intrinsically motivated, and task-oriented
  - **Flow** is brought on by novel, challenging situations and increases both enjoyment and performance
  - **Confidence and anxiety facilitation** (interpreting anxiety as helpful rather than harmful) are key to performance
  - Elite climbers exhibit lower anxiety than average population
  - **Perception** (route reading, affordance detection) plays a key role
  - Risk-taking is NOT a defining characteristic of climbers (contra popular belief)
  - Climbing as therapy: bouldering + mindfulness reduces depression symptoms (multiple RCTs)

---

## 2. Fear of Falling

### 2.1 The Problem

Fear of falling is the most commonly cited psychological limiter in climbing, especially in lead climbing where falls are longer and more consequential.

**Physiological effects of fear/anxiety (from multiple studies):**
- Increased heart rate and cortisol → reduced fine motor control
- Narrowed visual attention (Nieuwenhuys et al. 2008) → miss holds, make poor decisions
- Increased muscle tension → higher energy expenditure, earlier pump
- "Freezing" behavior → extended time on holds, wasting energy
- Self-fulfilling prophecy: fear → tension → poor movement → failure → more fear

**Advanced vs. beginner differences** (Psychophysiological Response study, 2025):
- Advanced climbers: lower anxiety, better sympathetic modulation (HRV), higher grip strength
- Beginners: higher anxiety, lower HRV, reduced RFD
- Experience develops cognitive appraisal (perceiving challenge as less threatening)

### 2.2 Gender Differences

- Fear of falling impacts women climbers disproportionately (Sendín-Pérez & Pans 2025, SR of 15 studies)
- Anxiety caused by fear of falling directly influences performance in women
- **Garrido-Palomino & España-Romero 2023** (RCT-like intervention):
  - Psychological training based on emotional regulation improved climbing ability in women with fear of falling
  - Reduced both cognitive and somatic anxiety
  - Increased self-confidence and interoceptive awareness
  - Physical training alone only reduced cognitive anxiety (not somatic)
  - **Implication:** Psychological intervention adds value BEYOND just more climbing practice

### 2.3 Managing Fear — Evidence-Based Strategies

From the literature and coaching sources:

| Strategy | Evidence | Mechanism |
|----------|----------|-----------|
| **Gradual exposure (stress inoculation)** | Deliberate practice theory (Ericsson) | Progressive challenge builds tolerance |
| **Emotional regulation training** | Garrido-Palomino 2023 (RCT) | Cognitive reappraisal reduces somatic anxiety |
| **Interoceptive awareness** | Garrido-Palomino 2023 | Noticing body signals without over-reacting |
| **Fall practice (controlled)** | Coaching consensus (Hörst, Ilgner) | Desensitization through repeated safe falls |
| **Confidence building via mastery** | Self-efficacy theory (Bandura) | Success breeds confidence; onsighting at comfortable grades |
| **Breathing techniques** | General sport psychology | Reduces sympathetic activation, lowers HR |
| **Positive self-talk** | Hörst self-assessment protocol | Replaces catastrophic thoughts with task-focused cues |

---

## 3. Route Previewing — The Trainable Cognitive Skill

### 3.1 Why Route Preview Matters

Route previewing is the pre-ascent visual inspection of a climbing route. Research consistently shows it is a critical determinant of on-sight performance.

**Sanchez et al. 2012** (*Scand J Med Sci Sports*):
- 29 male climbers (intermediate to expert)
- Route preview doesn't help with completion (whether you top out) but helps with FORM (fewer stops, shorter stops)
- Expert climbers benefit most from preview
- "Route preview errors are a major reason for falling"

**Seifert et al. 2017** (*PLoS ONE*):
- 8 inexperienced + 10 experienced climbers
- Tested 4 previewing strategies: chunking, zigzag, bottom-to-top, fragmentary
- Route preview reduces anxiety, helps detect affordances, helps chain movements
- Shorter preview time correlated with greater climbing fluency (experts are faster AND more effective at previewing)

### 3.2 Expert vs. Novice Preview Behavior

**Medernach et al. 2024** (*Psychol Sport Exerc*) — Cognitive-behavioral processes in bouldering preview:
- Elite climbers: shorter preview durations, fewer scans, more "superficial scanning" strategy
- Advanced/intermediate: longer previews, more detailed scanning
- Experts have superior task-specific cognitive proficiency: faster pickup of perceptual cues, more efficient visual search, better pattern recognition
- Movement repertoire accounts for expertise differences in previewing

**Embodied planning research (2024):**
- Holds looked at during preview are used 2× more often during climbing than those not looked at
- Fixation duration is longer for holds that are subsequently used
- Experience correlates with faster climbing AND shorter fixations on unused holds

### 3.3 Two Functions of Route Preview

From Sanchez et al. 2019 (*Frontiers in Psychology*):
1. **Ascent strategy forecasting:** Planning the progression (which holds, which sequence, where to clip, where to rest)
2. **Ascent effort forecasting:** Estimating where the crux is, pacing energy expenditure, managing rest points

Both functions are trainable. Expert climbers confer "central value" to route previewing.

### 3.4 Practical Implications

Route preview is one of the most actionable psychological skills for climb-agent:
- Can be prompted before each climbing session ("Did you preview your routes?")
- LLM Coach could teach previewing strategies (chunking, bottom-up, identify rests first)
- Could be tracked as a technique/tactical metric in self-assessment

---

## 4. Flow State in Climbing

### 4.1 What Flow Is

Flow (Csikszentmihalyi) = the state of complete immersion and optimal performance where challenge matches skill.

**From Mangan et al. 2024:**
- Flow is brought on by novel, challenging climbing situations
- Increases both enjoyment and performance
- Associated with: clear goals, immediate feedback, challenge-skill balance, deep concentration, sense of control

### 4.2 Flow in Climbing Context

Climbing is one of the sports most associated with flow states because:
- Immediate consequences (fall = instant feedback)
- Progressive challenge (grade system)
- Full-body engagement (physical + mental + technical)
- Environmental novelty (every route is different)

**Risk and flow (Schüler & Nakamura 2013):**
- Flow can lead to risk-taking behavior in some individuals
- Important to distinguish flow (optimal performance state) from recklessness

### 4.3 Implications for Training

- Train at the challenge-skill boundary: problems that are hard but achievable (flash to 2-session project range)
- Novel stimuli promote flow: vary climbing venues, styles, wall angles
- Minimize distractions during climbing sessions
- The LLM Coach could help identify the "flow zone" grade range for each climber

---

## 5. Climbing as Mental Health Intervention

### 5.1 Bouldering Psychotherapy

**Systematic review (2025, PMC):** 7 studies, 471 participants:
- Indoor bouldering + mindfulness ("Bouldering Psychotherapy") significantly reduces depression symptoms
- Effect: moderate → mild depression (−8.3 points on MADRS, exceeds MCID of 5 points)
- Longer interventions (8-10 weeks) needed for effects to persist at 6-12 months
- No adverse events reported

**Implication for climb-agent:** We are not a mental health app, but we should acknowledge that climbing itself has therapeutic benefits. The Coach could reference this when discussing motivation or the broader value of consistent training.

---

## 6. Key Psychological Models Relevant to Climbing

| Model | Application | Source |
|-------|-----------|--------|
| **Flow Theory** (Csikszentmihalyi) | Optimal performance at challenge-skill balance | Mangan 2024 |
| **Stress Inoculation Theory** | Gradual exposure builds anxiety tolerance | Deliberate practice research |
| **Cognitive Appraisal Theory** | Experienced climbers perceive challenge as less threatening | Psychophysiological Response 2025 |
| **Self-Efficacy Theory** (Bandura) | Success → confidence → better performance → more success | Llewellyn et al. 2008 |
| **Inverted-U (Yerkes-Dodson)** | Moderate arousal = optimal performance; too much or too little = impairment | General sport psychology |
| **Attentional Control Theory** | Anxiety narrows visual attention and impairs decision-making | Nieuwenhuys et al. 2008 |

---

## 7. Implications for climb-agent

### 7.1 Current Status

Psychology is NOT an assessment axis (D04: deferred to v3/LLM Coach). This is correct given the difficulty of objective measurement. However, several psychological skills are actionable NOW:

### 7.2 What We Can Do Now (v1)

| Action | How | Effort |
|--------|-----|--------|
| **Route preview prompt** | Guided session mode: "Preview your route for 2 minutes before climbing" | Low — text cue |
| **Post-climb reflection prompt** | "Was that a physical failure or a mental quit?" (Hörst) | Low — feedback question |
| **Fall practice sessions** | Include in catalog as a technique/mental drill | Medium — new exercise type |
| **Self-talk cues** | Tips in rest phases: "Focus on the next move, not the last one" | Low — text cue |

### 7.3 What the LLM Coach Could Do (v3)

| Feature | Mechanism | Evidence |
|---------|-----------|----------|
| **Fear of falling assessment** | Structured questions about falling comfort, lead anxiety, style preference | Garrido-Palomino 2023 |
| **Route preview coaching** | Teach chunking, bottom-up scanning, rest identification strategies | Sanchez 2012, Seifert 2017 |
| **Emotional regulation techniques** | Breathing exercises, cognitive reappraisal prompts | Garrido-Palomino 2023 |
| **Motivation tracking** | Monitor training consistency, flag motivation dips, suggest deload | General coaching |
| **Flow zone identification** | Recommend grade ranges for "challenge-skill balance" based on current level | Flow theory |
| **Mental strength profiling** | Track self-reported fear, confidence, focus over time | Longitudinal self-report |

---

## 8. Reference List

### Systematic Reviews
1. Mangan K, Andrews K, Miles B, Draper N. (2024/2025). "The psychology of rock climbing: A systematic review." *Psychol Sport Exerc* 76:102763.
2. Sendín-Pérez M, Pans M. (2025). "Impact of fear of falling on sport performance of female climbers: A systematic review." *Ágora para la EF y el Deporte* 27:219-246.
3. SR on bouldering as depression treatment (2025). PMC. 7 studies, 471 participants.

### Fear and Anxiety
4. Garrido-Palomino I, España-Romero V. (2023). "Fear of falling in women: A psychological training intervention improves climbing performance." *J Sports Sci* 41:1518-1529.
5. Nieuwenhuys A et al. (2008). "The influence of anxiety on visual attention in climbing." *J Sport Exerc Psychol* 30:171-185.
6. Aras D, Akalan C. (2014). "The effect of anxiety about falling on physiological parameters with different rope protocols." *J Sports Med Phys Fitness* 54(1):1-8.
7. Llewellyn DJ et al. (2008). "Self-efficacy, risk taking and performance in rock climbing." *Personality and Individual Differences* 45(1):75-81.
8. Psychophysiological Response Differences study (2025). Advanced vs. beginner HRV, anxiety, grip strength.

### Route Preview and Cognition
9. Sanchez X et al. (2012). "Efficacy of pre-ascent climbing route visual inspection." *Scand J Med Sci Sports* 22:67-72.
10. Seifert L et al. (2017). "Role of route previewing strategies on climbing fluency and exploratory movements." *PLoS ONE* 12:e0176306.
11. Sanchez X et al. (2019). "Identification of Parameters That Predict Sport Climbing Performance." *Front Psychol* 10:1294.
12. Medernach JP et al. (2024). "Cognitive-behavioural processes during route previewing in bouldering." *Psychol Sport Exerc* 73:102654.
13. Vasile AI et al. (2022). "Cognitive factors that predict on-sight and red-point performance at youth level." *Front Psychol* 13:1012792.
14. Pezzulo G et al. (2010). "When affordances climb into your mind." *Brain Cogn* 73:68-73.
15. Embodied planning study (2024). *Front Psychol*. Eye-tracking + climbing performance.

### Flow and Motivation
16. Schüler J, Nakamura J. (2013). "Does flow experience lead to risk?" *Applied Psychology: Health and Well-Being* 5(3):311-331.

### Mental Health
17. Karg N et al. (2020). "Bouldering psychotherapy is more effective in treatment of depression than physical exercise alone." *BMC Psychiatry* 20(1):116.

### Books (Pending Integration)
18. Ilgner A. "The Rock Warrior's Way" — fear management, mental training framework
19. MacLeod D. "9 Out of 10 Climbers" — mental chapters on self-analysis, identifying weaknesses
20. Hörst E. "Training for Climbing" — mental training, visualization, self-assessment chapters

### Cross-references
21. Topic 01 §2.1 — Magiera 2013: mental endurance = #2 factor (canonical weight −0.410)
22. Topic 01 §3.2 — Hörst 4-domain self-assessment (mental as one of 4 domains)

---

## 9. Decision Log — Topic 05

| # | Decision | Rationale | Action | Owner |
|---|----------|-----------|--------|-------|
| D28 | **Add route preview prompt to guided session mode** | Sanchez 2012, Seifert 2017: preview reduces stops, improves fluency. Zero-cost intervention. | Add text cue before main climbing block: "Preview your route for 2 min" | Claude Code |
| D29 | **Add post-climb reflection question to feedback** | Hörst self-assessment: "Was this a physical or mental failure?" Tracks psychology implicitly. | Add optional question in session feedback flow | Claude Code |
| D30 | **Add fall practice drill to exercise catalog** | Coaching consensus for fear management. Progressive: top-rope falls → lead falls → higher falls. | Create exercise with progression levels | Claude Code |
| D31 | **Route preview coaching for LLM Coach (v3)** | Medernach 2024: previewing strategies are expert-level skills, teachable. | Design coach conversation flow for teaching preview | Roadmap v3 |
| D32 | **Fear of falling self-assessment for LLM Coach (v3)** | Garrido-Palomino 2023: structured assessment enables targeted intervention. | Design questionnaire for psychological profiling | Roadmap v3 |

---

## 10. Test & Exercise Watchlist (Topic 05 additions)

| Item | Type | Source | Priority |
|------|------|--------|----------|
| **Fall practice drill (progressive)** | Exercise | Coaching consensus | ⭐⭐⭐ Add to catalog |
| **Route preview prompt** | Session cue | Sanchez 2012, Seifert 2017 | ⭐⭐⭐ Add to guided mode |
| **Post-climb mental reflection** | Feedback question | Hörst self-assessment | ⭐⭐⭐ Add to feedback flow |
| **Breathing exercise (pre-climb)** | Exercise/cue | General sport psychology | ⭐⭐ Add as warmup cue |
| **Visualization exercise** | Mental drill | Hardy & Callow 1999 | ⭐ LLM Coach v3 |

---

*End of Topic 05 — Fear, Psychology, Mental Training, Visualization*
*Pending: Book integration (Rock Warrior's Way, MacLeod mental chapters)*
*Next chat: Topics 06-10*
