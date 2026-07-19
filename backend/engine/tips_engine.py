"""Daily tips engine — deterministic per-user feature-discovery tip rotation.

A234 (A-DAILYTIP). Selection is stateless: each user gets a stable
pseudo-random permutation of the tip pool (md5 of user_id + tip_id), and the
calendar day indexes into it. No repeat within pool-size days for the same
user; different users see different tips on the same day. Dismissals are
per-day bookkeeping in ``user_state.tips_seen`` — they hide the card for the
rest of the day but never alter the rotation.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

_TIPS_CATALOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "daily_tips", "v1", "feature_discovery.json"
)

_MAX_SEEN_HISTORY = 100


@functools.lru_cache(maxsize=1)
def _load_tips() -> List[Dict[str, Any]]:
    """Load and cache the daily tips catalog."""
    path = os.path.normpath(_TIPS_CATALOG_PATH)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tips", [])


def tip_exists(tip_id: str) -> bool:
    return any(t.get("id") == tip_id for t in _load_tips())


def _user_order_key(user_id: str, tip_id: str) -> str:
    return hashlib.md5(f"{user_id}|{tip_id}".encode("utf-8")).hexdigest()


def get_daily_tip(user_id: str, target_date: date) -> Optional[Dict[str, Any]]:
    """Return the tip of the day for this user, or None if the pool is empty."""
    tips = _load_tips()
    if not tips:
        return None
    ordered = sorted(tips, key=lambda t: _user_order_key(user_id, t.get("id", "")))
    idx = target_date.toordinal() % len(ordered)
    return dict(ordered[idx])


def is_dismissed(state: Dict[str, Any], tip_id: str, target_date: date) -> bool:
    """True if this tip was already dismissed on this calendar day."""
    iso = target_date.isoformat()
    return any(
        entry.get("id") == tip_id and entry.get("date") == iso
        for entry in state.get("tips_seen", [])
    )


def record_dismissal(state: Dict[str, Any], tip_id: str, target_date: date) -> None:
    """Append a dismissal to ``state.tips_seen`` (idempotent per id+day, trimmed)."""
    if is_dismissed(state, tip_id, target_date):
        return
    seen = state.setdefault("tips_seen", [])
    seen.append({"id": tip_id, "date": target_date.isoformat()})
    if len(seen) > _MAX_SEEN_HISTORY:
        state["tips_seen"] = seen[-_MAX_SEEN_HISTORY:]
