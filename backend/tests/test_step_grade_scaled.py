"""A291 (R6a): half-grade ladder with the '+' — step_grade_scaled / step_grade_half.

Closes B-LEAD-HALF-GRADE-ROUNDING: the '+' of a reference grade is no longer
stripped before the catalog offset, the catalog unit stays one letter
(= 2 half grades), unknown grades emit nothing instead of a silent 6C.
"""

from __future__ import annotations

import pytest

from backend.engine.progression_v1 import (
    FONT_GRADES,
    FRENCH_GRADES,
    _grade_delta_for_feedback,
    apply_feedback,
    inject_targets,
    normalize_grade_on_scale,
    step_grade,
    step_grade_half,
    step_grade_scaled,
)


# ─── pure arithmetic ─────────────────────────────────────────────────────


@pytest.mark.parametrize("grade, offset, expected", [
    ("7A+", -2, "6B+"),
    ("7A+", -1, "6C+"),
    ("7A", -1, "6C"),
    ("7B+", 0, "7B+"),
    ("6C+", 1, "7A+"),
    ("8C", 1, "8C+"),    # clamp at the top of the Font ladder
    ("5A+", -1, "5A"),   # clamp at the bottom
    ("7a+", -1, "6C+"),  # lowercase input → canonical uppercase output
])
def test_font_table(grade, offset, expected):
    assert step_grade_scaled(grade, offset, "font") == expected


@pytest.mark.parametrize("grade, offset, expected", [
    ("7a+", -1, "6C+"),
    ("7a+", -5, "5B+"),
    ("7c+", -1, "7B+"),
    ("8a+", -3, "7A+"),
    ("9a", -1, "8C"),    # 9a − 1 letter = 8c (2 half grades)
    ("9a+", 1, "9A+"),   # clamp at the top of the French ladder
    ("5b", -2, "5A"),    # clamp at the bottom
])
def test_french_table(grade, offset, expected):
    assert step_grade_scaled(grade, offset, "french") == expected


def test_nine_a_minus_one_half_is_eight_c_plus():
    assert step_grade_half("9a", -1, "french") == "8C+"


def test_offset_zero_is_identity_and_keeps_plus():
    for g in FONT_GRADES:
        assert step_grade_scaled(g, 0, "font") == g
    for g in FRENCH_GRADES:
        assert step_grade_scaled(g.lower(), 0, "french") == g


@pytest.mark.parametrize("grade, scale", [
    ("9a", "font"),     # not a Font grade
    ("V5", "font"),
    ("", "french"),
    (None, "french"),
    ("12", "french"),
])
def test_unknown_grade_is_none(grade, scale):
    assert step_grade_scaled(grade, -1, scale) is None
    assert normalize_grade_on_scale(grade, scale) is None


def test_legacy_step_grade_unchanged():
    # Kept for compatibility; nothing in the engine calls it any more.
    assert step_grade("7A+", -1) == "6C"
    assert step_grade("9A", 0) == "6C"


def test_limit_feedback_delta_is_half_grades():
    assert [_grade_delta_for_feedback(lbl) for lbl in ("very_easy", "easy", "ok", "hard", "very_hard")] == [2, 1, 0, -1, -2]


# ─── engine wiring ───────────────────────────────────────────────────────


def _state(grades):
    return {
        "schema_version": "1.5",
        "assessment": {"grades": grades},
        "equipment": {"gyms": [{"gym_id": "g1", "equipment": ["gym_boulder", "board_kilter", "gym_routes"]}]},
        "working_loads": {"entries": []},
        "bodyweight_kg": 75,
    }


def _day(ex_id, prescription, date="2026-10-20"):
    return {
        "date": date,
        "sessions": [{"gym_id": "g1", "location": "gym",
                      "exercise_instances": [{"exercise_id": ex_id, "prescription": prescription}]}],
    }


def _suggested(day):
    return day["sessions"][0]["exercise_instances"][0].get("suggested") or {}


def test_daniele_route_intervals_six_c_plus():
    """Daniele (OS 7a+): route_intervals −1 was 6c, now 6c+."""
    s = _suggested(inject_targets(_day("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1}),
                                  _state({"lead_max_os": "7a+"})))
    assert s["suggested_grade"] == "6C+"
    assert s["grade_scale"] == "french"


def test_unknown_reference_grade_emits_no_suggested_grade():
    """A lead reference that is not on the ladder used to come out as a 6C-relative value."""
    s = _suggested(inject_targets(_day("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1}),
                                  _state({"lead_max_os": "V9"})))
    assert "suggested_grade" not in s
    assert "grade_scale" not in s


def test_lead_nine_a_reference_no_longer_collapses():
    s = _suggested(inject_targets(_day("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1}),
                                  _state({"lead_max_os": "9a"})))
    assert s["suggested_grade"] == "8C"


def test_limit_anchor_keeps_plus():
    """boulder_max_rp 7B+ + offset 0 on the gym wall → target 7B+ (was 7B)."""
    state = _state({"boulder_max_rp": "7B+"})
    state["equipment"]["gyms"][0]["equipment"] = ["gym_boulder"]
    day = inject_targets(_day("limit_bouldering", {"grade_ref": "boulder_max_rp", "grade_offset": 0}), state)
    target = _suggested(day)["suggested_boulder_target"]
    assert target["target_grade"] == "7B+"
    assert target["target_grade_low"] == "7A+"


def _feedback(state, ex_id, label, used, date, planned_prescription=None):
    planned = []
    if planned_prescription is not None:
        planned = [{"session_id": "s", "gym_id": "g1",
                    "exercise_instances": [{"exercise_id": ex_id, "prescription": planned_prescription}]}]
    log = {
        "date": date,
        "planned": planned,
        "actual": {"exercise_feedback_v1": [
            {"exercise_id": ex_id, "completed": True, "feedback_label": label, "used_grade": used},
        ]},
    }
    return apply_feedback(log, state)


def _entry(state, ex_id):
    return next(e for e in state["working_loads"]["entries"] if e["exercise_id"] == ex_id)


def test_limit_ok_keeps_plus_in_memory():
    """'ok' on 7A+ used to be stored as 7A (step_grade stripped the '+')."""
    state = _state({"boulder_max_rp": "7B"})
    log = {
        "date": "2026-10-20",
        "planned": [],
        "actual": {"exercise_feedback_v1": [{
            "exercise_id": "limit_bouldering", "completed": True, "feedback_label": "ok",
            "used_grade": "7A+", "surface_selected": "board_kilter",
        }]},
    }
    out = apply_feedback(log, state)
    assert _entry(out, "limit_bouldering")["next_target_grade"] == "7A+"


def test_endurance_lead_streak_steps_half_grade_on_french_scale():
    """Lead endurance memory: 2 concordant easy at 8c+ → 9A (French ladder; the
    Font list stops at 8C+ and used to drop the feedback)."""
    state = _state({"lead_max_os": "9a"})
    state = _feedback(state, "route_intervals", "easy", "8c+", "2026-10-20")
    state = _feedback(state, "route_intervals", "easy", "8c+", "2026-10-22")
    assert _entry(state, "route_intervals")["next_target_grade"] == "9A"


def test_endurance_custom_without_planned_uses_catalog_scale():
    """No planned instance (custom session): the scale comes from the catalog
    grade_ref (route_intervals → lead_max_os → french)."""
    state = _state({"lead_max_os": "7a+"})
    state = _feedback(state, "route_intervals", "hard", "6c+", "2026-10-20")
    state = _feedback(state, "route_intervals", "hard", "6c+", "2026-10-22")
    assert _entry(state, "route_intervals")["next_target_grade"] == "6C"
