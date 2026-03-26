# climb-agent — Engine Audit Snapshot

> Generated: 2026-03-26
> Script: `scripts/extract_audit_snapshot.py`
> Purpose: Comprehensive engine state for literature audit

---

# Section 1: MACROCYCLE STRUCTURE

## Phase Definitions

```
PHASE_ORDER = ("base", "strength_power", "power_endurance", "performance", "deload")
```

| Phase | Display Name | Energy System | Intensity Cap |
|-------|-------------|---------------|---------------|
| base | Endurance Base | aerobic | medium |
| strength_power | Strength & Power | anaerobic_alactic | max |
| power_endurance | Power Endurance | anaerobic_lactic | high |
| performance | Performance | specific | max |
| deload | Deload | recovery | low |

## Base Durations (weeks)

| Phase | Lead | Boulder |
|-------|------|---------|
| base | 4 | 2 |
| strength_power | 3 | 4 |
| power_endurance | 2 | 1 |
| performance | 2 | 2 |
| deload | 1 | 1 |

_MIN_TOTAL_WEEKS = 9

## Phase Floor Logic

- Lead: floor = 2 weeks per non-deload phase; deload = 1 week
- Boulder: floor = 1 week per non-deload phase; deload = 1 week
- Weakness adjustments: if weakest axis score < 50, extend relevant phase +1wk, shrink paired phase -1wk

### Weakness Adjustments

| Weak Axis | Extend Phase | Shrink Phase |
|-----------|-------------|-------------|
| power_endurance | power_endurance | strength_power |
| endurance | base | strength_power |
| finger_strength | strength_power | base |
| pulling_strength | strength_power | base |
| technique | base | performance |

## Domain Weight Tables

### Lead Discipline

| Phase | finger_strength | pulling_strength | power_endurance | volume_climbing | technique | core_prehab |
|-------|-----|-----|-----|-----|-----|-----|
| base | 0.2 | 0.15 | 0.15 | 0.25 | 0.2 | 0.05 |
| strength_power | 0.35 | 0.25 | 0.1 | 0.1 | 0.1 | 0.1 |
| power_endurance | 0.15 | 0.1 | 0.35 | 0.15 | 0.15 | 0.1 |
| performance | 0.1 | 0.05 | 0.2 | 0.25 | 0.25 | 0.15 |
| deload | 0.05 | 0.05 | 0.05 | 0.1 | 0.05 | 0.1 |

### Boulder Discipline

| Phase | finger_strength | pulling_strength | power_endurance | volume_climbing | technique | core_prehab |
|-------|-----|-----|-----|-----|-----|-----|
| base | 0.2 | 0.15 | 0.05 | 0.35 | 0.2 | 0.05 |
| strength_power | 0.4 | 0.25 | 0.1 | 0.1 | 0.1 | 0.05 |
| power_endurance | 0.2 | 0.15 | 0.3 | 0.2 | 0.1 | 0.05 |
| performance | 0.15 | 0.1 | 0.15 | 0.3 | 0.25 | 0.05 |
| deload | 0.05 | 0.05 | 0.05 | 0.1 | 0.05 | 0.1 |

## Domain Weight Adjustment (per user profile)

- Score < 50 on axis → +0.05 to mapped weight domain
- Score > 75 on axis → -0.03 from mapped weight domain (min 0.02)
- Renormalize to sum = 1.0
- Axis → domain: finger_strength→finger_strength, pulling_strength→pulling_strength, power_endurance→power_endurance, technique→technique, endurance→volume_climbing

## Session Pools per Phase

### Lead Discipline

**base:**
- Primary: boulder_circuit_gym, endurance_aerobic_gym, finger_maintenance_home, finger_maintenance_gym, prehab_maintenance, technique_focus_gym
- Available: complementary_conditioning, flexibility_full, finger_aerobic_base, finger_endurance_short, handstand_practice, route_endurance_gym

**strength_power:**
- Primary: finger_strength_home, limit_boulder_gym, power_contact_gym, prehab_maintenance, strength_long
- Available: complementary_conditioning, finger_endurance_short, finger_maintenance_gym, flexibility_full, handstand_practice, technique_focus_gym

**power_endurance:**
- Primary: power_endurance_gym, prehab_maintenance
- Available: endurance_aerobic_gym, flexibility_full, finger_strength_home, handstand_practice, route_endurance_gym, technique_focus_gym

**performance:**
- Primary: limit_boulder_gym, prehab_maintenance, technique_focus_gym
- Available: boulder_circuit_gym, finger_strength_home, flexibility_full, handstand_practice, power_contact_gym, power_endurance_gym, route_endurance_gym

**deload:**
- Primary: flexibility_full, prehab_maintenance, regeneration_easy, yoga_recovery
- Available: deload_recovery, easy_climbing_deload, finger_aerobic_base

### Boulder Discipline

**base:**
- Primary: boulder_circuit_gym, technique_focus_gym, finger_maintenance_home, prehab_maintenance
- Available: flexibility_full, handstand_practice, complementary_conditioning, core_training

**strength_power:**
- Primary: power_contact_gym, limit_boulder_gym, strength_long, finger_strength_home, prehab_maintenance
- Available: technique_focus_gym, flexibility_full, handstand_practice, complementary_conditioning, core_training

**power_endurance:**
- Primary: boulder_circuit_gym, prehab_maintenance
- Available: technique_focus_gym, finger_strength_home, flexibility_full, core_training

**performance:**
- Primary: technique_focus_gym, limit_boulder_gym, prehab_maintenance
- Available: power_contact_gym, boulder_circuit_gym, finger_strength_home, flexibility_full, handstand_practice, core_training

**deload:**
- Primary: regeneration_easy, flexibility_full, yoga_recovery, prehab_maintenance
- Available: easy_climbing_deload, deload_recovery, finger_aerobic_base

## Deload Structure

- Deload session pool: regeneration_easy, flexibility_full, yoga_recovery, prehab_maintenance, easy_climbing_deload
- Hard cap during deload: 0 hard days, 0 finger days
- Deload factor: 0.5
- Max sessions/week during deload: 5

## Phase Transition Logic

- Each phase has explicit start_week and end_week bounds
- Week counter increments per phase duration
- `should_extend_phase()`: if last 2 weeks feedback = hard/very_hard → extend +1wk (max +2)
- `should_trigger_adaptive_deload()`: if 5+ consecutive very_hard days → trigger recovery deload
- Pre-trip deload: 5 days before trip, no hard/max sessions

## DUP Implementation

- Domain weights per phase encode the undulating emphasis
- Session pools rotate cyclically (primary_idx % len(pool)) for week-to-week variety
- Max per week limits (default 1) prevent session repetition within a week
- Recovery multiplier (D83) extends spacing between hard/finger days
- `generate_macrocycle()` supports `from_phase` for partial regeneration

---

# Section 2: PLANNER LOGIC (planner_v2.py)

## 3-Pass Algorithm Overview

```
PASS 1:   Place primary sessions (hard=True OR climbing=True)
          → gym-first day order, respects all constraints
PASS 1.5: Climbing fallback for empty gym days
          → technique_focus_gym / easy_climbing_deload if pool lacks gym_boulder
PASS 2:   Fill remaining empty days with complementary sessions
          → up to target_training_days_per_week
PASS 2.2: Fill extra slots on multi-slot days (non-hard only)
          → B121: if total < session_target, add to existing session days
PASS 2.5: Ensure PE phase has finger maintenance
          → finger_maintenance_home/gym if none placed
PASS 3:   Inject test sessions (last week of base/strength_power)
          → replace complementary sessions, respect finger/hard spacing
```

## Constraint System

### PERMANENT constraints (burn uses if hit, session skipped permanently):
- Anti-repetition: session_count >= max_per_week
- Hard day cap: hard_days >= effective_hard_cap

### TEMPORARY constraints (defer, don't burn uses):
- Finger gap: meta.finger AND offset - last_finger_offset <= finger_gap_days
- Hard gap: meta.hard AND offset - last_hard_offset <= hard_gap_days
- Other-activity reduction: day has other_activity AND meta.hard
- Pre-trip deload: date in pretrip_set AND (meta.hard OR intensity=max)
- Preferred equipment deferral: B160d, defer to later day with better gear

## Day Assignment Logic

1. Score each day: gym_preferred=+100, gym_available=+50, home=+1, evening_slot=+10
2. Sort by (-score, offset) → gym days first, stable weekday order within group
3. Youth cap (D81): if age < 18 → max 4 days/week
4. If available_days > target_days → keep only top-scoring days

## Slot Selection

- Primary sessions prefer: evening > morning > lunch
- Complementary sessions prefer: lunch > morning > evening

## Gym Selection

1. If slot has specific gym_id → use it
2. If default_gym_id → use it
3. If required_equipment → pick first gym by priority with matching equipment
4. Else → first gym by priority

## Test Scheduling (Pass 3)

- Triggers: inject_tests=True OR last week of base/strength_power phase
- TEST_FRESHNESS_DAYS = 42 (6-week minimum between retests)
- Test schedule (ordered):
  1. Finger test: test_lp_max_5s (loading_pin) or test_max_hang_5s (hangboard) — required
  2. Repeater test: test_lp_repeater (loading_pin) or test_repeater_7_3 (hangboard) — required
  3. Pulling test: test_max_weighted_pullup (if baseline or BW pullups ≥15) or test_pullup_bw — optional
- Tests bypass phase intensity cap
- Respect finger/hard spacing, hard cap
- Replace complementary sessions on existing days

## Cross-Week Continuity

- prev_week_plan seeds hard_day_offsets and finger_day_offsets from last week (offsets -7 to -1)
- Ensures spacing constraints are enforced across week boundaries

## Recovery Multiplier (D83)

- hard_gap_days = ceil(1 × recovery_multiplier)
- finger_gap_days = ceil(1 × recovery_multiplier)
- Default multiplier = 1.0
- Age 40-49: 1.25, Age 50-59: 1.5, Age 60+: 1.75

---

# Section 3: SESSION CATALOG

Total sessions: 34

| session_id | name | location | domains | intensity | climbing | duration_min |
|-----------|------|----------|---------|-----------|----------|-------------|
| boulder_circuit_gym | Boulder Circuit (Gym — Volume & Movement Quality) | ? |  | ? | N | ? |
| complementary_conditioning | Complementary Conditioning (Carries + Crawls + TGU) | ? |  | ? | N | ? |
| core_training | Core Training (Climbing-Specific) | ? |  | ? | N | ? |
| deload_recovery | Deload Recovery (Home) | ? |  | ? | N | ? |
| easy_climbing_deload | Easy Climbing — Deload | gym |  | ? | N | 60 |
| endurance_aerobic_gym | Aerobic Endurance (Gym) | ? |  | ? | N | ? |
| finger_aerobic_base | Finger Aerobic Base (Home) | ? |  | ? | N | ? |
| finger_endurance_short | Finger Endurance (Short) | ? |  | ? | N | ? |
| finger_maintenance_gym | Finger Maintenance (Gym — Submaximal Repeaters + Easy Climbing) | ? |  | ? | N | ? |
| finger_maintenance_home | Finger Maintenance (Home — Submaximal Repeaters) | ? |  | ? | N | ? |
| finger_strength_home | Finger Strength (Home — Hangboard Only) | ? |  | ? | N | ? |
| flexibility_full | Full Flexibility Session (Rest Day) | ? |  | ? | N | ? |
| handstand_practice | Handstand Practice (Skill Session) | ? |  | ? | N | ? |
| heavy_conditioning_gym | Heavy Conditioning Gym | ? |  | ? | N | ? |
| legs_strength | Legs Strength (Unilateral Focus) | ? |  | ? | N | ? |
| limit_boulder_gym | Limit Bouldering (Projecting) | ? |  | ? | N | ? |
| lower_body_gym | Lower Body Strength (Gym) | ? |  | ? | N | ? |
| power_contact_gym | Power & Contact Strength (Gym) | ? |  | ? | N | ? |
| power_endurance_gym | Power Endurance (Gym — Lead Focus) | ? |  | ? | N | ? |
| prehab_maintenance | Prehab Maintenance (Daily) | ? |  | ? | N | ? |
| pulling_strength_gym | Pulling Strength (Gym) | ? |  | ? | N | ? |
| regeneration_easy | Regeneration (Easy Climbing + Stretch) | ? |  | ? | N | ? |
| route_endurance_gym | Route Endurance (Gym — Lead Aerobic Base) | ? |  | ? | N | ? |
| strength_long | Strength Day (Long Session) – Finger Max Strength Focus | ? |  | ? | N | ? |
| technique_focus_gym | Technique Focus (Gym — Drills + Intentional Climbing) | ? |  | ? | N | ? |
| test_lp_max_5s | Test LP Max 7s | ? |  | ? | N | ? |
| test_lp_repeater | Test Session — Loading Pin Repeater 7/3 | ? |  | ? | N | ? |
| test_max_hang_5s | Test Max Hang 7s | ? |  | ? | N | ? |
| test_max_hang_7s | Test Max Hang 7s | ? |  | ? | N | ? |
| test_max_weighted_pullup | Test Session — Weighted Pullup 2RM | ? |  | ? | N | ? |
| test_pullup_bw | Pull-Up Assessment (Bodyweight) | ? |  | ? | N | ? |
| test_repeater_7_3 | Test Session — Repeater 7/3 Baseline | ? |  | ? | N | ? |
| upper_body_weights | Upper Body Antagonist (Push) | ? |  | ? | N | ? |
| yoga_recovery | Yoga / Recovery Flow (Rest Day) | ? |  | ? | N | ? |

## SESSION_META (planner_v2.py)

| Session | Hard | Finger | Intensity | Climbing | Location | Equipment | max/wk |
|---------|------|--------|-----------|----------|----------|-----------|--------|
| boulder_circuit_gym |  |  | medium | Y | gym | gym_boulder | 2 |
| complementary_conditioning |  |  | medium |  | home, gym |  | 1 |
| core_training |  |  | medium |  | gym, home |  | 3 |
| deload_recovery |  |  | low |  | home, gym |  | 2 |
| easy_climbing_deload |  |  | low | Y | gym | gym_boulder | 1 |
| endurance_aerobic_gym |  |  | medium | Y | gym | gym_routes | 2 |
| finger_aerobic_base |  | Y | low |  | home | hangboard | 1 |
| finger_endurance_short |  | Y | medium |  | home | hangboard | 1 |
| finger_maintenance_gym |  | Y | medium | Y | gym | hangboard | 1 |
| finger_maintenance_home |  | Y | medium | Y | home | hangboard | 1 |
| finger_strength_home | Y | Y | high |  | home | hangboard | 1 |
| flexibility_full |  |  | low |  | home, gym |  | 2 |
| handstand_practice |  |  | medium |  | home, gym |  | 1 |
| heavy_conditioning_gym |  |  | medium |  | gym | dumbbell | 1 |
| legs_strength |  |  | medium |  | gym, home |  | 2 |
| limit_boulder_gym | Y |  | max | Y | gym | gym_boulder | 1 |
| lower_body_gym |  |  | medium |  | gym | dumbbell | 1 |
| power_contact_gym | Y |  | max | Y | gym | gym_boulder | 1 |
| power_endurance_gym | Y |  | high | Y | gym | gym_boulder (pref: gym_routes) | 1 |
| prehab_maintenance |  |  | low |  | home, gym |  | 1 |
| pulling_strength_gym | Y |  | high |  | gym | pullup_bar | 1 |
| regeneration_easy |  |  | low |  | home, gym, outdoor |  | 1 |
| route_endurance_gym |  |  | medium | Y | gym | gym_routes | 1 |
| strength_long | Y | Y | max | Y | gym, home | hangboard | 1 |
| technique_focus_gym |  |  | medium | Y | gym | gym_boulder | 1 |
| test_lp_max_5s | Y | Y | high |  | home, gym | loading_pin | 1 |
| test_lp_repeater | Y | Y | high |  | home, gym | loading_pin | 1 |
| test_max_hang_5s | Y | Y | high |  | home, gym | hangboard | 1 |
| test_max_weighted_pullup | Y |  | high |  | home, gym | pullup_bar | 1 |
| test_pullup_bw |  |  | medium |  | home, gym | pullup_bar | 1 |
| test_repeater_7_3 | Y | Y | high |  | home, gym | hangboard | 1 |
| upper_body_weights |  |  | medium |  | gym, home |  | 2 |
| yoga_recovery |  |  | low |  | home |  | 2 |

## _ALWAYS_SUGGESTIBLE

```python
_ALWAYS_SUGGESTIBLE = {"core_training"}
```

---

# Section 4: TEMPLATE CATALOG

Total templates: 26

### antagonist_prehab
**Name:** Antagonist & Prehab (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |

### cooldown_stretch
**Name:** Cooldown Stretching (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### core_short
**Name:** Core Short (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |

### core_standard
**Name:** Core Standard (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |

### deload_recovery
**Name:** Deload / Recovery

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### finger_aerobic_endurance
**Name:** Finger Aerobic Endurance (Base)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### finger_max_strength
**Name:** Finger Max Strength

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### finger_max_strength_test
**Name:** Finger Max Strength (Test Protocol)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### finger_max_strength_test_lp
**Name:** Finger Max Strength — Loading Pin Test

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### finger_strength_endurance
**Name:** Finger Strength-Endurance

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### finger_strength_endurance_test
**Name:** Finger Strength-Endurance (Test Protocol)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### finger_strength_endurance_test_lp
**Name:** Finger Strength-Endurance — Loading Pin Test

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### general_strength_accessories
**Name:** General Strength Accessories

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |

### general_warmup
**Name:** General Warm-up (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### gym_aerobic_endurance
**Name:** Gym Aerobic Endurance (ARC / Volume)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |

### gym_power_bouldering
**Name:** Gym Power (Limit Bouldering)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### gym_power_endurance
**Name:** Gym Power-Endurance (Intervals)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |

### gym_technique_boulder
**Name:** Gym Technique (Boulder Drills)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |

### pulling_endurance
**Name:** Pulling Endurance (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |

### pulling_strength
**Name:** Pulling Strength (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |

### pulling_strength_compound
**Name:** Pulling Strength Compound (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### pulling_strength_test
**Name:** Pulling Strength (Test Protocol — 2RM)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |

### pulling_strength_test_bw
**Name:** Pull-Up Assessment (Bodyweight Only)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |

### warmup_climbing
**Name:** Climbing Warm-up (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

### warmup_recovery
**Name:** Recovery Warm-up (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |

### warmup_strength
**Name:** Strength Warm-up (Module)

| Block | Roles | Domains | Count |
|-------|-------|---------|-------|
| ? |  |  | ? |
| ? |  |  | ? |
| ? |  |  | ? |

---

# Section 5: EXERCISE CATALOG

Total exercises: 179

## Category Counts

| Category | Count |
|----------|-------|
| complementary | 5 |
| conditioning | 8 |
| core | 12 |
| endurance | 14 |
| flexibility | 17 |
| main_strength | 41 |
| mobility | 1 |
| power_endurance | 5 |
| prehab | 17 |
| strength_accessory | 22 |
| technique | 20 |
| test | 4 |
| test_measurement | 4 |
| warmup_general | 3 |
| warmup_specific | 6 |

## complementary (5 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| freestanding_handstand_practice | Freestanding Handstand Practice | handstand_skill | medium | handstand |  |  | shoulder_sensitive, wrist_sensitive | handstand_freestanding | home, gym |  |
| handstand_pushup_wall | Handstand Push-up (Wall) | strength_general, handstand_skill | high | push |  |  | shoulder_sensitive, wrist_sensitive | handstand_hspu | home, gym |  |
| handstand_shoulder_taps | Handstand Shoulder Taps (Wall) | handstand_skill, core | high | handstand |  |  | shoulder_sensitive, wrist_sensitive | handstand_holds | home, gym |  |
| wall_handstand_hold | Wall Handstand Hold (Belly-to-Wall) | handstand_skill, strength_general | medium | handstand |  |  | shoulder_sensitive, wrist_sensitive | handstand_holds | home, gym |  |
| wall_walk_up | Wall Walk-up | handstand_skill | medium | handstand |  |  | shoulder_sensitive, wrist_sensitive | handstand_walkup | home, gym |  |

## conditioning (8 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| bear_crawl | Bear Crawl | core, mobility | low | locomotion |  |  |  | conditioning_crawls | home, gym, outdoor |  |
| farmers_carry | Farmer's Carry | strength_general, core | medium | carry | weight |  |  | conditioning_carries | home, gym |  |
| hip_flexor_strengthening | Hip Flexor Strengthening | strength_general | low | compression |  |  |  | core_hip_flexor | home, gym |  |
| jump_rope | Jump Rope (Cardio Conditioning) | aerobic_capacity | low | locomotion |  |  |  | warmup_pulse_raise | home, gym, outdoor |  |
| nordic_curl | Nordic Hamstring Curl | strength_general | medium | hinge |  |  |  | lower_body_posterior | home, gym |  |
| single_leg_calf_raise | Single Leg Calf Raise | strength_general | low | squat |  |  |  | lower_body_calf | home, gym |  |
| step_ups | Step-Ups (Weighted) | strength_general | medium | squat |  |  |  | lower_body_quad | home, gym |  |
| turkish_getup | Turkish Get-up | strength_general, core | medium | rotation | weight |  | shoulder_sensitive | conditioning_tgu | home, gym |  |

## core (12 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| ab_wheel_rollout | Ab Wheel Rollout | core | medium | anti_extension |  |  |  | core_anti_extension | home, gym |  |
| copenhagen_plank | Copenhagen Plank | core | medium | anti_rotation | bench |  | shoulder_sensitive | core_anti_rotation | home, gym |  |
| core_hollow_hold | Hollow Body Hold | core | medium | anti_extension |  |  |  | core_anti_extension | home, gym, outdoor |  |
| core_l_sit | L-Sit (Floor) | core | medium | anti_extension |  |  | shoulder_sensitive | core_compression | home, gym |  |
| dead_bug | Dead Bug | core | low | anti_extension |  |  |  | core_anti_extension | home, gym, outdoor |  |
| front_lever_tuck | Front Lever (Tuck Progression) | core | high | anti_extension | pullup_bar |  | shoulder_sensitive | core_front_lever | home, gym |  |
| hanging_leg_raise | Hanging Leg Raise | core | medium | compression | pullup_bar |  |  | core_compression | home, gym |  |
| pallof_press | Pallof Press (Anti-Rotation) | core | medium | anti_rotation | resistance_band |  |  | core_anti_rotation | home, gym |  |
| plank | Plank | core | low | anti_extension |  |  |  | core_anti_extension | home, gym, outdoor |  |
| side_plank | Side Plank | core | medium | anti_lateral_flexion |  |  |  | core_anti_lateral_flexion | home, gym, outdoor |  |
| toes_to_bar | Toes to Bar | core | high | compression | pullup_bar |  |  | core_compression | home, gym |  |
| windshield_wipers | Windshield Wipers (Hanging) | core | high | rotation | pullup_bar |  |  | core_rotation | home, gym |  |

## endurance (14 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| aerobic_pyramid_intervals | Aerobic Pyramid Intervals (1-2-3-4-3-2-1) | aerobic_capacity | low | climbing_intervals |  |  |  | gym_threshold | gym, outdoor |  |
| arc_easy_traverse | ARC Easy Traverse (Continuous) | aerobic_capacity | low | climbing_continuous |  |  |  | gym_arc | gym |  |
| arc_training | ARC Training (Continuous Low Intensity) | aerobic_capacity | low | climbing_continuous |  |  |  | gym_arc | gym |  |
| arc_training_progressive | ARC Training Progressive | aerobic_capacity, regeneration | low | climbing_continuous |  |  |  | gym_arc | gym, outdoor |  |
| continuity_climbing | Continuity Climbing (Ultra-Easy Volume) | regeneration | low | climbing_continuous |  |  |  | gym_continuity | gym |  |
| easy_route_laps | Easy Route Laps (Recovery) | regeneration | low | climbing_routes | gym_routes |  |  | gym_easy_laps | gym |  |
| gym_arc_easy_volume | ARC / Easy Volume (Aerobic Endurance) | aerobic_capacity | low | climbing_continuous |  |  |  | gym_arc | gym |  |
| hangboard_moving_hangs | Hangboard Moving Hangs (HMH) | finger_strength_endurance, aerobic_capacity | low | repeater_hang | hangboard |  |  | hangboard_endurance | home, gym |  |
| one_on_one_off_intervals | 1-on / 1-off Aerobic Intervals (Lattice) | aerobic_capacity | low | climbing_intervals |  |  |  | gym_threshold | gym, outdoor |  |
| regeneration_climbing | Regeneration Climbing | regeneration | very_low | climbing_continuous |  |  |  | gym_arc | gym, outdoor |  |
| repeater_15_15 | Repeater Hang 15/15 (IntHangs) | finger_strength_endurance | medium | repeater_hang | hangboard |  | elbow_sensitive | finger_repeaters | home, gym |  |
| route_redpoint_attempt | Route Redpoint Attempt | climbing_routes | high | climbing_routes | gym_routes |  |  | route_redpoint | gym, outdoor |  |
| threshold_climbing | Threshold Climbing (Sustained Sub-Onsight) | power_endurance | medium | climbing_continuous | gym_routes |  |  | gym_threshold | gym |  |
| threshold_long_intervals | Threshold Long Intervals (2:1) | aerobic_capacity | low | climbing_intervals |  |  |  | gym_threshold | gym, outdoor |  |

## flexibility (17 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| active_hip_mobility | Active Hip Mobility (CARs/High Step/Frog) | flexibility, mobility | low | flexibility_active |  |  |  | flexibility_hips_active | home, gym, outdoor |  |
| cooldown_deep_squat_hold | Deep Squat Hold (Cooldown) | flexibility, mobility | low | flexibility_passive |  |  |  | cooldown_hips | home, gym, outdoor |  |
| cooldown_forearm_wrist_stretch | Forearm & Wrist Stretch (Cooldown) | prehab_wrist, flexibility | low | flexibility_passive |  |  |  | cooldown_forearm | home, gym, outdoor |  |
| cooldown_hamstring_fold | Standing Forward Fold (Cooldown) | flexibility | low | flexibility_passive |  |  |  | cooldown_hamstrings | home, gym, outdoor |  |
| cooldown_hip_frog | Frog Stretch (Cooldown) | flexibility, mobility | low | flexibility_passive |  |  |  | cooldown_hips | home, gym, outdoor |  |
| cooldown_hip_pigeon | Pigeon Stretch (Cooldown) | flexibility, mobility | low | flexibility_passive |  |  |  | cooldown_hips | home, gym, outdoor |  |
| cooldown_shoulder_chest | Shoulder & Chest Stretch (Cooldown) | flexibility, mobility | low | flexibility_passive |  |  |  | cooldown_shoulders | home, gym, outdoor |  |
| cooldown_spinal_twist | Supine Spinal Twist (Cooldown) | flexibility, mobility | low | flexibility_passive |  |  |  | cooldown_spine | home, gym, outdoor |  |
| flexibility_active_leg_raise | Active Straight Leg Raise | flexibility | low | flexibility_active |  |  |  | flexibility_hamstrings | home, gym |  |
| flexibility_cossack_squat | Cossack Squat (Active Flexibility) | flexibility, mobility | low | flexibility_active |  |  |  | flexibility_hips | home, gym |  |
| flexibility_ninety_ninety | 90/90 Hip Switch (Active Flexibility) | flexibility, mobility | low | flexibility_active |  |  |  | flexibility_hips | home, gym |  |
| forearm_stretches | Forearm Stretches (Wrist Extension/Flexion) | prehab_wrist, flexibility | low | wrist_extension |  |  |  | flexibility_forearms | home, gym, outdoor |  |
| full_body_stretch_flow | Full Body Stretch Flow (Yin-inspired) | flexibility | low | flexibility_passive |  |  |  | flexibility_full_body | home, gym, outdoor |  |
| hip_flexor_couch_stretch | Hip Flexor Couch Stretch (Psoas / Quad) | flexibility | low | flexibility_passive |  |  | knee_injury | flexibility_hip | gym, home, outdoor |  |
| hip_opener_flow | Hip Opener Flow (Frog/Pigeon/90-90) | flexibility, mobility | low | flexibility_passive |  |  |  | flexibility_hips | home, gym, outdoor |  |
| lat_overhead_stretch | Lat and Overhead Flexibility Stretch | flexibility | low | flexibility_passive |  |  |  | flexibility_shoulder | gym, home, outdoor |  |
| shoulder_stretch_flow | Shoulder Stretch Flow (Pec/Cross-body/Sleeper) | flexibility, mobility | low | flexibility_passive |  |  |  | flexibility_shoulders | home, gym, outdoor |  |

## main_strength (41 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| archer_pullup | Archer Pull-up | strength_general | high | pull_vertical | pullup_bar |  | shoulder_sensitive | pullup_variants | home, gym |  |
| board_limit_boulders | Board Limit Boulders (Kilter/Moon/Tension) | power | max | climbing_limit_boulder |  |  | elbow_sensitive, finger_sensitive, shoulder_sensitive | board_limit_boulders | gym |  |
| campus_bumps | Campus Bumps (Touch-and-Go) | contact_strength | high | campus_ladder | campus_board |  | age_under_16, elbow_sensitive, finger_injury, finger_sensitive, shoulder_sensitive | campus_bumps | gym |  |
| campus_double_dyno | Campus Double Dyno | contact_strength, power | max | campus_ladder | campus_board |  | age_under_16, elbow_sensitive, finger_injury, finger_sensitive, shoulder_sensitive | campus_dynos | gym |  |
| campus_laddering_down | Campus Laddering Down | contact_strength | high | campus_ladder | campus_board |  | age_under_16, finger_injury, finger_sensitive, shoulder_sensitive | campus_ladders | gym |  |
| campus_laddering_feet_off | Campus Laddering (Feet Off) | contact_strength | high | campus_ladder | campus_board |  | age_under_16, elbow_sensitive, finger_injury, finger_sensitive, shoulder_sensitive | campus_ladders | gym |  |
| campus_laddering_feet_on | Campus Laddering (Feet On Wall) | contact_strength | high | campus_ladder | campus_board |  | age_under_16, finger_injury, shoulder_sensitive | campus_ladders | gym |  |
| campus_max_ladders | Campus Max Ladders | contact_strength, power | high | campus_ladder | campus_board |  | age_under_16, elbow_sensitive, finger_injury, finger_sensitive, shoulder_sensitive | campus_ladders | gym |  |
| campus_switches | Campus Board Switches | contact_strength | high | campus_ladder | campus_board |  | age_under_16, finger_injury, shoulder_sensitive | campus_switches | gym |  |
| campus_touches | Campus Board Touches | contact_strength, power | high | campus_ladder | campus_board |  | age_under_16, finger_injury, shoulder_sensitive | campus_ladders | gym |  |
| density_hangs | Density Hangs (Tyler Nelson) | finger_strength_endurance | high | isometric_hang | hangboard |  | elbow_sensitive | finger_density_hangs | home, gym |  |
| dip | Dip | strength_general | high | push |  |  | shoulder_sensitive | dip_variants | home, gym, outdoor |  |
| eccentric_pullup | Eccentric Pull-Up (Negative) | strength_general | medium | pull_vertical | pullup_bar |  | shoulder_sensitive | pulling_vertical | home, gym |  |
| four_by_four_bouldering | 4x4 Bouldering (Power-Endurance) | power_endurance, anaerobic_capacity | high | climbing_intervals |  |  |  | gym_4x4 | gym, home |  |
| grip_transitions_half_to_open | Grip Transitions (Half-Crimp to Open-Hand) | finger_strength | high | grip_transition | hangboard |  | elbow_sensitive | finger_transition | home, gym |  |
| horst_7_53 | Hörst 7-53 Protocol | finger_strength, finger_max_strength | high | isometric_hang | hangboard |  | elbow_sensitive | finger_max_hang | home, gym |  |
| l_sit_pullup | L-Sit Pull-up | strength_general, core | high | pull_vertical | pullup_bar |  | shoulder_sensitive | pullup_variants | home, gym |  |
| limit_bouldering | Limit Bouldering (Deadpoint/Latching Focus) | power, technique_boulder | max | climbing_limit_boulder |  |  | elbow_sensitive, finger_sensitive, shoulder_sensitive | gym_limit_bouldering | gym, home |  |
| linked_boulders | Linked Boulders (No Pause) | power_endurance | high | climbing_intervals |  |  |  | gym_linked_boulders | gym |  |
| lock_off_isometric | Lock-off Isometric (Multi-Angle) | strength_general | high | pull_vertical | pullup_bar |  | elbow_sensitive | pullup_lock_off | home, gym |  |
| lopez_subhangs | López Submaximal Hangs | finger_strength_endurance | medium | isometric_hang | hangboard |  |  | finger_submaximal_hang | home, gym |  |
| lp_density_lifts | Loading Pin Density Lifts | finger_strength_endurance | medium | isometric_hang | loading_pin |  | elbow_sensitive | finger_density_hangs | home, gym | Y |
| lp_max_lift_10s | Loading Pin Max Lift (10s) | finger_strength | high | isometric_hang | loading_pin |  | finger_sensitive | finger_max_hang | home, gym | Y |
| lp_max_lift_5s | Loading Pin Max Lift (5s) | finger_strength, finger_max_strength | max | isometric_hang | loading_pin |  | finger_sensitive | finger_max_hang | home, gym | Y |
| lp_max_lift_7s | Loading Pin Max Lift (7s) | finger_strength, finger_max_strength | max | isometric_hang | loading_pin |  | finger_sensitive | finger_max_hang | home, gym | Y |
| lp_short_lifts | Loading Pin Short Lifts (Recruitment) | finger_strength, finger_max_strength | max | isometric_hang | loading_pin |  | finger_sensitive | finger_max_hang | home, gym | Y |
| max_hang_10s | Max Hang 10s (Hypertrophy) | finger_strength | high | isometric_hang | hangboard |  | finger_sensitive | finger_max_hang | home, gym |  |
| max_hang_5s | Max Hang (5s) | finger_strength, finger_max_strength | max | isometric_hang | hangboard |  | elbow_sensitive, finger_sensitive | finger_max_hang | home, gym |  |
| max_hang_7s | Max Hang (7s) | finger_strength, finger_max_strength | max | isometric_hang | hangboard |  | elbow_sensitive, finger_sensitive | finger_max_hang | home, gym |  |
| max_hang_ladder | Bechtel 3-6-9 Ladder | finger_strength, finger_max_strength | max | isometric_hang | hangboard |  | elbow_sensitive, finger_sensitive | finger_max_hang | home, gym |  |
| min_edge_hang | Minimum Edge Hang (MED) | finger_strength, finger_max_strength | max | isometric_hang | hangboard |  | elbow_sensitive, finger_sensitive | finger_min_edge | home, gym |  |
| one_arm_hang_assisted | One-Arm Hang (Assisted) | finger_max_strength | max | isometric_hang | hangboard, band |  | elbow_sensitive, finger_sensitive | finger_max_hang | home, gym |  |
| one_arm_pullup_assisted | One-Arm Pull-up (Assisted) | strength_general | max | pull_vertical | pullup_bar, band |  | shoulder_sensitive, elbow_sensitive | pullup_one_arm | home, gym |  |
| pangullich_ladders_easy | Campus Board Ladders (Controlled) | finger_strength | high | pull_vertical | campus_board |  | age_under_16, elbow_sensitive, finger_injury, shoulder_sensitive | campus_ladders | home, gym |  |
| pinch_block_training | Pinch Block Training | finger_strength | high | isometric_hang | pinch_block |  | finger_sensitive | finger_pinch | home, gym |  |
| power_pullups_explosive | Explosive Pull-ups (Power) | power | high | pull_vertical | pullup_bar |  | shoulder_sensitive | pullup_variants | home, gym |  |
| pullup | Pull-up | strength_general | high | pull_vertical | pullup_bar |  | shoulder_sensitive | pullup_variants | home, gym, outdoor |  |
| repeater_hang_7_3 | Hangboard Repeaters 7/3 (Strength-Endurance) | finger_strength_endurance | high | repeater_hang | hangboard |  | elbow_sensitive | finger_repeaters | home, gym |  |
| route_intervals | Route Intervals (Timed Rest) | power_endurance | high | climbing_intervals | gym_routes |  |  | gym_route_intervals | gym |  |
| typewriter_pullup | Typewriter Pull-up | strength_general | high | pull_vertical | pullup_bar |  | shoulder_sensitive | pullup_variants | home, gym |  |
| weighted_pullup | Weighted Pull-up | strength_general | high | pull_vertical | pullup_bar, weight |  | shoulder_sensitive | pullup_variants | home, gym |  |

## mobility (1 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| mobility_thoracic_shoulders_flow | Thoracic & Shoulder Mobility Flow | mobility | low | mobility_shoulders |  |  |  | mobility_shoulders_thoracic | home, gym, outdoor |  |

## power_endurance (5 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| campus_sprint_endurance | Campus Sprint Endurance | contact_strength, anaerobic_capacity | high | campus_ladder | campus_board |  | age_under_16, finger_injury, shoulder_sensitive | campus_endurance | gym |  |
| emom_bouldering | EMOM Bouldering | power_endurance, anaerobic_capacity | high | climbing_intervals |  |  |  | gym_emom | gym, outdoor, home |  |
| linked_boulders_circuit | Linked Boulder Circuit | power_endurance, anaerobic_capacity | high | climbing_intervals |  |  |  | gym_linked_boulders | gym, outdoor, home |  |
| otm_bouldering | OTM Bouldering (Every 2 Minutes) | power_endurance, anaerobic_capacity | high | climbing_intervals |  |  |  | gym_otm | gym, outdoor, home |  |
| thirty_thirty_intervals | 30/30 Climbing Intervals | power_endurance, anaerobic_capacity | very_high | climbing_intervals |  |  | finger_sensitive, elbow_sensitive | pe_thirty_thirty | gym |  |

## prehab (17 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| active_finger_curls | Active Finger Curls (Dynamic Tendon Loading) | finger_strength | low | isometric_hang | hangboard |  | elbow_sensitive | prehab_finger_dynamic | home, gym |  |
| band_external_rotation | Band External Rotation | prehab_shoulder | low | rotation | resistance_band |  |  | prehab_shoulder_rotator_cuff | home, gym |  |
| band_pull_apart | Band Pull-apart (Scapular Daily) | prehab_shoulder | low | scapular_control | resistance_band |  |  | prehab_shoulder_rotator_cuff | home, gym, outdoor |  |
| elbow_eccentric_curl | Elbow Eccentric Curl (Tyler Twist) | prehab_elbow | low | forearm_supination | resistance_band |  |  | prehab_elbow_extensors | home, gym |  |
| elbow_wrist_extensor_eccentric | Wrist Extensor Eccentrics | prehab_elbow | low | wrist_extension | dumbbell |  |  | prehab_elbow_extensors | home, gym |  |
| face_pull | Face Pull (Band) | prehab_shoulder | low | scapular_control | resistance_band |  |  | prehab_shoulder_rotator_cuff | home, gym |  |
| finger_extensor_band | Finger Extensor Band Extensions | prehab_finger | very_low | finger_extension |  |  |  | prehab_finger_extensors | home, gym |  |
| finger_extensor_training | Finger Extensor Training (Rubber Band) | prehab_wrist | low | wrist_extension |  |  |  | prehab_finger_extensors | home, gym, outdoor |  |
| finger_tendon_glides | Finger Tendon Gliding Exercises | prehab_finger | very_low | tendon_glide |  |  |  | prehab_finger_glides | home, gym |  |
| forearm_pronation_supination | Forearm Pronation/Supination | prehab_elbow | low | forearm_pronation |  |  |  | prehab_elbow_pronation_supination | home, gym |  |
| long_duration_hang | Long Duration Hang (Tendon Health) | finger_aerobic_endurance | medium | isometric_hang | hangboard |  |  | finger_long_duration_hang | home, gym |  |
| pronator_terres_isometric_hold | Pronator Teres Isometric Hold | prehab_elbow | low | forearm_pronation | resistance_band |  |  | prehab_elbow_pronator | home, gym |  |
| reverse_wrist_curl | Reverse Wrist Curl (Extension) | prehab_wrist | low | wrist_extension | weight |  |  | prehab_wrist_curls | home, gym |  |
| shoulder_car | Shoulder CARs (Controlled Articular Rotation) | prehab_shoulder, mobility | low | mobility_shoulders |  |  |  | prehab_shoulder_cars | home, gym, outdoor |  |
| stick_pronation_supination_eccentric | Stick Pronation/Supination Eccentrics | prehab_elbow | low | rotation | dumbbell |  | elbow_sensitive | prehab_elbow_rotation | home, gym |  |
| wall_slide | Wall Slide (Forearm) | prehab_shoulder | low | scapular_control |  |  | shoulder_sensitive | prehab_shoulder_scapular | home, gym, outdoor |  |
| wrist_curl | Wrist Curl (Flexion) | prehab_wrist | low | wrist_flexion | weight |  |  | prehab_wrist_curls | home, gym |  |

## strength_accessory (22 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| band_assisted_pullup | Band-assisted Pull-up | strength_general | medium | pull_vertical | pullup_bar, band |  | shoulder_sensitive | pullup_variants | home, gym |  |
| barbell_row | Barbell Row | strength_general | medium | pull_horizontal | weight |  |  | horizontal_pull | gym |  |
| bench_press | Bench Press | strength_general | medium | push | weight |  | shoulder_sensitive | bench_press | gym |  |
| bicep_curl | Bicep Curl | strength_general | low | elbow_flexion | dumbbell |  | elbow_sensitive | bicep_curl | gym, home |  |
| chinup | Chin-up | strength_general | medium | pull_vertical | pullup_bar |  | shoulder_sensitive | pullup_variants | home, gym, outdoor |  |
| dumbbell_bench_press | Dumbbell Bench Press | strength_general | medium | push | dumbbell |  | shoulder_sensitive | bench_press | gym |  |
| frenchies | Frenchies (Isometric Pull-up Intervals) | strength_pulling, lock_off_endurance | high | pull_vertical | pullup_bar |  | finger_injury, elbow_injury | vertical_pull | gym, home |  |
| glute_bridge | Glute Bridge | strength_general | low | hinge |  |  |  | glute_bridge | home, gym |  |
| goblet_squat | Goblet Squat | strength_general | medium | squat | weight |  |  | goblet_squat | home, gym |  |
| gym_technique_boulder_drills | Technique Boulder Drills (Footwork / Efficiency) | technique_boulder, technique_footwork | low | technique_drill |  |  |  | gym_technique_drills | gym |  |
| inverted_row | Inverted Row | strength_general | medium | pull_horizontal |  |  | shoulder_sensitive | horizontal_pull | home, gym, outdoor |  |
| lateral_raise | Lateral Raise | strength_general | low | shoulder_isolation | dumbbell |  | shoulder_sensitive | lateral_raise | gym, home |  |
| lp_repeater_lifts | Loading Pin Repeater Lifts | finger_strength_endurance | medium | isometric_hang | loading_pin |  | elbow_sensitive | finger_repeater | home, gym | Y |
| overhead_press | Overhead Press | strength_general | medium | push | weight |  | shoulder_sensitive | overhead_press | home, gym |  |
| pike_pushup | Pike Push-up | strength_general | medium | push |  |  | shoulder_sensitive | pushup_variants | home, gym |  |
| pistol_squat_progression | Pistol Squat Progression (Chair → Full) | strength_general | medium | squat |  |  | knee_injury | unilateral_squat | home, gym |  |
| pushup | Push-up | strength_general | medium | push |  |  | shoulder_sensitive | pushup_variants | home, gym, outdoor |  |
| ring_pushup | Ring Push-up | strength_general | medium | push | rings |  | shoulder_sensitive | pushup_variants | home, gym |  |
| romanian_deadlift | Romanian Deadlift (RDL) | strength_general | medium | hinge | weight |  |  | hip_hinge | gym |  |
| scapular_pullup | Scapular Pull-up | strength_general, prehab_shoulder | low | scapular_control | pullup_bar |  |  | scapular_control_pull | home, gym, outdoor |  |
| split_squat | Split Squat (Single-leg) | strength_general | medium | squat | weight |  |  | split_squat | home, gym |  |
| uneven_grip_pullup | Uneven-Grip Pull-up (One-Arm Progression) | strength_pulling, lock_off_endurance | high | pull_vertical | pullup_bar |  | finger_injury, elbow_injury | vertical_pull | gym, home |  |

## technique (20 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| breathing_awareness | Breathing Awareness | technique_relaxation | low | technique_drill |  |  |  | technique_relaxation_drills | home, gym, outdoor |  |
| downclimbing_drill | Downclimbing Drill | technique_footwork | low | technique_drill |  |  |  | technique_footwork_drills | gym |  |
| fall_practice | Intentional Fall Practice | technique_lead | medium | technique_drill |  | strength_power, power_endurance, performance |  | technique_lead_specific | gym |  |
| flag_practice | Flag Practice (Inside/Outside/Drop Knee) | technique_boulder | low | technique_drill |  |  |  | technique_body_position_drills | gym |  |
| foothold_stare | Foothold Stare Drill | technique_footwork | low | technique_drill |  |  |  | technique_footwork_drills | home, gym, outdoor |  |
| freeze_drill | Freeze | technique_body_position | low | technique_drill |  |  |  | technique_body_position_drills | gym |  |
| heel_hook_specific_drill | Heel-Hook Specific Drill | technique_footwork | medium | technique_drill |  |  |  | technique_heel | gym, outdoor |  |
| hip_rotation_drill | Hip Rotation Drill | technique_body_position | low | technique_drill |  |  |  | technique_body_position_drills | home, gym, outdoor |  |
| hover_hands | Hover Hands | technique_movement | low | technique_drill |  |  |  | technique_movement_drills | home, gym, outdoor |  |
| no_readjust_drill | No Readjust Drill | technique_footwork | low | technique_drill |  |  |  | technique_footwork_drills | gym |  |
| one_hand_climbing | One Hand Climbing | technique_constraint | low | technique_drill |  |  |  | technique_constraint_drills | home, gym, outdoor |  |
| silent_feet_drill | Silent Feet Drill | technique_footwork | low | technique_drill |  |  |  | technique_footwork_drills | gym |  |
| sloth_monkey | Sloth / Monkey Move | technique_movement | low | technique_drill |  |  |  | technique_movement_drills | home, gym, outdoor |  |
| slow_climbing | Slow Climbing (Count to 3) | technique_lead | low | technique_drill |  |  |  | technique_pacing_drills | gym |  |
| sticky_feet | Sticky Feet Drill | technique_footwork | low | technique_drill |  |  |  | technique_footwork_drills | home, gym, outdoor |  |
| straight_arms | Straight Arms Drill | technique_body_position | low | technique_drill |  |  |  | technique_body_position_drills | home, gym, outdoor |  |
| tap_and_place | Tap and Place | technique_footwork | low | technique_drill |  |  |  | technique_footwork_drills | home, gym, outdoor |  |
| three_limb_drill | Three Limb Drill | technique_constraint | low | technique_drill |  |  |  | technique_constraint_drills | home, gym, outdoor |  |
| timed_route_preview | Timed Route Preview | technique_lead | very_low | technique_drill | gym_routes |  |  | technique_route_reading | gym |  |
| twist_lock_drill | Twist-Lock Drill | technique_body_position | low | technique_drill |  |  |  | technique_body_position_drills | gym |  |

## test (4 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| lp_duration_test | Loading Pin Duration Test (20mm) | finger_strength | medium | isometric_lift | loading_pin |  | finger_sensitive | finger_endurance | home, gym | Y |
| lp_max_test_5s | Loading Pin Max Test (5s) | finger_strength, finger_max_strength | max | isometric_hang | loading_pin |  |  | finger_test | home, gym | Y |
| lp_repeater_test | Loading Pin Repeater Test (7/3) | finger_strength_endurance | medium | repeater_lift | loading_pin |  | finger_sensitive | finger_repeaters | home, gym | Y |
| test_repeater_7_3_to_failure | Repeater Test 7/3 (To Failure) | finger_strength_endurance | medium | repeater_hang | hangboard |  | finger_sensitive | finger_repeaters | home, gym |  |

## test_measurement (4 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| test_hip_flexibility | Hip Flexibility Test (Straddle Split) | flexibility | low | static_stretch |  |  |  | test_hip_flexibility | home, gym |  |
| test_l_sit_hold | L-Sit Hold Test (Max Duration) | core | max | isometric_hold |  |  |  | test_l_sit | home, gym |  |
| test_max_hang_duration_20mm | Max Hang Duration Test (20mm, BW) | finger_strength | max | isometric_hang | hangboard |  |  | test_hang_duration | home, gym |  |
| test_max_pullup_bw | Max Reps Bodyweight Pull-Up Test | strength_general | high | pull_vertical | pullup_bar |  |  | pulling_test | home, gym |  |

## warmup_general (3 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| dynamic_mobility_flow | Dynamic Mobility Flow | mobility, flexibility | low | mobility_flow |  |  |  | warmup_mobility | home, gym, outdoor |  |
| foam_rolling_general | Foam Rolling (General) | regeneration | low | self_massage |  |  |  | warmup_foam_rolling | home, gym |  |
| general_pulse_raise | Pulse Raise (Light) | aerobic_capacity | low | carry |  |  |  | warmup_pulse_raise | home, gym, outdoor |  |

## warmup_specific (6 exercises)

| exercise_id | name | domain | intensity | pattern | equipment | phase_affinity | contraindications | recency_group | location | unilateral |
|------------|------|--------|-----------|---------|-----------|---------------|-------------------|---------------|----------|-----------|
| dead_hang_easy | Easy Dead Hangs (Warm-up) | finger_strength | low | isometric_hang | hangboard |  | elbow_sensitive | finger_warmup_easy_hang | home, gym |  |
| finger_recruitment_pulls | Recruitment Pulls (Hangboard) | finger_strength | low | pull_vertical | hangboard |  | elbow_sensitive | finger_warmup_recruitment | home, gym |  |
| finger_warmup_generic | Finger Warm-up (No Equipment) | finger_strength | low | wrist_extension |  |  |  | finger_warmup_generic | home, gym, outdoor |  |
| hang_rampup_progressive | Hang Ramp-up (Progressive) | finger_strength | low | isometric_hang | hangboard |  |  | warmup_hang_rampup | home, gym |  |
| warmup_easy_boulders | Easy Boulder Progression | technique_footwork | low | climbing_limit_boulder |  |  |  | warmup_climbing | gym |  |
| warmup_repeaters_large | Warm-Up Repeaters (Large Edge) | finger_strength | very_low | repeater_hang | hangboard |  |  | warmup_hang_rampup | home, gym |  |

---

# Section 6: RESOLVER LOGIC (resolve_session.py)

## P0 Pipeline Stages

```
Stage 0:  Start with all exercises in catalog
Stage 1:  Location filter — exercise.location_allowed must include current location
Stage 2:  Equipment hard filter — equipment_required ⊆ available_equipment
          equipment_required_any ∩ available_equipment ≠ ∅
Stage 2b: Block equipment preference (soft — falls back if empty)
Stage 2c: Finger device preference (soft — B126)
          Splits into finger_pool vs other_pool, prefers user's device
Stage 2d: Age gate (D80) — block if exercise.age_minimum > user_age
Stage 2e: Hangboard experience gate (D35)
          Users < 2yr blocked from: max_hang_5s/7s/10s, max_hang_ladder,
          min_edge_hang, one_arm_hang_assisted (exception: role=test)
Stage 2f: Generic experience_minimum_years gate (B159a)
Stage 3:  Role filter — ANY role match required
Stage 3b: Deduplication — exclude recent_ex_ids (soft)
Stage 4:  Domain filter — ANY domain match (soft, skipped if would zero pool)
Stage 5:  Pattern filter — ANY pattern match (soft, skipped if would zero pool)
Stage 6:  Limitation filter
          Severe contraindications → hard block
          Active contraindications → soft block (try to avoid)
```

## Exercise Scoring (score_exercise)

- Recent exercise_id in last 5 uses: -100
- Recent exercise_id in last 15 uses: -25
- Any recent use: -5
- Recency group penalty (B159b): -15 if rg in recent_recency_groups
- Edge mm preference match: +10
- Grip preference match: +5
- Tie-breaking: sort by (score desc, exercise_id asc)

## Load/Prescription Computation

- Session load score = round(min(85, raw_fatigue_sum × 1.5))
- Per-exercise: fatigue_cost field summed across all resolved exercises
- Load overrides: user_state.overrides.per_exercise[id] → absolute_load_kg | delta_kg | multiplier

## Finger Device Routing

- Reads user_state.preferences.finger_training_device
- If not loading_pin: alias loading_pin → hangboard in available_equipment
- Gym location always implies pullup_bar

## Exercise Ordering (A121)

- Phase-aware ordering: derives effective_phase from macrocycle + current date
- sort_exercises_by_phase() + enforce_ordering_constraints()

## Prehab Injection (B38)

- For each limitation zone → auto-inject one prehab exercise if not present
- Domain: prehab_{zone}
- If 2+ zones severe → force deload

## Contraindication System

- Zones: elbow, finger, shoulder, wrist
- Zone → contraindication: elbow→elbow_sensitive, finger→finger_sensitive, etc.
- Severities: monitor (0), active (1), severe (2)
- Legacy migration: mild→monitor, moderate→active, lieve→monitor, moderato→active
- Active limitation: 0.8× load multiplier on prescription

---

# Section 7: PROGRESSION & ADAPTATION

## Feedback → Load Change (DEFAULT_ADJUSTMENT_POLICY)

| Feedback | Adjustment Range | Midpoint |
|----------|-----------------|----------|
| very_easy | [+10%, +20%] | +15% |
| easy | [+5%, +10%] | +7.5% |
| ok | [0%, +5%] | +2.5% |
| hard | [-5%, 0%] | -2.5% |
| very_hard | [-15%, -5%] | -10% |

## Grade-Based Feedback (limit bouldering)

| Feedback | Grade Delta |
|----------|------------|
| very_easy | +2 |
| easy | +1 |
| ok | 0 |
| hard | -1 |
| very_hard | -2 |

## Working Load System

- Keyed by: exercise_id + setup (edge_mm/grip/load_method for hangboard, surface for bouldering)
- Fields: last_external_load_kg, next_external_load_kg, last_feedback_label, updated_at
- Fresh within 60 days (preferred); falls back to any fresh entry if setup mismatch
- Formula: next_load = last_load × (1 + midpoint_pct)

## Load Transfer (cross-exercise)

- Similarity groups: push (bench_press↔dumbbell_bench 0.85), squat (split_squat↔goblet 0.80), pull (barbell_row↔face_pull 0.25)
- Formula: transferred_load = donor_load × (target_coeff / donor_coeff)

## Pulling Strength Targets (PULLING_1RM_PCT)

| Phase | Easy | Medium | Hard |
|-------|------|--------|------|
| base | 55% | 65% | 75% |
| strength_power | 65% | 75% | 85% |
| power_endurance | 60% | 70% | 80% |
| performance | 60% | 70% | 85% |
| deload | 40% | 50% | 60% |

## Hangboard Default Intensity

| Exercise | % of Max |
|----------|---------|
| max_hang_7s | 88% |
| max_hang_5s | 92% |
| repeater_15_15 | 65% |
| repeater_7_3 | 70% |
| density_hangs | 55% |
| min_edge_hang | 100% (bodyweight) |

## Baseline Sources

- Hangboard: baselines.hangboard[0].max_total_load_kg
- Pulling: baselines.pulling.weighted_pullup_1rm_total_kg
- Loading pin: baselines.loading_pin per hand
- Fallback: derive from grade via _FINGER_BENCHMARK (1.10× BW if unknown)
- Brzycki 1RM: weight × 36 / (37 - reps), accurate 1-10 reps

## Exercises with Progression Logic

- All hangboard exercises (total_load model): max_hang_5s/7s, repeaters, density_hangs
- Weighted pullup (external_load model, uses baselines.pulling)
- Limit bouldering (grade_relative model)
- All external_load exercises: barbell_row, bench_press, split_squat, etc.
- Loading pin exercises (unilateral external_load)

## Closed-Loop State Updates

- stimulus_recency: {last_done_date, last_skipped_date, done_count, skipped_count} per category
- fatigue_proxy: done_sessions_total, hard_sessions_total, finger_sessions_total, endurance_sessions_total
- Categories: finger_strength, boulder_power, endurance, complementaries

---

# Section 8: SAFETY GATES & CONSTRAINTS

| Gate | Location | Description |
|------|----------|-------------|
| Age gate (D80) | resolve_session.py Stage 2d | exercise.age_minimum > user_age → blocked. Primary use: campus board exercises (age_minimum=16). |
| Hangboard experience gate (D35) | resolve_session.py Stage 2e | Users < 2yr experience blocked from: max_hang_5s/7s/10s, max_hang_ladder, min_edge_hang, one_arm_hang_assisted. Test exercises exempt. |
| Generic experience gate (B159a) | resolve_session.py Stage 2f | exercise.experience_minimum_years > user.experience → blocked. Campus exercises require 2+ years. |
| Contraindication system | resolve_session.py Stage 6 | Zones: elbow, finger, shoulder, wrist. Severities: monitor/active/severe. Severe=hard block, Active=soft block + 0.8× load. |
| RED-S guardrails (D64) | test_reds_guardrails.py | Banned weight-loss/body-composition language never appears in codebase. Assessment has exactly 5 axes (no body_composition). |
| Limitation handling | resolve_session.py normalize_limitations() | Parse user_state.limitations → {zone: severity}. Auto-inject prehab exercises. Force deload if 2+ severe zones. |
| Youth cap (D81) | planner_v2.py | Users under 18: max 4 training days per week. |
| Recovery multiplier (D83) | onboarding.py + planner_v2.py | Age 40-49: 1.25×, 50-59: 1.5×, 60+: 1.75×. Extends hard/finger day spacing. |
| Immutability invariant | replanner_v1.py | Past sessions with status done/skipped are NEVER modified. Blocks moving, clearing, or overwriting completed sessions. |
| Monday-start invariant | planner_v2.py ensure_monday() | All start_date must be Monday (weekday 0). Auto-corrects by subtracting days. |
| Hard day cap | planner_v2.py | Default 3 hard days/week. Deload: 0 hard days. Configurable via planning_prefs.hard_day_cap_per_week. |
| Pre-trip deload | macrocycle_v1.py | 5 days before trip: no hard/max sessions. compute_pretrip_dates() marks affected dates. |
| Test freshness | planner_v2.py | 42-day minimum between retests of same type (finger/repeater/pulling). |

---

# Section 9: USER STATE

## User: 681431ae-31c7-4965-9b68-e2695c4fc037

### Assessment Profile

| Axis | Score |
|------|-------|
| finger_strength | 66 |
| pulling_strength | 61 |
| power_endurance | 37 |
| technique | 35 |
| endurance | 30 |

### Body

- body_fat_pct: None
- height_cm: 182
- weight_kg: 77

### Goal

- current_grade: 8a+
- deadline: 2026-08-22
- discipline: lead
- goal_type: lead_grade
- target_grade: 8b
- target_style: redpoint

### Experience

- climbing_years: 15
- structured_training_years: 7

### Equipment

- Home: hangboard
- Gym: Gym 1 — gym_boulder, board_moonboard, spraywall, gym_routes, board_kilter, campus_board, hangboard, barbell, dumbbell, bench, leg_press, cable_machine

### Limitations

```json
{
  "active_flags": [],
  "details": []
}
```

### Macrocycle

- Total weeks: 12
- Start date: 2026-02-16

| Phase | Name | Weeks | Start Week | End Week | Intensity Cap |
|-------|------|-------|------------|----------|---------------|
| base | Endurance Base | 5 | 1 | 5 | medium |
| strength_power | Strength & Power | 2 | 6 | 7 | max |
| power_endurance | Power Endurance | 2 | 8 | 9 | high |
| performance | Performance | 2 | 10 | 11 | max |
| deload | Deload | 1 | 12 | 12 | low |

## Test Fixture User State

### Assessment Profile

| Axis | Score |
|------|-------|
| finger_strength | 100 |
| pulling_strength | 100 |
| power_endurance | 51 |
| technique | 30 |
| endurance | 46 |

- Height: 182cm, Weight: 77kg
- Climbing years: 15, Structured training: 8
- Goal: ? 8b by 2026-06-30
- Grades: boulder OS=? RP=?, lead OS=? RP=?
- Home equipment: pullup_bar, dumbbell, band, hangboard
- Gym: Blocx — spraywall, board_kilter, hangboard, dumbbell, barbell, bench
- Gym: Work Gym — dumbbell, bench, barbell
- Gym: BKL — gym_boulder, spraywall, board_moonboard
- Limitations: {"active_flags": ["gomito_sinistro"], "details": [{"area": "gomito", "id": "elbow_left_tendon", "notes": "Irritation risk with high intensity pulling/hangs.", "severity": "lieve", "side": "sinistro", "updated_at": "2026-01-19"}]}

### Macrocycle (12 weeks)
| Phase | Weeks |
|-------|-------|
| base | 4 |
| strength_power | 3 |
| power_endurance | 2 |
| performance | 2 |
| deload | 1 |

---

# Section 10: PROCESS CUES & COACHING

Total cues: 25

## All Process Cues

| ID | Text | Session Types | Source |
|----|------|---------------|--------|
| cue_001 | Read each problem fully before starting. Where's the crux? Where will you rest? | boulder_circuit_gym, power_contact_gym, limit_boulder_gym, power_endurance_gym | D78 |
| cue_002 | Place every foot so silently that no sound is audible. If your foot makes noise, retry the placement. | boulder_circuit_gym, technique_focus_gym, route_endurance_gym, regeneration_easy | D74/D78 |
| cue_003 | Focus on shoulder engagement — active hang, not passive. Depress and retract your scapulae before every rep. | finger_strength_home, strength_long, finger_maintenance_gym, finger_maintenance_home, finger_aerobic_base, finger_endurance_short | D78 |
| cue_004 | Quality over quantity — stop the set when form breaks down. A sloppy rep teaches bad patterns. | complementary_conditioning, core_training, heavy_conditioning_gym, pulling_strength_gym, upper_body_weights, legs_strength, lower_body_gym | D78 |
| cue_005 | Count your breaths at every rest position. Breathing rhythm is the foundation of route climbing endurance. | route_endurance_gym, endurance_aerobic_gym | D78 |
| cue_006 | G-Tox: while resting on the wall, alternate your arms — overhead for 5s, then down at your side for 5s. Gravity helps... | route_endurance_gym, endurance_aerobic_gym, power_endurance_gym | D17 |
| cue_007 | Between hard attempts, do 2-3 minutes of easy traversing instead of sitting. Active recovery promotes faster reperfus... | boulder_circuit_gym, power_contact_gym, limit_boulder_gym, strength_long | D48 (Valenzuela 2015) |
| cue_008 | Before each climb, scan the route bottom to top for 30 seconds. Identify rest spots, the crux, and your clipping posi... | route_endurance_gym, technique_focus_gym | D75 (Seifert 2017) |
| cue_009 | Today's focus: hip rotation. On every move, think about turning your hips toward the wall before reaching. | technique_focus_gym, boulder_circuit_gym | D78 |
| cue_010 | Hover your hand 2cm above the target hold for a full second before grabbing. This prevents lunging and builds precision. | technique_focus_gym, boulder_circuit_gym, regeneration_easy | D76 (hover_hands drill) |
| cue_011 | Downclimb every warm-up problem back to the start. It builds eccentric strength and route-reading in reverse. | boulder_circuit_gym, technique_focus_gym, regeneration_easy | D76 |
| cue_012 | If you feel ANY pump during ARC, you're going too hard. Drop the grade. The goal is blood flow, not effort. | endurance_aerobic_gym, finger_aerobic_base | D45 |
| cue_013 | Rest day tomorrow is part of the plan, not a break from it. Adaptation happens during recovery, not during training. | _any_last_session_before_rest | D79 |
| cue_014 | Squeeze every rep with maximal intent. On hangboard, the difference between 90% effort and 100% effort is the differe... | finger_strength_home, strength_long | D78 |
| cue_015 | Try flagging on every move today, even where it's not strictly necessary. Building the habit makes it automatic when ... | technique_focus_gym, boulder_circuit_gym | D76 (flagging_practice) |
| cue_016 | Pause 2-3 seconds after each move. No dynamic movements. Feel your body position before reaching for the next hold. | technique_focus_gym, regeneration_easy | D76 (freeze drill, Matros) |
| cue_017 | Warm up your fingers progressively — never go from cold to max. Your pulleys need time to reach full physiological sl... | finger_strength_home, strength_long, finger_maintenance_gym, finger_maintenance_home | D33 (Fradkin 2010) |
| cue_018 | On conditioning exercises, focus on full range of motion. Half reps build half strength. | complementary_conditioning, heavy_conditioning_gym, pulling_strength_gym, upper_body_weights | D78 |
| cue_019 | Use open-hand grip whenever possible on the hangboard. Save your crimp for the wall where you actually need it. | finger_strength_home, strength_long, finger_maintenance_gym, finger_maintenance_home, finger_aerobic_base, finger_endurance_short | D78 |
| cue_020 | Shake out each arm for 10 seconds between sets. Blood flow is your friend — help it do its job. | boulder_circuit_gym, power_endurance_gym, route_endurance_gym | D78 |
| cue_021 | Today is deload — resist the temptation to go hard. Your body is consolidating gains from the last phase. Trust the p... | deload_recovery, easy_climbing_deload | D79 |
| cue_022 | Engage your core before every dynamic move. A split second of tension through your midsection transfers power from fe... | boulder_circuit_gym, power_contact_gym, limit_boulder_gym | D78 |
| cue_023 | Eccentric control wins. On every pull-up, lower yourself in 3-4 seconds. The descent builds more strength than the as... | pulling_strength_gym, complementary_conditioning, heavy_conditioning_gym | D39 (Earp 2016) |
| cue_024 | Stare at the foothold for 2 seconds after placing your foot. This builds precision and trust in your placements. | technique_focus_gym, boulder_circuit_gym, regeneration_easy | D76 (target_practice) |
| cue_025 | Breathe. Exhale on the hardest part of each move. Holding your breath increases blood pressure and wastes energy. | boulder_circuit_gym, power_contact_gym, limit_boulder_gym, route_endurance_gym, power_endurance_gym | D78 |

## Selection Algorithm

```
1. Load all cues from process_cues.json (cached via @lru_cache)
2. Filter: cue.session_types contains session_template_id
   Special: if next_day_is_rest → also include "_any_last_session_before_rest" tagged cues
3. Seed = SHA256("{user_id}:{date_str}")
4. Index = seed_int % len(matching_cues)
5. Return {"id": cue.id, "text": cue.text}
```
Properties: stateless, deterministic (same user+date+session = same cue), natural rotation.

## Phase Rationale Texts (A141)

Located in: `frontend/src/lib/phase-rationales.ts`

**base** — *Endurance Base: Building your aerobic foundation*
6+ weeks low-intensity work for vascular adaptation (angiogenesis, mitochondria). Common mistake: going too hard (>25% MVC = anaerobic).

**strength_power** — *Strength & Power: Neural horsepower*
Build neural recruitment. High intensity, low volume. Max hang increase 5-10%. Common mistake: adding volume.

**power_endurance** — *Power Endurance: Putting it all together*
Convert base + strength into sustained hard moves. Varied intensity within sessions. Common mistake: all-out on every problem.

**performance** — *Performance: Send season*
Peak readiness. Volume drops, intensity stays. Time to project/onsight. Common mistake: training through it.

**deload** — *Deload: Recovery is training*
Body consolidates gains. Growth hormone surge, tendon repair. 1 week non-negotiable. Common mistake: sneaking in hard sessions.

---

# Section 11: LOAD MODEL

## Session Load Score

- Computed in resolve_session.py
- Formula: `session_load_score = round(min(85, raw_fatigue_sum × 1.5))`
- raw_fatigue_sum = sum of exercise fatigue_cost across all resolved exercises
- Capped at 85

## Intensity-to-Load Mapping (planner estimated)

| Intensity | Estimated Load |
|-----------|---------------|
| low | 20 |
| medium | 40 |
| high | 65 |
| max | 85 |

## Weekly Load Aggregation (report_engine.py)

- planned_total = sum(estimated_load_score) across all sessions in week
- actual_total = sum(session_load_score) for done sessions + outdoor_load + free_session_load
- load_ratio = actual_total / planned_total

## Free Session Load Formula

```
per_climb = relative_difficulty × status_weight × attempt_modifier
load = sum(per_climb) × SCALE_FACTOR

SCALE_FACTOR = 4.0
relative_difficulty = grade_index / max_grade_index
status_weight: flash=0.8, sent=1.0, attempted=0.6
attempt_modifier: 1 attempt=1.0, 2=1.1, 3+=1.3
Typical: 20 moderate boulders ≈ 40 (medium intensity)
```

## Outdoor Load Formula

```
load = avg(grade_weight × style_modifier) × volume_factor × duration_factor
Capped at 85

grade_weight = grade_index(g) + 3
style_modifier: onsight=1.2, flash=1.1, redpoint=1.0, project=0.7, repeat=0.5
volume_factor = min(2.0, 1.0 + log(num_routes, 5))
duration_factor = max(0.5, min(1.5, duration_minutes / 120))
```

## Modifiers

- Deload factor: 0.5 (applied during deload phase)
- Active limitation: 0.8× load multiplier on affected exercises
- Cooldown fallback: 0.9× multiplier
- Social modifier: NOT YET IMPLEMENTED (planned for Social Session feature)

---

# Section 12: IDENTIFIED GAPS (from roadmap)

All items from ROADMAP_CURRENT.md that represent missing training methodology:

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D19 | Simplified linear periodization for beginners | M | Longer base, no MaxHangs, more technique. Subsumes D44. |
| D34 | EL (Effort Level) as primary intensity metric | L | New field on every prescription. Current feedback (very_easy→very_hard) sufficient for launch. |
| D44 | ARC ≥6 weeks in Base phase | S | Currently base=4wk/floor=2wk. Best via D19 beginner path. |
| D45 | ARC <25% MVC formal enforcement | S | Currently process cues only. Formal resolver load cap. |
| D47 | Varied-intensity intervals (replace 4×4) | M | Consuegra Ch.8. 4×4 is industry standard. |
| D49 | Don't combine MaxHangs + IntHangs in same mesocycle | M | López-Rivera 2018. Planner change. |
| D51 | Climbing:conditioning ratio by level | M | 70/30 → 60/40 → 50/50. Currently template weights only. |
| D52 | EL prescription table by experience level | M | Depends on D34. |
| D14 | López load monitoring (EL trend tracking) | M | Depends on D34. Autoregulation. |
| D69 | ACWR-based load monitoring | L | Needs 4+ weeks data. Overlaps Load Model v2. |
| D70 | Overtraining detection heuristics | M | 5-flag system. Depends on D69. |
| D71 | <10% weekly volume increase cap | S | Needs historical volume baseline. |
| D73 | Technique drill % allocation by level | M | Beginners ≥30% drill time. |
| D33 | Dedicated generate_warmup() function | M | 5-phase protocol generator. Current template approach works. |
| D20 | Overreach + taper before Performance phase | M | +10-15% volume overreach → 40-60% taper. |
| D29 | Post-climb mental reflection questions | S | 5 rotating questions, free text, optional. |
| D41 | Campus board auto-stop rules | S | RPE check after campus sets. |
| D53 | Active recovery progression (3-step) | S | References EL system. |
| D59 | Hypertonic/inhibited muscle table | S | Internal resolver pairing logic. |

## Additional gaps (from Engine improvements backlog)

- ACWR design needed before Load Model v2
- No overreach detection (readiness score)
- No plateau detection
- No beginner-specific macrocycle path
- No formal climbing:conditioning ratio enforcement
- No technique drill percentage allocation
- No effort level system (EL)
- No ACWR calculation
- No overtraining detection
- No volume increase cap

---

# Appendix A: ASSESSMENT ENGINE (assessment_v1.py)

## 5-Axis Computation

### Finger Strength

- If max_hang_20mm_7s/5s_total_kg exists: ratio = max_hang / BW, score = (ratio / benchmark) × 100
- Else: grade estimate = (current_idx / target_idx) × 70, minus self-eval penalty
- Self-eval: -15 if primary='fingers_give_out', -8 if secondary

### Pulling Strength

- If weighted_pullup_1rm_total_kg exists: score = (1RM/BW / benchmark) × 100
- If submaximal data: Brzycki estimate 1RM = weight × 36/(37-reps)
- Else: grade estimate = (current_idx / target_idx) × 65
- Self-eval: -10 if primary='cant_hold_hard_moves', -5 if secondary

### Power Endurance

Three-component weighted score:
- Gap score (40%/60%): RP-OS grade gap → 75/55/40/30 for gap ≤2/3-4/5-6/>6
- Repeater test (40%/0%): reps / benchmark × 100
- Self-eval (20%/40%): -8 primary / -4 secondary for 'pump_too_early'

### Technique

- RP-OS gap: 80/60/40/30 for gap ≤2/3-4/5-6/>6
- Self-eval: -10 primary / -5 secondary for 'technique_errors' or 'cant_read_routes'

### Endurance

- Base = PE_score × 0.8
- Experience bonus: min(climbing_years × 2, 10)
- Max hang duration: ≥90s=+8, ≥60s=+4, ≥45s=0, ≥30s=-4, <30s=-8
- Self-eval: -10/-5 for 'pump_too_early', -10/-5 for 'cant_manage_rests'

## Benchmark Tables

### Finger Benchmark (max hang 20mm / BW ratio)

| Grade | Ratio |
|-------|-------|
| 7a | 1.0 |
| 7a+ | 1.08 |
| 7b | 1.15 |
| 7b+ | 1.2 |
| 7c | 1.25 |
| 7c+ | 1.3 |
| 8a | 1.4 |
| 8a+ | 1.5 |
| 8b | 1.6 |
| 8b+ | 1.7 |
| 8c | 1.8 |
| 8c+ | 1.9 |
| 9a | 2.0 |
| 9a+ | 2.1 |

### Pulling Benchmark (weighted pullup 1RM / BW ratio)

| Grade | Ratio |
|-------|-------|
| 7a | 1.2 |
| 7a+ | 1.25 |
| 7b | 1.3 |
| 7b+ | 1.35 |
| 7c | 1.4 |
| 7c+ | 1.45 |
| 8a | 1.55 |
| 8a+ | 1.65 |
| 8b | 1.75 |
| 8b+ | 1.85 |
| 8c | 1.95 |
| 8c+ | 2.05 |
| 9a | 2.15 |
| 9a+ | 2.25 |

### PE Repeater Benchmark (7:3 duty, 20mm, 60% max — expected reps)

| Grade | Reps |
|-------|------|
| 7a | 18 |
| 7a+ | 20 |
| 7b | 22 |
| 7b+ | 24 |
| 7c | 26 |
| 7c+ | 28 |
| 8a | 30 |
| 8a+ | 32 |
| 8b | 34 |
| 8b+ | 36 |
| 8c | 38 |
| 8c+ | 40 |
| 9a | 42 |
| 9a+ | 44 |
