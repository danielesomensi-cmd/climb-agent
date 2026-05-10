# D236 — Subagent A: Cross-doc consistency

Findings: P0=0, P1=5, P2=7, P3=4

Severity legend: P0 = blocking/wrong fact, P1 = clear contradiction, P2 = stale but recoverable, P3 = cosmetic.

---

## Drift Matrix

| fact | PROJECT_BRIEF | README | CLAUDE | ROADMAP_CURRENT | DESIGN | other (cite) | drift_y_n | source_of_truth |
|------|--------------|--------|--------|-----------------|--------|--------------|-----------|-----------------|
| **Tests (passing)** | 1984 (line 21) | 1984 (line 12) | — | — | — | — | N | PROJECT_BRIEF (auto-synced) |
| **Exercises** | 218 (line 22) | 218 (line 13) | — | — | — | — | N | PROJECT_BRIEF (auto-synced) |
| **Sessions (active)** | 35 (line 23) | 35 (line 14) | — | — | — | vocab:622 "35" | N | Disk count = 35 ✓ |
| **Templates** | 19 (line 24) | 19 (line 15) | — | — | — | vocab:665 "27 module template_ids" | Y | Disk = 19; vocab lists 27 (8 orphan entries) — see F-A-07 |
| **API endpoints (total)** | 68 (line 25) | 68 (line 16) | 64 (line 149) | — | — | real=68 (66 router+2 app) | Y | PROJECT_BRIEF (auto-synced) |
| **API endpoints (table row count)** | n/a | n/a | 64 (grep count) | — | — | — | n/a | CLAUDE endpoint table self-consistent at 64 but stale |
| **Frontend pages** | 42 (line 26) | 42 (line 17) | 42 (line 222) | — | — | — | N | PROJECT_BRIEF (auto-synced) |
| **Frontend components** | 76 (line 27) | 76 (line 18) | — | — | — | — | N | PROJECT_BRIEF (auto-synced) |
| **Routers count** | — | — | 19 (line 113) | — | — | real=19 files | N | Code (19 .py router files) |
| **Indoor intents** | — | — | "13" (line 144) | D229 note: real=15 (line 109) | — | ENGINE_ARCH:496 "13" | Y | replanner_v1.py INTENT_TO_SESSION = 15 keys |
| **Outdoor intents** | — | — | "3" (line 144) | D229 note: real=4 (line 109) | — | ENGINE_ARCH:503 "3" | Y | replanner_v1.py OUTDOOR_INTENT_TO_DISCIPLINE = 4 keys |
| **Next.js version** | "Next.js 16" (line 70) | "Next.js 16" (line 35,48) | "Next.js 16" (line 119) | — | "Next.js 16" (line 449) | package.json: "16.1.6" | N | package.json |
| **Tailwind major version** | — | — | — | — | — | package.json: "^4" | n/a | No doc states Tailwind version explicitly |
| **FastAPI version** | — | "FastAPI" (line 34) | "FastAPI" (line 113) | — | — | requirements.txt: unpinned | n/a | No doc states version |
| **Clerk (live/planned)** | live (line 69) | live (line 36) | live (line 257) | live (line 137) | — | AUTH_AUDIT.md:4 confirms | N | All docs agree: live |
| **Supabase (live/planned)** | live JSONB (line 32) | live (line 37) | live (line 301) | live (line 137,139) | "Migrazione completata" (line 448) | — | N | All docs agree: live |
| **Stripe status** | LIVE (line 30,34) + stale "sk_test…disabled" (line 76) | — | LIVE since 2026-04-16 (line 255) | Contradicts self: "TEST MODE" (line 85) vs "LIVE since 2026-04-16" (line 137) | — | — | Y | CLAUDE.md §Deployment and ROADMAP line 137 are ground truth |
| **Persistent volume vs JSONB** | "Supabase JSONB live" (line 32) | "Supabase…production" (line 37) | JSONB primary, volume fallback (line 301) | JSONB ✅ (line 139) | JSONB (line 448) | — | N | All agree |
| **Assessment axes (count)** | "5 dimensions" (line 43) | "5 dimensions" (line 24) | "5-axis" (line 141,163) | — | "5 dimensioni" (line 37; explicitly notes body_composition removed D01) | vocabulary:998-1006 lists 5; ENGINE_ARCH:89-91 outputs 5 | N | All agree: 5 axes |
| **Macrocycle phase count** | "5 phases" (line 45) | "5 phases" (line 26) | "5 phases" (line 142) | — | "5 fasi" (table §4.1) | vocabulary §5.5 lists 5 phase_ids; ENGINE_ARCH:119 "5 phase dicts" | N | All agree: 5 phases |
| **Macrocycle phase names** | base→str_power→PE→perf→deload (line 45) | same (line 26) | same (line 142) | — | "Endurance Base / Strength & Power / Power Endurance / Performance / Deload" (table §4.1) | vocabulary §5.5 identical | N | All agree |
| **Macrocycle duration range** | "10-13 weeks" (line 45) | "10-13 weeks" (line 26) | "8–16 week" (line 142) | — | "11–16 lead / 8–16 boulder" (line 137) | vocabulary §5.5.1: lead=[11,16] boulder=[8,16]; macrocycle_v1.py: MIN_LEAD=11 MIN_BOULDER=8 MAX=16 | Y | Code + vocabulary are ground truth (post-A218); PROJECT_BRIEF and README show pre-A218 "10-13" |
| **Planner version in engine** | planner_v2 (line 57) | planner_v2 (line 27) | planner_v2 (line 136) | — | — | planner_v2.py exists + planner_v1.py also exists | N (with note) | planner_v2 is active; CLAUDE.md line 103 has stale import example — see F-A-09 |
| **closed_loop module name** | — | — | "closed_loop_v1.py" (lines 85,85) | "closed_loop_v1.py filename stale" (line 31) | — | actual file: adaptation/closed_loop.py | Y | Code: `backend/engine/adaptation/closed_loop.py` |
| **_SESSION_META count (planner registry)** | — | — | — | — | — | ENGINE_ARCH:706 "34 sessions (as of D163)" vs actual count in code = 31 | Y | Code (31 entries as of now; 35 sessions on disk, 4 not in META — the test sessions moved after D163) |
| **ENGINE_ARCH planner pass count** | — | — | "3-pass algorithm" (line 143) | — | — | ENGINE_ARCH §4: 6 named passes (1, 1.5, 2, 2.2, 2.5, 3) | Y | ENGINE_ARCH is implementation ground truth; CLAUDE.md "3-pass" is a simplification |
| **Open priority / current phase** | "Paid launch prep" (line 30) | — | — | "Priority 1.25/1.26/1.27/1.75" audit remediations ongoing | — | — | N (consistent: all signal post-launch maintenance) | PROJECT_BRIEF is the canonical "current phase" statement |
| **sync_status.py auto-updates** | ✓ table+header | ✓ table | endpoint+router+page counts | — | — | — | Y (see Notes) | sync_status.py regex broken for CLAUDE.md endpoint line — see F-A-01 |

---

## Findings List

### F-A-01 — CLAUDE.md endpoint count stale AND sync_status.py regex broken  [P1]
**Files:** `CLAUDE.md:149`, `scripts/sync_status.py:200-202`
**Drift:** CLAUDE.md declares "64 endpoints total (62 router + 2 app-level: health check + stripe webhook)" — actual count from code is 68 (66 router + 2 app-level). PROJECT_BRIEF and README correctly show 68 (auto-synced). The sync_status.py `update_claude()` function has a regex that matches `"\d+ endpoints total (\d+ router + 1 app-level health check)"` — this pattern does NOT match the CLAUDE.md text which says "2 app-level: health check + stripe webhook". As a result, sync_status.py silently skips updating the endpoint count in CLAUDE.md every run.
**Source of truth:** PROJECT_BRIEF (68, auto-synced via actual code count)
**Recommended action:** (1) Fix sync_status.py regex to match the "2 app-level" variant. (2) Update CLAUDE.md:149 from 64→68 and adjust the breakdown: "66 router + 2 app-level". Also update the endpoint table to add the 4 missing rows. D229 already flags this but notes it as "30 min, single commit."

---

### F-A-02 — CLAUDE.md and ENGINE_ARCHITECTURE indoor/outdoor intent counts stale  [P1]
**Files:** `CLAUDE.md:144`, `docs/ENGINE_ARCHITECTURE.md:496,503`, `docs/ROADMAP_CURRENT.md:109`
**Drift:** CLAUDE.md:144 states "13 indoor + 3 outdoor intents". ENGINE_ARCHITECTURE.md:496,503 also states "13 indoor intents" and "3 outdoor intents". Actual code in `backend/engine/replanner_v1.py` has `INTENT_TO_SESSION` with 15 keys (indoor) and `OUTDOOR_INTENT_TO_DISCIPLINE` with 4 keys (outdoor). ROADMAP_CURRENT D229 item acknowledges this (line 109: "real = 15+4") but the fixes are pending.
**Source of truth:** `replanner_v1.py` — 15 indoor intents: rest, recovery, technique, strength, power, power_endurance, aerobic_endurance, core, prehab, flexibility, finger_maintenance, finger_max, projecting, endurance, hard. 4 outdoor: outdoor_easy, outdoor_projecting, outdoor_volume, outdoor_boulder.
**Recommended action:** Update CLAUDE.md:144 to "15 indoor + 4 outdoor intents". Update ENGINE_ARCHITECTURE.md §9 header lines 496 and 503. Part of D229 (Open P2, "30 min").

---

### F-A-03 — ROADMAP_CURRENT internal Stripe contradiction  [P1]
**Files:** `docs/ROADMAP_CURRENT.md:85`, `docs/ROADMAP_CURRENT.md:137`
**Drift:** Line 85 (inside the §1.75 GTM Sprint callout block) reads: "Stripe status: A159 implemented in TEST MODE. Not live. Currently disabled for beta period." Line 137 reads: "Clerk auth ✅, Supabase JSONB ✅, and Stripe ✅ are complete. Stripe LIVE since 2026-04-16." These two statements directly contradict each other within the same document.
**Source of truth:** Line 137 and CLAUDE.md §Deployment: Stripe LIVE since 2026-04-16 with sk_live keys. The line 85 block is a historical state snapshot from the GTM Sprint planning section that was never updated when Stripe went live.
**Recommended action:** Update ROADMAP_CURRENT line 85 (and surrounding Timeline section at lines 89–91) to reflect that Stripe is live. Flag as part of D229. The "Week 0/1-2/2-3" timeline is entirely stale.

---

### F-A-04 — PROJECT_BRIEF "Payments" row contradicts its own "Current phase" section  [P1]
**Files:** `PROJECT_BRIEF.md:76`, `PROJECT_BRIEF.md:30,34`
**Drift:** The tech stack table row (line 76) reads: "Stripe (code complete, sk_test verified — temporarily disabled for open beta)". The "Current phase" section (lines 30, 34) correctly states "Stripe LIVE (sk_live keys on Railway + Vercel)" and "Stripe LIVE." The table row is a leftover from before go-live.
**Source of truth:** Lines 30/34 of PROJECT_BRIEF itself, and CLAUDE.md §Deployment.
**Recommended action:** Update PROJECT_BRIEF.md line 76 tech stack row to: "Stripe — LIVE since 2026-04-16 (sk_live keys). $9.99/mo Standard + $4.99/mo Founding Climber." Note: sync_status.py does not touch this tech stack table, so it will not auto-fix.

---

### F-A-05 — Macrocycle duration range stale in PROJECT_BRIEF and README  [P1]
**Files:** `PROJECT_BRIEF.md:45`, `README.md:26`, `CLAUDE.md:142`, `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:137`, `docs/vocabulary_v1.md:905`
**Drift:** PROJECT_BRIEF and README state "10-13 weeks". CLAUDE.md says "8–16 week". DESIGN doc says "11–16 settimane (lead) / 8–16 settimane (boulder)". vocabulary §5.5.1 says "lead=[11,16], boulder=[8,16]". Code in `macrocycle_v1.py`: `_MIN_TOTAL_WEEKS_LEAD=11`, `_MIN_TOTAL_WEEKS_BOULDER=8`, `_MAX_TOTAL_WEEKS=16`. The "10-13" figure predates the A218 cap rewrite (2026-05-07) which changed the floor for lead from 10→11 and expanded the max from 13→16.
**Source of truth:** Code + vocabulary + DESIGN doc (all post-A218): lead 11–16, boulder 8–16.
**Recommended action:** Update PROJECT_BRIEF.md:45 and README.md:26 from "10-13 weeks" to "11–16 weeks (lead) / 8–16 weeks (boulder), 5 phases". Note: sync_status.py does not touch this line.

---

### F-A-06 — ENGINE_ARCHITECTURE _SESSION_META count stale  [P2]
**Files:** `docs/ENGINE_ARCHITECTURE.md:706`
**Drift:** ENGINE_ARCHITECTURE states "34 sessions registered (as of D163)". Current code has 31 entries in `_SESSION_META` (planner_v2.py:38–73). On disk: 35 session files. The 4 sessions on disk not in _SESSION_META are the test hang/repeater sessions (test_max_hang_5s, test_max_hang_7s, test_lp_max_5s, test_repeater_7_3) — these appear to have been removed from _SESSION_META at some point after D163 (2026-03-27).
**Source of truth:** `planner_v2.py` (31 entries in _SESSION_META); disk has 35 .json files.
**Recommended action:** Update ENGINE_ARCHITECTURE.md:706 from "34 sessions registered" to "31 sessions registered (in _SESSION_META; 35 session JSON files on disk)". Investigate whether the 4 missing test sessions were intentionally removed from _SESSION_META or accidentally dropped.

---

### F-A-07 — vocabulary_v1.md module template count vs disk mismatch  [P2]
**Files:** `docs/vocabulary_v1.md:665`, disk: `backend/catalog/templates/v1/`
**Drift:** vocabulary §3 heading says "Canonical module template_ids (27)" and lists 27 entries. Only 19 template JSON files exist on disk. 8 templates are listed in vocabulary but have no corresponding file: `general_strength_accessories`, `gym_aerobic_endurance`, `gym_power_bouldering`, `gym_power_endurance`, `gym_technique_boulder`, `pulling_endurance`, `pulling_strength`, `warmup_recovery`.
**Source of truth:** Disk (19 files). These 8 are likely orphan entries — referenced in the vocabulary but never created as files (or deleted without updating the vocabulary).
**Recommended action:** Update vocabulary_v1.md §3 header from "(27)" to "(19)" and remove the 8 orphan entries. Confirm none are referenced by active session templates before removing. (sync_status.py's `validate()` function already warns about this in the opposite direction — files not in vocab — but doesn't warn about vocab entries with no file.)

---

### F-A-08 — ENGINE_ARCHITECTURE planner intent counts stale (same as F-A-02)  [P2]
**Files:** `docs/ENGINE_ARCHITECTURE.md:496,503`
**Drift:** ENGINE_ARCHITECTURE §9 Replanner states "13 indoor intents" (line 496) and "3 outdoor intents" (line 503). Actual code: 15 indoor, 4 outdoor. The intent lists below the headers also enumerate only 13 indoor (missing: projecting, endurance, hard) and 3 outdoor (missing: outdoor_volume).
**Source of truth:** `replanner_v1.py:84-106`
**Recommended action:** Update ENGINE_ARCHITECTURE.md §9 to list all 15 indoor intents and all 4 outdoor intents. (Same fix required as F-A-02 but in a different file.)

---

### F-A-09 — CLAUDE.md import example references `planner_v1` (stale)  [P2]
**Files:** `CLAUDE.md:103`
**Drift:** CLAUDE.md §"Import conventions" shows: `from backend.engine.planner_v1 import generate_week_plan`. The active planner is `planner_v2`. `planner_v1.py` does exist on disk (it is the legacy planner, not removed) but the illustrative import example should point to the current module.
**Source of truth:** CLAUDE.md itself: line 136 correctly states "generate_phase_week() [planner_v2, per week]". The import example at line 103 is cosmetically inconsistent.
**Recommended action:** Update CLAUDE.md:103 import example to `from backend.engine.planner_v2 import generate_phase_week` to avoid misleading new contributors.

---

### F-A-10 — CLAUDE.md references `closed_loop_v1.py` (wrong filename)  [P2]
**Files:** `CLAUDE.md:85`, `CLAUDE.md:62`
**Drift:** CLAUDE.md uses `closed_loop_v1.py` in two places (lines 62 and 85, in the "When you MUST stop" section and the model-switching suggestion). The actual file is `backend/engine/adaptation/closed_loop.py` — no `_v1` suffix, and inside the `adaptation/` subdirectory. ROADMAP_CURRENT line 31 already flags this: "closed_loop_v1.py filename stale".
**Source of truth:** `backend/engine/adaptation/closed_loop.py`
**Recommended action:** Update CLAUDE.md lines 62 and 85 from `closed_loop_v1.py` to `adaptation/closed_loop.py`. Also D229 covers this.

---

### F-A-11 — sync_status.py regex broken for CLAUDE.md endpoint update  [P2]
**Files:** `scripts/sync_status.py:200-202`, `CLAUDE.md:149`
**Drift:** `sync_status.py:update_claude()` has a regex pattern: `r"\d+ endpoints total \(\d+ router \+ 1 app-level health check\)"`. CLAUDE.md line 149 reads: `"64 endpoints total (62 router + 2 app-level: health check + stripe webhook)."` The pattern doesn't match (1 vs 2 app-level; different text format). As a result, every run of sync_status.py silently fails to update the CLAUDE.md endpoint count. The validation step (`validate()`) does catch the mismatch between table rows (64) and declared total (64) and reports no warning — so neither the sync nor the validation surfaces the true drift against the real code count (68).
**Source of truth:** `scripts/sync_status.py` is the canonical sync mechanism; its regex is the bug.
**Recommended action:** Fix `sync_status.py:200-202` regex to match the current CLAUDE.md format, then run sync to update all counts atomically.

---

### F-A-12 — ENGINE_ARCHITECTURE "3-pass" vs actual 6-pass algorithm  [P3]
**Files:** `CLAUDE.md:143`, `docs/ENGINE_ARCHITECTURE.md:221-258`
**Drift:** CLAUDE.md calls planner_v2 a "3-pass algorithm". ENGINE_ARCHITECTURE §4 documents 6 named passes: 1, 1.5, 2, 2.2, 2.5, 3. CLAUDE.md is a deliberate simplification (3 main logical phases: primary / complementary / tests), but technically misleading.
**Source of truth:** ENGINE_ARCHITECTURE §4 is the precise description.
**Recommended action:** CLAUDE.md could say "multi-pass algorithm (primary → complementary → tests)" to avoid the implied count.

---

### F-A-13 — DESIGN doc version header inconsistency  [P3]
**Files:** `docs/DESIGN_GOAL_MACROCICLO_v1.1.md:4`
**Drift:** The document header reads "Versione: 1.2 (file: v1.1)". The file is named `v1.1` but declares itself as version 1.2. Minor cosmetic inconsistency.
**Source of truth:** n/a — purely cosmetic.
**Recommended action:** Either rename the file to `v1.2` or update the version field to `1.1`.

---

### F-A-14 — ENGINE_ARCHITECTURE §9 "13 sort categories" header while §5.8 vocabulary lists 14  [P3]
**Files:** `docs/ENGINE_ARCHITECTURE.md:550`, `docs/vocabulary_v1.md:975-996`
**Drift:** ENGINE_ARCHITECTURE §10 heading says "13 sort categories" and lists 13 categories in the text block (line 554). However, vocabulary §5.8 lists 14 values including `main_unclassified` as a 14th fallback category. The actual `exercise_ordering.py` has `main_unclassified` as an explicit fallback.
**Source of truth:** `backend/engine/exercise_ordering.py` and vocabulary §5.8.
**Recommended action:** Update ENGINE_ARCHITECTURE §10 heading from "13 sort categories" to "14 sort categories (including main_unclassified fallback)". Low priority.

---

## Notes

- **sync_status.py is the root cause of counter drift in CLAUDE.md endpoint count.** The script successfully auto-syncs PROJECT_BRIEF.md and README.md (which use marker-based tables). It also updates CLAUDE.md for endpoint count, router count, and page count — but its endpoint-update regex (`1 app-level health check`) does not match the current CLAUDE.md text ("2 app-level: health check + stripe webhook"). The regex was correct when written but CLAUDE.md was updated to mention the stripe webhook without updating the regex. This is the root cause of F-A-01 and F-A-11.

- **D229 (Open P2 in ROADMAP) already identifies most of the CLAUDE.md drifts** (endpoints, intents, Stripe text in ROADMAP). The D229 note is partially stale itself: it says "CLAUDE.md:149 says 63 endpoints (real = 67)" — but CLAUDE.md currently says 64 (not 63) and the real count is now 68 (not 67), reflecting endpoint additions since D229 was written.

- **DESIGN doc does not lag the A218 macrocycle changes.** The DESIGN doc was updated on 2026-05-07 (same day as A218) and correctly reflects the new cap constraints, the 11–16 lead / 8–16 boulder range, and the 16-week hard cap with a note about block-stacking intent. This is correct ground truth.

- **The "6th axis" claim (D229 anchor question) does not appear in any live doc.** `body_composition` was explicitly removed as an axis in Phase 3.2 (D01) and all five current docs consistently say 5 axes. No live doc claims 6 axes. If there was such a claim it was in an obsolete version not visible in the current codebase.

- **MEMORY_AUDIT.md does not exist** at the repo root. It was listed as in-scope per the brief but is absent. AUTH_AUDIT.md exists (730 lines, 2026-05-04) and was reviewed — it contains no numerical counters that conflict with other docs, and correctly describes the Clerk/Supabase live stack.

- **vocabulary_v1.md module template list** (27 entries) is the most quantitatively wrong item outside of the endpoint count drift — 8 orphan entries exist in the vocabulary with no corresponding file on disk. sync_status.py's `validate()` only checks the reverse direction (files on disk not in vocab), so this drift direction is invisible to automation.

- **ENGINE_ARCHITECTURE.md `_SESSION_META` count (34)** reflects the state at D163 (2026-03-27). Since then, the count has dropped to 31 entries (several test sessions removed from _SESSION_META), which may be intentional but is undocumented.

- **The planner_v1.py file still exists on disk** alongside planner_v2.py. It is not imported by any active module (only test_planner_v1.py uses it), but its presence means the CLAUDE.md import example pointing to planner_v1 is not immediately obviously broken — the file exists, just the example is misleading.

- **Tailwind v4 is in use** (package.json: `"tailwindcss": "^4"`), but no doc explicitly states the major version. This is not a drift — it's simply not documented anywhere. Low concern.

- **The PROJECT_BRIEF "Completed phases" table** (lines 82–96) references "14 routers" under Phase 3: "3: UI (Next.js PWA) — Mobile-first dark PWA, 14 routers". This is a historical snapshot from when the router count was 14; it now stands at 19. This is a historical note, not a current-state claim, so not classified as a finding — but worth noting.
