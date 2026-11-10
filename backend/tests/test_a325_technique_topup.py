"""A325 — technique key: drills add up over the week, one missing drill is a
top-up of a planned session; add-exercise ``position``; plausible duration.

Shape of the 2026-11-09 case: a custom session listed two feet / positioning
drills, one was done, the app proposed to replace a whole evening session.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import key_sessions_v1 as ks
from backend.engine.session_duration import MAX_SESSION_DURATION_S, keep_longest, plausible_duration
from backend.tests.test_a294_key_sessions import _req, _sess, _state, _week

client = TestClient(app)
REAL_STATE_PATH = Path(__file__).resolve().parent / "fixtures" / "test_user_state.json"
MON, TUE, WED = "2026-10-05", "2026-10-06", "2026-10-07"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _custom(done_ids, listed=("no_readjust_drill", "tech_hard_target"), status="done"):
    return _sess("evening", "custom_cs_tech", status, is_custom=True, name="Tecnica",
                 tags={"hard": False, "finger": False},
                 exercises=[{"exercise_id": e, "sets": 4, "reps": 2} for e in listed],
                 actual_exercises=[{"exercise_id": e, "completed": e in done_ids,
                                    "completed_sets": 4 if e in done_ids else 0, "completed_reps": 2}
                                   for e in listed] if status == "done" else None)


def _resolved(*instances):
    return {"resolved_session": {"exercise_instances": [dict(i) for i in instances]}}


WARMUP = {"exercise_id": "easy_climbing_warmup", "category": "warmup_specific", "source": "resolver"}
MAIN = {"exercise_id": "boulder_circuit", "category": "power_endurance", "source": "resolver"}


def _host(slot="evening", sid="boulder_circuit_gym", **kw):
    return _sess(slot, sid, location="gym", gym_id="g1", resolved=_resolved(WARMUP, MAIN), **kw)


def _st(days, today_week="2026-10-05"):
    st = _state()
    st["week_plans"][today_week] = _week(today_week, days)
    return st


class TestWeeklyCredit:
    def test_one_drill_of_two_is_partial_with_the_reason(self):
        st = _st({MON: [_custom(["no_readjust_drill"])], TUE: [_host()]})
        tech = _req(ks.compute_key_status(st, TUE), "technique")
        assert tech["status"] == "partial"
        assert tech["progress"]["done"] == 1 and tech["progress"]["needed"] == 2
        assert [d["exercise_id"] for d in tech["progress"]["drills_done"]] == ["no_readjust_drill"]
        assert tech["progress"]["drills_missed"] == [{"exercise_id": "tech_hard_target", "name": "Hard Target"}]
        ref = tech["partial"][0]
        assert ref["date"] == MON and ref["dose_reason"] == "technique_drills"

    def test_two_drills_across_two_sessions_are_done(self):
        st = _st({MON: [_custom(["no_readjust_drill"])],
                  TUE: [_custom(["flag_practice"], listed=("flag_practice",))]})
        s = ks.compute_key_status(st, WED)
        tech = _req(s, "technique")
        assert tech["status"] == "done" and tech["debt"] == 0
        assert "progress" not in tech and s["topups"] == []

    def test_the_same_drill_twice_is_still_one(self):
        st = _st({MON: [_custom(["no_readjust_drill"])],
                  TUE: [_custom(["no_readjust_drill"], listed=("no_readjust_drill",))]})
        tech = _req(ks.compute_key_status(st, WED), "technique")
        assert tech["status"] == "partial" and tech["progress"]["done"] == 1

    def test_no_drill_done_is_missing_as_before(self):
        st = _st({MON: [_custom([])], TUE: [_host()]})
        s = ks.compute_key_status(st, TUE)
        tech = _req(s, "technique")
        assert tech["status"] == "missing" and "progress" not in tech and s["topups"] == []

    def test_one_session_rule_is_unchanged(self):
        cat = ks.load_exercise_catalog()
        assert ks.technique_drill_ids(_custom(["no_readjust_drill"]), cat) == ["no_readjust_drill"]
        assert not ks.technique_hit(_custom(["no_readjust_drill"]), cat)
        assert ks.technique_hit(_custom(["no_readjust_drill", "tech_hard_target"]), cat)

    def test_history_counts_a_week_of_split_drills(self):
        """Severity escalation: a week with two drills across two sessions is not an empty week."""
        cat = ks.load_exercise_catalog()
        st = _st({MON: [_custom(["no_readjust_drill"])],
                  TUE: [_custom(["flag_practice"], listed=("flag_practice",))]})
        days = ks._plan_days(st, None)
        assert ks._week_drill_count(days, date.fromisoformat(MON), cat) == 2
        assert ks._week_drill_count(days, date.fromisoformat("2026-09-21"), cat) == 0


class TestTopUp:
    def test_one_drill_short_adds_it_to_the_next_climbing_session(self):
        st = _st({MON: [_custom(["no_readjust_drill"])],
                  TUE: [_sess("lunch", "prehab_maintenance", location="gym", gym_id="g1"), _host()],
                  WED: [_host(sid="limit_boulder_gym")]})
        s = ks.compute_key_status(st, TUE)
        tech = _req(s, "technique")
        assert tech["resolution"] == "topup"
        assert tech["hint"] == "1 of 2 drills done — add Hard Target to Boulder circuit gym on 2026-10-06"
        assert not any("technique" in (p.get("keys") or [p.get("key")]) for p in s["proposals"])
        (t,) = s["topups"]
        assert (t["date"], t["slot"], t["session_index"], t["session_id"]) == (TUE, "evening", 1, "boulder_circuit_gym")
        assert t["exercise_id"] == "tech_hard_target" and t["from"]["date"] == MON
        assert t["apply"] == {"endpoint": "/api/session/add-exercise", "body": {
            "date": TUE, "session_index": 1, "exercise_id": "tech_hard_target",
            "position": "after_warmup", "prescription_override": {"sets": 4, "reps": 2}}}
        assert "add tech_hard_target to boulder_circuit_gym 10-06 evening" in ks.key_status_text(s)

    def test_no_topups_without_proposals(self):
        st = _st({MON: [_custom(["no_readjust_drill"])], TUE: [_host()]})
        s = ks.compute_key_status(st, TUE, with_proposals=False)
        assert s["topups"] == [] and _req(s, "technique")["resolution"] != "topup"

    def test_host_must_have_equipment_that_fits_the_drill(self):
        st = _st({MON: [_custom(["no_readjust_drill"])], TUE: [_host()], WED: [_host(sid="limit_boulder_gym")]})
        st["equipment"]["gyms"].append({"gym_id": "g2", "name": "Bar only", "priority": 2,
                                        "equipment": ["pullup_bar", "hangboard"]})
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][1]["sessions"][0]["gym_id"] = "g2"
        (t,) = ks.compute_key_status(st, TUE)["topups"]
        assert t["date"] == WED and t["session_id"] == "limit_boulder_gym"

    def test_a_past_or_done_session_is_never_the_host(self):
        st = _st({MON: [_custom(["no_readjust_drill"]), _host(slot="lunch")],
                  TUE: [_host(status="done")], WED: [_host()]})
        (t,) = ks.compute_key_status(st, TUE)["topups"]
        assert t["date"] == WED

    def test_falls_back_to_the_whole_session_when_no_host(self):
        st = _st({MON: [_custom(["no_readjust_drill"])],
                  TUE: [_sess("evening", "prehab_maintenance", location="gym", gym_id="g1")]})
        s = ks.compute_key_status(st, TUE)
        tech = _req(s, "technique")
        assert s["topups"] == [] and tech["resolution"] != "topup"
        assert tech["status"] == "partial" and tech["progress"]["done"] == 1

    def test_a_drill_that_was_not_listed_is_not_invented(self):
        st = _st({MON: [_custom(["no_readjust_drill"], listed=("no_readjust_drill",))], TUE: [_host()]})
        s = ks.compute_key_status(st, TUE)
        assert s["topups"] == [] and _req(s, "technique")["progress"]["drills_missed"] == []

    def test_intense_drills_are_not_topped_up(self):
        cat = ks.load_exercise_catalog()
        hard = next(k for k, v in cat.items()
                    if ks._counts_as_technique_drill(k, cat) and v.get("intensity_level") not in ks.TOPUP_INTENSITY)
        st = _st({MON: [_custom(["no_readjust_drill"], listed=("no_readjust_drill", hard))], TUE: [_host()]})
        assert ks.compute_key_status(st, TUE)["topups"] == []

    def test_added_by_hand_drill_makes_the_key_planned(self):
        st = _st({MON: [_custom(["no_readjust_drill"])], TUE: [_host()]})
        host = st["week_plans"]["2026-10-05"]["weeks"][0]["days"][1]["sessions"][0]
        host["resolved"]["resolved_session"]["exercise_instances"].insert(
            1, {"exercise_id": "tech_hard_target", "category": "technique", "source": "user_added"})
        s = ks.compute_key_status(st, TUE)
        tech = _req(s, "technique")
        assert tech["status"] == "planned" and tech["debt"] == 0 and s["topups"] == []
        assert tech["planned"][0]["date"] == TUE and tech["planned"][0]["topup"] is True

    def test_a_resolver_pick_is_not_a_promise(self):
        st = _st({MON: [_custom(["no_readjust_drill"])], TUE: [_host()]})
        host = st["week_plans"]["2026-10-05"]["weeks"][0]["days"][1]["sessions"][0]
        host["resolved"]["resolved_session"]["exercise_instances"].insert(
            1, {"exercise_id": "flag_practice", "category": "technique", "source": "resolver"})
        assert _req(ks.compute_key_status(st, TUE), "technique")["status"] == "partial"

    def test_topup_applies_through_the_endpoint_and_the_status_follows(self):
        st = _st({MON: [_custom(["no_readjust_drill"])], TUE: [_host()]})
        plan = st["week_plans"]["2026-10-05"]
        (t,) = ks.compute_key_status(st, TUE)["topups"]
        r = client.post(t["apply"]["endpoint"], json={**t["apply"]["body"], "week_plan": plan})
        assert r.status_code == 200, r.text
        new_plan = r.json()["week_plan"]
        inst = new_plan["weeks"][0]["days"][1]["sessions"][0]["resolved"]["resolved_session"]["exercise_instances"]
        assert [i["exercise_id"] for i in inst] == ["easy_climbing_warmup", "tech_hard_target", "boulder_circuit"]
        assert inst[1]["source"] == "user_added" and inst[1]["prescription"]["sets"] == 4
        st["week_plans"]["2026-10-05"] = new_plan
        s = ks.compute_key_status(st, TUE)
        assert _req(s, "technique")["status"] == "planned" and s["topups"] == []


class TestAddExercisePosition:
    def _plan(self):
        return _week(MON, {MON: [_host()]})

    def test_default_appends(self):
        r = client.post("/api/session/add-exercise", json={
            "date": MON, "session_index": 0, "exercise_id": "tech_hard_target", "week_plan": self._plan()})
        inst = r.json()["week_plan"]["weeks"][0]["days"][0]["sessions"][0]["resolved"]["resolved_session"]["exercise_instances"]
        assert inst[-1]["exercise_id"] == "tech_hard_target"

    def test_after_warmup_without_a_warmup_goes_first(self):
        plan = self._plan()
        plan["weeks"][0]["days"][0]["sessions"][0]["resolved"] = _resolved(MAIN)
        r = client.post("/api/session/add-exercise", json={
            "date": MON, "session_index": 0, "exercise_id": "tech_hard_target",
            "position": "after_warmup", "week_plan": plan})
        inst = r.json()["week_plan"]["weeks"][0]["days"][0]["sessions"][0]["resolved"]["resolved_session"]["exercise_instances"]
        assert [i["exercise_id"] for i in inst] == ["tech_hard_target", "boulder_circuit"]

    def test_edit_returns_the_key_status_for_the_card(self):
        """The card must refresh right after the tap: add/remove-exercise carry `key_status`."""
        r = client.post("/api/session/add-exercise", json={
            "date": MON, "session_index": 0, "exercise_id": "tech_hard_target",
            "position": "after_warmup", "today": MON, "week_plan": self._plan()})
        body = r.json()
        assert r.status_code == 200 and "key_status" in body
        inst = body["week_plan"]["weeks"][0]["days"][0]["sessions"][0]["resolved"]["resolved_session"]["exercise_instances"]
        idx = next(i for i, x in enumerate(inst) if x["exercise_id"] == "tech_hard_target")
        r2 = client.post("/api/session/remove-exercise", json={
            "date": MON, "session_index": 0, "exercise_index": idx, "today": MON,
            "week_plan": body["week_plan"]})
        assert r2.status_code == 200 and "key_status" in r2.json()

    def test_unknown_position_is_refused(self):
        r = client.post("/api/session/add-exercise", json={
            "date": MON, "session_index": 0, "exercise_id": "tech_hard_target",
            "position": "first", "week_plan": self._plan()})
        assert r.status_code == 422


class TestPlausibleDuration:
    def test_bound(self):
        assert plausible_duration(5400) == 5400
        assert plausible_duration(MAX_SESSION_DURATION_S) == MAX_SESSION_DURATION_S
        assert plausible_duration(37555) is None  # 10 h 26 min, 2026-11-09
        assert plausible_duration(None) is None and plausible_duration(True) is None

    def test_keep_longest_never_keeps_an_implausible_stored_value(self):
        assert keep_longest(1800, 32) == 1800 and keep_longest(600, 2400) == 2400
        assert keep_longest(37555, 5400) == 5400
        assert keep_longest(None, 5400) == 5400

    def _seed(self):
        wp = {"start_date": "2026-04-06", "weeks": [{"phase": "base", "days": [{
            "date": "2026-04-06", "weekday": "mon", "sessions": [{
                "session_id": "strength_long", "slot": "evening",
                "resolved": {"resolved_session": {"exercise_instances": []}}}]}]}]}
        state = deps.load_state(None)
        state["current_week_plan"] = deepcopy(wp)
        state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
        state["session_completion_log"] = []
        state["feedback_log"] = []
        deps.save_state(state, None)

    def _post(self, seconds):
        return client.post("/api/feedback", json={"log_entry": {
            "date": "2026-04-06", "session_id": "strength_long", "session_duration_seconds": seconds,
            "actual": {"exercise_feedback_v1": [{"exercise_id": "ex_a", "feedback_label": "ok"}]}}})

    def _stored(self):
        state = deps.load_state(None)
        sess = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        return (state["session_completion_log"][0].get("session_duration_seconds"),
                state["feedback_log"][0].get("session_duration_seconds"),
                sess.get("session_duration_seconds"), sess.get("status"))

    def test_a_player_left_open_overnight_saves_no_duration(self):
        self._seed()
        assert self._post(37555).status_code == 200
        assert self._stored() == (None, None, None, "done")

    def test_a_corrected_duration_replaces_a_stored_implausible_one(self):
        self._seed()
        assert self._post(1800).status_code == 200
        state = deps.load_state(None)
        state["session_completion_log"][0]["session_duration_seconds"] = 37555
        state["feedback_log"][0]["session_duration_seconds"] = 37555
        state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]["session_duration_seconds"] = 37555
        state["week_plans"]["2026-04-06"] = deepcopy(state["current_week_plan"])
        deps.save_state(state, None)
        assert self._post(5400).status_code == 200
        assert self._stored() == (5400, 5400, 5400, "done")
