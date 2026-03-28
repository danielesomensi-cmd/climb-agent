# D164 — Backend Code Audit

**Scope:** `backend/api/`, `backend/data/`, `backend/engine/equipment_utils.py`, `backend/engine/cluster_utils.py`, `backend/engine/storage_file.py`, `backend/engine/storage_supabase.py`

**Date:** 2026-03-27
**Auditor:** Claude (automated)

---

## Summary

The backend is well-structured with consistent patterns across all 16 routers. Auth flows through Clerk JWT + X-User-ID fallback, admin endpoints are gated behind `ADMIN_SECRET`, and a global exception handler prevents stack trace leaks. The main concerns are: (1) non-atomic file writes that risk state corruption on crash, (2) duplicated `_auto_resolve` logic across two routers, (3) error messages that expose internal details (exception strings) to clients, and (4) no rate limiting on any endpoint.

**Overall risk assessment:** No P1 blockers found. Several P2 items should be addressed before wider rollout.

---

## P1 — Blocks Launch

None found.

---

## P2 — Fix Soon

### P2-01: File-based state writes are not atomic (storage_file.py:59-66)
`write_state()` calls `path.write_text()` directly. If the process crashes mid-write (OOM, deploy, power loss), `user_state.json` is left truncated/corrupt. `read_state()` catches `JSONDecodeError` and returns `None`, which means `load_state()` in `deps.py` returns an empty template — the user loses all data silently.

**Fix:** Write to a temp file in the same directory, then `os.replace()` (atomic on POSIX). Same pattern for `save_recovery_codes()` and `remove_outdoor_log_by_date()` (lines 262-266 rewrite in-place).

**Affected:** `storage_file.write_state`, `storage_file.save_recovery_codes`, `storage_file.remove_outdoor_log_by_date`

### P2-02: Error messages leak internal exception details to clients
Multiple endpoints expose raw Python exception strings via `detail=f"... failed: {e}"`. Examples:
- `week.py:353` — `"Week generation failed: {e}"` (can expose file paths, import errors, engine internals)
- `session.py:76` — `"Session resolution failed: {e}"`
- `feedback.py:34` — `"Feedback application failed: {e}"`
- `replanner.py:176,214,260,304` — Override/suggestion/quick-add/events failure messages
- `macrocycle.py:87` — `"Macrocycle generation failed: {e}"`
- `assessment.py:31` — `"Assessment computation failed: {e}"`
- `outdoor.py:96,103` — Exposes file paths in `"Failed to write outdoor log: {e}"` and `"file not found at {log_path}"`

The global exception handler at `main.py:87-93` correctly returns a generic message, but these explicit `HTTPException` raises bypass it.

**Fix:** Log the full exception server-side, return a generic user-facing message. Keep specific messages only for 4xx validation errors.

### P2-03: `deps.py:103` leaks auth exception details
```python
raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
```
PyJWT exceptions can include token fragments, key details, or algorithm info. This should return a generic "Invalid or expired token" message.

### P2-04: No rate limiting on any endpoint
No middleware or dependency for rate limiting. Public endpoints (`/api/user/recover`, `/health`, `/api/onboarding/defaults`) and write-heavy endpoints (`/api/feedback`, `/api/free-session/*/log-climb`) are all unthrottled.

**Risk:** A malicious user could enumerate recovery codes (brute-force CLIMB-XXXX-XXXX, 32^8 space is large but still no throttle), or spam expensive endpoints (week generation, macrocycle generation) causing CPU/DB exhaustion.

**Fix:** Add a rate-limiting middleware (e.g., `slowapi` or a simple token-bucket per IP/user_id). Priority targets: `/api/user/recover`, `/api/macrocycle/generate`, `/api/week/{week_num}`.

### P2-05: Recovery code generation uses `random` instead of `secrets`
`user.py:35` uses `random.choices()` for generating recovery codes. The `random` module is not cryptographically secure — its state can be predicted if other random outputs are observable.

**Fix:** Replace with `secrets.choice()`.

### P2-06: Duplicated `_auto_resolve` function (week.py + replanner.py)
`_auto_resolve` is implemented twice with nearly identical logic: `week.py:38-101` and `replanner.py:96-141`. The week.py version accepts an extra `phase` parameter; otherwise they are copy-paste identical. Divergence risk is high — a bug fix in one may miss the other.

**Fix:** Extract to a shared utility in `deps.py` or a new `backend/api/resolve_utils.py`.

### P2-07: `save_recovery_codes` in Supabase is destructive (storage_supabase.py:276-291)
The Supabase implementation does a DELETE-all then INSERT-all for every code save. This is not transactional — if the process crashes between DELETE and INSERT, all recovery codes are lost. Also, this scales poorly as the number of codes grows.

**Fix:** Use upsert for the new code only. The current "save all codes" pattern is inherited from the file backend and does not suit a relational store.

### P2-08: `PUT /api/state` accepts arbitrary keys via deep merge
`StatePatch` uses `model_config = {"extra": "allow"}`, and `_deep_merge` writes any key into state without validation. A client can inject arbitrary top-level keys (e.g., `"_prev_week_plan"`, `"initial_tests_requested"`, `"test_reminder_skipped_until"`) to manipulate engine behavior, bypass test reminders, or corrupt internal bookkeeping.

**Fix:** Whitelist allowed top-level keys for the state patch, or at minimum reject keys starting with `_`.

### P2-09: `POST /api/feedback` returns full state in response
`feedback.py:142` returns `{"status": "ok", "state": state}` which includes the entire user state. This is a large payload (can be 100KB+) and exposes all internal bookkeeping fields (`_prev_week_plan`, `feedback_log`, `working_loads`, etc.) to the client.

**Fix:** Return only the fields the frontend needs (e.g., `status`, `limitation_suggestions`, maybe updated `working_loads` summary).

---

## P3 — Backlog

### P3-01: `health` endpoint exposes `data_dir` path (main.py:147-154)
The `/health` response includes `"data_dir": data_dir` which reveals the server filesystem layout (e.g., `/data/climb-agent` or `/app/backend/data`). Minor info leak.

**Fix:** Remove `data_dir` from the health response, or restrict it behind admin auth.

### P3-02: No input validation on date format parameters
Several endpoints accept date strings (e.g., `req.date`, `target_date`, `week_start`) but never validate they are valid `YYYY-MM-DD`. Invalid dates will propagate into state and potentially cause `strptime` crashes deeper in the engine.

**Affected:** `AddExerciseRequest.date`, `RemoveExerciseRequest.date`, `OverrideRequest.reference_date`, `QuickAddRequest.target_date`, `OutdoorSessionLog.date`, `FreeSessionStartRequest.date`, `ConvertSlotRequest.date`, `GET /api/outdoor/log/{date}`, `GET /api/reports/weekly?week_start=...`

**Fix:** Add a Pydantic validator on all date fields: `@validator('date') ... datetime.strptime(v, '%Y-%m-%d')`.

### P3-03: `_PRESETS_CACHE` and `_TIPS_CACHE` are module-level globals (free_session.py:39-58)
These caches are never invalidated. If the JSON files are updated at runtime (hot-reload scenario), stale data is served. Minor issue since catalog changes require a redeploy, but could cause confusion during development.

### P3-04: `weekly_override.py:78` uses deprecated `datetime.utcnow()`
```python
"created_at": datetime.utcnow().isoformat() + "Z",
```
`datetime.utcnow()` is deprecated in Python 3.12+. Use `datetime.now(timezone.utc)` (already used elsewhere in the codebase).

### P3-05: `PUT /api/state` does not validate `patch` body type
The endpoint signature is `patch: Dict[str, Any]` — FastAPI will accept any JSON object. No Pydantic model constrains the shape. Combined with P2-08 (arbitrary keys), this makes the endpoint very permissive. Lower priority than P2-08 since auth is required.

### P3-06: No request body size limit
FastAPI/Starlette has no default body size limit. A user could POST a very large JSON body to any endpoint (e.g., `PUT /api/state` with megabytes of data) and the server will parse it all into memory.

**Fix:** Add `RequestSizeLimitMiddleware` or similar.

### P3-07: `convert_outdoor_slot` calls `suggest_sessions` with wrong signature
`outdoor.py:182-185` calls `suggest_sessions(user_state=state, ...)` but looking at the import, `suggest_sessions` from `replanner_v1` expects `(week_plan, target_date, location, ...)`. This may fail at runtime when the code path is exercised. Needs verification.

### P3-08: Supabase client initialized at module import time (storage_supabase.py:22)
```python
_client = create_client(_url, _key) if _url and _key else None
```
If `STORAGE_BACKEND=supabase` but env vars are missing, the client is `None` and every operation will raise `RuntimeError` at request time. The error is clear but initialization should be deferred or fail-fast at startup.

### P3-09: `requirements.txt` has no version pins
All dependencies are unpinned: `fastapi`, `uvicorn[standard]`, `supabase`, `PyJWT[crypto]`, etc. A `pip install` could pull breaking changes at any time.

**Fix:** Pin major versions at minimum (e.g., `fastapi>=0.115,<1.0`). Better: use a lockfile.

### P3-10: No logging in most router endpoints
Only `week.py` and `main.py` have `logger` instances. Most routers have no logging at all — errors are caught and converted to HTTPException without being logged first. The global exception handler at `main.py:90` logs unhandled exceptions, but explicitly caught ones (most 500s in the routers) are not logged.

**Fix:** Add `logger.exception()` or `logger.error()` before every `raise HTTPException(status_code=500, ...)`.

### P3-11: `_auto_resolve` does `deepcopy(state)` per session (week.py:78, replanner.py:123)
For a week with 4-5 sessions, this creates 4-5 full deep copies of the entire user state. State can be large (100KB+). This is a performance concern for response latency.

**Fix:** Create a single stripped-down resolve context outside the loop, deep-copy only the mutable parts that `resolve_session` modifies.

### P3-12: Admin `_scan_users` loads every user's state (admin.py:80-97)
`list_users` reads and parses the full state for every user to extract summary fields. With many users on the Supabase backend, this is N queries with full JSONB deserialization.

**Fix:** Create a materialized view or summary table, or use a Supabase RPC that extracts summary fields server-side.

### P3-13: `catalog.py` reads and parses all session JSON files on every request
`list_sessions()` iterates over all files in `SESSIONS_DIR`, parsing each one. This is called on every `/api/catalog/sessions` request with no caching.

**Fix:** Cache the result (static catalog data changes only on deploy).

### P3-14: `equipment_utils.py` and `cluster_utils.py` are clean utility modules
No issues found. Both are small, well-documented, and have no side effects. `cluster_utils.parse_date` gracefully handles None and invalid inputs.

---

## Security Checklist

| Check | Status | Notes |
|-------|--------|-------|
| Admin endpoints require X-Admin-Key | PASS | Both `/api/admin/users` and `/api/admin/users/{uuid}` call `_require_admin()` |
| Empty ADMIN_SECRET rejects all requests | PASS | `if not secret or key != secret` — empty string fails `not secret` |
| CORS restricted to known origins | PASS | Only `localhost:3000` and `climb-agent.vercel.app` |
| Global exception handler prevents stack traces | PASS | `main.py:87-93` catches `Exception` and returns generic message |
| Clerk JWT verified with JWKS | PASS | `auth.py:48-56` uses PyJWKClient for signature verification |
| No hardcoded secrets in code | PASS | All secrets via env vars |
| File writes create parent directories | PASS | `mkdir(parents=True, exist_ok=True)` in storage_file |
| Supabase writes require authenticated user_id | PASS | `_require_user_id()` prevents writes to `__legacy__` bucket |

---

## Dependency Health (requirements.txt)

| Package | Pinned? | Notes |
|---------|---------|-------|
| jsonschema | No | Used for schema validation |
| fastapi | No | Core framework |
| uvicorn[standard] | No | ASGI server |
| pytest | No | Test-only, not a prod concern |
| httpx | No | Test client, not a prod concern |
| supabase | No | DB client |
| PyJWT[crypto] | No | JWT verification |

**Verdict:** No known CVEs at time of audit for these packages at latest versions, but unpinned deps are a supply chain risk (P3-09).
