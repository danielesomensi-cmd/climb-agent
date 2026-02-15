"""Catalog router — exercise and session catalogs."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from backend.api.deps import REPO_ROOT
from backend.engine.resolve_session import ensure_exercise_list, load_json

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
SESSIONS_DIR = REPO_ROOT / "backend" / "catalog" / "sessions" / "v1"


@router.get("/exercises")
def list_exercises():
    """Return all exercises from the catalog."""
    raw = load_json(str(EXERCISES_PATH))
    exercises = ensure_exercise_list(raw)
    return {"exercises": exercises, "count": len(exercises)}


@router.get("/sessions")
def list_sessions():
    """Return all session definitions (id + metadata, not full body)."""
    sessions = []
    for p in sorted(SESSIONS_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        sessions.append({
            "id": p.stem,
            "name": data.get("session_name", p.stem),
            "type": data.get("session_type", "unknown"),
            "location": data.get("location", "any"),
            "tags": data.get("tags", {}),
        })
    return {"sessions": sessions, "count": len(sessions)}
