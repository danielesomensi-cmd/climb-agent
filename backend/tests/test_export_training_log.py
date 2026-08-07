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


# ── outdoor times reconstructed from the save timestamp ─────────────────────
# The state's bookkeeping array has no duration; the outdoor_logs table does.
# These pin when that duration is allowed to become a clock time and when not.

OUTDOOR_STATE = {
    "session_completion_log": [],
    "outdoor_log": [
        {"date": "2026-07-19", "spot_name": "Berdorf", "load_score": 40},   # saved same day
        {"date": "2026-08-05", "spot_name": "Berdorf", "load_score": 24},   # saved next day
        {"date": "2026-07-21", "spot_name": "Berdorf", "load_score": 30},   # no detail row
    ],
}
OUTDOOR_DETAIL_ROWS = [
    {"session_date": "2026-07-19", "created_at": "2026-07-19T19:54:09+00:00",
     "entry": {"date": "2026-07-19", "duration_minutes": 493}},
    {"session_date": "2026-08-05", "created_at": "2026-08-06T10:23:14+00:00",
     "entry": {"date": "2026-08-05", "duration_minutes": 120}},
]


def _outdoor_rows(details=None):
    idx = etl.index_outdoor_details(details) if details is not None else None
    return {r["data"]: r for r in etl.build_rows(OUTDOOR_STATE, outdoor_details=idx)}


def test_outdoor_saved_same_day_gets_times_from_the_save():
    r = _outdoor_rows(OUTDOOR_DETAIL_ROWS)["2026-07-19"]
    assert r["orari_fonte"] == "salvataggio_stimato"
    assert r["ora_fine"] == "21:54"            # 19:54 UTC → CEST, the save
    assert r["ora_inizio"] == "13:41"          # save − 493 min


def test_outdoor_saved_the_day_after_stays_blank():
    # The motivating case: 05/08 Berdorf, logged the next morning. A window
    # reconstructed from a 10:23 save would be fiction, and it feeds the
    # night-validity criteria in health-vault.
    r = _outdoor_rows(OUTDOOR_DETAIL_ROWS)["2026-08-05"]
    assert r["orari_fonte"] == "manuale"
    assert r["ora_inizio"] == "" and r["ora_fine"] == ""


def test_outdoor_without_a_detail_row_stays_blank():
    r = _outdoor_rows(OUTDOOR_DETAIL_ROWS)["2026-07-21"]
    assert r["orari_fonte"] == "manuale"
    assert r["ora_inizio"] == ""


def test_outdoor_details_are_optional_and_change_nothing_when_absent():
    # Backwards compatibility: no --outdoor-logs → the old behaviour, exactly.
    rows = _outdoor_rows(None)
    assert {r["orari_fonte"] for r in rows.values()} == {"manuale"}
    assert all(r["ora_inizio"] == "" and r["ora_fine"] == "" for r in rows.values())


def test_start_falling_on_the_previous_day_is_refused():
    # 09:00 save minus 10h would start at 23:00 the day before, contradicting
    # the row's own date → refuse rather than emit a cross-midnight window.
    detail = [{"session_date": "2026-07-19", "created_at": "2026-07-19T07:00:00+00:00",
               "entry": {"duration_minutes": 600}}]
    r = _outdoor_rows(detail)["2026-07-19"]
    assert r["orari_fonte"] == "manuale"
    assert r["ora_inizio"] == ""


def test_zero_or_missing_duration_is_not_a_zero_length_session():
    for bad in (0, None, "molto"):
        detail = [{"session_date": "2026-07-19", "created_at": "2026-07-19T19:54:09+00:00",
                   "entry": {"duration_minutes": bad}}]
        r = _outdoor_rows(detail)["2026-07-19"]
        assert r["orari_fonte"] == "manuale", bad


def test_duplicate_detail_rows_keep_the_earliest_save():
    detail = [
        {"session_date": "2026-07-19", "created_at": "2026-07-19T20:30:00+00:00",
         "entry": {"duration_minutes": 60}},
        {"session_date": "2026-07-19", "created_at": "2026-07-19T19:54:09+00:00",
         "entry": {"duration_minutes": 493}},
    ]
    idx = etl.index_outdoor_details(detail)
    assert idx["2026-07-19"]["duration_minutes"] == 493


def test_a_real_outdoor_timer_still_wins_over_the_save_estimate():
    state = {"session_completion_log": [], "outdoor_log": [
        {"date": "2026-07-19", "spot_name": "Berdorf", "load_score": 40,
         "started_at": "2026-07-19T09:00:00+00:00",
         "finished_at": "2026-07-19T12:00:00+00:00"},
    ]}
    idx = etl.index_outdoor_details(OUTDOOR_DETAIL_ROWS)
    r = etl.build_rows(state, outdoor_details=idx)[0]
    assert r["orari_fonte"] == "timer_reale"
    assert r["ora_inizio"] == "11:00" and r["ora_fine"] == "14:00"
