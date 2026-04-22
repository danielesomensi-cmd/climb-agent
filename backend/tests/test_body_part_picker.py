"""Unit tests for body_part_picker engine (A213)."""

from __future__ import annotations

import json
import os

import pytest

from backend.engine.body_part_picker import (
    BODY_PART_CATEGORIES,
    BODY_PART_ORDER,
    N_PER_BODY_PART,
    apply_resolver_light,
    build_body_part_index,
    classify_exercise_body_parts,
    estimate_duration_stub,
    generate_body_part_session,
    get_available_body_parts,
    resolve_equipment_mode,
    select_exercises_for_part,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXERCISES_PATH = os.path.join(
    REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json"
)


@pytest.fixture(scope="module")
def catalog():
    with open(EXERCISES_PATH) as f:
        return json.load(f)["exercises"]


@pytest.fixture(scope="module")
def by_id(catalog):
    return {e["id"]: e for e in catalog}


@pytest.fixture(scope="module")
def index(catalog):
    return build_body_part_index(catalog)


# ── Classification ─────────────────────────────────────────────────────────


def test_classify_has_entry_for_every_category(catalog):
    """Every body-part category must map to at least one exercise in the catalog."""
    idx = build_body_part_index(catalog)
    for cat in BODY_PART_ORDER:
        assert len(idx[cat]) > 0, f"Category {cat!r} has no matching exercises"


def test_classify_no_climbing_surface_exercises(catalog):
    """Boulder/route/board exercises are never classified into body parts."""
    idx = build_body_part_index(catalog)
    climbing_surfaces = {
        "gym_boulder", "gym_routes", "spraywall", "homewall",
        "board_kilter", "board_moonboard", "board_other", "campus_board",
    }
    all_classified: set[str] = set()
    for ids in idx.values():
        all_classified.update(ids)
    for ex in catalog:
        req = ex.get("equipment_required") or []
        if isinstance(req, str):
            req = [req]
        if set(req) & climbing_surfaces:
            assert ex["id"] not in all_classified, (
                f"Climbing-surface exercise {ex['id']!r} was classified"
            )


def test_classify_fingers_includes_hangboard_exercises(index):
    """Hangboard IDs must appear in fingers category."""
    hangboard_ids = [
        "max_hang_5s", "max_hang_7s", "repeater_hang_7_3", "density_hangs",
        "min_edge_hang", "dead_hang_easy",
    ]
    for eid in hangboard_ids:
        assert eid in index["fingers"], f"{eid} missing from fingers"


def test_classify_biceps_excludes_forearms(index):
    """D217 fix: wrist-curl noise must not leak into biceps."""
    wrist_ids_in_forearms = [
        eid for eid in index["forearms"]
        if "wrist" in eid.lower() or "curl" in eid.lower()
    ]
    for eid in wrist_ids_in_forearms:
        assert eid not in index["biceps"], (
            f"{eid} leaked into biceps — forearms exclusion failed"
        )


def test_classify_forearms_excludes_fingers(index):
    """Hangboard overlap must not double-count into forearms."""
    hangboard_in_fingers = [
        eid for eid in index["fingers"] if "hang" in eid.lower()
    ]
    for eid in hangboard_in_fingers:
        assert eid not in index["forearms"], (
            f"{eid} leaked into forearms — fingers exclusion failed"
        )


def test_classify_chinup_in_back_pulling_and_biceps(index):
    """chinup is an explicit include for both categories."""
    assert "chinup" in index["back_pulling"]
    assert "chinup" in index["biceps"]


def test_classify_exercise_returns_categories(catalog, by_id):
    """The per-exercise classifier matches the index."""
    ex = by_id.get("pushup")
    if ex:
        cats = classify_exercise_body_parts(ex, catalog)
        assert "chest" in cats or "triceps" in cats


# ── Equipment resolution ──────────────────────────────────────────────────


def test_resolve_equipment_bodyweight():
    assert resolve_equipment_mode("bodyweight", {}) == []


def test_resolve_equipment_home():
    state = {"equipment": {"home": ["dumbbell", "pullup_bar"]}}
    eq = resolve_equipment_mode("home", state)
    assert "dumbbell" in eq
    assert "pullup_bar" in eq
    # expand_equipment adds "weight" implication
    assert "weight" in eq


def test_resolve_equipment_gym_specific():
    state = {
        "equipment": {
            "gyms": [
                {"gym_id": "a", "name": "A", "equipment": ["gym_boulder", "hangboard"]},
                {"gym_id": "b", "name": "B", "equipment": ["dumbbell"]},
            ],
        }
    }
    eq_a = resolve_equipment_mode("gym", state, gym_id="a")
    assert "gym_boulder" in eq_a
    assert "hangboard" in eq_a
    assert "dumbbell" not in eq_a


def test_resolve_equipment_gym_missing_returns_empty():
    state = {"equipment": {"gyms": []}}
    assert resolve_equipment_mode("gym", state, gym_id="nonexistent") == []


def test_resolve_equipment_all_returns_known_keys():
    eq = resolve_equipment_mode("all", {})
    from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS
    assert set(eq) == set(KNOWN_EQUIPMENT_KEYS)


# ── Availability ──────────────────────────────────────────────────────────


def test_get_available_body_parts_shape(catalog):
    out = get_available_body_parts(catalog, equipment=[])
    assert len(out) == len(BODY_PART_ORDER)
    for entry in out:
        assert set(entry.keys()) == {
            "id", "label", "description", "icon",
            "enabled", "exercise_count", "stub_duration_min",
        }


def test_get_available_body_parts_bodyweight_has_at_least_core(catalog):
    """Bodyweight users can always do core work."""
    out = get_available_body_parts(catalog, equipment=[])
    core = next(bp for bp in out if bp["id"] == "core")
    assert core["exercise_count"] > 0
    assert core["enabled"] is True


# ── Selection ─────────────────────────────────────────────────────────────


def test_select_exercises_respects_equipment(catalog):
    """Selected exercises fit within the available equipment."""
    picks = select_exercises_for_part(
        "legs", catalog, equipment=[], already_selected=set(),
        user_state={}, seed=1,
    )
    for ex in picks:
        req = ex.get("equipment_required") or []
        assert not req, f"{ex['id']} requires {req} but equipment was empty"


def test_select_exercises_n_per_part(catalog):
    picks = select_exercises_for_part(
        "core", catalog, equipment=[], already_selected=set(),
        user_state={}, seed=1,
    )
    assert len(picks) == N_PER_BODY_PART


def test_select_exercises_dedup(catalog):
    already = set()
    picks_1 = select_exercises_for_part(
        "core", catalog, [], already, {}, seed=1,
    )
    already.update(p["id"] for p in picks_1)
    picks_2 = select_exercises_for_part(
        "core", catalog, [], already, {}, seed=1,
    )
    assert set(p["id"] for p in picks_1) & set(p["id"] for p in picks_2) == set()


def test_select_exercises_empty_pool_returns_empty(catalog):
    picks = select_exercises_for_part(
        "legs", catalog, equipment=[], already_selected=set(),
        user_state={}, n=2, seed=1,
    )
    # legs has bodyweight exercises so empty pool is unlikely — use unknown body part
    picks_unknown = select_exercises_for_part(
        "nonexistent_body_part", catalog, [], set(), {}, seed=1,
    )
    assert picks_unknown == []


def test_select_deterministic_with_seed(catalog):
    p1 = select_exercises_for_part("legs", catalog, [], set(), {}, seed=42)
    p2 = select_exercises_for_part("legs", catalog, [], set(), {}, seed=42)
    assert [e["id"] for e in p1] == [e["id"] for e in p2]


# ── Resolver light ────────────────────────────────────────────────────────


def test_resolver_light_copies_prescription_defaults(by_id):
    ex = by_id["pushup"]
    inst = apply_resolver_light(ex, {})
    assert "prescription" in inst
    pd = ex.get("prescription_defaults") or {}
    if "sets" in pd:
        assert inst["prescription"]["sets"] == pd["sets"]


def test_resolver_light_working_loads_override(by_id):
    ex = by_id["bench_press"] if "bench_press" in by_id else None
    if not ex:
        pytest.skip("bench_press not in catalog")
    state = {
        "working_loads": {
            "entries": [
                {"exercise_id": "bench_press", "next_external_load_kg": 60.0},
            ],
        }
    }
    inst = apply_resolver_light(ex, state)
    assert inst.get("load_source") == "working_loads"
    assert inst.get("suggested_external_load_kg") == 60.0


def test_resolver_light_no_baseline_graceful(by_id):
    """No crash when there's no baseline — load stays unset."""
    ex = by_id.get("max_hang_5s")
    if not ex:
        pytest.skip("max_hang_5s not in catalog")
    inst = apply_resolver_light(ex, {})
    assert inst.get("load_source") == "unset"


def test_resolver_light_copies_cues(by_id):
    """B221 parity: resolver-light propagates cues[] from catalog."""
    ex = by_id.get("romanian_deadlift")
    if not ex:
        pytest.skip("romanian_deadlift not in catalog")
    catalog_cues = ex.get("cues") or []
    assert len(catalog_cues) > 0, "fixture guard: catalog entry must have cues"
    inst = apply_resolver_light(ex, {})
    assert inst["cues"] == catalog_cues


def test_resolver_light_cues_empty_list_when_missing():
    """Exercise without a cues field → instance still has cues == [] (not missing)."""
    synthetic_ex = {
        "id": "synthetic_no_cues",
        "name": "Synthetic",
        "category": "strength_accessory",
        "load_model": "bodyweight_only",
        "prescription_defaults": {"sets": 3, "reps": 10},
    }
    inst = apply_resolver_light(synthetic_ex, {})
    assert "cues" in inst
    assert inst["cues"] == []


# ── Duration estimate ─────────────────────────────────────────────────────


def test_estimate_duration_stub_empty():
    assert estimate_duration_stub([]) == 0


def test_estimate_duration_stub_scales_with_parts():
    d1 = estimate_duration_stub(["core"])
    d2 = estimate_duration_stub(["core", "legs"])
    assert d2 > d1


def test_estimate_duration_stub_cooldown_adds_time():
    d_with = estimate_duration_stub(["core"], include_cooldown=True)
    d_without = estimate_duration_stub(["core"], include_cooldown=False)
    assert d_with > d_without


# ── Full generation ───────────────────────────────────────────────────────


def test_generate_session_metadata(catalog):
    s = generate_body_part_session(
        ["core", "legs"], "bodyweight", None, {}, catalog, seed=42,
    )
    assert s["session_mode"] == "custom_build"
    assert s["build_kind"] == "body_parts"
    assert s["is_custom"] is True
    assert s["body_parts_selected"] == ["core", "legs"]
    assert s["equipment_mode"] == "bodyweight"
    assert s["include_cooldown"] is True


def test_generate_session_has_exercises(catalog):
    s = generate_body_part_session(
        ["core", "legs"], "bodyweight", None, {}, catalog, seed=42,
    )
    # B218 Bug 4: 2 warmup exercises prepended to body-part picks.
    main_exercises = [e for e in s["exercises"] if e.get("body_part") != "warmup"]
    warmup_exercises = [e for e in s["exercises"] if e.get("body_part") == "warmup"]
    assert len(main_exercises) == 2 * N_PER_BODY_PART
    assert len(warmup_exercises) >= 1
    body_parts_in = {e["body_part"] for e in main_exercises}
    assert body_parts_in == {"core", "legs"}
    # Warmup comes first so the guided flow starts with mobility work.
    assert s["exercises"][0].get("module_role") == "warmup"


def test_generate_session_warmup_prepended(catalog):
    """B218 Bug 4: warmup block prepended with module_role=warmup."""
    s = generate_body_part_session(
        ["core"], "bodyweight", None, {}, catalog, seed=1,
    )
    warmup_ids = [
        e["exercise_id"] for e in s["exercises"]
        if e.get("module_role") == "warmup"
    ]
    assert "general_pulse_raise" in warmup_ids
    assert "dynamic_mobility_flow" in warmup_ids
    # Warmup exercises appear BEFORE any main-block exercises.
    first_main_idx = next(
        i for i, e in enumerate(s["exercises"]) if e.get("module_role") == "main"
    )
    for i in range(first_main_idx):
        assert s["exercises"][i].get("module_role") == "warmup"


def test_generate_session_top_level_sets_reps(catalog):
    """B218 Bug 2: prescription fields promoted to top-level for session-card."""
    s = generate_body_part_session(
        ["core"], "bodyweight", None, {}, catalog, seed=1,
    )
    for ex in s["exercises"]:
        # Core A206 CustomSessionExercise shape: top-level sets + notes + load_kg.
        assert "sets" in ex and isinstance(ex["sets"], int)
        assert "notes" in ex
        assert "load_kg" in ex
        # At least one of reps / work_seconds is populated at top-level.
        assert (ex.get("reps") is not None) or (ex.get("work_seconds") is not None)


def test_generate_session_deterministic_with_seed(catalog):
    s1 = generate_body_part_session(
        ["core"], "bodyweight", None, {}, catalog, seed=7,
    )
    s2 = generate_body_part_session(
        ["core"], "bodyweight", None, {}, catalog, seed=7,
    )
    ids1 = [e["exercise_id"] for e in s1["exercises"]]
    ids2 = [e["exercise_id"] for e in s2["exercises"]]
    assert ids1 == ids2


def test_generate_session_fingers_tag_set(catalog):
    s = generate_body_part_session(
        ["fingers"], "all", None, {}, catalog, seed=1,
    )
    assert s["tags"]["finger"] is True


def test_generate_session_duration_positive(catalog):
    s = generate_body_part_session(
        ["core", "legs"], "bodyweight", None, {}, catalog, seed=1,
    )
    assert s["estimated_duration_minutes"] > 0
    assert s["estimated_load_score"] >= 0


def test_generate_session_no_cooldown(catalog):
    s = generate_body_part_session(
        ["core"], "bodyweight", None, {}, catalog,
        include_cooldown=False, seed=1,
    )
    assert s["include_cooldown"] is False
