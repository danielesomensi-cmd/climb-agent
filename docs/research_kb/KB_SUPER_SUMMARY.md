# climb-agent — Knowledge Base Super Summary

> **Generated:** 2026-04-05
> **Source:** All 35+ project files distilled into a single reference document
> **Purpose:** Complete overview of research findings, decisions, architecture, and status

---

## 1. PROJECT OVERVIEW

**climb-agent** is a deterministic AI-powered climbing training engine that generates personalized training plans. It uses a rule-based resolver (no ML), structured around:

- **Assessment module** → 5-axis athlete profile
- **Macrocycle generator** → phase-sequenced training plan (Hörst 4-3-2-1 + DUP)
- **Session templates + Exercise catalog** → concrete workouts
- **Progression engine** → load/intensity adaptation
- **Closed-loop feedback** → adjustment based on session outcomes

**Target user:** Daniele (project owner, 16yr experience, 8a lead / 7C boulder, targeting 8a+). Engine designed for intermediate-to-advanced climbers.

**Two-project architecture:** claude.ai KB project (research & decisions) + Claude Code project (implementation). Handoff via structured briefs.

---

## 2. THE SCIENCE — 10 RESEARCH TOPICS DISTILLED

### Topic 01: Performance Determinants

**Core finding:** 7 variables explain 77% of climbing performance variance (Magiera 2013, n=30). In order: (1) maximal relative finger strength, (2) mental endurance, (3) climbing technique, (4) isometric finger endurance, (5) reaction time accuracy, (6) ape index, (7) VO2 at anaerobic threshold.

**Evidence base:** 5 systematic reviews (Faggian 2024 — 74 studies; Langer 2023 — 156 studies; Saul 2019; Diez-Fernandez 2023; Ginszt 2023), plus landmark originals (Mermier 2000: trainable variables = 59% variance, anthropometry = 0.3%).

**Engine decisions:**
- **5-axis assessment:** finger_strength, pulling_strength, power_endurance, technique, endurance
- D01: Body composition axis removed (0.3% variance, ED risk)
- D03: Flexibility axis → v2 (threshold effect)
- D04: Mental/Tactical → v3 (not objectively measurable yet)
- D05: Contact strength/RFD → v3 (needs force sensor)

### Topic 02: Finger Strength

**Core finding:** Finger strength is the #1 predictor (r = 0.42–0.92). Three levels of adaptation: neural (2–8 wk), muscular (4–8 mo), structural/tendon (1–3+ yr). Tendons are the rate-limiting factor.

**Major methodologies:**
- **Eva López PhD:** MaxHangs MAW (85–100% MVC, 5–10s), MaxHangs MED (BW on minimum edge), IntHangs (60–80% MVC, 7–15s on/3–15s off), SubHangs (55–85% MVC, 20–45s)
- **Tyler Nelson / C4HP:** Recruitment (overcoming isometrics, RPE 10, 3–5s), Density (yielding, 40–75% MVC, 30–45s), Hypertrophy (60–80% MVC, 20–30s)
- **Lattice Training:** Large-scale normative data (n=901+), 7s hang protocol validated

**Key research findings:**
- Half crimp alone explains 57% of bouldering variance; + front 3 drag = 66% (Söderqvist 2024)
- 5 wk dynamic finger training improved strength but NOT grade (Saeterbakken 2024 RCT)
- López load monitoring rule: edge drops >2mm or weight >25% → excessive fatigue
- 20mm edge is the global standard; 7s hang aligns with competition contraction times

**Engine decisions:** D10 (add overcoming isometric), D11 (warm-up repeaters 40mm), D12 (correct density hang protocol), D35 (hangboard experience gates), D72 (open-hand default, never full crimp on hangboard)

### Topic 03: Pump, Endurance, Capillaries

**Core finding:** The pump is caused by H+ accumulation + inorganic phosphate + blood flow occlusion (NOT "lactic acid"). At >50% MVC, forearm blood flow is completely occluded. Intermittent finger flexor tests are ~60% aerobic (Maciejczyk 2021).

**Critical concepts:**
- **Critical Force (CF):** boundary of sustainable climbing intensity (Baláš 2024, Giles 2019)
- **ARC training:** 20–45 min continuous easy climbing for capillarization + mitochondrial density
- **Flash pump prevention:** 15–20 min progressive warmup essential
- **Energy system crossover:** at ~60–75s sustained climbing, aerobic becomes primary

**Engine decisions:** D15 (progressive ARC duration), D17 (G-Tox recovery cue), D45 (<25% MVC ceiling for ARC), D47 (replace 4×4 with varied-intensity intervals per Consuegra), D48 (easy traversing recovery)

### Topic 04: Periodization

**Core finding:** Periodized > non-periodized for strength (ES = 0.31–0.43). DUP slightly superior for trained athletes (ES = 0.61, Moesgaard 2022). No difference for hypertrophy. No climbing-specific periodization RCT exists.

**Engine model:** Hörst 4-3-2-1 hybrid = sequential phases (Base → Strength → PE → Performance → Deload) + concurrent DUP within each phase. Well-supported by evidence.

**Phase structure:** Base (≥6 wk per D44), Strength (2–3 wk), PE (2–3 wk), Performance (1–2 wk), Deload (1 wk). Total ~10–13 wk.

**Taper science:** Reduce volume 60–90%, maintain intensity, reduce frequency ≤20%. Progressive nonlinear taper > step taper. Produces ~2–6% performance improvement (Mujika & Padilla 2003).

**Engine decisions:** D19 (simplified linear for beginners), D20 (overreach + taper before Performance), D21 (minimum phase duration), D22 (3-week competition taper, v2), D23 (multi-macrocycle seasonal planning, v2)

### Topic 05: Psychology & Mental Training

**Core finding:** Psychology is #2 predictor (Magiera: canonical weight −0.410). First comprehensive SR: Mangan 2024, 83 studies. Flow, confidence, and anxiety facilitation are key performance mediators. Fear of falling impacts women disproportionately (Sendín-Pérez 2025). Route previewing is a trainable cognitive-motor skill.

**Actionable for engine:** Route preview protocol (D75), structured self-reflection via LLM Coach (v3). Hörst Ch.3: ANSWER sequence, progressive relaxation, centering, visualization.

**Engine decisions:** D28/D75 (structured route preview protocol), D29 (fall practice progression, v2), D30 (pre-climb centering cue), D31 (post-session reflection prompt)

### Topic 06: Nutrition, Recovery, Sleep

**Core finding:** Climbers frequently under-eat. RED-S is a documented risk. Supplement evidence is limited. Engine role is educational, never prescriptive on diet/weight.

**Key evidence:**
- 15.8% amenorrhoea prevalence in elite female competition climbers (Joubert 2022)
- Vitamin C (50mg) + hydrolysed collagen (15g) 30–60 min pre-training → enhanced collagen synthesis (Shaw 2017)
- Creatine: small-dose OK, loading counterproductive for climbers (Hörst Ch.11)
- Sleep: <7h = increased injury risk; 8–10h optimal for recovery (Watson 2017)
- G-Tox technique: alternating arms overhead during rests → +18.4% grip recovery (Hörst)
- Active rest +35% lactate clearance vs passive (Watts 2000)

**Engine decisions:** D64 (never suggest weight loss, never comment on body composition), D65–D67 (recovery education cues, v2)

### Topic 07: Overtraining, Injury, Load Management

**Core finding:** 93% of climbing injuries are chronic overuse; fingers = 52% of all injuries. Key risk factors: higher intensity, bouldering, crimp grip, reduced grip strength relative to demands, previous injury.

**Prevention strategies:** Progressive load management, antagonist/eccentric training, proper warm-up, avoid full crimp under max load. ACWR (Acute:Chronic Workload Ratio) 0.8–1.3 = safe zone.

**ACT ebook (Schöffl/Matros/Korb):** Highly relevant for prehab catalog. Pulley injury grading system. Tendon healing timelines: grade I = 6 wk, grade II = 3–6 mo, grade III = surgery.

**Engine decisions:** D68 (injury history in onboarding), D69–D71 (load monitoring, v2), D72 (never prescribe full crimp on hangboard), D55 (exercise safety blacklist)

### Topic 08: Technique & Movement

**Core finding:** Elite climbers use as little as 20% of the energy of novices on the same circuit (Baláš 2014b). Jerk coefficient (Seifert 2014) quantifies movement fluency. Technique is primarily trained through deliberate practice drills, not strength exercises.

**Assessment proxies:** OS/RP gap, board grade vs finger-strength-predicted grade (D09), self-report questionnaire.

**Drill catalog sources:** Consuegra Ch.8 wall-based exercises, Bechtel Drills Manual (pp.31–90 pending), Hörst Ch.4.

**Engine decisions:** D73 (technique drills 30%+ of session for beginners), D74 (silent feet in warm-up), D75 (structured route preview), D76 (drill rotation system)

### Topic 09: Climbing Philosophy & Motivation

**Framework:** Self-Determination Theory (Ryan & Deci) — autonomy, competence, relatedness. Coach voice: "train better, not more" (Consuegra). Frame training as mastery path, respect user autonomy, celebrate progress.

**Engine decisions:** D77 (Coach personality: encouraging but honest), D78 (progress celebration cues), D79 (methodology transparency)

### Topic 10: Female, Age, Youth Considerations

**Key findings:**
- Menstrual cycle: evidence inconclusive for performance effects (Phillips 2023 umbrella review). Individual tracking recommended.
- Youth (<16): growth plate vulnerability → D80 blocks campus/max hangboard/hypergravity
- Youth (<18): max 4 training days/week (D81)
- Older climbers (40+): extended recovery timelines, injury prevention emphasis

**Engine decisions:** D80 (youth age gates <16), D81 (max 4 days/wk <18), D82 (optional menstrual cycle tracking, v2), D83 (age-adjusted recovery parameters)

---

## 3. CONSUEGRA SYNTHESIS — Key Unique Contributions

From "The Science of Climbing Training" (2023), Chapters 7, 8, 10:

- Debunked athletics-based climbing physiology model (climbing ≠ running analogy)
- Lactate levels in climbing only 5–7 mmol/L (vs 17 in sprinting)
- Force-Time Integral (FTI) as key endurance metric
- ARC intensity ceiling: <25% MVC / 1–2 pump scale (D45)
- Replace 4×4 with varied-intensity intervals — 4×4 drives total vascular occlusion (D47)
- Beginners: 70% climbing / 30% conditioning ratio (D51)
- ATR block periodization model for climbing (D27, v2 research)
- 27 detailed exercise/training sections in Ch.8 → decisions D33–D63

---

## 4. HÖRST "TRAINING FOR CLIMBING" SYNTHESIS — Key Additions

7 chapters synthesized (Ch. 2, 3, 4, 6, 11, 12, 13). Integration audit result: **0 conflicts, 14 confirmations, 6 new coaching cues**.

**Ch.6 — Mobility & Stability:** 38 exercises cataloged across 6 categories (8 SMR, 18 stretches, 7 wrist stabilizers, 2 rotator cuff, 4 scapular, 3 push). Pyramid principle: Mobility → Stability → Strength → Power.

**Ch.12 — Recovery:** 3-period model (short-term 10–30 min, medium 24–72h, long-term 1–4 wk). ATP-CP resynthesis 3–5 min. Active rest +35% lactate clearance. Post-exercise 4:1 carb:protein. Central fatigue 7× slower than peripheral.

**Key coaching cues proposed:**
- CUE-01: "Roll, then stretch" warm-up sequence
- CUE-02: No heavy forearm flexor static stretching before performance (reduces grip strength up to 1 hour)
- CUE-03: G-Tox alternating arms during rests
- CUE-04: 4:1 carb:protein within 30 min post-training
- CUE-05: Active rest day = 30–60 min light activity
- CUE-06: Visualization before redpoint attempts

---

## 5. DECISION LOG SUMMARY

**Total decisions:** 91 (D01–D91)
**Active:** 85 | **Superseded:** 3 (D16→D47, D18→D33, D28→D75) | **Reserved:** 3 (D02, D07, D09)

### By Version
| Version | Count | Scope |
|---------|-------|-------|
| v1 (launch) | 57 | Assessment, exercises, session planning, periodization, load monitoring, coaching |
| v2 (post-launch) | 16 | Flexibility axis, ATR model, competition taper, VBT, BFR, menstrual tracking |
| v3 (future) | 6 | LLM Coach, RFD, critical force |
| Test protocols (D84–D91) | 8 | 5 implemented, 3 deferred |

### Critical Safety Decisions
- D64: Never suggest weight loss or comment on body composition
- D80: Block campus/max hangboard/hypergravity for <16
- D81: Max 4 training days/week for <18
- D35: Hangboard experience gates (2+ years for advanced protocols)
- D55: Exercise safety blacklist
- D72: Never prescribe full crimp on hangboard

### Key Conflicts Resolved
- T1: D21 vs D44 → ARC phase min 6 weeks overrides general min
- T2: D19 vs D27 → Keep simple linear for beginners in v1
- T3: D16 vs D47 → Replace 4×4 entirely (D16 superseded)
- T6: D73 vs D51 → Technique drills ⊂ climbing time (no conflict)
- T7: D75 upgrades D28 → Route preview now structured protocol

---

## 6. ENGINE ARCHITECTURE

**Data flow:**
```
Assessment → 5-axis profile → Macrocycle (phases + domain weights)
→ Weekly Planner (session slots) → Session Resolver (exercise selection)
→ Progression Engine (load targets) → Exercise Ordering → Guided UI
→ Feedback → Closed-loop adaptation
```

**Exercise selection:** P0 filter chain (equipment → location → experience gates → safety blacklist → role matching → pattern matching → scoring with recency penalty)

**Key naming corrections applied:**
- `density_hang_endurance` → `sub_max_capacity_hang` (was incorrectly implying ~75% MVC)
- `intermittent_dead_hang` → `repeater_sub_max_endurance` (actual intensity 40–55% MVC)
- `threshold_climbing` domain: `aerobic_capacity` → `power_endurance` (occlusion at >50% MVC)

---

## 7. IMPLEMENTATION STATUS

**Mega-brief v1:** ~80% implemented, archived. Remaining decisions migrated to backlog.

**Completed:** Auth (Clerk) ✅, DB (Supabase JSONB) ✅, all P1 bug fixes (30+ items) ✅, circuit timer ✅, campus gate + selection quality ✅, exercise rotation ✅.

**In progress / remaining:**
- Stripe subscriptions (pricing TBD)
- Frontend error handling hardening (R141)
- Template gap fix (P0: gym sessions producing 2–3 blocks where literature prescribes 5–7)
- Session 2 patch (4 corrections: D11, D12, D39, D72) — prepared, not applied
- Multiple v2 backlog items (D19, D20, D22, D23, D29, D37, D47, D49, etc.)

---

## 8. OPEN RESEARCH ITEMS

| Item | Status |
|------|--------|
| Bechtel Drills Manual pp.31–90 (Topic 08) | Pending photo upload |
| Phase B books (MacLeod, Ilgner, Climbing Bible ×2) | Not acquired (~€45) |
| Topics 01–04 Steps 4–5 (engine verification + finalization) | Not started |
| Engine audit v4 (full resolver output data needed from Claude Code) | Pending data extraction |
| Free mobility session design (using Ch.6 material) | Not started |
| Coach Knowledge Base v2 (conversational LLM coach) | Spec written, not implemented |

---

## 9. KEY LEARNINGS & PRINCIPLES

1. **Template gap is P0:** Sessions must have 5–7 blocks minimum (core, antagonist/prehab, supplementary pulling, cooldown were missing)
2. **Bug vs placement:** "Wrong exercise for session" ≠ "correct exercise in wrong block"
3. **Naming must reflect physiology:** Names should match actual intensity/mechanism
4. **Domain classification has downstream consequences:** Incorrect domain → wrong sort category → wrong session placement
5. **Contact strength ≠ pulling strength:** RFD (first 100–200ms) is distinct from max pulling force
6. **Test protocol precision matters:** Repeater test at 60% MVC-7 (not 80%), single continuous set to failure
7. **Pre-performance stretching warning:** No heavy forearm flexor static stretching before climbing
8. **Memory materialization:** Critical findings must be written to files before session ends
9. **Recency penalty tuning:** -100 → -30 for last-5 exercises → technique_drill variety 3 → 12 unique across 4 weeks

---

## 10. REFERENCE COUNT & SOURCES

~275 total references across the KB:
- 5 systematic reviews on performance determinants
- 4 meta-analyses on periodization
- Eva López PhD + 3 peer-reviewed studies
- Tyler Nelson / C4HP methodology
- Hörst "Training for Climbing" 3rd ed. (7 chapters synthesized)
- Consuegra "The Science of Climbing Training" (3 chapters synthesized)
- ACT ebook (Schöffl/Matros/Korb) — read in full
- Lattice Training normative data (n=901+)
- Maciejczyk 2021 (energy systems), Levernier & Laffaye (RFD), Mujika (tapering)
- Quarmby 2023 SR (injury epidemiology)
- Mangan 2024 SR (climbing psychology, 83 studies)
- ~15 Hörst cited studies integrated

---

*End of Super Summary — 2026-04-05*
