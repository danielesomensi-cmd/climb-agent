"""A252 — Adhoc: muscle-level focus + coach announces multi-session.

Fixes audit anomalies:
  A2 — requested muscles ignored: "chest+abs+triceps" produced squat/row
       (general_strength soup). The builder now constrains the main block to the
       requested body-parts (reusing the closed body_part_picker taxonomy) and
       round-robins across them, so each requested muscle is represented and no
       unrelated group is padded in.
  A1 — silent second-session drop: when the user asks for TWO sessions the coach
       builds ONE (the sooner) and the reply EXPLICITLY says so, inviting them to
       ask again — never implies both were created.

Invariants under test:
  1. body_parts drives selection; only requested-muscle work appears.
  2. Each requested part gets representation (round-robin).
  3. No body_parts → coarse-focus behaviour is unchanged.
  4. Composition stays deterministic in muscle mode.
  5. Invalid / unknown body-parts are filtered out.
  6. A part with no equipment-compatible work is skipped + noted honestly.
  7. build_adhoc_summary announces the single-session limit iff
     multi_session_requested is set.
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
from backend.coach.service import build_adhoc_summary
from backend.engine.adhoc_builder import ADHOC_BODY_PARTS, compose_adhoc_session
from backend.engine.body_part_picker import BODY_PART_ORDER, build_body_part_index

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


def _catalog_items() -> list:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else (raw.get("exercises") or list(raw.values()))


def _catalog() -> dict:
    return {ex["id"]: ex for ex in _catalog_items() if isinstance(ex, dict) and ex.get("id")}


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


WARMUP_IDS = {"general_pulse_raise", "dynamic_mobility_flow"}


def _mains(session: dict, catalog: dict) -> list:
    """Exercise ids that are not warmups (warmups are role-tagged)."""
    out = []
    for ex in session["exercises"]:
        eid = ex["exercise_id"]
        roles = catalog[eid].get("role") or []
        if isinstance(roles, str):
            roles = [roles]
        if eid in WARMUP_IDS or "warmup" in roles:
            continue
        out.append(eid)
    return out


# ── A2: muscle-level composition ────────────────────────────────────────


class TestMuscleFocus:
    def test_exports_match_taxonomy(self):
        assert tuple(ADHOC_BODY_PARTS) == tuple(BODY_PART_ORDER)

    def test_requested_muscles_only_no_unrelated_padding(self):
        cat, st = _catalog(), _state()
        idx = build_body_part_index(_catalog_items())
        allowed = idx["chest"] | idx["core"] | idx["triceps"]
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength",
             "body_parts": ["chest", "core", "triceps"], "minutes": 60, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        mains = _mains(s, cat)
        assert mains, "expected muscle work"
        # Every non-warmup pick belongs to a requested muscle.
        assert all(m in allowed for m in mains), mains
        # The A2 bug signature: NO squats / rows / generic legs-back soup.
        assert not any("squat" in m for m in mains), mains
        assert "barbell_row" not in mains

    def test_each_requested_part_represented(self):
        cat, st = _catalog(), _state()
        idx = build_body_part_index(_catalog_items())
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength",
             "body_parts": ["chest", "core"], "minutes": 60, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        mains = set(_mains(s, cat))
        assert mains & idx["chest"], "chest not represented"
        assert mains & idx["core"], "core not represented"

    def test_single_pattern_muscle_not_starved(self):
        # Every triceps move is pattern="push"; the coarse-focus MAX_PER_PATTERN
        # cap would starve this to 2. Muscle mode must give a fuller session.
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength",
             "body_parts": ["triceps"], "minutes": 60, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        assert len(_mains(s, cat)) >= 3

    def test_deterministic(self):
        cat, st = _catalog(), _state()
        intent = {"equipment_set": "gym", "focus": "general_strength",
                  "body_parts": ["chest", "triceps"], "minutes": 60, "energy": "medium"}
        a = compose_adhoc_session(intent, st, cat, today="2026-07-20")
        b = compose_adhoc_session(intent, st, cat, today="2026-07-20")
        assert [e["exercise_id"] for e in a["exercises"]] == [e["exercise_id"] for e in b["exercises"]]

    def test_invalid_body_parts_filtered(self):
        cat, st = _catalog(), _state()
        # Unknown ids dropped; a valid one still drives muscle mode.
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength",
             "body_parts": ["quads", "not_a_part", "core"], "minutes": 45, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        assert s["intent"]["body_parts"] == ["core"]

    def test_no_body_parts_keeps_coarse_behaviour(self):
        # Regression: focus-only path unchanged (still composes a session).
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength", "minutes": 60, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        assert s["exercises"]
        assert s["intent"]["body_parts"] == []
        assert "(gym)" in s["name"]

    def test_empty_part_skipped_and_noted(self):
        # Fingers needs a hangboard; a bodyweight-only user can't do them, so the
        # part is skipped and the explanation says so — never padded with others.
        cat = _catalog()
        st = {"equipment": {"home": [], "gyms": []},
              "macrocycle": _state()["macrocycle"], "recent_sessions": []}
        s = compose_adhoc_session(
            {"equipment_set": "home", "focus": "general_strength",
             "body_parts": ["fingers", "core"], "minutes": 45, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        assert "skipped" in s["explanation"].lower()

    def test_name_and_tags_reflect_muscles(self):
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "home", "focus": "general_strength",
             "body_parts": ["chest", "core"], "minutes": 45, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        assert "chest" in s["tags"] and "core" in s["tags"] and "home" in s["tags"]
        assert "Chest" in s["name"]


# ── A1: multi-session announcement (pure summary builder) ────────────────


class TestMultiSessionAnnouncement:
    def _session(self):
        return {"name": "Adhoc Chest (gym)", "estimated_duration_minutes": 40,
                "explanation": "A ~40-min Chest session for gym."}

    def test_single_session_no_announcement(self):
        summary = build_adhoc_summary(self._session(), {"multi_session_requested": False})
        assert "more than one session" not in summary
        assert "one at a time" not in summary

    def test_multi_session_announced_with_hint(self):
        summary = build_adhoc_summary(
            self._session(),
            {"multi_session_requested": True, "deferred_session_hint": "tonight at home: core and biceps"},
        )
        assert "more than one session" in summary
        assert "tonight at home: core and biceps" in summary
        assert "message me again" in summary.lower()

    def test_multi_session_announced_without_hint(self):
        summary = build_adhoc_summary(self._session(), {"multi_session_requested": True})
        assert "one at a time" in summary
        assert "message me again" in summary.lower()


# ── Endpoint: announcement flows through the composed reply ──────────────


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
    from backend.coach import llm_client
    monkeypatch.setattr(llm_client, "extract", lambda system_text, message, tool: slots)


class TestMultiSessionEndpoint:
    def test_multi_session_reply_announces_and_builds_one(self, isolate_state, monkeypatch):
        _mock_extract(monkeypatch, {
            "is_adhoc_request": True, "equipment_set": "gym",
            "body_parts": ["chest", "triceps"], "minutes": 45, "energy": "medium",
            "multi_session_requested": True,
            "deferred_session_hint": "tonight at home: core and biceps",
        })
        state = deps.load_state(None)
        state["equipment"] = _state()["equipment"]
        state["macrocycle"] = _state()["macrocycle"]
        deps.save_state(state, None)

        r = client.post("/api/coach/adhoc-session", json={
            "message": "build me a chest/triceps session at the gym for lunch, and one tonight at home for core/biceps",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["adhoc"] is True
        # ONE session built...
        assert data["session"]["exercises"]
        # ...and the reply is honest about the deferred one.
        assert "more than one session" in data["summary"]
        assert "core and biceps" in data["summary"]
