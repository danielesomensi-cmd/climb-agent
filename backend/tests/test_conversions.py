"""Tests for hangboard ↔ loading pin conversion functions."""

import pytest

from backend.engine.conversions import (
    convert_duration_max,
    hangboard_to_loading_pin,
    loading_pin_to_hangboard,
)


# ── hangboard_to_loading_pin ────────────────────────────────────────────────


def test_hb_to_lp_basic():
    """100 kg HB total → each hand ≈ 45.0 kg."""
    result = hangboard_to_loading_pin(100.0)
    assert result == {"right": 45.0, "left": 45.0}


def test_hb_to_lp_odd_value():
    """Verify rounding to 1 decimal."""
    result = hangboard_to_loading_pin(93.0)
    expected = round((93.0 / 2) * 0.90, 1)
    assert result["right"] == expected
    assert result["left"] == expected


def test_hb_to_lp_zero():
    result = hangboard_to_loading_pin(0.0)
    assert result == {"right": 0.0, "left": 0.0}


# ── loading_pin_to_hangboard ────────────────────────────────────────────────


def test_lp_to_hb_symmetric():
    """45 kg each hand → HB total = (45 × 2) / 0.90 = 100.0."""
    assert loading_pin_to_hangboard(45.0, 45.0) == 100.0


def test_lp_to_hb_asymmetric():
    """Different per-hand values: uses average."""
    result = loading_pin_to_hangboard(50.0, 40.0)
    expected = round(((50.0 + 40.0) / 2 * 2) / 0.90, 1)
    assert result == expected


def test_roundtrip_hb_lp_hb():
    """HB → LP → HB should return approximately the original value."""
    original = 102.0
    lp = hangboard_to_loading_pin(original)
    back = loading_pin_to_hangboard(lp["right"], lp["left"])
    assert abs(back - original) < 0.5


# ── convert_duration_max ────────────────────────────────────────────────────


def test_duration_5s_to_7s():
    """5s → 7s: factor = 0.93/1.00 = 0.93."""
    result = convert_duration_max(50.0, 5, 7)
    assert result == 46.5


def test_duration_5s_to_10s():
    """5s → 10s: factor = 0.85/1.00 = 0.85."""
    result = convert_duration_max(50.0, 5, 10)
    assert result == 42.5


def test_duration_7s_to_5s():
    """7s → 5s: factor = 1.00/0.93 ≈ 1.075."""
    result = convert_duration_max(46.5, 7, 5)
    assert result == 50.0


def test_duration_10s_to_7s():
    """10s → 7s: factor = 0.93/0.85 ≈ 1.094."""
    result = convert_duration_max(42.5, 10, 7)
    assert result == round(42.5 * (0.93 / 0.85), 1)


def test_duration_same():
    """Same duration → no change."""
    assert convert_duration_max(50.0, 5, 5) == 50.0


def test_duration_unknown_returns_unchanged():
    """Unknown duration (e.g. 3s) → returns input unchanged."""
    assert convert_duration_max(50.0, 3, 7) == 50.0
    assert convert_duration_max(50.0, 5, 3) == 50.0
