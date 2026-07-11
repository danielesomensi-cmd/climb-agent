"""Mobility & Stretching free-session pool engine (A230).

Loads the dedicated ``backend/catalog/mobility/v1/mobility.json`` catalog.
This catalog is intentionally SEPARATE from ``exercises.json``: it must never
be reachable by the climbing-session resolver (``resolve_session``) or the
Body Part Picker. It is served only through the ``/api/mobility`` router for
the free-session "Stretching & Mobility" surface.

GATE-1 is enforced by placement (free-session area only). GATE-2 is a soft,
read-only warning: forearm-flexor stretches flagged ``pre_performance_blocked``
get a warning when a climbing session is still planned on the same day —
static forearm stretching can reduce grip strength for up to an hour (CUE-02).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MOBILITY_CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "mobility" / "v1" / "mobility.json"

# Picker sort order (KB brief §1.2) — id → display label.
REGION_ORDER: List[Dict[str, str]] = [
    {"id": "forearms_wrists", "label": "Forearms & Wrists"},
    {"id": "hips_glutes", "label": "Hips & Glutes"},
    {"id": "chest_anterior_shoulder", "label": "Chest & Anterior Shoulder"},
    {"id": "thoracic_spine", "label": "Thoracic Spine"},
    {"id": "hip_flexors_quads", "label": "Hip Flexors & Quads"},
    {"id": "adductors_groin", "label": "Adductors & Groin"},
    {"id": "lats", "label": "Lats"},
    {"id": "shoulders_scapula", "label": "Shoulders & Scapula"},
    {"id": "hamstrings", "label": "Hamstrings"},
    {"id": "calves_ankles", "label": "Calves & Ankles"},
    {"id": "spine_rotation_obliques", "label": "Spine Rotation & Obliques"},
]

REGION_IDS = [r["id"] for r in REGION_ORDER]

GATE2_WARNING = (
    "Climbing session scheduled later today — skip forearm-flexor stretches, "
    "they can reduce grip strength for up to 1h."
)

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

_CATALOG_CACHE: Optional[List[Dict[str, Any]]] = None


def load_mobility_catalog() -> List[Dict[str, Any]]:
    """Load (and cache) the mobility catalog entries."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        with open(MOBILITY_CATALOG_PATH, encoding="utf-8") as f:
            _CATALOG_CACHE = json.load(f).get("entries", [])
    return _CATALOG_CACHE


def sort_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort entries within a region: releases first, then holds by priority.

    "Roll first, stretch second" (Hörst) — ``untimed_release`` entries lead,
    then ``timed_hold`` by priority (high > medium > low). Name is the final
    tiebreaker to keep the order deterministic.
    """
    def key(e: Dict[str, Any]):
        mode_rank = 0 if e.get("mode") == "untimed_release" else 1
        return (mode_rank, _PRIORITY_RANK.get(e.get("priority"), 3), e.get("name", ""))

    return sorted(entries, key=key)


def has_planned_session_on_date(state: Dict[str, Any], date: str) -> bool:
    """Read-only check: is any session still planned on ``date``?

    Conservative GATE-2 approximation: any not-yet-done planned session that
    day counts as "climbing later today" (almost every planned session loads
    the fingers). Never mutates the plan.
    """
    week_plan = state.get("current_week_plan") or {}
    for week in week_plan.get("weeks", []):
        for day in week.get("days", []):
            if day.get("date") == date:
                for sess in day.get("sessions", []):
                    if sess.get("status") == "planned":
                        return True
    return False


def build_pool_payload(state: Dict[str, Any], date: Optional[str]) -> Dict[str, Any]:
    """Build the full pool payload: regions in picker order with sorted entries.

    When ``date`` is provided and a session is still planned that day, entries
    flagged ``pre_performance_blocked`` carry a ``warning`` string (GATE-2,
    soft — entries are never removed from the payload).
    """
    catalog = load_mobility_catalog()
    gate2_active = bool(date) and has_planned_session_on_date(state, date)

    regions: List[Dict[str, Any]] = []
    for region in REGION_ORDER:
        entries = [dict(e) for e in catalog if e.get("body_region") == region["id"]]
        for e in entries:
            if gate2_active and e.get("pre_performance_blocked"):
                e["warning"] = GATE2_WARNING
        regions.append({
            "id": region["id"],
            "label": region["label"],
            "count": len(entries),
            "entries": sort_entries(entries),
        })

    return {"regions": regions, "gate2_active": gate2_active}
