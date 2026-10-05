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


def build_guard_warnings(
    state: Mapping[str, Any], plan: Optional[Mapping[str, Any]], today: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """``guards_v1.evaluate`` of *plan* with storage inputs; ``[]`` on failure."""
    if not isinstance(plan, Mapping):
        return []
    try:
        return guards_v1.evaluate(
            plan, prev_week_days(state or {}, plan.get("start_date")), resolve_today(today), state or {},
        )
    except Exception:
        logger.warning("A301: guard alerts failed", exc_info=True)
        return []


def messages_for(warnings: List[Mapping[str, Any]], date_iso: Optional[str], slot: Optional[str] = None) -> List[str]:
    """The messages of the alerts that involve the session at *date_iso* /
    *slot* — the legacy ``warnings: [str]`` of quick-add and override."""
    if not date_iso:
        return []
    return [str(w.get("message")) for w in warnings if guards_v1.involves(w, date_iso, slot)]
