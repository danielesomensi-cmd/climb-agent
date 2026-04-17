"""Catalog router — exercise and session catalogs."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from backend.api.deps import REPO_ROOT
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.resolve_session import ensure_exercise_list, load_json

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
SESSIONS_DIR = REPO_ROOT / "backend" / "catalog" / "sessions" / "v1"


def _session_location(session_id: str, data: dict) -> str:
    """Derive location label for catalog listing (B206: runtime is source-of-truth;
    catalog exposes viable locations from _SESSION_META)."""
    top_level = data.get("location")
    if isinstance(top_level, str) and top_level:
        return top_level
    meta = _SESSION_META.get(session_id)
    if meta:
        locs = meta.get("location") or ()
        if len(locs) == 1:
            return locs[0]
        if len(locs) > 1:
            return "both"
    return "any"


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
            "name": data.get("session_name") or data.get("name") or p.stem,
            "type": data.get("session_type") or data.get("type") or "unknown",
            "location": _session_location(p.stem, data),
            "tags": data.get("tags", {}),
            "required_equipment": data.get("required_equipment", []),
        })
    return {"sessions": sessions, "count": len(sessions)}
