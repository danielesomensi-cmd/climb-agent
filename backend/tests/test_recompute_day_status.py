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

    # --- blocking: outdoor/other_activity not done blocks day status ---

    def test_outdoor_planned_blocks_indoor_done(self):
        """Indoor done + outdoor planned → day NOT done (outdoor blocks)."""
        day = _day([_session("done")], outdoor_session_status="planned")
        _recompute_day_status(day)
        assert "status" not in day

    def test_other_activity_pending_blocks_indoor_done(self):
        """Indoor done + other_activity present but not completed → day NOT done."""
        day = _day([_session("done")], other_activity=True)
        _recompute_day_status(day)
        assert "status" not in day

    def test_other_activity_done_indoor_planned_stays_planned(self):
        """other_activity done + indoor planned → day NOT done (indoor blocks)."""
        day = _day([_session()], other_activity=True, other_activity_status="done")
        _recompute_day_status(day)
        assert "status" not in day

    def test_outdoor_planned_other_done_indoor_done(self):
        """Indoor done + other done + outdoor planned → NOT done (outdoor blocks)."""
        day = _day(
            [_session("done")],
            outdoor_session_status="planned",
            other_activity=True,
            other_activity_status="completed",
        )
        _recompute_day_status(day)
        assert "status" not in day


class TestApplyEventsRecomputesStatus:
    """Verify apply_events delegates to _recompute_day_status instead of hardcoding."""

    def _make_plan(self, sessions=None, **day_extra):
        day = {
            "date": "2026-03-09",
            "weekday": "mon",
            "sessions": sessions or [],
        }
        day.update(day_extra)
        return {
            "start_date": "2026-03-09",
            "plan_revision": 1,
            "weeks": [{"days": [
                day,
                {"date": "2026-03-10", "weekday": "tue", "sessions": []},
                {"date": "2026-03-11", "weekday": "wed", "sessions": []},
                {"date": "2026-03-12", "weekday": "thu", "sessions": []},
                {"date": "2026-03-13", "weekday": "fri", "sessions": []},
                {"date": "2026-03-14", "weekday": "sat", "sessions": []},
                {"date": "2026-03-15", "weekday": "sun", "sessions": []},
            ]}],
        }

    def test_complete_other_activity_indoor_planned_not_done(self):
        """Bug repro: complete_other_activity with indoor planned → day NOT done."""
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_plan(
            [_session()],  # indoor planned (no status)
            other_activity=True,
            other_activity_name="Yoga",
        )
        result = apply_events(plan, [
            {"event_type": "complete_other_activity", "date": "2026-03-09"},
        ])
        day = result["weeks"][0]["days"][0]
        assert day["other_activity_status"] == "completed"
        assert "status" not in day, "Day should NOT be 'done' while indoor session is planned"

    def test_complete_outdoor_indoor_planned_not_done(self):
        """complete_outdoor with indoor planned → day NOT done."""
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_plan(
            [_session()],  # indoor planned
            outdoor_spot_name="Berdorf",
            outdoor_discipline="lead",
            outdoor_session_status="planned",
        )
        result = apply_events(plan, [
            {"event_type": "complete_outdoor", "date": "2026-03-09"},
        ])
        day = result["weeks"][0]["days"][0]
        assert day["outdoor_session_status"] == "done"
        assert "status" not in day, "Day should NOT be 'done' while indoor session is planned"

    def test_mark_done_other_activity_pending_not_done(self):
        """mark_done indoor but other_activity still pending → day NOT done."""
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_plan(
            [_session()],
            other_activity=True,
            other_activity_name="Yoga",
        )
        result = apply_events(plan, [
            {"event_type": "mark_done", "date": "2026-03-09", "slot": "evening"},
        ])
        day = result["weeks"][0]["days"][0]
        assert day["sessions"][0]["status"] == "done"
        assert "status" not in day, "Day should NOT be 'done' while other_activity is pending"

    def test_all_done_then_day_done(self):
        """Indoor done + other_activity done → day IS done."""
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_plan(
            [_session()],
            other_activity=True,
            other_activity_name="Yoga",
        )
        result = apply_events(plan, [
            {"event_type": "mark_done", "date": "2026-03-09", "slot": "evening"},
            {"event_type": "complete_other_activity", "date": "2026-03-09"},
        ])
        day = result["weeks"][0]["days"][0]
        assert day["status"] == "done"
