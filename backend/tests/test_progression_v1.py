from __future__ import annotations

from copy import deepcopy

from backend.engine.progression_v1 import (
    HANGBOARD_DEFAULT_INTENSITY_PCT,
    apply_feedback,
    inject_targets,
    normalize_font_grade,
    step_grade,
)
from backend.engine.resolve_session import resolve_session


def _base_user_state() -> dict:
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 77.0,
        "baselines": {"hangboard": [{"max_total_load_kg": 102.0}]},
        "working_loads": {
            "entries": [{"exercise_id": "weighted_pullup", "next_external_load_kg": 10.0}],
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
                "session_id": "power_contact_gym",
                "intent": "power",
                "location": "gym",
                "gym_id": "blocx",
                "tags": {"hard": True},
                "exercise_instances": [
                    {"exercise_id": "limit_bouldering", "prescription": {}},
                    {"exercise_id": "max_hang_5s", "prescription": {"sets": 6, "work_seconds": 5, "edge_mm": 20, "grip": "half_crimp", "load_method": "added_weight"}, "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.9}},
                ],
            }
        ],
    }


def test_horst_7_53_intensity_is_max_strength():
    """Hörst 7-53 is a max strength protocol (90-95% MVC per catalog notes
    and Hörst/López literature), not a repeater. Regression guard for
    B-HORST-INTENSITY: previously set to 0.70 (repeater level)."""
    assert HANGBOARD_DEFAULT_INTENSITY_PCT["horst_7_53"] >= 0.88


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
                        "prescription": {"sets": 6, "work_seconds": 5},
                        "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.9},
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
    limit = next(i for i in first["sessions"][0]["exercise_instances"] if i["exercise_id"] == "limit_bouldering")
    base_grade = limit["suggested"]["suggested_boulder_target"]["target_grade"]

    log_entry = {
        "date": "2026-01-05",
        "planned": first["sessions"],
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": "limit_bouldering",
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
    limit_2 = next(i for i in second["sessions"][0]["exercise_instances"] if i["exercise_id"] == "limit_bouldering")
    new_grade = limit_2["suggested"]["suggested_boulder_target"]["target_grade"]

    assert normalize_font_grade(base_grade) is not None
    assert new_grade == "6C"  # 7B - 2 whole grades (very_hard)


def test_working_load_update_from_feedback():
    user_state = _base_user_state()
    log_easy = {
        "date": "2026-01-05",
        "planned": [{"exercise_instances": [{"exercise_id": "weighted_pullup", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{"exercise_id": "weighted_pullup", "completed": True, "feedback_label": "easy", "used_external_load_kg": 10.0}]},
    }
    updated_easy = apply_feedback(log_easy, user_state)
    easy_next = next(e for e in updated_easy["working_loads"]["entries"] if e["exercise_id"] == "weighted_pullup" and e.get("key") == "weighted_pullup")["next_external_load_kg"]
    assert easy_next == 16.5

    log_hard = {
        "date": "2026-01-06",
        "planned": [{"exercise_instances": [{"exercise_id": "weighted_pullup", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{"exercise_id": "weighted_pullup", "completed": True, "feedback_label": "very_hard", "used_external_load_kg": 10.0}]},
    }
    updated_hard = apply_feedback(log_hard, user_state)
    hard_next = next(e for e in updated_hard["working_loads"]["entries"] if e["exercise_id"] == "weighted_pullup" and e.get("key") == "weighted_pullup")["next_external_load_kg"]
    assert hard_next == 1.5


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
    assert queue[0]["test_id"] == "max_hang_7s_total_load"
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
    # step_grade uses whole-grade scale (vocabulary §2.10.1)
    assert step_grade("7A", 1) == "7B"
    assert step_grade("7B", 1) == "7C"
    assert step_grade("7C", -1) == "7B"
    assert step_grade("7C", -2) == "7A"
    # '+' inputs are stripped to base whole grade
    assert step_grade("7A+", 1) == "7B"
    assert step_grade("7B+", 1) == "7C"
    assert step_grade("7C+", -2) == "7A"


def test_gym_limit_bouldering_requires_surface(tmp_path):
    repo_root = str(tmp_path.parent)
    from pathlib import Path
    repo_root = str(Path(__file__).resolve().parents[2])

    def run_with_equipment(equipment: list[str]):
        user_state = _base_user_state()
        user_state["context"] = {"location": "gym", "gym_id": "blocx"}
        user_state["equipment"]["gyms"][0]["equipment"] = equipment
        out = resolve_session(
            repo_root=repo_root,
            session_path="backend/catalog/sessions/v1/power_contact_gym.json",
            templates_dir="backend/catalog/templates",
            exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="out/tmp/ignore.progression.json",
            user_state_override=user_state,
            write_output=False,
        )
        day = {"date": "2026-01-05", "sessions": [{"session_id": "power_contact_gym", "intent": "power", "location": "gym", "gym_id": "blocx", "tags": {"hard": True}, "exercise_instances": out["resolved_session"]["exercise_instances"]}]}
        return inject_targets(day, user_state)

    yes = run_with_equipment(["spraywall"])
    yes_inst = yes["sessions"][0]["exercise_instances"]
    limit = next(i for i in yes_inst if i["exercise_id"] == "limit_bouldering")
    target = limit.get("suggested", {}).get("suggested_boulder_target")
    assert target is not None
    assert target["surface_options"] == ["spraywall"]
    assert target["surface_selected"] == "spraywall"
    assert normalize_font_grade(target["target_grade"]) is not None

    no = run_with_equipment(["hangboard"])
    no_ids = [i["exercise_id"] for i in no["sessions"][0]["exercise_instances"]]
    assert "limit_bouldering" not in no_ids


# ─── B260: limit bouldering anchors to redpoint, not board benchmark ──────────

def _state_with_assessment_grades() -> dict:
    """Base state + a realistic assessment profile (RP boulder 7C, OS 7A).

    The base state's Kilter benchmark (7B) and worked grade (7C) remain — so
    a target of 7C proves the anchor is boulder_max_rp, NOT the board benchmark.
    """
    us = _base_user_state()
    us["assessment"] = {
        "grades": {
            "boulder_max_rp": "7C",
            "boulder_max_os": "7A",
            "lead_max_rp": "8a",
            "lead_max_os": "7a+",
        }
    }
    return us


def test_b260_limit_bouldering_anchors_to_redpoint():
    """limit_bouldering target = boulder_max_rp (RP-1 -> RP band), not benchmark.

    Regression for B260: previously anchored to the Kilter board benchmark
    (~7A) via _extract_grade_benchmark, producing 7A. Must anchor to
    boulder_max_rp (7C) with offset 0 -> 7C high, 7B low.
    """
    out = inject_targets(_resolved_day_for_progression(), _state_with_assessment_grades())
    limit = next(i for i in out["sessions"][0]["exercise_instances"]
                 if i["exercise_id"] == "limit_bouldering")
    bt = limit["suggested"]["suggested_boulder_target"]
    assert bt["target_grade"] == "7C"      # boulder_max_rp + 0
    assert bt["target_grade_low"] == "7B"  # boulder_max_rp - 1  => band 7B->7C


def test_b260_limit_bouldering_falls_back_to_benchmark_when_grade_missing():
    """When assessment.grades has no boulder_max_rp, fall back to the board
    benchmark (legacy behaviour) rather than crashing or defaulting blindly."""
    us = _base_user_state()  # no assessment.grades -> benchmark 7B fallback
    out = inject_targets(_resolved_day_for_progression(), us)
    limit = next(i for i in out["sessions"][0]["exercise_instances"]
                 if i["exercise_id"] == "limit_bouldering")
    bt = limit["suggested"]["suggested_boulder_target"]
    assert bt["target_grade"] == "7B"      # benchmark 7B + 0
    assert bt["target_grade_low"] == "7A"  # benchmark 7B - 1


def test_b260_other_limit_exercises_unchanged():
    """B260 regression, updated by B289 group A: the other 3 limit boulder
    exercises now share limit_bouldering's rich suggested_boulder_target path
    (surface-keyed memory) instead of the flat suggested_grade. Anchor is
    unchanged: boulder_max_rp + 0 → 7C."""
    us = _state_with_assessment_grades()
    for ex in ("board_limit_boulders", "spray_wall_limit", "system_board_limit"):
        day = {
            "date": "2026-01-05",
            "sessions": [{
                "intent": "power", "gym_id": "blocx", "tags": {"hard": True},
                "exercise_instances": [{
                    "exercise_id": ex,
                    "prescription": {"grade_ref": "boulder_max_rp", "grade_offset": 0},
                }],
            }],
        }
        out = inject_targets(day, deepcopy(us))
        sug = out["sessions"][0]["exercise_instances"][0]["suggested"]
        assert "suggested_grade" not in sug, ex  # B289: no more flat path
        bt = sug["suggested_boulder_target"]
        assert bt["target_grade"] == "7C", ex
        assert bt["target_grade_low"] == "7B", ex


def test_b260_rich_boulder_target_payload_intact():
    """The rich suggested_boulder_target payload (surface options/selection,
    band, intensity, intent-driven guidance) survives the anchor change."""
    out = inject_targets(_resolved_day_for_progression(), _state_with_assessment_grades())
    bt = next(i for i in out["sessions"][0]["exercise_instances"]
              if i["exercise_id"] == "limit_bouldering")["suggested"]["suggested_boulder_target"]
    assert bt["schema_version"] == "boulder_grade_font_v0"
    assert bt["surface_options"] == ["board_kilter", "spraywall"]
    assert bt["surface_selected"] == "board_kilter"
    assert bt["target_grade"] == "7C" and bt["target_grade_low"] == "7B"
    assert bt["intensity_label"] == "hard"
    assert bt["attempt_guidance"]  # intent=power -> guidance present
    assert bt["rest_guidance"]


def test_b260_completed_limit_bouldering_target_immutable():
    """CRITICAL invariant: a completed limit_bouldering session keeps its frozen
    target_grade across regeneration. The anchor change must NOT rewrite the
    target on past/completed sessions.

    Simulates an old plan completed under the OLD anchor (7A) being merged into a
    freshly regenerated plan that would now compute 7C. The done session must
    retain 7A.
    """
    from backend.engine.replanner_v1 import regenerate_preserving_completed

    old_plan = {"weeks": [{"days": [{
        "date": "2026-01-05",
        "sessions": [{
            "slot": "morning", "status": "done", "session_id": "power_contact_gym",
            "exercise_instances": [{
                "exercise_id": "limit_bouldering",
                "suggested": {"suggested_boulder_target": {
                    "schema_version": "boulder_grade_font_v0",
                    "target_grade": "7A", "target_grade_low": "6C",
                }},
            }],
        }],
    }]}]}
    new_plan = {"weeks": [{"days": [{
        "date": "2026-01-05",
        "sessions": [{
            "slot": "morning", "status": "planned", "session_id": "power_contact_gym",
            "exercise_instances": [{
                "exercise_id": "limit_bouldering",
                "suggested": {"suggested_boulder_target": {
                    "schema_version": "boulder_grade_font_v0",
                    "target_grade": "7C", "target_grade_low": "7B",
                }},
            }],
        }],
    }]}]}

    merged = regenerate_preserving_completed(old_plan, new_plan)
    day = merged["weeks"][0]["days"][0]
    s = next(x for x in day["sessions"] if x.get("slot") == "morning")
    bt = s["exercise_instances"][0]["suggested"]["suggested_boulder_target"]
    assert s["status"] == "done"
    assert bt["target_grade"] == "7A"      # frozen old value preserved
    assert bt["target_grade_low"] == "6C"  # NOT recomputed to 7C/7B
