"""B335 — the friction score must not reward heat (D279 finding F1).

A238 assumed the temperature component could carry the heat signal by itself.
Above ``TEMP_HOT_ZERO_C`` (26 °C) that component is pinned at 0, so its 30 %
weight drops out of the sum — while heat keeps RAISING dew spread and LOWERING
relative humidity, the two components worth 55 %. The score therefore climbed
with temperature.

Every number in the "Kalymnos" tests below is the value D279 actually measured
against the pre-B335 code on a plausible Masouri day in late August; each one is
asserted here in its fixed form so the inversion cannot come back.

    local   T       pre-B335        post-B335
    07:00   26 °C   43  ok          43  ok
    12:00   33 °C   66  good        30  poor
    15:00   34 °C   70  GOOD  ←     20  poor
"""

from __future__ import annotations

import calendar

import pytest

from backend.api.routers import weather as weather_router
from backend.engine.weather_v1 import (
    BAND_HOT_OK_C,
    BAND_HOT_POOR_C,
    HEAT_CEILING_FROM_C,
    HEAT_CEILING_ZERO_C,
    band_headline,
    catalog_condition_band,
    compute_dew_point,
    compute_friction_score,
    heat_score_ceiling,
)

# The D279 Kalymnos day: (label, temp °C, RH %, wind km/h).
KALYMNOS_MORNING = ("07:00", 26.0, 65.0, 8.0)
KALYMNOS_NOON = ("12:00", 33.0, 50.0, 12.0)
KALYMNOS_AFTERNOON = ("15:00", 34.0, 45.0, 15.0)


def _score(temp_c: float, humidity: float, wind: float):
    return compute_friction_score(
        temp_c, humidity, compute_dew_point(temp_c, humidity), wind
    )


# --- the inversion itself -----------------------------------------------------

def test_kalymnos_afternoon_is_never_good_again():
    """34 °C in full sun must not read 'solid day to try hard'."""
    _, t, rh, w = KALYMNOS_AFTERNOON
    score, band = _score(t, rh, w)
    assert band not in ("good", "prime")
    assert band == "poor"
    assert score == 20  # pre-B335: 70


def test_cool_morning_outscores_hot_afternoon():
    """The headline regression: 26 °C must beat 34 °C, not lose to it by 27."""
    _, t_am, rh_am, w_am = KALYMNOS_MORNING
    _, t_pm, rh_pm, w_pm = KALYMNOS_AFTERNOON
    morning, _ = _score(t_am, rh_am, w_am)
    afternoon, _ = _score(t_pm, rh_pm, w_pm)
    assert morning == 43     # unchanged — 26 °C is the ceiling's starting point
    assert afternoon == 20   # pre-B335: 70
    assert morning > afternoon


def test_kalymnos_noon_drops_out_of_good():
    _, t, rh, w = KALYMNOS_NOON
    score, band = _score(t, rh, w)
    assert (score, band) == (30, "poor")  # pre-B335: (66, "good")


def test_score_never_rises_with_temperature():
    """Same air, more heat → never a better score. The general property."""
    scores = [_score(float(t), 45.0, 12.0)[0] for t in range(20, 40)]
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] == 0  # 39 °C scores nothing at all


# --- the ceiling, in isolation -------------------------------------------------

def test_heat_ceiling_shape():
    assert heat_score_ceiling(10.0) == 100
    assert heat_score_ceiling(HEAT_CEILING_FROM_C) == 100      # no effect at 26
    assert heat_score_ceiling(31.0) == 50                      # midpoint 26→36
    assert heat_score_ceiling(HEAT_CEILING_ZERO_C) == 0
    assert heat_score_ceiling(45.0) == 0
    # Monotonically decreasing across the ramp.
    ramp = [heat_score_ceiling(t / 2) for t in range(40, 80)]
    assert ramp == sorted(ramp, reverse=True)


def test_band_capped_at_ok_then_poor():
    # Perfectly dry, breezy air — the score would otherwise be high.
    assert _score(BAND_HOT_OK_C, 30.0, 15.0)[1] == "ok"
    assert _score(BAND_HOT_POOR_C, 30.0, 15.0)[1] == "poor"
    assert _score(BAND_HOT_POOR_C + 5, 30.0, 15.0)[1] == "poor"


def test_catalog_band_now_selects_the_hot_humid_nudge():
    """The C241 'downgrade to Volume/Scout, seek shade' patch must fire."""
    _, t, rh, w = KALYMNOS_AFTERNOON
    _, band = _score(t, rh, w)
    assert catalog_condition_band(t, band) == "poor_hot_humid"


def test_headline_no_longer_contradicts_its_own_limiter():
    """Pre-B335 the card said 'solid day to try hard. Heat is the limiter'."""
    _, t, rh, w = KALYMNOS_AFTERNOON
    dew = compute_dew_point(t, rh)
    _, band = _score(t, rh, w)
    head = band_headline(band, t, rh, dew, w)
    assert "Heat is the limiter" in head
    assert "try hard" not in head
    assert head.startswith("Poor conditions")


# --- no regression below the threshold ----------------------------------------

def test_temperate_days_are_untouched():
    """Nothing at or below 26 °C may move — A238's whole calibration lives there."""
    # The Berdorf field-test day that motivated A238.
    assert _score(22.0, 39.0, 23.0) == (85, "prime")
    assert compute_friction_score(10.0, 30.0, -5.0, 15.0) == (100, "prime")
    assert compute_friction_score(-1.0, 30.0, -15.0, 15.0)[1] == "ok"   # sub-zero cap
    assert compute_friction_score(10.0, 30.0, -5.0, 15.0, precip_active=True) == (100, "poor")
    for t in (0.0, 5.0, 15.0, 18.0, 24.0, HEAT_CEILING_FROM_C):
        assert heat_score_ceiling(t) == 100, f"ceiling must not bind at {t}°C"


# --- best_window: never send anyone into a hotter hour -------------------------

_D0 = calendar.timegm((2026, 8, 20, 0, 0, 0, 0, 0, 0))  # trip day 1, 00:00 UTC
_TZ = 3 * 3600  # Europe/Athens, EEST


def _step(local_hour: int, temp: float, humidity: float, wind_ms: float = 3.0):
    return {
        "dt": _D0 + (local_hour * 3600) - _TZ,
        "main": {"temp": temp, "humidity": humidity},
        "wind": {"speed": wind_ms},
        "weather": [{"id": 800, "description": "clear sky"}],
        "pop": 0.0,
    }


def _raw(steps):
    return {"city": {"timezone": _TZ}, "list": steps}


def _current(temp: float, humidity: float, wind: float):
    dew = compute_dew_point(temp, humidity)
    score, band = compute_friction_score(temp, humidity, dew, wind)
    return {"temp": temp, "humidity": humidity, "dew_point": dew, "wind": wind,
            "friction_score": score, "band": band}


def test_fixture_epoch_is_the_trip_date():
    """Guard the guard: a wrong epoch silently filters every step to None."""
    import time
    assert time.strftime("%Y-%m-%d", time.gmtime(_D0)) == "2026-08-20"
    assert time.strftime("%H:%M", time.gmtime(_step(15, 30.0, 50.0)["dt"] + _TZ)) == "15:00"


def test_best_window_never_proposes_a_hotter_window():
    """The D279 scenario: 07:00 at 26 °C, the day only gets hotter."""
    now = _D0 + (7 * 3600) - _TZ
    steps = [_step(9, 29.0, 60.0), _step(12, 33.0, 50.0),
             _step(15, 34.0, 45.0), _step(18, 31.0, 55.0)]
    assert weather_router.best_window(
        _raw(steps), "2026-08-20", _current(26.0, 65.0, 8.0), now_dt=now
    ) is None


def test_best_window_still_finds_a_genuinely_cooler_evening():
    """The cap must silence bad advice, not the feature."""
    now = _D0 + (7 * 3600) - _TZ
    w = weather_router.best_window(
        _raw([_step(15, 34.0, 45.0), _step(20, 19.0, 50.0)]),
        "2026-08-20", _current(26.0, 65.0, 8.0), now_dt=now,
    )
    assert w is not None
    assert w["from"] == "20:00"
    assert "temp drops to 19" in w["reason"]


def test_best_window_still_allows_warming_when_cold():
    """Below the comfort plateau a warmer window is the right answer."""
    now = _D0 + (7 * 3600) - _TZ
    w = weather_router.best_window(
        _raw([_step(13, 12.0, 45.0), _step(16, 14.0, 42.0)]),
        "2026-08-20", _current(3.0, 80.0, 5.0), now_dt=now,
    )
    assert w is not None
    assert w["score"] > _current(3.0, 80.0, 5.0)["friction_score"]


@pytest.mark.parametrize("later_temp,expected", [(27.0, None), (26.5, "found")])
def test_best_window_tolerance_at_the_boundary(later_temp, expected):
    """1 °C of drift is tolerated; a materially hotter step is not."""
    now = _D0 + (7 * 3600) - _TZ
    # Same temp band, much drier later → a big score gain, so only the
    # temperature filter can decide the outcome.
    w = weather_router.best_window(
        _raw([_step(16, later_temp, 25.0, wind_ms=4.0)]),
        "2026-08-20", _current(25.5, 78.0, 6.0), now_dt=now,
    )
    assert (w is None) if expected is None else (w is not None)
