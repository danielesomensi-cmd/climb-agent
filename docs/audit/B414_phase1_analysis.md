# B414 — Fase 1: analisi (inbox del coach, scadenza del test, tetto max hang, P2/P3)

> 2026-11-07 · workflow `wf_6b5307f3-48b` (8 analisti per area + 1 critico incrociato), sola lettura su origin/main `4d53bf5`.
> **STOP**: nessuna implementazione prima dell'OK di Daniele (CLAUDE.md, moduli ad alto rischio).

## Decisioni di Daniele già prese (2026-11-07)

- Scadenza del test: l'app propone sempre il test; in alternativa si posticipa la scadenza per scelta; non si azzera mai niente.
- END-OF-CYCLE-STUCK-IN-DELOAD: accettato così, il nuovo ciclo lo avvia l'utente.
- REENTRY-MAX-HANG-SETS: togliere il tetto di 5 serie.
- P3: dentro (perimetro nel messaggio del 07/11).

## Domande aperte per Daniele (con raccomandazione)

1. Test che scade (vale per tutti gli utenti): confermi il modello A? Alla scadenza non si spegne niente (scale, carichi ancorati, rotazione e coach restano attivi e continuano a progredire) e 14 giorni prima la Today mostra una card non chiudibile con solo «Fai il test» e «Posticipa la scadenza». Per il rinvio: scelta fra 2, 4 o 6 settimane, ripetibile senza tetto totale, un solo bottone per dita e trazione insieme. Consiglio: sì a tutto, con 4 settimane come scelta predefinita.
2. «Fai il test» a metà ciclo: lo piazzo come tua richiesta nella policy (record nuovo in retest_declines, un cambio di schema che richiede il tuo OK) nel primo giorno ammesso dalle guardie (72 h dopo una max) e in qualunque fase, perché la scelta è tua? Correggo qui anche il «Schedule test week» di A246, che oggi a metà ciclo non piazza niente e il cui promemoria resta nascosto per sempre da un campo del ciclo vecchio? Consiglio: sì alla richiesta via policy, ammessa in ogni fase ma mai contro la guardia delle 72 h; sì ad A246 qui, così i campi del promemoria si azzerano a ogni nuovo ciclo.
3. «P2» in parole semplici sono tre cose. (1) Se fai un test in un giorno diverso dal lunedì, per il resto della settimana l'app crede che non l'hai fatto e può rimettertelo. (2) Il quick-add al Bkl non ti mostra i test con i pesi e un testo della card dei test è sbagliato. (3) I bottoni sulla card dei test: li assorbe la card della scadenza, solo «Fai il test» e «Posticipa», niente «Not now». In più: una sessione di test segnata «fatta» senza valori chiude la settimana (il massimale resta quello vecchio finché non metti i valori). Ok? Consiglio: sì a tutto.
4. Il «fatto» nei player: (a) un esercizio con tutte le serie contate ma chiuso con Skip conta come fatto; con serie parziali resta «non fatto», ma le serie si salvano; (b) nel player di My Sessions un voto su un esercizio saltato parte con completed:false; (c) Done senza timer sulle custom vale le serie prescritte (oggi succede solo sulle scale); (d) esercizi a lati alterni: per la dose delle chiavi contano le serie per lato; (e) lead_tryhard_gym fatto conta anche come chiave Tecnica; (f) se il player invia una sessione tolta dal piano, propongo «Registrala al posto di X» e «Scarta», e «come extra» solo se c'è uno slot libero. Consiglio: sì a tutto.
5. Catalogo e resolver: PE solo route_intervals dove ci sono le vie, altrimenti un solo PE boulder dalla rotazione di fase; tecnica nella PE come una regola per serie nei cue; sospensioni sub-max dopo i PE senza tag dita (come la sessione di catalogo) e mai il 7/3 nella PE; back squat per tutti quelli che hanno il bilanciere (stessa dose 5×6, 4 serie in scarico), goblet senza; 2RM senza pesi saltato, mai sostituito; il pin controlla solo l'attrezzatura. Consiglio: sì a tutto. La partenza a freddo del back squat (oggi circa 11 kg per chi non ha un carico) la lascio fuori da B414 per non toccare progression_v1: tu hai già il carico.
6. Cambio sede e rigenerazione: una combinata spostata in una palestra senza pesi diventa la sola sospensione e la trazione aspetta il turno dopo; «cambia sede → casa» usa l'attrezzatura di casa salvata (vale per tutti); alla rigenerazione il planner rilegge la palestra che hai scelto (Opzione B) e, se il coach indica lo slot, cambia solo quello; intorno alle tue sessioni future il motore rispetta solo gap dita, gap hard e tetto, e la sonda regeneration_guard_warnings, che nessuno legge, si toglie. Consiglio: sì a tutto. Le ancore (B369-P6 punto 1) come ultimo passo, rinviabile; la corsa residua di B371 in un brief a parte.

## Piano di implementazione (passi da un commit)

| # | Consegna | Alto rischio | Dipende da | Voci | Note |
|---|---|---|---|---|---|
| 1 | backend_main | sì |  | INBOX-2026-11-05: `stimulus.row_done` unico; `logged_entry_counts` diventa un wrapper, `bw_ladders.ladder_row_done` lo richiama; load_score NON cambia<br>backend/tests/test_b414_row_done.py (matrice + proprietà di equivalenza + forme del 04/11 e 05/11 + pre-fill del player libreria non contato + passato invariato)<br>vocabulary_v1.md:1276, ENGINE_ARCHITECTURE, ROADMAP | Il codice di planner_v2, progression_v1 e resolve_session non cambia, ma il loro comportamento sì (PASS 2.7, giorni finger-hard, recency): STOP. Verificato stimulus.py:334-360 e key_sessions_v1.py:314-317. Atteso: settimana 02/11 con try-hard e tecnica «done». Toccata anche la confidenza calcolata dei test (count_exposures). |
| 2 | backend_main |  |  | B312-LOAD-ACTUAL-VS-FROZEN: il passo 4b legge le exercise_instances di `_frozen` con chiave (date, slot, session_id), ripiego sul resolved salvato<br>test_b312_feedback_endpoint (forma prod senza resolved, sessione completa, flusso /today, ripiego B216)<br>ENGINE_ARCHITECTURE §Prescribed vs actual load | Verificato feedback.py:488-497 contro :650-652. Nessun ricalcolo del passato. |
| 3 | backend_main |  | 2 | PLAYED-SESSION-READ-KEYS: `strip_derived` prende le 4 chiavi dal gemello salvato; `read_view` attacca feedback e cue (argomento user_id nei 5 punti di chiamata)<br>test_b371_plan_revision (aggiornare il test :136-165), end-to-end feedback → GET → /events | Serve 6 endpoint di scrittura e il dry run: suite completa. La durata salvata vince sempre sulla copia del client. |
| 4 | backend_main | sì | 3 | INBOX-2026-11-04-ORPHAN (2): `SessionNotInPlan(ValueError)` sollevata da apply_events mark_done quando nessuna sessione corrisponde; /events risponde 422 (dry run compreso), senza riga nel completion log<br>feedback.py: il ramo B216 la riconosce (niente retry), comportamento di /feedback invariato fino al passo 27<br>test_b369/test_a194 restano verdi; nuovo test /events 422 con il passato byte per byte invariato | replanner_v1.py:1268-1274: STOP. Avvisare il coach (runbook): un mark_done con ref sbagliato ora dà 422. |
| 5 | backend_main | sì |  | A289-TEST-DONE-IN-WEEK parte 1 (`axis_official` a fine settimana, `done_in_week`) + parte 2 (sessione di test done senza valori, `result_missing`)<br>backend/tests/test_b414_test_done_in_week.py<br>vocabulary:1196, ENGINE_ARCHITECTURE, user_guide:583 | Verificato retest_policy.py:1260 e il filtro as_of :212-213. Cambia l'input di planner_v2 PASS 3a: STOP. Includere il test della rigenerazione a metà settimana con il passato identico. |
| 6 | backend_main | sì | 5 | REENTRY-MAX-HANG-SETS opzione B: via REENTRY_MAX_HANG_SETS, ramp_for e la chiave `ramp` (anchored_load), il blocco di adhoc_builder.py:388-395, `stored_sets` in resolve_custom_exercises (:907-914), reentry_step/REENTRY_* (retest_policy), `ramp` di athlete_context<br>golden c272 (6 chiavi), test b413/b364/a288 aggiornati, VERSION alzata<br>pulizia di coach/prompt_builder.py:294; frontend `ramp.factor` lasciato (passato) | Decisione di Daniele già presa («togli il tetto»): opzione B salvo sua preferenza per la minima. Verificato anchored_load.py:61-64, :663-666 e che l'unico consumatore di reentry_step sia :384. Il commento di progression_v1.py:1673 si tocca solo con OK. |
| 7 | backend_main | sì | 5, 6 | B414-1 modello A: `tested` = test reale a qualunque età; `valid_until` / `expired` / `expiring`; retest_status li espone; motivo `after_cycle_end`<br>casi stale_tests tolti dai golden non testati di a290/b364 e messi come casi testati espliciti<br>end-to-end con freezegun dal 20/12 al 05/01 sulla fixture di Daniele; non testati identici bit per bit<br>docstring di bw_ladders, bw_progression, anchored_load e phase_anchor; vocabulary §4.5b, ENGINE_ARCHITECTURE §8.2 | Verificato retest_policy.py:67, :306-307, :333-334, bw_ladders.py:325-334. Prima, conteggio in sola lettura in prod degli utenti con un test di più di 90 giorni: per loro cambia regime e PASS 3a comincia a piazzare test della policy. |
| 8 | backend_main | sì | 7 | B414-5: tolte le 4 scritture di `freshness_policy` in progression_v1._update_test_from_log; chiudere B-FRESHNESS-POLICY-INERT | Banale, ma è progression_v1: STOP. Nessun lettore del campo. |
| 9 | backend_main | sì | 7 | B414-2: il rinvio diventa proroga (trigger `expiry` senza test in sospeso, tetto per singolo rinvio until_too_far, upsert con previous_until + evento retest_postponed, DELETE annulla)<br>test_a320 aggiornati (:941-943, :1618, :1630-1637), test nuovi<br>API_ENDPOINTS, vocabulary | Cambio additivo della forma dei record di retest_declines: STOP esplicito. Durata e ripetibilità secondo la risposta alla domanda 1. |
| 10 | backend_main | sì | 9 | B414-3 «Fai il test»: (a) va al test già in piano, (b) con il ciclo finito risponde cycle_ended, (c) richiesta con trigger `requested` (oppure add_planned_session via /events, secondo la domanda 2)<br>ogni lettore di retest_declines filtra per kind<br>se approvato: A246, la conferma piazza davvero i test e start-new-cycle azzera test_reminder_* | Input di planner_v2 PASS 3a e week.py want_tests: STOP. Verificato week.py:785-790 e :1061-1068. |
| 11 | backend_main |  | 7, 9, 10 | B414-6: righe SCADE / SCADUTO / PROROGATO nella CLI e nel blocco coach, warning TEST_EXPIRING / TEST_EXPIRED, VERSION alzata<br>INBOX-2026-11-02-d: key_refs + attribuzione esplicita nella riga ALERT di scripts/athlete_context.py<br>user_guide §5/§6, .claude/commands/custom-session.md, docs/training/athlete_plan.md | Poi la regressione del Coach KB. Solo codici e date, mai valori di salute. |
| 12 | backend_main | sì |  | B381-FALLBACK: helper `_resolve_pin_chain` per il ramo inline e il ramo template; `fallback_exercise_ids`, `pin_exhausted` p0/skip/fail, pin_strict come alias di fail, pin_strict anche nel ramo template<br>lint di catalogo + test_b414_pin_chain.py + c269 che legge i fallback | resolve_session (P0): STOP. Senza le chiavi nuove l'uscita è identica (golden invariati): è il controllo di accettazione. Verificato resolve_session.py:1194-1247 e :283-302. |
| 13 | catalog | sì | 12 | Catalogo GOBLET: back_squat equipment_required [barbell]; legs_maintenance_lunch.squat_main [back_squat → goblet_squat]; note riscritte; version della sessione invariata<br>Catalogo B261-TEST-FALLBACK: `pin_exhausted: skip` su pulling_strength_test.main e test_max_hang_pullup.pullup_2rm_test<br>golden b413 (6 chiavi daniele\|legs), c274:72-74, c275:61; PRE_B413_LEGS_DIGESTS e c272 invariati | Le custom gambe di Daniele (12/11-01/12) restano. Partenza a freddo del back squat (progression_v1) solo se approvata, in un commit a parte con STOP. Prima, conteggio in sola lettura degli utenti con il bilanciere. |
| 14 | backend_main | sì | 13 | INBOX-2026-11-02-b: in infer_sort_category le sospensioni finger_aerobic_endurance diventano finger_endurance; l'ARC su parete resta aerobic_pure<br>test_a121, audit di replica, golden c272/b413 (solo ordine) | Cambia l'uscita del resolver (ordine di exercise_instances). Player e card seguono i blocchi e non cambiano. |
| 15 | backend_main | sì |  | INBOX-2026-11-02-e parte 1 (E2): in session_tags le sospensioni sub-max non danno finger dentro una sessione con intervalli PE e senza altro carico dita<br>test b345/b392 invariati + coerenza con il catalogo e allowlist delle discrepanze note | Consumatore: replanner_v1 add_custom_session (tag salvati). Dopo il deploy, passo 29 (B395). |
| 16 | catalog | sì | 14, 15 | Catalogo power_endurance_gym: un solo blocco PE (si tiene block_id `pe_boulder` per il seme di phase_anchor), intensity_max medium sul blocco finger_endurance<br>exercises.json: una regola tecnica per serie nei cue di four_by_four_bouldering, linked_boulders, linked_boulders_circuit, route_intervals<br>test b157/a290/c261/session_enrichment; golden c272/a290_untested/b413 rigenerati dopo il diff grezzo | Opzione A (solo catalogo) salvo diversa risposta di Daniele. Verificato power_endurance_gym.json:37-87 e resolve_session.py:565-570. Invisibile per Daniele fino alla prossima PE. |
| 17 | backend_main | sì | 4, 7 | A319-CHANGE-GYM: in change_gym la combinata va su test_max_hang_7s quando c'è la trave ma mancano i pesi (stamp solo dita, warning, niente lost_finger); docstring corretta<br>dry run: `gyms` e attrezzatura di casa in build_key_conflicts e _simulate_add<br>se approvati: home_equipment dallo stato nel router; motivo blocked:no_paired_slot in _generated_week_skip<br>test_a319 TestChangeGymOnATestDay (il test :1224 si ribalta) | Verificato replanner_v1.py:69-91, :1502, :1510-1530. Test aggiuntivo: combinata risolta senza pesi (dopo il passo 13) senza un «planned» falso per la trazione. |
| 18 | backend_main | sì | 17 | B369-P6(2) Opzione B: lettore `user_owned.gym_changes(plan)` (vince l'ultimo per data); planner_v2 applica sede e palestra agli slot ≥ today; slot di change_gym rispettato quando c'è<br>digest A300 identici per le settimane senza change_gym; passato identico | planner_v2: STOP. Attenzione: scrive locations sugli slot, quindi va verificato che la scelta resti guidata dall'attrezzatura. |
| 19 | backend_main | sì | 18 | B369-P6(1): ancore delle sessioni future dell'utente in PASS 1/1.5/2 (gap dita, gap hard, tetto hard); tolta `_regen_guard_warnings` se approvato<br>test b382/b400/a305/b390/b379 rilanciati, digest A300 | Sforzo L: ultimo passo del motore, rinviabile senza bloccare il resto. La corsa residua di B371 va in un brief a parte. |
| 20 | backend_main |  |  | BODY-PART-PICKER-NONDETERMINISM: `sorted(candidate_ids)`, seme da today + richiesta quando manca, esclusione di active:false nell'indice<br>test subprocess con PYTHONHASHSEED 0/1; preview == start | Verificato body_part_picker.py:503-547. `today` deve arrivare dal router. |
| 21 | backend_main |  |  | B-FORECAST-MIDDAY-STEP: selezione del giorno e dello step più vicino alle 12:00 locali (tz_offset), ripiego su dt_txt<br>test con fuso +2 e +3 | Correzione pura (A); nessun cambio di prodotto. |
| 22 | backend_main |  |  | A-CLIMB-CLIENT-ID passo 1: indice monotono (max+1) in free_session.py:277<br>test log 3, delete 2, log → 4; delete di un indice assente → 404 | Il passo 2 (client_id) resta aperto in roadmap. |
| 23 | frontend_branch_preview |  | 1 | Player che dicono la verità: guidedRowDone (Done oppure tutte le serie interne), completed_sets in unità reali (floor/2 per alt_sides), Done senza timer sulle custom/generated → serie prescritte (playerSession), player libreria completed = serie ≥ 1 e niente kg precompilato sulle righe saltate, riepilogo con le righe complete mostrate come fatte<br>vitest: feedback-items, b408, guided-alt-sides, b406/b414 player libreria, pagina Finish early<br>user_guide (player libreria), vocabulary | Stesso branch dei passi 24-26. Le REPEATER_TEST_IDS non devono essere dimezzate. Prova sulla PWA su iPhone. |
| 24 | frontend_branch_preview |  | 4 | ORPHAN client: api.ts riconosce il 409 session_not_in_plan; riquadro nel player con le scelte; replay che tiene la voce «da decidere» senza fermare la coda; refetchOnWindowFocus sulla settimana; controllo della sessione su Start con cache più vecchia di 60 s | Le scelte del riquadro secondo la domanda 4. Test b397 aggiornati. |
| 25 | frontend_branch_preview |  | 7, 9, 10, 17 | B414-4: TestExpiryCard sulla Today (da valid_until − 14, non chiudibile, «Fai il test» / «Posticipa la scadenza» con dry run e conferma)<br>RetestStatusCard: valido / prorogato fino al, motivi nuovi, Annulla rinvio; A320-FE superata<br>A319-FE: expandEquipment nel quick-add, testo di blocked:no_paired_slot e di skipped-tests-card<br>types.ts, api.ts, FRONTEND.md, user_guide | Errori dell'endpoint sempre mostrati, mai un salvataggio finto. |
| 26 | frontend_branch_preview |  | 13 | B372-FE-COPY: titolo «After an outdoor day»<br>B-GOAL-DEADLINE (1)(2): «Plan ends» da macrocycle.end_date, frase «la durata vale dal prossimo ciclo»<br>guide-content.tsx:408 back squat / goblet | Il punto 4 (guard di macrocycle.py) va rinviato a un brief con STOP. Poi preview Vercel, OK di Daniele e merge di tutto il branch (passi 23-26). |
| 27 | backend_main |  | 24 | ORPHAN (1): 409 session_not_in_plan su /feedback prima di ogni scrittura, con lo stesso predicato `_session_matches` su current_week_plan e week_plans[lunedì]; data non coperta, già done e B216 restano 200<br>test_a194 (graceful → 409), test_b369 _path_feedback_very_hard su una sessione vera, invarianza byte per byte<br>API_ENDPOINTS | Solo dopo il merge del passo 24, lasciando aggiornare le PWA. Non è nella lista ad alto rischio, ma blocca gli input del ciclo chiuso: suite completa. |
| 28 | docs |  | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 24, 25, 26, 27 | Giro finale sulla roadmap: chiudere B-RESOLVE-ERROR-UI (B293/0ac742b), END-OF-CYCLE accettata, «End-of-cycle reminder UX» ridotta, A320-FE superata, BW-PROGRESSION-FOLLOWUPS spezzata in un C (dip con le parallele, intensità del core) e un A con STOP (front lever), BODY-PART e A-CLIMB aggiornate<br>trim_roadmap --dry-run, lessons.md se serve, sync_status.py (commit di sync senza ID nel soggetto) | Ogni passo chiude già la propria riga in roadmap nello stesso commit: questo passo serve solo per le righe di più voci. |
| 29 | docs |  | 11, 15, 16, 25, 27 | Dopo il deploy, senza commit: scripts/athlete_context.py (STALE_CUSTOM_TAGS B395, chiavi della 02/11, valid_until 22/12); un eventuale riallineamento con remove_session + add_custom_session solo con dry run e OK di Daniele<br>opzionale: togliere test_reminder_skipped_until/postponed_to in prod con diff e OK<br>fuori repo: spuntare le righe della bug-inbox, runbook e regole.md di climb-coach | Nessuna scrittura in prod senza dry run (o diff completo prima/dopo) e OK esplicito. Sessioni passate mai toccate. |

## Conflitti fra aree

- **fatto-conteggio, events-feedback (B312), fatto-conteggio (B-ALTSIDES-SETS, CUSTOM-PLAYER-DONE-FLAG), max-hang-e-test-settimana** — Ci sono quattro definizioni di «fatto» sulla stessa riga: `stimulus.logged_entry_counts` (stimulus.py:334-349), `bw_ladders.ladder_row_done` (bw_ladders.py:224-249), la dose delle chiavi `MIN_FULL_SETS` in key_sessions_v1 e `load_score.compute_actual_load_score`, dove un flag assente vale «fatto» (load_score.py:89-108). Le proposte le toccano in modi diversi. row_done unifica le prime due. Come opzione propone di spostare anche load_score, proprio mentre B312 cambia quali exercise_instances legge lo stesso calcolo. B-ALTSIDES cambia l'unità di completed_sets (da serie interne a serie reali), su cui si basa la regola «completed:false + serie ≥ dose». CUSTOM-PLAYER-DONE-FLAG manda le serie prescritte quando si preme Done senza timer, cioè proprio l'alternativa B che fatto-conteggio scarta («inventa un conteggio»).
  - **Soluzione:** Un solo predicato `stimulus.row_done`, che `ladder_row_done` richiama. In B414 load_score NON passa al predicato: resta «flag assente = fatto» e B312 cambia solo la fonte delle exercise_instances (congelate). Le serie prescritte su Done senza timer valgono solo per custom/generated (estensione di B413), mai sul catalogo. Il rischio per il ciclo chiuso non cresce: anchored_load.py:1055-1057 e progression_v1.py:2763-2767 trattano già le serie assenti come «tutte le serie». Cambiano solo la dose delle chiavi e sets_done delle esposizioni. PLAYER-COMPLETED-FALSE e B-ALTSIDES vanno nello stesso commit frontend: il confronto «tutte le serie» si fa in unità interne, l'invio in unità reali (floor/2). MIN_FULL_SETS si conta per lato.
- **max-hang-e-test-settimana (A289), max-hang-e-test-settimana (REENTRY), scadenza-test (B414-1/2/3), replanner-residui (A319 opzionale)** — retest_policy.py viene modificato da cinque voci: A289 (`_axis_week_decision`, che legge il massimale al lunedì, retest_policy.py:1260), REENTRY opzione B (rimozione di `reentry_step` :395-456), B414-1 (`tested` = test reale a qualunque età, :306-307/:333-334), B414-2/3 (`_DECLINE_TRIGGERS` :683, trigger nuovi) e A319 (motivo `blocked:no_paired_slot` in `_generated_week_skip`). A289 dice che «la copertura (età < 90) resta letta al lunedì», ma con il modello A la copertura non dipende più dall'età.
  - **Soluzione:** Si fanno in sequenza, un commit e un file di test per voce: A289, poi REENTRY B, poi B414-1, poi B414-2, poi B414-3, poi A319. Con il modello A la nota di A289 sulla copertura non serve più, e la lettura al lunedì resta solo per `valid_until`/`expired`. Ogni passo rilancia test_a288/a289/a319/a320/b400 e i golden.
- **max-hang-e-test-settimana, power-endurance-gym, pin-e-fallback, scadenza-test** — I golden vengono rigenerati da passi diversi. c272: REENTRY B (6 chiavi con anchored.ramp), exercise_ordering, blocco PE, intensity_max. b413: GOBLET (6 chiavi daniele|legs), ordering, PE. a290_untested: blocco PE, cue PE, caso `stale_tests` del modello A. b364_untested: caso `stale_tests`. Power-endurance chiede di rigenerarli «una volta sola», ma i commit sono distinti e si deployano uno per volta.
  - **Soluzione:** Ogni commit rigenera solo i propri golden, dopo aver controllato che il diff grezzo tocchi solo le chiavi attese, e lo motiva nei *_cases.py come in C283/B406. I casi `stale_tests` NON vanno rigenerati: vanno tolti dai golden «non testati bit per bit» e diventano casi testati espliciti, perché con il modello A non sono più atleti non testati. I passi del resolver e del catalogo sono in serie (pin chain → GOBLET → ordering → PE) e non toccano mai gli stessi golden in parallelo.
- **power-endurance-gym (a)** — Il blocco unico `pe_main` cambia il seme di phase_anchor, che contiene il block_id (phase_anchor.py:659, `f"{ctx.phase_seed}|{session_id}|{block_id}"`). Per gli atleti testati in fase PE l'esercizio fisso della fase cambierebbe a metà fase. Rompe anche test_a290 (`_pick 'inline.pe_boulder'`) e test_b157, che cercano `pe_boulder`.
  - **Soluzione:** Il blocco unico mantiene `block_id: pe_boulder`. Senza vie il seme è lo stesso di oggi, quindi la scelta boulder non cambia; con le vie la preferenza soft Stage 2b (resolve_session.py:565-570) porta su route_intervals. In alternativa si accetta lo spostamento, che per Daniele è invisibile (nessuna PE pianificata fino al 06/12), dichiarandolo nel commit.
- **events-feedback (ORPHAN, B312, PLAYED-SESSION-READ-KEYS)** — feedback.py è modificato da tre voci: il passo 4b di B312 (:488-497), read_view con user_id (:681) e il 409 session_not_in_plan dopo `_snapshot_weeks` (:239). Il fix (2) di ORPHAN fa sollevare ValueError a `apply_events` mark_done, ma /feedback cattura ValueError come caso B216 (data fuori finestra, feedback.py:312 circa), ritenta su week_plans[lunedì], lo ingoia (:349-358) e poi scrive comunque la riga del completion log (:369-383). In questo modo l'orfano continua a essere scritto.
  - **Soluzione:** Serve un'eccezione dedicata (`SessionNotInPlan(ValueError)`): /events la trasforma in 422 e il ramo B216 la riconosce (niente retry). Fino al passo 409 il comportamento di /feedback resta quello di oggi. Il controllo 409 usa lo stesso predicato `_session_matches` (replanner_v1.py:179-184) su current_week_plan e week_plans[lunedì]. Ordine: B312, poi READ-KEYS, poi il raise in replanner, poi il frontend, poi il 409.
- **events-feedback (ORPHAN), replanner-residui (A319-CHANGE-GYM, B369-P6), power-endurance-gym (e)** — replanner_v1.py: il ramo mark_done di apply_events (:1268-1274) viene modificato da ORPHAN, il ramo change_gym (:1474-1559) da A319 e da B369-P6 (slot opzionale), `_regen_guard_warnings` (:649-664) da B369-P6. In più add_custom_session (:1613) consuma i tag nuovi di session_tags E2.
  - **Soluzione:** Un commit per voce, in quest'ordine: ORPHAN raise, poi A319, poi B369-P6(2), poi B369-P6(1). Ognuno con la suite completa, i digest A300 e il test delle sessioni passate identiche byte per byte.
- **fatto-conteggio (player), events-feedback (ORPHAN client), scadenza-test (B414-4), p3-piccoli (B372, B-GOAL-DEADLINE), pin-e-fallback (guide-content)** — Alcuni file frontend sono condivisi: feedback-items.ts e session-builder/[id]/play/page.tsx (tre voci dei player), today/page.tsx (banner ORPHAN e TestExpiryCard), retest-status-card.tsx (B414-4 e A319-FE, quest'ultimo non analizzato), session-card.tsx (ORPHAN 5), api.ts e types.ts. Contano anche i vincoli di rilascio: il 409 dopo il frontend, la card dopo il backend B414-1/2/3, i player dopo row_done.
  - **Soluzione:** Un solo branch frontend (brief/B414-…) con commit ordinati, una preview Vercel, la prova su desktop e su iPhone (PWA) e l'OK di Daniele prima del merge. I passi backend vanno su main prima di quel branch. Il 409 su /feedback va su main dopo il merge del frontend.
- **fatto-conteggio, p3-piccoli, scadenza-test** — Le aree leggono in modo diverso il messaggio di Daniele. fatto-conteggio pensa che «P2» siano i player. p3-piccoli pensa che «bisogna avviare un nuovo ciclo» riguardi B-GOAL-DEADLINE-DERIVED. scadenza-test lo riferisce a END-OF-CYCLE-STUCK-IN-DELOAD.
  - **Soluzione:** Il messaggio segue l'ordine delle sotto-voci di B413 in ROADMAP_CURRENT.md:14-16: LADDERS-TEST-EXPIRY, poi END-OF-CYCLE-STUCK-IN-DELOAD, poi REENTRY-MAX-HANG-SETS. Quindi «nuovo ciclo» = END-OF-CYCLE (accettato, si toccano solo i documenti). «P2» sono le voci 🟡 P2 della roadmap: A320-FE (:63), A319-FE (:89), A289-TEST-DONE-IN-WEEK (:93), più B-FRESHNESS (:141). Va spiegato in parole semplici (domanda 3). B-GOAL-DEADLINE resta tra i P3 («P3, vai»): solo testo della UI.
- **scadenza-test (B414-4), roadmap A320-FE** — A320-FE prevede «Not now / Postpone» sulla card. Daniele vuole solo due strade: posticipare la scadenza o fare il test. B414-4 toglie «Not now» dall'app.
  - **Soluzione:** A320-FE si chiude come superata da B414-4: in app solo «Fai il test», «Posticipa la scadenza» e «Annulla rinvio» come azione secondaria. Il rifiuto resta via API o coach. La riga va riscritta in roadmap nello stesso commit del frontend.
- **scadenza-test (B414-3), scadenza-test (B414-2)** — `kind: request` dentro `retest_declines` mette una richiesta in una lista di rifiuti. I lettori trattano ogni record come rifiuto o rinvio: righe RINVIATO di athlete_context (:1669-1680), `_active_postpone`, `plan_edit_removal`, `retest_declines.week_to_reopen` (:439), import di user.py:61. B414-2 aggiunge `previous_until` e il trigger `expiry`. Le due analisi si contraddicono: dicono «nessuna chiave nuova» ma segnano un cambio di schema.
  - **Soluzione:** È un cambio additivo dello schema di user_state (forma dei record) e richiede uno STOP esplicito. Ogni lettore deve filtrare per `kind`, con un test per lettore. In alternativa, «Fai il test» può aggiungere la sessione di test con /events (add_planned_session, dry run A294), senza record nuovi: domanda 2.
- **replanner-residui (A319-CHANGE-GYM), pin-e-fallback (B261-TEST-FALLBACK)** — Tutte e due gestiscono «combinata o 2RM senza pesi»: A319 a livello di piano (scambio con test_max_hang_7s e tolto `retest:pulling`), B261 nel resolver (blocco 2RM saltato). Se una combinata viene risolta senza pesi passando da quick-add o da un override, dopo B261 perde il blocco 2RM ma tiene il timbro `retest:pulling`. L'asse trazione risulterebbe «planned» e poi «missed».
  - **Soluzione:** Sono compatibili. Va aggiunto un test: una combinata risolta senza pesi tiene la sospensione e retest_status per la trazione non dice «planned». Il motivo `blocked:no_paired_slot` va solo nel ramo change_gym, come propone A319.
- **max-hang-e-test-settimana (REENTRY B), scadenza-test (B414-6), power-endurance-gym (d)** — `athlete_context.VERSION` (oggi a324.1, fissato in 5 test) va alzata due volte: per REENTRY B (via la chiave `ramp` dal JSON) e per B414-6 (righe nuove). INBOX-02-d cambia solo lo script.
  - **Soluzione:** VERSION si alza in ogni commit che cambia la forma del JSON (REENTRY, B414-6) e si aggiornano i 5 pin. Lo script (key_refs) va con B414-6.
- **scadenza-test (modello A), max-hang-e-test-settimana (REENTRY)** — I due cambi tolgono insieme due protezioni dopo un lungo stacco. Con il modello A un test di un anno fa rimette l'atleta nel regime testato. Senza il tetto di 5 serie e senza i fattori di rientro (già tolti da B413) il primo max hang parte dalla dose di catalogo sul massimale vecchio.
  - **Soluzione:** Si accetta, ma va dichiarato. La partenza a freddo (0,90 × massimale 7 s con i tetti di fase, anchored_load.py:68, :117-120, :646-660) è vicina al ramo legacy (intensità × baselines.hangboard, progression_v1.py:1357-1364). Le scale hanno R11. Prima della Fase 2 serve un conteggio in sola lettura degli utenti con un test reale di più di 90 giorni, più un test end-to-end oltre il 23/12.

## Claim smentiti o dubbi (verifica del critico)

- **INBOX-2026-11-05** — «Righe «nude» impossibili: «lo schema resolved_day_log_entry.v1 rende `completed` obbligatorio».»
  - Quello schema non si applica agli item di /feedback. load_score.py:89-90 gestisce apposta gli item senza `completed`, e il coach via API può mandarli. La garanzia viene solo dal conteggio prod (0 righe), non da un vincolo. Togliere la «riga nuda» da ladder_row_done può quindi cambiare righe future scritte da client non-app.
- **CUSTOM-PLAYER-DONE-FLAG** — «Mandare `prescription.sets` su Done senza timer per ogni riga custom «soddisfa la regola senza nuovi campi».»
  - Contraddice l'alternativa B scartata nella stessa area («inventa un conteggio che sembra misurato»). Il Done del player guidato non conta serie (guided/[date]/[sessionId]/page.tsx:478-527), quindi su una riga a tempo chiusa senza avviare il timer il conteggio è dichiarato, non misurato. Il ciclo chiuso non peggiora (serie assenti = tutte già oggi, anchored_load.py:1055-1057). Cambiano però la dose MIN_FULL_SETS e sets_done delle esposizioni. Si accetta solo su custom/generated, e va scritto in vocabulary.
- **INBOX-2026-11-04-ORPHAN** — «(2) `apply_events` mark_done: ValueError come mark_skipped → /events 422, e /feedback è coperto dal 409.»
  - Un ValueError generico sollevato dentro /feedback viene catturato dal ramo B216 (feedback.py, `except ValueError` dopo :311), ritentato e ingoiato (:349-358). Poi la riga del completion log viene scritta comunque, senza condizioni (:369-383). Servono un'eccezione dedicata e lo stesso predicato `_session_matches` (replanner_v1.py:179-184) nel controllo 409, altrimenti l'orfano resta possibile quando il controllo e apply_events non concordano.
- **A319-CHANGE-GYM / B369-P6-residui** — ««Filtro per attrezzatura: rispettato; l'Opzione B è pura attrezzatura.»»
  - change_gym decide anche sul luogo del catalogo: `location_ok = new_location in meta.get("location", ...)` (replanner_v1.py:1502), prima di guardare l'attrezzatura. L'Opzione B scrive `locations=[loc]` e `preferred_location` sugli slot. È un controllo per luogo più attrezzatura, già esistente. Il ripiego test_max_hang_7s a casa dipende dalla `location` del suo meta, non solo dalla trave.
- **B414-2-POSTPONE / B414-3-DO-TEST** — ««Nessuna chiave nuova in user_state … schema_version invariata»»
  - Il trigger `expiry`, `previous_until` e `kind: request` cambiano la forma dei record di `retest_declines` (retest_declines.py:155-180, retest_policy.py:683). Per CLAUDE.md è un cambio di schema di user_state: va fermato come alto rischio, e ogni lettore della lista va adattato.
- **INBOX-2026-11-02-a** — «Blocco unico `pe_main`: «le golden si rigenerano, le guardie restano soddisfatte».»
  - Non considera che il seme di phase_anchor contiene il block_id (phase_anchor.py:659): con un id nuovo cambia l'esercizio fisso della fase PE per gli atleti testati che sono a metà fase. Confermato invece il resto: i blocchi inline vengono risolti tutti (`required`/`priority` non sono letti dal resolver, l'unico `priority` in resolve_session.py:884 è delle palestre) e il filtro attrezzatura del blocco è soft (resolve_session.py:565-570).
- **B-GOAL-DEADLINE-DERIVED** — ««Bisogna avviare un nuovo ciclo, ovvio» sembra riferito a questo punto.»
  - È improbabile. La frase di Daniele segue l'ordine delle sotto-voci di B413 (ROADMAP_CURRENT.md:14-16): test che scade, poi END-OF-CYCLE-STUCK-IN-DELOAD, poi il tetto delle 5 serie. Il «nuovo ciclo» è END-OF-CYCLE (accettato).
- **B414-1-GATE** — ««Non è meno prudente di oggi: il ramo legacy prescriveva dallo stesso massimale vecchio.»»
  - Il ramo legacy legge `baselines.hangboard[0].max_total_load_kg` × intensità (progression_v1.py:1357-1364), non il test ufficiale: i due valori coincidono solo se la baseline è allineata al test. La conclusione resta plausibile (partenza ancorata 0,90 × massimale 7 s con i tetti di fase, anchored_load.py:68, :117-120), ma va verificata sugli utenti con un test vecchio.

## Mancanze

- A319-FE (P2, ROADMAP_CURRENT.md:89) non è stato analizzato. (1) quick-add-dialog.tsx filtra sull'attrezzatura grezza della palestra: al Bkl i test con `weight` non compaiono; fix: `expandEquipment`. (2) Il testo `blocked:no_paired_slot` in retest-status-card.tsx e skipped-tests-card.tsx è vecchio. È lo stesso file di B414-4: va nello stesso commit frontend.
- A320-FE (P2, ROADMAP_CURRENT.md:63) va chiuso o riscritto come superato da B414-4, senza «Not now» in app.
- Sessioni passate: week._auto_resolve risolve di nuovo ogni sessione che non ha `resolved` salvato, a qualunque data (week.py:143-156 salta solo done, skipped e _user_edited che hanno `resolved`). I commit di catalogo e resolver (PE, ordering, back squat, pin chain, intensity_max) cambiano quindi la prescrizione mostrata dei giorni passati pianificati e non fatti. Nel mirror ce n'è 1 (06/11 upper_push_arms_lunch). Il test di immutabilità deve coprire questo caso; valutare a parte (con STOP) di saltare le date < today.
- row_done cambia anche retest_policy.axis_confidence (count_exposures → counted_entries, retest_policy.py:380, :493): la confidenza calcolata del massimale e i testi di athlete_context e del coach possono cambiare retroattivamente. Le date dei test no: A319 la ha resa ininfluente (retest_policy.py:696-704).
- Lettori di `retest_declines` da adattare se arriva `kind: request`: athlete_context.py:1669-1680, retest_declines.week_to_reopen (:439), `_active_postpone`, plan_edit_removal, routers/user.py:61 (import), endpoint DELETE.
- Letture in sola lettura in prod (admin GET) prima della Fase 2: utenti con un test reale di più di 90 giorni (modello A), utenti con il bilanciere e slot pranzo (back squat), completamenti orfani e change_gym nelle settimane in hot degli altri utenti (il mirror contiene solo Daniele).
- Fuori repo, dopo il deploy: runbook di climb-coach (scrivere-in-app.md «Retest»: rinvio come proroga, «Fai il test»; /events 422 su mark_done; dry run con le palestre), regole.md:183 e il testo della bug-inbox sul tetto delle 5 serie, comando /custom-session. Spuntare le righe della bug-inbox (05/11, 04/11 orfano, 04/11 goblet, 04/11 4x4, 02/11 PE).
- Regressione del Coach KB (`--only` Q-03, Q-12, Q-20, Q-23, soglia 45/56) dopo le modifiche a prompt_builder e athlete_context (REENTRY ramp, B414-6).
- docs/API_ENDPOINTS.md: 409 session_not_in_plan su /feedback, 422 su mark_done di /events, trigger `expiry` e un eventuale endpoint di richiesta del test (riga a mano più conteggio con sync_status).
- feedback-items.ts:308-311: per REPEATER_TEST_IDS `completed_reps = completedSets`. Il dimezzamento alt_sides non deve toccare le reps di quei test; serve un test.
- Verifiche frontend: npx tsc, eslint, vitest e build nel worktree (con `npm ci` vero), prova della PWA su iPhone per i player e il replay offline.
- Dopo session_tags E2: B395, lanciare scripts/athlete_context.py per STALE_CUSTOM_TAGS (atteso vuoto); nessuno lo ha messo come passo esplicito.
- Prod opzionale per Daniele: `test_reminder_skipped_until=18` / `postponed_to=12` rimasti dal ciclo vecchio. Solo con diff e OK, e superflui se A246 azzera i campi a ogni nuovo ciclo.
- Effetto per gli altri utenti del modello A sulla programmazione: per chi ha un test scaduto, PASS 3a comincerà a piazzare da solo test della policy nelle settimane utili, e il promemoria delle 6 settimane sparisce (week.py:1003-1006). L'area lo dice solo in parte.

## Rischi sugli invarianti

- Sessioni passate immutabili: le correzioni in lettura (row_done, modello A, A289) non scrivono niente, ma cambiano lo stato derivato delle settimane passate (chiavi della 02/11, confidenza dei test). È ammesso, purché nessun campo salvato cambi. I commit di catalogo e resolver passano per `_auto_resolve` sulle sessioni passate senza `resolved` (week.py:143-156): test byte per byte su done, skipped e passate non fatte dopo ogni commit di catalogo.
- Sessioni passate: PLAYED-SESSION-READ-KEYS deve ripristinare `session_duration_seconds` dal gemello salvato e non deve mai cancellarlo. ORPHAN 409/422 e B312: nessun ricalcolo delle 51 sessioni parziali storiche.
- Determinismo: body_part_picker deve iterare `sorted(candidate_ids)` e il seme deve venire da `today` passato dal router, mai da un orologio dentro il motore. row_done, valid_until e done_in_week sono funzioni pure dello stato e di as_of. Il blocco PE con block_id nuovo sposta il seme md5 della fase (phase_anchor.py:659).
- Filtro per attrezzatura: change_gym decide anche sul luogo del meta (replanner_v1.py:1502) e l'Opzione B di B369-P6 scrive `locations`/`preferred_location` sugli slot. Il ripiego A319 deve controllare l'attrezzatura (la trave), non il luogo. back_squat → `barbell` è corretto (WEIGHT_SUBTYPES non espande mai verso barbell, equipment_utils.py:27-31). `dip` senza attrezzatura resta una violazione, fuori scope.
- Fontainebleau: nessuna voce tocca gradi boulder o la conversione.
- generate_macrocycle(from_phase="current"): nessun passo raccomandato lo chiama. Il punto 4 di B-GOAL-DEADLINE (macrocycle.py:59-69) va rinviato a uno STOP a parte. «Fai il test» con il ciclo finito apre start-new-cycle (from_phase None, già così).
- Lunedì: A289 e B414-2 calcolano la settimana con `_monday`. Il lettore gym_changes di B369-P6 lavora per data dentro la settimana del piano: nessun cambio a start_date.
- Schema di user_state: B414-2 (trigger expiry, previous_until) e B414-3 (kind request) cambiano la forma dei record di retest_declines: STOP. A-CLIMB passo 2 (client_id) e BW-FOLLOWUPS (3, 8) sono rinviati.
- Moduli ad alto rischio toccati indirettamente: planner_v2 PASS 2.7/3a (row_done, retest_decisions di A289 e del modello A), progression_v1 (input dei player, freshness_policy, eventuale partenza a freddo del back squat), resolve_session (pin chain, catalogo PE e gambe, ordering), replanner_v1 (mark_done, change_gym, tag delle custom). Dopo ogni passo: suite completa, digest A300, test_b413_end_to_end e test_b413_loads_never_lower.
- Ciclo chiuso: con le serie alt_sides in unità reali, chi si ferma a metà non progredisce più (voluto). Le righe saltate del player libreria non riscrivono più working_loads. Gli altri utenti vedono la progressione cambiare da subito.
- Rilascio: con il 409 su /feedback le voci di una PWA vecchia restano in «Waiting to sync» e fermano la coda (guided-pending-feedback.ts:223). Il backend va dopo il merge del frontend.

## Analisi per area

### p3-piccoli

#### BODY-PART-PICKER-NONDETERMINISM — Il generatore per distretti non è deterministico: né fra processi, né (in prod) fra preview e start

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** backend/engine/body_part_picker.py:503-505 costruisce `candidates` iterando un `set` di id stringa (`index.get(body_part, set()) - already_selected`): l'ordine dipende da PYTHONHASHSEED. Il jitter (:538 `rng = random.Random(seed)`, :541-547) viene estratto nell'ordine di iterazione, quindi a seed fisso cambia la scelta. Verificato: seed=42, stesso catalogo, PYTHONHASHSEED 0/1/2/3 → 4 output diversi su tutti gli 11 distretti. Aggravante non in roadmap: il frontend non manda MAI `seed` (frontend/src/app/(main)/body-part-picker/page.tsx:120-126 preview, :182-190 start; il router lo lascia None, backend/api/routers/body_part_picker.py:71, :145, :172) → `random.Random(None)` pesca entropia di sistema: due chiamate nello stesso processo danno esercizi diversi (verificato su `core`), e /start rigenera da zero (:165) → la sessione inserita non è quella mostrata in preview. Difetto adiacente: `build_body_part_index` (:320-345) filtra `is_library_only` ma non `active: false` → `max_hang_10s` (unico esercizio inattivo del catalogo) finisce nell'indice e viene scelto (~49 volte su 300 seed per fingers+hangboard). adhoc_builder (adhoc_builder.py:764-778) usa lo stesso indice ma ordina con tie-break per id (`_rank_key` :276-290) e filtra `_is_active` (:253-255): lì non c'è il bug.
- **Fix proposto:** (a) body_part_picker.py:504 iterare `sorted(candidate_ids)`. (b) In `generate_body_part_session` (:737), se `seed is None`, derivare un seed stabile da sha256(`today|body_parts|equipment_mode|gym_id`) → stessa richiesta stesso giorno = stessa sessione, preview == start, varietà fra giorni da data + recency. (c) In `build_body_part_index` saltare `ex.get("active") is False` accanto al controllo library-only. Opzionale: aggiungere il picker al golden statico C272 (c272_golden_cases.py:246-266), ora possibile.
- **Alternative:** Seed scelto dal client alla preview e riusato allo start (tocca frontend, preview Vercel). Oppure /start che accetta gli id della preview: più invasivo.
- **Raccomandazione:** Fare (a)+(b)+(c) insieme, solo backend. Vale la pena: costo piccolo, chiude una violazione del principio deterministico e un bug visibile (preview ≠ sessione). Per Daniele il valore è basso perché non usa il picker.
- **File:**
  - backend/engine/body_part_picker.py
  - backend/tests/test_body_part_picker.py
  - backend/tests/test_body_part_picker_api.py
  - backend/tests/c272_golden_cases.py (opzionale, golden)
- **Chiamanti e consumatori:**
  - generate_body_part_session ← backend/api/routers/body_part_picker.py:138 (POST /preview) e :165 (POST /start)
  - select_exercises_for_part ← body_part_picker.py:761 (unico chiamante di prod)
  - build_body_part_index ← body_part_picker.py:361 (classify_exercise_body_parts), :441 (get_available_body_parts → GET /options, conteggi), :503; backend/engine/adhoc_builder.py:764 (A252, non toccato da (a), (c) è già filtrato lì)
  - backend/tests/c272_golden_cases.py:257-266 (differenziale in-process, seed=7)
  - frontend/src/app/(main)/body-part-picker/page.tsx:120, :182 (nessuna modifica necessaria)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_body_part_picker.py:232 test_select_deterministic_with_seed (stesso processo: resta verde)
  - backend/tests/test_body_part_picker.py:479-600 test B224 (ruoli e conteggi, non id: restano verdi)
  - backend/tests/test_body_part_picker_api.py:120 test_preview_deterministic (seed 7, stesso processo)
  - backend/tests/test_c272_bw_ladders_catalog.py:325 test_body_part_picker_ignores_library_entries, :339 test_body_part_picker_still_finds_the_pre_c272_ids
  - backend/tests/test_a252_adhoc_muscle_focus.py:96, :113; backend/tests/test_exercises_v2.py:369 (appartenenza all'indice)
  - backend/tests/test_body_part_picker.py:180 conteggio core > 0 (con (c) fingers scende di 1, nessun test lo fissa)
- **Test da aggiungere:**
  - subprocess: stessa chiamata con PYTHONHASHSEED=0 e =1 → stessi id (picker e generate_body_part_session)
  - seed omesso: due generate_body_part_session uguali; API preview e start senza seed → stessi exercise_id
  - esercizio con active:false mai nell'indice né fra le scelte
  - (se approvato) picker nel golden statico C272
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Per tutti: la sessione per distretti diventa stabile per richiesta+giorno, la preview coincide con la sessione inserita, ripetere la preview non rimescola più, max_hang_10s non viene più proposto, /options conta un esercizio in meno su fingers. Nessun dato salvato cambia; le sessioni già inserite (anche passate) non vengono toccate.
- **Correzione dati in prod:** no (nel mirror di Daniele 0 sessioni build_kind=body_parts in hot + archivio)
- **Domande:**
  - Va bene un seed derivato da giorno+richiesta (niente rimescolamento ripetendo la preview)? Oppure vuoi un pulsante «Rimescola» (frontend) che passa un seed esplicito?
  - Includiamo il picker nel golden statico C272 ora che è deterministico?

#### B372-FE-COPY — Titolo della card post_outdoor ancora «Right after a big outdoor day»

**Verdetto:** confermato · **effort** XS · **rischio** basso · frontend sì · schema user_state no

- **Causa:** frontend/src/lib/week-alerts.ts:61 (non più :58) `post_outdoor: "Right after a big outdoor day"`. Da B372 il backend emette post_outdoor per ogni giornata outdoor che conta (backend/engine/guards_v1.py:493-511), e mette il motivo nel messaggio (`_OUTDOOR_WHY` :272-277: planned / logged hard / big load / no route log) e in `outdoor` (:280-281, :511). La guida utente dice già «After an outdoor day» (docs/user_guide_v1.md:786). Il tipo `GuardWarning` (frontend/src/lib/types.ts:303-313) non dichiara `outdoor`.
- **Fix proposto:** Minimo: week-alerts.ts:61 → "After an outdoor day". Opzionale: aggiungere `outdoor?: {date, reason, spot, load}` a GuardWarning e scegliere il titolo da `w.outdoor.reason` (es. «After a planned outdoor day»), più varianti di titolo per finger_gap / hard_back_to_back quando c'è `w.outdoor`. Consiglio il minimo.
- **Alternative:** Varianti di titolo da w.outdoor.reason (S, serve aggiornare il tipo).
- **Raccomandazione:** Sì, ma accodato ad altro lavoro frontend dello stesso brief: il costo vero è branch + preview Vercel + OK.
- **File:**
  - frontend/src/lib/week-alerts.ts
  - frontend/src/lib/__tests__/week-alerts.test.ts
- **Chiamanti e consumatori:**
  - guardTitle/guardAlert (week-alerts.ts:65, :99) ← frontend/src/components/training/session-card.tsx, day-card.tsx, week-alerts-card.tsx; frontend/src/app/(main)/today/page.tsx, week/page.tsx, settings/page.tsx; frontend/src/components/settings/availability-editor.tsx; frontend/src/lib/week-cache.ts
  - backend: guards_v1._post_outdoor (non cambia)
- **Test che fissano il comportamento attuale:**
  - nessuno: «Right after» / «big outdoor» non compare in nessun test frontend; i 27 test backend su post_outdoor riguardano codice e messaggio, non il titolo
- **Test da aggiungere:**
  - week-alerts.test.ts: guardAlert(code post_outdoor).title === "After an outdoor day"
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Solo testo: tutti vedono il nuovo titolo sulla card dell'alert. Nessun effetto sul motore.
- **Correzione dati in prod:** no
- **Domande:**
  - Basta il titolo unico «After an outdoor day» o vuoi le varianti per motivo (pianificata / dura / senza log)?

#### B-FORECAST-MIDDAY-STEP — Il forecast di un giorno usa lo step più vicino alle 12:00 UTC

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** backend/api/routers/weather.py:259-299 `_normalize_forecast`: filtra il giorno con `dt_txt.startswith(date)` (:283) e misura la distanza da mezzogiorno sull'ora di `dt_txt` (:286-290), entrambi in UTC; `tz_offset` è letto solo dopo (:292). Lo stesso file bucketizza già in ora locale altrove (hourly_steps :196, best_window :377-381). Effetto: con l'ora legale italiana (UTC+2) lo step scelto sono le 14:00 locali, a UTC+3 le 15:00, d'inverno in Italia le 13:00. Il valore va in `condition_band` → patch della strategia outdoor (backend/api/routers/outdoor.py:583-599 → outdoor_resolver DIMENSION_ORDER) e nel testo del coach (backend/coach/weather_tool.py:197, :119).
- **Fix proposto:** (A, correzione pura) Selezionare gli step del giorno con `time.gmtime(dt + tz_offset)` e scegliere quello più vicino alle 12:00 LOCALI; ripiegare su `dt_txt` quando `dt` manca (le fixture di test_weather_v1 hanno solo dt_txt e nessun city.timezone → tz 0, comportamento identico). (B, scelta di prodotto) Cambiare quale ora rappresenta la giornata (es. mediana degli step di luce 09-19 locali, o un'ora di arrampicata fissa): decide Daniele. Consiglio A adesso; B solo se lui lo vuole, visto che hourly e best_window coprono già la domanda «quando scalo».
- **Alternative:** Rappresentare la giornata con la mediana degli step di luce, o col peggiore (prudente) o col migliore (best_window).
- **Raccomandazione:** Fare A (correzione UTC → ora locale), che è un bug senza ambiguità; B solo su richiesta. Valore per Daniele medio-basso: conta per le uscite in falesia d'estate e all'estero.
- **File:**
  - backend/api/routers/weather.py
  - backend/tests/test_weather_v1.py (o un nuovo test con fuso)
- **Chiamanti e consumatori:**
  - cached_conditions (weather.py:579) ← GET /api/weather?date= (weather.py:622)
  - fetch_outdoor_conditions (weather.py:529) ← GET /api/outdoor/strategy con lat/lon/date (outdoor.py:587-591) ← frontend/src/app/(main)/outdoor/[date]/page.tsx:256-262
  - backend/coach/weather_tool.py:197 (testo per il coach)
  - le letture correnti (senza date) non passano da qui: card /today e condition-badge invariati
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_weather_v1.py:82 test_normalize_forecast_picks_midday_step (fixture UTC, resta verde col fallback)
  - backend/tests/test_weather_v1.py:89, :120
  - backend/tests/test_a275_weather_hourly.py:195 test_endpoint_forecast_by_date_carries_the_whole_day (asserisce hourly/sunset, non lo step del riassunto)
- **Test da aggiungere:**
  - fixture con city.timezone=7200: il riassunto prende lo step delle 11:00 locali (09 UTC), non le 14:00
  - fixture UTC+3 (Kalymnos): filtro del giorno in ora locale, coerente con hourly_steps
  - fallback su dt_txt quando manca dt
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Solo per previsioni di un giorno futuro: fuori da UTC lo step rappresentativo si sposta verso il mezzogiorno locale (Italia d'estate 14:00 → 11:00, d'inverno invariato; UTC+3 15:00 → 12:00). Può cambiare condition_band e quindi le patch del testo strategia outdoor. Nulla di salvato cambia; i log outdoor passati conservano le condizioni già scritte.
- **Correzione dati in prod:** no
- **Domande:**
  - Quale ora rappresenta una giornata in falesia: mezzogiorno locale (correzione pura) o altro (mediana delle ore di luce, pomeriggio)?

#### B-RESOLVE-ERROR-UI — resolve_error non letto dal client

**Verdetto:** gia_risolto · **effort** XS · **rischio** basso · frontend no · schema user_state no

- **Causa:** Già chiuso da B293 (commit 0ac742b, 2026-07-21, «consuma finalmente il resolve_error di A245 E-3/B17»): frontend/src/lib/session-resolution.ts:29-40 distingue ok / empty / error; frontend/src/components/training/session-card.tsx:505-510 lo usa, Done/Skip disabilitati se non `ok`; :1083-1113 stato esplicito «This session couldn't be prepared» con Retry (refetch della settimana = nuova risoluzione). Il backend lo scrive in backend/api/routers/week.py:219/237 e replanner.py:275/290 e lo pulisce in plan_revision.py:441. La riga della roadmap (docs/ROADMAP_CURRENT.md:192) è rimasta aperta per errore.
- **Fix proposto:** Nessun codice. Chiudere la riga B-RESOLVE-ERROR-UI in docs/ROADMAP_CURRENT.md (✅, rimando a B293 / 0ac742b).
- **Raccomandazione:** Chiudere la riga della roadmap nello stesso commit del brief.
- **File:**
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - frontend/src/lib/session-resolution.ts (sessionResolutionState)
  - frontend/src/components/training/session-card.tsx:505, :1091
  - backend/api/routers/week.py:219, :237; backend/api/routers/replanner.py:275, :290; backend/api/plan_revision.py:441
- **Test che fissano il comportamento attuale:**
  - frontend/src/lib/__tests__/session-resolution.test.ts:22, :38
  - backend/tests/test_a245_resolve_error_marker.py:45-93
  - backend/tests/test_b399_week_roundtrips.py:325
- **Test da aggiungere:**
  - —
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Nessuno (solo documentazione).
- **Correzione dati in prod:** no (nel mirror di Daniele nessuna sessione con resolve_error)

#### B-GOAL-DEADLINE-DERIVED — goal.deadline è una data derivata con un nome da scadenza; lo slider della durata non tocca il ciclo in corso

**Verdetto:** parziale · **effort** S · **rischio** basso · frontend sì · schema user_state no

- **Causa:** Il client deriva la «deadline» da oggi + N settimane (frontend/src/components/shared/deadline-weeks-selector.tsx:82; goal-editor.tsx:155-158; onboarding/goals/page.tsx:257; start-new-macrocycle-dialog.tsx:252). La rigenerazione incrementale ignora la durata nuova: backend/api/routers/macrocycle.py:91 `total_weeks = old_mc.get("total_weeks", 12)` (il client lo sa, settings/page.tsx:470-478). /settings mostra «Deadline» da goal.deadline (settings/page.tsx:659-668). Lo stato attuale di Daniele però è coerente: deadline = macrocycle.end_date (stesso giorno di dicembre); restano goal.total_weeks 12 contro macrocycle.total_weeks 13. Problema latente non in roadmap: macrocycle.py:59-69 rifiuta con 400 «Goal deadline is in the past» ANCHE la rigenerazione incrementale; con «Start new cycle» il ciclo parte il lunedì successivo (macrocycle_v1.py:1074-1099) mentre la deadline è oggi + N×7, quindi la deadline cade fino a 6 giorni prima di end_date: negli ultimi giorni del ciclo un cambio di attrezzatura che chiede la rigenerazione risponde 400. Altri lettori: coach (backend/coach/prompt_builder.py:372 «deadline …»), athlete_context.py:252 e :1616 («entro <deadline>»), goal_snapshot nel macrociclo (macrocycle_v1.py:863).
- **Fix proposto:** Basta il testo della UI, senza rinominare (rinominare = cambio dello schema di user_state → alto rischio, non vale la pena). (1) /settings: riga «Plan ends» letta da macrocycle.end_date invece di goal.deadline. (2) Goal editor: frase esplicita «Changing the duration applies to the next cycle — use Start new cycle», oppure togliere lo slider dal goal editor e lasciarlo solo in Start new cycle. (3) Opzionale backend: nel coach/athlete_context usare end_date come «fine piano». (4) Opzionale, ad alto rischio: in macrocycle.py:59-69 applicare il controllo sulla deadline passata solo alla rigenerazione completa (from_phase None); la chiamata a generate_macrocycle non cambia e from_phase="current" resta.
- **Alternative:** Rinominare in plan_end_date: cambio di schema di user_state + migrazione → alto rischio, nessun beneficio in più per l'atleta.
- **Raccomandazione:** Solo testo UI (1)+(2), più (3) se costa poco. Il punto 4 è il solo che cambia un comportamento: da valutare con STOP. Valore per Daniele basso; per lui la scadenza oggi coincide con la fine del ciclo.
- **File:**
  - frontend/src/app/(main)/settings/page.tsx
  - frontend/src/components/settings/goal-editor.tsx
  - docs/user_guide_v1.md
  - (opzionale) backend/coach/prompt_builder.py, backend/engine/athlete_context.py
  - (opzionale, alto rischio) backend/api/routers/macrocycle.py
- **Chiamanti e consumatori:**
  - goal.deadline scritto da: goal-editor.tsx:158, onboarding/goals/page.tsx:257, start-new-macrocycle-dialog.tsx:252 → backend/api/routers/macrocycle.py:235 (start-new-cycle), PUT /api/state
  - goal.deadline letto da: macrocycle.py:59-69 (guard), :185-193 (validazione start-new-cycle), macrocycle_v1.py:863 (snapshot), athlete_context.py:252/:1616, coach/prompt_builder.py:372, scripts/extract_audit_snapshot.py:755, settings/page.tsx:659-668, deadlineIsoToWeeks in goal-editor.tsx:94 e start-new-macrocycle-dialog.tsx:178
  - generate_macrocycle ← macrocycle.py:98 (generate, incrementale/completa), :282 (start-new-cycle, from_phase=None), onboarding.py:506/:514
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b357_fixture_date_timebomb.py (la fixture non deve portare una deadline che scade: dipende dal guard)
  - backend/tests/test_b119_start_date_monday.py:157 (cita il 400 sulla deadline passata)
  - backend/tests/test_start_new_macrocycle.py:384 test_deadline_too_soon_returns_400, :391 test_invalid_deadline_format_returns_400
- **Test da aggiungere:**
  - vitest: la riga di /settings mostra macrocycle.end_date
  - (se si fa il punto 4) pytest: generate con from_phase="current" e goal.deadline nel passato → 200, start_date lunedì invariata, sessioni passate identiche; la rigenerazione completa con deadline passata resta 400
- **Moduli ad alto rischio:**
  - backend/api/routers/macrocycle.py (solo se si fa il punto 4: chiama generate_macrocycle)
- **Effetto sugli altri utenti:** UI: tutti vedono la fine reale del piano al posto di una «deadline» derivata, e sanno che la durata cambia solo col ciclo nuovo. Col punto 4: la rigenerazione incrementale non fallisce più negli ultimi giorni di un ciclo con deadline derivata già passata.
- **Correzione dati in prod:** no (per Daniele deadline = end_date; il disallineamento 12 contro 13 di total_weeks è solo cosmetico e non serve correggerlo)
- **Domande:**
  - La tua frase «bisogna avviare un nuovo ciclo, ovvio» si riferisce a questo punto? Se sì: la durata cambia solo con Start new cycle, e la UI lo deve dire. Togliamo lo slider dal goal editor o lo lasciamo con la frase?
  - Facciamo anche il punto 4 (guard solo sulla rigenerazione completa)? Tocca il router che chiama generate_macrocycle → STOP dedicato.

#### BW-PROGRESSION-FOLLOWUPS — Pezzi della spec BW non fatti in A298: 12 sottopunti, tutti ancora aperti

**Verdetto:** confermato · **effort** L · **rischio** alto · frontend sì · schema user_state sì

- **Causa:** Verificato su origin/main: (1) `dose_for` (backend/engine/bw_progression.py:403) è chiamato solo dentro bw_progression.py; adhoc_builder.py e coach/session_composer.py non importano bw_progression e non scrivono mai `progress_mode: 'ladder'` (unici produttori: models.py:535, custom_session.py:136); resolve_custom_ladder_rows (:1088-1152) dà la dose solo alle righe ladder. (2) Nessun budget core né pavimento d'intensità (nessun riferimento a posterior_chain o hollow_plank nel motore). (3) resolve_session.py:353-358 ZONE_TO_CONTRAINDICATION senza lower_back/knee; has_lower_back_zone torna sempre False (bw_progression.py:235-240). (4) Catalogo: side_plank medium, nordic_curl medium, `dip` con equipment_required [] (nessuna chiave dip bars: viene proposto anche senza parallele, contro il filtro sull'attrezzatura), band e resistance_band entrambe in uso, copenhagen_adductor_plank / pistol_squat_progression attivi, core_l_sit pattern anti_extension. (5) Nessuna UI: il frontend usa solo POST /promotion (api.ts:734), PUT /api/bw-progression/{family} (routers/bw_progression.py:61) nessuno lo chiama. (6) Nessuna regola sul front lever in planner_v2 / guards_v1. (7) FROZEN_PHASES = {deload} (bw_progression.py:72), il taper A281 (macrocycle_v1.py:960) è ignorato. (8) Posizioni «non ancora tracciate» (bw_progression.py:35), nessun B1/B2. (9) Nessun test_front_lever_* nel catalogo. (10) Handoff R7: solo messaggio con start_kg (:755-776), working_loads non inizializzato. (11) single_leg_squat terminal {kind: load, load_step_kg_lower: 5} senza tetto. (12) technique_next (:1481) non usa B1. Stato di Daniele (mirror): 11 famiglie BW, front_lever al livello 3, livelli tecnici vuoti, nessuna limitazione.
- **Fix proposto:** Non farli in questo brief: è un ombrello da L con moduli ad alto rischio. Spezzare. Brief C (con OK sul golden C272): sottopunto (4), con priorità sulla chiave di attrezzatura delle parallele per `dip` (aggiungere la chiave al vocabolario equipment + equipment_required) e sulle intensità side_plank/nordic_curl. Brief A con STOP: (6) regole FL nel planner, perché Daniele allena il FL al livello 3. Poi, se servono: (1) dose nel builder/composer, (5) UI dei livelli. In attesa: (2), (3), (7)-(12).
- **Alternative:** Lasciare tutto in roadmap e fare solo la chiave di attrezzatura del dip, l'unico difetto che viola un principio (filtro per attrezzatura).
- **Raccomandazione:** Ancora utili per Daniele: (6) regole FL (FL al livello 3), (4) dip + intensità del core, poi (8)/(12) se inizierà a registrare piedi e posizioni (oggi i livelli tecnici sono vuoti). Poco utili adesso: (3), (9), (10), (11). (5) è comodo ma lui oggi imposta i livelli con user_edit. Fuori da questo brief P3.
- **File:**
  - (4) backend/catalog/exercises/v1/exercises.json, backend/engine/equipment_utils.py, backend/engine/body_part_picker.py (liste), frontend equipment picker (onboarding/settings), backend/tests/fixtures golden C272
  - (6) backend/engine/planner_v2.py, backend/engine/guards_v1.py
  - (1) backend/engine/adhoc_builder.py, backend/coach/session_composer.py
  - (5) frontend/src/app/(main)/settings/page.tsx + nuovo componente
  - (3) backend/engine/resolve_session.py, frontend limitazioni
  - (7)(8)(10)(11)(12) backend/engine/bw_progression.py, backend/catalog/progressions/v1/bw_ladders.json
- **Chiamanti e consumatori:**
  - bw_progression ← progression_v1.py:2992, :3451 (apply_feedback); resolve_session.py:1408, 1557, 1597, 1640, 1685, 1924, 2198; athlete_context.py:1075; routers feedback.py:418, replanner.py:322, custom_session.py:26, week.py:249, bw_progression.py:27
  - bw_ladders ← athlete_context.py:56, key_sessions_v1.py:770, coach/athlete_block.py:35, api/ladder_archive.py:43, measured_feedback.py:114
  - catalogo esercizi ← resolve_session, adhoc_builder, session_composer.build_pool, body_part_picker, golden C272
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_a298_bw_progression.py (dose_for :86, :91, :233, :273, :281)
  - backend/tests/test_b413_ladder_rules.py:270, :295
  - backend/tests/test_c272_bw_ladders_catalog.py:339 (pistol_squat_progression e copenhagen_adductor_plank devono stare nell'indice del picker: si rompe con (4))
  - backend/tests/c272_golden_cases.py + fixture other_engines (golden statico: cambia con (2) e (4))
- **Test da aggiungere:**
  - (4) dip mai proposto senza la chiave delle parallele; golden C272 rigenerato con diff verificato
  - (6) FL max 1 a settimana in performance; famiglie appese mai nelle 24 h prima di limit/strength_long; invariante sessioni passate immutabili dopo la rigenerazione
- **Moduli ad alto rischio:**
  - backend/engine/planner_v2.py (6)
  - backend/engine/resolve_session.py (2, 3)
  - backend/engine/progression_v1.py / bw_progression.py, ciclo chiuso (7, 8, 10, 11, 12)
  - backend/engine/macrocycle_v1.py (7: legge il taper A281)
  - schema user_state (3: nuova zona di limitazione; 8: posizioni tecniche)
- **Effetto sugli altri utenti:** (2) e (4) cambiano la selezione degli esercizi per tutti (golden). (6) sposta il planner per chi ha il FL. (1) dà la dose di livello alle custom del coach in-app per chi ha voci BW. Gli altri sottopunti valgono solo per chi usa quelle scale.
- **Correzione dati in prod:** no
- **Domande:**
  - Confermi di spezzare: brief C per le correzioni di catalogo (dip con le parallele per primo) e brief A con STOP per le regole del front lever?
  - Le parallele per i dip ce le hai a casa? Serve per decidere la chiave di attrezzatura e come migrarla nelle tue palestre/casa (dato in user_state.equipment).

#### A-CLIMB-CLIENT-ID — Identità delle climb di una free session: indice che si ripete dopo un delete e indice provvisorio offline

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend sì · schema user_state sì

- **Causa:** Peggio di quanto dice la roadmap, anche online: backend/api/routers/free_session.py:277 assegna `index = len(climbs) + 1` e :452 cancella tutte le righe con quell'indice. Dopo un delete l'indice successivo si ripete: con le climb 1,2,3, si cancella la 2, la nuova prende 3 → due righe con indice 3, e cancellarne una le cancella entrambe, sul server e in UI (climb-logger.tsx:279 filtra per index; :503 lo usa anche come key React). Offline: indice provvisorio = max+1 partendo da -1 (climb-logger.tsx:225), quindi la prima climb offline è #0 contro #1 del server; nessun refetch riallinea (la lista viene solo dalla bozza locale, :93-103) → DELETE 404 → rollback, la climb non si può cancellare. Il replay dell'outbox (frontend/src/lib/outbox.ts:127-132) non è idempotente: se la richiesta era arrivata ma la risposta si è persa, la climb risulta due volte. L'outdoor live usa indici posizionali e restituisce la lista intera (outdoor.py:722-760), lì il problema non c'è. Mirror: 12 free session di Daniele, nessun indice duplicato.
- **Fix proposto:** Passo 1 (backend, XS, consigliato): free_session.py:277 → `index = max((c.get("index") or 0) for c in climbs, default=0) + 1`: indice monotono, niente collisioni dopo un delete; i test esistenti (1, 2 consecutivi) restano verdi. Passo 2 (il «fix vero» della roadmap, S, opzionale): `client_id` facoltativo in FreeSessionLogClimbRequest (models.py:492), salvato sulla climb, replay deduplicato per client_id, DELETE che accetta client_id; climb-logger genera crypto.randomUUID(), lo usa come key e per il delete, e se cancelli una climb ancora in coda la toglie dall'outbox.
- **Alternative:** Indice posizionale con la lista intera restituita, come l'outdoor live (cambia il contratto della risposta).
- **Raccomandazione:** Fare subito il passo 1 (XS, solo backend, chiude il bug online). Il passo 2 solo se Daniele logga offline; per un tool personale con 12 free session in 7 mesi vale poco. Nota: i flag frontend/schema si riferiscono al passo 2; il passo 1 non tocca né frontend né schema.
- **File:**
  - backend/api/routers/free_session.py
  - backend/tests/test_free_session.py
  - (passo 2) backend/api/models.py, frontend/src/components/free-session/climb-logger.tsx, frontend/src/lib/api.ts, frontend/src/lib/outbox.ts, docs/API_ENDPOINTS.md
- **Chiamanti e consumatori:**
  - POST /api/free-session/{id}/log-climb (free_session.py:246) ← api.ts:985 logFreeClimb ← climb-logger.tsx:218 e replay outbox.ts:127-132
  - DELETE /api/free-session/{id}/climb/{climb_index} (free_session.py:438) ← api.ts:997 deleteFreeClimb ← climb-logger.tsx:281
  - climb.index letto solo in free_session.py:452 e climb-logger.tsx:279, :503-542 (nessun consumatore nel motore)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_free_session.py:561 test_log_valid_climb (index 1), :571 test_log_multiple_climbs (1, 2): compatibili col passo 1
  - nessun test sul DELETE delle climb di una free session (né backend né frontend)
- **Test da aggiungere:**
  - log 3 → delete 2 → log → indice 4 (non 3); delete 4 lascia 1 e 3
  - delete di un indice assente → 404
  - (passo 2) replay con lo stesso client_id → una sola climb; delete per client_id
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Passo 1: per tutti gli indici delle nuove climb non si ripetono più dopo un delete; le sessioni finite e quelle passate non vengono toccate (gli endpoint rifiutano le sessioni finite). Passo 2: campo facoltativo in più dentro free_sessions[].climbs[] (aggiunta, le climb vecchie restano valide), replay offline senza doppioni.
- **Correzione dati in prod:** no (mirror: nessun indice duplicato nelle 12 free session)
- **Domande:**
  - Logghi spesso climb offline in palestra? Se no basta il passo 1 (solo backend, nessuna preview).

**Note trasversali (analisi:p3-piccoli):** Analisi in sola lettura sul worktree climb-agent-b414 (4d53bf5). Nessun file modificato e nessun pytest eseguito. Gli snippet Python girano con STORAGE_BACKEND=file, fanno solo letture e sono in /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/bpp.py.

Sintesi: 4 confermati (1, 2, 3, 7), 1 già risolto (4, chiuso da B293 commit 0ac742b: va solo chiusa la riga della roadmap), 1 parziale (5), 1 ombrello da spezzare (6). Due difetti che la roadmap non registra: (a) il picker per distretti in prod non riceve mai un seed, quindi la preview non coincide con la sessione inserita, e propone l'esercizio inattivo max_hang_10s; (b) l'indice delle climb di una free session si ripete dopo un delete anche online, e allora un delete ne cancella due.

Rischio: nessuna delle correzioni consigliate per 1, 2, 3, 4, 5(UI), 7(passo 1) tocca planner_v2, replanner_v1, macrocycle_v1, resolve_session, progression_v1, closed_loop_v1 o lo schema di user_state. Le eccezioni hanno bisogno di uno STOP a parte: il punto 4 opzionale di B-GOAL-DEADLINE-DERIVED (router che chiama generate_macrocycle; from_phase="current" va mantenuto e start_date resta lunedì) e quasi tutto BW-PROGRESSION-FOLLOWUPS. Invarianti verificati sulle correzioni consigliate: nessuna rigenera il piano né modifica sessioni passate. Il determinismo migliora (punto 1). Il punto 3 non tocca i dati salvati. Fontainebleau e il filtro per attrezzatura non sono toccati; l'unica violazione del filtro per attrezzatura trovata è `dip` senza attrezzatura richiesta, sottopunto (4) di BW-FOLLOWUPS.

Flusso dei branch: 2 e 5 toccano frontend/, quindi tutto il brief B414 va su branch con preview Vercel e OK di Daniele prima del merge. Se si vuole che 1, 3 e 7 (passo 1) arrivino subito, vanno in un commit solo backend separato.

Documenti da allineare nello stesso brief: in ROADMAP_CURRENT chiudere B-RESOLVE-ERROR-UI e le righe fatte, aggiornare BODY-PART-PICKER-NONDETERMINISM con i difetti scoperti e A-CLIMB-CLIENT-ID (passo 1 fatto, passo 2 aperto); user_guide_v1 per la riga «Plan ends» e la durata che vale dal ciclo successivo; API_ENDPOINTS solo se cambia il DELETE delle climb.

Sulla richiesta di Daniele: «P3, vai» vale come via libera di principio per questi punti, non per i moduli ad alto rischio. «Bisogna avviare un nuovo ciclo, ovvio» sembra riferito a B-GOAL-DEADLINE-DERIVED (la durata cambia solo con Start new cycle): va confermato. Tre punti del messaggio sono fuori dalla mia area: la scadenza dei test da posticipare senza mai azzerare, il tetto di 5 serie di max hang da togliere, il P2 non chiaro.

Nota minore, non è un bug: i DELETE di free_session (free_session.py:438, :462) non hanno require_active_subscription, a differenza dei POST. Cancellare i propri dati da abbonamento scaduto è accettabile.

### max-hang-e-test-settimana

#### REENTRY-MAX-HANG-SETS — Togliere il tetto di 5 serie di max hang nelle prime 2 esposizioni dopo uno stacco (decisione di Daniele del 2026-11-07)

**Verdetto:** decisione_di_design · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** Il tetto è una regola di prescrizione, non un bug. backend/engine/anchored_load.py:61-64 `REENTRY_MAX_HANG_SETS = 5`; :663-666 per i soli max hang, se `ramp["in_reentry"]` e `n_sets > 5`, abbassa `n_sets` a 5 e aggiunge la guardia `{guard: reentry_sets, sets: 5}`. `ramp` viene da `ramp_for` (:366-397), che chiama `retest_policy.reentry_step` (retest_policy.py:398-456: `in_reentry = n <= REENTRY_EXPOSURES` (2), stacco `REENTRY_GAP_D` 14 gg, :79-87). La stessa regola è copiata in adhoc_builder.py:27 (import) e :388-395 (con energia «high» le serie diventano min(6, 5+1) = 6, poi il tetto le riporta a 5) e in resolve_custom_exercises, anchored_load.py:907-914 (abbassa `sets` e scrive `stored_sets` sulla copia letta). Dopo B413 è l'unico consumatore di `reentry_step` (vocabulary_v1.md:1159, ROADMAP_CURRENT.md:21). Verificato in sola lettura (fixture di test_b413): rientro n=1, gap 18 gg; con sets=6 o 8 il risultato è 5 serie, guardia reentry_sets, totale 104,0 e tetto 104,0, gli stessi numeri di sets=5. Il carico non dipende da n_sets per gli hang (tetto a :646-648): il tetto agisce solo su `sets`, `rep_scheme` e `guards`. Nelle sessioni pianificate non scatta mai: il catalogo prescrive 5 serie (exercises.json max_hang_5s/7s, prescription_defaults.sets=5) e la PE 3 (templates/v1/finger_max_strength.json:89). Scatta solo su custom e ad-hoc con più di 5 serie.
- **Evidenza:** Snippet in sola lettura (fixture di test_b413, nessuna scrittura, git status pulito). sets None/5 → 5x7s, totale 104,0, nessuna guardia. sets 6/8 → 5x7s, totale 104,0, guardia reentry_sets. Custom a 6 serie letta il 02/11: sets 5, stored_sets 6. Trazione con sets=6: 6 serie, nessuna guardia. Mirror prod del 07/11: 4 anchored.ramp con factor, nessun in_reentry, nessun reentry_sets.
- **Fix proposto:** Opzione B (raccomandata, pulizia completa): (1) anchored_load.py: togliere `REENTRY_MAX_HANG_SETS` (:61-64 e __all__ :1312), il ramo :663-666, `ramp_for` (:366-397 e __all__ :1314) con la chiamata :588, la chiave `ramp` dal payload (:739-740), da `anchor_summary` (:786) e dal docstring (:571); da resolve_custom_exercises togliere l'abbassamento delle serie e `stored_sets` (:907-914, docstring :856-862). `_test_dates` resta perché la usano :527 e scripts/migrate_b364.py:152. (2) adhoc_builder.py: togliere l'import di REENTRY_MAX_HANG_SETS (:27) e il blocco :388-395. (3) retest_policy.py: togliere `reentry_step` (:395-456), `REENTRY_EXPOSURES` e `REENTRY_GAP_D` (:79-87, usati solo lì e in ramp_for) e le voci di __all__ (:1807/:1812); aggiornare il docstring del modulo (:24-27). `stimulus.exposure_dates` resta (la usa phase_anchor.py:485/492). (4) athlete_context.py: togliere la chiave `ramp` della riga ancorata (:324) e i commenti :1240-1241 e :1927-1929. (5) Documenti: ENGINE_ARCHITECTURE.md:669-672, vocabulary_v1.md:644/656/1159, user_guide_v1.md:472 (togliere «During a comeback, max hangs are also capped at 5 sets»), docs/training/athlete_plan.md:55, ROADMAP_CURRENT.md:21 → ✅. Opzione A (minima): solo i punti 1 e 2 sul tetto, `ramp` resta nel payload come dato informativo; nessun golden cambia, ma `reentry_step` e `ramp_for` restano codice che nessuno legge. NUMERO DI SERIE DOPO UNO STACCO = lo stesso di sempre. Pianificate: 5 (PE 3, scarico A312 con una serie in meno). Custom: le serie salvate, anche quelle del composer LLM (1-20, session_composer.py:72/:362). Ad-hoc deterministico: 5 con energia normale, 4 con «low», 6 con «high» (adhoc_builder.py:383-386). CAMPI LEGACY da leggere senza migrazione: le prescrizioni salvate (week_plans, week_archive, prescrizioni congelate al «fatto» di B413/D2) hanno `suggested.anchored.ramp` = {n, factor, gap_days, source} (prima di B413) o {n, gap_days, in_reentry, source} (dopo), e forse la guardia `reentry_sets`. Il ramo `ramp.factor` in frontend/src/lib/anchored-load.ts:78-86 RESTA, perché scrive la nota del giorno sulle sessioni passate. I codici delle guardie non sono mostrati dal frontend. Sul mirror del 07/11: 4 `anchored.ramp` con `factor` (3 in week_plans, 1 in archivio), 0 `in_reentry`, 0 `reentry_sets`, 0 `stored_sets`. Il campo `stored_sets` resta: lo scrivono anche il deload A312 (resolve_session.py:87-105) e le scale A298.
- **Alternative:** A (minima, XS): solo il tetto, ramp resta informativo. Terza via, non raccomandata: un tetto unico di serie per i max hang valido sempre (es. 6), indipendente dallo stacco. Contraddice la decisione di Daniele.
- **Raccomandazione:** Opzione B in un commit separato del brief: togliere il tetto e il codice che ne dipende (reentry_step, ramp_for, ramp). Il ramo frontend `ramp.factor` resta per le sessioni passate. Nessun file frontend: il commento obsoleto in types.ts:1203 si lascia al prossimo brief frontend, per non chiedere una preview Vercel per un commento.
- **File:**
  - backend/engine/anchored_load.py
  - backend/engine/adhoc_builder.py
  - backend/engine/retest_policy.py (solo opzione B)
  - backend/engine/athlete_context.py (solo opzione B)
  - backend/tests/test_b413_loads_never_lower.py
  - backend/tests/test_b364_official_max_vs_working_load.py
  - backend/tests/test_a288_retest_policy.py (solo opzione B)
  - backend/tests/c272_golden_cases.py + backend/tests/fixtures/c272_resolver_golden.json (solo opzione B: 6 chiavi)
  - docs/ENGINE_ARCHITECTURE.md
  - docs/vocabulary_v1.md
  - docs/user_guide_v1.md
  - docs/training/athlete_plan.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - Chiamate di anchored_load (tutte ricevono `sets`, `rep_scheme` e `guards`): progression_v1.py:1681 (inject_targets, sessioni pianificate), body_part_picker.py:619, adhoc_prescription.py:144 e :218, coach/session_composer.py:466 (usa solo il carico), coach/prompt_builder.py:348 (rep_scheme nel prompt), athlete_context.py:303 (_anchors, sets di default, il tetto non scatta mai) e :2248 (heavy_pull_pct, solo trazioni), key_sessions_v1.py:462 (legge solo `floor`), anchored_load.py:894 (resolve_custom_exercises: GET /api/custom-session/{id}?date= e GET /api/week) e :1156-1184 (letture di riferimento del feedback, usano solo `total`)
  - Lettori di `in_reentry`: anchored_load.py:664 e adhoc_builder.py:393. Lettori di `ramp`: athlete_context.py:324 (JSON di scripts/athlete_context.py) e frontend/src/lib/anchored-load.ts:81 (solo `factor`, legacy). Nessun lettore in climb-coach (grep: solo bug-inbox.md)
  - Chiamate di reentry_step: solo anchored_load.py:384. REENTRY_GAP_D: solo anchored_load.py:394. REENTRY_EXPOSURES: solo retest_policy.py:454
  - Indipendente, non si tocca: key_sessions_v1.REENTRY_MIN_EXPOSURES/REENTRY_WINDOW_D (:125-126, reduced_reentry_dose di A294, conta le sue esposizioni)
  - Ciclo chiuso: apply_anchored_feedback (anchored_load.py:1053-1057) confronta completed_sets con prescribed_sets. Senza tetto il player prescrive le serie salvate (es. 6) e il passo in su richiede 6 serie fatte: coerente. progression_v1/closed_loop_v1 non leggono reentry né ramp (grep: progression_v1 ha solo i campi legacy del limit, :243-247, già gestiti da B413)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b413_loads_never_lower.py::test_no_reentry_ramp_after_gap (:111-127; :121-122 sets == 5 e guardia reentry_sets; :118-119 ramp n/gap/in_reentry)
  - backend/tests/test_b413_loads_never_lower.py::test_no_reentry_ramp_on_the_memory_after_the_02_11_session (:136 ramp n=2, in_reentry)
  - backend/tests/test_b364_official_max_vs_working_load.py::test_custom_reentry_caps_max_hang_sets (:560-567, sets 5 e stored_sets 6)
  - Solo opzione B, asserzioni su ramp in test_b364: test_working_load_108_at_3_prescribes_108 (:208), test_hang_7s_cap_in_strength_power_is_110 (:230), test_daniele_hang_13_10_is_the_first_exposure_after_a_gap (:251), test_second_hang_session_is_n2 (:261), test_pulling_n3_has_no_reduction (:267), test_pulling_after_a_gap_has_no_reduction_either (:274/:277), test_empty_registry_and_fresh_entry_means_n3 (:286), test_no_history_at_all_means_n1 (:294), test_empty_date_is_conservative (:327)
  - Solo opzione B, in test_a288_retest_policy.py: test_no_load_factor_any_more (:206), test_no_history_is_first_exposure (:215), test_daniele_like_finger_gap_reopens_ramp (:220), test_run_counts_and_current_session (:226), test_gap_boundary_thirteen_vs_fourteen_days (:236), test_same_day_exposure_not_double_counted_and_today_excluded (:245), test_test_counts_as_exposure (:253), test_constants_pinned (:309 REENTRY_GAP_D)
  - Solo opzione B: golden c272 (backend/tests/fixtures/c272_resolver_golden.json, storia in c272_golden_cases.py:99-107): 6 chiavi del profilo advanced testato (finger_strength_home, pulling_strength_gym, strength_long × 10-07/10-21) contengono anchored.ramp
  - Resta invariato: frontend/src/lib/__tests__/anchored-load.test.ts:31-43 (nota legacy con ramp.factor)
- **Test da aggiungere:**
  - anchored_load max_hang_7s in rientro (n=1, gap 18) con sets=6: sets 6, rep_scheme '6x7s', nessuna guardia reentry_sets; total/cap identici a sets=5 e alla corsa con n≥3
  - resolve_custom_exercises: custom con 6 serie di hang dopo uno stacco tiene 6 serie, nessuno `stored_sets`, input non mutato
  - adhoc_builder: atleta testato dopo uno stacco, focus dita, energia high → hang a 6 serie, come senza stacco
  - Opzione B: `ramp` assente da anchored_load e da anchor_summary; `not hasattr(anchored_load, 'REENTRY_MAX_HANG_SETS')`, `not hasattr(rp, 'reentry_step')`; i test di B364 «dopo uno stacco nessuna riduzione» restano sui carichi
  - Golden c272 rigenerato: diff limitato ad `anchored.ramp` sulle 6 chiavi note, documentato in c272_golden_cases.py; b364_untested_golden invariato (atleti non testati identici bit per bit)
  - Determinismo: due chiamate identiche danno lo stesso output
- **Moduli ad alto rischio:**
  - anchored_load.py: non è nella lista, ma è chiamato da progression_v1.inject_targets e cambia l'output delle sessioni pianificate risolte (solo hang con più di 5 serie, mai nel catalogo; con l'opzione B sparisce la chiave ramp da ogni prescrizione ancorata)
  - progression_v1.py: nessuna modifica di codice (resta il commento obsoleto «re-entry ramp» a :1673; lo tocchiamo solo con OK)
  - closed_loop_v1.py / planner_v2 / replanner_v1 / macrocycle_v1 / resolve_session: non coinvolti (grep: nessun riferimento a reentry/ramp)
- **Effetto sugli altri utenti:** Riguarda solo gli atleti testati (percorso anchored_load). Dopo uno stacco di 14 giorni o più, i max hang delle custom e delle ad-hoc con più di 5 serie non vengono più tagliati a 5: valgono le serie salvate (ad-hoc con energia high = 6). Sessioni pianificate e carichi in kg invariati per tutti. Non testati: nessun cambiamento (anchored_load restituisce None, golden b364). Le sessioni passate restano come sono: la nota legacy sul fattore resta visibile.
- **Correzione dati in prod:** no
- **Domande:**
  - Pulizia completa (opzione B: via anche reentry_step, ramp_for e la chiave `ramp` dalle prescrizioni, 6 chiavi del golden c272 da rigenerare) o minima (opzione A: solo il tetto)? Raccomando B.
  - Confermi nessun tetto di serie sui max hang, nemmeno fuori dal rientro? Oggi una custom, anche composta dal coach LLM, può avere fino a 20 serie, e l'ad-hoc con energia alta ne dà 6.

#### A289-TEST-DONE-IN-WEEK — Un test fatto e registrato nella sua settimana (da martedì a domenica) risulta «non fatto» e il piano prova a rimetterlo

**Verdetto:** confermato · **effort** S · **rischio** medio · frontend no · schema user_state no

- **Causa:** retest_policy.py:1260: `_axis_week_decision` legge il massimale ufficiale al lunedì della settimana, `axis_official(state, axis, ws)`. official_max scarta i test con data successiva ad as_of (_hang_candidates :212-213, _pull_candidates :246-247), quindi un test registrato da martedì in poi non sposta `last`. `_trigger_for_week` continua a vedere `last < ws` (fine SP :1225, inizio ciclo :1227) e la settimana resta «due» con allowed_dates dai giorni rimasti (:1371-1384). Effetti: (a) retest_decisions (:1464) rimette il test tra le required_sessions e PASS 3a di planner_v2, a una rigenerazione della settimana (week.py:857), prova a piazzarlo di nuovo nei giorni rimasti, oppure scrive `no_placement_slot` («Couldn't schedule a test») se il blocco di 72 h lo impedisce; (b) retest_status (:1688-1723) trova la settimana generata e chiede a `_generated_week_skip`, che risponde «missed» per una riga piazzata prima di oggi senza guardare se la sessione è fatta (:1786) e «not_in_plan» il giorno stesso del test. La scheda (retest-status-card.tsx:45) mostra «the planned test this week was not done». Un test fatto di lunedì non ha il problema (as_of inclusivo). Riprodotto in sola lettura con la fixture `_due_1019()` più la combinata fatta e registrata giovedì 23/10: decisione 19/10 al 24/10 = due per entrambi gli assi (last 2026-09-10, allowed 24-25/10); retest_status 24/10 = «missed», 23/10 = «not_in_plan»; dal lunedì 26/10 not_due, quindi il difetto dura fino a fine settimana. Daniele oggi non è colpito (mirror 07/11: nessun test in questa settimana).
- **Evidenza:** Snippet in sola lettura (fixture `_due_1019` di test_a289, git status pulito). Senza fix: decisione 19/10 al 24/10 = due/due, allowed ['2026-10-24', '2026-10-25'], last_test_date 2026-09-10; retest_status 24/10 = missed, 23/10 = not_in_plan; settimana 26/10 = not_due. Con il fix in memoria: not_due con done_in_week 2026-10-23, required []; controllo con test non ancora fatto invariato.
- **Fix proposto:** IN PAROLE SEMPLICI (per Daniele): se fai il test un giorno diverso dal lunedì della settimana in cui era dovuto, per il resto della settimana l'app crede che tu non l'abbia fatto. La scheda «Your tested maxes» dice «il test previsto non è stato fatto» e, se la settimana viene ricostruita (sposti o aggiungi una sessione, cambi disponibilità), il piano prova a rimetterti il test nei giorni rimasti, oppure dice «Couldn't schedule a test». Il massimale nuovo è salvato correttamente: sbaglia solo la decisione su quella settimana. Il fix: un test fatto dentro la settimana chiude la settimana. CODICE, tutto in retest_policy.py, planner_v2 non cambia. Parte 1: in `_axis_week_decision`, dopo `base` e prima dei declines, `om_we = axis_official(state, axis, we, finger_device=...)`; se `om_we` è un test vero (`_om_is_test`) e `ws < data(om_we) <= we`, return `{**base, 'status': 'not_due', 'done_in_week': om_we['date']}`. La copertura (età < 90 gg) resta letta al lunedì, così un test che scade a metà settimana non cambia regime. Parte 2 (raccomandata): vale lo stesso per una sessione di test dell'asse (AXIS_TEST_SESSIONS_ALL[axis], combinata inclusa) con status 'done' nel piano della settimana anche senza valori registrati (`done_in_week` + `result_missing: True`), così non arriva un secondo test massimale 2-3 giorni dopo. Una sessione 'skipped' non conta. Con la parte 2, una combinata fatta chiude entrambi gli assi anche se è stata registrata solo la sospensione. `_generated_week_skip` non cambia: la settimana not_due non lo raggiunge più, e «missed» resta giusto per un test sparito e non fatto. Non serve un codice di motivo nuovo né un testo frontend. Determinismo: legge solo lo stato. Settimana sempre da `_monday`. Passato immutabile: la rigenerazione aggiunge di meno, il merge preserva le sessioni fatte. Documenti: vocabulary_v1.md:1196 (definizione di `missed` + `done_in_week`), ENGINE_ARCHITECTURE.md (sezione retest ~:693), user_guide_v1.md:583 (una frase: «un test fatto in qualsiasi giorno della settimana in cui era dovuto chiude quella settimana»), ROADMAP_CURRENT.md:93 → ✅. Validato con un monkeypatch in memoria: decisione 19/10 al 24/10 = not_due, done_in_week 2026-10-23, required []; retest_status 23 e 24/10 non dice più missed/not_in_plan; caso di controllo con test pianificato e non ancora fatto (21/10) invariato (due).
- **Alternative:** Solo parte 1, cioè conta solo il test registrato in tests.*: più stretta, ma una sessione fatta senza valori fa ancora rimettere il test. Leggere tutto il massimale a fine settimana invece che al lunedì: scartata, perché cambia la copertura dei 90 giorni a metà settimana (un test che scade di mercoledì farebbe passare la settimana alle regole legacy).
- **Raccomandazione:** Parte 1 + parte 2, solo in retest_policy.py, nello stesso branch del punto «test che scade», prima di quello: toccano entrambi `_axis_week_decision`/`retest_status`.
- **File:**
  - backend/engine/retest_policy.py
  - backend/tests/test_b414_test_done_in_week.py (nuovo)
  - docs/vocabulary_v1.md
  - docs/ENGINE_ARCHITECTURE.md
  - docs/user_guide_v1.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - _axis_week_decision è chiamata da: retest_decisions (retest_policy.py:1464), con la ricorsione deferred:earlier_week (:1357); retest_status (:1674 pdec di un test pianificato, :1692 proiezione); _plan_edit_weeks (:1762); retest_declines.week_to_reopen (retest_declines.py:436)
  - retest_decisions → api/routers/week.py:857 (generazione e rigenerazione della settimana) → planner_v2.generate_phase_week PASS 3a (legge required_sessions, skipped, already_scheduled, covered_axes; snapshot persistito planner_v2.py:3506-3515, senza `axes`, quindi forma invariata)
  - retest_status → api/routers/week.py:599 (GET /api/week/{n}.retest_status → frontend retest-status-card.tsx, mappa NO_TEST_TEXT :35-47); api/routers/retest.py:88/:126/:168 (decline/postpone A320: senza test pendente risponde 409 no_pending_retest, ed è corretto); athlete_context.py:343 (_retest, sezione Retest :1660-1667 e :1989 con next_test_reason), scripts/athlete_context.py e coach
  - Non cambiano: _generated_week_skip (:1771-1790), _planned_axis_tests (:961-997), legacy PASS 3 degli assi non coperti (week.py ~:830, legge le date dei test)
- **Test che fissano il comportamento attuale:**
  - Nessun test pinna il difetto: nessuno registra un test a metà di una settimana dovuta e controlla quella settimana
  - Comportamenti vicini da mantenere: test_a320_retest_decline.py::TestImplicitDecline::test_generated_week_skip_reads_declined_for_a_placed_then_removed_test (:705-717: «missed» per un test sparito senza traccia e non fatto)
  - test_a320_retest_decline.py::TestPostpone::test_skipped_before_until_then_due_from_until_until_a_new_test (:391-413: un test nuovo rende inerte il rinvio)
  - test_a289_retest_policy.py::TestDayBlockers::test_skipped_test_does_not_count_as_scheduled (:418), ::TestStatus::test_projection_skips_a_generated_week_without_the_test (:862), ::TestStatus::test_planned_test_reason_and_no_blockers_24_10 (:617), ::TestPlanner::test_past_sessions_immutable_after_regeneration (:555)
  - test_a319_retest_rules.py::TestCombinedTestLog::test_one_log_writes_both_maxes (:1054)
- **Test da aggiungere:**
  - Combinata registrata giovedì in una settimana dovuta: retest_decisions(ws, today=venerdì) dà not_due per entrambi gli assi, `done_in_week`, required_sessions []
  - retest_status il giorno del test e il giorno dopo: next_test_reason non è «missed» né «not_in_plan»; earliest_retest = test + 42
  - Test fatto lunedì: comportamento invariato (già not_due)
  - Solo sospensione registrata in una sessione singola: dita not_due, trazione ancora due
  - Parte 2: sessione di test 'done' senza valori → not_due con result_missing; 'skipped' → ancora due
  - Rigenerazione a metà settimana dopo il test (generate_phase_week con le decisioni, o regenerate_preserving_completed): nessun test nuovo e la sessione di test fatta identica byte per byte (passato immutabile)
  - Test pianificato e non ancora fatto: decisione invariata (controllo)
  - Atleta non testato: retest_decisions None (planner byte-identical); determinismo (due chiamate uguali)
- **Moduli ad alto rischio:**
  - retest_policy.py: non è nella lista, ma la sua uscita guida planner_v2 PASS 3a. Cambia cosa il planner piazza nella settimana del test, senza modifiche al codice di planner_v2
  - planner_v2.py / replanner_v1.py (regenerate_preserving_completed): coinvolti solo come consumatori, nessuna modifica; serve il test dell'immutabilità del passato dopo la rigenerazione
  - macrocycle_v1 / resolve_session / progression_v1 / closed_loop_v1: non coinvolti
- **Effetto sugli altri utenti:** Ogni atleta testato (test < 90 gg) che registra un test da martedì a domenica di una settimana dovuta non vede più «missed»/«not_in_plan» e non si ritrova il test rimesso (o «Couldn't schedule a test») nei giorni rimasti. Atleti non testati e assi non coperti (loading pin, test scaduto): invariati. Nessun dato salvato cambia: lo snapshot della settimana ha la stessa forma.
- **Correzione dati in prod:** no
- **Domande:**
  - Adesso che è spiegato (sopra, «in parole semplici»): ok a sistemarlo così?
  - Parte 2: una sessione di test segnata «fatta» senza valori chiude la settimana (niente secondo test massimale in 2-3 giorni; il massimale resta quello vecchio finché non inserisci i valori con la matita)? Raccomando sì.

**Note trasversali (analisi:max-hang-e-test-settimana):** Tutto backend, nessun file frontend: il push diretto su main è permesso dalla regola dei branch, salvo che il brief B414 includa la parte UI del punto «test che scade». Nessuna scrittura in prod: per Daniele nessuno dei due punti richiede correzioni di dati. Il mirror del 07/11 non mostra test in questa settimana, ma dice «not_tested_recently» con tested_until 22/12: è il punto «test che scade» (posticipare la scadenza o fare il test, mai azzerare). Quel punto e A289-TEST-DONE-IN-WEEK toccano le stesse funzioni (retest_policy._axis_week_decision, retest_status, il postpone di retest_declines): vanno in sequenza nello stesso branch, prima A289 (piccolo), con un file di test per punto. Il motivo `not_tested_recently` oggi cade sul fallback «not due yet» della scheda (NO_TEST_TEXT non lo mappa): ne terrà conto il punto della scadenza. Moduli ad alto rischio: nessuna modifica diretta a planner_v2, replanner_v1, macrocycle_v1, resolve_session, progression_v1, closed_loop_v1, ma entrambi i punti ne cambiano gli input (anchored_load tramite inject_targets, retest_decisions tramite PASS 3a). Fase 3: suite completa, golden c272 (cambia solo con l'opzione B del punto 1, 6 chiavi), golden b364 dei non testati invariato, test dell'immutabilità del passato dopo la rigenerazione. Se l'opzione B toglie `ramp` dal JSON di athlete_context, alzare VERSION (oggi «a324.1», pinnata in test_a320_retest_decline.py:1165). Residui di B413 da pulire nello stesso commit: coach/prompt_builder.py:294 («re-entry discount» del limit, che non esiste più) e il commento di progression_v1.py:1673 (file ad alto rischio: solo con OK). Fuori da questo repo, dopo il deploy: climb-coach/regole.md:183 e bug-inbox.md:15 citano ancora il tetto di 5 serie. Pre-esistente, fuori scope: la KB del coach (knowledge/L3/20_return_to_training.md:18) descrive una rampa del motore dopo uno stop (70-80% per 2 sedute) che il motore non implementa. Script di riproduzione in /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/repro_a289.py (sola lettura). Codice letto nel worktree /Users/danielesomensi/Projects/climb-agent-b414 @ 4d53bf5, git status pulito dopo ogni snippet.

### replanner-residui

#### A319-CHANGE-GYM — change_gym su un giorno con la combinata perde anche la sospensione massimale

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** replanner_v1.py:1474-1544 (ramo change_gym) confronta `_get_required_equipment(sid)` (replanner_v1.py:53-66, dal catalogo: test_max_hang_pullup chiede hangboard+pullup_bar+weight, catalog/sessions/v1/test_max_hang_pullup.json e planner_v2.py:69) con l'attrezzatura espansa della nuova palestra. Se non basta, `_find_gym_change_replacement` (replanner_v1.py:69-91) restituisce solo complementary_conditioning o regeneration_easy: non sa che la combinata contiene una sospensione da sola valida. La docstring (righe 75-79) promette anche un ripiego finger_strength_home che il codice non ha. La riga 1527 riscrive `explain`, quindi il timbro `retest:` sparisce e `retest_policy.is_policy_test` (retest_policy.py:1098-1106) dà False. Due difetti collegati trovati nell'analisi: (a) andando a casa senza `home_equipment` nell'evento non si controlla l'attrezzatura (replanner_v1.py:1515-1518, `if home_eq and ...`). L'app non lo manda mai (week/page.tsx:621-629, today/page.tsx:899-907) e il router non lo riempie (replanner.py:694-705), quindi la combinata portata a casa resta combinata anche senza pesi. (b) Il dry run di /events (`key_sessions_v1.build_key_conflicts`, key_sessions_v1.py:1692) e `_simulate_add` (key_sessions_v1.py:740) chiamano apply_events senza `gyms`: un change_gym nel dry run sostituisce ogni sessione che chiede attrezzatura, anche verso la stessa palestra.
- **Evidenza:** Snippet in sola lettura (/private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/repro_a319.py). Combinata Bkl→Cocque: complementary_conditioning, policy_test=False, lost_finger=True, warning missing_equipment={'weight'}. Combinata→casa senza home_equipment: resta test_max_hang_pullup senza controllo. Con home_equipment [hangboard, pullup_bar]: complementary + lost_finger. Dry run senza gyms: limit_boulder_gym verso la STESSA palestra bkl diventa complementary_conditioning; con gyms resta limit_boulder_gym.
- **Fix proposto:** Nel ramo change_gym di replanner_v1: se sid è la combinata (planner_v2._COMBINED_TEST_SID / retest_policy.COMBINED_TEST_SESSION) e la nuova sede ha l'attrezzatura di test_max_hang_7s (hangboard) ma non tutta quella della combinata, il sostituto è `test_max_hang_7s`. Su quella sessione: tag e intensità da `_meta_for` (hard, finger, test); explain = riga `gym_change: ...` più il timbro della policy solo per le dita (`retest:finger:<t>` diventa `retest:<t>`, si toglie `retest:pulling:*`); niente `lost_finger`; warning «test_max_hang_pullup → test_max_hang_7s (missing_equipment={'weight'}): the pull-up test waits for its next turn». Senza trave resta il comportamento attuale (complementary_conditioning + lost_finger). Mai il 2RM da solo: in PASS 3a di A319 la trazione non va mai senza la sospensione. Il 2RM da solo resta com'è (complementary). Si corregge la docstring di `_find_gym_change_replacement`. Collegati, piccoli: (b) passare `gyms` e l'attrezzatura di casa dallo stato in `build_key_conflicts` e `_simulate_add`; (a) da decidere: il router riempie `home_equipment` da `state.equipment.home` quando l'evento non lo porta. Opzionale: `retest_policy._generated_week_skip` (retest_policy.py:1771-1790) mostra `blocked:no_paired_slot` per l'asse trazione quando la sua riga dello snapshot è `combined` e nel piano, a placed_date/placed_slot, c'è un test solo dita. Oggi la card direbbe `not_in_plan`. Immutabilità: done/skipped si saltano ancora (replanner_v1.py:1500-1501), gli altri giorni restano identici (A301), un giorno passato si tocca solo con un'azione esplicita dell'utente (eccezione ammessa). Determinismo: invariato.
- **Alternative:** Lasciare il comportamento attuale: il 2RM e la combinata spariscono tutti e due, come fissato da TestChangeGymOnATestDay. Oppure ripiegare in modo simmetrico sul 2RM da solo dove ci sono pesi ma non la trave: scartato, contraddice A319 (la trazione aspetta, mai da sola).
- **Raccomandazione:** Ripiego sulla sospensione da sola con la trazione che aspetta, fix del dry run (b), e il motivo `blocked:no_paired_slot` nella card. L'iniezione di home_equipment (a) solo con l'OK di Daniele, perché cambia change_gym→casa per tutti.
- **File:**
  - backend/engine/replanner_v1.py
  - backend/engine/key_sessions_v1.py
  - backend/api/routers/replanner.py (opzionale, home_equipment)
  - backend/engine/retest_policy.py (opzionale, motivo blocked:no_paired_slot)
  - backend/tests/test_a319_retest_rules.py
  - docs/ENGINE_ARCHITECTURE.md (778-781, 965)
  - docs/vocabulary_v1.md (1744)
  - docs/user_guide_v1.md (767)
  - docs/ROADMAP_CURRENT.md (91)
- **Chiamanti e consumatori:**
  - backend/engine/replanner_v1.py:1474 apply_events, ramo change_gym (unica implementazione); log `event` (1845) e adattamento `change_gym` (1552-1559)
  - backend/api/routers/replanner.py:694 POST /api/replanner/events (scrittura vera, gyms passati); 873-879 i warning di change_gym vanno nella risposta
  - backend/api/routers/replanner.py:634-637 dry run → key_sessions_v1.build_key_conflicts (key_sessions_v1.py:1692, senza gyms); would_auto_reschedule calcolato sul piano del dry run (replanner.py:655-657)
  - backend/engine/key_sessions_v1.py:740 _simulate_add (senza gyms, oggi solo add_*)
  - frontend/src/app/(main)/week/page.tsx:613-641 e today/page.tsx:891-918 handleChangeGymApply (toast con i warning; manda solo date/gym_id/location)
  - coach climb-coach via /events: evento archiviato del 2026-10-06 con slot + session_ref, che change_gym ignora (si applica a tutto il giorno)
  - Lettori della combinata/sospensione dopo il cambio: retest_policy._planned_axis_tests (961-998), retest_status (1667-1686), _generated_week_skip (1771-1790), plan_edit_removal (1109-1189: change_gym non è un record di rimozione, quindi nessun rifiuto implicito A320), key_sessions_v1._pending_tests (634-642, il prefisso test_max resta)
  - backend/api/auto_reschedule.py:155 (A315, solo add_planned_session, non tocca change_gym)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_a319_retest_rules.py::TestChangeGymOnATestDay::test_combined_replaced_where_there_are_no_weights_and_its_hang_is_lost (1224): si ribalta
  - backend/tests/test_a319_retest_rules.py::TestChangeGymOnATestDay::test_2rm_replaced_where_there_are_no_weights (1219): resta
  - backend/tests/test_a319_retest_rules.py::TestChangeGymOnATestDay::test_kept_where_a_dumbbell_implies_weight (1216): resta
  - backend/tests/test_replanning_v1.py:838-1015 (5 test change_gym, nessuna combinata): restano
  - backend/tests/test_a301_guards_are_alerts.py:311 (param change_gym di test_events) e 700-711 test_events_surface_a_lost_finger_session: restano (LIMIT solo palestra); ricontrollare se si inietta home_equipment
  - backend/tests/test_b173_silent_fallback_warnings.py:113 test_change_gym_event_warns_on_unknown_gym_id: resta
  - backend/tests/test_b413_freeze_prescription.py:483 (change_gym nel flusso API, controlla solo le sessioni giocate): resta
  - frontend/src/lib/__tests__/plan-revision.test.ts:93 (solo l'elenco degli event type): resta
- **Test da aggiungere:**
  - combinata Bkl→Cocque diventa test_max_hang_7s: is_policy_test True, explain senza retest:pulling, warning con la trazione che aspetta, niente lost_finger
  - combinata verso una palestra senza trave: complementary_conditioning + lost_finger (invariato)
  - combinata verso una palestra con pesi ma senza trave: mai il 2RM da solo
  - combinata done/skipped intatta; gli altri giorni identici byte per byte (_unchanged_except di A301)
  - dry run di change_gym (build_key_conflicts) uguale alla scrittura vera, stessa palestra = nessuna sostituzione
  - API: change_gym→casa con equipment.home senza pesi → sospensione (solo se si inietta home_equipment)
  - retest_status asse trazione = blocked:no_paired_slot dopo il cambio (se accettato)
  - determinismo: stesso piano + stesso evento → stesso risultato
- **Moduli ad alto rischio:**
  - backend/engine/replanner_v1.py
- **Effetto sugli altri utenti:** Riguarda solo chi ha la combinata pianificata (entrambi gli assi dovuti e coperti dalla policy) e cambia la palestra di quel giorno verso un posto con trave ma senza pesi: ora tiene la sospensione massimale invece di perderla. Il fix del dry run vale per tutti: il dry run di un change_gym combacia con la scrittura (oggi il coach vede sostituzioni false). L'iniezione di home_equipment, se accettata, cambia change_gym→casa per tutti: le sessioni che chiedono attrezzatura assente a casa vengono sostituite, oggi restano.
- **Correzione dati in prod:** no. Nel mirror le settimane in hot di Daniele (26/10→30/11) hanno 0 record change_gym e nessuna combinata pianificata. I 6 change_gym storici sono in settimane archiviate passate, immutabili.
- **Domande:**
  - Va bene che la combinata portata in una palestra senza pesi diventi la sola sospensione, con il 2RM che aspetta il prossimo turno?
  - Il router deve prendere l'attrezzatura di casa dallo stato quando l'app non la manda? Cambia «cambia sede → casa» per tutti.
  - Per l'asse trazione, la card deve dire `blocked:no_paired_slot` invece di `not_in_plan`?

#### B369-P6-residui — Dopo B371: change_gym persa alla rigenerazione e riconciliazione post-rigenerazione delle sessioni del motore

**Verdetto:** parziale · **effort** L · **rischio** medio · frontend no · schema user_state no

- **Causa:** (2) change_gym (replanner_v1.py:1474-1544) cambia location, gym_id e a volte session_id, ma non mette nessun marker. `user_owned.is_user_owned` (user_owned.py:27-52) dà False, quindi in `_merge_user_content` la sessione vecchia non si conserva (replanner_v1.py:776) e quella rigenerata dal motore la sostituisce. Il planner non legge il cambio: dal piano della stessa settimana legge solo gli slot svuotati (B382(a), planner_v2.py:1590-1601) e i giorni engine-free (B379, 1691-1698). L'unica rigenerazione di una settimana vera è GET /api/week con force o stale (week.py:715, 866-898, merge a 927). (1) PASS 1/1.5/2 non vedono le sessioni future dell'utente. Lo spacing parte solo da: settimana prima (B161, planner_v2.py:1659-1671), giorni vissuti fatti (B390, 1771-1792), giorni in falesia (B382(b), 1736-1757, `_near_crag` 1794-1800, inseriti dopo PASS 1.5 a 2082-2091). PASS 3a (B400, 2678-2700), PASS 2.7 (A305, 966-1060) e A300 leggono la vista unita; gli altri pass no. Il merge rimette le sessioni dell'utente e chiama solo `_regen_guard_warnings` (replanner_v1.py:649-664), una sonda su `_reconcile` che segnala solo quando la sessione dopo è riscrivibile (`_enforce_no_consecutive_finger`, 1054-1121). Nessun codice legge `regeneration_guard_warnings` (solo test_b369:790-797). (3) La corsa residua di B371 non è in replanner_v1: il lock per utente vale nel singolo processo (plan_revision.py:470-492) e il salvataggio della rigenerazione in GET /api/week è senza lock (week.py:960-963).
- **Evidenza:** Snippet in sola lettura nel scratchpad. repro_p6.py: boulder_circuit_gym gym_a→gym_b con change_gym, poi rigenerazione + merge → di nuovo gym_a. repro_a319.py: combinata→Cocque dà complementary, la rigenerazione rimette la combinata a Bkl. repro_p6_1.py: custom dita-hard sabato a pranzo, disponibilità senza giovedì; la rigenerazione mette power_contact_gym (H,F) venerdì sera, guards_v1 segnala finger_gap + hard_back_to_back il sabato, ma `regeneration_guard_warnings` è vuoto.
- **Fix proposto:** (2) Opzione B, raccomandata: il planner rilegge la scelta di palestra fatta sulla stessa settimana, come fa B382(a) con gli slot svuotati. Nuovo lettore puro `user_owned.gym_changes(plan)` → {data: {location, gym_id}}, dall'ultimo adattamento `change_gym` per data. In planner_v2, accanto al blocco slot_emptied (1590-1601), per ogni data della settimana ≥ today: ogni slot disponibile di quel giorno prende `locations=[loc]`, `preferred_location=loc`, `gym_id` (None a casa). Il planner sceglie così una sessione compatibile con l'attrezzatura di quella palestra; PASS 3a controlla già l'attrezzatura della combinata nello slot. Merge invariato, nessun marker nuovo in USER_MARKERS. Le settimane senza record change_gym restano identiche byte per byte. Opzionale: change_gym rispetta lo `slot` quando c'è (il coach lo manda già) e il lettore applica il cambio solo a quegli slot. (1) Minimo: estendere le ancore di B382(b) alle sessioni future dell'utente della stessa settimana (data ≥ today, conservabili, non skipped, flag via `stimulus.session_flag`, la stessa lettura di guards_v1). Controllo sui due lati in PASS 1/1.5 (`_near_crag` generalizzato: gap dita per le sessioni dita dell'utente, gap hard per quelle hard), inserite in finger_day_offsets/hard_day_offsets dopo PASS 1.5 come le falesie, +1 a `hard_days` per ogni giorno hard dell'utente non già contato. Niente blocco degli slot e nessun cambio ai giorni target: domanda. La sonda `_regen_guard_warnings`, non usata e incompleta, si toglie o si sostituisce con un diff di guards_v1: domanda. (3) Fuori da replanner: brief separato (salvataggio condizionato sulla revisione a livello storage). Invarianti: il passato resta immutabile (il planner salta le date < today, il merge copia i giorni prima di preserve_before e tiene done/skipped identici); determinismo (si leggono solo le adaptations del piano, vince l'ultimo record); filtro per attrezzatura (Opzione B è puro equipment); niente chiamate a generate_macrocycle né cambi a start_date o Monday.
- **Alternative:** Opzione A: marker `user_gym_change` in USER_MARKERS. Scartata per gli effetti collaterali: «Salta giorno» (whole_day) non pulirebbe più il giorno (replanner_v1.py:2115-2117); l'override outdoor la terrebbe (1992-1994); A294/A315 non potrebbero più sostituirla (key_sessions_v1.py:880); toglierla non svuoterebbe più lo slot (replanner_v1.py:1245, user_owned.py:118-123); A300 la conterebbe come dell'utente (complementary_v1.py:484); cambierebbero _locked_by_merge, _planned_axis_tests e plan_edit_removal (retest_policy.py:885, 961, 1109); infine congelerebbe la sessione, che non seguirebbe più un cambio di fase. Opzione C: /events scrive un weekly_override per quella data. Mescola due funzioni, si vede nelle impostazioni e ha un'altra semantica di stale.
- **Raccomandazione:** Nel brief: prima (2) con l'Opzione B, poi (1) con le ancore, ognuno con il test di identità sulle settimane senza dati nuovi (fixtures/a300_identity_digests.json). (3) a parte. Dopo B, alla rigenerazione PASS 3a può spostare un test in un altro giorno con i pesi: è il planner che decide, la scelta di palestra dell'atleta resta.
- **File:**
  - backend/engine/user_owned.py (lettore gym_changes)
  - backend/engine/planner_v2.py (override sede/palestra per data; ancore delle sessioni future dell'utente in PASS 1/1.5/2)
  - backend/engine/replanner_v1.py (opzionale: slot in change_gym; sonda _regen_guard_warnings)
  - backend/tests/test_b414_*.py (nuovo)
  - docs/ENGINE_ARCHITECTURE.md (994, 1008-1010, 965)
  - docs/vocabulary_v1.md
  - docs/user_guide_v1.md (767, 778: il cambio di sede resta dopo una rigenerazione)
  - docs/ROADMAP_CURRENT.md (96)
- **Chiamanti e consumatori:**
  - backend/api/routers/week.py:612-963 GET /api/week: unica rigenerazione vera (force o _stale), generate_phase_week(existing_week_plan=old_plan) a 866-898, regenerate_preserving_completed a 927
  - stale impostato da deps.mark_weeks_stale: deps.py:138 (invalidate_week_cache: macrociclo, onboarding, start-week, promemoria test), plan.py:71, weekly_override.py:136/167, retest.py:72, macrocycle.py:155, PUT /api/state (availability/planning_prefs/weekly_overrides), nuovo ciclo, ripresa dalla pausa
  - backend/engine/replanner_v1.py:891 regenerate_preserving_completed e 847 merge_prev_week_sessions (fuori dai test, chiamato solo da week.py) → _merge_user_content 667-844 → _regen_guard_warnings 649-664
  - viste del merge dentro il planner: planner_v2._merge_preview 847-882 (PASS 3a 2678-2700), _key_stimulus_pass _week_view 1010-1060, complementary_v1._effective_view 500-515
  - retest_policy._locked_by_merge 885-937, _merge_wholesale_dates 940-958, _planned_axis_tests 961-998
  - change_gym: come nella voce A319-CHANGE-GYM (replanner_v1.py:1474; replanner.py:694, 634-637, 873-879; key_sessions_v1.py:1692; week/page.tsx:624; today/page.tsx:902; coach via /events)
  - lettori di is_user_owned/is_preservable (impatto dell'Opzione A scartata): complementary_v1.py:484/604/642, retest_policy.py:935/994/1152, planner_v2.py:1180, replanner_v1.py:776/1245/1672/1993/2115, adaptive_replan.py:339, guards_v1.py:234-252/520-531, key_sessions_v1.py:880, retest_declines.py:287-338
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b369_preserve_user_sessions.py::test_regeneration_alerts_on_a_guard_conflict_without_rewriting (780-797): fissa la sonda regeneration_guard_warnings
  - backend/tests/test_a300_complementary_slots.py + fixtures/a300_identity_digests.json: 180 piani da tenere identici
  - backend/tests/test_b382_slot_empty_crag_hard.py (D1 a 151, sessioni dell'utente o spostate a 158/166, falesie 232-277): da rilanciare, con le ancore gli slot del motore possono spostarsi
  - backend/tests/test_b400_retest_merge_view.py, test_a305_key_stimulus_pass.py, test_b390_midweek_past_hard.py, test_b379_outdoor_day_regeneration.py: usano existing_week_plan con sessioni dell'utente, da rilanciare
  - backend/tests/test_merge_prev_week.py, test_b114_preserve_past_weeks.py, test_b287_replanner_immutability.py, test_b257_guard_pastweek.py, test_outdoor.py, test_a265_outdoor_pitch_ladder.py: merge, devono restare verdi (il merge non cambia)
  - nessun test fissa oggi che la rigenerazione annulli un change_gym
- **Test da aggiungere:**
  - change_gym gym_a→gym_b, poi rigenerazione stale/force: il giorno resta a gym_b con una sessione compatibile; le altre date identiche
  - combinata spostata a Cocque, poi rigenerazione: nessun test a Cocque che chieda pesi; snapshot coerente col piano
  - change_gym su un giorno passato o con done: rigenerazione con passato byte-identico
  - due change_gym sulla stessa data: vince l'ultimo; settimana senza record → identità (digest A300)
  - ancore: custom dita-hard sabato + disponibilità cambiata → nessuna sessione dita/hard del motore venerdì; hard cap con giorni hard dell'utente
  - ancore: sessione spostata/forzata/key_reschedule conta, skipped no, giorno passato non fatto no (B390)
  - determinismo: due rigenerazioni uguali → stesso piano
  - settimana con sessioni dell'utente solo prima di today: identica a oggi
- **Moduli ad alto rischio:**
  - backend/engine/planner_v2.py
  - backend/engine/replanner_v1.py
- **Effetto sugli altri utenti:** (2) Solo chi ha usato «cambia sede» su un giorno futuro di una settimana in cache: alla rigenerazione successiva quel giorno resta nella sede scelta, con una sessione scelta per quella attrezzatura (oggi torna alla palestra di default). (1) Chiunque abbia sessioni proprie future (custom, spostate, forzate, quick-add, key re-schedule, generated add) in una settimana che si rigenera: le sessioni del motore rispettano gap dita, gap hard e tetto hard intorno a quelle dell'utente. Meno alert, ma a volte il motore mette una sessione hard in meno o in un altro giorno. Settimane senza questi dati: identiche.
- **Correzione dati in prod:** no. Nessun record change_gym nelle settimane in hot di Daniele (mirror, 26/10→30/11); le settimane passate non si rigenerano.
- **Domande:**
  - Per la palestra cambiata: il planner rilegge la tua scelta e alla rigenerazione può cambiare la sessione di quel giorno, scelta per la nuova palestra (Opzione B)? Oppure preferisci che la sessione resti congelata come tua (Opzione A, con gli effetti su «Salta giorno» e sulle proposte)?
  - «Cambia sede» deve valere per tutto il giorno, pranzo al Work compreso, come oggi, o solo per lo slot scelto? Il coach manda già lo slot, il motore lo ignora.
  - Per la riconciliazione: basta che il motore rispetti gap e tetto intorno alle tue sessioni? Oppure deve anche liberare gli slot che occupi e contare i tuoi giorni nel numero di giorni di allenamento?
  - `regeneration_guard_warnings` non lo legge nessuno e manca dei casi: lo tolgo?
  - La corsa residua di B371 (salvataggio condizionato sulla revisione): brief a parte o resta aperta, visto che oggi c'è un solo processo?

**Note trasversali (analisi:replanner-residui):** Le due voci sono legate: il ripiego di A319-CHANGE-GYM conta fino alla rigenerazione successiva. Con l'Opzione B di B369-P6(2), da lì in poi è PASS 3a a decidere il test con la palestra scelta (può spostarlo in un giorno con i pesi). Ordine consigliato nel brief: A319-CHANGE-GYM + fix del dry run (solo replanner_v1 e key_sessions_v1), poi B369-P6(2) Opzione B (user_owned + planner_v2), poi B369-P6(1) ancore (planner_v2). Ogni passo con il test di identità A300 e la verifica del passato immutabile. Tutti toccano moduli ad alto rischio (replanner_v1, planner_v2): Fase 1 + STOP, nessun cambio allo schema di user_state (si legge solo `adaptations`, che esiste già nel week_plan), nessun file frontend. Invarianti controllati: passato immutabile (change_gym salta done/skipped; il planner ignora le date < today; il merge copia i giorni prima di preserve_before); determinismo (si leggono solo i record del piano, vince l'ultimo per data); filtro per attrezzatura (rispettato, l'Opzione B è pura attrezzatura); Fontainebleau, from_phase="current" e Monday non toccati. Trovati fuori dalle voci: (a) change_gym ignora `slot` e `session_ref` e cambia tutto il giorno (evento del coach del 2026-10-06 nell'archivio), quindi un pranzo in un'altra palestra si sposta insieme alla sera; (b) il dry run di /events (key_sessions_v1.py:1692) non passa `gyms`, quindi un change_gym nel dry run dà sostituzioni false: tocca la regola «dry run prima di ogni scrittura» del coach; (c) change_gym→casa dall'app non controlla mai l'attrezzatura di casa. Il punto (3) di B369-P6-residui (corsa residua di B371) è nello storage e nelle API, non nel replanner: brief separato. Dati di prod: niente da correggere (0 change_gym nelle settimane in hot di Daniele, nessuna combinata pianificata). Gli altri punti della richiesta di Daniele (scadenza dei test e rinvio senza azzerare, tetto delle 5 serie di max hang, P2) non sono in quest'area. Nessun dato di salute nelle evidenze. Snippet di riproduzione, tutti in sola lettura: /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/repro_a319.py, /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/repro_p6.py, /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/repro_p6_1.py.

### scadenza-test

#### B414-1-GATE — La scadenza del test non deve più spegnere niente: scale, carichi ancorati, rotazione A290, ancora PE, coach

**Verdetto:** confermato · **effort** M · **rischio** alto · frontend no · schema user_state no

- **Causa:** Il cancello è uno solo: retest_policy.py:67 (TEST_FRESH_DAYS=90), :306-307 e :333-334 (`tested` = test reale E età < 90), :344-347 (is_tested). Il 23/12 si spengono queste parti. (1) Scale: bw_ladders.py:325-334 (tested_gate) porta a bw_progression.py:331 (entries_for vuoto), :849 (apply_bw_item non fa niente: il feedback non muove le scale), :1099 (righe custom con le dosi salvate), :1159 (misure tecniche piedi/cadute), :1321 (build_resolve_context None: il resolver lascia il catalogo, ladder_pin dei pranzi compreso). (2) Carichi: anchored_load.py:579-580 (anchored_load None) porta al ramo pre-B364 di progression_v1.py:1700ss: max hang = `_max_hang_suggested`, cioè baseline × 0,9 senza tetti di fase, guardie, dolore o fatica; pull-up = % del 2RM. Il feedback va al ramo legacy (anchored_load.py:1030 dà False, progression_v1.py:2960-2978), che riscrive working_loads. (3) Rotazione A290 spenta (phase_anchor.py:218, :241) e ancora PE A292 spenta (progression_v1.py:704). (4) Coach in regime da non testato (athlete_context.py:2255-2260, letto da adhoc_builder.py:622/665 e session_composer.py:263/613/653). (5) Assi non più coperti (retest_policy.py:1261) e programmazione dei test con il PASS 3 legacy. Niente viene cancellato (bw_progression, working_loads e tests restano), ma il comportamento è quello di un atleta mai testato.
- **Evidenza:** Simulazione read-only sul mirror di prod (test del 24/09, entrambi gli assi). Dal 06/12 al 22/12 è tutto attivo: gate True, anchored su max_hang_7s e weighted_pullup, 11 famiglie di scala, build_resolve_context e rotazione. Dal 23/12 è tutto spento: gate False, anchored None, 0 famiglie, ctx None, tested_any False. Dopo il 06/12 position_on dà deload, abs_week 13 e after_end True (macro_position.py:141). Oggi retest_status ha next_test None con motivo not_tested_recently su entrambi gli assi.
- **Fix proposto:** Modello A. In `official_max`, `tested` diventa «test reale» a qualunque età (`_cand_tested`): la scadenza smette di essere un cancello. Si aggiungono tre campi: `valid_until` (test + 89 gg, oppure l'`until` di un rinvio attivo se è più tardi, vedi B414-2), `expired` e `expiring` (da valid_until − 14 gg). `fresh` resta «età < 90», solo informativo. Nessun consumatore cambia codice. Scale, carichi ancorati, rotazione e coach restano attivi e il ciclo chiuso continua a progredire. La policy continua a coprire l'asse: dopo 84 gg il trigger maintenance propone il test in ogni settimana utile (non in performance, deload o dopo la fine del ciclo). `retest_status` espone valid_until / expired / expiring. Per un test reale sparisce 'not_tested_recently'; arriva un motivo nuovo, 'after_cycle_end'. Da aggiornare: docstring di bw_ladders, bw_progression, anchored_load e phase_anchor, poi vocabulary §4.5b ed ENGINE_ARCHITECTURE §8.2.
- **Alternative:** B — congelato all'ultimo livello: entries e carichi letti come al 22/12, feedback senza effetto. Serve un terzo stato in bw_progression, anchored_load e phase_anchor; rompe il ciclo chiuso; sforzo M-L. C — come oggi più la sola proroga esplicita: senza scelta il 23/12 si spegne tutto, contro il «mai azzerare»; scartata. A-ristretto — la continuazione solo per chi ha già bw_progression o working_loads del regime testato: preserva i golden, ma è una regola oscura che dipende dallo stato.
- **Raccomandazione:** Modello A. Rispetta alla lettera il «mai azzerare» ed è un diff piccolo in un punto solo, la lettura unica di A288. Non è meno prudente di oggi: il ramo legacy prescriveva dallo stesso massimale vecchio (baseline × 0,9 senza tetti di fase, progression_v1.py:1704 / _max_hang_suggested), il ramo ancorato ha tetti, guardie, dolore e fatica.
- **File:**
  - backend/engine/retest_policy.py
  - backend/engine/bw_ladders.py (docstring)
  - backend/engine/bw_progression.py (docstring apply_bw_item)
  - backend/engine/anchored_load.py (docstring scope)
  - backend/engine/phase_anchor.py (docstring)
  - backend/tests/fixtures/a290_untested_golden.json
  - backend/tests/fixtures/b364_untested_golden.json
  - backend/tests/a290_untested_cases.py
  - backend/tests/b364_untested_cases.py
  - docs/vocabulary_v1.md
  - docs/ENGINE_ARCHITECTURE.md
  - docs/user_guide_v1.md
- **Chiamanti e consumatori:**
  - bw_ladders.tested_gate (bw_ladders.py:325) ← seed_levels :484/:487, bw_progression.tested :315, athlete_context.py:589, key_sessions_v1.py:774, api/ladder_archive.py:119
  - bw_progression.entries_for :331 / apply_bw_item :849 / resolve_custom_ladder_rows :1099 / attach_technique_measures :1159 / build_resolve_context :1321 / ladder_view :1263
  - anchored_load.is_anchored_and_tested :326, anchored_load :579, apply_anchored_feedback :1030, hang_write_cap :1229 ← progression_v1.inject_targets :1681, body_part_picker.py:619, adhoc_prescription.py:144/218, coach/session_composer.py:466, coach/prompt_builder.py:348, athlete_context.py:303/2248, key_sessions_v1.py:462, week.py _with_custom_anchored_loads
  - phase_anchor.tested_ratio :218 / is_tested_any :241 ← build_rotation_context (resolve_session)
  - progression_v1.pe_anchor_applies :704, official_hang_7s :1657, _hang_recently_tested :2016
  - retest_policy._axis_week_decision :1261, retest_status :1622-1631 (covered, tested_until), retest_declines.week_to_reopen :439
  - api/routers/week.py:577 (_status_needs_archive), :1003-1006 (il promemoria delle 6 settimane è nascosto quando entrambi gli assi sono coperti)
  - athlete_context.py:280-281, :1125, :1322, :1896, :2255; adhoc_builder.py:622/665; coach/prompt_builder.py:331; scripts/athlete_context.py:258; scripts/migrate_b364.py:107 (migrazione una tantum, da lasciare)
- **Test che fissano il comportamento attuale:**
  - test_a288_retest_policy.py::test_as_of_excludes_later_tests_and_staleness
  - test_a289_retest_policy.py::test_stale_test_is_not_covered, ::test_stale_real_test_still_reported
  - test_a290_phase_anchor.py::test_test_after_target_or_older_than_90_days_is_not_tested, ::test_untested_resolver_output_is_bit_for_bit_pre_a290 (caso golden stale_tests)
  - test_b364_official_max_vs_working_load.py::test_untested_athletes_bit_for_bit_unchanged (caso stale_tests in b364_untested_golden.json), ::test_untested_pullup_keeps_progressing_from_feedback (usa stale_tests)
  - test_b400_retest_merge_view.py::test_real_reason_survives_the_90_day_expiry, ::test_expiry_without_a_real_skip_stays_not_tested_recently
  - test_a293_athlete_context.py::test_stale_test_flags_max_not_tested
  - test_a297_coach_athlete_context.py::test_stale_max_stays_in_the_chat_block_flagged
  - test_b413_ladder_rules.py docstring riga 17 («expired test»; il test usa un profilo mai testato, quindi resta valido)
- **Test da aggiungere:**
  - Test reale di 91 / 200 gg: tested_gate, entries_for, build_resolve_context, anchored_load e build_rotation_context restano attivi e il feedback di scala muove ancora bw_progression
  - official_max: valid_until / expired / expiring ai confini (giorno 89, 90, valid_until − 14)
  - End-to-end stile B413 con freezegun dal 20/12 al 05/01 sulla fixture di Daniele: sessioni passate identiche byte per byte, scale e carichi continui fra il 22 e il 23/12
  - Atleta mai testato (c272/a290/b364, profili senza test) identico bit per bit; self-report di onboarding sempre non testato
  - Determinismo: 100 run identiche oltre la scadenza
- **Moduli ad alto rischio:**
  - retest_policy.py (cancello letto da resolve_session via phase_anchor e bw_progression, da progression_v1.inject_targets e da planner_v2 PASS 3a attraverso la copertura di retest_decisions)
  - resolve_session.py (indiretto: cambia l'input, non il codice)
  - progression_v1.py (indiretto)
  - planner_v2.py (indiretto: copertura degli assi)
- **Effetto sugli altri utenti:** Atleti mai testati, o con solo un self-report di onboarding: bit per bit identici. Atleti con un test reale più vecchio di 90 gg: oggi sono nel regime legacy; con A restano in quello testato. Cosa cambia per loro: carichi ancorati con tetti di fase invece di 0,9 × massimale senza tetti, esercizio principale fisso per fase, scale attive (R11 li fa rientrare un livello sotto dopo 120/60 gg di stacco), policy che propone il test nelle settimane utili e promemoria delle 6 settimane nascosto. Il mirror ha solo Daniele: prima della Fase 2 serve una lettura read-only in prod per contare chi ha un test reale > 90 gg. I golden `stale_tests` (A290/B364) cambiano per scelta e ogni diff va rivisto.
- **Correzione dati in prod:** no
- **Domande:**
  - Confermi il modello A: a scadenza senza scelta resta tutto attivo e continua a progredire, con la proposta fissa sulla Today? L'alternativa è B: tutto congelato all'ultimo livello, con il feedback che non muove più niente.
  - Vale per tutti gli utenti (motore), non solo per te: ok?

#### B414-2-POSTPONE — «Posticipa la scadenza»: il rinvio A320 diventa la proroga, senza una chiave nuova

**Verdetto:** confermato · **effort** M · **rischio** medio · frontend no · schema user_state sì

- **Causa:** Il rinvio A320 così com'è non può prorogare. (1) retest_declines.py:165-168: `not_covered` (422) quando il test è scaduto. (2) :170-173: `until_after_expiry`, cioè until non può superare tested_until. (3) :175-177: `no_pending_retest` (409) quando non c'è un test in sospeso. È esattamente il caso di Daniele: dopo il 06/12 retest_policy.py:1222 (after_end) porta a not_due, e già oggi next_test è None. (4) Il rinvio agisce solo sulla programmazione (_axis_week_decision, retest_policy.py:1238-1383), mai su `tested`.
- **Evidenza:** Lo stato del mirror non ha `retest_declines` (nessun record). Il bug-inbox del 18/10 conferma che oggi un POST per Daniele darebbe 409 no_pending_retest.
- **Fix proposto:** Con il modello A il rinvio può fare da proroga. (1) Il tetto until_after_expiry diventa un tetto per singolo rinvio: until ≤ max(oggi, valid_until) + EXTENSION_MAX_D (proposta 42 gg, costante ingegneristica), errore `until_too_far`. (2) Rinvio ammesso anche senza test in sospeso, con il trigger nuovo `expiry`; chiave del record: axis + official_date + expiry. (3) `valid_until` = max(test + 89, until del rinvio attivo), letto da official_max / retest_status. Da until in poi il test torna dovuto (regola A320 esistente): è la nuova proposta. (4) Ripetibile: un nuovo rinvio sostituisce il precedente (upsert) e il router restituisce `replaced`. Audit: `previous_until` nel record più un evento append-only `retest_postponed` (storage.append_event). (5) Restano le regole A320: un test nuovo rende il record inerte, DELETE annulla, dry run senza scritture, lock per utente B371. Endpoint per asse come oggi, con due chiamate dalla UI, oppure `axes: [..]`. Motivo dalla lista chiusa A320.
- **Alternative:** Chiave nuova `test_validity_extensions`: semanticamente più pulita, ma duplica ciclo di vita, import, 422 del PUT e dry run, ed è una vera modifica di schema. Scrivere `freshness_policy.extended_until` sul test: muta la storia append-only dei test (scritta solo dai log di test) e una riapplicazione del log la perderebbe. Scartata.
- **Raccomandazione:** Estendere il postpone A320 (trigger `expiry` e tetto per singolo rinvio): un solo concetto, «non prima di X, e il massimale vale fino a X», con l'audit e l'annullamento che esistono già.
- **File:**
  - backend/engine/retest_declines.py
  - backend/engine/retest_policy.py (_DECLINE_TRIGGERS, _TRIGGER_TEXT, _active_postpone, valid_until)
  - backend/api/routers/retest.py
  - docs/API_ENDPOINTS.md
  - docs/vocabulary_v1.md
  - docs/user_guide_v1.md
  - .claude/commands/custom-session.md
  - docs/training/athlete_plan.md
- **Chiamanti e consumatori:**
  - routers/retest.py:82-130 decline (build_record, upsert, week_to_reopen)
  - retest_policy._axis_week_decision (rinvio attivo e settimane held)
  - retest_policy.retest_status (declines, next_test_reason postponed)
  - retest_declines.week_to_reopen :439 (oggi termina quando il massimale scade)
  - athlete_context.py:1669-1680 (righe RINVIATO) e _decline_lines_en
  - api/routers/user.py:61-63 (l'import accetta una lista: invariato)
  - frontend: A320-FE / B414-4
- **Test che fissano il comportamento attuale:**
  - test_a320_retest_decline.py:941-943 (not_covered, until_after_expiry nella tabella degli errori)
  - test_a320_retest_decline.py:1618 (until_after_expiry via API)
  - test_a320_retest_decline.py:1630-1637 (test_not_covered_and_no_pending_retest)
  - test_a320_retest_decline.py:430 e :1150 (commenti e attese «the max expires first»)
- **Test da aggiungere:**
  - Rinvio `expiry` senza test in sospeso, dopo la fine del ciclo: 200, valid_until spostato, nessuna sessione passata toccata
  - until oltre il vecchio tested_until accettato, oltre valid_until + 42 rifiutato con until_too_far
  - Rinvio ripetuto: il record viene sostituito, previous_until registrato, evento scritto
  - Un test nuovo rende inerte la proroga; DELETE la annulla e valid_until torna a test + 89
  - Dry run senza scritture, 409 con il piano in pausa
- **Moduli ad alto rischio:**
  - retest_policy.py (input di planner_v2 PASS 3a)
- **Effetto sugli altri utenti:** Solo per chi preme «Posticipa»: è una scelta esplicita, il default non cambia. Nessuna chiave nuova in user_state: si aggiunge il trigger `expiry` e un campo additivo nei record di `retest_declines`, senza migrazione e con schema_version invariata.
- **Correzione dati in prod:** no
- **Domande:**
  - Di quanto si posticipa a ogni tocco: scelta fra 2, 4 o 6 settimane, oppure fisso a 4?
  - Ripetibile senza un tetto totale (ogni volta è una tua scelta)?
  - Un solo bottone che posticipa insieme dita e trazione (hanno la stessa data)?

#### B414-3-DO-TEST — «Fai il test»: un percorso che piazzi davvero il test (il «Schedule test week» di A246 oggi non piazza niente a metà ciclo)

**Verdetto:** confermato · **effort** M · **rischio** medio · frontend no · schema user_state sì

- **Causa:** La conferma di A246 (week.py:1061-1068) imposta solo `initial_tests_requested`. week.py:785-790 lo usa solo nella prima settimana della fase base (is_first_week_of_phase e phase base), quindi a metà ciclo non piazza niente. Intanto la card promette «you'll find it in next week's plan» (test-reminder-card.tsx:39-43); il test di contratto controlla solo il flag (test_a246_test_reminder_contract.py:120). Inoltre `test_reminder_skipped_until` / `postponed_to` sono numeri di settimana assoluti (planner_v2.py:3759-3775, week.py:1071-1079) che start-new-cycle non azzera (macrocycle.py:162-340). Daniele ha skipped_until 18: il promemoria resta nascosto in ogni ciclo futuro, che dura al massimo 16 settimane. Per un asse coperto i test li piazza solo la policy (fine SP, inizio ciclo, 84 gg, anticipato), mai in performance o deload (retest_policy.py:1341) né dopo la fine del ciclo (:1222).
- **Evidenza:** week.py:785-790 e :1061-1068; mirror: test_reminder_skipped_until 18, postponed_to 12, initial_tests_requested assente; dopo la fine del ciclo il numero di settimana resta fermo a 13 (_current_week_num → phase_and_week_on, macro_position.py:86-89).
- **Fix proposto:** «Fai il test» a seconda dello stato. (a) Test già nel piano o proiettato: il bottone porta a quel giorno, senza scritture. (b) Ciclo finito: apre «Avvia nuovo ciclo», che già mette i test nella settimana 1 (macrocycle.py:301-302 + trigger cycle_start). (c) Altrimenti: record `kind: request` in retest_declines, che fa scattare il trigger `requested` con priorità in _trigger_for_week. Il test è dovuto dal giorno della richiesta; restano la distanza di 42 gg (già passata alla scadenza) e le guardie del giorno (72 h / 48 h, viaggio, dolore, very_hard). La richiesta vince su un rifiuto implicito della stessa settimana e il router segna stale la settimana corrente e la prossima. Per gli utenti non coperti: correggere A246 (la conferma inietta i test nella settimana dopo e il flag si consuma dopo il piazzamento; i campi del promemoria si azzerano a start-new-cycle), oppure aprirlo come bug a parte.
- **Alternative:** Riusare la conferma A246 / inject_tests: piazza dito, ripetute e trazione con il PASS 3 legacy, scavalca la policy e le regole A319 di accoppiamento, e il flag oggi non si consuma mai. Sconsigliato per gli assi coperti.
- **Raccomandazione:** Percorso (a)/(b)/(c) attraverso la policy; A246 corretto a parte per gli utenti non coperti.
- **File:**
  - backend/engine/retest_policy.py (_trigger_for_week: TRIGGER_REQUESTED)
  - backend/engine/retest_declines.py (kind request)
  - backend/api/routers/retest.py (POST request, o kind nel decline)
  - backend/api/routers/week.py (want_tests / test-reminder-response, se si corregge A246)
  - backend/api/routers/macrocycle.py (azzerare test_reminder_* a start-new-cycle)
  - docs/API_ENDPOINTS.md
- **Chiamanti e consumatori:**
  - planner_v2 PASS 3a (riceve required_sessions con trigger requested)
  - retest_status.next_test (trigger e testo)
  - key_sessions_v1._replaceable via retest_policy.is_policy_test (timbro retest:)
  - frontend TestReminderCard / nuova TestExpiryCard
- **Test che fissano il comportamento attuale:**
  - test_a246_test_reminder_contract.py (la conferma imposta initial_tests_requested; postpone/skip in numeri di settimana)
  - test_start_new_macrocycle.py T4/T5 (settimana 1 con i test, ciclo di vita del flag)
  - test_a320_retest_decline.py (rifiuto implicito: solo un'aggiunta esplicita lo toglie)
- **Test da aggiungere:**
  - Richiesta in una settimana di SP o PE: test piazzato nel primo giorno ammesso, guardie rispettate, sessioni passate intatte
  - Richiesta dopo un rifiuto implicito nella stessa settimana: la richiesta vince
  - Richiesta con il ciclo finito: nessuna scrittura, risposta cycle_ended (la UI apre il nuovo ciclo)
  - A246: la conferma a metà ciclo mette davvero i test nella settimana dopo (se si corregge qui)
  - start-new-cycle azzera test_reminder_skipped_until / postponed_to
- **Moduli ad alto rischio:**
  - retest_policy.py (input di planner_v2 PASS 3a)
  - week.py want_tests (input del planner, se si tocca A246)
- **Effetto sugli altri utenti:** Una richiesta ha effetto solo se l'atleta preme il bottone. Correggere A246 cambia il comportamento della conferma per gli utenti non coperti: oggi non fa niente fuori dalla settimana 1 della base, dopo piazzerebbe i test. Azzerare i campi del promemoria a ogni nuovo ciclo lo fa riapparire a chi l'aveva rimandato nel ciclo precedente.
- **Correzione dati in prod:** no (opzionale, solo con l'OK di Daniele: togliere test_reminder_skipped_until=18 e postponed_to=12, rimasti dal ciclo vecchio; con il modello A sono comunque irrilevanti per lui)
- **Domande:**
  - Se chiedi il test in deload o in performance, lo piazzo lo stesso (scelta esplicita, come inject_tests) o aspetto la fase successiva?
  - Correggiamo qui il «Schedule test week» di A246, che a metà ciclo non fa niente, o lo apriamo come bug a parte?

#### B414-4-UI — Card di scadenza sulla Today e RetestStatusCard (A320-FE) con «Fai il test» / «Posticipa la scadenza»

**Verdetto:** confermato · **effort** M · **rischio** basso · frontend sì · schema user_state no

- **Causa:** retest-status-card.tsx:34-46: NO_TEST_TEXT non ha `not_tested_recently`, `declined` né `postponed`. Per questo oggi Daniele legge «No test scheduled: not due yet.» (riga 81), mentre il massimale scade il 22/12. Riga 82: il testo per il test scaduto è falso («the plan schedules a fresh one at the end of a phase»: dopo la fine del ciclo non succede mai). La card vive solo nelle note collassate di /week (week/page.tsx:1125), quindi non c'è nessuna proposta sulla Today. types.ts:1463-1482 non ha tested_until, declines né plan_edit_declines. Nessun bottone: A320-FE è ancora aperto (ROADMAP_CURRENT.md:63).
- **Evidenza:** retest_status read-only del 07/11 sul mirror: finger e pulling coperti, tested_until 2026-12-22, next_test None, motivo not_tested_recently: la card renderizza «not due yet».
- **Fix proposto:** (1) `TestExpiryCard` sulla Today, non chiudibile come TestReminderCard (i due bottoni sono l'uscita). Visibile da valid_until − 14 gg, e dopo la scadenza finché non c'è una scelta. Testo prima: «Il tuo test di dita e trazione scade il gg/mm»; dopo: «scaduto il …: scale e carichi restano dove sono». Bottoni: «Fai il test» (B414-3) e «Posticipa la scadenza» (scelta delle settimane, poi dry run, riepilogo e conferma, B414-2). (2) RetestStatusCard: riga «valido fino al …» / «prorogato al …», gli stessi due bottoni, testi per not_tested_recently / after_cycle_end / declined / postponed e «Annulla rinvio» (DELETE) come azione secondaria. Il «Not now» (rifiuto) di A320-FE non va in app, per rispettare le due sole alternative: resta via API o coach. (3) Tipi TS aggiornati. (4) I dati arrivano già da retest_status nel GET /api/week, che anche la Today legge. Branch, preview Vercel e OK di Daniele prima del merge.
- **Alternative:** Riusare TestReminderCard con un nuovo tipo di payload: il test fissa l'union esatta delle opzioni e le tre risposte di A246, quindi meglio una card a parte che legge retest_status.
- **Raccomandazione:** Card dedicata sulla Today più RetestStatusCard aggiornata, nello stesso branch frontend, dopo che il backend B414-1/2/3 è su main (retrocompatibile).
- **File:**
  - frontend/src/components/training/retest-status-card.tsx
  - frontend/src/components/training/test-expiry-card.tsx (nuovo)
  - frontend/src/app/(main)/today/page.tsx
  - frontend/src/lib/types.ts
  - frontend/src/lib/api.ts (postponeRetest / requestRetest / undo)
  - frontend/src/components/training/__tests__/retest-status-card.test.tsx
  - docs/user_guide_v1.md
  - docs/FRONTEND.md
- **Chiamanti e consumatori:**
  - week/page.tsx:1125 (RetestStatusCard nelle note)
  - today/page.tsx:1404-1407 (posto accanto a TestReminderCard)
  - api.ts → POST /api/retest/decline (postpone), DELETE /api/retest/decline/{axis}, richiesta del test
- **Test che fissano il comportamento attuale:**
  - retest-status-card.test.tsx::explains why there is no next test, ::labels a projected test as the earliest day
  - lib/__tests__/test-reminder.test.ts (union delle opzioni identica al backend; nessuna chiusura silenziosa)
- **Test da aggiungere:**
  - TestExpiryCard: nascosta prima di valid_until − 14, visibile in scadenza e da scaduta, nessuna ✕, i due bottoni chiamano gli endpoint con dry run e poi la conferma
  - RetestStatusCard: valido fino al / prorogato al, testi dei motivi nuovi, Annulla rinvio
  - Errore dell'endpoint mostrato all'utente (mai fingere il salvataggio, come in A246)
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** La card compare solo agli atleti con un test reale in scadenza o scaduto. Gli altri non vedono niente di nuovo; il promemoria delle 6 settimane resta per gli assi non coperti.
- **Correzione dati in prod:** no
- **Domande:**
  - La proposta parte 14 giorni prima della scadenza, o preferisci 7?
  - Card sulla Today non chiudibile (come «Time to retest»): ok?
  - «Annulla rinvio» visibile nella card dei massimali, o solo dal coach?

#### B414-5-FRESHNESS — B-FRESHNESS-POLICY-INERT: non è la sede della scadenza; da chiudere come superato

**Verdetto:** parziale · **effort** XS · **rischio** basso · frontend no · schema user_state no

- **Causa:** Confermato che `{"stale_after_days": 90}` è scritto in progression_v1.py:2241, :2282, :2320, :2376 e non è letto da nessuno (grep su backend/engine, backend/api, scripts, frontend/src: zero letture; nei test compare solo il docstring di test_b346_dead_channels.py:4). Il resto della voce in roadmap (ROADMAP_CURRENT.md:141) è vecchio. `confidence` non è più fissa: è calcolata da B364 (progression_v1.py:2206-2217; i test di Daniele hanno 'low' calcolato con confidence_basis). La soglia dei 90 gg la applica già retest_policy.TEST_FRESH_DAYS (:67) partendo dalla data del test, non dal campo. Le righe citate dall'audit D280 (1318…) non corrispondono più.
- **Evidenza:** Mirror: ognuna delle 6 voci di tests ha freshness_policy {stale_after_days: 90} e confidence calcolata ('low' / 'high').
- **Fix proposto:** Non usarlo come sede della proroga: è un metadato statico della storia append-only dei test, che scrivono solo i log di test, mentre la proroga è una scelta dell'atleta con il suo ciclo di vita (B414-2). Togliere le 4 scritture: i test già salvati tengono il campo, che è innocuo. Il declassamento e il segnale «stale» chiesti dalla voce li coprono `expired` / `expiring` di B414-1 e la card di B414-4. Chiudere la voce in roadmap come superata da B414.
- **Alternative:** Collegarlo come sede della scadenza (`extended_until` sul test): scartato, vedi B414-2. Lasciarlo e documentarlo: zero rischio, ma resta un canale morto.
- **Raccomandazione:** Togliere le scritture e chiudere la voce come superata da B414.
- **File:**
  - backend/engine/progression_v1.py (4 righe)
  - docs/ROADMAP_CURRENT.md
  - backend/tests/test_b346_dead_channels.py (docstring)
- **Chiamanti e consumatori:**
  - progression_v1._update_test_from_log (le 4 scritture); nessun lettore
- **Test che fissano il comportamento attuale:**
  - nessuno (grep: nessuna asserzione sul campo)
- **Test da aggiungere:**
  - Un log di test non scrive più freshness_policy; un test salvato con il campo si legge ancora uguale
- **Moduli ad alto rischio:**
  - progression_v1.py (protocollo high-risk anche se la modifica è banale)
- **Effetto sugli altri utenti:** Nessuno: il campo non lo legge nessuno.
- **Correzione dati in prod:** no
- **Domande:**
  - Togliamo le 4 scritture (consigliato), o le lasciamo documentando il campo come informativo?

#### B414-6-TEXTS — Testi di coach, athlete_context e documenti sulla scadenza

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** athlete_context.py:1669: la CLI dice «massimale valido fino al». :1992: il coach legge «tested max valid until». :1983-1996: _retest_lines_en salta gli assi non coperti, quindi dopo la scadenza il coach non vede né il test né una proposta. :1896-1903: «stale or not a test». :1125-1127: warning MAX_NOT_TESTED. :1322-1324: «atleta non testato: valgono le dosi del catalogo». Poi coach/prompt_builder.py:331, user_guide_v1.md:481 («older than 90 days … nothing changes») e :576/:589, .claude/commands/custom-session.md:43-44, docs/training/athlete_plan.md:76.
- **Evidenza:** Con il test scaduto, _retest_lines_en (athlete_context.py:1985-1986: `if not row.get("covered"): continue`) non scrive niente per l'asse.
- **Fix proposto:** Righe nuove in CLI e blocco coach, solo codici e date (mai la nota): «SCADE il …», «SCADUTO il … — proponi: fai il test o posticipa la scadenza; non si azzera niente», «PROROGATO al …». Warning `TEST_EXPIRING` / `TEST_EXPIRED` al posto di MAX_NOT_TESTED per un test reale. Bump di VERSION (oggi a324.1: pin in c272, b400, a319, a320, a324). Aggiornare user guide §5 e §6, custom-session.md e athlete_plan.md. Fuori repo: runbook di climb-coach, sezione «Retest».
- **Raccomandazione:** Nello stesso brief di B414-1/2, per non lasciare il coach muto alla scadenza.
- **File:**
  - backend/engine/athlete_context.py
  - backend/coach/prompt_builder.py
  - scripts/athlete_context.py (testo dell'avviso --simulate)
  - docs/user_guide_v1.md
  - .claude/commands/custom-session.md
  - docs/training/athlete_plan.md
- **Chiamanti e consumatori:**
  - scripts/athlete_context.py (CLI letta da Claude Code e da climb-coach)
  - backend/coach/athlete_block.py (blocco della chat del coach)
  - limite di 3 500 caratteri del blocco coach (A320: la sezione retest sta già prima delle guardie)
- **Test che fissano il comportamento attuale:**
  - test_a293_athlete_context.py::test_stale_test_flags_max_not_tested
  - test_a297_coach_athlete_context.py::test_stale_max_stays_in_the_chat_block_flagged
  - pin di VERSION in test_c272_bw_ladders_catalog, test_b400_retest_merge_view, test_a319_retest_rules, test_a320_retest_decline, test_a324_rope_role_aid
- **Test da aggiungere:**
  - CLI e blocco coach con test in scadenza, scaduto e prorogato: righe presenti, nessuna nota libera, dentro il limite di caratteri
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Solo testi, per gli atleti con un test reale in scadenza o scaduto.
- **Correzione dati in prod:** no

#### B414-7-END-OF-CYCLE — Fine ciclo: il richiamo «Avvia nuovo ciclo» esiste (verificato, nessun cambio al motore)

**Verdetto:** decisione_di_design · **effort** XS · **rischio** basso · frontend no · schema user_state no

- **Causa:** Comportamento accettato da Daniele il 07/11. Verifica del richiamo: today/page.tsx:343 (`showNewCycleBanner = isViewingToday && cycleStatus.canShow`) e :1538-1559 (Banner «Final week — ready to plan your next cycle?» / «Your macrocycle is complete.», con il bottone che apre StartNewMacrocycleDialog). use-can-start-new-cycle.ts:42-64: canShow vale negli ultimi 7 giorni o dopo end_date. settings/page.tsx:235/:1611: card sempre visibile. today/page.tsx:1390-1398: «Your training plan has ended… start your next cycle» quando la settimana non si genera più (B257, week.py:677-704). Per Daniele (end_date 2026-12-06) il banner compare dal 30/11. Il nuovo ciclo mette `initial_tests_requested` e la settimana 1 con i test (macrocycle.py:301-302, start-new-macrocycle-dialog.tsx:277/362).
- **Evidenza:** Mirror: macrocycle dal 2026-09-07 al 2026-12-06, 13 settimane (deload alla 13). position_on dal 07/12 dà phase deload e after_end True; dopo la fine il numero di settimana resta fermo a 13.
- **Fix proposto:** Nessun cambio al motore. Solo documenti: la voce P3 «End-of-cycle reminder UX» (ROADMAP_CURRENT.md:423-436) è di fatto coperta da A-NEW-MACRO sulla Today e va chiusa o ridotta (mancano un banner su /plan e la chiusura, che qui non servono). END-OF-CYCLE-STUCK-IN-DELOAD va segnata come accettata: si preme «Avvia nuovo ciclo», il richiamo c'è. Nota facoltativa: todayIso usa UTC (toISOString), quindi in CET il banner cambia testo un'ora dopo la mezzanotte locale.
- **Raccomandazione:** Solo documenti. Con B414-1 la scadenza del 23/12 non spegne più niente anche se il nuovo ciclo parte tardi.
- **File:**
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - useCanStartNewCycle ← today/page.tsx:237, settings/page.tsx:235
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_start_new_macrocycle.py (T4 settimana 1 con i test, T5 ciclo di vita del flag)
- **Test da aggiungere:**
  - —
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Nessuno.
- **Correzione dati in prod:** no

**Note trasversali (analisi:scadenza-test):** Ordine consigliato. (1) Motore B414-1, high-risk: con l'OK di Daniele, su main per primo, retrocompatibile. (2) B414-2 e B414-3: backend. (3) B414-4: frontend, con branch, preview Vercel e OK. (4) B414-5 e B414-6 nello stesso brief. (5) B414-7: solo documenti.

Timeline di Daniele:
- Il ciclo finisce il 06/12 e il banner del nuovo ciclo compare dal 30/11.
- Con «Avvia nuovo ciclo» la settimana 1 contiene i test, prima del 22/12.
- Se rinuncia a quei test o avvia il ciclo dopo il 23/12, oggi si spegne tutto: scale, carichi ancorati, rotazione, coach testato. Con il modello A non si spegne niente e la card propone «Fai il test» / «Posticipa la scadenza».
- Il trigger maintenance degli 84 gg (17/12) cade dopo la fine del ciclo (retest_policy.py:1222 restituisce None): da solo la policy non proporrebbe mai il test.

Interazione con la richiesta di togliere il tetto di 5 serie (REENTRY-MAX-HANG-SETS, altra area del workflow): con il modello A, dopo uno stacco lungo e senza un working load ≤ 60 gg, il max hang parte dal target di fase calcolato sul massimale vecchio, senza nessun tetto di rientro. Non è meno prudente di oggi: il ramo legacy prescriveva dallo stesso massimale (baseline × 0,9 senza tetti di fase). Le scale hanno già R11: con un gap oltre 120 o 60 gg si riparte un livello sotto.

Invarianti:
- Nessuna modifica a macrocycle_v1, generate_macrocycle o start_date: from_phase e lunedì non sono toccati.
- Passato immutabile: le prescrizioni delle sessioni fatte sono congelate (B413 D2) e il router A320 non tocca mai sessioni passate. Va comunque fissato con un end-to-end oltre il 23/12.
- Determinismo: tutte le date sono passate come argomento, nessun today() nel motore.
- Equipaggiamento e Fontainebleau: non toccati.

Prima della Fase 2 serve una lettura read-only in prod per contare gli utenti con un test reale > 90 gg: con il modello A cambiano regime. Il mirror contiene solo Daniele.

Trovato strada facendo, fuori dall'area ma collegato: il «Schedule test week» di A246 a metà ciclo non piazza niente, e i campi del promemoria (numeri di settimana assoluti) sopravvivono al cambio di ciclo. Per Daniele skipped_until=18 lo nasconde in ogni ciclo futuro.

Nessun pytest eseguito, nessuna scrittura: solo snippet python read-only sul mirror (/Users/danielesomensi/Projects/climb-state-mirror/data/state_latest.json) e lettura del codice nel worktree /Users/danielesomensi/Projects/climb-agent-b414.

### pin-e-fallback

#### B381-FALLBACK — Catena di pin ordinata per blocco nel resolver (fallback_exercise_ids + esito finale dichiarato): il meccanismo unico che chiude anche GOBLET e B261-TEST-FALLBACK

**Verdetto:** confermato · **effort** M · **rischio** medio · frontend no · schema user_state no

- **Causa:** Un pin oggi è un solo id. Ramo inline: resolve_session.py:1194-1247. Se il pin passa `_pin_equipment_ok` (resolve_session.py:283-296) viene preso e salta TUTTI gli altri filtri P0 (luogo, età, esperienza, limitazioni, intensity_max). Se fallisce ci sono solo tre esiti, decisi dal codice e non dal catalogo: (1) pin con ruolo test → blocco saltato (B261, :1217-1226); (2) `pin_strict` → blocco fallito (C274, :1227-1240, solo inline); (3) altrimenti P0 generico sui filtri del blocco (:1241-1247, poi :1260-1329). Ramo template: resolve_session.py:2075-2157, stessi esiti senza `pin_strict`. Non esiste un secondo candidato dichiarato, per cui un pin che manca l'attrezzatura finisce su una scelta del filtro che ruota per settimana e segue la storia recente. Prova (simulazione in sola lettura su una copia, scratchpad): con il pin a back_squat e un bilanciere obbligatorio, alla palestra Bkl (solo manubri) P0 sceglie cossack_squat, non il goblet. Nei template c'è anche un vocabolario `selection.fallbacks` che il resolver non legge mai (general_warmup.json:50, finger_max_strength.json:53/112/206; il ramo template legge solo role/domain/pattern a :2117-2119).
- **Fix proposto:** Un solo helper puro `_resolve_pin_chain(spec, exercises, available_equipment, limitation_map)`, usato sia dal ramo inline sia dal ramo template al posto dei due blocchi if/elif attuali.

Schema del catalogo, additivo. Inline: in `selection.primary`. Template: sul blocco, accanto a `exercise_id`.
- `fallback_exercise_ids: [..]`: lista ordinata di candidati dopo `exercise_id`.
- `pin_exhausted: "p0" | "skip" | "fail"`: cosa succede se nessun candidato passa. Default `p0`, il comportamento B261 di oggi. `pin_strict: true` resta come alias di `fail`, così nessun blocco C274/C276 va migrato.

Algoritmo, deterministico:
1. I candidati sono `[exercise_id] + fallback_exercise_ids`, deduplicati e nell'ordine del catalogo. Un id che manca dal catalogo va loggato e saltato.
2. Vince il primo candidato che passa il gate. Il gate è `_pin_equipment_ok`, più `active` diverso da false; le limitazioni gravi solo se Daniele le approva, vedi domanda.
3. Recency, seed settimanale, rotazione e luogo non contano: «stesso movimento ogni volta».
4. Se nessuno passa: un primo pin con ruolo test → skip (B261, invariato). Altrimenti `fail`/`pin_strict` → blocco failed (C274). `skip` → blocco saltato. `p0` → P0 coi filtri del blocco, che non vengono mai aggirati.

`chosen_by` resta `explicit_exercise_id` per qualunque candidato della catena. Così restano identici il `picked_by`, la fase ladder_pin (:1349-1351), l'esclusione della scala A298 (:1333/:2161) e quella degli override A290 (:1386/:2188). L'indice del candidato e gli scarti con il motivo vanno in `p0_trace`, che i golden scartano. Aggiungere a `pin_strict` il ramo template, che oggi manca.

Lint di catalogo in un test: ogni id di fallback esiste, è attivo, non è library-only, soddisfa i filtri del blocco (role/domain/pattern/intensity_max) e chiede un'attrezzatura diversa dai candidati prima di lui. Un primo pin di test non può avere fallback (mai sostituire una misura).

Blocchi che ne beneficiano, controllati su tutti i 222 pin:
- legs_maintenance_lunch.squat_main [back_squat, goblet_squat]: serve ora.
- I due blocchi 2RM con `pin_exhausted: skip`, vedi B261-TEST-FALLBACK.
- Nessun altro serve oggi. upper_push_arms_lunch.chest_press: dumbbell_bench_press passa sempre dove c'è il bilanciere, che implica i manubri (equipment_utils.py:85-92). warmup_strength.hang_rampup e la warmup_specific dei test LP: P0 sceglie già finger_warmup_generic. heavy_conditioning_gym.core_compression (pin senza filtri: se fallisse, P0 sceglierebbe qualunque cosa) è solo in palestra, dove la sbarra è implicita (:1897-1899): rischio latente, candidabile [ab_wheel_rollout, v_up]. warmup_climbing.climbing_activation nelle sessioni solo-vie: P0 dà wall_slide, ma nel catalogo non c'è un riscaldamento su vie da mettere in catena, quindi servirebbe prima un brief C.
- **Alternative:** (a) Cambiare solo il pin, come in B381: scartata, perché senza bilanciere si finisce su cossack_squat (verificato). (b) Riusare `selection.fallbacks` dei template: scartata, è una lista di filtri a tag che il resolver non legge e il nome si confonde. (c) Una preferenza di esercizio per utente: richiede un cambio di schema di user_state, rinviata.
- **Raccomandazione:** Un solo helper per i due rami del resolver, chiavi additive con default = comportamento di oggi, label di picked_by invariata (golden stabili), lint di catalogo che verifica le catene in modo statico. Per ora un solo uso reale (gambe) più l'esito skip dei 2RM; gli altri blocchi solo se ricompare un caso.
- **File:**
  - backend/engine/resolve_session.py
  - backend/tests/test_b414_pin_chain.py (nuovo)
  - backend/tests/test_c269_exercise_reachability.py (_session_pinned_ids legge anche fallback_exercise_ids)
  - docs/vocabulary_v1.md (accanto a :1021 pin_strict)
  - docs/ENGINE_ARCHITECTURE.md (Resolution flow, passo 6, :378-381)
  - docs/ROADMAP_CURRENT.md (:85 chiudere B381-FALLBACK)
- **Chiamanti e consumatori:**
  - resolve_session._resolve_inline_block — pin a resolve_session.py:1194-1247
  - resolve_session.resolve_session ramo template — pin a resolve_session.py:2075-2157
  - Chi legge chosen_by dentro il resolver: ladder_pin :1349-1351, scala A298 :1333/:2161, override di rotazione A290 :1386/:2188, deload :1388-1392 (solo inline), status failed :1462-1467, resolution_status :2361-2363
  - Chiamanti di resolve_session (comportamento invariato senza le chiavi nuove): week._auto_resolve (backend/api/routers/week.py:143-200), replanner/custom/composer tramite resolve_session
  - picked_by e resolution_status non hanno lettori runtime fuori dal resolver, solo nei test (grep su backend/api, backend/engine, frontend/src)
  - Il frontend legge resolved_session.blocks/exercise_instances (session-card.tsx:283, :1080) senza interpretare chosen_by
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b261_pin_equipment_fallback.py (tutto: pin non-test → P0, pin di test → skip, P0 a zero → skip, immutabilità)
  - backend/tests/test_resolve_real_sessions.py:23, :301-343 (picked_by explicit_exercise_id, pin_strict)
  - backend/tests/test_c274_lunch_complementary_catalog.py (HIIT senza tapis roulant fallisce, mai degradato)
  - backend/tests/test_c276_tryhard_catalog.py (pin strict delle vie)
  - backend/tests/test_b413_lunch_core_ladder.py:162 (picked_by explicit_exercise_id), :168-201 (digest legs pre-B413)
  - backend/tests/test_c269_exercise_reachability.py:152-163
  - backend/tests/fixtures/c272_resolver_golden.json + c272_golden_cases.py (traccia scartata dal digest)
- **Test da aggiungere:**
  - Catena: il primo candidato che passa l'attrezzatura vince. Con bilanciere → back_squat, solo manubri → goblet_squat, senza pesi → P0 coi filtri del blocco
  - Ordine fisso: un candidato nei recent_ex_ids viene preso lo stesso. Due risoluzioni identiche (determinismo)
  - Un id di fallback che manca dal catalogo va loggato e saltato al successivo
  - Esiti finali p0 / skip / fail su entrambi i rami (inline e template). pin_strict resta alias di fail. Un primo pin di test esaurito → skip anche con pin_exhausted p0
  - picked_by resta resolver_v0.2/explicit_exercise_id per ogni candidato; p0_trace porta pin_index e scarti
  - ladder_pin funziona su un blocco con catena
  - Lint di catalogo: fallback esistenti, attivi, non library-only, conformi ai filtri del blocco, con attrezzatura diversa; nessun fallback su un primo pin di test
  - Golden: c272 e PRE_B413_LEGS_DIGESTS invariati per i profili senza bilanciere
  - (se approvato) gate delle limitazioni gravi: un candidato controindicato viene scartato
- **Moduli ad alto rischio:**
  - backend/engine/resolve_session.py (filtri P0 e risoluzione dei template)
- **Effetto sugli altri utenti:** Senza le chiavi nuove l'uscita resta identica per tutti, compresi i pin_strict (alias). Cambia solo dove il catalogo dichiara una catena o un esito finale, cioè la gamba del pranzo e i due blocchi 2RM: gli effetti sono negli altri due item. Se si approva anche il gate delle limitazioni gravi su tutti i pin, chi ha una limitazione grave perde i pin controindicati (bulgarian_split_squat, pushup, max_hang_7s, weighted_pullup…) a favore di P0 o di uno skip.
- **Correzione dati in prod:** no
- **Domande:**
  - Il gate dei candidati controlla solo l'attrezzatura, come i pin di oggi, o anche le limitazioni gravi (P0 Stage 6, resolve_session.py:715-721)? Se le limitazioni: (a) solo sui blocchi con catena, consigliato ora, oppure (b) su tutti i pin? La (b) chiude un'elusione di P0 che esiste già oggi, ma cambia per gli utenti con limitazioni gravi.
  - Nomi delle chiavi: `fallback_exercise_ids` (quello in roadmap) e `pin_exhausted` (p0|skip|fail), con `pin_strict` tenuto come alias. Ti vanno bene?

#### INBOX-2026-11-04-GOBLET — legs_maintenance_lunch: back squat per chi ha il bilanciere, goblet senza (attrezzatura, mai il luogo), con lo scarico fatto dal motore

**Verdetto:** confermato · **effort** M · **rischio** medio · frontend sì · schema user_state no

- **Causa:** Il blocco squat_main fissa `goblet_squat` senza alternative (legs_maintenance_lunch.json:57-85, pin a :64). back_squat chiede solo `["weight"]` (exercises.json:13600, equipment_required a :13614), e qualunque manubrio implica `weight` (equipment_utils.py:85-92). Quindi, anche fissando back_squat, l'attrezzatura non distingue chi ha il bilanciere da chi ha solo manubri. Il bilanciere invece non è mai implicato: WEIGHT_SUBTYPES lo espande solo verso weight e dumbbell (equipment_utils.py:27-31). Una rigenerazione rimette il goblet: le sessioni pianificate vengono risolte a ogni GET (week.py:157-200), mentre le custom attuali (12/11, 19/11, 26/11, 01/12) sono fuori dal resolver e non ricevono `deload_sets` (_apply_deload_sets, resolve_session.py:78-107 e :1388-1392). Simulazione in sola lettura sulla copia del mirror: con pin back_squat e bilanciere obbligatorio, a Work (3c7f08e0, che ha il bilanciere) esce back_squat 5×6, col carico dal suo working_load. Il 01/12 (scarico) esce 4 serie (stored_sets 5). A Bkl (solo manubri), senza catena, esce cossack_squat.
- **Fix proposto:** Catalogo, usando il meccanismo di B381-FALLBACK:
1. back_squat: `equipment_required` passa da ["weight"] a ["barbell"]. È il precedente B380 di bench_press e barbell_row (exercises.json:1737, :3298).
2. squat_main: `exercise_id: back_squat`, `fallback_exercise_ids: ["goblet_squat"]`. Esito finale p0, come oggi. Le `prescription_overrides` restano le stesse (5×6, deload_sets 4, 120").
3. Riscrivere le note: intent.notes e note del blocco («back squat col bilanciere, goblet squat senza»; scarico «squat 4 serie»).

Il `version` della sessione resta 1.3: entra nel digest e romperebbe PRE_B413_LEGS_DIGESTS. Il piano (planner_v2.py:91, required_equipment [dumbbell]) non si tocca. back_squat ha intensity medium come il goblet, quindi tag e cap restano uguali (STALE_CUSTOM_TAGS non scatta). Il session_load_score sale di 3 punti (fatigue_cost 6 contro 4).

Carichi:
- back_squat legge working_loads.entries['back_squat']. Daniele ce l'ha già (corretto il 04/11), goblet_squat no.
- Non ci sono conversioni goblet↔back squat: non sono una coppia BARBELL_DUMBBELL (load_units.py:32-36) e B363 ha tolto il gruppo squat (progression_v1.py:113-124).
- Unità: back_squat è `total` (nessun suggested.load_unit), il goblet resta `implement` (B380).
- measure_kind: dp_reps per entrambi.
- anchored_load non si applica: copre solo 4 esercizi (anchored_load.py:58).
- Per chi ha il bilanciere ma nessun carico di back squat, la partenza a freddo è 0,15×BW (progression_v1.py:1887-1893, back_squat assente da :51-74): circa 11 kg, meno del bilanciere vuoto. Vedi domanda.

Documenti da aggiornare: user_guide_v1.md:749; :146, che ha già numeri vecchi (dice goblet 3 serie, il catalogo dice 4); vocabulary_v1.md:987. Testo in-app opzionale: frontend/src/lib/guide-content.tsx:408.
- **Alternative:** (a) Solo cambio di pin, come B381: senza bilanciere si finisce su cossack_squat (verificato). (b) Una preferenza utente per l'esercizio: cambio di schema. (c) Due sessioni gambe (bilanciere / manubri) scelte dal planner: tocca planner_v2 e duplica il catalogo. (d) Aggiungere «home» a location_allowed di back_squat, coerente col principio dell'attrezzatura ma fuori scope (il pin aggira già il luogo, come tutti i pin).
- **Raccomandazione:** back_squat chiede il bilanciere, più la catena [back_squat, goblet_squat]: tutto dal catalogo, a parte il resolver di B381-FALLBACK. Lasciare le custom già messe. Decidere la partenza a freddo prima della Fase 2.
- **File:**
  - backend/catalog/sessions/v1/legs_maintenance_lunch.json
  - backend/catalog/exercises/v1/exercises.json (back_squat equipment_required)
  - backend/tests/test_c274_lunch_complementary_catalog.py (EXPECTED :72-74: back_squat al posto del goblet; l'ordinamento per id lo porta prima del bulgarian)
  - backend/tests/test_c275_lunch_harder.py (LOADED_PINS :61, più il fallback goblet con dumbbell_cable)
  - backend/tests/fixtures/b413_lunch_ladder_golden.json (le 6 chiavi daniele|*|legs_maintenance_lunch, rigenerate e motivate nella docstring di b413_lunch_golden_cases.py)
  - backend/tests/test_b414_pin_chain.py (nuovo)
  - docs/user_guide_v1.md
  - docs/vocabulary_v1.md
  - (se approvato) backend/engine/progression_v1.py (costante di partenza a freddo)
  - (opzionale) frontend/src/lib/guide-content.tsx:408
- **Chiamanti e consumatori:**
  - resolve_session._resolve_inline_block (unico lettore del pin di sessione)
  - Pool P0 di ogni blocco squat (legs_strength, lower_body_gym…), adhoc_builder, coach session_composer (pool A259), body_part_picker, custom-session builder: tutti filtrano su equipment_required, quindi back_squat sparisce per chi non ha il bilanciere
  - progression_v1.inject_targets ramo external_load (:1847-1903) e measured_feedback.measure_kind (:155-184): leggono il catalogo, nessun cambio di codice
  - exercise_ordering.sort_exercises_by_phase: a parità ordina per id, quindi back_squat prima di bulgarian_split_squat
  - week._auto_resolve (week.py:143-156): done, skipped e sessioni modificate non vengono mai ri-risolte (B120/B153b)
  - complementary_v1.py:76 (famiglia legs) e planner_v2.py:91: invariati
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_c274_lunch_complementary_catalog.py:72-74 (lista con goblet_squat a WORK_GYM, che ha il bilanciere)
  - backend/tests/test_c275_lunch_harder.py:61 e :140-146 (pin squat_main = goblet_squat)
  - backend/tests/test_a312_deload_sets.py:30, :92 (squat_main 5→4: resta valido)
  - backend/tests/fixtures/b413_lunch_ladder_golden.json, chiavi daniele|… (gym Work col bilanciere: cambiano)
  - backend/tests/fixtures/c272_resolver_golden.json, chiavi legs (profili senza bilanciere: devono restare uguali)
  - backend/tests/test_b413_lunch_core_ladder.py:168-201 (PRE_B413_LEGS_DIGESTS: devono restare uguali)
  - backend/tests/test_b380_load_units.py:184-195, :236
  - backend/tests/test_a253_adhoc_load_anchor.py:128-135 (back_squat senza ancora: resta verde)
  - backend/tests/test_c269_exercise_reachability.py (goblet resta raggiungibile)
- **Test da aggiungere:**
  - Palestra Work-like col bilanciere → back_squat 5×6 a 120". In scarico 4 serie (stored_sets 5)
  - Solo manubri (Bkl-like) → goblet_squat 5×6, mai cossack/split. Senza pesi → P0 squat coi filtri
  - _pin_equipment_ok(back_squat, expand_equipment(["dumbbell"])) è False, con ["barbell"] è True
  - Il carico di back_squat viene dal working_load. Nessun suggested.load_unit (total); il goblet resta implement
  - Durata entro 55' in ogni fase con WORK. Determinismo
  - Immutabilità: una sessione done del passato con goblet_squat resta byte per byte uguale dopo la rigenerazione; quella pianificata passa a back_squat
  - (se approvato) partenza a freddo di back_squat ≥ 20 kg / k×BW
- **Moduli ad alto rischio:**
  - backend/engine/resolve_session.py (tramite il meccanismo B381-FALLBACK)
  - backend/engine/progression_v1.py (solo se si approva la costante di partenza a freddo)
- **Effetto sugli altri utenti:** Chiunque abbia il bilanciere nel luogo dove la sessione viene risolta riceve back_squat al posto del goblet nel pranzo gambe. Si raggiunge con gli slot pranzo A300 o con il quick-add: è supplementary, il planner non la mette da solo. Chi non ha un working_load di back squat parte da 0,15×BW, salvo correzione. Chi ha solo manubri o pesi senza bilanciere continua col goblet, digest invariati. back_squat esce dai pool P0, ad-hoc, composer e body-part per chi non ha il bilanciere (giusto: è «Barbell back squat»). Nessun golden c272/a290 lo sceglie oggi (0 occorrenze). Quanti utenti hanno il bilanciere va contato in Fase 2 con una lettura admin GET.
- **Correzione dati in prod:** no. Le custom di Daniele (cs_89e2a6e6 12/11, cs_9f27d87a 19/11 e 26/11, cs_5853e508 01/12, già scaricata a mano) sono corrette e restano. Sostituirle con la sessione di catalogo è opzionale: remove_session + add con dry_run e OK di Daniele, non consigliato. La sessione done del 03/11 resta col goblet nel resolved (immutabile; il log è già corretto).
- **Domande:**
  - Confermi back squat come prima scelta per TUTTI quelli che hanno il bilanciere dove fanno il pranzo, e goblet solo senza?
  - Stessa dose del goblet: 5×6 RIR 1-2, 120", 4 serie in scarico?
  - Partenza a freddo di back_squat per chi non ha un carico registrato: oggi circa 11 kg (0,15×BW). Aggiungo una costante in progression_v1, per esempio 0,40×BW come lo stacco rumeno, o almeno 20 kg (il bilanciere vuoto)? Oppure lascio com'è? Tocca un modulo ad alto rischio, anche se è solo un dato.
  - Testo della guida in-app (guide-content.tsx:408, «goblet squat»): lo aggiorno in questo brief (diventa misto, serve la preview Vercel) o lo rimando?

#### B261-TEST-FALLBACK — Test 2RM: un weighted_pullup fissato senza pesi non va mai sostituito da un'altra trazione

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** I blocchi di misura del 2RM fissano `weighted_pullup`, che ha ruolo `main` e non `test`: pulling_strength_test.json:15-28 (template) e test_max_hang_pullup.json:74-90 (inline pullup_2rm_test). `_is_test_exercise` guarda solo il ruolo dell'esercizio (resolve_session.py:298-302), quindi senza `weight` entrambi i rami vanno a P0 (template :2107-2157, inline :1241-1247). Verificato in sola lettura: test_max_weighted_pullup e test_max_hang_pullup in una palestra con sbarra e trave ma senza pesi danno `power_pullups_explosive` con `test_protocol: 2RM` nella prescrizione e resolution_status success. A319(d) evita il caso a livello di planner (_SESSION_META chiede pullup_bar+weight, planner_v2.py:64/69), ma restano quick-add, cambio palestra e override di attrezzatura. Gli unici due blocchi del catalogo con `prescription.test_protocol` sono proprio questi due.
- **Fix proposto:** Con l'helper di B381-FALLBACK, aggiungere `pin_exhausted: "skip"` a pulling_strength_test.main e a test_max_hang_pullup.pullup_2rm_test, senza fallback: una misura non si sostituisce mai. Senza pesi il blocco viene saltato come i pin di test B261. Il resto della sessione resta: L-sit, sospensione massimale e misure secondarie della combinata. Per il template va aggiunto il supporto all'esito finale, che oggi manca. Lint di catalogo: ogni blocco con `prescription.test_protocol` o con un pin di ruolo test dichiara skip/fail, mai p0. Il ciclo chiuso non cambia: col sostituto non si scriveva comunque nessun massimale (roadmap :87), adesso non si registra nemmeno un carico di lavoro su un esercizio estraneo.
- **Alternative:** (a) Regola implicita «sessione di test → ogni pin esaurito salta»: meno legata ai dati, toglierebbe anche i ripieghi legittimi dei riscaldamenti e del prehab. (b) Dare a weighted_pullup il ruolo test: impossibile, è un esercizio di allenamento ovunque.
- **Raccomandazione:** `pin_exhausted: skip` sui due blocchi 2RM, nessun fallback, lint su test_protocol.
- **File:**
  - backend/catalog/templates/v1/pulling_strength_test.json
  - backend/catalog/sessions/v1/test_max_hang_pullup.json
  - backend/engine/resolve_session.py (esito finale nel ramo template, stesso helper di B381-FALLBACK)
  - backend/tests/test_b414_pin_chain.py (nuovo)
  - docs/vocabulary_v1.md
  - docs/ROADMAP_CURRENT.md (:87 chiudere B261-TEST-FALLBACK)
- **Chiamanti e consumatori:**
  - resolve_session ramo template :2075-2157 (pulling_strength_test, usato da test_max_weighted_pullup)
  - resolve_session._resolve_inline_block :1194-1247 (test_max_hang_pullup)
  - week._auto_resolve, replanner quick-add e change_gym (replanner_v1.py:1867, :2060 controllano required_equipment a livello di sessione: invariati)
  - progression_v1._update_test_from_log: scrive il massimale solo dal weighted_pullup loggato, un blocco saltato non porta nessuna riga
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b261_pin_equipment_fallback.py:129-160 (TestB261TestPinGuard: pin di test saltato, resolution success)
  - backend/tests/test_a319_retest_rules.py:978-1000 (coi pesi c'è il vero 2RM, mai archer_pullup/dip)
  - Nessun test fissa oggi la sostituzione senza pesi; i golden c272/a290 escludono le sessioni test_*
- **Test da aggiungere:**
  - test_max_weighted_pullup in una palestra senza pesi: blocco main saltato, nessun power_pullups_explosive/dip/archer_pullup, L-sit presente
  - test_max_hang_pullup senza pesi: pullup_2rm_test saltato, max_hang_7s e misure secondarie presenti nell'ordine A319
  - Coi pesi: uscita identica a oggi (A319)
  - Lint: ogni blocco con test_protocol o con un pin di test ha esito skip/fail
- **Moduli ad alto rischio:**
  - backend/engine/resolve_session.py
- **Effetto sugli altri utenti:** Solo chi risolve un test trazione senza pesi (quick-add, cambio palestra, override): vede la sessione senza il blocco 2RM invece di una trazione esplosiva con le note del 2RM. Il blocco non spiega in pagina perché manca: il testo è il residuo frontend [[A319-FE]]. Nessun cambio con i pesi.
- **Correzione dati in prod:** no
- **Domande:**
  - Senza pesi il 2RM va saltato (come i pin di test B261: la sessione resta «success», consigliato) o fallito (come C274: resolution_status «failed», oggi senza effetti visibili in UI)?

**Note trasversali (analisi:pin-e-fallback):** Un solo meccanismo copre i tre punti: una catena di pin ordinata per blocco più un esito finale dichiarato nel catalogo.
- GOBLET = catena [back_squat, goblet_squat] + back_squat che chiede il bilanciere.
- B381-FALLBACK = il meccanismo stesso.
- B261-TEST-FALLBACK = esito `skip` sui due blocchi 2RM.

Un solo helper per i due rami del resolver (inline resolve_session.py:1194-1247, template :2075-2157). Il `picked_by` resta `explicit_exercise_id` e il dettaglio va in `p0_trace`: i golden c272/a290 e PRE_B413_LEGS_DIGESTS restano identici per chi non ha il bilanciere. Cambiano solo le 6 chiavi daniele del golden b413 e due liste attese nei test C274/C275. Il `version` di legs_maintenance_lunch non va alzato.

Invarianti:
- Sessioni passate immutabili: done, skipped e modificate non vengono mai ri-risolte (week.py:143-156). Il 03/11 resta goblet.
- Determinismo: l'ordine viene dal catalogo, il gate guarda solo attrezzatura (ed eventualmente le limitazioni). Niente recency né seed.
- Filtro per attrezzatura, mai per luogo: il gate è `_pin_equipment_ok`. back_squat ha location_allowed [gym], ma i pin non leggono il luogo, come già oggi.
- Fontainebleau, from_phase="current" e invariante del lunedì: non toccati.

Nessuna modifica a planner_v2, replanner_v1, macrocycle_v1, closed_loop_v1 né allo schema di user_state. progression_v1 si tocca solo se Daniele approva la partenza a freddo del back squat. È alto rischio solo resolve_session.py: Fase 1, STOP, poi l'OK.

Il cambio di attrezzatura di back_squat non tocca stress_tags/pattern/role/domain/intensity_level: nessuna riallineazione B395.

Fase 2:
- contare in sola lettura gli utenti con il bilanciere che hanno slot pranzo o quick-add;
- aggiornare i documenti (vocabulary_v1, ENGINE_ARCHITECTURE passo 6, user_guide :146, che è già vecchio, e :749; ROADMAP_CURRENT :85 e :87; spuntare l'item nella bug-inbox);
- frontend solo se Daniele vuole il testo della guida, e allora preview Vercel.

Residui da aprire, fuori scope:
- `deadlift` chiede solo `weight` (un deadlift classico coi manubri), stessa incoerenza che back_squat aveva;
- `selection.fallbacks` nei template è un dato morto, mai letto (general_warmup.json:50, finger_max_strength.json:53/112/206);
- nessun riscaldamento su vie nel catalogo per le palestre senza boulder (P0 dà wall_slide);
- heavy_conditioning_gym.core_compression ha un pin senza filtri, rischio latente.

Le simulazioni sono state fatte in sola lettura su copie nella scratchpad (/private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/exp1.py, exp2.py, exp3.py, pins.py), senza pytest. Il worktree /Users/danielesomensi/Projects/climb-agent-b414 è rimasto pulito.

### power-endurance-gym

#### INBOX-2026-11-02-a — power_endurance_gym risolve sempre due blocchi PE: il ripiego pe_boulder non è mai un ripiego

**Verdetto:** confermato · **effort** S · **rischio** medio · frontend no · schema user_state no

- **Causa:** Il resolver non conosce blocchi alternativi. Di un modulo inline legge solo block_id, selection, module_role, prescription, ladder_pin e order (resolve_session.py:1178-1182, 1348, 1370, 1444): `required` e `priority` sono campi morti (nessun lettore in engine/api), quindi ogni blocco inline viene risolto. Il filtro `equipment: [gym_routes]` di pe_routes è solo una preferenza (Stage 2b, resolve_session.py:565-570): senza vie ricade su tutti i PE boulder. Poi l'esclusione degli esercizi già usati nella sessione (phase_anchor.py:766 per i testati, resolve_session.py:1453-1454 + Stage 3b :651 per i non testati) fa scegliere a pe_boulder un SECONDO esercizio PE diverso. Catalogo: power_endurance_gym.json:37-87 (le note dicono «fallback when routes unavailable», ma nessun meccanismo lo applica). Riprodotto in sola lettura sul mirror del 07/11, fase PE, data 03/11: Cocque, D-Summit ed Escale danno route_intervals + linked_boulders; Boulder Forest, Bkl, Eifelblock e Cocque «solo boulder» (override B313) danno linked_boulders + linked_boulders_circuit. Profilo non testato: Cocque route_intervals + four_by_four_bouldering, Boulder Forest four_by_four_bouldering + thirty_thirty_intervals. Il doppione c'è per tutti gli utenti.
- **Evidenza:** Snippet in sola lettura (resolve_session con write_output=False, stato del mirror state_latest.json del 07/11): i risultati per palestra sono quelli in root_cause. Prototipo del blocco unico in scratchpad proto_sessions/power_endurance_gym.json.
- **Fix proposto:** Opzione A, solo catalogo (raccomandata): unire pe_routes e pe_boulder in un solo blocco `pe_main` (rotation phase_anchor, role main, domain power_endurance/anaerobic_capacity, pattern climbing_intervals, equipment [gym_routes] come preferenza soft). La preferenza già esistente fa quello che la nota promette: con le vie route_intervals, senza un solo PE boulder. Prototipo in scratchpad verificato: Cocque → route_intervals; Boulder Forest, Bkl, Eifelblock e Cocque solo boulder → linked_boulders; non testato a Boulder Forest → four_by_four_bouldering. Le guardie del surface-override (_primary_block_survived, _rope_free) restano soddisfatte. Volendo, si aggiunge `anchor_priority` per fissare il ripiego boulder (per esempio 4x4 per primo). Opzione B, resolver (alto rischio): una chiave nuova (`equipment_strict` o un gruppo alternativo) che rende rigido il filtro di pe_routes e tiene pe_boulder sempre. Nelle palestre con vie resterebbe route_intervals + un PE boulder; senza vie un solo PE boulder.
- **Alternative:** Opzione B (resolver: equipment_strict o gruppo alternativo) se vuoi tenere vie + boulder insieme; opzione C: lasciare tutto com'è e correggere solo le note del catalogo (non risolve i doppioni).
- **Raccomandazione:** Opzione A: risolve i doppioni per tutti senza toccare il codice del resolver. Le golden si rigenerano dopo il diff dell'output grezzo, come in C283/B406.
- **File:**
  - backend/catalog/sessions/v1/power_endurance_gym.json
  - backend/tests/test_b157_pe_equipment_gate.py
  - backend/tests/test_a290_phase_anchor.py
  - backend/tests/test_c261_pulling_maintenance_block.py
  - backend/tests/test_session_enrichment.py
  - backend/tests/fixtures/c272_resolver_golden.json
  - backend/tests/fixtures/a290_untested_golden.json
  - backend/tests/fixtures/b413_lunch_ladder_golden.json
  - backend/tests/c272_golden_cases.py
  - backend/tests/a290_untested_cases.py
  - docs/user_guide_v1.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - backend/engine/resolve_session.py:_resolve_inline_block (1149-1485) e pick_best_exercise_p0 Stage 2b (565-570)
  - backend/engine/phase_anchor.py:plan_block/select_from_pool (rotation phase_anchor del blocco)
  - backend/api/routers/week.py:_auto_resolve (108-200): le sessioni pianificate si ririsolvono a ogni GET /api/week; done/skipped/_user_edited no (145-150, B120/B153b)
  - backend/api/routers/session.py:/resolve (66-98), _resolve_for_slot, surface_override (_boulder_equipment_override, _primary_block_survived, _rope_free)
  - backend/engine/planner_v2.py:44 _SESSION_META.power_endurance_gym (preferred_equipment gym_routes, invariato)
  - backend/engine/key_sessions_v1.py chiave power_endurance (dose presence, families power_endurance: route_intervals e i PE boulder sono in stimulus._POWER_ENDURANCE_IDS)
  - backend/engine/load_score: session_load_score cala (un esercizio fatigue 8 in meno)
  - frontend/src/lib/session-blocks.ts:walkResolvedBlocks (ordine dei blocchi nel player e nella card)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b157_pe_equipment_gate.py:66-84 (cerca block_id 'pe_boulder' o id vecchi tipo 'boulder_4x4')
  - backend/tests/test_a290_phase_anchor.py:280-288 test_pe_blocks_fixed_for_the_phase (_pick 'inline.pe_boulder')
  - backend/tests/test_c261_pulling_maintenance_block.py:98-108 TestPlacement (elenco pe_boulder/pe_routes)
  - backend/tests/test_session_enrichment.py:190-225 (route_intervals con vie / assente senza: resta vero)
  - backend/tests/test_resolver_p0.py:288-295 (≥3 esercizi, blocchi inline: resta vero)
  - backend/tests/test_b313_surface_override.py:170-183 (PE solo boulder senza vie: resta vero)
  - golden c272 (6 chiavi power_endurance_gym), a290_untested (2 digest), b413 (chiavi PE)
- **Test da aggiungere:**
  - power_endurance_gym con gym_routes: un solo esercizio climbing_intervals PE, ed è route_intervals (testato e non testato)
  - senza gym_routes e con equipment_override solo boulder: un solo PE boulder, nessun doppione (stimulus power_endurance presente)
  - guardia di catalogo: nessuna sessione con due blocchi primary che possano risolvere lo stesso pattern+dominio senza un filtro di attrezzatura rigido
- **Moduli ad alto rischio:**
  - resolve_session (output cambiato dal catalogo; con l'opzione B codice in resolve_session.py)
- **Effetto sugli altri utenti:** Per ogni utente la power_endurance_gym perde un blocco PE: nelle palestre con vie solo route_intervals, altrove un solo PE boulder. La sessione si accorcia e session_load_score scende. Le sessioni passate (done/skipped/modificate) non si toccano. Le PE pianificate cambiano al prossimo GET /api/week. Per Daniele non si vede subito: la fase PE finisce il 09/11 e nelle settimane 09/11-06/12 del mirror non c'è nessuna power_endurance_gym.
- **Correzione dati in prod:** no
- **Domande:**
  - Nelle palestre con le vie vuoi solo route_intervals (opzione A, solo catalogo) o route_intervals + un PE boulder (opzione B, codice nel resolver)?
  - Ripiego boulder: fisso il 4x4 per primo (athlete_plan, PE: «nei 4×4, 1 regola tecnica per serie») o lascio la rotazione di fase (in questa fase per te uscirebbe linked_boulders)?

#### INBOX-2026-11-02-b — intermittent_dead_hangs ordinato prima dell'arrampicata in exercise_instances (il player invece segue i blocchi)

**Verdetto:** parziale · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** Il player guidato, la card e la pagina sessione mostrano gli esercizi nell'ordine dei BLOCCHI del catalogo (frontend/src/lib/session-blocks.ts:35-69, usato da session-card.tsx:289 e 1119; session/[id]/page.tsx rende resolved_session.blocks). Lì le trazioni sospese vengono DOPO i blocchi PE, come dice la nota «post-climbing». La lista backend exercise_instances, invece, passa dall'ordinamento A121 (resolve_session.py:2348-2356). intermittent_dead_hangs ha domain[0] = finger_aerobic_endurance, quindi categoria «aerobic_pure» (exercise_ordering.py:110), e il vincolo 3 «ARC before pump» lo sposta prima del primo pe_intervals (exercise_ordering.py:353-361). Riprodotto a Cocque: warmup_easy_boulders, intermittent_dead_hangs, linked_boulders, route_intervals. Il profilo non testato prende hangboard_moving_hangs (finger_strength_endurance → finger_endurance) e lo mette dopo. Colpite le 6 sospensioni con dominio finger_aerobic_endurance: sub_max_capacity_hang, repeater_sub_max_endurance, intermittent_dead_hangs, long_interval_repeaters, bar_dead_hang, long_duration_hang. Chi legge l'ordine di exercise_instances: payload /api/session/resolve e /api/week (quello che legge il coach), dialog del feedback (frontend/src/lib/feedback-items.ts:124).
- **Evidenza:** Snippet in sola lettura con resolve sul mirror e patch in-process di infer_sort_category (scratchpad order_proto.py): ordine attuale e proposto come in proposed_fix.
- **Fix proposto:** In infer_sort_category (exercise_ordering.py:64-174): domain[0] finger_aerobic_endurance con pattern repeater_hang/isometric_hang/hang (non warm-up) → categoria «finger_endurance», non «aerobic_pure». L'ARC su parete (domain aerobic_capacity) resta aerobic_pure. Prototipo in-process: Cocque diventa linked_boulders, route_intervals, intermittent_dead_hangs. Riordino puro: l'invariante «mai perdere esercizi» resta. Nessuna modifica al frontend.
- **Alternative:** Una chiave di catalogo `order: after_main` sul blocco (sul modello di C276 after_warmup): più esplicita, ma corregge solo questa sessione e non le altre 4 con le stesse sospensioni.
- **Raccomandazione:** Correggere la categoria in exercise_ordering, così tutte le sessioni seguono la stessa regola. Le golden si rigenerano dopo il diff dell'output grezzo (devono cambiare solo l'ordine e il digest).
- **File:**
  - backend/engine/exercise_ordering.py
  - backend/tests/test_a121_exercise_ordering.py
  - backend/tests/test_a121_sort_category_audit.py
  - backend/tests/fixtures/c272_resolver_golden.json
  - backend/tests/fixtures/b413_lunch_ladder_golden.json
  - docs/ENGINE_ARCHITECTURE.md
  - docs/vocabulary_v1.md
- **Chiamanti e consumatori:**
  - backend/engine/resolve_session.py:2348-2356 (unico chiamante di sort_exercises_by_phase / enforce_ordering_constraints)
  - backend/api/routers/week.py:_auto_resolve, session.py:/resolve e surface-override (payload)
  - frontend/src/lib/feedback-items.ts:124 (ordine della lista nel dialog del feedback)
  - frontend/src/lib/session-blocks.ts:35-69 (il player usa l'ordine dei blocchi: invariato)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_a121_exercise_ordering.py (ARC prima del pump: :53, :183 — su aerobic_capacity, invariato)
  - backend/tests/test_a121_sort_category_audit.py:66-69 (replica d'audit che mappa finger_aerobic_endurance → aerobic_pure; non confronta col motore, ma va riallineata)
  - golden c272: 20 chiavi con sospensioni sub-max (endurance_aerobic_gym, finger_aerobic_base, finger_maintenance_gym, regeneration_easy, power_endurance_gym)
  - golden b413: 14 chiavi con sospensioni sub-max
- **Test da aggiungere:**
  - infer_sort_category: le 6 sospensioni finger_aerobic_endurance → finger_endurance; arc/aerobic_capacity resta aerobic_pure
  - power_endurance_gym in fase PE: le sospensioni dopo l'ultimo pe_intervals in exercise_instances
- **Moduli ad alto rischio:**
  - resolve_session (output: ordine di exercise_instances, via exercise_ordering)
- **Effetto sugli altri utenti:** Per tutti cambia solo l'ordine della lista backend (API e dialog del feedback) nelle sessioni con quelle 6 sospensioni. Il player e la card no, perché seguono i blocchi. Determinismo invariato; le sessioni passate restano quelle salvate.
- **Correzione dati in prod:** no

#### INBOX-2026-11-02-c — power_endurance_gym senza blocco tecnica

**Verdetto:** decisione_di_design · **effort** XS · **rischio** basso · frontend no · schema user_state no

- **Causa:** Il template non ha nessun blocco tecnica (power_endurance_gym.json:30-161). Non è un difetto del motore. Nella fase PE la chiave tecnica è una richiesta a sé (key_stimuli.json, phases.power_endurance) e la soddisfano technique_focus_gym o ≥2 drill di piedi/posizione (key_sessions_v1.py:278-290). La regola A293 «ogni custom non di recupero ha un blocco tecnica o try-hard» vale per le custom di Daniele, non per le sessioni del catalogo. athlete_plan.md:221-222, PE: «Chiave tecnica: lead con regole tecniche sotto pump vero; nei 4×4, 1 regola tecnica per serie».
- **Evidenza:** Lettura del template e di athlete_plan.md:219-223; key_sessions_v1.technique_hit.
- **Fix proposto:** Opzione 1 (raccomandata, solo testo di catalogo): aggiungere ai `cues` degli esercizi PE (four_by_four_bouldering, linked_boulders, linked_boulders_circuit, route_intervals) una regola tecnica per serie («scegli 1 regola per serie: piedi silenziosi o niente riaggiustamenti, e tienila sotto pump»). Non costa tempo, non tocca selezione né tag. Opzione 2: un blocco opzionale `technique_primer` dopo il riscaldamento (meccanismo C276 `order: after_warmup`, resolve_session.py:1444-1445; vincolo 6 di exercise_ordering), circa 10' per tutti; da solo non chiude la chiave tecnica, che chiede ≥2 drill. Opzione 3: niente.
- **Alternative:** Una cue di processo (process_cues.json) per power_endurance_gym: ne esce una sola per sessione, scelta a caso (cues.py), quindi non è garantita.
- **Raccomandazione:** Opzione 1, in linea con athlete_plan (1 regola tecnica per serie sotto pump).
- **File:**
  - backend/catalog/exercises/v1/exercises.json
  - backend/tests/fixtures/a290_untested_golden.json
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - frontend: il player mostra i cues dell'esercizio (instance.cues da resolve_session.py:1416)
  - backend/tests/c272_golden_cases.py:_strip (i cues sono in _TEXT_KEYS: il digest c272 non cambia)
  - a290_untested golden: hash dell'output completo, quindi i digest che contengono quegli esercizi cambiano
- **Test che fissano il comportamento attuale:**
  - backend/tests/a290_untested_cases.py / fixtures/a290_untested_golden.json (hash completo, testi inclusi)
- **Test da aggiungere:**
  - con l'opzione 2: il blocco tecnica sta subito dopo il riscaldamento e non conta come chiave tecnica da solo
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Opzione 1: tutti vedono una riga di cue in più sugli esercizi PE, senza effetti su durata, carico e tag (i cues non sono campi letti da session_tags, quindi la regola B395 non scatta). Opzione 2: +1 esercizio e circa 10' nella PE di tutti.
- **Correzione dati in prod:** no
- **Domande:**
  - Tecnica nella PE: basta una regola per serie nei cues (opzione 1) o vuoi un blocco tecnica vero dopo il riscaldamento (opzione 2, circa 10' in più per tutti)?

#### INBOX-2026-11-02-d — --simulate attribuisce alla custom la «CHIAVE finger_maintenance» della sessione con cui è in conflitto

**Verdetto:** confermato · **effort** XS · **rischio** basso · frontend no · schema user_state no

- **Causa:** È un problema di resa del testo, la logica è giusta. Riprodotto sullo snapshot del 02/11 con una bozza PE + intermittent_dead_hangs a Boulder Forest per il 03/11 sera (--replace). Riga stampata: «ALERT [finger_gap] 2026-11-03 evening: custom_cs_simulated_a293 — CHIAVE finger_maintenance». La chiave è quella di custom_cs_4c66003d del 02/11 (max_hang_7s, stimolo finger_max, chiave finger_maintenance in PE): simulate() calcola le chiavi sui riferimenti dell'alert ESCLUDENDO la bozza (scripts/athlete_context.py:371-374), e render_simulation le stampa subito dopo il session_id della sessione segnalata, cioè la bozza (scripts/athlete_context.py:440-443). Le chiavi della bozza sono solo ['power_endurance'] (verificato con key_matches). La riga «CHIAVE [finger_gap]» viene da check_insertion (key_sessions_v1.py:1784-1801) perché la bozza risulta dita-hard (tag finger+hard): sparisce se si corregge il punto (e).
- **Evidenza:** Simulazione in sola lettura sullo snapshot del 02/11 (scratchpad snap1102, draft_pe.json): output come riportato in root_cause.
- **Fix proposto:** In simulate() salvare anche le chiavi per riferimento (`key_refs`: date, slot, session_id, key) lasciando `key` com'è. In render_simulation: se la chiave è della sessione segnalata, testo invariato; se viene da una sessione del «with», stampare «— tocca CHIAVE finger_maintenance (2026-11-02 custom_cs_4c66003d)». Il caso fissato da A293 (sessione segnalata = sessione chiave) resta identico.
- **Alternative:** Stampare la chiave solo sulla riga della sessione chiave (una riga in più per ogni «with»).
- **Raccomandazione:** key_refs + attribuzione esplicita nella riga ALERT.
- **File:**
  - scripts/athlete_context.py
  - backend/tests/test_a293_athlete_context_script.py
  - .claude/commands/custom-session.md
- **Chiamanti e consumatori:**
  - scripts/athlete_context.py:simulate (263-397) e render_simulation (420-447)
  - il comando /custom-session (.claude/commands/custom-session.md:78-86) legge questo output
  - backend/engine/athlete_context.key_matches (362-367), key_sessions_v1.session_keys (345-352): invariati
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_a293_athlete_context_script.py:144-153 (stringa «ALERT [finger_gap] 2026-10-07 evening: power_contact_gym — CHIAVE limit_power»)
  - backend/tests/test_a293_athlete_context_script.py:155-163 (guard_alerts[].key)
- **Test da aggiungere:**
  - alert in cui la sessione segnalata è la bozza e la chiave è dell'altra sessione: la riga nomina la sessione chiave e la data, non la bozza
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Nessuno: lo script è una CLI in sola lettura usata solo per le custom di Daniele.
- **Correzione dati in prod:** no

#### INBOX-2026-11-02-e — Custom PE + sospensioni sub-max: finger True (e dita-hard), la sessione del catalogo con lo stesso esercizio no

**Verdetto:** confermato · **effort** S · **rischio** medio · frontend no · schema user_state no

- **Causa:** derive_session_tags mette finger su qualsiasi pattern repeater_hang o dominio finger_aerobic_endurance che non sia un riscaldamento leggero (session_tags.py:75-93, 179-183). B392 ha tenuto apposta le sospensioni sub-max come finger (session_tags.py:108-111; test_b392_warmup_finger_tag.py:45-50). Il catalogo invece dichiara power_endurance_gym finger: False (planner_v2.py:44), anche se il suo blocco finger_endurance risolve proprio intermittent_dead_hangs per Daniele in tutte le palestre. Nella custom il hard arriva dai PE (≥2 esercizi high), quindi finger+hard rende la custom dita-hard (stimulus.is_finger_hard_session:408-409). Ne seguono l'alert finger_gap (guards_v1.py:284-323, legge solo finger) e il conflitto finger_gap high di check_insertion (key_sessions_v1.py:1784-1801). La sessione del catalogo non ha né l'uno né l'altro. Il «VERIFIED … false for power endurance» della docstring (session_tags.py:29-31) è falso sul contenuto risolto: il derivato non coincide col catalogo per power_endurance_gym, endurance_aerobic_gym, regeneration_easy (bar_dead_hang), prehab_maintenance (un profilo) e route_projecting_gym (qui il derivato dà False contro True: protegge meno). Problema latente: il blocco finger_endurance della PE di catalogo può scegliere repeater_hang_7_3 (stress dita high, intensità high) sotto finger: False; visto per Daniele in base/performance a Escale.
- **Evidenza:** Prototipi in scratchpad (e3b.py) sul mirror del 07/11: confronto tra derivato e _SESSION_META per tutte le sessioni del catalogo, 3 palestre/casa, testato e non testato, 4 fasi.
- **Fix proposto:** Raccomandata (E2, mirata) in due parti. (1) session_tags: le sospensioni sub-max (pattern repeater_hang/isometric_hang/hang, intensity_level ≤ medium, non in _FINGER_HARD_IDS, non riscaldamento leggero) NON mettono finger se la sessione contiene intervalli PE (role main, pattern climbing_intervals, dominio power_endurance/anaerobic_capacity) e nessun altro carico dita. (2) Catalogo: `intensity_max: "medium"` sul blocco finger_endurance di power_endurance_gym, così il finger: False del catalogo è vero anche per contenuto (niente 7/3). Prototipo: i casi fissati da B345/B392 sono invariati (sospensione sub-max da sola → True; max hang e limit → True); PE + intermittent_dead_hangs → False; PE + 7/3 e PE + limit → True; finger_maintenance_gym resta True; il derivato di power_endurance_gym ora coincide col catalogo. Alternativa E1: non cambiare niente. La regola resta conservativa per principio (B345) e per le custom PE ci si limita a non mettere sospensioni sub-max entro 48 h da un giorno max.
- **Alternative:** E1: nessuna modifica. E3, scartata dopo il prototipo: «sospensione leggera + qualsiasi arrampicata → non finger» rompe finger_maintenance_gym (arc_easy_traverse + hangboard_moving_hangs, che nel catalogo è finger True).
- **Raccomandazione:** E2 + intensity_max sul blocco del catalogo: allinea custom e catalogo senza indebolire i casi B345/B392.
- **File:**
  - backend/engine/session_tags.py
  - backend/catalog/sessions/v1/power_endurance_gym.json
  - backend/tests/test_b345_custom_session_tags.py
  - backend/tests/test_b392_warmup_finger_tag.py
  - docs/ENGINE_ARCHITECTURE.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - backend/engine/replanner_v1.py:1613 add_custom_session (tag derivati e salvati all'inserimento)
  - backend/engine/replanner_v1.py:1809-1812 add_generated_session (merge_declared_tags: si alza soltanto)
  - backend/engine/athlete_context.py:422-455 _stale_custom_tags (B395)
  - scripts/athlete_context.py:296 simulate
  - chi legge i tag: guards_v1._finger_gap (284-323), stimulus.is_finger_hard_session (key_sessions_v1.check_insertion 1784-1801, guardia finger_test_72h, blocco dei retest, guardie per giorno di athlete_context), planner_v2 _enforce_no_consecutive_finger (seed)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b345_custom_session_tags.py (tutti; invariante hard⇔high/max e allowlist treadmill_hiit_4x4 :104-130)
  - backend/tests/test_b392_warmup_finger_tag.py:45-50 (sospensione sub-max da sola → finger True: resta vero)
  - backend/tests/test_b395_stale_custom_tags.py
  - backend/tests/test_b405_coach_inbox.py (id dita-hard)
  - backend/tests/test_a293_athlete_context_script.py:158 (custom_tags della DRAFT con max hang)
  - golden c272/b413: profili in cui il blocco finger_endurance sceglie repeater_hang_7_3 (cambio intensity_max)
- **Test da aggiungere:**
  - PE + intermittent_dead_hangs (e le altre sub-max) → finger False, hard True; PE + repeater_hang_7_3 o + limit_bouldering → finger True
  - test di coerenza col catalogo: derive_session_tags sulle sessioni del catalogo risolte (3 profili, 4 fasi) uguale a _SESSION_META.finger, con allowlist esplicita delle discrepanze note (endurance_aerobic_gym, regeneration_easy, prehab_maintenance, route_projecting_gym)
  - power_endurance_gym: il blocco finger_endurance non sceglie mai un esercizio sopra intensità medium
- **Moduli ad alto rischio:**
  - replanner_v1 (consumatore di derive_session_tags: il codice non cambia, i tag sì)
  - resolve_session (output del catalogo per l'intensity_max del blocco)
- **Effetto sugli altri utenti:** Le nuove custom/generate che uniscono intervalli PE e sospensioni sub-max escono finger: False: niente alert finger_gap e niente dita-hard, come la sessione di catalogo equivalente. Le custom già pianificate tengono i tag salvati, fino a un reinserimento (direzione più protettiva). Le generate non scendono sotto i tag dichiarati. intensity_max: nelle PE di catalogo dei profili a cui toccava il 7/3 esce una sospensione sub-max.
- **Correzione dati in prod:** no: regola B395, dopo il deploy si lancia scripts/athlete_context.py e si controlla STALE_CUSTOM_TAGS. Sul mirror del 07/11 la base è vuota; le custom pianificate (07/11 cs_5836f06e, 12/11 cs_89e2a6e6, 19/11 e 26/11 cs_9f27d87a, 01/12 cs_5853e508) non contengono sospensioni, e nessuna delle 66 custom in libreria unisce PE e sospensioni: nessun riallineamento atteso.
- **Domande:**
  - Per le sospensioni sub-max dopo i PE preferisci la regola mirata (E2: la custom diventa come la sessione di catalogo, niente gap dita) o tenere la regola conservativa attuale (E1: alert finger_gap e conflitto)?
  - Va bene mettere intensity_max medium sul blocco dita della PE di catalogo (mai 7/3 dopo i 4x4)?

**Note trasversali (analisi:power-endurance-gym):** Fase 1, sola lettura: nessun file del repo modificato, nessuna scrittura in prod, pytest non lanciato. Prototipi e snippet sono nello scratchpad /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad (resolve_pe.py, resolve_proto.py, order_proto.py, e3b.py, proto_sessions/power_endurance_gym.json, snap1102/). (1) Ordine consigliato: catalogo (a: blocco unico, e: intensity_max, c: cues) + exercise_ordering (b) + session_tags (e) nello stesso brief. Golden c272, a290_untested e b413 si rigenerano UNA volta sola, dopo il diff dell'output grezzo, con la nota nei rispettivi *_cases.py come in C283/B406. Tutto backend: push diretto a main consentito, ma resolve_session e il consumatore replanner_v1 richiedono lo STOP per l'OK di Daniele prima dell'implementazione. (2) Invarianti: passato immutabile (week.py:145-150: done/skipped/_user_edited mai ririsolti; i tag salvati delle custom non si riscrivono); determinismo (solo regole su campi del catalogo, md5 di fase invariato); filtro per attrezzatura (gym_routes resta preferenza di equipment, nessun vincolo sulla location); Fontainebleau, generate_macrocycle(from_phase="current") e invariante del lunedì non toccati; nessuno schema di user_state cambiato. (3) Campi morti: `required` e `priority` dei moduli non sono letti dal resolver in nessuna sessione. Il caso analogo power_contact_gym.campus_power (equipment campus_board soft) ha nelle note un ripiego voluto, quindi lì va bene così. Conviene una nota in ENGINE_ARCHITECTURE o un D di pulizia, non questo brief. (4) Fuori area, segnalato: route_projecting_gym ha finger True nel catalogo, ma una custom di progetto su via esce finger False (climbing_routes non è un pattern dita): lacuna di protezione per le custom, da valutare a parte. (5) Il messaggio di Daniele copre anche scadenza dei test (rinvio, mai azzeramento), nuovo ciclo e tetto delle 5 serie di max hang (REENTRY-MAX-HANG-SETS in roadmap): sono altre aree del workflow, non trattate qui. (6) Visibilità: la fase PE di Daniele finisce il 09/11 e nelle settimane pianificate fino al 06/12 non c'è nessuna power_endurance_gym, quindi (a), (b) ed (e)-catalogo non si vedranno nell'app fino alla prossima fase PE (o a una PE aggiunta a mano). Il punto (d) si vede subito, alla prossima --simulate.

### fatto-conteggio

#### INBOX-2026-11-05 — Sessione di catalogo fatta nel player, esercizi senza serie né carico: non conta per le chiavi

**Verdetto:** confermato · **effort** M · **rischio** medio · frontend no · schema user_state no

- **Causa:** backend/engine/stimulus.py:334-349 `logged_entry_counts`: una riga loggata conta solo con completed_sets/completed_reps ≥ 1, oppure (catalogo) con un carico. Una riga di catalogo `completed: true` senza serie né carico viene scartata. Il player guidato manda completed_sets solo se il timer ha contato una serie (frontend/src/lib/feedback-items.ts:306-319). Per tre tipi di riga questo non succede mai: (a) righe senza timer, cioè sets ≤ 1, senza work_seconds né recupero tra ripetizioni (guided-exercise-step.tsx:59-65): `lead_precision_feet_above_bolt` e `lead_technique_under_pump` sono 1×1; (b) righe con timer mai avviato: `fall_practice` 3×3 si fa in parete col compagno, e B408 conta la serie aperta solo con il timer in fase work (exercise-timer.tsx:248-253); (c) lavoro a tempo chiuso con Done mentre scorre: `treadmill_incline_walk` 2700 s. In più il FeedbackDialog manda sempre `completed: true` senza serie (feedback-items.ts:186-189). Con origin "actual" e 0 righe contate, `counted_entries` restituisce [] (stimulus.py:352-360) e `tryhard_hit` non usa il fallback per session_id, che vale solo con origin "none" (key_sessions_v1.py:314-317). Intanto `bw_ladders.ladder_row_done` (bw_ladders.py:224-249) giudica fatta la stessa riga (catalogo, completed non False). Sulla stessa riga ci sono quindi due definizioni che non concordano, e vocabulary_v1.md:1276 dice esplicitamente che sono separate. Paradosso: una sessione di catalogo con feedback conta meno della stessa sessione segnata fatta senza feedback (origin planned).
- **Evidenza:** Mirror prod del 07/11, sola lettura. 04/11 lead_tryhard_gym: 13 righe → 0 contate, tryhard_hit False. 05/11 treadmill_zone2_cardio: 2 → 0. Simulazione su 114 sessioni fatte con log (hot + archivio), sostituendo la regola in memoria: con la regola unica cambiano 8 sessioni, cioè 04/11 lead_tryhard_gym (try-hard + tecnica), 3 limit_boulder_gym di marzo/giugno/luglio (+limit_power) e 4 route_endurance_gym di aprile-giugno (+power_endurance). Nessun cambio su finger_max e pulling_max. compute_key_status, settimana 02/11: try_hard missing → done, technique planned → done; settimana 26/10 invariata.
- **Fix proposto:** Un solo predicato `stimulus.row_done(row, *, player_session, dose_sets=None)`. `logged_entry_counts` resta come wrapper per i chiamanti e `bw_ladders.ladder_row_done` lo delega. Regole: (1) label `skipped` → no; (2) `completed: false` → sì solo se le serie contate raggiungono la dose (dose_sets, altrimenti prescribed_sets); (3) serie contate presenti → sì con ≥ 1; completed_reps ≥ 1 → sì; (4) sessioni custom/generated senza serie contata → no: è il pre-fill del player libreria, regola tenuta per lo storico; (5) catalogo: `completed: true` oppure un carico loggato → sì; una riga senza flag, serie e carico → no. Cosa cambia: `logged_entry_counts` guadagna le regole (2) e (5); `ladder_row_done` guadagna completed_reps e perde la riga nuda. Nei dati prod ci sono 0 righe nude, e lo schema resolved_day_log_entry.v1 rende `completed` obbligatorio. Opzionale per coerenza: `load_score.compute_actual_load_score` (load_score.py:84-108) usa lo stesso predicato, tenendo «flag assente = fatto». Nessuna modifica di codice in planner_v2, resolve_session, progression_v1 o anchored_load: leggono la regola tramite counted_entries / logged_entry_counts / ladder_row_done.
- **Alternative:** A (proposta dell'inbox) «completed:true + feedback_label conta»: scartata. Conterebbe fall_practice (votato) ma non lead_precision_feet_above_bolt, chiuso con Done e non votato, anche se sono stati fatti entrambi. Va contro A295/B413 («senza voto = ok»). Sulle custom, il player libreria fa votare anche le righe saltate. B «il player salva completed_sets»: sistema solo i dati nuovi, non il 04-05/11 né il dialog. Inventa un conteggio che sembra misurato, e sul catalogo cambia il controllo MIN_FULL_SETS della dose (key_sessions_v1.py:452-455) per righe prescritte con meno di 4 serie. Tutte e due insieme: sul catalogo sono ridondanti; B serve solo per le custom nel player guidato (vedi CUSTOM-PLAYER-DONE-FLAG).
- **Raccomandazione:** Regola unica nel motore (A' = la regola delle scale estesa a stimoli e chiavi), in lettura e quindi valida anche per la storia. Backend da solo su main, retrocompatibile, prima dei fix frontend.
- **File:**
  - backend/engine/stimulus.py
  - backend/engine/bw_ladders.py
  - backend/engine/load_score.py (opzionale)
  - backend/tests/test_a288_stimulus.py
  - backend/tests/test_b414_row_done.py (nuovo)
  - docs/vocabulary_v1.md
  - docs/ENGINE_ARCHITECTURE.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - stimulus.counted_entries (stimulus.py:352), session_stimuli (363-377), is_finger_hard_session (413), is_hiit_session (478), exposures (678)
  - anchored_load.record_exposures (anchored_load.py:1272) → registro persistito progression_counters.stimulus_exposures, chiamato da progression_v1.apply_feedback (progression_v1.py:2895)
  - key_sessions_v1.technique_hit (286), tryhard_hit (314), session_dose (441) → compute_key_status, check_insertion, athlete_context, /events dry run
  - planner_v2._key_stimulus_pass via session_delivers (planner_v2.py:983-996) e is_finger_hard_session sui giorni vissuti (2602-2856)
  - resolve_session recency con include_custom (resolve_session.py:1002-1003)
  - retest_policy, pull pesante (retest_policy.py:493)
  - athlete_context: varietà (athlete_context.py:803) e recent_exercises/no_repeat (856, usato dal composer ad-hoc)
  - report_engine._off_plan_categories (report_engine.py:551-555)
  - bw_ladders: pull pesante (122), seed (358, 409)
  - measured_feedback.unrated_done (99-116) → anchored_load.py:1182, progression_v1._is_unrated_done (2817-2830, usato a 3088/3156/3248/3350/3424), bw_progression.apply_bw_item (882)
  - load_score.compute_actual_load_score ← feedback.py:485-494 (session_load_actual)
  - Frontend: nessuno; key-sessions.ts mostra lo stato del server
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_a288_stimulus.py:111-122 test_logged_entry_counts: tutti i 7 casi restano validi con il predicato proposto
  - backend/tests/test_a288_stimulus.py:380-390: custom con completed_sets 0, non finger-hard
  - backend/tests/test_b413_ladder_rules.py:139-152 test_done_predicate_shared_by_seed_and_closed_loop: tutti i 10 casi restano validi
  - backend/tests/test_b413_ladder_rules.py:118-135 test_unrated_not_done_is_noop
  - backend/tests/test_c276_tryhard_catalog.py:309-313 (loggata senza cadute) e :325+ (lead_tryhard_gym è anche chiave tecnica)
  - backend/tests/test_a294_key_sessions.py, test_a293_athlete_context.py:93 e :417-427 (fixture con completed_sets)
  - backend/tests/test_b312_load_actual.py:89/127/271 (se load_score passa al predicato)
  - backend/tests/test_b413_end_to_end.py:220-233, test_b413_loads_never_lower.py, test_b413_lunch_core_ladder.py:392/677/688
- **Test da aggiungere:**
  - Matrice parametrica di row_done: catalogo/player × completed true/false/assente × serie none/0/≥1/≥dose × label skipped/votato/none × carico
  - Proprietà: logged_entry_counts e ladder_row_done danno la stessa risposta su ogni riga della matrice
  - Regressione forma 04/11: lead_tryhard_gym con 13 righe completed:true senza serie → tryhard_hit True e technique_hit True
  - Regressione forma 05/11: treadmill_incline_walk completed:true senza serie → contata
  - Sessione di catalogo loggata dal dialog (solo label) → stesse famiglie della stessa sessione senza log
  - completed:false con serie = prescritte (forma 4x4 03/11) → power_endurance contata; serie parziali → no
  - Pre-fill del player libreria (completed:true + carico, senza serie) ancora non contato
  - planner PASS 2.7 su una settimana con lead_tryhard_gym fatto senza serie → nessun floor lead_tryhard_gym aggiunto
  - Sessione passata invariata: week plan deep-equal prima e dopo le letture
- **Moduli ad alto rischio:**
  - planner_v2 (indiretto: PASS 2.7 e guardie finger-hard sui giorni vissuti)
  - progression_v1 (indiretto: record_exposures e unrated_done nel ciclo chiuso)
  - resolve_session (indiretto: lista recency con include_custom)
  - anchored_load (vista esposizioni: rientro, pull pesanti, giorni finger-hard)
- **Effetto sugli altri utenti:** Per tutti: le sessioni di catalogo chiuse con Done senza timer, o loggate dal dialog post-sessione, ora portano i loro stimoli a livello di esercizio: try-hard, drill tecnici, famiglie, esposizioni a 21 giorni, varietà/no_repeat. Conseguenze possibili: il planner aggiunge meno sessioni floor; più esposizioni, quindi la rampa di rientro scatta meno; una riga pulling_max di catalogo senza carico ora conta come pull pesante (regola «prudente» di retest_policy) e può spostare un test di un giorno. Custom/generated invariate, tranne completed:false con tutte le serie. Il registro esposizioni riceve più righe da ora in avanti, nello schema esistente. Un solo utente esterno ha mai completato una sessione.
- **Correzione dati in prod:** no: la regola in lettura copre 04/11 e 05/11 senza scrivere nulla. Il registro stimulus_exposures non va ricostruito: le righe derivate da week_plans e archivio coprono la storia, il registro si limita ad aggiungere.
- **Domande:**
  - Ok che lead_tryhard_gym fatto conti anche come chiave Tecnica (due regole di via: piedi sopra il rinvio + tecnica sotto pump)? Da pianificata conta già così (test C276). Col fix la settimana 02/11 passa da Tecnica «planned» a «done» e la custom di sabato 07/11 diventa un extra.
  - Le custom/generate fatte nel player guidato con Done senza timer restano «non fatte» per lo storico: 40 righe votate da luglio, nessuna chiave cambia. Le lasciamo così? È la proposta, perché nel player della libreria si possono votare esercizi saltati.

#### PLAYER-COMPLETED-FALSE — Il player guidato salva completed:false su righe con tutte le serie fatte

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend sì · schema user_state no

- **Causa:** frontend/src/lib/feedback-items.ts:247, 264, 278: `completed: ex.status === "done"`. Lo status diventa "done" solo con Done (app/(guided)/guided/[date]/[sessionId]/page.tsx:478-527) o con «Mark done» nel riepilogo (602-622). Le serie contate stanno in un campo separato (handleSetChange 762-768) e non toccano mai lo status. Una riga con tutte le serie contate esce quindi completed:false in questi casi: chiusa con Skip (529-535); lasciata pending spostandosi con i pallini (handleNavigate 580-588); con «Finish session early» (597-600) seguito da «Submit & finish», che resta attivo anche con righe pending (guided-summary.tsx:172-200, 214-228); con «Skip remaining» (624-637). La riga 4x4 del 03/11 nel backup ~/backups/log-fix-2026-11-04/state_before.json ha completed false, 4/4 serie, nessuna label, nessun grado, nessuna nota: compatibile con Skip o con una riga mai chiusa. La sequenza esatta di tap non si ricostruisce dai dati. Il 03/11 era la prima serata dopo B411 (02/11, barra Skip/Done fissa in basso). L'«1/4» del 16/10 è un altro difetto: serie sotto-contate, prima di B408.
- **Evidenza:** Backup del 04/11 prima della correzione: custom_cs_2ea7e4a9, four_by_four_bouldering completed false, completed_sets 4, prescribed_sets 4, nessuna label; tutte le altre 9 righe completed true.
- **Fix proposto:** Frontend, in buildGuidedFeedbackItems: un helper `guidedRowDone(ex)` = status "done" OPPURE completedSets ≥ totale interno (totalSetsWithSides(prescription.sets, altSides)), usato nei tre punti (riga intera, per-mano, test per-mano). Il riepilogo mostra quelle righe come fatte (✓ «tutte le serie contate») e non le conta tra le «N not completed». Le righe con serie parziali restano completed:false con le loro serie, e il motore le giudica non fatte se sotto la dose. Lato motore la storia è già coperta dalla regola unica di INBOX-2026-11-05 (completed:false + serie ≥ dose = fatto).
- **Alternative:** Chiudere da sola la riga quando il timer arriva a «Done!»: scartata, B397 vuole un Done esplicito (voto, carichi, Undo). Bloccare «Submit» finché restano righe pending: frizione inutile.
- **Raccomandazione:** Correzione nel payload (una regola) più l'indicazione nel riepilogo, nello stesso branch frontend di CUSTOM-PLAYER-DONE-FLAG e B-ALTSIDES-SETS (stesso file).
- **File:**
  - frontend/src/lib/feedback-items.ts
  - frontend/src/components/guided/guided-summary.tsx (righe con tutte le serie mostrate come fatte)
  - frontend/src/lib/__tests__/feedback-items.test.ts
  - frontend/src/lib/__tests__/b414-guided-done-flag.test.tsx (nuovo)
  - docs/user_guide_v1.md
- **Chiamanti e consumatori:**
  - buildGuidedFeedbackItems ← guided-pending-feedback.buildGuidedFeedbackBody (guided-pending-feedback.ts:60-81): primo POST e replay; pendingFeedbackBody (87-90) per le voci salvate prima di B397; syncPendingGuidedFeedback su /today
  - Server: feedback.py salva gli item così come arrivano (feedback.py:481); arricchimento prescribed_sets (161-162)
  - Consumatori del flag: stimulus.logged_entry_counts (stimulus.py:336, la PE sparisce); load_score.compute_actual_load_score (load_score.py:92, il fatigue_cost esce da session_load_actual, solo catalogo, salvato al momento del feedback); progression_v1._apply_dp_feedback (2762, 2778 → not_completed, niente progressione); anchored_load.py:1052 (niente salita, niente evidenza); measured_feedback.py:596 (copertura della difficoltà). Le scale sono già immuni (bw_ladders.py:244-246)
- **Test che fissano il comportamento attuale:**
  - frontend/src/lib/__tests__/feedback-items.test.ts:362-380 (B413: una riga skipped non riceve completed_sets)
  - frontend/src/lib/__tests__/b397-step-undo.test.ts
  - frontend/src/lib/__tests__/b397-guided-page.test.tsx
  - frontend/src/lib/__tests__/b408-guided-page-done-sets.test.tsx
  - frontend/src/lib/__tests__/b411-pinned-actions.test.tsx
- **Test da aggiungere:**
  - buildGuidedFeedbackItems: skipped con completedSets = sets → completed true
  - pending con tutte le serie → true; pending 2/4 → false con completed_sets 2
  - alt_sides con 6 interne su 3 prescritte → true; con 5 interne → false
  - item per-mano seguono la stessa regola
  - Test pagina: Finish early + Submit con una riga pending tutta contata → POST completed:true; il riepilogo la mostra come fatta
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Per chi usa il player guidato: un esercizio con tutte le serie contate ma chiuso con Skip o lasciato aperto diventa «fatto». La progressione può muoversi (dp reps_up/carico), c'è evidenza per gli anchored, PE e stimoli contano, il carico della sessione è pieno. Le righe parziali non cambiano.
- **Correzione dati in prod:** no: la riga del 03/11 è già stata corretta in prod il 04/11 con l'OK di Daniele (backup ~/backups/log-fix-2026-11-04/). Le altre righe storiche completed:false con serie sono parziali o senza prescritte (es. 06/10 threshold_climbing 4/6) e restano giustamente non fatte; casi futuri li copre la regola in lettura.
- **Domande:**
  - Una riga con TUTTE le serie contate ma chiusa con Skip la consideriamo fatta (proposta)? Con serie parziali (es. 4x4 a 3/4, poi Skip) resta «non fatta» per chiavi e PE, ma le serie vengono salvate: va bene?

#### CUSTOM-PLAYER-DONE-FLAG — Il player della libreria custom (/session-builder/[id]/play) manda sempre completed:true

**Verdetto:** confermato · **effort** S · **rischio** medio · frontend sì · schema user_state no

- **Causa:** app/(guided)/session-builder/[id]/play/page.tsx:436-460: ogni riga parte con `completed: true`. Il carico precompilato `kgByIndex[i] ?? ex.load_kg` (446-448) viene mandato anche per le righe mai fatte; completed_sets solo se contate (449-450). «Skip exercise» (356-366) non registra niente, e la schermata finale fa votare ogni riga, anche quelle saltate (715-724). Per questo il motore non può fidarsi del flag sulle sessioni custom/generated (stimulus.py:342-345, bw_ladders.py:236-249: serve una serie contata). Quella regola penalizza però anche le custom eseguite nel player GUIDATO, che è il percorso normale da Today (session-card.tsx:369/413 → /guided): lì completed:true è affidabile, ma le righe chiuse con Done senza timer non hanno serie. Il 03/11 sono stati scartati riscaldamenti, no_readjust_drill, pike_pushup e wall_slide. Il player libreria si raggiunge solo dallo «Start» delle custom salvate (start-custom-session.ts:48-50). Effetto sul ciclo chiuso oggi: una riga saltata col kg precompilato arriva a progression_v1 come fatta con quel carico. Rating None vale 'ok', il carico viene tenuto, ma non è unrated_done per la regola dei player: può riscrivere la memoria working_loads con il carico salvato nella custom e rinfrescarne la data per un esercizio non fatto.
- **Evidenza:** Backup del 03/11 (custom nel player guidato): general_pulse_raise, dynamic_mobility_flow, warmup_easy_boulders, no_readjust_drill, pike_pushup, wall_slide e cooldown sono completed:true senza serie, e sono tutti scartati da counted_entries. 19/08 generated_cardio_core: 5 righe votate e 0 con serie, la sessione non porta niente.
- **Fix proposto:** Player libreria: `completed = setsByIndex[i] ≥ 1`; `completed_sets` mandato sempre, in serie reali (vedi B-ALTSIDES-SETS), 0 se nessuna; sulle righe con 0 serie niente kg precompilato e niente misure; un eventuale voto parte con completed:false. Opzionale: la schermata finale segna «saltato» le righe a 0 serie. Player guidato su custom/generated: estendere la regola B413 (feedback-items.ts:312-319) dalle righe di scala a ogni riga chiusa con Done o «Mark done» senza serie contate, mandando prescription.sets. Così la regola dei player è soddisfatta da un «Done» vero, senza nuovi campi. buildGuidedFeedbackBody (guided-pending-feedback.ts:60-81) passa `playerSession` (id custom_/generated_, stessa regola di stimulus._is_player_session). Sul catalogo non cambia niente: il test feedback-items.test.ts:380 resta. Regola del motore per le sessioni player invariata: la storia resta prudente.
- **Alternative:** Un marcatore per riga (es. `source: "library_player"`) per fidarsi del completed:true del player guidato: aggiunge un campo alle righe salvate, cioè cambia la forma di actual_exercises. Fidarsi del voto sulle sessioni player: il player libreria fa votare anche le righe saltate.
- **Raccomandazione:** Correggere i due player perché dicano la verità e non cambiare la regola player nel motore.
- **File:**
  - frontend/src/app/(guided)/session-builder/[id]/play/page.tsx
  - frontend/src/lib/feedback-items.ts
  - frontend/src/lib/guided-pending-feedback.ts
  - frontend/src/lib/__tests__/feedback-items.test.ts
  - frontend/src/lib/__tests__/b406-custom-rep-rest.test.tsx o un nuovo b414-custom-player-done.test.tsx
  - docs/user_guide_v1.md (testo «An exercise you did but didn't rate counts as ok» del player libreria)
  - docs/vocabulary_v1.md:1276
- **Chiamanti e consumatori:**
  - Player libreria: handleFinish (play/page.tsx:392-475) → applyEvents mark_done + postFeedback
  - Player guidato: buildGuidedFeedbackItems ← buildGuidedFeedbackBody / pendingFeedbackBody / sync del replay su /today
  - Server: feedback.py:481 (actual_exercises salvati così come arrivano), _enrich prescribed (161-162), progression_v1.apply_feedback (working_loads, A240), anchored_load.apply_anchored_feedback, bw_progression.apply_bw_item (882), stimulus.exposures / registro
- **Test che fissano il comportamento attuale:**
  - frontend/src/lib/__tests__/feedback-items.test.ts:362-380 (riga 380: riga non di scala chiusa con Done senza serie → nessun completed_sets; cambierebbe solo con playerSession true)
  - frontend/src/lib/__tests__/b406-custom-rep-rest.test.tsx (player libreria)
  - backend/tests/test_b413_ladder_rules.py:139-152 (casi custom_cs_core)
  - backend/tests/test_b413_loads_never_lower.py (sessioni custom_cs_x)
  - backend/tests/test_a288_stimulus.py:114-116 (pre-fill del player)
- **Test da aggiungere:**
  - Pagina del player libreria: riga saltata → POST completed:false, nessun used_external_load_kg, completed_sets 0
  - Riga con serie → completed true con conteggio reale; alt_sides 6 interne → 3
  - buildGuidedFeedbackItems con playerSession true: riga chiusa con Done senza serie → manda prescription.sets; con playerSession false → no (test 380 invariato)
  - Backend: apply_feedback con una riga saltata del player libreria (completed false, senza carico) lascia invariati working_loads e scale
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Chi usa il player libreria: gli esercizi saltati non scrivono più il carico precompilato in memoria e non contano come fatti. Custom e generate nel player guidato: le righe chiuse con Done senza timer contano per chiavi, stimoli, varietà e scale (portano le serie prescritte); per esempio un drill tecnico chiuso con Done conta per la chiave Tecnica. Codice del motore invariato, ma cambiano gli input del ciclo chiuso.
- **Correzione dati in prod:** no: le righe storiche non dicono quale player le ha scritte, quindi non si possono correggere senza tirare a indovinare. Il motore mantiene la regola prudente; nei dati di Daniele nessuna chiave cambia (40 righe votate senza serie su custom da luglio, nessuna in una famiglia chiave).
- **Domande:**
  - Nel player della libreria, se voti un esercizio saltato (0 serie) il voto lo mandiamo comunque con completed:false (proposta) o lo togliamo?
  - Ok estendere la regola B413 (serie prescritte su «Done» senza timer) a tutte le righe delle custom nel player guidato, non solo alle righe di scala?

#### B-ALTSIDES-SETS — Esercizi destro/sinistro: i player mandano le serie interne (raddoppiate), il server le confronta con le prescritte per lato

**Verdetto:** confermato · **effort** S · **rischio** basso · frontend sì · schema user_state no

- **Causa:** Entrambi i player contano le serie interne (alt-sides.ts:28-31; exercise-timer.tsx:237; play/page.tsx:301-312 con totalSetsWithSides) e le mandano così come completed_sets (feedback-items.ts:306-307; play/page.tsx:449-450). Il server le confronta con prescribed_sets, che è per lato: progression_v1.py:2763-2767 `sets_ok`; anchored_load.py:1055-1057 `all_sets`; bw_ladders.py:244-246 (completed:false + serie ≥ dose); key_sessions_v1.py:380-385 `_entry_sets` contro MIN_FULL_SETS=4 (114, 452); sets_done delle esposizioni (stimulus.py:681) e del registro (anchored_load.py:1274); stampa «4/2 serie» (athlete_context.py:1742-1743); «Sets: 6/3 ✓» (exercise-card.tsx:227-230). Invece la spedizione B413 delle righe di scala (feedback-items.ts:318) e bw_progression.mark_done_items (983-992) scrivono già serie REALI: nello stesso campo convivono due unità. Fermarsi dopo destra-sinistra-destra (1,5 serie) vale come «tutte le serie».
- **Evidenza:** Prod 03/11: archer_pullup 4/2 (alt_sides, 2 per lato); pranzo 03/11: copenhagen_plank 6 e edge_calf_raise_bigtoe 6 su 3 prescritte. Riproduzione del 30/10 in roadmap: split squat bulgaro 3×8 con completed_sets 3 → reps_up, come con 6.
- **Fix proposto:** I player mandano serie reali: `completed_sets = altSides ? floor(interne/2) : interne`, cioè contano solo le coppie D+S complete (D-S-D = 1). L'interfaccia continua a usare il conteggio interno (timer, ripresa, Undo, B408). La regola «tutte le serie contate» di PLAYER-COMPLETED-FALSE confronta interno con totale interno. Stessa conversione nel player libreria. Motore invariato. Storia invariata perché immutabile: le vecchie righe alt_sides restano in unità interne (si vede 6/3; una vecchia riga completed:false con interne ≥ prescritte risulta fatta, effetto innocuo).
- **Alternative:** Il server dimezza per gli alt_sides (suggerimento della roadmap): andrebbe aggiunto un helper a ogni lettore (8+ punti, alcuni in progression_v1/anchored_load, ad alto rischio), e dimezzerebbe per sbaglio le righe già in unità reali (scale B413, mark_done_items) senza un modo per riconoscerle. Un secondo campo `completed_sides`: nuovo campo nelle righe salvate, non serve.
- **Raccomandazione:** Conversione nel payload dei due player (floor), nello stesso branch frontend di PLAYER-COMPLETED-FALSE e CUSTOM-PLAYER-DONE-FLAG.
- **File:**
  - frontend/src/lib/feedback-items.ts
  - frontend/src/app/(guided)/session-builder/[id]/play/page.tsx
  - frontend/src/lib/alt-sides.ts (helper realSetsFromInternal)
  - frontend/src/lib/__tests__/b408-done-counts-last-set.test.tsx
  - frontend/src/lib/__tests__/guided-alt-sides.test.ts
  - docs/vocabulary_v1.md
- **Chiamanti e consumatori:**
  - Payload: buildGuidedFeedbackItems (feedback-items.ts:306-319), handleFinish del player libreria (play/page.tsx:449-450)
  - Lettori lato server, invariati: progression_v1._apply_dp_feedback, anchored_load (all_sets, record_exposures), bw_ladders.ladder_row_done, key_sessions_v1._entry_sets / session_dose, stimulus.exposures, athlete_context.recent_exercises (869-870, 1742)
  - Visualizzazione: exercise-card.tsx:227-230
  - Item per-mano (B120, carichi per mano) non portano completed_sets: non toccati
- **Test che fissano il comportamento attuale:**
  - frontend/src/lib/__tests__/b408-done-counts-last-set.test.tsx:221-256 (sentSets() si aspetta 4 e 3 interne: diventerebbero 2 e 1)
  - frontend/src/lib/__tests__/feedback-items.test.ts:151
  - frontend/src/lib/__tests__/guided-alt-sides.test.ts, b404-side-switch-timer.test.tsx (conteggio interno del timer, invariato)
  - backend/tests/test_b324_alt_sides_propagation.py, test_b352_custom_alt_sides_read.py (propagazione del flag, invariati)
- **Test da aggiungere:**
  - buildGuidedFeedbackItems: alt_sides 6 interne → completed_sets 3; 5 → 2; 1 → 0 (e completed false)
  - Player libreria: split squat 3×8 alt_sides tutto fatto → 3; fermo a D-S-D → 1
  - Backend: split squat bulgaro 3×8 con completed_sets 1 → niente reps_up; con 3 → reps_up (il caso riprodotto il 30/10)
  - Riga non alt_sides invariata
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Per chi fa esercizi a lati alterni (67 nel catalogo, tra cui one_arm_hang_assisted e lp_max_lift_5s/7s/lp_short_lifts della famiglia finger_max): fermarsi a metà blocca la progressione, come dovrebbe; la visualizzazione è corretta. Dose delle chiavi: una riga finger_max alt_sides senza split per mano, prescritta a 3 per lato (one_arm_hang_assisted), risulta 3 < MIN_FULL_SETS 4, quindi «parziale», dove oggi conta 6 e risulta piena. LP 5 per lato invariato. Con tutte le serie fatte, nell'uso normale l'effetto è nullo.
- **Correzione dati in prod:** no: la storia resta in unità interne (immutabile); l'effetto è solo nella visualizzazione più un caso limite innocuo.
- **Domande:**
  - Per MIN_FULL_SETS=4 su un esercizio a lati alterni contiamo le serie per lato (3 per lato = parziale) o le salite totali (6 = piena)? La proposta è per lato. Riguarda solo one_arm_hang_assisted a 3 per lato senza carichi per mano.

**Note trasversali (analisi:fatto-conteggio):** DEFINIZIONE UNICA DI «FATTO» (proposta). Il motore ha una sola regola, `stimulus.row_done`: la usano chiavi, try-hard, tecnica, PE, esposizioni, scale, carichi (unrated_done) e report. I due player mandano dati veri, e il motore non deve più indovinare.
- Saltato (label skipped) → mai fatto.
- completed:false → fatto solo se le serie contate arrivano alla dose (rimedio in lettura al difetto del player, vale anche per la storia).
- Serie contate → fatto con ≥ 1; completed_reps ≥ 1 → fatto.
- Custom/generate senza serie contata → non fatto: per la storia non si distinguono i due player.
- Catalogo: completed:true o un carico → fatto.
Lato player: guidato completed = Done oppure tutte le serie contate; sulle custom, Done senza timer manda le serie prescritte (B413 esteso). Libreria: completed = almeno una serie, niente carico precompilato sulle righe saltate. Alt_sides: serie reali = coppie D+S complete.

SEQUENZA. (1) Backend da solo (INBOX-2026-11-05), su main dopo l'OK: retrocompatibile, regola in lettura, sistema subito il 04/11 e il 05/11. (2) Un solo branch frontend brief/B414-… con PLAYER-COMPLETED-FALSE, CUSTOM-PLAYER-DONE-FLAG e B-ALTSIDES-SETS: stessi file, feedback-items.ts e play/page.tsx. Serve la preview Vercel e l'OK di Daniele prima del merge (CLAUDE.md, Branch workflow).

SE «P2» È IL PUNTO SUI PLAYER, in parole semplici: i due player salvano male il «fatto». Il guidato segna «non fatto» un esercizio con tutte le serie fatte se lo chiudi con Skip o finisci prima senza toccare Done: è il 4x4 del 03/11. Quello della libreria segna «fatto» anche gli esercizi saltati e ci mette dentro il carico precompilato. Da fare: correggere i due player perché dicano la verità. Il motore poi legge una regola sola.

INVARIANTI. Sessioni passate immutabili: niente scritture, solo lettura; nessuna correzione di dati prod necessaria (il 4x4 del 03/11 è già stato corretto il 04/11 con OK, backup ~/backups/log-fix-2026-11-04/). Determinismo: predicato puro. Filtro per attrezzatura, Fontainebleau, from_phase="current" e lunedì: non toccati. Schema di user_state: nessun cambio, nessun campo nuovo nelle righe.

ALTO RISCHIO. Nessuna modifica di codice in planner_v2, replanner_v1, macrocycle_v1, resolve_session, progression_v1 o closed_loop_v1. Cambia però indirettamente il loro comportamento: planner_v2 PASS 2.7 (session_delivers) e guardie finger-hard sui giorni vissuti; resolve_session (recency include_custom); progression_v1.apply_feedback (registro esposizioni, input dai player) → protocollo con STOP valido. Va lanciata la suite completa più un test che la sessione passata resti invariata dopo le letture.

DOCUMENTI. vocabulary_v1.md:1276 oggi dice «logged_entry_counts è una regola separata, intoccata»: va riscritto. ENGINE_ARCHITECTURE (regola stimolo e riga 397, session_load_actual). user_guide (player libreria: voto e saltati). In roadmap: chiudere PLAYER-COMPLETED-FALSE, CUSTOM-PLAYER-DONE-FLAG e B-ALTSIDES-SETS. bug-inbox (climb-coach): righe 9 e 13 da spuntare a chiusura.

FUORI AREA, non analizzati qui: tetto delle 5 serie di max hang (REENTRY-MAX-HANG-SETS), scadenza dei test (LADDERS-TEST-EXPIRY), nuovo ciclo (END-OF-CYCLE-STUCK-IN-DELOAD), mark_done orfano (inbox 04/11).

METODO. Solo lettura nel worktree /Users/danielesomensi/Projects/climb-agent-b414 e sul mirror ~/Projects/climb-state-mirror. Le simulazioni sostituiscono la regola in memoria senza scrivere nulla. Pytest non è stato lanciato. Script: /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/b414_scan.py, /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/b414_scan2.py, /private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/4ba6d823-12c9-4b3c-accf-10b2998ce651/scratchpad/b414_keys.py.

### events-feedback

#### INBOX-2026-11-04-ORPHAN — mark_done / feedback su una sessione non più nel piano lascia un completamento orfano

**Verdetto:** confermato · **effort** M · **rischio** medio · frontend sì · schema user_state no

- **Causa:** (a) Il player parte da una copia del piano in cache sul telefono, senza mai chiedere al server. Start usa la `session` della card (`session-card.tsx:355-414`, `handleStartGuided`) e scrive lo stato in localStorage. Il player poi legge solo da localStorage (`guided/[date]/[sessionId]/page.tsx:206-261`) e non confronta mai la sessione con il piano. La cache della settimana resta vecchia per tre motivi: è persistita per 7 giorni (`query-persist.ts:279`), ha staleTime di 60 s (`use-week-plan.ts:63`) e non si aggiorna quando l'app torna in primo piano (`query-client.ts:24`, `refetchOnWindowFocus: false`, nessun listener di visibilitychange su /today). La modifica delle 12:21 è stata scritta dal server da un altro client (probabilmente il coach con il flusso /custom-session, cfr. climb-coach/progetti/vo2max.md:37), quindi il telefono non ne ha saputo niente. Non è una ripresa (resume): `started_at` 11:28:57Z è il primo Start, e B197 avrebbe conservato uno startedAt precedente (`session-card.tsx:397-408`).
(b) /feedback: non riceve il piano del client né `base_revision`, quindi B371 non lo copre. Il `mark_done` inline (`feedback.py:281-297`) non trova la sessione: `apply_events` non segna niente (`replanner_v1.py:1268-1274`, nessun errore) ma aggiunge comunque un'adattamento `{type: event, mark_done}` (`replanner_v1.py:1845`) e la settimana viene salvata con la revisione aumentata (`feedback.py:664-673`). La riga del completion log viene aggiunta senza condizioni (`feedback.py:369-383`). `apply_feedback` muove i working_loads (`feedback.py:428`). `append_feedback_log` aggiunge una voce e taglia il log a 7, quindi scaccia una voce vera (`adaptive_replan.py:143-147`). Il passo 4b non trova lo slot (`feedback.py:472-506`). La risposta è 200 senza nessun avviso. /events: con `session_ref` assente nel piano, `mark_done` non fa niente in silenzio ma la riga del completion log viene scritta lo stesso (`replanner.py:802-830`, `_logged_session_id` restituisce il ref). Il ciclo chiuso viene saltato (`replanner.py:782-787`). Dall'app B371 dà 409 su una copia vecchia e non ritenta se la sessione manca (`frontend lib/plan-revision.ts:95-123`, `api.ts:586-600`). Senza `base_revision` (coach con curl, PWA di prima di B371) la scrittura passa (`plan_revision.py:153-158`). `mark_skipped` e `remove_session` invece rifiutano già un ref inesistente (`replanner_v1.py:187-192`, 1239, 1252 → 422 in `replanner.py:706-707`).
- **Evidenza:** Backup ~/backups/back-squat-2026-11-04/state_before_casa.json (letto in sola lettura). Settimana 2026-11-02, nell'adaptations: remove_session treadmill_hiit_4x4 lunch, poi add_custom_session cs_320de282, poi `mark_done session_ref treadmill_hiit_4x4` senza slot. È la forma dell'evento inline di /feedback (`feedback.py:286-290`). Nel completion log c'è treadmill_hiit_4x4 done con `started_at` 2026-11-04T11:28:57Z (lo manda solo il player guidato, `feedback.py:627-631`) e 5 esercizi. In feedback_log c'è la voce treadmill_hiit_4x4. La custom risulta `planned`. Mirror del 07/11 (dato corretto il 04/11): 144 righe done del completion log, tutte con la sessione done nel piano, 0 orfane.
- **Fix proposto:** Backend:
(1) /feedback: un controllo prima di ogni scrittura, subito dopo `_snapshot_weeks` a `feedback.py:239`. Se `target_date` è un giorno di `current_week_plan` o di `week_plans[lunedì(date)]` e quel giorno non ha nessuna sessione con `session_id == target_sid`, la risposta è 409 con `detail: {code: "session_not_in_plan", message, date, session_id, day_sessions: [{session_id, slot, status, name}]}`. Niente `current_revision` nel corpo, altrimenti il client lo legge come stale_plan (`api.ts:217-221`). Non si scrive niente: niente completion log, feedback_log, working_loads, piano o revisione. Restano come oggi: nessun piano che copra la data (per esempio una settimana già archiviata), la sessione già done (`_already_done`) e il rollover B216 (cercando in entrambi i piani). Uno stub saltato (`skipped_session_id == sid`) conta come non nel piano.
(2) `apply_events` mark_done: ValueError se nessuna sessione corrisponde, come fanno già mark_skipped e remove_session. /events risponde 422, dry run compreso, e senza riga orfana.
Frontend (branch, preview e OK):
(3) `api.ts` riconosce il 409 `session_not_in_plan`. Il player non lo tratta come un errore di rete (oggi qualunque errore → `feedback_pending`, `page.tsx:691-713`). Mostra invece un riquadro: «Questa sessione non è più nel piano di oggi (ora c'è X)», con le scelte da decidere (vedi domande).
(4) Replay (`guided-pending-feedback.ts:205-224`): con questo 409 la voce resta sul telefono come «da decidere», il ciclo passa alle altre voci senza fermarsi e /today mostra un banner.
(5) Prevenzione: sulla query della settimana `refetchOnWindowFocus: true`, che scatta al ritorno in primo piano se i dati hanno più di 60 s. Su Start di una sessione nuova, se si è online e la cache ha più di 60 s, si rilegge la settimana (al massimo circa 3 s) e si controlla che la sessione ci sia ancora in quella data. Se manca: toast «Il piano è cambiato» e niente avvio. Offline o timeout: si parte come oggi.
- **Alternative:** A) Solo un avviso: 200 con `warning: session_not_in_plan` e i log scritti lo stesso. È semplice ma il dato orfano resta, quindi non lo raccomando. B) 200 con il dato salvato ma marcato `off_plan: true` sulla riga del completion log e niente adattamento. Serve un campo nuovo nello stato (cambio di schema additivo, da fermare come alto rischio), e la sessione resta invisibile nella settimana. C) Il server sistema da solo il piano: un campo `place_if_missing` su /feedback che aggiunge e segna done la sessione giocata. È atomico e funziona anche nel replay, ma mette logica del replanner dentro /feedback.
- **Raccomandazione:** Fare (1) e (2) e, per il client, (3), (4) e (5). È un controllo per sessione, più preciso di un `base_revision` su /feedback: quello bloccherebbe il feedback per qualunque modifica della settimana, anche una che non c'entra. Rilascio: prima il frontend, poi il backend, oppure insieme. Ho verificato che una PWA vecchia, a un 409, tiene la voce sul telefono e non la perde (`isPermanent` del replay accetta solo 400/422, `guided-pending-feedback.ts:130-132`). Il rischio è che quella voce resti bloccata in «Waiting to sync» e fermi le altre in coda (`break` a riga 223): per questo il backend va dopo, o insieme.
- **File:**
  - backend/api/routers/feedback.py
  - backend/engine/replanner_v1.py
  - frontend/src/lib/api.ts
  - frontend/src/app/(guided)/guided/[date]/[sessionId]/page.tsx
  - frontend/src/lib/guided-pending-feedback.ts
  - frontend/src/components/training/session-card.tsx
  - frontend/src/lib/hooks/queries/use-week-plan.ts
  - frontend/src/app/(main)/today/page.tsx
  - backend/tests/test_a194_feedback_atomic.py
  - backend/tests/test_b369_preserve_user_sessions.py
  - docs/API_ENDPOINTS.md
  - docs/vocabulary_v1.md
  - docs/user_guide_v1.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - apply_events mark_done: replanner.py:694 (/events), replanner.py:636 (dry run, build_key_conflicts), feedback.py:284 e :321 (inline e ripiego B216)
  - Mittenti di /feedback: guided page.tsx:668, guided-pending-feedback.ts:209 (replay), today/page.tsx:1166 e week/page.tsx:598 (dialog dopo mark_done), session-builder/[id]/play/page.tsx:461 (dopo il proprio /events), outbox.ts:122, use-feedback.ts:31
  - Mittenti di mark_done su /events: today/page.tsx:592, week/page.tsx, session-builder play:408, il coach climb-coach (API)
  - Lettori del completion log: key_sessions_v1.py:509, report_engine.py:647-690 e :1353, coach/prompt_builder.py:682, routers/state.py:66, macrocycle_archive, scripts/export_training_log.py
  - Lettori del feedback_log: week.py:436-463, adaptive_replan.check_adaptive_replan, report_engine.py:391, retest_policy.py:809
  - Le sessioni body-part (`generated_`) e le custom del coach o del builder sono inserite nel piano prima di giocarle (body_part_picker.py:185-217, coach/page.tsx:495-528): il controllo non le tocca
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_a194_feedback_atomic.py::test_feedback_with_unknown_session_graceful (200 su una sessione sconosciuta in un giorno pianificato)
  - backend/tests/test_b369_preserve_user_sessions.py::_path_feedback_very_hard (riga 501-513, `nonexistent_session` → 200) e ::test_feedback_very_hard_changes_nothing_and_suggests (riga 639): da passare a una sessione vera del piano
  - backend/tests/test_a194_feedback_atomic.py::test_feedback_without_current_week_plan (deve restare 200)
  - backend/tests/test_week_rollover_B216.py::test_mark_done_lands_in_week_plans_when_legacy_stale (deve restare 200)
  - frontend/src/lib/__tests__/b397-pending-feedback.test.tsx («an entry refused for good (422)», «a retryable failure keeps the entry»)
  - frontend/src/lib/__tests__/b397-guided-page.test.tsx («offline: keeps the exact body»)
  - frontend/src/lib/__tests__/b397-review-start-paywall.test.tsx e b396-guided-resume.test.ts (handler di Start)
  - frontend/src/lib/__tests__/plan-revision.test.ts (isRetrySafeEvents su una sessione mancante)
- **Test da aggiungere:**
  - /feedback: sessione assente in quel giorno → 409 session_not_in_plan; completion log, feedback_log, working_loads, adaptations e plan_revision restano byte-identici
  - /feedback: data non coperta da nessun piano salvato → 200 come oggi
  - /feedback: rollover B216 (sessione solo in week_plans[lunedì]) → 200; sessione già done → 200 e idempotente
  - /feedback: stub saltato con skipped_session_id uguale → 409
  - apply_events mark_done con ref inesistente → ValueError; /events → 422 senza riga nel completion log e senza salvataggio; dry run → 422
  - Invariante: sessioni passate byte-identiche dopo un 409 e dopo un 422
  - Frontend: un 409 session_not_in_plan nel player mostra il riquadro e non va in pending; nel replay la voce resta, il ciclo prosegue e c'è il banner; Start con cache più vecchia di 60 s rilegge la settimana e non parte se la sessione è stata tolta; la query della settimana si rilegge al ritorno in primo piano
- **Moduli ad alto rischio:**
  - backend/engine/replanner_v1.py (apply_events, ramo mark_done)
- **Effetto sugli altri utenti:** Per tutti gli utenti: una sessione giocata e poi tolta dal piano non scrive più completamenti e feedback orfani né sposta i carichi. Il server risponde 409 e il player chiede cosa fare. Con una PWA non aggiornata la voce resta sul telefono in «Waiting to sync», non si perde. Un mark_done con un ref sbagliato su /events dà 422; l'app non lo manda mai con un piano fresco, quindi il cambio riguarda solo il coach e gli script. Al ritorno in primo piano la settimana si rilegge: una GET in più, al massimo una al minuto.
- **Correzione dati in prod:** no. Il caso del 04/11 è già stato corretto con l'OK di Daniele (backup ~/backups/back-squat-2026-11-04/). La scansione in sola lettura del mirror del 07/11 trova 144 righe done e 0 orfane. Gli altri utenti non sono nel mirror: se serve, una scansione in sola lettura in fase 2.
- **Domande:**
  - Quando il player invia una sessione che non è più nel piano, quali scelte vuoi? (a) «Registrala al posto di <sessione ora nel piano>», con una sola /events: remove + add_planned_session/add_custom_session + mark_done, poi il feedback; è quello che il coach ha fatto a mano il 04/11. (b) «Registrala come extra» in uno slot libero. (c) «Scarta», con conferma. Tutte e tre o solo alcune?
  - Va bene che /api/replanner/events risponda 422 a un mark_done su una sessione che non c'è, come fa già mark_skipped? Il coach deve gestire l'errore.
  - Rilascio: prima il frontend (preview e tuo OK), poi il backend del controllo. Va bene?

#### B312-LOAD-ACTUAL-VS-FROZEN — Carico reale (session_load_actual) calcolato prima del congelamento: per le sessioni del player guidato non viene mai salvato

**Verdetto:** confermato · **effort** XS · **rischio** basso · frontend no · schema user_state no

- **Causa:** In parole semplici: quando finisci col player guidato una sessione del catalogo, l'app dovrebbe salvare il carico che hai fatto davvero (se salti esercizi, il carico scende). Lo calcola però sulla prescrizione salvata nel piano prima del «fatto», e per le sessioni del catalogo ancora da fare quella copia nel piano non c'è. Quindi non lo calcola, e i report contano sempre il carico pieno.
Nel codice: il passo 4b chiama `compute_actual_load_score(_fb_items, sess.resolved...exercise_instances)` (`feedback.py:488-497`). Il `resolved` congelato (quello che GET ha mostrato) viene calcolato al passo 1 (`feedback.py:301-303`, `335-337`) ma scritto solo al 7b (`feedback.py:650-652`). Una sessione del motore in attesa, nello stato di prod, non ha un `resolved` salvato, quindi `compute_actual_load_score` riceve None e restituisce None (`load_score.py:80-81`) e il campo non viene scritto. I report usano `effective_session_load` (`load_score.py:111-142`), che ricade sul `session_load_score` prescritto del resolved congelato (`report_engine.py:307`, `:1544`, `coach/prompt_builder.py:488`). Il flusso di /today (mark_done su /events, poi il dialog) funziona: /events scrive prima il congelato (`replanner.py:716-719`, `859`).
- **Evidenza:** Backup del 04/11 alle 13:18: lead_tryhard_gym, power_contact_gym e treadmill_zone2_cardio in attesa senza `resolved` salvato. Mirror del 07/11: le 4 sessioni del motore giocate a novembre non hanno `session_load_actual`, anche se il calcolo sul resolved congelato dà un valore più basso per lead_tryhard_gym del 04/11 (3 esercizi su 13 non fatti) e per power_contact_gym del 05/11 (4 su 13). Storico del mirror (archivio e settimane in memoria): 76 sessioni del motore giocate con flag `completed`, solo 5 con `session_load_actual` (tutte tra luglio e settembre). Da ottobre 0 su 10, e 51 sessioni parziali in tutto contano il carico pieno.
- **Fix proposto:** Al passo 4b si usano le `exercise_instances` del `_frozen` della sessione, cercato per (target_date, target_sid) tra le chiavi `(date, slot, session_id)`. Se non c'è (sessione già done da /events, custom o body-part) si ripiega sul `resolved` salvato come oggi. La scrittura al 7b resta dov'è: gli input del ciclo chiuso (passi 2-4, `_attach_prescribed_reps`, `attach_feedback_context`) non cambiano. Nessun ricalcolo delle sessioni passate.
- **Alternative:** B) Spostare la scrittura del 7b subito prima del 4b, comunque dopo il ciclo chiuso dei passi 2-4. Così anche il controllo 4c (`feedback.py:529-557`) vede la prescrizione congelata e si riattiva: oggi è muto per le sessioni del player perché manca il resolved salvato. Effetto: un `warning` in più nella risposta, che il client oggi non legge. C) Lasciare com'è: B312 resta di fatto spento per il player guidato.
- **Raccomandazione:** Opzione A (4b legge il congelato senza scriverlo prima): due o tre righe, e nessun effetto sul controllo 4c né sui passi 5-7. Con sessione completa il valore è uguale al `session_load_score` congelato; con esercizi saltati scende. Aggiornare ENGINE_ARCHITECTURE §«Prescribed vs actual load».
- **File:**
  - backend/api/routers/feedback.py
  - backend/tests/test_b312_feedback_endpoint.py
  - docs/ENGINE_ARCHITECTURE.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - Unico punto che scrive: feedback.py:488-497 (passo 4b); mark_planned lo toglie in replanner_v1.py:1309
  - Lettori tramite effective_session_load: report_engine.py:307 (_build_load, carico settimanale e load_ratio), report_engine.py:1544 (heatmap mensile), coach/prompt_builder.py:488
  - Frontend: solo il tipo in lib/types.ts:109, nessuna lettura
  - Congelamento: plan_revision.compute_played_resolved (feedback.py:301 e :335), write_played_resolved (feedback.py:652, replanner.py:859)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b312_feedback_endpoint.py::TestB312WithTheB413Freeze::test_actual_from_the_stored_copy_score_from_the_frozen_view (afferma session_load_actual == PRESCRIBED dello stub salvato): diventa == session_load_score congelato
  - Le altre di TestB312FeedbackEndpoint usano `_user_edited`, quindi congelato == stub: non cambiano
- **Test da aggiungere:**
  - Sessione del motore senza `resolved` salvato (la forma di prod) giocata via /feedback con una riga completed:false → session_load_actual scritto, più basso del prescritto congelato
  - Sessione completa → session_load_actual == session_load_score congelato
  - Flusso /today (mark_done su /events, poi /feedback) invariato
  - Ripiego B216 (piano in week_plans[lunedì]) → usa il congelato dell'alt_plan
  - _build_load del report legge il nuovo valore
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Per chi usa il player guidato sulle sessioni del catalogo, dal rilascio in poi il carico settimanale, la heatmap e il prompt del coach scendono per le sessioni con esercizi saltati. Le sessioni complete non cambiano. Il flusso «segna fatta» con il dialog non cambia. Le settimane passate non cambiano.
- **Correzione dati in prod:** no (raccomandato). Ricalcolare `session_load_actual` delle sessioni già giocate (51 parziali nello storico di Daniele) vorrebbe dire modificare sessioni passate. Solo se Daniele lo chiede esplicitamente, con dry run e diff.
- **Domande:**
  - Va bene che d'ora in poi il carico dei report scenda quando salti esercizi nel player, senza ricalcolare le sessioni passate?

#### PLAYED-SESSION-READ-KEYS — /events salva su una sessione giocata le chiavi che GET /week calcola in lettura

**Verdetto:** parziale · **effort** S · **rischio** basso · frontend no · schema user_state no

- **Causa:** `strip_derived` salta del tutto le sessioni giocate (`plan_revision.py:228`): la copia del client viene salvata così com'è. GET /week aggiunge alla copia: `process_cue` su tutte le sessioni (`week.py:466-491`, deterministico per utente, data e sessione, cues.py), e `feedback_summary`, `exercise_feedback` e `session_duration_seconds` sulle sessioni done, presi dal feedback_log (`week.py:436-463`, chiamati a 988-992). Il client rimanda tutta la settimana a /events (`api.ts:571-583`), quindi quelle chiavi finiscono nel record. La premessa della roadmap («copie di dati che stanno altrove») però vale solo in parte. `process_cue` si ricalcola sempre, quindi toglierlo è sicuro. `feedback_summary` ed `exercise_feedback` stanno nel feedback_log, che è tagliato alle ultime 7 voci (`adaptive_replan.py:145-147`); la fonte che dura è `difficulty` nel completion log (`feedback.py:610-612`) più `actual_exercises`. Il record non li ha mai di suo, quindi toglierli non perde niente di salvato. `session_duration_seconds` invece è un dato vero del record: lo scrive /feedback al passo 4b con max() (`feedback.py:498-505`), quindi toglierlo dalla copia del client cancellerebbe il valore salvato e violerebbe l'immutabilità. Inoltre `read_view` (le risposte delle scritture) non riattacca né pillole né cue (`plan_revision.py:266-286`). Se le chiavi vengono tolte e basta, dopo un'azione su /today le pillole delle sessioni giocate spariscono dallo schermo fino alla prossima GET.
- **Evidenza:** Mirror del 07/11: nessuna sessione giocata salvata (settimane 26/10 e 02/11) ha `process_cue`, `feedback_summary` o `exercise_feedback`; tutte hanno `session_duration_seconds` e `actual_exercises`. Il problema c'è nel codice ma oggi non tocca i dati di Daniele. I test lo tollerano: `test_b413_end_to_end.py:184-190` (READ_TIME_KEYS esclusi dal confronto) e `test_b413_freeze_prescription.py:217-220`.
- **Fix proposto:** (1) `strip_derived`: per ogni sessione giocata della copia del client che ha un gemello giocato nel piano salvato, con chiave (date, slot, session_id) e associazione a lista come per le custom, le 4 chiavi prendono il valore del gemello salvato, e vengono tolte se il gemello non le ha. Così `session_duration_seconds` resta quello salvato (il max) e le altre tre spariscono se non c'erano. Una sessione giocata senza gemello (client di prima di B371) perde solo `process_cue`. Tutti gli altri campi della sessione giocata restano come oggi.
(2) `read_view` produce la stessa vista di GET: sulla copia applica anche `_attach_feedback` (sessioni done) e `_attach_process_cues`. Serve un argomento `user_id` per il seme del cue, da passare ai 5 punti di chiamata. Il piano salvato resta grezzo. Senza (2) le pillole sparirebbero dopo ogni scrittura; con (2) si sistema anche un difetto che c'era già: il cue del giorno su /today sparisce dopo ogni scrittura, perché `strip_derived` lo toglie dalle sessioni in attesa e la risposta non lo rimette.
- **Alternative:** A) Togliere tutte e 4 le chiavi con pop, come dice la roadmap: no, perde `session_duration_seconds` salvato. B) «Vince il salvato» su tutta la sessione giocata: immutabilità più forte, ma se il salvato non ha `resolved` (sessioni vecchie) lo perderebbe, e la GET dopo lo ricalcolerebbe sullo stato attuale. È un rischio per le sessioni passate, quindi meglio la versione per chiave. C) Correzione più ampia, fuori scope: GET prende `feedback_summary` dal completion log invece che dal feedback_log a 7 voci, così le pillole delle sessioni oltre le ultime 7 non spariscono.
- **Raccomandazione:** (1) e (2) insieme, nel brief B414, solo backend con push su main. Nessuna correzione di dati.
- **File:**
  - backend/api/plan_revision.py
  - backend/api/routers/replanner.py
  - backend/api/routers/feedback.py
  - backend/api/routers/session.py
  - backend/api/routers/week.py
  - backend/tests/test_b371_plan_revision.py
  - docs/vocabulary_v1.md
  - docs/ROADMAP_CURRENT.md
- **Chiamanti e consumatori:**
  - strip_derived tramite guard_client_plan (plan_revision.py:258): replanner.py:360 (/override), :515 (/quick-add), :583 (/events); session.py:111 (add-exercise), :238 (remove-exercise), :433 (surface-override); chiamata diretta in replanner.py:579-581 (dry run di /events)
  - read_view: replanner.py:443, :550, :881; feedback.py:681; session.py:57; plan_revision.py:324 (vista interna di freeze_played_customs, legge solo gli `exercises` delle custom: non cambia)
  - Attacchi di GET: week.py:988-992
  - Lettori delle chiavi: session-card.tsx:318, :853-861, :878-882, :1158; daily-cue-banner.tsx:33-41; exercise-card.tsx:79; report_engine.py:948 (legge `feedback_summary` dal piano salvato, quindi in prod è sempre None già oggi); coach/prompt_builder.py:692 (durata dal feedback_log)
  - mark_planned toglie le stesse chiavi: replanner_v1.py:1301-1310 (invariato)
- **Test che fissano il comportamento attuale:**
  - backend/tests/test_b371_plan_revision.py::test_strip_derived_restores_custom_rows_and_drops_read_fields (righe 136-165: afferma che `process_cue` resta su una sessione done: va cambiato)
  - backend/tests/test_b413_end_to_end.py (READ_TIME_KEYS esclusi, righe 184-190: tollerante, si può stringere)
  - backend/tests/test_b413_freeze_prescription.py:217-220 (confronto meno process_cue)
  - backend/tests/test_undo_session_B192.py::test_T2_end_to_end_undo_clears_ui_fields_across_fetches (manda a /events la vista GET con le chiavi: deve restare verde)
  - backend/tests/test_b413_ladder_archive.py (usa read_view)
- **Test da aggiungere:**
  - strip_derived: sessione giocata con gemello → process_cue, feedback_summary ed exercise_feedback tolti se assenti nel salvato; session_duration_seconds uguale al valore salvato anche se il client ne manda un altro
  - strip_derived: sessione giocata senza gemello → solo process_cue tolto; sessioni in attesa invariate
  - End-to-end: feedback, GET con le chiavi, /events mark_done di un'altra sessione → nel salvato la sessione giocata non ha le 3 chiavi e la durata è il max salvato; la week_plan della risposta ha ancora pillola e cue
  - read_view: attacca feedback e cue sulla copia, il piano salvato resta byte-identico; deterministico (due chiamate danno lo stesso risultato)
- **Moduli ad alto rischio:**
  - —
- **Effetto sugli altri utenti:** Per tutti gli utenti, nelle scritture future: le sessioni giocate non accumulano più copie di campi di lettura, e la durata salvata non può più essere sovrascritta da una copia del client. Le risposte di /events, /override, /quick-add, /session/* e /feedback mostrano pillole e cue come GET: le pillole non spariscono più dopo un tap. Nessun dato salvato cambia; un valore finito prima nel record resta, perché si ripristina dal salvato.
- **Correzione dati in prod:** no. Nel mirror nessuna sessione giocata ha le chiavi copiate; per gli altri utenti quello che c'è resta (si ripristina dal salvato, non si cancella).

**Note trasversali (analisi:events-feedback):** Invarianti. Nessuna delle tre correzioni tocca planner_v2, macrocycle_v1, resolve_session, progression_v1 o closed_loop_v1, né from_phase, il lunedì, Fontainebleau o il filtro per attrezzatura. L'unico modulo ad alto rischio è replanner_v1, solo nel ramo mark_done di apply_events (voce 1). Sessioni passate: il 409 e il 422 della voce 1 non scrivono niente; il carico reale della voce 2 si scrive solo nel momento del «fatto» e non si ricalcola nessuna sessione passata; la voce 3 rafforza l'immutabilità (la durata salvata vince sulla copia del client). Tutto resta deterministico: nessun orologio né caso nuovo; il cue resta seminato per utente, data e sessione.

Moduli condivisi. `plan_revision.strip_derived` serve 6 endpoint di scrittura e il dry run di /events; `read_view` serve 5 risposte. La voce 3 li cambia tutti, quindi va provata con l'intera suite.

Rilascio. Le voci 2 e 3 e il 422 della voce 1 sono solo backend: push su main. Il 409 su /feedback va insieme al frontend della voce 1 (branch brief/B414-…, preview Vercel, OK di Daniele) o dopo. Con un 409 una PWA vecchia non perde il feedback, ma lo tiene in «Waiting to sync» e ferma il replay delle voci dopo (`guided-pending-feedback.ts:223`).

Osservazioni fuori scope, da registrare in roadmap:
(a) il feedback_log è tagliato a 7 voci (`adaptive_replan.py:145-147`). Daniele fa circa 10 sessioni a settimana, quindi le pillole delle sessioni più vecchie della settimana spariscono da GET. La fonte che dura è `difficulty` nel completion log.
(b) Il giorno per giorno del report settimanale legge `feedback_summary` dal piano salvato (`report_engine.py:948`): in prod è sempre None.
(c) Le custom non hanno mai `session_load_actual` (niente `resolved`): i report usano il loro `estimated_load_score`.
(d) Da ottobre le sessioni del motore in attesa sono salvate senza `resolved`. È per questo che B312 si è spento per il player guidato (correlato nel tempo con B369/B371 del 05/10, causa non verificata). La correzione della voce 2 non dipende da quella causa.

Verifiche non fatte. Non ho lanciato pytest né vitest, come da istruzioni: in fase 2 servono la suite completa, `npx tsc`, eslint, vitest e il build. Elenco dei test da adattare nelle singole voci. Le letture di prod sono state solo sul mirror e sul backup del 04/11, in sola lettura; nessun valore di salute riportato.

Documenti da aggiornare: docs/API_ENDPOINTS.md (/feedback 409 session_not_in_plan, /events 422 su mark_done), docs/vocabulary_v1.md (§B371 read-time fields e write responses), docs/ENGINE_ARCHITECTURE.md (§Prescribed vs actual load), docs/user_guide_v1.md (scelta nel player), ROADMAP_CURRENT (chiudere B312-LOAD-ACTUAL-VS-FROZEN e PLAYED-SESSION-READ-KEYS, voce nuova per l'orfano). La riga del bug-inbox del coach si spunta a chiusura del brief.

