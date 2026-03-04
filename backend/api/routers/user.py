"""User router — GET /api/user/export, POST /api/user/import, recovery codes."""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.api.deps import (
    DATA_DIR,
    USERS_DIR,
    get_user_id,
    load_state,
    save_state,
)

# ── Recovery code helpers ───────────────────────────────────────────────

_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I/L
_CODES_PATH = DATA_DIR / "recovery_codes.json"


def _load_codes() -> Dict[str, Any]:
    if _CODES_PATH.exists():
        return json.loads(_CODES_PATH.read_text(encoding="utf-8"))
    return {}


def _save_codes(codes: Dict[str, Any]) -> None:
    _CODES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CODES_PATH.write_text(
        json.dumps(codes, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _generate_code(codes: Dict[str, Any]) -> str:
    """Generate a unique CLIMB-XXXX-XXXX code not already in *codes*."""
    for _ in range(100):
        part1 = "".join(random.choices(_ALPHABET, k=4))
        part2 = "".join(random.choices(_ALPHABET, k=4))
        code = f"CLIMB-{part1}-{part2}"
        if code not in codes:
            return code
    raise RuntimeError("Could not generate unique recovery code")

router = APIRouter(prefix="/api/user", tags=["user"])

# ── Required top-level keys in a valid user_state ──────────────────────

_REQUIRED_KEYS = {"schema_version"}


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


def _log_dir(user_id: Optional[str]) -> str:
    if user_id:
        d = str(USERS_DIR / user_id / "logs")
        os.makedirs(d, exist_ok=True)
        return d
    from backend.api.deps import DATA_DIR
    d = str(DATA_DIR / "logs")
    os.makedirs(d, exist_ok=True)
    return d


def _append_import_event(user_id: Optional[str]) -> None:
    """Write an append-only event to the user's log directory."""
    log_path = os.path.join(_log_dir(user_id), "events.jsonl")
    entry = {
        "event": "state_imported",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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


@router.post("/recovery-code")
def get_or_create_recovery_code(
    user_id: Optional[str] = Depends(get_user_id),
):
    """Return existing recovery code for this user, or generate a new one.

    Requires X-User-ID header. Idempotent: repeated calls return the same code.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header required")

    codes = _load_codes()

    # Check if this UUID already has a code
    for code, info in codes.items():
        if info.get("uuid") == user_id:
            return {"recovery_code": code}

    # Generate new code
    code = _generate_code(codes)
    codes[code] = {
        "uuid": user_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    _save_codes(codes)
    return {"recovery_code": code}


@router.post("/recover")
def recover_account(body: Dict[str, Any]):
    """Given a recovery code, return the associated UUID.

    Public endpoint — no X-User-ID required.
    Body: { "recovery_code": "CLIMB-XXXX-XXXX" }
    """
    code = str(body.get("recovery_code", "")).strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="recovery_code required")

    codes = _load_codes()
    info = codes.get(code)
    if not info:
        raise HTTPException(status_code=404, detail="Recovery code not found")

    return {"uuid": info["uuid"]}
