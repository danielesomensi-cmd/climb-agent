"""A265 — deterministic outdoor pitch ladder + day-level plan persistence."""

from __future__ import annotations

import copy

import pytest

from backend.engine.outdoor_pitch_ladder import (
    DAY_TYPES,
    build_pitch_ladder,
    grades_from_state,
    infer_onsight,
)
from backend.engine.replanner_v1 import _DAY_LEVEL_FIELDS, apply_events


# ── Ladder generation ───────────────────────────────────────────────────────

def test_ladder_is_deterministic():
    a = build_pitch_ladder("onsight_flash", onsight_grade="7a+", redpoint_grade="8a+")
    b = build_pitch_ladder("onsight_flash", onsight_grade="7a+", redpoint_grade="8a+")
    assert a == b


@pytest.mark.parametrize("day_type", DAY_TYPES)
def test_every_day_type_yields_a_usable_ladder(day_type):
    ladder = build_pitch_ladder(day_type, onsight_grade="7a+", redpoint_grade="8a+")
    assert ladder is not None
    assert ladder["pitches"], "a ladder with no pitches is not a plan"
    for p in ladder["pitches"]:
        assert p["grade"], "every pitch must name an absolute grade"
        assert p["attempts"] >= 1
        assert p["rest_after_min"] >= 0
    assert ladder["summary"]["pitch_count"] == len(ladder["pitches"])


def test_onsight_flash_ramps_up_then_closes_easy():
    ladder = build_pitch_ladder("onsight_flash", onsight_grade="7a+", redpoint_grade="8a+")
    grades = [p["grade"] for p in ladder["pitches"]]
    assert grades[0] == "6a"          # warm-up starts well below
    assert grades[3] == "7a+"         # the onsight ceiling itself
    assert grades[4] == "7b"          # one step above
    assert grades[-1] == "6b"         # closes easy
    assert ladder["summary"]["total_attempts"] == 8


def test_power_endurance_pitch_gets_the_short_rest():
    """The PE stimulus IS the short rest — if it drifts up, the day changes."""
    ladder = build_pitch_ladder("onsight_flash", onsight_grade="7a+", redpoint_grade="8a+")
    pe = [p for p in ladder["pitches"] if p["role"] == "power_endurance"]
    assert len(pe) == 1
    mains = [p for p in ladder["pitches"] if p["role"] == "main"]
    assert pe[0]["rest_after_min"] < min(m["rest_after_min"] for m in mains)


def test_project_day_anchors_the_main_pitch_on_redpoint():
    ladder = build_pitch_ladder("project", onsight_grade="7a+", redpoint_grade="8a+")
    main = next(p for p in ladder["pitches"] if p["role"] == "main")
    assert main["grade"] == "8a+"
    assert main["attempts"] >= 2, "a project day without burns is not a project day"


def test_volume_day_stays_below_the_onsight_ceiling():
    ladder = build_pitch_ladder("volume", onsight_grade="7a+", redpoint_grade="8a+")
    assert all(p["grade"] != "7a+" for p in ladder["pitches"])
    assert ladder["summary"]["pitch_count"] >= 6, "volume means volume"


def test_ladder_scales_with_the_athlete():
    weak = build_pitch_ladder("onsight_flash", onsight_grade="6a", redpoint_grade="6c")
    strong = build_pitch_ladder("onsight_flash", onsight_grade="8a", redpoint_grade="8c")
    assert weak["pitches"][3]["grade"] == "6a"
    assert strong["pitches"][3]["grade"] == "8a"


def test_grades_clamp_at_the_bottom_of_the_scale():
    """A 5a onsight must not walk off the start of GRADE_ORDER."""
    ladder = build_pitch_ladder("onsight_flash", onsight_grade="5a", redpoint_grade="5c")
    assert all(p["grade"] == "5a" or p["grade"] for p in ladder["pitches"])
    assert ladder["pitches"][0]["grade"] == "5a"


def test_onsight_inferred_one_number_grade_below_redpoint():
    assert infer_onsight("8a+") == "7a+"
    assert infer_onsight("7a") == "6a"


def test_redpoint_only_still_produces_a_ladder():
    ladder = build_pitch_ladder("onsight_flash", redpoint_grade="8a+")
    assert ladder is not None
    assert ladder["onsight_grade"] == "7a+"


# ── Refusals: never invent grades ───────────────────────────────────────────

def test_no_ladder_without_grades():
    assert build_pitch_ladder("onsight_flash") is None


def test_no_ladder_for_boulder_v1():
    assert build_pitch_ladder("volume", onsight_grade="7a", discipline="boulder") is None


def test_no_ladder_for_unknown_day_type():
    assert build_pitch_ladder("send_it", onsight_grade="7a") is None


def test_grades_from_state_reads_performance():
    state = {"performance": {"current_level": {"sport": {
        "worked": {"grade": "8a+"}, "onsight": {"grade": "7a+"}}}}}
    assert grades_from_state(state) == {"onsight": "7a+", "redpoint": "8a+"}


def test_grades_from_state_falls_back_to_goal():
    state = {"goal": {"current_grade": "7b"}}
    assert grades_from_state(state) == {"onsight": "6b", "redpoint": "7b"}


def test_grades_from_state_returns_none_when_unusable():
    assert grades_from_state({}) is None
    assert grades_from_state({"goal": {"current_grade": "V7"}}) is None


# ── Day-level persistence (the part that silently breaks) ───────────────────

def _plan_with_outdoor_day():
    return {
        "start_date": "2026-08-03",
        "adaptations": [],
        "weeks": [{"week_index": 1, "phase": "performance", "days": [
            {"date": "2026-08-08", "weekday": "sat", "sessions": [],
             "outdoor_spot_name": "Berdorf", "outdoor_discipline": "lead",
             "outdoor_session_status": "planned"},
        ]}],
    }


LADDER = {"pitches": [{"index": 1, "grade": "6a", "attempts": 1, "rest_after_min": 10}]}


def test_outdoor_plan_is_in_the_preserved_day_fields():
    """Regression guard: dropping this makes the plan vanish on regeneration."""
    assert "outdoor_plan" in _DAY_LEVEL_FIELDS


def test_set_outdoor_plan_attaches_the_ladder():
    plan = _plan_with_outdoor_day()
    out = apply_events(plan, [
        {"event_type": "set_outdoor_plan", "date": "2026-08-08", "plan": LADDER}
    ])
    assert out["weeks"][0]["days"][0]["outdoor_plan"] == LADDER


def test_set_outdoor_plan_with_null_clears_it():
    plan = _plan_with_outdoor_day()
    plan["weeks"][0]["days"][0]["outdoor_plan"] = LADDER
    out = apply_events(plan, [
        {"event_type": "set_outdoor_plan", "date": "2026-08-08", "plan": None}
    ])
    assert "outdoor_plan" not in out["weeks"][0]["days"][0]


def test_hand_edited_plan_is_stored_verbatim():
    """The engine must not normalise the user's edit — 'modificabile a mano'."""
    edited = {"pitches": [{"index": 1, "grade": "7c", "attempts": 9,
                           "rest_after_min": 3, "note": "mio"}], "generated": False}
    out = apply_events(_plan_with_outdoor_day(), [
        {"event_type": "set_outdoor_plan", "date": "2026-08-08", "plan": edited}
    ])
    assert out["weeks"][0]["days"][0]["outdoor_plan"] == edited


def test_cannot_plan_a_day_without_an_outdoor_session():
    plan = _plan_with_outdoor_day()
    plan["weeks"][0]["days"][0].pop("outdoor_spot_name")
    with pytest.raises(ValueError, match="no outdoor day"):
        apply_events(plan, [
            {"event_type": "set_outdoor_plan", "date": "2026-08-08", "plan": LADDER}
        ])


def test_cannot_change_the_plan_of_a_completed_day():
    """Past sessions are immutable (core invariant)."""
    plan = _plan_with_outdoor_day()
    plan["weeks"][0]["days"][0]["outdoor_session_status"] = "done"
    with pytest.raises(ValueError, match="completed"):
        apply_events(plan, [
            {"event_type": "set_outdoor_plan", "date": "2026-08-08", "plan": LADDER}
        ])


def test_remove_outdoor_takes_the_plan_with_it():
    plan = _plan_with_outdoor_day()
    plan["weeks"][0]["days"][0]["outdoor_plan"] = LADDER
    out = apply_events(plan, [{"event_type": "remove_outdoor", "date": "2026-08-08"}])
    day = out["weeks"][0]["days"][0]
    assert "outdoor_plan" not in day and "outdoor_spot_name" not in day


def test_plan_survives_a_week_regeneration():
    """The whole point of _DAY_LEVEL_FIELDS — verified end to end."""
    from backend.engine.replanner_v1 import merge_prev_week_sessions

    prev = _plan_with_outdoor_day()
    prev["weeks"][0]["days"][0]["outdoor_plan"] = LADDER

    # A freshly generated week knows nothing about the outdoor day.
    fresh = {"start_date": "2026-08-03", "adaptations": [], "weeks": [
        {"week_index": 1, "phase": "performance", "days": [
            {"date": "2026-08-08", "weekday": "sat", "sessions": []}]}]}

    merged = merge_prev_week_sessions(prev, copy.deepcopy(fresh))
    day = merged["weeks"][0]["days"][0]
    assert day["outdoor_plan"] == LADDER, "the ladder was dropped by regeneration"
    assert day["outdoor_spot_name"] == "Berdorf"
