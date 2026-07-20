# D253 — Coach Weather & Tool-Use Readiness Audit (v1)

**Type:** D (audit / read-only) · **Working name:** D-COACH-WEATHER-AUDIT
**Date:** 2026-07-20 · **Model:** Opus 4.8
**Depends on:** none. Informs the follow-up **A-COACH-WEATHER-TOOL** brief and relates to **B-COACH-CONTEXT-FIX** (BUG-1, BUG-2).
**Scope:** read-only. No code changed. Every claim carries a `file:line` anchor.

> **Deliverable path note:** the brief names `docs/audit_coach_weather_v1.md`; CLAUDE.md mandates `docs/audit/<brief-id>_<topic>.md` (singular `audit/`). This file follows CLAUDE.md.

---

## TL;DR (read this first)

1. **Weather is a pre-fetch, not routed.** It is injected unconditionally into the *uncached dynamic* context block whenever the client sends `lat/lon` **or** the current week has a planned outdoor day within a 5-day horizon (`prompt_builder._weather_section`, `prompt_builder.py:471-524`). The KB router (`routing.py`) has **no** weather row and plays **no** part in the weather path.
2. **Native Anthropic tool use is already wired** — but only single-shot forced extraction, not a tool-use *loop*. `llm_client.extract()` (`llm_client.py:99-119`) sends `tools=[…]` + `tool_choice`. The chat path `llm_client.chat()` (`llm_client.py:56-96`) sends **no** tools and does **no** `tool_result` turn.
3. **There is no "English-only enforcement."** The runtime instruction explicitly says *reply in the user's language* (`prompt_builder.py:52-53`). BUG-2 as framed ("replied in Italian despite English-only") rests on a premise that does not exist in the code — see §3. This matters: **native tool use makes trigger detection language-agnostic for free**, and no keyword layer is needed or wanted.
4. **No streaming.** `coachChat` awaits one JSON `{reply}` (`api.ts:943-950`); the server calls `messages.create` non-streamed (`llm_client.py:73`). The client *already* waits for the full reply, so a tool round-trip introduces **no** "delay-before-first-token" regression relative to today's UX.
5. **Moving weather to on-demand tool use is a net improvement, not just neutral:** non-weather questions stop paying the always-on OWM fetch + injected weather tokens (§4). "Zero regression" is not only achievable — the common case gets *cheaper and faster*.
6. **Do NOT switch to Open-Meteo.** Its hosted free API is **non-commercial only**; climb-agent is a paid product. Keep OpenWeatherMap (already commercial-with-attribution) and have the tool wrap the existing `cached_conditions()` (§6).

---

## 1. Current weather flow

### 1.1 Where fetched / provider / fields
- Provider: **OpenWeatherMap free tier**, classic 2.5 endpoints — `/data/2.5/weather` (current) and `/data/2.5/forecast` (5 day / 3 h steps). `weather.py:41`, `weather.py:283-301`.
- Single fetch path: `cached_conditions(lat, lon, date?)` (`weather.py:402-435`). Normalized shape produced by `_normalize_current` (`weather.py:92-125`) and `_normalize_forecast` (`weather.py:128-176`): `temp, feels_like, humidity, dew_point, wind, wind_label, precip_prob, condition_text/code, friction_score, band/condition_band, headline, qualifiers, best_window, recent_rain_mm, is_forecast, date`.
- Dew point is **derived** (Magnus-Tetens) in `weather_v1.compute_dew_point` — OWM does not return it (`weather.py:10-12`, `weather.py:101`).

### 1.2 When fetched / caching / TTL
- Fetched **per coach message**, inside `build_dynamic_block` → `_weather_section` (`prompt_builder.py:608`, `prompt_builder.py:471`).
- Shared server cache: key `(round(lat,2), round(lon,2), date|"current", 15-min bucket)`, `weather.py:45-49`, `weather.py:402-435`. So a chat turn right after the `/today` card render is a **cache hit**, not a second OWM call (`weather.py:405-409`).
- Geocoding has its own in-memory cache (`_geo_cache`, ≤256 entries, successes + confirmed-not-found; transient failures never cached) — `weather.py:328-355`.

### 1.3 For which location
Two independent sources, both handled in `_weather_section` (`prompt_builder.py:471-524`):
- **Current conditions** — only if the client passes `lat/lon` (device GPS). `prompt_builder.py:487-492`.
- **Forecast** — for each **planned outdoor day** in the current week within the horizon, geocoded from `day["outdoor_spot_name"]` via `geocode_place()`. `prompt_builder.py:494-514`. There is **no** user-home fallback and **no** hardcoded location.

### 1.4 How injected — always or conditional
Injected into the **dynamic (uncached)** block, conditionally: a line per available datum. If neither current-location weather nor any qualifying outdoor day resolves, the whole section is dropped (`return None`, `prompt_builder.py:516-517`; consumed at `prompt_builder.py:575-576`). The section carries an anti-hallucination footer: *"If asked about weather not listed here, say you don't have that data — never invent conditions"* (`prompt_builder.py:521-523`).

### 1.5 Forecast capability
- Provider **is** forecast-capable on the current plan: 5 day / 3 h steps (`_normalize_forecast`, `weather.py:128-176`).
- Coach horizon is deliberately clamped tighter than the provider: `FORECAST_WINDOW_DAYS = 5`, `MAX_WEATHER_DAYS = 3` (`prompt_builder.py:434-436`, `prompt_builder.py:497-503`). Representative step = the 3 h slot closest to local **12:00** (`weather.py:139-143`).
- **Ceiling:** the free 2.5 forecast tops out at ~5 days. A `days` argument beyond that cannot be served without upgrading to One Call 3.0 (§6).

### 1.6 Friction score origin
**Computed by us**, not the provider — `compute_friction_score` in `weather_v1` (called at `weather.py:81`, surfaced via `_friction_fields`, `weather.py:76-89`). The "93/100" in the screenshot is our composite. `best_window` (`weather.py:217-278`) is also ours. This is a **competitive asset to preserve** through any tool migration — the tool must return our normalized shape, not raw OWM.

---

## 2. Coach invocation & routing

### 2.1 Model + API call shape; is native tool use wired?
- Model: `COACH_MODEL` env, default `claude-sonnet-4-6`; `MAX_TOKENS = 1024` (`llm_client.py:26-27`, `llm_client.py:52-53`).
- Chat call: `client.messages.create(model, max_tokens, system=[…], messages=…)` — **no tools** (`llm_client.py:73-78`).
- **Native tool use already exists in the codebase**: `extract()` sends `tools=[tool]` + `tool_choice={"type":"tool", …}` and reads the `tool_use` block back (`llm_client.py:99-119`). This is A243's adhoc-intent extractor. So the SDK plumbing, provider, and auth for tool use are proven — but it is **single-shot forced extraction**, not a call→result→answer loop.

### 2.2 How routing decides L0/L1/L2/L3; language of triggers
- **Keyword / BM25-style, no embeddings** — `routing.route_query()` (`routing.py:129-173`). L0+L1+L2 are always loaded (`prompt_builder.py:32-36`); up to 3 L3 files are keyword-matched from `_index.md` (`routing.py:61-109`).
- **Triggers are English-only.** The keyword table in `_index.md` is entirely English ("phase", "deload", "hangboard", …). An Italian query matches **zero** rows and silently falls back to the periodization+motivation pair (`routing.py:157-158`, `FALLBACK_FILES` at `routing.py:37-40`). This is a *latent* L3-relevance gap for non-English users — out of scope to fix here, but it is the same class of bug the weather tool must **not** reintroduce.
- **Weather is not in this table at all** — confirmed by grep of `_index.md`. Weather never routes.

### 2.3 Where a tool-use loop would plug in
Single, contained touchpoint: **`llm_client.chat()`** (`llm_client.py:56-96`) and its one caller **`service.handle_chat()`** (`service.py:161-180`).
- Today `chat()` returns `str`. A loop needs: pass `tools=[WEATHER_TOOL]`; if `response.stop_reason == "tool_use"`, execute the tool, append the assistant `tool_use` turn + a `user` `tool_result` turn to `messages`, and re-call `messages.create` until a text answer returns (cap the iterations — see §5.2).
- `messages` is already a mutable list assembled in `service.handle_chat` (`service.py:174-177`); the loop can live wholly inside `llm_client` with the tool executor injected, keeping `service` thin.
- **No streaming to unwind** (§2 TL;DR / 4.3). No multi-turn-within-one-message machinery exists today, so the loop is additive.
- The `extract()` shape (`llm_client.py:99-119`) is a ready template for the request/response handling.

### 2.4 Conversation history sent to the model?
Yes. `_load_history` returns a rolling window: **≤ 40 messages AND ≤ 30 days**, chronological, forced to start on a user turn (`service.py:20-22`, `service.py:32-48`). `handle_chat` sends `history + [new user msg]` (`service.py:174-177`). Implication for the loop: `tool_use`/`tool_result` turns must be appended to *this* list for the follow-up call, but must **not** be persisted to coach history (`append_coach_message` only stores the final user text + assistant reply, `service.py:178-179`) — otherwise the next turn's history would contain orphan tool blocks.

---

## 3. Language handling (BUG-2 adjacency)

### 3.1 Where English-only is enforced today
**It is not.** The only language rule is `prompt_builder.py:52-53`: *"Respond in the language the user writes in (Italian message → Italian reply, English → English). Use exactly ONE language per reply — never mix."* Grep of `backend/coach/knowledge/**` finds no "English-only" instruction (the `L*` hits for "language" are about *tone/voice*, not output language). **Finding: the BUG-2 premise ("English-only enforcement") does not exist in the code.** The real defect is likely one of: (a) reply mixing languages, or (b) the model answering in the "wrong" language on a terminology-heavy turn — but there is no rule to violate as stated. **Recommend the A/B brief re-baseline BUG-2 against the actual instruction before "fixing" it.** (Confirm with Daniele: what was the expected vs actual language, and the exact input?)

### 3.2 Language-dependent triggers that would miss Italian
- **Yes, in routing** (`_index.md` keyword table) — see §2.2. "che tempo fa", "condizioni", "meteo", "martedì" match nothing; but since weather isn't routed anyway, this specifically does **not** affect weather today.
- **Weather injection itself is language-agnostic** — it triggers on `lat/lon` presence and on structured `outdoor_spot_name`/`date` fields (`prompt_builder.py:487`, `prompt_builder.py:498-503`), never on message text. So today a user asking "che tempo fa martedì?" gets weather **only** if they happen to have GPS on or a planned outdoor day — the *question* never triggers a fetch. This is precisely the gap the tool closes.

### 3.3 Confirm/refute: native tool use ⇒ language-agnostic trigger, no keyword layer
**Confirmed.** With a `get_weather` tool, the model decides when to call it from the *meaning* of the turn in any language — no keyword/regex layer is added, and none should be. **Conflict to flag:** do **not** wire the weather decision through `routing.py` or any keyword gate; that would reintroduce the English-only blind spot (§2.2) the tool is meant to eliminate. Leave `routing.py` for L3 topic selection only.

---

## 4. Latency & cost baseline

### 4.1 Current latency
No request-timing logs exist for the coach (only token usage is logged, `llm_client.py:83-87`) — so no server-side p50/p95 is available. Indicative shape: one non-streamed `messages.create` on `claude-sonnet-4-6`, `max_tokens=1024`, with a large prompt-cached prefix. Wall-clock ≈ one model round-trip + (cache-miss only) the static-block creation. When the client sends `lat/lon`, add one OWM call **unless** the 15-min cache is warm (`weather.py:405-409`).

### 4.2 Token footprint + tool-definition delta
- Prompt is two blocks: **static** (L0+L1+L2+instructions ≈ **5.1k tokens**, `_index.md` "Subtotal always-loaded"), prompt-cached via the breakpoint at `llm_client.py:63-69`; **dynamic** (≤3 L3 files + user context + today's always-on weather), budget-capped at **`TOKEN_BUDGET = 25_000`** (`prompt_builder.py:30`, `prompt_builder.py:624-638`).
- A `get_weather` tool definition (2 params + descriptions) ≈ **150-250 tokens**. In the Anthropic request the cache order is **tools → system → messages**; a *static* tool definition sits in the cached prefix, so after the first call it is billed at cache-read rate (~0.1×) — i.e. **near-zero marginal cost per message**, and it never invalidates the L0/L1/L2 cache as long as the tool schema is byte-stable (keep it as static as `INSTRUCTION_BLOCK`).
- **Net for the common (non-weather) case:** removing the always-on `_weather_section` fetch+injection *reduces* dynamic tokens and removes an OWM call. The tool definition adds a cached ~200 tokens. **Expected delta ≈ neutral-to-negative** (cheaper), not a regression.

### 4.3 Streaming
**Not streamed.** `messages.create` is the non-streaming call (`llm_client.py:73`); the client awaits a single `{reply}` JSON (`api.ts:943-950`) and renders it whole (`coach-card.tsx` / `coach/page.tsx`). Therefore a tool round-trip adds latency *only when a weather call actually fires*, and it is **invisible as a UX category** — there is no first-token contract to break. (If streaming is ever added later, the tool round-trip would precede the stream; note it for that future brief, not this one.)

### 4.4 Cost per message + projected delta
- **Today:** 1 model call (cached prefix + ≤25k dynamic, ≤1024 out) + 0-1 OWM calls, always paid on weather-eligible turns.
- **(a) Tool definition always present, no call:** +~200 cached input tokens ≈ negligible; **minus** the removed always-on weather tokens+fetch → **lower** average cost.
- **(b) Tool actually called:** +1 model round-trip (the follow-up with `tool_result`) + 1 OWM call (cache-permitting). Bounded to weather-intent turns only. Cap the loop (§5.2) so a misbehaving model can't fan out calls.

---

## 5. Guardrails & failure modes

### 5.1 What happens if weather fetch fails today
**Best-effort, silent drop.** Every fetch in `_weather_section` is wrapped: current-location failure logs `info` and skips the line (`prompt_builder.py:491-492`); a per-spot failure `continue`s (`prompt_builder.py:509-511`); unresolved geocode is skipped (`prompt_builder.py:507-508`). If nothing resolves, the section is omitted entirely (`prompt_builder.py:516-517`). The chat **never** fails or stalls on weather. **The tool must preserve this contract:** a tool execution error should return a structured "weather unavailable" `tool_result` (so the model can say "I can't pull conditions right now"), never raise into the chat handler.

### 5.2 Rate limiting
- **App-level only:** `DAILY_MESSAGE_LIMIT = 30` user messages/day, enforced in the router (`service.py:22`, `coach.py:50-57`). **No `slowapi` decorator on the coach routes** (grep clean) — unlike other sensitive endpoints.
- **Tool calls need their own inner cap.** Recommend **max 1-2 tool executions per coach message** in the loop, independent of the 30/day counter (which counts user turns, not tool round-trips). Without it, a model that keeps emitting `tool_use` could multiply OWM calls and model round-trips on a single user message. The OWM 15-min cache (`weather.py:405`) softens cost but is not a correctness bound.

### 5.3 Injection risk on the location string
- Today the location is **not** free-text from the message: it is validated `lat/lon` (`coach.py:36-37`, `Query(ge/le)` at `weather.py:442-443`) or a structured `outdoor_spot_name` from the user's own state (`prompt_builder.py:505`). `geocode_place` lowercases/strips and passes the name as an **httpx `params` value** (URL-encoded, not concatenated) — `weather.py:315-321`, `weather.py:338`.
- **With a tool, the `location` arg becomes model-generated free text** derived from user input — a new (low) surface. Mitigations for the A brief: length-cap + charset-sanitize the `location` arg; keep passing it via `params=` (never string-format into the URL); prefer resolving against the user's **known spots** first and only geocode as fallback; treat geocode-miss as "unavailable" (§5.1). No secrets are reachable from the arg; risk is bounded to "geocode a weird string", i.e. wasted call, not exfiltration.

---

## 6. Provider assessment (desk check)

### 6.1 OpenWeatherMap (current)
- Classic **free tier**: current + **5 day / 3 h** forecast, air pollution, geocoding; **60 calls/min, 1,000,000/month**; commercial use **permitted with visible attribution** (already noted in CLAUDE.md `OPENWEATHER_API_KEY` and `weather.py:8`). Sources below.
- **One Call 3.0** would add an **8-day daily** forecast + hourly-48h, but it is a separate **"One Call by Call"** subscription (card on file, 1,000 calls/day included then metered). Only needed if the tool must answer beyond ~5 days.
- **Verdict:** sufficient for a `get_weather(location, days≤5)` tool with **zero new integration** — the tool wraps `cached_conditions()` as-is.

### 6.2 Open-Meteo (candidate) — **BLOCKER for us**
- Hosted `api.open-meteo.com` is **free for non-commercial use only**; commercial use requires a paid subscription (`customer-api.open-meteo.com`) **or self-hosting** the open-source engine. climb-agent is a **paid product (Stripe live)** → the hosted free tier is **not licence-compatible**.
- The *data* is CC BY 4.0 (commercial OK with attribution), but that does not grant free use of the *hosted service*. 16-day forecast + keyless geocoding are attractive, but the commercial-licence gate is a hard stop.
- **Verdict:** **do not adopt** for the tool. The brief's "free, no API key" framing does not hold in our commercial context. Revisit only if we ever self-host or take a paid Open-Meteo plan — not for A-COACH-WEATHER-TOOL.

---

## Recommendation — A-COACH-WEATHER-TOOL (design direction, ≤1 page)

**Move weather from always-on pre-fetch to on-demand native tool use, wrapping the existing OWM stack.**

### Tool schema (draft)
```python
WEATHER_TOOL = {
    "name": "get_weather",
    "description": (
        "Get current conditions or a midday forecast (friction/temperature/"
        "humidity/wind) for a climbing location. Call ONLY when the user's "
        "question needs weather. Prefer the user's known spots; 'here' uses "
        "their current GPS if available."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {"type": "string",
                "description": "Spot/city name, or 'here' for current GPS."},
            "days_ahead": {"type": "integer", "minimum": 0, "maximum": 5,
                "description": "0 = now/today, 1-5 = forecast day offset."},
        },
        "required": ["location"],
    },
}
```
Executor: resolve `location` → coords (known spots first, else `geocode_place`, else 'here'→client `lat/lon`); map `days_ahead` → ISO date; call `cached_conditions(lat, lon, date?)`; return the normalized dict (temp, friction_score, band, headline, best_window, …). On any failure return `{"available": false, "reason": …}` — never raise.

### Trigger strategy
**Native tool use, nothing else.** The model decides from turn meaning → language-agnostic by construction (§3.3). **No keyword/regex/routing gate** (would reintroduce the §2.2 English-only blind spot). Delete the always-on `_weather_section` injection; keep `cached_conditions` + `geocode_place` as the executor's backend.

### Zero regression for normal questions — guaranteed
- No weather intent ⇒ model emits no `tool_use` ⇒ **no extra round-trip, no OWM call** (§4.3).
- Fixed overhead = the tool definition only: ~200 tokens, in the **cached prefix** (tools→system order) ⇒ near-zero marginal cost after call #1, and it does **not** invalidate the L0/L1/L2 cache if kept byte-stable (§4.2).
- Common case actually gets **cheaper/faster**: today's unconditional weather fetch+injection is removed.

### Interaction with B-COACH-CONTEXT-FIX
- **Order:** do **B-COACH-CONTEXT-FIX first**, then A-COACH-WEATHER-TOOL. B touches `_weather_section`/context assembly; A **removes** the always-on `_weather_section`. Landing A first would strand B's weather edits.
- **Shared touchpoints:** `prompt_builder._weather_section` (`prompt_builder.py:471-524`, deleted/relocated by A), `service.handle_chat` (`service.py:161-180`, gains the tool loop), `llm_client.chat` (`llm_client.py:56-96`, gains `tools` + loop).
- **BUG-2 (language):** re-baseline before fixing — there is no English-only rule to violate (§3.1). Likely a one-language-per-reply reinforcement in `INSTRUCTION_BLOCK`, not a weather concern. Keep it in B, not A.

### Open questions for Daniele
1. **BUG-2:** exact input + expected vs actual language? (No "English-only" rule exists — need the real repro to scope the fix — §3.1.)
2. **`days_ahead` ceiling:** 5 days (stay on OWM free) acceptable, or do we ever need 8-day → One Call 3.0 subscription? (§6.1)
3. **'here' semantics:** should the tool use client `lat/lon` when the user says "here/oggi", i.e. keep passing `lat/lon` from `ChatRequest` into the executor? (Yes recommended.)
4. **Inner tool-call cap:** confirm max 1-2 weather executions per message (§5.2).
5. **L3 routing English-only gap (§2.2):** separate future item, or fold a note into the roadmap now?

---

## Out-of-scope confirmations
No planner/replanner/macrocycle/resolve/progression/closed-loop module was touched or implicated. No STOP-gate module is on the migration path — the change is contained to `coach/` + the weather executor. No fix was applied (BUG-1/BUG-2 remain for B-COACH-CONTEXT-FIX). Provider stays OpenWeatherMap.

**Sources (§6):**
- [OpenWeatherMap — One Call API 3.0](https://openweathermap.org/api/one-call-3)
- [OpenWeatherMap — Self-service pricing & limits](https://openweathermap.org/full-price)
- [Open-Meteo — Pricing](https://open-meteo.com/en/pricing)
- [Open-Meteo — Terms](https://open-meteo.com/en/terms)
- [Open-Meteo — API Subscriptions for Commercial Use](https://openmeteo.substack.com/p/api-subscriptions-for-commercial)
