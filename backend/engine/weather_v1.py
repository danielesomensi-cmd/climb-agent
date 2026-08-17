"""Weather engine — deterministic climbing-conditions logic (A224 → A238 v2).

Pure, provider-agnostic, no network. Responsibilities:

1. ``compute_dew_point`` — derive dew point from temperature + relative humidity
   via the Magnus-Tetens approximation (~±0.4°C). Needed because the free
   OpenWeatherMap endpoints used by climb-agent (``/data/2.5/weather`` and
   ``/data/2.5/forecast``) do NOT return dew point natively — only One Call 3.0
   does, and that tier requires a card on file.

2. ``compute_friction_score`` (A238) — composite 0–100 friction score from
   weighted components (temp 30%, dew spread 30%, humidity 25%, wind 15%) with
   linear decay instead of hard thresholds, mapped to a 4-value band
   ``{prime, good, ok, poor}``. Replaces the A224 weakest-link ``condition_band``
   (whose hard temp cutoff rated an objectively great day — Berdorf 2026-07-19:
   22°C, spread 15° — as merely "ok"). Hard overrides: active precip caps the
   band at poor; sub-zero temp caps at ok.

3. ``metric_qualifiers`` / ``band_headline`` (A238) — backend-owned plain-English
   chips per metric and the band verdict copy, so every UI surface renders the
   same words.

This module is fully unit-tested in isolation (the network layer lives in the
``weather`` router and is mocked in CI). Sun-aspect is intentionally out —
it is not auto-fetchable.
"""

from __future__ import annotations

import math
from typing import Dict, Literal, Tuple

ConditionBand = Literal["prime", "good", "ok", "poor"]

# --- Magnus-Tetens constants (over-water, valid for -45..60°C) -----------------
_MAGNUS_A = 17.625
_MAGNUS_B = 243.04

# --- A238 friction-score parameters (tunable) ---------------------------------
# Each component is normalized 0–1 (full-score plateau + linear decay to a
# floor), then weighted. Dew SPREAD (temp − dew point) is the friction proxy —
# a big spread means the air can absorb sweat/moisture regardless of raw temp.
FRICTION_WEIGHTS = {"temp": 0.30, "dew_spread": 0.30, "humidity": 0.25, "wind": 0.15}

TEMP_FULL_C = (5.0, 18.0)      # plateau; decays 18→26 (hot) and 5→−2 (cold)
TEMP_HOT_ZERO_C = 26.0
TEMP_COLD_ZERO_C = -2.0
SPREAD_FULL_C = 10.0           # plateau ≥10; decays 10→3; 0 below 3
SPREAD_ZERO_C = 3.0
HUMIDITY_FULL_PCT = 45.0       # plateau ≤45; decays 45→80; 0 above 80
HUMIDITY_ZERO_PCT = 80.0
WIND_FULL_KMH = (8.0, 25.0)    # plateau; decays 25→40 (harsh) and 8→0 (still)
WIND_HARSH_ZERO_KMH = 40.0

# --- B335 heat ceiling --------------------------------------------------------
# The temperature component is pinned at 0 above TEMP_HOT_ZERO_C, so its 30%
# weight silently drops out of the sum — while heat keeps RAISING dew spread and
# LOWERING relative humidity, the two components worth 55%. The score therefore
# climbed with temperature: D279 measured a Kalymnos day at 34°C scoring 70
# ("good — solid day to try hard") against 26°C scoring 43 ("ok"), and
# best_window duly recommended 15:00. Above ~28°C the limiter is the athlete,
# not the friction of the rock, so heat is capped here instead of merely
# abstaining. Below HEAT_CEILING_FROM_C nothing changes.
HEAT_CEILING_FROM_C = 26.0     # ceiling starts where the temp component dies
HEAT_CEILING_ZERO_C = 36.0     # ceiling reaches 0 — no score survives this heat
BAND_HOT_OK_C = 28.0           # ≥ this: band capped at ok, whatever the score
BAND_HOT_POOR_C = 32.0         # ≥ this: band capped at poor

# Band cut points on the 0–100 score.
BAND_PRIME_MIN = 80
BAND_GOOD_MIN = 60
BAND_OK_MIN = 40

# Legacy cold floor (A224) — still splits a poor rating into cold-dry vs
# hot-humid for the 4-value catalog vocabulary.
TEMP_OK_MIN_C = -6.0

_BAND_RANK = {"prime": 3, "good": 2, "ok": 1, "poor": 0}
_RANK_BAND = {v: k for k, v in _BAND_RANK.items()}


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


def _ramp(x: float, zero_at: float, full_at: float) -> float:
    """Linear 0→1 ramp: 0 at ``zero_at``, 1 at ``full_at`` (either direction)."""
    if full_at == zero_at:
        return 1.0 if x == full_at else 0.0
    t = (x - zero_at) / (full_at - zero_at)
    return max(0.0, min(1.0, t))


def friction_components(
    temp_c: float, humidity_pct: float, dew_point_c: float, wind_kmh: float
) -> Dict[str, float]:
    """Normalized 0–1 score per component (A238). Pure, deterministic."""
    if TEMP_FULL_C[0] <= temp_c <= TEMP_FULL_C[1]:
        temp = 1.0
    elif temp_c > TEMP_FULL_C[1]:
        temp = _ramp(temp_c, TEMP_HOT_ZERO_C, TEMP_FULL_C[1])
    else:
        temp = _ramp(temp_c, TEMP_COLD_ZERO_C, TEMP_FULL_C[0])

    spread = _ramp(temp_c - dew_point_c, SPREAD_ZERO_C, SPREAD_FULL_C)
    humidity = _ramp(humidity_pct, HUMIDITY_ZERO_PCT, HUMIDITY_FULL_PCT)

    if WIND_FULL_KMH[0] <= wind_kmh <= WIND_FULL_KMH[1]:
        wind = 1.0
    elif wind_kmh > WIND_FULL_KMH[1]:
        wind = _ramp(wind_kmh, WIND_HARSH_ZERO_KMH, WIND_FULL_KMH[1])
    else:
        wind = _ramp(wind_kmh, 0.0, WIND_FULL_KMH[0])

    return {"temp": temp, "dew_spread": spread, "humidity": humidity, "wind": wind}


def heat_score_ceiling(temp_c: float) -> int:
    """Upper bound the friction score may reach at *temp_c* (B335).

    100 (no effect) up to ``HEAT_CEILING_FROM_C``, then a linear decay to 0 at
    ``HEAT_CEILING_ZERO_C``. Pure, monotonically decreasing in temperature.
    """
    if temp_c <= HEAT_CEILING_FROM_C:
        return 100
    if temp_c >= HEAT_CEILING_ZERO_C:
        return 0
    span = HEAT_CEILING_ZERO_C - HEAT_CEILING_FROM_C
    return int(round(100 * (HEAT_CEILING_ZERO_C - temp_c) / span))


def compute_friction_score(
    temp_c: float,
    humidity_pct: float,
    dew_point_c: float,
    wind_kmh: float,
    precip_active: bool = False,
) -> Tuple[int, ConditionBand]:
    """Composite friction score 0–100 + band ``{prime, good, ok, poor}`` (A238).

    ``precip_active`` = rain/snow/fog now, measurable recent rain, or >30%
    precipitation probability in the current 3h forecast step — caps the band at
    poor. Sub-zero temperature caps the band at ok (ice / numb fingers). Those
    two caps move the band only, never the score.

    B335 adds the missing symmetric case at the hot end, and it *does* move the
    score: ``heat_score_ceiling`` clamps it above ``HEAT_CEILING_FROM_C`` so the
    result is monotonically decreasing in heat instead of rising with it, and the
    band is additionally capped at ok from ``BAND_HOT_OK_C`` and at poor from
    ``BAND_HOT_POOR_C``. Below ``HEAT_CEILING_FROM_C`` behaviour is unchanged.
    """
    comps = friction_components(temp_c, humidity_pct, dew_point_c, wind_kmh)
    score = round(100 * sum(FRICTION_WEIGHTS[k] * v for k, v in comps.items()))
    score = min(score, heat_score_ceiling(temp_c))

    if score >= BAND_PRIME_MIN:
        band: ConditionBand = "prime"
    elif score >= BAND_GOOD_MIN:
        band = "good"
    elif score >= BAND_OK_MIN:
        band = "ok"
    else:
        band = "poor"

    rank = _BAND_RANK[band]
    if precip_active:
        rank = min(rank, _BAND_RANK["poor"])
    if temp_c < 0.0:
        rank = min(rank, _BAND_RANK["ok"])
    if temp_c >= BAND_HOT_POOR_C:
        rank = min(rank, _BAND_RANK["poor"])
    elif temp_c >= BAND_HOT_OK_C:
        rank = min(rank, _BAND_RANK["ok"])
    return score, _RANK_BAND[rank]


# --- wind descriptor (Beaufort-aligned, English) ------------------------------
# Upper bound (km/h, exclusive) → label. Last entry is the catch-all.
_WIND_LABELS = (
    (1.0, "calm"),
    (6.0, "very light"),
    (12.0, "light"),
    (20.0, "moderate"),
    (29.0, "brisk"),
    (39.0, "fresh"),
    (50.0, "strong"),
    (float("inf"), "very strong"),
)


def wind_label(wind_kmh: float) -> str:
    """Qualitative English wind descriptor from speed in km/h (Beaufort-aligned)."""
    for upper, label in _WIND_LABELS:
        if wind_kmh < upper:
            return label
    return _WIND_LABELS[-1][1]


# --- A238 per-metric qualifiers (backend-owned copy) ---------------------------

def metric_qualifiers(
    temp_c: float,
    humidity_pct: float,
    dew_point_c: float,
    wind_kmh: float,
    precip_mm: float = 0.0,
) -> Dict[str, str]:
    """Plain-English chip per metric — the single source of truth for the UI.

    Keys: ``temp``, ``humidity``, ``dew_spread``, ``wind``, ``precip``.
    """
    spread = temp_c - dew_point_c

    if spread >= 10:
        spread_q = "prime friction"
    elif spread >= 5:
        spread_q = "good friction"
    elif spread >= 3:
        spread_q = "greasy risk"
    else:
        spread_q = "condensation"

    if humidity_pct <= 40:
        hum_q = "dry air"
    elif humidity_pct <= 60:
        hum_q = "ok"
    elif humidity_pct <= 75:
        hum_q = "humid"
    else:
        hum_q = "greasy"

    if temp_c < 5:
        temp_q = "cold — warm up well"
    elif temp_c <= 18:
        temp_q = "crisp"
    elif temp_c <= 24:
        temp_q = "warm"
    else:
        temp_q = "hot — 🔥"

    if wind_kmh < 5:
        wind_q = "still"
    elif wind_kmh <= 25:
        wind_q = "helps drying"
    elif wind_kmh <= 40:
        wind_q = "windy"
    else:
        wind_q = "harsh"

    return {
        "temp": temp_q,
        "humidity": hum_q,
        "dew_spread": spread_q,
        "wind": wind_q,
        "precip": "wet rock risk" if precip_mm > 0 else "dry",
    }


# --- A238 band headline (backend-owned copy) -----------------------------------

_BAND_HEADLINES: Dict[str, str] = {
    "prime": "Conditions are prime — go send your project.",
    "good": "Good conditions — solid day to try hard.",
    "ok": "Workable conditions — manage expectations.",
    "poor": "Poor conditions — consider the gym or a rest day.",
}

# Limiter suffix per weakest component (weighted). Emitted only when something
# is actually limiting (worst weighted component < its full weight).
_LIMITER_SUFFIX: Dict[str, str] = {
    "temp_hot": "Heat is the limiter — seek shade.",
    "temp_cold": "Cold is the limiter — warm up well, keep burns short.",
    "greasy": "Air is greasy — brush holds, chalk up.",
    "wind": "Wind is the limiter — bundle up between burns.",
}


def band_headline(
    band: ConditionBand,
    temp_c: float,
    humidity_pct: float,
    dew_point_c: float,
    wind_kmh: float,
    precip_active: bool = False,
) -> str:
    """Headline for the band + one contextual limiter suffix (A238).

    Deterministic: precip wins; otherwise the component with the lowest
    weighted score. No suffix when nothing is limiting (all components full).
    """
    head = _BAND_HEADLINES[band]
    if precip_active:
        return f"{head} Rock may be wet."

    comps = friction_components(temp_c, humidity_pct, dew_point_c, wind_kmh)
    weighted = {k: v * FRICTION_WEIGHTS[k] for k, v in comps.items()}
    worst = min(weighted, key=lambda k: weighted[k] - FRICTION_WEIGHTS[k])
    if comps[worst] >= 1.0:
        return head  # nothing limiting

    if worst == "temp":
        key = "temp_hot" if temp_c > TEMP_FULL_C[1] else "temp_cold"
    elif worst in ("dew_spread", "humidity"):
        key = "greasy"
    else:
        key = "wind"
    return f"{head} {_LIMITER_SUFFIX[key]}"


# --- catalog band (A225, updated A238) -----------------------------------------
# The C241 outdoor-strategy catalog splits "poor" into two actionable causes so
# the nudge can differ (precool/shade vs. warm hands/glassy tips). The friction
# band is mapped to the 4-value catalog vocabulary: ``good`` selects the ``ok``
# patches (conservative nudge — decision A238); a ``poor`` rating is classified
# by the *cause*: cold air → cold-dry; otherwise (greasy / wet / hot) → hot-humid.
CatalogConditionBand = Literal["prime", "ok", "poor_hot_humid", "poor_cold_dry"]


def catalog_condition_band(temp_c: float, band: ConditionBand) -> CatalogConditionBand:
    """Map the 4-value friction ``band`` → the 4-value catalog vocabulary.

    ``prime`` maps through; ``good`` → ``ok`` (conservative patch selection);
    ``poor`` is classified by air temperature: below the cold floor
    (``TEMP_OK_MIN_C``) → ``poor_cold_dry`` (numb fingers, glassy tips);
    otherwise → ``poor_hot_humid`` (greasy / wet / sweaty). Deterministic, pure.
    """
    if band == "good":
        return "ok"
    if band != "poor":
        return band  # prime | ok
    return "poor_cold_dry" if temp_c < TEMP_OK_MIN_C else "poor_hot_humid"
