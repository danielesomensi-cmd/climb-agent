"""A228: Pallof Press optional "weight used" logging (record-only).

Pallof Press is `load_model: bodyweight_only` (cable OR band) but opts into the
existing guided "weight used (kg)" field via `attributes.allow_load_logging`.

The logged weight is **record-only** — it persists on the session slot
(`actual_exercises`) so the user remembers it ("così mi ricordo"), and is NOT
consumed by the progression / closed-loop engine (confirmed by the D249 audit:
`apply_feedback` has no `bodyweight_only` branch).

These tests guard:
  1. the catalog opt-in contract,
  2. a numeric weight persists on the slot and creates NO working_loads entry,
  3. an empty weight is accepted (band users) without error or mutation,
  4. apply_feedback record-only invariant at the unit level,
  5. past/completed sessions are never rewritten when logging on a current one.
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
from backend.engine.progression_v1 import apply_feedback

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


# 1 — catalog opt-in contract
def test_pallof_catalog_opts_into_load_logging():
    data = json.loads(EXERCISES_PATH.read_text(encoding="utf-8"))
    pallof = next(e for e in data["exercises"] if e["id"] == "pallof_press")
    assert pallof["load_model"] == "bodyweight_only"
    assert (pallof.get("attributes") or {}).get("allow_load_logging") is True


# 2 — numeric weight persists on the slot (record path) + no engine consumption
def test_pallof_numeric_weight_persists_and_not_consumed():
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
    assert actual["pallof_press"]["used_external_load_kg"] == 12.5  # record persisted
    assert _pallof_working_entries(state) == []  # record-only, no engine consumption


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


# 4 — apply_feedback unit: record-only invariant (no working_loads mutation)
def test_apply_feedback_pallof_no_working_load_mutation():
    state = {"working_loads": {"entries": []}, "bodyweight_kg": 70.0}
    log_entry = {
        "date": "2026-04-06",
        "actual": {"exercise_feedback_v1": [
            {"exercise_id": "pallof_press", "load_model": "bodyweight_only",
             "feedback_label": "very_easy", "completed": True, "used_external_load_kg": 15.0}
        ]},
    }
    out = apply_feedback(log_entry, state)
    assert _pallof_working_entries(out) == []


# 5 — immutability: logging on a current session never rewrites a past completed one
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
