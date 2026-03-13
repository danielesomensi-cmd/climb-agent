"""Conversion utilities for hangboard ↔ loading pin baselines."""


# Rohmert's curve approximation: relative max at each duration (baseline = 5s).
_DURATION_FACTORS = {5: 1.00, 7: 0.93, 10: 0.85}

# Conversion factor: loading pin per-hand ≈ hangboard total / 2 × this factor.
_HB_TO_LP_FACTOR = 0.90


def hangboard_to_loading_pin(hb_total_load_kg: float) -> dict:
    """Convert two-arm hangboard max to estimated loading pin per-hand max.

    Formula: LP_per_hand = (HB_total / 2) × 0.90
    Returns dict with right and left estimates (same value — user refines via test).
    """
    lp_estimate = round((hb_total_load_kg / 2) * _HB_TO_LP_FACTOR, 1)
    return {"right": lp_estimate, "left": lp_estimate}


def loading_pin_to_hangboard(lp_right_kg: float, lp_left_kg: float) -> float:
    """Convert loading pin per-hand maxes to estimated two-arm hangboard total.

    Formula: HB_total = (avg(right, left) × 2) / 0.90
    """
    avg_lp = (lp_right_kg + lp_left_kg) / 2
    return round((avg_lp * 2) / _HB_TO_LP_FACTOR, 1)


def convert_duration_max(max_load_kg: float, from_seconds: int, to_seconds: int) -> float:
    """Convert a max load at one duration to estimated max at another duration.

    Based on simplified Rohmert's curve approximation.
    Factors (relative to 5s baseline): 5s = 1.00, 7s = 0.93, 10s = 0.85.
    """
    if from_seconds not in _DURATION_FACTORS or to_seconds not in _DURATION_FACTORS:
        return max_load_kg  # no conversion available
    return round(max_load_kg * (_DURATION_FACTORS[to_seconds] / _DURATION_FACTORS[from_seconds]), 1)
