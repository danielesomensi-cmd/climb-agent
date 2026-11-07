"""B414 (step 13, B261-TEST-FALLBACK) — a 2RM test without weights is skipped,
never substituted.

The two 2RM blocks pin ``weighted_pullup`` (role ``main``, not ``test``), so
B261's test guard did not fire: without weights the pin went to P0 and the
"test" became ``power_pullups_explosive`` with the 2RM notes, resolution
success, no max ever written. Now both blocks declare ``pin_exhausted: skip``
(no fallback: a measurement is never replaced) — ``pulling_strength_test.main``
(template branch, used by ``test_max_weighted_pullup``) and
``test_max_hang_pullup.pullup_2rm_test`` (inline). The rest of the session
stays. With weights nothing changes (A319).
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from backend.engine.resolve_session import resolve_session

REPO = Path(__file__).resolve().parents[2]
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
PULLS = {"power_pullups_explosive", "archer_pullup", "dip", "one_arm_pullup_assisted", "pullup", "weighted_pullup"}

NO_WEIGHTS = ["pullup_bar", "hangboard", "gym_boulder"]
WITH_WEIGHTS = NO_WEIGHTS + ["weight", "dumbbell"]


def _resolve(sid: str, equipment) -> dict:
    state = {
        "context": {"location": "gym", "gym_id": "g1"},
        "equipment": {"gyms": [{"gym_id": "g1", "priority": 1, "equipment": list(equipment)}], "home": []},
        "defaults": {"location": "gym"},
    }
    return resolve_session(
        repo_root=str(REPO), session_path=f"backend/catalog/sessions/v1/{sid}.json",
        templates_dir="backend/catalog/templates", exercises_path=EXERCISES, out_path="",
        user_state_override=state, write_output=False, user_id=None,
    )


def _ids(r: dict) -> list:
    return [i["exercise_id"] for i in r["resolved_session"]["exercise_instances"]]


def _block(r: dict, block_id: str) -> dict:
    return next(b for b in r["resolved_session"]["blocks"] if b["block_id"] == block_id)


class TestWithoutWeights:
    def test_pulling_test_skips_the_2rm_keeps_the_l_sit(self):
        r = _resolve("test_max_weighted_pullup", NO_WEIGHTS)
        main = _block(r, "main")
        assert (main["status"], main["selected_exercises"]) == ("skipped", [])
        assert "pin_exhausted: skip" in main["message"]
        assert not PULLS & set(_ids(r)), _ids(r)
        assert "test_l_sit_hold" in _ids(r)
        assert r["resolution_status"] == "success"
        assert not any((i["prescription"] or {}).get("test_protocol") for i in r["resolved_session"]["exercise_instances"])

    def test_combined_test_keeps_the_hang_and_the_secondary_measures(self):
        r = _resolve("test_max_hang_pullup", NO_WEIGHTS)
        blk = _block(r, "pullup_2rm_test")
        assert (blk["status"], blk["selected_exercises"]) == ("skipped", [])
        ids = _ids(r)
        assert not PULLS & set(ids), ids
        assert "max_hang_7s" in ids and "test_l_sit_hold" in ids
        assert ids.index("max_hang_7s") < ids.index("test_l_sit_hold")  # A319 order kept
        assert r["resolution_status"] == "success"


class TestWithWeights:
    @pytest.mark.parametrize("sid, block_id", [("test_max_weighted_pullup", "main"),
                                               ("test_max_hang_pullup", "pullup_2rm_test")])
    def test_the_2rm_is_there(self, sid, block_id):
        r = _resolve(sid, WITH_WEIGHTS)
        sel = _block(r, block_id)["selected_exercises"]
        assert [s["exercise_id"] for s in sel] == ["weighted_pullup"]
        assert sel[0]["prescription"]["test_protocol"] == "2RM"


def _test_protocol_blocks():
    for path in sorted(glob.glob(str(REPO / "backend/catalog/sessions/v1/*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        for m in doc.get("modules") or []:
            if (m.get("prescription") or {}).get("test_protocol"):
                yield f"{doc['id']}.{m.get('block_id')}", (m.get("selection") or {}).get("primary") or {}
    for path in sorted(glob.glob(str(REPO / "backend/catalog/templates/v1/*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        for b in doc.get("blocks") or []:
            if (b.get("prescription") or {}).get("test_protocol"):
                yield f"{doc.get('id')}.{b.get('block_id')}", b


def test_every_measurement_block_declares_skip_or_fail():
    """A block with ``prescription.test_protocol`` never falls to P0 and never
    has a fallback: a measurement is skipped or failed, never substituted."""
    found = list(_test_protocol_blocks())
    assert {w for w, _ in found} == {"test_max_hang_pullup.pullup_2rm_test", "pulling_strength_test.main"}
    for where, spec in found:
        assert spec.get("pin_exhausted") in ("skip", "fail") or spec.get("pin_strict") is True, where
        assert not spec.get("fallback_exercise_ids"), where
