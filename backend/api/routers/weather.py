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
    catalog_condition_band,
    compute_dew_point,
    condition_band,
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
    precip = _is_precip_or_fog(code)

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
        "condition_band": condition_band(temp, humidity, dew_point, wind_kmh, precip),
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
    precip = _is_precip_or_fog(code)
    pop = step.get("pop")  # A227: probability of precipitation, 0..1

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
        "condition_band": condition_band(temp, humidity, dew_point, wind_kmh, precip),
        "is_forecast": True,
        "date": date,
        "source": "openweathermap",
    }


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
        payload = _normalize_forecast(_owm_get("forecast", lat, lon), date)
    else:
        payload = _normalize_current(_owm_get("weather", lat, lon))
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
