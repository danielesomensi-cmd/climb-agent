# climb-agent — Active Roadmap

> Last updated: 2026-03-08
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Priority 1 — Stability and bug fixes

Open items that affect production reliability or core UX.

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| ~~B99~~ | ~~Test week crashata~~ | ~~L~~ | Done: test_week_mode eliminato, onboarding genera sempre macrociclo con estimate_missing_baselines() + inject_tests in Pass 3. |
| ~~B100~~ | ~~Piano parte nel passato~~ | ~~M~~ | Done: this_monday() → next_monday() in onboarding. Piano parte sempre dal prossimo lunedì. |
| ~~B101~~ | ~~Test week ignora gym~~ | ~~M~~ | Non era un bug: planner rispetta gym_id da availability. 5 test di conferma aggiunti. |
| ~~B102~~ | ~~Finger mancante dalle zone infortuni~~ | ~~M~~ | Done: `finger → finger_sensitive` mapping, 11 esercizi marcati, 2 esercizi `prehab_finger` creati (finger_extensor_band, finger_tendon_glides). |
| B103 | Gym equipment: nessun preset alla creazione | S | Preselezionare default comuni (gym_boulder, hangboard, pullup_bar). Utente toglie ciò che manca. |
| B104 | Board mancanti + other equipment | S | Aggiungere `board_tension` e `board_other` al vocabulary — trattati come `board_kilter` (stessi esercizi). Resolver: `equipment_required_any` include tutti i board type. Aggiungere campo `equipment_other` generico (free text, non usato dal motore). |
| B105 | Gym lookup disallineato (state.gyms vs state.equipment.gyms) | M | Dati gym in `state["equipment"]["gyms"]` ma alcuni consumer cercano `state["gyms"]`. Mappare e allineare tutti i punti. |
| ~~B48~~ | ~~Edit single session (multi-session day)~~ | ~~M~~ | Done: `session_index` param in override — replaces only targeted session, others untouched. |
| ~~B37~~ | ~~Add exercise to existing session~~ | ~~M~~ | Done: `POST /api/session/add-exercise` — appends exercise, recalculates load score. |
| ~~B38~~ | ~~Injuries filter (contraindications)~~ | ~~M~~ | Done: 3-level severity system (monitor/active/severe) in resolver. |
| ~~UI-9~~ | ~~Limitation filtering in resolver~~ | ~~M~~ | Done: integrated in B38. Frontend severity picker pending (phase 2). |
| B42 | Sunday reminder — confirm next week availability | S | Weekly push/banner asking user to confirm next week's schedule. From beta feedback (FB-3). |
| UI-25 | Test Maxes & Loads panel (Plan tab) | L | Collapsible card: test history timeline, benchmark comparison, exercise loads list. See ROADMAP_v2.md §9.5 for full spec. |
| FR-4 | Outdoor vs gym slot priority preference | S | When both outdoor and gym available same day, user sets preference (outdoor-first / gym-first / alternate). See ROADMAP_v2.md §9.3-9.4. |
| B113 | AddExerciseDialog: lista incompleta + nessuna descrizione | S | getExercises() potrebbe non restituire tutti i 153 esercizi. Ogni item deve mostrare anche la descrizione breve dal catalogo. Prima cosa domani. |

---

## Priority 1b — Beta feedback (Christie, 2026-03-07)

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| ~~B106~~ | ~~Loading pin alias (v1)~~ | ~~M~~ | Done: alias `loading_pin→hangboard` nel resolver + vocabulary + UI. v2 (B109): gestione unilaterale, doppio tempo. |
| ~~B107~~ | ~~"Other" per injuries~~ | ~~S~~ | Done: "Other" aggiunto come zona in onboarding + settings. Notes field cattura dettagli. Zero effetto motore. |
| B108 | Outdoor tooltip in onboarding | S | Non aggiungere outdoor in onboarding (spontaneo, dipende da meteo). Tooltip: "You can add outdoor days in your weekly plan." |
| B109 | Loading pin: esercizi one-arm | M | Esercizi specifici per loading pin (one-arm hang progressions). Dipende da B106. |

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
| ~~B110~~ | ~~Fix sync_status.py endpoint count~~ | ~~S~~ | Done: risolto implicitamente con rimozione 2 endpoint test-week. Count 37 ora corretto. |
| UI-26 | Session card: ⋯ menu + Add Exercise | M | Phase A done: ⋯ button → bottom sheet (Drawer/vaul) con azioni contestuali, AddExerciseDialog con ricerca catalogo + form prescrizione. Phase B pending: Modify session, Modify outdoor. |

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

---

## Future — Engine improvements

| ID | Title | Notes |
|----|-------|-------|
| ~~B37~~ | ~~Add exercise to existing session~~ | Done (P1). |
| ~~B38~~ | ~~Injuries filter (contraindications)~~ | Done (P1). Frontend severity picker + settings UI pending. |
| — | Override intensity cap warning | Warn when user overrides with session above current phase intensity cap. |
| — | P1 ranking in resolver | Recency, intensity, and fatigue-based exercise prioritization. |
| — | Advanced adaptivity | Readiness score, overreach detection, plateau detection (DESIGN_DOC §4.4 spec). |
| B105 | Gym lookup disallineato | `state["equipment"]["gyms"]` vs `state["gyms"]` — mappare tutti i consumer e unificare |
| B112 | Equipment filter in Add Exercise | AddExerciseDialog shows all 153 exercises regardless of session location/equipment. Must filter by required_equipment vs available equipment (gym or home). Frontend: hide or gray out incompatible exercises with "Missing: X" label. Backend: validate equipment_required on add-exercise endpoint. This is a core engine principle — equipment compatibility is non-negotiable. Depends on audit_location_equipment.md. |

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

- **Multi-goal support**: boulder, all-round, outdoor_season goal types (boulder macrocycle already exists via B91)
- **Annual report**: year-end training summary and progression analysis
- **Multi-macrocycle periodization**: seasonal planning across multiple cycles
- **Notifications/reminders**: push notifications for sessions, test reminders, weekly confirmation
- **Season reset**: partial re-onboarding preserving historical logs, archive radar profiles as seasonal baselines
- **Gym preferences**: prefer specific gym for specific day (e.g. "BKL on Mondays")

---

## Backlog / exploration

Items from audits and brainstorming. Not committed to any timeline.

| Theme | Detail | Origin |
|-------|--------|--------|
| Additional test assessments | Objective tests for technique (route-reading score) and endurance (continuous climbing time) to reduce proxy/self-eval dependency | audit_post_fix |
| Additional assessment dimensions | Mobility/flexibility, mental game, contact strength as separate axes | audit_post_fix |
| Deload vs literature | Compare deload structure with Hörst, Lattice, Eva López — may be too light | audit_post_fix |
| Bouldering discipline expansion | Boulder macrocycle exists (B91), but lead-specific features may need boulder equivalents | memory |
| Midjourney imagery | Photorealistic climbing images for UI (dark background, Midjourney v6) | memory |

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
