"""User router — GET /api/user/export, POST /api/user/import.

B320 retired the recovery-code endpoints (`/recovery-code`, `/recover`): they
were a pre-Clerk relic. Account recovery is email sign-in through Clerk, and
the export/import pair below is the data backup.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.api.deps import (
    get_user_id,
    load_state,
    save_state,
)
from backend.engine import storage

router = APIRouter(prefix="/api/user", tags=["user"])

# ── Required top-level keys in a valid user_state ──────────────────────

_REQUIRED_KEYS = {"schema_version"}

# Keys that must be dicts IF present (all guaranteed by EMPTY_TEMPLATE)
_REQUIRED_DICT_KEYS = {
    "assessment": "assessment deve essere un oggetto JSON",
    "equipment": "equipment deve essere un oggetto JSON",
}


def _validate_import(data: Any) -> None:
    """Validate that *data* looks like a plausible user_state.

    Raises ValueError with a human-readable message on failure.
    """
    if not isinstance(data, dict):
        raise ValueError("Il file deve contenere un oggetto JSON (dizionario)")

    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Campi obbligatori mancanti: {', '.join(sorted(missing))}")

    sv = data.get("schema_version")
    if sv not in ("1.5",):
        raise ValueError(
            f"schema_version non supportata: {sv!r} (attesa: '1.5')"
        )

    for key, msg in _REQUIRED_DICT_KEYS.items():
        if key not in data:
            raise ValueError(f"Campo obbligatorio mancante: {key!r}")
        if not isinstance(data[key], dict):
            raise ValueError(f"Campo non valido: {key!r} deve essere un oggetto JSON (trovato: {type(data[key]).__name__})")


def _append_import_event(user_id: Optional[str]) -> None:
    """Write an append-only event to the user's log directory."""
    storage.append_event(user_id, {
        "event": "state_imported",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/export")
def export_state(user_id: Optional[str] = Depends(get_user_id)):
    """Download the full user_state as a JSON file."""
    state = load_state(user_id)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"climb-agent-backup-{today}.json"
    return Response(
        content=json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def import_state(
    body: Dict[str, Any],
    user_id: Optional[str] = Depends(get_user_id),
):
    """Import a full user_state, overwriting the current one."""
    try:
        _validate_import(body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    save_state(body, user_id)
    _append_import_event(user_id)
    return {"status": "imported"}
