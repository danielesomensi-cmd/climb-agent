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


# ── A272: archivio, RPE onesto, classificazione dal contenuto ───────────────

def test_archived_week_recovers_load_the_hot_state_no_longer_has():
    """A221 moves past weeks to the cold store; without reading it every
    session older than the hot window exported as load_fonte=unavailable.
    On the real 60-day export that was 18 of 41 completed sessions."""
    state = {
        "session_completion_log": [
            {"date": "2026-06-10", "session_id": "route_endurance_gym", "status": "done",
             "completed_at": "2026-06-10T13:23:00+00:00", "difficulty": "ok",
             "session_duration_seconds": 3600},
        ],
        "week_plans": {},  # hot state has already rolled over
    }
    archived = {
        "2026-06-08": {"start_date": "2026-06-08", "weeks": [{"days": [
            {"date": "2026-06-10", "sessions": [
                {"session_id": "route_endurance_gym", "session_load_score": 48}]},
        ]}]}
    }
    without = etl.build_rows(state)[0]
    assert without["load"] == "" and without["load_fonte"] == "unavailable"
    assert without["rpe_stimato"] == ""

    with_archive = etl.build_rows(state, archived=archived)[0]
    assert with_archive["load"] == 48
    assert with_archive["load_fonte"] == "prescribed"
    assert with_archive["rpe_stimato"] != ""


def test_hot_state_wins_over_the_archive_on_overlap():
    state = {
        "session_completion_log": [
            {"date": "2026-06-10", "session_id": "route_endurance_gym", "status": "done",
             "completed_at": "2026-06-10T13:23:00+00:00"},
        ],
        "week_plans": {"2026-06-08": {"start_date": "2026-06-08", "weeks": [{"days": [
            {"date": "2026-06-10", "sessions": [
                {"session_id": "route_endurance_gym", "session_load_score": 70}]}]}]}},
    }
    archived = {"2026-06-08": {"start_date": "2026-06-08", "weeks": [{"days": [
        {"date": "2026-06-10", "sessions": [
            {"session_id": "route_endurance_gym", "session_load_score": 10}]}]}]}}
    assert etl.build_rows(state, archived=archived)[0]["load"] == 70


def test_no_load_means_no_rpe_even_when_a_difficulty_label_exists():
    """The label alone used to produce an RPE. Since 'ok' is the default and
    appeared on 77 real entries out of 77, that emitted a constant 5 that read
    like a per-session measurement."""
    assert etl.estimate_rpe(None, "ok") == ""
    assert etl.estimate_rpe(None, "hard") == ""
    assert etl.estimate_rpe(None, None) == ""


def test_neutral_difficulty_does_not_drag_the_load_estimate():
    """Blending the neutral label flattened real variation toward 5 — a load of
    78 came out as 7 instead of 9, damping the very signal being correlated."""
    assert etl.estimate_rpe(78, "ok") == etl.estimate_rpe(78, None) == "9"
    assert etl.estimate_rpe(78, "easy") == "7"   # an informative label still moves it


def test_custom_session_typed_from_its_exercises_not_from_the_fallback():
    """A custom session is not in the catalog, so its id is a hash and the
    classifier fell through to 'generic indoor climbing': a treadmill evening
    exported as boulder_indoor with a finger load it never had."""
    exercises = {
        "treadmill_incline_walk": {"domain": ["aerobic_capacity"], "role": ["conditioning"],
                                   "time_min": 30, "equipment_required": []},
        "pallof_press": {"domain": ["core"], "role": ["accessory"], "time_min": 8,
                         "equipment_required": []},
        "dynamic_mobility_flow": {"domain": ["mobility"], "role": ["warmup"], "time_min": 5,
                                  "equipment_required": []},
    }
    session = {"id": "cs_x", "name": "Work — cardio montagna + core easy", "exercises": [
        {"exercise_id": "dynamic_mobility_flow"}, {"exercise_id": "treadmill_incline_walk"},
        {"exercise_id": "pallof_press"},
    ]}
    tipo, carico = etl.classify_custom_session(session, exercises)
    assert tipo == "cardio"
    assert carico == ""   # no finger work: say nothing rather than guess "medio"


def test_custom_session_wins_for_the_wall_when_climbing_is_present():
    exercises = {
        "boulder_4x4": {"domain": ["power_endurance"], "role": ["main"], "time_min": 30,
                        "equipment_required": ["gym_boulder"]},
        "bench_press": {"domain": ["strength_general"], "role": ["accessory"], "time_min": 40,
                        "equipment_required": ["weight"]},
    }
    session = {"id": "cs_y", "name": "misto", "exercises": [
        {"exercise_id": "bench_press"}, {"exercise_id": "boulder_4x4"},
    ]}
    tipo, _ = etl.classify_custom_session(session, exercises)
    assert tipo == "boulder_indoor"   # even though the weights hold more minutes


def test_outdoor_double_submit_collapses_but_two_real_sessions_survive():
    twin = {"date": "2026-07-07", "spot_name": "Berdorf", "discipline": "lead",
            "load_score": 20, "completed_at": "2026-07-08T16:35:13+00:00"}
    copy = {**twin, "completed_at": "2026-07-08T16:35:22+00:00"}    # 9s later
    later = {**twin, "completed_at": "2026-07-08T21:10:00+00:00"}   # hours later
    kept, dropped = etl.dedupe_outdoor([twin, copy])
    assert len(kept) == 1 and len(dropped) == 1
    kept2, dropped2 = etl.dedupe_outdoor([twin, later])
    assert len(kept2) == 2 and not dropped2


def test_skipped_session_carries_no_times():
    """completed_at on a skip is when the skip was tapped: three separate days
    skipped in one sitting all exported carrying the same 19:37."""
    state = {"session_completion_log": [
        {"date": "2026-07-24", "session_id": "prehab_maintenance", "status": "skipped",
         "completed_at": "2026-07-26T19:37:00+00:00"},
    ]}
    row = etl.build_rows(state)[0]
    assert row["ora_inizio"] == "" and row["ora_fine"] == ""
    assert row["orari_fonte"] == "manuale"
