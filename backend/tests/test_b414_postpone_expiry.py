"""B414 (B414-2) — "Postpone the expiry": the A320 postpone becomes the extension.

Decision of Daniele (2026-11-07): next to "Do the test", the only other way
out of an expiring test is to postpone its expiry — 2, 4 or 6 weeks (default
4), repeatable with no total cap, one button for fingers and pulling.

One concept ("not before X, and the max counts until X"), built on the A320
postpone record:
- the record's ``until`` extends ``official_max.valid_until`` (``extended``);
- allowed with no pending test (after the end of the cycle, a declined
  test…): the record carries the trigger ``expiry``;
- A320's ``until_after_expiry`` is gone; one postpone reaches at most
  ``EXTENSION_MAX_D`` days past the later of today and the current validity
  (``until_too_far``);
- a new postpone replaces the axis' active ones (``previous_until`` in the
  record, a ``retest_postponed`` event in the log);
- the A320 rules stay: a new test makes the record inert, DELETE undoes it,
  a dry run writes nothing, a paused plan refuses the write, past sessions are
  never touched.

``POST /api/retest/extend`` is the one-button path: both covered axes to the
same day, ``weeks`` after the later of today and their latest validity.
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
from backend.engine import retest_declines as rd
from backend.engine import retest_policy as rp

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture
def api(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(FIXTURE_STATE, tmp_state)
    from backend.engine import storage, storage_file

    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_path


def _today() -> date:
    return date.today()


def _seed(*, test_age: int = 80, cycle_weeks_ago: int = 20) -> dict:
    """Both max tests ``test_age`` days ago; the macrocycle started
    ``cycle_weeks_ago`` weeks ago (13 weeks: by default it ended 7 weeks ago,
    so nothing is pending), with a done session last week (the past)."""
    today = _today()
    state = deps.load_state(None)
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=cycle_weeks_ago)
    state["macrocycle"] = {"start_date": start.isoformat(), "phases": [
        {"phase_id": "base", "duration_weeks": 2}, {"phase_id": "strength_power", "duration_weeks": 4},
        {"phase_id": "power_endurance", "duration_weeks": 3}, {"phase_id": "performance", "duration_weeks": 3},
        {"phase_id": "deload", "duration_weeks": 1}]}
    t = (today - timedelta(days=test_age)).isoformat()
    state["tests"] = {
        "max_strength": [{"date": t, "test_id": "max_hang_7s_total_load", "total_load_kg": 110.0,
                          "bodyweight_kg": 77.0}],
        "pulling_strength": [{"date": t, "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 115.0,
                              "estimated_1rm_kg": 120.5, "bodyweight_kg": 77.0}],
    }
    state["preferences"] = {"finger_training_device": "hangboard"}
    last_mon = (today - timedelta(days=today.weekday()) - timedelta(weeks=1)).isoformat()
    state["week_plans"] = {last_mon: {"start_date": last_mon, "weeks": [{"days": [
        {"date": last_mon, "sessions": [{"session_id": "strength_long", "status": "done", "slot": "evening",
                                         "actual_exercises": [{"exercise_id": "max_hang_7s", "completed": True,
                                                               "used_total_load_kg": 104.0}]}]}]}]}}
    state["current_week_plan"] = None
    state.pop(rp.DECLINES_KEY, None)
    deps.save_state(state, None)
    return state


def _events(tmp: Path) -> list:
    p = tmp / "logs" / "events.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def _past(state: dict) -> str:
    mon = (_today() - timedelta(days=_today().weekday())).isoformat()
    return json.dumps({k: v for k, v in (state.get("week_plans") or {}).items() if k < mon}, sort_keys=True)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _row(**over) -> dict:
    row = {"axis": "finger", "covered": True, "test_date": "2026-09-24", "valid_until": "2026-12-22",
           "tested_until": "2026-12-22", "next_test": None}
    row.update(over)
    return row


def _daniele() -> dict:
    return {"tests": {
        "max_strength": [{"test_id": "max_hang_7s_total_load", "date": "2026-09-24", "total_load_kg": 116.0}],
        "pulling_strength": [{"test_id": "weighted_pullup_2rm", "date": "2026-09-24", "total_load_2rm_kg": 123.0,
                              "estimated_1rm_kg": 128.9}],
    }, "macrocycle": {"start_date": "2026-09-07", "phases": [{"phase_id": "base", "duration_weeks": 13}]}}


class TestEngine:
    def test_the_cap_is_per_postpone_and_counts_from_the_current_validity(self):
        st = _daniele()
        ok = rd.build_record(st, "finger", status_row=_row(), today="2026-12-10", reason="schedule",
                             kind="postpone", until="2027-02-02")  # 22/12 + 42
        assert (ok["trigger"], ok["until"]) == (rp.TRIGGER_EXPIRY, "2027-02-02")
        with pytest.raises(rd.DeclineError) as err:
            rd.build_record(st, "finger", status_row=_row(), today="2026-12-10", reason="schedule",
                            kind="postpone", until="2027-02-03")
        assert err.value.code == "until_too_far"
        # After the expiry the cap counts from today.
        late = rd.build_record(st, "finger", status_row=_row(expired=True), today="2027-01-10",
                               reason="schedule", kind="postpone", until="2027-02-21")
        assert late["until"] == "2027-02-21"

    def test_a_repeated_postpone_replaces_the_previous_one(self):
        st = _daniele()
        first = rd.build_record(st, "finger", status_row=_row(), today="2026-12-10", reason="schedule",
                                kind="postpone", until="2027-01-19")
        assert rd.upsert(st, first, today="2026-12-10") is None
        row = rp.retest_status(st, "2027-01-10")["axes"]["finger"]
        assert (row["valid_until"], row["extended"], row["tested_until"]) == ("2027-01-19", True, "2027-01-19")
        # Repeatable, no total cap: from the extended validity on.
        second = rd.build_record(st, "finger", status_row=row, today="2027-01-10", reason="schedule",
                                 kind="postpone", until="2027-03-02")  # 19/01 + 42
        assert second["previous_until"] == "2027-01-19"
        assert rd.upsert(st, second, today="2027-01-10") == first
        assert st[rp.DECLINES_KEY] == [second]
        assert rp.official_max(st, rp.PROTOCOL_HANG_7S, "2027-02-20")["valid_until"] == "2027-03-02"
        view = rp.retest_status(st, "2027-01-10")["axes"]["finger"]["declines"][0]
        assert (view["until"], view["previous_until"], view["trigger"]) == ("2027-03-02", "2027-01-19", "expiry")

    def test_a_new_test_makes_the_extension_inert(self):
        st = _daniele()
        rec = rd.build_record(st, "finger", status_row=_row(), today="2026-12-10", reason="schedule",
                              kind="postpone", until="2027-01-19")
        rd.upsert(st, rec, today="2026-12-10")
        st["tests"]["max_strength"].append({"test_id": "max_hang_7s_total_load", "date": "2027-01-05",
                                            "total_load_kg": 118.0})
        om = rp.official_max(st, rp.PROTOCOL_HANG_7S, "2027-01-10")
        assert (om["valid_until"], om["extended"]) == ("2027-04-04", False)

    def test_extended_validity_drives_expiring_and_expired(self):
        st = _daniele()
        st[rp.DECLINES_KEY] = [{"axis": "finger", "kind": "postpone", "trigger": "expiry",
                                "official_date": "2026-09-24", "until": "2027-01-19"}]
        flags = {on: (om["expiring"], om["expired"]) for on in ("2026-12-23", "2027-01-05", "2027-01-19",
                                                               "2027-01-20")
                 for om in [rp.official_max(st, rp.PROTOCOL_HANG_7S, on)]}
        assert flags == {"2026-12-23": (False, False), "2027-01-05": (True, False),
                         "2027-01-19": (True, False), "2027-01-20": (False, True)}
        # Another kind of record never extends (B414-3 requests, declines).
        st[rp.DECLINES_KEY][0]["kind"] = "decline"
        assert rp.official_max(st, rp.PROTOCOL_HANG_7S, "2027-01-05")["valid_until"] == "2026-12-22"

    def test_from_until_on_the_test_is_proposed_again(self):
        # A covered week after the extension: due again from `until` (the
        # natural maintenance trigger keeps its name, A320; with none it
        # would read `postponed`).
        st = _daniele()
        st["macrocycle"] = {"start_date": "2026-12-14", "phases": [{"phase_id": "base", "duration_weeks": 8}]}
        st[rp.DECLINES_KEY] = [{"axis": "finger", "kind": "postpone", "trigger": "expiry",
                                "official_date": "2026-09-24", "until": "2027-01-20"}]
        held = rp.retest_decisions(st, "2027-01-11", today="2027-01-11")["axes"]["finger"]
        assert (held["status"], held["skip_reason"]) == ("skipped", "postponed")
        due = rp.retest_decisions(st, "2027-01-18", today="2027-01-18")["axes"]["finger"]
        assert (due["status"], due["trigger"], due["first_date"]) == ("due", rp.TRIGGER_MAINTENANCE, "2027-01-20")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class TestApi:
    def test_extend_after_the_cycle_end_moves_both_axes_and_keeps_the_past(self, api):
        state = _seed()
        past = _past(state)
        today = _today()
        valid = today + timedelta(days=9)  # test 80 days ago + 89
        r = client.post("/api/retest/extend", json={"dry_run": False})
        assert r.status_code == 200, r.text
        body = r.json()
        until = (valid + timedelta(weeks=rp.EXTENSION_DEFAULT_WEEKS)).isoformat()
        assert (body["weeks"], body["until"]) == (4, until)
        assert [(e["axis"], e["decline"]["trigger"], e["previous_until"]) for e in body["extensions"]] == [
            ("finger", rp.TRIGGER_EXPIRY, None), ("pulling", rp.TRIGGER_EXPIRY, None)]
        for row in body["retest_status"]["axes"].values():
            assert (row["valid_until"], row["extended"], row["expired"]) == (until, True, False)
        stored = deps.load_state(None)
        assert [x["until"] for x in stored[rp.DECLINES_KEY]] == [until, until]
        assert _past(stored) == past
        ev = [e for e in _events(api) if e.get("event") == "retest_postponed"]
        assert [(e["axis"], e["until"], e["previous_until"]) for e in ev] == [
            ("finger", until, None), ("pulling", until, None)]

    def test_extend_is_repeatable_and_delete_undoes_one_axis(self, api):
        _seed()
        first = client.post("/api/retest/extend", json={"weeks": 2}).json()["until"]
        r = client.post("/api/retest/extend", json={"weeks": 6})
        assert r.status_code == 200, r.text
        second = r.json()["until"]
        assert second == (date.fromisoformat(first) + timedelta(weeks=6)).isoformat()
        assert [e["previous_until"] for e in r.json()["extensions"]] == [first, first]
        assert len(deps.load_state(None)[rp.DECLINES_KEY]) == 2  # one per axis: replaced, not stacked
        # Undo the finger one: its validity goes back to the test + 89.
        r = client.delete("/api/retest/decline/finger")
        assert r.status_code == 200, r.text
        axes = r.json()["retest_status"]["axes"]
        test_day = date.fromisoformat(axes["finger"]["test_date"])
        assert (axes["finger"]["valid_until"], axes["finger"]["extended"]) == (
            (test_day + timedelta(days=89)).isoformat(), False)
        assert (axes["pulling"]["valid_until"], axes["pulling"]["extended"]) == (second, True)

    def test_extend_six_weeks_with_axes_tested_on_different_days(self, api):
        """B414 review: one button, one day for both axes, counted from the
        LATER validity. The axis tested first must not refuse the 6 weeks
        (until_too_far on its own earlier validity): before the fix the
        whole extend failed with 422 whenever the two tests were not on the
        same day — and after a DELETE of one axis' postpone."""
        state = _seed()
        today = _today()
        state["tests"]["pulling_strength"][0]["date"] = (today - timedelta(days=70)).isoformat()
        deps.save_state(state, None)
        late = today + timedelta(days=19)  # pulling: 70 days ago + 89
        r = client.post("/api/retest/extend", json={"weeks": 6})
        assert r.status_code == 200, r.text
        until = (late + timedelta(weeks=6)).isoformat()
        assert r.json()["until"] == until
        axes = r.json()["retest_status"]["axes"]
        assert {a: (row["valid_until"], row["extended"]) for a, row in axes.items()} == {
            "finger": (until, True), "pulling": (until, True)}
        # Undo one axis, extend again by 6: the undone one is 42+ days behind.
        assert client.delete("/api/retest/decline/finger").status_code == 200
        r = client.post("/api/retest/extend", json={"weeks": 6})
        assert r.status_code == 200, r.text
        again = (date.fromisoformat(until) + timedelta(weeks=6)).isoformat()
        assert {a: row["valid_until"] for a, row in r.json()["retest_status"]["axes"].items()} == {
            "finger": again, "pulling": again}
        # The per-axis path keeps its own cap (no cap_from there).
        with pytest.raises(rd.DeclineError) as err:
            rd.build_record(_daniele(), "finger", status_row=_row(), today="2026-12-10", reason="schedule",
                            kind="postpone", until="2027-02-09")
        assert err.value.code == "until_too_far"
        ok = rd.build_record(_daniele(), "finger", status_row=_row(), today="2026-12-10", reason="schedule",
                             kind="postpone", until="2027-02-09", cap_from="2026-12-29")
        assert ok["until"] == "2027-02-09"

    def test_dry_run_writes_nothing_and_paused_plan_refuses(self, api):
        _seed()
        # The first read of the fixture saves its load-time migrations (any
        # endpoint): settle them, then a dry run must leave the bytes as they are.
        client.post("/api/retest/extend", json={"dry_run": True})
        raw = (api / "user_state.json").read_bytes()
        r = client.post("/api/retest/extend", json={"dry_run": True, "weeks": 6})
        assert r.status_code == 200, r.text
        assert r.json()["retest_status"]["axes"]["finger"]["extended"] is True
        assert (api / "user_state.json").read_bytes() == raw
        assert _events(api) == []
        state = deps.load_state(None)
        state["macrocycle"]["pause"] = {"active_since": _today().isoformat()}
        deps.save_state(state, None)
        assert client.post("/api/retest/extend", json={}).status_code == 409
        assert client.post("/api/retest/extend", json={"dry_run": True}).status_code == 200

    def test_errors(self, api):
        _seed()
        r = client.post("/api/retest/extend", json={"weeks": 3})
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "invalid_weeks")
        state = deps.load_state(None)
        state["tests"] = {}
        deps.save_state(state, None)
        r = client.post("/api/retest/extend", json={})
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "not_covered")

    def test_per_axis_postpone_past_the_expiry_and_its_cap(self, api):
        _seed()
        today = _today()
        valid = today + timedelta(days=9)
        too_far = (valid + timedelta(days=rp.EXTENSION_MAX_D + 1)).isoformat()
        r = client.post("/api/retest/decline", json={"axis": "finger", "kind": "postpone", "until": too_far,
                                                     "reason": "schedule"})
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "until_too_far")
        ok = (valid + timedelta(days=rp.EXTENSION_MAX_D)).isoformat()
        r = client.post("/api/retest/decline", json={"axis": "finger", "kind": "postpone", "until": ok,
                                                     "reason": "schedule"})
        assert r.status_code == 200, r.text
        assert r.json()["decline"]["trigger"] == rp.TRIGGER_EXPIRY
        assert r.json()["retest_status"]["axes"]["finger"]["valid_until"] == ok
        # A decline still needs a pending test (nothing is due after the cycle).
        r = client.post("/api/retest/decline", json={"axis": "pulling", "reason": "schedule"})
        assert (r.status_code, r.json()["detail"]["code"]) == (409, "no_pending_retest")
