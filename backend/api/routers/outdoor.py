"""Outdoor router — spots CRUD, session logging, slot conversion."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_user_id, load_state, require_active_subscription, save_state
from backend.api.models import (
    OutdoorSpotCreate,
    OutdoorSessionLog,
    OutdoorSessionStartRequest,
    OutdoorSessionFinishRequest,
    OutdoorClimbLogRequest,
    OutdoorRoutesReplaceRequest,
    ConvertSlotRequest,
)
from backend.engine.outdoor_log import (
    CURRENT_LOG_VERSION,
    append_outdoor_session,
    compute_outdoor_load_score,
    compute_outdoor_stats,
    derive_outdoor_duration,
    load_outdoor_sessions,
    remove_outdoor_session,
    update_outdoor_session,
)
from backend.engine.outdoor_pitch_ladder import build_pitch_ladder, grades_from_state
from backend.engine.outdoor_resolver import OutdoorResolveError, resolve_outdoor_day

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/outdoor", tags=["outdoor"])


def _sync_plan_after_outdoor_log(
    state: Dict[str, Any], user_id: Optional[str], entry: Dict[str, Any],
    load_score: int,
) -> bool:
    """Close the closed-loop on the week plan after an outdoor log (B273).

    The active-session finish flow (A225) wrote the immutable log but never
    marked the plan day done — that side effect lived only in the frontend
    form flow (today/week → applyEvents complete_outdoor), so routes/load/
    ripple were silently skipped. The backend that records the outcome now
    also closes it, via the same replanner events the legacy flow uses.

    Best-effort by design: the outdoor log is the primary record and is
    already persisted when this runs. Returns True iff the plan day was
    marked done. Skips (False) when: plan paused (A223), date in a past week
    (B257 immutability), no hot plan for that Monday, or day not in the plan.
    """
    from backend.api.deps import ensure_monday, is_past_week, is_plan_paused
    from backend.api.routers.replanner import _auto_resolve, persist_week_plan
    from backend.engine.replanner_v1 import apply_events

    date = entry.get("date") or ""
    if not date:
        return False
    if is_plan_paused(state):
        logger.info("B273: plan paused — outdoor log %s saved without plan sync", date)
        return False
    monday = ensure_monday(date)
    if is_past_week(monday):
        logger.info("B273: %s is in a past week — plan untouched (immutability)", date)
        return False

    plan = (state.get("week_plans") or {}).get(monday)
    if not plan:
        cwp = state.get("current_week_plan")
        if cwp and cwp.get("start_date") == monday:
            plan = cwp
    if not plan:
        logger.info("B273: no hot week plan for %s — nothing to sync", monday)
        return False

    day = next(
        (d for w in plan.get("weeks") or [] for d in w.get("days") or []
         if d.get("date") == date),
        None,
    )
    if day is None:
        return False

    events: List[Dict[str, Any]] = []
    if not day.get("outdoor_spot_name"):
        # Spontaneous outdoor day (not planned): register it first so
        # complete_outdoor has a target — same as the replan add_outdoor path.
        add_ev: Dict[str, Any] = {
            "event_type": "add_outdoor",
            "date": date,
            "spot_name": entry.get("spot_name") or "Outdoor",
            "discipline": entry.get("discipline") or "both",
        }
        if entry.get("spot_id"):
            add_ev["spot_id"] = entry["spot_id"]
        events.append(add_ev)
    events.append({
        "event_type": "complete_outdoor",
        "date": date,
        "outdoor_load_score": load_score,
    })

    updated = apply_events(
        plan,
        events,
        availability=state.get("availability"),
        planning_prefs=state.get("planning_prefs"),
        gyms=(state.get("equipment") or {}).get("gyms"),
        custom_sessions=state.get("custom_sessions") or [],
    )

    # B116 bookkeeping — same shape the replanner events endpoint writes.
    u_day = next(
        (d for w in updated.get("weeks", []) for d in w.get("days", [])
         if d.get("date") == date),
        None,
    )
    # B277: one bookkeeping entry per date — idempotent across re-logs and
    # manual edits (also cleans up any historical duplicates for this date).
    bookkeeping = state.setdefault("outdoor_log", [])
    bookkeeping[:] = [e for e in bookkeeping if e.get("date") != date]
    bookkeeping.append({
        "date": date,
        "spot_name": (u_day or {}).get("outdoor_spot_name", entry.get("spot_name", "")),
        "spot_id": (u_day or {}).get("outdoor_spot_id", entry.get("spot_id", "")),
        "discipline": (u_day or {}).get("outdoor_discipline", entry.get("discipline", "both")),
        "load_score": load_score,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })

    persist_week_plan(updated, state, user_id)
    # Ripple may have swapped next-day sessions with unresolved replacements.
    _auto_resolve(updated, state, user_id)
    return True


# ── Spots CRUD ──────────────────────────────────────────────────────────

@router.get("/spots")
def get_outdoor_spots(user_id: Optional[str] = Depends(get_user_id)):
    """Return all saved outdoor climbing spots."""
    state = load_state(user_id)
    return {"spots": state.get("outdoor_spots", [])}


@router.post("/spots")
def add_outdoor_spot(req: OutdoorSpotCreate, user_id: Optional[str] = Depends(get_user_id)):
    """Add a new outdoor spot to user state."""
    state = load_state(user_id)
    spots = state.setdefault("outdoor_spots", [])

    spot_id = req.id or f"spot_{uuid.uuid4().hex[:8]}"

    # Check for duplicate id
    if any(s.get("id") == spot_id for s in spots):
        raise HTTPException(status_code=409, detail=f"Spot with id '{spot_id}' already exists")

    spot: Dict[str, Any] = {
        "id": spot_id,
        "name": req.name,
        "discipline": req.discipline,
    }
    if req.typical_days:
        spot["typical_days"] = req.typical_days
    if req.notes:
        spot["notes"] = req.notes

    spots.append(spot)
    save_state(state, user_id)
    return {"status": "ok", "spot": spot}


@router.delete("/spots/{spot_id}")
def delete_outdoor_spot(spot_id: str, user_id: Optional[str] = Depends(get_user_id)):
    """Remove an outdoor spot by id."""
    state = load_state(user_id)
    spots = state.get("outdoor_spots", [])
    new_spots = [s for s in spots if s.get("id") != spot_id]

    if len(new_spots) == len(spots):
        raise HTTPException(status_code=404, detail=f"Spot '{spot_id}' not found")

    state["outdoor_spots"] = new_spots
    save_state(state, user_id)
    return {"status": "ok"}


# ── Session logging ─────────────────────────────────────────────────────

@router.post("/log", dependencies=[Depends(require_active_subscription)])
def post_outdoor_log(req: OutdoorSessionLog, user_id: Optional[str] = Depends(get_user_id)):
    """Validate and append an outdoor session to the log."""
    entry = req.model_dump(exclude_none=True)
    entry["log_version"] = CURRENT_LOG_VERSION

    try:
        log_path = append_outdoor_session(entry, user_id)
    except ValueError as e:
        # D134: distinguish auth errors (missing user_id) from validation errors
        if "authenticated user_id" in str(e):
            raise HTTPException(
                status_code=401,
                detail="Authentication required to save outdoor session",
            )
        raise HTTPException(status_code=422, detail=str(e))
    except OSError as e:
        logger.error("Failed to write outdoor log: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to write outdoor log. Please try again.",
        )

    # Verify write persisted (file backend only — Supabase has read-after-write in storage layer)
    if not log_path.startswith("supabase://") and not os.path.isfile(log_path):
        logger.error("Outdoor log write succeeded but file not found at %s", log_path)
        raise HTTPException(
            status_code=500,
            detail="Outdoor log write succeeded but file could not be verified.",
        )

    # B277: close the closed-loop on the week plan (status done + load + ripple),
    # same as the active-session finish flow (B273). Without this, a manually
    # logged outdoor session stays "planned" on the plan and its routes never
    # surface in the Week view. Best-effort — the log above is the primary record.
    plan_synced = False
    try:
        state = load_state(user_id)
        plan_synced = _sync_plan_after_outdoor_log(
            state, user_id, entry, compute_outdoor_load_score(entry)
        )
    except Exception:
        logger.exception(
            "B277: plan sync after manual outdoor log failed — log saved, plan untouched"
        )

    return {"status": "ok", "log_path": os.path.basename(log_path), "plan_synced": plan_synced}


@router.get("/log/{date}")
def get_outdoor_log_by_date(date: str, user_id: Optional[str] = Depends(get_user_id)):
    """Return the outdoor session entry for a specific date."""
    sessions = load_outdoor_sessions(user_id, since_date=date)
    matching = [s for s in sessions if s.get("date") == date]
    if not matching:
        raise HTTPException(status_code=404, detail=f"No outdoor session found for date {date}")
    entry = matching[-1]
    entry["load_score"] = compute_outdoor_load_score(entry)
    return {"session": entry}


@router.put("/log")
def put_outdoor_log(req: OutdoorSessionLog, user_id: Optional[str] = Depends(get_user_id)):
    """Update an existing outdoor session (replace entry for the same date)."""
    entry = req.model_dump(exclude_none=True)
    entry["log_version"] = CURRENT_LOG_VERSION

    try:
        update_outdoor_session(user_id, req.date, entry)
    except ValueError as e:
        detail = str(e)
        if "authenticated user_id" in detail:
            raise HTTPException(status_code=401, detail="Authentication required to update outdoor session")
        status = 404 if "No outdoor session found" in detail or "No outdoor log file" in detail else 422
        raise HTTPException(status_code=status, detail=detail)
    except OSError as e:
        logger.error("Failed to update outdoor log: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update outdoor log. Please try again.")

    # Update state.outdoor_log[] (B116) with recalculated load_score
    state = load_state(user_id)
    outdoor_log = state.get("outdoor_log", [])
    for ol_entry in outdoor_log:
        if ol_entry.get("date") == req.date:
            ol_entry["spot_name"] = entry.get("spot_name", ol_entry.get("spot_name", ""))
            ol_entry["discipline"] = entry.get("discipline", ol_entry.get("discipline", "both"))
            ol_entry["load_score"] = compute_outdoor_load_score(entry)
            break
    save_state(state, user_id)

    # B277: close the loop if an edit finalizes a session whose plan day was
    # never marked done (dedupe in the sync keeps bookkeeping to one entry).
    plan_synced = False
    try:
        plan_synced = _sync_plan_after_outdoor_log(
            state, user_id, entry, compute_outdoor_load_score(entry)
        )
    except Exception:
        logger.exception(
            "B277: plan sync after outdoor log update failed — log saved, plan untouched"
        )

    return {"status": "ok", "load_score": compute_outdoor_load_score(entry), "plan_synced": plan_synced}


@router.delete("/log/{date}")
def delete_outdoor_log(date: str, user_id: Optional[str] = Depends(get_user_id)):
    """Delete the outdoor session for a given date."""
    try:
        removed = remove_outdoor_session(user_id, date)
    except ValueError as e:
        detail = str(e)
        if "authenticated user_id" in detail:
            raise HTTPException(status_code=401, detail="Authentication required to delete outdoor session")
        raise HTTPException(status_code=404, detail=f"No outdoor session found for date {date}")
    except OSError as e:
        logger.error("Failed to delete outdoor log: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete outdoor log. Please try again.")

    if removed == 0:
        raise HTTPException(status_code=404, detail=f"No outdoor session found for date {date}")

    # Remove from state.outdoor_log[]
    state = load_state(user_id)
    outdoor_log = state.get("outdoor_log", [])
    state["outdoor_log"] = [ol for ol in outdoor_log if ol.get("date") != date]
    save_state(state, user_id)

    return {"status": "ok", "date": date}


@router.get("/sessions")
def get_outdoor_sessions(since: Optional[str] = Query(None), user_id: Optional[str] = Depends(get_user_id)):
    """List outdoor sessions, optionally filtered by date."""
    sessions = load_outdoor_sessions(user_id, since_date=since)
    # Enrich each session with its load score
    for s in sessions:
        s["load_score"] = compute_outdoor_load_score(s)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/stats")
def get_outdoor_stats(since: Optional[str] = Query(None), user_id: Optional[str] = Depends(get_user_id)):
    """Get aggregated outdoor climbing statistics."""
    sessions = load_outdoor_sessions(user_id, since_date=since)
    stats = compute_outdoor_stats(sessions)
    return stats


# ── Strategy + nutrition resolver (A225 Phase 3) ─────────────────────────

@router.get("/strategy", dependencies=[Depends(require_active_subscription)])
def get_outdoor_strategy(
    day_type: str = Query(..., description="project | onsight_flash | volume | scout_easy"),
    discipline: str = Query("lead"),
    wall_angle: Optional[str] = Query(None),
    route_length: Optional[str] = Query(None),
    hold_style: Optional[str] = Query(None),
    target_grade_relative: Optional[str] = Query(None),
    condition_band: Optional[str] = Query(None),
    macrocycle_phase: Optional[str] = Query(None, description="Explicit catalog phase; overrides use_current_phase"),
    use_current_phase: bool = Query(False, description="Read the user's current macrocycle phase (read-only nudge)"),
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Optional: auto-derive condition_band from weather"),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0),
    date: Optional[str] = Query(None, description="YYYY-MM-DD for forecast (with lat/lon)"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Resolve the deterministic strategy + nutrition for an outdoor day.

    ``day_type`` alone returns a complete entry; optional dimensions layer
    patches. ``macrocycle_phase`` is a read-only text nudge (D3): pass it
    explicitly, or set ``use_current_phase`` to derive it from the user's plan.
    When ``condition_band`` is omitted but ``lat``/``lon`` are given, the band is
    auto-derived from weather (graceful: no weather → base, no band).
    """
    # macrocycle_phase shares the engine vocabulary (base, strength_power,
    # power_endurance, performance, deload) — direct lookup, no translation (D3).
    phase = macrocycle_phase
    if phase is None and use_current_phase:
        from datetime import date as _date
        from backend.engine.free_session import get_phase_for_date

        state = load_state(user_id)
        phase = get_phase_for_date(state, _date.today().isoformat())

    # Weather auto-fill (A225 Phase 4): derive condition_band when not explicit.
    derived_conditions: Optional[Dict[str, Any]] = None
    band = condition_band
    if band is None and lat is not None and lon is not None:
        from backend.api.routers.weather import fetch_outdoor_conditions

        derived_conditions = fetch_outdoor_conditions(lat, lon, date)
        if derived_conditions:
            band = derived_conditions["condition_band"]

    dimensions = {
        "wall_angle": wall_angle,
        "route_length": route_length,
        "hold_style": hold_style,
        "target_grade_relative": target_grade_relative,
        "macrocycle_phase": phase,
        "condition_band": band,
    }

    try:
        resolved = resolve_outdoor_day(discipline, day_type, dimensions)
    except OutdoorResolveError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Surface the derived conditions so the UI (brief #3) can pre-fill the log.
    resolved["conditions"] = derived_conditions

    # A265: the catalog talks in relative terms ("ramp grades into the day").
    # Attach the absolute ladder derived from the athlete's own grades, so the
    # strategy screen names actual grades instead of an example ramp.
    grades = grades_from_state(load_state(user_id))
    resolved["pitch_ladder"] = (
        build_pitch_ladder(
            day_type,
            onsight_grade=grades["onsight"],
            redpoint_grade=grades["redpoint"],
            discipline=discipline,
        )
        if grades
        else None
    )
    return resolved


@router.get("/pitch-ladder", dependencies=[Depends(require_active_subscription)])
def get_pitch_ladder(
    day_type: str = Query(..., description="project | onsight_flash | volume | scout_easy"),
    discipline: str = Query("lead"),
    onsight_grade: Optional[str] = Query(None, description="Override the recorded onsight grade"),
    redpoint_grade: Optional[str] = Query(None, description="Override the recorded redpoint grade"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Generate the deterministic pitch ladder for an outdoor day (A265).

    Grades come from the athlete's ``performance.current_level.sport`` unless
    overridden. 422 rather than a guess when no usable grade exists: prescribing
    grades that are not the athlete's is worse than prescribing none.
    """
    if not onsight_grade and not redpoint_grade:
        grades = grades_from_state(load_state(user_id))
        if not grades:
            raise HTTPException(
                status_code=422,
                detail="No recorded sport grade — set your onsight/redpoint grade first",
            )
        onsight_grade, redpoint_grade = grades["onsight"], grades["redpoint"]

    ladder = build_pitch_ladder(
        day_type,
        onsight_grade=onsight_grade,
        redpoint_grade=redpoint_grade,
        discipline=discipline,
    )
    if ladder is None:
        raise HTTPException(
            status_code=422,
            detail=f"No ladder for discipline={discipline!r} day_type={day_type!r}",
        )
    return ladder


# ── Active session lifecycle (A225) ─────────────────────────────────────
# planned → active (started_at set) → done (logged to outdoor_logs, immutable).
# The active session is transient working state in user_state; the canonical,
# immutable record is the outdoor_logs entry written on finish.

def _find_active_session(state: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    for s in state.get("outdoor_active_sessions", []):
        if s.get("session_id") == session_id:
            return s
    raise HTTPException(status_code=404, detail=f"Active outdoor session '{session_id}' not found")


@router.post("/session/start", dependencies=[Depends(require_active_subscription)])
def start_outdoor_session(
    req: OutdoorSessionStartRequest, user_id: Optional[str] = Depends(get_user_id)
):
    """Start an active outdoor session — sets started_at server-side (timer)."""
    state = load_state(user_id)
    active = state.setdefault("outdoor_active_sessions", [])

    seq = len([s for s in active if s.get("date") == req.date]) + 1
    session_id = f"outdoor_active_{req.date.replace('-', '')}_{seq}"
    now = datetime.now(timezone.utc).isoformat()

    session: Dict[str, Any] = {
        "session_id": session_id,
        "date": req.date,
        "spot_id": req.spot_id,
        "spot_name": req.spot_name,
        "discipline": req.discipline,
        "day_type": req.day_type,
        "status": "active",
        "started_at": now,
        "routes": [],
    }
    active.append(session)
    save_state(state, user_id)
    return {"session_id": session_id, "started_at": now, "status": "active"}


@router.get("/session/active")
def get_active_outdoor_session(
    date: Optional[str] = Query(None), user_id: Optional[str] = Depends(get_user_id)
):
    """Return the user's active outdoor session (optionally for a date) for restore.

    Lets the UI recover a live session — including routes logged so far — after a
    refresh / app close. Returns the most recent active session, or 404.
    """
    state = load_state(user_id)
    active = state.get("outdoor_active_sessions", [])
    if date:
        active = [s for s in active if s.get("date") == date]
    if not active:
        raise HTTPException(status_code=404, detail="No active outdoor session")
    return {"session": active[-1]}


@router.post("/session/{session_id}/log-climb", dependencies=[Depends(require_active_subscription)])
def log_outdoor_climb(
    session_id: str,
    req: OutdoorClimbLogRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Append a climb to an active outdoor session (A226 live logging).

    Persists each route as it's climbed so the live log survives a refresh.
    Returns the full updated routes list.
    """
    state = load_state(user_id)
    session = _find_active_session(state, session_id)
    route = req.model_dump(exclude_none=True)
    session.setdefault("routes", []).append(route)
    save_state(state, user_id)
    return {"routes": session["routes"], "count": len(session["routes"])}


@router.delete("/session/{session_id}/climb/{climb_index}", dependencies=[Depends(require_active_subscription)])
def delete_outdoor_climb(
    session_id: str,
    climb_index: int,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Remove a climb (by 0-based index) from an active outdoor session."""
    state = load_state(user_id)
    session = _find_active_session(state, session_id)
    routes = session.get("routes", [])
    if climb_index < 0 or climb_index >= len(routes):
        raise HTTPException(status_code=404, detail=f"Climb index {climb_index} out of range")
    routes.pop(climb_index)
    session["routes"] = routes
    save_state(state, user_id)
    return {"routes": routes, "count": len(routes)}


@router.put("/session/{session_id}/routes", dependencies=[Depends(require_active_subscription)])
def replace_outdoor_routes(
    session_id: str,
    req: OutdoorRoutesReplaceRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Replace the active session's full routes list (A226 live route sync).

    The client manages routes + attempts locally (multiple attempts per route,
    removals) and syncs the whole array here so it survives a refresh.
    """
    state = load_state(user_id)
    session = _find_active_session(state, session_id)
    session["routes"] = [r.model_dump(exclude_none=True) for r in req.routes]
    save_state(state, user_id)
    return {"routes": session["routes"], "count": len(session["routes"])}


@router.post("/session/{session_id}/finish", dependencies=[Depends(require_active_subscription)])
def finish_outdoor_session(
    session_id: str,
    req: OutdoorSessionFinishRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Close an active outdoor session → write an immutable outdoor.v2 log.

    Derives ``duration_minutes`` from the timer (started_at→now), capped against a
    stale timer; an explicit ``duration_minutes`` in the body wins as a manual
    override. Returns the saved entry plus duration provenance so the UI can ask
    for confirmation when the timer was capped.
    """
    state = load_state(user_id)
    session = _find_active_session(state, session_id)

    now = datetime.now(timezone.utc)
    dur = derive_outdoor_duration(session.get("started_at"), now, req.duration_minutes)
    if dur["minutes"] is None:
        raise HTTPException(
            status_code=422,
            detail="Cannot determine duration: no valid timer and no manual duration_minutes provided.",
        )

    entry = req.model_dump(exclude_none=True)
    entry["log_version"] = CURRENT_LOG_VERSION
    entry["date"] = session["date"]
    entry["duration_minutes"] = dur["minutes"]
    # Carry the day_type chosen at start unless the finish body overrides it.
    if not entry.get("day_type") and session.get("day_type"):
        entry["day_type"] = session["day_type"]
    # Fall back to live-logged routes if the finish body carried none (A226).
    if not entry.get("routes") and session.get("routes"):
        entry["routes"] = [
            {k: v for k, v in r.items() if k != "at_min"} for r in session["routes"]
        ]

    try:
        append_outdoor_session(entry, user_id)
    except ValueError as e:
        if "authenticated user_id" in str(e):
            raise HTTPException(status_code=401, detail="Authentication required to save outdoor session")
        raise HTTPException(status_code=422, detail=str(e))
    except OSError as e:
        logger.error("Failed to write outdoor log on finish: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to write outdoor log. Please try again.")

    # Remove the active session — the immutable record now lives in outdoor_logs.
    state = load_state(user_id)
    state["outdoor_active_sessions"] = [
        s for s in state.get("outdoor_active_sessions", []) if s.get("session_id") != session_id
    ]
    save_state(state, user_id)

    load_score = compute_outdoor_load_score(entry)

    # B273: close the loop on the week plan (status done + load + ripple) —
    # best-effort, the log above is the primary record and is already saved.
    plan_synced = False
    try:
        plan_synced = _sync_plan_after_outdoor_log(state, user_id, entry, load_score)
    except Exception:
        logger.exception(
            "B273: plan sync after outdoor finish failed — log saved, plan untouched"
        )

    return {
        "status": "done",
        "date": entry["date"],
        "duration_minutes": dur["minutes"],
        "duration_capped": dur["capped"],
        "duration_raw_minutes": dur["raw_minutes"],
        "duration_source": dur["source"],
        "load_score": load_score,
        "plan_synced": plan_synced,
    }


@router.delete("/session/{session_id}", dependencies=[Depends(require_active_subscription)])
def cancel_outdoor_session(session_id: str, user_id: Optional[str] = Depends(get_user_id)):
    """Discard an active outdoor session without logging it."""
    state = load_state(user_id)
    active = state.get("outdoor_active_sessions", [])
    remaining = [s for s in active if s.get("session_id") != session_id]
    if len(remaining) == len(active):
        raise HTTPException(status_code=404, detail=f"Active outdoor session '{session_id}' not found")
    state["outdoor_active_sessions"] = remaining
    save_state(state, user_id)
    return {"status": "ok"}


# ── Slot conversion ─────────────────────────────────────────────────────

@router.post("/convert-slot", dependencies=[Depends(require_active_subscription)])
def convert_outdoor_slot(req: ConvertSlotRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Convert an outdoor day slot to gym/home and suggest a session."""
    from backend.engine.replanner_v1 import suggest_sessions

    state = load_state(user_id)
    macrocycle = state.get("macrocycle")
    if not macrocycle:
        raise HTTPException(status_code=400, detail="No macrocycle generated yet")

    suggestions = suggest_sessions(
        user_state=state,
        target_date=req.date,
        location=req.new_location,
    )

    return {
        "date": req.date,
        "new_location": req.new_location,
        "suggestions": suggestions,
    }
