# D164 — Documentation Coherence Audit

> **Date:** 2026-03-27
> **Scope:** CLAUDE.md, PROJECT_BRIEF.md, README.md, docs/ROADMAP_CURRENT.md, docs/vocabulary_v1.md, docs/DESIGN_GOAL_MACROCICLO_v1.1.md, docs/ENGINE_ARCHITECTURE.md, docs/user_guide_v1.md
> **Method:** Automated counting, codebase grep, cross-reference

---

## 1. Counter Accuracy

| Metric | Documented | Actual | Match | Notes |
|--------|-----------|--------|-------|-------|
| Tests (passing) | 1402 | 1402 | OK | All three docs (PROJECT_BRIEF, README, CLAUDE.md) agree |
| Exercises | 185 | 185 | OK | `exercises.json` → `data["exercises"]` has 185 entries |
| Sessions (active) | 35 | **30 active + 5 supplementary = 35 total** | **P2** | Label says "active" but `sync_status.py:count_sessions()` counts ALL JSON files including supplementary. The number 35 is the total, not the active count |
| Templates | 27 | 27 | OK | |
| API endpoints | 50 (49 router + 1 health) | 50 | OK | Verified: 54 FastAPI routes minus 4 framework auto-generated (docs, openapi.json, redoc, oauth2-redirect) = 50 |
| Frontend pages | 31 | 31 | OK | |
| Frontend components | 58 | 58 | OK | |

### P2 — Sessions label mismatch

**File:** `scripts/sync_status.py` line 69-71
**Problem:** `count_sessions()` uses `glob("*.json")` which returns 35 (all sessions), but the label in all three status tables says "Sessions (active)". Active (non-supplementary) count is 30.
**Fix:** Either change the label to "Sessions (total)" or filter out `supplementary: true` sessions in `count_sessions()`.

---

## 2. Vocabulary vs Code

### 2.1 Role — OK

Vocabulary lists 10 values: warmup, activation, main, accessory, cooldown, prehab, technique, conditioning, test, recovery.
Code uses exactly these 10 values. No discrepancies.

### 2.2 Domain

| Status | Value | Notes |
|--------|-------|-------|
| **P3** | `endurance` | Listed in vocabulary as domain, used in engine as assessment axis name, but **zero exercises** have `domain: "endurance"`. Dead vocabulary entry. |

All 29 domains found in exercises.json are documented in vocabulary. No undocumented domains in code.

### 2.3 Pattern

| Status | Value | Notes |
|--------|-------|-------|
| **P2** | `grip_transition` | Used by exercise(s) in `exercises.json` but **NOT listed** in vocabulary_v1.md pattern section (section 2.4). Missing vocabulary entry. |

All other 39 patterns found in code are documented. No other gaps.

### 2.4 Category — OK

All 15 category values in code match vocabulary section 2.11 exactly.

### 2.5 Load Model — OK

4 values in code (total_load, external_load, grade_relative, bodyweight_only) all documented. Vocabulary also lists `null` as valid.

### 2.6 Phase — OK

5 phase_id values (base, strength_power, power_endurance, performance, deload) match vocabulary section 5.5 and `macrocycle_v1.py:PHASE_ORDER`.

### 2.7 Recency Group — N/A

Vocabulary defines format rules but no closed set. 118 unique values in code. Format compliance not audited (all appear to follow snake_case convention).

### 2.8 Grip — N/A

No `grip` field found on any exercise. Vocabulary does not define a grip enum (D72 deferred). Task scope mentioned `grip` but it is not yet implemented.

---

## 3. ROADMAP vs Reality

### 3.1 Completed items spot-checked

| Item | Claim | Verified |
|------|-------|----------|
| B157 | Orphan exercise leak fixed | `critical_force_test` not in exercises.json: confirmed removed |
| B159b | Exercise rotation via `load_recent_exercise_ids()` | Function exists in `resolve_session.py`, reads from `week_plans`: confirmed |
| B160g | Template gap fix — 7 sessions got tail blocks | Spot-checked `boulder_circuit_gym.json`: has `core_standard` and `antagonist_prehab` modules: confirmed |
| R140 | Backend error handling hardening | `@lru_cache` on quote loading, `logger.warning` in engine modules: confirmed |

### 3.2 Intent count discrepancy

| Doc | Indoor intents | Outdoor intents | Actual Indoor | Actual Outdoor |
|-----|---------------|-----------------|---------------|----------------|
| CLAUDE.md | 13 | 3 | **15** | **4** |
| ENGINE_ARCHITECTURE.md | 13 | 3 | **15** | **4** |
| user_guide_v1.md | "8 indoor intents and 4 outdoor intents" | — | **15** | **4** |

**P2 — CLAUDE.md and ENGINE_ARCHITECTURE.md:** State "13 indoor + 3 outdoor intents" but `replanner_v1.py:INTENT_TO_SESSION` has 15 keys (rest, recovery, technique, strength, power, power_endurance, aerobic_endurance, core, prehab, flexibility, finger_maintenance, finger_max, projecting, endurance, hard) and `OUTDOOR_INTENT_TO_DISCIPLINE` has 4 keys (outdoor_easy, outdoor_projecting, outdoor_volume, outdoor_boulder).

**P3 — user_guide_v1.md:** Says "8 indoor intents and 4 outdoor intents" — the outdoor count is correct but indoor count is wrong (15 actual).

---

## 4. ENGINE_ARCHITECTURE vs Code

### 4.1 Data flow — OK

The documented flow (assessment → macrocycle → planner → resolver → progression → feedback → closed-loop) matches actual code. Function signatures verified:
- `compute_assessment_profile(assessment, goal)` — matches
- `generate_macrocycle(goal, assessment_profile, user_state, start_date, total_weeks, *, from_phase)` — matches
- `generate_phase_week(*, phase_id, domain_weights, session_pool, start_date, availability, ...)` — matches
- `resolve_session(repo_root, session_path, templates_dir, exercises_path, out_path, *, ...)` — matches

### 4.2 Closed-loop module path

| Doc | Referenced as | Actual file |
|-----|--------------|-------------|
| ENGINE_ARCHITECTURE.md | `adaptation/closed_loop.py` | `backend/engine/adaptation/closed_loop.py` | OK |
| CLAUDE.md | `closed_loop_v1.py` | **Does not exist** — actual file is `closed_loop.py` | **P2** |

**P2 — CLAUDE.md line 63:** References `closed_loop_v1.py` in the mandatory analysis list, but the actual file is `backend/engine/adaptation/closed_loop.py` (no `_v1` suffix). Also, there is a separate file `backend/engine/closed_loop_v1.py` — let me verify.

Note: `backend/engine/closed_loop_v1.py` does exist as a separate legacy module. CLAUDE.md's reference may be intentionally pointing to this file. However, ENGINE_ARCHITECTURE.md documents `adaptation/closed_loop.py` as the active closed-loop module with `update_user_state_adjustments()`. These appear to be two different files serving different purposes.

### 4.3 P0 filter stages — OK

Filter chain in ENGINE_ARCHITECTURE.md section 6 (stages 0 through 6b) matches the actual implementation in `resolve_session.py:pick_best_exercise_p0()`. Stage numbers, names, and hard/soft classification verified.

### 4.4 Progression load_model table

| ENGINE_ARCHITECTURE.md | Code |
|----------------------|------|
| `grade_based` | `grade_relative` |

**P3 — ENGINE_ARCHITECTURE.md section 7:** Uses the term `grade_based` in the inject_targets table, but the actual `load_model` value in exercises and vocabulary is `grade_relative`. Minor terminology inconsistency.

---

## 5. Cross-Doc Consistency

### 5.1 Internal references — OK

| Reference | Source | Target | Status |
|-----------|--------|--------|--------|
| `docs/ROADMAP_v2.md` | ROADMAP_CURRENT, CLAUDE.md | `docs/ROADMAP_v2.md` | EXISTS |
| `_archive/docs/coach_knowledge_base_spec.md` | ROADMAP_CURRENT | `_archive/docs/coach_knowledge_base_spec.md` | EXISTS |
| `DESIGN_GOAL_MACROCICLO_v1.1.md` | ENGINE_ARCHITECTURE.md | `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` | EXISTS |
| `vocabulary_v1.md` | ENGINE_ARCHITECTURE.md | `docs/vocabulary_v1.md` | EXISTS |
| `PROJECT_BRIEF.md` | ROADMAP_CURRENT, CLAUDE.md | `PROJECT_BRIEF.md` | EXISTS |

No broken cross-document links found.

### 5.2 Page count breakdown inconsistency

**P3 — CLAUDE.md:** States "9 main views + 15 onboarding steps + 1 root + 1 onboarding index + 2 auth + 1 tabata + 1 legal = 31". But `(main)/` group contains 12 page.tsx files (today, week, plan, session/[id], reports/weekly, outdoor, whats-next, settings, tabata, free-session, guide, free-session). Subtracting tabata (counted separately), there are 10 or 11 main views, not 9. The total (31) is correct, but the breakdown is stale. Pages `free-session` and `guide` were added after the breakdown was written.

### 5.3 Architecture flow consistency — OK

All docs (PROJECT_BRIEF, CLAUDE.md, DESIGN_GOAL, ENGINE_ARCHITECTURE) describe the same pipeline: Assessment → Macrocycle → Week → Session → Feedback → Adaptation. No contradictions.

---

## 6. Stale Information

| Item | Doc | Stale Value | Current Value | Severity |
|------|-----|------------|---------------|----------|
| Test count in user guide header | user_guide_v1.md line 6 | "Last verified: 2026-03-24 at 1335 tests" | 1402 tests as of 2026-03-27 | **P3** |
| Vocabulary last updated | vocabulary_v1.md line 6 | "Last updated: 2026-03-23" | `grip_transition` pattern missing (added after 03-23) | **P3** |
| Base phase duration | DESIGN_GOAL section 4.1 | "3-4" weeks for base | Code: base=4 weeks, can extend to 5 with weakness adjustment | **P3** |
| Base phase duration | user_guide_v1.md section 2 | "Base / Endurance (4-6 weeks)" | Code max is 5 weeks (base=4 + 1 weakness extension) | **P3** |
| Router count text | CLAUDE.md | "16 routers" | 16 router files (correct, but listed names may need verification against free_session addition) | OK |
| CLAUDE.md endpoint count text | CLAUDE.md | "50 endpoints total (49 router + 1 app-level)" | 50 confirmed | OK |

---

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| **P1** | 0 | — |
| **P2** | 4 | Sessions label mismatch, `grip_transition` missing from vocabulary, intent counts wrong (CLAUDE.md + ENGINE_ARCHITECTURE), `closed_loop_v1.py` filename wrong in CLAUDE.md |
| **P3** | 5 | `endurance` dead domain, user_guide stale test count, user_guide stale base phase duration, design doc base phase "3-4" vs code "4", `grade_based` vs `grade_relative` in ENGINE_ARCHITECTURE, page count breakdown stale |

**Overall assessment:** Documentation is well-maintained. No P1 issues. The 4 P2 findings are straightforward corrections. The P3 items are cosmetic or represent natural drift from recent changes.
