"""B389: the weekly report names the session that was skipped, not the stub.

``mark_skipped`` swaps the slot for a ``regeneration_easy`` recovery stub; the
report used to list every skip as "regeneration_easy" while the completion log
named the real session (the "SCL vs plan" mismatch of 29/09–12/10).
"""
from backend.engine.replanner_v1 import apply_events
from backend.engine.report_engine import _build_adherence

WEEK = "2026-10-05"


def _plan(sessions_by_date):
    return {"weeks": [{"days": [{"date": d, "sessions": ss} for d, ss in sessions_by_date.items()]}]}


def _stub(**extra):
    s = {"slot": "lunch", "session_id": "regeneration_easy", "status": "skipped",
         "explain": ["deterministic refill", "fill_kind=recovery"]}
    s.update(extra)
    return s


def test_stub_reports_skipped_session_id():
    plan = _plan({"2026-10-06": [_stub(skipped_session_id="pulling_strength_gym")]})
    adh = _build_adherence(plan, WEEK, [])
    assert adh["skipped_sessions"] == [{"date": "2026-10-06", "session_id": "pulling_strength_gym"}]


def test_stub_with_only_skipped_original():
    plan = _plan({"2026-10-06": [_stub(skipped_original={"session_id": "custom_cs_x", "slot": "lunch"})]})
    assert _build_adherence(plan, WEEK, [])["skipped_sessions"][0]["session_id"] == "custom_cs_x"


def test_legacy_stub_falls_back_to_completion_log():
    plan = _plan({"2026-10-07": [_stub()]})
    scl = [{"date": "2026-10-07", "status": "skipped", "session_id": "custom_cs_61a28d9a"},
           {"date": "2026-10-07", "status": "done", "session_id": "other"}]
    assert _build_adherence(plan, WEEK, scl)["skipped_sessions"][0]["session_id"] == "custom_cs_61a28d9a"


def test_legacy_stub_without_log_row_is_unknown_not_regeneration():
    plan = _plan({"2026-10-07": [_stub()]})
    scl = [{"date": "2026-10-07", "status": "skipped", "session_id": ""}]
    assert _build_adherence(plan, WEEK, scl)["skipped_sessions"][0]["session_id"] == ""


def test_log_row_already_named_by_a_stub_is_not_reused():
    plan = _plan({"2026-10-08": [_stub(skipped_session_id="a"), _stub(slot="evening")]})
    scl = [{"date": "2026-10-08", "status": "skipped", "session_id": "a"}]
    ids = [s["session_id"] for s in _build_adherence(plan, WEEK, scl)["skipped_sessions"]]
    assert ids == ["a", ""]


def test_real_skip_end_to_end():
    plan = _plan({"2026-10-06": [{"slot": "lunch", "session_id": "pulling_strength_gym",
                                  "tags": {"hard": True}}]})
    updated = apply_events(plan, [{"event_type": "mark_skipped", "date": "2026-10-06",
                                   "slot": "lunch"}])
    ids = [s["session_id"] for s in _build_adherence(updated, WEEK, [])["skipped_sessions"]]
    assert ids == ["pulling_strength_gym"]
