# climb-agent — Active Roadmap

> Last updated: 2026-03-07
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Priority 1 — Stability and bug fixes

Open items that affect production reliability or core UX.

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B48 | Edit single session (multi-session day) | M | "Change plan" should only affect the selected session, not the whole day. Offer "Replan rest of week" after. |
| B37 | Add exercise to existing session | M | Allow users to append an exercise to a resolved session. |
| B38 | Injuries filter (contraindications) | M | Resolver should filter out exercises matching user's active contraindications/limitations. Related to UI-9. |
| UI-9 | Limitation filtering in resolver | M | Verify and enforce limitation-based exercise filtering in resolve_session. |
| B42 | Sunday reminder — confirm next week availability | S | Weekly push/banner asking user to confirm next week's schedule. From beta feedback (FB-3). |
| UI-25 | Test Maxes & Loads panel (Plan tab) | L | Collapsible card: test history timeline, benchmark comparison, exercise loads list. See ROADMAP_v2.md §9.5 for full spec. |
| FR-4 | Outdoor vs gym slot priority preference | S | When both outdoor and gym available same day, user sets preference (outdoor-first / gym-first / alternate). See ROADMAP_v2.md §9.3-9.4. |

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
| B37 | Add exercise to existing session | User can append exercises to a resolved session (also listed in P1). |
| B38 | Injuries filter (contraindications) | Resolver respects user limitations (also listed in P1). |
| — | Override intensity cap warning | Warn when user overrides with session above current phase intensity cap. |
| — | P1 ranking in resolver | Recency, intensity, and fatigue-based exercise prioritization. |
| — | Advanced adaptivity | Readiness score, overreach detection, plateau detection (DESIGN_DOC §4.4 spec). |

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
