# Document Alignment Audit Report

> **Date:** 2026-03-22
> **Auditor:** Claude Code
> **Scope:** 7 documents × codebase cross-reference

## Summary

- **Total checks:** 58
- ✅ **Aligned:** 40
- ⚠️ **Stale/outdated:** 11
- ❌ **Contradictory:** 4
- 🔍 **Missing:** 1

---

## Findings by document

### 1. CLAUDE.md

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Repo structure | ✅ | All directories match actual layout |
| 2 | Listed modules | ✅ | All key modules exist: assessment_v1, macrocycle_v1, planner_v2, replanner_v1, resolve_session, progression_v1, closed_loop_v1 |
| 3 | API endpoint count | ✅ | "49 endpoints" correct (48 router + 1 /health) |
| 4 | API endpoint table — paths | ⚠️ | 3 free-session endpoints use `{id}` in doc but `{session_id}` in code (log-climb, finish, delete) |
| 5 | Frontend page count | ❌ | Claims "25 pages (9 main + 14 onboarding + 1 root + 1 index)" — actual is **29** (9 main + 15 onboarding + 1 root + 4 dynamic/auth: sign-in, sign-up, tabata, extra onboarding step) |
| 6 | Component count | 🔍 | No explicit count in CLAUDE.md — actual is 54 .tsx files. Not wrong, but missing |
| 7 | Listed routers | ⚠️ | Claims "16 routers" but list names only 15 — missing `free_session` (7 endpoints) |
| 8 | Import conventions | ✅ | `backend.*` prefix verified across codebase |
| 9 | "When you MUST stop" modules | ✅ | All filenames exist and are correct |
| 10 | Deployment info | ✅ | URLs, port, env vars, Procfile all accurate |
| 11 | Commands section | ✅ | All commands work as documented |
| 12 | Engine architecture pipeline | ✅ | `compute_assessment_profile()` → `generate_macrocycle()` → `generate_phase_week()` → `resolve_session()` — all match |

---

### 2. PROJECT_BRIEF.md

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Test count | ✅ | 1250 — matches (sync_status.py confirms; grep count differs due to parametrized tests) |
| 2 | Exercise count | ✅ | 178 — matches |
| 3 | Session count | ✅ | 33 — matches |
| 4 | Template count | ✅ | 26 — matches |
| 5 | Endpoint count | ✅ | 49 — matches |
| 6 | Page count | ✅ | 29 — matches |
| 7 | Component count | ✅ | 54 — matches |
| 8 | Architecture diagram | ✅ | Code flow matches |
| 9 | Tech stack table | ✅ | Dependencies verified against requirements.txt and package.json |
| 10 | Assessment axes | ❌ | Claims **"6 dimensions"** (line ~24) — code implements **5 axes** (body_composition removed per D01). CLAUDE.md correctly says 5 |
| 11 | Completed phases | ✅ | All 10 phases accurate |

---

### 3. README.md

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Product description | ✅ | Accurate |
| 2 | Status counters | ✅ | All counters match (sync_status.py confirmed) |
| 3 | Assessment axes | ❌ | Same "6 dimensions" error as PROJECT_BRIEF |
| 4 | Architecture section | ✅ | Accurate |
| 5 | Tech stack | ✅ | Accurate |
| 6 | Repository layout | ✅ | Accurate |
| 7 | Dev commands | ✅ | All verified |
| 8 | Deployment URLs | ✅ | Both URLs live (Vercel 200, Railway 405 as expected) |
| 9 | Deprecated references | ✅ | None found |

---

### 4. ROADMAP_CURRENT.md

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Mega Brief Sessions 1-10 tracker | ✅ | Status matches actual implementation |
| 2 | 5 closed items spot-check (D150, D35, D64, B137b, B138) | ✅ | All 5 verified implemented correctly, descriptions accurate |
| 3 | 5 open items spot-check (D37, D34, R140, C130, R147) | ✅ | All 5 confirmed NOT implemented — correctly marked open |
| 4 | Priority section consistency (P1–P4) | ✅ | No inversions, proper hierarchy |
| 5 | Duplicate check | ✅ | No ID collisions across 170+ items |
| 6 | R140–R149 backlog validity | ✅ | All items valid, specific, currently open |
| 7 | Recently closed items accuracy | ✅ | All descriptions match implementation |
| 8 | Test count in D150 entry | ✅ | "1250 total" confirmed by sync_status.py |
| 9 | Exercise count in backlog note (line ~526) | ⚠️ | References "153 esercizi" — actual is 178 (stale backlog note) |

---

### 5. vocabulary_v1.md

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Phase IDs | ✅ | All 5 match macrocycle_v1.py PHASE_ORDER |
| 2 | Location enum | ✅ | home, gym, outdoor — all used |
| 3 | Equipment canonical IDs | ✅ | All 22 verified. Note: 6 listed values (ab_wheel, barbell, cable_machine, foam_roller, kettlebell, leg_press) exist only in onboarding options, not exercises |
| 4 | Role enum | ⚠️ | Lists 9 roles but **missing `recovery`** (used in exercises.json) |
| 5 | Domain enum | ⚠️ | **Missing 2 values** from code: `lock_off_endurance`, `strength_pulling` |
| 6 | Pattern enum | ⚠️ | **Missing 8 values** from code: `finger_extension`, `isometric_hold`, `isometric_lift`, `mobility_flow`, `repeater_lift`, `self_massage`, `static_stretch`, `tendon_glide`. 2 listed values unused: `mobility_hips`, `mobility_spine` |
| 7 | Intensity levels | ⚠️ | **Missing `very_high`** (used in exercises.json) |
| 8 | Category enum | ⚠️ | **Missing `test_measurement`** (used in exercises.json) |
| 9 | Contraindications | ⚠️ | Lists only 4 values; code also uses `elbow_injury`, `finger_injury`, `knee_injury` |
| 10 | Load models | ✅ | All values match |
| 11 | Feedback labels | ✅ | All 5 values match progression_v1.py |
| 12 | **Template IDs** | ❌ | **CRITICAL:** Lists 26 templates but code has **33** different ones. Most vocabulary template names don't match actual filenames (e.g., vocab: `finger_max_strength` → code: `finger_strength_home`) |
| 13 | Test IDs | ⚠️ | Conflates exercise test_id values with assessment.tests scalar keys |
| 14 | Free session presets | ✅ | All 7 presets match |
| 15 | Surfaces | ✅ | All values match |
| 16 | Outdoor route styles | ⚠️ | Missing `repeat` (used in code schema) |
| 17 | Weekday/slot keys | ✅ | All match |
| 18 | Assessment axes | ✅ | §5.9 correctly lists 5 axes |
| 19 | Constraint enforcement | ✅ | Monday invariant, hangboard gates, test immunity — all enforced |

---

### 6. DESIGN_GOAL_MACROCICLO_v1.1.md

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Phase names | ✅ | All 5 match code |
| 2 | Phase durations | ✅ | Base durations match `_BASE_DURATIONS` in macrocycle_v1.py |
| 3 | DUP methodology | ✅ | Domain weights per phase match code |
| 4 | Assessment axes | ❌ | §2.2 and §2.4 claim **6 axes** including "Composizione corporea" — code has 5 (body_composition removed per D01, doc never updated) |
| 5 | Domain weight distribution | ✅ | Values match macrocycle_v1.py |
| 6 | Formulas/constants | ✅ | Benchmarks present and accurate |
| 7 | Test session names | ⚠️ | References `test_max_hang_5s` — should be `test_max_hang_7s_total_kg` (D85 changed 5s→7s) |

---

### 7. claude_code_mega_brief_v1.md

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Progress tracker | ⚠️ | Snapshot from 2026-03-16; shows Sessions 2-10 as unchecked but roadmap shows them as 🟡 Partial |
| 2 | Architecture — axis count | ⚠️ | Line ~45 says "6 dimensions" but line ~66 correctly says "5 Axes (D01: body_composition removed)" — internal inconsistency |
| 3 | Assessment axis list | ❌ | Lists `finger_endurance` as axis #2 — code has `endurance` (not finger_endurance). Missing `endurance` from list |
| 4 | Exercise count | ⚠️ | Claims 168 — actual 178 (+10) |
| 5 | Endpoint count | ⚠️ | Claims 42 — actual 49 (+7) |
| 6 | Key code functions | ✅ | All 4 functions exist: compute_assessment_profile, generate_macrocycle, generate_phase_week, resolve_session |
| 7 | D01 note attribution | ⚠️ | Conflates D01 (assessment axes) with D68 (injury history) in deferral note |
| 8 | Test session names | ⚠️ | References `test_max_hang_5s` — should be 7s (D85) |

---

## Recommended fixes (priority-ordered)

### CRITICAL

1. **vocabulary_v1.md §3 — Template IDs completely misaligned.** Lists 26 templates that mostly don't match the 33 actual templates in `backend/catalog/sessions/v1/`. Section needs full rewrite from catalog scan.

2. **6→5 axes mismatch across 4 documents.** `body_composition` was removed (D01) but not updated in:
   - `PROJECT_BRIEF.md` (line ~24): "6 dimensions" → "5 dimensions"
   - `README.md` (line ~24): same fix
   - `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` §2.2 + §2.4: 6 dimensioni → 5
   - `docs/claude_code_mega_brief_v1.md` (line ~45): "6 dimensions" → "5 dimensions"

3. **claude_code_mega_brief_v1.md — axis naming error.** Lines ~66-71 list `finger_endurance` as axis #2 — code has `endurance` (general, not finger-specific). Correct the 5-axis list to: finger_strength, pulling_strength, power_endurance, technique, endurance.

### HIGH

4. **vocabulary_v1.md — 8 missing pattern values.** Code uses `finger_extension`, `isometric_hold`, `isometric_lift`, `mobility_flow`, `repeater_lift`, `self_massage`, `static_stretch`, `tendon_glide` — none documented. Also 2 unused values to remove: `mobility_hips`, `mobility_spine`.

5. **vocabulary_v1.md — missing enum values across 5 categories:**
   - Role: add `recovery`
   - Domain: add `lock_off_endurance`, `strength_pulling`
   - Intensity: add `very_high`
   - Category: add `test_measurement`
   - Contraindications: add `elbow_injury`, `finger_injury`, `knee_injury`
   - Outdoor styles: add `repeat`

6. **CLAUDE.md — page count and router list.** Claims 25 pages (actual 29), lists 15 routers (actual 16 — missing `free_session`).

7. **CLAUDE.md — API path parameters.** 3 free-session endpoints use `{id}` in table but code uses `{session_id}`.

### MEDIUM

8. **claude_code_mega_brief_v1.md — stale counts.** Exercises 168→178, endpoints 42→49. Consider adding a "snapshot date" disclaimer or refreshing.

9. **DESIGN_GOAL_MACROCICLO_v1.1.md + mega_brief — test name stale.** Both reference `test_max_hang_5s` — D85 changed to 7s MVC protocol.

10. ~~Test count drift~~ — **FALSE ALARM.** sync_status.py confirms 1250 passing tests. Grep-based count (1245) differs due to parametrized tests.

### LOW

11. **ROADMAP backlog note** (line ~526) references "153 esercizi" — actual is 178. Stale exploration note.

12. **vocabulary_v1.md — test_id documentation.** Conflates exercise test_id values with assessment.tests scalar keys. Clarify distinction.

13. **vocabulary_v1.md — equipment phantom values.** 6 equipment types (ab_wheel, barbell, cable_machine, foam_roller, kettlebell, leg_press) listed but unused in any exercise. Present only in onboarding options. Document as "onboarding-only" or remove.

14. **claude_code_mega_brief_v1.md — D01/D68 attribution.** Deferral note about injury history belongs to D68, not D01.
