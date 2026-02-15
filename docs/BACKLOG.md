# BACKLOG — climb-agent

> Last updated: 2026-02-15 (post Phase 3 — UI)

Features to implement in upcoming phases. For each: title, description,
suggested phase, dependencies.

---

## TODO

### B1. Standalone core session

- **Description**: Session `core_conditioning_home.json` for lunch slot (30-45min). Intensity "low"/"medium", domain core + prehab. Ab wheel, hollow hold, pallof press, dead bug, front lever progressions.
- **Suggested phase**: Phase 1.75
- **Dependencies**: None (exercise catalog already has core exercises)
- **Notes**: Goes in the pool of all phases as complementary (Pass 2). Incorporated in B8.

### B2. Outdoor sessions

- **Description**: Sessions like `projecting_outdoor`, `volume_outdoor`. Intent "outdoor" in the replanner. Outdoor is NOT a session resolved by the engine: it's logging of what the user does at the crag, with grades/style/attempts.
- **Suggested phase**: Phase 2 (tracking)
- **Dependencies**: Trip planning, feedback contract
- **Notes**: Integration with trip planning (pre-trip deload now working). Outdoor logging has a different schema from resolved indoor sessions. F14 (outdoor not supported) is tracked here.

### B3. Plan validation vs literature

- **Description**: Compare macrocycle structure with:
  - Hörst "Training for Climbing" — volume/intensity ratio per phase, 4-3-2-1 durations, hard day distribution (2-3/week)
  - Lattice Training — finger training frequency and protocols
  - Eva López — finger strength periodization
- **Output**: Report "aligned" vs "deviates and why"
- **Suggested phase**: Phase 1.75 (incorporated in B8)
- **Dependencies**: None (documentary analysis)

### B4. Load score / weekly fatigue

- **Description**: Each session in the planner should have an `estimated_load_score`. Numeric model TBD: RPE-based? stress tag aggregation? TRIMP-like? Simple placeholder (low=20, medium=40, high=65, max=85)?
- **Output**: Weekly summary with total load, hard days count, comparison vs target
- **Suggested phase**: Phase 1.75 (incorporated in B8)
- **Dependencies**: `load_model_hint` in sessions (partial, see strength_long)
- **Notes**: Needed for: overtraining monitoring, adaptive deload input, UI visualization

### B8. Session enrichment and modules (from literature)

- **Description**: Literature review (Hörst "Training for Climbing", Lattice "How to Structure Your Training" 2025, Hooper's Beta, Eva López) shows:
  - Evening sessions 1.5-2h should have 5-7 blocks, not 2-3
  - Target structure for evening strength session: warmup → finger → pulling strength → climbing on wall → core → antagonist/prehab → cooldown
  - Missing templates: pulling_strength (weighted pullup, lock-off), antagonist_prehab (push-up, dip, rotator cuff), limit_bouldering
  - Core should not be optional but standard in every evening session
  - Antagonists year-round (Lattice: "should be included year round")
  - Evening PE session: 4x4/intervals + route volume + core + antagonist
- **Incorporates**: B1 (standalone core), B3 (literature validation), B4 (load score)
- **Suggested phase**: Phase 1.75 (before Phase 2)
- **Dependencies**: Resolver inline blocks (done), pulling/antagonist exercise catalog (partial, needs expansion)

### B9. Add cable_machine, leg_press to gym equipment

- **Description**: Add `cable_machine` and `leg_press` to vocabulary_v1.md §1.2 and to EQUIPMENT_GYM in `backend/api/routers/onboarding.py`. Many gyms have these; useful for antagonist/conditioning sessions.
- **Suggested phase**: Phase 3.1
- **Dependencies**: None

### B10. Outdoor climbing spots as location type

- **Description**: Allow users to register outdoor climbing spots (e.g. "Berdorf — boulder — weekends") as a new location type. Usable in the availability grid and trip planning. Bridges the gap between indoor training and outdoor tracking.
- **Suggested phase**: Phase 3.1
- **Dependencies**: B2 (outdoor sessions)

### B11. Configurable test protocols

- **Description**: Let user choose test protocol variants (5s or 7s hang, 1RM or 2RM pullup) with automatic conversion to the engine's internal benchmark format. Currently the engine only supports 5s/20mm max hang and 1RM pullup.
- **Suggested phase**: Phase 3.1
- **Dependencies**: None

---

## DONE

### ~~B5. Replanner phase-aware + complete intents [F6, F7]~~ ✅

- **Resolved in**: Cluster 2, commit fix(F6,F7)
- **Status**: Replanner now uses planner_v2 `_SESSION_META`, 12 intents mapped, `phase_id` propagated

### ~~B6. PE assessment — repeater test + no double counting [F5]~~ ✅

- **Resolved in**: Cluster 2, commit fix(F5)
- **Status**: `_compute_power_endurance()` uses repeater test (40%) + gap (40%) + self_eval (20%). Penalties reduced.

### ~~B7. Edge case validations [F8, F9, F10]~~ ✅

- **Resolved in**: Cluster 2, commits fix(F9), fix(F10), fix(F8)
- **Status**:
  - Goal validation: warning if target ≤ current or gap > 8 half-grades
  - Minimum floor: 2 weeks per non-deload phase
  - Pre-trip deload: `pretrip_dates` blocks hard sessions, flag in plan

### ~~B12. Auto-assign highest-priority gym~~ ✅

- **Resolved in**: Phase 3, Fix 4
- **Status**: Week router sorts gyms by priority and assigns `default_gym_id` to sessions with location "gym" and no explicit gym selected.

### ~~B13. Auto-resolve week sessions~~ ✅

- **Resolved in**: Phase 3, Fix 1
- **Status**: GET `/api/week/{week_num}` now auto-resolves each session inline so the frontend receives exercises without a second call.

### ~~B14. Day navigation in week view~~ ✅

- **Resolved in**: Phase 3, Fix 6
- **Status**: Clicking a day in the week grid scrolls to the detailed day card. Week page shows both grid overview and day-by-day detail.
