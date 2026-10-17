# climb-agent — Active Roadmap

> Last updated: 2026-08-16 ([[D276]] — potatura + razionalizzazione: **427 → ~310 righe**. Archiviate le entry chiuse che il trim automatico non intercettava; i residui **aperti** di [[D260]] spostati da sotto un'intestazione «Recently closed» a **## Open**, dove erano di fatto invisibili; `B228`/`D230` tolti dalla tabella go-to-market, di cui non hanno mai fatto parte; `MKT-COACH` congelato per coerenza con [[D275]]; `W7` ridotto da 3 orfani a 1 dopo verifica sul codice; conteggi e stati rimisurati.)
> Precedente: 2026-08-13 ([[D275]] — allineamento alla decisione di [[D274]]: climb-agent è uno **strumento personale** che resta pubblicamente disponibile, marketing in pausa. Niente si spegne — Stripe LIVE, guardia attiva, piani acquistabili — ma il lavoro di crescita esce dalla roadmap. §1.75 riscritta, ACT-01/03 riclassificati per uso proprio, ACT-02 declassato, ACT-04 rinviato, GTM-06 chiuso won't-do.)
> Unscheduled exploratory items live in `docs/ROADMAP_BACKLOG.md` (B320) — questo file
> contiene solo ciò che è aperto **e** schedulato.
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Open

**B381-FALLBACK — `fallback_exercise_ids` per blocco nel resolver (rinviato da [[B381]], 2026-10-17)** ⚪ P3 — un pin che fallisce per equipaggiamento ricade oggi sulla scelta generica dei filtri. B381 ha risolto il caso concreto (panca) cambiando il pin; un fallback esplicito per blocco serve solo se ricompare un caso simile. Tocca `resolve_session.py` → fase 1 + STOP.

**B387-DISPLAY — le custom vecchie mostrano ancora i campi del catalogo salvati al momento (da [[B387]], 2026-10-17)** 🟡 P3 — decisione di Daniele — B387 rende «magro» un esercizio custom solo se si riproduce identico. Le custom di Daniele sono tutte anteriori a B380 (manca `load_unit`), quindi restano piene: 229 KB. `scripts/migrate_b387_state_shrink.py --refresh-display` le rifà dal catalogo attuale (dry run del 17/10: 291 esercizi guadagnano l'unità — 243 `total`, 27 `implement`, 21 `per_dumbbell` —, 19 cue aggiornati, `bulgarian_split_squat`/`cossack_squat` da `bodyweight_only` a `external_load`, «Handstand Kick-up (a Muro)» → «(Wall)»); il blob di Daniele passerebbe da 538 a 391 KB. Carichi, serie, ripetizioni e note dell'utente restano identici (il gate lo verifica campo per campo). Serve l'OK perché cambia ciò che il player mostra.


**B369-P6-residui — dopo [[B371]]: riconciliazione post-rigenerazione e `change_gym` (da [[B369]], 2026-10-05)** 🟡 P3 — [[B371]] ha chiuso il controllo di versione; restano i due punti collegati, entrambi nel motore (`replanner_v1`, Fase 1 + STOP): (1) dopo una rigenerazione le sessioni del motore non vengono riconciliate contro quelle dell'utente conservate — oggi solo segnalazione (`regeneration_guard_warnings`, coerente con A301); (2) `change_gym` non marca la sessione come dell'utente, quindi una rigenerazione successiva riporta la sessione del motore alla palestra di default. Non «banalmente sicuro»: un nuovo marker in `USER_MARKERS` cambia cosa vedono `retest_policy._locked_by_merge`, la rotazione dei complementari (A300) e gli alert di A301. (3) **corsa residua di B371**: il lock per utente vale nel singolo processo uvicorn (Procfile attuale); con più worker/repliche, o con gli scrittori senza lock (rigenerazione in `GET /api/week`, `PUT /api/state`), resta una finestra stretta di lost update — la chiusura vera è un salvataggio condizionato sulla revisione salvata (PATCH/RPC Supabase filtrato).


**CONTENT-BRIDGE-VIDEO — video su «pilotare Claude Code da Telegram» ([[A276]], 2026-08-21)** 🟢 idea di Daniele — raccontare in video il bridge di [[A276]]: un messaggio Telegram diventa un turno di Claude Code dentro il repo, con sessione persistente, `/stop` e allowlist di uno. **Non riapre la GTM di climb-agent**: è contenuto su *tooling di sviluppo*, non acquisizione utenti per l'app — il trigger `GTM-07` resta l'unico che rimette in discussione la decisione di [[D274]]. Materiale già pronto e verificato durante il brief: `--output-format json` con `session_id`, la differenza fra boot a freddo (CLAUDE.md grosso riletto senza cache, più lento) e resume, il recupero da sessione stantia (senza cui da Kalymnos il ponte è irrecuperabile), il lock di istanza singola contro il 409 di Telegram, e il perché **long polling e non webhook** (Mac dietro NAT). L'angolo onesto è il confronto col plugin ufficiale — che esiste, supporta più bot via `TELEGRAM_STATE_DIR`, e vuole però una sessione interattiva viva: il demone serve solo quando la macchina è a casa e tu no. **Da decidere prima di girare**: se mostrare `.env` e i nomi delle variabili (il token di un bot è una credenziale, e in A276 uno è già passato in chat — vedi nota sotto), e se il repo mostrato è climb-agent o uno di prova.


**ASSESSMENT-CARRYOVER-INVISIBLE — il carry-over non è visibile sul primo step (da [[B318]] Fase 2, 2026-08-01)** 🟡 P3 UX — il CTA promette che le risposte sono riportate, ma il wizard atterra su `/onboarding/profile` (nome, età, peso, altezza), che l'assessment non raccoglie: i campi seminati compaiono solo agli step `grades`/`goals`, cioè 4-5 schermate dopo. L'utente vede un form vuoto nel momento esatto in cui dovrebbe vedere la prova della promessa. Candidati: atterrare su uno step già popolato, oppure una conferma esplicita («abbiamo già i tuoi gradi») in cima al primo step. **Attenuato da [[B319]]** (2026-08-01): `profile.weight_kg` ora arriva pre-compilato per chi ha inserito i numeri, quindi il primo step non è più del tutto vuoto — ma resta vuoto per chi ha risposto solo alle sei domande. Da scopare con Daniele — è una scelta di flusso, non un fix.

**COACH-TRUNCATION-RESIDUAL — risposte tagliate o vuote: causa trovata in [[D283]] (da [[D266]], 2026-07-30)** 🔴 — non è il `tool_use` del meteo ipotizzato in D266: `claude-sonnet-5` con `thinking` omesso **ragiona in modo adattivo per default** e i token di thinking contano dentro `COACH_MAX_TOKENS` (2048). D283 l'ha misurato registrando `stop_reason`: Q-05 e Q-16 chiudono a `max_tokens` con 2.048 token in uscita, e Q-16 nella ripetizione ha speso **tutto** il budget nel thinking → `_final_text()` restituisce una **stringa vuota** all'utente. Fix: (1) subito, senza deploy, `COACH_MAX_TOKENS=6000` su Railway; (2) brief B su `llm_client.chat()`: `output_config.effort` esplicito (medium/low, da misurare) e `stop_reason == "max_tokens"` con testo vuoto trattato come errore, mai `""` restituito; (3) il runner `coach_regression_rerun.py` scrive `stop_reason` + `output_tokens` nel raw (Q-03 era un falso positivo di `looks_truncated`: `end_turn`). Dettagli: `docs/audit/D283_coach_regression_r7.md` F1.

**COACH-REENTRY-FRAMING — il coach legge «re-entry after a break» come una pausa dell'atleta (da [[D283]], 2026-10-05)** 🟡 — unica regressione attribuibile ad [[A297]]: la riga dei carichi ancorati (`athlete_context._anchor_line_en`) dice «re-entry after a break (exposure n), capped lower» quando la rampa riparte dopo `REENTRY_GAP_D` giorni senza esposizione (anche solo dopo un test); il modello ne fa una biografia («sei in rientro dopo una pausa», «prima sessione dopo lo stop») e cambia il consiglio (Q-03 perde il gate dei 6 mesi di hangboard, Q-12 parla di rientro invece che di sonno). Fix: rendere la riga come rampa di carico con `gap_days` («first exposure after N days without finger work → capped lower») + una frase nell'intestazione del blocco («ramp/cap markers describe how loads are set, never infer a layoff, illness or injury from them»); verificare con `--only Q-03,Q-12,Q-20,Q-23`. D283 F2.

**COACH-PE-4X4-DRIFT — Q-06 perde il rifiuto del 4×4 (da [[D266]], 2026-07-30)** 🟡 minore — il primo run rifiutava esplicitamente il 4×4 in favore degli intervalli a intensità variata (D47); il re-run non lo menziona più, pur avendo `04_power_endurance` in contesto. Non è retrieval, è deriva del modello: se si ripete al prossimo run, vale un rinforzo nel file L3 (spostare D47 in cima alla sezione, o renderlo una riga «cosa NON prescrivere»). **D283 (2026-10-05):** non ripetuto — Q-06 a 2/2, nomina gli intervalli a intensità variata «invece del classico 4×4»; resta aperto solo come osservazione di varianza.

**A-ADHOC-BACKDATE — loggare a posteriori una sessione composta dal coach (da [[B309]], 2026-07-29)** 🟡 — il CTA "Add to today & run" usa sempre `localToday()`: se hai fatto l'allenamento ieri e chiedi al coach di ricrearlo per loggarlo (caso reale di Daniele, 29/07), non c'è modo di appoggiarlo al giorno giusto. Serve un selettore di data sulla card (oggi / ieri) e una decisione esplicita su quanto indietro si può andare — l'inserimento su un giorno passato non viola l'immutabilità (è un'azione utente esplicita, come la matita), ma è un cambio di comportamento da approvare.


**BASE-PULLING-INTENSITY-CAP — La forza massima di tirata non può entrare in `base` (da [[A258]], 2026-07-29)** 🟡 — il KB indicava `base` come collocazione classica della forza massima multiarticolare (Consuegra §8.8), ma `pulling_strength_gym` è `intensity: high` e `base` ha `PHASE_INTENSITY_CAP = medium`: il planner la scarta prima di considerarla. In base la tirata arriva solo come **mantenimento** (blocco [[C261]]). Per dare lavoro di **sviluppo** in base servirebbe alzare il tetto d'intensità della fase o creare una variante a intensità media della sessione — decisione metodologica, non un dettaglio di pool. Da riportare al KB insieme alla domanda se la fase base debba davvero ospitare forza massima o se il tetto `medium` sia corretto. **Aggiunta di [[D280]] (2026-08-30):** il problema è più concreto di così — `PULLING_1RM_PCT[("base", …)]` vale **0,55 / 0,625 / 0,70** (`progression_v1.py:89-91`) mentre il blocco `pulling_maintenance` di `finger_maintenance_home.json` prescrive 2×4 con la nota *«Low volume, high intensity»* e *«drop a rep — never the load»*. Il 62,5% dell'1RM a 4 ripetizioni lascia 8-10 ripetizioni di buffer: **il codice contraddice il proprio catalogo**, ed è volume basso a intensità bassa, cioè né mantenimento né stimolo. ⚠️ Prima di alzare la soglia serve ri-ancorare il «≥80% 1RM per mantenere» a una fonte corretta sul *mantenimento* (Spiering et al. 2021) — la review 2024 sulla dose minima (PMC11127831) riguarda la popolazione generale e l'*aumento*, ed è stata misattribuita in prima battuta.


### Programma «train harder» — brief successivi ad [[A288]] (da [[D282]], 2026-10-04)

Ordine serializzato e decisioni vincolanti in `docs/audit/D282_train_harder_phase1.md` (ogni brief si mergia prima del successivo). Tutti usano le fondamenta di [[A288]] (`macro_position`, `stimulus`, `retest_policy`) invece di reimplementarle.

- ~~**A290**~~ ✅ — rotazione delle ancore di fase nel resolver (R2), vedi Recently closed. ~~**A291**~~ ✅ — scala gradi con «+», mezzi gradi (R6a), vedi Recently closed. ~~**A292**~~ ✅ — evidenza onsight + offset PE (R6b/R6-PE), vedi Recently closed. **Dopo il deploy:** Daniele conferma l'onsight dalla card in Settings (la proposta è 7b; Nishiki Alien va segnata «Worked»).
- ~~**A293**~~ ✅ — contesto atleta per Claude Code (R7a), vedi Recently closed. ~~**A294**~~ ✅ — sessioni chiave (R5), vedi Recently closed. ~~**A295**~~ ✅ — feedback misurato (R4), vedi Recently closed. ~~**A296**~~ ✅ — `limit_log` + logger dei problemi (R6c), vedi Recently closed. ~~**A297**~~ ✅ — contesto atleta nel coach e nel composer in-app (R7b), vedi Recently closed. ~~**COACH-REGRESSION-R7**~~ ✅ → **D283** (50/56, zero breach), vedi Recently closed.
- ~~**C272**~~ ✅ — scale a corpo libero, libreria tecnica / try-hard e riscaldamento tasche nel catalogo (role `ladder` / `library`, mai scelti dal motore), seed dei livelli in sola lettura nel contesto atleta; vedi Recently closed (2026-10-05).
- ~~**BW-PROGRESSION**~~ ✅ → **A298** — progressione a corpo libero a ciclo chiuso, vedi Recently closed (2026-10-05).
- **BW-PROGRESSION-FOLLOWUPS — pezzi della spec BW non fatti in A298** 🔲 (da [[A298]]): (1) `dose_for` nell'ad-hoc builder e nel pool del composer (livello / «next» nelle righe, pool solo dal pavimento al livello corrente, validator che riporta le reps nella banda) — oggi le custom del coach ricevono la dose solo se le righe sono `ladder`; (2) budget core per blocco (≤ 2 high/max, ≤ 1 appeso o a leva, ≤ 1 anti-estensione, ≤ 2 compressione per seduta + posterior_chain obbligatorio) e pavimento d'intensità core (hollow_plank fuori da main/accessory con L-sit ≥ 35 s) — cambiano la selezione; (3) zone `lower_back` / `knee` in `ZONE_TO_CONTRAINDICATION` (quando esistono, `has_lower_back_zone` sblocca i livelli lombari); (4) le correzioni di catalogo che cambiano la selezione rinviate da C272 (side_plank → low, nordic_curl → high, alias `band` ↔ `resistance_band`, chiavi dip bars prima di `equipment_required_any` sul dip, `copenhagen_adductor_plank` / `pistol_squat_progression` inattivi con le liste di `body_part_picker.py`, pattern di `core_l_sit`, recency copenhagen / hip_flexor); (5) Impostazioni → «Livelli corpo libero» (UI: l'endpoint `PUT /api/bw-progression/{family}` c'è già); (6) regole di piano sul front lever: max 1 a settimana in performance, famiglie appese mai nelle 24 h prima di limit/strength_long (oggi il FL conta come tirata pesante nei conflitti e nelle proposte A294, non sposta il planner); (7) R-PHASE nel taper pre-viaggio A281 (oggi solo performance / deload); (8) scala POSIZIONI (hover x/5) e benchmark B1/B2 nel tracciamento tecnico; (9) `test_front_lever_progression` come esercizio di test (seed del FL solo dallo storico). (10) carico sulla variante di handoff: oggi il terminale R7 con `handoff_exercise_id` dà solo il messaggio «passa a X, parti da +N kg» — l'inizializzazione di `working_loads` per l'esercizio zavorrato (spec R7) non è fatta; (11) tetto ai kg sull'unica famiglia senza variante nominata (`single_leg_squat`, +5 kg a passo, senza fonte per un massimo); (12) il criterio «benchmark B1 stabile o migliore» della scala piedi (oggi conta solo la misura sui drill del livello corrente).
- ~~**CATALOG-NOTES-ALL-USERS**~~ ✅ → **C273** — note del catalogo coerenti con le cues, vedi Recently closed (2026-10-05).
- **BODY-PART-PICKER-NONDETERMINISM — il generatore per distretti non è deterministico fra processi** 🔲 (trovato in [[C272]]): `select_exercises_for_part` costruisce i candidati da un `set` di id stringa (`build_body_part_index`), quindi l'ordine — e con il jitter a seed fisso la scelta — cambia con `PYTHONHASHSEED` da un processo all'altro: stessa richiesta, stesso stato, sessioni diverse fra due worker o due deploy. Viola il principio «deterministico». Fix probabile: ordinare i candidati per id prima dello scoring (cambia l'output per tutti → golden da rigenerare con OK). Per questo il golden statico di C272 non include il picker (solo un differenziale nello stesso processo).
- ~~**A296-FOLLOWUP — residui di R6c non implementati**~~ ✅ → **A299** (vedi Recently closed 2026-10-05): (1) report settimanale con il massimo chiuso per superficie (R6c frontend §7); (2) il dialog di feedback post-sessione (/today, /week) non ha né il campo grado né il logger dei problemi, quindi un limit chiuso da lì non aggiorna la memoria (pre-esistente); (3) i target di grado nelle anteprime del composer/adhoc sono solo display (scartati al salvataggio, ricalcolati dal player).
- ~~**Migrazione B364 da lanciare dopo il deploy**~~ ✅ verificata 2026-10-05: `STORAGE_BACKEND=supabase` (con `.env` caricato) → Daniele **0 cambi**, 34 settimane archiviate lette: già applicata. ⚠️ Senza `STORAGE_BACKEND=supabase` lo script legge il file locale di test e stampa cambi che non riguardano la produzione.
- ~~**B separati, fuori dal programma**~~ ✅ → **B367** (adaptive replan che cancellava custom e done, undo skip, cap che ignorava le done, `set_availability` ritirato, `prev_days`/`today` a override e quick-add), vedi Recently closed (2026-10-05).
- **STIMULUS-RECENCY-DIVERGENCE — `closed_loop_v1.stimulus_recency` diverge dalla vista di esposizione A288** 🔲 (da [[B367]], rimandato: decisione di design). Contatore incrementale scritto agli eventi (4 *categorie* a livello sessione: finger_strength / boulder_power / endurance / complementaries) contro `stimulus.exposures`, vista derivata in lettura (4 *famiglie* a livello esercizio: finger_max / pulling_max / limit_power / power_endurance) usata dalle chiavi A294. Divergenze concrete: nessun decremento all'undo (done/undo/done conta due volte), `last_done_date` è «l'ultimo scritto» e non il massimo (una spunta in ritardo lo riporta indietro), `last_skipped_date` mai scritto (il `mark_skipped` cerca la sessione per `session_ref` dopo lo swap con lo stub), `/events mark_done` sulle custom scrive anche se A240 dice di no. Consumatori: solo la riga «Nd since last» del report settimanale (`report_engine._build_stimulus_balance`, può venire negativa sulle settimane passate) e `body_part_picker._recent_recency_groups` (legge le chiavi categoria come recency_group: di fatto morto). Il planner non lo legge. **Opzioni:** (a) il report calcola `days_since_last` in lettura da week_plans + archivio A221 come già `sessions_this_week`, `stimulus_recency` diventa legacy — S–M; (b) il report passa alle famiglie A288 — M, cambia ciò che l'utente vede. Nessun impatto sul piano.
- **Divergenza nota:** `progression_v1._get_current_phase_id` ignora la pausa A223 — [[B364]] l'ha sostituita con `macro_position` nei 4 esercizi ancorati; resta nei percorsi legacy (non testati, B363 picker/builder per il pull-up non testato). Il rientro di B365 (limit) conta ancora con la sua logica: va riallineato a `reentry_step` — A291 ha toccato quel ramo solo per il delta in mezzi gradi e non l'ha fatto (fuori dalla spec R6a), resta aperto.

### Metodologia — finding aperti di [[D280]] (2026-08-30)

Da `docs/audit/D280_methodology_vs_literature.md` — workflow a 15 agenti: letteratura 2022-2026,
audit del motore, incrocio col piano reale di Daniele, round di verifica avversariale.
**Tutto ciò che segue è stato riverificato a mano** eseguendo il codice o con grep mirati; i
finding che la verifica ha demolito sono nella Parte D dell'audit e **non vanno riaperti**.
Tutto quanto tocca `progression_v1` / `planner_v2` / `macrocycle_v1` è high-risk → Fase 1 + STOP.

| B-FRESHNESS-POLICY-INERT | **`freshness_policy` è scritta su ogni test e non letta da nessuno** | B | M | Open P2 | *(Residuo di `B-DEAD-CHANNELS`: gli altri quattro canali sono chiusi da [[B346]].)* `{"stale_after_days": 90}` viene scritto in `progression_v1.py` (4 punti) e `confidence: "high"` è hardcoded alla scrittura; grep su `backend/engine`, `backend/api`, `frontend/src`: **zero letture**. I 4 test di Daniele hanno 100-166 giorni e le prescrizioni ne derivano al 100% senza declassamento né richiesta di re-test. **Fix proposto:** oltre la soglia declassare `confidence` a `low` e marcare la prescrizione `load_source: "stale_baseline"`, mostrandolo in card. ⚠️ **Non** sospendere la progressione: con i test di Daniele tutti scaduti gli congelerebbe ogni carico. Serve anche una decisione su quale soglia (oggi ne convivono tre: 42 gg in PASS 3, 60 gg in `_best_entry`, 90 gg dichiarati qui). Tocca il frontend → branch + preview.
| B372-FE-COPY | **Titolo della card `post_outdoor` non allineato a B372** | B | S | Open P3 | `frontend/src/lib/week-alerts.ts:58` mostra «Right after a big outdoor day», ma da [[B372]] `post_outdoor` scatta dopo ogni giornata outdoor che conta (dichiarata, loggata hard, carico ≥ 65, completata senza log) e il messaggio del backend dice «(planned)» / «(no route log)». **Fix:** titolo «After an outdoor day» (come la guida utente), eventualmente varianti da `w.outdoor.reason`; opzionale una variante di titolo per `finger_gap` / `finger_test_72h` / `hiit_near_max` / `hard_back_to_back` quando c'è `w.outdoor`. Tocca `frontend/` → branch + preview Vercel. |
| A-AUTOREGULATION-APRE | **Autoregolazione al posto della percentuale fissa** | A | L | Open P3 | Network meta-analysis 2025 (J Exerc Sci Fit, PubMed 40791980): sulla forza massima l'autoregolazione batte in modo consistente il carico a % fissa — SUCRA back squat **APRE 93,0%** · RPE 66,8% · VBRT 27,0% · **PBRT 13,2%**. Il motore prescrive esclusivamente % fisse di un massimale (`PULLING_1RM_PCT`, `HANGBOARD_DEFAULT_INTENSITY_PCT`, `intensity_pct × max_total_load_kg`). **APRE è essa stessa deterministica** (il carico della serie N+1 è funzione delle ripetizioni della serie N secondo una tabella fissa) → compatibile col vincolo di determinismo del progetto. Probabilmente il singolo miglioramento metodologico col miglior rapporto evidenza/compatibilità. Da scopare con Daniele prima di aprirlo. |
| C-CATALOG-METHODOLOGY | **Tre correzioni di catalogo** | C | M | Open P2 | **(a)** `arc_training` (`exercises.json:2773`) promette *«capillary density and forearm aerobic enzyme activity»*; "capillarization/capillary density" compare in 3 descrizioni user-facing (righe 1015, 2773, 10740). Bioengineering 2024 (PMC11048441, NIRS+DCS, n=32): l'adattamento è di **delivery/riperfusione** (flusso iperemico p=0,043; picco HbO₂ p=0,001, d=1,263), **nessuna differenza nel consumo di O₂** — e il protocollo *senza rilascio* («no rests, no shaking out») è proprio quello che non allena la riperfusione. **(b)** `threshold_climbing` (`:2731`) e `threshold_long_intervals` (`:2789`) hanno `prescription_defaults` **identici** (6×120 s, 60 s riposo, `lead_max_os` −1) ma sono etichettati `power_endurance`/`medium` e `aerobic_capacity`/`low`: `intensity_level` è un filtro P0, quindi due esercizi identici entrano in fasi diverse. Baláš 2021-2022 (PMC8819085): il sistema energetico è determinato dalla **struttura lavoro/riposo**, non dall'etichetta. **Fix:** derivare `energy_system` dai parametri + test di catalogo che fallisca sulle incoerenze. **(c)** Aggiungere il blocco dita low-load/high-frequency (vedi [[A-FINGER-LOAD-TIERS]]). |
| A-FINGER-LOAD-TIERS | **Il gap 48 h sulle dita è binario e blocca la combinazione meglio supportata** | A | M | Open P3 🔴 high-risk | In `_SESSION_META` (`planner_v2.py:38-74`) il carico dita è un booleano e `finger_gap_days = ceil(1 × recovery_multiplier)` applica le stesse 48 h a `finger_aerobic_base` (low) e a `limit_boulder_gym` (max). Gilmore/Klimek/Abrahamsson/Baar 2024 (Sports Med Open, 10.1186/s40798-024-00793-7, coorte retrospettiva n=526): carico frequente a ~40% del massimo (piedi a terra, ~10 min appeso, ≥3 sessioni/sett., ≥6 h fra le sessioni) → **+2,5%** strength:weight vs **+3,2%** dei max hangs, e **chi fa entrambi +5,8% (d=0,79, p=0,0081)**, quasi additivo; chi solo arrampica **0%**. Oggi quella combinazione è **strutturalmente non pianificabile**. **Fix:** `finger_load: high | low`, gap 48 h solo fra `high`, minimo 6 h altrove. ⚠️ Studio retrospettivo, non randomizzato, carico Abrahangs non misurato, 21 donne su 526 — evidenza moderata. |
| A-AGE-MODIFIERS | **Nessun modificatore di età sopra i 18 anni** | A | M | Open P3 | Grep `age|birth` in `progression_v1.py` e `assessment_v1.py`: nessun uso. L'unico gate anagrafico nel planner è `target_days = min(target_days, 4)` per gli under-18. Sopra i 40 (Daniele ne ha 40) il parametro che conta non è ridurre il volume ma limitare il **rate** di progressione del carico e diluire la frequenza degli stimoli massimali: il muscolo guadagna forza in 6-8 settimane, il tendine si rimodella in mesi. **Da marcare esplicitamente in codice come euristica a evidenza debole** — la letteratura specifica per arrampicatori master è sottile. |
| A-INJURY-HISTORY | **L'infortunio pregresso non è persistito** | A | L | Open P3 | `normalize_limitations` (`resolve_session.py:337-379`) costruisce `{zona: severità}` dallo stato **corrente** su 4 zone. Non esiste `injury_history[]`: nessuna data di esordio, di risoluzione, nessuna persistenza — alla risoluzione tutti gli esercizi si riaprono in blocco. Systematic review 2023 (PMC10756908, 34 studi) e 2025 (PMC12821603): l'infortunio pregresso è un predittore forte, **re-infortunio ~63%** su 3 studi prospettici; **93% degli infortuni da sovraccarico**. |
| A-DECLARED-VS-LOGGED-GRADE | **Nessun confronto fra grado dichiarato e log reali** | A | M | Open P3 | `_validate_goal` (`macrocycle_v1.py:597-629`) valida solo il gap target−current (warning se >8 mezzi gradi); **nessun modulo di assessment/macrociclo/planner legge `outdoor_log`** (solo `milestones_v1` e `report_engine`, percorsi di sola visualizzazione). Su Daniele: `worked = 8a+`, target 8b, e nei 46 log outdoor (5,5 mesi) il send più duro è **un 7b+** più sette 7b, con l'8a tentato e non chiuso 26 volte. ⚠️ **Limite dell'inferenza:** i log coprono 5,5 mesi — l'affermazione difendibile è *«dichiarato ≠ confermato dai log»*, non *«il dichiarato è falso»*. ⚠️ **Verificato per esecuzione che correggere il goal NON cambia il piano**: `finger_strength = 100` con target 8b, 8a+, 8a, 7c+ e 7c indifferentemente, e rigenerando il macrociclo con 8a/7c la struttura delle fasi è identica e i pesi cambiano di ~1 pp. **Vale per onestà del report, non per ricalibrare il piano.** Fix proposto: mostrare il massimo *concluso* accanto al dichiarato, con prompt di conferma oltre 2 mezzi gradi di divario. |
| B-GOAL-DEADLINE-DERIVED | **`goal.deadline` è un nome fuorviante per una data derivata** | B | S | Open P3 | *(Residuo di un finding "critico" **scartato** in verifica — vedi Parte D1 dell'audit: non esistono «7 settimane di picco perse».)* L'utente non inserisce mai una data-evento: `deadline-weeks-selector.tsx` è uno slider *«Plan duration (weeks)»* con `computeEndDateIso(weeks) = today + weeks*7`, e `goal-editor.tsx:150-153` porta il commento *«A218: total_weeks is the source of truth; deadline is a derived display string»*. Due incoerenze visibili: `goal.total_weeks` = 12 contro `macrocycle.total_weeks` = 16, perché `/api/macrocycle/generate` con `from_phase="current"` rilegge `old_mc["total_weeks"]` (`macrocycle.py:91`) — **lo slider non ha effetto sul ciclo in corso**; e `/settings` mostra una "deadline" che non corrisponde né alla fine del piano né ad alcun evento. **Fix:** rinominare in `plan_end_date`, e far sì che modificare `total_weeks` o rigeneri davvero o dica esplicitamente che non lo farà. |

**Nota di metodo (vale per chiunque riapra questo audit):** il round avversariale ha demolito 2
finding su 5 e ne ha declassati altri 2, trovando **citazioni misattribuite in tre casi su cinque**
(Faggian 2025, PMC11127831, Kaufmann 2024 PLOS ONE). Anche due cifre del mio riassunto iniziale
erano sbagliate: l'aderenza **non** è zero (87 done / 11 skipped su 98) e le "7 voci di feedback"
sono un **buffer rotante troncato a 7 per design** (`adaptive_replan.py:150`). Nessun finding di
questo tipo va accettato senza riaprire la fonte e il file.

### Outdoor — finding aperti di [[D279]] (2026-08-17)

Dall'audit `docs/audit/D279_outdoor_ux_audit_kalymnos.md`. **F1 è chiuso da [[B335]], F3 da [[B336]]**; questi restano.
Tutto quanto tocca `planner_v2` / `replanner_v1` è high-risk → Fase 1 + STOP prima di implementare.

| ID | Titolo | Tipo | Effort | Stato | Note |
|----|--------|------|--------|-------|------|
| C-OUTDOOR-SECTORS | **Catalogo settori v1 — Kalymnos (~20 righe)** | C | S | Open P2 | `backend/catalog/outdoor/v1/sectors.json`: nome, esposizione, ora in cui arriva il sole, avvicinamento, range di gradi, stile, **fonte** e flag `inferred`. Niente vie, niente topo, niente coordinate, nessuna seconda area. Il dato che decide davvero («Odyssey ora, Spartacus dopo le 16:00») è pubblicato e statico; su Kalymnos ad agosto il meteo non porta informazione (zero giorni di pioggia). Da seminare **dopo** il trip, con le note di campo del protocollo §4.3 a validare le ore. Precede [[A-OUTDOOR-WHERE-NOW]]. |
| A-OUTDOOR-WHERE-NOW | **«Dove si scala adesso» dal catalogo settori** | A | M | Open P3 | `GET /api/outdoor/sectors?area=&at=` read-only, ordinato per ombra all'ora locale; alimenta `condition_band` **a livello di strategia** (`outdoor_resolver`), non nel motore meteo. Dipende da [[C-OUTDOOR-SECTORS]]. |
| A-TRIP-ONE-DECLARATION | **Un viaggio dovrebbe essere una dichiarazione sola** | A | L | Open P3 🔴 high-risk | `trips[].end_date` **non è letto da nessuno**: gli unici consumatori sono la finestra dei 5 giorni pre-partenza e il prompt del coach. Oggi dichiarare 10 giorni fuori costa ~20 tap di weekly-override. Manca anche il **recovery post-trip**, promesso dal design §7.2 e implementato da nessuna parte (`grep post_trip` in `backend/`: zero). |
| B-FORECAST-MIDDAY-STEP | **Il forecast rappresenta la giornata con lo step di mezzogiorno, e quel mezzogiorno è UTC** | B | S | Open P3 | `_normalize_forecast` sceglie lo step più vicino alle 12:00 come «rappresentativo della giornata di arrampicata». D'estate mezzogiorno è l'unica ora in cui nessuno scala. Attenuato da [[B335]] (la banda ora è cappata sul caldo) ma non chiuso. **Sotto-finding aggiunto da [[A275]] (2026-08-21):** sia il filtro della data sia la distanza da mezzogiorno leggono `dt_txt`, che OWM emette in **UTC** — a Kalymnos (UTC+3) lo step scelto sono le **15:00 locali**, a UTC+12 è il cuore della notte. Due difetti nello stesso `min()`. **Non corretto da A275 di proposito**, perché spostare questo step muove `condition_band`, che alimenta le patch di `/api/outdoor/strategy`: va deciso insieme a *quale* ora rappresenta una giornata di arrampicata, non di corsa. Nel frattempo `hourly[]` (A275) espone tutti gli step in ora locale vera, quindi chi ha bisogno del dato esatto non dipende più da questa scelta. |

**B-OUTDOOR-RELATIVE-LOAD — Load outdoor relativo al max grade (proposto, da B302, 2026-07-23)** 🟡 design. Oggi `compute_outdoor_load_score` (outdoor_log) pesa i tiri con `_GRADE_WEIGHT` **assoluto** per grado: un 6a pesa uguale per un climber 8a e per uno 6a. Intuizione di Daniele (corretta): il load dovrebbe essere **relativo all'abilità** — un 6a per un 8a-climber è recupero (load basso), per un 6a-climber è al limite (load alto). Serve ancorare il peso alla distanza dal max/assessment (es. `grade_gap(route, user_max)` → curva di sforzo). Tocca la formula D151 + probabilmente il session_load_score indoor per coerenza. **Da scopare con Daniele** (curva, floor/cap, retro-compatibilità dei report storici). Non urgente.

**A-COACH-V1c — Coach v1.2 (proposto, stub)** — residui da A-COACH-V1b: L4 per-exercise rationale (deferred da KB v1.0); refresh L3 su gap sources (Bechtel, MacLeod, Ilgner, Mobråten, Lattice MXEdge); streaming risposte (deferred da V1a); idee personalizzazione non scopate in V1b: stile coach configurabile (tecnico/motivazionale), milestone/PR nel contesto, riga readiness aggregata.

**B228 — Handler 402 globale in `api.ts`** 🟢 P2, B, effort S — centralizzare 402 → `router.push('/subscribe')` + toast. Frontend → branch + preview Vercel. *(Stava nella tabella §1.75: non è mai stato un item di go-to-market, è un difetto di gestione errori. Spostato qui da [[D276]].)*

**D230 — Lint frontend** 🟡 P3, D, effort M — **36 errori / 41 warning** (misurato 2026-08-16 da [[D276]]; era 34/41 il 13/08 e 30/38 prima ancora — la tendenza è di crescita lenta). Quasi tutto `react-hooks/set-state-in-effect`, la regola che il React Compiler porta con Next 16. La CI non lo blocca e la build passa. Un pomeriggio, branch + preview. *(Anche questo stava nella tabella GTM senza esserlo — spostato da [[D276]].)*

### Residui della remediation A245 / D254

Tutti generati durante [[A245]]. Erano finiti per errore nella tabella dello sprint
GTM (§1.75), che non c'entra: spostati qui il 2026-07-20 così la sezione Open è
la sola fonte di verità.

| ID | Titolo | Tipo | Effort | Stato | Note |
|----|--------|------|--------|-------|------|
| A-CLIMB-CLIENT-ID | **Id climb generato client-side e propagato al backend** | A | S | Open P3 | Registrato da A245 Phase B. Una climb loggata offline entra in UI con un **indice locale provvisorio**; il server assegna il suo indice reale al replay dell'outbox. Nella finestra fra replay e refetch, `DELETE /api/free-session/{id}/climb/{climb_index}` può colpire la riga sbagliata perché l'indice mostrato non è ancora quello del server. Mitigazione attuale: il delete fa rollback ottimistico su fallimento, e la finestra è breve. **Fix vero:** id client-side (UUID) generato al log, propagato nel payload e usato dal backend come chiave di identità al posto dell'indice posizionale. Tocca `free_session` router + `climb-logger.tsx`. |
| A-DELTA-EVENT-ENDPOINT | **Endpoint replanner a delta (evento singolo, non piano intero)** | A | M | Open P3 | Registrato da A245 Phase B. Oggi `POST /api/replanner/events` spedisce l'**intero** week plan e il backend lo persiste sovrascrivendo: per questo Done/Skip è escluso dall'outbox offline (riprodurre uno snapshot catturato ore prima sovrascriverebbe tutto ciò che è successo nel mezzo e potrebbe toccare sessioni passate, violando il pilastro di immutabilità). Offline oggi fallisce con messaggio esplicito. **Trigger:** aprire solo se i dati d'uso mostrano domanda reale di Done/Skip offline — non prima. Un endpoint a delta renderebbe l'evento accodabile in sicurezza e chiuderebbe anche la radice di F6. |
| B-RESOLVED-CASTS | **220 cast `as X` sul percorso dati più critico (F24)** | B | M | Open P3 | Residuo di F24 dopo A245 G-6, che ha reso onesto `ResolvedSession` (prerequisito: prima il tipo mentiva, quindi togliere i cast avrebbe solo spostato la bugia). Restano 220 `as X` in 63 file e 13 `as unknown as`, con picco in `session-card.tsx` (`resolved` è `Record<string, unknown> | null`). **Impatto:** un rename di campo lato backend compila verde e renderizza `undefined` nella schermata di allenamento. **Fix:** usare i nuovi `ResolvedSession`/`ResolvedBlock`/`ResolvedExerciseInstance` nel percorso guided/today e togliere i cast lì; il resto può restare. Ora è fattibile in sicurezza — il test che confronta i campi TS col Python del resolver fa da rete. |
| B-SESSIONCARD-DECOMP | **SessionCard resta un monolite da 1386 righe** (misurato 2026-08-16; era 1333 — cresce) | B | M | Open P3 | Residuo di F20 dopo A245 G-7, che ha chiuso la parte pericolosa (il walk sui blocchi duplicato *dentro lo stesso file*, con rischio di divergenza fra ordine mostrato e ordine eseguito). Restano le responsabilità mescolate: factory dei dati guidati, orchestrazione avvio + scrittura localStorage, dialog "Add Exercise" completo con fetch del catalogo, chiamate API dentro un componente di presentazione. **Fix:** estrarre `AddExerciseDialog` in un file proprio e la factory in `lib/guided-state-builder.ts` (unit-testabile). Puro spostamento di file: valore di manutenibilità, non di correttezza — da fare insieme a [[B-REFACTOR-COMPONENTS]]. |
| A-CLERK-PROVIDER-SCOPE | **Togliere ClerkProvider dal root layout (F27)** | A | M | Open P3 | Differito da A245 Phase F con misura, non a occhio. Clerk pesa ~227 KB su ogni route, ma **serve davvero** a `(main)`, `(guided)`, `onboarding`, `sign-in`, `sign-up` e alla root `page.tsx` (usa `useAuth`): le uniche pagine che ne farebbero a meno sono `/legal`, `/offline` e **`/demo`**. **Riformulata da [[D276]] (2026-08-16):** la motivazione scritta era «è la landing di acquisizione per il traffico Reddit/IG, quindi 227 KB in meno lì sono valore GTM reale» e «da fare prima di spingere traffico» — con il marketing in pausa ([[D274]]/[[D275]]) e Reddit chiuso, quel traffico non arriva. Resta un item di **performance**, non di acquisizione, e senza urgenza: il beneficio si limita a tre pagine che oggi quasi nessuno apre. **Perché non fatto ora:** `src/app/page.tsx` è la root e condivide il root layout con `/demo`, quindi escludere Clerk da `/demo` richiede di spostare la root in un route group e di replicare `ClerkProvider` + `SessionScopeGuard` in un layout condiviso per tutti gli altri gruppi — una modifica strutturale all'ingresso dell'app, non "perf leggera". Da fare in un brief proprio, prima di spingere traffico. |
| B-TIMER-TICK-SCOPE | **Il tick a 1 Hz ri-renderizza tutto ExerciseTimer** | B | M | Open P3 | Metà residua di F26 (l'altra metà, la memoizzazione, è chiusa in A245 F-8). `secondsLeft` è stato del componente e pilota la macchina a stati delle fasi, quindi ogni secondo ri-renderizza le 368 righe di JSX del timer per tutta la durata dell'esercizio — costo su batteria e INP sui telefoni di fascia bassa. **Fix:** pubblicare `secondsLeft` via `useSyncExternalStore` verso un piccolo display memoizzato, lasciando l'interval e i ref di fase dove sono. **Cautela:** è il componente più critico dell'app (rompe l'allenamento in corso se sbagliato) — serve verifica su device vero, non solo test. Nota: il finding originale stimava "~1000 righe", la misura reale è 368 di JSX senza sotto-alberi pesanti (il file intero è 1079 dopo [[B332]]). **Aggiornamento [[B332]] (2026-08-16):** il file è stato toccato per un difetto di correttezza — la macchina a stati avanzava il contatore delle serie al risveglio dal background — e ora ha la sua prima suite di test (`exercise-timer-background.test.tsx`, 5 test jsdom sulle transizioni). Quella rete non esisteva quando questo item è stato scritto, ed è precisamente ciò che rendeva rischioso il refactor: chi lo affronta oggi parte in condizioni migliori. |
| B-RESOLVE-ERROR-UI | **`resolve_error` non è ancora letto dal client** | A | XS | Open P3 | A245 E-3 (B17) marca lato backend le sessioni la cui risoluzione è fallita (`resolve_error: true` in `week.py` e `replanner.py`), distinguendole da «nessun esercizio compatibile». Il client non lo legge ancora: la session card resta identica nei due casi. Manca la metà frontend — stato d'errore esplicito con retry sulla card. Registrato subito per non lasciare orfano un campo che nessuno consuma (esattamente il pattern di B8/E-4). |

**B-REFACTOR-COMPONENTS — Batch di decomposizione componenti (differito da A245 v1)** 🟡 P3, qualità/manutenzione, nessun impatto utente. I 4 finding di [[D254]] esclusi da A245 per non gonfiare la Phase G, già la più pesante: **F55** `QuickAddDialog` (766 righe, tre wizard in un dialog con 18 `useState`), **F56** serializzazione del feedback — il contratto col motore — inline nella guided page (~100 righe), **F57** prop drilling a 3 livelli (page → DayCard con 27 prop/19 callback → SessionCard), **F58** `GuidedExerciseStep` (1093 righe, 8 modalità input con flag mutuamente esclusivi). *(Conteggi rimisurati 2026-08-16 da [[D276]].)* Da affrontare dopo A245, possibilmente insieme a G-6 (`SessionCard` monolite) se quel lavoro lascia fondamenta riusabili.

**B256 — Rimuovere `current_week_plan` (dedup hot state)** 🔴 high-risk, **scorporato da A221**. Ora che l'hot è `{N-1, N, future}` (post-A221), `current_week_plan` (~234 KB, byte-identico a `week_plans[this_monday()]`) è peso morto duplicato. Reindirizzare i ~10 reader backend a un helper unico `week_plans[this_monday()]` + sistemare lo stash `_prev_week_plan` (alimentato da `week_plans[N]`) + strip su prossima write. Riduzione attesa: hot Daniele 448→~250 KB. **Tocca multi-modulo** (`week.py`, `feedback.py`, `free_session.py`, `deps.py`, …) → richiede Fase 1 di analisi (mappa completa reader) + STOP prima dell'implementazione, branch + test invariante. Reader map di partenza: vedi D242 §2 + nota B256 nell'audit `docs/audit/D242_archive_weekplans.md`.

**D251 follow-ups residui (P2, non bloccanti)** — dall'audit `docs/audit/D251_fe_be_coherence.md` (§WARNING). W1/W3/W5/W6/W8/W9 chiusi da B272 (2026-07-08). Restano:
- **W2** — `self_eval` weaknesses senza editor in Settings (feature: serve un A-brief; pesa su ogni asse dell'assessment ma è congelato dopo l'onboarding).
- **W4** — convenzione grado boulder in `goal.target_grade` **contraddittoria by design tra 3 percorsi**: onboarding e start-new-cycle salvano il lead-calibrato (`BOULDER_TO_LEAD`, raw preservato in `target_boulder_grade`); il discipline-switch di `PUT /api/state` (A-NEW-MACRO) salva invece la convenzione Font (docstring `grade_mapping.py`: "Font for boulder"); il GoalEditor manda il Font raw che finisce nei benchmark lead-calibrati di `assessment_v1`. Serve una **decisione di design** (convenzione unica + normalizzazione server-side + eventuale migrazione dati) — NON un quick fix.
- **W7** — endpoint orfani. **Ridotto da 3 a 1 da [[D276]] (2026-08-16), verificando i tre contro il codice invece che contro il testo dell'audit:** `/api/user/recovery-code|recover` sono **già stati rimossi** da [[B320]] (il router lo dichiara in cima), e `/api/week/test-reminder-response` **non è affatto "solo test"** — `test-reminder-card.tsx:61` lo chiama via `respondToTestReminder`. Restava aperto solo perché nessuno era tornato a rileggerli. **L'unico vero orfano è `/api/reports/monthly`**: l'endpoint esiste, il wrapper client `getMonthlyReport` (`lib/api.ts:962`) esiste, e nessun componente lo importa → decidere fra pagina report mensile e rimozione di entrambi.

**Follow-up aperto di [[A266]] (P2)** — dato di produzione da verificare con l'utente, non lavoro di codice.
- **A266-P1 — Il dato loading-pin di `e60d7a0c` è internamente incoerente** 🔲 Open. 62,5/65 kg sollevati a una mano su 67 kg di peso corporeo (0,97 × BW, livello ~V12 secondo Lattice) da un utente che dichiara **7B** e le cui trazioni con zavorra sono **assistite di 22 kg** (`weighted_pullup_1rm_total_kg: 45` con BW 67). Le due cose non stanno insieme: chi non completa una trazione a corpo libero non solleva il 97% del proprio peso con quattro dita di una mano. Il valore passa il bound di plausibilità di [[A266]] (che filtra solo l'impossibile in assoluto, non l'incoerente col profilo) e satura l'asse a 100, spostando il piano lontano dalle dita. **Deliberatamente non "corretto" dal motore:** un guardrail sulla coerenza fra assi sarebbe una regola inventata, esattamente ciò che [[B321]] insegna a non fare. **Decisione di Daniele (06/08): il suo profilo NON è stato ricalcolato** — resta a `finger_strength: 51` finché il dato non è verificato con lui; il ricalcolo in produzione è stato applicato al solo `f8ff8569` (50 → 64, dato coerente). **Azione umana, non di codice:** è l'iscritto Reddit del 05/08, destinatario della nota del fondatore di [[A264]] — chiedergli di verificare il numero (probabile confusione fra carico esterno e carico totale, nonostante l'etichetta del wizard dica «external load only»). Se conferma, il dato resta e l'asse è corretto. **Nota collaterale:** il titolo della sezione nel wizard dice «Loading Pin Max Lift (**7s**)» mentre la chiave è `lp_max_lift_**5s**_*` — incoerenza cosmetica preesistente che vale la pena sanare quando si tocca quello step.

**Follow-up aperti di [[D274]] (P2, non bloccanti)** — dall'audit `docs/audit/D274_gtm_cohort_audit.md`. Sono strumenti di misura, non difetti di prodotto: restano aperti perché senza di loro i numeri su cui è stata presa la decisione «progetto personale» non sono più ricontrollabili da soli.
- **FUNNEL-REVENUE-LINE — `gtm_funnel.py` non ha mai mostrato che del denaro si è mosso** 🔲 **Open P2.** Aperto da [[D274]]. Lo script stampa `Paganti attivi: 0` / `Canceled: 3` e si ferma lì: l'unico addebito vero **e il suo rimborso in giornata** sono invisibili, e il netto lifetime (**−€0,47**) è emerso solo interrogando `Charge`/`Refund`/`BalanceTransaction` a mano. Manca una riga di ricavo lifetime — leggere lo stato delle subscription non basta, perché una subscription `canceled` non dice se è stata incassata o restituita.
- **VERCEL-ANALYTICS-UNREADABLE — il funnel pre-iscrizione è strumentato ma illeggibile** 🔲 **Open P2.** Aperto da [[D274]]. `public_assessment_view` / `_completed` / `_cta` e `demo_*` sparano su Vercel Analytics, ma il token CLI locale (`~/Library/Application Support/com.vercel.cli/auth.json`) risponde `invalidToken`. Da [[A256]] il server **non vede nulla** prima del submit, quindi Vercel è **l'unica** fonte per «assessment completato vs abbandonato». Rimedio: `vercel login`, oppure leggere la dashboard a mano. Finché resta così, la metrica di GTM-07 non è calcolabile.

### Assessment scoring — residui aperti di [[D260]]

> Stavano sotto un'intestazione «Recently closed», che è il motivo per cui erano
> facili da non vedere: spostati qui da [[D276]] (2026-08-16). La **ricerca** che
> mancava è stata fatta ([[C267]], `docs/research/assessment_scoring_research_2026-08.md`);
> restano aperti perché la ricerca decide *cosa* misurare, non *come cablarlo*.
> Nessuna riga di engine è stata scritta. `D260-P1b` è chiuso da [[A270]].

- **D260-P1a — Endurance senza test dedicato**: l'asse "Endurance" è `0.8 × power_endurance` + tenure + hang-duration; il design doc §2.2 specifica Repeaters/Critical Force. **Decisione presa ([[D261]] rev B, che supersede D07): arriva un test dedicato `test_endurance_intermittent`** — 8s:2s al 60% del max hang, a cedimento, punteggio = impulso normalizzato sulla massa corporea. Critical Force **non** è più la strada ([[D265]]), l'appeso a corpo libero **non** misura endurance ([[D263]]), il test continuo è escluso ([[D264]]). Open sul **come**: vedi [[D271]].
- **D260-P2 — saturazione anchor target-relative + soglie fragili + default "50"**: re-anchoring di Finger/Pulling (assoluto vs target-relative), curve continue al posto dei cliff <35/<50/>75, provenienza `measured|default` per axis. Open, **invalida gli score storici** → decisione di prodotto (domanda 1). Vedi `docs/audit/D260_tooltip_and_assessment_scoring.md` §8 per la sequenza fix proposta. **Parzialmente mitigata sul lato presentazione, non sul lato dato:** [[B304]] ha reso esplicito che 100 significa «≥ benchmark del tuo obiettivo», e [[A267]] aggiunge una seconda scala di lettura (Elite) senza toccare gli score memorizzati — il segnale in cima resta però censurato nel dato che il motore usa.
- **D271 — Analisi: `test_endurance_intermittent`** 📋 Analisi consegnata, implementazione **non** avviata. Copre punto d'inserimento nel flusso di assessment, modello dati additivo, il **problema dell'assistenza** (il 60% del max hang sta sotto il peso corporeo per chiunque stia sotto ~167% BW — cioè quasi tutti, autore incluso), gate di sicurezza, proposta di scoring dalle bande di [[D267]], impatto sul macrociclo con verifica snapshot-vs-live, piano di versioning e piano di test. `docs/audit/D271_endurance_test_analysis.md`. **Serve la decisione di Daniele su equipment/fallback e sul mapping banda→punteggio prima di scrivere codice.** STOP-gate (`assessment_v1` → `macrocycle_v1`).

---

## Recently closed (2026-10-04)

- **B381 — il pranzo spinta+braccia fissa la panca ai manubri** ✅ (2026-10-17, opzione 4 approvata da Daniele; solo catalogo) `upper_push_arms_lunch` blocco `chest_press`: pin `bench_press` → `dumbbell_bench_press` per tutti (carico per manubrio, da `working_loads` o ÷2 dal bilanciere). Attrezzi di `dumbbell_bench_press` invariati (`dumbbell`): aggiungere `bench` lo toglierebbe a chi dichiara manubri senza panca (Bkl, casa). Golden C272: 6 chiavi `upper_push_arms_lunch` (con soli manubri prima usciva `handstand_pushup_wall`/`overhead_press`). `fallback_exercise_ids` rinviato → B381-FALLBACK. Test: `test_b381_dumbbell_bench_lunch.py`.
- **B382 — togliere una sessione lascia vuoto quello slot; il giorno in falesia pianificato conta come giorno duro** ✅ (2026-10-17, fase 1 + STOP, OK di Daniele con D1 sì e D2 sì; solo backend, `user_owned` / `replanner_v1` / `planner_v2`). (a) `remove_session` registra `removed_slot` + `removed_owned` (l'app manda solo l'id, quindi prima una rigenerazione metteva un id diverso nello slot svuotato: gio 22/10 sul mirror). `user_owned.slot_emptied` → il planner rende lo slot non disponibile da oggi in poi e il merge non ci rimette nessuna sessione del motore; la sessione tolta può finire su un altro giorno (D1); togliere la propria quick-add non svuota lo slot; i record vecchi senza slot restano per id. D2: `remove_outdoor` annulla le rimozioni di quel giorno fatte prima dell'`add_outdoor`. (b) Il giorno in falesia dichiarato (fatto o non passato; quello della settimana prima per la spaziatura) conta nel cap dei giorni hard e nei gap hard/dita in PASS 1/1.5 (controllo simmetrico), 2.x, 3a, 3 e 2.7 (anche nella vista degli alert). Settimane senza falesie né rimozioni: identiche byte per byte (sim sul mirror 19/10-02/11). Test `test_b382_slot_empty_crag_hard.py` (21, 12 falliscono sul codice vecchio). Fuori scope, da aprire a parte: il planner non conta le sessioni hard GIÀ FATTE nei giorni passati della settimana corrente; nel log `adaptations` delle settimane dal 19/10 ci sono `add_custom_session` senza la sessione nel piano.
- **B387 — user_state più piccolo: codec di `current_week_plan`, esercizi custom senza i campi del catalogo, `GET /api/state` sottile** ✅ (2026-10-17, fase 1 + STOP, OK di Daniele; solo backend). (1) `backend/engine/state_codec.py` allo strato storage (file e Supabase): in scrittura, se `current_week_plan` è uguale a `week_plans[start_date]` si salva `current_week_key` al suo posto; in lettura si ricostruisce una **copia profonda** indipendente (stessa semantica del vecchio JSON: due copie uguali e separate, nessun alias). Copie divergenti, settimana archiviata o senza `start_date` → copia intera come prima. Puro, idempotente, gli stati vecchi si leggono uguali; kill switch `STATE_CODEC_PACK=0`. `scripts/athlete_context.py` passa da `unpack` (legge il blob grezzo). (2) `custom_session.storage_form`: le nuove custom si salvano senza `name/cues/video_url/category/load_model/load_unit/alt_sides` (e senza `notes` se è il default del catalogo) **solo se** l'esercizio si riproduce identico nel percorso di lettura reale; altrimenti resta com'è. La risposta di create/update non cambia. `outdoor.py` passa al replanner le custom arricchite come `/events`. (3) `GET /api/state` e la risposta di `PUT` non portano più `week_plans`, `current_week_plan`, `custom_sessions` (il frontend non li legge: test-guardia sul sorgente), con `_omitted` che li elenca; `?full=1` li rimette. Migrazione `scripts/migrate_b387_state_shrink.py` (dry run di default, gate di losslessness per utente, backup in `~/backups/`, PATCH con lock su `updated_at`, verifica dopo, `--rollback`). Test: `test_b387_state_shrink.py` (17); i test che ispezionano lo stato via API usano `?full=1`.
- **B389 — il report settimanale nomina la sessione saltata, non lo stub `regeneration_easy`** ✅ (2026-10-17, dal bug-inbox del coach «SCL vs piano», OK di Daniele; solo backend, `report_engine` in sola lettura). Il «mismatch» dei 6 giorni saltati (29/09–12/10) non era un errore di scrittura: `mark_skipped` sostituisce lo slot con uno stub di recupero e il completion log registra correttamente la sessione saltata (dal 06/10 lo stub la porta in `skipped_session_id`, A294; prima di A294 no). Il solo lettore sbagliato era `_build_adherence`, che elencava ogni skip come `regeneration_easy`: ora legge `skipped_session_id` → `skipped_original` → riga skip del completion log del giorno → vuoto per uno stub mai registrato. La riga SCL vuota del 25/09 è il log '' di un evento solo-slot, già corretto da A294 (`_logged_session_id`). Nessuna correzione dati: le sessioni passate restano immutabili e il log è già giusto. Test: `test_b389_skipped_ids.py` (6).
- **B386 — meno richieste all'apertura della PWA (fast-path, /today senza fan-out, prefetch pigro, cache statica)** ✅ (2026-10-17, dall'audit read-only del 17/10, approvato da Daniele; solo frontend, branch + preview). **Misura** (hook che /today monta a freddo, API contate con mock): **13 → 3 richieste** (prima: `/api/state` del dispatcher + `/api/state` + `/api/week/0` + prefetch `/api/week/{n+1}` + 7× `/api/free-session/history` + 2× `/api/subscription/status`; dopo: state + week + 1 subscription). (S6) il dispatcher `/` va diretto a `/today` quando il localStorage A245 ricorda `/today` (niente `getState()` né salto seriale); `/today` riscrive la destinazione ricordata sulla risposta del server (`/onboarding/welcome` se non c'è macrociclo), quindi un valore vecchio si corregge alla prossima apertura; offline e utenti senza destinazione invariati. (S7) `useFreeSessionsForDates` deriva i badge da `['state']` (`free_sessions` è già nel payload) — zero richieste, visibili anche offline; ripristina il campo `date` che la vista `/history` non portava, per cui da A245 F-5 le free session non comparivano mai nelle card di `/week`; `invalidateFreeSessionHistory` ora invalida `['state']` (anche dopo una sessione di mobilità, prima mai invalidata). `useSubscription` su React Query (chiave condivisa, `staleTime` 60 s, poll 5' non offline, `retry: false`, refetch al reconnect, non persistito): fail-closed B202/A245 C-1 invariato via `deriveSubscriptionResult` puro; rimosso `useSubscriptionStatus` inutilizzato. `useWeekPlan` prefetcha n+1 solo con `prefetchNext` (lo passa solo `/week`) e su idle. (S8) service worker: `/_next/static/*` (content-addressed) in `climb-agent-static-v1`, immagini in `climb-agent-images-v1`, cache che sopravvivono ai deploy (tetto FIFO 600 / 120 voci, immagini non hashate riconvalidate in background dopo 7 giorni); shell HTML/RSC restano nella cache per-build. `frontend/vercel.json` `ignoreCommand` → `scripts/vercel-ignore-build.sh`: confronta con `VERCEL_GIT_PREVIOUS_SHA` (ultimo deploy riuscito del branch), **non** `HEAD^` — un push «commit frontend + sync» deployerebbe solo l'ultimo commit e `HEAD^..HEAD` salterebbe il frontend; senza SHA, SHA fuori dal clone o errore git → build. Nota: i build annullati contano comunque nella quota deploy Vercel. Test: `b386-app-open-requests.test.tsx` (15), `b386-static-cache.test.ts` (10, incluso lo script su repo git temporanei), `billing-pause.test.ts` adattato al provider.
- **D285 — CLAUDE.md snellito, roadmap potata, lessons divise per mese** ✅ (2026-10-17, approvato da Daniele). CLAUDE.md 53,4 KB → ~19,5 KB: tabella endpoint → `docs/API_ENDPOINTS.md`, deployment/env/Clerk/Stripe → `docs/DEPLOYMENT.md`, pagine/routing → `docs/FRONTEND.md`, storia incidenti → `docs/SESSION_ISOLATION.md`, mappa doc → `docs/README.md`; in CLAUDE.md restano regole, STOP gate e una lista «Never» inline. `sync_status.py` scrive l'header endpoint in API_ENDPOINTS.md e le pagine in FRONTEND.md (sentinel + snapshot aggiornati, test nuovo: niente header endpoint duplicato in CLAUDE.md). `trim_roadmap.py`: ROADMAP 320 → 66 KB. `docs/lessons.md` 127 → 15 KB (mar–ago in `docs/lessons/AAAA-MM.md`, 256 lezioni tutte presenti). `.claude/commands/sync.md` riscritto.

  - **Modulo** `backend/engine/athlete_context.py`: puro, deterministico, in sola lettura. Assembla in un'unica fotografia:
    - posizione nel macrociclo (`macro_position`);
    - massimali per protocollo con confidenza `axis_confidence`;
    - carichi del giorno presi tali e quali da `anchored_load`;
    - `retest_status`;
    - stato delle sessioni chiave della settimana corrente e della prossima, senza debito riportato. Gli skip sono recuperati da `session_completion_log` per data. È un **fallback etichettato** finché A294 non porta `key_sessions_v1.compute_key_status`, che verrà usato in automatico. Requisiti per fase da DECISIONS, più tecnica in ogni fase e try-hard tranne che in deload;
    - guardie giorno per giorno: gap dita 48 h, test dita 72 h, tirata ≥85% e front lever prima di limit/strength_long, max 2 tirate pesanti in 7 gg, HIIT, cap hard. Sono ricavate dalle proprietà delle sessioni, mai dal load score;
    - varietà sulla finestra del resolver;
    - flag dei working load (`STALE` / `TEST_COPY`);
    - esiti try-hard dalle note outdoor (formato `T1 M7 FALL +1`).
  - **Script** `scripts/athlete_context.py`: legge Supabase live con soli `curl -X GET` (un test fallisce se il comando contiene un body o un metodo diverso) e stampa in italiano anche il blocco note di `docs/training/athlete_plan.md`. Con `--simulate` riproduce `POST /api/replanner/events` su una copia e confronta prima/dopo. Esempio: una custom con max hang martedì 06/10 sera declassa **power_contact_gym** (chiave limit_power) di mercoledì a regeneration_easy.
  - **Comando** `.claude/commands/custom-session.md` (`/custom-session`): regole uniche per comporre le custom di Daniele. Lo script si lancia sempre prima di proporre, i carichi vengono solo dagli anchor, ogni seduta ha un blocco tecnica o try-hard con un target misurabile, si simula, si mostra l'anteprima e si scrive solo dopo l'OK.
  - **Piano** `docs/training/athlete_plan.md`: obiettivo, limitatori (piedi → posizione → try-hard), progressione della forza, scale PIEDI/POSIZIONI/CADUTE, try-hard, settimane per fase, scale BW, tasche (mono medio sinistro, bi/tridito destra), Cima Nikita come un progetto e non come asse.
  - Sezione in CLAUDE.md, vocabolario §4.6. Test: `test_a293_athlete_context.py`, `test_a293_athlete_context_script.py`.
  - **Fix da review:** la guardia dita vede anche lo spacing del replanner (sessioni con tag dita entro `ceil(recovery_multiplier)` gg, finger_maintenance compresa); la tirata pesante e il front lever contano ogni finestra mobile di 7 gg, giorni pianificati compresi; cap hard 0 del deload rispettato (prima ripiegava sulla preferenza 4), deload e cap bloccano le righe max, tetto di intensità stampato; chiave tecnica da contenuto anche per le custom pianificate, ma i drill di riscaldamento non contano; limit PE `not_due` dentro il gap di 12 gg (try-hard al seguito); un A294 presente con firma/forma diversa è segnalato (`KEY_SESSIONS_A294_MISMATCH`), mai inghiottito; ricorrenze «Work» controllate (`HIIT_ON_GUARD_DAY`, `WORK_RECURRENCE_PHASE_CHANGE`); la simulazione stampa la nota di calcolo per lo schema della bozza e il comando la usa al posto della sezione anchor quando lo schema cambia; regola del dolore completa nel piano (2 → hang ≤85%, 3 → tetto 0.80).
  - **Non fatto qui:** il blocco per il prompt del composer in-app (A297/R7b), la sorgente `mirror` e `--resolve-today`. I drill di C271 non ancora in catalogo sono elencati nel piano e resi con l'id esistente più vicino.


## Recently closed (2026-08-09)


- **Backfill dei `load_score` outdoor storici** (dati di produzione, nessun codice) — applicata la formula [[B327]] a tutto lo storico dell'autore su richiesta esplicita: 28 entry di bookkeeping, 4 giorni in `week_plans`, 2 in `current_week_plan`. Le giornate di volume salgono (8 ago 22 → 33), quelle il cui punteggio era gonfiato dalla durata scendono (2 ago 39 → 30). Corretta anche la durata dell'8 agosto (120' → 240', il valore reale: i riposi non erano stati loggati) — con B327 il carico non cambia, ed è esattamente il punto.


---

## Audit storici — cosa resta di leggibile (D163/D172/D170)

> **Verificati contro il codice e chiusi da [[D269]] (2026-08-02);** l'elenco di cosa risultò già
> chiuso è stato archiviato da [[D276]] (2026-08-16) — restava in roadmap a occupare venti righe
> per dire che non c'era niente da fare. Testo integrale in `ROADMAP_v2.md` §D269 e §D276.
> Resta qui **solo** la tabella sotto: i finding che non sono più rintracciabili, che è una cosa
> da sapere, non da fare.
> Report originali (verificati esistenti, 2026-08-02): `docs/audit/D164/`,
> `docs/audit/outdoor_audit_D170.md`, `docs/audit/D-TESTUSER-VERIFY_report.md`, `docs/audit/D236/`.
> ⚠️ Il report **D163** (67 finding frontend) **non è nel repo**: la roadmap lo dava in
> `_archive/docs/frontend_audit_D163.md`, ma A198 lo ha cancellato dicendo di archiviarlo. Vive solo
> nella storia git — `git show be7ec67 --stat` per ritrovarlo. Stesso caso di D172 (vedi sotto): due
> audit citati per anni da una roadmap che puntava a file inesistenti.

**Cosa resta davvero aperto** (spostato dove è azionabile):

| ID | Titolo | Dove vive ora |
|----|--------|---------------|
| D172-16, D172-21 | 2 finding "structural/deferred" **non più leggibili**: il tracker `D172_findings_tracker.md` non è mai stato creato e nessun report D172 esiste nel repo (né in `_archive`). Non sono azionabili per ID: o si riapre un audit mirato o restano chiusi di fatto. | qui, come nota — nessun brief |
| `apply_day_add` non riceve `gyms` (D170 P1-04) | P3, M — serve refactor di firma. Il path utente principale è già coperto dal fix frontend di B173. | Backlog / exploration |
| Lint frontend, `session-card` monolite, test E2E full-pipeline | già tracciati singolarmente e con numeri più freschi | `D230`, `B-SESSIONCARD-DECOMP`, `R150` |

---

## Priority 1.75 — ~~Go-to-Market~~ → **chiusa: progetto personale**

> **Decisione di Daniele, 2026-08-13, su [[D274]] (2026-08-10) — vedi [[D275]]: climb-agent è uno strumento personale
> che resta pubblicamente disponibile. Il marketing è in pausa a tempo indefinito.**
>
> **Cosa NON cambia:** l'app resta live su climbagent.app, Stripe resta **LIVE**, la guardia
> fail-closed [[B202]] resta attiva, entrambi i piani restano acquistabili. Non si spegne niente —
> se qualcuno arriva e vuole pagare, può. Persone vere ci si allenano (Daniele incluso), quindi un
> difetto in produzione resta un difetto in produzione e la barra ingegneristica non si abbassa.
>
> **Cosa cambia:** *quale lavoro vale la pena fare*. Si costruisce per l'atleta che lo usa, non per
> un funnel. Niente brief di crescita, acquisizione o conversione se non li chiede Daniele, e
> «più utenti» non è un obiettivo implicito di nessun brief.
>
> Questa sezione resta in roadmap **solo** come memoria di ciò che è stato misurato e della
> condizione che riaprirebbe la decisione. Il log operativo di luglio, la timeline di aprile e le
> raccomandazioni del Council erano già stati archiviati in `ROADMAP_v2.md` §D269 da [[D269]].

### I numeri su cui è stata presa la decisione ([[D274]], 2026-08-10)

Report completo: `docs/audit/D274_gtm_cohort_audit.md`. Read-only: nessuna scrittura su Supabase,
Stripe o Clerk.

| | |
|---|---|
| Account totali | 20 |
| di cui **utenti esterni veri** | **11** (fuori: l'autore, 3 suoi account di test, 4 beta, 1 riga orfana) |
| Esterni che hanno completato il wizard e generato il macrociclo | **11 su 11** |
| Esterni con **≥1 sessione completata** | **1** |
| Esterni con ≥3 sessioni | **0** |
| **Paganti oggi** | **0** |
| **Ricavo netto lifetime** | **−€0,47** |
| Ultima sessione completata da un non-autore | **2026-04-21** |

**Il collo di bottiglia, misurato:** **−91%** su `macrociclo generato → prima sessione`. Non è
l'acquisizione e non è l'assessment — l'intento è intatto, 11 su 11 completano dodici step di
onboarding. È l'uso che non parte mai. Cause: `docs/audit/D273_first_session_activation.md`.

**Il ricavo, per esteso:** l'unico pagamento mai incassato ($4,99 il 14/06) è stato **rimborsato
quattro ore dopo**, da un utente con **zero sessioni completate**; Stripe ha trattenuto la
commissione. Va letto su `Charge`/`Refund`/`BalanceTransaction`, non sullo stato delle
subscription — vedi [[FUNNEL-REVENUE-LINE]].

**Canali:** Reddit è esaurito — r/bouldering rifiutato, **ban da r/climbharder l'08/08**, resta
solo r/indoorbouldering (un post al mese nel thread *Simple Questions*). Il post r/climbharder ha
prodotto **2 iscritti e 0 sessioni**.

### La sola condizione che riapre la decisione

**Un utente non-autore che completa 3 sessioni in 14 giorni** (`GTM-07`). Non è mai successo, e la
sua assenza è ciò che rende inutile ogni altro numero. Verifica: `python scripts/gtm_funnel.py`,
una volta al mese. Nessun altro lavoro GTM è schedulato.

### Attivazione — ricollocata, non abbandonata

> **Riclassificati da [[D275]] (2026-08-13).** [[D273]] li aveva scritti come *prerequisiti GTM* —
> sistemare l'attivazione prima di mandare traffico. Con il marketing in pausa quella cornice non
> vale più, ma **il difetto che descrivono è reale e colpisce anche Daniele**, quindi gli item
> restano: cambia la ragione per cui si fanno, non se si fanno.
>
> **Il fatto strutturale, in una riga:** delle 6 sessioni con parete a catalogo la più corta è
> di **70 minuti** ed è di scarico; le altre stanno a 85-100. Alla domanda «sono in palestra, ho
> mezz'ora, voglio arrampicare» il prodotto **non ha una risposta** — ed è una domanda che si fa
> Daniele almeno quanto un iscritto nuovo. Non è che i primi allenamenti non siano attraenti: è
> che il primo giorno molti utenti non ricevono affatto arrampicata (4 giorni su 7 per il profilo
> di Jason aprono con la prehab), e chi la riceve se la vede proporre in blocchi da 85 minuti nel
> momento sbagliato.
>
> **Nuovo criterio di priorità:** utile all'atleta che lo usa oggi → si fa. Utile solo a un utente
> ipotetico che non esiste → si rinvia. È la riga che separa ACT-01/ACT-03 da ACT-02/ACT-04.

| ID | Titolo | Tipo | Effort | Stato | Note |
|----|--------|------|--------|-------|------|
| ACT-01 | **Una sessione corta che si può fare subito** | A/C | M | 🎯 **Attivo** — ora per uso proprio | Da [[D273]], **riclassificato da [[D275]]**: non più "il prossimo passo GTM" ma la lacuna di catalogo più fastidiosa per chi lo usa davvero. Delle 6 sessioni con parete la più corta è **70 min** (ed è di scarico), le altre 85-100: «sono in palestra e ho mezz'ora» non ha risposta, né per un iscritto nuovo né per Daniele. Serve una voce di catalogo + un ramo nel planner. **STOP-gate** (`planner_v2`). |
| ACT-02 | **Non aprire con la prehab** | A | S | 🟡 Open P3 — **declassato** | Da [[D273]]. Se il giorno 1 di un utente nuovo cade su uno slot casa, il piano apre con cuffia dei rotatori ed eccentrici di gomito (successo a Jason). **[[D275]]:** è un difetto della *prima settimana di un utente nuovo* — con il marketing in pausa gli utenti nuovi sono ~1 ogni due settimane e Daniele non ci ripassa mai. Resta aperto perché è vero, non perché è urgente. **STOP-gate** (`planner_v2`). |
| ACT-03 | **Dire quando si arrampica la prima volta** | A | S | 🟢 Open P2 | Da [[D273]]. Se la prima sessione vera è fra 3 giorni, `/today` deve dirlo invece di lasciarlo dedurre. `nextSessionInfo` è **già calcolato** in `today/page.tsx` ma mostrato solo negli stati vuoti. **[[D275]]:** utile a chiunque apra `/today` in un giorno di riposo, non solo al primo accesso — quindi vale anche a marketing fermo. Frontend → branch + preview. |
| ACT-04 | **Un canale di ritorno (push o email)** | A | L | ⏸️ **Rinviato da [[D275]]** | Da [[D273]]. Oggi **non esiste**: l'unico `notify()` manda un Telegram a Daniele, il service worker non ha handler `push`, non c'è email transazionale. Era il prerequisito che rendeva utili ACT-01/02/03 **per una coorte** — e la coorte non c'è: 0 paganti, 0 esterni attivi. È l'unico item che richiede infrastruttura nuova, ed è esattamente il tipo di lavoro che [[D274]] dice di non fare adesso. Si riapre con `GTM-07`. |
| GTM-08 | **Trovare un canale dopo Reddit** | — | M | ⏸️ **Congelato da [[D274]]** (lo stato diceva «🔴 Open — da scopare» mentre la nota diceva già congelato: corretto da [[D276]]) | Registrato 2026-08-08 dopo il ban da r/climbharder. Due dei tre subreddit di arrampicata sono chiusi definitivamente. Candidati mai provati: forum/Discord di settore, gruppi Facebook di palestre, la palestra fisica di Daniele (volantino/QR — `docs/attribution_utm_convention.md` ha già la convenzione), passaparola dai ~~4 utenti attivati~~ (**[[D274]]: quei 4 sono l'autore, 2 beta tester e un solo esterno con una singola sessione — non c'è una base da cui parta un passaparola**), contenuto proprio (il `/assessment` pubblico è linkabile ovunque). **Vincolo appreso:** qualunque testo pubblico deve leggersi come scritto da un arrampicatore, non da un modello. **Non prima dell'attivazione** — il vincolo di D273 vale per ogni canale, non solo per Reddit. **[[D274]] (2026-08-10): congelato** — la ricerca di un canale non riparte finché non si verifica la metrica di GTM-07. |
| MKT-COACH | **Pubblicizzare il Coach AI** | — | S | ⏸️ **Congelato da [[D276]]** — si riapre con `GTM-07` | Proposto 2026-07-12, quando l'obiettivo era ancora convertire: il Coach è live, plan-aware e subscription-gated, quindi era la leva trial→paid più forte. Stava in **## Open** anche dopo [[D275]], che aveva riclassificato tutti gli altri item di crescita — è l'unico rimasto indietro, ed è esattamente il tipo di lavoro che [[D274]] dice di non fare adesso: non c'è coorte a cui annunciarlo (0 paganti, 0 esterni attivi) né canale su cui farlo (Reddit chiuso). **Il prerequisito tecnico è raggiunto e resta valido** (A-COACH-V1b, 2026-07-12: meteo reale allo spot, note personali, chips), quindi se `GTM-07` scatta si riparte dai canali, non dal prodotto. |
| GTM-STRIPE-TAX | **Stripe Tax registration** | Config | S | 🟡 Deferred | Riattivare a una di queste: (a) 10+ clienti EU paganti, (b) €5k di ricavo EU cumulato, (c) soglia OSS €10k in avvicinamento. Sotto, valgono le regole IVA domestiche italiane e Stripe Tax è scope creep. All'attivazione: 4 passaggi dashboard + 4 righe in `subscription.py:108-124` (`automatic_tax` + `tax_id_collection` + `billing_address_collection`). **Deciso ora:** $9.99/$4.99 sono **netti** (IVA aggiunta sopra all'attivazione). |

---

## Priority 2 — Sessioni boulder & board (residui)

> Auth (Clerk), persistenza (Supabase JSONB) e pagamenti (Stripe LIVE dal 2026-04-16, guard B202,
> hardening B226) sono **completi da mesi**: il dettaglio è archiviato in `ROADMAP_v2.md` §D269 ([[D269]],
> 2026-08-02). Restano qui i due item di catalogo che non c'entravano con i go-to-market blocker.

### A-B6 — Session pool boulder audit & completion

**Priority:** P2 | **Status:** Open | **Type:** D + A (audit + feature) | **Effort:** M

Audit `_SESSION_POOL_BOULDER`: verify ≥3 primary sessions per phase, limit_boulder exists, board session templates exist (board_limit, board_volume), PE sessions adapted (boulder_circuit, linked_boulders), climbing_routes excluded from boulder pool, technique sessions adapted, all_round pool = union of lead + boulder.

### A-B8 — Board session templates (guided)

**Priority:** P2 | **Status:** Open | **Type:** A (catalog + template) | **Effort:** M

Three new session definitions: `board_limit_session` (6-10 problems at max, 3-5 min rest), `board_volume_session` (15-20 problems 2-3 below max, 1-2 min rest), `board_pe_session` (4x4 format, 3-4 below max). Equipment: board_kilter/board_moonboard/board_other. No board API integration.

## Priority 2.25 — Code Quality & Hardening

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R142 — Magic Numbers Extraction

**Priority:** P2.25 | **Status:** Open | **Type:** R (refactor)

- Estrarre magic numbers da `progression_v1.py` in named constants
- Spostare tabelle grade-to-score e axis weights da `assessment_v1.py` in JSON catalog

**Rischio:** BASSO — estrazione costanti

## Priority 3 — UI polish

### Warmup Circuit add-on

**Status:** Open — design pending | **Effort:** M
Same architecture for pre-session dynamic warmup (30s work / 10s transition).

### A-PHASE-EDIT — Phase Duration Editor in /plan

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

UI in `/plan` (controllo accanto al nome di ogni fase del macrociclo: +/- buttons o slider) che permette all'utente di aumentare o ridurre la durata di una fase. Le settimane recuperate o necessarie vengono redistribuite automaticamente alle altre fasi rispettando le caps A218 (con surplus distribution B). Il `total_weeks` resta invariato (la deadline non si sposta).

**Policy decisa (Daniele 2026-05-20):**
- **NO hard block, solo soft warning.** L'utente è libero di portare qualsiasi fase a 0 settimane.
- Warning sotto floor: *"Riducendo Base sotto 3 settimane potresti compromettere la capacità aerobica di base. Per atleti advanced (8a+ lead, 7C boulder) con macrocicli completati nei 6 mesi precedenti, una base abbreviata è accettabile. Continuare?"*
- Caps A218 diventano **soft default** (valori proposti dall'algoritmo), non hard cap.
- L'override manuale è persistito in `macrocycle.phases[].manual_override=true` e sopravvive a rigenerazioni del macrociclo finché l'utente non cambia `goal.target_grade` o `goal.deadline`.

**Decisioni di UX ancora aperte** (da chiudere nel brief A-type proper):
1. Controllo: pulsanti +/- accanto al nome fase, slider per fase, o modal editor full-screen?
2. Visualizzazione del ricalcolo: preview live mentre l'utente modifica, o conferma esplicita?
3. Cosa succede se l'utente porta una fase a 0? Cancella la fase dal macrociclo o la tiene a 0w (skip)?
4. Reset to default: pulsante "ripristina suggerito A218" per ogni fase?

**Risk:** HIGH — tocca `macrocycle_v1.py`. Brief A-type proper richiede mandatory analysis phase + STOP gate (regola CLAUDE.md non-negoziabile). Suggerire `/model opus` per Phase 1 analysis.

**Predecessore:** A218 (A-MACRO-CAPS), B254 (one-shot manual override per Daniele).

**Origin:** Daniele richiesta diretta 2026-05-20 — caso d'uso: advanced climber che vuole base abbreviata dopo cicli completi precedenti, evitando detraining gap.

### End-of-cycle reminder UX

**Priority:** P3 (post-launch) | **Status:** Open | **Type:** A (frontend) | **Effort:** S
**Origin:** A218 / KB Q4-d red flag — without a reminder, advanced users who lose 2-3 weeks between cycles begin detraining (Hörst, Lattice).

When a macrocycle reaches its final deload week (or its `end_date` is within the next 7 days), surface a reminder card on `/today` and `/plan`: *"Your training cycle is ending. Want to start a new one?"* Links to the existing `start-new-macrocycle-dialog` flow (D-NEW-MACRO).

The user does the manual re-trigger (block-stacking is intentionally not automatic in v1, per A218 design doc). The reminder bridges the gap between automatic prompt and inactive cycle.

**Implementation hints:**
- Use `current_phase_and_week()` to detect "deload phase, last week".
- Or compare `macrocycle.end_date - today < 7d`.
- Dismissable; remember dismissal in `state.preferences.dismissed_reminders` keyed on `macrocycle.start_date` so it doesn't re-show after the user opts out.

### Smart planner availability suggestions

**Priority:** P3 (post-launch) | **Status:** Open | **Type:** A (engine + frontend) | **Effort:** M

When the planner struggles to fit sessions into the user's availability (e.g., too many skips, spacing violations, key sessions dropped), surface proactive suggestions:
- "Your plan needs 2 hard climbing sessions per week, but you only have 1 gym slot. Consider adding a gym day on Wednesday."
- "Finger training on Monday and Wednesday violates the 48h spacing rule. Try moving Wednesday's session to Thursday."

**Implementation:** After `planner_v2` generates a week, run a diagnostic pass checking: sessions dropped vs requested, spacing violations resolved by skipping, equipment mismatches forcing substitutions. If diagnostic score is below threshold → generate suggestion(s) as structured data. Frontend: suggestion card on Week view ("Optimize your schedule" expandable). User can accept → triggers availability update + replan.

**Depends on:** Nothing (standalone diagnostic layer on top of existing planner).
**Origin:** GTM-01 dry-run insight (2026-04-01) — if the plan looks weak because of bad availability input, the user blames the app, not their schedule.

---
