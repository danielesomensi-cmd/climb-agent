"""B367 (#3) — the weekly hard cap counts the hard days already done.

``_enforce_caps`` (and the quick-add cap warning) selected hard days with
``status != "done"``: after two completed hard days the week had room for two
more, and a quick-add of a 4th hard session after 3 done ones went through with
no warning and no downshift. Done sessions now count; they are still never
rewritten, and skipped sessions still never count.

A301: after a user action the cap is an ALERT (quick-add warning, guards_v1
``hard_cap``), never a downshift; ``_enforce_caps`` survives as the probe of the
post-merge alert and keeps its counting rule.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta

from backend.engine.planner_v2 import _SESSION_META
from backend.engine import guards_v1
from backend.engine.replanner_v1 import _enforce_caps, apply_day_add, apply_events

HARD = "power_endurance_gym"  # hard, not finger: isolates the cap from the 48h gap
MON = "2026-10-05"


def _sess(sid, slot="evening", **kw):
    m = _SESSION_META[sid]
    s = {"slot": slot, "session_id": sid, "location": "gym", "intensity": m["intensity"],
         "tags": {"hard": m["hard"], "finger": m["finger"]}, "constraints_applied": []}
    s.update(kw)
    return s


def _plan(days_sessions, hard_cap=3):
    d0 = date.fromisoformat(MON)
    days = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(days_sessions.get(i, []))}
            for i in range(7)]
    return {"start_date": MON, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": hard_cap,
                                 "recovery_multiplier": 1.0},
            "weeks": [{"week_index": 1, "days": days}], "adaptations": []}


def _day(plan, i):
    return plan["weeks"][0]["days"][i]


def test_done_hard_days_count_toward_the_cap():
    plan = _plan({0: [_sess(HARD, status="done")], 1: [_sess(HARD, status="done")],
                  3: [_sess(HARD)], 4: [_sess(HARD)], 6: [_sess(HARD)]})
    done_before = [copy.deepcopy(_day(plan, i)) for i in (0, 1)]
    adj = _enforce_caps(plan)
    # 5 hard days, cap 3 → the two latest planned ones go
    assert sorted(a["date"] for a in adj) == ["2026-10-09", "2026-10-11"]
    assert _day(plan, 3)["sessions"][0]["session_id"] == HARD
    assert [_day(plan, i) for i in (0, 1)] == done_before, "a done session was rewritten"


def test_skipped_sessions_do_not_count():
    skipped = _sess("regeneration_easy", status="skipped", skipped_session_id=HARD,
                    skipped_tags={"hard": True, "finger": False})
    # a skipped session that still carries hard tags (defensive) never counts either
    skipped_hard = _sess(HARD, slot="morning", status="skipped")
    plan = _plan({0: [skipped], 1: [skipped_hard], 2: [_sess(HARD)], 4: [_sess(HARD)], 6: [_sess(HARD)]})
    before = copy.deepcopy(plan)
    assert _enforce_caps(plan) == []
    assert plan == before


def test_quick_add_fourth_hard_after_three_done_is_kept_and_warned():
    plan = _plan({0: [_sess(HARD, status="done")], 1: [_sess(HARD, status="done")],
                  2: [_sess(HARD, status="done")]})
    done_before = [copy.deepcopy(_day(plan, i)) for i in (0, 1, 2)]
    out, warnings, adj = apply_day_add(plan, session_id=HARD, target_date="2026-10-10", location="gym")
    assert any("exceeds weekly cap" in w for w in warnings)
    assert adj == []
    assert _day(out, 5)["sessions"][0]["session_id"] == HARD
    assert [_day(out, i) for i in (0, 1, 2)] == done_before
    alerts = guards_v1.evaluate(out)
    assert [(w["code"], w["date"], w["count"], w["cap"]) for w in alerts] == [("hard_cap", "2026-10-10", 4, 3)]


def test_forced_quick_add_still_kept_past_the_cap():
    """A301: force is a no-op — kept with or without it."""
    plan = _plan({0: [_sess(HARD, status="done")], 1: [_sess(HARD, status="done")],
                  2: [_sess(HARD, status="done")]})
    out, _w, adj = apply_day_add(plan, session_id=HARD, target_date="2026-10-10",
                                 location="gym", force=True)
    assert _day(out, 5)["sessions"][0]["session_id"] == HARD
    assert not any(a["reason"] == "hard_cap_downshift" for a in adj)


def test_frozen_past_hard_days_count_and_stay_byte_identical():
    plan = _plan({0: [_sess(HARD)], 1: [_sess(HARD)], 2: [_sess(HARD)], 5: [_sess(HARD)]})
    past_before = [copy.deepcopy(_day(plan, i)) for i in (0, 1, 2)]
    out = apply_events(plan, [], today="2026-10-09")
    assert [_day(out, i) for i in (0, 1, 2)] == past_before
    # A301: events never downshift; the 4th hard day is an alert.
    assert _day(out, 5)["sessions"][0]["session_id"] == HARD
    alerts = guards_v1.evaluate(out, None, "2026-10-09")
    assert [(w["code"], w["date"]) for w in alerts] == [("hard_cap", "2026-10-10")]


def test_deterministic():
    def run():
        p = _plan({0: [_sess(HARD, status="done")], 2: [_sess(HARD)], 4: [_sess(HARD)], 5: [_sess(HARD)]})
        return _enforce_caps(p), p
    assert run() == run()
