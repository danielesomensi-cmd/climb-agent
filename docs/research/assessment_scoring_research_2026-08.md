# Assessment Scoring Research — Decision Log (2026-08)

**Brief:** C267 · **Date:** 2026-08-06 · **Type:** C (research / decision record, docs only)
**Predecessor:** `docs/audit_D260_tooltip_and_assessment_scoring.md` (audit, 2026-07-23)
**Status:** Decisions recorded. D261 and D266 have implementation analyses pending approval
(`docs/analysis_D272_endurance_test.md`, `docs/analysis_D273_gap_demotion.md`).

---

## 0. Why this file exists

Audit D260 found that three of the five assessment axes are proxy-derived rather than
measured, and that the largest single plan-shaping lever in the engine — the Technique &
Tactics score — rests on the redpoint − onsight grade gap, a tactics/style composite.
This file records the research decisions taken in response, so that the constants and the
protocol shipped later have a written, sourced origin instead of the code-only
extrapolations D260 §7 documented.

**Numbering namespace.** D261–D267 below are **research decision records**, continuing the
D01–D91 series consolidated in `docs/research_kb/decision_consolidation_D01_D91.md`. They
are *not* audit-brief IDs. The repository unfortunately reuses the `D` prefix for audit
briefs (`docs/audit/D261_adhoc_selection_ranking.md` is a brief, not this decision), so
these seven numbers collide with existing brief IDs. The IDs were assigned by the
originating brief and are recorded here verbatim; see §4 for the open question about
renaming the series.

---

## 1. Decision records

### D261 (rev B) — Dedicated endurance test

Endurance axis gets a dedicated v1 test `test_endurance_intermittent`: 8s work : 2s rest at
60% of the user's collected max-hang total load, to failure; scored outcome =
body-mass-normalized impulse (kg·s·kg⁻¹). Supersedes D07 and the earlier 7:3 @ 50% proposal.
Source: Berta et al. 2025, J Sports Sci 43(3):245–255, DOI 10.1080/02640414.2024.2449316
(intermittent impulse carries 28% M / 34% F of climbing-ability variance, second only to
strength).

### D262 — Elite radar anchors are display-only

"vs elite" radar anchors are display-only: Finger 200% BW, Pulling 187% BW (survey data,
medium confidence; peer-reviewed finger anchor exists only for a one-hand MVC protocol —
v1.1 option); Endurance elite = 58.5 kg·s·kg⁻¹ (derived from peer-reviewed data, male median
8b–9a+), dormant until the intermittent test ships; PE and Technique permanently greyed
(no defensible quantitative anchor).

### D263 — Bodyweight finger hang is not an endurance measure

Bodyweight finger hang EXCLUDED as an endurance measure (65% M / 80% F of its variance is
finger strength). May remain a composite ability predictor; never the Endurance axis.

### D264 — Continuous endurance test excluded

Continuous endurance test EXCLUDED (2–4% variance, non-significant).

### D265 — Critical Force test downgraded

Sensor-based Critical Force test (formerly D89) DOWNGRADED: all-out CF validity contested in
climbing-specific setups (Baláš et al. 2024). Not a clean "v3 precision upgrade."

### D266 — Redpoint–onsight gap demoted to a tactical hint

Redpoint–onsight gap demoted from weight driver to tactical hint: it is a
tactics/style/mental composite, not a physiological measure. Implementation analysis in
Package 6.

### D267 — Berta bands are curve shape, not transferable absolutes

Berta normative bands are NOT directly transferable to climb-agent's protocol (one hand /
23mm / dynamometer vs two arms / 20mm / added load). v1 scoring uses the bands as curve
shape; every endurance result stores raw impulse + `scoring_version` for future
recalibration on own data.

---

## 2. Normative band table (Berta supplementary data)

Source: Berta et al. 2025, supplementary data. Male/unisex. Metric: **intermittent impulse,
kg·s·kg⁻¹** (body-mass-normalized). Format: p10 / p50 / p90.

| Grade band | p10 | p50 | p90 |
|---|---|---|---|
| 5+–6b+ | 20.0 | 29.5 | 46.5 |
| 6c–7b | 23.2 | 37.3 | 52.0 |
| 7b+–8a+ | 33.1 | 48.9 | 65.7 |
| 8b–9a+ | 47.9 | 58.5 | 79.4 |

**Usage constraint (D267).** These percentiles were collected on a *different protocol*
(one hand, 23 mm, dynamometer) from the one `test_endurance_intermittent` specifies (two
arms, 20 mm edge, added load). They are therefore used as **curve shape** — the relative
spacing of p10/p50/p90 within a band and the progression of medians across bands — not as
absolute pass marks. Every stored endurance result carries the raw impulse and a
`scoring_version` so the mapping can be recalibrated against climb-agent's own data once
enough results accumulate.

The p50 of the 8b–9a+ band, **58.5 kg·s·kg⁻¹**, is the value D262 designates as the elite
anchor for the Endurance axis. It stays dormant until the test ships.

---

## 3. What each decision changes

| Decision | Affects | Ships when |
|---|---|---|
| D261 rev B | New assessment test, Endurance axis becomes measured | After approval of `analysis_D272_endurance_test.md` |
| D262 | Radar "Elite" comparison mode (display only) | A267 — shipped with 2 live axes, 3 greyed |
| D263 | `max_hang_duration_20mm_seconds` keeps its composite role, loses any endurance claim | With D261 |
| D264 | Closes the continuous-endurance option; no work to do | Immediately (no-op) |
| D265 | Removes Critical Force from the v3 roadmap as a "precision upgrade" | Immediately (roadmap) |
| D266 | Technique & Tactics scoring, domain weights, coach payload | After approval of `analysis_D273_gap_demotion.md` |
| D267 | Endurance scoring curve + `scoring_version` field | With D261 |

---

## 4. Notes on cross-references and open questions

1. **D07 is correctly superseded.** `docs/research_kb/01_performance_determinants.md:666`
   defines D07 as *"Endurance axis: keep as-is in v1 — splitting adds complexity without
   clear v1 benefit. CF test enables clean split in v3. Deferred."* D261 rev B replaces that
   deferral with a shipped test. Note that
   `docs/research_kb/decision_consolidation_D01_D91.md:223` and `KB_SUPER_SUMMARY.md:177`
   both list D07 among "reserved for future use" — that classification is wrong and should
   be corrected when the consolidation file is next revised.
2. **D265 and D89 are consistent.** D89 ("Critical Force test, simplified 2-point") is
   already `⏸️ Deferred v2` in the consolidation appendix. D265 downgrades the *rationale*,
   not the status: CF is no longer held out as the eventual precision upgrade, so the
   deferral becomes indefinite rather than scheduled.
3. **Open question — decision-ID namespace.** D261–D267 collide with audit-brief IDs in the
   same `D` prefix (`D261` is already an audit brief on file). The decision series itself
   only runs to D91. Either the decision series should resume at D92 and these seven be
   renumbered D92–D98, or the brief namespace should move off `D`. This needs Daniele's
   call; nothing here is renamed unilaterally.
4. **Open question — female anchors.** D262 fixes unisex (male-derived) anchors. Berta
   reports 34% variance for women vs 28% for men on the same metric, and D263's
   contamination figure is worse for women (80% vs 65%). Whether the radar should carry a
   sex-specific anchor set once enough female data exists is unresolved.
5. **Not sourced here.** The `_PE_REPEATER_BENCHMARK` constants (18→44 sets) that D260 §7
   flagged as having no in-repo source remain unsourced. Nothing in this research pass
   grounds them.
