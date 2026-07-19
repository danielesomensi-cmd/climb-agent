# D252 — Step-0 Foundation Audit (outdoor shape + custom-session load + E2E health)

**Tipo**: D (audit, read-only). Nessuna modifica al codice.
**Data**: 2026-07-19
**Contesto**: la feature "Adhoc Coach Sessions" verrà costruita sopra `custom_session`. Prima di scrivere qualsiasi brief, verifica che la fondazione funzioni davvero.

---

## Verdetto sintetico

| Sez. | Item | Esito |
|---|---|---|
| **A** | BUG-1 outdoor shape | ✅ **PASS** — chiuso |
| **B** | Custom-session load → 4 superfici | ✅ **PASS** — tutte e 4, no doppi conteggi |
| **C.1** | Catalog visibility | ✅ PASS (caveat under-filter) |
| **C.2** | Load history | ❌ **FAIL** |
| **C.3** | Load proposal | ❌ **FAIL / assente** |
| **C.4** | Timers & logging | ⚠️ **PARTIAL** — timer ok, logging per-esercizio assente |
| **C.5** | Immutability | ✅ PASS (meccanismo) / ⚠️ test coverage mancante |

**La fondazione regge sul piano dati (load accounting corretto e immutabile), ma è cieca sul piano "apprendimento carichi": una custom session non propone carichi, non mostra lo storico, e non logga nulla a livello di esercizio.** Questi tre buchi (C.2/C.3/C.4) sono esattamente ciò su cui una "coach-driven adhoc session" dovrebbe costruire — e oggi non ci sono. Non bloccano un v0 conversazionale, ma sono prerequisiti reali per un v1 credibile. BUG-1 invece è già chiuso: nessun brief necessario.

---

## Sezione A — Forma di persistenza outdoor → PASS, BUG-1 chiuso

Ogni writer che scrive un giorno outdoor sul week plan usa i **campi flat `outdoor_*` direttamente sul dict del giorno** — la forma esatta che il coach legge in `prompt_builder.py:244-266` (`_day_extras`). Nessun path crea una outdoor session annidata dentro `day["sessions"]`.

| # | Path | file:line | Forma |
|---|------|-----------|-------|
| 1 | Planner riserva giorno outdoor | `planner_v2.py:1417-1418` | flat `outdoor_slot=True` |
| 2 | Replanner `add_outdoor` | `replanner_v1.py:998-1002` | flat `outdoor_spot_name/discipline/status` |
| 3 | `complete_outdoor` | `replanner_v1.py:1008,1012` | flat `status="done"` + `outdoor_load_score` |
| 4-5 | `undo_/remove_outdoor` | `replanner_v1.py:1070,1077` | flat |
| 6 | Override "converti in outdoor" | `replanner_v1.py:1538-1542` | **svuota `sessions=[]`** poi setta flat — non crea mai session object |
| 7 | Sync log manuale (B277) | `outdoor.py:90-116` | passa per `apply_events` → writer #2/#3 → flat |
| 8 | Merge settimana prec. | (test `test_merge_prev_week.py:349-457`) | preserva flat |

Reader `_plan_days` (`prompt_builder.py:226-241`) tollera sia `plan["days"]` legacy sia `plan["weeks"][0]["days"]`. Il path di override **svuota esplicitamente `day["sessions"]` prima** di settare i campi flat, quindi è strutturalmente impossibile produrre una forma annidata che il coach leggerebbe come "rest".

**Correzione al brief precedente:** il coach prompt builder vive in `backend/coach/prompt_builder.py` (non `backend/api/`), e non esiste un campo stringa `outdoor_slot` oltre al marker booleano. Il prerequisito "fix BUG-1" del feature Adhoc Coach non serve: è già chiuso.

---

## Sezione B — Custom-session load accounting → PASS su tutte e 4 le superfici

**Calcolo/salvataggio:** `compute_custom_session_load` (`custom_session.py:8-11`) = `round(min(85, Σ fatigue_cost × 1.5))` — **stessa formula** del resolver catalogo (`resolve_session.py:1961`). Salvato come **`estimated_load_score`** sul template (`custom_session.py:79`) e copiato sull'entry del giorno all'inserimento (`replanner_v1.py:1264`), con `is_custom:True`, `session_id="custom_{id}"`.

**Lock:** la custom session **non ha mai `session_load_score`** perché `_auto_resolve` salta gli `is_custom` (`replanner.py:119-122`). Il load è **congelato all'add-time e mai ricalcolato**. Finish = solo `mark_done` (`feedback.py:95-105`), nessun ricalcolo. Sopravvive alla rigenerazione se `status="done"` (`_is_preservable`, `replanner_v1.py:513-519`). Modifica successiva del template (PUT) **non** retro-propaga sull'istanza già piazzata (copia by-value). Lock robusto; meccanismo diverso da outdoor (che locka al finish) ma esito equivalente.

| Superficie | Esito | Evidenza |
|---|---|---|
| a. `report_engine` week total | ✅ PASS | `report_engine.py:257-261` somma `session_load_score or estimated_load_score` per ogni sessione `done`, nessun filtro `is_custom` |
| b. `week-progress-bar` `doneLoad` | ✅ PASS | custom ha `session_id` → in `allSessions`; `doneSessionLoad` usa il fallback `?? estimated_load_score` (`:31-35,50`) |
| c. Week header | ✅ PASS | `week/page.tsx:731-741` stesso fallback |
| d. Today | ✅ PASS | eredita `WeekProgressBar` (`today/page.tsx:1077`) |

Nessun doppio conteggio (le custom vivono solo in `day["sessions"]`, non in outdoor/free/other stores). **Rischio latente (non bug):** la coerenza dipende interamente dal fallback `?? estimated_load_score` — una futura superficie che legga solo `session_load_score` mostrerebbe **0** per le custom.

---

## Sezione C — Custom-session E2E health

### C.1 Catalog visibility → PASS
`GET /api/custom-session/exercises` restituisce **tutti i 242** di default (`custom_session.py:117-118`). I filtri (`q`, `domain`, `equipment`) sono **opt-in via query param**, assenti di default. Nessun filtro nascosto su `active`/`category`/`age`/`experience`.
**Caveat (under-filter):** l'unico esercizio `active:False` (`max_hang_10s`) **non** viene escluso → selezionabile. [LOW]

### C.2 Load history → FAIL
Zero riferimenti a `working_loads`/`load_history`/`baseline` nel path custom-session (backend). `working_loads` esiste in user_state ed è usato altrove (progression, guided player `guided/.../page.tsx:446`) ma **la build custom non lo legge**. Riproponendo un esercizio, nessun carico passato viene mostrato. La response picker espone `prescription_defaults`/`load_model` ma nessun valore utente.

### C.3 Load proposal coherence → FAIL / assente
`_build_session` (`custom_session.py:60-81`) calcola solo `estimated_load_score` e durata; **non deriva `load_kg` per esercizio**. `load_kg` arriva dal request con **default 0** (`models.py:371`); i blocchi warmup/cooldown **hardcodano `"load_kg":0`** (`custom_session.py:223`) pur leggendo `prescription_defaults` per set/rep. Carico non proposto, non derivato da `load_model` né da storico, non coerente. Il player mostra il carico read-only solo se >0.

### C.4 Timers & logging → PARTIAL
Le custom **non** passano dal guided player: hanno un **player dedicato** (`session-builder/[id]/play/page.tsx`, via `GET /api/custom-session/{id}`).
- **Timer: OK** — countdown+auto-advance (`custom-exercise-step.tsx:98-117`), rest timer, wake-lock, duration tracking.
- **Logging: MANCANTE [HIGH]** — `handleFinish` (`play/page.tsx:205-243`) invia **solo `mark_done`**. Nessun feedback per-esercizio, nessun carico usato, nessun RPE, nessuna durata persistiti. `CustomExerciseStep` non ha input carico/RPE. Il guided player invece logga ricco `exercise_feedback_v1` (`guided/.../page.tsx:330-438`). Completare una custom produce **zero dati a livello esercizio** — compounda direttamente C.2.

### C.5 Immutability → PASS meccanismo / test mancante
POST `/api/custom-session` fa **append** su `state["custom_sessions"]` separato (`custom_session.py:269-271`), non tocca il week plan. L'inserimento nel piano è l'evento `add_custom_session` che fa **append** a `day["sessions"]` con id proprio `custom_{id}` (`replanner_v1.py:1211-1278`), con guard anti-conflitto slot (`:1243-1251`), senza toccare sessioni sorelle. `_DAY_LEVEL_FIELDS` non è coinvolto in questo path.
**Coverage:** `test_a207_...:130-161` verifica il no-ripple (closest). **MANCA** un test che asserisca direttamente che `exercise_id`/loads/status di sessioni esistenti/passate restano invariati dopo un insert custom, e che il POST lasci il piano intatto. [MED]

---

## Gap list per severità (input per brief futuri — non scritti)

- **[HIGH] Logging per-esercizio assente nelle custom** — solo `mark_done`, nessun carico/RPE/durata persistiti. Blocca ogni futuro tracking carichi coach-driven.
- **[HIGH] Nessuno storico carichi (`working_loads`) letto né scritto** dal path custom.
- **[MED] Nessuna proposta di carico** — `load_kg` default 0, blocchi hardcodati a 0, `load_model`/`prescription_defaults` non applicati.
- **[MED] Test immutability custom-session mancante** — meccanismo sano ma non presidiato.
- **[LOW] `active:False` non filtrato** dal picker (`max_hang_10s`).
- **[LOW] Due player divergenti** (guided ricco vs custom povero) → rischio drift.

---

## Implicazione per il feature Adhoc Coach

La fondazione "load accounting + immutability" è solida e riusabile (Sezione B, C.5). Ma le tre feature che rendono utile un adhoc builder — **proporre un carico, ricordare lo storico, loggare cosa hai fatto** (C.2/C.3/C.4) — oggi **non esistono** in `custom_session`. Un v1 serio deve chiudere almeno il logging per-esercizio (HIGH) prima di poter "imparare i carichi". BUG-1 (Sezione A) è già chiuso.
