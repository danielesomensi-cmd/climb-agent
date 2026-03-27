# Hörst Integration Audit — 7 Chapters vs. Existing KB
> **Date:** 2026-03-27
> **Scope:** Cross-reference all 7 Hörst synthesis files against Topics 01–10, D01–D83, and mega-brief
> **Result:** 0 conflicts, 14 confirmations, 6 proposed new coaching cues, 2 minor corrections, 1 proposed new decision

---

## 1. FILES AUDITED

### Hörst Synthesis Files (new)
| File | Chapter | Topic Target | Status |
|------|---------|-------------|--------|
| `horst_ch2_self_assessment_synthesis.md` | Ch. 2 — Self-Assessment & Goal Setting | Topic 01 | ✅ |
| `horst_ch3_mental_training_synthesis.md` | Ch. 3 — Mental Training | Topic 05 | ✅ |
| `horst_ch4_technique_skill_synthesis.md` | Ch. 4 — Training Technique & Skill | Topic 08 | ✅ |
| `horst_ch6_mobility_synthesis.md` | Ch. 6 — Mobility, Stability, Antagonist Training | Topic 07 + Catalog | ✅ |
| `horst_ch11_nutrition_synthesis.md` | Ch. 11 — Performance Nutrition | Topic 06 | ✅ |
| `horst_ch12_recovery_synthesis.md` | Ch. 12 — Accelerating Recovery | Topic 06 | ✅ |
| `horst_ch13_injury_synthesis.md` | Ch. 13 — Injury Treatment & Prevention | Topic 07 | ✅ |

### Existing KB Files (checked against)
- `decision_consolidation_D01_D83.md` (master reference)
- `00_INDEX.md`
- `cross_check_report.md`
- `06_nutrition_recovery_sleep.md` (Topic 06)
- `07_overtraining_injury_load.md` (Topic 07)
- `claude_code_mega_brief_v1.md` (Sessions 1–10)
- `ROADMAP_CURRENT.md`

---

## 2. CONFLICTS FOUND: 0

**No conflicts between any Hörst chapter and existing KB decisions.** All Hörst content either confirms, extends, or adds new coaching-level material that doesn't contradict the research-based decisions already made.

---

## 3. CONFIRMATIONS (Hörst strengthens existing decisions)

| # | Hörst Source | Confirms | How |
|---|-------------|----------|-----|
| C1 | Ch. 6 §6 (antagonist 2×/week) | D33–D43 (ACT decisions) | Same priority: scapular stability + rotator cuff first, forearm extensors second |
| C2 | Ch. 6 §6 (Pyramid: Mobility→Strength→Power) | D33 (warm-up protocol) | Confirms "develop stability before strength, strength before power" |
| C3 | Ch. 12 §2.1 (ATP-CP resynthesis 3–5 min) | D12 (rest times 120–300s) | Physiological basis for our existing rest-time prescription |
| C4 | Ch. 12 §2.2 (exponential recovery curve) | D20 (overreach + taper) | 70% recovery in first 1/3 of time supports deload timing |
| C5 | Ch. 12 §5.7 (active rest day: 30–60 min light activity) | D62 (active rest day design) | Exactly our model, including ARC-style easy climbing |
| C6 | Ch. 11 §2.3 (low-carb diets inappropriate for climbers) | D26 (energy system model) | Climbing = mixed anaerobic alactic + glycolytic — needs carbs |
| C7 | Ch. 13 (injury prevention via antagonist training) | D58 (postural correction), D60 (wrist extension protocol) | Hörst's entire Ch. 6 exercise catalog supports these decisions |
| C8 | Ch. 6 §4 (roll first, stretch second) | D33 (warm-up protocol) | Confirms our warm-up sequence order |
| C9 | Ch. 12 §3.3 (active rest +35% lactate clearance) | D48 (easy traversing recovery cue) | Watts 2000 study confirms our D48 design |
| C10 | Ch. 4 (technique: economy of movement) | D73 (technique drills ≥30% for beginners) | Hörst confirms technique = primary performance driver, not strength |
| C11 | Ch. 6 §D1 (chicken-wing = wrist extension deficit) | D60 (wrist extension protocol) | Hörst explains the biomechanical WHY behind our D60 decision |
| C12 | Ch. 3 (Progressive Relaxation Sequence) | D30 (fall practice drill) + D29 (mental reflection) | Complementary mental training tools |
| C13 | Ch. 2 (self-assessment: weak link identification) | D01 (5-axis assessment) | Hörst's self-assessment approach directly supports multi-axis profiling |
| C14 | Ch. 11 §7.4 (creatine: loading counterproductive for climbers) | Topic 06 §4 (creatine weight gain concern) | Topic 06 already flagged weight concern; Hörst provides detailed mechanism (cell volumizing → worse pump) |

---

## 4. MINOR CORRECTIONS / CLARIFICATIONS NEEDED

### 4.1 Sleep Range Discrepancy (minor)

| Source | Minimum Sleep | Notes |
|--------|--------------|-------|
| Topic 06 (D65, from IOC consensus) | **7 hours** adults | Research-based |
| Hörst Ch. 12 | **6–7 hours** minimum | Slightly lower floor |
| IOC + Charest & Grandner 2020 | **7 hours** minimum | Primary source |

**Resolution:** Keep **7 hours** as our minimum (D65) — IOC consensus is a stronger source than Hörst's practical recommendation. No change needed. Hörst's "6 hours" is his stated bare minimum ("bare minimum amount"), not his recommendation. He explicitly says 8–10 hours is ideal after hard training, which aligns with our D65.

**Action:** None — no correction needed.

### 4.2 Creatine Guidance Enrichment

Topic 06 currently says: "If asked: explain trade-off honestly, recommend consulting sports dietitian."

Hörst Ch. 11 provides a much more nuanced, climbing-specific position:
- Small-dose (2–5g/day) = potentially beneficial for power recovery
- Loading protocol (10–20g/day) = explicitly counterproductive (weight gain, cell volumizing → worse pump)

**Action:** Enrich Topic 06 or D67 with Hörst's nuanced creatine guidance. Not a conflict — an upgrade.

---

## 5. PROPOSED NEW COACHING CUES (v2 Coach LLM)

These are **new coaching-level content items** from Hörst that don't exist in our current KB. All are v2 Coach material — not engine logic changes.

### CUE-01: G-Tox Technique (from Ch. 12)
**Current state:** D17 already includes G-Tox as a coaching cue in rest prompts.
**Hörst adds:** Detailed physiological explanation (arterial inflow > venous return in dangling position), specific protocol (alternate every 5–10 seconds), and a university research citation (Roberts 2003).
**Action:** Enrich D17's rationale field in the Coach KB. Already planned for Session 10.

### CUE-02: "Don't Stretch Forearm Flexors Hard Pre-Climb" (from Ch. 6)
**Current state:** NOT in our KB. This is an important NEW coaching cue.
**Content:** Excessive static stretching of forearm flexors before climbing may reduce maximum grip strength and power for up to 1 hour. Favor light stretching, Armaid use, and sports massage before performance climbing.
**Action:** ⚠️ **Add as coaching cue to D33 (warm-up protocol).** Important for Session 4 (Warm-Up). Could prevent our warm-up generator from prescribing heavy forearm flexor stretching before performance sessions.
**Priority:** v1 — this directly affects warm-up session generation logic.

### CUE-03: Post-Exercise Refueling Protocol (from Ch. 12)
**Current state:** D66 mentions "fuel your training" messaging. Topic 06 discusses post-exercise in general terms.
**Hörst adds:** Specific 3-step post-climb protocol:
1. First 30 min: high-GI + protein in 4:1 ratio (chocolate skim milk)
2. 2 hours after: full meal at 65:15:20
3. Before bed: skim milk + carb for glycogen resynthesis + tryptophan
**Action:** Add as detailed coaching cue for v2 Coach post-session messaging. Not engine logic.

### CUE-04: Scapular Pull-Up as "Best Exercise Nobody Does" (from Ch. 6)
**Current state:** Not specifically called out in our exercise catalog priorities.
**Content:** Hörst considers this perhaps the most impactful exercise for shoulder health and climbing longevity. Develops kinesthetic awareness of scapular position, enables climbing harder and longer with good form despite fatigue.
**Action:** When populating exercise catalog (Session 3), flag `EX-SCAP-04` as high-priority for all training plans. Consider making it part of the standard antagonist routine alongside Nordic curls (D56).

### CUE-05: Caffeine Periodization for Performance Days (from Ch. 11)
**Current state:** Not in KB.
**Content:** Decrease daily caffeine dosing in days leading up to a critical climb/competition → return to normal moderate dose on performance day. Superior to simply doubling dose (which risks jitters, GI distress, impaired fine motor control).
**Action:** v2 Coach — mention in competition/performance-day preparation tips.

### CUE-06: Central Fatigue Recovery Timeline (from Ch. 12)
**Current state:** Topic 06 mentions CNS fatigue from Consuegra (24–48h). Topic 07 discusses overtraining.
**Hörst adds:** Nerve cell takes up to 7× longer to recover than muscle cell (Bompa 1983). If you still feel "off" after several rest days, you may need 2–10 more days.
**Action:** Enrich D70 (overtraining detection heuristics) with this specific recovery timeline. Useful for the engine's deload trigger logic: if user reports persistent fatigue after standard rest → suggest extended deload rather than standard rest day.

---

## 6. PROPOSED NEW DECISION

### D84-CANDIDATE: Warm-Up Forearm Flexor Stretch Restriction

**Rationale:** Hörst Ch. 6 explicitly states that excessive static stretching of forearm flexors before climbing reduces grip strength for up to 1 hour. This is a concrete, actionable, evidence-based constraint that directly affects our warm-up generator (D33, Session 4).

**Proposed rule:** In `generate_warmup()`, if session type = performance (projecting, max strength, power):
- **DO NOT** include extended forearm flexor static stretching (>10s holds)
- **DO** include light dynamic finger/wrist warm-up (EX-STR-01, EX-STR-02)
- **DO** include Armaid/SMR forearm work (which doesn't impair strength)
- For non-performance sessions (ARC, volume, technique): forearm flexor stretching is fine

**Version:** v1 — affects warm-up session generation directly.

**Status:** Candidate — needs your confirmation before adding to the consolidation.

---

## 7. INDEX UPDATE PROPOSAL

The `00_INDEX.md` should be updated to include the 7 Hörst files. Proposed addition:

```markdown
## Hörst Synthesis Files (Primary Source)

| File | Chapter | Topic Target | Exercises | References |
|------|---------|-------------|-----------|------------|
| `horst_ch2_self_assessment_synthesis.md` | Ch. 2 — Self-Assessment | Topic 01 | — | Hörst 2022 |
| `horst_ch3_mental_training_synthesis.md` | Ch. 3 — Mental Training | Topic 05 | — | Hörst 2022 |
| `horst_ch4_technique_skill_synthesis.md` | Ch. 4 — Technique & Skill | Topic 08 | — | Hörst 2022 |
| `horst_ch6_mobility_synthesis.md` | Ch. 6 — Mobility/Antagonist | Topic 07 + Catalog | **38 exercises** | Hörst 2022 |
| `horst_ch11_nutrition_synthesis.md` | Ch. 11 — Nutrition | Topic 06 | — | Hörst 2022 + 4 cited studies |
| `horst_ch12_recovery_synthesis.md` | Ch. 12 — Recovery | Topic 06 | — | Hörst 2022 + 11 cited studies |
| `horst_ch13_injury_synthesis.md` | Ch. 13 — Injury | Topic 07 | — | Hörst 2022 |
```

**Updated totals:**
- Total files: 20 → **27**
- Total references: ~260 → **~275** (Hörst + cited studies)
- Exercise catalog from Ch. 6: **38 new exercises** (8 SMR, 18 stretches, 7 wrist stabilizers, 2 rotator cuff, 4 scapular, 3 push)

---

## 8. EXERCISE CATALOG IMPACT

Ch. 6 produces **38 exercises** that need to be added to the engine's exercise database. These map to mega-brief **Session 3** (Exercise Database — Conditioning, Injury Prevention & Drills).

**Breakdown by engine category:**

| Engine Category | Ch. 6 Exercises | Priority | Session |
|----------------|----------------|----------|---------|
| `warm_up` | EX-STR-01 (Arm Circles), EX-STR-02 (Finger Curls), EX-ANT-01 (Rubber Band) | v1 — already in D33 warm-up | Session 4 |
| `smr_recovery` | EX-SMR-01 through EX-SMR-08 (8 exercises) | v2 — rest-day / free mobility session | Future |
| `flexibility` | EX-STR-03 through EX-STR-18 (16 exercises) | v2 — D62 (ROM session) | Future |
| `antagonist_wrist` | EX-ANT-02 through EX-ANT-07 (6 exercises) | v1 — D60 (wrist extension protocol) | Session 3 |
| `antagonist_rotator_cuff` | EX-RC-01, EX-RC-02 (2 exercises) | v1 — D58 (postural correction) | Session 3 |
| `antagonist_scapular` | EX-SCAP-01 through EX-SCAP-04 (4 exercises) | v1 — D58 (postural correction) | Session 3 |
| `antagonist_push` | EX-PUSH-01 through EX-PUSH-03 (3 exercises) | v1 — general antagonist | Session 3 |

**Key insight:** The Session 3 brief already includes D37 (core catalog from Matros), D56 (Nordic curl), D57 (lower body catalog), D58 (postural correction), D60 (wrist extension). The Ch. 6 exercises provide the **concrete exercise data** to populate these decisions. This is a perfect fit — no new decisions needed, just richer exercise data.

---

## 9. WHAT DOESN'T NEED ACTION

These Hörst findings are interesting but don't require any KB changes because they're purely informational or already covered:

| Hörst Content | Why No Action |
|--------------|---------------|
| Ch. 2: Self-assessment philosophy | Informational context for D01 assessment design — no change needed |
| Ch. 3: Progressive Relaxation Sequence | v2/v3 Coach feature (D04 mental assessment) — not engine logic |
| Ch. 4: Technique drill descriptions | Enriches D76 (drill catalog) but doesn't change any decisions |
| Ch. 11: GI table, protein BV table | Informational for Coach v2 — not engine logic |
| Ch. 11: Macro ratio 65:15:20 vs 55:15:30 | Educational coaching content, aligns with D66 messaging. No engine rule needed |
| Ch. 12: Sports massage cross-fiber technique | Good content for Coach v2 recovery tips, not engine logic |
| Ch. 13: Injury treatment protocols | Informational — engine should detect/prevent, not treat |

---

## 10. SUMMARY OF RECOMMENDED ACTIONS

| # | Action | Priority | Effort | Target |
|---|--------|----------|--------|--------|
| A1 | Add CUE-02 (forearm flexor stretch restriction) as new decision or D33 amendment | **v1** | S | mega-brief Session 4 |
| A2 | Enrich D17 (G-Tox) rationale with Ch. 12 physiological detail | v1 | XS | mega-brief Session 10 |
| A3 | Enrich D70 (overtraining heuristics) with central fatigue 7× recovery timeline | v1 | S | mega-brief Session 9 |
| A4 | Add Ch. 6 exercise data to Session 3 population brief | **v1** | M | mega-brief Session 3 |
| A5 | Update `00_INDEX.md` to include 7 Hörst files | v1 | XS | Project knowledge |
| A6 | Enrich Topic 06 creatine section with Hörst's nuanced guidance | v1 | XS | Topic 06 file |
| A7 | Add CUE-03 (post-exercise refueling protocol) to Coach KB spec | v2 | S | `coach_knowledge_base_spec.md` |
| A8 | Add CUE-04 (scapular pull-up priority) to antagonist exercise selection | v1 | XS | Session 3 exercise data |
| A9 | Add CUE-05 (caffeine periodization) to Coach KB | v2 | XS | `coach_knowledge_base_spec.md` |

---

*End of Hörst Integration Audit*
