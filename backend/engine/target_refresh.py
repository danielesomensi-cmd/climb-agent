"""A291 — grade targets of pencil-edited future sessions.

DECISIONS (Grades line): "_user_edited future sessions keep their exercises;
only targets refresh."

``_auto_resolve`` (week and replanner routers) never re-resolves a session the
user edited with the pencil (B153b): re-resolving would throw away the
exercises the user chose. The side effect was that such a session kept the
grade targets computed when it was last resolved — so after A291 changed the
grade arithmetic ('+' kept, half-grade steps) one plan could show two
conventions side by side.

``refresh_edited_session_targets`` recomputes, with the same ``inject_targets``
the resolver uses, ONLY the grade-target fields of the instances the engine
placed in the session. Nothing else moves:

- exercise_ids, prescriptions, order, user-added instances: untouched;
- loads (``suggested_*_kg`` and friends): untouched — the scope is the grade
  ladder, not the load anchors;
- done / skipped sessions and sessions dated before today: never touched
  (immutability pillar).
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DIR = REPO_ROOT / "backend" / "catalog" / "sessions" / "v1"

# The grade-target fields inject_targets writes into ``inst["suggested"]``.
GRADE_TARGET_KEYS = (
    "suggested_grade",
    "grade_ref",
    "grade_offset",
    "grade_scale",
    "grade_source",
    "suggested_boulder_target",
)


def _catalog_session(session_id: str) -> Optional[Dict[str, Any]]:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not session_id or not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def refresh_edited_session_targets(
    session_entry: Dict[str, Any],
    day_date: Optional[str],
    state: Dict[str, Any],
    today: Optional[str] = None,
) -> bool:
    """Refresh the grade targets of a future, pending, ``_user_edited`` session
    in place. Returns True when at least one instance changed."""
    if not session_entry.get("_user_edited"):
        return False
    if session_entry.get("status") in ("done", "skipped"):
        return False
    if session_entry.get("is_custom"):
        return False
    today = today or _date.today().isoformat()
    if not day_date or str(day_date) < today:
        return False
    resolved = session_entry.get("resolved") or {}
    instances = (resolved.get("resolved_session") or {}).get("exercise_instances") or []
    if not instances:
        return False
    session_id = str(session_entry.get("session_id") or "")
    catalog = _catalog_session(session_id)
    if catalog is None:
        return False

    from backend.engine.progression_v1 import inject_targets

    # The engine's own instances only: a hand-added exercise never carried
    # targets (it is re-appended after resolution), and it keeps not carrying
    # them.
    engine_idx = [i for i, inst in enumerate(instances) if inst.get("source") != "user_added"]
    if not engine_idx:
        return False

    probe = []
    for i in engine_idx:
        inst = deepcopy(instances[i])
        sugg = dict(inst.get("suggested") or {})
        # Start clean so a target that no longer applies (unknown grade) goes
        # away, exactly as on a fresh resolution.
        for key in GRADE_TARGET_KEYS:
            sugg.pop(key, None)
        inst["suggested"] = sugg
        probe.append(inst)

    intent = catalog.get("intent") or {}
    intent_str = intent if isinstance(intent, str) else (intent.get("primary_goal") or "")
    target_state = deepcopy(state)
    target_state["context"] = {
        **(target_state.get("context") or {}),
        "location": session_entry.get("location", "home"),
        "gym_id": session_entry.get("gym_id"),
        "target_date": day_date,
        "date": day_date,
    }
    pseudo_day = {
        "date": day_date,
        "sessions": [{
            "session_id": session_id,
            "intent": intent_str,
            "location": session_entry.get("location", "home"),
            "gym_id": session_entry.get("gym_id"),
            "tags": catalog.get("tags") or {},
            "exercise_instances": probe,
        }],
    }
    try:
        enriched = inject_targets(pseudo_day, target_state)
    except Exception:
        logger.warning("A291: target refresh failed for %r", session_id, exc_info=True)
        return False
    fresh = enriched["sessions"][0]["exercise_instances"]
    if len(fresh) != len(engine_idx):
        return False

    changed = False
    for i, new_inst in zip(engine_idx, fresh):
        inst = instances[i]
        old = inst.get("suggested") or {}
        new_sugg = new_inst.get("suggested") or {}
        merged = dict(old)
        for key in GRADE_TARGET_KEYS:
            if key in new_sugg:
                merged[key] = new_sugg[key]
            else:
                merged.pop(key, None)
        if merged != old:
            if merged or "suggested" in inst:
                inst["suggested"] = merged
            changed = True
    return changed
