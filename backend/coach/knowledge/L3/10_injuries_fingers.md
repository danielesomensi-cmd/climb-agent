# L3 — Injuries Fingers

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC10.
> **Token target:** ~6,000.
> **Status:** v1.0 — ready, with documented coverage gap (see below).
> **Source files distilled:** `docs/research_kb/07_overtraining_injury_load.md` (T07), `horst_ch13_injury_synthesis.md` (finger sections), decision consolidation D68, D71, D72, D80.
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table).

> **v1.0 coverage gap:** Christophersen *Managing Injuries* Part 2 (lumbrical-specific rehab progressions, A2 graded loading protocols) is not part of v1.0. v1.1 will expand the rehab-loading prescription detail with their grade-by-grade timelines and specific loading milestones. v1.0 covers diagnosis recognition, triage, prevention, and conservative initial management; what's missing is the post-medical-clearance graded loading protocol detail, not foundational content. **Operative principle:** Coach never prescribes a rehab return timeline without medical clearance — see "When user asks" and the protocol qualifiers throughout.

---

## ⚠️ Scope boundary (non-negotiable)

climb-agent is a training engine, not a medical or physiotherapy tool. The coach does not diagnose finger injuries, prescribe treatment, or stamp return-to-climb timelines. What this file enables: pattern-recognize what a user is describing, surface the relevant body of evidence, route them to a climbing-aware physio (Vagy / Hooper's Beta network / Christophersen-trained), and adjust engine prescription (load, grip type, volume) while they recover. If the user describes anything beyond a minor tweak — visible swelling, audible pop, persistent pain >2 weeks, bowstringing — the coach's first move is always "see a hand-aware physio before we continue training planning."

---

## Quick reference

Fingers are 52% of all nonfall climbing injuries (Schöffl 2015) — the dominant injury site in the sport. Among finger injuries, pulley tears (30%), capsulitis (18%), and tenosynovitis (17%) are the top three. The crimp grip drives most of them: it produces ~4× tip force on the A2/A4 pulleys (Miro 2021) and combined with eccentric loading (foot slip while crimping) is the primary rupture mechanism. The engine's role is prevention through grip-type defaults (D72: open-hand / half-crimp on hangboard, never full crimp), load progression caps (D71: ≤10% weekly), experience gates (D35), and honoring onboarding injury history as a permanent gate (D68). When a user reports an active finger issue, the coach pauses the training conversation and routes to medical evaluation first.

---

## Core findings

### 1. Epidemiology — what climbers actually hurt

From Schöffl 2015 (n=836 climbers, 911 nonfall injuries):

| Site | % of nonfall injuries |
|---|---|
| Fingers | 52% |
| Shoulder | 17% |
| Hand | 13% |
| Elbow | 9% |
| Other | 9% |

Within fingers, the top 10 diagnoses (Schöffl 2015):

| Injury | Frequency |
|---|---|
| Pulley injury | 30% |
| Capsulitis | 18% |
| Tenosynovitis | 17% |
| Flexor tendon strain | 8% |
| Sprained joint capsule | 5% |
| Flexor tendon ganglion | 4% |
| Collateral ligament injury | 4% |
| Epiphyseal (growth plate) fracture | 3% |
| Lumbrical shift syndrome | 3% |
| Osteoarthritis | 3% |

Two trend shifts since Schöffl's earlier (2003) study: **A4 pulley injuries are now more common than A2** (the textbook used to teach the opposite), and **growth plate fractures in youth climbers have increased ~600%** (Schöffl 2015). The youth trend tracks campus board proliferation and is a key driver of L0 rule D80 (no campus / hypergravity / weighted hangs <16).

Risk factors with consistent evidence (Quarmby 2023 systematic review, 34 studies): higher climbing intensity (grade), bouldering vs lead, reduced finger strength relative to demands, full-crimp grip use, and **previous injury — the strongest single predictor of future injury.** Re-injury rates run 2–5× first-injury rates, which is why D68 treats onboarding injury history as a permanent gate even when the user reports current full pain-free function.

### 2. Anatomy in one paragraph

Finger flexion is produced by forearm muscles (FDS — flexor digitorum superficialis; FDP — flexor digitorum profundus) whose tendons run from the medial epicondyle to the middle and distal phalanges. They pass through a sheath held to the bone by five annular pulleys (A1, A2, A3, A4, A5) and three or four cruciform pulleys (C0–C3). **A2 and A4 are the most important mechanically** (Lin 1989). The lumbricals are four small intrinsic hand muscles that originate from the FDP tendons in the palm — they flex the MCP joint and extend the PIP/DIP joints, and they're frequently involved in single-finger pocket-pull injuries.

Two practical consequences:

- Force at the pulley can be **~4× the force at the fingertip** when crimping (Miro 2021). Hangboard isometric loading + full crimp + eccentric (foot slip) is the trifecta that ruptures pulleys.
- Lumbrical strains are common in single-finger and two-finger pocket pulls — climbers often misread them as "pulley pain" because the location is similar. Diagnosis differentiation is a physio's job, not the coach's.

### 3. Pulley injuries (A2 / A4) — the dominant climbing injury

**Schöffl grading** (clinical standard):

- **Grade I** — pulley strain (microscopic to small partial tear)
- **Grade II** — complete rupture of A4 or partial rupture of A2/A3
- **Grade III** — complete rupture of A2 or A3
- **Grade IV** — multiple ruptures, or rupture combined with lumbrical / collateral ligament damage

Grade I–III are typically managed conservatively (rest, immobilization, taping, graded return). Grade IV usually requires surgical repair (Schöffl 2015). The grading is made by a hand-aware physician — the coach does not assign a grade based on user description.

**Symptoms (A2 pulley, most diagnosable in conversation):**

- Pain and swelling at the base of the finger (palm side, just below the PIP joint).
- Pain that's mild at rest but sharp under isometric contraction (gripping a hold) or when pressing on the base of the finger.
- **Visible bowstringing** of the flexor tendon when actively flexing — the tendon visibly lifts off the bone where it should track close. Bowstringing = likely multi-pulley rupture, surgical consult priority.
- Sometimes (but not always) a felt or heard "pop" during the inciting move — almost always indicates significant partial tear or complete rupture.

**The mechanism that does most of the damage:** crimp grip with PIP joint at near-90° flexion, loaded eccentrically — the classic "foot slipped while crimping a small edge" scenario. Hörst's framing (Ch.13): "small partial tears are insidious — they develop over a few climbs, a few days, or even gradually over a season." A user who describes "my finger just kinda feels off lately" on small holds is in that insidious-progression window, and that's when the cost of pausing is lowest.

**The conservative-management framework** (adapted from Hörst Ch.13, qualified for engine use):

> ⚠️ **All steps below require medical clearance first.** The coach can pattern-match symptoms in conversation; it cannot diagnose grade, prescribe immobilization, or set a return-to-climb date. What follows is the general shape of conservative management so the coach can speak coherently about it — not a protocol the engine prescribes.

1. **Stop climbing immediately** at first sign of finger pain — anything that flexes the injured finger forcefully slows healing and can worsen the injury. Continuing to climb on an early-stage tweak is the single most common reason a 6-week injury becomes a 6-month injury (Hörst Ch.13).
2. **Get evaluated** by a hand-aware physio or sports physician. Bowstringing, palpable defect, audible pop, or pain with daily activities (gripping a milk jug) escalate the urgency. Imaging (ultrasound, MRI) may be indicated.
3. **Acute phase** (per physician guidance): ice + NSAIDs only if swelling is visible/palpable, and only briefly — discontinue both as soon as swelling subsides (see §6 NSAID warning). Immobilization (splint or buddy tape) for a few days to two weeks if daily activities provoke acute pain.
4. **Subacute phase:** light, pain-free finger flexion, putty squeeze, massage, mild stretching — only after swelling resolves and only as guided by the physio. Heating pad (10–15 min, 3×/day) accelerates blood flow.
5. **Graded return to climbing** — easy routes, big holds, taped finger, no crimp. The French elite-climber study (Moutet 1993, n=12 A2 injuries) found 8/12 returned within 5 days for very mild cases; more severe tears took 2–3 months. **No timeline is reliable in isolation** — the physio's call governs.
6. **Prophylactic taping for ~6 months post-return** — Schöffl's recommendation (Hörst Ch.13). Tendon remodeling continues for months past pain-free function.

**Three taping methods** (climbers often ask which is best):

- **Ring (A2):** narrow strip (~10 mm) circumferentially around the distal end of the proximal phalanx, just below the PIP. Quick to apply; reinforces A2 only.
- **Figure-8:** crosses under the PIP with turns above and below. Adds some support to A3, A4, and cruciform pulleys.
- **H method:** ~10 cm of 25 mm tape split lengthwise from each end leaving a 12 mm bridge in the middle; bridge sits over the palm side of the PIP joint, free ends wrap above and below. Schöffl's research shows the H method most effectively reduces tendon-to-bone distance of a bowstringing pulley — **the most clinically effective taping method.**

All three require reapplication every few hours during a full climbing day and the strongest tape available (Hörst recommends German Leukotape).

### 4. Lumbrical strains, tenosynovitis, capsulitis — the not-quite-pulley injuries

These three account for ~40% of finger injuries (18% + 17% + 3% lumbrical from Schöffl) and frequently get misdiagnosed by climbers as pulley injuries because the pain location overlaps.

**Lumbrical strain / shift syndrome:** the lumbricals are small intrinsic hand muscles arising from the FDP tendons in the palm. Single-finger or two-finger pocket pulls — especially in monos or asymmetric pulls where the unloaded fingers are pulled distally — create high lumbrical strain. Pain typically located in the **palm** (proximal to the finger base, distinguishing it from A2 pain at the finger base). Hooper's Beta has popularized recognition of this injury — recovery is often faster than pulley injury but requires similar load modification (no single-finger pockets, no asymmetric crimping) for several weeks.

**Tenosynovitis (tendovaginitis):** inflammation of the tendon sheath surrounding FDS/FDP. Symptoms: constant dull ache with each finger movement, pain that radiates down the tendon toward the wrist, sometimes audible/palpable crepitus on movement. Withdrawal from climbing is essential — Hörst Ch.13 protocol mirrors the pulley protocol: stop, evaluate, conservative management, gradual return.

**Capsulitis:** swelling and reduced range of motion in the PIP joint, typically from chronic crimp-grip use under high force. Hallmark symptom: **stiff, achy fingers upon waking** that loosen up through the day. Cartilage stress + increased synovial fluid drives it. Treatment: reduce climbing frequency, switch to open-hand grip as much as possible, ice acute flares. Often resolves with a deliberate crimp-load reduction; sometimes requires full withdrawal.

**Sprained joint capsule:** acute version of capsulitis, from finger jamming in cracks or single-finger dynamic pocket pulls. More acute pain than chronic capsulitis. Buddy taping or splinting (under physio guidance) for early healing; gradual return.

### 5. Collateral ligament injuries

Sprains from a powerful lunge or awkward torque off a "fixed" finger (e.g. in a jam or tight pocket). Mild-to-moderate pain and swelling around the PIP but **no loss of joint stability** in partial sprains (Jebson 1997). Treatment: incomplete sprains splint the PIP for 10–14 days, then buddy tape with range-of-motion exercises; climbing can be reintroduced gradually despite some persistent low-grade pain that may take months to resolve (Bach 1999). Complete tears typically need surgical repair with ~3 month return.

### 6. NSAID warning — counter-intuitive but important

Daily NSAID use (ibuprofen, naproxen, aspirin) **may actually slow muscle, ligament, tendon, and cartilage healing** (Almekinders 1999, 2003). NSAIDs work by blocking the prostaglandin signaling that drives both inflammation and the inflammatory cascade required for tissue repair — blocking one blocks the other. This is in addition to the well-known GI, kidney, and clotting risks of chronic NSAID use.

Practical translation for the coach:

- ✅ Short-course NSAIDs (days, not weeks) for acute swelling, under physician guidance, are reasonable.
- ❌ Daily NSAIDs as a way to "climb through" pain are actively harmful — they mask the warning signal and impair the healing the body is trying to do. Hörst Ch.13: "Never use NSAIDs to mask pain in order to continue climbing while injured."
- The Consuegra Ch.8 / Cook 2017 tendon-injury cascade explicitly notes that mature tendon injuries are **not primarily inflammatory** — cell proliferation and matrix disorganization dominate, which is why ice and NSAIDs are largely ineffective past the first few days.

Climber-friendly alternatives the coach can mention without diagnosing:

- **RICE for acute injury** (rest, ice, compression, elevation) — 20 min icing, 3–6×/day for the first few days. Continued use beyond that inhibits healing.
- **Omega-3 EFA** (fish oil): 2–4 g/day shows anti-inflammatory benefit for musculoskeletal injuries (Maroon 2006). Not a substitute for medical evaluation, but a reasonable supplement under a physio's guidance.
- **Heating + circulation** (heating pad, foam rolling, light aerobic activity) once acute swelling is past — promotes the healing the body is trying to do.

### 7. Growth plate fractures in youth — the highest-stakes single rule

Epiphyseal (growth plate) fractures in fingers — slow onset of pain and swelling at the middle finger joint (PIP), sometimes inability to crimp — were rare a generation ago. Schöffl 2015 documented a **600% increase** in the prior decade. Contributing factors:

- Campus training and hypergravity training are the leading causes.
- Intensive fingerboard training in adolescence.
- Singular focus on hard bouldering with copious dynamic moves and repeated full-crimp loading.
- Total climbing days >3–4/week during the growth spurt.

**Highest-risk window:** ages 11–14 (girls) and 12–16 (boys), with most fractures occurring between 13 and 15. Boys are at significantly higher risk than girls (Hochholzer 2005: 23/24 cases were male). The condition is easily diagnosed via X-ray.

This is the empirical basis for L0 rule D80 (youth <16 hard block on campus, MaxHangs, hypergravity, weighted hangs, one-arm hang training) and D81 (≤4 climbing/training days/week for users <18). Growth plates do not heal back — a fracture that closes the plate prematurely is permanent. The rules are absolute regardless of how strong, how mature, or how committed the youth climber is.

**Hörst Ch.13 youth protocol** (reinforcing D80/D81):

- Ages 11–16: zero double-dyno campus training. Some controlled hand-over-hand campus laddering on big holds *may* be permitted by strong, mature climbers, but only with smooth low-impact movement.
- Favor open-hand grip on all but the smallest holds.
- Little to no hypergravity training (climbing or hangboard with added weight).
- Limit climbing to **3 days/week during the growth spurt**, which is more conservative than the all-ages 4-day cap.
- No campus, no hypergravity, no intensive fingerboarding until **age 16 or end of puberty** (max adult height achieved).

If a youth climber reports finger joint pain — chronic or acute — the engine response is full pause and physician referral. There is no "train through it" path that's safe for this population.

### 8. Carpal tunnel and arthritis — low-frequency notes

**Carpal tunnel syndrome (CTS):** the median nerve compressed at the wrist. Symptoms — numbness, tingling, burning in fingers, often worse at night. Not disproportionately common in climbers (Robinson 1993), but worth knowing as a differential. Conservative management: reduce climbing intensity, anti-inflammatory measures, neutral-wrist splinting at night for 3–6 weeks. Surgical decompression if conservative care fails. Always a physician's call.

**Arthritis (long-term outlook):** the climber-development-arthritis narrative has not held up empirically. Sylvester 2006 found climbers were **not at increased risk** of debilitating osteoarthritis, and that climbers' finger and hand bones are wider and denser than non-climber controls (superiosteal bone deposition). Rohrbaugh 1998 found increased radiographic osteoarthritis in specific joints but no significant difference in overall prevalence. Heavy crimp users may experience some PIP/DIP swelling and stiffness with age. For aging climbers asking about joint maintenance: glucosamine sulfate 1500 mg/day (long-term, cumulative effect) + MSM 1.5–3 g/day shows the strongest evidence for slowing joint degradation (Reginster 2001). Coach can mention these as known supplement evidence — not as a prescription.

---

## How the engine applies this

**D72 — Open-hand default on hangboard, never full crimp.** All hangboard protocols prescribe open-hand or half-crimp grip. Full crimp is never prescribed on hangboard regardless of user request, experience, or strength level. This is L0 and non-overridable. The rationale traces directly to Miro 2021 (~4× tip force at the pulley) and Schöffl 2015's documentation that the crimp grip is the dominant pulley-injury mechanism.

**D68 — Onboarding injury history is a permanent gate.** A user reporting prior A2 grade II in the last 12 months blocks full-crimp wall prescription, lowers hangboard intensity, and extends warm-up. Same gate-logic applies for any documented finger injury. Re-injury rates run 2–5× first-injury rates (Quarmby 2023). The gate is not "blocking forever" — it's pacing. If the user reports 18+ months pain-free and full strength back, they can update injury history in Settings and the engine re-evaluates.

**D71 — Weekly volume ≤10%.** Volume spikes are the dominant tendinopathy trigger (Quarmby 2023, Gabbett 2016). The engine refuses week-over-week volume increases above 10% and holds ACWR within 0.8–1.3. This is the systemic prevention layer — most pulley injuries develop over weeks of accumulated load, not in a single move.

**D35 — Hangboard experience gate (<2 yr systematic).** Tendon/pulley adaptation lags muscular adaptation 6–18 months (Consuegra Ch.8). Climbers with <2 yr systematic training have muscles strong enough to load pulleys past their adapted tensile strength. Advanced hangboard protocols (MaxHangs, weighted, Anderson Repeaters, high-load IntHangs) are gated.

**D80 — Youth <16 hard block.** Absolute block on campus board, MaxHangs, hypergravity, weighted hangs, one-arm hang training. Growth-plate fracture risk is the empirical basis. Non-negotiable, applies regardless of climbing grade or perceived maturity.

**Warm-up prescription (D33).** Progressive warm-up before every climbing or training session — 5–10 min general aerobic, dynamic finger curls and arm circles, foam rolling on the lateral forearm and pectorals, then easy climbing graduating to limit attempts over ~30–60 min. Warming up increases physiologic bowstringing — counterintuitively this helps prevent injury because the system is in its loaded geometry rather than being shock-loaded from cold (Hörst Ch.13). The CUE-02 corollary applies: **no heavy static stretching of forearm flexors pre-climb** (reduces grip strength for up to 60 min).

**No diagnostic claims.** Even with all the above, if a user describes an active injury, the engine does not provide a diagnosis, a grade, or a return-to-climb date. It can describe the general shape of the injury category (see "When user asks…"), modify the current week's plan to remove finger-loading sessions, and route to a climbing-aware physio.

---

## When user asks…

**"I felt a pop in my finger yesterday."**

> That's almost always a significant partial tear or complete rupture of a pulley — not something we resolve through training adjustment. Stop climbing now, get an evaluation from a hand-aware physio or sports physician this week. Bowstringing (the flexor tendon visibly lifting off the bone when you flex the finger) makes it more urgent — that's a multi-pulley injury until proven otherwise. I'll pause the training plan and we can rebuild it once you have a diagnosis and clearance. The cost of pausing now is small; the cost of climbing through is often 2–3× longer recovery (Hörst Ch.13).

**"My finger has been kinda achy at the base for a few weeks but I can still climb on it."**

> That's the insidious pulley-strain pattern Hörst flags in Ch.13 — small partial tears that develop over weeks and feel "okay" until they don't. Climbing through it is the single biggest reason a 6-week injury becomes a 6-month injury. Two things I'd ask you to do: (1) get it evaluated — even a 20-minute physio visit is worth it for the diagnosis differentiation between A2 strain, capsulitis, and lumbrical involvement; (2) until then, I'll switch your hangboard work to open-hand only and drop the volume — and we should probably skip crimpy boulder limit work this week. Pain location matters for differentiation: base of the finger = pulley territory; palm = lumbrical; PIP joint = capsule. The physio will tell us which.

**"What's the safest way to climb back after an A2 injury?"**

> Honest answer: your physio's protocol governs the timeline, not mine. The general pattern Schöffl recommends (and Hörst follows in Ch.13) is conservative management for Grade I–III, with full taping prophylactically for ~6 months post-return — tendon remodeling continues long past pain-free function. When you have clearance, the engine adjusts: open-hand or half-crimp only on hangboard (D72 — that's an L0 rule, not an option), lower starting intensity, longer warm-up, and ACWR-capped progression (≤10% weekly volume, D71). The H taping method is the most evidence-supported for ongoing protection — narrow strip with a bridge over the PIP, free ends wrapped above and below. The single biggest predictor of re-injury is climbing back too hot too soon; the second is dropping the protective habits (open-hand default, prophylactic tape) once the original pain is gone.

**"Are NSAIDs okay to take while I climb through this?"**

> The short version: brief courses are fine under your physician's guidance for acute swelling, but using NSAIDs to mask pain so you can keep climbing is actively counterproductive. Almekinders 1999/2003 showed regular NSAID use may slow tendon and ligament healing — and the pain is the warning signal you're trying to silence. The Cook 2017 work on tendon-injury cascade is clearer still: mature tendon injuries aren't primarily inflammatory, so ice + NSAIDs past the first few days don't do much except mask symptoms. Better default: RICE for the first few days, then heat and circulation. Omega-3 (2–4 g/day) has reasonable anti-inflammatory evidence (Maroon 2006). And the most useful intervention is not climbing on it.

**"My kid (13) keeps getting finger pain — should we just back off campus board for a bit?"**

> Not "back off" — full pause. Growth plate fractures in adolescent climbers have gone up ~600% in a decade (Schöffl 2015), and the highest-risk window is exactly the age range you're describing. The L0 rules I work from block campus, hypergravity, weighted hangs, and one-arm hangs entirely for users under 16 — non-negotiable, regardless of strength or grade, because growth plates don't heal back. Hörst's protocol during the growth spurt: max 3 climbing days a week, no campus, no hypergravity, open-hand grip on all but the smallest holds, no intensive fingerboard work. And the pain itself needs a physician evaluation — slow-onset pain with swelling at the PIP joint is the growth-plate-fracture symptom pattern and it shows clearly on X-ray. Catching it now matters; missing it can mean permanent damage.

---

## Sources

- Almekinders LC (1999, 2003). NSAID effects on tendon and ligament healing.
- Artiaco S et al. (2023). Flexor tendon pulley injuries: systematic review. *J Hand Microsurg* 15(4):247–252.
- Bach AW (1999). Collateral ligament injury management.
- Cook JL et al. (2017). Revisiting the continuum model of tendon pathology.
- Gabbett TJ (2016). High training workloads alone do not cause sports injuries. *Br J Sports Med* 50:444–445.
- Hochholzer T (2005). Epiphyseal fractures in juvenile climbers (24 cases).
- Hörst EJ (2022). *Training for Climbing* (3rd ed.), Ch.13 — Injury Treatment and Prevention. FalconGuides.
- Jebson PJ (1997). Hand and finger injuries in climbing.
- Jones G et al. (2008). Climbing injury one-year prevalence.
- Jones G et al. (2018). Injury rate per 1,000 climbing hours.
- Lin GT et al. (1989). Mechanical importance of A2 and A4 pulleys.
- Maroon JC (2006). Omega-3 EFA for musculoskeletal injury.
- Miro PH et al. (2021). Finger flexor pulley injuries in rock climbers. *Wilderness Environ Med* 32(2):259–272.
- Moutet F et al. (1993). Return-to-climbing timelines in 12 elite climbers with A2 injury.
- Quarmby A et al. (2023). Risk factors and injury prevention strategies for overuse injuries in adult climbers: a systematic review. *Front Sports Act Living* 5:1269870.
- Reginster JY (2001). Glucosamine sulfate for osteoarthritis progression.
- Robinson D (1993). Carpal tunnel syndrome in climbers.
- Rohrbaugh JA (1998). Radiographic osteoarthritis in veteran climbers.
- Schöffl V et al. (2015). Climbing injury distribution: 836 patients, 911 injuries.
- Sylvester AD (2006). Bone density adaptations in climbers.

---

Cross-refs: [[L0_safety_hard_rules]], [[L1_coach_voice]], [[11_injuries_shoulder_elbow]], [[12_antagonist_postural]], [[02_finger_strength]].
