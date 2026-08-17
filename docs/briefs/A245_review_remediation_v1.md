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

---

# Wrap-up (2026-07-20) — brief chiuso

Tutte e 7 le fasi mergiate in `main`. **67 finding schedulati → 63 chiusi**, 4 differiti
con misura (non per stanchezza) e tracciati in `ROADMAP_CURRENT.md`.

## Finding → commit → fase

| Fase | Finding chiusi | Commit |
|---|---|---|
| **A** — quick win UX | F33, F12, F42, F31, F41, F11(p), F61, F62 | `0ed3a42` |
| | F3 | `70c5874` |
| | F7 | `ca5822a` |
| | F6 | `a68b11c` |
| | F11 | `ea8a822` |
| | F32 | `9d66807` |
| | F39 | `41e35e4` |
| | F40 | `6a5f040` |
| **B** — PWA offline v1 | F2, F21, F22 | `711bc7a` |
| | F1 (persistenza) | `e73e5df` |
| | F1 (root offline) | `af2ccc1` |
| | F4, F5 | `6de35f9` |
| | F44 + Done/Skip offline | `e36044b` |
| **C** — stato-rete | F8, F9(client), F10, F28, F37, F51 | `d2b1f3a` (merge `b09f128`) |
| **D** — funnel onboarding | F17, F16, F45, F49 | `7c6f5d9` |
| | F18, F29, F30 | `466c616` |
| | F46, F47, F48 | `45a67f9` |
| | F38 | `75db940` |
| **E** — hygiene backend | B4 | `def61bf` |
| | B10, B15 | `24eda2b` |
| | B16, B17 | `0a134d4` |
| | B19 (E-6 isolato) | `4307f53` |
| | B8 (E-4, opzione c) | `d38376e` |
| **F** — dedup + perf | F53 | `eb2579e` |
| | F59, F60 | `1939d55` |
| | F13, F43 | `25d3253` |
| | F15, F14, F25 | `e7f4f47` |
| | F26 (metà) | `803235a` |
| **G** — data-layer | F50 | `2a15956` |
| | F34, F36 | `47e753b` |
| | F52, F19 | `f4e2d43` |
| | F23 | `ebb8c8e` |
| | F20 (parte a rischio) | `64b4690` |
| **fuori fase** | F54 | `2acf48d` (B290) |

## Bug trovati DURANTE la remediation, non presenti in D254

| ID | Cosa | Commit |
|---|---|---|
| **B290** | Regressione mia di Phase B: fix delle chiavi guided applicato a 2 produttori su 4 → resume cieco, retry feedback cieco, e il purge cancellava **sessioni vive** a ogni apertura | `2acf48d`, `aa8894f` |
| **B291** | I test API scrivevano nel `backend/data/user_state.json` **tracciato** | `e1b1208` |
| **B292 / b / c** | PWA che non si apriva offline: precache di route autenticate (404 ingoiato), cache che si autocancellava perché Clerk non carica offline, e «Load failed» + «completa l'onboarding» mostrati **insieme** | `a60d3bd`, `91116bc`, `2971fb5` |

## `file:line` driftati rispetto all'audit

- `top-bar.tsx:15` aveva **già** `min-h-[44px]` (F40 restava valido solo per `aria-label` + `<a>` nativo)
- `session-card.tsx:252-272 / 1047-1071` (F20): righe spostate dalle fasi A/B/F; il walk duplicato era a `204-232` e `1018-1046`
- `guided-exercise-step.tsx:882` (F60): il ring era a `598` e `897`
- I 3 esercizi «senza immagine» (F13) hanno la riga `image:` **commentata**: placeholder deliberati, non riferimenti rotti

## Decisioni prese

| Item | Decisione |
|---|---|
| **E-4** (`adaptation/closed_loop.py`) | Opzione **(c)**: rimosso il ramo `adjustments` morto (zero lettori), tenuto il cooldown (ha un lettore vivo), doc allineata. Attivazione → `A-CLOSED-LOOP-ACTIVATION` con **sunset 2026-09-20** → default rimozione |
| **F-4** (chiavi guided) | Chiavi **non** identiche: divergenza reale trovata e corretta in B290. Purge → **migrazione guardata** |
| **F52** | Non è payload morto: è feature backend **completa senza UI** → `A-TEST-REMINDER-UI` (**P1**, è metodologia) |
| **F16** legacy | **Purge**, non migrazione: ri-attribuire dati ambigui all'utente loggato È la leak da chiudere |
| **Outbox** | Solo write append-only e autoconsistenti. Done/Skip escluso (spedisce l'intero week plan) → `A-DELTA-EVENT-ENDPOINT` |
| **F19** | Le copie non erano tutte identiche: adottato il comportamento **migliore** (`setError(null)`), non uno a caso |
| **F55-F58** | Fuori scope dichiarato dall'inizio → `B-REFACTOR-COMPONENTS` |

## Decisioni ancora pendenti

- `A-CLOSED-LOOP-ACTIVATION` — attivare il cooldown o rimuoverlo (serve misurare la doppia penalizzazione con `progression_v1` su feedback reali). **Sunset 2026-09-20**
- `A-CLERK-PROVIDER-SCOPE` — vale la ristrutturazione della root per 227 KB su `/demo`?
- `B289` — `used_grade` scartato per 39 esercizi su 40 (STOP-gate `progression_v1`)
