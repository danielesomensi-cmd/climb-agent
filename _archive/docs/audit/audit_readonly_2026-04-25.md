# climb-agent — Read-Only Audit Report

Date: 2026-04-25

## 1. Executive Summary

Audit read-only completato.

Finding principali:

- **P1:** il resolver ignora `intensity_max` nei blocchi inline; `regeneration_easy` può risolversi a casa in un esercizio high-intensity (`dip`) invece di recovery/climbing easy.
- **P1/P2:** Stripe webhook intercetta eccezioni ma ritorna comunque `200`, quindi Stripe non ritenta eventi falliti.
- **P2:** frontend non gestisce globalmente `402 subscription_required`; l'utente può vedere errori raw o nessun feedback.
- **P2:** `npm run lint` fallisce: 30 errori, 38 warning.
- **P2/P3:** drift documentale tra `CLAUDE.md`, codice e roadmap su endpoint, intent, closed-loop naming.

## 2. Relevant Files Discovered From CLAUDE.md

Da `CLAUDE.md` ho considerato rilevanti:

- Engine: `backend/engine/planner_v2.py`, `replanner_v1.py`, `macrocycle_v1.py`, `resolve_session.py`, `progression_v1.py`, `adaptation/closed_loop.py`, `closed_loop_v1.py`.
- API: `backend/api/main.py`, `backend/api/routers/*`, `backend/api/deps.py`, `backend/api/stripe_webhook.py`.
- Frontend: `frontend/src/app`, `frontend/src/components`, `frontend/src/lib`.
- Cataloghi: `backend/catalog/sessions/v1`, `backend/catalog/templates/v1`, `backend/catalog/exercises/v1`.
- Test: `backend/tests`.
- Docs: `README.md`, `PROJECT_BRIEF.md`, `docs/ROADMAP_CURRENT.md`, `docs/ENGINE_ARCHITECTURE.md`.

Workflow da `CLAUDE.md`: analisi prima di implementare, STOP obbligatorio per planner/replanner/macrocycle/resolver/progression/closed-loop/schema/multi-module; frontend su branch preview con OK esplicito; backend-only può andare diretto; test e `sync_status.py` prima/fine brief.

## 3. Commands Run

Read-only / verifica:

- `sed` su `CLAUDE.md` e file rilevanti.
- `find` / `rg` per mappare engine, router, frontend, test.
- `git status --short`.
- `python3` one-liner per contare endpoint e intent.
- `python3` one-liner per riprodurre `regeneration_easy` resolver.
- `python3 -m pytest ...` fallito: Python di sistema senza `pytest`.
- `source .venv/bin/activate && python -m pytest backend/tests/test_planner_v2.py -q` -> pass.
- `source .venv/bin/activate && python -m pytest backend/tests/test_resolve_real_sessions.py backend/tests/test_replanning_v1.py -q` -> pass.
- `npm run lint` in `frontend/` -> fail, 30 errori / 38 warning.

## 4. Confirmed Issues, Ranked By Severity

### P1 — Inline resolver ignores `intensity_max`, causing wrong exercise selection

`regeneration_easy.json` declares `intensity_max: "low"` for the main recovery block and `required_equipment: ["gym_boulder"]`: `backend/catalog/sessions/v1/regeneration_easy.json:21`, `backend/catalog/sessions/v1/regeneration_easy.json:44`.

But `_resolve_inline_block()` only reads `role`, `domain`, `pattern`, `equipment`: `backend/engine/resolve_session.py:952`. It passes no intensity bound to P0: `backend/engine/resolve_session.py:989`.

Reproduction resolved `regeneration_easy` at home with no equipment as `success`, selecting `dip` for `continuity_main`; `dip` is `intensity_level: high`.

### P1/P2 — Stripe webhook swallows handler failures and returns 200

In `backend/api/stripe_webhook.py:95`, exceptions are logged, then the handler still returns `200` at line 99. The inline comment explicitly says Stripe will not retry: `backend/api/stripe_webhook.py:97`. For payment/subscription state, this can permanently drop an event.

### P2 — `customer.deleted` still unhandled

Webhook dispatch handles checkout/session/subscription/invoice events but not `customer.deleted`: `backend/api/stripe_webhook.py:84`. This is already open as B203, but still confirmed in code.

### P2 — Frontend subscription failure UX is incomplete

`request()` handles only 401 specially; all other statuses, including 402, become raw `Error("API 402: ...")`: `frontend/src/lib/api.ts:54`.

Settings portal catches errors and silently resets loading without user feedback: `frontend/src/app/(main)/settings/page.tsx:789`.

### P2 — Frontend lint currently fails

`npm run lint` reports 30 errors / 38 warnings. Examples: `frontend/demo.jsx` parse error, `frontend/scripts/build-sw.js` forbidden `require()`, React compiler hook/ref errors in guided, tabata, timers, settings, quick-add, macrocycle timeline.

### P3 — Replan UI exposes only 8 of 15 backend indoor intents

Backend has 15 indoor intents: `backend/engine/replanner_v1.py:84`. Frontend dialog exposes 8: `frontend/src/components/training/replan-dialog.tsx:29`. Could be intentional product simplification, but it is undocumented and creates API/UI capability drift.

## 5. Hypotheses / Risks Requiring Manual Verification

- `regeneration_easy` may surface as a visibly wrong guided recovery session after skip/rest/recovery flows, especially home/no-wall.
- Other inline blocks using `intensity_max` may select exercises outside intended intensity.
- Session-level `required_equipment` is not enforced by resolver; planner/replanner metadata may be the only gate.
- Lint may not be in CI, otherwise current frontend would block deploys.
- 402 UX may already be partially masked by page-level hooks, but global API behavior is raw.

## 6. Planner / Backend Findings

- `_SESSION_META` says `regeneration_easy` has locations `home/gym/outdoor` and no required equipment: `backend/engine/planner_v2.py:51`. Catalog says it requires `gym_boulder`: `backend/catalog/sessions/v1/regeneration_easy.json:21`. Import emits a warning, but tests still pass.
- `rest` intent maps to `regeneration_easy`: `backend/engine/replanner_v1.py:85`. This makes the mismatch user-facing.
- Targeted planner/resolver/replanner tests passed, so current tests do not catch this behavior.

## 7. Frontend / UI Findings

- `npm run lint` is red.
- `window.location.href` remains in API auth redirect, subscribe checkout, settings portal.
- `console.warn/error` remains in production paths.
- Replan dialog intent set is narrower than backend intent set.
- Billing portal error path has no user-visible error.

## 8. Test Coverage Gaps

Missing or weak tests:

- Resolver test asserting inline `intensity_max` is enforced.
- Resolver/planner test failing on `_SESSION_META.required_equipment` vs session JSON mismatch.
- End-to-end skip/rest -> resolved session test for `regeneration_easy`.
- Webhook test that handler exceptions return non-2xx for Stripe retry.
- `customer.deleted` webhook test.
- Frontend API/request tests for 402 subscription redirect/UX.
- Lint appears not enforced in current verification baseline.

## 9. Documentation Or Workflow Drift

- `CLAUDE.md` says 63 endpoints: `CLAUDE.md:149`. `PROJECT_BRIEF.md` says 67: `PROJECT_BRIEF.md:25`. Code count is 67 when including `app.add_api_route("/api/stripe/webhook")`: `backend/api/main.py:134`.
- `CLAUDE.md` says replanner has 13 indoor + 3 outdoor intents: `CLAUDE.md:144`. Code has 15 + 4.
- `backend/api/deps.py` docstring says no subscription row is a no-op/onboarding case: `backend/api/deps.py:316`. `subscription_guard.py` correctly says fail-closed denies no row: `backend/engine/subscription_guard.py:151`.
- `docs/ROADMAP_CURRENT.md` still contains internally conflicting Stripe status text: earlier "TEST MODE / disabled" and later "LIVE".

## 10. Suggested First 3 Small PRs

1. Resolver/catalog safety PR: enforce or explicitly validate `intensity_max`, add regression for `regeneration_easy` not selecting `dip`, and make `_SESSION_META`/JSON equipment mismatch a failing test.
2. Stripe reliability PR: return non-2xx on webhook handler failures and add `customer.deleted` handling/tests.
3. Frontend subscription UX PR: centralize 402 handling in `frontend/src/lib/api.ts`, show clean redirect/toast, and add visible portal error handling.

## 11. Questions Before Implementation

- For `regeneration_easy`, should it be gym-only climbing recovery, or should home recovery be a different session such as yoga/flexibility?
- Should `domain` remain soft for inline main blocks, or should required inline blocks be allowed to fail rather than pick unrelated exercises?
- Should `intensity_max` be part of the canonical resolver contract?
- Should lint be required for frontend PRs now, or cleaned in a separate hygiene pass?
- For Stripe webhook failures, do you want strict retry semantics immediately, even if that may produce repeated Stripe retries during transient Supabase outages?
