"""A314 — the athlete context lists the exercises done in the last 3 days and
flags the accessory / core / prehab ones not to repeat today.

Real case: copenhagen_plank composed by hand into the custom sessions of
13/10 and 14/10/2026, back to back, because nothing showed the day before.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from backend.engine import athlete_context as ac
from backend.tests.test_a293_athlete_context import _sess, _set_day, _state

CAT = {
    "copenhagen_plank": {"category": "core", "name": "Copenhagen Plank"},
    "ring_pushup": {"category": "strength_accessory", "name": "Ring Push-up"},
    "weighted_pullup": {"category": "main_strength", "name": "Weighted Pull-up"},
    "general_pulse_raise": {"category": "warmup_general", "name": "Pulse Raise"},
    "dead_bug": {"category": "core", "name": "Dead Bug"},
}


def _st():
    st = _state()
    _set_day(st, "2026-09-28", "2026-10-02", [
        _sess("lunch", "custom_cs_a", "done", is_custom=True, actual_exercises=[
            {"exercise_id": "general_pulse_raise", "completed": True, "completed_sets": 1, "prescribed_sets": 1},
            {"exercise_id": "copenhagen_plank", "completed": True, "completed_sets": 3, "prescribed_sets": 3,
             "feedback_label": "easy"},
            {"exercise_id": "ring_pushup", "completed": True, "completed_sets": 3, "prescribed_sets": 3,
             "used_external_load_kg": 0},
        ]),
    ])
    _set_day(st, "2026-09-28", "2026-10-03", [
        _sess("lunch", "custom_cs_b", "done", is_custom=True, actual_exercises=[
            {"exercise_id": "copenhagen_plank", "completed": True, "completed_sets": 1, "prescribed_sets": 3},
        ]),
        _sess("evening", "custom_cs_c", "skipped", is_custom=True, actual_exercises=[
            {"exercise_id": "dead_bug", "completed": True, "completed_sets": 3, "prescribed_sets": 3},
        ]),
    ])
    _set_day(st, "2026-09-28", "2026-09-29", [
        _sess("lunch", "custom_cs_old", "done", is_custom=True, actual_exercises=[
            {"exercise_id": "dead_bug", "completed": True, "completed_sets": 3, "prescribed_sets": 3},
        ]),
    ])
    return st


def test_groups_done_exercises_of_the_last_three_days():
    rx = ac.recent_exercises(_st(), "2026-10-04", catalog=CAT)
    assert rx["window_start"] == "2026-10-01" and rx["window_end"] == "2026-10-04"
    by = {r["exercise_id"]: r for r in rx["exercises"]}
    # 09-29 is outside the 72 h window, the skipped session never counts.
    assert "dead_bug" not in by
    assert [x["date"] for x in by["copenhagen_plank"]["done"]] == ["2026-10-02", "2026-10-03"]
    first = by["copenhagen_plank"]["done"][0]
    assert (first["completed_sets"], first["prescribed_sets"], first["feedback_label"]) == (3, 3, "easy")
    assert by["copenhagen_plank"]["last_date"] == "2026-10-03"


def test_no_repeat_lists_accessory_core_prehab_of_the_last_48h_only():
    rx = ac.recent_exercises(_st(), "2026-10-04", catalog=CAT)
    assert [r["exercise_id"] for r in rx["no_repeat"]] == ["copenhagen_plank", "ring_pushup"]
    assert rx["no_repeat"][0]["dates"] == ["2026-10-02", "2026-10-03"]
    # Two days later: 10-02 left the 48 h window, 10-03 is still in it.
    later = ac.recent_exercises(_st(), "2026-10-05", catalog=CAT)
    assert [r["exercise_id"] for r in later["no_repeat"]] == ["copenhagen_plank"]


def test_repeated_exercises_flags_the_draft_but_not_warmups():
    rx = ac.recent_exercises(_st(), "2026-10-04", catalog=CAT)
    rep = ac.repeated_exercises(["general_pulse_raise", "copenhagen_plank", "weighted_pullup",
                                 "copenhagen_plank"], rx, "2026-10-04")
    # weighted_pullup is main strength, done on 10-04 in the base state: flagged
    # too (only the generic warm-up / cool-down categories are exempt).
    assert rep == [{"exercise_id": "copenhagen_plank", "dates": ["2026-10-02", "2026-10-03"]},
                   {"exercise_id": "weighted_pullup", "dates": ["2026-10-04"]}]


def test_context_carries_and_renders_the_section():
    ctx = ac.build_athlete_context(_st(), "2026-10-04", catalog=None, with_proposals=False,
                                   include_next_week=False)
    assert "recent_exercises" in ctx
    text = ac.render_text(ctx)
    assert "## Esercizi fatti negli ultimi 3 giorni" in text
    assert "Da non ripetere oggi" in text and "copenhagen_plank (2026-10-02, 2026-10-03)" in text
    assert "copenhagen_plank [core]: 2026-10-02 3/3 serie «easy»; 2026-10-03 1/3 serie" in text


def test_simulate_warns_on_a_repetition():
    path = Path(__file__).resolve().parents[2] / "scripts" / "athlete_context.py"
    spec = importlib.util.spec_from_file_location("athlete_context_cli_a314", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    draft = {"name": "Core", "exercises": [{"exercise_id": "copenhagen_plank", "sets": 3, "work_seconds": 20}]}
    sim = mod.simulate(_st(), draft, "2026-10-05", "evening", today="2026-10-04")
    assert sim.get("repeats") == [{"exercise_id": "copenhagen_plank", "dates": ["2026-10-03"]}]
    assert any(w.startswith("ripetizione: copenhagen_plank fatto il 2026-10-03") for w in sim["warnings"])
