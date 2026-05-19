# climb-agent Knowledge Base — Research Compilation v2

> Master reference for the training methodology doc AND future LLM Coach context
> Date: 2026-03-14
> Status: COMPLETE RESEARCH — ready for Claude Code to write the final doc
> This file supersedes: research_methodology_compilation.md (v1)

---

## FILE ARCHITECTURE PLAN (for LLM Coach brain)

### Current literature files in repo:
- `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` — internal design doc (engine logic)
- `docs/vocabulary_v1.md` — closed vocabulary and schemas
- `docs/analysis_loading_pin_v1.md` — loading pin literature review
- `docs/audit_timer_load_D121.md` — timer/load audit

### Proposed unified structure:
```
docs/knowledge/
├── 00_INDEX.md                          ← Table of contents + how to use
├── 01_periodization.md                  ← Hörst, Matveyev, DUP, phases
├── 02_finger_strength.md                ← Eva López, hangboard, loading pin
├── 03_pump_and_endurance.md             ← Capillaries, mitochondria, ARC, energy systems
├── 04_fear_and_psychology.md            ← Fear of falling, visualization, mental training
├── 05_nutrition_and_recovery.md         ← Macros, timing, hydration, sleep, supplements
├── 06_overtraining_and_injury.md        ← Signs, prevention, MED principle, prehab
├── 07_technique_and_movement.md         ← Route reading, body position, footwork, drills
├── 08_climbing_philosophy.md            ← Why we climb, process vs outcome, community
├── 09_references.md                     ← All scientific citations in one place
└── training_methodology_explained.md    ← THE user-facing doc (draws from all above)
```

### Why this structure:
1. **Modular** — each file is independent, LLM can load only what's relevant
2. **Indexable** — 00_INDEX.md tells the LLM what's in each file
3. **Extensible** — new topics = new file, no refactoring
4. **Dual-use** — same files serve the methodology doc AND the LLM Coach system prompt
5. **Claude Code task** — merge existing files (analysis_loading_pin_v1.md → 02, audit_timer_load_D121.md stays separate as operational doc)

### For the LLM Coach (future):
The system prompt will inject:
- `00_INDEX.md` (always — tells the LLM what knowledge exists)
- Relevant topic file(s) based on user question
- `user_state` + current plan + recent logs (dynamic)

---

## SECTION 1: Periodization
(See v1 research compilation — unchanged)

### Key references
- Matveyev (1977) — Linear periodization, season as macrocycle
- Muñoz (2017) — Training plan improves performance 1.5-2.3%
- Kazzi et al. (2025) — MOJ Sports Med, systematic review climbing strength training
- PMC meta-analysis (2022) — Climbing + resistance training effects
- Hörst — 4-3-2-1 model, Training for Climbing (3rd ed.)
- Bompa — Periodization Training for Sports, flat pyramid

### Models: Linear (Hörst) + DUP within phases = our hybrid approach

---

## SECTION 2: Finger Strength
(See v1 — unchanged, includes Eva López, Tyler Nelson, loading pin)

---

## SECTION 3: The Pump, Capillaries, Mitochondria, Energy Systems
(See v1 — unchanged, includes Fryer 2016, Granata 2024 meta-analysis, Hellsten 2024)

---

## SECTION 4: Fear, Psychology, Visualization (EXPANDED)

### 4a. Fear of Falling
(See v1 — Lattice/Maguire, Woodman, PubMed 2023, Findlay, Ilgner)

### 4b. Visualization and Route Reading (NEW)

#### Key references
- **Hörst / Training for Climbing** — Beta visualization technique: "Watch your mental movie at least 3x as often as you climb the route." Research on Olympic athletes showed greatest gains with vivid visualization routines.
- **Vertical Mind (McGrath & Elison)** — Hebb's Law applied to climbing: "Neurons that fire together, wire together." Repetition changes neural connections. Overlearning = rehearsing until automatic.
- **Sanchez et al. (2012)** — "Efficacy of pre-ascent climbing route visual inspection in indoor sport climbing." Scand J Med Sci Sports. Route preview improves performance.
- **Seifert et al. (PLOS ONE, 2017)** — "Role of route previewing strategies on climbing fluency and exploratory movements." Experts use different visual strategies (sequence-of-blocks) vs beginners (fragmentary). Preview helps perceive "nested affordances."
- **Pezzulo et al. (2010)** — "When affordances climb into your mind." Motor simulation advantages in memory task for expert climbers vs novices. Brain Cogn.

#### Key concepts
1. **Route reading as problem-solving** — Not just looking, but reverse-engineering the setter's intention. Identify hold types → predict movement → plan sequence → identify rests and clips.
2. **Mental rehearsal** — Visualize FEELING of each move, not just positions. Include effort levels, pacing, breathing. Elite climbers "climb" routes multiple times mentally before touching holds.
3. **Beta maps** — Drawing the route with key holds, cruxes, clips. Study like an exam. Hörst: do it lying in bed, on the bus, any free moment.
4. **Top-down + bottom-up scanning** — Start from finish, work backward (find hidden transitions), then bottom-up for starting strategy.
5. **Contingency planning** — What if preferred grip doesn't work? Backup plans reduce anxiety.
6. **Expert vs novice gaze patterns** — Experts: longer fixation duration, fewer fixations, sequence-of-blocks strategy. Beginners: many short fixations, fragmentary scanning.

### 4c. Mental Conditioning (NEW)

#### Key concepts
1. **Process vs outcome focus** — Ondra: "The goal should be the training itself." Bachar: "It's the dance that counts." Focusing on movement quality, not grade.
2. **Growth mindset** — Findlay: letting go of "I'm an anxious climber" as fixed identity. Falling as learning, not failure.
3. **Arousal regulation** — Managing activation level. Too low = sloppy. Too high = tense, over-gripping. Optimal zone varies per person and per route.
4. **Self-talk scripts** — Positive reframing during climbing. "Why don't you just try?" (Rodden). Replace "I can't" with "I haven't yet."
5. **Breathing techniques** — Hörst: breathe more intentionally to save energy, accelerate recovery, maintain focus. Rhythmic breathing on route.
6. **Comfort → Stress → Panic zones** — Train in stress zone (slightly uncomfortable). Panic zone reinforces fear. Comfort zone doesn't grow.

---

## SECTION 5: Nutrition and Recovery (NEW)

### Key references
- **Smith, Storey & Ranchordas (2017)** — Sheffield Hallam University. Nutritional considerations for competitive bouldering. Carbs 3-12 g/kg/day, 5g/kg sufficient for high-intensity.
- **ISSN position stand** — Protein timing less critical than daily total. Anabolic window more flexible than previously thought.
- **Nutritional Considerations for Female Rock Climbers (2024)** — Springer. Post-exercise protein ~0.3-0.4 g/kg. Menstrual cycle considerations. Under-represented in research.
- **Hooper's Beta nutrition guide** — Pre: carbs. During: hydration + electrolytes. Post: carbs + protein. Functional hydration.
- **Seifert research (Rock Way Climbing)** — 4:1 carb:protein ratio for recovery. Recovery window ~45 min. Carb/protein drink reduces muscle fatigue 79% vs water.
- **PhysiVāntage (Hörst)** — Beetroot/nitrate supplementation: 400mg daily + dose 2-3h before. Improves muscle contractility, reduces oxygen demand.

### Key nutrition concepts for the doc
1. **Climbers chronically under-eat** — 82% of adolescent climbers didn't meet calorie needs (Climbing Nutrition research). Under-eating carbs = depleted glycogen = poor performance + poor recovery.
2. **Carbs are NOT the enemy** — Glycogen is primary fuel for climbing. 5g/kg/day for boulder/high-intensity. 1g/kg pre-session.
3. **Protein timing is flexible** — Daily total matters more than exact window. ~1.2-1.8 g/kg/day. Distribute throughout day. Post-exercise: 0.3 g/kg within 2 hours.
4. **Hydration** — 5-7 mL/kg 4 hours before exercise. Replace lost water during session. Electrolytes matter for long sessions.
5. **Recovery nutrition** — Carbs + protein within 45 min post-session for optimal glycogen replenishment. 4:1 carb:protein ratio.
6. **Supplements with evidence** — Beta-alanine, beetroot/nitrates, sodium bicarbonate (for pump/lactate). Creatine (general strength). Collagen (tendon health — emerging evidence). ALWAYS check third-party testing.
7. **Body composition WARNING** — Climbing has a dark history with eating disorders. Anthropometrics explain only 1.8-4% of climbing ability. Health > weight. App must include disclaimer.
8. **Sleep** — The #1 recovery tool. No supplement replaces it. Growth hormone release during deep sleep. 7-9 hours for athletes.

### CRITICAL DISCLAIMER
climb-agent does NOT provide nutritional advice. The methodology doc presents science for education. Users should consult healthcare professionals. Required: "This information is for educational purposes only. Consult a qualified nutritionist or healthcare professional for personalized dietary advice."

---

## SECTION 6: Overtraining and Injury Prevention
(See v1 — Eva López signs, Hörst fatigue rule, tenosynovitis, MED principle)

---

## SECTION 7: Technique and Movement (NEW)

### Key concepts
1. **Footwork first** — Precise foot placement reduces arm demand by 30-50%. Silent feet drill. Weight on feet, not hands.
2. **Body position** — Center of gravity management. Hips close to wall on vertical. Hips away on overhang. Flagging, drop-knee, twist-lock.
3. **Efficiency** — Straight arms when possible (skeletal system, not muscular). Minimum grip force needed. Quick between holds, rest on holds.
4. **Pacing** — Hörst: limit time on any hold to 5 seconds (unless resting). Climb quickly between rests, rest effectively on rest holds.
5. **Micro-rests** — Hörst: "flick water off fingers" between grips. G-Tox: raise and lower arms alternately during rests (gravity-assisted blood flow).
6. **Technique drills** — Silent feet, hover hands, one-hand climbing, sloth/monkey, straight arms, hip rotation. All in our catalog.

---

## SECTION 8: Climbing Philosophy (NEW)

### Key concepts
1. **Why we climb** — Not just physical. Mental challenge, problem-solving, flow state, community, self-discovery. Kauk: "two worlds — the world where nothing is sacred except money, and the other world where everything is sacred."
2. **The process IS the goal** — Ondra: "Training can be very fun." Bachar: "It's the dance that counts." Chouinard: "The only good reason to climb is to improve yourself." Not grade-chasing.
3. **Community and connection** — Climbing is individual but communal. Partners, belayers, beta-sharing, encouragement. The social session concept.
4. **Risk and respect** — Whymper: "courage and strength are nought without prudence." Viesturs: "Getting to the summit is optional, getting down is mandatory." Smart risk assessment.
5. **Fun** — Alex Lowe: "The best climber is the one having the most fun." Carl Tobin: "It don't gotta be fun to be fun." Sharma: "rock climbing is merely one of many ways to exist and grow."
6. **Long game** — Climbing is a lifelong pursuit. No rush. "Tomorrow is a new day" (Rebuffat). Progression is stepped, not linear. Patience.
7. **Mind-body integration** — Ament: "When you ride your bike, your mind is on a treadmill. When you play chess, your body is stagnating. Climbing brings it together in a beautiful, magical way."

---

## SECTION 9: References (consolidated)

### Peer-reviewed
- Fryer S et al. (2016). Forearm muscle oxidative capacity index predicts sport rock-climbing performance. Eur J Appl Physiol.
- Granata C et al. (2024). Effects of Exercise Training on Mitochondrial and Capillary Growth. Sports Medicine.
- Hellsten Y & Gliemann L (2024). Peripheral limitations for performance: Muscle capillarization. Scand J Med Sci Sports.
- Kazzi E et al. (2025). Optimizing physical performance in climbing. MOJ Sports Med.
- López-Rivera E & González-Badillo JJ. Effects of two max grip strength training methods. Sports Technology.
- López-Rivera E (2021). Finger Strength Training for Climbing. Sportphysio.
- Parry H et al. (2024). Impact of capillary and sarcolemmal proximity on mitochondrial function. J Physiol.
- Sanchez X et al. (2012). Efficacy of pre-ascent route visual inspection. Scand J Med Sci Sports.
- Seifert L et al. (2017). Role of route previewing strategies on climbing fluency. PLOS ONE.
- Pezzulo G et al. (2010). When affordances climb into your mind. Brain Cogn.
- Smith E, Storey R, Ranchordas M (2017). Nutritional considerations for competitive bouldering.
- PubMed (2023). Fear of falling in women: psychological training intervention.
- PMC (2022). Effects of climbing- and resistance-training. Systematic review & meta-analysis.

### Books
- Hörst EJ. Training for Climbing (3rd ed.). Falcon Guides.
- Hörst EJ. How to Climb 5.12. Falcon Guides.
- Ilgner A. The Rock Warrior's Way.
- McGrath D & Elison J. Vertical Mind: Psychological Approaches for Optimal Rock Climbing.
- Moffatt J. Mastermind: Mental Training for Climbers.
- Bompa T. Periodization Training for Sports.

### Expert sources (blogs, podcasts, courses)
- Eva López: en-eva-lopez.blogspot.com — Evidence-based finger training
- Hörst / Training for Climbing: trainingforclimbing.com — Periodization, visualization, supplements
- Tyler Nelson / C4HP — Recruitment pulls, density hangs, loading pin
- Lattice Training: latticetraining.com — Assessment, data-driven coaching, fear management
- Hooper's Beta: hoopersbeta.com — Injury prevention, prehab, nutrition
- Climbing Doctor (Dr. Jared Vagy): theclimbingdoctor.com — Injury, Eva López interviews
- Hazel Findlay / Altitude Climbing: altitudeclimbing.com — Fear of falling course
- Climbing Psychology (Madeleine Crane): climbingpsychology.com — Fear masterclass
- Climbing Nutrition: climbingnutrition.com — Macros, timing, evidence-based nutrition

---

## CLAUDE CODE TASK: Build the knowledge base

### What to do:
1. Create `docs/knowledge/` directory
2. Create `00_INDEX.md` with table of contents
3. Split THIS file into the 9 topic files (01-09)
4. Merge `analysis_loading_pin_v1.md` content into `02_finger_strength.md`
5. Write `training_methodology_explained.md` using ALL topic files as source
6. Keep audit files (D121, etc.) separate — they're operational, not knowledge

### The methodology doc draws from knowledge files but is DIFFERENT:
- Knowledge files = raw research, references, detailed findings
- Methodology doc = user-facing, coach tone, concrete examples, no jargon
- Knowledge files are the brain. Methodology doc is the voice.
