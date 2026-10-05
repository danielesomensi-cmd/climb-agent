"""A294 — key status in the API: sibling of week_plan (never persisted),
/events dry_run (no writes), custom_session_payload, completion-log session id.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage, storage_file
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_state


def _monday() -> date:
    d = date.today()
    return d - timedelta(days=d.weekday())


def _plan(start: date, sessions: dict) -> dict:
    days = []
    for i in range(7):
        d = (start + timedelta(days=i)).isoformat()
        days.append({"date": d, "weekday": WEEKDAYS[i], "sessions": deepcopy(sessions.get(i, []))})
    return {"start_date": start.isoformat(), "weeks": [{"week_index": 1, "days": days}],
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": 4, "recovery_multiplier": 1.0,
                                 "session_pool": ["strength_long", "limit_boulder_gym", "finger_strength_home",
                                                  "technique_focus_gym"]}}


def _seed() -> dict:
    mon = _monday()
    state = deps.load_state(None)
    state["macrocycle"] = {
        "start_date": (mon - timedelta(weeks=1)).isoformat(),
        "end_date": (mon + timedelta(weeks=11) - timedelta(days=1)).isoformat(),
        "total_weeks": 12,
        "phases": [
            {"phase_id": "strength_power", "duration_weeks": 4, "domain_weights": {}, "session_pool": [],
             "start_week": 1, "end_week": 4},
            {"phase_id": "power_endurance", "duration_weeks": 4, "domain_weights": {}, "session_pool": [],
             "start_week": 5, "end_week": 8},
            {"phase_id": "performance", "duration_weeks": 4, "domain_weights": {}, "session_pool": [],
             "start_week": 9, "end_week": 12},
        ],
    }
    plan = _plan(mon, {
        0: [{"slot": "evening", "session_id": "limit_boulder_gym", "tags": {"hard": True, "finger": True}}],
        3: [{"slot": "evening", "session_id": "strength_long", "tags": {"hard": True, "finger": True}}],
        5: [{"slot": "evening", "session_id": "technique_focus_gym", "tags": {"hard": False, "finger": False}}],
    })
    state["week_plans"] = {mon.isoformat(): plan}
    state["current_week_plan"] = plan
    state["session_completion_log"] = []
    state["custom_sessions"] = [{"id": "cs_hang", "name": "Hangs",
                                 "exercises": [{"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7}]}]
    deps.save_state(state, None)
    return plan


def _today() -> str:
    return _monday().isoformat()


class TestEventsDryRun:
    def test_dry_run_returns_conflicts_and_writes_nothing(self):
        plan = _seed()
        before = deps.load_state(None)
        wed = (_monday() + timedelta(days=2)).isoformat()
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "dry_run": True, "today": _today(),
            "events": [{"event_type": "add_custom_session", "custom_session_id": "cs_hang",
                        "target_date": wed, "slot": "lunch", "location": "home"}],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dry_run"] is True
        codes = {(c["code"], c.get("key")) for c in body["key_conflicts"]}
        # A301: the key session the day after is no longer downshifted by the
        # insertion — the clash is a finger gap, never silent.
        assert ("finger_gap", None) in codes
        assert body["adjustments"] == []
        thu = (_monday() + timedelta(days=3)).isoformat()
        assert any(w["code"] == "finger_gap" and w["date"] == thu for w in body["added_guard_warnings"])
        assert any(w["code"] == "finger_gap" and w["date"] == thu for w in body["guard_warnings"])
        assert "key_status" in body and "key_status" not in body["week_plan"]
        after = deps.load_state(None)
        assert after["week_plans"] == before["week_plans"]
        assert after.get("session_completion_log") == before.get("session_completion_log")

    def test_dry_run_with_payload_creates_no_custom(self):
        plan = _seed()
        wed = (_monday() + timedelta(days=2)).isoformat()
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "dry_run": True, "today": _today(),
            "custom_session_payload": {"id": "preview", "name": "Coach",
                                       "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}]},
            "events": [{"event_type": "add_custom_session", "custom_session_id": "preview",
                        "target_date": wed, "slot": "lunch", "location": "home"}],
        })
        assert r.status_code == 200, r.text
        assert r.json()["key_conflicts"]
        assert all(c["id"] != "preview" for c in deps.load_state(None)["custom_sessions"])

    def test_dry_run_does_not_mutate_events(self):
        plan = _seed()
        events = [{"event_type": "mark_done", "date": _today(), "slot": "evening"}]
        r = client.post("/api/replanner/events", json={"week_plan": plan, "dry_run": True, "events": events})
        assert r.status_code == 200
        assert deps.load_state(None).get("session_completion_log") == []


class TestEventsReal:
    def test_key_status_sibling_and_adjustments(self):
        plan = _seed()
        wed = (_monday() + timedelta(days=2)).isoformat()
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "today": _today(),
            "events": [{"event_type": "add_custom_session", "custom_session_id": "cs_hang",
                        "target_date": wed, "slot": "lunch", "location": "home"}],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        # A301: nothing rewritten; the alert travels next to the plan.
        assert body["adjustments"] == []
        thu = (_monday() + timedelta(days=3)).isoformat()
        assert body["week_plan"]["weeks"][0]["days"][3]["sessions"][0]["session_id"] == "strength_long"
        assert any(w["code"] == "finger_gap" and w["date"] == thu for w in body["guard_warnings"])
        assert body["key_status"]["week_start"] == _monday().isoformat()
        saved = deps.load_state(None)
        assert "key_status" not in json.dumps(saved["week_plans"])
        assert "guard_warnings" not in json.dumps(saved["week_plans"])

    def test_slot_only_skip_logs_the_real_session_id(self):
        plan = _seed()
        thu = (_monday() + timedelta(days=3)).isoformat()
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "events": [{"event_type": "mark_skipped", "date": thu, "slot": "evening"}]})
        assert r.status_code == 200, r.text
        log = deps.load_state(None)["session_completion_log"]
        assert log[-1]["session_id"] == "strength_long" and log[-1]["status"] == "skipped"
        stub = r.json()["week_plan"]["weeks"][0]["days"][3]["sessions"][0]
        assert stub["skipped_session_id"] == "strength_long"

    def test_add_planned_session_event(self):
        plan = _seed()
        sun = (_monday() + timedelta(days=6)).isoformat()
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "events": [{"event_type": "add_planned_session", "session_id": "finger_strength_home",
                                           "target_date": sun, "slot": "morning", "location": "home"}]})
        assert r.status_code == 200, r.text
        s = r.json()["week_plan"]["weeks"][0]["days"][6]["sessions"][0]
        assert s["session_id"] == "finger_strength_home" and not s.get("is_custom")

    def test_add_planned_session_unknown_is_422(self):
        plan = _seed()
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "events": [{"event_type": "add_planned_session", "session_id": "nope",
                                           "target_date": _today(), "slot": "morning"}]})
        assert r.status_code == 422


class TestWeekEndpoint:
    def test_get_week_has_key_status_sibling(self):
        _seed()
        r = client.get(f"/api/week/0?today={_today()}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "key_status" not in body["week_plan"]
        ks = body.get("key_status")
        assert ks is not None and ks["source"] == "a294"
        assert ks["week_start"] == _monday().isoformat()
        saved = deps.load_state(None)
        assert "key_status" not in json.dumps(saved.get("week_plans") or {})
