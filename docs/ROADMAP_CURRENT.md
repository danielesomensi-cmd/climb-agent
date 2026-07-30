# climb-agent — Active Roadmap

> Last updated: 2026-07-20 (A239 — milestone system. Piano gamification: A-GAMIFY-00 approvato → A234 daily tips, A235 phase progress, A236 heatmap, A239 milestones. Restano A-GAMIFY-04 (opzionale) e A-DAILYTIP-V2.)
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Open

**~~COACH-ROUTER-IT~~** ✅ **Chiuso da [[B310]]** (2026-07-30, backend-only). **La diagnosi di [[D265]] era imprecisa e va letta rettificata:** il router non era "monolingua inglese" — `_index.md` aveva già keyword italiane quasi ovunque. La causa reale, verificata token per token: **match esatto sul token con lemmi nell'indice contro forme flesse nella query** (`dormire` vs `dormo`, `ripresa` vs `riprendo`, `drill` vs `drills` — il plurale rompeva anche l'inglese, `ciclo mestruale` vs il semplice `ciclo`), più tre lacune di copertura vere: `dieta`/`low-carb`, `dimagrire`/`peso`, `influenza`, e **`warm-up` non indicizzato in nessuna lingua** pur avendo il contenuto D33 + CUE-02 nel KB. **Fix:** keyword con `*` finale = radice, match per prefisso (min 4 char) — tre righe in `routing.py`, la morfologia resta nei dati dell'indice; più le keyword mancanti. **Fallback da 7/28 a 1/28**, e l'ultimo residuo («Ho 30 minuti oggi») atterra correttamente su `01_periodization` proprio via fallback. «ciclo» sta su entrambe le righe (mestruale + macrociclo): in italiano è ambiguo, si caricano i due sensi invece di perderne uno. Test: 15 casi nuovi in `test_coach_routing.py` (le 7 domande che cadevano + guardia anti-regressione sul macrociclo + prefisso-non-infisso: `dorm*` prende «dormo», non «addormentato»). **Il punteggio 43/56 non è stato ricalcolato** — le risposte precedono il fix; il re-run è il prerequisito dello Step 10.

**~~KB-ENGINE-BASE-FLOOR~~** ✅ **Chiuso da [[C263]]** (2026-07-30, backend-only; decisione di Daniele: **allineare il KB alle 4 settimane**, non alzare il floor del motore). **Fatto decisivo emerso durante il fix:** D44 (Base ≥6 wk) era **già registrata come deferred** nel proprio registro (`docs/research_kb/00_INDEX_v3.md`, Stale References Log: «❌ D44 deferred») — è il KB del coach che l'aveva promossa a *hard floor* per conto suo, fino ad affermare il falso in `05_aerobic_endurance_arc.md`: «Engine cannot generate a macrocycle with Base <6 weeks». **Allineati** `L3/01_periodization` (tabella fasi, floor reali, nota D44, risposta a «perché la mia Base è N settimane»), `L3/05_aerobic_endurance_arc` (4 punti), `L2_decision_index` (D21 **e** D44), più la risposta boulder che dava per identica la durata (2 vs 4 settimane). **La letteratura non è stata riscritta:** Mujika 2012 resta, ma citato come *punto di saturazione dell'adattamento*, con il 4 dichiarato per quello che è — un compromesso deliberato dentro il cap di 16 settimane, con le leve oneste per chi vuole più base aerobica (secondo ciclo a obiettivo endurance, o deadline più lontana). Aggiornati anche i doc di ricerca (`00_INDEX_v3`, `KB_SUPER_SUMMARY`, `decision_consolidation` T1) con lo stato reale. **Guardia:** `test_c263_kb_engine_coherence.py` estrae il numero dal KB e lo confronta con `_PHASE_FLOORS_LEAD`/`_PHASE_FLOORS_BOULDER` — se un giorno il floor del motore sale, il test fallisce finché il KB non viene aggiornato; più un test che vieta il ritorno delle 5 affermazioni stale.

**~~COACH-RESPONSE-TRUNCATION~~** ✅ **Chiuso da [[B311]]** (2026-07-30) — `MAX_TOKENS` era **1024**, fissato contro il target di design «300-800 token» che era misurato **in inglese**; l'italiano costa ~2,3 caratteri/token, quindi una risposta strutturata con tabella esauriva il budget a ~2.300 caratteri e si spegneva a metà parola (`stop_reason=max_tokens`, verificato con chiamata diagnostica). Il re-run di [[D266]] ne ha trovate **10 su 28**. Fix: cap a **2048**, sovrascrivibile con `COACH_MAX_TOKENS` senza deploy, **più un warning nei log quando `stop_reason == max_tokens`** — il difetto era invisibile perché nessuno lo segnalava. Dopo il fix: 2 casi residui, non spiegati dal cap → [[COACH-TRUNCATION-RESIDUAL]].

**~~LOAD-ACTUAL-SKIPPED~~** ✅ **Chiuso da [[B312]]** (2026-07-30, backend-only; segnalato da Daniele: «se in una sessione skippo molti esercizi il load non sarebbe da abbassare?» — sì, e non lo faceva). **Due difetti, uno dentro l'altro.** **(1) Il segnale c'era e nessuno lo leggeva:** il guided player manda già `completed: false` per ogni esercizio skippato (`feedback-items.ts:168`) e il router lo persiste in `session.actual_exercises`, ma i suoi unici consumatori erano le milestone e la UI della session-card — **mai il load**. Chiudere una sessione dopo 2 esercizi su 8 accreditava il carico pieno al report settimanale, alla heatmap mensile e (per omissione) al coach, che vedeva solo `planned_load`. **(2) Il difetto latente sotto:** `session_load_score` lo scrive `resolve_session` sul payload risolto, che il week router attacca sotto `slot["resolved"]`, mentre i due consumatori del report lo cercavano su `slot` — dove non esiste mai. Quindi da [[D151]] **ogni** sessione cadeva silenziosamente su `estimated_load_score`, il bucket grezzo dell'intensity: il fix D151 era corretto nella formula e inerte nella lettura. I test D151 lo settavano a mano sullo slot, perciò passavano. **Fix:** nuovo `backend/engine/load_score.py` come unica sorgente della formula (era inline in 3 punti) con `session_load_actual` calcolato al feedback dai flag `completed`, e `effective_session_load()` come **unico** reader per report + heatmap + coach. Denominatore = gli `exercise_instances` risolti, non gli item di feedback: così il completamento pieno atterra **esattamente** sul prescritto (gli step instruction-only non compaiono mai nel payload ma hanno `fatigue_cost`), e il carico si sottrae **solo** su un `completed: false` esplicito — un esercizio non riportato conta come fatto. Le mani di un esercizio unilaterale contano una volta. `session_load_score` non viene mai sovrascritto: `load_ratio` ha bisogno di un denominatore intatto. Lo zero è una risposta reale solo per l'*actual* (skippato tutto = 0); un prescritto a zero significa «il resolver non ha prodotto esercizi» e continua a cadere su `estimated_load_score`, semantica [[D151]] preservata. `mark_planned` (undo) cancella anche il nuovo campo, come gli altri feedback-derived ([[B192]]). **Non toccato di proposito:** il closed-loop resta binario per sessione — le flag `hard`/`finger` guidano il gap di 48h sulle dita e sovrastimare lì è conservativo (l'utente riposa di più, non di meno), declassarle su completamento parziale rischierebbe due sessioni dita ravvicinate. **Verifica:** 26 test nuovi (`test_b312_load_actual.py` + `test_b312_feedback_endpoint.py`, quest'ultimo sull'endpoint reale con TestClient, incluso il round-trip nella cache `week_plans` che legge `GET /api/week`); su `heavy_conditioning_gym` (16 esercizi risolti, prescritto 78) skippare i due pesanti dà **60**, e il calo è monotòno esercizio per esercizio. Suite completa: 2960 passed.

**~~BOULDER-ONLY-NOT-IN-GUIDED~~** ✅ **Chiuso da [[B313]]** (2026-07-30; segnalato da Daniele: «clicco "trasforma in boulder", la preview è giusta, poi lancio la guided ed è tornata lead — provato varie volte»). **Causa:** [[A210]] teneva l'override in `boulderOverride`, uno `useState` **interno alla session-card**, letto solo da `effectiveResolved` per il rendering. `handleStartGuided` è una funzione **module-level**: non lo riceve, costruisce lo stato del player da `session.resolved` (il piano lead) e lo scrive in localStorage, da cui la pagina guidata legge. Preview e player leggevano **due sorgenti diverse** e solo una conosceva l'override. Corollario dello stesso difetto: essendo React state puro, l'override **evaporava a ogni rimount** della card (refetch di /today, navigazione, ritorno dalla PWA in background) senza alcun avviso — da qui il «varie volte». **Fix (una sola sorgente):** nuovo `POST /api/session/surface-override` che scrive la sessione adattata **sullo slot** (`surface_override` + `surface_override_from` + `_user_edited`, quest'ultimo già il meccanismo B153b che tiene `_auto_resolve` lontano dallo slot). Il player non è cambiato di una riga: legge `session.resolved`, che ora **è** il boulder. Sparisce anche la biforcazione client-side `if (boulderFallbackId) … else …`: quale sessione usare la decide il server. **Scoperta durante l'implementazione — la prima versione era sbagliata:** applicavo l'`equipment_override` solo al ramo "nessun fallback dichiarato", perché lo swap sembrava garantire il boulder per costruzione. Non lo garantisce: in una palestra con **entrambe** le pareti, `boulder_circuit_gym` sceglie `route_on_the_minute` (esercizio da corda) per il blocco primario — l'utente chiedeva boulder e otteneva vie sotto un altro nome. Ora la corda viene tolta dall'attrezzatura **sempre**; il `boulder_fallback` decide solo *quale* sessione, non *come* risolverla. **Tre guardie**, perché la promessa fatta all'utente va verificata e non assunta: parete boulder presente in loco (altrimenti il resolver ripiega in silenzio su `hangboard_moving_hangs` e ti dà una sessione valida che non è bouldering), blocco primario sopravvissuto, nessun esercizio residuo che richieda `gym_routes` (gli esercizi pinnati bypassano i filtri P0). Tutte e tre → 422 onesto invece di una card boulder solo di nome. Realineati anche `intensity`/`tags`/`estimated_load_score` allo swap: lasciare le flag `hard`/`finger` della sessione a corda avrebbe guidato il gap di 48h sulle dita sulla sessione sbagliata. Undo = ri-risoluzione della sessione pianificata attraverso lo **stesso** codepath, quindi la risposta è renderizzabile subito e non serve alcuno snapshot. **26 test** (14 nuovi in `test_b313_surface_override.py`, inclusi immutabilità del passato → 409, doppio apply che non perde il session_id pianificato, `_auto_resolve` che non riscrive lo slot, feedback senza warning stale e load [[B312]] misurato sulla sessione adattata). Suite: 2974 passed. **Mergiato senza preview Vercel su richiesta esplicita di Daniele** (test dal vivo in palestra); build di produzione, typecheck e lint verificati in locale prima del merge.

**COACH-TRUNCATION-RESIDUAL — 2 risposte ancora tagliate senza raggiungere il cap (da [[D266]], 2026-07-30)** 🟡 — Q-16 (taper, 1.962 char) e Q-19 (30 minuti, 715 char) si interrompono a metà parola, ma **nessun warning `max_tokens` compare nei log**, quindi il cap a 2048 non è stato raggiunto. Ipotesi da verificare: il modello emette un blocco `tool_use` (weather) dopo il testo e `_final_text()` restituisce solo la parte testuale, facendola sembrare tagliata. Da chiudere registrando `stop_reason` nel raw del runner — a quel punto la causa è visibile in un solo run.

**COACH-FOURTH-WALL — Il coach nomina Daniele parlando a un altro utente (da [[D266]], 2026-07-30)** 🟠 — in Q-08 la risposta dice: «sono materiali fisici che **Daniele** possiede in cartaceo, e l'estrazione è ancora in corso». Il KB annota lo stato di acquisizione delle fonti e a chi appartengono (`00_INDEX_v3`, risk register), e il modello l'ha riferito a un utente che non è Daniele. Su un'app multi-utente a pagamento è un difetto di professionalità: l'utente non deve sapere chi possiede quali libri né vedere il processo interno. Fix probabile in L1 (regola: mai nominare persone del team né lo stato interno delle fonti; se una fonte manca, dire solo «non è ancora nel motore»).

**COACH-PE-4X4-DRIFT — Q-06 perde il rifiuto del 4×4 (da [[D266]], 2026-07-30)** 🟡 minore — il primo run rifiutava esplicitamente il 4×4 in favore degli intervalli a intensità variata (D47); il re-run non lo menziona più, pur avendo `04_power_endurance` in contesto. Non è retrieval, è deriva del modello: se si ripete al prossimo run, vale un rinforzo nel file L3 (spostare D47 in cima alla sezione, o renderlo una riga «cosa NON prescrivere»).

**A-ADHOC-BACKDATE — loggare a posteriori una sessione composta dal coach (da [[B309]], 2026-07-29)** 🟡 — il CTA "Add to today & run" usa sempre `localToday()`: se hai fatto l'allenamento ieri e chiedi al coach di ricrearlo per loggarlo (caso reale di Daniele, 29/07), non c'è modo di appoggiarlo al giorno giusto. Serve un selettore di data sulla card (oggi / ieri) e una decisione esplicita su quanto indietro si può andare — l'inserimento su un giorno passato non viola l'immutabilità (è un'azione utente esplicita, come la matita), ma è un cambio di comportamento da approvare.

**PLANNER-ACCESSORY-GAP — 16 esercizi che il planner non mette mai nei piani (da [[D262]], 2026-07-29)** 🟡 — non sono morti (il coach li compone), ma **nessun blocco di sessione o template li può selezionare**, perché la combinazione ruolo+pattern che hanno non è filtrata da nessuna parte. Due famiglie: **(a) accessori di tirata** — `chinup`, `band_assisted_pullup`, `frenchies`, `uneven_grip_pullup`, `supinated_inverted_row`: i blocchi che filtrano `pull_vertical`/`pull_horizontal` chiedono tutti `role=["main"]`, quindi gli accessori non entrano mai; **(b) pattern senza casa** — `hip_isolation` (clamshell, side_lying_hip_abduction, standing_hip_adduction_band), `compression` (hip_flexor_strengthening, seated_leg_raise_hip_flexor), `anti_lateral_flexion` (copenhagen_adductor_plank), `anti_extension` (front_lever_tuck), `tendon_glide` (active_finger_curls), `grip_transition` (grip_transitions_half_to_open), `isometric_hang` accessorio (lp_repeater_lifts, one_arm_hang_assisted). **Non è un bug da chiudere al volo**: aggiungerli ai template è una decisione di *training design* (quali sessioni devono avere un blocco accessorio, con che priorità e budget di tempo), non una correzione di dato. Da scopare con Daniele.

**BASE-PULLING-INTENSITY-CAP — La forza massima di tirata non può entrare in `base` (da [[A258]], 2026-07-29)** 🟡 — il KB indicava `base` come collocazione classica della forza massima multiarticolare (Consuegra §8.8), ma `pulling_strength_gym` è `intensity: high` e `base` ha `PHASE_INTENSITY_CAP = medium`: il planner la scarta prima di considerarla. In base la tirata arriva solo come **mantenimento** (blocco [[C261]]). Per dare lavoro di **sviluppo** in base servirebbe alzare il tetto d'intensità della fase o creare una variante a intensità media della sessione — decisione metodologica, non un dettaglio di pool. Da riportare al KB insieme alla domanda se la fase base debba davvero ospitare forza massima o se il tetto `medium` sia corretto.

**B-OUTDOOR-RELATIVE-LOAD — Load outdoor relativo al max grade (proposto, da B302, 2026-07-23)** 🟡 design. Oggi `compute_outdoor_load_score` (outdoor_log) pesa i tiri con `_GRADE_WEIGHT` **assoluto** per grado: un 6a pesa uguale per un climber 8a e per uno 6a. Intuizione di Daniele (corretta): il load dovrebbe essere **relativo all'abilità** — un 6a per un 8a-climber è recupero (load basso), per un 6a-climber è al limite (load alto). Serve ancorare il peso alla distanza dal max/assessment (es. `grade_gap(route, user_max)` → curva di sforzo). Tocca la formula D151 + probabilmente il session_load_score indoor per coerenza. **Da scopare con Daniele** (curva, floor/cap, retro-compatibilità dei report storici). Non urgente.

**A-COACH-KB-V1 (in progress, Phase B, Session 7a of 7b complete)**
- Phase A audit: `docs/research_kb/coach_kb_v1_audit.md` (commit `75bd4f5`)
- Phase B output: `backend/coach/knowledge/` (Session 1: commit `1971da1`; Session 2: commit `1415b2f`; Session 3: commit `7a98d05`; Session 4: commit `e682efb`; Session 5: commit `f87cdd0`; Session 6: commit `bc3db55`; Session 7a: TBD)
- Steps 1-4 ✅ (scaffold 24 file, L0 11 safety rules, L1 voice, L2 35 decision index)
- Step 5 ✅: Batch A ✅ (files 01-05), Batch B ✅ (files 06-09), Batch C ✅ (files 10-12), Batch D ✅ (files 13-15: tapering/redpoint, female/age/youth, goal-setting/motivation), **Batch E ✅** (files 16-20: assessment interpretation, readiness/overtraining, equipment fallback, lifestyle integration, return-to-training)
- **Step 6 ✅** — `docs/coach/design.md` (2865 word ≈ 3725 tok, target 3000-4000): 9 sezioni (scope, architettura multi-layer, layer spec + catalogo 20 file L3, loading strategy, firewall 14 D-ID engine-internal, citation policy + gap markers, fase A→B→next, governance, open items v1.1). Sostituisce la dangling reference a `_archive/docs/coach_knowledge_base_spec.md` (ghost file confermato D-COACH-AUDIT).
- **Step 8 ✅** — `backend/coach/routing.py` (BM25-style keyword router su `_index.md`, max 3 file, fallback `01_periodization`+`15_goal_setting_motivation`, co-load rule `10_injuries_fingers`→`02_finger_strength` se keyword finger-strength). Tests: `backend/tests/test_coach_routing.py`, 39 test passing (20 per UC + 19 ranking/fallback/cap/co-load/robustness).
- **Step 9 ✅** — scoring eseguito da Claude su richiesta di Daniele ([[D265]], 2026-07-30): **43/56 (76,8%), sotto la soglia di pass 45/56**, zero breach sulle 6 domande ⛔ hard-fail. Risultati e note per domanda in `docs/coach/regression_scoring_v1.md`. I punti persi si concentrano su due cause sistemiche → [[COACH-ROUTER-IT]] (🔴 bloccante) e [[KB-ENGINE-BASE-FLOOR]], più [[COACH-RESPONSE-TRUNCATION]].
- Step 10 ⏳ (final v1.0 lock) — **re-run eseguito ([[D266]], 2026-07-30): 46/50 sulle 25 domande valutabili (era 38/50 sulle stesse), routing 28/28, zero citazioni fuori KB, zero leak.** **Bloccato su un fatto operativo:** il credito dell'API Anthropic si è esaurito durante il run e **Q-26/Q-27/Q-28 non hanno risposta — sono tutte e tre ⛔ hard-fail**, quindi il verdetto di rilascio non è determinabile. Ricaricare i crediti e rilanciare `scripts/coach_regression_rerun.py` (le 25 già valide non vanno rifatte). Dettaglio in `docs/coach/regression_rerun_raw.md`
- Est. remaining: ~2.5h in Session 7b con Daniele (Steps 9 + 10)
- Step 7 (L4 schema + coach_rationale catalog edits) **DEFERRED to v1.1** per brief scope-change
- Risk register: see brief; key items = books not yet acquired (MacLeod/Ilgner/Mobråten/Christophersen Part 1+2/Bechtel pp.31-90/Lattice 2019 taper newsletter/Hörst redpoint chapter/Bechtel Integrated Strength/Lattice MXEdge protocol/Mujika & Padilla 2000a/b detraining primaries) → L3 files 06, 07, 10, 11, 13, 15, 16, 18, 19, 20 ship v1.0 with explicit `**v1.0 coverage gap**` markers for v1.1 refresh
- **Engine-internal D-ID firewall (D03, D04, D05, D06, D08, D13, D23, D32, D42, D61, D62, D63, D88, D90) honored across all 20 L3 files.** File 16 (assessment interpretation) explicitly firewalls D88/D90 in its v1.0-gap block: the brief mentioned them but they govern engine scheduling/protocol-selection internals, not user-facing knowledge. Verified via `grep -nE "\bD(03|04|05|06|08|13|23|32|42|61|62|63|88|90)\b"` — only hit across Batch E is the firewall block itself in file 16.
- Known token undershoot/overshoot vs §4.6 audit targets: Batch A files ~40-60% of upper-band; Batch B files 06+07 ~25%/13% under, files 08+09 spot-on; Batch C files 10+11+12 ~13%/5%/7% under; Batch D file 13 +12% over, file 14 +2% (spot-on), file 15 +25% over; **Batch E file 16 +10% over (4419 tok vs 4000 target), file 17 -4% (4334 vs 4500 target, spot-on), file 18 +23% over (4310 vs 3500 target — substitution matrix density), file 19 +19% over (4176 vs 3500 — concurrent-training pairings + central fatigue + cut-order detail), file 20 +17% over (4666 vs 4000 — three-band decision tree + D71 reset math + injury-driven differential)**. Content complete and source-anchored; deviation is content-driven, not padding. Documented for v1.1 refresh decision.

**MKT-COACH — Pubblicizzare il Coach AI (proposto, 2026-07-12)** 📣 — il Coach è live in prod, validato sul campo (B-COACH-CONTEXT-FIX) e ora plan-aware al 100%: è il feature differenziante più forte dell'app → va comunicato. Candidati: annuncio ai beta tester / utenti esistenti (email o Telegram), card/banner in-app che presenta il Coach ai non-subscriber (è subscription-gated → leva di conversione trial→paid), post social / changelog pubblico, sezione dedicata sulla landing. Da scopare con Daniele: canali, messaggio, timing. Prerequisito tecnico ✅ raggiunto: A-COACH-V1b chiuso (2026-07-12) — il demo include meteo reale allo spot, note personali e chips.

**A-COACH-V1c — Coach v1.2 (proposto, stub)** — residui da A-COACH-V1b: L4 per-exercise rationale (deferred da KB v1.0); refresh L3 su gap sources (Bechtel, MacLeod, Ilgner, Mobråten, Lattice MXEdge); streaming risposte (deferred da V1a); idee personalizzazione non scopate in V1b: stile coach configurabile (tecnico/motivazionale), milestone/PR nel contesto, riga readiness aggregata.

### Residui della remediation A245 / D254

Tutti generati durante [[A245]]. Erano finiti per errore nella tabella dello sprint
GTM (§1.75), che non c'entra: spostati qui il 2026-07-20 così la sezione Open è
la sola fonte di verità.

| ID | Titolo | Tipo | Effort | Stato | Note |
|----|--------|------|--------|-------|------|
| A-CLIMB-CLIENT-ID | **Id climb generato client-side e propagato al backend** | A | S | Open P3 | Registrato da A245 Phase B. Una climb loggata offline entra in UI con un **indice locale provvisorio**; il server assegna il suo indice reale al replay dell'outbox. Nella finestra fra replay e refetch, `DELETE /api/free-session/{id}/climb/{climb_index}` può colpire la riga sbagliata perché l'indice mostrato non è ancora quello del server. Mitigazione attuale: il delete fa rollback ottimistico su fallimento, e la finestra è breve. **Fix vero:** id client-side (UUID) generato al log, propagato nel payload e usato dal backend come chiave di identità al posto dell'indice posizionale. Tocca `free_session` router + `climb-logger.tsx`. |
| A-DELTA-EVENT-ENDPOINT | **Endpoint replanner a delta (evento singolo, non piano intero)** | A | M | Open P3 | Registrato da A245 Phase B. Oggi `POST /api/replanner/events` spedisce l'**intero** week plan e il backend lo persiste sovrascrivendo: per questo Done/Skip è escluso dall'outbox offline (riprodurre uno snapshot catturato ore prima sovrascriverebbe tutto ciò che è successo nel mezzo e potrebbe toccare sessioni passate, violando il pilastro di immutabilità). Offline oggi fallisce con messaggio esplicito. **Trigger:** aprire solo se i dati d'uso mostrano domanda reale di Done/Skip offline — non prima. Un endpoint a delta renderebbe l'evento accodabile in sicurezza e chiuderebbe anche la radice di F6. |
| B-RESOLVED-CASTS | **220 cast `as X` sul percorso dati più critico (F24)** | B | M | Open P3 | Residuo di F24 dopo A245 G-6, che ha reso onesto `ResolvedSession` (prerequisito: prima il tipo mentiva, quindi togliere i cast avrebbe solo spostato la bugia). Restano 220 `as X` in 63 file e 13 `as unknown as`, con picco in `session-card.tsx` (`resolved` è `Record<string, unknown> | null`). **Impatto:** un rename di campo lato backend compila verde e renderizza `undefined` nella schermata di allenamento. **Fix:** usare i nuovi `ResolvedSession`/`ResolvedBlock`/`ResolvedExerciseInstance` nel percorso guided/today e togliere i cast lì; il resto può restare. Ora è fattibile in sicurezza — il test che confronta i campi TS col Python del resolver fa da rete. |
| B-SESSIONCARD-DECOMP | **SessionCard resta un monolite da 1333 righe** | B | M | Open P3 | Residuo di F20 dopo A245 G-7, che ha chiuso la parte pericolosa (il walk sui blocchi duplicato *dentro lo stesso file*, con rischio di divergenza fra ordine mostrato e ordine eseguito). Restano le responsabilità mescolate: factory dei dati guidati, orchestrazione avvio + scrittura localStorage, dialog "Add Exercise" completo con fetch del catalogo, chiamate API dentro un componente di presentazione. **Fix:** estrarre `AddExerciseDialog` in un file proprio e la factory in `lib/guided-state-builder.ts` (unit-testabile). Puro spostamento di file: valore di manutenibilità, non di correttezza — da fare insieme a [[B-REFACTOR-COMPONENTS]]. |
| A-CLERK-PROVIDER-SCOPE | **Togliere ClerkProvider dal root layout (F27)** | A | M | Open P3 | Differito da A245 Phase F con misura, non a occhio. Clerk pesa ~227 KB su ogni route, ma **serve davvero** a `(main)`, `(guided)`, `onboarding`, `sign-in`, `sign-up` e alla root `page.tsx` (usa `useAuth`): le uniche pagine che ne farebbero a meno sono `/legal`, `/offline` e **`/demo`**. Quest'ultima conta — è la landing di acquisizione per il traffico Reddit/IG, quindi 227 KB in meno lì sono valore GTM reale. **Perché non fatto ora:** `src/app/page.tsx` è la root e condivide il root layout con `/demo`, quindi escludere Clerk da `/demo` richiede di spostare la root in un route group e di replicare `ClerkProvider` + `SessionScopeGuard` in un layout condiviso per tutti gli altri gruppi — una modifica strutturale all'ingresso dell'app, non "perf leggera". Da fare in un brief proprio, prima di spingere traffico. |
| B-TIMER-TICK-SCOPE | **Il tick a 1 Hz ri-renderizza tutto ExerciseTimer** | B | M | Open P3 | Metà residua di F26 (l'altra metà, la memoizzazione, è chiusa in A245 F-8). `secondsLeft` è stato del componente e pilota la macchina a stati delle fasi, quindi ogni secondo ri-renderizza le 368 righe di JSX del timer per tutta la durata dell'esercizio — costo su batteria e INP sui telefoni di fascia bassa. **Fix:** pubblicare `secondsLeft` via `useSyncExternalStore` verso un piccolo display memoizzato, lasciando l'interval e i ref di fase dove sono. **Cautela:** è il componente più critico dell'app (rompe l'allenamento in corso se sbagliato) — serve verifica su device vero, non solo test. Nota: il finding originale stimava "~1000 righe", la misura reale è 368 senza sotto-alberi pesanti. |
| B-RESOLVE-ERROR-UI | **`resolve_error` non è ancora letto dal client** | A | XS | Open P3 | A245 E-3 (B17) marca lato backend le sessioni la cui risoluzione è fallita (`resolve_error: true` in `week.py` e `replanner.py`), distinguendole da «nessun esercizio compatibile». Il client non lo legge ancora: la session card resta identica nei due casi. Manca la metà frontend — stato d'errore esplicito con retry sulla card. Registrato subito per non lasciare orfano un campo che nessuno consuma (esattamente il pattern di B8/E-4). |


**B-REFACTOR-COMPONENTS — Batch di decomposizione componenti (differito da A245 v1)** 🟡 P3, qualità/manutenzione, nessun impatto utente. I 4 finding di [[D254]] esclusi da A245 per non gonfiare la Phase G, già la più pesante: **F55** `QuickAddDialog` (776 righe, tre wizard in un dialog con 18 `useState`), **F56** serializzazione del feedback — il contratto col motore — inline nella guided page (~100 righe), **F57** prop drilling a 3 livelli (page → DayCard con 27 prop/19 callback → SessionCard), **F58** `GuidedExerciseStep` (1053 righe, 8 modalità input con flag mutuamente esclusivi). Da affrontare dopo A245, possibilmente insieme a G-6 (`SessionCard` monolite) se quel lavoro lascia fondamenta riusabili.

**B256 — Rimuovere `current_week_plan` (dedup hot state)** 🔴 high-risk, **scorporato da A221**. Ora che l'hot è `{N-1, N, future}` (post-A221), `current_week_plan` (~234 KB, byte-identico a `week_plans[this_monday()]`) è peso morto duplicato. Reindirizzare i ~10 reader backend a un helper unico `week_plans[this_monday()]` + sistemare lo stash `_prev_week_plan` (alimentato da `week_plans[N]`) + strip su prossima write. Riduzione attesa: hot Daniele 448→~250 KB. **Tocca multi-modulo** (`week.py`, `feedback.py`, `free_session.py`, `deps.py`, …) → richiede Fase 1 di analisi (mappa completa reader) + STOP prima dell'implementazione, branch + test invariante. Reader map di partenza: vedi D242 §2 + nota B256 nell'audit `docs/audit/D242_archive_weekplans.md`.

_Nessun follow-up D238 aperto. Tutti i finding del report `docs/audit/D238_test_load_calculation.md` sono chiusi: B251 (Fix 1 catalog), B252 (Fix 3 protocol_version), B253 (Fix `tests_source` legacy backfill)._

_Nessun follow-up D239 aperto. Audit conferma "no bug" — 3 possibili miglioramenti cosmetici suggeriti (vedi §10 di `docs/audit/D239_quote_render_audit.md`) sono P3 e non bloccanti._

_D240 next step **chiuso da C239** (2026-05-26): le 25 proposte KB (cue_036→cue_060) sono state mergeate nel catalog._

**D251 follow-ups residui (P2, non bloccanti)** — dall'audit `docs/audit/D251_fe_be_coherence.md` (§WARNING). W1/W3/W5/W6/W8/W9 chiusi da B272 (2026-07-08). Restano:
- **W2** — `self_eval` weaknesses senza editor in Settings (feature: serve un A-brief; pesa su ogni asse dell'assessment ma è congelato dopo l'onboarding).
- **W4** — convenzione grado boulder in `goal.target_grade` **contraddittoria by design tra 3 percorsi**: onboarding e start-new-cycle salvano il lead-calibrato (`BOULDER_TO_LEAD`, raw preservato in `target_boulder_grade`); il discipline-switch di `PUT /api/state` (A-NEW-MACRO) salva invece la convenzione Font (docstring `grade_mapping.py`: "Font for boulder"); il GoalEditor manda il Font raw che finisce nei benchmark lead-calibrati di `assessment_v1`. Serve una **decisione di design** (convenzione unica + normalizzazione server-side + eventuale migrazione dati) — NON un quick fix.
- **W7** — endpoint orfani: `/api/reports/monthly` (endpoint+client mai cablati in UI → decidere: pagina report mensile o rimozione), `/api/user/recovery-code|recover` (morti post-Clerk → candidati a rimozione), `/api/week/test-reminder-response` (solo test). Toccano endpoint count/docs.

---

## Recently closed (2026-07-29)

- **D263 — Perché nel piano non compaiono mai bloccaggi e trazioni con sovrappeso** ✅ **Chiuso** — analisi + risposta del KB + tutte e 4 le azioni implementate ([[C261]] blocco di mantenimento, [[B308]] frequenza garantita, [[A258]] pool condizionato al profilo e copertura casa; la separazione dei `recency_group` era già stata fatta da [[B307]]). Residui metodologici aperti: [[BASE-PULLING-INTENSITY-CAP]], [[PLANNER-ACCESSORY-GAP]]. Analisi originale (read-only, 2026-07-29, su segnalazione di Daniele verificata sul suo stato prod). **Non li ha persi: il piano ne mette pochissimi per costruzione.** **(1) La causa principale:** `pulling_strength_gym` — l'**unica** sessione che usa il template `pulling_strength_compound`, cioè i 3 blocchi dedicati (`weighted_pullup_main`, `lock_off_hold`, `typewriter_unilateral`) — **non è nel pool di nessuna fase**, né lead né boulder. È la sessione progettata esattamente per il lavoro che manca, ed è irraggiungibile dal macrociclo. Stessa sorte per altre 4 sessioni di forza: `heavy_conditioning_gym`, `legs_strength`, `lower_body_gym`, `upper_body_weights` (i 7 `test_*` orfani sono invece legittimi — flusso test separato). **(2) Conseguenza sul macrociclo di Daniele:** su 12 settimane, solo **6** possono ospitare un blocco di tirata, e sempre **un blocco singolo** dentro una sessione che ha altro come focus — `strength_long.pulling_compound` (solo in `strength_power`) e `limit_boulder_gym.supplementary_pulling` (opzionale, `required:false`). In `base`, `power_endurance` e `deload` non c'è **nessuna** tirata pesante. **(3) Il ranking funziona:** simulando 16 settimane col seed di varietà settimanale (B274) e la recenza iniettata come in produzione, il blocco ruota correttamente — `lock_off_isometric` 4/16, `weighted_chinup` 4/16, `one_arm_pullup_assisted` 4/16, `typewriter_pullup` e `pullup` 2/16. Quindi **i bloccaggi ci sono**, ma solo nelle ~4 settimane di `strength_power`, una volta a settimana. `weighted_pullup` in particolare non esce quasi mai perché condivide `recency_group=pullup_variants` con altri 5 esercizi e il gruppo è penalizzato in blocco. **(4) Il motore adatta i pesi al profilo, ma non il pool di sessioni:** `_adjust_domain_weights` abbassa `pulling_strength` per Daniele (0.25→0.21 in strength_power, 0.05→0.02 in performance) perché ha 100/100 su quell'asse, e alza `technique` (0.10→0.19, 0.25→0.34) che è a 30. **Quindi per lui la scarsità di tirata è probabilmente corretta** — ma l'appartenenza al pool è statica, quindi uno scalatore con tirata *debole* riceverebbe la stessa dose quasi nulla. Il meccanismo che produce il risultato giusto per Daniele non è quello che dovrebbe: è un orfano strutturale. **Prossimo passo:** domanda al KB pronta in `docs/research_kb/question_pulling_strength_dosing.md` (7 domande mirate: collocazione per fase, dose di mantenimento e detraining della forza massima, se esista un pavimento sotto cui non scendere neanche per un asse massimale, sessione dedicata vs blocco nei template, interferenza con sospensione massimale e boulder al limite, verdetto sul caso concreto). **(5) Risposta del KB ricevuta (2026-07-29) → NON won't-fix.** Verdetto: *«comportamento corretto prodotto da un meccanismo sbagliato»* — giusto per Daniele oggi (taper, 11 giorni all'obiettivo, tecnica a 30 è il vero limiter, forza massima decade in ~4 settimane quindi nessuna perdita attesa), **difettoso in generale**. Tre livelli: (i) CRITICO, un peso di dominio basso non garantisce una dose bassa ma **assenza probabilistica**, mentre il mantenimento richiede frequenza garantita; (ii) CRITICO, il pool di fase è statico quindi uno scalatore con tirata a 20/100 riceve la stessa dose quasi nulla; (iii) IMPORTANTE, 8 settimane su 12 a zero contraddice il modello **DUP dichiarato** in `04_periodization.md` (*«phase weights shift gradually, not binary on/off»*) — è una contraddizione interna al progetto, non un'opinione. Azioni raccomandate: 1) separare i `recency_group` di trazione zavorrata / bloccaggio / monobraccio (sono qualità complementari, non varianti da ruotare — oggi **competono fra loro**, il che da solo spiega `weighted_pullup` 2/16) · 2) blocco tirata in `base` e `power_endurance` · 3) ⚠️ regola di frequenza garantita ≥1 blocco/7-10 gg · 4) ⚠️ pool di fase condizionato al profilo · 5) audit "peso basso → dose zero" su altri domini. **Dati di risposta + audit punto 5 fatti** in `docs/research_kb/answer_pulling_strength_dosing_data.md`: 7 giorni allenabili e tetto **4** giorni duri (non 2 — l'opzione "sessione dedicata" è praticabile per lui); nessun macrociclo dopo il 2026-08-09; la scala **satura ma è target-relativa** (100 = "esattamente al requisito", Daniele è a 1.01× il benchmark 8a+, margine zero → il clamp distrugge l'informazione per costruire il pavimento, che va derivato dal ratio grezzo); **punto 5: il difetto NON è sistemico** — su 30 coppie (fase × asse) solo 3 hanno peso >0 e zero sessioni, di cui 2 in deload (benigne): il buco vero è `power_endurance`/`pulling_strength` (0.10) più `base`/`pulling_strength` coperto da **una sola** sessione opzionale. `macrocycle_v1` è modulo ad alto rischio → analisi + STOP + OK prima di toccare. Vedi anche [[PLANNER-ACCESSORY-GAP]], stessa famiglia di problema.

- **~~ADHOC-PAST-SESSIONS-VANISHED~~** ✅ **Chiuso — non è un bug** ([[D264]], 2026-07-29, read-only). Il sospetto di [[B309]] era che una rigenerazione avesse cancellato sessioni passate. **Falso:** gli `adaptations` della settimana `2026-07-20` (31 eventi, in ordine) mostrano che **ogni** `add_custom_session` è seguito da un `remove_session` esplicito sullo stesso `session_ref` — `cs_e9f88ebb`, `cs_3ade86c2`, `cs_2a3e40c2` il 20/07 (add→remove immediati, prove del picker), `cs_d6cae4bb` il 22/07, e `cs_a9ea4d09` con la sequenza completa `add → mark_done → mark_planned → remove_session`, seguita da un `quick_add` di `core_training` sullo stesso slot. **Sono rimozioni dell'utente**, non regressioni del motore: nessuna violazione del pilastro di immutabilità, nessun brief da aprire. **Effetto collaterale noto e già documentato:** `feedback_log` è append-only e sopravvive all'undo per scelta ([[B192]], `replanner_v1.py:1053-1057`), quindi la riga di feedback di `custom_cs_a9ea4d09` (difficoltà "ok", 140 s) resta e viene contata da `_build_difficulty` nel report settimanale del 20-26/07 pur non esistendo più nel piano. Distorsione minima (1 voce su una settimana), trade-off accettato quando fu deciso: se dà fastidio, il fix è filtrare `feedback_log` sulle sessioni ancora presenti nel piano → [[B-FEEDBACK-ORPHAN-FILTER]], non aperto.

- **~~A-ADHOC-DELOAD-CAP~~** ✅ **Chiuso won't-fix (decisione Daniele, 2026-07-29):** «non è grave se ogni tanto piazza qualcosa di pesante». `phase_affinity` resta una **preferenza** di ranking e non diventa un tetto hard: quando i candidati appropriati alla fase si esauriscono, la coda della selezione può pescare lavoro fuori banda (es. `high` in settimana di scarico) ed è accettabile. Non riaprire.

- **D261 — Perché il composer adhoc non produce i bloccaggi** ✅ **Audit chiuso** (opzioni 2+3 implementate da [[B307]] con OK di Daniele; opzione 1 → [[A-ADHOC-PHASE-AFFINITY]]; opzione 4 scartata come raccomandato). Audit read-only, `docs/audit/D261_adhoc_selection_ranking.md`, 2026-07-29. Nato per indagare il pattern `pull_vertical` sovraffollato; **smentisce la mia stessa ipotesi**. **Causa reale:** `adhoc_builder._rank_key` ordina per `phase_affinity` → non-recente → id, ma (a) `phase_affinity` esiste su **1 esercizio su 255**, (b) il termine "non-recente" è **codice morto** (i recenti sono già hard-esclusi da `exclude=used`) → la selezione collassa sull'**ordine alfabetico dell'id**, in *ogni* sessione adhoc e per *ogni* focus. `lock_off_isometric` perde perché inizia per L, non perché sia inadatto. Corollario docs↔codice: A243 dichiara il builder "phase-aware via `phase_affinity`" — il codice legge il campo, i dati non ce l'hanno, quindi la parte phase-aware è **inattiva** (impatto confinato: `phase_affinity` è consumato solo da `adhoc_builder.py:122`, il planner non lo usa). **Causa secondaria:** `MAX_PER_PATTERN` capa su `pattern` (12/14 pulling = `pull_vertical`) mentre `recency_group` distingue già lock-off/monobraccio — ma le etichette `vertical_pull`/`pulling_vertical`/`pullup_variants` vanno normalizzate prima di usarle. **Lo split di `pull_vertical` è la soluzione sbagliata:** `pulling_strength_compound.json` ha un blocco chiamato `lock_off_hold` che filtra proprio `pull_vertical` — togliendogli il lock-off il design "pesante→bloccaggio→unilaterale" collasserebbe in tre trazioni (regressione del piano peggiore del sintomo). **Raccomandazione:** focus dedicato `lock_off` → cap su `recency_group` → popolare `phase_affinity` come brief separato (lavoro di dominio con la KB, non di codice). Baseline misurato per la verifica: filtro isolato = 10 candidati → `archer_pullup`; `limit_boulder_gym.supplementary_pulling` → `archer_pullup`.

- **~~C-EQUIPMENT-DECLARATIONS~~** ✅ **Chiuso** (2026-07-29, [[C262]]). Punto 1 **risolto**: `finger_extensor_training` e `finger_extensor_band` dichiarano ora `equipment_required_any: [band, resistance_band]` — l'ambiguità fra le due chiavi si risolve con la semantica OR disponibile da [[B305]], e il timore di togliere il prehab a chi non ha elastici è stato **verificato infondato** (restano `finger_tendon_glides` per le dita e `forearm_stretches`/`cooldown_forearm_wrist_stretch` per il polso). Punto 2 (`jump_rope`) **chiuso won't-fix**: non esiste una chiave `rope`/`jump_rope` in `KNOWN_EQUIPMENT_KEYS` né un modo per l'utente di dichiararla in onboarding, quindi introdurla renderebbe l'esercizio selezionabile solo da chi possiede una chiave che nessuno può possedere — cioè lo ucciderebbe, esattamente il difetto bonificato da [[D262]]. È un warmup `low` con sostituti equivalenti. Non riaprire.

- **~~B-SUB-TRIAL-RECONCILE~~** ✅ **Chiuso — by design, non won't-fix per pigrizia** (verificato 2026-07-29). **(1) Nessun leak in corso:** su 16 subscription in produzione, le righe `trialing` con `trial_end` scaduto sono **zero** (10 trialing, tutte con scadenza futura — la coorte del 5/08; il caso storico `daniele.somensi@ferrero.com` è ora `canceled`). **(2) L'esclusione delle righe Stripe è una scelta motivata, non una dimenticanza:** [[A250]] applica già la lazy expiry ai trial **locali** (senza `stripe_subscription_id`, dove nessun webhook arriverà mai), e il commento in `subscription_guard.py` spiega perché le righe Stripe restano fuori — *«a lagging webhook must not lock out a user whose trial just converted to active»*. Aggiungere il guard proposto scambierebbe un leak raro con il rischio di **bloccare fuori un cliente che ha appena pagato**, che è il fallimento peggiore per un prodotto a pagamento. **(3) La visibilità c'è già:** `scripts/gtm_funnel.py` elenca i trial con la loro scadenza, quindi una riga rimasta indietro si vede senza doverla bloccare. Se un giorno il leak si materializza, la cura giusta è un **alert**, non un blocco. Non riaprire senza una riga realmente scaduta da mostrare.

- **A258 — Pool di fase condizionato al profilo + copertura tirata a casa** ✅ (⚠️ `macrocycle_v1.py` e `planner_v2.py`, moduli ad alto rischio — Fase 1 con STOP gate, OK esplicito, poi implementazione). Chiude il punto 4 (CRITICO) di [[D263]] e il residuo HOME-ONLY-PULLING-GAP. **(1) Pool condizionato:** `_build_session_pool` accetta ora `assessment_profile` (opzionale, default `None` = comportamento identico a prima — i ~25 file di test che la chiamano senza profilo restano validi); `pulling_strength_gym` entra per chi ha `pulling_strength < 50`. Soglia riusata da `_adjust_domain_weights`: una sola definizione di "asse debole" nel motore, con un test che verifica che alla stessa soglia salga anche il peso. **Vale per ogni disciplina** — il buco nel pool boulder è identico. **(2) Due correzioni rispetto al brief, entrambe da misura:** *ruolo* `primary` e non `available` — da `available` la sessione non veniva **mai** collocata (perde contro le primarie); da `primary` entra al posto di un'altra seduta dura e **il conteggio dei giorni duri resta identico** fra profilo debole e forte, che è esattamente il "in sostituzione, non in aggiunta" del KB. E *solo* `strength_power`, non anche `base`: la sessione è `intensity: high` mentre base ha `PHASE_INTENSITY_CAP = medium`, quindi il planner la scarterebbe comunque — dichiararla in base sarebbe una promessa senza effetto (→ [[BASE-PULLING-INTENSITY-CAP]]). **(3) Divergenza del replanner chiusa:** il pool viaggia ora in `profile_snapshot` accanto a `domain_weights`, e `apply_events` lo preferisce alla ricostruzione da `(phase_id, discipline)` — che già era costata un bug (B287/R-3: un boulderista con pool da lead) e avrebbe fatto **sparire** la sessione condizionata da una settimana replanificata. Fallback per le settimane pianificate prima di A258. **(4) HOME-ONLY-PULLING-GAP chiuso:** blocco `pulling_maintenance` anche in `finger_maintenance_home` (base) e `finger_strength_home` (PE/SP) — entrambe richiedono hangboard, che implica la sbarra via `PULLUP_BAR_IMPLIERS`, quindi il blocco è sempre eseguibile dove la sessione lo è. Un utente senza palestra non resta più scoperto. **Limite dichiarato:** eleggibilità ≠ collocazione — sotto le 6 sedute/settimana la settimana si riempie di primarie e la sessione resta nel pool senza entrare; per quegli utenti la tirata arriva comunque dalla garanzia di [[B308]]. Test: `test_a258_profile_conditional_pool.py` (17). Suite completa verde.


- **B308 — PASS 2.6: stimolo di tirata garantito ogni settimana** ✅ (⚠️ `planner_v2.py`, modulo ad alto rischio — Fase 1 con STOP gate, OK esplicito di Daniele, poi implementazione). Chiude il punto 3 (CRITICO) di [[D263]]: un peso di dominio rende una sessione *più probabile*, non *garantita*, e il mantenimento della forza massima richiede **frequenza**. **Cosa:** nuovo `PASS 2.6` modellato su `PASS 2.5` (mantenimento dita in PE, in produzione da tempo): se la settimana non contiene alcuna sessione che allena la tirata, ne colloca una — giorno vuoto per primo, altrimenti sostituendo una **complementare** e mai una primaria. **Cadenza settimanale** (decisione Daniele): il planner genera una settimana per volta e non ha memoria strutturale, quindi è l'opzione semplice ed è più conservativa della finestra 7-10 gg. **Deload esente** per costruzione (il KB conferma). **I vincoli di sicurezza vincono sempre sulla garanzia:** tetto giorni duri, distanza fra giorni duri e gap dita non vengono mai sacrificati; se non c'è spazio il pass **non forza** e lo dichiara in un nuovo campo di piano `unmet_stimulus` — scelta deliberata, perché uno stimolo "garantito" che sparisce in silenzio è esattamente la classe di bug che [[D263]] ha impiegato mesi a emergere. **Copertura:** flag `pulling` in `_SESSION_META` su 6 sessioni, dichiarato a mano perché A245 E-6 ha rimosso l'I/O di catalogo a import-time da questo modulo; un test confronta il flag col catalogo e fallisce alla prima deriva. Criterio stretto (pattern `pull_vertical`/`pull_horizontal` o domini `strength_pulling`/`lock_off_endurance`): `strength_general` da solo **non** basta, copre 65 esercizi fra cui squat e panca — con quel criterio largo `legs_strength` risultava "sessione di tirata". **Verificato sul macrociclo reale di Daniele:** tutte e quattro le fasi di allenamento hanno ora la tirata, il deload no. Test: `test_b308_pulling_guaranteed_frequency.py` (13). Suite completa verde, immutabilità verificata.


- **C261 — Blocco di mantenimento della tirata in `base` e `power_endurance`** ✅ (catalogo + hook; azione 2 della risposta KB a [[D263]], **prerequisito di [[B308]]**). Il motore lasciava 3 fasi su 5 senza **alcun** lavoro di tirata pesante — oltre la finestra di detraining della forza massima (~4 settimane, Mujika & Padilla 2000) e in contraddizione col modello DUP dichiarato in `04_periodization.md` («phase weights shift gradually, not binary on/off»). **Cosa:** nuovo modulo inline `pulling_maintenance` in **`boulder_circuit_gym`** e **`power_endurance_gym`** — due sole sessioni che coprono tutte e quattro le combinazioni fase × disciplina (boulder_circuit_gym è primary in base/lead, base/boulder e power_endurance/boulder; power_endurance_gym in power_endurance/lead). **Posizionamento secondo il KB:** priorità 70, cioè **sotto** lo specifico di arrampicata (90/85/80) e **sopra** core e antagonisti (60/55/50) — mai riempitivo di fine seduta, perché eseguito affaticato l'intensità reale scende, ed è l'unica variabile non comprimibile per la forza massima. **Dose di mantenimento** (Bickel 2011, Spiering 2021 — si taglia il volume, mai l'intensità): 2 serie × 4 rip, recupero 180 s, come override di blocco sui default dell'esercizio (che sono 4-5 serie, dose di sviluppo). `required: false`: senza sbarra il blocco salta e la sessione regge. **Impatto misurato:** +1 esercizio e +10 di load score per sessione (44→54 e 62→72). Test: `test_c261_pulling_maintenance_block.py` (9: presenza, copertura fase×disciplina, portatori primary, posizionamento, override della prescrizione, non-rottura senza attrezzo). **Incluso il fix di processo:** hook `pre-commit` che blocca i commit su branch non-`main` nel worktree **primario** — il terzo incidente di sessioni parallele (B308 finito su `brief/B309`) è successo perché la regola in CLAUDE.md era condizionale e il preflight è una fotografia istantanea. Regola resa incondizionata.

- **B309 — Coach "Add to today & run": slot hardcodato → sessione fantasma** ✅ (frontend-only; branch `brief/B309-adhoc-slot-conflict` → preview Vercel). **Sintomo riportato da Daniele:** il coach compone la sessione, il tap sul CTA sembra non fare nulla, la sessione non compare né oggi né ieri. **Causa:** `coach/page.tsx` inviava `add_custom_session` con `slot: "evening"` **hardcodato**; il 29/07 la sera era già occupata da `route_endurance_gym`, quindi `replanner_v1.py:1421` alzava `ValueError("Slot 'evening' already occupied")` → 422. E poiché `createCustomSession()` girava **prima** di `applyEvents`, la sessione restava salvata ma non pianificata — **orfana e invisibile** (2 duplicati creati dai due tap). I percorsi `/week` e `/today` non hanno mai avuto il bug: lì lo slot lo sceglie l'utente nel modale. **Fix:** **(1)** nuovo `lib/day-slots.ts` — `findDay` / `occupiedSlots` / `firstFreeSlot`, con ordine di preferenza `evening → morning → lunch` (evening primo: caso comune invariato) e conteggio delle "other activities" B276 (forma lista **e** scalare legacy). **(2)** Lo slot si risolve **prima** di creare qualsiasi cosa; se `applyEvents` fallisce comunque, la custom appena creata viene cancellata (`deleteCustomSession`) — mai più orfane. **(3)** Giornata piena e conflitto di slot → messaggio azionabile, come già fanno `/week` e `/today`. Test: `day-slots.test.ts` (9). **Fuori scope, aperto:** [[A-ADHOC-BACKDATE]] — il CTA usa sempre `localToday()`, non c'è modo di appoggiare una sessione a ieri per loggarla a posteriori. **Da verificare a parte:** le adhoc del 20-22/07 risultano inserite in `adaptations` (e una con feedback) ma non compaiono più nei `days` della settimana — possibile perdita di sessioni passate da rigenerazione, da indagare.

- **D262 — Zero esercizi morti + progressione handstand** ✅ (backend-only; analisi read-only → fix applicati con OK esplicito di Daniele). **Analisi:** incrocio dei 149 filtri di selezione di sessioni+template con i percorsi del composer adhoc **e** con i due percorsi non esprimibili come filtro (iniezione prehab da limitazioni, flusso test), simulando ogni fase × focus × body_part con rotazione della recenza su 15 giri. **Fix applicati:** **(1)** `regeneration_climbing` era **l'unico esercizio irraggiungibile** dell'intero catalogo — `role=["cooldown"]` + `domain=["regeneration"]` mentre tutti e 3 i filtri su quel dominio chiedono `role=["main"]`, e i suoi 3 fratelli sono tutti `main`: errore di dato, corretto a `role=["main"]` (verificato: ora `regeneration_easy.continuity_main` lo seleziona). **(2)** `FOCUS_DOMAINS["technique"]` estesa con `technique_constraint` + `technique_relaxation` — 4 esercizi (one-hand climbing, three-limb drill, single-leg climbing, breathing awareness) erano vivi nel planner e invisibili al coach. **(3)** Nuovo focus `handstand` → `["handstand_skill"]` (richiesta di Daniele: è una progressione a sé, non un sottoinsieme di `technique`), + prompt dell'estrattore aggiornato. **(4) 4 nuovi esercizi** che colmano i buchi della scala: `frog_stand` (ingresso `low` — prima il gradino più basso era `medium`), `handstand_kick_up_wall` (controllo dello slancio), `heel_pulls_chest_to_wall` (il ponte muro→freestanding che mancava), `wall_handstand_shrugs` (forza di elevazione scapolare, la ragione più comune per cui un hold cede); `pike_pushup` esisteva già ma non era collegato — ora dichiara anche `handstand_skill`, così il precursore dell'HSPU è raggiungibile dalla progressione. Catalogo 255 → 259. **(5)** Difetto del riempimento di budget ([[B305]]) trovato durante la verifica: `freestanding_handstand_practice` veniva portato a `2×600s`, 20 minuti su 59 per un solo drill — introdotto `MAX_BUMPABLE_WORK_SECONDS`, i blocchi a tempo lungo non sono un volume da raddoppiare. **Risultato: 0 esercizi senza percorso** (227/259 raggiungibili dal coach, il resto dal planner). Test: `test_d262_reachability.py` (7, fra cui una guardia che fallisce se un dominio nuovo resta orfano). Residuo → [[PLANNER-ACCESSORY-GAP]].

- **A257 — `phase_affinity` popolata sul catalogo (causa radice di [[D261]])** ✅ (backend-only). Il campo esisteva su **1 esercizio su 255**: il primo criterio di `_rank_key` non discriminava mai, il secondo era **codice morto** (i recenti sono già hard-esclusi da `exclude=used`), quindi la selezione del composer adhoc collassava sull'**ordine alfabetico dell'id** — in ogni sessione e per ogni focus. **Regola di assegnazione derivata dalla metodologia già nel codice**, non inventata: un esercizio è appropriato a una fase se (a) l'asse che allena è enfatizzato in quella fase secondo `_BASE_WEIGHTS` di `macrocycle_v1` (design doc §4.3, Hörst 4-3-2-1 — peso ≥ media dell'asse; asse piatto come `core_prehab` ⇒ vale ovunque e discrimina l'intensità) **e** (b) la sua `intensity_level` rientra nella banda della fase (da `PHASE_INTENSITY_CAP`). **Eccezione motivata:** l'affinità al deload si concede sulla sola intensità — una settimana di scarico non enfatizza un asse, chiede lavoro leggero; senza l'eccezione interi focus (dita) restavano senza candidati. Copertura **254/255** (`fall_practice` conserva il valore curato a mano). `_rank_key` perde il termine morto (3 call site aggiornati). **Nessuno script di rigenerazione**: i valori sono dati di catalogo versionati, la coerenza è garantita da test. Doc di riferimento per il catalogo: `docs/catalog/phase_affinity_v1.md`. **Effetto misurato** sullo stato prod di Daniele (fase `performance`), esercizi appropriati alla fase per sessione composta: core **2/8 → 6/8**, fingers 1/6 → 2/8, endurance 0/3 → 1/3 (il guadagno è minore dove la metodologia de-enfatizza l'asse in quella fase — corretto, non un difetto). **Tre test preesistenti aggiornati** perché asserivano su *quale* esercizio vincesse il ranking invece che sull'invariante dichiarata dal loro nome: `test_equipment_filter_differs_home_vs_gym` (riscritto e **rafforzato**: casa a corpo libero + simmetria dell'attrezzatura, invece di `assert "bench_press" in gym_ids`), e i due test di plumbing del carico in `test_a253` (fase fixture → `base`, dove il rematore è metodologicamente appropriato; anchor identico, 18.0, verificato). Test: `test_a257_phase_affinity.py` (12). Suite completa verde. Residuo → [[A-ADHOC-DELOAD-CAP]].

- **B307 — Focus `lock_off` + asse di diversità su `recency_group`** ✅ (backend-only; chiude le opzioni 2 e 3 di [[D261]], OK esplicito di Daniele). **(1) Opzione 3:** nuovo focus `lock_off` → `["lock_off_endurance"]` (i domini esistevano già da [[B305]]); l'enum del tool di estrazione si aggiorna da sé (`ADHOC_FOCUS` è derivato da `FOCUS_DOMAINS`), prompt esteso con la mappa movimento→focus (bloccaggi/monobraccio → `lock_off`, trazioni → `pull`, sospensioni → `fingers`). Prima "bloccaggi" annegava nel bucket `pull` a 33 candidati. **(2) Opzione 2:** `_pattern_of` usa `recency_group` invece di `pattern` come asse di `MAX_PER_PATTERN` — `pattern` è troppo grosso (12/14 pulling sono `pull_vertical`), quindi il cap scartava un bloccaggio come se fosse una quinta trazione; `recency_group` è l'asse "stessa famiglia" già usato da B159b. **(3)** Normalizzate 3 etichette `recency_group` quasi-duplicate che avrebbero aggirato il cap, per semantica dichiarata dalle descrizioni stesse: `frenchies` → `pullup_lock_off` («isometric lock-offs at three joint angles»), `uneven_grip_pullup` → `pullup_one_arm` («bridging between two-arm and one-arm»), `eccentric_pullup` → `pullup_variants`. Nessun test/template dipendeva dalle vecchie etichette (verificato); l'effetto sul planner è solo sulla penalità soft di recenza B159b, ora più corretta. **Opzione 4 (split di `pull_vertical`) NON eseguita** — avrebbe rotto il blocco `lock_off_hold` di `pulling_strength_compound`. Verifica e2e con LLM reale e stato prod: il messaggio originale del 28/07 ora compone Archer + Frenchies + Lock-off Isometric. Test: `test_b307_adhoc_lockoff_focus.py` (8). **Causa radice ancora aperta** → [[A-ADHOC-PHASE-AFFINITY]].

## Recently closed (2026-07-28)

- **B306 — Coach adhoc: follow-up routing + card persistente** ✅ (misto; backend in main `57d954b`, frontend su branch `brief/B306-adhoc-card-persistence` → preview Vercel → merge con OK di Daniele). **(1)** Colonna JSONB `coach_messages.adhoc_session` (DDL applicata in prod): `append_coach_message` persiste il payload composto, `/coach/history` lo restituisce, `hydrateAdhocCard` ricostruisce la card con CTA dalla history → **sopravvive al reload PWA** (prima viveva solo nello stato React). **(2)** Gate estratto in `lib/adhoc-gate.ts` (9 unit test) + `isAdhocFollowUp`: messaggi corti ("Si", "Crea!") instradati al composer quando la conversazione recente è adhoc-flavored — l'extractor backend con history resta l'autorità (adhoc:false → fallback chat). Chiude il loop "frase magica" della conversazione del 28/07. **(3)** `COACH_MODEL=claude-sonnet-5` (env Railway + default codice). **Scope deciso fuori:** i18n stringhe card — tutta la UI è inglese, localizzare solo la card sarebbe incoerente (il summary chat è già localizzato da B305). Test: `adhoc-gate.test.ts` (9) + `test_b306_adhoc_card_persistence.py` (2).
- **C260-bis — 4 esercizi macchina dichiaravano solo `weight`** ✅ — `leg_extension`/`leg_curl` → `leg_press`, `triceps_cable_pushdown`/`cable_woodchop` → `cable_machine`. Erano **fisicamente impossibili** con i soli manubri eppure eleggibili a casa (il woodchop compariva nelle sessioni adhoc home). Effetto collaterale corretto e verificato: in una location con cable machine **ma senza pesi liberi**, `cable_woodchop` ora è eleggibile e supera `pallof_press` nel ranking P0 anti-rotation — prima era escluso a torto. Il test A229 asseriva "pallof vince" invece di "pallof è eleggibile": riscritto sull'invariante dichiarata dal suo stesso nome. Nessun impatto sulle palestre reali (che hanno sia cavi sia pesi, dove il woodchop era già eleggibile).
- **C260 — bar_dead_hang** ✅ — nuovo esercizio (finger_aerobic_endurance, solo `pullup_bar`, bodyweight): con "casa minima" (solo sbarra — il caso trasferta) il focus fingers componeva un pool **vuoto**; il dead hang è l'unica opzione finger-adjacent senza hangboard. Catalogo a 255.
- **Prehab-injection equipment_required_any** ✅ (era il punto 3 di [[C-EQUIPMENT-DECLARATIONS]]; OK esplicito di Daniele, lista STOP) — `_inject_prehab_for_limitations` in `resolve_session.py` ora onora `equipment_required_any` (OR) come il filtro P0: `elbow_eccentric_curl` (any=[weight, resistance_band]) non viene più iniettato dove non c'è né peso né elastico. Impatto: solo utenti in location senza entrambi. +2 test in `test_limitations.py`.

- **B305 — Coach adhoc: equipment_required_any + domini pulling + prompt anti-fabbricazione + summary i18n + riempimento budget tempo** ✅ (backend-only). Root-cause della conversazione-disastro del 28/07 (20 msg, "board limit a casa" + card fantasma): **(1)** `_exercise_fits_equipment` (body_part_picker) ignorava `equipment_required_any` → i board-only (`board_limit_boulders` etc., `equipment_required=[]`) passavano il filtro home nell'adhoc builder (il TODO li dava per "inerti" — vero per il picker B224, falso per adhoc che pesca role=main). Ora semantica AND+OR allineata al resolver pieno. **(2)** Quasi tutta la famiglia pullup era taggata solo `strength_general` → focus "pull" raggiungeva 2 main; aggiunti `strength_pulling` (14 esercizi) e `lock_off_endurance` (lock_off_isometric, archer, typewriter, one_arm_assisted) — zero impatto planner (nessun template filtra su quei domini, verificato). **(3)** `ab_wheel_rollout`→`ab_wheel`, `back_extension`→`bench`, `foam_rolling_general`→`foam_roller` (req=[] errati). **(4)** Il system prompt del coach citava testualmente il formato "I built you a session — …" e l'LLM l'ha **imitato** fabbricando una build mai avvenuta (il "Si" delle 08:54 non passò mai dal composer — gate frontend); ora il prompt vieta esplicitamente le conferme di build e chiarisce che la card appare in chat. **(5)** Slot `language` (it/en, required) nell'extractor → `build_adhoc_summary` localizzato (explanation inglese preservata per le honesty note A252). **(6)** Riempimento budget tempo: "60 minuti" componeva ~30 min (cap 8 esercizi con set base); ora +1 set round-robin sui non-warmup (cap 6) fino al budget. Verificato end-to-end con lo stato prod di Daniele + estrazione LLM reale: 60 min esatti, archer pull-up + core solido, zero attrezzi fantasma, summary in italiano. Test: `test_b305_adhoc_equipment_any.py` (13). Follow-up: [[B306]] (frontend) + [[C-EQUIPMENT-DECLARATIONS]].

## Recently closed (2026-07-24)

- **B304 — Tooltip viewport clamping + presentazione target-relative degli assi** ✅ (frontend, branch `brief/B304-tooltip-axis-relabel` → preview Vercel; worktree isolato). Chiude [[D260]] Scope A + la metà **presentazionale** di Scope B. **Part 1 (Scope A):** il popover ⓘ del radar (`AxisTooltip` in `radar-chart.tsx`) era un box a larghezza fissa `w-72` centrato sulla cella con `translateX(-50%)` senza collision detection → gli assi in colonna sinistra sforavano il bordo sinistro sotto ~400px (iPhone). Ora clampa orizzontalmente al viewport (shift + `env(safe-area-inset-*)`, margine ≥12px) e **flippa sopra** la bottom tab bar quando servirebbe; `max-width: min(288px, 100vw-24px)`. La matematica di posizionamento è estratta in `lib/radarTooltip.ts` come funzioni pure con unit test a 320/390/768/1280 (il posizionamento DOM misura poi muta lo stile del nodo direttamente — nessun setState-in-effect). Nessuna libreria di posizionamento aggiunta (unico consumer: `/plan`, verificato). **Part 2 (Scope B, solo presentazione):** sottotitolo del radar **"Readiness for {target}"**, badge **"✓ At target"** al posto del 100 nudo sugli assi saturi (geometria del grafico invariata), e le 5 copy dei tooltip riscritte per rendere **esplicito** il framing target-relative ("Scored against what {target} typically demands — 100 means you're already there") + low-line riformulata come **roadmap** invece di verdetto. **Zero** modifiche a engine/formule/anchor/score/DB; solo frontend; sessioni passate intatte (nessun percorso di rigenerazione toccato). Test: +26 frontend (`radar-tooltip.test.ts`: clamping, flip, interpolazione grade, budget 300 char, copertura 5 assi lead+boulder). Suite frontend 34 file / 386 test verdi; tsc + eslint + `next build` OK.

### Residui di [[D260]] (lato engine, Open — richiedono decisioni di prodotto di Daniele)

- **D260-P1a — Endurance senza test dedicato**: l'asse "Endurance" è `0.8 × power_endurance` + tenure + hang-duration; il design doc §2.2 specifica Repeaters/Critical Force. Open. Richiede decisione: aggiungere un test reale o rinominare l'asse (domanda 3 dell'audit). Brief tipo D/A.
- **D260-P1b — Technique = proxy gap RP−OS + self-report**: asse guidato dal gap redpoint−onsight (solo 7 valori possibili) + penalità auto-dichiarata; è la leva dominante dei pesi di dominio. Open. Decisione: il gap è un segnale legittimo di tecnica per un redpointer? (domanda 2). Brief tipo D/A, STOP-gate (`assessment_v1`→`macrocycle_v1`).
- **D260-P2 — saturazione anchor target-relative + soglie fragili + default "50"**: re-anchoring di Finger/Pulling (assoluto vs target-relative), curve continue al posto dei cliff <35/<50/>75, provenienza `measured|default` per axis. Open, **invalida gli score storici** → decisione di prodotto (domanda 1). Vedi `docs/audit_D260_tooltip_and_assessment_scoring.md` §8 per la sequenza fix proposta.

## Recently closed (2026-07-23)

- **A256 — Wizard di onboarding pubblico: il muro della registrazione si sposta a valle** ✅ (frontend, branch `brief/A256-public-onboarding-wizard` → preview Vercel; worktree isolato). **Problema:** `/onboarding/welcome` era pubblico ma lo **step 1 di 12** (`/onboarding/profile`) no, e il CTA "Start assessment" era un `<SignUpButton>` → il visitatore freddo da flyer/Reddit doveva creare un account **prima di vedere un solo output del prodotto**. **Fix:** i 12 step del wizard + `/onboarding/recover` (linkato dalla welcome pubblica) diventano pubblici, derivati da `ONBOARDING_STEPS` così un nuovo step nasce pubblico; l'account viene chiesto **sul CTA finale in `/review`**, dopo che l'utente ha visto il proprio riepilogo ("salva questo", non "iscriviti per iniziare"). Ritorno post-signup con **auto-submit**: l'intent (`generate`|`test`) viaggia in `?complete=` nel `redirect_url` (sopravvive al full reload di Clerk), guardie su `authLoaded`/`isSignedIn`/`loaded`/`profileProblems` + ref anti-doppio-invio + `replaceState` per non ri-sparare al reload. `start-week` e `install` restano gated (girano a piano esistente). **Zero perdita dati:** B293 aveva già predisposto tutto (bozza `_anon` in localStorage, nessuna `getState()` da anonimo, adozione anon→user in `loadDraft`); `SessionScopeGuard` non tocca le bozze onboarding; UTM già in localStorage → attribution intatta; `/api/onboarding/defaults` (unico endpoint chiamato dal wizard, da `/locations`) è senza `Depends(get_user_id)` → 200 da anonimo, verificato in prod. **Leak chiuso nello stesso brief:** `clearOnboardingDraft()` puliva solo `_user_XXX` e lasciava `_anon` orfano sul device — innocuo finché nessuno poteva produrne una, un leak dal momento in cui il wizard diventa pubblico (device condiviso → il visitatore successivo si ritrovava precompilati i dati del precedente). Test: +3 frontend (`onboarding-draft-scope.test.ts`, verificato che fallisce senza il fix) + `public-routes.test.ts` riscritto (l'asserzione B292 "solo /welcome è pubblico" era diventata falsa per design). Frontend 355 → **360**. Backend invariato (2815).

- **B303 — Onboarding disponibilità: niente selettore "Which gym?" con una sola palestra** ✅ (frontend, branch `brief/B303-gym-selector-single` → preview Vercel). In `availability/page.tsx` il dropdown gym compariva con `gyms.length > 0`, quindi anche con **una sola** palestra mostrava un select con un'unica opzione — rumore inutile. Ora condizionato a `gyms.length > 1`. Nessuna perdita di funzione: con una gym il planner usa già quella di default (`gym_id` undefined → `default_gym_id`). Modifica di una riga, zero backend.

- **B302 — Ladder gradi lead priva di 5a+/5b+/5c+: assessment/piano crashavano per i principianti** ✅ (backend-only, tocca `assessment_v1` → feeds `macrocycle_v1`: Fase 1 analisi + OK Daniele). **Bug:** il picker frontend (`LEAD_GRADES`) offre `5a+/5b+/5c+` ma `assessment_v1.GRADE_ORDER` li saltava → `grade_index('5c+')` sollevava *"Unknown grade"* → `compute_assessment_profile` crashava → nessun profilo → nessun piano. **Scoperto su `daniele.somensi@ferrero.com`** (max 5a+, target 5c+, `profile: null`) ma sistemico: qualsiasi principiante lead che seleziona quei gradi non poteva generare il piano. **Fix:** inseriti `5a+/5b+/5c+` in `GRADE_ORDER`. Blast radius verificato: tutti i consumer usano gli indici **relativamente** (`grade_gap`, ranking milestone, distanze) tranne il proxy euristico `(current_idx/target_idx)×axis_max` di assessment — shift atteso di ~1 punto su utenti senza test (8a+/8b: 16/17→19/20; `pulling_strength` 61→62, test aggiornato). **outdoor_log reso behavior-preserving:** `_GRADE_WEIGHT` ancorato allo spacing pre-B302 (i + del grado 5 ereditano il peso base, i 6a+ invariati) → il load outdoor storico non si muove; bonus, un 5c+ outdoor non pesa più 10 (era `_UNKNOWN`, mis-pesato come un 6c). `BOULDER_GRADE_ORDER` allineato al picker (5A+/5B+/5C+). `BOULDER_TO_LEAD` già completo (boulder non crashava). Test: +10 (`test_b302_grade_ladder.py`). Suite 2815 → **2825**. ferrero si sblocca ricalcolando assessment → rigenerando.

- **A255 — Onboarding: equipment di default preselezionato per home e nuove palestre** ✅ (frontend, branch `brief/A255-onboarding-equipment-defaults` → preview Vercel). **Root cause di Mario:** in `locations/page.tsx` una nuova gym nasceva con `equipment: []` e l'attivazione "train at home" non preselezionava nulla → l'utente doveva spuntare tutto a mano e chi dimenticava l'hangboard perdeva i test dita + le sessioni forza in silenzio (Radium finita con solo `gym_boulder`). **Fix:** `addGym` ora parte con `["hangboard", "pullup_bar", "weight"]` preselezionati; `toggleHomeEnabled` semina `["hangboard", "pullup_bar"]` alla prima attivazione (solo se `home` è ancora vuoto → non sovrascrive scelte deliberate al re-toggle). La **superficie di arrampicata** (gym_boulder/gym_routes) resta a carico dell'utente perché è disciplina-specifica (il gate `locationBlockers` la richiede comunque). Combinato con [[B301]], un tag `weight` di default sblocca subito la forza. Nessun tocco al backend/planner. Verificato su preview.

- **B301 — `weight` ≡ `dumbbell`: le sessioni di forza sono raggiungibili con qualsiasi peso libero** ✅ (backend-only, STOP-gate `equipment_utils`/pipeline planning: Fase 1 analisi + OK Daniele → Opzione A). **Bug:** l'espansione equipment in `equipment_utils.expand_equipment` era **monodirezionale** — `dumbbell/kettlebell/barbell → weight`, ma chi spuntava solo "Weight plates" (`weight`) non otteneva mai `dumbbell`, e le **2 sole sessioni** gated su `["dumbbell"]` (`heavy_conditioning_gym`, `lower_body_gym`) restavano irraggiungibili. **Fix (Opzione A):** `WEIGHT_FAMILY = {weight, dumbbell, kettlebell, barbell}`; la presenza di uno qualsiasi implica **sia `weight` sia `dumbbell`** → plates-only / barbell-only / kettlebell-only sbloccano la forza. **Blast radius minimo:** 0 esercizi filtrano su dumbbell/weight (gating solo a livello sessione), quindi nessun rischio di sessione svuotata in resolve. Choke point unico condiviso da planner/resolver/replanner/body_part_picker → fix uniforme. Regressione: un utente con `dumbbell` produce output byte-identico (aggiunge `dumbbell` che già aveva → no-op). Test: +8 (`test_b301_weight_dumbbell_equivalence.py`), B159 invariati. Suite 2807 → **2815**. **Scoperto durante l'analisi utente di Mario** (palestra Radium registrata a mano con solo `gym_boulder`).

- **B300 — La root manda i visitatori sloggati alla welcome landing, non al login wall** ✅ (frontend, branch `brief/B300-root-welcome-landing` → preview Vercel → OK Daniele → merge in `main`; deploy prod forzato via API perché il webhook Vercel non era scattato sulla push). **Problema di funnel:** un visitatore freddo da pubblicità/QR che digitava `climbagent.app` sbatteva su `/sign-in` (form di login nudo, zero pitch) invece che sulla pagina che vende il prodotto. **Fix chirurgico (1 riga in `src/app/page.tsx`):** il ramo "non loggato" della root passa da `/sign-in` a `/onboarding/welcome` (la landing pubblica: hero "Periodized training" + value props + CTA "Start assessment"). Nessuna regressione — utente loggato resta dritto a `/today` (nessun doppio hop), logica offline `readLastDestination` (A245) intatta. **Secondo commit:** aggiunto link **"Already have an account? Sign in"** ben visibile (colore primary, sotto la CTA) con Clerk `SignInButton` che dopo il login torna alla root → smista al piano; il recover declassato a "Lost access? Recover with a code". **Doc aggiornata:** `docs/attribution_utm_convention.md` (la vecchia regola "MAI linkare la root / → /sign-in" era ora superata) + sezione "Entry-point routing" in `CLAUDE.md`. Nessun test nuovo (routing puro, verificato su prod da Daniele: sloggato→welcome, Sign in→/today, loggato→/today).

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
| F4 | **Stale cached week plan across deploys** — no regeneration trigger on deploy; users onboarded within ~5 min of a push keep pre-push output. | LOW | P3 | B | XS | Accept (deploy-window artifact). Users can force-regenerate via Settings. Document in user guide. |
| F5 | **`goal.primary_weakness`/`secondary_weakness` are absent** — actual storage at `assessment.self_eval.*`. Consumers reading `goal.*` see `None`. | LOW | P3 | D+B | XS | Grep consumers; if any read `goal.*` for weaknesses, fix read site (not write). Spec-drift only. |
| F6 | **`macrocycle.phases[].weeks` is `null`** — consumers iterating `phases[].weeks` see `null`; sum via `start_week` deltas works. | LOW | P3 | D+B | XS | Audit consumers; drop the field from schema if all compute from `start_week` deltas, else populate at generation. |
| F7 | **`goal.deadline` empty while `total_weeks=12`** — onboarding writes `deadline=""` when deadline is derived from `total_weeks`. | LOW | P3 | B | XS | Cosmetic. Compute ISO date from `total_weeks + start_date`, or drop the field. |
| F8 | **`assessment.tests.last_test_date = 2026-04-16`** (3 days before macrocycle start) — writer not traced in D211. | COSMETIC | P3 | D | XS | Grep writer site; likely legacy path in `progression_v1.py`. |

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

### GTM log — re-lancio climbagent.app (2026-07-21, post-A248/A249/A250/A251)

**✅ FATTO (2026-07-21):**
- **Email win-back INVIATE** (manuali, Gmail): 8 destinatari — Christie (personalizzata,
  la più ingaggiata), Cesar + Arthur (con nota Forgot-password), David + Edoardo (in
  italiano), Tabitha, Paolo, Agustin, Rowene (`woween@gmail.com`). Contenuto: trial
  attivo fino al **5 agosto** senza carta (A251), pitch AI coach, mobility/stretching,
  nuovo dominio + reinstallazione PWA, leva Founding Climber $4.99.
- **Welcome email INVIATA** al nuovo utente organico (`xbox.live.marionumber0001@`,
  iscritto 21/07, trial fino al 5/08).
- **Reddit modmail pre-approvazione** (policy value-first): r/indoorbouldering +
  r/bouldering — chiesta approvazione mod prima di postare, link
  `climbagent.app/onboarding/welcome`, offerto ai mod il trial gratuito per feedback.
- Esclusi come da piano: arnaud + pippin (gestiti a parte).

**⏳ PENDING:**
- [ ] Attendere risposta mod r/indoorbouldering + r/bouldering → postare dopo approvazione
- [ ] Domani (22/07): modmail r/climbharder (variante honest prior-removal, già in bozza);
      valutare r/griptraining; post diretti r/ClaudeAI + r/SideProject
- [ ] Email activation-nudge a Donato (`odlan3@`) — NON ancora inviata
- [ ] Monitorare le conversioni win-back prima della scadenza trial del **5 agosto**
      (dashboard admin: chi rientra, chi completa sessioni, chi aggiunge la carta)

**✅ FATTO (2026-07-23):**
- **r/indoorbouldering** — postato intro climb-agent nel thread mensile *Simple
  Questions* (canale mod-approved, nessun post dedicato consentito). Link:
  `climbagent.app`. Angle: training planner + coach chat, focus lead dichiarato.
  Pricing non menzionato nel post.
- **r/bouldering** — outreach rifiutato. **Canale chiuso, non riprovare.**

**⏳ PENDING (2026-07-23):**
- [ ] Monitorare le risposte ai commenti su r/indoorbouldering → rispondere entro 24h
- [ ] Canned reply pronta per la domanda "free or paid?"

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
