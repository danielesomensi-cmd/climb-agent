# L3 — Equipment Fallback

> **Layer:** L3 (routed via `_index.md` keyword match).
> **Use case(s):** UC19.
> **Token target:** ~3,500.
> **Status:** v1.0 — ready, with documented coverage gap (see below). NEW file.
> **Source files distilled:** `docs/vocabulary_v1.md` §1.2 (canonical equipment IDs + filtering semantics), `docs/research_kb/literature_review_climbing_training.md` §1-3 (volume / frequency / session-structure constraints), CLAUDE.md principle (engine filters sessions by `required_equipment`, NOT by `location_type`), Hörst Ch.6 / Ch.8 (warm-up + home wall content, scattered), plus practical synthesis. NEW file — built from scratch.
> **Audit anchor:** `docs/research_kb/coach_kb_v1_audit.md` §4.6 (file-by-file table, row `18_equipment_fallback`) + §4.1 UC19 (entire-gap finding).

> **v1.0 coverage gap:** the audit (§4.3 row 499) flagged that Lattice 2024 has shifted ~30% of plans away from hangboard toward lifting-edge / pick-up protocols. The substitution matrix below treats lifting edge as an *alternative*, but the deeper Lattice protocol detail (specific pick-up cadence, MXEdge timings) is not yet integrated. v1.1 will fold this in. v1.0 ships with the substitution principles + the most common fallbacks, which covers the user-facing "I don't have X" question fully.

> **Safety firewall (CRITICAL).** Equipment substitution **never** licenses skipping a safety constraint. No hangboard does not mean "skip the warm-up of the fingers" — the warm-up comes from progressive bouldering or no-hang protocols, never from omission. No rope does not license outdoor solo climbing or unprotected falls. Open-hand grip default (D72) applies on whatever surface the user is loading the fingers, including improvised setups. See [[L0_safety_hard_rules]].

---

## Quick reference

The engine filters sessions by `required_equipment`, not by `location_type` (CLAUDE.md core principle). When a user is missing a piece, two valid moves exist: (1) substitute with a functional equivalent (the matrix in §3) and accept the slight signal degradation, or (2) swap the session type for one that targets the same axis using available equipment. **What never works:** skipping the safety scaffold (warm-up, progressive loading, antagonist) to "do the main thing without the prerequisites." During travel / home / minimum-kit weeks, the honest framing is *maintenance, not progression* — Mujika & Padilla 2000 (covered in [[20_return_to_training]]) shows strength holds 2-4 weeks under reduced stimulus, so a maintenance week is genuinely OK and not a "lost" week.

---

## Core findings

### 1. The principle: filter by equipment, not by location

CLAUDE.md is explicit: the engine selects sessions by `required_equipment` availability, not by the user's location label. A "gym" session that requires only `pullup_bar` + `band` is valid at home if the user has both. An "outdoor" trip with a portable lifting edge supports finger work the same way a home garage with a hangboard does. **The location is not the gate; the equipment is.** This unlocks most fallback questions: "what's available right now?" rather than "where am I right now?"

The canonical equipment IDs (vocabulary_v1.md §1.2) form the substitution vocabulary: `hangboard`, `hangboard_20mm`, `pullup_bar`, `band`, `weight`, `dumbbell`, `kettlebell`, `campus_board`, `foam_roller`, `resistance_band`, `bench`, `rings`, `pinch_block`, `spraywall`, `board_kilter`, `board_moonboard`, `board_other`, `homewall`, `gym_boulder`, `gym_routes`, `cable_machine`, `leg_press`, `loading_pin`. Substitution operates on this vocabulary — the matrix in §3 maps the most common "missing" cases to functional alternatives.

### 2. The two valid moves when something is missing

When the engine encounters a missing piece, the coach has two valid responses:

**Move A — Functional substitute.** Replace the missing item with the closest functional equivalent (see §3). Acceptance: the signal quality degrades slightly (a door-frame edge is not as repeatable as a hangboard_20mm; a backpack-loaded pull-up is not as smooth as a weight belt), but the trained axis is unchanged. Best for short-term gaps (a single session, a travel week).

**Move B — Session swap.** Replace the missing-equipment session with a different session that hits the same axis using available equipment. Example: no hangboard at all → swap a finger-strength session for limit bouldering on a `homewall` or `gym_boulder` (climbing-volume-on-small-holds delivers a real but less targeted finger stimulus). Best for longer gaps (a multi-week travel block, a long-term home-only training arrangement).

**Move that never works — Skip the safety scaffold.** "No hangboard? skip the finger warm-up" is wrong. Warm-up doesn't *come from* the hangboard; it comes from the protocol (progressive bouldering, joint mobility, light traverses). See [[09_recovery_sleep]] + [[L0_safety_hard_rules]] D33 / CUE-02. Equivalent errors: "no rope? do unroped highballs" (no — train low-ball boulder volume or board sessions); "no campus board? do dynamic moves on the open project" (no — train RFD inside graded limit bouldering with guarded fall conditions).

### 3. Substitution matrix

The most common missing-equipment cases, with the v1 substitution and acceptance notes. Items marked ⚠️ require a specific safety caveat.

| Missing | Closest substitute | Acceptance note |
|---|---|---|
| `hangboard` (no edge surface at all) | **Door-frame edge or built bottom edge** (10-20 mm) for warm-up only; primary work = `homewall` / `gym_boulder` volume on small holds | ⚠️ Door frames vary wildly in depth and grip-friendliness; do not progress to MaxHangs on a door frame. For genuine progressive max work, see lifting edge or pick-up below |
| `hangboard` (have hangboard but not 20mm) | Use the closest available edge (16-25 mm) — **D85 standardised test invalidates** at non-20 mm depths, but training still works | Document the edge depth used; recalibrate target loads to the new depth. Test results from non-20 mm edges are not comparable to Lattice / Berta 2025 norms |
| `loading_pin` (was used for unilateral finger work) | Switch to bilateral `hangboard` for the cycle | Acceptance: lose the per-hand asymmetry signal. Engine resolver does this automatically when `finger_training_device = hangboard` |
| **Lifting edge / pick-up tool** (Lattice MXEdge, similar) | Treat as **first-class alternative to hangboard**, not as fallback | Lattice 2024 (per audit §4.3) has ~30% of plans on lifting-edge. v1 engine catalog does not yet route this natively (v1.1 candidate); coach can describe the protocol but cannot ship it as engine prescription |
| `weight` (for weighted pull-ups, weighted hangs) | **Backpack with books or water bottles**, dip belt with rope, weight vest, kettlebell on a sling | ⚠️ Stability matters — anything that swings disrupts the hang's controlled loading. Backpack is OK if it's snug (compression straps); a loose pack swings and changes the load profile |
| `weight` (for hangboard) AND need to *reduce* load below BW | **Band assist** (anchor at top, foot or knee in band) — opposite of weight added | Acceptance: band offloads progressively as you sink, so the load profile is not constant. For initial Repeater work this is fine; for Max-Hang protocols the band-assist is methodologically muddier. Document |
| `pullup_bar` (no bar at all) | **Door-frame edge wide grip** (limited movement), table-edge eccentric pulls, **rings or sling** from a ceiling anchor, gym membership for one session | Acceptance: door-frame pull-ups are constrained by grip strength (small edge) rather than pulling power, so they bias the signal toward fingers. Not equivalent. For real pulling progression, the cheapest fix is a $30 doorway bar |
| `campus_board` | **Limit bouldering on small holds** + **on-the-wall dynamic move practice** (one-arm reach-and-stick, deliberate double-clutches inside a graded boulder) | Acceptance: campus is the *single tool* for measured-distance dynamic recruitment. Substitute hits some of the stimulus but loses the calibration. **D41 prerequisites still apply** to whatever campus-style work is done; see [[L0_safety_hard_rules]] |
| `board_kilter` / `board_moonboard` / `board_other` | **Steep-overhang section of `gym_boulder`** + spraywall + outdoor cave problems | Acceptance: boards offer reproducible, graded, dense problem sets — the substitute loses the standardisation. For projecting and benchmarking, the board's value is hard to replace. For training stimulus alone, steep-gym-boulder + spraywall covers most of it |
| `gym_routes` (need lead/rope work, only have boulder) | **Boulder pyramids** (link 3-5 problems with minimal rest), **4×4-style circuits** if PE-phase, **route projecting via gym membership swap** | Acceptance: lead-head practice (clipping, falling, route reading) cannot be substituted on a boulder. If the user's macrocycle goal is lead-grade, a periodic outdoor or partner gym trip is functionally required |
| `bench`, `cable_machine`, `leg_press` (antagonist / general strength equipment) | **Bodyweight push-ups, dips on chairs, single-leg squats, Bulgarian split squats, resistance band pulls** | Antagonist work [[12_antagonist_postural]] is highly portable — almost all of it can be done bodyweight + band. The bench is a convenience, not a prerequisite |
| `resistance_band` (no bands at all) | **Towel-pull isometrics for rotator-cuff prehab**, deliberate slow-tempo pushups, bodyweight scapular slides on the floor | Acceptance: bands are the cleanest way to load light antagonist work progressively. Towel + slow tempo gets most of it; reload as soon as bands are accessible |
| `foam_roller` | **Tennis ball or lacrosse ball** for self-myofascial release; firm-pressure self-massage with knuckles | Functionally equivalent for forearm / shoulder work; foam roller is slightly easier for big-muscle work (back, glutes) |
| `pinch_block` | **Heavy book between fingers and thumb** with weight balanced on it; pinching the corner of a hangboard if shaped for it | Acceptance: book pinching is calibration-poor. For pinch-specific training, a $20-30 pinch block is one of the higher-leverage purchases |
| **Outdoor rock only** (no gym at all) | Outdoor climbing volume + **hangboard / lifting edge** for finger work + **bodyweight + band** for antagonist; consider **portable boards** (T-Stop, GripSaw, Lattice's MXEdge) | The "I only climb outside" user is well-served by minimal kit (hangboard + band + pull-up bar = ~$80 of kit covers ~80% of the off-wall training space) |
| **Travel — no kit at all** | Bodyweight conditioning + mobility + (if at a hotel) door-frame edge for finger warm-up; accept that this is **maintenance, not progression** | Hörst Ch.12 + Mujika 2000: strength holds 2-4 weeks under reduced stimulus. A travel week at maintenance is not a lost week — see [[20_return_to_training]] §2 |

### 4. The "minimum viable kit" question

A frequent UC19 question (audit §4.1): "what's the minimum equipment to actually train?" Honest answer, anchored to the engine's current catalog:

**Minimum viable home kit, ranked by leverage:**
1. **`hangboard` or lifting edge** — $30-100; unlocks the finger-strength axis, the highest-leverage trainable variable (Magiera 2013, see [[16_assessment_interpretation]]).
2. **`pullup_bar`** (doorway type works) — $20-40; unlocks pulling-strength training [[03_pulling_strength]].
3. **`resistance_band` set** (2-3 tensions) — $15-25; unlocks antagonist [[12_antagonist_postural]] + rotator-cuff prehab.
4. **`weight`** (any form: weight vest, dip belt + plates, kettlebell, heavy backpack) — $25-100; unlocks weighted pull-up progression + weighted hangs.
5. **`foam_roller` or lacrosse ball** — $15-25; unlocks self-myofascial work for recovery (Hörst Ch.12 §4.2).

Items 1-3 cover ~80% of off-wall training across all phases. Item 4 becomes relevant once the user passes the bodyweight pull-up gate (D84b — see [[03_pulling_strength]]). Item 5 is recovery-side, not training-side, but the leverage on consistency is high.

**Not on the minimum list:** campus_board (D41 gates limit its eligible user pool to ≥7a redpoint + ≥2 yr systematic + clean injury history — see [[L0_safety_hard_rules]]), home spraywall / training board (very useful but high cost, not minimum), pinch_block (specialist).

### 5. The "I only have 30 minutes" question

UC16 / UC19 boundary. Time is the most-asked constraint, and the answer is *which* 30 minutes:

- **30 minutes with a hangboard available** → warm-up (5 min) + max hangs cluster (15 min, 3-4 sets) + antagonist/cooldown (10 min). Highest-leverage 30 minutes for the finger axis.
- **30 minutes at a gym with boards** → warm-up (10 min progressive) + limit bouldering on 4-6 problems near max + cooldown (5 min). Skip everything else.
- **30 minutes at home, bodyweight only** → mobility / warm-up (5 min) + pull-up + push-up + core circuit (20 min, 3-4 rounds) + antagonist (5 min). Maintenance volume, no max-effort.
- **30 minutes outdoor at the crag with a project** → standard outdoor warm-up (15 min — see [[L0_safety_hard_rules]] CUE-02) + 2 burns on the project. Don't compress the warm-up to extract a third burn; that's the injury route.

The pattern: **don't try to do a full session in 30 minutes**. Pick the highest-value block for the current goal and execute that with full quality. Hörst's "train better, not more" (D79, see [[L1_coach_voice]]) maps cleanly here.

### 6. What never substitutes (irreplaceable items)

Some things have no v1 substitute and should be flagged honestly:

- **Lead-head training and falling practice** — requires `gym_routes` + a partner. No bouldering substitute trains the clipping rhythm, the rope-management cognitive load, the planned-fall protocol (D29 deferred, see [[07_mental_fear_focus]]). If the user's macrocycle targets a lead grade, periodic access to a route gym or outdoor rope partner is functionally required.
- **Standardised testing** — `test_max_hang` (D85) needs a 20 mm edge specifically; non-20 mm tests aren't comparable to Lattice / Berta 2025 norms (see [[16_assessment_interpretation]]).
- **Critical Force / 4-min all-out test** (D89, v2) — requires Tindeq / Climbro instrumentation; no v1 substitute.
- **RFD / contact strength testing** — needs a high-rate force sensor (not v1 — see [[03_pulling_strength]] §5).

The coach surfaces these honestly: *"there's no substitute for X — the engine can't fake it. For your current goal, this is fine; if you want to track Y you need the kit."*

---

## How the engine applies this

- **`required_equipment` filtering** — every session metadata declares its equipment dependency. The session is only eligible if the user's inventory satisfies it (AND semantics on `equipment_required`, OR semantics on `equipment_required_any`). See vocabulary_v1.md §2.8.
- **Location-agnostic** — the engine does NOT gate on `location_type`; gym, home, outdoor are equipment-inventory shorthand, not eligibility filters.
- **Loading-pin / hangboard switch** — `finger_training_device` user setting routes between hangboard and loading-pin exercise variants automatically (vocabulary_v1.md §1.3). User flips the setting; resolver picks the right exercise family.
- **Weekly override** — `/api/weekly-override/{week_start}` lets the user say "this week I have access to X only" without changing their permanent inventory; the planner regenerates the week against the temporary inventory.
- **Outdoor slot conversion** — `/api/outdoor/convert-slot` converts a planned outdoor session to gym/home when the user's plans change (weather, partner availability).
- **What the engine does NOT do (v1):** automatic substitute-suggestion at session-level (the engine drops a session if its equipment isn't available rather than auto-substituting). Lifting-edge as a first-class hangboard alternative is v1.1. Engine-side detection of "you have new equipment" requires the user to update inventory.

---

## When user asks…

**"I'm traveling for 10 days, no equipment at all. What do I do?"**

Maintenance, not progression. The honest framing: 10 days under reduced stimulus is inside the strength-retention window (Mujika 2000: ~2-4 weeks before measurable decline). Bodyweight conditioning (push-ups, dips on chairs, pistol squats, planks, hollow body), mobility (10-15 min daily), and finger warm-ups on a door frame if you can find a clean edge. Hotel-stair sprints if you want some aerobic load. The strategic move is to **not try to compress 10 sessions into 6 hard ones when you get home** — see the D71 ≤10% volume cap in [[17_readiness_overtraining]]. Resume at 70-80% of pre-travel volume the first week back.

**"My gym closed unexpectedly. Can I keep my macrocycle?"**

Depends on how long the closure is and what your home setup looks like. If you have a hangboard + pullup_bar + bands and the closure is ≤2 weeks: yes, mostly. Swap climbing-volume sessions for hangboard + pulling work, expect the technique side to drift. If the closure is longer or you have no home kit: the macrocycle's phase structure can hold for ~3-4 weeks (Mujika 2000 strength-retention window), beyond which the engine should be regenerated when normal training resumes. Don't fake-train through a multi-week closure pretending the cycle is intact — the engine's closed-loop will read incomplete sessions as overtraining signals (see [[17_readiness_overtraining]] §2 D70).

**"I have no hangboard, only a door frame. Can I do MaxHangs?"**

⚠️ No — not in the D-protocol sense. MaxHangs are a measured load (D85 protocol on 20 mm) and a door frame doesn't give you that. What you *can* do on a door frame: warm-up hangs, density / volume work at sub-max load (open-hand grip default per [[L0_safety_hard_rules]] D72), assisted hangs as part of a progression. For genuine max-effort finger strength training, the leverage is to spend $30-60 on the minimum hangboard or lifting edge — see §4. Doing MaxHangs on an unmeasured edge is the *worst* of both worlds: high load (risk) without the data (no progress signal).

**"I don't have a campus board. Is there a real substitute?"**

Partial. Campus is the only tool that delivers measured-distance dynamic recruitment in a reproducible way. The functional substitute (limit bouldering with dynamic moves + on-the-wall practice of one-arm reach-and-stick) trains some of the same RFD stimulus but loses the calibration. **Important:** the D41 prerequisites (≥7a redpoint, ≥2 yr systematic, no current finger/elbow/shoulder issue — see [[L0_safety_hard_rules]]) apply to *any* campus-style work, including the on-wall substitute. If you don't meet the prerequisites, the campus-style substitute is also off the table — train the underlying capacity through hangboard + limit bouldering instead.

**"What's the cheapest setup that lets me actually train?"**

Hangboard ($30-100) + doorway pull-up bar ($20-40) + resistance band set ($15-25) = ~$80-160 total. Covers finger strength, pulling strength, antagonist + rotator-cuff prehab, finger and pulling endurance proxies. With a $40 weight vest or a heavy backpack, you also cover weighted-pull-up progression once you pass the BW pull-up gate ([[03_pulling_strength]] D84b). That kit + access to *some* climbing surface (a community gym membership, an outdoor crag, a board membership, friends' homewalls) is the genuine minimum.

**"My loading pin broke. Can I switch to hangboard mid-cycle?"**

Yes. Flip the `finger_training_device` setting in your inventory from `loading_pin` to `hangboard`; the engine resolver swaps the exercise family automatically. Note: per-hand asymmetry signal is lost (loading pin is unilateral, standard hangboard is bilateral). If asymmetry was an explicit training target (history of finger injury on one hand, for example), the swap is functional but the targeted asymmetry work degrades. Surface this honestly to the user.

**"I've never used a hangboard. Where do I start?"**

Two prerequisites before the engine prescribes anything advanced: D35 (≥2 years systematic climbing) and clean injury history. If you have both, start with the engine's beginner finger sub-protocols — open-hand grip default ([[L0_safety_hard_rules]] D72), 20 mm edge, sub-max repeater protocol (60% MVC, 7s on / 3s off — see [[02_finger_strength]]). If you don't have the 2 years yet, the engine *will not* prescribe hangboard work and the coach should not encourage it — climbing volume itself is the right finger-training stimulus at that level (T07 muscle-tendon adaptation mismatch — see [[10_injuries_fingers]]).

---

## Sources

- Mujika I, Padilla S. 2000a. Detraining: loss of training-induced physiological and performance adaptations. Part I — short term insufficient training stimulus. *Sports Med* 30(2):79-87.
- Mujika I, Padilla S. 2000b. Detraining: loss of training-induced physiological and performance adaptations. Part II — long term insufficient training stimulus. *Sports Med* 30(3):145-154.
- Hörst EJ. 2022. *Training for Climbing* (3rd ed.), Ch.6 (warm-up structure), Ch.8 (home wall design).
- Quarmby A et al. 2023. Risk factors and injury prevention strategies for overuse injuries in adult climbers. *Front Sports Act Living* 5:1269870.
- Lattice Training. 2024. *How to train pick-ups for finger strength* (Hutchens, blog) — lifting-edge / pick-up protocol shift, referenced in audit §4.3 row 499. (v1.0 references conceptually; v1.1 will deepen.)
- climb-agent vocabulary_v1.md §1.2 — canonical equipment IDs.

---

## Cross-references

- [[L0_safety_hard_rules]] — D35 (hangboard experience gate), D41 (campus prerequisites), D72 (open-hand default), CUE-02 (no heavy static stretching pre-perf), D55 (exercise blacklist applies regardless of equipment).
- [[02_finger_strength]] — what `test_max_hang` measures + protocol depth.
- [[03_pulling_strength]] — D84b pulling-test gate (BW pull-up before weighted) + D38 Brzycki.
- [[09_recovery_sleep]] — warm-up + active-rest content that doesn't depend on equipment.
- [[12_antagonist_postural]] — antagonist work that is largely bodyweight + band.
- [[13_tapering_redpoint]] — trip preparation and skin/logistics overlap with travel-kit choices.
- [[16_assessment_interpretation]] — standardised testing requires 20 mm edge specifically.
- [[17_readiness_overtraining]] — D71 ≤10% volume cap applies to the post-break ramp.
- [[19_lifestyle_integration]] — minimum-kit reality intersects with limited training time.
- [[20_return_to_training]] — Mujika 2000 strength-retention window underpins "maintenance is fine."
