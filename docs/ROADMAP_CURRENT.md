# climb-agent — Active Roadmap

> Last updated: 2026-03-12
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Priority 1 — Stability and bug fixes

Open items that affect production reliability or core UX.

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| ~~B115~~ | ~~Edit outdoor session~~ | ~~M~~ | Done: `PUT /api/outdoor/log` (update JSONL + state.outdoor_log), `GET /api/outdoor/log/{date}` (singola entry). OutdoorLogForm con `initialData` prop per edit mode. Bottone Edit (Pencil) su outdoor card completata in week + today. 11 test. |
| ~~B116~~ | ~~Persistent outdoor log~~ | ~~M~~ | Done: `state.outdoor_log[]` append su `complete_outdoor`, remove su `undo_outdoor`. Entry: date, spot_name, spot_id, discipline, load_score, completed_at. 2 test. |
| ~~B117~~ | ~~Persistent completion log~~ | ~~M~~ | Done: `state.session_completion_log[]` append su `mark_done`/`mark_skipped`, remove su `mark_planned`. Feedback router attacca difficulty + exercise_count. 4 test. |
| ~~B99~~ | ~~Test week crashata~~ | ~~L~~ | Done: test_week_mode eliminato, onboarding genera sempre macrociclo con estimate_missing_baselines() + inject_tests in Pass 3. |
| ~~B100~~ | ~~Piano parte nel passato~~ | ~~M~~ | Done: this_monday() → next_monday() in onboarding. Piano parte sempre dal prossimo lunedì. |
| ~~B101~~ | ~~Test week ignora gym~~ | ~~M~~ | Non era un bug: planner rispetta gym_id da availability. 5 test di conferma aggiunti. |
| ~~B102~~ | ~~Finger mancante dalle zone infortuni~~ | ~~M~~ | Done: `finger → finger_sensitive` mapping, 11 esercizi marcati, 2 esercizi `prehab_finger` creati (finger_extensor_band, finger_tendon_glides). |
| ~~B103~~ | ~~Gym equipment: nessun preset alla creazione~~ | ~~S~~ | Done: 3 quick-fill pill (Boulder/Lead/Fitness) sopra checkbox gym. Replace mode (non additive). Riordinati EQUIPMENT_GYM (20 item, raggruppati) e EQUIPMENT_HOME (loading_pin dopo hangboard). Applicato a settings + onboarding. |
| ~~B104~~ | ~~Board mancanti + other equipment~~ | ~~S~~ | Done: `board_other` aggiunto a vocabulary, EQUIPMENT_GYM, 15 esercizi (equipment_required_any), SURFACE_PRIORITY. Fix bonus: board_moonboard mancava da SURFACE_PRIORITY. `equipment_other` free-text in gym + home (settings + onboarding), ignorato dal motore. |
| ~~B105~~ | ~~Gym lookup disallineato (state.gyms vs state.equipment.gyms)~~ | ~~M~~ | Non riproducibile: audit completo conferma che tutti i reader e writer usano `state["equipment"]["gyms"]`. Nessun accesso a `state["gyms"]` trovato. Probabilmente risolto implicitamente con B88/B101. |
| ~~B48~~ | ~~Edit single session (multi-session day)~~ | ~~M~~ | Done: `session_index` param in override — replaces only targeted session, others untouched. |
| ~~B37~~ | ~~Add exercise to existing session~~ | ~~M~~ | Done: `POST /api/session/add-exercise` — appends exercise, recalculates load score. |
| ~~B38~~ | ~~Injuries filter (contraindications)~~ | ~~M~~ | Done: 3-level severity system (monitor/active/severe) in resolver. |
| ~~UI-9~~ | ~~Limitation filtering in resolver~~ | ~~M~~ | Done: integrated in B38. Frontend severity picker pending (phase 2). |
| ~~B42~~ | ~~Sunday reminder — confirm next week availability~~ | ~~L~~ | Done: Weekly Check-in flow (Sunday + Monday morning grace period). Bottom sheet with 7-day editor: toggle available/rest, switch location (gym/home/outdoor), change gym. Override saved as `weekly_overrides` in user_state (temporary layer, never modifies settings). Planner merges override before planning. 3 new endpoints (GET/PUT/DELETE `/api/weekly-override/{week_start}`). Absorbs FR-4. 11 tests. |
| ~~FR-4~~ | ~~Outdoor vs gym slot priority preference~~ | ~~—~~ | Archived — absorbed by B42 weekly check-in. User decides day-by-day in the check-in instead of needing a global preference rule. |
| ~~B113~~ | ~~AddExerciseDialog: lista incompleta + nessuna descrizione~~ | ~~S~~ | Done: rimosso `slice(0,30)`, tutti i 155 esercizi visibili in lista scrollabile. Fix ricerca domain (array, non stringa). Aggiunta descrizione (troncata 1 riga) + category + equipment sotto ogni nome. Ricerca estesa a description e category. |
| ~~B114~~ | ~~Regenerate Plan: past days protection + smart popup~~ | ~~M~~ | Done: `preserve_before` param in `GET /api/week`, `merge_prev_week_sessions` ora matcha per data (non weekday), giorni passati copiati wholesale, oggi con sessioni completate protetto. Frontend: `RegeneratePlanSheet` bottom sheet con 3 opzioni (Today/Tomorrow/Next Monday). |
| ~~B118~~ | ~~P0: Equipment regen resetta macrociclo a week 1~~ | ~~S~~ | Done: `handleRegenSheetConfirm()` chiamava `generateMacrocycle()` senza `from_phase`, causando full regen (start_date=this_monday). Fix: passa `from_phase="current"` per tutti i path tranne Danger Zone restart. Audit: `plan/page.tsx` già corretto, `onboarding.py` correttamente full. 6 test + restore script. |
| ~~B119~~ | ~~P0: start_date must always be a Monday~~ | ~~S~~ | Done: `ensure_monday()` in `deps.py` auto-corrects non-Monday dates to previous Monday. Applied at all setters: state PUT, macrocycle generate (full+incremental), start-week shift, engine `generate_macrocycle()`. 15 new tests, zero regressions. Invariant documented in vocabulary_v1.md §5.5.1. Production patched to 2026-02-23. |
| ~~B121~~ | ~~Planner non riempie tutti gli slot disponibili~~ | ~~M~~ | Done: Pass 2.2 in planner_v2 — quando un giorno ha più slot (es. lunch+evening) e `target_days > sessions piazzate`, riempie gli slot extra con sessioni non-hard. `_find_best_slot` ora accetta `occupied_slots` per evitare conflitti. 8 nuovi test. |

---

## Priority 1b — Beta feedback (Christie, 2026-03-07)

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| ~~B106~~ | ~~Loading pin alias (v1)~~ | ~~M~~ | Done: alias `loading_pin→hangboard` nel resolver + vocabulary + UI. v2 (B109): gestione unilaterale, doppio tempo. |
| ~~B107~~ | ~~"Other" per injuries~~ | ~~S~~ | Done: "Other" aggiunto come zona in onboarding + settings. Notes field cattura dettagli. Zero effetto motore. |
| ~~B108~~ | ~~Outdoor tooltip in onboarding~~ | ~~S~~ | Done: CardDescription nella pagina availability: "Outdoor days can be added later in your weekly plan based on weather and season." |
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

## Priority 3 — UI polish (parallel with P2)

Items that affect first impression for paying users.

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B40 | Branch develop/main workflow | S | Set up develop branch for staging, main for production deploys. |
| B109 | Loading pin: esercizi one-arm | M | Esercizi specifici per loading pin (one-arm hang progressions). Dipende da B106. |
| ~~B110~~ | ~~Fix sync_status.py endpoint count~~ | ~~S~~ | Done: risolto implicitamente con rimozione 2 endpoint test-week. Count 39 (38 router + 1 health) dopo B-115. |
| ~~UI-26~~ | ~~Session card: ⋯ menu + Add Exercise~~ | ~~M~~ | Done: Phase A: ⋯ button → bottom sheet con Add Exercise, Move, Remove, Undo. Phase B: "Modify session" nel menu ⋯ (indoor, non finalized) → apre ReplanDialog con session_index. "Edit outdoor" già presente come bottone su outdoor card completata. |

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
| ~~B37~~ | ~~Add exercise to existing session~~ | Done (P1). |
| ~~B38~~ | ~~Injuries filter (contraindications)~~ | Done (P1). Frontend severity picker + settings UI pending. |
| — | Override intensity cap warning | Warn when user overrides with session above current phase intensity cap. |
| — | P1 ranking in resolver | Recency, intensity, and fatigue-based exercise prioritization. |
| — | Advanced adaptivity | Readiness score, overreach detection, plateau detection (DESIGN_DOC §4.4 spec). |
| ~~B105~~ | ~~Gym lookup disallineato~~ | Chiuso: nessun mismatch trovato (audit 2026-03-10). |
| ~~B112~~ | ~~Equipment filter in Add Exercise~~ | Done: frontend-only equipment filtering in AddExerciseDialog. `expandEquipment()` replicates backend implicit equipment expansion (floor, weight subtypes, loading_pin→hangboard, gym→pullup_bar). `isExerciseCompatible()` applies AND/OR equipment checks matching resolver Stage 2. Toggle "Show all exercises" reveals hidden items with "Missing equipment" badge. Equipment context passed via props: page→DayCard→SessionCard→dialog. Backend unchanged. |

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
| Quotes pool expansion | Espandere il pool di citazioni motivazionali. Audit quantità attuale, aggiungere citazioni da letteratura climbing + atleti. Task piccolo, alto impatto percepito. | roadmap discussion |

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
