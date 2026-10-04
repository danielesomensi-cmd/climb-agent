"""A297 (R7b) — the ONE place the engine's athlete context enters an LLM prompt.

Before A297 every brief of the 2026-10-04 programme added its own lines to the
coach prompt — B364 the official maxima and anchored loads in the baselines
section, A294 a ``## Key sessions this week`` block — and the ad-hoc composer
saw none of it: it would compose max hangs the day before a finger key session
or a weighted pull-up at 2RM the evening before a limit boulder. A297 routes
all of it (B364 maxima + anchors, A295 pain / fatigue / retest signals, A294 key
sessions, A296 limit log, the recovery guards and the variety collector)
through ``backend.engine.athlete_context`` and this module:

- ``chat_block(state, user_id, today)`` → the English ``## Athlete context``
  section of the coach chat prompt (dynamic, never cached);
- ``composer_context(state, user_id, day)`` → the context dict the ad-hoc
  composer and the deterministic builder read (``ATHLETE CONTEXT`` block, pool
  markers, guard exclusions, recency).

Flag: ``COACH_ATHLETE_CONTEXT`` — default ON, only the literal ``0`` turns it
off (like ``RATE_LIMIT_ENABLED``). Read at call time, so a Railway variable
change applies without a deploy. With the flag off every consumer behaves
exactly as before A297.

Fail-soft by construction: storage reads and the context build are wrapped;
any failure returns ``None`` and the caller keeps its pre-A297 path. Nothing
here writes anything.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

#: Look-back of the archived weeks read for the context: the variety window
#: (3 weeks), the guards (8 days back) and the low-confidence window of a test
#: up to ~6 weeks old (21 days before it).
ARCHIVE_LOOKBACK_D = 63
#: Outdoor logs read for the context (try-hard window, 28 days).
OUTDOOR_LOOKBACK_D = 28


def enabled() -> bool:
    """``COACH_ATHLETE_CONTEXT`` (default ON; only the literal ``0`` disables)."""
    return os.getenv("COACH_ATHLETE_CONTEXT", "1").strip() != "0"


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _archived_weeks(state: Mapping[str, Any], user_id: Optional[str], day: date) -> Optional[dict]:
    """Archived weeks (A221 cold store) of the look-back window, only when a
    week of it is no longer hot. None when not needed or on failure."""
    lo = day - timedelta(days=ARCHIVE_LOOKBACK_D)
    hot = set((state.get("week_plans") or {}).keys())
    wk = lo - timedelta(days=lo.weekday())
    this_monday = day - timedelta(days=day.weekday())
    missing = False
    while wk < this_monday:
        if wk.isoformat() not in hot:
            missing = True
            break
        wk += timedelta(days=7)
    if not missing:
        return None
    try:
        from backend.engine import storage

        return storage.read_archived_weeks_in_range(user_id, lo.isoformat(), day.isoformat()) or None
    except Exception:
        logger.warning("A297: archived weeks unavailable for the athlete context", exc_info=True)
        return None


def _outdoor_rows(user_id: Optional[str], day: date) -> Optional[list]:
    try:
        from backend.engine import storage

        return storage.read_outdoor_logs(user_id, since_date=(day - timedelta(days=OUTDOOR_LOOKBACK_D)).isoformat())
    except Exception:
        logger.warning("A297: outdoor logs unavailable for the athlete context", exc_info=True)
        return None


def load_context(
    state: Mapping[str, Any],
    user_id: Optional[str],
    day: Any,
    *,
    with_proposals: bool,
) -> Optional[Dict[str, Any]]:
    """``build_athlete_context`` with its storage inputs, or None (flag off,
    no state, or any failure)."""
    if not enabled() or not state:
        return None
    try:
        from backend.engine.athlete_context import build_athlete_context

        d = _as_date(day) if day else date.today()
        return build_athlete_context(
            state, d,
            archived_weeks=_archived_weeks(state, user_id, d),
            outdoor_rows=_outdoor_rows(user_id, d),
            with_proposals=with_proposals,
            include_next_week=False,
        )
    except Exception:
        logger.warning("A297: athlete context failed — prompt without it", exc_info=True)
        return None


def chat_block(state: Mapping[str, Any], user_id: Optional[str], today_iso: str) -> Optional[str]:
    """The ``## Athlete context`` section of the coach chat prompt, or None."""
    ctx = load_context(state, user_id, today_iso, with_proposals=True)
    if ctx is None:
        return None
    try:
        from backend.engine.athlete_context import render_coach_block

        return render_coach_block(ctx) or None
    except Exception:
        logger.warning("A297: coach block render failed", exc_info=True)
        return None


def composer_context(state: Mapping[str, Any], user_id: Optional[str], day: Any) -> Optional[Dict[str, Any]]:
    """The athlete context of the session day for the ad-hoc composer (no
    catch-up proposals: they are replanner simulations the composer never
    shows), or None."""
    return load_context(state, user_id, day, with_proposals=False)


__all__ = ["enabled", "load_context", "chat_block", "composer_context",
           "ARCHIVE_LOOKBACK_D", "OUTDOOR_LOOKBACK_D"]
