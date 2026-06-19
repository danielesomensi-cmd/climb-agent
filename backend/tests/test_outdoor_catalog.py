"""C241 — Outdoor strategy & nutrition catalog validation.

Validates the two content catalogs authored in C241:
  - backend/catalog/outdoor/v1/strategy.json
  - backend/catalog/outdoor/v1/nutrition.json

These are pure JSON content catalogs (no engine, no network). The resolver that
consumes them lands in the NEXT brief; this test only locks the data contract.

Resolver contract (documented here, implemented next brief)
-----------------------------------------------------------
Lookup is layered:
  1. Start from base[discipline][day_type] — a COMPLETE strategy entry. day_type
     alone always yields a full entry (no patches required).
  2. For each supplied optional dimension (wall_angle, route_length, hold_style,
     target_grade_relative, macrocycle_phase, condition_band), look up
     patches[discipline][dimension][value]. Each patch is a PARTIAL object whose
     keys carry merge semantics by suffix:
        *_add / *_note / *_override / nudge / strategy_add → appended or layered
        onto the corresponding base field; never silently replace a base field
        wholesale unless the key ends in _override.
  3. Missing dimensions are simply skipped (graceful degradation).
  4. discipline is currently 'lead' only; 'boulder' can be added later by
     populating base['boulder'] and patches['boulder'] with NO schema change.

Nutrition is per-discipline (no day_type axis at the top level; day_type nuances
live inside the entry under day_type_nuances).
"""

import json
import os

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
STRATEGY_PATH = os.path.join(REPO_ROOT, "backend/catalog/outdoor/v1/strategy.json")
NUTRITION_PATH = os.path.join(REPO_ROOT, "backend/catalog/outdoor/v1/nutrition.json")

LEAD_DAY_TYPES = ["project", "onsight_flash", "volume", "scout_easy"]

STRATEGY_BASE_FIELDS = [
    "warmup_protocol",
    "target_burns",
    "rest_between_attempts_min",
    "stop_criteria",
    "skin_tips",
    "time_of_day_advice",
    "hours_plan",
    "downgrade_rule",
]

# Valid dimension → allowed values. Patches may only key off these.
VALID_DIMENSIONS = {
    "wall_angle": {"slab", "vertical", "overhang", "roof"},
    "route_length": {"short_power", "medium", "long_endurance"},
    "hold_style": {"crimp", "sloper_pinch", "mixed"},
    "target_grade_relative": {"within_limit", "at_or_above_limit"},
    "macrocycle_phase": {"base", "strength_power", "power_endurance", "performance", "deload"},
    "condition_band": {"prime", "ok", "poor_hot_humid", "poor_cold_dry"},
}

NUTRITION_TOP_FIELDS = [
    "pre_day",
    "during_by_duration",
    "hydration_by_climate",
    "caffeine_timing",
    "post_day",
    "climate_addons",
    "day_type_nuances",
]


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def strategy():
    return _load(STRATEGY_PATH)


@pytest.fixture(scope="module")
def nutrition():
    return _load(NUTRITION_PATH)


# --------------------------------------------------------------------------- #
# Parse
# --------------------------------------------------------------------------- #

def test_both_files_parse():
    assert isinstance(_load(STRATEGY_PATH), dict)
    assert isinstance(_load(NUTRITION_PATH), dict)


# --------------------------------------------------------------------------- #
# Strategy: complete base entries for all 4 lead day_types
# --------------------------------------------------------------------------- #

def test_strategy_has_lead_base(strategy):
    assert "lead" in strategy["base"], "base must contain a 'lead' discipline block"


@pytest.mark.parametrize("day_type", LEAD_DAY_TYPES)
def test_strategy_base_entry_complete(strategy, day_type):
    lead = strategy["base"]["lead"]
    assert day_type in lead, f"missing base entry for lead/{day_type}"
    entry = lead[day_type]

    for field in STRATEGY_BASE_FIELDS:
        assert field in entry, f"lead/{day_type} missing field '{field}'"
        value = entry[field]
        # None empty: non-empty string, or non-empty list of non-empty strings
        if isinstance(value, list):
            assert value, f"lead/{day_type}.{field} is an empty list"
            assert all(
                isinstance(x, str) and x.strip() for x in value
            ), f"lead/{day_type}.{field} has empty list items"
        else:
            assert isinstance(value, str) and value.strip(), (
                f"lead/{day_type}.{field} is empty"
            )


def test_strategy_no_extra_day_types(strategy):
    assert set(strategy["base"]["lead"].keys()) == set(LEAD_DAY_TYPES)


def test_strategy_list_fields_are_lists(strategy):
    for day_type in LEAD_DAY_TYPES:
        entry = strategy["base"]["lead"][day_type]
        assert isinstance(entry["stop_criteria"], list)
        assert isinstance(entry["skin_tips"], list)


# --------------------------------------------------------------------------- #
# Strategy: patches only reference valid dimension values
# --------------------------------------------------------------------------- #

def test_strategy_patches_dimensions_valid(strategy):
    patches = strategy["patches"]["lead"]
    for dimension, values in patches.items():
        assert dimension in VALID_DIMENSIONS, f"unknown patch dimension '{dimension}'"
        for value in values:
            assert value in VALID_DIMENSIONS[dimension], (
                f"patch {dimension}.{value} is not a valid value "
                f"(allowed: {sorted(VALID_DIMENSIONS[dimension])})"
            )


def test_strategy_patches_are_partial_dicts(strategy):
    patches = strategy["patches"]["lead"]
    for dimension, values in patches.items():
        for value, patch in values.items():
            assert isinstance(patch, dict) and patch, (
                f"patch {dimension}.{value} must be a non-empty dict"
            )
            for k, v in patch.items():
                assert isinstance(v, str) and v.strip(), (
                    f"patch {dimension}.{value}.{k} is empty"
                )


def test_strategy_declared_dimensions_match_validator(strategy):
    """The catalog's self-declared dimensions block must match the test's truth."""
    declared = strategy["dimensions"]
    for dim, allowed in VALID_DIMENSIONS.items():
        assert dim in declared, f"catalog dimensions missing '{dim}'"
        assert set(declared[dim]) == allowed, f"declared values for '{dim}' drifted"


def test_strategy_safety_copy_present(strategy):
    safety = strategy["safety"]
    assert safety["no_cold_full_crimp"]
    assert safety["no_static_forearm_stretch"]
    assert safety["fueling_framing_only"]


# --------------------------------------------------------------------------- #
# Nutrition
# --------------------------------------------------------------------------- #

def test_nutrition_has_lead_base(nutrition):
    assert "lead" in nutrition["base"]


def test_nutrition_base_complete(nutrition):
    entry = nutrition["base"]["lead"]
    for field in NUTRITION_TOP_FIELDS:
        assert field in entry, f"nutrition lead missing '{field}'"

    # nested required keys
    assert set(entry["during_by_duration"].keys()) >= {"short", "long"}
    assert "precool" in entry["climate_addons"]
    assert set(entry["day_type_nuances"].keys()) >= {"project", "volume"}

    # no empty leaf strings
    for field in ("pre_day", "hydration_by_climate", "caffeine_timing", "post_day"):
        assert entry[field].strip(), f"nutrition lead.{field} is empty"
    for k, v in entry["during_by_duration"].items():
        assert v.strip(), f"during_by_duration.{k} is empty"


def test_nutrition_framing_is_fueling_only(nutrition):
    """D64: framing must never reference weight/deficit."""
    framing = nutrition["framing"].lower()
    assert "fueling" in framing or "performance" in framing


# --------------------------------------------------------------------------- #
# Extensibility: boulder can be added with no schema change
# --------------------------------------------------------------------------- #

def test_discipline_keyed_structure(strategy, nutrition):
    """base/patches are keyed by discipline → adding 'boulder' is purely additive."""
    assert "lead" in strategy["base"]
    assert "lead" in strategy["patches"]
    assert "lead" in nutrition["base"]
    # Only 'lead' populated for now (C241 scope).
    assert set(strategy["base"].keys()) == {"lead"}
