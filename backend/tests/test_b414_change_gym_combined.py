"""B414 (step 17, A319-CHANGE-GYM) — a change of gym on a combined-test day
keeps its max hang where the hangboard is.

Before B414 ``change_gym`` compared the combined test's catalog equipment
(hangboard + pull-up bar + weight) with the new gym and, missing the weights,
replaced the whole session with complementary_conditioning: the max hang went
too although the gym has a hangboard (``lost_finger``), and the retest stamp
was gone. Decided by Daniele (2026-11-07): the combined moved to a gym without
weights becomes the hang alone, the pull-up waits for its next turn — never
the 2RM alone. The check is on equipment only, never on the catalog location.

Linked fixes of the same step:
- the dry run of /events (``build_key_conflicts``) and ``_simulate_add`` pass
  the athlete's gyms and home kit: a change_gym in the dry run used to replace
  every session that needs equipment, even towards the same gym;
- "change location → home" checks the saved home kit (``state.equipment.home``)
  when the event carries none (the app never sends one) — for every user;
- the retest card reads ``blocked:no_paired_slot`` for the pull-up of a
  combined turned into the hang alone (``_generated_week_skip``), not
  ``not_in_plan``, and never "planned".

Synthetic fixtures only.
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
from backend.engine import key_sessions_v1 as ks
from backend.engine import retest_policy as rp
from backend.engine.replanner_v1 import apply_events
from backend.engine.resolve_session import resolve_session
from backend.tests.test_a289_retest_policy import _due_1019

REPO = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO / "backend" / "data" / "user_state.json"
client = TestClient(app)

WS = "2026-10-19"
MON, TUE, WED, THU, FRI, SAT, SUN = ((date.fromisoformat(WS) + timedelta(days=i)).isoformat() for i in range(7))
HANG, PULL, COMBO = "test_max_hang_7s", "test_max_weighted_pullup", "test_max_hang_pullup"
REASON = "End of the strength phase: measure what the block built."

GYMS = [
    {"gym_id": "cocque", "name": "Cocque", "equipment": ["spraywall", "gym_routes", "hangboard", "pullup_bar"]},
    {"gym_id": "bkl", "name": "Bkl", "equipment": ["hangboard", "gym_boulder", "pullup_bar", "dumbbell"]},
    {"gym_id": "work", "name": "Work", "equipment": ["barbell", "bench", "dumbbell", "pullup_bar"]},
    {"gym_id": "wall", "name": "Wall", "equipment": ["gym_boulder", "pullup_bar"]},
]

COMBO_EXPLAIN = ["pass3:retest_policy", "retest:finger:end_of_phase", REASON,
                 "retest:pulling:end_of_phase", REASON]


def _combo(status: str = "planned", **kw) -> dict:
    s = {"slot": "evening", "session_id": COMBO, "location": "gym", "gym_id": "bkl", "status": status,
         "intensity": "high", "tags": {"hard": True, "finger": True, "test": True},
         "constraints_applied": ["pass3:retest_policy"], "explain": list(COMBO_EXPLAIN)}
    s.update(kw)
    return s


def _lunch() -> dict:
    return {"slot": "lunch", "session_id": "complementary_conditioning", "location": "home", "gym_id": None,
            "status": "planned", "intensity": "low", "tags": {"hard": False, "finger": False}}


def _plan(sessions_by_date: dict, snapshot=None) -> dict:
    days = [{"date": d, "sessions": deepcopy(sessions_by_date.get(d, []))}
            for d in (MON, TUE, WED, THU, FRI, SAT, SUN)]
    return {"start_date": WS, "plan_revision": 1, "weeks": [{"week_index": 1, "days": days}],
            "profile_snapshot": {"phase_id": "strength_power", **({"retest_decisions": snapshot} if snapshot else {})},
            "adaptations": []}


def _snapshot() -> dict:
    return {"required_sessions": [
        {"axis": axis, "session_id": COMBO, "trigger": rp.TRIGGER_END_OF_PHASE, "reason": REASON,
         "status": "placed", "placed_date": FRI, "placed_slot": "evening", "combined": True, "order": order}
        for axis, order in (("finger", 1), ("pulling", 2))
    ]}


def _change(plan: dict, gym_id=None, location: str = "gym", **kw) -> dict:
    ev = {"event_type": "change_gym", "date": FRI, "location": location}
    if gym_id:
        ev["gym_id"] = gym_id
    return apply_events(plan, [ev], gyms=GYMS, **kw)


def _fri(plan: dict) -> list:
    return next(d for d in plan["weeks"][0]["days"] if d["date"] == FRI)["sessions"]


def _evening(plan: dict) -> dict:
    return next(s for s in _fri(plan) if s["slot"] == "evening")


def _adaptation(plan: dict) -> dict:
    return next(a for a in plan["adaptations"] if a.get("type") == "change_gym")


def _unchanged_except(before: dict, after: dict, dates: set) -> None:
    for b, a in zip(before["weeks"][0]["days"], after["weeks"][0]["days"]):
        if b["date"] not in dates:
            assert a == b, f"{b['date']} was rewritten"


class TestCombinedKeepsItsHang:
    def test_gym_with_hangboard_without_weights_gives_the_hang_alone(self):
        plan = _plan({FRI: [_combo()]})
        out = _change(plan, "cocque")
        s = _evening(out)
        assert (s["session_id"], s["location"], s["gym_id"]) == (HANG, "gym", "cocque")
        assert s["tags"] == {"hard": True, "finger": True, "test": True}
        assert s["intensity"] == "high" and "resolved" not in s
        # The policy's finger stamp stays (single-axis form); the pull-up's goes.
        assert s["explain"] == [f"gym_change: {COMBO} → {HANG}", "missing_equipment={'weight'}",
                                "retest:end_of_phase"]
        assert rp.is_policy_test(s)
        assert not any(e.startswith("retest:pulling") or e.startswith("retest:finger") for e in s["explain"])
        a = _adaptation(out)
        assert "lost_finger" not in a
        assert a["warnings"] == [f"{COMBO} → {HANG} (missing_equipment={{'weight'}}): "
                                 "the pull-up test waits for its next turn"]
        assert not any("finger session lost" in w for w in a["warnings"])

    def test_each_finger_trigger_keeps_its_own_stamp(self):
        explain = ["pass3:retest_policy", "retest:finger:early_retest", "x", "retest:pulling:end_of_phase", "y"]
        out = _change(_plan({FRI: [_combo(explain=explain)]}), "cocque")
        assert _evening(out)["explain"][2:] == ["retest:early_retest"]

    def test_a_combined_the_policy_did_not_place_gets_no_stamp(self):
        out = _change(_plan({FRI: [_combo(explain=["quick_add"], constraints_applied=["quick_add"])]}), "cocque")
        s = _evening(out)
        assert s["session_id"] == HANG and not rp.is_policy_test(s)
        assert s["constraints_applied"] == ["quick_add"]  # still the user's (is_user_owned)

    def test_gym_without_hangboard_loses_the_finger_session_as_before(self):
        out = _change(_plan({FRI: [_combo()]}), "wall")
        assert _evening(out)["session_id"] == "complementary_conditioning"
        assert _adaptation(out).get("lost_finger") is True

    def test_weights_without_hangboard_never_give_the_2rm_alone(self):
        out = _change(_plan({FRI: [_combo()]}), "work")
        assert _evening(out)["session_id"] == "complementary_conditioning"
        assert _adaptation(out).get("lost_finger") is True

    def test_gym_with_everything_keeps_the_combined(self):
        out = _change(_plan({FRI: [_combo(gym_id="cocque")]}), "bkl")  # dumbbell implies weight
        s = _evening(out)
        assert (s["session_id"], s["gym_id"], s["explain"]) == (COMBO, "bkl", COMBO_EXPLAIN)

    def test_unknown_gym_still_downshifts(self):
        out = _change(_plan({FRI: [_combo()]}), "nowhere")
        assert _evening(out)["session_id"] == "complementary_conditioning"

    @pytest.mark.parametrize("status", ["done", "skipped"])
    def test_done_or_skipped_combined_is_never_touched(self, status):
        plan = _plan({FRI: [_combo(status)]})
        out = _change(plan, "cocque")
        assert _fri(out) == _fri(plan)

    def test_other_days_and_the_other_slot_are_byte_identical(self):
        plan = _plan({TUE: [_combo("done", gym_id="bkl")], FRI: [_lunch(), _combo()], SUN: [_combo()]})
        out = _change(plan, "cocque")
        _unchanged_except(plan, out, {FRI})
        # The whole day moves (no slot in the event): the lunch needs nothing.
        lunch = next(s for s in _fri(out) if s["slot"] == "lunch")
        assert (lunch["session_id"], lunch["gym_id"]) == ("complementary_conditioning", "cocque")

    def test_deterministic(self):
        plan = _plan({FRI: [_combo()]})
        a, b = _change(deepcopy(plan), "cocque"), _change(deepcopy(plan), "cocque")
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


class TestChangeToHome:
    def test_saved_home_kit_without_weights_gives_the_hang(self):
        out = _change(_plan({FRI: [_combo()]}), location="home", home_equipment=["hangboard", "pullup_bar"])
        s = _evening(out)
        assert (s["session_id"], s["location"], s["gym_id"]) == (HANG, "home", None)
        assert _adaptation(out).get("lost_finger") is None

    def test_saved_home_kit_with_weights_keeps_the_combined(self):
        out = _change(_plan({FRI: [_combo()]}), location="home",
                      home_equipment=["hangboard", "pullup_bar", "dumbbell"])
        assert _evening(out)["session_id"] == COMBO

    def test_empty_saved_home_kit_is_known_empty(self):
        out = _change(_plan({FRI: [_combo()]}), location="home", home_equipment=[])
        assert _evening(out)["session_id"] == "complementary_conditioning"
        assert _adaptation(out).get("lost_finger") is True

    def test_no_home_kit_anywhere_is_unknown_as_before(self):
        out = _change(_plan({FRI: [_combo()]}), location="home")
        assert (_evening(out)["session_id"], _evening(out)["location"]) == (COMBO, "home")

    def test_the_event_kit_wins_over_the_saved_one(self):
        plan = _plan({FRI: [_combo()]})
        ev = {"event_type": "change_gym", "date": FRI, "location": "home",
              "home_equipment": ["hangboard", "pullup_bar", "dumbbell"]}
        out = apply_events(plan, [ev], gyms=GYMS, home_equipment=["hangboard"])
        assert _evening(out)["session_id"] == COMBO


class TestRetestStatusAfterTheChange:
    def _state(self, plan: dict) -> dict:
        st = _due_1019()
        st["week_plans"] = {WS: plan}
        st.setdefault("equipment", {})["gyms"] = deepcopy(GYMS)
        return st

    def test_before_the_change_both_axes_are_planned(self):
        st = self._state(_plan({FRI: [_combo()]}, snapshot=_snapshot()))
        axes = rp.retest_status(st, WS, finger_device="hangboard")["axes"]
        assert {a: axes[a]["next_test"]["source"] for a in ("finger", "pulling")} == \
            {"finger": "planned", "pulling": "planned"}

    def test_pull_up_waits_hang_stays_planned(self):
        plan = _change(_plan({FRI: [_combo()]}, snapshot=_snapshot()), "cocque")
        st = self._state(plan)
        axes = rp.retest_status(st, WS, finger_device="hangboard")["axes"]
        nt = axes["finger"]["next_test"]
        assert (nt["source"], nt["date"], nt["session_id"]) == ("planned", FRI, HANG)
        pull = axes["pulling"]
        assert (pull["next_test"] or {}).get("source") != "planned"
        assert rp._generated_week_skip(st, "pulling", date.fromisoformat(WS), date.fromisoformat(WS)) \
            == rp.SKIP_NO_PAIRED_SLOT == "blocked:no_paired_slot"
        # (next_test_reason is the LAST skip of the projection — later weeks.)

    def test_a_week_without_the_swap_still_reads_not_in_plan(self):
        # Non-vacuity: the snapshot row alone (the slot holds something else).
        plan = _plan({FRI: [_lunch()]}, snapshot=_snapshot())
        st = self._state(plan)
        assert rp._generated_week_skip(st, "pulling", date.fromisoformat(WS), date.fromisoformat(WS)) == "not_in_plan"

    def test_the_hang_alone_resolves_at_the_gym_without_weights(self):
        plan = _change(_plan({FRI: [_combo()]}, snapshot=_snapshot()), "cocque")
        s = _evening(plan)
        state = {"context": {"location": "gym", "gym_id": "cocque"},
                 "equipment": {"gyms": [{**GYMS[0], "priority": 1}], "home": []},
                 "defaults": {"location": "gym"}}
        r = resolve_session(
            repo_root=str(REPO), session_path=f"backend/catalog/sessions/v1/{s['session_id']}.json",
            templates_dir="backend/catalog/templates", exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="", user_state_override=state, write_output=False, user_id=None,
        )
        ids = [i["exercise_id"] for i in r["resolved_session"]["exercise_instances"]]
        assert "max_hang_7s" in ids and "weighted_pullup" not in ids
        assert r["resolution_status"] == "success"


class TestDryRunMatchesTheWrite:
    def _state(self, plan: dict) -> dict:
        st = _due_1019()
        st["week_plans"] = {WS: deepcopy(plan)}
        st["equipment"] = {"gyms": deepcopy(GYMS), "home": ["hangboard", "pullup_bar"]}
        return st

    @pytest.mark.parametrize("ev", [
        {"event_type": "change_gym", "date": FRI, "location": "gym", "gym_id": "bkl"},     # same gym
        {"event_type": "change_gym", "date": FRI, "location": "gym", "gym_id": "cocque"},  # hang alone
        {"event_type": "change_gym", "date": FRI, "location": "home"},                    # saved home kit
    ])
    def test_check_insertion_plan_equals_the_real_write(self, ev):
        plan = _plan({FRI: [_combo()]}, snapshot=_snapshot())
        st = self._state(plan)
        dry = ks.check_insertion(st, WS, plan=deepcopy(plan), events=[deepcopy(ev)], archived_weeks=[])
        real = apply_events(deepcopy(plan), [deepcopy(ev)], gyms=st["equipment"]["gyms"],
                            home_equipment=st["equipment"]["home"], today=WS)
        assert _fri(dry["week_plan"]) == _fri(real)

    def test_same_gym_replaces_nothing_in_the_dry_run(self):
        plan = _plan({FRI: [_combo()]}, snapshot=_snapshot())
        ev = {"event_type": "change_gym", "date": FRI, "location": "gym", "gym_id": "bkl"}
        dry = ks.check_insertion(self._state(plan), WS, plan=deepcopy(plan), events=[ev], archived_weeks=[])
        assert _evening(dry["week_plan"])["session_id"] == COMBO


# ---------------------------------------------------------------------------
# API: the router passes the saved home kit
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


class TestApi:
    def _seed(self, home: list) -> tuple:
        mon = _current_monday()
        fri = (date.fromisoformat(mon) + timedelta(days=4)).isoformat()
        days = [{"date": (date.fromisoformat(mon) + timedelta(days=i)).isoformat(), "sessions": []} for i in range(7)]
        days[4]["sessions"] = [_combo()]
        plan = {"start_date": mon, "plan_revision": 1, "weeks": [{"week_index": 1, "days": days}],
                "profile_snapshot": {"phase_id": "strength_power"}, "adaptations": []}
        state = deps.load_state(None)
        state.setdefault("week_plans", {})[mon] = deepcopy(plan)
        state.pop("macrocycle_paused", None)
        state["equipment"] = {"gyms": deepcopy(GYMS), "home": list(home), "home_enabled": True}
        deps.save_state(state, None)
        return mon, fri, plan

    def _post(self, plan: dict, mon: str, fri: str, dry_run: bool = False) -> dict:
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "today": mon, "dry_run": dry_run,
            "events": [{"event_type": "change_gym", "date": fri, "location": "home"}],
        })
        assert r.status_code == 200, r.text
        return r.json()

    def test_change_to_home_reads_the_saved_kit(self, isolated_state):
        mon, fri, plan = self._seed(["hangboard", "pullup_bar"])
        dry = self._post(plan, mon, fri, dry_run=True)
        body = self._post(plan, mon, fri)
        for wp in (dry["week_plan"], body["week_plan"]):
            s = next(s for s in wp["weeks"][0]["days"][4]["sessions"] if s["slot"] == "evening")
            assert (s["session_id"], s["location"]) == (HANG, "home")
        assert any("the pull-up test waits" in w for w in body["warnings"])
        assert not any("finger session lost" in w for w in body["warnings"])

    def test_change_to_home_with_weights_keeps_the_combined(self, isolated_state):
        mon, fri, plan = self._seed(["hangboard", "pullup_bar", "dumbbell"])
        body = self._post(plan, mon, fri)
        s = next(s for s in body["week_plan"]["weeks"][0]["days"][4]["sessions"] if s["slot"] == "evening")
        assert s["session_id"] == COMBO
