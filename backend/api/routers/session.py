"""Session router — resolve abstract session to concrete exercises."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from backend.api.deps import REPO_ROOT, load_state
from backend.api.models import SessionResolveRequest
from backend.engine.resolve_session import resolve_session

router = APIRouter(prefix="/api/session", tags=["session"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


@router.post("/resolve")
def resolve(req: SessionResolveRequest):
    """Resolve a session_id into concrete exercises."""
    session_path = os.path.join(SESSIONS_DIR, f"{req.session_id}.json")
    full_path = REPO_ROOT / session_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {req.session_id}")

    state = load_state()
    if req.context:
        state["context"] = {**state.get("context", {}), **req.context}

    try:
        resolved = resolve_session(
            repo_root=str(REPO_ROOT),
            session_path=session_path,
            templates_dir=TEMPLATES_DIR,
            exercises_path=EXERCISES_PATH,
            out_path="",  # not writing to disk
            user_state_override=state,
            write_output=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session resolution failed: {e}")

    return {"resolved": resolved}
