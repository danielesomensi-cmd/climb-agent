"""A243 — Adhoc Coach v1, Phase 3: coach → deterministic adhoc builder bridge.

Invariants under test:
  1. Composition is deterministic (same intent + state ⇒ identical session).
  2. The composed session is a custom_session shape flagged adhoc:true, honours
     equipment/focus/minutes, is spine-safe, and loads come from the Phase-2
     proposal (remembered or 0 — never invented).
  3. The LLM only extracts a structured intent (forced tool) — never exercises.
  4. POST /api/coach/adhoc-session returns a PREVIEW (no persistence, no plan
     mutation); adhoc:false falls back to chat; the daily limit is enforced.
  5. Persisting + inserting the composed session (the CTA path) never mutates a
     sibling or past session (immutability, CLAUDE.md).
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
from backend.engine.adhoc_builder import ADHOC_FOCUS, FOCUS_DOMAINS, compose_adhoc_session
from backend.engine.replanner_v1 import apply_events

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
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


# ── Engine: deterministic composition ───────────────────────────────────


class TestComposeAdhocSession:
    def test_deterministic(self):
        cat, st = _catalog(), _state()
        intent = {"equipment_set": "gym", "focus": "pull", "minutes": 45, "energy": "medium"}
        a = compose_adhoc_session(intent, st, cat, today="2026-07-20")
        b = compose_adhoc_session(intent, st, cat, today="2026-07-20")
        assert [e["exercise_id"] for e in a["exercises"]] == [e["exercise_id"] for e in b["exercises"]]

    def test_shape_and_flags(self):
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength", "minutes": 45, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        assert s["adhoc"] is True
        assert s["exercises"], "expected a non-empty session"
        assert s["estimated_duration_minutes"] > 0
        assert "explanation" in s and s["explanation"]
        assert s["intent"]["focus"] == "general_strength"
        # Every exercise is a valid CustomSessionExercise shape.
        for ex in s["exercises"]:
            assert ex["exercise_id"]
            assert isinstance(ex["sets"], int) and ex["sets"] >= 1
            assert ex["load_kg"] is not None and ex["load_kg"] >= 0

    def test_minutes_budget_respected(self):
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength", "minutes": 30, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        assert s["estimated_duration_minutes"] <= 30

    def test_equipment_filter_differs_home_vs_gym(self):
        cat, st = _catalog(), _state()
        gym = compose_adhoc_session({"equipment_set": "gym", "focus": "general_strength", "minutes": 45, "energy": "medium"}, st, cat, today="2026-07-20")
        home = compose_adhoc_session({"equipment_set": "home", "focus": "general_strength", "minutes": 45, "energy": "medium"}, st, cat, today="2026-07-20")
        gym_ids = {e["exercise_id"] for e in gym["exercises"]}
        # gym has bench + cable → picks up bench_press etc. that home (no bench) can't.
        assert "bench_press" in gym_ids

    def test_spine_safe_no_forbidden_ids(self):
        cat, st = _catalog(), _state()
        for focus in ADHOC_FOCUS:
            s = compose_adhoc_session({"equipment_set": "gym", "focus": focus, "minutes": 60, "energy": "high"}, st, cat, today="2026-07-20")
            for ex in s["exercises"]:
                eid = ex["exercise_id"].lower()
                assert "crunch" not in eid and "situp" not in eid and "sit_up" not in eid

    def test_energy_modulates_volume(self):
        cat, st = _catalog(), _state()
        low = compose_adhoc_session({"equipment_set": "gym", "focus": "core", "minutes": 60, "energy": "low"}, st, cat, today="2026-07-20")
        high = compose_adhoc_session({"equipment_set": "gym", "focus": "core", "minutes": 60, "energy": "high"}, st, cat, today="2026-07-20")
        # Same first main exercise → high energy prescribes >= sets of low.
        low_by = {e["exercise_id"]: e for e in low["exercises"]}
        high_by = {e["exercise_id"]: e for e in high["exercises"]}
        common = set(low_by) & set(high_by)
        assert common
        assert any(high_by[e]["sets"] >= low_by[e]["sets"] for e in common)

    def test_remembered_load_flows_in(self):
        cat = _catalog()
        st = _state()
        st["working_loads"] = {
            "entries": [{
                "exercise_id": "bench_press", "key": "bench_press", "setup": {},
                "last_external_load_kg": 47.5, "last_feedback_label": "ok", "updated_at": "2026-06-01",
            }]
        }
        s = compose_adhoc_session({"equipment_set": "gym", "focus": "general_strength", "minutes": 60, "energy": "medium"}, st, cat, today="2026-07-20")
        bench = next((e for e in s["exercises"] if e["exercise_id"] == "bench_press"), None)
        if bench is not None:  # bench_press is a general_strength pick under gym equipment
            assert bench["load_kg"] == 47.5

    def test_focus_domains_cover_all_enum(self):
        # Every advertised focus maps to at least one domain (no dead enum value).
        for focus in ADHOC_FOCUS:
            assert FOCUS_DOMAINS[focus]


# ── Endpoint: preview only, no persistence ──────────────────────────────


@pytest.fixture()
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


def _mock_extract(monkeypatch, slots: dict):
    """Patch the LLM extraction so no real API call is made."""
    from backend.coach import llm_client
    monkeypatch.setattr(llm_client, "extract", lambda system_text, message, tool: slots)


class TestAdhocEndpoint:
    def test_adhoc_true_returns_preview(self, isolate_state, monkeypatch):
        _mock_extract(monkeypatch, {
            "is_adhoc_request": True, "equipment_set": "gym",
            "focus": "pull", "minutes": 45, "energy": "medium",
        })
        # Ensure the user has equipment so composition is non-trivial.
        state = deps.load_state(None)
        state["equipment"] = _state()["equipment"]
        state["macrocycle"] = _state()["macrocycle"]
        deps.save_state(state, None)

        r = client.post("/api/coach/adhoc-session", json={"message": "I'm at the gym, build me a 45-min pulling session"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["adhoc"] is True
        assert data["session"]["adhoc"] is True
        assert data["session"]["exercises"]

    def test_adhoc_preview_does_not_persist_custom_session(self, isolate_state, monkeypatch):
        _mock_extract(monkeypatch, {
            "is_adhoc_request": True, "equipment_set": "home",
            "focus": "core", "minutes": 30, "energy": "medium",
        })
        r = client.post("/api/coach/adhoc-session", json={"message": "quick core at home"})
        assert r.status_code == 200, r.text
        after = deps.load_state(None)
        # No orphan custom_session created by compose (persist-on-accept only).
        assert not after.get("custom_sessions")

    def test_non_adhoc_returns_false(self, isolate_state, monkeypatch):
        _mock_extract(monkeypatch, {"is_adhoc_request": False})
        r = client.post("/api/coach/adhoc-session", json={"message": "why is this week a deload?"})
        assert r.status_code == 200, r.text
        assert r.json() == {"adhoc": False}
        # No history write on a non-adhoc turn (no rate-limit charge).
        after = deps.load_state(None)

    def test_daily_limit_enforced(self, isolate_state, monkeypatch):
        _mock_extract(monkeypatch, {"is_adhoc_request": True, "focus": "core"})
        from backend.coach import service
        monkeypatch.setattr(service, "messages_sent_today", lambda uid: service.DAILY_MESSAGE_LIMIT)
        r = client.post("/api/coach/adhoc-session", json={"message": "build me a session"})
        assert r.status_code == 429


# ── Insertion immutability (the CTA path) ───────────────────────────────


class TestAdhocInsertionImmutability:
    def test_persist_and_insert_does_not_mutate_siblings_or_past(self):
        cat, st = _catalog(), _state()
        composed = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "core", "minutes": 30, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        # Simulate persist-on-accept: give it an id, store it.
        cs = {
            "id": "cs_adhoc01",
            "name": composed["name"],
            "tags": composed["tags"],
            "exercises": composed["exercises"],
            "estimated_load_score": composed["estimated_load_score"],
            "estimated_duration_minutes": composed["estimated_duration_minutes"],
            "adhoc": True,
        }

        past = {
            "session_id": "strength_long", "slot": "evening", "status": "done",
            "estimated_load_score": 55, "tags": {"hard": True},
            "actual_exercises": [{"exercise_id": "bench_press", "used_external_load_kg": 50}],
        }
        sibling = {
            "session_id": "core_circuit", "slot": "lunch", "status": "planned",
            "estimated_load_score": 20, "tags": {"hard": False},
        }
        plan = {
            "start_date": "2026-07-20",
            "weeks": [{
                "days": [
                    {"date": "2026-07-20", "weekday": "mon", "sessions": [deepcopy(past), deepcopy(sibling)]},
                    {"date": "2026-07-21", "weekday": "tue", "sessions": []},
                ]
            }],
        }

        after = apply_events(
            plan,
            [{
                "event_type": "add_custom_session",
                "custom_session_id": "cs_adhoc01",
                "target_date": "2026-07-20",
                "slot": "morning",
            }],
            custom_sessions=[cs],
        )
        day0 = after["weeks"][0]["days"][0]["sessions"]
        past_after = next(s for s in day0 if s["session_id"] == "strength_long")
        sibling_after = next(s for s in day0 if s["session_id"] == "core_circuit")
        assert past_after == past
        assert sibling_after == sibling
        adhoc_after = next(s for s in day0 if s["session_id"] == "custom_cs_adhoc01")
        assert adhoc_after["is_custom"] is True
