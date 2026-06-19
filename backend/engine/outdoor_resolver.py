"""Outdoor strategy + nutrition resolver (A225, Phase 3).

Deterministic, NO LLM. Reads the C241 catalogs
(``backend/catalog/outdoor/v1/strategy.json`` + ``nutrition.json``) and merges a
complete ``base`` entry with the applicable ``patches`` for the supplied optional
dimensions.

Merge contract (documented in ``test_outdoor_catalog.py``):
  1. Start from ``base[discipline][day_type]`` — always a complete entry, so
     ``day_type`` alone resolves fully (graceful degradation).
  2. For each supplied dimension, look up ``patches[discipline][dim][value]``.
     Each patch is a partial dict whose keys carry merge semantics by suffix:
       - ``*_override`` → REPLACES the matching base field (key minus ``_override``).
       - ``*_add`` / ``*_note`` / ``nudge`` / ``strategy_add`` → LAYERED as ordered
         modifiers (never silently replace a base field).
  3. Missing dimensions are skipped.

The resolver is pure: ``macrocycle_phase`` is just a catalog-vocabulary string
({base, build, peak, performance, deload}); reading the user's current phase and
mapping it lives in the API layer (read-only, no engine coupling — D3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
_STRATEGY_PATH = REPO_ROOT / "backend" / "catalog" / "outdoor" / "v1" / "strategy.json"
_NUTRITION_PATH = REPO_ROOT / "backend" / "catalog" / "outdoor" / "v1" / "nutrition.json"

# Deterministic order in which dimension patches are layered.
DIMENSION_ORDER = (
    "wall_angle",
    "route_length",
    "hold_style",
    "target_grade_relative",
    "macrocycle_phase",
    "condition_band",
)

_strategy_cache: Optional[Dict[str, Any]] = None
_nutrition_cache: Optional[Dict[str, Any]] = None


def _load_strategy() -> Dict[str, Any]:
    global _strategy_cache
    if _strategy_cache is None:
        with open(_STRATEGY_PATH, encoding="utf-8") as f:
            _strategy_cache = json.load(f)
    return _strategy_cache


def _load_nutrition() -> Dict[str, Any]:
    global _nutrition_cache
    if _nutrition_cache is None:
        with open(_NUTRITION_PATH, encoding="utf-8") as f:
            _nutrition_cache = json.load(f)
    return _nutrition_cache


class OutdoorResolveError(ValueError):
    """Raised on an unknown discipline / day_type (caller maps to 422)."""


def resolve_strategy(
    discipline: str,
    day_type: str,
    dimensions: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    """Resolve the strategy entry for a day_type + optional dimensions.

    Returns ``{base, modifiers, applied_dimensions, skipped_dimensions}`` where
    ``base`` is the day_type entry with ``*_override`` patches applied, and
    ``modifiers`` is the ordered list of layered notes/nudges.
    """
    catalog = _load_strategy()
    disc_base = catalog.get("base", {}).get(discipline)
    if disc_base is None:
        raise OutdoorResolveError(f"Unknown discipline: {discipline}")
    entry = disc_base.get(day_type)
    if entry is None:
        raise OutdoorResolveError(f"Unknown day_type: {day_type}")

    # Deep-ish copy: base fields are str | list[str]; copy lists so we never
    # mutate the cached catalog.
    resolved: Dict[str, Any] = {
        k: (list(v) if isinstance(v, list) else v) for k, v in entry.items()
    }

    patches = catalog.get("patches", {}).get(discipline, {})
    dims = dimensions or {}
    modifiers: List[Dict[str, str]] = []
    applied: List[str] = []
    skipped: List[str] = []

    for dim in DIMENSION_ORDER:
        value = dims.get(dim)
        if not value:
            continue
        patch = patches.get(dim, {}).get(value)
        if patch is None:
            skipped.append(f"{dim}={value}")
            continue
        applied.append(f"{dim}={value}")
        for key, text in patch.items():
            if key == "note":
                # pure "no override" marker — carry as a modifier for transparency
                modifiers.append({"dimension": dim, "value": value, "key": key, "text": text})
            elif key.endswith("_override"):
                field = key[: -len("_override")]
                resolved[field] = text
            else:
                modifiers.append({"dimension": dim, "value": value, "key": key, "text": text})

    return {
        "discipline": discipline,
        "day_type": day_type,
        "base": resolved,
        "modifiers": modifiers,
        "applied_dimensions": applied,
        "skipped_dimensions": skipped,
    }


def resolve_nutrition(discipline: str, day_type: Optional[str] = None) -> Dict[str, Any]:
    """Resolve the nutrition entry for a discipline.

    Nutrition has no day_type axis at the top level; the matching
    ``day_type_nuances`` entry is surfaced as a convenience field when present.
    """
    catalog = _load_nutrition()
    entry = catalog.get("base", {}).get(discipline)
    if entry is None:
        raise OutdoorResolveError(f"Unknown discipline: {discipline}")

    result = {k: v for k, v in entry.items()}
    nuance = None
    if day_type:
        nuance = entry.get("day_type_nuances", {}).get(day_type)
    result["day_type_nuance"] = nuance
    return result


def resolve_outdoor_day(
    discipline: str,
    day_type: str,
    dimensions: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    """Combined strategy + nutrition for an outdoor day's parameters."""
    return {
        "strategy": resolve_strategy(discipline, day_type, dimensions),
        "nutrition": resolve_nutrition(discipline, day_type),
        "safety": _load_strategy().get("safety", {}),
    }
