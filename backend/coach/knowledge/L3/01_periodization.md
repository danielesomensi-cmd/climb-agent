# L3 — Periodization

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC1 (primary), UC13 (partial — taper basics), UC23 (partial — return-to-training context).
> **Token target:** ~6,000.
> **Status:** v1.0 — ready.
> **Source files distilled:** `docs/research_kb/04_periodization.md` (T04), `horst_ch2_self_assessment_synthesis.md` (goal setting), `literature_review_climbing_training.md` §5, `consuegra_book_synthesis.md` Ch.10, decision consolidation D19/D20/D21/D22, D44, D51, audit §4.3-§4.4 (Bechtel nonlinear, boulder vs lead).
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table).

---

## Quick reference

Periodization is the deliberate organization of training into sequential phases to maximize specific adaptations, manage fatigue, and peak on demand. The climb-agent engine uses a **Hörst 4-3-2-1 framework with concurrent (DUP) elements**: sequential phases (Base → Strength → Power Endurance → Performance → Deload) where each phase trains all qualities but at shifted percentages. This hybrid is well-supported for intermediate and advanced climbers; beginners get a simplified linear variant (D19).

---

## Core findings

### 1. Why periodize at all

The strongest evidence on periodization comes from general resistance-training meta-analyses applied to climbing by extrapolation — no climbing-specific RCT exists on periodization models per se.

- **Williams 2017** meta-analysis (*Sports Medicine*): 81 effect sizes across 18 studies. Periodized > non-periodized for 1RM strength, **ES = 0.43** (95% CI 0.27-0.58). Undulating models more favorable than linear (β = 0.51). Variation in training stimuli is "vital for increasing maximal strength."
- **Moesgaard 2022** (*Sports Medicine*) volume-equated: periodized > non-periodized **ES = 0.31**; DUP > LP for *trained* athletes (**ES = 0.61**), no advantage for untrained (ES = 0.06). No model difference for hypertrophy.
- **Grgic 2017** (*PeerJ*): when LP and DUP are volume-equated, virtually identical hypertrophy outcomes (Cohen's d = −0.02).

Two takeaways the coach can use directly:
1. Periodization beats "just climb harder" for trained climbers — the user's plan justifies itself.
2. For *beginners*, LP and DUP produce essentially the same results. The engine deliberately keeps beginners on a simpler structure (D19) for cognitive load reasons, not because DUP would hurt them.

### 2. The phases (climb-agent's hybrid)

The engine ships a Hörst 4-3-2-1 backbone with concurrent (DUP) elements within each phase. All qualities are trained in every phase; only the percentage shifts.

| Phase | Duration | Primary stimulus | Secondary | Coach framing |
|---|---|---|---|---|
| **Base** | **≥6 wk (D44, hard floor)** | ARC + technique + general conditioning | Submaximal hangboard, climbing volume | "Build the engine. ARC adaptations are time-locked." |
| **Strength & Power** | 2-3 wk (≥3 wk D21) | Max hangs, limit bouldering, pulling | Maintenance ARC, technique drills | "Build the peak. Neural recruitment + tendon density." |
| **Power Endurance** | 2-3 wk | Varied-intensity intervals (D47), repeaters, route circuits | Maintenance hangboard, technique | "Bridge strength to performance under pump." |
| **Performance** | 1-2 wk (≥2 wk D21) | Project climbing, redpoint attempts | Maintenance only on rest days | "Convert fitness to sends. Don't add new stimulus." |
| **Deload** | 1 wk | Active recovery, easy climbing, mobility | Light prehab | "Adaptation happens here, not during the hard week." |

**Phase floors (D21, hard):**
- Base ≥6 weeks (D44, mitochondrial biogenesis timeline, Mujika 2012).
- Build ≥3 weeks (neural adaptations).
- Peak ≥2 weeks (specificity + recovery).

These are floors, not ceilings. The engine extends them when user data suggests adaptation is incomplete.

### 3. DUP within each phase ("concurrent" element)

Even in the Strength & Power phase, the engine prescribes ~10-15% endurance content to prevent detraining (capillary loss begins at 2-3 weeks without stimulus). Weekly distribution within each phase (`literature_review_climbing_training.md` §5.2, validated against Bechtel/Hörst):

| Phase | Strength/Power | PE | Endurance | Technique | Recovery |
|---|---|---|---|---|---|
| Base | 20% | 15% | 35% | 20% | 10% |
| Strength & Power | 45% | 15% | 10% | 15% | 15% |
| Power Endurance | 15% | 45% | 15% | 10% | 15% |
| Performance | 25% | 25% | 10% | 20% | 20% |
| Deload | 10% | 10% | 20% | 10% | 50% |

The user shouldn't see these percentages as targets. They explain why a Base-phase user still gets one limit-bouldering session per week, and a Performance-phase user still has one ARC.

### 4. Overreach + taper (D20)

Before Performance phase, the engine programs a deliberate **1-week overreach** (volume +10-15%) followed by a brief taper. The performance dip during overreach is intentional — supercompensation produces the peak after fatigue clears (fitness-fatigue model, Bannister 1976). Mujika & Padilla 2003 give the taper parameters: volume reduction 60-90%, intensity *maintained*, frequency reduction ≤20%.

When the user complains "I felt terrible last week and now my plan is easier", that's the protocol working as designed.

### 5. Deload (D20)

The engine programs a deload at the end of each macrocycle and an adaptive mini-deload if the fatigue proxy exceeds threshold.

Deload parameters (coaching consensus; Hörst, Lattice, Bechtel, general S&C):
- Frequency: every 3-6 weeks (4-week mesocycle most common).
- Volume reduction: 50-75%.
- **Intensity: maintained** (do NOT reduce intensity significantly — Mujika 2003).
- Frequency: maintained or one fewer session.
- Content: easy climbing, technique, mobility, prehab. No max efforts.

**The honest caveat (Hooper's Beta 2024):** there's almost no direct RCT evidence on deload weeks vs. continuous training; the rationale is extrapolated from taper science + fitness-fatigue theory + clinical coaching observation. The engine programs deloads because they're low-cost insurance against tendinopathy and overtraining (Quarmby 2023 SR), not because we have iron-clad evidence.

### 6. Tapering for trips and redpoints (UC13 partial)

For sport-route trips (more in `13_tapering_redpoint.md`):
- **Trip taper (1 week):** maintain climbing intensity up to ~85% normal max; cut volume 50%; eliminate supplemental strength work (hangboard, weights).
- **Competition / redpoint taper (3 weeks):** week -3 gentle overreach; week -2 vol −25%; week -1 vol −50%, intensity preserved.
- **Maintain frequency**, not just volume. Mujika 2012: ≥30% frequency reduction during taper = no performance gain.

Performance impact from a good taper: 0.5-6% (Mujika & Padilla 2003). Small in absolute terms but meaningful at limit.

### 7. Boulder vs lead phase weights

The engine differentiates by goal discipline. Boulder users get:
- Longer Strength & Power phase (3-4 weeks vs lead's 2-3).
- Shorter PE phase (2 weeks vs lead's 3-4).
- Heavier emphasis on alactic and contact strength during PE.
- Energy system priority: alactic > glycolytic > aerobic.

Lead users get the inverse: shorter strength, longer PE, longer Base ARC, energy priority aerobic > glycolytic > alactic.

Empirical support is partial: Saeterbakken 2021 (PMC8100213) showed 5 weeks of discipline-prioritized training in advanced/intermediate climbers didn't decrement the other discipline (BCT → finger strength gains; LCT → forearm endurance gains). No direct comparison of phase-weight schemes exists. The boulder/lead split is principled (energy-system theory + Consuegra Ch.7 forearm physiology) rather than RCT-backed.

### 8. Alternative model: Bechtel nonlinear (acknowledgment only)

Bechtel & Stewart 2017 (*Logical Progression*) describe a nonlinear model where all energy systems are trained year-round, with month-to-month emphasis shifts but no hard sequential phases. The argument: trained climbers detrain too quickly within a 4-month Hörst cycle; better to maintain all systems and rotate emphasis.

**Engine choice:** stays with Hörst 4-3-2-1 + DUP for v1. Reasons:
- Clearer peak windows for redpoint and trip goals (Bechtel's continuous model produces flatter performance curves, harder to peak on demand).
- Closed-loop adaptation is cleaner with discrete phases (easier to detect "Base phase response" vs "Strength phase response").
- Hörst model is more familiar to most users and easier to explain.

The coach acknowledges Bechtel's framework exists when asked; doesn't claim Hörst is the only valid model.

### 9. Adaptive deloading

The engine triggers a mini-deload outside the calendar schedule when the fatigue proxy exceeds threshold (ACWR, RPE trend, sleep degradation, performance plateau). This is "stressor banking" (Israetel/Galpin) operationalized — the engine doesn't deload on a fixed calendar alone.

**Implication for the coach:** if the user reports being trashed in week 3 of a Build mesocycle and the engine just inserted a recovery day, that's the system working. If the user feels great and the engine *still* inserted a deload at week 4, that's calendar prophylaxis — the user can negotiate a short delay (see "When user asks…" below).

### 10. Multi-macrocycle / seasonal planning

Consuegra Ch.10: experienced climbers can chain 2-4 macrocycles per year aligned with seasonal goals (spring trip, fall trip, comp). Engine v1 supports one macrocycle at a time; rolling chaining is a future feature. When users ask, the coach can describe the principle (ATR-style sequential macrocycles, used by Patxi Usobiaga / Adam Ondra) but doesn't promise an automated multi-cycle plan today.

### 11. Phase transitions — what changes between phases

The transition between phases is a high-information moment for the user (often confused as "the plan got harder for no reason"). What actually changes:

| Transition | Volume | Intensity | Session character | Coach explanation |
|---|---|---|---|---|
| Base → Strength | Drops 10-20% | Rises ~30% | ARC shifts to maintenance, max hangs + limit boulder take center stage | "Same total stress, redistributed. The capillary engine is built; now we recruit motor units that engine will feed." |
| Strength → PE | Holds | Holds at near-peak | Max protocols cycle to maintenance, varied-intensity intervals + circuits dominate | "We learned to recruit; now we learn to sustain. Strength is the input, not the output we measure." |
| PE → Performance | Drops 20-30% | Rises slightly then holds | Project work, redpoint attempts, intensity sharpens through specificity | "Stop training. Convert. The capacities are there; the engine reduces volume so you can deploy them at quality." |
| Performance → Deload | Drops 50-75% | Intensity *maintained* | Easy climbing, technique, mobility, prehab | "Adaptation happens here. The hard work was the question; recovery is the answer." |

The week between phases is often where adherence drops — sessions feel different, the user second-guesses the plan. The coach's job at these moments is to *name what's happening* before the user names it ("I noticed the plan feels different this week — that's by design; here's why").

### 12. Weekly micro-undulation within a phase

Inside each phase, the week has a HIGH/LOW pattern that respects 48-hour recovery for high-load systems. Concrete example for a 4-day intermediate user in Strength & Power phase:

| Day | Pattern | Content | Load |
|---|---|---|---|
| Mon | HIGH | Max hangs + limit boulder + weighted pulls | High |
| Tue | LOW / REST | Mobility + antagonist (if training) or rest | Recovery |
| Wed | HIGH | Limit boulder + technique drills | High |
| Thu | REST | Full rest | Recovery |
| Fri | HIGH | Max hangs + weighted pulls + core | High |
| Sat | MODERATE | Outdoor climbing or ARC maintenance | Medium |
| Sun | REST | Full rest | Recovery |

The HIGH/HIGH/HIGH spacing with REST or LOW between days respects the 48-hour neural-recovery window for high-CNS-load work (max hangs, limit). Boulder volume sessions can stack on consecutive days at lower intensities (e.g. circuit work + technique drills), but max-effort hangboard + max-effort limit attempts shouldn't.

The coach can surface this when a user requests "back-to-back hard days" — the engine's pattern is *intentional spacing*, not a scheduling quirk.

### 13. Adaptation evidence within a phase

How does the coach (and the user) know a phase is working? Concrete signal patterns:

| Phase | Adaptation signal | Where it shows |
|---|---|---|
| Base | Forearm recovery between attempts improves; light pump dissipates faster; daily HR drops 2-5 bpm at fixed intensity | Subjective recovery rating after first 15 min of climbing; in-session feedback ("felt easier today") |
| Strength & Power | Max hang load increases 2-5% per cycle; limit boulder grade ceiling rises 0.5-1.5 V-grades | Hangboard load progression session-to-session; session feedback on attempted limit problems |
| Power Endurance | Falls during PE sessions occur later in the linked sequence; route project attempt count before fatigue rises | Session-feedback failure-point data |
| Performance | Redpoint attempts at goal grade become viable; OS-RP gap narrows by 0.5-1 grade | Outdoor logs, free-session entries |
| Deload | Session intensity feels lower, perceived recovery higher; fingers and elbows ease tension | Self-report at end of deload week |

When the user asks "is my training working?", point to the phase-appropriate signal. Not seeing the Base-phase signal at week 4? The first adjustment is recovery quality (sleep, fueling) before training adjustments.

### 14. Beginner vs intermediate vs advanced — phase modifications

The engine adapts phase structure to user level (D19, D51):

| User level | Macrocycle | Phase modifications |
|---|---|---|
| Beginner (<2 yr systematic, V0-V4) | 11-12 weeks linear | Longer Base (8 wk), simplified Strength (2 wk), short PE (2 wk), Performance + Deload as standard. No DUP within phases — single-stimulus focus. |
| Intermediate (2-5 yr, V4-V8) | 12-14 weeks Hörst + DUP | Standard 4-3-2-1 with 10-15% off-phase DUP content. Closed-loop adaptation active. |
| Advanced (5+ yr, V8+) | 13-16 weeks Hörst + DUP, deeper | Standard 4-3-2-1 with 15-20% off-phase DUP content. Tighter phase durations possible. Adaptive deload + overreach more aggressive. |

Beginners get less internal complexity because they don't need it yet — climbing volume + technique is doing most of the work; periodization is a small refinement on top. Advanced climbers get more aggressive adaptive layers because they have the recovery capacity and the precision in self-report to justify them.

---

## How the engine applies this

- **Macrocycle generation** creates a Hörst 4-3-2-1 + DUP plan with phase durations bounded by D21/D44 floors. Default total: 11-16 weeks (lead floor 11, boulder floor 8, total cap 16 per A-MACRO-CAPS).
- **Phase weights** (per §3 above) are baked into session selection — the planner picks sessions from the catalog weighted by phase, not by absolute prescriptions.
- **Deload** is scheduled at the end of each macrocycle. Adaptive mini-deload fires when fatigue proxy exceeds threshold.
- **Overreach + taper** triggers 1 week before Performance phase begins (D20).
- **Boulder vs lead** differentiation is handled by goal discipline in user state, affecting phase durations and weights.
- **Adaptive phase duration** per exercise (López load-monitoring style adjustment, D14) is handled at the closed-loop layer, not the macrocycle layer.

---

## When user asks…

**"Why is my Base phase 6 weeks? I want to shorten it."**

Cite D44 + Mujika 2012: mitochondrial biogenesis and capillarization run on a 6+ week clock that's time-locked, not effort-locked. Pushing intensity doesn't shorten the timeline; it converts the stimulus to a different (less useful) adaptation. The engine respects this as a floor, not a target. If the user insists, explain the trade: shortening Base costs the Build and Peak phases a smaller aerobic engine — diminished returns later, not now. Don't relent.

**"I'm a boulderer. Why is my Base phase so long / why is there ARC at all?"**

Acknowledge the boulder/lead distinction: yes, the engine gives boulderers a shorter ARC and longer Strength & Power than it gives lead climbers. But Base ≥6 weeks remains a floor because mitochondrial density is the foundation under contact-strength work too — boulder PE on circuits and density work both require the aerobic engine ARC builds. The boulder Base differs in *content* (more board climbing, more density hangs alongside ARC) more than in *duration*.

**"DUP vs linear — which is better for me?"**

For trained climbers (≥2 years systematic), DUP is slightly better (Moesgaard 2022, ES = 0.61 for strength). For beginners, no meaningful difference (ES = 0.06). The engine handles this automatically — beginners get a simplified linear structure (D19); intermediate+ users get Hörst 4-3-2-1 + DUP. If the user is curious about Bechtel's nonlinear model, acknowledge it as a valid alternative; explain why the engine chose periodized (clearer peaks, easier closed-loop adaptation).

**"I want to peak for my trip in 5 weeks — can the engine taper me?"**

Yes, if the goal trip date is set. Engine programs trip taper: maintain intensity ≤85% max, cut volume 50%, eliminate supplemental strength in the final week. For a 5-week window the structure is 3 weeks normal training → 1 week competition-style taper (vol −25%, intensity preserved) → 1 week trip taper (vol −50%). Last 2-4 days: cessation of training, mental prep, skin care.

**"Can I run two macrocycles in parallel (boulder + sport)?"**

Engine doesn't do this today. The coach can describe the principle from Consuegra Ch.10 (ATR-style multi-peak), but engine v1 prescribes one macrocycle at a time. If the user has dual seasonal goals, the right move is to sequence them: 11-16 weeks with one discipline as primary, then a discipline switch + new macrocycle.

**"I feel great — can I skip the deload?"**

Trade-off framing: deloads are insurance (fitness-fatigue model + tendinopathy prevention). The evidence for *needing* a deload when fatigue proxies are clean is genuinely thin (Hooper's Beta 2024). The user can negotiate a 1-week delay if data is clean (ACWR <1.1, RPE stable, sleep good); cannot delay >1 week — adaptation gains require recovery to consolidate (supercompensation window 48-96 hr). If RPE has crept up, sleep has degraded, or session performance has dropped: deload is non-negotiable, frame it as the engine catching what the user might not consciously feel.

---

## Sources

- Williams TD et al. 2017. Periodized vs non-periodized RT meta-analysis. *Sports Medicine* 47(10):2083-2100.
- Moesgaard L et al. 2022. Volume-equated periodization MA. *Sports Medicine* 52(7):1647-1666.
- Grgic J et al. 2017. LP vs DUP for hypertrophy. *PeerJ* 5:e3695.
- Mujika I, Padilla S. 2003. Tapering scientific bases. *Med Sci Sports Exerc* 35(7):1182-1187.
- Mujika I 2012. Mitochondrial biogenesis timeline; frequency reduction during taper.
- Quarmby A et al. 2023. Climbing tendinopathy systematic review.
- Saeterbakken AH et al. 2021. Boulder vs lead 5-week training transfer (PMC8100213).
- Hooper's Beta 2024. "Deload Weeks: Progression Hack or Harmful Crutch?"
- Consuegra S 2023. *The Science of Climbing Training* — Ch.10 ATR model, Mujika & Bosquet 2016 taper rules.
- Hörst EJ 2022. *Training for Climbing* 3rd ed. — 4-3-2-1 framework, deload guidance, redpoint taper.
- Bechtel S & Stewart C 2017. *Logical Progression* — nonlinear acknowledgment.
- Lattice Training 2019. Competition taper newsletter.
- Bannister EW 1976. Fitness-fatigue model.
- Issurin VB 2010. Block periodization review. *Sports Medicine* 40(3):189-206.
