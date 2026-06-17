# D246 — Plan Pause/Resume: Read-Only Audit (pre A-PLAN-PAUSE)

**Tipo:** D (audit, read-only) · **Rischio feature target:** HIGH
**Data:** 2026-06-17 · **Autore:** Daniele Somensi (analisi assistita)
**Stato:** report di audit — ZERO modifiche al codice applicativo. STOP gate al fondo.

Moduli ispezionati (read-only): `macrocycle_v1.py`, `planner_v2.py`, `resolve_session.py`,
`replanner_v1.py`, `deps.py`, `macrocycle_archive.py`, state model, `week_archive` (A221),
frontend `today/week/plan/settings` + hooks.

---

## 0. Feature in esame (semantica bloccata 2026-06-09)

- **Pausa open-ended**: utente tocca "Metti in pausa" (Settings → avanzate). Lo stato registra `paused_at` (data ISO). Nessun auto-resume, nessuna durata fissa.
- **Resume**: utente tocca "Riprendi". Tutte le entità di piano FUTURE shiftano in avanti del delta. Il piano riparte identico a dove si era fermato.
- **Auto-suggest** (banner dopo ≥7 giorni di inattività): NON in scope per v1, solo annotare gli hook.
- **Billing**: la pausa NON tocca subscription, trial countdown, Stripe. Da verificare che resti vero.
- **Invariante non negoziabile**: sessioni passate/completate immutabili. Lo shift NON deve toccare alcuna sessione completata o passata (exercise_id, loads, feedback, status, timestamps), incluse le settimane archiviate.

---

## Phase 1 — Mappa call-site & consumer

### 1.1 `generate_macrocycle()` — call site

| File:line | Trigger | Note |
|---|---|---|
| `macrocycle_v1.py:540` | **definizione** | `generate_macrocycle(goal, profile, state, start_date, total_weeks=12, *, from_phase=None)` |
| `api/routers/macrocycle.py:90` | `POST /api/macrocycle/generate` | regen full o incrementale (`from_phase`) |
| `api/routers/macrocycle.py:255` | `POST /api/macrocycle/start-new-cycle` | ciclo nuovo, `from_phase=None` |
| `api/routers/onboarding.py:421` | `POST /api/onboarding/complete` | generazione iniziale |
| `api/routers/onboarding.py:429` | `POST /api/onboarding/complete` | fallback (week1 vuota) → `strict_next_monday()` |

**Monday invariant interno**: `macrocycle_v1.py:574-577` corregge `start_date` al lunedì precedente se `weekday()!=0`.

### 1.2 `ensure_monday()` — call site

Definizione `deps.py:225`. Call site: `macrocycle.py:78,83,86`; `onboarding.py:414,428,470`;
`weekly_override.py:43,67,115`; `state.py:70`. È il gatekeeper finale del Monday-invariant
(difesa in profondità con il guard interno di `generate_macrocycle`).
⇒ **Implicazione pausa**: qualunque nuova mutazione di date dovrà passare per lo stesso gate
o non potrà più garantire l'allineamento al lunedì (vedi §3, caso 3).

### 1.3 Consumer di `macrocycle.start_date` / `end_date`

**Derivazione settimana→data (anchor-derived — il cuore del rischio):**

| File:line | Formula | Ruolo |
|---|---|---|
| `macrocycle_v1.py:621` | `phase_start = start + weeks(current_week-1)` | calcolo date fasi in generazione |
| `deps.py:375,379-383` | `today_offset=(today-mc_start)//7` ; `phase_end=phase_start+weeks(dur)` | **`current_phase_and_week()`** — dove sono OGGI nel ciclo |
| `deps.py:403,416` | `week_start=mc_start+weeks(cum+week_in_phase)` | **`week_num_to_phase_context()`** — week_num→lunedì calendario |
| `progression_v1.py:249,254-257` | `start=mc.start_date` → settimane trascorse | fase corrente per progression |
| `report_engine.py:98,103-111` | offset settimane | bucketing report |
| `resolve_session.py:1755` | `_mc_start` → fase corrente | ordinamento phase-aware |
| `free_session.py:202` | fallback fase per data | solo contesto UI |
| `feedback.py:69` / `replanner.py:94` | `mc_start` come contesto | scoping |

**Finestra di ciclo `[start_date, end_date]` (filtri completamento — l'altro fulcro):**

| File:line | Uso |
|---|---|
| `macrocycle_archive.py:50-71` | `_planned_session_count` — conta sessioni in `week_plans` con `start <= week_key <= end` (+ merge archivio) |
| `macrocycle_archive.py:104-113` | `_build_completion_summary` — done/skipped con `_within_cycle(date, start, end)` |
| `macrocycle_archive.py:124-138` | `_weeks_completed` — `(today-start)//7` cap a `total_weeks` |
| `macrocycle_archive.py:74-90` | `_tests_completed_in_window` — test nel range |
| `macrocycle.py:130` | pruning week cache `k < new_start_date` (start-new-cycle) |

**Scrittura `start_date`/`end_date`:** `macrocycle_v1.py:668-669` (gen); `onboarding.py:470,473` (onboarding_start_week ricomputa end).

### 1.4 `phases[].start_week` / `end_week` / `duration_weeks`

- `start_week`/`end_week` (`macrocycle_v1.py:638-639`): **0 letture aritmetiche** — solo display/debug. Impatto pausa: basso.
- `duration_weeks` (`macrocycle_v1.py:640`): consumato ovunque per l'aritmetica cumulativa (`deps.py`, `week.py:218`, `progression_v1.py`, `report_engine.py`, frontend timeline). **Immutabile sotto pausa** — è la durata della fase, non una data; va usato per ri-derivare gli offset.

### 1.5 Scrittori di `week_plans`

| File:line | Endpoint/funzione | Campi data scritti |
|---|---|---|
| `week.py:474` | `GET /api/week/{n}` (gen + cache) | `start_date`, `weeks[].days[].date` |
| `replanner.py:87` (`persist_week_plan`) | override / quick-add / events | idem |
| `replanner.py:215,301,405` | override, quick-add, events | via persist |
| `feedback.py:326` | `POST /api/feedback` (replan adattivo) | idem |
| `body_part_picker.py:189` | insert body-part | idem |
| `weekly_override.py:86-88` | `PUT /weekly-override` | **invalida** (cancella) il plan cached |

**Shape week plan**: key cache = lunedì ISO assoluto. Oggetto contiene `start_date` (lunedì) e
`weeks[].days[].date` (data ISO per giorno). Le sessioni NON hanno data propria: ereditano dal
giorno. Lo `status` ("done"/"skipped"/None), `feedback_summary`, `_user_edited` vivono sulla
sessione.

### 1.6 `week_archive` (A221) — chiavi & date

- **File backend**: `{DATA_DIR}/{user_id}/week_archive/{week_start}.json` (`storage_file.py:105-144`).
- **Supabase**: tabella `week_archive (user_id, week_start, plan JSONB)`, upsert su `(user_id, week_start)` (`storage_supabase.py:109-188`).
- **Chiave = `week_start` lunedì ISO ASSOLUTO**, NON derivata dall'anchor. Confronti range lessicografici su stringhe ISO (`storage_file.py:140` `start <= key <= end`).
- Boundary hot/cold: `hot_floor()` = lunedì della settimana precedente (`deps.py:277-285`). Archiviazione lazy gated da `WEEKPLAN_ARCHIVE_LAZY` (default OFF). Il READ path (serve archivio, recency, report) funziona sempre.
- **Conseguenza critica**: una settimana archiviata è datata in ASSOLUTO. Se l'anchor del macrociclo si sposta, le chiavi d'archivio **non** si risincronizzano da sole. Qualsiasi meccanismo che sposti l'anchor deve trattare l'archivio come immutabile (NON va riscritto né ri-keyed).

### 1.7 Immutabilità passato — dove è garantita oggi

- `is_past_week()` (`deps.py:254-265`): `week_start < this_monday()`. Canonical B257.
- `week.py:53-62`: niente re-resolve di sessioni `done`/`skipped` o `_user_edited` con `resolved` già presente.
- `week.py:336-343`: cache-miss su settimana passata ⇒ `past_week_unavailable`, **mai rigenera**.
- `session_completion_log` append-only (`feedback.py:161-178`), datato in assoluto.
⇒ Le date passate **non vengono mai ri-derivate dall'anchor**: le settimane passate sono servite per chiave assoluta (hot o cold). Questo è il fatto che rende fattibile la pausa senza toccare il passato.

### 1.8 Frontend — consumer di date di piano

| Area | File:line | Ruolo |
|---|---|---|
| Today pre-start | `today/page.tsx:379-389` | `today < start_date` → hero "il piano inizia il …" |
| Today CTA fine ciclo | `today/page.tsx:135,954-971` + hook | banner "pianifica prossimo ciclo" |
| Week header/nav | `week/page.tsx:60,175,178-206,700-748` | "Week N / total", bounds prev/next, mappa week→fase |
| Plan timeline | `plan/page.tsx:40-46,194-227` | `computeCurrentWeek` = `(now-start_date)/7`; banner stale |
| Timeline component | `macrocycle-timeline.tsx:36-118` | marker settimana corrente, larghezza fasi |
| Week progress bar | `week-progress-bar.tsx:50-59` | "Week N/total" da `profile_snapshot` |
| Hero CTA | `today-hero-cta.tsx:51-197` | pre_start / offday |
| Can-start-new-cycle | `use-can-start-new-cycle.ts:45-62` | `isLastWeek`/`isPastEndDate` da `end_date` |
| Tipi | `types.ts:24-29,108,131-137` | `Macrocycle.start_date/end_date/total_weeks`, `DayPlan.date` |

**Nessun countdown "N giorni rimanenti" esiste**: tutto il display è week-index relativo + `end_date` per le CTA di fine ciclo. ⇒ Un eventuale stato "in pausa" va comunicato esplicitamente (oggi non c'è alcuno stato neutro tra "pre-start" e "off-day").

---

## Phase 2 — Meccanismo di shift: analisi e raccomandazione

### Il vincolo che decide tutto

Due famiglie di consumer leggono l'anchor in modo **opposto**:

1. **Forward / posizione** (`current_phase_and_week`, `week_num_to_phase_context`): derivano
   la data calendario di una settimana da `mc_start + weeks`. Vogliono che, dopo il resume,
   il "dove sono" NON includa il tempo in pausa.
2. **Finestra di completamento** (`_build_completion_summary`, `_planned_session_count`,
   `_weeks_completed`): contano done/skipped/planned con `start_date <= date <= end_date`.
   Vogliono che le settimane **già completate prima della pausa restino dentro** la finestra.

### Option A — shift di `start_date` in avanti di N: **RESPINTA**

Spostando `start_date` in avanti, le settimane completate prima della pausa (a date calendario
*precedenti* il nuovo `start_date`) cadono **sotto** `start_date`:

- `_build_completion_summary` (`macrocycle_archive.py:104-113`): `_within_cycle(date, start, end)` le **esclude** → il lavoro reale dell'utente sparisce dal riepilogo del ciclo.
- `_planned_session_count` (`:66`): `start <= week_key` esclude le settimane hot/cold completate → completion % falsato.
- `_weeks_completed` (`:137`): `(today-start)//7` sottoconta.
- Archivio (§1.6): le chiavi assolute restano dov'erano, fuori dalla nuova finestra.

> ⚠️ Nota di rettifica: un'analisi automatica preliminare aveva indicato Option A come "più pulita"
> sostenendo che "le settimane passate restano `< new start_date`". È esattamente **il bug**: in
> questo codebase restare sotto `start_date` significa essere **espulse** dalla finestra di ciclo,
> non preservate. Option A viola l'invariante di accounting del passato.

### Option B — shift solo del futuro + offset cumulativo: **RACCOMANDATA**

Tieni `start_date` come **anchor storico immutabile**; introduci sul macrociclo:

- `paused_at` (ISO date | null) — settato in pausa, azzerato al resume.
- `pause_offset_days` (int cumulativo, **sempre multiplo di 7** — vedi §3 caso 3).

Regole:

1. **`start_date` non cambia mai** → tutta la derivazione del passato e la finestra
   `[start_date, end_date]` restano corrette. Sessioni/archivio passati intatti by construction.
2. **`end_date` si estende di N** ad ogni resume (`end_date += pause_offset_delta`) → la finestra
   include sia il passato completato sia le settimane future shiftate.
3. **Anchor effettivo per il solo forward**: le due funzioni forward-looking usano
   `effective_start = start_date + pause_offset_days`:
   - `current_phase_and_week`: `today_offset = (today - effective_start)//7`. Al resume,
     `today = pause_day + N` ed `effective_start = start_date + N` ⇒ `today - effective_start`
     = posizione al momento della pausa. **L'utente riprende esattamente alla settimana in cui era.**
   - `week_num_to_phase_context`: `week_start = effective_start + weeks(...)` per current/future.
4. **Settimane future in cache**: al resume vanno gestite (sono mutabili, non immutabili):
   - settimane future SENZA `_user_edited`/quick-add → invalidare (`invalidate_future_week_cache`,
     `deps.py:75`) e lasciar rigenerare on-demand con l'anchor effettivo (date già shiftate).
   - settimane future CON edit utente → shiftare data+rekey preservando il contenuto (NON rigenerare).
5. **Archivio**: mai toccato (immutabile per definizione).

**Campi che si muovono** sotto Option B: `macrocycle.end_date`; `macrocycle.pause_offset_days`;
`macrocycle.paused_at`; chiavi+`start_date`+`days[].date` delle SOLE week_plans hot future
(o loro invalidazione). **Campi garantiti intatti**: `macrocycle.start_date`; ogni settimana con
`week_start < this_monday()`; tutto `week_archive`; `session_completion_log`; `phases[].duration_weeks`.

**Costo di Option B**: serve un punto unico di derivazione dell'anchor effettivo. Oggi
`current_phase_and_week` e `week_num_to_phase_context` (entrambe in `deps.py`) sono gli **unici due**
consumer forward che leggono `mc_start`; concentrare lì l'offset (helper `effective_start(macrocycle)`)
limita la superficie di modifica. Rischio classe B216/B217 (logica-date parallela) **mitigato** da
single source of truth — da testare esplicitamente.

---

## Phase 3 — Interazioni & edge case

| # | Caso | Comportamento attuale | Cosa deve fare pausa/resume |
|---|---|---|---|
| 1 | Replan/regen mentre `paused_at` settato | `set_availability` event rigenera l'intera settimana (`replanner.py` → `generate_phase_week`); `/macrocycle/generate` rigenera | **Bloccare/no-op** mutazioni che rigenerano (set_availability, override, quick-add, /generate, feedback-replan) finché in pausa. Definire 409/banner. `start-new-cycle` invece termina implicitamente la pausa (ok). |
| 2 | Free session durante pausa | `free_session` solo subscription-gated, NESSUN check macrociclo (`free_session.py:129,239,279`) | **Consentita** — plan-independent. Verificare che `get_phase_for_date` (solo UI) non assuma anchor non-shiftato. |
| 3 | Pausa non-multiplo-di-7 (es. 5 giorni) | week_plans keyed su lunedì; intero engine assume start lunedì | **Cruciale**: lo shift strutturale va misurato **lunedì-pausa → lunedì-resume** (sempre multiplo di 7) ⇒ Monday-invariant preservato automaticamente. Il parziale infrasettimanale (resume mercoledì) è già gestito dal param `today` del planner (settimana parziale). Quindi `pause_offset_days` **deve** essere multiplo di 7. Decisione: resume "snappa" al lunedì della settimana di resume. |
| 4 | Pausa attraversa confine di fase / anno | derivazione fase da offset cumulativo `duration_weeks` | Nessun trattamento speciale se l'offset è applicato all'anchor effettivo: la fase si ricalcola dalla posizione, non dal calendario. Verificare bucketing report (`report_engine.py`). |
| 5 | Pause/resume multipli | n/a | `pause_offset_days += delta` ad ogni resume; `end_date += delta`. Correttezza cumulativa = somma offset + estensione end. Test dedicato. |
| 6 | Pausa con trip/override esistente nella finestra | `compute_pretrip_dates` usa date trip ASSOLUTE vs week boundary (`macrocycle_v1.py:495-509`); `weekly_overrides` keyed su lunedì | Le date trip sono input utente assoluto: **non** shiftano. Dopo resume, un trip che cadeva in week W ora cade in calendario diverso → ridefinire se il trip resta ancorato al calendario (sì, è una data reale) o alla settimana di piano. Probabile: resta al calendario, la finestra pre-trip va ricalcolata. `weekly_overrides` future: stessa logica delle week_plans future (rekey o invalida). |
| 7 | Device switch / reload durante pausa | stato persistito server-side | `paused_at`/`pause_offset_days` sul macrociclo persistono → nessun problema, lo stato è O(1) e server-authoritative. |
| 8 | Subscription guard / trial countdown | `subscription_guard.check_subscription` calcola SOLO da riga Stripe/`trial_end` (`subscription_guard.py:137-188`), zero dipendenza da piano | **Indipendente confermato** — la pausa NON tocca billing/trial. Da blindare con test. |
| 9 | Dimensione stato / cleanup | n/a | O(1): solo `paused_at` + `pause_offset_days` sul macrociclo. Azzerare `paused_at` al resume; `pause_offset_days` persiste fino a `start-new-cycle` (che resetta tutto il ciclo). |

---

## Phase 4 — Superfici UX (solo documentazione)

1. **Comunicare lo stato "in pausa"** dove oggi non esiste uno stato neutro:
   - **Today (primario)**: card "Piano in pausa dal GG/MM — Riprendi" al posto delle sessioni (oggi Today ha solo pre_start e off-day, §1.8).
   - **Week**: badge "in pausa" sulla griglia; disabilitare replan/quick-add (coerente con §3 caso 1).
   - **Plan**: marker "pausa" sulla timeline; congelare il "current week" marker.
   - **Settings → avanzate**: entry point "Metti in pausa" / "Riprendi piano" (naturale vicino al blocco "Plan Next Cycle", `settings/page.tsx:969-995`).
2. **Today in pausa**: nessuna sessione dovuta; card pausa con CTA Riprendi + data inizio pausa.
3. **Entry point**: Settings → avanzate. Niente in onboarding.
4. **Interazione con CTA fine ciclo**: `use-can-start-new-cycle` (`isLastWeek`/`isPastEndDate`) deve **escludere** i cicli in pausa (l'`end_date` esteso già aiuta, ma la pausa va comunque gated per non far scattare il banner durante il freeze).

---

## Lista test invariante (da aggiungere nell'A-brief)

Obbligatori (l'A-brief NON è approvabile senza questi verdi):

1. **Sessione completata immutabile dopo pause+resume**: done/skipped in settimana passata → `exercise_id`, `loads`, `feedback`, `status`, `completed_at`, `days[].date` invariati byte-per-byte.
2. **Settimana archiviata intatta**: nessuna chiave `week_archive` aggiunta/rimossa/riscritta da pausa o resume.
3. **Completion summary preserva il passato**: `_build_completion_summary`/`_planned_session_count` contano le settimane pre-pausa ANCHE dopo lo shift (regressione diretta di Option A).
4. **Resume riprende alla stessa settimana**: `current_phase_and_week` post-resume == valore al momento della pausa (a parità di posizione, indipendente da N).
5. **Doppio pause/resume — offset cumulativo**: due cicli pausa-resume → `pause_offset_days` = somma; `end_date` esteso della somma; posizione corretta.
6. **Monday invariant dopo resume**: ogni chiave `week_plans` e ogni `start_date` di settimana restano lunedì (offset multiplo di 7) anche per pausa di 5 giorni.
7. **Billing indipendente**: `check_subscription` identico prima/dopo pausa (mock riga Stripe invariata) — `trial_days_remaining`, `is_active`, `can_interact`.
8. **Free session durante pausa**: log consentito, nessun errore, fase UI coerente.
9. **Mutazioni bloccate in pausa**: `set_availability`/override/quick-add/`/generate`/feedback-replan → no-op o 409, NON rigenerano.
10. **Settimana futura con edit utente preservata**: `_user_edited`/quick-add in settimana futura sopravvive al resume (shift+rekey, non rigenerazione).
11. **Trip/override nella finestra**: comportamento definito e testato (date trip assolute non shiftano; finestra pre-trip ricalcolata).
12. **Determinismo**: stesso stato + stessa pausa/resume → stesso output (principio non negoziabile).

---

## Outline A-brief di follow-up

**Tipo:** A (feature) · **Rischio:** HIGH · **STOP gate:** Phase 0 analisi + STOP prima di implementare (tocca `deps.py` forward-derivation, state schema, `week.py`, `replanner.py`).

**Scope:**
- Schema `user_state`: `macrocycle.paused_at`, `macrocycle.pause_offset_days` (default null/0).
- `deps.py`: helper unico `effective_start(macrocycle)` usato SOLO da `current_phase_and_week` e `week_num_to_phase_context`; tutto il resto continua a usare `start_date` grezzo.
- Endpoint: `POST /api/macrocycle/pause` (set `paused_at`), `POST /api/macrocycle/resume` (calcola delta lunedì→lunedì, `pause_offset_days += delta`, `end_date += delta`, gestisce week future hot, azzera `paused_at`).
- Gate mutazioni piano durante pausa (replanner, /generate, feedback-replan) → 409/no-op.
- Frontend: stato "in pausa" su Today/Week/Plan, entry point Settings, esclusione CTA fine ciclo.
- Branch obbligatorio `brief/A<n>-plan-pause` + preview Vercel (tocca frontend).

**Effort stimato:** M-L. Backend ~2 endpoint + 1 helper + gating (chirurgico grazie ai soli 2 consumer forward). Frontend ~4 superfici. Il grosso del rischio è nei test invariante (12 sopra), non nel volume di codice.

**STOP gate dell'A-brief:** Phase 1 analisi → STOP → Phase 2 impl → Phase 3 full suite + diff.

---

## STOP

Fine audit read-only. **Nessuna riga di codice applicativo modificata.** Daniele rivede il report
prima che l'A-brief venga autorizzato. Punto decisionale principale da validare: **Option B
(anchor effettivo + offset, `start_date` immutabile)** vs eventuali alternative.
