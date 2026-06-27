"""A228: Pallof Press "weight used" logging.

A228 first exposed an optional "weight used (kg)" field on Pallof. A229 then
upgraded Pallof from `bodyweight_only` (record-only) to `external_load`, so the
field is now driven by load_model + the suggested load, and the value DOES feed
progression (see test_a229_pallof_weight_progression). These tests guard what
A228 still owns: the catalog modeling that surfaces the field, the value
persisting in the record/history, empty-weight acceptance (band users with no
number), and past/completed sessions never being rewritten.
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
EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


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


def _pallof_week_plan(date: str = "2026-04-06", session_id: str = "core_training") -> dict:
    """Minimal week plan with one planned core session containing pallof_press."""
    return {
        "start_date": date,
        "weeks": [{
            "phase": "base",
            "days": [{
                "date": date,
                "weekday": "mon",
                "sessions": [{
                    "session_id": session_id,
                    "slot": "evening",
                    "resolved": {
                        "resolved_session": {
                            "exercise_instances": [
                                {"exercise_id": "pallof_press", "load_model": "bodyweight_only"}
                            ]
                        },
                    },
                }],
            }],
        }],
    }


def _seed(wp: dict) -> None:
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
    state["session_completion_log"] = []
    deps.save_state(state, None)


def _pallof_working_entries(state: dict) -> list:
    entries = (state.get("working_loads") or {}).get("entries") or []
    return [e for e in entries if e.get("exercise_id") == "pallof_press"]


# 1 — catalog modeling. A229 superseded A228: pallof is now external_load and
#     the "weight used" field is driven by load_model + suggested load (not the
#     old A228 allow_load_logging flag, which was removed).
def test_pallof_catalog_is_external_load_band_or_cable():
    data = json.loads(EXERCISES_PATH.read_text(encoding="utf-8"))
    pallof = next(e for e in data["exercises"] if e["id"] == "pallof_press")
    assert pallof["load_model"] == "external_load"
    assert set(pallof.get("equipment_required_any") or []) == {"resistance_band", "cable_machine"}
    assert "allow_load_logging" not in (pallof.get("attributes") or {})


# 2 — numeric weight persists on the session slot (record path / history)
def test_pallof_numeric_weight_persists_in_record():
    wp = _pallof_week_plan()
    _seed(wp)

    r = client.post("/api/feedback", json={
        "log_entry": {
            "date": "2026-04-06",
            "session_id": "core_training",
            "actual": {"exercise_feedback_v1": [
                {"exercise_id": "pallof_press", "completed": True,
                 "feedback_label": "ok", "used_external_load_kg": 12.5}
            ]},
        },
    })
    assert r.status_code == 200, r.text

    state = deps.load_state(None)
    sess = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
    actual = {a["exercise_id"]: a for a in sess.get("actual_exercises", [])}
    assert actual["pallof_press"]["used_external_load_kg"] == 12.5  # logged weight in the record


# 3 — empty weight accepted (band users): no error, no value, no mutation
def test_pallof_empty_weight_accepted():
    wp = _pallof_week_plan()
    _seed(wp)

    r = client.post("/api/feedback", json={
        "log_entry": {
            "date": "2026-04-06",
            "session_id": "core_training",
            "actual": {"exercise_feedback_v1": [
                {"exercise_id": "pallof_press", "completed": True, "feedback_label": "ok"}
            ]},
        },
    })
    assert r.status_code == 200, r.text

    state = deps.load_state(None)
    sess = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
    actual = {a["exercise_id"]: a for a in sess.get("actual_exercises", [])}
    assert "used_external_load_kg" not in actual["pallof_press"]  # empty → no value
    assert _pallof_working_entries(state) == []


# 4 — immutability: logging on a current session never rewrites a past completed one
def test_pallof_past_session_untouched():
    cur_date = "2026-04-06"
    past_date = "2026-03-30"
    wp = _pallof_week_plan(cur_date)

    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {cur_date: deepcopy(wp)}
    state["session_completion_log"] = []
    # a past, already-completed pallof carrying a previously logged weight (7.0 kg)
    state["week_plans"][past_date] = {
        "start_date": past_date,
        "weeks": [{
            "phase": "base",
            "days": [{
                "date": past_date,
                "weekday": "mon",
                "sessions": [{
                    "session_id": "core_training",
                    "slot": "evening",
                    "status": "done",
                    "actual_exercises": [
                        {"exercise_id": "pallof_press", "used_external_load_kg": 7.0,
                         "feedback_label": "ok", "completed": True}
                    ],
                }],
            }],
        }],
    }
    deps.save_state(state, None)

    r = client.post("/api/feedback", json={
        "log_entry": {
            "date": cur_date,
            "session_id": "core_training",
            "actual": {"exercise_feedback_v1": [
                {"exercise_id": "pallof_press", "completed": True,
                 "feedback_label": "easy", "used_external_load_kg": 20.0}
            ]},
        },
    })
    assert r.status_code == 200, r.text

    state = deps.load_state(None)
    past = state["week_plans"][past_date]["weeks"][0]["days"][0]["sessions"][0]
    past_actual = {a["exercise_id"]: a for a in past["actual_exercises"]}
    assert past_actual["pallof_press"]["used_external_load_kg"] == 7.0  # untouched
