# climb-agent — Boulder & Discipline Support Roadmap

> Origin: Strategic analysis (claude.ai, 2026-03-28)
> Context: Indoor bouldering is the dominant form of gym climbing. climb-agent must serve
> boulder-only climbers as a first-class experience, not a lead-centric app with boulder bolted on.
> Market research: Crimpd/Lattice, KAYA, TopLogger, board apps (Kilter, Tension, Moon).
> Key insight: No competitor generates a fully personalized, periodized plan automatically.
> That's our differentiator — it works for both lead and boulder, but UX must speak to each.

-----

## Design decisions

### DD-B1: Discipline selection model

**Decision:** Three options at onboarding: **Lead**, **Boulder**, **Both**.

- `Lead` → `goal_type: lead_grade`, lead macrocycle (as today)
- `Boulder` → `goal_type: boulder_grade`, boulder macrocycle (base:2, S&P:4, PE:1, perf:2, deload:1)
- `Both` → `goal_type: all_round`, **uses lead macrocycle** with boulder sessions mixed into session pool

**Rationale for Both = lead macrocycle:** The lead macrocycle is a superset — it covers endurance and PE that boulder-only would underweight. A "Both" climber needs all energy systems. The session pool for `all_round` includes both lead and boulder sessions, with domain weights slightly shifted toward strength/power compared to pure lead.

### DD-B2: Grade display preference

**Decision:** Add `grade_system_boulder` user preference: `"font"` (default) or `"v_scale"`.

- Engine internals: always Fontainebleau (no change to existing invariant)
- Frontend: `displayBoulderGrade(font_grade, user_pref)` utility converts at render time
- Conversion table is 1:1 and well-established (6A=V4, 7A=V6, 7C+=V10, 8A=V11, etc.)
- Lead grades: French only for now (YDS support deferred — US lead market is smaller)
- Set during onboarding, changeable in settings

### DD-B3: Both = lead macrocycle

See DD-B1. No parallel macrocycles, no dual-goal engine. Simplest correct approach for launch.

-----

## TIER 1 — Pre-launch mandatory (without these, a boulderer bounces at onboarding)

### A-B1: Discipline selection in onboarding

**Priority:** P1.5 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Add discipline selector as first onboarding step after physical data:

- Three cards: Lead / Boulder / Both
- Selection sets `goal.discipline` and `goal.goal_type`
- Boulder: `goal_type: boulder_grade`
- Lead: `goal_type: lead_grade` (existing)
- Both: `goal_type: all_round`

**Backend:**

- `boulder_grade` goal type: activate existing `_SESSION_POOL_BOULDER` and `_BASE_DURATIONS` boulder config in `macrocycle_v1.py`
- `all_round` goal type: use lead macrocycle + merged session pool (lead + boulder primary sessions)
- Assessment profile computation: same 5 axes, but axis interpretation adapts (see A-B4)

**Frontend:**

- New onboarding step component
- Conditional flow: Boulder skips `target_style` (redpoint/onsight)
- Boulder target grade input uses boulder grade range (6A-8C+ / V4-V16)
- Both: asks both lead target AND boulder target grade

**Files:** onboarding flow (frontend), goal schema validation (backend), macrocycle_v1.py (activate boulder_grade + add all_round), assessment_v1.py (minor label adjustments)

### A-B2: Grade display preference (Font / V-scale)

**Priority:** P1.5 | **Status:** Open | **Type:** A (feature) | **Effort:** S

- New user preference: `grade_system_boulder: "font" | "v_scale"` (default: `"font"`)
- Onboarding: after discipline selection, if boulder or both, ask grade system preference
- Frontend utility: `displayBoulderGrade(fontGrade, preference)` — pure conversion function
- Conversion table as JSON constant (frontend + backend share)
- Apply everywhere boulder grades appear: onboarding, plan view, session view, free session, reports, settings
- Engine internals unchanged — always Fontainebleau

**Conversion table (subset):**

|Font|V-scale|
|----|-------|
|4A  |V0     |
|5A  |V2     |
|6A  |V4     |
|6B  |V4     |
|6C  |V5     |
|7A  |V6     |
|7A+ |V7     |
|7B  |V8     |
|7B+ |V8     |
|7C  |V9     |
|7C+ |V10    |
|8A  |V11    |
|8A+ |V12    |
|8B  |V13    |
|8B+ |V14    |
|8C  |V15    |
|8C+ |V16    |

### A-B3: Self-eval weakness options per discipline

**Priority:** P1.5 | **Status:** Open | **Type:** A (feature) | **Effort:** S

Current self-eval options are lead-biased. Add discipline-conditional options:

**Universal (both disciplines):**

- `cant_hold_hard_moves` — lack of max strength or power on crux moves
- `fingers_give_out` — finger strength is the limiting factor
- `technique_errors` — falling due to poor body positioning or movement quality
- `lack_power` — insufficient explosive power for dynamic moves
- `injury_prone` — frequent injuries or niggles limiting training

**Lead-only:**

- `pump_too_early` — forearm pump limits climbing before strength does
- `cant_manage_rests` — poor ability to recover on rests during routes
- `cant_read_routes` — poor route reading and beta finding

**Boulder-only:**

- `poor_body_tension` — can't maintain tension on steep terrain, feet cut
- `poor_dynamic_movement` — can't execute coordination/dynamic moves
- `weak_on_slopers` — struggle on rounded/open-hand holds
- `poor_problem_reading` — can't read sequences or find beta efficiently

**Both:** show all options (universal + lead + boulder), user picks primary + secondary

**Backend:** vocabulary_v1.md update, assessment_v1.py score mapping for new options, onboarding API accepts new values. New boulder options map to existing axes:

- `poor_body_tension` → technique axis (low score)
- `poor_dynamic_movement` → power_endurance axis (low score) + technique
- `weak_on_slopers` → finger_strength axis (low score)
- `poor_problem_reading` → technique axis (low score)

### A-B4: Assessment radar discipline-aware labels

**Priority:** P1.5 | **Status:** Open | **Type:** A (frontend) | **Effort:** XS

Same 5 axes, different display labels and descriptions based on discipline:

|Axis            |Lead label         |Boulder label                        |
|----------------|-------------------|-------------------------------------|
|finger_strength |Finger Strength    |Finger Strength                      |
|pulling_strength|Pulling Strength   |Pulling & Contact Strength           |
|power_endurance |Power Endurance    |Work Capacity                        |
|technique       |Technique & Tactics|Movement & Reading                   |
|endurance       |Endurance          |Endurance (recovery between attempts)|

Frontend-only change. Axis IDs unchanged.

-----

## TIER 2 — Launch or first week (coherent experience)

### A-B5: Phase labels and messaging per discipline

**Priority:** P2 | **Status:** Open | **Type:** A (frontend + backend notes) | **Effort:** S

Phase display names adapt to discipline:

|phase_id       |Lead            |Boulder               |Both            |
|---------------|----------------|----------------------|----------------|
|base           |Endurance Base  |Movement & Volume Base|General Base    |
|strength_power |Strength & Power|Max Strength & Power  |Strength & Power|
|power_endurance|Power Endurance |Work Capacity         |Power Endurance |
|performance    |Performance     |Projecting & Peak     |Performance     |
|deload         |Deload          |Deload                |Deload          |

Also: phase `notes` field and phase transition tips should be discipline-aware. Add `discipline` parameter to phase note generation in `macrocycle_v1.py`.

### A-B6: Session pool boulder audit & completion

**Priority:** P2 | **Status:** Open | **Type:** D (audit) + A (feature) | **Effort:** M

Audit `_SESSION_POOL_BOULDER` in `macrocycle_v1.py` to verify:

- [ ] Every phase has >=3 primary sessions and >=2 available sessions
- [ ] `limit_boulder` session exists and is well-defined (limit attempts, long rest, grade near max)
- [ ] Board session templates exist: `board_limit_session`, `board_volume_session`
- [ ] PE for boulder covered: `boulder_circuit` (4x4-style), `linked_boulders`, density bouldering
- [ ] `climbing_routes` sessions excluded from boulder-only pool
- [ ] Technique sessions adapted: boulder-relevant drills (not route preview, clipping drill)
- [ ] `all_round` session pool = union of lead primary + boulder primary sessions

Create missing sessions/templates as needed.

### A-B7: Boulder target in guided sessions

**Priority:** P2 | **Status:** Open | **Type:** A (backend + frontend) | **Effort:** S

When resolver outputs a session with climbing blocks for a boulder-discipline user:

- `suggested_boulder_target` should use user's max boulder grade (not lead grade)
- Grade target calibrated by session type:
  - Limit bouldering: max grade to max-1 (e.g., 7B -> target 7A+-7B)
  - Volume bouldering: max-2 to max-3 (e.g., 7B -> target 6B-6C)
  - PE/circuit: max-2 to max-1 (e.g., 7B -> target 6C-7A)
- Include attempt guidance: "3-5 attempts per problem" for limit, "flash attempts" for volume
- Include rest guidance: "3-5 min rest" for limit, "1-2 min" for volume/PE

### A-B8: Board session templates (guided)

**Priority:** P2 | **Status:** Open | **Type:** A (catalog + template) | **Effort:** M

New session definitions for training boards:

1. **`board_limit_session`** — Limit bouldering on Kilter/Moon/Tension
   - Grade: at or near max
   - Structure: 6-10 problems, max 5 attempts each, 3-5 min rest
   - Phase affinity: strength_power, performance
   - Equipment: `board_kilter` OR `board_moonboard` OR `board_other`

2. **`board_volume_session`** — Volume/technique on board
   - Grade: 2-3 below max
   - Structure: 15-20 problems, 1-2 attempts each, 1-2 min rest
   - Phase affinity: base, power_endurance
   - Equipment: same as above

3. **`board_pe_session`** — Power endurance on board
   - Structure: 4x4 format (4 problems x 4 rounds, 4 min rest between rounds)
   - Grade: 3-4 below max
   - Phase affinity: power_endurance
   - Equipment: same as above

No API integration with board apps — these are guidance-only templates.

### A-B9: Process cues and phase tips for boulder

**Priority:** P2 | **Status:** Open | **Type:** C (content) | **Effort:** S

Add boulder-tagged process cues to the cue catalog:

**Bouldering cues:**

- "Read the whole problem before you pull on"
- "One attempt at full intensity, then rest completely"
- "Try the crux move in isolation before linking"
- "Watch other climbers — steal beta"
- "If you can't do it in 5 tries, move on and come back fresh"
- "Focus on precise foot placement — quiet feet on every attempt"
- "Visualize the full sequence before each attempt"
- "Control the descent — downclimb or jump off intentionally"

**Phase tips for boulder discipline:**

- Base: "Build your movement vocabulary — try every style of problem"
- S&P: "This is your power phase — attempt problems at your absolute limit"
- PE: "Work capacity matters — how many hard problems can you do in one session?"
- Performance: "Send season — pick your projects and commit"
- Deload: "Easy problems only, focus on technique and having fun"

-----

## TIER 3 — First month post-launch (meaningful improvements)

### A-B10: Board benchmark tracking

**Priority:** P2.5 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Track progress on training boards specifically:

- In free session (board surface): log max grade sent + board angle
- Dashboard widget: board grade trend over time (per board type)
- Optional: user marks 2-3 "benchmark problems" — track send/not-send over time
- Data stored in existing free session log structure (no schema change needed — surface + grade already captured)

### A-B11: Movement drills for boulder in exercise catalog

**Priority:** P2.5 | **Status:** Open | **Type:** C (catalog expansion) | **Effort:** S

Add or tag exercises specifically for boulder technique:

- Flagging practice (inside flag, outside flag, backstep)
- Heel hook and toe hook drills
- Volume traversing (long traverse for footwork endurance)
- Coordination drills (progressive dynamic movement)
- Drop knee practice
- Body tension drill on steep terrain
- Silent feet (already exists — add `boulder_technique` tag)
- Smearing practice (slab footwork)

Tag with `domain: technique_drill`, `pattern: technique_drill`, suitable `recency_group`.
Phase affinity: all phases for boulder discipline, especially base.

### A-B12: Discipline-aware PE routing

**Priority:** P2.5 | **Status:** Open | **Type:** A (planner) | **Effort:** S

Expand existing "Gym-aware PE routing" roadmap item:

- `discipline: boulder` → PE sessions prefer gyms with `gym_boulder` equipment
- `discipline: lead` → PE sessions prefer gyms with `gym_routes` equipment
- `discipline: all_round` → no preference (either works)
- Implementation: add `discipline` as input to gym-day scoring in planner Pass 1

### A-B13: Conditioning weights per discipline

**Priority:** P2.5 | **Status:** Open | **Type:** A (engine) | **Effort:** S

Verify and adjust `_BASE_DOMAIN_WEIGHTS` in `macrocycle_v1.py` for boulder discipline:

- Boulder needs proportionally MORE: power pulling (campus, weighted pull-ups), core anti-extension/rotation, antagonist push volume
- Boulder needs proportionally LESS: ARC/continuous climbing, forearm endurance (repeaters kept but reduced)
- Audit current boulder weights vs literature (Horst boulder periodization, Lattice boulder plans)

### A-B14: Free session UX for boulder

**Priority:** P2.5 | **Status:** Open | **Type:** A (frontend) | **Effort:** S

When logging a free session on `gym_boulder`:

- Phase-aware suggestion card:
  - Base: "Warm up 10 min on easy problems -> work volume on different styles"
  - S&P: "Warm up -> work 3-5 limit projects -> rest fully between attempts"
  - PE: "Warm up -> circuit of 4 problems, repeat 4 times"
  - Performance: "Focus on your top project(s)"
- Include suggested grade ranges based on user max and session intent
- This is guidance only — user always logs whatever they actually did

### A-B15: Spray wall as guided session surface

**Priority:** P2.5 | **Status:** Open | **Type:** A (catalog + template) | **Effort:** S

Spray wall (`spraywall` in vocabulary) can host guided sessions:

- Limit bouldering (set your own problems at max difficulty)
- Technique drills with constraints (only open hand, only flagging, etc.)
- Work capacity circuits (set a timer, climb continuously)

Add spray wall to `location_any` for relevant session templates.

-----

## TIER 4 — Competitive differentiators (Q2-Q3 2026)

### A-B16: Board workout generator

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** L

Structured board workout mode:

- Input: board type, angle, session goal (limit/volume/PE)
- Output: suggested grade range, number of problems, rest times, timer
- RPE tracking per problem
- Session summary with volume/intensity metrics

### A-B17: Pyramid/circuit builder for board

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Pre-built workout formats:

- Grade pyramid: V3->V4->V5->V6->V5->V4->V3
- 4x4: 4 problems x 4 rounds, configurable rest
- Density set: max problems in X minutes
- User can save custom circuits

### A-B18: Competition prep mode

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** L

For climbers preparing for boulder competitions:

- Flash/onsight emphasis (read-and-send training)
- Time pressure training (4-5 min per problem, like comp format)
- Style variety exposure (route setting variety)
- Comp-specific periodization (peak for comp date)

### A-B19: Indoor grade calibration

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Indoor boulder grades vary enormously between gyms:

- User self-report: "My gym grades are soft/accurate/hard"
- OR: anchor to board grades (Kilter/Moon = standardized)
- Multiplier applied to grade-based load calculations
- Affects session difficulty suggestions

### A-B20: Video/GIF reference for movement patterns

**Priority:** P3 | **Status:** Open | **Type:** C (content) | **Effort:** L

Boulder is more visual than lead. For technique drills and complex exercises:

- Short GIF or video clip of execution
- Key points highlighted
- Displayed on exercise detail card
- Priority targets: flagging, heel hooks, drop knees, dynos, body tension

-----

## TIER 5 — Future (v2+)

### A-B21: Board API integration

When Kilter/Tension/Moon open public APIs:

- Sync sends from board account
- Problem recommendation based on level
- Auto-log in free session

### A-B22: Style finder (strength profile analysis)

Analyze which boulder styles suit the user (crimpy, dynamic, slopey, technical):

- Based on free session logs (grade by surface, style patterns)
- Suggest drills to broaden style range
- Best candidate for LLM Coach layer (Phase 3.5)

### A-B23: Finger strength periodization (advanced)

Lattice-style cycling within macrocycle:

- Max hang -> repeaters -> contact strength -> board limit
- Automatic stimulus rotation
- Partially covered by DUP already — this is the refined version

### A-B24: Injury prevention specific to boulder

Boulder injury patterns differ from lead:

- Higher pulley injury incidence
- More shoulder impingement (steep terrain)
- Ankle/wrist from falls
- Adapted prehab emphasis in session resolver
- Best combined with injury tracking feature (Phase 3.5/4)

-----

## Implementation plan summary

|Tier|Items              |Effort  |Timeline               |Dependency                  |
|----|-------------------|--------|-----------------------|----------------------------|
|T1  |A-B1 through A-B4  |M total |**Pre-launch**         |None — can start immediately|
|T2  |A-B5 through A-B9  |M total |**Launch week**        |T1 complete                 |
|T3  |A-B10 through A-B15|S-M each|**Month 1 post-launch**|T1+T2 complete              |
|T4  |A-B16 through A-B20|M-L each|**Q2-Q3 2026**         |Core stable                 |
|T5  |A-B21 through A-B24|L each  |**v2+**                |Market validation           |

### Suggested implementation order for T1:

1. A-B2 (grade display utility — pure function, no deps) — XS
2. A-B4 (radar labels — frontend-only) — XS
3. A-B3 (self-eval options — vocabulary + assessment) — S
4. A-B1 (discipline selection + goal types — the main work) — M

This order builds bottom-up: utility -> display -> data model -> flow.
