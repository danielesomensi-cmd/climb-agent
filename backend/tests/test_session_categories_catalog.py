"""A291 (R6a): closed-loop stimulus categories come from the catalog's
intent.primary_goal; the substring rule is only a fallback for ids the catalog
does not know, and 'power' no longer matches 'power_endurance'."""

from __future__ import annotations

import json
from pathlib import Path

from backend.engine.closed_loop_v1 import (
    STIMULUS_CATEGORIES,
    _catalog_primary_goals,
    _session_categories,
    apply_day_result_to_user_state,
)

SESSIONS_DIR = Path(__file__).resolve().parents[1] / "catalog" / "sessions" / "v1"


def test_limit_boulder_is_boulder_power_and_fingers():
    # Planned sessions in the week plan carry intent=None.
    assert _session_categories({"session_id": "limit_boulder_gym", "intent": None, "tags": {}}) == [
        "boulder_power", "finger_strength",
    ]


def test_power_contact_is_boulder_power():
    assert "boulder_power" in _session_categories({"session_id": "power_contact_gym", "intent": None})


def test_power_endurance_is_not_boulder_power():
    cats = _session_categories({"session_id": "power_endurance_gym", "intent": None,
                                "tags": {"hard": True, "finger": False}})
    assert cats == ["endurance"]


def test_strength_long_is_fingers():
    assert _session_categories({"session_id": "strength_long", "intent": None}) == ["finger_strength"]


def test_route_projecting_mapping():
    assert _session_categories({"session_id": "route_projecting_gym", "intent": None}) == [
        "complementaries", "endurance",
    ]


def test_sessions_without_primary_goal_are_mapped():
    for sid in ("finger_aerobic_base", "finger_endurance_short"):
        assert _session_categories({"session_id": sid}) == ["endurance", "finger_strength"]


def test_every_catalog_session_has_a_mapping():
    """Every catalog session either has a primary_goal or an explicit override,
    and maps into the known categories."""
    goals = _catalog_primary_goals()
    ids = {json.loads(p.read_text())["id"] for p in SESSIONS_DIR.glob("*.json")}
    assert ids == set(goals)
    missing = sorted(sid for sid, goal in goals.items() if not goal)
    assert missing == ["finger_aerobic_base", "finger_endurance_short"]
    for sid in ids:
        cats = _session_categories({"session_id": sid})
        assert cats and set(cats) <= set(STIMULUS_CATEGORIES), sid


def test_unknown_ids_use_substring_fallback():
    assert _session_categories({"session_id": "custom_power_board", "intent": None}) == ["boulder_power"]
    # 'power_endurance' inside an unknown id is endurance, not boulder_power.
    assert _session_categories({"session_id": "custom_power_endurance_mix", "intent": None}) == ["endurance"]
    assert _session_categories({"session_id": "something_custom", "intent": None}) == ["complementaries"]


def test_primary_goal_as_intent_string_for_unknown_id():
    """The resolver's pseudo-day passes the primary_goal string as intent."""
    assert _session_categories({"session_id": "adhoc_x", "intent": "limit_projecting"}) == [
        "boulder_power", "finger_strength",
    ]


def test_categories_do_not_collide_with_recency_groups():
    """body_part_picker reads stimulus_recency keys as recency groups: the
    category names must not be exercise recency_group values."""
    catalog = json.loads((Path(__file__).resolve().parents[1] / "catalog" / "exercises" / "v1" / "exercises.json").read_text())
    exercises = catalog if isinstance(catalog, list) else catalog.get("exercises", [])
    groups = {e.get("recency_group") for e in exercises if e.get("recency_group")}
    assert not groups & set(STIMULUS_CATEGORIES)


def test_power_endurance_done_writes_endurance_recency_only():
    state = {"stimulus_recency": {}}
    out = apply_day_result_to_user_state(
        state,
        resolved_day={"date": "2026-10-20", "sessions": [{"session_id": "power_endurance_gym", "intent": None,
                                                          "tags": {"hard": True, "finger": False}}]},
        status="done",
    )
    rec = out["stimulus_recency"]
    assert rec["endurance"]["last_done_date"] == "2026-10-20"
    assert rec.get("boulder_power", {}).get("last_done_date") is None
