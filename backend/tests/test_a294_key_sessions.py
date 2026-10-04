"""A294 (R5) — key sessions: catalog, status, dose, proposals, conflicts,
insertion check, composer guard and the additive replanner changes.

Synthetic fixtures shaped like the 2026-10-04 state (no prod data): SP week 2
of 4 on 2026-09-28, tested athlete (hang 7 s 116 kg, pull-up 2RM 123 kg).
"""

from __future__ import annotations

import copy
import json
import os
from datetime import date, timedelta

import pytest

from backend.engine import key_sessions_v1 as ks
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import apply_events
from backend.engine.stimulus import FAMILIES

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TODAY = "2026-10-04"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _sess(slot, sid, status=None, **kw):
    s = {"slot": slot, "session_id": sid}
    if status:
        s["status"] = status
    meta = _SESSION_META.get(sid)
    if meta and "tags" not in kw:
        s["tags"] = {"hard": bool(meta.get("hard")), "finger": bool(meta.get("finger"))}
    s.update(kw)
    return s


def _week(start, days, phase="strength_power", **extra):
    d0 = date.fromisoformat(start)
    out = []
    for k in range(7):
        d = (d0 + timedelta(days=k)).isoformat()
        out.append({"date": d, "weekday": WEEKDAYS[k], "sessions": copy.deepcopy(days.get(d, []))})
    plan = {"start_date": start, "weeks": [{"week_index": 1, "days": out}],
            "profile_snapshot": {"phase_id": phase, "hard_cap_per_week": 4, "recovery_multiplier": 1.0,
                                 "session_pool": ["finger_strength_home", "limit_boulder_gym", "power_contact_gym",
                                                  "strength_long", "technique_focus_gym", "finger_maintenance_gym",
                                                  "prehab_maintenance", "route_endurance_gym"]}}
    plan.update(extra)
    return plan


def _avail():
    return {wd: {"evening": {"available": True, "preferred_location": "gym", "gym_id": "g1"},
                 "lunch": {"available": True, "preferred_location": "gym", "gym_id": "g1"},
                 "morning": {"available": False}} for wd in WEEKDAYS}


def _custom_pull(load=30.0, sets=4):
    return _sess("morning", "custom_cs_pull", "done", is_custom=True, name="Trazioni",
                 tags={"hard": True, "finger": False},
                 exercises=[{"exercise_id": "weighted_pullup", "sets": sets, "reps": 3}],
                 actual_exercises=[{"exercise_id": "weighted_pullup", "completed_sets": sets,
                                    "completed_reps": 3, "used_external_load_kg": load}])


def _state(**over):
    prev_week = _week("2026-09-21", {
        "2026-09-24": [_sess("morning", "test_max_hang_7s", "done", tags={"hard": True, "finger": True, "test": True})],
    })
    cur_week = _week("2026-09-28", {
        "2026-09-28": [_sess("evening", "technique_focus_gym", "done")],
        "2026-09-30": [_sess("evening", "regeneration_easy", "skipped", tags={"hard": False, "finger": False},
                             skipped_session_id="finger_strength_home",
                             skipped_tags={"hard": True, "finger": True})],
        "2026-10-04": [_custom_pull()],
    })
    next_week = _week("2026-10-05", {
        "2026-10-05": [_sess("evening", "limit_boulder_gym")],
        "2026-10-06": [_sess("lunch", "prehab_maintenance")],
        "2026-10-07": [_sess("evening", "power_contact_gym")],
        "2026-10-09": [_sess("evening", "strength_long")],
        "2026-10-10": [_sess("evening", "technique_focus_gym")],
        "2026-10-11": [_sess("evening", "finger_maintenance_gym")],
    })
    st = {
        "bodyweight_kg": 78,
        "goal": {"discipline": "lead", "target_grade": "8b", "current_grade": "8a+"},
        "performance": {"current_level": {"sport": {"worked": {"grade": "8a+"}}}},
        "macrocycle": {"start_date": "2026-09-07", "phases": [
            {"phase_id": "base", "duration_weeks": 2},
            {"phase_id": "strength_power", "duration_weeks": 4},
            {"phase_id": "power_endurance", "duration_weeks": 3},
            {"phase_id": "performance", "duration_weeks": 3},
            {"phase_id": "deload", "duration_weeks": 1},
        ]},
        "availability": _avail(),
        "equipment": {"gyms": [{"gym_id": "g1", "name": "G", "priority": 1,
                                "equipment": ["gym_boulder", "hangboard", "pullup_bar", "campus_board",
                                              "gym_routes", "weight", "dumbbell", "barbell", "bench"]}],
                      "home": ["hangboard", "pullup_bar", "weight"]},
        "tests": {
            "max_strength": [
                {"date": "2026-09-24", "test_id": "max_hang_7s_total_load", "total_load_kg": 116.0,
                 "external_load_kg": 40.0, "bodyweight_kg": 76.0, "exercise_id": "max_hang_7s",
                 "confidence": "high"},
            ],
            "pulling_strength": [
                {"date": "2026-09-24", "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 123.0,
                 "external_load_2rm_kg": 45.0, "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0,
                 "exercise_id": "weighted_pullup", "confidence": "high"},
            ],
        },
        "week_plans": {"2026-09-21": prev_week, "2026-09-28": cur_week, "2026-10-05": next_week},
        "session_completion_log": [],
        "feedback_log": [],
    }
    st.update(over)
    return st


def _req(status, key):
    return next(r for r in status["requirements"] if r["key"] == key)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_session_ids_exist(self):
        cat = ks.load_key_catalog()
        for sid, sdef in cat["stimuli"].items():
            for s in (sdef.get("session_ids") or []) + (sdef.get("propose") or []) + (sdef.get("reentry_excluded") or []):
                assert s in _SESSION_META, (sid, s)
                assert os.path.exists(os.path.join(REPO, "backend", "catalog", "sessions", "v1", f"{s}.json"))
            for fam in sdef.get("families") or []:
                assert fam in FAMILIES
            assert sdef.get("why") and sdef.get("label")

    def test_exercise_ids_exist(self):
        ex = ks.load_exercise_catalog()
        for sdef in ks.load_key_catalog()["stimuli"].values():
            for eid in sdef.get("exercise_ids") or []:
                assert eid in ex

    def test_phases_follow_decisions(self):
        keys = lambda p: [r["key"] for r in ks.phase_requirements(p)]  # noqa: E731
        assert keys("strength_power") == ["finger_max", "limit_power", "pulling_max", "technique", "try_hard"]
        assert keys("power_endurance") == ["power_endurance", "finger_maintenance", "limit_power",
                                           "technique", "try_hard"]
        assert keys("performance") == ["project", "technique", "try_hard"]
        # A294 review: no limit key in base → no try-hard row; in performance
        # the try-hard rides on the project key.
        assert keys("base") == ["technique"]
        assert keys("deload") == ["technique"]
        perf_th = next(r for r in ks.phase_requirements("performance") if r["key"] == "try_hard")
        assert perf_th["attached_to"] == "project"
        deload_tech = next(r for r in ks.phase_requirements("deload") if r["key"] == "technique")
        assert deload_tech["max_severity"] == "info"
        pe_limit = next(r for r in ks.phase_requirements("power_endurance") if r["key"] == "limit_power")
        assert pe_limit["max_gap_days"] == 12
        pull = next(r for r in ks.phase_requirements("strength_power") if r["key"] == "pulling_max")
        assert pull["max_severity"] == "warning"

    def test_catalog_copy_is_independent(self):
        a = ks.load_key_catalog()
        a["stimuli"]["finger_max"]["label"] = "x"
        assert ks.load_key_catalog()["stimuli"]["finger_max"]["label"] != "x"

    def test_session_keys(self):
        assert ks.session_keys({"session_id": "strength_long"}, "strength_power") == ["finger_max", "pulling_max"]
        assert ks.session_keys({"session_id": "power_contact_gym"}, "strength_power") == ["limit_power"]
        assert ks.session_keys({"session_id": "technique_focus_gym"}, "deload") == ["technique"]
        assert ks.session_keys({"session_id": "prehab_maintenance"}, "strength_power") == []


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_current_week(self):
        s = ks.compute_key_status(_state(), TODAY)
        assert s["source"] == "a294" and s["week_start"] == "2026-09-28" and s["is_current_week"]
        fm = _req(s, "finger_max")
        assert fm["status"] == "missing" and fm["debt"] == 1
        assert fm["skipped"][0]["session_id"] == "finger_strength_home"
        pm = _req(s, "pulling_max")
        assert pm["status"] == "done" and pm["done"][0]["dose"] == "full"
        assert _req(s, "technique")["status"] == "done"

    def test_deferred_next_on_sunday(self):
        # Sunday: a finger catch-up today sits next to Monday's limit key.
        s = ks.compute_key_status(_state(), TODAY)
        fm = _req(s, "finger_max")
        assert fm["resolution"] == "deferred_next"
        assert fm["next_key"]["date"] == "2026-10-09" and fm["next_key"]["session_id"] == "strength_long"
        assert fm["severity"] == "info"
        assert s["proposals"] == []

    def test_next_week_roles(self):
        s = ks.compute_key_status(_state(), "2026-10-05")
        roles = {(e["date"], e["session_id"]): e for e in s["sessions"]}
        assert roles[("2026-10-05", "limit_boulder_gym")]["role"] == "key"
        assert "try_hard" in roles[("2026-10-05", "limit_boulder_gym")]["keys"]
        # Re-entry (< 2 limit exposures in 21 d): the second limit session is optional.
        assert s["reentry"]["limit_power"] is True
        assert roles[("2026-10-07", "power_contact_gym")]["role"] == "optional"
        sl = roles[("2026-10-09", "strength_long")]
        assert sl["role"] == "key" and set(sl["keys"]) == {"finger_max", "pulling_max"}
        # A294 review: the limit session alone is not the try-hard — it is
        # owed until a fall-practice block is in, and the hint says where.
        assert s["summary"]["missing"] == ["try_hard"]
        assert "2026-10-05" in _req(s, "try_hard")["hint"]

    def test_supporting_outside_reentry(self):
        st = _state()
        # Two limit exposures in the last 21 days → no re-entry.
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][1]["sessions"] = [_sess("evening", "limit_boulder_gym", "done")]
        st["week_plans"]["2026-09-21"]["weeks"][0]["days"][0]["sessions"] = [_sess("evening", "limit_boulder_gym", "done")]
        s = ks.compute_key_status(st, "2026-10-05")
        roles = {(e["date"], e["session_id"]): e["role"] for e in s["sessions"]}
        assert s["reentry"]["limit_power"] is False
        assert roles[("2026-10-07", "power_contact_gym")] == "supporting"

    def test_skipped_and_downgraded_roles(self):
        st = _state()
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        days[4]["sessions"] = [_sess("evening", "regeneration_easy", tags={"hard": False, "finger": False},
                                     downshifted_from="strength_long",
                                     constraints_applied=["finger_spacing_downshift"])]
        s = ks.compute_key_status(st, "2026-10-06")
        dg = [e for e in s["sessions"] if e["role"] == "downgraded"]
        assert dg and dg[0]["downgraded_from"] == "strength_long"
        assert any(c["code"] == "key_downgraded" for c in s["conflicts"])
        assert _req(s, "finger_max")["lost"][0]["session_id"] == "strength_long"

    def test_determinism_and_no_mutation(self):
        st = _state()
        before = copy.deepcopy(st)
        a = ks.compute_key_status(st, "2026-10-06")
        b = ks.compute_key_status(st, "2026-10-06")
        assert a == b and st == before
        json.dumps(a)  # serialisable

    def test_unplaceable_finger(self):
        st = _state()
        st["week_plans"]["2026-09-28"]["unmet_stimulus"] = [{"stimulus": "finger_strength"}]
        fm = _req(ks.compute_key_status(st, TODAY), "finger_max")
        assert fm["status"] == "unplaceable" and fm["debt"] == 0

    def test_b308_pulling_not_mapped(self):
        st = _state()
        st["week_plans"]["2026-09-28"]["unmet_stimulus"] = [{"stimulus": "pulling"}]
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][6]["sessions"] = []
        assert _req(ks.compute_key_status(st, TODAY), "pulling_max")["status"] == "missing"

    def test_outdoor_counts_for_try_hard_not_technique_and_blocks_proposals(self):
        st = _state()
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][0]["sessions"] = []
        rows = [{"entry": {"date": "2026-10-03", "spot_name": "Berdorf", "discipline": "lead",
                           "routes": [{"name": "P", "grade": "8a", "attempts": [{"result": "fell"}]}]}}]
        s = ks.compute_key_status(st, "2026-10-02", outdoor_rows=rows)
        # A294 review: an outdoor day says nothing verifiable about feet /
        # positioning work — the technique key stays owed.
        assert _req(s, "technique")["status"] != "done"
        assert _req(s, "try_hard")["status"] == "done"
        fm = _req(s, "finger_max")
        # 02/10 sits next to the 03/10 outdoor-hard day; 04/10 between it and Monday's limit.
        assert fm["resolution"] != "proposal"
        assert all(p["date"] not in ("2026-10-02", "2026-10-04") for p in s["proposals"]
                   if _SESSION_META[p["session_id"]].get("finger"))

    def test_free_boulder_counts_as_limit(self):
        st = _state(free_sessions=[{"id": "f1", "date": "2026-10-01", "surface": "gym_boulder",
                                    "finished_at": "x", "climbs": [{"grade": "7B+"}, {"grade": "7C"}]}],
                    performance={"current_level": {"boulder": {"worked": {"grade": "7C"}},
                                                   "sport": {"worked": {"grade": "8a+"}}}})
        lp = _req(ks.compute_key_status(st, TODAY), "limit_power")
        assert lp["status"] == "done" and lp["done"][0]["evidence"].startswith("free")

    def test_test_counts_for_finger_max(self):
        st = _state()
        s = ks.compute_key_status(st, "2026-09-25", week_start="2026-09-21")
        assert _req(s, "finger_max")["status"] == "done"

    def test_past_week_is_missed_without_proposals(self):
        s = ks.compute_key_status(_state(), "2026-10-08", week_start="2026-09-28")
        assert s["is_past_week"] and s["proposals"] == [] and s["conflicts"] == []
        assert _req(s, "finger_max")["resolution"] == "missed"


class TestDose:
    def test_full_above_floor(self):
        r = _req(ks.compute_key_status(_state(), TODAY), "pulling_max")
        assert r["done"][0]["dose_reason"] == "at_or_above_floor"

    def test_partial_below_floor(self):
        st = _state()
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][6]["sessions"] = [_custom_pull(load=0.0)]
        r = _req(ks.compute_key_status(st, TODAY), "pulling_max")
        assert r["status"] == "partial" and r["partial"][0]["dose_reason"] == "below_floor"
        assert r["debt"] == 1 and r["severity"] in ("warning", "info")

    def test_partial_too_few_sets(self):
        st = _state()
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][6]["sessions"] = [_custom_pull(sets=2)]
        r = _req(ks.compute_key_status(st, TODAY), "pulling_max")
        assert r["partial"][0]["dose_reason"] == "too_few_sets"

    def test_untested_custom_is_partial_catalog_full(self):
        st = _state(tests={})
        r = _req(ks.compute_key_status(st, TODAY), "pulling_max")
        assert r["partial"][0]["dose_reason"] == "no_tested_max"
        s2 = ks.compute_key_status(st, "2026-10-05")
        assert _req(s2, "finger_max")["planned"][0]["dose"] == "full"  # catalog strength_long

    def test_anchored_custom_planned_is_full(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][4]["sessions"] = [
            _sess("evening", "custom_cs_h", is_custom=True, tags={"hard": True, "finger": True},
                  exercises=[{"exercise_id": "max_hang_7s", "sets": 5, "load_mode": "anchored"}])]
        r = _req(ks.compute_key_status(st, "2026-10-05"), "finger_max")
        assert r["planned"][0]["dose"] == "full" and r["planned"][0]["dose_reason"] == "anchored_prescription"


class TestProposals:
    def _skipped_strength_long(self):
        st = _state()
        plan = st["week_plans"]["2026-10-05"]
        st["week_plans"]["2026-10-05"] = apply_events(plan, [{"event_type": "mark_skipped", "date": "2026-10-09",
                                                              "slot": "evening"}])
        return st

    def test_proposal_covers_finger_and_pulling_with_side_effects(self):
        s = ks.compute_key_status(self._skipped_strength_long(), "2026-10-06")
        assert len(s["proposals"]) == 1
        p = s["proposals"][0]
        assert set(p["keys"]) == {"finger_max", "pulling_max"} and p["session_id"] == "strength_long"
        # 06 (after limit 05), 08 (before... after power_contact 07), 09 (skipped that day) are out.
        assert p["date"] == "2026-10-10"
        assert p["gym_id"] == "g1" and p["location"] == "gym"
        assert p["apply"]["event"]["event_type"] == "add_planned_session"
        # Sunday's finger maintenance becomes recovery: declared, not hidden.
        assert any(x["date"] == "2026-10-11" and x["from"] == "finger_maintenance_gym" for x in p["side_effects"])
        assert _req(s, "finger_max")["resolution"] == "proposal"
        assert _req(s, "pulling_max")["resolution"] == "proposal"

    def test_applying_the_proposal_settles_the_debt(self):
        st = self._skipped_strength_long()
        p = ks.compute_key_status(st, "2026-10-06")["proposals"][0]
        st["week_plans"]["2026-10-05"] = apply_events(st["week_plans"]["2026-10-05"], [p["apply"]["event"]])
        s = ks.compute_key_status(st, "2026-10-06")
        assert _req(s, "finger_max")["debt"] == 0 and _req(s, "pulling_max")["debt"] == 0
        assert s["proposals"] == []

    def test_proposal_never_touches_custom_or_done(self):
        st = self._skipped_strength_long()
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        days[6]["sessions"] = [_sess("evening", "custom_cs_f", is_custom=True, tags={"hard": False, "finger": True},
                                     exercises=[{"exercise_id": "max_hang_7s", "sets": 3}])]
        s = ks.compute_key_status(st, "2026-10-06")
        for p in s["proposals"]:
            assert p["date"] != "2026-10-10"  # would sit next to the custom finger session

    def test_pre_test_block(self):
        st = self._skipped_strength_long()
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        days[6]["sessions"] = [_sess("evening", "test_max_hang_7s", tags={"hard": True, "finger": True, "test": True})]
        s = ks.compute_key_status(st, "2026-10-06")
        assert all(p["date"] < "2026-10-08" for p in s["proposals"])
        rej = _req(s, "finger_max").get("rejections") or []
        assert any(r["reason"] == "pre_test" for r in rej) or not s["proposals"]

    def test_deferred_fatigue(self):
        st = self._skipped_strength_long()
        st["feedback_log"] = [{"date": "2026-10-05", "difficulty": "very_hard"}]
        s = ks.compute_key_status(st, "2026-10-06")
        assert s["proposals"] == []
        assert _req(s, "finger_max")["resolution"] == "deferred_fatigue"
        assert _req(s, "finger_max")["severity"] == "info"

    def test_one_finger_proposal_per_week(self):
        st = self._skipped_strength_long()
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        days[0]["sessions"] = []  # limit gone too
        days[2]["sessions"] = []
        s = ks.compute_key_status(st, "2026-10-05")
        finger_props = [p for p in s["proposals"]
                        if _SESSION_META[p["session_id"]].get("finger")]
        assert len(finger_props) <= 1

    def test_reentry_never_proposes_campus(self):
        st = self._skipped_strength_long()
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        days[0]["sessions"] = []
        days[2]["sessions"] = []
        st["week_plans"]["2026-10-05"]["profile_snapshot"]["session_pool"] = ["power_contact_gym"]
        s = ks.compute_key_status(st, "2026-10-05")
        assert all(p["session_id"] != "power_contact_gym" for p in s["proposals"])


class TestSeverity:
    def _no_finger_phase(self):
        st = _state()
        for wk in ("2026-09-21", "2026-09-28"):
            for day in st["week_plans"][wk]["weeks"][0]["days"]:
                day["sessions"] = [x for x in day["sessions"] if "finger" not in str(x.get("session_id"))
                                   and not str(x.get("session_id")).startswith("test_")]
        return st

    def test_critical_when_half_the_phase_missed(self):
        s = ks.compute_key_status(self._no_finger_phase(), TODAY)
        fm = _req(s, "finger_max")
        assert fm["debt"] == 1
        # Deferred to next week's key → informative, never alarm.
        assert fm["severity"] == "info"
        st = self._no_finger_phase()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"] = []  # no Monday limit
        s = ks.compute_key_status(st, "2026-10-01")
        fm = _req(s, "finger_max")
        if fm["resolution"] == "proposal":
            assert fm["severity"] == "critical"

    def test_pulling_never_critical(self):
        st = self._no_finger_phase()
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][6]["sessions"] = []
        assert _req(ks.compute_key_status(st, "2026-10-01"), "pulling_max")["severity"] in ("none", "info", "warning")


class TestMaxGap:
    def test_pe_limit_not_due_then_missing(self):
        st = _state()
        st["week_plans"]["2026-10-19"] = _week("2026-10-19", {
            "2026-10-22": [_sess("evening", "power_endurance_gym")],
            "2026-10-20": [_sess("evening", "finger_strength_home")],
        }, phase="power_endurance")
        st["week_plans"]["2026-10-12"] = _week("2026-10-12", {
            "2026-10-17": [_sess("evening", "power_contact_gym", "done")],
        })
        lp = _req(ks.compute_key_status(st, "2026-10-19"), "limit_power")
        assert lp["status"] == "not_due" and lp["due_by"] == "2026-10-29" and lp["debt"] == 0
        th = _req(ks.compute_key_status(st, "2026-10-19"), "try_hard")
        assert th["status"] == "not_due"
        st["week_plans"]["2026-10-12"]["weeks"][0]["days"][5]["sessions"][0]["status"] = "skipped"
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"][0]["status"] = "done"
        lp = _req(ks.compute_key_status(st, "2026-10-19"), "limit_power")
        assert lp["status"] == "missing"


# ---------------------------------------------------------------------------
# Insertion check
# ---------------------------------------------------------------------------

class TestInsertion:
    def _hang_custom(self):
        return {"id": "cs_hang", "name": "Hangs", "exercises": [{"exercise_id": "max_hang_7s", "sets": 5,
                                                                  "work_seconds": 7, "load_mode": "anchored"}]}

    def test_custom_replacing_finger_key(self):
        st = _state()
        res = ks.check_insertion(st, "2026-10-05", plan=st["week_plans"]["2026-10-05"],
                                 events=[{"event_type": "add_custom_session", "custom_session_id": "cs_hang",
                                          "target_date": "2026-10-08", "slot": "evening", "location": "home"}],
                                 custom_sessions=[self._hang_custom()])
        codes = {(c["code"], c.get("key")) for c in res["key_conflicts"]}
        assert ("key_replaced", "finger_max") in codes
        assert ("key_removed", "pulling_max") in codes
        rep = next(c for c in res["key_conflicts"] if c["code"] == "key_replaced")
        assert rep["replace_key"] is True
        assert res["adjustments"][0]["previous_session_id"] == "strength_long"
        # Nothing persisted: the input plan is untouched.
        assert st["week_plans"]["2026-10-05"]["weeks"][0]["days"][4]["sessions"][0]["session_id"] == "strength_long"

    def test_harmless_custom_has_no_conflict(self):
        st = _state()
        cs = {"id": "cs_core", "name": "Core", "exercises": [{"exercise_id": "dead_bug", "sets": 3}]}
        res = ks.check_insertion(st, "2026-10-05", plan=st["week_plans"]["2026-10-05"],
                                 events=[{"event_type": "add_custom_session", "custom_session_id": "cs_core",
                                          "target_date": "2026-10-08", "slot": "lunch", "location": "home"}],
                                 custom_sessions=[cs])
        assert res["key_conflicts"] == []

    def test_pre_test_conflict(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][6]["sessions"] = [
            _sess("evening", "test_max_hang_7s", tags={"hard": True, "finger": True, "test": True})]
        res = ks.check_insertion(st, "2026-10-05", plan=st["week_plans"]["2026-10-05"],
                                 events=[{"event_type": "add_custom_session", "custom_session_id": "cs_hang",
                                          "target_date": "2026-10-10", "slot": "lunch", "location": "home"}],
                                 custom_sessions=[self._hang_custom()])
        codes = {c["code"] for c in res["key_conflicts"]}
        assert "pre_test_fatigue" in codes
        # The finger custom the day before also pushes the test itself to recovery.
        assert "test_downgraded" in codes


# ---------------------------------------------------------------------------
# Composer guard + text
# ---------------------------------------------------------------------------

class TestComposerGuard:
    def test_near_finger_key_excludes_finger_hard(self):
        g = ks.composer_guard(_state(), "2026-10-08")  # day before strength_long
        assert "max_hang_7s" in g["exclude_ids"] and "limit_bouldering" in g["exclude_ids"]
        assert "weighted_pullup" not in g["exclude_ids"]
        assert g["warnings"][0]["code"] == "near_finger_key"

    def test_free_day_has_no_guard(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][2]["sessions"] = []
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"] = []
        assert ks.composer_guard(st, "2026-10-06") == {"exclude_ids": [], "warnings": []}

    def test_pre_pullup_test_excludes_heavy_pulls(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][6]["sessions"] = [
            _sess("evening", "test_max_weighted_pullup", tags={"hard": True, "finger": False, "test": True})]
        g = ks.composer_guard(st, "2026-10-10")
        assert "weighted_pullup" in g["exclude_ids"]

    def test_builder_honours_guard(self):
        from backend.engine.adaptive_replan import load_exercises_by_id
        from backend.engine.adhoc_builder import compose_adhoc_session

        cat = load_exercises_by_id()
        intent = {"equipment_set": "home", "focus": "finger_strength", "minutes": 45, "energy": "high",
                  "key_guard_exclude_ids": ks.composer_guard(_state(), "2026-10-08")["exclude_ids"]}
        sess = compose_adhoc_session(intent, _state(), cat, today="2026-10-08")
        ids = {e["exercise_id"] for e in sess["exercises"]}
        assert not ids & {"max_hang_7s", "max_hang_5s", "max_hang_ladder", "min_edge_hang"}

    def test_text_block(self):
        txt = ks.key_status_text(ks.compute_key_status(_state(), "2026-10-05"))
        assert txt.startswith("Key sessions 2026-10-05") and "Finger max: planned" in txt
        assert ks.key_status_text(None) == ""


# ---------------------------------------------------------------------------
# Replanner (additive)
# ---------------------------------------------------------------------------

class TestReplannerAdditive:
    def test_add_planned_session_is_catalog_no_ripple(self):
        st = _state()
        plan = st["week_plans"]["2026-10-05"]
        days = plan["weeks"][0]["days"]
        days[4]["sessions"] = []
        out = apply_events(plan, [{"event_type": "add_planned_session", "session_id": "strength_long",
                                   "target_date": "2026-10-09", "slot": "evening", "location": "gym",
                                   "gym_id": "g1"}])
        s = out["weeks"][0]["days"][4]["sessions"][0]
        assert s["session_id"] == "strength_long" and not s.get("is_custom")
        assert s["tags"] == {"hard": True, "finger": True} and "key_reschedule" in s["constraints_applied"]
        # No day+1 ripple: Saturday's technique session is untouched.
        assert out["weeks"][0]["days"][5]["sessions"][0]["session_id"] == "technique_focus_gym"

    def test_add_planned_session_validates(self):
        plan = _state()["week_plans"]["2026-10-05"]
        with pytest.raises(ValueError):
            apply_events(plan, [{"event_type": "add_planned_session", "session_id": "nope",
                                 "target_date": "2026-10-09", "slot": "evening"}])
        with pytest.raises(ValueError):
            apply_events(plan, [{"event_type": "add_planned_session", "session_id": "strength_long",
                                 "target_date": "2026-10-09", "slot": "evening"}])  # occupied

    def test_mark_skipped_stub_keeps_id(self):
        plan = _state()["week_plans"]["2026-10-05"]
        out = apply_events(plan, [{"event_type": "mark_skipped", "date": "2026-10-09", "slot": "evening"}])
        stub = out["weeks"][0]["days"][4]["sessions"][0]
        assert stub["status"] == "skipped" and stub["skipped_session_id"] == "strength_long"
        assert stub["skipped_tags"] == {"hard": True, "finger": True}

    def test_reconcile_adaptation_and_downshift_stamp(self):
        plan = _state()["week_plans"]["2026-10-05"]
        out = apply_events(plan, [{"event_type": "add_custom_session", "custom_session_id": "cs_h",
                                   "target_date": "2026-10-08", "slot": "lunch", "location": "home"}],
                           custom_sessions=[{"id": "cs_h", "name": "H",
                                             "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}]}])
        rec = [a for a in out["adaptations"] if a.get("type") == "reconcile"]
        assert rec and rec[0]["adjustments"][0]["previous_session_id"] == "strength_long"
        assert out["weeks"][0]["days"][4]["sessions"][0]["downshifted_from"] == "strength_long"

    def test_no_reconcile_adaptation_when_nothing_changes(self):
        plan = _state()["week_plans"]["2026-10-05"]
        out = apply_events(plan, [{"event_type": "mark_done", "date": "2026-10-06", "slot": "lunch"}])
        assert not [a for a in out["adaptations"] if a.get("type") == "reconcile"]

    def test_prev_days_seed(self):
        st = _state()
        plan = st["week_plans"]["2026-10-05"]
        prev = copy.deepcopy(st["week_plans"]["2026-09-28"]["weeks"][0]["days"])
        prev[6]["sessions"] = [_sess("evening", "finger_strength_home", "done")]
        out = apply_events(plan, [], prev_days=prev)
        assert out["weeks"][0]["days"][0]["sessions"][0]["session_id"] == "regeneration_easy"
        assert apply_events(plan, [])["weeks"][0]["days"][0]["sessions"][0]["session_id"] == "limit_boulder_gym"

    def test_done_sessions_never_rewritten(self):
        st = _state()
        plan = st["week_plans"]["2026-10-05"]
        plan["weeks"][0]["days"][0]["sessions"][0]["status"] = "done"
        prev = copy.deepcopy(st["week_plans"]["2026-09-28"]["weeks"][0]["days"])
        prev[6]["sessions"] = [_sess("evening", "finger_strength_home", "done")]
        before = copy.deepcopy(plan["weeks"][0]["days"][0])
        out = apply_events(plan, [], prev_days=prev)
        assert out["weeks"][0]["days"][0] == before


class TestCoachExposure:
    def test_prompt_key_section(self):
        from backend.coach.prompt_builder import _key_section

        txt = _key_section(_state(), None, "2026-10-05")
        assert txt.startswith("## Key sessions this week")
        assert "Finger max: planned" in txt and "Never suggest dropping" in txt

    def test_prompt_key_section_absent_without_plan(self):
        from backend.coach.prompt_builder import _key_section

        assert _key_section({}, None, "2026-10-05") is None

    def test_composer_pool_honours_guard(self):
        from backend.coach.session_composer import build_pool
        from backend.engine.adaptive_replan import load_exercises_by_id

        cat = load_exercises_by_id()
        st = _state()
        free = {e["id"] for e in build_pool({"equipment_set": "home"}, st, cat)}
        victim = sorted(free)[0]
        guarded = {e["id"] for e in build_pool({"equipment_set": "home",
                                                "key_guard_exclude_ids": [victim]}, st, cat)}
        assert victim not in guarded and guarded == free - {victim}


# ---------------------------------------------------------------------------
# A294 review fixes
# ---------------------------------------------------------------------------

class TestReviewFixes:
    def test_events_never_rewrite_a_past_unmarked_session(self):
        """Finding 1: the Sunday→Monday seed must not downshift a past Monday
        the athlete did but has not ticked yet."""
        st = _state()
        plan = _week("2026-09-28", {
            "2026-09-28": [_sess("evening", "finger_strength_home")],  # done in real life, unmarked
            "2026-09-30": [_sess("evening", "technique_focus_gym")],
        })
        prev = copy.deepcopy(st["week_plans"]["2026-09-21"]["weeks"][0]["days"])
        prev[6]["sessions"] = [_sess("evening", "strength_long", "done")]
        ev = [{"event_type": "mark_done", "date": "2026-09-30", "slot": "evening"}]
        out = apply_events(plan, ev, prev_days=prev, today="2026-09-30")
        mon = out["weeks"][0]["days"][0]["sessions"][0]
        assert mon["session_id"] == "finger_strength_home" and "downshifted_from" not in mon
        # Without a today the pre-A294 behaviour is unchanged (the guard runs).
        legacy = apply_events(plan, ev, prev_days=prev)
        assert legacy["weeks"][0]["days"][0]["sessions"][0]["session_id"] == "regeneration_easy"

    def test_frozen_past_day_still_constrains(self):
        st = _state()
        plan = _week("2026-09-28", {
            "2026-09-28": [_sess("evening", "finger_strength_home")],
            "2026-09-29": [_sess("evening", "strength_long")],
        })
        out = apply_events(plan, [], today="2026-09-29")
        days = out["weeks"][0]["days"]
        assert days[0]["sessions"][0]["session_id"] == "finger_strength_home"
        assert days[1]["sessions"][0]["session_id"] == "regeneration_easy"  # today, after a past finger day

    def test_untested_catalog_session_with_logged_load_is_full(self):
        """Finding 2: untested athletes who did the catalog session owe nothing."""
        st = _state(tests={})
        days = st["week_plans"]["2026-09-28"]["weeks"][0]["days"]
        days[1]["sessions"] = [_sess("evening", "finger_strength_home", "done", actual_exercises=[
            {"exercise_id": "max_hang_7s", "completed_sets": 5, "used_external_load_kg": 10}])]
        fm = _req(ks.compute_key_status(st, "2026-10-01"), "finger_max")
        assert fm["status"] == "done" and fm["debt"] == 0
        # A custom without a tested max stays partial (no floor to check).
        cust = _sess("evening", "custom_cs_h", "done", is_custom=True, actual_exercises=[
            {"exercise_id": "max_hang_7s", "completed_sets": 5, "used_external_load_kg": 10}])
        assert ks.session_dose(st, cust, "2026-10-01", ks.phase_requirements("strength_power")[0])["dose"] == "partial"

    def test_downshift_of_a_covered_stimulus_is_not_lost(self):
        """Finding 3: finger_max done Monday, strength_long downshifted Sunday →
        no 'lost' for finger_max; pulling_max (still owed) keeps it."""
        st = _state()
        st["week_plans"]["2026-09-28"] = _week("2026-09-28", {
            "2026-09-28": [_sess("evening", "finger_strength_home", "done")],
            "2026-10-04": [_sess("evening", "regeneration_easy", tags={"hard": False, "finger": False},
                                 downshifted_from="strength_long", constraints_applied=["hard_cap_downshift"])],
        })
        s = ks.compute_key_status(st, "2026-10-01")
        assert _req(s, "finger_max")["status"] == "done" and _req(s, "finger_max")["lost"] == []
        kd = [c for c in s["conflicts"] if c["code"] == "key_downgraded"]
        assert kd and "finger_max" not in kd[0]["keys"] and "pulling_max" in kd[0]["keys"]

    def _pull_week(self):
        st = _state()
        plan = _week("2026-10-05", {
            "2026-10-05": [_sess("evening", "finger_strength_home", "done")],
            "2026-10-06": [_sess("evening", "technique_focus_gym", "done")],
            "2026-10-08": [_sess("evening", "limit_boulder_gym")],
        })
        plan["profile_snapshot"]["session_pool"].append("pulling_strength_gym")
        st["week_plans"]["2026-10-05"] = plan
        return st

    def test_no_heavy_pull_proposed_the_evening_before_limit(self):
        """Finding 5: no ≥85 % pull within 24 h before a limit key."""
        s = ks.compute_key_status(self._pull_week(), "2026-10-07")
        pulls = [p for p in s["proposals"] if "pulling_max" in p["keys"]]
        for p in pulls:
            assert p["date"] not in ("2026-10-07",) and not (p["date"] == "2026-10-08" and p["slot"] != "evening")
        assert pulls and pulls[0]["date"] == "2026-10-09"  # after the limit key, not the evening before
        clash = ks._heavy_pull_clash(self._pull_week(), ks._plan_days(self._pull_week(), None),
                                     date(2026, 10, 7), "evening", "pulling_strength_gym")
        assert clash["reason"] == "heavy_pull_before_limit" and clash["with"] == ["2026-10-08 limit_boulder_gym"]

    def test_heavy_pull_cap_two_per_seven_days(self):
        st = _state()
        st["week_plans"]["2026-10-05"] = _week("2026-10-05", {
            "2026-10-05": [_custom_pull(load=45.0)],
            "2026-10-07": [_sess("evening", "pulling_strength_gym", "done")],
        })
        clash = ks._heavy_pull_clash(st, ks._plan_days(st, None), date(2026, 10, 9), "evening",
                                     "pulling_strength_gym")
        assert clash and clash["reason"] == "heavy_pull_cap"
        assert ks._heavy_pull_clash(st, ks._plan_days(st, None), date(2026, 10, 13), "evening",
                                    "pulling_strength_gym") is None

    def test_guard_covers_done_key_and_same_day_key(self):
        """Finding 6: a done finger key protects the next day; a pending one
        protects its own day."""
        st = _state()
        st["week_plans"]["2026-10-05"] = _week("2026-10-05", {
            "2026-10-05": [_sess("evening", "strength_long", "done")],
            "2026-10-07": [_sess("evening", "limit_boulder_gym")],
        })
        assert "max_hang_7s" in ks.composer_guard(st, "2026-10-06")["exclude_ids"]
        st["week_plans"]["2026-10-05"] = _week("2026-10-05", {
            "2026-10-07": [_sess("evening", "limit_boulder_gym")],
        })
        g = ks.composer_guard(st, "2026-10-07")
        assert "max_hang_7s" in g["exclude_ids"]

    def test_insertion_next_to_done_finger_key_asks_for_confirm(self):
        st = _state()
        st["week_plans"]["2026-10-05"] = _week("2026-10-05", {
            "2026-10-05": [_sess("evening", "strength_long", "done")],
        })
        res = ks.check_insertion(st, "2026-10-06", plan=st["week_plans"]["2026-10-05"],
                                 events=[{"event_type": "add_custom_session", "custom_session_id": "cs_hang",
                                          "target_date": "2026-10-06", "slot": "evening", "location": "home"}],
                                 custom_sessions=[{"id": "cs_hang", "name": "Hangs", "exercises": [
                                     {"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7}]}])
        fg = [c for c in res["key_conflicts"] if c["code"] == "finger_gap"]
        assert fg and fg[0]["severity"] == "high" and any("2026-10-05" in w for w in fg[0]["with"])

    def test_proposals_never_share_a_slot(self):
        """Finding 7: proposals are validated cumulatively."""
        st = _state()
        st["week_plans"]["2026-10-05"] = _week("2026-10-05", {})
        s = ks.compute_key_status(st, "2026-10-06")
        slots = [(p["date"], p["slot"]) for p in s["proposals"]]
        assert len(slots) == len(set(slots)) and len(slots) >= 2
        assert all(p.get("assumes") for p in s["proposals"][1:])
        # Applying them all in order still works (each one was validated on top of the previous).
        plan = st["week_plans"]["2026-10-05"]
        for p in s["proposals"]:
            plan = apply_events(plan, [p["apply"]["event"]])
            assert any(x.get("session_id") == p["session_id"] for d in plan["weeks"][0]["days"]
                       if d["date"] == p["date"] for x in d["sessions"])

    def test_technique_needs_feet_or_positioning_drills(self):
        """Finding 8: pacing / relaxation drills are not the technique key."""
        cat = ks.load_exercise_catalog()
        easy = {"session_id": "custom_x", "exercises": [{"exercise_id": "slow_climbing"},
                                                         {"exercise_id": "breathing_awareness"}]}
        real = {"session_id": "custom_y", "exercises": [{"exercise_id": "no_readjust_drill"},
                                                         {"exercise_id": "flag_practice"}]}
        assert not ks.technique_hit(easy, cat) and ks.technique_hit(real, cat)

    def test_technique_can_turn_critical(self):
        st = _state()
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][0]["sessions"] = []
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][5]["sessions"] = []
        tech = _req(ks.compute_key_status(st, "2026-10-06", with_proposals=False), "technique")
        assert tech["debt"] == 1 and tech["severity"] == "critical"

    def test_try_hard_needs_fall_practice_not_just_limit(self):
        """Finding 9: a limit session alone is not the try-hard."""
        st = _state()
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        assert _req(ks.compute_key_status(st, "2026-10-05"), "try_hard")["status"] == "missing"
        days[0]["sessions"][0]["exercises"] = [{"exercise_id": "limit_bouldering", "sets": 5},
                                               {"exercise_id": "fall_practice", "sets": 1}]
        th = _req(ks.compute_key_status(st, "2026-10-05"), "try_hard")
        assert th["status"] == "planned" and th["debt"] == 0

    def test_pe_limit_can_be_proposed_outside_the_pool(self):
        """Finding 10: PE asks for limit every 12 days; its pool has no limit
        session — the proposal may still use one, never a false 'let it go'."""
        st = _state()
        st["week_plans"]["2026-10-12"] = _week("2026-10-12", {
            "2026-10-13": [_sess("evening", "limit_boulder_gym", "done")],
        })
        pe_pool = ["power_endurance_gym", "prehab_maintenance", "core_training", "endurance_aerobic_gym",
                   "finger_strength_home", "flexibility_full", "route_endurance_gym", "technique_focus_gym"]
        plan = _week("2026-11-02", {"2026-11-03": [_sess("evening", "power_endurance_gym")],
                                    "2026-11-07": [_sess("evening", "finger_strength_home")]},
                     phase="power_endurance")
        plan["profile_snapshot"]["session_pool"] = pe_pool
        st["week_plans"]["2026-11-02"] = plan
        lp = _req(ks.compute_key_status(st, "2026-11-02"), "limit_power")
        assert lp["status"] == "missing" and lp["resolution"] != "let_go"
        s = ks.compute_key_status(st, "2026-11-02")
        assert any("limit_power" in p["keys"] for p in s["proposals"])

    def test_no_candidate_is_not_let_go(self):
        st = _state(equipment={"gyms": [], "home": []})
        st["week_plans"]["2026-10-05"] = _week("2026-10-05", {})
        s = ks.compute_key_status(st, "2026-10-06")
        tech = _req(s, "technique")
        assert tech["resolution"] != "let_go"


class TestCoachFlag:
    def test_key_section_off_with_flag(self, monkeypatch):
        from backend.coach.prompt_builder import _key_section

        monkeypatch.setenv("COACH_ATHLETE_CONTEXT", "0")
        assert _key_section(_state(), None, "2026-10-05") is None
        monkeypatch.setenv("COACH_ATHLETE_CONTEXT", "false")  # only the literal 0 turns it off
        assert _key_section(_state(), None, "2026-10-05") is not None
