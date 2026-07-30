# climb-agent Knowledge Base — Index

> **Last updated:** 2026-04-05
> **Total files:** 37 (35 original + sync doc + updated consolidation)
> **Total decisions:** 91 (D01-D83 core + D84-D91 test protocol + D84b)
> **Active decisions:** 80 (63 v1 + 18 v2 + 6 v3 — minus ~35 implemented, ~28 in v2 backlog)
> **Intentionally excluded:** 5 (D24, D25, D27, D40, D46)
> **Total references:** ~275

---

## ⚠️ IMPORTANT: Two Projects

This knowledge base lives in a **claude.ai project** called "climb-agent knowledge base".
The **implementation** lives in a separate Claude Code project.

**Rule:** Before implementing any deferred decision in Claude Code, always check this KB project first — especially `horst_integration_audit.md` for enrichment material.

---

## Core Knowledge Base Files (Research — Topics 01–10)

| # | File | Topic | Decisions | Refs |
|---|------|-------|-----------|------|
| 01 | `01_performance_determinants.md` | What determines climbing grade? 5 SRs, Magiera 77%, 5-axis assessment | D01-D09 | 52 |
| 02 | `02_finger_strength.md` | Hangboard science: López PhD, Nelson C4HP, grip types, protocols | D10-D14 | 25 |
| 03 | `03_pump_endurance_capillaries.md` | Pump physiology, energy systems, ARC, NIRS, critical force | D15-D18 | 21 |
| 04 | `04_periodization.md` | LP vs DUP meta-analyses, deload, taper, Hörst 4-3-2-1 | D19-D23 | 20 |
| 05 | `05_psychology_mental.md` | Fear of falling, route preview, flow, Mangan 2024 SR | D28-D32 | 22 |
| 06 | `06_nutrition_recovery_sleep.md` | RED-S, macros, sleep, supplements, collagen+vitC | D64-D67 | 19 |
| 07 | `07_overtraining_injury_load.md` | ACWR, overtraining spectrum, pulley injuries, Quarmby 2023 SR | D68-D72 | 18 |
| 08 | `08_technique_movement_route_reading.md` | Seifert jerk metric, drill catalog, technique assessment | D73-D76 | 14 |
| 09 | `09_climbing_philosophy_motivation.md` | SDT framework, Coach personality, "train better not more" | D77-D79 | 8 |
| 10 | `10_female_age_youth.md` | Menstrual cycle (inconclusive), growth plates, age adjustments | D80-D83 | 12 |
| — | `consuegra_book_synthesis.md` | Ch.7 (physiology) + Ch.8 (27 sections) + Ch.10 (periodization) | D24-D27, D33-D63 | ~50 |

---

## Hörst "Training for Climbing" Synthesis Files (Primary Source — 2026-03-27)

| File | Ch. | Topic Target | Key Content |
|------|-----|-------------|-------------|
| `horst_ch2_self_assessment_synthesis.md` | 2 | Topic 01 | Goal setting, self-assessment methodology, weak link ID |
| `horst_ch3_mental_training_synthesis.md` | 3 | Topic 05 | Progressive relaxation, visualization, centering, ANSWER sequence |
| `horst_ch4_technique_skill_synthesis.md` | 4 | Topic 08 | Technique principles, drill descriptions, motor learning |
| `horst_ch6_mobility_synthesis.md` | 6 | Topic 07 + Exercise Catalog | **38 exercises**: 8 SMR, 18 stretches, 7 wrist stabilizers, 2 rotator cuff, 4 scapular, 3 push |
| `horst_ch11_nutrition_synthesis.md` | 11 | Topic 06 | Macros (65:15:20), GI strategy, hydration, creatine (small-dose OK, loading counterproductive), caffeine periodization |
| `horst_ch12_recovery_synthesis.md` | 12 | Topic 06 | 3 recovery periods model, G-Tox, active rest +35%, post-exercise 4:1 protocol, central fatigue 7× |
| `horst_ch13_injury_synthesis.md` | 13 | Topic 07 | Injury treatment/prevention, tendon healing timelines |

**Integration audit:** `horst_integration_audit.md` — 0 conflicts, 14 confirmations, 6 new coaching cues proposed.

---

## Decision & Planning Files

| File | Purpose | Status |
|------|---------|--------|
| `decision_consolidation_D01_D91.md` | Master cross-reference: 91 decisions, conflicts, version grouping, D84-D91 appendix | ✅ Synced 2026-04-05 |
| `decision_roadmap_sync_2026_04_05.md` | **NEW** — Complete decision↔roadmap sync with literature review priorities | ✅ Current |
| `decision_consolidation_D01_D83.md` | Earlier version (D01-D83 only) — historical | Superseded by D01-D91 |
| `decision_consolidation_D01_D63.md` | Earlier version (D01-D63 only) — historical | Superseded by D01-D91 |
| `claude_code_mega_brief_v1.md` | Implementation guide: 57 v1 decisions in 10 sessions | ARCHIVED (~80% implemented) |
| `knowledge_base_roadmap.md` | Original research roadmap (10 topics) | ⚠️ Stale (says PLANNING, Topics 01-10 Step 1 all done) |
| `knowledge_base_roadmap_update_topic01.md` | Decision log D01-D32 + topic status after Topics 01-05 | Historical |
| `cross_check_report.md` | Cross-check for contradictions (2026-03-16) | ⚠️ Superseded by `horst_integration_audit.md` |
| `horst_integration_audit.md` | **CURRENT** — 7 Hörst files vs D01-D83: 0 conflicts, 14 confirmations, 6 cues, 38 exercises | ✅ Current |

---

## Design & Architecture Files

| File | Purpose |
|------|---------|
| `ROADMAP_CURRENT.md` | **Source of truth** for implementation status and backlog |
| `PROJECT_BRIEF.md` | Architecture overview, tech stack |
| `DESIGN_GOAL_MACROCICLO_v1_1.md` | Engine design: Assessment → Macrocycle → Session |
| `ENGINE_ARCHITECTURE.md` | Current engine architecture documentation |
| `CLAUDE.md` | Instructions for Claude Code implementation project |
| `coach_knowledge_base_spec.md` | Design spec for Coach KB (v1 rationale + v2 LLM Coach) |
| `brief_training_methodology_explained.md` | Outline for user-facing methodology document |
| `engine_audit_report_v3_FINAL.md` | Full codebase audit report |

---

## Reference Files

| File | Purpose |
|------|---------|
| `research_methodology_v2_COMPLETE.md` | How research was conducted (sources, criteria, process) |
| `literature_review_climbing_training.md` | Pre-existing literature review (foundation) |
| `docs_literature_hangboard.md` | Pre-existing hangboard exercise validation (17 exercises) |

---

## Decision Quick Reference

### By Version

| Version | IDs | Count | Scope |
|---------|-----|-------|-------|
| v1 (launch) | D01-D83 subset + D84-D91 subset | 63 (~35 implemented, ~28 in backlog) | Assessment, exercises, session planning, periodization, load monitoring, coaching |
| v2 (post-launch) | D01-D83 subset + D87b/D89/D91 | 18 | Flexibility axis, competition taper, menstrual cycle (upgraded scope), PE test, critical force |
| v3 (future) | D01-D83 subset | 6 | LLM Coach, RFD, critical force full protocol |
| Intentionally excluded | D24, D25, D27, D40, D46 | 5 | ATR model, microcycle granularity, reverse periodization, VBT, BFR |
| Superseded | D16, D18, D28 | 3 | D16→D47, D18→D33, D28→D75 |
| Reserved | D02, D07, D09 | 3 | — |

### Critical Safety Decisions

| # | Rule |
|---|------|
| D64 | Never suggest weight loss or comment on body composition |
| D80 | Block campus/max hangboard/hypergravity for <16 |
| D81 | Max 4 training days/week for <18 |
| D35 | Hangboard experience gates (2+ years for advanced protocols) |
| D55 | Exercise safety blacklist |
| D72 | Never prescribe full crimp on hangboard |

---

## How to Navigate

| Goal | Start Here |
|------|-----------|
| Starting from scratch | `PROJECT_BRIEF.md` → `DESIGN_GOAL` → `decision_consolidation_D01_D83.md` |
| Implementing a deferred decision | `ROADMAP_CURRENT.md` (backlog) → check `horst_integration_audit.md` for enrichment |
| Adding exercises to catalog | `horst_ch6_mobility_synthesis.md` §8 (38 exercises) + `consuegra_book_synthesis.md` |
| Building Coach v2 | `coach_knowledge_base_spec.md` + all Hörst files for coaching cues |
| Researching a topic | Numbered topic file (01-10) + corresponding Hörst chapter if exists |
| Looking for a specific decision | `decision_consolidation_D01_D83.md` §4 or §5 |
| Understanding what's implemented vs deferred | `ROADMAP_CURRENT.md` mega-brief status table |

---

## Open Research Items (tracked in ROADMAP_CURRENT.md)

| Item | Status |
|------|--------|
| **D82 menstrual cycle literature review** (Bruinvels, Hackney, McNulty, Wikström-Frisén) | 🔴 HIGH PRIORITY — upgraded scope needs evidence base |
| D03/R-01 flexibility axis — validated climber tests | ⏳ Not started |
| D22 competition taper protocol — Mujika, Bosquet | ⏳ Not started |
| CUE-02 forearm flexor stretch restriction (→ amend D33) | 📋 Proposed in audit |
| Topics 05-10 Steps 4-5 (detailed decision specs) | ⏳ Not started |
| Remaining books: MacLeod, Ilgner, Climbing Bible ×2, Bechtel pp.31-90 | ⏳ Not acquired |
| Krystina (menstrual cycle & strength thesis) — contact via Tabitha | 📋 Potential literature source for D82 |

---

## Stale References Log

| File | Issue | Decision | Fixed? |
|------|-------|----------|--------|
| `DESIGN_GOAL_MACROCICLO_v1_1.md` line 37 | "6 dimensioni" (now 5) | D01 | ✅ Session 1 implemented D01 |
| `DESIGN_GOAL_MACROCICLO_v1_1.md` lines 30, 44, 144, 157, 283 | "4×4" references | D47 | ❌ D47 deferred |
| `DESIGN_GOAL_MACROCICLO_v1_1.md` line 142 | Base "3-4 wk" (now ≥6 wk) | D21/D44 | ❌ D44 deferred |
| `PROJECT_BRIEF.md` line 64 | "6-axis profile" (now 5-axis) | D01 | ✅ Session 1 implemented D01 |
| `04_periodization.md` lines 254, 268 | Base "3-4 weeks" | D21/D44 | ❌ D44 deferred — **and the engine agrees** (4 wk lead / 2 wk boulder). The coach KB, which had promoted D44 to an enforced floor, was realigned to the engine in C263 (2026-07-30). If D44 is ever implemented, `backend/tests/test_c263_kb_engine_coherence.py` fails until the KB is updated too. |
| `02_finger_strength.md` line 206 | "Add full crimp cautiously" — ambiguous | D72 | ❌ D72 deferred |
| `knowledge_base_roadmap.md` | Says "PLANNING" — Topics 01-10 Step 1 all done | — | ⚠️ Content stale |

---

*End of Knowledge Base Index — v3 (2026-04-05)*
