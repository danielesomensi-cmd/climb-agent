"""Tests for working loads: grade resolver, external load, hangboard total load, wiring."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from backend.engine.progression_v1 import (
    EXTERNAL_LOAD_EXERCISES,
    HANGBOARD_TOTAL_LOAD_EXERCISES,
    LOAD_BASED_EXERCISES,
    _get_bodyweight,
    _rule_midpoint_pct,
    apply_feedback,
    estimate_missing_baselines,
    inject_targets,
    step_grade,
)
from backend.engine.resolve_session import resolve_session

REPO_ROOT = str(Path(__file__).resolve().parents[2])


def _base_user_state() -> dict:
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 77.0,
        "baselines": {"hangboard": [{"max_total_load_kg": 102.0}]},
        "assessment": {
            "grades": {
                "boulder_max_os": "7A+",
                "boulder_max_rp": "7C",
                "lead_max_os": "7a+",
                "lead_max_rp": "8a+",
            },
        },
        "working_loads": {
            "entries": [],
            "rules": {
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
        },
        "equipment": {
            "home": ["hangboard", "pullup_bar"],
            "gyms": [{"gym_id": "blocx", "equipment": ["board_kilter", "spraywall"]}],
        },
    }


def _day_with_exercises(exercises: list[dict], date: str = "2026-01-05") -> dict:
    return {
        "date": date,
        "sessions": [{
            "session_id": "test_session",
            "intent": "strength",
            "location": "home",
            "gym_id": None,
            "tags": {},
            "exercise_instances": exercises,
        }],
    }


# ─── Grade resolver (5 tests) ────────────────────────────────────────────────

def test_grade_relative_boulder_os():
    """grade_ref=boulder_max_os, offset=-2 → step_grade("7A+", -2) = "5C" (strips +, whole-grade)."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "silent_feet_drill",
        "prescription": {"grade_ref": "boulder_max_os", "grade_offset": -2},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    assert inst["suggested"]["suggested_grade"] == step_grade("7A+", -2)
    assert inst["suggested"]["grade_ref"] == "boulder_max_os"
    assert inst["suggested"]["grade_offset"] == -2


def test_grade_relative_lead_os():
    """lead_max_os="7a+" (lowercase French) → uppercase → step_grade("7A+", -5) = "5B"."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "arc_training",
        "prescription": {"grade_ref": "lead_max_os", "grade_offset": -5},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    assert inst["suggested"]["suggested_grade"] == step_grade("7A+", -5)


def test_grade_relative_no_grade_ref():
    """Campus exercise without grade_ref → no suggested_grade."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "campus_laddering_feet_on",
        "prescription": {},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    assert "suggested_grade" not in (inst.get("suggested") or {})


def test_grade_relative_missing_grade():
    """Assessment grades missing the referenced key → no suggestion, no crash."""
    us = _base_user_state()
    us["assessment"]["grades"] = {}  # empty
    day = _day_with_exercises([{
        "exercise_id": "silent_feet_drill",
        "prescription": {"grade_ref": "boulder_max_os", "grade_offset": -2},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    assert "suggested_grade" not in (inst.get("suggested") or {})


def test_grade_relative_skips_limit_bouldering():
    """limit_bouldering keeps its special boulder_target, not generic suggested_grade."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "limit_bouldering",
        "prescription": {"grade_ref": "boulder_max_rp", "grade_offset": 0},
    }])
    day["sessions"][0]["location"] = "gym"
    day["sessions"][0]["gym_id"] = "blocx"
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    assert "suggested_boulder_target" in (inst.get("suggested") or {})
    assert "suggested_grade" not in (inst.get("suggested") or {})


# ─── External load (3 tests) ─────────────────────────────────────────────────

def test_external_load_fallback():
    """No history → BW% fallback estimate."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "barbell_row",
        "prescription": {"reps": 8, "sets": 3},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    sug = inst["suggested"]
    # 77.0 * 0.30 = 23.1 → round to 23.0
    assert sug["suggested_external_load_kg"] == 23.0
    assert sug["suggested_rep_scheme"] == "3x8"


def test_external_load_from_history():
    """Working loads entry → uses stored value."""
    us = _base_user_state()
    us["working_loads"]["entries"].append({
        "exercise_id": "barbell_row",
        "key": "barbell_row",
        "setup": {},
        "next_external_load_kg": 30.0,
        "updated_at": "2026-01-04",
    })
    day = _day_with_exercises([{
        "exercise_id": "barbell_row",
        "prescription": {"reps": 8, "sets": 3},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    assert inst["suggested"]["suggested_external_load_kg"] == 30.0


def test_external_load_feedback():
    """apply_feedback updates working_loads for external_load exercise."""
    us = _base_user_state()
    log = {
        "date": "2026-01-05",
        "planned": [{"exercise_instances": [{"exercise_id": "barbell_row", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{
            "exercise_id": "barbell_row",
            "completed": True,
            "feedback_label": "easy",
            "used_external_load_kg": 25.0,
        }]},
    }
    updated = apply_feedback(log, us)
    entry = next(e for e in updated["working_loads"]["entries"] if e["exercise_id"] == "barbell_row")
    # easy midpoint = (0.05+0.10)/2 = 0.075 → 25 * 1.075 = 26.875 → round 27.0
    assert entry["next_external_load_kg"] == 27.0
    assert entry["last_feedback_label"] == "easy"


# ─── Hangboard (4 tests) ─────────────────────────────────────────────────────

def test_hangboard_repeater_from_baseline():
    """Baseline=102, default intensity for repeater_hang_7_3=0.70 → suggested."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "repeater_hang_7_3",
        "prescription": {"sets": 6, "work_seconds": 7},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    sug = inst["suggested"]
    # 102 * 0.70 = 71.4 → round 71.5
    assert sug["suggested_total_load_kg"] == 71.5
    # 71.5 - 77 = -5.5
    assert sug["suggested_external_load_kg"] == -5.5


def test_hangboard_working_loads_override():
    """History overrides baseline."""
    us = _base_user_state()
    us["working_loads"]["entries"].append({
        "exercise_id": "repeater_hang_7_3",
        "key": "repeater_hang_7_3",
        "setup": {},
        "next_external_load_kg": 5.0,
        "updated_at": "2026-01-04",
    })
    day = _day_with_exercises([{
        "exercise_id": "repeater_hang_7_3",
        "prescription": {"sets": 6, "work_seconds": 7},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    assert inst["suggested"]["suggested_external_load_kg"] == 5.0
    assert inst["suggested"]["suggested_total_load_kg"] == 82.0  # 77 + 5


def test_hangboard_no_baseline():
    """No baseline → estimate_missing_baselines fills from lead_max_rp grade.
    Fixture has lead_max_rp="8a+" → GRADE_TO_HANG_OFFSET["8a+"]=40 → estimated=77+40=117.
    Then _hangboard_suggested: 117 × 0.70 = 81.9 → 82.0; ext = 82.0 - 77 = 5.0
    """
    us = _base_user_state()
    us["baselines"] = {}
    day = _day_with_exercises([{
        "exercise_id": "repeater_hang_7_3",
        "prescription": {"sets": 6, "work_seconds": 7},
    }])
    out = inject_targets(day, us)
    inst = out["sessions"][0]["exercise_instances"][0]
    sug = inst["suggested"]
    # 77 + 40 = 117; 117 * 0.70 = 81.9 → 82.0
    assert sug["suggested_total_load_kg"] == 82.0
    # 82.0 - 77 = 5.0
    assert sug["suggested_external_load_kg"] == 5.0


def test_hangboard_feedback():
    """apply_feedback creates working_loads entry for hangboard exercise."""
    us = _base_user_state()
    log = {
        "date": "2026-01-05",
        "planned": [{"exercise_instances": [{"exercise_id": "repeater_hang_7_3", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{
            "exercise_id": "repeater_hang_7_3",
            "completed": True,
            "feedback_label": "ok",
            "used_total_load_kg": 80.0,
        }]},
    }
    updated = apply_feedback(log, us)
    entry = next(e for e in updated["working_loads"]["entries"] if e["exercise_id"] == "repeater_hang_7_3")
    # ok midpoint = 0.025; total = 80 × 1.025 = 82.0; ext = 82.0 - 77 = 5.0
    assert entry["next_external_load_kg"] == 5.0
    assert entry["last_total_load_kg"] == 80.0


# ─── Default adjustment policy (2 tests) ─────────────────────────────────────

def test_default_policy_when_rules_empty():
    """_rule_midpoint_pct returns non-zero even without user policy (uses DEFAULT_ADJUSTMENT_POLICY)."""
    us_no_policy = {"working_loads": {"entries": [], "rules": {}}}
    pct = _rule_midpoint_pct(us_no_policy, "easy")
    assert abs(pct - 0.075) < 1e-9  # (0.05 + 0.10) / 2


def test_custom_policy_overrides():
    """User policy takes precedence over default."""
    us = {
        "working_loads": {
            "entries": [],
            "rules": {"adjustment_policy": {"easy": {"pct_range": [0.02, 0.04]}}},
        }
    }
    pct = _rule_midpoint_pct(us, "easy")
    assert abs(pct - 0.03) < 1e-9


# ─── Wiring (2 tests) ────────────────────────────────────────────────────────

def test_resolve_includes_load_model():
    """Exercise instances from resolve_session include load_model field."""
    us = _base_user_state()
    us["context"] = {"location": "home"}
    out = resolve_session(
        repo_root=REPO_ROOT,
        session_path="backend/catalog/sessions/v1/strength_long.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path="out/tmp/test_load_model.json",
        user_state_override=us,
        write_output=False,
    )
    instances = out["resolved_session"]["exercise_instances"]
    assert len(instances) > 0
    has_load_model = any(inst.get("load_model") is not None for inst in instances)
    assert has_load_model, "At least one instance should have a non-null load_model"


def test_resolve_includes_suggested():
    """At least one instance from resolve_session has suggested field (from inject_targets)."""
    us = _base_user_state()
    us["context"] = {"location": "home"}
    out = resolve_session(
        repo_root=REPO_ROOT,
        session_path="backend/catalog/sessions/v1/strength_long.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path="out/tmp/test_suggested.json",
        user_state_override=us,
        write_output=False,
    )
    instances = out["resolved_session"]["exercise_instances"]
    has_suggested = any("suggested" in inst for inst in instances)
    assert has_suggested, "At least one instance should have suggested targets"


# ─── Misc (2 tests) ──────────────────────────────────────────────────────────

def test_pullup_not_in_load_based():
    """pullup was removed from LOAD_BASED_EXERCISES (only weighted_pullup remains)."""
    assert "pullup" not in LOAD_BASED_EXERCISES
    assert "weighted_pullup" in LOAD_BASED_EXERCISES


def test_get_bodyweight_fallback():
    """_get_bodyweight reads from bodyweight_kg or body.weight_kg."""
    assert _get_bodyweight({"bodyweight_kg": 70.0}) == 70.0
    assert _get_bodyweight({"body": {"weight_kg": 65.0}}) == 65.0
    assert _get_bodyweight({}) == 0.0


# ─── NEW-F11: estimate_missing_baselines + load_warning (5 tests) ─────────────

def test_estimate_from_grade_7b():
    """BW=77, lead_max_rp='7b' → estimated max_total = 77+15 = 92 kg (NEW-F11)."""
    us = _base_user_state()
    us["baselines"] = {}
    us["assessment"]["grades"]["lead_max_rp"] = "7b"
    estimate_missing_baselines(us)
    baseline = us["baselines"]["hangboard"][0]
    assert baseline["max_total_load_kg"] == 92.0
    assert baseline["source"] == "estimated_from_grade"
    assert baseline["grade_used"] == "7b"


def test_no_overwrite_test_baseline():
    """Baseline with source='test' must never be overwritten by estimation."""
    us = _base_user_state()
    us["baselines"] = {"hangboard": [{"max_total_load_kg": 100.0, "source": "test"}]}
    us["assessment"]["grades"]["lead_max_rp"] = "7b"
    estimate_missing_baselines(us)
    # Must remain exactly as-is
    assert us["baselines"]["hangboard"][0]["max_total_load_kg"] == 100.0
    assert us["baselines"]["hangboard"][0]["source"] == "test"


def test_no_estimate_without_grade_or_pullup():
    """No grade, no pullup → no estimation, no crash."""
    us = {
        "bodyweight_kg": 77.0,
        "baselines": {},
        "assessment": {"grades": {}, "tests": {}},
    }
    estimate_missing_baselines(us)  # Must not raise
    # No hangboard baseline created
    assert not us["baselines"].get("hangboard")


def test_load_warning_on_negative_external():
    """When estimated external < 0, load_warning is injected into suggested (Step 1)."""
    us = _base_user_state()
    us["baselines"] = {}
    us["assessment"]["grades"]["lead_max_rp"] = "6b"  # offset=-10 → estimated=67kg
    day = _day_with_exercises([{
        "exercise_id": "density_hangs",
        "prescription": {"sets": 3, "work_seconds": 30},
    }])
    out = inject_targets(day, us)
    sug = out["sessions"][0]["exercise_instances"][0]["suggested"]
    # external = round(67 * 0.75, 0.5) - 77 → should be negative
    assert sug["suggested_external_load_kg"] < 0
    assert "load_warning" in sug
    assert "counterweight_required" in sug["load_warning"]


def test_load_source_estimated_in_output():
    """When baseline is estimated, load_source='estimated' appears in suggested."""
    us = _base_user_state()
    us["baselines"] = {}
    us["assessment"]["grades"]["lead_max_rp"] = "7b"
    day = _day_with_exercises([{
        "exercise_id": "repeater_hang_7_3",
        "prescription": {"sets": 6, "work_seconds": 7},
    }])
    out = inject_targets(day, us)
    sug = out["sessions"][0]["exercise_instances"][0]["suggested"]
    assert sug.get("load_source") == "estimated"


# ─── Leg exercises catalog (10 tests) ────────────────────────────────────────

def test_romanian_deadlift_in_external_load_set():
    """romanian_deadlift must be in EXTERNAL_LOAD_EXERCISES."""
    assert "romanian_deadlift" in EXTERNAL_LOAD_EXERCISES


def test_pistol_squat_not_in_external_load_set():
    """pistol_squat_progression is bodyweight_only — must NOT be in EXTERNAL_LOAD_EXERCISES."""
    assert "pistol_squat_progression" not in EXTERNAL_LOAD_EXERCISES


def test_romanian_deadlift_fallback_load():
    """No history → 0.40×BW fallback → 77 * 0.40 = 30.8 → rounds to 31.0."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "romanian_deadlift",
        "prescription": {"reps": 6, "sets": 3},
    }])
    out = inject_targets(day, us)
    sug = out["sessions"][0]["exercise_instances"][0]["suggested"]
    assert sug["suggested_external_load_kg"] == 31.0
    assert sug["suggested_rep_scheme"] == "3x6"


def test_romanian_deadlift_from_history():
    """Working loads entry → uses stored value for romanian_deadlift."""
    us = _base_user_state()
    us["working_loads"]["entries"].append({
        "exercise_id": "romanian_deadlift",
        "key": "romanian_deadlift",
        "setup": {},
        "next_external_load_kg": 50.0,
        "updated_at": "2026-01-04",
    })
    day = _day_with_exercises([{
        "exercise_id": "romanian_deadlift",
        "prescription": {"reps": 6, "sets": 3},
    }])
    out = inject_targets(day, us)
    sug = out["sessions"][0]["exercise_instances"][0]["suggested"]
    assert sug["suggested_external_load_kg"] == 50.0


def test_romanian_deadlift_feedback_updates_working_loads():
    """apply_feedback updates working_loads for romanian_deadlift."""
    us = _base_user_state()
    log = {
        "date": "2026-01-06",
        "planned": [{"exercise_instances": [{"exercise_id": "romanian_deadlift", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{
            "exercise_id": "romanian_deadlift",
            "completed": True,
            "feedback_label": "easy",
            "used_external_load_kg": 40.0,
        }]},
    }
    updated = apply_feedback(log, us)
    entries = updated["working_loads"]["entries"]
    entry = next(e for e in entries if e["exercise_id"] == "romanian_deadlift")
    # easy midpoint = (0.05+0.10)/2 = 0.075 → 40 * 1.075 = 43.0
    assert entry["next_external_load_kg"] == 43.0
    assert entry["last_feedback_label"] == "easy"


def test_pistol_squat_no_external_load_suggestion():
    """pistol_squat_progression is bodyweight_only → no suggested_external_load_kg."""
    us = _base_user_state()
    day = _day_with_exercises([{
        "exercise_id": "pistol_squat_progression",
        "prescription": {"reps": "4-6", "sets": 3},
    }])
    out = inject_targets(day, us)
    sug = out["sessions"][0]["exercise_instances"][0].get("suggested") or {}
    assert "suggested_external_load_kg" not in sug


def _resolve_session(session_id: str, user_state: dict) -> dict:
    """Helper: resolve a catalog session with user_state_override."""
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=f"backend/catalog/sessions/v1/{session_id}.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path=f"output/__test_{session_id}.json",
        user_state_override=user_state,
        write_output=False,
    )


def test_lower_body_gym_resolves():
    """lower_body_gym session resolves to at least one exercise."""
    us = _base_user_state()
    us["context"] = {"location": "gym", "gym_id": "test_gym"}
    us["equipment"] = {"home": [], "gyms": [{"gym_id": "test_gym", "equipment": ["weight"]}]}
    result = _resolve_session("lower_body_gym", us)
    instances = result.get("resolved_session", {}).get("exercise_instances", [])
    assert len(instances) > 0


def test_lower_body_gym_contains_squat():
    """lower_body_gym must include a squat-pattern exercise."""
    us = _base_user_state()
    us["context"] = {"location": "gym", "gym_id": "test_gym"}
    us["equipment"] = {"home": [], "gyms": [{"gym_id": "test_gym", "equipment": ["weight"]}]}
    result = _resolve_session("lower_body_gym", us)
    instances = result.get("resolved_session", {}).get("exercise_instances", [])
    ex_ids = [inst["exercise_id"] for inst in instances]
    squat_exercises = {"split_squat", "pistol_squat_progression"}
    assert squat_exercises & set(ex_ids), f"Expected a squat exercise in {ex_ids}"


def test_heavy_conditioning_gym_resolves():
    """heavy_conditioning_gym session resolves to at least one exercise."""
    us = _base_user_state()
    us["context"] = {"location": "gym", "gym_id": "test_gym"}
    us["equipment"] = {"home": [], "gyms": [{"gym_id": "test_gym", "equipment": ["weight", "pullup_bar"]}]}
    result = _resolve_session("heavy_conditioning_gym", us)
    instances = result.get("resolved_session", {}).get("exercise_instances", [])
    assert len(instances) > 0


def test_lower_body_gym_in_meta_but_not_auto_scheduled():
    """lower_body_gym is in _SESSION_META (for quick-add/resolve) but not in any phase pool."""
    from backend.engine.planner_v2 import _SESSION_META
    from backend.engine.macrocycle_v1 import _SESSION_POOL
    assert "lower_body_gym" in _SESSION_META
    for phase, pool in _SESSION_POOL.items():
        assert "lower_body_gym" not in pool, f"lower_body_gym should not be in {phase} pool"


def test_heavy_conditioning_gym_in_meta_but_not_auto_scheduled():
    """heavy_conditioning_gym is in _SESSION_META (for quick-add/resolve) but not in any phase pool."""
    from backend.engine.planner_v2 import _SESSION_META
    from backend.engine.macrocycle_v1 import _SESSION_POOL
    assert "heavy_conditioning_gym" in _SESSION_META
    for phase, pool in _SESSION_POOL.items():
        assert "heavy_conditioning_gym" not in pool, f"heavy_conditioning_gym should not be in {phase} pool"
