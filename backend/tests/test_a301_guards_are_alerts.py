"""A301 — guards are alerts: after a user action nothing the user did not touch
is rewritten, and ``guards_v1`` says what the guards object to.

Daniele (2026-10-05): "se voglio fare sovrallenamento lo faccio, decisione mia,
tu solo segnala alert". Covered here:

- ``guards_v1.evaluate``: one test per code, the previous-week seed, the
  ``today`` floor (history counts, is never flagged), determinism, no mutation;
- every user action next to engine sessions leaves the whole week
  byte-identical except the action itself (quick-add, override, move, custom /
  generated / planned session, change of gym, outdoor day, mark done/skipped);
- override replaces only the targeted slot; ``move_session`` refuses a
  done/skipped destination; quick-add ``force`` is a no-op;
- the planner, generating a week on its own, still respects the guards;
- the key-session proposal (engine-made) never adds a guard alert;
- API: ``guard_warnings`` sibling on ``GET /api/week`` and every replanner
  response, never persisted; 422 on a move onto a done session.
"""
from __future__ import annotations

import copy
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import guards_v1
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import apply_day_add, apply_day_override, apply_events

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

MON = "2026-10-05"
FINGER = "strength_long"          # hard + finger + pulling (max)
LIMIT = "limit_boulder_gym"       # hard + finger
HARD = "power_endurance_gym"      # hard, not finger
EASY = "technique_focus_gym"      # medium
HIIT = "treadmill_hiit_4x4"       # HIIT (catalog tags.hiit), not hard


def _d(i: int, start: str = MON) -> str:
    return (date.fromisoformat(start) + timedelta(days=i)).isoformat()


def _sess(sid: str, slot: str = "evening", **kw) -> dict:
    m = _SESSION_META[sid]
    s = {"slot": slot, "session_id": sid, "location": "gym", "gym_id": "g1", "phase_id": "strength_power",
         "intensity": m["intensity"], "tags": {"hard": m["hard"], "finger": m["finger"]},
         "constraints_applied": []}
    s.update(kw)
    return s


def _custom(slot: str = "evening", *, finger: bool = True, sid: str = "custom_cs_1") -> dict:
    return {"slot": slot, "session_id": sid, "custom_session_id": sid[7:], "is_custom": True,
            "name": "My session", "location": "home", "status": "planned", "intensity": "max",
            "tags": {"hard": True, "finger": finger}, "constraints_applied": ["custom_add"],
            "exercises": [{"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7}]}


def _plan(days: dict, *, start: str = MON, hard_cap: int = 3, recovery_multiplier: float = 1.0) -> dict:
    d0 = date.fromisoformat(start)
    out_days = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(days.get(i, []))}
                for i in range(7)]
    return {"start_date": start, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": hard_cap,
                                 "recovery_multiplier": recovery_multiplier},
            "weeks": [{"week_index": 1, "days": out_days}], "adaptations": []}


def _day(plan: dict, i: int) -> dict:
    return plan["weeks"][0]["days"][i]


def _codes(alerts) -> list:
    return [(w["code"], w["date"], w["session_id"]) for w in alerts]


# ---------------------------------------------------------------------------
# guards_v1.evaluate
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_empty_and_clean_plans(self):
        assert guards_v1.evaluate(None) == []
        assert guards_v1.evaluate({}) == []
        assert guards_v1.evaluate(_plan({0: [_sess(FINGER)], 2: [_sess(LIMIT)], 4: [_sess(EASY)]})) == []

    def test_finger_gap(self):
        plan = _plan({0: [_sess(FINGER)], 1: [_sess(LIMIT)]})
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("finger_gap", _d(1), LIMIT)]
        w = alerts[0]
        assert w["with"] == [{"date": _d(0), "slot": "evening", "session_id": FINGER}]
        assert w["gap_days"] == 1 and w["severity"] == "warning" and w["user_owned"] is False

    def test_finger_gap_recovery_multiplier(self):
        plan = _plan({0: [_sess(FINGER)], 2: [_sess(LIMIT)]}, recovery_multiplier=1.5)
        assert _codes(guards_v1.evaluate(plan)) == [("finger_gap", _d(2), LIMIT)]

    def test_previous_week_seeds_monday(self):
        prev = [{"date": _d(-1), "sessions": [_sess(FINGER, status="done")]}]
        plan = _plan({0: [_sess(LIMIT)]})
        assert guards_v1.evaluate(plan) == []
        assert _codes(guards_v1.evaluate(plan, prev)) == [("finger_gap", MON, LIMIT)]

    def test_history_counts_but_is_never_flagged(self):
        plan = _plan({0: [_sess(FINGER, status="done")], 1: [_sess(LIMIT, status="done")],
                      2: [_sess(LIMIT)]})
        # Tue is done → not flagged; Wed after a done Tue → flagged.
        assert _codes(guards_v1.evaluate(plan)) == [("finger_gap", _d(2), LIMIT)]
        # Planned but before today: counted, not flagged.
        plan2 = _plan({0: [_sess(FINGER)], 1: [_sess(LIMIT)], 2: [_sess(LIMIT, slot="lunch")]})
        assert _codes(guards_v1.evaluate(plan2, None, _d(2))) == [("finger_gap", _d(2), LIMIT)]

    def test_skipped_never_counts(self):
        plan = _plan({0: [_sess("regeneration_easy", status="skipped", skipped_session_id=FINGER)],
                      1: [_sess(LIMIT)]})
        assert guards_v1.evaluate(plan) == []

    def test_finger_test_72h(self):
        test = _sess("test_max_hang_7s", tags={"hard": True, "finger": True, "test": True})
        plan = _plan({1: [_sess(LIMIT)], 4: [test]})
        assert _codes(guards_v1.evaluate(plan)) == [("finger_test_72h", _d(1), LIMIT)]
        # 4 days before: outside the block.
        assert guards_v1.evaluate(_plan({0: [_sess(LIMIT)], 4: [test]})) == []

    def test_heavy_pull_7d(self):
        plan = _plan({0: [_sess(FINGER)], 2: [_sess("pulling_strength_gym")],
                      5: [_sess(FINGER, slot="morning")]})
        alerts = [w for w in guards_v1.evaluate(plan) if w["code"] == "heavy_pull_7d"]
        assert [(w["date"], w["count"], w["limit"]) for w in alerts] == [(_d(5), 3, 2)]

    def test_hiit_near_max(self):
        plan = _plan({2: [_sess(HIIT, slot="lunch")], 3: [_sess(FINGER)]})
        assert _codes(guards_v1.evaluate(plan)) == [("hiit_near_max", _d(2), HIIT)]
        # same day, max in the evening
        plan = _plan({3: [_sess(HIIT, slot="lunch"), _sess(LIMIT)]})
        assert _codes(guards_v1.evaluate(plan)) == [("hiit_near_max", _d(3), HIIT)]
        # two days before: fine
        assert guards_v1.evaluate(_plan({1: [_sess(HIIT, slot="lunch")], 3: [_sess(FINGER)]})) == []

    def test_hiit_never_counts_as_hard(self):
        plan = _plan({0: [_sess(HIIT)], 1: [_sess(HARD)], 3: [_sess(HARD)], 5: [_sess(HARD)]}, hard_cap=3)
        assert [w for w in guards_v1.evaluate(plan) if w["code"] == "hard_cap"] == []

    def test_hard_cap(self):
        plan = _plan({0: [_sess(HARD)], 2: [_sess(HARD)], 4: [_sess(HARD)], 6: [_sess(HARD)]}, hard_cap=2)
        alerts = guards_v1.evaluate(plan)
        assert [(w["code"], w["date"]) for w in alerts] == [("hard_cap", _d(4)), ("hard_cap", _d(6))]
        assert alerts[0]["count"] == 4 and alerts[0]["cap"] == 2

    def test_pre_trip(self):
        trip_start = _d(5)
        state = {"trips": [{"start_date": trip_start, "end_date": _d(9), "name": "Kalymnos"}]}
        plan = _plan({3: [_sess(HARD)], 0: [_sess(HARD)]})
        alerts = [w for w in guards_v1.evaluate(plan, None, None, state) if w["code"] == "pre_trip"]
        assert alerts and all(w["date"] >= _d(2) for w in alerts)
        assert not [w for w in guards_v1.evaluate(plan) if w["code"] == "pre_trip"], "no state → no trips"

    def test_post_outdoor(self):
        plan = _plan({1: [_sess(LIMIT)], 2: [_sess(EASY)]})
        _day(plan, 0).update({"outdoor_spot_name": "Berdorf", "outdoor_session_status": "done",
                              "outdoor_load_score": 80})
        assert _codes(guards_v1.evaluate(plan)) == [("post_outdoor", _d(1), LIMIT)]
        # B372: a low load says nothing (it never reached 65 in 37 real
        # days): a completed day without a route log still counts...
        _day(plan, 0)["outdoor_load_score"] = 30
        assert _codes(guards_v1.evaluate(plan)) == [("post_outdoor", _d(1), LIMIT)]
        # ...a measured easy day (routes logged, none hard) does not.
        easy_log = {"outdoor_log": [{"date": _d(0), "discipline": "lead",
                                     "routes": [{"name": "Easy", "grade": "6a"}]}],
                    "performance": {"current_level": {"sport": {"worked": {"grade": "8a"}}}}}
        assert guards_v1.evaluate(plan, None, None, easy_log) == []

    def test_deterministic_and_pure(self):
        plan = _plan({0: [_sess(FINGER)], 1: [_sess(LIMIT), _sess(HIIT, slot="lunch")],
                      2: [_sess(FINGER)], 4: [_sess(HARD)]}, hard_cap=2)
        before = copy.deepcopy(plan)
        a = guards_v1.evaluate(plan, None, MON, {})
        b = guards_v1.evaluate(copy.deepcopy(plan), None, MON, {})
        assert a == b and plan == before
        json.dumps(a)  # serialisable

    def test_new_warnings_and_involves(self):
        before = guards_v1.evaluate(_plan({0: [_sess(FINGER)]}))
        after = guards_v1.evaluate(_plan({0: [_sess(FINGER)], 1: [_sess(LIMIT)]}))
        fresh = guards_v1.new_warnings(before, after)
        assert len(fresh) == 1
        assert guards_v1.involves(fresh[0], _d(1), "evening")
        assert guards_v1.involves(fresh[0], _d(0))
        assert not guards_v1.involves(fresh[0], _d(3))


# ---------------------------------------------------------------------------
# Every user action: the week is byte-identical except the action itself
# ---------------------------------------------------------------------------

def _crowded_week() -> dict:
    """Engine sessions that the old guards would have downshifted after almost
    any action (finger every day, over the cap), a custom, a done day."""
    return _plan({
        0: [_sess(FINGER, status="done")],
        1: [_sess(LIMIT), _sess(EASY, slot="lunch")],
        2: [_sess(HARD)],
        3: [_sess(LIMIT)],
        4: [_custom()],
        5: [_sess(FINGER)],
    }, hard_cap=2)


def _unchanged_except(before: dict, after: dict, dates: set) -> None:
    for b, a in zip(before["weeks"][0]["days"], after["weeks"][0]["days"]):
        if b["date"] not in dates:
            assert a == b, f"{b['date']} was rewritten"


def _no_reconcile_records(after: dict) -> None:
    for a in after.get("adaptations") or []:
        assert a.get("type") not in ("reconcile", "outdoor_ripple", "finger_compensation",
                                     "finger_compensation_warning")


class TestUserActionsRewriteNothingElse:
    def test_quick_add(self):
        plan = _crowded_week()
        out, warnings, adj = apply_day_add(plan, session_id=LIMIT, target_date=_d(2), slot="lunch",
                                           location="gym", prev_days=None, today=_d(1))
        _unchanged_except(plan, out, {_d(2)})
        assert [s for s in _day(out, 2)["sessions"] if s["slot"] == "evening"] == _day(plan, 2)["sessions"]
        assert adj == [] and warnings
        _no_reconcile_records(out)

    def test_override_with_index(self):
        plan = _crowded_week()
        out = apply_day_override(plan, intent="finger_max", location="home", reference_date=_d(1),
                                 target_date=_d(2), session_index=0, today=_d(1))
        _unchanged_except(plan, out, {_d(2)})
        assert _day(out, 2)["sessions"][0]["constraints_applied"] == ["manual_override"]
        _no_reconcile_records(out)

    def test_override_without_index_keeps_other_slots(self):
        plan = _crowded_week()
        out = apply_day_override(plan, intent="strength", location="gym", reference_date=_d(0),
                                 target_date=_d(1), today=_d(1))
        _unchanged_except(plan, out, {_d(1)})
        tue = {s["slot"]: s for s in _day(out, 1)["sessions"]}
        assert tue["lunch"] == _day(plan, 1)["sessions"][1]
        assert tue["evening"]["constraints_applied"] == ["manual_override"]
        ov = next(a for a in out["adaptations"] if a["type"] == "day_override")
        assert ov["whole_day"] is False and (ov["replaced_session_id"], ov["replaced_slot"]) == (LIMIT, "evening")

    def test_override_never_infers_a_user_session(self):
        """A day holding only the user's custom at lunch: an override without
        index/slot goes to the evening and the custom stays."""
        plan = _plan({2: [_custom("lunch")]})
        out = apply_day_override(plan, intent="technique", location="gym", reference_date=_d(1),
                                 target_date=_d(2))
        wed = {s["slot"]: s for s in _day(out, 2)["sessions"]}
        assert wed["lunch"] == _custom("lunch")
        assert wed["evening"]["session_id"] == EASY

    def test_override_replaces_a_user_session_only_when_targeted(self):
        plan = _plan({2: [_custom("lunch"), _sess(LIMIT)]})
        out = apply_day_override(plan, intent="technique", location="gym", reference_date=_d(1),
                                 target_date=_d(2), session_index=0)
        assert [s["session_id"] for s in _day(out, 2)["sessions"]] == [EASY, LIMIT]

    def test_override_done_only_blocks_its_own_slot(self):
        plan = _plan({2: [_sess(EASY, slot="lunch", status="done"), _sess(LIMIT)]})
        out = apply_day_override(plan, intent="technique", location="gym", reference_date=_d(1),
                                 target_date=_d(2))
        assert _day(out, 2)["sessions"][0] == _day(plan, 2)["sessions"][0]
        with pytest.raises(ValueError):
            apply_day_override(plan, intent="technique", location="gym", reference_date=_d(1),
                               target_date=_d(2), slot="lunch")

    def test_outdoor_override_keeps_the_users_sessions(self):
        plan = _plan({2: [_custom("lunch"), _sess(LIMIT)]})
        out = apply_day_override(plan, intent="outdoor_projecting", location="outdoor", reference_date=_d(1),
                                 target_date=_d(2), spot_name="Berdorf")
        assert _day(out, 2)["sessions"] == [_custom("lunch")]
        assert _day(out, 2)["outdoor_spot_name"] == "Berdorf"
        _unchanged_except(plan, out, {_d(2)})

    @pytest.mark.parametrize("event,dates", [
        ({"event_type": "move_session", "from_date": _d(3), "from_slot": "evening",
          "to_date": _d(2), "to_slot": "lunch"}, {_d(2), _d(3)}),
        ({"event_type": "add_custom_session", "custom_session_id": "cs_x", "target_date": _d(2),
          "slot": "lunch", "location": "home"}, {_d(2)}),
        ({"event_type": "add_generated_session", "target_date": _d(2), "slot": "lunch",
          "session_payload": {"build_kind": "body_part", "exercises": [{"exercise_id": "max_hang_7s", "sets": 4}],
                              "tags": {"hard": True, "finger": True}}}, {_d(2)}),
        ({"event_type": "add_planned_session", "session_id": FINGER, "target_date": _d(2),
          "slot": "lunch", "location": "gym", "gym_id": "g1"}, {_d(2)}),
        ({"event_type": "change_gym", "date": _d(1), "location": "home"}, {_d(1)}),
        ({"event_type": "mark_done", "date": _d(1), "slot": "evening"}, {_d(1)}),
        ({"event_type": "mark_skipped", "date": _d(3), "slot": "evening"}, {_d(3)}),
        ({"event_type": "remove_session", "date": _d(2), "slot": "evening"}, {_d(2)}),
    ])
    def test_events(self, event, dates):
        plan = _crowded_week()
        customs = [{"id": "cs_x", "name": "Hangs", "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}]}]
        out = apply_events(plan, [event], custom_sessions=customs, today=_d(1))
        _unchanged_except(plan, out, dates)
        _no_reconcile_records(out)

    def test_big_outdoor_day(self):
        plan = _crowded_week()
        _day(plan, 2).update({"outdoor_spot_name": "Berdorf", "outdoor_session_status": "planned"})
        out = apply_events(plan, [{"event_type": "complete_outdoor", "date": _d(2), "outdoor_load_score": 90}])
        _unchanged_except(plan, out, {_d(2)})
        assert any(w["code"] == "post_outdoor" and w["date"] == _d(3) for w in guards_v1.evaluate(out))

    def test_move_onto_done_or_skipped_is_refused(self):
        for status in ("done", "skipped"):
            plan = _plan({1: [_sess(LIMIT)], 3: [_sess(EASY, status=status)]})
            with pytest.raises(ValueError, match=status):
                apply_events(plan, [{"event_type": "move_session", "from_date": _d(1), "from_slot": "evening",
                                     "to_date": _d(3), "to_slot": "evening"}])

    def test_move_replaces_a_planned_user_session_in_the_targeted_slot(self):
        plan = _plan({1: [_sess(LIMIT)], 3: [_custom()]})
        out = apply_events(plan, [{"event_type": "move_session", "from_date": _d(1), "from_slot": "evening",
                                   "to_date": _d(3), "to_slot": "evening"}])
        assert [s["session_id"] for s in _day(out, 3)["sessions"]] == [LIMIT]

    def test_force_is_a_noop(self):
        plan = _crowded_week()
        a = apply_day_add(plan, session_id=LIMIT, target_date=_d(2), slot="lunch", location="gym", force=True)
        b = apply_day_add(plan, session_id=LIMIT, target_date=_d(2), slot="lunch", location="gym", force=False)
        assert a == b

    def test_past_sessions_immutable_through_every_action(self):
        plan = _crowded_week()
        done_mon = copy.deepcopy(_day(plan, 0))
        out, _w, _a = apply_day_add(plan, session_id=FINGER, target_date=_d(1), slot="morning", location="gym")
        out = apply_day_override(out, intent="finger_max", location="home", reference_date=_d(1),
                                 target_date=_d(2), session_index=0)
        out = apply_events(out, [{"event_type": "move_session", "from_date": _d(3), "from_slot": "evening",
                                  "to_date": _d(6), "to_slot": "evening"}])
        assert _day(out, 0) == done_mon


# ---------------------------------------------------------------------------
# The planner, on its own, still respects the guards
# ---------------------------------------------------------------------------

class TestPlannerStillRespectsGuards:
    @pytest.mark.parametrize("phase", ["base", "strength_power", "power_endurance", "performance", "deload"])
    @pytest.mark.parametrize("days", [3, 5, 6])
    def test_generated_week_has_no_alert(self, phase, days):
        from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
        from backend.engine.planner_v2 import generate_phase_week

        slot = {"available": True, "locations": ["gym", "home"], "gym_id": "g1"}
        avail = {d: {"morning": dict(slot), "lunch": dict(slot), "evening": dict(slot)}
                 for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
                   "technique": 50, "endurance": 40}
        week = generate_phase_week(
            phase_id=phase, domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase], profile),
            session_pool=_build_session_pool(phase), start_date="2026-01-05", availability=avail,
            allowed_locations=["home", "gym"], hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": days, "hard_day_cap_per_week": 3},
            default_gym_id="g1",
            gyms=[{"gym_id": "g1", "equipment": ["gym_boulder", "board_kilter", "hangboard", "pullup_bar",
                                                 "gym_routes"]}],
            home_equipment=["hangboard", "pullup_bar"],
        )
        # A305: the week-level density alert is not a recovery guard — the
        # planner fills the days the athlete made available and only says so.
        assert [w for w in guards_v1.evaluate(week) if w["code"] != guards_v1.CODE_LOW_REST_DAYS] == []


# ---------------------------------------------------------------------------
# Key-session proposals (engine-made) never add a guard alert
# ---------------------------------------------------------------------------

def test_key_proposal_adds_no_guard_alert():
    from backend.engine import key_sessions_v1 as ks
    from backend.tests.test_a294_key_sessions import TestProposals

    st = TestProposals()._skipped_strength_long()
    status = ks.compute_key_status(st, "2026-10-06")
    assert status["proposals"]
    plan = st["week_plans"]["2026-10-05"]
    after = apply_events(plan, [status["proposals"][0]["apply"]["event"]])
    assert guards_v1.new_warnings(guards_v1.evaluate(plan, None, "2026-10-06", st),
                                  guards_v1.evaluate(after, None, "2026-10-06", st)) == []


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _current_monday() -> str:
    t = date.today()
    return (t - timedelta(days=t.weekday())).isoformat()


def _seed(plan: dict) -> None:
    state = deps.load_state(None)
    state.setdefault("week_plans", {})[plan["start_date"]] = plan
    state.pop("macrocycle_paused", None)
    deps.save_state(state, None)


class TestApi:
    def test_quick_add_force_and_guard_warnings(self, isolated_state):
        mon = _current_monday()
        plan = _plan({0: [_sess(FINGER)], 2: [_sess(LIMIT)]}, start=mon)
        _seed(plan)
        r = client.post("/api/replanner/quick-add", json={
            "week_plan": plan, "session_id": LIMIT, "target_date": _d(1, mon), "slot": "evening",
            "location": "gym", "today": mon,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        days = body["week_plan"]["weeks"][0]["days"]
        assert days[1]["sessions"][0]["session_id"] == LIMIT
        assert days[2]["sessions"][0]["session_id"] == LIMIT
        assert body["adjustments"] == []
        codes = {(w["code"], w["date"]) for w in body["guard_warnings"]}
        assert ("finger_gap", _d(1, mon)) in codes and ("finger_gap", _d(2, mon)) in codes
        saved = deps.load_state(None)
        assert "guard_warnings" not in json.dumps(saved["week_plans"][mon])

    def test_override_keeps_custom_in_other_slot(self, isolated_state):
        mon = _current_monday()
        plan = _plan({2: [_custom("lunch"), _sess(EASY)]}, start=mon)
        _seed(plan)
        r = client.post("/api/replanner/override", json={
            "week_plan": plan, "intent": "strength", "location": "gym",
            "reference_date": _d(1, mon), "target_date": _d(2, mon), "today": mon,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        # B371 review: the response is the read view (anchored loads on the
        # custom's rows); the STORED custom is the one the user put there.
        wed = {s["slot"]: s for s in body["week_plan"]["weeks"][0]["days"][2]["sessions"]}
        assert [e["exercise_id"] for e in wed["lunch"]["exercises"]] == [
            e["exercise_id"] for e in _custom("lunch")["exercises"]]
        saved = deps.load_state(None)["week_plans"][mon]
        swed = {s["slot"]: s for s in saved["weeks"][0]["days"][2]["sessions"]}
        assert swed["lunch"] == _custom("lunch")
        assert body["adjustments"] == [] and isinstance(body["guard_warnings"], list)

    def test_move_onto_done_is_422(self, isolated_state):
        mon = _current_monday()
        plan = _plan({1: [_sess(LIMIT)], 3: [_sess(EASY, status="done")]}, start=mon)
        _seed(plan)
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "today": mon,
            "events": [{"event_type": "move_session", "from_date": _d(1, mon), "from_slot": "evening",
                        "to_date": _d(3, mon), "to_slot": "evening"}],
        })
        assert r.status_code == 422

    def test_events_response_and_dry_run_carry_guard_warnings(self, isolated_state):
        mon = _current_monday()
        plan = _plan({0: [_sess(FINGER)]}, start=mon)
        _seed(plan)
        ev = [{"event_type": "add_planned_session", "session_id": LIMIT, "target_date": _d(1, mon),
               "slot": "evening", "location": "gym", "gym_id": "g1"}]
        dry = client.post("/api/replanner/events", json={"week_plan": plan, "today": mon, "dry_run": True,
                                                        "events": ev})
        assert dry.status_code == 200, dry.text
        assert any(w["code"] == "finger_gap" for w in dry.json()["added_guard_warnings"])
        assert any(w["code"] == "finger_gap" for w in dry.json()["guard_warnings"])
        real = client.post("/api/replanner/events", json={"week_plan": plan, "today": mon, "events": ev})
        assert real.status_code == 200, real.text
        body = real.json()
        assert body["week_plan"]["weeks"][0]["days"][1]["sessions"][0]["session_id"] == LIMIT
        assert any(w["code"] == "finger_gap" and w["date"] == _d(1, mon) for w in body["guard_warnings"])

    def test_get_week_carries_guard_warnings_never_persisted(self, isolated_state):
        mon = date.fromisoformat(_current_monday())
        state = deps.load_state(None)
        state["macrocycle"] = {
            "start_date": (mon - timedelta(weeks=1)).isoformat(),
            "end_date": (mon + timedelta(weeks=11) - timedelta(days=1)).isoformat(),
            "total_weeks": 12,
            "phases": [
                {"phase_id": "strength_power", "duration_weeks": 12, "domain_weights": {}, "session_pool": [],
                 "start_week": 1, "end_week": 12},
            ],
        }
        plan = _plan({0: [_sess(FINGER)], 1: [_sess(LIMIT)]}, start=mon.isoformat())
        state["week_plans"] = {mon.isoformat(): plan}
        state["current_week_plan"] = plan
        state.pop("macrocycle_paused", None)
        deps.save_state(state, None)
        r = client.get("/api/week/0", params={"today": mon.isoformat()})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["week_plan"]["weeks"][0]["days"][1]["sessions"][0]["session_id"] == LIMIT
        assert [(w["code"], w["date"]) for w in body["guard_warnings"]] == [("finger_gap", _d(1, mon.isoformat()))]
        saved = deps.load_state(None)
        assert "guard_warnings" not in json.dumps(saved.get("week_plans") or {})
        # Reading the alerts changes nothing in the stored plan.
        assert saved["week_plans"][mon.isoformat()] == plan


# ---------------------------------------------------------------------------
# A301 review — override targeting, Skip day, back-to-back alert, alert keys
# ---------------------------------------------------------------------------

def _generated(slot: str = "evening") -> dict:
    return {"slot": slot, "session_id": "generated_bp_1", "is_generated": True, "location": "home",
            "status": "planned", "intensity": "medium", "tags": {"hard": False, "finger": False},
            "constraints_applied": ["generated_add"]}


class TestOverrideTargetReview:
    def test_inferred_override_never_replaces_the_users_evening(self):
        """Engine lunch + the user's custom in the evening, override without
        index/slot: the engine lunch is the target, the custom stays."""
        plan = _plan({2: [_sess(EASY, slot="lunch"), _custom("evening")]})
        out = apply_day_override(plan, intent="strength", location="gym", reference_date=_d(1),
                                 target_date=_d(2))
        wed = _day(out, 2)["sessions"]
        assert _custom("evening") in wed
        assert [s["slot"] for s in wed if s.get("constraints_applied") == ["manual_override"]] == ["lunch"]
        assert EASY not in [s["session_id"] for s in wed]

    @pytest.mark.parametrize("intent", ["technique", "rest", "strength"])
    def test_lone_custom_evening_is_byte_identical(self, intent):
        plan = _plan({2: [_custom("evening")]})
        out = apply_day_override(plan, intent=intent, location="home", reference_date=_d(1),
                                 target_date=_d(2))
        wed = _day(out, 2)["sessions"]
        assert wed[0] == _custom("evening") or _custom("evening") in wed
        assert len(wed) == 2
        ov = next(a for a in out["adaptations"] if a["type"] == "day_override")
        assert "replaced_session_id" not in ov and not ov.get("replaced_slots")

    def test_stacked_engine_and_generated_evening(self):
        """B218 stack: only the engine session of the evening is replaced."""
        plan = _plan({2: [_sess(HARD), _generated("evening")]})
        out = apply_day_override(plan, intent="technique", location="gym", reference_date=_d(1),
                                 target_date=_d(2))
        wed = _day(out, 2)["sessions"]
        assert _generated("evening") in wed
        assert HARD not in [s["session_id"] for s in wed]
        assert EASY in [s["session_id"] for s in wed]

    def test_skip_day_replaces_every_engine_session(self):
        """'Skip day' (rest, no index/slot): the old whole-day semantics over
        the ENGINE sessions — lunch and evening both go; nothing the user owns
        or did is touched; the regeneration does not bring them back."""
        from backend.engine.replanner_v1 import regenerate_preserving_completed

        base = {2: [_sess(EASY, slot="lunch"), _sess(LIMIT)]}
        out = apply_day_override(_plan(base), intent="rest", location="home", reference_date=_d(1),
                                 target_date=_d(2))
        wed = _day(out, 2)["sessions"]
        assert [(s["slot"], s["session_id"]) for s in wed] == [("evening", "regeneration_easy")]
        ov = next(a for a in out["adaptations"] if a["type"] == "day_override")
        assert ov["whole_day"] is True and ov["replaced_slots"] == ["lunch", "evening"]
        regen = regenerate_preserving_completed(out, _plan(base))
        assert _day(regen, 2)["sessions"] == wed

    def test_skip_day_keeps_user_and_done_sessions(self):
        plan = _plan({2: [_sess(EASY, slot="morning", status="done"), _custom("lunch"), _sess(LIMIT)]})
        out = apply_day_override(plan, intent="rest", location="home", reference_date=_d(1),
                                 target_date=_d(2))
        wed = _day(out, 2)["sessions"]
        assert wed[0] == _day(plan, 2)["sessions"][0]
        assert wed[1] == _custom("lunch")
        assert wed[2]["session_id"] == "regeneration_easy"
        _unchanged_except(plan, out, {_d(2)})

    def test_whole_day_flag_is_explicit(self):
        base = {2: [_sess(EASY, slot="lunch"), _sess(LIMIT)]}
        only_evening = apply_day_override(_plan(base), intent="rest", location="home", reference_date=_d(1),
                                          target_date=_d(2), whole_day=False)
        assert [s["session_id"] for s in _day(only_evening, 2)["sessions"]] == [EASY, "regeneration_easy"]
        whole = apply_day_override(_plan(base), intent="technique", location="gym", reference_date=_d(1),
                                   target_date=_d(2), whole_day=True)
        assert [s["session_id"] for s in _day(whole, 2)["sessions"]] == [EASY]
        assert _day(whole, 2)["sessions"][0]["constraints_applied"] == ["manual_override"]

    def test_skip_day_on_a_done_day_is_refused(self):
        plan = _plan({2: [_sess(LIMIT, status="done")]})
        with pytest.raises(ValueError, match="already completed/skipped"):
            apply_day_override(plan, intent="rest", location="home", reference_date=_d(1), target_date=_d(2))


class TestHardBackToBack:
    def test_quick_add_the_day_before_an_engine_hard_day(self):
        plan = _plan({2: [_sess(HARD)]})
        out, warnings, _adj = apply_day_add(plan, session_id=HARD, target_date=_d(1), slot="evening",
                                            location="gym")
        alerts = guards_v1.evaluate(out)
        assert _codes(alerts) == [("hard_back_to_back", _d(2), HARD)]
        assert alerts[0]["with"] == [{"date": _d(1), "slot": "evening", "session_id": HARD}]
        assert any("back-to-back" in w for w in warnings)

    def test_override_next_to_an_engine_hard_day(self):
        plan = _plan({1: [_sess(EASY)], 2: [_sess(HARD)]})
        out = apply_day_override(plan, intent="power_endurance", location="gym", reference_date=_d(0),
                                 target_date=_d(1))
        assert ("hard_back_to_back", _d(2)) in {(w["code"], w["date"]) for w in guards_v1.evaluate(out)}

    def test_engine_pairs_are_not_flagged(self):
        assert guards_v1.evaluate(_plan({1: [_sess(HARD)], 2: [_sess(HARD)]})) == []

    def test_hiit_is_not_hard(self):
        plan = _plan({1: [_sess(HIIT, slot="lunch", constraints_applied=["quick_add"])], 2: [_sess(HARD)]})
        assert [w for w in guards_v1.evaluate(plan) if w["code"] == "hard_back_to_back"] == []

    def test_done_side_is_never_flagged(self):
        plan = _plan({1: [_sess(HARD, constraints_applied=["quick_add"])], 2: [_sess(HARD, status="done")]})
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("hard_back_to_back", _d(1), HARD)]


def test_new_warnings_over_the_cap_on_an_already_hard_day():
    """A week already over the cap: one more hard session on a day that is
    already hard adds no hard day, so no alert is 'new'."""
    before_plan = _plan({0: [_sess(HARD)], 2: [_sess(HARD)], 4: [_sess(HARD)], 6: [_sess(HARD)]}, hard_cap=2)
    after_plan = copy.deepcopy(before_plan)
    _day(after_plan, 0)["sessions"].append(_sess(HARD, slot="lunch"))
    before, after = guards_v1.evaluate(before_plan), guards_v1.evaluate(after_plan)
    assert [w["with"] for w in before] != [w["with"] for w in after]  # the `with` lists did change
    assert guards_v1.new_warnings(before, after) == []


class TestApiReview:
    def test_quick_add_warnings_read_the_state(self, isolated_state):
        mon = _current_monday()
        state = deps.load_state(None)
        state["trips"] = [{"start_date": _d(5, mon), "end_date": _d(9, mon), "name": "Kalymnos"}]
        deps.save_state(state, None)
        plan = _plan({}, start=mon)
        _seed(plan)
        r = client.post("/api/replanner/quick-add", json={
            "week_plan": plan, "session_id": HARD, "target_date": _d(3, mon), "slot": "evening",
            "location": "gym", "today": mon,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        pre = [w["message"] for w in body["guard_warnings"] if w["code"] == "pre_trip" and w["date"] == _d(3, mon)]
        assert pre and all(m in body["warnings"] for m in pre)

    def test_override_warnings_are_the_overridden_slot_only(self, isolated_state):
        mon = _current_monday()
        plan = _plan({1: [_sess(FINGER)], 2: [_sess(LIMIT, slot="lunch"), _sess(EASY)]}, start=mon)
        _seed(plan)
        r = client.post("/api/replanner/override", json={
            "week_plan": plan, "intent": "technique", "location": "gym",
            "reference_date": _d(1, mon), "target_date": _d(2, mon), "session_index": 1, "today": mon,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert any(w["code"] == "finger_gap" and w["slot"] == "lunch" for w in body["guard_warnings"])
        assert body["warnings"] == []

    def test_skip_day_through_the_api(self, isolated_state):
        mon = _current_monday()
        plan = _plan({2: [_sess(EASY, slot="lunch"), _sess(LIMIT)]}, start=mon)
        _seed(plan)
        r = client.post("/api/replanner/override", json={
            "week_plan": plan, "intent": "rest", "location": "home",
            "reference_date": _d(1, mon), "target_date": _d(2, mon), "today": mon,
        })
        assert r.status_code == 200, r.text
        wed = r.json()["week_plan"]["weeks"][0]["days"][2]["sessions"]
        assert [s["session_id"] for s in wed] == ["regeneration_easy"]

    def test_events_surface_a_lost_finger_session(self, isolated_state):
        mon = _current_monday()
        plan = _plan({1: [_sess(LIMIT)]}, start=mon)
        _seed(plan)
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "today": mon,
            "events": [{"event_type": "change_gym", "date": _d(1, mon), "location": "home"}],
        })
        assert r.status_code == 200, r.text
        assert any("finger session lost" in w for w in r.json()["warnings"])
