"""B387 — storage codec for the user_state blob.

``current_week_plan`` is, in practice, a byte-for-byte duplicate of
``week_plans[<its start_date>]``: every writer assigns the same plan to both
(week.py, replanner, feedback, auto_reschedule, key_sessions). On Daniele's
state that duplicate was 125 KB of a 678 KB JSONB row, read and rewritten on
every request.

The codec removes the duplicate **at the storage boundary only**:

- :func:`pack` (on write) — when ``week_plans[K] == current_week_plan`` with
  ``K = current_week_plan["start_date"]``, the stored blob carries
  ``current_week_key: K`` instead of the plan. In every other case (the two
  copies diverge, ``K`` is not a hot week, no start_date) the full copy is
  stored exactly as before: nothing can be lost.
- :func:`unpack` (on read) — rebuilds ``current_week_plan`` as an independent
  **deep copy** of ``week_plans[K]`` and drops the pointer. A JSON load always
  produced two equal, independent copies, so in-memory semantics are identical
  to before the codec: no reader or writer has to change, and nothing that
  mutates one copy can silently mutate the other.

Both directions are pure (the caller's dict is never mutated by ``pack``) and
idempotent; a legacy blob without ``current_week_key`` reads unchanged.
The pointer restored is the stored one, never "today", so a Monday rollover
behaves exactly as with the full copy (B216 self-heal in week.py).

Kill switch: ``STATE_CODEC_PACK=0`` (read at call time) writes the full copy
again. Reads always understand both formats, so the switch is safe either way.
"""

from __future__ import annotations

import copy
import os
from typing import Any, Dict, Optional

CWP_KEY = "current_week_plan"
POINTER_KEY = "current_week_key"


def pack_enabled() -> bool:
    return os.environ.get("STATE_CODEC_PACK", "1") != "0"


def _pointer_for(state: Dict[str, Any]) -> Optional[str]:
    """The week key the current plan duplicates, or None if it is not a pure duplicate."""
    cwp = state.get(CWP_KEY)
    if not isinstance(cwp, dict):
        return None
    key = cwp.get("start_date")
    if not isinstance(key, str) or not key:
        return None
    hot = state.get("week_plans")
    if not isinstance(hot, dict) or key not in hot:
        return None
    return key if hot[key] == cwp else None


def pack(state: Dict[str, Any]) -> Dict[str, Any]:
    """Stored form of ``state``. Returns a shallow copy; ``state`` is untouched."""
    if not isinstance(state, dict):
        return state
    out = dict(state)
    out.pop(POINTER_KEY, None)
    if not pack_enabled():
        return out
    key = _pointer_for(state)
    if key is not None:
        out.pop(CWP_KEY, None)
        out[POINTER_KEY] = key
    return out


def unpack(stored: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """In-memory form of a stored blob (mutates and returns ``stored``)."""
    if not isinstance(stored, dict):
        return stored
    key = stored.pop(POINTER_KEY, None)
    if key is None or stored.get(CWP_KEY) is not None:
        # Legacy blob, or a full copy stored next to a stale pointer: the copy wins.
        return stored
    hot = stored.get("week_plans")
    if isinstance(hot, dict) and isinstance(hot.get(key), dict):
        stored[CWP_KEY] = copy.deepcopy(hot[key])
    # A pointer to a week that is gone cannot be produced by pack(); if it ever
    # happens, current_week_plan stays absent, which every reader already
    # treats as "not generated yet" (week.py regenerates it).
    return stored
