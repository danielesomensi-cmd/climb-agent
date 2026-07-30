"""B313 — "Boulder only (today)" must survive into the guided session.

A210 shipped the override as React state inside the session card: the preview
switched to boulder while the guided player, the feedback payload and the load
all kept reading the planned rope session (the player builds its state from
`session.resolved`, which the override never touched). The override now lands on
the slot itself, through POST /api/session/surface-override, so there is a single
source of truth for every consumer.

These tests pin the slot-level contract. The frontend side is one line — the
player already reads `session.resolved`.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
DATE = "2026-03-16"

# A gym with BOTH walls: the rope session resolves normally, and the boulder
# alternative is reachable — otherwise the override would fail for lack of a
# boulder wall rather than for the reason under test.
FULL_GYM = {
    "gym_id": "wall",
    "name": "Full Wall",
    "priority": 1,
    "equipment": [
        "gym_routes", "gym_boulder", "spraywall", "hangboard",
        "pullup_bar", "dumbbell", "barbell", "bench", "band",
    ],
}


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)

    state = deps.load_state(None)
    equipment = state.setdefault("equipment", {})
    equipment["gyms"] = [FULL_GYM]
    deps.save_state(state, None)
    yield tmp_state


def _resolve(session_id: str) -> dict:
    r = client.post("/api/session/resolve", json={
        "session_id": session_id,
        "context": {"location": "gym", "gym_id": "wall", "date": DATE, "target_date": DATE},
    })
    assert r.status_code == 200, r.text
    return r.json()["resolved"]


def _week_plan(session_id: str, **slot_extra) -> dict:
    slot = {
        "session_id": session_id,
        "slot": "evening",
        "location": "gym",
        "gym_id": "wall",
        "phase_id": "power_endurance",
        "intensity": "medium",
        "estimated_load_score": 40,
        "tags": {"hard": False, "finger": False},
        "resolved": _resolve(session_id),
    }
    slot.update(slot_extra)
    return {
        "start_date": DATE,
        "weeks": [{"phase": "power_endurance", "days": [
            {"date": DATE, "weekday": "mon", "sessions": [slot]},
        ]}],
    }


def _seed(week_plan: dict) -> None:
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(week_plan)
    state["week_plans"] = {week_plan["start_date"]: deepcopy(week_plan)}
    deps.save_state(state, None)


def _override(week_plan: dict, surface: str | None = "boulder", expect: int = 200) -> dict:
    r = client.post("/api/session/surface-override", json={
        "date": DATE, "session_index": 0, "surface": surface, "week_plan": week_plan,
    })
    assert r.status_code == expect, r.text
    return r.json().get("week_plan", {})


def _slot(week_plan: dict) -> dict:
    return week_plan["weeks"][0]["days"][0]["sessions"][0]


def _exercise_ids(slot: dict) -> list:
    rs = (slot.get("resolved") or {}).get("resolved_session") or {}
    return [i.get("exercise_id") for i in rs.get("exercise_instances") or []]


def _needs_rope(slot: dict) -> bool:
    rs = (slot.get("resolved") or {}).get("resolved_session") or {}
    return any(
        "gym_routes" in (i.get("equipment_required") or [])
        for i in rs.get("exercise_instances") or []
    )


class TestSwapMechanism:
    """Sessions that declare a `boulder_fallback` move onto it."""

    def test_slot_moves_to_the_declared_boulder_session(self):
        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        slot = _slot(_override(wp))

        assert slot["session_id"] == "boulder_circuit_gym"
        assert slot["surface_override"] == "boulder"
        assert slot["surface_override_from"] == "route_endurance_gym"
        assert _exercise_ids(slot), "the adapted session must have exercises"
        assert not _needs_rope(slot)

    def test_planner_fields_follow_the_new_session(self):
        """Stale hard/finger flags would drive the 48h finger gap off the wrong
        session, and the report's hard-day count with them."""
        wp = _week_plan("route_projecting_gym", intensity="max",
                        tags={"hard": True, "finger": True})
        _seed(wp)
        slot = _slot(_override(wp))

        assert slot["session_id"] == "limit_boulder_gym"
        # limit_boulder_gym is max/hard/finger — the flags moved with it.
        assert slot["intensity"] == "max"
        assert slot["tags"] == {"hard": True, "finger": True}
        assert slot["estimated_load_score"] == 85

    def test_the_week_router_does_not_resolve_the_rope_session_back(self):
        """_user_edited is what keeps _auto_resolve off an overridden slot —
        without it the next week fetch would silently undo the override."""
        from backend.api.routers.week import _auto_resolve

        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        overridden = _override(wp)

        _auto_resolve(overridden, deps.load_state(None), None)
        slot = _slot(overridden)
        assert slot["session_id"] == "boulder_circuit_gym"
        assert slot["surface_override"] == "boulder"
        assert not _needs_rope(slot)


class TestEquipmentMechanism:
    """Sessions without a declared fallback are re-resolved without the rope."""

    def test_same_session_resolved_without_rope_exercises(self):
        wp = _week_plan("power_endurance_gym")
        _seed(wp)
        assert _needs_rope(_slot(wp)), "fixture must start rope-dependent"

        slot = _slot(_override(wp))
        assert slot["session_id"] == "power_endurance_gym", "no swap without a fallback"
        assert slot["surface_override"] == "boulder"
        assert _exercise_ids(slot)
        assert not _needs_rope(slot)


class TestRevert:
    def test_revert_restores_the_planned_session_resolved(self):
        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        overridden = _override(wp)
        reverted = _override(overridden, surface=None)
        slot = _slot(reverted)

        assert slot["session_id"] == "route_endurance_gym"
        assert "surface_override" not in slot
        assert "surface_override_from" not in slot
        assert "_user_edited" not in slot
        # Renderable straight away — not an empty card waiting for a refetch.
        assert _exercise_ids(slot)

    def test_revert_without_an_override_is_a_no_op(self):
        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        slot = _slot(_override(wp, surface=None))
        assert slot["session_id"] == "route_endurance_gym"
        assert "surface_override" not in slot

    def test_applying_twice_keeps_the_planned_session_id(self):
        """Otherwise the second apply would record the boulder session as the
        thing to revert to, stranding the user on it."""
        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        once = _override(wp)
        twice = _override(once)
        assert _slot(twice)["surface_override_from"] == "route_endurance_gym"

        reverted = _override(twice, surface=None)
        assert _slot(reverted)["session_id"] == "route_endurance_gym"


class TestGuards:
    def test_completed_session_cannot_be_overridden(self):
        """Past sessions are immutable — the pillar, enforced server-side."""
        wp = _week_plan("route_endurance_gym", status="done")
        _seed(wp)
        _override(wp, expect=409)

    def test_skipped_session_cannot_be_overridden(self):
        wp = _week_plan("route_endurance_gym", status="skipped")
        _seed(wp)
        _override(wp, expect=409)

    def test_custom_session_is_rejected(self):
        wp = _week_plan("route_endurance_gym", is_custom=True)
        _seed(wp)
        _override(wp, expect=422)

    def test_no_boulder_wall_fails_loudly(self):
        """A gym with ropes only: better a 422 than a card with zero exercises."""
        state = deps.load_state(None)
        state["equipment"]["gyms"] = [{
            "gym_id": "wall", "name": "Ropes Only", "priority": 1,
            "equipment": ["gym_routes", "hangboard", "pullup_bar"],
        }]
        deps.save_state(state, None)

        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        _override(wp, expect=422)

    def test_unknown_date_is_404(self):
        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        r = client.post("/api/session/surface-override", json={
            "date": "2030-01-01", "session_index": 0, "surface": "boulder", "week_plan": wp,
        })
        assert r.status_code == 404, r.text


class TestDownstreamConsumers:
    """The point of the brief: everything downstream now sees one session."""

    def test_feedback_on_the_adapted_session_is_not_stale(self):
        """Pre-B313 the player sent rope exercise_ids against a boulder session
        (or vice versa) and the D172-04 guard flagged them as stale."""
        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        overridden = _override(wp)
        _seed(overridden)
        slot = _slot(overridden)

        items = [
            {"exercise_id": ex, "feedback_label": "ok", "completed": True}
            for ex in _exercise_ids(slot)
        ]
        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": DATE,
                "session_id": slot["session_id"],
                "actual": {"exercise_feedback_v1": items},
            },
            "status": "done",
        })
        assert r.status_code == 200, r.text
        assert not r.json().get("stale_exercise_warning")

    def test_b312_load_is_measured_against_the_adapted_session(self):
        """Skipping half the boulder session must lower the load of the boulder
        session — not be scored against the rope prescription."""
        wp = _week_plan("route_endurance_gym")
        _seed(wp)
        overridden = _override(wp)
        _seed(overridden)
        slot = _slot(overridden)
        ids = _exercise_ids(slot)
        prescribed = slot["resolved"]["session_load_score"]

        half = len(ids) // 2
        items = [
            {"exercise_id": ex, "feedback_label": "ok", "completed": idx < half}
            for idx, ex in enumerate(ids)
        ]
        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": DATE,
                "session_id": slot["session_id"],
                "actual": {"exercise_feedback_v1": items},
            },
            "status": "done",
        })
        assert r.status_code == 200, r.text

        stored = _slot(deps.load_state(None)["current_week_plan"])
        assert stored["session_load_actual"] < prescribed
