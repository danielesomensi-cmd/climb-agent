"""Milestones router — one-time achievement unlocks (A239 / A-GAMIFY-02).

GET evaluates lazily (read-driven, no hooks in write paths) and persists only
when something new unlocked. Unlocks are append-only — never revoked.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_user_id, load_state, save_state
from backend.engine.milestones_v1 import (
    evaluate_milestones,
    load_milestones_catalog,
    mark_seen,
)

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


@router.get("")
def get_milestones(user_id: Optional[str] = Depends(get_user_id)):
    """Catalog + per-user unlock status; evaluates pending unlocks first."""
    state = load_state(user_id)
    newly = evaluate_milestones(state, user_id)
    if newly:
        save_state(state, user_id)

    unlocked = {u["id"]: u for u in (state.get("milestones") or {}).get("unlocked", [])}
    catalog = load_milestones_catalog()
    items = []
    for m in catalog:
        if m.get("dynamic"):
            # Dynamic rules expand into their unlocked instances (grade PBs);
            # the rule itself is shown as a locked template when none exist.
            instances = [
                {**m, "id": u["id"], "unlocked": True,
                 "unlocked_at": u["unlocked_at"], "seen": u.get("seen", False),
                 "context": u.get("context")}
                for u in unlocked.values()
                if (u.get("context") or {}).get("rule") == m["id"]
            ]
            if instances:
                items.extend(sorted(instances, key=lambda x: x["unlocked_at"]))
            else:
                items.append({**m, "unlocked": False})
        else:
            u = unlocked.get(m["id"])
            items.append({
                **m,
                "unlocked": u is not None,
                "unlocked_at": u["unlocked_at"] if u else None,
                "seen": u.get("seen", False) if u else False,
            })

    return {
        "milestones": items,
        "unlocked_count": len(unlocked),
        "newly_unlocked": newly,
    }


@router.post("/{milestone_id}/seen")
def mark_milestone_seen(milestone_id: str, user_id: Optional[str] = Depends(get_user_id)):
    """Mark an unlocked milestone's celebration as seen (idempotent)."""
    state = load_state(user_id)
    if not mark_seen(state, milestone_id):
        raise HTTPException(status_code=404, detail="Milestone not unlocked")
    save_state(state, user_id)
    return {"ok": True, "milestone_id": milestone_id}
