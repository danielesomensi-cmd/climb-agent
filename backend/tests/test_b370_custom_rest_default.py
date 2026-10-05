"""B370 — a multi-set custom exercise without a rest between sets takes the catalog's.

A custom session saved with `rest_between_sets_seconds: null` (3x10 single-leg
calf raise, 2x15 reverse wrist curl) reached the player as 0: no rest timer, the
sets ran back to back. The catalog default fills the gap on save and on read
(sessions already stored); an explicit value — 0 included — is never touched.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers.custom_session import enrich_custom_sessions_for_play

client = TestClient(app)


def test_save_fills_missing_rest_from_catalog():
    client.delete("/api/state")
    r = client.post("/api/custom-session", json={"name": "Calf", "exercises": [
        {"exercise_id": "single_leg_calf_raise", "sets": 3, "reps": 10},
    ]})
    assert r.status_code == 201
    assert r.json()["exercises"][0]["rest_between_sets_seconds"] == 60


def test_read_fills_sessions_stored_without_rest():
    stored = [{"id": "cs_old", "exercises": [
        {"exercise_id": "single_leg_calf_raise", "sets": 3, "reps": 10,
         "rest_between_sets_seconds": None, "cues": ["stored cue"]},
    ]}]
    assert enrich_custom_sessions_for_play(stored)[0]["exercises"][0]["rest_between_sets_seconds"] == 60


def test_explicit_rest_wins_even_zero():
    stored = [{"id": "cs_x", "exercises": [
        {"exercise_id": "single_leg_calf_raise", "sets": 3, "reps": 10,
         "rest_between_sets_seconds": 0, "cues": ["c"]},
        {"exercise_id": "single_leg_calf_raise", "sets": 3, "reps": 10,
         "rest_between_sets_seconds": 45, "cues": ["c"]},
    ]}]
    out = enrich_custom_sessions_for_play(stored)[0]["exercises"]
    assert [e["rest_between_sets_seconds"] for e in out] == [0, 45]


def test_single_set_is_left_alone():
    stored = [{"id": "cs_y", "exercises": [
        {"exercise_id": "single_leg_calf_raise", "sets": 1, "reps": 10,
         "rest_between_sets_seconds": None, "cues": ["c"]},
    ]}]
    assert enrich_custom_sessions_for_play(stored)[0]["exercises"][0]["rest_between_sets_seconds"] is None
