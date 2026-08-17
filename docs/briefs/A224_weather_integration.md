# A224 — Weather Capability: integration notes

**Type:** A (feature) · **Risk:** LOW (no engine modules touched) · **Date:** 2026-06-19

Server-side weather proxy + live `/today` widget (Goal A), plus reusable infra
for future outdoor auto-fill (Goal B). Weather and outdoor stay **decoupled**:
the widget ships independently; outdoor wiring is a separate brief.

## Provider & licensing decision (Phase 1)

- **Chosen:** OpenWeatherMap free tier (commercial use permitted **with
  attribution**), endpoints `GET /data/2.5/weather` and `GET /data/2.5/forecast`
  (5 day / 3-hour). No card required; 60 calls/min, 1M/month.
- **Rejected:** Open-Meteo. Best data (native `dew_point_2m`, no key) **but its
  free tier explicitly forbids commercial use** — climb-agent is paid
  production. Its commercial plan starts at $29/mo; not adopted.
- **Dew point** is not returned by the OWM free endpoints → derived
  deterministically via Magnus-Tetens in `backend/engine/weather_v1.py`
  (`compute_dew_point`, ~±0.4°C).
- **Attribution:** OWM requires visible attribution. TODO before/at scale —
  add a "Weather by OpenWeather" credit near the widget or in the legal page.

## Architecture

Server-side proxy (`backend/api/routers/weather.py`), `GET /api/weather`:
- params: `lat`, `lon` (required), `date` (optional `YYYY-MM-DD` → forecast).
- returns: `{ temp, humidity, dew_point, wind, condition_text, condition_code,
  condition_band, is_forecast, date, source }`.
- gating: **fail-closed** via `require_active_subscription` (consistent with the
  rest of the product surface).
- caching: in-memory, keyed by `(round(lat,2), round(lon,2), date|"current",
  15-min bucket)` → ~1.1 km resolution, far below OWM rate limits.
- key: env var `OPENWEATHER_API_KEY` (Railway + Vercel). Unset → 503
  `weather_unavailable`; the frontend hides the card gracefully.

## `condition_band` rule (deterministic, `weather_v1.condition_band`)

Provider-agnostic `(temp, humidity, dew_point, wind, is_precip_or_fog) →
{prime, ok, poor}`. Weakest-link (Liebig) rule:

0. Precipitation / snow / fog (OWM id < 800) → `poor` (wet / condensing rock).
1. Band = worse of (dew-point band, air-temperature band):
   - dew ≤ 8°C → prime · 8–14°C → ok · > 14°C → poor
   - −2..16°C → prime · −6..−2 / 16..24°C → ok · < −6 / > 24°C → poor
2. Wind > 40 km/h caps the band at `ok` (unsafe/uncomfortable on lead).

Thresholds are tunable constants at the top of `weather_v1.py`. Sun-aspect is
out of v1 (not auto-fetchable).

## Goal B — outdoor auto-fill integration point (infra ready, NOT wired here)

The endpoint already supports the outdoor case: pass the **crag location + the
planned date** to `GET /api/weather?lat=&lon=&date=YYYY-MM-DD` and it returns the
midday-step forecast + `condition_band`. The outdoor day will use this to
auto-fill `OutdoorSessionLog.conditions` (a free JSONB container, already
present — see D247 §1a) and surface `condition_band`.

**GAP to close in the outdoor brief (from D247):** outdoor spots currently have
**no coordinates** — `OutdoorSpotCreate` is `{name, discipline, typical_days,
notes}` only (`backend/api/models.py:173`). Full crag-forecast wiring needs spot
`lat/lon` (a future field) **or** a manual location input. Until then, fall back
to current position (already wired in the `/today` widget) or manual entry.

**Out of scope here:** the UI wiring into the outdoor day. Auto-fill switches on
when both this infra and the outdoor design brief are ready.

## Deployment checklist

- [ ] Set `OPENWEATHER_API_KEY` on Railway (backend) — required for live data.
- [ ] (Vercel) no frontend key needed — calls go through the backend proxy.
- [ ] Add OpenWeather attribution near the widget (license requirement).
