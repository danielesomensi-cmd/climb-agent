#!/usr/bin/env python3
"""
Migrate exercises.json from v1.1 to v2.0 canonical format.

- Transforms prescription_defaults to 5 canonical fields + notes
- Adds description, cues, video_url, load_model to all exercises
- Adds attributes to hangboard exercises (incl. intensity_pct)
- Adds focus to technique exercises
- Appends 26 new exercises
- Writes version 2.0

Usage:
    python scripts/migrate_exercises_v2.py
"""

import json
import os
import sys
from copy import deepcopy
from typing import Any, Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXERCISES_PATH = os.path.join(REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json")

# ── load_model assignments ──────────────────────────────────────────────

TOTAL_LOAD = {
    "max_hang_5s", "max_hang_7s", "max_hang_10s_lev1", "max_hang_ladder",
    "weighted_pullup", "one_arm_hang_assisted", "pinch_block_training",
    "long_duration_hang", "repeater_hang_7_3", "density_hang_10_10",
    "min_edge_hang", "dead_hang_easy",
}

EXTERNAL_LOAD = {
    "overhead_press", "split_squat", "dumbbell_row", "farmers_carry",
    "turkish_getup", "bench_press", "face_pull",
}

GRADE_RELATIVE = {
    "limit_bouldering", "board_limit_boulders", "four_by_four_bouldering",
    "arc_training", "threshold_climbing", "continuity_climbing",
    "gym_arc_easy_volume", "easy_climbing_deload", "silent_feet_drill",
    "no_readjust_drill", "downclimbing_drill", "slow_climbing",
    "flag_practice", "gym_technique_boulder_drills", "pangullich_ladders_easy",
    "campus_laddering_feet_off", "campus_laddering_feet_on", "campus_bumps",
    "campus_double_dyno", "route_intervals",
}

# ── hangboard attributes ────────────────────────────────────────────────

HANGBOARD_ATTRIBUTES = {
    "max_hang_5s": {"edge_mm": 20, "grip": "half_crimp"},
    "max_hang_7s": {"edge_mm": 20, "grip": "half_crimp"},
    "max_hang_ladder": {"edge_mm": 20, "grip": "half_crimp"},
    "repeater_hang_7_3": {"edge_mm": 20, "grip": "half_crimp"},
    "density_hang_10_10": {"edge_mm": 20, "grip": "half_crimp"},
    "min_edge_hang": {"edge_mm": 20, "grip": "half_crimp"},
    "dead_hang_easy": {"edge_mm": 20, "grip": "half_crimp"},
    "long_duration_hang": {"edge_mm": 20, "grip": "half_crimp"},
    "one_arm_hang_assisted": {"edge_mm": 20, "grip": "half_crimp"},
    "pinch_block_training": {"edge_mm": 20, "grip": "pinch"},
}

# ── technique focus ─────────────────────────────────────────────────────

TECHNIQUE_FOCUS = {
    "silent_feet_drill": "footwork",
    "no_readjust_drill": "footwork",
    "downclimbing_drill": "movement",
    "slow_climbing": "movement",
    "flag_practice": "body_position",
    "gym_technique_boulder_drills": None,
    "pangullich_ladders_easy": "body_position",
}

# ── special case overrides (from brief) ─────────────────────────────────

SPECIAL_CASES: Dict[str, Dict[str, Any]] = {
    "repeater_hang_7_3": {
        "sets": 3, "reps": 6, "work_seconds": 7,
        "rest_between_reps_seconds": 3, "rest_between_sets_seconds": 180,
    },
    "density_hang_10_10": {
        "sets": 3, "reps": 6, "work_seconds": 10,
        "rest_between_reps_seconds": 10, "rest_between_sets_seconds": 180,
    },
    "arc_training": {
        "sets": 2, "reps": None, "work_seconds": 1200,
        "rest_between_reps_seconds": None, "rest_between_sets_seconds": 300,
    },
    "threshold_climbing": {
        "sets": 6, "reps": None, "work_seconds": 120,
        "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
    },
    "continuity_climbing": {
        "sets": 6, "reps": None, "work_seconds": 120,
        "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
    },
    "gym_arc_easy_volume": {
        "sets": 2, "reps": None, "work_seconds": 1200,
        "rest_between_reps_seconds": None, "rest_between_sets_seconds": 300,
    },
    "arc_easy_traverse": {
        "sets": 2, "reps": None, "work_seconds": 900,
        "rest_between_reps_seconds": None, "rest_between_sets_seconds": 300,
    },
    "density_hangs": {
        "sets": 3, "reps": 6, "work_seconds": 10,
        "rest_between_reps_seconds": 10, "rest_between_sets_seconds": 180,
    },
}


def _low(val: Any) -> Optional[int]:
    """Extract low value from a range [low, high] or return int directly."""
    if isinstance(val, list) and len(val) >= 1:
        return int(val[0])
    if isinstance(val, (int, float)):
        return int(val)
    return None


def _minutes_to_seconds(val: Any) -> Optional[int]:
    """Convert minutes range to seconds (low value)."""
    low = _low(val)
    return low * 60 if low is not None else None


def _collect_notes(pd: Dict[str, Any], exercise: Dict[str, Any]) -> Optional[str]:
    """Collect notes from various sources into a single string."""
    parts: List[str] = []

    # Existing notes (can be string or list)
    notes = pd.get("notes") or exercise.get("notes")
    if isinstance(notes, list):
        parts.extend(str(n) for n in notes)
    elif isinstance(notes, str):
        parts.append(notes)

    # intensity_notes → merge into notes
    inotes = pd.get("intensity_notes")
    if isinstance(inotes, list):
        parts.extend(str(n) for n in inotes)
    elif isinstance(inotes, str):
        parts.append(inotes)

    # protocol → add to notes if informative
    proto = pd.get("protocol")
    if isinstance(proto, str) and proto:
        parts.append(f"Protocol: {proto}.")

    # tempo → add to notes
    tempo = pd.get("tempo")
    if isinstance(tempo, str) and tempo:
        parts.append(f"Tempo: {tempo}.")

    # steps → summarize
    steps = pd.get("steps")
    if isinstance(steps, list) and steps:
        step_strs = []
        for i, s in enumerate(steps, 1):
            dur = s.get("hang_seconds", "?")
            pct = s.get("intensity_pct_of_total_load", "?")
            step_strs.append(f"step {i}: {dur}s @ {pct}")
        parts.append("Ladder: " + ", ".join(step_strs) + ".")

    if not parts:
        return None
    return " ".join(parts)


def migrate_prescription(exercise: Dict[str, Any]) -> Dict[str, Any]:
    """Transform prescription_defaults to canonical 5 fields + notes."""
    eid = exercise["id"]
    pd = exercise.get("prescription_defaults", {})

    # Special cases: use exact values from brief
    if eid in SPECIAL_CASES:
        new_pd = dict(SPECIAL_CASES[eid])
        notes = _collect_notes(pd, exercise)
        if notes:
            new_pd["notes"] = notes
        return new_pd

    # Generic migration
    new_pd: Dict[str, Any] = {}

    # ── sets ──
    sets = pd.get("sets")
    if sets is None:
        sets = _low(pd.get("sets_range"))
    if sets is None:
        rounds = pd.get("rounds")
        if rounds is not None:
            sets = int(rounds)
    if sets is None:
        # Exercises with only duration_min_range and no sets → sets: 1
        if pd.get("duration_min_range") or pd.get("total_minutes_range"):
            sets = 1
    new_pd["sets"] = sets

    # ── reps ──
    reps = pd.get("reps")
    if reps is None:
        reps = _low(pd.get("reps_range")) or _low(pd.get("reps_per_set_range"))
    # Technique drills: sets = number of boulders, reps = 1
    if exercise.get("category") == "technique" and reps is None:
        reps = 1
    new_pd["reps"] = reps

    # ── work_seconds ──
    work = pd.get("hang_seconds")
    if work is None:
        work = pd.get("hold_seconds")
    if work is None:
        work = _low(pd.get("hold_seconds_range"))
    if work is None:
        work = pd.get("duration_seconds")
    if work is None:
        work = _low(pd.get("duration_seconds_range"))
    if work is None:
        tmr = pd.get("total_minutes_range")
        if tmr is not None:
            work = _minutes_to_seconds(tmr)
    if work is None:
        dmr = pd.get("duration_min_range")
        if dmr is not None:
            work = _minutes_to_seconds(dmr)
    new_pd["work_seconds"] = work

    # ── rest_between_reps_seconds ──
    # Only for exercises with explicit inter-rep rest
    rest_reps = None
    # repeater_hang_7_3 and density_hang_10_10 handled in SPECIAL_CASES
    new_pd["rest_between_reps_seconds"] = rest_reps

    # ── rest_between_sets_seconds ──
    rest_sets = pd.get("rest_seconds")
    if rest_sets is None:
        rest_sets = _low(pd.get("rest_seconds_range"))
    new_pd["rest_between_sets_seconds"] = rest_sets

    # ── notes ──
    notes = _collect_notes(pd, exercise)
    if notes:
        new_pd["notes"] = notes

    return new_pd


def assign_load_model(eid: str, exercise: Dict[str, Any]) -> Optional[str]:
    """Determine load_model string for an exercise."""
    # Existing load_model objects → collapse to string
    existing = exercise.get("load_model")
    if isinstance(existing, dict):
        return existing.get("type", "total_load")

    if eid in TOTAL_LOAD:
        return "total_load"
    if eid in EXTERNAL_LOAD:
        return "external_load"
    if eid in GRADE_RELATIVE:
        return "grade_relative"
    # Everything else → bodyweight_only
    return "bodyweight_only"


def migrate_exercise(exercise: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a single exercise to v2 format."""
    e = deepcopy(exercise)
    eid = e["id"]

    # ── Transform prescription_defaults ──
    old_pd = e.get("prescription_defaults", {})
    e["prescription_defaults"] = migrate_prescription(e)

    # ── Add root-level fields ──
    if "description" not in e:
        e["description"] = None
    if "cues" not in e:
        e["cues"] = []
    if "video_url" not in e:
        e["video_url"] = None

    # ── load_model → collapse to string ──
    e["load_model"] = assign_load_model(eid, e)

    # ── attributes (hangboard) ──
    if eid in HANGBOARD_ATTRIBUTES:
        attrs = dict(HANGBOARD_ATTRIBUTES[eid])
        # Move intensity_pct from old prescription_defaults to attributes
        intensity = old_pd.get("intensity_pct_of_total_load")
        if intensity is not None:
            attrs["intensity_pct"] = float(intensity)
        # Preserve existing attributes
        existing_attrs = e.get("attributes", {})
        if isinstance(existing_attrs, dict):
            # Keep existing, update with new
            merged_attrs = {**existing_attrs, **attrs}
            # If existing had intensity_pct_of_total_load, rename it
            if "intensity_pct_of_total_load" in merged_attrs:
                merged_attrs["intensity_pct"] = merged_attrs.pop("intensity_pct_of_total_load")
            e["attributes"] = merged_attrs
        else:
            e["attributes"] = attrs

    # ── focus (technique) ──
    if eid in TECHNIQUE_FOCUS:
        e["focus"] = TECHNIQUE_FOCUS[eid]

    # ── Clean up top-level notes if it was in prescription_defaults ──
    if "notes" in e and eid != "core_l_sit":
        # core_l_sit has notes at top level, keep it
        pass
    # Remove top-level notes if they were migrated into prescription_defaults.notes
    if "notes" in e and "notes" in e.get("prescription_defaults", {}):
        if e["notes"] == e["prescription_defaults"]["notes"]:
            del e["notes"]

    return e


# ── 26 New Exercises ────────────────────────────────────────────────────

def get_new_exercises() -> List[Dict[str, Any]]:
    """Return the 26 new exercises from the brief, with vocabulary corrections."""
    exercises = []

    # ── 2A. Hangboard (6) ──

    exercises.append({
        "id": "max_hang_10s",
        "name": "Max Hang 10s (Hypertrophy)",
        "category": "main_strength",
        "time_min": 20,
        "role": ["main"],
        "domain": ["finger_strength"],
        "pattern": "isometric_hang",
        "intensity_level": "high",
        "fatigue_cost": 7,
        "recency_group": "finger_max_hang",
        "equipment_required": ["hangboard"],
        "location_allowed": ["home", "gym"],
        "contraindications": ["finger_injury", "pulley_injury"],
        "prescription_defaults": {
            "sets": 5, "reps": None, "work_seconds": 10,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 180,
            "notes": "85-90% intensity. Longer duration for structural/hypertrophic adaptation."
        },
        "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.88},
        "load_model": "total_load",
        "stress_tags": {"elbow": "medium", "fingers": "high", "cns": "high", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "horst_7_53",
        "name": "Hörst 7-53 Protocol",
        "category": "main_strength",
        "time_min": 25,
        "role": ["main"],
        "domain": ["finger_strength"],
        "pattern": "isometric_hang",
        "intensity_level": "high",
        "fatigue_cost": 8,
        "recency_group": "finger_max_hang",
        "equipment_required": ["hangboard"],
        "location_allowed": ["home", "gym"],
        "contraindications": ["finger_injury", "pulley_injury"],
        "prescription_defaults": {
            "sets": 4, "reps": None, "work_seconds": 7,
            "rest_between_reps_seconds": 53, "rest_between_sets_seconds": 180,
            "notes": "90-95% intensity. Each set = 3 hangs (7s on / 53s off). 3 min between sets. Hörst signature protocol."
        },
        "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.93},
        "load_model": "total_load",
        "stress_tags": {"elbow": "high", "fingers": "high", "cns": "high", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "repeater_15_15",
        "name": "Repeater Hang 15/15 (Endurance)",
        "category": "endurance",
        "time_min": 20,
        "role": ["main"],
        "domain": ["finger_strength", "endurance"],
        "pattern": "repeater_hang",
        "intensity_level": "medium",
        "fatigue_cost": 5,
        "recency_group": "finger_repeaters",
        "equipment_required": ["hangboard"],
        "location_allowed": ["home", "gym"],
        "contraindications": ["finger_injury", "pulley_injury"],
        "prescription_defaults": {
            "sets": 4, "reps": 6, "work_seconds": 15,
            "rest_between_reps_seconds": 15, "rest_between_sets_seconds": 120,
            "notes": "40-50% max load. Eva López / Hörst endurance protocol. Focus on sustained grip."
        },
        "attributes": {"edge_mm": 20, "grip": "half_crimp"},
        "load_model": "total_load",
        "stress_tags": {"elbow": "medium", "fingers": "medium", "cns": "medium", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "lopez_subhangs",
        "name": "López Submaximal Hangs",
        "category": "prehab",
        "time_min": 15,
        "role": ["prehab"],
        "domain": ["finger_strength", "prehab_finger"],
        "pattern": "isometric_hang",
        "intensity_level": "low",
        "fatigue_cost": 3,
        "recency_group": "finger_submaximal_hang",
        "equipment_required": ["hangboard"],
        "location_allowed": ["home", "gym"],
        "contraindications": ["acute_finger_injury"],
        "prescription_defaults": {
            "sets": 5, "reps": None, "work_seconds": 30,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
            "notes": "30-40% max load. High volume, low intensity. Eva López protocol for tendon conditioning."
        },
        "attributes": {"edge_mm": 22, "grip": "half_crimp"},
        "load_model": "total_load",
        "stress_tags": {"elbow": "low", "fingers": "low", "cns": "low", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "critical_force_test",
        "name": "Critical Force Test",
        "category": "test",
        "time_min": 15,
        "role": ["test"],
        "domain": ["finger_strength", "endurance"],
        "pattern": "isometric_hang",
        "intensity_level": "high",
        "fatigue_cost": 8,
        "recency_group": "finger_test",
        "equipment_required": ["hangboard"],
        "location_allowed": ["home", "gym"],
        "contraindications": ["finger_injury", "pulley_injury"],
        "prescription_defaults": {
            "sets": 1, "reps": None, "work_seconds": None,
            "rest_between_reps_seconds": 3, "rest_between_sets_seconds": None,
            "notes": "7s on / 3s off to failure at fixed load. Determines aerobic threshold of forearm. Lattice / research protocol."
        },
        "attributes": {"edge_mm": 20, "grip": "half_crimp"},
        "load_model": "total_load",
        "stress_tags": {"elbow": "high", "fingers": "high", "cns": "high", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "med_test",
        "name": "Maximum Effort Duration Test (MED)",
        "category": "test",
        "time_min": 10,
        "role": ["test"],
        "domain": ["finger_strength", "endurance"],
        "pattern": "isometric_hang",
        "intensity_level": "high",
        "fatigue_cost": 6,
        "recency_group": "finger_test",
        "equipment_required": ["hangboard"],
        "location_allowed": ["home", "gym"],
        "contraindications": ["finger_injury", "pulley_injury"],
        "prescription_defaults": {
            "sets": 1, "reps": None, "work_seconds": None,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": None,
            "notes": "Hang at 45% bodyweight until failure. Record total seconds. Lattice endurance metric."
        },
        "attributes": {"edge_mm": 20, "grip": "half_crimp"},
        "load_model": "total_load",
        "stress_tags": {"elbow": "medium", "fingers": "high", "cns": "medium", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    # ── 2B. Campus (4) ──

    exercises.append({
        "id": "campus_touches",
        "name": "Campus Board Touches",
        "category": "main_strength",
        "time_min": 15,
        "role": ["main"],
        "domain": ["contact_strength", "power"],
        "pattern": "campus_ladder",
        "intensity_level": "high",
        "fatigue_cost": 7,
        "recency_group": "campus_ladders",
        "equipment_required": ["campus_board"],
        "location_allowed": ["gym"],
        "contraindications": ["finger_injury", "pulley_injury", "shoulder_injury"],
        "prescription_defaults": {
            "sets": 5, "reps": 4, "work_seconds": None,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 180,
            "notes": "Touch high rung and return. Focus on speed and precision. Contact strength development."
        },
        "load_model": "bodyweight_only",
        "stress_tags": {"elbow": "high", "fingers": "high", "cns": "high", "skin": "high"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "campus_max_ladders",
        "name": "Campus Max Ladders",
        "category": "main_strength",
        "time_min": 20,
        "role": ["main"],
        "domain": ["contact_strength", "power"],
        "pattern": "campus_ladder",
        "intensity_level": "high",
        "fatigue_cost": 9,
        "recency_group": "campus_ladders",
        "equipment_required": ["campus_board"],
        "location_allowed": ["gym"],
        "contraindications": ["finger_injury", "pulley_injury", "shoulder_injury", "elbow_injury"],
        "prescription_defaults": {
            "sets": 4, "reps": 1, "work_seconds": None,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 210,
            "notes": "Advanced. 1-4-7, 1-5-8 patterns. Full body tension. Stop when speed drops. Anderson RCTM / Hörst."
        },
        "load_model": "bodyweight_only",
        "stress_tags": {"elbow": "high", "fingers": "high", "cns": "high", "skin": "high"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "campus_switches",
        "name": "Campus Board Switches",
        "category": "main_strength",
        "time_min": 15,
        "role": ["main"],
        "domain": ["contact_strength"],
        "pattern": "campus_ladder",
        "intensity_level": "high",
        "fatigue_cost": 7,
        "recency_group": "campus_switches",
        "equipment_required": ["campus_board"],
        "location_allowed": ["gym"],
        "contraindications": ["finger_injury", "pulley_injury", "shoulder_injury"],
        "prescription_defaults": {
            "sets": 5, "reps": 8, "work_seconds": None,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 150,
            "notes": "Match on rung, rapid hand switches (hand-over-hand). Speed training. Same rung height throughout."
        },
        "load_model": "bodyweight_only",
        "stress_tags": {"elbow": "high", "fingers": "high", "cns": "high", "skin": "high"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "campus_sprint_endurance",
        "name": "Campus Sprint Endurance",
        "category": "power_endurance",
        "time_min": 15,
        "role": ["main"],
        "domain": ["contact_strength", "anaerobic_capacity"],
        "pattern": "campus_ladder",
        "intensity_level": "high",
        "fatigue_cost": 8,
        "recency_group": "campus_endurance",
        "equipment_required": ["campus_board"],
        "location_allowed": ["gym"],
        "contraindications": ["finger_injury", "pulley_injury", "shoulder_injury"],
        "prescription_defaults": {
            "sets": 3, "reps": None, "work_seconds": 15,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 120,
            "notes": "Up and down repeatedly for 15-20s. Alactic-aerobic campus capacity. Stop if form breaks."
        },
        "load_model": "bodyweight_only",
        "stress_tags": {"elbow": "high", "fingers": "high", "cns": "high", "skin": "high"},
        "description": None, "cues": [], "video_url": None,
    })

    # ── 2C. Climbing Protocols (6) ──

    exercises.append({
        "id": "emom_bouldering",
        "name": "EMOM Bouldering",
        "category": "power_endurance",
        "time_min": 15,
        "role": ["main"],
        "domain": ["power_endurance", "anaerobic_capacity"],
        "pattern": "climbing_intervals",
        "intensity_level": "high",
        "fatigue_cost": 7,
        "recency_group": "gym_emom",
        "equipment_required": [],
        "equipment_required_any": ["gym_boulder", "spraywall", "board_kilter", "board_moonboard"],
        "location_allowed": ["gym", "outdoor"],
        "contraindications": [],
        "prescription_defaults": {
            "sets": 12, "reps": 1, "work_seconds": None,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": None,
            "notes": "Every Minute On the Minute. Start at minute mark, rest remainder. Grade at flash or +1. 10-15 minutes total."
        },
        "load_model": "grade_relative",
        "stress_tags": {"elbow": "medium", "fingers": "high", "cns": "high", "skin": "high"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "otm_bouldering",
        "name": "OTM Bouldering (Every 2 Minutes)",
        "category": "power_endurance",
        "time_min": 20,
        "role": ["main"],
        "domain": ["power_endurance", "anaerobic_capacity"],
        "pattern": "climbing_intervals",
        "intensity_level": "high",
        "fatigue_cost": 7,
        "recency_group": "gym_otm",
        "equipment_required": [],
        "equipment_required_any": ["gym_boulder", "spraywall", "board_kilter", "board_moonboard"],
        "location_allowed": ["gym", "outdoor"],
        "contraindications": [],
        "prescription_defaults": {
            "sets": 8, "reps": 1, "work_seconds": None,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": None,
            "notes": "On The Minute (every 2 min). Grade at or above flash level. Longer rest than EMOM allows harder attempts."
        },
        "load_model": "grade_relative",
        "stress_tags": {"elbow": "medium", "fingers": "high", "cns": "high", "skin": "high"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "linked_boulders_circuit",
        "name": "Linked Boulder Circuit",
        "category": "power_endurance",
        "time_min": 25,
        "role": ["main"],
        "domain": ["power_endurance", "anaerobic_capacity"],
        "pattern": "climbing_intervals",
        "intensity_level": "high",
        "fatigue_cost": 8,
        "recency_group": "gym_linked_boulders",
        "equipment_required": [],
        "equipment_required_any": ["gym_boulder", "spraywall", "board_kilter", "board_moonboard"],
        "location_allowed": ["gym", "outdoor"],
        "contraindications": [],
        "prescription_defaults": {
            "sets": 3, "reps": 4, "work_seconds": None,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 300,
            "notes": "Link 3-5 boulders back-to-back, no rest between. Grade 2-3 below flash. 5 min rest between circuits."
        },
        "load_model": "grade_relative",
        "stress_tags": {"elbow": "high", "fingers": "high", "cns": "high", "skin": "high"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "arc_training_progressive",
        "name": "ARC Training Progressive",
        "category": "endurance",
        "time_min": 35,
        "role": ["main"],
        "domain": ["aerobic_capacity", "regeneration"],
        "pattern": "climbing_continuous",
        "intensity_level": "low",
        "fatigue_cost": 3,
        "recency_group": "gym_arc",
        "equipment_required": [],
        "equipment_required_any": ["gym_boulder", "gym_routes", "spraywall"],
        "location_allowed": ["gym", "outdoor"],
        "contraindications": [],
        "prescription_defaults": {
            "sets": 2, "reps": None, "work_seconds": 900,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 300,
            "notes": "Start at 15 min continuous, build to 30 min week over week. Grade well below onsight. Zero pump target."
        },
        "load_model": "grade_relative",
        "stress_tags": {"elbow": "low", "fingers": "low", "cns": "low", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "threshold_long_intervals",
        "name": "Threshold Long Intervals (2:1)",
        "category": "endurance",
        "time_min": 25,
        "role": ["main"],
        "domain": ["aerobic_capacity"],
        "pattern": "climbing_intervals",
        "intensity_level": "medium",
        "fatigue_cost": 6,
        "recency_group": "gym_threshold",
        "equipment_required": [],
        "equipment_required_any": ["gym_routes", "gym_boulder", "spraywall"],
        "location_allowed": ["gym", "outdoor"],
        "contraindications": [],
        "prescription_defaults": {
            "sets": 6, "reps": None, "work_seconds": 120,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
            "notes": "120s climb / 60s rest. Moderate pump OK, deep pump = too hard. RPE 7-8/10. Hörst recommended protocol."
        },
        "load_model": "grade_relative",
        "stress_tags": {"elbow": "medium", "fingers": "medium", "cns": "medium", "skin": "medium"},
        "description": None, "cues": [], "video_url": None,
    })

    exercises.append({
        "id": "regeneration_climbing",
        "name": "Regeneration Climbing",
        "category": "endurance",
        "time_min": 25,
        "role": ["cooldown"],
        "domain": ["regeneration"],
        "pattern": "climbing_continuous",
        "intensity_level": "very_low",
        "fatigue_cost": 1,
        "recency_group": "gym_arc",
        "equipment_required": [],
        "equipment_required_any": ["gym_boulder", "gym_routes", "spraywall"],
        "location_allowed": ["gym", "outdoor"],
        "contraindications": [],
        "prescription_defaults": {
            "sets": 1, "reps": None, "work_seconds": 1200,
            "rest_between_reps_seconds": None, "rest_between_sets_seconds": None,
            "notes": "Grade 4-6 below onsight. Conversational pace. 20-30 min. Focus on movement quality, not effort."
        },
        "load_model": "grade_relative",
        "stress_tags": {"elbow": "none", "fingers": "low", "cns": "none", "skin": "low"},
        "description": None, "cues": [], "video_url": None,
    })

    # ── 2D. Technique Drills (10) ──

    _TECH_BASE = {
        "category": "technique",
        "role": ["technique"],
        "pattern": "technique_drill",
        "equipment_required": [],
        "equipment_required_any": ["gym_boulder", "gym_routes", "spraywall"],
        "location_allowed": ["gym", "outdoor"],
        "contraindications": [],
        "load_model": "grade_relative",
        "description": None, "cues": [], "video_url": None,
    }

    _TECH_STRESS_LOW = {"elbow": "low", "fingers": "low", "cns": "low", "skin": "low"}
    _TECH_STRESS_NONE = {"elbow": "none", "fingers": "low", "cns": "low", "skin": "low"}

    tech_drills = [
        {
            "id": "sticky_feet", "name": "Sticky Feet Drill",
            "domain": ["technique_footwork"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_footwork_drills", "focus": "footwork", "time_min": 15,
            "prescription_defaults": {
                "sets": 6, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Place foot once, no adjustments. If you adjust, downclimb and restart. Grade 2-3 below onsight."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "foothold_stare", "name": "Foothold Stare Drill",
            "domain": ["technique_footwork"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_footwork_drills", "focus": "footwork", "time_min": 15,
            "prescription_defaults": {
                "sets": 6, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Look at every foothold 2s before placing. Grade 2-3 below onsight. Builds precision habit."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "tap_and_place", "name": "Tap and Place Drill",
            "domain": ["technique_footwork"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_footwork_drills", "focus": "footwork", "time_min": 15,
            "prescription_defaults": {
                "sets": 5, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Tap foothold with toe, hover 1s, then place. Develops deliberate foot placement."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "hover_hands", "name": "Hover Hands Drill",
            "domain": ["technique_movement"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_movement_drills", "focus": "movement", "time_min": 15,
            "prescription_defaults": {
                "sets": 5, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Hover hand over next hold 3s before grabbing. Forces body position awareness before reaching."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "hip_rotation_drill", "name": "Hip Rotation Drill",
            "domain": ["technique_body_position"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_body_position_drills", "focus": "body_position", "time_min": 15,
            "prescription_defaults": {
                "sets": 6, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Exaggerated hip turn into wall on every move. Inside/outside flag required each move."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "straight_arms", "name": "Straight Arms Drill",
            "domain": ["technique_body_position"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_body_position_drills", "focus": "body_position", "time_min": 15,
            "prescription_defaults": {
                "sets": 6, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Keep arms straight as much as possible. Bent arms = start over. Builds efficiency and hip drive."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "sloth_monkey", "name": "Sloth-Monkey Drill",
            "domain": ["technique_movement"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_movement_drills", "focus": "movement", "time_min": 15,
            "prescription_defaults": {
                "sets": 5, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "2 moves ultra-slow (sloth), then 2 moves fast/dynamic (monkey). Alternate throughout. Rhythm training."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "breathing_awareness", "name": "Breathing Awareness Drill",
            "domain": ["technique_relaxation"], "intensity_level": "low", "fatigue_cost": 1,
            "recency_group": "technique_relaxation_drills", "focus": "relaxation", "time_min": 15,
            "prescription_defaults": {
                "sets": 5, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Conscious exhale on every move. Count breaths. Never hold breath. Grade well below onsight."
            },
            "stress_tags": _TECH_STRESS_NONE,
        },
        {
            "id": "one_hand_climbing", "name": "One Hand Climbing Drill",
            "domain": ["technique_constraint"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_constraint_drills", "focus": "constraint", "time_min": 15,
            "contraindications": ["shoulder_injury"],
            "prescription_defaults": {
                "sets": 4, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 90,
                "notes": "Climb using only one hand (alternate left/right per boulder). Forces maximum footwork. Very easy grade."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
        {
            "id": "three_limb_drill", "name": "Three Limbs Drill",
            "domain": ["technique_constraint"], "intensity_level": "low", "fatigue_cost": 2,
            "recency_group": "technique_constraint_drills", "focus": "constraint", "time_min": 15,
            "prescription_defaults": {
                "sets": 5, "reps": 1, "work_seconds": None,
                "rest_between_reps_seconds": None, "rest_between_sets_seconds": 60,
                "notes": "Always keep 3 limbs on wall. Move only one limb at a time. Develops static, controlled climbing."
            },
            "stress_tags": _TECH_STRESS_LOW,
        },
    ]

    for td in tech_drills:
        ex = dict(_TECH_BASE)
        ex.update(td)
        # one_hand_climbing has its own contraindications
        if "contraindications" not in td:
            ex["contraindications"] = []
        exercises.append(ex)

    return exercises


def main():
    # ── Load ──
    with open(EXERCISES_PATH, "r") as f:
        data = json.load(f)

    original_count = len(data["exercises"])
    print(f"Loaded {original_count} exercises (version {data['version']})")

    # ── Migrate existing exercises ──
    migrated = [migrate_exercise(e) for e in data["exercises"]]
    print(f"Migrated {len(migrated)} exercises to v2 format")

    # ── Add new exercises ──
    new_exercises = get_new_exercises()
    # Verify no duplicates
    existing_ids = {e["id"] for e in migrated}
    for ne in new_exercises:
        if ne["id"] in existing_ids:
            print(f"  WARNING: {ne['id']} already exists, skipping")
        else:
            migrated.append(ne)
            existing_ids.add(ne["id"])

    print(f"Added {len(migrated) - original_count} new exercises")
    print(f"Total: {len(migrated)} exercises")

    # ── Verify silent_feet_drill has focus ──
    for e in migrated:
        if e["id"] == "silent_feet_drill" and "focus" not in e:
            print("  Adding focus to silent_feet_drill")

    # ── Write output ──
    output = {
        "version": "2.0",
        "exercises": migrated,
    }

    with open(EXERCISES_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Written to {EXERCISES_PATH}")

    # ── Validation ──
    canonical_fields = {"sets", "reps", "work_seconds", "rest_between_reps_seconds", "rest_between_sets_seconds"}
    errors = []
    for e in migrated:
        eid = e["id"]
        pd = e.get("prescription_defaults", {})
        pd_keys = {k for k in pd.keys() if k != "notes"}
        missing = canonical_fields - pd_keys
        if missing:
            errors.append(f"  {eid}: missing {missing}")

        if "description" not in e:
            errors.append(f"  {eid}: missing description")
        if "cues" not in e:
            errors.append(f"  {eid}: missing cues")
        if "video_url" not in e:
            errors.append(f"  {eid}: missing video_url")
        if "load_model" not in e:
            errors.append(f"  {eid}: missing load_model")

    if errors:
        print(f"\nValidation errors ({len(errors)}):")
        for err in errors:
            print(err)
        sys.exit(1)
    else:
        print("\nValidation passed: all exercises have canonical fields")


if __name__ == "__main__":
    main()
