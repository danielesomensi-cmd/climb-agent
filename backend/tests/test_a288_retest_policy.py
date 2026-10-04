"""A288 (F0) — read-only retest-policy primitives: official max, computed test
confidence, the single re-entry ramp, heavy pulling."""

from __future__ import annotations

import copy

import pytest

from backend.engine import retest_policy as rp


def _week(start, days):
    return {"start_date": start, "weeks": [{"days": [
        {"date": d, "sessions": sessions} for d, sessions in days
    ]}]}


def _done(eid, sets=4, sid=None, **extra):
    return {"session_id": sid or f"custom_{eid}", "is_custom": sid is None, "status": "done",
            "actual_exercises": [{"exercise_id": eid, "completed_sets": sets, **extra}]}


def _state(**over):
    s = {
        "bodyweight_kg": 78.0,
        "tests": {
            "max_strength": [
                {"date": "2026-03-17", "test_id": "max_hang_5s_total_load", "total_load_kg": 120.0,
                 "bodyweight_kg": 77.0, "confidence": "high"},
                {"date": "2026-05-19", "test_id": "max_hang_7s_total_load", "total_load_kg": 122.0,
                 "bodyweight_kg": 77.0, "confidence": "high"},
                {"date": "2026-09-24", "test_id": "max_hang_7s_total_load", "total_load_kg": 116.0,
                 "bodyweight_kg": 76.0, "confidence": "high"},
            ],
            "pulling_strength": [
                {"date": "2026-05-22", "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 122.0,
                 "estimated_1rm_kg": 127.8, "confidence": "high"},
                {"date": "2026-09-24", "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 123.0,
                 "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0, "confidence": "high"},
            ],
            "repeater_strength_endurance": [
                {"date": "2026-03-19", "test_id": "repeater_7_3_max_reps", "completed_reps": 25},
            ],
        },
        "baselines": {
            "hangboard": [{"grip": "half_crimp", "edge_mm": 20, "source": "test",
                           "updated_at": "2026-09-24", "hang_seconds": 7, "max_total_load_kg": 116.0}],
            "pulling": {"source": "test_session", "updated_at": "2026-09-24",
                        "weighted_pullup_2rm_total_kg": 123.0, "weighted_pullup_1rm_total_kg": 128.9},
        },
        "week_plans": {},
    }
    s.update(over)
    return s


# ---------------------------------------------------------------------------
# official_max
# ---------------------------------------------------------------------------

def test_hang_7s_is_the_freshest_test():
    om = rp.official_max(_state(), rp.PROTOCOL_HANG_7S, "2026-10-13")
    assert om["total_kg"] == 116.0 and om["date"] == "2026-09-24"
    assert om["tested"] is True and om["fresh"] is True and om["converted"] is False
    assert om["age_days"] == 19 and om["family"] == "finger_max"
    assert (om["edge_mm"], om["grip"]) == (20, "half_crimp")
    assert om["bodyweight_kg"] == 76.0


def test_hang_5s_converted_from_fresh_7s_never_the_old_5s():
    om = rp.official_max(_state(), rp.PROTOCOL_HANG_5S, "2026-10-13")
    # 116 × (1 + 0.015 × 2) = 119.48 → 119.5 ; the 120 kg 5 s test of 17/03 is ignored
    assert om["total_kg"] == 119.5
    assert om["converted"] is True and om["source_seconds"] == 7 and om["date"] == "2026-09-24"


def test_same_day_tie_prefers_same_duration():
    s = _state()
    s["tests"]["max_strength"].append(
        {"date": "2026-09-24", "test_id": "max_hang_5s_total_load", "total_load_kg": 118.0})
    assert rp.official_max(s, rp.PROTOCOL_HANG_5S, "2026-10-13")["total_kg"] == 118.0
    assert rp.official_max(s, rp.PROTOCOL_HANG_7S, "2026-10-13")["total_kg"] == 116.0


def test_as_of_excludes_later_tests_and_staleness():
    om = rp.official_max(_state(), rp.PROTOCOL_HANG_7S, "2026-09-23")
    assert om["date"] == "2026-05-19" and om["total_kg"] == 122.0
    assert om["age_days"] == 127 and om["fresh"] is False and om["tested"] is False
    assert rp.official_max(_state(), rp.PROTOCOL_HANG_7S, "2026-03-01") is None


def test_ninety_day_boundary():
    assert rp.is_tested(_state(), rp.PROTOCOL_HANG_7S, "2026-12-22") is True   # 89 d
    assert rp.is_tested(_state(), rp.PROTOCOL_HANG_7S, "2026-12-23") is False  # 90 d


def test_pullup_2rm_and_saved_1rm():
    om = rp.official_max(_state(), rp.PROTOCOL_PULLUP_2RM, "2026-10-09")
    assert (om["total_kg"], om["one_rm_kg"], om["date"]) == (123.0, 128.9, "2026-09-24")
    assert om["tested"] is True


def test_pullup_1rm_estimated_when_not_saved():
    s = _state()
    del s["tests"]["pulling_strength"][1]["estimated_1rm_kg"]
    from backend.engine.progression_v1 import estimate_1rm_from_2rm

    om = rp.official_max(s, rp.PROTOCOL_PULLUP_2RM, "2026-10-09")
    assert om["one_rm_kg"] == estimate_1rm_from_2rm(123.0)


def test_baseline_fallback_only_without_tests_and_source_matters():
    s = _state(tests={})
    om = rp.official_max(s, rp.PROTOCOL_HANG_7S, "2026-10-13")
    assert om["source"] == "test" and om["total_kg"] == 116.0 and om["tested"] is True
    pull = rp.official_max(s, rp.PROTOCOL_PULLUP_2RM, "2026-10-13")
    assert pull["source"] == "test_session" and pull["tested"] is True
    s["baselines"]["hangboard"][0]["source"] = "estimated"
    om = rp.official_max(s, rp.PROTOCOL_HANG_7S, "2026-10-13")
    assert om is not None and om["tested"] is False


def test_unknown_protocol_and_empty_state():
    assert rp.official_max(_state(), "repeater_7_3_max_reps", "2026-10-13") is None
    assert rp.official_max({}, rp.PROTOCOL_HANG_7S, "2026-10-13") is None
    assert rp.is_tested({}, rp.PROTOCOL_PULLUP_2RM, "2026-10-13") is False


def test_official_max_does_not_mutate_state():
    s = _state()
    snap = copy.deepcopy(s)
    rp.official_max(s, rp.PROTOCOL_HANG_5S, "2026-10-13")
    rp.official_max(s, rp.PROTOCOL_PULLUP_2RM, "2026-10-13")
    assert s == snap


# ---------------------------------------------------------------------------
# test_confidence
# ---------------------------------------------------------------------------

def _archive_two_hangs():
    return {"2026-09-07": _week("2026-09-07", [
        ("2026-09-08", [_done("max_hang_7s")]),
        ("2026-09-11", [_done("horst_7_53")]),
    ])}


def test_confidence_low_without_exposures_even_if_stored_high():
    s = _state()
    t = s["tests"]["max_strength"][-1]
    c = rp.test_confidence(s, t)
    assert c["confidence"] == "low" and c["exposures"] == 0
    assert (c["window_start"], c["window_end"]) == ("2026-09-03", "2026-09-23")


def test_confidence_needs_the_archived_weeks():
    s = _state()
    t = s["tests"]["max_strength"][-1]
    assert rp.test_confidence(s, t)["confidence"] == "low"
    c = rp.test_confidence(s, t, archived_weeks=_archive_two_hangs())
    assert c["confidence"] == "high" and c["exposures"] == 2


def test_confidence_window_excludes_test_day_and_older_days():
    s = _state(week_plans={"2026-09-21": _week("2026-09-21", [
        ("2026-09-24", [_done("max_hang_7s"), _done("horst_7_53")]),  # the test day itself
    ])})
    arch = {"2026-08-31": _week("2026-08-31", [("2026-09-02", [_done("max_hang_7s")])])}  # d−22
    c = rp.test_confidence(s, s["tests"]["max_strength"][-1], archived_weeks=arch)
    assert c["exposures"] == 0 and c["confidence"] == "low"


def test_confidence_family_is_per_protocol():
    s = _state()
    pull = s["tests"]["pulling_strength"][-1]
    assert rp.test_confidence(s, pull, archived_weeks=_archive_two_hangs())["confidence"] == "low"


def test_confidence_from_official_max_result_and_unknown_protocol():
    s = _state()
    om = rp.official_max(s, rp.PROTOCOL_HANG_5S, "2026-10-13")
    assert rp.test_confidence(s, om, archived_weeks=_archive_two_hangs())["confidence"] == "high"
    rep = rp.test_confidence(s, s["tests"]["repeater_strength_endurance"][0])
    assert rep["confidence"] is None and rep["family"] is None
    assert rp.test_confidence(s, {"test_id": rp.PROTOCOL_HANG_7S})["confidence"] is None


# ---------------------------------------------------------------------------
# reentry_step
# ---------------------------------------------------------------------------

def _hang_state(dates):
    days = [(d, [_done("max_hang_7s")]) for d in dates]
    return _state(week_plans={"w": _week("w", days)})


def test_factor_table():
    assert [rp.reentry_factor(n) for n in (0, 1, 2, 3, 7)] == [0.90, 0.90, 0.95, 1.0, 1.0]


def test_no_history_is_first_exposure():
    r = rp.reentry_step(_state(), "finger_max", "2026-10-13")
    assert (r["n"], r["factor"], r["gap_days"], r["in_reentry"]) == (1, 0.90, None, True)


def test_daniele_like_finger_gap_reopens_ramp():
    # test 24/09, next hang 13/10: 19 days → gap → n=1 (B364 example)
    r = rp.reentry_step(_hang_state(["2026-09-24"]), "finger_max", "2026-10-13")
    assert (r["n"], r["factor"], r["gap_days"], r["last_exposure"]) == (1, 0.90, 19, "2026-09-24")


def test_run_counts_and_current_session():
    s = _hang_state(["2026-09-24", "2026-10-04"])
    r = rp.reentry_step(s, "finger_max", "2026-10-09")
    assert (r["n"], r["factor"], r["run_dates"]) == (3, 1.0, ["2026-09-24", "2026-10-04"])
    assert r["in_reentry"] is False
    r2 = rp.reentry_step(s, "finger_max", "2026-10-09", include_current=False)
    assert (r2["n"], r2["factor"]) == (2, 0.95)


def test_gap_boundary_thirteen_vs_fourteen_days():
    assert rp.reentry_step(_hang_state(["2026-10-01"]), "finger_max", "2026-10-14")["n"] == 2
    assert rp.reentry_step(_hang_state(["2026-10-01"]), "finger_max", "2026-10-15")["n"] == 1
    # an old run before a gap is not counted
    s = _hang_state(["2026-08-01", "2026-08-05", "2026-08-09", "2026-09-01", "2026-09-05"])
    r = rp.reentry_step(s, "finger_max", "2026-09-08")
    assert (r["n"], r["gap_days"], r["run_start"]) == (3, 23, "2026-09-01")


def test_same_day_exposure_not_double_counted_and_today_excluded():
    s = _hang_state(["2026-10-04"])
    s["week_plans"]["w"]["weeks"][0]["days"][0]["sessions"].append(_done("horst_7_53"))
    s["week_plans"]["w"]["weeks"][0]["days"].append({"date": "2026-10-09", "sessions": [_done("max_hang_7s")]})
    r = rp.reentry_step(s, "finger_max", "2026-10-09")
    assert (r["n"], r["run_dates"]) == (2, ["2026-10-04"])


def test_test_counts_as_exposure():
    s = _state(week_plans={"w": _week("w", [("2026-09-24", [
        {"session_id": "test_max_weighted_pullup", "status": "done",
         "actual_exercises": [{"exercise_id": "weighted_pullup", "completed_sets": 4,
                               "used_total_load_kg": 123}]}])])})
    assert rp.reentry_step(s, "pulling_max", "2026-10-04")["n"] == 2


# ---------------------------------------------------------------------------
# Heavy pulling
# ---------------------------------------------------------------------------

def _custom_pull(load_kg=None, **logged):
    s = {"session_id": "custom_cs_ab", "is_custom": True, "status": "done",
         "tags": {"hard": True, "finger": False},
         "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3, "load_kg": load_kg}]}
    if logged:
        s["actual_exercises"] = [{"exercise_id": "weighted_pullup", "completed_sets": 4, **logged}]
    return s


def test_weighted_pull_below_85pct_is_not_heavy():
    # 78 + 30 = 108 < 0.85 × 128.9 = 109.6
    assert rp.is_heavy_pulling_session(_state(), _custom_pull(load_kg=30), "2026-10-04") is False
    assert rp.is_heavy_pulling_session(
        _state(), _custom_pull(used_external_load_kg=30), "2026-10-04") is False


def test_weighted_pull_at_or_above_85pct_is_heavy():
    assert rp.is_heavy_pulling_session(_state(), _custom_pull(load_kg=32), "2026-10-04") is True
    assert rp.is_heavy_pulling_session(
        _state(), _custom_pull(used_total_load_kg=112), "2026-10-04") is True


def test_unknown_load_or_no_official_max_is_heavy():
    assert rp.is_heavy_pulling_session(_state(), _custom_pull(), "2026-10-04") is True
    assert rp.is_heavy_pulling_session(_state(tests={}, baselines={}), _custom_pull(load_kg=5),
                                       "2026-10-04") is True


def test_label_rule_power_endurance_gym_is_heavy_pulling():
    pe = {"session_id": "power_endurance_gym", "tags": {"hard": True, "finger": False}}
    assert rp.is_heavy_pulling_session(_state(), pe, "2026-10-22") is True
    assert rp.is_heavy_pulling_session(_state(), {"session_id": "technique_focus_gym"}, "2026-10-22") is False


# ---------------------------------------------------------------------------
# Constants (decisions 2026-10-04) — pinned so a change is a reviewed change
# ---------------------------------------------------------------------------

def test_constants_pinned():
    assert rp.FINGER_GAP_H == 48
    assert rp.RETEST_BLOCK_H == 72
    assert rp.PULL_TEST_BLOCK_H == 48
    assert rp.TEST_FRESH_DAYS == 90
    assert (rp.LOW_CONF_MIN_EXPOSURES, rp.LOW_CONF_WINDOW_D, rp.LOW_CONF_RETEST_D) == (2, 21, 28)
    assert rp.REENTRY_GAP_D == 14
    assert rp.HANG_PCT_PER_S == 0.015
    assert rp.HEAVY_PULL_PCT_1RM == 0.85
    assert (rp.VERY_HARD_BLOCK_D, rp.PRE_TRIP_BLOCK_D) == (3, 10)
    assert rp.RETEST_BLOCKED_PHASES == ("performance", "deload")


@pytest.mark.parametrize("eid", sorted(rp.EXERCISE_PROTOCOL))
def test_exercise_protocol_family_matches_stimulus_table(eid):
    from backend.engine.stimulus import stimulus_of

    assert stimulus_of(eid) == rp.PROTOCOL_FAMILY[rp.EXERCISE_PROTOCOL[eid]]


def test_skipped_logged_pull_is_not_heavy():
    """Review fix: the player pre-fills completed + load even for a skipped
    exercise; 0 sets/reps (or feedback_label skipped) is not a heavy pull."""
    prefilled = {"session_id": "custom_cs_pull", "is_custom": True, "status": "done",
                 "actual_exercises": [{"exercise_id": "weighted_pullup", "completed": True,
                                       "completed_sets": 0, "completed_reps": 0,
                                       "used_external_load_kg": 45}]}
    assert rp.is_heavy_pulling_session(_state(), prefilled, "2026-10-04") is False
    labelled = {"session_id": "custom_cs_pull", "is_custom": True, "status": "done",
                "actual_exercises": [{"exercise_id": "weighted_pullup", "completed_sets": 3,
                                      "feedback_label": "skipped", "used_external_load_kg": 45}]}
    assert rp.is_heavy_pulling_session(_state(), labelled, "2026-10-04") is False
    done = {"session_id": "custom_cs_pull", "is_custom": True, "status": "done",
            "actual_exercises": [{"exercise_id": "weighted_pullup", "completed": True,
                                  "completed_sets": 3, "used_external_load_kg": 45}]}
    assert rp.is_heavy_pulling_session(_state(), done, "2026-10-04") is True
