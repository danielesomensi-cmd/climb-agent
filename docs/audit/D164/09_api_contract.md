# D164/09 — API Contract Consistency Audit

**Date:** 2026-03-27
**Scope:** `backend/api/routers/*.py`, `backend/api/main.py`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`
**Auditor:** Claude (automated)

---

## 1. Endpoint Map

| # | Method | Path | Backend Router | Frontend Caller | Notes |
|---|--------|------|----------------|-----------------|-------|
| 1 | GET | `/health` | `main.py` (app-level) | -- | Not called by FE; infra-only |
| 2 | GET | `/api/state` | `state.router` | `getState()` | OK |
| 3 | PUT | `/api/state` | `state.router` | `putState()` | OK |
| 4 | GET | `/api/state/status` | `state.router` | `getStateStatus()` | OK |
| 5 | DELETE | `/api/state` | `state.router` | `deleteState()` | OK |
| 6 | GET | `/api/catalog/exercises` | `catalog.router` | `getExercises()` | OK |
| 7 | GET | `/api/catalog/sessions` | `catalog.router` | `getSessions()` | OK |
| 8 | GET | `/api/onboarding/defaults` | `onboarding.router` | `getOnboardingDefaults()` | OK |
| 9 | POST | `/api/onboarding/complete` | `onboarding.router` | `completeOnboarding()` | OK |
| 10 | POST | `/api/onboarding/start-week` | `onboarding.router` | `setStartWeek()` | OK |
| 11 | POST | `/api/assessment/compute` | `assessment.router` | `computeAssessment()` | OK |
| 12 | POST | `/api/macrocycle/generate` | `macrocycle.router` | `generateMacrocycle()` | OK |
| 13 | GET | `/api/week/{week_num}` | `week.router` | `getWeek()` | OK |
| 14 | POST | `/api/week/test-reminder-response` | `week.router` | -- | **No FE caller** (see F1) |
| 15 | POST | `/api/session/resolve` | `session.router` | `resolveSession()` | OK |
| 16 | POST | `/api/session/add-exercise` | `session.router` | `addExerciseToSession()` | OK |
| 17 | POST | `/api/session/remove-exercise` | `session.router` | `removeExerciseFromSession()` | OK |
| 18 | POST | `/api/replanner/override` | `replanner.router` | `applyOverride()` | OK |
| 19 | POST | `/api/replanner/events` | `replanner.router` | `applyEvents()` | OK |
| 20 | GET | `/api/replanner/suggest-sessions` | `replanner.router` | `getSuggestedSessions()` | OK |
| 21 | POST | `/api/replanner/quick-add` | `replanner.router` | `quickAddSession()` | OK |
| 22 | POST | `/api/feedback` | `feedback.router` | `postFeedback()` | OK (see F2) |
| 23 | GET | `/api/outdoor/spots` | `outdoor.router` | `getOutdoorSpots()` | OK |
| 24 | POST | `/api/outdoor/spots` | `outdoor.router` | `addOutdoorSpot()` | OK |
| 25 | DELETE | `/api/outdoor/spots/{spot_id}` | `outdoor.router` | `deleteOutdoorSpot()` | OK |
| 26 | POST | `/api/outdoor/log` | `outdoor.router` | `postOutdoorLog()` | OK |
| 27 | GET | `/api/outdoor/log/{date}` | `outdoor.router` | `getOutdoorLogByDate()` | OK |
| 28 | PUT | `/api/outdoor/log` | `outdoor.router` | `putOutdoorLog()` | OK |
| 29 | GET | `/api/outdoor/sessions` | `outdoor.router` | `getOutdoorSessions()` | OK |
| 30 | GET | `/api/outdoor/stats` | `outdoor.router` | `getOutdoorStats()` | OK |
| 31 | POST | `/api/outdoor/convert-slot` | `outdoor.router` | `convertOutdoorSlot()` | **Response mismatch** (see F3) |
| 32 | GET | `/api/reports/weekly` | `reports.router` | `getWeeklyReport()` | OK |
| 33 | GET | `/api/reports/monthly` | `reports.router` | `getMonthlyReport()` | OK |
| 34 | GET | `/api/quotes/daily` | `quotes.router` | `getDailyQuote()` | OK |
| 35 | GET | `/api/user/export` | `user.router` | `exportUserState()` | OK (custom fetch) |
| 36 | POST | `/api/user/import` | `user.router` | `importUserState()` | OK |
| 37 | POST | `/api/user/recovery-code` | `user.router` | -- | **No FE caller** (legacy, OK) |
| 38 | POST | `/api/user/recover` | `user.router` | -- | **No FE caller** (legacy, OK) |
| 39 | GET | `/api/weekly-override/{week_start}` | `weekly_override.router` | `getWeeklyOverride()` | OK |
| 40 | PUT | `/api/weekly-override/{week_start}` | `weekly_override.router` | `putWeeklyOverride()` | OK |
| 41 | DELETE | `/api/weekly-override/{week_start}` | `weekly_override.router` | `deleteWeeklyOverride()` | OK |
| 42 | GET | `/api/free-session/surfaces` | `free_session.router` | `getFreeSessionSurfaces()` | OK |
| 43 | GET | `/api/free-session/presets` | `free_session.router` | `getFreeSessionPresets()` | OK |
| 44 | POST | `/api/free-session/start` | `free_session.router` | `startFreeSession()` | OK |
| 45 | POST | `/api/free-session/{session_id}/log-climb` | `free_session.router` | `logFreeClimb()` | OK |
| 46 | POST | `/api/free-session/{session_id}/finish` | `free_session.router` | `finishFreeSession()` | OK |
| 47 | GET | `/api/free-session/history` | `free_session.router` | `getFreeSessionHistory()` | OK |
| 48 | DELETE | `/api/free-session/{session_id}` | `free_session.router` | `deleteFreeSession()` | OK |
| 49 | GET | `/api/admin/users` | `admin.router` | -- | Admin-only, correct |
| 50 | DELETE | `/api/admin/users/{uuid}` | `admin.router` | -- | Admin-only, correct |

**Totals:** 50 endpoints (49 router + 1 app-level health). 44 called by frontend. 6 not called: health (infra), test-reminder-response (see F1), recovery-code (legacy), recover (legacy), admin/users GET, admin/users DELETE (admin-only). No frontend calls to non-existent backend endpoints.

---

## 2. Findings

### F1 — POST `/api/week/test-reminder-response` has no frontend caller
**Severity: P3**

The backend exposes `POST /api/week/test-reminder-response` (accepts `{option: "confirm"|"postpone_1_week"|"skip_cycle"}`), but there is no corresponding function in `api.ts` and no grep match for `test-reminder` or `testReminder` anywhere in `frontend/src/`. The `GET /api/week/{week_num}` response conditionally includes a `test_reminder` field, but the frontend never renders it or calls the response endpoint.

**Impact:** Feature is backend-complete but frontend-incomplete. Users never see test reminders.

---

### F2 — POST `/api/feedback` response includes extra `limitation_suggestions` field
**Severity: P3**

Backend returns `{status, state, limitation_suggestions?}` when limitation suggestions are generated. The frontend types the response as `{status: string; state: UserState}` and does not declare or consume `limitation_suggestions`. This is harmless (extra fields are ignored by TS), but the feature is silently unused.

**Impact:** Limitation severity upgrade suggestions are never shown to the user.

---

### F3 — POST `/api/outdoor/convert-slot` response shape mismatch
**Severity: P2**

- **Frontend expects:** `{status: string; suggestions: Array<Record<string, unknown>>}`
- **Backend returns:** `{date: string; new_location: string; suggestions: [...]}`

The backend does NOT return a `status` field. The frontend wrapping type expects `status` which will be `undefined`. Additionally, the backend returns `date` and `new_location` which the frontend does not type.

**Impact:** Frontend code checking `response.status` would get `undefined`. Functional impact depends on whether any component actually reads the `status` field after calling `convertOutdoorSlot()`.

---

### F4 — POST `/api/user/import` response shape inconsistency
**Severity: P3**

- **Frontend expects:** `{status: string}`
- **Backend returns:** `{status: "imported"}`

These align, but note the backend returns `"imported"` while `deleteState` returns `"reset"` and other endpoints return `"ok"`. Minor inconsistency in status string values across the API.

---

### F5 — GET `/api/week/{week_num}` response has undeclared `test_reminder` field
**Severity: P3**

Frontend types the response as `{week_num: number; phase_id: string; week_plan: WeekPlan}`. The backend conditionally adds a `test_reminder` key. The frontend never reads it (see F1). Not a runtime error since TS ignores extra keys at runtime, but the type is technically incomplete.

---

### F6 — Recovery code endpoints are dead code (backend)
**Severity: P3**

`POST /api/user/recovery-code` and `POST /api/user/recover` exist in the backend but are not called by the frontend. The comment in `api.ts` line 311 says: "Recovery code functions removed -- Clerk handles account recovery." These endpoints are dead code on the backend.

**Impact:** No runtime impact. Code bloat only. Could be removed in a cleanup pass.

---

## 3. Type Alignment

### 3.1 Request Bodies

| Endpoint | Frontend sends | Backend expects (Pydantic) | Status |
|----------|---------------|---------------------------|--------|
| PUT `/api/state` | `Record<string, unknown>` | `Dict[str, Any]` | OK |
| POST `/api/onboarding/complete` | `OnboardingData` | `OnboardingData` (Pydantic `Dict` fields) | OK (FE sends superset, Pydantic accepts) |
| POST `/api/onboarding/start-week` | `{offset_weeks}` | `StartWeekRequest({offset_weeks: int})` | OK |
| POST `/api/assessment/compute` | `{assessment?, goal?}` | `AssessmentRequest({assessment, goal})` | OK (defaults to empty dict) |
| POST `/api/macrocycle/generate` | `{start_date?, total_weeks?, from_phase?}` | `MacrocycleRequest` | OK |
| POST `/api/session/resolve` | `{session_id, context?}` | `SessionResolveRequest` | OK |
| POST `/api/session/add-exercise` | `{date, session_index, exercise_id, prescription_override?, week_plan}` | `AddExerciseRequest` | OK |
| POST `/api/session/remove-exercise` | `{date, session_index, exercise_index, week_plan}` | `RemoveExerciseRequest` | OK |
| POST `/api/replanner/override` | `{intent, location, reference_date, slot?, phase_id?, week_plan, target_date?, gym_id?, session_index?}` | `OverrideRequest` | OK |
| POST `/api/replanner/events` | `{events, week_plan}` | `EventsRequest` | OK |
| POST `/api/replanner/quick-add` | `{session_id, target_date, slot?, location?, phase_id?, week_plan, gym_id?}` | `QuickAddRequest` | OK |
| POST `/api/feedback` | `{log_entry, resolved_day?, status?}` | `FeedbackRequest` | OK |
| POST `/api/outdoor/spots` | `{id?, name, discipline, typical_days?, notes?}` | `OutdoorSpotCreate` | OK |
| POST `/api/outdoor/log` | `Omit<OutdoorSession, "log_version">` | `OutdoorSessionLog` | OK |
| PUT `/api/outdoor/log` | `Omit<OutdoorSession, "log_version">` | `OutdoorSessionLog` | OK |
| POST `/api/outdoor/convert-slot` | `{date, new_location, gym_id?}` | `ConvertSlotRequest` | OK |
| POST `/api/user/import` | `Record<string, unknown>` | `Dict[str, Any]` | OK |
| PUT `/api/weekly-override/{week_start}` | `{days: {...}}` | `WeeklyOverridePayload` | OK |
| POST `/api/free-session/start` | `{date, surface, gym_name?, session_mode, preset_id?, context}` | `FreeSessionStartRequest` | OK |
| POST `/api/free-session/{id}/log-climb` | `{grade, status, attempts, style?, topped?, notes?}` | `FreeSessionLogClimbRequest` | OK |
| POST `/api/free-session/{id}/finish` | `{overall_feel?, notes?, circuit?}` | `FreeSessionFinishRequest` | OK |

### 3.2 Response Shapes

All response shapes match between frontend TypeScript types and backend return values, **except** the findings noted above (F2, F3, F5).

### 3.3 Enum Values

No explicit enum mismatches detected. Key enums are:
- Session status: `"planned" | "done" | "skipped"` — consistent FE/BE
- Disciplines: `"lead" | "boulder" | "both"` — consistent
- Slots: `"morning" | "lunch" | "evening"` — consistent
- Locations: `"gym" | "home" | "outdoor"` — consistent
- Free session modes: `"template" | "free"` in FE, backend also accepts `"circuit"` (FE sends it correctly from guided session code)

---

## 4. Error Handling Contract

### 4.1 Backend Error Shape

The backend uses FastAPI's `HTTPException` consistently, which produces `{"detail": "..."}` responses. The global exception handler in `main.py` catches unhandled exceptions and returns `{"detail": "Internal server error"}` with status 500.

**Status codes used across all routers:**
- `400` — Invalid input (bad enum values, missing fields)
- `401` — Authentication required (outdoor log without user_id)
- `403` — Admin endpoints (wrong/missing X-Admin-Key)
- `404` — Resource not found (session, spot, date, user)
- `409` — Conflict (immutable session modification, duplicate spot)
- `422` — Validation/precondition failure (no macrocycle, no assessment)
- `500` — Internal errors (generation failure, I/O)

All errors use the `detail` field consistently.

### 4.2 Frontend Error Handling

The `request<T>()` function in `api.ts`:
1. On **401**: retries once after 500ms (B155), then redirects to `/sign-in`
2. On **any non-ok**: reads `res.text()` and throws `Error(`API ${status}: ${body}`)`

The frontend does NOT parse the `detail` field from JSON error bodies. It reads the raw text. This means error messages displayed to users may include raw JSON like `{"detail":"No macrocycle -- generate one first"}` rather than just the human-readable message.

**Verdict:** Functional but not user-friendly for error display.

---

## 5. Auth Contract

### 5.1 Clerk Token

The `_getAuthHeaders()` function in `api.ts` attempts to get a Clerk session token via `window.Clerk?.session?.getToken()` and sends it as `Authorization: Bearer <token>`. This is called on **every** request via the `request<T>()` helper. The `exportUserState()` function also calls `_getAuthHeaders()` directly.

All frontend API calls go through `request<T>()` or the custom `exportUserState()` fetch, so auth headers are consistently applied.

### 5.2 Admin Endpoints

Admin endpoints (`/api/admin/users`, `/api/admin/users/{uuid}`) use `X-Admin-Key` header checked against `ADMIN_SECRET` env var. They do NOT use `Depends(get_user_id)` (i.e., no Clerk auth). The frontend has no code calling these endpoints, which is correct.

### 5.3 Recovery Endpoints

`POST /api/user/recover` is a public endpoint (no auth required, by design). `POST /api/user/recovery-code` requires `user_id` via the standard `Depends(get_user_id)`. Both are legacy/dead code.

---

## 6. URL Consistency

### 6.1 Base URL

`api.ts` line 19: `const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";`

- Production: env var set to Railway URL. Correct.
- Development: falls back to `localhost:8000`. Correct.
- No hardcoded localhost URLs anywhere else in `frontend/src/`.

### 6.2 Path Construction

All paths use string interpolation against `API_BASE`. No double-slash issues detected. Query parameter construction uses `URLSearchParams` (in `getWeek`) or direct string concatenation (in other calls). Both approaches are correct.

---

## 7. Summary

| ID | Severity | Description |
|----|----------|-------------|
| F1 | P3 | `POST /api/week/test-reminder-response` has no frontend caller — feature incomplete |
| F2 | P3 | `POST /api/feedback` returns optional `limitation_suggestions` — frontend ignores |
| F3 | P2 | `POST /api/outdoor/convert-slot` response shape mismatch — FE expects `status`, BE returns `date`+`new_location` |
| F4 | P3 | Status string inconsistency (`"imported"` vs `"ok"` vs `"reset"`) across endpoints |
| F5 | P3 | `GET /api/week/{week_num}` conditionally includes `test_reminder` — FE type incomplete |
| F6 | P3 | Recovery code endpoints are dead code — Clerk handles auth now |

**Overall assessment:** The API contract is in good shape. 44 of 50 endpoints have matching frontend callers; the 6 uncalled endpoints are admin-only, infra-only, or legacy. Request body shapes align across all endpoints. The only actionable finding is **F3** (P2) where the convert-slot response shape genuinely mismatches. All other findings are P3 completeness/cleanup items.
