"""Tests for A224 — weather engine + /api/weather proxy.

Covers the deterministic core (Magnus dew point, condition_band boundaries),
the OWM adapters, and the endpoint with the upstream provider mocked (never
hits the network in CI).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers import weather as weather_router
from backend.engine.weather_v1 import compute_dew_point, condition_band, wind_label

client = TestClient(app)


# --- Magnus dew point ---------------------------------------------------------

def test_dew_point_saturated_equals_temp():
    # 100% RH → dew point ≈ air temp.
    assert compute_dew_point(20.0, 100.0) == pytest.approx(20.0, abs=0.2)


def test_dew_point_known_value():
    # 30°C / 36% RH → ~13.3°C (matches live Open-Meteo reference of 13.4).
    assert compute_dew_point(30.0, 36.0) == pytest.approx(13.3, abs=0.3)


def test_dew_point_clamps_zero_humidity():
    # Must not raise on RH=0 (log(0)) — clamped to a small floor.
    assert compute_dew_point(10.0, 0.0) < -20.0


# --- condition_band boundaries ------------------------------------------------

def test_band_prime_cool_and_dry():
    assert condition_band(10.0, 40.0, 5.0, 10.0, False) == "prime"


def test_band_precip_override_always_poor():
    # Even with otherwise prime numbers, precipitation/fog forces poor.
    assert condition_band(8.0, 30.0, 2.0, 5.0, True) == "poor"


def test_band_dew_point_boundaries():
    assert condition_band(10.0, 50.0, 8.0, 0.0, False) == "prime"   # ≤ 8 → prime
    assert condition_band(10.0, 50.0, 8.1, 0.0, False) == "ok"      # > 8 → ok
    assert condition_band(10.0, 50.0, 14.0, 0.0, False) == "ok"     # ≤ 14 → ok
    assert condition_band(10.0, 50.0, 14.1, 0.0, False) == "poor"   # > 14 → poor


def test_band_temperature_boundaries():
    # Low dew point keeps the dew axis prime; temp axis drives the result.
    assert condition_band(16.0, 30.0, 5.0, 0.0, False) == "prime"   # ≤ 16 → prime
    assert condition_band(16.1, 30.0, 5.0, 0.0, False) == "ok"      # warm → ok
    assert condition_band(24.0, 30.0, 5.0, 0.0, False) == "ok"      # ≤ 24 → ok
    assert condition_band(24.1, 30.0, 5.0, 0.0, False) == "poor"    # hot → poor
    assert condition_band(-2.0, 30.0, 5.0, 0.0, False) == "prime"   # ≥ -2 → prime
    assert condition_band(-6.0, 30.0, 5.0, 0.0, False) == "ok"      # cold → ok
    assert condition_band(-6.1, 30.0, 5.0, 0.0, False) == "poor"    # frozen → poor


def test_band_weakest_link():
    # Prime temp but greasy dew point → overall poor (worse axis wins).
    assert condition_band(10.0, 90.0, 18.0, 0.0, False) == "poor"


def test_band_strong_wind_caps_at_ok():
    assert condition_band(10.0, 40.0, 5.0, 41.0, False) == "ok"     # > 40 → cap
    assert condition_band(10.0, 40.0, 5.0, 40.0, False) == "prime"  # = 40 → no cap


# --- wind descriptor ----------------------------------------------------------

def test_wind_label_scale():
    assert wind_label(0.0) == "calm"
    assert wind_label(0.9) == "calm"
    assert wind_label(1.0) == "very light"
    assert wind_label(9.0) == "light"
    assert wind_label(15.0) == "moderate"
    assert wind_label(25.0) == "brisk"
    assert wind_label(35.0) == "fresh"
    assert wind_label(45.0) == "strong"
    assert wind_label(60.0) == "very strong"


# --- OWM adapters -------------------------------------------------------------

_OWM_CURRENT = {
    "main": {"temp": 8.4, "humidity": 55},
    "wind": {"speed": 2.5},  # m/s
    "weather": [{"id": 800, "description": "clear sky"}],
}

_OWM_FORECAST = {
    "list": [
        {"dt_txt": "2026-06-21 09:00:00", "main": {"temp": 12.0, "humidity": 70},
         "wind": {"speed": 1.0}, "weather": [{"id": 500, "description": "light rain"}]},
        {"dt_txt": "2026-06-21 12:00:00", "main": {"temp": 7.0, "humidity": 45},
         "wind": {"speed": 3.0}, "weather": [{"id": 801, "description": "few clouds"}]},
        {"dt_txt": "2026-06-22 12:00:00", "main": {"temp": 20.0, "humidity": 80},
         "wind": {"speed": 2.0}, "weather": [{"id": 800, "description": "clear sky"}]},
    ]
}


def test_normalize_current_shape():
    out = weather_router._normalize_current(_OWM_CURRENT)
    assert out["temp"] == 8.4
    assert out["wind"] == pytest.approx(9.0, abs=0.1)  # 2.5 m/s → km/h
    assert out["wind_label"] == "light"
    assert out["condition_band"] == "prime"
    assert out["is_forecast"] is False
    assert out["source"] == "openweathermap"


def test_normalize_forecast_picks_midday_step():
    out = weather_router._normalize_forecast(_OWM_FORECAST, "2026-06-21")
    assert out["temp"] == 7.0          # 12:00 step, not the 09:00 rainy one
    assert out["is_forecast"] is True
    assert out["date"] == "2026-06-21"


def test_normalize_forecast_unknown_date_raises():
    with pytest.raises(weather_router.WeatherUnavailable):
        weather_router._normalize_forecast(_OWM_FORECAST, "2026-12-25")


# --- A227: expanded fields (feels_like / wind_deg / cloud_cover / precip_prob) -

_OWM_CURRENT_RICH = {
    "main": {"temp": 8.4, "feels_like": 6.1, "humidity": 55},
    "wind": {"speed": 2.5, "deg": 270},
    "clouds": {"all": 40},
    "weather": [{"id": 800, "description": "clear sky"}],
}

_OWM_FORECAST_RICH = {
    "list": [
        {"dt_txt": "2026-06-21 12:00:00", "main": {"temp": 7.0, "feels_like": 4.0, "humidity": 45},
         "wind": {"speed": 3.0, "deg": 180}, "clouds": {"all": 75}, "pop": 0.6,
         "weather": [{"id": 801, "description": "few clouds"}]},
    ]
}


def test_normalize_current_expanded_fields():
    out = weather_router._normalize_current(_OWM_CURRENT_RICH)
    assert out["feels_like"] == 6.1
    assert out["wind_deg"] == 270
    assert out["cloud_cover"] == 40
    assert out["precip_prob"] is None  # current endpoint has no pop


def test_normalize_forecast_expanded_fields():
    out = weather_router._normalize_forecast(_OWM_FORECAST_RICH, "2026-06-21")
    assert out["feels_like"] == 4.0
    assert out["wind_deg"] == 180
    assert out["cloud_cover"] == 75
    assert out["precip_prob"] == 60  # 0.6 → 60%


def test_normalize_missing_expanded_fields_are_none():
    # legacy/minimal payload (no feels_like/deg/clouds) → graceful None, no crash
    out = weather_router._normalize_current(_OWM_CURRENT)
    assert out["feels_like"] is None
    assert out["wind_deg"] is None
    assert out["cloud_cover"] is None
    assert out["precip_prob"] is None


def test_is_precip_or_fog():
    assert weather_router._is_precip_or_fog(500) is True   # rain
    assert weather_router._is_precip_or_fog(741) is True   # fog
    assert weather_router._is_precip_or_fog(800) is False  # clear
    assert weather_router._is_precip_or_fog(804) is False  # overcast clouds


# --- endpoint (provider mocked) ----------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cache():
    weather_router._cache.clear()
    yield
    weather_router._cache.clear()


def test_endpoint_current_mocked(monkeypatch):
    monkeypatch.setattr(weather_router, "_owm_get", lambda path, lat, lon: _OWM_CURRENT)
    r = client.get("/api/weather", params={"lat": 45.07, "lon": 7.69})
    assert r.status_code == 200
    body = r.json()
    assert body["condition_band"] == "prime"
    assert body["dew_point"] == compute_dew_point(8.4, 55)


def test_endpoint_forecast_mocked(monkeypatch):
    monkeypatch.setattr(weather_router, "_owm_get", lambda path, lat, lon: _OWM_FORECAST)
    r = client.get("/api/weather", params={"lat": 45.07, "lon": 7.69, "date": "2026-06-21"})
    assert r.status_code == 200
    assert r.json()["is_forecast"] is True


def test_endpoint_unavailable_returns_503(monkeypatch):
    def _boom(path, lat, lon):
        raise weather_router.WeatherUnavailable("OPENWEATHER_API_KEY not configured")
    monkeypatch.setattr(weather_router, "_owm_get", _boom)
    r = client.get("/api/weather", params={"lat": 45.07, "lon": 7.69})
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "weather_unavailable"


def test_endpoint_rejects_out_of_range_coords():
    r = client.get("/api/weather", params={"lat": 200, "lon": 7.69})
    assert r.status_code == 422


def test_endpoint_caches_within_window(monkeypatch):
    calls = {"n": 0}

    def _counting(path, lat, lon):
        calls["n"] += 1
        return _OWM_CURRENT

    monkeypatch.setattr(weather_router, "_owm_get", _counting)
    client.get("/api/weather", params={"lat": 45.07, "lon": 7.69})
    client.get("/api/weather", params={"lat": 45.07, "lon": 7.69})
    assert calls["n"] == 1  # second request served from cache
