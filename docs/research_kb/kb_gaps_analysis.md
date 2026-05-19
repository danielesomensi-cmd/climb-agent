# KB Project — State of the Union & Gaps Analysis
> **Date:** 2026-03-27
> **Purpose:** Identify everything at risk of being lost. Propose fixes.
> **Action required:** Apply these updates to project knowledge files.

---

## 1. CRITICAL GAPS IDENTIFIED

### GAP 1: `00_INDEX.md` è vecchio di 11 giorni
- **Data:** 2026-03-16
- **Mancano:** 7 file Hörst, `horst_integration_audit.md`, `coach_knowledge_base_spec.md`, `ENGINE_ARCHITECTURE.md`, `engine_audit_report_v3_FINAL.md`, `ROADMAP_CURRENT.md`, `CLAUDE.md`
- **File count:** dice 20, in realtà sono **35+ file** nel project knowledge
- **References count:** dice ~260, ora sono **~275+** (Hörst aggiunge ~15 studi citati)
- **Rischio:** Chi apre il progetto KB per la prima volta non vede i file Hörst

### GAP 2: `ROADMAP_CURRENT.md` non ha sezione KB Research
- **Nessun riferimento** ai 7 file Hörst completati
- **Nessun link** al progetto KB di claude.ai come companion project
- I backlog entries (D33, D58, D70, ecc.) non menzionano il materiale Hörst che li arricchisce
- **Libri ancora da processare** non tracciati da nessuna parte nella roadmap
- **CUE-02** (forearm flexor stretch restriction) non è in nessun documento
- **Finger strength test architecture revision** (dalla memoria di progetto) non tracciata
- **Session 2 patch** (megabrief_patch_session2_pre.md) non tracciato
- **Rischio:** Claude Code implementa D33, D58, D70 senza sapere che ci sono 38 esercizi pronti + coaching cues

### GAP 3: `decision_consolidation_D01_D83.md` è incompleto
- **Non include D84–D91** (Session 1b — test protocol revision)
- Queste decisioni esistono nel mega-brief e nella roadmap ma non nella consolidation
- **Rischio:** Chi cerca "tutte le decisioni" trova solo D01–D83

### GAP 4: `cross_check_report.md` è datato
- Datato 2026-03-16
- Non tiene conto dei 7 file Hörst
- Dice "7 stale references" — alcuni sono stati corretti da Session 1 (D01 implementato)
- **Rischio:** Basso (il nuovo audit Hörst lo sostituisce di fatto)

### GAP 5: `coach_knowledge_base_spec.md` non è referenziato
- Non è nell'INDEX
- Non include le 6 nuove coaching cues da Hörst (G-Tox arricchito, forearm stretch warning, post-exercise protocol, scapular pull-up priority, caffeine periodization, central fatigue timeline)
- **Rischio:** Quando si costruisce il Coach v2, le cues Hörst vengono dimenticate

### GAP 6: `knowledge_base_roadmap.md` è stale
- Datato 2026-03-14 (PLANNING status)
- Non riflette che Topics 01–10 Step 1 sono TUTTI completati
- Non riflette che Hörst è stato processato (7/13 capitoli)
- Lista libri non aggiornata (ACT ebook ✅ completato, Hörst 7 capitoli ✅)
- **Rischio:** Chi legge questo file pensa che la research sia ancora in fase planning

---

## 2. PROPOSED UPDATES (in ordine di priorità)

### UPDATE 1: Patch `00_INDEX.md` (CRITICO)

Aggiungere:

```markdown
## Hörst Synthesis Files (Primary Source — 2026-03-27)

| File | Chapter | Topic Target | Content |
|------|---------|-------------|---------|
| `horst_ch2_self_assessment_synthesis.md` | Ch. 2 — Self-Assessment | Topic 01 | Goal setting, self-assessment methodology |
| `horst_ch3_mental_training_synthesis.md` | Ch. 3 — Mental Training | Topic 05 | Progressive relaxation, visualization, centering |
| `horst_ch4_technique_skill_synthesis.md` | Ch. 4 — Technique & Skill | Topic 08 | Drill descriptions, technique principles |
| `horst_ch6_mobility_synthesis.md` | Ch. 6 — Mobility/Antagonist | Topic 07 + Catalog | **38 exercises** (SMR, stretches, antagonist, scapular, push) |
| `horst_ch11_nutrition_synthesis.md` | Ch. 11 — Nutrition | Topic 06 | Macros, GI, hydration, creatine, caffeine |
| `horst_ch12_recovery_synthesis.md` | Ch. 12 — Recovery | Topic 06 | 3 recovery periods, G-Tox, refueling protocol |
| `horst_ch13_injury_synthesis.md` | Ch. 13 — Injury | Topic 07 | Treatment protocols, prevention principles |

## Audit & Integration Files

| File | Purpose |
|------|---------|
| `horst_integration_audit.md` | Cross-check of 7 Hörst files vs D01–D83: 0 conflicts, 14 confirmations, 6 new coaching cues |
| `coach_knowledge_base_spec.md` | Design spec for Coach KB (v1 rationale fields + v2 LLM Coach) |
| `engine_audit_report_v3_FINAL.md` | Full codebase audit report |
| `ENGINE_ARCHITECTURE.md` | Current engine architecture documentation |

## Navigation Update

- **Implementing a deferred decision?** Check `horst_integration_audit.md` §5-§8 for Hörst material that enriches it
- **Adding exercises to catalog?** `horst_ch6_mobility_synthesis.md` §8 has 38 exercises ready to import
- **Building Coach v2?** Start with `coach_knowledge_base_spec.md` + all Hörst files for coaching cues
```

Update header:
```
> **Last updated:** 2026-03-27
> **Total files:** 35
> **Total decisions:** 91 (D01-D83 + D84-D91 from Session 1b)
> **Total references:** ~275
```

---

### UPDATE 2: Sezione KB Research in `ROADMAP_CURRENT.md` (CRITICO)

Aggiungere dopo "Priority 2.5b — Catalog & Polish":

```markdown
---

## KB Research Pipeline (companion project: claude.ai "climb-agent KB")

> **Where:** Questo lavoro di ricerca vive in un progetto claude.ai separato chiamato
> "climb-agent knowledge base". I file risultanti sono nel project knowledge di quel progetto
> E vengono copiati qui come reference.
>
> **Come consultare:** Aprire il progetto "climb-agent knowledge base" su claude.ai.
> I file chiave sono tutti nel project knowledge di quel progetto.
>
> **Regola:** Prima di implementare qualsiasi decisione deferred (D10-D79), consultare
> `horst_integration_audit.md` nel progetto KB per verificare se ci sono enrichment disponibili.

### Hörst "Training for Climbing" (3rd ed.) — 7/13 capitoli completati

| File | Ch. | Status | Enriches |
|------|-----|--------|----------|
| `horst_ch2_self_assessment_synthesis.md` | 2 | ✅ | D01 context |
| `horst_ch3_mental_training_synthesis.md` | 3 | ✅ | D29, D30 context |
| `horst_ch4_technique_skill_synthesis.md` | 4 | ✅ | D73, D76 context |
| `horst_ch6_mobility_synthesis.md` | 6 | ✅ | **D33, D58, D60 — 38 exercises ready to import** |
| `horst_ch11_nutrition_synthesis.md` | 11 | ✅ | D65, D66, D67 enrichment |
| `horst_ch12_recovery_synthesis.md` | 12 | ✅ | **D17, D70 enrichment + post-exercise protocol** |
| `horst_ch13_injury_synthesis.md` | 13 | ✅ | D68-D72 context |

**Integration audit:** `horst_integration_audit.md` — 0 conflicts, 14 confirmations, 6 new coaching cues.

### Enrichment notes per deferred decision

| Decision | Hörst Enrichment Available | Source |
|----------|---------------------------|--------|
| D33 (warm-up generator) | ⚠️ **CUE-02: Don't stretch forearm flexors hard pre-performance** (reduces grip 1h). Add as constraint to warm-up logic. | Ch. 6 §4 tip #8 |
| D33 (warm-up generator) | Ch. 6 warm-up exercises (EX-STR-01, EX-STR-02, EX-ANT-01) ready to populate | Ch. 6 §4, §6 |
| D58 (postural correction — YTW missing) | **EX-SCAP-01 "T" + EX-SCAP-02 "Y"** exercises with full protocols | Ch. 6 §D2 |
| D58 + D60 | **38 total exercises** from Ch. 6 ready to import (antagonist, scapular, push) | Ch. 6 §8 master list |
| D37 (core drills from Matros) | No Hörst enrichment — Matros/ACT remains primary source | — |
| D17 (G-Tox cue) | Detailed physiological mechanism + Roberts 2003 citation | Ch. 12 §3.2 |
| D70 (overtraining heuristics) | **Central fatigue: nerve cell 7× slower recovery than muscle** (Bompa 1983). Add to detection logic. | Ch. 12 §2.1 |
| D65 (sleep tips) | Quantified: 6–7h minimum, 8–10h after hard training | Ch. 12 §5.5 |
| D47 (varied-intensity intervals) | No Hörst enrichment — Consuegra remains primary source | — |

### Remaining books to process

| # | Book | Status | Needed from Topic |
|---|------|--------|-------------------|
| 1 | **Hörst — remaining chapters** (5, 7, 8, 9, 10) | 🔜 If needed | Various |
| 2 | **Steve Bechtel — Climb Strong: Drills Manual** (pp. 31–90) | 📷 Photograph physical copy | Topic 08 (technique drills) |
| 3 | MacLeod — 9 Out of 10 Climbers | 🛒 Da comprare (DRM-free PDF or photos) | Topics 04, 05, 07, 08 |
| 4 | Ilgner — The Rock Warrior's Way | 🛒 Da comprare | Topics 05, 09 |
| 5 | Mobråten — The Climbing Bible | 🛒 Da comprare | Topics 01, 02, 04, 07, 08 |
| 6 | Christophersen — Climbing Bible: Injuries | 🛒 Da comprare | Topic 07 |

### Open KB research items

| Item | Status | Notes |
|------|--------|-------|
| **Session 2 patch** (megabrief_patch_session2_pre.md) | ⏸️ Prepared, not yet applied | 4 FIND/REPLACE corrections: D11, D12, D39, D72 |
| **D84 pulling strength test** | ⏸️ Under review | Maximum load parameters for pulling test |
| **Finger strength test architecture revision** | ⏸️ Under review | 5s→7s alignment with Lattice; bodyweight duration test cleanup |
| **Topics 05–10 Steps 4–5** | ⏳ Not started | Detailed decision specs for remaining topics |
| **CUE-02 formalization** | 📋 Proposed in audit | Forearm flexor stretch restriction → amend D33 or new decision |
```

---

### UPDATE 3: Note su decisioni deferred nel backlog della roadmap (IMPORTANTE)

Aggiungere note inline ai backlog entries esistenti:

**D33 row:**
```
| D33 | Dedicated `generate_warmup()` function | M | 5-phase protocol generator. **⚠️ See KB: Ch. 6 has warm-up exercises + CUE-02 (no forearm flexor stretch before performance).** |
```

**D58 row:**
```
| D58 | YTW raises exercise (missing from postural set) | XS | 4/5 done, only YTW missing. **⚠️ See KB: Ch. 6 has T exercise (EX-SCAP-01) and Y exercise (EX-SCAP-02) with full protocols.** |
```

**D70 row:**
```
| D70 | Overtraining detection heuristics | M | 5-flag system. **⚠️ See KB: Ch. 12 adds central fatigue recovery timeline (nerve cell 7× slower, Bompa 1983).** |
```

**D65/D66/D67 rows:**
```
| D65 | Sleep education tips | S | **See KB: Ch. 11 (quantified ranges) + Ch. 12 (sleep = #1 recovery tool).** |
| D66 | Nutrition messaging at phase transitions | S | **See KB: Ch. 11 has macro ratios by climbing style (65:15:20 vs 55:15:30), GI tables, refueling protocol.** |
| D67 | Collagen + vitamin C educational mention | XS | **See KB: Ch. 11 also covers creatine (small-dose OK, loading counterproductive) and caffeine periodization.** |
```

---

### UPDATE 4: `coach_knowledge_base_spec.md` — nuove cues da aggiungere (v2)

Aggiungere alla sezione "FAQ Bank" o "Coaching Cue Context":

```markdown
### NEW from Hörst Integration (2026-03-27)

| Cue ID | Content | Source | Section |
|--------|---------|--------|---------|
| CUE-H01 | G-Tox: alternate raised-arm/dangling-arm every 5–10s at rest. Raised arm aids venous return via gravity. Roberts 2003 confirmed. | Ch. 12 §3.2 | §4 Coaching Cues |
| CUE-H02 | **No heavy forearm flexor stretching before performance sessions** — reduces grip strength up to 1 hour. Light stretching + Armaid OK. | Ch. 6 §4 tip #8 | §4 Coaching Cues |
| CUE-H03 | Post-exercise refueling: 4:1 carb:protein within 30 min. Chocolate skim milk = ideal. Waiting >2h = 50% less glycogen (Burke 1999). | Ch. 12 §4.1 | §7 FAQ Bank |
| CUE-H04 | Scapular pull-up = "best climbing exercise nobody does." Develops kinesthetic scapular awareness. Priority for all training plans. | Ch. 6 §D2 | §4 Coaching Cues |
| CUE-H05 | Caffeine periodization: reduce daily dose pre-competition → return to normal on day. Don't double dose (jitters, GI distress). | Ch. 11 §7.5 | §7 FAQ Bank |
| CUE-H06 | Central fatigue: if "off" after several rest days → may need 2–10 more days. Nerve cell recovery 7× slower than muscle (Bompa 1983). | Ch. 12 §2.1 | §7 FAQ Bank |
| CUE-H07 | Weak rotator cuff = hidden limiter of max pulling/grip strength. Central governor limits power output from unstable shoulders. | Ch. 6 §D2 | §4 Coaching Cues |
| CUE-H08 | Active rest between climbs +35% lactate clearance vs sitting (Watts 2000). Walk 20 min + self-massage forearms. | Ch. 12 §3.3 | §4 Coaching Cues |
```

---

### UPDATE 5: `decision_consolidation_D01_D83.md` → rinominare/appendere D84–D91

La consolidation si ferma a D83. Le decisioni D84–D91 (Session 1b) esistono solo nel mega-brief e nella roadmap.

**Opzione A (semplice):** Aggiungere un appendice al file esistente:
```markdown
## APPENDIX: D84–D91 (Session 1b — Test Protocol Revision)

> Added 2026-03-17. See mega-brief Session 1b for full specifications.

| # | Decision | Status |
|---|----------|--------|
| D84 | Pulling strength test revision (max load parameters) | ⏸️ Open — under review |
| D84b | Two-test pulling strength architecture | ✅ Implemented |
| D85 | Finger strength test: MVC-7 on 20mm edge | ✅ Implemented |
| D86 | Endurance test: bodyweight duration on 20mm | ✅ Implemented |
| D87b | PE diagnostic test (repeaters 60% to failure) | Deferred v2 |
| D88 | Test scheduling in macrocycle | ✅ Implemented |
| D89 | Critical Force test (simplified, 2-point) | Deferred v2 |
| D90 | Test_max_hang replaces legacy protocol | ✅ Implemented |
| D91 | test_pe_repeaters_60 + baselines.power_endurance | Deferred v2 |
```

---

## 3. CHECKLIST — Nulla si perde

| # | Item | Tracked Where | Status |
|---|------|---------------|--------|
| 1 | 7 Hörst synthesis files | Project knowledge ✅ | **NOT in 00_INDEX** ❌ |
| 2 | Hörst integration audit | Project knowledge ✅ | **NOT in 00_INDEX, NOT in ROADMAP** ❌ |
| 3 | 38 Ch. 6 exercises ready for D58/D60 | horst_ch6 file ✅ | **NOT linked from ROADMAP D58 entry** ❌ |
| 4 | CUE-02 forearm flexor stretch restriction | audit file ✅ | **NOT in any decision or roadmap** ❌ |
| 5 | Post-exercise refueling protocol (4:1, 30min) | horst_ch12 file ✅ | **NOT in coach_kb_spec** ❌ |
| 6 | Central fatigue 7× timeline | horst_ch12 file ✅ | **NOT linked from D70 entry** ❌ |
| 7 | Caffeine periodization | horst_ch11 file ✅ | **NOT in coach_kb_spec** ❌ |
| 8 | Session 2 patch (megabrief_patch_session2_pre.md) | Memory only ⚠️ | **NOT in project knowledge, NOT in ROADMAP** ❌ |
| 9 | Finger strength test architecture revision | Memory only ⚠️ | **NOT in ROADMAP** ❌ |
| 10 | D84 pulling strength test (open) | Memory only ⚠️ | **In ROADMAP backlog** ✅ (as deferred) |
| 11 | D84–D91 existence | mega-brief + roadmap ✅ | **NOT in decision_consolidation** ❌ |
| 12 | Books remaining (MacLeod, Ilgner, Climbing Bible ×2, Bechtel) | knowledge_base_roadmap.md ✅ | **NOT in ROADMAP_CURRENT** ❌ |
| 13 | Coach KB spec enrichment with Hörst cues | — | **NOT done** ❌ |
| 14 | `knowledge_base_roadmap.md` stale (says PLANNING) | File exists ✅ | **Content outdated** ⚠️ |
| 15 | `cross_check_report.md` stale | File exists ✅ | **Superseded by audit** ⚠️ |
| 16 | Creatine enrichment for Topic 06 | horst_ch11 ✅ | **NOT applied to topic file** ❌ |

**13 out of 16 items have gaps.** The biggest risk is items 8 and 9 which exist only in Claude memory — if that memory gets cleared, they're gone.

---

## 4. RECOMMENDED ORDER OF OPERATIONS

1. **NOW (this session):** Produce the updated files:
   - `00_INDEX.md` (updated)
   - ROADMAP patch (KB Research section + backlog annotations)
   
2. **Daniele saves** both files to project knowledge → they become persistent

3. **Next session:** Apply remaining enrichments:
   - Coach KB spec update with 8 new cues
   - Decision consolidation appendix (D84–D91)
   - Session 2 patch brief → save to project knowledge (currently only in memory!)

4. **When ready for Claude Code:** The ROADMAP now points to all KB material, so nothing gets missed during implementation.

---

*End of gaps analysis*
