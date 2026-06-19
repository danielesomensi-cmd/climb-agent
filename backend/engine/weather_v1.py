"""Weather engine v1 — deterministic climbing-conditions logic (A224).

Pure, provider-agnostic, no network. Two responsibilities:

1. ``compute_dew_point`` — derive dew point from temperature + relative humidity
   via the Magnus-Tetens approximation (~±0.4°C). Needed because the free
   OpenWeatherMap endpoints used by climb-agent (``/data/2.5/weather`` and
   ``/data/2.5/forecast``) do NOT return dew point natively — only One Call 3.0
   does, and that tier requires a card on file.

2. ``condition_band`` — map ``(temp, humidity, dew point, wind, precip flag)`` to
   one of ``{prime, ok, poor}`` using a deterministic "weakest-link" rule. Dew
   point is the primary friction proxy; air temperature is the secondary axis;
   precipitation/fog is a hard override; strong wind caps the band.

This module is fully unit-tested in isolation (the network layer lives in the
``weather`` router and is mocked in CI). Sun-aspect is intentionally out of v1 —
it is not auto-fetchable.
"""

from __future__ import annotations

import math
from typing import Literal

ConditionBand = Literal["prime", "ok", "poor"]

# --- Magnus-Tetens constants (over-water, valid for -45..60°C) -----------------
_MAGNUS_A = 17.625
_MAGNUS_B = 243.04

# --- condition_band thresholds (tunable) --------------------------------------
# Dew point is the single best predictor of rock "grip": dry air → firm friction,
# humid air → condensation / greasy holds.
DEW_PRIME_MAX_C = 8.0    # dew point ≤ 8°C  → dry, prime friction
DEW_OK_MAX_C = 14.0      # 8 < dew ≤ 14°C   → acceptable; dew > 14°C → greasy/poor

# Air temperature comfort window for skin + rubber friction.
TEMP_PRIME_MIN_C = -2.0  # below this fingers go numb
TEMP_PRIME_MAX_C = 16.0  # ideal sending window is cool
TEMP_OK_MIN_C = -6.0     # -6..-2 still climbable but cold; below → poor
TEMP_OK_MAX_C = 24.0     # 16..24 warm but ok; above → sweaty/soft → poor

# Strong wind is uncomfortable / unsafe on lead — caps the band at "ok".
WIND_STRONG_KMH = 40.0

_BAND_RANK = {"prime": 2, "ok": 1, "poor": 0}
_RANK_BAND = {2: "prime", 1: "ok", 0: "poor"}


def compute_dew_point(temp_c: float, relative_humidity: float) -> float:
    """Dew point (°C) from air temperature (°C) and relative humidity (%).

    Magnus-Tetens approximation. ``relative_humidity`` is a percentage in
    (0, 100]; values are clamped to a small positive floor to avoid log(0).
    """
    rh = max(float(relative_humidity), 0.1)
    rh = min(rh, 100.0)
    alpha = math.log(rh / 100.0) + (_MAGNUS_A * temp_c) / (_MAGNUS_B + temp_c)
    dew = (_MAGNUS_B * alpha) / (_MAGNUS_A - alpha)
    return round(dew, 1)


def _dew_band(dew_point_c: float) -> ConditionBand:
    if dew_point_c <= DEW_PRIME_MAX_C:
        return "prime"
    if dew_point_c <= DEW_OK_MAX_C:
        return "ok"
    return "poor"


def _temp_band(temp_c: float) -> ConditionBand:
    if TEMP_PRIME_MIN_C <= temp_c <= TEMP_PRIME_MAX_C:
        return "prime"
    if TEMP_OK_MIN_C <= temp_c <= TEMP_OK_MAX_C:
        return "ok"
    return "poor"


# --- wind descriptor (Beaufort-aligned, Italian) ------------------------------
# Upper bound (km/h, exclusive) → label. Last entry is the catch-all.
_WIND_LABELS = (
    (1.0, "assente"),
    (6.0, "molto debole"),
    (12.0, "debole"),
    (20.0, "moderato"),
    (29.0, "teso"),
    (39.0, "fresco"),
    (50.0, "forte"),
    (float("inf"), "molto forte"),
)


def wind_label(wind_kmh: float) -> str:
    """Qualitative Italian wind descriptor from speed in km/h (Beaufort-aligned)."""
    for upper, label in _WIND_LABELS:
        if wind_kmh < upper:
            return label
    return _WIND_LABELS[-1][1]


def condition_band(
    temp_c: float,
    relative_humidity: float,
    dew_point_c: float,
    wind_kmh: float,
    is_precip_or_fog: bool,
) -> ConditionBand:
    """Deterministic friction band ``{prime, ok, poor}``.

    Rule (weakest-link / Liebig's minimum):
      0. Precipitation, snow or fog/mist → ``poor`` (wet or condensing rock).
      1. Band = worse of (dew-point band, air-temperature band).
      2. Strong wind (> 40 km/h) caps the band at ``ok``.

    ``relative_humidity`` is accepted for symmetry / future tuning but the rule
    keys off dew point (which already encodes humidity).
    """
    if is_precip_or_fog:
        return "poor"

    band_rank = min(_BAND_RANK[_dew_band(dew_point_c)], _BAND_RANK[_temp_band(temp_c)])

    if wind_kmh > WIND_STRONG_KMH:
        band_rank = min(band_rank, _BAND_RANK["ok"])

    return _RANK_BAND[band_rank]
