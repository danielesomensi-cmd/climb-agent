"""B367 (#1) — adaptive replan never deletes what the engine may not rewrite.

After 2× very_hard/fail in 3 days, ``insert_recovery`` replaced the WHOLE
target day with one regeneration_easy: a custom session on that day vanished,
and so did a done session sharing the day with a planned one (the check only
skipped days that were ENTIRELY done/skipped). ``downgrade_next_hard`` likewise
turned a custom hard session into complementary_conditioning. Both now go
through the replanner's ``_is_rewritable`` and never touch a day before today.
"""
from __future__ import annotations

import copy

from backend.engine.adaptive_replan import apply_adaptive_replan, check_adaptive_replan

TWO_HARD = [{"date": "2026-10-05", "difficulty": "very_hard"},
            {"date": "2026-10-04", "difficulty": "fail"}]
ONE_HARD = [{"date": "2026-10-05", "difficulty": "very_hard"}]


def _s(sid, slot="evening", hard=False, finger=False, intensity="medium", **kw):
    s = {"session_id": sid, "slot": slot, "location": "gym", "gym_id": "g1",
         "intensity": intensity, "tags": {"hard": hard, "finger": finger}}
    s.update(kw)
    return s


def _custom(slot="morning", hard=False):
    return _s("custom_abc", slot=slot, hard=hard, finger=hard, is_custom=True,
              custom_session_id="abc", status="planned", exercises=[{"exercise_id": "max_hang_7s"}])


def _plan(days):
    return {"weeks": [{"week_index": 1, "days": [{"date": d, "sessions": ss} for d, ss in days]}],
            "adaptations": []}


def _run(plan, history, current="2026-10-05", today=None):
    r = check_adaptive_replan(plan, history, current, today=today)
    return r["actions"], apply_adaptive_replan(plan, r["actions"]) if r["actions"] else plan


def _sessions(plan, i):
    return plan["weeks"][0]["days"][i]["sessions"]


def test_recovery_keeps_the_custom_session_byte_identical():
    custom = _custom()
    plan = _plan([("2026-10-06", [custom, _s("strength_long", hard=True, finger=True)])])
    actions, out = _run(plan, TWO_HARD)
    assert actions[0]["type"] == "insert_recovery"
    ss = _sessions(out, 0)
    assert ss[0] == custom
    assert ss[1]["session_id"] == "regeneration_easy" and ss[1]["slot"] == "evening"
    assert ss[1]["downshifted_from"] == "strength_long"


def test_recovery_never_deletes_a_done_session():
    done = _s("power_endurance_gym", slot="morning", hard=True, status="done", feedback_summary="hard")
    plan = _plan([("2026-10-06", [done, _s("technique_focus_gym", status="planned")])])
    _actions, out = _run(plan, TWO_HARD)
    ss = _sessions(out, 0)
    assert ss[0] == done, "a completed session was deleted/rewritten"
    assert [s["session_id"] for s in ss] == ["power_endurance_gym", "regeneration_easy"]


def test_day_with_only_protected_sessions_is_skipped_for_the_next_one():
    skipped = _s("regeneration_easy", status="skipped", skipped_session_id="strength_long")
    forced = _s("strength_long", slot="lunch", hard=True, finger=True, forced=True)
    day1 = [_custom(), skipped, forced]
    plan = _plan([("2026-10-06", copy.deepcopy(day1)),
                  ("2026-10-07", [_s("power_endurance_gym", hard=True)])])
    actions, out = _run(plan, TWO_HARD)
    assert actions[0]["target_date"] == "2026-10-07"
    assert _sessions(out, 0) == day1
    assert _sessions(out, 1)[0]["session_id"] == "regeneration_easy"


def test_all_rewritable_day_unchanged_from_before():
    """Regression guard: a plain engine day still becomes one recovery session."""
    plan = _plan([("2026-10-06", [_s("strength_long", slot="morning", hard=True, finger=True),
                                  _s("technique_focus_gym")])])
    _a, out = _run(plan, TWO_HARD)
    ss = _sessions(out, 0)
    assert len(ss) == 1 and ss[0]["session_id"] == "regeneration_easy" and ss[0]["slot"] == "morning"


def test_downgrade_skips_custom_and_forced_hard_sessions():
    custom_hard = _custom(slot="evening", hard=True)
    forced = _s("strength_long", hard=True, finger=True, forced=True)
    plan = _plan([("2026-10-06", [custom_hard]), ("2026-10-07", [forced]),
                  ("2026-10-08", [_s("power_endurance_gym", hard=True)])])
    actions, out = _run(plan, ONE_HARD)
    assert actions[0]["type"] == "downgrade_next_hard"
    assert actions[0]["target_date"] == "2026-10-08"
    assert _sessions(out, 0) == [custom_hard]
    assert _sessions(out, 1) == [forced]
    assert _sessions(out, 2)[0]["session_id"] == "complementary_conditioning"


def test_apply_is_defensive_against_a_stale_action():
    """An action computed on another plan never rewrites a protected session."""
    custom_hard = _custom(slot="evening", hard=True)
    plan = _plan([("2026-10-06", [custom_hard])])
    out = apply_adaptive_replan(plan, [
        {"type": "downgrade_next_hard", "target_date": "2026-10-06"},
        {"type": "insert_recovery", "target_date": "2026-10-06"},
    ])
    assert _sessions(out, 0) == [custom_hard]


def test_days_before_today_are_never_targeted():
    """Late feedback for a past date: the days between it and today are past."""
    past_mon = [_s("strength_long", hard=True, finger=True)]
    plan = _plan([("2026-10-06", copy.deepcopy(past_mon)),
                  ("2026-10-08", [_s("power_endurance_gym", hard=True)])])
    actions, out = _run(plan, TWO_HARD, today="2026-10-08")
    assert actions[0]["target_date"] == "2026-10-08"
    assert _sessions(out, 0) == past_mon
    actions1, out1 = _run(plan, ONE_HARD, today="2026-10-08")
    assert actions1[0]["target_date"] == "2026-10-08"
    assert _sessions(out1, 0) == past_mon


def test_deterministic():
    plan = _plan([("2026-10-06", [_custom(), _s("strength_long", hard=True, finger=True)])])
    assert _run(copy.deepcopy(plan), TWO_HARD) == _run(copy.deepcopy(plan), TWO_HARD)
