# D251 — Frontend ↔ Backend Coherence Audit

**Date:** 2026-07-03
**Method:** 4 parallel read-only agents — (1) API contracts, (2) types/enums, (3) user_state schema, (4) feature coverage. Every finding re-verified against code before acceptance.

## Summary

| Dimension | Verdict |
|-----------|---------|
| API contracts (method/path/params/body) | ✅ Clean — ~60 FE calls vs ~70 BE routes, zero mismatches |
| Types/enums | 1 CRITICAL (phase labels), rest aligned |
| user_state schema | 1 CRITICAL (bodyweight sync), 6 warnings |
| Feature coverage | 0 broken flows, 3 orphan endpoints, 2 UX gaps |

## CRITICAL — fixed in this remediation

### C1. Macrocycle timeline keyed on `energy_system` instead of `phase_id` → **B269 ✅**
`macrocycle-timeline.tsx:57,58,60,95` and `plan/page.tsx:276` fed `phase.energy_system` (values: `aerobic`, `anaerobic_alactic`, `anaerobic_lactic`, `specific`, `recovery` — from `macrocycle_v1.py::PHASE_ENERGY`) into `PHASE_COLORS`/`PHASE_TEXT`/`getPhaseName(Short)`, which are keyed on `phase_id`. Every lookup missed → all phase bars gray (`bg-gray-300`) and labels rendered as raw tokens ("aerobic", "anaerobic alactic") on `/plan`. Fix: key on `phase.phase_id` (matching the correct usage already present in `week/page.tsx:993`).

### C2. Settings body-weight edits never reach the load engine → **B270 ✅**
The Profile editor wrote weight/height only under `assessment.body` (`profile-assessment-editor.tsx` → `putState({assessment: patch})` in `settings/page.tsx`). But `progression_v1.py::_get_bodyweight` and `resolve_session.py::suggest_max_hang_load` read top-level `bodyweight_kg` / `body.weight_kg` — which only onboarding sets. Worse, `_ALLOWED_STATE_KEYS` (`state.py`) blocked `body`/`bodyweight_kg`, so no PUT could fix the drift: max-hang added-weight suggestions kept using the onboarding-era bodyweight forever. Fix: allow-list `body` + `bodyweight_kg` (B270 test added in `test_api.py`), and Settings now mirrors weight/height to the top-level copies in the same PUT.

## WARNING — open, tracked in roadmap

- **W1. `performance.current_level` stale on grade edits** — onboarding builds it (`onboarding.py:298`), `progression_v1.py:377` reads `boulder.worked.grade` for kilter benchmarks, but Settings grade edits never refresh it and `performance` is not PUT-allowed.
- **W2. `self_eval` weaknesses have no Settings editor** — drives every axis penalty in `assessment_v1.py` but is frozen after onboarding.
- **W3. Legacy `_day_meta` survives availability saves** — `availability-editor.tsx` migrates `_day_meta.other_activity` to per-slot `other_sport` on load but never clears the legacy key on save; `planner_v2.py:699` reads both → possible double-count for pre-migration users.
- **W4. Goal editor boulder-grade convention** — onboarding maps boulder targets through `BOULDER_TO_LEAD` before assessment (`onboarding.py:381`); the Settings GoalEditor sends the raw Font grade into lead-calibrated benchmarks. Verify intended behavior.
- **W5. 402 backstop UX** — only the start-new-cycle dialog maps 402 → subscribe prompt; other gated mutations surface raw `API 402: ...` if they race past the client-side gate.
- **W6. Onboarding re-entry hardcodes `home_enabled: true`** (`onboarding-context.tsx:96`) and drops `equipment_other`/`gym_id` on rehydrate.
- **W7. Orphan endpoints** — `GET /api/reports/monthly` (client fn exists, never called, no page); `POST /api/user/recovery-code` + `/recover` (dead post-Clerk); `POST /api/week/test-reminder-response` (tests only). Candidates for wiring or removal.
- **W8. Dead field `limitations.has_recent_injury`** — written at onboarding, read by nothing.
- **W9. TS `UserState` type is thin** — missing `body`, `bodyweight_kg`, `performance`, `preferences`, `baselines`, `working_loads` → `as Record<string, unknown>` casts hide exactly the drifts in C2/W1.

## Doc fixes in this remediation

- `vocabulary_v1.md` §6.4: removed `repeat` from free-session `climb_style` (backend `VALID_CLIMB_STYLES` rejects it; `repeat` is outdoor-only).

## Verified-clean highlights (no action)

Replan intents (15+4), phase ids, feedback levels (5), discipline/grade scales (Font internal, V-scale render-only), outdoor day_type/route_profile/condition bands, free-session enums, session/day status, deep-merge array semantics for all editors, weather-503 and paused-409 handling, route ordering in routers, all internal nav targets.
