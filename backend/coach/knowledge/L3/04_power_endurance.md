# L3 — Power Endurance

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC4 (primary).
> **Token target:** ~4,000.
> **Status:** v1.0 — ready.
> **Source files distilled:** `docs/research_kb/03_pump_endurance_capillaries.md` (T03 PE portions), `consuegra_book_synthesis.md` (Ch.7 + Ch.8 4×4 critique + varied intervals), `literature_review_climbing_training.md` §6-8 (session templates), decision consolidation D17, D26, D47, D48, audit §4.4 OD-3 (Bechtel high/low-threshold acknowledgment).
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6.

---

## Quick reference

Power endurance (PE) is the capacity to sustain near-maximal grip and pulling force across linked sequences of 15-180 seconds — the difference between sending the crux on attempt 1 and falling on attempt 5 from accumulated forearm fatigue. The engine **does not prescribe traditional 4×4 (D47)** — Consuegra and Valenzuela's evidence shows 4×4 drives total vascular occlusion which is counterproductive. Instead the engine uses **varied-intensity intervals**: hardest first, decreasing intensity, ≥45 s rest between problems, 2-4 sets. Active recovery between attempts (easy traversing, not sitting) accelerates lactate clearance ~35% (D48, Watts 2000).

---

## Core findings

### 1. What PE actually is — and what it isn't

PE training targets the glycolytic energy system plus aerobic-power support. Climbing PE has unique constraints because forearm work is isometric — blood flow is fully occluded above ~50% MVC (Hörst T4C; Lacrux/Völker). The lactate-acidosis-recovery cycle climbers experience during sustained crux work is dominated by:
- **H+ accumulation** (intracellular acidosis) — impairs enzymatic function, reduces force.
- **Inorganic phosphate (Pi)** — now thought to be the primary driver of force reduction during sustained exercise (Lattice energy systems guide).
- **Impaired PCr resynthesis** — without blood flow between contractions, the alactic system can't replenish.

**Common myth:** "lactic acid causes the pump". Lactate and H+ are 99% dissociated at physiological pH. Lactate is actually a fuel, shuttled to other tissues (heart, liver) for energy (D26). The coach should debunk this myth when it comes up — climbers train smarter when they understand the actual physiology.

### 2. Energy system mix — surprising finding

Maciejczyk 2021 (*Frontiers in Physiology*) measured energy system contributions in climbing-specific tests:
- 30 s all-out finger flexor test: 62% alactic, 18% glycolytic, **19% aerobic**.
- Continuous 60% MVC: 54% alactic, 18% glycolytic, **28% aerobic**.
- **Intermittent 60% MVC (most like real climbing): 27% alactic, 13% glycolytic, 60% aerobic.**

This is the surprising finding the coach can surface: intermittent climbing (what we actually do) is **predominantly aerobic** (60%). The aerobic system replenishes PCr during the brief rests between moves (D17 G-Tox cues this directly). This is why ARC and aerobic-power work matter even for "anaerobic" PE training — the recovery between attempts is aerobic.

Consuegra Ch.7 reinforces this from a different angle: forearm lactate in climbing peaks at 5-7 mmol/L (Gáspari 2015, La Torre 2009, Schöffl 2006) vs. 17 mmol/L in 400m sprint and 29 mmol/L in BMX Wingate. Anaerobic glycolysis is **not** the dominant energy system in climbing. The dominant pathway in the forearm is alactic + aerobic, with aerobic acting as the recovery engine between alactic efforts (Bertuzzi 2007 — cited by Consuegra).

### 3. The 4×4 problem (D47)

Traditional 4×4 protocol: 4 boulder problems back-to-back with minimal rest, 4 sets total. Hardest first, easiest last.

**Consuegra Ch.8 + Valenzuela 2015 critique:** 4×4 drives total vascular occlusion in the forearms. Across 4 problems without rest, intracellular acidosis becomes overwhelming, recovery between sets is incomplete, and the stimulus becomes a fatigue grind rather than a clean glycolytic + aerobic training signal. The exercise *does* produce pump (it works the system) but the adaptation it produces is mostly lactate tolerance, not the alactic + aerobic interplay that matters for actual climbing.

**Engine prescription (D47): varied-intensity intervals.** Hardest first, decreasing intensity across the set, **≥45 s rest between problems**, 2-4 sets total, 4-5 min rest between sets. The rest between problems is the critical change — it lets the aerobic system clear metabolites and resynthesize PCr partially, which trains the actual climbing pattern (alactic effort → brief aerobic recovery → repeat).

When the user requests 4×4 specifically (it's the most-named PE protocol in popular climbing media), the coach explains the issue and offers the varied-intensity alternative.

### 4. Bechtel's high-threshold vs low-threshold PE acknowledgment

Bechtel & Stewart (2017) distinguish two PE styles:
- **High-threshold PE** — short, hard linked sequences (15-30 s), near-maximal effort. Trains alactic + early glycolytic.
- **Low-threshold PE** — longer, sustained sequences (60-180 s), submaximal but sustained. Trains glycolytic capacity + aerobic-power crossover.

The engine doesn't tag sessions explicitly with high/low threshold today but the catalog covers both:
- High-threshold: `boulder_circuit_gym` (limit boulder problems linked), `power_contact_gym`.
- Low-threshold: `power_endurance_gym` (route circuits, repeaters), `route_endurance_gym` for lead climbers.

When the user reads Bechtel and asks, the coach can map: "your linked-boulder circuits are high-threshold; your route repeaters are low-threshold; the engine prescribes both in the PE phase but weighted by your discipline (more high-threshold for boulder, more low-threshold for lead)."

### 5. The PE diagnostic gap (UC4 §4.1)

The engine cannot objectively *measure* PE in v1 (D87b — a PE-specific test using repeaters at 60% MVC to failure — is deferred). Without a direct test, PE is inferred indirectly from:
- 5-axis assessment overall (the `power_endurance` axis is currently scored from self-report + climbing-grade history).
- Closed-loop feedback during PE-phase sessions.
- Plateau pattern recognition (user falls at the same point in a route across 3+ sessions → PE limit).

When the user asks "how do I know my PE is improving?", be honest: the engine can't tell them precisely. Indirect signals are session sustainability (number of failed PE sessions per cycle dropping) and reduced grade gap between onsight and redpoint (less PE-driven projecting). When D87b ships in v2, the coach gets a direct test to point to.

### 6. Active recovery between attempts (D48)

Watts 2000 (cited in `09_recovery_sleep.md`): active recovery via easy traversing between hard attempts **clears lactate ~35% faster** than passive sitting. The mechanism is straightforward — light contractions maintain blood flow, the aerobic system clears metabolites, PCr resynthesizes faster.

In PE sessions specifically, the planner schedules ≥2-3 min between attempts and the in-session cues prompt active rest (walk between problems, light traversing on warm-up holds, never sit). G-Tox arm shakes (D17 — alternating arms overhead 5 s / down 5 s) add another 18.4% recovery speed (Hörst). This is the **lowest-cost intervention** in PE training; users get measurable improvements just by changing rest behavior.

### 7. PE session structure — the engine catalog

| Session | Phase | Structure | Target effect |
|---|---|---|---|
| `power_endurance_gym` | PE phase primary | 4-6 linked sequences, 30-60 s each, full rest 4-5 min, 3-4 sets | Glycolytic + aerobic crossover (lead-leaning) |
| `boulder_circuit_gym` | PE phase + Performance | 4-8 boulder problems linked at varied intensity, ≥45 s between, 3-4 sets | High-threshold PE (boulder-leaning) |
| `power_contact_gym` | PE + Performance | Short hard problems (5-15 moves), max effort, long rest (4-5 min between attempts) | Alactic + RFD bias |
| `route_endurance_gym` | PE + Base (maintenance) | Route circuits, 4-8 min per circuit, 3-5 min rest, 2-4 sets | Aerobic-power, low-threshold PE (lead) |

The varied-intensity interval protocol (D47) is the *structure* applied to `boulder_circuit_gym` — not a separate session.

---

## How the engine applies this

- **D47 (no 4×4):** the engine's `power_endurance_gym` and `boulder_circuit_gym` templates use varied-intensity intervals with rest periods, never the back-to-back 4×4 structure.
- **D48 active recovery cues:** PE-session guided playback prompts active rest between attempts.
- **D17 G-Tox cue:** surfaces in rest contexts (route_endurance, project, PE).
- **D26 energy-systems model:** the planner respects alactic + aerobic dominance — PE phase still carries ARC maintenance (~15% endurance content per `01_periodization.md` §3 table).
- **Phase weighting:** PE phase prescribes ~45% PE content (vs 15% in adjacent phases). Boulder users get more high-threshold (boulder circuits, power contact); lead users get more low-threshold (route endurance, sustained intervals).
- **No PE test in v1:** the engine infers PE from indirect signals; the dedicated PE test (D87b repeaters to failure) is deferred. Coach is transparent about this.

---

## When user asks…

**"Why doesn't the engine prescribe 4×4? Everyone does 4×4."**

Cite D47 + Consuegra/Valenzuela: 4×4 drives total vascular occlusion. The back-to-back structure (no rest between problems) doesn't train the alactic + aerobic interplay that actual climbing requires — it just produces lactate tolerance. Varied-intensity intervals with ≥45 s rest between problems give the same hard-effort stimulus but train the recovery pattern that matters. If the user has used 4×4 for years and made progress, acknowledge that — 4×4 isn't useless, it's just not optimal. The engine picks the better-targeted variant.

**"What's the difference between PE for boulder and PE for lead?"**

Boulder PE skews high-threshold (short, hard linked sequences at near-max effort, alactic-dominant). Lead PE skews low-threshold (longer sustained sequences at submaximal effort, glycolytic + aerobic crossover). The engine handles this by goal discipline: boulder users get more `boulder_circuit_gym` and `power_contact_gym`; lead users get more `power_endurance_gym` and `route_endurance_gym`. Bechtel uses this distinction explicitly in *Logical Progression*; the engine maps but doesn't name-tag the sessions with the high/low label.

**"How do I objectively test my PE?"**

Honestly: the engine can't, today. The dedicated PE test (repeaters at 60% MVC to failure, D87b) is deferred to v2. For now, PE is inferred from indirect signals — falling-pattern in session feedback, OS/RP grade gap, plateau recognition. When users want self-monitoring, suggest tracking how many attempts before form breaks down on a fixed route at their PE-target grade (a poor man's PE proxy).

**"How often should I do PE sessions in the PE phase?"**

Typically 2 PE sessions per week, paired with maintained finger strength (1 hangboard session) and ARC (1-2 light aerobic sessions). The 2 PE sessions are not consecutive — they need 48+ hr separation for glycolytic + aerobic recovery. Volume guidance from `literature_review_climbing_training.md` §6: total ≤4 hard sessions per week for intermediate, ≤5 for advanced. PE is one of those hard slots.

**"Why is my forearm so pumped after PE training — is that good?"**

Mild-moderate pump is the expected stimulus signature for PE work. Deep, debilitating pump for hours after = too much volume or too little rest between sets. PE sessions should produce pump-and-recover within ~30 min, not pump-and-suffer for the rest of the day. If the latter, the planner is asking too much; surface the feedback and the closed-loop layer will adjust.

**"Should I be doing more lactate-tolerance work?"**

The "lactic acid pump" framing is a myth (D26). Climbing forearm work is alactic + aerobic-dominant, not glycolytic-dominant. Training pure lactate tolerance (back-to-back attempts with no rest, "pump fests") doesn't transfer to better climbing — it just trains the climber to *tolerate* poor recovery patterns. The engine's design is to train the recovery side of the cycle (G-Tox, active recovery, varied-intensity) alongside the effort side.

---

## Sources

- Maciejczyk M et al. 2021. Climbing-specific exercise tests — energy system contributions. *Front Physiol* 12:787902.
- Consuegra S 2023. *The Science of Climbing Training* — Ch.7 physiology + Ch.8 4×4 critique and varied-intensity intervals.
- Bertuzzi R et al. 2007. Forearm energy-system contribution (cited by Consuegra).
- Valenzuela PL et al. 2015. Active vs passive recovery interventions.
- Watts PB 2000. Active recovery and lactate clearance in climbing.
- Hörst EJ. *Training for Climbing* 3rd ed. — energy systems podcast series #22-26.
- Bechtel S & Stewart C 2017. *Logical Progression* — high-threshold vs low-threshold PE distinction.
- Gáspari AF et al. 2015. Climbing lactate measurements.
- La Torre A et al. 2009. Climbing lactate measurements.
- Schöffl V et al. 2006. Climbing physiology.
- Lattice Training. "Training Energy Systems: The Climbers Guide" (blog, Sept 2024).
- Lacrux / target10a (Völker) 2018. Forearm occlusion physiology in climbing.
