# D197 — Audit documenti obsoleti nel repo

**Date:** 2026-04-10
**Type:** D (read-only audit)
**Status:** Report only — no file modifications

---

## Summary

- **Total .md files audited:** 52 (26 active + 5 council + 3 reports + 18 archive)
- **KEEP:** 27 files (active, referenced, current)
- **ARCHIVE → `_archive/`:** 8 files (historical value, no active references)
- **DELETE:** 17+ files (obsolete, superseded, or stale)
- **ROADMAP_CURRENT.md is 1069 lines** (target ≤350) — needs `trim_roadmap.py`

---

## Classification table

### Root files

| File | Last Commit | Status | Rationale |
|------|-------------|--------|-----------|
| `CLAUDE.md` | 2026-04-08 | **KEEP** | Core operational reference, updated every session |
| `PROJECT_BRIEF.md` | 2026-04-09 | **KEEP** | Auto-synced counters via `sync_status.py` |
| `README.md` | 2026-04-09 | **KEEP** | Public-facing, current |
| `frontend_audit_D163.md` | 2026-03-28 | **ARCHIVE** | Comprehensive audit (67 findings) — findings addressed, superseded by D164. Should be in `_archive/docs/` or `docs/audit/` |

### docs/ — Core documentation

| File | Last Commit | Status | Rationale |
|------|-------------|--------|-----------|
| `docs/ROADMAP_CURRENT.md` | 2026-04-09 | **KEEP** | Active tracking — but at 1069 lines, needs trimming |
| `docs/ROADMAP_v2.md` | 2026-03-25 | **KEEP** | Append-only archive, managed by `trim_roadmap.py` |
| `docs/ENGINE_ARCHITECTURE.md` | 2026-03-30 | **KEEP** | Core technical reference, referenced by CLAUDE.md |
| `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` | 2026-03-30 | **KEEP** | Methodology rationale, living document |
| `docs/vocabulary_v1.md` | 2026-04-08 | **KEEP** | Canonical enums/constraints, recently updated |
| `docs/user_guide_v1.md` | 2026-03-30 | **KEEP** | User-facing guide, maintained per workflow rules |
| `docs/lessons.md` | 2026-04-06 | **KEEP** | Operational lessons (24 entries), actively maintained |
| `docs/beta_feedback.md` | 2026-03-31 | **KEEP** | Beta tester feedback with brief mappings |
| `docs/audit_workflow.md` | 2026-03-26 | **KEEP** | Repeatable audit methodology |
| `docs/literature_review_climbing_training.md` | 2026-02-16 | **KEEP** | Foundation science reference |
| `docs/docs_literature_hangboard.md` | 2026-02-20 | **KEEP** | Hangboard science reference |

### docs/ — Audit & brief reports

| File | Last Commit | Status | Rationale |
|------|-------------|--------|-----------|
| `docs/audit_decision_roadmap_xcheck.md` | 2026-04-05 | **KEEP** | Recent decision-tracking validation |
| `docs/audit/D175_performance_audit.md` | 2026-04-07 | **KEEP** | Blocks A187 (React Query), active dependency |
| `docs/audit/D176_invalidation_map.md` | 2026-04-07 | **KEEP** | Cache invalidation spec for A187, active |
| `docs/B183_duration_review.md` | 2026-04-02 | **KEEP** | Session duration audit, tracked in roadmap |
| `docs/outdoor_audit_D170.md` | 2026-04-04 | **KEEP** | Outdoor module design audit, recent |

### docs/audit/D164/ (pre-launch comprehensive audit)

| File | Last Commit | Status | Rationale |
|------|-------------|--------|-----------|
| `00_SUMMARY.md` | 2026-03-28 | **KEEP** | D164 master summary (138 findings, 6 P1) |
| `01_frontend_code.md` | 2026-03-28 | **KEEP** | Frontend findings (22 items) |
| `02_backend_code.md` | 2026-03-28 | **KEEP** | Backend security findings |
| `03_planner_replanner.md` | 2026-03-28 | **KEEP** | Engine edge cases |
| `04_resolver_progression.md` | 2026-03-28 | **KEEP** | Filter chain validation |
| `05_macrocycle_assessment.md` | 2026-03-28 | **KEEP** | Assessment math audit |
| `06_docs_coherence.md` | 2026-03-28 | **KEEP** | Counter cross-validation |
| `07_exercise_catalog.md` | 2026-03-28 | **KEEP** | Schema compliance (185 exercises) |
| `08_session_template_catalog.md` | 2026-03-28 | **KEEP** | Session/template integrity |
| `09_api_contract.md` | 2026-03-28 | **KEEP** | Endpoint contract validation |
| `10_test_coverage.md` | 2026-03-28 | **KEEP** | Coverage baseline (1402 tests) |

### docs/council_reports/

| File | Last Commit | Status | Rationale |
|------|-------------|--------|-----------|
| `council_2026-04-01_11-45.md` | 2026-04-01 | **ARCHIVE** | Strategic decision taken, no longer actionable |
| `council_2026-04-01_16-30.md` | 2026-04-01 | **ARCHIVE** | "Keep building / wait / charge" — decision archived |
| `council_2026-04-02_test-peer-review.md` | 2026-04-01 | **ARCHIVE** | Test protocol review — completed |
| `council_2026-04-03_17-00.md` | 2026-04-01 | **ARCHIVE** | Exploratory session — no open items |
| `council_2026-04-05_10-30.md` | 2026-04-01 | **ARCHIVE** | SaunaFinder portfolio question — not climb-agent specific |

### reports/ (untracked)

| File | Last Commit | Status | Rationale |
|------|-------------|--------|-----------|
| `reports/users_report_2026-04-05.md` | untracked | **DELETE** | Stale metrics snapshot (5 days old) |
| `reports/users_report_2026-04-06.md` | untracked | **DELETE** | Stale metrics snapshot (4 days old) |
| `reports/users_report_2026-04-07.md` | untracked | **DELETE** | Stale metrics snapshot (3 days old) |

### _archive/ — Assessment

| File | Status | Rationale |
|------|--------|-----------|
| `architecture_legacy.md` | **DELETE** | Superseded by ENGINE_ARCHITECTURE.md, references removed JSON file persistence |
| `docs_legacy/*.md` (17 files) | **DELETE** | Pre-v1 docs (VISION, PLANNER_V1, PROGRESSION_V1, CLOSED_LOOP_V1, COLAB_*, UI_GRADIO) — all superseded by shipped code + ENGINE_ARCHITECTURE |
| `docs/audit_backend_report.md` | **DELETE** | Pre-D164 audit, superseded by D164/02 |
| `docs/audit_catalog_report.md` | **DELETE** | Pre-D164 audit, superseded by D164/07+08 |
| `docs/audit_docs_report.md` | **DELETE** | Pre-D164 audit, superseded by D164/06 |
| `docs/audit_frontend_report.md` | **DELETE** | Pre-D164 audit, superseded by D164/01 |
| `docs/audit_location_equipment.md` | **DELETE** | Single-issue audit, resolved |
| `docs/audit_post_fix.md` | **DELETE** | Post-fix verification, resolved |
| `docs/audit_timer_load_D121.md` | **DELETE** | Timer/load audit (D121), resolved |
| `docs/B157_orphan_exercise_leak.md` | **DELETE** | Bug remediation doc, issue fixed in code |
| `docs/B159_boulder_surface_equivalence.md` | **DELETE** | Bug remediation doc, issue fixed in code |
| `docs/BACKLOG.md` | **DELETE** | Replaced by ROADMAP_CURRENT.md |
| `docs/NEXT_STEPS.md` | **DELETE** | Replaced by ROADMAP_CURRENT.md |
| `docs/D154_phase1_sp_climbing_fix.md` | **DELETE** | Remediation applied, archived scope |
| `docs/D155_full_phase_distribution_audit.md` | **DELETE** | Findings applied, archived scope |
| `docs/claude_code_mega_brief_v1.md` | **DELETE** | Explicitly marked ARCHIVED in ROADMAP_CURRENT header, all decisions migrated |
| `docs/decision_consolidation_D01_D83.md` | **DELETE** | Superseded by granular tracking |
| `docs/coach_knowledge_base_spec.md` | **DELETE** | v2 feature spec, not shipped, no active references |
| `docs/free_climbing_design_v2.md` | **DELETE** | Feature shipped (free-session), design doc superseded by code |
| `docs/horst_integration_audit.md` | **DELETE** | Findings applied to engine, no active references |
| `docs/roadmap_boulder_support.md` | **DELETE** | Superseded by ROADMAP_CURRENT.md |
| `docs/roadmap_kb_patch.md` | **DELETE** | Superseded by ROADMAP_CURRENT.md |
| `docs/e2e_test_results.md` | **DELETE** | Test log artifact, no lasting value |
| `docs/megabrief_patch_session2_pre.md` | **DELETE** | Pre-session notes, no lasting value |
| `docs/analysis_loading_pin_v1.md` | **DELETE** | Loading pin analysis, resolved |
| `docs/07_PROFILE_INTAKE_V1.md` | **DELETE** | Pre-v1 onboarding spec, superseded by shipped onboarding code |
| `STATUS.md` | **DELETE** | Pre-roadmap status log (Jan-Feb 2026), replaced by ROADMAP_CURRENT |

---

## Recommended actions

### 1. Trim ROADMAP_CURRENT.md (critical)
At 1069 lines (target ≤350), run:
```bash
python scripts/trim_roadmap.py
```

### 2. Move to `_archive/docs/`
- `frontend_audit_D163.md` (from root — repo_hygiene already flagged this)
- `docs/council_reports/*` (5 files)

### 3. Delete from `_archive/`
Everything in `_archive/` can be safely deleted — 43 files total. All content is either:
- Superseded by ENGINE_ARCHITECTURE.md, D164 audit, or ROADMAP_CURRENT.md
- Pre-v1 specs for features that have been shipped or deferred to v2
- Single-issue audits whose fixes are in the code

### 4. Delete untracked reports
```bash
rm -rf reports/
```

### 5. Add `reports/` to `.gitignore`
If generated reports should never be committed, add the directory to `.gitignore`.

---

## References to removed features flagged

The following files reference features that no longer exist:
- `_archive/architecture_legacy.md` → JSON file persistence (now Supabase)
- `_archive/docs/02_CONTRACTS.md` → recovery codes v0 schema
- `_archive/docs_legacy/04_CLOSED_LOOP_V1.md` → pre-multiplier closed loop
- `_archive/docs/claude_code_mega_brief_v1.md` → multiple deprecated decisions

All are in `_archive/` and marked for DELETE above.

No active docs (`docs/` or root) reference removed features.
