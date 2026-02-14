# climb-agent — Project Brief

> Ultimo aggiornamento: 2026-02-14 (post Fase 1)
> Source of truth dettagliata: `docs/DESIGN_GOAL_MACROCICLO_v1.1.md`

---

## Cos'è

Motore di pianificazione allenamento arrampicata. Deterministico (stessi input → stessi output), closed-loop (feedback → adattamento), nessun LLM nel loop decisionale.

Risponde alla domanda: **"Dato il mio goal, i miei punti deboli, e quanto tempo ho, cosa devo fare oggi?"**

---

## Stato attuale

| Area | Quantità | Note |
|------|----------|------|
| Esercizi | 105 | 12 categorie (finger, power, PE, endurance, pull, push, core, prehab, technique, flexibility, handstand, conditioning) |
| Sessioni | 28 | gym evening, home lunch, recovery, flexibility, prehab, conditioning |
| Template | 11 | invariati da v1 |
| Test | 115 | tutti verdi (56 base + 17 assessment + 26 macrocycle + 16 planner_v2) |
| user_state | v1.5 | goal, assessment (6 assi), trips, macrocycle |

---

## Architettura: il flusso completo

```
Assessment (6 dimensioni → profilo radar 0-100)
  → Goal (lead_grade v1, target + deadline)
  → Macrocycle (Hörst 4-3-2-1 + DUP, 10-13 settimane, 5 fasi)
  → Week (planner_v2 phase-aware, domain weights + session pool)
  → Session (resolver seleziona esercizi concreti con carichi)
  → Feedback (granulare per esercizio, piano vs realtà)
  → Adattamento (closed-loop, multiplier-based)
```

In codice:

```
compute_assessment_profile()    [assessment_v1]
→ generate_macrocycle()         [macrocycle_v1]
→ generate_phase_week()         [planner_v2, per settimana]
→ resolve_session()             [resolve_session, per sessione]
```

---

## Repo structure

```
backend/
  engine/
    assessment_v1.py       ← Profilo 6 assi (0-100) con benchmark per grado
    macrocycle_v1.py        ← Generator Hörst 4-3-2-1 + DUP + deload
    planner_v1.py           ← Planner settimanale originale (mode-based)
    planner_v2.py           ← Planner phase-aware (usa macrociclo)
    resolve_session.py      ← Resolver sessioni → esercizi concreti
    progression_v1.py       ← Progressione carichi
    replanner_v1.py         ← Replanning (day override + ripple)
    closed_loop_v1.py       ← Closed-loop feedback processing
    adaptation/             ← Closed-loop (multiplier-based adjustments)
  api/                      ← FastAPI skeleton (health endpoint)
  catalog/
    exercises/v1/           ← 105 esercizi (JSON)
    sessions/v1/            ← 28 sessioni (JSON)
    templates/v1/           ← 11 template (JSON)
  data/
    user_state.json         ← Source of truth utente (v1.5)
    schemas/                ← JSON schemas per validazione log
  tests/                    ← 115 test pytest
frontend/                   ← Da costruire (Next.js PWA)
docs/
  vocabulary_v1.md          ← Vocabolario chiuso (aggiornato §5.1-5.6)
  DESIGN_GOAL_MACROCICLO_v1.1.md ← Design completo + roadmap
PROJECT_BRIEF.md            ← Questo file
CLAUDE.md                   ← Contesto per Claude Code
```

---

## Decisioni tecniche approvate

| Decisione | Scelta |
|-----------|--------|
| Persistenza | JSON/JSONL (no database) |
| Frontend | Next.js + React + Tailwind CSS (PWA mobile-first) |
| Assessment | Ogni 6 settimane, benchmark per grado target |
| Periodizzazione | Hörst 4-3-2-1 con DUP concurrent training |
| Deload | Misto: programmato + adattivo + pre-trip |
| Outdoor logging | Integrato nella day view |
| Feedback | Granulare per esercizio (5 livelli: very_easy → very_hard) |
| LLM Coach | Claude Sonnet come layer conversazionale (Fase 3.5) |
| Equipment | `equipment_required` solo per attrezzi indispensabili, opzionali in notes |
| Guided Session Mode | Timer UI con rest timer colorato (spec in design doc, Fase 3) |

---

## Principi non negoziabili

1. **Determinismo totale**: stessi input → stessi output, zero random
2. **user_state.json** è la source of truth utente (no file paralleli)
3. **Log append-only**, entry invalide in quarantena, mai cancellate
4. **Massimali ufficiali** aggiornati SOLO da sessioni test esplicite
5. **Vocabolario chiuso** (`docs/vocabulary_v1.md`) — no valori nuovi senza aggiornamento
6. **Hard filters P0** nel resolver non si toccano senza richiesta esplicita

---

## Comandi

```bash
python -m pytest backend/tests -q          # Test (115 verdi)
uvicorn backend.api.main:app --reload      # API dev server
from backend.engine.X import Y             # Import convention
```

---

## Roadmap

### Fase 0: Catalogo ✅
- 105 esercizi, 28 sessioni, vocabulary aggiornato
- pangullich → campus_board, guided session mode spec

### Fase 1: Macrocycle engine ✅
- assessment_v1.py, macrocycle_v1.py, planner_v2.py
- user_state v1.5 (goal, assessment, trips, macrocycle)
- 59 nuovi test (115 totali)

### Fase 2: Tracking + extras (PROSSIMA)
- Feedback granulare, logging climbing, trip planning
- Citazioni motivazionali, report engine

### Fase 3: UI (Next.js PWA)
- Day/week/feedback view, onboarding wizard
- Guided session mode con timer
- Report con grafici (Recharts)

### Fase 3.5: LLM Coach
- Claude Sonnet conversazionale sopra engine deterministico

### Fase 4: Evoluzione
- Più goal types, report annuale, multi-macrociclo, notifiche

---

## Come lavoriamo

- **Claude Code (terminale Mac)**: implementazione, file, commit, push
- **Claude.ai (chat)**: pianificazione, discussione, review
- Ogni fase → aggiornare questo file + test tutti verdi
