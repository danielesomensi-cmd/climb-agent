# D155 — Full-Spectrum Phase Distribution Audit

> **Type:** D (review/analysis)
> **Priority:** P1.5 — pre-launch quality gate for training plan correctness
> **Risk:** LOW (read-only audit) — but findings may trigger HIGH-risk fixes
> **Origin:** D154 S&P audit found critical gap (1 vs 2-3 limit boulder sessions). This audit extends to ALL phases.
> **Depends on:** D154 Phase 1 MUST be complete first (limit_boulder_gym added to S&P pool)
> **Estimated effort:** LARGE (5 phases × 4 availability scenarios × analysis)

---

## 1. Objective

Systematically verify that **every macrocycle phase** generates week plans with session distributions aligned to climbing training literature. This is the definitive quality gate before paid launch.

For each phase, we check 4 dimensions:
- **A) Hard climbing** (limit bouldering, projecting, hard routes)
- **B) Easy/moderate climbing** (volume, ARC, threshold, technique drills on wall)
- **C) Hangboard** (max hangs, repeaters, density hangs)
- **D) Complementary** (conditioning, prehab, flexibility, core, skill work)

---

## 2. Literature Reference Matrix

Sources: Hörst (Training for Climbing), Lattice Training, Eva López, Tyler Nelson, Consuegra, StrengthClimbing, design doc §4.3.

### 2.1 Expected sessions per week BY PHASE (intermediate/advanced climber, lead focus)

```
LEGEND:
  Hard climb  = limit boulder, projecting, hard routes (RPE 8-10)
  Easy climb   = ARC, volume, regeneration, easy routes (RPE 3-6)
  Technique    = on-wall drills, footwork, movement quality (RPE 3-5)
  Hangboard    = max hangs, repeaters, density hangs (any intensity)
  Conditioning = core, pulling suppl., antagonists, prehab, lower body
  Flex/Rest    = flexibility, yoga, mobility, handstand, full rest
```

| Dimension | BASE | S&P | PE | PERF | DELOAD |
|-----------|------|-----|-----|------|--------|
| **Hard climbing** | 0-1 | **2-3** | 1-2 | **2-3** | 0 |
| **Easy/mod climbing** | **3-4** | 0-1 | **2-3** | 1-2 | 1-2 |
| **Technique (on-wall)** | **1-2** (30%+ for beginners) | 0-1 | 0-1 | 1 | 0-1 |
| **Hangboard** | 1-2 (repeaters/density) | **1-2** (max hangs) | 1 (maintenance) | 0-1 (maint.) | 0 |
| **Conditioning** | 2-3 | 2-3 | 1-2 | 1 | 0-1 |
| **Flex/Rest/Skill** | 1-2 | 1-2 | 1-2 | 1-2 | **3-4** |
| | | | | | |
| **Total on-wall** | **4-6** | **2-4** | **3-5** | **3-5** | **1-2** |
| **Total off-wall** | 3-5 | 3-5 | 2-4 | 2-3 | **4-6** |

### 2.2 Rationale per phase

**BASE (Endurance Base):**
- Hörst: "Climb a LOT, climb easy." 3-4× volume/ARC per week.
- Technique emphasis: 20% weight in design doc. Drills embedded in climbing sessions.
- Hangboard: repeaters only (D49), maintenance dose. No max hangs.
- ARC: <25% MVC, no pump (D45). Long sessions (20-40+ min).
- Hard climbing: minimal — maybe 1 moderate session, never limit.

**S&P (Strength & Power):**
- Hörst: "Max hang + limit boulder + general strength."
- Lattice: 2× limit boulder + 1-2× hangboard typical.
- Hard climbing is THE focus: 35% finger_strength + 25% pulling maps to both hangboard AND on-wall limit work.
- Volume climbing drops to 10% — easy sessions are recovery only.
- Post-D154 fix: pool should now include power_contact_gym + limit_boulder_gym.

**PE (Power Endurance):**
- Hörst: "4×4, interval climbing, threshold routes."
- 2-3 on-wall PE sessions (moderate-hard intensity, controlled pump).
- Hangboard: maintenance only (1×/week, sub-max).
- Design doc example week: 4 on-wall sessions (PE intervals, technique, volume, outdoor).
- Hard climbing: 1-2 (intervals count as moderate-hard).

**PERF (Performance):**
- Hörst: "Climb at your limit, project, perform."
- On-wall dominance: 3-5 sessions, mostly hard/projecting.
- Conditioning minimal — maintain don't build.
- Volume reduced 40-60% (D20 taper).
- Hangboard: optional maintenance or skip entirely.

**DELOAD:**
- Hörst: "Volume bassissimo, mobilità, riposo attivo."
- 1-2 easy climbing sessions max. Zero hard climbing.
- Dominated by flexibility, rest, light mobility.
- No hangboard. No conditioning.

---

## 3. Availability Scenarios

### Scenario A: "Daniele" (BASE CASE — must be 100% correct)
```
Mon:  home (evening)
Tue:  gym  (lunch) — BKL
Wed:  home (evening)
Thu:  gym  (evening) — Cocque
Fri:  home/gym (evening) — varies
Sat:  home (evening) — Cocque sometimes
Sun:  home (evening)

Gyms: BKL (gym_boulder, hangboard, pullup_bar, weight)
      Cocque (gym_boulder, hangboard, pullup_bar)
Home: hangboard, pullup_bar, loading_pin
Experience: 5+ years, advanced
Goal: lead_grade, 7c+ target
```
- 2 guaranteed gym days, 5 home days
- Tests Daniele's actual setup — any bug here is a real user-facing problem

### Scenario B: "Gym Rat" (3-4 gym days)
```
Mon:  gym (evening)
Tue:  rest
Wed:  gym (evening)
Thu:  rest
Fri:  gym (evening)
Sat:  gym (morning)
Sun:  rest

Gyms: 1 gym with full equipment
Home: no equipment
Experience: 3 years, intermediate
Goal: lead_grade, 7b target
```
- 4 gym days, 3 rest days
- Tests: does the planner fill 4 gym slots appropriately per phase?

### Scenario C: "Home Trainer" (1 gym day, homewall)
```
Mon:  home (evening) — has homewall
Tue:  home (lunch + evening)
Wed:  rest
Thu:  home (evening)
Fri:  home (evening)
Sat:  gym (morning)
Sun:  rest

Gyms: 1 gym with full equipment
Home: homewall (gym_boulder equiv.), hangboard, pullup_bar
Experience: 4 years, intermediate
Goal: boulder_grade, 7a target
```
- 1 gym day, 4 home days (with homewall = climbing possible at home)
- Tests: does homewall→gym_boulder equivalence produce enough climbing sessions?

### Scenario D: "Minimal" (2 gym days, no home equipment)
```
Mon:  rest
Tue:  gym (evening)
Wed:  rest
Thu:  gym (evening)
Fri:  rest
Sat:  rest (or home, no equipment)
Sun:  rest

Gyms: 1 gym with gym_boulder, hangboard, pullup_bar
Home: no equipment
Experience: 2 years, intermediate
Goal: lead_grade, 7a target
```
- 2 gym days only, no home training
- Tests: minimum viable plan — can the planner generate something useful?

---

## 4. Audit Protocol

### Phase 0: Data Collection (MANDATORY STOP)

For **each of the 5 phases × 4 scenarios** (= 20 combinations), generate a week plan and record:

#### Step 1: Extract session pools per phase

For each phase, list:
- Primary pool sessions (with metadata: hard, climbing, finger, intensity, location)
- Available/complementary pool sessions
- Any phase-specific exclusions

#### Step 2: Generate week plans

For each scenario × phase combination, either:
- Use existing test fixtures if they cover this case
- OR write a minimal test script that calls `generate_phase_week()` with the scenario's availability and the target phase

Record the output as a table:

```
| Day | Session | Hard? | On-wall? | Hangboard? | Category |
|-----|---------|-------|----------|------------|----------|
| Mon | ...     | ...   | ...      | ...        | ...      |
```

Where Category = one of: `hard_climb`, `easy_climb`, `technique`, `hangboard`, `conditioning`, `flex_rest`, `rest`

#### Step 3: Count and compare

For each generated week, tally:

```
| Metric | Generated | Expected (§2.1) | Status |
|--------|-----------|-----------------|--------|
| Hard climbing sessions | ? | X-Y | ✅/⚠️/❌ |
| Easy/mod climbing sessions | ? | X-Y | ✅/⚠️/❌ |
| Technique sessions | ? | X-Y | ✅/⚠️/❌ |
| Hangboard sessions | ? | X-Y | ✅/⚠️/❌ |
| Conditioning sessions | ? | X-Y | ✅/⚠️/❌ |
| Flex/rest sessions | ? | X-Y | ✅/⚠️/❌ |
| Total on-wall | ? | X-Y | ✅/⚠️/❌ |
| Total off-wall | ? | X-Y | ✅/⚠️/❌ |
```

#### Step 4: Identify classification issues

Check session metadata honesty:
- Is every session with `climbing=True` actually on-wall?
- Is every `hard=True` session genuinely hard (RPE 8+)?
- Are hangboard-only sessions correctly marked `climbing=False`?

#### Step 5: Cross-check D154 fix

Specifically verify that S&P (Scenario A = Daniele) now generates ≥2 hard on-wall sessions after the D154 fix.

---

## STOP — Produce Phase 0 Report

### Report format

**Executive summary:** 1 paragraph — overall health, number of ❌ findings.

**Per-phase section (5 sections):**

Each section contains:
1. Session pool table (primary + complementary)
2. 4 scenario result tables (one per availability scenario)
3. Comparison vs literature (using §2.1 matrix)
4. Findings: ✅ (aligned), ⚠️ (marginal), ❌ (misaligned)

**Consolidated findings table:**

```
| # | Phase | Scenario | Finding | Severity | Category |
|---|-------|----------|---------|----------|----------|
| 1 | S&P | A (Daniele) | Only 1 hard climb session | ❌ CRITICAL | (a) pool gap |
| 2 | ... | ... | ... | ... | ... |
```

Categories:
- (a) Pool gap — missing session type in phase pool
- (b) Metadata error — climbing/hard/finger flag incorrect
- (c) Planner logic — correct pool but wrong assignment
- (d) Availability interaction — specific scenario causes degenerate plan
- (e) Template content — session resolves but exercise mix is wrong

**Proposed fix list** (ordered by severity):
```
| # | Finding | Fix type | Effort | Files |
|---|---------|----------|--------|-------|
```

---

## Phase 1: Fixes (only after approval)

TBD based on Phase 0 findings. Likely a mix of:
- New session JSONs for missing session types
- Pool membership changes in macrocycle_v1.py
- Metadata corrections in planner_v2.py SESSION_META
- Possibly planner constraints (min on-wall per phase)

Each fix will be a separate sub-brief with its own tests.

---

## Implementation Notes for Claude Code

### How to generate week plans programmatically

The audit agent should:

1. Read `macrocycle_v1.py` to extract phase pools
2. Read `planner_v2.py` to understand SESSION_META and scoring
3. For each scenario, construct a minimal `user_state` dict with the right availability/gyms/equipment
4. Call `generate_phase_week()` (or the equivalent planning function) for each phase
5. Parse the output to extract session assignments per day
6. Classify each session using SESSION_META + template content

If `generate_phase_week()` requires too much state setup, the agent can alternatively:
- Read all session JSONs and template JSONs
- Simulate the planner's selection logic based on pool membership + scoring
- This is less accurate but faster

### Parallel execution

This audit has 5 independent sections (one per phase). Use subagents:
- Agent 1: BASE phase (4 scenarios)
- Agent 2: S&P phase (4 scenarios) — also verifies D154 fix
- Agent 3: PE phase (4 scenarios)
- Agent 4: PERF phase (4 scenarios)
- Agent 5: DELOAD phase (4 scenarios)

Leader agent: consolidates findings, produces final report.

### Files to read (not modify)

```
backend/engine/macrocycle_v1.py          — phase pools
backend/engine/planner_v2.py             — SESSION_META, scoring, pass logic
backend/catalog/v1/sessions/*.json       — all session definitions
backend/catalog/v1/templates/*.json      — template blocks
backend/engine/resolve_session.py        — exercise selection (for template content check)
backend/tests/                           — existing test fixtures for reference
```

---

## Acceptance Criteria

- [ ] All 20 combinations (5 phases × 4 scenarios) have generated week plans documented
- [ ] Each week plan has per-day session classification (hard_climb / easy_climb / technique / hangboard / conditioning / flex_rest)
- [ ] Each combination has a comparison table vs literature expectations (§2.1)
- [ ] D154 fix is confirmed working for S&P × Scenario A
- [ ] All ❌ findings are listed with severity, category, and proposed fix
- [ ] Metadata honesty check completed (climbing/hard/finger flags)
- [ ] Executive summary with overall health assessment
- [ ] No code changes in Phase 0
