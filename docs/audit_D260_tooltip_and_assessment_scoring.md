# Audit D260 — Info Tooltip Viewport Clipping + Assessment Axis Scoring

**Type:** D (audit, read-only) · **Date:** 2026-07-23 · **Author account under review:** `7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e`
**Status:** Findings only. No production code, catalog, DB, test, or plan changes made. Awaiting decision.

---

## 1. Executive summary

The axis scoring is **only partially trustworthy, and not in the way the observation assumed.**

- **Finger Strength and Pulling Strength are real force-ratio measurements, but the ceiling is anchored to the user's *target grade*, not an absolute scale — so any user whose measured strength meets or exceeds their target benchmark is clipped to exactly 100.** The author is genuinely *above* benchmark (finger 107, pulling 102 before clamping), so both pin at 100. This is **saturation by design** (it is even asserted by a test), not a computation bug — but it means both axes carry no signal at the top and cannot distinguish a strong user from an elite one.
- **Power Endurance, Endurance and Technique are largely proxy-derived from a single input — the redpoint − onsight grade gap — plus self-reported weaknesses.** Endurance has **no dedicated endurance test at all**: it is computed as `0.8 × power_endurance` + climbing-years + a hang-duration nudge. So the author's Endurance 52 and PE 54 are *mostly the RP-OS gap and a repeater test*, not an endurance measurement.
- **Technique 30 = RP-OS gap bucket (40) − self-declared "technique_errors" penalty (10).** It is a proxy plus self-report, not an independent technique measurement. A redpoint-focused 8a climber has a wide RP-OS gap *by choice*, so this axis reads their style as a deficit.
- **The 100/100 causes essentially zero distortion to the author's actual plan** — the domain-weight function saturates its response at score > 75, so 100 and 85 produce identical weights, and the phase-duration shift the low axis would trigger is silently no-op'd because Base is already at its cap. The real plan-shaping lever is **Technique 30**, which boosts the `technique` domain weight by ~+7.5 points in every phase. If T&T is a mismeasurement, *that* is what skews the plan — not the double 100.
- **Tooltip clipping (Scope A) is a single hand-rolled popover** in `radar-chart.tsx`: a fixed 288 px-wide box centered on a ~150 px grid cell with `translateX(-50%)` and no viewport clamping. Left-column axes overflow the left screen edge on phones ≤ ~400 px. One component, one page — a contained fix.

**Bottom line:** trust Finger/Pulling *directionally* but treat 100 as "≥ target benchmark," not a true maximum. Treat Endurance and (largely) Technique as **proxy-derived, not measured.** The plan is mildly over-weighted toward technique for the author, driven by a proxy, not by the saturated axes.

---

## 2. Scope A — Info tooltip / popover rendering

### 2.1 Root cause (precise)

**File:** `frontend/src/components/onboarding/radar-chart.tsx`, component `AxisTooltip` (lines 22–58) rendered inside the legend grid (lines 149–173).

The popover is:

```tsx
className="absolute z-50 w-72 rounded-lg border border-border bg-background p-3 shadow-lg text-sm"
style={{ left: "50%", transform: "translateX(-50%)", top: "100%" }}
```

- `w-72` = **288 px fixed width**, centered on its parent cell via `left:50% / translateX(-50%)`, dropped below the cell via `top:100%`.
- The parent cell is one column of a **2-column grid** (`grid grid-cols-2 gap-x-6`, line 149). On a 390–400 px phone inside the `max-w-2xl` + `p-4` container, each legend column is roughly **140–165 px wide**.
- Centering a 288 px box on a ~150 px cell pushes it **~70 px past each side of the cell**. For the **left column**, the cell center sits ~110–120 px from the viewport's left edge, so the box's left edge lands at roughly **−20 to −40 px → off-screen, text cut mid-word.** Exactly the reported symptom.

**It is not a `position:fixed`-vs-transform ancestor trap and not an `overflow:hidden` clip.** The `Card` (`ui/card.tsx`) is `rounded-xl border py-6 shadow-sm` — **no `overflow-hidden`, no `transform`, no `filter`, no `contain`** on any ancestor. The popover is free to paint outside the card; it simply overflows the **viewport** because its width is fixed and its anchor is a narrow cell with no collision handling.

Root cause in one line: **a fixed-width, cell-centered, hand-rolled popover with zero collision detection / flip / shift / viewport clamping.** No positioning library is used (no Radix, no Floating UI) — it is bespoke absolute positioning.

### 2.2 Which axes clip

Legend is row-major over `AXIS_KEYS = [finger_strength, pulling_strength, power_endurance, technique, endurance]`:

| Column | Axes | Clip behaviour on ~390 px |
|---|---|---|
| Left | finger_strength, power_endurance, endurance | **Overflow left viewport edge** (worst; matches report) |
| Right | pulling_strength, technique | Right edge lands ~near the viewport edge; marginal/partial clip |

### 2.3 Positioning mechanism audit

| Property | Finding |
|---|---|
| Strategy | `position:absolute` relative to the legend cell; in-tree (no portal). |
| Library / version | None. Fully hand-rolled. |
| Collision / flip / shift / clamp | **None.** No boundary awareness whatsoever. |
| Ancestor `overflow/transform/filter/contain` | **None** (checked `Card`, `CardContent flex justify-center`, `(main)/layout.tsx`, `<main class="mx-auto max-w-2xl … p-4">`). |
| `env(safe-area-inset-*)` | Not respected by the popover (irrelevant here — popover sits high on the page, far from the notch/home-bar). |
| Width on narrow viewports | Fixed `w-72` (288 px), never reduced. This is the defect. |
| z-index | `z-50`. **Same as the bottom nav** (`bottom-nav.tsx`: `fixed bottom-0 … z-50`). No vertical overlap in practice (radar is near top of page), so no real z-fight — noted as theoretical only. |

### 2.4 Vertical / desktop / browser characterisation

- **Horizontal is the failure.** Vertical `top:100%` drop is small and the card is near the top of `/plan`, so the popover never reaches the fixed bottom nav — **no below-fold / behind-tab-bar clipping observed by analysis.**
- **Narrowest failing viewport:** clipping is present at the reported ~393 px (iPhone Pro) for the left column and worsens below it. It disappears once the centered ~150 px cell's center sits ≥ ~144 px from both edges, i.e. roughly **≥ ~500 px viewport** the 288 px box can no longer reach a screen edge.
- **Desktop / tablet:** determined **analytically, not live-rendered.** With `max-w-2xl` (672 px) centered and wide side-margins, the 288 px popover overflows the *cell/column* but stays **fully on-screen and readable** — at most it visually overlaps the adjacent legend column. So desktop is **not clipped**, only slightly misaligned. ⚠️ This is a geometric determination from the container/grid/popover math; I did **not** run a live desktop or mobile browser in this environment (no Safari/Chrome render was executed). A 30-second live check on `/plan` at 390 px and at 1280 px is recommended to confirm before the fix brief.

### 2.5 Content length (A.4)

Axis `description` strings, character counts: **141, 148, 163, 168, 180, 188, 189, 192, 201.** Plus a `low:` sentence appended below. At 288 px the longest (201 chars + `low`) renders ~9–11 lines — **tall but readable**; not the primary problem. A correctly-positioned 288 px popover is acceptable on a 390 px screen. → The fix is **primarily positional**, not a forced rewrite to a bottom sheet, though a bottom-sheet would also neutralise the length.

### 2.6 Two fix options (do not implement)

**Option 1 — minimal positional fix (recommended).** In `radar-chart.tsx` only: stop centering on the cell. Either (a) render the popover as a **full-width block spanning both columns** (move it out of the cell into a relative wrapper around the whole legend, `left-0 right-0`, `max-w-[calc(100vw-2rem)] mx-auto`), or (b) keep it per-cell but clamp with `max-w-[calc(100vw-2rem)]` and align to the card edge instead of the cell center.
- Files touched: **1** (`radar-chart.tsx`).
- Blast radius: **`/plan` only** — `RadarChart` is imported by exactly one page (verified: no other usage; it is *not* used in onboarding despite its folder). Regression risk: **low.**

**Option 2 — shared popover consolidation.** Add a real popover primitive (shadcn/Radix `Popover` or Floating UI) with collision detection; adopt it in `radar-chart.tsx` and audit the other ad-hoc `title=`/info affordances across the app for the same class of bug.
- Files touched: new `ui/popover` + refactor + a sweep of ad-hoc tooltips.
- Blast radius: **larger** (new dependency/primitive, multiple components). Regression risk: **medium.** Benefit: kills the bug class, not just this instance. Note: this is currently the **only** hand-rolled `translateX(-50%)`/`openTooltip` popover in `src` (verified) — so the consolidation benefit is mostly future-proofing, not fixing many existing instances.

---

## 3. Scope B — Assessment axis scoring

All scoring lives in `backend/engine/assessment_v1.py`. Every axis below is reconstructed from code and **verified against the author's stored inputs** (pulled read-only from Supabase `users.state`). All five reproduced to the exact integer.

**Author's stored assessment inputs** (`7ea9f0ee`, lead, target 8a+, current 8a, bw 76 kg):
`grades`: lead_rp 8a, lead_os 7a+, boulder_rp 7C, boulder_os 7A ·
`tests`: max_hang_20mm_7s 122 kg, weighted_pullup_1rm 127.8 kg, repeater_7_3 25 sets, max_hang_duration 60 s ·
`self_eval`: primary=technique_errors, secondary=pump_too_early · `experience`: climbing_years 16.

### 3.1 Finger Strength — **VERDICT: saturated**

| | |
|---|---|
| Inputs | `assessment.tests.max_hang_20mm_7s_total_kg` (fallback `…_5s…`); `body.weight_kg` (default 70). |
| Raw units | Total load hung on a 20 mm edge (kg, includes bodyweight). |
| Formula | `ratio = max_hang / bw; score = (ratio / benchmark) * 100` (lines 176–178). |
| Anchors | `_FINGER_BENCHMARK[target_grade]`, **target-relative.** 8a+ → **1.50 × BW**. Absolute-vs-BW: BW-relative. **Not sex/age-adjusted.** |
| Clipping | `_clamp(score, 0, 100)` (line 76). Caps at 100. |
| Fallback | If no hang test: grade estimate `(current_idx/target_idx)*70` + weakness penalty → **can never reach 100** (so a 100 always means a real test met/exceeded benchmark). |
| Recency | **None.** `last_test_date` is stored but never consulted; a January test counts at full weight in week 10 of 12. |

**Author:** 122/76 = 1.6053; /1.50 = **107.0 → clamped 100.** True score is 7 % above ceiling.
**Saturation band:** score = 100 for any total hang **≥ 114.0 kg** (1.50 × 76). Author is 122. **An unbounded band of ability ≥ 114 kg all reports 100.** For lower target grades the ceiling is far lower — a 7b target uses benchmark 1.15, so ~78 kg total hang already = 100 (see cross-user user `f49678eb`). **The ceiling is calibrated to the user's target, so it is trivially reachable for modest targets and slightly-exceeded for the author — it is not an elite-population scale.**

### 3.2 Pulling Strength — **VERDICT: saturated**

Same structure. Anchor `_PULLING_BENCHMARK[8a+] = 1.65 × BW`. Uses `weighted_pullup_1rm_total_kg` (with a Brzycki estimate from submaximal reps as fallback, D38).
**Author:** 127.8/76 = 1.6816; /1.65 = **101.9 → clamped 100.** Saturation band: total ≥ **125.4 kg** = 100. Author 127.8 → only 2.4 kg above the ceiling, still censored.
Note (P3): design doc §2.2 specifies pulling via **2RM** and benchmark **≥1.5× BW for 7c+**; code uses **1RM** with `_PULLING_BENCHMARK[7c+] = 1.45`. Unit + anchor mismatch vs the doc.

### 3.3 Power Endurance — **VERDICT: proxy-derived (part-measured)**

| | |
|---|---|
| Inputs | `grades.lead_max_rp/os` (gap); `tests.repeater_7_3_max_sets_20mm` (optional); self_eval. |
| Formula | With repeater: `repeater*0.4 + gap*0.4 + (gap+eval)*0.2`. Without: `gap*0.6 + (gap+eval)*0.4` (lines 275–280). |
| Gap buckets | gap ≤2 →75, ≤4 →55, ≤6 →40, else 30 (coarse 4-value step). Missing grades → **hard default 50.** |
| Repeater anchor | `_PE_REPEATER_BENCHMARK[8a+]=32` sets; `repeater/32*100`, capped 100. |

**Author:** gap = idx(8a) − idx(7a+) = 18 − 13 = **5 → gap_score 40**. repeater 25/32×100 = 78.1. eval −4 (pump_too_early secondary). `78.1·0.4 + 40·0.4 + 36·0.2 = 54.45 → 54.` ✅
**Interpretation:** the objective repeater says **78/100**, but it is diluted 40/40 with the subjective RP-OS gap (40) and dragged to 54. **A genuinely decent PE reads as mid because 60 % of the score is the grade-gap proxy + self-report.**

### 3.4 Endurance — **VERDICT: proxy-derived (derivative of a proxy; no dedicated test)**

| | |
|---|---|
| Inputs | `pe_score` (the PE axis above), `experience.climbing_years`, self_eval, `tests.max_hang_duration_20mm_seconds`. |
| Formula | `score = pe_score*0.8 + min(years*2,10) + weakness_penalty + hang_duration_modifier` (lines 316–338). |
| Dedicated test | **NONE.** No Critical Force, no continuous-route timer, no repeater feeds this axis directly (verified: `repeater_7_3_max_sets_20mm` is consumed only by PE). |

**Author:** 54·0.8 = 43.2; +10 (16 yrs, capped); −5 (pump secondary); +4 (60 s hang) = **52.2 → 52.** ✅
**Design-vs-code mismatch (finding):** design doc §2.2 defines this axis as *finger endurance* measured by **Repeaters 7:3 / Critical Force, CF/BW ≥ 0.55.** The code implements it as **80 % of Power Endurance + tenure + a hang-duration nudge.** The axis labelled "Endurance" measures nothing endurance-specific; it is a re-scaled echo of PE. **Answer to the brief's question: the author's Endurance ~52 is the *absence* of an endurance measurement — it is PE·0.8 plus experience.**

### 3.5 Technique & Tactics — **VERDICT: proxy-derived (gap + self-report)**

| | |
|---|---|
| Inputs | `grades.lead_max_rp/os` (gap) + self_eval only. **No test.** |
| Formula | gap ≤2 →80, ≤4 →60, ≤6 →40, else 30; then `+ weakness_penalty` (lines 292–305). Missing grades → **default 50.** |

**Author:** gap 5 → 40; primary weakness `technique_errors` → −10 → **30.** ✅
**Interpretation:** 30 = RP-OS gap bucket (40) minus the user's own self-declared technique weakness (−10). It is **not an independent technique measurement.** A redpoint-focused climber intentionally runs a wide RP-OS gap; this axis reads that style choice as a deficit and the user's honest self-report deepens it. Only **7 distinct values are possible** across the whole population (see §4) — the axis is heavily quantized.

### 3.6 The "50" problem (fallbacks, B.1.6)

`50` is dangerously overloaded. It is emitted as a silent default by: missing grades in PE/Technique; the `else` branch of Finger/Pulling when target_idx = 0; and `profile.get(axis, 50)` in the macrocycle's `_find_weakest_axis` and `_adjust_domain_weights`. **A real "average" score and "no data" are indistinguishable downstream.** No field records whether an axis was measured or defaulted.

---

## 4. Cross-user table (B.4) — decisive evidence

Read-only pull of `users.state` from Supabase (18 rows; 16 have a computed `assessment.profile`). Axes: FS = finger, PS = pulling, PE = power-endurance, EN = endurance, TT = technique.

| uid | disc | target | current | bw | FS | PS | PE | EN | TT |
|---|---|---|---|---|---|---|---|---|---|
| **7ea9f0ee (author)** | lead | 8a+ | 8a | 76 | **100** | **100** | 54 | 52 | 30 |
| 22080848 | lead | 8a | 7c | 68 | 97 | 87 | 67 | 54 | 60 |
| 3fc2a699 | lead | 7b | 7a | 73 | 57 | 53 | 55 | 49 | 50 |
| 42c3087c | lead | 8c+ | 8a | 77 | 38 | 44 | 40 | 42 | 40 |
| 52681ef7 | both | 7b+ | 7a+ | 78 | 50 | 44 | 75 | 70 | 80 |
| 5a98187c | lead | 8a+ | 7b | 66 | 91 | 91 | 53 | 43 | 60 |
| 611e0369 | lead | 7a | 6c+ | 47 | 62 | 53 | 55 | 52 | 60 |
| 6cf99c0d | lead | 7b | 7a | 56 | 57 | 88 | 53 | 51 | 60 |
| 7208f92f | boulder | 8b+ | 7C+ | 72 | 98 | 90 | 48 | 46 | 45 |
| 79fadc50 | lead | 8a | 7b | 68 | 51 | 74 | 54 | 52 | 60 |
| 98f77487 | lead | 5c+ | 5b | 55 | 28 | 26 | 75 | 70 | 70 |
| 9e4154d4 | both | 7a+ | 6c+ | 82 | 84 | 52 | 52 | 34 | 60 |
| bcab057d | both | 7c | 7b | 73 | 59 | 55 | 53 | 43 | 50 |
| ce8914f0 | both | 7b | 6c | 68 | 30 | 41 | 53 | 45 | 60 |
| d7f6083e | both | 8a | 7c+ | 65 | 50 | 89 | 40 | 42 | 40 |
| f49678eb | lead | 7b | 6c+ | 68 | **100** | **100** | 53 | 47 | 50 |

**Distribution / discrimination:**

| Axis | min | max | mean | # distinct | Reading |
|---|---|---|---|---|---|
| FS | 28 | 100 | 65.8 | 13 | Wide spread; **saturates only for the 2 users at/above target benchmark** (author; and `f49678eb`, a *7b*-target user who hits 100 at ~78 kg). Top-censored, not globally dead. |
| PS | 26 | 100 | 67.9 | 13 | Same 2 users at 100. |
| PE | 40 | 75 | 55.0 | 8 | **Compressed to the middle** — everyone clusters 40–75. |
| EN | 34 | 70 | 49.5 | 11 | Clusters low-middle; being PE·0.8 it inherits PE's compression. |
| TT | 30 | 80 | 54.7 | **7** | **Heavily quantized** (gap buckets ± fixed penalties). Poor discrimination. |

- **FS = 100:** 2 of 16. **PS = 100:** 2 of 16. **Both 100:** 2 (author + `f49678eb`).
- So the double-100 is **not yet epidemic** (12.5 % of users), but it is **structural, not a personal quirk**: because the ceiling is the *target* benchmark, every user who reaches their target's strength pins to 100 — and lower-target users reach it trivially (`f49678eb` at 7b). As the base trains toward modest targets, more will pin. The mechanism is systemic even if the current count is 2.
- **The bottom three axes (PE/EN/TT) barely discriminate**: PE spans 35 points with 8 values, EN clusters near 45–52, TT has only 7 possible values. This is the more important calibration problem than the two 100s.

---

## 5. Macrocycle impact (B.5) — quantified, on paper (no regeneration run)

Two levers translate axis scores into the plan (`macrocycle_v1.py`, read-only):

**(a) Phase durations** — `_find_weakest_axis` picks the single lowest axis **only if < 50**, then `_WEAKNESS_ADJUSTMENTS` shifts ±1 week, **clamped to floors/caps.**
- Author weakest = **TT 30** (< 50) → wants Base +1 / Performance −1. **But Base is already at its cap (4 = floor = cap for lead), so the shift silently no-ops** (`durations[ext]+1 ≤ caps[ext]` fails). → **Author's durations remain the lead default 4/3/2/2/1 — unchanged by any score.**
- Note the brittleness: PE 54 and EN 52 sit **2–4 points above the < 50 cliff**, so they trigger nothing; a ±3-point wobble in a *proxy* would flip a real duration decision.

**(b) Domain weights** — `_adjust_domain_weights` per phase: score < 35 → +0.10; < 50 → +0.05; > 75 → −0.03; renormalize.
- Author: **TT 30 → technique +0.10** (every phase); **FS 100 & PS 100 → −0.03 each** (every phase); PE 54 / EN 52 → nothing.
- Worked example, Base phase (lead base weights finger .20 / pulling .15 / PE .15 / volume .25 / technique .20 / core .10):

| Domain | Base | Author (renorm ÷1.09) | If FS/PS were 85 | If FS/PS were 75 |
|---|---|---|---|---|
| technique | .20 | **.275** | .275 | .261 |
| volume_climbing | .25 | .229 | .229 | .217 |
| finger_strength | .20 | .156 | .156 | .174 |
| power_endurance | .15 | .138 | .138 | .130 |
| pulling_strength | .15 | .110 | .110 | .130 |
| core_prehab | .10 | .092 | .092 | .087 |

**Key result:** dropping Finger & Pulling from **100 → 85 changes the weights by exactly 0** (both are > 75 either way; the weight response *saturates at 75*). Only going below 75 moves anything, and even then finger shifts ~+1.8 pp. **So the double-100 the observation flagged does not distort the author's plan.** The actual distortion is the **+7.5 pp technique boost** (20 % → 27.5 %) applied in *every* phase, driven entirely by **TT 30 — a RP-OS-gap proxy plus the user's self-reported "technique_errors."** If T&T is a mismeasurement for a redpoint-focused climber, the plan over-invests in technique and under-invests in finger/pulling volume across the whole cycle. No plan regeneration was triggered; past/completed sessions untouched.

---

## 6. Severity-ranked issues

| # | Sev | Issue | Paying-user impact |
|---|---|---|---|
| 1 | **P1** | **Endurance axis has no endurance test** — it is `0.8 × power_endurance` + tenure + hang nudge; design doc specifies Repeaters/Critical Force. | Users see an "Endurance" score that measures power-endurance, not endurance; it also drives `volume_climbing` weight. Mislabels + mis-weights for every user. |
| 2 | **P1** | **Technique conflates RP-OS gap + self-report with technique.** Only 7 possible values; drives the largest single weight adjustment (+0.10). | A redpoint-focused climber is told technique is their weakness and gets base/technique volume they may not need. This is the dominant plan-shaping lever, and it rests on a proxy. |
| 3 | **P2** | **Finger/Pulling saturate to 100 at the *target* benchmark**, not an absolute scale; unbounded ability band → 100; lower-target users saturate trivially. | Two axes carry no top-end signal; radar shows "100/100" that reads as a bug to users; blocks any future finer strength weighting. Current plan impact low (weight response saturates > 75). |
| 4 | **P2** | **PE dilutes an objective repeater 40/40 with the subjective grade gap.** | A genuinely strong PE (repeater 78) reads as 54. Under-credits real fitness. |
| 5 | **P2** | **Brittle thresholds:** `< 50` duration cliff on the single weakest axis, `< 35 / < 50 / > 75` weight cliffs, and Base-at-cap silently no-ops the weakness shift. | ±2–3 points of proxy noise flips plan decisions; the intended weakness→duration adaptation silently does nothing when the target phase is capped. |
| 6 | **P2** | **Tooltip clipping on `/plan`** (Scope A) — fixed-width cell-centered popover, no clamping; left column off-screen ≤ ~400 px. | The page that *explains* the (mis-calibrated) scores is itself unreadable on the author's phone. Contained fix. |
| 7 | **P3** | `50` is an undetectable silent default for "no data" across scoring + macrocycle. | Missing measurements masquerade as average and feed the plan as if real. |
| 8 | **P3** | Doc/code mismatches: pulling 1RM (code) vs 2RM (doc) and 1.45 vs 1.5 anchor; anchors ≥ 8a are code-only extrapolations with **no in-repo source** (see §7). | Calibration is undocumented above 7c+; hard to validate or defend. |

---

## 7. Literature grounding (B.7)

Per axis, whether the anchor constants cite any in-repo source (`docs/`, code comments, design doc):

| Axis | Anchors | Source in repo? |
|---|---|---|
| Finger | `_FINGER_BENCHMARK` 7a→9a+ (1.00→2.10) | 7c+ value (1.30) matches design doc §2.2. **8a–9a+ values are undocumented, code-only extrapolations.** Comment cites `D85` (internal brief), not literature. |
| Pulling | `_PULLING_BENCHMARK` (1.20→2.25) | **Mismatch** with doc (doc 1.5 @7c+, code 1.45; doc 2RM, code 1RM). ≥8a undocumented. Comment `D84`. |
| PE (repeater) | `_PE_REPEATER_BENCHMARK` (18→44 sets) | **No source anywhere.** Not in design doc, no citation. Pure code constants. |
| Endurance | n/a (derived 0.8×PE) | Design doc §2.2 specifies a *different* method (Repeaters/CF, CF/BW≥0.55) that is **not implemented**. |
| Technique | gap buckets 80/60/40/30 + penalties | Bucket thresholds have **no in-repo source**; design doc only states "gap ≤ 2 grades" qualitatively. |

Per the brief: I did **not** search external references or invent citations. Every "no source" above means the constant is unsourced in the repository and should be routed to the knowledge-base project for grounding, not guessed here.

**Test coverage (B.6):** `test_assessment_v1.py` (299 lines) + `test_assessment_boulder_weaknesses.py` (143). Tests assert **derived scores**, never the anchor constant values — changing an anchor breaks score tests but no test pins "8a+ finger benchmark = 1.50." The clamp is *deliberately validated*: `test_score_clamped_0_100` feeds max_hang 200 / pullup 200 (elite-ish) but asserts only `0 ≤ v ≤ 100`, and `test_finger_score_benchmark_7c` comments "104 → clamped to 100." **There is no fixture of an elite user with a matching high target where the score is expected to still discriminate at the top** — so saturation shipped precisely because the only strong fixtures assert the ceiling rather than resolution. That is how the ceiling went unnoticed.

---

## 8. Recommended fix sequence (proposals only — not written)

1. **B — Tooltip positional fix** (Scope A, Option 1): full-width clamped popover in `radar-chart.tsx`. Small, isolated, unblocks reading the radar. Do first — cheap and user-visible.
2. **D — Assessment re-anchoring design brief** (STOP-gate analysis): decide (a) absolute vs target-relative anchors for Finger/Pulling to restore top-end signal; (b) wire a real endurance measurement to the Endurance axis (or rename it to reflect it derives from PE); (c) reduce the grade-gap proxy's weight in PE now that a repeater exists; (d) replace hard cliffs with continuous curves; (e) source the anchors via the KB project. **Analysis + Daniele decision before any code.**
3. **B — Fallback/default disambiguation**: record per-axis `measured|default` provenance so "50 = no data" stops masquerading as a measurement (prereq for trusting the radar and for the coach).
4. **B — Test fixtures for elite users** with high matching targets that assert *discrimination*, not just the clamp — so a re-anchoring can't silently regress.

---

## 9. Open questions for Daniele (product decisions, not technical)

1. **Re-anchoring invalidates history.** Moving Finger/Pulling to an absolute scale (or raising ceilings) will change every existing user's stored scores and radar shape, and their `assessment_snapshot` inside live macrocycles. Do we re-score in place, version the scoring, or only apply on the next assessment? This is a data-integrity/UX call, not a code call.
2. **Is the RP-OS gap a legitimate Technique signal at all?** For redpoint-focused sport climbers a wide gap is a style, not a weakness. Do we keep gap→technique, gate it on discipline/goal, or demote it to a hint?
3. **Should "Endurance" keep its name** while it is computed from Power Endurance, or do we either add a real endurance test or relabel the axis? Affects the radar, the coach, and the design doc.
4. **Target-relative vs absolute ceiling by intent:** the current design *is* "% of the strength your goal needs," which is arguably a valid coaching frame (100 = "strong enough for your goal"). If we keep it, the fix is presentational (show "≥ target" instead of a bare 100) rather than a re-anchoring. Which frame do we want?

---

*End of audit D260. No fixes applied. Awaiting approval before any follow-up brief.*
