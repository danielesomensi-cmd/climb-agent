"""Equipment expansion utilities — B159.

Shared by planner, resolver, and replanner to ensure consistent equipment
matching across the planning and resolution pipeline.
"""

from __future__ import annotations

import logging
from typing import Collection, List, Set

logger = logging.getLogger(__name__)

# Any of these surfaces lets a user do bouldering.  Sessions requiring
# "gym_boulder" should be placeable at any location with at least one
# of these.
BOULDER_SURFACES: frozenset[str] = frozenset({
    "gym_boulder",
    "spraywall",
    "board_kilter",
    "board_moonboard",
    "board_other",
    "homewall",
})

# Any of these implies the generic "weight" equipment tag.
WEIGHT_SUBTYPES: frozenset[str] = frozenset({
    "dumbbell",
    "kettlebell",
    "barbell",
})

KNOWN_EQUIPMENT_KEYS: frozenset[str] = frozenset({
    # climbing surfaces
    "gym_boulder", "gym_routes", "spraywall",
    "board_kilter", "board_moonboard", "board_other", "homewall",
    # finger training (generic and size-specific variants)
    "hangboard", "hangboard_20mm", "loading_pin", "pinch_block",
    # strength
    "pullup_bar", "weight", "dumbbell", "kettlebell", "barbell", "bench",
    "cable_machine", "leg_press",
    # accessories
    "band", "resistance_band", "rings", "foam_roller", "ab_wheel",
    "campus_board",
})


def expand_equipment(equipment: Collection[str]) -> List[str]:
    """Apply all equipment implication rules and return an expanded list.

    Rules:
    - If any BOULDER_SURFACE is present → implies "gym_boulder".
    - If any WEIGHT_SUBTYPE is present  → implies "weight".
    """
    eq: List[str] = list(equipment)
    for k in eq:
        if k not in KNOWN_EQUIPMENT_KEYS:
            logger.warning("Unknown equipment key: %r — will be ignored by planning engine", k)
    eq_set: Set[str] = set(eq)

    if eq_set & BOULDER_SURFACES and "gym_boulder" not in eq_set:
        eq.append("gym_boulder")

    if eq_set & WEIGHT_SUBTYPES and "weight" not in eq_set:
        eq.append("weight")

    return eq
