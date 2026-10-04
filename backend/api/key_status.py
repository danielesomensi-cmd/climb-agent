"""A294 — key-session status for API responses (read-only, fail-soft).

The engine (``backend.engine.key_sessions_v1``) is pure; this module gathers
its inputs from storage — the outdoor logs of the window, the archived weeks
of the phase when they are not hot any more — and NEVER breaks a response:
any failure returns ``None`` and is logged. The status is returned as a field
SIBLING of ``week_plan`` (never inside it), so nothing can persist it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Mapping, Optional

from backend.engine import key_sessions_v1 as ks1

logger = logging.getLogger(__name__)

#: Outdoor days read before the week (finger-hard days of the previous week
#: matter for Monday's gap) — and the whole week itself.
OUTDOOR_LOOKBACK_D = 10


def resolve_today(today: Optional[str]) -> str:
    """Client-local ``YYYY-MM-DD`` when valid, else the server clock."""
    if today:
        try:
            return datetime.strptime(str(today)[:10], "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def _outdoor_rows(user_id: Optional[str], since: date, until: date) -> Optional[list]:
    try:
        from backend.api import deps as _deps

        rows = _deps._storage.read_outdoor_logs(user_id, since.isoformat())
        out = []
        for r in rows or []:
            entry = r.get("entry") if isinstance(r, Mapping) and isinstance(r.get("entry"), Mapping) else r
            d = str((entry or {}).get("date") or "")[:10]
            if d and d <= until.isoformat():
                out.append(r)
        return out
    except Exception:
        logger.warning("A294: outdoor logs unavailable for the key status", exc_info=True)
        return None


def _archived_for_phase(state: Mapping[str, Any], user_id: Optional[str], ws: date) -> Optional[dict]:
    """Archived weeks of the current phase that are no longer hot (A221), or
    None when every phase week is still in ``week_plans``."""
    try:
        from backend.engine.macro_position import position_on

        pos = position_on(state.get("macrocycle"), ws)
        start = datetime.strptime(str((pos or {}).get("phase_start"))[:10], "%Y-%m-%d").date() if pos else None
    except Exception:
        start = None
    lo = min(ws - timedelta(days=ks1.REENTRY_WINDOW_D + 7), start or ws)
    hot = set((state.get("week_plans") or {}).keys())
    wk = lo - timedelta(days=lo.weekday())
    missing = False
    while wk < ws:
        if wk.isoformat() not in hot:
            missing = True
            break
        wk += timedelta(days=7)
    if not missing:
        return None
    try:
        from backend.api import deps as _deps

        return _deps._storage.read_archived_weeks_in_range(user_id, lo.isoformat(), ws.isoformat())
    except Exception:
        logger.warning("A294: archived weeks unavailable for the key status", exc_info=True)
        return None


def build_key_status(
    state: Mapping[str, Any],
    user_id: Optional[str],
    *,
    week_start: Optional[str] = None,
    today: Optional[str] = None,
    extra_archived: Optional[Dict[str, Any]] = None,
    with_proposals: bool = True,
) -> Optional[Dict[str, Any]]:
    """The key status of the week of ``week_start`` (default: of ``today``), or
    None (no macrocycle, no requirement in this phase, or any failure)."""
    try:
        if not state or not state.get("macrocycle"):
            return None
        td_iso = resolve_today(today)
        td = datetime.strptime(td_iso, "%Y-%m-%d").date()
        ws_d = datetime.strptime(str(week_start)[:10], "%Y-%m-%d").date() if week_start else td
        ws = ws_d - timedelta(days=ws_d.weekday())
        archived = _archived_for_phase(state, user_id, ws) or {}
        if extra_archived:
            archived = {**archived, **extra_archived}
        rows = _outdoor_rows(user_id, ws - timedelta(days=OUTDOOR_LOOKBACK_D), ws + timedelta(days=6))
        status = ks1.compute_key_status(state, td_iso, archived_weeks=archived or None, outdoor_rows=rows,
                                        week_start=ws, with_proposals=with_proposals)
        if not status.get("requirements"):
            return None
        return status
    except Exception:
        logger.warning("A294: key status failed", exc_info=True)
        return None


def build_key_conflicts(
    state: Mapping[str, Any],
    user_id: Optional[str],
    *,
    plan: Mapping[str, Any],
    events: list,
    custom_sessions: Optional[list],
    today: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """``key_sessions_v1.check_insertion`` with storage inputs (dry run)."""
    td_iso = resolve_today(today)
    ws_raw = str(plan.get("start_date") or td_iso)[:10]
    ws_d = datetime.strptime(ws_raw, "%Y-%m-%d").date()
    ws = ws_d - timedelta(days=ws_d.weekday())
    archived = _archived_for_phase(state, user_id, ws)
    rows = _outdoor_rows(user_id, ws - timedelta(days=OUTDOOR_LOOKBACK_D), ws + timedelta(days=6))
    return ks1.check_insertion(state, td_iso, plan=plan, events=events, archived_weeks=archived,
                               outdoor_rows=rows, custom_sessions=custom_sessions)
