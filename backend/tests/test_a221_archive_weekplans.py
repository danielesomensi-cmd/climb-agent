"""A221: lazy-archive past week_plans into a cold store.

Proof obligations (non-negotiable):
- Round-trip byte-identical: a week moved to the cold store reads back unchanged
  (completed sessions + feedback intact).
- Pure move + boundary: archive_past_weeks moves only weeks < hot_floor() (= N-1),
  keeps {N-1, N, future} hot, is idempotent, never regenerates.
- Safety: archive write is verified before the hot copy is pruned.
- Determinism: load_recent_exercise_ids returns a byte-identical list before/after
  archiving (recency window reconstructed from hot ∪ archive).
- Anti-regen / anti-resurrect: GET /api/week/{past} served from the archive never
  calls the planner and never writes the week back into hot.
- Fail-closed: a past week absent from BOTH hot and archive → past_week_unavailable.
- Reports + macrocycle completion count read the archive.
- Flag gating: the lazy load_state trigger is OFF by default.
- Hot-state size drops sharply once past weeks are archived.
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
from backend.engine import storage
from backend.engine import resolve_session
from backend.engine import report_engine
from backend.engine import macrocycle_archive

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

TEST_UID = "00000000-0000-4000-8000-0000000a221c"


@pytest.fixture(autouse=True)
def isolate_store(tmp_path, monkeypatch):
    """Redirect all file persistence (state + cold store) into tmp_path."""
    data_dir = tmp_path
    users_dir = tmp_path / "users"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir, raising=False)
    monkeypatch.setattr(storage, "USERS_DIR", users_dir, raising=False)
    monkeypatch.setattr(storage, "STATE_PATH", tmp_path / "user_state.json", raising=False)
    # lazy trigger OFF unless a test opts in
    monkeypatch.delenv("WEEKPLAN_ARCHIVE_LAZY", raising=False)
    yield


def _monday(weeks_offset: int) -> str:
    d = date.today() + timedelta(weeks=weeks_offset)
    return (d - timedelta(days=d.weekday())).isoformat()


def _make_week_plan(start_date: str, session_id: str = "strength_long",
                    status: str | None = None, exercise_id: str = "pullup_weighted",
                    feedback: str | None = None) -> dict:
    days = []
    start = date.fromisoformat(start_date)
    for i in range(7):
        day_iso = (start + timedelta(days=i)).isoformat()
        entry = {"date": day_iso,
                 "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][i],
                 "sessions": []}
        if i == 0:
            sess = {"session_id": session_id, "slot": "evening",
                    "resolved": {"resolved_session": {"exercise_instances": [
                        {"exercise_id": exercise_id}]}}}
            if status:
                sess["status"] = status
            if feedback:
                sess["feedback_summary"] = feedback
            entry["sessions"].append(sess)
        days.append(entry)
    return {"start_date": start_date, "weeks": [{"phase": "base", "days": days}]}


def _load_fixture_state() -> dict:
    state = json.loads(REAL_STATE_PATH.read_text(encoding="utf-8"))
    return state


# ── A. storage layer round-trip ─────────────────────────────────────────────

class TestColdStoreRoundTrip:
    def test_archive_read_byte_identical(self):
        plan = _make_week_plan(_monday(-4), status="done", feedback="hard")
        storage.archive_week(TEST_UID, _monday(-4), plan)
        back = storage.read_archived_week(TEST_UID, _monday(-4))
        assert back == plan  # JSONB/JSON round-trip preserves everything

    def test_read_missing_returns_none(self):
        assert storage.read_archived_week(TEST_UID, _monday(-9)) is None

    def test_list_keys_sorted(self):
        for off in (-2, -5, -3):
            storage.archive_week(TEST_UID, _monday(off), _make_week_plan(_monday(off)))
        keys = storage.list_archived_keys(TEST_UID)
        assert keys == sorted(keys)
        assert set(keys) == {_monday(-2), _monday(-3), _monday(-5)}

    def test_range_filter(self):
        for off in (-2, -5, -3):
            storage.archive_week(TEST_UID, _monday(off), _make_week_plan(_monday(off)))
        got = storage.read_archived_weeks_in_range(TEST_UID, _monday(-3), _monday(-2))
        assert set(got.keys()) == {_monday(-2), _monday(-3)}

    def test_delete(self):
        storage.archive_week(TEST_UID, _monday(-2), _make_week_plan(_monday(-2)))
        assert storage.delete_archived_week(TEST_UID, _monday(-2)) is True
        assert storage.read_archived_week(TEST_UID, _monday(-2)) is None

    def test_delete_all(self):
        for off in (-2, -3):
            storage.archive_week(TEST_UID, _monday(off), _make_week_plan(_monday(off)))
        assert storage.delete_all_archived(TEST_UID) == 2
        assert storage.list_archived_keys(TEST_UID) == []


# ── B. archive_past_weeks: boundary, purity, idempotency, safety ────────────

class TestArchivePastWeeks:
    def _hot(self):
        # N-3, N-2, N-1, N, N+1 — done sessions on the past ones
        return {
            _monday(-3): _make_week_plan(_monday(-3), status="done", feedback="a"),
            _monday(-2): _make_week_plan(_monday(-2), status="done", feedback="b"),
            _monday(-1): _make_week_plan(_monday(-1), status="done", feedback="c"),
            _monday(0): _make_week_plan(_monday(0)),
            _monday(1): _make_week_plan(_monday(1)),
        }

    def test_boundary_keeps_n_minus_1_and_newer(self):
        state = {"week_plans": deepcopy(self._hot())}
        moved = deps.archive_past_weeks(state, TEST_UID)
        assert moved == 2  # N-3, N-2 archived
        assert set(state["week_plans"].keys()) == {_monday(-1), _monday(0), _monday(1)}
        assert set(storage.list_archived_keys(TEST_UID)) == {_monday(-3), _monday(-2)}

    def test_move_is_byte_identical(self):
        hot = self._hot()
        state = {"week_plans": deepcopy(hot)}
        deps.archive_past_weeks(state, TEST_UID)
        assert storage.read_archived_week(TEST_UID, _monday(-2)) == hot[_monday(-2)]
        assert storage.read_archived_week(TEST_UID, _monday(-3)) == hot[_monday(-3)]

    def test_idempotent(self):
        state = {"week_plans": deepcopy(self._hot())}
        deps.archive_past_weeks(state, TEST_UID)
        moved2 = deps.archive_past_weeks(state, TEST_UID)
        assert moved2 == 0
        assert set(state["week_plans"].keys()) == {_monday(-1), _monday(0), _monday(1)}

    def test_verify_before_prune_keeps_hot_on_write_failure(self, monkeypatch):
        """If the archive write/verify fails, the hot copy must NOT be pruned."""
        state = {"week_plans": deepcopy(self._hot())}

        def _boom(*a, **k):
            raise OSError("archive store down")

        monkeypatch.setattr(storage, "archive_week", _boom)
        moved = deps.archive_past_weeks(state, TEST_UID)
        assert moved == 0
        # nothing lost — past weeks still in hot
        assert _monday(-2) in state["week_plans"]
        assert _monday(-3) in state["week_plans"]

    def test_verify_failure_keeps_hot(self, monkeypatch):
        """Write 'succeeds' but read-back returns None → keep hot, skip prune."""
        state = {"week_plans": deepcopy(self._hot())}
        monkeypatch.setattr(storage, "archive_week", lambda *a, **k: None)
        monkeypatch.setattr(storage, "read_archived_week", lambda *a, **k: None)
        moved = deps.archive_past_weeks(state, TEST_UID)
        assert moved == 0
        assert _monday(-2) in state["week_plans"]


# ── C. hot_floor canonical boundary ─────────────────────────────────────────

class TestHotFloor:
    def test_hot_floor_is_previous_monday(self):
        assert deps.hot_floor() == _monday(-1)

    def test_lazy_flag_off_by_default(self):
        assert deps._lazy_archive_enabled() is False

    def test_lazy_flag_parses_truthy(self, monkeypatch):
        for v in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("WEEKPLAN_ARCHIVE_LAZY", v)
            assert deps._lazy_archive_enabled() is True
        monkeypatch.setenv("WEEKPLAN_ARCHIVE_LAZY", "false")
        assert deps._lazy_archive_enabled() is False


# ── D. determinism: recency identical before/after archiving ────────────────

class TestRecencyDeterminism:
    def test_recency_identical_after_archive(self):
        hot = {
            _monday(-2): _make_week_plan(_monday(-2), status="done", exercise_id="ex_a"),
            _monday(-1): _make_week_plan(_monday(-1), status="done", exercise_id="ex_b"),
            _monday(0): _make_week_plan(_monday(0), status="done", exercise_id="ex_c"),
        }
        before = resolve_session.load_recent_exercise_ids(
            TEST_UID, user_state={"week_plans": deepcopy(hot)}
        )
        # archive moves N-2 to the cold store
        state = {"week_plans": deepcopy(hot)}
        deps.archive_past_weeks(state, TEST_UID)
        assert _monday(-2) not in state["week_plans"]  # confirm it really moved
        after = resolve_session.load_recent_exercise_ids(TEST_UID, user_state=state)
        assert after == before
        assert after == ["ex_a", "ex_b", "ex_c"]  # oldest → newest preserved


# ── E. report reads the archive for a past week ─────────────────────────────

class TestReportReadsArchive:
    def test_adherence_identical_after_archive(self):
        past_key = _monday(-2)
        past = _make_week_plan(past_key, status="done", feedback="hard")
        state = {
            "week_plans": {past_key: deepcopy(past), _monday(0): _make_week_plan(_monday(0))},
            "session_completion_log": [],
            "feedback_log": [],
        }
        rep_before = report_engine.generate_weekly_report(deepcopy(state), TEST_UID, past_key)
        # archive the past week
        deps.archive_past_weeks(state, TEST_UID)
        assert past_key not in state["week_plans"]
        rep_after = report_engine.generate_weekly_report(state, TEST_UID, past_key)
        assert rep_after["adherence"] == rep_before["adherence"]
        # the done session is still reflected (not an empty week)
        assert rep_after["adherence"]["completed"] >= 1


# ── F. macrocycle completion count merges the archive ───────────────────────

class TestPlannedCountMergesArchive:
    def test_count_identical_after_archive(self):
        mc = {"start_date": _monday(-3), "end_date": _monday(1)}
        hot = {
            _monday(-3): _make_week_plan(_monday(-3), status="done"),
            _monday(-2): _make_week_plan(_monday(-2), status="done"),
            _monday(-1): _make_week_plan(_monday(-1), status="done"),
            _monday(0): _make_week_plan(_monday(0)),
        }
        state = {"week_plans": deepcopy(hot)}
        before = macrocycle_archive._planned_session_count(mc, state, TEST_UID)
        deps.archive_past_weeks(state, TEST_UID)
        after = macrocycle_archive._planned_session_count(mc, state, TEST_UID)
        assert after == before
        assert after == 4  # one session per week × 4 weeks in window


# ── G. API: anti-regen, anti-resurrect, fail-closed ─────────────────────────

class TestApiServeFromArchive:
    def _seed_state(self, *, hot_week_plans: dict, archived: dict):
        """Seed Daniele's fixture state under TEST_UID with a -3w macrocycle."""
        state = _load_fixture_state()
        state["week_plans"] = {k: deepcopy(v) for k, v in hot_week_plans.items()}
        state["current_week_plan"] = None
        state["macrocycle"]["start_date"] = _monday(-3)
        phases = state["macrocycle"].get("phases") or []
        phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), 6)
        storage.write_state(state, TEST_UID)
        for key, plan in archived.items():
            storage.archive_week(TEST_UID, key, plan)

    def test_past_week_served_from_archive(self):
        past_key = _monday(-3)
        past = _make_week_plan(past_key, status="done", feedback="hard")
        self._seed_state(
            hot_week_plans={_monday(0): _make_week_plan(_monday(0))},
            archived={past_key: past},
        )
        r = client.get("/api/week/1", headers={"X-User-ID": TEST_UID})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("past_week_unavailable") is not True
        sess = body["week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert sess["status"] == "done"
        assert sess["feedback_summary"] == "hard"

    def test_serving_from_archive_does_not_resurrect_into_hot(self):
        past_key = _monday(-3)
        self._seed_state(
            hot_week_plans={_monday(0): _make_week_plan(_monday(0))},
            archived={past_key: _make_week_plan(past_key, status="done")},
        )
        client.get("/api/week/1", headers={"X-User-ID": TEST_UID})
        state = storage.read_state(TEST_UID)
        assert past_key not in (state.get("week_plans") or {}), \
            "archived week must not be written back into hot state"

    def test_archive_serve_never_calls_planner(self, monkeypatch):
        """generate_phase_week must never run for a past week served from archive."""
        from backend.api.routers import week as week_router

        def _boom(*a, **k):
            raise AssertionError("planner must not run for an archived past week")

        monkeypatch.setattr(week_router, "generate_phase_week", _boom)
        past_key = _monday(-3)
        self._seed_state(
            hot_week_plans={_monday(0): _make_week_plan(_monday(0))},
            archived={past_key: _make_week_plan(past_key, status="done")},
        )
        r = client.get("/api/week/1", headers={"X-User-ID": TEST_UID})
        assert r.status_code == 200, r.text
        assert r.json()["week_plan"] is not None

    def test_fail_closed_when_absent_from_hot_and_archive(self):
        self._seed_state(
            hot_week_plans={_monday(0): _make_week_plan(_monday(0))},
            archived={},  # nothing archived
        )
        r = client.get("/api/week/1", headers={"X-User-ID": TEST_UID})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["week_plan"] is None
        assert body["past_week_unavailable"] is True


# ── H. lazy trigger gating via load_state ───────────────────────────────────

class TestLazyTriggerGating:
    def _seed_with_past(self):
        state = _load_fixture_state()
        state["week_plans"] = {
            _monday(-3): _make_week_plan(_monday(-3), status="done"),
            _monday(0): _make_week_plan(_monday(0)),
        }
        storage.write_state(state, TEST_UID)

    def test_flag_off_does_not_archive(self):
        self._seed_with_past()
        deps.load_state(TEST_UID)
        state = storage.read_state(TEST_UID)
        assert _monday(-3) in (state.get("week_plans") or {}), \
            "with the flag OFF, load_state must not archive"
        assert storage.list_archived_keys(TEST_UID) == []

    def test_flag_on_archives_past_weeks(self, monkeypatch):
        self._seed_with_past()
        monkeypatch.setenv("WEEKPLAN_ARCHIVE_LAZY", "true")
        deps.load_state(TEST_UID)
        state = storage.read_state(TEST_UID)
        assert _monday(-3) not in (state.get("week_plans") or {})
        assert _monday(-3) in storage.list_archived_keys(TEST_UID)
        # hot keeps current
        assert _monday(0) in state["week_plans"]


# ── I. hot-state size reduction on a synthetic 18-week fixture ───────────────

class TestHotSizeReduction:
    def test_hot_state_shrinks(self):
        hot = {}
        # 16 past weeks + N-1 + N (18 weeks). Past weeks are "heavy" (resolved).
        for off in range(-17, 1):
            heavy = _make_week_plan(_monday(off), status="done", feedback="x" * 200)
            # bulk up resolved payload to mimic a real resolved week
            heavy["weeks"][0]["days"][0]["sessions"][0]["resolved"]["resolved_session"][
                "exercise_instances"
            ] = [{"exercise_id": f"ex_{i}", "notes": "n" * 100} for i in range(20)]
            hot[_monday(off)] = heavy
        state = {"week_plans": deepcopy(hot)}
        size_before = len(json.dumps(state["week_plans"]))
        deps.archive_past_weeks(state, TEST_UID)
        size_after = len(json.dumps(state["week_plans"]))
        # only {N-1, N} remain hot → expect a large reduction
        assert set(state["week_plans"].keys()) == {_monday(-1), _monday(0)}
        reduction = 1 - size_after / size_before
        assert reduction > 0.70, f"expected >70% hot reduction, got {reduction:.0%}"
