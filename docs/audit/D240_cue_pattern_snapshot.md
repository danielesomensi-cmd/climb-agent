# D240 — Process cue pattern snapshot for KB

> **Type:** D (read-only audit / extraction)
> **Date:** 2026-05-19
> **Origin:** D239 follow-up — coverage gap (11/35 sessioni senza cue)
> **Purpose:** Provide a self-contained pattern document for the claude.ai
> project "climb-agent knowledge base" to generate ~20-25 new process cues in
> a format coherent with the existing 35.

---

## How to use this document

1. **Copy this entire file** into the climb-agent KB project as a single message.
2. Append: *"Propose new process cues per §6 (Gap analysis). Return one JSON array in a markdown code block, schema per §7."*
3. KB responds with proposals.
4. A C-brief in climb-agent codebase merges the proposals into
   `backend/catalog/cues/v1/process_cues.json`.

---

## §0 — What a process cue is

A **process cue** is a short, deterministic coaching reminder attached to a
single training session. It appears in the user's guided session UI as a
banner labelled *"Today's focus"*, intended to nudge attention toward one
specific quality aspect (mindset, technique, breathing, rest behaviour, etc.).

- **Deterministic selection**: `hash(user_id + date) → idx % len(matching_cues)`,
  matched by `session_template_id ∈ cue.session_types`.
- **One cue per session per day**: same user + same date + same session →
  same cue. Different days rotate naturally.
- **No personalisation beyond session type**: cues are not gated by grade,
  discipline, phase, or experience level (today).

---

## §1 — Schema (current, authoritative)

File: `backend/catalog/cues/v1/process_cues.json`. JSON array of 35 objects.

Every object has **exactly four fields**, all mandatory (35/35 coverage):

```json
{
  "id": "cue_028",
  "text": "Walk between attempts — don't sit down. Active rest accelerates lactate clearance by ~35%.",
  "session_types": ["limit_boulder_gym", "power_contact_gym", "boulder_circuit_gym"],
  "source": "Draper 2006 + Watts 2000"
}
```

| Field | Type | Constraint |
|-------|------|------------|
| `id` | string | Format `cue_NNN` with 3-digit zero-padded sequential index. Next ID after this batch: **`cue_036`**. |
| `text` | string | The cue itself. 79–163 chars (avg 116, median 113), 13–28 words (avg/median 19). 1–2 sentences (29/35) or 3 sentences (6/35). |
| `session_types` | array of strings | Whitelist of `session_template_id` values where this cue is eligible. Plus one pseudo-tag `_any_last_session_before_rest` (1 cue, `cue_013`). Values must match real session ids in `backend/catalog/sessions/v1/`. |
| `source` | string | Citation. All 35 existing cues have one. Format varies (see §5). For the new batch, Daniele has relaxed this — `source` may be omitted if the cue is general coaching wisdom without a specific reference. |

**Fields NOT in the schema** (do not propose them — they'd be ignored at runtime
and break the linter): `phases`, `weight`, `tags`, `discipline`, `grade_min`,
`grade_max`, `priority`, `experience_level`. The brief that triggered this
audit suggested some of these — they are **out of scope**. The current selection
algorithm (`backend/engine/cues.py:38-78`) reads only `session_types`.

---

## §2 — Valid session_types (the only ones cues may reference)

The 35 real session_ids in `backend/catalog/sessions/v1/` plus the special
pseudo-tag. Anything outside this list is invalid.

| Session type | Description |
|--------------|-------------|
| `boulder_circuit_gym` | Volume/circuits, technical work, sub-max boulders |
| `complementary_conditioning` | Antagonist + accessory work |
| `core_training` | Core-focused conditioning |
| `deload_recovery` | Active recovery during deload week |
| `easy_climbing_deload` | Easy climbing during deload |
| `endurance_aerobic_gym` | Aerobic capacity ARC-style |
| `finger_aerobic_base` | Low-intensity finger aerobic |
| `finger_endurance_short` | Hangboard endurance short reps |
| `finger_maintenance_gym` | Finger maintenance at gym hangboard |
| `finger_maintenance_home` | Finger maintenance at home hangboard |
| `finger_strength_home` | Max hangs / heavy hangs at home |
| `flexibility_full` | Full-body mobility/flexibility |
| `handstand_practice` | Handstand technical practice |
| `heavy_conditioning_gym` | Heavy weights conditioning |
| `legs_strength` | Lower body strength |
| `limit_boulder_gym` | Limit boulders / projects |
| `lower_body_gym` | Lower body conditioning |
| `power_contact_gym` | Contact strength / explosive boulder |
| `power_endurance_gym` | Power endurance circuits / linked problems |
| `prehab_maintenance` | Antagonist + injury prevention |
| `pulling_strength_gym` | Heavy pull-ups / lock-offs |
| `regeneration_easy` | Easy session with regen focus |
| `route_endurance_gym` | Route laps / endurance routes |
| `route_projecting_gym` | Route project attempts |
| `strength_long` | Long-duration hangboard protocols |
| `technique_focus_gym` | Movement drills / technique |
| `test_lp_max_5s` | Test session: long-pinch max 5s |
| `test_lp_repeater` | Test session: long-pinch repeater |
| `test_max_hang_5s` | Test session: max hang 5s |
| `test_max_hang_7s` | Test session: max hang 7s |
| `test_max_weighted_pullup` | Test session: max weighted pull-up |
| `test_pullup_bw` | Test session: bodyweight pull-ups to failure |
| `test_repeater_7_3` | Test session: 7-3 repeater capacity |
| `upper_body_weights` | Upper body conditioning |
| `yoga_recovery` | Yoga-based recovery |
| `_any_last_session_before_rest` | **PSEUDO-TAG**: matches any session immediately before a rest day. Used by `cue_013`. |

---

## §3 — Tone & style guide (inferred from existing 35)

### Statistics

- **Length**: 79–163 chars (avg 116 / median 113). **Target: 90–130 chars** for new cues. Avoid sub-80 (too terse, loses rationale) or over-150 (too long for UI banner).
- **Words**: 13–28 (avg/median 19). **Target: 16–24 words.**
- **Sentences**: 29/35 are 1–2 sentences. 6/35 are 3 sentences. **Target: 2 sentences (action + rationale).**
- **Voice**: ~33/35 imperative or directive in second person. **Use imperative.** Avoid "you should..." / "it's recommended..." — too soft.
- **Language**: English only. No translation.
- **Punctuation**: prefer em-dash (`—`, not `--`) for the action/rationale split. Single quotes inside text fine.

### Pattern: action → rationale

The dominant pattern is **one imperative directive followed by the *why***:

> *"Walk between attempts — don't sit down. Active rest accelerates lactate clearance by ~35%."*

The rationale matters because:
- It anchors the cue in physiology / motor learning / methodology (not arbitrary advice).
- It gives the user a reason to comply ("OK, that's why").
- It enables self-extrapolation: if the user understands *why*, they apply it beyond the literal moment.

### Alternative patterns (acceptable)

- **Declarative reframing** (~3/35): *"Today is deload — resist the temptation to go hard..."* — used when the cue establishes context rather than a specific action.
- **Question + action**: *"Read each problem fully before starting. Where's the crux? Where will you rest?"* — used for cognitive cues (route reading, projecting).
- **Conditional**: *"If your foot cuts, ask why — body tension or placement?..."* — used for self-eval cues.

### Anti-patterns to avoid

- ❌ "Remember to..." / "Don't forget to..." (weak, condescending)
- ❌ "You should..." / "It's important to..." (soft, non-actionable)
- ❌ Generic motivation without specific action ("Push hard today!")
- ❌ Multi-action cues ("Warm up, then breathe, then focus on feet, then..."). One focus per cue.
- ❌ Numeric prescription that overlaps with the exercise's own sets/reps prescription ("Do 3×5 hangs at 90%"). The cue is about *how*, not *what*.

### 5 representative exemplars (good ones to imitate)

```json
{
  "id": "cue_028",
  "text": "Walk between attempts — don't sit down. Active rest accelerates lactate clearance by ~35%.",
  "session_types": ["limit_boulder_gym", "power_contact_gym", "boulder_circuit_gym"],
  "source": "Draper 2006 + Watts 2000"
}
```
*Why good: classic action + rationale, specific physiology citation, ~110 chars.*

```json
{
  "id": "cue_006",
  "text": "G-Tox: while resting on the wall, alternate your arms — overhead for 5s, then down at your side for 5s. Gravity helps clear metabolites faster.",
  "session_types": ["route_endurance_gym", "endurance_aerobic_gym", "power_endurance_gym", "route_projecting_gym"],
  "source": "D17"
}
```
*Why good: names the technique, gives concrete protocol numbers, explains the mechanism.*

```json
{
  "id": "cue_014",
  "text": "Squeeze every rep with maximal intent. On hangboard, the difference between 90% effort and 100% effort is the difference between maintenance and adaptation.",
  "session_types": ["finger_strength_home", "strength_long"],
  "source": "D78"
}
```
*Why good: contrasts adjacent intensities to make the point vivid, ties to outcome (adaptation), tight imperative.*

```json
{
  "id": "cue_021",
  "text": "Today is deload — resist the temptation to go hard. Your body is consolidating gains from the last phase. Trust the process.",
  "session_types": ["deload_recovery", "easy_climbing_deload"],
  "source": "D79"
}
```
*Why good: declarative context-setting + emotional reframing for a specific phase.*

```json
{
  "id": "cue_032",
  "text": "Scale the warm-up: 15-20 minutes progressive, never a cold start. Flash pump prevention requires a gradual ramp.",
  "session_types": ["limit_boulder_gym", "power_contact_gym", "boulder_circuit_gym", "route_projecting_gym", "power_endurance_gym"],
  "source": "Hörst Ch.12 + López"
}
```
*Why good: protocol numbers ("15-20 min"), names the risk ("flash pump"), broad session_types coverage.*

---

## §4 — Coverage map (current state)

35 cues distributed unevenly across 24 session_types (out of 35 valid types) + 1 pseudo-tag.

| Session type | # cues | Cue IDs |
|---|---:|---|
| `boulder_circuit_gym` | 18 | cue_001, 002, 007, 009, 010, 011, 015, 020, 022, 024, 025, 026, 028, 030, 031, 032, 034, 035 |
| `limit_boulder_gym` | 13 | cue_001, 007, 022, 025, 026, 027, 028, 029, 030, 031, 032, 033, 035 |
| `power_contact_gym` | 10 | cue_001, 007, 022, 025, 026, 028, 029, 030, 032, 035 |
| `technique_focus_gym` | 8 | cue_002, 008, 009, 010, 011, 015, 016, 024 |
| `route_projecting_gym` | 8 | cue_001, 005, 006, 007, 008, 025, 032, 035 |
| `power_endurance_gym` | 6 | cue_001, 006, 020, 025, 032, 035 |
| `route_endurance_gym` | 6 | cue_002, 005, 006, 008, 020, 025 |
| `strength_long` | 5 | cue_003, 007, 014, 017, 019 |
| `regeneration_easy` | 5 | cue_002, 010, 011, 016, 024 |
| `finger_strength_home` | 4 | cue_003, 014, 017, 019 |
| `finger_aerobic_base` | 3 | cue_003, 012, 019 |
| `finger_maintenance_gym` | 3 | cue_003, 017, 019 |
| `finger_maintenance_home` | 3 | cue_003, 017, 019 |
| `endurance_aerobic_gym` | 3 | cue_005, 006, 012 |
| `complementary_conditioning` | 3 | cue_004, 018, 023 |
| `pulling_strength_gym` | 3 | cue_004, 018, 023 |
| `heavy_conditioning_gym` | 3 | cue_004, 018, 023 |
| `finger_endurance_short` | 2 | cue_003, 019 |
| `upper_body_weights` | 2 | cue_004, 018 |
| `core_training` | 1 | cue_004 |
| `legs_strength` | 1 | cue_004 |
| `lower_body_gym` | 1 | cue_004 |
| `deload_recovery` | 1 | cue_021 |
| `easy_climbing_deload` | 1 | cue_021 |
| `_any_last_session_before_rest` | 1 | cue_013 |
| **`test_max_hang_7s`** | **0** | — **ZERO** — |
| **`test_max_hang_5s`** | **0** | — **ZERO** — |
| **`test_lp_max_5s`** | **0** | — **ZERO** — |
| **`test_lp_repeater`** | **0** | — **ZERO** — |
| **`test_repeater_7_3`** | **0** | — **ZERO** — |
| **`test_max_weighted_pullup`** | **0** | — **ZERO** — |
| **`test_pullup_bw`** | **0** | — **ZERO** — |
| **`yoga_recovery`** | **0** | — **ZERO** — |
| **`flexibility_full`** | **0** | — **ZERO** — |
| **`handstand_practice`** | **0** | — **ZERO** — |
| **`prehab_maintenance`** | **0** | — **ZERO** — |

### Observations

- Coverage is heavily **boulder-skewed**. Top 3 most-covered are all boulder session types.
- Underserved (1-2 cues each): `core_training`, `legs_strength`, `lower_body_gym`, `upper_body_weights`, `deload_recovery`, `easy_climbing_deload`, `finger_endurance_short`. **More cues welcome here**, especially conditioning-specific (form vs ego on heavy lifts, hip drive, scapular packing, etc.).
- **11 zero-coverage** session types (the explicit ask).
- `boulder_circuit_gym` has 18 cues → already saturated; new cues should rarely target it.

---

## §5 — Source citation patterns

All 35 cues have a `source`. Three styles observed:

1. **Internal doc code only** (~15/35): `"D78"`, `"D17"`, `"D45"`, `"D33"`. These reference internal climb-agent docs (literature reviews, design docs). **KB does not have access to these IDs** and should NOT invent them.
2. **Author/study direct** (~12/35): `"Hörst (mental movie)"`, `"Hörst Ch.12 + López"`, `"Draper 2006 + Watts 2000"`, `"Ondra/Bachar"`, `"Seifert 2017 (preview improves fluency...)"`. KB **can** use this style — cite the author/year if the cue draws on identifiable research or methodology.
3. **Hybrid code + study** (~7/35): `"D75 (Seifert 2017)"`, `"D48 (Valenzuela 2015)"`. KB should use just the author/year part (no D-codes).

### Frequency of `source` values

- `D78` (generic technique reference): 11 cues — the catch-all when no specific study applies
- `D79` (deload/rest reference): 2 cues
- All other sources: 1 cue each

### Daniele's decision (2026-05-19)

> `source` is **optional** for the new batch. Cite naturally where the cue derives from a specific study or coach (Hörst, Lattice, Eva López, Tyler Nelson, MacLeod, Schweizer, Seifert, Watts, Draper, Valenzuela, Earp, Fradkin, Ondra/Bachar, etc.). **Omit the field entirely** if the cue is general process advice without a specific reference. Do NOT fabricate citations.

If KB includes a citation, prefer **`AuthorYear (concept)`** format: `"Hörst Ch.7 (max recruitment)"`, `"López 2021 (intermittent dead-hangs)"`, etc.

---

## §6 — Gap analysis — what to generate

**Target: ~20-25 new cues**, distributed as follows.

### A. Test sessions — 7 cues mandatory, 1 per session (≈7-10 total)

These are the dedicated assessment days. Tone should differ from training cues:
emphasise **measurement quality**, **no PR-chasing during the warm-up**, **full
recovery between max attempts**, **honest self-reporting**.

| Session ID | What it measures | Suggested cue theme |
|---|---|---|
| `test_max_hang_7s` | Max 7s hang on 20mm edge | Warm-up neurale graduale, qualità del rep, no PR-chasing on warm-up rungs |
| `test_max_hang_5s` | Max 5s hang on 20mm edge | Same as 7s but shorter contact → focus on pure recruitment quality |
| `test_lp_max_5s` | Max 5s on long-pinch grip | Thumb engagement, full pad contact, don't compromise wrist angle for "feel" |
| `test_lp_repeater` | Long-pinch repeater capacity | Pacing — don't blow the early sets chasing reps |
| `test_repeater_7_3` | 7-on-3-off repeater max sets | Same pacing logic + form breakdown = stop signal |
| `test_max_weighted_pullup` | 1RM weighted pull-up | Full extension, full chin-over-bar, no kipping. Earn the rep. |
| `test_pullup_bw` | Reps to failure bodyweight pull-ups | Pace; full ROM each rep; the rep that breaks form doesn't count |

**Common test-day themes** (1-3 cross-cutting cues welcome, targeting multiple test_* session_types):
- Honest self-reporting → the test data shapes 4-8 weeks of training, garbage in = garbage out
- No comparison to previous tests during the warm-up
- 5+ min between max attempts (neural recovery)
- Document baseline conditions (sleep, food, fatigue) — data only useful with context

### B. Ancillary sessions — 4 cues mandatory, 1 per session (≈4-6 total)

Low-volume technical/recovery sessions. Tone is calmer, more **mind-body**.

| Session ID | Theme |
|---|---|
| `yoga_recovery` | Breathing as anchor; let the climbing day's tension dissolve; not a stretch competition |
| `flexibility_full` | Static stretch held ≥30s; never to pain; consistency > intensity |
| `handstand_practice` | Stack alignment (wrist-shoulder-hip-heel); micro-corrections every 3 breaths; falls are reps |
| `prehab_maintenance` | Slow tempo on antagonist work; the unsexy work is the work that keeps you climbing past 35 |

### C. Cross-cutting (~8-12 cues)

Themes underrepresented in the current 35. These can target multiple existing
session_types (broad `session_types` arrays welcome). **Prioritise lead-specific
content** — the current 35 are boulder-heavy.

Suggested themes:

1. **Fear management on lead** — accepting controlled falls, the "fall practice" mental routine. Target: `route_projecting_gym`, `route_endurance_gym`, `power_endurance_gym`.
2. **Clip strategy & pacing on lead** — clip from stable positions, pre-rehearse the clipping holds. Target: `route_projecting_gym`, `route_endurance_gym`.
3. **Breath cadence under pump** — the 4-second exhale during forearm pump. Target: `route_endurance_gym`, `endurance_aerobic_gym`, `power_endurance_gym`, `route_projecting_gym`.
4. **Antagonist activation between climbs** — 10 reps of scapular pushup / band external rotation while resting. Target: `boulder_circuit_gym`, `route_endurance_gym`, `route_projecting_gym`, `power_endurance_gym`.
5. **Partner/belay communication** — call the clip, call the fall, call the rest. Target: `route_endurance_gym`, `route_projecting_gym`.
6. **Tactical pacing on multi-pitch / long routes** — manage forearm in the lower 1/3, save reserves for the crux. Target: `endurance_aerobic_gym`, `route_endurance_gym`.
7. **Hydration/fueling mid-session** — 20-30g carbs at the 60-min mark for sessions >90 min. Target: `route_projecting_gym`, `limit_boulder_gym`, `power_endurance_gym`.
8. **Skin management** — file vs sand, when to call the session for skin reasons. Target: `limit_boulder_gym`, `power_contact_gym`, `boulder_circuit_gym`, `route_projecting_gym`.
9. **Pre-session activation routine** — 5 min specific warm-up after general warm-up (low-grade target hold patterns). Target: `finger_strength_home`, `strength_long`, `limit_boulder_gym`.
10. **Mental refresh between attempts on a project** — 90-second eyes-closed cooldown of the previous attempt before the next try. Target: `route_projecting_gym`, `limit_boulder_gym`.
11. **Conditioning underserved**: lock-off control, hip-drive on heel hooks, scapular packing for pull-ups. Target: `pulling_strength_gym`, `upper_body_weights`, `complementary_conditioning`.
12. **Hangboard safety** — pulley load awareness, especially crimp protocols; the half-crimp is a contract with your tendons. Target: `finger_strength_home`, `strength_long`.

KB has discretion to add/swap themes — use the literature you have access to
(Hörst, Lattice, Eva López, Tyler Nelson, MacLeod, Schweizer, Seifert).

### D. Constraints

- **Do not duplicate** an existing cue (semantic duplication or same theme + same session_types). The current 35 are listed in §4 by ID.
- **Do not target only oversaturated session_types** (`boulder_circuit_gym` already has 18).
- **`session_types` arrays must use only the 35 valid IDs from §2** (+ `_any_last_session_before_rest` if relevant). Misspellings or new types will fail validation.

---

## §7 — Output format for KB

KB must respond with **one markdown code block containing a JSON array**, in the
existing schema. Example structure:

````
```json
[
  {
    "id": "cue_036",
    "text": "Document tonight's sleep, fatigue, and fueling before testing. The number you record only means something with context — without it, you're measuring noise.",
    "session_types": ["test_max_hang_7s", "test_max_hang_5s", "test_lp_max_5s", "test_repeater_7_3", "test_lp_repeater", "test_max_weighted_pullup", "test_pullup_bw"],
    "source": "Lattice (test reliability protocols)"
  },
  {
    "id": "cue_037",
    "text": "Stack your alignment from the ground up — wrists, shoulders, hips, heels. Micro-correct every three breaths; falls are reps, not failures.",
    "session_types": ["handstand_practice"]
  }
]
```
````

### Rules for the response

1. **One JSON array**, exact valid JSON (parseable). No comments, no trailing commas.
2. **IDs**: sequential starting at `cue_036`. No gaps.
3. **session_types**: only IDs from §2 (35 valid types + the pseudo-tag).
4. **source**: optional. Omit the field entirely if no citation; do not write `"source": null` or `"source": ""`.
5. **Length**: aim for 90–130 chars / 16–24 words per `text`.
6. **No new fields** (`phases`, `weight`, `tags`, etc. will be rejected).
7. **20–25 cues total** in the array.
8. **English only**.

---

## §8 — Validation hooks (what the C-brief in climb-agent will check)

When the new cues are merged into the catalog, the implementation brief will
run these checks. KB should pre-validate against them:

1. JSON parses cleanly.
2. Each `id` matches `^cue_\d{3}$` and is sequential after the last existing ID.
3. Each `session_types` value ∈ the 35-valid set from §2.
4. No duplicate IDs.
5. No cue with empty `session_types` array.
6. (Soft) `text` length between 70 and 180 chars.
7. (Soft) `text` is a non-trivial English string (≥10 words).

After merge:
- The full `process_cues.json` will be tested against `backend/tests/test_process_cues.py`.
- The 11 currently-uncovered session types should reach coverage ≥1 each.
- New cross-cutting cues will land in matching sessions on the next plan regeneration.

---

## §9 — Out of scope for KB

Do **not** propose:
- Frontend changes (where the cue is displayed) — separate A-brief.
- Schema extensions — separate D-brief if Daniele decides to expand.
- Changes to the selection algorithm (hash-based deterministic) — separate A-brief.
- Catalog reorganisation (sharding, versioning) — separate D-brief.
- New session types — the 35 are fixed; cues attach to them.

---

## §10 — Anchor for Daniele

When you copy this doc into the KB project, also paste this short prompt at the end:

> *Generate 20-25 new process cues per §6 (Gap analysis). Follow §1 schema strictly. Apply §3 tone. Avoid §4 oversaturated session_types. Use §5 source rules. Return one JSON array per §7. Pre-validate against §8.*

Then when KB returns, run the proposals through a quick sanity check and open a
C-brief in the climb-agent repo to merge them.
