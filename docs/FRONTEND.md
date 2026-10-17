# Frontend — climb-agent

> Pagine, routing di ingresso, auth wall dell'onboarding (il conteggio «Pages (N)» è aggiornato da `scripts/sync_status.py`). Spostato da `CLAUDE.md` in D285 (2026-10-17). Le regole operative restano in `CLAUDE.md`.

## Overview

Next.js 16 App Router (Turbopack) + Tailwind CSS + shadcn/ui. Mobile-first dark-mode PWA.

**Pages (46):** 19 under `(main)` + 2 under `(guided)` (guided session, session-builder play) + 16 under `/onboarding` (index + 15 route dirs) + 2 auth (sign-in, sign-up) + 1 root dispatcher + `/assessment` + `/demo` + `/legal` + `/offline` + 2 dev-only (`/dev/tokens`, `/dev/today-states`). Recount verified against `find frontend/src/app -name page.tsx` (D277, 2026-08-17). **The onboarding sub-count was wrong from D269 until D277** and the breakdown summed to 45 against a headline of 46: B320 deleted `/onboarding/recover` and decremented the sub-count on top of a figure that was already one short, so the total was right for the wrong reason. Check the sum, not just the headline. (The pre-D269 breakdown summed to 36 and omitted the session-builder, body-part-picker, `/demo`, `/offline` and the dev pages.)

**Entry-point routing (B300, `src/app/page.tsx`)** — the root `/` is a smart dispatcher, not a page:
- **Signed-out** (cold ad/flyer visitor) → `/onboarding/welcome` (public marketing landing: hero + value props + "Start assessment" CTA + a visible "Sign in" link). Before B300 it sent them to the bare `/sign-in` login wall — a bad ad landing.
- **Signed-in with a macrocycle** → `/today`.
- **Signed-in, no macrocycle** → `/onboarding/welcome` (→ wizard).
- **Offline** → last known destination from localStorage (A245), never a forced re-onboard.

`/onboarding/welcome` is the **public entry page**: it renders `WelcomeContent` when unauthenticated (no auth wall) and redirects authenticated users onward. It's the recommended landing for cold acquisition traffic with context — see `docs/attribution_utm_convention.md` (cold zero-context traffic still prefers `/demo`).

**Where the auth wall sits (A256)** — the whole 12-step wizard is public (`PUBLIC_ROUTES` derives them from `ONBOARDING_STEPS`, so a new step is public by default), plus `/onboarding/recover`. The account is requested **only at the submit CTA on `/onboarding/review`**, once the user can see their own summary. The tapped CTA travels back as `?complete=generate|test` in the Clerk `redirect_url`, and `/review` auto-submits on return. `/onboarding/start-week` and `/onboarding/install` stay gated — they run after a plan exists.

Answers typed before signing up live in `localStorage` under `climb_onboarding_draft_anon` and are **adopted** by `loadDraft()` at sign-in. That key must be cleared on submit alongside the user-scoped one, or the next anonymous visitor on a shared device inherits it (regression guard: `onboarding-draft-scope.test.ts`).

- `/today` — Today's sessions, mark done/skipped, post-session feedback
- `/week` — 7-day grid, day detail cards, replan dialog, multi-week navigation
- `/plan` — Assessment radar chart + macrocycle timeline + phase details
- `/session/[id]` — Resolved exercises with prescription details, load score
- `/reports/weekly` — Adherence, load, difficulty distribution, progression table
- `/outdoor` — Outdoor history, stats, per-spot breakdown, grade histogram
- `/whats-next` — Votable roadmap + feedback form
- `/settings` — Profile, goals, equipment, spots, regenerate assessment/macrocycle
- `/guided/[date]/[sessionId]` — Step-by-step guided session with timer
- `/free-session` — Log free climbing sessions (lead/boulder/outdoor)
- `/mobility` — Stretching & Mobility guided flow (multi-region setup → auto-advancing timer, Core Circuit UX)
- `/tabata` — Standalone interval timer (documented in `docs/user_guide_v1.md` §16)
- `/coach` — LLM Coach chat (plan-aware, KB-grounded, suggest-only; 30 msg/day; weather-aware via on-demand `get_weather` tool with GPS + spot geocoding, personal notes, suggested chips)
- `/assessment` — **Public** 5-axis assessment (A262/A263). No account, nothing stored: six questions → radar + weakest axis. Scale selezionabile (French/YDS, Font/V-scale — conversione client-side prima dell'invio, l'engine riceve sempre la sua convenzione); blocco opzionale max hang + weighted pull-up che rende misurati gli assi dita/tirata. **A268**: chi compila quei numeri vede anche il toggle `[ Goal | Elite ]` di A267 (solo render, niente di persistito); chi li salta vede la pagina identica a prima. The acquisition landing meant to be posted publicly; the CTA seeds the answers into the wizard's anonymous draft (`seedDraftFromAssessment`) so nothing is retyped.
- `/guide` — User guide
- `/subscribe` — Subscription plans and checkout
- `/session-builder`, `/session-builder/[id]`, `/session-builder/[id]/view`, `/session-builder/[id]/play` — Custom session builder: list, edit, read-only view, guided playback (`/api/custom-session/*`)
- `/body-part-picker` — Body-part session generator (preview → insert into the week plan)
- `/demo` — Zero-context acquisition landing (no Clerk needed by the page itself — see `A-CLERK-PROVIDER-SCOPE`)
- `/offline` — Service-worker offline fallback
- `/dev/tokens`, `/dev/today-states` — Dev-only harnesses (design tokens, `/today` state matrix)
- `/onboarding/*` — 15 route dirs (12 wizard steps + `welcome` + `install` + `start-week`; corrected in D277). **The wizard proper is 12 steps** (`ONBOARDING_STEPS`: profile, experience, discipline, grades, goals, weaknesses, tests, limitations, locations, availability, trips, review). Outside that list: `welcome` (the public landing) plus `install` and `start-week`, which run *after* a plan exists and stay gated. (B320 removed `recover`: recovery-by-code was a pre-Clerk relic — recovery is signing in with the original email.)
