"""A301 — the guard alerts of a week for API responses (read-only, fail-soft).

``backend.engine.guards_v1`` is pure; this module gathers its inputs from the
user state (the previous week's days for the Sunday→Monday gap, the athlete's
today, the state itself for heavy-pull loads and trips) and NEVER breaks a
response: any failure returns ``[]`` and is logged. The alerts are returned as
a field SIBLING of ``week_plan`` (never inside it), like ``key_status``, so
nothing can persist them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional

from backend.api.key_status import resolve_today
from backend.engine import guards_v1

logger = logging.getLogger(__name__)


def prev_week_days(state: Mapping[str, Any], start_date: Optional[str]) -> Optional[list]:
    """Days of the week preceding *start_date* (hot store only, as the
    replanner's own ``_prev_week_days``)."""
    if not start_date:
        return None
    try:
        prev_monday = (datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date() - timedelta(days=7)).isoformat()
    except ValueError:
        return None
    prev_plan = (state.get("week_plans") or {}).get(prev_monday)
    if not isinstance(prev_plan, Mapping):
        return None
    try:
        return (prev_plan.get("weeks") or [{}])[0].get("days") or None
    except (IndexError, AttributeError):
        return None


def next_week_days(state: Mapping[str, Any], start_date: Optional[str]) -> Optional[list]:
    """B372: days of the week following *start_date* — read by the guards for
    a declared crag day on its Monday only."""
    if not start_date:
        return None
    try:
        next_monday = (datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date() + timedelta(days=7)).isoformat()
    except ValueError:
        return None
    nxt = (state.get("week_plans") or {}).get(next_monday)
    if not isinstance(nxt, Mapping):
        return None
    try:
        return (nxt.get("weeks") or [{}])[0].get("days") or None
    except (IndexError, AttributeError):
        return None


_NO_USER = object()


def outdoor_rows_for(user_id: Optional[str], start_date: Optional[str]) -> Optional[list]:
    """B372: the ``outdoor_logs`` rows of the previous week + the week of
    *start_date* — the route log that tells a hard crag day from an easy one.
    ``None`` when unavailable (the guards then read ``state.outdoor_log``)."""
    if not start_date:
        return None
    try:
        ws = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    from backend.api.key_status import _outdoor_rows

    return _outdoor_rows(user_id, ws - timedelta(days=7), ws + timedelta(days=6))


def build_guard_warnings(
    state: Mapping[str, Any], plan: Optional[Mapping[str, Any]], today: Optional[str] = None,
    *, user_id: Any = _NO_USER,
) -> List[Dict[str, Any]]:
    """``guards_v1.evaluate`` of *plan* with storage inputs; ``[]`` on failure.
    With *user_id* the outdoor route log of the window is read (B372)."""
    if not isinstance(plan, Mapping):
        return []
    try:
        rows = None if user_id is _NO_USER else outdoor_rows_for(user_id, plan.get("start_date"))
        return guards_v1.evaluate(
            plan, prev_week_days(state or {}, plan.get("start_date")), resolve_today(today), state or {},
            outdoor_rows=rows, next_days=next_week_days(state or {}, plan.get("start_date")),
        )
    except Exception:
        logger.warning("A301: guard alerts failed", exc_info=True)
        return []


def build_week_guard_warnings(
    state: Mapping[str, Any], plan: Optional[Mapping[str, Any]], today: Optional[str] = None,
    *, user_id: Any = _NO_USER,
) -> List[Dict[str, Any]]:
    """A305: the WEEK-level alerts of *plan* (``low_rest_days``) — a separate
    sibling (``week_guard_warnings``) so the session-level ``guard_warnings``
    contract is unchanged. ``[]`` on failure."""
    if not isinstance(plan, Mapping):
        return []
    try:
        rows = None if user_id is _NO_USER else outdoor_rows_for(user_id, plan.get("start_date"))
        return guards_v1.evaluate_week(
            plan, prev_week_days(state or {}, plan.get("start_date")), resolve_today(today), state or {},
            outdoor_rows=rows, next_days=next_week_days(state or {}, plan.get("start_date")),
        )
    except Exception:
        logger.warning("A305: week guard alerts failed", exc_info=True)
        return []


def messages_for(warnings: List[Mapping[str, Any]], date_iso: Optional[str], slot: Optional[str] = None) -> List[str]:
    """The messages of the alerts that involve the session at *date_iso* /
    *slot* — the legacy ``warnings: [str]`` of quick-add and override."""
    if not date_iso:
        return []
    return [str(w.get("message")) for w in warnings if guards_v1.involves(w, date_iso, slot)]
