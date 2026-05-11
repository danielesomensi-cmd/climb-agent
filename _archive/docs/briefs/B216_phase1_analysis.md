# B216 — Phase 1 analysis

**Scope:** chiudere i due difetti identificati dall'audit D215.
- **Defect A** — cache `current_week_plan` che non si rinfresca al rollover di lunedì (`week.py:273-289`, ramo cache-hit).
- **Defect B** — `except Exception` troppo largo in `feedback.py:82-89` che inghiotte silenziosamente `ValueError` da `_find_day`.

**Modello usato:** Opus 4.7.
**Brief number:** **B216** (B214/B215 sono pre-riservati localmente per il refactor `progression_v1.py`, non committati). Verificato che il prossimo B libero in git è B214, ma due brief locali hanno già quei numeri → uso B216 per evitare collisioni.

**STOP gate:** dopo questo documento, aspetto *OK Phase 2* prima di qualunque modifica a codice.

---

## 1.1 Map the cache

### Due livelli di cache, stessa fonte di verità

La "current week plan" vive in due slot distinti dello stato:

| Slot | Tipo | Chiave di accesso | Intento originario |
|---|---|---|---|
| `state["current_week_plan"]` | singolo oggetto | fisso (top-level) | **legacy** — cache della settimana corrente prima di `week_plans` |
| `state["week_plans"][iso_date]` | dict | Monday-ISO della settimana | **per-week cache** introdotta con navigazione multi-settimana |

Entrambi possono puntare allo stesso oggetto Python o a copie divergenti. L'invariante implicito è: **se `is_current_week`, i due puntatori coincidono**.

### Writers

| # | Sito | Cosa scrive | Quando |
|---|---|---|---|
| W1 | `week.py:418` | `state["week_plans"][week_start_key] = week_plan` | sempre dopo generazione fresca |
| W2 | `week.py:420` | `state["current_week_plan"] = week_plan` | solo se `is_current_week` E generazione fresca |
| W3 | `replanner.py:87` (`persist_week_plan`) | `state["week_plans"][start_key] = updated` | sempre |
| W4 | `replanner.py:99` (`persist_week_plan`) | `state["current_week_plan"] = updated` | solo se `start_key == current_start` calcolato da macrocycle |
| W5 | `feedback.py:76` | `state["current_week_plan"] = week_plan` | **dentro il try** di `apply_events` → salta se ValueError |
| W6 | `feedback.py:81` | `state["week_plans"][start_key] = week_plan` | **dentro lo stesso try** → idem |
| W7 | `feedback.py:209-215` | entrambi gli slot, da `apply_adaptive_replan` | solo su `very_hard/fail` → rarissimo |
| W8 | `feedback.py:266` (`persist_week_plan` riuso) | vedi W3/W4 | sempre a fine handler |
| W9 | `onboarding.py` / `macrocycle.py` | assegnazione iniziale di entrambi | a onboarding/regen |
| W10 | `deps.py:62` (`invalidate_week_cache`) | `state["current_week_plan"] = None` | a regen/mutazioni strutturali |

### Readers

| # | Sito | Cosa legge | Criticità per B216 |
|---|---|---|---|
| R1 | `week.py:276-278` | `week_plans[key]` poi fallback `current_week_plan` | **root cause Defect A** — al cache-hit non riscrive W2 |
| R2 | `feedback.py:59` | `current_week_plan` per mark_done | **root cause Defect B** — se stale, `_find_day` tira ValueError |
| R3 | `feedback.py:148` | `current_week_plan` per persistere `actual_exercises` | stesso bug di R2 (silenzioso: loop non matcha e amen) |
| R4 | `feedback.py:176` | `current_week_plan` per stale-exercise guard (D172-04) | falso negativo silenzioso |
| R5 | `feedback.py:202` | `current_week_plan` per `check_adaptive_replan` | se stale, valuta una settimana sbagliata |
| R6 | `feedback.py:264` | `current_week_plan` come `final_plan` per `persist_week_plan` | `persist_week_plan` NON lo scrive in `current_week_plan` se `start_key ≠ current_start` → **Defect A persiste anche dopo il fix del feedback** |
| R7 | `state.py:PUT /api/state` | key allow-list (whitelist) | nessun impatto semantico |
| R8 | `free_session.py:431` | `current_week_plan` per mark-skipped auto-triggered | stesso bug di R2 |
| R9 | `weekly_override.py` | `current_week_plan` per ricalcolo | stesso bug di R2 |
| R10 | `report_engine.py` | `current_week_plan` per report | meno critico (report è best-effort) |

**Frontend:** `grep -r current_week_plan frontend/src` → **nessun hit**. Il frontend consuma `/api/week/{n}` (che ritorna `week_plan` dal cache-hit) e `/api/state` (JSONB intero, include `current_week_plan` ma nessun componente React lo legge). → Lo stale `current_week_plan` è **interamente backend-facing**.

### Staleness behavior (grafico di drift)

Scenario che ha morso Daniele il 2026-04-20:

```
Sat 2026-04-18 00:00 — state.current_week_plan.start_date = 2026-04-13
Sun 2026-04-19 14:14 — GET /api/week/9 force=false → cache miss → fresh generation
                       → week_plans["2026-04-20"] = plan9
                       → is_current_week == False (perché on 04-19 settimana corrente = 04-13)
                       → current_week_plan NON aggiornato
Mon 2026-04-20 00:00 — calendario avanza, macrocycle.current_week = settimana 04-20
                       (calcolo on-the-fly da start_date + weeks())
Mon 2026-04-20 ~12:40 — GET /api/week/0 (force=false)
                       → ctx["start_date"] = 2026-04-20, is_current_week = True
                       → cache HIT su week_plans["2026-04-20"] (generato ieri)
                       → week_plan = cached   ← ramo R1
                       ✗ state["current_week_plan"] NON viene riscritto
                       ✗ save_state NON chiamato
                       → HTTP 200 con il piano corretto per oggi
                       → MA state.current_week_plan ancora punta al piano 04-13
Mon 2026-04-20 12:49 — POST /api/feedback (Upper Body Antagonist)
                       → R2: current_week_plan.start_date = 2026-04-13
                       → apply_events(mark_done 2026-04-20) → _find_day → ValueError
                       → except:82-89 inghiotte → warning log → continua
                       → feedback_log.append OK
                       → working_loads update OK
                       → persist_week_plan(current_week_plan, …)
                         → scrive week_plans["2026-04-13"] (self)
                         → current_start (calcolato) = 2026-04-20
                         → start_key (04-13) ≠ current_start (04-20)
                         → NON riscrive current_week_plan
                       → save_state
Mon 2026-04-20 12:58 — frontend refetch /api/week/0
                       → cache HIT su week_plans["2026-04-20"]
                       → ma quel piano NON ha status=done (mark_done non ci è arrivato)
                       → UBA ancora "Planned"
```

**Apertura della finestra:** la prima `/api/week/0` di un lunedì (o qualsiasi giorno successivo al primo lunedì) in cui `week_plans[this_monday]` esiste già ma `current_week_plan.start_date` è rimasto al lunedì precedente.

**Chiusura naturale:** nessuna. Senza un force-regen (macrocycle regen via Settings) o un fresh-generation (cache miss) o un intervento scritto di `persist_week_plan` con `start_key == current_start`, la stale resta indefinita.

### Catena di causalità — cosa rompe cosa

- **Defect A (cache staleness)** → fa sì che tutti i reader `feedback.py:59/148/176/202/264` vedano la settimana sbagliata.
- **Defect B (except troppo largo)** → trasforma il ValueError sintomatico in un silent-skip.

I due difetti sono **composti, non ridondanti**. Fissare solo A: il feedback non arriva più al bug. Fissare solo B: il feedback crasha con 500 visibile invece di silent-skip → user-visible ma ancora rotto. **Va fatto entrambi.**

---

## 1.2 Map the except

### Blocco esatto (feedback.py:61-95)

```python
week_plan = state.get("current_week_plan")
if week_plan and target_date and target_sid:
    try:
        availability = state.get("availability")
        planning_prefs = state.get("planning_prefs")
        gyms = (state.get("equipment") or {}).get("gyms")
        week_plan = apply_events(
            week_plan,
            [{"event_type": "mark_done", "date": target_date, "session_ref": target_sid}],
            availability=availability,
            planning_prefs=planning_prefs,
            gyms=gyms,
        )
        state["current_week_plan"] = week_plan
        start_key = week_plan.get("start_date", "")
        if start_key:
            state.setdefault("week_plans", {})[start_key] = week_plan
    except Exception as e:
        logger.warning(
            "A194 mark_done inline skipped: %s (date=%r, sid=%r)",
            e, target_date, target_sid,
        )
```

### Cosa può tirare `apply_events`/`_find_day`

Path attraversato per `mark_done`: `apply_events → _apply_event (branch "mark_done") → _find_day(plan, target_date)`.

| Eccezione | Origine | Semantica |
|---|---|---|
| `ValueError` | `replanner_v1.py:143-146` | `target_date` non nella finestra del piano → **unico caso realmente "skippabile"** |
| `ValueError` | altri event types (override_day, …) | non in gioco qui (si passa solo mark_done) |
| `KeyError` | piano malformato (weeks[], days[] mancanti) | bug strutturale — **NON va ingoiato** |
| `TypeError` | `plan.get` su non-dict, etc. | bug strutturale — **NON va ingoiato** |
| `AttributeError` | idem | idem |

Oggi il blocco ingoia tutte e cinque con un log a livello WARNING. Significato operativo:

- Un ValueError da data-not-in-plan → silent-skip, DATA LOSS (mark_done perso, feedback persistito), user vede "UBA ancora Planned" ma crede di aver concluso.
- Un KeyError da piano malformato → idem, ma nasconde un bug nel generator → resta invisibile a monitoring.

### Fallback legittimo richiesto dal codice esistente

Il commento al clause dice:

> Non-fatal: apply_events may raise for edge cases (e.g. date not in plan).
> The legacy mark_done flow from /today already succeeded, so feedback still applies.

Traduzione: l'idea è che il frontend `/today` abbia **già** chiamato `/api/replanner/events` con lo stesso mark_done, quindi anche se qui fallisce, il mark_done è già atterrato nel per-week cache. **Ma questo assunto è violato al rollover di lunedì:** `/api/replanner/events` chiamato dal `/today` sta scrivendo contro `current_week_plan` anche lui (vedi `replanner_v1.py:_find_day` nello stesso path), stesso bug.

Verifica puntuale: **nessuno dei due path** ha un retry su `week_plans[target_monday]`. Il piano giusto c'è, nessuno lo guarda.

### Grep `except Exception` in `backend/api/routers/` — FLAG only

16 siti totali. Classificazione (non modifichiamo nulla in questo brief):

| Sito | Comportamento | Verdetto |
|---|---|---|
| `week.py:104` (_auto_resolve per-session) | log error, lascia session senza resolved | OK (fallback per-sessione) |
| `week.py:287` (cache read) | log warning, regenera | OK (difesa da cache corrotta) |
| `week.py:386` (week generation) | log error, raise 500 | OK |
| `week.py:399, 411` (preserve_completed, merge_prev) | log warning, usa piano fresh | OK (fallback benigno) |
| `macrocycle.py:86` | raise 422 | OK |
| **`feedback.py:82`** | **log warning, silent-skip** | **ROTTO — B216 Defect B** |
| `feedback.py:119, 131` | log error, raise 500 | OK |
| `session.py:80` | log error, raise 500 | OK |
| `onboarding.py:398, 436` | save_state + raise 422 | OK |
| `replanner.py:39, 58, 159, 249` | best-effort metadata fallback | OK (catalog I/O) |
| `replanner.py:198, 237, 284, 331` | log error, raise 500 | OK |
| `assessment.py:30` | raise 422 | OK |

**Conclusione §1.2:** unico sito problematico da sistemare in B216 è `feedback.py:82`. Tutti gli altri o sollevano HTTPException (utente informato) o sono degradazioni legittime. Non tocco gli altri — brief B216 resta single-purpose.

---

## 1.3 Propose the fix

### Defect A — cache staleness

**Opzioni valutate:**

- **Opt-1 "Invalidate on read":** al cache-hit in `week.py:279-286`, se `is_current_week`, riscrivi `state["current_week_plan"] = cached` e `save_state`. Costo: 1 save_state extra per ogni `/api/week/0` che è cache-hit su piano già corretto (che è la maggioranza dei casi). Non serve.
- **Opt-2 "Ditch current_week_plan":** rimuovi del tutto lo slot legacy, tutti i reader usano `week_plans[macrocycle.today_monday]`. Tocca ~15 siti (feedback.py ×5, free_session.py, weekly_override.py, report_engine.py, …) + shape di `/api/state`. **Fuori scope B216.**
- **Opt-3 "Narrow self-heal" (RACCOMANDATO):** al cache-hit, se `is_current_week` E `state.current_week_plan.start_date != cached.start_date`, allora riscrivi e save. Zero costo a regime; auto-heal quando rileva drift. Fire solo al primo `/api/week/0` del lunedì (o primo dopo drift).

**Codice proposto (week.py, ramo cache-hit):**

```python
if (
    cached
    and cached.get("start_date") == week_start_key
    and cached.get("weeks")
    and len(cached["weeks"]) > 0
    and cached["weeks"][0].get("days")
):
    week_plan = cached
    # B216: self-heal del legacy current_week_plan quando il calendario
    # avanza (lunedì rollover) e il cache-hit conferma che la per-week
    # cache è corretta. Senza questo, feedback.py e altri reader del
    # current_week_plan continuerebbero a vedere la settimana precedente.
    if is_current_week:
        legacy = state.get("current_week_plan") or {}
        if legacy.get("start_date") != week_start_key:
            state["current_week_plan"] = cached
            save_state(state, user_id)
```

- **Idempotente:** se già sincronizzato, il branch `if` non scatta.
- **Non tocca il piano:** riassegna il puntatore, non muta `cached`.
- **Non viola past-immutability:** nessun `session.status` viene toccato; il piano cached era appena stato generato al giorno prima ed è già intatto.
- **Invariante di ripristino:** dopo il fix, se il calendario avanza, la prima `/api/week/0` del giorno corrente chiude automaticamente il gap.

**Side effect check (per sicurezza):**
- `persist_week_plan` (replanner.py:90-99) calcola `current_start` da macrocycle — stessa logica di `is_current_week` nel week router? Quasi: il router usa `_current_week_num(macrocycle)`, persist usa `current_phase_and_week(macrocycle)`. Da Phase 2 verifico che producano la stessa data per il lunedì corrente. Se non è vero, abbiamo un altro bug ma fuori scope — loggo come finding per D217.

### Defect B — broad except

**Proposta:** restringi a `ValueError` e aggiungi un secondo tentativo esplicito su `week_plans[target_monday]` prima di rinunciare.

```python
try:
    ...
    week_plan = apply_events(week_plan, [...], ...)
    state["current_week_plan"] = week_plan
    start_key = week_plan.get("start_date", "")
    if start_key:
        state.setdefault("week_plans", {})[start_key] = week_plan
except ValueError as e:
    # B216 Defect B: _find_day raises ValueError when target_date is
    # outside the plan window (tipicamente quando current_week_plan è
    # stale e il piano per target_date vive in week_plans[target_monday]).
    # Prima di rinunciare, ritenta contro il piano indicizzato per data.
    target_monday = _monday_for_date(target_date)  # helper nuovo in feedback.py
    alt_plan = (state.get("week_plans") or {}).get(target_monday)
    if alt_plan:
        try:
            alt_plan = apply_events(alt_plan, [{
                "event_type": "mark_done",
                "date": target_date,
                "session_ref": target_sid,
            }], availability=availability, planning_prefs=planning_prefs, gyms=gyms)
            state.setdefault("week_plans", {})[target_monday] = alt_plan
            # Se è la settimana corrente, riallinea anche il legacy slot
            if alt_plan.get("start_date") == target_monday:
                macrocycle = state.get("macrocycle") or {}
                mc_start = macrocycle.get("start_date")
                if mc_start and _is_current_monday(mc_start, target_monday):
                    state["current_week_plan"] = alt_plan
            logger.info(
                "B216: mark_done landed in week_plans[%s] (current_week_plan was stale)",
                target_monday,
            )
        except ValueError as e2:
            logger.warning(
                "B216: mark_done skipped — date not in primary or alt plan: %s (date=%r, sid=%r)",
                e2, target_date, target_sid,
            )
    else:
        logger.warning(
            "A194 mark_done inline skipped: %s (date=%r, sid=%r)",
            e, target_date, target_sid,
        )
```

**Helper nuovi (privati a feedback.py):**
- `_monday_for_date(iso_date: str) -> str`: ritorna il lunedì ISO della settimana di `iso_date`. Due righe usando `datetime.fromisoformat().weekday()`.
- `_is_current_monday(mc_start: str, candidate_monday: str) -> bool`: true sse `candidate_monday` è la settimana corrente del macrocycle. Riusa `current_phase_and_week` da `api.deps`.

**Eccezioni non-ValueError** (KeyError, TypeError, AttributeError): **non catturate**. Si propagano al gestore outer di FastAPI → HTTP 500. Questo è un cambio di comportamento voluto: un piano malformato oggi silenzia, domani genera un 500 visibile → monitoring lo vede, noi lo fissiamo. Nessun utente si trova con dati persi silenziosamente.

**Past-immutability check:**
- `apply_events(alt_plan, [mark_done])` cambia solo `session.status="done"` sulla sessione target. Non tocca `exercise_id`, `actual_exercises`, `feedback`, `resolved`. Conforme al principio non-negoziabile di CLAUDE.md.
- Il target è `target_date = 2026-04-20` (giorno corrente) quando il bug scatta. Non è una sessione passata.

**Rollback:** se Defect B fix genera noise (KeyError inattesi in produzione che prima erano silenziati), revert singolo del commit Defect B lasciando Defect A in produzione. Fix A da solo già chiude il sintomo principale per utenti futuri.

### Perché serve il doppio fix (e non solo A)

Fix A da solo copre solo il path `GET /api/week/0` come trigger di re-sync. Non copre:
- Utenti che non visitano `/today` prima di submittare un feedback (es. PWA aperta da notifica).
- Race condition tra la renderizzazione di `/today` e il POST `/feedback` — se il POST parte prima che l'aggiornamento del cache sia persistito (networking parallelo, offline queue).
- Navigazioni via deep-link.

Fix B è la cintura di sicurezza: indipendentemente da come `current_week_plan` sia arrivato stale, il mark_done trova comunque la casa corretta.

---

## 1.4 Regression test plan

File nuovo: `backend/tests/test_week_rollover_B216.py`. Usa `TestClient` + `STORAGE_BACKEND=file` + fixture isolata per utente. Sei test, numerati T1..T6.

### T1 — cache-hit refreshes current_week_plan on calendar advance

**Intento:** Defect A behavior spec. Setup: macrocycle con `start_date = this_monday - 2 settimane`, `week_plans[prev_monday]` già popolato, `week_plans[this_monday]` già popolato (pre-generato), `state["current_week_plan"].start_date = prev_monday`. Chiamata: `GET /api/week/0`. Asserzione:
- risposta 200
- `response["week_plan"]["start_date"] == this_monday`
- dopo la chiamata, `load_state(user).current_week_plan.start_date == this_monday`
- `week_plans` intatto (entrambe le chiavi presenti, strutture uguali)

File rationale: tests dedicato al rollover — separato da `test_a194_feedback_atomic.py` (che copre altri invariants) per chiarezza.

### T2 — cache-hit is no-op when current_week_plan is already fresh

**Intento:** il self-heal non save-spamma. Setup: `current_week_plan.start_date == this_monday` già. Mock `save_state` per contare chiamate. Asserzione:
- `GET /api/week/0` non chiama `save_state` nel ramo cache-hit (0 chiamate in quel branch).
- Piano ritornato identico.

### T3 — feedback on target_date outside current_week_plan falls back to week_plans[target_monday]

**Intento:** Defect B happy path. Setup replica Daniele: `current_week_plan.start_date = prev_monday`, `week_plans[this_monday]` contiene una sessione `upper_body_weights` pianificata per `this_monday`. POST `/api/feedback` con `log_entry.date=this_monday, session_id=upper_body_weights, exercise_feedback_v1=[{id, feedback:"ok"}]`. Asserzione:
- risposta 200
- `state.week_plans[this_monday].weeks[0].days[0].sessions[0].status == "done"`
- `state.session_completion_log[-1].session_id == "upper_body_weights"` e `date == this_monday`
- `state.feedback_log[-1].session_id == "upper_body_weights"`

### T4 — feedback with malformed plan propagates (non-ValueError no longer swallowed)

**Intento:** Defect B — restringere il catch non deve regredire il comportamento di resilienza, MA un KeyError strutturale non va più ingoiato. Setup: inietta un piano malformato in `current_week_plan` (es. `weeks` al posto di `weeks[]`, o `days` assenti). POST `/api/feedback`. Asserzione:
- risposta 500 (non silent-skip)
- `session_completion_log` **non modificato** (nessun feedback persistito a fronte di stato corrotto)
- log contiene l'errore con stack trace

**Nota:** questo test codifica il cambio di comportamento ✨ — voglio l'OK esplicito di Daniele su questo prima del merge. Se preferiamo "graceful degradation su piano malformato", switcho a un fallback che logga + 500 ma persiste comunque il feedback_log. Scelta di default: 500 + nessun persist, perché se il piano è corrotto non possiamo fidarci dello stato per nessuno scopo.

### T5 — past-session immutability under rollover fix

**Intento:** CLAUDE.md non-negotiable. Setup: `week_plans[prev_monday]` contiene una sessione `done` con `feedback_summary`, `actual_exercises`, `completed_at`. Trigger: `GET /api/week/0` al lunedì successivo (self-heal di T1). Asserzione:
- tutti i campi della sessione done in `week_plans[prev_monday]` **bit-for-bit identici** (json.dumps deterministico).
- idem per qualunque sessione in `current_week_plan` se punta ancora a `prev_monday` prima del self-heal.

### T6 — end-to-end Daniele scenario replay

**Intento:** golden-path integration. Replica la sequenza esatta del trace D215:
1. Setup stato snapshot-like (current_week_plan=prev_monday, week_plans[this_monday] popolato con UBA pianificato).
2. GET /api/week/0 → verifica piano UBA ritornato, verifica self-heal (T1 subset).
3. POST /api/feedback per UBA su this_monday con exercise_feedback_v1 realistico (10 items, difficulty "ok").
4. Verifica:
   - `session_completion_log[-1]` — done, this_monday, UBA, `completed_at` presente
   - `feedback_log[-1]` — entry completa, `exercise_count=10`
   - `working_loads.entries[*].updated_at == today` per almeno 1 entry legata all'UBA
   - `week_plans[this_monday].weeks[0].days[*].sessions[*].status == "done"` dove session_id="upper_body_weights"
   - `current_week_plan.start_date == this_monday` (self-heal + post-feedback state)
5. GET /api/week/0 di nuovo (refetch post-mutation) → UBA `status="done"`, niente regression.

File rationale: E2E test, vive nel nuovo file T1..T5 vicino, perché è lo "smoke test" del brief.

### Fuori scope B216 (non inclusi in questo file di test)

- Multi-user race condition (due device lo stesso account, submit concorrenti) → D218 futuro.
- Pre-esistenti path che usano `current_week_plan` (`free_session.py:431`, `weekly_override.py`, `report_engine.py`): stessa vulnerabilità R8-R10, ma fuori dallo scope B216. Le flag in findings.md §5 "Follow-ups" per D217.
- Persistenza negli spelling edge-case di `target_date` (timezone, formato): già coperto da test esistenti (`test_a194_feedback_atomic.py`).

### Totale test nuovi: 6

Conteggio atteso post-brief: 1721 → 1727. Aggiorno `sync_status.py` nel commit finale.

---

## 2. Commit plan (proposto)

| # | Subject | File | Tests run |
|---|---|---|---|
| 1 | `B216: self-heal current_week_plan at cache hit (Defect A)` | `backend/api/routers/week.py` + test T1, T2, T5 | full suite |
| 2 | `B216: narrow feedback mark_done except + week_plans fallback (Defect B)` | `backend/api/routers/feedback.py` + test T3, T4 | full suite |
| 3 | `B216: integration test for Daniele rollover scenario` | test T6 | full suite |
| 4 | `B216: close in ROADMAP_CURRENT` | `docs/ROADMAP_CURRENT.md` | — |
| 5 | `sync: test count 1721 → 1727 after B216` | counters files | — |

Tre commit funzionali + due commit doc (regola CLAUDE.md su sync/counter commits senza brief ID nel subject). Push diretto a main (backend-only, nessun frontend touched).

---

## 3. Scope flags per Daniele

Due cose dove prendo una decisione esplicita — approva o reindirizza:

1. **Fix A è un self-heal nel cache-hit del router, NON un refactor di `current_week_plan`.** L'unificazione dei due slot cache (current_week_plan vs week_plans[start_date]) è un brief più grande, da D217 se lo vogliamo. B216 si limita a chiudere il bug segnalato senza toccare contratti esterni.

2. **T4 codifica un cambio di comportamento osservabile:** piano malformato → HTTP 500 invece di silent-skip. Questo è un lieve regression-risk se esistono legacy plans corrotti in produzione che oggi funzionano per casualità. Due alternative:
   - (a) **Strict (default):** come proposto, 500 su non-ValueError. Monitoring vede, noi fissiamo.
   - (b) **Graceful:** tengo il catch largo ma differenzio il log level (ERROR per non-ValueError, WARN per ValueError-atteso).

   Preferenza mia: (a). Se preferisci (b) lo implemento in 5 righe e T4 diventa "non-ValueError logged as ERROR".

---

## 4. STOP — await OK Phase 2

Riepilogo azioni pending prima del merge:

- [ ] Phase 2: implementare fix A in `week.py:279-289`
- [ ] Phase 2: implementare fix B in `feedback.py:61-95` con helper `_monday_for_date` + `_is_current_monday`
- [ ] Phase 2: scrivere `backend/tests/test_week_rollover_B216.py` con T1..T6
- [ ] Phase 3: `python -m pytest backend/tests -q` → 1721→1727 PASS
- [ ] Phase 3: diff summary + ROADMAP_CURRENT close + sync_status
- [ ] Commit + push a main
- [ ] Solo dopo: archiviare snapshot D215 (decisione tua)

**Risponde con una delle:**

- **"OK Phase 2"** → procedo come specificato (T4 strict, Fix A opt-3, tre commit funzionali).
- **"OK Phase 2, T4 graceful"** → procedo con l'alternativa (b) per il catch non-ValueError.
- **"Re-scope / split / defer"** → dimmi cosa cambiare.
