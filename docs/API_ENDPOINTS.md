# API endpoints — climb-agent

> Riferimento completo degli endpoint REST (contato da `scripts/sync_status.py`: header e righe di tabella sono verificati). Spostato da `CLAUDE.md` in D285 (2026-10-17). Le regole operative restano in `CLAUDE.md`.

## Endpoints

102 endpoints total (100 router + 2 app-level: health check + stripe webhook). B320 retired `/api/user/recovery-code` and `/api/user/recover`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/state` | User state. **B387**: lean by default — no `week_plans`, `current_week_plan`, `custom_sessions` (they have their own endpoints); `_omitted` lists what was left out, `?full=1` returns every key. The PUT response is the same lean view |
| PUT | `/api/state` | Deep-merge patch into state |
| GET | `/api/state/status` | Dirty-state check (is_macrocycle_stale) |
| DELETE | `/api/state` | Reset state to empty |
| GET | `/api/catalog/exercises` | List all exercises |
| GET | `/api/catalog/sessions` | List all session metadata |
| GET | `/api/onboarding/defaults` | Option lists for onboarding form |
| POST | `/api/onboarding/complete` | Atomic: save state + assessment + macrocycle (B293: profile bounds → 422). A250: auto-starts the 15-day LOCAL trial (subscriptions row `trialing`, no Stripe objects; lazy expiry in guard; checkout/portal convert it carrying remaining days) |
| POST | `/api/onboarding/start-week` | Shift macrocycle start_date back N weeks |
| GET | `/api/onboarding/draft` | Server-side wizard draft for the user, or null (B293) |
| PUT | `/api/onboarding/draft` | Save wizard draft (replace wholesale; wiped on complete; ignored if macrocycle exists) |
| POST | `/api/assessment/compute` | Recompute 5-axis profile |
| GET | `/api/assessment/grade-evidence` | A292 (R6b), read-only: does the outdoor log support a harder lead onsight than the declared one? Evidence = lead route, first appearance in the log, one `sent` attempt, style absent/onsight/flash; proposal = highest grade with ≥2 such routes on 2 days or 2 crags, only upward, never above the RP, never a declined grade. Trip-only evidence is flagged (`all_in_trip`), not blocked |
| POST | `/api/assessment/confirm-grade` | A292: confirm (`onsight`/`flash`/`worked` per route) or dismiss the proposal. Confirm writes `grades.lead_max_os` + `grades_source` and rebuilds `current_level`; dismiss writes `grade_evidence_dismissed`; worked routes leave the evidence for good. 422 on unknown route / insufficient evidence / not above current / above RP. Never rewrites the outdoor log |
| POST | `/api/public/assessment` | **Unauthenticated** (A262). 5-axis profile from six answers — acquisition surface for `/assessment`. Stateless: no `get_user_id`, no state read/write, nothing persisted. Rate-limited 20/min (per-IP, no user to key on). Rejects what it cannot score honestly: unknown grade → 422 (never a silent `grade_index` 0), onsight above redpoint → 422, missing grades → 422 instead of the engine's `7a`/`7c+` defaults. Boulder input in Font, mapped through `BOULDER_TO_LEAD` so it is scored against the same benchmarks as lead. **A263**: accetta anche `bodyweight_kg` + `max_hang_added_kg` / `weighted_pullup_added_kg` (peso **aggiunto**, negativo se assistito; il totale lo calcola il router). Numeri senza peso corporeo → 422, perché il fallback a 70 kg del motore riscalerebbe in silenzio il dato dell'utente. Risponde `measured_axes[]` (assi retti da un numero reale) e `estimated` = lista vuota. |
| POST | `/api/macrocycle/generate` | Generate new macrocycle |
| POST | `/api/macrocycle/start-new-cycle` | Start fresh macrocycle (atomic: archive → goal review → generate → flag tests). Subscription-gated. |
| POST | `/api/plan/pause` | Pause active plan (A223 — records pause start; idempotent) |
| POST | `/api/plan/resume` | Resume paused plan (A223 — shift future weeks by whole-week offset, extend end_date; idempotent) |
| GET | `/api/week/{week_num}` | Generate week plan (auto-resolves sessions). **A294**: `key_status` sibling of `week_plan` (key sessions of the phase, debt, validated re-schedule proposal, conflicts — derived at read, never persisted); optional client-local `?today=` |
| POST | `/api/week/test-reminder-response` | Handle periodic test reminder |
| POST | `/api/retest/decline` | **A320**: decline (`kind: decline`) or postpone (`kind: postpone` + `until`) the **pending** retest of one axis (`retest_status.axes.<axis>.next_test`). Body `{axis: finger\|pulling, kind, until?, reason: fatigue\|injury\|illness\|travel\|schedule\|not_needed\|other, note? (≤ 200, stored only — never shown to the coach LLM), trigger? (client's reading of the pending trigger), source: app\|coach\|cli, dry_run, today?}`. Stores the record in `retest_declines` (endpoint-owned key), removes the **engine's** planned tests of the axis from the later of the server's and the athlete's today (`today` clamped ±1 day; a combined test goes for both axes — the regeneration re-places the other one alone), stamps the revision and marks those weeks stale, plus the cached week the test now belongs to (the week of `until`, or of the next trigger of another kind) when it was generated without it; the athlete's own planned tests are kept and listed in `kept_user_owned_tests`. A decline also ends the axis' active postpones (the athlete's latest word wins). Response `{dry_run, decline, replaced (the record with the same key, else the postpone the decline ended), tests_removed, kept_user_owned_tests, weeks_marked_stale, retest_status}`. Errors (`detail: {code, message}`): 422 `not_covered` / `invalid_until` (also an `until` not after the pending test's own day: a postpone never brings a test forward) / `until_after_expiry`, 409 `no_pending_retest` / `trigger_mismatch`, 409 `{paused}` (a dry run is allowed while paused). `dry_run: true` runs on a copy, zero writes. Per-user write lock (B371). Subscription-gated |
| DELETE | `/api/retest/decline/{axis}` | **A320**: undo the stored declines / postpones of one axis (`?dry_run=&today=`): removes the records, takes out the engine's tests placed under a postpone (trigger `postponed`, dated from the later of the server's and the athlete's today — nothing backs them once the postpone is undone; the athlete's own are kept and listed) and marks stale those weeks and the weeks from this Monday generated under the records, so the next `GET /api/week` places the test again where the policy wants it. 422 `unknown_axis`, 404 `no_decline`, 409 `{paused}` (not on a dry run). An implicit decline (the athlete removed or replaced the test in a week's plan) is not undone here: the test goes back with an explicit add. Response `{dry_run, removed, tests_removed, kept_user_owned_tests, weeks_marked_stale, retest_status}`. Per-user write lock (B371). Subscription-gated |
| POST | `/api/session/resolve` | Resolve a single session to exercises |
| POST | `/api/session/add-exercise` | Add exercise to resolved session |
| POST | `/api/session/remove-exercise` | Remove exercise from resolved session |
| POST | `/api/session/surface-override` | B313: adapt a rope session to the boulder wall for the day (`surface: "boulder"`), or revert (`surface: null`). Writes the adapted session onto the slot (`surface_override` + `_user_edited`) so card, guided player and feedback read one source. Server picks the mechanism: catalog `boulder_fallback` swap, else same session re-resolved without `gym_routes` — the rope is stripped from the equipment in **both** cases. 422 if the location has no boulder wall or the primary block does not survive. |
| POST | `/api/replanner/override` | Apply day override (intent-based, equipment-aware). **A315**: an override that takes a key session away re-schedules it automatically → `auto_reschedules[]` (undo via `/events` `undo_auto_reschedule`) |
| POST | `/api/replanner/events` | Apply events (done/skipped) to week plan. **A294**: `prev_days` seeded (Sunday→Monday finger gap), returns `adjustments` (always empty since A301) + `key_status` + `guard_warnings` siblings (A301: alerts only, nothing rewritten); `dry_run: true` applies on a copy and returns `{week_plan, adjustments, key_status, key_conflicts}` with zero writes (`custom_session_payload` checks a custom that does not exist yet); new event `add_planned_session` (catalog session, no ripple — the key-session re-schedule); optional client-local `today`. **A315**: a write that makes a key requirement owe more applies its validated proposal automatically (free slot first, else in place of a non-key engine session) and returns `auto_reschedules[]` (`would_auto_reschedule[]` on a dry run); new event `undo_auto_reschedule {adaptation_id}` puts back what was replaced; `KEY_AUTO_RESCHEDULE=0` turns it off |
| GET | `/api/replanner/suggest-sessions` | Suggest sessions for quick-add |
| POST | `/api/replanner/quick-add` | Add extra session to a day. **A301**: applied exactly as picked — nothing is downshifted or rippled, `force` is a compatibility no-op, `adjustments[]` is always empty; returns `guard_warnings` (sibling, never persisted) + `warnings` (alert messages involving the added session) |
| POST | `/api/feedback` | Submit session feedback |
| GET | `/api/outdoor/spots` | List outdoor spots |
| POST | `/api/outdoor/spots` | Add outdoor spot |
| DELETE | `/api/outdoor/spots/{spot_id}` | Remove outdoor spot |
| POST | `/api/outdoor/log` | Log outdoor session |
| GET | `/api/outdoor/log/{date}` | Get outdoor session by date |
| PUT | `/api/outdoor/log` | Update outdoor session |
| DELETE | `/api/outdoor/log/{date}` | Delete outdoor session by date |
| GET | `/api/outdoor/sessions` | List outdoor sessions |
| GET | `/api/outdoor/stats` | Outdoor statistics |
| GET | `/api/outdoor/strategy` | Resolve deterministic strategy + nutrition for an outdoor day (layered patches) |
| GET | `/api/outdoor/pitch-ladder` | A265: deterministic pitch ladder for an outdoor day — absolute grade, attempts and rest per pitch, derived from the athlete's own onsight/redpoint (`performance.current_level.sport`, goal `current_grade` as fallback). Lead-only in v1, matching the strategy catalog. 422 rather than a guess when no usable grade exists. `/api/outdoor/strategy` now carries the same ladder under `pitch_ladder`. Persisted onto the day via the `set_outdoor_plan` replanner event (`day.outdoor_plan`, preserved in `_DAY_LEVEL_FIELDS`) and hand-editable from the day card. |
| POST | `/api/outdoor/session/start` | Start an active outdoor session (server-side timer) |
| POST | `/api/outdoor/session/{session_id}/finish` | Finish active outdoor session → immutable outdoor.v2 log |
| GET | `/api/outdoor/session/active` | Restore in-progress active outdoor session (with live routes) |
| POST | `/api/outdoor/session/{session_id}/log-climb` | Append a climb to the active session (live logging) |
| DELETE | `/api/outdoor/session/{session_id}/climb/{climb_index}` | Remove a climb from the active session |
| PUT | `/api/outdoor/session/{session_id}/routes` | Replace the active session's full routes list (live sync) |
| DELETE | `/api/outdoor/session/{session_id}` | Discard an active outdoor session without logging |
| POST | `/api/outdoor/convert-slot` | Convert outdoor slot to gym/home |
| GET | `/api/quaderno` | **A321**: the athlete's own route report ("quaderno", built in climb-watch and copied by `scripts/sync_quaderno.py`). `{available: false}` when the user has none, the link secret is unset or the manifest is unreadable; else `{available, generated, days (newest first), page_path, expires_at}` — `page_path` is a freshly signed link (1 h, HMAC with `QUADERNO_LINK_SECRET`, token in the path) relative to the API origin. Not subscription-gated (reading your own data) |
| GET | `/api/quaderno/v/{token}/{path}` | **A321**: one file of the user's quaderno for the in-app iframe — no bearer (an iframe cannot send it): the signed token names the user. Serves only paths the stored `manifest.json` lists (never the manifest itself); 403 bad/expired link, 404 anything else. Headers: `Cache-Control: no-store`, `Access-Control-Allow-Origin: *` (the sandboxed page is an opaque origin), `Referrer-Policy: no-referrer`, `nosniff`, CSP `sandbox allow-scripts` + inline script/style + Google Fonts + `frame-ancestors` the app's origins |
| GET | `/api/reports/weekly` | Weekly training report |
| GET | `/api/reports/monthly` | Monthly training report |
| GET | `/api/reports/heatmap` | Monthly rest-positive heatmap cells (`?month=YYYY-MM`) |
| GET | `/api/quotes/daily` | Daily motivational quote. **B384**: pure function of (user, day, context) — optional client-local `?date=`; writes `quote_history` at most once per new quote, under the user write lock (no more full-state save on every GET) |
| GET | `/api/tips/daily` | Daily feature-discovery tip (deterministic per user, `?date=` client-local) |
| POST | `/api/tips/{tip_id}/dismiss` | Dismiss today's tip (per-day, idempotent) |
| GET | `/api/milestones` | Milestone catalog + per-user unlock status (lazy eval) |
| POST | `/api/milestones/{milestone_id}/seen` | Mark an unlocked milestone celebration as seen |
| GET | `/api/user/export` | Download user_state as JSON backup |
| POST | `/api/user/import` | Import user_state (validates, overwrites) |
| GET | `/api/weekly-override/{week_start}` | Get weekly availability override |
| PUT | `/api/weekly-override/{week_start}` | Save weekly availability override |
| DELETE | `/api/weekly-override/{week_start}` | Delete weekly availability override |
| GET | `/api/free-session/surfaces` | Available surfaces + user gyms |
| GET | `/api/free-session/presets` | Presets for surface (personalized grades, phase tips) |
| POST | `/api/free-session/start` | Start a free climbing session |
| POST | `/api/free-session/{session_id}/log-climb` | Log a climb to active session |
| POST | `/api/free-session/{session_id}/finish` | Finish session (summary + load) |
| GET | `/api/free-session/history` | Free sessions for a date |
| DELETE | `/api/free-session/{session_id}/climb/{climb_index}` | Delete a climb from active session |
| DELETE | `/api/free-session/{session_id}` | Delete a free session |
| GET | `/api/custom-session/list` | List user's custom sessions (summary) |
| GET | `/api/custom-session/exercises` | Exercise catalog for builder picker (search/filter) |
| GET | `/api/custom-session/blocks` | Resolved warmup/cooldown blocks |
| GET | `/api/custom-session/{session_id}` | Get full custom session detail |
| POST | `/api/custom-session` | Create custom session |
| PUT | `/api/custom-session/{session_id}` | Update custom session |
| DELETE | `/api/custom-session/{session_id}` | Delete custom session |
| GET | `/api/body-part-picker/options` | Available body parts + equipment options for picker UI |
| POST | `/api/body-part-picker/preview` | Generate body-part session preview (no persistence) |
| POST | `/api/body-part-picker/start` | Generate body-part session + insert into week plan |
| GET | `/api/body-part-picker/estimate` | Lightweight duration estimate for live counter |
| GET | `/api/mobility/pool` | Mobility/stretching pool by body region (GATE-2 soft warnings) |
| GET | `/api/mobility/generate` | Deterministic guided stretch flow (regions + minutes + pace + rest) |
| GET | `/api/bw-progression` | A298: every bodyweight-ladder family with the athlete's level, dose of the day (`?date=`), pending promotion and last outcome; technique ladders (feet / falls). Subscription-gated |
| PUT | `/api/bw-progression/{family}` | A298: manual level change from Settings (source `user_edit`). More than one level above the current needs `confirm: true` (409 otherwise); lower-back levels are allowed only here (R12) |
| POST | `/api/bw-progression/{family}/promotion` | A298: the custom-session promotion tap — `accept` moves the level up and rewrites that family's `ladder` rows in the custom and its not-yet-played slots from `date` on; decline clears the proposal. Past / done / skipped sessions never touched |
| POST | `/api/coach/chat` | LLM Coach chat turn (subscription-gated, 30 msg/day, suggest-only; optional `lat`/`lon` → passed to the on-demand `get_weather` tool, A244). Weather is native tool use, not a pre-fetch: the model calls `get_weather(location, days_ahead≤5)` only when a turn needs conditions (language-agnostic trigger); non-weather turns pay nothing but the cached tool definition. Executor wraps `cached_conditions()`/`geocode_place()`; loop capped at 2 tool calls/message. |
| POST | `/api/coach/adhoc-session` | Compose an ad-hoc session PREVIEW from a chat turn (A243). LLM extracts a structured intent via forced tool — including `exclude`, the user's refusals (A259: 'niente trazioni' → `pullups`, which spares lock-offs). **A259**: the session is then composed by the LLM *selecting from an engine-built pool* (`coach/session_composer.py`) and validated line by line; `adhoc_builder` is the fallback on kill switch / tiny pool / provider error / failed validation. Loads always come from `working_loads`, never from the model. The payload carries `composed_by` + `dropped` for audit. No persistence/plan mutation — client persists + inserts on the "Add to today & run" CTA. `{adhoc:false}` → fall back to `/chat`. Counts toward the 30/day limit only on adhoc:true. **A297**: with `COACH_ATHLETE_CONTEXT` on, both composers read the athlete context of `target_date` — the recovery guards of that day take finger-hard / front-lever lines (and weighted pulls ≥ 85 % 1RM) out, listed in `dropped`; the payload adds `athlete_guards` + `athlete_context_version`. |
| GET | `/api/coach/history` | Coach chat history (paginated, `limit` + `before` cursor) |
| GET | `/api/coach/suggestions` | Context-aware suggested questions (deterministic, no LLM, not rate-limited) |
| GET | `/api/admin/users` | List all users (protected, X-Admin-Key) |
| DELETE | `/api/admin/users/{uuid}` | Delete a user (protected, X-Admin-Key) |
| GET | `/api/subscription/status` | Current subscription status + trial days remaining. A285 adds `enforced` (additive): `false` only while `SUBSCRIPTION_ENFORCED=0`, which is how the UI tells "active because they pay" from "active because billing is paused" — the other fields are identical in both cases |
| POST | `/api/subscription/checkout` | Create Stripe Checkout Session → returns hosted URL |
| POST | `/api/subscription/portal` | Create Stripe Customer Portal session (manage/cancel). A250: for a local trial (no Stripe customer) returns a card-collecting Checkout session instead |
| POST | `/api/stripe/webhook` | Stripe webhook receiver (signature-verified) |
| GET | `/api/weather` | Live conditions (lat/lon) or forecast-by-date; returns metrics + composite friction_score/band (prime/good/ok/poor), per-metric qualifiers, headline, best_window (A238). **A275** adds, additively: `hourly[]` (every 3h step of the day — same metrics and same friction verdict as the summary, bucketed in **crag-local** time, elapsed steps dropped on the "now" call), `sunrise`/`sunset`/`sun_date` (local `HH:MM`; OWM publishes today's sun times only, so `sun_date` names the day they belong to), `wind_dir` (16-point compass beside the existing degrees) and `timezone_offset_s`. Costs no extra upstream call — it rides the forecast fetch A238 already makes for `best_window`. The day summary still comes from the midday step and still reads UTC (`B-FORECAST-MIDDAY-STEP`); `hourly[]` is what you read when you need the truth about a given hour. `fetch_outdoor_conditions` now goes through `cached_conditions`, so it shares the 15-min cache and serves the last good reading when the provider dies with a warm cache (cold cache → `None` → catalog base, unchanged) |
