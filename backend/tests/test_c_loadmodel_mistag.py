"""C-LOADMODEL-MISTAG — loadable leg accessories become external_load with a
single (bilateral) load + closed loop, WITHOUT mis-routing through the finger
loading-pin path.

Background (see docs/audit/D259 + Phase-1 analysis):
  - Bulgarian/Cossack/etc. were ``bodyweight_only`` → no kg field, no memory,
    no progression. Now ``external_load`` → loggable everywhere + closed loop.
  - The per-hand loading-pin suggested/write branches used to gate on raw
    ``unilateral``. Unilateral LEG accessories (split_squat, and post-brief
    bulgarian/cossack) were therefore mis-routed into ``_loading_pin_suggested``
    (finger baseline, per-hand structure). The gate now keys on genuine
    ``loading_pin`` equipment, so:
      * finger lp_* work → per-hand (unchanged);
      * leg accessories → single bilateral load (crude bw×0.15 seed the user
        corrects, then a real progression).
  - split_squat was ALREADY mis-routed in production — this fixes it too.
  - The 3 tiny isolation accessories (side_lying_hip_abduction,
    hip_flexor_strengthening, seated_leg_raise_hip_flexor) + the skill
    progression pistol_squat stay ``bodyweight_only`` (option (a) / ARCH-2).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from backend.engine.progression_v1 import apply_feedback, inject_targets

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

RETAGGED = [
    "elbow_wrist_extensor_eccentric", "stick_pronation_supination_eccentric",
    "bulgarian_split_squat", "cossack_squat", "reverse_lunge",
    "single_leg_calf_raise", "glute_bridge", "single_leg_glute_bridge",
    "single_leg_rdl",
]
STILL_BODYWEIGHT = [
    "side_lying_hip_abduction", "hip_flexor_strengthening",
    "seated_leg_raise_hip_flexor", "pistol_squat_progression",
]


def _catalog() -> dict:
    items = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["exercises"]
    return {e["id"]: e for e in items}


def _state() -> dict:
    return {
        "bodyweight_kg": 77.0,
        # A hangboard baseline exists so a genuine loading-pin exercise CAN
        # produce a per-hand suggestion via the hangboard→pin fallback — proving
        # the leg accessories stay single-load by routing, not by lack of data.
        "baselines": {"hangboard": [{"max_total_load_kg": 102.0}]},
        "working_loads": {
            "entries": [],
            "rules": {"adjustment_policy": {
                "ok": {"pct_range": [0.0, 0.05]},
                "easy": {"pct_range": [0.05, 0.1]},
            }},
        },
        "equipment": {"home": ["hangboard", "weight", "pullup_bar"], "gyms": []},
    }


def _day(exercise_id: str, date: str = "2026-01-05") -> dict:
    return {
        "date": date,
        "sessions": [{
            "session_id": "s", "intent": "strength", "location": "home",
            "gym_id": None, "tags": {},
            "exercise_instances": [{"exercise_id": exercise_id, "prescription": {"sets": 3, "reps": 8}}],
        }],
    }


def _suggested(user_state: dict, exercise_id: str, date: str = "2026-01-05") -> dict:
    out = inject_targets(_day(exercise_id, date), user_state)
    return out["sessions"][0]["exercise_instances"][0].get("suggested") or {}


# ── Catalog re-tag ───────────────────────────────────────────────────────


def test_retagged_are_external_load():
    cat = _catalog()
    for eid in RETAGGED:
        assert cat[eid]["load_model"] == "external_load", eid


def test_excluded_stay_bodyweight_only():
    cat = _catalog()
    for eid in STILL_BODYWEIGHT:
        assert cat[eid]["load_model"] == "bodyweight_only", eid


def test_retagged_carry_no_equipment_gate():
    # load_model is not a filter; these must stay doable bodyweight (no forced
    # weight equipment) so equipment-poor users still get them.
    cat = _catalog()
    for eid in ("bulgarian_split_squat", "cossack_squat", "glute_bridge"):
        assert (cat[eid].get("equipment_required") or []) == [], eid


# ── Leg accessories → single (bilateral) load, NOT finger per-hand ───────


def test_bulgarian_single_load_not_per_hand():
    sug = _suggested(_state(), "bulgarian_split_squat")
    assert sug.get("suggested_external_load_kg") is not None
    assert sug["suggested_external_load_kg"] > 0          # crude bw×0.15 seed
    assert "right_hand" not in sug and "left_hand" not in sug


def test_cossack_single_load_not_per_hand():
    sug = _suggested(_state(), "cossack_squat")
    assert sug.get("suggested_external_load_kg") is not None
    assert "right_hand" not in sug and "left_hand" not in sug


def test_split_squat_no_longer_finger_derived():
    # Regression: split_squat (weight equip, unilateral) used to route through
    # _loading_pin_suggested and read the finger/hangboard baseline.
    sug = _suggested(_state(), "split_squat")
    assert sug.get("suggested_external_load_kg") is not None
    assert "right_hand" not in sug and "left_hand" not in sug


def test_eccentric_uses_light_fixed_seed():
    # Without the FIXED_KG entry these would seed 0.15×77 ≈ 11.5 kg — absurd for
    # wrist/forearm prehab.
    assert _suggested(_state(), "elbow_wrist_extensor_eccentric")["suggested_external_load_kg"] == 1.5
    assert _suggested(_state(), "stick_pronation_supination_eccentric")["suggested_external_load_kg"] == 1.0


# ── Genuine loading-pin work stays per-hand ──────────────────────────────


def test_loading_pin_still_per_hand():
    sug = _suggested(_state(), "lp_max_lift_5s")
    assert "right_hand" in sug and "left_hand" in sug
    assert "suggested_external_load_kg" not in sug


# ── Closed loop: log → remember (single key) → propose next ──────────────


def test_bulgarian_closed_loop_single_key():
    st = _state()
    log = {
        "date": "2026-01-06",
        "planned": [{"exercise_instances": [{"exercise_id": "bulgarian_split_squat", "prescription": {}}]}],
        "actual": {"exercise_feedback_v1": [{
            "exercise_id": "bulgarian_split_squat",
            "completed": True,
            "feedback_label": "ok",
            "used_external_load_kg": 20.0,
        }]},
    }
    updated = apply_feedback(log, st)
    entries = updated["working_loads"]["entries"]
    # single key, NOT bulgarian_split_squat:right / :left
    keys = {e.get("key") for e in entries if e.get("exercise_id") == "bulgarian_split_squat"}
    assert keys == {"bulgarian_split_squat"}
    entry = next(e for e in entries if e["key"] == "bulgarian_split_squat")
    assert entry["last_external_load_kg"] == 20.0
    # ok midpoint = (0.0+0.05)/2 = 0.025 → 20 × 1.025 = 20.5
    assert entry["next_external_load_kg"] == 20.5

    # …and it is proposed back on the next resolve (dated after the feedback,
    # else the entry is (correctly) rejected as future-dated).
    assert _suggested(updated, "bulgarian_split_squat", "2026-01-07")["suggested_external_load_kg"] == 20.5


# ── Immutability ─────────────────────────────────────────────────────────


def test_inject_does_not_mutate_state():
    st = _state()
    before = deepcopy(st)
    _suggested(st, "bulgarian_split_squat")
    _suggested(st, "lp_max_lift_5s")
    assert st == before
