"""A300 — complementary slots and the adaptive lunch rotation.

Daniele (2026-10-05): "non fare cose manuali, voglio che la struttura sia
adattativa". Six primary evenings (Mon, Tue, Wed, Thu, Sat, Sun), Friday evening
off, mornings off, lunches Tue–Fri at the Work gym (weights + cable + treadmill),
45' gross, complementary. The planner must put the climbing sessions of the
phase in the evenings and fill the lunches itself with a rotation of focus
families (legs, HIIT, Z2, push + arms), paired to the days by penalties:

- HIIT never the same day as, nor the day before, a max day; at most one a week;
  HIIT does not consume the hard-day cap;
- biceps not within 24 h before a heavy pull;
- legs not within 48 h before a limit session or an outdoor day;
- Z2 anywhere;
- a violation that cannot be avoided is reported (``secondary_warnings``), a
  slot that cannot be filled too (``unmet_secondary``): never silently.

Users without the new fields get byte-identical plans: checked against digests
produced on origin/main @ 87f99d8 (the fixture ``a300_identity_digests.json``,
180 cases) and by explicit ``role: "any"`` / ``"primary"`` equivalence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.engine import complementary_v1 as cv
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.planner_v2 import (
    _SESSION_META,
    _normalize_availability,
    _primary_view,
    generate_phase_week,
    session_duration_min,
)
from backend.engine.stimulus import (
    FAMILY_LIMIT_POWER,
    is_finger_hard_session,
    is_hiit_like,
    is_hiit_session,
    is_pulling_hard_session,
    is_test_session,
    session_stimuli,
)

REPO = Path(__file__).resolve().parents[2]
DIGESTS = REPO / "backend" / "tests" / "fixtures" / "a300_identity_digests.json"

PROFILE = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
           "technique": 50, "endurance": 40}
GYMS = [
    {"gym_id": "blocx", "priority": 1,
     "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder", "gym_routes", "pullup_bar"]},
    {"gym_id": "work", "priority": 5,
     "equipment": ["dumbbell", "barbell", "cable_machine", "treadmill", "pullup_bar"]},
]
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
PRIMARY_EVENINGS = ("mon", "tue", "wed", "thu", "sat", "sun")
LUNCH_DAYS = ("tue", "wed", "thu", "fri")
START = "2026-10-12"
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")
ROTATION = ["legs", "hiit", "z2", "upper_push_arms"]
PREFS = {"target_training_days_per_week": 6, "hard_day_cap_per_week": 3,
         "complementary_rotation": ROTATION}


def daniele_availability(lunch_role="complementary", max_minutes=45, evening_role="primary"):
    av = {}
    for d in DAYS:
        evening = {"available": d != "fri", "locations": ["gym"], "preferred_location": "gym",
                   "gym_id": "blocx"}
        if evening_role:
            evening["role"] = evening_role
        av[d] = {"morning": {"available": False}, "evening": evening}
        if d in LUNCH_DAYS:
            lunch = {"available": True, "locations": ["gym"], "preferred_location": "gym", "gym_id": "work"}
            if lunch_role:
                lunch["role"] = lunch_role
            if max_minutes is not None:
                lunch["max_minutes"] = max_minutes
            av[d]["lunch"] = lunch
        else:
            av[d]["lunch"] = {"available": False}
    return av


def plan(phase, availability=None, prefs=None, discipline="lead", **extra):
    return generate_phase_week(
        phase_id=phase,
        domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase], PROFILE),
        session_pool=_build_session_pool(phase, discipline),
        start_date=extra.pop("start_date", START),
        availability=availability if availability is not None else daniele_availability(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs=copy.deepcopy(prefs if prefs is not None else PREFS),
        default_gym_id="blocx",
        gyms=copy.deepcopy(GYMS),
        home_equipment=["hangboard", "pullup_bar"],
        **extra,
    )


def days_of(wp):
    return wp["weeks"][0]["days"]


def fingerprint(wp):
    p = json.loads(json.dumps(wp))
    p.pop("generated_at", None)
    return json.dumps(p, sort_keys=True)


SLOT_H = {"morning": 8, "lunch": 13, "evening": 19}


def _events(wp):
    out = []
    for i, d in enumerate(days_of(wp)):
        for s in d["sessions"]:
            if s.get("slot_role") == "complementary":
                continue
            out.append((i, i * 24 + SLOT_H[s["slot"]], s))
    return out


def rule_violations(wp):
    """Independent re-check of the three placement rules on a generated week."""
    bad = []
    ev = _events(wp)
    for i, d in enumerate(days_of(wp)):
        for s in d["sessions"]:
            if s.get("slot_role") != "complementary":
                continue
            t = i * 24 + SLOT_H[s["slot"]]
            sid = s["session_id"]
            if is_hiit_session(s):
                for j, _te, e in ev:
                    if j in (i, i + 1) and (is_finger_hard_session(e) or is_pulling_hard_session(e)
                                            or is_test_session(e) or e.get("intensity") == "max"):
                        bad.append(("hiit", d["date"], e["session_id"]))
            if sid in cv.BICEPS_SESSIONS:
                for _j, te, e in ev:
                    if 0 < te - t <= 24 and is_pulling_hard_session(e):
                        bad.append(("biceps", d["date"], e["session_id"]))
            if sid in cv.LEGS_SESSIONS:
                for _j, te, e in ev:
                    if 0 < te - t <= 48 and FAMILY_LIMIT_POWER in session_stimuli(e):
                        bad.append(("legs", d["date"], e["session_id"]))
    return bad


# ---------------------------------------------------------------------------
# Daniele-like structure
# ---------------------------------------------------------------------------

class TestDanieleStructure:
    @pytest.mark.parametrize("phase", PHASES)
    def test_evenings_primary_lunches_complementary(self, phase):
        wp = plan(phase)
        for d in days_of(wp):
            wd = d["weekday"]
            by_slot = {}
            for s in d["sessions"]:
                by_slot.setdefault(s["slot"], []).append(s)
            assert "morning" not in by_slot, (wd, by_slot)
            if wd in LUNCH_DAYS:
                lunch = by_slot.get("lunch") or []
                assert len(lunch) == 1, (phase, wd, lunch)
                s = lunch[0]
                assert s["slot_role"] == "complementary" and s["focus"] in cv.FOCUS_FAMILIES
                assert s["session_id"] in cv.FAMILY_SESSIONS[s["focus"]]
                assert s["gym_id"] == "work"
                assert session_duration_min(s["session_id"]) <= 45
                assert not s["tags"]["hard"] and not s["tags"]["finger"]
            else:
                assert "lunch" not in by_slot, (phase, wd)
            if wd == "fri":
                assert "evening" not in by_slot
            # Nothing but complementary sessions ever lands on a lunch.
            for s in by_slot.get("lunch", []):
                assert s.get("slot_role") == "complementary"
            for s in by_slot.get("evening", []):
                assert s.get("slot_role") is None and s["gym_id"] == "blocx"
        assert wp["unmet_secondary"] == []

    @pytest.mark.parametrize("phase", ("strength_power", "power_endurance"))
    def test_six_primary_evenings_and_four_rotated_lunches(self, phase):
        wp = plan(phase)
        evenings = {d["weekday"]: [s for s in d["sessions"] if s["slot"] == "evening"] for d in days_of(wp)}
        assert sorted(wd for wd, ss in evenings.items() if len(ss) == 1) == sorted(PRIMARY_EVENINGS)
        assert evenings["fri"] == []
        lunches = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert len(lunches) == 4
        assert sorted(s["focus"] for s in lunches) == sorted(ROTATION)
        assert sum(1 for s in lunches if is_hiit_like(s)) == 1
        # Every rule satisfied: the pairing adapted to the evenings, no alert.
        assert wp["secondary_warnings"] == []
        assert rule_violations(wp) == []

    def test_pairing_is_adaptive_not_fixed_weekdays(self):
        """The same rotation lands on different weekdays in SP and PE: the
        evenings decide, not a fixed calendar."""
        sp = {d["weekday"]: s["focus"] for d in days_of(plan("strength_power"))
              for s in d["sessions"] if s["slot"] == "lunch"}
        pe = {d["weekday"]: s["focus"] for d in days_of(plan("power_endurance"))
              for s in d["sessions"] if s["slot"] == "lunch"}
        assert sp != pe

    def test_deload_turns_hiit_into_z2(self):
        wp = plan("deload")
        lunches = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert len(lunches) == 4
        assert not any(is_hiit_like(s) for s in lunches)
        assert sum(1 for s in lunches if s["focus"] == "z2") == 2

    @pytest.mark.parametrize("phase", PHASES)
    def test_lunches_do_not_change_the_primaries_nor_the_hard_cap(self, phase):
        """Own budget: the evenings are exactly those of the same week without
        the lunches; HIIT does not consume the hard-day cap."""
        with_lunch = plan(phase)
        no_lunch_av = daniele_availability()
        for d in LUNCH_DAYS:
            no_lunch_av[d]["lunch"] = {"available": False}
        without = plan(phase, availability=no_lunch_av)
        strip = [[s for s in d["sessions"] if s.get("slot_role") != "complementary"] for d in days_of(with_lunch)]
        assert strip == [d["sessions"] for d in days_of(without)]
        assert with_lunch["weekly_load_summary"]["hard_days_count"] == \
            without["weekly_load_summary"]["hard_days_count"]

    @pytest.mark.parametrize("phase", PHASES)
    def test_deterministic(self, phase):
        assert fingerprint(plan(phase)) == fingerprint(plan(phase))

    def test_boulder_discipline_too(self):
        wp = plan("strength_power", discipline="boulder")
        lunches = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert len(lunches) == 4 and all(s.get("slot_role") == "complementary" for s in lunches)


# ---------------------------------------------------------------------------
# Rules, warnings, unmet
# ---------------------------------------------------------------------------

class TestRules:
    def test_unavoidable_violation_is_reported_not_dropped(self):
        """Performance: limit Thu evening and Sat evening, projecting Mon — no
        pairing satisfies all four families; the least penalised is used and
        the violation is an alert."""
        wp = plan("performance")
        lunches = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert len(lunches) == 4
        assert len(wp["secondary_warnings"]) >= 1
        w = wp["secondary_warnings"][0]
        assert {"date", "slot", "session_id", "focus", "code", "with"} <= set(w)
        assert w["code"] in ("hiit_near_max", "legs_before_limit", "biceps_before_heavy_pull")
        # The report matches an independent re-check of the rules.
        assert len(rule_violations(wp)) == len(wp["secondary_warnings"])

    def test_only_hiit_is_flagged_next_to_a_max(self):
        wp = plan("strength_power", prefs={**PREFS, "complementary_rotation": ["hiit"]})
        lunches = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert sum(1 for s in lunches if is_hiit_like(s)) == 1  # cap: the rest becomes Z2
        assert {s["focus"] for s in lunches} == {"hiit", "z2"}
        assert rule_violations(wp) == []

    def test_pinned_focus_is_kept_and_alerted(self):
        av = daniele_availability()
        # SP: Thursday evening is power_contact (max) → HIIT pinned on Wed/Thu breaks the rule.
        av["thu"]["lunch"]["focus"] = "hiit"
        wp = plan("strength_power", availability=av)
        thu = next(d for d in days_of(wp) if d["weekday"] == "thu")
        lunch = [s for s in thu["sessions"] if s["slot"] == "lunch"][0]
        assert lunch["session_id"] == "treadmill_hiit_4x4" and lunch["focus"] == "hiit"
        assert any(w["code"] == "hiit_near_max" and w["date"] == thu["date"] for w in wp["secondary_warnings"])
        # Still at most one HIIT in the week.
        assert sum(1 for d in days_of(wp) for s in d["sessions"] if is_hiit_like(s)) == 1

    def test_outdoor_day_counts_for_legs(self):
        av = daniele_availability(evening_role=None)
        av["sat"] = {"morning": {"available": True, "preferred_location": "outdoor", "locations": ["outdoor"]}}
        events = cv._classify_events(days_of(plan("base", availability=av)), _normalize_availability(av, ["gym", "home"]))
        assert any("outdoor" in e["kinds"] and e["date"] == "2026-10-17" for e in events)
        v = cv._violations("legs_maintenance_lunch", 4, "lunch", events)  # Fri 13:00 → Sat 08:00 = 19 h
        assert v and v[0]["code"] == "legs_before_limit"
        assert cv._violations("treadmill_zone2_cardio", 4, "lunch", events) == []

    def test_empty_rotation_leaves_slots_empty_and_reports(self):
        wp = plan("base", prefs={**PREFS, "complementary_rotation": [], "target_sessions_per_week": 14})
        lunches = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        # Not even PASS 2.2 with a big session target takes a complementary slot.
        assert lunches == []
        assert len(wp["unmet_secondary"]) == 4
        assert {u["reason"] for u in wp["unmet_secondary"]} == {"no_focus"}

    @pytest.mark.parametrize("phase", PHASES)
    def test_complementary_slots_are_never_taken_by_other_passes(self, phase):
        """Quality floors (2.5/2.6), PASS 2/2.2 and tests stay off the lunches."""
        prefs = {**PREFS, "complementary_rotation": [], "target_sessions_per_week": 14}
        for inject in (False, True):
            wp = plan(phase, prefs=prefs, inject_tests=inject)
            assert not [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]

    def test_phase_override_rotation(self):
        prefs = {**PREFS, "complementary_rotation_by_phase": {"power_endurance": ["z2", "upper_push_arms"]}}
        wp = plan("power_endurance", prefs=prefs)
        focus = sorted(s["focus"] for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch")
        assert set(focus) <= {"z2", "upper_push_arms"} and len(focus) == 4


# ---------------------------------------------------------------------------
# max_minutes
# ---------------------------------------------------------------------------

class TestMaxMinutes:
    def test_long_legs_sessions_never_fit_a_45_minute_lunch(self):
        assert session_duration_min("legs_strength") == 55
        assert session_duration_min("lower_body_gym") == 90
        for phase in PHASES:
            wp = plan(phase, prefs={**PREFS, "complementary_rotation": ["legs"] * 4})
            sids = {s["session_id"] for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"}
            assert sids <= {"legs_maintenance_lunch"}, sids
            # max_per_week 2 for legs_maintenance_lunch: the other two are reported.
            assert len(wp["unmet_secondary"]) == 2
            assert all(u["reason"] == "no_session_fits" for u in wp["unmet_secondary"])

    def test_a_longer_slot_admits_the_longer_session(self):
        av = daniele_availability(max_minutes=60)
        wp = plan("base", availability=av, prefs={**PREFS, "complementary_rotation": ["legs"] * 4})
        sids = [s["session_id"] for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert sids.count("legs_maintenance_lunch") == 2 and sids.count("legs_strength") == 2

    def test_max_minutes_on_an_evening_excludes_long_primaries(self):
        av = daniele_availability()
        for d in PRIMARY_EVENINGS:
            av[d]["evening"]["max_minutes"] = 70
        for phase in PHASES:
            wp = plan(phase, availability=av)
            for d in days_of(wp):
                for s in d["sessions"]:
                    dur = session_duration_min(s["session_id"])
                    assert dur is None or dur <= 70 or s["slot"] == "lunch", (phase, s["session_id"], dur)


# ---------------------------------------------------------------------------
# Identity for users without the new fields
# ---------------------------------------------------------------------------

def _identity_matrix():
    def av_split():
        a = {}
        for d in DAYS:
            a[d] = {"evening": {"available": d != "fri", "locations": ["gym"], "preferred_location": "gym",
                                "gym_id": "blocx"}}
            if d in LUNCH_DAYS:
                a[d]["lunch"] = {"available": True, "locations": ["gym"], "preferred_location": "gym",
                                 "gym_id": "work"}
            a[d]["morning"] = {"available": True, "locations": ["home"], "preferred_location": "home"}
        return a

    def av_evenings():
        return {d: {"evening": {"available": True, "locations": ["gym", "home"]}} for d in DAYS}

    def av_simple():
        return {d: {"available": True} for d in ("mon", "wed", "fri", "sat")}

    avs = {"split": av_split, "evenings": av_evenings, "simple": av_simple}
    prefs = [{"target_training_days_per_week": 6, "hard_day_cap_per_week": 3},
             {"target_training_days_per_week": 7, "hard_day_cap_per_week": 3, "target_sessions_per_week": 11},
             {"target_training_days_per_week": 4}]
    gyms = [{"gym_id": "blocx", "priority": 1,
             "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder", "gym_routes", "pullup_bar"]},
            {"gym_id": "work", "priority": 5,
             "equipment": ["dumbbell", "barbell", "cable_machine", "treadmill", "pullup_bar"]}]
    for an, af in avs.items():
        for pi, pr in enumerate(prefs):
            for ph in PHASES:
                for disc in ("lead", "boulder"):
                    for today in (None, "2026-10-15"):
                        yield f"{an}|{pi}|{ph}|{disc}|{today}", dict(
                            phase_id=ph, domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[ph], PROFILE),
                            session_pool=_build_session_pool(ph, disc), start_date=START, availability=af(),
                            allowed_locations=["home", "gym"], hard_cap_per_week=3, planning_prefs=dict(pr),
                            default_gym_id="blocx", gyms=copy.deepcopy(gyms),
                            home_equipment=["hangboard", "pullup_bar"], today=today,
                            inject_tests=(ph == "base" and today is None))


def _digest(wp):
    return hashlib.sha256(fingerprint(wp).encode()).hexdigest()[:16]


class TestIdentity:
    def test_byte_identical_to_origin_main(self):
        """180 plans without A300 fields hash exactly as on origin/main @ 87f99d8."""
        golden = json.loads(DIGESTS.read_text())
        got = {k: _digest(generate_phase_week(**kw)) for k, kw in _identity_matrix()}
        assert set(got) == set(golden)
        diff = sorted(k for k in got if got[k] != golden[k])
        assert diff == [], diff[:10]
        for k, kw in _identity_matrix():
            wp = generate_phase_week(**kw)
            assert "unmet_secondary" not in wp and "secondary_warnings" not in wp
            break

    @pytest.mark.parametrize("role", ["any", "primary", None])
    def test_role_any_or_primary_alone_changes_nothing(self, role):
        """Only ``complementary`` changes the passes; ``any``/``primary`` alone
        (and an invalid role) give the plan of a slot without the field."""
        base = daniele_availability(lunch_role=None, max_minutes=None, evening_role=None)
        tagged = copy.deepcopy(base)
        for d in DAYS:
            for sl in ("evening", "lunch"):
                if tagged[d][sl].get("available"):
                    tagged[d][sl]["role"] = role if role is not None else "bogus"
        for phase in PHASES:
            assert fingerprint(plan(phase, availability=base)) == fingerprint(plan(phase, availability=tagged))

    def test_primary_view_identity(self):
        norm = _normalize_availability(daniele_availability(lunch_role=None, max_minutes=None), ["gym", "home"])
        assert _primary_view(norm) is norm


# ---------------------------------------------------------------------------
# Regeneration mid-week: past untouched, HIIT cap counts what happened
# ---------------------------------------------------------------------------

class TestMidWeek:
    def test_past_days_get_nothing_and_past_hiit_counts(self):
        today = "2026-10-15"  # Thursday
        first = plan("base")
        existing = copy.deepcopy(first)
        tue = days_of(existing)[1]
        for s in tue["sessions"]:
            if s["slot"] == "lunch":
                s.update({"session_id": "treadmill_hiit_4x4", "focus": "hiit", "status": "done"})
        wp = plan("base", today=today, existing_week_plan=existing)
        for d in days_of(wp):
            if d["date"] < today:
                assert d["sessions"] == []
        future_lunch = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert len(future_lunch) == 2
        assert not any(is_hiit_like(s) for s in future_lunch)

    def test_without_existing_plan_mid_week_is_still_capped(self):
        wp = plan("base", today="2026-10-15")
        future_lunch = [s for d in days_of(wp) for s in d["sessions"] if s["slot"] == "lunch"]
        assert len(future_lunch) == 2
        assert sum(1 for s in future_lunch if is_hiit_like(s)) <= 1

    def test_existing_plan_of_another_week_is_ignored(self):
        other = copy.deepcopy(plan("base"))
        other["start_date"] = "2026-10-05"
        a = plan("base", today="2026-10-15", existing_week_plan=other)
        b = plan("base", today="2026-10-15")
        assert fingerprint(a) == fingerprint(b)


# ---------------------------------------------------------------------------
# Single HIIT source, key sessions, overrides, validation
# ---------------------------------------------------------------------------

class TestSingleSources:
    def test_hiit_predicate(self):
        assert is_hiit_like({"session_id": "treadmill_hiit_4x4"})
        assert not is_hiit_like({"session_id": "treadmill_zone2_cardio"})
        # Legacy custom: only the name says HIIT.
        assert is_hiit_like({"session_id": "custom_cs_x", "is_custom": True, "name": "Work — HIIT"})
        # An explicit tag wins over the name.
        assert not is_hiit_like({"session_id": "custom_cs_x", "name": "HIIT", "tags": {"hiit": False}})

    def test_athlete_context_uses_the_catalog_flag(self):
        from backend.engine.athlete_context import _session_view

        v = _session_view("2026-10-14", {"slot": "lunch", "session_id": "treadmill_hiit_4x4",
                                         "name": "Intervalli 4x4", "tags": {"hard": False, "finger": False}})
        assert v["hiit"] is True
        legacy = _session_view("2026-10-14", {"slot": "lunch", "session_id": "custom_cs_1", "is_custom": True,
                                              "name": "Work — HIIT"})
        assert legacy["hiit"] is True
        z2 = _session_view("2026-10-14", {"slot": "lunch", "session_id": "treadmill_zone2_cardio"})
        assert z2["hiit"] is False

    def test_family_sessions_exist_in_meta_and_catalog(self):
        for fam, sids in cv.FAMILY_SESSIONS.items():
            for sid in sids:
                assert sid in _SESSION_META, sid
                assert session_duration_min(sid) is not None, sid
        assert [sid for sids in cv.FAMILY_SESSIONS.values() for sid in sids
                if is_hiit_session({"session_id": sid})] == ["treadmill_hiit_4x4"]
        assert not any(_SESSION_META[s]["hard"] for sids in cv.FAMILY_SESSIONS.values() for s in sids)

    def test_key_session_proposals_skip_complementary_slots(self):
        from backend.engine import key_sessions_v1 as ks
        from backend.engine.replanner_v1 import apply_events
        from backend.tests.test_a294_key_sessions import WEEKDAYS as KW, _state

        def state(role):
            st = _state()
            st["week_plans"]["2026-10-05"] = apply_events(
                st["week_plans"]["2026-10-05"],
                [{"event_type": "mark_skipped", "date": "2026-10-09", "slot": "evening"}])
            for wd in KW:
                st["availability"][wd]["evening"]["available"] = False
                if role:
                    st["availability"][wd]["lunch"]["role"] = role
            return st

        free = ks.compute_key_status(state(None), "2026-10-06")["proposals"]
        assert any(p["slot"] == "lunch" for p in free)  # non-vacuous: lunch is the only slot
        assert ks.compute_key_status(state("complementary"), "2026-10-06")["proposals"] == []

    def test_weekly_override_keeps_the_slot_structure(self):
        from backend.engine.weekly_override import merge_override_into_availability

        av = daniele_availability()
        merged = merge_override_into_availability(av, {"days": {"wednesday": {
            "available": True, "slots": {"lunch": {"available": True, "location": "gym", "gym_id": "work"}}}}})
        assert merged["wed"]["lunch"]["role"] == "complementary"
        assert merged["wed"]["lunch"]["max_minutes"] == 45
        legacy = merge_override_into_availability(av, {"days": {"thursday": {"location": "gym", "gym_id": "work"}}})
        assert legacy["thu"]["lunch"]["role"] == "complementary"
        # No structure fields in → none out (identity).
        plain = daniele_availability(lunch_role=None, max_minutes=None, evening_role=None)
        merged = merge_override_into_availability(plain, {"days": {"wednesday": {
            "available": True, "slots": {"lunch": {"available": True, "location": "gym"}}}}})
        assert "role" not in merged["wed"]["lunch"]

    def test_validate_structure(self):
        assert cv.validate_structure(daniele_availability(), PREFS) == []
        assert cv.validate_structure({"tue": {"lunch": {"role": "lunch"}}}, None)
        assert cv.validate_structure({"tue": {"lunch": {"max_minutes": 5}}}, None)
        assert cv.validate_structure({"tue": {"lunch": {"max_minutes": True}}}, None)
        assert cv.validate_structure({"tue": {"lunch": {"focus": "biceps"}}}, None)
        assert cv.validate_structure(None, {"complementary_rotation": ["legs", "yoga"]})
        assert cv.validate_structure(None, {"complementary_rotation": "legs"})
        assert cv.validate_structure(None, {"complementary_rotation_by_phase": {"winter": ["z2"]}})
        assert cv.validate_structure(None, {"complementary_rotation_by_phase": {"deload": ["z2"]}}) == []
        # Legacy shapes stay valid.
        assert cv.validate_structure({"mon": True, "tue": {"available": True}}, {"target_training_days_per_week": 4}) == []

    def test_onboarding_model_rejects_bad_structure(self):
        from pydantic import ValidationError

        from backend.api.models import OnboardingData

        OnboardingData(availability=daniele_availability(), planning_prefs=PREFS)
        with pytest.raises(ValidationError):
            OnboardingData(availability={"tue": {"lunch": {"role": "pranzo"}}})


# ---------------------------------------------------------------------------
# API: PUT /api/state + GET /api/week — past immutable, structure applied
# ---------------------------------------------------------------------------

STATE_FIXTURE = REPO / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    from backend.api import deps
    from backend.api.main import app
    from backend.engine import storage

    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(STATE_FIXTURE, tmp_state)
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    return TestClient(app), deps


def _monday(offset_weeks=0) -> str:
    t = date.today()
    return (t - timedelta(days=t.weekday()) + timedelta(weeks=offset_weeks)).isoformat()


class TestApi:
    def test_put_state_validates_the_new_fields(self, api):
        client, _deps = api
        r = client.put("/api/state", json={"availability": {"tue": {"lunch": {"role": "pranzo"}}}})
        assert r.status_code == 422 and "role" in r.text
        r = client.put("/api/state", json={"planning_prefs": {"complementary_rotation": ["yoga"]}})
        assert r.status_code == 422
        r = client.put("/api/state", json={"availability": daniele_availability(),
                                           "planning_prefs": {"complementary_rotation": ROTATION}})
        assert r.status_code == 200, r.text
        assert r.json()["availability"]["tue"]["lunch"]["role"] == "complementary"

    def test_structure_change_regenerates_future_keeps_past(self, api, monkeypatch):
        from backend.api.routers import week as week_router

        client, deps = api
        st = deps.load_state(None)
        st["macrocycle"]["start_date"] = _monday(-1)
        st["macrocycle"].pop("pause", None)
        phases = st["macrocycle"].get("phases") or []
        phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), 6)
        st["week_plans"], st["current_week_plan"] = {}, None
        st.pop("weekly_overrides", None)
        deps.save_state(st, None)
        mon = _monday(0)
        wed = (date.fromisoformat(mon) + timedelta(days=2)).isoformat()
        monkeypatch.setattr(week_router, "_client_today", lambda t: wed)
        assert client.get(f"/api/week/0?today={wed}").status_code == 200

        # Monday and Tuesday happened: one done session each, Tuesday lunch a done HIIT.
        st = deps.load_state(None)
        cur = st["week_plans"][mon]
        days = cur["weeks"][0]["days"]
        days[0]["sessions"] = [{"slot": "evening", "session_id": "technique_focus_gym", "status": "done",
                                "location": "gym", "intensity": "medium", "tags": {"hard": False, "finger": False}}]
        days[1]["sessions"] = [{"slot": "lunch", "session_id": "treadmill_hiit_4x4", "status": "done",
                                "location": "gym", "gym_id": "work", "intensity": "high",
                                "tags": {"hard": False, "finger": False}}]
        st["current_week_plan"] = copy.deepcopy(cur)
        deps.save_state(st, None)
        past_before = copy.deepcopy(days[:2])

        equipment = copy.deepcopy(st["equipment"])
        equipment["gyms"] = copy.deepcopy(GYMS)
        r = client.put("/api/state", json={"equipment": equipment, "availability": daniele_availability(),
                                           "planning_prefs": {"target_training_days_per_week": 6,
                                                              "complementary_rotation": ROTATION}})
        assert r.status_code == 200, r.text
        r = client.get(f"/api/week/0?today={wed}")
        assert r.status_code == 200, r.text
        after = deps.load_state(None)["week_plans"][mon]
        a_days = after["weeks"][0]["days"]
        assert a_days[:2] == past_before  # past immutable, byte for byte
        lunches = [s for d in a_days[2:] for s in d["sessions"] if s["slot"] == "lunch"]
        assert lunches and all(s.get("slot_role") == "complementary" for s in lunches)
        assert not any(is_hiit_like(s) for s in lunches)  # Tuesday's HIIT was the week's one
        assert not [s for d in a_days[2:] for s in d["sessions"] if s["slot"] == "morning"]
        assert "unmet_secondary" in after
