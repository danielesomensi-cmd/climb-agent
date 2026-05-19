# Topic 08 — Technique, Movement, Route Reading

> **Project:** climb-agent knowledge base
> **Scope:** How to measure, train, and improve climbing technique and movement quality
> **Status:** DRAFT v1
> **Date:** 2026-03-16
> **Language:** English (knowledge base standard)
> **Cross-references:** Consuegra Ch.7 (efficiency data), Ch.8 (drill catalog, warm-up drills), Topic 05 (route preview)

---

## Executive Summary

Technique is the great equaliser in climbing — elite climbers use as little as 1/5 (20%) of the energy of novices on the same circuit (Baláš 2014b, in Consuegra Ch.7). Movement quality is measurable through metrics like the jerk coefficient (Seifert et al., 2014), geometric index of entropy, and immobility-to-mobility ratio. For the engine, technique is primarily trained through deliberate practice drills (not strength exercises) and assessed through proxy measures (onsight/redpoint gap, self-report, board grade vs. finger strength comparison). The drill catalog — combining Consuegra's wall-based exercises, Bechtel's drills, and coaching community best practices — is the most actionable output for the engine.

---

## 1. The Science of Climbing Movement

### 1.1 Efficiency as the Core Metric

From Consuegra Ch.7 (already in synthesis):
- Elite climbers use up to 20% of the energy of novices on the same circuit (Baláš 2014b)
- More weight through feet = 11% less energy expenditure, 14% lower heart rate (Baláš 2014a)
- Elite climbers produce more ATP via alactic + aerobic pathways, avoiding glycolytic pathway → lower lactate (Saul 2019)
- Efficiency comes from: technique, visualisation, footwork, motor skills, psychology, experience

**Key insight (Consuegra Ch.7, Bertuzzi 2007):** movement economy is more important than a good metabolism. A climber with poor technique will never compensate with fitness alone.

### 1.2 Seifert Jerk Metric — Quantifying Movement Fluency

**Citation:** Seifert L et al. (2014). "Climbing skill and complexity of climbing wall design: assessment of jerk as a novel indicator of performance fluency." *J Applied Biomechanics* 30(5):619-625.

**What it measures:** jerk is the third time derivative of position (rate of change of acceleration). A normalized jerk coefficient computed from hip trajectory and orientation data captures both spatial and temporal aspects of movement fluency — how smoothly a climber moves through a route.

**Key findings:**
- High correlation (r = .99) between jerk coefficient of hip trajectory and hip orientation
- More complex routes produced higher jerk (less fluent movement)
- Jerk decreased with practice (climbers got smoother with repetition)
- Jerk coefficient captures what geometric entropy misses: temporal aspects (pauses, speed variations, hesitations)

**Measurement:** requires IMU (inertial measurement unit) attached to hips. Currently a research tool, not practical for consumer apps. However, the concept is valuable for coaching: fluent, smooth movement = better technique.

**Orth et al. (2017) extension:** analysed relations between spatiotemporal movement regulation and discrete action performance in skilled climbing. Jerk provides the most straightforward indication of capacity to co-adapt to spatial-temporal demands.

### 1.3 Other Movement Quality Metrics (Research Context)

| Metric | What it measures | Source | Practicality |
|--------|-----------------|--------|-------------|
| Geometric Index of Entropy (GIE) | Spatial efficiency of climbing trajectory vs. convex hull | Cordier et al. (1993) | Research only |
| Immobility-to-Mobility Ratio (IMR) | Time spent still vs. moving (resting, reading, hesitating) | Orth et al. (2017) | Research only |
| Jerk coefficient | Smoothness of hip trajectory (spatial + temporal) | Seifert et al. (2014) | Research only (IMU needed) |
| Contact time per hold | Time spent touching each hold — fluency indicator | Seifert et al. (2020) | Requires instrumented holds |

**For the engine:** none of these are currently practical for a consumer app. The proxy measures we already use (onsight/redpoint gap, self-assessment, board grade vs finger strength) remain the best available for v1. Topic 01 roadmap item R-03 covers future technique assessment improvements.

---

## 2. Route Reading and Preview

### 2.1 Already Covered (Topic 05)

- Sanchez et al. (2012): route preview strategy differs between experts and novices
- Seifert et al. (2017): role of route previewing strategies on climbing fluency and exploratory movements — better preview leads to lower jerk (smoother climbing)
- Medernach et al. (2024): structured route preview improves performance
- D28: Route preview prompt in guided session mode
- D31: Route preview coaching (v3, LLM Coach)

### 2.2 Seifert et al. (2017) — Preview Strategy and Fluency Link

**Citation:** Seifert L et al. (2017). "Role of route previewing strategies on climbing fluency and exploratory movements." *PLOS ONE* 12(4):e0176306.

Used eye tracking + IMUs simultaneously. Found that the quality and duration of route preview directly affected climbing fluency (lower jerk coefficient) and the ratio of exploratory to performatory movements. Climbers who previewed more thoroughly made fewer exploratory movements during the climb and moved more smoothly.

**Engine implication:** the route preview prompt (D28) has a measurable effect on climbing quality. The engine should not just suggest previewing but provide structure (look for rest positions, identify crux sequences, plan clipping positions).

---

## 3. Technique Drill Catalog

### 3.1 Drill Categories and Sources

| Category | Drills | Primary Source |
|----------|--------|---------------|
| Footwork precision | Silent feet, sticky feet, target practice, eyes-on-feet | Coaching consensus (Hörst, Anderson, Claassen) |
| Weight transfer | No-hands slab climbing, foot-only traversing | Coaching community |
| Body position | Twist-lock drill, hip rotation practice, flagging practice | Hörst, coaching community |
| Downclimbing | Full downclimb of warm-up routes/boulders | Coaching consensus |
| Core-on-wall | Tic Tac Toe, Diagonal, Get'em!, Freeze, Feet Forwards, Hang Around | Matros et al. (2013) via Consuegra Ch.8 |
| Movement economy | Tennis ball hands (slab with tennis balls in hands) | Anderson & Anderson |
| Route reading | Timed preview + predict crux, post-climb analysis | Medernach (2024), Sanchez (2012) |

### 3.2 Key Drills Described

**Silent feet / Quiet feet:**
Climb at 2-3 grades below onsight level. Place every foot so silently that no sound is audible. If your foot makes noise, return it and retry the placement. Focus on precision, not speed. Develops awareness, control, and proprioception. Can be incorporated into every warm-up.

**Sticky feet:**
Once your foot touches a hold, it cannot be adjusted (as if glued). Forces precise first-attempt placement. Develops sequencing awareness — you must plan foot orientation for the next move before placing it.

**Target practice (Hörst):**
Climb a technical route ~1 grade below onsight. Sustained focus on feet: identify the best spot on every foothold, place toe with laser precision, stare at foot for 2-3 seconds before continuing. Develop kinesthetic feel — sense placement quality through your body, not just visually.

**Downclimbing:**
Downclimb all warm-up boulders/routes. Feet-first movement forces foot focus. More challenging than climbing up. Can be extended: downclimb to exact starting holds.

**Tennis ball hands (Anderson & Anderson):**
Hold a tennis ball in each hand. Climb a slab touching only the wall surface with the balls (not holds). Forces instep technique, hip opening, core engagement, and complete reliance on footwork. Surprisingly fun.

**No-hands slab:**
Climb a slab section using only feet — hands don't touch anything. Develops balance, weight shifting, and trust in feet. Even V0 slab is challenging without hands.

**Freeze (Consuegra Ch.8, Matros et al. 2013):**
Climb a problem with no dynamic moves. Pause for 2-3 seconds in position after each move. Works core strength, lock-off strength, technique, and movement efficiency simultaneously.

### 3.3 Bechtel "Climb Strong: Drills Manual" Integration

**Source:** Steve Bechtel, *Climb Strong: Drills Manual* (Daniele has the physical book — pages 31-90 contain the drill catalog)

**Status:** Pending — Daniele to photograph pages 31-90 when we work on this topic. These drills will significantly expand the catalog, particularly for:
- Climbing-specific movement patterns
- Power and coordination drills on wall
- Bouldering-specific technique work
- Advanced movement sequences

**Action:** When Bechtel photos are available, integrate into this file and populate the engine exercise database.

---

## 4. Technique Assessment for the Engine

### 4.1 Current Approach (v1)

| Measure | How | What it tells us |
|---------|-----|------------------|
| Onsight/Redpoint gap | User reports onsight and redpoint grades | Large gap (>3 grades) suggests strength > technique; small gap suggests good technique |
| Self-report questionnaire | 4-5 questions on technique aspects (1-5 scale) | Subjective baseline for technique areas |
| Board grade vs. finger strength | Compare MoonBoard/Kilter grade to hangboard test | If board grade is low relative to finger strength → technique is the limiter |

### 4.2 Roadmap (v2-v3)

From Topic 01 roadmap item R-03:
- Structured technique questionnaire (Cameron Hörst style)
- Board grade vs finger strength comparison as technique proxy
- Video-based assessment prompts (v3, LLM Coach)
- Seifert-style fluency metrics if wearable IMU data becomes available (v3+)

---

## 5. Implications for climb-agent

| Finding | Impact | Priority |
|---------|--------|----------|
| Elite use 20% energy of novice on same circuit (Baláš 2014b) | Technique training is the highest-ROI activity for beginners | v1 |
| Jerk coefficient decreases with practice (Seifert 2014) | Repetition on routes/boulders at sub-max grade improves fluency measurably | v1 |
| Route preview quality directly affects movement fluency (Seifert 2017) | Strengthen D28 (route preview prompt) with structured guidance | v1 |
| Silent feet is the most universally recommended beginner technique drill | Should be the first drill prescribed for all new users | v1 |
| Freeze drill works core + lock-off + technique simultaneously (Matros 2013) | Multi-benefit drill, good for warm-up and technique phases | v1 |
| Onsight/RP gap is a practical technique proxy | Already in assessment — validate against board grade comparison | v1 |
| Bechtel drill catalog (pages 31-90) | Major expansion of exercise database when available | v1 (pending) |

### New Decisions

| # | Decision | Rationale | Action |
|---|----------|-----------|--------|
| D73 | **Prescribe technique drills in every training phase, especially for beginners** | Baláš (2014b): technique gap between elite and novice is massive (5× energy difference). For beginners, technique training has higher ROI than any strength exercise. | Engine allocates technique drill time proportionally: beginners 30%+, advanced 10-15% of session time |
| D74 | **Silent feet as mandatory warm-up drill for all users** | Universal coaching consensus; develops precision, proprioception, body awareness. Low injury risk. Can be done at any level. | Add "silent feet" to default warm-up protocol alongside D33 warm-up generation |
| D75 | **Add structured route preview protocol to session guidance** | Seifert (2017): preview quality directly improves climbing fluency. Extends D28 from a simple prompt to a structured protocol (identify rests → plan crux → visualise clipping → plan descent). | Upgrade D28 route preview prompt to structured checklist |
| D76 | **Populate drill catalog from coaching consensus sources** | 7+ categories of drills from Hörst, Anderson, Matros, Claassen, and coaching community. Bechtel manual pending. | Build initial drill database with the drills documented in this topic; expand when Bechtel photos available |

---

## 6. References

1. Seifert L et al. (2014). "Climbing skill and complexity of climbing wall design: assessment of jerk as a novel indicator of performance fluency." *J Applied Biomechanics* 30(5):619-625.
2. Seifert L et al. (2017). "Role of route previewing strategies on climbing fluency and exploratory movements." *PLOS ONE* 12(4):e0176306.
3. Orth D et al. (2017). "Analysis of relations between spatiotemporal movement regulation and performance of discrete actions reveals functionality in skilled climbing." *Front Psychol* 8:1744.
4. Cordier P et al. (1993). "Entropy, degrees of freedom, and free climbing: a thermodynamic study." *Int J Sport Psychol* 24:370-378.
5. Baláš J et al. (2014a). Footwork and energy expenditure study (cited in Consuegra Ch.7).
6. Baláš J et al. (2014b). Elite vs novice energy study — 20% energy use (cited in Consuegra Ch.7).
7. Bertuzzi RCM et al. (2007). Economy of movement study (cited in Consuegra Ch.7).
8. Matros A et al. (2013). Wall-based core and technique exercises (cited in Consuegra Ch.8).
9. Bechtel S. *Climb Strong: Drills Manual.* Pages 31-90 pending integration.
10. Sanchez X et al. (2012). Route preview strategy in experts vs novices (cited in Topic 05).
11. Medernach J et al. (2024). Structured route preview and performance (cited in Topic 05).
12. Hörst E. "Improve climbing footwork with target practice." Training for Climbing blog.
13. Anderson M & Anderson M. The Rock Climber's Training Manual. Drill descriptions.
14. Claassen P. Precision Footwork tips. Climbing Magazine.

---

*End of Topic 08 — 4 new decisions (D73-D76), 14 references. Bechtel drill catalog pending photo integration.*
