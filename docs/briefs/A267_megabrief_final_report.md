# Megabrief — Assessment Overhaul: Final Report

**Date:** 2026-08-06 · **Branch:** `brief/A267-assessment-megabrief` (worktree `../climb-agent-megabrief`)
**Origin:** `docs/audit/D260_tooltip_and_assessment_scoring.md`

> **STOP.** Packages 1–4 are delivered. Packages 5–6 are analyses only — **nothing from them has been
> implemented and nothing should be, until Daniele decides §3**.

---

## 1. Package → brief-ID table

| Pkg | Assigned ID | Deliverable | Commit | Status |
|---|---|---|---|---|
| 1 | **C267** | `docs/research/assessment_scoring_research_2026-08.md` + KB pointers | `9f28f0a` | ✅ delivered |
| 2 | *(none — B323 not consumed)* | Tooltip clamping + axis relabel | — | ⏭️ **already done by B304**, see §1.1 |
| 3 | **A267** | Radar Elite comparison mode (display-only) | `585508c` | ✅ delivered — **needs Vercel preview approval before merge** |
| 4 | *(none — bookkeeping)* | `docs/ROADMAP_CURRENT.md` updates | `d07881f` | ✅ delivered |
| 5 | **D271** | `docs/audit/D271_endurance_test_analysis.md` | `1d5f5a9` | 📋 analysis only |
| 6 | **D272** | `docs/audit/D272_gap_demotion_analysis.md` | `15f9c19` | 📋 analysis only |

Total diff vs `origin/main`: **12 files, +1845 / −43**. `python scripts/next_brief.py` was run before
each package; `B323` and `C268` remain free.

**Two deliberate deviations from the brief's instructions, both flagged rather than silently taken:**

- **Package 4 was not given a brief ID.** It is a roadmap-bookkeeping commit for C267/A267; burning a
  `D` number on it would have pushed the analyses to D272/D273 and polluted the git-log ↔ roadmap
  reconciliation `scripts/next_brief.py` relies on. The analyses therefore took D271/D272.
- **`docs/ROADMAP_CURRENT.md` entries are in Italian.** The brief says "English for all code/docs/UI";
  that file is Italian end to end, and a single English entry inside it would be worse than either
  convention. Everything else — the research log, both analyses, all code, all comments, all UI copy —
  is English.

### 1.1 Package 2 was already delivered

`git log --all` shows **B304 — "tooltip viewport clamping + target-relative axis presentation"**
(`6970adb`), plus **B318** (`6bb8cfe`) for the SVG label clipping. Verified against the brief's
acceptance criteria, item by item:

| Brief requirement | Where it already lives |
|---|---|
| Viewport clamping, ≥ 12px margin both sides | `computeTooltipShift`, `TOOLTIP_MARGIN = 12` — `lib/radarTooltip.ts:27` |
| `env(safe-area-inset-*)` respected | `readSafeAreaInsets()` probe — `radar-chart.tsx:36`; `insetLeft`/`insetRight` in the clamp |
| `max-width: min(288px, calc(100vw − 24px))` | `w-72 max-w-[calc(100vw-24px)]` — `radar-chart.tsx:117` |
| Vertical behaviour vs the tab bar | `shouldFlipAbove`, `bottomSafe = 64 + inset` — flips above when it would land under the bar |
| No positioning library | Hand-rolled, measure-then-place in `useLayoutEffect` |
| Subtitle "Readiness for {target_grade}" | `plan/page.tsx:161` (moved into `RadarChart` by A267) |
| "✓ At target" badge at ≥ 100 | `radar-chart.tsx:263` |
| Five ⓘ copies rewritten, < 300 chars, roadmap-framed | `AXIS_DESCRIPTIONS` in `gradeUtils.ts:212`; asserted by `radar-tooltip.test.ts:146` |
| Tests at 320 / 390 / 768 / 1280 | `radar-tooltip.test.ts:16–79` — all four widths present |

**One thing the brief asked for that B304 did leave open, and it is now covered:** D260 said
`RadarChart` had exactly one consumer (`/plan`). It now has **two** — the public `/assessment` page
(`assessment/page.tsx:202`, added by A262/A263 after the audit). Because B304 put the clamping inside
the component rather than the page, `/assessment` inherits the fix for free. Verified, no action
needed.

The five final ⓘ copies are reproduced in §5 as the brief requested.

### 1.2 What A267 shipped

- `frontend/src/lib/eliteAnchors.ts` — the versioned anchor table, **data only** (`ELITE_ANCHOR_SET_VERSION = "elite_anchors_v1"`).
- `frontend/src/lib/eliteScoring.ts` — pure `(raw_inputs, anchor_set) → scores`, plus
  `extractEliteInputs(state)` reading numbers already present in `/api/state`.
- `radar-chart.tsx` — `[ Goal | Elite ]` segmented toggle, mode-aware subtitle, greyed axes render as
  an em dash and an **absent vertex** (never a zero), spokes instead of a polygon when fewer than three
  axes are live.
- `radarTooltip.ts` — `buildEliteAxisTooltipCopy`, so the two framings never mix.
- 31 new tests. Frontend suite **508 passed**, `tsc --noEmit` clean, `eslint` clean, backend **3085 passed**.

At launch: **2 live axes** (Finger 200% BW, Pulling 187% BW), **3 greyed** — Endurance dormant with its
decided anchor (58.5 kg·s·kg⁻¹) already in the table, Power Endurance and Technique permanently.

**Sanity check on the author's real production data** (BW 76, max hang 122, weighted pull-up 127.8,
target 8b): Goal mode shows **✓ At target** on Finger and **96** on Pulling; Elite mode shows
**61** and **78** — plausible and sub-100, as required.

---

## 2. Global non-negotiables — verification

| # | Constraint | Verified how | Result |
|---|---|---|---|
| 1 | **Past sessions immutable** | `git diff --name-only origin/main \| grep '^backend/'` → **empty**. No engine, router, catalog or data file was touched by any package. A267 is render-only and issues no request; §2.1 proves it. | ✅ No code path exists that could modify a completed session |
| 2 | **No retroactive rescoring** | Nothing recomputes `assessment.profile`. The elite scores are a *second, parallel* view computed at render and discarded; stored scores are read and passed through unchanged (`plan/page.tsx:62`). Both analyses state the never-retroactive rule explicitly (D271 §7, D272 §7). | ✅ |
| 3 | **Active macrocycles never re-weighted in place** | Traced in D271 §6.2: `generate_macrocycle` writes `assessment_snapshot` (`macrocycle_v1.py:760`), the planners write `profile_snapshot`, and `replanner_v1` reads `profile_snapshot` in eleven places without ever re-reading `assessment.profile`. `state_checks.is_macrocycle_stale` only *reports*. | ✅ Verified read-only; no code shipped that could change it |
| 4 | **Equipment-based filtering, never location-based** | No filtering logic touched. D271 §3.2 keeps to it: it proposes `pulley_system` as an *equipment* entry, and gates the test on equipment availability, never on gym vs home. | ✅ |
| 5 | **Fontainebleau / English / no placeholders** | Boulder grades are untouched; A267's inputs are kg and %BW, grade-free. All code, comments, UI copy and both analyses are English (roadmap exception in §1). Nothing was invented: every gap is an open question in §4. | ✅ |
| 6 | **Packages 5–6 write zero application code** | `git show --stat 1d5f5a9` → 1 file, `docs/audit/D271_endurance_test_analysis.md`. `git show --stat 15f9c19` → 1 file, `docs/audit/D272_gap_demotion_analysis.md`. | ✅ |

### 2.1 A267's display-only proof

The brief required proving no engine consumer can pick up the elite variant. Four independent checks:

1. **Importers of the elite modules — three, all render-path:**
   `app/(main)/plan/page.tsx` (decides whether to show the toggle), `components/onboarding/radar-chart.tsx`
   (renders), `lib/radarTooltip.ts` (copy). Plus the test file. Nothing else, anywhere.
2. **No I/O in the elite path.** `grep -E 'from "@/lib/api"|fetch\(|localStorage|sessionStorage|sendBeacon'`
   over `eliteScoring.ts`, `eliteAnchors.ts`, `radar-chart.tsx`, `radarTooltip.ts` → the only hit is the
   word `localStorage` inside a comment explaining why it is *not* used.
3. **Zero backend awareness.** `grep -rni elite backend/` returns only unrelated pre-existing strings
   (an exercise cue, a Hörst PE protocol description, a test-label list, KB citations). No endpoint,
   no field, no schema.
4. **Mutation guarantees are asserted, not assumed.** `elite-scoring.test.ts` pins that
   `computeEliteScores` leaves both the input object and `ELITE_ANCHORS_V1` byte-identical, and runs
   in a bare Node context with no `localStorage` and no fetch mock — a write attempt would throw
   rather than return a number.

Mode is `useState` inside the component. No DB field, no localStorage, no query param.

---

## 3. Executive summary of the two analyses — decisions awaiting Daniele

### 3.1 D271 — `test_endurance_intermittent`

Three findings, all quantified on the 18 production profiles.

**(i) The adoption gate is a blocker, and it is measurable.** 60% of the max-hang total is below
bodyweight for anyone under **166.7% BW**. Only 10 of 18 profiles have a usable max-hang base at all;
of those, **eight need to be unloaded** (2.8 kg for the author, up to 37.6 kg), one lands exactly at
bodyweight, and the single user who would *add* weight is `e60d7a0c`, whose finger data is already
flagged incoherent (A266-P1). **No production user can take this test today with added weight only.**

**(ii) The scored outcome carries finger strength multiplicatively.** At a fixed relative load,
`impulse = 0.6 × (max_hang/BW) × time_to_failure`. `max_hang/BW` spans **1.95×** across our users;
holding time-to-failure at 100 s, impulse alone would span 54 → 106 kg·s·kg⁻¹ — the whole Berta scale,
with zero endurance information. Structurally the same contamination D263 rejected the bodyweight hang
for. **The spec was not redesigned** (the brief forbade it); the finding is on the table.

**(iii) An absolute band→score mapping cannot ship in v1.** Our protocol lands ~1.6× above Berta's, so
both worked examples (the author and a 6c user) clamp to 100 on day one — reproducing D260's
saturation failure, for everyone, immediately. D267 predicted this; the numbers confirm it.

**Recommendation: two stages.** Stage 1 collects, stores the full row and *displays* the result with a
descriptive band position, while the Endurance axis stays derived and is flagged `estimated`.
Stage 2 calibrates on ~30 own results and flips the axis to measured.

**Decisions needed:** (1) add `pulley_system` and put the existing `band` into the gym equipment list —
without them the test ships to nobody; (2) introduce `profile_source` (`measured` / `estimated`),
which finally makes D260's hidden default honest but visibly caveats four other axes too; (3) score on
impulse, on time-to-failure, or both; (4) two-stage or ship the absolute mapping now.

**Equipment correction:** `assistance_band` **already exists** as the canonical id `band`
(`vocabulary_v1.md:36`); adding it would duplicate. The real gap is that `band` is missing from
`EQUIPMENT_GYM`. Only `pulley_system` is genuinely new. And the two are not interchangeable: a pulley
gives constant, quantifiable assistance and makes the test *scorable*; a band varies with stretch and
only makes it *performable*.

### 3.2 D272 — demoting the RP−OS gap

The gap has **exactly two consumers**, both in `assessment_v1.py`. Demoting it is contained; what it
exposes is not.

**Recommendation: option (c)** — Technique & Tactics becomes a `self_reported` axis, greyed and
excluded from the weight and duration machinery.

| Option | Verdict |
|---|---|
| (a) self-report only + hard cap | ❌ The cap is invented — the same unsourced-constant species D260 §7 criticised. On real data it moves scores in **both** directions: `e60d7a0c` goes 75 → 45 and *gains* technique weight |
| (b) weight-neutral informational axis | ❌ Displays a confident number that drives nothing; the user cannot tell it is inert |
| **(c) greyed as `self_reported`** | ✅ Same weight behaviour as (b), says what is true, no invented constant, and the greyed-axis UI already exists from A267 |

**The distortion D260 found, reversed and measured on the author:** technique's domain weight falls
from **.275 → .202 in Base (−7.3 pp)**, and −7.1 to −8.6 pp in every other phase. The 7.3 pp returns
distributed across finger (.156→.172), pulling (.110→.121), power-endurance (.138→.152) and volume
(.229→.253).

**Power Endurance gets better, then honest.** Undiluted, the author's PE goes **53 → 70** — exactly
what D260 predicted ("a genuinely decent PE reads as mid"). But **only 3 of 18 users have a repeater on
file**; for the other 15, PE after the demotion measures nothing and must be flagged `estimated`
rather than sitting silently at ~53. The repeater is already scheduled in every user's first cycle,
so the greyed state resolves itself.

**Endurance moves with PE** (`0.8 ×`), so `79fadc50` crosses the `< 50` weight cliff on both axes as a
knock-on. **Recommended order: D272 first, then D271** — D272 is a pure scoring change with no new
test, no new equipment and no new UI surface.

**Implementation trap recorded:** `_find_weakest_axis` does `profile.get(axis, 50)`, so deleting
`technique` from the profile turns it into a phantom 50 — which, verified on real profiles, wins the
weakest-axis title for two users. It must be removed from the tuple at `macrocycle_v1.py:297`
explicitly.

**Decisions needed:** option a/b/c; whether a greyed axis on the radar is acceptable (with D271, a
user with no tests could see three of five greyed); PE-without-repeater handling; the onboarding and
`/assessment` copy that currently tells users the gap "reveals technique and power endurance" and will
be false.

---

## 4. Open questions, honestly listed

1. **Decision-ID namespace collision.** D261–D267 are *research decisions* continuing a series that
   only ran to D91, but they collide with audit-brief IDs on the same `D` prefix — `D261` is already
   a brief on file (`docs/audit/D261_adhoc_selection_ranking.md`). Either renumber the decisions
   D92–D98 or move the briefs off `D`. Nothing was renamed unilaterally.
2. **`docs/analysis_D271_*.md` sits at `docs/` root, not `docs/audit/`.** CLAUDE.md says audit
   deliverables live in `docs/audit/<brief-id>_<topic>.md`. The megabrief named the path explicitly and
   `docs/audit_D260_*.md` sets the precedent at root, so the instruction was followed. Move them if
   you prefer the convention.
3. **Female anchors (D262).** The elite anchors are unisex/male-derived. Berta reports 34% variance
   for women vs 28% for men, and D263's contamination is worse for women (80% vs 65%). Whether a
   sex-specific anchor set is warranted once enough data exists is unresolved.
4. **`_PE_REPEATER_BENCHMARK` (18→44 sets) is still unsourced.** D260 §7 flagged it; nothing in this
   research pass grounds it. It is the benchmark the *undiluted* PE score of D272 divides by, so it
   matters more after that change than before.
5. **A KB correction found in passing.** `decision_consolidation_D01_D91.md:223` and
   `KB_SUPER_SUMMARY.md:177` list D07 as "reserved for future use", but
   `01_performance_determinants.md:666` defines it ("Endurance axis: keep as-is in v1 … Deferred").
   Noted in both files; the summary was not edited.
6. **D260-P2 remains fully open.** Anchor saturation, the brittle `<35 / <50 / >75` cliffs and the
   "50 problem" are untouched. A267 adds a second reading scale and B304 made the framing explicit,
   but the *stored* score a lead athlete's plan runs on is still top-censored. D272 §4 shows how
   narrow the margins around the cliffs are — three real users sit 1–4 points above `< 50` on a
   derived number.
7. ~~**The elite toggle ships on `/plan` only.**~~ **Resolved by A268 (2026-08-06).** The toggle now
   also renders on the public `/assessment` page, gated on `hasAnyEliteScore` so a visitor who skips
   the optional numbers sees the page exactly as before. Same pure function, same anchors, still
   render-only — the public page converts *added* loads to totals via `eliteInputsFromAddedLoads`,
   mirroring `public_assessment.py`, and a test asserts both surfaces score the same athlete
   identically.

---

## 5. The five ⓘ copies (Package 2b, as shipped by B304)

Lead discipline; each section is under 300 characters and asserted so by test.

| Axis | What it measures | Low-score line (roadmap-framed, `{target}` interpolated) |
|---|---|---|
| **Finger Strength** | "How hard you can grip a hold with maximum effort. Measured by how much weight you can hang on a standard 20mm edge for 7 seconds — the single strongest predictor of climbing grade." | "A lower score means your fingers are the limiter right now — the axis where focused hangboard work buys the most progress toward {target}." |
| **Pulling Strength** | "How much force your arms and back can generate to pull through powerful moves and lock off on steep terrain. Measured by your best weighted pull-up." | "A lower score means pulling power holds you back on steep, powerful moves — general strength work is where you'll gain most toward {target}." |
| **Power Endurance** | "How long you can sustain hard moves before the pump shuts you down. Your ability to keep climbing through sustained crux sections without your forearms giving out." | "A lower score means linking sustained cruxes is your ceiling — power-endurance intervals are where training pays off most toward {target}." |
| **Technique & Tactics** | "How efficiently you climb and how well you read routes. A big gap between your onsight and redpoint grades suggests there's free performance hiding in better movement and route-reading skills." | "A lower score means there's free performance in better movement and route-reading — often the fastest axis to improve on the way to {target}." |
| **Endurance** | "Your ability to sustain moderate effort over a full route without accumulating pump. This is about capillary density and aerobic fitness — can you cruise the easy sections and arrive at the crux fresh?" | "A lower score means aerobic base is your gap — easy mileage and capillarity work is where steady progress toward {target} comes from." |

Shared line, both modes: *"Scored against what {target} typically demands — 100 means you're already
there."* Elite mode replaces it with *"Scored against elite benchmarks — 100 means elite level."* plus
*"Elite = benchmarks around 8b–9a level performance."*

⚠️ **The Technique copy becomes false if D272 ships.** It names the onsight–redpoint gap as the
measurement. Rewriting it is part of the D272 implementation brief, not of this one.

---

## 6. Proposed implementation order for the engine work

Each is a separate brief requiring its own STOP gate.

| # | Brief | Depends on | Why here |
|---|---|---|---|
| 1 | **Decisions**: option a/b/c for TT; `profile_source`; equipment | — | Everything below branches on these. Nothing is written first. |
| 2 | **`profile_source` + `profile_scoring_version`** (B-type, backend + a small frontend grey state) | decision 1 | The shared foundation both analyses need, and the honest fix to D260's "50 problem" on its own merits. Ships alone, low risk, no scoring change. |
| 3 | **D272 — gap demotion** (A/B-type, STOP gate `assessment_v1` → `macrocycle_v1`) | 2 | Pure scoring change: no new test, no new equipment, no new UI beyond the grey state from 2. Removes the largest known distortion. Ship and observe. |
| 4 | **Equipment: `pulley_system` + `band` in the gym list** (C-type, catalog) | decision 1 | Tiny, independent, and the prerequisite for anything endurance. Can run in parallel with 3. |
| 5 | **D271 Stage 1 — collect** (A-type: catalog session, guided flow, safety gates, storage) | 2, 4 | Ships the test without changing a single score. Zero risk to live plans. |
| 6 | **D271 Stage 2 — calibrate and score** (A-type, STOP gate) | 5 + ~30 valid results | Flip Endurance to measured, `profile_scoring_version` → `v3`. |
| 7 | **D260-P2 — re-anchoring, continuous curves, elite fixtures** (D + A) | 3, 6 | The remaining half of D260. Invalidates historical scores → needs its own product decision. Deliberately last: the other axes should be honest before the strength anchors move. |

---

## 7. Merge instructions

The branch is linear. Commits `9f28f0a`, `d07881f`, `1d5f5a9`, `15f9c19` are **docs only** and safe to
merge at any time. Commit `585508c` (A267) touches `frontend/` and therefore **must not reach `main`
until the Vercel preview of `brief/A267-assessment-megabrief` has been checked** — desktop and the
installed iPhone PWA — and approved, per the branch workflow rule in CLAUDE.md.

Suggested check on the preview: open `/plan`, confirm Goal mode is byte-for-byte the experience you
have today, flip to Elite, confirm Finger ≈ 61 and Pulling ≈ 78 with the other three greyed, and open
each of the five ⓘ tooltips at 390 px in both modes.

After merge: `git worktree remove ../climb-agent-megabrief` and delete the branch.

---

*End of megabrief report. Packages 5 and 6 are not implemented and must not be until Daniele decides §3.*
