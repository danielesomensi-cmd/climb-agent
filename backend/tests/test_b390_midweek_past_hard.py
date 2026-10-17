"""B390 — a mid-week regeneration counts the hard sessions already done this week.

Decided by Daniele on 2026-10-17 (Phase 1: docs/briefs/B390_midweek_past_hard.md),
option A: the lived days of the current week feed the hard-day cap, the hard /
finger gaps and anti-repetition. Only sessions marked **done** count, only
sessions of the plan (free sessions / crag logs off the plan: no; crag days
declared on the plan are B382(b)'s).

Before B390, ``generate_phase_week`` started the counters empty, so on the
synthetic week below (cap 3, ``strength_long`` done on Wednesday) a Thursday
regeneration put ``limit_boulder_gym`` on Thursday: 4 hard days, finger back to
back Wed→Thu, the same limit session twice in the week.

Fixtures are synthetic (no real user state in the repo).
"""

from __future__ import annotations

from copy import deepcopy

from backend.tests.test_a300_complementary_slots import days_of, plan
from backend.tests.test_b382_slot_empty_crag_hard import (
    FRI, MON, PHASE, SAT, SUN, THU, TUE, WED, _base, _day, _finger, _fp, _hard, _regen,
)

CAP = 3


def _lived(status="done"):
    """Mon–Wed lived with ``status``; Wednesday evening = ``strength_long`` (H, F)."""
    wp = deepcopy(_base())
    for d in days_of(wp):
        if d["date"] in (MON, TUE, WED):
            for s in d.get("sessions") or []:
                s["status"] = status
    wed = _day(wp, WED)
    wed["sessions"] = [s for s in wed["sessions"] if s["slot"] != "evening"] + [{
        "slot": "evening", "session_id": "strength_long", "status": status,
        "tags": {"hard": True, "finger": True}, "constraints_applied": ["quick_add"],
    }]
    return wp


def _hard_days(wp):
    return [d["date"] for d in days_of(wp) if any(_hard(s) and s.get("status") != "skipped"
                                                  for s in d.get("sessions") or [])]


def _finger_days(wp):
    return [d["date"] for d in days_of(wp) if any(_finger(s) and s.get("status") != "skipped"
                                                  for s in d.get("sessions") or [])]


def _sids(wp):
    return [s["session_id"] for d in days_of(wp) for s in d.get("sessions") or []]


class TestThursdayCase:
    def test_cap_respected_over_the_whole_week(self):
        _new, merged = _regen(_lived(), THU)
        assert len(_hard_days(merged)) <= CAP, _hard_days(merged)

    def test_no_finger_session_the_day_after_wednesday(self):
        _new, merged = _regen(_lived(), THU)
        assert not any(_finger(s) for s in _day(merged, THU).get("sessions") or [])

    def test_no_session_repeated_against_the_lived_days(self):
        _new, merged = _regen(_lived(), THU)
        assert _sids(merged).count("limit_boulder_gym") == 1
        assert _sids(merged).count("strength_long") == 1

    def test_summary_counts_the_lived_hard_days(self):
        new, merged = _regen(_lived(), THU)
        summary = new["weeks"][0].get("weekly_load_summary") or new.get("weekly_load_summary") or {}
        if "hard_days_count" in summary:
            assert summary["hard_days_count"] == len(_hard_days(merged))


class TestWhatCounts:
    def test_unmarked_past_sessions_do_not_count(self):
        """A past session never marked done did not happen as far as the plan knows."""
        unmarked = _lived(status=None)
        skipped = _lived(status="skipped")
        new_u, _ = _regen(unmarked, THU)
        new_s, _ = _regen(skipped, THU)
        future = (THU, FRI, SAT, SUN)
        pick = lambda wp: [[(s["slot"], s["session_id"]) for s in _day(wp, d).get("sessions") or []]
                           for d in future]
        assert pick(new_u) == pick(new_s)

    def test_todays_done_session_counts(self):
        """Regenerating on Wednesday after Wednesday's strength_long: no finger Thursday."""
        _new, merged = _regen(_lived(), WED)
        assert not any(_finger(s) for s in _day(merged, THU).get("sessions") or [])
        assert len(_hard_days(merged)) <= CAP


class TestInvariants:
    def test_lived_days_untouched(self):
        old = _lived()
        _new, merged = _regen(old, THU)
        for d in (MON, TUE, WED):
            assert _day(merged, d)["sessions"] == _day(old, d)["sessions"]

    def test_deterministic(self):
        a = _regen(_lived(), THU)[1]
        b = _regen(_lived(), THU)[1]
        assert _fp(a) == _fp(b)

    def test_monday_regeneration_unchanged(self):
        """No lived day → the week the planner generates is the one it always did."""
        base = _base()
        new, _ = _regen(base, MON)
        assert [[(s["slot"], s["session_id"]) for s in d.get("sessions") or []] for d in days_of(new)] \
            == [[(s["slot"], s["session_id"]) for s in d.get("sessions") or []] for d in days_of(plan(PHASE, today=MON))]
