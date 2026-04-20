# Brief B217 — Fix: session_duration_seconds write + remove frontend fallback slot-table + hygiene

**Type:** B (bugfix) — bundle 4-in-1
**Priority:** P1 — user trust issue caught in QA today (fake "~90 min" after Completed)
**Depends on:** D216 findings (`docs/audit/D216/findings.md`)
**Touches:** backend (feedback router) + frontend (session-card, feedback-dialog) → **branch + Vercel preview mandatory per CLAUDE.md** (not backend-only)
**High-risk modules:** none (feedback.py is a router, not an engine module). Standard STOP gate still applies for Phase 1 analysis.
**Model suggestion:** Sonnet is sufficient.

> Number is placeholder. Run `python scripts/next_brief.py` before filing — may be different from 217.

-----

## Scope — 4 changes bundled

**D216 root cause summary** (see full report for detail):

- `POST /api/feedback` writes `session_duration_seconds` to `session_completion_log[-1]` and `feedback_log[*]` but NOT to the session slot in `current_week_plan`.
- `_attach_feedback` (`week.py:170-171`) backfills it from `feedback_log` on subsequent `GET /api/week/*` calls, so the value eventually appears — but the POST response itself returns the session without the field.
- Frontend guided page does `qc.setQueryData(['week', 0], response.week_plan)` with that incomplete response → `session.session_duration_seconds === undefined`.
- `session-card.tsx:864-877` renders the Completed badge with a **hardcoded fallback slot-table** `{lunch:35, morning:60, evening:90}` when the field is nullish, prefixed by `~`. This produces the exact fake values observed on 2026-04-20 (Technique Focus evening → "~90 min", Upper Body lunch → "~35 min").

### Change 1 — PRIMARY: backend writes `session_duration_seconds` on session slot

**File:** `backend/api/routers/feedback.py:210-233` (the POST /api/feedback loop that iterates sessions in `current_week_plan`).

Inside that loop, when the matching session is found and feedback is applied, also write `session_duration_seconds` onto the session dict. Reuse the B197-style `max(prev, duration)` pattern if there's already a value — never regress a measured duration to null/zero.

Effort: XS.

### Change 2 — DEFENSE: remove frontend fallback slot-table from Completed badge

**Files:**

- `frontend/src/components/training/session-card.tsx:864-877` (badge render)
- `frontend/src/components/training/session-card.tsx:1150` (drawer, same fallback pattern per D216)

Render the badge as:

- `Completed · XX min` when `session.session_duration_seconds` is a positive number → format as `Math.round(session_duration_seconds / 60)` min, no `~` prefix (this is a measured value, not an estimate).
- `Completed ·` (no minutes, no fallback text) when `session_duration_seconds` is nullish or zero — **design decision A confirmed by user**.

Do NOT render the estimated duration from the slot-table on the Completed badge under any condition. The slot-table `{lunch:35, morning:60, evening:90}` remains valid for the **Planned** badge (where `~40 min` next to "Work / lunch" is legitimately an estimate — see Image 7 from today's trace).

Effort: XS.

### Change 3 — HYGIENE: single-source slot-table

**Files currently carrying divergent copies:**

- `frontend/src/components/training/session-card.tsx`
- `frontend/src/components/training/feedback-dialog.tsx`
- `backend/engine/report_engine.py`

`feedback-dialog.tsx` reportedly adds `afternoon:60`, which already diverges. Consolidate to one canonical source. Options (pick the simpler one, justify briefly in Phase 1):

- **Option A — frontend shared constant**: move to `frontend/src/lib/slot-durations.ts` exporting the lookup. Both components import from there. `report_engine.py` stays separate (different language, different concern).
- **Option B — backend-served**: add the slot-table to an existing catalog/defaults endpoint, frontend reads it once. Future-proof but adds a fetch.

Recommend A unless Phase 1 finds a reason to prefer B. Keep backend copy in `report_engine.py` **independent** — different concern (weekly report analytics), do not chase cross-stack unification in this brief.

Effort: S.

### Change 4 — HYGIENE: `duration_source` tombstone

**Files:**

- `frontend/src/components/training/feedback-dialog.tsx` (sender — remove from POST payload)
- `backend/api/routers/feedback.py` (receiver — remove from payload schema)
- `backend/engine/report_engine.py:817` (reader — currently `.get("duration_source", "timer")` with default "timer", dead branch per D216)

D216 confirmed: `duration_source` is a **Potemkin field**. Frontend sends it, backend accepts it, **nobody writes it anywhere on server-side state**. The reader in `report_engine.py` has a hard-coded default so the field never surfaces in reports either.

Remove from all three locations. No schema migration needed (it's not persisted).

Effort: S.

-----

## Hard constraints

1. **Branch mandatory + Vercel preview + explicit OK before merge to main** — this touches `frontend/`, per CLAUDE.md. Branch name: `brief/B217-session-duration-fix`.
1. **Do NOT regress measured durations.** In Change 1, never overwrite a positive `session_duration_seconds` with null/zero. Use `max(prev, duration)` or equivalent guard. Test this.
1. **Do NOT change the Planned badge behavior.** The slot-table estimate is legitimate for `~40 min` on Planned sessions. Only the Completed badge loses the fallback.
1. **Do NOT touch `_attach_feedback` in `week.py`.** It was the self-healing mechanism that B192 introduced a gate on (status == "done" only). It's fine as-is. The primary fix in Change 1 closes the gap upstream; `_attach_feedback` remains as a safety net for clients that never received the POST response.
1. **Immutability invariant.** Change 1 writes to today's session slot only (the one being completed). Past sessions are not touched.

-----

## Phase 1 — Analysis (STOP gate)

1. Confirm the exact code location for each of the 4 changes (line numbers may have shifted from D216).
1. Change 1: identify whether there's a single write point or the loop writes in multiple places. Decide where to inject the new write — should be the same site where `status="done"` is set, to keep the two fields written atomically.
1. Change 2: inventory all conditional render branches in `session-card.tsx` that use the slot-table. Confirm which are Completed-only vs Planned-only vs both. Report any surprise.
1. Change 3: pick Option A or B with justification. Confirm `feedback-dialog.tsx` divergence (`afternoon:60` observation from D216). If it's worse than described (e.g., 3 different tables with different keys), call it out.
1. Change 4: confirm `duration_source` has zero writer in the backend (grep `"duration_source"` across `backend/` and confirm all hits are readers or schema declarations). If any writer is found, STOP and report — that changes the tombstone decision.
1. Regression test plan — 3 tests minimum (see Phase 2 below).

Present analysis. Wait for explicit OK before Phase 2.

-----

## Phase 2 — Implementation (only after OK)

1. **Change 1** (backend): write `session_duration_seconds` on the session slot inside `feedback.py:210-233`.
1. **Change 2** (frontend): remove the slot-table fallback branch in the Completed badge render path (both `:864-877` and `:1150`).
1. **Change 3** (frontend): extract shared constant per Option A.
1. **Change 4**: remove `duration_source` from all three sites.
1. **Regression tests** (backend only — frontend will be tested manually via Vercel preview):
   - T1 — `POST /api/feedback` with `elapsed_seconds=1800` on a planned session → response `week_plan.sessions[*].session_duration_seconds == 1800` for the targeted session.
   - T2 — `POST /api/feedback` with `elapsed_seconds=null` → response preserves existing `session_duration_seconds` if any (no regression from valid to null).
   - T3 — payload without `duration_source` is accepted (backward compatibility for mid-deploy race where old client still sends it AFTER the frontend deploy; old payload with `duration_source` is accepted and silently ignored).

   Naming: `backend/tests/test_feedback_duration_B217.py`.
1. Manual QA on Vercel preview (before merge):
   - Complete a session via guided → badge shows real duration like `Completed · 23 min` (no `~`).
   - Mark done without guided → badge shows `Completed ·` (no minutes).
   - Planned session card still shows `~40 min` estimated in the metadata chip.
   - Pull-to-refresh on a completed session with null duration → stays `Completed ·`, does NOT suddenly fill in from fallback.
1. `python scripts/sync_status.py`.
1. Push branch, confirm Vercel preview URL, post it + screenshot of manual QA in chat. **Wait for Daniele's OK before merging to main.**

Commit message (final merge):

```
B217: write session_duration on slot + remove frontend fallback

- feedback.py: write session_duration_seconds on session slot
  (was only in session_completion_log + feedback_log)
- session-card.tsx: remove hardcoded slot-table fallback from
  Completed badge (was showing fake "~90 min" when guided timer
  had not persisted)
- lib/slot-durations.ts: single-source slot-table (deduped from
  session-card.tsx + feedback-dialog.tsx)
- Removed `duration_source` Potemkin field (sent by FE, accepted
  by BE, never written server-side, dead-default in reader)
- Tests: test_feedback_duration_B217.py (T1..T3)
- Closes D216 root cause
```

-----

## Phase 3 — Post-deploy verification

1. Wait for Vercel production build to propagate (~2 min).
1. Hard refresh PWA on iPhone (close task switcher, reopen).
1. Complete a test session on a clean account (or disposable user). Verify badge text matches expectation.
1. Do NOT test on Daniele's account for Technique Focus today — it's already in mixed state (completed + undo cycle). The fix is forward-looking.
1. Mark B217 ✅ Done in `docs/ROADMAP_CURRENT.md` in a follow-up sync commit (or inside the merge commit).
1. Add lesson to `docs/lessons.md`:

   ```
   [2026-04-20] [B217]: frontend fallback slot-tables for "measured"
   values hide backend write gaps. Rule: if the field is meant to be
   measured (duration, actual load, actual grade), render null/empty
   when absent — never silently substitute an estimate under the same
   label. Estimates and measurements must be visually distinguishable.
   ```

-----

## Rollback

```bash
git revert <B217-merge-commit-sha>
git push
```

Restores fallback slot-table and Potemkin `duration_source`. Users would again see fake `~90 min` on Completed badges, but no data loss — the real duration is already in `session_completion_log` regardless.

-----

## Out of scope (do NOT do in this brief)

- **B192** is a separate brief for undo-session ghost state. Do not bundle. B192 fixes `mark_planned` + `_attach_feedback` gate; B217 fixes the write-path upstream. Both needed, different code paths.
- **Cross-stack slot-table unification** (making frontend and `report_engine.py` share one source). Leave backend copy independent. Frontend-only dedupe in Change 3.
- **Weekly report analytics recompute** for past sessions that were completed with the old (zero/null) session_duration. Historical data is historical; do not backfill.
- **Refactoring `feedback.py`** beyond the single write addition. D164 flagged this file as bloated — separate R-brief territory.
