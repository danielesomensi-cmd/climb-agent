> **ARCHIVED — append-only via `trim_roadmap.py`**
> Active roadmap: `docs/ROADMAP_CURRENT.md`

# ROADMAP v2 — climb-agent

> Last updated: 2026-03-06 (B95-B98 fixes; 758 test)
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

### Phase 2.5: Catalog audit ✅
- Audit sistematico catalogo esercizi vs letteratura (Hörst, Lattice, Eva López, Tension)
- 10 patch applicati: main_strength, grade_ref, core, technique, endurance, power_endurance, strength_accessory, endurance_addendum, flexibility, remaining (complementary + conditioning + mobility)
- 135 → 143 esercizi (+8 nuovi, -1 rimosso lattice_lactate_8x8)
- grade_ref + grade_offset su 23/28 esercizi grade_relative (5 campus esclusi by design)
- Vocabulary aggiornato: §2.10.1 grade prescription, pattern locomotion
- Bug fix: 11 prescription_defaults corretti, 1 load_model fix (barbell_row), 2 pattern fix (jump_rope, bear_crawl)
- 377 test verdi
- ARCH-1 — Equipment-based session filtering (replace location hard filter with equipment matching). See `docs/audit_location_equipment.md`

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
| power_endurance_gym | 4 (warmup, pe_main, core_short, cooldown) | 6 (warmup_climbing, pe_routes+pe_boulder, finger_endurance, core_standard, antagonist_prehab, cooldown_stretch) | ✅ |
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
| NEW-F3b | assessment.tests aggiornamento dal closed loop | `_update_test_from_log()` in progression_v1 aggiorna `assessment.tests` per tutti e 6 i test (max_hang, repeater, duration, l_sit, hip_flex, weighted_pullup) + array storici in `tests.*` + baselines. | Verificato 2026-03-05: già implementato. | ✅ DONE |
| NEW-F4 | Ripple effect proporzionale | Dopo override hard/max, il replanner ora applica downgrade proporzionale. | Delta=1: hard→medium (complementary_conditioning), medium→low (regeneration_easy), low→keep. Delta=2: tutto non-low→recovery. Solo direzione upward (più intenso → più leggero il giorno dopo). | ✅ DONE |
| F6-partial | Intent "projecting" mancante | 11/12 intent funzionano, ma "projecting" (naturale per climber) non è mappato. | Aggiunto `"projecting": "power_contact_gym"` in INTENT_TO_SESSION. 13 intent totali. | ✅ DONE |
| NEW-F1 | Prescription climbing vuota | Esercizi climbing hanno solo notes generico. Mancano: grado suggerito, volume, rest. | Moved to Phase 2.5 — see §2.6 | ⏩ Phase 2.5 |

### §2.5 B4 — Load score ✅

Implementato 2026-02-17. Approccio a due livelli:

1. **`estimated_load_score`** (fallback, planner): basato su intensity mapping (low=20, medium=40, high=65, max=85). Presente su ogni sessione nel piano settimanale e nel replanner fill.
2. **`session_load_score`** (primario, resolver): somma di `fatigue_cost` (1-9) di tutti gli esercizi risolti. Presente nell'output di `resolve_session()`.
3. **`weekly_load_summary`**: aggiunto al piano settimanale con `total_load`, `hard_days_count`, `recovery_days_count`. Ricalcolato dopo deload transform.

Necessario per: overtraining monitoring, adaptive deload input, UI visualization.

### §2.6 Exercise Catalog Audit (Phase 2.5) ✅ COMPLETE

Audit sistematico del catalogo esercizi contro la literature review
(`docs/literature_review_climbing_training.md`, 19 sezioni).

**Completato 2026-02-21.** 10 patch applicati in sequenza, 377 test verdi.

| Metrica | Prima | Dopo |
|---------|-------|------|
| Esercizi totali | 135 | 145 |
| Nuovi aggiunti | — | +9 (copenhagen_plank, hangboard_moving_hangs, thirty_thirty_intervals, frenchies, uneven_grip_pullup, one_on_one_off_intervals, aerobic_pyramid_intervals, hip_flexor_couch_stretch, lat_overhead_stretch) + pistol_squat_progression + romanian_deadlift (NEW-F12) |
| Rimossi | — | -1 (lattice_lactate_8x8 — protocollo non standard) |
| Bug fix prescription | — | 11 (work_seconds, sets, rest, load_model, intensity) |
| Enrichment (desc/cues/video) | — | ~80 esercizi aggiornati |
| grade_ref/grade_offset | 0 | 23/28 grade_relative (5 campus esclusi) |
| Vocabulary updates | — | §2.10.1 grade prescription, locomotion pattern |

**Hangboard audit (prima fase):** 5 esercizi aggiunti, fix contraindications su 8 esercizi.

**Remaining items moved to future phases:**
- **B11** (configurable test protocols): → Phase 3.5 or later
- **B29** (dedicated test exercises): → Phase 3.5 or later
- **UI-9** (limitation filtering): → next implementation phase
- **UI-20** (warmup variety): → next implementation phase

### §2.7 Grade resolver ✅ DONE

Implementato in `progression_v1.py:393-405` via `inject_targets()`, chiamato da `resolve_session.py:1098-1116` post-resolution.

- `step_grade()` normalizza gradi Font (strip "+", whole-grade only, scala 5A→8C)
- Legge `grade_ref` + `grade_offset` da prescription_defaults, lookup in `user_state.assessment.grades`
- Output: `suggested_grade`, `grade_ref`, `grade_offset` nel dict `suggested` di ogni exercise instance
- `limit_bouldering` escluso (ha logica dedicata `suggested_boulder_target`)
- 13 test: 5 in `test_working_loads.py`, 4 E2E in `test_feedback_loop_e2e.py`, 4 validazione catalogo in `test_exercises_v2.py`

### §2.8 Working loads (UI-18) ✅ DONE

Implementato in `progression_v1.py:324-442` (`inject_targets()`), closed loop in `progression_v1.py:548-685` (`apply_feedback()`).

**Backend**:
- `inject_targets()` produce `suggested_total_load_kg`, `suggested_external_load_kg`, `suggested_rep_scheme` per load-based, external-load, e hangboard exercises
- Fallback chain: working_loads entry → baselines.hangboard (pre-filled by `estimate_missing_baselines`) → `_FINGER_BENCHMARK` ratio → 1.10×BW se tutto manca
- **NEW-F11** `estimate_missing_baselines(user_state)`: pre-step in `inject_targets()`. Stima `max_total_load_kg` da `lead_max_rp` (tabella grade→offset, es. 7b+20kg) o da `max_weighted_pullup_kg` ((BW+pullup)×0.85). Non sovrascrive mai source="test". Output `suggested` include `load_source="estimated"` (badge grigio frontend) e `load_warning` se external<0 (testo arancione "⚠ Baseline outdated").
- `apply_feedback()` aggiorna `working_loads.entries[]` con adjustment policy (very_easy +15%, easy +7.5%, ok +2.5%, hard -2.5%, very_hard -10%)
- Persistito via `save_state()` in feedback router

**Frontend**:
- Guided session pre-popola load/grade input da `suggested` (exercise-step.tsx:79-92)
- Box "Suggested: +X kg" con icona Lightbulb visibile per esercizi con load
- Feedback con `used_external_load_kg` e `used_grade` inviato al backend

**Test**: 17 in `test_working_loads.py`, E2E loop in `test_feedback_loop_e2e.py` (max_hang 3-session, repeater 2-session, bench_press 3-session), `test_progression_v1.py`

---

> **UI Test (feb 2026)**: 22 findings from manual end-to-end test.
> Batch 1 (4 P0/P1), Batch 1b (2 location fixes), Batch 2 (18 UX items), UI-23 (gym priority).
> All done except: UI-9 (next phase), UI-18 (§2.8), UI-20 (next phase).
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
| B48 | Edit single session (multi-session day) | TODO | Medium | Quando più sessioni nello stesso giorno, "Change plan" tocca solo la sessione selezionata. Le altre sessioni del giorno restano invariate. Dopo la modifica, offrire opzione "Replan rest of week" per ribilanciare il carico. |
| B49 | Reschedule session to different day/slot | ✅ DONE | Medium | MoveSessionDialog: mostra slot liberi nella settimana, muove sessione via `move_session` event. Backend già completo (replanner_v1), UI: MoveSessionDialog + SessionCard Move button + week page integration. |

### §4.2 — Outdoor UI ✅ DONE (verificato 2026-03-05)

Backend outdoor completo (6 endpoint). Frontend completo:
- ✅ OutdoorLogForm.tsx montato in `/today` (dialog) e `/week` (dialog)
- ✅ `/outdoor/page.tsx` — pagina dedicata con stats, sessioni, grade histogram
- ✅ api.ts — 6 funzioni outdoor presenti
- ✅ `convertOutdoorSlot` aggiunto in api.ts (2026-03-05)

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
- ~~Guided timer mode~~ → ✅ DONE in Phase 4b (guided session + GS-01/02/BUG-01/BUG-03)

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
| Session add-on modules (B83) | Moduli opzionali (upper_body_weights, legs, core) aggiungibili a sessioni esistenti. Equipment-aware, load score aggiornato. Giustificazione: lavoro antagonista raccomandato da Hörst/Lattice per bilanciamento muscolare e prevenzione infortuni | B74 brief |

---

## §8 — Registro completo B-items e finding

Tabella unica con TUTTI gli item tracciati.

| ID | Titolo | Stato | Fase | Sezione roadmap |
|----|--------|-------|------|-----------------|
| B1 | Standalone core session | ✅ DONE | 1.75 | §2.3 |
| B2 | Outdoor sessions / logging | ✅ DONE | 2 | §4 |
| B3 | Plan validation vs literature | ✅ DONE (→ audit §2.2 + §2.6) | 1.75 | §2.2 |
| B4 | Load score / weekly fatigue | ✅ DONE | 1.75 | §2.5 |
| B5 | Replanner phase-aware | ✅ DONE | 1.5 | §1 |
| B6 | PE assessment repeater | ✅ DONE | 1.5 | §1 |
| B7 | Validazioni edge case | ✅ DONE | 1.5 | §1 |
| B8 | Session enrichment + modules | ✅ DONE | 1.75 | §2.3 |
| B9 | cable_machine, leg_press | ✅ DONE | 3.1 | §1 |
| B10 | Outdoor climbing spots | ✅ DONE | 2 | §4 |
| B11 | Configurable test protocols | ⏩ future | 3.5+ | §2.6 |
| B19 | Quick-add session | ✅ DONE | 3.2 | §3 |
| B20 | Edit availability from Settings | ✅ DONE | 3.2 | §3 |
| B21 | Done button status | ✅ DONE | 3.1 | §1 |
| B22 | Events endpoint auto-resolve | ✅ DONE | 3.1 | §1 |
| B23 | Skip status update | ✅ DONE | 3.1 | §1 |
| B24 | Gym equipment labels | ✅ DONE | 3.1 | §1 |
| B25 | Adaptive replanning after feedback | ✅ DONE | 3.2 | §3 |
| B26 | Test isolation fixtures | ✅ DONE | 3.1 | §1 |
| B27 | Equipment label single source | ✅ DONE | 3.2 | §3 |
| NEW-F1 | Prescription climbing vuota | ✅ DONE | 4b | §2.7 |
| NEW-F2 | Equipment climbing mancante | ✅ DONE | 1.75 | §2.1 |
| NEW-F3a | Test sessions scheduling | ✅ DONE | 1.75 | §2.4 |
| NEW-F3b | assessment.tests closed loop | ✅ DONE (2026-03-03) — test results (max_hang, repeater, pullup) → assessment.tests + baselines; guided session sends completedSets + planned field; session_id fallback when planned missing; repeater sets-completed UI; 24 tests | 2.5 | §2.4 |
| NEW-F4 | Ripple effect proporzionale | ✅ DONE | 1.75 | §2.4 |
| NEW-F5 | Durate fase negative | ✅ DONE | 1.75 | §2.1 |
| NEW-F6 | Warning phase_mismatch | ✅ DONE | 3.2 | §3 |
| NEW-F7 | Finger compensation | ✅ DONE | 3.2 | §3 |
| NEW-F8 | Easy climbing in deload | ✅ DONE | 2 | §4 |
| NEW-F9 | Finger maintenance in PE | ✅ DONE | 2 | §4 |
| NEW-F10 | Trip start_date HARD | ✅ DONE | 1.75 | §2.1 |
| F6-partial | Intent projecting mancante | ✅ DONE | 1.75 | §2.4 |
| B28 | Cross-session recency nel resolver | ✅ DONE | 2 | §4.1 |
| B29a | Dedicated test exercises in catalog | ⏩ future | 3.5+ | §2.6 |
| B-NEW | Exercise catalog audit | ✅ DONE | 2.5 | §2.6 |
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
| UI-18 | Exercise load/weight prescription display | ✅ DONE | 4b | §2.8 |
| UI-19 | technique_focus_gym resolves wrong | ✅ DONE | Batch 1 | §2 |
| UI-20 | Warmup variety (always shoulder_car). Verified: intra-session dedup already works (L.1070). Cold-start alphabetical fallback is B28 (cross-session). Instruction_only blocks now visible via B93. (2026-03-05) | ✅ DONE | B93 | §2.6 |
| UI-21 | Session structure info (informational) | ℹ️ | — | — |
| UI-22 | Week view: multi-week navigation | ✅ DONE | Batch 2 | §3 |
| FR-1 | Outdoor as availability location option | ✅ DONE | 2 | §4 |
| FR-2 | Warning: no climbing equipment in gyms | ✅ DONE | Batch 2 | §3 |
| FR-3 | Feedback badge/sticker on exercises | ✅ DONE | Batch 2 | §3 |
| UI-23 | Gym slot priority in planner | ✅ DONE | UI-23 | §3 |
| FR-4 | Outdoor vs gym slot priority | TODO | 2 backlog | §9.4 |
| B29b | Undo "done" non funziona | ✅ DONE | post-2 | — |
| B30 | easy_climbing_deload "unknown" nel dialog | ✅ DONE | post-2 | — |
| B31 | Add session "other" mostra solo deload | ✅ DONE | post-2 | — |
| B32 | Feedback done non visibile in UI | ✅ DONE | post-2 | — |
| B33 | Quote motivazionale nella Today view | ✅ DONE | post-2 | — |
| B34 | Feedback badge sessione mancante in Today view | ✅ DONE | 4b | — |
| B35 | Feedback esercizio singolo non visibile (FR-3 incompleto) | ✅ DONE | 4b | — |
| B36 | "— unknown" type label in Add session all-sessions list | ✅ DONE | post-2 | — |
| UI-24 | Feedback con carico/grado — pre-popolare dal suggested | ✅ DONE | 4b | §2.8 |
| B37 | Add exercise to existing session | TODO | next | — |
| B38 | Injuries filter (contraindications) | TODO | next | — |
| B39 | Railway persistent volume. Was marked DONE but volume never configured (status drift). Fixed 2026-03-02: volume mounted at `/data/climb-agent`, `DATA_DIR` env var set, health check confirms `ephemeral_warning: false`. | ✅ DONE | infra | §10 |
| B40 | Branch develop/main workflow | TODO | infra | — |
| B41 | Other activities in availability (block day + optional intensity reduction day after) | ✅ DONE | 4b post | — |
| B42 | Sunday reminder — confirm next week availability | TODO | beta feedback | — |
| B43 | Edit profile + assessment data from Settings | ✅ DONE | 4b post | — |
| B44 | Permettere meno di 3 sessioni/settimana (min 1) | ✅ DONE | 4b post | — |
| B45 | REST phase timer non funziona nel guided session | ✅ DONE | 4b post | — |
| B46 | Density hang load errato senza baseline (usava BW anziché grade-stima) | ✅ DONE | 4b post | — |
| B47 | Guided session: nessun banner al resume + set number perso su refresh | ✅ DONE | 4b post | — |
| NEW-F11 | estimate_missing_baselines(): stima max_total da grade/pullup quando nessun baseline reale | ✅ DONE | 4b post | §2.8 |
| B48 | Edit single session senza toccare l'intero giorno (multi-session day) | TODO | next | §4 |
| B49 | Reschedule session to different day/slot (move session UI) | ✅ DONE | 4b post | §4 |
| NEW-F12 | Leg exercises catalog (pistol_squat_progression, romanian_deadlift, lower_body_gym, heavy_conditioning_gym) | ✅ DONE | 4b post | §2.6 |
| CAT-01 | Lead climbing catalog fixes: strength_long domain filter, pe_gym equipment filter split, resolver equipment support | ✅ DONE | 4b post | §2.3 |
| CAT-02 | New session route_endurance_gym (lead aerobic base, threshold + ARC) + pool registration (base, PE) | ✅ DONE | 4b post | §2.3 |
| GS-01 | Set navigation arrows durante rest phase nel guided session timer | ✅ DONE | 4b post | §10 |
| GS-02 | Fix audio su iPhone PWA (Safari AudioContext singleton + unlock trick) | ✅ DONE | 4b post | §10 |
| GS-BUG-01 | Timer non si resetta al cambio esercizio (mancava key prop per remount) | ✅ DONE | 4b post | §10 |
| GS-BUG-03 | Frecce navigazione timer phase-based (sempre visibili, 48px tap target) | ✅ DONE | 4b post | §10 |
| UI-25 | Pannello Test Maxes & Loads nel tab Plan (history, benchmark, exercise loads) | TODO | next | §9.5 |
| UI-26 | Fix overflow testo selettore fasi macrociclo (Plan tab). Rimosso `truncate` da timeline labels, ridotto font a `text-[10px]` su mobile, `break-words` per labels sotto la barra. Soglia visibilità ridotta da 10% a 8%. (2026-03-05) | ✅ DONE | next | §9.5 |
| UI-27 | Tooltip indicatori numerici Week view. Aggiunto `title` con "N sessions · status" su dot+count nella griglia settimanale + `sr-only` label per accessibilità. (2026-03-05) | ✅ DONE | next | §9.5 |
| UI-28 | Dirty-state banner + incremental macrocycle regen + Danger Zone full restart | ✅ DONE | 4b post | §9.5 |
| B50 | ProfileEditor/GoalEditor pre-populate with current values | ✅ DONE | 4b post | §10 |
| B51 | Session display names in quick-add dialog (human-readable names) | ✅ DONE | 4b post | §10 |
| B52 | Equipment compatibility filter in quick-add (hide incompatible sessions) | ✅ DONE | 4b post | §10 |
| B53 | Actual load display in week header (Done: X alongside planned Load) | ✅ DONE | 4b post | §10 |
| B54 | Heavy Conditioning Gym: add push/triceps/core blocks + audit report | ✅ DONE | 4b post | §2.3 |
| NEW-F13 | Complementary sport completion with feedback-based load (easy=10, ok=20, hard=30) | ✅ DONE | 4b post | §10 |
| B55 | Catalog audit fixes: names, cooldown gaps, core, antagonist, pulling_strength_gym | ✅ DONE | 4b post | §10 |
| B56 | Heavy Conditioning Gym: aggiunto dumbbell_bench_press, bicep_curl, lateral_raise (145→148 esercizi) + blocchi arm_curl/shoulder_isolation in heavy_conditioning_gym. Pattern: elbow_flexion, shoulder_isolation. (2026-02-28) | ✅ DONE | catalog | §2.3 |
| B57 | Active Finger Curls: rinominato "Rep rest" → "Hold between reps" in prescription e "Hold" nel timer ring. Note esercizio aggiornate con dettaglio ciclo rep. (2026-02-28) | ✅ DONE | catalog+UI | §7 |
| B58 | Test Sessions (hangboard) e sessioni climbing appaiono in Work gym — filtro equipment non funziona correttamente. Fix: aggiunto `required_equipment` a 3 test session JSON (hangboard per max_hang/repeater, pullup_bar per weighted_pullup). | ✅ DONE | engine | §4 |
| B59 | "Get Ready" countdown tra le serie: rimosso. Get Ready solo all'inizio (set 1). Tra le serie: set_rest → work direttamente. Back da work set > 1 torna a set_rest. | ✅ DONE | UI | §7 |
| B60 | Bug: suoni sessione non funzionavano (Web Audio API, iOS). Fix: `handleStart`/`handleDoneSet` async con `await unlockAudio()`, `beep()` tenta `ctx.resume()` prima di arrendersi, visibility change re-play silent buffer. | ✅ DONE | UI | §7 |
| B61 | Voice cues durante sessione guidata — Web Speech API: "Go" (work), "Rest" (set_rest), "Hold" (rep_rest), "Done" (complete), "Get ready". Toggle in Settings, default ON. (2026-03-02) | ✅ DONE | UI | §7 |
| B65 | Feature: Weekly Report (LLM-ready) — fase 1 DONE (2026-03-02): report engine riscritto con 9 sezioni strutturate (context, adherence, load, difficulty, stimulus_balance, progression, outdoor, days, highlights). Fix multi-user bug in reports router (_log_dir user-scoped). Frontend: /reports/weekly page (mobile-first, adherence ring, load bar, difficulty distribution, highlights, day timeline, progression table, outdoor summary, stimulus balance grid). "Weekly Report" button in week view. 56 test dedicati. Fase 2 (narrative LLM) in Phase 3.5. | ✅ DONE (fase 1) | engine+UI | §7 |
| B67 | Timer guided session si ferma in background iOS (setInterval sospeso). Fix: wall-clock based timer (phaseEndTimeRef = Date.now() + duration, ogni tick calcola remaining = endTime - now). visibilitychange handler per recalc immediato al foreground. Pause + background → resta in pausa. | ✅ DONE | UI | §7 |
| C-1 | Week view missing Done/Skip/Undo/Remove + FeedbackDialog. Added all session action callbacks to DayCard in week/page.tsx. | ✅ DONE | UI | §8 |
| C-2 | Day view missing Quick-add dialog. Added QuickAddDialog integration to today/page.tsx. | ✅ DONE | UI | §8 |
| C-3 | Day view missing Replan + Move dialogs. Added ReplanDialog + MoveSessionDialog to today/page.tsx. | ✅ DONE | UI | §8 |
| C-4 | Daily gym/location change: new `change_gym` event in replanner with equipment-aware fallback (complementary_conditioning → regeneration_easy + finger compensation). GymPickerDialog in both views. 5 new tests. | ✅ DONE | engine+UI | §8 |
| OD-1 | Outdoor session flow (Model B): add_outdoor/complete_outdoor/undo_outdoor/remove_outdoor events, QuickAddDialog outdoor mode with spot picker + inline creation, DayCard outdoor card with log/undo/remove, OutdoorLogForm wired in Today+Week views. Fix multi-user JSONL. 8 new tests. | ✅ DONE | engine+UI | §8 |
| B68 | Outdoor load score: `compute_outdoor_load_score()` in outdoor_log.py — grade_weight × style_modifier × duration_factor. Integrated into report_engine `_build_load()` (outdoor_load field) and API endpoints (load_score per session, total_load/avg in stats). 11 new tests. (2026-03-03) | ✅ DONE | engine | §4 |
| B69 | Outdoor done in adherence: `_build_adherence()` counts outdoor planned/completed per day (outdoor_spot_name or outdoor_slot). 3 new tests. (2026-03-03) | ✅ DONE | engine | §4 |
| B70 | Ripple effect post-outdoor: when outdoor load ≥ 65 (OUTDOOR_RIPPLE_THRESHOLD), apply 1-day ripple (hard→complementary, medium→recovery). API router computes load from JSONL. 5 new tests. (2026-03-03) | ✅ DONE | engine | §4 |
| B71 | ~~Fix JSONL outdoor non segregato per utente~~ — FIXED in OD-1 (user-scoped log directory). | ✅ DONE | engine | §4 |
| B72 | Outdoor history/stats UI: new `/outdoor` page with stats cards, per-spot breakdown, session list with load scores, grade histogram. Links from Settings and weekly report. (2026-03-03) | ✅ DONE | UI | §4 |
| B73 | Outdoor spots in onboarding: Locations step now has outdoor spots card (add/remove, name + discipline). Persisted via `_build_user_state_from_onboarding()` with auto-generated IDs. 2 new tests. (2026-03-03) | ✅ DONE | UI | §4 |
| B74 | Outdoor route summary in DayCard: expand/collapse route list when done (grade + name + style badge + ×N attempts + max grade). Style picker in OutdoorLogForm (onsight/flash/redpoint/project). Today+Week auto-fetch outdoor sessions. | ✅ DONE | UI | §4 |
| **B75** | **Data persistence — fix intermedi completati.** (a) admin recovery endpoint ✅ B75a, (b) export/import ✅ B75b, (c) backup periodico volume → low-priority (volume Railway attivo B78). Persistent volume funzionante, export/import disponibile, admin recovery attivo. Fix definitivo: auth reale (Clerk, Phase 4c). (2026-03-02) | ✅ DONE (interim) | infra | §4a |
| B75a | Admin recovery endpoint: `GET /api/admin/users` protetto da `X-Admin-Key` (ADMIN_SECRET env var). Per ogni utente: uuid, last_access, grade, sessions_completed, onboarding_date. Fallback chain per last_access (feedback_log → macrocycle → assessment → file mtime) e grade (goal → assessment.grades). 11 nuovi test. (2026-03-02) | ✅ DONE | API | §4a |
| B75b | Export/import user_state: `GET /api/user/export` (Content-Disposition attachment) + `POST /api/user/import` (schema validation + append-only event log). Sezione "Backup & Restore" in Settings con toast feedback. 9 nuovi test. (2026-03-02) | ✅ DONE | API+UI | §4a |
| B76 | Outdoor + other_activity day-level fields persi dopo rigenerazione week plan. `regenerate_preserving_completed()` e `merge_prev_week_sessions()` copiavano solo sessions[], ignorando outdoor_spot_name/status/discipline e other_activity_status/feedback/load. Fix: `_DAY_LEVEL_FIELDS` tuple + restore loop in entrambe le funzioni. 6 nuovi test. (2026-03-02) | ✅ DONE | engine | §4 |
| B77 | POST /api/outdoor/log: OSError/IOError non catturati — propagavano come 500 generico senza messaggio utile. Fix: catch OSError con messaggio esplicito (path + errore) + post-write verification che il JSONL esista su disco. E2E test cross-week: add_outdoor → log → complete → regen → verify merge + JSONL persistenza. 3 nuovi test (533 totali). (2026-03-02) | ✅ DONE | engine+test | §4 |
| B78 | Railway persistent volume non era configurato (B39 status drift). Fix: volume montato a `/data/climb-agent` da dashboard Railway, `DATA_DIR` env var settata. Health check all'avvio (`_check_data_dir()` in main.py) + `/health` endpoint arricchito con `data_dir`, `data_dir_from_env`, `ephemeral_warning`. Verificato in produzione: `ephemeral_warning: false`. (2026-03-02) | ✅ DONE | infra | §10 |
| B79 | Start-from-week-N in onboarding: dopo generazione macrocycle, nuova pagina chiede "Have you already been training?" e permette di iniziare da week 2/3/4. `POST /api/onboarding/start-week` shifta `macrocycle.start_date` indietro di N settimane (clamped a first_phase_duration-1). Nuova pagina `/onboarding/start-week` con radio group + Skip/Continue. Review page ora redirecta a start-week. Step indicator mostra 100% su start-week. 4 nuovi test (557 totali). (2026-03-02) | ✅ DONE | API+UI | §4b |
| B80 | Per-week cache: navigare tra settimane diverse perdeva sessioni completate e modifiche manuali. Causa: replanner endpoints sovrascrivevano `current_week_plan` con qualsiasi settimana modificata → cache miss al ritorno sulla settimana corrente → rigenerazione fresca. Fix: `week_plans` dict (keyed by `start_date`) in user_state per persistere modifiche a TUTTE le settimane. `_persist_week_plan()` helper salva in `week_plans` + condizionalmente in `current_week_plan`. Week router legge da `week_plans[start_date]` con fallback a legacy `current_week_plan`. Feedback adaptive replan sincronizzato. 5 nuovi test (562 totali). (2026-03-02) | ✅ DONE | API | §4b |
| B81 | Outdoor undo duplica vie: `undo_outdoor` cambiava solo `outdoor_session_status` nel piano ma non toccava il JSONL log. Re-loggando le stesse vie venivano appese di nuovo → duplicati. Fix: `remove_outdoor_session(log_dir, date)` in `outdoor_log.py` riscrive il JSONL escludendo entries per la data. L'endpoint `/api/replanner/events` chiama `remove_outdoor_session()` per ogni evento `undo_outdoor`. 4 nuovi test (566 totali). (2026-03-02) | ✅ DONE | engine+API | §4b |
| B82 | Recovery code system per UUID loss. UUID in localStorage → perso se si pulisce Safari/cambia device → stato Railway irrecuperabile. Fix: `POST /api/user/recovery-code` (idempotente, genera CLIMB-XXXX-XXXX); `POST /api/user/recover` (pubblico, restituisce UUID da codice). Storage: `{DATA_DIR}/recovery_codes.json`. Frontend: modal bloccante in `/onboarding/start-week` con skip secondario + warning; nuova pagina `/onboarding/recover`; link "Already have an account?" su welcome; sezione Account in Settings con copy code + inline recover. 698 test verdi. (2026-03-04) | ✅ DONE | API+UI | §8 |
| B83 | Session add-on mini-sessions via quick-add (Pattern B). 3 nuove sessioni: `upper_body_weights` (push antagonist, 30min), `legs_strength` (unilateral legs, 30min), `core_training` (climbing-specific core, 25min). Tutte bodyweight, home+gym, finger=false, hard=false. 2 nuovi esercizi: `goblet_squat`, `glute_bridge` (153 totali). `suggest_sessions` ora include sempre le complementary add-on indipendentemente dalla fase (`_ALWAYS_SUGGESTIBLE`). 7 nuovi test (713 totali). (2026-03-04) | ✅ DONE | catalog+engine | §7 |
| B84 | Gym selection bugs — Bug A + Bug B. **Bug A**: `_location_has_equipment` si fermava alla prima gym; se gym1 (priority 1) mancava equipment, la sessione veniva skippata anche se gym2 aveva l'equipment. Fix: iterazione di tutte le gym per priority; `_select_gym_id` sceglie la prima gym con equipment compatibile. **Bug B**: quando il pool climbing ha solo sessioni gym_routes ma la gym del giorno manca di gym_routes, Pass 1 lasciava il giorno vuoto. Fix: Pass 1.5 inietta fallback climbing (technique_focus_gym o easy_climbing_deload, entrambi gym_boulder) solo quando il pool non ha gym_boulder climbing AND la gym del giorno non può fare routes. 5 nuovi test (698 totali). (2026-03-04) | ✅ DONE | engine | §4 |
| B85 | ~~Manca sessione boulder endurance per base phase.~~ **RESOLVED BY B86** — `boulder_circuit_gym` (medium, gym_boulder) creata e aggiunta al pool base. (2026-03-04) | ✅ DONE | — | §4 |
| B86 | Base phase intensity cap + pool audit + expansion. **Fix**: `PHASE_INTENSITY_CAP["base"]` da `"high"` a `"medium"`. **Audit completo** di tutti i pool: rimossi 4 sessioni dal pool base (finger_strength_home high, strength_long max, power_endurance_gym high, pulling_strength_gym high) + handstand_practice dal pool deload (medium > cap low). **Nuova sessione**: `boulder_circuit_gym` (medium, gym_boulder, circuit bouldering -3/-4 grade). **Pool base risultante**: technique_focus_gym + endurance_aerobic_gym + route_endurance_gym + boulder_circuit_gym (climbing) + finger_maintenance_home + prehab/flex/handstand/conditioning (complementary). **Guard test** parametrizzato su tutte le fasi. 5 nuovi test (706 totali). (2026-03-04) | ✅ DONE | engine+catalog | §4 |
| B87 | Gym name fallback in equipment lookup. Gyms in `user_state.equipment.gyms` non hanno campo `gym_id` (solo `name`). L'availability editor salva `g.name` come `gym_id` negli slot. `_equipment_for_location` cercava gym per `g.get("gym_id") == slot_gym_id` → always None → fallback alla prima gym per priority (sbagliata). Con 2+ gym, i slot che referenziano Cocuqe per nome ricevevano invece l'equipment della gym con priority 1 → sessioni routes fallite su equipment check → nessuna sessione climbing piazzata. Fix: aggiunta `or g.get("name") == gym_id` nel loop in `_equipment_for_location` (line 103) e nella `day_gym_can_do_routes` check in Pass 1.5. Fix anche `_select_gym_id` per restituire `g.get("gym_id") or g.get("name")`. 3 nuovi test (701 totali). (2026-03-04) | ✅ DONE | engine | §4 |
| B88 | Stable gym_id at onboarding. UUID hex[:8] generato al momento della creazione gym (onboarding + equipment editor + settings). Migration on-read per utenti esistenti (`_migrate_gym_ids` in deps.py). Rimossi fallback `g.get("name")` da planner_v2 e replanner_v1. Frontend: tutti i Gym interface aggiornati con `gym_id?`, availability/gym-picker usano `gym_id` come valore. session-card risolve gym_id → nome per display. (2026-03-05) | ✅ DONE | engine+api+frontend | §4 |
| B89 | Weekly report narrative LLM (Phase 3.5). Fase 2 del weekly report (B65). Sostituire le rule-based insights con narrative generata da LLM coach. Dipende da Phase 3.5 (LLM coach layer). | ⏩ deferred | feature/llm | §9 |
| B90 | Cross-exercise load transfer + coherence check. `_SIMILARITY_GROUPS` definisce gruppi con coefficienti (push: bench_press↔dumbbell_bench_press 0.85×, squat: split_squat↔goblet_squat 0.80×). `_transfer_load()` in progression_v1: quando `_best_entry()` non trova match diretto, cerca nel gruppo similarità e applica coefficiente. `check_load_coherence()` segnala outlier (ratio >2× o <0.5× rispetto ad atteso). Aggiunto `dumbbell_bench_press` e `goblet_squat` a EXTERNAL_LOAD_EXERCISES. 10 nuovi test (736 totali). (2026-03-05) | ✅ DONE | engine | §2.8 |
| B98 | Recompute day status after `regenerate_preserving_completed`. Merged sessions from old plan could leave stale day-level `status` field. Fix: call `_recompute_day_status()` after merge loop. (2026-03-06) | ✅ DONE | engine | §4 |
| B97 | Outdoor override in replan dialog. New intents `outdoor_projecting`, `outdoor_boulder`, `outdoor_volume` in replan dialog. `apply_day_override` detects outdoor intents → sets outdoor fields (`outdoor_session_status`, `outdoor_discipline`) and clears indoor sessions. No ripple effect for outdoor. Frontend: 3 new intent options in ReplanDialog. 4 new tests. (2026-03-06) | ✅ DONE | engine+UI | §4 |
| B96 | Equipment-aware override. `apply_day_override` now accepts `gyms` param and checks required_equipment against gym equipment before placing a session. If mismatch, falls back to equipment-compatible alternative via `_resolve_intent_with_equipment()`. Prevents placing sessions requiring gym_routes at boulder-only gyms. 3 new tests. (2026-03-06) | ✅ DONE | engine | §4 |
| B95 | Other sport per-slot. `other_activity` bloccava l'intero giorno in availability: nessuna sessione climbing generata. Fix: (1) planner tratta `other_activity` come intensity-reduced (no hard) ma genera comunque sessioni; (2) availability UI ora ha opzione "Other" per-slot (Home/Gym/Other) invece di toggle a livello giorno — blocca solo lo slot scelto; (3) quick-add dialog aggiunge opzione "Other sport / activity" con scelta slot+nome; (4) backend: nuovi eventi `add_other_activity`/`remove_other_activity` in replanner, slot-aware. 4 nuovi test (748 totali). (2026-03-06) | ✅ DONE | engine+UI | §4 |
| B94 | Equipment mismatch pool cycling fix. Pass 1/2 pool cycling decremented `primary_uses`/`comp_uses` on equipment/location mismatch, exhausting the pool before reaching days with compatible gyms. Fix: equipment mismatch skips only advance index+attempts, not uses. Real scenario: 4 gyms (boulder-only, weights-only, routes-only, full) → climbing now placed on all equipment-compatible days. 3 new tests (744 totali). (2026-03-05) | ✅ DONE | engine | §3 |
| B93 | Warmup completo — instruction_only blocks visibili + exercise variety. **Bug 1**: blocchi instruction_only (pulse_raise, mobility) ora visibili sia nella session card (card informativa con durata + note) sia nel guided mode (step con Done button, no feedback/RPE). `buildGuidedState()` ricostruito per interleave blocchi istruzione + esercizi in ordine corretto. **Bug 2**: intra-session dedup verificato funzionante (L.1070 in resolve_session.py — `recent_ex_ids.append()` già previene duplicati tra warmup e prehab blocks). Cross-session variety rimane B28. 5 nuovi test (741 totali). (2026-03-05) | ✅ DONE | frontend+test | §4 |
| B92 | Video URL audit. Nulled 33 `video_url` entries from 10 non-trusted domains (latticetraining, climbing.com, gmb.io, strengthclimbing, cameronhorst, rehabhero, gripped, 99boulders, inspirerock, theprehabguys). Kept only youtube.com, hoopersbeta.com, trainingforclimbing.com. 96 URLs remaining. (2026-03-05) | ✅ DONE | catalog | §2.6 |
| B91 | Boulder macrocycle (`goal_type: boulder_grade`). `generate_macrocycle()` detects `discipline="boulder"` from goal and applies boulder-specific parameters: shorter base (2w), longer strength_power (4-5w), 1w PE, boulder session pools (no route sessions), `_BASE_WEIGHTS_BOULDER` with finger_strength 0.40 in SP phase. Flex phase = strength_power (not base). `_build_session_pool()` accepts `discipline` param. `_compute_phase_durations()` accepts `discipline` param with boulder floor=1w per phase. Frontend already supported discipline selection in onboarding goals page. 12 new tests (726 totali). (2026-03-05) | ✅ DONE | engine | §8 |

---

## §9 — Future features (from UI testing insights, feb 2026)

### 9.1 — Testing week in onboarding ✅ DONE (2026-03-02)
After onboarding review step, two options:
- "Start training now" — generates macrocycle immediately with available data
- "Do a test week first" — generates a special 1-week assessment plan

`generate_test_week()` in planner_v2.py places 3 test sessions on non-consecutive days (48h finger gap):
- Day 1: test_max_hang_5s (finger strength)
- Day 2: test_max_weighted_pullup (pulling strength)
- Day 3: test_repeater_7_3 (power endurance, 48h gap from max_hang)
- Remaining days: prehab/flexibility fillers

API: POST /api/onboarding/test-week, POST /api/onboarding/test-week-complete
Week endpoint returns test_week when test_week_mode=True.
Periodic test reminder: `should_show_test_reminder()` fires at weeks 5, 11, 17... with postpone/skip.
POST /api/week/test-reminder-response handles confirm/postpone/skip.
Frontend: review page fork, today page banner + completion trigger, api client functions.
8 new backend tests (test_test_week.py).

### 9.2 — Expanded onboarding test battery ✅ DONE (2026-03-02)
Expanded from 3 to 6 evidence-based tests (all optional):
1. Max hang 20mm/5s (existing) — finger_strength axis
2. Repeater 7/3 (existing) — power_endurance axis
3. Weighted pull-up 1RM (existing) — pulling_strength axis
4. **Max hang duration 20mm** (NEW) — endurance axis (±8 max; Hörst test #3)
5. **L-sit hold** (NEW) — body_composition axis (±5; 9c test tier 2)
6. **Hip flexibility straddle** (NEW) — informational only v1 (Lattice, r=.53-.95)

Assessment engine: `_compute_endurance()` and `_compute_body_composition()` accept optional `tests` param.
Frontend: tests page has 6 sections + info banner, review page shows X/6.
6 new backend tests in test_assessment_v1.py.

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

### 9.5 — Plan & Week UI improvements (2026-02-25)

#### UI-25 — Pannello Test Maxes & Loads (Plan tab)

Card collassabile sotto "Assessment profile" nel tab Plan. Tre blocchi:

**Blocco 1 — Test Maxes History:**
- Timeline compatta per esercizio test, tutte le entry con data e valore in ordine cronologico
- Entry attiva evidenziata visivamente
- Entry di tipo `manual_correction` mostrano icona diversa da `test_session`
- Possibilità di aggiungere `manual_correction` con nota obbligatoria (es. "errore inserimento", "test autonomo")
- Nessun nuovo file: tutto da `user_state.json` (assessment.tests + working_loads.entries)
- Principio 3 rispettato (append-only)

**Blocco 2 — Benchmark Comparison (dipende da Phase 2.5):**
- Per massimali con benchmark documentati (Lattice/Hörst), indicatore "sopra/sotto benchmark" relativo al bodyweight
- Solo finger strength e pulling strength in v1

**Blocco 3 — Exercise Loads (collassato di default):**
- Lista esercizi con `load_model: total_load | external_load`
- Per ognuno: ultimo carico usato + stringa derivazione (es. "19.8kg — da 1RM 22kg, feedback easy")
- Sola lettura, aggiornato dall'engine

#### UI-26 — Fix overflow testo selettore fasi macrociclo (Plan tab)

Il testo nel selettore orizzontale delle fasi viene troncato in modo errato producendo stringhe illeggibili (es. "Endurance Base rength & Power Endurerformanc"). Gestire overflow correttamente: truncate con ellipsis oppure abbreviazioni predefinite per nome fase.

#### UI-27 — Chiarire indicatori numerici giorni (Week tab)

I pallini con numero (1, 2…) sui giorni nella Week view non sono autoesplicativi. Aggiungere label o tooltip che chiariscano il significato (sessioni pianificate? completate? totali?).

#### UI-28 — Dirty-state banner + incremental macrocycle regen + Danger Zone ✅ DONE

Implementato 2026-02-25 in due commit. 472 test verdi (25 nuovi).

**Backend:**
- `state_checks.py`: `is_macrocycle_stale(state)` confronta `assessment.profile` vs `macrocycle.assessment_snapshot` (threshold 5 punti per asse)
- `GET /api/state/status` endpoint (28 endpoint totali)
- `generate_macrocycle(from_phase=)`: incremental regen che preserva le fasi precedenti. Router risolve `"current"` → phase_id concreto via `current_phase_and_week()`
- `_compute_remaining_durations()`: alloca settimane rimanenti tra fasi residue con floor enforcement e compression

**Frontend:**
- Rimosso "Regenerate Assessment" da Settings (auto-triggered da ProfileEditor e GoalEditor)
- Rimossa intera sezione "Actions" da Settings
- Plan tab: dirty-state banner giallo ("Your profile has changed") con "Regenerate plan" / "Dismiss" + bottone "Regenerate Macrocycle" sotto timeline → entrambi usano regen incrementale (`from_phase: "current"`)
- Dialog aggiornato: "regenera dalla fase corrente in poi, le fasi precedenti restano intatte"
- Settings > Danger Zone: nuova card "Restart Macrocycle" con doppia conferma → full regen da week 1 (senza `from_phase`)

---

## §10 — Deployment & Distribution

### Phase 4a — ✅ LIVE (2026-02-22)

- **Frontend**: https://climb-agent.vercel.app ✅ (Vercel, auto-deploy da main, root dir: `frontend/`)
- **Backend**: https://web-production-fb1e9.up.railway.app ✅ (Railway, auto-deploy da main, `Procfile` + `requirements.txt`, `$PORT=8080`)
  - Migrato da vecchio progetto `climb-agent-production` il 2026-03-06: 15 utenti migrati (0 fallimenti), 3 già presenti skippati, 21 utenti totali. Vecchio progetto eliminato.
- **Multi-user**: UUID v4 generato dal frontend al primo accesso, salvato in `localStorage`, inviato come header `X-User-ID` su ogni chiamata API
- **Per-user state**: `backend/data/users/{user_id}/user_state.json` (copia da template al primo accesso)
- **CORS**: `http://localhost:3000` + `https://climb-agent.vercel.app`
- **No auth, no database, no pagamenti** in questa fase

### Phase 4b — Guided Session + Beta prep ✅ (2026-02-23)

- **Guided Session Mode**: `/guided/[date]/[sessionId]`
  localStorage persistence, step-by-step navigation,
  progress dots, session timer, feedback inline per esercizio,
  carico/grado editabile, summary screen,
  retry automatico feedback fallito
- **B34/B35 fix**: feedback badge Today view + feedback esercizio singolo
- **Catalog fixes**: load_model 6 esercizi (campus → bodyweight_only, 30/30 → grade_relative),
  grade_ref aerobic_pyramid → lead_max_os, homewall aggiunto come equipment home
- **UX**: hint "Start session", intro onboarding, video link + cues in guided session,
  session_duration_seconds nel feedback payload
- **Tab "What's next"**: roadmap votabile (7 feature), feedback form → daniele.somensi@gmail.com
- **Settings**: Edit Equipment (con regenerate dialog), Edit Goal (two-step confirmation + rigenera macrociclo)
- 421 test verdi

**Bug fix post-4b (2026-02-24):**
- **B45 REST timer**: `session-card.tsx` leggeva `prescription.rest_s` (campo inesistente) anziché `rest_between_sets_seconds` → `restSeconds` sempre `undefined` → fase REST mai avviata nel timer. Fix: fallback `rest_between_sets_seconds ?? rest_s`.
- **B46 Density hang load**: `_hangboard_suggested()` usava `bodyweight` come `max_total_load` in assenza di baseline, assumendo 1.0×BW max hang per qualsiasi climber (errato). Fix: stima da grade attuale via `_FINGER_BENCHMARK` (es. 7b+ → 1.20×BW). Intensity `density_hangs` corretta 65% → 75% per allineamento a Tyler Nelson (~75% MVC).
- **B47 Guided session persistence**: aggiunto banner "Session resumed" (auto-dismiss 4s) quando lo stato ripristinato da localStorage ha progresso reale. Aggiunto `completedSets` su `GuidedExercise` + prop `initialSet`/`onSetChange` su `ExerciseTimer` → il set number sopravvive al refresh.
- **NEW-F11 estimate_missing_baselines**: pre-step in `inject_targets()` che stima `max_total_load_kg` da `lead_max_rp` (tabella grade→offset) o `max_weighted_pullup_kg` ((BW+pullup)×0.85) quando nessun baseline reale è presente. Non sovrascrive mai source="test". Frontend: badge "(estimated)" grigio + warning arancione se external<0. 5 nuovi test → 426 totali.
- **B43 Edit profile/assessment**: ProfileAssessmentEditor in Settings — modifica profilo, gradi, test senza reset completo. Ricalcola assessment.
- **B44 Min sessioni/settimana**: slider availability abbassato da min=3 a min=1 (onboarding + settings).
- **B41 Other activities**: planner_v2 parse `_day_meta` da availability, blocca giorni con other_activity, riduce intensità giorno dopo (opzionale). UI controls in settings + onboarding. 3 nuovi test → 440 totali.
- **CAT-01 Lead fixes**: strength_long `climbing_movement` domain filter allargato a `technique_lead`/`climbing_routes`. power_endurance_gym: split pe_climbing_main in `pe_routes` (equipment: gym_routes, priorità 90) + `pe_boulder` (fallback, priorità 85). resolve_session: aggiunto `required_equipment` param a `pick_best_exercise_p0()` + Stage 2b soft equipment filter.
- **CAT-02 route_endurance_gym**: nuova sessione lead aerobic base (threshold su routes + ARC su boulder/board). Registrata in `_SESSION_META` (medium, climbing, gym) e `_SESSION_POOL` (base + power_endurance come "available").
- **B49 Move session UI**: MoveSessionDialog mostra slot liberi nella settimana, SessionCard "Move" button, week page integration via `applyEvents()` con evento `move_session`. 7 nuovi test → 447 totali.

**Guided Session fixes (2026-02-25):**
- **GS-01 Set navigation arrows**: durante fase `set_rest`, frecce ‹ › per sfogliare set completati/futuri senza alterare il timer. Click freccia auto-pausa; resume torna al set reale. Indicatore ✓ per set completati.
- **GS-02 iOS audio fix**: AudioContext estratto in singleton condiviso (`audio-unlock.ts`) con silent buffer unlock trick per Safari/PWA. Listener `touchstart` + `visibilitychange` per mantenere audio attivo tra background/foreground.
- **GS-BUG-01 Timer reset on exercise change**: aggiunto `key` prop su `GuidedExerciseStep` per forzare remount al cambio esercizio → timer si resetta correttamente.
- **GS-BUG-03 Phase-based arrow navigation**: frecce timer sempre visibili quando attivo (48px tap target). Forward salta alla fase successiva, back ricomincia fase (se >2s) o torna alla fase precedente. Reset button ingrandito con bordo e label.
- **Test cwd-independence**: 5 test resi indipendenti dalla working directory (path assoluti in test_p1_75_closing, test_planner_v1, test_schema_validation).

**UI-28 Dirty-state + incremental regen (2026-02-25):**
- **Dirty-state detection**: `state_checks.py` con `is_macrocycle_stale()` (threshold 5 punti/asse). `GET /api/state/status` endpoint. 12 test.
- **Actions reorganization**: rimosso "Regenerate Assessment" (auto-triggered), rimossa sezione Actions da Settings, spostato "Regenerate Macrocycle" in Plan tab con dirty-state banner.
- **Incremental macrocycle regen**: `generate_macrocycle(from_phase=)` preserva fasi precedenti, rigenera da `from_phase` in poi con profilo aggiornato. `_compute_remaining_durations()` per allocazione settimane. Router risolve `"current"` → phase_id concreto. 13 test.
- **Danger Zone full restart**: nuova card "Restart Macrocycle" in Settings con doppia conferma → full regen senza `from_phase`.
- 472 test verdi totali.

**Settings editor fix (2026-02-25):**
- **B50 Pre-populate editors**: ProfileEditor e GoalEditor si aprivano con campi vuoti (placeholder) invece dei valori correnti. Causa: `useState` catturava valori iniziali vuoti perché i componenti erano montati prima del caricamento dello state. Fix: aggiunto `useEffect` che sincronizza lo state del form dai props ad ogni apertura del dialog.

**Session UX fixes + complementary sport (2026-02-26):**
- **B51 Session display names**: Quick-add dialog mostrava ID interni (blocx_power_bouldering, gym_aerobic_endurance…) invece di nomi leggibili. Fix: aggiunto campo `name` a 12 session JSON, enriched `/suggest-sessions` API con `session_name`, frontend usa nome se presente.
- **B52 Equipment compatibility filter**: Quick-add suggeriva sessioni incompatibili con l'attrezzatura della palestra selezionata. Fix: aggiunto `required_equipment` a 18 session JSON, esposto in `/catalog/sessions` e `/suggest-sessions`, frontend filtra suggerimenti e lista "all sessions" contro equipment palestra.
- **B53 Actual load in week header**: Week view mostrava solo load pianificato. Fix: aggiunto calcolo client-side "Done: X" sommando `estimated_load_score` delle sessioni completate + `other_activity_load`.
- **B54 Heavy Conditioning Gym incompleta**: Sessione aveva solo compound pull e carry, mancavano push/triceps/core. Fix: `compound_push` reso required, aggiunti blocchi `triceps_dip` (dip 3×10) e `core_compression` (hanging_leg_raise 3×10), `core_standard` template reso required.
- **B54b Session catalog audit**: Analisi testuale di tutti i 36 file sessione. Identificati 14 file con gap, 5 pattern ricorrenti (nomi mancanti, equipment mancanti, blocchi troppo pochi).
- **Complementary sport completion**: Nuovo evento `complete_other_activity` con feedback (easy/ok/hard) → load 10/20/30 punti. Evento `undo_other_activity` per annullare. UI: badge completamento, feedback picker inline, undo button. DayCard integrata in Today + Week view. 6 nuovi test → 497 totali.
- **B55 Catalog audit fixes** (post-audit):
  - GAP-0: Rimosso "Blocx" dai nomi sessioni → "(Climbing Gym)"
  - GAP-1: Aggiunto cooldown_stretch a 8 sessioni gym/blocx mancanti
  - GAP-2: Aggiunto core_short + cooldown_stretch a finger_strength_home e finger_maintenance_home
  - GAP-3: antagonist_prehab alzato a priority 65, required in strength_long e power_contact_gym
  - GAP-4: Verificata struttura warmup+main+cooldown su tutte le sessioni v1
  - GAP-5: Nuova sessione pulling_strength_gym (template pulling_strength_compound con weighted_pullup 4×4, lock_off_isometric 3×3, typewriter_pullup 3×5 + antagonist_prehab + cooldown_stretch)
  - GAP-5b: Aggiunto cooldown_stretch + antagonist_prehab a strength_pull_short e strength_push_short
  - Nuovo template: pulling_strength_compound (3 blocchi explicit exercise_id)
  - 5 nuovi test per pulling_strength_gym → 502 totali

**Base phase session distribution audit (2026-02-27):**
- **B58 equipment filter**: Aggiunto `required_equipment` a 3 test session JSON (hangboard, pullup_bar)
- **B60 audio async**: handleStart/handleDoneSet async con await unlockAudio(), beep() con ctx.resume(), visibility change silent buffer replay
- **Step 1 — Intensity cap**: finger_strength_home intensity "max"→"high" in `_SESSION_META`, PHASE_INTENSITY_CAP["base"] "medium"→"high" in macrocycle_v1. Pool primario base da 4 a 6 sessioni.
- **Step 2 — Anti-repetition**: Aggiunto `max_per_week` field in `_SESSION_META` (default 1, endurance_aerobic_gym=2). Tracking `session_count` dict in pass 1 e pass 2 di planner_v2. 3 nuovi test (TestPlannerV2AntiRepetition).
- **Step 3 — Pool expansion**: Aggiunto `pulling_strength_gym: "available"` a `_SESSION_POOL["base"]`. Pool base: 7 primary + 5 complementary = 12 sessioni.
- **Step 4 — Orphan cleanup**: 13 sessioni archiviate in `_archive/` (4 blocx_*, 4 gym_*, 3 strength_short, core_conditioning_standalone, strength_long_with_core_required). 5 sessioni registrate in META (heavy_conditioning_gym, lower_body_gym, finger_aerobic_base, deload_recovery, finger_endurance_short). Creato finger_maintenance_gym.json (era in META ma mancava il file). Aggiornato planner_v1 legacy (session IDs rinominati). 25 sessioni attive = 25 entry META, 0% orphan rate.
- **Step 5 — Location/Equipment audit**: Analisi delle 25 sessioni per location/equipment pattern. Nessuna modifica (solo analisi).
- **Step 6 — Validazione finale**: 509 test verdi. Generazione settimana per tutte le 5 fasi con 0 violazioni anti-repetition. Letteratura base: ARC ≤3x ✓, Finger ≥1x ✓, Technique ≥1x ✓, Core/Antagonist integrato ✓.
- 509 test verdi totali.

### Phase 4c — Produzione

- **Auth**: Clerk (Next.js native)
- **DB**: Supabase Postgres
- **Pagamenti**: Stripe (subscription)

### Phase 4d — App store (futuro)

- **Capacitor**: wrappa la PWA esistente per iOS/Android
- Zero riscrittura del codice

---

## §11 — Beta feedback log

| ID | Tester | Data | Descrizione | Status | B-item |
|----|--------|------|-------------|--------|--------|
| FB-1 | Alexis | 2026-02-23 | Bloccare giorni per altri sport con riduzione intensità opzionale giorno dopo | ✅ DONE | B41 |
| FB-2 | Alexis | 2026-02-23 | Sessione su giorno non selezionato — comportamento corretto, non bug | CHIUSO | — |
| FB-3 | Alexis | 2026-02-23 | Reminder domenicale per confermare disponibilità settimana successiva | TODO | B42 |
| FB-4 | Davide Vato | 2026-02-23 | Re-enter assessment data senza reset completo (età, peso, grado massimo) | ✅ DONE | B43 |
| FB-5 | Luca | 2026-02-23 | Impossibile selezionare meno di 3 allenamenti/settimana — scala 1 volta a settimana | ✅ DONE | B44 |

---

## §11b — Closed items archived from ROADMAP_CURRENT (D156, 2026-03-25)

### P1 — Stability and bug fixes (all completed)

- **B159** (2026-03-25) — Boulder surface equivalence + weight expansion. Any gym with spraywall, board_kilter, board_moonboard, or board_other now implies `gym_boulder`. Same logic for weight: dumbbell/kettlebell/barbell implies `weight`. Unified `expand_equipment()` in `equipment_utils.py`. 14 new tests (1391 total).
- **B158** (2026-03-25) — Planner Pass 1 uses budget fix. Temporary day-specific skips no longer burn `primary_uses` budget. `permanent_skip` flag. 4 new tests (1381 total).
- **D154 Phase 1** (2026-03-25) — Fix S&P climbing distribution. `finger_strength_home` metadata corrected. New `limit_boulder_gym` session. 13 new tests (1376 total, 34 sessions).
- **B157** (2026-03-25) — Three bugs from live session: campus_bumps prescription, R/L weight input guard for bodyweight_only, guided session completion for future-week sessions.
- **B156** (2026-03-25) — Session UX Fixes (6 items): test_measurement persistence, countup stopwatch, warmup_easy_boulders, campus_bumps rewrite, active_hip_mobility, per-exercise notes. 7 new tests (1363 total).
- **B155e** (2026-03-25) — Removed exercise drag & drop reorder entirely. −1 endpoint (50 total), −3 npm deps, −8 reorder tests.
- **B155** (2026-03-25) — Clerk auth race condition fix. Gate all page-level fetches on `useAuth().isLoaded`. One-time 401 retry safety net.
- **B153d** (2026-03-25) — Exercise reorder 422 fix. Frontend uses response data directly instead of GET reload.
- **A141** (2026-03-24) — Process cues, phase rationales, fall drill, nav restructure. 14 new tests (1335 total).
- **A142** (2026-03-24) — Exercise Detail Preview Sheet (ExerciseDetailSheet). 1 new component (58 total).
- **B-SUPP** (2026-03-23) — Supplementary training via quick-add. `supplementary: true` flag on 5 sessions. 7 new tests (1321 total).
- **A140** (2026-03-23) — Core Circuit add-on. New activity type in Free Session with configurable timer. 30 core exercises. 9 new backend tests.
- **D151** (2026-03-23) — Load coherence audit & fix. 5 incoherences fixed. 20 new tests (1307 total).
- **D152** (2026-03-24) — Add Exercise UX audit. 3 new tests (1338 total).
- **B151** (2026-03-22) — Settings page: 4 bugs fixed. 2 new tests (1287 total).
- **D150** (2026-03-22) — Planner availability compliance audit & fix. 14 new tests (1250 total).
- **D35** (2026-03-22) — Hangboard experience gates. 7 new tests.
- **D64** (2026-03-22) — RED-S guardrails. 3 new tests.
- **B137b** (2026-03-22) — Resolver homewall equipment equivalence. 5 new tests.
- **B139** (2026-03-22) — Week navigation picker.
- **B137** (2026-03-21) — Homewall users get climbing sessions at home. 3 new tests (1223 total).
- **B138** (2026-03-21) — Test interval 14→42 days.
- **B136 + B136b** (2026-03-21) — Test results not visible in Today/Week view.
- **B135** (2026-03-21) — Settings not showing max hang baseline.
- **A139** (2026-03-21) — Session review: show actual logged data for completed sessions. 6 new tests (1220 total).
- **B139** (2026-03-21) — Root URL 404 + OG meta tags.
- **B153c** (2026-03-24) — Exercise reorder persistence audit. 1 new test (1356 total).
- **B153b** (2026-03-24) — Drag reorder not persisting. `_user_edited` flag. 3 new tests (1355 total).
- **B153** (2026-03-24) — Reorder exercises drag UX.
- **A153** (2026-03-24) — Remove + Reorder exercises in resolved sessions. 14 new tests.
- **A138** (2026-03-20) — Free session integration.
- **D134** (2026-03-20) — Outdoor session persistence audit & fix. 8 new tests (1205 total).
- **A137** (2026-03-20) — Free climbing session frontend.
- **A136** (2026-03-20) — Free climbing session backend. 72 new tests.
- **A135** (2026-03-20) — Tabata timer tab.
- **B133 + B133-fix + B134** (2026-03-19) — Repeater test protocol fix (Lattice 2025).
- **Session 1** (2026-03-17) — Assessment & Onboarding mega brief decisions (D01, D38, D68, D80, D81, D83).
- **Session 1b** (2026-03-18) — Test protocol revision (D84-D91).
- **B131** (2026-03-17) — LP test session UX fixes.
- **A121** (2026-03-18) — Phase-aware intra-session exercise ordering. 41 new tests.
- **D126/B126** (2026-03-15) — Resolver Stage 2c bug fix.
- **B127** (2026-03-15) — Assessment profile auto-refresh.
- **B126** (2026-03-15) — Weekly report audit: 5 bugs fixed.
- **B127 duration** (2026-03-15) — 3-level duration capture.

### P1b — Beta feedback (all completed)

- **B128** — Test interval updated by B138 (14→42 days).

### P2.5 — Catalog audit (closed items)

- **B129** (2026-03-19) — `threshold_climbing` domain fix (aerobic_capacity → power_endurance).
- **B-SUPP** (2026-03-23) — Supplementary training via quick-add.

---

## §12 — Regole di allineamento

1. **Dopo ogni sessione di sviluppo**: aggiornare questo file (stati, nuovi item) E
   aggiornare la sezione Roadmap in PROJECT_BRIEF.md (solo stati fasi ✅/🔲)
2. **Nuovi finding/bug**: aggiungerli in §8 con ID progressivo e nella sezione fase appropriata
3. **BACKLOG.md e NEXT_STEPS.md sono archiviati** in _archive/ — non più aggiornati
4. **audit_post_fix.md e e2e_test_results.md** restano in docs/ come storico test
5. **DESIGN_GOAL_MACROCICLO_v1.1.md** resta il design doc (il "perché") — non contiene stati o planning operativo
6. **Questo file** è il "cosa fare e quando" — la fonte autoritativa per la pianificazione

### Archived from ROADMAP_CURRENT.md — 2026-04-10

| 1: Assessment & Onboarding | ✅ Done | D01, D38, D68, D80, D81, D83 | — |
| 1b: Test Protocol Revision | ✅ Done | D84, D84b, D85, D86, D88, D90 | D87b, D89, D91 |
| 2: Exercise DB — Strength | ✅ Closed | D11, D12, D39 | D10, D50, D72 |
| 3: Exercise DB — Conditioning | ✅ Closed | D43, D55*, D56, D57, D60, D76 | D37 |
| 4: Warm-Up | ✅ Closed | (warmup via template) | D33, D36, D74 |
| 5: Intensity System (EL) | ✅ Closed | — (entire session deferred) | D34, D52, D14 |
| 6: Hangboard Logic | ✅ Closed | D35 | D49 |
| 7: Endurance & Intervals | ✅ Closed | D48 (A141) | D47, D53 |
| 8: Conditioning & Ratio | ✅ Closed | D54, D58*, D78 (A141) | D51, D59, D73 |
| 9: Periodization & Load | ✅ Closed | D21, D44* | D19, D20, D45, D69, D70, D71 |
| 10: Coaching & UX | ✅ Closed | D17, D30, D64, D75* (A141) | D29, D41, D65, D66, D67, D77, D79 |
- ✅ **B157** — Orphan exercise leak: `critical_force_test` removed from catalog (deferred to v2/D89), role filter added to `easy_climbing_post_finger` block, 4 catalog validation tests added (2026-03-26)
- ✅ **B158** — Change Plan + Quick-Add dialog Confirm button hidden on Android: split DialogContent into scrollable body + sticky footer, added `viewport-fit: cover` + `safe-area-inset-bottom` padding, switched to `75dvh` (2026-03-26)
- ✅ **D158** — `finger_strength_home` template selecting Grip Transitions instead of MaxHangs: resolver now reads `pattern` from template blocks, `grip_transitions` role→activation + pattern→grip_transition, `finger_max_strength` main block filters by `isometric_hang` (2026-03-26)
- ✅ **B159** — What's Next page: renamed to "Roadmap & Support", flagged Add Exercise + Injury Tracking as implemented, added "Coming soon" badge to Kilter integration (2026-03-26)
- ✅ **B159a** — Campus gate + selection quality: added `experience_minimum_years`, `age_minimum: 16`, `difficulty_tier`, and `contraindications` to all 10 campus exercises. Added generic `experience_minimum_years` gate (Stage 2f) in resolver. Beginners now get tier-appropriate exercises (2026-03-26)
- ✅ **B159b** — Exercise rotation: `load_recent_exercise_ids()` now reads from `week_plans` (status=done, lookback 3 weeks). Added `recency_group` penalty (-15) in `score_exercise`. All templates now produce 3/3 unique weeks instead of 1/3 (2026-03-26)
- ✅ **B160** — Circuit timer: off-by-one fix (exercise mismatch REST→WORK), added "Rest" voice cue, 3-2-1 beep edge case (skip if phase ≤ 3s), image-first layout redesign with always-visible controls (2026-03-26)
- ✅ **B160b** — Circuit timer hotfix: full description (line-clamp-4), arrows advance one phase at a time (work→rest→work), STOP+EXIT buttons visible, compact bottom bar layout (2026-03-26)
- ✅ **B160c** — Circuit timer layout: timer ring + controls side-by-side (no more hidden buttons), ring 144px, image max-h-140, full description no truncation, EXIT in header (2026-03-26)
- ✅ **B160g** — Template gap fix: added `core_standard` and/or `antagonist_prehab` modules to 7 gym session definitions (boulder_circuit, route_endurance, limit_boulder, pulling_strength, finger_maintenance, heavy_conditioning, easy_climbing_deload). All gym sessions now resolve with complete tail blocks. Updated duration estimates. Zero engine code changes (2026-03-27)
- ✅ **B167** — Sync safety net: `sync_status.py` now aborts with warning if non-sync files are uncommitted (SYNC_FILES whitelist = PROJECT_BRIEF.md + README.md). CLAUDE.md rule added: commit before sync. (2026-03-29)
- ✅ **B164-trimmed** — Frontend P2 fixes: rest timer placeholder removed, very_easy/easy feedback badge distinction, outdoor spot delete confirmation dialog, import data confirmation dialog (2026-03-30)
- ✅ **B168** — Fix boulder onboarding flow: boulder-to-lead grade mapping for assessment benchmarks (P0 fix), discipline step before grades, conditional grade fields per discipline, Font/V toggle in grades page, weakness labels in review page (2026-03-30)
- ✅ **B169** — Radar label truncation fix (boulder labels shortened), boulder base phase floor raised to min 2 weeks. Planner diagnostic: 2/3 hard sessions is correct (finger spacing blocks Tue/Thu), not a bug. (2026-03-30)
- ✅ **B168c** — Onboarding copy polish: discipline page "What do you want to improve?" + goal-focused descriptions, review page hides empty grade fields for boulder-only users (2026-03-30)
- ✅ **B165b-fix** — `_recovery_multiplier_for_age()` thresholds corrected: 1.0× under 50 (was 40), 1.25× at 50-59, 1.5× at 60+. Removed 1.75× tier. Replanner spacing now uses `_recovery_gap()` from plan snapshot. (2026-03-30)
- ✅ **A-B4b** — Radar chart axis tooltips: (i) icon on each legend axis, tap shows discipline-aware description + "low score means" popover. (2026-03-30)
- ✅ **B170** — Undo button UX clarity: label now context-dependent ("Undo completion" / "Undo skip"). Remove session dialog improved. (2026-03-30)
- ✅ **B172** — Post-deploy verification: altSides badge visible in idle; unilateral/altSides separated in GuidedExercise (test form no longer triggers on prehab exercises in test sessions); cooldown_forearm_wrist_stretch sets 2→4; cooldown_shoulder_chest work_seconds 20→30; cooldown_hip_pigeon work_seconds 30→60. (2026-03-31)
- ✅ **B172b** — Catalog hotfix: `active_hip_mobility` alt_sides removed (non-bilateral exercise); `archer_pullup` corrected unilateral→alt_sides. (2026-03-31)
- ✅ **B173** — Systematic gym_id + silent fallback remediation (D170 audit). Frontend: `replan-dialog`, `gym-picker-dialog`, `quick-add-dialog`, `availability` always send gym_id UUID (not name). Backend: `logger.warning` on gym_id miss in resolver, replanner (change_gym, apply_day_override, suggest_sessions), `logger.warning` on hangboard baseline mismatch in progression_v1, `logger.error` on session resolution failure in routers. 9 new caplog tests. (2026-03-31)
- ✅ **B171** — ExerciseTimer fixes from D169 audit: F1 `emom_bouldering` work_seconds 30→60 (full EMOM interval); F2 `one_on_one_off_intervals` rest moved to set_rest; F3a 29 exercises marked `alt_sides=true` (catalog field, separate from loading-pin `unilateral`); F3b ExerciseTimer `unilateral` prop — RIGHT/LEFT badge, doubled internal sets, displaySet/totalSets logic. (2026-03-30)
- ✅ **A180** — Outdoor routes list: aggregate climbs by route name + spot across sessions. Shows total attempts, session count, best style badge (onsight/flash/sent/projecting), sent checkmark, grade. Collapsible card, sorted by most recent. Frontend-only, zero backend changes. (2026-03-31)
- ✅ **B183** — Lower body session quality + alt_sides audit + duration estimate: (1) `lower_body_gym` enriched with 2 new required blocks (`accessory_lunge`, `accessory_calf`); `reverse_lunge` added to catalog; session now resolves 4 leg exercises; time_budget updated 50→60 min. (2) Full alt_sides audit: 6 exercises fixed (`split_squat`, `pistol_squat_progression`, `campus_bumps`, `side_plank`, `one_arm_hang_assisted`, `single_leg_calf_raise`); `lunge`/`calf_raise` added to vocabulary. (3) `hip_flexor_strengthening` cues rewritten for clarity. (4) Duration estimate: `target_duration_min` exposed from resolver output; `~XX min` badge shown on planned session cards. (2026-04-02)
- ✅ **B184** — Session quality sweep (B183 follow-up): (1) `turkish_getup`/`farmers_carry` equipment fixed (`equipment_required: []` + `equipment_required_any` with canonical tokens). (2) `legs_strength` v1.1: replaced broken warmup with `general_warmup` template, split squat/hinge blocks, added lunge + calf blocks, time_budget 30→45. (3) `upper_body_weights` v1.1: added `general_warmup` template, `antagonist_prehab` → module_role "activation", time_budget 30→40. (4) `flexibility_full` v1.1: added 4 stretch blocks (`stretch_lower_passive`, `stretch_lower_active`, `stretch_thoracic`, `stretch_hip_flexor`, `stretch_full_body`) — session now resolves 5-6 exercises instead of 2. time_budget 35→40. (5) `handstand_practice` v1.1: added `general_warmup` template, second handstand drill block, time_budget 25→30. (6) `complementary_conditioning` v1.1: added `conditioning_secondary` block (carry/locomotion). (7) 4 stale time_budget values fixed: `lower_body_gym` 60→75, `heavy_conditioning_gym` 70→80, `core_training` 25→40, `prehab_maintenance` 18→20. (2026-04-02)
- ✅ **B185** — Template filter audit + 5 KB-validated bug fixes: Phase 1 audited all 27 templates + 35 session inline blocks. Phase 2 fixed 5 real bugs: (1) `pulling_strength.pull_compound`: added `pattern: ["pull_vertical","pull_horizontal"]` — excluded `dip` (push) from compound pull block. (2) `gym_power_bouldering.main`: added `pattern: ["climbing_limit_boulder","campus_ladder"]` — excluded `power_pullups_explosive` from limit bouldering block. (3) `gym_aerobic_endurance.main`: added `pattern: ["climbing_continuous"]` — excluded interval exercises and hangboard from ARC block. (4) `handstand_shoulder_taps`: removed `"core"` from domain (skill exercise, not anti-gravity core) — no longer selectable in core blocks. (5) `finger_extensor_prehab` inline block in `finger_strength_home` + `finger_maintenance_home`: added `pattern: ["wrist_extension"]` — excluded `wrist_curl` (flexor) from extensor prehab block. All 35 sessions resolve successfully, 1572 tests pass. (2026-04-02)
- ✅ **B185b** — Post-fix: `power_pullups_explosive` domain changed from `["power"]` to `["strength_general"]`. Root cause: soft pattern filter dropped when `gym_boulder` unavailable → exercise selected in `limit_projecting`/`limit_bouldering` blocks. Fix moves it to `supplementary_pulling` (correct block). 1572 tests pass. (2026-04-02)
- ✅ **B186** — Pulling rotation fix + 3 contact strength exercises + archive dead templates: (1) `pulling_strength_compound` v1.0→v1.1: 3 hardcoded blocks converted to P0 `strength_general + pull_vertical` — 9 candidates in `pullup_variants` recency_group ensure unique triplette each session. (2) 3 new contact_strength exercises: `overcoming_isometric_pull` + `rfd_explosive_pulls` (hangboard) + `power_slap_drill` (gym_boulder) as campus board fallbacks. (3) `campus_power` block: pattern widened + `equipment: ["campus_board"]` soft preference — `dip` bug eliminated, hangboard/boulder fallbacks confirmed. (4) 8 dead templates archived to `_archive/`. (5) 2 P3 roadmap items added. 189 exercises, 19 templates, 1571 tests pass. (2026-04-02)
### Recovered briefs (D188 audit, 2026-04-06)

The following briefs were shipped but never tracked in ROADMAP_CURRENT or ROADMAP_v2 — recovered from git log during D188 reconciliation. Listed in chronological order, each with the original commit hash. All are ✅ Done.

- ✅ **B161** — Cross-week `hard_gap` and `finger_gap` enforcement. Planner now respects recovery gaps across week boundaries, not just within a single week. 3 files. (`4001708`, 2026-03-25)
- ✅ **D161** — Audit snapshot script + workflow doc + production user state reader. Foundation for repeatable audit workflow. 4 files, +526 lines. (`566acda`, 2026-03-26)
- ✅ **B162** — Route projecting session + phase pool rebalance for lead climbers. New session type + macrocycle pool adjustments. 11 files, +143 lines. (`f1482b2`, 2026-03-27)
- ✅ **A165** — Exercise phase coloring + session context card. 5 files, +190 lines. Note: partially reverted the same day by B165 (`aa7c34f`) which kept phase coloring and removed the context card — both entries preserved for history. (`255678c`, 2026-03-28)
- ✅ **B164** — Replace stale `total_load` with frozen `planned_load`. Load accounting uses plan snapshot values instead of live catalog, preventing drift after catalog edits. 11 files, +190 lines. Distinct from `B164-trimmed` (frontend P2 fixes) already tracked above. (`35260d6`, 2026-03-28)
- ✅ **B165** (parent) — Clerk user lookup docs in CLAUDE.md + exercise phase coloring revert + week progress bar (removed A165 context card). Parent brief that spawned sub-items B165a-e already tracked. (`bf0eb74` + `aa7c34f`, 2026-03-28)
- ✅ **D162** — `docs/lessons.md` system + `/audit-module` + `/sync-check` slash commands. Introduced the structured lessons-learned workflow. 3 files. (`9c7d7b6`, 2026-03-28)
- ✅ **B166** — Remove redundant "View day" button from Week day cards + add model switching convention to CLAUDE.md. (`a36f56b` + `da945a8`, 2026-03-29)
- ✅ **C170** — Exercise catalog fixes: 3 critical corrections, 9 `unilateral` flag additions, clarity rewrites for confusion-pair exercises. 1 file, +75 / −51. (`594b59a`, 2026-03-30)
- ✅ **C169** — Tyler Twist exercise cues and description improvements. 1 file. (`75975f6`, 2026-03-31)
- ✅ **D175** — Meta: add D170/D172 audit findings to roadmap (Priority 1.26 section). Self-referential closure. (`04752c7`, 2026-03-31)
- ✅ **B177** — 📝 Logged (known issue, not fixed): intermittent guided session scroll+timer bug. Reproduction conditions unclear — tracking only. (`bc23627`, 2026-03-31)
- ✅ **B178** — `alt_sides` catalog updates, set counter clamp fix, FAB "start session" button on day cards. 6 files, +52. (`3ba8acf`, 2026-03-31)
- ✅ **B180** — Tyler Twist equipment: `weight` OR `resistance_band` (was `weight` only, blocked home users). 1 file. (`5827b6d`, 2026-03-31)
- ✅ **A181** — Strategic Advisory Council: 5 parallel subagents + `/council` + `/council-launch` slash commands + `admin_dashboard.py` CLI for user overview. 10 files, +833 lines. (`cf82562` + `697b7d5`, 2026-04-01)
- ✅ **B181** — Resume in-progress session from Today page after iOS background kill. 3 files, +150. (`6593b53`, 2026-04-01)
- ✅ **B182** — `/brief` command diagnosis + roadmap alignment fix + rename "Log extra session" → "Log Free Session". 6 files. (`e4472b1` + `d82179f`, 2026-04-01)
- ✅ **D186** — Document Supabase RLS enablement on all 6 tables (CLAUDE.md deployment section). 2 files. (`ce6bd15`, 2026-04-03)

> **Note on B179**: no dedicated brief — the commit `c42e302` was a 1-line append to `lessons.md` from another session's debugging work. Not tracked as a brief. Reserved as used to prevent renumber collision.

---

### P1 findings — ✅ All closed (B165a-e, 2026-03-29 to 2026-03-31)

All 16 P1 findings from D163 + D164 audits verified fixed in code. See remediation briefs below for details.

**Remaining (moved to post-launch):**
- F3-P1-009 — Replanner hardcodes finger/hard spacing to 1-day gaps, ignoring `recovery_multiplier` for 50+ users (replanner_v1.py). Age threshold shifted to 50 in B165b. Remaining: replanner hardcoded spacing — impacts only users ≥50. Post-launch.

### Remediation briefs

| Brief | Scope | Effort | Status |
|-------|-------|--------|--------|
| B165a | Quick P1 wins — profanity, Suspense, vocabulary sync, equipment editor 0-locations guard, histogram NaN, RP≥OS validation, onboarding timeout, trip dates, availability 0-gyms guard, limitations empty array, guided double-tap, recovery code tests, finger_warmup_generic description | S | ✅ Done (2026-03-29) |
| B165b | Replanner recovery_multiplier fix + age threshold shift to 50 (high-risk: replanner_v1.py, STOP gate required) | M | ✅ Done (2026-03-30) |
| B165c | Frontend error handling sweep — replace ~20 `.catch(() => {})` with error states/toasts (subsumes R141) | M | ✅ Done (2026-03-31) |
| B165d | Security hardening — atomic file writes, rate limiting, `secrets` for recovery codes, error response sanitization, `PUT /api/state` key whitelist | M | ✅ Done (2026-03-31) |
| B165e | Catalog cleanup — `easy_climbing_deload` + `deload_recovery` schema normalization, video_url + contraindication tests, placeholder URLs→null, `finger_warmup_generic` description/cues, `age_under_16`→`age_minimum:16` on 10 campus exercises | S | ✅ Done (2026-03-31) |

### Completed

| ID | Title | Date |
|----|-------|------|
| B169 (quick-add) | Quick-add location mismatch — frontend sent `gym.name` instead of `gym_id` UUID | 2026-03-31 |
| D170 | Silent fallback audit — 5 agents, 24 findings (gym_id propagation) | 2026-03-31 |
| B173 | Systematic gym_id + silent fallback remediation (D170 findings) — 13 findings fixed, +9 tests | 2026-03-31 |
| D172 | Field propagation audit — 6 agents, 25 findings (session_id, template_id, equipment, slot, phase, API validation) | 2026-03-31 |

### Ready to implement (P1 — pre-launch blockers)

| ID | Title | Type | Effort | Notes |
|----|-------|------|--------|-------|
| **B174** | `_resolve_inline_block` ignores explicit `exercise_id` → wrong exercises in sessions with inline blocks (D172-01) | B | S | ✅ Done (implemented, tracking missed) |
| **B175** | Input validation hardening: 500→422 on bad dict keys (D172-02), `ensure_monday` crash (D172-03), stale session guard (D172-04), boulder `domain_weights` in `set_availability` (D172-06) | B | M | ✅ Done (implemented, tracking missed) |

| **TD-HORST-1** | ✅ Done (B200, 2026-04-09) — Non-bug. Two-tier design verified: `assessment.tests` = latest scalars for profile compute; top-level `tests` = append-only history log with metadata (date, freshness_policy, confidence). Complementary, not redundant. Docstring added to `_update_test_from_log` to prevent re-investigation. |
| **TD-HORST-2** | ✅ Done (B199, 2026-04-08) — `max_hang_7s: 0.88` removed from `HANGBOARD_DEFAULT_INTENSITY_PCT`. Dead code: `_hangboard_suggested` explicitly excludes `max_hang_7s` in call path. |
| **TD-HORST-3** | ✅ Done (B199, 2026-04-08) — `max_hang_10s: 0.85` removed from `HANGBOARD_DEFAULT_INTENSITY_PCT`; `active: false` set in exercises.json. No session catalog file exists; constant was unreachable. |
| `free-session/page.tsx` sends `gym_name` not `gym_id` (D170 P2-04) | P3 | S | ✅ Done (B201, 2026-04-09) — added `gym_id` to `FreeSessionStartRequest`, validated server-side (422 if not in user gyms), denormalized canonical name. `gym_name` reserved for free-text custom gym. Frontend updated, gym_id wins when both sent. |
### A-B1 — Discipline selection in onboarding

**Priority:** P1.5 | **Status:** ✅ Done | **Type:** A (feature) | **Effort:** M

Discipline selector (Lead/Boulder/Both) in onboarding goals page. `boulder_grade` activates `_SESSION_POOL_BOULDER` + `_BASE_DURATIONS_BOULDER` (10-week cycle). `all_round` uses lead durations + merged lead/boulder session pool. Frontend: conditional target_style (hidden for boulder), dual grade pickers for Both, discipline-filtered weakness options. Settings page shows discipline + boulder target. Backward-compatible: missing `discipline` defaults to lead. 22 new tests. (2026-03-29)

**Depends on:** ~~A-B2~~ ✅, ~~A-B3~~ ✅

### A-B2 — Grade display preference (Font / V-scale)

**Priority:** P1.5 | **Status:** ✅ Done | **Type:** A (feature) | **Effort:** S

New user preference `grade_system_boulder: "font" | "v_scale"` (default: font). Engine internals unchanged (always Fontainebleau). Frontend utility `displayBoulderGrade(fontGrade, pref)` converts at render time. Settings toggle added. Applied to: GradePicker, ClimbLogger, SessionSummary, outdoor page, free-session presets. 14 unit tests. (2026-03-29)

### A-B3 — Self-eval weakness options per discipline

**Priority:** P1.5 | **Status:** ✅ Done | **Type:** A (feature) | **Effort:** S

4 boulder-specific weakness values added (poor_body_tension, poor_dynamic_movement, weak_on_slopers, poor_problem_reading) with axis mappings in assessment_v1.py. Onboarding defaults API returns grouped weakness options by discipline scope. Frontend weakness page filters by selected discipline. Vocabulary updated. 18 new tests. (2026-03-29)

### A-B4 — Assessment radar discipline-aware labels

**Priority:** P1.5 | **Status:** ✅ Done | **Type:** A (frontend) | **Effort:** XS

Same 5 axes, different display labels per discipline. RadarChart now accepts `discipline` prop, labels switch between lead/boulder/all_round. `getDiscipline()` infers from goal_type. 5 unit tests. (2026-03-29)

---

| GTM-01 | **Onboarding dry-run** — Daniele completes full flow as unknown user (clean account, no founder help). Document every friction point. | D | S | ✅ Done | Completed 2026-04-01. 13 pages reviewed. 0 blockers, 3 P2, 5 P3. |
| GTM-02 | **Fix onboarding blockers** — 9 quick fixes from dry-run (copy, CSS, info boxes) | B | S | ✅ Done | Welcome copy, discipline subtitle, goals helpers + weeks display, weakness padding, test labels, limitations copy, availability info box, trips skip. (2026-04-01) |
| A-GTM-08 | **PWA Install Guide in onboarding** — new step 2 (after welcome, before profile) with iPhone/Android tabs teaching home screen install | A | S | ✅ Done | Two-tab layout, 3 numbered steps per platform, custom iOS share icon SVG. 34 pages total. (2026-04-04) |
| B187 | **English strings + gym UX guards** — replace 11 hardcoded Italian strings, disable Gym button when no gyms, add amber banner, "All" quick-fill button, fix Next validation | B | S | ✅ Done | Triggered by beta tester Tabitha stuck on availability page. (2026-04-05) |
| B188 | **Bypass subscribe page** — route onboarding start-week to `/plan` instead of `/subscribe` while Stripe disabled | B | XS | ✅ Done | Beta testers hit 503 on subscribe page. TODO marker for GTM-04 re-enable. (2026-04-05) |
| B189 | **Outdoor route dots = per-attempt sent/fell** — replace single style-colored dot + ×N with individual green (sent/topped_out) / red (fell) circular dots, one per attempt, in expanded outdoor route view (day-card) | B | S | ✅ Done | Removed unused `STYLE_BADGE` constant. 1571 tests pass. (2026-04-06) |
| B193 | **Guided submit cache refetch + post_feedback timing logs** — guided session submit was leaving /today on stale "Planned" badge (`invalidateQueries` was fire-and-forget with no active observers); replaced with `await refetchQueries(week(weekNum))` so /today renders fresh on first paint. Also added per-step `time.perf_counter` logs in `post_feedback` to locate the ~20s bottleneck observed in production (load_state, apply_feedback, apply_day_result, append_feedback_log, persist_actual, adaptive_replan, save_state). | B | S | ✅ Done | Bug 2 (cache) fixed. Timing logs revealed backend is 3.1s (load_state 1.3s + save_state 1.7s) — the 20s user-perceived latency was from 5 sequential round-trips in guided submit, not backend. Closed by A194 which collapses to 1 round-trip and removes B193 instrumentation. (2026-04-07) |
| B196 | **Service Worker versioning + update banner + branch workflow** — `frontend/public/sw.js` had a hardcoded `CACHE_NAME = "climb-agent-v2"` that never changed across deploys, so PWA users on iPhone kept serving stale JS bundles after every push (root cause of "exercise-timer doesn't start" report). Renamed to `sw.template.js` with `__BUILD_ID__` placeholder; new `frontend/scripts/build-sw.js` runs as `prebuild`, injecting `VERCEL_GIT_COMMIT_SHA` (or local git rev) so every deploy ships a unique sw.js → browser triggers `install` → `activate` purges every cache that doesn't match current build. Added `<SwUpdateBanner />` (mounted in `app/layout.tsx`) that detects `installing → installed` with an existing controller, prompts the user to reload, and posts `SKIP_WAITING` to the waiting worker. SW now also handles `SKIP_WAITING` postMessage and uses `clients.claim()` inside an awaited activate handler. New convention: every brief that touches `frontend/` MUST be developed on a `brief/B<n>-<slug>` branch and tested via the Vercel preview URL before merge to main. | B | S | ✅ Done | Merged to main via `e793ab0` after Vercel preview verification. Effect: PWA cache invalidation now automatic per-deploy. (2026-04-08) |
| B195 | **Hörst 7-53 intensity + hangboard baseline writers** — `HANGBOARD_DEFAULT_INTENSITY_PCT["horst_7_53"]` corrected `0.70 → 0.90` (was repeater-level, catalog notes specify 90-95% MVC per Hörst/López). Both `max_hang_5s` and `max_hang_7s` test session writers in `_update_test_from_log` now populate full protocol fields (`hang_seconds`, `edge_mm=20`, `grip=half_crimp`) on `baselines.hangboard[0]`; previously the 5s branch wrote nothing beyond `max_total_load_kg` and the 7s branch wrote only `hang_seconds=7`, causing `_pick_hangboard_baseline` to fall back with WARNING on every session resolution. `_estimate_hangboard_baseline` (grade/pullup-derived stims) also now populates the same defaults. One-off migration script `scripts/migrate_baseline_fields.py` patched Daniele's incomplete production baseline. | B | S | ✅ Done | +9 e2e tests in `test_test_session_e2e.py` (red→green), +1 regression guard in `test_progression_v1.py`. 1596 tests pass. Effect for Daniele: Hörst 7-53 now suggests +31 kg (was +7 kg). 3 tech debt items spawned: TD-HORST-1/2/3. (2026-04-07) |
| A194 | **Feedback submit atomic — 5 round-trip → 1** — collapsed guided session submit from 5 sequential backend round-trips (getState → getWeek → applyEvents → postFeedback → refetchQueries) down to a single POST /api/feedback. The endpoint now applies `mark_done` inline via `apply_events()` on `current_week_plan`, appends to `session_completion_log` with dedup guard, and returns the updated `week_plan` so the frontend can `setQueryData(['week', 0], …)` instead of issuing a separate refetch. B193 timing instrumentation removed in the same brief. | A | M | ✅ Done | Backend: `persist_week_plan` exposed as public helper from `replanner.py`; new `test_a194_feedback_atomic.py` (6 cases) using TestClient; `test_a139_actual_exercises.py` rewritten to use TestClient against the real endpoint (R4). Scope: only `current_week_plan` — past/future sessions continue through legacy flow (R6). Dedup: skip completion_log append if entry with same date+session_id+status already exists (R3). Frontend: `use-feedback.ts` onSuccess now does `setQueryData`; guided page handleSubmit reduced from ~170 lines of prelude+refetch to a single `postFeedback` call. 1586 tests pass. (2026-04-07) |
| A193 | **Core Training v1.1 + 7 new core exercises + hangboard→pullup_bar equipment rule** — D189 audit found `core_training.json` resolved only 3 exercises (~15 min real) against a `time_budget` of 40 min, and the anti_lateral_flexion pool had only 1 exercise making variety impossible. Session restructured to v1.1: `general_warmup` template added, `compression` + `anti_rotation` + `anti_lateral_flexion` promoted to `required`, optional `isometric_hold_or_rotation` finisher block, time_budget corrected 40→35 / 50→45. 7 new catalog exercises (189→196): `front_lever_one_leg`, `front_lever_straddle`, `kneeling_superman`, `knees_to_elbows`, `suitcase_carry`, plus bodyweight fallbacks `v_up` (compression) and `plank_shoulder_tap` (anti_rotation) so home-only users without pullup_bar still get full pattern coverage. `copenhagen_plank` equipment fixed (`["bench"]` → `[]`, cue updated to "chair/bench/sofa/any raised surface"). `windshield_wipers` marked with `safety_notes` (KB Kapandji flag: combined spinal flexion + rotation). Equipment engine: `expand_equipment()` now applies `hangboard`/`hangboard_20mm` → implies `pullup_bar` (a hangboard is always mounted on a bar — the two cannot be separated in practice; `loading_pin` intentionally excluded as it's a ground-based alternative). Rule is centralised so planner/resolver/replanner all honour it. | A+C | M | ✅ Done | +8 tests in `test_a193_hangboard_implies_pullup_bar.py` (6 unit on `expand_equipment` + 2 integration via `pick_best_exercise_p0`). Collateral: `test_planner_v2.py::test_pullup_test_at_gym_when_home_lacks_pullup_bar` updated — dropped `hangboard` from the home_equipment fixture since under the new rule it would imply `pullup_bar`. Vocabulary updated. Resolution check against Daniele's real state returns 11 exercises / ~43 min duration with all 4 required blocks matching their pattern. 1617 tests pass. (2026-04-08) |
| B198 | **Outdoor load score in Week view** — `load_score` computed by backend on `GET /api/outdoor/sessions` was not displayed in Week view. Added `outdoor_load_score` field to `DayPlan` and `OutdoorSession` TS types; extracted load per date from `getOutdoorSessions()` into `outdoorLoadMap`; passed as `outdoorLoadScore` prop to `DayCard` which now shows a `Load: N` badge on completed outdoor sessions alongside the green "Completed" badge; included outdoor load in the weekly "Done" load total calculation. | B | XS | ✅ Done | No backend changes needed — `/api/outdoor/sessions` already returns `load_score`. (2026-04-08) |
| B197 | **Feedback resubmit dedup + duration preserve + circuit history** — two prod bugs from Daniele's 2026-04-07 session. (Bug 1) Guided session "Finger Strength" showed "Completed · 1 min" instead of ~30 min: the user re-ran the flow (likely after a /today render race post-A194), each rerun resetting `state.startedAt = Date.now()` in `buildGuidedState`; backend `feedback.py` section 7 then last-write-wins clobbered the real `session_duration_seconds` on the completion log entry, and `append_feedback_log` had no dedup so prod state had 5 entries for the same (date, session_id). (Bug 2) Core Circuit free session showed "0 exercises" — `GET /api/free-session/history` returned a lightweight view that omitted the `circuit` field, so `fs.circuit?.completed_exercises ?? 0` rendered 0. Fix bundle: backend completion log keeps `max(prev, new)` duration; `append_feedback_log` dedups by (date, session_id) and merges with max-duration; `free_session.get_history` now returns `circuit`; frontend `session-card.tsx` extracts a `handleStartGuided` helper that (a) refuses to re-start when `session.status === "done"/"skipped"`, (b) preserves any pre-existing `startedAt` from localStorage even when `hasSavedProgress` says false. | B | S | ✅ Done | +7 tests in `test_b197_feedback_dedup.py` (3 completion log + 3 feedback_log dedup + 1 history.circuit). 1609 tests pass. (2026-04-08) |
### A-B5 — Phase labels and messaging per discipline

**Priority:** P2 | **Status:** ✅ Done (2026-03-31) | **Type:** A (frontend + backend) | **Effort:** S

Phase display names adapt: base → "Movement & Volume Base" (boulder), strength_power → "Max Strength & Power" (boulder), power_endurance → "Work Capacity" (boulder), performance → "Projecting & Peak" (boulder). Centralized in `lib/phase-labels.ts` (frontend) and `PHASE_NAMES_BOULDER` (backend). 7 frontend + 3 backend tests.

### A-B7 — Boulder target in guided sessions

**Priority:** P2 | **Status:** ✅ Done (2026-03-31) | **Type:** A (backend + frontend) | **Effort:** S

`_boulder_target_info()` returns grade range (offset_high/offset_low) + attempt/rest guidance per session intent. Guided session shows target grade range and guidance tips. 5 backend tests.

### A-B9 — Process cues and phase tips for boulder

**Priority:** P2 | **Status:** ✅ Done (C203, 2026-04-09) | **Type:** C (content) | **Effort:** S

10 new boulder-tagged process cues (cue_026..cue_035) added to
`backend/catalog/cues/v1/process_cues.json`, reusing the A141 rotation
infrastructure (one deterministic cue per session per day). Intent→template
mapping: limit→`limit_boulder_gym`, power→`power_contact_gym`,
volume→`boulder_circuit_gym`. Cues 032 (progressive warm-up) and 035
(no static forearm stretching) also tag `route_projecting_gym` and
`power_endurance_gym` since the principle is discipline-agnostic. Sources:
Seifert 2017, Hörst (Ch.6/Ch.12), Draper 2006, Watts 2000, López,
Ondra/Bachar. 5 phase tips stored in
`frontend/src/lib/boulder-phase-tips.ts` (static frontend constants, no
backend endpoint), rendered as a dismissible banner in `/today` when
`goal.discipline === "boulder"`. Dismissal persisted per-phase in
`localStorage` under `boulder_phase_tip_dismissed_${phaseId}` so the
banner reappears on phase transitions. 1624 tests pass; all existing cue
coverage tests (`test_process_cues.py`) still green.

---

### R140 — Backend Error Handling Hardening ✅

**Priority:** P2.25 | **Status:** Closed (2026-03-26) | **Type:** R (refactor)

Logging aggiunto a 6 moduli engine, 5 `except:pass` silenziosi sostituiti con `logger.warning`, cache globali mutabili (`_required_equipment_cache`, `_cached_quotes`) sostituite con `@lru_cache`, validazione input su `generate_phase_week`, `generate_macrocycle`, `resolve_session`, `suggest_sessions`, `apply_day_add`.

### R141 — Frontend Error Handling Hardening

**Priority:** P2.25 | **Status:** ✅ Closed (B165c, 2026-03-31) | **Type:** R (refactor)

- Sostituire `.catch(() => {})` silenziosi (~20 istanze) con error toast
- Validazione Zod su `JSON.parse` del localStorage nella guided session
- `AbortController` sulla navigazione week
- Stati loading/error consistenti su `today/`, `plan/`, `outdoor/`

> Note: D163 + D164 audits confirmed ~20+ instances. Will be addressed as part of B165c.

**Rischio:** BASSO — cambiamenti UX difensivi

### Combo sessions (climbing + conditioning tail)

**Status:** ✅ Resolved by B160g | **Effort:** M

~~Sessions with a primary climbing block (60-70 min) + secondary conditioning block (15-20 min core/prehab/antagonists).~~ **Resolved:** B160g added core_standard + antagonist_prehab tail blocks to all gym sessions that were missing them. Every gym session now follows the strength_long pattern: warmup → main → core → antagonist → cooldown.

### Gym-aware PE routing

**Status:** ✅ Done (B201, 2026-04-09) | **Effort:** S

PE sessions now prefer gyms with `gym_routes` over boulder-only gyms when both are available. `_select_gym_id` accepts a `preferred_equipment` parameter and applies a soft bonus (Pass 1: required + preferred; Pass 2: required only; Pass 3: first by priority). Soft preference — never drops sessions when no gym has routes. `power_endurance_gym` already had `preferred_equipment=["gym_routes"]` in `_SESSION_META` (B160d infrastructure); B201 wired it through to the in-day gym selection. 3 unit tests added (`TestPlannerV2B201PreferredGymRouting`).

---

### Free Session UI grouping — collapse climbing surfaces

**Priority:** P2.5 | **Status:** ✅ Done (A202, 2026-04-09) | **Type:** A (frontend only) | **Effort:** S

Single "Climbing" card with tap-to-expand, showing available surfaces. Add-ons section below. Surfaces filtered by user equipment (gyms ∪ home); falls back to all 5 when equipment unknown. Single-surface shortcut skips the expand and selects directly. Collapsed by default.

### Core Circuit exercise images — Gemini AI generation

**Priority:** P2.5 | **Status:** ✅ Done — 30/30 | **Type:** C (content)

All 30 core circuit exercises have images. Generated via Gemini AI, renamed and linked in `circuit-exercises.ts`.

### C164 — Catalog expansion: Category B exercise pools

**Priority:** P2.5b | **Status:** ✅ Done (C164, 2026-04-08) | **Type:** C (catalog) | **Effort:** M

**Problem:** Phase 0 of Brief B (resolver scoring, 2026-03-28) diagnosed 4 template blocks
where exercise variety is impossible regardless of scoring tuning, because the P0 filter
pipeline leaves ≤2 candidates. No amount of recency rebalancing can fix a pool of 1-2.

**Affected blocks (from production P0 analysis on Daniele's S&P weeks):**

| Block | Session(s) | P0 survivors | Gap |
|-------|-----------|-------------|-----|
| `limit_projecting` | `limit_boulder_gym` | 2 (`board_limit_boulders`, `limit_bouldering`) | Need 2-3 more limit boulder variants (spray wall problems, system board limit, moonboard limit) |
| `limit_bouldering` | `power_contact_gym` | 2 (same pool) | Same gap — shared role/domain/pattern filters |
| `threshold_main` | `route_endurance_gym` | 1 (`threshold_climbing`) | Need 2-3 threshold route variants (linked laps, route on-the-minute, threshold circuit) |
| `capacity_hangboard` | `endurance_aerobic_gym` | 1 (`long_duration_hang`) | Need 2-3 long finger endurance variants (density hangs, intermittent dead hangs, sub-max long hangs) |

**Why this matters:** These blocks appear in sessions that run 1-2×/week in S&P and Performance
phases. Users see the exact same exercise every single week for 4-6 weeks straight. This is the
#1 visible monotony issue in the app.

**Approach:** One C-type brief per block group. Each exercise needs: full JSON entry in
`exercises.json`, correct `role`/`domain`/`pattern`/`recency_group` tags, `load_model` +
`prescription_defaults`, literature-backed protocol parameters.

**Depends on:** Nothing. Can be done independently of Brief B (scoring rebalance).
**Cross-ref:** Engine Audit v3 finding F8, Brief B Phase 0 diagnosis.

### Hörst "Training for Climbing" (3rd ed.) — Status

7 of 13 chapters synthesized into structured MD files. 0 conflicts with existing D01-D83 decisions. 14 confirmations. 6 new coaching cues proposed.

| Ch. | File | Status | Enriches Decisions |
|-----|------|--------|--------------------|
| 2 | `horst_ch2_self_assessment_synthesis.md` | ✅ | D01 (context) |
| 3 | `horst_ch3_mental_training_synthesis.md` | ✅ | D29, D30 (context) |
| 4 | `horst_ch4_technique_skill_synthesis.md` | ✅ | D73, D76 (context) |
| 6 | `horst_ch6_mobility_synthesis.md` | ✅ | **D33, D58, D60 — 38 exercises ready** |
| 11 | `horst_ch11_nutrition_synthesis.md` | ✅ | D65, D66, D67 (enrichment) |
| 12 | `horst_ch12_recovery_synthesis.md` | ✅ | **D17, D70 — quantified recovery data** |
| 13 | `horst_ch13_injury_synthesis.md` | ✅ | D68-D72 (context) |

**Key audit finding — CUE-02 (v1, affects D33):** Excessive forearm flexor static stretching before climbing reduces grip strength for up to 1 hour. The warm-up generator (D33) must not prescribe heavy forearm flexor stretches before performance sessions.

### R144 — Frontend API Layer Refactor ✅

**Status:** ✅ Closed (A187, 2026-04-07) | TanStack Query integrato con cache condivisa per `state`, `week/{n}`, outdoor, free-session surfaces; mutations centralizzate in `lib/hooks/mutations/`; invalidation map (D176) implementata in `lib/invalidation.ts`; prefetch settimane adiacenti su `useWeekPlan`. `api.ts` resta come thin layer sui fetch — il refactor di splitting è rimandato.
**Rischio:** MEDIO

### Feedback Loop Education Copy

**Status:** ✅ Done (A202, 2026-04-09) — main UI touchpoint | **Effort:** XS

Dismissible education banner added above the day card in `/today`, shown only
after ≥1 completed session. Copy: "Il tuo feedback adatta i carichi — Dopo
ogni esercizio, il tuo giudizio (facile/ok/difficile) regola automaticamente
peso e volume delle sessioni future. Più feedback dai, più il piano diventa
preciso." Dismissal persisted in `localStorage` under
`feedback_education_dismissed`. Onboarding touchpoint deferred (lower priority
per brief).

Related: D77 (SDT principles), D79 ("Train better, not more" personality), Educational content (methodology explanations).

| ✅ B191 | Phase-aware retest scheduling + Christie fixes | Fixed 4 bugs: dashboard phase display (duration_weeks key), hangboard freshness (estimated_at fallback), repeater freshness (onboarding users), Pass 3 phase-blind scheduling. `_PHASE_TEST_MAP` added. `skipped_tests` in week plan. 1580 tests. |


### Archived from ROADMAP_CURRENT.md — 2026-04-19

| A-DEMO-01 | **Demo session page** — `/demo` public route with timers, full ~100 min session walkthrough + CTA | A | S | ✅ Done | A182 + B190 (2026-04-08) |
| B-DEMO-02 | **Demo session restructure** — strength-first exercise order, English copy | B | XS | ✅ Done | 2d7feca (2026-04-08) |
| GTM-03 | **Pricing decision** — choose final price point and model | — | — | ✅ Done | USD pricing. $9.99/mo Standard + $4.99/mo Founding Climber (first 20, locked forever), 15-day trial. Two Stripe Price objects, not coupon. Product: `prod_ULXc8O7pmuA2`. |
| GTM-04 | **Stripe go-live** — two-tier pricing, B188 revert, subscribe page update | B | S | ✅ Done | Live keys deployed 2026-04-16. Full E2E tested: checkout → access → portal → cancel at period end. D205 audit + B202 fix shipped same day. |
| B-stripe-recovery | **Stripe stale customer_id recovery** — handle deleted/invalid Stripe customers gracefully | B | XS | ✅ Done | Auto-recovery when Stripe customer no longer exists. Part of GTM-04 hardening. |
| B-BYPASS-DANIELE | **Founder subscription bypass** — env var `BYPASS_USER_IDS` skips Stripe check for founder | B | XS | ✅ Done | `subscription_guard.py` reads comma-separated UUIDs from env var. No Stripe customer created for founder. Railway env var set. |
| D205 | **Subscription status leak & webhook robustness audit** | D | S | ✅ Done | Report: `docs/audit/D205_subscription_audit_2026_04_16.md`. Fail-open bug (H3), unhandled customer.deleted, portal button failure. Spawned B202/B203/B204/B205. |
| B202 | **Fix fail-open → fail-closed subscription check** | B | S | ✅ Done | check_subscription() returns deny when no row + Stripe configured. Frontend defaults to canInteract=false on error. 1651 tests pass. |
| B212 | **Guard checkout endpoint against overwriting active/trialing subscription** | B | XS | ✅ Done | Short-circuit in `POST /api/subscription/checkout` when existing row status ∈ `_ACTIVE_STATUSES`. Returns `{already_active, status, redirect_url}` instead of creating a second Checkout Session + writing `pending_checkout`. Frontend redirects to `/today` when `already_active=true`. 4 new tests in `test_b212_checkout_guard.py`. Fixes Daniele 2026-04-17 (trial Stripe `trialing` clobbered a `pending_checkout` dopo Reset + re-onboarding). |
| D-MAINT-01 | **Fix endpoint table in CLAUDE.md** — correct count 54→56 | D | XS | ✅ Done | Doc-only fix. |
| A198 | **Repo cleanup per D197 audit** — delete 24 obsolete docs/scripts, archive council reports | A | S | ✅ Done | Hygiene sweep. |
| A199 | **Dynamic slider capping on availability page** | A | XS | ✅ Done | Frontend-only UX improvement. |
| C204 | **Pump-management cues to route_on_the_minute** | C | XS | ✅ Done | Catalog content addition. |
| D209 | **Next.js version audit** — rename middleware→proxy, update docs 14→16 | D | XS | ✅ Done | Doc + rename only. |
| B206 | **Single source of truth for session location** — invert resolver precedence (runtime > template) + strip `context.location` from 28 catalog JSONs + derive location from `_SESSION_META` | B | M | ✅ Done | Fixes Daniele 2026-04-17: `aerobic_pyramid_intervals` resolved for `finger_maintenance_gym` on home slot. Added `LEGACY_SESSION_ALIASES` extension point. Downstream symptom fix — upstream cause tracked in B208. |
| D210 | **B206 verification audit** — before/after comparison against pre-B206 worktree (5 scenarios + Daniele prod regression) | D | S | ✅ Done | Report: `docs/audit/D210_b206_verification.md`. Zero gym regressions, Daniele real-incompat 2→1. Surfaced residual B207 (warmup_easy_boulders bypass). |
| D93 | **Grade offset catalog audit** — full-catalog review of all 31 `grade_offset` exercises | D | M | ✅ Done | Audit report: `docs/audit/audit_route_intervals_offset_D93.md`. Found `route_intervals` misclassified at -2 (should be -1). |
| B94 | **Fix `route_intervals.grade_offset` -2 → -1** + test gap fix + vocab sync | B | S | ✅ Done | Catalog patch, 5 new tests (1 catalog e2e + 4 parametrized), vocabulary synced. `emom_bouldering` deferred to D95. |
| B208 | **Narrow `_expand_session_locations` to wall-surface sessions** (Option A) | B | S | ✅ Done | Root-cause fix upstream of B206. Planner now only re-routes to home when session requires a wall surface (gym_boulder/spraywall/board_*/homewall/gym_routes) AND home has a wall equivalent. Hangboard-/weight-only gym sessions stay at their declared location. 2 regression tests added. Proposal: `docs/briefs/B208_proposal.md`. |
| A-ACTIVATION-TIMING | **First-session activation fix** — shift start_date to this_monday() + Today hero CTA + cold-start retrofit | A | M | ✅ Done | Addresses 75% stage-4 drop-off from D-ANALYTICS-DROPOFF. Branch: `brief/A-ACTIVATION-timing`. Day 1 onboarding shift + Day 2 fallback + Day 3 /today hero (4 states) + Day 4 retrofit script. Retrofit: run `scripts/retrofit_coldstart_users.py` after merge. |
| B204 | **Subscription guard 402 UX + cancel status display** | B | S | Open | Global 402 interceptor → redirect to /subscribe (not raw JSON). Portal 404 handling. cancel_at_period_end display. Depends on B202 ✅. |
| A205 | **Session Builder** — backend CRUD + data model | P3 | A | S | ✅ Done | Backend: CRUD API (`/api/custom-session`), exercise listing with search/filter, warmup/cooldown blocks, load score + duration computation. Data in `user_state.custom_sessions[]`. 27 tests. Frontend builder page is A206 (separate brief). |
| A206 | **Session Builder** — frontend builder page | P3 | A | M | ✅ Done | "My Sessions" collapsible section on Free Session page, builder with exercise picker + domain chips, params editor, warmup/cooldown template picker, drag reorder, save/edit/delete. View mode with exercise checklist + progress bar. 15 new files, 38 pages, 67 components. |
| A207 | **Session Builder** — Today/Week integration | P3 | A | M | ✅ Done | `add_custom_session` replanner event (bypasses ripple/spacing, `is_custom: True`, no closed-loop feedback). QuickAddDialog "My Sessions" branch. SessionSlot/SessionCard render inline exercises, "Custom" badge, start routes to `/session-builder/{id}/view`. 6 new tests. |
| D204 | **Session Builder audit** — pre-implementation audit of A205 design | P3 | D | XS | ✅ Done | `docs/audit/D204_session_builder_audit.md`. Covered: data model, CRUD API, exercise catalog, load scoring, warmup/cooldown blocks. |
| A210 | **Boulder only ephemeral override** — boulder_fallback field + equipment_override | P3 | A | S | ✅ Done | `boulder_fallback` field in session instances, `equipment_required` in instances, `equipment_override` param in resolve. SessionCard UI for toggle. |

