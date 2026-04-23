# D223 — C225 Research Notes: Climbing-Specific Forearm & Biceps Exercises

**Date:** 2026-04-23
**Purpose:** Research notes to inform a future C225 catalog brief. Read-only. No catalog edits.
**Parent audit:** `docs/audit/D223_body_part_picker_classification_audit.md` + `docs/audit/D223_body_part_pool_listing.md`.

---

## 1. Intro & scope

Audit D223 surfaced two body-part pools that cannot sustain a `main ≥ 3` selection even after the body-part picker enforces `role: main` (fix shipped in B224):

- **forearms**: 12 exercises total, **0 with `role: main`** (9 prehab, 2 cooldown, 1 conditioning). Real gap — the picker currently can only fall back to accessory/prehab.
- **biceps**: only **2 exercises** (`bicep_curl` accessory, `chinup` accessory). Tiny pool, zero mains.

This research identifies climbing-specific forearm and biceps strength exercises from authoritative sources, mapped to the catalog's canonical vocabulary (`docs/vocabulary_v1.md`) and to the `body_part_picker.py` classification rules.

**Classification constraints to respect (from `body_part_picker.py:72-117`):**

- Forearms bucket = `domain in {prehab_wrist, prehab_finger}` OR `pattern in {wrist_extension, wrist_flexion, forearm_pronation, forearm_supination, finger_extension, tendon_glide}` OR `include_ids: ["farmers_carry"]`. Then `forearms -= fingers`.
- Biceps bucket = `pattern: elbow_flexion` OR `include_ids: ["chinup", "bicep_curl"]`. Then `biceps -= forearms`.
- **Fingers are separate**: hangboard work, pinch-block hangs, finger-edge work all route to `fingers`, never to `forearms`. Wrist-specific work (flexion/extension/pronation/supination/roller) and grip-carry work are the legitimate forearms territory.

**Out of scope:** No edits to `exercises.json`. No brief opened. No adjustments to the bucket classification rules.

---

## 2. Sources consulted

All retrieved 2026-04-23 unless noted otherwise.

| # | Source | URL |
|---|---|---|
| 1 | Eric Hörst — *Training the Wrist Stabilizers* (TrainingForClimbing.com) | https://trainingforclimbing.com/training-the-wrist-stabilizers/ |
| 2 | Eric Hörst — *Lattice Heavy Roller — Forearm Training for Climbers* | https://trainingforclimbing.com/training_tools/lattice-heavy-roller-forearm-training-for-climbers/ |
| 3 | Lattice Training — *How do I strengthen my wrists for climbing?* (Coach Jonny) | https://latticetraining.com/blog/how-do-i-strengthen-my-wrists-for-climbing/ |
| 4 | Tyler Nelson / Camp4 Human Performance — *Using the Wrist Wrench for Rock Climbers* | https://www.camp4humanperformance.com/blog/wrist-wrench |
| 5 | Tyler Nelson / Camp4 — *Wrist Position and Grip Type in Climbing* | https://www.camp4humanperformance.com/research/wrist-position-grip-type-climbing |
| 6 | Hooper's Beta — *Basic Wrist Stability Training for Climbers, Pt. 1* | https://www.hoopersbeta.com/library/wrist-stability-training-for-climbing-part-1 |
| 7 | Gripped Magazine — *Five Exercises for Building Stronger Biceps* | https://gripped.com/indoor-climbing/five-exercises-for-building-stronger-biceps/ |
| 8 | Gripped Magazine — *Training Tuesday: The Brachialis and the Brachioradialis* | https://gripped.com/indoor-climbing/training-tuesday-the-brachialis-and-the-brachioradialis/ |
| 9 | TrainingBeta — *Forearm Antagonist Training for Climbing* (Hörst repost) | https://www.trainingbeta.com/training-wrist-stabilizers-for-climbing/ |
| 10 | 8BPLUS — *Body by Bruno Part 3: How to Train Biceps for Climbing* | https://blog.8bplus.com/body-by-bruno-part-3-how-to-train-biceps-for-climbing |
| 11 | The Climbing Doctor — *Train Antagonist Strength for Climbing* | https://theclimbingdoctor.com/how-to-train-antagonist-muscle-strength-for-climbing/ |
| 12 | Eric Hörst — *Training Max Grip Strength with Nicros H.I.T.* (one-arm lock-off methodology) | https://trainingforclimbing.com/overview-of-hit-system-workouts-for-building-maximum-grip-strength/ |
| 13 | Lattice Training — *Importance of Antagonist Training During Performance Phase* | https://latticetraining.com/blog/training-tips-for-climbers-the-importance-of-antagonist-training-during-performance-phase/ |
| 14 | Gripped Magazine — *Rip Underclings Off the Wall with These Five Bicep Drills* (Outside+ paywall — summary via search only) | https://www.climbing.com/gym-climbing/the-best-bicep-exercises-for-athletes/ |

Peer-reviewed check (PMC article on finger flexion/extension ratio, PMC10701375) was surfaced but not cited for specific exercise prescriptions — it supports the general thesis that extensor-side training is under-dosed in climbers.

---

## 3. Bucket A — Forearms `main` candidates

Target: bring `forearms` from `main=0 → main≥3` in `gym_full`, and ≥2 in home_min_hangboard.

### A.1 Wrist Roller (Hörst/Lattice Heavy Roller)
- **Proposed ID**: `wrist_roller`
- **Description**: Rotational wrist device (commercial Lattice Heavy Roller, or DIY dowel + cord + weight): roll a weight up and down via wrist flexion/extension cycles. Flip the device to shift emphasis between flexors and extensors. High torque at moderate loads, isolates forearms without loading the shoulders.
- **Equipment**: `equipment_required_any: ["weight", "dumbbell", "barbell"]` (for DIY dowel + loading) — in practice a dedicated `wrist_roller` tool is typical but the catalog lacks that equipment ID, so fallback to any weighted item. **[inference]** on equipment mapping.
- **Source**: Hörst — *Lattice Heavy Roller* [#2]; Lattice — *Strengthen wrists* [#3]; Gripped *Brachialis/Brachioradialis* [#8].
- **Proposed role**: `main`
- **Proposed domain**: `strength_general` (antagonist/forearm strength) — could also include `prehab_wrist` as secondary.
- **Proposed pattern**: `wrist_flexion` (primary) with a twin entry `wrist_roller_extensor` using `wrist_extension` if splitting flexor vs extensor bias is desired. Simpler option: single entry with `pattern: wrist_flexion` covering both directions, described as "flip device to switch focus".
- **Why climbing-relevant**: Lattice explicitly cites sloper- and sandstone-specific strength; Hörst cites reduction of finger strain by developing antagonist capacity. Transfers directly to large-hold compression and antagonist balance for tendinitis prevention.
- **Duplicate check**: `grep -n "wrist_roller" exercises.json` → not found. No collision with existing `wrist_curl` / `reverse_wrist_curl` (those are prehab-role, dumbbell-only, static curl — different exercise).

### A.2 Wide-Pinch Hold with Extended Wrist (Hörst)
- **Proposed ID**: `wide_pinch_extended_wrist_hold`
- **Description**: Standing pinch of a stack of two or three 2x4 wood blocks (or a thick bumper plate) at the side, arm hanging straight, wrist in full extension. 10–30 s holds per hand. Hörst calls this "the single most overlooked and important position" for extensor training because it matches open-hand edge/pocket/wide-pinch positions on rock.
- **Equipment**: `equipment_required_any: ["pinch_block", "weight"]` — DIY 2x4 stack counts as a pinch block; commercial pinch blocks work; bumper plate works.
- **Source**: Hörst — *Training the Wrist Stabilizers* [#1]; TrainingBeta repost [#9].
- **Proposed role**: `main`
- **Proposed domain**: `strength_general` (antagonist-loaded isometric) + `prehab_wrist` — **[inference]** on domain: Hörst frames this as antagonist *strength*, not rehab. Primary `strength_general`, secondary `prehab_wrist`.
- **Proposed pattern**: `wrist_extension`
- **Why climbing-relevant**: "Wrist extensors function a bit differently when the fingers are straight (extended) compared with when the fingers are flexed, as in crimping or holding a dumbbell" (Hörst). Trains the extensor in the grip position used on rock — open-hand edges, pockets, wide pinches.
- **Duplicate check**: `grep -n "wide_pinch" exercises.json` → not found. Distinct from `pinch_block_training` (that is `domain: finger_strength`, `pattern: isometric_hang`, lives in *fingers* bucket, equipment `pinch_block`). The new entry's focus is wrist extension, not finger-flexor pinch strength.

### A.3 Heavy Reverse Wrist Curl (Hörst)
- **Proposed ID**: `heavy_reverse_wrist_curl`
- **Description**: Seated or standing reverse wrist curl with heavier loading than the existing `reverse_wrist_curl` prehab entry. 3 sets × 8-12 reps in hypertrophy/strength range (vs Hörst's 2×15-20 light prehab prescription). Dumbbell or barbell. Progressive overload focus.
- **Equipment**: `equipment_required_any: ["dumbbell", "barbell", "weight"]`.
- **Source**: Hörst — *Training the Wrist Stabilizers* [#1] (prehab protocol); Lattice *Strengthen wrists* [#3] (strength-range protocol 3×8-12 @ 1 min rest OR 3×3-6 @ 2-3 min rest); Gripped *Brachialis/Brachioradialis* [#8].
- **Proposed role**: `main`
- **Proposed domain**: `strength_general`
- **Proposed pattern**: `wrist_extension`
- **Why climbing-relevant**: Lateral-forearm imbalance drives lateral epicondylitis (climber's elbow). Strength-range extensor work shifts this from "prehab maintenance" to genuine antagonist capacity — the threshold Hörst cites for serious climbers.
- **Duplicate check**: `grep -n "heavy_reverse_wrist_curl" exercises.json` → not found. Distinct `role` and dosing from existing `reverse_wrist_curl` (prehab, 2×15-20 style). Possible alternative: promote existing `reverse_wrist_curl` to dual-role `["prehab", "main"]` with expanded prescription defaults — simpler but loses the strength-vs-prehab semantic split. **Recommend separate entry** to keep roles clean.

### A.4 Offset Dumbbell Pronation/Supination (Hörst pronator isolation)
- **Proposed ID**: `offset_dumbbell_pronation_supination`
- **Description**: Seated with forearm on bench, grip an asymmetrically-loaded dumbbell (weights only on one side) or a hammer. Rotate through pronation and supination, 3 sets × 8-12 reps per side. Offset creates a rotational moment that loads pronator teres and supinator specifically.
- **Equipment**: `equipment_required: ["dumbbell"]` (offset loading assumed). Bench optional.
- **Source**: Hörst — *Training the Wrist Stabilizers* [#1] ("pronator isolation" with light warmup + 2-3 heavier sets); Lattice *Strengthen wrists* [#3] (rotations 2-3×/week); ACE exercise library (supination/pronation mechanics, referenced by Lattice).
- **Proposed role**: `main`
- **Proposed domain**: `strength_general` — **[inference]** (could be `prehab_elbow` like existing entries). Justification: Hörst's article lists this as part of strength-phase antagonist training, with 2-3 heavier sets. Existing `stick_pronation_supination_eccentric` and `forearm_pronation_supination` already cover the prehab side; this fills the strength-range gap.
- **Proposed pattern**: `forearm_pronation` (catalog convention — `forearm_supination` is a separate valid pattern; pick one for the primary tag, mention both motions in description).
- **Why climbing-relevant**: Pronator/supinator strength protects the medial and lateral elbow from repeated off-axis loading when climbing on slopers and compressing/twisting on features. Transfers to twist-lock positions and stabilization during dynamic loading.
- **Duplicate check**: `grep -n "offset_dumbbell" exercises.json` → not found. Similar in motion to existing `forearm_pronation_supination` (bodyweight prehab, empty equipment list) and `stick_pronation_supination_eccentric` (dumbbell, eccentric prehab). This new entry is the **strength-load, concentric-eccentric, main-role** variant they lack.

### A.5 Barbell Hold / Thick-Bar Hold (grip-forearm carry alternative)
- **Proposed ID**: `barbell_hold_thick_bar`
- **Description**: Static hold of a loaded barbell (ideally with Fat Gripz or a thick-bar implement) for max duration, 3-5 sets × 20-40 s at ~65-75% of max-grip load. Primarily a finger-flexor endurance challenge, but the wrist and forearm flexors are loaded isometrically throughout. Hypertrophy-range protocol from Nelson's wrist-wrench hypertrophy block applied to a barbell context.
- **Equipment**: `equipment_required_any: ["barbell", "dumbbell", "kettlebell"]`.
- **Source**: Nelson — *Wrist Wrench* [#4] (hypertrophy protocol 20-40 s @ 65-75%); Lattice *Strengthen wrists* [#3].
- **Proposed role**: `main`
- **Proposed domain**: `strength_general`
- **Proposed pattern**: `carry` (match existing `farmers_carry` convention — static hold is a degenerate carry).
- **Why climbing-relevant**: Overlap with `farmers_carry` conditioning role, but delivered as a true strength block (static hold, heavy load, longer duration). For climbers with wrist pain history, long isometric loading is Nelson's preferred modality over ballistic wrist curls.
- **Duplicate check**: `grep -n "barbell_hold" exercises.json` → not found. Related: `farmers_carry` is already `role: conditioning` and relies on the `include_ids: ["farmers_carry"]` entry in the forearms bucket rules — this new entry has `pattern: carry` which would also route into forearms (via the bucket's `include_ids` or a rule expansion to include `pattern: carry` — **check during C225 implementation**).
  - **Open question for C225**: `carry` is not in the forearms `patterns` allowlist. Either (a) add the new exercise via `include_ids` to the bucket rules, or (b) add `carry` to the forearms pattern allowlist. Option (b) would also re-route `farmers_carry` via its pattern (redundant with existing `include_ids` but cleaner semantically). This is a **picker rule edit**, not just a catalog edit — flag for Daniele.

**Recommended minimum forearms `main` set (gym_full): A.1, A.2, A.3, A.4** → 4 mains, exceeds the `main≥3` target.

**Home-minimum (hangboard+band only — no dumbbell/barbell):**
- A.2 (wide pinch with extended wrist) works if user has *any* weight — loose interpretation allows `equipment_required_any: ["pinch_block", "weight"]` to include backpacks as weight, but this is already documented as an abstraction-leaky case. Safer: pair hangboard with `resistance_band` and dumbbell.
- A.1 (wrist roller) is the cheapest DIY build but still needs weight.
- A.3 heavy reverse wrist curl needs dumbbell/barbell.
- **Verdict**: at `home_min_hangboard` without any weight, no `main` candidates become available. Fallback to existing prehab (`reverse_wrist_curl`, `wrist_curl`, `finger_extensor_training`) as accessory-filler is the pragmatic path per the D223 fallback policy ("accessory OK for 3rd slot at home"). **No new catalog entries can close this corner case without assuming at least one weight or band.**

---

## 4. Bucket B — Biceps `main` candidates

Target: bring biceps from 2 entries / 0 mains → main ≥ 3 in gym_full, ≥ 2 at home.

### B.1 Weighted Chin-up (heavy, strength-range)
- **Proposed ID**: `weighted_chinup`
- **Description**: Chin-up (supinated grip) with added weight via belt/vest. 3-5 sets × 3-6 reps at 2-3 min rest (strength range). Primary driver of biceps + brachialis + lat recruitment in climbers.
- **Equipment**: `equipment_required: ["pullup_bar", "weight"]`.
- **Source**: Nelson / TrainingBeta episode on bar isometrics [#4-#5]; Hörst *Nicros H.I.T.* [#12] cites weighted pull-ups and one-arm lock-offs as maximum strength drivers. Gripped *Bigger Biceps* [#7] cites chin-ups as "directly trains lock-off".
- **Proposed role**: `main`
- **Proposed domain**: `strength_pulling` (matches catalog convention — see existing `supinated_inverted_row`), secondary `strength_general`.
- **Proposed pattern**: `elbow_flexion` — **critical**: this is what routes it into the biceps bucket. If tagged `pull_vertical` it routes to `back_pulling` instead (like existing `chinup`). Multi-pattern entries are allowed (e.g. `["elbow_flexion", "pull_vertical"]`), but the `biceps -= forearms` / `biceps -= back_pulling` subtraction order in `build_body_part_index` does NOT subtract biceps from back_pulling; they co-exist, BUT `forearms -= fingers` and `biceps -= forearms` only.
  - **[inference]** The catalog convention for `chinup` is `pattern: pull_vertical` with `include_ids: ["chinup"]` in the biceps bucket — a targeted override. A cleaner approach for `weighted_chinup` is to **use `pattern: elbow_flexion`** as primary (or list both) so it naturally lands in biceps without needing an include_ids override. Verify with Daniele during C225.
- **Why climbing-relevant**: One-arm lock-offs and weighted pull-ups are Hörst's named maximum-strength drivers. Supinated grip biases biceps brachii and brachialis, which are the primary elbow flexors recruited during undercling pulls and deep lock-offs.
- **Duplicate check**: `grep -n "weighted_chinup" exercises.json` → not found. Not a collision with existing `chinup` (bodyweight accessory) — this is the loaded strength-range variant. Distinct.

### B.2 Hammer Curl (brachialis/brachioradialis)
- **Proposed ID**: `hammer_curl`
- **Description**: Dumbbell curl with neutral grip (palms facing each other). 4 sets × 6-10 reps per arm. Targets brachialis and brachioradialis — the elbow flexors that climbers recruit in underclings, neutral-grip lock-offs, and sloper pulls.
- **Equipment**: `equipment_required: ["dumbbell"]`.
- **Source**: Gripped *Bigger Biceps* [#7] (4×6 per arm, climbing-specific); Gripped *Brachialis/Brachioradialis* [#8]; 8BPLUS Body by Bruno Pt.3 [#10] (search snippet, full article unreachable).
- **Proposed role**: `main`
- **Proposed domain**: `strength_general`
- **Proposed pattern**: `elbow_flexion`
- **Why climbing-relevant**: Brachioradialis is "often overlooked in climbing training... a strong brachioradialis essentially allows you to get more out of your climbing by increasing your pulling force" (Gripped). Neutral-grip loading reflects real climbing hand positions better than pure supinated curl.
- **Duplicate check**: `grep -n "hammer_curl" exercises.json` → not found. Distinct from existing `bicep_curl` (dumbbell, supinated grip, elbow_flexion pattern). The two can coexist as separate entries with different grip attributes.

### B.3 Reverse Curl (brachialis + forearm extensor overlap)
- **Proposed ID**: `reverse_barbell_curl`
- **Description**: Barbell (or EZ-bar) curl with pronated grip (palms down). 3 sets × 8-10 reps. Loads brachialis and brachioradialis heavily, with extensor-side forearm involvement as a stabilizer.
- **Equipment**: `equipment_required_any: ["barbell", "dumbbell", "weight"]`.
- **Source**: Gripped *Bigger Biceps* [#7] (3×8-10); Gripped *Brachialis/Brachioradialis* [#8]; TrainingBeta forearm antagonist [#9] (overlap with extensor dosing).
- **Proposed role**: `main`
- **Proposed domain**: `strength_general`
- **Proposed pattern**: `elbow_flexion`
- **Why climbing-relevant**: Pronated-grip elbow flexion mimics undercling pulls and pinch-dominant moves where the forearm is not neutral. Biases brachialis, which Gripped cites as "actually a much stronger driver of flexion than the biceps brachii."
- **Duplicate check**: `grep -n "reverse_barbell_curl\|reverse_curl" exercises.json` → `reverse_wrist_curl` exists (wrist extension, not elbow flexion). No collision.

### B.4 Two-Arm Lock-Off Holds (multi-angle isometric)
- **Proposed ID**: `two_arm_lockoff_multi_angle`
- **Description**: Two-arm bar hold at three elbow angles: 160° (shallow), 120° (mid), 90° (deep lock). 3 sets × 10-s holds at each angle, 2-3 min rest. Direct transfer to climbing lock-off positions.
- **Equipment**: `equipment_required: ["pullup_bar"]`; optionally add weight.
- **Source**: Gripped *Bigger Biceps* [#7] (the exact three-angle protocol); Nelson/TrainingBeta on bar isometrics [#5] ("two-arm hangs at different joint angles and hand positions... for maybe 5-10 minutes").
- **Proposed role**: `main`
- **Proposed domain**: `lock_off_endurance` (catalog already has this domain for related work) OR `strength_general`.
- **Proposed pattern**: `elbow_flexion` (to route into biceps bucket) — **[inference]**: existing `lock_off_isometric` in catalog uses `pattern: pull_vertical` and routes to `back_pulling`. If we want this new entry to populate the biceps bucket specifically, we need `elbow_flexion` (or multi-pattern `["elbow_flexion", "pull_vertical"]`). Alternative: add to biceps `include_ids` list like existing `chinup`.
- **Why climbing-relevant**: Directly trains the position climbers hold when reaching for the next hold. Bar isometrics at neutral/supinated/pronated grips let the same exercise hit biceps, brachioradialis, and lat differentially.
- **Duplicate check**: `grep -n "two_arm_lockoff\|lockoff_multi" exercises.json` → not found. Related: existing `lock_off_isometric` (`role: main`, `pattern: pull_vertical`, routes to back_pulling). The new entry is the biceps-bucket-routed, angle-explicit variant — Daniele may prefer instead to **re-tag `lock_off_isometric` with multi-pattern `["pull_vertical", "elbow_flexion"]`** so it populates both buckets, rather than duplicating. **Flag as C225 decision point.**

**Recommended minimum biceps `main` set (gym_full): B.1, B.2, B.3** → 3 mains. If Daniele prefers to include B.4, that's 4.

**Home-minimum (dumbbell or band):**
- B.2 (hammer curl) — dumbbell required, most home setups have one.
- B.3 (reverse curl) — dumbbell or weight.
- If home has `pullup_bar`: B.1 (weighted chinup — but requires weight) or B.4 (two-arm lockoff bodyweight).
- **Target**: main ≥ 2 at home is achievable with B.2 + B.3 (dumbbell) OR B.4 (pullup_bar, bodyweight).

---

## 5. Bucket C — Nice-to-have accessories / prehab

Lower priority; include only if Daniele decides to expand prehab coverage too.

### C.1 Wrist Wrench Peak Force (Nelson)
- **Proposed ID**: `wrist_wrench_peak_force`
- **Description**: Cord-loaded wrist wrench device (DIY $7-10 per Nelson). Peak force protocol: heavy load, 5-s hold, 5-7 sets. Targets open-hand wrist strength for compression climbing.
- **Equipment**: `equipment_required: ["weight"]` + wrist wrench (no canonical ID — treat as DIY via weight + cord).
- **Source**: Nelson — *Wrist Wrench* [#4].
- **Proposed role**: `main` (peak force is strength-range) or `accessory` if the tool is considered specialty.
- **Proposed domain**: `strength_general` + `prehab_wrist`.
- **Proposed pattern**: `wrist_flexion` or `wrist_extension` (two variants per cord position).
- **Why climbing-relevant**: Open-hand compression wrist specificity. Nelson reports transfer to open-hand control on the wall. Useful for sandstone/sloper specialists.
- **Duplicate check**: `grep -n "wrist_wrench" exercises.json` → not found.

### C.2 Plank Clocks (multi-directional wrist stability)
- **Proposed ID**: `plank_clocks`
- **Description**: Plank position with wrists in closed-chain loading. Reach a band-anchored direction at 12/3/6/9 o'clock positions. Proprioceptive wrist stability.
- **Equipment**: `equipment_required_any: ["resistance_band"]`.
- **Source**: Hooper's Beta *Wrist Stability Pt.1* [#6] — prehab/proprioception, 3 sets to fatigue.
- **Proposed role**: `prehab`
- **Proposed domain**: `prehab_wrist`
- **Proposed pattern**: `anti_rotation` (already in catalog) — this would route to `core` bucket, not forearms. **Misfit for the forearms bucket goal.**
- **Why climbing-relevant**: Closed-chain wrist load reflects mantling, slab palming, compression wrist positions.
- **Duplicate check**: `grep -n "plank_clocks" exercises.json` → not found.
- **Caveat**: Due to pattern routing, this will NOT appear in the forearms pool unless explicitly added via `include_ids` to the forearms bucket rules. Marking as C-tier.

### C.3 Knuckle Push-ups (closed-chain wrist extension)
- **Proposed ID**: `knuckle_pushup`
- **Description**: Push-up on closed fists (knuckles), wrist in neutral/extended with weight loaded through the knuckles. Closed-chain wrist extensor proprioception.
- **Equipment**: none.
- **Source**: Hooper's Beta *Wrist Stability Pt.1* [#6].
- **Proposed role**: `prehab` or `accessory`
- **Proposed domain**: `prehab_wrist` + `strength_general`
- **Proposed pattern**: `push` — **misfit** (would route to chest/triceps, not forearms).
- **Why climbing-relevant**: Niche — helps mantling and slab palming. Low priority unless a "wrist stability" session is envisioned.
- **Duplicate check**: `grep -n "knuckle_pushup" exercises.json` → not found.

### C.4 One-Arm Chin-up Progression (Hörst H.I.T.)
- **Proposed ID**: `one_arm_chinup_progression`
- **Description**: Assisted one-arm chin-up with band or pulley counterweight, progressing toward true one-arm. 3-5 sets × 2-3 reps per side. Extreme max-strength protocol.
- **Equipment**: `equipment_required: ["pullup_bar"]`, `equipment_required_any: ["resistance_band", "cable_machine"]`.
- **Source**: Hörst *Nicros H.I.T.* [#12].
- **Proposed role**: `main`
- **Proposed domain**: `strength_pulling`
- **Proposed pattern**: `elbow_flexion` + `pull_vertical`.
- **Why climbing-relevant**: One-arm lock-off capacity is cited by Hörst as the single biggest correlate with elite climbing. Very advanced — should gate by experience like hangboard gate D35.
- **Caveat**: High injury risk. Probably defer to a dedicated advanced-pulling C-brief rather than a forearms/biceps fill.

---

## 6. Cross-check summary (proposed IDs vs existing catalog)

| Proposed ID | Catalog collision? | Nearest existing |
|---|---|---|
| `wrist_roller` | not found | none — `wrist_curl` is prehab/dumbbell, different exercise |
| `wide_pinch_extended_wrist_hold` | not found | `pinch_block_training` (fingers bucket, different intent) |
| `heavy_reverse_wrist_curl` | not found | `reverse_wrist_curl` (prehab role, 2×15-20) — distinct dosing/role |
| `offset_dumbbell_pronation_supination` | not found | `stick_pronation_supination_eccentric` (prehab), `forearm_pronation_supination` (bodyweight prehab) — distinct role |
| `barbell_hold_thick_bar` | not found | `farmers_carry` (conditioning) — distinct as static strength hold |
| `weighted_chinup` | not found | `chinup` (bodyweight accessory) — distinct |
| `hammer_curl` | not found | `bicep_curl` (supinated) — distinct grip |
| `reverse_barbell_curl` | not found | `reverse_wrist_curl` (wrist extension, unrelated mechanic) |
| `two_arm_lockoff_multi_angle` | not found | `lock_off_isometric` (pull_vertical, routes to back_pulling) — candidate for consolidation, see §4-B.4 |
| `wrist_wrench_peak_force` | not found | none |
| `plank_clocks` | not found | `pallof_press` (anti_rotation, different mechanic) |
| `knuckle_pushup` | not found | `pushup` family |
| `one_arm_chinup_progression` | not found | `chinup`, `lock_off_isometric` |

---

## 7. Minimum viable list

To achieve `main ≥ 3` in `gym_full` and `main ≥ 2` in `home_min_hangboard` (fallback to accessory allowed for third slot at home per D223 fallback policy):

### Forearms (gym_full ≥ 3 mains)
1. **A.1 `wrist_roller`** — pattern `wrist_flexion`, equipment `weight`/`dumbbell`/`barbell`.
2. **A.2 `wide_pinch_extended_wrist_hold`** — pattern `wrist_extension`, equipment `pinch_block` OR `weight`.
3. **A.3 `heavy_reverse_wrist_curl`** — pattern `wrist_extension`, equipment `dumbbell`/`barbell`.
4. (optional) **A.4 `offset_dumbbell_pronation_supination`** — pattern `forearm_pronation`, equipment `dumbbell`.

### Biceps (gym_full ≥ 3 mains)
1. **B.1 `weighted_chinup`** — pattern `elbow_flexion`, equipment `pullup_bar` + `weight`.
2. **B.2 `hammer_curl`** — pattern `elbow_flexion`, equipment `dumbbell`.
3. **B.3 `reverse_barbell_curl`** — pattern `elbow_flexion`, equipment `barbell`/`dumbbell`.
4. (optional) **B.4 `two_arm_lockoff_multi_angle`** — pattern `elbow_flexion`, equipment `pullup_bar`. *OR* re-tag existing `lock_off_isometric` with multi-pattern.

### Home coverage (home_min_hangboard + dumbbell/band)
- Forearms home: A.3 `heavy_reverse_wrist_curl` + (fallback to existing prehab `reverse_wrist_curl`/`wrist_curl` if only hangboard+band available).
- Biceps home: B.2 `hammer_curl` + B.3 `reverse_barbell_curl` (both dumbbell-only) reaches `main ≥ 2` cleanly with just a dumbbell.

**Grand total: 6 new exercises (3 forearms + 3 biceps) → closes both gaps with margin, aligned with Hörst + Lattice + Nelson consensus.**

---

## 8. Flags / caveats for C225 decision

1. **Pattern routing for `two_arm_lockoff_multi_angle` vs existing `lock_off_isometric`.** Either add `elbow_flexion` to the existing entry's pattern array (re-routes it into biceps bucket too) OR add a new entry. Consolidation is cleaner; duplication is safer. **Daniele's call.**
2. **`barbell_hold_thick_bar` relies on `pattern: carry` which is NOT in the forearms bucket allowlist.** Requires either (a) adding to `include_ids`, or (b) adding `carry` to the forearms patterns list (picker rule edit — minor but touches `body_part_picker.py`). **Flag as in-scope for C225 or split into separate micro-brief.**
3. **No canonical `wrist_roller` equipment ID** in `vocabulary_v1.md §1.2`. Exercises that require the Lattice Heavy Roller tool can only declare `weight`/`dumbbell`/`barbell` as a DIY fallback, which is imprecise. Consider adding `wrist_roller` to the equipment vocabulary in a companion brief (trivial), OR accept the DIY fallback (pragmatic).
4. **Home-no-weight corner case**: users with only `hangboard` + `resistance_band` cannot reach `main ≥ 2` for forearms via any of the proposed mains. The D223 fallback policy already covers this by falling back to accessory/prehab. No new exercise closes this without assuming a dumbbell or a band-only creative protocol (none of the authoritative sources I consulted prescribe a pure band-only wrist strength protocol in the strength range — bands appear only in prehab/rehab contexts).
5. **`role: [main, prehab]` dual-role entries**: Hörst's *Wide Pinch Extended Wrist* blurs the prehab/strength line. Catalog has precedent for multi-role (`nordic_curl: ["accessory", "prehab"]`, `scapular_pullup: ["accessory", "prehab", "activation"]`). Dual-role is cleaner than duplicating into prehab + main variants, but the picker's `role: main` filter will happily accept `role: [main, prehab]`. Recommend dual-role for A.2.
6. **`recency_group` values needed for each new entry** (required by `vocabulary_v1.md §2.7`). Suggested groups (not exhaustive; confirm during C225):
   - `forearm_wrist_extensor` — A.2, A.3
   - `forearm_wrist_flexor` — A.1
   - `forearm_rotation` — A.4
   - `forearm_carry` — A.5
   - `biceps_weighted_pull` — B.1
   - `biceps_elbow_flexion` — B.2, B.3
   - `biceps_lockoff` — B.4
