"""A299 — the three residues of A296 (R6c) closed.

1. Weekly report: hardest boulder SENT per surface (``limit_sends``), from the
   limit log (planned / custom / adhoc problems) and the free boulder sessions,
   never counting a free session twice.
2. (frontend) the post-session dialog logs the grade and the problems through
   the same payload builder as the guided player — covered by vitest; the
   server side is the A296 /api/feedback path, pinned here once more for a
   dialog-shaped item.
3. Grade targets: computed at read, never stored. The week read now attaches
   the limit target to not-yet-played custom / adhoc rows (same function as
   GET custom ?date=), so every player recomputes it; a preview computed for
   day D carries the same target the player reads on D, and the coach preview
   says which day that is (``resolved_for_date``).
"""

from __future__ import annotations

from copy import deepcopy

from backend.api.routers.custom_session import attach_limit_targets
from backend.api.routers.week import _with_custom_anchored_loads
from backend.coach import service
from backend.coach.session_composer import _decorate_engine_fields
from backend.engine import limit_log
from backend.engine.adaptive_replan import load_exercises_by_id
from backend.engine.adhoc_builder import _to_custom_exercise
from backend.engine.progression_v1 import apply_feedback, limit_grade_target
from backend.engine.report_engine import generate_weekly_report

from backend.tests.test_a296_limit_log import P, _fresh_kilter_state

WEEK = "2026-10-05"  # a Monday
DAY = "2026-10-07"


def _entry(date, surface, problems, *, source="planned", target="7A", session_id="limit_boulder_gym"):
    return {"date": date, "session_id": session_id, "exercise_id": "limit_bouldering",
            "surface": surface, "target_grade": target, "problems": problems, "source": source}


def _free(date, surface, climbs, *, finished=True, fid="fs_1"):
    return {"id": fid, "date": date, "surface": surface, "climbs": climbs,
            **({"finished_at": f"{date}T20:00:00"} if finished else {})}


# ─── 1. limit_sends ──────────────────────────────────────────────────────


def test_sends_by_surface_reads_the_log_and_the_free_sessions_once():
    state = {"limit_log": [
        _entry("2026-10-05", "board_kilter", [P("7A", "sent"), P("7A+", "high_point"), P("6C+", "sent")]),
        _entry("2026-10-08", "board_kilter", [P("7A+", "sent")], target="7A+", session_id="custom_cs1",
               source="custom"),
        # A free entry is a copy of the free session's climbs: never read.
        _entry("2026-10-09", "gym_boulder", [P("8A", "sent")], source="free", session_id="fs_1"),
        # Outside the week.
        _entry("2026-10-04", "board_kilter", [P("7C", "sent")]),
        _entry("2026-10-12", "board_kilter", [P("7C", "sent")]),
    ]}
    free = [
        _free("2026-10-09", "gym_boulder", [
            {"grade": "7A", "status": "sent"}, {"grade": "7B", "status": "flash"},
            {"grade": "7C", "status": "attempted"},
        ]),
        _free("2026-10-10", "gym_boulder", [{"grade": "8A", "status": "sent"}], finished=False, fid="fs_2"),
        _free("2026-10-10", "gym_routes", [{"grade": "7b", "status": "sent"}], fid="fs_3"),
    ]
    rows = limit_log.sends_by_surface(state, free, "2026-10-05", "2026-10-11")
    assert rows == [
        {"surface": "board_kilter", "max_grade_sent": "7A+", "sends": 3,
         "sources": ["custom", "planned"], "target_grade": "7A+"},
        {"surface": "gym_boulder", "max_grade_sent": "7B", "sends": 2,
         "sources": ["free"], "target_grade": None},
    ]


def test_problem_surface_wins_and_a_week_without_sends_has_no_row():
    state = {"limit_log": [
        _entry("2026-10-06", "board_kilter", [P("7A", "sent", surface="board_moonboard"),
                                              P("7B", "no_progress")]),
        _entry("2026-10-07", "spraywall", [P("6C", "high_point")]),
    ]}
    rows = limit_log.sends_by_surface(state, [], "2026-10-05", "2026-10-11")
    assert [(r["surface"], r["max_grade_sent"]) for r in rows] == [("board_moonboard", "7A")]
    # The target belongs to the entry's surface, not the problem's.
    assert rows[0]["target_grade"] is None
    assert limit_log.sends_by_surface({}, [], "2026-10-05", "2026-10-11") == []


def test_target_is_the_last_logged_session_of_the_week_even_without_a_send():
    state = {"limit_log": [
        _entry("2026-10-05", "board_kilter", [P("7A", "sent")], target="7A"),
        _entry("2026-10-09", "board_kilter", [P("7B", "no_progress")], target="7A+"),
    ]}
    [row] = limit_log.sends_by_surface(state, [], "2026-10-05", "2026-10-11")
    assert row["max_grade_sent"] == "7A" and row["target_grade"] == "7A+"


def test_weekly_report_carries_limit_sends(monkeypatch):
    monkeypatch.setattr("backend.engine.report_engine.load_outdoor_sessions", lambda *a, **k: [])
    monkeypatch.setattr("backend.engine.report_engine._load_indoor_sessions", lambda *a, **k: [])
    state = {"limit_log": [_entry("2026-10-06", "board_kilter", [P("7A", "sent"), P("7A", "sent")])],
             "free_sessions": [_free("2026-10-10", "board_kilter", [{"grade": "7B", "status": "sent"}])]}
    report = generate_weekly_report(state, None, WEEK)
    assert report["limit_sends"] == [{"surface": "board_kilter", "max_grade_sent": "7B", "sends": 3,
                                      "sources": ["free", "planned"], "target_grade": "7A"}]
    empty = generate_weekly_report({}, None, WEEK)
    assert empty["limit_sends"] == []


# ─── 2. a dialog-shaped item reaches the limit log ───────────────────────


def test_dialog_item_with_problems_writes_the_limit_log_like_the_player():
    st = _fresh_kilter_state("7B")
    # What buildDialogFeedbackItems sends for a limit row: no label, the
    # problems, used_grade = hardest send, surface_selected from the target.
    item = {"exercise_id": "limit_bouldering", "completed": True, "surface_selected": "board_kilter",
            "problems": [P("7B", "sent"), P("7B", "sent")], "used_grade": "7B"}
    out = apply_feedback({"date": DAY, "session_id": "limit_boulder_gym", "feedback_contract": 2,
                          "actual": {"exercise_feedback_v1": [item]}}, st)
    [entry] = out["limit_log"]
    assert entry["step"] == 1 and entry["next_target_grade"] == "7B+" and entry["qualifies"] is True


# ─── 3. read-time targets, never stored ──────────────────────────────────


def _plan_with_custom(status="planned"):
    return {"weeks": [{"days": [{"date": DAY, "sessions": [{
        "session_id": "custom_cs_l", "is_custom": True, "status": status,
        "exercises": [{"exercise_id": "limit_bouldering", "sets": 1},
                      {"exercise_id": "pullup", "sets": 3, "reps": 5}],
    }]}]}]}


def test_week_read_attaches_the_limit_target_of_the_day_to_custom_rows():
    st = _fresh_kilter_state("7B")
    plan = _plan_with_custom()
    out = _with_custom_anchored_loads(plan, st)
    limit_row, other = out["weeks"][0]["days"][0]["sessions"][0]["exercises"]
    expected = limit_grade_target(st, "limit_bouldering", DAY)
    assert limit_row["target_grade"] == expected["target_grade"] == "7B"
    assert limit_row["log_problems"] is True
    assert limit_row["surface_selected"] == expected["surface_selected"]
    assert limit_row["surface_targets"] == expected["surface_targets"]
    assert "target_grade" not in other
    # The stored plan is untouched (read-time only).
    assert "target_grade" not in plan["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]


def test_week_read_leaves_played_custom_sessions_as_stored():
    st = _fresh_kilter_state("7B")
    for status in ("done", "skipped"):
        plan = _plan_with_custom(status)
        out = _with_custom_anchored_loads(plan, st)
        assert out == plan


def test_week_read_and_custom_read_agree():
    st = _fresh_kilter_state("7B")
    rows = [{"exercise_id": "limit_bouldering", "sets": 1}]
    via_week = _with_custom_anchored_loads(_plan_with_custom(), st)["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]
    via_custom = attach_limit_targets(st, rows, DAY)[0]
    for k in ("target_grade", "target_grade_low", "surface_selected", "surface_targets", "log_problems"):
        assert via_week.get(k) == via_custom.get(k)


def test_stale_target_round_tripped_by_the_client_is_recomputed():
    st = _fresh_kilter_state("7B")
    plan = _plan_with_custom()
    plan["weeks"][0]["days"][0]["sessions"][0]["exercises"][0].update(
        {"target_grade": "5A", "log_problems": True, "surface_selected": "gym_boulder"})
    row = _with_custom_anchored_loads(plan, st)["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]
    assert row["target_grade"] == "7B"


def test_previews_carry_the_target_the_player_reads_on_the_same_day():
    st = _fresh_kilter_state("7B")
    catalog = load_exercises_by_id()
    player = attach_limit_targets(st, [{"exercise_id": "limit_bouldering"}], DAY)[0]
    builder = _to_custom_exercise({"id": "limit_bouldering"}, catalog, deepcopy(st), "strength_power", "normal", DAY)
    composed = [{"exercise_id": "limit_bouldering", "sets": 1, "reps": None}]
    _decorate_engine_fields(composed, catalog, deepcopy(st), "strength_power", today=DAY)
    for preview in (builder, composed[0]):
        assert preview["target_grade"] == player["target_grade"]
        assert preview["target_grade_low"] == player["target_grade_low"]
        assert preview["surface_selected"] == player["surface_selected"]


def test_saved_custom_rows_never_keep_the_preview_target():
    from backend.api.models import CustomSessionCreateRequest

    req = CustomSessionCreateRequest(name="L", exercises=[{
        "exercise_id": "limit_bouldering", "sets": 1, "target_grade": "7B",
        "target_grade_low": "7A+", "surface_selected": "board_kilter",
    }])
    dumped = req.exercises[0].model_dump()
    assert not {"target_grade", "target_grade_low", "surface_selected"} & set(dumped)


_SESSION = {"name": "S", "estimated_duration_minutes": 60, "explanation": "x", "exercises": []}


def _compose(monkeypatch, flag, context):
    from backend.coach import athlete_block

    monkeypatch.setenv("COACH_ATHLETE_CONTEXT", flag)
    monkeypatch.setattr(service, "_load_history", lambda uid: [])
    monkeypatch.setattr("backend.coach.adhoc_intent.extract_intent",
                        lambda msg, history=None: {"equipment_set": "gym", "focus": "limit", "minutes": 60})
    monkeypatch.setattr("backend.api.deps.load_state", lambda uid: _fresh_kilter_state("7B"))
    monkeypatch.setattr("backend.coach.session_composer.compose", lambda *a, **k: None)
    monkeypatch.setattr("backend.engine.adhoc_builder.compose_adhoc_session", lambda *a, **k: deepcopy(_SESSION))
    monkeypatch.setattr(service, "_key_guard", lambda *a: {"exclude_ids": [], "warnings": []})
    monkeypatch.setattr(service.storage, "append_coach_message", lambda *a, **k: None)
    monkeypatch.setattr(athlete_block, "composer_context", context)
    return service.handle_adhoc_compose(None, "limit session", target_date=DAY)


def test_adhoc_preview_says_which_day_its_targets_are_for(monkeypatch):
    res = _compose(monkeypatch, "1", lambda st, uid, d: {"as_of": d})
    assert res["session"]["resolved_for_date"] == DAY


def test_adhoc_preview_with_the_flag_off_is_stamped_with_the_server_day(monkeypatch):
    from datetime import date

    res = _compose(monkeypatch, "0", lambda st, uid, d: None)
    # No athlete context: the composers read the server date, the stamp says so.
    assert res["session"]["resolved_for_date"] == date.today().isoformat()
