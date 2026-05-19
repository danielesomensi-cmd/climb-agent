# Brief: training_methodology_explained.md (User-Facing Document)

> **Purpose:** A user-readable document explaining HOW and WHY climb-agent trains users the way it does. Written for climbers, not engineers.
> **Audience:** climb-agent users who want to understand the science behind their training plan
> **Tone:** Accessible, confident, cited but not academic. Think "well-written climbing blog post backed by 260 references."
> **Length target:** ~2,000-3,000 words (readable in 10-15 min)
> **When to write:** After Claude Code implements Sessions 1-10 (so the document reflects the actual engine)

---

## Proposed Structure

### 1. Introduction: Why This Isn't Just Another Training App
- climb-agent is built on peer-reviewed science, not bro-science
- 260+ references, 5 systematic reviews, 10 research topics
- Deterministic engine: same inputs → same outputs (no black box)
- Philosophy: "train better, not more" (Consuegra)

### 2. How We Assess You (5-Axis Profile)
- The 5 axes: finger strength, pulling strength, power endurance, technique, endurance
- Why body composition is NOT an axis (Mermier: 0.3% variance; RED-S risk)
- Body weight used only for ratio calculations — we never comment on it
- Source: Magiera 2013 (7 variables → 77% of performance), Lattice methodology
- Radar chart: your strengths and weaknesses drive everything

### 3. How We Build Your Training Plan (Periodization)
- The Hörst 4-3-2-1 model adapted with DUP (undulating)
- Why periodization works: Williams 2017 meta-analysis (ES = 0.43)
- The 5 phases explained simply: Base → Strength → Power Endurance → Performance → Deload
- Phase minimums: Base ≥6 weeks (your capillaries need this), Build ≥3, Peak ≥2
- For beginners: simplified linear model (longer base, more climbing, less intensity)

### 4. The Science of Finger Strength
- Why finger strength is #1: correlations of r = 0.42-0.92 across studies
- Three adaptation levels: neural (weeks), muscular (months), structural/tendon (years)
- Why we recommend open-hand grip for hangboard (pulley injury prevention)
- Why we don't combine MaxHangs and IntHangs in the same phase
- Why beginners wait before advanced hangboard work (tissue adaptation timelines)

### 5. Endurance and "The Pump"
- What pump actually is: vascular occlusion, not just lactate
- The real energy system: alactic + aerobic, NOT glycolytic (Consuegra/Bertuzzi)
- Why ARC training works: capillary growth, mitochondrial biogenesis
- Why we replaced the 4×4: varied-intensity intervals prevent total occlusion

### 6. Technique: The Great Equalizer
- Elite climbers use 1/5 the energy of novices on the same route (Baláš 2014b)
- Why we prescribe technique drills in every phase
- Why beginners spend 30%+ of climbing time on drills
- Silent feet: the one drill everyone should do

### 7. How We Keep You Safe
- Load monitoring: ACWR sweet spot (0.8-1.3)
- The <10% weekly volume increase rule
- Overtraining detection: what we watch for
- Youth protection: why under-16s have hard training limits (Schöffl: growth plates)
- Injury history: why we ask and how it affects your plan

### 8. Recovery Is Training
- Sleep is #1: growth hormone, tissue repair, cognitive function
- Why we praise rest days (SDT: rest compliance = competence signal)
- "Fuel your training": why eating enough matters more than eating less
- Collagen + vitamin C: the one supplement with climbing evidence

### 9. The Coach Voice
- Self-Determination Theory: autonomy, competence, relatedness
- Process goals over outcome goals
- We explain the "why" behind every prescription
- We never shame, never push weight loss, never celebrate overtraining
- "Train better, not more"

### 10. What's Coming Next (v2-v3 Roadmap)
- Flexibility assessment
- Competition taper protocol
- ATR (block) periodization option
- Menstrual cycle tracking (optional, evidence-based caution)
- LLM Coach for route reading and mental skills

---

## Writing Guidelines

- **Cite sparingly but meaningfully:** Use author names and years, not full citations. E.g., "Magiera et al. (2013) showed that just 7 variables explain 77% of climbing performance."
- **No jargon without explanation:** Define MVC, ACWR, EL on first use.
- **Use "we":** "We prescribe open-hand grip because..." (builds trust)
- **Include one "surprising fact" per section** to maintain engagement
- **End each section with a one-sentence takeaway** in bold
- **Link to topic files** for readers who want the deep dive
- **Disclaimer:** "climb-agent is not a medical or nutrition advisor" at the start

---

## Key Messages to Convey

1. **Science-backed, not opinion-based** — every decision has a cited source
2. **Personalized to YOU** — your weaknesses drive your plan
3. **Safety first** — youth protection, injury prevention, no weight-loss messaging
4. **Patience rewarded** — tendons adapt in years, not weeks. Trust the process.
5. **Climbing > gym** — especially for beginners. Technique is the highest ROI.
6. **Recovery = training** — sleep, eat, rest. The gains happen off the wall.

---

*This outline is ready to be written as a full document once the engine reflects all v1 decisions.*
