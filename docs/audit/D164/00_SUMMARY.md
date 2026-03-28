# D164 Pre-Launch Audit — Consolidated Summary

> Date: 2026-03-28
> Subagents completed: 10/10

## Overall Health

- **Total findings: 138**
- **P1 (launch blockers): 6**
- **P2 (fix soon): 54**
- **P3 (backlog): 78**

---

## P1 Findings — Must Fix Before Launch

### Frontend
| ID | Finding | Agent |
|----|---------|-------|
| **F1-P1-001** | Profanity in voice cues ("Vaffanculo!", "Punani!") spoken aloud via TTS during timer work phases at 30% probability — reputation risk for a paid product | Agent 1 |
| **F1-P1-002** | `useSearchParams()` without Suspense boundary in `session/[id]/page.tsx` — causes Next.js 14 build/SSR crash | Agent 1 |

### Planner/Replanner
| ID | Finding | Agent |
|----|---------|-------|
| **F3-P1-009** | Replanner hardcodes finger/hard spacing to 1-day gaps, ignoring `recovery_multiplier` for 40+ users. Initial planning respects it but any replanner action (override, quick-add, gym change) uses insufficient spacing | Agent 3 |

### Exercise Catalog
| ID | Finding | Agent |
|----|---------|-------|
| **F7-P1-001** | Unknown vocabulary value `lead_wall` in `fall_practice.equipment_required_any` — resolver may fail to match | Agent 7 |
| **F7-P1-002** | Unknown vocabulary value `grip_transition` pattern in `grip_transitions_half_to_open` — P0 filter may mishandle | Agent 7 |

### Test Coverage
| ID | Finding | Agent |
|----|---------|-------|
| **F10-P1-001** | `POST /api/user/recovery-code` and `POST /api/user/recover` have zero test coverage at any level — auth-critical endpoints | Agent 10 |

---

## P2 Findings — Fix Within 2 Weeks of Launch

### Security & Data Integrity (9 items — Agent 2)
- Non-atomic file writes in `storage_file.py` risk state corruption on crash
- Error messages leak internal Python exception details (~15 endpoints)
- No rate limiting on any endpoint (recovery code brute-force risk)
- Recovery codes use non-cryptographic `random` instead of `secrets`
- `PUT /api/state` accepts arbitrary keys that can manipulate internal engine flags
- `POST /api/feedback` returns entire user state in response body
- Supabase `save_recovery_codes` DELETE-all + INSERT-all without transaction
- Duplicated `_auto_resolve` logic in `week.py` and `replanner.py`

### Engine Logic (8 items — Agents 3, 4, 5)
- `test_max_hang_7s` in catalog but no `_SESSION_META` entry (orphaned)
- `regeneration_easy` equipment mismatch between catalog JSON and META
- `_find_gym_change_replacement()` has dead `is_finger_session` parameter
- `move_session` event doesn't validate hard/finger spacing on target day
- Pass 3 test scheduling silently drops tests when days have no sessions
- `_reconcile()` enforces finger but not hard-day spacing
- `_apply_load_override` mutates `user_state` via `setdefault` (side effect)
- Deload weights sum to 0.40 instead of ~1.0 (renormalization saves it but inconsistent)

### Macrocycle (2 items — Agent 5)
- Phase duration sum mismatch possible for 9-11 week macrocycles
- Streak saved in `closed_loop.py` but never used in multiplier calculation

### Frontend (10 items — Agent 1)
- Outdoor page silently swallows all API errors
- `PHASE_LABELS` duplicated across 4 files
- 16+ API calls with `.catch(() => {})` silently eating errors
- `window.location.href` used for navigation (breaks SPA)
- Hardcoded email in feedback section
- Plus 5 more (see full report)

### Catalog (16 items — Agents 7, 8)
- 10 campus exercises use non-canonical `age_under_16` contraindication
- 8 broken video URLs (hoopersbeta.com/library/* subpaths)
- `easy_climbing_deload` uses legacy schema (different field names)
- `deload_recovery` missing 3 required fields
- `finger_warmup_generic` has null description and zero cues
- 8 orphan templates never referenced by any session

### API Contract (1 item — Agent 9)
- `POST /api/outdoor/convert-slot` response shape mismatch (frontend expects `status`, backend returns `date`)

### Documentation (4 items — Agent 6)
- Intent counts wrong in CLAUDE.md (13+3 vs actual 15+4)
- `grip_transition` pattern missing from vocabulary_v1.md
- `closed_loop_v1.py` filename reference stale in CLAUDE.md
- Session "active" label mismatch in sync_status.py

### Test Coverage (4 items — Agent 10)
- 9 API endpoints lack integration tests
- No full-pipeline E2E test (assessment -> macrocycle -> planner -> resolver -> feedback)
- `cluster_utils` 5/6 utility functions untested
- Test fixtures duplicated inline across ~10+ files

---

## P3 Findings — Backlog

78 items across all agents. See individual reports:
- [01_frontend_code.md](01_frontend_code.md) — 10 P3
- [02_backend_code.md](02_backend_code.md) — 14 P3
- [03_planner_replanner.md](03_planner_replanner.md) — 15 P3
- [04_resolver_progression.md](04_resolver_progression.md) — 8 P3
- [05_macrocycle_assessment.md](05_macrocycle_assessment.md) — 8 P3
- [06_docs_coherence.md](06_docs_coherence.md) — 5 P3
- [07_exercise_catalog.md](07_exercise_catalog.md) — 18 P3
- [08_session_template_catalog.md](08_session_template_catalog.md) — 10 P3
- [09_api_contract.md](09_api_contract.md) — 5 P3
- [10_test_coverage.md](10_test_coverage.md) — 3 P3 (estimated, includes fixture consolidation)

---

## Per-Agent Summary

| # | Agent | Findings | P1 | P2 | P3 | Status |
|---|-------|----------|----|----|----|----|
| 1 | Frontend Code | 22 | 2 | 10 | 10 | Done |
| 2 | Backend Code | 23 | 0 | 9 | 14 | Done |
| 3 | Planner/Replanner | 22 | 1 | 6 | 15 | Done |
| 4 | Resolver/Progression | 14 | 0 | 6 | 8 | Done |
| 5 | Macrocycle/Assessment | 10 | 0 | 2 | 8 | Done |
| 6 | Documentation | 9 | 0 | 4 | 5 | Done |
| 7 | Exercise Catalog | 34 | 2 | 14 | 18 | Done |
| 8 | Session/Template | 12 | 0 | 2 | 10 | Done |
| 9 | API Contract | 6 | 0 | 1 | 5 | Done |
| 10 | Test Coverage | ~8 | 1 | 4 | ~3 | Done |

---

## Recommendations

### 1. Fix 6 P1 items before any public launch
- Remove profanity from timer cues (immediate — 5 min fix)
- Add Suspense boundary for useSearchParams (5 min fix)
- Add `route_projecting_gym` to vocabulary or remap unknown values (10 min)
- Add recovery code endpoint tests (30 min)
- Replanner recovery_multiplier: scope and fix (1-2 hours)

### 2. Security hardening sprint (P2, 1 day)
- Atomic file writes (write-then-rename)
- Rate limiting on recovery code + generation endpoints
- `secrets.token_hex()` for recovery codes
- Sanitize error responses (strip internal details)

### 3. Frontend error handling sweep (P2, half day)
- Replace all `.catch(() => {})` with proper error UI
- Add error states to outdoor page and other silent-fail patterns

### 4. Catalog cleanup (P2, half day)
- Fix broken video URLs or remove them
- Normalize `easy_climbing_deload` and `deload_recovery` schemas
- Add `test_max_hang_7s` to `_SESSION_META`

### 5. E2E test pipeline (P2, 1 day)
- Full assessment-to-feedback pipeline test
- Recovery code endpoint tests
- Weekly override endpoint tests
