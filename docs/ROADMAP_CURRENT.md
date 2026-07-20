# climb-agent — Active Roadmap

> Last updated: 2026-07-20 (A239 — milestone system. Piano gamification: A-GAMIFY-00 approvato → A234 daily tips, A235 phase progress, A236 heatmap, A239 milestones. Restano A-GAMIFY-04 (opzionale) e A-DAILYTIP-V2.)
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Open

**A-COACH-KB-V1 (in progress, Phase B, Session 7a of 7b complete)**
- Phase A audit: `docs/research_kb/coach_kb_v1_audit.md` (commit `75bd4f5`)
- Phase B output: `backend/coach/knowledge/` (Session 1: commit `1971da1`; Session 2: commit `1415b2f`; Session 3: commit `7a98d05`; Session 4: commit `e682efb`; Session 5: commit `f87cdd0`; Session 6: commit `bc3db55`; Session 7a: TBD)
- Steps 1-4 ✅ (scaffold 24 file, L0 11 safety rules, L1 voice, L2 35 decision index)
- Step 5 ✅: Batch A ✅ (files 01-05), Batch B ✅ (files 06-09), Batch C ✅ (files 10-12), Batch D ✅ (files 13-15: tapering/redpoint, female/age/youth, goal-setting/motivation), **Batch E ✅** (files 16-20: assessment interpretation, readiness/overtraining, equipment fallback, lifestyle integration, return-to-training)
- **Step 6 ✅** — `docs/coach/design.md` (2865 word ≈ 3725 tok, target 3000-4000): 9 sezioni (scope, architettura multi-layer, layer spec + catalogo 20 file L3, loading strategy, firewall 14 D-ID engine-internal, citation policy + gap markers, fase A→B→next, governance, open items v1.1). Sostituisce la dangling reference a `_archive/docs/coach_knowledge_base_spec.md` (ghost file confermato D-COACH-AUDIT).
- **Step 8 ✅** — `backend/coach/routing.py` (BM25-style keyword router su `_index.md`, max 3 file, fallback `01_periodization`+`15_goal_setting_motivation`, co-load rule `10_injuries_fingers`→`02_finger_strength` se keyword finger-strength). Tests: `backend/tests/test_coach_routing.py`, 39 test passing (20 per UC + 19 ranking/fallback/cap/co-load/robustness).
- Step 9 ⏳ (28-question regression scoring con Daniele), Step 10 ⏳ (final v1.0 lock + roadmap entry)
- Est. remaining: ~2.5h in Session 7b con Daniele (Steps 9 + 10)
- Step 7 (L4 schema + coach_rationale catalog edits) **DEFERRED to v1.1** per brief scope-change
- Risk register: see brief; key items = books not yet acquired (MacLeod/Ilgner/Mobråten/Christophersen Part 1+2/Bechtel pp.31-90/Lattice 2019 taper newsletter/Hörst redpoint chapter/Bechtel Integrated Strength/Lattice MXEdge protocol/Mujika & Padilla 2000a/b detraining primaries) → L3 files 06, 07, 10, 11, 13, 15, 16, 18, 19, 20 ship v1.0 with explicit `**v1.0 coverage gap**` markers for v1.1 refresh
- **Engine-internal D-ID firewall (D03, D04, D05, D06, D08, D13, D23, D32, D42, D61, D62, D63, D88, D90) honored across all 20 L3 files.** File 16 (assessment interpretation) explicitly firewalls D88/D90 in its v1.0-gap block: the brief mentioned them but they govern engine scheduling/protocol-selection internals, not user-facing knowledge. Verified via `grep -nE "\bD(03|04|05|06|08|13|23|32|42|61|62|63|88|90)\b"` — only hit across Batch E is the firewall block itself in file 16.
- Known token undershoot/overshoot vs §4.6 audit targets: Batch A files ~40-60% of upper-band; Batch B files 06+07 ~25%/13% under, files 08+09 spot-on; Batch C files 10+11+12 ~13%/5%/7% under; Batch D file 13 +12% over, file 14 +2% (spot-on), file 15 +25% over; **Batch E file 16 +10% over (4419 tok vs 4000 target), file 17 -4% (4334 vs 4500 target, spot-on), file 18 +23% over (4310 vs 3500 target — substitution matrix density), file 19 +19% over (4176 vs 3500 — concurrent-training pairings + central fatigue + cut-order detail), file 20 +17% over (4666 vs 4000 — three-band decision tree + D71 reset math + injury-driven differential)**. Content complete and source-anchored; deviation is content-driven, not padding. Documented for v1.1 refresh decision.

**MKT-COACH — Pubblicizzare il Coach AI (proposto, 2026-07-12)** 📣 — il Coach è live in prod, validato sul campo (B-COACH-CONTEXT-FIX) e ora plan-aware al 100%: è il feature differenziante più forte dell'app → va comunicato. Candidati: annuncio ai beta tester / utenti esistenti (email o Telegram), card/banner in-app che presenta il Coach ai non-subscriber (è subscription-gated → leva di conversione trial→paid), post social / changelog pubblico, sezione dedicata sulla landing. Da scopare con Daniele: canali, messaggio, timing. Prerequisito tecnico ✅ raggiunto: A-COACH-V1b chiuso (2026-07-12) — il demo include meteo reale allo spot, note personali e chips.

**A-COACH-V1c — Coach v1.2 (proposto, stub)** — residui da A-COACH-V1b: L4 per-exercise rationale (deferred da KB v1.0); refresh L3 su gap sources (Bechtel, MacLeod, Ilgner, Mobråten, Lattice MXEdge); streaming risposte (deferred da V1a); idee personalizzazione non scopate in V1b: stile coach configurabile (tecnico/motivazionale), milestone/PR nel contesto, riga readiness aggregata.

**B289 — `used_grade` accettato e scartato per 39 esercizi `grade_relative` su 40 (da B288)** 🟡 backend, 🔴 STOP-gate (`progression_v1.py`). In `apply_feedback` il ramo `grade_relative` è gated su `exercise_id == "limit_bouldering"`: per gli altri 39 esercizi `grade_relative` del catalogo il grado inviato dal client viene accettato e buttato in silenzio, quindi nessuna memoria di grado e nessuna progressione. Non è un fix di coda: serve **decidere la chiave di setup per esercizio** (`limit_bouldering` usa `surface`, che per un drill di tecnica non ha senso) prima di scrivere `working_loads` per tutti. Trovato dall'audit dei path di feedback in [[B288]], tenuto fuori da quel brief di proposito. Prerequisito: censire i 39 esercizi e raggrupparli per semantica del grado.

**B-QUICKADD-ADJUSTMENTS — Mostrare all'utente perché la sessione quick-add è stata declassata (da B287/R-5)** 🟡 frontend-only, piccolo. Dopo B287 il quick-add **applica** il gap dita 48h e l'hard cap invece di limitarsi ad avvisare: la sessione aggiunta può diventare `regeneration_easy`. Il backend restituisce già il motivo machine-readable in `POST /api/replanner/quick-add` → `adjustments: [{date, slot, action, reason, previous_session_id, session_id}]` (`reason` ∈ `finger_spacing_downshift` | `hard_cap_downshift`), ma **nessuna UI lo rende** — oggi l'utente vede solo una sessione diversa da quella che ha scelto. Serve un toast/inline note nel dialog Quick-Add che spieghi il declassamento (protezione recupero dita / cap settimanale superato). Tocca `frontend/` → branch + preview Vercel obbligatori.

**D254 — Full repo review (frontend + backend), 81 finding** 📋 audit read-only, `docs/audit/D254_full_repo_review.md`. Review esterna del 2026-07-20, rimasta untracked a root come `REVIEW.md` fino all'hygiene pass dello stesso giorno — motivo per cui i suoi finding frontend non erano mai stati triati (violava la regola "i finding di un audit SONO item di roadmap"). **Esito triage:** 9 già chiusi (B1/B2/B11/B13 → [[B285]]; B3/B6/B7/B9/B18 → [[B287]]), **67 schedulati in A245** (63 dal brief + F28 e F13/F14/F15/F27 aggiunti al triage), 4 differiti (F55-F58, vedi sotto). **3 critici frontend ancora aperti** e tutti nella promessa core del prodotto: **F1** (a freddo e offline la PWA non si apre — lo scenario "apro la PWA in falesia senza campo" semplicemente non funziona), **F2** (navigazioni offline falliscono in silenzio; il guided, unico flusso costruito offline-ready, non è avviabile offline), **F3** (in falesia si cancella una via con un tap su target da ~22px senza conferma → dati che alimentano il closed-loop). Coperti da A245 Phase A (F3) e Phase B (F1, F2).

**A245 — REVIEW-REMEDIATION-V1: bonifica consolidata frontend + backend** 🔨 P1→P3, mega-brief in 7 fasi (A→G), **una fase per sessione con OK esplicito tra una e l'altra**. Chiude 67 finding di [[D254]]. Prerequisiti soddisfatti: [[B285]] e [[B287]] entrambi in `main`. **Phase A** ✅ Done e mergiata in `main` (preview iPhone PWA verificata da Daniele, 2026-07-20 — chiude F3, F6, F7, F11, F12, F31, F32, F33, F39, F40, F41, F42, F61, F62) · **Phase B** ✅ Done e mergiata in `main` (preview verificata da Daniele, 2026-07-20 — chiude F1, F2, F4, F5, F21, F44 + **F22 tirato dentro** perché stesso file, una sola preview) · **Phase C** ✅ Done (branch `brief/A245-phase-c` — chiude F8, F9 *(solo metà client: la metà backend era già chiusa da [[B285]], verificato)*, F10, F28, F37, F51; **in attesa di verifica preview Vercel prima del merge**) · **Phase D** ✅ Done (branch `brief/A245-phase-d` — chiude F16, F17, F18, F29, F30, F38, F45, F46, F47, F48, F49; **in attesa di verifica preview Vercel prima del merge**. Fuori scope dichiarato dentro F38: la fusione experience+discipline e weaknesses+goals, che l'audit dava come «valutare» = decisione di prodotto, non fix) · **Phase E** ✅ Done (branch `brief/A245-phase-e`, backend-only — chiude B4, B8, B10, B15, B16, B17, B19; B11/B12/B14 verificati già chiusi da [[B285]]. **E-4 risolto con l'opzione (c)**: rimosso il ramo `adjustments` morto, cooldown tenuto, doc allineata, attivazione tracciata in [[A-CLOSED-LOOP-ACTIVATION]] con sunset. E-6 in commit isolato) · **Phase F** dedup + perf leggera (+F13/F14/F15/F27) · **Phase G** correttezza data-layer + i due refactor pesanti (**meno F22**, chiuso in Phase B). Fasi A/B/C/D/F/G toccano `frontend/` → branch `brief/A245-*` + preview Vercel approvata prima di ogni merge; solo E è backend-only. **Fuori scope dichiarato:** B5 (timezone del server nei path caldi — serve un A-brief proprio + D-audit prima di utenti US) e F55-F58.

**B-REFACTOR-COMPONENTS — Batch di decomposizione componenti (differito da A245 v1)** 🟡 P3, qualità/manutenzione, nessun impatto utente. I 4 finding di [[D254]] esclusi da A245 per non gonfiare la Phase G, già la più pesante: **F55** `QuickAddDialog` (776 righe, tre wizard in un dialog con 18 `useState`), **F56** serializzazione del feedback — il contratto col motore — inline nella guided page (~100 righe), **F57** prop drilling a 3 livelli (page → DayCard con 27 prop/19 callback → SessionCard), **F58** `GuidedExerciseStep` (1053 righe, 8 modalità input con flag mutuamente esclusivi). Da affrontare dopo A245, possibilmente insieme a G-6 (`SessionCard` monolite) se quel lavoro lascia fondamenta riusabili.

**B256 — Rimuovere `current_week_plan` (dedup hot state)** 🔴 high-risk, **scorporato da A221**. Ora che l'hot è `{N-1, N, future}` (post-A221), `current_week_plan` (~234 KB, byte-identico a `week_plans[this_monday()]`) è peso morto duplicato. Reindirizzare i ~10 reader backend a un helper unico `week_plans[this_monday()]` + sistemare lo stash `_prev_week_plan` (alimentato da `week_plans[N]`) + strip su prossima write. Riduzione attesa: hot Daniele 448→~250 KB. **Tocca multi-modulo** (`week.py`, `feedback.py`, `free_session.py`, `deps.py`, …) → richiede Fase 1 di analisi (mappa completa reader) + STOP prima dell'implementazione, branch + test invariante. Reader map di partenza: vedi D242 §2 + nota B256 nell'audit `docs/audit/D242_archive_weekplans.md`.

**B-SUB-TRIAL-RECONCILE — Riconciliazione subscription `trialing` scadute (proposto, da D243/B258)** 🟡 revenue-leak latente. `check_subscription` tratta `trialing` come attivo (`is_active = status in {trialing, active}`) **senza ricontrollare `trial_end`**: se un webhook Stripe (`customer.subscription.updated/deleted`) non arriva, una riga resta `trialing` a tempo indefinito → accesso gratuito permanente. Caso reale osservato: alias `daniele.somensi@ferrero.com` ancora `trialing` con `trial_end=2026-05-01` (scaduto >1 mese). Stripe è source-of-truth e i webhook B226 sono hardened (dedup + retry), quindi il rischio è basso ma non nullo. Opzioni: (a) guard difensivo `status==trialing && trial_end < now → deny` (fail-closed, ma rischia falsi-deny se l'orologio diverge dalla transizione Stripe); (b) job/endpoint di riconciliazione che ripaga lo stato da Stripe per le righe `trialing` scadute; (c) solo monitoraggio (admin dashboard flag "trialing scaduto"). **Da decidere con Daniele** — backend-only, tocca `subscription_guard.py` (sensibile, paywall). Non urgente.

_Nessun follow-up D238 aperto. Tutti i finding del report `docs/audit/D238_test_load_calculation.md` sono chiusi: B251 (Fix 1 catalog), B252 (Fix 3 protocol_version), B253 (Fix `tests_source` legacy backfill)._

_Nessun follow-up D239 aperto. Audit conferma "no bug" — 3 possibili miglioramenti cosmetici suggeriti (vedi §10 di `docs/audit/D239_quote_render_audit.md`) sono P3 e non bloccanti._

_D240 next step **chiuso da C239** (2026-05-26): le 25 proposte KB (cue_036→cue_060) sono state mergeate nel catalog._

**D251 follow-ups residui (P2, non bloccanti)** — dall'audit `docs/audit/D251_fe_be_coherence.md` (§WARNING). W1/W3/W5/W6/W8/W9 chiusi da B272 (2026-07-08). Restano:
- **W2** — `self_eval` weaknesses senza editor in Settings (feature: serve un A-brief; pesa su ogni asse dell'assessment ma è congelato dopo l'onboarding).
- **W4** — convenzione grado boulder in `goal.target_grade` **contraddittoria by design tra 3 percorsi**: onboarding e start-new-cycle salvano il lead-calibrato (`BOULDER_TO_LEAD`, raw preservato in `target_boulder_grade`); il discipline-switch di `PUT /api/state` (A-NEW-MACRO) salva invece la convenzione Font (docstring `grade_mapping.py`: "Font for boulder"); il GoalEditor manda il Font raw che finisce nei benchmark lead-calibrati di `assessment_v1`. Serve una **decisione di design** (convenzione unica + normalizzazione server-side + eventuale migrazione dati) — NON un quick fix.
- **W7** — endpoint orfani: `/api/reports/monthly` (endpoint+client mai cablati in UI → decidere: pagina report mensile o rimozione), `/api/user/recovery-code|recover` (morti post-Clerk → candidati a rimozione), `/api/week/test-reminder-response` (solo test). Toccano endpoint count/docs.

---

## Recently closed (2026-07-20)

- **B288 — LOAD-CAPTURE: il carico usato non arrivava mai al motore** ✅ (bugfix, 🔴 HIGH RISK — `progression_v1.py`; branch `brief/B288-load-capture`, STOP gate approvato da Daniele su tutte e 3 le voci backend). Origine: report utente "nel reverse wrist curl mi propone sempre 2kg anche se segno che ne uso 5". **Diagnosi sui dati di produzione** (Supabase, read-only): entry `working_loads` di `reverse_wrist_curl` ferma al 2026-03-30 con `last=2.0`, mentre l'archivio (23 settimane) mostrava la sessione del 2026-06-29 `completed: true` **senza** `used_external_load_kg`. Tre cause indipendenti, tutte necessarie. **(1) Il dialog di feedback di `/today` e `/week`** costruiva gli item come `{exercise_id, feedback_label, completed}` e basta — `apply_feedback` scarta in silenzio ogni item privo di `used_*`, quindi chiudere una sessione da lì non ha **mai** scritto un carico; il dialog non aveva nemmeno un campo kg. Nuovo `lib/feedback-items.ts` come unica fonte di verità per la costruzione degli item + campo kg per esercizio prefillato col suggerito (stesso contratto del player guidato). **(2) `guided-exercise-step`**: la `useEffect` di prefill dipendeva dall'oggetto `exercise`, quindi riscriveva il campo carico col suggerito a ogni update (cambio set, nota), cancellando quanto appena digitato — il prefill è un cold start, non un sync: ora parte una volta per esercizio. **(3) Memoria a 60 giorni**: per un prehab programmato ogni 2-3 mesi il dato scadeva sempre prima del giro successivo → ritorno perenne al fallback `EXTERNAL_LOAD_FALLBACK_FIXED_KG`. Finestra allargata (`EXTERNAL_LOAD_FRESHNESS_DAYS`) per il solo `external_load` non-unilaterale; **non** disabilitata: `_is_fresh` è anche la guardia su data mancante e su entry future (B-fix-CORE) e la prima versione con `freshness_days=None` ha resuscitato quel bug — **2 test l'hanno intercettata**. Gate a 60 giorni invariato su max-hang/hangboard/loading-pin/grade. **Altri 3 path trovati dall'audit dei feedback:** "Mark remaining as OK" chiudeva gli esercizi mai visitati senza carico (ora usa il suggerito); il retry offline in `/today` ricostruiva gli item a mano tenendo solo `usedLoadKg`/`usedGrade` — un POST fallito degradava in uno lossy (total load, split R/L, set/reps, superficie, note, misure test) e poi cancellava la copia locale più ricca (ora riusa lo stesso builder); **carico `0 kg` scartato** perché `a or b` legge lo 0 come assente (`_first_not_none` + test di regressione verificato rosso pre-fix). Fuori scope per decisione esplicita: `used_grade` sui 39 `grade_relative` → [[B289]]. **Nota di processo:** brief eseguito durante un districamento git — un'altra sessione Claude sullo stesso working tree aveva impacchettato 2 file di questo brief nel proprio commit; lezioni in `docs/lessons.md`. Test: 4 nuovi (0 kg), 2 aggiornati (pinnavano i 60 giorni), 1 aggiunto (oltre la finestra il fallback vale ancora).

- **B-TEST-COACH-ISOLATION — I test scrivevano in `backend/data/` (suite che falliva a orologeria)** ✅ (test-only, backend). Trovato dall'hygiene pass del 2026-07-20. I moduli di test isolavano `STATE_PATH` ma **nessuno** isolava gli altri sink di scrittura di `storage_file`: log dir, dir per-utente, week archive, recovery code. Ogni run appendeva al vero `backend/data/logs/coach_messages.jsonl` e creava directory sotto `backend/data/users/` — entrambi **gitignored**, il che rendeva il danno invisibile a `git status` (le 9 dir UUID residue lì dentro erano proprio quello). **Sintomo:** superati i 30 messaggi utente nello stesso giorno UTC scattava `DAILY_MESSAGE_LIMIT` (`coach/service.py`) e 3 test di `test_a243_adhoc_builder.py` fallivano con 429 **su codice immutato**, per poi tornare verdi dopo la mezzanotte UTC. Una suite il cui esito dipende da quante volte l'hai lanciata oggi è peggio di una rossa: insegna a non fidarsi dei fallimenti veri. **Fix:** fixture `isolate_storage_write_dirs` autouse in `conftest.py` che redirige `DATA_DIR`/`USERS_DIR`/`_CODES_PATH` su `tmp_path` (tutte risolte come attributi di modulo a runtime, nessun altro modulo le importa direttamente). `STATE_PATH` **deliberatamente non** rediretta: i moduli che la usano puntano già alla propria copia tmp della fixture e un override globale litigherebbe con loro. `test_multiuser.py` importava `USERS_DIR` a import-time → reso dinamico (era anche il creatore delle dir residue). **Verifica:** 10 run consecutive del file coach tutte verdi (prima ne bastavano ~7 per innescare il 429), 0 righe scritte nel log condiviso, 0 dir utente toccate. Suite 2669 verde.

- **B287 — REPLANNER-IMMUTABILITY: violazioni immutabilità + disciplina del pool** ✅ (bugfix, 🔴 HIGH RISK — `replanner_v1.py` + router replanner/feedback; branch `brief/B287-replanner-immutability`, backend-only, STOP gate su Phase 0 e prima di ogni push). Origine: review esterna 2026-07-20. **Tutti e 7 i finding verificati contro il codice reale prima di implementare** (nessuna premessa smentita), poi due tranche indipendentemente deployabili. **Tranche 1 — immutabilità.** **R-1 (High):** il branch `set_availability` di `apply_events` chiamava `generate_phase_week` e riassegnava `updated["weeks"]` **senza alcun preserve** → ogni sessione done/skipped della settimana distrutta, violazione diretta del pilastro. Ora passa da `regenerate_preserving_completed` col nuovo `_preserve_floor()` = `max(today, start_date della settimana)` (settimana corrente → passato congelato a oggi; settimana futura → suo lunedì, coi giorni completati in anticipo salvati dal merge a livello sessione). **R-2 (High):** `/override` aveva il guard B257 dal B257, `/events` no — e `set_availability` è raggiungibile da entrambi. Guard aggiunto sullo `start_date` fornito dal client, **ristretto ai soli event type che rigenerano** (`_REGENERATING_EVENT_TYPES`; `set_availability` è l'unica call site di `generate_phase_week`): un guard blanket avrebbe respinto anche il `mark_done` retroattivo su settimana passata, che è *explicit user edit* — l'unica eccezione ammessa dal pilastro — e che la UI permette ogni volta che esiste un piano salvato (`past_week_unavailable` scatta solo in assenza di piano). **R-3 (High):** `_build_session_pool(phase_id)` chiamato senza `discipline` → default `"lead"`: il replanner leggeva la disciplina dallo snapshot per i **pesi** e la dimenticava la riga dopo per il **pool**. Forward-fix only (mirror di `generate_macrocycle`), nessuna correzione dati. Blast radius misurato su Supabase prod (read-only): **5 utenti su 17** — 1 boulder + **4 `both`** (`both`/`all_round` hanno un pool a sé, non ricadono su lead) — ma **impatto reale zero**: il frontend non invia mai `set_availability` (path raggiungibile solo via API diretta). **R-4 (Medium):** il fallback per giorno-della-settimana di `merge_prev_week_sessions` riscriveva `copied["date"]`, spostando sessioni completate di un'altra settimana su date passate → storia di allenamento fabbricata e `_attach_feedback` che lega il feedback sbagliato via chiave `(date, session_id)`. Sotto il preserve floor ora **solo match a data esatta** (con warning quando i range non si sovrappongono); sopra il floor il fallback resta (scenario B114 start_date shiftato) perché lì unisce solo sessioni preservabili senza mai riscrivere una data. **Tranche 2 — correttezza.** **R-5 (Medium):** `apply_day_add` saltava `_reconcile` (il commento diceva "spacing enforcement handled by _reconcile", ma su quel path non girava mai) → gap dita 48h e hard cap solo *warning*; inoltre gli enforcer scandivano solo `weeks[0]` con `last_finger_date=None`, quindi il confine domenica→lunedì non era mai controllato. Ora `_reconcile` gira, è **seedato con i giorni finali della settimana precedente** (`_prev_week_days`, hot-store; per il seed contano anche le sessioni `done` — una sessione dita **fatta** domenica è esattamente quella che deve bloccare lunedì) e ogni declassamento è restituito in `adjustments: [{date, slot, action, reason, previous_session_id, session_id}]` — `reason` riusa il vocabolario `constraints_applied` esistente. `apply_day_add` → 3-tuple, `POST /api/replanner/quick-add` espone `adjustments`. **Decisione Daniele: enforcement sì (protezione infortuni), silenzioso mai.** **R-6 (Medium):** `persist_week_plan` e `_is_current_macrocycle_monday` ricalcolavano il lunedì corrente dallo `start_date` **grezzo**, ignorando l'offset di pausa A223 → con una pausa attiva `current_week_plan` restava stale per i suoi reader (feedback step 1, suggest-sessions, adaptive replan). Entrambi ora passano da `week_num_to_phase_context(mc, 0)`, che àncora su `_effective_anchor` (unica definizione pause-aware). **R-7 (Low):** `_auto_resolve` non passava mai `phase` → `resolve_session` la derivava da `date.today()` (A121 ordering) e un override/quick-add su settimana futura in fase diversa ordinava gli esercizi con la fase di oggi. Ora fase per-sessione (`phase_id`, che planner e quick-add già stampano) con fallback sullo snapshot del piano. **R-8 (High, trovato durante la verifica di R-5, non nel brief originale):** la scansione in-settimana escludeva `status == "done"` dall'**intera** computazione dita — quindi (a) una sessione dita **effettivamente allenata** martedì non vincolava il mercoledì (buco nell'invariante 48h: un quick-add passava indisturbato) e (b) non era protetta dal loop di declassamento, che riscriveva **ogni** sessione dita del giorno in violazione, comprese quelle completate → `session_id` di una sessione immutabile sovrascritto con `regeneration_easy`. Stesso identico buco di riscrittura nel loop interno di `_enforce_caps`. Regola ora esplicita: le sessioni `done` **vincolano ma non sono mai bersaglio**; le `skipped` non sono né l'uno né l'altro (non sono avvenute, ma restano preservabili); un giorno declassato che conserva una sessione done resta comunque àncora per i giorni successivi. **Invarianti verificate:** sessioni passate/completate intatte da ogni path di rigenerazione (id, carichi, feedback, status, timestamp), determinismo preservato, nessuna randomness nuova, invariante lunedì intatto, filtro per equipment mai per location. Test: `test_b287_replanner_immutability.py` (18) + `test_b287_replanner_correctness.py` (24); **entrambi verificati falliti sul codice pre-fix** (8, 13 e 7 failure) e verdi dopo — più adeguamento di 12 call site all'arity di `apply_day_add` e riscrittura di `test_add_exceeding_cap_warns` alla nuova semantica (declassa invece di solo avvisare). Suite 2628 → 2669. **Nota di follow-up:** il rendering frontend del payload `adjustments` è fuori scope — serve un brief di remediation perché l'utente veda *perché* la sessione aggiunta è stata declassata.

- **A244 — A-COACH-WEATHER-TOOL: meteo on-demand via native tool use** ✅ (feature, backend-only `coach/` → push diretto main; il frontend già inviava `lat`/`lon` e renderizza `{reply}`, zero modifiche). Chiude il tema weather aperto da [[D253]]. **Cosa:** il meteo passa da **pre-fetch always-on** (iniettato nel context block quando c'erano lat/lon o un outdoor day) a **native tool use** — il modello chiama `get_weather(location, days_ahead≤5)` **solo** quando il turno lo richiede, in **qualsiasi lingua** (trigger delegato al modello, nessun layer keyword → risolve anche il blind-spot English-only del router L3 senza reintrodurlo). **Nuovo modulo** `backend/coach/weather_tool.py`: tool schema + executor che wrappa lo stack OWM esistente (`cached_conditions`/`geocode_place`, stessa cache 15', **stesso friction score computato da noi** — asset preservato); `location='here'` → GPS del client, altrimenti geocoding del nome; `days_ahead` 0=adesso, 1-5=forecast mezzogiorno; **mai solleva** (fallimento provider → stringa "unavailable" → il modello lo dice, non inventa). **Loop** in `llm_client.chat` (params `tools`/`tool_executor` opzionali, retro-compatibili): esegue i `tool_use` → rimanda `tool_result` finché il modello risponde con testo, **cap 2 tool-call/messaggio** + backstop `MAX_ITERATIONS=4` (termina sempre). `service.handle_chat` carica lo state una volta e lo passa sia a `build_system_blocks(state=…)` sia all'executor (niente doppio load). **Rimosso** il pre-fetch da `prompt_builder` (`_weather_section`/`_fmt_conditions`/costanti/threading lat-lon-weather_text) → i turni non-meteo **non pagano più** il fetch né i token meteo (caso comune più economico); tool def ~200 tok nel prefix cached (order tools→system) → costo marginale ≈0, cache L0/L1/L2 non invalidata. Nota `get_weather` aggiunta all'INSTRUCTION_BLOCK statico (anti-invenzione). **Zero-regression garantito** (D253): nessun tool_use se non serve → nessun round-trip extra; nessuno streaming da rompere. **E2E verificato:** "che condizioni ci sono adesso qui?" (IT, senza keyword, con GPS) → il modello chiama `get_weather(here)` → executor risolve i coords → OWM → "22°C, RH 39%, dew 7.4°, friction prime 85/100" → risposta groundata in italiano (lo scenario Berdorf di D253). Test: `test_coach_v1a.py` riscritto (rimossi i 3 test weather-in-context; +`TestWeatherTool` con executor here/named/unresolvable/provider-fail/clamp + loop tool-use/single-call/cap; endpoint wiring tool+executor; note capping su `build_user_context` senza `weather_text`). Suite 2621 → 2628. **Provider invariato OpenWeatherMap** (Open-Meteo scartato in D253 §6: blocker commerciale). Restano opzionali A-COACH-V1c (streaming, L4, personalizzazione).

- **C259 — KB Routing: keyword italiane per tutte le righe L3** ✅ (content/catalog, backend-only: tabella `_index.md` + test). Grounding: [[D253]] §2.2/§3.2 — la keyword table del router era **solo inglese**, quindi le query coach in italiano matchavano **zero righe** e cadevano silenziosamente sul fallback generico periodizzazione+motivazione (`routing.py:157-158`), invece del file L3 topico. **Fix:** sinonimi IT aggiunti a **tutte le 21 righe** (solo keyword table; nessun edit ai contenuti L3, nessun file nuovo). **Vincoli tecnici rispettati:** (1) solo termini in `"..."` contano (`_QUOTED_KEYWORD_RE`); (2) **niente accenti nei single-word** — il tokenizer query è `[a-z0-9+×x]+`, un `"continuità"` si spezzerebbe in `continuit` e non matcherebbe mai → usati solo termini ASCII, con un test-invariante che lo garantisce (`kw in _tokenize(kw)`, il `×` di `4×4` resta valido perché incluso nel charset); (3) scoring a conteggio grezzo per-riga indipendente → nessuno skew su query non correlate; collisioni cross-riga disambiguate da tie-breaker (`dolore`→10+11 rotto da `spalla`/`dita`/`puleggia`; `infortunio`→10+20; `resistenza`→05 mentre power-endurance usa il multi-word `"resistenza alla forza"`); (4) `_index.md` è **server-side only** (letto da `routing.py`, mai iniettato — NON in `_ALWAYS_LOADED`) → **impatto prompt-cache/prefix = nil**, verificato. **Regressione EN-free:** tutti i top file per-UC invariati (ri-verificato empiricamente + suite). Test: +5 in `test_coach_routing.py` (routing IT parametrico incl. le 5 query di acceptance del brief, disambiguazione body-part, mixed-language, fallback su IT off-topic, invariante tokenizer-survival). Suite 2607 → 2621. `_index.md` versioning → v1.2. **Prossimo nella pipeline coach:** A-COACH-WEATHER-TOOL (indipendente).

- **B286 — Coach Context Fix v2 (BUG-1): chiuso come già-fixed (no-op di verifica)** ✅ (bugfix verification-only, backend/docs-only). Il brief ipotizzava che il coach fosse cieco ai giorni outdoor pianificati (dato letto solo da `_weather_section` per il forecast). **Premessa smentita dal codice al Phase 0:** `_day_extras` — aggiunto dal B-COACH-CONTEXT-FIX originale `c7c4b58` (titolo: "…+ outdoor days visibility") — è già chiamato in `_week_section` (`prompt_builder.py:303`) e `_today_section` (`:335`), entrambe di default nel context block. Il coach vede già **data + giorno + spot + stato + disciplina** di ogni giornata outdoor della settimana, più la nota anti-"rest day". Prova empirica eseguita (week/today section con 2 outdoor day → render corretto). Già ri-confermato da [[D252]] (esito A: "BUG-1 già chiuso, 8 writer outdoor scrivono i campi flat"). **BUG-2 (English-only)** parimenti già chiuso dal medesimo `c7c4b58` (English-only → match-user-language) e ri-verificato da [[D253]] §3.1 (nessuna regola English-only esiste; il language-follow è by-design). **STOP-and-report** al Phase 0 (Fix req #1: "if reality differs, STOP") → decisione Daniele: chiudi come già-fixed. Nessun codice nuovo. Lezione in `docs/lessons.md`. Effetto collaterale: A-COACH-WEATHER-TOOL non è più gated da un B intermedio (nessun edit a `_weather_section` pendente).

- **D253 — Coach Weather & Tool-Use Readiness Audit** ✅ (audit read-only, `docs/audit/D253_coach_weather_tooluse.md`). Prepara **A-COACH-WEATHER-TOOL** (meteo da pre-fetch → on-demand tool use). **Esiti:** (1) il meteo è un **pre-fetch** iniettato sempre nel dynamic block quando arrivano `lat/lon` o c'è un outdoor day entro 5gg (`_weather_section`), **NON** routed via L3 (il router non ha riga meteo); (2) **native tool use già cablato** in `llm_client.extract()` (forced `tool_choice`, A243) ma non loop-ato in `chat()` — innesto contenuto a `chat()`+`handle_chat()`; (3) **nessuno streaming** (`coachChat` attende un `{reply}`) → un tool round-trip non introduce regressione "first-token"; (4) **nessuna regola English-only esiste** (premessa BUG-2 smentita, §3.1); (5) **Open-Meteo è un BLOCKER commerciale** (hosted free solo non-commercial; noi paid) → restare su **OpenWeatherMap**, il tool wrappa `cached_conditions()`; (6) **zero-regression garantito** e il caso non-meteo diventa più economico (tool def ~200 tok nel prefix cached, rimosso il fetch always-on). Friction score/best_window sono **computati da noi** (asset da preservare). Raccomanda `get_weather(location, days_ahead≤5)`, nessun gate a keyword (reintrodurrebbe il blind-spot English-only del router L3). 5 domande aperte per Daniele in fondo al doc.

- **B285 — SEC-AUTH: hardening auth in produzione (IDOR + fail-open anonimo)** ✅ 🔴 P0 sicurezza (backend-only, da review esterna 2026-07-20). Tutti e 6 i finding verificati contro il codice reale prima dell'implementazione. **SEC-1 (critical, IDOR completo):** il fallback dev `X-User-ID` in `deps.get_user_id` era accettato **senza alcun check ambientale** — chiunque poteva mandare `X-User-ID: <uuid>` senza `Authorization` e agire come quell'utente (export stato, import/patch, cancellazione account); UUID sconosciuti facevano bootstrap di righe DB → DB-fill non autenticato illimitato. **SEC-2 (high, fail-open):** `check_subscription` restituiva ALLOW_ALL per `user_id=None` → traffico anonimo passava `require_active_subscription`, e su `/api/coach/chat` la chiamata Anthropic (a pagamento) avviene **prima** della persistenza → fino a 30 chiamate LLM/giorno gratis sul bucket `__legacy__`. **Fix strutturale unico:** `_auth_enforced()` (Clerk configurato **oppure** `STORAGE_BACKEND=supabase`, salvo `ALLOW_LEGACY_HEADER=1`) → in prod l'header `X-User-ID` viene rifiutato con 401 **e** l'assenza totale di credenziali dà 401 invece di `None`. Chiude SEC-1, SEC-2 e SEC-5 alla radice, prima di qualsiasi chiamata LLM o scrittura DB. È anche un fix di correttezza: un token Clerk scaduto restituiva i dati di `__legacy__` (cioè non i propri) invece di un errore; il retry-on-401 del frontend (`api.ts`, B155) copre già il caso "Clerk non ancora caricato". **SEC-3:** `X-Admin-Key` ora con `secrets.compare_digest`. **SEC-4:** identificatori mascherati (`mask_uid`, primi 8 char) e DIAG declassati a DEBUG in `auth.py`, `subscription_guard.py`, `stripe_webhook.py` (~10 call site) — i log Railway non sono più un vettore di recupero UUID. **SEC-5:** `storage_supabase._effective_uid` non mappa più `None → '__legacy__'` ma alza (le write erano già protette, le read no); verificato su DB prod **prima** del cambio: 0 righe `__legacy__` su users/subscriptions/coach_messages/session_logs (17 utenti totali) → nessuna dipendenza dal vecchio mapping. **SEC-6:** il regex CORS `climb-agent(-[a-z0-9-]+)?\.vercel\.app` accettava preview di **qualsiasi** account Vercel con un progetto omonimo → ora pinnato allo slug del team (`-danielesomensi-cmds-projects`). Invarianti verificate: `BYPASS_USER_IDS` è valutato dopo il check user_id (founder/beta intatti), subscriber attivi non toccati, nessun path tocca piani o sessioni passate, il frontend non ha mai mandato `X-User-ID` (usa solo il Bearer Clerk) → zero impatto sui client legittimi. Test: +24 in `test_auth_hardening_b285.py` (attacco respinto **e** dev/test invariato per ogni finding) +2 in `test_cors.py`; i 2 test CORS preview usavano uno slug inventato (`danieles-projects`) → allineati a quello reale. Suite 2589 → 2607.

- **B284 — Adhoc: palestra nominata + secondary focus (fix equipment-union e core sparito)** ✅ (bugfix, follow-up feedback live #2 di Daniele su A243, merge diretto in main). **Problema 1 (grave):** con più palestre registrate (Bkl boulder, Cocque corde, Work pesi), l'intent sapeva solo `equipment_set=gym` → `resolve_equipment_mode("gym", gym_id=None)` faceva l'**unione dell'attrezzatura di tutte** → il compositore proponeva panca/cavi "al Bkl". Fix: nuovo slot `gym_name` nell'estrazione (il prompt istruisce a catturare il nome verbatim, es. "al Bkl" → "Bkl"), `match_gym` deterministico case-insensitive substring-tolerant → `resolve_equipment_mode` con il `gym_id` giusto; senza nome: 1 sola palestra → quella, multi → unione (comportamento precedente). Verificato con l'equipment reale di Daniele: zero violazioni al Bkl. **Problema 2:** "core e tecnica" perdeva il core (l'estrattore sceglieva solo il dominante, il finisher singolo saltava per budget) → nuovo slot `secondary_focus` + **blocco garantito 2-3 esercizi** del focus secondario nel composer: la riserva viene calcolata PRIMA del riempimento primario (budget primario = minuti − riserva; cap totale invariato), ordine warmup→primario→secondario→finisher, finisher core saltato se il core è già primario o secondario. Nome/explanation/tags portano gym e combo ("Adhoc technique + core @ Bkl", "Only exercises doable with Bkl's equipment"). Determinismo preservato. Test: +6 in `test_b281_adhoc_fixes.py` (equipment ristretto alla gym nominata, matching fuzzy, fallback single-gym, blocco secondary ≥2, no doppio finisher, determinismo). Suite 2583 → 2589.

- **B283 — Le custom session girano nel player guidato VERO (pensionato il player minimale A211)** ✅ (bugfix/UX, follow-up feedback live di Daniele su A243: "sembra amatoriale — non si vede a che punto siamo, non si naviga tra esercizi, niente peso, niente descrizioni", merge diretto in main). Chiude anche la divergenza due-player segnalata da D252 (LOW-6). **Root cause:** le saved custom (e le adhoc del coach) usavano la playback page dedicata A211 (`/session-builder/[id]/play`) — minimale: nessuna progress bar, nessuna navigazione, nessuna cue/descrizione, peso invisibile. Le body-part (B218) invece giravano già nel player guidato reale via `buildGuidedStateFromInline`. **Fix:** (1) **Backend** — `_build_session` (create/update) arricchisce ogni esercizio custom con i display-field del catalogo (`name`, `cues`, `video_url`, `load_model`, `category`, note tecniche da `prescription_defaults.notes` quando l'utente non ne ha scritte); `enrich_custom_sessions_for_play` fa il backfill read-path per le sessioni salvate pre-fix (GET detail + router `/replanner/events` prima che `add_custom_session` copi gli esercizi nello slot — `replanner_v1.py` NON toccato). (2) **Frontend** — bridge generalizzato `buildGuidedStateFromExercises` + `saveGuidedState` in `guided-session-utils` (mappa anche `video_url` e `load_kg`→suggested weight); `session-card` non devia più le saved custom sul player A211: TUTTE le `is_custom` passano dal player guidato; il CTA del coach "Add to today & run" costruisce lo stato guidato e apre `/guided/[date]/custom_<id>`. Risultato: progress bar con indice, navigazione avanti/indietro, cues+note tecniche+video, peso suggerito+input peso usato, feedback per-esercizio nativo (che alimenta `working_loads` via A240). La pagina A211 resta come dead code (nessuna route UI la raggiunge) — rimozione in un cleanup futuro. Test: +3 in `test_b281_adhoc_fixes.py` (enrichment su create, user-notes vincono, backfill legacy read-only). Suite 2580 → 2583.

- **B282 — Routing adhoc: stem-based, basta whack-a-mole morfologico** ✅ (bugfix frontend-only, follow-up B280/B281, merge diretto in main). Terzo giro sul routing: anche dopo B280, le frasi italiane in seconda persona interrogativa ("Mi **prepari** una sessione…?", "**manda** tu al session builder") sfuggivano — una lista di coniugazioni perde sempre contro la morfologia italiana (crei/prepari/mandi/generi…). Riscritto `looksLikeAdhoc` (B282): **co-occorrenza a livello messaggio** di un nome-sessione (`sessione|allenament*|seduta|scheda|…`) + uno **stem verbale** (`cre*|prepar*|mand*|aggiung*|vorrei|serve|build*|…`), più trigger standalone per i **clitici** ("crearla", "mandamela", "preparamela") dove il nome vive dentro il verbo, e i segnali-palestra esistenti. Fortemente biased verso il routing: un falso positivo costa una estrazione economica che ritorna `{adhoc:false}` → fallback chat; un falso negativo dà la risposta sbagliata. Verificato 14/14 contro i messaggi REALI della conversazione prod di Daniele (tutti i build-request matchano, tutte le domande normali no). Nessuna nuova chiamata LLM sul path normale — il coach resta rapido (vincolo di Daniele).

- **B281 — Adhoc field-test fixes (4 difetti dal test live di Daniele)** ✅ (bugfix, follow-up A243/B280, merge diretto in main — Daniele verifica da prod). Dalla lettura della conversazione coach reale: **(1) Il coach negava e si scusava** ("Non posso creare sessioni... il messaggio precedente è stato un errore") — l'`INSTRUCTION_BLOCK` A237 diceva ancora all'LLM che non può creare sessioni → riscritto: l'app PUÒ comporre via card "Add to today & run", mai negare, mai chiamare "errore" una card creata, guida l'utente a riformulare come build-request diretta. **(2) "Riprovi a crearla?" componeva i default sbagliati** (home/general_strength/45 invece di core+tecnica@Bkl 80min) — l'estrattore vedeva SOLO l'ultimo messaggio → ora riceve gli ultimi 6 turni di conversazione (`build_extraction_content`, prompt aggiornato: slot dai turni precedenti, gym nominata ⇒ equipment_set=gym, doppio focus ⇒ dominante). **(3) Sessione composta "alphabet soup"** (5 varianti di trazione in fila alfabetica, warmup mobilità da 8 minuti, 9 esercizi) → `adhoc_builder`: diversità di movement-pattern (max 2 per `pattern`), cap 8 esercizi, warmup ≤300s scelto per brevità, main block ordinato main_strength→accessory→drill, energy non gonfia più il warmup. Determinismo preservato. **(4) Player custom intrappolava l'utente** nei timer lunghi (nessun modo di avanzare) → "Finish set early" durante il countdown + "Skip exercise →" sempre raggiungibile (salta tutti i set rimanenti). Test: `test_b281_adhoc_fixes.py` (11: diversità pattern, cap esercizi, warmup corto su 4 focus, ordering, warmup non gonfiato da energy, determinismo, contesto estrazione incluso+cappato+carrying specs, instruction block card-aware). Suite 2570 → 2580.

- **B280 — Adhoc card routing troppo English-centrico (fix heuristica coach)** ✅ (bugfix, follow-up A243, merge in main — Daniele verifica da prod). **Decisione:** teniamo la heuristica veloce (opzione a), NIENTE always-extract per non rallentare la chat. Follow-up di [[A243]]: la heuristica frontend `looksLikeAdhoc` che instrada i turni chat verso `POST /api/coach/adhoc-session` (card) invece di `/chat` (testo) copriva bene l'inglese ma poche frasi italiane (`componi`/`costruisci`/`in palestra`). Una richiesta IT tipo "creami una sessione da palestra" o "fammi un allenamento" **non matchava** → finiva sul path testuale A237 → il coach rispondeva col vecchio "non posso creare sessioni, usa il Session Builder" (misleading, ora il flusso a card esiste). Fix: heuristica riscritta molto più inclusiva IT+EN (verbo-build + nome-sessione in prossimità, contesto palestra, "sessione veloce"…), **biased verso il routing** (un falso positivo costa solo un'estrazione economica che ritorna `{adhoc:false}` → fallback chat; un falso negativo dà la risposta "non posso" sbagliata, molto peggio). Verificata contro 14 frasi IT/EN (10 build + 4 domande normali): 14/14 corrette. Backend `adhoc-session` confermato live in prod (HTTP 200). Frontend-only → branch + preview.

- **A243 — Adhoc Coach v1, Phase 3 (coach → deterministic adhoc builder bridge)** ✅ (feature, Adhoc Coach v1 track Phase 3 — **la feature**, branch `brief/A243-adhoc-builder` → preview Vercel approvata da Daniele → merge in main). **🎯 Track Adhoc Coach v1 COMPLETO** (Phase 1+2+3 su main). Terzo e ultimo brief del track `docs/adhoc_coach_v1_track.md` — la feature vera. **STOP-gate analysis-first** con OK esplicito. **Cosa:** l'utente chiede nel chat coach "sono in palestra, componimi una sessione di 45 min" → l'**LLM estrae solo un intent strutturato** `{equipment_set, focus, minutes, energy}` via **forced tool_choice** (`backend/coach/adhoc_intent.py`, non vede mai il catalogo) → il modulo deterministico `backend/engine/adhoc_builder.py::compose_adhoc_session` compone una `custom_session` (warmup→blocchi focus→core finisher, equipment- e phase-aware via `phase_affinity`, spine-safe, recency-avoidance, prescrizioni+carico da Phase-2 `propose_exercise_prescription`) flaggata `adhoc: true`. Riuso massiccio di `body_part_picker` (equipment resolution/fit, recent ids) e `adhoc_prescription`. **Endpoint** `POST /api/coach/adhoc-session` (89→90): ritorna una **PREVIEW** — **compose NON persiste** (decisione Daniele: zero orfani), nessuna mutazione piano; `{adhoc:false}` → il client fa fallback su `/chat`; conta verso il limite 30/die solo su adhoc:true. **Frontend:** la coach chat instrada i turni "adhoc-looking" all'endpoint e rende una **card strutturata** (lista esercizi, sets×reps, carico, effort-band) con **un solo CTA "Add to today & run"** → `createCustomSession` (persist-on-accept) → `applyEvents(add_custom_session, oggi)` → player Phase-1. **Decisioni Daniele:** Option-1 (endpoint+card), compose-no-persist, single-CTA, target=oggi, explanation deterministica (no call extra), card minimale nel chat, `adhoc:true` come provenance dato (nessun badge UI in v1), A237 L3 testuale **coesiste** (fallback conversazionale + scenario-2 suggest-only). **Invarianti:** `adhoc_builder` **fuori dal coach** (claim "engine deterministico" intatto); **nessun tocco** a `planner_v2`/`replanner_v1` (solo riuso evento `add_custom_session`), `resolve_session` P0, `macrocycle_v1`, `progression_v1`; immutability preservata; load accounting invariato. Test: `test_a243_adhoc_builder.py` (13: determinismo, shape+flag adhoc, budget minuti, filtro equipment home/gym, spine-safe su tutti i focus, energy modula volume, carico ricordato, focus→domains coprono l'enum, endpoint preview+no-persist+adhoc:false+limite, insertion-immutability sibling/past). Suite 2557 → 2570. **Chiude il track Adhoc Coach v1** (Phase 1+2+3 su main).

- **A242 — Adhoc Coach v1, Phase 2 (load proposal + history nel builder)** ✅ (feature, Adhoc Coach v1 track Phase 2, branch `brief/A242-load-proposal` → preview Vercel approvata da Daniele → merge in main). Secondo dei 3 brief del track `docs/adhoc_coach_v1_track.md`; chiude [[D252]] C.2 (HIGH) + C.3 (MED). **STOP-gate analysis-first** eseguito con OK esplicito. **Scoperta chiave:** l'app **non ha RPE/RIR** nel modello dati (i `prescription_defaults` hanno solo sets/reps/work/rest; l'engine usa `intensity_pct_of_total_load` per i caricati e grade-relative per l'arrampicata; l'unico segnale di sforzo è `feedback_label`). Reinterpretata la richiesta "RPE/RIR primary" del brief di conseguenza. **Cosa:** nuovo helper deterministico `backend/engine/adhoc_prescription.py::propose_exercise_prescription` (riusabile da Phase 3) che sovrappone 3 livelli — struttura (`prescription_defaults`), memoria carico (`working_loads` via `_best_entry`), banda sforzo per fase — e restituisce `{sets, reps, work_seconds, rest_*, load_kg, effort_band, last_logged}`. `load_kg` = valore **ricordato o 0, mai inventato** (C.3). `last_logged` = `{load_kg, feedback_label, date}` per il "last time: X · N ago". Banda sforzo `PHASE_EFFORT_BAND` = cue testuale coarse per fase (base→moderate … strength_power→hard … deload→easy), **display-only, mai persistita, mai un numero**, custom-only. **Decisione di Daniele:** prefill del carico ricordato **sempre, freshness disabilitata** (l'umano rivede/edita; stale è sicuro se datato) → `_best_entry` reso freshness-parametrico (`freshness_days=None`) **e non-mutante** (lettura pura senza `setdefault`, così un GET non muta lo stato) — behavior-preserving per i caller progression (default 60gg invariato, coperto da `test_load_transfer`/`test_resolve_session_freshness`/`test_daniele_loads_snapshot`). **Endpoint:** `GET /api/custom-session/exercises` arricchito additivamente con `proposal` per esercizio (legge fase macrocycle + working_loads, read-only, non persiste). **Frontend:** `exercise-picker.tsx` prefilla `load_kg` dal proposal, mostra "Last time: X · N ago" per gli esercizi con storico e la banda sforzo di fase una volta sola. **Nessun tocco a `resolve_session`/`planner_v2`/`macrocycle_v1`/`closed_loop_v1`/`replanner_v1`; nessun nuovo campo su `CustomSessionExerciseEntry`.** Test: `test_a242_load_proposal.py` (10: proposta deterministica, load 0 senza storico, prefill ricordato anche stale, bodyweight senza kg non inventa, banda per fase, lettura non-mutante, endpoint carica proposal + surfacing carico + no persist mutation). Suite 2547 → 2557. **Prossimo:** Phase 3 (coach → deterministic adhoc builder bridge).

- **A240 — Adhoc Coach v1, Phase 1 (custom-session per-exercise logging + immutability guard)** ✅ (feature, Adhoc Coach v1 track `docs/adhoc_coach_v1_track.md` Phase 1, branch `brief/A240-custom-logging` → preview Vercel approvata da Daniele → merge in main). Primo dei 3 brief del track; chiude [[D252]] C.4 (HIGH) + C.5 (MED). **STOP-gate analysis-first** (tocca feedback path + confine closed-loop, moduli high-risk) eseguito con OK esplicito prima dell'implementazione. **Cosa:** il player delle **saved custom session** (`/session-builder/[id]/play`) ora cattura per-esercizio (sforzo percepito `feedback_label`, carico usato kg opzionale prefill da `load_kg`, set completati tracciati durante il flusso) alla schermata di completamento e a fine sessione scrive un log per-esercizio via `POST /api/feedback` riusando lo shape `exercise_feedback_v1` (nessuno schema nuovo). Prima faceva solo `mark_done`. **Confine closed-loop:** le sessioni adhoc/custom **scrivono `working_loads`** (via `apply_feedback`, che gira sempre) ma **NON alimentano il closed-loop** (`stimulus_recency`/`fatigue_proxy`) — off-plan support work. Doppia barriera: (1) il player omette `resolved_day` → il gate esistente a feedback.py step-3 salta il closed-loop; (2) nuovo guard esplicito `_is_custom_session` (mirror di `_is_body_part_session`/A213) che salta `apply_day_result_to_user_state` per session `custom_*` anche se un futuro caller passasse `resolved_day`. **Nessun tocco a `closed_loop_v1.py`/`progression_v1.py`/`replanner_v1.py`/`resolve_session.py`** — solo il gate dentro `feedback.py`. Persistenza `actual_exercises`+durata unificata (ex 4b/4b-bis) ed estesa a `week_plans[monday]` così le custom in settimane future attaccano i raw allo slot (mark_done già coperto da B216). Guard frontend `is_custom` (week/today `handleMarkDone`) invariati. Test: `test_a240_custom_feedback.py` (6: immutabilità sibling/past su insert+complete, working_loads scritto, closed-loop OFF senza resolved_day, closed-loop OFF anche CON resolved_day via guard, actual+durata sullo slot, control: sessione normale alimenta ancora il closed-loop). Suite 2542 → 2547. **Non-goals track rispettati:** strettamente additivo, RPE/RIR primary (kg solo come memoria loggata dall'utente), nessun endpoint nuovo. **Prossimo:** Phase 2 (load proposal + history nel builder), poi Phase 3 (coach → deterministic adhoc builder bridge).

- **A241 — Per-try rest/climb breakdown (outdoor live logging)** ✅ (feature, `backend/api/models.py` (1 campo) + frontend outdoor live-logging/history → branch `brief/A241-per-try-rest-breakdown` + preview Vercel prima del merge). Rinumerato da A239 (collisione con A-GAMIFY-02 milestones, già su main). Origine: field test Daniele 18-19/07 — la card di via mostrava un unico contatore rest cumulativo (es. `rest 195:03` su 2 try), nascondendo l'evoluzione rest/climb try-per-try. **Design (approvato):** rest **session-wide** (rest prima del try N = tempo dalla fine del burn precedente su **qualunque** via all'inizio del try N; se nel mezzo climbi un'altra via quel tempo non è rest), primo burn → `—`, **derive-don't-store** (si persiste solo il timestamp per-try + climb opzionale, il rest si calcola a render → coerente dopo la cancellazione di un try). **Backend:** unico campo additivo `OutdoorAttempt.logged_at` (ISO 8601 UTC, client-stamped); i nuovi try scrivono `logged_at` (+`climb_seconds` se timer) e **non** più `rest_seconds` (decisione: derive-only); passa intatto in PUT/finish nel log immutabile; payload vecchi validi. **Frontend:** util pura `deriveTryTimings` (ordinamento cronologico cross-route, start = `logged_at − climb_seconds`, primo burn null, robusta a delete/clock-skew), componente `TryBreakdown` read-only (`✗ try 1 · rest — · climb 2:41`) riusato in live logger + `OutdoorLogForm` + history `/outdoor`; card live: **collassata** = ticker "last try Xm ago" per-via (sostituisce la somma cumulativa), **espansa** (tap sul corpo, non confligge con +✓/+✗/×) = righe per-try. **Fix incidentale del difetto A227:** il rest cronometrato non include più il tempo sulla parete (start = press − climb). **Legacy** (try senza `logged_at`, incl. i log B279/A227 di ieri): fallback grazioso ai totali attuali, zero migrazione, log passati byte-identici. **Fix `sync_status.py`:** parser conteggio test ristretto a `backend/tests/…py: N` (le deprecation-warning del venv 3.14 finivano su stdout e venivano contate). Test: `test_a241_logged_at_round_trips` (persistenza PUT+finish, payload misti) + `try-timings.test.ts` (10 vitest: first-burn null, cross-route, delete-middle, climb-subtraction, point-event, legacy no-chain, clamp skew). Suite backend verde, vitest 147 verdi, build frontend OK. **Nota infra:** venv ricreato (Homebrew aveva rimosso python@3.13 → interprete dangling; ora Python 3.14; deploy Railway non impattato — Nixpacks gestisce il proprio Python). Out of scope: analytics rest-evolution cross-sessione, UI timestamp per manual log.

- **A239 — Milestone system (A-GAMIFY-02)** ✅ (feature P2.9 retention, branch `brief/A239-milestones` → preview Vercel; slice backend additiva su main per la preview, pattern A234). Terza tappa del piano gamification (A-GAMIFY-00). **Catalog:** `backend/catalog/milestones/v1/milestones.json` — 22 milestone one-time su 5 categorie (session/exercise/outdoor/grade/process), distribuzione di difficoltà deliberata activation/medium/career (ricerca: retention ∝ difficoltà achievement). Integra le idee di Daniele: exercise-family firsts (hangboard/campus/technique via equipment del catalogo, NON per-esercizio), Explorer 25/50 esercizi diversi, Drill Collector 10, grade-firsts outdoor per disciplina (dynamic, redpoint+onsight), Crag Explorer 3/5 spot, **Perfect week** (tutte le sessioni pianificate fatte + almeno un rest day → la risposta corretta al "badge mi alleno tutti i giorni" respinto in A-GAMIFY-00). **Engine:** `milestones_v1.evaluate_milestones` — valutazione **lazy read-driven** (nessun hook nei write path, zero moduli high-risk toccati), deterministica; deriva tutto da dati esistenti (hot week_plans, outdoor log, free/custom sessions, macrocycle+history). Stato additivo `state.milestones{unlocked[],counters,counted_weeks}`: unlock **append-only mai revocati** (cancellare un climb non ri-blocca), counter esercizi assorbono SOLO settimane completamente passate (immutabili per invariante → sopravvivono all'archiviazione A221; la settimana in corso è transitoria, un undo non lascia conteggi fantasma). **Deviazione documentata:** le settimane archiviate prima del lancio non vengono scansionate (i conteggi cumulativi partono da oggi; i grade-PB retroattivi hanno unlock_at = data di scoperta). Router `GET /api/milestones` (valuta+persiste se nuovi) + `POST /api/milestones/{id}/seen`, endpoint 87 → 89. **Frontend:** `MilestonesCard` su /plan (griglia 4-col, unlocked ambrati / locked dimmed+grayscale, dynamic grade-PB con grado, show-all), `MilestoneToast` su /today (toast celebrativo per unseen, >2 collassano in un summary anti-spam, tutti marcati seen). Vincoli design doc: nessuno streak, nessun badge di volume, nessuno stato negativo. Test: `test_a239_milestones.py` (17: integrità catalog + distribuzione tier, condizioni session/exercise/outdoor/process, append-only/idempotenza, counters fold solo-passato + survive-archiving, dynamic PB nuovo grado, API). Suite 2525 → 2542. Build frontend OK.

## Recently closed (2026-07-19)

- **A238 — Weather conditions v2: composite friction score + legible metrics + best window (A-WEATHER-V2)** ✅ (feature, backend `weather_v1.py`/router + frontend cards → branch `brief/A238-weather-v2` + preview Vercel prima del merge). Origine: field test Daniele a Berdorf 19/07 — 22°C, RH 39%, dew 7°C (spread 15°), vento 23 km/h, secco → l'app dava **OK**; condizioni oggettivamente ottime. Root cause: band A224 a soglie dure weakest-link, temp 22° > 16° (`TEMP_PRIME_MAX_C`) declassava ignorando lo spread. **Backend:** `compute_friction_score` — score composito 0–100 pesato (temp 30% plateau 5–18° decadimento→26°/−2°, dew spread 30% ≥10° →3°, humidity 25% ≤45% →80%, wind 15% 8–25 →40/0) + band a 4 valori `prime≥80/good≥60/ok≥40/poor`; override: precipitazione (attiva, rain.1h>0 o pop>30%) → cap poor, temp<0° → cap ok. Berdorf-regression: (22,39,7,23) → **85 PRIME** (unit test). `metric_qualifiers` (chip inglesi backend-owned per temp/humidity/dew_spread/wind/precip) + `band_headline` (verdetto per band + suffisso sul limitatore peggiore). **Best window:** dagli step 3h forecast dello stesso giorno locale (daylight 07–21, tz-aware via `city.timezone`), run contigua attorno al picco, solo se batte il punteggio attuale di ≥10 (`best_window {from,to,score,band,reason}`); per la current-weather il router fa una seconda chiamata forecast (stessa cache 15'). `recent_rain_mm` esposto da OWM `rain.1h` (2.6 free-tier). **Compat:** chiave legacy `condition_band` ora emette il nuovo vocabolario; `catalog_condition_band` mappa **good→ok** (decisione Daniele — patch strategy conservativi, catalogo C241 intatto); coach `_fmt_conditions` passa band+score. **Frontend:** nuovo `ConditionsPanel` condiviso (band chip prominente color-coded + emoji dominante 🌧🔥💧💨❄️, headline sempre visibile, riga best window, griglia metriche con chip qualifier, dew point riframato come **spread** "N° below air", attribution OpenWeather visibile) usato sia da `WeatherCard` (/today, cache sessionStorage bumpata v3) sia da `ConditionBadge` (outdoor) → band/copy identici sulle due superfici (acceptance 3). Test: `test_a238_weather_v2.py` (18: decadimenti per componente, cut-point, override, Berdorf, qualifiers, headline, best-window incl. tz/altri giorni/step passati/run contigua, shape endpoint additiva, fetch_outdoor good→ok); `test_weather_v1.py` adattato (soglie A224 superseded). Suite verde, build frontend OK. **Follow-up (out of scope):** rain-recency vera via osservazioni persistite (OWM free dà solo `rain.1h` live); crag aspect/sole per spot.

- **A237 — Adhoc Coach v0 (conversational session composition)** ✅ (feature, prompt/KB-only — nessun engine/endpoint/schema, backend-only → push diretto main). Primo step di "Adhoc Coach Sessions": il coach compone una sessione **strutturata ma testuale** su richiesta, armonizzata col piano. Costruisce su [[D252]] (coach = puro testo, nessun write path) e [[C258]] (12 esercizi commercial-gym). **Cosa:** (1) nuovo file L3 `21_adhoc_gym_sessions.md` (~2.6K token, snello) con 2 intent — "sono in palestra pesi, componi una sessione" + "non mi va la sessione di oggi, trade-off" — struttura sessione (warmup→2-4 blocchi→finisher core/prehab), RPE/RIR only mai kg, phase-awareness, regole di armonizzazione (ieri dai log, domani dal session-label del piano), menu esercizi **solo id reali del catalogo** (C258 + esistenti), core spine-safe D55, ponte save→Session Builder; (2) riga di routing in `_index.md` (gym/bench/dumbbell/swap/"don't feel like"…, UC24/UC25); (3) `INSTRUCTION_BLOCK`: regola compose + suggest-only ("never imply added/logged", RPE only, → Session Builder), resta nel blocco statico cached; (4) 2 chip suggerite ("build me a session" / "alternatives"), `MAX_SUGGESTIONS` 4→6. **Test — correzione al brief:** i "golden-transcript test" su output LLM NON sono deterministici/offline (tutti i test coach mockano `llm_client`), quindi test deterministici di prompt-assembly + routing + integrità vocabolario esercizi + instruction-block + chip (`test_a237_adhoc_coach.py`, 11 test), più bump `test_coach_routing` 20→21 righe + casi UC24/UC25. Sample transcript **live** generata per giudizio umano (qualità ottima: struttura completa, solo esercizi catalogo, RPE, phase-aware, armonizzazione pull basso pre-hangboard, suggest-only). **Limite noto (dipendenza v1, da D252):** il ponte custom-session è lossy — il builder non propone carichi né logga per-esercizio, quindi le prescrizioni RPE non si trasferiscono automaticamente. Suite verde (2507). Non-goals rispettati: nessun endpoint/session-object/logging/timer, nessun tocco a resolve_session/replanner, scenario-2 (swap reale) resta suggest-only.

- **C258 — General Gym Batch (commercial-gym exercises)** ✅ (catalog/content, data-only, backend-only → push diretto main). Chiude il gap "nessuna copertura commercial-gym" trovato da [[D252]], così la futura feature "Adhoc Coach Sessions" potrà comporre sessioni da palestra pesi credibili. **+12 esercizi** (242 → 254): Legs (`back_squat`, `deadlift`, `leg_extension`, `leg_curl`, `standing_calf_raise_loaded`), Arms (`skullcrusher`, `triceps_cable_pushdown`), Shoulders prehab (`dumbbell_external_rotation`), Loaded core (`back_extension`, `cable_woodchop`, `weighted_hanging_leg_raise`, `weighted_plank`). **Decisioni bloccate rispettate:** nessuna nuova chiave equipment (tutti `["weight"]`, o `[]`/`["pullup_bar","weight"]` dove appropriato — la specificità machine/cable/barbell vive in nome+descrizione), nessun re-tag di esercizi esistenti, load RPE-based nei `prescription_defaults` (mai kg assoluti), `domain: strength_general` collapse per i lift generali. **Deviazione di sicurezza:** i 2 crunch richiesti (`cable_crunch`, `machine_ab_crunch`) collidono con la blacklist D55 (`test_catalog_safety` vieta id con "crunch" — flessione spinale caricata contraindicata); sostituiti con core caricato spine-safe (`weighted_hanging_leg_raise`, `weighted_plank`) su decisione di Daniele. Tutti e 12 classificano correttamente nel body-part picker (legs/glutes/triceps/shoulders/core). Suite verde (2495). Test count aggiornato 242→254.

- **B279 — Project mode nel live logger outdoor + timing per tentativo** ✅ (bugfix UX, branch `brief/B279-project-mode-live-logger` → preview Vercel prima del merge). Origine: field test Daniele — nella sessione outdoor attiva, dopo un "✗ Fell" i bottoni grandi (quelli col climb timer) creavano **sempre una via nuova**: progettando una via si finiva con N duplicati, e il retry passava solo dai mini-bottoni "+✗" per-riga scollegati dal timer. In più `rest_seconds`/`climb_seconds` erano per-via: `addAttempt` sovrascriveva il climb del burn precedente e il rest dei tentativi ≥2 non veniva salvato affatto → tempi incoerenti sui progetti. **Fix (frontend `live-route-logger.tsx`):** modalità "Projecting" — un Fell (quick-add o "+✗") rende la via attiva: il pannello principale mostra "Projecting: {grado} {nome} · try N" e climb timer + Sent/Fell puntano alla **stessa via**; "New route" esce, un Sent chiude. Riga attiva evidenziata (indigo, label "Projecting"). **Timing per tentativo:** campi opzionali `rest_seconds`/`climb_seconds` su ogni attempt (types.ts + `OutdoorAttempt` in `backend/api/models.py`, additivo/retrocompatibile — i campi route-level restano = primo burn A227); righe e `OutdoorLogForm` mostrano i **totali** su vie multi-burn, tooltip per-tentativo sui pallini. Test: `test_per_attempt_timing_round_trips` (sync live + finish preservano il timing per attempt). Build frontend OK.

- **D252 — Step-0 Foundation Audit (Adhoc Coach)** ✅ (audit read-only, `docs/audit/D252_adhoc_foundation.md`). Verifica la fondazione prima di scrivere brief per la feature "Adhoc Coach Sessions" (costruita sopra `custom_session`). **Esiti:** (A) BUG-1 "coach cieco ai giorni outdoor" **già chiuso** — tutti gli 8 writer outdoor scrivono i campi flat `outdoor_*` sul day dict che il coach legge (`prompt_builder.py:244-266`); l'override "converti in outdoor" svuota `sessions=[]` prima di settare i flat, impossibile produrre forma annidata. (B) Custom-session load raggiunge **tutte e 4** le superfici (report_engine, week-progress-bar, header Week, Today) via fallback `session_load_score ?? estimated_load_score`, congelato all'add-time, no doppi conteggi. (C) **3 buchi HIGH/MED** verso il feature adhoc: [HIGH] logging per-esercizio assente (custom player invia solo `mark_done`, zero carico/RPE/durata), [HIGH] nessuno storico `working_loads` letto/scritto, [MED] nessuna proposta di carico (`load_kg` default 0), [MED] test immutability custom-session mancante, [LOW] `active:False` non filtrato dal picker, [LOW] due player divergenti. **Conclusione:** load accounting + immutability solidi e riusabili; le 3 feature che rendono utile un adhoc builder (proporre carico, ricordare storico, loggare) oggi non esistono in `custom_session` → prerequisiti per un v1, non per un v0 conversazionale.
- **A236 — Monthly heatmap rest-positive (A-GAMIFY-03)** ✅ (feature P2.9 retention, branch `brief/A236-monthly-heatmap` → preview Vercel; slice backend additiva pushata direttamente su main per rendere la preview testabile, pattern A234). Calendario mensile "Month at a glance" in fondo a `/reports/weekly` con navigazione mese e tap-to-day-view. **Il differenziatore filosofico del design doc:** rest day rispettato = verde tenue proprio (premiamo il riposo), skip = neutro zinc indistinguibile dal quiet (NO color shame, mai rosso), done = 3 tier emerald via load score, planned/rest_planned futuri = bordo tratteggiato, oggi = ring azzurro. **Backend:** `generate_monthly_heatmap` in `report_engine.py` + `GET /api/reports/heatmap?month=YYYY-MM` (86 → 87 endpoint) — read-only, riusa `_find_week_plan` (hot `week_plans` + cold store A221), somma per-giorno session/outdoor/other-activity/free-session load; classificazione: done > (planned se futuro-o-oggi | skipped se passato) > (rest se in-plan vuoto passato/oggi | rest_planned se futuro) > none; guardie anti-double-count (outdoor done nel piano vince sul log; log outdoor conta solo per giorni non sincati pre-B277); free session finita su giorno senza piano = done (mai "rest" farlocco). Test: `test_a236_monthly_heatmap.py` (17: classificazione celle, tier load, cold-store fallback via monkeypatch, free session aggregation, contratto API + 422). Suite 2477 → 2494. Build frontend OK.

- **A235 — Macrocycle progress + phase completion celebration (A-GAMIFY-01 + P5)** ✅ (feature P2.9 retention, frontend-only, branch `brief/A235-gamify-phase-progress` → preview Vercel prima del merge). Prima implementazione del design gamification (A-GAMIFY-00, doc approvato stesso giorno). **Timeline /plan:** `MacrocycleTimeline` con `showProgress` — ✓ verde sulle fasi completate + riga "Week X of Y · Z% of cycle complete"; marker settimana ora **pause-aware**: nuova util condivisa `lib/phase-progress.ts` (`computeCurrentWeek` sottrae `pause.offset_days` A223 e clampa a total_weeks — fix del calcolo che su /plan ignorava la pausa). **Celebrazione fase:** `PhaseCelebration` su /today — modal one-time all'ingresso in una nuova fase che celebra la fase COMPLETATA ("{Fase} complete! N weeks of focused work in the bank") + "what to expect" della nuova fase (riusa `PHASE_RATIONALES` A141); seen-tracking in `preferences.phase_celebrations_seen` (chiavi `{start_date}:{phase_id}`, scoped al ciclo → un nuovo macrociclo ri-celebra) via PUT /api/state deep-merge, **zero backend nuovo**; regola backlog: si celebra SOLO l'ingresso nella fase corrente, le precedenti non viste vengono marcate in silenzio (niente coda di modal dopo assenze); guardie: mai per la prima fase, mai in pausa, mai a ciclo finito. **P5:** copy hero rest-day su /today riframata in positivo ("Recovery is where the gains happen — your body is consolidating the last sessions"). Vincoli design doc rispettati: nessuno stato negativo, nessuno streak, skip neutro. Build frontend OK, suite invariata (2477).

- **A234 — Daily tips card on Today page (A-DAILYTIP v1)** ✅ (feature P2.9 retention/discovery, branch `brief/A234-daily-tips` → preview Vercel prima del merge). Risolve il problema reale: i beta tester non scoprono metà delle feature. **Catalog:** `backend/catalog/daily_tips/v1/feature_discovery.json` — 22 tip `feature_discovery` (replan, weekly override, free session, Session Builder, body-part picker, mobility, guided mode, Coach + note personali, backup/export, equipment, spot, pausa piano, report, outdoor stats, quick-add, tabata, whats-next, guide, radar, feedback loop). **Backend:** `backend/engine/tips_engine.py` — selezione stateless deterministica: permutazione per-utente del pool (md5 `user_id|tip_id`) indicizzata da `date.toordinal() % pool` → nessuna ripetizione entro pool-size giorni (22), utenti diversi vedono tip diversi lo stesso giorno; **deviazione documentata dal design originale** ("rotazione 30gg" → rotazione = dimensione pool, cresce col catalogo, zero stato da persistere per la selezione). Dismissal per-giorno in `user_state.tips_seen` (idempotente, trim a 100). Router `tips.py`: `GET /api/tips/daily?date=` (read-only, client-local date) + `POST /api/tips/{tip_id}/dismiss` (404 su id ignoto, 422 su data invalida). Endpoint 84 → 86. **Frontend:** `DailyTipCard` (icona Sparkles + accento sky per distinguerla dal cue banner amber A220) su `/today` sotto la quote, solo vista-oggi; dismiss ottimistico persistito server-side (cross-device); CTA `Link` alle pagine feature. Distinto da A220 daily-cue-banner (process cue di training ≠ feature discovery). Test: `test_a234_daily_tips.py` (14: catalog integrity + CTA route valide, determinismo, copertura pool completa senza ripetizioni, permutazioni per-utente, dismissal idempotente/trim/per-day, API e2e). Suite 2463 → 2477. User guide §3 aggiornata.

## Recently closed (2026-07-18)

- **B278 — Today week-load bar coherent with outdoor** ✅ (bugfix, frontend-only → branch `brief/B278-today-load-outdoor` + preview Vercel). Origine: field test Daniele — il "load" non coerente tra pagine. Audit di tutte le formule di load: `WeekProgressBar` (usato **solo** nella pagina Today) era l'**unico** a **omettere il load outdoor** — sommava done-sessions + other-activity + free ma non l'outdoor, e non riceveva nemmeno i dati outdoor. Header Week (`week/page.tsx`) e report settimanale (`report_engine.py`) includevano tutti e 4 i componenti → la barra Today leggeva più bassa esattamente della quota outdoor. **Fix:** nuovo prop `outdoorLoad` su `WeekProgressBar` incluso nel `doneLoad`; la today page calcola il totale outdoor dalla fetch sessioni già esistente (`s.load_score` sui giorni "done") e lo passa al componente. Nessun doppio conteggio (era un'omissione). **Non toccato (scelta Daniele):** la calibrazione di `compute_outdoor_load_score` — un giorno outdoor pieno (~4 vie 7a ≈ 22) resta strutturalmente sotto una gym medium (40); annotato come possibile ricalibrazione futura (metodologia). Build frontend OK.

## Recently closed (2026-07-17)

- **B277 — Manual outdoor log closes the loop** ✅ (bugfix, `backend/api/routers/outdoor.py` only — nessun modulo engine ad alto rischio; backend-only → push diretto main). Origine: field test Daniele — sessione outdoor loggata a mano (Berdorf, giovedì 16/07, 4 vie) non compariva nel Week. **Root cause:** il Week renderizza l'outdoor **solo** dal giorno del piano (`outdoor_session_status == "done"`), non dal log JSONL immutabile; ma solo `finish_outdoor_session` (flusso sessione live, B273) chiamava `_sync_plan_after_outdoor_log`. Gli endpoint `POST /api/outdoor/log` e `PUT /api/outdoor/log` (log/edit manuale) salvavano le vie ma lasciavano il giorno a "planned" → vie invisibili. **Fix:** POST + PUT ora chiamano la stessa sync best-effort (stessi guard B273: no pausa A223, no settimana passata B257, giorno nel piano) → status "done" + load + ripple. Bookkeeping `state.outdoor_log` reso **idempotente** (una entry per data, dedupe) — ripulisce anche i doppioni storici. Risposta arricchita con `plan_synced`. Test: `test_b277_manual_outdoor_log_plan_sync.py` (9: planned/unplanned close, dedupe POST+PUT, guard past-week/paused/no-plan/sync-failure, ripple). Suite 2454 → 2463. **Dati storici:** l'unica sessione invisibile in una settimana ancora memorizzata era il 16/07, chiusa manualmente via `complete_outdoor` (status done, load 21); le sessioni più vecchie stanno in week_plans trimmati (nessun piano da patchare).

## Recently closed (2026-07-15)

- **B276 — Multiple other activities same day** ✅ (chiude anche il vecchio **B133c**; bugfix + feature, tocca `planner_v2.py` + `replanner_v1.py` → moduli ad alto rischio, branch `brief/B276-multiple-other-activities` → preview Vercel prima del merge). Origine: field test Daniele — aggiungendo due "other activity" nello stesso giorno (pranzo petto + cena HIIT) la seconda **sovrascriveva** silenziosamente la prima. **Root cause:** le other activity erano campi scalari piatti per-giorno (`other_activity_*`), keyed solo per data → il secondo `add_other_activity` riassegnava gli stessi campi. **Fix:** nuovo modello a lista `other_activities: [{slot,name,status,feedback,load,duration_minutes}]`, max una per slot (morning/lunch/evening → max 3/giorno). Nuovo modulo `backend/engine/other_activity_v1.py` (normalize + migrazione legacy scalari→lista, non-mutante in lettura). Eventi `add/complete/edit/undo/remove` ora keyed by `(date, slot)`; add su slot occupato = update-in-place (no duplicati). `planner_v2` emette la lista per-slot da availability `other_sport`; `_recompute_day_status` → giorno "done" solo quando **tutte** le attività completate; `report_engine` + `_DAY_LEVEL_FIELDS` (immutabilità) aggiornati. **Frontend:** `OtherActivity[]` in types, sotto-componente `OtherActivityBlock` con stato locale proprio (N attività indipendenti, badge slot), handler today/week con slot, reports/week-progress-bar/weekly-checkin-card via helper `normalizeOtherActivities`. Retrocompat: giorni preservati pre-B276 con scalari letti via fallback, mai mutati. Test: +5 (`test_add_two_other_activities_same_day`, dedup per-slot, completamento indipendente, remove per-slot, immutabilità lista in regen). Suite 2449 → 2454. Build frontend OK.

## Recently closed (2026-07-13)

- **A233 — First-touch attribution server-side** ✅ (feature GTM, branch `brief/A233-attribution` → preview Vercel prima del merge). Origine: caso Donato — impossibile sapere da dove arriva un iscritto (UTM solo client-side → Vercel Analytics anonimo, capture solo su /demo e /subscribe, zero referrer). **Frontend:** capture first-touch estesa a `referrer` esterno + `landing_page` + `first_touch_at` e montata nel root layout (`AttributionCapture`, tutte le pagine); la review page allega `getAttribution()` al payload di `POST /api/onboarding/complete` (entrambi i bottoni). Record pre-A233 in localStorage restano compatibili (campi nuovi opzionali). **Backend:** `OnboardingData.attribution` opzionale, sanitizer server-side (whitelist 8 chiavi: 5 utm + referrer + landing_page + first_touch_at; cap 200 char; non-string droppati) → `state["attribution"]` + timestamp server `onboarded_at`, scritto prima di ogni save (sopravvive a fallimenti macrocycle). Chiave assente se capture vuota — nessuna migrazione, utenti esistenti = "—". `generate_macrocycle`/Monday invariant non toccati. **Reporting:** colonna "Origine" nei nuovi iscritti di `admin_dashboard.py` (utm_source/campaign → hostname referrer → direct). **Docs:** `docs/attribution_utm_convention.md` (convenzione canali: flyer QR, reddit, email winback…). Test: `test_a233_attribution.py` (8: sanitizer whitelist/cap/tipi + e2e persistenza/assenza, con cleanup). **Fix collaterale:** `test_b259` rotto da B275 di stamattina (invoice fixture senza `amount_paid` → skip) — fixture aggiornata, main torna verde.

- **B275 — $0 trial-invoice mascherava lo status trialing** ✅ (bugfix, `stripe_webhook.py` only — scoperto durante la verifica E2E di A232 in prod). La invoice di apertura trial è $0 e "paid" immediata → `invoice.payment_succeeded` promuoveva la riga ad `active`: banner trial/countdown/CTA add-card mai mostrati (successo anche ad Arnaud a maggio), e sulle versioni API Stripe nuove (invoice senza `subscription` top-level) sovrascriveva `stripe_subscription_id` con None. Fix: skip totale delle invoice a importo zero (un pagamento vero non è mai $0) + mai includere `stripe_subscription_id` nell'upsert quando è None. Il lockout a fine trial NON era compromesso (resolve via customer_id + metadata). 4 test in `test_b275_zero_invoice_trial.py`. Backend-only → push diretto main.

- **A232 — Card-free trial + trial-end handling** ✅ (feature P0 GTM, branch `brief/A232-trial-nocard` → merge dopo verifica preview Vercel + iPhone PWA di Daniele). Contesto: 4 checkout abbandonati su 6 tentativi alla richiesta carta, 0 paganti organici. **Backend:** Checkout Session con `payment_method_collection: if_required` + `trial_settings.end_behavior.missing_payment_method: cancel` → trial 15gg senza carta; a fine trial senza carta la sub si cancella pulita (no invoice, no dunning) e `customer.subscription.deleted` → riga locale `canceled` → guard B202 fail-closed (percorso già esistente post-B226, coperto da test). **Anti-abuso:** riga con `trial_end` valorizzato = trial consumato → nuovo checkout SENZA trial (paga subito, Stripe richiede la carta perché c'è importo dovuto); righe `pending_checkout` senza `trial_end` (i 3 drop-off pre-A232) mantengono il trial pieno (test dedicato). Nuovo handler `customer.subscription.trial_will_end` (log + alert Telegram founder, no DB write). Colonna `has_payment_method` su `subscriptions` (DDL applicata in prod), sync da webhook (`checkout.session.completed` + `subscription.updated` via `default_payment_method`), esposta da `check_subscription`/`/api/subscription/status`. Copy 402 post-trial: "Your training data is safe". **Frontend:** TrialBanner — trialing senza carta → CTA "Add payment method" → Billing Portal (fix del vicolo cieco B212: /subscribe rimbalzava i trialing a /today); copy expired aggiornato; /subscribe "no card required"; welcome bullet coach al presente (era "coming soon", coach live da A-COACH-V1a). User guide: nuova sezione 18b. Test: `test_a232_trial_nocard.py` (9 test: params checkout entrambi i price, abbandono≠consumo trial, no secondo trial, sync has_payment_method, trial_will_end dispatch/no-write, trial-end cancel → guard blocca). Nota: i 5 failure in `test_resolve_session_freshness`/`test_week_router_auto_resolve` osservati durante A232 erano regressione del tie-break B274 — risolti lo stesso giorno dal follow-up B274 (vedi entry B274).

- **B274** ✅ — Variety tie-break settimanale in `pick_best_exercise_p0` (fix finding 2 di C256, analisi Phase 1 + OK esplicito di Daniele). Root cause: chiave finale di sort = `exercise_id` alfabetico → tutti i drill `tech_*` (23 Bechtel) in coda all'alfabeto, fuori rotazione (12 drill distinti in ciclo fisso di 4 sessioni, 1 solo Bechtel in 12 settimane simulate sul profilo reale). **Fix:** `_variety_key(ex_id, seed)` = md5 di `(exercise_id | seed)` come tie-break finale nei due branch di sort; `_variety_seed_from_date(target_date)` = lunedì ISO della settimana del target_date (già disponibile: `_resolve_inline_block` riceve target_date, il path template lo ha in scope). Stessa settimana → stessa rotazione (ricarichi /week stabili); settimana nuova → pool ruotato; **senza data nel context → seed None → comportamento legacy identico** (zero regressioni sui percorsi date-less e sui test esistenti). Determinismo preservato (seed = funzione pura di un input); B120/B153b/B159b/B267/B268/B227 invariati (l'hash rompe solo i pareggi). Rimosso dead code `pick_best_exercise` (0 chiamanti; `exercise_matches_filters`/`compatible_with_location` restano, ora anch'essi orfani — candidati a pulizia futura). **Effetto misurato (profilo Daniele, 12 lunedì):** drill distinti 12→18, slot `tech_*` 8%→61% (proporzionale: 19/38 del pool eleggibile), tutti e 3 gli ex-orfani C257 in rotazione. Nuovo `test_b274_variety_tiebreak.py` (8 test: unit key/seed, determinismo byte-identico stessa data, stabilità intra-settimana, legacy date-less, rotazione ≥20 drill e ≥5 tech_* su 12 settimane). Suite verde. Backend-only → push diretto main. **Follow-up (stessa giornata):** 5 test pre-esistenti fragili al tie-break (freshness/auto-resolve working_loads: assumevano `elbow_eccentric_curl` vincitore alfabetico con target_date settato) rotti da B274 e sfuggiti al check per exit-code mascherato da `pytest | tail` → riscritti col pattern discover-then-assert (l'esercizio loadable selezionato viene scoperto a runtime, il WL entry si aggancia a quello); suite riverificata con exit code esplicito: 0 failed.
- **C257** ✅ — Fix finding 1 di C256: i 3 drill orfani di selettore (`tech_green_light_red_light`, `tech_pogo`, `tech_throwing_the_shoe`) diventano selezionabili. I 3 blocchi `technique_drill_*` di `technique_focus_gym` ora filtrano `pattern: [technique_drill, climbing_intervals, explosive_touch]` (role=technique invariato → il pool si allarga **esattamente** dei 3 ex-orfani; verificato: nessun altro esercizio ha role=technique + quei pattern). Edit chirurgico (3 righe). `easy_climbing_deload` e sessioni power NON toccate (il deload non deve pescare drill esplosivi; i blocchi power richiedono correttamente role=main). Nuovo `test_c257_orphan_drills_selectable.py` (3 test: filtri estesi, invariante "solo i 3 orfani nel pool" a guardia di future aggiunte, selezione effettiva sotto recency pressure). Suite verde. **Nota onesta:** post-C257 eleggibili ma nella rotazione reale (profilo Daniele, 12 settimane simulate) ancora assenti — il tie-break alfabetico li tiene fuori → il valore si sblocca con B-VARIETY-TIEBREAK. Catalog-only → push diretto main.

- **C256** ✅ — Batch 3/3 Bechtel Momentum Drills (Climb Strong: Drills Manual pp.72-91). **Bechtel Drills Manual integration CLOSED — 3 batch, 27 drill processati, 23 mergeati** (C240: 7/8, C255: 6/8, C256: 10/10). **10 drill mergeati**: `tech_contrast_bouldering` (p.72, orig. Gimme Kraft), `tech_foot_flyaways` (p.74), `tech_green_light_red_light` (p.76), `tech_hard_target` (p.78), `tech_hips_first` (p.80), `tech_hop_and_skip` (p.82, orig. Dave Wetmore), `tech_pogo` (p.84), `tech_smooth_is_fast` (p.86), `tech_the_bump` (p.88), `tech_throwing_the_shoe` (p.90, erratum p.91 documentato in prosa). **Dedup: 4 sospetti, tutti MERGE** (contrast vs sloth_monkey: within-problem tempo vs whole-ascent style, distinti + stesso recency_group per competere; pogo/throwing vs power_slap: leg-swing momentum vs pull RFD; smooth_is_fast vs slow_climbing: progressione slow→fast vs solo-slow, stesso gruppo pacing; green_light vs route_intervals: sprint tecnico su open holds vs PE su corda). **hop_and_skip INCLUSO con time_min=30** (evidenza: `time_min` non è consumato da nessun codice backend/frontend — solo metadato; precedente tech_applied_strength già a 30). Pattern `climbing_intervals` ed `explosive_touch` canonici (verificati su route_intervals e power_slap_drill), zero mapping. stress_tags: `shoulders` droppato (verdetto C255), 4 chiavi canoniche ovunque. recency: nuovo gruppo `technique_momentum_drills` (foot_flyaways, pogo, throwing_the_shoe, the_bump, hop_and_skip) + per-domain per gli altri (contrast→movement, smooth+green_light→pacing, hard_target→footwork, hips_first→body_position). D80 ✅ (campus solo in prosa, test di guardia). D133 ✅ (the_bump 15s, throwing_the_shoe 15s+120s, hard_target 40s). Fix in corso d'opera: grade anchor mancante su foot_flyaways (boulder_max_os −2, warm-up level). Catalogo 232→242. `test_c256_momentum_drills.py` (11 test). Suite verde (2415). **⚠️ 2 finding flaggati:** (1) `tech_green_light_red_light`/`tech_pogo`/`tech_throwing_the_shoe` sono **orfani di selettore**: hanno role=technique ma i blocchi che filtrano i loro pattern (pe_routes/pe_boulder/boulder_circuit_main/campus_power) richiedono role=main + domain power/contact → oggi nessuna sessione li seleziona. Opzioni: estendere i filtri di technique_focus_gym ai 3 pattern (C-brief futuro) o accettarli come catalog-only. (2) Tie-break per ordine-file → vedi B-VARIETY-TIEBREAK in Open. Verifica sul profilo reale di Daniele: 19 Bechtel eleggibili al suo gym (solo banded_climber esclusa, serve resistance_band), auto-resolve ri-risolve le sessioni pending ad ogni GET /week → nessuna rigenerazione piano necessaria, i drill sono in pool dal primo load post-deploy. Catalog-only → push diretto main.

- **C255** ✅ — Batch 2 Bechtel Movement Drills (Climb Strong: Drills Manual pp.51-69), follow-up del pilot C240. **6 drill mergeati** (di 8 nel patch KB): `tech_barn_door_2000` (p.52), `tech_climb_it_backwards` (p.56), `tech_deadpoint_roll_through` (p.58), `tech_foot_to_hand` (p.60, orig. Lattice), `tech_single_leg_climbing` (p.66), `tech_trust_the_eyes` (p.68). **2 esclusi:** `tech_move_and_lock` SKIP per dedup (meccanica pause-before-latch = `hover_hands`; lato tension-awareness = `freeze_drill` — stesso trattamento di matched_breathing nel pilot); `tech_rockovers` EXCLUDED — richiede `plyo_box`, token assente dal vocabulary §1.2, no silent vocabulary extension → **flag back al KB project** (decidere se aggiungere il token o riscrivere il drill senza box). **Remapping schema v1:** equipment `bouldering_wall`→`gym_boulder`, `spray_wall`→`spraywall`, `system_board`/`fixed_board`→`board_*`; gate C243 standard (`equipment_required: []` + `equipment_required_any` a 6 superfici) su tutti; `campus_board`/`hangboard` del patch droppati (erano solo su move_and_lock, skippato). stress_tags rimappati al canon fingers/elbow/cns/skin (`core_tension`→`cns`, `lock_off`→`elbow`; droppati `skill`/`shoulders`/`hip_mobility`/`legs` — nessun equivalente canonico). `experience_level` droppato (0/28 technique drill usano difficulty_tier). **Deviazione dal patch documentata:** recency_group allineato al domain per convenzione catalogo (barn_door→body_position_drills, foot_to_hand→footwork_drills, single_leg→constraint_drills, altri 3→movement_drills) invece del singolo `technique_movement_drills` del patch. load_model per-drill: `grade_relative` (boulder_max_os −2) su climb_it_backwards e single_leg, `bodyweight_only` sugli altri 4 (sequenze auto-costruite/open holds). D133: rest_between_reps_seconds esplicito (15-20s) sui 4 drill side-switching. Catalogo 226→232 (count test aggiornato; nota: base era 226 post-C251, non 225 come da brief). Nuovo `test_c255_movement_drills.py` (9 test: presenza, 5 campi prescription canonici, load_model+grade anchor, equipment canonici, stress_tags canonici, D133, invariante C243 wall-surface, pickup resolver, no-leak no-wall). **Smoke pickup:** `technique_focus_gym` (lead intermediate, gym_boulder+gym_routes) risolve; sotto pressione di recency il resolver seleziona `tech_barn_door_2000`+`tech_climb_it_backwards`+`tech_deadpoint_roll_through` → pickup reale confermato; graceful skip a no-wall gym invariato. Suite verde. Catalog-only → push diretto main. **Next batch KB: Momentum (pp.71-91, ~9-10 drill).**

## Priority 1.25 — Audit Remediation (D163 + D164)

> Full reports: `docs/audit/D164/` (138 findings) and `_archive/docs/frontend_audit_D163.md` (67 findings)
> Date: 2026-03-28
> Combined: 205 findings (20 P1, 71 P2, 102 P3, 12 P4)

### P2 highlights (not individually tracked — see full reports)

**Engine (D164 Agents 3-5):** Phase duration sum mismatch for 9-11 week macrocycles (P2), deload weights sum 0.40 not 1.0 (P2), `move_session` doesn't validate spacing (P2), `_reconcile()` enforces finger but not hard-day spacing (P2), streak field saved but unused in multiplier (P2).

**Frontend (D164 Agent 1 + D163):** PHASE_LABELS duplicated 4 files, `window.location.href` instead of router.push, console.warn/error in prod, eslint-disable on hooks deps, hardcoded email, session-card 1081 lines, tap targets <44px (6 instances), missing aria-labels (5 instances) → partially covered by B165c, rest deferred to R141/R144/R145.

**Catalog (D164 Agents 7-8):** 10 campus exercises use non-canonical `age_under_16` contraindication, `easy_climbing_deload` legacy schema, `deload_recovery` missing fields, 8 orphan templates, 11 generic placeholder video URLs → covered by B165e.

**Docs (D164 Agent 6):** Intent counts wrong in CLAUDE.md (13+3 vs actual 15+4), `closed_loop_v1.py` filename stale, session "active" label mismatch in sync_status.py, `grip_transition` missing from vocabulary → vocabulary fix in B165a, rest are P2 doc fixes (standalone).

**API contract (D164 Agent 9):** `POST /api/outdoor/convert-slot` response shape mismatch.

**Test coverage (D164 Agent 10):** 9 API endpoints lack integration tests, no full-pipeline E2E test (R150), `cluster_utils` 5/6 functions untested, test fixtures duplicated inline.

### P3 items (102 total) — see full reports, not individually tracked in roadmap

---

## Priority 1.26 — Audit Remediation (D170 + D172)

> Full breakdown: tracked inline in this roadmap (see P1.26 priority list below). The file `D172_findings_tracker.md` was planned but never created.
> Audits: D170 (gym_id propagation, 24 findings, 2026-03-31), D172 (all other fields: session_id / template_id / equipment / slot / phase / API validation, 25 findings, 2026-03-31)
> Combined: 49 findings — 13 fixed in B173, 2 P1 hotfixes pending (B174/B175), 21 deferred to B176

### Post-launch (P2)

| ID | Title | Type | Effort | Notes |
|----|-------|------|--------|-------|
| **B176** | D172 consolidated remediation — 21 remaining findings (P2+P3) | B | L | 5 groups: type safety (D172-05,11,12), equipment validation (D172-07,08,22), event/input validation (D172-09,13,14,25), logging (D172-10,15,17-20,23,24), structural/deferred (D172-16,21). Supabase migration already complete — no longer a prerequisite. |

### Deferred from B173 (need API refactoring)

| Title | Priority | Effort | Notes |
|-------|----------|--------|-------|
| `apply_day_add` doesn't receive `gyms` parameter (D170 P1-04) | P3 | M | Needs signature refactoring. Frontend fix in B173 covers the main user-facing path. |

---

## Priority 1.27 — Audit Remediation (D211 / D-TESTUSER-VERIFY residuals)

> Origin: `docs/audit/D-TESTUSER-VERIFY_report.md` §5 (2026-04-19)
> F1 (HIGH) + F3 (HIGH) closed by D214 (`assessment.tests_source` sidecar). Residuals below parked post-launch.

### Post-launch (P2/P3)

| ID | Title | Severity | Priority | Type | Effort | Notes |
|----|-------|----------|----------|------|--------|-------|
| F2 | **Onboarding input validation** — no bounds on BW/height/age/test inputs (BW=33 kg, height=33 cm, age=3, max_hang=3.5× BW accepted silently; radar saturates to 100). | MEDIUM | P2 | B | S | Add range checks at onboarding: BW 35–150 kg, height 120–220 cm, age 10–80, max_hang ≤ 3× BW (soft-warn). |
| F4 | **Stale cached week plan across deploys** — no regeneration trigger on deploy; users onboarded within ~5 min of a push keep pre-push output. | LOW | P3 | B | XS | Accept (deploy-window artifact). Users can force-regenerate via Settings. Document in user guide. |
| F5 | **`goal.primary_weakness`/`secondary_weakness` are absent** — actual storage at `assessment.self_eval.*`. Consumers reading `goal.*` see `None`. | LOW | P3 | D+B | XS | Grep consumers; if any read `goal.*` for weaknesses, fix read site (not write). Spec-drift only. |
| F6 | **`macrocycle.phases[].weeks` is `null`** — consumers iterating `phases[].weeks` see `null`; sum via `start_week` deltas works. | LOW | P3 | D+B | XS | Audit consumers; drop the field from schema if all compute from `start_week` deltas, else populate at generation. |
| F7 | **`goal.deadline` empty while `total_weeks=12`** — onboarding writes `deadline=""` when deadline is derived from `total_weeks`. | LOW | P3 | B | XS | Cosmetic. Compute ISO date from `total_weeks + start_date`, or drop the field. |
| F8 | **`assessment.tests.last_test_date = 2026-04-16`** (3 days before macrocycle start) — writer not traced in D211. | COSMETIC | P3 | D | XS | Grep writer site; likely legacy path in `progression_v1.py`. |
| F9 | **Pass 3 test placement requires non-empty day** (`planner_v2.py:1360`: `if not day_sessions[offset]: continue`). Tests can only replace existing sessions — users with few available days silently lose tests. | MEDIUM | P2 | B | S | Loosen empty-day rule for test sessions, or order `required=True` first across axes. |

---

## Priority 1.28 — Audit Remediation (D236)

> Tracking docs: `docs/audit/D236/00_remediation_plan.md` (piano completo, 6 Group), `docs/audit/D236/00_findings.md` (47 finding deduplicati su 78 raw).
> Audit: D236 read-only cleanup, completato 2026-05-09 (47 findings: 6 P0, 22 P1, 13 P2, 6 P3).
> Group 0 chiuso da B-SYNC-FIX (2026-05-10). Group 1-6 aperti come C-brief indipendenti.
>
> **Ordine raccomandato**: Group 3 → Group 1 → Group 6 → Group 4 → Group 2 → Group 5.
> Razionale: Group 3 fixa code-ref errati in CLAUDE.md (F-15 closed_loop path, F-16 planner_v1→v2) — file letto da ogni istanza Claude Code, alta probabilità di morsicare in brief macrocycle/engine. Group 1 chiude P0 Stripe/pricing lies in PROJECT_BRIEF e ROADMAP. Group 6 sblocca KB anchors per D33/CUE-02. Resto è cleanup.

| Group | Title | Type | Effort | Status | Notes |
|---|---|---|---|---|---|

---

## Priority 1.75 — Go-to-Market Sprint

> Origin: Strategic Advisory Council (2× runs, 5 advisors each, 2026-04-01)
> Key insight: distribution + onboarding friction are the real blockers, not features.
> Constraint: solo founder, zero marketing budget, feature freeze for 30 days.
> Stripe status: LIVE since 2026-04-16, sk_live keys on Railway + Vercel.

### Timeline

- **Week 0 (archived, ~2026-04-01):** Beta testers using the app (4-5 users). Founder dry-run. Stripe LIVE since 2026-04-16, sk_live keys on Railway + Vercel.
- **Week 1-2:** Collect beta feedback + fix onboarding blockers from dry-run.
- **Week 2-3:** Pricing decision → activate Stripe live → soft launch on r/climbharder.
- **Week 3-6:** Feature freeze. Only fix bugs from paying/trialing users. Measure.

### Phase 0 — Onboarding dry-run + beta feedback (week 0-2)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| GTM-02b | **Beta tester feedback collection** — structured check-in with Christie, Cesar, Paolo, Agustin on their experience | — | XS | Open | Ask: what confused you? what's missing? would you pay? Key signal: would they pay $9.99/mo Standard (or $4.99/mo as a Founding Climber). |

### Phase 1 — Pricing + Stripe go-live (week 2-3)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| B205 | **Verify cancel_at_period_end grace period** | B | XS-S | 🔁 Rolled into B226 | Targeted test added inside B226 (`stripe_webhook.py` is opened once for fail-loud + customer.deleted + cancel_at_period_end). Marginal cost. |
| GTM-STRIPE-TAX | **Stripe Tax registration** | Config | S | 🟡 Deferred | Reactivate when **either** condition met: (a) 10+ paying EU customers, OR (b) €5k cumulative EU revenue, OR (c) approaching €10k OSS threshold. Below these, IT domestic VAT rules apply (regime forfettario or ordinario per Daniele's setup), Stripe Tax is scope creep. When reactivating: 4 dashboard steps + 4-line code change in `subscription.py:108-124` (`automatic_tax: {enabled: true}` + `tax_id_collection` + `billing_address_collection: 'required'`). Decide now: prices $9.99/$4.99 are **net** (exclusive — VAT added on top at activation) — document this so future activation is consistent. |
| GTM-05 | **r/climbharder soft launch** — post asking for 5 beta testers, zero pitch | — | XS | Open | Not a code task. After B204 + B203. |
| B228 | **Frontend 402 global handler in `api.ts`** | B | S | Open P2 | Audit F4. Centralize 402 → router.push('/subscribe') + sonner toast. Frontend branch + Vercel preview. After both P1. |

### Phase 2 — Measure + iterate (week 3-6)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| GTM-06 | **Feature freeze** — zero new features for 30 days, only fix bugs reported by paying/trialing users | — | — | Open | Starts when first non-beta user signs up. |
| GTM-07 | **Success metric** — 3-5 paying users by end of April 2026 | — | — | Open | 0 paying after 30 days → reassess PMF. 3+ paying → validate and continue. |
| D230 | **Frontend lint hygiene — 30 errors / 38 warnings** | D | M | Open P3 | Audit F5. Mostly `react-hooks/set-state-in-effect` from React Compiler in Next 16. CI does not enforce, but debt accumulating. One afternoon, branch + preview. After GTM stability window. |
| A-CLIMB-CLIENT-ID | **Id climb generato client-side e propagato al backend** | A | S | Open P3 | Registrato da A245 Phase B. Una climb loggata offline entra in UI con un **indice locale provvisorio**; il server assegna il suo indice reale al replay dell'outbox. Nella finestra fra replay e refetch, `DELETE /api/free-session/{id}/climb/{climb_index}` può colpire la riga sbagliata perché l'indice mostrato non è ancora quello del server. Mitigazione attuale: il delete fa rollback ottimistico su fallimento, e la finestra è breve. **Fix vero:** id client-side (UUID) generato al log, propagato nel payload e usato dal backend come chiave di identità al posto dell'indice posizionale. Tocca `free_session` router + `climb-logger.tsx`. |
| A-DELTA-EVENT-ENDPOINT | **Endpoint replanner a delta (evento singolo, non piano intero)** | A | M | Open P3 | Registrato da A245 Phase B. Oggi `POST /api/replanner/events` spedisce l'**intero** week plan e il backend lo persiste sovrascrivendo: per questo Done/Skip è escluso dall'outbox offline (riprodurre uno snapshot catturato ore prima sovrascriverebbe tutto ciò che è successo nel mezzo e potrebbe toccare sessioni passate, violando il pilastro di immutabilità). Offline oggi fallisce con messaggio esplicito. **Trigger:** aprire solo se i dati d'uso mostrano domanda reale di Done/Skip offline — non prima. Un endpoint a delta renderebbe l'evento accodabile in sicurezza e chiuderebbe anche la radice di F6. |
| A-CLOSED-LOOP-ACTIVATION | **Decidere se attivare il cooldown per-cluster (o rimuoverlo)** | A | M | Open P2 · **sunset 2026-09-20** | Brief di decisione aperto da A245 E-4, opzione (c). `record_cluster_cooldown()` scrive `cooldowns.per_cluster`, che **è letto in produzione** da `resolve_session._cooldown_until_date` e piloterebbe due comportamenti reali (`cluster_cooldown_fallback`, `cluster_cooldown_downshift`) — ma nessuno la chiama, quindi il dizionario è sempre vuoto e nessuno dei due è mai scattato per un utente. **La domanda da rispondere, con dati di feedback veri:** collegarla al feedback path significa che dopo un `fail`/`too_hard` l'utente subisce *sia* il calo di carico che `progression_v1.apply_feedback` già applica sui `working_loads`, *sia* la sostituzione/declassamento dell'esercizio — **doppia penalizzazione**. Serve misurare quanto spesso i due si sovrappongono su feedback reali prima di decidere; se l'overlap è alto, o si attiva solo un ramo o si smorza `progression_v1` di conseguenza. **Sunset clause:** se non attivato entro ~2 mesi (≈ 2026-09-20), default a rimozione completa (opzione (b)) — modulo, i due rami nel resolver, i test e la sezione §8 di `ENGINE_ARCHITECTURE.md`. Nel frattempo la doc dice il vero (⚠ not wired). |
| B-TEST-STATE-ISOLATION | **I test API scrivono nel `backend/data/user_state.json` reale** | B | S | Open P2 | Trovato in A245 Phase E (2026-07-20) rivedendo il diff di E-6, che mostrava lo state file sporco. **Sistemico, non un caso isolato:** ogni test che usa `TestClient` senza monkeypatchare `STATE_PATH` scrive nello state vero del repo — verificati 5/5 fra i candidati (`test_b119_start_date_monday`, `test_onboarding_boulder`, `test_a205_custom_session`, `test_free_session`, `test_body_part_picker_api`); ~16 file non isolano. Stessa classe di [[B-TEST-COACH-ISOLATION]], che però **deliberatamente** non redirezionò `STATE_PATH` («i moduli che ne hanno bisogno puntano già alla propria copia tmp e un override globale litigherebbe con loro»). **Quindi il fix non è una fixture autouse ingenua**: serve capire quali moduli si auto-isolano e quali no, e redirezionare solo per i secondi (o convertirli tutti alla stessa fixture). Rischio attuale: un `git status` sporco dopo ogni run maschera modifiche vere e può far committare stato di test. |
| B-RESOLVE-ERROR-UI | **`resolve_error` non è ancora letto dal client** | A | XS | Open P3 | A245 E-3 (B17) marca lato backend le sessioni la cui risoluzione è fallita (`resolve_error: true` in `week.py` e `replanner.py`), distinguendole da «nessun esercizio compatibile». Il client non lo legge ancora: la session card resta identica nei due casi. Manca la metà frontend — stato d'errore esplicito con retry sulla card. Registrato subito per non lasciare orfano un campo che nessuno consuma (esattamente il pattern di B8/E-4). |
| B-TSC-TEST-ERRORS | **2 errori `tsc --noEmit` preesistenti nei test frontend** | B | XS | Open P3 | Trovati durante A245 Phase A (2026-07-20), non introdotti da essa. `components/session-play/__tests__/custom-playback.test.ts:7` — `notes?: string \| undefined` non assegnabile a `CustomSessionExercise.notes: string` (il fixture omette un campo required, o il tipo dovrebbe essere opzionale). `lib/__tests__/equipment-filter.test.ts:16` — TS2783, `equipment_required` specificato due volte nello stesso oggetto literal: la seconda occorrenza sovrascrive silenziosamente la prima, quindi **il test potrebbe non star testando quello che crede**. Non bloccano `npm run build` (i test sono fuori dal type-check di build) — per questo sono sopravvissuti. Verificare per prima cosa il secondo: è un potenziale falso verde. |

### Council recommendations (reference)

**Convergence across both runs (high confidence):**
- Launch NOW — Supabase migration is not a blocker (JSONB handles ~260KB/year/user)
- r/climbharder is the #1 acquisition channel
- Zero new features for 30 days post-launch
- Onboarding is the critical blind spot — no advisor caught it initially, both chairmen flagged it
- Don't build Kilter/Capacitor/LLM Coach before validating willingness to pay

**Divergence (Daniele decides after beta feedback):**
- Price: €14.99/mo (Run 1) vs €9.99/mo Founding Climber lock-in (Run 2)
- Synthesis: €14.99 standard + €9.99 Founding Climber for first 20-30 users

---

## Priority 2 — Auth + Payments + DB (go-to-market blockers)

Clerk auth ✅, Supabase JSONB ✅, and Stripe ✅ are complete. Stripe LIVE since 2026-04-16.

- **Supabase migration** ✅ — JSONB live in production (6 tables: users, session_logs, outdoor_logs, event_logs, recovery_codes, subscriptions)
- **A159 — Stripe subscriptions** ✅ — **LIVE** (sk_live keys on Railway + Vercel). Two-tier pricing ($9.99 Standard + $4.99 Founding Climber). B202 fail-closed guard active. B226 hardening done: fail-loud (500 → Stripe retries), LRU event dedup, customer.deleted handled. No known gaps.
  - Backend: `subscription_guard.py`, 4 endpoints (status/checkout/portal/webhook), guards on 10 POST endpoints
  - Frontend: `useSubscription()` hook, `TrialBanner`, `/subscribe` page, settings portal link, guided session gate
  - Phase 3: `onboarding/start-week` → redirect to `/subscribe` (both Continue and Skip)
  - SQL migration: `_archive/docs/migrations/subscriptions_table.sql` — ✅ run in Supabase (confirmed 2026-03-31)

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

## Priority 2.5 — Session Quality (post-launch)

### Flex/rest auto-fill (Pass 3)

**Status:** Open | **Effort:** S

After Pass 1 (primary) and Pass 2 (complementary), add a Pass 3 that fills remaining empty days with flex/rest/mobility sessions. Currently empty days stay empty. Especially needed in deload phase (3 sessions on 7 days). Depends on: nothing.

## Priority 2.5b — Catalog & Polish

### C130 — Audit sistematico domain/intensity/pattern

**Priority:** P2.5 | **Status:** Partially closed (2026-03-22)

**Completato:** Audit 178 esercizi, 5 intensity mismatch corretti, 4 session filter corretti, 9 sessioni orfane triagate.

**Ancora aperto:** ~33 pattern/domain borderline cases (multi-domain exercises, vocabulary gaps) — richiedono decisione design.

### A-B10 — Board benchmark tracking

**Priority:** P2.5 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Track max grade + angle per board type in free session logs. Dashboard trend widget. Optional benchmark problems (user marks 2-3 reference problems).

### A-B11 — Movement drills for boulder in exercise catalog

**Priority:** P2.5 | **Status:** Open | **Type:** C (catalog) | **Effort:** S

Add exercises: flagging practice, heel/toe hook drills, volume traversing, coordination drills, drop knee practice, body tension drill, smearing practice. Tag with technique_drill pattern.

### A-B12 — Discipline-aware PE routing

**Priority:** P2.5 | **Status:** Open | **Type:** A (planner) | **Effort:** S

Expand gym-aware PE routing: boulder discipline → prefer gyms with gym_boulder, lead → prefer gym_routes, all_round → no preference.

### A-B13 — Conditioning weights audit per discipline

**Priority:** P2.5 | **Status:** Open | **Type:** A (engine) | **Effort:** S

Audit `_BASE_DOMAIN_WEIGHTS` for boulder: more power pulling, core, antagonist push; less ARC, forearm endurance.

### A-B14 — Free session UX for boulder

**Priority:** P2.5 | **Status:** Open | **Type:** A (frontend) | **Effort:** S

Phase-aware suggestion card when logging free session on gym_boulder. Grade range suggestions based on user max + phase.

### A-B15 — Spray wall as guided session surface

**Priority:** P2.5 | **Status:** Open | **Type:** A (catalog) | **Effort:** S

Add spraywall to location_any for relevant session templates: limit bouldering, technique drills, work capacity circuits.

### Exercise images for complex exercises

**Priority:** P2.5 | **Status:** Open — TBD post-launch | **Type:** A + C (schema + content)

- Add `image_url` or `images[]` field to exercise catalog schema (currently no image support — only `video_url` exists)
- Generate instructional images (Gemini AI) for exercises that assume prior knowledge and are hard to understand from text alone
- Priority targets: hangboard grip exercises (grip_transitions, overcoming_isometric_pull), campus board exercises, technique drills
- Style: clean side-view instructional photos, consistent framing, suitable for in-app display on exercise detail cards
- Frontend: display image(s) on `exercise-detail-sheet.tsx`, above or below the description
- Discovered during B157 audit: `grip_transitions_half_to_open` was the only hangboard exercise with a one-line description and no visual reference

---

## Priority 2.9 — Retention & Discovery (post-launch)

> Origin: discussione 2026-05-08 (gamification + daily tips).
> Filosofia guida: "Train better, not more" (D79). Nessun elemento premia giorni consecutivi, volume cumulativo, o RPE alto. Si premia qualità, completamento di fase, e rispetto del recupero.
> Tutte le entries sono post-launch. Non toccano moduli high-risk (planner_v2, replanner_v1, macrocycle_v1, resolve_session, progression_v1, closed_loop_v1).
> Da rivisitare quando: 3+ paying users attivi da 30 giorni + feature freeze conclusa.

### A-DAILYTIP-V2 — Daily tips: categorie future (stub)

**Priority:** P3 | **Status:** Open | **Type:** A + C | **Effort:** S-M

Espansione di A234 (v1 chiusa 2026-07-19): categorie `training_science` (Hörst/Lattice tip tecnici) e `personalized` (basato su user_state, es. "Test repeater programmato la prossima settimana — riposa bene il giorno prima"). La v1 copre solo `feature_discovery` (22 tip).

### A-GAMIFY-04 — Weekly adherence "perfect week" badge (opzionale)

**Priority:** P4 | **Status:** Open — opzionale | **Type:** A | **Effort:** M
**Depends on:** A-GAMIFY-00, A-GAMIFY-01

Riconoscimento per chi ha completato fedelmente la settimana programmata, **incluso il rispetto dei rest day**.

**Engine:** `compute_week_adherence(week_plan, logs)` → `{score: 0-100, perfect: bool}`. "Perfect" = sessioni hard fatte nei giorni programmati + nessuna sessione extra non programmata (anti-overtraining).

**Rischio:** tocca la semantica del piano, può essere percepito come pressione. **Da fare per ultimo**, dopo aver visto la reazione utenti ai 3 elementi precedenti. Se feedback negativo → si scarta.

### Sequenza implementazione consigliata

1. ~~A-GAMIFY-00~~ ✅ doc `docs/design_gamification.md` approvato da Daniele (2026-07-19)
2. ~~A-DAILYTIP~~ ✅ chiusa come **A234** (2026-07-19)
3. ~~A-GAMIFY-01~~ ✅ chiusa come **A235** (2026-07-19, include P5 rest-copy)
4. ~~A-GAMIFY-03~~ ✅ chiusa come **A236** (2026-07-19, heatmap rest-positive)
5. ~~A-GAMIFY-02~~ ✅ chiusa come **A239** (2026-07-20, milestone system, 22 milestone)
4. **A-GAMIFY-03** (S) — heatmap mensile
5. **A-GAMIFY-02** (M) — milestone system
6. **A-GAMIFY-04** (M, opzionale) — perfect week, solo se feedback positivo sui 3 precedenti

**Effort totale:** ~5-7 giorni di lavoro post-launch.

### C-FEEDBACK-LOOP — Feedback-loop email automation

**Priority:** P2.9 (post-launch, alongside C-RETENTION-ROADMAP) | **Status:** Open — design only, no implementation | **Type:** A (automation) | **Effort:** M+
**Depends on:** LLM coach layer (Phase 3.5) + knowledge-base RAG (solo per Track B)

> **⚠️ Timing — NON ora.** Da affrontare **solo quando ci saranno tanti utenti**: finché il volume di supporto è gestibile a mano, il valore non giustifica il lavoro. Inbox di gestione: **daniele.somensi@gmail.com**. Origin: Daniele (2026-05-31).

Automatizzare il loop di feedback/supporto clienti oggi gestito manualmente (welcome email a mano, risposte via Claude).

**Due track disaccoppiati — ship indipendenti:**

- **Track A — Outbound (basso rischio, può partire per primo):** trigger Stripe webhook `customer.subscription.created` → invia welcome/feedback email templata (deterministica, no LLM). Idempotenza: dedupe su subscription id; mai re-inviare su plan change o device switch. Nessuna dipendenza da Phase 3.5 — standalone.
- **Track B — Inbound (gated su Phase 3.5):** cron (Claude Code su Mac) polla l'inbox supporto, classifica ogni reply (feedback / training question / feature request / bug). Training questions → LLM coach risponde via KB RAG (stesso layer di Phase 3.5, NON costruire un secondo RAG). Feature requests/bug → auto-file come roadmap candidate.

**Non-negoziabili Track B:**
- **Human-in-the-loop finché piccolo.** Il cron CLASSIFICA + DRAFTA solo. Daniele approva prima dell'invio. Nessuna risposta LLM non supervisionata a clienti paganti (rischio allucinazione/reputazione su consigli di training).
- **Accesso inbox separato da claude.ai.** Il connettore Gmail nella chat claude.ai NON dà a Claude Code su Mac accesso all'inbox. Il cron serve credenziali proprie (Gmail API / IMAP) sul Mac.
- **La KB è prerequisito, non side-project.** Risposte "tailored" hanno senso solo quando il coach legge la KB letteratura. Allineato a Phase 3.5 RAG.

**Open decisions prima di qualsiasi brief:**
1. Indirizzo inbox supporto + routing delle reply → **daniele.somensi@gmail.com** (deciso).
2. Metodo di accesso inbox Mac-side per il cron.
3. Soglia auto-send (se mai) — definire l'exit criteria dell'human-in-the-loop.

---

## Priority 2.75 — KB Research Integration

> **Companion project:** The KB research lives in a **separate claude.ai project** called **"climb-agent knowledge base"**.
> All research files, Hörst syntheses, topic files, and decision consolidations live in that project's knowledge.
>
> **⚠️ RULE: Before implementing any deferred decision from the backlog below, open the KB project and check
> `_archive/docs/horst_integration_audit.md` for enrichment material. Many deferred decisions have ready-to-use content.**

### Open KB Research Items

| Item | Status | Where |
|------|--------|-------|
| Session 2 patch (4 corrections: D11, D12, D39, D72) | ⏸️ Prepared | KB project memory (not yet a file) |
| D84 pulling strength test (max load review) | ⏸️ Under review | KB project |
| Finger strength test architecture (5s→7s Lattice) | ⏸️ Under review | KB project |
| CUE-02 formalize (forearm stretch → D33 amendment) | 📋 Proposed | `_archive/docs/horst_integration_audit.md` §6 |
| Coach KB spec: add 8 Hörst coaching cues | 📋 Proposed | `_archive/docs/horst_integration_audit.md` §5 |
| Decision consolidation: append D84-D91 | 📋 Proposed | `kb_gaps_analysis.md` |
| Topics 05-10 Steps 4-5 (decision specs) | ⏳ Not started | KB project |

### Remaining Books

| Book | Status | Needed for |
|------|--------|-----------|
| Bechtel — Climb Strong: Drills Manual (pp. 31-90) | 📷 Photograph physical copy | Topic 08 drills |
| MacLeod — 9 Out of 10 Climbers | 🛒 Buy (DRM-free PDF or photos) | Topics 04, 05, 07, 08 |
| Ilgner — The Rock Warrior's Way | 🛒 Buy | Topics 05, 09 |
| Mobråten — The Climbing Bible | 🛒 Buy | Topics 01, 02, 04, 07, 08 |
| Christophersen — Climbing Bible: Injuries | 🛒 Buy | Topic 07 |

---

## Priority 2b — Test results → full exercise calibration

Every test result we collect MUST influence exercise prescription.

| Test result | Current use | New use | Impact |
|-------------|------------|---------|--------|
| L-sit hold (sec) | radar only | Core progression tier (3 tiers) | Exercise selection + prescription |
| Hip flexibility (cm) | radar only | Mobility tier (skip acquired stretches) | Exercise selection |
| Repeater 7/3 max sets | radar only | Finger endurance volume calibration | Prescription (sets/volume) |
| Max hang duration (sec) | radar only | Endurance hang calibration | Prescription (time) |

Depends on: B122 pattern. Supabase migration ✅ complete.

---

## Priority 2.8 — Refactoring

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R143 — Refactor replanner_v1.py

**Status:** Open | Spezzare in package `replanner/` + estrarre `_SESSION_META` in modulo condiviso.
**Rischio:** ALTO — mandatory analysis phase

### R145 — Spezzare pagine componente grandi

**Status:** Open | `today/` (971), `week/` (889), `settings/` (1018), `guided/` (600+) → hook + sotto-componenti.
**Rischio:** MEDIO

### R146 — Estrarre logica duplicata

**Status:** Open | Backend: load score utility. Frontend: `useSessionHandlers` hook, shared states.
**Rischio:** MEDIO

### R147 — Resolve Session Refactor

**Status:** Open | Spezzare `resolve_session()` + pipeline pattern per filtri P0.
**Rischio:** ALTO — mandatory analysis phase

---

## Priority 2.75 — Architecture

### D168 — Outdoor / Week Plan Unification Audit

**Priority:** P2 | **Status:** Audit done (D170) — implementation open | **Type:** D (architecture audit) | **Effort:** L

Outdoor sessions and week plan are two separate systems that don't communicate:
- Outdoor: JSONL storage, `/api/outdoor/*` endpoints, `OutdoorLogForm` component
- Week plan: `user_state.week_plans`, `/api/week/*` endpoints, week/today views

Problems caused by this split:
- Today/Week views don't show outdoor sessions logged via /outdoor
- Multiple entry points create sessions in different backends
- Delete mechanisms are inconsistent (week plan removal vs JSONL deletion)
- Same-day conflict checks need to be duplicated everywhere

Audit should:
1. Map all data flows and entry points
2. Propose single source of truth for daily sessions
3. Design unified view: Today/Week shows ALL sessions (planned + outdoor + free)
4. Migration path from current split to unified model

Depends on: B186 (immediate fixes). Must be done before further outdoor features.

Audit deliverable: `docs/audit/outdoor_audit_D170.md` (2026-04-04) — 13 findings (2 P1, 5 P2, 6 P3), 5 redesign recommendations. Root cause of outdoor+indoor coexistence bug identified (F1: `add_outdoor` doesn't clear sessions).

---

## Priority 3 — UI polish

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B40 | Branch develop/main workflow | S | Staging/production branches |

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

## Priority 4 — Go-to-market

- Landing page / marketing site
- ~~Pricing model definition~~ ✅ Decided (final): USD $9.99/month Standard (15-day trial) + USD $4.99/month Founding Climber (first 20 users). Net/exclusive (VAT added on top at future Stripe Tax activation, decision locked 2026-04-28). Live since 2026-04-16.

### Capacitor Native Wrap

**Status:** Open | **Effort:** S (base wrap) / M (with native plugins)
**Recommended timing:** 2-4 weeks post soft-launch, after stabilization.

Base wrap (1-2 days): wrap the Next.js PWA in Capacitor for App Store + Google Play. Identical UX to PWA but gains: native push notifications, no localStorage loss on iOS Safari, App Store credibility. Free to test on own devices (Xcode + free Apple ID); Apple Developer Program (99€/yr) only needed for App Store publication. Google Play: 25$ one-time.

Native plugins (incremental): BLE (Kilter Board), haptics, background timers. Each plugin added as needed.

**Dependency sequence:** PWA soft-launch → bug stabilization → Capacitor base wrap → native plugins (BLE for Kilter, etc.)

### Board-specific features (Kilter first)

**Status:** Open | **Effort:** L (basic) / XL (games)

**Dependency sequence:** PWA launch → stabilization → Capacitor base wrap → Level 1 → Level 2.

**Level 1 — Data integration (L):**
API integration for Kilter Board problem lookup, difficulty grades, and ascent logging. Use [BoardLib](https://github.com/lemeryfertitta/BoardLib) (Python) for Aurora API access — downloads the SQLite DB with holes, LEDs, placements, and climbs. Covers all Aurora boards (Kilter, Tension, Grasshopper, Decoy). Other boards (MoonBoard) follow same pattern. Can start before Capacitor (data layer is web-only).

**Level 2 — LED control + games (XL, exploratory):**
Interactive games via BLE LED control: tic tac toe on the wall, incremental hold lighting (add one hold each round), circuit creation. **Requires Capacitor BLE plugin for iOS support** (Web Bluetooth API works on Chrome/Edge but NOT Safari/iOS). This is the main reason to do Capacitor wrap before Kilter Level 2.

**Open-source references:**
- [BoardLib](https://github.com/lemeryfertitta/BoardLib) — Python, Aurora board API utilities, SQLite DB sync
- [Boardsesh](https://github.com/marcodejongh/boardsesh) — Apache license, unified multi-board app with queue management and Party Mode
- [kilterboard.app](https://tim.wants.coffee/posts/kilterboard-app/) — Web Bluetooth reverse engineering blog post
- [fake_kilter_board](https://github.com/1-max-1/fake_kilter_board) — BLE protocol documentation
- [Grip Connect](https://stevie-ray.github.io/hangtime-grip-connect/devices/kilterboard) — DB schema and placement format docs

**Risk:** Kilter launched a new standalone app (kilterboard.io) separate from the old Aurora app — API stability uncertain.

---

## Future — Phase 3.5: LLM Coach

Claude Sonnet as conversational layer over the deterministic engine.
Design spec: `docs/coach/design.md`

- Dynamic system prompt injecting user_state + current plan + recent logs
- POST /chat endpoint
- Use cases: conversational onboarding, pre-session coaching, post-session analysis
- The LLM suggests and converses — it does NOT modify the plan directly

**Dependent items:** B89 (weekly report narrative), B11 (configurable test protocols), B29a (dedicated test exercises), science explainers, nutrition hints.

### R149 — Weakness→resolver hints

**Priority:** P3.5 | **Status:** Open | **Type:** A (feature) | **Effort:** S

Pass user weaknesses as soft preferences to `score_exercise()` in the resolver. Example: `weak_on_slopers` → boost exercises with `grip: open_hand`. Depends on R148 (centralized weakness mapping).

---

## Future — Load calculation v2

> Origin: D151 load coherence audit (2026-03-23)

| # | Area | Detail |
|---|------|--------|
| 1 | Outdoor user-relative scaling | Use `grade / user_max` instead of absolute French grades |
| 2 | Other activities load map | `activity_load_map` with fixed AU values per type |
| 3 | Engine load normalization | Replace ×1.5 magic number with proper formula |
| 4 | Free session non-linear scaling | Exponential curve above 90% of max |
| 5 | Unified AU scale validation | Validate with beta tester data |

Depends on: D69 (ACWR) design, beta tester data.

---

## Future — Engine improvements

| ID | Title | Notes |
|----|-------|-------|
| P3 | Data-driven phase→axis mapping | Replace hardcoded `_PHASE_TEST_MAP` with `stimulated_axes` metadata on phase definitions in `macrocycle_v1.py` (KB Decision D92) |
| ARCH-3 | Generic timer from prescription | Frontend timer derives behavior from `work_seconds` + `reps` + `rest_*` fields |
| — | Override intensity cap warning | Warn when user overrides above phase intensity cap |
| — | P1 ranking in resolver | Recency, intensity, fatigue-based exercise prioritization |
| — | Advanced adaptivity | Readiness score, overreach detection, plateau detection |
| — | Test results → exercise calibration | Use ALL test results to calibrate difficulty and prescription |
| B127 | Pre-test adjacency rule | Planner excludes finger work day before finger test sessions |
| R161 | Performance: JSON catalog caching | `@lru_cache` on `json_loader.py`, optimize `pick_best_exercise_p0()` (renumbered from R148 — collided with implemented weakness-mapping R148) |
| R162 | Frontend performance | Code splitting, `React.memo` on hot-path components (renumbered from R149 — collided with weakness→resolver-hints R149) |

---

## Future — Content & UX

### Educational content (methodology explanations)

Two-layer system: reference doc (`docs/training_methodology_explained.md`) + condensed UI cards in Plan page.
Content: 5 phases, DUP vs linear, feedback loop, deload science, exercise ordering.

### Outdoor redesign

Guided outdoor session mode, load calculation, ripple effect, done tracking, history/stats UI, spots in onboarding.
Consolidates: B68, B69, B70, B72, B73.

### Trip Management (post-onboarding CRUD)

**Status:** Open | **Effort:** M | **Priority:** P3

Full trip lifecycle outside onboarding: add, edit, delete planned trips from Settings.
When a trip is added/modified:
- Trip days auto-marked as outdoor in affected week plans
- Pre-trip deload (3-5 days before, no hard/max sessions) via existing `compute_pretrip_dates()`
- Recovery day after return
- Affected week plans auto-regenerated

Backend: CRUD endpoints for `user_state.trips` + trigger plan regeneration on change.
Frontend: Settings → "Planned Trips" section (list + add/edit/delete). Week view shows trip days with visual badge (read-only).
Workaround until implemented: use weekly overrides to manually mark days as outdoor/rest.

Related: Outdoor redesign (B68-B73), `compute_pretrip_dates()` in planner_v2.

### Social Session (fun bouldering with friends)

**Status:** Open | **Effort:** M
Recreational session: game catalog, purpose selector, timer, social_modifier=0.5 load. Available as a free session mode. Origin: real session 2026-03-14.

### Technique Drills in Free Session

**Status:** Open | **Effort:** S-M
Add technique drill selection as a free session activity type. User picks from the drill catalog (D76) and runs drills as a standalone free session or add-on. Depends on D76 (drill catalog population) being complete.
Related: D73 (technique drill % allocation), D76 (drill catalog).

### A-B20 — Video/GIF reference for movement patterns

**Priority:** P3 | **Status:** Open | **Type:** C (content) | **Effort:** L

Short clips for technique drills and complex exercises. Priority: flagging, heel hooks, drop knees, dynos. Boulder is more visual than lead — video reference is a differentiator.

### Injury-Specific Rehab/Prehab

Rehab exercise catalog + injury→exercise mapping. Medical disclaimer required. Best candidate for LLM Coach layer (Phase 3.5). Origin: Christie feedback 2026-03-21.

---

## Future — Evolution (Phase 4+)

### A-B16 — Board workout generator

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** L

Structured board workout mode: input board type + angle + goal → output grade range, problem count, rest times, timer, RPE per problem.

### A-B17 — Pyramid/circuit builder for board

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Pre-built formats: grade pyramid, 4x4, density sets. User can save custom circuits.

### A-B18 — Competition prep mode

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** L

Flash/onsight training, time pressure, style variety, comp-specific periodization.

### A-B19 — Indoor grade calibration

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Self-report gym grading (soft/accurate/hard) or anchor to board grades. Multiplier on grade-based calculations.

- UI-25 — Test Maxes & Loads panel (Plan tab)
- Multi-goal support (boulder, all-round, outdoor_season)
- Annual report
- Multi-macrocycle periodization
- Notifications/reminders
- Gym preferences per day
- Crowdsourced gym DB

### A-B21 — Board API integration (v2+)

When Kilter/Tension/Moon open public APIs: sync sends, problem recommendation, auto-log. Future/v2+.

### A-B22 — Style finder — strength profile analysis (v2+)

Analyze boulder style preferences (crimpy, dynamic, slopey). Best candidate for LLM Coach layer. Future/v2+.

### A-B23 — Advanced finger strength periodization (v2+)

Lattice-style stimulus cycling: max hang → repeaters → contact strength → board. Refined DUP. Future/v2+.

### A-B24 — Boulder-specific injury prevention (v2+)

Higher pulley injury rate, shoulder impingement from steep terrain, fall injuries. Adapted prehab emphasis. Combine with injury tracking (Phase 3.5/4). Future/v2+.

---

## Backlog / exploration

### Mega Brief v1 — Deferred Decisions (v2+)

> Full specifications in `docs/claude_code_mega_brief_v1.md`. Grouped by theme.

**Effort Level / Intensity System (mega brief Session 5)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D34 | EL (Effort Level) as primary intensity metric | L | New field on every prescription, resolver + feedback changes. Current very_easy→very_hard feedback sufficient for launch. |
| D52 | EL prescription table by experience level | M | Depends on D34. Intensity ranges per beginner/intermediate/advanced. |
| D14 | López load monitoring (EL trend tracking) | M | Depends on D34. Autoregulation: reported_el vs target_el trend → load adjustment. |

**Periodization & Load Management (mega brief Session 9)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D19 | Simplified linear periodization for beginners | M | Longer base, no MaxHangs, more technique. Also subsumes D44 (ARC ≥6wk for beginners). |
| D20 | Overreach + taper before Performance phase | M | +10-15% volume overreach → 40-60% taper. Advanced periodization. |
| D44 | ARC ≥6 weeks in Base phase | S | Currently base=4wk/floor=2wk. Best handled via D19 (beginner path gets ≥6wk base). |
| D45 | ARC <25% MVC formal enforcement | S | Currently via process cues only. Formal resolver load cap. |
| D69 | ACWR-based load monitoring | L | Needs 4+ weeks accumulated data. Overlaps Load Model v2 section. |
| D70 | Overtraining detection heuristics | M | 5-flag system. **⚠️ KB: Ch. 12 adds central fatigue timeline — nerve cell 7× slower recovery than muscle (Bompa 1983). If "off" after several rest days → 2-10 more days needed.** |
| D71 | <10% weekly volume increase cap | S | Guard on planner output. Needs historical volume baseline. |
| D15 | Progressive ARC duration | XS | Confirmed by D44 + D45. ARC duration increases progressively within Base phase. Covered by current implementation (4wk base with floor=2wk). |

**Warm-Up & Recovery (mega brief Sessions 4, 7)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D33 | Dedicated `generate_warmup()` function | M | 5-phase protocol generator. **⚠️ KB: Ch. 6 has warm-up exercises + CUE-02 (no forearm flexor stretch pre-performance). See `_archive/docs/horst_integration_audit.md` §5-§6.** |
| D36 | PAP (Post-Activation Potentiation) | S | Advanced users only (3+ years, pulling ≥60). Niche. |
| D74 | `silent_feet` auto-inject in warmup template | XS | Drill exists, not auto-injected in warmup. |
| D53 | Active recovery progression (3-step) | S | References EL system (D34). **KB: Ch. 12 confirms active rest +35% lactate clearance (Watts 2000).** |

**Session Balance & Ratios (mega brief Session 8)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D51 | Climbing vs conditioning ratio by level | M | 70/30 → 60/40 → 50/50. Currently approximated by template weights. Formal enforcement = resolver change. |
| D59 | Hypertonic/inhibited muscle reference table | S | Internal resolver pairing logic. Exercises already exist. |
| D73 | Technique drill % allocation by level | M | Beginners ≥30% drill time. Resolver change. |

**Endurance & Hangboard (mega brief Sessions 6, 7)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D47 | Varied-intensity intervals (replace 4×4) | M | Consuegra Ch.8. Add as option first, 4×4 is industry standard. |
| D49 | Don't combine MaxHangs + IntHangs in same mesocycle | M | López-Rivera 2018. Planner change (high-risk). Current system tends to pick one naturally. |

**Coaching & UX (mega brief Session 10)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D29 | Post-climb mental reflection questions | S | 5 rotating questions, free text, optional. Good UX differentiator. |
| D41 | Campus board auto-stop rules | S | RPE check after campus sets → stop + substitute. Safety layer on top of B159a. |
| D77 | SDT principles in all copy | S | Audit + rewrite all user-facing strings. Partially followed already. |
| D79 | "Train better, not more" personality | S | Messaging guidelines. Already embodied in current copy. |
| D65 | Sleep education tips | S | **KB: Ch. 12 §5.5 (6-7h min, 8-10h after hard training) + Ch. 11 hydration data.** |
| D66 | Nutrition messaging at phase transitions | S | **KB: Ch. 11 has macro ratios by climbing style (65:15:20 vs 55:15:30), GI tables, 3-step refueling protocol.** |
| D67 | Collagen + vitamin C educational mention | XS | **KB: Ch. 11 also covers creatine (2-5g OK, loading counterproductive) + caffeine periodization.** |

**Exercise Catalog (mega brief Sessions 2, 3)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D10 | Overcoming isometric pull exercise | S | Requires pin/strap equipment not in vocabulary. Tyler Nelson protocol. |
| D37 | Core activation drills from Matros (8 exercises) | M | Tic tac toe, diagonal, freeze wall, etc. Catalog enrichment. |
| D50 | Three named repeater protocols (López/Anderson/Hörst) | M | Level-based selection logic in resolver. |
| D55 | Exercise safety blacklist formal guard | S | Validate no blacklisted exercises in catalog (CI test or resolver check). De facto safe today. |
| D58 | YTW raises exercise (missing from postural set) | XS | 4/5 done, only YTW missing. **⚠️ KB: Ch. 6 has T exercise (EX-SCAP-01) and Y exercise (EX-SCAP-02) with full protocols + 38 total exercises. See `horst_ch6_mobility_synthesis.md` §8.** |
| D72 | `grip_type` field on hangboard exercises | M | Structural schema change + full_crimp validation block. |

**Test Protocols v2 (mega brief Session 1b deferred)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D87b | PE diagnostic test (repeaters 60% to failure) | M | New test protocol for power endurance baseline. |
| D89 | Critical Force test (simplified, 2-point) | M | `critical_force_test` orphan exists in catalog. |
| D91 | `test_pe_repeaters_60` + `baselines.power_endurance` | S | Depends on D87b. |

### Other backlog items

| Theme | Detail | Origin |
|-------|--------|--------|
| R150 | Integration test full-pipeline (assessment → closed-loop) | audit 2026-03-21, confirmed by D164 Agent 10 |
| R151 | Type hints (`TypedDict`/`dataclass`), eliminate `any`, date utils | audit 2026-03-21 |
| R152 | Periodic full codebase audit con Agent Teams | audit 2026-03-21 |
| R160 | Audio util dedup: beep/countdownTick/transitionBeep duplicated in CircuitTimer and Tabata — extract to single shared module in lib/ | B160 audit 2026-03-26 |
| — | Dynamic background imagery (Midjourney, phase-aware) | roadmap discussion |
| — | Technique drills from book (scan + catalog) | roadmap discussion |

### Bodyweight exercises — load and band progression (v2+)

Exercises like dip, push-up, pull-up currently use `load_model: bodyweight_only`.
When feedback is "too easy", the engine should suggest adding external load (weight belt + disc).
When feedback is "hard" or "failed", it should suggest resistance band assistance.

Implementation approach:
- Add two optional boolean flags to the exercise catalog schema: `supports_load_progression` and `supports_band_assistance`
- Extend `closed_loop_v1.py` / `progression_v1.py` to read these flags and adjust suggestions accordingly
- Same pattern as existing external_load progression — no new concepts

**Scope:** catalog schema change + closed-loop extension. Generic solution (not dip-specific).
**Depends on:** nothing. Natural fit alongside LLM Coach closed-loop work (Phase 3.5).
**Origin:** beta feedback (Daniele, 2026-03-31)
**Audited:** D249 (2026-06-26) — `docs/audit/D249_isometric_progression.md`. Confirmed at code level: `apply_feedback` has no `bodyweight_only` branch (no-op), and this backlog item covers **external-load** bodyweight exercises only. **Time-based isometrics (Side Plank: `work_seconds`/sets/lever/variant) are UNCOVERED by this item** — they need a separate A-brief (recommended lever: increment `work_seconds`, streak-triggered, capped, future-only).

### Superseded Decisions

| ID | Superseded by | Reason |
|----|---------------|--------|
| D16 | → D47 | Replace 4×4 entirely, not tweak |
| D18 | → D33 | Absorbed into full warm-up protocol |
| D28 | → D75 | Upgraded to structured route preview |

---

## v2+ Deferred Decisions (Decision Consolidation)

> Origin: Decision consolidation cross-check (D-ROADMAP-XCHECK, 2026-04-05)
> Source docs: `decision_consolidation_D01_D83.md` + `claude_code_mega_brief_v1.md`
> Intentionally excluded: D25 (microcycle types), D27 (reverse periodization), D40 (VBT), D46 (BFR) — too niche for target audience.

### Assessment Expansion

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D03/R-01 | Flexibility axis (6th assessment dimension) | L | Requires radar UI redesign, domain weight rebalancing. Real gap for many climbers. |
| D08/R-02 | Test bank concept (optional tests beyond defaults) | M | Natural extension of current test framework. Low priority. |
| D13 | Open hand grip strength test | S | Tyler Nelson protocol. Depends on D72 (grip_type field). |
| R-03 | Technique assessment improvement | M | Current technique axis is weakest (onsight/redpoint gap + self-eval only). May need LLM Coach for video analysis → could slip to v3. |

### Periodization

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D22 | Competition taper protocol | S | Deload variant with competition-specific timing. Niche but differentiating for competitive climbers. |
| D23 | Seasonal multi-macrocycle planning | L | Already listed in "Future" section as "Multi-macrocycle periodization" — this is the formal decision ID. |
| D24 | ATR as alternative macrocycle model | L | Accumulation-Transmutation-Realization. Practically a second engine. **Recommend v3.** |

### Female-Specific

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D82 | Menstrual cycle tracking with light algorithm | M | **Upgraded from original "no algorithmic rules" scope.** v2 scope: optional cycle input (last period date + avg duration), light algorithmic adjustment on planner (follicular → favor intensity, luteal → favor volume/recovery), educational tips per phase. LLM Coach layer: expert mode for personalized cycle-aware coaching. Opt-in, privacy-first. Positive beta feedback received. Differentiates from all climbing training competitors. |

### Conditioning & Mobility

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D61 | VO2 max benchmark + optional HIIT sessions | S | Useful for endurance/multipitch focus. Supplementary session, not core. Low priority. |
| D62 | Separate mobility into ROM vs postural categories | S | Catalog refinement. Improves prescription accuracy. Not user-visible. |
| D63 | PNF stretching protocols | S | Linked to D62. Add PNF as method once ROM/postural distinction exists. Can be bundled with D62. |

---

## v3 — LLM Coach & Advanced Assessment

> These decisions require the LLM Coach layer (Phase 3.5) or specialized hardware.

| ID | Title | Category | Effort | Notes |
|----|-------|----------|--------|-------|
| D04/R-04 | Mental/tactical assessment via AI conversation | Assessment | L | Perfect LLM Coach use case. Qualitative assessment through dialogue. |
| D05/R-05 | Contact strength / RFD axis | Assessment | L | Requires force plate or similar hardware. Linked to D42. |
| D06/R-06 | Critical Force test (full protocol) | Assessment | M | D89 (v2) is the simplified 2-point version. D06 is the complete protocol. |
| D31 | Route preview coaching | Coaching | M | AI-guided route reading. Potential photo input. High differentiation. |
| D32 | Fear assessment protocol | Coaching | M | Sensitive topic, needs LLM Coach for nuance. Very differentiating if done well. |
| D42 | Levernier & Laffaye one-arm hang for RFD | Exercise DB | S | Depends on D05 (RFD axis). Specific test protocol. |

---

## Post-launch — Christie feedback (2026-03-28)

| ID | Title | Priority | Type | Effort | Status | Notes |
|----|-------|----------|------|--------|--------|-------|
| — | **Free session expansion** — standalone non-structured activities | P3.5 | A | M | Open | Standalone hangboard cycle, mobility routine, core circuit. "Tap and go" — no resolver, no structured prescription. Complements Session Builder. Core/mobility partially exist in free session surfaces. |
| — | **Quick-add equipment guard**: `suggest_sessions` and `apply_day_add` don't validate `required_equipment` — user can quick-add `limit_boulder_gym` without gym_boulder | P3 | B | S | Open | Touches replanner_v1.py — needs analysis brief (STOP gate). Origin: B185 verification. |
| — | **Warmup/cooldown P0 rotation**: convert hardcoded warmup/cooldown blocks to P0 selection for exercise variety | P3 | A | M | Open | Low priority — warmup sequences are standard. 11 hardcoded warmup blocks (warmup_climbing ×4, warmup_strength ×3, general_warmup ×2, cooldown_stretch ×2). Origin: B185 catalog audit. |
| — | **Quick-add filter/search** — session list discoverability | P4 | A | S | Open | Search/filter by goal or body part in quick-add list. Data available via `intent.primary_goal`. Low priority — Session Builder likely subsumes most of this. |
| — | **Session phase coloring** — warmup/cooldown dimmed | P4 | A (frontend) | XS | Parked | Dim warmup/cooldown, vivid main work. Data from `module_role` + `exercise_ordering.py`. Pure CSS, zero backend. |
| — | **Exercise request mailto banner** — "Missing an exercise? Email us" | P4 | A (frontend) | XS | Open | Simple mailto link/banner in Free Session page and exercise-related UI. Encourages users to request new exercises. No backend needed. Origin: Christie idea (2026-04-08). |
| A-FREE-01 | **Free Tier Logging** — logging as free tier, training plan as paid upsell | P3 | A | L | Open | All logging (outdoor, hangboard, campus, any activity) is free. Paywall on: training plan, guided sessions, resolver, progression, radar assessment, closed-loop adaptation. Requires: decouple logging from plan, define paywall boundary in frontend + API, extend outdoor session framework for generic activity types. Connects to D168 (outdoor/week plan unification). Design brief (D-type) needed first. |
| A-FREE-02 | **Flexible Activity Logger** — log any climbing/training activity without going through the weekly plan | P3 | A | M | Open | Intuitive UX to log what you actually did: open app → tap "Log activity" → pick type (hangboard, boulder session, campus, stretching, weights, outdoor, etc.) → enter details → done. No plan dependency. Solves Christie's pain point (can't easily log non-plan activities). Connects to Session Builder (custom sessions) and Free Session Expansion. Design brief (D-type) needed first. |
| A219 | **Partner Training Mode** — ⤳ **superseded da D244**. Lo spec è ora `docs/design/D244-PARTNER-MODE_audit.md` (modifier system estendibile). Implementazione scorporata nei 5 brief sotto. | P3 | A | M | Superseded | Vedi D244 §6. Origin: Daniele (2026-05-07/21). Marketing angle: differenziatore vs competitor solo-focused. |
| A-MODIFIER-CORE | **Modifier system core** — astrazione `session.modifiers: []` + reversibilità snapshot; estende il replanner per applicare/rimuovere modifier. Riusa `equipment_override` (A210) e `boulder_fallback`. | P3 | A | S-M | Open | **HIGH RISK** (`replanner_v1.py`) → mandatory analysis + STOP gate. NON tocca `resolve_session.py` per L1. Spec: D244 §3/§6. |
| A-SURFACE-PREF | **Surface preference modifier** — generalizza A210 ("Boulder only") aggiungendo `prefer_routes` + toggle bi-direzionale. EFFIMERO (no persistenza). | P3 | A | XS-S | Open | Quasi indipendente (riusa A210). Frontend → branch + Vercel preview. Spec: D244 §3.3/§5. |
| A-PARTNER-MODE | **Partner mode L1** — swap sessione partner-friendly per fase (`boulder_fallback`/helper-text), preview modal, banner/badge/undo, persistenza + immutabilità. | P3 | A | M | Open | Dipende da A-MODIFIER-CORE. Frontend → branch + preview. Spec: D244 §3.2/§5. |
| B-MODIFIER-SCHEMA | **`session.modifiers: []` convenzione** — campo additivo, **nessuna migration** (user_state schemaless). | P3 | B | XS | Open | Quasi no-op; assorbibile in A-MODIFIER-CORE. Spec: D244 F3/§6. |
| C-PARTNER-CATALOG | **`partner_compatibility` su 225 esercizi** (parallel/rotation/solo_only). | P3 | C | S | Open | **OPZIONALE/post-MVP** — non serve per L1 (serve solo per L2/badge). Spec: D244 §4.1. |
| — | **Audit visuale `/today`** — 11 issue identificate (2 P0 + 5 P1 + 4 P2). Backlog informale, non-brief. | P3 | A (design) | — | Parked | File: `docs/audit/audit-today-2026-05-12.md`. Solo P1 #5 (touch target dismiss × da 24→44px) fixato immediatamente. Review post-launch + 30gg (~2026-05-16) → convertire in brief A-design con dati reali su retention. Origin: skill `example-skills:frontend-design` validation (2026-05-12). |

---

## Completed phases (reference only)

Full details in `docs/ROADMAP_v2.md`.

| Phase | Completed | Highlights |
|-------|-----------|------------|
| 0: Catalog | 2026-02 | 102 exercises, 29 sessions, vocabulary |
| 1: Macrocycle engine | 2026-02 | assessment_v1, macrocycle_v1, planner_v2 |
| 1.5: Post-E2E fixes | 2026-02 | 14 findings resolved |
| 1.75: Session enrichment | 2026-02 | Load scores, test scheduling, ripple fix |
| 2: Tracking + outdoor | 2026-03 | Outdoor logging, reports, quotes |
| 2.5: Catalog audit | 2026-02 | 10 enrichment patches, grade_ref, working loads |
| 3: UI (Next.js PWA) | 2026-02 | 14 routers, mobile-first dark PWA |
| 3.1-3.2: Bug fixes + polish | 2026-02 | 22+ bugs, adaptive replanning, quick-add |
| 4a: Multi-user + deploy | 2026-02 | UUID multi-user, Railway/Vercel |
| 4b: Guided session + beta | 2026-03 | Step-by-step timer, settings editors, dirty-state |
