"""A325 — a session duration is a measure only while it is plausible.

The players time a session on the wall clock (``now - started_at``). A player
left open overnight saved 10 h 26 min for a 1 h 30 session (2026-11-09), and
the B197 "keep the longest" rule then made the wrong value impossible to
correct. One bound, read by every writer and every reader:

- a duration above ``MAX_SESSION_DURATION_S`` is not stored (the session keeps
  no measured duration and the app shows the planned estimate);
- a stored value above the bound (written before A325) never wins over a new
  one, and the readers skip it.
"""

from __future__ import annotations

from typing import Any, Optional

#: Longest indoor session taken as real. ENGINEERING CONSTANT: the longest
#: sessions in the catalog are ~2 h 30; a day at the crag is logged as an
#: outdoor day, not through the players.
MAX_SESSION_DURATION_S = 5 * 3600


def plausible_duration(value: Any) -> Optional[float]:
    """``value`` when it is a number of seconds within the bound, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if value <= MAX_SESSION_DURATION_S else None


def keep_longest(prev: Any, new: Any) -> Any:
    """B197: a resubmit never shortens a measured duration — unless what is
    stored is not a plausible duration, which a new value always replaces."""
    return max(prev, new) if plausible_duration(prev) is not None else new
