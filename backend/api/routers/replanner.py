"""Replanner router — day overrides and event-based adaptation."""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import REPO_ROOT, assert_plan_not_paused, current_phase_and_week, get_user_id, is_past_week, load_state, require_active_subscription, save_state, week_num_to_phase_context
from backend.api.models import EventsRequest, OverrideRequest, QuickAddRequest
from backend.engine.outdoor_log import compute_outdoor_load_score, load_outdoor_sessions, remove_outdoor_session
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import apply_day_add, apply_day_override, apply_events, suggest_sessions
from backend.engine.resolve_session import resolve_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/replanner", tags=["replanner"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


def _session_display_name(session_id: str) -> str:
    """Return the human-readable name for a session, reading from its JSON file."""
    path = REPO_ROOT / SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = data.get("session_name") or data.get("name")
            if name:
                return name
        except Exception:
            pass
    # Fallback: format session_id as title
    return session_id.replace("_", " ").title()


def _get_supplementary_sessions(location: str) -> list:
    """Scan session catalog for supplementary sessions compatible with *location*.

    B206: location viability comes from _SESSION_META (source of truth), not from
    the session JSON's (now removed) context.location hint.
    """
    results = []
    sessions_dir = REPO_ROOT / SESSIONS_DIR
    if not sessions_dir.is_dir():
        return results
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not data.get("supplementary"):
            continue
        session_id = data.get("id") or path.stem
        meta = _SESSION_META.get(session_id)
        viable_locs = set(meta.get("location") or ()) if meta else set()
        if viable_locs and location not in viable_locs:
            continue
        results.append({
            "session_id": session_id,
            "session_name": data.get("name", path.stem.replace("_", " ").title()),
            "required_equipment": data.get("required_equipment", []),
            "time_budget": data.get("time_budget", ""),
        })
    return results


# B287/R-2: event types that rebuild the week from scratch (generate_phase_week)
# rather than editing individual sessions. Only these are refused on a past week.
# Keep in sync with the apply_events branches in replanner_v1.py — today
# set_availability is the single call site of generate_phase_week.
_REGENERATING_EVENT_TYPES = frozenset({"set_availability"})


def _prev_week_days(state: dict, start_date: Optional[str]) -> Optional[list]:
    """B287/R-5: days of the week preceding *start_date*, for cross-week spacing.

    Hot-store only: N-1 is inside the hot window by design (A221), and a missing
    neighbour simply means no seed → the previous, Monday-blind behaviour.
    """
    if not start_date:
        return None
    try:
        prev_monday = (
            datetime.strptime(start_date, "%Y-%m-%d").date() - timedelta(days=7)
        ).isoformat()
    except (ValueError, TypeError):
        return None
    prev_plan = (state.get("week_plans") or {}).get(prev_monday)
    if not prev_plan:
        return None
    try:
        return (prev_plan.get("weeks") or [{}])[0].get("days") or None
    except (IndexError, AttributeError):
        return None


def persist_week_plan(updated: dict, state: dict, user_id) -> None:
    """Save modified plan to per-week cache and (if current) to legacy cache.

    Public helper: reused by backend/api/routers/feedback.py (A194).
    """
    start_key = updated.get("start_date", "")
    if not start_key:
        return

    if "week_plans" not in state:
        state["week_plans"] = {}
    state["week_plans"][start_key] = updated

    # Also update legacy current_week_plan if this IS the current week.
    # B287/R-6: the anchor must be pause-aware. This used to recompute it from
    # the RAW macrocycle start_date, so with a pause offset > 0 (A223) it never
    # matched the real current week — current_week_plan stayed stale until the
    # next GET /api/week/0, and its readers (feedback step 1, suggest-sessions,
    # adaptive replan) served an outdated plan. week_num_to_phase_context goes
    # through _effective_anchor, the single pause-aware definition.
    macrocycle = state.get("macrocycle")
    if macrocycle and macrocycle.get("phases"):
        try:
            current_start = week_num_to_phase_context(macrocycle, 0)["start_date"]
        except (ValueError, KeyError):
            current_start = None
        if current_start and start_key == current_start:
            state["current_week_plan"] = updated
    else:
        state["current_week_plan"] = updated

    save_state(state, user_id)


def _auto_resolve(week_plan: dict, state: dict, user_id: Optional[str] = None) -> None:
    """Resolve all sessions in a week plan inline (same logic as week router).

    B120: completed/skipped sessions with cached resolved data are never
    re-resolved — this protects past sessions from device-switch corruption.

    B287/R-7: the phase is taken from the plan being resolved, not from the
    calendar. The resolver derives it from date.today() when phase is None
    (resolve_session.py, A121 phase-aware ordering), so an override or quick-add
    on a FUTURE week that sits in a different phase used to order its exercises
    with today's phase. Per-session phase_id (stamped by the planner and by
    quick-add) with the plan snapshot as fallback — the week router passes its
    own ctx["phase_id"] the same way.
    """
    _plan_phase = (week_plan.get("profile_snapshot") or {}).get("phase_id")
    # B268: exercise_ids planned on EARLIER days this week, fed into the
    # resolver as recency so a session repeated on a later day varies.
    planned_recent: list = []
    for week_block in week_plan.get("weeks", []):
        for day_entry in week_block.get("days", []):
            day_ex_ids: list = []  # B268: this day's resolved exercise_ids
            for session_entry in day_entry.get("sessions", []):
                # A207: custom sessions carry their own exercises inline and
                # do not use the catalog resolver — skip to avoid log noise.
                if session_entry.get("is_custom"):
                    continue

                # B120: never re-resolve completed sessions with cached data
                # B153b: never re-resolve sessions the user explicitly edited
                if (
                    session_entry.get("status") in ("done", "skipped")
                    and session_entry.get("resolved")
                ) or (
                    session_entry.get("_user_edited")
                    and session_entry.get("resolved")
                ):
                    continue

                session_id = session_entry.get("session_id", "")
                session_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
                full_path = REPO_ROOT / session_path
                if not full_path.exists():
                    logger.warning(
                        "_auto_resolve: session %r not found in catalog (user=%s), skipping resolution",
                        session_id, user_id,
                    )
                    session_entry["resolved"] = None
                    continue
                try:
                    resolve_state = deepcopy(state)
                    resolve_state["context"] = {
                        **resolve_state.get("context", {}),
                        "location": session_entry.get("location", "home"),
                        "gym_id": session_entry.get("gym_id"),
                        "target_date": day_entry.get("date"),
                        "date": day_entry.get("date"),
                    }
                    resolved = resolve_session(
                        phase=session_entry.get("phase_id") or _plan_phase,
                        repo_root=str(REPO_ROOT),
                        session_path=session_path,
                        templates_dir=TEMPLATES_DIR,
                        exercises_path=EXERCISES_PATH,
                        out_path="",
                        user_state_override=resolve_state,
                        write_output=False,
                        user_id=user_id,
                        extra_recent_ex_ids=planned_recent,  # B268
                    )
                    session_entry["resolved"] = resolved
                    # A stale marker would keep an error banner up forever.
                    session_entry.pop("resolve_error", None)
                    # B268: collect this day's exercises for LATER days only
                    for _inst in (resolved or {}).get("resolved_session", {}).get("exercise_instances", []):
                        _eid = _inst.get("exercise_id")
                        if _eid:
                            day_ex_ids.append(_eid)
                except Exception as _resolve_err:
                    logger.error(
                        "_auto_resolve: session resolution failed for %r: %s",
                        session_entry.get("session_id"), _resolve_err, exc_info=True,
                    )
                    session_entry["resolved"] = None
                    # A245 E-3 (B17): see the identical marker in week.py —
                    # `resolved=None` cannot tell a transient failure apart from
                    # a legitimately empty session.
                    session_entry["resolve_error"] = True
            # B268: a day's exercises become recency for subsequent days only
            planned_recent.extend(day_ex_ids)


@router.post("/override", dependencies=[Depends(require_active_subscription)])
def override(req: OverrideRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Apply a day override (change a day's session by intent)."""
    state = load_state(user_id)
    assert_plan_not_paused(state)  # A223

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    # B257: past weeks are immutable. Reject any override targeting a week whose
    # Monday is before the current week's — set_availability would regenerate it
    # (generate_phase_week), and every other intent would mutate completed
    # sessions. Only explicit user edit may touch past weeks.
    _ws = week_plan.get("start_date")
    if _ws and is_past_week(_ws):
        raise HTTPException(
            status_code=422,
            detail="Cannot modify a past week — past sessions are immutable.",
        )

    # B96: pass gyms so override can check equipment compatibility
    equipment = state.get("equipment", {})
    gyms = equipment.get("gyms", [])

    try:
        updated = apply_day_override(
            week_plan,
            intent=req.intent,
            location=req.location,
            reference_date=req.reference_date,
            slot=req.slot,
            phase_id=req.phase_id,
            target_date=req.target_date,
            gym_id=req.gym_id,
            gyms=gyms,
            session_index=req.session_index,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Override failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Override failed. Please try again.")

    persist_week_plan(updated, state, user_id)

    # Auto-resolve all sessions so the frontend gets exercises inline
    _auto_resolve(updated, state, user_id)

    return {"week_plan": updated}


@router.get("/suggest-sessions")
def get_suggestions(target_date: str, location: str = "gym", user_id: Optional[str] = Depends(get_user_id)):
    """Suggest sessions to quick-add on a given date."""
    state = load_state(user_id)
    week_plan = state.get("current_week_plan")
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="No current week plan — generate one from GET /api/week/0 first",
        )

    # Build session pool from macrocycle context if available
    session_pool = None
    macrocycle = state.get("macrocycle")
    if macrocycle:
        snapshot = week_plan.get("profile_snapshot") or {}
        phase_id = snapshot.get("phase_id", "base")
        from backend.engine.macrocycle_v1 import _build_session_pool
        session_pool = _build_session_pool(phase_id)

    try:
        suggestions = suggest_sessions(
            week_plan,
            target_date,
            location,
            session_pool=session_pool,
        )
    except Exception as e:
        logger.error("Suggestion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Suggestion failed. Please try again.")

    # Enrich suggestions with human-readable names and equipment info
    for s in suggestions:
        s["session_name"] = _session_display_name(s["session_id"])
        path = REPO_ROOT / SESSIONS_DIR / f"{s['session_id']}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                s["required_equipment"] = data.get("required_equipment", [])
            except Exception:
                s["required_equipment"] = []
        else:
            s["required_equipment"] = []

    # Build supplementary sessions list (phase-agnostic, filtered by location/equipment)
    supplementary = _get_supplementary_sessions(location)

    return {"suggestions": suggestions, "supplementary": supplementary}


@router.post("/quick-add", dependencies=[Depends(require_active_subscription)])
def quick_add(req: QuickAddRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Add an extra session to a day without replacing existing ones."""
    state = load_state(user_id)
    assert_plan_not_paused(state)  # A223

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    try:
        updated, warnings, adjustments = apply_day_add(
            week_plan,
            session_id=req.session_id,
            target_date=req.target_date,
            slot=req.slot,
            location=req.location,
            phase_id=req.phase_id,
            gym_id=req.gym_id,
            # B287/R-5: trailing days of the preceding week, so the Sunday→Monday
            # finger gap is checked instead of the scan starting blind at Monday.
            prev_days=_prev_week_days(state, week_plan.get("start_date")),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Quick-add failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Quick-add failed. Please try again.")

    persist_week_plan(updated, state, user_id)

    _auto_resolve(updated, state, user_id)

    # B287/R-5: `adjustments` tells the client exactly what reconciliation changed
    # about the session it just added (empty list = nothing was touched).
    return {"week_plan": updated, "warnings": warnings, "adjustments": adjustments}


@router.post("/events", dependencies=[Depends(require_active_subscription)])
def events(req: EventsRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Apply a list of events (move, mark_done, mark_skipped, etc.) to a week plan."""
    state = load_state(user_id)
    assert_plan_not_paused(state)  # A223 — no week-plan mutation while paused

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    # B287/R-2: /override has carried the B257 past-week guard since B257, but
    # /events never did — and `set_availability` is reachable from BOTH (it is
    # the only event type that calls generate_phase_week). Applied to the
    # client-supplied start_date, exactly like /override.
    #
    # Scoped to regenerating event types on purpose: a blanket guard would also
    # reject mark_done/mark_skipped on a past week, which the UI still renders
    # and allows whenever a saved plan exists (week/page.tsx — past_week_unavailable
    # is only set when there is NO saved plan). Retroactively ticking a session
    # you forgot to mark is explicit user edit, the one exception the
    # immutability pillar allows. Regeneration is not.
    _ws = week_plan.get("start_date")
    if _ws and is_past_week(_ws) and any(
        ev.get("event_type") in _REGENERATING_EVENT_TYPES for ev in req.events
    ):
        raise HTTPException(
            status_code=422,
            detail="Cannot modify a past week — past sessions are immutable.",
        )

    availability = state.get("availability")
    planning_prefs = state.get("planning_prefs")
    gyms = (state.get("equipment") or {}).get("gyms")
    # B283: enrich with catalog display fields (name/cues/video/load_model) so
    # the week-plan slot that add_custom_session copies carries what the real
    # guided player renders. Read-path only; replanner_v1 logic untouched.
    from backend.api.routers.custom_session import enrich_custom_sessions_for_play
    custom_sessions = enrich_custom_sessions_for_play(state.get("custom_sessions") or [])

    # For complete_outdoor events, compute outdoor load score from JSONL log
    for ev in req.events:
        if ev.get("event_type") == "complete_outdoor" and ev.get("date"):
            outdoor_sessions = load_outdoor_sessions(user_id, since_date=ev["date"])
            matching = [s for s in outdoor_sessions if s.get("date") == ev["date"]]
            if matching:
                ev["outdoor_load_score"] = compute_outdoor_load_score(matching[-1])

    try:
        updated = apply_events(
            week_plan,
            req.events,
            availability=availability,
            planning_prefs=planning_prefs,
            gyms=gyms,
            custom_sessions=custom_sessions,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Events application failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Events application failed. Please try again.")

    # Remove outdoor log entries for any undo_outdoor events so re-logging
    # doesn't produce duplicates.
    for ev in req.events:
        if ev.get("event_type") == "undo_outdoor" and ev.get("date"):
            remove_outdoor_session(user_id, ev["date"])

    # --- B116: Persistent outdoor log in user_state ---
    outdoor_log = state.setdefault("outdoor_log", [])
    for ev in req.events:
        evt = ev.get("event_type")
        ev_date = ev.get("date")
        if evt == "complete_outdoor" and ev_date:
            # Find day in updated plan to grab spot details
            day = next(
                (d for w in updated.get("weeks", []) for d in w.get("days", []) if d.get("date") == ev_date),
                None,
            )
            entry = {
                "date": ev_date,
                "spot_name": (day or {}).get("outdoor_spot_name", ev.get("spot_name", "")),
                "spot_id": (day or {}).get("outdoor_spot_id", ev.get("spot_id", "")),
                "discipline": (day or {}).get("outdoor_discipline", ev.get("discipline", "both")),
                "load_score": ev.get("outdoor_load_score", 0),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            outdoor_log.append(entry)
        elif evt == "undo_outdoor" and ev_date:
            state["outdoor_log"] = [e for e in outdoor_log if e.get("date") != ev_date]

    # --- B117: Persistent session completion log ---
    completion_log = state.setdefault("session_completion_log", [])
    for ev in req.events:
        evt = ev.get("event_type")
        ev_date = ev.get("date")
        if evt == "mark_done" and ev_date:
            completion_log.append({
                "date": ev_date,
                "session_id": ev.get("session_ref", ""),
                "status": "done",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
        elif evt == "mark_skipped" and ev_date:
            completion_log.append({
                "date": ev_date,
                "session_id": ev.get("session_ref", ""),
                "status": "skipped",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
        elif evt == "mark_planned" and ev_date:
            # Undo: remove matching entry
            ref = ev.get("session_ref", "")
            state["session_completion_log"] = [
                e for e in completion_log
                if not (e.get("date") == ev_date and e.get("session_id") == ref)
            ]
            completion_log = state["session_completion_log"]

    persist_week_plan(updated, state, user_id)

    # Auto-resolve all sessions so the frontend gets exercises inline
    _auto_resolve(updated, state, user_id)

    return {"week_plan": updated}
