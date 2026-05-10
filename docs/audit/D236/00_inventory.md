# D236 — Phase 0 Inventory

> Renumbered from D235 → D236 because `docs/audit/D235_project_description_rewrite.md` already exists as a separate untracked draft (collision discovered post-write; `next_brief.py` does not scan untracked files).

Generated: 2026-05-09
Scope: all *.md outside node_modules/.next/_archive (Table 1), all _archive/**/*.md (Table 2), all scripts/*.py (Table 3).
Method: read-only filesystem walk + git log for last-modified dates.

Found 90 live md, 6 archived md, 11 scripts.

Note: `_archive/`, `docs/council_reports/`, and `reports/` are all gitignored — dates for those entries use filesystem mtime.

---

## Table 1 — Live `*.md` files

Files in `.venv/` and `.pytest_cache/` excluded (third-party, not project-authored).

| path | size_lines | last_modified (YYYY-MM-DD) | first_paragraph_excerpt (max 120 chars) | listed_in_CLAUDE.md (Y/N) |
|------|-----------|--------------------------|----------------------------------------|--------------------------|
| `.claude/agents/contrarian.md` | 14 | 2026-04-01 | `name: contrarian` | N |
| `.claude/agents/executor.md` | 12 | 2026-04-01 | `name: executor` | N |
| `.claude/agents/first-principles.md` | 13 | 2026-04-01 | `name: first-principles` | N |
| `.claude/agents/niche-founder.md` | 11 | 2026-04-01 | `name: niche-founder` | N |
| `.claude/agents/saas-expert.md` | 13 | 2026-04-01 | `name: saas-expert` | N |
| `.claude/commands/audit-module.md` | 12 | 2026-03-28 | `Read-only audit of a single module. Argument: module path (e.g. backend/engine/planner_v2.py).` | N |
| `.claude/commands/brief.md` | 22 | 2026-04-01 | `Read these files (in this order):` | N |
| `.claude/commands/council-launch.md` | 41 | 2026-04-01 | `description: Run Council with the pre-loaded climb-agent launch timing + pricing question` | N |
| `.claude/commands/council.md` | 156 | 2026-04-02 | `description: Run the Strategic Advisory Council — 5 parallel advisors + anonymized peer review + synthesis` | N |
| `.claude/commands/sync-check.md` | 8 | 2026-03-28 | `Pre-push verification checklist. Run all checks, report pass/fail for each.` | N |
| `.claude/commands/sync.md` | 11 | 2026-03-07 | `Run the status sync script and commit:` | N |
| `.claude/commands/test.md` | 7 | 2026-03-07 | `Run the full test suite:` | N |
| `AUTH_AUDIT.md` | 730 | 2026-05-04 | `**Audit date:** 2026-04-23` | N |
| `CLAUDE.md` | 360 | 2026-05-07 | `You are a senior software engineer building climb-agent — a climbing training app heading to paid production.` | Y |
| `PROJECT_BRIEF.md` | 95 | 2026-05-07 | `> Counters auto-updated by python scripts/sync_status.py` | Y |
| `README.md` | 76 | 2026-05-07 | `Deterministic climbing training engine. Generates personalised weekly plans, resolves sessions into concrete exercises` | Y |
| `docs/A214_phase0_audit.md` | 398 | 2026-04-24 | `**Date:** 2026-04-24` | N |
| `docs/A215_phase0_audit.md` | 451 | 2026-04-24 | `**Date:** 2026-04-24` | N |
| `docs/A216_phase0_audit.md` | 368 | 2026-04-27 | `**Date**: 2026-04-27` | N |
| `docs/audit_decision_roadmap_xcheck.md` | 213 | 2026-04-05 | `> **Date:** 2026-04-05` | N |
| `docs/audit_docs_D197.md` | 162 | 2026-04-10 | `**Date:** 2026-04-10` | N |
| `docs/audit_readonly_2026-04-25.md` | 129 | 2026-05-04 | `Date: 2026-04-25` | N |
| `docs/audit_workflow.md` | 93 | 2026-03-26 | `Repeatable 3-step process for auditing climb-agent's training engine against climbing science literature.` | Y |
| `docs/B183_duration_review.md` | 182 | 2026-04-02 | `> Generated: 2026-04-02` | N |
| `docs/beta_feedback.md` | 157 | 2026-03-31 | `> Ultimo aggiornamento: 2026-03-14` | Y |
| `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` | 507 | 2026-05-07 | `> Documento di design per il sistema di periodizzazione adattiva.` | Y |
| `docs/design_system_v1.md` | 254 | 2026-04-24 | `> **Status:** A214 Phase 1 (foundation only — no screen redesigns).` | N |
| `docs/docs_literature_hangboard.md` | 523 | 2026-02-20 | `**File:** docs/docs_literature_hangboard.md` | Y |
| `docs/ENGINE_ARCHITECTURE.md` | 874 | 2026-03-30 | `> **Last verified:** 2026-03-27 (D163)` | Y |
| `docs/lessons.md` | 43 | 2026-05-07 | `Patterns, mistakes, and non-obvious behaviors discovered during development.` | Y |
| `docs/literature_review_climbing_training.md` | 906 | 2026-02-16 | `> Per climb-agent §2.2/§2.3 — Fonti: Hörst, Lattice, Eva López, Bechtel, Power Company, Hooper's Beta, Gresham` | Y |
| `docs/outdoor_audit_D170.md` | 315 | 2026-04-04 | `> Date: 2026-04-04` | N |
| `docs/ROADMAP_CURRENT.md` | 783 | 2026-05-07 | `> Last updated: 2026-05-07 (A218 / A-MACRO-CAPS ✅ — phase duration cap rewrite)` | Y |
| `docs/ROADMAP_v2.md` | 1231 | 2026-05-07 | `> **ARCHIVED — append-only via trim_roadmap.py**` | Y |
| `docs/user_guide_v1.md` | 482 | 2026-05-05 | `(HTML comment — no visible text on first line)` | Y |
| `docs/vocabulary_v1.md` | 1141 | 2026-05-07 | `This document defines the canonical vocabulary and schema constraints for the climb-agent repository.` | Y |
| `docs/audit/A-MACRO-CAPS_design.md` | 670 | 2026-05-07 | `**Brief:** A-MACRO-CAPS (canonical A218)` | N |
| `docs/audit/audit_route_intervals_offset_D93.md` | 461 | 2026-04-17 | `> **Type:** D (audit — read-only)` | N |
| `docs/audit/B227_phase0_findings.md` | 405 | 2026-04-27 | `**Date:** 2026-04-27` | N |
| `docs/audit/D-ANALYTICS-DROPOFF_output.md` | 113 | 2026-04-17 | `**Data run:** 2026-04-17` | N |
| `docs/audit/D-BASELINE-AUDIT_report.md` | 409 | 2026-04-19 | `**Tipo**: Audit read-only` | N |
| `docs/audit/D-TESTUSER-VERIFY_report.md` | 374 | 2026-04-19 | `**Type:** D (read-only verification audit)` | N |
| `docs/audit/D-TESTWEEK-AUDIT_report.md` | 281 | 2026-04-19 | `**Status:** COMPLETE` | N |
| `docs/audit/D164/00_SUMMARY.md` | 160 | 2026-03-28 | `> Date: 2026-03-28` | N |
| `docs/audit/D164/01_frontend_code.md` | 169 | 2026-03-28 | `**Date:** 2026-03-27` | N |
| `docs/audit/D164/02_backend_code.md` | 184 | 2026-03-28 | `**Scope:** backend/api/, backend/data/, backend/engine/equipment_utils.py, ...` | N |
| `docs/audit/D164/03_planner_replanner.md` | 237 | 2026-03-28 | `**Scope:** backend/engine/planner_v2.py, backend/engine/replanner_v1.py` | N |
| `docs/audit/D164/04_resolver_progression.md` | 206 | 2026-03-28 | `**Date:** 2026-03-27` | N |
| `docs/audit/D164/05_macrocycle_assessment.md` | 191 | 2026-03-28 | `**Data:** 2026-03-27` | N |
| `docs/audit/D164/06_docs_coherence.md` | 179 | 2026-03-28 | `> **Date:** 2026-03-27` | N |
| `docs/audit/D164/07_exercise_catalog.md` | 229 | 2026-03-28 | `**Date:** 2026-03-27` | N |
| `docs/audit/D164/08_session_template_catalog.md` | 273 | 2026-03-28 | `**Date:** 2026-03-27` | N |
| `docs/audit/D164/09_api_contract.md` | 243 | 2026-03-28 | `**Date:** 2026-03-27` | N |
| `docs/audit/D164/10_test_coverage.md` | 221 | 2026-03-28 | `**Data**: 2026-03-27` | N |
| `docs/audit/D175_performance_audit.md` | 189 | 2026-04-07 | `**Data:** 2026-04-07 / **Tipo:** D (read-only audit) / **Stato:** ✅ Done` | N |
| `docs/audit/D176_invalidation_map.md` | 309 | 2026-04-07 | `**Data:** 2026-04-07 / **Tipo:** D (read-only audit) / **Stato:** ✅ Done` | N |
| `docs/audit/D204_session_builder_audit.md` | 379 | 2026-04-16 | `**Date:** 2026-04-10` | N |
| `docs/audit/D205_subscription_audit_2026_04_16.md` | 188 | 2026-04-16 | `**Date:** 2026-04-16` | N |
| `docs/audit/D210_b206_verification.md` | 161 | 2026-04-17 | `**Date:** 2026-04-17` | N |
| `docs/audit/D215/findings.md` | 395 | 2026-04-20 | `**Brief:** D215 (placeholder in original brief was D213; next_brief.py returned D215)` | N |
| `docs/audit/D215/trace.md` | 115 | 2026-04-20 | `User: 7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e (daniele.somensi@gmail.com)` | N |
| `docs/audit/D216/findings.md` | 290 | 2026-04-20 | `**Brief:** D216 (placeholder in original brief was D219; next_brief.py returned D216)` | N |
| `docs/audit/D217_body_part_picker_audit.md` | 812 | 2026-04-21 | `> **Type:** D (read-only audit + design)` | N |
| `docs/audit/D220_body_part_picker_audit.md` | 234 | 2026-04-22 | `**Date:** 2026-04-22` | N |
| `docs/audit/D223_body_part_picker_classification_audit.md` | 369 | 2026-04-22 | `**Date:** 2026-04-22` | N |
| `docs/audit/D223_body_part_pool_listing.md` | 142 | 2026-04-23 | `Generated for Phase 0.4 of B224. Scope: 9 body parts with main < 3 in gym_full scenario.` | N |
| `docs/audit/D223_c225_research_notes.md` | 291 | 2026-04-23 | `**Date:** 2026-04-23` | N |
| `docs/audit/D223_full_resolver_reclass_impact.md` | 282 | 2026-04-23 | `**Date:** 2026-04-23` | N |
| `docs/audit/D233_macro_durations_report.md` | 496 | 2026-05-07 | `**Brief:** D-MACRO-DURATIONS (D233)` | N |
| `docs/audit/D234_macro_deadline_findings.md` | 176 | 2026-05-07 | `**Brief:** D-MACRO-DEADLINE (D234)` | N |
| `docs/audit/D235_project_description_rewrite.md` | 156 | untracked (mtime: 2026-05-09) | `> **Type:** D (audit + drafting, read-only)` | N |
| `docs/audits/D_guided_session_countdown_beep_2026-05-04.md` | 363 | 2026-05-04 | `**Status:** Phase 0 (read-only) — awaiting OK before Phase 1` | N |
| `docs/audits/D-MEM-002_railway_memory_2026-05-07.md` | 248 | 2026-05-07 | `**Brief:** D-MEM-002` | N |
| `docs/audits/D232_new_macrocycle_2026-05-05.md` | 595 | 2026-05-05 | `**Date:** 2026-05-05` | N |
| `docs/briefs/A-ACTIVATION-timing_parked.md` | 139 | 2026-04-17 | `Issues surfaced during Phase 1 that are NOT in scope for this brief. Logged` | N |
| `docs/briefs/A-ACTIVATION-timing_phase0.md` | 315 | 2026-04-17 | `**Tipo:** A (feature, fase 0 read-only)` | N |
| `docs/briefs/A-ACTIVATION-timing_simulation.md` | 111 | 2026-04-17 | `**Generated:** 2026-04-17T20:45:29` | N |
| `docs/briefs/A-ACTIVATION-timing_subscription_audit.md` | 177 | 2026-04-17 | `**Date:** 2026-04-17` | N |
| `docs/briefs/B202_proposal.md` | 5 | 2026-04-16 | `**Severity:** P0 (launch-blocker)` | N |
| `docs/briefs/B203_proposal.md` | 5 | 2026-04-16 | `**Severity:** P1` | N |
| `docs/briefs/B204_proposal.md` | 5 | 2026-04-16 | `**Severity:** P2` | N |
| `docs/briefs/B208_proposal.md` | 179 | 2026-04-17 | `**Severity:** P1` | N |
| `docs/briefs/B214_B215_phase0_analysis.md` | 329 | 2026-04-20 | `**Scope:** close remaining Bundle B items on backend/engine/progression_v1.py.` | N |
| `docs/briefs/B216_phase1_analysis.md` | 417 | 2026-04-20 | `**Scope:** chiudere i due difetti identificati dall'audit D215.` | N |
| `docs/briefs/B217_session_duration_fix.md` | 178 | 2026-04-20 | `**Type:** B (bugfix) — bundle 4-in-1` | N |
| `docs/briefs/D214_phase0_analysis.md` | 312 | 2026-04-20 | `**Model:** Opus` | N |
| `docs/briefs/D214_source_taxonomy_normalization.md` | 88 | 2026-04-20 | `**Type:** D (cross-module refactor, read → design → implementation)` | N |
| `docs/council_reports/council_2026-04-19_11-47.md` | 171 | untracked (mtime: 2026-04-19) | `**Mode:** full (5 advisors + 5 peer reviews + chairman synthesis)` | N |
| `frontend/DEMO/README.md` | 359 | 2026-04-22 | `Redesign of the public /demo page at climb-agent.vercel.app/demo — the primary conversion surface for cold traffic` | Y |
| `reports/users_report_2026-04-05.md` | 59 | untracked (mtime: 2026-04-05) | `(raw data block — no prose intro)` | N |
| `reports/users_report_2026-04-06.md` | 65 | untracked (mtime: 2026-04-06) | `(raw data block — no prose intro)` | N |
| `reports/users_report_2026-04-07.md` | 65 | untracked (mtime: 2026-04-07) | `(raw data block — no prose intro)` | N |

---

## Table 2 — `_archive/**/*.md` files

All files in `_archive/` are gitignored; dates use filesystem mtime.

| path | size_lines | last_modified (YYYY-MM-DD) | first_paragraph_excerpt (max 120 chars) | original_location_guess |
|------|-----------|--------------------------|----------------------------------------|------------------------|
| `_archive/docs/council/council_2026-04-01_11-45.md` | 120 | 2026-04-01 | `climb-agent: launch timing + pricing strategy` | `docs/council_reports/` |
| `_archive/docs/council/council_2026-04-01_16-30.md` | 105 | 2026-04-01 | `climb-agent: next strategic move — build more, wait for feedback, or start charging?` | `docs/council_reports/` |
| `_archive/docs/council/council_2026-04-02_test-peer-review.md` | 158 | 2026-04-02 | `**Mode:** Full (5 advisors + 5 reviewers + chairman)` | `docs/council_reports/` |
| `_archive/docs/council/council_2026-04-03_17-00.md` | 188 | 2026-04-03 | `**Date:** 2026-04-03` | `docs/council_reports/` |
| `_archive/docs/council/council_2026-04-05_10-30.md` | 173 | 2026-04-05 | `> Date: 2026-04-05` | `docs/council_reports/` |
| `_archive/docs/frontend_audit_D163.md` | 270 | 2026-03-28 | `> **Date:** 2026-03-28` | `docs/` (frontend audit moved after D163) |

---

## Table 3 — `scripts/*.py`

| script | last_modified (YYYY-MM-DD) | mentioned_in_CLAUDE.md_section (header name or "—") | mentioned_in_other_doc (file paths or "—") |
|--------|--------------------------|-----------------------------------------------------|-------------------------------------------|
| `scripts/admin_dashboard.py` | 2026-04-07 | — | `docs/ROADMAP_v2.md` |
| `scripts/diag_hang_load.py` | 2026-04-07 | — | — |
| `scripts/diagnose_dropoff.py` | 2026-04-17 | — | `docs/lessons.md`, `docs/audit/D-ANALYTICS-DROPOFF_output.md`, `docs/briefs/A-ACTIVATION-timing_parked.md` |
| `scripts/extract_audit_snapshot.py` | 2026-03-26 | — | `docs/audit_workflow.md`, `docs/audits/D232_new_macrocycle_2026-05-05.md` |
| `scripts/migrate_baseline_fields.py` | 2026-04-07 | — | `docs/ROADMAP_v2.md` |
| `scripts/next_brief.py` | 2026-04-06 | ## Docs maintenance | `docs/lessons.md`, `docs/ROADMAP_v2.md`, `docs/audit/D217_body_part_picker_audit.md`, `docs/audit/D216/findings.md`, `docs/audit/D215/findings.md`, `docs/briefs/B217_session_duration_fix.md`, `docs/audit/D235_project_description_rewrite.md` |
| `scripts/repo_hygiene.py` | 2026-03-26 | ## Workflow rules | — |
| `scripts/retrofit_coldstart_users.py` | 2026-04-17 | — | `docs/ROADMAP_v2.md`, `docs/audits/D232_new_macrocycle_2026-05-05.md` |
| `scripts/simulate_onboarding_start.py` | 2026-04-17 | — | `docs/audits/D232_new_macrocycle_2026-05-05.md`, `docs/briefs/A-ACTIVATION-timing_simulation.md` |
| `scripts/sync_status.py` | 2026-03-30 | ## Commands | `docs/audit_readonly_2026-04-25.md`, `docs/ROADMAP_CURRENT.md`, `docs/audit_docs_D197.md`, `docs/ROADMAP_v2.md`, `docs/audit/D235_project_description_rewrite.md`, `docs/audit/D164/00_SUMMARY.md`, `docs/audit/D164/06_docs_coherence.md`, `docs/briefs/B216_phase1_analysis.md`, `docs/briefs/D214_source_taxonomy_normalization.md`, `docs/briefs/B217_session_duration_fix.md`, `README.md`, `PROJECT_BRIEF.md` |
| `scripts/trim_roadmap.py` | 2026-04-10 | ## Docs maintenance | `docs/lessons.md`, `docs/ROADMAP_v2.md`, `docs/audit_docs_D197.md` |

---

## Notes & anomalies

- **Two parallel `docs/audit*` directories exist with inconsistent naming:** `docs/audit/` (flat + numbered subdirs, 34 files) and `docs/audits/` (3 files, date-stamped names). No clear rule separates which directory a new audit document goes to — naming conventions diverge between these two folders.
- **`docs/audit/D235_project_description_rewrite.md` is untracked (not git-added).** Created today (mtime: 2026-05-09); may be a prior session artifact or in-progress work. The current brief D235 is this inventory, so the filename suggests a different scope.
- **Three report files (`reports/`) are gitignored and untracked:** `users_report_2026-04-05.md`, `users_report_2026-04-06.md`, `users_report_2026-04-07.md`. No reports after 2026-04-07 — the directory appears abandoned.
- **`docs/council_reports/council_2026-04-19_11-47.md` is gitignored (untracked).** A single council report survived outside `_archive/`; the rest were moved to `_archive/docs/council/`.
- **`AUTH_AUDIT.md` (730 lines, 2026-05-04) is at repo root, unmentioned in CLAUDE.md.** Large file, not in a docs subdirectory — likely misplaced relative to `docs/audit/`.
- **`docs/B183_duration_review.md` is at docs root, not inside `docs/audit/`.** Pattern inconsistency vs. all other audit/review files.
- **`docs/outdoor_audit_D170.md` is at docs root.** Same issue — inconsistent with numbered audits being under `docs/audit/`.
- **`docs/A214_phase0_audit.md`, `docs/A215_phase0_audit.md`, `docs/A216_phase0_audit.md` are at docs root.** Three phase-0 audit docs for A-type briefs not placed under `docs/audit/` or `docs/briefs/`.
- **`docs/audit_decision_roadmap_xcheck.md`, `docs/audit_docs_D197.md`, `docs/audit_readonly_2026-04-25.md` are at docs root** — standalone audit files without a consistent home.
- **`docs/briefs/B202_proposal.md`, `B203_proposal.md`, `B204_proposal.md` are 5 lines each** — stub/placeholder files, essentially empty.
- **`_archive/` and `reports/` are entirely gitignored** — all files in those directories are invisible to `git log`; dates are filesystem-only.
- **`diag_hang_load.py`** has no mention in any `.md` file and is not referenced in CLAUDE.md — appears to be an orphan diagnostic script.
- **`scripts/repo_hygiene.py`** is mentioned in CLAUDE.md (## Workflow rules) but appears in no other `.md` doc — sole documentation is the CLAUDE.md line.
- **`docs/design_system_v1.md`** is not mentioned in CLAUDE.md despite being a design artifact (254 lines, last updated 2026-04-24 as part of A214).
