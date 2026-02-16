# BACKLOG — climb-agent

> Last updated: 2026-02-16 (post Phase 3.1 — bug fixes)

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

### B19. Quick-add session

- **Description**: Add an extra session to any day/slot from the week view. Suggest session type based on current phase and weekly balance (e.g. recovery if hard cap near, technique if underrepresented). Replanner creates the session inline without regenerating the whole week.
- **Suggested phase**: Phase 3.1
- **Dependencies**: Replanner event system (done)

### B20. Edit availability from Settings

- **Description**: Allow users to modify their weekly availability (days, slots, preferred locations) from the Settings page. Changes trigger plan regeneration for the current week using the replanner's `set_availability` event. Avoids requiring a full re-onboarding to adjust schedule.
- **Suggested phase**: Phase 3.1
- **Dependencies**: Settings page (done), set_availability event handler (done)

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

### ~~B15. Show gym name instead of 'gym'~~ ✅

- **Resolved in**: Phase 3, Fix A
- **Status**: SessionCard and DayCard accept a `gyms` prop. Location badge shows the actual gym name (from `gym_id` / `equipment.gyms`) instead of generic "gym". Pages fetch state to pass gym data down.

### ~~B16. Exercise card full prescription format~~ ✅

- **Resolved in**: Phase 3, Fix B
- **Status**: ExerciseCard shows `4 × 8 @ 25kg — Rest 2:00` format. Uses × (multiplication sign), @ for load, — (em dash) before rest, mm:ss rest format. Shows "bodyweight" if load_kg is 0. Tempo and notes always visible (no expand/collapse).

### ~~B17. Date query parameter on Today page~~ ✅

- **Resolved in**: Phase 3, Fix C
- **Status**: Today page accepts `?date=YYYY-MM-DD` to view any day's plan. "View day" button on each day card in week view links to `/today?date=YYYY-MM-DD`. Title adapts to show day name when viewing a non-today date.

### ~~B18. Replan dialog with auto-resolve~~ ✅

- **Resolved in**: Phase 3, Fix D
- **Status**: "Change plan" button on each day card in week view opens a replan dialog. Dialog lets user pick location (Home / gym names) and intensity (Rest / Easy / Hard), or skip the day entirely. Backend `POST /api/replanner/override` supports `target_date` and `gym_id` params, and auto-resolves all sessions in the returned week plan. `apply_day_override` updated with ripple day error handling.

### ~~B21. Done button removes session instead of keeping it~~ ✅

- **Resolved in**: Phase 3.1, Bug 1
- **Status**: `mark_done` now sets `session.status = "done"` and keeps the session in `day.sessions`. Day status set to "done" when all sessions are done. Constraint functions (`_enforce_caps`, `_enforce_no_consecutive_finger`) skip done sessions. Frontend hides action buttons and shows "Completed" badge.

### ~~B22. Events endpoint missing auto-resolve~~ ✅

- **Resolved in**: Phase 3.1, Bug 2
- **Status**: `/api/replanner/events` now calls `_auto_resolve()` before returning, matching the `/override` endpoint. Recovery sessions from `mark_skipped` return with resolved exercises.

### ~~B23. Skip doesn't visually update day status~~ ✅

- **Resolved in**: Phase 3.1, Bug 3
- **Status**: `mark_skipped` now sets `day["status"] = "skipped"` and `recovery["status"] = "skipped"` on the replacement session. DayCard correctly shows "Skipped" badge.

### ~~B24. Gym equipment label corrections~~ ✅

- **Resolved in**: Phase 3.1, Fix 4
- **Status**: `gym_boulder` label "Boulder area" → "Bouldering area", `gym_routes` label "Roped routes" → "Lead / Top-rope walls".
