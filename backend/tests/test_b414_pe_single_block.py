"""B414 (step 16, INBOX-2026-11-02-a / -c / -e part 2) — power_endurance_gym:
one PE block, a technique rule per set, never a 7/3 after the PE work.

Before: two inline PE blocks (``pe_routes`` with the soft ``gym_routes``
preference, ``pe_boulder``) — the resolver resolves every inline block
(``required`` / ``priority`` are not read), so every athlete got TWO PE drills
(route intervals + a boulder one, or two boulder ones without routes), and the
finger block could pick ``repeater_hang_7_3`` under ``finger: False``.

Daniele, 2026-11-07: route intervals only where there are routes, otherwise
one PE boulder drill from the phase rotation; technique in the PE as one rule
per set in the cues; sub-max hangs only (no 7/3). Catalog only:

- one block, ``block_id`` kept as ``pe_boulder`` (phase-anchor history), with
  the ``gym_routes`` preference (Stage 2b: route intervals with routes,
  otherwise the boulder pool) — the boulder pick is the phase rotation's first
  choice, the one ``pe_routes`` used to get;
- ``intensity_max: medium`` on ``finger_endurance``;
- a "one technique rule per set, under pump" cue on ``four_by_four_bouldering``,
  ``linked_boulders``, ``linked_boulders_circuit``, ``route_intervals``.
"""
from __future__ import annotations

import copy
import glob
import json
from pathlib import Path

import pytest

from backend.engine.stimulus import stimulus_of
from backend.tests import b413_lunch_golden_cases as lg
from backend.tests import c272_golden_cases as golden

REPO = Path(__file__).resolve().parents[2]
SID = "power_endurance_gym"
SESSION = REPO / f"backend/catalog/sessions/v1/{SID}.json"
PE_DRILLS = ("four_by_four_bouldering", "linked_boulders", "linked_boulders_circuit", "route_intervals")
RANK = {"low": 0, "medium": 1, "high": 2, "max": 3}

GYMS = {
    "cocque": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"],
    "bkl": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar", "dumbbell", "weight"],
    "boulder_forest": ["gym_boulder", "hangboard", "pullup_bar"],
    "boulder_only": ["gym_boulder"],
}
PHASES = (("2026-10-13", "base"), ("2026-10-13", "strength_power"),
          ("2026-10-27", "power_endurance"), ("2026-11-10", "performance"))


@pytest.fixture(scope="module")
def catalog() -> dict:
    data = json.loads((REPO / "backend/catalog/exercises/v1/exercises.json").read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


def _state(profile: str, gym: str, date: str) -> dict:
    if profile == "daniele":
        st = lg.daniele_state(date)
        st["equipment"]["gyms"][-1]["equipment"] = list(GYMS[gym])
        return st
    st = copy.deepcopy(golden.profiles()[profile])
    st["equipment"]["gyms"].append({"gym_id": gym, "priority": 1, "equipment": list(GYMS[gym])})
    st["context"] = {"location": "gym", "gym_id": gym, "target_date": date, "date": date}
    return st


def _pe_rows(r: dict, catalog: dict) -> list:
    return [i for i in r["resolved_session"]["exercise_instances"]
            if "climbing_intervals" in ([catalog[i["exercise_id"]]["pattern"]]
                                        if isinstance(catalog[i["exercise_id"]]["pattern"], str)
                                        else catalog[i["exercise_id"]]["pattern"])
            and "main" in catalog[i["exercise_id"]]["role"]]


class TestCatalog:
    def test_one_pe_block_named_pe_boulder(self):
        mods = json.loads(SESSION.read_text(encoding="utf-8"))["modules"]
        ids = [m.get("block_id") for m in mods if m.get("block_id")]
        assert "pe_routes" not in ids and ids.count("pe_boulder") == 1
        pe = next(m for m in mods if m.get("block_id") == "pe_boulder")
        f = pe["selection"]["primary"]["filters"]
        assert pe["rotation"] == "phase_anchor"
        assert (f["pattern"], f["equipment"]) == (["climbing_intervals"], ["gym_routes"])
        fe = next(m for m in mods if m.get("block_id") == "finger_endurance")
        assert fe["selection"]["primary"]["filters"]["intensity_max"] == "medium"

    @pytest.mark.parametrize("eid", PE_DRILLS)
    def test_technique_rule_per_set_in_the_cues(self, catalog, eid):
        assert any("ONE rule per set" in c for c in catalog[eid]["cues"]), eid


def test_no_session_has_two_primary_blocks_for_the_same_work():
    """Guard: two inline P0 blocks of a session that share pattern AND domain
    resolve twice the same kind of drill (inline blocks are all resolved and
    have no hard block-level equipment filter)."""
    offenders = []
    for path in sorted(glob.glob(str(REPO / "backend/catalog/sessions/v1/*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        blocks = []
        for m in doc.get("modules") or []:
            prim = (m.get("selection") or {}).get("primary") or {}
            if "template_id" in m or prim.get("exercise_id") or m.get("module_role") not in ("primary", "main"):
                continue
            f = prim.get("filters") or {}
            blocks.append((m.get("block_id"), set(f.get("pattern") or []), set(f.get("domain") or [])))
        for i, a in enumerate(blocks):
            for b in blocks[i + 1:]:
                if a[1] & b[1] and a[2] & b[2]:
                    offenders.append((doc["id"], a[0], b[0]))
    assert offenders == []


@pytest.mark.parametrize("profile", ["daniele", "untested"])
@pytest.mark.parametrize("gym", ["cocque", "bkl"])
@pytest.mark.parametrize("date, phase", PHASES)
def test_with_routes_only_route_intervals(profile, gym, date, phase, catalog):
    r = lg._resolve(SID, _state(profile, gym, date), phase)
    assert [i["exercise_id"] for i in _pe_rows(r, catalog)] == ["route_intervals"]


@pytest.mark.parametrize("profile", ["daniele", "untested"])
@pytest.mark.parametrize("gym", ["boulder_forest", "boulder_only"])
@pytest.mark.parametrize("date, phase", PHASES)
def test_without_routes_one_boulder_drill(profile, gym, date, phase, catalog):
    r = lg._resolve(SID, _state(profile, gym, date), phase)
    rows = _pe_rows(r, catalog)
    assert len(rows) == 1 and rows[0]["exercise_id"] != "route_intervals", [i["exercise_id"] for i in rows]
    assert rows[0]["source"]["block_id"] == "pe_boulder"
    assert stimulus_of(rows[0]["exercise_id"]) == "power_endurance"


def test_without_routes_the_pick_follows_the_phase_rotation():
    """Daniele, PE phase, no routes: the phase anchor's first choice (the
    analysis' "for you linked_boulders in this phase")."""
    r = lg._resolve(SID, _state("daniele", "boulder_forest", "2026-10-27"), "power_endurance")
    assert [i["exercise_id"] for i in r["resolved_session"]["exercise_instances"]
            if i["source"]["block_id"] == "pe_boulder"] == ["linked_boulders"]


@pytest.mark.parametrize("profile", ["daniele", "untested", "advanced"])
@pytest.mark.parametrize("gym", sorted(GYMS))
@pytest.mark.parametrize("date, phase", PHASES)
def test_finger_block_never_above_medium(profile, gym, date, phase, catalog):
    r = lg._resolve(SID, _state(profile, gym, date), phase)
    for i in r["resolved_session"]["exercise_instances"]:
        if i["source"]["block_id"] == "finger_endurance":
            assert RANK[catalog[i["exercise_id"]]["intensity_level"]] <= 1, i["exercise_id"]
            assert i["exercise_id"] != "repeater_hang_7_3"


class TestPastImmutable:
    def test_a_played_two_block_pe_stays_byte_for_byte(self, tmp_path, monkeypatch):
        """A PE stored with the two old PE blocks (done / skipped / edited)
        stays byte for byte through GET /week and a forced regeneration; the
        planned one of the same week gets the single block."""
        from backend.api import deps
        from backend.engine import storage_file
        from backend.tests import test_b413_freeze_prescription as fz

        monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
        monkeypatch.delenv("STORAGE_REQUEST_MEMO", raising=False)

        slot = {"slot": "evening", "session_id": SID, "location": "gym", "gym_id": "cq",
                "tags": {"hard": True, "finger": False}}
        st = fz._state(this_week={d: [dict(slot)] for d in (0, 1, 2, 3)}, offset=4)
        st["equipment"]["gyms"] = [{"gym_id": "cq", "name": "Cocque", "priority": 1,
                                    "equipment": list(GYMS["cocque"])}]
        ctx = {"location": "gym", "gym_id": "cq", "target_date": fz.MON_ISO, "date": fz.MON_ISO}
        old = lg._resolve(SID, dict(copy.deepcopy(st), context=ctx), "strength_power")
        pe = next(i for i in old["resolved_session"]["exercise_instances"] if i["source"]["block_id"] == "pe_boulder")
        twin = copy.deepcopy(pe)  # the record as stored before B414: a second PE block
        twin.update(exercise_id="linked_boulders_circuit", instance_id="pe_routes_99",
                    source=dict(twin["source"], block_id="pe_routes"))
        old["resolved_session"]["exercise_instances"].append(twin)
        plan = st["week_plans"][fz.MON_ISO]
        fz._session(plan, SID, 0).update(status="done", resolved=copy.deepcopy(old))
        fz._session(plan, SID, 1).update(status="skipped", resolved=copy.deepcopy(old))
        fz._session(plan, SID, 2).update(_user_edited=True, resolved=copy.deepcopy(old))
        st["current_week_plan"] = plan
        deps.save_state(st, fz.UID)
        want = {d: fz._played(fz._stored(SID, d)) for d in (0, 1, 2)}

        view = fz._get()["week_plan"]
        assert {d: fz._played(fz._stored(SID, d)) for d in (0, 1, 2)} == want
        planned = fz._session(view, SID, 3)["resolved"]["resolved_session"]["exercise_instances"]
        assert "pe_routes" not in {i["source"]["block_id"] for i in planned}
        assert [i["exercise_id"] for i in planned if i["source"]["block_id"] == "pe_boulder"] == ["route_intervals"]
        assert not fz._get(force="true").get("regeneration_failed")
        assert {d: fz._played(fz._stored(SID, d)) for d in (0, 1, 2)} == want
