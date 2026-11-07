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
                    # B413 (D2): at "done" the server freezes the prescription
                    # GET showed. GET re-resolves a planned session, so a stub
                    # ``resolved`` is what it shows only on a session the user
                    # edited (B153b) — which keeps this stub the prescription.
                    "_user_edited": True,
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


class TestB312WithTheB413Freeze:
    """B413 (D2) × B312 on an ordinary planned session (not user-edited): the
    freeze replaces the stored stub ``resolved`` with the prescription GET
    shows, written at step 7b. B414 (B312-LOAD-ACTUAL-VS-FROZEN): step 4b now
    scores ``session_load_actual`` against that same frozen prescription
    (computed at step 1), no longer against the stored copy — which a pending
    engine session does not even have in production (no ``resolved`` stored),
    so the guided player's sessions never got an actual load at all."""

    def _seed_planned(self, *, drop_resolved: bool = False) -> None:
        wp = _week_plan()
        sess = wp["weeks"][0]["days"][0]["sessions"][0]
        sess.pop("_user_edited")
        if drop_resolved:
            sess.pop("resolved")
        state = deps.load_state(None)
        state["current_week_plan"] = deepcopy(wp)
        state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
        state["session_completion_log"] = []
        deps.save_state(state, None)

    def _frozen_ids(self, *, drop_resolved: bool = False) -> list:
        """The exercise ids of the frozen prescription (a full-completion run
        on a fresh seed — the resolver is deterministic)."""
        self._seed_planned(drop_resolved=drop_resolved)
        slot = _slot(_post([True, True, True]))
        return [i["exercise_id"] for i in slot["resolved"]["resolved_session"]["exercise_instances"]]

    def _post_items(self, items: list) -> dict:
        r = client.post("/api/feedback", json={
            "log_entry": {"date": DATE, "session_id": SESSION_ID,
                          "actual": {"exercise_feedback_v1": items}},
            "status": "done",
        })
        assert r.status_code == 200, r.text
        return deps.load_state(None)

    def test_actual_and_score_from_the_frozen_view(self):
        self._seed_planned()
        slot = _slot(_post([True, True, True]))
        frozen = slot["resolved"]
        insts = frozen["resolved_session"]["exercise_instances"]
        # Step 7b: the record is the server view, not the stub …
        assert [i["exercise_id"] for i in insts] != EXERCISES
        assert frozen["session_load_score"] != PRESCRIBED
        # … and step 4b scored the earned load on that same view: full
        # completion (the stub's ids are not in it → unreported → done).
        assert slot["session_load_actual"] == frozen["session_load_score"]

    def test_prod_shape_without_stored_resolved_records_a_lower_actual(self):
        """The production shape: a pending engine session stored WITHOUT
        ``resolved``. Before B414 step 4b had nothing to score against and
        wrote no ``session_load_actual``."""
        ids = self._frozen_ids(drop_resolved=True)
        assert len(ids) >= 2
        self._seed_planned(drop_resolved=True)
        # Only the first frozen exercise done, every other one skipped.
        items = [{"exercise_id": ex, "feedback_label": "ok", "completed": i == 0}
                 for i, ex in enumerate(ids)]
        slot = _slot(self._post_items(items))
        assert "session_load_actual" in slot
        assert slot["session_load_actual"] < slot["resolved"]["session_load_score"]
        # Both plan copies agree (GET reads the cache).
        state = deps.load_state(None)
        assert _slot(state, "week_plans")["session_load_actual"] == slot["session_load_actual"]
        # The weekly report reads the new value (effective_session_load).
        report = _build_load(state["current_week_plan"], [], [], [], DATE)
        assert report["actual_total"] == slot["session_load_actual"]

    def test_prod_shape_full_completion_equals_the_frozen_score(self):
        ids = self._frozen_ids(drop_resolved=True)
        self._seed_planned(drop_resolved=True)
        items = [{"exercise_id": ex, "feedback_label": "ok", "completed": True} for ex in ids]
        slot = _slot(self._post_items(items))
        assert slot["session_load_actual"] == slot["resolved"]["session_load_score"]

    def test_today_flow_mark_done_then_feedback_uses_the_stored_freeze(self):
        """/today: mark_done through /events first (it writes the frozen
        ``resolved``), then the dialog posts /feedback — the session is
        already done, nothing is frozen again and step 4b reads the stored
        freeze, exactly as before."""
        self._seed_planned(drop_resolved=True)
        state = deps.load_state(None)
        r = client.post("/api/replanner/events", json={
            "week_plan": state["current_week_plan"],
            "events": [{"event_type": "mark_done", "date": DATE, "session_ref": SESSION_ID}],
        })
        assert r.status_code == 200, r.text
        # /events saves the week cache (current_week_plan only for the
        # calendar's current week) — the copy GET and /feedback's B216 read.
        stored = _slot(deps.load_state(None), "week_plans")
        assert stored["status"] == "done"
        ids = [i["exercise_id"] for i in stored["resolved"]["resolved_session"]["exercise_instances"]]
        items = [{"exercise_id": ex, "feedback_label": "ok", "completed": i == 0}
                 for i, ex in enumerate(ids)]
        slot = _slot(self._post_items(items), "week_plans")
        assert slot["resolved"] == stored["resolved"], "the freeze of /events is kept"
        assert slot["session_load_actual"] < slot["resolved"]["session_load_score"]

    def test_b216_rollover_scores_against_the_alt_plan_freeze(self):
        """B216: current_week_plan is the previous week, the session lives in
        week_plans[monday]. The retry freezes on the alt plan; step 4b scores
        against that freeze."""
        ids = self._frozen_ids(drop_resolved=True)
        wp = _week_plan()
        wp["weeks"][0]["days"][0]["sessions"][0].pop("_user_edited")
        wp["weeks"][0]["days"][0]["sessions"][0].pop("resolved")
        prev = deepcopy(wp)
        prev["start_date"] = "2026-03-09"
        prev["weeks"][0]["days"][0]["date"] = "2026-03-09"
        state = deps.load_state(None)
        state["current_week_plan"] = deepcopy(prev)
        state["week_plans"] = {"2026-03-09": deepcopy(prev), DATE: deepcopy(wp)}
        state["session_completion_log"] = []
        deps.save_state(state, None)
        items = [{"exercise_id": ex, "feedback_label": "ok", "completed": i == 0}
                 for i, ex in enumerate(ids)]
        state = self._post_items(items)
        slot = _slot(state, "week_plans")
        assert slot["status"] == "done"
        assert slot["session_load_actual"] < slot["resolved"]["session_load_score"]
        # The previous week is untouched.
        assert state["week_plans"]["2026-03-09"]["weeks"][0]["days"][0]["sessions"][0].get("status") != "done"

    def test_an_already_played_session_stays_byte_identical(self):
        """Immutability: the feedback writes the actual load on the session
        it marks done, never on another played session of the week (no
        recomputation of the past)."""
        wp = _week_plan()
        sess = wp["weeks"][0]["days"][0]["sessions"][0]
        sess.pop("_user_edited")
        sess.pop("resolved")
        played = {
            "session_id": "power_contact_gym", "slot": "evening", "status": "done",
            "actual_exercises": [{"exercise_id": "max_hang_7s", "completed": False}],
            "resolved": {"session_load_score": 40, "resolved_session": {
                "exercise_instances": [{"exercise_id": "max_hang_7s"}, {"exercise_id": "weighted_pullup"}]}},
            "session_duration_seconds": 3600,
        }
        wp["weeks"][0]["days"].append({"date": "2026-03-17", "weekday": "tue", "sessions": [played]})
        state = deps.load_state(None)
        state["current_week_plan"] = deepcopy(wp)
        state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
        state["session_completion_log"] = []
        deps.save_state(state, None)
        before = json.dumps(played, sort_keys=True)
        state = self._post_items([{"exercise_id": "max_hang_7s", "feedback_label": "ok", "completed": False}])
        for plan in (state["current_week_plan"], state["week_plans"][DATE]):
            assert json.dumps(plan["weeks"][0]["days"][1]["sessions"][0], sort_keys=True) == before
