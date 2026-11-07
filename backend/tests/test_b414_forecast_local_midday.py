"""B414 (step 21) — B-FORECAST-MIDDAY-STEP.

The forecast summary of a day is the 3-hour step closest to midday. Both the
day filter and the distance to noon read OWM's ``dt_txt``, which is UTC: in an
Italian summer (UTC+2) the step picked was 14:00 local, at UTC+3 15:00. Now
both read the crag-local clock (``dt`` + ``city.timezone``) — the same
bucketing as ``hourly_steps`` — and a step without ``dt`` falls back to its
``dt_txt`` read as UTC. Which hour represents the day (midday) is unchanged.
Provider always mocked — no network.
"""

from __future__ import annotations

import calendar
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers import weather as weather_router

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cache():
    weather_router._cache.clear()
    yield
    weather_router._cache.clear()


def _utc(day: str, hour: int) -> int:
    return calendar.timegm(time.strptime(f"{day} {hour:02d}:00:00", "%Y-%m-%d %H:%M:%S"))


def _step(dt: int, temp: float, *, with_dt: bool = True) -> dict:
    s = {
        "dt_txt": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(dt)),  # UTC, as OWM labels it
        "main": {"temp": temp, "humidity": 50},
        "wind": {"speed": 2.0, "deg": 180},
        "weather": [{"id": 800, "description": "clear sky"}],
    }
    if with_dt:
        s["dt"] = dt
    return s


def _forecast(tz: int, steps: list) -> dict:
    return {"city": {"timezone": tz}, "list": steps}


# Temperatures encode the UTC hour of the step: 6 → 6.0 °C, 9 → 9.0 °C …
def _day(day: str, tz: int, hours=(0, 3, 6, 9, 12, 15, 18, 21), *, with_dt: bool = True) -> dict:
    return _forecast(tz, [_step(_utc(day, h), float(h), with_dt=with_dt) for h in hours])


def test_utc_plus_2_picks_11_local_not_14():
    """Italian summer: steps at 11:00 and 14:00 local → 11:00 (09 UTC)."""
    out = weather_router._normalize_forecast(_day("2026-07-15", 7200), "2026-07-15")
    assert out["temp"] == 9.0  # 09 UTC = 11:00 local; before: 12 UTC = 14:00 local
    assert out["date"] == "2026-07-15" and out["timezone_offset_s"] == 7200


def test_utc_plus_3_picks_local_noon_and_filters_the_local_day():
    """Kalymnos: 09 UTC is 12:00 local. The local day runs 21 UTC of the day
    before → 18 UTC: a step at 21 UTC of the 15th is the 16th locally."""
    raw = _forecast(10800, [
        _step(_utc("2026-07-14", 21), 99.0),   # 00:00 local on the 15th
        _step(_utc("2026-07-15", 9), 9.0),     # 12:00 local
        _step(_utc("2026-07-15", 12), 12.0),   # 15:00 local (the old pick)
        _step(_utc("2026-07-15", 21), 21.0),   # 00:00 local on the 16th
    ])
    out = weather_router._normalize_forecast(raw, "2026-07-15")
    assert out["temp"] == 9.0
    # Same day membership as the hourly strip.
    strip = weather_router.hourly_steps(raw, "2026-07-15", 10800)
    assert [s["dt"] for s in strip] == [_utc("2026-07-14", 21), _utc("2026-07-15", 9), _utc("2026-07-15", 12)]
    # Only the 00:00-local step of the 16th → it is the 16th's summary, not the 15th's.
    late = _forecast(10800, [_step(_utc("2026-07-15", 21), 21.0)])
    with pytest.raises(weather_router.WeatherUnavailable):
        weather_router._normalize_forecast(late, "2026-07-15")
    assert weather_router._normalize_forecast(late, "2026-07-16")["temp"] == 21.0


def test_italian_winter_unchanged():
    """UTC+1: 12 UTC is 13:00 local, still the nearest step to noon."""
    out = weather_router._normalize_forecast(_day("2026-01-15", 3600), "2026-01-15")
    assert out["temp"] == 12.0


def test_fallback_on_dt_txt_reads_it_as_utc():
    """A step without ``dt``: its ``dt_txt`` is UTC, shifted to local like dt."""
    with_dt = weather_router._normalize_forecast(_day("2026-07-15", 7200), "2026-07-15")
    without = weather_router._normalize_forecast(_day("2026-07-15", 7200, with_dt=False), "2026-07-15")
    assert without["temp"] == with_dt["temp"] == 9.0
    # No timezone and no dt (the legacy fixtures): exactly the old UTC reading.
    out = weather_router._normalize_forecast(_day("2026-07-15", 0, with_dt=False), "2026-07-15")
    assert out["temp"] == 12.0


def test_tie_keeps_the_earlier_step():
    """UTC+1:30 → steps at 10:30 and 13:30 local are both 90' from noon: the
    earlier one wins (provider order), deterministic."""
    out = weather_router._normalize_forecast(_day("2026-07-15", 5400), "2026-07-15")
    assert out["temp"] == 9.0


def test_endpoint_forecast_by_date_uses_local_midday(monkeypatch):
    raw = _day("2026-07-15", 7200)
    raw["city"].update({"sunrise": _utc("2026-07-15", 4), "sunset": _utc("2026-07-15", 19)})

    def _get(path, lat, lon):
        if path == "forecast":
            return raw
        raise weather_router.WeatherUnavailable("only the forecast is mocked")

    monkeypatch.setattr(weather_router, "_owm_get", _get)
    body = client.get("/api/weather", params={"lat": 45.9, "lon": 10.9, "date": "2026-07-15"}).json()
    assert body["is_forecast"] is True
    assert body["temp"] == 9.0
