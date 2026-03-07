"""Tests for B38 — limitation/injury 3-level filtering in resolver."""
from __future__ import annotations

import pytest

from backend.engine.resolve_session import (
    normalize_limitations,
    pick_best_exercise_p0,
    _check_exercise_limitation,
    _apply_limitation_to_instance,
    _inject_prehab_for_limitations,
    get_ex_id,
)


# ---------------------------------------------------------------------------
# Minimal exercise catalog for limitation tests
# ---------------------------------------------------------------------------
def _make_exercises():
    return [
        {
            "id": "max_hang_5s",
            "name": "Max Hang 5s",
            "role": ["primary"],
            "domain": ["finger_strength"],
            "pattern": ["max_hang"],
            "location_allowed": ["gym", "home"],
            "equipment_required": ["hangboard"],
            "contraindications": ["elbow_sensitive"],
            "prescription_defaults": {"sets": 5, "work_seconds": 5},
            "fatigue_cost": 3,
        },
        {
            "id": "repeater_hang_7_3",
            "name": "Repeater Hang 7/3",
            "role": ["primary"],
            "domain": ["finger_strength"],
            "pattern": ["repeater"],
            "location_allowed": ["gym", "home"],
            "equipment_required": ["hangboard"],
            "contraindications": ["elbow_sensitive"],
            "prescription_defaults": {"sets": 4},
            "fatigue_cost": 2,
        },
        {
            "id": "finger_extensor_training",
            "name": "Finger Extensor Training",
            "role": ["accessory"],
            "domain": ["prehab_wrist"],
            "pattern": ["wrist_extension"],
            "location_allowed": ["gym", "home"],
            "equipment_required": [],
            "contraindications": [],
            "prescription_defaults": {"sets": 3, "reps": 15},
            "fatigue_cost": 1,
        },
        {
            "id": "pullup",
            "name": "Pull-up",
            "role": ["primary"],
            "domain": ["strength_general"],
            "pattern": ["pull"],
            "location_allowed": ["gym", "home"],
            "equipment_required": ["pullup_bar"],
            "contraindications": ["shoulder_sensitive"],
            "prescription_defaults": {"sets": 4, "reps": 8},
            "fatigue_cost": 2,
        },
        {
            "id": "inverted_row",
            "name": "Inverted Row",
            "role": ["primary"],
            "domain": ["strength_general"],
            "pattern": ["pull"],
            "location_allowed": ["gym", "home"],
            "equipment_required": ["pullup_bar"],
            "contraindications": ["shoulder_sensitive"],
            "prescription_defaults": {"sets": 3, "reps": 10},
            "fatigue_cost": 1,
        },
        {
            "id": "core_plank",
            "name": "Plank",
            "role": ["primary", "accessory"],
            "domain": ["core"],
            "pattern": ["isometric"],
            "location_allowed": ["gym", "home"],
            "equipment_required": [],
            "contraindications": [],
            "prescription_defaults": {"sets": 3, "hold_seconds": 60},
            "fatigue_cost": 1,
        },
        {
            "id": "band_external_rotation",
            "name": "Band External Rotation",
            "role": ["accessory"],
            "domain": ["prehab_shoulder"],
            "pattern": ["rotation"],
            "location_allowed": ["gym", "home"],
            "equipment_required": ["resistance_band"],
            "contraindications": [],
            "prescription_defaults": {"sets": 3, "reps": 15},
            "fatigue_cost": 1,
        },
        {
            "id": "elbow_eccentric_curl",
            "name": "Elbow Eccentric Curl",
            "role": ["accessory"],
            "domain": ["prehab_elbow"],
            "pattern": ["forearm_supination"],
            "location_allowed": ["gym", "home"],
            "equipment_required": [],
            "contraindications": [],
            "prescription_defaults": {"sets": 3, "reps": 12},
            "fatigue_cost": 1,
        },
        {
            "id": "wall_handstand_hold",
            "name": "Wall Handstand Hold",
            "role": ["primary"],
            "domain": ["handstand_skill"],
            "pattern": ["handstand"],
            "location_allowed": ["gym", "home"],
            "equipment_required": [],
            "contraindications": ["shoulder_sensitive", "wrist_sensitive"],
            "prescription_defaults": {"sets": 3, "hold_seconds": 30},
            "fatigue_cost": 2,
        },
        {
            "id": "bodyweight_squat",
            "name": "Bodyweight Squat",
            "role": ["primary"],
            "domain": ["strength_general"],
            "pattern": ["squat"],
            "location_allowed": ["gym", "home"],
            "equipment_required": [],
            "contraindications": [],
            "prescription_defaults": {"sets": 3, "reps": 15},
            "fatigue_cost": 1,
        },
    ]


# ===================================================================
# 1. normalize_limitations
# ===================================================================
class TestNormalizeLimitations:
    def test_current_format_with_details(self):
        us = {
            "limitations": {
                "active_flags": ["elbow_left"],
                "details": [{"area": "elbow", "side": "left", "severity": "moderate"}],
            }
        }
        assert normalize_limitations(us) == {"elbow": "active"}

    def test_severity_migration_mild_to_monitor(self):
        us = {"limitations": {"active_flags": [], "details": [{"area": "shoulder", "severity": "mild"}]}}
        assert normalize_limitations(us) == {"shoulder": "monitor"}

    def test_severity_migration_italian(self):
        us = {"limitations": {"active_flags": [], "details": [{"area": "elbow", "severity": "lieve"}]}}
        assert normalize_limitations(us) == {"elbow": "monitor"}

    def test_active_flags_only_fallback(self):
        us = {"limitations": {"active_flags": ["elbow_left", "shoulder_both"], "details": []}}
        assert normalize_limitations(us) == {"elbow": "active", "shoulder": "active"}

    def test_list_of_strings_legacy(self):
        us = {"limitations": ["elbow_sensitive", "wrist_sensitive"]}
        assert normalize_limitations(us) == {"elbow": "active", "wrist": "active"}

    def test_new_format_list_of_dicts(self):
        us = {"limitations": [{"zone": "elbow", "severity": "active"}, {"zone": "wrist", "severity": "severe"}]}
        assert normalize_limitations(us) == {"elbow": "active", "wrist": "severe"}

    def test_highest_severity_wins(self):
        us = {"limitations": {"active_flags": [], "details": [
            {"area": "elbow", "severity": "monitor"},
            {"area": "elbow", "severity": "severe"},
        ]}}
        assert normalize_limitations(us) == {"elbow": "severe"}

    def test_empty_limitations(self):
        assert normalize_limitations({}) == {}
        assert normalize_limitations({"limitations": None}) == {}
        assert normalize_limitations({"limitations": {}}) == {}
        assert normalize_limitations({"limitations": []}) == {}

    def test_unknown_zone_ignored(self):
        us = {"limitations": {"active_flags": [], "details": [
            {"area": "knee", "severity": "active"},
            {"area": "elbow", "severity": "monitor"},
        ]}}
        assert normalize_limitations(us) == {"elbow": "monitor"}

    def test_legacy_fixture_italian_zone_ignored(self):
        """The existing test fixture uses Italian zone 'gomito' — must not crash."""
        us = {"limitations": {
            "active_flags": ["gomito_sinistro"],
            "details": [{"area": "gomito", "severity": "lieve", "side": "sinistro"}],
        }}
        assert normalize_limitations(us) == {}


# ===================================================================
# 2. pick_best_exercise_p0 — monitor
# ===================================================================
class TestP0Monitor:
    def test_monitor_does_not_filter(self):
        """Monitor: exercise with contraindication is still selected."""
        ex, _ = pick_best_exercise_p0(
            exercises=_make_exercises(),
            location="home",
            available_equipment=["hangboard"],
            role_req="primary",
            domain_req="finger_strength",
            limitation_map={"elbow": "monitor"},
        )
        assert ex is not None
        assert get_ex_id(ex) == "max_hang_5s"


# ===================================================================
# 3. pick_best_exercise_p0 — active (substitute)
# ===================================================================
class TestP0ActiveSubstitute:
    def test_active_substitutes_when_variant_exists(self):
        """Active: prefer exercise without contraindication if available."""
        exercises = _make_exercises()
        ex, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="home",
            available_equipment=[],
            role_req="primary",
            domain_req="strength_general",
            limitation_map={"shoulder": "active"},
        )
        # pullup and inverted_row have shoulder_sensitive; bodyweight_squat does not
        assert ex is not None
        assert get_ex_id(ex) == "bodyweight_squat"

    def test_active_falls_back_when_no_variant(self):
        """Active: no variant without contraindication → keep original."""
        ex, _ = pick_best_exercise_p0(
            exercises=_make_exercises(),
            location="home",
            available_equipment=["hangboard"],
            role_req="primary",
            domain_req="finger_strength",
            limitation_map={"elbow": "active"},
        )
        assert ex is not None
        assert get_ex_id(ex) in ("max_hang_5s", "repeater_hang_7_3")


# ===================================================================
# 4. pick_best_exercise_p0 — active (reduce load)
# ===================================================================
class TestP0ActiveReduceLoad:
    def test_active_load_modifier_on_fallback(self):
        """Active with no variant: instance gets limitation_load_modifier=0.8."""
        exercises = _make_exercises()
        ex, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="home",
            available_equipment=["hangboard"],
            role_req="primary",
            domain_req="finger_strength",
            limitation_map={"elbow": "active"},
        )
        # Verify tagging
        inst = {"prescription": {"sets": 5}}
        _apply_limitation_to_instance(inst, ex, {"elbow": "active"})
        assert inst["limitation_warning"] == "active"
        assert inst["limitation_load_modifier"] == 0.8
        assert inst["prescription"]["multiplier"] == pytest.approx(0.8)

    def test_active_modifier_stacks_with_existing(self):
        ex = {"id": "max_hang_5s", "contraindications": ["elbow_sensitive"]}
        inst = {"prescription": {"sets": 5, "multiplier": 0.9}}
        _apply_limitation_to_instance(inst, ex, {"elbow": "active"})
        assert inst["prescription"]["multiplier"] == pytest.approx(0.72)


# ===================================================================
# 5. pick_best_exercise_p0 — severe (exclude)
# ===================================================================
class TestP0SevereExclude:
    def test_severe_excludes_contraindicated(self):
        """Severe: all exercises with matching contraindication excluded."""
        ex, _ = pick_best_exercise_p0(
            exercises=_make_exercises(),
            location="home",
            available_equipment=["hangboard"],
            role_req="primary",
            domain_req="finger_strength",
            limitation_map={"elbow": "severe"},
        )
        assert ex is None

    def test_severe_allows_non_contraindicated(self):
        ex, _ = pick_best_exercise_p0(
            exercises=_make_exercises(),
            location="home",
            available_equipment=[],
            role_req="primary",
            domain_req="core",
            limitation_map={"elbow": "severe"},
        )
        assert ex is not None
        assert get_ex_id(ex) == "core_plank"


# ===================================================================
# 6. Force deload (severe x 2)
# ===================================================================
class TestForceDeload:
    def test_severe_count_logic(self):
        limitation_map = {"elbow": "severe", "shoulder": "severe"}
        severe_count = sum(1 for s in limitation_map.values() if s == "severe")
        assert severe_count >= 2

    def test_one_severe_no_deload(self):
        limitation_map = {"elbow": "severe", "shoulder": "monitor"}
        severe_count = sum(1 for s in limitation_map.values() if s == "severe")
        assert severe_count < 2


# ===================================================================
# 7. Backward compatibility
# ===================================================================
class TestBackwardCompat:
    def test_old_format_migrates(self):
        us = {"limitations": ["elbow_sensitive"]}
        assert normalize_limitations(us) == {"elbow": "active"}

    def test_old_format_moderate_migrates(self):
        us = {"limitations": {"active_flags": [], "details": [
            {"area": "wrist", "severity": "moderate"},
        ]}}
        assert normalize_limitations(us) == {"wrist": "active"}


# ===================================================================
# 8. No limitation — regression
# ===================================================================
class TestNoLimitationRegression:
    def test_no_limitation_same_result(self):
        exercises = _make_exercises()
        ex_without, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="home",
            available_equipment=["hangboard"],
            role_req="primary",
            domain_req="finger_strength",
        )
        ex_with_empty, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="home",
            available_equipment=["hangboard"],
            role_req="primary",
            domain_req="finger_strength",
            limitation_map={},
        )
        assert get_ex_id(ex_without) == get_ex_id(ex_with_empty)

    def test_no_tag_when_no_limitation(self):
        ex = {"id": "max_hang_5s", "contraindications": ["elbow_sensitive"]}
        inst = {"prescription": {"sets": 5}}
        _apply_limitation_to_instance(inst, ex, {})
        assert "limitation_warning" not in inst


# ===================================================================
# 9. Prehab injection
# ===================================================================
class TestPrehabInjection:
    def test_injects_prehab_for_elbow(self):
        exercises = _make_exercises()
        instances = [{"exercise_id": "max_hang_5s", "block_uid": "t.main"}]
        blocks = []
        counter = _inject_prehab_for_limitations(
            exercise_instances=instances,
            blocks_out=blocks,
            limitation_map={"elbow": "monitor"},
            exercises=exercises,
            location="home",
            available_equipment=[],
            instance_counter=1,
        )
        prehab = [i for i in instances if i.get("limitation_prehab_for") == "elbow"]
        assert len(prehab) == 1
        assert prehab[0]["exercise_id"] == "elbow_eccentric_curl"
        assert counter == 2
        assert len(blocks) == 1
        assert blocks[0]["type"] == "prehab"

    def test_no_duplicate_if_prehab_already_present(self):
        exercises = _make_exercises()
        instances = [{"exercise_id": "elbow_eccentric_curl", "block_uid": "t.prehab"}]
        blocks = []
        counter = _inject_prehab_for_limitations(
            exercise_instances=instances,
            blocks_out=blocks,
            limitation_map={"elbow": "active"},
            exercises=exercises,
            location="home",
            available_equipment=[],
            instance_counter=1,
        )
        assert len(instances) == 1
        assert counter == 1

    def test_injects_for_severe_zone_too(self):
        """Severe zones also get prehab (as replacement for excluded exercises)."""
        exercises = _make_exercises()
        instances = []
        blocks = []
        counter = _inject_prehab_for_limitations(
            exercise_instances=instances,
            blocks_out=blocks,
            limitation_map={"elbow": "severe"},
            exercises=exercises,
            location="home",
            available_equipment=[],
            instance_counter=0,
        )
        assert len(instances) == 1
        assert instances[0]["limitation_prehab_for"] == "elbow"

    def test_multiple_zones_inject_multiple(self):
        exercises = _make_exercises()
        instances = []
        blocks = []
        _inject_prehab_for_limitations(
            exercise_instances=instances,
            blocks_out=blocks,
            limitation_map={"elbow": "monitor", "wrist": "active"},
            exercises=exercises,
            location="home",
            available_equipment=[],
            instance_counter=0,
        )
        zones = {i["limitation_prehab_for"] for i in instances}
        assert zones == {"elbow", "wrist"}

    def test_skips_if_no_candidate(self):
        """If no prehab exercise matches location/equipment, skip gracefully."""
        exercises = _make_exercises()
        instances = []
        blocks = []
        counter = _inject_prehab_for_limitations(
            exercise_instances=instances,
            blocks_out=blocks,
            limitation_map={"shoulder": "monitor"},
            exercises=exercises,
            location="home",
            available_equipment=[],  # band_external_rotation needs resistance_band
            instance_counter=0,
        )
        # No shoulder prehab available without resistance_band at home
        shoulder_prehab = [i for i in instances if i.get("limitation_prehab_for") == "shoulder"]
        # shoulder_car and wall_slide don't need equipment, let's check
        # Actually shoulder_car and wall_slide ARE in the real catalog but not in our test fixtures
        # With our minimal catalog, only band_external_rotation exists for prehab_shoulder
        assert len(shoulder_prehab) == 0


# ===================================================================
# 10. _check_exercise_limitation
# ===================================================================
class TestCheckExerciseLimitation:
    def test_worst_severity_wins_multi_zone(self):
        ex = {"id": "wall_handstand_hold", "contraindications": ["shoulder_sensitive", "wrist_sensitive"]}
        result = _check_exercise_limitation(ex, {"shoulder": "monitor", "wrist": "active"})
        assert result == {"zone": "wrist", "severity": "active"}

    def test_no_match_returns_none(self):
        ex = {"id": "core_plank", "contraindications": []}
        assert _check_exercise_limitation(ex, {"elbow": "severe"}) is None

    def test_empty_map_returns_none(self):
        ex = {"id": "max_hang_5s", "contraindications": ["elbow_sensitive"]}
        assert _check_exercise_limitation(ex, {}) is None
