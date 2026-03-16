"""State router — GET / PUT / DELETE /api/state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from backend.api.deps import EMPTY_TEMPLATE, ensure_monday, get_user_id, load_state, save_state
from backend.engine import storage
from backend.engine.state_checks import is_macrocycle_stale

router = APIRouter(prefix="/api/state", tags=["state"])


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *patch* into *base* (mutates base)."""
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


@router.get("")
def get_state(user_id: Optional[str] = Depends(get_user_id)):
    """Return the full user_state.json."""
    return load_state(user_id)


@router.put("")
def put_state(patch: Dict[str, Any], user_id: Optional[str] = Depends(get_user_id)):
    """Deep-merge patch into existing state."""
    # Auto-correct macrocycle.start_date to Monday if present in patch
    mc_patch = patch.get("macrocycle")
    if isinstance(mc_patch, dict) and "start_date" in mc_patch:
        mc_patch["start_date"] = ensure_monday(mc_patch["start_date"])
    state = load_state(user_id)
    _deep_merge(state, patch)
    save_state(state, user_id)
    return state


@router.get("/status")
def get_state_status(user_id: Optional[str] = Depends(get_user_id)):
    """Lightweight consistency check — no mutations."""
    state = load_state(user_id)
    return {"is_macrocycle_stale": is_macrocycle_stale(state)}


def _clear_outdoor_logs(user_id: Optional[str]) -> int:
    """Remove all outdoor JSONL log files for the user. Returns count removed."""
    return storage.delete_all_outdoor_logs(user_id)


@router.delete("")
def delete_state(user_id: Optional[str] = Depends(get_user_id)):
    """Reset state to minimal empty template and clear outdoor logs."""
    state = deepcopy(EMPTY_TEMPLATE)
    save_state(state, user_id)
    _clear_outdoor_logs(user_id)
    return {"status": "reset", "state": state}
