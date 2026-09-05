"""A281 — the trip taper: cut volume, hold intensity, and stop the leak.

Before this brief the only thing that happened before a trip was a 6-day window
in which PASS 1 refused to place hard/max sessions — the opposite of what the
evidence supports, and enforced in exactly one of the planner's nine placement
sites.

Bosquet et al. 2007 (meta-analysis, Med Sci Sports Exerc): an effective taper
removes 41-60% of the VOLUME and holds intensity and frequency constant
(ES 0.72 ± 0.36). So A281 splits it in two:

* a volume ramp over the two weeks before departure (0.6 then 0.4), applied to
  the sets of training work only;
* a 3-day no-hard window immediately before the flight — kept because Bosquet
  studied endurance athletes peaking for a race day, not climbers about to
  spend two weeks on rock, and maximal finger loading 48h before travelling is
  a tendon risk the meta-analysis says nothing about.

It also closes B-PRETRIP-PASS1-ONLY: reproduced on Daniele's real state, PASS
2.6 placed `finger_strength_home` (hard, intensity high) on 2026-08-18 — a day
the planner itself had flagged `pretrip_deload: True`, 48h before Kalymnos.
"""

import pytest

from backend.api.routers.week import _apply_taper_volume
from backend.engine.macrocycle_v1 import (
    TAPER_NO_HARD_DAYS,
    TAPER_WEEK1_VOLUME,
    TAPER_WEEK2_VOLUME,
    compute_taper_windows,
)
from backend.engine.planner_v2 import generate_phase_week


# ─── compute_taper_windows ───────────────────────────────────────────────────

TRIP = [{"name": "Kalymnos", "start_date": "2026-10-19", "end_date": "2026-11-02"}]


def test_second_week_before_the_trip_cuts_volume_hardest():
    """Days T-7..T-1 → 0.4 (i.e. -60% volume, the top of Bosquet's band)."""
    out = compute_taper_windows(TRIP, "2026-10-12", "2026-10-18")
    assert set(out["volume"].values()) == {TAPER_WEEK2_VOLUME}
    assert len(out["volume"]) == 7


def test_first_week_before_the_trip_cuts_less():
    """Days T-14..T-8 → 0.6 (-40%)."""
    out = compute_taper_windows(TRIP, "2026-10-05", "2026-10-11")
    assert set(out["volume"].values()) == {TAPER_WEEK1_VOLUME}


def test_three_weeks_out_is_not_tapered():
    out = compute_taper_windows(TRIP, "2026-09-28", "2026-10-04")
    assert out["volume"] == {}
    assert out["no_hard"] == []


def test_no_hard_window_is_three_days_ending_on_departure():
    out = compute_taper_windows(TRIP, "2026-10-12", "2026-10-19")
    assert out["no_hard"] == ["2026-10-17", "2026-10-18", "2026-10-19"]
    assert len(out["no_hard"]) == TAPER_NO_HARD_DAYS


def test_departure_day_itself_is_never_a_hard_day():
    out = compute_taper_windows(TRIP, "2026-10-19", "2026-10-25")
    assert "2026-10-19" in out["no_hard"]


def test_departure_day_carries_no_volume_multiplier():
    """The trip day is travel, not a training day to scale."""
    out = compute_taper_windows(TRIP, "2026-10-19", "2026-10-25")
    assert "2026-10-19" not in out["volume"]


def test_no_trips_means_no_taper():
    out = compute_taper_windows([], "2026-10-12", "2026-10-18")
    assert out == {"volume": {}, "no_hard": []}


@pytest.mark.parametrize("trips", [
    [{"name": "broken"}],                       # no start_date
    [{"name": "broken", "start_date": None}],
    [{"name": "broken", "start_date": "not-a-date"}],
])
def test_malformed_trips_are_skipped_not_raised(trips):
    assert compute_taper_windows(trips, "2026-10-12", "2026-10-18") == {"volume": {}, "no_hard": []}


def test_overlapping_trips_take_the_stronger_taper():
    """Two trips over one date → the nearer one wins (lower multiplier)."""
    trips = [
        {"name": "far", "start_date": "2026-10-26"},   # 2026-10-15 is T-11 → 0.6
        {"name": "near", "start_date": "2026-10-19"},  # 2026-10-15 is T-4  → 0.4
    ]
    out = compute_taper_windows(trips, "2026-10-12", "2026-10-18")
    assert out["volume"]["2026-10-15"] == TAPER_WEEK2_VOLUME


# ─── planner: the no-hard sweep (B-PRETRIP-PASS1-ONLY) ───────────────────────

def _kwargs(**over):
    kwargs = dict(
        phase_id="strength_power",
        domain_weights={"finger_strength": 0.3, "pulling_strength": 0.2, "technique": 0.2,
                        "volume_climbing": 0.15, "power_endurance": 0.1, "core_prehab": 0.05},
        session_pool=["finger_strength_home", "strength_long", "pulling_strength_gym",
                      "limit_boulder_gym", "prehab_maintenance", "flexibility_full",
                      "technique_focus_gym", "core_training"],
        start_date="2026-10-12",
        availability={d: {"evening": {"available": True, "preferred_location": "home"}}
                      for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        home_equipment=["hangboard", "pullup_bar", "dumbbell"],
        allowed_locations=["home"],
    )
    kwargs.update(over)
    return kwargs


ALL_WEEK = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15",
            "2026-10-16", "2026-10-17", "2026-10-18"]


def test_no_hard_session_survives_anywhere_in_the_window():
    """The invariant the old PASS-1-only gate could not hold.

    PASS 2.5 and PASS 2.6 both place sessions after PASS 1 has had its say —
    2.6 is the one that put `finger_strength_home` 48h before Kalymnos.
    """
    plan = generate_phase_week(**_kwargs(pretrip_dates=ALL_WEEK))
    for day in plan["weeks"][0]["days"]:
        for session in day.get("sessions", []):
            assert not (session.get("tags") or {}).get("hard"), (
                f"hard session {session['session_id']} on no-hard day {day['date']}"
            )
            assert session.get("intensity") != "max"


def test_pass26_pulling_guarantee_cannot_break_the_window():
    """B308's pulling guarantee must yield to the taper, not override it."""
    plan = generate_phase_week(**_kwargs(
        pretrip_dates=ALL_WEEK,
        session_pool=["pulling_strength_gym", "finger_strength_home", "prehab_maintenance"],
    ))
    placed = [s["session_id"] for d in plan["weeks"][0]["days"] for s in d.get("sessions", [])]
    assert "pulling_strength_gym" not in placed
    assert "finger_strength_home" not in placed


def test_days_outside_the_window_keep_their_hard_sessions():
    """The sweep must not become a blanket ban."""
    plan = generate_phase_week(**_kwargs(pretrip_dates=["2026-10-18"]))
    hard = [s for d in plan["weeks"][0]["days"] for s in d.get("sessions", [])
            if (s.get("tags") or {}).get("hard")]
    assert hard, "the week lost every hard session — the sweep is over-reaching"


def test_no_pretrip_dates_changes_nothing():
    assert generate_phase_week(**_kwargs()) == generate_phase_week(**_kwargs(pretrip_dates=None))


# ─── planner: the volume multiplier travels on the day ───────────────────────

def test_multiplier_is_stamped_on_the_day():
    plan = generate_phase_week(**_kwargs(
        taper_volume={d: TAPER_WEEK2_VOLUME for d in ALL_WEEK}))
    for day in plan["weeks"][0]["days"]:
        assert day["taper_volume_multiplier"] == TAPER_WEEK2_VOLUME


def test_no_multiplier_field_without_a_taper():
    plan = generate_phase_week(**_kwargs())
    for day in plan["weeks"][0]["days"]:
        assert "taper_volume_multiplier" not in day


def test_multiplier_of_one_is_not_stamped():
    """1.0 is 'no taper' — the field must stay absent rather than say nothing."""
    plan = generate_phase_week(**_kwargs(taper_volume={d: 1.0 for d in ALL_WEEK}))
    for day in plan["weeks"][0]["days"]:
        assert "taper_volume_multiplier" not in day


def test_planner_stays_deterministic_under_a_taper():
    kwargs = _kwargs(pretrip_dates=["2026-10-17", "2026-10-18"],
                     taper_volume={d: TAPER_WEEK2_VOLUME for d in ALL_WEEK})
    assert generate_phase_week(**kwargs) == generate_phase_week(**kwargs)


# ─── _apply_taper_volume ─────────────────────────────────────────────────────

def _resolved(instances):
    return {"resolved_session": {"exercise_instances": instances}}


def _inst(exercise_id, sets, **extra):
    return {"exercise_id": exercise_id, "prescription": {"sets": sets}, **extra}


def test_training_sets_are_scaled():
    r = _resolved([_inst("max_hang_7s", 5)])          # role: main
    _apply_taper_volume(r, 0.4)
    p = r["resolved_session"]["exercise_instances"][0]["prescription"]
    assert p["sets"] == 2
    assert p["taper_scaled_from"] == 5


def test_warmup_and_cooldown_are_never_scaled():
    """Cutting the warmup in a high-intensity taper week is the opposite of the point."""
    r = _resolved([_inst("general_pulse_raise", 3),      # warmup
                   _inst("cooldown_spinal_twist", 3)])   # cooldown
    _apply_taper_volume(r, 0.4)
    for inst in r["resolved_session"]["exercise_instances"]:
        assert inst["prescription"]["sets"] == 3
        assert "taper_scaled_from" not in inst["prescription"]


def test_prehab_is_never_scaled():
    r = _resolved([_inst("finger_extensor_band", 3)])
    _apply_taper_volume(r, 0.4)
    assert r["resolved_session"]["exercise_instances"][0]["prescription"]["sets"] == 3


def test_never_goes_below_one_set():
    """Frequency is what a taper must HOLD — a zero-set session is a missing one."""
    r = _resolved([_inst("limit_bouldering", 2)])
    _apply_taper_volume(r, 0.1)
    assert r["resolved_session"]["exercise_instances"][0]["prescription"]["sets"] == 1


def test_single_set_work_is_left_alone():
    r = _resolved([_inst("limit_bouldering", 1)])
    _apply_taper_volume(r, 0.4)
    assert "taper_scaled_from" not in r["resolved_session"]["exercise_instances"][0]["prescription"]


def test_user_added_exercises_are_left_alone():
    r = _resolved([_inst("max_hang_7s", 5, source="user_added")])
    _apply_taper_volume(r, 0.4)
    assert r["resolved_session"]["exercise_instances"][0]["prescription"]["sets"] == 5


def test_unknown_exercise_is_still_scaled_but_does_not_raise():
    r = _resolved([_inst("no_such_exercise", 4)])
    _apply_taper_volume(r, 0.5)
    assert r["resolved_session"]["exercise_instances"][0]["prescription"]["sets"] == 2


def test_malformed_instances_do_not_raise():
    r = _resolved([{"exercise_id": "max_hang_7s"},
                   {"exercise_id": "max_hang_7s", "prescription": None},
                   {"exercise_id": "max_hang_7s", "prescription": {"sets": None}}])
    _apply_taper_volume(r, 0.4)  # must not raise


def test_loads_and_grades_are_untouched():
    """Intensity is exactly what a taper must NOT reduce."""
    r = _resolved([{
        "exercise_id": "max_hang_7s",
        "prescription": {"sets": 5, "load_kg": 45.0, "intensity_pct_of_total_load": 0.9},
    }])
    _apply_taper_volume(r, 0.4)
    p = r["resolved_session"]["exercise_instances"][0]["prescription"]
    assert p["load_kg"] == 45.0
    assert p["intensity_pct_of_total_load"] == 0.9


def test_a_real_test_session_is_exempt_as_a_whole():
    """`max_hang_7s` is role ["main","test"]: tapered in training, never in a test.

    An allow-list on training roles is what makes this possible — a deny-list on
    "test" would have exempted max hangs from the taper everywhere, which is the
    single kind of work that most needs it.
    """
    r = _resolved([_inst("max_hang_7s", 5)])
    _apply_taper_volume(r, 0.4, is_test_session=True)
    assert r["resolved_session"]["exercise_instances"][0]["prescription"]["sets"] == 5

    r2 = _resolved([_inst("max_hang_7s", 5)])
    _apply_taper_volume(r2, 0.4, is_test_session=False)
    assert r2["resolved_session"]["exercise_instances"][0]["prescription"]["sets"] == 2


def test_scaling_is_idempotent_against_a_fresh_resolve():
    """resolve_session rebuilds from the catalog, so scaling never compounds."""
    first = _resolved([_inst("max_hang_7s", 5)])
    _apply_taper_volume(first, 0.4)
    second = _resolved([_inst("max_hang_7s", 5)])   # what a re-resolve produces
    _apply_taper_volume(second, 0.4)
    assert (first["resolved_session"]["exercise_instances"][0]["prescription"]["sets"]
            == second["resolved_session"]["exercise_instances"][0]["prescription"]["sets"])
