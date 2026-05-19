# Research Knowledge Base — climb-agent

This folder is a **snapshot** of the research knowledge base for climb-agent. It contains the scientific foundations, methodology decisions, and literature syntheses that inform the deterministic training engine and (via distillation) the LLM Coach.

---

## ⚠️ This is a snapshot — not the live KB

**The live, authoritative KB lives in a separate Claude.ai project** (`climb-agent Knowledge Base`). That project is where research happens, decisions are made, and topic files evolve. This folder in the repo is a **periodic snapshot** for version control, backup, and visibility.

| Where | What | Authority |
|-------|------|-----------|
| Claude.ai project `climb-agent Knowledge Base` | Live working KB — research, decisions, audit work | ✅ Source of truth |
| `docs/research_kb/` (this folder) | Versioned snapshot at meaningful milestones | 📸 Snapshot |
| `backend/coach/knowledge/` | Distilled, Coach-ready KB (Fase B output) | 🎯 Production input |

**Do not edit files in this folder directly** — changes here won't propagate back to the live KB. To update content: edit in the Claude.ai project first, then re-snapshot here.

---

## When to re-snapshot

Snapshot the KB into this folder when:

- A major topic file is completed (e.g., Topic 08 Bechtel integration)
- A decision finalization milestone is reached (e.g., v1 decisions locked)
- Before exporting to `backend/coach/knowledge/` (Fase B)
- Before any external review or collaboration handoff

**Last snapshot:** 2026-05-19

---

## Structure

```
research_kb/
├── README.md                                    ← this file
│
├── 00_INDEX_v3.md                               ← KB navigation index (authoritative)
├── KB_SUPER_SUMMARY.md                          ← high-level overview
│
├── 01_performance_determinants.md               ← Topic files (01-10)
├── 02_finger_strength.md
├── 03_pump_endurance_capillaries.md
├── 04_periodization.md
├── 05_psychology_mental.md
├── 06_nutrition_recovery_sleep.md
├── 07_overtraining_injury_load.md
├── 08_technique_movement_route_reading.md
├── 09_climbing_philosophy_motivation.md
├── 10_female_age_youth.md
│
├── horst_ch2_self_assessment_synthesis.md       ← Hörst (Training for Climbing 3rd ed.) chapter syntheses
├── horst_ch3_mental_training_synthesis.md
├── horst_ch4_technique_skill_synthesis.md
├── horst_ch6_mobility_synthesis.md
├── horst_ch11_nutrition_synthesis.md
├── horst_ch12_recovery_synthesis.md
├── horst_ch13_injury_synthesis.md
│
├── consuegra_book_synthesis.md                  ← Consuegra (forearm physiology) book synthesis
├── brief_training_methodology_explained.md      ← User-facing methodology explainer
│
├── decision_consolidation_D01_D91.md            ← Consolidated decision log (current authority)
├── horst_integration_audit.md                   ← Audit: Hörst syntheses ↔ topic files integration
├── kb_gaps_analysis.md                          ← Open gaps and pending research
│
├── research_methodology_v2_COMPLETE.md          ← Methodology for KB research process
├── coach_knowledge_base_spec.md                 ← Coach KB architecture spec (in revision)
│
├── docs_literature_hangboard.md                 ← Engine validation: 17 hangboard exercises × source matrix
└── literature_review_climbing_training.md       ← Training load and session structure literature
```

---

## File conventions

### Active knowledge
All `.md` files in this folder are **active knowledge** — current, methodologically validated, citable.

### What's NOT here
The live Claude.ai project also contains two consolidated files that are deliberately excluded from this snapshot:

- `_ARCHIVE_consolidated.md` — historical / superseded content. Git history serves the same purpose.
- `_MIRROR_consolidated.md` — engine implementation reference whose source of truth lives in the Claude Code project. Including it here would be a circular reference.

### Source quality standards
- PubMed peer-reviewed papers (SR > MA > RCT > cohort > expert opinion)
- Published books from credentialed authors (Hörst, Consuegra, Schöffl, López, Ilgner, etc.)
- Expert coaching sources with verified credentials (Eva López PhD, Eric Hörst MSc, Lattice Training, Jared Vagy DPT, Tyler Nelson DC, Hooper's Beta)
- Reddit/forums used only as leads — claims traced to original sources

Every methodological finding is captured in `decision_consolidation_D01_D91.md` with: finding, rationale, fix rule, prevention pattern.

---

## Engine context

The KB serves a deterministic training engine (no LLM in planning loop) with:

- **5-axis assessment** (D01 removed body composition): finger_strength, pulling_strength, power_endurance, technique, endurance
- **Hörst 4-3-2-1 periodization with DUP**, closed-loop feedback
- **Phases:** Base ≥6 wk → Strength (2-3 wk) → Power Endurance (2-3 wk) → Performance (1-2 wk) → Deload (1 wk)
- **Safety hard rules:** D55 (blacklist), D64 (no weight loss talk), D72 (no full crimp on hangboard), D80 (<16 youth blocks), D81 (<18 youth frequency), CUE-02 (no heavy flexor stretch pre-perf)

For full implementation state, see the climb-agent Claude Code project — it is the source of truth for engine code, catalog, and current implementation status.

---

## Re-snapshot procedure

When refreshing this snapshot:

1. In the Claude.ai project, verify all active files are current and the index (`00_INDEX_v3.md`) reflects the actual file set.
2. Download all active files from the Claude.ai project (excluding `_ARCHIVE_*` and `_MIRROR_*`).
3. Replace contents of `docs/research_kb/` with the new files.
4. Update the "Last snapshot" date in this README.
5. Commit with message: `docs(kb): snapshot research_kb @ YYYY-MM-DD — <reason>`.
