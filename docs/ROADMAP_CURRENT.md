# climb-agent — Active Roadmap

> Last updated: 2026-03-22
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
| 6: Hangboard Logic | D35, D49 | 🟡 Partial | D35 ✅ experience gate (<2yr blocks MaxHangs/MED). Deferred: D49 (method restriction) |
| 7: Endurance & Intervals | D47, D48, D53 | 🟡 Partial | 4x4 esiste. D48 absorbed into process cues (A141). Mancano: varied-intensity |
| 8: Conditioning & Ratio | D51, D54, D58, D59, D73, D78 | 🟡 Partial | face_pull + band_pull_apart + planks. D78 ✅ process cues (A141). Mancano: ratio, technique allocation |
| 9: Periodization & Load | D19-D21, D44, D45, D69-D71 | 🟡 Partial | min_weeks esiste. Mancano: beginner linear, overreach, ACWR, OTS, volume cap |
| 10: Coaching & UX | D17, D29, D30, D41, D64-D67, D75, D77, D79 | 🟡 Partial | D64 ✅ RED-S guardrails. D17 ✅ G-Tox cue (A141). D30 ✅ fall practice drill (A141). Remaining: D29, D41, D65-D67, D75, D77, D79 |

---

## Priority 1 — Stability and bug fixes

All P1 items completed (30 items). See archived history in `docs/ROADMAP_v2.md`.

Recently closed (2026-03-24):
- **A141** — Process cues, phase rationales, fall drill, nav restructure. 25 coaching cues tagged by session type, deterministic selection, banner in guided session. Phase rationales: 6 educational texts in Plan view, expandable 'About this phase' sections. Fall practice drill exercise (D30). Nav: Plan promoted to bottom nav, Tabata → More drawer. Mega brief: D78 ✅, D17 ✅, D30 ✅. 14 new tests (1335 total).
- **A142** — Exercise Detail Preview Sheet. New `ExerciseDetailSheet` component (bottom sheet via vaul Drawer). Tapping any exercise card in Today/Week/Session views opens a read-only sheet showing full prescription (sets/reps/load/rest/tempo), suggested load/grade (bilateral + unilateral), technique cues, notes, equipment, video link, limitation warnings. `rawExercise` optional prop added to `ExerciseCard` — existing rendering unchanged, raw data only feeds the sheet. Wired in `SessionCard` (Today/Week) and `/session/[id]` page. 1 new component (58 total).

Recently closed (2026-03-23):
- **B-SUPP** — Supplementary training via quick-add. `supplementary: true` flag on 5 session JSONs (upper_body_weights, legs_strength, lower_body_gym, heavy_conditioning_gym, pulling_strength_gym). Backend: `_get_supplementary_sessions()` scans catalog, filters by location, returns in `GET /api/replanner/suggest-sessions` response as separate `supplementary` array. Frontend: dedicated "Supplementary training" section in QuickAddDialog with blue accent, equipment-filtered. Removed upper_body_weights/legs_strength from `_ALWAYS_SUGGESTIBLE` (now in dedicated section). 7 new tests (1321 total).
- **A140** — Core Circuit add-on. New activity type in Free Session: guided bodyweight core workout with configurable timer (work/rest/duration). 30 core exercises in frontend catalog organized by movement pattern (anti-extension, anti-rotation, anti-lateral flexion, compression, extension) with mix of dynamic and isometric. Fisher-Yates randomized sequence with no-consecutive-repeat guard. Timer reuses Tabata wall-clock engine (iOS Safari PWA safe). Back/Next buttons to skip/revisit exercises. Work max increased to 180s. Circuit sessions logged in `free_sessions[]` with `surface: "circuit_core"`, `session_mode: "circuit"`. Load score: `completed_exercises × 0.5`. New "Add-ons" divider in Free Session surface list. Backend: `circuit_core` in SURFACES, `circuit` in VALID_SESSION_MODES, circuit-aware finish endpoint, report engine label. Frontend: 4 new components (CircuitSetup, CircuitTimer, CircuitCompletion, circuit-exercises catalog), circuit card with emerald gradient, day-card circuit rendering. Vocabulary §6.9 (circuit surfaces) and §6.10 (session_mode: circuit) added. Exercise images: Gemini AI generation in progress (semi-realistic illustration style, stored in `frontend/public/exercises/core/`). 9 new backend tests.
- **D151** — Load coherence audit & fix. Phase 0 audit found 5 incoherences across 4 session types (engine, free, outdoor, other_activity). Fix 1: `_build_load()` in report_engine now reads `session_load_score` (granular per-exercise fatigue sum) with fallback to `estimated_load_score` (4 fixed buckets). Fix 2: `compute_outdoor_load_score()` rewritten with normalized formula `avg(grade_weight × style_mod) × volume_factor(log5, cap 2.0) × duration_factor`, hard cap at 85 — old formula produced 141 for 8 hard routes. Fix 3: `session_load_score` rescaled ×1.5 (range 12-48 → 18-72) to align with 20-85 AU target. Session router add-exercise aligned. Other_activity load deferred to Load v2. 20 new tests (1307 total).

Recently closed (2026-03-24):
- **D152** — Add Exercise UX audit for duration-based/test exercises. Phase 0 audit verified: (1) backend `session.py` correctly reads `prescription_defaults` and propagates `category`, `attributes`, `load_model`, `unilateral` to manually-added exercises. (2) Frontend Add Exercise dialog shows "1 × max attempt" for test_measurement exercises and "Duration (s)" input for duration-based exercises. (3) `formatPrescription` has fallback for `sets && !reps && !workSeconds` → "N × max". (4) Full test-measurement save chain works end-to-end (guided input → feedback payload → progression baselines). 3 dedicated tests cover defaults merge + field propagation (1338 total).

Recently closed (2026-03-22):
- **B151** — Settings page: loading flash + availability day order + availability save + future week cache invalidation. Four bugs: (A) first load showed "—" — Clerk auth not ready, gate on `useAuth().isLoaded` + `useUserState(enabled)`. (B) Availability days alphabetical → `WEEKDAYS` constant Mon→Sun. (C) Removing days didn't persist — deep-merge `{}` no-op → send `null`. (D) Future weeks kept stale availability — `PUT /api/state` with `availability` key now calls `invalidate_future_week_cache()` to clear cached weeks > current Monday. Current week handled by frontend `getWeek(0, true)`. Past weeks preserved (immutability invariant). 2 new tests (1287 total).
- **D150** — Planner availability compliance audit & fix. Root cause: two bugs combined — (1) Settings `handleSave()` created empty `{}` entries for all 7 weekdays, including untouched days, (2) `_normalize_availability()` treated empty dicts as "all 3 slots fully available in gym+home" (300+ scoring), causing capping to prefer phantom days over real single-slot days. Fix: backend normalizer now treats empty dicts, None, non-dict values, and `_day_meta`-only entries as unavailable; `{"available": True}` without slots → available with home fallback; bare `True` → available home; non-dict types (bool/string/list) → defensive handling, no crash. Frontend `handleSave()` now filters out days with no active slots. 14 new tests (1250 total).
- **D35** — Hangboard experience gates. Users with `climbing_years < 2` blocked from MaxHangs, MED, one-arm hang in resolver (Stage 2e in P0 pipeline). Repeaters, density hangs, warmup always open. Test sessions never blocked. `finger_sensitive` contraindication added to `min_edge_hang` + `one_arm_hang_assisted`. 7 new tests.
- **D64** — RED-S guardrails. Audit: zero weight-loss language in codebase. Removed `body_fat_pct` from frontend (types, onboarding review, context). 5-axis assessment confirmed (no body_composition). Permanent test scans all source files for banned phrases. 3 new tests.
- **B137b** — Resolver homewall equipment equivalence. B137 fixed planner but resolver's `get_location_equipment()` didn't apply homewall→gym_boulder. Boulder Circuit at home resolved with zero climbing exercises. Fix: 2-line addition mirroring planner logic. 5 new tests.
- **B139** — Week navigation picker. "Week X/Y" text tappable → Drawer (bottom sheet) listing all weeks with phase name, past/current/future indicators. Direct navigation to any week in one tap.

Recently closed (2026-03-21):
- **B137** — Homewall users get climbing sessions at home. `_expand_session_locations()` dynamically adds "home" to gym-only boulder sessions when user has homewall (homewall→gym_boulder equivalence). Route sessions correctly excluded. 3 new tests (1223 total).
- **B138** — Test interval 14→42 days (6 weeks). Per Hörst/Lattice/Eva López, neuromuscular adaptations need 4-6 weeks to manifest. `TEST_FRESHNESS_DAYS` updated. Subsumes B128 logic.
- **B136 + B136b** — Test results not visible in Today/Week view. B136: added test results summary (Max Hang kg, Repeater reps, Duration, Hip Flex) in session card header, visible without expanding. B136b: `actual_exercises` was written to `current_week_plan` but not synced to `week_plans` cache — `GET /api/week/0` reads cache first, missed data. Fix: feedback handler writes to both stores.
- **B135** — Settings not showing max hang baseline. D85 introduced `max_hang_20mm_7s_total_kg` key but frontend/assessment still read legacy `5s` key. Fix: dual-write in progression_v1 (both 7s + 5s), fallback reads in assessment_v1, Settings editor, onboarding. Label updated to "7 seconds (MVC-7)".
- **A139** — Session review: show actual logged data for completed sessions. Backend: persist raw `actual_exercises[]` (exercise_feedback_v1) in session slot inside week plan on POST /api/feedback. Data survives week rotation via week_plans{} cache. Frontend: enriched exercise-card with feedback label badges (colored pill instead of dot), load delta (prescribed vs used with green/orange color), test result display (star icon + value), used grade, completed sets count, user notes. Graceful fallback for label-only feedback (FeedbackDialog flow) and old sessions without actual_exercises. 6 new backend tests (1220 total).
- **B139** — Root URL 404 + OG meta tags. Root `/` was blocked by Clerk middleware (`auth.protect()`) causing 404 for unauthenticated users and social crawlers. Fix: added `/` to public routes in middleware. Added Open Graph + Twitter Card meta tags to layout for social link previews (WhatsApp, Telegram, iMessage).

Recently closed (2026-03-25):
- **B155** — Clerk auth race condition: reorder not persisting after refresh + intermittent 422 on first load. Root cause: `_getAuthHeaders()` calls `window.Clerk?.session?.getToken()` which returns undefined if Clerk SDK hasn't loaded yet; `useEffect` fires fetch on mount without waiting. Fix A (primary): gate all page-level data fetches on `useAuth().isLoaded` — applied to today, week, plan, outdoor, reports, free-session, session/[id], onboarding/start-week (8 pages). Fix B (safety net): one-time 401 retry with 500ms delay in `request()` for edge cases where Clerk is still loading. Fix C (cleanup): reverted B153d's 401 guard in `deps.py` that converted retryable 422 into redirect-to-sign-in; kept diagnostic logging on 422 path.
- **B153d** — Exercise reorder: GET /api/week/0 returns 422 after successful reorder. Root cause: Clerk token race condition — if `getToken()` returns null during session refresh, backend receives no auth, loads empty state (macrocycle: null), returns 422. Three fixes: (A) Frontend uses reorder/add/remove response data directly (`onSessionUpdated(updatedWeekPlan)`) instead of full GET reload, eliminating the 422 window. (B) Backend guard in `get_user_id`: returns 401 when Clerk is configured but no auth header is present, preventing silent fallback to legacy bucket — **reverted in B155**. (C) Diagnostic logging on 422 "No macrocycle" path with user_id and state keys.

Recently closed (2026-03-24):
- **B153c** — Exercise reorder persistence audit. Full end-to-end trace confirmed backend is correct (reorder → GET /api/week/0 → order persists). `_user_edited` flag + `_auto_resolve` skip both verified working. Added E2E integration test (onboarding → generate week → reorder → reload → assert order matches). Added diagnostic console.log in frontend handleDragEnd for production debugging. Replaced silent catch blocks with error logging. 1 new test (1356 total).
- **B153b** — Drag reorder not persisting + exercise card layout. Root cause: `GET /api/week/0` calls `_auto_resolve()` which re-resolves planned sessions on every fetch, overwriting user's exercise order. Fix: `_user_edited` flag on sessions modified via add/remove/reorder endpoints; `_auto_resolve` (week.py + replanner.py) skips re-resolution for flagged sessions. Trash icon moved inside exercise card (top-right, absolute positioned) so card takes full width. 3 new tests (1355 total).
- **B153** — Reorder exercises: drag didn't save + drag handle UX unclear. Root cause: `handleDragEnd` used raw instanceIdx as array positions (wrong when block matching reorders), and no optimistic state update caused visual snap-back. Fix: `localOrder` state for optimistic reorder (permutation of server indices), `arrayMove` from @dnd-kit for correct position computation, `reorderPending` flag to block concurrent drags, flat list rendering when user has reordered. Drag handle: 44×44px touch target (Apple HIG), `size-5` icon, elevation + ring during drag. Trash icon: 44×44px target.
- **A153** — Remove + Reorder exercises in resolved sessions. Two new endpoints: `POST /api/session/remove-exercise` (with min-1 guard) and `POST /api/session/reorder-exercises` (valid permutation check). Shared `_assert_session_mutable()` guard (retrofitted on add-exercise too). Frontend: drag-and-drop reorder with @dnd-kit (grip handle + touch/pointer sensors), trash icon per exercise with confirm dialog, reorder safety warning banner. Immutability invariant enforced on all 3 exercise mutation endpoints (409 on done/skipped). 14 new tests.

Recently closed (2026-03-20):
- **A138** — Free session integration. Add-on entry point ("+ Log extra climbing" after completed engine sessions), quick-add entry ("Free climbing session" in QuickAddDialog with purple Grip icon), Today/Week view display (free session cards with surface/preset/climbs/grade/duration), query params support (`?context=add_on&date=`). Report engine: free session load in weekly actual total, free sessions in day-by-day timeline, active days count, training time aggregation with `free_session` source.
- **D134** — Outdoor session persistence audit & fix. Root cause: dual-storage architecture (outdoor_logs table + state.outdoor_log[] summary) with no auth guard on Supabase writes — Clerk token expiry could route data to `__legacy__` bucket, causing 404 on subsequent reads. Fix: auth guard on all Supabase write functions (`_require_user_id`), read-after-write verification for outdoor_logs, frontend read-after-write before `complete_outdoor` event. Recovery script for orphaned `__legacy__` data. 8 new tests (1205 total).
- **A137** — Free climbing session frontend. Full multi-step flow: surface selection (5 surfaces, always all shown, colored gradient cards), optional gym picker (saved gyms + custom text), mode selection (Template/Free), preset picker (phase compatibility badges, computed target grades, rest times). ClimbLogger component: Fontainebleau grade picker (+/- buttons), status selector (Flash/Sent/Attempted with color coding), attempts picker, lead mode (OS/FL/RP/PROJ + Topped/Fell), auto rest timer (template mode, wall-clock based, voice cues), manual rest timer (free mode), climb history list, progress counter, elapsed time. Session summary: stats card, grade distribution bar chart, feel selector (Easy/Good/Hard), notes. 5 new components, 6 API integrations.
- **A136** — Free climbing session backend. Data model (`free_sessions[]` in user_state), 6 API endpoints (surfaces, presets, start, log-climb, finish, history), preset catalog (4 boulder + 3 lead), phase tips (template + free mode × 5 phases), load calculation (v1 formula: relative difficulty × status weight × attempt modifier), grade utilities (Fontainebleau 4A-8C+), context-aware replacement (marks planned session as skipped). 72 new tests. Vocabulary §6 updated.
- **A135** — Tabata timer tab. New `/tabata` page with fully configurable interval timer (7 parameters: prepare, work, rest, cycles, sets, set rest, cool down). Setup screen with +/- buttons + tap-to-edit numeric input. Running timer with wall-clock engine (iOS Safari PWA safe), animated SVG progress ring, phase-colored backgrounds (teal work, blue rest, grey prepare/cooldown), 3-2-1 countdown beeps, voice encouragement (30% random phrases from A123 pool). Expand mode (fullscreen 120px font). Completion screen with stats grid + restart. Bottom nav restructured: Today | Week | Tabata | Free | More (drawer with Plan, What's next, Settings, Outdoor, Reports). Free Session placeholder page added.

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

### ~~B128 — Test duplicati dopo rigenerazione macrociclo~~ ✅

**Priority:** P1b
**Status:** Closed (2026-03-21). Updated by B138 (2026-03-21): interval 14→42 days.

**Fix:** Pass 3 in planner_v2 now checks `recent_test_dates` (finger, repeater, pulling) before scheduling each test. Tests completed within `TEST_FRESHNESS_DAYS` (42 days = 6 weeks, per Hörst/Lattice/Eva López) of week start are skipped. Granular per-test: if finger is fresh but repeater is stale, only repeater is scheduled. New parameter `recent_test_dates: Dict[str, str]` on `generate_phase_week()`. Call site (week.py) extracts dates from `baselines.hangboard[0].updated_at`, `tests.repeater_strength_endurance[-1].date`, `baselines.pulling.updated_at`. Inline freshness check in planner — zero coupling with progression_v1.

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

## Priority 2.25 — Code Quality & Hardening

> Origin: Full codebase audit con Agent Teams (2026-03-21)
> Scope: backend engine + frontend React — safety, error handling, refactoring

### R140 — Backend Error Handling Hardening

**Priority:** P2.25 (high — safety first)
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- Sostituire tutti i `except Exception` silenziosi in `closed_loop_v1.py` con logging esplicito
- Aggiungere validazione su `perceived_difficulty` (range 1-5) in `closed_loop_v1.py:180-195`
- Aggiungere validazione input (formato date, struttura user_state, validità phase) sulle funzioni pubbliche di: `planner_v2.py`, `resolve_session.py`, `macrocycle_v1.py`, `replanner_v1.py`
- Sostituire i global mutable state (`_CATALOG_CACHE`, `_cached_quotes`) con `@lru_cache`

**Moduli impattati:** closed_loop_v1, planner_v2, resolve_session, macrocycle_v1, replanner_v1, progression_v1, quotes_engine
**Rischio:** MEDIO — tocca moduli core ma i cambiamenti sono difensivi (aggiungono validazione, non cambiano logica)

### R141 — Frontend Error Handling Hardening

**Priority:** P2.25 (high — safety first)
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- Sostituire tutti i `.catch(() => {})` silenziosi (~20 istanze) con error toast per l'utente
- Aggiungere validazione Zod su `JSON.parse` del localStorage nella guided session
- Aggiungere `AbortController` sulla navigazione week per evitare race condition con click rapidi
- Aggiungere stati loading/error consistenti su `today/`, `plan/`, `outdoor/` pages

**Moduli impattati:** today/page.tsx, week/page.tsx, guided/page.tsx, plan/page.tsx, outdoor/page.tsx, lib/api.ts
**Rischio:** BASSO — cambiamenti UX difensivi, non toccano logica engine

### R142 — Magic Numbers Extraction

**Priority:** P2.25 (high)
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- Estrarre tutti i magic numbers da `progression_v1.py` (0.05, 0.85, 1.15, 3, 0.7) in named constants o file di configurazione
- Spostare le tabelle grade-to-score e axis weights da `assessment_v1.py:45-90` in un file JSON catalog

**Moduli impattati:** progression_v1, assessment_v1
**Rischio:** BASSO — estrazione costanti, nessun cambio logica

---

## Priority 2.5 — Catalog audit

### ~~B129 — Verificare domain di threshold_climbing nel catalogo~~ ✅

**Priority:** P2.5 (catalog audit)
**Status:** Closed (2026-03-19)
**Discovered:** 2026-03-18 durante A121

**Fix:** domain cambiato da `aerobic_capacity` → `power_endurance` in `exercises.json`. Filtro sessione `route_endurance_gym.json` aggiornato di conseguenza. Sort category ora correttamente derivata come `pe_intervals` (priority 6 in Base) anziché `aerobic_pure` (priority 2). Commit: `5ab1100`.

### C130 — Audit sistematico domain/intensity/pattern di tutti gli esercizi

**Priority:** P2.5
**Status:** Partially closed (2026-03-22, D-CAT + D-ORPHAN)
**Discovered:** 2026-03-18 (durante A121 + knowledge base review)
**Type:** C (catalog)

**Completato (D-CAT audit, 2026-03-22):**
- Audit esaustivo di tutti i 178 esercizi: domain, intensity, pattern, grade_offset
- 5 intensity mismatch corretti: `aerobic_pyramid_intervals` (medium→low), `campus_laddering_feet_on` (medium→high), `critical_force_test` (high→medium), `one_on_one_off_intervals` (medium→low), `threshold_long_intervals` (medium→low)
- 4 session filter corretti: `boulder_circuit_gym` (volume_climbing→power_endurance), `upper_body_weights` (push_horizontal→push ×2), `core_training` (lateral_flexion→anti_lateral_flexion)
- 9 sessioni orfane triagate: 4 integrate nel planner, 5 classificate come supplementary
- Schema drift rimosso (version: v1) da 4 sessioni
- Deload pool: aggiunto `finger_aerobic_base` + `deload_recovery` (colma gap hangboard)
- Report completo: `audit_catalog_report.md`

**Ancora aperto:**
- ~33 pattern/domain borderline cases (multi-domain exercises, vocabulary gaps) — richiedono decisione design, non fix meccanici
- Vocabulary §2.4 reference table incompleta per patterns come carry, locomotion, self_massage

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

### Free Session UI grouping — collapse climbing surfaces

**Priority:** P2.5 (post-launch polish)
**Status:** Open — design decided
**Type:** A (frontend only)

**Context:** Free Session page currently shows 5 climbing surface cards + Add-ons divider + circuit cards = a lot of scrolling. Climbing surfaces should be grouped under a single expandable "Climbing" card.

**Design:**
- Single "Climbing" card with tap-to-expand behavior
- Expands to show: Gym Boulder, Kilter Board, MoonBoard, Other Board, Lead/Top-rope
- Add-ons section stays below, always visible
- Collapsed state shows just the Climbing card + Add-ons

**Effort:** S (frontend only, no backend changes)

### Core Circuit exercise images — Gemini AI generation

**Priority:** P2.5 (ongoing, non-blocking)
**Status:** In progress — 4/30 done
**Type:** C (content)

**Context:** Semi-realistic fitness illustrations generated via Google Gemini AI. Two positions (A/B) per exercise, consistent style (fit woman, red/coral sports bra, gray leggings, white background). Stored in `frontend/public/exercises/core/`. Frontend shows images in CircuitTimer when available, graceful fallback to text-only when not.

**Process:** Reference image from Google Images + Gemini prompt. Guide document prepared with all 30 prompts.

**Remaining:** 26 of 30 exercises need images. Non-blocking — circuit works fine with text descriptions only.

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

### ~~B-SUPP — Supplementary training via quick-add~~ ✅

**Priority:** P2.5 (post-audit, pre-launch nice-to-have)
**Status:** Closed (2026-03-23)
**Origin:** D-CAT audit (9 orphan sessions) + B83 (supplementary work request) + B74 (rest day activities)
**Discovered:** 2026-03-22 (D-ORPHAN triage)
**Type:** B (feature)

**Context:** Users want to add non-climbing supplementary work (legs, upper body, core, conditioning) after climbing sessions or on rest days. 5 orphan sessions exist for this purpose but are invisible to users because they're not in any phase pool and `suggest-sessions` only returns phase-compatible climbing sessions.

**Triage result (D-ORPHAN Phase 0):**
- INTEGRATE into planner (4): `deload_recovery`, `finger_aerobic_base`, `finger_endurance_short`, `finger_maintenance_gym` — ✅ Done (2026-03-22)
- KEEP as supplementary (5): `heavy_conditioning_gym`, `legs_strength`, `lower_body_gym`, `pulling_strength_gym`, `upper_body_weights`

**Scope:**
1. **Backend:** Expand `GET /api/replanner/suggest-sessions` response with `supplementary` section
   - Returns two sections: `climbing` (existing) + `supplementary` (new)
   - Supplementary sessions: phase-agnostic, filtered by user equipment/location only
   - Tag: `supplementary: true` field on session JSON
   - Load modifier: `supplementary_modifier = 0.5` (50% impact on weekly load)
2. **Frontend:** Expand QuickAddDialog with supplementary category
   - Section "💪 Supplementary Training" between climbing suggestions and free climbing entry
   - Shows: Upper Body, Core, Legs (Home), Legs (Gym), Heavy Conditioning, Pulling
3. **Load scoring:** Supplementary sessions count at 0.5× for weekly load, count as "active day" for adherence, appear in weekly report under separate section
4. **No adaptation trigger:** Supplementary sessions do NOT trigger replanning or macrocycle adaptation

**5 supplementary sessions (all already exist as JSON):**
- `upper_body_weights` — Push antagonist work (home, no equipment needed)
- `legs_strength` — Squat/hinge/unilateral (home, weight)
- `lower_body_gym` — Legs in gym (gym, weight)
- `heavy_conditioning_gym` — Full-body conditioning (gym, weight+bench)
- `pulling_strength_gym` — Dedicated pulling (gym, pullup_bar+weight)

**Stretching:** Not needed — `flexibility_full` and `yoga_recovery` already in planner pool. Users find them in climbing suggestions.

**Not in scope (separate features):**
- B37 (add single exercise to session)
- Supplementary sessions in auto-planner (these are user-initiated only via quick-add)
- Guided session for supplementary (uses same guided flow)

**Rischio:** BASSO — backend: aggiunge campo + sezione API response. Frontend: espande UI dialog. Zero impatto su planner/resolver/macrocycle.

---

## Priority 2.75 — Refactoring (prossimo ciclo)

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R143 — Refactor replanner_v1.py

**Priority:** P2.75
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- Spezzare `replanner_v1.py` (1042 righe) in package `replanner/` con handler separati per categoria intent (rest, swap, equipment, outdoor)
- Risolvere dipendenza circolare con `planner_v2.py` estraendo `_INTENSITY_TO_LOAD` e `_SESSION_META` in `session_catalog.py` condiviso

**Moduli impattati:** replanner_v1, planner_v2
**Rischio:** ALTO — tocca replanner e planner, mandatory analysis phase

### R144 — Frontend API Layer Refactor

**Priority:** P2.75
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- Adottare TanStack Query per caching, deduplicazione request, e gestione loading/error standardizzata
- Refactorare `api.ts` (590 righe) con client tipizzato e interceptor centralizzato

**Moduli impattati:** lib/api.ts, tutte le pagine che fetchano dati
**Rischio:** MEDIO — cambia pattern data fetching su tutto il frontend

### R145 — Spezzare pagine componente grandi

**Priority:** P2.75
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- `today/page.tsx` (971 righe) → custom hook `useToday` + sotto-componenti
- `week/page.tsx` (889 righe) → custom hook `useWeekPlan` + sotto-componenti
- `settings/page.tsx` (1018 righe) → pannelli separati
- `guided/[date]/[sessionId]/page.tsx` (600+ righe) → separare timer logic, UI, state

**Moduli impattati:** 4 pagine principali + nuovi hook/componenti
**Rischio:** MEDIO — refactor strutturale, nessun cambio logica

### R146 — Estrarre logica duplicata

**Priority:** P2.75
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- **Backend:** load score computation condivisa tra `resolve_session.py` e `planner_v2.py` → utility module
- **Frontend:** handler duplicati (`handleMarkDone`, `handleMarkSkipped`, `handleUndo`) tra `today/` e `week/` → hook condiviso `useSessionHandlers`
- **Frontend:** componenti condivisi `<LoadingState>`, `<EmptyState>`, `<ErrorState>`

**Moduli impattati:** resolve_session, planner_v2, today/page, week/page
**Rischio:** MEDIO — tocca resolve_session e planner_v2

### R147 — Resolve Session Refactor

**Priority:** P2.75
**Status:** Open
**Discovered:** 2026-03-21 (codebase audit)
**Type:** R (refactor)

- Spezzare `resolve_session()` (7 parametri, 170+ righe) in `_resolve_session_context()`, `_resolve_module()`, `_load_session_templates()`
- Refactorare filtri P0 da nesting 5+ livelli a pipeline pattern
- Eliminare codice morto (`resolve_session.py:1145-1146`)

**Moduli impattati:** resolve_session
**Rischio:** ALTO — tocca resolve_session, mandatory analysis phase

---

## Priority 3 — UI polish (parallel with P2)

Items that affect first impression for paying users.

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B40 | Branch develop/main workflow | S | Set up develop branch for staging, main for production deploys. |

### Stretching Circuit add-on

**Priority:** P3 (post-launch)
**Status:** Open — design pending
**Type:** A (feature)

**Context:** Same architecture as Core Circuit but for post-session static stretching. Timer with longer holds (30-60s hold / 5s transition). Pool of ~20 stretching exercises. Position: post-session.

**Dependencies:** A140 (Core Circuit — done, provides the architecture pattern)
**Effort:** M (exercise catalog + minor timer config changes)

### Warmup Circuit add-on

**Priority:** P3 (post-launch)
**Status:** Open — design pending
**Type:** A (feature)

**Context:** Same architecture as Core Circuit but for pre-session dynamic warmup. Mobility, activation, pulse raiser exercises. Shorter work times (30s work / 10s transition). Position: pre-session.

**Dependencies:** A140 (Core Circuit — done)
**Effort:** M (exercise catalog + minor timer config changes)

---

## Priority 4 — Go-to-market

- Landing page / marketing site
- Pricing model definition
- App Store prep (Capacitor wrapping PWA — Phase 4d, zero code rewrite)

### Board-specific features (Kilter first)

**Priority:** P4 (long-term)
**Status:** Open — no design yet
**Type:** A (feature)

**Context:** Currently all board surfaces (Kilter, MoonBoard, Other) share the same generic free climbing flow. Each board has unique features that could be integrated:
- **Kilter Board:** API integration for problem lookup, difficulty ratings, lighting
- **Tension Board:** Similar API capabilities
- **MoonBoard:** Problem database, benchmarks

**Approach:** Start with Kilter (most mature API, Daniele uses it). Research API capabilities, then design integration. Other boards follow same pattern later.

**Dependencies:** Free Session system (done)
**Effort:** L (API research + integration per board)

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

### Load calculation v2 — proper normalization

**Priority:** Post-launch (v2)
**Status:** Open
**Origin:** D151 load coherence audit (2026-03-23)

I fix v1 (D151) usano approssimazioni pragmatiche: ×1.5 rescale per engine, hard cap per outdoor, zero contribution per other_activities. Un v2 proper dovrebbe:

| # | Area | Dettaglio |
|---|------|-----------|
| 1 | Outdoor user-relative scaling | Attualmente usa gradi French assoluti (6a pesa uguale per un 6a climber e un 7c climber). Dovrebbe usare `grade / user_max` come free sessions. Richiede decidere grade_ref (boulder_max_rp? lead_max_rp? dipende dal tipo via). |
| 2 | Other activities load map | `activity_load_map` con valori AU fissi per tipo: `{"running": 30, "yoga": 10, "cycling": 20, "swimming": 25, ...}`. Necessario per ACWR (D69). |
| 3 | Engine load normalization | Sostituire ×1.5 magic number con formula proper: `(sum_fatigue / max_possible_fatigue) × 85` basata su exercise count e intensity della sessione. |
| 4 | Free session non-linear scaling | Climb vicini o sopra il max dovrebbero pesare esponenzialmente di più (il SCALE_FACTOR = 4.0 lineare sottostima). Proposta: curva esponenziale sopra 90% del max (×1.3 al 90-100%, ×1.8 sopra 100%). Da calibrare con dati reali beta tester. |
| 5 | Unified AU scale validation | Dopo normalizzazione di tutte le sorgenti, validare con dati reali beta tester che i pesi relativi siano corretti. |

**Depends on:** D69 (ACWR) design, beta tester data.
**Priority:** Post-launch, pre-ACWR.

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
| R148 | Performance: JSON catalog caching | Aggiungere `@lru_cache` su `json_loader.py` (ogni request ri-legge da disco). Ottimizzare `pick_best_exercise_p0()` da 6 passate a singola passata. Aggiungere bounds checking su adaptation engine multipliers. Origin: codebase audit 2026-03-21. |
| R149 | Frontend performance | Code splitting con `next/dynamic` per radar charts, guided session, onboarding. `React.memo` su `SessionCard` (919 righe) e componenti hot-path. Origin: codebase audit 2026-03-21. |

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

## Future — Injury-Specific Rehab/Prehab

> Origin: Christie feedback 2026-03-21

Currently, when a user flags an injury in their limitations, the system shows a generic warning ("be careful, you have an injury") during sessions that stress the affected area. Christie requested that the app suggest **specific rehab/prehab exercises** tailored to the injury type and body zone.

**Example:** User flags "finger pain" → instead of just warning, the app suggests finger tendon gliding exercises, eccentric wrist curls, rice bucket work, etc. User flags "shoulder pain" → suggests band pull-aparts, external rotations, scapular stabilization drills.

| # | Component | Effort | Detail |
|---|-----------|--------|--------|
| 1 | Rehab exercise catalog | M | New exercises in `exercises.json` with `category: "rehab"`, tagged by `injury_zone` (finger, shoulder, elbow, wrist, knee, back) and `injury_type` (tendon, muscle, joint). Evidence-based protocols from literature (Hörst, Hooper's Beta, physiotherapy sources). |
| 2 | Injury → exercise mapping | S | Mapping logic: user's `limitations[]` entries → matched rehab exercises. Must handle multiple concurrent injuries. |
| 3 | Rehab session integration | M | Options: (a) prepend rehab block to existing sessions, (b) separate "Rehab Session" type, (c) both. Rehab exercises should NOT count toward training load. |
| 4 | Progression logic | M | Rehab exercises need their own progression model — lighter, more conservative than training progression. Possibly: pain-based gating (if pain increases → regress, if pain decreases → progress). |
| 5 | Medical disclaimer | S | Mandatory disclaimer: "This is not medical advice. Consult a physiotherapist for diagnosis and treatment." Must be shown on every rehab suggestion. Required before launch of this feature. |
| 6 | LLM Coach integration | M | Strong candidate for Phase 3.5 LLM Coach: Coach suggests rehab exercises from literature dynamically, avoiding need to hardcode every injury→exercise combination. Coach can also ask follow-up questions about pain type/severity. |

**Risks:**
- **Medical/legal liability**: prescribing rehab exercises for injuries is sensitive territory. Wrong exercise on a real injury can cause harm. Disclaimer is necessary but not sufficient — exercises must be evidence-based and conservative.
- **Catalog complexity**: rehab is essentially a sub-system with its own progression, its own exercise pool, and its own safety constraints.

**Recommendation:** Do NOT implement before soft launch. Best approach is Phase 3.5 (LLM Coach) where the Coach can suggest from literature without hardcoding. Quick win for now: add links to external resources (e.g. Hooper's Beta rehab videos) in the injury warning message.

**Dependencies:** None for roadmap entry. Implementation depends on LLM Coach (Phase 3.5) or standalone rehab catalog (Phase 4+).

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
| R150 — Integration test full-pipeline | Test end-to-end: assessment → macrocycle → planner → resolver → feedback → closed-loop. Edge case tests per replanner e resolve_session P0 filters. Test compound multiplier scenarios per adaptation_engine. | codebase audit 2026-03-21 |
| R151 — Code quality polish | Type hints completi (sostituire `dict` generico con `TypedDict`/`dataclass`) in replanner_v1 e closed_loop_v1. Eliminare ~15 istanze di `any` nel frontend. Consolidare date handling usando `utils/date_utils.py` ovunque. Docstrings sulle funzioni pubbliche core. | codebase audit 2026-03-21 |
| R152 — Full codebase audit con Agent Teams | Audit periodico con team di 3+ agenti specializzati (backend logic, frontend UX, test coverage). Output: report dettagliato con file e righe esatti, classificato per severità. Frequenza suggerita: una volta per sprint/ciclo di sviluppo. | codebase audit 2026-03-21 |
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
| Injury-specific rehab/prehab | Rehab exercise catalog + injury→exercise mapping + progression. Generic warning → targeted exercises. Medical disclaimer required. Best candidate for LLM Coach layer. | Christie feedback 2026-03-21 |

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
