# climb-agent — Claude Code Mega-Brief (v1 Implementation)

> **Date:** 2026-03-16
> **Purpose:** Self-contained implementation guide for Claude Code to execute all 57 v1 decisions
> **Source:** Knowledge base Topics 01-10 + Consuegra synthesis + decision consolidation D01-D83
> **How to use:** Execute sessions 1-10 in order. Each session is self-contained with: context, decisions, specifications, acceptance criteria, and files to modify.

---

## TABLE OF CONTENTS

1. [Engine Context](#engine-context)
2. [Session 1: Assessment & Onboarding](#session-1)
3. [Session 2: Exercise Database — Strength & Hangboard](#session-2)
4. [Session 3: Exercise Database — Conditioning, Injury Prevention & Drills](#session-3)
5. [Session 4: Session Planner — Warm-Up](#session-4)
6. [Session 5: Session Planner — Intensity System (EL)](#session-5)
7. [Session 6: Session Planner — Hangboard Logic](#session-6)
8. [Session 7: Session Planner — Endurance & Intervals](#session-7)
9. [Session 8: Session Planner — Conditioning, Technique & Ratio](#session-8)
10. [Session 9: Periodization & Load Management](#session-9)
11. [Session 10: Coaching Cues, Safety & UX](#session-10)
12. [Cross-Session Safety Rules](#safety-rules)
13. [Glossary](#glossary)

---

## <a id="engine-context"></a>ENGINE CONTEXT

### Current Architecture

```
Assessment (6 dimensions → radar profile 0-100)
  → Goal (lead_grade or boulder_grade, target + deadline)
  → Macrocycle (Hörst 4-3-2-1 + DUP, 10-13 weeks, 5 phases)
  → Week (planner_v2 phase-aware, domain weights + session pool)
  → Session (resolver selects concrete exercises with loads)
  → Feedback (granular per exercise, plan vs actual)
  → Adaptation (closed-loop, multiplier-based)
```

### Tech Stack
- Runtime logic: Pure Python, deterministic, no LLM
- Persistence: JSON/JSONL (Railway) → Supabase Postgres (planned)
- Frontend: Next.js 14 + React + Tailwind + shadcn/ui (PWA)
- Current counts: 981 tests, 167 exercises, 31 sessions, 25 templates, 42 API endpoints

### Key Code Functions
- `compute_assessment_profile()` — assessment_v1
- `generate_macrocycle()` — macrocycle_v1
- `generate_phase_week()` — planner_v2
- `resolve_session()` — session resolver

### Current Assessment: 6 Axes
1. `finger_strength` — Max hang 20mm 5s (kg/BW)
2. `finger_endurance` — Repeaters 7:3 x6 on 20mm, or Critical Force
3. `pulling_strength` — Weighted pullup 1RM (kg/BW)
4. `power_endurance` — 4×4 bouldering or continuous route time
5. `technique` — Onsight vs redpoint gap + self-report
6. `body_composition` — BW, body fat %, force/weight ratio ← **TO BE REMOVED (D01)**

### Current Phases (Hörst 4-3-2-1)
1. Endurance Base (3-4 wk)
2. Strength & Power (2-3 wk)
3. Power Endurance (2-3 wk)
4. Performance (1-2 wk)
5. Deload (1 wk)

### Feedback System
Per exercise: `very_easy | easy | ok | hard | very_hard`
Session RPE tracked. Session completion tracked.

---

## <a id="session-1"></a>SESSION 1: ASSESSMENT & ONBOARDING

**Decisions:** D01, D38, D68, D80, D81, D83
**Estimated effort:** Medium (data model changes + onboarding flow)
**Dependencies:** None — this goes first

---

### D01: Remove body_composition axis (6 → 5 axes)

**What:** Remove `body_composition` from the assessment profile. Go from 6 to 5 axes.

**Final 5 axes:**
1. `finger_strength`
2. `pulling_strength`
3. `power_endurance`
4. `technique`
5. `endurance`

**What to keep:**
- Body weight as numeric input (used for ratio calculations: max hang %BW, pull-up %BW)
- Height (for future ape index calculation)

**What to remove:**
- `body_composition` axis from profile computation
- Body fat % question from onboarding
- Body fat % rows from benchmark tables
- `body_composition` from radar chart rendering (5 axes not 6)
- `body_composition` weight from macrocycle domain weight derivation → redistribute proportionally to remaining 5 axes

**Safety rule:** The engine must NEVER comment on body weight, body fat, or suggest weight loss. No messaging about body composition whatsoever.

**Source:** Mermier 2000 (anthropometry = 0.3% variance), Lattice Training methodology, D64 RED-S safety.

**Files to modify:**
- Assessment profile computation
- Radar chart component
- Benchmark tables
- Onboarding flow (remove body fat Q, keep BW)
- Macrocycle weight derivation (redistribute)
- `DESIGN_GOAL_MACROCICLO` documentation

**Acceptance criteria:**
- [ ] Profile has exactly 5 axes
- [ ] Radar chart renders 5 axes
- [ ] BW still collected and used for ratio calculations
- [ ] No body fat % question anywhere
- [ ] Macrocycle weights sum to 100% across 5 axes
- [ ] Existing tests pass (update affected tests)

---

### D38: Add Brzycki 1RM estimation for pulling strength

**What:** Implement Brzycki formula to estimate 1RM from submaximal test data.

**Formula:** `1RM = weight × (36 / (37 - reps))`

**Use case:** When user can't do a true 1RM weighted pull-up (injury risk), they can do submaximal reps:
- Example: 5 reps at +20kg → 1RM ≈ (BW+20) × 36/32

**Implementation:**
- Add to onboarding: option to enter either true 1RM OR submaximal reps + load
- If submaximal: compute estimated 1RM via Brzycki
- Store both raw input and estimated 1RM
- Use estimated 1RM for all pulling_strength axis calculations
- Add accuracy note: Brzycki is most accurate for 1-10 reps, less accurate beyond 10

**Source:** Brzycki M (1993), standard in strength training. Used by Consuegra Ch.8.

**Acceptance criteria:**
- [ ] Onboarding offers 1RM OR submaximal input option
- [ ] Brzycki formula correctly computes 1RM
- [ ] Estimated 1RM flows into pulling_strength axis
- [ ] Validation: reject >10 reps with warning about accuracy

---

### D68: Collect injury history in onboarding

**What:** Add injury history questions to onboarding flow.

**Questions to add:**
1. "Have you had any climbing-related injuries in the past 12 months?" (Yes/No)
2. If Yes: "Which body parts?" (multi-select: fingers, shoulders, elbows, wrists, knees, back, other)
3. If Yes: "Are you currently experiencing any pain?" (Yes/No)
4. If current pain: "Which areas?" (same multi-select)
5. If current pain: "Pain level during climbing?" (1-5 scale: mild discomfort → significant pain)

**Data model:**
```json
{
  "injury_history": {
    "has_recent_injury": true,
    "affected_areas": ["fingers", "shoulders"],
    "current_pain": true,
    "current_pain_areas": ["fingers"],
    "current_pain_level": 3
  }
}
```

**How it affects training:**
- If `current_pain` is true and `current_pain_level >= 3`: display warning "We recommend consulting a healthcare professional before starting a training program"
- If `affected_areas` includes "fingers": extra conservative on hangboard progression (start at lower intensity, slower % increases)
- If `affected_areas` includes "shoulders" or "elbows": ensure antagonist/prehab exercises are prioritized (D58, D60)
- Data feeds into load monitoring (Session 9, D69-D70)

**Source:** Quarmby et al. (2023): previous injury is the strongest predictor of future injury.

**Acceptance criteria:**
- [ ] Injury history questions in onboarding
- [ ] Data persisted in user profile
- [ ] Pain warning displays at level ≥ 3
- [ ] Injury areas influence exercise selection (conservative hangboard, prioritize prehab)

---

### D80: Hard age gates for youth <16 (CRITICAL SAFETY)

**What:** Enforce absolute training restrictions for users under 16.

**⚠️ NON-NEGOTIABLE — these are hard blocks, not warnings:**

| Training element | Under 16 | 16-18 |
|-----------------|----------|-------|
| Campus board (double dynos) | ❌ BLOCKED | ⚠️ Warning + prerequisites |
| Max-weight hangboard (MAW) | ❌ BLOCKED | ⚠️ Only if 2+ years systematic training |
| Min-edge hangboard (MED) | ❌ BLOCKED | ⚠️ Only if 2+ years systematic training |
| Hypergravity training (added weight) | ❌ BLOCKED | ⚠️ Warning |
| Full crimp grip instruction | ❌ BLOCKED | ⚠️ Discouraged |
| Campus board (controlled laddering, large holds) | ⚠️ Small amounts, 1-2×/week max | ✅ With prerequisites |

**Implementation:**
- Collect date of birth (or age) at onboarding
- Compute age; if <16: filter out blocked exercises from session resolver
- If 16-18: add prerequisite checks (experience ≥ 2 years for advanced hangboard)
- Display age-appropriate safety message at onboarding for <18 users
- If user age <16 and session resolver tries to assign a blocked exercise → skip it and log the gate

**Source:** Schöffl (2004-2024): 600% increase in epiphyseal fractures. 45% of youth injuries are growth plate. López-Rivera: <16 = contraindicated for advanced hangboard.

**Acceptance criteria:**
- [ ] Age collected at onboarding
- [ ] <16 users NEVER see MAW, MED, campus double dynos, or hypergravity exercises
- [ ] 16-18 users see warnings + prerequisites for advanced hangboard
- [ ] Tests verify blocked exercises cannot be assigned to <16 users
- [ ] Safety message displays for <18 users

---

### D81: Youth training cap — max 4 days/week

**What:** Limit session scheduling for users under 18 to maximum 4 days per week.

**Implementation:**
- In `generate_phase_week()`: if user age < 18, cap `sessions_per_week` at 4
- If user has set availability for more than 4 days: use best 4 (prioritize evening/long sessions, drop shortest)
- Display note: "For climbers under 18, we recommend a maximum of 4 training days per week to protect growing bodies."

**Source:** Hörst, Schöffl consensus. >10-12 hours/week during growth spurts = significantly elevated injury risk.

**Acceptance criteria:**
- [ ] <18 users get max 4 sessions/week regardless of availability
- [ ] Informational note displayed
- [ ] Weekly planner respects the cap

---

### D83: Adjustable recovery multiplier for 40+ users

**What:** Apply age-based recovery multiplier to rest intervals between similar session types.

**Default multipliers (user-adjustable):**

| Age range | Recovery multiplier |
|-----------|-------------------|
| < 40 | 1.0× (baseline) |
| 40-49 | 1.25× |
| 50-59 | 1.5× |
| 60+ | 1.75× |

**How it works:**
- If baseline recovery between hangboard sessions = 48h, a 45-year-old gets 48 × 1.25 = 60h minimum
- Apply to: hangboard sessions, max strength sessions, high-intensity bouldering
- Do NOT apply to: easy climbing, technique drills, mobility work
- User can adjust their multiplier in settings (range 1.0-2.5)

**Implementation:**
- Store `recovery_multiplier` in user profile (auto-set from age, user-adjustable)
- `generate_phase_week()` uses multiplier when checking minimum rest between hard sessions
- Settings page: slider for recovery multiplier with age-suggested default

**Source:** Physiological: HGH decreases with age, tendon adaptation slows, muscle repair takes longer.

**Acceptance criteria:**
- [ ] Recovery multiplier auto-set from age at onboarding
- [ ] Multiplier applied to hard session spacing
- [ ] User can override in settings
- [ ] <40 users unaffected (1.0× default)

---

## <a id="session-2"></a>SESSION 2: EXERCISE DATABASE — STRENGTH & HANGBOARD

**Decisions:** D10, D11, D12, D39, D50, D72
**Estimated effort:** Medium (exercise catalog additions + corrections)
**Dependencies:** Session 1 (age gates needed for D72 context)

---

### D10: Add overcoming isometric pull exercise

**Exercise definition:**
```json
{
  "id": "overcoming_iso_pull",
  "name": "Overcoming Isometric Pull",
  "category": "finger_strength",
  "type": "isometric",
  "description": "Pull maximally against an immovable hold/pin for 3-5 seconds. Recruits high-threshold motor units more effectively than yielding isometrics.",
  "protocol": {
    "hang_time_s": 5,
    "rest_between_reps_s": 120,
    "sets": 3,
    "reps_per_set": 3,
    "intensity": "maximum effort (cannot move the hold)"
  },
  "equipment_required": ["hangboard_with_pin_or_strap"],
  "grip_types": ["half_crimp", "open_hand"],
  "experience_minimum_years": 2,
  "contraindications": ["age_under_16", "current_finger_pain"],
  "phase_affinity": ["strength_power"],
  "source": "Nelson/C4HP methodology"
}
```

**Source:** Tyler Nelson (C4HP): overcoming isometrics potentially superior to yielding for neural recruitment and RFD development.

---

### D11: Add warm-up repeaters on large edge

**Exercise definition:**
```json
{
  "id": "warmup_repeaters_large",
  "name": "Warm-Up Repeaters (Large Edge)",
  "category": "finger_strength",
  "type": "repeater",
  "description": "Sub-maximal repeaters on large edge (25-35mm) as finger-specific warm-up before main hangboard work.",
  "protocol": {
    "hang_time_s": 7,
    "rest_time_s": 3,
    "reps_per_set": 6,
    "sets": 2,
    "rest_between_sets_s": 120,
    "edge_mm": "25-35 (large)",
    "intensity": "bodyweight only, should feel easy (EL 8-9 out of 10, where 10 = easiest)"
  },
  "equipment_required": ["hangboard"],
  "grip_types": ["open_hand"],
  "experience_minimum_years": 0,
  "phase_affinity": ["all"],
  "notes": "Always before MaxHangs or IntHangs. NOT a training set.",
  "source": "López-Rivera methodology, Lattice warm-up protocol"
}
```

---

### D12: Apply density_hangs corrections

**What:** Correct existing density hang exercise parameters based on Nelson/C4HP evidence.

**Corrections to apply to existing density hang exercises:**
- Duration: ensure 30-45s per hang (not shorter)
- Intensity: 40-75% MVC (moderate, not high)
- Rest: 60-120s between sets
- Purpose tag: update from "strength" to "structural/tendon density"
- Add note: "Targets tendon collagen synthesis via sustained moderate load. Not a max strength exercise."

**Source:** Nelson/C4HP: long-duration moderate isometrics create fascicle sliding effect → denser connective tissue.

---

### D39: Eccentric pull-ups for beginners (not resistance bands)

**Exercise definition:**
```json
{
  "id": "eccentric_pullup",
  "name": "Eccentric Pull-Up (Negative)",
  "category": "pulling_strength",
  "type": "eccentric",
  "description": "Jump or step to top position, lower yourself as slowly as possible (5-8 seconds). Builds pulling strength more effectively than band-assisted pull-ups for beginners.",
  "protocol": {
    "eccentric_duration_s": "5-8",
    "sets": 3,
    "reps_per_set": "3-5",
    "rest_between_sets_s": 180,
    "intensity": "bodyweight, controlled descent"
  },
  "equipment_required": ["pull_up_bar"],
  "experience_minimum_years": 0,
  "contraindications": ["current_shoulder_pain"],
  "phase_affinity": ["endurance_base", "strength_power"],
  "replaces": "band_assisted_pullup for beginners",
  "notes": "Eccentric loading builds high force levels efficiently and is superior to band assistance for strength development. Also beneficial for tendon strengthening (Consuegra Ch.8).",
  "source": "Consuegra Ch.8, Earp et al. 2016"
}
```

**Action:** If a `band_assisted_pullup` exercise exists, mark it as secondary option. `eccentric_pullup` becomes the default for beginners who cannot do full pull-ups.

---

### D50: Three repeater protocol options

**What:** Add three distinct repeater (IntHangs) protocols. Session resolver picks based on user level and phase.

**Protocol 1: López-Rivera Standard**
```json
{
  "id": "repeater_lopez",
  "name": "IntHangs — López-Rivera",
  "protocol": {
    "hang_time_s": 10,
    "rest_time_s": 5,
    "reps_per_set": 4,
    "sets": "4-5",
    "rest_between_sets_s": 60,
    "edge_mm": 18,
    "intensity": "60-80% MVC (add weight or reduce edge to reach)"
  },
  "target_adaptation": "strength-endurance, hypertrophy",
  "recommended_for": "intermediate+ (2+ years)",
  "source": "López-Rivera & González-Badillo 2018"
}
```

**Protocol 2: Anderson Standard**
```json
{
  "id": "repeater_anderson",
  "name": "Repeaters — Anderson",
  "protocol": {
    "hang_time_s": 7,
    "rest_time_s": 3,
    "reps_per_set": 6,
    "sets": "3-6",
    "rest_between_sets_s": 120,
    "edge_mm": 20,
    "intensity": "bodyweight or slight added weight"
  },
  "target_adaptation": "finger endurance, work capacity",
  "recommended_for": "beginner-intermediate",
  "source": "Anderson & Anderson, Rock Climber's Training Manual"
}
```

**Protocol 3: Hörst Pyramid**
```json
{
  "id": "repeater_horst",
  "name": "Repeaters — Hörst Pyramid",
  "protocol": {
    "sequence": "7:3 × 3 reps → 6:3 × 3 reps → 5:3 × 3 reps (decreasing hang time as fatigue builds)",
    "sets": "3 (one at each level)",
    "rest_between_sets_s": 180,
    "edge_mm": 20,
    "intensity": "bodyweight (adjust edge depth for difficulty)"
  },
  "target_adaptation": "finger endurance under fatigue",
  "recommended_for": "intermediate",
  "source": "Hörst, Training for Climbing"
}
```

**Selection logic:** Session resolver picks protocol based on:
- Beginner (<2yr): Anderson only
- Intermediate: any, biased toward Anderson or Hörst
- Advanced: any, biased toward López

---

### D72: Default to open-hand grip for all hangboard training

**What:** All hangboard exercises must default to open-hand or half-crimp grip. Full crimp is NEVER prescribed on hangboard.

**Implementation:**
- Every hangboard exercise's `grip_types` field: default to `["open_hand", "half_crimp"]`
- Add validation: no hangboard exercise may include `"full_crimp"` in `grip_types`
- Session resolver: when assigning grip, prefer `open_hand` unless user profile indicates half-crimp preference
- Add note to all hangboard exercises: "Use open-hand or half-crimp grip only. Full crimp is not recommended on hangboard due to pulley injury risk."

**Safety hierarchy:**
1. Open hand (safest, default)
2. Half crimp (acceptable)
3. Full crimp (❌ NEVER on hangboard)

**Source:** Miro et al. 2021: full crimp is the primary mechanism for pulley injuries. Quarmby 2023 SR confirms.

**Acceptance criteria:**
- [ ] All hangboard exercises default to open-hand
- [ ] No hangboard exercise has full_crimp in grip_types
- [ ] Validation test: reject exercises with full_crimp + hangboard

---

## <a id="session-3"></a>SESSION 3: EXERCISE DATABASE — CONDITIONING, INJURY PREVENTION & DRILLS

**Decisions:** D37, D43, D55, D56, D57, D60, D76
**Estimated effort:** Medium-Large (many exercises to add)
**Dependencies:** None (standalone data population)

---

### D37: Core activation drill catalog (8 exercises from Matros)

**Add these 8 exercises:**

1. **Tic Tac Toe** — Move hands between marked holds in a 3×3 grid while maintaining body tension. Core + coordination.
2. **Diagonal** — On steep wall, move opposite hand+foot simultaneously while stabilizing. Core + cross-body coordination.
3. **Get'em!** — Start matched on one hold, reach to touch distant holds while maintaining contact with feet. Dynamic core stability.
4. **Freeze** — Climb a problem, pausing 2-3 seconds in position after each move. No dynamic moves. Core + lock-off + technique.
5. **Feet Forwards** — Traverse with feet placed in front of hands (facing away from wall). Extreme core engagement.
6. **Hang Around** — Hang from holds in various body positions (L-sit, typewriter, etc.). Static core strength.
7. **Front Lever Progression** — Tuck → advanced tuck → single leg → full front lever. Progressive pulling + core.
8. **Plank Shoulder Taps** — High plank position, alternate tapping opposite shoulder. Anti-rotation core.

**Category:** `core_activation`
**Phase affinity:** All phases
**Source:** Matros et al. (2013) via Consuegra Ch.8

---

### D43: Campus board exercise progression (6 exercises)

**Add these 6 exercises in progression order:**

1. **Campus Touches** — Hang from large rung, touch higher rungs alternately. Entry-level contact strength. Prerequisites: 1+ pull-up, 1yr experience.
2. **Campus Laddering Up** — Move hands up rungs sequentially (1-2-3-4...). Basic campus movement. Prerequisites: 5+ pull-ups, 2yr experience.
3. **Campus Laddering Down** — Controlled descent rung by rung. Eccentric power. Prerequisites: can do laddering up.
4. **Campus 1-3-5** — Skip-rung ascending pattern. Power + coordination. Prerequisites: can ladder smoothly.
5. **Campus Bumps** — One hand moves up while other stays. Unilateral power. Prerequisites: can do 1-3-5.
6. **Campus Double Dynos** — Both hands release simultaneously. Maximum power. Prerequisites: can bump, 3+ years experience, age ≥16.

**All campus exercises require:**
- `experience_minimum_years: 2` (except touches: 1)
- `age_minimum: 16` (double dynos: ≥16 hard gate)
- `pull_up_1rm_ratio_minimum: 1.3` (can do weighted pull-ups)
- `contraindications: ["age_under_16", "current_finger_pain", "current_shoulder_pain"]`

**Auto-stop rules (D41):** If user reports pain, RPE > 8, or failed reps, session resolver should stop campus work and substitute with strength exercises.

**Source:** Consuegra Ch.8 (Matros progression), Hörst campus guidelines.

---

### D55: Exercise safety blacklist

**Create a blacklist of exercises the engine must NEVER prescribe:**

| Exercise | Reason | Safe Alternative |
|----------|--------|-----------------|
| Crunches / sit-ups | Spinal flexion under load; counterproductive for climbing posture | Planks, hollow body holds, dead bugs |
| Russian twist (weighted) | Spinal rotation under compression; disc injury risk | Pallof press, cable woodchop |
| Behind-neck pull-down | Shoulder impingement risk; no climbing specificity | Standard pull-up, lat pull-down |
| Behind-neck press | Shoulder impingement risk | Overhead press (front) |
| Upright row (narrow grip) | Shoulder impingement | Face pulls, lateral raises |
| Kipping pull-ups | Shoulder instability; not applicable to climbing | Strict pull-ups |
| Full crimp on hangboard | Primary pulley injury mechanism | Open hand, half crimp |

**Implementation:**
- Add `blacklisted: true` flag to any exercise matching these patterns
- Session resolver must never assign a blacklisted exercise
- If user creates a custom exercise matching blacklist patterns: display warning
- Validation test: blacklisted exercises cannot appear in any generated session

**Source:** Consuegra Ch.8 (exercise contraindications), Quarmby 2023 (injury mechanisms).

---

### D56: Nordic curl — mandatory injury prevention

**Exercise definition:**
```json
{
  "id": "nordic_curl",
  "name": "Nordic Hamstring Curl",
  "category": "injury_prevention",
  "type": "eccentric",
  "description": "Kneel, partner/anchor holds ankles. Lower torso forward as slowly as possible, resisting with hamstrings. THE most evidence-backed exercise for lower body injury prevention.",
  "protocol": {
    "sets": "2-3",
    "reps_per_set": "3-6",
    "tempo": "slow eccentric (3-5s descent)",
    "rest_between_sets_s": 90,
    "frequency": "2×/week"
  },
  "equipment_required": ["anchor_point_or_partner"],
  "mandatory": true,
  "phase_affinity": ["all"],
  "source": "Van Dyk et al. 2019: 51% lower injury rate. Consuegra Ch.8."
}
```

**Implementation:** Session resolver includes Nordic curls in at least one session per week for all users. Not optional.

---

### D57: Comprehensive lower body exercise catalog (10 exercises)

**Add these 10 exercises:**

1. **Goblet Squat** — General lower body strength. All levels.
2. **Bulgarian Split Squat** — Unilateral leg strength + balance. Intermediate+.
3. **Romanian Deadlift (RDL)** — Posterior chain. Intermediate+.
4. **Step-Ups (weighted)** — Functional unilateral strength. All levels.
5. **Pistol Squat Progression** — Tuck → assisted → full. Advanced balance + strength.
6. **Calf Raises (single leg)** — Ankle stability for heel hooks and slab.
7. **Hip Flexor Strengthening** — High steps, knee raises. Climbing-specific hip engagement.
8. **Glute Bridge / Hip Thrust** — Posterior chain activation, hip extension.
9. **Nordic Curl** — (see D56, cross-reference)
10. **Copenhagen Adductor** — Inner thigh strength for knee bars, stemming.

**Phase affinity:** Endurance Base and Strength phases. Reduced volume in PE and Performance.

---

### D60: Wrist extension protocol for epicondylitis prevention

**Exercise definition:**
```json
{
  "id": "wrist_extension_prehab",
  "name": "Wrist Extension (Epicondylitis Prevention)",
  "category": "injury_prevention",
  "type": "isolation",
  "description": "Wrist extension with light dumbbell or rubber bar. Prevents lateral epicondylitis (tennis elbow), common in climbers due to imbalanced forearm flexor/extensor ratio.",
  "protocol": {
    "sets": 3,
    "reps_per_set": 15,
    "tempo": "slow (2s up, 2s down)",
    "weight": "light (1-3kg)",
    "rest_between_sets_s": 60,
    "frequency": "3×/week, can be done daily"
  },
  "equipment_required": ["light_dumbbell_or_rubber_bar"],
  "phase_affinity": ["all"],
  "notes": "Climbing creates extreme forearm flexor:extensor imbalance. Extensor training is essential for elbow health.",
  "source": "Consuegra Ch.8, climbing physiotherapy consensus"
}
```

---

### D76: Populate drill catalog from coaching consensus

**Add these technique drills (from Topic 08):**

| Drill | Category | Description | Level |
|-------|----------|-------------|-------|
| Silent Feet | footwork | Climb 2-3 grades below OS, zero noise on foot placements. Retry if any sound. | All |
| Sticky Feet | footwork | Once foot touches hold, cannot adjust. Forces precise first placement. | All |
| Target Practice | footwork | Identify best spot on every foothold, stare 2-3s after placing. | All |
| Downclimbing | footwork | Downclimb all warm-up boulders/routes to starting holds. | All |
| Tennis Ball Hands | weight_transfer | Hold tennis ball in each hand, climb slab touching only wall. Forces footwork reliance. | Intermediate+ |
| No-Hands Slab | weight_transfer | Climb slab using only feet. Develops balance and trust. | All |
| Twist-Lock Drill | body_position | Practice twist-lock/drop-knee on moderate routes. Focus on hip rotation. | Intermediate+ |
| Flagging Practice | body_position | Climb routes using flagging on every move. Builds balance awareness. | Intermediate+ |
| Freeze | core_on_wall | Climb with 2-3s pause after each move. No dynamic moves. (Matros) | All |
| Timed Route Preview | route_reading | 2 min preview → predict crux → climb → compare prediction to reality. | All |
| Hover Hands | precision | Hover hand 2cm above target hold for 2s before grabbing. Prevents lunging. | All |

**Category field:** `technique_drill`
**Phase affinity:** All phases. Beginners: 30%+ of climbing time. Advanced: 10-15%.
**Source:** Hörst, Anderson, Matros (2013), Claassen, coaching consensus. Bechtel manual pending.

---

## <a id="session-4"></a>SESSION 4: SESSION PLANNER — WARM-UP

**Decisions:** D33, D36, D74
**Estimated effort:** Medium (new warm-up generation logic)
**Dependencies:** Session 3 (drills must exist in DB)

---

### D33: Full warm-up protocol generation

**What:** Generate a structured warm-up sequence for every session. This is not optional.

**Warm-up phases (in order):**

| Phase | Duration | Content | Intensity |
|-------|----------|---------|-----------|
| 1. Joint mobilization | 3-5 min | Wrist circles, shoulder circles, finger extension/flexion, hip circles, ankle rotations | None (movement only) |
| 2. General cardio | 3-5 min | Light jogging, jumping jacks, jump rope, or easy traversing | HR elevation, light sweat |
| 3. Range of motion | 3-5 min | Dynamic stretches: arm swings, leg swings, hip openers, thoracic rotation | Full ROM, no static holds |
| 4. Climbing activation | 5-10 min | Easy traversing (3-4 grades below OS), Silent Feet drill (D74), easy boulders | EL 9-10 (very easy) |
| 5. Specific preparation | 5-10 min | Warm-up repeaters on large edge (D11), movement patterns relevant to session | Building toward session intensity |

**Total warm-up: 15-30 minutes depending on session type.**

**Session-type adaptations:**
- Before hangboard: emphasize Phase 5 (warm-up repeaters mandatory)
- Before bouldering: longer Phase 4 (progressive difficulty boulders)
- Before lead/endurance: Phase 4 can be climbing-based (easy routes)
- Before conditioning-only: Phases 1-3 sufficient, Phase 4 optional

**Implementation:**
- `generate_warmup(session_type, user_profile)` → returns ordered list of warm-up exercises
- Always prepend to session plan
- Non-skippable in guided session mode (can be marked "done" but not removed)

**Source:** Fradkin et al. (2010): 79% of studies show warm-up improves performance. Consuegra Ch.8 structure.

---

### D36: PAP option for advanced users

**What:** Post-Activation Potentiation — optional advanced warm-up technique.

**Protocol:**
- After standard warm-up (D33), before main work:
- 1-2 sets of near-maximal effort (e.g., heavy pull-up, hard 3-move boulder)
- Wait 3-5 min
- Begin main work with enhanced neural activation

**Gate:** Only available if:
- User experience ≥ 3 years
- User level ≥ intermediate (pulling_strength axis ≥ 60)
- Session type = strength/power or bouldering

**Implementation:**
- Add as optional Phase 6 in warm-up generator
- Off by default; user can enable in settings
- Display: "PAP warm-up: 1-2 hard efforts → 3-5 min rest → main work"

**Source:** Consuegra Ch.8: PAP effective for power sessions in experienced athletes.

---

### D74: Silent feet mandatory in warm-up

**What:** `silent_feet` drill is automatically included in warm-up Phase 4 for ALL users.

**Implementation:**
- `generate_warmup()` always includes `silent_feet` in climbing activation phase
- Duration: minimum 5 minutes / 2-3 easy problems or routes
- Instruction text: "Climb 2-3 grades below your onsight level. Place every foot so silently that no sound is audible. If your foot makes noise, return it and retry. Focus on precision, not speed."

**Source:** Universal coaching consensus; low injury risk; develops proprioception.

---

## <a id="session-5"></a>SESSION 5: SESSION PLANNER — INTENSITY SYSTEM (EL)

**Decisions:** D34, D52, D14
**Estimated effort:** Large (core engine change — new intensity framework)
**Dependencies:** Session 2 (exercises must have intensity parameters)

---

### D34: Effort Level (EL) as primary intensity metric

**What:** Adopt Consuegra's Effort Level system as the engine's primary way to prescribe and track training intensity.

**The EL Scale:**

| EL | Description | Reps in Reserve (RIR) | ~%1RM |
|----|-------------|----------------------|-------|
| 1 | Maximum effort, could not do one more rep | 0 | 95-100% |
| 2 | Near-maximum, maybe 1 more rep | 1 | 90-95% |
| 3 | Very hard, 2 more possible | 2 | 85-90% |
| 4 | Hard but controlled, 3-4 more | 3-4 | 80-85% |
| 5 | Moderately hard, 5-6 more | 5-6 | 70-80% |
| 6 | Moderate, could do many more | 6-8 | 60-70% |
| 7 | Easy-moderate | 8+ | 50-60% |
| 8 | Easy | 10+ | 40-50% |
| 9 | Very easy | — | 30-40% |
| 10 | Minimal effort (warm-up) | — | <30% |

**Format notation:** EL X(Y) where X = effort level and Y = reps prescribed.
- Example: EL 3(5) = do 5 reps at effort level 3 (meaning you could do ~7 total)
- Example: EL 8(20) = do 20 reps at effort level 8 (high-rep, low intensity)

**Implementation:**
- Add `target_el` field to every exercise prescription in session plan
- Session resolver assigns EL based on phase and exercise purpose
- Feedback: user reports actual EL felt (1-10) → feeds adaptation system
- If user reports EL consistently lower than target (easier than intended): increase load next session
- If user reports EL consistently higher (harder): decrease load or flag overreaching

**Mapping to existing feedback:** The current `very_easy|easy|ok|hard|very_hard` maps roughly to:
- very_easy → EL 8-10
- easy → EL 6-7
- ok → EL 4-5
- hard → EL 2-3
- very_hard → EL 1

**Source:** Consuegra Ch.8, standard RPE/RIR framework adapted for climbing.

---

### D52: EL/%1RM prescription table by experience level

**What:** Define intensity ranges per experience level to prevent beginners from training too hard and advanced athletes from training too easy.

**Prescription ranges by level:**

| Exercise type | Beginner (<2yr) | Intermediate (2-5yr) | Advanced (5+yr) |
|--------------|----------------|---------------------|-----------------|
| Max strength (hangboard MAW) | N/A (not prescribed) | EL 2-3 / 85-95% 1RM | EL 1-3 / 90-100% 1RM |
| Strength-endurance (repeaters) | EL 5-6 / 60-70% | EL 4-5 / 70-80% | EL 3-5 / 75-85% |
| Hypertrophy (pulling) | EL 5-6 / 65-75% | EL 4-5 / 70-80% | EL 3-4 / 75-85% |
| Endurance (ARC/SubHangs) | EL 8-9 / <25% MVC | EL 7-8 / <30% MVC | EL 7-8 / <30% MVC |
| Power (campus, dynamic) | N/A (<2yr) or EL 2-3 | EL 1-3 | EL 1-2 |
| Conditioning (general) | EL 6-8 | EL 5-7 | EL 4-6 |

**Implementation:**
- Session resolver uses this table when computing target loads
- `user.experience_years` determines column
- EL assigned per exercise; load computed from EL → %1RM → actual kg

**Source:** Consuegra Ch.8, López-Rivera methodology.

---

### D14: López load monitoring rule

**What:** Monitor training response using the EL system to detect adaptation or stagnation.

**Rule:** Track the relationship between prescribed EL and reported EL over time:
- **Adapting well:** user reports same or lower EL for same absolute load (getting stronger) → progress load
- **Stagnating:** user reports same EL for same load over 3+ sessions → consider changing stimulus
- **Overreaching:** user reports higher EL for same or lower load → flag, consider deload

**Implementation:**
- After each session: compare `target_el` vs `reported_el` for key exercises
- Store trend data: `load_kg`, `target_el`, `reported_el`, `date`
- Adaptation algorithm: if `reported_el < target_el` for 2+ consecutive sessions → increase load by smallest increment
- Stagnation flag: if same EL ± 0.5 for same load over 3+ sessions → suggest program variation
- Overreaching flag: if `reported_el > target_el + 1` for 2+ sessions → flag and reduce load

**Source:** López-Rivera load monitoring principles; RPE-based autoregulation standard in strength training.

---

## <a id="session-6"></a>SESSION 6: SESSION PLANNER — HANGBOARD LOGIC

**Decisions:** D35, D49
**Estimated effort:** Medium (gate logic + session constraints)
**Dependencies:** Session 1 (age/experience data), Session 2 (exercises), Session 5 (EL system)

---

### D35: Gate hangboard protocols behind experience check

**What:** Advanced hangboard protocols require passing prerequisite gates.

**Gate matrix:**

| Protocol | Min Age | Min Experience | Min Strength | Additional |
|----------|---------|---------------|-------------|------------|
| Warm-up repeaters (D11) | Any | Any | Any | None |
| Anderson repeaters | Any | 6 months | Any | None |
| Hörst repeaters | 16+ | 1 year | Any | None |
| López IntHangs | 16+ | 2 years | Medium+ finger strength | None |
| MaxHangs MAW | 16+ | 2 years | finger_strength axis ≥ 50 | No current finger pain |
| MaxHangs MED | 16+ | 2 years | finger_strength axis ≥ 50 | No current finger pain |
| Density Hangs | 16+ | 1 year | Any | None |
| Overcoming Isometric | 16+ | 2 years | finger_strength axis ≥ 60 | No current finger pain |

**"Medium+ finger strength":** finger_strength axis score ≥ 40 in assessment profile.

**Implementation:**
- Session resolver checks gates before assigning hangboard exercises
- If gate fails: substitute with appropriate lower-level protocol
- If age gate fails: block entirely (D80)
- Log all gate checks for debugging

---

### D49: Don't combine MaxHangs and IntHangs in same mesocycle

**What:** Within a single mesocycle (phase), prescribe EITHER MaxHangs OR IntHangs, not both.

**Rationale:** López-Rivera (2018): both methods improve finger strength but via different mechanisms. Combining them in one phase dilutes the stimulus and increases injury risk.

**Logic:**
- In Strength & Power phase → prefer MaxHangs (neural adaptation focus)
- In Endurance Base phase → prefer IntHangs/repeaters (endurance focus)
- In Power Endurance phase → prefer IntHangs (strength-endurance)
- In Performance phase → either maintenance-dose MaxHangs OR no hangboard
- In Deload → no hangboard or very light repeaters only

**Implementation:**
- `generate_phase_week()` picks ONE hangboard method for the entire phase
- Method stored as phase parameter: `hangboard_method: "max_hangs" | "int_hangs" | "none"`
- Session resolver only assigns exercises matching the phase's chosen method
- Alternation between macrocycles: if last macrocycle used MaxHangs in S&P phase, this one can use IntHangs

---

## <a id="session-7"></a>SESSION 7: SESSION PLANNER — ENDURANCE & INTERVALS

**Decisions:** D47, D48, D53
**Estimated effort:** Medium (replace 4×4 logic, add recovery exercises)
**Dependencies:** Session 3 (exercises in DB)

---

### D47: Replace 4×4 with varied-intensity intervals (SUPERSEDES D16)

**What:** Remove traditional 4×4 bouldering as the default power-endurance method. Replace with Consuegra's varied-intensity interval approach.

**Problem with 4×4:** Climbing 4 boulders at near-max difficulty with minimal rest drives total forearm vascular occlusion → glycolytic overload → counterproductive training stimulus (Consuegra Ch.8, Valenzuela evidence).

**Replacement: Varied-Intensity Intervals**

**Protocol:**
```
Round structure: 3-4 problems per round
- Problem 1: Hard (near onsight level), EL 3-4
- Problem 2: Moderate (2 grades below OS), EL 5-6
- Problem 3: Easy (3-4 grades below OS), EL 7-8
- [Optional] Problem 4: Easy traverse/downclimb, EL 8-9

Rest between problems: 30-60s (just chalk up and transition)
Rest between rounds: 3-5 min (full recovery)
Total rounds: 3-5
```

**Why this works:** The intensity variation prevents sustained vascular occlusion. The easy problems between hard ones allow partial reperfusion, maintaining aerobic contribution and avoiding excessive lactate accumulation.

**Implementation:**
- Remove or deprecate `4x4_bouldering` session template
- Create `varied_intensity_intervals` session template
- Session resolver auto-selects appropriate grades based on user's onsight level
- PE phase: 2-3 sessions/week of this type

**Source:** Consuegra Ch.8; Valenzuela studies on vascular occlusion.

---

### D48: Active recovery — easy traversing between attempts

**What:** Add coaching cue for active recovery between hard climbing attempts.

**Evidence:** Valenzuela et al. (2015): easy traversing > walking > sitting for between-attempt recovery in climbing.

**Implementation:**
- In bouldering and strength sessions: after each hard attempt, session guide suggests "Easy traverse for 2-3 minutes between attempts"
- In guided session mode: display recovery cue with timer
- Add `active_recovery_traverse` as an exercise that can be inserted between hard sets

**Exercise definition:**
```json
{
  "id": "active_recovery_traverse",
  "name": "Active Recovery Traverse",
  "category": "recovery",
  "description": "Easy traversing at very low intensity between hard attempts. Promotes blood flow and reperfusion without additional fatigue.",
  "protocol": {
    "duration_min": "2-3",
    "intensity": "EL 9-10 (minimal effort, easy movement)"
  }
}
```

---

### D53: Active recovery training progression (3-step)

**What:** Progressive on-wall recovery training, separate from between-attempt recovery.

**3-step progression:**

| Step | Duration | Description | Phase |
|------|----------|-------------|-------|
| 1 | 2 min | Easy traverse at EL 9 between rest periods on moderate route | Base |
| 2 | 4 min | Continuous easy climbing with deliberate rest positions (shake, G-Tox) | Base-Build |
| 3 | 8+ min | Sustained moderate climbing with planned rests, mimicking route strategy | Build-PE |

**Implementation:** Add as training exercises. Session resolver assigns step based on user's current endurance level and phase.

---

## <a id="session-8"></a>SESSION 8: SESSION PLANNER — CONDITIONING, TECHNIQUE & RATIO

**Decisions:** D51, D54, D58, D59, D73, D78
**Estimated effort:** Medium (ratio logic + exercise assignment rules)
**Dependencies:** Session 3 (exercises), Session 5 (EL system)

---

### D51: Scale climbing vs conditioning ratio by level

**What:** The proportion of climbing vs off-wall conditioning in each session varies by experience level.

**Ratio table:**

| Level | Climbing (on-wall) | Conditioning (off-wall) |
|-------|-------------------|----------------------|
| Beginner (<2yr) | 70% | 30% |
| Intermediate (2-5yr) | 60% | 40% |
| Advanced (5+yr) | 50% | 50% |

**Clarification (from T6 resolution):** Technique drills (D73) count as "climbing" since they're on-wall.

**Implementation:**
- `resolve_session()` allocates session time according to ratio
- `user.experience_years` determines ratio
- Climbing time includes: routes, boulders, technique drills, traversing
- Conditioning time includes: hangboard, pull-ups, core, prehab, lower body, mobility

---

### D54: Core — 12-15s intense planks, not long holds

**What:** Replace long-duration planks (60s+) with short, intense variations.

**Rationale:** Consuegra Ch.8: 12-15s of maximal plank activation develops more functional core strength for climbing than 60+ seconds of moderate planks. Climbing requires brief, intense core engagement during individual moves.

**Implementation:**
- Update all plank exercises: set duration to 12-15s per hold
- Increase intensity: add weight, use single arm/leg variations, RKC plank
- Sets: 3-5 × 12-15s with 30-60s rest
- Remove any plank prescriptions > 30s from session resolver

---

### D58: Postural correction exercises (anti-climber's-back)

**What:** Include antagonist exercises in every program to counter "climber's back" (kyphosis + lordosis from overactive climbing muscles).

**Exercises to include:**
1. **Face pulls** — external rotation + rear delts. 3×15.
2. **Band pull-aparts** — mid-back activation. 3×15.
3. **YTW raises** — rotator cuff + lower trapezius. 2×10 each position.
4. **Thoracic extension over foam roller** — mobility. 2 min.
5. **Doorway chest stretch** — pec length. 30s × 3 each side.

**Implementation:**
- At least 2 of these exercises in every conditioning session
- Priority increases for users who report shoulder/back issues (D68 injury history)
- Phase affinity: all phases, never skipped even in Performance

**Source:** Förster et al. (2009): "climber's back" documented. Consuegra Ch.8 antagonist protocols.

---

### D59: Hypertonic/inhibited muscle reference table

**What:** Reference data for the session resolver to correctly pair muscle groups.

| Hypertonic (tight/overactive) | Inhibited (weak/underactive) | Correction |
|------------------------------|-----------------------------|-----------| 
| Forearm flexors | Forearm extensors | Wrist extensions (D60) |
| Biceps, lats | Lower/mid trapezius, rear deltoids | Face pulls, YTW, band pull-aparts |
| Pectorals | Rhomboids, serratus anterior | Chest stretch, rows, push-up plus |
| Hip flexors | Glutes | Hip flexor stretch, glute bridge |
| Internal rotators | External rotators | Band external rotation |

**Implementation:** Session resolver uses this table to ensure every conditioning session includes at least one inhibited-muscle exercise. Not a user-facing table — internal logic reference.

---

### D73: Technique drills in every phase (beginners 30%+)

**What:** Ensure technique drill time is allocated proportionally to experience level.

**Allocation:**

| Level | Technique drill % of climbing time | Example (60 min climbing) |
|-------|-----------------------------------|--------------------------|
| Beginner (<2yr) | ≥30% | ≥18 min drills + ≤42 min climbing for grade |
| Intermediate (2-5yr) | 15-25% | 9-15 min drills |
| Advanced (5+yr) | 10-15% | 6-9 min drills |

**Implementation:**
- `resolve_session()` allocates technique drills within the climbing portion
- Drill selection: rotate through drill catalog (D76), prioritize user's weak areas
- Beginner default drills: Silent Feet, Downclimbing, Freeze
- Advanced default drills: Timed Route Preview, Flagging Practice, Hover Hands

---

### D78: Process goals for daily session cues

**What:** Each session includes one process-focused cue relevant to the session type.

**Examples by session type:**

| Session type | Process cue example |
|-------------|-------------------|
| Bouldering | "Focus on reading each problem fully before starting" |
| Lead/routes | "Count your breaths at every rest position" |
| Hangboard | "Focus on shoulder engagement — active hang, not passive" |
| Technique | "Today's focus: place each foot perfectly on the first try" |
| Conditioning | "Quality over quantity — stop the set when form breaks" |

**Implementation:**
- Add `process_cue` field to session plan output
- Curated list of ~30 cues, tagged by session type
- Rotate daily (don't repeat within 2 weeks)
- Display prominently at session start in guided mode

**Source:** SDT (D77): process focus builds competence. Hardy et al. (1996) goal-setting theory.

---

## <a id="session-9"></a>SESSION 9: PERIODIZATION & LOAD MANAGEMENT

**Decisions:** D19, D20, D21, D44, D45, D69, D70, D71
**Estimated effort:** Large (phase constraints + load tracking system)
**Dependencies:** Session 5 (EL system), Session 8 (ratio)

---

### D19: Simplified linear periodization for beginners

**What:** Beginners (< 2 years experience) get a simplified linear macrocycle.

**Simplified structure:**

| Phase | Duration | Focus |
|-------|----------|-------|
| Base (General) | 6-8 weeks | Volume climbing, technique drills (30%+), ARC, general conditioning, movement variety |
| Build (Specific) | 4-6 weeks | IntHangs (repeaters), moderate climbing intensity, targeted conditioning |
| Peak | 2-3 weeks | Climbing at onsight level, project attempts, reduced conditioning |
| Deload | 1 week | Rest, mobility, easy climbing |

**Key differences from standard model:**
- Longer Base phase (more technique and volume)
- No MaxHangs in Build phase (repeaters only)
- No campus board
- Higher climbing:conditioning ratio (70:30, per D51)
- Phase transitions based on time, not performance metrics (simpler logic)

**Implementation:**
- If `user.experience_years < 2`: use simplified macrocycle template
- Fewer phase types, longer durations, conservative intensity

---

### D20: Overreach + taper before Performance phase

**What:** The last 1-2 weeks of the PE/Build phase should include planned functional overreaching, followed by a taper into Performance phase.

**Protocol:**
1. **Overreach week:** increase volume by 10-15% above normal (one week only)
2. **Taper (1-2 weeks):**
   - Reduce volume 40-60% (Mujika & Padilla 2003)
   - Maintain intensity (do NOT reduce intensity)
   - Reduce frequency by ≤20% (e.g., 5 sessions → 4)
   - First reduce session count, then reduce session duration

**Implementation:**
- In macrocycle generation: insert overreach microcycle before Performance phase
- Taper: reduce volume parameter progressively over 1-2 weeks
- Performance phase starts at reduced volume, maintained intensity

**Source:** Mujika & Padilla (2003): taper produces 2-6% performance improvement. Consuegra Ch.10.

---

### D21: Minimum phase duration (UPDATED)

**What:** Enforce minimum phase durations to ensure physiological adaptation.

| Phase | Minimum Duration | Rationale |
|-------|-----------------|-----------|
| Base/Endurance | 6 weeks | Mitochondrial biogenesis requires ≥6 weeks (Mujika 2012, D44) |
| Build/Strength | 3 weeks | Neural adaptation: 2-4 weeks for meaningful gains |
| Peak/Performance | 2 weeks | Supercompensation timeline |
| Deload | 1 week (3-7 days) | Recovery period |

**Implementation:**
- `generate_macrocycle()`: enforce these minimums
- If total macrocycle duration doesn't allow all minimums: compress Peak first, then Build, NEVER compress Base below 6 weeks
- Adaptive extension: phases CAN be extended (up to +2 weeks) if adaptation is incomplete

---

### D44: ARC/endurance phase minimum 6 weeks

**What:** ARC (Aerobic Restoration and Capillarity) training requires a minimum of 6 weeks in the Base phase.

**Source:** Mujika (2012): mitochondrial biogenesis in skeletal muscle requires sustained aerobic stimulus. <6 weeks = incomplete capillary adaptation.

**Implementation:** Enforce in D21 (Base ≥ 6 weeks). The Base phase is where ARC lives.

---

### D45: Enforce <25% MVC ceiling for ARC

**What:** ARC training must stay below 25% MVC (or 1-2 on pump scale).

**Rationale:** Above 25% MVC, intramuscular pressure occludes blood flow → switches from aerobic to anaerobic metabolism → defeats the purpose of ARC.

**Implementation:**
- ARC exercises: set `max_intensity = 0.25` (25% MVC)
- In EL terms: EL 8-9 (very easy, minimal effort)
- Session resolver: if prescribing ARC, ensure grade is well below onsight level
- Coaching cue: "If you feel any pump at all, you're going too hard. Drop the grade."

**Source:** Barnes (physiology), Byström, Sjøgaard, López-Rivera (2014c).

---

### D69: ACWR-based load monitoring

**What:** Track Acute:Chronic Workload Ratio to flag injury risk from load spikes.

**Metrics:**
- Session load (AU) = Duration (min) × Session RPE (1-10)
- Acute load = rolling 7-day sum of session loads
- Chronic load = rolling 28-day average of weekly loads
- ACWR = Acute / Chronic

**Zones:**
| ACWR | Zone | Action |
|------|------|--------|
| < 0.8 | Under-training | Inform user: "Training load is below your usual level" |
| 0.8 - 1.3 | Sweet spot | No action — safe progressive loading |
| 1.3 - 1.5 | Caution | Warning: "Training load is increasing quickly. Monitor how you feel." |
| > 1.5 | Danger | Alert: "Significant load spike detected. Consider reducing volume this week." |

**Implementation:**
- After each session: compute session_load, update rolling averages
- Display ACWR on dashboard (simple color indicator: green/yellow/red)
- If ACWR > 1.3: display warning in next session briefing
- If ACWR > 1.5: suggest deload or reduced session

**Source:** Gabbett (2016), Hulin et al. (2015).

---

### D70: Overtraining detection heuristics

**What:** Flag potential overreaching/overtraining from user data patterns.

**Flags (any 2 of these = warning):**

| Flag | Detection | Data Source |
|------|-----------|-------------|
| Performance decline | 2+ consecutive test results declining | Assessment tests |
| Elevated RPE | Session RPE consistently +1.5 above expected for same workload | Session feedback |
| Incomplete sessions | >30% of sessions incomplete over 2 weeks | Session completion |
| Persistent fatigue | User reports "very_hard" on exercises that were previously "ok" | Exercise feedback |
| ACWR spike | ACWR > 1.5 (from D69) | Load tracking |

**Actions when flagged:**
1. Display: "Your recent data suggests you may be overreaching. This is normal if temporary, but persistent patterns need attention."
2. Suggest: reduce volume by 20-30% for 1 week
3. If pattern persists > 2 weeks: suggest full deload week
4. Never diagnose OTS — that requires medical professional

**Source:** Meeusen et al. (2013) overtraining continuum. Hooper's Beta, Firestone (2022).

---

### D71: Enforce <10% weekly volume increase

**What:** Limit week-over-week training volume increases to <10%.

**Implementation:**
- After `generate_phase_week()`: compare total planned session load (sum of duration × expected RPE) to previous week
- If increase > 10%: reduce by removing lowest-priority exercises or reducing sets
- Exception: first week after deload may increase >10% to return to pre-deload levels
- Display: "Weekly volume change: +X%" in weekly summary

**Source:** General sports medicine guideline. Gabbett (2016): rapid load spikes are the primary injury risk factor.

---

## <a id="session-10"></a>SESSION 10: COACHING CUES, SAFETY & UX

**Decisions:** D17, D29, D30, D41, D64, D65, D66, D67, D75, D77, D79
**Estimated effort:** Medium (mostly content/messaging, some logic)
**Dependencies:** All previous sessions (this is the UI/messaging layer)

---

### D17: G-Tox technique cue in rest prompts

**What:** When the session guide shows rest periods during climbing, include G-Tox instruction.

**Cue text:** "G-Tox: alternate arms overhead and at your side every 5 seconds while resting. This uses gravity to assist venous return and can improve recovery during rests."

**When to show:** During rest intervals in route climbing sessions, endurance sessions, and PE intervals.

**Source:** Coaching consensus; gravity-assisted blood flow during on-wall rests.

---

### D29: Post-climb mental reflection question

**What:** After climbing sessions, prompt a brief mental reflection.

**Questions (rotate):**
1. "What was one move or decision you're proud of today?"
2. "Was there a moment where you hesitated? What happened?"
3. "Did you notice any patterns in where you fell or struggled?"
4. "Rate your focus today 1-5. What affected it?"
5. "What would you do differently if you climbed that route again?"

**Implementation:**
- Add `reflection_prompt` to post-session feedback flow
- One question per session (rotate through list)
- Response is free text, stored in session log
- Optional — user can skip

---

### D30: Fall practice drill in exercise catalog

**Exercise definition:**
```json
{
  "id": "fall_practice",
  "name": "Intentional Fall Practice",
  "category": "technique_drill",
  "type": "mental_training",
  "description": "Practice taking intentional falls on lead to build confidence and reduce fear response. Start with short falls (1-2 clips above last clip) and progressively increase distance.",
  "protocol": {
    "progression": [
      "Step 1: Fall from 30cm above last clip (rope tight)",
      "Step 2: Fall from 1m above last clip",
      "Step 3: Fall from 2m above last clip (normal lead fall)",
      "Step 4: Fall from unexpected positions (partner calls 'fall')"
    ],
    "reps": "3-5 falls per step",
    "frequency": "1×/week during Build and PE phases"
  },
  "equipment_required": ["lead_rope", "belayer"],
  "contraindications": ["solo_climbing", "bouldering_only"],
  "notes": "Always with a trusted belayer. Focus on falling posture: push away from wall, feet facing wall, knees slightly bent. NEVER practice on terrain with ledge-fall risk."
}
```

**Source:** Garrido-Palomino (2023) RCT: intentional fall practice reduces fear of falling significantly.

---

### D41: Campus board prerequisites and auto-stop rules

**What:** Campus board exercises require prerequisites (D43 already defines these). Add auto-stop behavior.

**Auto-stop triggers:**
- User reports pain during campus exercise → immediately stop campus work for session
- User reports RPE > 8 on campus exercise → stop and suggest substitution
- User fails >50% of prescribed reps → stop campus, substitute power exercises

**Implementation:**
- In guided session mode: after each campus set, ask "Any pain? Rate difficulty 1-10"
- If pain = yes OR difficulty > 8: stop campus, replace with pull-up variations or power bouldering
- Log auto-stop events for load monitoring

---

### D64: RED-S awareness guardrails (CRITICAL SAFETY)

**What:** Hard safety rules to prevent the engine from encouraging disordered eating or weight manipulation.

**Rules:**
1. The engine NEVER suggests weight loss, calorie restriction, or body composition changes
2. The engine NEVER comments on body weight beyond using it for ratio calculations
3. The engine NEVER displays body fat percentage or BMI
4. If user shows pattern of: declining performance + increased training volume + reports of fatigue → display: "Your performance pattern may indicate insufficient energy availability. We strongly recommend consulting a sports dietitian."
5. Educational content uses positive framing: "fuel your training" not "watch your weight"
6. No exercises categorized as "fat burning" or "weight loss"

**Implementation:**
- Audit all user-facing strings: remove any reference to weight loss, body fat goals, or calorie targets
- Add RED-S detection pattern to overtraining heuristics (D70)
- Validation test: no session plan or coaching message contains weight-loss language

**Source:** Joubert (2020, 2022): documented eating disorder prevalence in climbing. IOC RED-S framework.

---

### D65: Sleep education in recovery guidance

**What:** Include sleep recommendations in post-session and rest-day guidance.

**Content:**
- Adults: minimum 7 hours sleep recommended (IOC consensus)
- Youth (<18): 8-10 hours (elevated injury risk with <8h)
- Post-session tip: "Sleep is your #1 recovery tool. Growth hormone surges during deep sleep — this is when your body repairs and strengthens."
- Rest day tip: "Prioritize sleep quality: consistent schedule, dark room, limit screens 1h before bed."

**Implementation:**
- Add sleep tip to post-session summary (rotate through 5-6 tips)
- Add sleep tip to rest day content
- If user is <18: emphasize 8-10h recommendation

**Source:** Charest & Grandner (2020). IOC consensus.

---

### D66: "Fuel your training" educational messaging

**What:** Positive nutrition messaging in onboarding and phase transitions.

**Messages (at phase transitions):**
- Base phase start: "You're entering a high-volume phase. Remember: more training volume means your body needs more fuel. Eat enough to support your training."
- Build phase start: "Strength training increases protein needs. Aim for protein-rich meals around your training sessions."
- General: "Climbing performance comes from training well AND recovering well. Recovery starts with eating enough."

**Implementation:**
- Add `phase_nutrition_tip` to phase transition messaging
- Onboarding: display general nutrition awareness message
- Never include caloric targets, specific diets, or weight goals

---

### D67: Collagen + vitamin C educational mention

**What:** When relevant, mention collagen + vitamin C as the supplement with most climbing-relevant evidence.

**Content:** "The supplement with the strongest evidence for climbing-relevant tendon health is hydrolysed collagen (10-15g) combined with vitamin C, taken 30-60 minutes before loading exercises. This is educational information, not a prescription — consult a sports dietitian for personalized supplement advice."

**When to show:** Only when user asks about supplements OR when displaying injury prevention/prehab content.

**Implementation:**
- Add to educational content library
- Never proactively push supplements
- Always include "food first" caveat and dietitian recommendation

**Source:** Shaw et al. (2017), Lattice review (2023).

---

### D75: Structured route preview protocol

**What:** Upgrade the simple route preview prompt (D28) to a structured multi-step protocol.

**Protocol (display before lead climbing sessions):**

```
ROUTE PREVIEW CHECKLIST:
1. SCAN: Look at the entire route bottom to top (30 seconds)
2. REST SPOTS: Identify every rest position (good holds, stances)
3. CRUX: Locate the hardest section — plan your body position and clips
4. CLIPPING: Plan where you'll clip from (stable positions, not mid-crux)
5. VISUALISE: Close your eyes, climb the route mentally move by move
6. DESCENT: Plan your descent route (lower-off, top-rope, or walk-off)
```

**Implementation:**
- Display in guided session mode before lead climbing exercises
- Checklist format with expandable tips for each step
- After climbing: "How did reality compare to your preview?" (connects to D29 reflection)

**Source:** Seifert (2017): preview quality directly improves movement fluency. Medernach (2024).

---

### D77: Coach voice follows SDT principles

**What:** All engine-generated messages follow Self-Determination Theory:
1. **Autonomy:** "Here's what I recommend and why" — never "You must do this"
2. **Competence:** Celebrate progress, contextualize setbacks
3. **Relatedness:** Acknowledge climbing as a shared experience

**Implementation guidelines (for all user-facing copy):**
- Use "consider" and "I recommend" instead of "you must" or "you need to"
- Include brief "why" with every prescription (e.g., "3×5 pull-ups to build the pulling strength for your 7b+ goal")
- After tests: always show progress vs previous, highlight improvements
- After setbacks: "It's normal for performance to fluctuate, especially in week X of this phase"
- Allow modification: user can always swap exercises or adjust session

---

### D79: Coach embodies "train better, not more"

**What:** The Coach personality consistently reinforces quality over quantity.

**Specific behaviors:**
- Never celebrate streak-based metrics (e.g., "10 days in a row!")
- DO celebrate rest day compliance: "Great job taking your rest day — recovery is training too"
- Frame deloads positively: "Deload week: this is when your body consolidates all the gains from the last phase"
- If user trains more than prescribed: "I noticed you've been adding extra sessions. Remember: adaptation happens during recovery, not during training."
- Never shame incomplete sessions: "Partial sessions still count. You showed up and did good work."

**Source:** Consuegra Ch.8: "Don't train more: train better." SDT framework.

---

## <a id="safety-rules"></a>CROSS-SESSION SAFETY RULES

These rules apply ACROSS all sessions and must never be violated:

| Rule | Priority | Source |
|------|----------|--------|
| Never suggest weight loss or comment on body composition | CRITICAL | D01, D64 |
| Block campus/max hangboard/hypergravity for <16 | CRITICAL | D80 |
| Max 4 training days/week for <18 | CRITICAL | D81 |
| Never prescribe full crimp on hangboard | HIGH | D72 |
| Exercise safety blacklist enforced | HIGH | D55 |
| Open-hand grip default for all hangboard | HIGH | D72 |
| <10% weekly volume increase | HIGH | D71 |
| ACWR alerts at >1.3 | MEDIUM | D69 |
| Warm-up mandatory for every session | MEDIUM | D33 |
| Nordic curl in every weekly plan | MEDIUM | D56 |

---

## <a id="glossary"></a>GLOSSARY

| Term | Definition |
|------|-----------|
| ARC | Aerobic Restoration and Capillarity — low-intensity sustained climbing for aerobic base |
| ACWR | Acute:Chronic Workload Ratio — load spike indicator |
| BW | Body weight |
| EL | Effort Level — 1-10 scale where 1 = maximum effort, 10 = minimal effort |
| FOR | Functional Overreaching — short-term performance dip, recovers in days |
| IntHangs | Intermittent Dead Hangs — repeater-style hangboard protocol |
| MAW | Maximum Added Weight — max hang protocol with added load |
| MaxHangs | General term for high-intensity hangboard (MAW or MED) |
| MED | Minimum Edge Depth — max hang protocol on smallest edge at bodyweight |
| MVC | Maximum Voluntary Contraction |
| NFOR | Non-Functional Overreaching — weeks to recover |
| OTS | Overtraining Syndrome — months to recover |
| PAP | Post-Activation Potentiation — neural priming technique |
| PE | Power Endurance |
| RED-S | Relative Energy Deficiency in Sport |
| RFD | Rate of Force Development — how fast you generate force |
| RPE | Rating of Perceived Exertion |
| SDT | Self-Determination Theory |
| SubHangs | Submaximal Dead Hangs — long-duration moderate-intensity hangboard |

---

*End of Claude Code Mega-Brief — 57 v1 decisions across 10 implementation sessions.*
*Total references: ~260 across knowledge base.*
*Ready for sequential implementation.*
