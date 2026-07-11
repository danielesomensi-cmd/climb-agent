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


# ── A231: guided flow generation ─────────────────────────────────────────
# The system picks the stretches: the user selects regions + total time +
# pace + rest, and gets a flattened, deterministic step sequence to run in
# an auto-advancing timer (Core Circuit UX).

PACE_MULTIPLIERS = {"quick": 0.7, "standard": 1.0, "deep": 1.4}

MIN_FLOW_MINUTES = 5
MAX_FLOW_MINUTES = 45
MIN_REST_SECONDS = 5
MAX_REST_SECONDS = 30

# Untimed releases get a timed slot inside a generated flow (an auto-advancing
# sequence can't wait forever); the user can always skip ahead early.
RELEASE_SLOT_SECONDS = 45
MIN_HOLD_SECONDS = 10


def _scaled_hold_seconds(entry: Dict[str, Any], pace: str) -> int:
    """Per-step hold duration for an entry at the given pace (5s rounding)."""
    mult = PACE_MULTIPLIERS[pace]
    base = entry["prescription_defaults"].get("work_seconds") or RELEASE_SLOT_SECONDS
    return max(MIN_HOLD_SECONDS, int(round(base * mult / 5.0)) * 5)


def _entry_steps(entry: Dict[str, Any], pace: str) -> List[Dict[str, Any]]:
    """Flatten an entry into runnable steps (per set, per side)."""
    hold = _scaled_hold_seconds(entry, pace)
    sets = entry["prescription_defaults"].get("sets") or 1
    sides = ["left", "right"] if entry.get("unilateral") else [None]
    kind = (
        "flow" if entry.get("ux_flow")
        else "release" if entry.get("mode") == "untimed_release"
        else "hold"
    )
    steps: List[Dict[str, Any]] = []
    for set_num in range(1, sets + 1):
        for side in sides:
            steps.append({
                "entry_id": entry["id"],
                "name": entry["name"],
                "body_region": entry["body_region"],
                "side": side,
                "set": set_num,
                "set_count": sets,
                "seconds": hold,
                "kind": kind,
                "cue": entry["prescription_defaults"].get("notes") or "",
                "description": entry.get("description") or "",
            })
    return steps


def _entry_cost_seconds(entry: Dict[str, Any], pace: str, rest_seconds: int) -> int:
    """Total seconds an entry consumes in the flow, including internal rests
    and the transition rest that precedes it."""
    steps = _entry_steps(entry, pace)
    holds = sum(s["seconds"] for s in steps)
    internal_rests = (len(steps) - 1) * rest_seconds
    return rest_seconds + holds + internal_rests


def generate_mobility_flow(
    state: Dict[str, Any],
    regions: List[str],
    minutes: int,
    pace: str,
    rest_seconds: int,
    date: Optional[str],
) -> Dict[str, Any]:
    """Deterministically fit a stretch sequence into a time budget.

    Selection is a round-robin across the selected regions (picker order),
    walking each region's sorted list (releases first, then holds by
    priority) so short sessions still cover every selected region. Entries
    flagged ``pre_performance_blocked`` are excluded when a session is still
    planned on ``date`` (GATE-2: when the system picks, it picks safely) and
    reported back so the UI can say what was skipped and why.
    """
    if not regions:
        raise ValueError("At least one region is required")
    unknown = [r for r in regions if r not in REGION_IDS]
    if unknown:
        raise ValueError(f"Unknown regions: {', '.join(unknown)}")
    if not (MIN_FLOW_MINUTES <= minutes <= MAX_FLOW_MINUTES):
        raise ValueError(f"minutes must be {MIN_FLOW_MINUTES}-{MAX_FLOW_MINUTES}")
    if pace not in PACE_MULTIPLIERS:
        raise ValueError(f"pace must be one of {sorted(PACE_MULTIPLIERS)}")
    if not (MIN_REST_SECONDS <= rest_seconds <= MAX_REST_SECONDS):
        raise ValueError(f"rest must be {MIN_REST_SECONDS}-{MAX_REST_SECONDS}s")

    catalog = load_mobility_catalog()
    gate2_active = bool(date) and has_planned_session_on_date(state, date)

    ordered_regions = [r for r in REGION_IDS if r in set(regions)]
    excluded: List[str] = []
    per_region: Dict[str, List[Dict[str, Any]]] = {}
    for region in ordered_regions:
        entries = [e for e in catalog if e["body_region"] == region]
        if gate2_active:
            blocked = [e for e in entries if e.get("pre_performance_blocked")]
            excluded.extend(e["name"] for e in blocked)
            entries = [e for e in entries if not e.get("pre_performance_blocked")]
        per_region[region] = sort_entries(entries)

    # Round-robin queue: rank 0 of each region, rank 1 of each region, …
    max_rank = max((len(v) for v in per_region.values()), default=0)
    queue: List[Dict[str, Any]] = []
    for rank in range(max_rank):
        for region in ordered_regions:
            if rank < len(per_region[region]):
                queue.append(per_region[region][rank])

    budget = minutes * 60
    plan: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    used = 0
    for entry in queue:
        cost = _entry_cost_seconds(entry, pace, rest_seconds)
        if plan and used + cost > budget:
            continue
        plan.append(entry)
        steps.extend(_entry_steps(entry, pace))
        used += cost

    return {
        "steps": steps,
        "entry_count": len(plan),
        "entry_ids": [e["id"] for e in plan],
        "total_seconds": used,
        "rest_seconds": rest_seconds,
        "pace": pace,
        "gate2_active": gate2_active,
        "excluded_pre_performance": excluded,
    }


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
