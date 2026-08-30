"""B344 — `ok` is neutral, 0 kg is not absorbing, and lead targets say so.

Three defects found by the D280 methodology audit, all in progression_v1:

1. `ok` carried pct_range [0.00, 0.05] → a +2.5% midpoint on EVERY session.
   It is also the label the feedback dialog ships when the user rates nothing
   ("Unrated exercises default to Ok"), so the zero-input path signed a load
   increase. ~2 finger sessions/week compounds to +5%/week against a ~2%/week
   adaptation rate (Devise et al. 2022).

2. `next = base * (1 + pct)` makes 0.0 kg an absorbing state — every label,
   `very_easy` included, returns 0.0. Seen in production on `back_squat`.
   The same trap freezes the whole small-load prehab regime.

3. A rope target anchored to `lead_max_os` was handed to the UI as "6C".
   The arithmetic is right (vocabulary §2.10.1 puts Font and French on the
   same whole-grade ladder), the CASING is not: uppercase 6C reads as a Font
   boulder grade, ~7a+ French.
"""

import pytest

from backend.engine.progression_v1 import (
    MIN_EXTERNAL_LOAD_STEP_KG,
    apply_feedback,
    grade_scale_for_ref,
    inject_targets,
    _next_external_load,
    _rule_midpoint_pct,
)


def _state(**over):
    st = {
        "bodyweight_kg": 76.0,
        "body": {"weight_kg": 76.0},
        "assessment": {
            "grades": {
                "boulder_max_os": "7A",
                "boulder_max_rp": "7C",
                "lead_max_os": "7a+",
                "lead_max_rp": "8a+",
            }
        },
        "working_loads": {"entries": [], "rules": {}},
    }
    st.update(over)
    return st


def _log(exercise_id, label, *, used_external=None, used_total=None, load_model="external_load",
         date="2026-08-30", hand=None):
    item = {"exercise_id": exercise_id, "completed": True, "feedback_label": label,
            "load_model": load_model}
    if used_external is not None:
        item["used_external_load_kg"] = used_external
    if used_total is not None:
        item["used_total_load_kg"] = used_total
    if hand:
        item["hand"] = hand
    return {"date": date, "actual": {"exercise_feedback_v1": [item]}}


def _entry(state, key):
    for e in state["working_loads"]["entries"]:
        if e.get("key") == key or e.get("exercise_id") == key:
            return e
    return None


# ─── 1. `ok` is neutral ──────────────────────────────────────────────────────

def test_ok_is_neutral_in_default_policy():
    assert _rule_midpoint_pct(_state(), "ok") == 0.0


@pytest.mark.parametrize("label,expected", [
    ("very_easy", 0.15), ("easy", 0.075), ("ok", 0.0), ("hard", -0.025), ("very_hard", -0.10),
])
def test_other_labels_unchanged(label, expected):
    """Only `ok` moved — the rest of the scale must be untouched."""
    assert _rule_midpoint_pct(_state(), label) == pytest.approx(expected)


def test_ok_does_not_move_external_load():
    out = apply_feedback(_log("bench_press", "ok", used_external=32.0), _state())
    e = _entry(out, "bench_press")
    assert e["last_external_load_kg"] == 32.0
    assert e["next_external_load_kg"] == 32.0


def test_ok_does_not_move_total_load():
    """The finger path: `ok` on a max hang must not add 2.5% of BODYWEIGHT+load."""
    out = apply_feedback(
        _log("max_hang_7s", "ok", used_total=122.0, load_model="total_load"), _state()
    )
    e = _entry(out, "max_hang_7s")
    assert e["next_total_load_kg"] == 122.0
    assert e["next_external_load_kg"] == 46.0  # 122 - 76, unchanged


def test_ok_ten_times_is_a_plateau_not_a_ramp():
    """The production scenario: ten 'ok' sessions used to reach ~116% of the max."""
    st = _state()
    for i in range(10):
        st = apply_feedback(
            _log("max_hang_7s", "ok", used_total=122.0, load_model="total_load",
                 date=f"2026-08-{10 + i:02d}"),
            st,
        )
    assert _entry(st, "max_hang_7s")["next_total_load_kg"] == 122.0


def test_stored_user_policy_still_wins():
    """Changing the DEFAULT must not silently rewrite an explicit user choice."""
    st = _state()
    st["working_loads"]["rules"] = {"adjustment_policy": {"ok": {"pct_range": [0.0, 0.05]}}}
    assert _rule_midpoint_pct(st, "ok") == pytest.approx(0.025)
    out = apply_feedback(_log("bench_press", "ok", used_external=32.0), st)
    assert _entry(out, "bench_press")["next_external_load_kg"] == 33.0


# ─── 2. 0 kg is not an absorbing state ───────────────────────────────────────

def test_zero_load_with_very_easy_moves_up():
    """The `back_squat` bug: 0.0 kg + very_easy used to return 0.0 forever."""
    out = apply_feedback(_log("back_squat", "very_easy", used_external=0.0), _state())
    e = _entry(out, "back_squat")
    assert e["last_external_load_kg"] == 0.0, "B288: 0 kg must still be RECORDED"
    assert e["next_external_load_kg"] == MIN_EXTERNAL_LOAD_STEP_KG


def test_zero_load_with_ok_stays_zero():
    """Interaction of both fixes: 'it was fine at bodyweight' must mean no change."""
    out = apply_feedback(_log("back_squat", "ok", used_external=0.0), _state())
    e = _entry(out, "back_squat")
    assert e["last_external_load_kg"] == 0.0
    assert e["next_external_load_kg"] == 0.0


def test_small_load_regime_is_not_frozen():
    """1.0 kg + easy = 1.075 → rounded back to 1.0. This is where prehab lives."""
    out = apply_feedback(_log("elbow_eccentric_curl", "easy", used_external=1.0), _state())
    assert _entry(out, "elbow_eccentric_curl")["next_external_load_kg"] == 1.5


def test_floor_is_asymmetric_by_decision():
    """Decision Daniele 2026-08-30: no downward floor — prehab is already minimal."""
    out = apply_feedback(_log("elbow_eccentric_curl", "very_hard", used_external=1.0), _state())
    assert _entry(out, "elbow_eccentric_curl")["next_external_load_kg"] == 1.0


def test_loading_pin_branch_also_fixed():
    """The per-hand finger branch had the same multiplier."""
    out = apply_feedback(
        _log("lp_max_lift_5s", "very_easy", used_external=0.0, hand="right"), _state()
    )
    assert _entry(out, "lp_max_lift_5s:right")["next_external_load_kg"] == MIN_EXTERNAL_LOAD_STEP_KG


def test_normal_loads_unaffected_by_the_floor():
    """The floor must never perturb a load the multiplier can already move."""
    assert _next_external_load(30.0, 0.075) == 32.0   # 32.25 → 32.0, no floor
    assert _next_external_load(30.0, 0.0) == 30.0
    assert _next_external_load(30.0, -0.10) == 27.0


# ─── 3. grade scale hint ─────────────────────────────────────────────────────

@pytest.mark.parametrize("ref,expected", [
    ("lead_max_os", "french"),
    ("lead_max_rp", "french"),
    ("boulder_max_os", "font"),
    ("boulder_max_rp", "font"),
    (None, "font"),
])
def test_grade_scale_for_ref(ref, expected):
    assert grade_scale_for_ref(ref) == expected


def _day(exercise_id, prescription):
    return {
        "date": "2026-08-30",
        "sessions": [{
            "session_id": "route_endurance_gym",
            "exercise_instances": [{
                "exercise_id": exercise_id,
                "load_model": "grade_relative",
                "prescription": prescription,
            }],
        }],
    }


def test_lead_anchored_target_is_marked_french():
    """route_intervals anchors to lead_max_os → the client must render '6c', not '6C'."""
    day = inject_targets(_day("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -1}),
                         _state())
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    # Engine convention is unchanged: canonical uppercase on the wire.
    assert s["suggested_grade"] == "6C"
    assert s["grade_scale"] == "french"


def test_boulder_anchored_target_stays_font():
    day = inject_targets(_day("four_by_four_bouldering",
                              {"grade_ref": "boulder_max_rp", "grade_offset": -2}),
                         _state())
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    assert s["grade_scale"] == "font"
