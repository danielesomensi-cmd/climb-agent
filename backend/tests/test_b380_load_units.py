"""B380 — explicit load units (per dumbbell / implement / total).

What a kg number counts is a catalog field (``load_unit``). The barbell and
dumbbell variants of the same movement convert with a plain ÷2 / ×2 on the
whole load, rounded to 0.5 kg, in both directions; progression stays
percentage-based and never looks at the unit.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine import load_units as lu
from backend.engine import progression_v1 as pv
from backend.engine.equipment_utils import expand_equipment
from backend.engine.progression_v1 import apply_feedback, inject_targets
from backend.engine.resolve_session import _pin_equipment_ok

REPO = Path(__file__).resolve().parents[2]
CATALOG = {
    e["id"]: e
    for e in json.loads((REPO / "backend/catalog/exercises/v1/exercises.json").read_text(encoding="utf-8"))["exercises"]
}
DAY = "2026-10-17"


def _state(entries=None) -> dict:
    return {
        "bodyweight_kg": 77.0,
        "working_loads": {
            "entries": list(entries or []),
            "rules": {
                "adjustment_policy": {
                    "very_easy": {"pct_range": [0.1, 0.2]},
                    "easy": {"pct_range": [0.05, 0.1]},
                    "ok": {"pct_range": [0.0, 0.05]},
                    "hard": {"pct_range": [-0.05, 0.0]},
                    "very_hard": {"pct_range": [-0.15, -0.05]},
                },
            },
        },
    }


def _entry(ex_id: str, kg: float, date: str = "2026-10-10") -> dict:
    return {"exercise_id": ex_id, "key": ex_id, "setup": {}, "next_external_load_kg": kg,
            "last_external_load_kg": kg, "last_feedback_label": "ok", "updated_at": date}


def _suggested(state: dict, ex_id: str) -> dict:
    day = {"date": DAY, "sessions": [{"session_id": "upper_push_arms_lunch", "intent": "strength",
                                      "location": "gym", "gym_id": None, "tags": {},
                                      "exercise_instances": [{"exercise_id": ex_id,
                                                              "prescription": {"sets": 4, "reps": 6}}]}]}
    return inject_targets(day, state)["sessions"][0]["exercise_instances"][0]["suggested"]


# ── conversion ────────────────────────────────────────────────────────────────

class TestConversion:
    def test_total_to_per_dumbbell_and_back(self):
        assert lu.convert_load(70, lu.TOTAL, lu.PER_DUMBBELL) == 35.0
        assert lu.convert_load(35, lu.PER_DUMBBELL, lu.TOTAL) == 70.0
        assert lu.convert_load(34, lu.PER_DUMBBELL, lu.TOTAL) == 68.0

    def test_rounded_to_half_kilo(self):
        assert lu.convert_load(61, lu.TOTAL, lu.PER_DUMBBELL) == 30.5
        assert lu.convert_load(61.5, lu.TOTAL, lu.PER_DUMBBELL) == 31.0  # 30.75 → 31.0
        assert lu.convert_load(30.5, lu.PER_DUMBBELL, lu.TOTAL) == 61.0

    def test_implement_and_total_are_not_doubled(self):
        assert lu.convert_load(12, lu.IMPLEMENT, lu.TOTAL) == 12.0
        assert lu.convert_load(12, lu.TOTAL, lu.IMPLEMENT) == 12.0

    def test_missing_or_unknown_unit_is_total(self):
        assert lu.load_unit_of({}) == lu.TOTAL
        assert lu.load_unit_of(None) == lu.TOTAL
        assert lu.normalize_load_unit("per_hand") == lu.TOTAL

    def test_pairs_are_bidirectional(self):
        assert lu.BARBELL_DUMBBELL_PAIRS["bench_press"] == "dumbbell_bench_press"
        assert lu.BARBELL_DUMBBELL_PAIRS["dumbbell_bench_press"] == "bench_press"
        assert lu.BARBELL_DUMBBELL_PAIRS["barbell_row"] == "dumbbell_row"
        assert lu.BARBELL_DUMBBELL_PAIRS["dumbbell_row"] == "barbell_row"


# ── transfer through inject_targets (Daniele's numbers) ──────────────────────

class TestTransfer:
    def test_bench_70_gives_dumbbell_bench_35_per_dumbbell(self):
        sug = _suggested(_state([_entry("bench_press", 70.0)]), "dumbbell_bench_press")
        assert sug["suggested_external_load_kg"] == 35.0
        assert sug["load_source"] == "transferred"
        assert sug["load_unit"] == "per_dumbbell"

    def test_dumbbell_bench_34_gives_bench_68_total(self):
        sug = _suggested(_state([_entry("dumbbell_bench_press", 34.0)]), "bench_press")
        assert sug["suggested_external_load_kg"] == 68.0
        assert sug["load_source"] == "transferred"
        assert "load_unit" not in sug  # total: the pre-B380 reading, no field

    def test_row_transfers_both_ways(self):
        assert _suggested(_state([_entry("barbell_row", 61.0)]), "dumbbell_row")["suggested_external_load_kg"] == 30.5
        assert _suggested(_state([_entry("dumbbell_row", 30.5)]), "barbell_row")["suggested_external_load_kg"] == 61.0

    def test_own_load_wins_over_transfer(self):
        sug = _suggested(_state([_entry("bench_press", 70.0), _entry("dumbbell_bench_press", 30.0)]),
                         "dumbbell_bench_press")
        assert sug["suggested_external_load_kg"] == 30.0
        assert "load_source" not in sug

    def test_stale_donor_does_not_transfer(self):
        sug = _suggested(_state([_entry("bench_press", 70.0, date="2026-01-01")]), "dumbbell_bench_press")
        assert sug.get("load_source") != "transferred"

    def test_coherence_compares_whole_loads(self):
        st = _state([_entry("bench_press", 70.0), _entry("dumbbell_bench_press", 35.0)])
        assert pv.check_load_coherence(st, DAY) == []


# ── cold start ────────────────────────────────────────────────────────────────

class TestColdStart:
    @pytest.mark.parametrize("ex_id", ["bicep_curl", "hammer_curl"])
    @pytest.mark.parametrize("bw,expected", [(78.0, 18.0), (55.0, 12.5)])
    def test_curls_cold_start_per_dumbbell_scaled_to_bodyweight(self, ex_id, bw, expected):
        # Daniele (78 kg) gets the 18 kg he asked for; a 55 kg athlete is not handed his number.
        st = _state()
        st["bodyweight_kg"] = bw
        sug = _suggested(st, ex_id)
        assert sug["suggested_external_load_kg"] == expected
        assert sug["load_unit"] == "per_dumbbell"

    def test_per_dumbbell_fallback_is_at_most_half_the_barbell_one(self):
        pct = pv.EXTERNAL_LOAD_FALLBACK_PCT_BW
        assert pct["dumbbell_bench_press"] <= pct["bench_press"] / 2
        assert pct["dumbbell_row"] <= pct["barbell_row"] / 2
        sc = pv.PULLING_EXTERNAL_SCALING
        assert sc["dumbbell_row"] <= sc["barbell_row"] / 2

    def test_dumbbell_bench_cold_start_is_per_dumbbell(self):
        # 77 kg × 0.17 = 13.09 → 13.0 per dumbbell (it was 0.34 = 26 kg "per hand").
        assert _suggested(_state(), "dumbbell_bench_press")["suggested_external_load_kg"] == 13.0


# ── progression is unit-agnostic ─────────────────────────────────────────────

class TestProgressionUnchanged:
    @pytest.mark.parametrize("label,expected,dumbbell", [("easy", 36.5, 36.0), ("hard", 33.0, 32.0),
                                                         ("ok", 34.0, 34.0)])
    def test_feedback_step_on_a_per_dumbbell_load(self, label, expected, dumbbell):
        # Same percentage as a total exercise (rounded to 0.5 there); since B409
        # a per-dumbbell load then lands on the 2 kg dumbbell grid.
        st = _state([_entry("dumbbell_bench_press", 34.0)])
        log = {"date": DAY,
               "planned": [{"exercise_instances": [{"exercise_id": "dumbbell_bench_press", "prescription": {}}]}],
               "actual": {"exercise_feedback_v1": [{"exercise_id": "dumbbell_bench_press", "completed": True,
                                                    "feedback_label": label, "used_external_load_kg": 34.0}]}}
        out = apply_feedback(log, st)
        e = next(x for x in out["working_loads"]["entries"] if x["exercise_id"] == "dumbbell_bench_press")
        assert e["next_external_load_kg"] == dumbbell
        # And the same percentage on a TOTAL exercise, on the 0.5 kg rounding.
        st2 = _state([_entry("bench_press", 34.0)])
        log2 = deepcopy(log)
        log2["planned"][0]["exercise_instances"][0]["exercise_id"] = "bench_press"
        log2["actual"]["exercise_feedback_v1"][0]["exercise_id"] = "bench_press"
        out2 = apply_feedback(log2, st2)
        e2 = next(x for x in out2["working_loads"]["entries"] if x["exercise_id"] == "bench_press")
        assert e2["next_external_load_kg"] == expected

    def test_existing_load_is_read_as_is(self):
        assert _suggested(_state([_entry("dumbbell_bench_press", 34.0)]),
                          "dumbbell_bench_press")["suggested_external_load_kg"] == 34.0


# ── equipment: the barbell bench needs a barbell ─────────────────────────────

class TestBenchNeedsABarbell:
    def test_bench_press_is_not_doable_with_dumbbells_only(self):
        dumbbells_only = expand_equipment(["dumbbell", "bench", "cable_machine"])
        assert not _pin_equipment_ok(CATALOG["bench_press"], dumbbells_only)
        assert _pin_equipment_ok(CATALOG["dumbbell_bench_press"], dumbbells_only)

    def test_plates_alone_do_not_make_a_barbell(self):
        assert not _pin_equipment_ok(CATALOG["bench_press"], expand_equipment(["weight", "bench"]))
        assert not _pin_equipment_ok(CATALOG["barbell_row"], expand_equipment(["weight", "dumbbell"]))

    def test_bench_and_row_need_a_real_barbell(self):
        work = expand_equipment(["barbell", "bench", "dumbbell", "cable_machine"])
        assert _pin_equipment_ok(CATALOG["bench_press"], work)
        assert _pin_equipment_ok(CATALOG["barbell_row"], work)
        assert _pin_equipment_ok(CATALOG["dumbbell_row"], work)

    def test_dumbbell_row_is_a_sibling_of_barbell_row(self):
        b, d = CATALOG["barbell_row"], CATALOG["dumbbell_row"]
        for k in ("pattern", "domain", "role", "recency_group", "load_model", "category", "intensity_level"):
            assert b[k] == d[k], k
        assert d["equipment_required"] == ["dumbbell", "bench"]
        assert b["equipment_required"] == ["barbell"]


# ── catalog invariant ─────────────────────────────────────────────────────────

def _uses_dumbbell(e: dict) -> bool:
    eq = set(e.get("equipment_required") or []) | set(e.get("equipment_required_any") or [])
    return "dumbbell" in eq or "dumbbell" in e["id"] or "dumbbell" in (e.get("name") or "").lower()


class TestCatalogInvariant:
    def test_every_load_unit_is_valid(self):
        for e in CATALOG.values():
            if "load_unit" in e:
                assert e["load_unit"] in lu.LOAD_UNITS, e["id"]

    def test_every_loaded_dumbbell_exercise_declares_its_unit(self):
        missing = [e["id"] for e in CATALOG.values()
                   if e.get("load_model") in ("external_load", "total_load") and _uses_dumbbell(e)
                   and e.get("load_unit") not in lu.LOAD_UNITS]
        assert missing == []

    def test_every_external_load_exercise_declares_its_unit(self):
        # Loading-pin lifts are per hand by their own L/R path — not this field.
        missing = [e["id"] for e in CATALOG.values()
                   if e.get("load_model") == "external_load"
                   and "loading_pin" not in (e.get("equipment_required") or [])
                   and e.get("load_unit") not in lu.LOAD_UNITS]
        assert missing == []

    @pytest.mark.parametrize("ex_id,unit", [
        ("dumbbell_bench_press", "per_dumbbell"), ("dumbbell_row", "per_dumbbell"),
        ("bicep_curl", "per_dumbbell"), ("hammer_curl", "per_dumbbell"), ("lateral_raise", "per_dumbbell"),
        ("overhead_press", "per_dumbbell"),
        ("goblet_squat", "implement"), ("overhead_tricep_extension", "implement"),
        ("bench_press", "total"), ("barbell_row", "total"), ("romanian_deadlift", "total"),
    ])
    def test_daniele_confirmed_units(self, ex_id, unit):
        assert CATALOG[ex_id]["load_unit"] == unit

    def test_pairs_have_matching_units(self):
        for barbell in ("bench_press", "barbell_row"):
            assert CATALOG[barbell]["load_unit"] == "total"
            assert CATALOG[lu.BARBELL_DUMBBELL_PAIRS[barbell]]["load_unit"] == "per_dumbbell"


# ── immutability ──────────────────────────────────────────────────────────────

class TestPastSessionsUntouched:
    def test_feedback_and_targets_never_touch_a_stored_past_session(self):
        past = {"date": "2026-10-06", "session_id": "upper_push_arms_lunch", "status": "done",
                "resolved": {"exercise_instances": [{"exercise_id": "bench_press",
                                                     "suggested": {"suggested_external_load_kg": 70.0}}]}}
        st = _state([_entry("bench_press", 70.0)])
        st["week_plans"] = {"2026-10-06": {"weeks": [{"days": [{"date": "2026-10-06", "sessions": [past]}]}]}}
        before = deepcopy(st["week_plans"])
        log = {"date": DAY,
               "planned": [{"exercise_instances": [{"exercise_id": "dumbbell_bench_press", "prescription": {}}]}],
               "actual": {"exercise_feedback_v1": [{"exercise_id": "dumbbell_bench_press", "completed": True,
                                                    "feedback_label": "easy", "used_external_load_kg": 35.0}]}}
        out = apply_feedback(log, st)
        _suggested(out, "dumbbell_bench_press")
        assert out["week_plans"] == before
        assert st["week_plans"] == before
        # The past bench entry keeps its own number (no conversion written back).
        bench = next(x for x in out["working_loads"]["entries"] if x["exercise_id"] == "bench_press")
        assert bench["next_external_load_kg"] == 70.0
