"""A244 — on-demand weather via native tool use (A-COACH-WEATHER-TOOL).

The coach calls ``get_weather`` ONLY when a turn needs conditions/forecast.
This replaces the always-on pre-fetch (D253): non-weather turns pay nothing but
the cached tool definition, and the trigger is language-agnostic (the model
decides, no keyword layer). The executor wraps the existing OWM stack
(``cached_conditions`` + ``geocode_place``) — same normalized shape, same
15-minute cache, same friction score WE compute ourselves.

Contract: the executor NEVER raises into the chat loop. On any failure it
returns a short "unavailable" string so the model can tell the user it can't
pull conditions (and the anti-invention rule in the tool description +
instruction block stops it from guessing).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_FORECAST_DAYS = 5        # OWM free forecast horizon (5 day / 3h steps)
MAX_LOCATION_CHARS = 100     # injection guard on the model-supplied string

# Words that mean "use the user's current GPS position" instead of a place name.
_HERE_TOKENS = {
    "here", "now", "current", "current location", "my location", "today",
    "qui", "qua", "adesso", "ora", "oggi", "posizione attuale",
}

WEATHER_TOOL: Dict[str, Any] = {
    "name": "get_weather",
    "description": (
        "Get real climbing-conditions weather for a location: temperature, "
        "humidity, dew-point spread, wind speed AND compass direction, cloud "
        "cover, precipitation and a 0-100 friction score (higher = better "
        "friction). The result also carries sunrise/sunset and an hour-by-hour "
        "strip in 3-hour steps, so you CAN answer questions about a specific "
        "window ('what will it be like between 14:00 and 20:00') and about "
        "remaining daylight — read those hours from the strip, never "
        "interpolate or estimate them. All times in the result are LOCAL at "
        "that location. Call this ONLY when the user's message needs weather / "
        "conditions / friction for a place or a day — never for unrelated "
        "questions. Set location='here' to use the user's current GPS "
        "position, or pass a crag/city name. days_ahead=0 is now/today; 1-5 is "
        "that many days into the future (forecast horizon is 5 days). If the "
        "result says the data is unavailable, tell the user you can't pull "
        "conditions right now — never invent numbers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "A crag/city name, or 'here' for the user's current GPS.",
            },
            "days_ahead": {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_FORECAST_DAYS,
                "description": "0 = now/today; 1-5 = days ahead (forecast).",
            },
        },
        "required": ["location"],
    },
}


MAX_HOURLY_STEPS = 8  # a full local day of 3-hour steps


def _fmt_wind(w: Dict[str, Any]) -> str:
    """Speed + compass bearing. A275: direction decides whether a NE-facing
    crag is in the wind or sheltered, so it must never be dropped."""
    out = f"wind {w['wind']} km/h"
    if w.get("wind_dir"):
        out += f" from {w['wind_dir']}"
    if w.get("wind_label"):
        out += f" ({w['wind_label']})"
    return out


def _fmt_hourly(steps: list) -> str:
    """A275 — compact hour-by-hour strip, in the crag's local time.

    One line per 3-hour step so the model can answer "what about 14:00–20:00"
    by reading, not by interpolating between a single midday number and its own
    imagination. Times are local at the crag; the label says so, because a
    model that assumes UTC would hand back a three-hour lie.
    """
    rows = []
    for s in steps[:MAX_HOURLY_STEPS]:
        bits = [f"{s.get('time', '?')}", f"{s['temp']}°C"]
        if s.get("cloud_cover") is not None:
            bits.append(f"cloud {s['cloud_cover']}%")
        bits.append(_fmt_wind(s))
        bits.append(f"RH {s['humidity']}%")
        if s.get("precip_prob"):
            bits.append(f"precip {s['precip_prob']}%")
        bits.append(f"{s.get('band', '?')} {s.get('friction_score', '?')}/100")
        rows.append(" ".join(bits))
    return "hour by hour (LOCAL time at the location): " + " | ".join(rows)


def _fmt_conditions(w: Dict[str, Any]) -> str:
    """One-line human summary of a normalized weather dict (A238/A275 shape)."""
    bits = [f"{w['temp']}°C", f"humidity {w['humidity']}%"]
    if w.get("dew_point") is not None:
        bits.append(f"dew point {w['dew_point']}°C")
    bits.append(_fmt_wind(w))
    if w.get("cloud_cover") is not None:
        bits.append(f"cloud cover {w['cloud_cover']}%")  # A275
    if w.get("precip_prob") is not None:
        bits.append(f"precip {w['precip_prob']}%")
    if w.get("condition_text"):
        bits.append(str(w["condition_text"]).lower())
    band_bit = f"friction band: {w.get('condition_band') or w.get('band', '?')}"
    if w.get("friction_score") is not None:
        band_bit += f" ({w['friction_score']}/100)"
    bits.append(band_bit)
    if w.get("headline"):
        bits.append(f"— {w['headline']}")
    bw = w.get("best_window")
    if bw and bw.get("from"):
        bits.append(
            f"best window today {bw['from']}–{bw['to']} "
            f"({bw.get('reason', 'better conditions')})"
        )
    # A275 — daylight. "Is there time for one more route" is a sunset question.
    if w.get("sunset"):
        sun = f"sunset {w['sunset']} local"
        if w.get("sunrise"):
            sun = f"sunrise {w['sunrise']} / " + sun
        if w.get("sun_date") and w.get("date") and w["sun_date"] != w["date"]:
            sun += f" (these sun times are for {w['sun_date']}, ±a few minutes)"
        bits.append(sun)
    line = ", ".join(bits)
    if w.get("hourly"):
        line += ". " + _fmt_hourly(w["hourly"])
    return line


def _resolve_location(
    location: str,
    state: Dict[str, Any],
    lat: Optional[float],
    lon: Optional[float],
) -> Tuple[Optional[Tuple[float, float]], str]:
    """Return ((lat, lon), label) or (None, reason).

    'here'/'now'/… → the client GPS (if provided); anything else → geocoded by
    name (outdoor spots store no coordinates, only a name — same path the old
    pre-fetch used). No user_state writes.
    """
    q = (location or "").strip()[:MAX_LOCATION_CHARS]
    if not q:
        return None, "no location was given"
    if q.lower() in _HERE_TOKENS:
        if lat is not None and lon is not None:
            return (lat, lon), "your current location"
        return None, "no GPS location is available for 'here'"

    from backend.api.routers.weather import geocode_place

    coords = geocode_place(q)
    if coords:
        return coords, q
    return None, f"couldn't find a location matching '{q}'"


def execute_get_weather(
    tool_input: Dict[str, Any],
    state: Dict[str, Any],
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> str:
    """Run one ``get_weather`` tool call. Always returns a string, never raises."""
    from backend.api.routers.weather import WeatherUnavailable, cached_conditions

    location = str(tool_input.get("location") or "")
    try:
        days = int(tool_input.get("days_ahead") or 0)
    except (TypeError, ValueError):
        days = 0
    days = max(0, min(days, MAX_FORECAST_DAYS))

    coords, label = _resolve_location(location, state, lat, lon)
    if coords is None:
        return f"Weather unavailable — {label}."

    target_date = (
        None if days == 0 else (date.today() + timedelta(days=days)).isoformat()
    )
    try:
        w = cached_conditions(coords[0], coords[1], target_date)
    except WeatherUnavailable:
        return f"Weather for {label} is unavailable right now (provider unreachable)."
    except Exception:  # noqa: BLE001 — never break the chat loop
        logger.exception("coach get_weather: unexpected failure")
        return f"Weather for {label} is unavailable right now."

    # A275: the leading numbers are still one representative step (now, or the
    # forecast's midday step). Say which, so the model quotes the hourly strip
    # rather than the headline when the user asked about a specific hour.
    when = (
        "now, plus the rest of today hour by hour" if days == 0
        else f"in {days} day(s) — summary from the midday step, plus that day hour by hour"
    )
    return f"Weather at {label} ({when}): {_fmt_conditions(w)}"
