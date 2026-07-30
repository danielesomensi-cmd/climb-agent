"""B312 — end-to-end: POST /api/feedback lowers the load when exercises are skipped.

The unit-level rules live in test_b312_load_actual.py. This file drives the real
endpoint, because the payoff only materialises if `session_load_actual` actually
lands on the session slot (in every plan copy: current_week_plan AND the
week_plans cache that GET /api/week reads) and the weekly report picks it up.

Follows the A139/A194 pattern: real TestClient, isolated state file.
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
from backend.engine.load_score import fatigue_map_from_catalog, load_score_from_ids
from backend.engine.report_engine import _build_load

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
DATE = "2026-03-16"
SESSION_ID = "strength_long"

# Three real catalog exercises with non-zero fatigue_cost (9 / 7 / 4).
EXERCISES = ["max_hang_7s", "weighted_pullup", "core_hollow_hold"]


def _catalog_fatigue() -> dict:
    with open(
        REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json",
        encoding="utf-8",
    ) as fh:
        catalog = json.load(fh)
    return fatigue_map_from_catalog(
        catalog if isinstance(catalog, list) else catalog.get("exercises", [])
    )


# The prescribed score is derived from the catalog, not hardcoded: hardcoding it
# would make "full completion == prescribed" pass for the wrong reason.
PRESCRIBED = load_score_from_ids(EXERCISES, _catalog_fatigue())


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
    yield tmp_state


def _week_plan() -> dict:
    return {
        "start_date": DATE,
        "weekly_load_summary": {"planned_load": 100},
        "weeks": [{
            "phase": "base",
            "days": [{
                "date": DATE,
                "weekday": "mon",
                "sessions": [{
                    "session_id": SESSION_ID,
                    "slot": "evening",
                    "estimated_load_score": 65,
                    "resolved": {
                        "session_load_score": PRESCRIBED,
                        "resolved_session": {
                            "exercise_instances": [
                                {"exercise_id": ex} for ex in EXERCISES
                            ],
                        },
                    },
                }],
            }],
        }],
    }


def _seed() -> None:
    wp = _week_plan()
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
    state["session_completion_log"] = []
    deps.save_state(state, None)


def _post(completed_flags: list[bool]) -> dict:
    """POST feedback with one item per exercise, then return the stored state."""
    items = [
        {"exercise_id": ex, "feedback_label": "ok", "completed": done}
        for ex, done in zip(EXERCISES, completed_flags)
    ]
    r = client.post("/api/feedback", json={
        "log_entry": {
            "date": DATE,
            "session_id": SESSION_ID,
            "actual": {"exercise_feedback_v1": items},
        },
        "status": "done",
    })
    assert r.status_code == 200, r.text
    return deps.load_state(None)


def _slot(state: dict, plan_key: str = "current_week_plan") -> dict:
    plan = state[plan_key] if plan_key == "current_week_plan" else state["week_plans"][DATE]
    return plan["weeks"][0]["days"][0]["sessions"][0]


class TestB312FeedbackEndpoint:
    def test_skipping_exercises_records_a_lower_actual_load(self):
        _seed()
        state = _post([True, False, False])
        slot = _slot(state)

        assert "session_load_actual" in slot, "feedback must record the earned load"
        assert slot["session_load_actual"] < slot["resolved"]["session_load_score"], (
            f"actual {slot['session_load_actual']} should be below the prescribed "
            f"{slot['resolved']['session_load_score']}"
        )

    def test_completing_everything_matches_the_prescribed_load(self):
        _seed()
        slot = _slot(_post([True, True, True]))
        assert slot["session_load_actual"] == slot["resolved"]["session_load_score"]

    def test_prescribed_score_is_never_overwritten(self):
        """load_ratio needs an untouched denominator."""
        _seed()
        slot = _slot(_post([True, False, False]))
        assert slot["resolved"]["session_load_score"] == PRESCRIBED

    def test_actual_load_lands_in_the_week_plans_cache_too(self):
        """GET /api/week reads the cache — the two copies must not disagree."""
        _seed()
        state = _post([True, False, False])
        assert (
            _slot(state, "week_plans")["session_load_actual"]
            == _slot(state)["session_load_actual"]
        )

    def test_weekly_report_load_drops(self):
        """The number the user actually sees on /reports/weekly."""
        _seed()
        partial_state = _post([True, False, False])
        partial = _build_load(partial_state["current_week_plan"], [], [], [], DATE)

        _seed()
        full_state = _post([True, True, True])
        full = _build_load(full_state["current_week_plan"], [], [], [], DATE)

        assert partial["actual_total"] < full["actual_total"]
        assert partial["load_ratio"] < full["load_ratio"]
        assert full["actual_total"] == PRESCRIBED, "full completion == prescribed load"

    def test_dialog_payload_without_completed_flags_keeps_prescribed_load(self):
        """/today and /week send no skip signal — nothing must be subtracted."""
        _seed()
        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": DATE,
                "session_id": SESSION_ID,
                "actual": {"exercise_feedback_v1": [
                    {"exercise_id": ex, "feedback_label": "ok"} for ex in EXERCISES
                ]},
            },
            "status": "done",
        })
        assert r.status_code == 200, r.text
        slot = _slot(deps.load_state(None))
        assert "session_load_actual" not in slot
        report = _build_load(deps.load_state(None)["current_week_plan"], [], [], [], DATE)
        assert report["actual_total"] == PRESCRIBED

    def test_undo_clears_the_actual_load(self):
        """B192 + B312: mark_planned must not leave a ghost actual load behind."""
        _seed()
        state = _post([True, False, False])
        assert "session_load_actual" in _slot(state)

        r = client.post("/api/replanner/events", json={
            "week_plan": state["current_week_plan"],
            "events": [{
                "event_type": "mark_planned",
                "date": DATE,
                "session_ref": SESSION_ID,
            }],
        })
        assert r.status_code == 200, r.text
        updated = r.json()
        plan = updated.get("week_plan") or updated
        slot = plan["weeks"][0]["days"][0]["sessions"][0]
        assert "session_load_actual" not in slot
        assert "actual_exercises" not in slot
