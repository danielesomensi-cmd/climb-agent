# Audit Post-Fix — E2E Retest + Documentation Coherence

> Date: 2026-02-15
> Tester: Claude Code (QA) + Daniele Somensi
> Engine version: Fase 1 + Fase 1.5 (Cluster 1 + Cluster 2)
> User state: v1.5 (goal: 8b redpoint, current: 8a+, 77kg, 10y experience)
> Tests: 155 passing (python3 -m pytest backend/tests -q)

---

## 1. Tabella finding F1-F14 — Stato verificato

### Finding originali

| Finding | Descrizione | Severità | Stato doc | Stato verificato | Step | Note |
|---------|-------------|----------|-----------|------------------|------|------|
| F1 | Resolver ignora inline blocks | P0 | FIXED | ✅ CONFERMATO | Step 5 | 4 sessioni inline → tutte ≥3 esercizi. `_resolve_inline_block()` funziona. |
| F2 | Planner pool non cicla, sessioni concentrate | P0 | FIXED | ✅ CONFERMATO | Step 4 | 2-pass algorithm. Sessioni distribuite uniformemente su 6/7 giorni in tutte le fasi. |
| F3 | Base phase zero finger work | P0 | FIXED | ✅ CONFERMATO | Step 4 | `finger_maintenance_home` nel pool Base, piazzato 2x/week (Tue, Fri) con gap ≥2gg. |
| F4 | Nessun integration test sessioni reali | P0 | FIXED | ✅ CONFERMATO | Step 5 | 29/29 sessioni del catalogo risolvono con successo, 0 skip, 0 errori. |
| F5 | PE score — double counting + no test oggettivi | P1 | FIXED | ✅ CONFERMATO | Step 2 | PE=51 (era 25 pre-fix). Formula: repeater 40% + gap 40% + self_eval 20%. Rimuovendo repeater PE scende a 37 (delta +14). Penalty ridotte (-8/-4 vs -15/-8). |
| F6 | Replanner — intent mancanti | P1 | FIXED | ⚠️ PARZIALE | Step 7 | 11/12 intent funzionano (core, prehab, flexibility, finger_maintenance, finger_max aggiunti). Intent **"projecting"** non mappato — un intent naturale per climber. Collegato a F14 ma potrebbe avere variante indoor. |
| F7 | Replanner usa planner_v1 | P1 | FIXED | ✅ CONFERMATO | Step 7 | Replanner importa `_SESSION_META` e `generate_phase_week` da planner_v2. `apply_day_override` accetta `phase_id`. |
| F8 | Pre-trip deload solo annotazione | P1 | FIXED | ✅ CONFERMATO | Step 3 | Confronto diretto con/senza `pretrip_dates`: sessioni hard bloccate, sostituite con prehab/flexibility. Effetto reale verificato. |
| F9 | Nessuna validazione goal vs livello attuale | P1 | FIXED | ✅ CONFERMATO | Step 3+8 | Gap 8b→8a+ = 1 → no warning ✅. Goal 8a con current 8a+ → warning "target not harder" ✅. Gap > 8 → warning "ambitious" ✅. |
| F10 | Base crolla a 1w con macrociclo corto | P1 | FIXED | ⚠️ PARZIALE | Step 3+8 | Floor 2w funziona per total_weeks ≥ 10. Per total_weeks=8 la Base viene eliminata (0w). Per total_weeks=6 si produce durata NEGATIVA (-2w). Causa: riga 179 di `_compute_phase_durations` sovrascrive il floor applicato a riga 166. Vedi dettaglio sotto. |
| F11 | Sessioni climbing non prioritizzate | P2 | FIXED | ✅ CONFERMATO | Step 4 | 2-pass: pass1 piazza climbing (sera), pass2 riempie complementari (pranzo). Ordine corretto in tutte le fasi. |
| F12 | board_moonboard non in vocabulary | P2 | FIXED | ✅ CONFERMATO | B5 | `board_moonboard`, `bench`, `barbell` presenti in vocabulary_v1.md e usati in user_state/exercises. |
| F13 | Distribuzione sessioni non uniforme | P2 | FIXED | ✅ CONFERMATO | Step 4 | Tutte le fasi usano 6/7 giorni (3/7 deload). Nessuna concentrazione lun-mer. |
| F14 | Outdoor climbing non supportato | P2 | DEFERRED | 🔲 CONFERMATO | N/A | Nel backlog B2. Intent "outdoor" e "projecting" non nel replanner. Sessioni outdoor non esistono nel catalogo. |

### Riepilogo finding originali

| Stato | Conteggio | Finding |
|-------|-----------|---------|
| ✅ Confermato risolto | 11/14 | F1, F2, F3, F4, F5, F7, F8, F9, F11, F12, F13 |
| ⚠️ Parzialmente risolto | 2/14 | F6 (projecting mancante), F10 (floor KO per <10w) |
| 🔲 Deferred confermato | 1/14 | F14 (outdoor → B2) |

### Discrepanze col documento e2e_test_results.md

Il doc segna F6 e F10 come "FIXED" ma la verifica mostra che sono parziali:
- **F6**: doc dice "expanded from 7 to 12 intents" → vero, ma "projecting" resta non mappato
- **F10**: doc dice "enforces min 2 weeks" → vero per la prima applicazione, ma la logica di scaling finale (riga 179) può sovrascrivere il floor

---

## 2. Nuovi finding da questo test

### NEW-F1 — Prescription climbing exercises vuota
- **Severità**: P2
- **Step**: 5
- **Descrizione**: Gli esercizi climbing (`gym_arc_easy_volume`, `gym_technique_boulder_drills`, `gym_power_endurance_4x4`) non hanno prescription strutturata — mancano grado target, volume (n. vie/boulder), tempo, ripetizioni, rest tra set. L'unico output è un campo `notes` con testo generico.
- **Impatto**: La UI non può mostrare indicazioni concrete all'utente. Un climber non sa a che grado scalare, quante vie fare, quanto riposare.
- **Fix suggerito**: Aggiungere a ogni esercizio climbing: `suggested_grade_offset` (es. -2 dal current_grade per ARC, 0 per limit), `volume` (es. "4 boulder" o "20 min continuous"), `rest_between` (es. 180s per limit, 0 per ARC). Il resolver dovrebbe calcolare il grado suggerito da `current_grade + offset`.
- **Fase suggerita**: 1.75 (arricchimento sessioni)

### NEW-F2 — Equipment mancante su esercizi climbing (GRAVE)
- **Severità**: **P0**
- **Step**: 6
- **Descrizione**: `gym_arc_easy_volume`, `gym_technique_boulder_drills`, `gym_power_endurance_4x4` hanno `location_allowed: ["gym"]` ma `equipment_required: []`. Questi esercizi richiedono fisicamente una parete boulder/lead per essere eseguiti, ma il resolver li piazza in qualsiasi palestra (anche una senza muro di arrampicata) perché passano il filtro P0 equipment.
- **Impatto**: Se l'utente ha una palestra fitness (senza muro), il resolver propone comunque boulder drills. Viola il principio "equipment_required è truly mandatory".
- **Fix suggerito**: Aggiungere `equipment_required: ["gym_boulder"]` (o `["gym_routes"]` per esercizi lead) a tutti gli esercizi climbing. Il vocabulary ha già `gym_boulder` e `gym_routes` come equipment canonici (§1.2).
- **Fase suggerita**: Immediato (pre-1.75), è un bug di dati non di logica.

### NEW-F3 — Test sessions mai pianificate
- **Severità**: P1
- **Step**: 6
- **Descrizione**: Il design doc (§2.3) specifica "Assessment periodico ogni 6 settimane, mini-test integrati nelle sessioni normali" e cita `test_max_hang_5s` come sessione esistente. In realtà:
  - `test_max_hang_5s.json` esiste nel catalogo (29 sessioni) ✅
  - `test_max_hang_5s` NON è in `_SESSION_META` del planner ❌
  - `test_max_hang_5s` NON è in nessun session pool di nessuna fase ❌
  - Non esiste nessun meccanismo di scheduling periodico ❌
  - Sessione `test_power_endurance` non esiste (menzionata nel doc come "da creare") ❌
  - Il closed loop aggiorna `working_loads` ma NON `assessment.tests` ❌
- **Impatto**: Il profilo 6 assi non viene mai aggiornato. L'utente allena per 12 settimane con valori assessment dell'onboarding. Il principio "closed-loop" è violato per l'assessment.
- **Fix suggerito**:
  1. Aggiungere `test_max_hang_5s` a `_SESSION_META` (hard=True, finger=True, intensity=max)
  2. Aggiungerlo ai pool di fine Base e fine Strength_Power
  3. Creare `test_power_endurance.json` (repeater test)
  4. Implementare scheduling: "ogni N settimane, sostituisci 1 sessione con test"
  5. Il risultato del test deve aggiornare `assessment.tests` e triggare recompute del profilo
- **Fase suggerita**: 1.75 o 2 (dipende da priorità closed-loop)

### NEW-F4 — Ripple effect troppo conservativo
- **Severità**: P1
- **Step**: 7
- **Descrizione**: Quando l'utente fa un override con sessione hard/max (es. `power_contact_gym`), il replanner controlla solo i giorni +2/+3 dalla reference_date e downgrida SOLO sessioni che sono già hard. Se i giorni successivi hanno sessioni medium (es. `technique_focus_gym`), vengono lasciate invariate.
- **Impatto**: Dopo boulder al limite (max intensity, alto stress CNS), il giorno successivo ha ancora `technique_focus_gym` (medium) invece di essere alleggerito a recovery. Un coach reale allegerirebbe sempre il giorno dopo un hard day.
- **Fix suggerito**: Dopo override hard/max, il giorno immediatamente successivo (override_day + 1) dovrebbe essere forzato a recovery/low, indipendentemente da cosa c'era prima. I giorni +2/+3 possono restare con la logica attuale (downgrade solo se hard).
- **Fase suggerita**: 1.75

### NEW-F5 — total_weeks < 9 produce durate negative
- **Severità**: P1
- **Step**: 8d
- **Descrizione**: `_compute_phase_durations(profile, 6)` restituisce `base: -2` — durata negativa. Con total_weeks=8 restituisce `base: 0`. Il totale output (8w) non corrisponde al richiesto (6w). Nessun warning emesso.
- **Root cause**: In `macrocycle_v1.py`, la funzione applica il floor di 2w per fase (riga 166), ma poi la logica di scaling (righe 173-179) sovrascrive il floor:
  ```python
  # Riga 166: floor applicato
  durations[phase_id] = max(2, durations[phase_id])   # base=2 ✅
  # Riga 174: primo scaling
  durations["base"] = max(2, durations["base"] + diff) # max(2, 2+(-4))=2 ✅
  # Riga 179: secondo scaling SOVRASCRIVE il floor
  durations["base"] += total_weeks - actual_total       # 2+(8-10)=0 ❌
  ```
- **Fix suggerito**:
  1. Calcolare il minimo strutturale: 4 fasi × 2w + 1w deload = 9w
  2. Se `total_weeks < 9`, emettere warning e clampare a 9
  3. Il secondo scaling (riga 179) deve rispettare il floor: `durations["base"] = max(2, durations["base"] + delta)`
- **Fase suggerita**: Immediato (bug fix)

### NEW-F6 — Phase mismatch silenzioso nel replanner
- **Severità**: P2
- **Step**: 7
- **Descrizione**: `apply_day_override` accetta un `phase_id` esplicito diverso dalla fase corrente del piano senza emettere alcun warning. La sessione viene creata con phase_id discordante silenziosamente.
- **Esempio**: Override con `phase_id='power_endurance'` su piano fase `base` → la sessione risultante ha `phase_id='power_endurance'` ma nessun log/warning indica la discordanza.
- **Fix suggerito**: Se `phase_id` passato ≠ `plan.profile_snapshot.phase_id`, aggiungere un warning nell'array `adaptations`: `{"type": "phase_mismatch_warning", "requested": "power_endurance", "current": "base"}`.
- **Fase suggerita**: 1.75

### NEW-F7 — Finger compensation mancante dopo override
- **Severità**: P2
- **Step**: 7
- **Descrizione**: Se l'utente fa un override che sostituisce una sessione finger (es. `finger_maintenance_home` → `power_contact_gym`), il replanner non prova a ripiazzare la sessione finger in un altro giorno della settimana. Il finger training è semplicemente perso.
- **Impatto**: Con 2 finger days/week, un override ne rimuove 1. In 4 settimane di fase Base, questo può risultare in settimane con solo 1 sessione finger, insufficiente per mantenimento.
- **Fix suggerito**: Dopo override che rimuove finger session, il replanner dovrebbe cercare un giorno libero (o con sessione complementare sostituibile) e piazzare il finger training lì, rispettando il gap 48h.
- **Fase suggerita**: 2

### NEW-F8 — Deload troppo leggera
- **Severità**: P2
- **Step**: 4
- **Descrizione**: La settimana deload contiene solo flexibility_full, prehab_maintenance, regeneration_easy (3 sessioni, tutte pranzo, tutte low). Zero climbing. La letteratura (Hörst "Training for Climbing", Lattice Training) raccomanda 1-2 sessioni di easy climbing durante il deload per mantenere il pattern motorio e la connessione con la roccia.
- **Fix suggerito**: Aggiungere `regeneration_easy` o `endurance_aerobic_gym` (con intensity forzata a low) al pool deload come sessione climbing facile. 2-3 sessioni totali con almeno 1 di climbing.
- **Fase suggerita**: 1.75 (validazione letteratura B3)

### NEW-F9 — Fase PE senza finger maintenance
- **Severità**: P2
- **Step**: 4
- **Descrizione**: La fase Power Endurance genera 6 sessioni tutte climbing/PE, con 0 sessioni finger. `finger_strength_home` è nel pool come "available" ma il pass1 riempie tutti i 6 giorni con sessioni climbing, non lasciando spazio per il pass2. La forza dita va almeno mantenuta in fase PE.
- **Fix suggerito**: Forzare almeno 1 finger_maintenance nel pool PE come "primary" oppure riservare 1 slot per complementari anche quando pass1 riempie 6 giorni.
- **Fase suggerita**: 1.75

### NEW-F10 — Pre-trip: giorno partenza trip ha sessione HARD
- **Severità**: P2
- **Step**: 3
- **Descrizione**: Nella simulazione pre-trip Arco (18 aprile), i giorni 13-17 aprile sono correttamente marcati [PRETRIP] con sessioni soft. Ma sabato 18 aprile (giorno di inizio trip!) ha `power_endurance_gym` (HARD). Il giorno di partenza del trip dovrebbe essere REST o al massimo easy/travel.
- **Fix suggerito**: Includere `trip.start_date` nella lista `pretrip_dates` (attualmente il window è solo i 5 giorni PRIMA, non il giorno stesso).
- **Fase suggerita**: Immediato (bug fix semplice)

---

## 3. Discrepanze documentazione

### B1 — Numeri coerenti

| Metrica | Actual | PROJECT_BRIEF | CLAUDE.md | e2e_test_results | Match |
|---------|--------|---------------|-----------|------------------|-------|
| Esercizi | 102 | 102 | 102 | - | ✅ |
| Sessioni | 29 | 29 | 29 | - | ✅ |
| Template | 11 | 11 | 11 | - | ✅ |
| Test | 155 | 155 | 155 | 155 | ✅ |
| Schema | 1.5 | 1.5 | 1.5 | - | ✅ |

**Nessuna discrepanza numerica.**

### B2 — Roadmap coerente

| Fase | BRIEF | DESIGN | Status match |
|------|-------|--------|-------------|
| 0 | Catalogo ✅ | Dati + API ✅ | ✅ |
| 1 | Macrocycle engine ✅ | Macrociclo engine ✅ | ✅ |
| 1.5 | Fix post-E2E ✅ | Fix post-E2E ✅ | ✅ |
| 1.75 | Arricchimento sessioni 🔲 | Arricchimento sessioni 🔲 | ✅ |
| 2 | Tracking + extras 🔲 | Tracking + extras 🔲 | ✅ |
| 3 | UI (Next.js PWA) 🔲 | UI 🔲 | ✅ |
| 3.5 | LLM Coach 🔲 | LLM Coach layer 🔲 | ✅ |
| 4 | Evoluzione 🔲 | Evoluzione 🔲 | ✅ |

**Discrepanze minori (solo naming)**:
- Fase 0: "Catalogo" vs "Dati + API" — stessa fase, nomi diversi
- Fase 3: "UI (Next.js PWA)" vs "UI" — il BRIEF è più specifico

**Stesse fasi, stessi stati, Fase 1.5 e 1.75 presenti in entrambi.** ✅

### B3 — Backlog vs Roadmap

| Item | Descrizione | Status | Fase | In roadmap? |
|------|-------------|--------|------|-------------|
| B1 | Core standalone | TODO | 1.75 | ✅ (incorporato in B8) |
| B2 | Sessioni outdoor | TODO | 2 | ✅ (F14 tracked qui) |
| B3 | Validazione letteratura | TODO | 1.75 | ✅ (incorporato in B8) |
| B4 | Load score | TODO | 1.75 | ✅ (incorporato in B8) |
| B5 | Replanner phase-aware | DONE | 1.5 | ✅ |
| B6 | PE assessment repeater | DONE | 1.5 | ✅ |
| B7 | Validazioni edge case | DONE | 1.5 | ✅ |
| B8 | Arricchimento sessioni | TODO | 1.75 | ✅ |

- B5, B6, B7 marcati Done ✅
- B1-B4, B8 ancora TODO ✅
- B8 corrisponde a Fase 1.75 e incorpora B1, B3, B4 ✅

**Raccomandazione backlog vs roadmap**: Il backlog dovrebbe restare separato dal design doc.
Motivazione: il design doc descrive il *cosa* e il *perché* per fase; il backlog descrive item operativi specifici con dipendenze e dettagli tecnici. B8 nel backlog dettaglia i "5-7 blocchi per sessione, pulling_strength template, ecc." — dettagli che non servono nella roadmap di alto livello. Tenere entrambi sincronizzati sugli stati (✅/🔲) ma con livelli di dettaglio diversi.

**Item mancanti dal backlog**: i nuovi finding di questo audit (NEW-F1 → NEW-F10) dovrebbero essere aggiunti come item B9-B18 o come un nuovo cluster di fix (Fase 1.5b o pre-1.75).

### B4 — e2e_test_results.md

- Post-fix note presente ✅
- 12/14 finding con stato corretto ✅
- **2 finding con stato da aggiornare**: F6 e F10 sono segnati FIXED ma sono parziali ⚠️

### B5 — Vocabulary coerenza

| Check | Risultato |
|-------|-----------|
| Equipment in user_state vs vocabulary | ✅ Tutti presenti |
| Equipment in exercises vs vocabulary | ✅ Tutti presenti |
| Locations in exercises vs vocabulary | ✅ Tutti presenti |
| Roles in exercises vs vocabulary | ✅ Tutti presenti |
| Domains in exercises vs vocabulary | ✅ Tutti presenti |
| F12: board_moonboard in vocabulary | ✅ |
| F12: bench in vocabulary | ✅ |
| F12: barbell in vocabulary | ✅ |

**Nessuna discrepanza vocabulary.** F12 confermato risolto.

### B6 — user_state.json conformità schema v1.5

| Campo | Atteso | Trovato | Match |
|-------|--------|---------|-------|
| schema_version | 1.5 | 1.5 | ✅ |
| goal.goal_type | lead_grade | lead_grade | ✅ |
| goal.target_grade | 8b | 8b | ✅ |
| goal.current_grade | 8a+ | 8a+ | ✅ |
| assessment.body.weight_kg | 77.0 | 77.0 | ✅ |
| assessment.experience.climbing_years | 10 | 10 | ✅ |
| assessment.experience.structured_training_years | 5 | 5 | ✅ |
| assessment.tests.max_hang_20mm_5s_total_kg | 125.0 | 125.0 | ✅ |
| assessment.tests.repeater_7_3_max_sets_20mm | 24 | 24 | ✅ |
| assessment.profile | null | null | ✅ |
| trips[0].start_date | 2026-04-18 | 2026-04-18 | ✅ |
| macrocycle | null | null | ✅ |
| planning_prefs.target_training_days_per_week | 6 | 6 | ✅ |

**Tutti i campi v1.5 presenti e corretti.** ✅

---

## 4. Azioni correttive

### Priorità P0 — Bloccanti (da risolvere prima di Fase 1.75)

| # | Finding | Azione | File coinvolti |
|---|---------|--------|----------------|
| 1 | NEW-F2 | Aggiungere `equipment_required: ["gym_boulder"]` agli esercizi climbing (gym_arc_easy_volume, gym_technique_boulder_drills, gym_power_endurance_4x4, board_limit_boulders, e tutti gli altri esercizi che richiedono parete/boulder) | `backend/catalog/exercises/v1/exercises.json` |
| 2 | NEW-F5 | Fix `_compute_phase_durations`: (a) validare total_weeks ≥ 9, (b) il secondo scaling rispetti il floor, (c) mai durate negative | `backend/engine/macrocycle_v1.py` |
| 3 | NEW-F10 | Includere `trip.start_date` in `pretrip_dates` (non solo i 5 giorni prima) | `backend/engine/macrocycle_v1.py` o `planner_v2.py` |

### Priorità P1 — Importanti (Fase 1.75)

| # | Finding | Azione | File coinvolti |
|---|---------|--------|----------------|
| 4 | F6 partial | Aggiungere intent "projecting" (variante indoor: limit bouldering) | `backend/engine/replanner_v1.py` |
| 5 | F10 partial | Aggiornare e2e_test_results.md: F10 è parziale, non FIXED | `docs/e2e_test_results.md` |
| 6 | NEW-F3 | Scheduling test sessions: aggiungere test_max_hang_5s a _SESSION_META e pool, creare test_power_endurance, scheduling periodico, aggiornamento assessment.tests | `backend/engine/planner_v2.py`, `backend/engine/macrocycle_v1.py`, catalogo sessioni |
| 7 | NEW-F4 | Ripple effect: dopo hard/max override, forzare giorno successivo a recovery | `backend/engine/replanner_v1.py` |

### Priorità P2 — Miglioramenti (Fase 1.75-2)

| # | Finding | Azione | File coinvolti |
|---|---------|--------|----------------|
| 8 | NEW-F1 | Arricchire prescription esercizi climbing con grado suggerito, volume, rest | `backend/catalog/exercises/v1/exercises.json`, resolver |
| 9 | NEW-F6 | Warning phase_mismatch nel replanner | `backend/engine/replanner_v1.py` |
| 10 | NEW-F7 | Finger compensation dopo override | `backend/engine/replanner_v1.py` |
| 11 | NEW-F8 | Aggiungere easy climbing nel pool deload (verificare con letteratura) | `backend/engine/macrocycle_v1.py` |
| 12 | NEW-F9 | Forzare almeno 1 finger_maintenance in fase PE | `backend/engine/macrocycle_v1.py` |

### Spunti da approfondire (non bloccanti)

| # | Tema | Dettaglio |
|---|------|-----------|
| A | Test assessment aggiuntivi | Aggiungere test oggettivi per technique e endurance (continuous climbing time, route-reading score) per ridurre dipendenza da proxy/self-eval |
| B | Altre dimensioni assessment | Valutare mobility/flexibility, mental game, contact strength come assi separati |
| C | Aggiornamento profilo nel tempo | Verificare e implementare che il closed loop aggiorni assessment.tests (non solo working_loads) dopo sessioni test |
| D | Deload vs letteratura | Confrontare struttura deload con Hörst, Lattice, Eva López — la deload attuale è probabilmente troppo leggera |
| E | Sessioni serali troppo corte | 4-5 esercizi per sessione serale vs 5-7 raccomandati da letteratura (B8) |
| F | Override intensity cap | Warning quando utente fa override con sessione di intensity superiore al cap della fase corrente |
| G | power_contact_gym scarsa | bench_press senza prescription, solo 4 esercizi per 1.5h — manca pulling, core |

---

## 5. Verdetto

### Il sistema è pronto per Fase 1.75?

**QUASI — serve un mini-cluster di fix P0 prima.**

Il macrocycle engine funziona nel caso standard (12 settimane, profilo reale, trip singolo). La pipeline assessment → macrocycle → planner → resolver → replanner produce output deterministic e ragionevole. 11/14 finding originali sono confermati risolti. 155 test verdi.

**Cosa blocca**:
1. **NEW-F2 (P0)**: esercizi climbing senza equipment_required — il resolver li piazza in palestre senza muro. Fix rapido: aggiungere `equipment_required` ai ~5-10 esercizi climbing. Nessuna modifica al codice engine.
2. **NEW-F5 (P0)**: durate fase negative con total_weeks < 9 — bug nel scaling che produce dati invalidi. Fix: validazione input + rispetto floor nel secondo scaling.
3. **NEW-F10 (P0)**: giorno partenza trip con sessione HARD — fix banale: includere start_date nel window pretrip.

**Stima**: i 3 fix P0 sono piccoli (1-2 ore totali, nessuna modifica architetturale). Dopo questi, si può procedere con Fase 1.75.

### Il sistema è pronto per Fase 2?

**NO — serve Fase 1.75 prima.** Le sessioni sono troppo corte (4-5 esercizi vs 5-7), manca climbing prescription strutturata (NEW-F1), manca scheduling test periodico (NEW-F3), e il ripple effect è troppo conservativo (NEW-F4). Tutti questi sono nel perimetro di Fase 1.75 + i fix P1 sopra elencati.

### Sequenza raccomandata

```
1. Mini-cluster fix P0 (NEW-F2, NEW-F5, NEW-F10) — pre-requisito
2. Fase 1.75 (B8 + fix P1 + fix P2 selezionati)
3. Fase 2 (tracking, feedback, outdoor)
```
