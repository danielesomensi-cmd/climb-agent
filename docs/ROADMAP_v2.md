# ROADMAP v2 — climb-agent

> Last updated: 2026-02-16
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

---

## §2 — Prossimo: Phase 1.75 — Session enrichment + fix

### §2.1 Pre-requisiti: fix P0

Tre bug bloccanti emersi dall'audit post-fix (docs/audit_post_fix.md).
Da risolvere PRIMA di qualsiasi enrichment.

| ID | Finding | Descrizione | Fix | File |
|----|---------|-------------|-----|------|
| NEW-F2 | Equipment climbing mancante | Esercizi climbing (gym_arc_easy_volume, gym_technique_boulder_drills, gym_power_endurance_4x4, board_limit_boulders) hanno equipment_required: []. Servono gym_boulder o gym_routes. | Aggiungere equipment_required ai ~5-10 esercizi climbing | exercises.json |
| NEW-F5 | Durate fase negative | _compute_phase_durations produce durate negative per total_weeks < 9. Riga 179 sovrascrive il floor di riga 166. | Validare total_weeks ≥ 9, floor nel secondo scaling, mai durate negative | macrocycle_v1.py |
| NEW-F10 | Trip start_date con sessione HARD | Giorno di partenza trip ha sessione hard. Il window pretrip copre solo i 5 giorni PRIMA, non il giorno stesso. | Includere trip.start_date in pretrip_dates | macrocycle_v1.py o planner_v2.py |

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

#### Stato attuale vs target

| Sessione attuale | Blocchi attuali | Blocchi target | Gap |
|-----------------|----------------|----------------|-----|
| strength_long | ~3 (finger_max, warmup, qualche pulling) | 7 (warmup → finger_max → climbing_jugs → pulling → core → antagonist → cooldown) | Mancano: climbing on jugs, core, antagonist, cooldown |
| power_contact_gym | ~4 (campus, limit boulder, bench_press senza prescription) | 6 (warmup → limit_boulder → campus → explosive_pull → core → antagonist) | Manca: core, antagonist strutturati. bench_press senza prescription. Sessione scarsa (solo 4 esercizi per 1.5h) |
| power_endurance_gym | ~3 (4x4, route intervals) | 6 (warmup → finger_repeaters → 4x4 → route_volume → core → antagonist) | Mancano: finger repeaters leggeri, core, antagonist |
| endurance_aerobic_gym | ~2-3 (ARC, easy laps) | 6 (warmup → ARC → endurance_repeaters → pulling_endurance → core → antagonist) | Mancano: endurance repeaters, pulling, core, antagonist |

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

### §2.3 Implementazione B8 — Session enrichment

Dopo l'audit (§2.2) e i fix P0 (§2.1):
1. Creare i template nuovi necessari (§2.2)
2. Aggiungere il ~1 esercizio mancante al catalogo
3. Riscrivere le 4 sessioni serali principali con la struttura target
4. NON toccare sessioni home/lunch/recovery
5. NON toccare il planner/replanner
6. Aggiungere test per ogni sessione riscritta (resolver deve funzionare)
7. Incorpora B1 (core_conditioning_home come sessione standalone)

### §2.4 Fix P1 collegati

| ID | Finding | Descrizione | Fix |
|----|---------|-------------|-----|
| NEW-F3 | Test sessions mai pianificate | test_max_hang_5s esiste ma non è in _SESSION_META né in nessun pool. Nessun scheduling periodico. assessment.tests mai aggiornato dal closed loop. | Aggiungere a _SESSION_META e pool fine-Base/fine-SP. Creare test_power_endurance. Scheduling ogni N settimane. |
| NEW-F4 | Ripple effect troppo conservativo | Dopo override hard/max, il replanner controlla solo giorni +2/+3 e solo sessioni già hard. Sessioni medium lasciate invariate. | Forzare giorno successivo a recovery dopo hard/max override |
| F6-partial | Intent "projecting" mancante | 11/12 intent funzionano, ma "projecting" (naturale per climber) non è mappato. Variante indoor possibile: limit bouldering. | Aggiungere intent projecting → limit bouldering indoor |
| NEW-F1 | Prescription climbing vuota | Esercizi climbing hanno solo notes generico. Mancano: grado suggerito, volume, rest. | Aggiungere suggested_grade_offset, volume, rest_between. Resolver calcola grado da current_grade + offset. |

### §2.5 B4 — Load score

Ogni sessione nel planner avrà `estimated_load_score`.
Modello semplice iniziale: low=20, medium=40, high=65, max=85.
Output: weekly summary con total load, hard days count.
Necessario per: overtraining monitoring, adaptive deload input, UI visualization.

---

## §3 — Phase 3.2: UI polish + adaptive

| ID | Titolo | Priorità | Effort | Descrizione |
|----|--------|----------|--------|-------------|
| B25 | Adaptive replanning after feedback | **Alta** | Medium | Regole conservative: very_hard → downgrade next hard day. 2× very_hard in 3 giorni → insert recovery. Solo downgrade automatici, mai upgrade senza conferma utente. |
| B19 | Quick-add session | Media | Medium | Aggiungere sessione extra da week view. Suggerisce tipo basato su fase e bilancio settimanale. |
| B20 | Edit availability da Settings | Media | Small | Form frontend + API call a set_availability. |
| B11 | Configurable test protocols | Media | Small | 5s vs 7s hang, 1RM vs 2RM pullup con conversione automatica. |
| B27 | Equipment label single source | Media | Small | Labels equipment definite in un solo posto, non duplicati tra onboarding.py e frontend. |
| NEW-F6 | Warning phase_mismatch nel replanner | Bassa | Small | Avvisare quando l'utente fa override con sessione incompatibile con la fase corrente. |
| NEW-F7 | Finger compensation dopo override | Bassa | Small | Se override rimuove sessione finger, compensare nei giorni successivi. |

---

## §4 — Phase 2: Tracking + outdoor

| ID | Titolo | Priorità | Effort | Descrizione |
|----|--------|----------|--------|-------------|
| B2 | Outdoor sessions / logging | Media | Large | Sessioni outdoor non risolte dall'engine: logging di gradi/stile/tentativi. Schema diverso da sessioni indoor. Integration con trip planning. |
| B10 | Outdoor climbing spots | Media | Medium | Location type per spot outdoor (es. "Berdorf — boulder — weekends"). Usabile in availability grid e trip planning. |
| NEW-F8 | Easy climbing nel pool deload | Bassa | Small | Verificare con letteratura e aggiungere climbing leggero nel pool deload. |
| NEW-F9 | Finger maintenance in fase PE | Bassa | Small | Forzare almeno 1 finger_maintenance nel pool PE come primary. |
| — | Motivational quotes | Bassa | Small | 1 citazione per sessione, contestuale (hard day → perseveranza, deload → pazienza). Rotazione 30 giorni. |
| — | Report engine | Media | Medium | Settimanale (aderenza, volume, highlight), mensile (trend, distribuzione gradi), annuale (timeline progressione). |

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
  Spec completa in DESIGN_GOAL_MACROCICLO_v1.1.md §9

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
| Adattività avanzata | Readiness score, overreach detection, plateau detection | DESIGN_DOC §13 Fase 1 checkbox vuota |
| Bouldering discipline | Espandere da lead-only a bouldering e mixed | memory progetto |
| Gym preferences | Preferire palestra specifica per giorno (es. "BKL il lunedì") | memory progetto |
| Midjourney imagery | Immagini fotorealistiche climbing per UI (dark background, Midjourney v6) | memory progetto |

---

## §8 — Registro completo B-items e finding

Tabella unica con TUTTI gli item tracciati.

| ID | Titolo | Stato | Fase | Sezione roadmap |
|----|--------|-------|------|-----------------|
| B1 | Standalone core session | TODO (incorporato in B8) | 1.75 | §2.3 |
| B2 | Outdoor sessions / logging | TODO | 2 | §4 |
| B3 | Plan validation vs literature | TODO (→ audit §2.2) | 1.75 | §2.2 |
| B4 | Load score / weekly fatigue | TODO | 1.75 | §2.5 |
| B5 | Replanner phase-aware | ✅ DONE | 1.5 | §1 |
| B6 | PE assessment repeater | ✅ DONE | 1.5 | §1 |
| B7 | Validazioni edge case | ✅ DONE | 1.5 | §1 |
| B8 | Session enrichment + modules | TODO | 1.75 | §2.3 |
| B9 | cable_machine, leg_press | ✅ DONE | 3.1 | §1 |
| B10 | Outdoor climbing spots | TODO | 2 | §4 |
| B11 | Configurable test protocols | TODO | 3.2 | §3 |
| B19 | Quick-add session | TODO | 3.2 | §3 |
| B20 | Edit availability from Settings | TODO | 3.2 | §3 |
| B21 | Done button status | ✅ DONE | 3.1 | §1 |
| B22 | Events endpoint auto-resolve | ✅ DONE | 3.1 | §1 |
| B23 | Skip status update | ✅ DONE | 3.1 | §1 |
| B24 | Gym equipment labels | ✅ DONE | 3.1 | §1 |
| B25 | Adaptive replanning after feedback | TODO | 3.2 | §3 |
| B26 | Test isolation fixtures | ✅ DONE | 3.1 | §1 |
| B27 | Equipment label single source | TODO | 3.2 | §3 |
| NEW-F1 | Prescription climbing vuota | TODO | 1.75 | §2.4 |
| NEW-F2 | Equipment climbing mancante | TODO (P0) | 1.75 | §2.1 |
| NEW-F3 | Test sessions mai pianificate | TODO | 1.75 | §2.4 |
| NEW-F4 | Ripple effect conservativo | TODO | 1.75 | §2.4 |
| NEW-F5 | Durate fase negative | TODO (P0) | 1.75 | §2.1 |
| NEW-F6 | Warning phase_mismatch | TODO | 3.2 | §3 |
| NEW-F7 | Finger compensation | TODO | 3.2 | §3 |
| NEW-F8 | Easy climbing in deload | TODO | 2 | §4 |
| NEW-F9 | Finger maintenance in PE | TODO | 2 | §4 |
| NEW-F10 | Trip start_date HARD | TODO (P0) | 1.75 | §2.1 |
| F6-partial | Intent projecting mancante | TODO | 1.75 | §2.4 |

---

## §9 — Regole di allineamento

1. **Dopo ogni sessione di sviluppo**: aggiornare questo file (stati, nuovi item) E
   aggiornare la sezione Roadmap in PROJECT_BRIEF.md (solo stati fasi ✅/🔲)
2. **Nuovi finding/bug**: aggiungerli in §8 con ID progressivo e nella sezione fase appropriata
3. **BACKLOG.md e NEXT_STEPS.md sono archiviati** in _archive/ — non più aggiornati
4. **audit_post_fix.md e e2e_test_results.md** restano in docs/ come storico test
5. **DESIGN_GOAL_MACROCICLO_v1.1.md** resta il design doc (il "perché") — non contiene stati o planning operativo
6. **Questo file** è il "cosa fare e quando" — la fonte autoritativa per la pianificazione
