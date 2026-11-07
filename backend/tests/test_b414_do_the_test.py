"""B414 (B414-3) — "Do the test": the athlete's request, through the policy.

Decision of Daniele (2026-11-07): "Do the test" mid-cycle is placed as the
athlete's request THROUGH the retest policy — a new record kind in
``retest_declines`` (``kind: request``, additive schema change approved; every
reader of the list filters by kind, one test per reader) — on the first day
the guards allow, never within 72 h of a max, in any phase. Plus A246: the
"Schedule test week" confirm now really places the tests (next week), and the
reminder's deferrals reset with a new cycle.

Covered:
- engine: trigger ``requested`` from the request day (gap kept), in
  performance too, not in a deload (hard cap 0: never projected), not after
  the end of the macrocycle; the planner places it on an allowed day (72 h
  rule); the request wins over a test removed BEFORE it, not over one removed
  from its day on; a new test makes it inert;
- every reader of ``retest_declines`` and the kind: ``axis_declines``,
  ``_postponed_until``, ``upsert`` (latest word wins both ways), ``remove``
  (DELETE keeps a request), the import, the athlete-context lines;
- API ``POST /api/retest/request``: already planned / projected (no write),
  cycle ended (no write), requested (record, stale week, dry run, pause,
  not covered), past sessions byte for byte through the regeneration;
- A246: the confirm names next Monday and that week's generation injects the
  tests mid-cycle; start-new-cycle drops the old deferrals.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import athlete_context as ac
from backend.engine import retest_declines as rd
from backend.engine import retest_policy as rp
from backend.engine.planner_v2 import generate_phase_week
from backend.tests import test_a289_retest_policy as a289

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
OFFICIAL = "2026-09-24"


def _req(day: str, axis: str = "finger", **over) -> dict:
    rec = {"axis": axis, "kind": rp.DECLINE_KIND_REQUEST, "trigger": rp.TRIGGER_REQUESTED,
           "official_date": OFFICIAL, "macrocycle_start": "2026-09-07", "requested_at": day, "source": "app"}
    rec.update(over)
    return rec


def _daniele(*recs) -> dict:
    """Tests of 24/09 (gap to 05/11); macrocycle from 07/09: PE 19/10-08/11,
    performance 09-29/11, deload 30/11-06/12."""
    st = a289._daniele()
    if recs:
        st[rp.DECLINES_KEY] = [dict(r) for r in recs]
    return st


def _axis(st: dict, ws: str, today: str = None, axis: str = "finger") -> dict:
    return a289._decision(st, ws, today=today or ws)["axes"][axis]


# ---------------------------------------------------------------------------
# Engine — the trigger
# ---------------------------------------------------------------------------

class TestTrigger:
    def test_without_a_request_nothing_is_due_in_performance(self):
        assert _axis(_daniele(), "2026-11-09")["status"] == "not_due"

    def test_a_request_is_due_from_its_day_in_performance(self):
        f = _axis(_daniele(_req("2026-11-11")), "2026-11-09", today="2026-11-11")
        assert (f["status"], f["trigger"], f["first_date"], f["allowed_dates"][0]) == (
            "due", rp.TRIGGER_REQUESTED, "2026-11-11", "2026-11-11")
        assert f["reason"] == "You asked for this test."
        # A week before the request day has no request yet.
        assert _axis(_daniele(_req("2026-11-17")), "2026-11-09")["status"] == "not_due"
        # Every later week of the cycle keeps it due until the test is logged.
        later = _axis(_daniele(_req("2026-11-11")), "2026-11-16")
        assert (later["status"], later["trigger"]) == ("due", rp.TRIGGER_REQUESTED)

    def test_the_gap_after_the_last_test_still_applies(self):
        # Requested on 27/10 (PE): the gap holds the test until 05/11.
        st = _daniele(_req("2026-10-27"))
        f = _axis(st, "2026-10-26", today="2026-10-27")
        assert (f["status"], f["skip_reason"], f["trigger"]) == ("skipped", "blocked:gap", rp.TRIGGER_REQUESTED)
        f = _axis(st, "2026-11-02", today="2026-11-02")
        assert (f["status"], f["first_date"]) == ("due", "2026-11-05")

    def test_not_in_a_deload_and_not_after_the_cycle(self):
        st = _daniele(_req("2026-11-30"))
        f = _axis(st, "2026-11-30")
        assert (f["status"], f["skip_reason"]) == ("skipped", "blocked:phase")
        assert _axis(st, "2026-12-07")["status"] == "not_due"
        row = rp.retest_status(st, "2026-11-30", finger_device="hangboard")["axes"]["finger"]
        assert (row["next_test"], row["next_test_reason"]) == (None, "blocked:phase")
        assert row["request"] == {"requested_at": "2026-11-30", "source": "app"}

    def test_the_planner_places_it_on_an_allowed_day_never_within_72_h(self):
        st = _daniele(_req("2026-11-09"), _req("2026-11-09", axis="pulling"))
        dec = a289._decision(st, "2026-11-09", today="2026-11-09")
        assert [r["trigger"] for r in dec["required_sessions"]] == [rp.TRIGGER_REQUESTED] * 2
        plan = generate_phase_week(**a289._kwargs("performance", "2026-11-09", retest_decisions=dec))
        days = a289._test_days(plan)
        placed = {sid: d for sid, (d, _slot) in days.items()
                  if sid in ("test_max_hang_7s", "test_max_hang_pullup")}
        assert placed, days
        # A finger-hard day on Tuesday 10/11 keeps the hang test off 11-12/11.
        dec2 = deepcopy(dec)
        dec2["finger_hard_dates"] = ["2026-11-10"]
        for r in dec2["required_sessions"]:
            r["allowed_dates"] = ["2026-11-11", "2026-11-12", "2026-11-13"]
        plan2 = generate_phase_week(**a289._kwargs("performance", "2026-11-09", retest_decisions=dec2))
        for sid, (d, _slot) in a289._test_days(plan2).items():
            if sid in ("test_max_hang_7s", "test_max_hang_pullup"):
                assert d >= "2026-11-13", (sid, d)
        snap = plan["profile_snapshot"]["retest_decisions"]["required_sessions"]
        assert {r["trigger"] for r in snap} == {rp.TRIGGER_REQUESTED}

    def test_the_request_wins_over_a_test_removed_before_it_not_after(self):
        def plan(removed_on: str) -> dict:
            return {"start_date": "2026-11-09", "weeks": [{"days": [
                {"date": f"2026-11-{d:02d}", "sessions": []} for d in range(9, 16)]}],
                "adaptations": [{"type": "event", "event": {
                    "event_type": "remove_session", "date": removed_on, "session_ref": "test_max_hang_7s",
                    "slot": "evening"}}]}

        before = _daniele(_req("2026-11-11"))
        before["week_plans"] = {"2026-11-09": plan("2026-11-10")}
        f = _axis(before, "2026-11-09", today="2026-11-11")
        assert (f["status"], f["trigger"]) == ("due", rp.TRIGGER_REQUESTED)
        after = _daniele(_req("2026-11-11"))
        after["week_plans"] = {"2026-11-09": plan("2026-11-12")}
        f = _axis(after, "2026-11-09", today="2026-11-11")
        assert (f["status"], f["skip_reason"], f["declined"]["source"]) == (
            "skipped", rp.SKIP_DECLINED, rp.DECLINE_SOURCE_PLAN_EDIT)

    def test_a_new_test_makes_the_request_inert(self):
        st = _daniele(_req("2026-11-09"))
        st["tests"]["max_strength"].append({"date": "2026-11-11", "test_id": "max_hang_7s_total_load",
                                            "total_load_kg": 118.0, "bodyweight_kg": 77.0})
        assert rp.axis_request(st, "finger", rp.axis_official(st, "finger", "2026-11-16")) is None
        assert _axis(st, "2026-11-16")["status"] == "not_due"


# ---------------------------------------------------------------------------
# Every reader of retest_declines filters by kind
# ---------------------------------------------------------------------------

class TestReaders:
    def test_axis_declines_ignores_a_request(self):
        st = _daniele(_req("2026-11-09"))
        assert rp.axis_declines(st, "finger", {"date": OFFICIAL}) == []
        row = rp.retest_status(st, "2026-11-09", finger_device="hangboard")["axes"]["finger"]
        assert row["declines"] == [] and row["request"]["requested_at"] == "2026-11-09"

    def test_a_request_never_extends_the_validity(self):
        st = _daniele(_req("2026-11-09", until="2027-02-01"))
        om = rp.official_max(st, rp.PROTOCOL_HANG_7S, "2026-12-20")
        assert (om["valid_until"], om["extended"]) == ("2026-12-22", False)

    def test_upsert_the_latest_word_wins_both_ways(self):
        st = _daniele()
        post = {"axis": "finger", "kind": "postpone", "trigger": "expiry", "official_date": OFFICIAL,
                "macrocycle_start": "2026-09-07", "until": "2027-01-10", "reason": "schedule",
                "declined_at": "2026-11-01", "source": "app", "previous_until": None}
        st[rp.DECLINES_KEY] = [post]
        req = rd.build_request(st, "finger", status_row={"covered": True, "test_date": OFFICIAL},
                               today="2026-11-09")
        assert rd.upsert(st, req, today="2026-11-09") == post
        assert st[rp.DECLINES_KEY] == [req]
        # A decline after it ends the request.
        dec = dict(post, kind="decline", trigger="maintenance", until=None, declined_at="2026-11-10")
        dec.pop("previous_until")
        assert rd.upsert(st, dec, today="2026-11-10") == req
        assert st[rp.DECLINES_KEY] == [dec]

    def test_axis_request_yields_to_a_later_decline_kept_by_an_import(self):
        dec = {"axis": "finger", "kind": "decline", "trigger": "maintenance", "official_date": OFFICIAL,
               "declined_at": "2026-11-12", "reason": "fatigue"}
        st = _daniele(_req("2026-11-10"), dec)
        assert rp.axis_request(st, "finger", {"date": OFFICIAL}) is None
        st = _daniele(dict(dec, declined_at="2026-11-08"), _req("2026-11-10"))
        assert rp.axis_request(st, "finger", {"date": OFFICIAL})["requested_at"] == "2026-11-10"

    def test_remove_keeps_the_request(self):
        post = {"axis": "finger", "kind": "postpone", "official_date": OFFICIAL, "until": "2027-01-10"}
        st = _daniele(_req("2026-11-09"), post, _req("2026-11-09", axis="pulling"))
        assert rd.remove(st, "finger") == [post]
        assert [r["kind"] for r in st[rp.DECLINES_KEY]] == ["request", "request"]
        assert rd.remove(st, "finger") == []

    def test_the_athlete_context_lines_skip_the_request(self):
        st = _daniele(_req("2026-11-09"))
        ctx = ac.build_athlete_context(st, "2026-11-09", with_proposals=False, include_next_week=False)
        text = ac.render_text(ctx)
        assert "RINVIATO" not in text and "RIFIUTATO" not in text
        assert "retest declined" not in ac.render_coach_block(ctx)

    def test_build_request_errors(self):
        for kw, code in (({"axis": "toes"}, "unknown_axis"), ({"source": "web"}, "invalid_source"),
                         ({"status_row": {"covered": False}}, "not_covered"), ({"status_row": None}, "not_covered")):
            args = {"axis": "finger", "status_row": {"covered": True, "test_date": OFFICIAL}, **kw}
            with pytest.raises(rd.DeclineError) as err:
                rd.build_request(_daniele(), args.pop("axis"), today="2026-11-09", **args)
            assert err.value.code == code


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.fixture
def api(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(FIXTURE_STATE, tmp_state)
    from backend.engine import storage, storage_file

    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_state


def _mon(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _seed(*, test_age: int, start_weeks_ago: int, phases=None) -> dict:
    today = date.today()
    state = deps.load_state(None)
    state["macrocycle"] = {"start_date": (_mon(today) - timedelta(weeks=start_weeks_ago)).isoformat(),
                           "phases": phases or [
                               {"phase_id": "base", "duration_weeks": 2},
                               {"phase_id": "strength_power", "duration_weeks": 4},
                               {"phase_id": "power_endurance", "duration_weeks": 3},
                               {"phase_id": "performance", "duration_weeks": 3},
                               {"phase_id": "deload", "duration_weeks": 1}]}
    t = (today - timedelta(days=test_age)).isoformat()
    state["tests"] = {
        "max_strength": [{"date": t, "test_id": "max_hang_7s_total_load", "total_load_kg": 110.0,
                          "bodyweight_kg": 77.0}],
        "pulling_strength": [{"date": t, "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 115.0,
                              "estimated_1rm_kg": 120.5, "bodyweight_kg": 77.0}],
    }
    state["preferences"] = {"finger_training_device": "hangboard"}
    last = _mon(today) - timedelta(weeks=1)
    state["week_plans"] = {last.isoformat(): {"start_date": last.isoformat(), "weeks": [{"days": [
        {"date": last.isoformat(), "sessions": [{"session_id": "strength_long", "status": "done",
                                                 "slot": "evening"}]}]}]}}
    state["current_week_plan"] = None
    state["equipment"]["home"] = ["hangboard", "pullup_bar", "dumbbell", "band"]
    state["availability"] = {wd: {s: {"available": True, "preferred_location": "home"}
                                  for s in ("morning", "lunch", "evening")}
                             for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    state.pop(rp.DECLINES_KEY, None)
    deps.save_state(state, None)
    return state


def _past() -> str:
    mon = _mon(date.today()).isoformat()
    st = deps.load_state(None)
    return json.dumps({k: v for k, v in (st.get("week_plans") or {}).items() if k < mon}, sort_keys=True)


#: A 20-week cycle of one strength_power phase: no phase block, nothing natural
#: due while the test is fresh (end of SP / maintenance fall outside).
_LONG_SP = [{"phase_id": "strength_power", "duration_weeks": 20}]


class TestApi:
    def test_request_writes_the_record_and_the_regeneration_places_the_test(self, api):
        # Test 50 days ago (gap passed, maintenance at 84 d not reached).
        _seed(test_age=50, start_weeks_ago=4, phases=_LONG_SP)
        client.get("/api/week/0")  # the current week cached
        past = _past()
        r = client.post("/api/retest/request", json={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] == "requested"
        assert [x["kind"] for x in body["requests"]] == ["request", "request"]
        assert body["weeks_marked_stale"] == [_mon(date.today()).isoformat()]
        stored = deps.load_state(None)[rp.DECLINES_KEY]
        assert {x["axis"] for x in stored} == {"finger", "pulling"}
        # The regeneration of the current week places the test (or the pair).
        week = client.get("/api/week/0").json()
        tests = [s["session_id"] for d in week["week_plan"]["weeks"][0]["days"] for s in d["sessions"]
                 if str(s["session_id"]).startswith("test_max")]
        reasons = {a: row.get("next_test_reason") for a, row in week["retest_status"]["axes"].items()}
        assert tests or set(reasons.values()) <= {"no_placement_slot", "blocked:no_paired_slot"}, (tests, reasons)
        assert _past() == past
        # Asked again with the test in the plan: nothing written, the day named.
        if tests:
            raw = api.read_bytes()
            again = client.post("/api/retest/request", json={})
            assert again.json()["action"] == "already_planned" and again.json()["go_to"]
            assert api.read_bytes() == raw

    def test_dry_run_pause_and_not_covered(self, api):
        _seed(test_age=50, start_weeks_ago=4, phases=_LONG_SP)
        client.post("/api/retest/request", json={"dry_run": True})  # settles the fixture migrations
        raw = api.read_bytes()
        r = client.post("/api/retest/request", json={"dry_run": True, "axes": ["finger"]})
        assert r.status_code == 200, r.text
        assert r.json()["action"] == "requested" and api.read_bytes() == raw
        state = deps.load_state(None)
        state["macrocycle"]["pause"] = {"active_since": date.today().isoformat()}
        deps.save_state(state, None)
        assert client.post("/api/retest/request", json={}).status_code == 409
        state = deps.load_state(None)
        state["macrocycle"].pop("pause")
        state["preferences"] = {"finger_training_device": "loading_pin"}
        deps.save_state(state, None)
        r = client.post("/api/retest/request", json={"axes": ["finger"]})
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "not_covered")

    def test_cycle_ended_writes_nothing(self, api):
        _seed(test_age=95, start_weeks_ago=20)
        client.post("/api/retest/request", json={"dry_run": True})
        raw = api.read_bytes()
        r = client.post("/api/retest/request", json={})
        assert r.status_code == 200, r.text
        assert (r.json()["action"], r.json()["go_to"]) == ("cycle_ended", None)
        assert api.read_bytes() == raw


# ---------------------------------------------------------------------------
# A246 — "Schedule test week" really schedules; deferrals reset per cycle
# ---------------------------------------------------------------------------

class TestA246:
    def test_the_confirm_names_next_week_and_its_generation_injects_the_tests(self, api):
        today = date.today()
        nxt = (_mon(today) + timedelta(weeks=1)).isoformat()
        state = _seed(test_age=50, start_weeks_ago=8, phases=_LONG_SP)
        state["tests"] = {}  # untested: the reminder's own population
        deps.save_state(state, None)
        cur = client.get("/api/week/0").json()["week_num"]
        r = client.post("/api/week/test-reminder-response", json={"option": "confirm"})
        assert r.status_code == 200, r.text
        assert deps.load_state(None)["initial_tests_requested"] == nxt
        week = client.get(f"/api/week/{cur + 1}").json()["week_plan"]
        assert week["start_date"] == nxt
        tests = [s["session_id"] for d in week["weeks"][0]["days"] for s in d["sessions"]
                 if str(s["session_id"]).startswith("test_")]
        assert tests, "the confirm mid-cycle must place the tests next week"
        # The week after is not a test week: the flag named only that one.
        later = client.get(f"/api/week/{cur + 2}").json()["week_plan"]
        assert not [s for d in later["weeks"][0]["days"] for s in d["sessions"]
                    if str(s["session_id"]).startswith("test_max") and s.get("status") != "done"]

    def test_start_new_cycle_drops_the_old_deferrals(self, api):
        from backend.tests.test_start_new_macrocycle import _valid_body

        state = deps.load_state(None)
        state["test_reminder_skipped_until"] = 18
        state["test_reminder_postponed_to"] = 12
        deps.save_state(state, None)
        r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
        assert r.status_code == 200, r.text
        state = deps.load_state(None)
        assert "test_reminder_skipped_until" not in state and "test_reminder_postponed_to" not in state
        assert state["initial_tests_requested"] is True
