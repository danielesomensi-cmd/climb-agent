# D236 — Subagent B: docs/ obsolescence

Findings: P0=4, P1=18, P2=10, P3=5

Severity legend: P0 = should-be-archived urgent (live ref to obsolete), P1 = obsolete, archive recommended, P2 = redundant/mergeable, P3 = ambiguous, escalate.

---

## Classification table

> Scope: every file in `docs/`, `docs/audit/`, `docs/audits/`, `docs/migrations/`, `docs/briefs/`, `docs/council_reports/`, plus `AUTH_AUDIT.md` and `MEMORY_AUDIT.md` at repo root (misplaced — flagged below). Files in `_archive/`, `reports/`, `.claude/`, `frontend/`, and root reference files (`CLAUDE.md`, `PROJECT_BRIEF.md`, `README.md`) are excluded from scope.
>
> "4 weeks ago" threshold: 2026-04-11. "All findings closed" = brief ID absent from open sections of ROADMAP_CURRENT.md.

| file | classification | rationale (≤ 25 words) | recommended_action | severity |
|------|---------------|------------------------|-------------------|----------|
| `AUTH_AUDIT.md` (repo root) | AMBIGUOUS | Misplaced: should be `docs/audit/`. Large (730L), no open roadmap items, created for Kilter-Up reference. | RENAME_TO docs/audit/AUTH_AUDIT.md | P3 |
| `docs/A214_phase0_audit.md` | OBSOLETE | A214 ✅ Done (2026-04-27). Phase 0 audit superseded by design_system_v1.md. Findings all closed. | ARCHIVE → _archive/docs/A214_phase0_audit.md | P1 |
| `docs/A215_phase0_audit.md` | OBSOLETE | A215 ✅ Done (2026-04-27). Phase 0 audit, all findings implemented. | ARCHIVE → _archive/docs/A215_phase0_audit.md | P1 |
| `docs/A216_phase0_audit.md` | OBSOLETE | A216 ✅ Done (2026-04-27). Phase 0 audit, all findings implemented. | ARCHIVE → _archive/docs/A216_phase0_audit.md | P1 |
| `docs/audit_decision_roadmap_xcheck.md` | OBSOLETE | D-ROADMAP-XCHECK audit from 2026-04-05 (>4 weeks). Decision IDs D01–D91 cross-check, no open actions. | ARCHIVE → _archive/docs/audit_decision_roadmap_xcheck.md | P1 |
| `docs/audit_docs_D197.md` | OBSOLETE | D197 audit from 2026-04-10. A198 cleanup ✅ Done; superseded by D236. Only self-referenced. | ARCHIVE → _archive/docs/audit_docs_D197.md | P1 |
| `docs/audit_readonly_2026-04-25.md` | OBSOLETE | Pre-implementation audit that spawned B227 ✅, B226 ✅; B228 and D229 are open but tracked in ROADMAP — no ref to this file in roadmap. | ARCHIVE → _archive/docs/audit_readonly_2026-04-25.md | P1 |
| `docs/audit_workflow.md` | ACTIVE | Listed in CLAUDE.md (## Documentation architecture). Canonical process reference. | KEEP | — |
| `docs/B183_duration_review.md` | OBSOLETE | B183 ✅ Done (2026-04-02). Misplaced: docs root not docs/audit/. All findings in ROADMAP_v2. | ARCHIVE → _archive/docs/B183_duration_review.md | P1 |
| `docs/beta_feedback.md` | ACTIVE | Listed in CLAUDE.md. Canonical beta tester feedback log. Last updated 2026-03-14; still referenced. | KEEP | — |
| `docs/design_system_v1.md` | ACTIVE | Referenced from `frontend/src/app/dev/tokens/page.tsx` (live code) and `docs/A214_phase0_audit.md`. Not in CLAUDE.md but live code ref. | KEEP | — |
| `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` | ACTIVE | Listed in CLAUDE.md. Canonical design doc for periodization methodology. | KEEP | — |
| `docs/docs_literature_hangboard.md` | ACTIVE | Listed in CLAUDE.md. Canonical hangboard science reference. | KEEP | — |
| `docs/ENGINE_ARCHITECTURE.md` | ACTIVE | Listed in CLAUDE.md. Canonical engine internals reference. | KEEP | — |
| `docs/lessons.md` | ACTIVE | Listed in CLAUDE.md. Append-only lessons log, updated each brief. | KEEP | — |
| `docs/literature_review_climbing_training.md` | ACTIVE | Listed in CLAUDE.md. Canonical climbing science reference. | KEEP | — |
| `docs/outdoor_audit_D170.md` | ACTIVE | Referenced from ROADMAP_CURRENT §D168 as the audit deliverable for an open architecture item. Misplaced: docs root not docs/audit/; rename but keep. | RENAME_TO docs/audit/outdoor_audit_D170.md | — |
| `docs/ROADMAP_CURRENT.md` | ACTIVE | Listed in CLAUDE.md. Living roadmap. | KEEP | — |
| `docs/ROADMAP_v2.md` | ACTIVE | Listed in CLAUDE.md. Append-only archived roadmap. | KEEP | — |
| `docs/user_guide_v1.md` | ACTIVE | Listed in CLAUDE.md. User-facing guide, updated per A/B briefs. | KEEP | — |
| `docs/vocabulary_v1.md` | ACTIVE | Listed in CLAUDE.md. Canonical domain glossary. | KEEP | — |
| `docs/audit/A-MACRO-CAPS_design.md` | ACTIVE | Referenced from ROADMAP_CURRENT:11 and DESIGN_GOAL_MACROCICLO_v1.1.md; cited in test_macrocycle_caps.py. A218 ✅ but design doc remains active spec. | KEEP | — |
| `docs/audit/audit_route_intervals_offset_D93.md` | OBSOLETE | D93 ✅ Done (cited in ROADMAP_v2). Audit older than 4 weeks, single finding closed. Only ROADMAP_v2 references it. | ARCHIVE → _archive/docs/audit/audit_route_intervals_offset_D93.md | P1 |
| `docs/audit/B227_phase0_findings.md` | OBSOLETE | B227 ✅ Done (2026-04-27). Phase 0 findings doc; B227 closed, referenced from test file and ROADMAP_v2 only. >4 weeks old. | ARCHIVE → _archive/docs/audit/B227_phase0_findings.md | P1 |
| `docs/audit/D-ANALYTICS-DROPOFF_output.md` | OBSOLETE | A-ACTIVATION-TIMING ✅ Done; spawned brief closed. Only referenced from AUTH_AUDIT.md (itself misplaced) and legacy scripts. >4 weeks old. | ARCHIVE → _archive/docs/audit/D-ANALYTICS-DROPOFF_output.md | P1 |
| `docs/audit/D-BASELINE-AUDIT_report.md` | OBSOLETE | Pre-cursor to D-TESTUSER-VERIFY; Bundle B ✅ Done (B209/B210/D214/B214/B215). No open findings remain. >4 weeks old. | ARCHIVE → _archive/docs/audit/D-BASELINE-AUDIT_report.md | P1 |
| `docs/audit/D-TESTUSER-VERIFY_report.md` | ACTIVE | Referenced from ROADMAP_CURRENT §1.27 as origin for open F2/F4–F9 residuals. Still active anchor. | KEEP | — |
| `docs/audit/D-TESTWEEK-AUDIT_report.md` | OBSOLETE | Precursor audit to D-TESTUSER-VERIFY; B209 ✅ Done closes its core finding. No open actions remain. Only self-references in audit cluster. | ARCHIVE → _archive/docs/audit/D-TESTWEEK-AUDIT_report.md | P1 |
| `docs/audit/D164/` (10 files) | ACTIVE | Referenced from ROADMAP_CURRENT §1.25 as canonical source for P2/P3 findings still tracked. Open items (B176, R142–R152 etc.) depend on these reports. | KEEP | — |
| `docs/audit/D175_performance_audit.md` | OBSOLETE | D175 ✅ Done (2026-03-31); only referenced from audit_docs_D197.md (itself obsolete). >4 weeks old. | ARCHIVE → _archive/docs/audit/D175_performance_audit.md | P1 |
| `docs/audit/D176_invalidation_map.md` | ACTIVE | Referenced from live production code `frontend/src/lib/query-keys.ts:9` — must keep. A187 closed the implementation, but the map doc is an active code reference. | KEEP | — |
| `docs/audit/D204_session_builder_audit.md` | OBSOLETE | D204 ✅ Done; A205 (Session Builder) implemented. Only ROADMAP_v2 references it (historical). >4 weeks old. | ARCHIVE → _archive/docs/audit/D204_session_builder_audit.md | P1 |
| `docs/audit/D205_subscription_audit_2026_04_16.md` | OBSOLETE | D205 ✅ Done (2026-04-16); spawned B202/B203/B226 all ✅ Done. Only ROADMAP_v2 historical reference. | ARCHIVE → _archive/docs/audit/D205_subscription_audit_2026_04_16.md | P1 |
| `docs/audit/D210_b206_verification.md` | OBSOLETE | D210 ✅ Done. B206 verified; B207 residual tracked in ROADMAP_CURRENT (not referenced to this doc). >4 weeks old. | ARCHIVE → _archive/docs/audit/D210_b206_verification.md | P1 |
| `docs/audit/D215/findings.md` | OBSOLETE | D215 ✅ Done (2026-04-20); B216 ✅ Done closes all findings. Referenced only from B216_phase1_analysis.md (itself obsolete) and test file comments. >4 weeks old. | ARCHIVE → _archive/docs/audit/D215/findings.md | P1 |
| `docs/audit/D215/trace.md` | OBSOLETE | Same status as findings.md — D215 ✅ Done, all closed. No standalone live references. | ARCHIVE → _archive/docs/audit/D215/trace.md | P1 |
| `docs/audit/D216/findings.md` | OBSOLETE | D216 ✅ Done; B217 ✅ Done closes all findings. Referenced from test file and B217_session_duration_fix.md (itself obsolete). >4 weeks old. | ARCHIVE → _archive/docs/audit/D216/findings.md | P1 |
| `docs/audit/D217_body_part_picker_audit.md` | OBSOLETE | D217 fully closed: C208 ✅ Done + A213 ✅ Done. No live references outside ROADMAP_v2 historical entry. >4 weeks old. | ARCHIVE → _archive/docs/audit/D217_body_part_picker_audit.md | P1 |
| `docs/audit/D220_body_part_picker_audit.md` | OBSOLETE | D220 ✅ Done; B221 ✅ Done closes all findings. Only ROADMAP_v2 historical reference. >4 weeks old. | ARCHIVE → _archive/docs/audit/D220_body_part_picker_audit.md | P1 |
| `docs/audit/D223_body_part_picker_classification_audit.md` | OBSOLETE | D223 ✅ Done; B224 ✅ Done. Only ROADMAP_v2 + sibling D223 docs reference it. >4 weeks old. | ARCHIVE → _archive/docs/audit/D223_body_part_picker_classification_audit.md | P1 |
| `docs/audit/D223_body_part_pool_listing.md` | OBSOLETE | D223 ✅ Done; B224 ✅ Done. Only ROADMAP_v2 + D223 cluster references. >4 weeks old. | ARCHIVE → _archive/docs/audit/D223_body_part_pool_listing.md | P1 |
| `docs/audit/D223_c225_research_notes.md` | OBSOLETE | D223 ✅ Done; B224 ✅ Done. Only ROADMAP_v2 references it. Research notes with no future use. >4 weeks old. | ARCHIVE → _archive/docs/audit/D223_c225_research_notes.md | P1 |
| `docs/audit/D223_full_resolver_reclass_impact.md` | OBSOLETE | D223 ✅ Done; B224 ✅ Done. Only ROADMAP_v2 historical reference. >4 weeks old. | ARCHIVE → _archive/docs/audit/D223_full_resolver_reclass_impact.md | P1 |
| `docs/audit/D233_macro_durations_report.md` | ACTIVE | Referenced from ROADMAP_CURRENT:13 (recently closed, predecessor to A218). Also cited in test_macrocycle_caps.py (live code reference). Keep for traceability. | KEEP | — |
| `docs/audit/D234_macro_deadline_findings.md` | ACTIVE | Referenced from ROADMAP_CURRENT:12 alongside D233. Closed 2026-05-07 (A218 predecessor). Keep for near-term traceability. | KEEP | — |
| `docs/audit/D235_project_description_rewrite.md` | AMBIGUOUS | Untracked (not git-added), mtime 2026-05-09. Appears to be an in-progress or orphaned draft from a prior session. | ESCALATE | P3 |
| `docs/audits/D_guided_session_countdown_beep_2026-05-04.md` | OBSOLETE | B247 ✅ Done (2026-05-04). Audit fully closed. Only ROADMAP_v2 historical reference. | ARCHIVE → _archive/docs/audits/D_guided_session_countdown_beep_2026-05-04.md | P1 |
| `docs/audits/D-MEM-002_railway_memory_2026-05-07.md` | AMBIGUOUS | Recent (2026-05-07). Findings listed but no closure brief created yet. Findings not in ROADMAP_CURRENT or v2 as tracked items. Escalate: decide whether to open a remediation brief or accept/defer findings. | ESCALATE | P3 |
| `docs/audits/D232_new_macrocycle_2026-05-05.md` | OBSOLETE | D232 ✅ Done; A-NEW-MACRO ✅ Done (2026-05-05). Only ROADMAP_v2 historical reference. | ARCHIVE → _archive/docs/audits/D232_new_macrocycle_2026-05-05.md | P1 |
| `docs/audits/` (directory, 3 files) | AMBIGUOUS | Plural `docs/audits/` naming conflicts with singular `docs/audit/`. New briefs deposited here inconsistently. Structural issue — should merge into `docs/audit/`. | ESCALATE | P0 |
| `docs/briefs/A-ACTIVATION-timing_parked.md` | OBSOLETE | A-ACTIVATION-TIMING ✅ Done. Parked issues list; none promoted to new roadmap items. No live references. | ARCHIVE → _archive/docs/briefs/A-ACTIVATION-timing_parked.md | P1 |
| `docs/briefs/A-ACTIVATION-timing_phase0.md` | OBSOLETE | A-ACTIVATION-TIMING ✅ Done. Phase 0 analysis completed and STOP gate passed. No live references from active docs. | ARCHIVE → _archive/docs/briefs/A-ACTIVATION-timing_phase0.md | P1 |
| `docs/briefs/A-ACTIVATION-timing_simulation.md` | AMBIGUOUS | A-ACTIVATION-TIMING ✅ Done, but `scripts/simulate_onboarding_start.py` still references this file in comments and the script itself is still present. Referencing a done brief. | ESCALATE | P3 |
| `docs/briefs/A-ACTIVATION-timing_subscription_audit.md` | OBSOLETE | A-ACTIVATION-TIMING ✅ Done; subscription audit sub-doc. Only referenced by _parked.md (itself obsolete). No live references. | ARCHIVE → _archive/docs/briefs/A-ACTIVATION-timing_subscription_audit.md | P1 |
| `docs/briefs/B202_proposal.md` | REDUNDANT | Stub (5 lines). B202 ✅ Done. Content entirely superseded by ROADMAP_v2 entry. No live references. | DELETE | P2 |
| `docs/briefs/B203_proposal.md` | REDUNDANT | Stub (5 lines). B203 ✅ Superseded by B226 ✅ Done. No live references. | DELETE | P2 |
| `docs/briefs/B204_proposal.md` | REDUNDANT | Stub (5 lines). B204 ✅ Superseded by B228 (Open P2). No live references; B228 tracked in ROADMAP_CURRENT. | DELETE | P2 |
| `docs/briefs/B208_proposal.md` | OBSOLETE | B208 ✅ Done (ROADMAP_v2 references this doc). Full proposal doc, superseded by ROADMAP_v2 entry. | ARCHIVE → _archive/docs/briefs/B208_proposal.md | P1 |
| `docs/briefs/B214_B215_phase0_analysis.md` | OBSOLETE | B214 ✅ Done + B215 ✅ Done (Bundle B complete). Phase 0 analysis doc. No live references. | ARCHIVE → _archive/docs/briefs/B214_B215_phase0_analysis.md | P1 |
| `docs/briefs/B216_phase1_analysis.md` | OBSOLETE | B216 ✅ Done. Referenced only from test_week_rollover_B216.py comment (historical). | ARCHIVE → _archive/docs/briefs/B216_phase1_analysis.md | P1 |
| `docs/briefs/B217_session_duration_fix.md` | OBSOLETE | B217 ✅ Done. Only referenced from test file comment (historical). | ARCHIVE → _archive/docs/briefs/B217_session_duration_fix.md | P1 |
| `docs/briefs/D214_phase0_analysis.md` | OBSOLETE | D214 ✅ Done (Bundle B). Self-referencing cluster only. No live references from active docs. | ARCHIVE → _archive/docs/briefs/D214_phase0_analysis.md | P1 |
| `docs/briefs/D214_source_taxonomy_normalization.md` | OBSOLETE | D214 ✅ Done (Bundle B). Only referenced from D214_phase0_analysis.md (itself obsolete). | ARCHIVE → _archive/docs/briefs/D214_source_taxonomy_normalization.md | P1 |
| `docs/council_reports/council_2026-04-19_11-47.md` | REDUNDANT | Gitignored, untracked. Council reports archived to `_archive/docs/council/`. This one survived outside archive — should complete the move. | ARCHIVE → _archive/docs/council/council_2026-04-19_11-47.md | P2 |
| `docs/migrations/subscriptions_table.sql` | OBSOLETE | A159/Stripe migration ✅ confirmed run in Supabase (ROADMAP_CURRENT confirms: "SQL migration confirmed 2026-03-31"). Migration already applied in production. | ARCHIVE → _archive/docs/migrations/subscriptions_table.sql | P2 |
| `frontend/DEMO/README.md` | OBSOLETE | A-DEMO-01 + B-DEMO-02 + B-DEMO-05 all ✅ Done. DEMO feature shipped and live. Design notes in README no longer drive any open work. | ARCHIVE → _archive/docs/frontend_DEMO_README.md | P2 |
| `reports/users_report_2026-04-05.md` | REDUNDANT | Gitignored, untracked. Raw data snapshot, no prose analysis. No follow-up reports after 2026-04-07 — directory appears abandoned. | DELETE | P2 |
| `reports/users_report_2026-04-06.md` | REDUNDANT | Same as above. | DELETE | P2 |
| `reports/users_report_2026-04-07.md` | REDUNDANT | Same as above. | DELETE | P2 |

---

## Structural P0 findings

### P0-A — `docs/audits/` vs `docs/audit/` directory naming conflict

The repo contains two parallel directories: `docs/audit/` (singular, 34 files) and `docs/audits/` (plural, 3 files). No rule governs which directory a new audit goes to. Three files deposited inconsistently in `docs/audits/`:
- `docs/audits/D_guided_session_countdown_beep_2026-05-04.md`
- `docs/audits/D-MEM-002_railway_memory_2026-05-07.md`
- `docs/audits/D232_new_macrocycle_2026-05-05.md`

**Resolution:** Consolidate all content into `docs/audit/` (singular), add a note to CLAUDE.md specifying the canonical name. The plural `docs/audits/` directory should be eliminated. After the two non-obsolete files (`D-MEM-002`, which is ambiguous) are moved, the directory becomes empty.

### P0-B — ROADMAP_CURRENT references a file that no longer exists at the cited path

`docs/ROADMAP_CURRENT.md:19` cites `docs/audit/D163_frontend_audit.md`. This file does **not exist** at that path — it was archived to `_archive/docs/frontend_audit_D163.md` by A198 (2026-04-07). The broken reference causes any reader following the link to find nothing.

**Resolution:** Update ROADMAP_CURRENT §1.25 to either remove the reference or update it to `_archive/docs/frontend_audit_D163.md`.

### P0-C — ROADMAP_CURRENT references a tracker file that was never created

`docs/ROADMAP_CURRENT.md:43` cites `docs/audit/D172_findings_tracker.md` as the full 25-finding breakdown for Priority 1.26. This file does not exist anywhere in the repo (not at `docs/audit/`, not in `_archive/`). The 25-finding D172 audit findings have no tracking doc.

**Resolution:** Either create a minimal tracker or update ROADMAP_CURRENT to note the tracker was never created and findings are tracked inline in the roadmap.

### P0-D — `docs/audits/` structural naming issue (see above — P0-A)

---

## Live → obsolete references

- `docs/ROADMAP_CURRENT.md:19` cites `docs/audit/D163_frontend_audit.md` — file is at `_archive/docs/frontend_audit_D163.md` (archived by A198). **Broken ref → P0.**
- `docs/ROADMAP_CURRENT.md:43` cites `docs/audit/D172_findings_tracker.md` — file does **not exist** anywhere. **Broken ref → P0.**
- `docs/ROADMAP_CURRENT.md:11` cites `D233_macro_durations_report.md` and `D234_macro_deadline_findings.md` → both classified ACTIVE (recently closed), no action needed.
- `docs/audit_docs_D197.md` (classified OBSOLETE) cites `docs/audit/D175_performance_audit.md` (classified OBSOLETE), `docs/audit/D176_invalidation_map.md` (classified ACTIVE), `docs/outdoor_audit_D170.md` (classified ACTIVE/RENAME). No action needed beyond archiving `audit_docs_D197.md`.
- `AUTH_AUDIT.md` (root, classified AMBIGUOUS) cites `docs/audit/D-ANALYTICS-DROPOFF_output.md` (classified OBSOLETE) and `docs/migrations/subscriptions_table.sql` (classified OBSOLETE). If AUTH_AUDIT.md is moved to `docs/audit/`, these internal citations remain readable but point to archived content — acceptable.
- `docs/briefs/A-ACTIVATION-timing_simulation.md` (classified OBSOLETE) is referenced by `backend/engine/start_date_utils.py` and `scripts/simulate_onboarding_start.py` — not by a live `.md` file. Code comments citing a doc brief are historical and not broken references in the doc sense.
- `frontend/src/lib/query-keys.ts:9` cites `docs/audit/D176_invalidation_map.md` (classified ACTIVE) → no issue.
- `backend/tests/test_source_taxonomy.py` cites D-TESTUSER-VERIFY (classified ACTIVE) → no issue.
- `backend/tests/test_week_rollover_B216.py` and `backend/tests/test_feedback_duration_B217.py` cite obsolete brief docs in comments → historical, no action needed.

---

## Quick wins

Three files that are clearly safe to remove with zero ambiguity:

1. **`docs/briefs/B202_proposal.md`** — 5-line stub, brief ✅ Done, no references anywhere. `DELETE`.
2. **`docs/briefs/B203_proposal.md`** — 5-line stub, superseded by B226 ✅ Done, no references anywhere. `DELETE`.
3. **`docs/briefs/B204_proposal.md`** — 5-line stub, superseded by B228 (tracked in ROADMAP_CURRENT), no references anywhere. `DELETE`.

Runners-up (safe archive, no cross-ref risk):
- `reports/users_report_2026-04-05.md`, `…-04-06.md`, `…-04-07.md` — gitignored raw data, no references, directory abandoned since April 2026.
- `docs/council_reports/council_2026-04-19_11-47.md` — gitignored, should have been archived with the other council reports.

---

## Notes on misplaced files

The following files are in the wrong location (docs root instead of `docs/audit/` or `docs/briefs/`), flagged for renaming regardless of obsolescence status:

| file | correct location |
|------|-----------------|
| `docs/B183_duration_review.md` | `docs/audit/B183_duration_review.md` |
| `docs/outdoor_audit_D170.md` | `docs/audit/outdoor_audit_D170.md` |
| `docs/A214_phase0_audit.md` | `docs/audit/A214_phase0_audit.md` (or archive) |
| `docs/A215_phase0_audit.md` | `docs/audit/A215_phase0_audit.md` (or archive) |
| `docs/A216_phase0_audit.md` | `docs/audit/A216_phase0_audit.md` (or archive) |
| `docs/audit_decision_roadmap_xcheck.md` | `docs/audit/D-ROADMAP-XCHECK_audit.md` (or archive) |
| `docs/audit_docs_D197.md` | `docs/audit/D197_docs_audit.md` (or archive) |
| `docs/audit_readonly_2026-04-25.md` | `docs/audit/D-READONLY-2026-04-25_audit.md` (or archive) |
| `AUTH_AUDIT.md` (repo root) | `docs/audit/AUTH_AUDIT.md` |
