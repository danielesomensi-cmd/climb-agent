# D236 — Master Findings (Phase 2 synthesis)

**Brief:** D236 — Repo & Docs Cleanup Audit (read-only)
**Generated:** 2026-05-09
**Inputs:** `00_inventory.md`, `01_consistency.md`, `02_docs_obsolescence.md`, `03_archive_refs.md`, `04_status_drift.md`
**Method:** Aggressive deduplication of 78 raw findings into a single canonical list. Every finding has exactly one ID; the `sources` column shows which subagent(s) reported it.

---

## Summary

| metric | value |
|---|---|
| Raw findings (sum across 4 subagents) | 78 |
| Unique findings (deduplicated) | **47** |
| P0 | 6 |
| P1 | 22 |
| P2 | 13 |
| P3 | 6 |

Subagent contribution map (raw → unique): A=15→13, B=37→22, C=6→3, D=13→11. Net dedup ratio: 40%.

---

## Master findings table

Severity legend:
- **P0** = blocking (broken citation in live planning doc, lie about prod state, structural directory conflict)
- **P1** = clear contradiction or stale fact requiring near-term fix
- **P2** = stale but recoverable (cosmetic counts, low-impact phrases)
- **P3** = ambiguous / cosmetic / escalation

Action codes used in the table: `FIX_TEXT` (in-place edit) · `ARCHIVE` (move to `_archive/`) · `DELETE` · `RENAME` · `RESTORE` (recover from git) · `MERGE` · `ESCALATE` · `FIX_SCRIPT` · `KEEP_BUT_FLAG`.

| id | severity | category | description (≤ 30 words) | files / location | sources | recommended_action | group |
|---|---|---|---|---|---|---|---|
| **F-01** | P0 | sync-script | `sync_status.py:200-202` regex matches "1 app-level health check" but CLAUDE.md says "2 app-level: health check + stripe webhook" → silent no-op every run. Replacement also wrong (uses `endpoints-1`, should be `endpoints-2`). | `scripts/sync_status.py:200-202` | A-F01, A-F11, A-Notes | FIX_SCRIPT (Group 0) | 0 |
| **F-02** | P0 | status-drift | Stripe described as "sk_test verified — temporarily disabled for open beta" while sk_live runs in prod since 2026-04-16. | `PROJECT_BRIEF.md:76` | A-F04, D-P0 | FIX_TEXT (Group 1) | 1 |
| **F-03** | P0 | status-drift | ROADMAP "Stripe status: A159 implemented in TEST MODE. Not live. Currently disabled" — opposite of reality. Lives at line 85 of GTM Sprint block, read before every GTM brief. | `docs/ROADMAP_CURRENT.md:85,89` | A-F03, D-F02, D-F03 | FIX_TEXT (Group 1) | 1 |
| **F-04** | P0 | status-drift | Pricing "decision" row: "EUR 14.99/month, 14-day trial, Founding Climber EUR 9.99 lifetime for first 50 users" — wrong on currency, amounts, trial days, user cap. | `docs/ROADMAP_CURRENT.md:388` | D-F04 | FIX_TEXT (Group 1) | 1 |
| **F-05** | P0 | broken-ref | ROADMAP cites `docs/audit/D163_frontend_audit.md` — not at that path; the file is at `_archive/docs/frontend_audit_D163.md`. Broken link. | `docs/ROADMAP_CURRENT.md:19` | B-P0-B | FIX_TEXT (Group 6) | 6 |
| **F-06** | P0 | broken-ref | ROADMAP cites `docs/audit/D172_findings_tracker.md` — file does not exist anywhere. Tracker was never created; 25 D172 findings sit untracked. | `docs/ROADMAP_CURRENT.md:43` | B-P0-C | FIX_TEXT or CREATE_TRACKER (Group 6) | 6 |
| **F-07** | P0 | broken-ref | ROADMAP cites `_archive/docs/horst_integration_audit.md` at 4 sites as authoritative KB. File never moved to `_archive/` (commit 00cdc33 mislabeled deletion as archive). Recoverable from git 70dadfa. | `docs/ROADMAP_CURRENT.md:244, 253, 254, 612` | C-P1, see §Post-mortem | RESTORE (Group 6) | 6 |
| **F-08** | P0 | structure | `docs/audits/` (plural, 3 files) and `docs/audit/` (singular, 34 files) coexist. No documented rule. New audits dropped inconsistently. | `docs/audits/` (entire dir) | B-P0-A, B-P0-D | RENAME + MERGE (Group 4) | 4 |
| **F-09** | P1 | counter-drift | CLAUDE.md endpoint count "64 (62 router + 2 app-level)" stale — real count is 68 (66 router + 2 app-level). 4 endpoint rows also missing from the table. | `CLAUDE.md:149` and endpoint table | A-F01, A-Notes | FIX_TEXT (post-Group-0 sync run) | 3 |
| **F-10** | P1 | counter-drift | CLAUDE.md "13 indoor + 3 outdoor intents" stale — real is 15 indoor + 4 outdoor. | `CLAUDE.md:144` | A-F02, D-F05, D229 | FIX_TEXT (Group 3) | 3 |
| **F-11** | P1 | counter-drift | ENGINE_ARCHITECTURE §9 "13 indoor / 3 outdoor intents" stale; intent enumeration also missing 3 indoor + 1 outdoor. | `docs/ENGINE_ARCHITECTURE.md:496, 503` | A-F02, A-F08 | FIX_TEXT (Group 3) | 3 |
| **F-12** | P1 | counter-drift | Macrocycle duration "10-13 weeks" stale (pre-A218). Ground truth: lead 11–16, boulder 8–16. | `PROJECT_BRIEF.md:45`, `README.md:26` | A-F05, D-F06 | FIX_TEXT (Group 3) | 3 |
| **F-13** | P1 | counter-drift | vocabulary lists 27 module template_ids in §3 header; only 19 JSON files on disk. 8 orphan entries. | `docs/vocabulary_v1.md:665` | A-F07 | FIX_TEXT + verify (Group 3) | 3 |
| **F-14** | P1 | counter-drift | ENGINE_ARCHITECTURE `_SESSION_META` count "34 sessions registered (as of D163)" stale — code now has 31 entries (4 test sessions removed post-D163). | `docs/ENGINE_ARCHITECTURE.md:706` | A-F06 | FIX_TEXT (Group 3) | 3 |
| **F-15** | P1 | code-ref | CLAUDE.md `closed_loop_v1.py` filename stale — real path is `backend/engine/adaptation/closed_loop.py`. | `CLAUDE.md:62, 85` | A-F10, ROADMAP:31 | FIX_TEXT (Group 3) | 3 |
| **F-16** | P1 | code-ref | CLAUDE.md import example uses `planner_v1` — should reference `planner_v2` to match active engine. | `CLAUDE.md:103` | A-F09 | FIX_TEXT (Group 3) | 3 |
| **F-17** | P1 | status-drift | design_system_v1.md lists A215/A216/A217 as "Downstream briefs (planned)" — all three ✅ Done 2026-04-27. | `docs/design_system_v1.md:254` | D-F07 | FIX_TEXT (Group 2) | 2 |
| **F-18** | P1 | obsolete-doc | `docs/A214_phase0_audit.md` — A214 ✅ Done. Misplaced (root, not `docs/audit/`). | `docs/A214_phase0_audit.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-19** | P1 | obsolete-doc | `docs/A215_phase0_audit.md` — A215 ✅ Done. Misplaced. | `docs/A215_phase0_audit.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-20** | P1 | obsolete-doc | `docs/A216_phase0_audit.md` — A216 ✅ Done. Misplaced. | `docs/A216_phase0_audit.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-21** | P1 | obsolete-doc | `docs/audit_decision_roadmap_xcheck.md` — D-ROADMAP-XCHECK closed 2026-04-05. | `docs/audit_decision_roadmap_xcheck.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-22** | P1 | obsolete-doc | `docs/audit_docs_D197.md` — D197 closed; A198 cleanup ✅; superseded by D236. Self-referenced only. | `docs/audit_docs_D197.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-23** | P1 | obsolete-doc | `docs/audit_readonly_2026-04-25.md` — pre-implementation audit; spawned briefs B227/B226 ✅. | `docs/audit_readonly_2026-04-25.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-24** | P1 | obsolete-doc | `docs/B183_duration_review.md` — B183 ✅ Done. Misplaced. | `docs/B183_duration_review.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-25** | P1 | obsolete-doc | 11 closed audits in `docs/audit/` >4 weeks old, all findings closed (D93, B227, D-ANALYTICS-DROPOFF, D-BASELINE-AUDIT, D-TESTWEEK-AUDIT, D175, D204, D205, D210, D215/, D216/). | `docs/audit/D*` | B-T1 | ARCHIVE bulk (Group 4) | 4 |
| **F-26** | P1 | obsolete-doc | 6 closed body-part-picker D217/D220/D223 audits + research notes — all underlying briefs (B221/B224/A213/C208) ✅. | `docs/audit/D217*`, `D220*`, `D223*` (5 files) | B-T1 | ARCHIVE bulk (Group 4) | 4 |
| **F-27** | P1 | obsolete-doc | 7 closed brief-process docs in `docs/briefs/` (A-ACTIVATION-timing × 3, B208, B214/B215_phase0, B216, B217, D214 × 2). All linked briefs ✅. | `docs/briefs/A-ACT*`, `B208`, `B214_B215`, `B216`, `B217`, `D214*` | B-T1 | ARCHIVE bulk (Group 4) | 4 |
| **F-28** | P1 | obsolete-doc | 2 audits in `docs/audits/` (plural) closed: `D232_new_macrocycle_2026-05-05.md`, `D_guided_session_countdown_beep_2026-05-04.md` — A-NEW-MACRO ✅, B247 ✅. | `docs/audits/D232*`, `docs/audits/D_guided_session*` | B-T1 | ARCHIVE during Group 4 dir-merge | 4 |
| **F-29** | P2 | redundant | 3 stub `B202/B203/B204_proposal.md` (5 lines each). All briefs ✅. Zero references. | `docs/briefs/B202_proposal.md`, `B203_proposal.md`, `B204_proposal.md` | B-Quickwin#1-3 | DELETE (Group 1) | 1 |
| **F-30** | P2 | redundant | 3 `users_report_*` raw data dumps gitignored, no references, dir abandoned. | `reports/users_report_2026-04-{05,06,07}.md` | B-T1 | DELETE (Group 1) | 1 |
| **F-31** | P2 | redundant | `council_2026-04-19_11-47.md` orphaned — siblings already in `_archive/docs/council/`. Gitignored. | `docs/council_reports/council_2026-04-19_11-47.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-32** | P2 | obsolete-doc | `docs/migrations/subscriptions_table.sql` — A159 migration confirmed run 2026-03-31. | `docs/migrations/subscriptions_table.sql` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-33** | P2 | obsolete-doc | `frontend/DEMO/README.md` — A-DEMO-01/B-DEMO-02/B-DEMO-05 ✅. Demo shipped. | `frontend/DEMO/README.md` | B-T1 | ARCHIVE (Group 4) | 4 |
| **F-34** | P2 | misplaced | `docs/outdoor_audit_D170.md` — actively referenced (D168 in ROADMAP) but misplaced (docs root, not `docs/audit/`). | `docs/outdoor_audit_D170.md` | B-T1 | RENAME (Group 5) | 5 |
| **F-35** | P2 | status-drift | DESIGN doc §12b "spec futura" while Guided Session is shipped (`/guided/[date]/[sessionId]`). | `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:457, 461` | D-F08, D-F09 | FIX_TEXT (Group 2) | 2 |
| **F-36** | P2 | counter-drift | ENGINE_ARCHITECTURE "13 sort categories" while vocabulary §5.8 + code list 14 (incl. `main_unclassified` fallback). | `docs/ENGINE_ARCHITECTURE.md:550` | A-F14 | FIX_TEXT (Group 3) | 3 |
| **F-37** | P2 | sync-script | `validate()` in `sync_status.py` only checks vocab→disk direction (file missing from vocab). Reverse direction (vocab entry with no file) invisible — root cause of F-13 going undetected. | `scripts/sync_status.py:233-261` | A-F07, A-Notes | FIX_SCRIPT (Group 0) | 0 |
| **F-38** | P2 | sync-script | `validate()` does NOT compare CLAUDE.md endpoint header vs real code count. Only checks header-vs-table consistency. So drift between code and CLAUDE.md table can persist indefinitely without warning. | `scripts/sync_status.py:263-275` | A-F11 derivative | FIX_SCRIPT (Group 0) | 0 |
| **F-39** | P2 | sync-script | `sync_status.py` does not auto-update the API endpoint **table rows** in CLAUDE.md, only the inline header. New endpoints require manual table edit → drift risk. | `scripts/sync_status.py` (whole script) | F-09 derivative | FIX_SCRIPT (Group 0) or document limit | 0 |
| **F-40** | P2 | sync-script | `sync_status.py` does not touch tech-stack tables or arbitrary status rows in PROJECT_BRIEF / ROADMAP — F-02/F-03/F-04 cannot be auto-synced. Document the limit, do not over-promise. | `scripts/sync_status.py` (whole script) | F-02/F-03/F-04 derivative | DOCUMENT (Group 0) | 0 |
| **F-41** | P3 | misplaced | `AUTH_AUDIT.md` (root, 730 lines) — should be in `docs/audit/`. ACTIVE doc, not obsolete. | `AUTH_AUDIT.md` | B-T1 | RENAME (Group 5) | 5 |
| **F-42** | P3 | misplaced | `MEMORY_AUDIT.md` (root) — D-MEM-002 output (untracked, 21 KB). Subagent A says it doesn't exist, Subagent B says it's misplaced — actually exists, untracked. Decide: archive, rename to `docs/audits/`, or commit at root. | `MEMORY_AUDIT.md` | A-Notes (mismatch), B-Scope | ESCALATE | 5 |
| **F-43** | P3 | escalate | `docs/audit/D235_project_description_rewrite.md` — untracked draft, separate scope from D236. Daniele owns. | `docs/audit/D235_project_description_rewrite.md` | B-T1 | ESCALATE | 5 |
| **F-44** | P3 | escalate | `docs/audits/D-MEM-002_railway_memory_2026-05-07.md` — recent audit, findings not yet tracked in ROADMAP. Decide remediation brief or accept. | `docs/audits/D-MEM-002_railway_memory_2026-05-07.md` | B-T1 | ESCALATE (Group 5) | 5 |
| **F-45** | P3 | escalate | `docs/briefs/A-ACTIVATION-timing_simulation.md` — referenced from `scripts/simulate_onboarding_start.py` and `backend/engine/start_date_utils.py` comments. Brief ✅ Done; reference is comment-only. | `docs/briefs/A-ACTIVATION-timing_simulation.md` | B-T1 | ESCALATE (Group 5) | 5 |
| **F-46** | P3 | counter-drift | CLAUDE.md "3-pass algorithm" simplification of 6-pass real algorithm (passes 1, 1.5, 2, 2.2, 2.5, 3). Deliberate but technically wrong. | `CLAUDE.md:143` | A-F12 | FIX_TEXT (Group 3, optional) | 3 |
| **F-47** | P3 | cosmetic | DESIGN doc header "Versione: 1.2 (file: v1.1)" — file name vs internal version mismatch. | `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:4` | A-F13 | FIX_TEXT (Group 3, optional) | 3 |

---

## §Root causes

For every drift, what *caused* it. Findings sharing a cause are listed together — the cause is the load-bearing fix.

### RC-1 — `sync_status.py` regex broken (CLAUDE.md endpoint count)

**Fix:** F-01.
**Symptoms it caused:** F-09 (CLAUDE.md endpoint count stuck at 64 vs real 68). Possibly also delayed detection of F-10/F-11 since the broken sync hides counter drift entirely.
**Origin:** Regex was correct when written (1 app-level health check). When the Stripe webhook was added as a 2nd app-level route (commit-unknown, around B202/A159 timeframe), CLAUDE.md text was updated to "2 app-level: health check + stripe webhook" but the regex was not updated. Bug present since Stripe webhook integration.
**Severity of root cause:** P0 (every CLAUDE.md endpoint count fix is fragile until this is fixed).

### RC-2 — `sync_status.py` validate() incomplete

**Fix:** F-37, F-38, F-39, F-40.
**Symptoms it caused:** F-13 (8 orphan template entries in vocabulary undetected for unknown duration). F-09 silently persisting (no validation comparing CLAUDE.md header to real code count).
**Origin:** The script was designed to push code-counts into docs but its validation surface is narrow: only file→vocab direction, only table-rows→declared-header within CLAUDE.md. Cross-doc and reverse-direction invariants invisible.
**Severity of root cause:** P1 (drift continues silently in absence of these checks).

### RC-3 — Stripe go-live (2026-04-16) not retroactively swept across docs

**Fix:** F-02, F-03, F-04.
**Symptoms:** Three independent assertions across PROJECT_BRIEF, ROADMAP, and pricing decision row — all stale by ~3 weeks. None auto-syncable (`sync_status.py` does not touch tech-stack rows, status callouts, or pricing tables).
**Origin:** No retro-sweep procedure documented in `CLAUDE.md` for "after a go-live, search docs for the pre-live language." The go-live fix was applied where it was top-of-mind (CLAUDE.md §Deployment, ROADMAP line 137) and missed elsewhere.
**Severity of root cause:** P0 for blocking lies (F-02), P1 for everything else.

### RC-4 — A218 macrocycle cap rewrite (2026-05-07) not retroactively swept

**Fix:** F-12.
**Symptoms:** PROJECT_BRIEF and README still say "10-13 weeks" while code/DESIGN/vocabulary all moved to "lead 11–16 / boulder 8–16".
**Origin:** Same class of issue as RC-3. The A218 brief updated authoritative sources (DESIGN, vocabulary, code) but did not run a `grep "10-13"` on the doc tree.
**Severity of root cause:** P1.

### RC-5 — Misleading "archive" commit (2026-03-31, 00cdc33)

**Fix:** F-07 (resolution requires understanding RC-5 first).
**Symptoms:** 4 dangling citations in ROADMAP_CURRENT.md to a `_archive/docs/horst_integration_audit.md` path that **never existed**.
**Origin:** Commit message said "Archived to `_archive/docs/`" but the diff shows pure deletion (5 files deleted, 0 added under `_archive/`). The ROADMAP citations were rewritten to the *intended* archive path without verifying the archival actually happened. See §Post-mortem below.
**Severity of root cause:** P0 (broken authoritative citations in active planning doc).

### RC-6 — `docs/audits/` (plural) directory drift

**Fix:** F-08.
**Symptoms:** 3 audits dropped in plural dir; pattern looks like a recent typo that propagated. No documented rule in CLAUDE.md (the §"Repository structure" tree shows `docs/` flat, doesn't list `audit/` vs `audits/`).
**Origin:** Inconsistent naming convention. CLAUDE.md never specifies the canonical path for audit deliverables, so different sessions chose differently.
**Severity of root cause:** P0 (structural).

### RC-7 — Closed-audit accumulation in live `docs/`

**Fix:** F-18 through F-28 (24 obsolete docs).
**Symptoms:** `docs/` and `docs/audit/` and `docs/briefs/` accumulate closed-brief deliverables. `repo_hygiene.py` is supposed to catch this every ~2 weeks but the last full audit was D156 (2026-03-25, ~6 weeks ago).
**Origin:** Hygiene cadence not enforced; no "archive on brief close" rule (CLAUDE.md only mentions sync_status, not archival).
**Severity of root cause:** P1 (drift, not blocking, but bloats repo).

### RC-8 — D229 still open

**Fix:** F-09, F-10, F-11, F-15.
**Symptoms:** All four findings already tracked in D229 since 2026-04-27. D229 itself is open ("30 min, single commit") but unscheduled.
**Origin:** D229 was identified but not closed; D236 re-discovered the same issues.
**Severity of root cause:** P1 (just close D229; this audit confirms its scope).

---

## §Post-mortem — `_archive/docs/horst_integration_audit.md`

**Question:** Was the file deleted erroneously or intentionally? Are the 4 ROADMAP citations recoverable from git history?

### Timeline (verified via git log)

| commit | date | action |
|---|---|---|
| `70dadfa` | 2026-03-27 | **CREATED** at `docs/horst_integration_audit.md` (220 lines) — Daniele Somensi + Claude Opus 4.6, "docs: add KB Research Integration section to roadmap + 3 research docs". ROADMAP citations added with relative path `horst_integration_audit.md`. |
| `00cdc33` | 2026-03-31 | **DELETED** (NOT moved to `_archive/`) — Daniele Somensi + Claude Sonnet 4.6, commit message: "docs: archive 4 completed reference docs". The diff shows 5 files changed, 856 deletions, 5 insertions — only deletions; no `_archive/docs/horst_integration_audit.md` addition. ROADMAP citations rewritten in the same commit to `_archive/docs/horst_integration_audit.md` (path that never existed). |

### Root cause classification

**Misleading commit (Claude Sonnet 4.6 archive operation, 2026-03-31).** The intent stated in the commit message was archival (move). The actual operation was deletion (remove). The ROADMAP citations were updated to the *intended* archive path as if the move had succeeded — but no verification step confirmed the file landed there. Result: 4 dangling citations to a ghost file.

**Was it erroneous?** Likely yes. The file's content (220 lines synthesizing Hörst Ch. 5–6 cues for D33 warm-up + CUE-02) was the authoritative source for at least one open backlog item (D33 warm-up). The accompanying claim "findings referenced inline in backlog" in the commit message is partially true (the ROADMAP table was annotated with KB references) but incomplete: the citations *to the file itself* weren't replaced with inline content — they were rewritten to a non-existent path.

### Recovery options

| option | feasibility | cost | risk |
|---|---|---|---|
| **(a) RESTORE from git history** to `_archive/docs/horst_integration_audit.md` (matching existing citations) | ✅ Trivially feasible: `git show 70dadfa:docs/horst_integration_audit.md > _archive/docs/horst_integration_audit.md` | 1 minute | Zero. Original content preserved exactly. |
| **(b) RESTORE to `docs/audit/horst_integration_audit.md`** (live, not archive) and update the 4 citations | ✅ Feasible: same `git show` + 4 citation edits | 5 minutes | Low. May invalidate the archival rationale ("found redundant") but restores citation integrity. |
| **(c) REWRITE from external KB project** (claude.ai "climb-agent knowledge base" project) | Possible but unverified — depends on whether KB project still has the source | 30+ min | Medium: may not match original audit numbering / section structure. |
| **(d) DROP all 4 ROADMAP citations**, accept that D33 / CUE-02 / coaching-cue specs lose their KB anchor | ✅ Trivially feasible | 5 minutes | High: loses authoritative source for at least 3 deferred backlog items. |

### Recommended action (Group 6 — Phase 2)

**(a) RESTORE from git history**, no rewrite. The original audit content is intact at commit 70dadfa, exactly matching the 4 ROADMAP citations (`§5`, `§6`). Cost is one minute, the citation surface stays exactly as documented in ROADMAP since 2026-03-27, and the underlying KB material returns to operational reach for D33/CUE-02 implementors. If Daniele later wants to re-archive, the file will at least *exist* at the path the rest of the system already expects.

**Concrete command** (read-only audit cannot run this; deferred to follow-up C-brief):
```bash
git show 70dadfa:docs/horst_integration_audit.md > _archive/docs/horst_integration_audit.md
git add _archive/docs/horst_integration_audit.md
git commit -m "C<NUM>: restore horst_integration_audit.md from git history (D236-F07)"
```

---

## §Live → obsolete reference matrix

(deduplicated from Subagent B + C)

| live referrer | cited target | target classification | severity | action |
|---|---|---|---|---|
| `docs/ROADMAP_CURRENT.md:19` | `docs/audit/D163_frontend_audit.md` | does not exist (lives at `_archive/docs/frontend_audit_D163.md`) | P0 | Update citation path → F-05 |
| `docs/ROADMAP_CURRENT.md:43` | `docs/audit/D172_findings_tracker.md` | never existed | P0 | Either create or remove citation → F-06 |
| `docs/ROADMAP_CURRENT.md:244, 253, 254, 612` | `_archive/docs/horst_integration_audit.md` | never existed at this path; deleted at `docs/` | P0 | RESTORE from git → F-07 |
| `docs/audit_docs_D197.md:28, 76-80, 113, 133` | various `_archive/` files | mention-only in audit table; no functional dep | P2 | No action (D197 itself archives in F-22) |
| `AUTH_AUDIT.md` (root) | `docs/audit/D-ANALYTICS-DROPOFF_output.md`, `docs/migrations/subscriptions_table.sql` | both classified OBSOLETE in F-25 / F-32 | P3 | If AUTH_AUDIT moves under `docs/audit/` (F-41), citation paths to obsolete docs remain readable post-archive. Acceptable. |
| `frontend/src/lib/query-keys.ts:9` | `docs/audit/D176_invalidation_map.md` | classified ACTIVE | — | No action needed |
| `backend/engine/start_date_utils.py`, `scripts/simulate_onboarding_start.py` | `docs/briefs/A-ACTIVATION-timing_simulation.md` | brief ✅ Done | P3 | Code comments to a closed-brief doc. Either keep (historical) or escalate → F-45 |

---

## §Reverse archive orphans

All 6 files currently under `_archive/` are pure orphans (no live references AND no cross-references between them):

- `_archive/docs/council/council_2026-04-01_11-45.md`
- `_archive/docs/council/council_2026-04-01_16-30.md`
- `_archive/docs/council/council_2026-04-02_test-peer-review.md`
- `_archive/docs/council/council_2026-04-03_17-00.md`
- `_archive/docs/council/council_2026-04-05_10-30.md`
- `_archive/docs/frontend_audit_D163.md`

Quasi-references exist only in the (about-to-be-archived) `docs/audit_docs_D197.md`. After D197 archives (F-22), these 6 council/audit files will have **zero references anywhere**. Eligible for deletion in a follow-up cleanup C-brief — explicitly out of D236 scope.

---

## §Notes on subagent disagreements (resolved)

1. **`MEMORY_AUDIT.md` existence.** Subagent A claimed "does not exist at root"; Subagent B classified it as "AMBIGUOUS, misplaced". Verified during synthesis: file exists, is untracked, was created by D-MEM-002 (2026-05-07). Outcome: F-42 (escalate — Daniele decides whether to commit, archive, or move).

2. **AUTH_AUDIT.md classification.** Subagent A noted the file contains no counters that conflict with other docs. Subagent B classified AMBIGUOUS / misplaced. Outcome: F-41 (RENAME to `docs/audit/AUTH_AUDIT.md`, no content change).

3. **Counter for D229's claim "67 endpoints (real)".** D229 says "real = 67"; current real count is 68 (verified via `count_api_endpoints()` in sync_status.py + endpoint table walk). One additional endpoint added since D229 was filed (~2026-04-27).
