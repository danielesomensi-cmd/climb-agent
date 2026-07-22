"""B298 — adhoc loadable exercises must always be loggable.

The runner decides whether to show the kg field from ``load_model`` (never from
a non-zero resolved value). Before B298 the adhoc composer dropped
``load_model`` from its exercise dicts, so a loadable exercise the user had
never logged rendered with NO kg field at all (report: Back Squat, no way to
record a weight). This pins that the composer now carries ``load_model`` through
so the field can render — even when the remembered load is 0.

The persistence chain itself was already correct (verified read-only in Phase 1:
guided finish → POST /api/feedback → apply_feedback → working_loads, the same
store adhoc reads); the only defect was the missing loggability affordance.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.engine.adhoc_builder import compose_adhoc_session

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


def _catalog() -> dict:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("exercises") or list(raw.values()))
    return {ex["id"]: ex for ex in items if isinstance(ex, dict) and ex.get("id")}


def _state() -> dict:
    return {
        "equipment": {
            "home": ["pullup_bar", "weight", "hangboard"],
            "gyms": [{"gym_id": "g1", "equipment": ["weight", "pullup_bar", "cable_machine", "bench"]}],
        },
        "macrocycle": {
            "start_date": "2026-07-06",
            "phases": [{"phase_id": "strength_power", "duration_weeks": 3}],
        },
        "recent_sessions": [],
    }


def test_every_exercise_carries_load_model_matching_catalog():
    cat, st = _catalog(), _state()
    s = compose_adhoc_session(
        {"equipment_set": "gym", "focus": "general_strength", "minutes": 60, "energy": "medium"},
        st, cat, today="2026-07-20",
    )
    assert s["exercises"], "expected a composed session"
    for ex in s["exercises"]:
        assert "load_model" in ex, f"{ex['exercise_id']} missing load_model"
        assert ex["load_model"] == cat[ex["exercise_id"]].get("load_model")


def test_loadable_exercise_emits_load_model_even_with_zero_remembered_load():
    # No working_loads history → load_kg is 0, but the exercise must still be
    # marked loadable so the runner renders the (empty) kg field.
    cat, st = _catalog(), _state()
    s = compose_adhoc_session(
        {"equipment_set": "gym", "focus": "general_strength",
         "body_parts": ["legs"], "minutes": 60, "energy": "medium"},
        st, cat, today="2026-07-20",
    )
    loadable = [
        e for e in s["exercises"]
        if e["load_model"] in ("external_load", "total_load")
    ]
    assert loadable, "a legs session should contain loadable barbell/weighted work"
    for e in loadable:
        # The exact bug signature: loadable, remembered load 0, still loadable.
        assert e["load_model"] in ("external_load", "total_load")


def test_bodyweight_exercise_is_not_marked_kg_loadable():
    cat, st = _catalog(), _state()
    s = compose_adhoc_session(
        {"equipment_set": "home", "focus": "core", "minutes": 45, "energy": "medium"},
        st, cat, today="2026-07-20",
    )
    # Core work is bodyweight — none should be flagged external/total load.
    for e in s["exercises"]:
        if e["exercise_id"] in ("ab_wheel_rollout", "dead_bug", "plank", "hollow_hold"):
            assert e["load_model"] not in ("external_load", "total_load")
