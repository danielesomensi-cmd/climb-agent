# D216 — Audit: session_duration calculation + display semantics

**Brief:** D216 (placeholder in original brief was D219; `next_brief.py` returned D216)
**Type:** D (read-only audit, no code changes)
**Date:** 2026-04-20
**Trigger:** Technique Focus submitted via guided path ~15:57 CEST showed `Completed · ~90 min`; earlier Upper Body Weights showed `Completed · ~35 min`. Both values coincide with frontend slot-table fallbacks, not with the wall-clock elapsed.
**Touches:** `backend/api/routers/feedback.py`, `backend/api/routers/week.py`, `backend/engine/adaptive_replan.py`, `backend/engine/report_engine.py`, `frontend/src/app/(guided)/guided/[date]/[sessionId]/page.tsx`, `frontend/src/components/training/session-card.tsx`, `frontend/src/components/training/feedback-dialog.tsx`, `frontend/src/app/(main)/today/page.tsx`.

> **Read-only.** No code changed, no tests added, no state mutated. A follow-up B-type brief is required to act on the findings.

---

## TL;DR

The “Completed · ~XX min” badge has **two independent defects** that conspire to show a template-like value instead of the measured wall-clock:

1. **Backend write gap.** `POST /api/feedback` persists `session_duration_seconds` into `session_completion_log` and `feedback_log`, but **never onto the session slot** inside `current_week_plan` / `week_plans[*]`. Only `GET /api/week/{n}` back-fills it via `_attach_feedback` (`week.py:170-171`). The POST response returns the plan *without* that field, so the frontend cache is wrong until the next full week refetch.
1. **Frontend slot-table fallback.** `session-card.tsx:864-877` (badge) and `:1150` (drawer) fall back to a hard-coded `{lunch:35, morning:60, evening:90}` table when `session.session_duration_seconds` is nullish. The fallback adds a `~` prefix but keeps the word “Completed” — visually indistinguishable from a measured value. Technique Focus runs on `evening` slot → fallback `90`. Upper Body on `lunch` slot → fallback `35`.

Result: the `~` badge shown right after submit is a slot-derived placeholder, *not* the elapsed timer. A page refresh (which re-calls `GET /api/week/0` → `_attach_feedback`) replaces it with the real duration from `feedback_log`.

Secondary findings:
- `duration_source` is sent by the feedback-dialog path (`today/page.tsx:866`) but is **silently dropped** server-side (no write site exists). `report_engine.py:817` reads it with default `"timer"` — a dead branch today.
- Three copies of the slot-estimate table live in the codebase (`session-card.tsx`, `feedback-dialog.tsx`, `report_engine.py`) — drift risk.
- The guided timer itself is implemented correctly: wall-clock based (`Date.now() - startedAt`), survives iOS Safari suspension, and B197 already preserves `startedAt` across restarts via localStorage.

---

## Section 1 — Backend: `session_duration_seconds` write path

### 1.1 Where it is written

| Location | File:Line | What it writes | Trigger |
|---|---|---|---|
| `session_completion_log[-1].session_duration_seconds` | `feedback.py:313-322` | value from `req.log_entry.get("session_duration_seconds")`; `max(prev, duration)` on resubmit (B197 Bug 1) | every `POST /api/feedback` |
| `feedback_log[*].session_duration_seconds` | `adaptive_replan.py:115-146` (`append_feedback_log`) | same source, same `max()` merge on dedup (B197 Bug 1) | every `POST /api/feedback` (step 4) |
| `week_plan.weeks[].days[].sessions[].session_duration_seconds` | `week.py:170-171` (`_attach_feedback`) | copied from `feedback_log` onto the matching session slot by `(date, session_id)` | **only** on `GET /api/week/{n}` |

### 1.2 Where it is **not** written

- Nowhere in `feedback.py` is the duration copied onto the session slot inside `current_week_plan` or `week_plans[start]`. The `actual_exercises` block at `feedback.py:210-233` is carefully mirrored into both `current_week_plan` and `week_plans[start_key]`, but the neighbouring `session_duration_seconds` field is absent from that block.
- `persist_week_plan` (`replanner.py:76-103`) saves the in-memory `state["current_week_plan"]` to the per-week cache and `save_state`s. It does **not** call `_attach_feedback`.
- The response body of `POST /api/feedback` at `feedback.py:335-336` returns `state["current_week_plan"]` verbatim. Therefore the returned plan is missing the duration on the session slot.

### 1.3 Source of the value

- **Guided path** (`guided/[date]/[sessionId]/page.tsx:417`):
  ```ts
  const durationSeconds = Math.max(0, Math.floor((Date.now() - new Date(state.startedAt).getTime()) / 1000));
  ```
  Wall-clock elapsed since `state.startedAt` was written. `state.startedAt` is set **when the user taps “Start” on the session card** (`session-card.tsx:248`, inside `buildGuidedState`), *not* when the first exercise is marked done. No `duration_source` field is sent in this payload (`guided/page.tsx:420-427`).

- **Feedback-dialog path** (`today/page.tsx:851-872`):
  ```ts
  session_duration_seconds: durationMinutes * 60,
  duration_source: durationSource,  // "user_reported" | "estimated"
  ```
  `durationMinutes` defaults to the slot-based pre-fill from `feedback-dialog.tsx:36-52` (`SLOT_ESTIMATES = {lunch:35, morning:60, afternoon:60, evening:90}`). If the user edits the input, `duration_source="user_reported"`; if they leave the pre-fill, `duration_source="estimated"`.

- **Week page / ad-hoc mark-done** (`week/page.tsx:472-476`): same shape as today page, same source.

### 1.4 `duration_source`: plumbed but never persisted

- **Frontend sends it** (feedback-dialog path only, not guided).
- **FastAPI model** (`models.py:111-115 FeedbackRequest`) declares `log_entry: Dict[str, Any]` so the field flows through untyped.
- **Backend never writes it.** Search for `duration_source` across `backend/` returns a single read site: `report_engine.py:817` `entry.get("duration_source", "timer")`. Since no write site exists in any router or engine module, the read always returns the default `"timer"`. The feature is **inert** today.

### 1.5 What the POST response carries

When the user submits Technique Focus via guided on 2026-04-20:

| Store | Ends up with the real duration? |
|---|---|
| `session_completion_log[-1]` | ✅ yes (wall-clock seconds from payload) |
| `feedback_log[*]` | ✅ yes |
| `state["current_week_plan"].weeks[0].days[i].sessions[j]` | ❌ no — field never written by any POST path |
| `state["week_plans"][start_key].weeks[0].days[i].sessions[j]` | ❌ no |
| `response["week_plan"]` (what the frontend receives) | ❌ no |

This is the defect’s primary root cause.

---

## Section 2 — Frontend: guided timer behaviour

### 2.1 Timer lifecycle

- **`startedAt` is set in `session-card.tsx:248`** inside `buildGuidedState`, called by `handleStartGuided` when the user taps the play button. Stored as `new Date().toISOString()` into localStorage under `guided_session_${userId}_${date}_${sessionId}`.
- **B197 restart-guard** (`session-card.tsx:277-306`): if a prior `guided_session_*` entry exists in localStorage for the same `(date, session_id)`, the pre-existing `startedAt` is preserved. Prevents a `/today` render race from resetting the clock.
- **Display while running**: `session-timer.tsx:20-39` computes elapsed as `Date.now() - new Date(startedAt).getTime()` every 1 s via `setInterval`. **Pure wall-clock** — correct pattern for iOS Safari suspension (the clock keeps moving even if the JS interval is frozen, and the next tick after resume catches up).
- **Display on summary**: `guided-summary.tsx:53` reuses the same `<SessionTimer>` — same wall-clock math.

### 2.2 What gets posted

On “Submit & finish” (`guided/page.tsx:311-472`):

```ts
const durationSeconds = Math.max(
  0,
  Math.floor((Date.now() - new Date(state.startedAt).getTime()) / 1000)
);
// ...
const logEntry = {
  date: state.date,
  session_id: state.sessionId,
  session_duration_seconds: durationSeconds,
  actual: { exercise_feedback_v1: exerciseFeedback },
};
```

Payload is always sent, always positive (`Math.max(0, …)` guards against clock skew). `duration_source` is **not** sent in this path.

### 2.3 Suspension survivability

- Timer: ✅ wall-clock → survives.
- Persistence: `state` (including `startedAt`, `currentIndex`, `exercises[]`) is written to localStorage on every change (`guided/page.tsx:124-126`) — survives PWA backgrounding / tab swap / reload.
- iOS Safari audio: `visibilitychange` handler at `guided/page.tsx:150-167` explicitly resumes `AudioContext` when the page comes back to foreground. Orthogonal to duration accuracy but worth noting as a sibling concern that’s already handled right.

### 2.4 Edge cases

| Path | Produces plausible `session_duration_seconds`? |
|---|---|
| User opens guided, does exercises, submits | ✅ wall-clock `submit_ts - play_tap_ts` |
| User taps play, walks away, comes back N hours later, submits | ✅ but the value includes dead time (not a bug — wall-clock is deliberate) |
| User resumes an in-progress session via localStorage | ✅ original `startedAt` preserved (B197) |
| Session-card shortcut → mark-done (non-guided) via feedback-dialog | ⚠ **not wall-clock** — value is `durationMinutes * 60` where `durationMinutes` pre-fills from slot table; user keeps or edits it. See §1.3. |
| Week-page mark-done | same as above |

### 2.5 `startedAt = play tap` vs `startedAt = first exercise tap`

Current choice: `startedAt` is set when the user taps play on the session card (`buildGuidedState`). The user could sit on the “session intro” view for minutes before tapping the first “Done” — that wait is included in the elapsed. This is a judgement call, not a bug; but it means “duration” currently means “session tab time” rather than “active work time”. Worth mentioning for the remediation discussion.

---

## Section 3 — Frontend: “Completed · ~XX min” label render

### 3.1 Two render sites (same logic)

Both the green badge on the card and the drawer header share the same fallback ladder.

- **Badge** (`session-card.tsx:864-877`):
  ```tsx
  const hasReal = session.session_duration_seconds != null
               && session.session_duration_seconds > 0;
  const slotEst: Record<string, number> = { lunch: 35, morning: 60, evening: 90 };
  const estMin = slotEst[session.slot] ?? 60;
  const durLabel = hasReal
    ? ` · ${Math.round(session.session_duration_seconds! / 60)} min`
    : ` · ~${estMin} min`;
  ```
  Visual cue: measured uses white text (`text-white`), estimated uses muted (`text-zinc-300`) + `~` prefix. Same green pill though — easy to miss.

- **Drawer** (`session-card.tsx:1150`): single-expression variant of the same logic, slot-fallback map inlined.

### 3.2 Precedence

1. If `session.session_duration_seconds != null && > 0` → format as `Math.round(x / 60)` minutes, no tilde.
1. Else → `~${ {lunch:35, morning:60, evening:90}[session.slot] ?? 60 } min` with tilde.

There is **no read of any `template.estimated_duration_minutes` / `target_duration_min` in the completed branch**. The only place the template-derived duration appears is the *planned* chip at `session-card.tsx:855-863` (`~${targetMin} min`, read from `resolved.session.target_duration_min`). That chip is a sibling, not a fallback path.

### 3.3 Why this fires

Because the POST response (see §1.5) carries no `session_duration_seconds` on the session slot, **every render that consumes the POST response directly will enter the fallback branch**. Specifically:

```
guided/page.tsx:447-453
  qc.setQueryData(['week', 0], { ..., week_plan: response.week_plan })
session-card.tsx renders using session from queryCache
  → session.session_duration_seconds === undefined
  → hasReal = false
  → slotEst[session.slot]  // evening → 90
  → "Completed · ~90 min"
```

A full `GET /api/week/0` refetch (e.g. pull-to-refresh, route change, hard reload) would instead run `_attach_feedback` and populate the field. The label would then flip to, e.g., `Completed · 31 min` (no tilde).

---

## Section 4 — Reproducibility hypotheses for the `~90 min` observation

### H1 (PRIMARY — confirmed by code inspection)

*POST /api/feedback returns a plan without `session_duration_seconds` on the session slot. Frontend writes that plan directly to queryCache via `setQueryData`. Badge renders the slot-table fallback.*

**Evidence:**
- `feedback.py:210-233` writes `actual_exercises` on the session slot but not duration.
- `feedback.py:328-336` returns `state["current_week_plan"]` as `response.week_plan` — never routed through `_attach_feedback`.
- `guided/page.tsx:447-458` does `qc.setQueryData(queryKeys.week(0), …, response.week_plan)` **instead** of a refetch when the response carries a plan.
- `session-card.tsx:866` `slotEst["evening"] = 90` matches the observed `~90 min` exactly. For Upper Body (lunch slot) `slotEst["lunch"] = 35` matches `~35 min`.
- The tilde character in the observed badge is itself a tell: the only code path that emits `· ~${N} min` (with tilde) is the fallback branch at line 870 / 1150.

**Refutation of alternatives:**
- H2 (timer never started): refuted. `buildGuidedState` always sets `startedAt` the moment the play button is tapped, and the guided page mount at `page.tsx:88-113` redirects to `/today` if localStorage is empty. There is no code path that submits guided feedback without a `startedAt`.
- H3 (timer was counter-based and froze on suspension): refuted. `session-timer.tsx:24-26` uses `Date.now() - start` — wall-clock.
- H4 (timer ran but clock read 0 because Date.now() == startedAt): refuted. The user walked through exercises between play-tap and submit — elapsed must be > 0.
- H5 (label reads a different field): refuted. No read of `template.duration_min` / `estimated_duration_minutes` in the completed branch. Only the slot table.
- H6 (Technique Focus opened via FeedbackDialog, not guided): possible but doesn’t change the outcome — the dialog path pre-fills with `SLOT_ESTIMATES["evening"] = 90` and sends `session_duration_seconds = 5400`. In that case the backend **would** store 5400 in completion_log/feedback_log and subsequent GETs would show `· 90 min` *without* tilde. Since the observed badge has a tilde, guided path is the more likely provenance — corroborating H1.

### H7 (contributing factor for Upper Body at 10:49)

The `~35 min` on Upper Body is *also* the fallback (lunch=35), **not** the real `session_duration_seconds=1868` stored in `session_completion_log` (per D215 snapshot). The same H1 mechanism applies. This is independent corroboration that H1 is the general pattern and not a Technique-Focus-specific anomaly.

### Net: H1 is the sole load-bearing cause

No scenario that does not require H1 fits the evidence.

---

## Section 5 — Recommended remediation direction (prose only — no code)

Four independent improvements, listed in priority order. A fix brief should bundle items 1 + 2 at minimum.

### 1. [PRIMARY, XS] Attach `session_duration_seconds` to the session slot in `POST /api/feedback`

In `feedback.py`, extend the already-running loop at `L210-233` (the `actual_exercises` persistence block) to also write `session_duration_seconds` onto the matching `_sess` and `_sess_c` objects. The value is already in scope via `req.log_entry.get("session_duration_seconds")`. Mirror the B197-style `max(prev, duration)` logic that block already implements for completion_log.

**Effect:** `response.week_plan` returned from POST now carries the measured duration on the session slot → frontend queryCache is correct on first render → the `~` fallback path stops firing on the happy path. No refetch required.

**Effort:** XS (≤10 lines, one file).
**Impact:** eliminates the misleading `~90 min` immediately after every guided submit.
**Regression surface:** low. The GET `_attach_feedback` path still runs and is idempotent; both writers would converge to the same value (modulo the same `max()` rule).

### 2. [DEFENSE-IN-DEPTH, XS] Stop lying with the slot table in the completed label

Current UX treats a completely unknown duration as “a plausible guess with a tilde”. Two options, either is acceptable:

- **Option A (cleaner):** when `session.session_duration_seconds` is nullish, show `Completed` with no duration at all, or `Completed · —`. No fallback number.
- **Option B (more informative):** show `Completed · no timer data`. More verbose but unambiguous.

Keep the slot-estimate mapping only where it is genuinely a *pre-fill suggestion* the user can edit — `feedback-dialog.tsx`. Remove it from `session-card.tsx:866,1150`.

Rationale: the tilde is a 1-pixel cue on a green pill; no one will read the colour difference between `text-white` and `text-zinc-300` as “measured vs estimated”. The current UI semantically conflates “we timed it” with “we guessed from the slot”.

**Effort:** XS. **Impact:** restores user trust in the Completed badge.

### 3. [HYGIENE, S] Decide on `duration_source` — persist or remove

`duration_source` is currently a Potemkin field: frontend sends it (dialog path only), backend accepts the payload, nobody writes it, `report_engine.py:817` reads a default. Two coherent resolutions:

- **Persist it.** Write `duration_source` into `session_completion_log[-1]` and `feedback_log[*]` in `feedback.py`/`adaptive_replan.py`, and into the session slot alongside item 1. Then `report_engine.py` telemetry becomes truthful (actual vs estimated minutes per week). Also send it from the guided path (`duration_source="timer"`).
- **Remove it.** Drop the field from the feedback dialog payload, drop the `duration_source` lookup in `report_engine.py`. Simpler if reports won’t differentiate in the near term.

The dialog path’s `"user_reported"` vs `"estimated"` distinction is a real signal that would be worth persisting if the /reports page ever surfaces it. Today it doesn’t.

**Effort:** S. **Impact:** makes report_engine trustworthy; removes silent drop of a field the frontend thinks matters.

### 4. [HYGIENE, XS] Single-source the slot-estimate map

Today: `{lunch:35, morning:60, evening:90}` lives in three places —
- `frontend/src/components/training/session-card.tsx:866,1150`
- `frontend/src/components/training/feedback-dialog.tsx:36-41` (adds `afternoon:60`)
- `backend/engine/report_engine.py:800`

Three copies drift; `feedback-dialog.tsx` already carries an extra `afternoon:60` entry that the other two don’t. Consolidate to one source (exposed via `/api/catalog/...` or hard-coded in a shared `lib/`). If item 2 is adopted, the frontend copies go away and only the backend report copy needs to stay.

**Effort:** XS. **Impact:** prevents future silent label divergence.

### Optional 5. [POLICY] Decide what “session duration” means

`startedAt` is currently **“time of play tap”**, not “time of first exercise Done”. A session opened for 20 minutes before the first rep counts those 20 minutes as training. Consider:

- Keep current semantics, document as “session tab time”.
- Or move `startedAt` to first exercise completion (reset once).
- Or start `startedAt` on play tap but reset it on an explicit “Begin warmup” tap.

Not a bug today. Worth one line in the user guide either way.

---

## Section 6 — Recommended next brief

**B-type fix brief, label `B<next>` (likely B217 per `next_brief.py`):**

- Implement remediation items 1 + 2 together (backend write + frontend label honesty). Single commit, atomic behaviour change.
- Add a test in `backend/tests/` that POSTs `/api/feedback` with a `session_duration_seconds` payload and asserts the response `week_plan`’s matching session slot carries that exact value.
- Add a second test that asserts `_attach_feedback` on subsequent GETs does **not** clobber a field that already matches (idempotency).
- Frontend: a unit test on `session-card.tsx` rendering logic that asserts `Completed · —` (or whichever label is chosen) appears when `session_duration_seconds` is absent, and `Completed · 31 min` appears when it’s 1868. Can piggyback on the existing jest/vitest setup.

Remediation items 3 and 4 can ride along or be split into a follow-up brief depending on scope appetite.

**STOP.** Await Daniele’s explicit OK before any fix brief is opened or code is written.

---

## Deliverables

- `docs/audit/D216/findings.md` — this document.

No snapshot file produced: the anomaly is fully reconstructable from the committed code (no per-user state involved).
