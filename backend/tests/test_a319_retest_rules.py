"""A319 — retest rules: one gap for every test, no end-of-phase slip, the
combined test session, a weighted pull-up test only where there are weights.

Origin: climb-coach bug-inbox 2026-10-18 ("tests too close together": the
policy put Daniele's hang test on Thu 22/10 and the 2RM pull-up on Sat 24/10,
28-30 days after the 24/09 tests, two hard evenings in one week). Decided by
Daniele on 2026-10-18 after the Phase 1 analysis.

(a) ``retest_gap_days`` is 42 days after ANY test: the confidence is still
    computed and shown, it no longer moves a date. 28 days
    (``LOW_CONF_RETEST_D``) only for the early retest (two measured signals),
    whose row now says ``gap_days: 28``; ``retest_status.earliest_retest``
    follows the same rule, so the "not before" never contradicts a projected
    early retest.
(b) No one-week slip of the end-of-phase test: a week the gap keeps out of
    reach is ``blocked:gap``. ``end_of_phase_slipped`` / ``slipped:gap`` /
    ``slipped_to_week`` are never produced again, and the snapshots written
    before A319 still read unchanged.
(c) Both tests due and no day with two ordered slots → ONE session on ONE day,
    ``test_max_hang_pullup`` (max hang 7 s, then the 2RM, then the secondary
    measurements), under the rules of both tests; else the hang alone and the
    pull-up ``blocked:no_paired_slot`` — never the two tests on two days.
(d) ``test_max_weighted_pullup`` (and the combined session) need ``weight``:
    without it the 2RM block resolved to a non-test pull (B261 non-test
    fallback) and wrote no max. The legacy PASS 3 falls back to the bodyweight
    pull-up test on the day the 2RM would take but where it finds no weights,
    when no day takes it with weights.

Review (2026-10-20): the partner of a test the week keeps (the user's, or a
day the merge copies back) joins that day or waits (``TestKeptPartner``); the
legacy fallback is decided on the outcome, not on the week's raw equipment; a
gap-blocked end-of-phase / cycle-start week yields to the early retest when
that one's own floor falls in it; ``_slip_eligible()`` is the shape the old
code slipped; the combined only on days both tests allow, under the same-day
pulling-hard and 48 h finger-gap rules; ``change_gym`` on a test day is pinned
as it is (open decision).

Synthetic fixtures only (no real user state in the repo).
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date, timedelta

import pytest

from backend.engine import athlete_context as ac
from backend.engine import key_sessions_v1 as ks
from backend.engine import retest_policy as rp
from backend.engine import stimulus
from backend.engine.macro_position import position_on
from backend.engine.planner_v2 import (
    _COMBINED_TEST_SID,
    _RD_PULL_TEST_SIDS,
    _SESSION_META,
    _test_sid_axes,
    generate_phase_week,
)
from backend.engine.progression_v1 import apply_feedback, estimate_1rm_from_2rm
from backend.engine.replanner_v1 import apply_events, regenerate_preserving_completed
from backend.engine.resolve_session import resolve_session
from backend.tests import test_b400_retest_merge_view as b400
from backend.tests.test_a289_retest_policy import (
    _avail,
    _daniele,
    _decision,
    _due_1019,
    _kwargs,
    _macrocycle,
    _pe_week,
    _sessions,
    _strip_volatile,
    _test_days,
    _with_exposures,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

WS = "2026-10-19"
MON, TUE, WED, THU, FRI, SAT, SUN = (
    (date.fromisoformat(WS) + timedelta(days=i)).isoformat() for i in range(7)
)
HANG, PULL, COMBO = "test_max_hang_7s", "test_max_weighted_pullup", "test_max_hang_pullup"
LEGACY = ("end_of_phase_slipped", "slipped:gap", "slipped_to_week")
POOL = ["technique_focus_gym", "route_endurance_gym", "endurance_aerobic_gym"]  # no hard session
EVENINGS = {"availability": _avail(slots=("evening",))}
NO_WEIGHTS = {"home_equipment": ["hangboard", "pullup_bar"],
              "gyms": [{"gym_id": "g1", "equipment": ["gym_boulder", "gym_routes", "spraywall", "hangboard"]}]}
REASON = "End of the strength phase: measure what the block built."


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _due() -> dict:
    """The due decision of the end-of-SP week 19-25/10 (both axes, paired)."""
    dec = _decision(_due_1019(), WS)
    assert [r["session_id"] for r in dec["required_sessions"]] == [HANG, PULL]
    return dec


def _allowed(dec: dict, days) -> dict:
    dec = deepcopy(dec)
    for r in dec["required_sessions"]:
        r["allowed_dates"] = list(days)
    return dec


def _rows(plan: dict) -> list:
    return plan["profile_snapshot"]["retest_decisions"]["required_sessions"]


def _by_axis(plan: dict) -> dict:
    return {r["axis"]: r for r in _rows(plan)}


def _policy_tests(plan: dict) -> list:
    """(date, slot, session_id) of every policy test session in the week."""
    return sorted((d, s["slot"], s["session_id"]) for d, s in _sessions(plan)
                  if s["session_id"] in (HANG, PULL, COMBO))


def _failures(plan: dict) -> list:
    """What the SkippedTestsCard shows ("Couldn't schedule a test")."""
    return [s for s in plan.get("skipped_tests") or []
            if s.get("required") and s.get("reason") in ("no_placement_slot", "blocked:no_paired_slot")]


def _day(plan: dict, d_iso: str) -> dict:
    return next(d for d in plan["weeks"][0]["days"] if d["date"] == d_iso)


def _week_plan(start: str, sessions_by_date: dict, snapshot=None, adaptations=None) -> dict:
    ws = date.fromisoformat(start)
    days = []
    for i in range(7):
        d = (ws + timedelta(days=i)).isoformat()
        days.append({"date": d, "sessions": deepcopy(sessions_by_date.get(d, []))})
    plan = {"start_date": start, "weeks": [{"days": days}],
            "profile_snapshot": {"retest_decisions": snapshot} if snapshot else {}}
    if adaptations:
        plan["adaptations"] = adaptations
    return plan


def _combo_slot(status: str = "planned", **extra) -> dict:
    out = {"slot": "evening", "session_id": COMBO, "status": status,
           "tags": {"hard": True, "finger": True, "test": True}}
    out.update(extra)
    return out


def _with_signals(state: dict, exercise: str, dates: list, official: str = "2026-09-24") -> dict:
    state = deepcopy(state)
    state.setdefault("progression_counters", {})["retest_signals"] = {
        exercise: {"count": len(dates), "dates": list(dates), "last_date": dates[-1], "official_date": official},
    }
    return state


def _slip_eligible() -> dict:
    """End-of-SP week 19-25/10 (macrocycle from 14/09), both tests on 17/09:
    earliest 29/10 falls in the week AFTER it — exactly where the pre-A319
    code slipped the test (``slipped:gap``, then ``end_of_phase_slipped``)."""
    st = _daniele(macrocycle=_macrocycle("2026-09-14"))
    for key in ("max_strength", "pulling_strength"):
        st["tests"][key][-1]["date"] = "2026-09-17"
    return st


def _staggered() -> dict:
    """Both axes due in the end-of-SP week 19-25/10, the pull-up tested two
    days after the hang (10/09, 12/09): finger allowed 22-25/10, pulling
    24-25/10."""
    st = _daniele(macrocycle=_macrocycle("2026-09-14"))
    st["tests"]["max_strength"][-1]["date"] = "2026-09-10"
    st["tests"]["pulling_strength"][-1]["date"] = "2026-09-12"
    return st


# ---------------------------------------------------------------------------
# (a) one gap for every test, 28 days only for the early retest
# ---------------------------------------------------------------------------

class TestGap:
    def test_gap_is_42_days_whatever_the_confidence(self):
        assert rp.retest_gap_days("low") == rp.retest_gap_days("high") == rp.retest_gap_days(None) == 42
        assert (rp.HIGH_CONF_RETEST_D, rp.LOW_CONF_RETEST_D) == (42, 28)

    def test_low_and_high_confidence_give_the_same_earliest(self):
        low = _daniele()
        high = _with_exposures(low, {"finger_max": ["2026-09-10", "2026-09-17"],
                                     "pulling_max": ["2026-09-10", "2026-09-17"]})
        for st, conf in ((low, "low"), (high, "high")):
            dec = _decision(st, "2026-10-12")
            for axis in ("finger", "pulling"):
                row = dec["axes"][axis]
                assert (row["confidence"], row["gap_days"], row["earliest_date"]) == (conf, 42, "2026-11-05")
            status = rp.retest_status(st, "2026-10-04", finger_device="hangboard")
            assert {r["earliest_retest"] for r in status["axes"].values()} == {"2026-11-05"}
            assert {r["confidence"] for r in status["axes"].values()} == {conf}


class TestEarlyRetestFloor:
    """Two measured signals: earliest = max(last test + 28, last signal + 1)."""

    @pytest.mark.parametrize("confidence", ["low", "high"])
    @pytest.mark.parametrize("signals, today, first, week", [
        # the 28-day floor binds (signals early in the gap)
        (["2026-10-10", "2026-10-12"], "2026-10-13", "2026-10-22", "2026-10-19"),
        # the day after the last signal binds
        (["2026-10-25", "2026-10-27"], "2026-10-27", "2026-10-28", "2026-10-26"),
    ])
    def test_floor_gap_days_and_status_agree(self, confidence, signals, today, first, week):
        st = _daniele()
        if confidence == "high":
            st = _with_exposures(st, {"pulling_max": ["2026-09-10", "2026-09-17"]})
        st = _with_signals(st, "weighted_pullup", signals)
        dec = _decision(st, week, today=today)
        req = {r["axis"]: r for r in dec["required_sessions"]}
        assert set(req) == {"pulling"}
        row = req["pulling"]
        assert (row["trigger"], row["confidence"]) == (rp.TRIGGER_EARLY, confidence)
        assert (row["earliest_date"], row["gap_days"]) == (first, 28)
        assert row["allowed_dates"][0] == first
        assert dec["axes"]["pulling"]["earliest_date"] == "2026-10-22"  # last test + 28
        # The status card / athlete_context "not before" is the projected day.
        p = rp.retest_status(st, today, finger_device="hangboard")["axes"]["pulling"]
        assert p["earliest_retest"] == first
        assert (p["next_test"]["date"], p["next_test"]["trigger"]) == (first, rp.TRIGGER_EARLY)
        # The finger axis has no signal: the 42-day gap.
        assert rp.retest_status(st, today, finger_device="hangboard")["axes"]["finger"]["earliest_retest"] == "2026-11-05"

    def test_late_signals_never_push_the_not_before_past_the_gap(self):
        # Signals after the 42-day mark: the regular gap is the first day a
        # test may come (any trigger) — "not before" never goes past it.
        st = _with_signals(_daniele(), "weighted_pullup", ["2026-11-06", "2026-11-08"])
        p = rp.retest_status(st, "2026-11-08", finger_device="hangboard")["axes"]["pulling"]
        assert p["earliest_retest"] == "2026-11-05"

    def test_one_signal_keeps_the_gap(self):
        st = _with_signals(_daniele(), "weighted_pullup", ["2026-10-12"])
        p = rp.retest_status(st, "2026-10-13", finger_device="hangboard")["axes"]["pulling"]
        assert p["earliest_retest"] == "2026-11-05"

    @pytest.mark.parametrize("confidence", ["low", "high"])
    def test_early_retest_takes_a_gap_blocked_end_of_phase_week(self, confidence):
        # A319 review: end-of-SP week 19-25/10, tests on 24/09 (the
        # end-of-phase test is out of the 42-day reach) and two pull-up signals
        # by 15/10: the early retest's own floor (22/10) falls in the week, so
        # it takes the week — it used to fire the week after (the end-of-phase
        # trigger came first and was gap-blocked).
        st = _daniele(macrocycle=_macrocycle("2026-09-14"))
        if confidence == "high":
            st = _with_exposures(st, {"pulling_max": ["2026-09-10", "2026-09-17"]})
        st = _with_signals(st, "weighted_pullup", ["2026-10-10", "2026-10-15"])
        dec = _decision(st, WS, today="2026-10-18")
        assert [r["session_id"] for r in dec["required_sessions"]] == [PULL]
        row = dec["required_sessions"][0]
        assert (row["trigger"], row["confidence"]) == (rp.TRIGGER_EARLY, confidence)
        assert (row["earliest_date"], row["gap_days"], row["paired_with"]) == (THU, 28, None)
        assert row["allowed_dates"] == [THU, FRI, SAT, SUN]
        f = dec["axes"]["finger"]  # no evidence there: the gap-blocked end-of-phase test
        assert (f["status"], f["trigger"], f["skip_reason"], f["gap_days"]) == (
            "skipped", rp.TRIGGER_END_OF_PHASE, "blocked:gap", 42)
        # The week after does not take it again: it belongs to 19/10.
        nxt = _decision(st, "2026-10-26", today="2026-10-18")
        assert nxt["required_sessions"] == []
        assert nxt["axes"]["pulling"]["skip_reason"] == "deferred:earlier_week"
        # The card projects it there, and its "not before" agrees.
        p = rp.retest_status(st, "2026-10-18", finger_device="hangboard")["axes"]["pulling"]
        assert p["earliest_retest"] == THU
        assert (p["next_test"]["date"], p["next_test"]["trigger"]) == (THU, rp.TRIGGER_EARLY)
        # PASS 3a places it in that week (alone: the finger axis is not due).
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        assert [sid for _d, _s, sid in _policy_tests(plan)] == [PULL]
        assert _policy_tests(plan)[0][0] in (THU, FRI, SAT, SUN)

    def test_gap_blocked_week_stays_blocked_when_the_early_floor_is_later(self):
        # The last signal on Sunday 25/10: the early retest's first day (26/10)
        # is after the week — the end-of-phase week stays `blocked:gap`, the
        # early retest comes the week after, from its own first day.
        st = _with_signals(_daniele(macrocycle=_macrocycle("2026-09-14")), "weighted_pullup",
                           ["2026-10-12", "2026-10-25"])
        dec = _decision(st, WS, today="2026-10-25")
        assert dec["required_sessions"] == []
        p = dec["axes"]["pulling"]
        assert (p["trigger"], p["skip_reason"], p["gap_days"]) == (rp.TRIGGER_END_OF_PHASE, "blocked:gap", 42)
        nxt = _decision(st, "2026-10-26", today="2026-10-25")
        (row,) = nxt["required_sessions"]
        assert (row["trigger"], row["earliest_date"], row["gap_days"]) == (rp.TRIGGER_EARLY, "2026-10-26", 28)
        # The signals in time but the 28-day floor after the week (tests on
        # 01/10 → 29/10): the end-of-phase row stays, with its own gap.
        st = _daniele(macrocycle=_macrocycle("2026-09-14"))
        for key in ("max_strength", "pulling_strength"):
            st["tests"][key][-1]["date"] = "2026-10-01"
        st = _with_signals(st, "weighted_pullup", ["2026-10-10", "2026-10-15"], official="2026-10-01")
        p = _decision(st, WS, today="2026-10-18")["axes"]["pulling"]
        assert (p["trigger"], p["skip_reason"], p["gap_days"]) == (rp.TRIGGER_END_OF_PHASE, "blocked:gap", 42)
        (row,) = _decision(st, "2026-10-26", today="2026-10-18")["required_sessions"]
        assert (row["trigger"], row["earliest_date"], row["gap_days"]) == (rp.TRIGGER_EARLY, "2026-10-29", 28)


# ---------------------------------------------------------------------------
# (b) no slip: never produced, old snapshots read unchanged
# ---------------------------------------------------------------------------

def _phase_kwargs(state: dict, ws: str) -> dict:
    pos = position_on(state["macrocycle"], ws) or {}
    if not pos or pos.get("before_start") or pos.get("after_end"):
        return _kwargs("power_endurance", ws)
    return _kwargs(pos["phase_id"], ws, is_last_week_of_phase=bool(pos.get("is_last_week_of_phase")))


class TestNoSlip:
    @pytest.mark.parametrize("builder", [_daniele, _due_1019, _slip_eligible])
    def test_sweep_never_produces_the_slip(self, builder):
        st = builder()
        ws = date(2026, 9, 7)
        seen_due = 0
        while ws <= date(2027, 1, 4):
            w = ws.isoformat()
            for today in ("2026-09-07", w):
                dec = _decision(st, w, today=today)
                text = json.dumps(dec)
                assert not any(tok in text for tok in LEGACY), (w, today)
                assert rp.TRIGGER_END_OF_PHASE_SLIPPED not in {
                    r.get("trigger") for r in (dec or {}).get("axes", {}).values()}
            dec = _decision(st, w, today=w)
            if dec is not None:
                seen_due += len(dec["required_sessions"])
                plan = generate_phase_week(**_phase_kwargs(st, w), retest_decisions=dec)
                text = json.dumps({"snap": plan["profile_snapshot"]["retest_decisions"],
                                   "skipped": plan.get("skipped_tests"),
                                   "explain": [s.get("explain") for _d, s in _sessions(plan)]})
                assert not any(tok in text for tok in LEGACY), w
            status = rp.retest_status(st, w, finger_device="hangboard")
            assert not any(tok in json.dumps(status) for tok in LEGACY), w
            ws += timedelta(days=7)
        # Non-vacuity: the due fixture really schedules tests in the sweep.
        if builder is _due_1019:
            assert seen_due >= 2

    def test_slip_eligible_week_is_blocked_and_the_week_after_not_due(self):
        # The one shape the pre-A319 code slipped (earliest 29/10, in the week
        # after the end-of-SP week): checked with a mutant restoring the slip.
        st = _slip_eligible()
        dec = _decision(st, WS)
        assert dec["required_sessions"] == []
        assert {s["axis"]: (s["skip_reason"], s["trigger"]) for s in dec["skipped"]} == {
            "finger": ("blocked:gap", rp.TRIGGER_END_OF_PHASE), "pulling": ("blocked:gap", rp.TRIGGER_END_OF_PHASE)}
        assert {r["earliest_date"] for r in dec["axes"].values()} == {"2026-10-29"}
        assert not any("slipped_to_week" in row for row in dec["skipped"] + list(dec["axes"].values()))
        nxt = _decision(st, "2026-10-26")
        assert nxt["required_sessions"] == [] and nxt["skipped"] == []
        assert {r["status"] for r in nxt["axes"].values()} == {"not_due"}
        for today in ("2026-10-12", WS):
            for row in rp.retest_status(st, today, finger_device="hangboard")["axes"].values():
                assert row["next_test"] is None, (today, row["next_test"])

    def test_old_snapshot_reads_unchanged(self):
        # Prod shape written before A319: week 12/10 slipped, week 19/10 with
        # the split pair placed under the slipped trigger and the 28-day reason.
        old_reason = ("End-of-strength retest moved one week: the last test needs 28 days "
                      "before it can be repeated (low confidence).")
        st = _daniele()
        st["week_plans"] = {
            "2026-10-12": _week_plan("2026-10-12", {}, snapshot={
                "required_sessions": [],
                "skipped": [{"axis": a, "session_id": sid, "trigger": "end_of_phase", "reason": REASON,
                             "skip_reason": "slipped:gap", "slipped_to_week": WS}
                            for a, sid in (("finger", HANG), ("pulling", PULL))],
            }),
            WS: _week_plan(WS, {
                THU: [{"slot": "evening", "session_id": HANG, "tags": {"hard": True, "finger": True, "test": True}}],
                SAT: [{"slot": "evening", "session_id": PULL, "tags": {"hard": True, "finger": False, "test": True}}],
            }, snapshot={"required_sessions": [
                {"axis": "finger", "session_id": HANG, "trigger": rp.TRIGGER_END_OF_PHASE_SLIPPED,
                 "reason": old_reason, "status": "placed", "placed_date": THU, "placed_slot": "evening"},
                {"axis": "pulling", "session_id": PULL, "trigger": rp.TRIGGER_END_OF_PHASE_SLIPPED,
                 "reason": old_reason, "status": "placed", "placed_date": SAT, "placed_slot": "evening"},
            ]}),
        }
        st["week_plans"]["2026-10-12"]["skipped_tests"] = [
            {"test_id": HANG, "axis": "finger", "reason": "slipped:gap", "required": True,
             "source": "retest_policy", "trigger": "end_of_phase"}]
        status = rp.retest_status(st, WS, finger_device="hangboard")
        for axis, d in (("finger", THU), ("pulling", SAT)):
            nt = status["axes"][axis]["next_test"]
            assert (nt["source"], nt["date"]) == ("planned", d)
            assert (nt["trigger"], nt["reason"]) == (rp.TRIGGER_END_OF_PHASE_SLIPPED, old_reason)
        # The new decision of that week ignores the old snapshot: not due.
        assert _decision(st, WS)["required_sessions"] == []

    def test_old_skip_reason_of_a_generated_week_reads_unchanged(self):
        # A generated week whose snapshot carries the legacy skip: the
        # projection passes it through (`_generated_week_skip`), no crash. The
        # macrocycle ends after power_endurance (15/11): nothing else skips
        # before the official max expires (B400 keeps the last real skip).
        st = _due_1019()
        st["macrocycle"]["phases"] = st["macrocycle"]["phases"][:3]
        st["week_plans"] = {WS: _week_plan(WS, {}, snapshot={
            "required_sessions": [],
            "skipped": [{"axis": "finger", "session_id": HANG, "trigger": "end_of_phase",
                         "skip_reason": "slipped:gap", "slipped_to_week": "2026-10-26"}],
        })}
        f = rp.retest_status(st, WS, finger_device="hangboard")["axes"]["finger"]
        assert f["next_test"] is None
        assert f["next_test_reason"] == "slipped:gap"

    def test_legacy_constant_is_kept_and_has_no_text(self):
        assert rp.TRIGGER_END_OF_PHASE_SLIPPED == "end_of_phase_slipped"
        assert "TRIGGER_END_OF_PHASE_SLIPPED" in rp.__all__
        assert rp.TRIGGER_END_OF_PHASE_SLIPPED not in rp._TRIGGER_TEXT
        # A320: only the postponed test's text takes a value (its date).
        assert all("{" not in text for trig, text in rp._TRIGGER_TEXT.items() if trig != rp.TRIGGER_POSTPONED)
        assert rp._TRIGGER_TEXT[rp.TRIGGER_POSTPONED].format(until="2026-11-02").endswith("2026-11-02.")


# ---------------------------------------------------------------------------
# (c) the combined test session
# ---------------------------------------------------------------------------

class TestCombinedTables:
    def test_ids_and_tables_agree(self):
        assert _COMBINED_TEST_SID == rp.COMBINED_TEST_SESSION == COMBO
        assert COMBO in rp.AXIS_TEST_SESSIONS_ALL["finger"] and COMBO in rp.AXIS_TEST_SESSIONS_ALL["pulling"]
        assert _test_sid_axes(COMBO) == ("finger", "pulling")
        assert _test_sid_axes(HANG) == ("finger",) and _test_sid_axes(PULL) == ("pulling",)
        assert _test_sid_axes("technique_focus_gym") == ()
        assert COMBO in _RD_PULL_TEST_SIDS
        meta = _SESSION_META[COMBO]
        assert (meta["hard"], meta["finger"], meta["test"], meta["intensity"]) == (True, True, True, "high")
        assert "pulling" not in meta  # test_b308: derived from the catalog blocks
        assert meta["required_equipment"] == ["hangboard", "pullup_bar", "weight"]
        assert _SESSION_META[PULL]["required_equipment"] == ["pullup_bar", "weight"]

    def test_load_bearing_id(self):
        # progression (test_), key_sessions_v1 pending tests (test_max),
        # finger-test prefixes (test_max_hang), composer guard ("hang"/"pullup").
        assert COMBO.startswith("test_max_hang") and "pullup" in COMBO

    def test_done_combined_is_a_max_hang_and_a_heavy_pull_day_for_the_rotation(self):
        # A290 legacy fallback (a done test with no family in the logs): the
        # combined counts on both sides.
        from backend.engine import phase_anchor as pa

        st = {"week_plans": {"2026-10-12": _week_plan("2026-10-12", {"2026-10-16": [_combo_slot("done")]})}}
        since, until = date(2026, 10, 12), date(2026, 10, 18)
        assert pa._done_test_days(st, pa._FINGER_TEST_PREFIXES, since, until) == [date(2026, 10, 16)]
        assert pa._done_test_days(st, pa._PULL_TEST_PREFIXES, since, until) == [date(2026, 10, 16)]

    def test_unresolved_combined_delivers_both_stimuli(self):
        s = {"slot": "evening", "session_id": COMBO, "status": "planned",
             "tags": {"hard": True, "finger": True, "test": True}}
        assert stimulus.SESSION_FALLBACK_STIMULI[COMBO] == (stimulus.FAMILY_FINGER_MAX, stimulus.FAMILY_PULLING_MAX)
        assert stimulus.session_stimuli(s) == [stimulus.FAMILY_FINGER_MAX, stimulus.FAMILY_PULLING_MAX]
        assert stimulus.is_finger_hard_session(s) and stimulus.is_pulling_hard_session(s)
        assert stimulus.is_test_session(s)
        # The key status reads both keys from it (A294).
        assert ks.session_keys(s, "strength_power") == ["finger_max", "pulling_max"]


class TestCombinedPlacement:
    def test_evenings_only_gives_one_combined_session(self):
        plan = generate_phase_week(**_pe_week(retest_decisions=_due(), **EVENINGS))
        tests = _policy_tests(plan)
        assert len(tests) == 1 and tests[0][1:] == ("evening", COMBO)
        d, slot, _sid = tests[0]
        assert d in (THU, FRI, SAT, SUN)
        rows = _by_axis(plan)
        assert set(rows) == {"finger", "pulling"}
        for axis, order in (("finger", 1), ("pulling", 2)):
            r = rows[axis]
            assert (r["session_id"], r["status"], r["placed_date"], r["placed_slot"]) == (COMBO, "placed", d, slot)
            assert (r["combined"], r["paired_with"], r["order"]) == (True, None, order)
            assert (r["trigger"], r["reason"], r["earliest_date"]) == (rp.TRIGGER_END_OF_PHASE, REASON, THU)
            assert (r["confidence"], r["last_test_date"]) == ("low", "2026-09-10")
        assert _failures(plan) == []
        entry = next(s for _d, s in _sessions(plan) if s["session_id"] == COMBO)
        assert entry["tags"] == {"hard": True, "finger": True, "test": True}
        assert "pass3:retest_policy" in entry["explain"]
        assert entry["explain"][-4:] == ["retest:finger:end_of_phase", REASON, "retest:pulling:end_of_phase", REASON]
        assert "retest:end_of_phase" not in entry["explain"]
        assert not any(e.startswith("paired_with=") for e in entry["explain"])

    def test_each_axis_keeps_its_own_trigger(self):
        dec = _due()
        pull = dec["required_sessions"][1]
        pull.update(trigger=rp.TRIGGER_EARLY, reason=rp._TRIGGER_TEXT[rp.TRIGGER_EARLY], earliest_date=FRI)
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **EVENINGS))
        rows = _by_axis(plan)
        assert (rows["finger"]["trigger"], rows["pulling"]["trigger"]) == (rp.TRIGGER_END_OF_PHASE, rp.TRIGGER_EARLY)
        assert rows["pulling"]["earliest_date"] == FRI
        entry = next(s for _d, s in _sessions(plan) if s["session_id"] == COMBO)
        assert "retest:finger:end_of_phase" in entry["explain"]
        assert "retest:pulling:early_retest" in entry["explain"]
        assert rp._TRIGGER_TEXT[rp.TRIGGER_EARLY] in entry["explain"]

    def test_two_ordered_slots_still_give_the_pair(self):
        plan = generate_phase_week(**_pe_week(retest_decisions=_due()))
        tests = _policy_tests(plan)
        assert {sid for _d, _s, sid in tests} == {HANG, PULL}
        assert not any("combined" in r for r in _rows(plan))

    def test_heavy_pull_the_day_before_refuses_the_combined(self):
        dec = _allowed(_due(), [SUN])
        dec["heavy_pull_dates"] = [SAT]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **EVENINGS))
        assert _policy_tests(plan) == [(SUN, "evening", HANG)]
        rows = _by_axis(plan)
        assert (rows["finger"]["session_id"], rows["finger"]["status"]) == (HANG, "placed")
        assert (rows["pulling"]["session_id"], rows["pulling"]["skip_reason"]) == (PULL, "blocked:no_paired_slot")
        # Non-vacuity: 48 h exactly (Friday) leaves the combined in.
        dec["heavy_pull_dates"] = [FRI]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **EVENINGS))
        assert _policy_tests(plan) == [(SUN, "evening", COMBO)]

    def test_finger_hard_within_72h_refuses_both(self):
        # Sunday is free in the evenings week (non-vacuity: the combined goes
        # there); an external finger-hard day on Thursday, 3 days before (the
        # inclusive 72 h block), refuses it — both tests no_placement_slot.
        dec = _allowed(_due(), [SUN])
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **EVENINGS))
        assert _policy_tests(plan) == [(SUN, "evening", COMBO)]
        dec["finger_hard_dates"] = [THU]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **EVENINGS))
        assert _policy_tests(plan) == []
        assert {r["skip_reason"] for r in _rows(plan)} == {"no_placement_slot"}
        assert {(s["test_id"], s["reason"]) for s in _failures(plan)} == {
            (HANG, "no_placement_slot"), (PULL, "no_placement_slot")}

    def test_combined_only_on_a_day_both_tests_allow(self):
        # The two axes tested two days apart: the hang may go 22-25/10, the
        # 2RM only 24-25/10 (its own 42 days). The combined holds the 2RM, so
        # only Saturday or Sunday — never Thursday/Friday (2RM inside its gap).
        dec = _decision(_staggered(), WS)
        rows = {r["axis"]: r for r in dec["required_sessions"]}
        assert rows["finger"]["allowed_dates"] == [THU, FRI, SAT, SUN]
        assert rows["pulling"]["allowed_dates"] == [SAT, SUN]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, session_pool=POOL, **EVENINGS))
        tests = _policy_tests(plan)
        assert [sid for _d, _s, sid in tests] == [COMBO]
        assert tests[0][0] in (SAT, SUN)
        assert {r["placed_date"] for r in _rows(plan)} == {tests[0][0]}

    def test_hang_alone_keeps_its_own_days(self):
        # Neither the pair nor the combined (no weights): the hang alone goes
        # on its OWN allowed days (22-25/10; the 2RM's are 24-25/10). No
        # weekend availability here, so Thursday or Friday.
        dec = _decision(_staggered(), WS)
        kw = {"availability": _avail(days=("mon", "tue", "wed", "thu", "fri"), slots=("evening",)),
              "session_pool": POOL, **NO_WEIGHTS}
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **kw))
        tests = _policy_tests(plan)
        assert [sid for _d, _s, sid in tests] == [HANG] and tests[0][0] in (THU, FRI)
        assert _by_axis(plan)["pulling"]["skip_reason"] == "blocked:no_paired_slot"

    def test_combined_never_on_a_day_only_the_pull_allows(self):
        # Symmetric: the hang restricted to the weekend, the 2RM free all week.
        dec = deepcopy(_due())
        dec["required_sessions"][0]["allowed_dates"] = [SAT, SUN]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, session_pool=POOL, **EVENINGS))
        tests = _policy_tests(plan)
        assert [sid for _d, _s, sid in tests] == [COMBO]
        assert tests[0][0] in (SAT, SUN)

    def test_combined_never_next_to_the_users_pulling_hard_session(self):
        # Evenings + Sunday lunch, both tests allowed on Sunday only. Clean
        # week: the pair (hang at lunch, 2RM in the evening). With the user's
        # power_endurance_gym on Sunday evening (put back by the merge): no
        # pair, and the combined at lunch would put the 2RM next to a
        # pulling-hard session the same day — the hang alone, the pull-up
        # blocked:no_paired_slot.
        st = b400._due_state()
        av = _avail(slots=("evening",))
        av["sun"]["lunch"] = {"available": True, "locations": ["gym", "home"]}
        kw = {"availability": av, "session_pool": POOL}
        old = generate_phase_week(**_pe_week(**kw))
        _dec, fresh, _m = b400._regen(deepcopy(old), st, allowed=[SUN], **kw)
        assert _policy_tests(fresh) == [(SUN, "evening", PULL), (SUN, "lunch", HANG)]
        b400._put(old, SUN, b400._owned("power_endurance_gym", "evening"))
        _dec, fresh, merged = b400._regen(old, st, allowed=[SUN], **kw)
        assert _policy_tests(fresh) == [(SUN, "lunch", HANG)]
        assert _by_axis(fresh)["pulling"]["skip_reason"] == "blocked:no_paired_slot"
        assert _policy_tests(merged) == [(SUN, "lunch", HANG)]

    def test_combined_respects_the_48h_finger_gap_after_it(self):
        # Both tests allowed on Wednesday only (evenings): the combined goes
        # there in a clean week; the user's finger custom on Thursday evening
        # (48 h finger gap, both sides) refuses it.
        st = b400._due_state()
        kw = {"availability": _avail(slots=("evening",)), "session_pool": POOL}
        old = generate_phase_week(**_pe_week(**kw))
        _dec, fresh, _m = b400._regen(deepcopy(old), st, allowed=[WED], **kw)
        assert _policy_tests(fresh) == [(WED, "evening", COMBO)]
        b400._put(old, THU, b400._custom_finger("evening"))
        _dec, fresh, _m = b400._regen(old, st, allowed=[WED], **kw)
        assert _policy_tests(fresh) == []
        assert {r["skip_reason"] for r in _rows(fresh)} == {"no_placement_slot"}

    def test_no_weights_hang_alone(self):
        plan = generate_phase_week(**_pe_week(retest_decisions=_due(), **EVENINGS, **NO_WEIGHTS))
        tests = _policy_tests(plan)
        assert [sid for _d, _s, sid in tests] == [HANG]
        rows = _by_axis(plan)
        assert rows["pulling"]["skip_reason"] == "blocked:no_paired_slot"
        assert [(s["test_id"], s["reason"]) for s in _failures(plan)] == [(PULL, "blocked:no_paired_slot")]

    def test_finger_rules_and_hang_window_hold_for_the_combined(self):
        # Plan-wide: no finger-hard session in the 3 days before the combined.
        plan = generate_phase_week(**_pe_week(retest_decisions=_due(), **EVENINGS))
        (d, _slot, _sid), = _policy_tests(plan)
        td = date.fromisoformat(d)
        for day, s in _sessions(plan):
            gap = (td - date.fromisoformat(day)).days
            if 0 < gap <= 3:
                assert not stimulus.is_finger_hard_session(s), (day, s["session_id"])

    def test_legacy_pass3_finger_test_stays_out_of_the_combined_window(self):
        # `_rd_hang_offsets` holds the combined (it is a finger test): the
        # legacy repeater test never lands in the 3 days before it.
        st = _daniele()
        for k in ("max_strength", "pulling_strength"):
            st["tests"][k][-1]["date"] = "2026-08-20"
        dec = _allowed(rp.retest_decisions(st, "2026-10-12", today="2026-10-12", finger_device="hangboard"),
                       ["2026-10-16"])
        assert len(dec["required_sessions"]) == 2
        # Evenings Tue, Wed, Fri, Sun: the legacy pass would put the repeater
        # on Tuesday (its first day with a session), 3 days before Friday's
        # combined — checked with a mutant that leaves the combined out of
        # `_rd_hang_offsets`.
        kw = _kwargs("strength_power", "2026-10-12", is_last_week_of_phase=True, session_pool=POOL,
                     availability=_avail(days=("tue", "wed", "fri", "sun"), slots=("evening",)))
        plan = generate_phase_week(**kw, retest_decisions=dec)
        tests = _test_days(plan)
        assert tests[COMBO] == ("2026-10-16", "evening")
        rep = tests["test_repeater_7_3"]
        gap = (date(2026, 10, 16) - date.fromisoformat(rep[0])).days
        assert not 0 < gap <= 3, rep

    @pytest.mark.parametrize("slots", [("morning", "lunch", "evening"), ("evening",), ("morning",),
                                       ("lunch", "evening"), ("morning", "evening")])
    @pytest.mark.parametrize("days", [("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
                                      ("mon", "wed", "fri", "sun"), ("tue", "thu", "sat")])
    @pytest.mark.parametrize("extra", [{}, {"heavy_pull_dates": [THU]}, {"finger_hard_dates": [WED]},
                                       {"heavy_pull_dates": [SAT]}])
    @pytest.mark.parametrize("weights", [True, False])
    def test_hang_and_pull_tests_never_on_two_days(self, slots, days, extra, weights):
        dec = deepcopy(_due())
        dec.update(extra)
        kw = {"availability": _avail(days=days, slots=slots)}
        if not weights:
            kw.update(NO_WEIGHTS)
        for pool in (None, POOL):
            if pool:
                kw["session_pool"] = pool
            plan = generate_phase_week(**_pe_week(retest_decisions=dec, **kw))
            tests = _policy_tests(plan)
            assert len({d for d, _s, _sid in tests}) <= 1, tests
            placed = [r for r in _rows(plan) if r["status"] == "placed"]
            assert len({r["placed_date"] for r in placed}) <= 1
            if {sid for _d, _s, sid in tests} == {HANG, PULL}:
                rank = {"morning": 0, "lunch": 1, "evening": 2}
                slot = {sid: s for _d, s, sid in tests}
                assert rank[slot[HANG]] < rank[slot[PULL]]
            if not weights:
                assert COMBO not in {sid for _d, _s, sid in tests}
                assert PULL not in {sid for _d, _s, sid in tests}

    def test_daniele_like_week_combined_on_the_weights_evening(self):
        # Evenings at a gym without weights (Cocque-like: Tue-Thu, Sat, Sun),
        # Monday evening at a gym with dumbbells (Bkl-like), weekday lunches
        # complementary at a work gym without hangboard (45 min). Home has the
        # kit but no slot. A pool without hard sessions, so the equipment is
        # the only rule at play (a hard session on Tuesday would refuse Monday
        # by hard spacing, as for any hard test).
        gyms = [{"gym_id": "cocque", "priority": 1, "equipment": ["hangboard", "pullup_bar", "gym_boulder", "gym_routes"]},
                {"gym_id": "bkl", "priority": 2, "equipment": ["hangboard", "pullup_bar", "dumbbell", "gym_boulder"]},
                {"gym_id": "work", "priority": 3, "equipment": ["dumbbell", "barbell", "bench", "cable_machine"]}]

        def ev(gym):
            return {"available": True, "locations": ["gym"], "preferred_location": "gym", "gym_id": gym,
                    "role": "primary"}

        lunch = {"available": True, "locations": ["gym"], "preferred_location": "gym", "gym_id": "work",
                 "role": "complementary", "max_minutes": 45}
        avail = {"mon": {"evening": ev("bkl"), "lunch": lunch}, "tue": {"evening": ev("cocque"), "lunch": lunch},
                 "wed": {"evening": ev("cocque"), "lunch": lunch}, "thu": {"evening": ev("cocque"), "lunch": lunch},
                 "fri": {"lunch": lunch}, "sat": {"evening": ev("cocque")}, "sun": {"evening": ev("cocque")}}
        kw = dict(availability=avail, gyms=gyms, home_equipment=["hangboard", "pullup_bar", "dumbbell"],
                  default_gym_id="cocque", session_pool=POOL)
        whole = _allowed(_due(), [MON, TUE, WED, THU, FRI, SAT, SUN])
        plan = generate_phase_week(**_pe_week(retest_decisions=whole, **kw))
        assert _policy_tests(plan) == [(MON, "evening", COMBO)]
        entry = next(s for _d, s in _sessions(plan) if s["session_id"] == COMBO)
        assert (entry["location"], entry["gym_id"]) == ("gym", "bkl")
        assert {r["combined"] for r in _rows(plan)} == {True}
        # The real end-of-SP window (Thu-Sun) has no evening with weights:
        # the hang alone at Cocque, the 2RM waits — never on another evening.
        plan = generate_phase_week(**_pe_week(retest_decisions=_due(), **kw))
        tests = _policy_tests(plan)
        assert [sid for _d, _s, sid in tests] == [HANG]
        assert next(s for _d, s in _sessions(plan) if s["session_id"] == HANG)["gym_id"] == "cocque"
        assert _by_axis(plan)["pulling"]["skip_reason"] == "blocked:no_paired_slot"

    def test_deterministic(self):
        a = _strip_volatile(generate_phase_week(**_pe_week(retest_decisions=_due(), **EVENINGS)))
        b = _strip_volatile(generate_phase_week(**_pe_week(retest_decisions=deepcopy(_due()), **EVENINGS)))
        assert a == b

    def test_past_sessions_immutable_after_a_regeneration_placing_the_combined(self):
        old = generate_phase_week(**_pe_week(**EVENINGS))
        mon = {"slot": "evening", "session_id": "finger_strength_home", "status": "done",
               "actual_exercises": [{"exercise_id": "max_hang_7s", "used_total_load_kg": 104.5}],
               "feedback_summary": {"difficulty": "ok"}}
        tue = {"slot": "evening", "session_id": "technique_focus_gym", "status": "skipped"}
        _day(old, MON)["sessions"] = [deepcopy(mon)]
        _day(old, TUE)["sessions"] = [deepcopy(tue)]
        dec = _decision(_due_1019(), WS, today=WED)
        assert len(dec["required_sessions"]) == 2
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, today=WED, **EVENINGS))
        assert [sid for _d, _s, sid in _policy_tests(fresh)] == [COMBO]
        merged = regenerate_preserving_completed(old, fresh, preserve_before=WED)
        assert _day(merged, MON)["sessions"] == [mon]
        assert _day(merged, TUE)["sessions"] == [tue]
        assert [sid for _d, _s, sid in _policy_tests(merged)] == [COMBO]


class TestCombinedPolicyReads:
    def test_already_scheduled_for_both_axes_from_another_week(self):
        st = _due_1019()
        st["week_plans"] = {"2026-10-12": _week_plan("2026-10-12", {"2026-10-17": [_combo_slot()]})}
        dec = _decision(st, WS)
        assert dec["required_sessions"] == []
        assert dec["already_scheduled"] == [
            {"axis": "finger", "date": "2026-10-17", "trigger": rp.TRIGGER_END_OF_PHASE},
            {"axis": "pulling", "date": "2026-10-17", "trigger": rp.TRIGGER_END_OF_PHASE},
        ]
        # A skipped one schedules nothing.
        st["week_plans"]["2026-10-12"]["weeks"][0]["days"][5]["sessions"] = [_combo_slot("skipped")]
        assert len(_decision(st, WS)["required_sessions"]) == 2

    def test_status_reads_a_planned_combined_for_both_axes(self):
        early = rp._TRIGGER_TEXT[rp.TRIGGER_EARLY]
        st = _due_1019()
        st["week_plans"] = {WS: _week_plan(WS, {FRI: [_combo_slot()]}, snapshot={"required_sessions": [
            {"axis": "finger", "session_id": COMBO, "trigger": rp.TRIGGER_END_OF_PHASE, "reason": REASON,
             "status": "placed", "placed_date": FRI, "placed_slot": "evening", "combined": True},
            {"axis": "pulling", "session_id": COMBO, "trigger": rp.TRIGGER_EARLY, "reason": early,
             "status": "placed", "placed_date": FRI, "placed_slot": "evening", "combined": True},
        ]})}
        axes = rp.retest_status(st, WS, finger_device="hangboard")["axes"]
        for axis, trig, reason in (("finger", rp.TRIGGER_END_OF_PHASE, REASON), ("pulling", rp.TRIGGER_EARLY, early)):
            nt = axes[axis]["next_test"]
            assert (nt["source"], nt["date"], nt["session_id"]) == ("planned", FRI, COMBO)
            assert (nt["trigger"], nt["reason"]) == (trig, reason)

    def test_removed_combined_locks_its_date(self):
        # A legacy removal by id (no slot): the merge drops that id there again.
        # A320: the athlete took the combined test out of the week — both axes
        # are declined there (nothing left to place: the decisions skip the
        # lock computation); the merge's lock itself is unchanged.
        st = _due_1019()
        st["week_plans"] = {WS: _week_plan(WS, {}, adaptations=[
            {"type": "event", "event": {"event_type": "remove_session", "date": FRI, "session_ref": COMBO}}])}
        dec = _decision(st, WS, today=WS)
        assert dec["required_sessions"] == []
        assert {s["axis"]: s["skip_reason"] for s in dec["skipped"]} == {"finger": "declined", "pulling": "declined"}
        ws = date.fromisoformat(WS)
        assert FRI in rp._locked_by_merge(st, ws, ws)["locked_dates"]

    def test_users_combined_is_already_scheduled_for_both_axes(self):
        # Moved by the user (user-owned): the regeneration keeps it.
        st = _due_1019()
        old = generate_phase_week(**_pe_week(**EVENINGS))
        _day(old, THU)["sessions"] = [_combo_slot(constraints_applied=["user_moved"])]
        st["week_plans"] = {WS: deepcopy(old)}
        dec = _decision(st, WS, today="2026-10-18")
        assert dec["required_sessions"] == []
        assert {(r["axis"], r["date"]) for r in dec["already_scheduled"]} == {("finger", THU), ("pulling", THU)}
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old), **EVENINGS))
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(fresh), preserve_before=None)
        assert _policy_tests(merged) == [(THU, "evening", COMBO)]

    def test_kept_combined_between_as_of_and_the_floor_schedules_both_axes(self):
        # B400 path: the engine's combined is today (Friday); "regenerate from
        # tomorrow" copies Friday back. The policy (server's today) cannot tell
        # — PASS 3a reads the merged week: both axes already scheduled.
        st = _due_1019()
        old = generate_phase_week(**_pe_week(retest_decisions=_allowed(_due(), [FRI]), session_pool=POOL, **EVENINGS))
        assert _policy_tests(old) == [(FRI, "evening", COMBO)]
        st["week_plans"] = {WS: deepcopy(old)}
        dec = rp.retest_decisions(st, WS, today=FRI, finger_device="hangboard")
        assert [r["session_id"] for r in dec["required_sessions"]] == [HANG, PULL]  # the policy cannot tell
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old), today=SAT,
                                               session_pool=POOL, **EVENINGS))
        snap = fresh["profile_snapshot"]["retest_decisions"]
        assert snap["required_sessions"] == []
        assert {(r["axis"], r["date"]) for r in snap["already_scheduled"]} == {("finger", FRI), ("pulling", FRI)}
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(fresh), preserve_before=SAT)
        assert _policy_tests(merged) == [(FRI, "evening", COMBO)]
        assert _failures(merged) == []


# A climbing gym with a hangboard and no weights, a fitness gym with weights
# and no hangboard: no location holds both, so neither the pair nor the
# combined fits, but the 2RM alone fits at the fitness gym.
_SPLIT_GYMS = [{"gym_id": "climb", "priority": 1, "equipment": ["gym_boulder", "gym_routes", "hangboard"]},
               {"gym_id": "fit", "priority": 2, "equipment": ["dumbbell", "barbell", "bench"]}]


def _evening_at(gym_by_day: dict) -> dict:
    return {wd: {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym", "gym_id": g}}
            for wd, g in gym_by_day.items()}


def _split_kw(gym_by_day: dict) -> dict:
    return dict(availability=_evening_at(gym_by_day), gyms=_SPLIT_GYMS, default_gym_id="climb",
                home_equipment=[], session_pool=POOL, allowed_locations=["gym"])


class TestKeptPartner:
    """A319 review: the partner of a test kept in the week (the user's, or a
    day the merge copies back) joins that test's day or waits — the B400 path
    used to place it alone on any allowed day (the 22/10 + 24/10 shape)."""

    def _pull_alone_fits_on_saturday(self, kw: dict) -> None:
        # Non-vacuity: the 2RM alone (loading pin: only the pulling axis is
        # covered) does fit on Saturday at the fitness gym.
        dec = rp.retest_decisions(_due_1019(), WS, today="2026-10-18", finger_device="loading_pin")
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **kw))
        entry = next(s for _d, s in _sessions(plan) if s["session_id"] == PULL)
        assert (_policy_tests(plan), entry["gym_id"]) == ([(SAT, "evening", PULL)], "fit")

    def test_regenerate_from_tomorrow_on_the_lone_hangs_day(self):
        kw = _split_kw({"thu": "climb", "fri": "climb", "sat": "fit", "sun": "climb"})
        self._pull_alone_fits_on_saturday(kw)
        st = _due_1019()
        old = generate_phase_week(**_pe_week(retest_decisions=_decision(st, WS, today="2026-10-18"), **kw))
        assert _policy_tests(old) == [(THU, "evening", HANG)]
        assert _by_axis(old)["pulling"]["skip_reason"] == "blocked:no_paired_slot"
        # Thursday: "regenerate from tomorrow" (the recommended option) copies
        # Thursday back — the hang is kept, the 2RM must not go on Saturday.
        st["week_plans"] = {WS: deepcopy(old)}
        dec = rp.retest_decisions(st, WS, today=THU, finger_device="hangboard")
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old), today=FRI, **kw))
        snap = fresh["profile_snapshot"]["retest_decisions"]
        assert snap["already_scheduled"] == [{"axis": "finger", "date": THU, "trigger": rp.TRIGGER_END_OF_PHASE}]
        assert [(r["session_id"], r["status"], r["skip_reason"]) for r in snap["required_sessions"]] == [
            (PULL, "skipped", "blocked:no_paired_slot")]
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(fresh), preserve_before=FRI)
        assert _policy_tests(merged) == [(THU, "evening", HANG)]
        for d_iso in (MON, TUE, WED, THU):  # the days before the floor, as they were
            assert _day(merged, d_iso) == _day(old, d_iso)

    def test_user_moved_lone_hang_the_pull_never_goes_on_another_day(self):
        kw = _split_kw({"wed": "climb", "thu": "climb", "sat": "fit", "sun": "climb"})
        self._pull_alone_fits_on_saturday(kw)
        st = _due_1019()
        old = generate_phase_week(**_pe_week(retest_decisions=_decision(st, WS, today="2026-10-18"), **kw))
        assert _policy_tests(old) == [(THU, "evening", HANG)]
        hang = next(s for s in _day(old, THU)["sessions"] if s["session_id"] == HANG)
        _day(old, THU)["sessions"].remove(hang)
        _day(old, WED)["sessions"] = [{**hang, "constraints_applied": ["user_moved"]}]
        st["week_plans"] = {WS: deepcopy(old)}
        dec = rp.retest_decisions(st, WS, today=MON, finger_device="hangboard")
        assert [(r["session_id"], r["paired_with"]) for r in dec["required_sessions"]] == [(PULL, None)]
        assert dec["already_scheduled"] == [{"axis": "finger", "date": WED, "trigger": rp.TRIGGER_END_OF_PHASE}]
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old), today=MON, **kw))
        assert _by_axis(fresh)["pulling"]["skip_reason"] == "blocked:no_paired_slot"
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(fresh), preserve_before=MON)
        assert _policy_tests(merged) == [(WED, "evening", HANG)]

    @pytest.mark.parametrize("setup", ["split_gyms", "evenings", "all_slots"])
    @pytest.mark.parametrize("kept", [(HANG, THU, "evening"), (HANG, FRI, "morning"), (HANG, SAT, "lunch"),
                                      (PULL, SUN, "evening"), (PULL, FRI, "morning")])
    def test_a_user_moved_test_and_its_partner_never_on_two_days(self, setup, kept):
        kw = {"split_gyms": _split_kw({"thu": "climb", "fri": "climb", "sat": "fit", "sun": "climb"}),
              "evenings": {"availability": _avail(slots=("evening",)), "session_pool": POOL},
              "all_slots": {}}[setup]
        st = b400._due_state()
        sid, d_iso, slot = kept
        old = generate_phase_week(**_pe_week(**kw))
        b400._put(old, d_iso, b400._owned(sid, slot, marker="user_moved",
                                          tags={"hard": True, "finger": sid == HANG, "test": True}))
        for today, floor in ((None, None), (MON, MON), (WED, THU)):
            _dec, fresh, merged = b400._regen(old, st, today=today, floor=floor, **kw)
            days = {d for d, _s, _sid in _policy_tests(merged)}
            assert days == {d_iso}, (today, _policy_tests(merged))

    @pytest.mark.parametrize("setup", ["split_gyms", "evenings", "all_slots"])
    @pytest.mark.parametrize("today", [THU, FRI, SAT])
    def test_regenerate_from_tomorrow_never_splits_the_tests(self, setup, today):
        kw = {"split_gyms": _split_kw({"thu": "climb", "fri": "climb", "sat": "fit", "sun": "climb"}),
              "evenings": {"availability": _avail(slots=("evening",)), "session_pool": POOL},
              "all_slots": {}}[setup]
        st = _due_1019()
        old = generate_phase_week(**_pe_week(retest_decisions=_decision(st, WS, today="2026-10-18"), **kw))
        floor = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
        st["week_plans"] = {WS: deepcopy(old)}
        dec = rp.retest_decisions(st, WS, today=today, finger_device="hangboard")
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old), today=floor, **kw))
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(fresh), preserve_before=floor)
        # A test left on a past day and never marked done was missed (B390):
        # the merge keeps it as it was (immutable), the policy places it again.
        live = [t for t in _policy_tests(merged) if t[0] >= today]
        assert len({d for d, _s, _sid in live}) <= 1, _policy_tests(merged)


class TestCombinedGuards:
    def test_athlete_context_flags_both_tests_before_a_combined(self):
        from backend.tests.test_a293_athlete_context import _sess, _state

        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][5]["sessions"] = [
            _sess("evening", COMBO, tags={"hard": True, "finger": True, "test": True})]
        ctx = ac.build_athlete_context(st, "2026-10-08")
        thu = next(r for r in ctx["guards"]["days"] if r["date"] == "2026-10-08")
        assert "hang_test_soon" in {c["code"] for c in thu["finger_codes"]}
        assert "pull_test_soon" in {c["code"] for c in thu["pull_codes"]}
        assert thu["finger_max_ok"] is False and thu["heavy_pull_ok"] is False
        assert ctx["version"] == ac.VERSION == "a320.1"

    def test_composer_guard_excludes_finger_and_pulling(self):
        from backend.tests.test_a294_key_sessions import _sess, _state

        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][6]["sessions"] = [
            _sess("evening", COMBO, tags={"hard": True, "finger": True, "test": True})]
        g = ks.composer_guard(st, "2026-10-10")
        assert "max_hang_7s" in g["exclude_ids"] and "weighted_pullup" in g["exclude_ids"]
        assert any(w["code"] == "pre_test" for w in g["warnings"])


# ---------------------------------------------------------------------------
# The catalog session: resolution and the test log
# ---------------------------------------------------------------------------

def _fixture_state(location: str, gym_id=None, home=None, gyms=None) -> dict:
    with open(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json")) as f:
        us = json.load(f)
    us.setdefault("context", {})["location"] = location
    us["context"]["gym_id"] = gym_id
    if home is not None:
        us["equipment"]["home"] = home
    if gyms is not None:
        us["equipment"]["gyms"] = gyms
    return us


def _resolve(session_id: str, us: dict, phase: str) -> dict:
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=f"backend/catalog/sessions/v1/{session_id}.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path=f"output/__test_a319_{session_id}.json",
        user_state_override=us,
        write_output=False,
        phase=phase,
    )


_WEIGHTS_STATES = {
    "home": lambda: _fixture_state("home", home=["hangboard", "pullup_bar", "dumbbell"]),
    "gym": lambda: _fixture_state("gym", "bkl_like", gyms=[
        {"gym_id": "bkl_like", "equipment": ["hangboard", "pullup_bar", "dumbbell", "gym_boulder"]}]),
}
_TEST_ORDER = ["max_hang_7s", "weighted_pullup", "test_max_hang_duration_20mm", "test_l_sit_hold",
               "test_hip_flexibility"]


class TestCatalogSession:
    @pytest.mark.parametrize("where", sorted(_WEIGHTS_STATES))
    @pytest.mark.parametrize("phase", ["strength_power", "power_endurance", "base"])
    def test_resolves_in_order_with_the_real_2rm(self, where, phase):
        out = _resolve(COMBO, _WEIGHTS_STATES[where](), phase)
        assert out["resolution_status"] == "success"
        rs = out["resolved_session"]
        ids = [i["exercise_id"] for i in rs["exercise_instances"]]
        assert "weighted_pullup" in ids and not {"archer_pullup", "dip"} & set(ids)
        # Instance order (A121 sort + after_warmup): the 2RM right after the
        # max hang, before every secondary measurement.
        pos = {e: ids.index(e) for e in _TEST_ORDER}
        assert pos["weighted_pullup"] == pos["max_hang_7s"] + 1
        assert pos["weighted_pullup"] < min(pos[e] for e in _TEST_ORDER[2:])
        assert ids.index("dead_hang_easy") < pos["max_hang_7s"]
        # Block order (what the guided player walks): general warm-up, finger
        # warm-up, max hang, 2RM, measurements, prehab, cool-down.
        blocks = [b["block_uid"] for b in rs["blocks"]]
        assert blocks[:3] == ["general_warmup.pulse_raise", "general_warmup.mobility", "general_warmup.upper_activation"]
        assert blocks[3:10] == ["inline.finger_warmup", "inline.max_hang_test", "inline.pullup_2rm_test",
                                "inline.test_hang_duration", "inline.test_l_sit", "inline.test_hip_flexibility",
                                "inline.cooldown_prehab"]
        assert all(b.startswith("cooldown_stretch.") for b in blocks[10:]) and blocks[10:]

    @pytest.mark.parametrize("where", sorted(_WEIGHTS_STATES))
    def test_each_test_measured_as_in_its_own_session(self, where):
        combo = {i["exercise_id"]: i for i in _resolve(COMBO, _WEIGHTS_STATES[where](), "strength_power")[
            "resolved_session"]["exercise_instances"]}
        for sid, shared in ((HANG, ("dead_hang_easy", "max_hang_7s", "test_max_hang_duration_20mm",
                                    "test_hip_flexibility", "wrist_curl")),
                            (PULL, ("weighted_pullup", "test_l_sit_hold"))):
            own = {i["exercise_id"]: i for i in _resolve(sid, _WEIGHTS_STATES[where](), "strength_power")[
                "resolved_session"]["exercise_instances"]}
            for eid in shared:
                a, b = dict(combo[eid]["prescription"]), dict(own[eid]["prescription"])
                if eid == "weighted_pullup":  # + the rest note between the two max efforts
                    assert a.pop("notes").startswith("Rest 5 full minutes after your last max hang")
                    assert own[eid]["prescription"]["notes"] in combo[eid]["prescription"]["notes"]
                    b.pop("notes")
                assert a == b, (sid, eid)
                assert combo[eid].get("suggested") == own[eid].get("suggested"), (sid, eid)
                assert combo[eid]["load_model"] == own[eid]["load_model"]

    def test_catalog_file(self):
        with open(os.path.join(REPO_ROOT, "backend", "catalog", "sessions", "v1", f"{COMBO}.json")) as f:
            data = json.load(f)
        assert data["id"] == COMBO and data["tags"] == {"test": True}
        assert data["intent"]["primary_goal"] == "finger_max_strength"
        assert data["intent"]["secondary_goals"] == ["pulling_strength"]
        assert data["required_equipment"] == _SESSION_META[COMBO]["required_equipment"]
        # Two test sessions minus one warm-up: longer than either, shorter than both.
        assert 60 < data["time_budget"]["hard_cap_min"] < 60 + 65
        pinned = {m.get("block_id"): m for m in data["modules"] if not m.get("template_id")}
        assert {b for b, m in pinned.items() if m.get("order") == "after_warmup"} == {
            "finger_warmup", "max_hang_test", "pullup_2rm_test"}


def _test_state() -> dict:
    return {
        "body": {"weight_kg": 77.0}, "bodyweight_kg": 77.0,
        "assessment": {"body": {"weight_kg": 77.0}, "tests": {}, "self_eval": {}},
        "working_loads": {"entries": [
            {"key": "max_hang_7s", "exercise_id": "max_hang_7s", "setup": {}, "last_external_load_kg": 35.0},
            {"key": "weighted_pullup", "exercise_id": "weighted_pullup", "setup": {}, "last_external_load_kg": 30.0},
        ]},
        "tests": {}, "baselines": {},
    }


_ITEMS = [
    {"exercise_id": "max_hang_7s", "used_external_load_kg": 41.0, "used_total_load_kg": 118.0, "feedback_label": "ok"},
    {"exercise_id": "weighted_pullup", "used_external_load_kg": 48.0, "used_total_load_kg": 125.0,
     "feedback_label": "ok"},
]


class TestCombinedTestLog:
    """No progression_v1 change: one combined log writes BOTH official maxes."""

    @pytest.mark.parametrize("payload", ["guided", "dialog"])
    def test_one_log_writes_both_maxes(self, payload):
        log = {"date": "2026-10-25", "actual": {"exercise_feedback_v1": deepcopy(_ITEMS)}}
        if payload == "guided":
            log["planned"] = [{"session_id": COMBO, "tags": {"test": True}, "exercise_instances": []}]
        else:  # the /today and /week dialog: no planned, the session id only
            log["session_id"] = COMBO
        out = apply_feedback(log, _test_state())
        hang = out["tests"]["max_strength"][-1]
        pull = out["tests"]["pulling_strength"][-1]
        assert (hang["test_id"], hang["date"], hang["total_load_kg"]) == ("max_hang_7s_total_load", "2026-10-25", 118.0)
        assert (pull["test_id"], pull["date"], pull["total_load_2rm_kg"]) == ("weighted_pullup_2rm", "2026-10-25", 125.0)
        assert out["baselines"]["hangboard"][0]["max_total_load_kg"] == 118.0
        assert out["baselines"]["pulling"]["weighted_pullup_2rm_total_kg"] == 125.0
        assert out["assessment"]["tests"]["weighted_pullup_1rm_total_kg"] == estimate_1rm_from_2rm(125.0)
        # B363: a test retires the training memory of both test exercises.
        assert {e["exercise_id"] for e in out["working_loads"]["entries"]} & {"max_hang_7s", "weighted_pullup"} == set()
        # Both axes are tested from that day on.
        assert rp.is_tested(out, rp.PROTOCOL_HANG_7S, "2026-10-26")
        assert rp.is_tested(out, rp.PROTOCOL_PULLUP_2RM, "2026-10-26")

    def test_a_training_session_writes_no_official_max(self):
        log = {"date": "2026-10-25", "session_id": "strength_long",
               "actual": {"exercise_feedback_v1": deepcopy(_ITEMS)}}
        out = apply_feedback(log, _test_state())
        assert not (out.get("tests") or {}).get("max_strength")
        assert not (out.get("tests") or {}).get("pulling_strength")
        assert "weighted_pullup_2rm_total_kg" not in (out.get("assessment") or {}).get("tests", {})


# ---------------------------------------------------------------------------
# (d) the weighted pull-up test needs weights
# ---------------------------------------------------------------------------

class TestPullTestEquipment:
    def _pull_only(self) -> dict:
        # Loading pin: only the pulling axis is covered — the 2RM test alone.
        dec = rp.retest_decisions(_due_1019(), WS, today="2026-10-18", finger_device="loading_pin")
        assert [r["session_id"] for r in dec["required_sessions"]] == [PULL]
        return dec

    def test_refused_without_weights(self):
        plan = generate_phase_week(**_pe_week(retest_decisions=self._pull_only(), **NO_WEIGHTS))
        assert PULL not in _test_days(plan)
        assert _by_axis(plan)["pulling"]["skip_reason"] == "no_placement_slot"

    def test_placed_where_a_dumbbell_implies_weight(self):
        gyms = [{"gym_id": "g1", "equipment": ["gym_boulder", "hangboard", "dumbbell"]}]
        plan = generate_phase_week(**_pe_week(retest_decisions=self._pull_only(), gyms=gyms,
                                              home_equipment=["hangboard", "pullup_bar"]))
        assert PULL in _test_days(plan)
        entry = next(s for _d, s in _sessions(plan) if s["session_id"] == PULL)
        assert (entry["location"], entry["gym_id"]) == ("gym", "g1")

    def test_legacy_pass3_falls_back_to_the_bodyweight_test_without_weights(self):
        # Untested athlete (no decisions): the end-of-SP week of the legacy pass.
        kw = _kwargs("strength_power", "2026-10-12", is_last_week_of_phase=True, **NO_WEIGHTS)
        tests = _test_days(generate_phase_week(**kw))
        assert "test_pullup_bw" in tests and PULL not in tests
        # A day whose slot has weights and passes the 2RM's rules → the 2RM,
        # where the weights are.
        kw = _kwargs("strength_power", "2026-10-12", is_last_week_of_phase=True, home_equipment=["hangboard", "pullup_bar"],
                     gyms=[{"gym_id": "g1", "equipment": ["gym_boulder", "hangboard", "dumbbell"]}])
        plan = generate_phase_week(**kw)
        tests = _test_days(plan)
        assert PULL in tests and "test_pullup_bw" not in tests
        assert next(s for _d, s in _sessions(plan) if s["session_id"] == PULL)["location"] == "gym"

    @pytest.mark.parametrize("phase, last, inject", [("strength_power", True, False), ("power_endurance", False, True)])
    @pytest.mark.parametrize("extra", [{}, {"availability": _avail(slots=("evening",))}, {"session_pool": POOL}])
    def test_legacy_bodyweight_test_takes_the_day_of_the_2rm(self, phase, last, inject, extra):
        # Without weights, the bodyweight test goes exactly where the 2RM goes
        # with them: the first day the 2RM passes every rule of the pass.
        kw = _kwargs(phase, "2026-10-12", is_last_week_of_phase=last, inject_tests=inject, **extra)
        with_weights = _test_days(generate_phase_week(**kw))
        without = _test_days(generate_phase_week(**{**kw, **NO_WEIGHTS}))
        assert PULL not in without and "test_pullup_bw" not in with_weights
        assert without["test_pullup_bw"] == with_weights[PULL]

    @pytest.mark.parametrize("inject", [False, True])
    def test_legacy_pass3_bodyweight_test_when_the_weights_day_is_taken(self, inject):
        # A319 review: Daniele-like gyms — weights only at the Monday gym
        # (Bkl-like), every other evening at a gym without them. The legacy
        # pass puts the hang test on Monday (one test per day): the 2RM finds
        # no other day with weights. It used to be dropped silently (an
        # optional test, never shown); now the bodyweight test goes where the
        # 2RM would have gone (Saturday at the gym without weights), also on
        # the initial assessment (inject_tests).
        gyms = [{"gym_id": "cocque", "priority": 1, "equipment": ["hangboard", "gym_boulder", "gym_routes"]},
                {"gym_id": "bkl", "priority": 2, "equipment": ["hangboard", "dumbbell", "gym_boulder"]}]
        avail = _evening_at({"mon": "bkl", "tue": "cocque", "wed": "cocque", "thu": "cocque", "sat": "cocque",
                             "sun": "cocque"})
        kw = _kwargs("strength_power", "2026-10-12", is_last_week_of_phase=True, availability=avail, gyms=gyms,
                     default_gym_id="cocque", home_equipment=[], allowed_locations=["gym"], inject_tests=inject)
        plan = generate_phase_week(**kw)
        tests = _test_days(plan)
        assert tests[HANG] == ("2026-10-12", "evening")
        assert tests["test_pullup_bw"] == ("2026-10-17", "evening") and PULL not in tests
        assert next(s for _d, s in _sessions(plan) if s["session_id"] == "test_pullup_bw")["gym_id"] == "cocque"
        assert not [s for s in plan["skipped_tests"] if s["test_id"] == PULL]

    def test_legacy_pass3_no_bodyweight_stand_in_where_the_2rm_misses_for_another_reason(self):
        # The bodyweight test only takes the day the 2RM passed every rule but
        # found no weights: a deload week's assessment refuses the 2RM by its
        # own rules first, with or without weights — no pull test either way
        # (as before A319), and the 2RM is reported as an optional miss.
        for extra in ({}, NO_WEIGHTS):
            plan = generate_phase_week(**_kwargs("deload", "2026-10-19", inject_tests=True,
                                                 availability=_avail(slots=("evening",)), **extra))
            assert not {PULL, "test_pullup_bw"} & set(_test_days(plan))
            assert [(s["reason"], s["required"]) for s in plan["skipped_tests"] if s["test_id"] == PULL] == [
                ("no_placement_slot", False)]


# ---------------------------------------------------------------------------
# Other readers of the catalog session
# ---------------------------------------------------------------------------

class TestCombinedCues:
    def test_combined_gets_the_cues_of_its_two_tests(self):
        # The session cue (A141) of the combined: every test cue of the max
        # hang or of the 2RM, none of the other tests only (repeater, pin).
        with open(os.path.join(REPO_ROOT, "backend", "catalog", "cues", "v1", "process_cues.json")) as f:
            cues = json.load(f)

        def ids(sid: str) -> set:
            return {c["id"] for c in cues if sid in c.get("session_types", [])}

        assert ids(COMBO) == ids(HANG) | ids(PULL) == {"cue_036", "cue_037", "cue_038", "cue_041", "cue_042"}
        from backend.engine.cues import get_session_cue

        for day in ("2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"):
            cue = get_session_cue(COMBO, day, "user_a319", REPO_ROOT)
            assert cue is not None and cue["id"] in ids(COMBO)


class TestChangeGymOnATestDay:
    """Characterization (A319 review): ``change_gym`` (replanner_v1) checks the
    catalog's ``required_equipment`` against the new gym's expanded equipment
    (dumbbell → weight). Since A319(d) a 2RM test moved to a gym without
    weights becomes complementary_conditioning — it would measure nothing
    there — and so does the combined, which loses its max hang too although
    the gym has a hangboard. Whether it should become ``test_max_hang_7s``
    instead is open (roadmap A319-CHANGE-GYM: replanner_v1 → Phase 1 + STOP)."""

    _GYMS = [{"gym_id": "cocque", "name": "Cocque", "equipment": ["spraywall", "gym_routes", "hangboard", "pullup_bar"]},
             {"gym_id": "bkl", "name": "Bkl", "equipment": ["hangboard", "gym_boulder", "pullup_bar", "dumbbell"]},
             {"gym_id": "work", "name": "Work", "equipment": ["barbell", "bench", "dumbbell", "pullup_bar"]}]

    def _moved(self, sid: str, gym_id: str) -> tuple:
        plan = {"start_date": WS, "weeks": [{"days": [{"date": MON, "sessions": [
            {"slot": "evening", "session_id": sid, "location": "gym", "gym_id": "bkl", "status": "planned",
             "tags": {"hard": True, "finger": sid != PULL, "test": True}}]}]}]}
        out = apply_events(plan, [{"event_type": "change_gym", "date": MON, "location": "gym", "gym_id": gym_id}],
                           gyms=self._GYMS)
        adaptation = next(a for a in out["adaptations"] if a.get("type") == "change_gym")
        return out["weeks"][0]["days"][0]["sessions"][0]["session_id"], adaptation

    @pytest.mark.parametrize("sid", [PULL, COMBO])
    def test_kept_where_a_dumbbell_implies_weight(self, sid):
        assert self._moved(sid, "bkl")[0] == sid

    def test_2rm_replaced_where_there_are_no_weights(self):
        sid, adaptation = self._moved(PULL, "cocque")
        assert sid == "complementary_conditioning"
        assert "missing_equipment={'weight'}" in " ".join(adaptation.get("warnings") or [])

    def test_combined_replaced_where_there_are_no_weights_and_its_hang_is_lost(self):
        sid, adaptation = self._moved(COMBO, "cocque")
        assert sid == "complementary_conditioning"
        assert adaptation.get("lost_finger") is True
        assert self._moved(HANG, "cocque")[0] == HANG  # the max hang alone would stay
