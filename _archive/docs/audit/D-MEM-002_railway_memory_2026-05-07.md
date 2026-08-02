# MEMORY_AUDIT.md — climb-agent

**Brief:** D-MEM-002
**Date:** 2026-05-07
**Mode:** Read-only audit. No source files modified, no commits.
**Repo:** climb-agent
**Question being answered:** how much of the ~$9.90/mo Railway memory bill (~990MB across two services) is consumed by climb-agent, and what is optimisable?

---

## Phase 0 — Discovery summary (one-line per artifact examined)

| Artifact | Type | Notes |
|---|---|---|
| `Procfile` | Deploy | `web: uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT` — 1 worker (no `--workers`) |
| `railway.json` | Deploy | `NIXPACKS` builder, same start command, `sleepApplication: false` |
| `requirements.txt` (root) | Deps | One line: `-r backend/requirements.txt` |
| `backend/requirements.txt` | Deps | 9 packages: `jsonschema fastapi uvicorn[standard] pytest httpx supabase PyJWT[crypto] stripe slowapi` |
| `pyproject.toml` | Project | Bare metadata + pytest config, no install deps |
| `Dockerfile` | Deploy | **Absent** — Railway uses Nixpacks default detection |
| `nixpacks.toml` | Deploy | **Absent** |
| `backend/api/main.py` | App entry | FastAPI app, eager-imports 19 routers + Stripe webhook handler. Lifespan only checks DATA_DIR writability — no data preload |
| `backend/api/deps.py` | Shared deps | `EMPTY_TEMPLATE` user-state dict, helpers, `require_active_subscription` (uses lazy import of `subscription_guard`) |
| `backend/api/auth.py` | Auth | Clerk JWT verify; `_get_jwk_client` (lru_cache=1), `_clerk_id_cache` **unbounded dict** with 5-min TTL |
| `backend/engine/storage.py` | Storage shim | Dispatches `STORAGE_BACKEND` env var → `storage_file` (dev/test) or `storage_supabase` (prod), self-replaces in `sys.modules` |
| `backend/engine/storage_supabase.py` | Storage | **Single Supabase client** created at import-time when `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` present |
| `backend/engine/planner_v2.py` (80KB) | Engine | Module-level `_SESSION_META` (~30 entries, inline Python). At import: `_validate_session_meta_equipment()` reads ~30 small JSON files (discarded after validation) |
| `backend/engine/replanner_v1.py` (74KB) | Engine | `_get_required_equipment` decorated `@lru_cache(maxsize=None)` — bounded in practice by ~30 unique session_ids |
| `backend/engine/quotes_engine.py` | Engine | `_load_quotes` lru_cache=1 — loads `quotes_catalog_v1.json` (72KB) once |
| `backend/engine/cues.py` | Engine | `_load_cues` lru_cache=1 — `process_cues.json` (12KB) |
| `backend/engine/progression_v1.py` (70KB) | Engine | Module-level `_CATALOG_CACHE`: subset of `exercises.json` (id→{load_model, unilateral}). Lazy-loaded on first call |
| `backend/engine/adaptive_replan.py` | Engine | lru_cache=1 loaders, small |
| `backend/api/routers/free_session.py` | Router | Module-level `_PRESETS_CACHE`, `_TIPS_CACHE` (lazy) |
| `backend/api/routers/body_part_picker.py` | Router | Module-level `_CATALOG_CACHE` — **full `exercises.json` loaded into list (lazy)** |
| `backend/api/routers/custom_session.py` | Router | Module-level `_EXERCISES_CACHE` — **full `exercises.json` keyed by id (lazy)** |
| `backend/api/routers/catalog.py` | Router | No module-level cache; reads JSON per-request |
| `backend/api/stripe_webhook.py` | Stripe | `import stripe` at top — pulls Stripe SDK into RAM at startup |
| `backend/catalog/` | Data | Total size 796KB, 80 JSON files. Largest: `exercises/v1/exercises.json` (392KB), `quotes/v1/quotes_catalog_v1.json` (72KB) |
| `backend/data/user_state.json` | Data | 12KB legacy single-user file (dev only) |
| `backend/data/users/*` | Data | 4 sample user_state.json files (4–28KB each) — not packaged into image (path is ephemeral on Railway, real prod uses Supabase JSONB) |
| `frontend/package.json` | Frontend | Next.js 16 PWA. Deployed to **Vercel** (per CLAUDE.md), not Railway → zero Railway memory cost |
| `.venv/` (local) | Local install | Used for site-package size estimation, NOT representative of Railway image (contains pyiceberg, hive_metastore, PIL, pip etc. that won't be installed on Railway) |
| Large data assets >50KB | Search | Only one match in repo runtime path: `backend/catalog/exercises/v1/exercises.json` (392KB). The 2.3MB `docs/audit/D215/snapshot_pre_fix.json` is a one-off audit snapshot in `docs/`, not loaded at runtime |
| Model files (`*.pkl`, `*.bin`, `*.npy`, `*.h5`, `*.pt`) | Search | **None** — confirmed no ML weights anywhere |

**Railway services from this repo:** ONE — the FastAPI backend. Frontend is on Vercel.

---

## Phase 1 — Analysis

### 1. Service shape

- **Single Railway service.** Backend-only. The Next.js PWA is on Vercel (`frontend/` directory; CLAUDE.md confirms).
- **Builder:** Nixpacks (auto-detects Python). No custom Dockerfile — image contains the full repo by default, including `frontend/`, `backend/tests/`, `docs/`, `_archive/`, `scripts/`. This is disk overhead, not memory, but it bloats deploys.
- **Start command:** `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT` (`Procfile:1` and `railway.json:6`).
- **Workers:** 1 (no `--workers` flag → uvicorn default).
- **Lifespan:** `backend/api/main.py:74-77` — only logs DATA_DIR and probes write permission. **No data preload, no model loading, no DB warm-up.**

### 2. Dependency footprint

Production install (`backend/requirements.txt`):

| Package | Disk size (local venv) | Used at runtime in prod? |
|---|---|---|
| `stripe` | **22 MB** | Yes — Stripe webhook + subscription router. Imported at startup of `stripe_webhook.py:30` and `subscription_guard.py` |
| `cryptography` | **21 MB** | Yes — pulled via `PyJWT[crypto]` for Clerk RS256 verification. Imported on first JWT verify (lazy, but inevitable) |
| `pydantic_core` | 4.4 MB | Yes — Pydantic v2 Rust core. Always loaded |
| `uvloop` | 4.3 MB | Yes — faster event loop (via `uvicorn[standard]`) |
| `pydantic` | 3.9 MB | Yes — model validation |
| `websockets` | 1.4 MB | **Not used by climb-agent** — pulled via `uvicorn[standard]`. Imported but unused |
| `fastapi` | 1.3 MB | Yes |
| `jsonschema` | 1.1 MB | Yes — log entry validation |
| `watchfiles` | 1.0 MB | **Only used in `--reload` mode** (dev). Pulled via `uvicorn[standard]`, idle in prod |
| `httpx` | 708 KB | Yes — Supabase + Stripe internal use |
| `httpcore` | 720 KB | Yes — httpx transport |
| `starlette` | 736 KB | Yes — FastAPI base |
| `uvicorn` | 692 KB | Yes |
| `h2` | 508 KB | Yes — HTTP/2 (httpx) |
| `supabase_auth` | 504 KB | Yes — supabase ecosystem |
| `httptools` | 420 KB | Yes — uvicorn parser |
| `storage3` | 300 KB | Pulled by `supabase` but **not used** (no file storage) |
| `realtime` | 240 KB | Pulled by `supabase` but **not used** |
| `postgrest` | 232 KB | Yes — supabase REST client |
| `h11` | 232 KB | Yes |
| `jwt` (PyJWT) | 264 KB | Yes — Clerk verification |
| `supabase` | 156 KB | Yes |
| `slowapi` | 132 KB | Yes — rate limiting |
| `supabase_functions` | 80 KB | Pulled by `supabase` but **not used** |

**Test-only dependency present in production install:** `pytest` is listed in `backend/requirements.txt:4`. It will be installed in the Railway image. It's not imported by app code, so it costs only **disk space** (~3MB) and a small `import sys.modules` surface — not RAM at runtime — but it pollutes the production image and increases deploy time. There is no separate `requirements-dev.txt`.

**No heavy ML/data libs:** confirmed — no torch, transformers, opencv, numpy, scipy, pandas, sklearn, faiss, sentence-transformers anywhere in the dep tree.

**Note on the local `.venv`:** `du` against the local virtualenv shows extra packages (`pyiceberg`, `hive_metastore`, `PIL`, `pip`, `pygments`) that are **not** in `backend/requirements.txt` and will NOT be installed on Railway. They're leftover from the developer's local environment. Sizes used in the table above are restricted to deps actually pulled by `backend/requirements.txt`.

### 3. Startup memory cost

Walking the import graph from `backend/api/main.py`:

1. **Line 13–37**: imports rate limiter + 19 routers + Stripe webhook handler, all eagerly. This pulls in:
   - `slowapi` + Pydantic models → light
   - All engine modules transitively (planner_v2, replanner_v1, resolve_session, progression_v1, etc.) → ~80–110MB (mostly pydantic, supabase, stripe).
   - `import stripe` (`stripe_webhook.py:30`) → ~30–50MB on import (Stripe SDK is large, eagerly loads many resource classes).
   - `supabase.create_client(...)` (`storage_supabase.py:22`) — one long-lived client; ~5–10MB once httpx and pydantic are warm.

2. **Module-level computations at import time:**
   - `planner_v2.py:134` calls `_validate_session_meta_equipment()` which **reads ~30 small JSON files** to log warnings. These are *not retained* — only used for validation. Cost: ~30 file opens at startup, no lasting memory.
   - `assessment_v1.py:19`: `_GRADE_INDEX = {g: i for i, g in enumerate(GRADE_ORDER)}` — trivial.
   - `progression_v1.py:28`: `_WHOLE_GRADE_TO_INDEX` — trivial.
   - `report_engine.py:21–49`: small grade lookup tables.
   - All other module-level constants are inline Python dicts/lists totalling <100KB.

3. **Lifespan:** `lifespan()` only logs and probes the data dir. No connection pool warm-up, no catalog preload.

**Result:** the only real startup memory cost beyond Python+FastAPI is the **eager import of `stripe`** (~30–50MB on load) and the resolution of all Pydantic models in the supabase + FastAPI stacks.

### 4. Training engine specifics

This is a **deterministic rule-based engine, not ML**. Specific findings:

- **No precomputed Markov chains, decision trees, or matrix lookups.** The engine is rules + small inline dicts.
- **JSON catalogs are small** (796KB total on disk, 80 files). The largest single file is `exercises/v1/exercises.json` (392KB).
- **Catalogs are loaded lazily** (no eager preload at import time, except the one-shot validation pass in planner_v2).
- **Catalogs are duplicated across in-memory caches:** the same `exercises.json` is loaded into THREE separate dicts — `progression_v1._CATALOG_CACHE` (subset: id→{load_model, unilateral}), `body_part_picker._CATALOG_CACHE` (full list), `custom_session._EXERCISES_CACHE` (full dict by id). After all three endpoints are exercised, ~1–2MB of duplicated state lives in RSS.
- **`_SESSION_META`** (`planner_v2.py:38`): ~30 entries × ~10 fields → a few KB. Inline Python.
- **No session/user state cached in memory**: each request loads `user_state` fresh from Supabase JSONB and writes it back. Per-request peak ~5–50KB; GC'd after response.
- **`auth._clerk_id_cache`** (`auth.py:65`): unbounded dict, 5-min TTL but no eviction. With ~few-hundred users it's negligible (<1MB), but it's a slow leak by design — entries are added on every fresh JWT lookup and only removed if accessed and stale.
- **`replanner_v1._get_required_equipment`** is `@lru_cache(maxsize=None)` (`replanner_v1.py:43`) — unbounded by decorator, but bounded in practice by the ~30 unique `session_id` keys in the catalog.

### 5. Database

- **Production:** Supabase Postgres with `STORAGE_BACKEND=supabase` (CLAUDE.md). User state stored as JSONB column. Single Supabase client instance (`storage_supabase.py:22`) created at import time. Per-request: read JSON → Python dict → handler logic → write back. No in-process mirroring.
- **Dev/test:** `STORAGE_BACKEND=file` (default) → `storage_file.py`. Not used in prod.
- **No SQLite, no in-memory DB, no in-process write buffer.** All persistence is round-trip to Supabase.
- Connection pool: managed inside the supabase-py client via httpx. Default settings (no override). Negligible memory.

This is a **clean architecture for memory** — the engine doesn't hold user state across requests.

### 6. Worker / uvicorn config

- **1 worker** (`Procfile`): no `--workers N`, no gunicorn wrapper.
- `uvicorn[standard]` provides:
   - `uvloop` event loop (~4MB)
   - `httptools` HTTP parser (~400KB)
   - `websockets` (~1.4MB) — **unused by climb-agent**
   - `watchfiles` (~1MB) — only relevant in `--reload` mode, idle in prod
- No `--limit-concurrency` or `--backlog` overrides.
- For an I/O-bound API serving a few users on a paid launch, **1 worker is correct**. Multiplying workers would multiply RSS without throughput gain.

### 7. Estimated memory breakdown

All numbers are RSS estimates for the climb-agent **backend Railway service only**.

| Component | Estimated MB | Confidence | Source |
|---|---|---|---|
| Python 3.13 interpreter + stdlib | 25–30 | High | baseline |
| FastAPI + Starlette + Pydantic v2 + pydantic_core | 90–110 | Medium-High | dep weight, pydantic v2 has C/Rust core |
| uvicorn + uvloop + httptools (+websockets/watchfiles unused) | 18–25 | Medium | dep sizes + idle async loop |
| supabase + supabase_auth + postgrest + httpx + httpcore + h11 + h2 | 25–40 | Medium | many small Pydantic models |
| Stripe SDK (eager import) | 35–50 | Medium | known large SDK, many resource classes |
| cryptography (PyJWT[crypto]) | 15–25 | Medium | C ext + key handling |
| jsonschema + slowapi + PyJWT | 8–12 | Medium-High | small but real |
| App code (engine + routers + models) | 5–10 | High | ~250KB Python source |
| Module-level catalog caches (after first use) | 2–5 | High | exercises.json × 2-3 + quotes + cues |
| Per-worker overhead × 1 | (already counted) | High | single worker |
| **Idle baseline RSS estimate** | **~220–300** | **Medium** | sum |
| Per-request peak (user_state JSON load) | +0.05–0.5 | High | 5–50KB JSON |

**Best-guess steady-state RSS:** ~**240–280 MB** for climb-agent on Railway. With ~990MB billed across two services, kilter-up plausibly accounts for the larger share (~700MB+) — confirm by cross-checking the kilter-up D-MEM-001 report.

These numbers are **estimates**, not measurements. Confirm with `memray` or Railway's own metrics dashboard before sizing decisions. If Railway exposes per-service memory, that is the authoritative number — this audit is a structural analysis of where the memory comes from.

### 8. Optimization recommendations (ranked by ROI)

| # | Recommendation | What | Est. saved | Risk | Effort |
|---|---|---|---|---|---|
| 1 | **Lazy-import `stripe`** | In `backend/api/stripe_webhook.py:30` and `backend/api/routers/subscription.py`, move `import stripe` from top-of-module into the function bodies that use it (the webhook handler and `_stripe_client()`). Same pattern is already used in `deps.py:96` for the auth import. The Stripe SDK is fat (~30–50MB on import) but only needed during webhook hits and Customer Portal redirects. | ~30–50MB until first Stripe call, then permanent after first call | Low — same lazy-import pattern already in use; subscription_guard pre-checks `STRIPE_SECRET_KEY` env var | XS |
| 2 | **Move `pytest` out of production requirements** | Split `backend/requirements.txt` into `requirements.txt` (prod) + `requirements-dev.txt` (pytest, test deps). Update CI to install both. | ~3–5MB disk, marginal RAM | Low — pure dev hygiene | XS |
| 3 | **Switch `uvicorn[standard]` → `uvicorn[standard]` minus unused extras** | The `[standard]` extra pulls `websockets` (1.4MB, unused) and `watchfiles` (1MB, only for `--reload`). Replace with explicit `uvicorn + uvloop + httptools` to drop 2.4MB on disk and a few MB of imported modules. | ~3–6MB | Low — climb-agent doesn't use websockets, doesn't run `--reload` in prod | S |
| 4 | **Deduplicate exercises.json caches** | Three modules (`progression_v1._CATALOG_CACHE`, `body_part_picker._CATALOG_CACHE`, `custom_session._EXERCISES_CACHE`) each load `exercises.json` separately. Centralize in one cache module exporting both shapes (full-list and id-keyed-dict and load-model-subset). | ~1–2MB | Low — purely refactor; tests cover both endpoints | S |
| 5 | **Bound `_clerk_id_cache`** | `backend/api/auth.py:65` uses a plain dict with no max size. Replace with `OrderedDict` + `move_to_end` + size cap (e.g. 2048), or use `cachetools.TTLCache`. | <1MB at current scale, but free protection against long-tail growth | Low | XS |
| 6 | **Lazy-import `cryptography` for JWT verify** | Already happens implicitly via PyJWT `@lru_cache` of `_get_jwk_client`, but `import jwt` at top of `auth.py` already pulls in cryptography. If JWT is rarely hit in dev (no Clerk → fallback to X-User-ID), lazy-import on first verify could save ~15MB. | ~10–15MB only if Clerk is dev-disabled — **not applicable in prod** | Low | XS but no prod gain |
| 7 | **Trim Nixpacks image** | Add a `.dockerignore` / Nixpacks configuration to exclude `frontend/`, `docs/`, `_archive/`, `backend/tests/`, `node_modules/`, `.next/`, `out/`, `reports/` from the deploy image. This is **disk + deploy speed**, not RAM, but reduces Railway image storage. | Disk only, not RAM | Low | S |
| 8 | **Profile before further cuts** | Run `memray run -o memray.bin -m uvicorn backend.api.main:app` locally, hit each endpoint, then `memray flamegraph memray.bin`. Identifies the actual hot allocators. | Information, not MB | None | M |

Items 1+2+3+4+5 are independent and additive. **Estimated combined steady-state savings: 35–60MB** (a 15–25% reduction off a ~250MB baseline) with all-low-risk changes. Item 1 alone is the biggest single win.

**Not worth doing:**
- Splitting frontend from backend deploy → already done (Vercel).
- Replacing in-memory state with Redis → there is no in-memory state to replace; user state is already in Supabase.
- Reducing worker count → already at 1.
- Lazy-loading the small JSON catalogs → already lazy.

### 9. What to do next — three concrete paths

**(a) Quick wins (1–2 hours, no functional change)**
Apply items 1, 2, 3, 5 above (lazy-import Stripe, split prod/dev requirements, drop unused uvicorn extras, bound the Clerk cache). Expected steady-state RSS drop: **~35–50 MB**, i.e. ~15% of baseline. Then redeploy and read the new RSS off the Railway metrics dashboard.

**(b) Profile first (recommended before any architectural change)**
Run `memray` locally against a representative request flow (onboarding → week generation → session resolve → feedback). climb-agent's memory profile is fairly predictable (no ML, small catalogs), so profiling is unlikely to reveal a hidden hog — but it's the only way to verify which of the estimates above are correct, and it's cheap.

**(c) Architectural — only if Railway billing remains a problem**
- Migrate the backend to a smaller-footprint host (Fly.io 256MB shared CPU, Render free tier, or a Railway "Hobby" instance if not already on it).
- Or split the Stripe webhook into its own tiny service so the main API can drop the Stripe import entirely. Likely not worth the operational cost at current scale.

---

## Critical findings

1. **`pytest` ships in the production image.** Listed in `backend/requirements.txt:4`. Doesn't run, but installs ~3MB and increases attack surface. **Fix:** split into `requirements-dev.txt`.
2. **`stripe` and `cryptography` are imported eagerly at startup** (the heaviest deps in the dep tree). Lazy-importing `stripe` is straightforward and saves ~30–50MB until the first webhook hit.
3. **`auth._clerk_id_cache` is unbounded** (`backend/api/auth.py:65`). Not a leak today — adds ~80 bytes per active user — but worth bounding before scale increases.
4. **No memory leaks observed.** The architecture is clean: stateless request handlers, all persistence in Supabase, lazy lru_cache for catalogs. The cost is structural (FastAPI + Pydantic + supabase + stripe baseline), not behavioural.

---

## Comparability with D-MEM-001 (kilter-up)

This report uses the same section structure as D-MEM-001 (Phase 0 discovery → 9-section Phase 1 → estimate table → ranked recommendations) so the two can sit side by side. The estimate-table column headers match (`Component / Estimated MB / Confidence / Source`).

Key shape differences to surface in any side-by-side comparison:
- climb-agent has **no ML, no model files, no embeddings** — all logic is rule-based with small JSON catalogs.
- climb-agent runs **1 uvicorn worker** with no gunicorn wrapper.
- climb-agent's frontend is on **Vercel**, not Railway → zero Railway frontend cost.
- climb-agent's per-request memory is bounded by Supabase round-trip (~5–50KB JSON).

If kilter-up's footprint is materially larger, the difference likely comes from one of: ML model weights held in RAM, larger persistent in-memory caches/lookups, multi-worker config, or bundled frontend.

---

## Caveat on numbers

All MB figures in this audit are **structural estimates derived from dep sizes and import patterns**, not measurements from `ps`/`memray`/Railway. To convert estimates into a verified number:

```bash
# Local measurement
memray run -o /tmp/climb.bin -m uvicorn backend.api.main:app
# In another terminal, hit a few endpoints (curl /health, curl /api/state with X-User-ID, etc.)
# Stop the server, then:
memray stats /tmp/climb.bin
memray flamegraph /tmp/climb.bin

# Production measurement
# Read Railway dashboard → climb-agent service → Memory metric.
```

Daniele should treat the breakdown table as a structural map of where the memory goes, and the Railway dashboard / memray output as the authoritative size.
