# L3 — Readiness & Overtraining

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC17 (readiness), UC21 (overtraining).
> **Token target:** ~4,500.
> **Status:** v1.0 — ready. NEW file. **Safety-critical:** medical-referral triggers below are absolute (see [[L0_safety_hard_rules]]).
> **Source files distilled:** `docs/research_kb/07_overtraining_injury_load.md` (T07 — ACWR / Quarmby 2023 / Meeusen 2013 overtraining continuum), `docs/research_kb/horst_ch12_recovery_synthesis.md` (3-period recovery model, central fatigue 7× rule, active rest), decision consolidation D69 (ACWR), D70 (overtraining detection heuristics), D71 (≤10% volume cap). NEW file — synthesized rather than 1:1 distilled.
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table, row `17_readiness_overtraining`) + §4.1 UC17 + UC21.

> **v1.0 coverage gap:** the audit notes (UC17) that there is no objective morning-of HRV / RHR threshold rule in the KB — only directional heuristics. v1.0 surfaces the heuristics honestly; v1.1 will fold in objective thresholds once a primary source is integrated (Hooper's Beta + Christophersen Pt.1 referenced in audit §4.2 cover this).

---

## Quick reference

Readiness and overtraining live on the same continuum, separated by time scale. **Morning readiness** is a same-day decision (train normally / train reduced / active-rest). **Overtraining** is a multi-week diagnosis on the Meeusen 2013 continuum (acute fatigue → functional overreach → non-functional overreach → overtraining syndrome). The engine watches both via ACWR (D69, sweet spot 0.8-1.3), the ≤10% weekly volume cap (D71), and a three-signal heuristic (D70 — performance regression, RPE elevation at constant load, sessions incomplete). The coach speaks in directional language ("a sleep dip + elevated RPE means dial intensity back today"); the coach never diagnoses overtraining syndrome and always escalates to a sports physician when the signature symptoms (chronic mood disturbance, persistent ≥10% RHR elevation, weight loss, repeated illness) co-occur.

---

## Core findings

### 1. The overtraining continuum (Meeusen 2013)

The European College of Sport Science position statement frames overtraining as a four-stage continuum, not a binary state:

| Stage | Timescale | Signature | Recovery |
|---|---|---|---|
| **Acute fatigue** | Hours-days after training | Normal post-session tiredness | Hours to days |
| **Functional Overreaching (FOR)** | Days-weeks | Generalised fatigue, temporary performance dip — *intentional* in some peaking blocks | A few extra rest days; supercompensation often follows |
| **Non-Functional Overreaching (NFOR)** | Weeks-months | Persistent fatigue, RHR/BP drift, sustained performance decline, mood disturbance | Weeks to months |
| **Overtraining Syndrome (OTS)** | Months-years | Chronic under-recovery, sleep + mood + immune disturbance, performance crash | Months to years; **medical** |

**Operative principle for the coach.** FOR is allowed and sometimes engineered (the pre-Performance overreach + taper in [[13_tapering_redpoint]] is a deliberate FOR). NFOR is the engine's red flag — the line where the engine should reduce load and the coach should surface the pattern. OTS is a **medical referral**, not a training-app problem. The coach does not diagnose OTS; it pattern-matches and escalates.

### 2. The engine's three-signal detection (D70)

The engine watches three signals to detect the FOR→NFOR transition:

1. **Performance regression** — two or more consecutive test declines (e.g., MVC on the next two hangboard test sessions trends down) at constant training prescription.
2. **RPE elevation at constant load** — same prescribed session producing higher post-session RPE for 2+ sessions in a row (the user is working harder for the same output).
3. **Session completion rate** — sessions skipped, sets cut short, or marked incomplete repeatedly without an external cause (illness, travel).

Any one signal is noise. Two signals together is a flag — the engine inserts an unscheduled deload (drop volume ~50%, hold intensity at sub-max — see [[09_recovery_sleep]]). Three signals together is a stop signal; the engine pauses progression and the coach surfaces the pattern to the user.

### 3. ACWR — the load-monitoring lens (D69)

Acute:Chronic Workload Ratio (Gabbett 2016, Hulin 2015) is the rolling load monitor:

- **Acute load** = rolling 7-day training load (load = session_duration_min × session_RPE).
- **Chronic load** = rolling 28-day average of the weekly load.
- **ACWR** = acute / chronic.

| ACWR | Interpretation | Coach action |
|---|---|---|
| **<0.8** | Undertraining trend — detraining starts inside 2-4 weeks (see [[20_return_to_training]]) | Surface as a flag if sustained 2+ weeks; if user is intentionally tapering this is fine ([[13_tapering_redpoint]]) |
| **0.8-1.3** | Sweet spot — sustained progression with managed injury risk | None — the system is in band |
| **1.3-1.5** | Elevated — load is building faster than chronic capacity | Engine flags; coach explains the trend, suggests holding the next week at current load to let chronic catch up |
| **>1.5** | Danger zone — Quarmby 2023 + Hulin 2015 link sustained ACWR>1.5 to materially elevated overuse injury risk (especially tendon) | Engine inserts a deload (volume −50%, intensity preserved); coach explains it's not optional — the engine is protecting downstream tendon load tolerance |

**Gabbett 2016 principle, worth repeating to users:** absolute load is not the injury driver; *the rate at which load was built* is. A user at 12 h/week of climbing isn't at higher injury risk than a user at 6 h/week — *unless* the 12 h/week was reached via a series of ≥30% week-on-week jumps. That's why D71 (≤10% weekly volume increase) is non-negotiable.

### 4. D71 — the ≤10% weekly volume cap

[[L0_safety_hard_rules]] D71. Operationalised: the engine will not prescribe a week with total volume more than 10% above the prior week's total. Override is not allowed for non-medical reasons (and the medical "override" is a return-to-training ramp after a documented break — see [[20_return_to_training]]).

The coach defends this rule by mechanism, not by authority:

> *"Your muscles can absorb the jump — they adapt in days to weeks. Your tendons can't — they adapt in months (T07: muscle 2-4 wk, tendon 3-6 months). A 20-30% volume spike is the dominant tendinopathy trigger (Quarmby 2023). Staying inside 10% keeps you progressing across years, not just weeks."*

If a user has *missed* prior weeks (illness, travel, life), the cap resets against the user's actual chronic load — not against the most ambitious recent week. See [[20_return_to_training]] §3.

### 5. Morning readiness — the same-day decision

There is no validated objective threshold (HRV, RHR, sleep score) that universally predicts a missed session vs a productive one. Hörst Ch.12 §5.8 (cortisol, behavioral mechanisms) + T07 + Watson 2017 sleep evidence converge on a **multi-signal subjective checklist** as the v1 approach. The morning-of checklist:

| Signal | Green | Yellow | Red |
|---|---|---|---|
| **Sleep last night** | ≥7 h, felt rested on waking | 5-7 h or restless | <5 h or wide-awake from broken sleep |
| **Mood** | Engaged, looking forward to session | Flat, going through motions | Irritable, dread, low motivation |
| **Body** | Soreness gone or mild | Localised stiffness/soreness from last session | Joint/tendon pain (not muscle), unusual whole-body fatigue |
| **Resting HR (if tracked)** | At baseline | ~5-7 bpm above baseline | ≥10 bpm above baseline sustained 2+ days |
| **Last 3 sessions RPE trend** | Stable or trending down at same prescription | Slight upward trend (1 pt) | 2+ point upward trend or sessions cut short |

**Decision logic:**

- **All green or one yellow** → train as prescribed.
- **2-3 yellows** → train, but cap session intensity at RPE 7 (drop the top-end work, keep the warm-up + technical / volume content). Document so the engine can adjust the next week's prescription.
- **1 red or ≥3 yellows** → active-rest day (light traverse / mobility / antagonist — see [[09_recovery_sleep]] §5.7). Move the prescribed session, don't drop it.
- **2+ reds** → full rest day. If the pattern persists 3 consecutive checks, the coach surfaces it (this is the *engine's* signal that NFOR may be developing — go to §6).

The coach never asks the user to push through a red. **The cost of a missed session is hours; the cost of triggering NFOR is weeks.**

### 6. When the coach must escalate to a sports physician

These thresholds are **non-negotiable** referral triggers, derived from Meeusen 2013 OTS criteria + Hörst Ch.13 + clinical practice:

- **Persistent resting HR elevation** ≥10 bpm above the user's baseline, sustained 7+ days, with no explanatory illness.
- **Sleep disturbance** — inability to fall asleep or stay asleep persisting >2 weeks at a level beyond the user's normal pattern, *combined* with any other signal below.
- **Unintended weight loss** of any amount accompanied by training fatigue (the combination is more important than any single number — see [[L0_safety_hard_rules]] D64 + [[14_female_age_youth]] §7 for RED-S framing).
- **Repeated minor illness** — colds / GI upset / lingering low-grade infection recurring inside 4 weeks (immune suppression is a OTS hallmark; Meeusen 2013).
- **Mood disturbance** — persistent low mood, anhedonia (loss of climbing pleasure specifically counts), or anxiety beyond the user's normal pattern lasting 2+ weeks.
- **Performance crash** — sudden inability to execute previously-easy tasks (RPE 9 on what was RPE 6 last month) that doesn't recover after 2 weeks of reduced load.

When any **two** of the above co-occur, the coach script is:

> *"The pattern you're describing — [name the two signals] — is in the territory where a sports physician needs to look. This isn't something a training app can or should diagnose. Non-Functional Overreach and Overtraining Syndrome share these signatures, but so do iron deficiency, thyroid issues, viral aftereffects, sleep apnea, and several other things — none of which I can sort. I'm pausing your progression and dropping volume; please get bloodwork and talk to a sports-medicine doctor. We'll resume when you have an all-clear."*

The coach does **not** diagnose. The coach **does** name the pattern, **does** pause the engine's progression, and **does** insist on the referral. See [[L0_safety_hard_rules]] (Coach behavior section: "If user-supplied evidence contradicts a rule, surface").

### 7. RPE trend interpretation

The audit (§4.1 UC17, Q-20) flags RPE-trend interpretation as a UC17 gap. The v1 rule:

- **Same prescribed load, RPE drifting up by 1 point over 2 sessions** = noise; could be sleep, hydration, life stress.
- **Same prescribed load, RPE drifting up by 2 points over 3 sessions** = signal. The user is working harder for the same output — a textbook NFOR precursor. Coach surfaces; engine inserts deload at next checkpoint.
- **Same prescribed load, RPE dropping by 1-2 points over 3+ sessions** = adaptation occurring. Engine increases prescription (within D71 cap).
- **RPE 9-10 on what was RPE 7-8 last week, no obvious cause** = single-session red flag. Coach asks: sleep, illness, life stress in the past 48 h? If none, this is the start of a regression signal — watch the next session before acting.

**The trend matters more than the point.** A single high-RPE session is noise. A trend across multiple sessions is the signal.

### 8. Central fatigue — why "felt fine yesterday" doesn't mean "fine today"

Hörst Ch.12 §2.1.5 (citing Bompa 1983): **nerve cells recover up to 7× longer than muscle cells.** This is the physiological reason why:

- A climber can feel fine on day 1 of a successive-hard-day block, then "off" for days after — without specific muscle soreness.
- Heavy campus / max-hangboard / projecting blocks have a delayed CNS cost that surfaces 2-4 days later.
- After a series of back-to-back hard sessions, "I still feel off after a few rest days" can need **2-10 additional rest days** — not a deload-week, an actual extended rest.

Coach framing for the user:

> *"Your fingers tell you when your fingers are ready. Your nervous system doesn't tell you the same way. If you're flat across multiple sessions with no obvious cause, that's often central fatigue — the nerve recovery side, not the muscle side. The fix isn't a harder warmup; it's 3-7 more days of low-CNS-cost work (technique, easy volume, antagonist) before re-attacking high-recruitment sessions like max hangs or campus."*

### 9. The "low ACWR" question (UC21 gap)

Audit §4.1 Q-24 noted: "What if my ACWR is 0.7 — am I undertraining?" The honest answer: ACWR 0.7 sustained for 2+ weeks means your acute load is 30% below your chronic average — you are **detraining-leaning**, not yet detraining. Detraining onset for recently-acquired aerobic gains is ~2 weeks (Mujika & Padilla 2000a, see [[20_return_to_training]]); strength holds longer (3-4 weeks). Action: if intentional (taper, life event), no concern. If unintentional, the next week's prescription should be rebuilt toward chronic (still within D71 cap from the *current* acute, not from the prior chronic — overshoot is the injury risk, not undershoot).

---

## How the engine applies this

- **D69 (ACWR monitoring)** — engine computes 7-day acute and 28-day chronic load (load = duration × RPE); flags ACWR <0.8 (undertraining trend) and >1.3 (elevated injury risk); inserts deload at >1.5 sustained.
- **D70 (overtraining detection heuristics)** — engine watches three signals (performance regression, RPE elevation at constant load, session-completion rate); two signals trigger deload, three trigger progression pause + coach escalation.
- **D71 (≤10% weekly volume cap)** — hard cap on week-over-week volume increase. Reset against actual chronic, not prior peak, after a break.
- **D68 (injury history)** — injury history from onboarding tightens the ACWR upper band for affected body regions (e.g., prior elbow tendinopathy → ACWR cap 1.2 for upper-body pulling work for 12 months — see [[L0_safety_hard_rules]] D68).
- **Morning readiness** — surfaced via a quick check-in pattern; the engine adjusts the day's session intensity cap based on the answer (RPE 7 cap on yellow, swap to active rest on red).
- **What the engine does NOT do (v1):** HRV-based readiness scoring, automated sleep-data integration, formal OTS scoring (POMS, Profile of Mood States — research instrument). These are v1.1+ candidates; v1.0 ships with the heuristics above.

---

## When user asks…

**"I slept 5 hours, should I train today?"**

Use the readiness checklist in §5 — sleep is one signal, not the decision. 5 hours puts you in the yellow column. If everything else is green (mood OK, no soreness beyond expected, RPE trend stable last 3 sessions), train at RPE 7 cap — drop the top-end work, keep the technical / volume content. If sleep is consistently <7 h (Watson 2017: <7 h is associated with elevated injury risk in athletes), the engine biases volume down across the week; surfacing this honestly is more useful than pushing through one day at a time. **Don't moralize about the sleep.** A user working 50 h/week with kids isn't sleeping less because of poor discipline; they're sleeping less because of life — and the engine's job is to make progress possible inside that reality (see [[19_lifestyle_integration]]).

**"My RPE was 9 in last session. What does that signal?"**

One session is noise. Possible causes: sleep, hydration, life stress in past 48 h, a prescription that was too high (engine error — surface it). What the coach asks first: was this the *same* session you'd done before at RPE 7-8, or new content? If new, RPE 9 may just mean the new stimulus surprised the system. If same, watch the next session before acting. If next session is also RPE 9 at the same prescription, that's the start of a regression signal (§7) — engine drops the next prescription one notch, coach watches the third session.

**"My ACWR is 1.5 for two weeks. What do I do?"**

Deload now — the engine should already have flagged this. Concretely: drop the *next* week's total volume by 50%, hold intensity (don't reduce session intensity, reduce the number of sessions and the within-session volume). Reassess after the deload week. The deload is not optional and not a failure — sustained ACWR >1.5 is the empirical injury-onset zone for overuse injuries (Quarmby 2023). The cost of the deload week is one week of training; the cost of triggering tendinopathy is 6-24 weeks.

**"I haven't trained for 3 weeks. Can I jump back into my Performance phase?"**

No. See [[20_return_to_training]] for the full ramp logic. Headline: <2 weeks off, resume at 70% of pre-break loads with RPE 7 cap for 2 sessions; 2-4 weeks off, restart from the previous phase end, not Performance; >4 weeks off, retest and restart from Base. The D71 ≤10% cap is computed against your *current* (post-break, near-zero) acute load — not against your pre-break peak. Don't try to undo the break in one week; the tendons can't.

**"How do I tell normal post-session fatigue from overtraining?"**

Timescale and pattern. Normal fatigue: noticeable 1-2 days after a hard session, gone by day 3-4, doesn't recur until you train again. Functional overreach (planned or unplanned): you feel flat for ~7-10 days after a hard block, then bounce back stronger than baseline (supercompensation). Non-functional overreach: the flat period extends past 14 days *and* you see two or more of the §6 escalation signals (RHR drift, persistent mood, repeat illness, weight change, sleep disruption). OTS: persistent for months, requires medical workup. The coach's job is to spot the FOR→NFOR transition (the §6 list) and surface it; the diagnosis is a sports physician's job, not the engine's.

**"Should I get an HRV tracker?"**

Optional. HRV (heart rate variability) is a research-validated readiness signal (lower HRV correlates with elevated sympathetic load and reduced readiness). v1 of the engine does not consume HRV input — the readiness checklist (§5) is the user-facing protocol. If you already track HRV and see a sustained dip (more than 1 SD below your personal baseline) alongside any yellow signal from §5, treat it as a confirming signal — drop the day's intensity cap. Treat HRV as one input among several; no single signal is sufficient.

**"I feel mentally done with training but my body feels fine. Is that overtraining?"**

The mental side of the overtraining continuum is real and named in Meeusen 2013 — anhedonia (loss of pleasure from previously-enjoyable activity, specifically including the sport) is on the NFOR criteria list. If this has lasted 2+ weeks and you're seeing any of the body-side signals from §6, treat as the escalation pattern. If it's a recent feeling without body signals, this is often closer to a motivation / SDT issue — see [[15_goal_setting_motivation]] §3 (the cycle of improvement) and the autonomy framing in [[L1_coach_voice]]. Reframing the goal or taking a deliberate week off may unwind it; if it doesn't, treat as §6.

---

## Sources

- Meeusen R et al. 2013. Prevention, diagnosis, and treatment of the overtraining syndrome — joint consensus statement of the European College of Sport Science and American College of Sports Medicine. *Med Sci Sports Exerc* 45(1):186-205.
- Quarmby A et al. 2023. Risk factors and injury prevention strategies for overuse injuries in adult climbers: a systematic review. *Front Sports Act Living* 5:1269870.
- Gabbett TJ. 2016. The training-injury prevention paradox: should athletes be training smarter and harder? *Br J Sports Med* 50:273-280.
- Hulin BT et al. 2015. The acute:chronic workload ratio predicts injury. *Br J Sports Med* 50(4):231-236.
- Hörst EJ. 2022. *Training for Climbing* (3rd ed.), Ch.12 — Accelerating Recovery (3-period model, central fatigue 7× rule, active rest).
- Watson AM. 2017. Sleep and athletic performance. *Curr Sports Med Rep* 16(6):413-418.
- Bompa T. 1983. *Theory and Methodology of Training* — central fatigue / nerve cell recovery.
- Firestone J. 2022. *Overtraining in climbers* — Hooper's Beta synthesis.
- Smith LL. 2003. Overtraining, excessive exercise, and altered immunity: is this a T helper-1 versus T helper-2 lymphocyte response? *Sports Med* 33(5):347-364.

---

## Cross-references

- [[L0_safety_hard_rules]] — D68 (injury history permanent gate), D71 (≤10% weekly volume cap), D64 (no body-comp guidance — RED-S signals route through here, not weight-loss advice).
- [[01_periodization]] — deload mechanics + planned FOR / Performance overreach.
- [[09_recovery_sleep]] — 3-period recovery model + active-rest day content.
- [[13_tapering_redpoint]] — planned FOR + taper interaction.
- [[14_female_age_youth]] — D83 recovery multiplier 40+ (recovery-debt accumulates faster).
- [[16_assessment_interpretation]] — test regression as one of the three D70 signals.
- [[19_lifestyle_integration]] — life stress + central fatigue (sleep deficit pattern under work demands).
- [[20_return_to_training]] — recovering chronic load + the post-break ACWR reset.
