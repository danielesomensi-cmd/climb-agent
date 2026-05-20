# L3 — Pulling Strength

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC3 (primary). **NEW file** built for v1.0 — fills the UC3 gap from audit §2.
> **Token target:** ~3,500.
> **Status:** v1.0 — ready.
> **Source files distilled:** `01_performance_determinants.md` (T01, 5-axis pulling content), `literature_review_climbing_training.md` (pulling sections), `02_finger_strength.md` (T02 — context for pulling vs finger distinction), decision consolidation D38, D39, D52, D84, D84b, audit §2 (UC3 gap) + §4.1 (UC3 mental tests). Contact strength is acknowledged but engine doesn't measure it (deferred).
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 + §2 (UC3 gap explicit).

---

## Quick reference

Upper-body pulling strength is the second-largest physical predictor of climbing performance after finger strength (MacKenzie 2020: adj R² = .77 in males, .62 in females for the pulling-strength-led model). The engine assesses pulling on two tests — bodyweight gate (`test_pullup_bw`) and weighted 1RM (`test_max_weighted_pullup`) — and trains it through pull-up variants, lock-offs, and eccentric pull-ups for beginners. **Pulling strength is distinct from finger strength** (they correlate but train differently) and **distinct from contact strength** (RFD, deferred from the engine). Don't conflate the three when interpreting weakness.

---

## Core findings

### 1. Pulling, finger, contact — three different things

Climbing requires force from the fingers (hold contact), from the arms (lifting bodyweight up), and from explosive recruitment (dynamic moves onto small holds). These overlap but are not the same:

| Axis | What it measures | Test | Adapts via |
|---|---|---|---|
| **Finger strength** | Forearm flexor MVC through grip | 7s max hang on 20 mm (D85) | Hangboard, climbing, lifting edge |
| **Pulling strength** | Upper-body lat / bicep / scapular pulling force | Pull-up test (BW reps + 1RM weighted) | Pull-ups, lock-offs, weighted pulls |
| **Contact strength / RFD** | Speed of force generation (ms to peak) | Campus board, power slap (not in engine v1) | Campus, dynamic moves, overcoming isometrics (Nelson) — **not directly measured** |

**Engine v1 measures finger and pulling. Contact strength is acknowledged but not tested or directly prescribed.** The coach can speak about RFD as a concept (especially for bouldering) but cannot claim the engine quantifies it. When users ask "what's my contact strength score?", redirect: "the engine doesn't measure that — for v1 we infer it indirectly through bouldering grade vs. finger strength gap."

### 2. Why pulling matters

**MacKenzie 2020** (*Int J Sports Physiol Perform*) — large multivariate study, 44 males (5a-8a) + 33 females (5a-7b+), 47 variables each:
- 23/47 variables correlated with climbing ability in males (r = 0.34-0.77).
- **Shoulder power and endurance** (max pull-ups, avg arm crank power, bent-arm hang) were the *main* determinants alongside finger strength. Combined model: adj R² = .77 males, .62 females.
- Training intervention: increasing main determinants by 42-67% improved climbing 2-3 grades.

**Baláš 2012** (*Eur J Sport Sci*): structural model combining grip strength + bent-arm hang + finger hang + body fat + climbing volume + experience explained **97%** of variance in n=205 climbers. Bent-arm hang (a pulling endurance proxy) was a load-bearing component.

**Magiera 2013:** of 7 variables explaining 77% of climbing performance variance, isometric finger endurance ranked #4 (canonical weight 0.340) — that test includes a strong upper-body holding component beyond pure forearm.

Lattice data (n=901) confirms pulling strength becomes more important *relatively* as users approach V9-V12 boulder grades — finger strength still dominates raw rank, but pulling adds explanatory power at higher grades.

### 3. The two-test architecture (D84b)

The engine tests pulling on two stages:

- **`test_pullup_bw`** — bodyweight pull-up reps to failure. This is a *gate*: users below 1 strict bodyweight pull-up don't get weighted pull-up testing or weighted pull-up training (beginner protocols only — see §5).
- **`test_max_weighted_pullup`** — once the gate passes, 1RM weighted pull-up using **Brzycki estimation** (D38). The user does AMRAP at a sub-max load, the engine estimates 1RM from rep count.

Why two stages? Bodyweight pull-up reps measure pulling endurance + capacity (useful for beginners and intermediates). Weighted 1RM measures pure pulling strength (more relevant at advanced levels). A single test can't capture both ends of the range cleanly.

### 4. Effort Level prescription by user level (D52)

The engine prescribes pulling-strength sessions using **Effort Level (EL)** rather than %1RM (D34 — climbing uses EL because hold geometry and grip type make %1RM unstable). Concrete EL bands:

| User level | Pull-up content | EL target | Reps | Sets | Rest |
|---|---|---|---|---|---|
| Beginner (no BW pull-up) | **Eccentric pull-ups** (D39 — not bands) | EL 7-8 | 3-5 | 3 | 3 min |
| Beginner (1-3 BW pull-ups) | BW pull-ups to RPE 8, scapular pull-ups | EL 7-8 | 3-6 | 3-4 | 2-3 min |
| Intermediate | Weighted pull-ups | EL 7-8 (80-87% 1RM) | 4-6 | 3-5 | 3-4 min |
| Advanced | Weighted pull-ups + lock-off variants | EL 8-9 (87-93% 1RM) | 2-5 | 4-5 | 3-5 min |

**D39 specifically:** eccentric pull-ups are the beginner progression, not assisted pull-ups with bands. Reason: eccentric loading produces neural recruitment + early strength gains; bands offload at the top of the rep (where the hardest leverage is) and accustom the climber to incomplete ROM. Engine prescribes a 3-4 second eccentric lower from the top position.

### 5. Lock-off and contact strength acknowledgments

**Lock-offs** (sustained hold at intermediate joint angles) train climbing-specific positions where most of the time-under-tension lives — climbers don't do reps, they hold positions and reach. The engine includes lock-off variants (one-arm lock-offs, frenchies, climber's pull-ups) at advanced levels. Evidence: less direct than pull-up evidence; rationale is specificity.

**Contact strength / RFD** is the speed of force generation. Boulderers' RFD is ~36.7% higher than sport climbers (Fanchini 2013); RFD200ms distinguishes climbing levels (Levernier & Laffaye 2019); boulder grade prediction improves when RFD is included. **Engine v1 doesn't measure RFD** — it requires a high-rate force sensor (Tindeq Progressor or similar) that most users don't have. The coach can describe the concept but defers training prescription to the limit-bouldering and campus-board sessions in the catalog (campus gated by D41 / L0).

When a user asks "should I train contact strength?", route to: limit bouldering for dynamic moves, campus board *if* prerequisites pass (D41, L0), overcoming isometrics on the hangboard (Nelson — see `02_finger_strength.md`).

### 6. Finger vs pulling — which is the bottleneck?

Common user question. Heuristic:
- Both axes high, climbing grade lower than predicted → technique or mental (see `06_technique_movement.md`, `07_mental_fear_focus.md`).
- Finger axis high, pulling axis low → upper-body limit reaching, body tension on overhang. Prescribe weighted pull-ups + lock-offs.
- Pulling axis high, finger axis low → can hold the position but not the holds. Prescribe hangboard work + climbing volume on smaller edges.
- Both axes low → climbing volume first (beginner level) or assessment retest (something off).

Lattice n=901 finding: at lower grades, finger dominates; at V9-V12, pulling and PE rise in relative importance. At V13+, multiple factors compress — no single axis dominates.

### 7. Concurrent training and pulling

Heavy pulling training (>85% 1RM, low rep) competes for recovery with hangboard work. The engine schedules pulling alongside hangboard in the same session (both upper-body neural work) rather than on separate days, to consolidate the recovery debt into fewer high-load days. Don't schedule heavy pulling the day before a max-hang session — same recovery system.

Lower-body and conditioning pulling (rows, face pulls, scapular work) belong on different days from finger-strength work — see `12_antagonist_postural.md`.

---

## How the engine applies this

- **D84b two-test architecture:** `test_pullup_bw` gates `test_max_weighted_pullup`. Users below 1 BW pull-up cannot select the weighted test.
- **D38 Brzycki estimation:** AMRAP at sub-max load → 1RM estimate via Brzycki formula. The user doesn't need to attempt true 1RM.
- **D39 eccentric default:** beginner pulling sessions prescribe eccentric pull-ups, not banded assists.
- **D52 EL table:** session prescriptions use the EL band per user level.
- **Lock-off catalog:** intermediate+ sessions include one-arm lock-off and climber's pull-up variants.
- **Contact strength:** not directly measured. Engine v1 doesn't have a `contact_strength` axis (deferred). Training stimulus comes from limit bouldering and campus (gated D41).
- **Pull-up + hangboard pairing:** session planner co-locates heavy pulling and max hangs on the same day to consolidate recovery debt.

---

## When user asks…

**"What does my pull-up score mean for my climbing?"**

Reference Lattice norms (see `16_assessment_interpretation.md` for tables). Rough mapping: BW+25 kg weighted pull-up 1RM is around the advanced range (7c+/8a redpoint, V7+ boulder). Don't make it deterministic — climbing grade depends on the *combination* of pulling, finger, PE, and technique. If pulling is your strongest axis and you climb below predicted grade, the limit is finger or technique.

**"Should I prioritize lock-off training?"**

Depends on the failure mode. Lock-offs train sustained holds at intermediate angles — useful if the user fails moves at the *position* (can't hold while reaching) rather than at the *contact* (can't grip the next hold). If failures are about contact strength on dynamic moves, lock-offs are the wrong tool — go to limit bouldering or campus (if gates pass, D41).

**"How does pulling strength translate to contact strength?"**

They're related but distinct. Pulling = max force generation (slow, sustained). Contact = speed of force generation (RFD, dynamic). High pulling strength gives a higher *ceiling* for contact strength but doesn't automatically transfer — RFD is its own adaptation (Levernier & Laffaye 2021). Boulderers tend to have both; sport climbers often have pulling without RFD. The engine v1 doesn't measure RFD directly; if the user wants to train contact strength specifically: limit bouldering, dynamic moves, overcoming isometrics on the hangboard.

**"Why am I tested two ways (BW pull-ups + weighted)?"**

D84b architecture. The BW test is a gate and an endurance measure — informative for beginners and intermediates. The weighted test measures pure pulling strength — informative for intermediates and advanced. One test alone misses information at the other end of the range. Brzycki estimation (D38) means you don't max out on the weighted test — sub-max load + AMRAP → 1RM estimate.

**"Why don't bands count as eccentric pull-ups?"**

D39. Bands offload at the top of the rep (where the lever is hardest), so the climber pulls through reduced ROM and skips the position that limits real climbing. Eccentric pull-ups (jump to top, lower in 3-4 s) load the full ROM under control — neural recruitment + early hypertrophy + better transfer to climbing position. Bands have a role in shoulder rehab and scapular activation work, not in primary pull-up progression.

**"I'm at 1.6 BW MVC on finger strength but my pull-up is only +10 kg. Which do I train?"**

Pulling is the weak axis here. 1.6 BW finger at +10 kg weighted pull-up indicates the climber can grip more than the upper body can leverage. Prescription: weighted pull-up cycles at EL 8-9 (3-5 reps, 4-5 sets, 3-5 min rest), 1-2 sessions/week, paired with reduced hangboard volume (one max-hang session/week instead of two — D49 already prevents doubling up). Expect 4-6 weeks before retesting.

---

## Sources

- MacKenzie R et al. 2020. Physical and physiological determinants of rock climbing. *Int J Sports Physiol Perform* 15(2):168-179.
- Baláš J et al. 2012. Hand-arm strength and endurance as climbing performance predictors. *Eur J Sport Sci* 12(1):16-25.
- Magiera A et al. 2013. Structure of performance of a sport rock climber. *J Hum Kinet* 36:107-117.
- Levernier G, Laffaye G 2019, 2021. RFD200ms and climbing ability — multiple publications.
- Vereide V et al. 2022. Peak force and RFD in male intermediate, advanced, elite climbers. *Int J Sports Physiol Perform*.
- Fanchini M et al. 2013. RFD comparison boulder vs sport climbers.
- Brzycki M. 1RM estimation formula (used in D38).
- Lattice Training 2025. Predictors for bouldering performance by ability level (n=901).
- Saeterbakken AH et al. 2024. Resistance training and climbing performance — narrative review. *Sports Med Open* 10(1):10.
