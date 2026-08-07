"""B324 — `alt_sides` must survive every path that builds an exercise instance.

The catalog marks side-alternating exercises (Copenhagen plank, Pallof press,
side-lying hip abduction…) with `alt_sides: true`; the players read that flag to
double the set count and show the RIGHT/LEFT badge. `resolve_session` propagated
it, but four other builders did not, so the same exercise ran one-sided when it
reached the user through:

  1. POST /api/session/add-exercise  (hand-added to a planned session)
  2. custom sessions                 (session builder → play page → week plan)
  3. adhoc_builder                   (coach ad-hoc, deterministic fallback)
  4. coach/session_composer          (coach ad-hoc, LLM path — the default)

These are pure propagation tests: the source of truth is always the catalog,
never the client and never the model.
"""

import json
from pathlib import Path

import pytest

CATALOG = Path("backend/catalog/exercises/v1/exercises.json")

# Catalog entries this brief was reported against. Guarded so a catalog edit
# that drops the flag fails here rather than silently un-fixing the bug.
LATERAL_IDS = ["copenhagen_plank", "copenhagen_adductor_plank", "pallof_press"]


@pytest.fixture(scope="module")
def catalog_by_id():
    raw = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = raw["exercises"] if isinstance(raw, dict) else raw
    return {e["id"]: e for e in items}


def test_catalog_marks_the_reported_exercises_as_side_alternating(catalog_by_id):
    for ex_id in LATERAL_IDS:
        assert catalog_by_id[ex_id].get("alt_sides") is True, (
            f"{ex_id} must stay alt_sides — it is performed once per side"
        )


# --------------------------------------------------------------------------- #
# 1. POST /api/session/add-exercise
# --------------------------------------------------------------------------- #

def _week_plan_with_resolved_session():
    return {
        "start_date": "2026-01-05",
        "weeks": [{
            "days": [{
                "date": "2026-01-05",
                "weekday": "monday",
                "sessions": [{
                    "slot": "evening",
                    "session_id": "core_training",
                    "location": "home",
                    "intensity": "medium",
                    "tags": {"hard": False, "finger": False},
                    "resolved": {
                        "session_load_score": 10,
                        "resolved_session": {"exercise_instances": []},
                    },
                }],
            }],
        }],
    }


def test_add_exercise_propagates_alt_sides_and_display_fields():
    from fastapi.testclient import TestClient

    from backend.api.main import app

    client = TestClient(app)
    r = client.post("/api/session/add-exercise", json={
        "date": "2026-01-05",
        "session_index": 0,
        "exercise_id": "copenhagen_plank",
        "week_plan": _week_plan_with_resolved_session(),
    })
    assert r.status_code == 200

    day = r.json()["week_plan"]["weeks"][0]["days"][0]
    inst = day["sessions"][0]["resolved"]["resolved_session"]["exercise_instances"][-1]

    assert inst["alt_sides"] is True, "hand-added exercise must keep its laterality"
    # The client reads `name`; `exercise_name` alone left the card showing the id.
    assert inst["name"] == "Copenhagen Plank"
    assert inst["cues"], "cues carry the per-side coaching text"


# --------------------------------------------------------------------------- #
# 2. custom sessions — builder, play page, and the week-plan slot
# --------------------------------------------------------------------------- #

def test_custom_session_enrichment_carries_alt_sides(catalog_by_id):
    """_enrich_exercise_display feeds both GET detail and the week-plan copy."""
    from backend.api.routers.custom_session import _enrich_exercise_display

    enriched = _enrich_exercise_display({"exercise_id": "copenhagen_plank", "sets": 3}, catalog_by_id)
    assert enriched["alt_sides"] is True

    bilateral = _enrich_exercise_display({"exercise_id": "hollow_body_hold", "sets": 3}, catalog_by_id)
    assert bilateral["alt_sides"] is False


def test_custom_session_enrichment_does_not_leak_unilateral(catalog_by_id):
    """`unilateral` drives per-hand load logging (loading-pin only) — the custom
    path has no per-hand suggested loads, so it must NOT be copied."""
    from backend.api.routers.custom_session import _enrich_exercise_display

    enriched = _enrich_exercise_display({"exercise_id": "copenhagen_plank", "sets": 3}, catalog_by_id)
    assert "unilateral" not in enriched


def test_custom_duration_counts_both_sides():
    from backend.engine.custom_session import estimate_custom_session_duration

    one_sided = [{"sets": 3, "work_seconds": 20, "rest_between_sets_seconds": 40}]
    two_sided = [{**one_sided[0], "alt_sides": True}]

    assert estimate_custom_session_duration(two_sided) > estimate_custom_session_duration(one_sided)
    # 6 x 20s work + 5 x 40s rest = 320s → 5 min
    assert estimate_custom_session_duration(two_sided) == 5


# --------------------------------------------------------------------------- #
# 3. + 4. coach ad-hoc — deterministic builder and LLM composer
# --------------------------------------------------------------------------- #

def test_adhoc_builder_line_carries_alt_sides(catalog_by_id):
    from backend.engine.adhoc_builder import _to_custom_exercise

    line = _to_custom_exercise(
        catalog_by_id["copenhagen_plank"], catalog_by_id, {}, "base", "medium", "2026-08-06"
    )
    assert line["alt_sides"] is True

    bilateral = _to_custom_exercise(
        catalog_by_id["core_hollow_hold"], catalog_by_id, {}, "base", "medium", "2026-08-06"
    )
    assert bilateral["alt_sides"] is False


def test_composer_decoration_carries_alt_sides(catalog_by_id):
    """The LLM picks the exercise; laterality comes from the catalog, like load."""
    from backend.coach.session_composer import _decorate_engine_fields

    entries = [
        {"exercise_id": "pallof_press", "sets": 3},
        {"exercise_id": "core_hollow_hold", "sets": 3},
    ]
    _decorate_engine_fields(entries, catalog_by_id, {}, "base", today="2026-08-06")

    assert entries[0]["alt_sides"] is True
    assert entries[1]["alt_sides"] is False


def test_composer_validate_sets_alt_sides_before_the_time_budget_trim(catalog_by_id):
    """validate() trims to the time budget with estimate_custom_session_duration,
    which counts both sides — so the flag must already be on the entry there."""
    from backend.coach.session_composer import validate

    pool = [catalog_by_id["copenhagen_plank"], catalog_by_id["core_hollow_hold"]]
    proposal = {
        "name": "core",
        "rationale": "",
        "exercises": [
            {"exercise_id": "copenhagen_plank", "sets": 3, "work_seconds": 20,
             "rest_between_sets_seconds": 45},
            {"exercise_id": "core_hollow_hold", "sets": 3, "work_seconds": 30,
             "rest_between_sets_seconds": 45},
        ],
    }
    kept, _dropped = validate(proposal, pool, minutes=45)

    by_id = {e["exercise_id"]: e for e in kept}
    assert by_id["copenhagen_plank"]["alt_sides"] is True
    assert by_id["core_hollow_hold"]["alt_sides"] is False
