"""Weather router — live conditions + forecast proxy (A224).

Server-side proxy over the OpenWeatherMap free endpoints. Centralises the API
key, caching, and the deterministic ``condition_band`` computation so both
``/today`` (Goal A) and the future outdoor auto-fill (Goal B) consume one
normalized shape.

Provider: OpenWeatherMap free tier (commercial use permitted with attribution).
  - current:  GET /data/2.5/weather
  - forecast: GET /data/2.5/forecast  (5 day / 3-hour steps)
Neither returns dew point, so it is derived via Magnus-Tetens (``weather_v1``).

Gating: fail-closed via ``require_active_subscription`` — consistent with the
rest of the product surface (``body_part_picker`` / ``custom_session``).
"""

from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import require_active_subscription
from backend.engine.weather_v1 import (
    FRICTION_WEIGHTS,
    band_headline,
    catalog_condition_band,
    compute_dew_point,
    compute_friction_score,
    friction_components,
    metric_qualifiers,
    wind_label,
)

router = APIRouter(prefix="/api/weather", tags=["weather"])

_OWM_BASE = "https://api.openweathermap.org/data/2.5"
_OWM_KEY_ENV = "OPENWEATHER_API_KEY"
_HTTP_TIMEOUT_S = 6.0

# Server-side cache: key = (round(lat,2), round(lon,2), date|"current", time-bucket).
# ~1.1 km spatial resolution; 15-minute time buckets keep us far below OWM rate
# limits and prevent refetch on every render.
_CACHE_WINDOW_S = 15 * 60
_cache: Dict[tuple, Dict[str, Any]] = {}


class WeatherUnavailable(Exception):
    """Raised when the upstream provider can't be reached or no key is set."""


# --- OWM adapter (pure, provider-specific) ------------------------------------

def _is_precip_or_fog(owm_weather_id: int) -> bool:
    """OWM condition id < 800 → precipitation / snow / atmosphere (fog, mist).

    800 = clear sky, 80x = clouds (both fine for friction).
    """
    return owm_weather_id < 800


def _rain_mm(container: Dict[str, Any]) -> float:
    """Recent/step precipitation in mm from an OWM ``rain``/``snow`` block."""
    total = 0.0
    for key in ("rain", "snow"):
        block = container.get(key) or {}
        if isinstance(block, dict):
            total += float(block.get("1h") or block.get("3h") or 0.0)
    return round(total, 2)


def _friction_fields(
    temp: float, humidity: float, dew_point: float, wind_kmh: float,
    precip_active: bool, precip_mm: float,
) -> Dict[str, Any]:
    """A238 additive fields shared by current + forecast normalization."""
    score, band = compute_friction_score(temp, humidity, dew_point, wind_kmh, precip_active)
    return {
        "friction_score": score,
        "band": band,
        "condition_band": band,  # legacy key, now emits the 4-value vocabulary
        "dew_spread": round(temp - dew_point, 1),
        "headline": band_headline(band, temp, humidity, dew_point, wind_kmh, precip_active),
        "qualifiers": metric_qualifiers(temp, humidity, dew_point, wind_kmh, precip_mm),
    }


def _normalize_current(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map OWM /weather (units=metric) → normalized weather dict."""
    main = raw.get("main", {})
    wind = raw.get("wind", {})
    clouds = raw.get("clouds", {})
    weather0 = (raw.get("weather") or [{}])[0]

    temp = float(main["temp"])
    humidity = float(main["humidity"])
    dew_point = compute_dew_point(temp, humidity)
    wind_kmh = round(float(wind.get("speed", 0.0)) * 3.6, 1)  # m/s → km/h
    code = int(weather0.get("id", 800))
    rain_mm = _rain_mm(raw)  # A238: rain.1h/3h present during/right after rain
    precip = _is_precip_or_fog(code) or rain_mm > 0

    return {
        "temp": round(temp, 1),
        "feels_like": round(float(main["feels_like"]), 1) if main.get("feels_like") is not None else None,  # A227
        "humidity": round(humidity),
        "dew_point": dew_point,
        "wind": wind_kmh,
        "wind_label": wind_label(wind_kmh),
        "wind_deg": int(wind["deg"]) if wind.get("deg") is not None else None,  # A227
        "cloud_cover": int(clouds["all"]) if clouds.get("all") is not None else None,  # A227
        "precip_prob": None,  # A227: current endpoint has no pop; forecast does
        "condition_text": (weather0.get("description") or "").capitalize(),
        "condition_code": code,
        **_friction_fields(temp, humidity, dew_point, wind_kmh, precip, rain_mm),
        "recent_rain_mm": rain_mm,  # A238
        "best_window": None,  # A238: filled by cached_conditions when forecast is available
        "is_forecast": False,
        "date": None,
        "source": "openweathermap",
    }


def _normalize_forecast(raw: Dict[str, Any], date: str) -> Dict[str, Any]:
    """Map OWM /forecast (5d/3h) → normalized dict for the midday step of *date*.

    Picks the 3-hour step on *date* closest to 12:00 local as representative of
    the climbing day. Raises if *date* is outside the returned window.
    """
    steps = raw.get("list", [])
    on_date = [s for s in steps if str(s.get("dt_txt", "")).startswith(date)]
    if not on_date:
        raise WeatherUnavailable(f"No forecast available for {date}")

    def _dist_to_noon(step: Dict[str, Any]) -> int:
        hh = int(str(step["dt_txt"])[11:13])
        return abs(hh - 12)

    step = min(on_date, key=_dist_to_noon)
    main = step.get("main", {})
    wind = step.get("wind", {})
    clouds = step.get("clouds", {})
    weather0 = (step.get("weather") or [{}])[0]

    temp = float(main["temp"])
    humidity = float(main["humidity"])
    dew_point = compute_dew_point(temp, humidity)
    wind_kmh = round(float(wind.get("speed", 0.0)) * 3.6, 1)
    code = int(weather0.get("id", 800))
    pop = step.get("pop")  # A227: probability of precipitation, 0..1
    rain_mm = _rain_mm(step)
    precip = _is_precip_or_fog(code) or rain_mm > 0 or (pop is not None and float(pop) > 0.3)

    return {
        "temp": round(temp, 1),
        "feels_like": round(float(main["feels_like"]), 1) if main.get("feels_like") is not None else None,  # A227
        "humidity": round(humidity),
        "dew_point": dew_point,
        "wind": wind_kmh,
        "wind_label": wind_label(wind_kmh),
        "wind_deg": int(wind["deg"]) if wind.get("deg") is not None else None,  # A227
        "cloud_cover": int(clouds["all"]) if clouds.get("all") is not None else None,  # A227
        "precip_prob": round(float(pop) * 100) if pop is not None else None,  # A227: 0..1 → %
        "condition_text": (weather0.get("description") or "").capitalize(),
        "condition_code": code,
        **_friction_fields(temp, humidity, dew_point, wind_kmh, precip, rain_mm),
        "recent_rain_mm": rain_mm,  # A238
        "best_window": None,  # A238: filled by cached_conditions from the same raw
        "is_forecast": True,
        "date": date,
        "source": "openweathermap",
    }


# --- A238: best window of the day ----------------------------------------------

_BEST_WINDOW_MIN_GAIN = 10   # must beat the current score by ≥10 points
_BEST_WINDOW_RUN_TOL = 5     # contiguous run: steps within 5 points of the peak
_DAYLIGHT_HOURS = (7, 21)    # local clock window considered climbable

_REASON_LABELS = {
    "temp": lambda cur, best: (
        f"temp drops to {round(best['temp'])}°C" if best["temp"] < cur["temp"]
        else f"temp rises to {round(best['temp'])}°C"
    ),
    "dew_spread": lambda cur, best: f"drier air (spread {round(best['temp'] - best['dew_point'])}°)",
    "humidity": lambda cur, best: f"humidity drops to {round(best['humidity'])}%",
    "wind": lambda cur, best: ("wind eases" if best["wind"] < cur["wind"] else "more breeze"),
}


def _score_step(step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Minimal normalization + friction score for one 3h forecast step."""
    try:
        main = step.get("main", {})
        temp = float(main["temp"])
        humidity = float(main["humidity"])
    except (KeyError, TypeError, ValueError):
        return None
    dew_point = compute_dew_point(temp, humidity)
    wind_kmh = round(float((step.get("wind") or {}).get("speed", 0.0)) * 3.6, 1)
    code = int(((step.get("weather") or [{}])[0]).get("id", 800))
    pop = step.get("pop")
    rain = _rain_mm(step)
    precip = _is_precip_or_fog(code) or rain > 0 or (pop is not None and float(pop) > 0.3)
    score, band = compute_friction_score(temp, humidity, dew_point, wind_kmh, precip)
    return {
        "temp": temp, "humidity": humidity, "dew_point": dew_point, "wind": wind_kmh,
        "score": score, "band": band, "dt": int(step.get("dt", 0)),
    }


def best_window(
    forecast_raw: Dict[str, Any], local_date: str, current: Dict[str, Any], now_dt: int = 0
) -> Optional[Dict[str, Any]]:
    """Best later window of *local_date* from the 3h forecast steps (A238).

    Scores every step whose LOCAL start time falls on ``local_date`` within
    daylight hours, strictly in the future. Returns the peak step expanded to
    the contiguous run within ``_BEST_WINDOW_RUN_TOL`` points — only when the
    peak beats the current score by ≥ ``_BEST_WINDOW_MIN_GAIN``. ``reason`` is
    the component with the largest weighted improvement vs. now. None when now
    is already (close to) the best the day offers, or on any malformed input.
    """
    try:
        tz_offset = int((forecast_raw.get("city") or {}).get("timezone", 0))
        scored = []
        for step in forecast_raw.get("list", []):
            s = _score_step(step)
            if s is None or s["dt"] <= now_dt:
                continue
            local = time.gmtime(s["dt"] + tz_offset)
            if time.strftime("%Y-%m-%d", local) != local_date:
                continue
            if not (_DAYLIGHT_HOURS[0] <= local.tm_hour < _DAYLIGHT_HOURS[1]):
                continue
            s["local_hm"] = time.strftime("%H:%M", local)
            s["local_end_hm"] = time.strftime("%H:%M", time.gmtime(s["dt"] + tz_offset + 3 * 3600))
            scored.append(s)
        if not scored:
            return None

        peak_i = max(range(len(scored)), key=lambda i: scored[i]["score"])
        peak = scored[peak_i]
        if peak["score"] < int(current["friction_score"]) + _BEST_WINDOW_MIN_GAIN:
            return None

        lo = peak_i
        while lo > 0 and scored[lo - 1]["score"] >= peak["score"] - _BEST_WINDOW_RUN_TOL \
                and scored[lo]["dt"] - scored[lo - 1]["dt"] == 3 * 3600:
            lo -= 1
        hi = peak_i
        while hi < len(scored) - 1 and scored[hi + 1]["score"] >= peak["score"] - _BEST_WINDOW_RUN_TOL \
                and scored[hi + 1]["dt"] - scored[hi]["dt"] == 3 * 3600:
            hi += 1

        cur_comps = friction_components(
            float(current["temp"]), float(current["humidity"]),
            float(current["dew_point"]), float(current["wind"]),
        )
        best_comps = friction_components(peak["temp"], peak["humidity"], peak["dew_point"], peak["wind"])
        gains = {k: (best_comps[k] - cur_comps[k]) * FRICTION_WEIGHTS[k] for k in FRICTION_WEIGHTS}
        top = max(gains, key=lambda k: gains[k])
        reason = _REASON_LABELS[top](current, peak) if gains[top] > 0 else "conditions improve"

        return {
            "from": scored[lo]["local_hm"],
            "to": scored[hi]["local_end_hm"],
            "score": peak["score"],
            "band": peak["band"],
            "reason": reason,
        }
    except Exception:
        return None  # best-effort — never break the weather payload


# --- network layer (mocked in tests) ------------------------------------------

def _owm_get(path: str, lat: float, lon: float) -> Dict[str, Any]:
    """Call an OWM endpoint and return raw JSON. Tests monkeypatch this.

    Reads the API key here (not at import) so that pytest — which never reaches
    this function because it patches it — needs no key.
    """
    key = os.environ.get(_OWM_KEY_ENV, "").strip()
    if not key:
        raise WeatherUnavailable("OPENWEATHER_API_KEY not configured")
    try:
        resp = httpx.get(
            f"{_OWM_BASE}/{path}",
            params={"lat": lat, "lon": lon, "appid": key, "units": "metric", "lang": "en"},
            timeout=_HTTP_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise WeatherUnavailable(f"upstream error: {exc}") from exc


# --- geocoding (A-COACH-V1b) ---------------------------------------------------

_OWM_GEO_BASE = "https://api.openweathermap.org/geo/1.0"


def _owm_geocode_get(q: str) -> Any:
    """Raw OWM direct-geocoding call. Tests monkeypatch this."""
    key = os.environ.get(_OWM_KEY_ENV, "").strip()
    if not key:
        raise WeatherUnavailable("OPENWEATHER_API_KEY not configured")
    try:
        resp = httpx.get(
            f"{_OWM_GEO_BASE}/direct",
            params={"q": q, "limit": 1, "appid": key},
            timeout=_HTTP_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise WeatherUnavailable(f"geocoding upstream error: {exc}") from exc


# Cache resolved lookups only (successes + confirmed not-found) — a transient
# provider failure must NOT stick for the process lifetime.
_geo_cache: Dict[str, Optional[Tuple[float, float]]] = {}


def geocode_place(name: str) -> Optional[Tuple[float, float]]:
    """Resolve a place name (e.g. an outdoor spot) to (lat, lon).

    In-memory cache only — no user_state writes from the lookup path.
    Returns None when the provider is unconfigured/unreachable or the name
    doesn't resolve.
    """
    q = (name or "").strip().lower()
    if not q:
        return None
    if q in _geo_cache:
        return _geo_cache[q]
    try:
        results = _owm_geocode_get(q)
    except WeatherUnavailable:
        return None  # transient / unconfigured — do not cache
    coords: Optional[Tuple[float, float]] = None
    if results and isinstance(results, list):
        try:
            coords = (float(results[0]["lat"]), float(results[0]["lon"]))
        except (KeyError, TypeError, ValueError):
            coords = None
    if len(_geo_cache) < 256:
        _geo_cache[q] = coords
    return coords


# --- outdoor auto-fill helper (A225) ------------------------------------------

def fetch_outdoor_conditions(
    lat: float, lon: float, date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Derive outdoor conditions (``temperature``, ``humidity``, ``wind``,
    ``condition_band``) for an outdoor day, reusing the same provider +
    normalization as the live card.

    Returns ``None`` (gracefully) when the provider is unreachable/unconfigured or
    the date is outside the forecast window — the caller then falls back to the
    catalog base (no condition_band patch). Network is mocked in tests via
    ``_owm_get``.
    """
    try:
        if date:
            payload = _normalize_forecast(_owm_get("forecast", lat, lon), date)
        else:
            payload = _normalize_current(_owm_get("weather", lat, lon))
    except WeatherUnavailable:
        return None

    return {
        "temperature": payload["temp"],
        "feels_like": payload.get("feels_like"),  # A227
        "humidity": payload["humidity"],
        "dew_point": payload.get("dew_point"),  # A227
        "wind": payload["wind"],
        "wind_label": payload["wind_label"],
        "wind_deg": payload.get("wind_deg"),  # A227
        "cloud_cover": payload.get("cloud_cover"),  # A227
        "precip_prob": payload.get("precip_prob"),  # A227
        "condition_band": catalog_condition_band(payload["temp"], payload["condition_band"]),
        "weather_band_raw": payload["condition_band"],
        # A238 — additive: same friction verdict as the live card, so the
        # outdoor widget renders identical band/headline/chips.
        "band": payload.get("band"),
        "friction_score": payload.get("friction_score"),
        "dew_spread": payload.get("dew_spread"),
        "headline": payload.get("headline"),
        "qualifiers": payload.get("qualifiers"),
    }


def cached_conditions(
    lat: float, lon: float, date: Optional[str] = None
) -> Dict[str, Any]:
    """Normalized current/forecast conditions through the shared 15-min cache.

    Single fetch path for the ``/api/weather`` route AND the coach context
    (A-COACH-V1b) — a chat turn right after the /today card render is a cache
    hit, not a second OWM call. Raises WeatherUnavailable on provider failure.
    """
    bucket = math.floor(time.time() / _CACHE_WINDOW_S)
    cache_key = (round(lat, 2), round(lon, 2), date or "current", bucket)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    if date:
        raw = _owm_get("forecast", lat, lon)
        payload = _normalize_forecast(raw, date)
        payload["best_window"] = best_window(raw, date, payload)
    else:
        raw_cur = _owm_get("weather", lat, lon)
        payload = _normalize_current(raw_cur)
        # A238 best-effort: score the rest of the local day from the forecast.
        # Any failure (provider, malformed payload) leaves best_window = None.
        try:
            now_dt = int(raw_cur.get("dt") or time.time())
            tz_offset = int(raw_cur.get("timezone") or 0)
            local_date = time.strftime("%Y-%m-%d", time.gmtime(now_dt + tz_offset))
            payload["best_window"] = best_window(
                _owm_get("forecast", lat, lon), local_date, payload, now_dt=now_dt
            )
        except (WeatherUnavailable, ValueError, TypeError):
            pass
    _cache[cache_key] = payload
    return payload


# --- route --------------------------------------------------------------------

@router.get("", dependencies=[Depends(require_active_subscription)])
def get_weather(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    date: Optional[str] = Query(None, description="YYYY-MM-DD for forecast; omit for current"),
) -> Dict[str, Any]:
    """Current conditions (Goal A) or forecast-by-date for a location (Goal B).

    Returns ``{temp, humidity, dew_point, wind, condition_text, condition_code,
    condition_band, is_forecast, date, source}``. 503 when the provider is
    unreachable / unconfigured (frontend hides the card gracefully).
    """
    try:
        return cached_conditions(lat, lon, date)
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail={"error": "weather_unavailable", "message": str(exc)})
