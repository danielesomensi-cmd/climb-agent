"""A240 — Adhoc Coach v1, Phase 1: custom-session per-exercise logging +
immutability guard.

Closes D252 C.4 (HIGH: custom player logged nothing) and C.5 (MED: no
immutability test on custom insert/complete).

Invariants under test:
  1. A custom insert + complete NEVER mutates a sibling or past session's
     exercise_id / loads / status (past-session immutability, CLAUDE.md).
  2. Custom feedback DOES write working_loads (so re-picking an exercise can
     remember last load — the Phase-2 memory).
  3. Custom feedback NEVER feeds the macrocycle closed-loop (stimulus_recency /
     fatigue_proxy) — off-plan support work. Enforced both by omitting
     resolved_day AND by the server-side _is_custom_session guard, even if a
     future caller passes resolved_day for a custom session.
  4. A normal planned session STILL feeds the closed-loop (we didn't break it).
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
from backend.engine.replanner_v1 import apply_events

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Copy real state to tmp and monkeypatch STATE_PATH so tests are isolated."""
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage

    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


CS_ID = "cs_test01"
CUSTOM_REF = f"custom_{CS_ID}"


def _custom_slot() -> dict:
    """A saved-custom slot as add_custom_session would produce it."""
    return {
        "session_id": CUSTOM_REF,
        "custom_session_id": CS_ID,
        "slot": "evening",
        "session_mode": "custom_build",
        "is_custom": True,
        "status": "planned",
        "name": "Adhoc gym",
        "location": "gym",
        "estimated_load_score": 40,
        "exercises": [
            {
                "exercise_id": "bench_press",
                "sets": 3,
                "reps": 8,
                "work_seconds": None,
                "rest_between_sets_seconds": 120,
                "load_kg": 40,
                "notes": "",
            }
        ],
        "tags": {"hard": False, "finger": False},
    }


def _week_plan_with_custom(
    date: str = "2026-04-06",
    extra_sessions: list | None = None,
) -> dict:
    """Single-day plan (Mon) carrying the custom slot + any extra sessions."""
    return {
        "start_date": date,
        "weeks": [
            {
                "phase": "base",
                "days": [
                    {
                        "date": date,
                        "weekday": "mon",
                        "sessions": [_custom_slot(), *(extra_sessions or [])],
                    }
                ],
            }
        ],
    }


def _seed_state(wp: dict, *, fatigue_sentinel: str = "SENTINEL") -> None:
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {wp["start_date"]: deepcopy(wp)}
    state["session_completion_log"] = []
    # Sentinel closed-loop markers — if the closed-loop runs, these change.
    state["fatigue_proxy"] = {"last_updated_date": fatigue_sentinel}
    state["stimulus_recency"] = {"__sentinel__": True}
    # Drop any pre-existing working_loads entry for bench_press so the assertion
    # is unambiguous (the fixture state may carry unrelated history).
    wl = state.get("working_loads") or {}
    entries = wl.get("entries") or []
    wl["entries"] = [e for e in entries if e.get("exercise_id") != "bench_press"]
    state["working_loads"] = wl
    deps.save_state(state, None)


def _bench_feedback(date: str = "2026-04-06") -> dict:
    return {
        "log_entry": {
            "date": date,
            "session_id": CUSTOM_REF,
            "session_duration_seconds": 1800,
            "actual": {
                "exercise_feedback_v1": [
                    {
                        "exercise_id": "bench_press",
                        "feedback_label": "ok",
                        "completed": True,
                        "used_external_load_kg": 40,
                        "completed_sets": 3,
                    }
                ]
            },
        },
        "status": "done",
    }


def _bench_entry(state: dict) -> dict | None:
    for e in (state.get("working_loads") or {}).get("entries") or []:
        if e.get("exercise_id") == "bench_press":
            return e
    return None


# ── C.5: immutability of siblings / past sessions ───────────────────────


class TestCustomInsertImmutability:
    def test_custom_insert_then_complete_does_not_mutate_sibling_or_past(self):
        """Adding + completing a custom session must never touch a sibling
        (same day) or a past completed session's exercise_id / loads / status."""
        # A past, completed strength session carrying real load data.
        past = {
            "session_id": "strength_long",
            "slot": "evening",
            "location": "gym",
            "status": "done",
            "estimated_load_score": 55,
            "tags": {"hard": True, "finger": True},
            "actual_exercises": [
                {"exercise_id": "bench_press", "feedback_label": "hard", "used_external_load_kg": 50}
            ],
        }
        # A sibling planned session on the SAME day as the custom insert.
        sibling = {
            "session_id": "core_circuit",
            "slot": "lunch",
            "location": "home",
            "status": "planned",
            "estimated_load_score": 20,
            "tags": {"hard": False, "finger": False},
        }
        dates = [f"2026-03-{16 + i:02d}" for i in range(7)]
        plan = {
            "start_date": "2026-03-16",
            "weeks": [
                {
                    "phase": "base",
                    "days": [
                        {"date": dates[0], "weekday": "mon", "sessions": [deepcopy(past)]},
                        {"date": dates[2], "weekday": "wed", "sessions": [deepcopy(sibling)]},
                    ]
                    + [
                        {"date": dates[i], "weekday": w, "sessions": []}
                        for i, w in [(1, "tue"), (3, "thu"), (4, "fri"), (5, "sat"), (6, "sun")]
                    ],
                }
            ],
        }

        cs = {
            "id": CS_ID,
            "name": "Adhoc gym",
            "created_at": "2026-03-15T10:00:00Z",
            "updated_at": "2026-03-15T10:00:00Z",
            "tags": [],
            "exercises": _custom_slot()["exercises"],
            "estimated_load_score": 40,
            "estimated_duration_minutes": 45,
        }

        # Insert the custom session on Wed (same day as the sibling)…
        mid = apply_events(
            plan,
            [
                {
                    "event_type": "add_custom_session",
                    "custom_session_id": CS_ID,
                    "target_date": dates[2],
                    "slot": "evening",
                    "location": "gym",
                }
            ],
            custom_sessions=[cs],
        )
        # …then complete it.
        after = apply_events(
            mid,
            [
                {
                    "event_type": "mark_done",
                    "date": dates[2],
                    "session_ref": CUSTOM_REF,
                    "slot": "evening",
                }
            ],
        )

        days = {d["date"]: d for w in after["weeks"] for d in w["days"]}

        # Past session on Mon — byte-identical to the original.
        past_after = days[dates[0]]["sessions"][0]
        assert past_after == past, "past session mutated by custom insert/complete"

        # Sibling on Wed — byte-identical (find it by session_id; the custom
        # slot now shares the day).
        wed_sessions = days[dates[2]]["sessions"]
        sibling_after = next(s for s in wed_sessions if s["session_id"] == "core_circuit")
        assert sibling_after == sibling, "sibling session mutated by custom insert/complete"

        # And the custom slot itself is the one marked done.
        custom_after = next(s for s in wed_sessions if s["session_id"] == CUSTOM_REF)
        assert custom_after["status"] == "done"
        assert custom_after["is_custom"] is True


# ── C.4: per-exercise logging → working_loads, never closed-loop ────────


class TestCustomFeedbackBoundary:
    def test_custom_feedback_writes_working_loads(self):
        """POST /api/feedback for a custom session updates working_loads."""
        _seed_state(_week_plan_with_custom())
        r = client.post("/api/feedback", json=_bench_feedback())
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        entry = _bench_entry(state)
        assert entry is not None, "custom feedback did not write working_loads"
        assert entry.get("last_external_load_kg") == 40
        assert "next_external_load_kg" in entry

    def test_custom_feedback_does_not_touch_closed_loop(self):
        """Custom feedback (no resolved_day) leaves stimulus_recency /
        fatigue_proxy untouched — off-plan, never feeds the macrocycle loop."""
        _seed_state(_week_plan_with_custom())
        r = client.post("/api/feedback", json=_bench_feedback())
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        assert state["fatigue_proxy"]["last_updated_date"] == "SENTINEL"
        assert state["stimulus_recency"] == {"__sentinel__": True}

    def test_custom_feedback_skips_closed_loop_even_with_resolved_day(self):
        """Defensive: even if a caller passes resolved_day for a custom session,
        the _is_custom_session guard keeps the closed-loop off."""
        _seed_state(_week_plan_with_custom())
        payload = _bench_feedback()
        payload["resolved_day"] = {
            "date": "2026-04-06",
            "sessions": [
                {
                    "session_id": CUSTOM_REF,
                    "is_custom": True,
                    "tags": {"hard": True, "finger": True},
                }
            ],
        }
        r = client.post("/api/feedback", json=payload)
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        # working_loads still written…
        assert _bench_entry(state) is not None
        # …but the closed-loop stayed off despite resolved_day being present.
        assert state["fatigue_proxy"]["last_updated_date"] == "SENTINEL"
        assert state["stimulus_recency"] == {"__sentinel__": True}

    def test_custom_feedback_persists_actual_and_duration_on_slot(self):
        """Raw per-exercise data + measured duration attach to the custom slot."""
        _seed_state(_week_plan_with_custom())
        r = client.post("/api/feedback", json=_bench_feedback())
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        slot = state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert slot["session_id"] == CUSTOM_REF
        assert slot["status"] == "done"
        assert slot.get("actual_exercises")
        assert slot["actual_exercises"][0]["exercise_id"] == "bench_press"
        assert slot.get("session_duration_seconds") == 1800


class TestPlannedSessionStillFeedsClosedLoop:
    """Control: the closed-loop must STILL fire for a normal planned session —
    the A240 guard is scoped to custom sessions only."""

    def test_planned_session_feedback_updates_fatigue_proxy(self):
        planned = {
            "session_id": "strength_long",
            "slot": "morning",
            "location": "gym",
            "status": "planned",
            "estimated_load_score": 55,
            "tags": {"hard": True, "finger": True},
            "resolved": {"resolved_session": {"exercise_instances": []}},
        }
        _seed_state(_week_plan_with_custom(extra_sessions=[planned]))

        payload = {
            "log_entry": {
                "date": "2026-04-06",
                "session_id": "strength_long",
                "actual": {"exercise_feedback_v1": []},
            },
            "resolved_day": {
                "date": "2026-04-06",
                "sessions": [
                    {
                        "session_id": "strength_long",
                        "tags": {"hard": True, "finger": True},
                    }
                ],
            },
            "status": "done",
        }
        r = client.post("/api/feedback", json=payload)
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        # Closed-loop DID run for the normal session.
        assert state["fatigue_proxy"]["last_updated_date"] == "2026-04-06"
