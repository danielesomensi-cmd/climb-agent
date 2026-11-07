"""B414 (model A) — the expiry of a test switches nothing off.

Decision of Daniele (2026-11-07): when the official test reaches its 90 days
nothing is reset and nothing switches off — the bodyweight ladders, the
anchored loads (and their closed loop), the A290 phase rotation, the A292 PE
anchor and the tested coach stay on and keep progressing. The expiry is only
information (``official_max`` → ``valid_until`` / ``expired`` / ``expiring``):
14 days before, the app proposes "Do the test" / "Postpone the expiry".

Before B414 one gate — ``tested`` = real test AND younger than 90 days — turned
every one of those off on day 90: for Daniele (tests of 24/09) on 23/12.

Covered here:
- a real test of 91 / 200 days: every consumer of the gate is still on, and
  the feedback still moves the ladders and the working loads;
- ``retest_status`` at the boundaries (expiring from valid_until − 14,
  expired from valid_until + 1, covered all the way);
- end to end, 20/12 → 05/01 on a Daniele-like state: the gate never closes,
  ladders and loads are continuous between 22/12 and 23/12, a feedback logged
  after the expiry moves both, and every past session stays byte for byte;
- an untested athlete (no test, or a self-report only) stays untested on
  every one of those days (the untested goldens pin the rest);
- determinism: 100 runs beyond the expiry are identical.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta

import pytest

from backend.engine import bw_ladders as bl
from backend.engine import bw_progression as bp
from backend.engine import phase_anchor as pa
from backend.engine import retest_policy as rp
from backend.engine.anchored_load import anchored_load, is_anchored_and_tested
from backend.engine.progression_v1 import apply_feedback, pe_anchor_applies
from backend.tests import b413_lunch_golden_cases as lg

TEST_DAY = date(2026, 9, 24)
VALID_UNTIL = date(2026, 12, 22)  # 24/09 + 89
DAYS = [date(2026, 12, 20) + timedelta(days=i) for i in range(17)]  # 20/12 → 05/01


def _daniele() -> dict:
    """Daniele-like (tests of 24/09, the four persisted core ladders, the
    history week of 28/09 with done sessions) + working loads of the two
    anchored lifts and a done past week in December."""
    st = lg.daniele_state("2026-12-22")
    st.pop("context", None)
    st["working_loads"] = {"entries": [
        {"exercise_id": "max_hang_7s", "key": "max_hang_7s", "setup": {}, "anchored": True,
         "last_total_load_kg": 103.0, "last_external_load_kg": 25.0, "next_total_load_kg": 105.0,
         "next_external_load_kg": 27.0, "last_feedback_label": "ok", "last_completed": True,
         "updated_at": "2026-12-15"},
        {"exercise_id": "weighted_pullup", "key": "weighted_pullup", "setup": {}, "anchored": True,
         "last_total_load_kg": 106.0, "last_external_load_kg": 28.0, "next_total_load_kg": 107.0,
         "next_external_load_kg": 29.0, "last_feedback_label": "ok", "last_reps": 3, "last_completed": True,
         "updated_at": "2026-12-15"},
    ], "rules": {}}
    st["week_plans"]["2026-12-14"] = {"start_date": "2026-12-14", "weeks": [{"days": [
        {"date": "2026-12-15", "sessions": [{
            "session_id": "strength_long", "status": "done", "location": "home", "slot": "evening",
            "actual_exercises": [
                {"exercise_id": "max_hang_7s", "completed": True, "completed_sets": 5,
                 "used_total_load_kg": 103.0},
                {"exercise_id": "ab_wheel_rollout", "completed": True, "completed_sets": 3},
            ],
        }]},
        {"date": "2026-12-17", "sessions": [{"session_id": "technique_focus_gym", "status": "skipped",
                                             "location": "gym", "slot": "evening"}]},
    ]}]}
    return st


def _new_cycle(st: dict, start: str = "2026-12-21") -> dict:
    """The athlete started the next macrocycle (``start-new-cycle``): outside
    its deload the ladders move (after the end of a cycle the phase reads
    deload and B413 freezes the doses — END-OF-CYCLE-STUCK-IN-DELOAD, accepted)."""
    st = deepcopy(st)
    st["macrocycle"] = {"start_date": start, "phases": [
        {"phase_id": "base", "duration_weeks": 3}, {"phase_id": "strength_power", "duration_weeks": 5},
        {"phase_id": "power_endurance", "duration_weeks": 4}, {"phase_id": "performance", "duration_weeks": 3},
        {"phase_id": "deload", "duration_weeks": 1}]}
    return st


def _view(st: dict, d: date) -> dict:
    """What the gate drives on ``d``: every consumer, plus the expiry flags."""
    hang = anchored_load(st, "max_hang_7s", date=d.isoformat(), sets=5, work_seconds=7)
    pull = anchored_load(st, "weighted_pullup", date=d.isoformat(), sets=4, reps=3)
    status = rp.retest_status(st, d, finger_device="hangboard")["axes"]
    return {
        "gate": bl.tested_gate(st, d),
        "ladders": {f: (e.get("level_idx"), e.get("exercise_id"), e.get("sets"), e.get("target"))
                    for f, e in sorted(bp.entries_for(st, d).items())},
        "resolve_ctx": bp.build_resolve_context(st, d) is not None,
        "rotation": pa.build_rotation_context(st, d, None) is not None,
        "pe_anchor": pe_anchor_applies(st, d),
        "hang": (hang or {}).get("total"),
        "pull": (pull or {}).get("total"),
        "covered": sorted(a for a, r in status.items() if r["covered"]),
        "expiry": {a: (r["valid_until"], r["expiring"], r["expired"]) for a, r in sorted(status.items())},
    }


def _past(st: dict) -> str:
    """Every stored session dated before 20/12, byte for byte."""
    out = {}
    for ws, plan in sorted((st.get("week_plans") or {}).items()):
        for wk in plan.get("weeks") or []:
            for day in wk.get("days") or []:
                if str(day.get("date")) < DAYS[0].isoformat():
                    out[str(day["date"])] = day
    return json.dumps(out, sort_keys=True)


# ---------------------------------------------------------------------------
# A real test of 91 / 200 days: every consumer still on
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("age", [91, 200])
def test_an_expired_test_keeps_every_consumer_on(age):
    st = _daniele()
    d = TEST_DAY + timedelta(days=age)
    v = _view(st, d)
    assert v["gate"] and v["resolve_ctx"] and v["rotation"] and v["pe_anchor"]
    assert set(v["ladders"]) == {"compression_floor", "hollow_plank", "lateral", "rollout"}
    assert v["hang"] is not None and v["pull"] is not None
    assert is_anchored_and_tested(st, "max_hang_7s", d) and is_anchored_and_tested(st, "weighted_pullup", d)
    assert v["covered"] == ["finger", "pulling"]
    assert all(e == (VALID_UNTIL.isoformat(), False, True) for e in v["expiry"].values())
    om = rp.official_max(st, rp.PROTOCOL_HANG_7S, d)
    assert (om["tested"], om["fresh"], om["age_days"]) == (True, False, age)


@pytest.mark.parametrize("age", [91, 150])
def test_the_feedback_still_moves_ladders_and_loads_after_the_expiry(age):
    st = _new_cycle(_daniele())
    d = (TEST_DAY + timedelta(days=age)).isoformat()
    log = {"date": d, "session_id": "core_training", "feedback_contract": 2, "actual": {"exercise_feedback_v1": [
        {"exercise_id": "ab_wheel_rollout", "completed": True, "completed_sets": 3, "feedback_label": "easy",
         "bw_ladder": "engine"},
        {"exercise_id": "max_hang_7s", "completed": True, "completed_sets": 5, "feedback_label": "ok",
         "used_total_load_kg": 105.0, "used_external_load_kg": 27.0},
    ]}}
    out = apply_feedback(log, deepcopy(st))
    roll = out["bw_progression"]["rollout"]
    assert roll["last_outcome"]["kind"] == "step_up"  # easy (B413); R11 re-enters after the long gap
    assert roll != st["bw_progression"]["rollout"]
    hang = next(e for e in out["working_loads"]["entries"] if e["exercise_id"] == "max_hang_7s")
    assert hang["updated_at"] == d and hang["last_total_load_kg"] == 105.0


# ---------------------------------------------------------------------------
# End to end 20/12 → 05/01 (the day the max used to switch off: 23/12)
# ---------------------------------------------------------------------------

def test_end_to_end_across_the_expiry():
    st = _daniele()
    before = deepcopy(st)
    past = _past(st)
    views = {d: _view(st, d) for d in DAYS}
    assert st == before  # every read is pure
    for d, v in views.items():
        assert v["gate"] and v["resolve_ctx"] and v["rotation"] and v["pe_anchor"], d
        assert v["covered"] == ["finger", "pulling"], d
        assert v["hang"] is not None and v["pull"] is not None, d
        assert set(v["ladders"]) == {"compression_floor", "hollow_plank", "lateral", "rollout"}, d
        expired = d > VALID_UNTIL
        assert all(e == (VALID_UNTIL.isoformat(), not expired, expired) for e in v["expiry"].values()), d
    # Continuity between the last valid day and the first expired one: the
    # same ladder levels, the same loads — only the expiry flags move.
    d22, d23 = views[date(2026, 12, 22)], views[date(2026, 12, 23)]
    assert {k: v for k, v in d22.items() if k != "expiry"} == {k: v for k, v in d23.items() if k != "expiry"}
    # A session logged after the expiry: the closed loop keeps moving, the
    # past stays byte for byte (the feedback writes only its own memory).
    log = {"date": "2026-12-28", "session_id": "core_training", "feedback_contract": 2,
           "actual": {"exercise_feedback_v1": [
               {"exercise_id": "core_hollow_hold", "completed": True, "completed_sets": 3, "feedback_label": "ok",
                "bw_ladder": "engine"},
               {"exercise_id": "weighted_pullup", "completed": True, "completed_sets": 4, "reps": 3,
                "feedback_label": "easy", "used_external_load_kg": 29.0},
           ]}}
    out = apply_feedback(log, deepcopy(st))
    # The ladder reads the feedback (the gate is open); after the end of the
    # 07/09 cycle the phase reads deload and B413 freezes the dose.
    assert out["bw_progression"]["hollow_plank"]["last_outcome"]["kind"] == "frozen"
    pull = next(e for e in out["working_loads"]["entries"] if e["exercise_id"] == "weighted_pullup")
    assert pull["updated_at"] == "2026-12-28"
    assert _past(out) == past
    assert out["tests"] == st["tests"] and out.get("baselines") == st.get("baselines")  # the max is never written
    # The next cycle started on 21/12 (base): the same feedback steps the ladder up.
    renewed = _new_cycle(st)
    out = apply_feedback(log, deepcopy(renewed))
    assert out["bw_progression"]["hollow_plank"]["last_outcome"]["kind"] == "step_up"
    assert _past(out) == past


def test_untested_athletes_stay_untested_across_the_same_days():
    """No test, or an onboarding self-report only: untested on every day (the
    A290 / B364 / C272 untested goldens pin the outputs bit for bit)."""
    no_test = _daniele()
    no_test.pop("tests")
    no_test.pop("baselines", None)
    self_report = deepcopy(no_test)
    self_report["baselines"] = {
        "hangboard": [{"max_total_load_kg": 116.0, "source": "test", "updated_at": "2026-09-24",
                       "hang_seconds": 7, "edge_mm": 20}],
        "pulling": {"weighted_pullup_2rm_total_kg": 123.0, "source": "test", "updated_at": "2026-09-24"},
    }
    for st in (no_test, self_report):
        for d in DAYS:
            v = _view(st, d)
            assert not (v["gate"] or v["resolve_ctx"] or v["rotation"] or v["pe_anchor"]), d
            assert (v["ladders"], v["hang"], v["pull"], v["covered"]) == ({}, None, None, []), d


def test_deterministic_beyond_the_expiry():
    st = _daniele()
    d = date(2027, 1, 4)
    first = json.dumps(_view(st, d), sort_keys=True)
    assert all(json.dumps(_view(deepcopy(st), d), sort_keys=True) == first for _ in range(100))
