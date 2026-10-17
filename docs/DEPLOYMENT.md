# Deployment — climb-agent

> Vercel, Railway, Stripe, Clerk, variabili d'ambiente, persistenza, query di debug. Spostato da `CLAUDE.md` in D285 (2026-10-17). Le regole operative restano in `CLAUDE.md`.

## Services

- **Frontend**: Next.js PWA on Vercel — **https://climbagent.app** (canonical, A248)
  - `www.climbagent.app` and the legacy `https://climb-agent.vercel.app` 308-redirect to the apex (configured in Vercel; DNS on Namecheap: A `@`/`www` → 76.76.21.21)
  - Auto-deploys on push to main. Root directory: `frontend/`
  - Env: `NEXT_PUBLIC_API_URL=https://web-production-fb1e9.up.railway.app`

- **Backend**: FastAPI/uvicorn on Railway — https://web-production-fb1e9.up.railway.app
  - Auto-deploys on push to main. Config: `Procfile` + `requirements.txt` in root
  - Railway uses port 8080 internally (`$PORT=8080`). Do not change the port in Procfile.
  - Region: `europe-west4-drams3a` (Amsterdam) since 2026-10-17 — moved from `us-west2` to sit next to Supabase (AWS eu-west-1, Dublin): GET `/api/week` 3.5 s → 1.3 s. `railway scale` (CLI 4.30.3) panics on regions; change it via GraphQL `serviceInstanceUpdate(multiRegionConfig)` + `serviceInstanceRedeploy`. The volume `/data/climb-agent` is legacy in Supabase mode and migrates with the region.

- **Deploy**: `git push` to main → both services update within 2-3 minutes.

- **Deploy workflow rules (B196):**
  - **Backend-only briefs** (no `frontend/` files touched): push directly to main is OK.
  - **Briefs that touch `frontend/`**: MUST be developed on a branch named `brief/B<n>-<slug>` and tested on the Vercel preview URL before merging to main. Daniele must explicitly approve the preview before merge. Never push frontend changes directly to main without preview verification — PWA users on iPhone are trapped on the previous SW until the new build is verified.
  - The Service Worker (`frontend/public/sw.template.js`) generates `public/sw.js` per-build via `frontend/scripts/build-sw.js` (prebuild hook), injecting `VERCEL_GIT_COMMIT_SHA` into `CACHE_NAME`. Do NOT commit `public/sw.js` (gitignored). Do NOT bump CACHE_NAME manually.

- **Stripe**: sk_live keys configured in Railway + Vercel. **LIVE** since 2026-04-16. Pricing: USD $9.99/month Standard (15-day free trial) + USD $4.99/month Founding Climber (locked forever, first 20 users — two separate Stripe Price objects, not coupon). Customer Portal configured. B202 fail-closed guard active — unless A285's `SUBSCRIPTION_ENFORCED=0` is set on Railway, which pauses billing without touching Stripe, the guard code, or a single subscription row (check the live variable before assuming which mode production is in). Webhook handles (B226 hardened): checkout.session.completed, customer.subscription.updated, customer.subscription.deleted, customer.deleted, invoice.payment_succeeded, invoice.payment_failed. Handler exceptions return 500 → Stripe retries with backoff. In-memory LRU dedup of event.id (1024 entries) short-circuits duplicate deliveries.

- **Auth**: Clerk (Next.js native). **Production instance since A249 (2026-07-21)** — Frontend API `https://clerk.climbagent.app`, accounts portal `https://accounts.climbagent.app`, 5 CNAME records on Namecheap. The dev instance (`funky-monarch-83`) survives for local dev + Vercel previews (pk_test/sk_test keys scoped to Preview/Development on Vercel). Backend resolves `clerk_id` → internal `user_id` (UUID) via `CLERK_JWKS_URL`. Supabase `users` table with `clerk_id` column (remapped to prod ids by `scripts/migrate_clerk_prod.py`, backup in `scripts/clerk_migration_backup.json`). In-memory LRU cache for `clerk_id → user_id` mapping. Without Clerk header → fallback to legacy UUID system (local dev only).
  - **Testing as a user in prod**: Clerk BAPI `POST /v1/sessions` is dev-only. On prod: `POST /v1/sign_in_tokens` (BAPI) → `POST https://clerk.climbagent.app/v1/client/sign_ins?_is_native=true` with `strategy=ticket` (FAPI) → session JWT in `client.sessions[0].last_active_token.jwt`.

- **Environment variables (Railway)**:
  | Variable | Description |
  |----------|-------------|
  | DATA_DIR | Persistent volume path (`/data/climb-agent`) |
  | ADMIN_SECRET | Key for admin endpoints (never commit) |
  | STORAGE_BACKEND | `supabase` (production) or `file` (pytest/dev) |
  | SUPABASE_URL | Supabase project URL |
  | SUPABASE_SERVICE_KEY | Supabase service role key (never commit) |
  | CLERK_SECRET_KEY | Clerk backend secret (never commit). NOTE: the backend code does NOT read it — auth uses only CLERK_JWKS_URL. Kept on Railway for completeness. |
  | CLERK_JWKS_URL | Clerk JWKS endpoint for JWT verification — the ONLY Clerk var the backend reads. Prod (A249): `https://clerk.climbagent.app/.well-known/jwks.json` |
  | STRIPE_SECRET_KEY | Stripe secret key — `sk_live_*` in prod (never commit) |
  | STRIPE_WEBHOOK_SECRET | Stripe webhook signing secret — `whsec_*` (never commit) |
  | STRIPE_PRICE_ID_STANDARD | Stripe Price ID for standard plan ($9.99/mo) |
  | STRIPE_PRICE_ID_FOUNDER | Stripe Price ID for Founding Climber plan ($4.99/mo) |
  | STRIPE_PORTAL_ENABLED | `true` to enable Customer Portal (default: true) |
  | FRONTEND_BASE_URL | Base URL for Stripe redirect (default: `https://climbagent.app`, A248) |
  | BYPASS_USER_IDS | Comma-separated user UUIDs that bypass subscription checks (founder, beta testers). Managed via Railway dashboard — no code change needed to add/remove. Read at import-time: changing it requires a service restart (Railway redeploy or manual restart). |
  | TELEGRAM_BOT_TOKEN | Bot token (@BotFather) for founder alerts. Unset → `notify()` is a silent no-op (A222). |
  | TELEGRAM_CHAT_ID | Destination chat id for founder alerts (new onboarding / trial started). Unset → no-op. |
  | OPENWEATHER_API_KEY | OpenWeatherMap free-tier key for `/api/weather` (A224) + coach `get_weather` tool & spot geocoding (A-COACH-V1b, on-demand since A244). Unset → endpoint returns 503, `/today` card hides, coach `get_weather` tool returns "unavailable" (model says so, never invents). Commercial use requires visible OpenWeather attribution. |
  | ANTHROPIC_API_KEY | Anthropic API key for the LLM Coach (A-COACH-V1a). Unset → `/api/coach/chat` fails LOUD with 500 `coach_not_configured` (never silent, never commit). |
  | COACH_MODEL | Coach model id (default `claude-sonnet-5` dal 2026-07-28, B306). Swap here for provider/model changes — no code change needed. |
  | COACH_MAX_TOKENS | Cap on the coach reply length (default `2048`). **Documented in D277**, and it is the knob the open `COACH-TRUNCATION-RESIDUAL` finding is about: `llm_client.py` logs "raise COACH_MAX_TOKENS or tighten L1" when a reply is cut, so the remedy existed while the variable did not appear anywhere in the docs. |
  | RATE_LIMIT_ENABLED | `0` turns off *all* API rate limiting. Default is **on** (any value other than `0`), so it fails safe — but it is a security switch and must stay unset in production. Documented in D277. |
  | TRACE_RESOLVE | `true` enables the verbose resolver trace (B126) for debugging `resolve_session` on Railway. Default `false`. Documented in D277. |
  | WEEKPLAN_ARCHIVE_LAZY | `true` makes the A221 week-plan archiving lazy instead of eager. Default `false`. Documented in D277. |
  | COACH_LLM_COMPOSER | `0` disables the A259 LLM composer — every ad-hoc session then goes through the deterministic `adhoc_builder`. Unset/any other value = enabled. |
  | COACH_ATHLETE_CONTEXT | A297 — the engine's athlete context in the coach prompts (maxima, anchored loads, pain/fatigue, key sessions, recovery guards, retest, limit log) and the composer's guards/ranking. Default **on**; only the literal `0` turns it off, read at call time (a Railway change needs no deploy). Off = coach chat, composer and builder exactly as before A297. Single integration point: `backend/coach/athlete_block.py`. |
  | KEY_AUTO_RESCHEDULE | A315 — automatic re-schedule of a key session lost by a user's write (`/events`, `/override`). Default **on**; only the literal `0` turns it off, read at call time (a Railway change needs no deploy). Off = the A294 proposals wait for a tap, as before. |
  | STORAGE_REQUEST_MEMO | B376 — memo per richiesta delle letture di storage (archivio settimane, outdoor log): ogni lettura una volta sola per richiesta HTTP, svuotato da ogni scrittura. Default **on**; solo il literal `0` lo spegne, letto a ogni chiamata (nessun deploy per cambiarlo). Off = una lettura Supabase per chiamata, come prima. |
  | STATE_CODEC_PACK | B387 — il blob `users.state` salva `current_week_plan` come puntatore (`current_week_key`) quando duplica `week_plans[<lunedì>]` (`backend/engine/state_codec.py`). Default **on**; solo il literal `0` lo spegne (si torna a scrivere la copia intera), letto a ogni scrittura. La lettura capisce sempre entrambi i formati, quindi lo switch è sicuro in tutte e due le direzioni. Chi legge il blob grezzo via REST (mirror, script) passa da `state_codec.unpack`. |
| ALLOW_LEGACY_HEADER | **Dev only.** `1` re-enables the `X-User-ID` auth fallback and anonymous (`user_id=None`) requests. MUST stay unset in production: with Clerk configured or `STORAGE_BACKEND=supabase`, B285 rejects both with 401 (the header was a full IDOR). |
  | SUBSCRIPTION_ENFORCED | A285 **billing pause**. `0` makes `check_subscription` return ALLOW_ALL for everyone before any DB read — the app is free, no row is touched, Stripe stays LIVE and checkout/portal/webhooks keep working. Default **on**: like `RATE_LIMIT_ENABLED`, only the literal `0` disables, so unset/empty/`false` leave the paywall standing. Read at import time → a change needs a restart (setting it on Railway redeploys anyway). While off, `start_trial_if_new` writes nothing (a trial granted during the pause would expire unused and burn the user's one lifetime trial, A232) and `/api/subscription/status` reports `enforced: false` so the UI can say "Free" instead of claiming a subscription that does not exist. |

### Clerk user lookup

To retrieve user info (name, email) from Clerk:

```bash
# Read key from local .env
export CLERK_SECRET_KEY=$(grep CLERK_SECRET_KEY .env | cut -d= -f2)

# List all users
curl -s -H "Authorization: Bearer $CLERK_SECRET_KEY" \
  https://api.clerk.com/v1/users | python3 -c "
import json, sys
for u in json.load(sys.stdin):
    name = f\"{u.get('first_name','') or ''} {u.get('last_name','') or ''}\".strip() or '—'
    email = u['email_addresses'][0]['email_address'] if u['email_addresses'] else '—'
    print(f\"{u['id'][:12]}  {name:20s}  {email}\")
"

# Get a single user by Clerk ID
curl -s -H "Authorization: Bearer $CLERK_SECRET_KEY" \
  https://api.clerk.com/v1/users/{clerk_user_id}
```

Key location: `.env` in repo root (gitignored, never commit). Since A249 `CLERK_SECRET_KEY` in `.env` is the **production** instance (`sk_live_*`, i.e. the real users); the old dev instance is under `CLERK_DEV_SECRET_KEY`.

### Stripe read-only queries (debug/audit)

`STRIPE_SECRET_KEY` (`sk_live_*`) is in `.env` at repo root (gitignored, never commit). Use it for read-only Stripe investigations (subscriptions, invoices, charges, webhook event delivery) without needing Railway CLI auth:

```bash
source .venv/bin/activate
export STRIPE_SECRET_KEY=$(grep '^STRIPE_SECRET_KEY=' .env | cut -d= -f2-)
python - <<'PY'
import os, stripe
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
# e.g. stripe.Subscription.list(customer="cus_...", status="all")
# e.g. stripe.Event.list(limit=30)  → check pending_webhooks (>0 = delivery not confirmed)
PY
```

Note: StripeObject in stripe-python 15.x does not expose `.get()` as a method — use `obj["key"]` (wrapped in try/except) or `obj.to_dict_recursive()`.

- **Persistence**: Supabase Postgres with JSONB (`STORAGE_BACKEND=supabase` in production). `user_state` stored as JSONB column. Railway persistent volume (`/data/climb-agent`) as fallback for `STORAGE_BACKEND=file` (pytest, local dev). `/health` exposes `ephemeral_warning`. RLS enabled on all 6 tables (2026-04-03). No policies — anon key blocked, service role key bypasses RLS.
