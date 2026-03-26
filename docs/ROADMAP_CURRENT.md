# climb-agent — Active Roadmap

> Last updated: 2026-03-25
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

All P1 items completed (30+ items). See archived history in `docs/ROADMAP_v2.md`.

---

## Priority 2 — Auth + Payments + DB (go-to-market blockers)

Clerk auth ✅ and Supabase JSONB ✅ are complete. Remaining:

- **Stripe subscriptions** — pricing model TBD
  - Free tier vs paid features to be defined

---

## Priority 2.25 — Code Quality & Hardening

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R140 — Backend Error Handling Hardening

**Priority:** P2.25 | **Status:** Open | **Type:** R (refactor)

- Sostituire `except Exception` silenziosi in `closed_loop_v1.py` con logging esplicito
- Validazione `perceived_difficulty` (range 1-5) in `closed_loop_v1.py`
- Validazione input sulle funzioni pubbliche di: `planner_v2.py`, `resolve_session.py`, `macrocycle_v1.py`, `replanner_v1.py`
- Sostituire global mutable state (`_CATALOG_CACHE`, `_cached_quotes`) con `@lru_cache`

**Rischio:** MEDIO — moduli core ma cambiamenti difensivi

### R141 — Frontend Error Handling Hardening

**Priority:** P2.25 | **Status:** Open | **Type:** R (refactor)

- Sostituire `.catch(() => {})` silenziosi (~20 istanze) con error toast
- Validazione Zod su `JSON.parse` del localStorage nella guided session
- `AbortController` sulla navigazione week
- Stati loading/error consistenti su `today/`, `plan/`, `outdoor/`

**Rischio:** BASSO — cambiamenti UX difensivi

### R142 — Magic Numbers Extraction

**Priority:** P2.25 | **Status:** Open | **Type:** R (refactor)

- Estrarre magic numbers da `progression_v1.py` in named constants
- Spostare tabelle grade-to-score e axis weights da `assessment_v1.py` in JSON catalog

**Rischio:** BASSO — estrazione costanti

---

## Priority 2.5 — Session Quality (post-launch)

### Combo sessions (climbing + conditioning tail)

**Status:** Open | **Effort:** M

Sessions with a primary climbing block (60-70 min) + secondary conditioning block (15-20 min core/prehab/antagonists). Resolves conditioning deficit without replacing climbing days. Pattern already exists in strength_long (hangboard + pulling). Extend to boulder sessions: e.g., limit_boulder_gym + 15min core/antagonist tail. Requires session template redesign to support optional conditioning appendix.

### Flex/rest auto-fill (Pass 3)

**Status:** Open | **Effort:** S

After Pass 1 (primary) and Pass 2 (complementary), add a Pass 3 that fills remaining empty days with flex/rest/mobility sessions. Currently empty days stay empty. Especially needed in deload phase (3 sessions on 7 days). Depends on: nothing.

### Gym-aware PE routing

**Status:** Open | **Effort:** S

PE sessions should prefer gyms with gym_routes over boulder-only gyms when both are available. Currently the planner picks the first gym day regardless of equipment fit. Cosmetic improvement — PE on routes at Cocque is better training than PE on boulders at BKL. Depends on: nothing.

---

## Priority 2.5b — Catalog & Polish

### C130 — Audit sistematico domain/intensity/pattern

**Priority:** P2.5 | **Status:** Partially closed (2026-03-22)

**Completato:** Audit 178 esercizi, 5 intensity mismatch corretti, 4 session filter corretti, 9 sessioni orfane triagate.

**Ancora aperto:** ~33 pattern/domain borderline cases (multi-domain exercises, vocabulary gaps) — richiedono decisione design.

### Free Session UI grouping — collapse climbing surfaces

**Priority:** P2.5 | **Status:** Open | **Type:** A (frontend only) | **Effort:** S

Single "Climbing" card with tap-to-expand, showing 5 surfaces. Add-ons section below.

### Core Circuit exercise images — Gemini AI generation

**Priority:** P2.5 | **Status:** In progress — 4/30 done | **Type:** C (content)

Semi-realistic illustrations via Gemini AI. 26 of 30 exercises remaining. Non-blocking.

### Exercise images for complex exercises

**Priority:** P2.5 | **Status:** Open — TBD post-launch | **Type:** A + C (schema + content)

- Add `image_url` or `images[]` field to exercise catalog schema (currently no image support — only `video_url` exists)
- Generate instructional images (Gemini AI) for exercises that assume prior knowledge and are hard to understand from text alone
- Priority targets: hangboard grip exercises (grip_transitions, overcoming_isometric_pull), campus board exercises, technique drills
- Style: clean side-view instructional photos, consistent framing, suitable for in-app display on exercise detail cards
- Frontend: display image(s) on `exercise-detail-sheet.tsx`, above or below the description
- Discovered during B157 audit: `grip_transitions_half_to_open` was the only hangboard exercise with a one-line description and no visual reference

---

## Priority 2b — Test results → full exercise calibration

Every test result we collect MUST influence exercise prescription.

| Test result | Current use | New use | Impact |
|-------------|------------|---------|--------|
| L-sit hold (sec) | radar only | Core progression tier (3 tiers) | Exercise selection + prescription |
| Hip flexibility (cm) | radar only | Mobility tier (skip acquired stretches) | Exercise selection |
| Repeater 7/3 max sets | radar only | Finger endurance volume calibration | Prescription (sets/volume) |
| Max hang duration (sec) | radar only | Endurance hang calibration | Prescription (time) |

Depends on: B122 pattern, Supabase migration.

---

## Priority 2.75 — Refactoring

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R143 — Refactor replanner_v1.py

**Status:** Open | Spezzare in package `replanner/` + estrarre `_SESSION_META` in modulo condiviso.
**Rischio:** ALTO — mandatory analysis phase

### R144 — Frontend API Layer Refactor

**Status:** Open | TanStack Query + refactor `api.ts` (590 righe).
**Rischio:** MEDIO

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

## Priority 3 — UI polish

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B40 | Branch develop/main workflow | S | Staging/production branches |

### Stretching Circuit add-on

**Status:** Open — design pending | **Effort:** M
Same architecture as Core Circuit for post-session static stretching (30-60s holds).

### Warmup Circuit add-on

**Status:** Open — design pending | **Effort:** M
Same architecture for pre-session dynamic warmup (30s work / 10s transition).

---

## Priority 4 — Go-to-market

- Landing page / marketing site
- Pricing model definition
- App Store prep (Capacitor wrapping PWA)

### Board-specific features (Kilter first)

**Status:** Open | **Effort:** L
API integration for Kilter Board (problem lookup, difficulty, lighting). Other boards follow same pattern.

---

## Future — Phase 3.5: LLM Coach

Claude Sonnet as conversational layer over the deterministic engine.
Design spec: `_archive/docs/coach_knowledge_base_spec.md`

- Dynamic system prompt injecting user_state + current plan + recent logs
- POST /chat endpoint
- Use cases: conversational onboarding, pre-session coaching, post-session analysis
- The LLM suggests and converses — it does NOT modify the plan directly

**Dependent items:** B89 (weekly report narrative), B11 (configurable test protocols), B29a (dedicated test exercises), science explainers, nutrition hints.

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
| ARCH-3 | Generic timer from prescription | Frontend timer derives behavior from `work_seconds` + `reps` + `rest_*` fields |
| — | Override intensity cap warning | Warn when user overrides above phase intensity cap |
| — | P1 ranking in resolver | Recency, intensity, fatigue-based exercise prioritization |
| — | Advanced adaptivity | Readiness score, overreach detection, plateau detection |
| — | Test results → exercise calibration | Use ALL test results to calibrate difficulty and prescription |
| B127 | Pre-test adjacency rule | Planner excludes finger work day before finger test sessions |
| B133c | Multiple other_sport same day | `other_activities: []` array instead of boolean |
| R148 | Performance: JSON catalog caching | `@lru_cache` on `json_loader.py`, optimize `pick_best_exercise_p0()` |
| R149 | Frontend performance | Code splitting, `React.memo` on hot-path components |

---

## Future — Content & UX

### Educational content (methodology explanations)

Two-layer system: reference doc (`docs/training_methodology_explained.md`) + condensed UI cards in Plan page.
Content: 5 phases, DUP vs linear, feedback loop, deload science, exercise ordering.

### Outdoor redesign

Guided outdoor session mode, load calculation, ripple effect, done tracking, history/stats UI, spots in onboarding.
Consolidates: B68, B69, B70, B72, B73.

### Social Session (fun bouldering with friends)

Recreational session: game catalog, purpose selector, timer, social_modifier=0.5 load. Origin: real session 2026-03-14.

### Injury-Specific Rehab/Prehab

Rehab exercise catalog + injury→exercise mapping. Medical disclaimer required. Best candidate for LLM Coach layer (Phase 3.5). Origin: Christie feedback 2026-03-21.

---

## Future — Evolution (Phase 4+)

- UI-25 — Test Maxes & Loads panel (Plan tab)
- Multi-goal support (boulder, all-round, outdoor_season)
- Annual report
- Multi-macrocycle periodization
- Notifications/reminders
- Season reset (partial re-onboarding)
- Gym preferences per day
- Crowdsourced gym DB

---

## Backlog / exploration

| Theme | Detail | Origin |
|-------|--------|--------|
| R150 | Integration test full-pipeline (assessment → closed-loop) | audit 2026-03-21 |
| R151 | Type hints (`TypedDict`/`dataclass`), eliminate `any`, date utils | audit 2026-03-21 |
| R152 | Periodic full codebase audit con Agent Teams | audit 2026-03-21 |
| D10 | Overcoming isometric pull exercise (pin/strap equipment) | mega brief Session 2 |
| D37 | Core activation drills from Matros (8 exercises) | mega brief Session 3 |
| D50 | Three named repeater protocols (López/Anderson/Hörst) | mega brief Session 2 |
| D72 | grip_type field on hangboard exercises | mega brief Session 2 |
| — | Dynamic background imagery (Midjourney, phase-aware) | roadmap discussion |
| — | Technique drills from book (scan + catalog) | roadmap discussion |

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
| 4b: Guided session + beta | 2026-03 | Step-by-step timer, settings editors, dirty-state |
