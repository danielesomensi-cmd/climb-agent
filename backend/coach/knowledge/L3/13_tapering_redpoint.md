# L3 — Tapering & Redpoint Prep

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC13.
> **Token target:** ~4,000.
> **Status:** v1.0 — ready, with documented coverage gap (see below).
> **Source files distilled:** `docs/research_kb/04_periodization.md` (T04 — Mujika/Hooper's Beta taper science), `horst_ch12_recovery_synthesis.md` (active rest, post-attempt recovery, post-trip), decision consolidation D20, D22. NEW file — synthesized rather than 1:1 distilled.
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table, row `13_tapering_redpoint`).

> **v1.0 coverage gap:** Lattice Training 2019 taper newsletter and a dedicated Hörst redpoint chapter are referenced in the audit as targets for distillation but are not yet integrated as primary sources. v1.1 will fold in the Lattice protocol detail (sport-route specific day-by-day cadence) and Hörst's redpoint-tactic detail (skin program, attempt budgeting, trigger word). v1.0 covers the science (Mujika & Padilla taper math), the engine's two implemented modes (D20 pre-Performance taper, D22 competition taper v2), and the operational pre-trip / pre-redpoint / post-trip pattern fully — what's missing is sport-specific protocol detail, not foundational content. **Operative principle:** when the user asks for a sport-route taper specifically, coach offers the protocol below + flags it as principle-based, not Lattice-specific.

---

## Quick reference

A taper is a deliberate reduction in training volume — with intensity **maintained** — designed to dissipate fatigue while preserving fitness, producing supercompensation at a planned moment. The science (Mujika & Padilla 2003) is mature: 0.5-6% performance improvement when done right. The engine ships **two taper modes**: (1) pre-Performance phase overreach + taper inside every macrocycle (D20, active in v1), (2) trip / competition taper triggered by goal date (D22, partial v1 — coach can speak generally, full multi-week protocol is v2). Mistakes that wipe the benefit: cutting intensity, cutting frequency below 80%, or adding new stimulus in the final week.

---

## Core findings

### 1. What a taper actually does

Supercompensation isn't mysticism — it's the practical consequence of the **fitness-fatigue model** (Bannister 1976). Training simultaneously produces fitness gains (decay slowly) and fatigue (decays fast). When fatigue is allowed to dissipate without losing fitness, the net performance curve peaks transiently above baseline. That peak is the taper's purpose.

Two things matter for the math to work:

- **Fitness must be preserved while fatigue clears.** This is why intensity stays high: detraining the neural/anaerobic side starts inside 7-10 days. Volume can drop hard because volume is the dominant fatigue driver.
- **The peak is transient.** Mujika & Padilla 2003 estimate the peak window is roughly 48-96 hours wide. That's the engine's targeting window for a trip day or a comp.

The most common mistake is treating a taper like a deload: cutting intensity *and* volume. Intensity cuts cost fitness; the user arrives at the trip rested but flat.

### 2. The numbers (Mujika & Padilla 2003)

The Mujika & Padilla 2003 review of taper studies (*Med Sci Sports Exerc* 35:1182) is the controlling source. Headline parameters:

| Parameter | Recommended range | Why |
|---|---|---|
| Performance gain | 0.5-6% | Small in absolute terms, decisive at limit |
| Volume reduction | 60-90% | Volume is the dominant fatigue driver |
| Intensity | **Maintain** | Detraining starts inside 7-10 days |
| Frequency reduction | ≤20% | Mujika 2012: ≥30% frequency cut wipes the gain |
| Duration | 4-28 days, sport-dependent | Endurance sports taper longer (running ≈14d); strength/power taper shorter (≈7d) |
| Taper shape | Progressive nonlinear > step | Exponential volume decay outperforms a single big cut |

For climbing specifically, the closest analogs are mixed strength-endurance sports. The engine defaults: **7-day taper for a single redpoint goal**, **14-day taper for a multi-day trip with cumulative climbing volume**, **21-day protocol (overreach + double cut) for a target competition** (D22, currently v2).

### 3. The engine's two implemented modes

**Mode A — Pre-Performance phase taper (D20, v1 active):**

Built into every macrocycle. The week before the Performance phase carries a deliberate overreach (volume +10-15%) then a brief taper into Performance. Mechanism: the overreach loads fatigue; the early Performance week absorbs the supercompensation. When the user says *"I felt terrible last week and now the plan got easier"*, this is the protocol working as designed. See [[01_periodization]] §4.

**Mode B — Trip / competition taper (D22, partial v1):**

If the user has set a goal date (trip, comp, project window), the engine schedules a taper terminating on that date. v1 implements the **trip taper (7-14 days)** and a **simplified pre-redpoint taper (3-5 days)**. The full **3-week competition taper** (overreach → -25% → -50%) is v2. Coach can describe it (per §5 below) but must flag that the engine doesn't auto-prescribe it in v1 — the user adapts manually.

### 4. The 7-day trip taper (engine-prescribed)

For a sport-climbing trip lasting 3-10 days:

| Day | Sessions | Volume vs normal | Intensity | Notes |
|---|---|---|---|---|
| T-7 | 1 quality | 70% | At normal max | Last hangboard session — moderate cluster, not exhaustive |
| T-6 | rest | — | — | Skin recovery |
| T-5 | 1 quality | 60% | At ~85% max | Limit boulders or limit routes, short session |
| T-4 | rest | — | — | — |
| T-3 | 1 light | 50% | Easy | Movement quality, no max effort, no skin damage |
| T-2 | rest | — | — | Skin program, mental rehearsal |
| T-1 | rest or 10-min activation | 0-10% | Easy | Optional easy traverse + warm-up repeaters on travel day |
| **Trip day 1** | **Climb** | — | — | First day usually feels slow — that's fine, fitness arrives ~day 2-3 |

Two things the user often gets wrong:

1. **They train hard at T-3 to "feel ready"** — that session loads fatigue that won't clear by T0. Hard sessions inside the final 72-96 h erase the taper benefit (Mujika & Padilla 2003).
2. **They take 5+ days completely off** — frequency reduction beyond 20% is the dominant cause of "tapered but flat" arrival (Mujika 2012). One short maintenance session inside T-2 to T-1 protects neural quality without loading fatigue.

### 5. The 21-day competition taper (D22 — v2 in engine; coach explains it)

For target competitions or single high-importance redpoint dates, the literature-backed protocol is three weeks (Hooper's Beta 2024 synthesizing Mujika):

| Week | Volume | Intensity | Frequency | Content character |
|---|---|---|---|---|
| Week -3 (overreach) | +10-15% | Normal | Normal | Push the fatigue floor — last hard hangboard cycle, limit boulder volume, last PE volume push |
| Week -2 (first cut) | −25% | **Maintain at near-max** | −1 session OK | Drop the volume; keep the quality. No new stimuli. Last attempts on project-level grades. |
| Week -1 (second cut) | −50% | **Maintain at near-max** | −1 session OK | Short sharp sessions. Drop supplemental strength entirely (hangboard, weighted pulls). Climbing-only. |
| Comp / project day | — | — | — | Warm-up + perform |

The asymmetry — keeping intensity high while volume crashes — is the entire mechanism. The week -1 session might be three boulder problems at limit, not five; one route at limit, not three. Quality over volume in the most literal sense.

**v1 limitation:** the engine ships Mode A (pre-Performance taper, always on) + Mode B 7-day trip taper. It does not yet auto-prescribe the 21-day overreach + double-cut. If the user has a date 3+ weeks out, the coach can talk them through this protocol; the user adapts the plan manually in week-by-week dialogue.

### 6. The pre-redpoint mini-taper (single-route focus)

For a single project the user is close on (going for one specific route in the next 3-5 sessions), a mini-taper:

- **3 days before send attempt:** last quality session — not on the project; one parallel-grade route or limit boulders. Skin survives.
- **2 days before:** rest or 10-min movement-quality session. No max efforts.
- **1 day before:** rest. Skin program, visualization, light mobility.
- **Send day:** thorough warm-up ([[12_antagonist_postural]] §warm-up integration), then attempt cluster (typically 2-3 attempts with 20-40 min rest each, then walk away — diminishing returns and skin loss dominate after attempt 3).

The mini-taper is shorter because the goal is one route, not a sustained trip — the fitness-fatigue math is simpler. Don't waste a week of training for it; 3 days of intentional rest is enough.

### 7. Skin and logistics (the underdiscussed taper layer)

A taper that ignores skin is half a taper. The mechanism: hard climbing in the final week leaves skin tender, glassy, or cracked at exactly the moment the user needs maximum grip security. Skin protocol that complements the training taper:

- **T-7 to T-3:** finish each session with a skin file pass. Moisturize at night (climbing-specific salve or plain lanolin).
- **T-3 to T-1:** no abrasive training surface (avoid wood/skin-heavy plywood at the gym; prefer plastic-only).
- **T-2 and T-1:** no skin damage. If the user must climb, route or moderate boulder only.
- **Travel/comp day morning:** light file pass if needed, hydrate normally (over-hydration the morning of a comp doesn't help; just don't show up dehydrated).

For multi-day trips: the **third day** is the typical skin failure point (Hörst Ch.12 general recovery framing — skin atrophies under sustained climbing load like any other adaptation, and Day 3 is when accumulated wear meets minimum repair time). Plan for it: hardest projects on Day 1-2, lower-intensity day or rest on Day 3, return to projects Day 4-5.

### 8. Mental tapering

Less-cited than physiological tapering, but Hörst Ch.3 and the SDT framing of [[15_goal_setting_motivation]] both reinforce: the final 48-72 h before a target attempt benefits from cognitive *de-load* as much as physical. Practical content:

- **Mental rehearsal** of the route or boulder — 5-10 min daily across T-3 to T-1, eyes closed, sequencing through specific holds and movements (Hörst Ch.3 visualization protocol).
- **Cessation of grade-anxiety conversations.** Stop reading beta forums, stop comparing recent sends to projected grade. The conversation is no longer useful and elevates baseline arousal.
- **Sleep priority +1.** A target attempt benefits from one extra hour of sleep in the final 48 h more than from any extra training (Watson 2017 — sleep <7 h elevates injury and degrades reaction time).
- **Caffeine periodization.** If the user uses caffeine daily, reducing intake for 3-5 days pre-attempt restores receptor sensitivity (Hörst Ch.11) for a meaningful day-of effect. If they don't use caffeine, don't add it as a new variable on send day.

### 9. Post-trip recovery (the un-discussed half)

A trip or competition is a high-volume high-stress event. The recovery from it is its own protocol, often skipped because the user thinks "trip = rest week" and shows up healthy on paper but flat for weeks after.

Engine pattern for post-trip week:

- **Days 1-3:** active rest. Easy traversing, mobility, antagonist work, walks. Intensity ≤50% normal. Sleep priority. **No** hangboard, **no** limit attempts, **no** PE intervals. Hörst's 3-period recovery model ([[09_recovery_sleep]]): the first window is dominantly tissue and skin repair.
- **Days 4-5:** moderate session — climbing volume at ≤70% intensity, technique focus. Test how forearms and fingers feel; the *flash pump signal* (heavy pump on the first climb) is the cue that capillary repair is incomplete.
- **Days 6-7:** if flash pump cleared and skin is back, resume normal phase content. If not, extend recovery 2-3 more days.
- **Don't immediately restart in Performance phase.** Drop back to the prior phase end (typically PE or Build). The macrocycle resumes from where the user left off, not where they "should" be on the calendar (engine pattern, see [[20_return_to_training]] when available).

The post-trip user often feels invincible in the first 48 h ("supercompensation from the trip!"), then crashes at day 4-7. The crash is normal; honor it.

### 10. Common failure modes (what wipes the taper benefit)

| Mistake | Why it wipes the gain |
|---|---|
| Cutting intensity along with volume | Detraining starts inside 7-10 days; arrives rested but flat |
| Skipping all sessions in the final week | Frequency drop >30% loses the supercompensation (Mujika 2012) |
| Adding a "test" max hang or limit attempt at T-2 | Loads fatigue that doesn't clear by T0 — the single biggest self-sabotage pattern |
| Trying a new exercise or technique pre-trip | Novel stimulus = soreness arriving at the wrong moment |
| Compensating with a "carb load" without prior practice | GI distress at the wrong moment ≠ the carb loading the user read about (see [[08_nutrition]]) |
| Drinking extra coffee for "energy" on send day | If user is a daily user, no acute effect; if they're not, jittery + suboptimal motor control |
| Believing rest = doing literally nothing | Active rest beats passive rest +35% lactate clearance (Watts 2000, Hörst Ch.12) — light movement helps |
| Ignoring skin | Day-of grip security is destroyed by tender skin; preventable with 3-day skin-light protocol |

### 11. Trip type modifiers (boulder vs sport, single vs multi-day)

The 7-day trip taper above is calibrated for a sport-route trip of 3-10 days. Modifications by goal type:

**Boulder-only trip:**
- Volume of climbing is lower per day but intensity per attempt is maximal. Skin damage is the dominant constraint, not aerobic recovery.
- Shorten the taper to 5 days; emphasize skin program harder.
- Drop hangboard at T-5, not T-7 — boulder strength carries through better than route fitness.

**Multi-pitch / alpine trip:**
- The constraint is endurance and movement efficiency, not max strength.
- Lengthen the taper to 10-14 days but maintain longer easy-climbing sessions to T-4 (mileage protects the aerobic engine the trip will demand).
- Strength can drop earlier; ARC or moderate route mileage to T-4.

**Single redpoint window (1-2 sessions at a project):**
- Use the 3-5 day mini-taper above (§6). The 7-day full taper is overkill and costs gym fitness that the next training cycle will need.

**Comp day (single date):**
- Closest to the 21-day overreach + double-cut (§5) if importance justifies it. For local league or fun comp, the 7-day taper is sufficient.

### 12. When *not* to taper

A taper is a trade — the user spends a week of training adaptation to peak on a date. If the date isn't load-bearing, the trade isn't worth it.

- **Casual outdoor weekend:** no taper. Light Friday session is fine; recover by climbing into the weekend, not by pre-resting.
- **Indoor session at usual gym:** no taper. The plan already includes weekly micro-recovery.
- **Gym session with friends:** social, not performance — don't taper for it.
- **Mid-mesocycle redpoint attempt on a route the user is far from sending:** training continues; the redpoint is opportunistic, not the target.

The user sometimes wants to taper for *every* session that matters emotionally. The honest reply: tapers cost training time; reserve them for dates that justify the cost.

---

## How the engine applies this

- **Pre-Performance taper (D20):** runs automatically in every macrocycle. The transition week from PE → Performance carries the +10-15% overreach; the early Performance week absorbs the supercompensation. See [[01_periodization]] §4.
- **Trip taper (D22 partial v1):** if a goal trip date is set in user state, the engine prescribes the 7-day trip taper above terminating on the trip start date. Cumulative phase weights shift: hangboard exits at T-7, PE exits at T-5, climbing intensity preserved through T-3.
- **Competition taper (D22 v2):** the full 21-day overreach + double-cut is not yet auto-prescribed in v1. Coach can walk the user through it manually if they have a target comp date 3+ weeks out.
- **Mini-redpoint taper:** not a separate engine mode; the user signals "I have one route I'm going for in the next week" and the coach prescribes the 3-5 day pattern from §6 manually.
- **Post-trip recovery:** not yet a discrete engine mode in v1. The week after a trip is treated as a deload week by manual user request, dropping back to prior phase end (see [[09_recovery_sleep]] for the recovery week structure).
- **D71 (≤10% weekly volume increase) applies to the post-trip ramp-back.** The instinct to "make up missed training" after returning is the dominant injury vector for the 2-4 weeks after a trip.

---

## When user asks…

**"I have a trip in 5 weeks — how should I structure?"**

Five weeks gives room for one more meaningful training block + a proper taper. Structure: weeks 1-3 normal training (whichever phase the user is in; if PE or Performance, hold there), week 4 the overreach (+10-15% volume), week 5 the trip taper (the 7-day pattern in §4 above). If the user is in Base phase 5 weeks out from a trip, the answer is harder honestly — Base adaptations are 6+ week timeline; trip won't see the full benefit. Coach option: shorten Base by 1 week if not yet 4 weeks in, prioritize trip-specific work in the cut weeks. Note the trade-off explicitly.

**"I tried tapering for my last trip but felt flat. What went wrong?"**

Three most likely causes: (1) cut intensity as well as volume — detraining beats supercompensation if the user spent the week doing easy climbing; (2) cut frequency too hard — 5+ days fully off wipes the neural quality (Mujika 2012); (3) snuck in a "test" hard session at T-2 or T-3 — the fatigue from that session doesn't clear by T0. Ask which of the three patterns matches; usually one of them does. Honest framing: tapers fail more often from doing too much rest than from doing too little.

**"Should I taper for a redpoint I have one shot at next weekend?"**

Yes — but not a full 7-day taper. The 3-5 day mini-taper from §6 above. Last quality session 3 days out (not on the project), 2 days of rest with skin program + visualization, send day. A full week of taper for a single redpoint is more rest than the goal needs and costs training fitness the next cycle will want.

**"My trip is 10 days — how do I avoid crashing mid-trip?"**

Two layers. First, the taper before — the 7-day trip taper preserves day-of capacity. Second, the *trip-internal* recovery cadence: hardest projects Day 1-2 (peak skin + peak rested), lower-intensity day or rest Day 3 (skin failure typical), return to projects Day 4-5, second moderate day Day 6 or 7, projects Day 8-9, easy Day 10. Don't try to climb at full intensity every day for 10 days — the third day skin/forearm failure pattern is consistent across climbers. Plan for it.

**"Can I do a 3-week competition taper if I have a comp date?"**

Yes — the protocol is in §5 above. The engine doesn't auto-prescribe it in v1 (Mode B is v2), but the coach can walk through it: week -3 overreach (+10-15% volume), week -2 cut volume 25% but keep intensity, week -1 cut volume 50% with intensity preserved and no supplemental strength. The user adapts the plan week-by-week with coach support. Caveat: the 3-week protocol assumes a competition or similarly high-stakes single date; for a normal trip the 7-day version is enough.

---

## Sources

- Mujika I, Padilla S. 2003. Scientific bases for precompetition tapering strategies. *Med Sci Sports Exerc* 35(7):1182-1187. **Primary source for parameter ranges.**
- Mujika I 2012. Frequency reduction during taper (≥30% loses gains). Cited in Hooper's Beta synthesis.
- Bannister EW 1976. Fitness-fatigue model. Foundational for supercompensation reasoning.
- Hooper's Beta 2024. "Deload Weeks: Progression Hack or Harmful Crutch?" — practical translation of Mujika science into climbing context, 3-week competition taper protocol.
- Watts PB 2000. Active vs passive rest between attempts. Active rest +35% lactate clearance.
- Watson AM 2017. Sleep duration and injury risk in athletes — relevance to final-week sleep priority.
- Hörst EJ 2022. *Training for Climbing* 3rd ed. — Ch.3 visualization (mental tapering), Ch.11 caffeine periodization, Ch.12 active rest and 3-period recovery (post-trip).
- Bompa TO, Buzzichelli C 2015. *Periodization: Theory and Methodology of Training* 6th ed. — general taper theory foundational text.

**Pending v1.1:** Lattice Training 2019 taper newsletter (sport-route specific day-by-day); a dedicated Hörst redpoint chapter distillation (skin program detail, attempt budgeting, trigger-word protocol).

---

## Cross-references

- [[01_periodization]] — pre-Performance taper (D20) inside the macrocycle structure.
- [[09_recovery_sleep]] — post-trip recovery week, Hörst 3-period model, sleep priority.
- [[12_antagonist_postural]] — warm-up integration on send/trip days.
- [[15_goal_setting_motivation]] — mental framing of the target date (process vs outcome goals).
- [[20_return_to_training]] — full return-to-training protocol (when available; v1.1).
- [[L0_safety_hard_rules]] — D71 (≤10% volume increase) controls the post-trip ramp-back.
