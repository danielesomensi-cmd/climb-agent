"""Cross-cutting state consistency checks.

Pure functions — no side effects, no I/O.
"""

from typing import Any, Dict

# Minimum per-axis delta (0-100 scale) to consider the macrocycle stale.
DIRTY_STATE_THRESHOLD = 5

_PROFILE_AXES = (
    "finger_strength",
    "pulling_strength",
    "power_endurance",
    "technique",
    "endurance",
    "body_composition",
)


def is_macrocycle_stale(state: Dict[str, Any]) -> bool:
    """Return True when the current assessment profile has diverged
    from the snapshot stored inside the macrocycle.

    Rules:
    - False if macrocycle or its assessment_snapshot is missing.
    - False if assessment.profile is missing.
    - True  if **any** axis differs by >= DIRTY_STATE_THRESHOLD points.
    """
    macrocycle = state.get("macrocycle")
    if not macrocycle:
        return False

    snapshot = macrocycle.get("assessment_snapshot")
    if not snapshot:
        return False

    profile = (state.get("assessment") or {}).get("profile")
    if not profile:
        return False

    for axis in _PROFILE_AXES:
        current = profile.get(axis, 0)
        saved = snapshot.get(axis, 0)
        if abs(current - saved) >= DIRTY_STATE_THRESHOLD:
            return True

    return False
