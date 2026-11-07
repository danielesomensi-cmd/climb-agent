"""B414 (step 13, INBOX-2026-11-04-GOBLET) — legs lunch: back squat with a
barbell, goblet squat without.

Daniele, 2026-11-07: back squat for everyone who has a barbell where the lunch
is resolved, same dose (5 x 6 at RIR 1-2, 120", 4 sets in deload), goblet
squat otherwise — decided by equipment, never by the place. Two catalog
changes on the B414 step-12 pin chain:

- ``back_squat`` needs ``barbell`` (it needed ``weight``, which any dumbbell
  implies, so the equipment could not tell a barbell from a pair of dumbbells);
- ``legs_maintenance_lunch.squat_main`` pins ``back_squat`` with
  ``fallback_exercise_ids: [goblet_squat]`` (exhausted = P0 with the block's
  own squat filters, as before).

The session ``version`` stays 1.3 (it is in the pre-B413 digests). The back
squat cold start (no working load: 0.15 x BW) is out of B414.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.engine import resolve_session as rs
from backend.engine.equipment_utils import expand_equipment
from backend.tests import b413_lunch_golden_cases as lg

REPO = Path(__file__).resolve().parents[2]
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
SID = "legs_maintenance_lunch"
SESSION = REPO / f"backend/catalog/sessions/v1/{SID}.json"

BKL_LIKE = ["gym_boulder", "gym_routes", "hangboard", "pullup_bar", "dumbbell", "weight"]
NO_WEIGHTS = ["gym_boulder", "pullup_bar", "hangboard"]


@pytest.fixture(scope="module")
def catalog() -> dict:
    return {e["id"]: e for e in json.loads((REPO / EXERCISES).read_text(encoding="utf-8"))["exercises"]}


def _state(date: str, equipment=None, working_loads=None) -> dict:
    st = lg.daniele_state(date)
    if equipment is not None:
        st["equipment"]["gyms"][-1]["equipment"] = list(equipment)
    if working_loads is not None:
        st["working_loads"] = {"entries": copy.deepcopy(working_loads), "rules": {}}
    return st


def _squat(r: dict) -> dict:
    return next(i for i in r["resolved_session"]["exercise_instances"] if i["source"]["block_id"] == "squat_main")


def _resolve(st: dict, phase: str = "performance") -> dict:
    return lg._resolve(SID, copy.deepcopy(st), phase)


class TestCatalog:
    def test_back_squat_needs_a_barbell(self, catalog):
        bs = catalog["back_squat"]
        assert bs["equipment_required"] == ["barbell"]
        assert not rs._pin_equipment_ok(bs, expand_equipment(["dumbbell"]))
        assert not rs._pin_equipment_ok(bs, expand_equipment(["weight", "dumbbell", "kettlebell"]))
        assert rs._pin_equipment_ok(bs, expand_equipment(["barbell"]))

    def test_the_block_is_a_chain_back_squat_then_goblet(self):
        doc = json.loads(SESSION.read_text(encoding="utf-8"))
        assert doc["version"] == "1.3"
        prim = next(m for m in doc["modules"] if m.get("block_id") == "squat_main")["selection"]["primary"]
        assert (prim["exercise_id"], prim["fallback_exercise_ids"]) == ("back_squat", ["goblet_squat"])
        assert "pin_exhausted" not in prim and "pin_strict" not in prim  # exhausted = P0 squat
        ov = prim["prescription_overrides"]
        assert (ov["sets"], ov["deload_sets"], ov["reps"], ov["rest_between_sets_seconds"]) == (5, 4, 6, 120)
        assert "goblet squat 5x6" not in doc["intent"]["notes"]
        assert "back squat with a barbell, goblet squat without" in doc["intent"]["notes"]

    def test_tags_and_cap_did_not_move(self, catalog):
        """Same intensity as the goblet: tags, cap and B395 stale tags unchanged."""
        bs, gs = catalog["back_squat"], catalog["goblet_squat"]
        for k in ("intensity_level", "role", "domain", "pattern", "load_model"):
            assert bs[k] == gs[k], k


class TestResolution:
    def test_with_a_barbell_back_squat_5x6(self):
        sq = _squat(_resolve(_state("2026-11-10")))
        p = sq["prescription"]
        assert (sq["exercise_id"], p["sets"], p["reps"], p["rest_between_sets_seconds"]) == ("back_squat", 5, 6, 120)
        assert sq["source"]["picked_by"] == "resolver_v0.2/explicit_exercise_id"
        assert "load_unit" not in (sq.get("suggested") or {})  # total (a barbell)

    def test_deload_drops_one_set(self):
        sq = _squat(_resolve(_state("2026-12-01"), "deload"))
        assert (sq["exercise_id"], sq["prescription"]["sets"]) == ("back_squat", 4)

    @pytest.mark.parametrize("phase", ["base", "strength_power", "power_endurance", "performance"])
    def test_dumbbells_only_goblet_never_cossack_or_split(self, phase):
        r = _resolve(_state("2026-11-10", BKL_LIKE), phase)
        sq = _squat(r)
        p = sq["prescription"]
        assert (sq["exercise_id"], p["sets"], p["reps"], p["rest_between_sets_seconds"]) == ("goblet_squat", 5, 6, 120)
        assert sq["source"]["picked_by"] == "resolver_v0.2/explicit_exercise_id"
        assert sq["suggested"].get("load_unit") == "implement"
        ids = [i["exercise_id"] for i in r["resolved_session"]["exercise_instances"]]
        assert "back_squat" not in ids and "cossack_squat" not in ids

    def test_no_weights_falls_to_p0_with_the_squat_filters(self, catalog):
        r = _resolve(_state("2026-11-10", NO_WEIGHTS))
        rows = [i for i in r["resolved_session"]["exercise_instances"] if i["source"]["block_id"] == "squat_main"]
        for i in rows:
            ex = catalog[i["exercise_id"]]
            assert ex["pattern"] == "squat" and ex["intensity_level"] in ("low", "medium")
            assert i["exercise_id"] not in ("back_squat", "goblet_squat")
        block = next(b for b in r["resolved_session"]["blocks"] if b["block_id"] == "squat_main")
        assert [x["exercise_id"] for x in block["p0_trace"]["pin_rejects"]] == ["back_squat", "goblet_squat"]

    def test_load_comes_from_the_working_load(self):
        wl = [{"exercise_id": "back_squat", "key": "back_squat", "last_external_load_kg": 60.0,
               "next_external_load_kg": 62.5, "updated_at": "2026-11-04"}]
        sq = _squat(_resolve(_state("2026-11-10", working_loads=wl)))
        assert sq["suggested"]["suggested_external_load_kg"] == 62.5

    def test_deterministic(self):
        st = _state("2026-11-10")
        a, b = _resolve(st), _resolve(st)
        a.pop("generated_at", None)
        b.pop("generated_at", None)
        assert a == b


class TestPastImmutable:
    def test_played_skipped_and_edited_lunches_stay_byte_for_byte(self, tmp_path, monkeypatch):
        """A legs lunch stored with the goblet (done / skipped / edited) stays
        byte for byte through GET /week and a forced regeneration; the planned
        one of the same week, at a home with a barbell, gets the back squat.
        Like every planned session without a stored record, a PAST planned-not-
        done lunch is re-resolved by GET too (``week._auto_resolve``) and shows
        the back squat: that is the prescription shown, nothing was played."""
        from backend.api import deps
        from backend.engine import storage_file
        from backend.tests import test_b413_freeze_prescription as fz

        monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
        monkeypatch.delenv("STORAGE_REQUEST_MEMO", raising=False)

        st = fz._state(this_week={d: [fz._core()] for d in (0, 1, 2, 3)}, offset=4)
        st["equipment"]["home"] = sorted(set(st["equipment"]["home"]) | {"barbell", "dumbbell", "bench"})
        ctx = {"location": "home", "target_date": fz.MON_ISO, "date": fz.MON_ISO}
        old = lg._resolve(SID, dict(copy.deepcopy(st), context=ctx), "strength_power")
        sq = _squat(old)
        assert sq["exercise_id"] == "back_squat"
        sq.update(exercise_id="goblet_squat", name="Goblet Squat")  # the record as stored before B414
        plan = st["week_plans"][fz.MON_ISO]
        fz._session(plan, SID, 0).update(status="done", resolved=copy.deepcopy(old))
        fz._session(plan, SID, 1).update(status="skipped", resolved=copy.deepcopy(old))
        fz._session(plan, SID, 2).update(_user_edited=True, resolved=copy.deepcopy(old))
        st["current_week_plan"] = plan
        deps.save_state(st, fz.UID)
        want = {d: fz._played(fz._stored(SID, d)) for d in (0, 1, 2)}

        view = fz._get()["week_plan"]
        assert {d: fz._played(fz._stored(SID, d)) for d in (0, 1, 2)} == want
        assert _squat(fz._session(view, SID, 3)["resolved"])["exercise_id"] == "back_squat"
        assert not fz._get(force="true").get("regeneration_failed")
        assert {d: fz._played(fz._stored(SID, d)) for d in (0, 1, 2)} == want
