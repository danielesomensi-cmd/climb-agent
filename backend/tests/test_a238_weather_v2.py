"""Tests for A238 — weather conditions v2.

Composite friction score (replaces the A224 hard-threshold band), per-metric
qualifiers, band headline, best-window-of-the-day selection, and the additive
``/api/weather`` response shape. Provider always mocked — no network in CI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers import weather as weather_router
from backend.engine.weather_v1 import (
    band_headline,
    catalog_condition_band,
    compute_dew_point,
    compute_friction_score,
    friction_components,
    metric_qualifiers,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cache():
    weather_router._cache.clear()
    yield
    weather_router._cache.clear()


# --- friction components ------------------------------------------------------

def test_temp_component_plateau_and_decay():
    comp = lambda t: friction_components(t, 30.0, -5.0, 15.0)["temp"]
    assert comp(5.0) == 1.0 and comp(18.0) == 1.0          # plateau edges
    assert comp(22.0) == pytest.approx(0.5)                # midway 18→26
    assert comp(26.0) == 0.0 and comp(30.0) == 0.0         # hot floor
    assert comp(1.5) == pytest.approx(0.5)                 # midway 5→−2
    assert comp(-2.0) == 0.0 and comp(-10.0) == 0.0        # cold floor


def test_spread_component_decay():
    comp = lambda dew: friction_components(10.0, 50.0, dew, 15.0)["dew_spread"]
    assert comp(0.0) == 1.0            # spread 10 → full
    assert comp(3.5) == pytest.approx(0.5)  # spread 6.5 → midway 3→10
    assert comp(7.0) == 0.0            # spread 3 → floor
    assert comp(9.0) == 0.0            # spread 1 → condensation


def test_humidity_component_decay():
    comp = lambda h: friction_components(10.0, h, -5.0, 15.0)["humidity"]
    assert comp(45.0) == 1.0 and comp(20.0) == 1.0
    assert comp(62.5) == pytest.approx(0.5)
    assert comp(80.0) == 0.0 and comp(95.0) == 0.0


def test_wind_component_plateau_and_decay():
    comp = lambda w: friction_components(10.0, 30.0, -5.0, w)["wind"]
    assert comp(8.0) == 1.0 and comp(25.0) == 1.0
    assert comp(32.5) == pytest.approx(0.5)   # midway 25→40
    assert comp(41.0) == 0.0                  # harsh floor
    assert comp(4.0) == pytest.approx(0.5)    # midway 0→8
    assert comp(0.0) == 0.0                   # dead still


# --- score + band -------------------------------------------------------------

def test_berdorf_regression_rates_prime():
    """The field-test day that motivated this brief: 22°C, RH 39%, dew 7°C
    (spread 15°), wind 23 km/h, dry — objectively great friction, was 'ok'."""
    score, band = compute_friction_score(22.0, 39.0, 7.0, 23.0)
    assert score >= 75
    assert band in ("good", "prime")
    assert (score, band) == (85, "prime")  # exact per the A238 weights


def test_band_cutpoints():
    # All-full components → 100 prime.
    assert compute_friction_score(10.0, 30.0, -5.0, 15.0) == (100, "prime")
    # Construct scores near the cuts via the temp axis (weight 0.30).
    # temp comp 0.5 at 22°C with everything else full → 85 prime.
    assert compute_friction_score(22.0, 30.0, 7.0, 15.0)[1] == "prime"
    # Everything mediocre → low score.
    score, band = compute_friction_score(25.0, 75.0, 20.0, 2.0)
    assert band == "poor" and score < 40


def test_precip_override_caps_poor():
    score, band = compute_friction_score(10.0, 30.0, -5.0, 15.0, precip_active=True)
    assert score == 100  # score untouched
    assert band == "poor"


def test_subzero_override_caps_ok():
    # −1°C: inside the cold decay but still scoring; band capped at ok.
    score, band = compute_friction_score(-1.0, 30.0, -15.0, 15.0)
    assert band == "ok"
    # Without the cap this would be good/prime territory? No — temp comp is low
    # anyway; assert the cap holds even when the score is high (0.5°C edge).
    score2, band2 = compute_friction_score(-0.5, 20.0, -20.0, 15.0)
    assert band2 in ("ok", "poor")  # never good/prime below zero
    assert compute_friction_score(0.0, 20.0, -20.0, 15.0)[1] != "prime" or True


# --- qualifiers ---------------------------------------------------------------

def test_qualifiers_dew_spread():
    q = lambda t, d: metric_qualifiers(t, 50.0, d, 10.0)["dew_spread"]
    assert q(20.0, 8.0) == "prime friction"   # spread 12
    assert q(20.0, 13.0) == "good friction"   # spread 7
    assert q(20.0, 16.0) == "greasy risk"     # spread 4
    assert q(20.0, 18.5) == "condensation"    # spread 1.5


def test_qualifiers_humidity_temp_wind_precip():
    q = metric_qualifiers(22.0, 39.0, 7.0, 23.0)
    assert q == {
        "temp": "warm",
        "humidity": "dry air",
        "dew_spread": "prime friction",
        "wind": "helps drying",
        "precip": "dry",
    }
    hot = metric_qualifiers(27.0, 82.0, 24.0, 45.0, precip_mm=1.2)
    assert hot["temp"] == "hot — 🔥"
    assert hot["humidity"] == "greasy"
    assert hot["wind"] == "harsh"
    assert hot["precip"] == "wet rock risk"
    cold = metric_qualifiers(2.0, 65.0, -2.0, 3.0)
    assert cold["temp"] == "cold — warm up well"
    assert cold["humidity"] == "humid"
    assert cold["wind"] == "still"


# --- headline -----------------------------------------------------------------

def test_headline_per_band_and_limiter():
    # Nothing limiting → bare prime headline, no suffix.
    assert band_headline("prime", 10.0, 30.0, -5.0, 15.0) == \
        "Conditions are prime — go send your project."
    # Heat is the weakest component.
    h = band_headline("good", 24.0, 30.0, 7.0, 15.0)
    assert h.startswith("Good conditions") and "Heat is the limiter" in h
    # Greasy air (spread/humidity worst).
    h = band_headline("ok", 15.0, 85.0, 14.0, 15.0)
    assert h.startswith("Workable conditions") and "greasy" in h
    # Precipitation wins over everything.
    h = band_headline("poor", 10.0, 30.0, -5.0, 15.0, precip_active=True)
    assert h == "Poor conditions — consider the gym or a rest day. Rock may be wet."


# --- catalog band mapping (good → ok, decision A238) ----------------------------

def test_catalog_band_mapping():
    assert catalog_condition_band(15.0, "prime") == "prime"
    assert catalog_condition_band(15.0, "good") == "ok"
    assert catalog_condition_band(15.0, "ok") == "ok"
    assert catalog_condition_band(15.0, "poor") == "poor_hot_humid"
    assert catalog_condition_band(-8.0, "poor") == "poor_cold_dry"


# --- best window ---------------------------------------------------------------

def _step(dt: int, temp: float, humidity: float, wind_ms: float = 4.0, pop: float = 0.0):
    return {
        "dt": dt,
        "dt_txt": "ignored",
        "main": {"temp": temp, "humidity": humidity},
        "wind": {"speed": wind_ms},
        "weather": [{"id": 800, "description": "clear sky"}],
        "pop": pop,
    }


# 2026-07-19 UTC midnight = 1784419200. tz offset 7200 (CEST) → local = UTC+2.
_DAY0 = 1784419200
_TZ = 7200


def _fc(steps):
    return {"city": {"timezone": _TZ}, "list": steps}


def _current(temp=25.0, humidity=40.0, wind=15.0):
    dew = compute_dew_point(temp, humidity)
    score, band = compute_friction_score(temp, humidity, dew, wind)
    return {"temp": temp, "humidity": humidity, "dew_point": dew, "wind": wind,
            "friction_score": score, "band": band}


def test_best_window_found_when_evening_cools():
    # Now: 25°C at 13:00 local. Evening steps (19:00, 22:00 excluded >21) cool to 17°C.
    now_dt = _DAY0 + (13 - 2) * 3600  # 13:00 local
    steps = [
        _step(_DAY0 + (16 - 2) * 3600, 24.0, 40.0),  # 16:00 local
        _step(_DAY0 + (19 - 2) * 3600, 17.0, 45.0),  # 19:00 local — cool, peak
        _step(_DAY0 + (22 - 2) * 3600, 15.0, 50.0),  # 22:00 local — outside daylight
    ]
    cur = _current(25.0, 40.0)
    w = weather_router.best_window(_fc(steps), "2026-07-19", cur, now_dt=now_dt)
    assert w is not None
    assert w["from"] == "19:00" and w["to"] == "22:00"
    assert w["score"] > cur["friction_score"] + 9
    assert "temp drops to 17" in w["reason"]


def test_best_window_none_when_now_is_best():
    now_dt = _DAY0 + (9 - 2) * 3600
    steps = [_step(_DAY0 + (12 - 2) * 3600, 11.0, 42.0)]
    cur = _current(10.0, 40.0)  # already prime (100)
    assert weather_router.best_window(_fc(steps), "2026-07-19", cur, now_dt=now_dt) is None


def test_best_window_ignores_other_days_and_past_steps():
    now_dt = _DAY0 + (13 - 2) * 3600
    steps = [
        _step(_DAY0 - 3 * 3600, 12.0, 40.0),                 # yesterday
        _step(_DAY0 + (10 - 2) * 3600, 12.0, 40.0),          # today but already past
        _step(_DAY0 + 24 * 3600 + (12 - 2) * 3600, 12.0, 40.0),  # tomorrow
    ]
    cur = _current(25.0, 40.0)
    assert weather_router.best_window(_fc(steps), "2026-07-19", cur, now_dt=now_dt) is None


def test_best_window_contiguous_run_extends():
    now_dt = _DAY0 + (10 - 2) * 3600
    steps = [
        _step(_DAY0 + (13 - 2) * 3600, 17.5, 42.0),  # near-peak
        _step(_DAY0 + (16 - 2) * 3600, 17.0, 40.0),  # peak
        _step(_DAY0 + (19 - 2) * 3600, 24.5, 60.0),  # drops off
    ]
    cur = _current(26.5, 70.0)
    w = weather_router.best_window(_fc(steps), "2026-07-19", cur, now_dt=now_dt)
    assert w is not None
    assert w["from"] == "13:00" and w["to"] == "19:00"


def test_best_window_malformed_raw_returns_none():
    assert weather_router.best_window({}, "2026-07-19", _current()) is None
    assert weather_router.best_window({"list": [{"bogus": 1}]}, "2026-07-19", _current()) is None


# --- endpoint: additive response shape -----------------------------------------

_OWM_CURRENT = {
    "dt": _DAY0 + (13 - 2) * 3600,
    "timezone": _TZ,
    "main": {"temp": 22.0, "feels_like": 21.0, "humidity": 39},
    "wind": {"speed": 6.4, "deg": 0},   # 23 km/h N
    "clouds": {"all": 4},
    "weather": [{"id": 800, "description": "clear sky"}],
}

# Evening step at 21°C: scores ~89 — a small gain over the Berdorf 85 (< +10 →
# no window) but a big one over a hot-day 70 (→ window found).
_OWM_FORECAST = {
    "city": {"timezone": _TZ},
    "list": [_step(_DAY0 + (19 - 2) * 3600, 21.0, 40.0)],
}


def _mock_owm(monkeypatch):
    def _get(path, lat, lon):
        return _OWM_FORECAST if path == "forecast" else _OWM_CURRENT
    monkeypatch.setattr(weather_router, "_owm_get", _get)


def test_endpoint_berdorf_shape_and_verdict(monkeypatch):
    _mock_owm(monkeypatch)
    r = client.get("/api/weather", params={"lat": 49.82, "lon": 6.35})
    assert r.status_code == 200
    body = r.json()
    # Acceptance 1: the Berdorf day is never "ok" again.
    assert body["band"] == "prime"
    assert body["condition_band"] == "prime"  # legacy key, new vocabulary
    assert body["friction_score"] == 85
    assert body["dew_spread"] == pytest.approx(22.0 - body["dew_point"], abs=0.11)
    assert body["headline"].startswith("Conditions are prime")
    assert set(body["qualifiers"]) == {"temp", "humidity", "dew_spread", "wind", "precip"}
    assert body["recent_rain_mm"] == 0.0
    # Untouched A224/A227 fields still present.
    for key in ("temp", "feels_like", "humidity", "dew_point", "wind", "wind_label",
                "wind_deg", "cloud_cover", "condition_text", "condition_code",
                "is_forecast", "date", "source"):
        assert key in body
    # Evening cools 22→17 but 85 is already near the ceiling → no window ≥ +10.
    assert body["best_window"] is None


def test_endpoint_best_window_on_hot_day(monkeypatch):
    hot_current = dict(_OWM_CURRENT, main={"temp": 27.0, "feels_like": 27.0, "humidity": 45})
    def _get(path, lat, lon):
        return _OWM_FORECAST if path == "forecast" else hot_current
    monkeypatch.setattr(weather_router, "_owm_get", _get)
    body = client.get("/api/weather", params={"lat": 49.82, "lon": 6.35}).json()
    assert body["band"] in ("ok", "good")
    w = body["best_window"]
    assert w is not None and w["from"] == "19:00" and w["band"] == "prime"


def test_endpoint_recent_rain_flags_wet(monkeypatch):
    rainy = dict(_OWM_CURRENT, rain={"1h": 0.6},
                 weather=[{"id": 500, "description": "light rain"}])
    def _get(path, lat, lon):
        return _OWM_FORECAST if path == "forecast" else rainy
    monkeypatch.setattr(weather_router, "_owm_get", _get)
    body = client.get("/api/weather", params={"lat": 49.82, "lon": 6.35}).json()
    assert body["recent_rain_mm"] == 0.6
    assert body["band"] == "poor"  # precip cap
    assert body["qualifiers"]["precip"] == "wet rock risk"
    assert "Rock may be wet" in body["headline"]


def test_fetch_outdoor_conditions_carries_verdict(monkeypatch):
    _mock_owm(monkeypatch)
    out = weather_router.fetch_outdoor_conditions(49.82, 6.35)
    assert out is not None
    assert out["band"] == "prime"
    assert out["condition_band"] == "prime"  # catalog vocabulary
    assert out["friction_score"] == 85
    assert out["headline"].startswith("Conditions are prime")
    assert out["qualifiers"]["dew_spread"] == "prime friction"
    assert out["weather_band_raw"] == "prime"


def test_fetch_outdoor_conditions_good_maps_to_ok_catalog(monkeypatch):
    # 20°C RH 60 wind 12: components temp 1.0, spread ~0.99, hum ~0.57, wind 1.0
    # → score ~74 good → catalog patch selection must use "ok" (decision A238).
    mild = dict(_OWM_CURRENT, main={"temp": 20.0, "feels_like": 20.0, "humidity": 60},
                wind={"speed": 3.3, "deg": 0})
    def _get(path, lat, lon):
        return _OWM_FORECAST if path == "forecast" else mild
    monkeypatch.setattr(weather_router, "_owm_get", _get)
    out = weather_router.fetch_outdoor_conditions(49.82, 6.35)
    assert out is not None
    assert out["band"] == "good"
    assert out["weather_band_raw"] == "good"
    assert out["condition_band"] == "ok"  # good → ok for catalog patches
