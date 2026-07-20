# A245 — REVIEW-REMEDIATION-V1: consolidated frontend + backend hygiene

**Type:** A (multi-fix, phased) · **Priority:** P1 → P3 across phases
**Source:** [[D254]] — `docs/audit/D254_full_repo_review.md` (external repo review, 2026-07-20)
**Official ID:** A245 (assigned via `scripts/next_brief.py`, 2026-07-20)
**Prerequisites:** ✅ [[B285]] (SEC-AUTH) and ✅ [[B287]] (REPLANNER-IMMUTABILITY) both merged to `main` (`5fc83a0`).

## Amendments to the original brief (approved by Daniele, 2026-07-20)

The brief as drafted covered 63 of D254's 81 findings. Coverage was verified by
extracting every `F<n>`/`B<n>` id from the audit and diffing against the phases.
Amendments:

1. **Official ID is A245.** The draft had no number; `next_brief.py` was run as
   the brief's own Phase 0 requires.
2. **+F28 → Phase C.** `start-week` shows a white screen if `getState` fails
   offline right after submit. GTM-critical and exactly the failure class
   phases B/C exist to remove, so it does not belong in a later phase.
3. **+F13, F14, F15, F27 → Phase F.** Perf findings (1.7 MB exercise images via
   native `<img>`, CLS on `/today`, manual N+1 fetch outside React Query, Clerk
   in the root layout costing ~227 KB on every route including public ones).
   Phase F is already "dedup + light perf".
4. **F55–F58 are OUT of scope for v1.** Component-decomposition refactor
   (`QuickAddDialog` 776 lines, feedback serialization inline in the guided
   page, 3-level prop drilling, `GuidedExerciseStep` 1053 lines). Registered in
   the roadmap as **B-REFACTOR-COMPONENTS** so they stay tracked. Rationale:
   Phase G is already the heaviest phase; inflating it risks the whole brief.
5. **Branch + preview rule made explicit.** Phases A, B, C, D, F, G touch
   `frontend/` → branch `brief/A245-<phase>` and a Vercel preview approved by
   Daniele before each merge to `main`. Phase E is backend-only → direct push.
   This is `CLAUDE.md` policy and the draft did not restate it.
6. **B5 (server-timezone "today") stays explicitly out of scope** — needs its
   own A-brief plus a D-audit before US users, as the draft flagged.

## Standing rules

- **One phase per session, in order A → G.** Each phase ends with: frontend
  build green (`npm run build`) / full pytest suite green, one commit per task
  (`A245 <phase>-<task>: desc`), and a checkpoint report. **Wait for explicit OK
  between phases.**
- **Re-verify every `file:line` before editing.** The audit was accurate on
  2026-07-20 and drifts with every commit.
- **Never touch** past/completed session semantics or the STOP-gate engine
  modules (`planner_v2`, `replanner_v1`, `macrocycle_v1`, `resolve_session`,
  `progression_v1`, `closed_loop_v1`) — except E-6, which is a mechanical move
  in an isolated commit with the suite run before and after.
- **If two "duplicate" copies turn out NOT to be identical** during any dedup
  task: STOP on that item, report the diff, continue with the rest of the phase.
- Decision gates that must not be passed silently: **E-4** (dead-code
  `adaptation/closed_loop.py`: wire it in vs remove it) and **F-4** (guided
  storage keys must be proven identical before unification — otherwise there
  are data-migration implications).

## Phases

| Phase | Scope | Findings | Frontend? |
|---|---|---|---|
| **A** | Quick wins: touch targets ≥44px, destructive-tap safety, fetch timeout, double-tap guards | F3, F6, F7, F11, F12, F31, F32, F33, F39, F40, F41, F42, F61, F62 | yes |
| **B** | PWA offline v1: app shell precache + generalized outbox | F1, F2, F4, F5, F21, F44 | yes |
| **C** | Network-state correctness (never map a network error onto a business state) | F8, F9, F10, F37, F51, **F28** | yes |
| **D** | Onboarding funnel (ship before pushing Reddit/IG traffic) | F16, F17, F18, F29, F30, F38, F45–F49 | yes |
| **E** | Backend hygiene batch | B4, B8, B10, B12, B14, B15, B16, B17, B19 | no |
| **F** | Dedup + light perf | F25, F26, F43, F53, F54, F59, F60, **F13, F14, F15, F27** | yes |
| **G** | Data-layer correctness + the two big refactors | F19, F20, F22, F23, F24, F34, F35, F36, F50, F52 | yes |

The per-task detail (file:line, symptom, prescribed fix) lives in the source
audit `docs/audit/D254_full_repo_review.md` under each finding id.

## Acceptance per phase

- **A** — every interactive control in gym/crag flows ≥44px hit area; no
  destructive action without confirm or undo; no request can hang forever.
- **B** — cold start with no network reaches `/today` with the last known plan;
  nothing logged offline is ever lost silently.
- **C** — a paying user offline NEVER sees `/subscribe` or the welcome screen.
  Manual matrix: {online, offline, flaky} × {active sub, expired trial,
  expired token}.
- **D** — closing the tab mid-onboarding does not lose the draft; no grey
  disabled button without an explanation of what is missing; a plan with zero
  climbing is impossible.
- **E** — pytest suite green; rate limits are per-user, not global.
- **F** — no behavioural change; build green; bundle measurably smaller.
- **G** — the duplicated today↔week handlers exist once; behaviour snapshotted
  by tests BEFORE extraction.

## Final deliverables (after G)

- `docs/lessons.md` updated (offline architecture; "every duplicated handler
  eventually diverges").
- Summary table: finding → commit → phase, plus the list of drifted `file:line`
  refs found along the way and every decision taken or still pending.
