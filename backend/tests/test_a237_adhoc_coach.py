"""A237 — Adhoc Coach v0 (conversational session composition).

Deterministic, offline tests only. The coach's LLM reply is non-deterministic
and offline-impossible to assert (all coach tests mock llm_client — see
test_coach_v1a.py), so we test what IS deterministic: the routed KB file, its
catalog-real exercise vocabulary, the assembled prompt, the suggest-only
instruction, and the suggestion chips. A live "golden transcript" is produced
manually in the brief report, not here.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

import pytest

from backend.api import deps
from backend.coach import prompt_builder, routing, service
from backend.engine import storage

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
CATALOG = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
ADHOC_L3 = prompt_builder.KNOWLEDGE_DIR / "L3" / "21_adhoc_gym_sessions.md"

C258_IDS = [
    "back_squat", "deadlift", "leg_extension", "leg_curl",
    "standing_calf_raise_loaded", "skullcrusher", "triceps_cable_pushdown",
    "dumbbell_external_rotation", "back_extension", "cable_woodchop",
    "weighted_hanging_leg_raise", "weighted_plank",
]

# Backticked snake_case tokens in the L3 that are NOT exercise ids.
NON_EXERCISE_BACKTICKS = {
    "prescription_defaults", "_index.md",
    "backend/catalog/exercises/v1/exercises.json",
}


@pytest.fixture(autouse=True)
def _clear_caches():
    routing._clear_cache()
    prompt_builder.build_static_block.cache_clear()
    yield
    routing._clear_cache()
    prompt_builder.build_static_block.cache_clear()


@pytest.fixture()
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if FIXTURE_STATE.exists():
        shutil.copy2(FIXTURE_STATE, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage_file
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_state


def _catalog_ids() -> set[str]:
    return {e["id"] for e in json.loads(CATALOG.read_text())["exercises"]}


# ── KB file ────────────────────────────────────────────────────────────────

def test_adhoc_l3_exists_and_is_lean():
    assert ADHOC_L3.exists()
    txt = ADHOC_L3.read_text(encoding="utf-8")
    tokens = len(txt) // 4
    # Lean by design so it rarely displaces context on 3-file co-routing.
    assert 1500 <= tokens <= 5000, f"adhoc L3 ~{tokens} tokens (target ~3,800)"


def test_adhoc_l3_only_references_real_catalog_ids():
    """No invented exercises: every backticked snake_case token is a real
    catalog id (or an allow-listed non-exercise term)."""
    ids = _catalog_ids()
    txt = ADHOC_L3.read_text(encoding="utf-8")
    backticked = set(re.findall(r"`([a-z][a-z0-9_]+)`", txt))
    unknown = [b for b in sorted(backticked)
               if b not in ids and b not in NON_EXERCISE_BACKTICKS]
    assert unknown == [], f"L3 references non-catalog ids: {unknown}"


def test_adhoc_l3_mentions_all_c258_exercises():
    txt = ADHOC_L3.read_text(encoding="utf-8")
    missing = [c for c in C258_IDS if c not in txt]
    assert missing == [], f"C258 exercises missing from adhoc menu: {missing}"


def test_adhoc_l3_is_spine_safe_and_rpe_only():
    txt = ADHOC_L3.read_text(encoding="utf-8").lower()
    assert "spine-safe" in txt
    assert "rpe" in txt
    # D55: no loaded crunch/sit-up exercise ids may leak in.
    for banned in ("cable_crunch", "machine_ab_crunch", "sit_up", "situp"):
        assert banned not in txt, f"spine-unsafe id in adhoc L3: {banned}"


# ── routing ────────────────────────────────────────────────────────────────

def test_gym_query_routes_to_adhoc_top():
    paths = routing.route_query(
        "I'm at a commercial gym today, build me a workout with dumbbells and a bench"
    )
    assert paths[0].name == "21_adhoc_gym_sessions.md"


def test_swap_query_routes_to_adhoc():
    paths = routing.route_query(
        "I don't feel like today's session, I'd rather do something else at the gym"
    )
    assert "21_adhoc_gym_sessions.md" in [p.name for p in paths]


def test_adhoc_does_not_hijack_unrelated_queries():
    """A pure finger/periodization query must not route to the gym file."""
    paths = routing.route_query("hangboard repeaters for finger strength this phase")
    assert "21_adhoc_gym_sessions.md" not in [p.name for p in paths]


# ── assembled prompt ───────────────────────────────────────────────────────

def test_adhoc_content_in_dynamic_block():
    state = deps.load_state(None)
    query = "I'm at a regular gym today, build me a session with a barbell"
    dynamic = prompt_builder.build_dynamic_block(state, None, query)
    first_line = ADHOC_L3.read_text(encoding="utf-8").strip().splitlines()[0]
    assert first_line in dynamic
    assert "RPE" in dynamic


def test_instruction_block_has_compose_suggest_only_rule():
    prompt_builder.build_static_block.cache_clear()
    block = prompt_builder.build_static_block()
    assert "RPE/RIR only" in block
    assert "Session Builder" in block
    # suggest-only reinforcement for composed sessions
    assert "never state or imply the session was" in block.lower()
    assert "NEVER absolute kilograms" in block


# ── suggestion chips ───────────────────────────────────────────────────────

def test_suggestions_include_adhoc_chips(isolate_state):
    uid = str(uuid.uuid4())  # fresh user → no context chips crowd them out
    sugg = service.suggested_questions(uid)
    assert any("build me a session" in s for s in sugg)
    assert any("alternatives" in s for s in sugg)
    assert len(sugg) <= service.MAX_SUGGESTIONS
