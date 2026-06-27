"""A229 — Pallof Press weight progression (propose + adjust).

A229 upgrades Pallof from `bodyweight_only` (record-only, A228/D249) to
`external_load`: the engine now PROPOSES a starting weight (cold-start 10 kg)
and ADJUSTS it from the actual weight used + feedback (very_easy → heavier,
hard → lighter), reusing the existing external_load progression machinery.

Pallof is also made eligible with a band OR a cable
(`equipment_required_any: [resistance_band, cable_machine]`), and a cue tells
band users to match the suggested kg with band tension.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.engine.progression_v1 import inject_targets, apply_feedback
from backend.engine.resolve_session import pick_best_exercise_p0

REPO_ROOT = Path(__file__).resolve().parents[2]
EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
ALL_EXERCISES = json.loads(EXERCISES_PATH.read_text(encoding="utf-8"))["exercises"]


def _pallof_day():
    return {"date": "2026-06-27", "sessions": [{"session_id": "core_training", "exercise_instances": [
        {"exercise_id": "pallof_press", "load_model": "external_load", "prescription": {"sets": 3, "reps": 8}}
    ]}]}


def _pallof_entry(state):
    entries = (state.get("working_loads") or {}).get("entries") or []
    return next((e for e in entries if e.get("exercise_id") == "pallof_press"), None)


# 1 — cold-start: engine proposes 10 kg when there is no history
def test_cold_start_proposes_10kg():
    out = inject_targets(_pallof_day(), {"bodyweight_kg": 77.0})
    sug = out["sessions"][0]["exercise_instances"][0].get("suggested") or {}
    assert sug.get("suggested_external_load_kg") == 10.0


# 2 — very_easy on a logged weight → next suggestion is HEAVIER
def test_very_easy_increases_weight():
    log = {"date": "2026-06-27", "actual": {"exercise_feedback_v1": [
        {"exercise_id": "pallof_press", "load_model": "external_load",
         "feedback_label": "very_easy", "completed": True, "used_external_load_kg": 10.0}
    ]}}
    out = apply_feedback(log, {"bodyweight_kg": 77.0})
    entry = _pallof_entry(out)
    assert entry is not None
    assert entry["next_external_load_kg"] > 10.0


# 3 — hard → next suggestion is NOT heavier (holds or drops)
def test_hard_does_not_increase_weight():
    log = {"date": "2026-06-27", "actual": {"exercise_feedback_v1": [
        {"exercise_id": "pallof_press", "load_model": "external_load",
         "feedback_label": "hard", "completed": True, "used_external_load_kg": 10.0}
    ]}}
    out = apply_feedback(log, {"bodyweight_kg": 77.0})
    entry = _pallof_entry(out)
    assert entry is not None
    assert entry["next_external_load_kg"] <= 10.0


# 4 — after feedback, the new working load drives the next suggestion
def test_adjusted_weight_feeds_next_suggestion():
    log = {"date": "2026-06-27", "actual": {"exercise_feedback_v1": [
        {"exercise_id": "pallof_press", "load_model": "external_load",
         "feedback_label": "very_easy", "completed": True, "used_external_load_kg": 10.0}
    ]}}
    state = apply_feedback(log, {"bodyweight_kg": 77.0})
    nxt = _pallof_entry(state)["next_external_load_kg"]
    out = inject_targets(_pallof_day(), state)
    sug = out["sessions"][0]["exercise_instances"][0].get("suggested") or {}
    assert sug.get("suggested_external_load_kg") == nxt  # >10, not the cold-start default


# 5 — eligibility: selectable with a band OR a cable, not without either
def test_eligible_with_band_or_cable():
    def picks_pallof(equipment):
        ex, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES, location="gym", available_equipment=equipment,
            role_req=["accessory"], domain_req=["core"], pattern_req=["anti_rotation"],
            recent_ex_ids=["copenhagen_plank", "plank_shoulder_tap"], recent_recency_groups=set(),
        )
        return (ex or {}).get("id") == "pallof_press"

    assert picks_pallof(["resistance_band"])               # band only
    assert picks_pallof(["cable_machine"])                 # cable only
    # neither band nor cable → pallof filtered out, a no-equipment sibling wins
    ex, _ = pick_best_exercise_p0(
        exercises=ALL_EXERCISES, location="gym", available_equipment=["pullup_bar"],
        role_req=["accessory"], domain_req=["core"], pattern_req=["anti_rotation"],
        recent_ex_ids=[], recent_recency_groups=set(),
    )
    assert (ex or {}).get("id") != "pallof_press"
