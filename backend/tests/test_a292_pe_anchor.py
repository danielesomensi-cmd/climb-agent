"""A292 (R6-PE) — lead power-endurance drills anchored to max(OS, RP − 3 half grades).

A climber whose onsight is within 3 half grades of the redpoint gets exactly the
targets of before (the OS stays the anchor); only a wide OS/RP gap moves them.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine.progression_v1 import (
    PE_ANCHOR_GRADE_REF,
    inject_targets,
    lead_pe_anchor,
)
from backend.engine.target_refresh import refresh_edited_session_targets

CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "exercises" / "v1" / "exercises.json"
PE_IDS = ("route_intervals", "route_linked_laps", "route_on_the_minute", "threshold_climbing")


def _catalog():
    return {e["id"]: e for e in json.loads(CATALOG.read_text())["exercises"]}


# A tested baseline (DECISIONS, Global): the derived anchor applies only to
# athletes with a tested official max (< 90 days) on fingers or pulling.
_TESTS = {"max_strength": [{"test_id": "max_hang_7s_total_load", "date": "2026-09-24",
                            "total_load_kg": 110.0, "bodyweight_kg": 70.0}]}


def _state(os_="7a+", rp="8a+", tested=True):
    grades = {"boulder_max_os": "7A", "boulder_max_rp": "7C"}
    if os_ is not None:
        grades["lead_max_os"] = os_
    if rp is not None:
        grades["lead_max_rp"] = rp
    state = {"assessment": {"grades": grades}, "working_loads": {"entries": []}}
    if tested:
        state["tests"] = deepcopy(_TESTS)
    return state


def _day(ex_id, prescription, date="2026-10-20"):
    return {
        "date": date,
        "sessions": [{
            "session_id": "power_endurance_gym",
            "exercise_instances": [{
                "exercise_id": ex_id, "load_model": "grade_relative",
                "prescription": dict(prescription),
            }],
        }],
    }


def _suggested(ex_id, state, prescription=None):
    rx = prescription or _catalog()[ex_id]["prescription_defaults"]
    day = inject_targets(_day(ex_id, rx), state)
    return day["sessions"][0]["exercise_instances"][0].get("suggested") or {}


def test_catalog_pe_drills_use_the_derived_anchor_aerobic_stays_on_os():
    cat = _catalog()
    for ex_id in PE_IDS:
        assert cat[ex_id]["prescription_defaults"]["grade_ref"] == PE_ANCHOR_GRADE_REF
        assert cat[ex_id]["prescription_defaults"]["grade_offset"] == -1  # offsets unchanged
    for ex_id in ("arc_training", "threshold_long_intervals", "one_on_one_off_intervals",
                  "continuity_climbing", "regeneration_climbing"):
        assert cat[ex_id]["prescription_defaults"]["grade_ref"] == "lead_max_os"


@pytest.mark.parametrize("os_,rp,expected", [
    ("7a+", "8a+", ("7C", "lead_max_rp")),   # Daniele today: RP − 3 = 7c beats 7a+
    ("7b", "8a+", ("7C", "lead_max_rp")),    # after the onsight confirmation
    ("7a", "7b", ("7A", "lead_max_os")),     # narrow gap: the OS, as before
    ("7a", "7b+", ("7A", "lead_max_os")),    # exactly 3 half grades: tie → OS
    ("7a", "7c", ("7A+", "lead_max_rp")),
    (None, "8a", ("7B+", "lead_max_rp")),
    ("7a", None, ("7A", "lead_max_os")),
    ("V9", "zz", (None, None)),
])
def test_lead_pe_anchor(os_, rp, expected):
    assert lead_pe_anchor(_state(os_, rp)["assessment"]["grades"]) == expected


def test_daniele_route_intervals_target():
    s = _suggested("route_intervals", _state("7a+", "8a+"))
    # Before A292: lead_max_os 7a+ − 1 letter = 6c+. Now 7c − 1 letter = 7b.
    assert s["suggested_grade"] == "7B"
    assert s["grade_ref"] == PE_ANCHOR_GRADE_REF
    assert s["grade_scale"] == "french"
    assert s["grade_anchor_from"] == "lead_max_rp"


@pytest.mark.parametrize("ex_id", PE_IDS)
@pytest.mark.parametrize("os_,rp", [("7a", "7b"), ("6b+", "7a"), ("7b", "7c"), ("8a", "8b")])
def test_narrow_gap_users_get_exactly_the_old_target(ex_id, os_, rp):
    """Regression: OS within 3 half grades of RP → same grade as the old lead_max_os anchor."""
    state = _state(os_, rp)
    new = _suggested(ex_id, state)
    old = _suggested(ex_id, state, {"grade_ref": "lead_max_os", "grade_offset": -1})
    assert new["suggested_grade"] == old["suggested_grade"]
    assert new["grade_scale"] == old["grade_scale"] == "french"
    assert new["grade_anchor_from"] == "lead_max_os"


@pytest.mark.parametrize("ex_id", PE_IDS)
@pytest.mark.parametrize("os_,rp", [("6a", "7a"), ("7a+", "8a+"), ("7a", "7b"), (None, "8a"), ("7a", "zz")])
def test_untested_users_keep_the_pre_a292_output_bit_for_bit(ex_id, os_, rp):
    """Review fix (DECISIONS, Global): untested athletes — wide gaps included —
    get exactly the old lead_max_os target, same suggested dict."""
    state = _state(os_, rp, tested=False)
    new = _suggested(ex_id, state)
    old = _suggested(ex_id, state, {"grade_ref": "lead_max_os", "grade_offset": -1})
    assert new == old
    assert "grade_anchor_from" not in new


def test_stale_test_is_untested():
    state = _state("6a", "7a")
    state["tests"]["max_strength"][0]["date"] = "2026-05-01"  # > 90 days before 2026-10-20
    assert _suggested("route_intervals", state)["suggested_grade"] == "5C"


def test_tested_wide_gap_uses_the_rp_side():
    s = _suggested("route_intervals", _state("6a", "7a"))
    # RP 7a − 3 half grades = 6b+; − 1 letter = 6a+.
    assert s["suggested_grade"] == "6A+"
    assert s["grade_anchor_from"] == "lead_max_rp"


def test_no_lead_grades_no_target():
    assert "suggested_grade" not in _suggested("route_intervals", _state(None, None))


def test_endurance_memory_still_overrides_the_anchor():
    state = _state("7a+", "8a+")
    state["working_loads"]["entries"].append({
        "exercise_id": "route_intervals", "key": "route_intervals", "setup": {},
        "next_target_grade": "7A", "updated_at": "2026-10-10",
    })
    s = _suggested("route_intervals", state)
    assert s["suggested_grade"] == "7A"
    assert s["grade_source"] == "working_loads"
    assert "grade_anchor_from" not in s


def test_edited_future_session_follows_the_new_anchor():
    """A pencil-edited session resolved before A292 still carries lead_max_os in
    its prescription; the refresh reads the anchor from the catalog."""
    state = _state("7a+", "8a+")
    entry = {
        "session_id": "power_endurance_gym", "status": "pending", "_user_edited": True,
        "resolved": {"resolved_session": {"exercise_instances": [{
            "exercise_id": "route_intervals", "load_model": "grade_relative",
            "prescription": {"grade_ref": "lead_max_os", "grade_offset": -1, "sets": 4},
            "suggested": {"suggested_grade": "6C+", "grade_ref": "lead_max_os",
                          "grade_offset": -1, "grade_scale": "french"},
        }]}},
    }
    before_rx = deepcopy(entry["resolved"]["resolved_session"]["exercise_instances"][0]["prescription"])
    assert refresh_edited_session_targets(entry, "2026-10-12", state, today="2026-10-04")
    inst = entry["resolved"]["resolved_session"]["exercise_instances"][0]
    assert inst["suggested"]["suggested_grade"] == "7B"
    assert inst["suggested"]["grade_anchor_from"] == "lead_max_rp"
    assert inst["prescription"] == before_rx  # the stored prescription is not rewritten


def test_done_session_is_never_refreshed():
    state = _state("7a+", "8a+")
    entry = {
        "session_id": "power_endurance_gym", "status": "done", "_user_edited": True,
        "resolved": {"resolved_session": {"exercise_instances": [{
            "exercise_id": "route_intervals", "load_model": "grade_relative",
            "prescription": {"grade_ref": "lead_max_os", "grade_offset": -1},
            "suggested": {"suggested_grade": "6C+"},
        }]}},
    }
    snapshot = deepcopy(entry)
    assert not refresh_edited_session_targets(entry, "2099-01-05", state, today="2026-10-04")
    assert entry == snapshot
