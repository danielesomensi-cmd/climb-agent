"""State router — GET / PUT / DELETE /api/state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from fastapi import APIRouter

from backend.api.deps import EMPTY_TEMPLATE, load_state, save_state

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
def get_state():
    """Return the full user_state.json."""
    return load_state()


@router.put("")
def put_state(patch: Dict[str, Any]):
    """Deep-merge patch into existing state."""
    state = load_state()
    _deep_merge(state, patch)
    save_state(state)
    return state


@router.delete("")
def delete_state():
    """Reset state to minimal empty template."""
    state = deepcopy(EMPTY_TEMPLATE)
    save_state(state)
    return {"status": "reset", "state": state}
