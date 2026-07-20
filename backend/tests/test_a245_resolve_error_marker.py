"""A245 E-3 (B17) — a failed resolution must be distinguishable from an empty one.

`_auto_resolve` swallowed every exception and set `resolved = None`. The client
then rendered a session card with no exercises, byte-identical to the legitimate
"no exercise matches your equipment" case — so a transient backend error looked
like a permanent content problem, and the user had nothing to retry.
"""

from backend.api.routers import week as week_router
from backend.api.routers import replanner as replanner_router


def _plan_with_one_session():
    return {
        "weeks": [
            {
                "days": [
                    {
                        "date": "2026-07-20",
                        "sessions": [
                            {"session_id": "strength_long", "location": "home", "status": "planned"}
                        ],
                    }
                ]
            }
        ]
    }


def _only_session(plan):
    return plan["weeks"][0]["days"][0]["sessions"][0]


class TestResolveErrorMarker:
    def test_week_marks_a_failed_resolution(self, monkeypatch):
        monkeypatch.setattr(
            week_router, "resolve_session",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("catalog exploded")),
        )
        plan = _plan_with_one_session()
        week_router._auto_resolve(plan, {}, user_id="u1")

        session = _only_session(plan)
        assert session["resolved"] is None
        assert session.get("resolve_error") is True

    def test_replanner_marks_a_failed_resolution(self, monkeypatch):
        monkeypatch.setattr(
            replanner_router, "resolve_session",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("catalog exploded")),
        )
        plan = _plan_with_one_session()
        replanner_router._auto_resolve(plan, {}, user_id="u1")

        session = _only_session(plan)
        assert session["resolved"] is None
        assert session.get("resolve_error") is True

    def test_a_successful_resolution_carries_no_marker(self, monkeypatch):
        monkeypatch.setattr(
            week_router, "resolve_session",
            lambda **kw: {"resolved_session": {"exercise_instances": [{"exercise_id": "pullup"}]}},
        )
        plan = _plan_with_one_session()
        week_router._auto_resolve(plan, {}, user_id="u1")

        assert "resolve_error" not in _only_session(plan)

    def test_a_stale_marker_is_cleared_once_resolution_succeeds(self, monkeypatch):
        """Otherwise the error state would outlive the error."""
        monkeypatch.setattr(
            week_router, "resolve_session",
            lambda **kw: {"resolved_session": {"exercise_instances": []}},
        )
        plan = _plan_with_one_session()
        _only_session(plan)["resolve_error"] = True

        week_router._auto_resolve(plan, {}, user_id="u1")

        assert "resolve_error" not in _only_session(plan)

    def test_an_empty_but_successful_resolution_is_not_an_error(self, monkeypatch):
        """The whole point: "no compatible exercise" is NOT a failure."""
        monkeypatch.setattr(
            week_router, "resolve_session",
            lambda **kw: {"resolved_session": {"exercise_instances": []}},
        )
        plan = _plan_with_one_session()
        week_router._auto_resolve(plan, {}, user_id="u1")

        session = _only_session(plan)
        assert session["resolved"] is not None
        assert "resolve_error" not in session
