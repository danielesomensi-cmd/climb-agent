"""A242 — Adhoc Coach v1, Phase 2: load proposal + history in the builder.

Closes D252 C.2 (HIGH: no working_loads read in custom path) and C.3 (MED:
builder proposes no load).

Invariants under test:
  1. Proposal is deterministic and derives structure from prescription_defaults.
  2. load_kg is the user's *remembered* value (from working_loads) or 0 — NEVER
     an invented absolute (RPE/RIR primary; kg only as logged memory).
  3. Remembered load is prefilled regardless of freshness (human reviews it),
     with recency surfaced via last_logged.date.
  4. Effort band is a display-only phase cue (never a number, never persisted).
  5. The read is non-mutating — proposing never adds working_loads to a state
     that had none (a GET must not mutate user_state).
  6. GET /api/custom-session/exercises carries the proposal per exercise.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine.adhoc_prescription import (
    PHASE_EFFORT_BAND,
    effort_band_for_phase,
    propose_exercise_prescription,
)

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

TODAY = "2026-07-20"

CATALOG = {
    "bench_press": {
        "id": "bench_press",
        "name": "Bench Press",
        "load_model": "external_load",
        "prescription_defaults": {
            "sets": 3,
            "reps": 8,
            "work_seconds": None,
            "rest_between_sets_seconds": 120,
            "rest_between_reps_seconds": None,
        },
    },
    "dead_hang_body": {
        "id": "dead_hang_body",
        "name": "Dead Hang",
        "load_model": "bodyweight_only",
        "prescription_defaults": {"sets": 3, "work_seconds": 10, "rest_between_sets_seconds": 120},
    },
}


def _state_with_load(exercise_id: str, kg: float, label: str, updated_at: str) -> dict:
    return {
        "working_loads": {
            "entries": [
                {
                    "exercise_id": exercise_id,
                    "key": exercise_id,
                    "setup": {},
                    "last_external_load_kg": kg,
                    "next_external_load_kg": kg,
                    "last_feedback_label": label,
                    "updated_at": updated_at,
                }
            ]
        }
    }


# ── Engine-level: deterministic proposal ────────────────────────────────


class TestProposeExercisePrescription:
    def test_structure_from_defaults(self):
        p = propose_exercise_prescription("bench_press", CATALOG, {}, "base", today=TODAY)
        assert p["sets"] == 3
        assert p["reps"] == 8
        assert p["rest_between_sets_seconds"] == 120

    def test_no_history_means_zero_load_no_invention(self):
        p = propose_exercise_prescription("bench_press", CATALOG, {}, "base", today=TODAY)
        assert p["load_kg"] == 0.0
        assert p["last_logged"] is None

    def test_remembered_load_prefilled(self):
        state = _state_with_load("bench_press", 45.0, "hard", "2026-07-10")
        p = propose_exercise_prescription("bench_press", CATALOG, state, "base", today=TODAY)
        assert p["load_kg"] == 45.0
        assert p["last_logged"]["load_kg"] == 45.0
        assert p["last_logged"]["feedback_label"] == "hard"
        assert p["last_logged"]["date"] == "2026-07-10"

    def test_remembered_load_prefilled_even_when_stale(self):
        """Freshness is disabled for the builder — a 6-month-old logged load is
        still prefilled (dated), unlike autonomous progression."""
        state = _state_with_load("bench_press", 50.0, "ok", "2026-01-05")  # ~200 days old
        p = propose_exercise_prescription("bench_press", CATALOG, state, "strength_power", today=TODAY)
        assert p["load_kg"] == 50.0
        assert p["last_logged"]["date"] == "2026-01-05"

    def test_bodyweight_history_without_kg_does_not_invent_load(self):
        """A logged entry with no external kg keeps load_kg at 0 but still
        surfaces the perceived-effort memory."""
        state = {
            "working_loads": {
                "entries": [
                    {
                        "exercise_id": "dead_hang_body",
                        "key": "dead_hang_body",
                        "setup": {},
                        "last_feedback_label": "ok",
                        "updated_at": "2026-07-15",
                    }
                ]
            }
        }
        p = propose_exercise_prescription("dead_hang_body", CATALOG, state, "base", today=TODAY)
        assert p["load_kg"] == 0.0
        assert p["last_logged"]["load_kg"] is None
        assert p["last_logged"]["feedback_label"] == "ok"

    def test_effort_band_per_phase(self):
        for phase, band in PHASE_EFFORT_BAND.items():
            p = propose_exercise_prescription("bench_press", CATALOG, {}, phase, today=TODAY)
            assert p["effort_band"] == band
        # No phase → no band (e.g. user without a macrocycle).
        assert propose_exercise_prescription("bench_press", CATALOG, {}, None, today=TODAY)["effort_band"] is None
        assert effort_band_for_phase("nonexistent_phase") is None

    def test_read_is_non_mutating(self):
        """Proposing must not add working_loads to a state that had none."""
        state: dict = {}
        propose_exercise_prescription("bench_press", CATALOG, state, "base", today=TODAY)
        assert "working_loads" not in state

        state2 = {"working_loads": {"entries": []}}
        before = deepcopy(state2)
        propose_exercise_prescription("bench_press", CATALOG, state2, "base", today=TODAY)
        assert state2 == before


# ── Endpoint-level: GET /exercises carries proposal ─────────────────────


@pytest.fixture()
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage

    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


class TestExercisesEndpointProposal:
    def test_exercises_response_includes_proposal(self, isolate_state):
        r = client.get("/api/custom-session/exercises", params={"q": "bench"})
        assert r.status_code == 200, r.text
        items = r.json()["exercises"]
        assert items, "expected at least one match for 'bench'"
        for it in items:
            assert "proposal" in it
            p = it["proposal"]
            assert "load_kg" in p and "effort_band" in p and "last_logged" in p

    def test_exercises_surfaces_remembered_load(self, isolate_state):
        # Seed a logged load for bench_press, then re-pick it.
        state = deps.load_state(None)
        state["working_loads"] = _state_with_load("bench_press", 42.5, "ok", "2026-06-01")["working_loads"]
        deps.save_state(state, None)

        r = client.get("/api/custom-session/exercises", params={"q": "bench press"})
        assert r.status_code == 200, r.text
        bench = next((x for x in r.json()["exercises"] if x["id"] == "bench_press"), None)
        assert bench is not None
        assert bench["proposal"]["load_kg"] == 42.5
        assert bench["proposal"]["last_logged"]["date"] == "2026-06-01"

    def test_exercises_endpoint_does_not_persist_mutation(self, isolate_state):
        """The read-only GET must not write working_loads into persisted state."""
        state = deps.load_state(None)
        state.pop("working_loads", None)
        deps.save_state(state, None)

        r = client.get("/api/custom-session/exercises", params={"q": "hang"})
        assert r.status_code == 200, r.text

        after = deps.load_state(None)
        assert "working_loads" not in after
