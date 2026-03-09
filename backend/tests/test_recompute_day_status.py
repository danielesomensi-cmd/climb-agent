"""Tests for _recompute_day_status considering outdoor and other_activity."""

from backend.engine.replanner_v1 import _recompute_day_status


def _day(sessions=None, **kwargs):
    d = {"date": "2026-03-09", "sessions": sessions or []}
    d.update(kwargs)
    return d


def _session(status=None):
    s = {"session_id": "strength_long", "slot": "evening", "intensity": "medium"}
    if status:
        s["status"] = status
    return s


class TestRecomputeDayStatus:

    def test_all_sessions_done(self):
        day = _day([_session("done"), _session("done")])
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_all_sessions_skipped(self):
        day = _day([_session("skipped")])
        _recompute_day_status(day)
        assert day["status"] == "skipped"

    def test_mixed_done_skipped(self):
        day = _day([_session("done"), _session("skipped")])
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_no_sessions_no_status(self):
        day = _day()
        day["status"] = "done"
        _recompute_day_status(day)
        assert "status" not in day

    def test_planned_session_clears_status(self):
        day = _day([_session()])
        day["status"] = "done"
        _recompute_day_status(day)
        assert "status" not in day

    # --- outdoor_session_status ---

    def test_outdoor_done_no_sessions(self):
        """Outdoor done with no indoor sessions → day done."""
        day = _day(outdoor_session_status="done")
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_outdoor_done_indoor_skipped(self):
        """Outdoor done + indoor skipped → day done."""
        day = _day([_session("skipped")], outdoor_session_status="done")
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_outdoor_done_indoor_planned(self):
        """Outdoor done + indoor planned → no status (planned not finalized)."""
        day = _day([_session()], outdoor_session_status="done")
        _recompute_day_status(day)
        assert "status" not in day

    def test_outdoor_planned_no_effect(self):
        """outdoor_session_status=planned doesn't count as done."""
        day = _day(outdoor_session_status="planned")
        _recompute_day_status(day)
        assert "status" not in day

    # --- other_activity_status ---

    def test_other_activity_completed_no_sessions(self):
        """Other activity completed with no sessions → day done."""
        day = _day(other_activity=True, other_activity_status="completed")
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_other_activity_done_no_sessions(self):
        """other_activity_status='done' also counts."""
        day = _day(other_activity=True, other_activity_status="done")
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_other_activity_completed_indoor_skipped(self):
        """Other activity completed + indoor skipped → day done (Christie 03-04 case)."""
        day = _day([_session("skipped")], other_activity=True, other_activity_status="completed")
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_other_activity_completed_indoor_planned(self):
        """Other activity completed + indoor planned → no status."""
        day = _day([_session()], other_activity=True, other_activity_status="completed")
        _recompute_day_status(day)
        assert "status" not in day

    # --- combined outdoor + other_activity ---

    def test_outdoor_done_and_other_done_no_sessions(self):
        """Both outdoor and other_activity done → day done."""
        day = _day(outdoor_session_status="done", other_activity=True, other_activity_status="completed")
        _recompute_day_status(day)
        assert day["status"] == "done"

    def test_outdoor_done_other_done_indoor_skipped(self):
        """All three: outdoor done + other done + indoor skipped → day done."""
        day = _day(
            [_session("skipped")],
            outdoor_session_status="done",
            other_activity=True,
            other_activity_status="completed",
        )
        _recompute_day_status(day)
        assert day["status"] == "done"
