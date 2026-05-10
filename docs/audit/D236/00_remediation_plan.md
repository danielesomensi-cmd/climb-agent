# D236 — Remediation Plan (Phase 2 synthesis)

**Source:** 47 deduplicated findings in `00_findings.md`.
**Output of D236:** This plan. Execution lives in follow-up briefs (Group 0 = B-brief; Groups 1–6 = C-briefs).
**Ordering:** risk-ascending, with Group 0 as a hard prerequisite to Group 3 (counter fixes would be re-broken by next sync run otherwise).

---

## Execution dependency graph

```
Group 0 (B-brief, sync_status.py fixes)  ──── prerequisite ────►  Group 3 (counter fixes)
        │
        └── independent ────────────►  Groups 1, 2, 4, 5, 6  (any order, parallelisable)
```

**Rule:** Groups 1, 2, 4, 5, 6 may execute in any order. **Group 3 MUST execute after Group 0** — otherwise the next sync run will re-break the regex-broken counters or, worse, leave them stale silently.

---

## Group 0 — Fix `sync_status.py` (B-brief, prerequisite)

**Type:** B-brief
**Effort:** S (~2 hours)
**Risk:** Low (script-only; no doc content change)
**Findings closed:** F-01, F-37, F-38, F-39, F-40

**Why it's Group 0:** the script is the auto-sync mechanism for counters; if it has a broken regex (RC-1) and an incomplete `validate()` (RC-2), every counter fix in Group 3 either silently regresses on the next run or persists undetected.

**Tasks (in order):**

1. **Fix the broken `update_claude()` regex (F-01).** File: `scripts/sync_status.py:200-204`.
   - Current pattern: `r"\d+ endpoints total \(\d+ router \+ 1 app-level health check\)"`
   - Replace with: `r"\d+ endpoints total \(\d+ router \+ 2 app-level: health check \+ stripe webhook\)"`
   - Update replacement string from `f"{endpoints} endpoints total ({endpoints - 1} router + 1 app-level health check)"` to `f"{endpoints} endpoints total ({endpoints - 2} router + 2 app-level: health check + stripe webhook)"` (note: `endpoints - 2` because there are now 2 app-level routes).
   - Verify by grepping CLAUDE.md before/after: the line must transition from "64 endpoints total (62 router + 2 app-level…)" to "68 endpoints total (66 router + 2 app-level…)" after running `python scripts/sync_status.py`.

2. **Audit ALL regexes in the script (F-39, F-40).** Walk every `re.sub` and `re.search` in `update_claude()`, `update_marker_file()`, `parse_old_counts()`, `validate()`. For each, verify the pattern matches current CLAUDE.md / PROJECT_BRIEF.md / README.md text. Specifically:
   - `r"# FastAPI REST API \(\d+ routers\)"` (line 207) — verify against CLAUDE.md:113
   - `r"\*\*Pages \(\d+\):\*\*"` (line 215) — verify against CLAUDE.md:222
   - `r"^\| (GET\|POST\|PUT\|DELETE\|PATCH) "` (line 268) — verify endpoint table walking still finds all 68 rows
   - `r"(\d+) endpoints? total"` (line 270) — verify

3. **Strengthen `validate()` (F-37, F-38).** Add two checks:
   - **Reverse direction template check:** for every `- \`<name>\`` entry in vocabulary §3 module template list, verify a `<name>.json` file exists on disk. Warn on entries with no file (this is the F-13 root cause).
   - **Code-vs-CLAUDE.md drift check:** compare `count_api_endpoints()` against the number declared in CLAUDE.md "N endpoints total" header. If they differ, warn explicitly. Currently the validate only checks header-vs-table-rows — a closed-loop check inside CLAUDE.md that does not catch drift against the real code.

4. **Decide and document the auto-sync limit (F-40).** `sync_status.py` does not (and probably should not) auto-edit:
   - Tech-stack tables (PROJECT_BRIEF.md:71-78)
   - Pricing rows (ROADMAP_CURRENT.md:388)
   - GTM Sprint status callouts (ROADMAP_CURRENT.md:85-89)
   - The CLAUDE.md endpoint table (only the inline header gets updated)
   Add a brief docstring section `## Sync limits (won't auto-update)` to the top of `sync_status.py` explicitly listing these. Add a short note in `CLAUDE.md` §"Docs maintenance" pointing to the limit.

5. **Add a sentinel test.** Create `backend/tests/test_sync_status_sentinel.py` (or co-locate in an existing tests file) that imports `sync_status` and runs each regex against a snapshot fixture of CLAUDE.md / PROJECT_BRIEF / README. If any regex fails to match, the test fails — preventing future silent breakage like RC-1.

6. **Run `python scripts/sync_status.py` end-to-end** and verify:
   - Endpoint count in CLAUDE.md updates from 64 → 68 (proves F-01 fixed)
   - 8 vocabulary template orphan warnings emitted (proves F-37 added)
   - No spurious warnings from re-validating freshly-synced docs

**Acceptance criteria:**
- Sentinel test passes; failing the regex causes test failure
- After running sync, CLAUDE.md inline endpoint count matches code reality
- Warnings list includes any vocabulary→disk reverse mismatches
- Brief docstring documents the auto-sync limits

**Brief number to assign:** Use `python scripts/next_brief.py` at execution time (next free B). Suggested ID: **B-SYNC-FIX**.

---

## Group 1 — P0 Stripe / Pricing drift (DEDICATED, exact suggested-text)

**Type:** C-brief
**Effort:** XS (~30 minutes)
**Risk:** None
**Findings closed:** F-02, F-03, F-04, F-29, F-30
**Why dedicated:** these are P0 active-lies in primary planning + status docs. The exact replacement text must come from the audit, not from the implementer (no new pricing facts get invented at execution time).

### F-02 — `PROJECT_BRIEF.md:76`

**Replace:**
```
| Payments | Stripe (code complete, sk_test verified — temporarily disabled for open beta) |
```
**With:**
```
| Payments | Stripe LIVE (sk_live keys on Railway + Vercel, since 2026-04-16). Two-tier: $9.99/mo Standard (15-day trial) + $4.99/mo Founding Climber (first 20 users). B202 fail-closed guard, B226 webhook hardening. |
```

### F-03 (line 85) — `docs/ROADMAP_CURRENT.md:85`

**Replace the full callout block** (single line in the doc):
```
> Stripe status: A159 implemented in TEST MODE. Not live. Currently disabled for beta period.
```
**With:**
```
> Stripe status: LIVE since 2026-04-16. sk_live keys configured on Railway + Vercel. B202 fail-closed guard + B226 webhook hardening deployed. Two-tier pricing: $9.99/mo Standard (15-day trial) + $4.99/mo Founding Climber (first 20 users).
```

### F-03 (line 89) — `docs/ROADMAP_CURRENT.md:89`

**Replace:**
```
- **Week 0 (now):** Beta testers using the app (4-5 users). Stripe disabled. Founder dry-run.
```
**With:**
```
- **Week 0 (archived, ~2026-04-01):** Beta testers using the app (4-5 users). Stripe disabled at that time. Stripe went live 2026-04-16.
```

### F-04 — `docs/ROADMAP_CURRENT.md:388`

**Replace:**
```
- ~~Pricing model definition~~ ✅ Decided: EUR 14.99/month, 14-day trial, Founding Climber EUR 9.99 lifetime for first 50 users
```
**With:**
```
- ~~Pricing model definition~~ ✅ Decided (final): USD $9.99/month Standard (15-day trial) + USD $4.99/month Founding Climber (first 20 users). Currency: USD. Live since 2026-04-16.
```

### F-29 — Delete 3 stub proposals

```bash
git rm docs/briefs/B202_proposal.md docs/briefs/B203_proposal.md docs/briefs/B204_proposal.md
```

### F-30 — Delete abandoned report dumps (gitignored, no `git rm` needed)

```bash
rm reports/users_report_2026-04-{05,06,07}.md
```

**Suggested brief ID:** **C-STATUS-DRIFT-P0**.

---

## Group 2 — Other status-marker drift (text fixes)

**Type:** C-brief
**Effort:** S (~30 minutes)
**Risk:** None
**Findings closed:** F-17, F-35

### F-17 — `docs/design_system_v1.md:254`

**Replace:**
```
- **Downstream briefs (planned):** A215 Paywall redesign, A216 Onboarding redesign, A217 Today redesign
```
**With:**
```
- **Downstream briefs (completed):** A215 Paywall redesign ✅ (2026-04-27), A216 Onboarding redesign ✅ (2026-04-27), A217 Today redesign ✅ (2026-04-27)
```

### F-35 — `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:457, 461`

- Line 457: change `Spec completa in §12b` row to add `(✅ implementato, /guided/[date]/[sessionId]; rest timer coloring parziale)`.
- Line 461: change `## 12b. Guided Session Mode (spec futura)` → `## 12b. Guided Session Mode (implemented — /guided/[date]/[sessionId])`.

**Suggested brief ID:** **C-STATUS-DRIFT-P1**.

---

## Group 3 — Counter / number reconciliations (post-Group-0)

**Type:** C-brief, **must run after Group 0**
**Effort:** S (~45 minutes)
**Risk:** Low
**Findings closed:** F-09, F-10, F-11, F-12, F-13, F-14, F-15, F-16, F-36, F-46, F-47

**Step 1 — Run sync after Group 0 lands**
```bash
python scripts/sync_status.py
```
After Group 0, this should fix F-09 (CLAUDE.md endpoint count 64 → 68) automatically and emit F-13 warnings (vocab orphan template entries).

**Step 2 — Fix endpoint table rows in CLAUDE.md (F-09 manual residual)**

The auto-sync only updates the inline header. The endpoint table at `CLAUDE.md` §"API endpoints" is missing 4 rows. Identify the 4 missing endpoints by comparing the table rows to `git diff` against `count_api_endpoints()` output. Add the 4 missing rows.

**Step 3 — Manual text edits**

| finding | file:line | current | replacement |
|---|---|---|---|
| F-10 | `CLAUDE.md:144` | "13 indoor + 3 outdoor intents" | "15 indoor + 4 outdoor intents" |
| F-11 (header) | `docs/ENGINE_ARCHITECTURE.md:496` | "13 indoor intents" | "15 indoor intents" |
| F-11 (list) | `docs/ENGINE_ARCHITECTURE.md` (intent list under §9) | enumerate 13 | enumerate 15 (add `projecting`, `endurance`, `hard`) |
| F-11 (header) | `docs/ENGINE_ARCHITECTURE.md:503` | "3 outdoor intents" | "4 outdoor intents" |
| F-11 (list) | `docs/ENGINE_ARCHITECTURE.md` (outdoor list under §9) | enumerate 3 | enumerate 4 (add `outdoor_volume`) |
| F-12 | `PROJECT_BRIEF.md:45`, `README.md:26` | "10-13 weeks" | "11–16 weeks (lead) / 8–16 weeks (boulder)" |
| F-13 | `docs/vocabulary_v1.md:665` | "Canonical module template_ids (27)" + 8 orphan list entries | "Canonical module template_ids (19)" — remove the 8 orphans (verify none are referenced by active session templates first via `grep -r "<orphan-name>" backend/catalog/sessions/`) |
| F-14 | `docs/ENGINE_ARCHITECTURE.md:706` | "34 sessions registered (as of D163)" | "31 sessions registered (in `_SESSION_META`; 35 session JSON files on disk)" |
| F-15 | `CLAUDE.md:62, 85` | "closed_loop_v1.py" (2 occurrences) | "adaptation/closed_loop.py" |
| F-16 | `CLAUDE.md:103` | `from backend.engine.planner_v1 import generate_week_plan` | `from backend.engine.planner_v2 import generate_phase_week` |
| F-36 (P2) | `docs/ENGINE_ARCHITECTURE.md:550` | "13 sort categories" | "14 sort categories (including `main_unclassified` fallback)" |
| F-46 (P3, optional) | `CLAUDE.md:143` | "3-pass algorithm" | "multi-pass algorithm (primary → complementary → tests)" |
| F-47 (P3, optional) | `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:4` | "Versione: 1.2 (file: v1.1)" | EITHER: rename file to `_v1.2.md`, OR change header to `Versione: 1.1`. Daniele decides — single-line. |

**Verification:** after edits, re-run `python scripts/sync_status.py` and confirm:
- Validation no longer warns about endpoint header / table mismatch
- Vocabulary template warnings (F-13) clear (8 orphans removed)
- Test suite still green

**Suggested brief ID:** **C-COUNTER-RECON**. (D229 should be marked superseded by this brief — its scope is folded in.)

---

## Group 4 — Doc archival (bulk move + dir merge)

**Type:** C-brief
**Effort:** M (~1.5 hours, mostly mechanical)
**Risk:** Low (only moves, no content edits — but EVERY moved file must be checked for live references, and any references must be updated)
**Findings closed:** F-08, F-18, F-19, F-20, F-21, F-22, F-23, F-24, F-25, F-26, F-27, F-28, F-31, F-32, F-33

This is the largest group by file count: ~30 files moving to `_archive/`. Output should be one explicit `git mv` command per file so the operation is auditable.

### Step 1 — Resolve `docs/audits/` (plural) vs `docs/audit/` (singular) — F-08

Decision (recommended): consolidate everything into `docs/audit/` (singular). Rationale: `docs/audit/` has 34 files vs 3 in `docs/audits/` — moving the 3 is cheaper than moving the 34, and CLAUDE.md (§Documentation architecture) doesn't currently specify a canonical name (this brief should add one).

```bash
# Move plural → singular for files staying live (rename only, not archive)
git mv docs/audits/D-MEM-002_railway_memory_2026-05-07.md docs/audit/D-MEM-002_railway_memory_2026-05-07.md
# (the other 2 files in docs/audits/ are obsolete and go straight to archive — see Step 4)
rmdir docs/audits/   # only after all 3 files moved out
```

Then **add to `CLAUDE.md` §"Documentation architecture"** a one-line rule:
```
- All audit deliverables live in `docs/audit/<brief-id>_<topic>.md` (singular, never `docs/audits/`).
```

### Step 2 — Rename misplaced docs to correct location (BEFORE archive — Group 5 covers active misplacements; this step covers the obsolete misplaced ones that go straight to archive)

```bash
# These 6 files are at docs/ root (or wrong dir); they're obsolete, so they go straight to _archive/ — but path-prefix them with their target dir for clarity inside _archive/
git mv docs/A214_phase0_audit.md             _archive/docs/audit/A214_phase0_audit.md
git mv docs/A215_phase0_audit.md             _archive/docs/audit/A215_phase0_audit.md
git mv docs/A216_phase0_audit.md             _archive/docs/audit/A216_phase0_audit.md
git mv docs/audit_decision_roadmap_xcheck.md _archive/docs/audit/audit_decision_roadmap_xcheck.md
git mv docs/audit_docs_D197.md               _archive/docs/audit/audit_docs_D197.md
git mv docs/audit_readonly_2026-04-25.md     _archive/docs/audit/audit_readonly_2026-04-25.md
git mv docs/B183_duration_review.md          _archive/docs/audit/B183_duration_review.md
```

### Step 3 — Archive closed `docs/audit/D*` reports (F-25)

11 closed audits, all >4 weeks old, all underlying briefs ✅:
```bash
git mv docs/audit/audit_route_intervals_offset_D93.md _archive/docs/audit/audit_route_intervals_offset_D93.md
git mv docs/audit/B227_phase0_findings.md             _archive/docs/audit/B227_phase0_findings.md
git mv docs/audit/D-ANALYTICS-DROPOFF_output.md       _archive/docs/audit/D-ANALYTICS-DROPOFF_output.md
git mv docs/audit/D-BASELINE-AUDIT_report.md          _archive/docs/audit/D-BASELINE-AUDIT_report.md
git mv docs/audit/D-TESTWEEK-AUDIT_report.md          _archive/docs/audit/D-TESTWEEK-AUDIT_report.md
git mv docs/audit/D175_performance_audit.md           _archive/docs/audit/D175_performance_audit.md
git mv docs/audit/D204_session_builder_audit.md       _archive/docs/audit/D204_session_builder_audit.md
git mv docs/audit/D205_subscription_audit_2026_04_16.md _archive/docs/audit/D205_subscription_audit_2026_04_16.md
git mv docs/audit/D210_b206_verification.md           _archive/docs/audit/D210_b206_verification.md
git mv docs/audit/D215/                                _archive/docs/audit/D215/
git mv docs/audit/D216/                                _archive/docs/audit/D216/
```

### Step 4 — Archive closed body-part-picker D217/D220/D223 cluster (F-26)

```bash
git mv docs/audit/D217_body_part_picker_audit.md            _archive/docs/audit/D217_body_part_picker_audit.md
git mv docs/audit/D220_body_part_picker_audit.md            _archive/docs/audit/D220_body_part_picker_audit.md
git mv docs/audit/D223_body_part_picker_classification_audit.md _archive/docs/audit/D223_body_part_picker_classification_audit.md
git mv docs/audit/D223_body_part_pool_listing.md            _archive/docs/audit/D223_body_part_pool_listing.md
git mv docs/audit/D223_c225_research_notes.md               _archive/docs/audit/D223_c225_research_notes.md
git mv docs/audit/D223_full_resolver_reclass_impact.md      _archive/docs/audit/D223_full_resolver_reclass_impact.md
```

### Step 5 — Archive closed brief-process docs in `docs/briefs/` (F-27)

```bash
git mv docs/briefs/A-ACTIVATION-timing_parked.md             _archive/docs/briefs/A-ACTIVATION-timing_parked.md
git mv docs/briefs/A-ACTIVATION-timing_phase0.md             _archive/docs/briefs/A-ACTIVATION-timing_phase0.md
git mv docs/briefs/A-ACTIVATION-timing_subscription_audit.md _archive/docs/briefs/A-ACTIVATION-timing_subscription_audit.md
git mv docs/briefs/B208_proposal.md                          _archive/docs/briefs/B208_proposal.md
git mv docs/briefs/B214_B215_phase0_analysis.md              _archive/docs/briefs/B214_B215_phase0_analysis.md
git mv docs/briefs/B216_phase1_analysis.md                   _archive/docs/briefs/B216_phase1_analysis.md
git mv docs/briefs/B217_session_duration_fix.md              _archive/docs/briefs/B217_session_duration_fix.md
git mv docs/briefs/D214_phase0_analysis.md                   _archive/docs/briefs/D214_phase0_analysis.md
git mv docs/briefs/D214_source_taxonomy_normalization.md     _archive/docs/briefs/D214_source_taxonomy_normalization.md
```

### Step 6 — Archive 2 closed audits in `docs/audits/` (plural) — F-28

```bash
git mv docs/audits/D232_new_macrocycle_2026-05-05.md          _archive/docs/audit/D232_new_macrocycle_2026-05-05.md
git mv docs/audits/D_guided_session_countdown_beep_2026-05-04.md _archive/docs/audit/D_guided_session_countdown_beep_2026-05-04.md
```

### Step 7 — Misc archive (F-31, F-32, F-33)

```bash
mv docs/council_reports/council_2026-04-19_11-47.md  _archive/docs/council/council_2026-04-19_11-47.md   # gitignored — plain mv
git mv docs/migrations/subscriptions_table.sql        _archive/docs/migrations/subscriptions_table.sql
git mv frontend/DEMO/README.md                        _archive/docs/frontend_DEMO_README.md
```

### Step 8 — Verify zero broken references after the moves

```bash
# After all moves, grep for any remaining live reference to a now-archived path
for f in $(git diff --name-only HEAD --diff-filter=R | awk '{print $1}'); do
  basename=$(basename "$f")
  echo "Checking refs to $basename..."
  grep -rn --exclude-dir=_archive --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv "$basename" .
done
```
Any hit means a live reference must be updated to the new `_archive/` path or rewritten.

**Suggested brief ID:** **C-DOC-ARCHIVE**.

---

## Group 5 — Active misplacements + escalations (rename-only, NO archive)

**Type:** C-brief
**Effort:** XS (~15 minutes for the renames; escalations are decisions, not edits)
**Risk:** None
**Findings closed:** F-34, F-41, F-42, F-43, F-44, F-45

### Renames (no escalation)

```bash
git mv docs/outdoor_audit_D170.md docs/audit/outdoor_audit_D170.md   # F-34
git mv AUTH_AUDIT.md              docs/audit/AUTH_AUDIT.md            # F-41
```

After F-41, also update any references to `AUTH_AUDIT.md` (root) to `docs/audit/AUTH_AUDIT.md`. Run a grep:
```bash
grep -rn --exclude-dir=_archive --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.venv 'AUTH_AUDIT.md' .
```

### Escalations (Daniele decides — do NOT auto-execute in C-brief)

| finding | file | question for Daniele |
|---|---|---|
| F-42 | `MEMORY_AUDIT.md` (root, untracked) | (a) Commit at root, (b) git mv to `docs/audit/MEMORY_AUDIT.md`, (c) archive (analysis stale), (d) leave untracked. |
| F-43 | `docs/audit/D235_project_description_rewrite.md` (untracked) | Is this a draft you want to keep working on, integrate, or discard? |
| F-44 | `docs/audits/D-MEM-002_railway_memory_2026-05-07.md` | Open a remediation B-brief from its 8 recommendations, or accept the findings and archive? |
| F-45 | `docs/briefs/A-ACTIVATION-timing_simulation.md` | Code comments in `start_date_utils.py` and `simulate_onboarding_start.py` cite this brief. Update comments to remove the citation, then archive — or keep brief live as historical reference? |

**Suggested brief ID:** **C-MISPLACED-RENAMES** (renames) + inline questions in `docs/ROADMAP_CURRENT.md` (escalations).

---

## Group 6 — Live → archive references and broken citations

**Type:** C-brief
**Effort:** S (~45 minutes — includes the F-07 git restore)
**Risk:** Low
**Findings closed:** F-05, F-06, F-07

### F-05 — `docs/ROADMAP_CURRENT.md:19`

**Replace:**
```
docs/audit/D163_frontend_audit.md
```
**With:**
```
_archive/docs/frontend_audit_D163.md
```
(or rewrite the surrounding sentence to not link the file at all if D163 is fully closed and no longer needs a citation)

### F-06 — `docs/ROADMAP_CURRENT.md:43`

The file `docs/audit/D172_findings_tracker.md` was never created. Two options:

**Option A (simple):** rewrite the citation to acknowledge the tracker doesn't exist:
```
Replace: > Full breakdown: docs/audit/D172_findings_tracker.md
With:    > Full breakdown: tracked inline in this roadmap (see P1.26 priority list below). The file `D172_findings_tracker.md` was planned but never created.
```

**Option B (recreate):** generate a minimal `docs/audit/D172_findings_tracker.md` that lists the 25 D172 findings with their current status. This requires walking the original D172 audit, which is also missing — so Option A is cheaper and equally honest.

**Recommended:** Option A.

### F-07 — Restore `horst_integration_audit.md` from git

Recovery command (single line, idempotent):
```bash
mkdir -p _archive/docs
git show 70dadfa:docs/horst_integration_audit.md > _archive/docs/horst_integration_audit.md
```

Then verify the 4 ROADMAP citations now point to a real file:
```bash
grep -n 'horst_integration_audit' docs/ROADMAP_CURRENT.md
# Expected hits at lines 244, 253, 254, 612
ls -la _archive/docs/horst_integration_audit.md
# Expected: file exists, 220 lines
wc -l _archive/docs/horst_integration_audit.md
```

If you'd rather restore to `docs/audit/` (live, not archive) — also acceptable, but then the 4 citations need to be rewritten to drop the `_archive/docs/` prefix. The simplest fix is to keep the citations exactly as they are and restore to the cited path.

**Suggested brief ID:** **C-CITATIONS-FIX**.

---

## Out-of-scope (escalations to track)

These don't fit any group — track in ROADMAP_CURRENT.md as separate decisions.

1. **Repo-hygiene cadence drift.** RC-7 says `repo_hygiene.py` was last fully run at D156 (2026-03-25, ~6 weeks ago). CLAUDE.md says "every ~2 weeks or ~10 briefs". The cadence is not enforced. Decision needed: either schedule it more aggressively, or fold archive-on-close into a per-brief checklist.

2. **D229 supersession.** D229 is open in ROADMAP_CURRENT.md tracking F-09/F-10/F-11/F-15. After Group 3 lands, D229 must be marked ✅ Done with a "superseded by D236" annotation.

3. **6 fully-orphaned `_archive/docs/council/*.md` files** (after F-22 archives D197). These have zero references anywhere. Eligible for plain deletion in a future cleanup C-brief; **explicitly out of D236 scope**.

4. **Sentinel CI gate.** Group 0 adds a sentinel test. If you want belt-and-braces, add a CI step that runs `python scripts/sync_status.py` and fails if it makes changes (i.e., the docs were dirty). This is a separate C-brief.

---

## Execution checklist (when Daniele picks groups)

Per group:

- [ ] Run `python scripts/next_brief.py` to assign a brief ID
- [ ] Open a `brief/<id>-<slug>` branch (per CLAUDE.md branch rules — Group 4 doc moves are not frontend, so direct push to main is allowed; Groups touching `frontend/` would need a preview)
- [ ] Apply the changes listed in the group
- [ ] Run `python -m pytest backend/tests -q` (Group 0 only — must stay green)
- [ ] Run `python scripts/sync_status.py` and confirm no unexpected diff
- [ ] Update `docs/ROADMAP_CURRENT.md` to mark closed findings ✅
- [ ] Commit with message `<id>: <description> (D236 Group <n>)`

---

## Final note

All findings, root causes, post-mortem, and recommendations are derived from the four Phase 1 reports under `docs/audit/D236/`. The execution of this plan is **out of D236 scope** — D236 ends at this file. The next step is Daniele's selection of which groups to schedule.
