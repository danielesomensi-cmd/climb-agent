"""B414 (step 14, INBOX-2026-11-02-b) — the sub-max hangs sort as finger endurance.

The six hangs whose first domain is ``finger_aerobic_endurance``
(``sub_max_capacity_hang``, ``repeater_sub_max_endurance``,
``intermittent_dead_hangs``, ``long_interval_repeaters``, ``bar_dead_hang``,
``long_duration_hang``) were ``aerobic_pure`` for ``exercise_ordering``, so
constraint 3 ("ARC before pump") moved them BEFORE the PE intervals in
``exercise_instances`` — against the catalog's "submaximal repeaters
post-climbing" (the player follows the blocks and never showed it; the API
list, the coach and the feedback dialog did). Now they are
``finger_endurance``; the ARC on the wall (``aerobic_capacity``) stays
``aerobic_pure``. A pure reorder: no exercise lost or added.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.engine.exercise_ordering import (
    enforce_ordering_constraints,
    infer_sort_category,
    sort_exercises_by_phase,
)
from backend.tests import b413_lunch_golden_cases as lg
from backend.tests import c272_golden_cases as golden

REPO = Path(__file__).resolve().parents[2]
SUB_MAX_HANGS = ("sub_max_capacity_hang", "repeater_sub_max_endurance", "intermittent_dead_hangs",
                 "long_interval_repeaters", "bar_dead_hang", "long_duration_hang")
COCQUE_LIKE = ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"]


@pytest.fixture(scope="module")
def catalog() -> dict:
    data = json.loads((REPO / "backend/catalog/exercises/v1/exercises.json").read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


def test_the_six_finger_aerobic_hangs_are_finger_endurance(catalog):
    found = sorted(e["id"] for e in catalog.values() if (e.get("domain") or [None])[0] == "finger_aerobic_endurance")
    assert found == sorted(SUB_MAX_HANGS)
    for eid in SUB_MAX_HANGS:
        assert infer_sort_category({"exercise_id": eid}, catalog) == "finger_endurance", eid


def test_the_arc_stays_aerobic_pure(catalog):
    assert infer_sort_category({"exercise_id": "arc_training"}, catalog) == "aerobic_pure"
    # a finger-aerobic entry that is not a hang (none today) stays aerobic
    assert infer_sort_category({"role": ["main"], "domain": ["finger_aerobic_endurance"],
                                "pattern": "climbing_continuous"}) == "aerobic_pure"
    # a warm-up role still wins over the domain
    assert infer_sort_category({"role": ["warmup"], "domain": ["finger_aerobic_endurance"],
                                "pattern": "hang"}) == "warmup"


@pytest.mark.parametrize("phase", ["base", "strength_power", "power_endurance", "performance", "deload"])
def test_pure_reorder(phase, catalog):
    rows = [{"exercise_id": eid} for eid in ("intermittent_dead_hangs", "linked_boulders", "route_intervals",
                                             "arc_training", "general_pulse_raise", "bar_dead_hang")]
    out = enforce_ordering_constraints(sort_exercises_by_phase(rows, phase, catalog), phase, catalog)
    assert sorted(r["exercise_id"] for r in out) == sorted(r["exercise_id"] for r in rows)


def _pe_state(profile: str, date: str) -> dict:
    if profile == "daniele":
        st = lg.daniele_state(date)
        st["equipment"]["gyms"][-1]["equipment"] = list(COCQUE_LIKE)
        return st
    st = copy.deepcopy(golden.profiles()["untested"])
    st["equipment"]["gyms"].append({"gym_id": "cq", "priority": 1, "equipment": list(COCQUE_LIKE)})
    st["context"] = {"location": "gym", "gym_id": "cq", "target_date": date, "date": date}
    return st


@pytest.mark.parametrize("profile", ["daniele", "untested"])
def test_pe_session_hangs_after_the_intervals(profile, catalog):
    """The 02/11 case: power_endurance_gym in the PE phase lists the sub-max
    hangs after the last PE interval (Cocque: linked boulders, route
    intervals, intermittent dead hangs)."""
    r = lg._resolve("power_endurance_gym", _pe_state(profile, "2026-10-27"), "power_endurance")
    insts = r["resolved_session"]["exercise_instances"]
    cats = [infer_sort_category(i, catalog) for i in insts]
    hangs = [k for k, i in enumerate(insts) if i["source"]["block_id"] == "finger_endurance"]
    pe = [k for k, c in enumerate(cats) if c == "pe_intervals"]
    assert hangs and pe, [i["exercise_id"] for i in insts]
    assert min(hangs) > max(pe), [i["exercise_id"] for i in insts]
    if profile == "daniele":
        assert insts[hangs[0]]["exercise_id"] == "intermittent_dead_hangs"
