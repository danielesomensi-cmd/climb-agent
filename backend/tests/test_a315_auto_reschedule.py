"""A315 — automatic re-schedule of a lost key session (with undo).

Synthetic fixtures of A294 (SP week of 2026-10-05, tested athlete). With lunch
unavailable every evening of the week is taken or blocked by a guard, so a
skipped strength_long (finger max + max pulling) can only come back by taking
the slot of Sunday's finger maintenance — a session that holds no key role.
"""

from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import key_sessions_v1 as ks
from backend.engine import user_owned as uo
from backend.engine.replanner_v1 import apply_events
from backend.tests.test_a294_key_sessions import WEEKDAYS, _req, _sess, _state

WS = "2026-10-05"
TODAY = "2026-10-06"
client = TestClient(app)


def _evening_only(st):
    for wd in WEEKDAYS:
        st["availability"][wd]["lunch"] = {"available": False}
    return st


def _skipped_state(**over):
    st = _evening_only(_state(**over))
    st["week_plans"][WS] = apply_events(st["week_plans"][WS], [
        {"event_type": "mark_skipped", "date": "2026-10-09", "slot": "evening"}])
    return st


def _day(plan, d):
    return next(x for x in plan["weeks"][0]["days"] if x["date"] == d)


def _auto_event(p, aid="ar_test"):
    return {**p["apply"]["event"], "auto": True, "adaptation_id": aid, "keys": p["keys"]}


# ---------------------------------------------------------------------------
# Engine — the second pass of the proposal search
# ---------------------------------------------------------------------------

class TestReplacementPass:
    def test_free_slot_first(self):
        """Pass 1 is A294 unchanged: with lunch free, nothing is replaced."""
        st = _state()
        st["week_plans"][WS] = apply_events(st["week_plans"][WS], [
            {"event_type": "mark_skipped", "date": "2026-10-09", "slot": "evening"}])
        p = ks.compute_key_status(st, TODAY)["proposals"][0]
        assert p["replaces"] is None
        assert "replace_session_ref" not in p["apply"]["event"]

    def test_replaces_a_session_without_key_role(self):
        s = ks.compute_key_status(_skipped_state(), TODAY)
        assert len(s["proposals"]) == 1
        p = s["proposals"][0]
        assert set(p["keys"]) == {"finger_max", "pulling_max"} and p["session_id"] == "strength_long"
        assert (p["date"], p["slot"]) == ("2026-10-11", "evening")
        assert p["replaces"]["session_id"] == "finger_maintenance_gym"
        assert p["apply"]["event"]["replace_session_ref"] == "finger_maintenance_gym"
        assert p["side_effects"] == [{"date": "2026-10-11", "slot": "evening", "from": "finger_maintenance_gym",
                                      "to": "strength_long", "reason": "key_reschedule"}]
        assert _req(s, "finger_max")["resolution"] == "proposal"

    @pytest.mark.parametrize("mark", [
        {"is_custom": True}, {"_user_edited": True}, {"forced": True},
        {"constraints_applied": ["quick_add"]}, {"constraints_applied": ["user_moved"]},
        {"status": "done"},
    ])
    def test_never_replaces_the_users_sessions(self, mark):
        st = _skipped_state()
        _day(st["week_plans"][WS], "2026-10-11")["sessions"][0].update(mark)
        s = ks.compute_key_status(st, TODAY)
        assert all(p.get("replaces") is None for p in s["proposals"])
        assert not any((p["date"], p["slot"]) == ("2026-10-11", "evening") for p in s["proposals"])

    def test_never_replaces_a_key_session(self):
        """Saturday's technique session is the week's technique key."""
        st = _skipped_state()
        _day(st["week_plans"][WS], "2026-10-11")["sessions"][0]["is_custom"] = True
        s = ks.compute_key_status(st, TODAY)
        assert not any(p["date"] == "2026-10-10" for p in s["proposals"])

    def test_rejected_when_another_key_gets_worse(self, monkeypatch):
        real = ks._week_debts

        def fake(state, today, ws, plan, *a):
            out = real(state, today, ws, plan, *a)
            sun = next(d for d in plan["weeks"][0]["days"] if d["date"] == "2026-10-11")
            if any("key_reschedule" in (s.get("constraints_applied") or []) for s in sun.get("sessions") or []):
                # the simulated replacement: technique would owe more
                out = {**out, "technique": out.get("technique", 0) + 1}
            return out

        monkeypatch.setattr(ks, "_week_debts", fake)
        s = ks.compute_key_status(_skipped_state(), TODAY)
        assert s["proposals"] == []
        assert _req(s, "finger_max")["resolution"] != "proposal"
        assert _req(s, "pulling_max")["resolution"] != "proposal"


# ---------------------------------------------------------------------------
# Engine — replacement and undo in the replanner
# ---------------------------------------------------------------------------

class TestReplannerEvents:
    def _applied(self):
        st = _skipped_state()
        plan = st["week_plans"][WS]
        p = ks.compute_key_status(st, TODAY)["proposals"][0]
        return plan, apply_events(plan, [_auto_event(p)], today=TODAY)

    def test_auto_add_replaces_and_keeps_the_snapshot(self):
        plan, after = self._applied()
        before_s = _day(plan, "2026-10-11")["sessions"][0]
        sun = _day(after, "2026-10-11")["sessions"]
        assert [s["session_id"] for s in sun] == ["strength_long"]
        assert sun[0]["replaced_original"] == before_s
        assert sun[0]["constraints_applied"] == ["key_reschedule", "auto_reschedule"]
        assert sun[0]["auto_reschedule_id"] == "ar_test"
        rec = [a for a in after["adaptations"] if a.get("type") == "auto_reschedule"]
        assert rec == [{"type": "auto_reschedule", "id": "ar_test", "keys": ["finger_max", "pulling_max"],
                        "date": "2026-10-11", "slot": "evening", "session_id": "strength_long",
                        "replaced_session_id": "finger_maintenance_gym"}]

    def test_replacement_refused_on_user_sessions(self):
        st = _skipped_state()
        plan = st["week_plans"][WS]
        _day(plan, "2026-10-11")["sessions"][0]["constraints_applied"] = ["manual_override"]
        ev = {"event_type": "add_planned_session", "session_id": "strength_long", "target_date": "2026-10-11",
              "slot": "evening", "replace_session_ref": "finger_maintenance_gym"}
        with pytest.raises(ValueError):
            apply_events(plan, [ev])
        # Without replace_session_ref an occupied slot is refused as before.
        with pytest.raises(ValueError):
            apply_events(st["week_plans"][WS], [{**ev, "replace_session_ref": None}])

    def test_undo_restores_the_snapshot_byte_for_byte(self):
        plan, after = self._applied()
        undone = apply_events(after, [{"event_type": "undo_auto_reschedule", "adaptation_id": "ar_test"}],
                              today=TODAY)
        assert _day(undone, "2026-10-11")["sessions"] == _day(plan, "2026-10-11")["sessions"]
        dec = [a for a in undone["adaptations"] if a.get("type") == "auto_reschedule_declined"]
        assert dec == [{"type": "auto_reschedule_declined", "adaptation_id": "ar_test",
                        "keys": ["finger_max", "pulling_max"], "week": WS}]

    def test_undo_without_replacement_removes_the_session(self):
        st = _state()
        st["week_plans"][WS] = apply_events(st["week_plans"][WS], [
            {"event_type": "mark_skipped", "date": "2026-10-09", "slot": "evening"}])
        p = ks.compute_key_status(st, TODAY)["proposals"][0]
        after = apply_events(st["week_plans"][WS], [_auto_event(p)], today=TODAY)
        undone = apply_events(after, [{"event_type": "undo_auto_reschedule", "adaptation_id": "ar_test"}],
                              today=TODAY)
        assert _day(undone, p["date"])["sessions"] == _day(st["week_plans"][WS], p["date"])["sessions"]

    @pytest.mark.parametrize("change,today", [
        ({"status": "done"}, TODAY),
        ({"status": "skipped"}, TODAY),
        ({"_user_edited": True}, TODAY),
        ({}, "2026-10-12"),  # the re-scheduled day is in the past
    ])
    def test_undo_refused(self, change, today):
        _plan, after = self._applied()
        _day(after, "2026-10-11")["sessions"][0].update(change)
        with pytest.raises(ValueError):
            apply_events(after, [{"event_type": "undo_auto_reschedule", "adaptation_id": "ar_test"}],
                         today=today)

    def test_undo_twice_or_unknown_refused(self):
        _plan, after = self._applied()
        undone = apply_events(after, [{"event_type": "undo_auto_reschedule", "adaptation_id": "ar_test"}],
                              today=TODAY)
        with pytest.raises(ValueError):
            apply_events(undone, [{"event_type": "undo_auto_reschedule", "adaptation_id": "ar_test"}],
                         today=TODAY)
        with pytest.raises(ValueError):
            apply_events(after, [{"event_type": "undo_auto_reschedule", "adaptation_id": "nope"}], today=TODAY)

    def test_regeneration_honours_the_replacement_until_undone(self):
        _plan, after = self._applied()
        assert ("2026-10-11", "finger_maintenance_gym", "evening") in uo.removed_refs(after)
        undone = apply_events(after, [{"event_type": "undo_auto_reschedule", "adaptation_id": "ar_test"}],
                              today=TODAY)
        assert ("2026-10-11", "finger_maintenance_gym", "evening") not in uo.removed_refs(undone)


# ---------------------------------------------------------------------------
# API — /events and /override
# ---------------------------------------------------------------------------

@pytest.fixture
def api_state(tmp_path, monkeypatch):
    from backend.engine import storage

    tmp_state = tmp_path / "user_state.json"
    st = _evening_only(_state())
    st["current_week_plan"] = copy.deepcopy(st["week_plans"][WS])
    tmp_state.write_text(json.dumps(st))
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.delenv("KEY_AUTO_RESCHEDULE", raising=False)
    return st


def _post(plan, events, today=TODAY, **kw):
    return client.post("/api/replanner/events", json={"week_plan": plan, "today": today, "events": events, **kw})


SKIP = [{"event_type": "mark_skipped", "date": "2026-10-09", "slot": "evening", "session_ref": "strength_long"}]


class TestApi:
    def test_skip_reschedules_automatically(self, api_state):
        r = _post(api_state["week_plans"][WS], SKIP)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["adjustments"] == []
        assert len(body["auto_reschedules"]) == 1
        a = body["auto_reschedules"][0]
        assert (a["date"], a["slot"], a["session_id"]) == ("2026-10-11", "evening", "strength_long")
        assert a["replaced"]["session_id"] == "finger_maintenance_gym"
        assert set(a["keys"]) == {"finger_max", "pulling_max"}
        saved = deps.load_state(None)["week_plans"][WS]
        assert _day(saved, "2026-10-11")["sessions"][0]["auto_reschedule_id"] == a["adaptation_id"]
        # The key status of the response already counts it: no debt left.
        assert _req(body["key_status"], "finger_max")["debt"] == 0

    def test_past_days_are_untouched(self, api_state):
        before = copy.deepcopy(api_state["week_plans"][WS])
        r = _post(before, SKIP)
        after = r.json()["week_plan"]

        def strip(sessions):  # ``resolved`` is the read-time prescription every write attaches
            return [{k: v for k, v in s.items() if k != "resolved"} for s in sessions]

        for d in ("2026-10-05",):  # before TODAY
            assert strip(_day(after, d)["sessions"]) == _day(before, d)["sessions"]

    def test_undo_restores_and_is_not_reapplied(self, api_state):
        r = _post(api_state["week_plans"][WS], SKIP)
        aid = r.json()["auto_reschedules"][0]["adaptation_id"]
        r2 = _post(r.json()["week_plan"], [{"event_type": "undo_auto_reschedule", "adaptation_id": aid}])
        assert r2.status_code == 200, r2.text
        assert r2.json()["auto_reschedules"] == []
        sun = _day(r2.json()["week_plan"], "2026-10-11")["sessions"]
        assert [s["session_id"] for s in sun] == ["finger_maintenance_gym"]
        # An unrelated write later in the week does not bring it back.
        r3 = _post(r2.json()["week_plan"], [{"event_type": "mark_done", "date": "2026-10-05", "slot": "evening"}])
        assert r3.status_code == 200, r3.text
        assert r3.json()["auto_reschedules"] == []

    def test_undo_refused_is_422(self, api_state):
        r = _post(api_state["week_plans"][WS], [{"event_type": "undo_auto_reschedule", "adaptation_id": "nope"}])
        assert r.status_code == 422

    def test_old_debt_is_not_applied_by_an_unrelated_write(self, api_state, monkeypatch):
        # The skip happened with the feature off: the debt stays a proposal.
        monkeypatch.setenv("KEY_AUTO_RESCHEDULE", "0")
        r = _post(api_state["week_plans"][WS], SKIP)
        assert r.json()["auto_reschedules"] == []
        assert r.json()["key_status"]["proposals"]
        monkeypatch.delenv("KEY_AUTO_RESCHEDULE")
        r2 = _post(r.json()["week_plan"], [{"event_type": "mark_done", "date": "2026-10-05", "slot": "evening"}])
        assert r2.status_code == 200, r2.text
        assert r2.json()["auto_reschedules"] == []

    def test_kill_switch(self, api_state, monkeypatch):
        monkeypatch.setenv("KEY_AUTO_RESCHEDULE", "0")
        r = _post(api_state["week_plans"][WS], SKIP)
        assert r.status_code == 200
        assert r.json()["auto_reschedules"] == []
        assert [s["session_id"] for s in _day(r.json()["week_plan"], "2026-10-11")["sessions"]] == \
            ["finger_maintenance_gym"]

    def test_dry_run_reports_and_writes_nothing(self, api_state):
        r = _post(api_state["week_plans"][WS], SKIP, dry_run=True)
        assert r.status_code == 200, r.text
        would = r.json()["would_auto_reschedule"]
        assert [(w["date"], w["session_id"]) for w in would] == [("2026-10-11", "strength_long")]
        saved = deps.load_state(None)["week_plans"][WS]
        assert saved == api_state["week_plans"][WS]

    def test_past_week_never_reschedules(self, api_state):
        r = _post(api_state["week_plans"][WS], SKIP, today="2026-10-13")
        assert r.status_code == 200, r.text
        assert r.json()["auto_reschedules"] == []

    def test_override_that_takes_a_key_away_reschedules(self, api_state, monkeypatch):
        # The fixture week is in the real past: /override refuses past weeks on the server clock.
        monkeypatch.setattr("backend.api.routers.replanner.is_past_week", lambda ws: False)
        r = client.post("/api/replanner/override", json={
            "intent": "rest", "location": "gym", "reference_date": "2026-10-09", "target_date": "2026-10-09",
            "week_plan": api_state["week_plans"][WS], "today": TODAY, "phase_id": "strength_power"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["adjustments"] == []
        assert [(a["date"], a["session_id"]) for a in body["auto_reschedules"]] == [("2026-10-11", "strength_long")]
