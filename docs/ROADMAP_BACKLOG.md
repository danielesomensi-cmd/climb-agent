# climb-agent — Unscheduled Backlog

> **Questo file non è lavoro preso in carico.** Sono idee, esplorazioni e debito
> tecnico noto ma senza un momento: nessuna data, nessun brief assegnato, nessuna
> priorità operativa. Vivono qui perché dimenticarle sarebbe una perdita, non
> perché siano in coda.
>
> **Regola di promozione:** un item passa in `docs/ROADMAP_CURRENT.md` **solo**
> quando viene schedulato — cioè quando riceve una priorità e qualcuno decide che
> si fa. Il percorso inverso (da attivo a qui) è altrettanto legittimo: se una
> voce resta ferma senza che nessuno la pianifichi, appartiene a questo file.
>
> **Nota per `repo_hygiene.py`:** lo script controlla la lunghezza di
> `ROADMAP_CURRENT.md` soltanto. Questo file non conta contro quel limite ed è
> libero di crescere — è un archivio di idee, non una coda di lavoro.
>
> Separato da `ROADMAP_CURRENT.md` in B320 (2026-08-02): la roadmap attiva aveva
> 959 righe contro un target di 350, e il grosso non era debito arretrato ma
> backlog esplorativo che nessuno aveva intenzione di affrontare a breve. Testo
> spostato **verbatim** — ID, priorità e note sono quelli di prima.
>
> Storia archiviata: `docs/ROADMAP_v2.md` · Stato progetto: `PROJECT_BRIEF.md`

---

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
> `docs/research_kb/horst_integration_audit.md` for enrichment material. Many deferred decisions have ready-to-use content.**

### Open KB Research Items

| Item | Status | Where |
|------|--------|-------|
| Session 2 patch (4 corrections: D11, D12, D39, D72) | ⏸️ Prepared | KB project memory (not yet a file) |
| D84 pulling strength test (max load review) | ⏸️ Under review | KB project |
| Finger strength test architecture (5s→7s Lattice) | ⏸️ Under review | KB project |
| CUE-02 formalize (forearm stretch → D33 amendment) | 📋 Proposed | `docs/research_kb/horst_integration_audit.md` §6 |
| Coach KB spec: add 8 Hörst coaching cues | 📋 Proposed | `docs/research_kb/horst_integration_audit.md` §5 |
| Decision consolidation: append D84-D91 | 📋 Proposed | `kb_gaps_analysis.md` |
| Topics 05-10 Steps 4-5 (decision specs) | ⏳ Not started | KB project |

### Remaining Books

| Book | Status | Needed for |
|------|--------|-----------|
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

Two-layer system: reference doc (`docs/training_methodology_explained.md` (cancellato — vive solo nella storia git)) + condensed UI cards in Plan page.
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

> Full specifications in `docs/claude_code_mega_brief_v1.md` (cancellato — vive solo nella storia git, `git log --diff-filter=D`). Grouped by theme.

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
| D33 | Dedicated `generate_warmup()` function | M | 5-phase protocol generator. **⚠️ KB: Ch. 6 has warm-up exercises + CUE-02 (no forearm flexor stretch pre-performance). See `docs/research_kb/horst_integration_audit.md` §5-§6.** |
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
| D170 P1-04 | `apply_day_add` non riceve `gyms` — serve refactor di firma. Il path utente principale è coperto dal fix frontend di B173. Spostato qui da P1.26 ([[D269]]). | audit D170 2026-03-31 |
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
