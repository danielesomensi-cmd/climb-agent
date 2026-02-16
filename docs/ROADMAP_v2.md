# ROADMAP v2 — climb-agent

> Last updated: 2026-02-16 (post §2.3 B8 session enrichment)
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

| ID | Finding | Descrizione | Fix |
|----|---------|-------------|-----|
| NEW-F3a | Test sessions mai pianificate (scheduling) | test_max_hang_5s esiste ma non è in _SESSION_META né in nessun pool. Nessun scheduling periodico. | Aggiungere a _SESSION_META e pool fine-Base/fine-SP. Scheduling ogni N settimane. |
| NEW-F3b | assessment.tests mai aggiornato dal closed loop | Closed loop aggiorna working_loads ma non assessment.tests dopo sessioni test. | Aggiornare assessment.tests nel closed loop quando sessione è un test. Creare test_power_endurance. |
| NEW-F4 | Ripple effect troppo conservativo | Dopo override hard/max, il replanner controlla solo giorni +2/+3 e solo sessioni già hard. Sessioni medium lasciate invariate. | Forzare giorno successivo a recovery dopo hard/max override |
| F6-partial | Intent "projecting" mancante | 11/12 intent funzionano, ma "projecting" (naturale per climber) non è mappato. Variante indoor possibile: limit bouldering. | Aggiungere intent projecting → limit bouldering indoor |
| NEW-F1 | Prescription climbing vuota | Esercizi climbing hanno solo notes generico. Mancano: grado suggerito, volume, rest. | Aggiungere suggested_grade_offset, volume, rest_between. Resolver calcola grado da current_grade + offset. |

### §2.5 B4 — Load score

Ogni sessione nel planner avrà `estimated_load_score`.
Modello semplice iniziale: low=20, medium=40, high=65, max=85.
Output: weekly summary con total load, hard days count.
Necessario per: overtraining monitoring, adaptive deload input, UI visualization.

### §2.6 Exercise Catalog Audit (Phase 2.5)

Placeholder per audit sistematico del catalogo esercizi:
- Verificare copertura equipment per tutti gli esercizi
- Identificare esercizi mai selezionati dal resolver
- Aggiungere esercizi mancanti per pattern non coperti
- Allineare `resistance_band` vs `band` nel catalogo

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
| B1 | Standalone core session | ✅ DONE | 1.75 | §2.3 |
| B2 | Outdoor sessions / logging | TODO | 2 | §4 |
| B3 | Plan validation vs literature | TODO (→ audit §2.2) | 1.75 | §2.2 |
| B4 | Load score / weekly fatigue | TODO | 1.75 | §2.5 |
| B5 | Replanner phase-aware | ✅ DONE | 1.5 | §1 |
| B6 | PE assessment repeater | ✅ DONE | 1.5 | §1 |
| B7 | Validazioni edge case | ✅ DONE | 1.5 | §1 |
| B8 | Session enrichment + modules | ✅ DONE | 1.75 | §2.3 |
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
| NEW-F2 | Equipment climbing mancante | ✅ DONE | 1.75 | §2.1 |
| NEW-F3a | Test sessions scheduling | TODO | 1.75 | §2.4 |
| NEW-F3b | assessment.tests closed loop | TODO | 2 | §2.4 |
| NEW-F4 | Ripple effect conservativo | TODO | 1.75 | §2.4 |
| NEW-F5 | Durate fase negative | ✅ DONE | 1.75 | §2.1 |
| NEW-F6 | Warning phase_mismatch | TODO | 3.2 | §3 |
| NEW-F7 | Finger compensation | TODO | 3.2 | §3 |
| NEW-F8 | Easy climbing in deload | TODO | 2 | §4 |
| NEW-F9 | Finger maintenance in PE | TODO | 2 | §4 |
| NEW-F10 | Trip start_date HARD | ✅ DONE | 1.75 | §2.1 |
| F6-partial | Intent projecting mancante | TODO | 1.75 | §2.4 |
| B-NEW | Exercise catalog audit | TODO | 2.5 | §2.6 |

---

## §9 — Regole di allineamento

1. **Dopo ogni sessione di sviluppo**: aggiornare questo file (stati, nuovi item) E
   aggiornare la sezione Roadmap in PROJECT_BRIEF.md (solo stati fasi ✅/🔲)
2. **Nuovi finding/bug**: aggiungerli in §8 con ID progressivo e nella sezione fase appropriata
3. **BACKLOG.md e NEXT_STEPS.md sono archiviati** in _archive/ — non più aggiornati
4. **audit_post_fix.md e e2e_test_results.md** restano in docs/ come storico test
5. **DESIGN_GOAL_MACROCICLO_v1.1.md** resta il design doc (il "perché") — non contiene stati o planning operativo
6. **Questo file** è il "cosa fare e quando" — la fonte autoritativa per la pianificazione
