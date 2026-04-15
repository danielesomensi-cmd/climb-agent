"""A210: verify boulder_fallback field is present in every climbing session JSON.

Climbing sessions (`_SESSION_META[sid]["climbing"] is True`) must declare an explicit
`boulder_fallback: str | null` so the resolver/frontend can pick the right override
mechanism. Only three sessions whose core block is rope-bound carry a non-null fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.engine.planner_v2 import _SESSION_META

SESSIONS_DIR = Path(__file__).resolve().parents[2] / "backend" / "catalog" / "sessions" / "v1"

EXPECTED_FALLBACKS: dict[str, str | None] = {
    "endurance_aerobic_gym": "boulder_circuit_gym",
    "route_endurance_gym": "boulder_circuit_gym",
    "route_projecting_gym": "limit_boulder_gym",
}


def _climbing_session_ids() -> list[str]:
    return sorted(sid for sid, meta in _SESSION_META.items() if meta.get("climbing"))


def test_boulder_fallback_field_present_in_all_climbing_sessions():
    missing: list[str] = []
    wrong_type: list[tuple[str, object]] = []
    wrong_value: list[tuple[str, object, object]] = []

    for sid in _climbing_session_ids():
        path = SESSIONS_DIR / f"{sid}.json"
        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        if "boulder_fallback" not in data:
            missing.append(sid)
            continue

        value = data["boulder_fallback"]
        if value is not None and not isinstance(value, str):
            wrong_type.append((sid, value))
            continue

        expected = EXPECTED_FALLBACKS.get(sid)  # None for sessions not in the map
        if value != expected:
            wrong_value.append((sid, value, expected))

    assert not missing, f"Missing boulder_fallback in climbing sessions: {missing}"
    assert not wrong_type, f"boulder_fallback must be str or null: {wrong_type}"
    assert not wrong_value, (
        f"boulder_fallback value mismatch (sid, actual, expected): {wrong_value}"
    )


def test_boulder_fallback_targets_exist_and_are_boulder():
    """Non-null fallback targets must (a) exist as session JSONs and (b) not themselves be rope-bound."""
    for source_sid, target_sid in EXPECTED_FALLBACKS.items():
        target_path = SESSIONS_DIR / f"{target_sid}.json"
        assert target_path.exists(), f"{source_sid} → missing fallback target {target_sid}"

        with target_path.open(encoding="utf-8") as f:
            target = json.load(f)

        req = target.get("required_equipment") or []
        assert "gym_routes" not in req, (
            f"{source_sid} → {target_sid} fallback is itself rope-bound ({req})"
        )
