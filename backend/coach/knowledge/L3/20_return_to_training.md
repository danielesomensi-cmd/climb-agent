# L3 — Return to Training

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC23.
> **Token target:** ~4,000.
> **Status:** v1.0 — ready, with documented coverage gap (see below). NEW file.
> **Source files distilled:** `docs/research_kb/horst_ch13_injury_synthesis.md` (return-from-injury protocols, conservative tendon timelines, taping methods), `docs/research_kb/07_overtraining_injury_load.md` (ACWR + ≤10% volume cap + tissue adaptation timelines), `docs/research_kb/horst_ch12_recovery_synthesis.md` (3-period recovery + central fatigue), decision consolidation D68 (injury history permanent gate), D71 (volume cap), D72 (open-hand default). NEW file — built from scratch via synthesis.
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table, row `20_return_to_training`) + §4.1 UC23 (entire-gap finding) + §4.3 row 503.

> **v1.0 coverage gap:** Mujika & Padilla 2000a/b (*Sports Med* 30:79-87 + 30:145-154) and Bosquet 2013 meta-analysis on detraining and tapering are referenced in the audit (§4.3 row 503) as the primary detraining-science sources. The KB has Mujika for *tapering* ([[13_tapering_redpoint]]) but not as a separate distilled file for *detraining*. v1.0 ships with the headline conclusions (strength retention 2-4 weeks, aerobic faster decay, recently-acquired gains lost first) cited from the audit and from secondary references in Hörst Ch.12. v1.1 will fold in the primary papers in full detail.

> **Safety firewall (CRITICAL).** Return-to-training after **injury** is a different problem class from return after a non-injury break. For any user returning from a diagnosed injury, the [[L0_safety_hard_rules]] D68 (injury history permanent gate) applies and stays applied; this file's general ramps do not override a physio's specific protocol. When in doubt: physio first.

---

## Quick reference

The detraining literature (Mujika & Padilla 2000a/b; Bosquet 2013) gives the engine a predictable timeline: **strength retained 2-4 weeks**, **aerobic capacity drops faster** (~4-25% over 3-4 weeks), **recently-acquired gains decay first**, **tendon adaptation losses lag perception**. The engine uses a three-band decision tree based on break duration: **<2 weeks** → resume at 70-80% of pre-break loads for 2 sessions, then back to plan; **2-4 weeks** → restart from the *previous* phase end (not Performance, not where you stopped); **>4 weeks** → retest the 5-axis assessment and restart from Base regardless of where the break interrupted you. The D71 ≤10% weekly volume cap is computed against your *post-break actual* chronic load, not against your pre-break peak — that's the highest-risk error in this whole space. For injury-driven breaks, the physio's protocol wins; this file's general ramps are scaffolding under the medical plan, not a replacement for it.

---

## Core findings

### 1. The detraining timeline (Mujika & Padilla 2000a/b; Bosquet 2013)

What is preserved, and for how long, under sustained reduced or absent training stimulus:

| System | Onset of measurable decline | Magnitude over 3-4 weeks | Recovery rate when retraining |
|---|---|---|---|
| **Maximal strength** | ~2-4 weeks | Small (~5-10% in trained athletes) | Fast (1-2 weeks for most of it) |
| **Neural recruitment** | ~7-14 days | Moderate (the "feel" goes first; technical execution slows) | Fast (within sessions) |
| **VO2max / aerobic capacity** | ~7-14 days | Moderate-large (4-25%) | Slower (2-4 weeks for substantial portion) |
| **Plasma volume + muscle glycogen** | Days | Significant within first week | Fast (days) |
| **Capillary density / mitochondrial enzymes** | 4-6 weeks | Moderate (gains take 6+ wk to build, similar to decay) | Slower (4-6 wk for re-adaptation) |
| **Tendon structural adaptation** | Weeks-months (lag perception) | Significant but invisible — the user *feels* fine before tendons are ready | Slow (weeks-months) |
| **Recently-acquired gains (any system)** | First to go | Larger fraction of recent gains lost | The newest gains are the most fragile |

The single most important practical point: **the user's perception lags the actual capacity recovery**. After 3 weeks off, a user can *feel* ready to train at pre-break load — the muscles are recovered, the soreness is gone, motivation is high. But the tendon-side capacity, plasma volume, and mitochondrial enzymes have decayed faster than the user notices. Going to pre-break volume on day 1 of return is the dominant return-from-break injury pattern.

### 2. The three-band decision tree

The engine uses three bands of break duration, calibrated against the §1 timeline:

#### Band A — <2 weeks off

- **Cause profile:** short illness (flu, GI), short travel, single life event, planned mini-rest, single bad week.
- **What's lost:** plasma volume (recoverable in days), some neural "feel" (recoverable inside sessions).
- **Ramp:** first 1-2 sessions at **70-80% of pre-break loads**, **RPE 7 cap** (no top-end work). If those sessions feel normal (RPE matches the prescription, no warning signs), back to the planned macrocycle from session 3 onward.
- **Reassessment:** none required. The engine doesn't need to regenerate.
- **Common error:** treating "short break" as zero cost and going to 100% load on day 1. Even a 7-day break costs something on the neural side; the cap exists to prevent the warning-sign cascade.

#### Band B — 2-4 weeks off

- **Cause profile:** moderate illness, vacation, planned deload-plus-life-event combination, minor injury cleared by physio, end-of-cycle pause that ran long.
- **What's lost:** measurable strength dip (~5-10%), aerobic decline meaningful (5-15%), neural recruitment regressed.
- **Ramp:** restart from the **previous phase end** (not where you stopped). If you were in Performance when the break began, return to the end of Power Endurance phase, not back into Performance. The 1-2 week Performance phase will compress; that's a worthwhile trade vs. injuring on first attempts.
- **Specific loads:** week 1 = ~70% of pre-break volume at full intensity for the previous phase's load level. Week 2 = ramp toward 100% under the D71 ≤10% weekly cap.
- **Reassessment:** optional — if the user wants to retest after week 2-3 of return, the engine accommodates. Not required.
- **Common error:** trying to resume the Performance peak on the original timeline. Performance phase exists *because* of an accumulated Build base; if Build was interrupted, Performance can't be peaked correctly.

#### Band C — >4 weeks off

- **Cause profile:** extended injury, sustained illness, life event lasting months, intentional long break.
- **What's lost:** substantial (~10-25% strength + aerobic; tendon adaptations potentially regressed; sport-specific neural patterns degraded).
- **Ramp:** **redo the 5-axis assessment** ([[16_assessment_interpretation]]) — the engine doesn't trust the pre-break baselines. **Restart from Base phase** regardless of where the break interrupted you. Base is built specifically to rebuild the capillary + tendon + strength-endurance scaffolding that's now decayed.
- **Specific loads:** the first Base cycle after a long break should be ~25% volume-discounted from a fresh-start Base, ramping under D71. The math: your current chronic load is near zero; D71 caps weekly increase at 10% of *that*; the ramp is slower than a fresh-start user's.
- **Reassessment:** required at start.
- **Common error:** trying to skip Base because the user "remembers" being stronger. The memory is real; the tissue capacity is not. Tendon adaptation lost over 4-6 weeks takes 4-6 weeks of patient Base loading to rebuild — there's no shortcut.

### 3. The D71 reset rule (the highest-stakes error in this space)

D71 (≤10% weekly volume increase) is computed against your *current* chronic load, not against your pre-break peak. **This is the single most-violated rule in return-from-break scenarios** — users want to undo a 3-week break in one week, and the engine has to defend against it.

Concretely: if you trained 12 hours/week for 6 months, then took 3 weeks off (chronic load drops toward ~3-4 h/week effective average), your *current* chronic is ~4 h/week. Week 1 of return: maximum 4 × 1.1 = 4.4 h/week. Week 2: ~4.8 h/week. Week 3: ~5.3 h/week. To get back to 12 h/week takes ~12 weeks of ramping under the cap.

**The cap exists for the tendon side**, which is the failure mode in this scenario. Quarmby 2023 ([[17_readiness_overtraining]] §3) confirms volume *spikes* are the dominant overuse-injury trigger; tendons can't absorb a 200% week-on-week increase even when the muscle side feels fine. The 12-week ramp is genuinely the right answer; trying to do it in 3 weeks is the failure pattern.

**Coach script for users who want to skip the ramp:**

> *"I hear you — you remember being able to do 12 h/week and the body remembers too on the muscle side. The cap isn't about muscles; it's about tendons, which adapt months slower than muscles and decay invisibly during the break. Tendinopathy 4-6 weeks after a too-fast return is the textbook pattern (Quarmby 2023). The ramp feels conservative; it's the path that gets you to 12 h/week sustainably. The other path lands you in physio for 3-6 months."*

### 4. Injury-driven returns — physio first, engine second

For any user returning from a diagnosed injury (anything that needed a physio visit, an MRI, an immobilisation period), the rules are different:

- **D68 (injury history permanent gate)** applies and stays applied — see [[L0_safety_hard_rules]]. The engine tightens the relevant load ceilings indefinitely for the affected tissue (full-crimp blocked for prior A2; weighted overhead pressing reduced for prior shoulder; etc.).
- **The physio's protocol wins** over any general ramp in this file. The engine is scaffolding under the physio's plan, not a replacement.
- **The 7-step pulley protocol** (Hörst Ch.13 §3.3 — covered in [[10_injuries_fingers]]) is the canonical example: minimum 2-4 weeks of conservative non-loading, gradual taping return, 6-month prophylactic taping. The engine does not shortcut these timelines.
- **The 8-step elbow tendinopathy protocol** (Hörst Ch.13 §5 — covered in [[11_injuries_shoulder_elbow]]) is the elbow equivalent. Same principle.
- **D72 (open-hand default on hangboard)** stays absolute for users with finger-injury history. Returning from an A2 injury and "feeling fine" does not license full-crimp work.
- **CUE warning:** the coach does *not* diagnose, does *not* prescribe rehab protocol, does *not* shortcut a physio's timeline at the user's request. If the user reports "physio said I can resume but I want to go faster," the coach scripts a return to the physio for that question — not a coach override.

### 5. The reassessment question

"Should I redo the 5-axis assessment after a break?" depends on the band:

- **Band A (<2 wk)** — no. Baselines from before the break are still valid.
- **Band B (2-4 wk)** — optional. If the user wants to know what shifted, the engine accommodates a retest after week 2-3 of return. Don't retest during the immediate-return weeks (results will be confounded by reduced neural drive that will recover quickly anyway).
- **Band C (>4 wk)** — required at start of Band C return. The pre-break baselines are no longer trustworthy. Retest, restart from Base.

Retest timing within Band C: don't retest the day you return. Wait until you've completed 1-2 sessions of low-stakes work (warm-up structure, easy bouldering, light antagonist). A retest immediately after a 6-week break will systematically under-measure neural drive that returns inside 1-2 sessions, biasing the user toward thinking they've lost more than they have.

### 6. The "I broke during Performance phase" question

Specific case worth calling out. A user in Performance phase (peaking for a trip, redpoint, comp) who has to take 2-4 weeks off has lost the peaking work. The options:

- **If the goal date is still ≥4 weeks out:** restart from the end of Power Endurance phase, compress Performance to 1-2 weeks instead of the original 2-3, accept that peak height is lower than originally planned.
- **If the goal date is <4 weeks out:** the peak cannot be replicated in time. Honest framing for the user: the goal stays on the calendar, but expectations for peak performance scale down. Coach script: *"You'll still be in shape for the trip / redpoint — you won't be at the peak you would have been. That's the cost of the disruption. The alternative — trying to compress 4 weeks of peaking into 2 — is the injury route, and it won't restore the lost peak anyway."*
- **If the user wants to reschedule the goal:** that's a macrocycle regeneration question; `/api/macrocycle/start-new-cycle` is the path. The coach can describe the option but the user owns the decision.

### 7. Mental and motivational side of return

Hörst Ch.12 §5.8 + T09 (SDT framing): the mental side of return is often harder than the physical. Users coming back from extended breaks frequently report:

- Frustration that "the body doesn't remember"
- Comparison-paralysis (comparing first-session loads to pre-break peaks)
- Reduced motivation as the rebuild feels slow
- Catastrophizing ("I'll never get back" or "I've lost everything")

The coach response (SDT autonomy + competence — see [[L1_coach_voice]] + [[15_goal_setting_motivation]]):

- Validate the frustration; don't minimise.
- Reframe to the math: 2-4 weeks of return work recovers most of what was lost (§1 timeline). The mental "everything is gone" feeling is loud; the physical reality is more forgiving.
- Process goals during return (D78 — see [[15_goal_setting_motivation]]): "execute the warm-up properly," "stay on the prescription," "log the session honestly" — these are fully controllable and rebuild the consistency rhythm.
- Track the trend, not the point. Week 1 of return looks ugly compared to pre-break peak; week 4 looks much closer; week 8 is often *better* than pre-break (the rest cleared accumulated fatigue + restored some tissue health).

---

## How the engine applies this

- **Three-band decision tree** — engine reads the gap between the last logged session and the current attempted resume; classifies into Band A / B / C; sets the appropriate ramp + reassessment + restart-point logic.
- **D71 reset** — `chronic_load` recalculation post-break uses the actual post-break 28-day window (which includes the break), so the engine's volume cap is computed against the genuine current chronic, not against pre-break peak.
- **D68 injury-history gate** — stays applied across breaks; injury-driven breaks tighten gates further (e.g., a return from prior elbow tendinopathy adds an ACWR cap of 1.2 on upper-body pulling work for 12 months — see [[L0_safety_hard_rules]]).
- **Phase restart point** — Band B restarts at previous phase end; Band C restarts from Base regardless. Engine does NOT resume the macrocycle from "where it was paused"; that's a deliberate design choice driven by the §1 timeline.
- **Reassessment trigger** — engine flags reassessment as required (not optional) for Band C; surfaces it as the first session in the new Base.
- **Macrocycle regeneration** — for Band C or for users whose goal date has shifted, `/api/macrocycle/start-new-cycle` is the path. Atomic: archive → goal review → generate → flag tests.
- **What the engine does NOT do (v1):** automatic injury-protocol selection (physio's job), HRV-based readiness check on return, automatic goal-date rescheduling (user's decision).

---

## When user asks…

**"I skipped 2 weeks for the flu. Where do I resume?"**

Band A boundary. Resume the planned session at **70-80% of pre-break loads**, RPE 7 cap, for the first 1-2 sessions. If those go normally, back to the planned macrocycle from session 3. No reassessment needed. The flu cost you mostly plasma volume and some neural recruitment — both recover inside the first 1-2 sessions. **What you don't do:** treat day-1-back as your hardest session of the week to "make up for lost time." That's the warning-sign cascade.

**"I was injured for 6 weeks. Where do I restart?"**

Band C, injury variant. Two things in sequence: (1) physio clearance is the prerequisite — the coach does not start a return ramp before the physio signs off (and the physio's specific protocol overrides this file's general ramps); (2) once cleared, redo the 5-axis assessment ([[16_assessment_interpretation]]) and restart from Base phase regardless of where the injury interrupted you. The first Base cycle is volume-discounted (~25% below a fresh-start Base) and ramps under D71. The injury history is now a permanent gate (D68) — the affected tissue gets a tightened load ceiling indefinitely.

**"I jumped back into my Performance phase after 3 weeks off. I felt great in week 1 but now I'm getting elbow pain. What happened?"**

Textbook tendon-decay-lag pattern. Three weeks off cost ~5-10% strength on the muscle side (which the user *felt* in week 1: muscles were close to normal) and *invisible* losses on the tendon-adaptation + capillary side (which the user did not feel until week 4-6 when the cumulative load exceeded the now-reduced tissue capacity). The fix: stop the Performance work, see a physio for the elbow (the coach doesn't diagnose), then restart from Band C protocol — redo the assessment, restart from Base, accept that Performance is off the table until the tendon side rebuilds.

**"Can I retest the day I get back?"**

No. Retest after 1-2 sessions of low-stakes work (warm-up structure, easy bouldering, light antagonist). A retest immediately after a long break will systematically under-measure neural drive that recovers inside the first 1-2 sessions, making you look weaker than you actually are. That's a bad anchor for the macrocycle regeneration.

**"My goal trip is in 3 weeks and I just took 2 weeks off. Can I still peak?"**

Probably not at the originally planned peak. Honest framing: with 3 weeks until the trip and 2 weeks of decay behind you, the best move is to restart from end-of-Power-Endurance, compress Performance into 1-2 weeks, and accept that peak height is lower than originally planned. You'll still be in trip shape — you won't be at the peak you would have been. Trying to compress 4 weeks of peaking into 2 is the injury route, and even if it works the peak you'd hit is no higher than the realistic compressed plan. The trip is still worth going on; the goal grade may need recalibration.

**"I broke for 8 weeks and I want to skip Base. I 'remember' being strong."**

The memory is real; the tissue isn't. 8 weeks is Band C — substantial decay on every system. Strength is recoverable in 2-4 weeks of patient retraining; tendon-side adaptation lost over 8 weeks takes 4-6 weeks of Base loading to rebuild. Skipping Base is the textbook tendinopathy-onset path (Quarmby 2023; Hörst Ch.13). The Base cycle isn't punishment — it's the scaffolding that lets you do the higher-stakes phases without breaking. 4-6 weeks of Base now buys 6+ months of progression after; skipping it buys 6 months of injury recovery instead.

**"I haven't trained in 6 months but I've been climbing socially. Where do I start?"**

Halfway-Band-C question. The climbing kept some volume on the system (the chronic-load math isn't quite zero), but structured progression / hangboard / weighted pulling stopped — the *specific* trained adaptations have decayed even if general climbing volume held. Treatment: redo the assessment ([[16_assessment_interpretation]]), restart from Base, but expect Base to feel less brutal than for a true zero-volume user (the climbing volume helped). The phase progression should proceed normally from there — don't try to skip into Build because climbing volume held; the specific finger / pulling / PE work has decayed and needs the Base re-introduction.

**"Should I worry about losing technique during a break?"**

Less than you might fear. Motor patterns are durable — Mujika & Padilla 2000 + Hörst Ch.4: technical patterns regress less under detraining than physical capacities, especially patterns that have been practiced for >6 months. What you may notice in week 1 of return is "rusty feeling" (slow movement, less smooth) — that's not lost technique, that's reduced neural recruitment driving the same movements. It returns inside 1-2 sessions. If a user has been climbing socially during the break (per the question above), technique decay is even less of a concern.

---

## Sources

- Mujika I, Padilla S. 2000a. Detraining: loss of training-induced physiological and performance adaptations. Part I — short term insufficient training stimulus. *Sports Med* 30(2):79-87.
- Mujika I, Padilla S. 2000b. Detraining: loss of training-induced physiological and performance adaptations. Part II — long term insufficient training stimulus. *Sports Med* 30(3):145-154.
- Mujika I, Padilla S. 2003. Scientific bases for precompetition tapering strategies. *Med Sci Sports Exerc* 35(7):1182-1187. (Same authors, tapering — referenced for the symmetric retention-vs-decay framing.)
- Bosquet L et al. 2013. Effect of training cessation on muscular performance: a meta-analysis. *Scand J Med Sci Sports* 23(3):e140-149.
- Hörst EJ. 2022. *Training for Climbing* (3rd ed.), Ch.12 (recovery + central fatigue), Ch.13 (return-from-injury protocols, 7-step pulley + 8-step elbow).
- Quarmby A et al. 2023. Risk factors and injury prevention strategies for overuse injuries in adult climbers. *Front Sports Act Living* 5:1269870.
- Gabbett TJ. 2016. The training-injury prevention paradox. *Br J Sports Med* 50:273-280.
- Schöffl V et al. 2015. Most common climbing injuries (Hörst Ch.13 anchor).
- Hooper's Beta (Firestone). 2022. *Recovery blueprint* — return-from-injury protocols (audit §4.2 reference; v1.1 will fold in deeper).

---

## Cross-references

- [[L0_safety_hard_rules]] — D68 (injury history permanent gate, applies indefinitely after a diagnosed injury), D71 (≤10% volume cap, computed against current chronic), D72 (open-hand default, especially absolute on return from finger injury), D35 (hangboard experience gate not waived by prior experience pre-injury).
- [[01_periodization]] — phase logic that the engine restarts (Band B previous phase end / Band C Base from scratch).
- [[09_recovery_sleep]] — 3-period recovery model + active-rest content during ramp-back.
- [[10_injuries_fingers]] — 7-step pulley protocol (the canonical injury-return protocol; this file's general ramps are scaffolding under it).
- [[11_injuries_shoulder_elbow]] — 8-step elbow tendinopathy protocol.
- [[13_tapering_redpoint]] — Mujika & Padilla 2003 (same authors, tapering side; symmetric to detraining science).
- [[15_goal_setting_motivation]] — mental side of return (§7); SDT autonomy framing for goal recalibration.
- [[16_assessment_interpretation]] — required reassessment for Band C.
- [[17_readiness_overtraining]] — ACWR + D71 + D70 detection (low ACWR is expected during return; the engine doesn't flag it as undertraining if a documented break precedes).
- [[18_equipment_fallback]] — equipment-limited maintenance during long disruptions.
- [[19_lifestyle_integration]] — life-event-driven breaks and the planned-disruption protocol (§5).
