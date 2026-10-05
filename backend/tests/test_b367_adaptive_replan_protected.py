"""B367 (#1) / B369 — adaptive replan targets, and it never rewrites anything.

B367 made the automatic rewrite spare what the engine may not touch (custom,
forced, done/skipped sessions, days before today). B369 removed the rewrite
altogether (Daniele, 2026-10-05: "non facciamo cose automatiche"): the detection
only produces a suggestion for the /api/feedback response. These tests pin the
detection's targets — the default (engine-rewritable) reading kept from B367,
and the suggestion reading (``include_protected``) that also names the user's
own hard session, since that is exactly what the athlete may want to lighten.
"""
from __future__ import annotations

import copy

from backend.engine.adaptive_replan import build_adaptive_suggestion, check_adaptive_replan

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
              custom_session_id="abc", status="planned", exercises=[{"exercise_id": "max_hang_7s"}],
              constraints_applied=["custom_add"])


def _plan(days):
    return {"weeks": [{"week_index": 1, "days": [{"date": d, "sessions": ss} for d, ss in days]}],
            "adaptations": []}


def _actions(plan, history, current="2026-10-05", today=None, include_protected=False):
    before = copy.deepcopy(plan)
    r = check_adaptive_replan(plan, history, current, today=today, include_protected=include_protected)
    assert plan == before, "detection must never mutate the plan"
    return r["actions"]


def test_day_with_only_protected_sessions_is_skipped_for_the_next_one():
    skipped = _s("regeneration_easy", status="skipped", skipped_session_id="strength_long")
    forced = _s("strength_long", slot="lunch", hard=True, finger=True, forced=True)
    plan = _plan([("2026-10-06", [_custom(), skipped, forced]),
                  ("2026-10-07", [_s("power_endurance_gym", hard=True)])])
    assert _actions(plan, TWO_HARD)[0]["target_date"] == "2026-10-07"


def test_default_reading_skips_custom_and_forced_hard_sessions():
    plan = _plan([("2026-10-06", [_custom(slot="evening", hard=True)]),
                  ("2026-10-07", [_s("strength_long", hard=True, finger=True, forced=True)]),
                  ("2026-10-08", [_s("power_endurance_gym", hard=True)])])
    actions = _actions(plan, ONE_HARD)
    assert actions[0]["type"] == "downgrade_next_hard"
    assert actions[0]["target_date"] == "2026-10-08"


def test_suggestion_names_the_users_own_hard_session():
    """B369: the custom limit boulder of tomorrow is what the alert is about."""
    custom_hard = _custom(slot="evening", hard=True)
    plan = _plan([("2026-10-06", [custom_hard]),
                  ("2026-10-08", [_s("power_endurance_gym", hard=True)])])
    actions = _actions(plan, ONE_HARD, include_protected=True)
    assert actions[0]["target_date"] == "2026-10-06"
    suggestion = build_adaptive_suggestion({"actions": actions}, plan)
    assert suggestion["session_id"] == "custom_abc"
    assert suggestion["user_owned"] is True
    assert suggestion["plan_changed"] is False


def test_suggestion_never_targets_done_or_skipped():
    plan = _plan([("2026-10-06", [_s("strength_long", hard=True, status="done")]),
                  ("2026-10-07", [_s("power_endurance_gym", hard=True)])])
    assert _actions(plan, ONE_HARD, include_protected=True)[0]["target_date"] == "2026-10-07"


def test_days_before_today_are_never_targeted():
    """Late feedback for a past date: the days between it and today are past."""
    plan = _plan([("2026-10-06", [_s("strength_long", hard=True, finger=True)]),
                  ("2026-10-08", [_s("power_endurance_gym", hard=True)])])
    assert _actions(plan, TWO_HARD, today="2026-10-08")[0]["target_date"] == "2026-10-08"
    assert _actions(plan, ONE_HARD, today="2026-10-08")[0]["target_date"] == "2026-10-08"
    assert _actions(plan, ONE_HARD, today="2026-10-08", include_protected=True)[0]["target_date"] == "2026-10-08"


def test_deterministic():
    plan = _plan([("2026-10-06", [_custom(), _s("strength_long", hard=True, finger=True)])])
    assert _actions(copy.deepcopy(plan), TWO_HARD) == _actions(copy.deepcopy(plan), TWO_HARD)
