# climb-agent — Active Roadmap

> Last updated: 2026-04-28 (Session wrap-up: B227 ✅ + B226 ✅ closed earlier today. GTM-STRIPE-TAX deferred (reactivate at 10+ EU paying customers OR €5k EU revenue OR approaching €10k OSS). Pricing decision locked: $9.99/$4.99 are net/exclusive — VAT added on top at future Stripe Tax activation.)
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Priority 1.25 — Audit Remediation (D163 + D164)

> Full reports: `docs/audit/D164/` (138 findings) and `docs/audit/D163_frontend_audit.md` (67 findings)
> Date: 2026-03-28
> Combined: 205 findings (20 P1, 71 P2, 102 P3, 12 P4)

### P2 highlights (not individually tracked — see full reports)

**Engine (D164 Agents 3-5):** Phase duration sum mismatch for 9-11 week macrocycles (P2), deload weights sum 0.40 not 1.0 (P2), `move_session` doesn't validate spacing (P2), `_reconcile()` enforces finger but not hard-day spacing (P2), streak field saved but unused in multiplier (P2).

**Frontend (D164 Agent 1 + D163):** PHASE_LABELS duplicated 4 files, `window.location.href` instead of router.push, console.warn/error in prod, eslint-disable on hooks deps, hardcoded email, session-card 1081 lines, tap targets <44px (6 instances), missing aria-labels (5 instances) → partially covered by B165c, rest deferred to R141/R144/R145.

**Catalog (D164 Agents 7-8):** 10 campus exercises use non-canonical `age_under_16` contraindication, `easy_climbing_deload` legacy schema, `deload_recovery` missing fields, 8 orphan templates, 11 generic placeholder video URLs → covered by B165e.

**Docs (D164 Agent 6):** Intent counts wrong in CLAUDE.md (13+3 vs actual 15+4), `closed_loop_v1.py` filename stale, session "active" label mismatch in sync_status.py, `grip_transition` missing from vocabulary → vocabulary fix in B165a, rest are P2 doc fixes (standalone).

**API contract (D164 Agent 9):** `POST /api/outdoor/convert-slot` response shape mismatch.

**Test coverage (D164 Agent 10):** 9 API endpoints lack integration tests, no full-pipeline E2E test (R150), `cluster_utils` 5/6 functions untested, test fixtures duplicated inline.

### P3 items (102 total) — see full reports, not individually tracked in roadmap

---

## Priority 1.26 — Audit Remediation (D170 + D172)

> Tracking docs: `docs/audit/D172_findings_tracker.md` (full 25-finding breakdown with status per item)
> Audits: D170 (gym_id propagation, 24 findings, 2026-03-31), D172 (all other fields: session_id / template_id / equipment / slot / phase / API validation, 25 findings, 2026-03-31)
> Combined: 49 findings — 13 fixed in B173, 2 P1 hotfixes pending (B174/B175), 21 deferred to B176

### Post-launch (P2)

| ID | Title | Type | Effort | Notes |
|----|-------|------|--------|-------|
| **B176** | D172 consolidated remediation — 21 remaining findings (P2+P3) | B | L | 5 groups: type safety (D172-05,11,12), equipment validation (D172-07,08,22), event/input validation (D172-09,13,14,25), logging (D172-10,15,17-20,23,24), structural/deferred (D172-16,21). Supabase migration already complete — no longer a prerequisite. |

### Deferred from B173 (need API refactoring)

| Title | Priority | Effort | Notes |
|-------|----------|--------|-------|
| `apply_day_add` doesn't receive `gyms` parameter (D170 P1-04) | P3 | M | Needs signature refactoring. Frontend fix in B173 covers the main user-facing path. |

---

## Priority 1.27 — Audit Remediation (D211 / D-TESTUSER-VERIFY residuals)

> Origin: `docs/audit/D-TESTUSER-VERIFY_report.md` §5 (2026-04-19)
> F1 (HIGH) + F3 (HIGH) closed by D214 (`assessment.tests_source` sidecar). Residuals below parked post-launch.

### Post-launch (P2/P3)

| ID | Title | Severity | Priority | Type | Effort | Notes |
|----|-------|----------|----------|------|--------|-------|
| F2 | **Onboarding input validation** — no bounds on BW/height/age/test inputs (BW=33 kg, height=33 cm, age=3, max_hang=3.5× BW accepted silently; radar saturates to 100). | MEDIUM | P2 | B | S | Add range checks at onboarding: BW 35–150 kg, height 120–220 cm, age 10–80, max_hang ≤ 3× BW (soft-warn). |
| F4 | **Stale cached week plan across deploys** — no regeneration trigger on deploy; users onboarded within ~5 min of a push keep pre-push output. | LOW | P3 | B | XS | Accept (deploy-window artifact). Users can force-regenerate via Settings. Document in user guide. |
| F5 | **`goal.primary_weakness`/`secondary_weakness` are absent** — actual storage at `assessment.self_eval.*`. Consumers reading `goal.*` see `None`. | LOW | P3 | D+B | XS | Grep consumers; if any read `goal.*` for weaknesses, fix read site (not write). Spec-drift only. |
| F6 | **`macrocycle.phases[].weeks` is `null`** — consumers iterating `phases[].weeks` see `null`; sum via `start_week` deltas works. | LOW | P3 | D+B | XS | Audit consumers; drop the field from schema if all compute from `start_week` deltas, else populate at generation. |
| F7 | **`goal.deadline` empty while `total_weeks=12`** — onboarding writes `deadline=""` when deadline is derived from `total_weeks`. | LOW | P3 | B | XS | Cosmetic. Compute ISO date from `total_weeks + start_date`, or drop the field. |
| F8 | **`assessment.tests.last_test_date = 2026-04-16`** (3 days before macrocycle start) — writer not traced in D211. | COSMETIC | P3 | D | XS | Grep writer site; likely legacy path in `progression_v1.py`. |
| F9 | **Pass 3 test placement requires non-empty day** (`planner_v2.py:1360`: `if not day_sessions[offset]: continue`). Tests can only replace existing sessions — users with few available days silently lose tests. | MEDIUM | P2 | B | S | Loosen empty-day rule for test sessions, or order `required=True` first across axes. |

---

## Priority 1.75 — Go-to-Market Sprint

> Origin: Strategic Advisory Council (2× runs, 5 advisors each, 2026-04-01)
> Key insight: distribution + onboarding friction are the real blockers, not features.
> Constraint: solo founder, zero marketing budget, feature freeze for 30 days.
> Stripe status: A159 implemented in TEST MODE. Not live. Currently disabled for beta period.

### Timeline

- **Week 0 (now):** Beta testers using the app (4-5 users). Stripe disabled. Founder dry-run.
- **Week 1-2:** Collect beta feedback + fix onboarding blockers from dry-run.
- **Week 2-3:** Pricing decision → activate Stripe live → soft launch on r/climbharder.
- **Week 3-6:** Feature freeze. Only fix bugs from paying/trialing users. Measure.

### Phase 0 — Onboarding dry-run + beta feedback (week 0-2)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| GTM-02b | **Beta tester feedback collection** — structured check-in with Christie, Vato, Alexis on their experience | — | XS | Open | Ask: what confused you? what's missing? would you pay? Key signal: would they pay €14.99/mo. |

### Phase 1 — Pricing + Stripe go-live (week 2-3)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| B209 | **Wire test_max_hang_7s into planner (RC1)** | B | S | ✅ Done | D85 catalog file was orphan — planner hardcoded 5s. Now schedules 7s per design. |
| B210 | **Fix freshness check RC2 — drop estimated_at + bypass on inject_tests** | B | XS | ✅ Done | New users' finger tests no longer skipped for 42 days. |
| D214 | **Source taxonomy normalization — `assessment.tests_source` sidecar (F1+F3)** | D+B | S | ✅ Done | Measured max_hang scalar now wins over grade estimate (F1). Pulling freshness gated on source (F3). Silent `"estimated"` default on missing key = no migration. |
| D215 | **Forensic audit — 2026-04-20 rollover incident (founder account)** | D | M | ✅ Done | Founder saw UBA feedback "vanish" + apparent macrocycle shift. Root-caused to stale `current_week_plan` cache + silent `except Exception` in feedback handler. Full report + snapshot + trace: `docs/audit/D215/`. Read-only, no user-state modified. |
| B216 | **Monday rollover fix — cache self-heal + narrow feedback except (D215 closure)** | B | S | ✅ Done | Defect A: cache-hit in `week.py` now refreshes legacy `current_week_plan` when calendar advances. Defect B: `feedback.py` narrows to `ValueError` + retries mark_done against `week_plans[target_monday]` before giving up. 6 regression tests (T1..T6). |
| D216 | **Audit — phantom "Completed · ~90 min" badge** | D | S | ✅ Done | Read-only. Root-caused to (a) `feedback.py` never writing `session_duration_seconds` onto the session slot (only into `session_completion_log` + `feedback_log`), combined with (b) frontend slot-table fallback `{lunch:35, morning:60, evening:90}` in `session-card.tsx` filling the gap with an estimate. Report: `docs/audit/D216/findings.md`. |
| B217 | **Write session_duration on slot + drop frontend slot-table fallback + tombstone `duration_source`** | B | S | ✅ Done | 4-in-1 bundle (D216 closure). Backend: new write block in `feedback.py` persists `session_duration_seconds` on `current_week_plan` + `week_plans` cache with B197-style max-guard. Frontend: `session-card.tsx` badge + drawer show "Completed" clean (no `· ~NN min`) when duration missing; real duration when measured. Hygiene: removed Potemkin field `duration_source` from 3 frontend senders + 1 backend reader + 1 fixture + roadmap. 5 regression tests (`test_feedback_duration_B217.py`). |
| B214 | **Scalar-write map consolidation in `_update_test_from_log`** | B | S | ✅ Done | `_TEST_EXERCISE_SCALARS` registry centralises `_mark_measured` keys per `exercise_id` branch. Closes D214 drift risk (adding a new scalar write without calling `_mark_measured`). AST introspection test prevents future drift. |
| B215 | **Pulling baseline Priority 0 source gate (symmetry with hangboard)** | B | S | ✅ Done | `_estimate_pulling_baseline` now branches on `assessment.tests_source`: measured → `source="test"` + `updated_at`; estimated → `source="estimated_from_assessment"` + `estimated_at`. Closes architectural asymmetry flagged in D214. |
| — | **Bundle B complete** — baseline + test-week remediation closed (B209 + B210 + D214 + B214 + B215) | — | — | ✅ | Pre-paid-launch remediation arc done. Next: B203, B205, GTM-STRIPE-TAX for launch prep. |
| B207 | **Harden `warmup_climbing` template — fallback for no-wall home** | B | S | Open **P2** | Residual from D210. `warmup_easy_boulders` referenced by explicit `exercise_id`, bypasses P0 equipment gate. Options: (a) filter-based selection with equipment gate, or (b) add `warmup_general_mobility` fallback. |
| B203 | **Handle customer.deleted webhook + error retry policy** | B | S | ✅ Superseded by B226 | Original scope absorbed into B226 (fail-loud + idempotency + customer.deleted in one brief). Tracking moves to B226. |
| B204 | **Subscription guard 402 UX + cancel status display** | B | S | ✅ Superseded by B228 | Audit F4 confirmed `api.ts:54-62` only handles 401; 402 falls through to `Error("API XXX: ...")` raw. Tracking moves to B228 (frontend-only, branch + Vercel preview). |
| B205 | **Verify cancel_at_period_end grace period** | B | XS-S | 🔁 Rolled into B226 | Targeted test added inside B226 (`stripe_webhook.py` is opened once for fail-loud + customer.deleted + cancel_at_period_end). Marginal cost. |
| GTM-STRIPE-TAX | **Stripe Tax registration** | Config | S | 🟡 Deferred | Reactivate when **either** condition met: (a) 10+ paying EU customers, OR (b) €5k cumulative EU revenue, OR (c) approaching €10k OSS threshold. Below these, IT domestic VAT rules apply (regime forfettario or ordinario per Daniele's setup), Stripe Tax is scope creep. When reactivating: 4 dashboard steps + 4-line code change in `subscription.py:108-124` (`automatic_tax: {enabled: true}` + `tax_id_collection` + `billing_address_collection: 'required'`). Decide now: prices $9.99/$4.99 are **net** (exclusive — VAT added on top at activation) — document this so future activation is consistent. |
| GTM-05 | **r/climbharder soft launch** — post asking for 5 beta testers, zero pitch | — | XS | Open | Not a code task. After B204 + B203. |
| A212 | **Vercel Analytics — channel attribution + funnel events** | A | S | ✅ Done | Council-flagged observability gap closed. `@vercel/analytics` mounted in root layout (pageviews auto-captured). UTM persistence via `localStorage` (30-day first-touch). 6 custom events: `demo_viewed`, `demo_engaged` (first interaction), `demo_scrolled_to_end` (IntersectionObserver), `demo_cta_clicked` (inline/sticky), `subscribe_viewed`, `checkout_clicked` (founding/standard). Privacy policy §6-7 updated: Vercel Analytics disclosed, cookieless+anonymous. Follow-ups: A-ANALYTICS-02 (UTM → Stripe metadata), A-ANALYTICS-03 (Posthog if insufficient), A-ANALYTICS-04 (onboarding funnel). |
| C207 | **Core images remap — orfani → schema numerato + toes_to_hands → hanging_leg_raise** | C | XS | ✅ Done | Audit post-A212 ha identificato 5 file orfani in `frontend/public/exercises/core/` e 10 TODO commentati nel catalogo `circuit-exercises.ts`. Rinominati 4 file raw (`Nordic Curl.jpeg`, `dragon flag.jpeg`, `start side planch left/right.jpeg`) nello schema `NN_<id>.jpeg` e decommentate le righe `image:` corrispondenti. `27_toes_to_hands.jpeg` (esercizio rimosso dal catalogo ma file residuo) rimappato a `ce_hanging_leg_raise` → `38_hanging_leg_raise.jpeg` (movimento analogo). 5 TODO residui senza immagine: ce_front_lever_tuck, ce_hanging_wipers, ce_straddle_l_sit, ce_v_up_hold, ce_arch_body_hold. |
| C208 | **Hips/chest/triceps catalog expansion — D217 gap closure (+8)** | C | S | ✅ Done | Aggiunti 5 hips (`side_lying_hip_abduction`, `standing_hip_adduction_band`, `copenhagen_adductor_plank`, `clamshell`, `seated_leg_raise_hip_flexor`), 2 chest (`incline_pushup`, `dumbbell_fly`), 1 triceps (`overhead_tricep_extension`). Vocabolario: nuovo pattern `hip_isolation` + 5 recency_group (`hip_abduction`, `hip_adduction`, `hip_flexor`, `push_horizontal`, `push_tricep`). Count 198 → 206. Nota: rinumerato da C207 per collisione (commit `38c72e7` già esistente, verificato via `scripts/next_brief.py`). |
| C209 | **KB-validated catalog expansion — hips/glutes/legs/biceps (+6)** | C | S | ✅ Done | Aggiunti `cossack_squat`, `hip_90_90_switch`, `single_leg_glute_bridge`, `single_leg_rdl`, `bulgarian_split_squat`, `supinated_inverted_row`. Vocabolario: 2 nuovi recency_group (`squat_lateral`, `hip_rotation`). Deviazioni dal brief: 4 `*_family` proposti dirottati su gruppi esistenti per preservare anti-repeat semantics (`glute_bridge_family`→`glute_bridge`, `rdl_family`→`hip_hinge`, `split_squat_family`→`split_squat`, `row_family`→`horizontal_pull`). Count 206 → 212. Fix test collaterali: `test_total_count` (→212), `test_lower_body_gym_contains_squat` (aggiunti cossack+bulgarian). |
| — | **test_b119: rimossi 2 skip condizionali** | — | XS | ✅ Done | `test_non_monday_corrected` + `test_explicit_non_monday_corrected` ora seedano macrocycle/goal+assessment via `PUT /api/state` prima dell'asserzione e ripristinano in `finally`. Non dipendono più dall'ordine di esecuzione. Suite: 1758 passed + 2 skipped → 1760 passed, 0 skipped. |
| A213 | **Body Part Picker — strength session generator (D217 closure)** | A | L | ✅ Done | Nuovo motore `body_part_picker.py` con 11 categorie, resolver-light (prescription_defaults + overrides + working_loads + hangboard baseline), cross-category exclusions (biceps−forearms, forearms−fingers), deterministic seeding. 4 endpoint (`/options`, `/preview`, `/start`, `/estimate`) con subscription guard. Nuovo event `add_generated_session` nel replanner (no ripple, no closed-loop). Feedback bypass per `build_kind="body_parts"` (working_loads sì, closed-loop no). Pagina `/body-part-picker` multi-step (equipment → parts → preview). 54 nuovi test (31 unit + 15 API + 8 replanner). Suite: 1760 → 1814 passed. |
| B218 | **Body Part Picker — 4 bugfix post-launch (A213 usability)** | B | S | ✅ Done | Bug 1: `add_generated_session` ora appende su slot occupato (non più 422); resta il reject su `other_activity_slot`. Bug 2: `apply_resolver_light` promuove `sets/reps/work_seconds/rest_*/load_kg/notes` a top-level per il branch `is_custom` di `session-card.tsx` (stesso shape di `CustomSessionExercise` A206). Bug 3: nuovo `buildGuidedStateFromInline` in `session-card.tsx` costruisce `GuidedSessionState` da `session.exercises[]` piatto e riusa `/guided/[date]/[sessionId]` via localStorage — niente lookup custom-session DB. Bug 4: `general_pulse_raise` + `dynamic_mobility_flow` prepended ai blocchi body-part con `module_role="warmup"`; baseline flat warmup rimosso dal calcolo durata (double-count). +3 test (`test_body_part_picker.py` warmup+top-level, `test_a213_replanner_generated_session.py` append-on-occupied + other-activity reject). |
| D220 | **Body Part Picker — description/cues/load propagation audit (read-only)** | D | XS | ✅ Done | Audit su 6 esercizi dal test iPhone (`romanian_deadlift`, `reverse_lunge`, `clamshell`, `hip_90_90_switch`, `core_l_sit`, `core_hollow_hold`): il "description" in Today/Guided è in realtà `prescription_defaults.notes` (solo 2 su 6 lo hanno nel catalogo). Il carico mancante per RDL è atteso (external_load senza `intensity_pct` né entry in `working_loads`). Unico gap di parità effettivo: `apply_resolver_light` non copia `cues[]` dal catalogo (il full resolver sì, `resolve_session.py:1070/1533`). Report: `docs/audit/D220_body_part_picker_audit.md`. |
| B221 | **Body Part Picker — propagate cues to instance + render in UI** | B | XS | ✅ Done | Chiude il parity gap identificato da D220. `apply_resolver_light` ora copia `cues[]` sull'istanza (fallback `[]`, stesso field-name del full resolver). `CustomSessionExercise` tipizza `cues?: string[]` opzionale. `session-card.tsx` inline A213 render aggiunge bullet list cues sotto notes in Today expanded. `buildGuidedStateFromInline` inoltra `cues` in `GuidedExercise` (il render in `guided-exercise-step.tsx:432` era già pronto). +2 test: catalog cues verbatim, fallback `[]` su esercizi senza cues. Nessun tocco a resolve_session/planner/progression. Suite: 1817 → 1819 passed. **Update 2026-04-23 (reopened):** aggiunti i 4 campi rimanenti che il full resolver emette e l'UI guided legge: `video_url` (link video), `unilateral` + `alt_sides` (bool, triggerano UI per-hand/alternating), `attributes` (drive `testField`/`testUnit` → stopwatch e dual-hand inputs). Default canonici (`None`/`False`/`{}`) matchati da `resolve_session.py:1532-1540`. +4 test parity. Suite 1819 → 1823. |
| D223 | **Body Part Picker — main vs warmup classification audit (read-only)** | D | XS | ✅ Done | Audit: `apply_resolver_light()` non filtra mai per `role` — warmup/activation/prehab/test sono candidati validi per lo slot main. Root cause primaria: riga missing in `select_exercises_for_part()`. Riproduzione: utente Home, Fingers, prefs vuote → 0 esercizi `role=main` in 20 draws (seeds 0-9). Bug secondario identificato ma fuori scope: `norm_str(None) == "none"` in `resolve_session.py:875,886-888` causa phantom +5.0 bonus per esercizi senza `attributes.grip`. Reports: `docs/audit/D223_body_part_picker_classification_audit.md`, `D223_body_part_pool_listing.md`, `D223_c225_research_notes.md`, `D223_full_resolver_reclass_impact.md`. |
| B224 | **Body Part Picker — role=main filter + N=3 + forearms/biceps main catalog expansion** | B | S | ✅ Done | Chiude D223. Tre interventi atomici: (1) catalog +6 main `role`: `wrist_roller`, `wide_pinch_extended_wrist_hold`, `heavy_reverse_wrist_curl` per forearms; `weighted_chinup`, `hammer_curl`, `reverse_barbell_curl` per biceps. Ricerca climbing-specific (Hörst / Lattice / Gripped) in `docs/audit/D223_c225_research_notes.md`. Classificazione attesa verificata: `weighted_chinup` in biceps+back_pulling (multi-pattern), altri 5 single-body-part. (2) `N_PER_BODY_PART` 2 → 3. (3) Three-tier cascade in `select_exercises_for_part()`: main → main+accessory → tutto (never empty). Tier-first-then-score preserva priorità implicita del ruolo, jitter/recency rankano intra-tier. TODO comment in `_exercise_fits_equipment` per `equipment_required_any` divergence (reso inerte dal role=main filter). Full resolver regression: solo `pulling_strength_compound` block guadagna `weighted_chinup` (9 → 10), finger/route blocks invariati. Field parity frontend confermata via `apply_resolver_light(weighted_chinup)` identica a `pullup`. +9 test (5 catalog: exist/fields/vocab/count-218/gym_full-main-≥3; 4 engine: main-preferred/tier2/tier3/never-empty/all-bp-n3). Suite: 1823 → 1832. Catalog 212 → 218. |
| A-DEMO2-01 | **Editorial Dark demo page at `/demo2`** | A | M | ✅ Done | Nuova route parallela a `/demo` (che resta live per traffico flyer QR) con redesign Editorial Dark: cream (#F5F1EA) su near-black (#0A0A0A), orange (#FF4A1C) come accent esclusivo per main-work. Font self-hosted via `next/font/google` (Archivo Narrow + JetBrains Mono + Inter). Stessi contenuti di `/demo` (warmup → fingers → pull-ups → projecting → 4×4 → core → antagonist → cooldown) ma remapped con sezioni numerate 01-08, timestamp cumulativi, FIG.02 personalization aside, closure "END OF SESSION · 09". Analytics replicata con `variant="editorial_dark"` su ogni evento (demo_viewed, demo_engaged, demo_scrolled_to_end, demo_cta_clicked) per A/B comparison post-deploy. CTA → `/onboarding/welcome`. Zero tocco su `/demo`. Pages 41 → 42. |
| B-DEMO-05 | **Promote Editorial Dark from `/demo2` → `/demo`** | B | S | ✅ Done | Swap mechanical: copiato `demo2/{layout.tsx,page.tsx,session-data.ts}` dentro `demo/`, sovrascritta la vecchia `/demo` pink/navy, eliminata intera cartella `demo2/` (ora 404, no redirect). Rinominate CSS vars `--font-demo2-*` → `--font-demo-*` e simboli `DEMO2_*` / `Demo2*` → `DEMO_*` / `Demo*`. Zero cambi visivi rispetto alla preview `/demo2`. Flyer QR (→ `/demo`) ora serve Editorial Dark. Pages 42 → 41. |
| A214 | **Visual Tokens Foundation — Dark Performance design system** | A | M | ✅ Done (2026-04-27) | **Closed 2026-04-27.** A214 Visual Tokens Foundation Done 2026-04-27. Tailwind v4 @theme inline tokens. Surface/foreground/border/brand/accent/functional/axis/phase token families. shadcn aliases remapped. /dev/tokens showcase gated. Docs: docs/A214_phase0_audit.md, docs/design_system_v1.md. — Tailwind v4 `@theme inline` + CSS variables in `globals.css`. Nuovi namespace: `surface-*` (base 222 28% 8%, raised/elevated/inset), `fg-*`, `border-*` (subtle/default/strong), `brand` (magenta — rinominato da brief's `accent` per evitare collision con shadcn ghost hover `bg-accent`), `brand-secondary` (cyan), functional (success/warning/danger/info + muted), `axis-*` (5 assi), `phase-*` (5 fasi macrocycle), `shadow-glow-{primary,secondary}`, radius 6/10/16/24/999. Shadcn aliases remappati trasparentemente → zero component changes. Climbing legacy tokens (hold-*, wall-*, chalk, rock-light) rimossi (0 referenze). `:root` light + `.dark` collassati in un unico `:root` dark; `@custom-variant dark` preservato per shadcn internals. `viewport.themeColor` aggiornato a `#0f121a`. Showcase `/dev/tokens` (gated NODE_ENV + VERCEL_ENV check). Doc: `docs/design_system_v1.md` con migration map per i 357 raw-palette classes → functional tokens (da migrare in A215/A216/A217). Phase 0 audit: `docs/A214_phase0_audit.md`. Foundation ready for A215 Paywall redesign. |
| B225 | **Remove DarkModeToggle orphan from A214** | B | XS | ✅ Done | A214 Phase 0 audit missed `DarkModeToggle` in `top-bar.tsx` (grep cercava `ThemeToggle` non `DarkModeToggle`). Post-A214 era partially broken: click rimuoveva `.dark` da `<html>` fermando `dark:` variants shadcn ma background restava dark via `:root`. Fix: delete `frontend/src/components/layout/dark-mode-toggle.tsx` (36 righe) + rimozione import/tag da `top-bar.tsx` + collasso `justify-between` → default. Single commit, FF-merge direct to main. |
| B244 | **Today hero card hierarchy fix — no-op closure** | B | XS | ✅ Done (2026-04-27) | Closed as no-op. Brief assumed Today hero card had `border-brand` + `shadow-glow-primary` competing with session card. Verified `page.tsx:1134` already uses `border border-border-subtle shadow-md` (target state) since A217 commit `24f3f89`. False positive in visual review (likely asset bleed perception or stale PWA Service Worker cache). Session card uses default shadcn `Card` (no brand border, no glow). Only `border-brand` + `shadow-glow-primary` references in repo: paywall `TierCard` (intentional A215) + `/dev/tokens` showcase. No code change. |
| A216 | **Onboarding Redesign — hero, A214 tokens, copy refresh** | A | M | ✅ Done (2026-04-27) | **Closed 2026-04-27.** Hero asset `onboarding_hero.webp` 67KB + `.jpg` 102KB fallback (941×1672 9:16) on welcome step, full-bleed 55vh + bottom-up gradient `surface-base/0.95`. h1 "Periodized training." + subtitle "Built for the top 5%." in-overlay. CardTitle "Welcome to Climb Agent" rimosso (ridondante con h1). Body copy refresh: `AI-driven periodization` → `deterministic periodization based on Hörst 4-3-2-1` (✪ critical bug fix: la copy precedente contraddiceva CLAUDE.md non-negotiable "no LLM at runtime"). 4 bullets nominati esplicitamente (5-axis, 10-13 week macrocycle, closed-loop, AI coach forward-looking commitment). CTA "Let's start" → "Start assessment". **StepIndicator hidden on welcome** (pathname.endsWith("/welcome") → null). **A214 token migration** (12 mappings, all banner pre-A214 light+dark pairs): `goals` 3 banner (yellow/red→warning/danger), `tests` info banner (blue→info), `locations` 2 (yellow→warning, red-500→danger), `availability` 4 (amber/blue→warning/info, amber-500→warning, yellow-600→warning), `trips` error (red-500→danger), `review` 3 (yellow×2→warning, red→danger). **Card click states downgrade**: `discipline` + `weaknesses` cards `border-primary ring-2 ring-primary/30` → `border-brand bg-brand/5` (no ring). **Copy refresh applied verbatim per A216 consolidated decisions doc** (14 step + post): all "Climb Agent" capitalized → `climb-agent` lowercase (4 occurrences). Statement-first conversions: discipline/locations/availability/trips/limitations/start-week titles. weaknesses titles "What is your main weakness?" → "Primary weakness". tests "Do you have test data? (optional but recommended)" → "Test data (optional)". goals warnings ambitious/too-low rephrased. review test-week tip refreshed. profile subtitle refreshed. experience labels conciser. **Preserved**: step count 14 (+post +stub), order, `OnboardingContext` logic, `completeOnboarding` payload, validation rules, backend endpoints, recover stub, radar-chart, all backend files. Phase 0 audit: `docs/A216_phase0_audit.md`. Asset source `Onboarding.png` 1.7MB removed (Pillow conversion). Manual QA blocked locally by Clerk middleware (no CLERK_SECRET_KEY in .env.local — known limitation since A217); production validation defers to Daniele on Vercel deploy. Build: TS clean (zero nuovi errori, 2 preesistenti in test files irrelevanti), production build green, all `/onboarding/*` static prerender, backend pytest 1832 passing invariato. |
| A217 | **Today Screen Redesign — hero card + rest day dedup + A214 tokens** | A | M | ✅ Done (2026-04-27) | **Closed 2026-04-27.** Hero card (`today_hero.webp` 76KB + `.jpg` 129KB fallback, 941×1672 9:16) wraps daily quote in `aspect-[4/5] rounded-xl border-border-subtle shadow-md` con bottom-up gradient `surface-base/0.95`. Asset prep via Pillow (`scripts` ad-hoc, source PNG 1.65MB → WebP/JPG, source rimosso). Rimosso backdrop globale `daniclimb.jpg` (172KB) + relativo div fixed-bottom in `page.tsx:917-938`. **Rest day dedup**: nuovo flag `hasNonEngineContent` (other_activity/outdoor/freeSessions); `heroState` IIFE ritorna null se vero (deferito a DayCard); `DayCard` gate cambiato da `dayPlan` a `dayPlan && !heroState` → singolo render path (hero copre rest puro, DayCard copre giorni con yoga/outdoor/free). **Token migration A214**: `WeekProgressBar` (slate-300/400/700 → fg-secondary/muted/surface-inset; emerald-500 active → brand magenta; blue-400 deload → info; emerald-400/amber-400 over/underload → success/warning) + altezza barra `h-1.5` → `h-2` + numero "X/Y" promosso a `font-medium text-fg`; `page.tsx` 3 banner (checkout green-500 → success, resume amber → warning, boulder phase tip sky → info). **Preserved**: `WeeklyCheckinCard` Sun/Mon grace logic invariata, `useDailyQuote` rotation invariata, session card untouched (DayCard 24+ classi hardcoded restano per altro brief). Phase 0 audit deliverable in chat. Build: TS clean (zero nuovi errori, 2 preesistenti in test files irrelevanti), production build green, /today static prerender, backend pytest 1832 passing invariato. |
| A215 | **Paywall Redesign — Dark Performance hero-driven layout** | A | M | ✅ Done (2026-04-27) | **Closed 2026-04-27.** A215 Paywall Redesign Done 2026-04-27. Hero asset (female climber, sunset, overhanging limestone) integrated and live in prod. Founding Climber card with glow-primary border + Standard card + FAQ accordion. SocialProof omitted for launch (no fake numbers). Preview mode (?preview=1) functional for bypass users. Foundation A214 + Paywall A215 complete. Next: A217 Today redesign. — 5 nuovi componenti in `frontend/src/components/paywall/`: `PaywallHero` (70vh full-bleed, `<h2>`, HERO_PLACEHOLDER finché `paywall_hero.webp` arriva), `ValueBullets` (3 icon+text rows — BrainCircuit/RefreshCcw/Mountain), `TierCard` (founding = border-brand + shadow-glow-primary + badge pill, standard = bg-surface-raised outline), `PaywallFAQ` (4 Q&A shadcn Accordion con `trackEvent("faq_expanded")`). Config `frontend/src/config/founding.ts` con `FOUNDING_SPOTS_TOTAL=20`, `FOUNDING_SPOTS_LEFT=20` + `foundingBadgeCopy()` switch statico→dinamico. Shadcn Accordion installato via `npx shadcn add accordion` (riusa umbrella `radix-ui` già in deps). `?preview=1` affordance: query param → CTA disabled + persistent sonner toast "Preview mode — checkout disabled". Stripe flow `POST /api/subscription/checkout` invariato (B212 short-circuit preservato, `handleSubscribe` preserva already_active redirect + checkout_url redirect + error handling). Analytics preservate (`subscribe_viewed`, `checkout_clicked`) + aggiunti `paywall_scrolled_to_tiers` (IntersectionObserver ≥30%) e `faq_expanded` per-question. TrialBanner migrato da `bg-amber-500/10 text-amber-400` → `bg-warning/10 text-warning` (4 classi). `SocialProof` OMESSO per launch (Daniele's call: no inflated beta counts). Page split in `page.tsx` (Suspense wrapper) + `SubscribeContent.tsx` (client logic) per Next 16 Turbopack `useSearchParams()` bailout. Tutti A214 tokens, zero hex. Phase 0 audit: `docs/A215_phase0_audit.md`. Pending hero asset handoff. |
| B226 | **Stripe webhook hardening — fail-loud + idempotency + customer.deleted (+ B205)** | B | S | ✅ Done | Closes audit F2+F3 + B203 + B205. (1) **Fail-loud**: handler exceptions now return HTTP 500 with `{error:"handler_failed", event_id, event_type}` body → Stripe retries with exponential backoff over 72h (was: silently swallowed 200, events lost forever). Failed events explicitly NOT marked processed in dedup cache so retries re-attempt. (2) **In-memory LRU dedup** (`OrderedDict` + `Lock`, max 1024 entries, ~hours of traffic): same `event.id` short-circuits with `{received:true, duplicate:true}`. Persistence gap (cache not survived across Railway restart) mitigated by all handlers being upsert-based (naturally idempotent). Persistent Supabase table → follow-up if LRU proves insufficient. (3) **`customer.deleted`**: new `_handle_customer_deleted` clears `stripe_customer_id`/`stripe_subscription_id`, sets `status="canceled"`, `cancel_at_period_end=False`. Logs `WARNING` if customer row not found. (4) **B205 (cancel_at_period_end)**: regression test confirms `subscription.updated` propagates the flag to `upsert_subscription` and that re-enabling resets it to False; status remains `active` during grace period (B202 fail-closed honors `current_period_end`). +12 tests in `test_stripe_webhook_B226.py` (3 fail-loud, 4 dedup/LRU, 4 customer.deleted, 2 cancel_at_period_end + 1 e2e dispatch). Suite 1843 → 1855. Backend-only, single commit, push direct to main. |
| B227 | **Resolver `intensity_max` enforcement — 3-tier cascade (hard filter)** | B | M | ✅ Done | Audit F1 closed. `pick_best_exercise_p0` 6th param `intensity_max` (default `None`, hard zeroing when set) inserted Stage 3c (between role and domain). `_resolve_inline_block` reads `filters.intensity_max` from JSON and runs generic 3-tier cascade: T1 full constraints → T2 drop domain/pattern (keep ceiling) → T3 only for `low` (one-step escalation to medium) → skip. 7-value ordinal mapping `_INTENSITY_ORDER` (very_low, low, moderate=medium, medium, high=very_high, max). R3 strict: missing `intensity_level` excluded from filtered pool. Structured logging via `extra={}`: WARNING on cascade_skip, INFO on cascade_tier=2|3 (5-key payload: session_id, block_id, cascade_tier, intensity_max, pool_size). Catalog parity (R1 meta→JSON): `_SESSION_META["regeneration_easy"]` gains `required_equipment=["gym_boulder"]` (planner_v2.py:51). +11 tests in `test_resolve_session_intensity_max.py` (8 brief + 2 extra fixtures + 1 max-exclusion). Cascade distribution across 9 declaring sessions × 4 equipment profiles: T1 95.7%, T2 0%, T3 2.2%, skip 2.2% — fix predominantly silent. Suite 1832 → 1843 (+11, zero regressions). Phase 0 audit: `docs/audit/B227_phase0_findings.md`. |
| B245 | **Plan-your-week banner targets correct week on Monday** | B | S | ✅ Done (2026-04-30) | Founder-reported off-by-one: `getNextMonday()` in `weekly-checkin-card.tsx` returned next Monday on Mondays (+7), so taps on Monday saved overrides one week into the future instead of editing the week the user was entering. Fix: new `getTargetMonday()` helper (`frontend/src/lib/weekly-checkin-dates.ts`) returns Sun→tomorrow, Mon→today, Tue–Sat→null. Banner visibility is now derived purely from this helper + a completed-activity gate that hides the banner on Monday when the current week already has any indoor `done`, outdoor `done`, or other-activity `completed`. Sunday skips the gate (next-week plan is freshly generated). Removed the noon Monday cutoff and the now-redundant `shouldShowCheckin()`. Stripped the "Review the week of …" subtitle from the card and the "Week of …" subtitle from the modal — banner label is purely "Plan your week" since the targeting rule is implicit. Today page passes `weekPlan` into `<WeeklyCheckinCard>`. +5 vitest unit tests on `getTargetMonday` (Sun, Mon regression, Tue–Sat, month boundary, year boundary). Branch `brief/B245-plan-your-week-monday` → Vercel preview validated → FF-merge. user_guide_v1.md §12 updated. |
| B228 | **Frontend 402 global handler in `api.ts`** | B | S | Open P2 | Audit F4. Centralize 402 → router.push('/subscribe') + sonner toast. Frontend branch + Vercel preview. After both P1. |
| D229 | **Doc drift alignment — CLAUDE.md endpoints + intents + Stripe text** | D | XS | Open P2 | Audit F7. CLAUDE.md:149 says 63 endpoints (real = 67). CLAUDE.md:144 says 13+3 intents (real = 15+4). ROADMAP line 77 says "Stripe TEST MODE / disabled" vs line 153 "LIVE since 2026-04-16". 30 min, single commit, no STOP. |
| C231 | **Catalog `intensity_level` enum normalization — drift singletons** | C | XS | Open P3 | B227 P0.2 discovery: catalog uses 7-value enum (very_low, low, moderate, medium, high, very_high, max). Two drift singletons absorb cleanly via ordinal mapping (`reverse_lunge`=moderate→medium, `thirty_thirty_intervals`=very_high→high), but worth normalizing to a clean 5-value canonical set `{very_low, low, medium, high, max}`. 2 catalog edits + test_exercises_v2.py enum check. Zero engine impact. |
| D231 | **Tyler Twist closed-loop audit (read-only)** | D | S | ✅ Done (2026-05-04) | Founder-reported: Tyler Twist suggeriva sempre `+1.5 kg` ignorando il feedback. Audit ha tracciato writer (`apply_feedback`) → reader (`inject_targets._best_entry`) → fallback (`EXTERNAL_LOAD_FALLBACK_FIXED_KG`). Verdict: H1/H2/H3 falsificate. Causa root identificata: `_auto_resolve` (week.py + replanner.py) costruisce il resolve context con solo `location + gym_id`, senza `target_date`. Conseguenza: `_is_fresh(updated_at, "", 60)` fallisce sempre (stringa vuota → None) → tutte le entries `working_loads` considerate stale → fallback FIXED_KG/BW% per ogni esercizio external_load + total_load + grade_relative + loading_pin. Scope: ~15 esercizi affetti (Tyler Twist 1.5 vs 5.0, weighted_pullup 11.5 vs 27.5, bench_press 31 vs 32, etc.). Non solo prehab. Verifica end-to-end su Daniele in prod (`inject_targets` con date='2026-05-04' → 5.0 ✓; con date='' → 1.5 ✗). Fix tracciato in B246. |
| B246 | **`working_loads` stale-by-default in `_auto_resolve` — closes D231** | B | S | ✅ Done (2026-05-04) | Patch A: `backend/api/routers/{week,replanner}.py:_auto_resolve` iniettano `target_date` + `date` (alias) in `resolve_state["context"]` (+2 righe ciascuno, da `day_entry["date"]`). Patch B: `backend/engine/resolve_session.py:1346,1701` aggiungono fallback `user_ctx.target_date or user_ctx.date` (specchio del pattern già esistente per `gym_id` a line 1345). Nessuna modifica a `progression_v1.py` — la logica `_is_fresh`/60-day window è corretta, riceveva solo input mancanti. +8 test: `test_resolve_session_freshness.py` (4 — Patch B unit), `test_week_router_auto_resolve.py` (2 — Patch A end-to-end), `test_daniele_loads_snapshot.py` (2 — pin audit baseline su 6 esercizi). Verifica end-to-end post-fix su Daniele: `forearm_pronation_supination` 1.0 → 5.0 ✓, `elbow_eccentric_curl` 1.5 → 5.0 ✓. Suite 1855 → 1863 (+8, zero regressioni). Cache esistenti non retroattivamente corrette (immutabilità past sessions): solo nuove resolutions vedono il fix. Follow-up briefs out-of-scope: B-fix-H1 (frontend non-guided non manda `used_external_load_kg` → silent skip in writer), UX-fix-suggestion-prefix (`+5 kg` confuso come delta vs valore assoluto). |
| B247 | **Guided session countdown beep silent on iPhone PWA — closes D-audit 2026-05-04** | B | S | ✅ Done (2026-05-04) | Founder-reported: i 3-2-1 countdown beep negli ultimi 3 secondi non suonano su PWA iPhone, mentre il transition beep funziona. Audit (`docs/audits/D_guided_session_countdown_beep_2026-05-04.md`): `exercise-timer.tsx` era l'unico di 5 timer del repo su `setInterval(1000ms)` + gate `useEffect([secondsLeft])`. Combinato con il wall-clock fix B67 (`14faee2`, sostituì counter-decrement con `Math.ceil(remainingMs/1000)`), drift/throttling iOS poteva far saltare valori della finestra `(0, 3000]` ms — i beep venivano silenziosamente droppati. Il transition beep era robusto perché `remainingMs <= 0` è soglia aperta. Fix: tick rate `1000 → 200` ms; gate idempotente inline via `lastBeepedSecRef` (mirror del pattern già usato in `custom-rest-timer.tsx`); helper puro `shouldFireCountdownBeep` esportato per test. Reset del ref su `startCountdown` (ogni transizione di fase) e `handleReset`. Niente modifiche a audio infrastructure / pause-resume / manual skip / voice cues. +7 test (`__tests__/exercise-timer-countdown.test.ts` — happy path, tick-skip resilience, idempotency, reset, paused, fuori range, inactive phase). Push diretto a main per autorizzazione esplicita di Daniele. QA manuale iPhone PWA post-deploy Vercel da fare. |

### Phase 2 — Measure + iterate (week 3-6)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| GTM-06 | **Feature freeze** — zero new features for 30 days, only fix bugs reported by paying/trialing users | — | — | Open | Starts when first non-beta user signs up. |
| GTM-07 | **Success metric** — 3-5 paying users by end of April 2026 | — | — | Open | 0 paying after 30 days → reassess PMF. 3+ paying → validate and continue. |
| D230 | **Frontend lint hygiene — 30 errors / 38 warnings** | D | M | Open P3 | Audit F5. Mostly `react-hooks/set-state-in-effect` from React Compiler in Next 16. CI does not enforce, but debt accumulating. One afternoon, branch + preview. After GTM stability window. |

### Council recommendations (reference)

**Convergence across both runs (high confidence):**
- Launch NOW — Supabase migration is not a blocker (JSONB handles ~260KB/year/user)
- r/climbharder is the #1 acquisition channel
- Zero new features for 30 days post-launch
- Onboarding is the critical blind spot — no advisor caught it initially, both chairmen flagged it
- Don't build Kilter/Capacitor/LLM Coach before validating willingness to pay

**Divergence (Daniele decides after beta feedback):**
- Price: €14.99/mo (Run 1) vs €9.99/mo Founding Climber lock-in (Run 2)
- Synthesis: €14.99 standard + €9.99 Founding Climber for first 20-30 users

---

## Priority 2 — Auth + Payments + DB (go-to-market blockers)

Clerk auth ✅, Supabase JSONB ✅, and Stripe ✅ are complete. Stripe LIVE since 2026-04-16.

- **Supabase migration** ✅ — JSONB live in production (6 tables: users, session_logs, outdoor_logs, event_logs, recovery_codes, subscriptions)
- **A159 — Stripe subscriptions** ✅ — **LIVE** (sk_live keys on Railway + Vercel). Two-tier pricing ($9.99 Standard + $4.99 Founding Climber). B202 fail-closed guard active. B226 hardening done: fail-loud (500 → Stripe retries), LRU event dedup, customer.deleted handled. No known gaps.
  - Backend: `subscription_guard.py`, 4 endpoints (status/checkout/portal/webhook), guards on 10 POST endpoints
  - Frontend: `useSubscription()` hook, `TrialBanner`, `/subscribe` page, settings portal link, guided session gate
  - Phase 3: `onboarding/start-week` → redirect to `/subscribe` (both Continue and Skip)
  - SQL migration: `docs/migrations/subscriptions_table.sql` — ✅ run in Supabase (confirmed 2026-03-31)

### A-B6 — Session pool boulder audit & completion

**Priority:** P2 | **Status:** Open | **Type:** D + A (audit + feature) | **Effort:** M

Audit `_SESSION_POOL_BOULDER`: verify ≥3 primary sessions per phase, limit_boulder exists, board session templates exist (board_limit, board_volume), PE sessions adapted (boulder_circuit, linked_boulders), climbing_routes excluded from boulder pool, technique sessions adapted, all_round pool = union of lead + boulder.

### A-B8 — Board session templates (guided)

**Priority:** P2 | **Status:** Open | **Type:** A (catalog + template) | **Effort:** M

Three new session definitions: `board_limit_session` (6-10 problems at max, 3-5 min rest), `board_volume_session` (15-20 problems 2-3 below max, 1-2 min rest), `board_pe_session` (4x4 format, 3-4 below max). Equipment: board_kilter/board_moonboard/board_other. No board API integration.

## Priority 2.25 — Code Quality & Hardening

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R142 — Magic Numbers Extraction

**Priority:** P2.25 | **Status:** Open | **Type:** R (refactor)

- Estrarre magic numbers da `progression_v1.py` in named constants
- Spostare tabelle grade-to-score e axis weights da `assessment_v1.py` in JSON catalog

**Rischio:** BASSO — estrazione costanti

### B192 — Undo session: clear stale feedback artifacts ✅ Done (2026-04-20)

**Priority:** P1 (elevated from P2 after 2026-04-20 post-B216 QA) | **Status:** ✅ Done | **Type:** B (bugfix) | **Discovered:** A187 STOP 2 (2026-04-07), confirmed via founder-account reproduction 2026-04-20

Pre-existing bug. When a user clicks Undo on a completed session, the backend `apply_events` branch `mark_planned` (`replanner_v1.py:871`) only cleared `s["status"]` but left 4 feedback-derived fields populated: `actual_exercises`, `feedback_summary`, `exercise_feedback`, `session_duration_seconds`. The frontend `session-card.tsx:1005,1026` renders per-exercise OK badges from `session.exercise_feedback[...]` and `actual_exercises` unconditionally (no `isDone` gate), so the badges persisted after undo.

**Scope correction during Phase 1:** roadmap originally listed 6 fields including `duration_source` and `session_load_score`. Verified at HEAD: `duration_source` is never written onto the session at all (B217 Phase 1 grep confirmed it was a Potemkin field — sent by frontend, accepted by backend, never persisted anywhere server-side, including `session_completion_log`); `session_load_score` lives inside `resolved.resolved_session` as a deterministic pre-feedback field from `resolve_session.py:1690`. True feedback-derived leak = **4 fields**, not 6.

**Fix (backend only, 2 files):**
1. `replanner_v1.py:871-879` — `mark_planned` now pops the 4 feedback-derived fields on the matched session, and logs `WARNING` on no-op (session not found) for traceability (B216 lesson: never silent-swallow).
2. `week.py:154-171` — `_attach_feedback` gates on `session.status == "done"`. Without this, `feedback_log` (genuinely append-only) would re-hydrate 3 of 4 fields on every `GET /api/week`, defeating the pop.

**NOT reverted (trade-off accepted):** closed-loop progression mutations on `working_loads.entries[*].next_external_load_kg`. Reversing closed-loop is complex and undo is rare.

**Documentation drift noted (§5bis of Phase 1 analysis):** roadmap claimed `session_completion_log` is append-only. Code at `replanner.py:383-390` actively removes the matching entry on `mark_planned` (confirmed by `test_mark_planned_removes_from_completion_log`). Only `feedback_log` and `working_loads` are genuinely append-only. See `docs/lessons.md` entry 2026-04-20 B192.

**Tests:** 7 in `backend/tests/test_undo_session_B192.py` (T1 pop, T2 end-to-end 2-fetch round-trip, T3 feedback_log preserved, T4 working_loads preserved, T5 no ghost on undo→redo, T6 session-level idempotence, T7 no-op+warning on unknown session).

**Rischio:** BASSO — single branch in `apply_events` + reader-side gate. Sibling branches (`mark_skipped`, `apply_day_override`, `move_session`, `remove_session`) audited clean in Phase 1.

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

## Priority 2.75 — KB Research Integration

> **Companion project:** The KB research lives in a **separate claude.ai project** called **"climb-agent knowledge base"**.
> All research files, Hörst syntheses, topic files, and decision consolidations live in that project's knowledge.
>
> **⚠️ RULE: Before implementing any deferred decision from the backlog below, open the KB project and check
> `_archive/docs/horst_integration_audit.md` for enrichment material. Many deferred decisions have ready-to-use content.**

### Open KB Research Items

| Item | Status | Where |
|------|--------|-------|
| Session 2 patch (4 corrections: D11, D12, D39, D72) | ⏸️ Prepared | KB project memory (not yet a file) |
| D84 pulling strength test (max load review) | ⏸️ Under review | KB project |
| Finger strength test architecture (5s→7s Lattice) | ⏸️ Under review | KB project |
| CUE-02 formalize (forearm stretch → D33 amendment) | 📋 Proposed | `_archive/docs/horst_integration_audit.md` §6 |
| Coach KB spec: add 8 Hörst coaching cues | 📋 Proposed | `_archive/docs/horst_integration_audit.md` §5 |
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

Audit deliverable: `docs/outdoor_audit_D170.md` (2026-04-04) — 13 findings (2 P1, 5 P2, 6 P3), 5 redesign recommendations. Root cause of outdoor+indoor coexistence bug identified (F1: `add_outdoor` doesn't clear sessions).

---

## Priority 3 — UI polish

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B40 | Branch develop/main workflow | S | Staging/production branches |
| R148 | Centralize weakness→axis mapping | S | Single dict in assessment_v1.py instead of scattered if-strings. Prerequisite for R149 and LLM Coach. LOW risk. |

### Stretching Circuit add-on

**Status:** Open — design pending | **Effort:** M
Same architecture as Core Circuit for post-session static stretching (30-60s holds).

### Warmup Circuit add-on

**Status:** Open — design pending | **Effort:** M
Same architecture for pre-session dynamic warmup (30s work / 10s transition).

### Smart planner availability suggestions

**Priority:** P3 (post-launch) | **Status:** Open | **Type:** A (engine + frontend) | **Effort:** M

When the planner struggles to fit sessions into the user's availability (e.g., too many skips, spacing violations, key sessions dropped), surface proactive suggestions:
- "Your plan needs 2 hard climbing sessions per week, but you only have 1 gym slot. Consider adding a gym day on Wednesday."
- "Finger training on Monday and Wednesday violates the 48h spacing rule. Try moving Wednesday's session to Thursday."

**Implementation:** After `planner_v2` generates a week, run a diagnostic pass checking: sessions dropped vs requested, spacing violations resolved by skipping, equipment mismatches forcing substitutions. If diagnostic score is below threshold → generate suggestion(s) as structured data. Frontend: suggestion card on Week view ("Optimize your schedule" expandable). User can accept → triggers availability update + replan.

**Depends on:** Nothing (standalone diagnostic layer on top of existing planner).
**Origin:** GTM-01 dry-run insight (2026-04-01) — if the plan looks weak because of bad availability input, the user blames the app, not their schedule.

---

## Priority 4 — Go-to-market

- Landing page / marketing site
- ~~Pricing model definition~~ ✅ Decided: EUR 14.99/month, 14-day trial, Founding Climber EUR 9.99 lifetime for first 50 users

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
Design spec: `_archive/docs/coach_knowledge_base_spec.md`

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
- Season reset (partial re-onboarding)
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
| D15 | Progressive ARC duration | XS | Confirmed by D44 + D45. ARC duration increases progressively within Base phase. Covered by current implementation (4wk base with floor=2wk). |

**Warm-Up & Recovery (mega brief Sessions 4, 7)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D33 | Dedicated `generate_warmup()` function | M | 5-phase protocol generator. **⚠️ KB: Ch. 6 has warm-up exercises + CUE-02 (no forearm flexor stretch pre-performance). See `_archive/docs/horst_integration_audit.md` §5-§6.** |
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
| R160 | Audio util dedup: beep/countdownTick/transitionBeep duplicated in CircuitTimer and Tabata — extract to single shared module in lib/ | B160 audit 2026-03-26 |
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
