# D164 — Test Coverage Audit

**Data**: 2026-03-27
**Scope**: `backend/tests/`, `backend/engine/`, `backend/api/`

---

## 1. Test Suite Health

```
1402 passed, 3 warnings in 4.26s
```

- **Total test functions**: ~1397 (across 78 test files)
- **All green**: Zero failures, zero errors
- **Warnings**: 3x `DeprecationWarning` from `jsonschema.RefResolver` in `schema_registry.py` (deprecated since jsonschema v4.18.0, should migrate to `referencing` library)
- **Slowest test**: `test_all_weeks_return_valid_plans` at 0.37s — no slow tests at all
- **No flaky tests detected**

---

## 2. Coverage Summary Table

| Module | Test File(s) | Test Count | Public Functions | Tested | Untested |
|--------|-------------|-----------|-----------------|--------|----------|
| `planner_v2.py` | test_planner_v2 (122), test_planner_v1 (9), test_test_week (16), test_youth_cap (7), test_b159 (17), test_b94 (4), test_availability_edit (7), test_weekly_override (18), test_quick_add (14), test_p0_fixes (16), test_d154 (23) | ~253 | 3 (`generate_phase_week`, `generate_test_week`, `should_show_test_reminder`) | 3 | 0 |
| `replanner_v1.py` | test_replanning_v1 (58), test_merge_prev_week (32), test_quick_add (14), test_b114 (17), test_loading_pin (51) | ~172 | 6 (`suggest_sessions`, `apply_day_add`, `merge_prev_week_sessions`, `regenerate_preserving_completed`, `apply_events`, `apply_day_override`) | 6 | 0 |
| `resolve_session.py` | test_resolver_p0 (24), test_resolver_enhancements (18), test_resolve_real_sessions (17), test_warmup_b93 (7), test_limitations (41), test_hangboard_gates (8), test_loading_pin (51), test_session_enrichment (27), test_baseline_session_under_test (3) | ~196 | 23 (public) | ~15 | ~8 (utility helpers) |
| `progression_v1.py` | test_progression_v1 (8), test_feedback_loop_e2e (8), test_session_1b (38), test_test_session_e2e (31), test_update_test_from_log (25), test_pulling_baseline_b121 (26), test_loading_pin (51), test_grade_arithmetic (9), test_b133 (15) | ~211 | 8 | 8 | 0 |
| `closed_loop_v1.py` | test_closed_loop_v1 (4), test_closed_loop_hardening (41) | ~45 | 3 (`ensure_planning_defaults`, `build_log_entry`, `apply_day_result_to_user_state`) | 3 | 0 |
| `adaptation/closed_loop.py` | test_closed_loop_adaptation (3), test_closed_loop_hardening (41) | ~44 | 3 (`compute_next_multiplier`, `apply_multiplier`, `update_user_state_adjustments`) | 3 | 0 |
| `macrocycle_v1.py` | test_macrocycle_v1 (63), test_macrocycle_boulder (18), test_b119 (21), test_p0_fixes (16) | ~118 | 6 (`generate_macrocycle`, `apply_deload_week`, `check_pretrip_deload`, `compute_pretrip_dates`, `should_extend_phase`, `should_trigger_adaptive_deload`) | 6 | 0 |
| `assessment_v1.py` | test_assessment_v1 (28), test_brzycki (12), test_reds_guardrails (3) | ~43 | 4 (`grade_index`, `grade_gap`, `brzycki_1rm`, `compute_assessment_profile`) | 4 | 0 |
| `exercise_ordering.py` | test_a121_exercise_ordering (48), test_a121_sort_category_audit (3) | ~51 | 3 (`infer_sort_category`, `sort_exercises_by_phase`, `enforce_ordering_constraints`) | 3 | 0 |
| `equipment_utils.py` | test_b159_boulder_surface_equivalence (17) | ~17 | 1 (`expand_equipment`) | 1 | 0 |
| `cluster_utils.py` | test_replanner_v0_cluster_cooldown (3) | ~3 | 6 (`norm_str`, `as_list`, `norm_list_str`, `sorted_join`, `cluster_key_for_exercise`, `parse_date`) | 1 | 5 |
| `adaptive_replan.py` | test_adaptive_replan (15), test_a139_actual_exercises (7) | ~22 | 4 (`load_exercises_by_id`, `append_feedback_log`, `check_adaptive_replan`, `apply_adaptive_replan`) | 4 | 0 |
| `cues.py` | test_process_cues (14) | 14 | 1 (`get_session_cue`) | 1 | 0 |
| `free_session.py` | test_free_session (100) | 100 | 11 | ~8 | ~3 (internal helpers: `font_to_index`, `index_to_font`, `is_lead_surface`) |
| `outdoor_log.py` | test_outdoor (81), test_d151 (23) | ~104 | 7 | 7 | 0 |
| `report_engine.py` | test_reports (91) | 91 | 2 (`generate_weekly_report`, `generate_monthly_report`) | 2 | 0 |
| `quotes_engine.py` | test_quotes (23) | 23 | 3 (`detect_quote_context`, `get_quote_for_session`, `update_quote_history`) | 3 | 0 |
| `state_checks.py` | test_state_checks (13) | 13 | 1 (`is_macrocycle_stale`) | 1 | 0 |
| `conversions.py` | test_conversions (12) | 12 | 3 (`hangboard_to_loading_pin`, `loading_pin_to_hangboard`, `convert_duration_max`) | 3 | 0 |
| `weekly_override.py` | test_weekly_override (18) | 18 | 3 (`merge_override_into_availability`, `build_merged_view`, `build_slot_view`) | 3 | 0 |
| `schema_registry.py` | test_schema_validation (3) | 3 | 2 (`SchemaRegistry`, `validate_instance`) | 2 | 0 |
| `validate_log_entry.py` | test_log_pipeline (3) | 3 | 2 (`validate_entry`, `main`) | 1 | 1 (`main`) |

---

## 3. API Router Integration Test Coverage

**Test files using TestClient**: test_api (84), test_free_session (100), test_outdoor (81), test_reports (91), test_admin (13), test_multiuser (13), test_user_export_import (11), test_quotes (23), test_weekly_override (18), test_b119_start_date_monday (21), test_p0_equipment_regen (7)

### Tested endpoints (via TestClient)

| Router | Endpoints | Tested via TestClient | Notes |
|--------|----------|----------------------|-------|
| `state` | GET/PUT/DELETE `/api/state`, GET `/api/state/status` | GET, PUT, DELETE tested | **`GET /api/state/status` — NOT TESTED** |
| `catalog` | GET exercises, GET sessions | Both tested | Good |
| `onboarding` | GET defaults, POST complete, POST start-week | All tested | Good |
| `assessment` | POST compute | Tested | Good |
| `macrocycle` | POST generate | Tested | Good |
| `week` | GET `/{week_num}`, POST test-reminder-response | GET tested | **`POST /api/week/test-reminder-response` — NOT TESTED via API** |
| `session` | POST resolve, POST add-exercise, POST remove-exercise | All tested | Good |
| `replanner` | POST override, POST events, GET suggest-sessions, POST quick-add | override + events tested | **`GET /api/replanner/suggest-sessions` — NOT TESTED via API** (unit-tested in test_quick_add) |
| | | | **`POST /api/replanner/quick-add` — NOT TESTED via API** (unit-tested) |
| `feedback` | POST feedback | Tested | Good |
| `outdoor` | All 8 endpoints | Most tested | **`POST /api/outdoor/convert-slot` — NOT TESTED** |
| `reports` | GET weekly, GET monthly | Both tested | Good |
| `quotes` | GET daily | Tested | Good |
| `user` | GET export, POST import, POST recovery-code, POST recover | export + import tested | **`POST /api/user/recovery-code` — NOT TESTED** |
| | | | **`POST /api/user/recover` — NOT TESTED** |
| `weekly_override` | GET/PUT/DELETE `/{week_start}` | **NOT TESTED via API** | Only engine-level tests exist |
| `free_session` | All 7 endpoints | Most tested | **`DELETE /api/free-session/{session_id}` — NOT TESTED** |
| `admin` | GET users, DELETE users/{uuid} | GET tested | **`DELETE /api/admin/users/{uuid}` — NOT TESTED** |

### Summary: Untested API endpoints (9 total)

| Endpoint | Severity | Notes |
|----------|----------|-------|
| `GET /api/state/status` | **P2** | Stale-state detection — tested at engine level via test_state_checks |
| `POST /api/week/test-reminder-response` | **P2** | Test reminder flow — engine-level tested in test_test_week |
| `GET /api/replanner/suggest-sessions` | **P3** | Unit-tested via test_quick_add, missing API integration |
| `POST /api/replanner/quick-add` | **P3** | Unit-tested via test_quick_add, missing API integration |
| `POST /api/outdoor/convert-slot` | **P2** | No test at any level |
| `POST /api/user/recovery-code` | **P1** | Auth-critical, no test at any level |
| `POST /api/user/recover` | **P1** | Auth-critical, no test at any level |
| `GET/PUT/DELETE /api/weekly-override/{week_start}` | **P2** | Engine tested, API routes not integration-tested |
| `DELETE /api/free-session/{session_id}` | **P3** | CRUD delete, low risk |
| `DELETE /api/admin/users/{uuid}` | **P3** | Admin-only, low traffic |

---

## 4. Test Quality Analysis

### Assertion density

All 78 test files contain assertions. Using unittest-style `self.assert*` (most files) and pytest-style `assert` (some files).

- **Lowest density**: ~1.0 asserts/test in a few files (test_b159, test_b94, test_catalog_safety, test_catalog_validation)
- **Highest density**: test_closed_loop_hardening (~6.4 asserts/test), test_reports (~4.5 asserts/test)
- **Average**: ~2-3 asserts/test across the codebase — reasonable

### Tests that only check "no exception"

- `test_resolve_real_sessions.py` — `test_no_failed_blocks` and `test_all_sessions_produce_exercises` verify structural output but some tests only check `len > 0`. **P3** — acceptable for smoke tests.
- Several planner tests confirm plan structure (`len(days) == 7`, `phase == "base"`) but don't deeply validate session selection logic. **P3** — covered by higher-level E2E tests.

### Overly broad assertions

No significant issues found. Most tests assert specific values, structure, and behavior.

---

## 5. Fixture Analysis

### Fixture files (`backend/tests/fixtures/`)

| File | Purpose | Status |
|------|---------|--------|
| `test_user_state.json` | Full user state for resolver/planner tests | **Current** — contains valid assessment, profile, macrocycle, availability |
| `log_good.json` | Valid log entry for schema validation | Current |
| `log_invalid_deep.json` | Invalid log for schema validation | Current |
| `log_invalid_shallow.json` | Invalid log for schema validation | Current |

### Inline fixtures

Most tests use inline helper functions (`_make_kwargs()`, `_base_availability()`, `_make_assessment()`, etc.) rather than shared fixtures. This is good for isolation but means:

- **Pro**: Tests are self-contained, no hidden coupling
- **Con**: Fixture duplication across files — e.g., `_base_availability()` is redefined in ~10+ test files with slight variations
- **Risk**: If the canonical availability schema changes, many test helpers need updating. **P3** — manageable.

### Fixture staleness

- `test_user_state.json` has `finger_strength: 100`, `pulling_strength: 100` — extreme values. Not representative of a typical user. **P3** — intentional for edge-case testing.
- Date strings in fixtures (`2026-02-16`, `2026-01-13`) are still in the future from today's perspective — no staleness issue.

---

## 6. Critical Untested Scenarios

### P1 — Must fix

| Scenario | Details |
|----------|---------|
| **Recovery code flow** | `POST /api/user/recovery-code` and `POST /api/user/recover` have zero tests. These are auth-critical endpoints for account recovery (CLIMB-XXXX codes). A bug here could lock users out. |
| **Full pipeline E2E with feedback loop** | While individual modules are well-tested, there is no single test that runs: assessment -> macrocycle -> planner -> resolver -> guided session -> feedback -> progression update -> next week generation. `test_feedback_loop_e2e.py` covers feedback -> progression but not the full pipeline. |

### P2 — Should fix

| Scenario | Details |
|----------|---------|
| **Outdoor convert-slot** | `POST /api/outdoor/convert-slot` — no test at any level. Could silently break. |
| **Weekly override API routes** | Engine logic tested but HTTP layer (validation, error codes, persistence) not tested. |
| **Phase transitions** | No explicit test verifying correct behavior when a user transitions between macrocycle phases (e.g., base -> strength_power week boundary). Implicit in planner tests but not targeted. |
| **Multi-week navigation with feedback** | Tests verify done sessions survive navigation, but not that feedback from week N correctly influences week N+1 session selection/loads. |

### P3 — Nice to have

| Scenario | Details |
|----------|---------|
| **Concurrent access** | No concurrent/parallel access tests. Single-user file storage mitigates risk, but Supabase backend could face race conditions. |
| **Multi-user isolation (deeper)** | `test_multiuser.py` has 13 tests verifying UUID isolation, but doesn't test concurrent operations between users. |
| **Immutability invariant** | Well-tested (test_loading_pin B120 pillar, test_b114, test_d154, test_api A153) — **no gap here**. |
| **cluster_utils utility functions** | 5/6 public functions untested (`norm_str`, `as_list`, `norm_list_str`, `sorted_join`, `parse_date`). Simple utilities, low risk. |

---

## 7. Module-Level Coverage Gaps

### Well-covered modules (no gaps)

- `planner_v2.py` — 253+ tests across 11 files
- `replanner_v1.py` — 172+ tests across 5 files
- `progression_v1.py` — 211+ tests across 9 files
- `macrocycle_v1.py` — 118+ tests across 4 files
- `closed_loop_v1.py` + `adaptation/closed_loop.py` — 89+ tests across 3 files
- `report_engine.py` — 91 tests
- `outdoor_log.py` — 104+ tests
- `free_session.py` — 100 tests
- `exercise_ordering.py` — 51 tests
- `assessment_v1.py` — 43 tests

### Modules with minor gaps

| Module | Gap | Severity |
|--------|-----|----------|
| `resolve_session.py` | Helper functions (`get_ex_tags`, `get_ex_equipment`, `ex_patterns`, `ex_roles`, `ex_domains`, `load_user_state`, `now_iso`, `norm_str`) not directly tested — but exercised indirectly through `resolve_session()` and `pick_best_exercise_p0()` | **P3** |
| `cluster_utils.py` | 5 of 6 public functions untested (only `cluster_key_for_exercise` tested) | **P3** |
| `validate_log_entry.py` | `main()` CLI entry point untested | **P3** |
| `storage.py` / `storage_file.py` / `storage_supabase.py` | No direct unit tests for storage backends — tested implicitly through API tests | **P3** |

---

## 8. Recommendations

### Priority 1 (should address soon)

1. **Add integration tests for recovery-code endpoints** — `POST /api/user/recovery-code` and `POST /api/user/recover`. These are user-facing account recovery features with zero test coverage.
2. **Add a full-pipeline E2E test** — assessment -> macrocycle -> planner -> resolver -> feedback -> next week, in a single test, verifying the feedback actually changes next week's outputs.

### Priority 2 (next sprint)

3. **Add API integration tests for weekly-override routes** — `GET/PUT/DELETE /api/weekly-override/{week_start}`.
4. **Add test for `POST /api/outdoor/convert-slot`** — currently zero coverage.
5. **Add explicit phase-transition tests** — verify week plans change correctly at phase boundaries.
6. **Migrate jsonschema from RefResolver** — address the 3 deprecation warnings before jsonschema removes it.

### Priority 3 (backlog)

7. **Extract shared test fixtures** — consolidate `_base_availability()`, `_make_kwargs()` duplicates into a `conftest.py`.
8. **Add cluster_utils unit tests** — simple utilities but good for completeness.
9. **Add storage backend unit tests** — especially for Supabase error handling paths.

---

## 9. Overall Assessment

**Rating: Strong** — The test suite is comprehensive, fast (4.3s for 1402 tests), and well-organized. Engine modules have deep coverage with targeted regression tests for specific bugs (B94, B101, B114, B119, B120, B133, B157, B159). The main gaps are in API integration testing for newer endpoints (recovery, weekly-override, convert-slot) and the absence of a true end-to-end pipeline test. The immutability invariant — the project's most critical non-negotiable — is thoroughly tested from multiple angles.
