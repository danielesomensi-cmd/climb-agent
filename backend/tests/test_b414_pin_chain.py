"""B414 (B381-FALLBACK) — an ordered pin chain per block in the resolver.

A pinned block may list ``fallback_exercise_ids`` after its ``exercise_id`` and
declare ``pin_exhausted`` (``p0`` | ``skip`` | ``fail``) for when no candidate
has its equipment. One helper, ``resolve_session._resolve_pin_chain``, serves
the inline branch (keys in ``selection.primary``) and the template branch
(keys on the block). The gate is equipment only (Daniele, 2026-11-07: "the pin
checks equipment only"): no recency, no weekly seed, no rotation, no location.

Acceptance check: a block without the new keys resolves exactly as before —
same outcome, same ``picked_by``, same trace (the c272 / a290 / b413 goldens
stay untouched by this step). ``pin_strict: true`` stays the alias of ``fail``.
"""
from __future__ import annotations

import copy
import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.engine import resolve_session as rs
from backend.engine.catalog_roles import is_library_only
from backend.engine.equipment_utils import expand_equipment
from backend.tests import b413_lunch_golden_cases as lg

REPO = Path(__file__).resolve().parents[2]
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
SESSIONS = REPO / "backend/catalog/sessions/v1"
TEMPLATES = REPO / "backend/catalog/templates/v1"

BARBELL_GYM = ["barbell", "bench", "dumbbell", "weight", "pullup_bar"]
DUMBBELL_GYM = ["dumbbell", "pullup_bar"]
BARE_GYM = ["pullup_bar"]


@pytest.fixture(scope="module")
def exercises() -> List[Dict[str, Any]]:
    return json.loads((REPO / EXERCISES).read_text(encoding="utf-8"))["exercises"]


@pytest.fixture(scope="module")
def catalog(exercises) -> Dict[str, Dict[str, Any]]:
    return {e["id"]: e for e in exercises}


def _chain(spec, exercises, equipment):
    return rs._resolve_pin_chain(spec, exercises, expand_equipment(list(equipment)), block_id="b")


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------

class TestChainHelper:
    SPEC = {"exercise_id": "bench_press", "fallback_exercise_ids": ["dumbbell_bench_press"]}

    def test_first_candidate_with_its_equipment_wins(self, exercises):
        out, ex, trace = _chain(self.SPEC, exercises, BARBELL_GYM)
        assert (out, ex["id"], trace["pin_index"], trace["pin_rejects"]) == (
            "explicit_exercise_id", "bench_press", 0, [])
        out, ex, trace = _chain(self.SPEC, exercises, DUMBBELL_GYM)
        assert (out, ex["id"], trace["pin_index"]) == ("explicit_exercise_id", "dumbbell_bench_press", 1)
        assert trace["pin_rejects"] == [{"exercise_id": "bench_press", "reason": "equipment"}]

    def test_order_is_the_catalog_order_and_deterministic(self, exercises):
        spec = {"exercise_id": "dumbbell_bench_press", "fallback_exercise_ids": ["bench_press"]}
        assert _chain(spec, exercises, BARBELL_GYM)[1]["id"] == "dumbbell_bench_press"
        assert _chain(self.SPEC, exercises, DUMBBELL_GYM) == _chain(self.SPEC, exercises, DUMBBELL_GYM)

    def test_repeated_ids_are_dropped(self):
        assert rs._pin_candidate_ids({"exercise_id": "a", "fallback_exercise_ids": ["b", "a", "B", "c"]}) == [
            "a", "b", "c"]
        assert rs._pin_candidate_ids({}) == []

    def test_missing_id_is_logged_and_skipped(self, exercises, caplog):
        spec = {"exercise_id": "no_such_exercise_b414", "fallback_exercise_ids": ["dumbbell_bench_press"]}
        with caplog.at_level("WARNING"):
            out, ex, trace = _chain(spec, exercises, DUMBBELL_GYM)
        assert (out, ex["id"], trace["pin_index"]) == ("explicit_exercise_id", "dumbbell_bench_press", 1)
        assert trace["pin_rejects"] == [{"exercise_id": "no_such_exercise_b414", "reason": "not_in_catalog"}]
        assert "no_such_exercise_b414" in caplog.text

    def test_no_pin_means_no_chain(self, exercises):
        assert _chain({"filters": {"role": ["main"]}}, exercises, BARE_GYM) == (None, None, {})

    @pytest.mark.parametrize("spec, expected", [
        ({}, "p0"),
        ({"pin_exhausted": "p0"}, "p0"),
        ({"pin_exhausted": "skip"}, "skip"),
        ({"pin_exhausted": "fail"}, "fail"),
        ({"pin_strict": True}, "fail"),
        ({"pin_strict": False}, "p0"),
        ({"pin_strict": True, "pin_exhausted": "skip"}, "skip"),
        ({"pin_exhausted": "bogus"}, "p0"),
    ])
    def test_exhausted_mode(self, spec, expected):
        assert rs._pin_exhausted_mode(spec) == expected

    @pytest.mark.parametrize("mode, outcome", [
        (None, "p0"),
        ("p0", "p0"),
        ("skip", "pin_exhausted_skip"),
        ("fail", "pin_strict_incompatible_failed"),
    ])
    def test_exhausted_outcomes(self, exercises, mode, outcome):
        spec = dict(self.SPEC)
        if mode:
            spec["pin_exhausted"] = mode
        out, ex, trace = _chain(spec, exercises, BARE_GYM)
        assert (out, ex) == (outcome, None)
        assert trace["pin_rejects"] == [{"exercise_id": "bench_press", "reason": "equipment"},
                                        {"exercise_id": "dumbbell_bench_press", "reason": "equipment"}]

    @pytest.mark.parametrize("mode", [None, "p0", "fail"])
    def test_first_test_pin_exhausted_is_always_skipped(self, exercises, mode):
        """B261: a measurement is never substituted, whatever the catalog says."""
        spec = {"exercise_id": "max_hang_7s"}
        if mode:
            spec["pin_exhausted"] = mode
        assert _chain(spec, exercises, BARE_GYM)[0] == "pin_test_incompatible_skip"


class TestNoNewKeysSameAsBefore:
    """Without the new keys: the pre-B414 outcome and trace, bit for bit."""

    def test_passing_pin(self, exercises):
        assert _chain({"exercise_id": "bench_press"}, exercises, BARBELL_GYM)[2] == {
            "counts": {}, "domain_filter_applied": None, "note": "explicit_exercise_id: bypassed P0 filters"}

    def test_incompatible_pin_goes_to_p0_with_an_untouched_trace(self, exercises):
        assert _chain({"exercise_id": "bench_press"}, exercises, DUMBBELL_GYM) == ("p0", None, {})

    def test_strict_pin(self, exercises):
        assert _chain({"exercise_id": "bench_press", "pin_strict": True}, exercises, DUMBBELL_GYM) == (
            "pin_strict_incompatible_failed", None,
            {"counts": {}, "domain_filter_applied": None,
             "note": "strict pin incompatible with equipment — block failed (C274)"})

    def test_test_pin(self, exercises):
        assert _chain({"exercise_id": "max_hang_7s"}, exercises, BARE_GYM) == (
            "pin_test_incompatible_skip", None,
            {"counts": {}, "domain_filter_applied": None,
             "note": "pinned test exercise incompatible with equipment — block skipped (B261)"})


# ---------------------------------------------------------------------------
# Both resolver branches
# ---------------------------------------------------------------------------

def _state(equipment, gym_id="g1"):
    return {
        "context": {"location": "gym", "gym_id": gym_id},
        "equipment": {"gyms": [{"gym_id": gym_id, "priority": 1, "equipment": list(equipment)}], "home": []},
        "defaults": {"location": "gym"},
    }


def _write(tmp: Path, name: str, doc: dict) -> str:
    p = tmp / f"{name}.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return os.path.relpath(p, REPO)


def _resolve(session_rel, templates_rel, equipment, *, state=None, phase=None):
    r = rs.resolve_session(
        str(REPO), session_rel, templates_rel, EXERCISES, "",
        user_state_override=copy.deepcopy(state or _state(equipment)), write_output=False, phase=phase,
    )
    r.pop("generated_at", None)
    return r


PUSH_FILTERS = {"role": ["accessory"], "domain": ["strength_general"], "pattern": ["push"]}


def _inline_session(tmp: Path, **primary_keys) -> str:
    primary = {"exercise_id": "bench_press", "filters": PUSH_FILTERS, **primary_keys}
    doc = {"id": "b414_chain_inline", "name": "B414 chain", "required_equipment": [],
           "modules": [{"block_id": "warm", "module_role": "general_warmup",
                        "selection": {"primary": {"exercise_id": "general_pulse_raise",
                                                  "filters": {"role": ["warmup"]}}}},
                       {"block_id": "press", "module_role": "primary", "selection": {"primary": primary}}]}
    return _write(tmp, "b414_chain_inline", doc)


def _template_session(tmp: Path, **block_keys) -> tuple:
    tpl = {"id": "b414_chain_tpl", "blocks": [
        {"block_id": "warm", "role": ["warmup"], "exercise_id": "general_pulse_raise"},
        {"block_id": "press", "role": ["accessory"], "domain": ["strength_general"], "pattern": ["push"],
         "exercise_id": "bench_press", **block_keys},
    ]}
    tdir = tmp / "templates"
    tdir.mkdir(exist_ok=True)
    (tdir / "b414_chain_tpl.json").write_text(json.dumps(tpl), encoding="utf-8")
    doc = {"id": "b414_chain_template", "name": "B414 chain", "required_equipment": [],
           "modules": [{"template_id": "b414_chain_tpl"}]}
    return _write(tmp, "b414_chain_template", doc), os.path.relpath(tdir, REPO)


def _press_block(r):
    return next(b for b in r["resolved_session"]["blocks"] if b["block_id"] == "press")


def _press_ids(r):
    return [i["exercise_id"] for i in r["resolved_session"]["exercise_instances"]
            if i["source"]["block_id"] == "press"]


def _press_picked_by(r):
    return [i["source"]["picked_by"] for i in r["resolved_session"]["exercise_instances"]
            if i["source"]["block_id"] == "press"]


@pytest.fixture()
def branch_builders(tmp_path):
    def inline(**keys):
        return _inline_session(tmp_path, **keys), "backend/catalog/templates"

    def template(**keys):
        return _template_session(tmp_path, **keys)

    return {"inline": inline, "template": template}


@pytest.mark.parametrize("branch", ["inline", "template"])
class TestBothBranches:
    def test_chain_follows_the_equipment(self, branch_builders, branch):
        sess, tpl = branch_builders[branch](fallback_exercise_ids=["dumbbell_bench_press"])
        assert _press_ids(_resolve(sess, tpl, BARBELL_GYM)) == ["bench_press"]
        r = _resolve(sess, tpl, DUMBBELL_GYM)
        assert _press_ids(r) == ["dumbbell_bench_press"]
        # every candidate of the chain is a pin: same picked_by as before
        assert _press_picked_by(r) == ["resolver_v0.2/explicit_exercise_id"]
        trace = _press_block(r)["p0_trace"]
        assert trace["pin_index"] == 1 and trace["pin_rejects"][0]["exercise_id"] == "bench_press"
        assert r["resolution_status"] == "success"

    def test_exhausted_p0_keeps_the_block_filters(self, branch_builders, branch, catalog):
        sess, tpl = branch_builders[branch](fallback_exercise_ids=["dumbbell_bench_press"])
        r = _resolve(sess, tpl, BARE_GYM)
        ids = _press_ids(r)
        for eid in ids:  # P0 never bypasses the block's filters
            ex = catalog[eid]
            assert "push" in ([ex["pattern"]] if isinstance(ex["pattern"], str) else ex["pattern"])
            assert rs._pin_equipment_ok(ex, expand_equipment(BARE_GYM))
        assert "dumbbell_bench_press" not in ids and "bench_press" not in ids
        assert len(_press_block(r)["p0_trace"]["pin_rejects"]) == 2

    def test_exhausted_skip(self, branch_builders, branch):
        sess, tpl = branch_builders[branch](fallback_exercise_ids=["dumbbell_bench_press"], pin_exhausted="skip")
        r = _resolve(sess, tpl, BARE_GYM)
        block = _press_block(r)
        assert (_press_ids(r), block["status"], r["resolution_status"]) == ([], "skipped", "success")
        assert "pin_exhausted: skip" in block["message"]

    @pytest.mark.parametrize("keys", [{"pin_exhausted": "fail"}, {"pin_strict": True}])
    def test_exhausted_fail(self, branch_builders, branch, keys):
        """``pin_strict`` = ``fail``, now on the template branch too."""
        sess, tpl = branch_builders[branch](**keys)
        r = _resolve(sess, tpl, DUMBBELL_GYM)
        block = _press_block(r)
        assert (_press_ids(r), block["status"], r["resolution_status"]) == ([], "failed", "failed")
        assert "C274 pin_strict" in block["message"]

    def test_no_new_keys_is_the_old_resolution(self, branch_builders, branch):
        """The pin alone: honoured with its equipment, P0 without (B261)."""
        sess, tpl = branch_builders[branch]()
        r = _resolve(sess, tpl, BARBELL_GYM)
        assert _press_ids(r) == ["bench_press"]
        assert _press_block(r)["p0_trace"] == {
            "counts": {}, "domain_filter_applied": None, "note": "explicit_exercise_id: bypassed P0 filters"}
        r = _resolve(sess, tpl, DUMBBELL_GYM)
        assert "pin_rejects" not in _press_block(r)["p0_trace"]
        assert _press_picked_by(r)[0] != "resolver_v0.2/explicit_exercise_id"

    def test_deterministic(self, branch_builders, branch):
        sess, tpl = branch_builders[branch](fallback_exercise_ids=["dumbbell_bench_press"])
        assert _resolve(sess, tpl, DUMBBELL_GYM) == _resolve(sess, tpl, DUMBBELL_GYM)


def test_recent_candidate_is_still_taken(exercises):
    """A pin is "the same movement every time": recency never moves the chain."""
    mod = {"block_id": "press", "module_role": "primary",
           "selection": {"primary": {"exercise_id": "bench_press", "fallback_exercise_ids": ["dumbbell_bench_press"],
                                     "filters": PUSH_FILTERS}}}
    blocks, insts = [], []
    rs._resolve_inline_block(
        mod=mod, exercises=exercises, location="gym", available_equipment=expand_equipment(DUMBBELL_GYM),
        prefs={}, recent_ex_ids=["dumbbell_bench_press"], user_state=None, target_date="2026-11-10",
        blocks_out=blocks, exercise_instances=insts, instance_counter=0,
    )
    assert [i["exercise_id"] for i in insts] == ["dumbbell_bench_press"]


def test_ladder_pin_runs_on_a_chain_candidate(tmp_path):
    """B413 D4: a ladder_pin block whose pin comes from the chain behaves like
    the same block pinned directly (the ladder sees ``explicit_exercise_id``)."""
    doc = json.loads((SESSIONS / "legs_maintenance_lunch.json").read_text(encoding="utf-8"))
    chained = copy.deepcopy(doc)
    for m in chained["modules"]:
        if m.get("block_id") == "core_anti_extension":
            prim = m["selection"]["primary"]
            assert prim["exercise_id"] == "core_hollow_hold" and m.get("ladder_pin")
            prim["exercise_id"] = "linked_boulders"  # needs a wall: never at Work
            prim["fallback_exercise_ids"] = ["core_hollow_hold"]
    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    (sess_dir / "legs_maintenance_lunch.json").write_text(json.dumps(chained), encoding="utf-8")
    state = lg.daniele_state("2026-11-10")
    direct = _resolve("backend/catalog/sessions/v1/legs_maintenance_lunch.json", "backend/catalog/templates",
                      [], state=state, phase="strength_power")
    via_chain = _resolve(os.path.relpath(sess_dir / "legs_maintenance_lunch.json", REPO),
                         "backend/catalog/templates", [], state=state, phase="strength_power")

    def core(r):
        return [i for i in r["resolved_session"]["exercise_instances"]
                if i["source"]["block_id"] == "core_anti_extension"]

    assert core(via_chain) == core(direct)
    assert core(direct)[0]["source"]["picked_by"] == "resolver_v0.2/ladder_pin"


# ---------------------------------------------------------------------------
# Catalog lint
# ---------------------------------------------------------------------------

_RANK = {"low": 0, "medium": 1, "high": 2, "max": 3}


def _as_list(v) -> List[str]:
    if v is None:
        return []
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def _matches_filters(ex: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    for key in ("role", "domain", "pattern"):
        want = set(_as_list(filters.get(key)))
        if want and not want & set(_as_list(ex.get(key))):
            return False
    imax = filters.get("intensity_max")
    if imax and _RANK.get(str(ex.get("intensity_level") or "low"), 0) > _RANK.get(str(imax), 3):
        return False
    return True


def _pinned_specs():
    """(where, spec, filters) of every pinned block of the catalog."""
    for path in sorted(glob.glob(str(SESSIONS / "*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        for m in doc.get("modules") or []:
            prim = (m.get("selection") or {}).get("primary") or {}
            if prim.get("exercise_id"):
                yield f"{doc['id']}.{m.get('block_id')}", prim, prim.get("filters") or {}
    for path in sorted(glob.glob(str(TEMPLATES / "*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        for b in doc.get("blocks") or []:
            if b.get("exercise_id"):
                yield f"{doc.get('id')}.{b.get('block_id')}", b, {k: b.get(k) for k in ("role", "domain", "pattern")}


def chain_lint(specs, catalog) -> List[str]:
    """Static check of every pin chain: each fallback exists, is active, is not
    library-only, matches the block's filters, needs equipment no earlier
    candidate already covers (else unreachable); no fallback after a test pin;
    ``pin_exhausted`` valid and never together with ``pin_strict``."""
    problems: List[str] = []
    for where, spec, filters in specs:
        mode = spec.get("pin_exhausted")
        if mode is not None and mode not in rs.PIN_EXHAUSTED_VALUES:
            problems.append(f"{where}: pin_exhausted {mode!r}")
        if mode is not None and "pin_strict" in spec:
            problems.append(f"{where}: pin_exhausted and pin_strict together")
        fallbacks = spec.get("fallback_exercise_ids")
        if fallbacks is None:
            continue
        if not isinstance(fallbacks, list) or not fallbacks:
            problems.append(f"{where}: fallback_exercise_ids must be a non-empty list")
            continue
        first = catalog.get(spec["exercise_id"])
        if first is not None and rs._is_test_exercise(first):
            problems.append(f"{where}: a test pin never has fallbacks")
        earlier = [first] if first is not None else []
        for eid in fallbacks:
            ex = catalog.get(eid)
            if ex is None:
                problems.append(f"{where}: fallback {eid} not in catalog")
                continue
            if ex.get("active") is False:
                problems.append(f"{where}: fallback {eid} inactive")
            if is_library_only(ex):
                problems.append(f"{where}: fallback {eid} library-only")
            if not _matches_filters(ex, filters):
                problems.append(f"{where}: fallback {eid} outside the block filters")
            # where this one passes, would an earlier one pass too? (expanded:
            # a barbell implies dumbbells, equipment_utils.expand_equipment)
            req = set(expand_equipment(_as_list(ex.get("equipment_required"))))
            for prev in earlier:
                prev_req = set(_as_list(prev.get("equipment_required")))
                if not _as_list(prev.get("equipment_required_any")) and prev_req <= req:
                    problems.append(f"{where}: fallback {eid} unreachable after {prev['id']}")
                    break
            earlier.append(ex)
    return problems


def test_catalog_chains_are_sound(catalog):
    assert chain_lint(_pinned_specs(), catalog) == []


@pytest.mark.parametrize("spec, filters, problem", [
    ({"exercise_id": "bench_press", "fallback_exercise_ids": ["nope_b414"]}, PUSH_FILTERS, "not in catalog"),
    ({"exercise_id": "bench_press", "fallback_exercise_ids": ["goblet_squat"]}, PUSH_FILTERS, "outside the block filters"),
    ({"exercise_id": "dumbbell_bench_press", "fallback_exercise_ids": ["bench_press"]}, PUSH_FILTERS, "unreachable"),
    ({"exercise_id": "max_hang_7s", "fallback_exercise_ids": ["dumbbell_bench_press"]}, {}, "test pin"),
    ({"exercise_id": "bench_press", "pin_exhausted": "maybe"}, PUSH_FILTERS, "pin_exhausted 'maybe'"),
    ({"exercise_id": "bench_press", "pin_exhausted": "fail", "pin_strict": True}, PUSH_FILTERS, "together"),
    ({"exercise_id": "bench_press", "fallback_exercise_ids": []}, PUSH_FILTERS, "non-empty list"),
])
def test_chain_lint_catches(catalog, spec, filters, problem):
    problems = chain_lint([("s.b", spec, filters)], catalog)
    assert len(problems) == 1 and problem in problems[0], problems


def test_chain_lint_flags_library_and_inactive(catalog):
    lib = next(e for e in catalog.values() if is_library_only(e))
    fake = dict(catalog)
    fake["inactive_b414"] = {**catalog["dumbbell_bench_press"], "id": "inactive_b414", "active": False}
    spec = {"exercise_id": "bench_press", "fallback_exercise_ids": [lib["id"], "inactive_b414"]}
    problems = chain_lint([("s.b", spec, {})], fake)
    assert any("library-only" in p for p in problems) and any("inactive" in p for p in problems)
