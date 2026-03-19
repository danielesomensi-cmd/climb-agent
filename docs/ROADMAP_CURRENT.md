# climb-agent — Active Roadmap

> Last updated: 2026-03-19
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Mega Brief v1 — Implementation Status

> Source: `docs/claude_code_mega_brief_v1.md` (57 v1 decisions, 10 sessions)
> Rule: ogni sessione completata o deferita aggiorna questa tabella E la sezione roadmap appropriata.

| Session | Decisions | Status | Notes |
|---------|-----------|--------|-------|
| 1: Assessment & Onboarding | D01, D38, D68, D80, D81, D83 | ✅ Done (2026-03-17) | D68: via limitations, non domande esplicite |
| 1b: Test Protocol Revision | D84, D84b, D85, D86, D88, D90 | ✅ Done (2026-03-18) | D87b, D89, D91 → v2 |
| 2: Exercise DB — Strength | D10, D11, D12, D39, D50, D72 | 🟡 Partial | D11 ✅ D12 ✅ D39 ✅. Deferred: D10 (equipment), D50 (selector logic), D72 (grip field) |
| 3: Exercise DB — Conditioning | D37, D43, D55, D56, D57, D60, D76 | 🟡 Partial | D43 ✅ D55 ✅ D56 ✅ D57 ✅ D76 ✅. Deferred: D37 (core drills Matros). D60 already done. |
| 4: Warm-Up | D33, D36, D74 | 🟡 Partial | Warmup via template (non funzione dedicata). Nessun PAP. silent_feet esiste ma non in warmup |
| 5: Intensity System (EL) | D34, D52, D14 | 🔲 Not started | Zero codice EL/intensity/load monitoring |
| 6: Hangboard Logic | D35, D49 | 🔲 Not started | Zero experience gates / method restriction |
| 7: Endurance & Intervals | D47, D48, D53 | 🟡 Partial | 4x4 esiste. Mancano: varied-intensity, active recovery, g-tox |
| 8: Conditioning & Ratio | D51, D54, D58, D59, D73, D78 | 🟡 Partial | face_pull + band_pull_apart + planks. Mancano: ratio, technique allocation, process cues |
| 9: Periodization & Load | D19-D21, D44, D45, D69-D71 | 🟡 Partial | min_weeks esiste. Mancano: beginner linear, overreach, ACWR, OTS, volume cap |
| 10: Coaching & UX | D17, D29, D30, D41, D64-D67, D75, D77, D79 | 🔲 Not started | Zero coaching cues, safety drills, UX educativo |

---

## Priority 1 — Stability and bug fixes

All P1 items completed (30 items). See archived history in `docs/ROADMAP_v2.md`.

Recently closed (2026-03-19):
- **B133 + B133-fix + B134** — Repeater test protocol fix (Lattice 2025). New exercise `test_repeater_7_3_to_failure` (1 set to failure @60% MVC-7, reps=40 ceiling). LP repeater reps null→40. Template swapped. Frontend: reps per hand form for LP + HB bilateral, handleDone reps submission fix, counterweight warning text fix, LP session name 5s→7s. Profile editor: "Profile & Maxes", added BW pullups field, repeater label "reps to failure". B134: TypeScript types for per-hand reps in guided session serialization.
- **Session 1 (D01, D38, D68, D80, D81, D83)** — Assessment & Onboarding mega brief decisions (2026-03-17). body_composition axis removed (5 axes), Brzycki 1RM estimation, injury detection via limitations, age gate <16, youth 4 days/week cap, recovery multiplier 40+.
- **Session 1b (D84-D91)** — Test protocol revision (2026-03-18). D85: finger test 5s→7s (MVC-7). D84: pulling test 1RM→2RM + Brzycki/Epley estimation + BW gate. D86: duration test benchmarks removed (wrong edge size). D88: L-sit benchmarks added. D90: med_test removed from catalog. Deferred to v2: D87b, D89, D91.
- **~~B131~~** — LP test session UX fixes (2026-03-17). Duration field input, suggestion recalc after LP max test, hand layout icons. Commit: `b063cc0`.

Previously closed (2026-03-18):
- **A121** — Phase-aware intra-session exercise ordering. Exercises are now sorted by physiological priority based on macrocycle phase (e.g., ARC before threshold in Base, max hangs before pulling in S&P). 13 derived sort categories, 5 phase maps, 5 hard constraints. Pure reorder — zero exercise loss guaranteed. 41 new tests.

Previously closed (2026-03-15):
- **D126/B126** — Resolver Stage 2c bug: finger device preference (`hangboard`/`loading_pin`) replaced the ENTIRE exercise pool, killing all climbing/bodyweight/campus exercises. Fix: Stage 2c now only filters among finger-device exercises; non-finger exercises are untouched. Also fixed `load_recent_exercise_ids` DATA_DIR path for production, added conditional trace logging (`TRACE_RESOLVE` env var).
- **B127** — Assessment profile auto-refresh: `save_state()` now recomputes profile when inputs change (fingerprint guard)
- **B126** — Weekly report audit: fixed 5 bugs (outdoor grade comparison, spontaneous outdoor in Day by Day, other_activity rendering, top_grade_attempted, duration tracking) + KPI enrichment (training_time, active_days, weekly summary card)
- **B127 (duration)** — 3-level duration capture: guided timer → mark-done user input → template estimate. Manual session edit (name, difficulty, duration). FeedbackDialog with slot-based duration pre-fill

---

## Priority 1b — Beta feedback (Christie, 2026-03-07)

All P1b items completed (3 items). See archived history in `docs/ROADMAP_v2.md`.

### B128 — Test duplicati dopo rigenerazione macrociclo

**Priority:** P1b — non blocca il lancio ma brutta UX
**Status:** Open
**Discovered:** 2026-03-18

**Problema:** Quando l'utente rigenera il macrociclo ("Rigenera da oggi"), il planner schedula test iniziali (Max Hang 5s, Repeater 7/3, ecc.) anche se gli stessi test sono stati completati 1-2 giorni prima. I risultati sono già freschi nello user_state (baselines, assessment) — rischedulare è inutile e confonde l'utente.

**Caso concreto:** Utente completa Test Max Hang 5s martedì 17 Mar. Mercoledì 18 rigenera macrociclo → il planner mette di nuovo Test Max Hang 5s il mercoledì stesso.

**Fix proposta:** Prima di schedulare un test, il planner deve verificare:
1. Cercare in `user_state.completed_sessions` (o feedback log) se quel tipo di test è stato completato negli ultimi N giorni (proposta: 14 giorni)
2. Se completato recentemente → skip, usa i risultati esistenti
3. Se non completato o risultati vecchi → schedula normalmente

**Moduli coinvolti:** `planner_v2.py` (test scheduling logic, pass 3)
**Rischio:** MEDIO — tocca planner ma logica isolata (solo check pre-scheduling)

**Non fare ora** — solo documentare in roadmap.

---

## Priority 2 — Auth + Payments + DB (go-to-market blockers)

These must be done before paid launch.

- **Clerk auth** (Next.js native) — replace UUID/localStorage system
  - Migration path: CLIMB-XXXX recovery codes → Clerk accounts
  - Current recovery code system (B82) serves as bridge
- **Supabase Postgres** — replace JSON file persistence
  - user_state, feedback logs, outdoor logs → proper tables
  - Railway persistent volume → deprecated after migration
- **Stripe subscriptions** — pricing model TBD
  - Free tier vs paid features to be defined

---

## Priority 2.5 — Catalog audit

### ~~B129 — Verificare domain di threshold_climbing nel catalogo~~ ✅

**Priority:** P2.5 (catalog audit)
**Status:** Closed (2026-03-19)
**Discovered:** 2026-03-18 durante A121

**Fix:** domain cambiato da `aerobic_capacity` → `power_endurance` in `exercises.json`. Filtro sessione `route_endurance_gym.json` aggiornato di conseguenza. Sort category ora correttamente derivata come `pe_intervals` (priority 6 in Base) anziché `aerobic_pure` (priority 2). Commit: `5ab1100`.

### C130 — Audit sistematico domain/intensity/pattern di tutti gli esercizi

**Priority:** P2.5
**Status:** Open
**Discovered:** 2026-03-18 (durante A121 + knowledge base review)
**Type:** C (catalog)

**Origine:** Il bug di `threshold_climbing` (domain `aerobic_capacity` invece di `power_endurance`) ha rivelato che il catalogo potrebbe avere altre incoerenze domain-esercizio. La knowledge base ha prodotto un framework di audit completo.

**Cosa verificare per OGNI esercizio (167 attuali):**

Per ogni exercise entry, cross-check la coerenza tra 4 campi:
1. `domain` — è il domain corretto per l'adattamento primario?
2. `intensity_level` — è coerente col domain?
3. `pattern` — riflette il tipo di movimento/protocollo reale?
4. `grade_offset` (se grade_relative) — coerente col domain?

**Tabella di riferimento per cross-check (dalla knowledge base):**

| Domain | Intensità attesa | Grade offset tipico | Pattern tipici |
|--------|-----------------|-------------------|----------------|
| `finger_max_strength` | `max` / `high` | N/A (hangboard) | `isometric_hang` |
| `finger_strength_endurance` | `medium` / `high` | N/A (hangboard) | `repeater_hang` |
| `finger_aerobic_endurance` | `low` / `medium` | N/A (hangboard) | `repeater_hang` |
| `power` | `max` / `high` | 0 (limit) | `climbing_limit_boulder`, `campus_ladder` |
| `contact_strength` | `max` / `high` | N/A | `campus_ladder` |
| `power_endurance` | `medium` / `high` | -1 a -2 | `climbing_intervals`, `climbing_continuous` |
| `aerobic_capacity` | `low` / `very_low` | -4 a -5 | `climbing_continuous` |
| `anaerobic_capacity` | `high` | -1 a -2 | `climbing_intervals` |
| `regeneration` | `very_low` | -5 o più facile | `climbing_continuous` |
| `strength_general` | varia | N/A | `push`, `pull_*`, `hinge`, `squat` |
| `core` | `low` a `high` | N/A | `anti_extension`, `anti_rotation`, `compression` |

**Red flags da cercare:**

1. **Domain/intensity mismatch** — es. domain=`aerobic_capacity` + intensity=`high`
2. **Domain/grade mismatch** — es. domain=`aerobic_capacity` + grade_offset=-1
3. **Domain/cue mismatch** — il testo del cue descrive sforzo incompatibile col domain
4. **Domain/phase mismatch** — esercizio assegnato a fasi che non corrispondono al domain
5. **Pattern/domain mismatch** — es. pattern=`climbing_limit_boulder` + domain=`aerobic_capacity`

**Formato output atteso per ogni anomalia:**
```
ANOMALIA: [exercise_id]
  Campo: [quale campo è incoerente]
  Valore attuale: [valore]
  Valore suggerito: [valore corretto]
  Motivo: [1 frase]
```

**Impatto downstream:**
- Il sistema A121 (exercise ordering) dipende dalla correttezza dei domain per la derivazione sort category
- Domain sbagliati = esercizi piazzati nell'ordine sbagliato in sessione
- Caso concreto: threshold_climbing con domain aerobic_capacity veniva classificato come ARC → stesso slot di ARC invece che dopo

**Riferimenti knowledge base (progetto "climb-agent knowledge base"):**
- Analisi completa threshold_climbing: domain aerobic_capacity → power_endurance (review fisiologica ARC vs threshold, tabella comparativa intensità/pump/sistema energetico)
- Framework audit con regole di coerenza domain/intensity/grade/pattern
- Tabella cross-check validata contro letteratura (Hörst, López-Rivera, Consuegra Ch.8)

**Dipendenze:**
- Prerequisito: threshold_climbing fix (già fatto, commit 2026-03-18)
- Input: catalogo esercizi (`backend/catalog/exercises/v1/`), vocabulary_v1.md, mappatura A121 sort categories
- Output: lista anomalie + fix proposti → da implementare come brief C separato

**Rischio:** BASSO — audit read-only, i fix sono patch isolate al catalogo JSON. Non tocca engine logic.

**Effort stimato:** M (1 sessione Claude Code per audit + 1 per fix)

---

## Priority 2b — Test results → full exercise calibration

> Prerequisite: B122 (baselines.pulling) establishes the pattern. This phase extends it to ALL test results.

Principle: every test result we collect MUST influence exercise prescription — if it doesn't affect anything, we shouldn't ask for it.

|Test result                  |Current use                  |New use                                                                                                                                                                                                           |Impact                           |
|-----------------------------|-----------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------|
|L-sit hold (sec)             |radar `body_composition` only|**Core progression tier**: tier 1 (<10s) = dead bug, plank; tier 2 (10-30s) = L-sit raises, hanging leg raise; tier 3 (30s+) = dragon flag, front lever progressions. Resolver selects from tier-appropriate pool.|Exercise selection + prescription|
|Hip flexibility straddle (cm)|radar `body_composition` only|**Mobility tier**: skip acquired stretches (>140cm = no basic straddle), propose advanced progressions (pancake, middle split). Reduce wasted time on easy drills.                                                |Exercise selection               |
|Repeater 7/3 max sets        |radar `power_endurance` only |**Finger endurance volume calibration**: max sets → working set count. 4 max → 3 work sets; 8 max → 5-6 work sets. Scales finger endurance session density.                                                       |Prescription (sets/volume)       |
|Max hang duration (sec)      |radar `endurance` only       |**Endurance hang calibration**: scales hang times in endurance sessions. 30s max vs 90s max → different prescribed durations. May also influence rest periods.                                                    |Prescription (time)              |

Architecture pattern (uniform for all):

```
test_result → tier OR scaling_factor
  → resolver uses tier/factor for:
    a) exercise pool filtering (tier-based selection)
    b) reps/sets/tempo scaling (prescription adjustment)
    c) initial progression starting point
```

Depends on: B122 pattern established, Supabase migration (for proper schema).
Feeds into: Phase 3.5 LLM Coach (coach explains "why" using tier context).

---

## Priority 3 — UI polish (parallel with P2)

Items that affect first impression for paying users.

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B40 | Branch develop/main workflow | S | Set up develop branch for staging, main for production deploys. |

---

## Priority 4 — Go-to-market

- Landing page / marketing site
- Pricing model definition
- App Store prep (Capacitor wrapping PWA — Phase 4d, zero code rewrite)

---

## Future — Phase 3.5: LLM Coach

Claude Sonnet as conversational layer over the deterministic engine.

- Dynamic system prompt injecting user_state + current plan + recent logs
- POST /chat endpoint
- Use cases: conversational onboarding, pre-session coaching, post-session analysis, climbing discussion
- The LLM suggests and converses — it does NOT modify the plan directly
- API key managed in backend (env var)

**Dependent items:**
| ID | Title | Notes |
|----|-------|-------|
| B89 | Weekly report narrative LLM | Phase 2 of B65 weekly report. Replace rule-based insights with LLM-generated narrative. |
| B11 | Configurable test protocols | Custom test exercises and schedules beyond the 3 defaults. |
| B29a | Dedicated test exercises in catalog | Separate test-specific exercise entries with test-optimized prescriptions. |
| — | Science explainers | Il Coach spiega il "perché" di ogni scelta: fisiologia, riferimenti letteratura (Hörst, Eva López, Tyler Nelson). Contestuale alla sessione corrente. |
| — | Nutrition hints (post-workout) | Consigli contestuali su alimentazione e idratazione post-sessione. Disclaimer legale obbligatorio ("not medical/nutritional advice"). Nice-to-have, non core. |

---

## Future — Engine improvements

| ID | Title | Notes |
|----|-------|-------|
| — | Override intensity cap warning | Warn when user overrides with session above current phase intensity cap. |
| — | P1 ranking in resolver | Recency, intensity, and fatigue-based exercise prioritization. |
| ARCH-3 | Generic timer behavior from prescription | Frontend timer derives behavior entirely from `work_seconds` + `reps` + `rest_*` fields. No hardcoded exercise lists or category checks. All exercises with `work_seconds > 0` get a countdown; manual mode otherwise. |
| — | Advanced adaptivity | Readiness score, overreach detection, plateau detection (DESIGN_DOC §4.4 spec). |
| — | Test results → exercise calibration | Use ALL assessment test results (repeaters, max hang duration, L-sit, hip flexibility) to calibrate exercise difficulty and prescription — not just for radar profile. E.g.: repeater max sets → finger endurance set count; L-sit hold → core exercise progression tier; max hang duration → endurance hang prescriptions. Requires: mapping table test_result → affected exercises → calibration formula. |
| B127 | Pre-test adjacency rule nel planner | Il planner non ha logica per evitare finger/hangboard exercises il giorno prima di finger test sessions. Serve un guard in planner_v2 che, quando il giorno N+1 ha una test session con domain finger_*, il giorno N escluda sessioni con finger work intenso (finger_maintenance, finger_max_strength templates). Scoperto in D126 audit. Risk: HIGH (planner). |
| B133c | Multiple other_sport same day | Data model supporta solo 1 other_activity per giorno (campo booleano). Per loggare 2 sport diversi nello stesso giorno serve `other_activities: []` array. Deferred post-launch. Discovered: B133 audit. |

---

## Future — Educational content (methodology explanations)

Two-layer system: detailed reference doc (`docs/training_methodology_explained.md`) + condensed UI cards in Plan page.

**Content covers:** 5 macrocycle phases (why each phase, physiology, what you'll do, how you'll feel), DUP vs linear periodization, feedback loop mechanics, deload science, exercise ordering logic (e.g. hangboard before climbing).

| Step | Effort | Dettaglio |
|------|--------|-----------|
| 1. Reference doc | M | Scrivere `docs/training_methodology_explained.md` — no code, usa letteratura esistente |
| 2. API endpoints | S | Endpoint per servire il contenuto al frontend |
| 3. UI cards in Plan page | M | Card espandibili sotto ogni fase + sezione "Why this plan" |
| 4. LLM Coach context | — | Il doc diventa contesto nel system prompt del Coach (Phase 3.5) |

**Dipendenze:** Step 1 non ha dipendenze. UI (Step 3) dipende dal doc. LLM Coach (Step 4) usa il doc come system prompt context.

---

## Future — Outdoor redesign

> Consolida e sostituisce: B68, B69, B70, B72, B73

Il flusso outdoor attuale è un log passivo post-sessione. Manca una sessione live, il load non è calcolato, e lo storico è minimale. Questo redesign copre tutto il ciclo outdoor.

| # | Area | Effort | Dettaglio |
|---|------|--------|-----------|
| 1 | Guided outdoor session mode | L | Start/Stop con timer, log vie inline (nome/grado + stile onsight/flash/redpoint/project + tentativi + effort), summary a fine sessione |
| 2 | Load calculation | M | Formula: `n_routes × grade_weight × style_modifier × effort_modifier × duration_factor`. Il load outdoor entra nel totale settimanale |
| 3 | Ripple effect | M | Outdoor load influenza la pianificazione del giorno dopo (ex-B70) |
| 4 | Done tracking | S | Sessione outdoor conta come "giorno fatto" nell'aderenza settimanale (ex-B69) |
| 5 | History/stats UI | M | Pagina /outdoor con breakdown per spot: sessioni, grado max, distribuzione gradi, % onsight/flash/sent (ex-B72) |
| 6 | Outdoor spots in onboarding | S | Raccogliere spot durante onboarding, non solo post-setup (ex-B73) |

**Prerequisito da verificare:** quando un giorno ha `location: "outdoor"`, il planner NON deve pianificare sessioni indoor — il giorno appare come "Outdoor day" senza sessioni risolte.

**Moduli impattati:** planner (slot blocking), guided session (nuovo mode), feedback/adaptation (load), reports (aderenza + load), UI (nuova pagina + flusso inline).

**Priorità:** dopo B38, B48, B37.

---

## Future — Social Session (fun bouldering / lead con amici)

> Origine: sessione reale 2026-03-14 (Blocschokolade, Trier)

Sessione ricreativa con amici: struttura leggera, giochi climbing, load ridotto. L'obiettivo è divertirsi senza compromettere il piano di allenamento.

**Principi:** intensità moderata (RPE 5-6), durata 1.5-2h, load_score ×0.5 rispetto a sessione standard. Nessun aggiornamento working_loads. Conta come "giorno fatto" per aderenza.

| # | Area | Effort | Dettaglio |
|---|------|--------|-----------|
| 1 | Game catalog JSON | S | `games_v1.json`: ~10 giochi (Add-On, Elimination, Silent Feet, Stick Game, Boulder Golf, Speed Race, Twister, Traverse Marathon, Stoplight, No-Feet). Per ogni gioco: regole, training_value, intensità, durata, rischio injury, fase_ideale. |
| 2 | Purpose selector UI | S | Pill buttons per scopo: Tecnica, Forza giocosa, Endurance, Creatività, Puro divertimento, Esplorazione. 1-3 selezionabili. Il sistema suggerisce 3-4 giochi dal catalogo in base a scopo + fase macrociclo. |
| 3 | Game card UI | M | Card swipeable per ogni gioco suggerito: regole sintetiche, training value, timer opzionale. Swipe per cambiare gioco (1 tap). Regole visibili inline. |
| 4 | Social session log | S | `POST /api/social-session`: durata, n° problemi, gradi, games_played[], fun_rating (1-5), participants[], notes. Load calcolato con social_modifier=0.5. |
| 5 | Planner integration | S | Social session sostituisce sessione pianificata. Load ridotto → no recovery extra. Appare in weekly view con badge 🎉 e colore viola. |
| 6 | Vocabulary update | XS | Aggiungere `session_mode` enum (training/social/competition) a vocabulary_v1.md §2.14. |

**Prerequisiti:** Nessuna dipendenza P2. Implementabile prima di Supabase/Clerk.

**Varianti future:** Social Lead (palestre con corde), Outdoor social, rating giochi per preferenze, multiplayer log.

**Effort totale stimato:** M-L (catalogo S + backend S + frontend M + integration S)

---

## Future — Evolution (Phase 4+)

- **UI-25 — Test Maxes & Loads panel (Plan tab)**: Collapsible card: test history timeline, benchmark comparison, exercise loads list
- **Multi-goal support**: boulder, all-round, outdoor_season goal types (boulder macrocycle already exists via B91)
- **Annual report**: year-end training summary and progression analysis
- **Multi-macrocycle periodization**: seasonal planning across multiple cycles
- **Notifications/reminders**: push notifications for sessions, test reminders, weekly confirmation
- **Season reset**: partial re-onboarding preserving historical logs, archive radar profiles as seasonal baselines
- **Gym preferences**: prefer specific gym for specific day (e.g. "BKL on Mondays")
- **Crowdsourced gym DB**: utenti condividono le proprie palestre (nome, equipment, location). Nuovi utenti cercano palestre vicine in onboarding → setup immediato. Richiede: tabella `shared_gyms` in Supabase, flag "share this gym", endpoint ricerca per nome/zona, deduplicazione fuzzy (nome + coordinate GPS). Utile solo con massa critica utenti.

---

## Backlog / exploration

Items from audits and brainstorming. Not committed to any timeline.

| Theme | Detail | Origin |
|-------|--------|--------|
| Additional test assessments | Objective tests for technique (route-reading score) and endurance (continuous climbing time) to reduce proxy/self-eval dependency | audit_post_fix |
| Additional assessment dimensions | Mobility/flexibility, mental game, contact strength as separate axes | audit_post_fix |
| Deload vs literature | Compare deload structure with Hörst, Lattice, Eva López — may be too light | audit_post_fix |
| Bouldering discipline expansion | Boulder macrocycle exists (B91), but lead-specific features may need boulder equivalents | memory |
| Dynamic background imagery | Pool di immagini climbing bilanciate per genere (uomini + donne). Variabili per fase del giorno (mattina/pomeriggio/sera) e potenzialmente meteo (indoor se pioggia, outdoor se sole — richiede API meteo). Midjourney v6 photorealistic, dark background. | memory + roadmap discussion |
| Liability disclaimer framework | Template disclaimer per contenuti health-adjacent (nutrizione, recupero). Necessario prima di attivare nutrition hints nel Coach | roadmap discussion |
| Exercise catalog audit v2 | Nuovo audit esercizi contro letteratura espansa e feedback beta. Identificare gap emersi dall'uso reale (153 esercizi attuali). Tipo C. | roadmap discussion |
| Technique drills from book | Scannerizzare il libro di Daniele sui drill tecnici, estrarre drill, mappare su exercise schema, aggiungere al catalogo. Attualmente ~5-6 drill tecnici, potenziale raddoppio. Tipo C. | roadmap discussion |
| ~~Quotes pool expansion~~ | ✅ Done. Pool espanso da 200 → 232 citazioni. Aggiunte 32 quote: 16 climber (Güllich, Sharma, Caldwell, Honnold, ecc.), 3 athlete (Ali, Jordan, Mandela), 1 philosophy (Nietzsche), 1 popular (proverbio cinese), 8 community/humor, 3 coach. Aggiunto source_type "community". | 2026-03-14 |
| Mega brief deferred — D10 | Overcoming isometric pull exercise. Requires pin/strap equipment not in vocabulary. | mega brief Session 2 |
| Mega brief deferred — D37 | Core activation drills from Matros (8 exercises: tic tac toe, diagonal, freeze wall, etc.). Post-launch catalog enrichment. | mega brief Session 3 |
| Mega brief deferred — D50 | Three named repeater protocols (López/Anderson/Hörst) with level-based selection logic in resolver. | mega brief Session 2 |
| Mega brief deferred — D72 | grip_type field on all hangboard exercises + open-hand default + full_crimp validation block. Structural change. | mega brief Session 2 |

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
| 4b: Guided session + beta | 2026-03 | Step-by-step timer, settings editors, dirty-state, recovery codes |
