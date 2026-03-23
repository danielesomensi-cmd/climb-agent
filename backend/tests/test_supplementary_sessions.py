"""Tests for B-SUPP — Supplementary training via quick-add."""

from __future__ import annotations

import json
from pathlib import Path

from backend.api.routers.replanner import _get_supplementary_sessions

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "catalog" / "sessions" / "v1"

SUPPLEMENTARY_IDS = {
    "upper_body_weights",
    "legs_strength",
    "lower_body_gym",
    "heavy_conditioning_gym",
    "pulling_strength_gym",
}

HOME_SUPPLEMENTARY = {"upper_body_weights", "legs_strength"}
GYM_SUPPLEMENTARY = {"lower_body_gym", "heavy_conditioning_gym", "pulling_strength_gym"}


# ---------- Catalog flag ----------


def test_all_supplementary_sessions_have_flag():
    """All 5 supplementary sessions must have supplementary: true."""
    for sid in SUPPLEMENTARY_IDS:
        path = SESSIONS_DIR / f"{sid}.json"
        assert path.exists(), f"Session file missing: {sid}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("supplementary") is True, f"{sid} missing supplementary: true"


def test_non_supplementary_sessions_lack_flag():
    """Spot-check that non-supplementary sessions do NOT have the flag."""
    non_supp = ["strength_short_gym", "finger_endurance_long", "boulder_power_gym"]
    for sid in non_supp:
        path = SESSIONS_DIR / f"{sid}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            assert not data.get("supplementary"), f"{sid} should not be supplementary"


# ---------- _get_supplementary_sessions ----------


def test_gym_returns_only_gym_supplementary():
    results = _get_supplementary_sessions("gym")
    ids = {r["session_id"] for r in results}
    assert ids == GYM_SUPPLEMENTARY, f"Expected {GYM_SUPPLEMENTARY}, got {ids}"


def test_home_returns_only_home_supplementary():
    results = _get_supplementary_sessions("home")
    ids = {r["session_id"] for r in results}
    assert ids == HOME_SUPPLEMENTARY, f"Expected {HOME_SUPPLEMENTARY}, got {ids}"


def test_supplementary_response_fields():
    """Each supplementary entry has the required fields."""
    results = _get_supplementary_sessions("gym")
    for r in results:
        assert "session_id" in r
        assert "session_name" in r
        assert "required_equipment" in r
        assert isinstance(r["required_equipment"], list)
        assert "time_budget" in r


def test_supplementary_deterministic():
    """Same input → same output."""
    a = _get_supplementary_sessions("gym")
    b = _get_supplementary_sessions("gym")
    assert a == b


def test_supplementary_not_in_climbing_suggestions():
    """Supplementary sessions should NOT appear in the regular suggest_sessions pool
    (they are excluded from phase pools by design)."""
    from backend.engine.macrocycle_v1 import _build_session_pool
    for phase in ["base", "strength_power", "power_endurance", "performance", "deload"]:
        pool = _build_session_pool(phase)
        for sid in SUPPLEMENTARY_IDS:
            assert sid not in pool, f"{sid} found in {phase} pool — supplementary sessions should not be in phase pools"
