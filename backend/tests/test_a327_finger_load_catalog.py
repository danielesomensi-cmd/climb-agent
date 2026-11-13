"""A327 step B (D288 R1) — ``finger_load`` in the exercise catalog.

Every exercise that loads the finger flexors for ``session_tags`` (a finger
pattern or domain, the B392 warm-ups included) and every finger-hard id carries
``finger_load: high | low``; nothing else does. ``low`` (≤ 50 % of max, no set
to failure, ≤ 10 min under load) is allowed only by a rule; ``high`` is always
allowed (the conservative side). The low list is pinned: a change is deliberate.

``finger_aerobic_base`` (the only catalog session meant to be low) is made
honest: its template picks the main hang among ``hang`` / ``isometric_hang``,
so it never resolves to intermittent hangs at 55-65 % or the 45-55 %
repeaters.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from backend.engine import session_tags as st
from backend.engine.stimulus import EXERCISE_FAMILY, FAMILY_FINGER_MAX, FAMILY_LIMIT_POWER

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

LOW = {
    "active_finger_curls", "bar_dead_hang", "dead_hang_easy", "finger_recruitment_pulls", "finger_warmup_generic",
    "hang_rampup_progressive", "long_duration_hang", "pocket_rampup_hangboard", "single_finger_pocket_rampup",
    "sub_max_capacity_hang", "warmup_easy_boulders", "warmup_repeaters_large",
}
LOW_LEVELS = {"very_low", "low", "medium"}
LOW_MAX_TUT_S = 600


def _catalog() -> dict:
    return {e["id"]: e for e in json.loads(CATALOG.read_text(encoding="utf-8"))["exercises"]}


def _loads_fingers(eid: str, e: dict) -> bool:
    pats = st._patterns_of(e)
    doms = [str(d) for d in (e.get("domain") or [])]
    return (eid in st._FINGER_HARD_IDS or any(p in st._FINGER_LOAD_PATTERNS for p in pats)
            or any(d in st._FINGER_LOAD_DOMAINS for d in doms))


def _tut(e: dict) -> int:
    pd = e.get("prescription_defaults") or {}
    sets = pd.get("sets") or 1
    reps = pd.get("reps") or 1
    work = pd.get("work_seconds") or 0
    return int(sets) * int(reps) * int(work)


def test_field_on_exactly_the_finger_exercises():
    cat = _catalog()
    have = {eid for eid, e in cat.items() if "finger_load" in e}
    want = {eid for eid, e in cat.items() if _loads_fingers(eid, e)}
    assert have == want
    assert len(have) == 57
    assert {e["finger_load"] for e in cat.values() if "finger_load" in e} == {"high", "low"}


def test_low_list_is_pinned():
    cat = _catalog()
    assert {eid for eid, e in cat.items() if e.get("finger_load") == "low"} == LOW


@pytest.mark.parametrize("eid", sorted(LOW))
def test_low_follows_the_rule(eid):
    e = _catalog()[eid]
    roles = e.get("role") or []
    roles = [roles] if isinstance(roles, str) else roles
    assert str(e.get("intensity_level")) in LOW_LEVELS
    assert str((e.get("stress_tags") or {}).get("fingers")) != "high"
    assert "test" not in roles
    assert eid not in st._FINGER_HARD_IDS
    assert EXERCISE_FAMILY.get(eid) not in (FAMILY_FINGER_MAX, FAMILY_LIMIT_POWER)
    assert _tut(e) <= LOW_MAX_TUT_S


def test_finger_hard_and_to_failure_are_high():
    cat = _catalog()
    for eid in st._FINGER_HARD_IDS:
        assert cat[eid]["finger_load"] == "high", eid
    for eid, fam in EXERCISE_FAMILY.items():
        if fam in (FAMILY_FINGER_MAX, FAMILY_LIMIT_POWER) and eid in cat:
            assert cat[eid]["finger_load"] == "high", eid
    # Sub-maximal to failure (answer 2: high for the spacing) and the borderline ones.
    for eid in ("intermittent_dead_hangs", "repeater_15_15", "lopez_subhangs", "density_hangs", "repeater_hang_7_3",
                "long_interval_repeaters", "repeater_sub_max_endurance", "hangboard_moving_hangs",
                "route_redpoint_attempt"):
        assert cat[eid]["finger_load"] == "high", eid


def test_aerobic_template_main_pool_is_low():
    """The main block of ``finger_aerobic_endurance`` (role main, domain
    finger_aerobic_endurance, pattern hang / isometric_hang) holds only low
    exercises."""
    tpl = json.loads((REPO / "backend/catalog/templates/v1/finger_aerobic_endurance.json").read_text())
    main = next(b for b in tpl["blocks"] if b["block_id"] == "main")
    assert main["pattern"] == ["hang", "isometric_hang"]
    pool = [eid for eid, e in _catalog().items()
            if "main" in (e.get("role") or []) and set(e.get("domain") or []) & set(main["domain"])
            and set(st._patterns_of(e)) & set(main["pattern"])]
    assert pool and all(_catalog()[eid]["finger_load"] == "low" for eid in pool), pool


def test_finger_aerobic_base_resolves_low_everywhere():
    from backend.tests import b413_lunch_golden_cases as lg
    from backend.tests.test_b414_session_tags_pe import _states

    cat = _catalog()
    logging.disable(logging.WARNING)
    try:
        seen = 0
        for _key, state, ph in _states():
            if state["context"]["location"] != "home":
                continue
            insts = lg._resolve("finger_aerobic_base", state, ph)["resolved_session"]["exercise_instances"]
            for i in insts:
                e = cat.get(i["exercise_id"]) or {}
                if "finger_load" in e:
                    seen += 1
                    assert e["finger_load"] == "low", (_key, i["exercise_id"])
        assert seen
    finally:
        logging.disable(logging.NOTSET)
