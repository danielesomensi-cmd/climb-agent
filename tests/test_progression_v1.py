from __future__ import annotations

from copy import deepcopy

from catalog.engine.progression_v1 import apply_feedback, inject_targets, normalize_font_grade, step_grade
from catalog.engine.resolve_session import resolve_session


def _base_user_state() -> dict:
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 77.0,
        "baselines": {"hangboard": [{"max_total_load_kg": 102.0}]},
        "working_loads": {
            "entries": [{"exercise_id": "pullup", "next_external_load_kg": 10.0}],
            "rules": {
                "feedback_scale": ["very_easy", "easy", "ok", "hard", "very_hard"],
                "adjustment_policy": {
                    "very_easy": {"pct_range": [0.1, 0.2]},
                    "easy": {"pct_range": [0.05, 0.1]},
                    "ok": {"pct_range": [0.0, 0.05]},
                    "hard": {"pct_range": [-0.05, 0.0]},
                    "very_hard": {"pct_range": [-0.15, -0.05]},
                },
            },
        },
        "performance": {
            "gym_reference": {"kilter": {"benchmark": {"grade": "7B"}}},
            "current_level": {"boulder": {"worked": {"grade": "7C"}}},
        },
        "equipment": {
            "home": ["hangboard", "pullup_bar"],
            "gyms": [{"gym_id": "blocx", "equipment": ["board_kilter", "spraywall"]}, {"gym_id": "work_gym", "equipment": []}],
        },
    }


def _resolved_day_for_progression() -> dict:
    return {
        "date": "2026-01-05",
        "sessions": [
            {
                "session_id": "gym_power_bouldering",
                "intent": "power",
                "location": "gym",
                "gym_id": "blocx",
                "tags": {"hard": True},
                "exercise_instances": [
                    {"exercise_id": "gym_limit_bouldering", "prescription": {}},
                    {"exercise_id": "max_hang_5s", "prescription": {"sets": 6, "hang_seconds": 5, "intensity_pct_of_total_load": 0.9, "edge_mm": 20, "grip": "half_crimp", "load_method": "added_weight"}},
                ],
            }
        ],
    }


def test_inject_targets_deterministic():
    user_state = _base_user_state()
    resolved_day = _resolved_day_for_progression()

    out_a = inject_targets(deepcopy(resolved_day), deepcopy(user_state))
    out_b = inject_targets(deepcopy(resolved_day), deepcopy(user_state))
    assert out_a == out_b


def test_load_based_progression_changes_next_target():
    user_state = _base_user_state()
    resolved_day = _resolved_day_for_progression()

    first = inject_targets(deepcopy(resolved_day), deepcopy(user_state))
    max_hang = next(i for i in first["sessions"][0]["exercise_instances"] if i["exercise_id"] == "max_hang_5s")
    x = float(max_hang["suggested"]["suggested_external_load_kg"])

    log_entry = {
        "date": "2026-01-05",
        "planned": first["sessions"],
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "max_hang_5s",
                    "completed": True,
                    "feedback_label": "easy",
                    "used_external_load_kg": x,
                    "used_total_load_kg": 77.0 + x,
                    "edge_mm": 20,
                    "grip": "half_crimp",
                    "load_method": "added_weight",
                }
            ]
        },
    }
    updated_state = apply_feedback(log_entry, user_state)

    second_day = deepcopy(resolved_day)
    second_day["date"] = "2026-01-06"
    second = inject_targets(second_day, updated_state)
    second_hang = next(i for i in second["sessions"][0]["exercise_instances"] if i["exercise_id"] == "max_hang_5s")
    assert second_hang["suggested"]["suggested_external_load_kg"] > x




def test_max_hang_override_precedence_and_total_recompute_with_missing_setup_in_prescription():
    user_state = _base_user_state()
    user_state["working_loads"]["entries"].append(
        {
            "exercise_id": "max_hang_5s",
            "key": "max_hang_5s|edge_mm=20|grip=half_crimp|load_method=added_weight",
            "setup": {"edge_mm": 20, "grip": "half_crimp", "load_method": "added_weight"},
            "next_external_load_kg": 16.0,
            "next_total_load_kg": 99.0,
            "updated_at": "2026-01-05",
        }
    )

    day = {
        "date": "2026-01-06",
        "sessions": [
            {
                "session_id": "strength_long",
                "intent": "strength",
                "location": "home",
                "gym_id": None,
                "tags": {"hard": True, "finger": True},
                "exercise_instances": [
                    {
                        "exercise_id": "max_hang_5s",
                        "prescription": {"sets": 6, "hang_seconds": 5, "intensity_pct_of_total_load": 0.9},
                        "suggested": {
                            "schema_version": "progression_targets.v1",
                            "suggested_external_load_kg": 15.0,
                            "edge_mm": 20,
                            "grip": "half_crimp",
                            "load_method": "added_weight",
                        },
                    }
                ],
            }
        ],
    }

    out = inject_targets(day, user_state)
    suggested = out["sessions"][0]["exercise_instances"][0]["suggested"]
    assert suggested["suggested_external_load_kg"] == 16.0
    assert suggested["suggested_total_load_kg"] == 93.0


def test_boulder_grade_progression_changes_next_target():
    user_state = _base_user_state()
    resolved_day = _resolved_day_for_progression()

    first = inject_targets(deepcopy(resolved_day), deepcopy(user_state))
    limit = next(i for i in first["sessions"][0]["exercise_instances"] if i["exercise_id"] == "gym_limit_bouldering")
    base_grade = limit["suggested"]["suggested_boulder_target"]["target_grade"]

    log_entry = {
        "date": "2026-01-05",
        "planned": first["sessions"],
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "gym_limit_bouldering",
                    "completed": True,
                    "feedback_label": "very_hard",
                    "used_grade": "7B",
                    "surface_selected": "board_kilter",
                }
            ]
        },
    }
    updated_state = apply_feedback(log_entry, user_state)

    second_day = deepcopy(resolved_day)
    second_day["date"] = "2026-01-06"
    second = inject_targets(second_day, updated_state)
    limit_2 = next(i for i in second["sessions"][0]["exercise_instances"] if i["exercise_id"] == "gym_limit_bouldering")
    new_grade = limit_2["suggested"]["suggested_boulder_target"]["target_grade"]

    assert normalize_font_grade(base_grade) is not None
    assert new_grade == "7A"


def test_working_load_update_from_feedback():
    user_state = _base_user_state()
    log_easy = {
        "date": "2026-01-05",
        "planned": [{"exercise_instances": [{"exercise_id": "pullup", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{"exercise_id": "pullup", "completed": True, "feedback_label": "easy", "used_external_load_kg": 10.0}]},
    }
    updated_easy = apply_feedback(log_easy, user_state)
    easy_next = next(e for e in updated_easy["working_loads"]["entries"] if e["exercise_id"] == "pullup" and e.get("key") == "pullup")["next_external_load_kg"]
    assert easy_next == 11.0

    log_hard = {
        "date": "2026-01-06",
        "planned": [{"exercise_instances": [{"exercise_id": "pullup", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{"exercise_id": "pullup", "completed": True, "feedback_label": "very_hard", "used_external_load_kg": 10.0}]},
    }
    updated_hard = apply_feedback(log_hard, user_state)
    hard_next = next(e for e in updated_hard["working_loads"]["entries"] if e["exercise_id"] == "pullup" and e.get("key") == "pullup")["next_external_load_kg"]
    assert hard_next == 9.0


def test_two_hard_feedbacks_enqueue_retest_and_retest_updates_official_test():
    user_state = _base_user_state()
    resolved_day = _resolved_day_for_progression()
    first = inject_targets(deepcopy(resolved_day), deepcopy(user_state))

    log_hard_1 = {
        "date": "2026-01-05",
        "planned": first["sessions"],
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "max_hang_5s",
                    "completed": True,
                    "feedback_label": "very_hard",
                    "used_external_load_kg": 14.5,
                    "used_total_load_kg": 91.5,
                    "edge_mm": 20,
                    "grip": "half_crimp",
                    "load_method": "added_weight",
                }
            ]
        },
    }
    after_1 = apply_feedback(log_hard_1, user_state)
    assert (after_1.get("test_queue") or []) == []

    log_hard_2 = deepcopy(log_hard_1)
    log_hard_2["date"] = "2026-01-06"
    after_2 = apply_feedback(log_hard_2, after_1)
    queue = after_2.get("test_queue") or []
    assert len(queue) == 1
    assert queue[0]["test_id"] == "max_hang_5s_total_load"
    assert queue[0]["recommended_by_date"] == "2026-01-13"

    test_log = {
        "date": "2026-01-13",
        "planned": [{"session_id": "test_max_hang_5s", "tags": {"test": True}}],
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "max_hang_5s",
                    "completed": True,
                    "feedback_label": "ok",
                    "used_total_load_kg": 105.0,
                }
            ]
        },
    }
    after_test = apply_feedback(test_log, after_2)
    assert after_test["baselines"]["hangboard"][0]["max_total_load_kg"] == 105.0
    max_strength_tests = after_test["tests"]["max_strength"]
    assert any(t["test_id"] == "max_hang_5s_total_load" and t["total_load_kg"] == 105.0 for t in max_strength_tests)


def test_font_grade_stepper():
    assert normalize_font_grade("7a") == "7A"
    assert step_grade("7A", 1) == "7A+"
    assert step_grade("7A+", 1) == "7B"
    assert step_grade("7B", 1) == "7B+"
    assert step_grade("7B+", 1) == "7C"
    assert step_grade("7C", -1) == "7B+"


def test_gym_limit_bouldering_requires_surface(tmp_path):
    repo_root = str(tmp_path.parent)
    from pathlib import Path
    repo_root = str(Path(__file__).resolve().parents[1])

    def run_with_equipment(equipment: list[str]):
        user_state = _base_user_state()
        user_state["context"] = {"location": "gym", "gym_id": "blocx"}
        user_state["equipment"]["gyms"][0]["equipment"] = equipment
        out = resolve_session(
            repo_root=repo_root,
            session_path="catalog/sessions/v1/gym_power_bouldering.json",
            templates_dir="catalog/templates",
            exercises_path="catalog/exercises/v1/exercises.json",
            out_path="out/tmp/ignore.progression.json",
            user_state_override=user_state,
            write_output=False,
        )
        day = {"date": "2026-01-05", "sessions": [{"session_id": "gym_power_bouldering", "intent": "power", "location": "gym", "gym_id": "blocx", "tags": {"hard": True}, "exercise_instances": out["resolved_session"]["exercise_instances"]}]}
        return inject_targets(day, user_state)

    yes = run_with_equipment(["spraywall"])
    yes_inst = yes["sessions"][0]["exercise_instances"]
    limit = next(i for i in yes_inst if i["exercise_id"] == "gym_limit_bouldering")
    target = limit.get("suggested", {}).get("suggested_boulder_target")
    assert target is not None
    assert target["surface_options"] == ["spraywall"]
    assert target["surface_selected"] == "spraywall"
    assert normalize_font_grade(target["target_grade"]) is not None

    no = run_with_equipment(["hangboard"])
    no_ids = [i["exercise_id"] for i in no["sessions"][0]["exercise_instances"]]
    assert "gym_limit_bouldering" not in no_ids
