"""A316 — heart-rate bands: catalog field, pass-through, read-path backfill, coach line.

The catalog carries the band as % of HRmax (`hr_target`); the athlete's HRmax
lives in `body.hr_max_bpm`; the bpm are computed at display time (frontend) and
in the coach prompt. No age formula anywhere.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy

from backend.api.routers.custom_session import enrich_custom_sessions_for_play
from backend.engine import hr_zones
from backend.engine.resolve_session import resolve_session

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CARDIO = {
    "easy_run_zone2": [60, 70],
    "treadmill_incline_walk": [60, 70],
    "stationary_bike_zone2": [60, 70],
    "approach_hike_loaded": [60, 70],
    "treadmill_hiit_4x4": [90, 95],
}


def _catalog():
    with open(os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")) as f:
        return {e["id"]: e for e in json.load(f)["exercises"]}


def test_catalog_hr_targets_are_well_formed():
    cat = _catalog()
    with_target = {i for i, e in cat.items() if e.get("hr_target")}
    assert with_target == set(CARDIO)
    for ex_id, work in CARDIO.items():
        t = cat[ex_id]["hr_target"]
        assert t["basis"] == "hr_max"
        assert t["work_pct"] == work
        for key in ("work_pct", "recovery_pct"):
            if key in t:
                lo, hi = t[key]
                assert 40 <= lo < hi <= 100
    assert cat["treadmill_hiit_4x4"]["hr_target"]["recovery_pct"] == [65, 75]


def test_4x4_catalog_text_says_jog_not_walk():
    ex = _catalog()["treadmill_hiit_4x4"]
    text = " ".join(ex["cues"]) + ex["prescription_defaults"]["notes"]
    assert "85-95%" not in text
    assert "easy walk between intervals" not in text
    assert "easy jog" in text


def test_bpm_band_and_hr_max_bounds():
    assert hr_zones.bpm_band(190, (90, 95)) == (171, 180)
    assert hr_zones.bpm_band(190, (60, 70)) == (114, 133)
    # .5 cases stay inside the band and match frontend/src/lib/hr-zones.ts.
    assert hr_zones.bpm_band(190, (65, 75)) == (124, 142)
    assert hr_zones.bpm_band(185, (90, 95)) == (167, 175)
    assert hr_zones.hr_max({"body": {"hr_max_bpm": 190}}) == 190
    assert hr_zones.hr_max({"body": {}, "assessment": {"body": {"hr_max_bpm": 192}}}) == 192
    for bad in (None, 0, 90, 260, "190", True):
        assert hr_zones.hr_max({"body": {"hr_max_bpm": bad}}) is None
    assert hr_zones.hr_rest({"body": {"hr_rest_bpm": 52}}) == 52
    assert hr_zones.hr_rest({"body": {"hr_rest_bpm": 5}}) is None


def test_coach_line_only_with_hr_max():
    assert hr_zones.coach_line({"body": {"weight_kg": 78}}) is None
    line = hr_zones.coach_line({"body": {"hr_max_bpm": 190, "hr_rest_bpm": 52, "hr_max_source": "measured"}})
    assert "HRmax 190 bpm (measured)" in line
    assert "resting HR 52" in line
    assert "Zone 2 114-133" in line and "171-180" in line


def test_coach_profile_section_carries_the_line():
    from backend.coach.prompt_builder import _profile_section

    out = _profile_section({"body": {"hr_max_bpm": 190}})
    assert "HRmax 190 bpm" in out
    assert "HRmax" not in _profile_section({"body": {"weight_kg": 78}})


def test_resolved_cardio_session_carries_hr_target():
    with open(os.path.join(REPO_ROOT, "backend/tests/fixtures/test_user_state.json")) as f:
        us = json.load(f)
    us = deepcopy(us)
    us.setdefault("context", {}).update({"location": "gym", "gym_id": None})
    us.setdefault("equipment", {}).setdefault("gyms", [])
    for g in us["equipment"]["gyms"]:
        g.setdefault("equipment", []).append("treadmill")
    us["equipment"].setdefault("home", []).append("treadmill")
    out = resolve_session(
        repo_root=REPO_ROOT,
        session_path="backend/catalog/sessions/v1/treadmill_hiit_4x4.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path="",
        user_state_override=us,
        write_output=False,
    )
    insts = out["resolved_session"]["exercise_instances"]
    hiit = [i for i in insts if i["exercise_id"] == "treadmill_hiit_4x4"]
    assert hiit, [i["exercise_id"] for i in insts]
    assert hiit[0]["hr_target"]["work_pct"] == [90, 95]
    # Exercises without a band do not get the key at all.
    assert all("hr_target" not in i for i in insts if i["exercise_id"] not in CARDIO)


def test_custom_read_backfills_hr_target():
    stored = [{"id": "cs_hiit", "exercises": [
        {"exercise_id": "treadmill_hiit_4x4", "sets": 4, "work_seconds": 240, "cues": ["stored"]},
        {"exercise_id": "single_leg_calf_raise", "sets": 3, "reps": 10, "cues": ["c"],
         "hr_target": {"basis": "hr_max", "work_pct": [1, 2]}},
    ]}]
    out = enrich_custom_sessions_for_play(stored)[0]["exercises"]
    assert out[0]["hr_target"]["work_pct"] == [90, 95]
    assert "hr_target" not in out[1]


def test_week_read_backfills_unplayed_custom_slot_only():
    from backend.api.routers.week import _with_custom_anchored_loads

    row = {"exercise_id": "easy_run_zone2", "sets": 1, "work_seconds": 600}
    plan = {"weeks": [{"days": [{"date": "2026-10-20", "sessions": [
        {"session_id": "custom_cs_a", "is_custom": True, "status": "planned", "exercises": [dict(row)]},
        {"session_id": "custom_cs_b", "is_custom": True, "status": "done", "exercises": [dict(row)]},
    ]}]}]}
    sessions = _with_custom_anchored_loads(plan, {})["weeks"][0]["days"][0]["sessions"]
    assert sessions[0]["exercises"][0]["hr_target"]["work_pct"] == [60, 70]
    # Done sessions are returned exactly as stored; the stored plan is untouched.
    assert "hr_target" not in sessions[1]["exercises"][0]
    assert "hr_target" not in plan["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]


def test_settings_save_path_keeps_hr_fields(tmp_path, monkeypatch):
    """The Settings patch (assessment.body + mirrored body) survives PUT /api/state
    and /api/assessment/compute, and the coach reads it back."""
    import shutil
    from pathlib import Path

    from fastapi.testclient import TestClient

    from backend.api import deps
    from backend.api.main import app
    from backend.engine import storage

    src = Path(REPO_ROOT) / "backend" / "tests" / "fixtures" / "test_user_state.json"
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(src, tmp_state)
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    client = TestClient(app)

    hr = {"hr_max_bpm": 190, "hr_rest_bpm": 52, "hr_max_source": "measured"}
    assert client.put("/api/state", json={"assessment": {"body": hr}, "body": hr}).status_code == 200
    st = client.get("/api/state?full=1").json()
    assert {k: st["body"][k] for k in hr} == hr
    assert {k: st["assessment"]["body"][k] for k in hr} == hr
    res = client.post("/api/assessment/compute", json={"assessment": st["assessment"], "goal": st.get("goal") or {}})
    assert res.status_code == 200
    after = client.get("/api/state?full=1").json()
    assert hr_zones.hr_max(after) == 190 and hr_zones.hr_rest(after) == 52
    assert "4x4 intervals 171-180" in hr_zones.coach_line(after)
