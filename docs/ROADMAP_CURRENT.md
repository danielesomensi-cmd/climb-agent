# climb-agent — Active Roadmap

> Last updated: 2026-03-26
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Mega Brief v1 — ARCHIVED (2026-03-26)

> Source: `docs/claude_code_mega_brief_v1.md` (57 v1 decisions, 10 sessions)
> Status: **Archived.** ~80% implemented. Remaining decisions migrated to backlog below.
> Triage report: D160 (claude.ai, 2026-03-26)
> Codebase verification: D160 Phase 0 (Claude Code, 2026-03-26)

| Session | Status | Implemented | Deferred to v2 |
|---------|--------|-------------|-----------------|
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

*D55: de facto safe (exercises not in catalog) but no formal blacklist guard — v2.
*D58: 4/5 postural exercises done, YTW missing — v2.
*D44: code has base=4wk/floor=2wk, not ≥6wk — intentional trade-off, v2 via D19.
*D75: cue_008 + timed_route_preview exercise exist — sufficient for launch.

---

## Priority 1 — Stability and bug fixes

All P1 items completed (30+ items). See archived history in `docs/ROADMAP_v2.md`.

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

---

## Priority 2 — Auth + Payments + DB (go-to-market blockers)

Clerk auth ✅ and Supabase JSONB ✅ are complete. Remaining:

- **Stripe subscriptions** — pricing model TBD
  - Free tier vs paid features to be defined

---

## Priority 2.25 — Code Quality & Hardening

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R140 — Backend Error Handling Hardening ✅

**Priority:** P2.25 | **Status:** Closed (2026-03-26) | **Type:** R (refactor)

Logging aggiunto a 6 moduli engine, 5 `except:pass` silenziosi sostituiti con `logger.warning`, cache globali mutabili (`_required_equipment_cache`, `_cached_quotes`) sostituite con `@lru_cache`, validazione input su `generate_phase_week`, `generate_macrocycle`, `resolve_session`, `suggest_sessions`, `apply_day_add`.

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

**Status:** ✅ Resolved by B160g | **Effort:** M

~~Sessions with a primary climbing block (60-70 min) + secondary conditioning block (15-20 min core/prehab/antagonists).~~ **Resolved:** B160g added core_standard + antagonist_prehab tail blocks to all gym sessions that were missing them. Every gym session now follows the strength_long pattern: warmup → main → core → antagonist → cooldown.

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

### C164 — Catalog expansion: Category B exercise pools

**Priority:** P2.5b | **Status:** Open | **Type:** C (catalog) | **Effort:** M

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

### Exercise images for complex exercises

**Priority:** P2.5 | **Status:** Open — TBD post-launch | **Type:** A + C (schema + content)

- Add `image_url` or `images[]` field to exercise catalog schema (currently no image support — only `video_url` exists)
- Generate instructional images (Gemini AI) for exercises that assume prior knowledge and are hard to understand from text alone
- Priority targets: hangboard grip exercises (grip_transitions, overcoming_isometric_pull), campus board exercises, technique drills
- Style: clean side-view instructional photos, consistent framing, suitable for in-app display on exercise detail cards
- Frontend: display image(s) on `exercise-detail-sheet.tsx`, above or below the description
- Discovered during B157 audit: `grip_transitions_half_to_open` was the only hangboard exercise with a one-line description and no visual reference

---

## Priority 2.75 — KB Research Integration

> **Companion project:** The KB research lives in a **separate claude.ai project** called **"climb-agent knowledge base"**.
> All research files, Hörst syntheses, topic files, and decision consolidations live in that project's knowledge.
>
> **⚠️ RULE: Before implementing any deferred decision from the backlog below, open the KB project and check
> `horst_integration_audit.md` for enrichment material. Many deferred decisions have ready-to-use content.**

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

### Open KB Research Items

| Item | Status | Where |
|------|--------|-------|
| Session 2 patch (4 corrections: D11, D12, D39, D72) | ⏸️ Prepared | KB project memory (not yet a file) |
| D84 pulling strength test (max load review) | ⏸️ Under review | KB project |
| Finger strength test architecture (5s→7s Lattice) | ⏸️ Under review | KB project |
| CUE-02 formalize (forearm stretch → D33 amendment) | 📋 Proposed | `horst_integration_audit.md` §6 |
| Coach KB spec: add 8 Hörst coaching cues | 📋 Proposed | `horst_integration_audit.md` §5 |
| Decision consolidation: append D84-D91 | 📋 Proposed | `kb_gaps_analysis.md` |
| Topics 05-10 Steps 4-5 (decision specs) | ⏳ Not started | KB project |

### Remaining Books

| Book | Status | Needed for |
|------|--------|-----------|
| Bechtel — Climb Strong: Drills Manual (pp. 31-90) | 📷 Photograph physical copy | Topic 08 drills |
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

### Feedback Loop Education Copy

**Status:** Open | **Effort:** XS
User-facing copy explaining that feedback drives plan adaptation. Two touchpoints:
1. **Onboarding:** Dedicated step or callout explaining the closed-loop: "Your feedback after each session calibrates your next plan — the more you share, the smarter your training gets."
2. **Main UI (today/session pages):** Persistent slogan/banner near feedback controls, e.g. "Every rating fine-tunes your next session."

Messaging should hint at written feedback value ("Your comments help us understand how you're feeling") without explicitly promising text analysis — that capability arrives with the LLM Coach layer (Phase 3.5).

Related: D77 (SDT principles), D79 ("Train better, not more" personality), Educational content (methodology explanations).

---

## Priority 4 — Go-to-market

- Landing page / marketing site
- Pricing model definition
- App Store prep (Capacitor wrapping PWA)

### Board-specific features (Kilter first)

**Status:** Open | **Effort:** L (basic) / XL (games)

**Level 1 — Data integration (L):**
API integration for Kilter Board problem lookup, difficulty grades, and ascent logging. Use [BoardLib](https://github.com/lemeryfertitta/BoardLib) (Python) for Aurora API access — downloads the SQLite DB with holes, LEDs, placements, and climbs. Covers all Aurora boards (Kilter, Tension, Grasshopper, Decoy). Other boards (MoonBoard) follow same pattern.

**Level 2 — LED control + games (XL, exploratory):**
Interactive games via BLE LED control: tic tac toe on the wall, incremental hold lighting (add one hold each round), circuit creation. Requires Web Bluetooth API (Chrome/Edge only — NOT Safari/iOS). May need native wrapper (Capacitor BLE plugin) for iOS support.

**Open-source references:**
- [BoardLib](https://github.com/lemeryfertitta/BoardLib) — Python, Aurora board API utilities, SQLite DB sync
- [Boardsesh](https://github.com/marcodejongh/boardsesh) — Apache license, unified multi-board app with queue management and Party Mode
- [kilterboard.app](https://tim.wants.coffee/posts/kilterboard-app/) — Web Bluetooth reverse engineering blog post
- [fake_kilter_board](https://github.com/1-max-1/fake_kilter_board) — BLE protocol documentation
- [Grip Connect](https://stevie-ray.github.io/hangtime-grip-connect/devices/kilterboard) — DB schema and placement format docs

**Risk:** Kilter launched a new standalone app (kilterboard.io) separate from the old Aurora app — API stability uncertain. Level 2 blocked on iOS by Web Bluetooth unavailability.

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

**Status:** Open | **Effort:** M
Recreational session: game catalog, purpose selector, timer, social_modifier=0.5 load. Available as a free session mode. Origin: real session 2026-03-14.

### Technique Drills in Free Session

**Status:** Open | **Effort:** S-M
Add technique drill selection as a free session activity type. User picks from the drill catalog (D76) and runs drills as a standalone free session or add-on. Depends on D76 (drill catalog population) being complete.
Related: D73 (technique drill % allocation), D76 (drill catalog).

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

### Mega Brief v1 — Deferred Decisions (v2+)

> Full specifications in `docs/claude_code_mega_brief_v1.md`. Grouped by theme.

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

**Warm-Up & Recovery (mega brief Sessions 4, 7)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D33 | Dedicated `generate_warmup()` function | M | 5-phase protocol generator. **⚠️ KB: Ch. 6 has warm-up exercises + CUE-02 (no forearm flexor stretch pre-performance). See `horst_integration_audit.md` §5-§6.** |
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
| R150 | Integration test full-pipeline (assessment → closed-loop) | audit 2026-03-21 |
| R151 | Type hints (`TypedDict`/`dataclass`), eliminate `any`, date utils | audit 2026-03-21 |
| R152 | Periodic full codebase audit con Agent Teams | audit 2026-03-21 |
| R160 | Audio util dedup: beep/countdownTick/transitionBeep duplicated in CircuitTimer and Tabata — extract to single shared module in lib/ | B160 audit 2026-03-26 |
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
