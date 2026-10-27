"""B407 — a skip stub stands where the skipped session stood.

``mark_skipped`` swaps the session for a ``regeneration_easy`` stub. The stub
took ``location="gym"`` whenever the day had *any* gym session, with the
default gym id — on prod (27/10/2026) a home lunch skipped on a gym evening
became a gym stub with ``gym_id=None``, which the card labelled with the first
gym in the list (Cocque).
"""
from __future__ import annotations

import copy
from datetime import date, timedelta

from backend.engine.replanner_v1 import apply_events

MON = "2026-10-26"


def _home_custom(slot="lunch"):
    return {"slot": slot, "session_id": "custom_abc", "custom_session_id": "abc", "is_custom": True,
            "session_mode": "custom_build", "name": "Casa — gambe", "status": "planned",
            "location": "home", "gym_id": None, "intensity": "medium",
            "tags": {"hard": False, "finger": False},
            "exercises": [{"exercise_id": "reverse_lunge", "sets": 3}], "constraints_applied": ["custom_add"]}


def _gym(sid, slot="evening", gym_id="g_evening"):
    return {"slot": slot, "session_id": sid, "location": "gym", "gym_id": gym_id, "intensity": "high",
            "tags": {"hard": True, "finger": False}, "constraints_applied": []}


def _plan(sessions, default_gym_id=None):
    d0 = date.fromisoformat(MON)
    days = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(sessions if i == 1 else [])}
            for i in range(7)]
    prefs = {"default_gym_id": default_gym_id} if default_gym_id else {}
    return {"start_date": MON, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "power_endurance", "planning_prefs": prefs},
            "weeks": [{"week_index": 1, "days": days}], "adaptations": []}


def _stub(plan, ref, slot):
    out = apply_events(plan, [{"event_type": "mark_skipped", "date": "2026-10-27",
                               "session_ref": ref, "slot": slot}])
    return next(s for s in out["weeks"][0]["days"][1]["sessions"] if s.get("status") == "skipped")


def test_home_session_skipped_on_a_gym_day_leaves_a_home_stub():
    plan = _plan([_home_custom(), _gym("power_endurance_gym")], default_gym_id="g_default")
    stub = _stub(plan, "custom_abc", "lunch")
    assert stub["session_id"] == "regeneration_easy"
    assert stub["location"] == "home"
    assert stub["gym_id"] is None
    assert stub["skipped_original"]["name"] == "Casa — gambe"


def test_gym_session_skipped_keeps_its_own_gym():
    plan = _plan([_gym("power_endurance_gym", gym_id="g_forest")], default_gym_id="g_default")
    stub = _stub(plan, "power_endurance_gym", "evening")
    assert stub["location"] == "gym"
    assert stub["gym_id"] == "g_forest"


def test_gym_session_without_gym_id_falls_back_to_the_default_gym():
    plan = _plan([_gym("power_endurance_gym", gym_id=None)], default_gym_id="g_default")
    stub = _stub(plan, "power_endurance_gym", "evening")
    assert stub["location"] == "gym"
    assert stub["gym_id"] == "g_default"


def test_outdoor_skip_keeps_the_day_rule():
    # An outdoor/travel session is not a place a regeneration stub can stand:
    # the day's own gym/home rule still decides.
    outdoor = {"slot": "morning", "session_id": "outdoor_day", "location": "outdoor", "gym_id": None,
               "intensity": "high", "tags": {"hard": True, "finger": False}, "constraints_applied": []}
    plan = _plan([outdoor, _gym("power_endurance_gym")], default_gym_id="g_default")
    stub = _stub(plan, "outdoor_day", "morning")
    assert stub["location"] == "gym"
    assert stub["gym_id"] == "g_default"
