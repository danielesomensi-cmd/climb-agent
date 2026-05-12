# D-COACH-AUDIT — LLM Coach readiness report

> Date: 2026-05-12
> Scope: read-only audit, no code changes
> Author: Claude Code (Sonnet)
> Brief ID assigned: **D-COACH-AUDIT** (slug). Numeric parallel available: `D238`. Slug verified free in `docs/`, `_archive/`, and `git log --all`.

---

## 1. Executive summary

The repo is a **green-field** for the LLM Coach layer: zero AI SDK imports (Python or JS), zero chat infrastructure (router, page, migration, components, streaming utilities), and zero coach-related stub files. The four planned directory roots (`backend/coach/`, `backend/coach/knowledge/`, `docs/knowledge/`, `frontend/src/app/chat/`) are all unoccupied — no rename collisions.

The biggest **immediate** gap is not infrastructure (which is straightforward to scaffold) but **scope clarification**: §11 of the design doc dates from before the Stripe LIVE pivot and Free Tier discussions (`A-FREE-01`/`A-FREE-02`), and the archived spec it cites — `_archive/docs/coach_knowledge_base_spec.md` — **does not exist on disk** (D236 cleanup found similar ghost-citations for `horst_integration_audit.md` but did not surface this one). Before any A-COACH-V1* brief is written, Daniele needs to make ~7 product decisions (Section 7) that the existing spec material leaves open.

**Recommended next brief: `A-COACH-V1a` — design doc + scaffold only** (no provider call, no UI). See Section 6 for the proposed sequence.

---

## 2. Existing spec material

### 2.1 `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` §11 — key points (lines 380–440)

- **Architectural principle**: engine remains 100 % deterministic; LLM is a layer *above* the engine, never inside the decision loop. Flow: `User ↔ LLM Coach ↔ API Backend ↔ Engine`.
- **Context injection per call**: `user_state` (profile, assessment, goal) + current plan (macrocycle, week, today's session) + recent logs (last 2 weeks) + available quotes.
- **Use cases**: guided onboarding (conversational assessment), pre-session coaching ("I feel tired today"), post-session reflection (narrate → structured feedback), trip preparation Q&A, contextual motivational quotes.
- **Implementation choices**: Claude Sonnet (cost/speed sweet spot), API key in backend env (user never configures anything), dynamic system prompt built per call, `POST /chat`, history passed inline.
- **Hard guard**: LLM cannot write to `user_state`, plan, or logs. Suggests only; the user confirms; the engine executes.
- **What the LLM does NOT do**: generate plans, compute progressions, modify the macrocycle, pick exercises. "L'LLM è l'interfaccia umana, non il cervello."

### 2.2 `_archive/docs/coach_knowledge_base_spec.md`

**FILE NOT FOUND** on disk. Referenced from `docs/ROADMAP_CURRENT.md:614` ("Design spec: `_archive/docs/coach_knowledge_base_spec.md`") but:

```bash
$ ls _archive/docs/coach_knowledge_base_spec.md
ls: _archive/docs/coach_knowledge_base_spec.md: No such file or directory

$ find _archive -iname "*coach*" -o -iname "*llm*"
(no results)
```

D236 (`docs/audit/D236/`) catalogued 4 dangling citations to `horst_integration_audit.md` (recoverable from git `70dadfa`) but **did not flag** the missing `coach_knowledge_base_spec.md`. Either the file lived in a different namespace, was never committed, or pre-dates the visible git history.

**Recommendation**: do not try to recover it. Treat §11 of the design doc as the only authoritative spec source for the audit, and have the next brief (`A-COACH-V1a`) write a fresh `docs/coach/design.md` that supersedes the dangling reference.

### 2.3 Roadmap mentions — exhaustive inventory

| Location | Reference |
|---|---|
| `ROADMAP_CURRENT.md:163` | "Don't build Kilter/Capacitor/LLM Coach before validating willingness to pay" (Council guardrail) |
| `ROADMAP_CURRENT.md:441` | "Coach KB spec: add 8 Hörst coaching cues" — 📋 Proposed, P2.75 KB Research |
| `ROADMAP_CURRENT.md:531` | R148 — "Prerequisite for R149 and LLM Coach" |
| `ROADMAP_CURRENT.md:611–621` | **Phase 3.5 LLM Coach** main entry, dependent items B89, B11, B29a, science explainers, nutrition hints |
| `ROADMAP_CURRENT.md:623–628` | R149 — Weakness→resolver hints (P3.5, depends R148) |
| `ROADMAP_CURRENT.md:712` | Rehab catalog — "Best candidate for LLM Coach layer (Phase 3.5)" |
| `ROADMAP_CURRENT.md:756` | Boulder style preferences — "Best candidate for LLM Coach layer" |
| `ROADMAP_CURRENT.md:764` | Boulder injury prehab — "Combine with injury tracking (Phase 3.5/4)" |
| `ROADMAP_CURRENT.md:873` | Coaching & UX mega brief — "Natural fit alongside LLM Coach closed-loop work (Phase 3.5)" |
| `ROADMAP_CURRENT.md:899` | R-03 Technique assessment — "May need LLM Coach for video analysis → could slip to v3" |
| `ROADMAP_CURRENT.md:913` | D82 — Menstrual cycle "LLM Coach layer: expert mode for personalized cycle-aware coaching" |
| `ROADMAP_CURRENT.md:925–936` | **v3 — LLM Coach & Advanced Assessment** table: D04/R-04, D31, D32 |
| `ROADMAP_v2.md:514` | B65 weekly report — fase 1 ✅ DONE, fase 2 (narrative) deferred to Phase 3.5 |
| `ROADMAP_v2.md:544` | B89 weekly report narrative LLM — ⏩ deferred |

---

## 3. Codebase inventory

### 3.1 Existing coach-related code

```bash
$ rg -i "anthropic|claude.?client|chat.?completion|llm.?coach|ollama|gemma" --type py --type ts --type tsx --type js -l
# Only doc files match — no source files
```

**Conclusion**: **zero** Anthropic SDK call sites, **zero** Ollama/Gemma references, **zero** `claude_client` modules, **zero** `llm_coach` symbols anywhere in `backend/` or `frontend/src/`. Pure green-field.

### 3.2 Chat-shaped backend infrastructure

```bash
$ rg -i "POST.*chat|router.*chat|chat.?router|conversations?|messages?\\b" --type py backend/api/
# Only hits: subscription error strings ("user_message", "Your trial has ended") and one user.py docstring
```

**Conclusion**: **no chat router, no conversation/message schemas, no placeholder endpoints.** The 20 routers in `backend/api/routers/` (`admin, assessment, body_part_picker, catalog, custom_session, feedback, free_session, macrocycle, onboarding, outdoor, quotes, replanner, reports, session, state, subscription, user, week, weekly_override`) do not include `chat.py`.

### 3.3 Frontend chat surfaces

```bash
$ ls frontend/src/app/chat/
ls: frontend/src/app/chat/: No such file or directory

$ rg -i "useChat|streamChat|sendMessage|chat.?stream" --type ts --type tsx frontend/
# No results
```

**Conclusion**: no `/chat` route, no chat components, no streaming hook, no useChat helper. Green-field.

### 3.4 Supabase / DB schema

```bash
$ ls docs/migrations/
subscriptions_table.sql        # only file
```

**Conclusion**: only one migration file (`subscriptions_table.sql`). No `chat_conversations`, `chat_messages`, `coach_sessions` table — names free. Note: production also has 5 tables (`users, session_logs, outdoor_logs, event_logs, recovery_codes`) created in Supabase dashboard without corresponding `.sql` files in this dir, so the audit assumes the new chat tables would follow the dashboard-managed convention or get a fresh migration file.

### 3.5 Dependencies already installed

**Python** (`backend/requirements.txt`):
```
jsonschema, fastapi, uvicorn[standard], pytest, httpx,
supabase, PyJWT[crypto], stripe, slowapi
```
→ no `anthropic`, no `openai`, no `ollama`. **httpx** is present (could be used for raw API calls, but a typed SDK is preferred).

**Frontend** (`frontend/package.json` dependencies):
```
@clerk/nextjs, @tanstack/react-query, @vercel/analytics,
class-variance-authority, clsx, lucide-react, next 16.1.6,
radix-ui, react 19.2.3, react-dom 19.2.3, sonner,
tailwind-merge, vaul
```
→ no `@anthropic-ai/sdk`, no `@ai-sdk/*`, no streaming primitive. Streaming would need either:
- `@anthropic-ai/sdk` (client-side, exposes API key — **not viable** since spec says key stays in backend), or
- a backend SSE/streaming endpoint consumed by `fetch` with `ReadableStream` (zero new deps required on FE).

### 3.6 Subscription guard integration

- **Core function**: `backend.engine.subscription_guard.check_subscription(user_id)` returns `{can_interact: bool, status: str, ...}`.
- **FastAPI dependency** (`backend/api/deps.py:309`): `require_active_subscription` raises `HTTPException(402)` on `can_interact == False`. No-op when `STRIPE_SECRET_KEY` unset, `STORAGE_BACKEND != "supabase"`, or user in `BYPASS_USER_IDS`.
- **Test coverage**: 16 unit tests in `backend/tests/test_a159_subscription.py` cover bypass / Stripe-off / Supabase-off / past_due / canceled paths.
- **Integration point for coach**: any new chat endpoint should declare `Depends(require_active_subscription)` in its signature — already a one-line wiring, no refactor needed.

---

## 4. Roadmap dependency map

| ID | Title | Current status | Relationship to LLM Coach |
|---|---|---|---|
| **B89** | Weekly report narrative LLM | ⏩ deferred (`ROADMAP_v2.md:544`) | **Use case** — replaces rule-based insights in `/reports/weekly` with LLM narrative |
| **B65** | Weekly Report (fase 1) | ✅ DONE | **Prerequisite met** — structured 9-section report exists, narrative slot ready |
| **B11** | Configurable test protocols | not found as standalone open item (`A-B11` is unrelated catalog item) | Listed as Phase 3.5 dependency in `ROADMAP_CURRENT.md:621` — needs status reconciliation |
| **B29a** | Dedicated test exercises | not found as open item | Listed as Phase 3.5 dependency — needs status reconciliation |
| **D04 / R-04** | Mental/tactical assessment via AI conversation | v3 (`ROADMAP_CURRENT.md:931`) | **Use case** — pure Coach feature |
| **D31** | Route preview coaching | v3 (`ROADMAP_CURRENT.md:934`) | **Use case** — Coach + optional photo input |
| **D32** | Fear assessment protocol | v3 (`ROADMAP_CURRENT.md:935`) | **Use case** — Coach for sensitive topic nuance |
| **D29** | Post-climb mental reflection questions | P3 (`ROADMAP_CURRENT.md:823`) | **Unblocked-by Coach** — currently 5 rotating questions, Coach could replace |
| **A-FREE-01** | Free Tier Logging | Open, P3 (`ROADMAP_CURRENT.md:950`) | **Parallel** — both pivot freemium boundary; Coach is likely paid-tier-only |
| **A-FREE-02** | Flexible Activity Logger | Open, P3 (`ROADMAP_CURRENT.md:951`) | **Parallel** — Coach can read logs from this regardless of plan structure |
| **R148** | Centralize weakness→axis mapping | Open, S effort (`ROADMAP_CURRENT.md:531`) | **Prerequisite** — explicitly named in roadmap as "Prerequisite for R149 and LLM Coach" |
| **R149** | Weakness→resolver hints | Open, P3.5 (`ROADMAP_CURRENT.md:623`) | **Parallel** — soft hints to resolver, complementary to Coach |
| **Coach KB cues** | Add 8 Hörst coaching cues | 📋 Proposed, P2.75 (`ROADMAP_CURRENT.md:441`) | **KB content** — material lives in claude.ai "climb-agent knowledge base" project (per CRITICAL CONSTRAINT in this brief) |
| **Rehab catalog** | Injury→exercise mapping with medical disclaimer | Open, future (`ROADMAP_CURRENT.md:712`) | **Use case** — explicitly tagged as "best candidate for LLM Coach layer" |
| **D82** | Menstrual cycle tracking | v2 (`ROADMAP_CURRENT.md:913`) | **Use case** — Coach expert mode for cycle-aware coaching |
| **Council guardrail** | (no ID) | Active rule (`ROADMAP_CURRENT.md:163`) | **Gate** — "Don't build LLM Coach before validating willingness to pay" → Stripe is now LIVE, ~4 beta testers; gate is conditionally lifted but post-launch retention data not yet in |

---

## 5. Architectural gap analysis

| Component | Planned location | Status | Evidence |
|---|---|---|---|
| Coach module (Python) | `backend/coach/` | **MISSING** | `ls backend/coach/` → No such file or directory |
| Provider abstraction | `backend/coach/providers/{anthropic,ollama}.py` | **MISSING** | Zero `anthropic` / `ollama` imports anywhere |
| Chat API router | `backend/api/routers/chat.py` | **MISSING** | Not in `backend/api/routers/` (20 routers, no `chat.py`) |
| Endpoints `POST /api/chat`, conversation/message list | — | **MISSING** | No matching handler in `backend/api/routers/` |
| Persistence: `chat_conversations`, `chat_messages` JSONB | Supabase | **MISSING** | No matching migration in `docs/migrations/`; table names not used in code |
| Tool definitions (`get_session_history`, `get_exercise_details`, `search_knowledge`) | `backend/coach/tools/` | **MISSING** | No tool-use scaffolding (`tool_call`, `function_call`, `tool_use` grep → 0 hits) |
| KB ingestion | `backend/coach/knowledge/` | **MISSING (by design)** | Per CRITICAL CONSTRAINT: KB content lives in a separate claude.ai project; staging is a later A-COACH-V1 sub-task, **not** an audit gap |
| Frontend page | `frontend/src/app/chat/page.tsx` | **MISSING** | Directory does not exist |
| Frontend hook | `frontend/src/lib/hooks/useChat.ts` | **MISSING** | No `useChat` / `streamChat` / `sendMessage` ref anywhere in `frontend/` |
| Subscription gate wrap | reuse `Depends(require_active_subscription)` | **EXISTS** | `backend/api/deps.py:309` — one-line wiring, 16 tests passing |
| Rate limiting | TBD (e.g. 200 msg/month) | **PARTIAL** | `slowapi` is in `backend/requirements.txt` — primitive available; no per-route policies in code yet |
| Env vars (`ANTHROPIC_API_KEY`, `COACH_MODEL`, `COACH_PROVIDER`) | Railway/Vercel | **MISSING** | Not in current CLAUDE.md env-var table or `.env` template |
| Telemetry (per-message token usage on row) | `chat_messages.usage_tokens_in/out` JSON | **MISSING** | No schema, no metric — but `slowapi` + existing logging patterns make this trivial to add |
| **Path collision check** | `backend/coach/`, `docs/knowledge/`, `frontend/src/app/chat/` | **ALL FREE** | All four `ls` calls return "No such file or directory" |

**Net assessment**: 12 of 13 components are MISSING. The single EXISTS row (subscription guard) is a clean, well-tested wiring point. The single PARTIAL (rate limiting) is just unused capacity, not a refactor target.

---

## 6. Recommended implementation sequence

Five sequential briefs. Each can be reviewed and OK'd before the next is started.

### `A-COACH-V1a` — Design doc + scaffold + provider abstraction (no UI, no live calls)
- **Scope**: write `docs/coach/design.md` (supersede dangling spec reference); create `backend/coach/` module skeleton (`__init__.py`, `context_builder.py` stub, `prompt_template.py` stub, `providers/__init__.py`, `providers/anthropic.py` interface only with mock implementation, `providers/ollama.py` placeholder).
- **Effort**: S (~half day)
- **Risk**: low (no engine touch, no production code path)
- **Dependencies**: none
- **STOP gate**: NO (zero high-risk modules touched)
- **Out**: a typed `CoachProvider` Protocol + mock that returns a canned response; ready for V1b to wire real Anthropic calls.

### `A-COACH-V1b` — Backend endpoint + Supabase schema + tool stubs (no FE, no live calls in CI)
- **Scope**: add `backend/api/routers/chat.py` with `POST /api/chat` (non-streaming first), `GET /api/chat/conversations`, `GET /api/chat/conversations/{id}/messages`; create `docs/migrations/chat_tables.sql` + apply via Supabase dashboard; wire `Depends(require_active_subscription)`; implement `backend/coach/tools/` interface (no LLM call yet, only `get_session_history`, `get_exercise_details`).
- **Effort**: M (1–2 days)
- **Risk**: medium (touches API surface + new tables)
- **Dependencies**: V1a
- **STOP gate**: YES — schema change + subscription wiring → user-state-adjacent
- **Tests**: provider mocked, expect `POST /api/chat` returns canned response, conversations persist, 402 returned when subscription expired

### `A-COACH-V1c` — Live Anthropic provider + dynamic system prompt + telemetry
- **Scope**: implement real `providers/anthropic.py` using `anthropic` SDK (new dep) with `claude-sonnet-4-6` default; build `context_builder.build_system_prompt(user_id)` from `user_state` + current plan + last-2-weeks logs; record `usage_tokens_in/out`, latency, provider, model on `chat_messages` row; add env vars to Railway.
- **Effort**: M (1–2 days)
- **Risk**: medium (real provider call, real API key, real cost)
- **Dependencies**: V1b
- **STOP gate**: NO (no engine modules) — but Daniele must approve the API-key handling pattern before commit
- **Cost gate**: ship with hardcoded soft cap (e.g. 50 msg/user/day) via `slowapi` before any non-bypass user can hit it

### `A-COACH-V1d` — Frontend `/chat` page + streaming wire-up
- **Scope**: `frontend/src/app/chat/page.tsx` with shadcn chat bubbles + input; `frontend/src/lib/hooks/useChat.ts` consuming SSE response from backend (re-wire V1c's endpoint to stream); add link from `/today` page.
- **Effort**: M (1–2 days)
- **Risk**: medium (frontend → MUST be on a `brief/A-COACH-V1d-chat` branch with Vercel preview per CLAUDE.md branch workflow rule)
- **Dependencies**: V1c
- **STOP gate**: NO — but **mandatory** Vercel preview verification on iPhone PWA before merge

### `A-COACH-V1e` — KB ingestion + `search_knowledge` tool
- **Scope**: Daniele exports KB summaries from claude.ai "climb-agent knowledge base" project into `backend/coach/knowledge/*.md`; implement `search_knowledge` tool (BM25 over markdown frontmatter+body is sufficient for v1 — no embeddings); the LLM calls it when methodology-question intent is detected.
- **Effort**: M (1–2 days, mostly content shaping)
- **Risk**: low (read-only tool, scoped to one tool function)
- **Dependencies**: V1d
- **STOP gate**: NO

---

## 7. Open questions for Daniele

These are decisions only Daniele can make. They block the design doc that `A-COACH-V1a` must produce.

1. **Free vs paid tier behaviour.** Should Coach be paid-tier-only (`require_active_subscription`), or also available — at lower message cap — on the trial/free tier? This interacts directly with `A-FREE-01` and the post-launch retention experiment.
2. **Chat history retention policy.** Forever? Last 90 days? Per-conversation manual delete? GDPR considerations — the Supabase row contains tokens from the LLM that may reflect personal context (injuries, mental state).
3. **Mental coaching disclaimer.** §11 includes "fear of falling" and post-session reflection. Should mental-health-adjacent topics show a one-time interstitial disclaimer ("not a substitute for therapy"), or only a footer line? D32 (fear assessment) explicitly notes "sensitive topic, needs LLM Coach for nuance".
4. **Plan-modification refusal pattern.** When the user says "change my plan to X", §11 says the LLM cannot write — but what's the UX? Hard refusal? Suggest action + "Apply this in /week" button? Inline `replanner` quick-call?
5. **Multi-language behaviour.** Daniele writes in Italian (per CLAUDE.md "Always respond in Italian"). Should the Coach (a) auto-detect user input language and mirror, (b) follow a user-profile `preferred_language` field (doesn't exist yet), or (c) always reply in the same language as the user message?
6. **Streaming on/off by default.** Streaming is better UX but raises cost/complexity. Decision affects whether V1b launches non-streaming and V1d adds streaming, or V1b/V1c bake it in from day one.
7. **Token budget per message and soft monthly cap.** Spec says "200 messages/month" as a rate-limit example — is that the actual target, or should we ship a higher cap and tune from analytics? Affects pricing model and Stripe upsell story.

**Bonus** (less urgent, but worth deciding before V1c):
- 8. **Telemetry surfaces.** Should Daniele see a live admin dashboard (`/admin/coach-usage`) or is logging to Railway + occasional manual SQL sufficient for V1?
- 9. **Conversation auto-naming.** Auto-generate title from first user message via the LLM (extra round-trip), or just `Chat 2026-05-12 16:42`?
- 10. **Ollama path priority.** Is the `providers/ollama.py` placeholder real (someday want to support self-hosted), or symbolic (kept for the abstraction but never to be implemented)? Affects how much rigor goes into the Protocol design in V1a.

---

✅ D-COACH-AUDIT complete. Report at docs/audit/D-COACH-AUDIT_report.md
   Waiting for Daniele's review before drafting implementation briefs.
