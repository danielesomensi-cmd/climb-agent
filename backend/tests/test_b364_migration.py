"""B364 — scripts/migrate_b364.py: the pure migrate_state (no storage, no prod)."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

from backend.tests.test_b364_official_max_vs_working_load import _daniele

_spec = importlib.util.spec_from_file_location(
    "migrate_b364", Path(__file__).resolve().parents[2] / "scripts" / "migrate_b364.py")
migrate_b364 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_b364)
migrate_state = migrate_b364.migrate_state

TODAY = date(2026, 10, 5)
NOTE = ("INVARIATO. Sub-massimali: 32 kg contro i 48 del working load (~65%). "
        "Riaccendere il crimp, NON testarsi.")


def _prod_like():
    state = _daniele(entries=[
        {"key": "weighted_pullup", "setup": {}, "last_reps": 3, "updated_at": "2026-10-04",
         "exercise_id": "weighted_pullup", "e2rm_total_kg": 123.0, "last_completed": True,
         "last_total_load_kg": 108.0, "next_total_load_kg": 106.5, "last_feedback_label": "ok",
         "last_external_load_kg": 30.0, "next_external_load_kg": 28.5},
    ], registry={})
    state["progression_counters"].update({"max_hang_5s_easy_streak": 0, "max_hang_5s_hard_streak": 0})
    hang = {"exercise_id": "max_hang_7s", "sets": 4, "work_seconds": 7, "load_kg": 32.0, "notes": NOTE}
    state["custom_sessions"] = [
        {"id": "cs_743c5d6d", "exercises": [dict(hang)]},
        {"id": "cs_ab49edf6", "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3, "load_kg": 28.0},
                                            {"exercise_id": "dip", "sets": 3, "reps": 8, "load_kg": 0}]},
    ]
    state["week_plans"] = {
        "2026-09-28": {"weeks": [{"days": [
            {"date": "2026-10-01", "sessions": [{"session_id": "custom_cs_743c5d6d", "custom_session_id": "cs_743c5d6d",
                                                 "status": "done", "exercises": [dict(hang)]}]},
            {"date": "2026-10-04", "sessions": [{"session_id": "custom_cs_ab49edf6", "custom_session_id": "cs_ab49edf6",
                                                 "status": "done", "is_custom": True,
                                                 "actual_exercises": [{"exercise_id": "weighted_pullup", "completed": True,
                                                                       "completed_sets": 4, "used_external_load_kg": 30.0}]}]},
        ]}]},
        "2026-10-05": {"weeks": [{"days": [
            {"date": "2026-10-09", "sessions": [{"session_id": "custom_cs_743c5d6d", "custom_session_id": "cs_743c5d6d",
                                                 "status": "planned", "exercises": [dict(hang)]}]},
        ]}]},
    }
    archived = {"2026-09-21": {"weeks": [{"days": [
        {"date": "2026-09-24", "sessions": [
            {"session_id": "test_max_hang_7s", "status": "done", "tags": {"test": True},
             "actual_exercises": [{"exercise_id": "max_hang_7s", "completed": True, "used_total_load_kg": 116.0}]},
            {"session_id": "test_max_weighted_pullup", "status": "done", "tags": {"test": True},
             "actual_exercises": [{"exercise_id": "weighted_pullup", "completed": True, "used_external_load_kg": 45.0}]},
        ]},
    ]}]}, "2026-09-14": {"weeks": [{"days": [
        {"date": "2026-09-15", "sessions": [{"session_id": "strength_long", "status": "done",
                                             "actual_exercises": [{"exercise_id": "weighted_pullup", "completed": True,
                                                                   "completed_sets": 4, "used_external_load_kg": 25.0}]}]},
        {"date": "2026-09-18", "sessions": [{"session_id": "pulling_strength_gym", "status": "done",
                                             "actual_exercises": [{"exercise_id": "weighted_chinup", "completed": True,
                                                                   "completed_sets": 4, "used_external_load_kg": 20.0}]}]},
    ]}]}}
    return state, archived


def test_e2rm_entries_get_a_kg_step_and_lose_the_rebase():
    state, archived = _prod_like()
    out, log = migrate_state(state, archived, TODAY)
    e = out["working_loads"]["entries"][0]
    assert "e2rm_total_kg" not in e
    assert (e["next_total_load_kg"], e["next_external_load_kg"]) == (108.0, 30.0)
    assert any(line.startswith("(a)") for line in log)


def test_registry_seeded_from_archive_hot_weeks_and_tests():
    state, archived = _prod_like()
    reg = migrate_state(state, archived, TODAY)[0]["progression_counters"]["stimulus_exposures"]
    # 10/01: a done custom with no logged entries counts with its planned
    # exercises (A288 view rule, evidence "planned").
    assert [r["date"] for r in reg["finger_max"]] == ["2026-09-24", "2026-10-01"]
    assert reg["finger_max"][1]["evidence"] == "planned"
    assert [r["date"] for r in reg["pulling_max"]] == ["2026-09-15", "2026-09-18", "2026-09-24", "2026-10-04"]
    assert all(r["date"] <= "2026-10-05" for rows in reg.values() for r in rows)


def test_confidence_recomputed_with_the_archived_weeks():
    state, archived = _prod_like()
    out = migrate_state(state, archived, TODAY)[0]
    hang = [t for t in out["tests"]["max_strength"] if t["date"] == "2026-09-24"][0]
    pull = [t for t in out["tests"]["pulling_strength"] if t["date"] == "2026-09-24"][0]
    assert hang["confidence"] == "low" and hang["confidence_basis"]["exposures"] == 0
    assert pull["confidence"] == "high" and pull["confidence_basis"]["exposures"] == 2
    assert hang["trend"] == "stable" and hang["delta_pct"] == -4.9  # 116 vs 122
    assert pull["trend"] == "stable" and pull["delta_pct"] == 0.8
    assert out["baselines"]["hangboard"][0]["confidence"] == "low"
    assert out["baselines"]["pulling"]["confidence"] == "high"
    # Without the archive the pull-up test would wrongly look low-confidence.
    no_archive = migrate_state(state, None, TODAY)[0]
    assert [t for t in no_archive["tests"]["pulling_strength"] if t["date"] == "2026-09-24"][0]["confidence"] == "low"


def test_customs_get_load_mode_and_the_false_note_only_in_the_future():
    state, archived = _prod_like()
    out = migrate_state(state, archived, TODAY)[0]
    lib = out["custom_sessions"][0]["exercises"][0]
    assert lib["load_mode"] == "anchored" and "Sub-massimali" not in lib["notes"] and "94,8%" in lib["notes"]
    assert lib["notes"].endswith("Riaccendere il crimp, NON testarsi.")
    assert out["custom_sessions"][1]["exercises"][0]["load_mode"] == "anchored"
    assert "load_mode" not in out["custom_sessions"][1]["exercises"][1]
    past = out["week_plans"]["2026-09-28"]["weeks"][0]["days"][0]["sessions"][0]
    assert past == state["week_plans"]["2026-09-28"]["weeks"][0]["days"][0]["sessions"][0]
    future = out["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]
    assert "Sub-massimali" not in future["notes"] and future["load_mode"] == "anchored"


def test_tests_and_baselines_values_never_change_and_streaks_go():
    state, archived = _prod_like()
    out = migrate_state(state, archived, TODAY)[0]
    for cat in ("max_strength", "pulling_strength"):
        assert [t.get("total_load_kg") or t.get("total_load_2rm_kg") for t in out["tests"][cat]] == \
               [t.get("total_load_kg") or t.get("total_load_2rm_kg") for t in state["tests"][cat]]
    assert out["baselines"]["pulling"]["weighted_pullup_2rm_total_kg"] == 123.0
    assert "max_hang_5s_hard_streak" not in out["progression_counters"]


def test_idempotent_and_pure():
    state, archived = _prod_like()
    snapshot = repr(state)
    once, _ = migrate_state(state, archived, TODAY)
    twice, log = migrate_state(once, archived, TODAY)
    assert twice == once
    assert log == []
    assert repr(state) == snapshot
