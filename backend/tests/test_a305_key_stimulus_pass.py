"""A305 — PASS 2.7 (key stimuli), the power-endurance structure and the
``low_rest_days`` density alert.

Decisions of Daniele (2026-10-06): the pass applies to every user; victims are
volume sessions (duplicates first), never prehab / recovery, tests or
complementary lunches; power_endurance holds a limit session every week
(limit_boulder_gym / power_contact_gym alternating by week) and two PE
sessions; fewer than 2 true rest days → one week-level alert; deload untouched.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from backend.engine import guards_v1
from backend.engine import key_sessions_v1 as ks
from backend.engine.planner_v2 import (
    KEY_PASS_SECONDARY_VICTIMS,
    KEY_PASS_VOLUME_VICTIMS,
    _SESSION_META,
    generate_phase_week,
    key_pass_week_index,
)
from backend.engine.replanner_v1 import regenerate_preserving_completed
from backend.tests.test_a300_complementary_slots import days_of, plan

PE_WEEKS = ("2026-10-19", "2026-10-26", "2026-11-02")
LIMIT_SIDS = ("limit_boulder_gym", "power_contact_gym")
REST_SIDS = guards_v1.REST_DAY_SESSION_IDS


def _sessions(wp):
    return [(d["date"], s) for d in days_of(wp) for s in d["sessions"]]


def _key_entries(wp):
    return [(d, s) for d, s in _sessions(wp) if "pass2.7:key_stimulus" in (s.get("explain") or [])]


def _count(wp, key, phase):
    req = next(r for r in ks.phase_requirements(phase) if r["key"] == key)
    cat = ks.load_exercise_catalog()
    return sum(1 for _d, s in _sessions(wp) if ks.session_delivers(req, s, cat))


def _strip(wp):
    out = copy.deepcopy(wp)
    out.pop("generated_at", None)
    return out


# ---------------------------------------------------------------------------
# Catalog: the floor fields live on the phase rows, A294 ignores them
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_floor_candidates_are_catalog_sessions(self):
        cat = ks.load_key_catalog()
        for phase, rows in cat["phases"].items():
            for row in rows:
                for sid in row.get("floor_candidates") or []:
                    assert sid in _SESSION_META, (phase, sid)

    def test_deload_has_no_floor(self):
        assert not any(r.get("floor_candidates") for r in ks.phase_requirements("deload"))

    def test_power_endurance_rows(self):
        rows = {r["key"]: r for r in ks.phase_requirements("power_endurance")}
        assert rows["power_endurance"]["floor_target"] == 2
        assert rows["power_endurance"]["target_per_week"] == 1  # A294 target unchanged
        assert rows["limit_power"]["floor_alternate"] is True
        assert rows["limit_power"]["max_gap_days"] == 12      # A294 "not due" reading unchanged
        assert rows["limit_power"]["floor_candidates"] == list(LIMIT_SIDS)

    def test_victims_never_recovery_test_or_key(self):
        for sid in KEY_PASS_VOLUME_VICTIMS + KEY_PASS_SECONDARY_VICTIMS:
            assert sid not in REST_SIDS
            assert not _SESSION_META[sid].get("test")
            assert not _SESSION_META[sid].get("finger")
            assert sid not in ("technique_focus_gym", "prehab_maintenance")

    def test_a294_ignores_floor_fields(self):
        """A294 status AND proposals are byte-identical with the floor fields
        stripped from the catalog (proposals unchanged)."""
        from backend.tests.test_a294_key_sessions import TODAY, _state

        stripped = ks.load_key_catalog()
        for rows in stripped["phases"].values():
            for row in rows:
                for k in ("floor_candidates", "floor_target", "floor_alternate"):
                    row.pop(k, None)
        st = _state()
        for ws in ("2026-09-28", "2026-10-05"):
            a = ks.compute_key_status(st, TODAY, week_start=ws)
            b = ks.compute_key_status(st, TODAY, week_start=ws, key_catalog=stripped)
            assert a == b


# ---------------------------------------------------------------------------
# Daniele's structure: 6 primary evenings (Fri off), complementary lunches Tue-Fri
# ---------------------------------------------------------------------------

class TestDanieleStructure:
    @pytest.mark.parametrize("start", ("2026-10-12", "2026-10-19"))
    def test_strength_power_every_key_present(self, start):
        wp = plan("strength_power", start_date=start)
        for r in ks.phase_requirements("strength_power"):
            assert _count(wp, r["key"], "strength_power") >= 1, r["key"]
        assert wp["unmet_stimulus"] == []
        # try-hard by the lead try-hard session, in place of volume
        (d, s), = [(d, s) for d, s in _key_entries(wp) if s["session_id"] == "lead_tryhard_gym"]
        assert any(x.startswith("replaced:") and x[9:] in KEY_PASS_VOLUME_VICTIMS for x in s["explain"])

    def test_strength_power_sunday_prehab_stays(self):
        wp = plan("strength_power")
        sun = days_of(wp)[6]
        assert [s["session_id"] for s in sun["sessions"]] == ["prehab_maintenance"]

    @pytest.mark.parametrize("start", PE_WEEKS)
    def test_power_endurance_structure(self, start):
        wp = plan("power_endurance", start_date=start)
        assert _count(wp, "power_endurance", "power_endurance") >= 2
        sids = [s["session_id"] for _d, s in _sessions(wp)]
        assert sids.count("power_endurance_gym") == 2  # decision 5, lead pool
        assert sum(1 for x in sids if x in LIMIT_SIDS) == 1  # decision 4, every week
        for key in ("technique", "try_hard", "finger_maintenance", "limit_power"):
            assert _count(wp, key, "power_endurance") >= 1, key
        hard_days = sum(1 for d in days_of(wp) if any(s["tags"].get("hard") for s in d["sessions"]))
        assert hard_days == 3 <= 3  # within the cap of the fixture (3)
        assert wp["unmet_stimulus"] == []

    def test_power_endurance_limit_alternates_by_week(self):
        got = []
        for start in PE_WEEKS:
            wp = plan("power_endurance", start_date=start)
            got.append(next(s["session_id"] for _d, s in _sessions(wp) if s["session_id"] in LIMIT_SIDS))
        assert got[0] != got[1] and got[0] == got[2]
        first = key_pass_week_index(date.fromisoformat(PE_WEEKS[0])) % 2
        assert got[0] == LIMIT_SIDS[first]

    @pytest.mark.parametrize("start", ("2026-11-09", "2026-11-16"))
    def test_performance_every_key_present(self, start):
        wp = plan("performance", start_date=start)
        for r in ks.phase_requirements("performance"):
            assert _count(wp, r["key"], "performance") >= 1, r["key"]

    @pytest.mark.parametrize("phase", ("strength_power", "power_endurance", "performance"))
    def test_a294_status_planned(self, phase):
        """The A294 card on the generated week: every key planned (or not due)."""
        from backend.tests.test_a294_key_sessions import _state

        start = {"strength_power": "2026-10-12", "power_endurance": "2026-10-26",
                 "performance": "2026-11-09"}[phase]
        wp = plan(phase, start_date=start)
        st = _state()
        st["week_plans"] = {start: wp}
        status = ks.compute_key_status(st, start, week_start=start, with_proposals=False)
        assert status["phase_id"] == phase
        bad = [(r["key"], r["status"]) for r in status["requirements"]
               if r["status"] not in ("planned", "done", "not_due")]
        assert bad == []

    @pytest.mark.parametrize("phase", ("base", "strength_power", "power_endurance", "performance"))
    def test_victims_are_volume_never_prehab_test_or_lunch(self, phase):
        for start in ("2026-10-12", "2026-10-19"):
            wp = plan(phase, start_date=start)
            for _d, s in _key_entries(wp):
                assert s["slot"] != "lunch"
                rep = [x[9:] for x in s["explain"] if x.startswith("replaced:")]
                for v in rep:
                    assert v in KEY_PASS_VOLUME_VICTIMS + KEY_PASS_SECONDARY_VICTIMS
            lunches = [s for _d, s in _sessions(wp) if s["slot"] == "lunch"]
            assert all(s.get("slot_role") == "complementary" for s in lunches)
            assert len(lunches) == 4

    @pytest.mark.parametrize("phase", ("strength_power", "power_endurance", "performance"))
    def test_no_recovery_guard_alert_on_key_sessions(self, phase):
        for start in ("2026-10-12", "2026-10-19"):
            wp = plan(phase, start_date=start)
            keyed = {(d, s["slot"]) for d, s in _key_entries(wp)}
            for w in guards_v1.evaluate(wp):
                if w["code"] in (guards_v1.CODE_LOW_REST_DAYS, guards_v1.CODE_HIIT_NEAR_MAX):
                    continue  # density / lunch rotation: alerts, not recovery guards
                assert (w["date"], w["slot"]) not in keyed, w

    def test_deterministic(self):
        for phase in ("strength_power", "power_endurance", "performance"):
            assert _strip(plan(phase)) == _strip(plan(phase))

    @pytest.mark.parametrize("disc", ("lead", "boulder"))
    def test_deload_untouched(self, disc):
        wp = plan("deload", discipline=disc)
        assert _key_entries(wp) == []

    def test_boulder_pool_never_gets_a_rope_session(self):
        for phase in ("strength_power", "power_endurance", "performance"):
            wp = plan(phase, discipline="boulder")
            for _d, s in _key_entries(wp):
                assert "gym_routes" not in (_SESSION_META[s["session_id"]].get("required_equipment") or [])

    def test_boulder_power_endurance_gets_the_limit(self):
        wp = plan("power_endurance", discipline="boulder")
        assert sum(1 for _d, s in _sessions(wp) if s["session_id"] in LIMIT_SIDS) == 1
        assert _count(wp, "power_endurance", "power_endurance") >= 2


# ---------------------------------------------------------------------------
# Unmet: never silent
# ---------------------------------------------------------------------------

class TestUnmet:
    def test_low_hard_cap_reports_unmet(self):
        prefs = {"target_training_days_per_week": 6, "hard_day_cap_per_week": 1,
                 "complementary_rotation": ["legs", "hiit", "z2", "upper_push_arms"]}
        wp = plan("power_endurance", prefs=prefs)
        hard_days = sum(1 for d in days_of(wp) if any(s["tags"].get("hard") for s in d["sessions"]))
        assert hard_days <= 1
        rows = {u["stimulus"]: u for u in wp["unmet_stimulus"] if u.get("source") == "key_stimulus_pass"}
        assert set(rows) == {"limit_power", "try_hard"} or set(rows) == {"limit_power"}
        assert rows["limit_power"]["target"] == 1 and rows["limit_power"]["placed"] == 0
        assert rows["limit_power"]["phase_id"] == "power_endurance" and rows["limit_power"]["reason"]
        # The second PE session falls back to the non-hard circuit: the cap holds.
        assert _count(wp, "power_endurance", "power_endurance") >= 2

    def test_no_equipment_is_left_to_a294(self):
        """No gym with routes → the lead try-hard is not carried at all: no
        placement and no unmet row (A294 says it)."""
        from backend.tests.test_a300_complementary_slots import GYMS

        gyms = copy.deepcopy(GYMS)
        gyms[0]["equipment"] = [e for e in gyms[0]["equipment"] if e != "gym_routes"]
        wp = generate_phase_week(
            phase_id="strength_power", domain_weights={"finger_strength": 0.35},
            session_pool=["limit_boulder_gym", "power_contact_gym", "strength_long", "technique_focus_gym",
                          "prehab_maintenance", "boulder_circuit_gym"],
            start_date="2026-10-12", hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 5}, default_gym_id="blocx", gyms=gyms,
            home_equipment=["hangboard", "pullup_bar"],
        )
        assert not any(s["session_id"] == "lead_tryhard_gym" for _d, s in _sessions(wp))
        assert not any(u["stimulus"] == "try_hard" for u in wp["unmet_stimulus"])


# ---------------------------------------------------------------------------
# Regeneration: past immutable, B369 merge keeps the user's sessions
# ---------------------------------------------------------------------------

class TestRegeneration:
    def test_midweek_regeneration_past_immutable_and_user_owned_counted(self):
        start = "2026-10-26"
        first = plan("power_endurance", start_date=start)
        old = copy.deepcopy(first)
        days = days_of(old)
        # Monday and Tuesday lived: done with feedback.
        for d in days[:2]:
            for s in d["sessions"]:
                s["status"] = "done"
                s["feedback"] = {"difficulty": "ok"}
        # The user put their own limit session on Thursday (custom).
        thu = days[3]
        thu["sessions"] = [s for s in thu["sessions"] if s["slot"] == "lunch"] + [{
            "slot": "evening", "session_id": "custom_cs_limit", "is_custom": True, "name": "Limit mio",
            "tags": {"hard": True, "finger": True}, "exercises": [{"exercise_id": "limit_bouldering"}],
        }]
        today = "2026-10-28"
        new = plan("power_endurance", start_date=start, today=today, existing_week_plan=old)
        # Nothing generated on the lived days.
        for d in days_of(new)[:2]:
            assert [s for s in d["sessions"] if s.get("slot_role") != "complementary"] == []
        merged = regenerate_preserving_completed(old, new, preserve_before=today)
        md = days_of(merged)
        assert md[0] == days[0] and md[1] == days[1]  # past byte-identical
        assert any(s.get("session_id") == "custom_cs_limit" for s in md[3]["sessions"])
        # The user's limit counts: the pass did not add a second one.
        sids = [s["session_id"] for d in md for s in d["sessions"]]
        assert sum(1 for x in sids if x in LIMIT_SIDS) == 0
        assert not any(u["stimulus"] == "limit_power" for u in new["unmet_stimulus"])
        # And no engine finger session sits next to the user's finger day.
        for o in (2, 4):
            for s in md[o]["sessions"]:
                if s.get("slot_role") == "complementary":
                    continue
                assert not (s.get("tags") or {}).get("finger"), (o, s["session_id"])


    # -- review A305: the pass sees the week as the B369 merge returns it ----

    @staticmethod
    def _assert_merge_keeps_every_key(new, merged, phase):
        """Every key session the pass placed survives the merge, and every key
        short in the merged week has an unmet row (never silent)."""
        md = days_of(merged)
        by_date = {d["date"]: d for d in md}
        for d_iso, s in _key_entries(new):
            assert any(x.get("session_id") == s["session_id"] and x.get("slot") == s["slot"]
                       for x in by_date[d_iso]["sessions"]), (d_iso, s["session_id"])
        unmet = {u["stimulus"] for u in new["unmet_stimulus"] if u.get("source") == "key_stimulus_pass"}
        for r in ks.phase_requirements(phase):
            if not r.get("floor_candidates"):
                continue
            target = r.get("floor_target", r["target_per_week"])
            if _count(merged, r["key"], phase) < target:
                assert r["key"] in unmet, r["key"]

    def test_user_removal_slot_is_never_refilled(self):
        """The user removed Tuesday evening's route endurance (pre-A305 cache):
        the pass must not put the lead try-hard (a NEW id the merge would not
        filter) into the slot the user emptied."""
        start, today = "2026-10-12", "2026-10-12"
        old = plan("strength_power", start_date=start)
        tue = days_of(old)[1]
        tue["sessions"] = [s for s in tue["sessions"] if s["slot"] != "evening"]
        old["adaptations"] = [{"type": "event", "event": {
            "event_type": "remove_session", "date": tue["date"], "session_ref": "route_endurance_gym",
            "slot": "evening"}}]
        new = plan("strength_power", start_date=start, today=today, existing_week_plan=old)
        merged = regenerate_preserving_completed(copy.deepcopy(old), new, preserve_before=today)
        assert [s for s in days_of(merged)[1]["sessions"] if s["slot"] == "evening"] == []
        assert not any(d == tue["date"] and s["slot"] == "evening" for d, s in _key_entries(new))
        self._assert_merge_keeps_every_key(new, merged, "strength_power")

    def test_overrides_skipped_stubs_and_lived_today_hold(self):
        """A whole-day override, a skipped stub and today with a done session:
        a key placed there would be dropped by the merge — the pass places it
        elsewhere or reports it."""
        start, today = "2026-10-26", "2026-10-27"
        old = plan("power_endurance", start_date=start)
        days = days_of(old)
        for s in days[1]["sessions"]:          # today (Tue): done
            s["status"] = "done"
        for s in days[2]["sessions"]:          # Wed: the user skipped it
            s["status"] = "skipped"
        old["adaptations"] = [{"type": "day_override", "target_date": days[5]["date"], "outdoor": True}]
        new = plan("power_endurance", start_date=start, today=today, existing_week_plan=old)
        merged = regenerate_preserving_completed(copy.deepcopy(old), new, preserve_before=today)
        keyed = {d for d, _s in _key_entries(new)}
        assert days[1]["date"] not in keyed and days[5]["date"] not in keyed
        assert not any(d == days[2]["date"] and s["slot"] == "evening" for d, s in _key_entries(new))
        self._assert_merge_keeps_every_key(new, merged, "power_endurance")


# ---------------------------------------------------------------------------
# Review A305: one climbing / hard session per day, never in an extra slot
# ---------------------------------------------------------------------------

class TestNoStacking:
    def test_identity_matrix_never_stacks(self):
        from backend.engine.stimulus import session_flag
        from backend.tests.test_a300_complementary_slots import _identity_matrix

        for k, kw in _identity_matrix():
            wp = generate_phase_week(**kw)
            for d in days_of(wp):
                keyed = [s for s in d["sessions"] if "pass2.7:key_stimulus" in (s.get("explain") or [])]
                others = [s for s in d["sessions"] if s not in keyed]
                for s in keyed:
                    assert not any(session_flag(o, "climbing") or session_flag(o, "hard") for o in others), \
                        (k, d["date"], [x["session_id"] for x in d["sessions"]])
                    rep = [x[9:] for x in s["explain"] if x.startswith("replaced:")]
                    if rep:  # never in place of an extra-slot session (B121)
                        assert "pass2.2:extra_slot" not in s["explain"]

    def test_extra_slot_conditioning_is_never_a_victim(self):
        """simple|0 strength_power lead: the lunch conditioning PASS 2.2 put
        next to an evening climbing session stays (pre-review: replaced by the
        lead try-hard, two climbing sessions on one day)."""
        from backend.tests.test_a300_complementary_slots import _identity_matrix

        kw = dict(_identity_matrix())["simple|0|strength_power|lead|None"]
        wp = generate_phase_week(**kw)
        for _d, s in _key_entries(wp):
            for x in s["explain"]:
                if x.startswith("replaced:"):
                    assert x[9:] not in ("complementary_conditioning", "core_training"), s["explain"]


# ---------------------------------------------------------------------------
# Review A305: the planner does not create a hiit_near_max on its own
# ---------------------------------------------------------------------------

def test_pretrip_week_leaves_the_hiit_a_safe_day():
    wp = plan("power_endurance", start_date="2026-12-07",
              pretrip_dates=["2026-12-10", "2026-12-11", "2026-12-12"])
    assert [w for w in guards_v1.evaluate(wp) if w["code"] == guards_v1.CODE_HIIT_NEAR_MAX] == []
    assert _count(wp, "power_endurance", "power_endurance") >= 2


# ---------------------------------------------------------------------------
# guards_v1 — low_rest_days (decision 6)
# ---------------------------------------------------------------------------

def _plan_days(start, per_day):
    d0 = date.fromisoformat(start)
    return {"start_date": start, "profile_snapshot": {"hard_cap_per_week": 4},
            "weeks": [{"days": [{"date": (d0 + timedelta(days=k)).isoformat(),
                                 "sessions": copy.deepcopy(per_day.get(k, []))} for k in range(7)]}]}


EVE = {"slot": "evening", "session_id": "technique_focus_gym", "tags": {"hard": False, "finger": False}}
LUNCH = {"slot": "lunch", "session_id": "treadmill_zone2_cardio", "slot_role": "complementary",
         "focus": "z2", "tags": {"hard": False, "finger": False}}
PREHAB = {"slot": "evening", "session_id": "prehab_maintenance", "tags": {"hard": False, "finger": False}}


def _low(ws):
    return [w for w in ws if w["code"] == guards_v1.CODE_LOW_REST_DAYS]


class TestLowRestDays:
    def test_dense_week_alerts_once_week_level(self):
        p = _plan_days("2026-10-26", {k: [EVE] for k in (0, 1, 2, 3, 5, 6)} | {4: [EVE]})
        (w,) = _low(guards_v1.evaluate_week(p))
        assert w["scope"] == "week" and w["date"] == "2026-10-26"
        assert w["slot"] is None and w["session_id"] is None
        assert w["rest_days"] == 0 and w["min_rest_days"] == guards_v1.MIN_REST_DAYS == 2

    def test_lunch_only_and_prehab_only_days_are_rest(self):
        p = _plan_days("2026-10-26", {0: [EVE], 1: [EVE], 2: [EVE], 3: [EVE], 4: [LUNCH], 5: [EVE], 6: [PREHAB]})
        assert _low(guards_v1.evaluate_week(p)) == []

    def test_one_rest_day_alerts(self):
        p = _plan_days("2026-10-26", {0: [EVE], 1: [EVE, LUNCH], 2: [EVE], 3: [EVE], 4: [LUNCH], 5: [EVE], 6: [EVE]})
        (w,) = _low(guards_v1.evaluate_week(p))
        assert w["rest_days"] == 1 and w["rest_dates"] == ["2026-10-30"]

    def test_outdoor_and_skipped(self):
        per = {0: [EVE], 1: [EVE], 2: [EVE], 3: [EVE], 5: [EVE]}
        p = _plan_days("2026-10-26", per)
        assert _low(guards_v1.evaluate_week(p)) == []          # Fri + Sun empty
        p["weeks"][0]["days"][6]["outdoor_spot_name"] = "Arco"
        assert _low(guards_v1.evaluate_week(p))                  # outdoor Sunday is not rest
        p2 = _plan_days("2026-10-26", {**per, 4: [dict(EVE, status="skipped")], 6: [EVE]})
        (w,) = _low(guards_v1.evaluate_week(p2))                 # a skipped session never happened
        assert w["rest_dates"] == ["2026-10-30"]

    def test_week_over_no_alert_and_involves_false(self):
        p = _plan_days("2026-10-26", {k: [EVE] for k in range(7)})
        assert _low(guards_v1.evaluate_week(p, today="2026-11-02")) == []
        (w,) = _low(guards_v1.evaluate_week(p, today="2026-11-01"))
        assert not guards_v1.involves(w, "2026-10-26", "evening")
        assert not guards_v1.involves(w, "2026-10-26")

    def test_new_warnings_only_when_caused(self):
        before = _plan_days("2026-10-26", {0: [EVE], 1: [EVE], 2: [EVE], 3: [EVE], 5: [EVE]})
        after = _plan_days("2026-10-26", {0: [EVE], 1: [EVE], 2: [EVE], 3: [EVE], 5: [EVE], 6: [EVE]})
        fresh = guards_v1.new_warnings(guards_v1.evaluate_week(before), guards_v1.evaluate_week(after))
        assert [w["code"] for w in fresh] == [guards_v1.CODE_LOW_REST_DAYS]
        assert guards_v1.new_warnings(guards_v1.evaluate_week(after), guards_v1.evaluate_week(after)) == []

    def test_session_level_contract_never_carries_week_alerts(self):
        # The client matches guard_warnings per session with a null slot as a
        # wildcard: week alerts must never reach that list (review A305).
        p = _plan_days("2026-10-26", {k: [EVE] for k in range(7)})
        assert _low(guards_v1.evaluate(p)) == []
        assert _low(guards_v1.evaluate(p, include_week=True))

    def test_planner_week_carries_it(self):
        wp = plan("power_endurance", start_date="2026-10-26")
        assert _low(guards_v1.evaluate_week(wp))


def test_api_week_alerts_travel_apart():
    """Review A305: the live client reads ``guard_warnings`` per session (a null
    slot is a wildcard): week alerts go in ``week_guard_warnings`` only."""
    from backend.api.guard_status import build_guard_warnings, build_week_guard_warnings
    from backend.api.plan_revision import _SIBLING_KEYS

    p = _plan_days("2026-10-26", {k: [EVE] for k in range(7)})
    assert _low(build_guard_warnings({}, p, "2026-10-26")) == []
    (w,) = _low(build_week_guard_warnings({}, p, "2026-10-26"))
    assert w["scope"] == "week"
    assert "week_guard_warnings" in _SIBLING_KEYS
