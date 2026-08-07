"""Regression guard for scripts/export_training_log.py (health-vault export).

The exporter feeds an HRV/sleep correlation analysis, so its honesty rules are
load-bearing: a faked start time or an invented RPE would poison the join. These
tests pin exactly those rules.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "export_training_log", REPO_ROOT / "scripts" / "export_training_log.py"
)
etl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(etl)


BASE_STATE = {
    "session_completion_log": [
        # real timer (guided, new started_at) → timer_reale
        {"date": "2026-08-05", "session_id": "finger_strength_home", "status": "done",
         "started_at": "2026-08-05T17:02:00+00:00", "finished_at": "2026-08-05T17:46:00+00:00",
         "completed_at": "2026-08-05T17:46:00+00:00", "difficulty": "hard", "exercise_count": 5,
         "session_duration_seconds": 2640},
        # no real start → ora_inizio reconstructed but flagged tap_stimato
        {"date": "2026-08-01", "session_id": "route_endurance_gym", "status": "done",
         "completed_at": "2026-08-01T20:10:00+00:00", "difficulty": "ok",
         "session_duration_seconds": 4200},
        # skipped → no load, no rpe
        {"date": "2026-07-30", "session_id": "limit_boulder_gym", "status": "skipped",
         "completed_at": "2026-07-30T21:00:00+00:00"},
    ],
    "week_plans": {
        "2026-08-03": {"start_date": "2026-08-03", "weeks": [{"days": [
            {"date": "2026-08-05", "sessions": [
                {"session_id": "finger_strength_home", "session_load_actual": 34, "session_load_score": 40}]},
            {"date": "2026-08-01", "sessions": [
                {"session_id": "route_endurance_gym", "session_load_score": 48}]},
        ]}]},
    },
    "outdoor_log": [
        {"date": "2026-08-05", "spot_name": "Berdorf", "discipline": "sport", "duration_minutes": 120,
         "started_at": "2026-08-05T18:00:00+00:00", "finished_at": "2026-08-05T20:00:00+00:00",
         "load_score": 58, "notes": "progetto 7b", "routes": [{"grade": "6c"}, {"grade": "7b"}]},
    ],
}


def _by(rows, date, sid_substr):
    for r in rows:
        if r["data"] == date and sid_substr in r["descrizione"].lower():
            return r
    raise AssertionError(f"row {date}/{sid_substr} not found in {rows}")


def test_real_timer_row_is_timer_reale_with_actual_load():
    rows = etl.build_rows(BASE_STATE)
    r = _by(rows, "2026-08-05", "finger")
    assert r["orari_fonte"] == "timer_reale"
    assert r["ora_inizio"] == "19:02"  # 17:02 UTC → CEST
    assert r["ora_fine"] == "19:46"
    assert r["load"] == 34 and r["load_fonte"] == "actual"
    assert r["tipo"] == "hangboard" and r["carico_dita"] == "alto"
    assert r["rpe_stimato"] != ""  # estimated, present


def test_no_real_start_leaves_fidelity_flagged():
    rows = etl.build_rows(BASE_STATE)
    r = _by(rows, "2026-08-01", "route endurance")
    # start reconstructed from measured duration off the real finish — flagged.
    assert r["orari_fonte"] == "tap_stimato"
    assert r["ora_fine"] == "22:10"
    assert r["load"] == 48 and r["load_fonte"] == "prescribed"


def test_skipped_session_has_no_load_and_no_rpe():
    rows = etl.build_rows(BASE_STATE)
    r = _by(rows, "2026-07-30", "limit")
    assert r["stato"] == "skipped"
    assert r["load"] == "" and r["rpe_stimato"] == ""


def test_outdoor_is_falesia_with_grade_load():
    rows = etl.build_rows(BASE_STATE)
    r = _by(rows, "2026-08-05", "berdorf")
    assert r["tipo"] == "falesia_outdoor"
    assert r["orari_fonte"] == "timer_reale"
    assert r["load"] == 58 and r["load_fonte"] == "outdoor_grade"
    assert "7b" in r["descrizione"]


def test_rpe_estimate_never_invented_without_any_signal():
    # No load, no difficulty → estimate must stay blank, not a fabricated number.
    assert etl.estimate_rpe(None, None) == ""
    # Load present → estimate produced, clamped into 1..10.
    assert etl.estimate_rpe(85, None) == "10"
    # load 0 blended 50/50 with very_easy (anchor 2) → 1, clamped to floor 1.
    assert etl.estimate_rpe(0, "very_easy") == "1"
    # a mid load with a very_hard label lands high.
    assert etl.estimate_rpe(60, "very_hard") == "8"


def test_since_filter():
    rows = etl.build_rows(BASE_STATE, since="2026-08-02")
    assert all(r["data"] >= "2026-08-02" for r in rows)
    assert rows  # 2026-08-05 rows survive
