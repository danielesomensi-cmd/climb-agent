"""B227 — Resolver intensity_max enforcement.

Tests the 3-tier cascade introduced by B227 in `_resolve_inline_block` and
`pick_best_exercise_p0`. See `_archive/docs/audit/B227_phase0_findings.md`.
"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.engine.resolve_session import (  # noqa: E402
    _INTENSITY_ORDER,
    pick_best_exercise_p0,
    resolve_session,
)

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"

DECLARING_SESSIONS = [
    "regeneration_easy", "yoga_recovery", "flexibility_full",
    "prehab_maintenance", "complementary_conditioning",
    "handstand_practice", "finger_maintenance_gym",
    "finger_maintenance_home", "finger_strength_home",
]


def _base_state(home_equipment: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "preferences": {
            "finger_training_device": None,
            "home_equipment": home_equipment or [],
        },
        "gyms": [],
        "goal": {"discipline": "lead", "main_goal_grade": "7a"},
        "assessment": {
            "profile": {
                "finger_strength": 50, "pulling_strength": 50,
                "power_endurance": 50, "technique": 50, "endurance": 50,
            },
            "archetype": "all_rounder",
        },
    }


def _resolve(session_id: str, *, location: str, equipment: List[str]) -> Dict[str, Any]:
    state = _base_state(equipment if location == "home" else [])
    state["context"] = {"location": location}
    return resolve_session(
        repo_root=str(REPO_ROOT),
        session_path=f"{SESSIONS_DIR}/{session_id}.json",
        templates_dir=TEMPLATES_DIR,
        exercises_path=EXERCISES_PATH,
        out_path="",
        user_state_override=state,
        write_output=False,
        phase="base",
        equipment_override=equipment,
    )


@pytest.fixture(scope="module")
def exercise_index() -> Dict[str, Dict[str, Any]]:
    data = json.loads(Path(REPO_ROOT / EXERCISES_PATH).read_text())
    cat = data.get("exercises", data) if isinstance(data, dict) else data
    return {(e.get("id") or e.get("exercise_id")): e for e in cat}


@pytest.fixture(scope="module")
def session_intensity_max_blocks() -> Dict[str, Dict[str, str]]:
    """Map session_id -> {block_id: intensity_max} for inline blocks declaring it."""
    out: Dict[str, Dict[str, str]] = {}
    for sid in DECLARING_SESSIONS:
        path = REPO_ROOT / SESSIONS_DIR / f"{sid}.json"
        js = json.loads(path.read_text())
        per_block: Dict[str, str] = {}
        for mod in js.get("modules", []):
            sel = mod.get("selection", {}).get("primary", {}).get("filters", {})
            if "intensity_max" in sel:
                bid = mod.get("block_id") or mod.get("template_id") or "?"
                per_block[bid] = sel["intensity_max"]
        out[sid] = per_block
    return out


def _ceiling_for(level: Optional[str]) -> int:
    return _INTENSITY_ORDER.get(level or "", -1)


def _violates_ceiling(declared_max: str, actual: Optional[str]) -> bool:
    """True when actual intensity strictly exceeds declared_max ceiling.
    Used for HARD violations (Tier 1 leak). Tier 3 escalations checked separately."""
    return _ceiling_for(actual) > _ceiling_for(declared_max)


def _exceeds_one_step(declared_max: str, actual: Optional[str]) -> bool:
    """True when actual intensity exceeds declared_max by MORE than the one-step
    Tier 3 escalation (low → medium). Used for the absolute red line: never `high`
    in a `intensity_max=low` block."""
    if actual is None or actual not in _INTENSITY_ORDER:
        return False
    if declared_max == "low":
        # Tier 3 may escalate to medium; high/very_high/max are forbidden.
        return _INTENSITY_ORDER[actual] > _INTENSITY_ORDER["medium"]
    # medium/high have no Tier 3 escalation — strict ceiling.
    return _violates_ceiling(declared_max, actual)


# ---------------------------------------------------------------------------
# Brief P1.3 tests (8) + 2 extra fixtures
# ---------------------------------------------------------------------------

def test_dip_not_selectable_in_finger_maintenance_at_home(exercise_index):
    """B227 audit F1 — exact P0.4 repro: finger_maintenance_gym at home selecting dip.

    Pre-B227: home + no equipment selected `dip` (intensity=high) for the
    `easy_climbing_post_finger` block declaring intensity_max=low.
    Post-B227: dip is filtered out at Stage 3c and Tier 3 cascade caps at medium.
    """
    res = _resolve("finger_maintenance_gym", location="home", equipment=[])
    rs = res.get("resolved_session", {})
    for blk in rs.get("blocks", []):
        if "easy_climbing_post_finger" not in (blk.get("block_uid") or ""):
            continue
        for ex in blk.get("selected_exercises", []):
            ex_id = ex.get("exercise_id")
            assert ex_id != "dip", (
                f"B227 regression: dip selected for "
                f"easy_climbing_post_finger (intensity_max=low)"
            )
            actual = exercise_index[ex_id].get("intensity_level")
            assert not _exceeds_one_step("low", actual), (
                f"B227: ex={ex_id} actual_intensity={actual} exceeds Tier 3 ceiling for low"
            )


def test_intensity_max_low_excludes_high_in_all_declaring_sessions(
    exercise_index, session_intensity_max_blocks,
):
    """For each of 9 declaring sessions × all reasonable equipment profiles:
    no high/very_high/max exercise ever appears in a low-declared block."""
    profiles = [
        ("home", []),
        ("home", ["pullup_bar"]),
        ("home", ["pullup_bar", "hangboard", "loading_pin", "rings", "barbell"]),
        ("gym", ["gym_boulder", "gym_routes", "hangboard", "pullup_bar", "barbell"]),
    ]
    leaks: List[Dict[str, Any]] = []
    for sid, block_imax in session_intensity_max_blocks.items():
        for location, eq in profiles:
            res = _resolve(sid, location=location, equipment=eq)
            for blk in res.get("resolved_session", {}).get("blocks", []):
                block_id = blk.get("block_id") or (blk.get("block_uid") or "").split(".")[-1]
                declared = block_imax.get(block_id)
                if not declared:
                    continue
                for ex in blk.get("selected_exercises", []):
                    actual = exercise_index[ex.get("exercise_id")].get("intensity_level")
                    if _exceeds_one_step(declared, actual):
                        leaks.append({
                            "session": sid, "block": block_id,
                            "profile": (location, eq),
                            "ex": ex.get("exercise_id"),
                            "declared": declared, "actual": actual,
                        })
    assert leaks == [], f"B227 ceiling leaks across declaring sessions: {leaks}"


def test_pick_best_exercise_p0_rejects_high_when_intensity_max_low(exercise_index):
    """Direct P0 unit test: with intensity_max='low', selection.primary
    filtering excludes any high/max exercise from the candidate pool."""
    catalog = list(exercise_index.values())
    selected, trace = pick_best_exercise_p0(
        exercises=catalog,
        location="home",
        available_equipment=[],
        role_req=["main"],
        domain_req=None,
        pattern_req=None,
        intensity_max="low",
        exclude_ids=set(),
        recent_ex_ids=[],
        recent_recency_groups=set(),
    )
    if selected is not None:
        actual = selected.get("intensity_level")
        assert _INTENSITY_ORDER[actual] <= _INTENSITY_ORDER["low"], (
            f"B227: pick_best_exercise_p0 returned {selected['id']} "
            f"intensity={actual} despite intensity_max=low"
        )
    assert trace.get("intensity_max_applied") is True


def test_cascade_tier1_keeps_domain_when_pool_nonempty(exercise_index):
    """When Tier 1 has matches, cascade does NOT escalate."""
    # Resolve regeneration_easy at gym with full equipment — Tier 1 should succeed.
    res = _resolve(
        "regeneration_easy",
        location="gym",
        equipment=["gym_boulder", "gym_routes", "hangboard"],
    )
    rs = res.get("resolved_session", {})
    found_main = False
    for blk in rs.get("blocks", []):
        if "continuity_main" in (blk.get("block_uid") or ""):
            found_main = True
            assert blk.get("status") == "selected", "Tier 1 should select continuity_climbing at gym"
            trace = blk.get("p0_trace") or blk.get("filter_trace") or {}
            assert trace.get("cascade_tier", 1) == 1, (
                f"Tier 1 expected, got cascade_tier={trace.get('cascade_tier')}"
            )
            ex_ids = [e.get("exercise_id") for e in blk.get("selected_exercises", [])]
            assert any(eid in ("continuity_climbing", "easy_route_laps", "arc_training_progressive")
                       for eid in ex_ids), f"Tier 1 should pick from regeneration domain, got {ex_ids}"
    assert found_main, "continuity_main block not found in regeneration_easy resolution"


def test_cascade_tier3_allows_medium_for_low_declared(exercise_index):
    """When Tier 1+2 empty for a low block, Tier 3 may pick a medium exercise.

    Repro: finger_maintenance_gym at home — no climbing exercises pass after_location;
    Tier 1 (domain=regeneration + low) empty; Tier 2 (any domain + low) empty for
    home pool too; Tier 3 (any domain + low/medium) picks a medium accessory.
    """
    res = _resolve("finger_maintenance_gym", location="home", equipment=[])
    rs = res.get("resolved_session", {})
    found_tier3 = False
    for blk in rs.get("blocks", []):
        if "easy_climbing_post_finger" not in (blk.get("block_uid") or ""):
            continue
        if blk.get("status") != "selected":
            continue
        trace = blk.get("p0_trace") or blk.get("filter_trace") or {}
        if trace.get("cascade_tier") == 3:
            found_tier3 = True
            for ex in blk.get("selected_exercises", []):
                actual = exercise_index[ex.get("exercise_id")].get("intensity_level")
                assert _INTENSITY_ORDER[actual] <= _INTENSITY_ORDER["medium"], (
                    f"Tier 3 must cap at medium, got {actual}"
                )
    # If Tier 3 didn't fire, the block must be skipped (not Tier 1/2 silent).
    if not found_tier3:
        for blk in rs.get("blocks", []):
            if "easy_climbing_post_finger" in (blk.get("block_uid") or ""):
                trace = blk.get("p0_trace") or blk.get("filter_trace") or {}
                assert blk.get("status") == "skipped" or trace.get("cascade_tier") in (1, 2), (
                    f"Block resolved without cascade tier annotation: {trace}"
                )


def test_cascade_skip_when_all_tiers_empty(exercise_index):
    """Degenerate fixture: a session at outdoor with no equipment — climbing
    wall blocks unreachable. continuity_main must skip cleanly, not pick a
    bodyweight high-intensity exercise."""
    res = _resolve("regeneration_easy", location="outdoor", equipment=[])
    rs = res.get("resolved_session", {})
    for blk in rs.get("blocks", []):
        if "continuity_main" not in (blk.get("block_uid") or ""):
            continue
        # Acceptable: skipped, OR resolved with low/medium intensity (Tier 3).
        if blk.get("status") == "selected":
            for ex in blk.get("selected_exercises", []):
                actual = exercise_index[ex.get("exercise_id")].get("intensity_level")
                assert _INTENSITY_ORDER[actual] <= _INTENSITY_ORDER["medium"], (
                    f"Outdoor regen continuity_main resolved to high-intensity {ex['exercise_id']}"
                )


def test_session_meta_json_required_equipment_parity():
    """B227 R1 closure: _SESSION_META.required_equipment matches JSON catalog
    for all sessions. Regression guard against future drift (D172-17 only warns)."""
    from backend.engine.planner_v2 import _SESSION_META
    sessions_dir = REPO_ROOT / SESSIONS_DIR
    drift: List[str] = []
    for sid, meta in _SESSION_META.items():
        path = sessions_dir / f"{sid}.json"
        if not path.exists():
            continue
        js = json.loads(path.read_text())
        meta_eq = sorted(meta.get("required_equipment") or [])
        json_eq = sorted(js.get("required_equipment") or [])
        if meta_eq != json_eq:
            drift.append(f"{sid}: meta={meta_eq} json={json_eq}")
    assert drift == [], "Catalog parity drift: " + "; ".join(drift)


def test_past_sessions_invariant_not_re_resolved(tmp_path):
    """B227 must NOT modify completed sessions. The week.py guard
    (B120 + B153b) skips re-resolution when status in (done, skipped) AND
    a cached `resolved` payload exists. Regression guard."""
    from backend.api.routers.week import _auto_resolve

    completed_resolved = {
        "resolved_session": {
            "blocks": [
                {"block_uid": "inline.continuity_main", "status": "selected",
                 "selected_exercises": [{"exercise_id": "dip"}]}
            ],
        },
    }
    week_plan = {
        "weeks": [{
            "days": [{
                "sessions": [
                    {"session_id": "regeneration_easy", "status": "done",
                     "location": "home", "resolved": deepcopy(completed_resolved)},
                ],
            }],
        }],
    }
    state = _base_state()
    _auto_resolve(week_plan, state, user_id=None, phase="base")
    final = week_plan["weeks"][0]["days"][0]["sessions"][0]["resolved"]
    assert final == completed_resolved, (
        "Past session was re-resolved by B227 cascade — invariant broken"
    )


def test_session_without_intensity_max_unchanged(exercise_index):
    """Backward compat: sessions whose inline blocks do NOT declare intensity_max
    must resolve identically to pre-B227. Use strength_long which has no
    intensity_max declarations."""
    res = _resolve(
        "strength_long",
        location="gym",
        equipment=["gym_boulder", "hangboard", "pullup_bar", "barbell"],
    )
    rs = res.get("resolved_session", {})
    # Just assert it resolves at all and no cascade_tier appears in any trace.
    for blk in rs.get("blocks", []):
        if blk.get("status") != "selected":
            continue
        trace = blk.get("p0_trace") or blk.get("filter_trace") or {}
        # No cascade_tier annotation when intensity_max is None.
        assert "cascade_tier" not in trace, (
            f"Block {blk.get('block_uid')} got cascade_tier={trace['cascade_tier']} "
            "in a session without intensity_max"
        )


def test_intensity_max_zero_pool_returns_none(exercise_index):
    """Extra fixture (P0 §Step 4): when ceiling kills all candidates at every tier,
    the block must skip — never escalate beyond the brief's red line.
    Direct P0 unit test."""
    catalog = list(exercise_index.values())
    # Ask for an impossible combination: role=test + intensity_max=very_low.
    # Tests are typically high-intensity max-effort assessments — pool should be empty.
    selected, trace = pick_best_exercise_p0(
        exercises=catalog,
        location="home",
        available_equipment=[],
        role_req=["test"],
        domain_req=None,
        intensity_max="very_low",
        exclude_ids=set(),
        recent_ex_ids=[],
        recent_recency_groups=set(),
    )
    # Must return None — never select a high-intensity test when ceiling=very_low.
    assert selected is None, (
        f"intensity_max=very_low + role=test should yield None, got {selected['id']}"
    )
    assert trace.get("intensity_max_applied") is True


def test_intensity_max_excludes_max_level_from_high_ceiling(exercise_index):
    """Extra: max-level exercises (limit-strength: max_hang, limit_bouldering, etc.)
    must be excluded even from intensity_max=high blocks. `max` > `high` in ordinal."""
    catalog = list(exercise_index.values())
    selected, trace = pick_best_exercise_p0(
        exercises=catalog,
        location="gym",
        available_equipment=["gym_boulder", "hangboard"],
        role_req=["main"],
        domain_req=None,
        intensity_max="high",
        exclude_ids=set(),
        recent_ex_ids=[],
        recent_recency_groups=set(),
    )
    if selected is not None:
        assert selected.get("intensity_level") != "max", (
            f"intensity_max=high must exclude max-level, got {selected['id']}"
        )
        assert _INTENSITY_ORDER[selected["intensity_level"]] <= _INTENSITY_ORDER["high"]
