"""A239 (A-GAMIFY-02) — milestone system.

Covers: catalog integrity, lazy evaluation (session/exercise/outdoor/process
conditions), append-only + idempotency invariants, counters folding rules
(fully-past weeks only), dynamic grade-PB unlocks, and the API contract.
"""

from __future__ import annotations

import shutil
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine import milestones_v1
from backend.engine.milestones_v1 import (
    evaluate_milestones,
    load_milestones_catalog,
    mark_seen,
)

client = TestClient(app)

_TEST_USER_ID = "00000000-0000-4000-a000-000000000239"

TODAY = date(2026, 7, 20)  # a Monday
PAST_MONDAY = "2026-07-13"


@pytest.fixture(autouse=True)
def _cleanup_test_users():
    yield
    from backend.api.deps import USERS_DIR

    shutil.rmtree(USERS_DIR / _TEST_USER_ID, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_outdoor(monkeypatch):
    """Isolate from real outdoor logs; individual tests override."""
    monkeypatch.setattr(milestones_v1, "load_outdoor_sessions", lambda uid: [])


def _week(days):
    return {"weeks": [{"days": days}]}


def _done_session(session_id="strength_long", **extra):
    return {"session_id": session_id, "status": "done", **extra}


class TestCatalog:
    def test_ids_unique_and_fields(self):
        cat = load_milestones_catalog()
        assert len(cat) >= 20
        ids = [m["id"] for m in cat]
        assert len(ids) == len(set(ids))
        for m in cat:
            assert m["tier"] in ("activation", "medium", "career")
            assert m["category"] in ("session", "outdoor", "grade", "exercise", "process")
            assert m["icon"] and m["name"] and m["description"]

    def test_tier_distribution(self):
        """Design doc: deliberate difficulty spread (retention ∝ difficulty)."""
        cat = load_milestones_catalog()
        tiers = {t: sum(1 for m in cat if m["tier"] == t) for t in ("activation", "medium", "career")}
        assert all(v >= 4 for v in tiers.values()), tiers


class TestSessionConditions:
    def test_first_session_and_guided(self):
        state = {
            "week_plans": {
                PAST_MONDAY: _week([
                    {"date": "2026-07-13", "sessions": [_done_session(session_duration_seconds=3600)]},
                    {"date": "2026-07-14", "sessions": []},
                ])
            }
        }
        newly = evaluate_milestones(state, None, today=TODAY)
        ids = {n["id"] for n in newly}
        assert "first_session_done" in ids
        assert "first_guided_session" in ids

    def test_perfect_week_requires_all_done_and_rest(self):
        # One skipped session → no perfect week
        state = {
            "week_plans": {
                PAST_MONDAY: _week([
                    {"date": "2026-07-13", "sessions": [_done_session()]},
                    {"date": "2026-07-14", "sessions": [{"session_id": "x", "status": "skipped"}]},
                    {"date": "2026-07-15", "sessions": []},
                ])
            }
        }
        newly = evaluate_milestones(state, None, today=TODAY)
        assert "perfect_week" not in {n["id"] for n in newly}

        # All done + rest day → perfect week
        state2 = {
            "week_plans": {
                PAST_MONDAY: _week([
                    {"date": "2026-07-13", "sessions": [_done_session()]},
                    {"date": "2026-07-14", "sessions": [_done_session("endurance_arc")]},
                    {"date": "2026-07-15", "sessions": []},
                ])
            }
        }
        newly2 = evaluate_milestones(state2, None, today=TODAY)
        assert "perfect_week" in {n["id"] for n in newly2}

    def test_current_week_never_counts_as_perfect(self):
        state = {
            "week_plans": {
                "2026-07-20": _week([
                    {"date": "2026-07-20", "sessions": [_done_session()]},
                    {"date": "2026-07-21", "sessions": []},
                ])
            }
        }
        newly = evaluate_milestones(state, None, today=TODAY)
        assert "perfect_week" not in {n["id"] for n in newly}

    def test_test_session_unlock(self):
        state = {
            "week_plans": {
                PAST_MONDAY: _week([
                    {"date": "2026-07-13", "sessions": [_done_session("test_max_hang")]},
                ])
            }
        }
        newly = evaluate_milestones(state, None, today=TODAY)
        assert "first_test_done" in {n["id"] for n in newly}


class TestExerciseConditions:
    def _state_with_exercises(self, ids, monday=PAST_MONDAY):
        session = _done_session(
            actual_exercises=[{"exercise_id": i} for i in ids],
        )
        return {"week_plans": {monday: _week([{"date": monday, "sessions": [session]}])}}

    def test_family_unlocks(self):
        state = self._state_with_exercises(["max_hang_5s", "campus_laddering_feet_on", "tech_pogo"])
        ids = {n["id"] for n in evaluate_milestones(state, None, today=TODAY)}
        assert {"first_hangboard_session", "first_campus_session", "first_technique_drill"} <= ids

    def test_explorer_threshold(self):
        many = [f"fake_ex_{i}" for i in range(25)]
        state = self._state_with_exercises(many)
        ids = {n["id"] for n in evaluate_milestones(state, None, today=TODAY)}
        assert "explorer_25" in ids
        assert "explorer_50" not in ids

    def test_counters_fold_only_fully_past_weeks(self):
        past = self._state_with_exercises(["a", "b"], monday=PAST_MONDAY)
        current_session = _done_session(actual_exercises=[{"exercise_id": "c"}])
        past["week_plans"]["2026-07-20"] = _week(
            [{"date": "2026-07-20", "sessions": [current_session]}]
        )
        evaluate_milestones(past, None, today=TODAY)
        persisted = past["milestones"]["counters"]["exercise_ids"]
        assert "a" in persisted and "b" in persisted
        assert "c" not in persisted  # current week is transient

    def test_counters_survive_week_archiving(self):
        state = self._state_with_exercises([f"ex_{i}" for i in range(24)])
        evaluate_milestones(state, None, today=TODAY)
        # Week gets archived (removed from hot) — counters keep the ids
        state["week_plans"] = {}
        state["week_plans"]["2026-07-06"] = _week([
            {"date": "2026-07-06", "sessions": [_done_session(
                actual_exercises=[{"exercise_id": "ex_new"}])]},
        ])
        newly = evaluate_milestones(state, None, today=TODAY)
        assert "explorer_25" in {n["id"] for n in newly}


class TestOutdoorConditions:
    def test_outdoor_unlocks_and_grade_pbs(self, monkeypatch):
        sessions = [
            {"date": "2026-06-01", "spot_name": "Berdorf", "discipline": "lead",
             "routes": [
                 {"name": "r1", "grade": "7a", "style": "redpoint",
                  "attempts": [{"result": "sent"}]},
                 {"name": "r2", "grade": "6b", "style": "onsight",
                  "attempts": [{"result": "sent"}]},
                 {"name": "r3", "grade": "7c", "style": "project",
                  "attempts": [{"result": "fell"}]},  # not sent → no PB
             ]},
            {"date": "2026-06-08", "spot_name": "Freyr", "discipline": "lead", "routes": []},
            {"date": "2026-06-15", "spot_name": "Ettringen", "discipline": "lead", "routes": []},
        ]
        monkeypatch.setattr(milestones_v1, "load_outdoor_sessions", lambda uid: sessions)
        state: dict = {}
        newly = evaluate_milestones(state, "u", today=TODAY)
        ids = {n["id"] for n in newly}
        assert "first_outdoor_session" in ids
        assert "first_onsight_outdoor" in ids
        assert "crag_explorer_3" in ids
        assert "crag_explorer_5" not in ids
        assert "grade_first_redpoint:lead:7a" in ids
        assert "grade_first_onsight:lead:6b" in ids
        assert not any(i.endswith(":7c") for i in ids)

    def test_new_pb_unlocks_new_instance(self, monkeypatch):
        base = [{"date": "2026-06-01", "spot_name": "s", "discipline": "boulder",
                 "routes": [{"name": "p", "grade": "7A", "style": "redpoint",
                             "attempts": [{"result": "sent"}]}]}]
        monkeypatch.setattr(milestones_v1, "load_outdoor_sessions", lambda uid: base)
        state: dict = {}
        evaluate_milestones(state, "u", today=TODAY)
        base.append({"date": "2026-07-01", "spot_name": "s", "discipline": "boulder",
                     "routes": [{"name": "p2", "grade": "7B", "style": "redpoint",
                                 "attempts": [{"result": "sent"}]}]})
        newly = evaluate_milestones(state, "u", today=TODAY)
        assert "grade_first_redpoint:boulder:7B" in {n["id"] for n in newly}
        # Old PB entry still unlocked (append-only)
        all_ids = {u["id"] for u in state["milestones"]["unlocked"]}
        assert "grade_first_redpoint:boulder:7A" in all_ids


class TestProcessAndInvariants:
    def test_cycle_and_performance_from_history(self):
        state = {
            "macrocycle_history": [
                {"completion_summary": {"phases_completed": ["base", "performance"]}}
            ]
        }
        ids = {n["id"] for n in evaluate_milestones(state, None, today=TODAY)}
        assert "first_cycle_completed" in ids
        assert "reached_performance" in ids

    def test_append_only_never_revoked(self):
        state = {"free_sessions": [{"date": "2026-07-01", "finished_at": "x"}]}
        newly = evaluate_milestones(state, None, today=TODAY)
        assert "first_free_session" in {n["id"] for n in newly}
        # Data disappears → milestone stays, nothing new
        state["free_sessions"] = []
        newly2 = evaluate_milestones(state, None, today=TODAY)
        assert newly2 == []
        assert "first_free_session" in {u["id"] for u in state["milestones"]["unlocked"]}

    def test_idempotent_second_run(self):
        state = {"custom_sessions": [{"id": "cs1"}]}
        first = evaluate_milestones(state, None, today=TODAY)
        assert first
        assert evaluate_milestones(state, None, today=TODAY) == []

    def test_mark_seen(self):
        state = {"custom_sessions": [{"id": "cs1"}]}
        evaluate_milestones(state, None, today=TODAY)
        assert mark_seen(state, "first_custom_session") is True
        assert state["milestones"]["unlocked"][0]["seen"] is True
        assert mark_seen(state, "nonexistent") is False


class TestApi:
    def test_get_and_seen_flow(self):
        headers = {"X-User-ID": _TEST_USER_ID}
        r = client.get("/api/milestones", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["milestones"]) >= 20
        assert body["unlocked_count"] == 0
        locked = body["milestones"][0]
        assert locked["unlocked"] is False

        r2 = client.post("/api/milestones/first_session_done/seen", headers=headers)
        assert r2.status_code == 404  # not unlocked yet
