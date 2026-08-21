"""Tests for A275 — hourly weather strip, sun times, wind direction.

The question A275 exists to answer is "what is it like at the crag between
14:00 and 20:00", which the A224/A238 payload could not answer: it collapsed a
climbing day into one step near midday and never exposed sunset. Provider
always mocked — no network in CI.

Timezone matters here and is not incidental: the bug these tests pin down only
shows up when the crag's local clock disagrees with UTC, so the fixture is
Kalymnos (UTC+3, EEST), not the author's home timezone.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers import weather as weather_router
from backend.engine.weather_v1 import wind_direction_label

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cache():
    weather_router._cache.clear()
    yield
    weather_router._cache.clear()


# --- fixtures -----------------------------------------------------------------

_TZ = 3 * 3600                # Kalymnos, EEST (UTC+3)
_DAY0_UTC = 1787270400        # 2026-08-21 00:00:00 UTC → 03:00 local
# 2026-08-21 00:00 LOCAL is three hours earlier, i.e. 2026-08-20 21:00 UTC.
_LOCAL_MIDNIGHT_UTC = _DAY0_UTC - _TZ
_SUNRISE = _LOCAL_MIDNIGHT_UTC + 6 * 3600 + 45 * 60   # 06:45 local
_SUNSET = _LOCAL_MIDNIGHT_UTC + 19 * 3600 + 55 * 60   # 19:55 local


def _step(dt: int, temp: float, humidity: float = 55.0,
          wind_ms: float = 3.8, deg: int = 348, clouds: int = 0):
    return {
        "dt": dt,
        # UTC, exactly as OWM labels it — the day summary reads this field and
        # the hourly strip deliberately does not.
        "dt_txt": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(dt)),
        "main": {"temp": temp, "feels_like": temp + 2, "humidity": humidity},
        "wind": {"speed": wind_ms, "deg": deg},
        "clouds": {"all": clouds},
        "weather": [{"id": 800, "description": "clear sky"}],
        "pop": 0.0,
    }


def _at_local(hour: int) -> int:
    """2026-08-21 <hour>:00 local → unix UTC."""
    return _LOCAL_MIDNIGHT_UTC + hour * 3600


# A real OWM day: steps land on 00/03/…/21 UTC = 03/06/…/24 local at UTC+3.
_FORECAST = {
    "city": {"timezone": _TZ, "sunrise": _SUNRISE, "sunset": _SUNSET},
    "list": [
        _step(_at_local(h), temp)
        for h, temp in [
            (3, 26.0), (6, 26.5), (9, 28.5), (12, 30.5),
            (15, 30.0), (18, 28.0), (21, 26.5),
        ]
    ] + [
        # next local day — must NOT leak into 2026-08-21's strip
        _step(_at_local(24), 26.0),
    ],
}

_CURRENT = {
    "dt": _at_local(11),
    "timezone": _TZ,
    "main": {"temp": 29.3, "feels_like": 31.2, "humidity": 58},
    "wind": {"speed": 3.75, "deg": 348},
    "clouds": {"all": 0},
    "weather": [{"id": 800, "description": "clear sky"}],
    "sys": {"sunrise": _SUNRISE, "sunset": _SUNSET},
}


def _mock(monkeypatch, current=None, forecast=None):
    cur, fc = current or _CURRENT, forecast or _FORECAST

    def _get(path, lat, lon):
        return fc if path == "forecast" else cur
    monkeypatch.setattr(weather_router, "_owm_get", _get)


# --- wind direction -----------------------------------------------------------

def test_wind_direction_16_point_compass():
    assert wind_direction_label(0) == "N"
    assert wind_direction_label(348) == "NNW"     # today's real Kalymnos bearing
    assert wind_direction_label(90) == "E"
    assert wind_direction_label(225) == "SW"
    assert wind_direction_label(359) == "N"       # wraps, never index 16
    assert wind_direction_label(360) == "N"
    assert wind_direction_label(720 + 45) == "NE"  # normalises beyond one turn


def test_wind_direction_missing_bearing_is_none():
    assert wind_direction_label(None) is None
    assert wind_direction_label("calm") is None


# --- hourly strip -------------------------------------------------------------

def test_hourly_buckets_by_local_day_not_utc(monkeypatch):
    """The whole point: at UTC+3 the UTC day and the local day disagree."""
    steps = weather_router.hourly_steps(_FORECAST, "2026-08-21", _TZ)
    assert [s["time"] for s in steps] == [
        "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00",
    ]
    # The 00:00-local step of the NEXT day was present in the payload and must
    # not appear here.
    assert "00:00" not in [s["time"] for s in steps]


def test_hourly_covers_the_afternoon_window(monkeypatch):
    """14:00–20:00 is covered by the 15:00 and 18:00 steps, with real numbers."""
    steps = weather_router.hourly_steps(_FORECAST, "2026-08-21", _TZ)
    window = [s for s in steps if "12:00" <= s["time"] <= "21:00"]
    assert [s["time"] for s in window] == ["12:00", "15:00", "18:00", "21:00"]
    afternoon = {s["time"]: s for s in window}
    assert afternoon["15:00"]["temp"] == 30.0
    assert afternoon["18:00"]["temp"] == 28.0
    # Cooling into the evening must show as a rising friction score.
    assert afternoon["18:00"]["friction_score"] > afternoon["15:00"]["friction_score"]


def test_hourly_entry_carries_full_metrics_and_verdict():
    step = weather_router.hourly_steps(_FORECAST, "2026-08-21", _TZ)[4]  # 15:00
    for key in ("time", "end_time", "dt", "temp", "feels_like", "humidity",
                "dew_point", "wind", "wind_label", "wind_deg", "wind_dir",
                "cloud_cover", "precip_prob", "condition_text", "friction_score",
                "band", "dew_spread", "qualifiers"):
        assert key in step, f"missing {key}"
    assert step["end_time"] == "18:00"
    assert step["wind_dir"] == "NNW"


def test_hourly_drops_elapsed_steps_but_keeps_the_current_one():
    """A step in progress describes the hour you are living — keep it."""
    now = _at_local(16)  # inside the 15:00→18:00 step
    steps = weather_router.hourly_steps(_FORECAST, "2026-08-21", _TZ, now_dt=now)
    assert [s["time"] for s in steps] == ["15:00", "18:00", "21:00"]


def test_hourly_survives_one_malformed_step():
    bad = {"city": {"timezone": _TZ},
           "list": [_step(_at_local(15), 30.0), {"dt": _at_local(18)}]}
    steps = weather_router.hourly_steps(bad, "2026-08-21", _TZ)
    assert [s["time"] for s in steps] == ["15:00"]


# --- sun times ----------------------------------------------------------------

def test_sun_times_are_local_not_utc(monkeypatch):
    _mock(monkeypatch)
    body = client.get("/api/weather", params={"lat": 37.0164, "lon": 26.9555}).json()
    assert body["sunset"] == "19:55"
    assert body["sunrise"] == "06:45"
    assert body["sun_date"] == "2026-08-21"
    assert body["timezone_offset_s"] == _TZ


def test_sun_times_absent_when_provider_omits_them(monkeypatch):
    bare = {k: v for k, v in _CURRENT.items() if k != "sys"}
    _mock(monkeypatch, current=bare)
    body = client.get("/api/weather", params={"lat": 37.0164, "lon": 26.9555}).json()
    assert body["sunset"] is None and body["sunrise"] is None
    assert body["sun_date"] is None


# --- endpoint wiring ----------------------------------------------------------

def test_endpoint_current_carries_rest_of_day(monkeypatch):
    _mock(monkeypatch)
    body = client.get("/api/weather", params={"lat": 37.0164, "lon": 26.9555}).json()
    assert body["local_date"] == "2026-08-21"
    # now = 11:00 local → the 09:00 step has elapsed, 12:00 onward remain.
    assert [s["time"] for s in body["hourly"]] == ["09:00", "12:00", "15:00", "18:00", "21:00"]
    assert body["wind_dir"] == "NNW"


def test_endpoint_forecast_by_date_carries_the_whole_day(monkeypatch):
    _mock(monkeypatch)
    body = client.get("/api/weather", params={
        "lat": 37.0164, "lon": 26.9555, "date": "2026-08-21"}).json()
    assert body["is_forecast"] is True
    assert len(body["hourly"]) == 7          # full local day, nothing elapsed
    assert body["hourly"][0]["time"] == "03:00"
    assert body["sunset"] == "19:55"


def test_hourly_is_empty_not_missing_when_forecast_fails(monkeypatch):
    """Graceful degradation: the live card must still render (A238 contract)."""
    def _get(path, lat, lon):
        if path == "forecast":
            raise weather_router.WeatherUnavailable("boom")
        return _CURRENT
    monkeypatch.setattr(weather_router, "_owm_get", _get)
    body = client.get("/api/weather", params={"lat": 37.0164, "lon": 26.9555}).json()
    assert body["hourly"] == []
    assert body["best_window"] is None
    assert body["temp"] == 29.3              # the current reading survived
    assert body["sunset"] == "19:55"         # sun times come from /weather, not /forecast


def test_hourly_costs_no_extra_upstream_call(monkeypatch):
    """A275 rides on the fetch A238 already made for best_window."""
    calls = []

    def _get(path, lat, lon):
        calls.append(path)
        return _FORECAST if path == "forecast" else _CURRENT
    monkeypatch.setattr(weather_router, "_owm_get", _get)
    client.get("/api/weather", params={"lat": 37.0164, "lon": 26.9555})
    assert calls == ["weather", "forecast"]


# --- outdoor helper -----------------------------------------------------------

def test_fetch_outdoor_conditions_carries_hours_and_sunset(monkeypatch):
    _mock(monkeypatch)
    out = weather_router.fetch_outdoor_conditions(37.0164, 26.9555)
    assert out is not None
    assert out["sunset"] == "19:55"
    assert out["hourly"] and out["hourly"][0]["time"] == "09:00"
    assert out["timezone_offset_s"] == _TZ
    # A238 fields must survive the switch to cached_conditions.
    assert out["condition_band"] in ("prime", "ok", "poor_cold_dry", "poor_hot_humid")
    assert out["friction_score"] is not None
    assert out["temperature"] == 29.3


def test_fetch_outdoor_conditions_serves_a_warm_cache_when_provider_dies(monkeypatch):
    """A275 behaviour change, pinned on purpose.

    Cold cache + provider down still returns None (A225 contract, covered in
    test_a225_outdoor_v2.py). But a reading inside the 15-minute window is the
    same number /today is showing the athlete right now, so it beats degrading
    to the catalog base.
    """
    _mock(monkeypatch)
    assert weather_router.fetch_outdoor_conditions(37.0164, 26.9555) is not None

    def _boom(path, lat, lon):
        raise weather_router.WeatherUnavailable("provider down")
    monkeypatch.setattr(weather_router, "_owm_get", _boom)

    warm = weather_router.fetch_outdoor_conditions(37.0164, 26.9555)
    assert warm is not None and warm["temperature"] == 29.3

    weather_router._cache.clear()  # cold again → old contract
    assert weather_router.fetch_outdoor_conditions(37.0164, 26.9555) is None


def test_fetch_outdoor_conditions_shares_the_cache(monkeypatch):
    """Was a second free-tier call for an identical answer before A275."""
    calls = []

    def _get(path, lat, lon):
        calls.append(path)
        return _FORECAST if path == "forecast" else _CURRENT
    monkeypatch.setattr(weather_router, "_owm_get", _get)
    client.get("/api/weather", params={"lat": 37.0164, "lon": 26.9555})
    n_after_card = len(calls)
    weather_router.fetch_outdoor_conditions(37.0164, 26.9555)
    assert len(calls) == n_after_card  # cache hit, zero new calls


# --- coach tool ---------------------------------------------------------------

def test_coach_tool_reports_hours_sunset_and_wind_direction(monkeypatch):
    from backend.coach import weather_tool

    _mock(monkeypatch)
    monkeypatch.setattr(weather_tool, "_resolve_location",
                        lambda *a, **k: ((37.0164, 26.9555), "Summertime"))
    out = weather_tool.execute_get_weather({"location": "Summertime"}, {})
    assert "from NNW" in out
    assert "cloud cover 0%" in out
    assert "sunset 19:55 local" in out
    assert "hour by hour (LOCAL time at the location)" in out
    assert "15:00 30.0°C" in out and "18:00 28.0°C" in out


def test_coach_tool_still_degrades_to_a_sentence(monkeypatch):
    """The A244 contract: never raise into the chat loop."""
    from backend.coach import weather_tool

    def _get(path, lat, lon):
        raise weather_router.WeatherUnavailable("down")
    monkeypatch.setattr(weather_router, "_owm_get", _get)
    monkeypatch.setattr(weather_tool, "_resolve_location",
                        lambda *a, **k: ((37.0164, 26.9555), "Summertime"))
    out = weather_tool.execute_get_weather({"location": "Summertime"}, {})
    assert "unavailable" in out.lower()
