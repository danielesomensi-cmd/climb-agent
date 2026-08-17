"""B333 — the composer pool ceiling must not act as a selection policy.

Found by the D278 code review. `MAX_POOL` was 120 while the admissible set is
162 at home and 139 at the gym, and `build_pool` sorts by id before cutting —
so the ceiling silently removed the same tail of the alphabet every time. The
user-visible result: "core at home" could not return the core, and the cardio
C266 added to the catalog was unreachable for the coach.

The assertions below are deliberately written against the REAL catalog rather
than a fixture. A fixture would have passed happily while production was broken:
the defect only exists at the real catalog's size.
"""

import json
import logging
from pathlib import Path

import pytest

from backend.coach import session_composer as sc

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

# Exercises that the 120 ceiling made unreachable. Every one of them sorts past
# the old cut-off, which is exactly why they are the regression: they are not
# rare, they are late in the alphabet.
PREVIOUSLY_INVISIBLE = [
    "side_plank",
    "v_up",
    "toes_to_bar",
    "wall_handstand_hold",
    "weighted_pullup",
    "treadmill_incline_walk",
    "stationary_bike_zone2",
]


@pytest.fixture(scope="module")
def catalog():
    return {e["id"]: e for e in json.loads(CATALOG.read_text())["exercises"]}


@pytest.fixture
def state():
    return {
        "equipment": {
            "home": [
                "hangboard", "pullup_bar", "dumbbell", "band",
                "resistance_band", "loading_pin",
            ],
            "home_enabled": True,
            "gyms": [
                {
                    "gym_id": "g1",
                    "name": "Work",
                    "equipment": [
                        "barbell", "cable_machine", "leg_press", "bench",
                        "dumbbell", "pullup_bar", "weight", "resistance_band",
                        "rings", "ab_wheel", "foam_roller",
                    ],
                }
            ],
        }
    }


def _pool(mode, state, catalog):
    intent = {"equipment_set": mode}
    if mode == "gym":
        intent["gym_name"] = "Work"
    return sc.build_pool(intent, state, catalog)


@pytest.mark.parametrize("mode", ["home", "gym", "bodyweight"])
def test_ceiling_does_not_bite_on_the_real_catalog(mode, state, catalog):
    """The ceiling is a backstop, not a filter — today it must not engage."""
    pool = _pool(mode, state, catalog)
    assert len(pool) < sc.MAX_POOL, (
        f"{mode}: the pool fills the ceiling ({len(pool)}/{sc.MAX_POOL}), so the "
        "tail of the id sort is being dropped as a policy. Raise MAX_POOL."
    )


@pytest.mark.parametrize("exercise_id", PREVIOUSLY_INVISIBLE)
def test_late_alphabet_exercises_are_selectable(exercise_id, state, catalog):
    """The concrete user-facing regression, one exercise per case."""
    reachable = {e["id"] for e in _pool("home", state, catalog)} | {
        e["id"] for e in _pool("gym", state, catalog)
    }
    assert exercise_id in reachable, (
        f"{exercise_id} is admissible but the model can never see it"
    )


def test_core_request_can_actually_return_core(state, catalog):
    """'Core at home' was the clearest casualty: all four sorted past the cut."""
    home = {e["id"] for e in _pool("home", state, catalog)}
    for eid in ("side_plank", "v_up", "toes_to_bar", "windshield_wipers"):
        assert eid in home, f"{eid} unreachable — core requests stay impoverished"


def test_c266_cardio_is_reachable(state, catalog):
    """C266 added steady-state cardio because it was missing; two of the three
    sorted past 120, so the composer could not propose them."""
    home = {e["id"] for e in _pool("home", state, catalog)}
    assert {"treadmill_incline_walk", "stationary_bike_zone2"} <= home


def test_truncation_is_logged_when_it_happens(monkeypatch, state, catalog, caplog):
    """The day the catalog outgrows the ceiling must be noticed, not guessed at.

    The old code had a warning for a pool that was too SMALL and no symmetric
    branch, so an impoverished pool looked healthy in the logs — and the
    deterministic fallback never fires, because the pool stays far above
    MIN_EXERCISES.
    """
    monkeypatch.setattr(sc, "MAX_POOL", 10)
    with caplog.at_level(logging.WARNING, logger=sc.logger.name):
        pool = _pool("home", state, catalog)
    assert len(pool) == 10
    assert any("pool truncated" in r.message for r in caplog.records), (
        "the ceiling engaged without saying so"
    )


def test_pool_is_deterministic(state, catalog):
    """Same state, same pool — the sort exists for this and must stay."""
    a = [e["id"] for e in _pool("home", state, catalog)]
    b = [e["id"] for e in _pool("home", state, catalog)]
    assert a == b
