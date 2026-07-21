"""B289 — grade_relative progression for the whole catalog, not just limit_bouldering.

Three groups by pattern (see progression_v1._grade_relative_group):
- A "limit"     (climbing_limit_boulder): surface-keyed memory, per-feedback steps.
- B "endurance" (climbing_intervals/continuous): exercise_id-keyed memory,
                step only after 2 consecutive concordant feedbacks.
- C "technique" (technique_drill): used_grade deliberately NOT stored.
"""

from copy import deepcopy

from backend.engine.progression_v1 import (
    _grade_relative_group,
    apply_feedback,
    inject_targets,
)


def _user_state():
    return {
        "user": {"id": "test", "name": "Test"},
        "bodyweight_kg": 70.0,
        "assessment": {
            "grades": {
                "boulder_max_rp": "7A",
                "boulder_max_os": "6B",
                "lead_max_rp": "7a",
                "lead_max_os": "6b",
            }
        },
        "equipment": {"gyms": [{"gym_id": "g1", "name": "G", "equipment": ["gym_boulder", "board_kilter"]}]},
        "working_loads": {"rules": {}, "entries": []},
    }


def _log(exercise_id: str, label: str, used_grade: str | None, date: str = "2026-01-05", **extra):
    item = {"exercise_id": exercise_id, "completed": True, "feedback_label": label}
    if used_grade is not None:
        item["used_grade"] = used_grade
    item.update(extra)
    return {
        "date": date,
        "planned": [{"gym_id": "g1", "exercise_instances": [{"exercise_id": exercise_id, "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [item]},
    }


def _entries(state):
    return (state.get("working_loads") or {}).get("entries") or []


# ─── Group classification ────────────────────────────────────────────────


def test_group_classification():
    assert _grade_relative_group("limit_bouldering") == "limit"
    assert _grade_relative_group("board_limit_boulders") == "limit"
    assert _grade_relative_group("spray_wall_limit") == "limit"
    assert _grade_relative_group("system_board_limit") == "limit"
    assert _grade_relative_group("four_by_four_bouldering") == "endurance"
    assert _grade_relative_group("arc_training") == "endurance"
    assert _grade_relative_group("silent_feet_drill") == "technique"
    assert _grade_relative_group("max_hang_7s") is None  # not grade_relative
    assert _grade_relative_group("nonexistent_exercise") is None


# ─── Group A: limit family ───────────────────────────────────────────────


def test_board_limit_writes_surface_keyed_entry():
    state = _user_state()
    out = apply_feedback(_log("board_limit_boulders", "easy", "7A", surface_selected="board_kilter"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "board_limit_boulders")
    assert entry["key"] == "board_limit_boulders|surface=board_kilter"
    assert entry["last_used_grade"] == "7A"
    assert entry["next_target_grade"] == "7B"  # easy → +1 whole grade


def test_limit_family_very_hard_steps_down_two():
    state = _user_state()
    out = apply_feedback(_log("spray_wall_limit", "very_hard", "7B", surface_selected="spraywall"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "spray_wall_limit")
    assert entry["next_target_grade"] == "6C"  # very_hard → -2 whole grades


def test_limit_family_memory_overrides_suggest_target():
    state = _user_state()
    state = apply_feedback(_log("board_limit_boulders", "easy", "7A", surface_selected="board_kilter"), state)
    day = {
        "date": "2026-01-06",
        "sessions": [{
            "gym_id": "g1",
            "exercise_instances": [{"exercise_id": "board_limit_boulders", "prescription": {}}],
        }],
    }
    out = inject_targets(day, state)
    target = out["sessions"][0]["exercise_instances"][0]["suggested"]["suggested_boulder_target"]
    assert target["target_grade"] == "7B"  # from memory, not the 7A anchor


def test_limit_bouldering_unchanged_regression():
    # The historical exercise keeps its exact pre-B289 behaviour.
    state = _user_state()
    out = apply_feedback(_log("limit_bouldering", "very_hard", "7B", surface_selected="board_kilter"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "limit_bouldering")
    assert entry["key"] == "limit_bouldering|surface=board_kilter"
    assert entry["next_target_grade"] == "6C"


# ─── Group B: endurance — streak rule ────────────────────────────────────


def test_endurance_single_easy_does_not_step():
    state = _user_state()
    out = apply_feedback(_log("four_by_four_bouldering", "easy", "6B"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "four_by_four_bouldering")
    assert entry["key"] == "four_by_four_bouldering"  # no setup in the key
    assert entry["setup"] == {}
    assert entry["next_target_grade"] == "6B"  # anchored, not stepped
    assert entry["grade_streak_direction"] == 1
    assert entry["grade_streak_count"] == 1


def test_endurance_two_concordant_easy_step_up():
    state = _user_state()
    state = apply_feedback(_log("four_by_four_bouldering", "easy", "6B", date="2026-01-05"), state)
    out = apply_feedback(_log("four_by_four_bouldering", "very_easy", "6B", date="2026-01-08"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "four_by_four_bouldering")
    assert entry["next_target_grade"] == "6C"  # 2 concordant → +1 (never ±2)
    assert entry["grade_streak_count"] == 0  # streak consumed
    assert entry["grade_streak_direction"] == 0


def test_endurance_two_concordant_hard_step_down():
    state = _user_state()
    state = apply_feedback(_log("route_intervals", "hard", "6C", date="2026-01-05"), state)
    out = apply_feedback(_log("route_intervals", "very_hard", "6C", date="2026-01-08"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "route_intervals")
    assert entry["next_target_grade"] == "6B"


def test_endurance_discordant_feedback_resets_streak():
    state = _user_state()
    state = apply_feedback(_log("four_by_four_bouldering", "easy", "6B", date="2026-01-05"), state)
    out = apply_feedback(_log("four_by_four_bouldering", "hard", "6B", date="2026-01-08"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "four_by_four_bouldering")
    assert entry["next_target_grade"] == "6B"  # no step
    assert entry["grade_streak_direction"] == -1
    assert entry["grade_streak_count"] == 1


def test_endurance_ok_resets_streak_and_reanchors():
    state = _user_state()
    state = apply_feedback(_log("four_by_four_bouldering", "easy", "6B", date="2026-01-05"), state)
    out = apply_feedback(_log("four_by_four_bouldering", "ok", "6C", date="2026-01-08"), state)
    entry = next(e for e in _entries(out) if e["exercise_id"] == "four_by_four_bouldering")
    assert entry["next_target_grade"] == "6C"  # re-anchored to what was used
    assert entry["grade_streak_direction"] == 0
    assert entry["grade_streak_count"] == 0


def test_endurance_missing_grade_is_skipped():
    state = _user_state()
    out = apply_feedback(_log("four_by_four_bouldering", "easy", None), state)
    assert not [e for e in _entries(out) if e["exercise_id"] == "four_by_four_bouldering"]


def test_endurance_memory_overrides_static_suggestion():
    state = _user_state()
    state = apply_feedback(_log("four_by_four_bouldering", "easy", "6B", date="2026-01-05"), state)
    state = apply_feedback(_log("four_by_four_bouldering", "easy", "6B", date="2026-01-08"), state)
    day = {
        "date": "2026-01-10",
        "sessions": [{
            "gym_id": "g1",
            "exercise_instances": [{
                "exercise_id": "four_by_four_bouldering",
                "prescription": {"grade_ref": "boulder_max_os", "grade_offset": -1},
            }],
        }],
    }
    out = inject_targets(day, state)
    suggested = out["sessions"][0]["exercise_instances"][0]["suggested"]
    assert suggested["suggested_grade"] == "6C"  # memory, not 6B-1
    assert suggested["grade_source"] == "working_loads"


def test_endurance_fallback_to_assessment_without_memory():
    state = _user_state()
    day = {
        "date": "2026-01-10",
        "sessions": [{
            "gym_id": "g1",
            "exercise_instances": [{
                "exercise_id": "four_by_four_bouldering",
                "prescription": {"grade_ref": "boulder_max_os", "grade_offset": -1},
            }],
        }],
    }
    out = inject_targets(day, state)
    suggested = out["sessions"][0]["exercise_instances"][0]["suggested"]
    assert suggested["suggested_grade"] == "6A"  # boulder_max_os 6B, offset -1
    assert "grade_source" not in suggested


def test_endurance_stale_memory_falls_back():
    # Memory older than the 60-day freshness gate is ignored.
    state = _user_state()
    state = apply_feedback(_log("four_by_four_bouldering", "easy", "6B", date="2025-10-01"), state)
    state = apply_feedback(_log("four_by_four_bouldering", "easy", "6B", date="2025-10-04"), state)
    day = {
        "date": "2026-01-10",
        "sessions": [{
            "gym_id": "g1",
            "exercise_instances": [{
                "exercise_id": "four_by_four_bouldering",
                "prescription": {"grade_ref": "boulder_max_os", "grade_offset": 0},
            }],
        }],
    }
    out = inject_targets(day, state)
    suggested = out["sessions"][0]["exercise_instances"][0]["suggested"]
    assert "grade_source" not in suggested


# ─── Group C: technique drills — deliberate no-op ────────────────────────


def test_technique_drill_used_grade_not_stored():
    state = _user_state()
    out = apply_feedback(_log("silent_feet_drill", "easy", "5C"), state)
    assert not [e for e in _entries(out) if e["exercise_id"] == "silent_feet_drill"]


def test_technique_drill_no_entry_even_after_repeat():
    state = _user_state()
    state = apply_feedback(_log("tech_five_step", "easy", "5C", date="2026-01-05"), state)
    out = apply_feedback(_log("tech_five_step", "easy", "5C", date="2026-01-08"), state)
    assert not [e for e in _entries(out) if e["exercise_id"] == "tech_five_step"]


# ─── Determinism ─────────────────────────────────────────────────────────


def test_apply_feedback_deterministic():
    state = _user_state()
    log = _log("four_by_four_bouldering", "easy", "6B")
    out1 = apply_feedback(deepcopy(log), deepcopy(state))
    out2 = apply_feedback(deepcopy(log), deepcopy(state))
    assert out1 == out2
