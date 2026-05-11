# A-ACTIVATION-TIMING — Phase 0 discovery

**Tipo:** A (feature, fase 0 read-only)
**Data:** 2026-04-17
**Stato:** Phase 0 completa — **STOP gate attivo**
**Commit di diagnosi a monte:** `a973329` (D-ANALYTICS-DROPOFF, 75% drop-off a stage 4)

---

## Contesto

D-ANALYTICS-DROPOFF ha mostrato che 6 utenti su 8 (75%) completano l'intero onboarding — profilo, assessment, goal, macrociclo, settimana pianificata — ma **non aprono mai una singola sessione**. Il wizard funziona; la rottura è nel momento *subito dopo*.

Questo brief mappa ciò che succede fra "Generate Plan" e la prima sessione, per capire dove l'utente si perde e quali leve sono realmente disponibili. Phase 0 è **discovery pura**, read-only, e si chiude con uno STOP gate: nessuna riga di codice viene scritta prima dell'OK esplicito di Daniele.

---

## §1 — Review → plan generation flow map

File: `frontend/src/app/onboarding/review/page.tsx`

Il bottone finale del wizard ha **due varianti**, entrambe nello stesso componente:

| Azione UI | Funzione | Flag POST | Redirect |
|-----------|----------|-----------|----------|
| "Generate Plan" | `handleGenerate` (L130–152) | — | `/onboarding/start-week` |
| "Start with test week" | `handleTestWeek` (L154–176) | `test_week_requested: true` | `/plan` |

Entrambi chiamano lo stesso endpoint `POST /api/onboarding/complete`. La differenza è solo il flag e la destinazione.

`/onboarding/start-week` (file `frontend/src/app/onboarding/start-week/page.tsx`):

- Linea 65–78 `handleContinue`:
  - se `offset > 0` chiama `setStartWeek(offset)` (shift all'indietro del `start_date` del macrociclo)
  - poi **sempre** `router.push("/subscribe")` — senza controllo sullo stato subscription dell'utente
  - anche il bottone "Skip" (L107–114) va a `/subscribe`

Conseguenza: dopo "Generate Plan", l'utente vede lo step "where do you want to start?" e poi **inevitabilmente** la paywall — anche se è il beta-tester già bypassato o l'utente già in trial. Questo è coerente con la sensazione di "paywall-first" di cui Daniele ha accennato, ed è un pezzo del motivo per cui l'utente a stage 4 non arriva mai alla prima sessione: non finisce su `/today`, finisce su `/subscribe`.

Backend: `backend/api/routers/onboarding.py` L380–394:
- L380–381: se `test_week_requested` allora `state["initial_tests_requested"] = True`
- L385: `start = next_monday()` — **sempre** lunedì successivo, indipendentemente dalla data corrente o dal flag test-week
- L386–394: `generate_macrocycle(goal, profile, state, start, total_weeks)`

---

## §2 — Test week semantics

File: `backend/api/routers/week.py` L300–312

```python
today_str = datetime.now().strftime("%Y-%m-%d") if is_current_week else None
effective_preserve = preserve_before or today_str
...
want_tests = (
    state.get("initial_tests_requested")
    and ctx.get("is_first_week_of_phase")
    and ctx["phase_id"] == "base"
    and not is_last
)
```

**Fatto chiave:** la "test week" **non è una settimana aggiuntiva**. Viene iniettata come Week 1 del macrociclo (Pass 3 del planner in `planner_v2.py`) quando:
- `initial_tests_requested == True`
- è la prima settimana della fase base
- non è l'ultima settimana (evita overlap con deload)

Quindi:
- il conteggio totale di settimane del macrociclo è invariato (10–13)
- "start with test week" significa "Week 1 = test sessions invece di sessioni di allenamento normali"
- `generate_test_week()` in `planner_v2.py` L1504 esiste ma è **dead code** in produzione: chiamato solo da test pytest, nessun router lo invoca

Implicazione per le opzioni UX: non esiste oggi un concetto di "settimana prima della Week 1" — il macrociclo è strutturalmente `[Week 1, Week 2, …]` a partire da `start_date` (lunedì).

---

## §3 — Monday invariant analysis

File: `backend/api/deps.py` L205–231

Tre helper disponibili:

| Helper | Comportamento | Uso attuale |
|--------|---------------|-------------|
| `ensure_monday(d)` | Arrotonda `d` al lunedì precedente (422 se formato invalido) | Validation gate |
| `next_monday(from_date)` | Se `from_date` è già lunedì ritorna `from_date`, altrimenti lunedì successivo | `onboarding.py` L385 (prod) |
| `this_monday(from_date)` | Lunedì della settimana corrente (guarda indietro) | Docstring esplicita: "so that a macrocycle can start immediately (partial first week)" — **presente ma non ancora usato in onboarding** |

### §3a — Iniettare test sessions su giorni *prima* dello start_date

**Strutturalmente bloccato.**

- `planner_v2.py` L693 costruisce esattamente **7 giorni forward** a partire da `start_date`. Non c'è slot dati per sessioni pre-start.
- `planner_v2.py` L639–643: auto-corregge qualsiasi `start_date` non-lunedì al lunedì precedente, logga warning. Se passi un giovedì, il planner lo rewinda al lunedì di quella settimana — non genera una "mezza settimana".
- `macrocycle_v1.py` L540–656: stessa logica di allineamento settimanale. `phase_start_date = start + timedelta(weeks=current_week - 1)` — strict week alignment, niente settimane frazionarie.

Per implementare questa strada servirebbe uno dei seguenti, tutti invasivi:
1. Aggiungere un concetto di "Week 0 / prelude" al modello dati (non esiste)
2. Spostare `start_date` indietro e marcare giorni passati come "già perduti" (equivale all'opzione §3b)
3. Disaccoppiare le test session dal macrociclo (popolare un log parallelo — nuovo modulo, regression risk su progressione/closed-loop)

**Verdict §3a:** high risk, tocca `planner_v2.py` + `macrocycle_v1.py` + schema state. Richiede STOP protocol completo (high-risk modules).

### §3b — `start_date = this_monday()` invece di `next_monday()`

**Infrastruttura già quasi pronta.**

Esiste già:
- `this_monday()` in `deps.py` (L224, con docstring che menziona "partial first week")
- `planner_v2.py` ha già il parametro `today` (L689–690 `today_date = _parse_date(today) if today else None`) che viene passato da `week.py` L300–301 quando `is_current_week=True`
- `planner_v2.py` L757–760 (commento `# B95: skip past days`): già salta i giorni precedenti a `today` quando genera la settimana corrente. Quindi se `start_date` è il lunedì appena passato e oggi è giovedì, lun-mer vengono marcati non disponibili e la settimana viene riempita su gio-dom.

Rischi da verificare in Phase 1 (non da risolvere in Phase 0):
- `progression_v1.py` e `closed_loop_v1.py`: contatori sessione-per-fase sono robusti a settimane parziali?
- `current_phase_and_week()`: consumer che calcola "siamo in Week 3 fase strength_power" — funziona se la prima settimana aveva solo 3 giorni utilizzabili?
- Flow di rigenerazione (`POST /api/macrocycle/generate`): l'utente che rigenera in mezzo alla settimana deve ottenere `this_monday` o `next_monday`? Probabilmente `this_monday` solo nella generazione iniziale da onboarding, per non retro-riscrivere settimane passate (vedi invariante "past sessions are immutable" in CLAUDE.md).
- Reports weekly/monthly: i range si basano su lunedì canonici — già compatibili.

**Verdict §3b:** medium risk. La variazione di codice è piccola (una riga in `onboarding.py`), ma richiede test mirato sulle proprietà di progressione. Tocca `onboarding.py` (low-risk) ma con implicazioni su moduli high-risk (`planner_v2`, `macrocycle_v1`) — serve analisi protocol STOP prima di toccare la riga.

---

## §4 — Today empty state

File: `frontend/src/app/(main)/today/page.tsx`

Due empty state oggi:

1. **Piano esiste ma nessuna sessione oggi** (L1017–1037, gate `dayPlan && sessions.length === 0`):
   - Copy: "No sessions today" + eventuale riga "Preview next training day: {weekday}"
   - CTA: `<Link href={`/today?date=${nextTrainingDay.date}`}>Preview next training day: {weekday}</Link>` — **un link testuale, grigio, nessun bottone primario**

2. **Nessun piano per questa data** (L1038–1055, gate `!dayPlan && weekPlan`):
   - Copy: "No plan found for this date"
   - CTA: stesso link "Preview next training day", identico visivamente

Logica `nextTrainingDay` (L350–352):
```ts
const nextTrainingDay = weekPlan?.days.find(
  (d) => d.date > targetDate && d.sessions.length > 0
);
```

Limitazioni:
- Guarda solo **dentro la settimana corrente** (`weekPlan.days`). Se l'utente è a venerdì e la settimana è già finita, `nextTrainingDay` è `undefined` → nessun CTA → empty state "No sessions today" con nient'altro.
- Non mostra alcun dettaglio della prossima sessione (tipo, durata, esercizi principali) — solo il weekday.
- Stilisticamente è una link-text, non un CTA primario. L'utente nuovo arriva su `/today`, vede "No sessions today" grigio, e non ha un'istruzione visiva forte su *cosa fare ora*.

È esattamente il "CTA troppo debole" ipotizzato da D-ANALYTICS-DROPOFF.

---

## §5 — /guided preview mode

File: `frontend/src/app/(guided)/guided/[date]/[sessionId]/page.tsx` L88–113

Comportamento attuale:
- Al mount chiama `loadState(date, sessionId)` da localStorage
- Se `null` → `router.replace('/today?date=${date}')`
- Lo state viene scritto in localStorage da `session-card.tsx` L260–299 (`handleStartGuided`) quando l'utente clicca "Start" su una sessione resolved

**Nessuna modalità preview.** Per ogni "mostra all'utente come sarà la prossima sessione prima di iniziarla", oggi non c'è nulla di pronto. Le strade possibili (non da implementare ora):
1. Pre-caricare lo state in localStorage e aprire `/guided` come fosse una sessione reale (rischio: stato zombie se l'utente non completa)
2. Aggiungere un query param `?preview=true` che disabilita il completion tracking in `/guided` (nuovo codice, edge cases)
3. Creare una card inline su `/today` che mostri la prossima sessione resolved — niente preview route, solo summary visuale (più economico, meno potente)

La strada 3 è la più sicura: nessuna modifica a `/guided`, solo UI nuova su `/today`.

---

## §6 — Email / scheduler infrastructure

**Nessuna infrastruttura presente.**

Verifiche:
- `requirements.txt`: solo librerie web/data (fastapi, supabase, stripe, pydantic, …). **Nessuna** libreria email (resend, sendgrid, smtplib use, postmark).
- `Procfile`: un unico processo `web: uvicorn backend.api.main:app …`. **Nessun worker**, nessun scheduler, nessun cron.
- `backend/api/` routers: nessun endpoint di tipo `/api/internal/reminder` o `/api/cron/*`.
- Railway config: solo web service (1 processo).
- Clerk: esporta gli eventi utente ma non manda email transazionali custom del prodotto (solo auth emails).
- Supabase: non usato per email (niente Edge Functions configurate in codice).

Qualsiasi opzione che preveda una "email reminder il giorno prima della prima sessione" richiederebbe **tutta nuova infra**:
- SDK email (Resend è la scelta naturale: piano free 100/giorno, dominio già da configurare)
- Scheduler: Railway Cron (cron triggerato che chiama un endpoint protetto `/api/internal/reminders/send`)
- Endpoint protetto con shared secret o firma
- Logica di dedup (non mandare due reminder allo stesso utente per la stessa sessione)
- Opt-out / unsubscribe (requisito legale in molte giurisdizioni)

Scope stimato: brief dedicato (A-REMINDERS), non includibile in questo A-ACTIVATION.

---

## §7 — Parked observations (non risolvere ora)

Cose emerse durante la discovery che **non** fanno parte di questo brief ma vanno annotate:

1. **`public.session_logs` è vuota in prod.** Le sessioni completate vivono in `users.state.session_completion_log` (JSONB). Qualsiasi query analytics SQL su `session_logs` ritorna risultati falsi. (Già flaggato in D-ANALYTICS-DROPOFF output.)
2. **`/onboarding/start-week/page.tsx` L72 e L111 redirigono a `/subscribe` incondizionatamente.** Anche utenti con bypass / trialing / active subscription passano per la paywall dopo onboarding. Candidato naturale per un B separato.
3. **`generate_test_week()` in `planner_v2.py` L1504 è dead code in prod.** Usato solo da test pytest. Da cancellare o collegare quando si decide la direzione delle test session.
4. **`nextTrainingDay` logic non guarda oltre la settimana corrente.** Se l'utente apre `/today` di sabato sera e la settimana è finita, nessun CTA.
5. **Empty state "No plan found for this date"** non spiega perché non c'è un piano (può essere: fuori range macrociclo, stato corrotto, macrocycle non rigenerato). Solo link debole.

Questi vanno in roadmap come voci separate a fine brief — non in Phase 1.

---

## §8 — UX options (almeno 2–3 distinti)

Tre opzioni genuinamente diverse per modo, rischio e scope.

### Opzione A — "Pre-week test injection"

**Idea:** quando l'utente sceglie "Start with test week" e oggi non è lunedì, iniettare test sessions sui giorni fra oggi e il prossimo lunedì. L'utente può fare una prima mini-attività immediata (anche solo 1–2 test) che rompe il ghiaccio. Il macrociclo vero parte comunque dal lunedì.

**Come:** nuovo concetto "prelude" nel modello dati: un array `state.prelude_sessions[]` di 0–6 sessioni pre-start, renderizzato da `/today` con bandiera "Initial assessment".

**Rischi:**
- Alto — tocca schema `user_state`, introduce un ciclo di vita parallelo per le sessioni prelude (completate vs saltate vs expired), deve essere invisibile ai reports e alla progressione.
- Incompatibile con l'invariante "7 giorni forward" del planner: va tenuto fuori dal planner e renderizzato solo in frontend.
- STOP protocol obbligatorio (tocca planner indirettamente via week view che aggrega prelude + week 1).

**Scope stimato:** 3–5 giorni, 1 backend brief + 1 frontend brief.

**Pro:** risolve il gap temporale direttamente — l'utente ha qualcosa da fare *oggi*, non "lunedì prossimo".

**Contro:** complessità alta per un effetto che potrebbe essere ottenuto da B in versione molto più semplice.

---

### Opzione B — "Shifted start_date (this Monday, partial first week)"

**Idea:** cambiare `onboarding.py` L385 da `start = next_monday()` a `start = this_monday()`. Il macrociclo parte dal lunedì della settimana corrente; i giorni passati vengono ignorati dal planner (già supportato da `# B95: skip past days` in `planner_v2.py` L757–760). L'utente che completa onboarding mercoledì vede subito sessioni su gio/ven/sab/dom invece di dover aspettare lunedì.

**Come:**
- `backend/api/routers/onboarding.py` L385: `start = this_monday()` invece di `next_monday()`
- Verificare che `initial_tests_requested` + partial week week 1 convivano (test session su una settimana parziale)
- Test pytest nuovi: (i) onboarding mid-week genera piano con 3 giorni visibili; (ii) progressione calcola correttamente "Week 1" quando sono passati 4 giorni; (iii) `current_phase_and_week()` robusto; (iv) rigenerazione macrociclo in mezzo alla settimana usa `next_monday` (non riscrive passato — invariante immutability).

**Rischi:**
- Medio — il codice cambia di una riga + test, ma gli effetti toccano moduli high-risk (`planner_v2`, `macrocycle_v1`, `progression_v1`, `closed_loop_v1`). STOP protocol obbligatorio prima di Phase 1.
- Edge case: utente completa onboarding la domenica sera → `this_monday()` ritorna il lunedì 6 giorni fa → la "Week 1" è fatta. Va gestito (probabilmente con `this_monday()` MA se oggi è domenica usa `next_monday()`, o soglia tipo "se mancano meno di 48h al next_monday usa next_monday").

**Scope stimato:** 2–3 giorni. 1 backend brief con test mirato.

**Pro:** infrastructure già quasi pronta (§3b). Risolve il gap temporale senza nuovi concetti. Testabile con pytest.

**Contro:** non aiuta chi ha completato "Start with test week" e vorrebbe test session immediate (si aggiunge: i test sono Week 1 comunque, quindi anche in partial week verrebbero mostrati).

---

### Opzione C — "Minimum viable — Today CTA revamp + /plan clarity"

**Idea:** zero modifiche al motore. Solo frontend. Trasformare gli empty state di `/today` da link testuali deboli in card ricche, e aggiungere un banner su `/plan` dopo onboarding che spieghi "La tua prima sessione è {giorno}, {data} — {nome sessione}".

**Come:**
- `today/page.tsx` L1017–1055: sostituire i link con una card visuale che mostri:
  - Nome prossima sessione (tipo: "Boulder Strength", durata, location)
  - Primo esercizio previsto (estratto da `resolved.exercises[0]`) come anteprima
  - Bottone primario "See plan for {weekday}"
  - Bottone secondario "Why nothing today?" che apri mini-dialog con spiegazione ("Rest day by design" / "Your macrocycle starts Monday")
- Estendere `nextTrainingDay` a guardare la settimana successiva quando quella corrente è finita (chiamata `/api/week/{n+1}`)
- Su `/plan`, dopo `POST /api/onboarding/complete`, mostrare un banner dismissibile "Your plan starts {date}. First session: {name}" per X giorni dopo l'onboarding.

**Rischi:**
- Basso — solo UI. Niente motore toccato. Branch + Vercel preview obbligatori (B196 rule), nessuno STOP protocol necessario.
- L'utente che ha completato onboarding un mercoledì vede comunque "nothing today" fino a lunedì — il gap temporale **resta**.

**Scope stimato:** 1–2 giorni. Un frontend brief.

**Pro:** fastest to ship, lowest risk, testabile subito su preview. Migliora la UX generale anche al di fuori del caso onboarding.

**Contro:** non risolve il problema di fondo (gap temporale). È una *mitigation*, non una *fix*. Se 75% degli utenti a stage 4 è intimidito dal "niente da fare fino a lunedì", un CTA migliore aiuta ma non elimina l'attesa.

---

### Opzione combinata (menzione)

**B + C** sono ortogonali e combinabili: shift start_date *e* migliora empty state. Il costo additivo di C dopo B è piccolo (1 giorno in più), e migliora molti altri casi ('No sessions today' nei giorni di rest legittimi, 'No plan found' post-macrociclo-scaduto, ecc.).

**A** è da valutare separatamente — secondo questo Phase 0 sarebbe prematura senza dati su quanti utenti scelgono "Start with test week" vs "Generate Plan".

---

## §9 — Raccomandazione

**B + C combinate**, in questo ordine.

**Perché:**
1. B risolve la causa-radice identificata (gap temporale fra fine-onboarding e first-session) usando infrastruttura già presente al 70%. Rischio medio ma perimetrato; pytest può dimostrare correttezza della progressione su settimana parziale.
2. C è complementare e poco costoso — anche dopo B, gli empty state esistono nei giorni di riposo legittimi e per utenti che hanno completato la settimana. Migliorarli ha valore permanente.
3. A è più ambizioso ma costoso e rischioso, e la sua premessa (utenti che scelgono "Start with test week" vogliono test *oggi*) non è validata dai dati (non sappiamo quanti scelgono quella variante). Rinviare ad A-ACTIVATION-v2 se dopo B+C il drop-off residuo giustifica l'investimento.
4. Email reminders: separate brief (A-REMINDERS). Non bloccare B+C per infra che non esiste.

**Decisione alternativa difendibile:** solo C. Se Daniele preferisce un ship sicuro e veloce, C risolve ~30–40% del problema percepito (CTA forte > CTA assente) senza STOP protocol e senza toccare il motore. B può sempre essere fatto in un brief successivo.

**Decisione che sconsiglio:** solo A. Complessità sproporzionata al segnale che abbiamo.

---

## §10 — STOP gate

═══════════════════════════════════════
  PHASE 0 COMPLETE — STOP
═══════════════════════════════════════

Decisions needed before Phase 1:
 1. Chosen option (A / B / C / B+C / other from §8)
 2. Include email reminder? (yes / no — if yes, scope out as separate A-REMINDERS brief)
 3. Include /guided preview mode? (yes / no — only relevant if §5 says it's needed; §8 assumes no)
 4. Scope of Today empty state fix: new-user only / all users (if C or B+C)

Waiting for Daniele's explicit "OK Phase 1, option N, [other decisions]".

**Non procederò a Phase 1 senza OK esplicito.** Nessun file verrà modificato, nessun commit creato, nessuna push. Se la risposta include dubbi sulla discovery, torno a Phase 0 per integrare.
