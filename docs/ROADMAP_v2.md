# ROADMAP v2 — climb-agent

> Last updated: 2026-02-19 (Phase 2 complete — catalog cleanup, doc alignment)
> Fonte autoritativa per pianificazione. Allineata con PROJECT_BRIEF.md.

---

## §1 — Fasi completate (storico)

### Phase 0: Catalog ✅
- 102 esercizi, 29 sessioni, vocabulary aggiornato
- pangullich → campus_board

### Phase 1: Macrocycle engine ✅
- assessment_v1, macrocycle_v1, planner_v2
- user_state v1.5

### Phase 1.5: Post-E2E fixes ✅
- 14 finding, 13 risolti in 2 cluster
- 155 test verdi (da 115)

### Phase 3: UI (Next.js PWA) ✅
- 15 endpoint FastAPI, 19 pagine frontend
- Onboarding wizard, Today/Week/Plan/Session/Settings
- Mobile-first dark PWA con shadcn/ui

### Phase 3.1: Bug fixes ✅
- B21 done status, B22 auto-resolve, B23 skip status, B24 gym labels
- B9 cable_machine/leg_press, B26 test isolation
- 188 test verdi

### UI Test Fixes ✅
- Batch 1 (planner P0): UI-6 slot fix, UI-11 target_days, UI-13 dedup, UI-19 technique session
- Batch 1b (location): UI-6b location filtering, UI-19b technique resolver
- Batch 2 (18 UX items): UI-1 through UI-22 + FR-2/FR-3
- UI-23: gym slot priority in planner
- ~251 test verdi

### Phase 3.2: UI polish + adaptive ✅
- B25 adaptive replanning after feedback (conservative rules)
- B19 quick-add session (suggest + append, day+1 ripple only)
- B20 edit availability from Settings (preserve completed sessions on regen)
- B27 equipment label single source (frontend fetches from API)
- NEW-F6 phase mismatch warning in replanner
- NEW-F7 finger compensation after override
- B11 configurable test protocols → deferred to Phase 2.5
- ~290 test verdi, 17 endpoints

---

## §2 — Phase 1.75: Session enrichment + fix ✅

### §2.1 Pre-requisiti: fix P0 ✅

Tre bug bloccanti emersi dall'audit post-fix (docs/audit_post_fix.md).
Risolti 2026-02-16. 13 test nuovi in `test_p0_fixes.py`. 201 test verdi.

| ID | Finding | Fix applicato | File |
|----|---------|---------------|------|
| NEW-F2 | Equipment climbing mancante | 9 esercizi bouldering → `equipment_required_any: ["gym_boulder", "spraywall", "board_kilter"]` (OR logic). 1 esercizio lead (`slow_climbing`) → `equipment_required: ["gym_routes"]`. | exercises.json |
| NEW-F5 | Durate fase negative | `_MIN_TOTAL_WEEKS = 9`, ValueError se < 9, floor re-enforced dopo secondo scaling. | macrocycle_v1.py |
| NEW-F10 | Trip start_date con sessione HARD | `check_pretrip_deload`: `0 <= days_until` (era `0 <`). Nuova `compute_pretrip_dates()` include trip start_date. Wired in `week.py`. | macrocycle_v1.py, week.py |

### §2.2 Audit sessioni vs letteratura

Analisi completa delle strutture sessione attuali confrontate con
le raccomandazioni di:
- Hörst "Training for Climbing" (3rd ed.)
- Lattice Training "How to Structure Your Training" (2025)
- Tension Climbing (Will Anglin — hangboard protocols)
- Eva López — finger strength periodization

#### Vincolo fondamentale scoperto: ordine finger → climbing

Il consenso dalla letteratura è:
- Hangboard va fatto PRIMA di scalare (dita fresche per sforzo max)
- MA: dopo hangboard max, il climbing deve essere su PRESE GRANDI / movimento, NON limit crimping
- Hangboard max + limit bouldering su tacchette nella stessa sessione = rischio infortunio
- Lattice: "3-4 hang seguiti da bouldering di forza/potenza, poi antagonist — evitare mescolare stimoli"
- Tension Climbing: "dopo hard hangboard, scala su tipi di presa che NON hai appena lavorato"

**Conseguenza**: NON esiste una struttura a 7 blocchi uguale per tutte le sessioni.
La struttura dipende dallo stimolo primario della sessione.

#### Struttura target per tipo di sessione serale

**STRENGTH (finger focus) — ~1.5-2h:**
1. Warmup generale (10-15 min)
2. Hangboard max (7/53, max hang protocol) — 15-25 min
3. Climbing su prese grandi/movimento (NO limit crimp) — 30-45 min
4. Pulling strength (weighted pullup, lock-off) — 15-20 min
5. Core (hollow body, front lever, pallof) — 10-15 min
6. Antagonist/prehab (push-up, dip, rotator cuff) — 10-15 min
7. Cooldown/stretching — 5-10 min

**POWER (limit boulder focus) — ~1.5-2h:**
1. Warmup generale (10-15 min)
2. Limit bouldering (tacchette, sforzo max, dita FRESCHE) — 30-45 min
3. Campus/power (se energia residua) — 15-20 min
4. Explosive pull (campus pull, power pull) — 10-15 min
5. Core — 10-15 min
6. Antagonist/prehab — 10-15 min
*(niente hangboard pesante — le dita servono fresche per il muro)*

**POWER ENDURANCE — ~1.5-2h:**
1. Warmup generale (10-15 min)
2. Finger repeaters (leggeri, submaximal) — 10-15 min
3. 4x4 / circuit bouldering — 20-30 min
4. Route volume (lead routes, threshold) — 20-30 min
5. Core — 10-15 min
6. Antagonist/prehab — 10-15 min

**ENDURANCE — ~1.5-2h:**
1. Warmup generale (10-15 min)
2. ARC / volume routes (submaximal, continuous) — 30-45 min
3. Endurance repeaters (post-climbing ok per endurance) — 10-15 min
4. Pulling endurance (high rep pullup, rows) — 10-15 min
5. Core — 10-15 min
6. Antagonist/prehab — 10-15 min

#### Stato attuale vs target (verificato 2026-02-16)

| Sessione | Moduli pre-B8 | Moduli post-B8 | Stato |
|----------|---------------|----------------|-------|
| strength_long | 3 (warmup, finger_max, core_short) | 7 (warmup_climbing, finger_max, climbing_movement, pulling, core_standard, antagonist_prehab, cooldown_stretch) | ✅ |
| power_contact_gym | 4 (warmup, limit_main, antagonist, cooldown) | 6 (warmup_climbing, limit_boulder, campus_power, core_standard, antagonist_prehab, cooldown_stretch) | ✅ |
| power_endurance_gym | 4 (warmup, pe_main, core_short, cooldown) | 6 (warmup_climbing, pe_climbing, finger_endurance, core_standard, antagonist_prehab, cooldown_stretch) | ✅ |
| endurance_aerobic_gym | 4 (warmup, aerobic_main, technique, cooldown) | 6 (warmup_climbing, aerobic_main, capacity_hangboard, core_standard, antagonist_prehab, cooldown_stretch) | ✅ |

**Sessioni aggiuntive verificate** (candidati per enrichment futuro):
- `technique_focus_gym`: 4 moduli (warmup, technique drills inline, core, cooldown) — struttura già buona
- `gym_power_bouldering`: 3 moduli (template) — potrebbe beneficiare di antagonist/cooldown
- `gym_aerobic_endurance`: 3 moduli (template) — potrebbe beneficiare di core/cooldown
- `gym_power_endurance`: 3 moduli (template) — potrebbe beneficiare di antagonist/cooldown
- `gym_technique_boulder`: 2 moduli (template) — il più scarno, mancano core/antagonist/cooldown

#### Template nuovi necessari

| Template | Esercizi | Note |
|----------|----------|------|
| pulling_strength | weighted_pullup *(already present)*, lock_off_isometric *(already present)*, one_arm_pullup_assisted *(already present)*, barbell_row *(already present)* | Per sessioni strength/power |
| pulling_endurance | pullup *(already present, high-rep config)*, inverted_row *(already present)* | Per sessioni endurance |
| antagonist_prehab | overhead_press *(already present)*, dip *(already present)*, reverse_wrist_curl *(already present)*, band_external_rotation *(already present)*, pushup *(already present)* | Year-round (Lattice: "should be included year round") |
| limit_bouldering | limit_bouldering *(already present)*, board_limit_boulders *(already present)* | Per sessioni power (dita fresche) |
| climbing_movement | gym_technique_boulder_drills *(already present, su prese grandi)*, arc_easy_traverse *(already present)* | Post-hangboard nelle sessioni strength |
| route_volume | threshold_climbing *(already present)*, gym_arc_easy_volume *(already present)*, route_redpoint_attempt **(da creare)** | Per sessioni PE ed endurance |
| core_standard | core_hollow_hold *(already present)*, front_lever_tuck *(already present)*, pallof_press *(already present)*, dead_bug *(already present)*, hanging_leg_raise *(already present)* | Standard in ogni sessione serale |

#### Esercizi nuovi necessari — audit vs catalogo

Verifica effettuata il 2026-02-16 sul catalogo 102 esercizi.
La maggior parte degli esercizi elencati come "nuovi" **esiste già**.

| Esercizio richiesto | ID nel catalogo | Stato |
|---------------------|-----------------|-------|
| weighted_pullup | `weighted_pullup` | **Già presente** |
| lock_off_hold | `lock_off_isometric` | **Già presente** (nome diverso) |
| one_arm_pullup_negative | `one_arm_pullup_assisted` | **Già presente** (variante simile) |
| barbell_bent_over_row | `barbell_row` | **Già presente** (nome diverso) |
| dumbbell_overhead_press | `overhead_press` | **Già presente** (nome diverso) |
| dip | `dip` / `dips` | **Già presente** |
| reverse_wrist_curl | `reverse_wrist_curl` | **Già presente** |
| band_external_rotation | `band_external_rotation` | **Già presente** |
| limit_boulder_attempt | `limit_bouldering` / `board_limit_boulders` | **Già presente** (2 varianti) |
| 4x4_circuit | `gym_power_endurance_4x4` / `four_by_four_bouldering` | **Già presente** (2 varianti) |
| arc_route_set | `gym_arc_easy_volume` / `arc_training` | **Già presente** (coperti da varianti ARC esistenti) |
| push_up_standard | `pushup` / `pushups` | **Già presente** |
| high_rep_pullup | `pullup` | **Già presente** (config set/rep diversa) |
| ring_row | `inverted_row` | **Già presente** (nome diverso) |
| hollow_body_hold | `core_hollow_hold` | **Già presente** (nome diverso) |
| front_lever_progression | `front_lever_tuck` | **Già presente** (nome diverso) |
| route_redpoint_attempt | — | **Da creare** |

**Risultato**: solo ~1 esercizio genuinamente mancante (`route_redpoint_attempt`).
I 7 template nuovi possono essere costruiti interamente con esercizi esistenti.

### §2.3 Implementazione B8 — Session enrichment ✅

Completato 2026-02-16. 13 test nuovi in `test_session_enrichment.py`. 214 test verdi.

| Deliverable | Dettaglio |
|-------------|-----------|
| Esercizi nuovi | 11: route_redpoint_attempt, 7 cooldown stretches, 3 active flexibility |
| Template nuovi | 8: warmup_climbing, warmup_strength, warmup_recovery, pulling_strength, pulling_endurance, antagonist_prehab, core_standard, cooldown_stretch |
| Sessioni riscritte | 4: strength_long (7 mod), power_contact_gym (6 mod), power_endurance_gym (6 mod), endurance_aerobic_gym (6 mod) |
| Sessione nuova | core_conditioning_standalone (B1, 6 mod, home) — non in planner/pool |
| Test | 13 nuovi in test_session_enrichment.py |

Dettagli implementazione:
1. Creati 8 template nuovi per warmup/pulling/antagonist/core/cooldown
2. Aggiunti 11 esercizi (1 route, 7 cooldown, 3 flexibility attiva) al catalogo
3. Riscritte le 4 sessioni serali principali con struttura target da §2.2
4. NON toccate sessioni home/lunch/recovery
5. NON toccato planner/replanner
6. B1 implementato come core_conditioning_standalone (non auto-schedulato)

### §2.4 Fix P1 collegati

| ID | Finding | Descrizione | Fix | Stato |
|----|---------|-------------|-----|-------|
| NEW-F3a | Test sessions mai pianificate (scheduling) | test_max_hang_5s esiste ma non è in _SESSION_META né in nessun pool. Nessun scheduling periodico. | Pass 3 in planner_v2: `is_last_week_of_phase=True` inietta test sessions (test_max_hang_5s, test_repeater_7_3, test_max_weighted_pullup) su ultima settimana di base/strength_power. Creati 2 nuovi session file. API wired in deps.py/week.py. | ✅ DONE |
| NEW-F3b | assessment.tests mai aggiornato dal closed loop | Closed loop aggiorna working_loads ma non assessment.tests dopo sessioni test. | Aggiornare assessment.tests nel closed loop quando sessione è un test. Creare test_power_endurance. | TODO (Phase 2) |
| NEW-F4 | Ripple effect proporzionale | Dopo override hard/max, il replanner ora applica downgrade proporzionale. | Delta=1: hard→medium (complementary_conditioning), medium→low (regeneration_easy), low→keep. Delta=2: tutto non-low→recovery. Solo direzione upward (più intenso → più leggero il giorno dopo). | ✅ DONE |
| F6-partial | Intent "projecting" mancante | 11/12 intent funzionano, ma "projecting" (naturale per climber) non è mappato. | Aggiunto `"projecting": "power_contact_gym"` in INTENT_TO_SESSION. 13 intent totali. | ✅ DONE |
| NEW-F1 | Prescription climbing vuota | Esercizi climbing hanno solo notes generico. Mancano: grado suggerito, volume, rest. | Moved to Phase 2.5 — see §2.6 | ⏩ Phase 2.5 |

### §2.5 B4 — Load score ✅

Implementato 2026-02-17. Approccio a due livelli:

1. **`estimated_load_score`** (fallback, planner): basato su intensity mapping (low=20, medium=40, high=65, max=85). Presente su ogni sessione nel piano settimanale e nel replanner fill.
2. **`session_load_score`** (primario, resolver): somma di `fatigue_cost` (1-9) di tutti gli esercizi risolti. Presente nell'output di `resolve_session()`.
3. **`weekly_load_summary`**: aggiunto al piano settimanale con `total_load`, `hard_days_count`, `recovery_days_count`. Ricalcolato dopo deload transform.

Necessario per: overtraining monitoring, adaptive deload input, UI visualization.

### §2.6 Exercise Catalog Audit (Phase 2.5 — da fare)

Audit sistematico del catalogo esercizi contro la literature review
(`docs/literature_review_climbing_training.md`, 19 sezioni).
Da fare DOPO Phase 2 (tracking) per beneficiare dei dati di feedback reali.

Include anche:
- **NEW-F1** (prescription climbing vuota): aggiungere suggested_grade_offset, volume, rest_between agli esercizi climbing.
- **B11** (configurable test protocols): 5s vs 7s hang, 1RM vs 2RM pullup con conversione automatica. Deferred from Phase 3.2.
- **Test exercise expansion**: aggiungere esercizi con `is_test: true` per coprire più assi dell'assessment. Phase 1.75 ha creato test_repeater_7_3 e test_max_weighted_pullup come session files, ma servono più esercizi test specializzati.
- **UI-9** (limitation filtering verification): verificare che resolve_session.py controlli limitations.active_flags contro controindicazioni esercizi. Se no → implementare.
- **UI-20** (warmup exercise variety): warmup template pool ha opzioni limitate o tie-break seleziona sempre shoulder_car. Espandere pool o migliorare selezione.

Scope:
1. **Qualità prescription**: parametri (set, rep, rest, durata) coerenti con la letteratura?
   Esercizi con notes generiche che meritano prescrizioni precise?
   Confrontare con raccomandazioni specifiche di Hörst, Lattice, Eva López.
   Esempio: un esercizio di max hang ha rest_seconds coerente con i 3-5 min
   raccomandati dalla letteratura? I repeater hanno il protocollo 7/3 corretto?
2. **Gap di copertura**: mancano esercizi per aree coperte dalla literature review?
   Verificare per ogni sezione della literature review (§1-19):
   - §1-4: Periodizzazione e hangboard — protocolli mancanti?
   - §5-8: Sessioni serali e complementary — esercizi gym mancanti?
   - §9-13: Core, handstand, technique — varianti sufficienti?
   - §14-16: Conditioning, ARC — esercizi specifici mancanti?
   - §17-18: Flexibility e cooldown — copertura sufficiente post-B8?
3. **Consistenza interna**: categorie, pattern, stress_tags, fatigue_cost
   calibrati in modo uniforme e coerente tra esercizi simili?
   Esempio: tutti gli esercizi di max hang hanno fatigue_cost simile?
   Tutti i core exercises hanno stress_tags coerenti tra loro?
4. **Validazione letteratura**: ogni esercizio ha parametri allineati con
   le raccomandazioni delle fonti (Hörst, Lattice, Eva López, ecc.)?
   Focus su: intensità, volume, rest, frequenza raccomandata.
5. **Check tecnici**: equipment_required coerente, esercizi mai selezionati
   dal resolver, allineamento resistance_band vs band, pattern non coperti.
6. **Dedicated test exercises**: Create exercises with `"is_test": true` flag in the catalog
   for assessment sessions. Currently test sessions (test_max_hang_5s, test_repeater_7_3,
   test_max_weighted_pullup) resolve through standard training templates. Dedicated test
   exercises would provide:
   - Clear separation between training and assessment in the catalog
   - Specific test protocols (precise prescription, not training-oriented)
   - Clean tracking: distinguish "this was a test" from "this was training" in logs
   - Required tests: max_hang_5s (finger_strength), repeater_7_3 (power_endurance)
   - Optional tests: max_weighted_pullup (pulling_strength),
     continuous_climbing_minutes (endurance)
   - technique and body_composition remain self-eval (no automated test exercise)
   Depends on Phase 2 (tracking) to get full value from the separation.

Dipendenza: il tracking (Phase 2) fornirà dati reali di feedback per informare
l'audit — se un esercizio ha prescrizioni sbagliate, il feedback lo rivelerà.

Posizionamento: Phase 2.5 (tra tracking e UI polish).

---

> **UI Test (feb 2026)**: 22 findings from manual end-to-end test.
> Batch 1 (4 P0/P1), Batch 1b (2 location fixes), Batch 2 (18 UX items), UI-23 (gym priority).
> All done except: UI-9 (Phase 2.5), UI-18 (Phase 2), UI-20 (Phase 2.5), FR-1 (Phase 2).
> See §8 for full status.

## §3 — Phase 3.2: UI polish + adaptive ✅ (complete — B11 deferred to Phase 2.5)

Completed in Batch 2: UI-1, UI-2, UI-3, UI-4, UI-5, UI-7, UI-8, UI-10, UI-12, UI-14, UI-15, UI-16, UI-17, UI-22, FR-2, FR-3.
Phase 3.2 bundle: B25, B19, B20, B27, NEW-F6, NEW-F7 — all done. B11 deferred to Phase 2.5 (depends on catalog audit).

| ID | Titolo | Stato | Note |
|----|--------|-------|------|
| B25 | Adaptive replanning after feedback | ✅ DONE | Conservative rules: very_hard → downgrade, 2× very_hard → insert recovery |
| B19 | Quick-add session | ✅ DONE | suggest_sessions + apply_day_add, day+1 ripple only, warnings |
| B20 | Edit availability from Settings | ✅ DONE | AvailabilityEditor component, force regen preserving completed sessions |
| B27 | Equipment label single source | ✅ DONE | Frontend fetches from GET /api/onboarding/defaults |
| NEW-F6 | Warning phase_mismatch nel replanner | ✅ DONE | Logged in adaptations when override uses different phase |
| NEW-F7 | Finger compensation dopo override | ✅ DONE | _compensate_finger: replaces complementary with finger_maintenance_home, 48h gap |
| B11 | Configurable test protocols | ⏩ Phase 2.5 | Depends on catalog audit and dedicated test exercises |

---

## §4 — Phase 2: Tracking + outdoor

> UI-18 moved to Phase 2.5 — depends on exercise catalog audit for load_parameters

| ID | Titolo | Priorità | Effort | Descrizione |
|----|--------|----------|--------|-------------|
| B2 | Outdoor sessions / logging | ✅ DONE | Large | Sessioni outdoor non risolte dall'engine: logging di gradi/stile/tentativi. Schema diverso da sessioni indoor. Integration con trip planning. |
| B10 | Outdoor climbing spots | ✅ DONE | Medium | Location type per spot outdoor (es. "Berdorf — boulder — weekends"). Usabile in availability grid e trip planning. |
| NEW-F8 | Easy climbing nel pool deload | ✅ DONE | Small | Verificare con letteratura e aggiungere climbing leggero nel pool deload. |
| NEW-F9 | Finger maintenance in fase PE | ✅ DONE | Small | Forzare almeno 1 finger_maintenance nel pool PE come primary. |
| — | Motivational quotes | ✅ DONE | Small | 1 citazione per sessione, contestuale (hard day → perseveranza, deload → pazienza). Rotazione 30 giorni. |
| B28 | Cross-session recency nel resolver | ✅ DONE | Small | Alimentare `recent_ex_ids` dal log sessioni completate per variabilità esercizi tra sessioni. Vedi §4.1. |
| UI-18 | Exercise weight/load prescription | → Phase 2.5 | Large | Resolver calculates initial loads from assessment tests. Frontend displays suggested weight. Depends on working_loads population. |
| FR-1 | Outdoor as availability location | ✅ DONE | Medium | "Outdoor" option in availability grid. Outdoor slots → logging only, no resolved sessions. Links to B2 outdoor sessions. |
| — | Report engine | ✅ DONE | Medium | Settimanale (aderenza, volume, highlight), mensile (trend, distribuzione gradi). |

### §4.1 Cross-session exercise variety (B28)

Attualmente `recent_ex_ids` è inizializzato vuoto ad ogni `resolve_session()`.
Risultato: blocchi con selezione dinamica (core, cooldown, pulling, antagonist)
selezionano sempre lo stesso esercizio (primo alfabeticamente),
sessione dopo sessione, settimana dopo settimana. Niente varietà.

Fix proposto: alimentare `recent_ex_ids` dal log sessioni completate.
Il meccanismo di scoring (-100/-25/-5) già esistente in `score_exercise()`
creerà variabilità automatica senza aggiungere randomness.

**Nota tecnica importante**: `pick_best_exercise_p0()` (usato sia per template blocks
che per inline blocks) attualmente NON chiama `score_exercise()`. Usa un tie-break
puramente alfabetico. Per attivare la recency, occorre:
1. Alimentare `recent_ex_ids` dal log sessioni (piccolo — solo estrazione dati)
2. Integrare `score_exercise()` in `pick_best_exercise_p0()` come tie-break
   al posto dell'ordine alfabetico (medio — richiede attenzione al determinismo)

Dipendenza: richiede log sessioni completate (tracking).
Determinismo preservato: stessa storia di sessioni → stessa selezione.

---

## §5 — Phase 3.5: LLM Coach

Claude Sonnet come layer conversazionale sopra engine deterministico.
- System prompt dinamico (inietta user_state + piano + log)
- Endpoint POST /chat
- Casi d'uso: onboarding conversazionale, coaching pre-sessione,
  analisi post-sessione, discussione climbing, citazioni motivazionali
- L'LLM suggerisce e conversa, NON modifica il piano direttamente
- API key gestita nel backend (env var)

---

## §6 — Phase 4: Evolution

- Più tipi di goal (boulder, all-round, outdoor_season)
- Report annuale
- P1 ranking nel resolver (recency, intensità, fatica)
- Periodizzazione multi-macrociclo (stagionale)
- Notifiche/reminder
- Guided timer mode (countdown, rest timer colorato, vibrazione/beep PWA)
  Spec completa in DESIGN_GOAL_MACROCICLO_v1.1.md §12b

---

## §7 — Backlog futuro / da esplorare

Spunti non bloccanti emersi dagli audit. Da valutare se e quando inserirli
nelle fasi attive.

| Tema | Dettaglio | Origine |
|------|-----------|---------|
| Test assessment aggiuntivi | Aggiungere test oggettivi per technique (route-reading score) e endurance (continuous climbing time) per ridurre dipendenza da proxy/self-eval | audit_post_fix spunto A |
| Altre dimensioni assessment | Valutare mobility/flexibility, mental game, contact strength come assi separati | audit_post_fix spunto B |
| Aggiornamento profilo nel tempo | Verificare che il closed loop aggiorni assessment.tests (non solo working_loads) dopo sessioni test | audit_post_fix spunto C |
| Deload vs letteratura | Confrontare struttura deload con Hörst, Lattice, Eva López — potrebbe essere troppo leggera | audit_post_fix spunto D |
| Override intensity cap | Warning quando utente fa override con sessione di intensity superiore al cap della fase corrente | audit_post_fix spunto F |
| Adattività avanzata | Readiness score, overreach detection, plateau detection | DESIGN_DOC §4.4 (spec) |
| Bouldering discipline | Espandere da lead-only a bouldering e mixed | memory progetto |
| Gym preferences | Preferire palestra specifica per giorno (es. "BKL il lunedì") | memory progetto |
| Midjourney imagery | Immagini fotorealistiche climbing per UI (dark background, Midjourney v6) | memory progetto |

---

## §8 — Registro completo B-items e finding

Tabella unica con TUTTI gli item tracciati.

| ID | Titolo | Stato | Fase | Sezione roadmap |
|----|--------|-------|------|-----------------|
| B1 | Standalone core session | ✅ DONE | 1.75 | §2.3 |
| B2 | Outdoor sessions / logging | ✅ DONE | 2 | §4 |
| B3 | Plan validation vs literature | TODO (→ audit §2.2) | 1.75 | §2.2 |
| B4 | Load score / weekly fatigue | ✅ DONE | 1.75 | §2.5 |
| B5 | Replanner phase-aware | ✅ DONE | 1.5 | §1 |
| B6 | PE assessment repeater | ✅ DONE | 1.5 | §1 |
| B7 | Validazioni edge case | ✅ DONE | 1.5 | §1 |
| B8 | Session enrichment + modules | ✅ DONE | 1.75 | §2.3 |
| B9 | cable_machine, leg_press | ✅ DONE | 3.1 | §1 |
| B10 | Outdoor climbing spots | ✅ DONE | 2 | §4 |
| B11 | Configurable test protocols | ⏩ Phase 2.5 | 2.5 | §2.6 |
| B19 | Quick-add session | ✅ DONE | 3.2 | §3 |
| B20 | Edit availability from Settings | ✅ DONE | 3.2 | §3 |
| B21 | Done button status | ✅ DONE | 3.1 | §1 |
| B22 | Events endpoint auto-resolve | ✅ DONE | 3.1 | §1 |
| B23 | Skip status update | ✅ DONE | 3.1 | §1 |
| B24 | Gym equipment labels | ✅ DONE | 3.1 | §1 |
| B25 | Adaptive replanning after feedback | ✅ DONE | 3.2 | §3 |
| B26 | Test isolation fixtures | ✅ DONE | 3.1 | §1 |
| B27 | Equipment label single source | ✅ DONE | 3.2 | §3 |
| NEW-F1 | Prescription climbing vuota | TODO | 2.5 | §2.6 |
| NEW-F2 | Equipment climbing mancante | ✅ DONE | 1.75 | §2.1 |
| NEW-F3a | Test sessions scheduling | ✅ DONE | 1.75 | §2.4 |
| NEW-F3b | assessment.tests closed loop | TODO | 2.5 | §2.4 |
| NEW-F4 | Ripple effect proporzionale | ✅ DONE | 1.75 | §2.4 |
| NEW-F5 | Durate fase negative | ✅ DONE | 1.75 | §2.1 |
| NEW-F6 | Warning phase_mismatch | ✅ DONE | 3.2 | §3 |
| NEW-F7 | Finger compensation | ✅ DONE | 3.2 | §3 |
| NEW-F8 | Easy climbing in deload | ✅ DONE | 2 | §4 |
| NEW-F9 | Finger maintenance in PE | ✅ DONE | 2 | §4 |
| NEW-F10 | Trip start_date HARD | ✅ DONE | 1.75 | §2.1 |
| F6-partial | Intent projecting mancante | ✅ DONE | 1.75 | §2.4 |
| B28 | Cross-session recency nel resolver | ✅ DONE | 2 | §4.1 |
| B29 | Dedicated test exercises in catalog | TODO | 2.5 | §2.6 |
| B-NEW | Exercise catalog audit | TODO | 2.5 | §2.6 |
| UI-1 | Trip date picker: end_date validation | ✅ DONE | Batch 2 | §3 |
| UI-2 | uvicorn --reload-exclude for data dir | ✅ DONE | Batch 2 | §3 |
| UI-3 | Settings: weight/height not displayed | ✅ DONE | Batch 2 | §3 |
| UI-4 | Settings: React duplicate key on gyms | ✅ DONE | Batch 2 | §3 |
| UI-5 | Plan starts always on Monday (partial week) | ✅ DONE | Batch 2 | §3 |
| UI-6 | Planner ignores slot + preferred_location | ✅ DONE | Batch 1 | §2 |
| UI-7 | Goal deadline validation (past date) | ✅ DONE | Batch 2 | §3 |
| UI-8 | Gym name required or auto-default | ✅ DONE | Batch 2 | §3 |
| UI-9 | Limitation filtering in resolver (verify) | TODO | 2.5 | §2.6 |
| UI-10 | Experience vs grade cross-validation warning | ✅ DONE | Batch 2 | §3 |
| UI-11 | Planner ignores target_training_days_per_week | ✅ DONE | Batch 1 | §2 |
| UI-12 | Settings: availability show location/gym | ✅ DONE | Batch 2 | §3 |
| UI-13 | Resolver selects duplicate exercises in session | ✅ DONE | Batch 1 | §2 |
| UI-14 | Load score (B4) visible in frontend | ✅ DONE | Batch 2 | §3 |
| UI-15 | Replan dialog: add intent selection | ✅ DONE | Batch 2 | §3 |
| UI-16 | Undo session "done" status | ✅ DONE | Batch 2 | §3 |
| UI-17 | Feedback optional + visible after submit | ✅ DONE | Batch 2 | §3 |
| UI-18 | Exercise load/weight prescription display | TODO | 2.5 | §4 |
| UI-19 | technique_focus_gym resolves wrong | ✅ DONE | Batch 1 | §2 |
| UI-20 | Warmup variety (always shoulder_car) | TODO | 2.5 | §2.6 |
| UI-21 | Session structure info (informational) | ℹ️ | — | — |
| UI-22 | Week view: multi-week navigation | ✅ DONE | Batch 2 | §3 |
| FR-1 | Outdoor as availability location option | ✅ DONE | 2 | §4 |
| FR-2 | Warning: no climbing equipment in gyms | ✅ DONE | Batch 2 | §3 |
| FR-3 | Feedback badge/sticker on exercises | ✅ DONE | Batch 2 | §3 |
| UI-23 | Gym slot priority in planner | ✅ DONE | UI-23 | §3 |
| FR-4 | Outdoor vs gym slot priority | TODO | 2 backlog | §9.4 |
| B29 | Undo "done" non funziona | ✅ DONE | post-2 | — |
| B30 | easy_climbing_deload "unknown" nel dialog | ✅ DONE | post-2 | — |
| B31 | Add session "other" mostra solo deload | ✅ DONE | post-2 | — |
| B32 | Feedback done non visibile in UI | ✅ DONE | post-2 | — |
| B33 | Quote motivazionale nella Today view | ✅ DONE | post-2 | — |
| B34 | Feedback badge sessione mancante in Today view | TODO | post-2 | — |
| B35 | Feedback esercizio singolo non visibile (FR-3 incompleto) | TODO | post-2 | — |
| B36 | "— unknown" type label in Add session all-sessions list | ✅ DONE | post-2 | — |

---

## §9 — Future features (from UI testing insights, feb 2026)

### 9.1 — Testing week in onboarding (Phase 2.5)
After onboarding review step, offer the user two options:
- "Start training now" — generates macrocycle immediately with available data
- "Do a test week first (recommended)" — generates a special 1-week assessment plan

The test week includes 3-4 sessions:
- Day 1: test_max_hang_5s (finger strength)
- Day 2: test_max_weighted_pullup (pulling strength)
- Day 3: test_repeater_7_3 (power endurance)
- Day 4 (optional): continuous_climbing_minutes (endurance)

After completing the test week, results update assessment.tests → profile is recomputed
→ then the real macrocycle is generated with precise data.

Depends on: Phase 2 tracking (to capture test results automatically)

### 9.2 — Expanded onboarding test battery (Phase 3.2)
Add more optional test fields to onboarding step 7 (tests):
- Core: max plank hold (seconds)
- Flexibility: can touch toes (boolean), shoulder mobility (boolean)
- Aerobic: resting heart rate, continuous climbing time (minutes)
- Pulling: max pull-ups (reps)

These are ALL optional with "Skip" prominent. Purpose:
- Gives the system a more complete initial profile
- Communicates seriousness and depth to the user
- Even displaying the option (without filling) signals "this matters"

### 9.3 — Outdoor vs gym priority preference (Phase 2)
In onboarding, after availability step, ask:
"When both outdoor and gym are available on the same day, which do you prefer?"
- Options: "Prioritize outdoor climbing" / "Prioritize gym training" / "Alternate"

This informs the planner the same way UI-23 does for gym vs home:
- Outdoor-priority: outdoor slots get climbing sessions first
- Gym-priority: gym slots get structured training first
- Alternate: even distribution

Depends on: FR-1 (outdoor as availability location)

### 9.4 — Outdoor vs gym priority preference (Phase 2 backlog — FR-4)
When both outdoor and gym slots are available on the same day, user can set a preference:
- "Prioritize outdoor climbing" — outdoor slots get climbing sessions first
- "Prioritize gym training" — gym slots get structured training first
- "Alternate" — even distribution

Works the same way as UI-23 (gym slot priority). Setting lives in planning_prefs.
Depends on: FR-1 (outdoor as availability location — ✅ DONE in Phase 2)

---

## §10 — Regole di allineamento

1. **Dopo ogni sessione di sviluppo**: aggiornare questo file (stati, nuovi item) E
   aggiornare la sezione Roadmap in PROJECT_BRIEF.md (solo stati fasi ✅/🔲)
2. **Nuovi finding/bug**: aggiungerli in §8 con ID progressivo e nella sezione fase appropriata
3. **BACKLOG.md e NEXT_STEPS.md sono archiviati** in _archive/ — non più aggiornati
4. **audit_post_fix.md e e2e_test_results.md** restano in docs/ come storico test
5. **DESIGN_GOAL_MACROCICLO_v1.1.md** resta il design doc (il "perché") — non contiene stati o planning operativo
6. **Questo file** è il "cosa fare e quando" — la fonte autoritativa per la pianificazione
