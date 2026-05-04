# AUTH_AUDIT.md — climb-agent authentication system

**Audit date:** 2026-04-23
**Mode:** read-only.
**Repo:** `~/Projects/climb-agent` @ branch `main`, commit `afdd45e`.

This document is sufficient for a separate project (Kilter-Up) to decide whether
to copy the approach, reimplement the same pattern, or keep its own stack.

---

## 1. Stack Overview

- **Auth provider:** **Clerk** (hosted). Frontend uses the official Next.js SDK;
  backend verifies Clerk-issued JWTs directly against Clerk's JWKS.
  - Frontend proof: `frontend/package.json` → `"@clerk/nextjs": "^7.0.4"`.
  - Backend proof: `backend/requirements.txt` → `PyJWT[crypto]`, and
    `backend/api/auth.py` uses `jwt.PyJWKClient(CLERK_JWKS_URL)` to verify RS256.
  - No password hashing, no email-confirmation code, no session cookies issued
    by the app. Clerk is the sole identity provider.

- **Where user records live:** **hybrid**.
  - Clerk owns the identity (email, password, OAuth, sessions, MFA, user
    metadata) inside its hosted service.
  - The app keeps a thin shadow row in its own Supabase Postgres `users` table,
    linked by `clerk_id`. The shadow row holds an app-generated UUID
    (`user_id`) + the full `state` JSONB blob (onboarding, macrocycle, logs).

- **Token / session storage:** Clerk's JS runtime manages session storage
  (httpOnly cookies under the Clerk domain + an in-memory JS session object).
  The app never reads or writes auth cookies directly. On every API call the
  frontend calls `window.Clerk?.session?.getToken()` which returns a short-lived
  JWT that is sent as `Authorization: Bearer <jwt>` (see `frontend/src/lib/api.ts:26-35`).
  There is no localStorage/sessionStorage involvement by app code.

- **Environment variables the auth system depends on** (names only, values
  never exposed):
  - Backend (`.env` in repo root, gitignored):
    - `CLERK_SECRET_KEY` — optional server-to-Clerk REST calls; **not**
      currently required by the auth path (backend only verifies JWT).
    - `CLERK_JWKS_URL` — optional in code but required in production. When
      unset, `is_clerk_configured()` returns False and the backend falls back
      to the `X-User-ID` dev header. The live Railway deployment has it set.
    - `ADMIN_SECRET` — unrelated to end-user auth; guards
      `/api/admin/*` via `X-Admin-Key` header.
    - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — used for the shadow users table.
    - `STORAGE_BACKEND` — `file` in pytest/dev, `supabase` in prod.
    - `BYPASS_USER_IDS` — comma-separated UUIDs that skip the
      subscription guard (founder + beta). Auth still required; this only
      bypasses paywall.
  - Frontend (`frontend/.env.local`, gitignored; shape shown in
    `frontend/.env.example`):
    - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
    - `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`
    - `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`
    - `NEXT_PUBLIC_API_URL` — pointer to the backend.

---

## 2. User Model / Schema

The canonical schema for the shadow `users` table is not in a committed SQL
migration; it was applied directly in Supabase. It can be reconstructed from
code references and a committed audit script.

### `public.users` (Supabase Postgres)

Columns observed at runtime (source: `docs/audit/D-ANALYTICS-DROPOFF_output.md:13-18`,
plus writes/reads in `backend/api/auth.py:82-94` and
`backend/engine/storage_supabase.py:79-94`):

| Column      | Type        | Notes                                           |
|-------------|-------------|-------------------------------------------------|
| `user_id`   | UUID (text) | Primary key. App-generated via `uuid.uuid4()`.  |
| `clerk_id`  | TEXT        | Clerk `sub` claim (e.g. `user_2a...`). Indexed implicitly by `.eq("clerk_id", …)`. |
| `state`     | JSONB       | Full user state (onboarding, macrocycle, logs). |
| `created_at`| TIMESTAMPTZ | Default now().                                  |
| `updated_at`| TIMESTAMPTZ | Auto-updated; read by `user_state_mtime()`.     |

No `email`, `name`, `password_hash` columns — those live in Clerk. Email is
fetched from Clerk at runtime (`frontend/src/app/(main)/subscribe/page.tsx:30`
uses `user?.primaryEmailAddress?.emailAddress` for Stripe prefill). A separate
`docs/audit/D-ANALYTICS-DROPOFF_output.md` shows the live row count was 9 users
on 2026-04-17.

### Adjacent tables (used by auth flow context, not storing identity)

- `subscriptions` — one-to-one with `users.user_id`, schema in
  `docs/migrations/subscriptions_table.sql`. Includes `cancel_at_period_end`,
  `status`, `stripe_customer_id`, `stripe_subscription_id`, `trial_start`,
  `trial_end`, etc.
- `session_logs`, `outdoor_logs`, `event_logs`, `recovery_codes` — keyed by
  `user_id`. Not identity data.

### Row-Level Security

Per `CLAUDE.md:300` and the confirmation in `docs/ROADMAP_v2.md:904`:

> RLS enabled on all 6 tables (2026-04-03). No policies — anon key blocked,
> service role key bypasses RLS.

Meaning: RLS is a defensive lid, but the backend holds the service role key
(`SUPABASE_SERVICE_KEY`) and every read/write goes through FastAPI with the
Clerk-derived `user_id` as an explicit `.eq("user_id", uid)` filter. **No RLS
policy SQL exists to quote** — access control is implemented in Python, not in
Postgres.

### Recovery codes (legacy)

`recovery_codes` table persists `CLIMB-XXXX-XXXX` codes, mapped to a UUID. Code
for this lives in `backend/api/routers/user.py:122-169`. The frontend is
explicitly marked as deprecated: `frontend/src/lib/api.ts:335` — `// Recovery
code functions removed — Clerk handles account recovery`. Dead code on the
frontend, still-reachable endpoints on the backend.

---

## 3. Registration Flow

- **Frontend entry point:** `frontend/src/app/sign-up/[[...sign-up]]/page.tsx`.
  Entire page body:
  ```tsx
  import { SignUp } from "@clerk/nextjs";
  export default function SignUpPage() {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <SignUp />
      </div>
    );
  }
  ```
  Everything (email capture, password validation, email verification, OAuth
  buttons, error states, localization) is handled by Clerk's `<SignUp />`
  component. The app has no custom registration code.

- **API route / SDK call:** none on the app side. Clerk's component posts
  directly to Clerk's API.

- **Backend handler on signup:** there is **no signup webhook**. The first time
  the new user hits any authenticated backend endpoint, `lookup_or_create_user`
  (`backend/api/auth.py:69-97`) queries the shadow `users` table by `clerk_id`
  and inserts a new row with `user_id = uuid4()`, `clerk_id`, `state = {}` if
  missing. Result is cached in-process for 5 minutes
  (`_CACHE_TTL = 300`).

- **Email verification:** handled entirely by Clerk (email code or magic link
  per Clerk dashboard settings — not visible from the repo).

- **What is written to the database:** one row in `public.users`:
  `{ user_id: <new UUID>, clerk_id: <Clerk sub>, state: {} }`.

- **What the client receives:** Clerk session (cookie + JS object) after
  `<SignUp />` completes. The app's root page (`frontend/src/app/page.tsx`)
  then redirects to `/onboarding/welcome` if `state.macrocycle` is missing.

- **Error handling:** all surfaced by Clerk's component. App code only handles
  "API 401" by retrying once after 500 ms then redirecting to `/sign-in`
  (`frontend/src/lib/api.ts:48-57`, labeled B155).

---

## 4. Login Flow

- **Frontend entry point:** `frontend/src/app/sign-in/[[...sign-in]]/page.tsx`
  — a one-line wrapper around Clerk's `<SignIn />` component, exactly mirroring
  the sign-up page above.

- **API route / SDK call:** Clerk's JS SDK talks to Clerk's API. No app
  endpoint involved.

- **Backend handler:** none.

- **Session / token creation mechanism:** Clerk issues a session and stores it
  in cookies scoped to the Clerk frontend domain. The short-lived RS256 JWT
  used for API calls is retrieved on demand via
  `window.Clerk.session.getToken()` (`frontend/src/lib/api.ts:29`).

- **What the client receives / where it stores it:** Clerk manages everything.
  The app never persists tokens itself.

- **Error handling:** same as sign-up — Clerk UI surfaces all errors.

---

## 5. Logout Flow

- **Frontend trigger:** Clerk's `<UserButton />` component rendered in the
  Settings page (`frontend/src/app/(main)/settings/page.tsx:807`). Its menu
  contains the "Sign out" item. There is no custom sign-out button, no
  `signOut()` call anywhere in the codebase (confirmed by grep).

- **What is cleared on the client:** Clerk clears its session cookie and
  in-memory session. The app's React Query cache (`queryKeys.state`, etc.) is
  **not** explicitly invalidated on sign-out — the session invalidation is
  implicit via the next API call returning 401 and redirecting to `/sign-in`
  (`frontend/src/lib/api.ts:54-57`). No localStorage keys to clear because the
  app stores none.

- **Backend revocation:** none. The shadow user row persists. The
  `clerk_id → user_id` in-memory cache keeps its entry until TTL (5 min) or
  process restart; since the mapping is immutable, this is harmless.

---

## 6. Session Management

- **"Am I logged in" on page load:**
  1. Clerk's `<ClerkProvider>` wraps the app in `frontend/src/app/layout.tsx:57-74`.
  2. The Next.js **proxy** (middleware) runs on every request. See section 7.
  3. Client components use Clerk hooks — every page that fetches data starts with:
     ```tsx
     const { isLoaded: authReady } = useAuth();
     const stateQuery = useUserState(authReady);
     ```
     (e.g. `frontend/src/app/(main)/today/page.tsx:87-96`,
     `frontend/src/app/(main)/week/page.tsx:50-53`). The React Query
     `enabled` flag is gated on `authReady` so no fetch fires before Clerk has
     hydrated its session.

- **Token refresh:** transparent. `window.Clerk.session.getToken()` returns a
  fresh JWT on each call — Clerk refreshes in the background. If a request
  ships with a stale token, the backend returns 401; the frontend retries once
  after 500 ms (`api.ts:48-53`, labeled B155) to cover the case where Clerk
  simply hasn't loaded yet. A second 401 triggers `window.location.href =
  "/sign-in"`.

- **Multi-tab behavior:** standard Clerk — logging out in one tab clears the
  Clerk cookie, so other tabs receive 401 on their next API call and are
  redirected to `/sign-in`. There is no explicit BroadcastChannel or
  storage-event listener in the app.

---

## 7. Protected Routes

### Frontend

The guarding is layered:

1. **Global middleware** at `frontend/src/proxy.ts` (renamed from
   `middleware.ts` — Next.js 16 renamed the filename to `proxy.ts`; see the
   `.next/server/middleware.js` artefact that confirms it still compiles as
   middleware):
   ```ts
   import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
   const isPublicRoute = createRouteMatcher([
     "/", "/sign-in(.*)", "/sign-up(.*)", "/legal", "/demo(.*)",
   ]);
   export default clerkMiddleware(async (auth, request) => {
     if (!isPublicRoute(request)) await auth.protect();
   });
   ```
   Any non-public path triggers `auth.protect()`, which redirects unauthenticated
   users to the Clerk-hosted sign-in route (falls back to `/sign-in` via env).

2. **Root page hydration guard** in `frontend/src/app/page.tsx:8-35` — uses
   `useAuth()`; if `!isSignedIn` it `router.replace("/sign-in")`. Otherwise it
   fetches state and routes to `/today` or `/onboarding/welcome`.

3. **Per-page fetch gating:** every page that needs state waits on
   `isLoaded: authReady` before calling React Query (pattern repeated across
   today/week/plan/settings/outdoor/session/subscribe).

### Backend

Every router handler that needs identity declares a FastAPI dependency:

```python
user_id: Optional[str] = Depends(get_user_id)
```

`get_user_id` is in `backend/api/deps.py:85-113`. Priority order:

1. `Authorization: Bearer <token>` + `is_clerk_configured()` →
   `verify_clerk_token` (RS256 via JWKS) → `lookup_or_create_user(clerk_id)`.
2. `X-User-ID: <uuid4>` header (dev/test fallback only; validated as UUIDv4).
3. `None` (legacy local dev without any header).

A **sample protected endpoint** (`backend/api/routers/state.py:34-37`):

```python
@router.get("")
def get_state(user_id: Optional[str] = Depends(get_user_id)):
    return load_state(user_id)
```

The fallback arm (`X-User-ID`) is not a security hole in production **as long
as `CLERK_JWKS_URL` is set** — when set, any `Authorization: Bearer …` with a
bad signature raises 401 immediately (`deps.py:102-103`). If `Authorization`
is absent the `X-User-ID` path is still reachable, so misconfiguring
`CLERK_JWKS_URL` would effectively disable auth. This is called out
explicitly as a documented behaviour, not a guarded invariant. **Potential
gotcha.**

Admin endpoints use a separate `X-Admin-Key` header validated against
`ADMIN_SECRET` (`backend/api/routers/admin.py:19-24`).

Subscription gating — orthogonal to auth — is a second dependency:
`Depends(require_active_subscription)` layered onto many write endpoints
(see grep results showing 88 occurrences of `Depends(get_user_id)` /
`require_active_subscription` across 17 router files).

---

## 8. Frontend Integration

- **Provider:** `<ClerkProvider>` in `frontend/src/app/layout.tsx:57`, wrapping
  the entire HTML shell. No Clerk props set — everything is driven by env vars.

- **Hooks consumed:**
  - `useAuth()` → `{ isLoaded, isSignedIn, userId, sessionId, ... }`. Used on 10+
    pages, always as `const { isLoaded: authReady } = useAuth();`.
  - `useUser()` → `{ user, isLoaded, isSignedIn }`. Used only once, in
    `frontend/src/app/(main)/subscribe/page.tsx:16`, to read
    `user?.primaryEmailAddress?.emailAddress` for the Stripe prefill.
  - `window.Clerk?.session?.getToken()` — called directly in
    `frontend/src/lib/api.ts:29` to attach `Authorization` on every fetch. A
    small ambient type file augments `window`: `frontend/src/lib/clerk.d.ts`.

- **Components consumed:** `<SignIn />`, `<SignUp />`, `<UserButton />`. Used
  in their canonical Clerk placement (no customization beyond a centering div).

- **App-specific auth abstraction:** none. The app does **not** wrap Clerk in
  its own `useAuth` / `AuthContext` — it calls the Clerk SDK directly. The
  closest helper is `_getAuthHeaders()` in `api.ts:26-35`, which is
  intentionally a plain module-level async function so it can be awaited from
  inside `request()`.

- **Representative consumer** (`frontend/src/app/(main)/today/page.tsx:87-96`):
  ```tsx
  const { isLoaded: authReady } = useAuth();
  const stateQuery = useUserState(authReady);
  // …react-query renders state.data once isLoaded is true and fetch has resolved
  ```

---

## 9. Backend Integration

- **JWT verification library:** `PyJWT` with the `[crypto]` extra (for RS256).
  `backend/api/auth.py:43-56` is the full verifier — 14 lines:
  ```python
  def verify_clerk_token(token: str) -> dict:
      jwk_client = _get_jwk_client()
      signing_key = jwk_client.get_signing_key_from_jwt(token)
      payload = jwt.decode(
          token,
          signing_key.key,
          algorithms=["RS256"],
          options={"verify_aud": False},
      )
      return payload
  ```

- **JWKS client caching:** `@lru_cache(maxsize=1)` on `_get_jwk_client()`
  (`auth.py:38-40`). PyJWKClient itself caches keys internally.

- **User identity attachment:** per request, not per connection. The
  `get_user_id` dependency returns `user_id` as a plain string; handlers take
  it as a parameter. There is no `request.state.user` or middleware-level
  attachment — FastAPI DI is the single mechanism.

- **clerk_id → user_id lookup cache:** `_clerk_id_cache: dict[str, tuple[str,
  float]]` module-level dict in `auth.py:65`. TTL 5 minutes. Safe because the
  mapping is immutable after row creation. **Per-process cache only** — Railway
  runs multiple workers, so lookup latency is paid once per worker per user per
  TTL.

- **Sample protected endpoint, full flow** (`backend/api/routers/state.py:34-37`):
  Authorization header → `get_user_id()` (`deps.py:93-103`) →
  `get_clerk_user_id()` (`auth.py:59-62`) → JWKS-verified `sub` →
  `lookup_or_create_user()` (`auth.py:69-97`) → Supabase upsert if needed →
  handler receives `user_id: str` → `load_state(user_id)` reads
  `users.state` JSONB row by that id.

- **401 surface:** `HTTPException(status_code=401, detail="Invalid token: {e}")`
  (`deps.py:103`). Any exception from PyJWT bubbles out as 401, no finer
  distinction between "expired", "bad signature", "malformed".

---

## 10. Password Management

- **Password reset:** fully delegated to Clerk. The `<SignIn />` component has
  a built-in "Forgot password?" link that triggers Clerk's email flow. No app
  code involved.
- **Change password:** inside Clerk's `<UserButton />` → "Manage account" UI,
  rendered on `/settings`.
- **Password rules (length, complexity, breach detection, MFA):** configured
  in the Clerk dashboard, not in this repository.

---

## 11. Social Login

**Not configured in code.** Any OAuth providers would be added in the Clerk
dashboard and appear automatically in `<SignIn />` / `<SignUp />`. Repository
contains no OAuth callback routes, no PKCE logic, no account-linking code. If
the current Clerk instance has, say, Google enabled, that is a
dashboard-only setting invisible here.

---

## 12. Testing

- **Strategy:** bypass Clerk entirely in pytest.
  - `backend/tests/conftest.py` sets `RATE_LIMIT_ENABLED=0` but does **not**
    set `CLERK_JWKS_URL`, so `is_clerk_configured()` returns False and the
    backend accepts `X-User-ID` as authoritative.
  - `STORAGE_BACKEND` defaults to `file`, so tests use the on-disk backend
    (`backend/engine/storage_file.py`). Supabase calls are never made.
  - No mock of Clerk, no test Clerk instance — tests simply route around the
    Clerk branch.

- **Representative test file:** `backend/tests/test_multiuser.py:50-55` shows
  the pattern in one line:
  ```python
  def _headers(user_id: str) -> dict:
      return {"X-User-ID": user_id}
  ```
  Every test issues a fresh UUIDv4 as `X-User-ID`, exercises endpoints, and
  asserts state isolation on disk.

- **Frontend tests:** `frontend/src/lib/__tests__` exists but no Clerk-specific
  mocks. `vitest.config.mts` is present; auth-related UI is not covered by
  Vitest — the tests target pure utility functions.

---

## 13. Files Inventory

### Frontend (auth or auth-adjacent)

- `frontend/package.json` — declares `@clerk/nextjs: ^7.0.4`.
- `frontend/.env.local`, `frontend/.env.example` — hold
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `NEXT_PUBLIC_CLERK_SIGN_IN_URL`,
  `NEXT_PUBLIC_CLERK_SIGN_UP_URL`.
- `frontend/src/proxy.ts` — Next 16 middleware (`clerkMiddleware` + public
  route matcher). The file that enforces "logged-in or redirect".
- `frontend/src/app/layout.tsx` — wraps app in `<ClerkProvider>`.
- `frontend/src/app/page.tsx` — root redirect: sign-in → onboarding → today.
- `frontend/src/app/sign-in/[[...sign-in]]/page.tsx` — renders `<SignIn />`.
- `frontend/src/app/sign-up/[[...sign-up]]/page.tsx` — renders `<SignUp />`.
- `frontend/src/lib/api.ts` — injects `Authorization: Bearer` from
  `window.Clerk.session.getToken()`; handles 401 retry + redirect.
- `frontend/src/lib/clerk.d.ts` — ambient type for `window.Clerk.session`.
- `frontend/src/app/(main)/settings/page.tsx` — embeds `<UserButton />`
  (sign-out and account management UI).
- `frontend/src/app/(main)/subscribe/page.tsx` — reads Clerk `user` for Stripe
  prefill.
- `frontend/src/lib/hooks/use-state.ts`,
  `frontend/src/lib/hooks/queries/use-user-state.ts` — gate fetches on
  `enabled=authReady`. Not strictly auth files but carry the coupling.
- Every page under `frontend/src/app/(main)/*/page.tsx` that reads
  `useAuth()` (≈10 files) — downstream consumers.

### Backend (auth or auth-adjacent)

- `backend/requirements.txt` — declares `PyJWT[crypto]` and `supabase`.
- `backend/api/auth.py` — full Clerk JWT verifier + shadow-row
  lookup/create. 97 lines. **The portable core.**
- `backend/api/deps.py:85-113` — `get_user_id()` dependency, the entry point
  used by every handler.
- `backend/api/deps.py:309-328` — `require_active_subscription()` (paywall,
  not identity).
- `backend/api/main.py` — mounts routers; CORS config includes `allow_credentials=True`
  and an origin regex covering Vercel previews.
- `backend/engine/storage_supabase.py` — `read_state` / `write_state` for the
  `users.state` JSONB column (the shadow row).
- `backend/api/routers/admin.py` — separate `X-Admin-Key` (not Clerk).
- `backend/api/routers/user.py:122-169` — legacy `recovery-code` endpoints,
  orphaned by the frontend but still reachable.
- `backend/api/routers/state.py`, `session.py`, `feedback.py`, `outdoor.py`,
  `subscription.py`, etc. — every router using `Depends(get_user_id)`.

### Shared / config / tests

- `.env` (repo root, gitignored) — holds `CLERK_SECRET_KEY`, `ADMIN_SECRET`,
  `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` for local dev.
- `CLAUDE.md:300` — one-liner documenting the Supabase RLS posture.
- `docs/migrations/subscriptions_table.sql` — only committed SQL migration;
  the `users` table is not in git.
- `backend/tests/test_multiuser.py` — end-to-end auth fallback tests via
  `X-User-ID`.
- `backend/tests/conftest.py` — configures pytest env; implicitly disables
  Clerk by omitting `CLERK_JWKS_URL`.
- `backend/tests/test_a159_subscription.py` — exercises the
  `BYPASS_USER_IDS` bypass path.

### Ambiguities / unknowns

- The canonical `CREATE TABLE users (...)` SQL for the shadow `users` table is
  **not in the repo**. It was applied directly in Supabase and is only
  recoverable by introspection. A port to another project will have to
  reconstruct the columns from code references listed in Section 2.
- The list of Clerk-dashboard settings (OAuth providers enabled, email
  template, password rules, MFA, allowed redirect URLs) is not in the repo.

---

## 14. Portability Assessment

### What is service-provider-specific vs reusable

- **Service-provider-specific (cannot be lifted as code, must be recreated):**
  - Clerk application setup (publishable key, secret key, JWKS URL).
  - Clerk dashboard configuration: OAuth providers, email templates, password
    rules, allowed redirect URLs, session lifetime, webhook endpoints.
  - Supabase project + `users` table + RLS posture + service role key.

- **Plain reusable code (direct lift or near-direct lift):**
  - `backend/api/auth.py` (97 lines) — the entire JWT verify + lookup/create
    module. Depends only on `PyJWT[crypto]` and a supabase-py client.
  - `backend/api/deps.py:85-113` — `get_user_id()` dependency pattern.
  - `frontend/src/proxy.ts` — Clerk middleware (rename to `middleware.ts` if
    target is Next 14).
  - `frontend/src/app/layout.tsx` — `<ClerkProvider>` wrap.
  - `frontend/src/app/sign-in/...`, `frontend/src/app/sign-up/...` — 9-line
    pages each, trivially portable.
  - `frontend/src/lib/api.ts:26-63` — token-attach + 401-retry-and-redirect
    fetch wrapper.
  - Testing pattern: skip Clerk in pytest by leaving `CLERK_JWKS_URL` unset and
    using an `X-User-ID` header fallback.

### What would block a direct port to Kilter-Up

Kilter-Up is Next.js 14 + FastAPI + SQLite-dev / PostgreSQL-prod, currently
using its own Python-native JWT in `backend/app/core/security.py`.

1. **Next.js version:** climb-agent is on Next 16 which renamed `middleware.ts`
   → `proxy.ts`. On Next 14 the file must be called `middleware.ts`. Otherwise
   the content is unchanged.
2. **Existing JWT stack must be removed or supplanted:** Kilter-Up's own
   `security.py` likely owns password hashing, signup, and HS256 JWT issuance.
   Adopting Clerk means deleting those routes (Clerk takes over the identity
   surface). Keeping both is possible but unusual and increases attack
   surface.
3. **User table shape:** Kilter-Up's `users` table presumably has its own id
   / email / password_hash columns. Adopting Clerk requires adding `clerk_id`
   (unique, indexed) and letting Clerk own email. If there are existing users
   they need to be migrated into Clerk (Clerk has a bulk import API) and
   backfilled with `clerk_id`.
4. **SQLite vs. Supabase:** the lookup-or-create code (`auth.py:82-94`) uses
   the `supabase-py` client. Porting to Kilter-Up's SQLAlchemy + SQLite/Postgres
   means rewriting those ~10 lines — structurally identical, just different
   ORM.
5. **Fallback `X-User-ID` path:** the dev-only escape hatch in `deps.py:105-113`
   is safe for climb-agent because `CLERK_JWKS_URL` is always set in prod. If
   ported verbatim to Kilter-Up it must be gated behind an explicit
   `ENV != "production"` check; otherwise it is a trivial auth bypass.
6. **CORS / cookie domain:** Clerk hosts the sign-in widget on its own
   subdomain. Any new project needs its production URL registered in the Clerk
   dashboard's allowed origins.

### Recommended migration approach

**Reimplement with same pattern** (option 2), using a new Clerk instance for
Kilter-Up.

Rationale: the code to lift is small (`auth.py` is 97 lines, `proxy.ts` is 22
lines, `api.ts` token wiring is 40 lines), but the data model and surrounding
stack differ enough that a mechanical copy would introduce bugs
(`X-User-ID` fallback on SQLite is not what Kilter-Up wants; supabase-py
calls need rewriting to SQLAlchemy). Keep the *shape*: Clerk as identity
provider, middleware for route protection, JWT verify via JWKS in a FastAPI
dependency, shadow `users` table linked by `clerk_id`, in-memory TTL cache for
the mapping, UserButton for sign-out, `useAuth().isLoaded` as the gate for
data fetches. Deprecate Kilter-Up's own password-JWT code at the same time — it
only pays off if Clerk becomes the sole identity provider. Two days of work
to wire up + user migration; far lower than building equivalent
password-reset + email-verification + OAuth code.

---

## Appendix A — Raw Evidence

### A.1  Clerk JWT verification (`backend/api/auth.py:38-97`)

```python
@lru_cache(maxsize=1)
def _get_jwk_client() -> PyJWKClient:
    return PyJWKClient(CLERK_JWKS_URL)

def verify_clerk_token(token: str) -> dict:
    jwk_client = _get_jwk_client()
    signing_key = jwk_client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token, signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    return payload

def get_clerk_user_id(token: str) -> str:
    return verify_clerk_token(token)["sub"]

_clerk_id_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300

def lookup_or_create_user(clerk_id: str) -> str:
    now = time.time()
    cached = _clerk_id_cache.get(clerk_id)
    if cached and now - cached[1] < _CACHE_TTL:
        return cached[0]
    from backend.engine.storage_supabase import _sb
    result = _sb().table("users").select("user_id").eq("clerk_id", clerk_id).execute()
    if result.data:
        user_id = result.data[0]["user_id"]; _clerk_id_cache[clerk_id] = (user_id, now); return user_id
    new_user_id = str(uuid.uuid4())
    _sb().table("users").insert({"user_id": new_user_id, "clerk_id": clerk_id, "state": {}}).execute()
    _clerk_id_cache[clerk_id] = (new_user_id, now)
    return new_user_id
```

### A.2  Request-level auth dependency (`backend/api/deps.py:85-113`)

```python
def get_user_id(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        from backend.api.auth import get_clerk_user_id, is_clerk_configured, lookup_or_create_user
        if is_clerk_configured():
            try:
                token = auth_header.split(" ", 1)[1]
                clerk_id = get_clerk_user_id(token)
                return lookup_or_create_user(clerk_id)
            except Exception as e:
                raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    header = request.headers.get("X-User-ID")
    if header is None: return None
    try: _uuid.UUID(header, version=4)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid X-User-ID: must be a valid UUID v4")
    return header
```

### A.3  Frontend middleware (`frontend/src/proxy.ts`, full file)

```ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
const isPublicRoute = createRouteMatcher([
  "/", "/sign-in(.*)", "/sign-up(.*)", "/legal", "/demo(.*)",
]);
export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) await auth.protect();
});
export const config = {
  matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)"],
};
```

### A.4  ClerkProvider root (`frontend/src/app/layout.tsx:51-75`)

```tsx
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark" suppressHydrationWarning>
        <body className={`${inter.variable} font-sans antialiased`}>
          <Providers>
            <div className="mx-auto min-h-screen max-w-3xl">{children}</div>
            <Toaster richColors position="top-center" />
            <SwUpdateBanner />
          </Providers>
          <Analytics />
          <script dangerouslySetInnerHTML={{ __html: `if("serviceWorker"in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("/sw.js"))` }} />
        </body>
      </html>
    </ClerkProvider>
  );
}
```

### A.5  Frontend fetch wrapper with token + retry (`frontend/src/lib/api.ts:26-63`)

```ts
async function _getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {};
  try {
    const token = await window.Clerk?.session?.getToken();
    if (token) return { Authorization: `Bearer ${token}` };
  } catch {}
  return {};
}

async function request<T>(path: string, options?: RequestInit, _isRetry = false): Promise<T> {
  const authHeaders = await _getAuthHeaders();
  const headers: Record<string, string> = { "Content-Type": "application/json", ...authHeaders, ...((options?.headers as Record<string, string>) || {}) };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401 && !_isRetry && typeof window !== "undefined") {
    await new Promise((r) => setTimeout(r, 500));
    return request<T>(path, options, true);
  }
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/sign-in"; throw new Error("Session expired");
  }
  if (!res.ok) { const body = await res.text(); throw new Error(`API ${res.status}: ${body}`); }
  return res.json() as Promise<T>;
}
```

### A.6  Sample protected endpoint (`backend/api/routers/state.py:34-37`)

```python
@router.get("")
def get_state(user_id: Optional[str] = Depends(get_user_id)):
    """Return the full user_state.json."""
    return load_state(user_id)
```

### A.7  Supabase shadow-row read/write (`backend/engine/storage_supabase.py:76-88`)

```python
def read_state(user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    uid = _effective_uid(user_id)
    r = _sb().table("users").select("state").eq("user_id", uid).execute()
    if r.data: return r.data[0]["state"]
    return None

def write_state(state: Dict[str, Any], user_id: Optional[str] = None) -> None:
    uid = _require_user_id(user_id)
    _sb().table("users").upsert({"user_id": uid, "state": state}).execute()
```

### A.8  Typical page-level auth gate (`frontend/src/app/(main)/today/page.tsx:87-96`)

```tsx
const { isLoaded: authReady } = useAuth();
// ...
const stateQuery = useUserState(authReady);
```
