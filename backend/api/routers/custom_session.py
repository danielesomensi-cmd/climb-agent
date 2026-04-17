"""Custom session router — CRUD, exercise listing, warmup/cooldown blocks (A205)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import REPO_ROOT, get_user_id, load_state, require_active_subscription, save_state
from backend.api.models import CustomSessionCreateRequest, CustomSessionUpdateRequest
from backend.engine.custom_session import compute_custom_session_load, estimate_custom_session_duration

router = APIRouter(prefix="/api/custom-session", tags=["custom-session"])

EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
TEMPLATES_DIR = REPO_ROOT / "backend" / "catalog" / "templates" / "v1"

# ── Catalog cache ────────────────────────────────────────────────────────

_EXERCISES_CACHE: Optional[Dict[str, Any]] = None


def _load_exercises_catalog() -> Dict[str, Any]:
    """Load {id: exercise_dict} from catalog. Cached after first load."""
    global _EXERCISES_CACHE
    if _EXERCISES_CACHE is None:
        with open(EXERCISES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _EXERCISES_CACHE = {e["id"]: e for e in data.get("exercises", [])}
    return _EXERCISES_CACHE


def _get_custom_sessions(state: dict) -> list:
    """Get custom_sessions list from state, defaulting to []."""
    return state.get("custom_sessions", [])


def _validate_exercise_ids(exercises: list, catalog: dict) -> None:
    """Raise 422 if any exercise_id not in catalog."""
    invalid = [ex.exercise_id for ex in exercises if ex.exercise_id not in catalog]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown exercise_id(s): {', '.join(invalid)}",
        )


def _validate_tags(tags: list) -> None:
    """Raise 422 if tags exceed limits."""
    if len(tags) > 5:
        raise HTTPException(status_code=422, detail="Maximum 5 tags allowed")
    for tag in tags:
        if len(tag) > 30:
            raise HTTPException(status_code=422, detail=f"Tag too long (max 30 chars): {tag!r}")


def _build_session(
    session_id: str,
    name: str,
    tags: list,
    exercises: list,
    catalog: dict,
    created_at: str,
) -> dict:
    """Build a full custom session dict with computed fields."""
    now = datetime.now(timezone.utc).isoformat()
    ex_dicts = [ex.model_dump() for ex in exercises]
    exercise_ids = [ex.exercise_id for ex in exercises]
    return {
        "id": session_id,
        "name": name.strip(),
        "created_at": created_at,
        "updated_at": now,
        "tags": tags,
        "exercises": ex_dicts,
        "estimated_load_score": compute_custom_session_load(exercise_ids, catalog),
        "estimated_duration_minutes": estimate_custom_session_duration(ex_dicts),
    }


def _summary(s: dict) -> dict:
    """Return summary view (no exercises)."""
    return {
        "id": s["id"],
        "name": s["name"],
        "tags": s.get("tags", []),
        "exercise_count": len(s.get("exercises", [])),
        "estimated_load_score": s.get("estimated_load_score", 0),
        "estimated_duration_minutes": s.get("estimated_duration_minutes", 0),
        "created_at": s.get("created_at", ""),
        "updated_at": s.get("updated_at", ""),
    }


# ── CRUD endpoints ──────────────────────────────────────────────────────


@router.get("/list", dependencies=[Depends(require_active_subscription)])
def list_sessions(user_id: Optional[str] = Depends(get_user_id)):
    """List all custom sessions (summary view)."""
    state = load_state(user_id)
    sessions = _get_custom_sessions(state)
    return {"sessions": [_summary(s) for s in sessions], "count": len(sessions)}


@router.get("/exercises", dependencies=[Depends(require_active_subscription)])
def list_exercises(
    q: Optional[str] = Query(None, description="Search name/description"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    equipment: Optional[bool] = Query(None, description="Filter by user equipment"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Exercise catalog for the builder picker."""
    catalog = _load_exercises_catalog()
    exercises = list(catalog.values())

    # Equipment filter: load user equipment and filter
    user_equipment: Optional[set] = None
    if equipment:
        state = load_state(user_id)
        eq = state.get("equipment", {})
        user_equipment = set(eq.get("available", []))

    results: List[Dict[str, Any]] = []
    for ex in exercises:
        # Search filter
        if q:
            q_lower = q.lower()
            name_match = q_lower in (ex.get("name") or "").lower()
            desc_match = q_lower in (ex.get("description") or "").lower()
            if not name_match and not desc_match:
                continue

        # Domain filter
        if domain:
            ex_domains = ex.get("domain", [])
            if isinstance(ex_domains, str):
                ex_domains = [ex_domains]
            if domain not in ex_domains:
                continue

        # Equipment filter
        if user_equipment is not None:
            req = ex.get("equipment_required", [])
            req_any = ex.get("equipment_required_any", [])
            # Hard filter: all required must be available
            if req and not set(req).issubset(user_equipment):
                continue
            # Any filter: at least one must be available
            if req_any and not any(e in user_equipment for e in req_any):
                continue

        results.append({
            "id": ex["id"],
            "name": ex.get("name", ex["id"]),
            "description": ex.get("description", ""),
            "domain": ex.get("domain", []),
            "equipment_required": ex.get("equipment_required", []),
            "prescription_defaults": ex.get("prescription_defaults", {}),
            "fatigue_cost": ex.get("fatigue_cost", 0),
            "load_model": ex.get("load_model"),
        })

    # Sort by domain (first entry), then name
    results.sort(key=lambda r: (
        r["domain"][0] if isinstance(r["domain"], list) and r["domain"] else "",
        r["name"],
    ))

    return {"exercises": results, "count": len(results)}


@router.get("/blocks", dependencies=[Depends(require_active_subscription)])
def get_blocks(user_id: Optional[str] = Depends(get_user_id)):
    """Resolved warmup/cooldown blocks as concrete exercise lists."""
    catalog = _load_exercises_catalog()
    result: Dict[str, List[Dict[str, Any]]] = {"warmup": [], "cooldown": []}

    # Scan templates directory for warmup/cooldown templates
    if not TEMPLATES_DIR.exists():
        return result

    for template_path in sorted(TEMPLATES_DIR.glob("*.json")):
        with open(template_path, encoding="utf-8") as f:
            template = json.load(f)

        template_id = template_path.stem
        label = template.get("name", template_id)
        category = template.get("category", "")

        # Classify as warmup or cooldown
        if "warmup" in template_id.lower() or "warmup" in category.lower():
            block_type = "warmup"
        elif "cooldown" in template_id.lower() or "cooldown" in category.lower():
            block_type = "cooldown"
        else:
            continue

        # Resolve template exercises to builder format.
        # Template blocks have exercise_id at block level (not nested array).
        # Blocks with mode=select_one or no exercise_id are dynamic — skip them.
        exercises: List[Dict[str, Any]] = []
        for block in template.get("blocks", []):
            ex_id = block.get("exercise_id", "")
            if not ex_id or ex_id not in catalog:
                continue
            ex_cat = catalog[ex_id]
            defaults = ex_cat.get("prescription_defaults", {})
            block_prescription = block.get("prescription", {})
            prescription = {**defaults, **(block_prescription if isinstance(block_prescription, dict) else {})}
            exercises.append({
                "exercise_id": ex_id,
                "name": ex_cat.get("name", ex_id),
                "sets": prescription.get("sets", 1),
                "reps": prescription.get("reps"),
                "work_seconds": prescription.get("work_seconds"),
                "rest_between_sets_seconds": prescription.get("rest_between_sets_seconds", 0),
                "rest_between_reps_seconds": prescription.get("rest_between_reps_seconds"),
                "load_kg": 0,
                "notes": prescription.get("notes", ""),
            })

        if exercises:
            result[block_type].append({
                "template_id": template_id,
                "label": label,
                "exercises": exercises,
            })

    return result


@router.get("/{session_id}", dependencies=[Depends(require_active_subscription)])
def get_session(session_id: str, user_id: Optional[str] = Depends(get_user_id)):
    """Get full custom session detail."""
    state = load_state(user_id)
    sessions = _get_custom_sessions(state)
    for s in sessions:
        if s.get("id") == session_id:
            return s
    raise HTTPException(status_code=404, detail=f"Custom session not found: {session_id}")


@router.post("", dependencies=[Depends(require_active_subscription)], status_code=201)
def create_session(req: CustomSessionCreateRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Create a new custom session."""
    catalog = _load_exercises_catalog()
    _validate_exercise_ids(req.exercises, catalog)
    _validate_tags(req.tags)

    state = load_state(user_id)
    sessions = _get_custom_sessions(state)

    session_id = f"cs_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    session = _build_session(
        session_id=session_id,
        name=req.name,
        tags=req.tags,
        exercises=req.exercises,
        catalog=catalog,
        created_at=now,
    )

    sessions.append(session)
    state["custom_sessions"] = sessions
    save_state(state, user_id)

    return session


@router.put("/{session_id}", dependencies=[Depends(require_active_subscription)])
def update_session(session_id: str, req: CustomSessionUpdateRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Update an existing custom session."""
    catalog = _load_exercises_catalog()
    _validate_exercise_ids(req.exercises, catalog)
    _validate_tags(req.tags)

    state = load_state(user_id)
    sessions = _get_custom_sessions(state)

    for i, s in enumerate(sessions):
        if s.get("id") == session_id:
            updated = _build_session(
                session_id=session_id,
                name=req.name,
                tags=req.tags,
                exercises=req.exercises,
                catalog=catalog,
                created_at=s.get("created_at", ""),
            )
            sessions[i] = updated
            state["custom_sessions"] = sessions
            save_state(state, user_id)
            return updated

    raise HTTPException(status_code=404, detail=f"Custom session not found: {session_id}")


@router.delete("/{session_id}", dependencies=[Depends(require_active_subscription)])
def delete_session(session_id: str, user_id: Optional[str] = Depends(get_user_id)):
    """Delete a custom session."""
    state = load_state(user_id)
    sessions = _get_custom_sessions(state)

    for i, s in enumerate(sessions):
        if s.get("id") == session_id:
            sessions.pop(i)
            state["custom_sessions"] = sessions
            save_state(state, user_id)
            return {"deleted": session_id}

    raise HTTPException(status_code=404, detail=f"Custom session not found: {session_id}")
