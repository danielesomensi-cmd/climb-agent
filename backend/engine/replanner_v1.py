from __future__ import annotations

import functools
import json
import logging
import math
import os
from copy import deepcopy

from backend.engine.equipment_utils import expand_equipment
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

from backend.engine.macrocycle_v1 import _build_session_pool
from backend.engine.planner_v2 import _INTENSITY_TO_LOAD, _SESSION_META, generate_phase_week
from backend.engine.other_activity_v1 import (
    ensure_other_activities_list,
    normalize_other_activities,
    other_activity_slots,
    select_activity,
    sort_other_activities,
)

def _recovery_gap(plan: Dict[str, Any]) -> int:
    """B165b: read recovery_multiplier from plan and return spacing gap (same formula as planner)."""
    raw = (plan.get("profile_snapshot") or {}).get("recovery_multiplier", 1.0)
    try:
        mult = float(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid recovery_multiplier %r, defaulting to 1.0", raw)
        mult = 1.0
    return math.ceil(1 * mult)


def _safe_hard_cap(snapshot: Dict[str, Any]) -> int:
    """Return hard_cap_per_week as int, defaulting to 3 on bad input."""
    raw = (snapshot or {}).get("hard_cap_per_week", 3)
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid hard_cap_per_week %r, defaulting to 3", raw)
        return 3


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SESSIONS_DIR = os.path.join(_REPO_ROOT, "backend", "catalog", "sessions", "v1")

@functools.lru_cache(maxsize=None)
def _get_required_equipment(session_id: str) -> tuple:
    """Load required_equipment from session JSON file (cached via lru_cache)."""
    path = os.path.join(_SESSIONS_DIR, f"{session_id}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            eq = data.get("required_equipment", [])
    except FileNotFoundError:
        logger.warning("_get_required_equipment: session file not found for %r — assuming no required equipment", session_id)
        eq = []
    except json.JSONDecodeError as e:
        logger.warning("_get_required_equipment: JSON decode error for %r: %s — assuming no required equipment", session_id, e)
        eq = []
    return tuple(eq)


def _find_gym_change_replacement(
    original_sid: str,
    new_location: str,
    gym_equipment: set,
    is_finger_session: bool,
) -> str:
    """Find replacement session when changing gym/location makes original incompatible.

    Fallback chain:
    1. complementary_conditioning (home+gym, no required_equipment)
    2. finger_strength_home — only if going home AND original was a finger session
    3. regeneration_easy (universal final fallback)
    """
    # First fallback: complementary_conditioning
    cc_meta = _meta_for("complementary_conditioning")
    if new_location in cc_meta.get("location", ()):
        cc_eq = set(_get_required_equipment("complementary_conditioning"))
        if not cc_eq or (new_location != "gym") or cc_eq.issubset(gym_equipment):
            return "complementary_conditioning"

    # Universal fallback
    return "regeneration_easy"

# Phase-aware intent → session_id mapping (uses planner_v2 session catalog)
INTENT_TO_SESSION = {
    "rest": "regeneration_easy",
    "recovery": "yoga_recovery",
    "technique": "technique_focus_gym",
    "strength": "strength_long",
    "power": "power_contact_gym",
    "power_endurance": "power_endurance_gym",
    "aerobic_endurance": "endurance_aerobic_gym",
    "core": "complementary_conditioning",
    "prehab": "prehab_maintenance",
    "flexibility": "flexibility_full",
    "finger_maintenance": "finger_maintenance_home",
    "finger_max": "finger_strength_home",
    "projecting": "power_contact_gym",
    "endurance": "endurance_aerobic_gym",
    "hard": "strength_long",
}

# B97: outdoor intent → discipline mapping (no session_id — outdoor is logged separately)
OUTDOOR_INTENT_TO_DISCIPLINE = {
    "outdoor_easy": "both",
    "outdoor_projecting": "both",
    "outdoor_volume": "lead",
    "outdoor_boulder": "boulder",
}
SLOTS = ("morning", "lunch", "evening")

# Load points for complementary sport feedback
COMPLEMENTARY_LOAD_EASY = 10
COMPLEMENTARY_LOAD_OK = 20
COMPLEMENTARY_LOAD_HARD = 30

COMPLEMENTARY_LOAD_MAP = {
    "easy": COMPLEMENTARY_LOAD_EASY,
    "ok": COMPLEMENTARY_LOAD_OK,
    "hard": COMPLEMENTARY_LOAD_HARD,
}

# Outdoor load threshold for triggering next-day ripple (matches high intensity)
OUTDOOR_RIPPLE_THRESHOLD = 65


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _find_day(plan: Dict[str, Any], target_date: str) -> Dict[str, Any]:
    # B157: search all weeks in the plan, not just weeks[0]
    for week_block in plan.get("weeks", []):
        for day in week_block.get("days", []):
            if day.get("date") == target_date:
                return day
    # Build helpful error with available date range
    all_dates = [
        d.get("date", "?")
        for wb in plan.get("weeks", [])
        for d in wb.get("days", [])
    ]
    date_range = f"{all_dates[0]}..{all_dates[-1]}" if all_dates else "empty"
    raise ValueError(
        f"Date not present in plan: {target_date} (plan covers {date_range}). "
        f"Go back to the week view and retry."
    )


def _default_gym_id_from_plan(plan: Dict[str, Any]) -> Optional[str]:
    profile = plan.get("profile_snapshot") or {}
    prefs = profile.get("planning_prefs") or {}
    gym_id = prefs.get("default_gym_id")
    return gym_id if isinstance(gym_id, str) and gym_id else None


def _session_matches(session: Dict[str, Any], *, session_ref: Optional[str], slot: Optional[str]) -> bool:
    if session_ref and session.get("session_id") != session_ref:
        return False
    if slot and session.get("slot") != slot:
        return False
    return True


def _extract_session(day: Dict[str, Any], *, session_ref: Optional[str], slot: Optional[str]) -> Dict[str, Any]:
    sessions = day.get("sessions") or []
    for idx, session in enumerate(sessions):
        if _session_matches(session, session_ref=session_ref, slot=slot):
            return sessions.pop(idx)
    raise ValueError(f"Session not found for day={day.get('date')} session_ref={session_ref} slot={slot}")


def _insert_or_replace(day: Dict[str, Any], moved: Dict[str, Any], to_slot: str) -> None:
    moved["slot"] = to_slot
    sessions = day.setdefault("sessions", [])
    for idx, existing in enumerate(sessions):
        if existing.get("slot") == to_slot:
            sessions[idx] = moved
            break
    else:
        sessions.append(moved)
    sessions.sort(key=lambda s: (SLOTS.index(s.get("slot") if s.get("slot") in SLOTS else "evening"), s.get("priority", 99), s.get("session_id", "")))


def _slots_from_day(day: Dict[str, Any]) -> set[str]:
    return {s.get("slot") for s in (day.get("sessions") or []) if s.get("slot") in SLOTS}


def _meta_for(session_id: str) -> Dict[str, Any]:
    """Get session metadata from planner_v2's _SESSION_META."""
    return _SESSION_META.get(session_id, {
        "hard": False, "finger": False, "intensity": "low",
        "climbing": False, "location": ("home", "gym"),
    })


def _build_fill_session(plan: Dict[str, Any], day: Dict[str, Any], slot: str, *, kind: str) -> Dict[str, Any]:
    # deterministic conservative fill using planner_v2 sessions
    session_id = "regeneration_easy" if kind == "recovery" else "complementary_conditioning"
    meta = _meta_for(session_id)
    location = "home"
    gym_id = None
    if any(s.get("location") == "gym" for s in day.get("sessions") or []):
        location = "gym"
        gym_id = _default_gym_id_from_plan(plan)
    return {
        "slot": slot,
        "session_id": session_id,
        "location": location,
        "gym_id": gym_id,
        "intensity": meta["intensity"],
        "estimated_load_score": _INTENSITY_TO_LOAD.get(meta["intensity"], 40),
        "constraints_applied": ["replanner_fill"],
        "tags": {"hard": meta["hard"], "finger": meta["finger"], **({"test": True} if meta.get("test") else {})},
        "explain": ["deterministic refill", f"fill_kind={kind}"],
    }


def suggest_sessions(
    plan: Dict[str, Any],
    target_date: str,
    location: str,
    *,
    session_pool: Optional[List[str]] = None,
    max_suggestions: int = 3,
) -> List[Dict[str, Any]]:
    """Return up to *max_suggestions* candidate sessions for quick-add.

    Scoring is deterministic — same inputs always yield the same output.
    """
    # --- Input validation ---
    _VALID_LOCATIONS = {"home", "gym", "outdoor", "travel"}
    if location not in _VALID_LOCATIONS:
        raise ValueError(f"suggest_sessions: invalid location '{location}', must be one of {_VALID_LOCATIONS}")
    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"suggest_sessions: invalid target_date '{target_date}', expected YYYY-MM-DD") from exc

    phase_id = (plan.get("profile_snapshot") or {}).get("phase_id")
    if phase_id is None:
        logger.warning("suggest_sessions: profile_snapshot missing or has no phase_id — defaulting to 'base'")
        phase_id = "base"
    candidates = session_pool if session_pool is not None else _build_session_pool(phase_id)

    # Always include complementary add-on mini-sessions regardless of phase
    # Note: upper_body_weights and legs_strength moved to supplementary section (B-SUPP)
    _ALWAYS_SUGGESTIBLE = {"core_training"}
    for sid in _ALWAYS_SUGGESTIBLE:
        if sid not in candidates:
            candidates.append(sid)

    # Filter by location compatibility
    candidates = [
        sid for sid in candidates
        if location in _meta_for(sid).get("location", ("home", "gym"))
    ]

    # Collect already-scheduled session IDs (skip done/skipped)
    scheduled: set[str] = set()
    for day in (plan.get("weeks") or [{}])[0].get("days", []):
        for s in day.get("sessions", []):
            if s.get("status") not in ("done", "skipped"):
                scheduled.add(s.get("session_id", ""))

    # Determine hard cap
    hard_cap = _safe_hard_cap(plan.get("profile_snapshot"))
    hard_count = 0
    finger_adjacent = False
    for day in (plan.get("weeks") or [{}])[0].get("days", []):
        if any((s.get("tags") or {}).get("hard") and s.get("status") != "done" for s in day.get("sessions", [])):
            hard_count += 1
        # Check if adjacent day has finger session
        try:
            target_d = _parse_date(target_date)
            day_d = _parse_date(day["date"])
            if abs((target_d - day_d).days) <= _recovery_gap(plan) and day["date"] != target_date:
                if any((s.get("tags") or {}).get("finger") for s in day.get("sessions", [])):
                    finger_adjacent = True
        except (KeyError, ValueError):
            logger.warning("Failed to check finger adjacency for target_date=%s", target_date)

    # Check if target_date follows a hard day (within recovery gap)
    follows_hard = False
    try:
        target_d = _parse_date(target_date)
        gap = _recovery_gap(plan)
        for i in range(1, gap + 1):
            check_date = (target_d - timedelta(days=i)).isoformat()
            for day in (plan.get("weeks") or [{}])[0].get("days", []):
                if day.get("date") == check_date:
                    if any((s.get("tags") or {}).get("hard") for s in day.get("sessions", [])):
                        follows_hard = True
                    break
            if follows_hard:
                break
    except (KeyError, ValueError):
        logger.warning("Failed to check hard-day adjacency for target_date=%s", target_date)

    # Score each candidate
    scored: List[tuple] = []
    for sid in candidates:
        meta = _meta_for(sid)
        score = 0

        # +10 if not already in week
        if sid not in scheduled:
            score += 10

        # +5 if recovery/complementary after hard day
        if follows_hard and not meta.get("hard") and meta.get("intensity") in ("low", "medium"):
            score += 5

        # -1000 if hard and hard cap reached
        if meta.get("hard") and hard_count >= hard_cap:
            score -= 1000

        # -1000 if finger and adjacent day has finger
        if meta.get("finger") and finger_adjacent:
            score -= 1000

        # Reason string for UX
        reason_parts = []
        if sid not in scheduled:
            reason_parts.append("adds variety")
        if follows_hard and not meta.get("hard"):
            reason_parts.append("good after a hard day")
        if meta.get("hard"):
            reason_parts.append("high intensity")
        reason = "; ".join(reason_parts) if reason_parts else "available"

        scored.append((score, sid, meta, reason))

    # Sort: highest score first, then alphabetical by session_id for determinism
    scored.sort(key=lambda t: (-t[0], t[1]))

    results: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _score, sid, meta, reason in scored:
        if sid in seen:
            continue
        seen.add(sid)
        results.append({
            "session_id": sid,
            "intensity": meta.get("intensity", "medium"),
            "estimated_load_score": _INTENSITY_TO_LOAD.get(meta.get("intensity", "medium"), 40),
            "reason": reason,
        })
        if len(results) >= max_suggestions:
            break

    return results


def apply_day_add(
    plan: Dict[str, Any],
    *,
    session_id: str,
    target_date: str,
    slot: str = "evening",
    location: str,
    phase_id: Optional[str] = None,
    gym_id: Optional[str] = None,
    force: bool = False,
    prev_days: Optional[Sequence[Dict[str, Any]]] = None,
) -> tuple:
    """Append a session to an existing day (quick-add).

    Returns ``(updated_plan, warnings, adjustments)``.

    A254: when *force* is true the added session is pinned — the reconcile
    enforcers skip downshifting THIS session (the user keeps the hard session at
    their own risk). Everything else the user did not force still reconciles
    normally, and a forced finger session still anchors the following days'
    spacing (the injury clock runs whether or not the session was forced).

    B287/R-5: this path used to skip ``_reconcile`` entirely — the 48h finger
    gap and the weekly hard cap were reported as warnings but never enforced, so
    a quick-add could put two finger sessions back to back. Reconciliation now
    runs, and every downshift it makes is returned in *adjustments* so the
    caller can tell the user what happened: enforcement must never be silent on
    a session the user explicitly added.
    """
    # --- Input validation ---
    if not session_id:
        raise ValueError("apply_day_add: session_id must be a non-empty string")
    if session_id not in _SESSION_META:
        raise ValueError(f"apply_day_add: unknown session_id '{session_id}'")
    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"apply_day_add: invalid target_date '{target_date}', expected YYYY-MM-DD") from exc

    updated = deepcopy(plan)
    updated.setdefault("adaptations", [])
    target_day = _find_day(updated, target_date)

    # Slot conflict check (sessions + other_activity slot)
    for s in target_day.get("sessions", []):
        if s.get("slot") == slot:
            raise ValueError(f"Slot '{slot}' already occupied on {target_date}")
    if slot in other_activity_slots(target_day):
        raise ValueError(f"Slot '{slot}' already occupied by other activity on {target_date}")

    meta = _meta_for(session_id)
    effective_phase = phase_id or (updated.get("profile_snapshot") or {}).get("phase_id", "base")
    effective_gym_id = gym_id or (_default_gym_id_from_plan(updated) if location == "gym" else None)

    new_session = {
        "slot": slot,
        "session_id": session_id,
        "location": location,
        "gym_id": effective_gym_id,
        "phase_id": effective_phase,
        "intensity": meta["intensity"],
        "estimated_load_score": _INTENSITY_TO_LOAD.get(meta["intensity"], 40),
        "constraints_applied": ["quick_add"] + (["user_forced"] if force else []),
        "tags": {"hard": meta["hard"], "finger": meta["finger"], **({"test": True} if meta.get("test") else {})},
        "explain": ["user quick-add session", f"added_session={session_id}"],
        # A254: persisted so later reconciles (e.g. a second quick-add) keep the pin.
        **({"forced": True} if force else {}),
    }

    target_day.setdefault("sessions", []).append(new_session)
    target_day["sessions"].sort(
        key=lambda s: (SLOTS.index(s.get("slot") if s.get("slot") in SLOTS else "evening"), s.get("priority", 99), s.get("session_id", ""))
    )

    # Ripple day+1 only (spacing enforcement handled by _reconcile)
    if meta["hard"] or meta["finger"]:
        target_d = _parse_date(target_date)
        ripple_key = (target_d + timedelta(days=1)).isoformat()
        try:
            ripple_day = _find_day(updated, ripple_key)
        except ValueError:
            ripple_day = None

        if ripple_day and ripple_day.get("sessions"):
            recovery_meta = _meta_for("regeneration_easy")
            comp_meta = _meta_for("complementary_conditioning")
            next_sessions = []
            for session in ripple_day["sessions"]:
                # B120: never replace completed/skipped sessions via ripple
                if session.get("status") in ("done", "skipped"):
                    next_sessions.append(session)
                    continue
                is_hard = (session.get("tags") or {}).get("hard")
                is_low = session.get("intensity") == "low"
                if is_hard:
                    next_sessions.append({
                        "slot": session.get("slot", "evening"),
                        "session_id": "complementary_conditioning",
                        "location": session.get("location", location),
                        "gym_id": session.get("gym_id", effective_gym_id),
                        "phase_id": effective_phase,
                        "intensity": comp_meta["intensity"],
                        "constraints_applied": ["quick_add_ripple"],
                        "tags": {"hard": False, "finger": False},
                        "explain": ["hard→medium after quick-add", f"source_day={target_date}"],
                    })
                elif not is_low:
                    next_sessions.append({
                        "slot": session.get("slot", "evening"),
                        "session_id": "regeneration_easy",
                        "location": session.get("location", location),
                        "gym_id": session.get("gym_id", effective_gym_id),
                        "phase_id": effective_phase,
                        "intensity": recovery_meta["intensity"],
                        "constraints_applied": ["quick_add_ripple"],
                        "tags": {"hard": False, "finger": False},
                        "explain": ["medium→low after quick-add", f"source_day={target_date}"],
                    })
                else:
                    next_sessions.append(session)
            ripple_day["sessions"] = next_sessions

    # Warnings (don't block) — computed BEFORE reconciliation so the cap warning
    # still reflects what the user asked for, not the already-corrected plan.
    warnings: List[str] = []
    hard_cap = _safe_hard_cap(updated.get("profile_snapshot"))
    hard_count = sum(
        1 for d in updated["weeks"][0]["days"]
        if any((s.get("tags") or {}).get("hard") and s.get("status") != "done" for s in d.get("sessions", []))
    )
    if hard_count > hard_cap:
        warnings.append(f"Hard session count ({hard_count}) exceeds weekly cap ({hard_cap})")

    # B287/R-5: enforce spacing + caps (with cross-week seeding), never silently.
    adjustments = _reconcile(updated, prev_days=prev_days)

    updated["adaptations"].append({
        "type": "quick_add",
        "target_date": target_date,
        "session_id": session_id,
        "slot": slot,
        "adjustments": adjustments,
    })

    return (updated, warnings, adjustments)


def _recompute_day_status(day: Dict[str, Any]) -> None:
    """Derive day-level status from sessions, outdoor, and other-activity statuses."""
    statuses = [s.get("status") for s in (day.get("sessions") or [])]

    outdoor_st = day.get("outdoor_session_status")
    if outdoor_st == "done":
        statuses.append("done")
    elif outdoor_st is not None:
        statuses.append(None)  # blocks "done" until outdoor is completed

    # B276: a day is "done" only when every other activity is completed.
    for oa in normalize_other_activities(day):
        if oa.get("status") in ("done", "completed"):
            statuses.append("done")
        else:
            statuses.append(None)  # blocks "done" until this activity is completed

    if not statuses:
        day.pop("status", None)
        return
    if all(st == "done" for st in statuses):
        day["status"] = "done"
    elif all(st == "skipped" for st in statuses):
        day["status"] = "skipped"
    elif all(st in ("done", "skipped") for st in statuses):
        day["status"] = "done"
    else:
        day.pop("status", None)


def _is_preservable(session: Dict[str, Any]) -> bool:
    """Return True if *session* should survive a plan regeneration."""
    if session.get("status") in ("done", "skipped"):
        return True
    if "quick_add" in (session.get("constraints_applied") or []):
        return True
    return False


def _preserve_floor(plan: Dict[str, Any], today: Optional[str] = None) -> str:
    """B287: canonical ``preserve_before`` floor for in-place regenerations.

    ``max(today, plan.start_date)`` — days strictly before this floor are copied
    wholesale from the old plan and can never be rewritten:

    - regenerating the CURRENT week → floor is today, so Mon..yesterday are frozen
      and only the remaining days are re-planned;
    - regenerating a FUTURE week → floor is that week's Monday (no day precedes
      it), so nothing is force-copied, while the session-level merge still keeps
      any day the user completed ahead of time (``_is_preservable``).

    Past weeks never reach this helper: they are rejected upstream by the B257
    guard on ``/override`` and ``/events``.
    """
    today_str = today or datetime.now().strftime("%Y-%m-%d")
    start = plan.get("start_date") or ""
    # Both operands are ISO dates → lexicographic max is chronological max.
    return max(today_str, start) if start else today_str


def merge_prev_week_sessions(
    prev_plan: Dict[str, Any],
    new_plan: Dict[str, Any],
    preserve_before: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge preservable sessions from *prev_plan* into *new_plan* by date.

    Days before *preserve_before* (YYYY-MM-DD) are copied wholesale from the
    previous plan — sessions, status, outdoor fields and all — so that past
    completed days are never corrupted by regeneration.

    For days >= *preserve_before*, only done/skipped/quick-add sessions are
    merged into the freshly generated plan.

    Falls back to matching by weekday index when the dates don't overlap
    (e.g. macrocycle start_date shifted).
    """
    result = deepcopy(new_plan)

    preserve_date = (
        datetime.strptime(preserve_before, "%Y-%m-%d").date()
        if preserve_before
        else None
    )

    # Index previous days by date AND weekday for fallback
    prev_by_date: Dict[str, Dict[str, Any]] = {}
    prev_by_wd: Dict[int, Dict[str, Any]] = {}
    for day in (prev_plan.get("weeks") or [{}])[0].get("days", []):
        d = day.get("date")
        if d:
            prev_by_date[d] = day
            try:
                prev_by_wd[datetime.strptime(d, "%Y-%m-%d").weekday()] = day
            except ValueError:
                logger.warning("Invalid date format in previous plan day: %s", d)

    if not prev_by_date:
        return result

    for i, day in enumerate((result.get("weeks") or [{}])[0].get("days", [])):
        day_date_str = day.get("date")
        if not day_date_str:
            continue

        try:
            day_date = datetime.strptime(day_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # --- Hard guard: days before preserve_before → copy wholesale ---
        #
        # B287/R-4: EXACT DATE ONLY. The weekday fallback used to apply here too
        # and then re-stamped copied["date"], moving another day's completed
        # sessions onto this date — fabricated training history, and
        # _attach_feedback would then bind the wrong feedback via its
        # (date, session_id) key. When the date ranges don't overlap we now
        # leave the regenerated past day untouched: the immutable records
        # (session_completion_log, feedback logs, outdoor JSONL) remain the
        # source of truth for what actually happened.
        if preserve_date and day_date < preserve_date:
            prev_day = prev_by_date.get(day_date_str)
            if prev_day:
                # Same date by construction → no date rewrite happens.
                (result.get("weeks") or [{}])[0]["days"][i] = deepcopy(prev_day)
            elif prev_by_wd.get(day_date.weekday()):
                logger.warning(
                    "merge_prev_week_sessions: no same-date match for past day %s "
                    "(date ranges don't overlap) — skipping weekday fallback to "
                    "avoid re-stamping another day's history",
                    day_date_str,
                )
            continue

        # --- Days >= preserve_before: merge preservable sessions ---
        # The weekday fallback stays allowed here (B114: macrocycle start_date
        # shifted) because this path only merges preservable sessions into the
        # freshly generated day and never rewrites a date.
        prev_day = prev_by_date.get(day_date_str)
        same_date_match = prev_day is not None
        if not prev_day:
            wd = day_date.weekday()
            prev_day = prev_by_wd.get(wd)
        if not prev_day:
            continue

        # Bug 2: if today has any completed session or outdoor log → copy wholesale.
        # B287/R-4: wholesale copy requires a same-date match, for the reason above.
        if preserve_date and day_date == preserve_date and same_date_match:
            has_completed = any(
                s.get("status") == "done" for s in prev_day.get("sessions", [])
            )
            has_outdoor = prev_day.get("outdoor_session_status") == "done"
            if has_completed or has_outdoor:
                (result.get("weeks") or [{}])[0]["days"][i] = deepcopy(prev_day)
                continue

        to_merge = [s for s in prev_day.get("sessions", []) if _is_preservable(s)]
        prev_extras = {k: prev_day[k] for k in _DAY_LEVEL_FIELDS if k in prev_day}

        if to_merge:
            occupied_slots = {s.get("slot") for s in day.get("sessions", [])}
            for ps in to_merge:
                ps_slot = ps.get("slot")
                if ps_slot in occupied_slots:
                    day["sessions"] = [
                        ps if s.get("slot") == ps_slot else s
                        for s in day["sessions"]
                    ]
                else:
                    day.setdefault("sessions", []).append(ps)
                occupied_slots.add(ps_slot)

            day["sessions"].sort(
                key=lambda s: (
                    SLOTS.index(s.get("slot", "evening")),
                    s.get("priority", 99),
                    s.get("session_id", ""),
                )
            )

        if prev_extras:
            day.update(prev_extras)

    # Recompute day-level status from merged sessions
    for day in (result.get("weeks") or [{}])[0].get("days", []):
        _recompute_day_status(day)

    # B164: restore planned_load from previous plan (regen calculates only future days)
    prev_summary = prev_plan.get("weekly_load_summary") or {}
    prev_planned = prev_summary.get("planned_load") or prev_summary.get("total_load")
    if prev_planned is not None:
        result.setdefault("weekly_load_summary", {})["planned_load"] = prev_planned

    result["plan_revision"] = int(result.get("plan_revision") or 1) + 1
    return result


_DAY_LEVEL_FIELDS = (
    "outdoor_spot_name", "outdoor_spot_id", "outdoor_discipline",
    "outdoor_session_status",
    # A265: the day's pitch ladder (grades / attempts / rests). Lives at day
    # level like the rest of the outdoor block, so it MUST be preserved here —
    # a field missing from this tuple is dropped on the next week regeneration,
    # silently (the B276 / D263 failure mode).
    "outdoor_plan",
    # B276: new canonical list form. Legacy scalars kept for preserved
    # pre-B276 days that were never re-touched (single source: whichever exists).
    "other_activities",
    "other_activity", "other_activity_name",
    "other_activity_slot", "other_activity_status",
    "other_activity_feedback", "other_activity_load",
    "other_activity_duration_minutes",
)


def regenerate_preserving_completed(
    old_plan: Dict[str, Any],
    new_plan: Dict[str, Any],
    preserve_before: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge completed/skipped sessions from *old_plan* into *new_plan*.

    Days before *preserve_before* are copied wholesale from *old_plan*.
    """
    result = deepcopy(new_plan)

    preserve_date = (
        datetime.strptime(preserve_before, "%Y-%m-%d").date()
        if preserve_before
        else None
    )

    # Index old days by date
    old_by_date: Dict[str, Dict[str, Any]] = {}
    for day in (old_plan.get("weeks") or [{}])[0].get("days", []):
        d = day.get("date")
        if d:
            old_by_date[d] = day

    new_days = (result.get("weeks") or [{}])[0].get("days", [])
    for i, day in enumerate(new_days):
        date_key = day.get("date")
        if not date_key or date_key not in old_by_date:
            continue

        old_day = old_by_date[date_key]

        # B114: days before preserve_before → copy wholesale
        if preserve_date:
            try:
                day_d = datetime.strptime(date_key, "%Y-%m-%d").date()
            except ValueError:
                day_d = None
            if day_d and day_d < preserve_date:
                new_days[i] = deepcopy(old_day)
                continue
            # Bug 2: today with completed sessions → copy wholesale
            if day_d and day_d == preserve_date:
                has_completed = any(
                    s.get("status") == "done" for s in old_day.get("sessions", [])
                )
                has_outdoor = old_day.get("outdoor_session_status") == "done"
                if has_completed or has_outdoor:
                    new_days[i] = deepcopy(old_day)
                    continue

        # Normal merge: only done/skipped sessions
        completed_sessions = [
            s for s in old_day.get("sessions", [])
            if s.get("status") in ("done", "skipped")
        ]
        if not completed_sessions:
            # Still restore day-level fields
            extras = {k: old_day[k] for k in _DAY_LEVEL_FIELDS if k in old_day}
            if extras:
                day.update(extras)
            continue

        occupied_slots = {s.get("slot") for s in day.get("sessions", [])}
        for cs in completed_sessions:
            cs_slot = cs.get("slot")
            if cs_slot in occupied_slots:
                day["sessions"] = [
                    cs if s.get("slot") == cs_slot else s
                    for s in day["sessions"]
                ]
            else:
                day.setdefault("sessions", []).append(cs)
            occupied_slots.add(cs_slot)

        day["sessions"].sort(
            key=lambda s: (SLOTS.index(s.get("slot", "evening")), s.get("priority", 99), s.get("session_id", ""))
        )

        # Restore day-level fields
        extras = {k: old_day[k] for k in _DAY_LEVEL_FIELDS if k in old_day}
        if extras:
            day.update(extras)

    # Recompute day-level status from merged sessions (B98)
    for day in (result.get("weeks") or [{}])[0].get("days", []):
        _recompute_day_status(day)

    # B164: restore planned_load from old plan (regen calculates only future days)
    old_summary = old_plan.get("weekly_load_summary") or {}
    old_planned = old_summary.get("planned_load") or old_summary.get("total_load")
    if old_planned is not None:
        result.setdefault("weekly_load_summary", {})["planned_load"] = old_planned

    result["plan_revision"] = int(result.get("plan_revision") or 1) + 1
    return result


def _adjustment(day_date: str, session: Dict[str, Any], previous_id: str, reason: str) -> Dict[str, Any]:
    """B287/R-5: machine-readable record of a reconciliation downshift.

    ``reason`` reuses the exact ``constraints_applied`` vocabulary already
    stamped on the session, so caller and payload share one source of truth.
    """
    return {
        "date": day_date,
        "slot": session.get("slot"),
        "action": "downgraded",
        "reason": reason,
        "previous_session_id": previous_id,
        "session_id": session.get("session_id"),
    }


def _enforce_caps(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Downshift hard sessions beyond the weekly cap. Returns what it changed."""
    adjustments: List[Dict[str, Any]] = []
    hard_cap = _safe_hard_cap(plan.get("profile_snapshot"))
    days = plan["weeks"][0]["days"]
    hard_days = [d for d in days if any((s.get("tags") or {}).get("hard") and s.get("status") != "done" for s in d.get("sessions") or [])]
    if len(hard_days) > hard_cap:
        for day in reversed(hard_days[hard_cap:]):
            for session in day.get("sessions") or []:
                tags = session.get("tags") or {}
                # B287/R-8: never rewrite a completed or skipped session. The
                # day-level selection above already ignores done sessions, but
                # this inner loop used to downshift every hard session on the
                # day — including one the user had already trained.
                if session.get("status") in ("done", "skipped"):
                    continue
                # A254: a user-forced hard session stays past the cap, at their
                # own risk — but it still counts as a hard day above, so the cap
                # is genuinely honoured for everything else.
                if session.get("forced"):
                    continue
                if tags.get("hard"):
                    recovery_meta = _meta_for("regeneration_easy")
                    _previous_id = session.get("session_id")
                    session.update(
                        {
                            "session_id": "regeneration_easy",
                            "intensity": recovery_meta["intensity"],
                            "tags": {"hard": False, "finger": False},
                            "constraints_applied": ["hard_cap_downshift"],
                            "explain": ["hard cap exceeded after replanning", "deterministic downshift"],
                        }
                    )
                    adjustments.append(
                        _adjustment(day.get("date", ""), session, _previous_id, "hard_cap_downshift")
                    )
    return adjustments


def _seed_finger_date(prev_days: Optional[Sequence[Dict[str, Any]]]) -> Optional[Any]:
    """B287/R-5: latest finger day in the *preceding* week, for cross-week spacing.

    The in-week scan ignores ``status == "done"`` sessions, but the seed must
    NOT: a finger session actually performed last Sunday is exactly the one that
    has to block Monday. The 48h gap is injury protection — what happened counts
    more than what is still planned.
    """
    latest = None
    for day in prev_days or []:
        if not any((s.get("tags") or {}).get("finger") for s in day.get("sessions") or []):
            continue
        try:
            d = _parse_date(day["date"])
        except (KeyError, ValueError):
            continue
        if latest is None or d > latest:
            latest = d
    return latest


def _enforce_no_consecutive_finger(
    plan: Dict[str, Any],
    prev_days: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Enforce the finger recovery gap. Returns what it changed.

    *prev_days* seeds the scan with the trailing days of the previous week so
    the Sunday→Monday boundary is checked too (the planner already seeds itself
    this way; the replanner used to start every scan blind at Monday).
    """
    adjustments: List[Dict[str, Any]] = []
    days = plan["weeks"][0]["days"]
    last_finger_date = _seed_finger_date(prev_days)
    for day in days:
        cur = _parse_date(day["date"])
        finger_sessions = [s for s in day.get("sessions") or [] if (s.get("tags") or {}).get("finger")]

        # B287/R-8: a finger session that was actually PERFORMED constrains the
        # following days exactly like a planned one — the tendons don't care
        # whether the entry is ticked. The old scan excluded status == "done"
        # from the whole computation, so a finger session completed on Tuesday
        # never became the anchor and a Wednesday quick-add sailed through the
        # 48h gap. Skipped sessions never happened, so they constrain nothing.
        constrains = [s for s in finger_sessions if s.get("status") != "skipped"]
        # ...but only sessions that are neither done nor skipped may be REWRITTEN.
        # The inner loop used to downshift every finger session on the day,
        # completed ones included, silently rewriting immutable history.
        # A254: a user-forced session is likewise exempt from rewriting (kept at
        # the user's own risk) — but it still constrains the following days below.
        downshiftable = [
            s for s in finger_sessions
            if s.get("status") not in ("done", "skipped") and not s.get("forced")
        ]

        violates = bool(constrains) and last_finger_date is not None \
            and (cur - last_finger_date).days <= _recovery_gap(plan)

        if violates and downshiftable:
            for session in downshiftable:
                recovery_meta = _meta_for("regeneration_easy")
                _previous_id = session.get("session_id")
                session.update(
                    {
                        "session_id": "regeneration_easy",
                        "intensity": recovery_meta["intensity"],
                        "tags": {"hard": False, "finger": False},
                        "constraints_applied": ["finger_spacing_downshift"],
                        "explain": ["no consecutive finger days", "deterministic downshift"],
                    }
                )
                adjustments.append(
                    _adjustment(day.get("date", ""), session, _previous_id, "finger_spacing_downshift")
                )
            # The day stops being an anchor only if nothing finger-ish survived:
            # an immutable done session — or an A254-forced one — on this day
            # still constrains what follows (the tendons don't care that the hard
            # session was forced).
            if not any(s.get("status") == "done" or s.get("forced") for s in constrains):
                continue

        if constrains:
            last_finger_date = cur
    return adjustments


def _reconcile(
    plan: Dict[str, Any],
    prev_days: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Run both enforcers. Returns the aggregated list of downshifts.

    Existing callers ignore the return value — behaviour is unchanged for them.
    """
    adjustments = _enforce_no_consecutive_finger(plan, prev_days=prev_days)
    adjustments.extend(_enforce_caps(plan))
    return adjustments


def apply_events(
    plan: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    *,
    availability: Optional[Dict[str, Any]] = None,
    planning_prefs: Optional[Dict[str, Any]] = None,
    gyms: Optional[List[Dict[str, Any]]] = None,
    custom_sessions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    updated = deepcopy(plan)
    updated.setdefault("adaptations", [])

    for event in events:
        event_type = event.get("event_type")
        if event_type == "move_session":
            from_date = event.get("from_date")
            to_date = event.get("to_date")
            to_slot = event.get("to_slot")
            if not from_date:
                raise ValueError("move_session requires 'from_date'")
            if not to_date:
                raise ValueError("move_session requires 'to_date'")
            if not to_slot:
                raise ValueError("move_session requires 'to_slot'")
            from_day = _find_day(updated, from_date)
            # B120: block moving completed/skipped sessions (immutability pillar)
            ref = event.get("session_ref")
            from_slot = event.get("from_slot")
            for s in from_day.get("sessions") or []:
                if _session_matches(s, session_ref=ref, slot=from_slot):
                    if s.get("status") in ("done", "skipped"):
                        raise ValueError(
                            f"Cannot move a session with status '{s['status']}'"
                        )
                    break
            to_day = _find_day(updated, to_date)
            moved = _extract_session(from_day, session_ref=ref, slot=from_slot)
            _insert_or_replace(to_day, moved, to_slot)

            if event.get("from_slot") not in _slots_from_day(from_day):
                fill_kind = "accessory" if any((s.get("tags") or {}).get("hard") for s in from_day.get("sessions") or []) else "recovery"
                from_day.setdefault("sessions", []).append(_build_fill_session(updated, from_day, event["from_slot"], kind=fill_kind))

        elif event_type == "remove_session":
            day = _find_day(updated, event["date"])
            session_ref = event.get("session_ref")
            slot = event.get("slot")
            # Block removal of done/skipped sessions
            for s in day.get("sessions") or []:
                if _session_matches(s, session_ref=session_ref, slot=slot):
                    if s.get("status") in ("done", "skipped"):
                        raise ValueError(
                            f"Cannot remove a session with status '{s['status']}'"
                        )
                    break
            _extract_session(day, session_ref=session_ref, slot=slot)
            # If no sessions left, clear day-level status
            if not day.get("sessions"):
                day.pop("status", None)

        elif event_type == "mark_skipped":
            day = _find_day(updated, event["date"])
            removed = _extract_session(day, session_ref=event.get("session_ref"), slot=event.get("slot"))
            slot = removed.get("slot") or event.get("slot") or "evening"
            recovery = _build_fill_session(updated, day, slot, kind="recovery")
            recovery["status"] = "skipped"
            day.setdefault("sessions", []).append(recovery)
            _recompute_day_status(day)

        elif event_type == "mark_done":
            day = _find_day(updated, event["date"])
            for s in day.get("sessions") or []:
                if _session_matches(s, session_ref=event.get("session_ref"), slot=event.get("slot")):
                    s["status"] = "done"
                    break
            _recompute_day_status(day)

        elif event_type == "mark_planned":
            # B192: undo must clear ALL feedback-derived fields on the session,
            # not just `status`. Leaving `actual_exercises`, `feedback_summary`,
            # `exercise_feedback`, `session_duration_seconds` populated caused
            # ghost "OK" pills + "Completed · ~NN min" text after undo.
            #
            # NOT reverted on purpose: working_loads mutations from
            # progression_v1.apply_feedback (closed-loop adaptation). Reversing
            # closed-loop is complex and undo is rare — trade-off accepted.
            # Append-only logs (feedback_log) also stay intact.
            day = _find_day(updated, event["date"])
            matched = False
            for s in day.get("sessions") or []:
                if _session_matches(s, session_ref=event.get("session_ref"), slot=event.get("slot")):
                    s.pop("status", None)
                    for _k in (
                        "actual_exercises",
                        "feedback_summary",
                        "exercise_feedback",
                        "session_duration_seconds",
                        "session_load_actual",  # B312: also feedback-derived
                    ):
                        s.pop(_k, None)
                    matched = True
                    break
            if not matched:
                logger.warning(
                    "mark_planned no-op: session not found (date=%r, session_ref=%r, slot=%r)",
                    event.get("date"), event.get("session_ref"), event.get("slot"),
                )
            # If any session is no longer done/skipped, clear day-level status
            if not all(s.get("status") in ("done", "skipped") for s in day.get("sessions") or []):
                day.pop("status", None)

        elif event_type == "complete_other_activity":
            # B276: keyed by slot; falls back to the sole activity when no slot.
            day = _find_day(updated, event["date"])
            items = ensure_other_activities_list(day)
            item = select_activity(items, event.get("slot"))
            if item is None:
                raise ValueError(f"Date {event['date']} is not an other-activity day")
            feedback = event.get("feedback", "ok")
            item["status"] = "completed"
            item["feedback"] = feedback
            item["load"] = COMPLEMENTARY_LOAD_MAP.get(feedback, COMPLEMENTARY_LOAD_OK)
            # B127: optional duration from user input
            if event.get("duration_minutes") is not None:
                item["duration_minutes"] = int(event["duration_minutes"])
            _recompute_day_status(day)

        elif event_type == "edit_other_activity":
            day = _find_day(updated, event["date"])
            items = ensure_other_activities_list(day)
            item = select_activity(items, event.get("slot"))
            if item is None:
                raise ValueError(f"Date {event['date']} is not an other-activity day")
            if event.get("activity_name") is not None:
                item["name"] = event["activity_name"]
            if event.get("feedback") is not None:
                feedback = event["feedback"]
                item["feedback"] = feedback
                item["load"] = COMPLEMENTARY_LOAD_MAP.get(feedback, COMPLEMENTARY_LOAD_OK)
            if event.get("duration_minutes") is not None:
                item["duration_minutes"] = int(event["duration_minutes"])

        elif event_type == "undo_other_activity":
            day = _find_day(updated, event["date"])
            items = ensure_other_activities_list(day)
            item = select_activity(items, event.get("slot"))
            if item is not None:
                item.pop("status", None)
                item.pop("feedback", None)
                item.pop("load", None)
                item.pop("duration_minutes", None)
            day.pop("status", None)

        elif event_type == "add_other_activity":
            day = _find_day(updated, event["date"])
            items = ensure_other_activities_list(day)
            slot = event.get("slot")
            name = event.get("activity_name")
            # One other-activity per slot: update in place if the slot is taken,
            # otherwise append a new item.
            existing = next((it for it in items if slot and it.get("slot") == slot), None)
            if existing is not None:
                if name:
                    existing["name"] = name
            else:
                new_item: Dict[str, Any] = {}
                if slot:
                    new_item["slot"] = slot
                if name:
                    new_item["name"] = name
                items.append(new_item)
            sort_other_activities(items)
            # A pending activity blocks the day from being "done".
            _recompute_day_status(day)

        elif event_type == "remove_other_activity":
            day = _find_day(updated, event["date"])
            items = ensure_other_activities_list(day)
            slot = event.get("slot")
            if slot:
                day["other_activities"] = [it for it in items if it.get("slot") != slot]
            else:
                # No slot → legacy behaviour: clear the whole day.
                day["other_activities"] = []
            if not day["other_activities"]:
                day.pop("other_activities", None)
            _recompute_day_status(day)

        elif event_type == "add_outdoor":
            day = _find_day(updated, event["date"])
            spot_name = event.get("spot_name")
            if not spot_name:
                raise ValueError("add_outdoor requires 'spot_name'")
            day["outdoor_spot_name"] = spot_name
            day["outdoor_discipline"] = event.get("discipline", "both")
            if event.get("spot_id"):
                day["outdoor_spot_id"] = event["spot_id"]
            day["outdoor_session_status"] = "planned"

        elif event_type == "complete_outdoor":
            day = _find_day(updated, event["date"])
            if not day.get("outdoor_spot_name"):
                raise ValueError(f"Date {event['date']} has no outdoor session to complete")
            day["outdoor_session_status"] = "done"

            # Store outdoor load score on the day and apply ripple if high
            outdoor_load = event.get("outdoor_load_score", 0)
            day["outdoor_load_score"] = outdoor_load
            if outdoor_load >= OUTDOOR_RIPPLE_THRESHOLD:
                target_d = _parse_date(event["date"])
                ripple_key = (target_d + timedelta(days=1)).isoformat()
                try:
                    ripple_day = _find_day(updated, ripple_key)
                except ValueError:
                    ripple_day = None

                if ripple_day and ripple_day.get("sessions"):
                    recovery_meta = _meta_for("regeneration_easy")
                    comp_meta = _meta_for("complementary_conditioning")
                    next_sessions = []
                    for session in ripple_day["sessions"]:
                        # B120: never replace completed/skipped sessions via ripple
                        if session.get("status") in ("done", "skipped"):
                            next_sessions.append(session)
                            continue
                        sid = session.get("session_id", "")
                        smeta = _SESSION_META.get(sid, {})
                        is_hard = smeta.get("hard") or (session.get("tags") or {}).get("hard")
                        is_finger = smeta.get("finger") or (session.get("tags") or {}).get("finger")
                        is_low = (smeta.get("intensity") or session.get("intensity")) == "low"

                        if is_hard or is_finger:
                            next_sessions.append({
                                "session_id": "complementary_conditioning",
                                "slot": session.get("slot", "evening"),
                                "location": session.get("location", "gym"),
                                "status": "planned",
                                "estimated_load_score": _INTENSITY_TO_LOAD.get(comp_meta["intensity"], 40),
                                "gym_id": session.get("gym_id"),
                                "intensity": comp_meta["intensity"],
                                "constraints_applied": ["outdoor_ripple"],
                                "tags": {"hard": False, "finger": False},
                                "explain": [f"hard→medium after outdoor load={outdoor_load}"],
                            })
                        elif not is_low and (smeta.get("intensity") or session.get("intensity")) == "medium":
                            next_sessions.append({
                                "session_id": "deload_recovery",
                                "slot": session.get("slot", "evening"),
                                "location": session.get("location", "gym"),
                                "status": "planned",
                                "estimated_load_score": _INTENSITY_TO_LOAD.get(recovery_meta["intensity"], 20),
                                "gym_id": session.get("gym_id"),
                                "intensity": recovery_meta["intensity"],
                                "constraints_applied": ["outdoor_ripple"],
                                "tags": {"hard": False, "finger": False},
                                "explain": [f"medium→low after outdoor load={outdoor_load}"],
                            })
                        else:
                            next_sessions.append(session)
                    ripple_day["sessions"] = next_sessions

            _recompute_day_status(day)

        elif event_type == "set_outdoor_plan":
            # A265: attach (or clear) the day's pitch ladder. The payload is
            # stored verbatim — it is either the deterministic ladder from
            # outdoor_pitch_ladder or the user's hand-edited version of it, and
            # the engine has no opinion on which.
            day = _find_day(updated, event["date"])
            if not day.get("outdoor_spot_name"):
                raise ValueError(f"Date {event['date']} has no outdoor day to plan")
            if day.get("outdoor_session_status") == "done":
                raise ValueError("Cannot change the plan of a completed outdoor session")
            plan = event.get("plan")
            if plan is None:
                day.pop("outdoor_plan", None)
            else:
                day["outdoor_plan"] = plan

        elif event_type == "undo_outdoor":
            day = _find_day(updated, event["date"])
            day["outdoor_session_status"] = "planned"
            _recompute_day_status(day)

        elif event_type == "remove_outdoor":
            day = _find_day(updated, event["date"])
            if day.get("outdoor_session_status") == "done":
                raise ValueError("Cannot remove a completed outdoor session")
            for k in ("outdoor_spot_name", "outdoor_discipline", "outdoor_spot_id",
                      "outdoor_session_status", "outdoor_plan"):
                day.pop(k, None)

        elif event_type == "change_gym":
            day = _find_day(updated, event["date"])
            new_location = event.get("location", "gym")
            new_gym_id = event.get("gym_id")

            gym_equipment: set = set()
            if new_location == "gym" and gyms and new_gym_id:
                for g in (gyms or []):
                    if g.get("gym_id") == new_gym_id:
                        gym_equipment = set(expand_equipment(g.get("equipment", [])))
                        break
                else:
                    logger.warning(
                        "change_gym: gym_id %r not found in user gyms (%d total) — equipment set is empty, all sessions may downshift",
                        new_gym_id, len(gyms),
                    )

            change_warnings: list = []
            lost_finger = False

            for s in day.get("sessions", []):
                if s.get("status") in ("done", "skipped"):
                    continue

                sid = s.get("session_id", "")
                meta = _meta_for(sid)

                # Check location compatibility
                location_ok = new_location in meta.get("location", ("gym", "home"))

                # Check equipment compatibility (gym and home)
                equipment_ok = True
                if location_ok:
                    req_eq = set(_get_required_equipment(sid))
                    if req_eq:
                        if new_location == "gym":
                            if not req_eq.issubset(gym_equipment):
                                equipment_ok = False
                                missing = req_eq - gym_equipment
                        elif new_location == "home":
                            home_eq = set(expand_equipment(event.get("home_equipment") or []))
                            if home_eq and not req_eq.issubset(home_eq):
                                equipment_ok = False
                                missing = req_eq - home_eq

                if not location_ok or not equipment_ok:
                    # Need replacement
                    replacement = _find_gym_change_replacement(
                        sid, new_location, gym_equipment, meta.get("finger", False),
                    )
                    if meta.get("finger") and not _meta_for(replacement).get("finger"):
                        lost_finger = True
                    rep_meta = _meta_for(replacement)
                    reason = f"incompatible_location={new_location}" if not location_ok else f"missing_equipment={missing}"
                    s["session_id"] = replacement
                    s["location"] = new_location
                    s["gym_id"] = new_gym_id if new_location == "gym" else None
                    s["intensity"] = rep_meta["intensity"]
                    s["estimated_load_score"] = _INTENSITY_TO_LOAD.get(rep_meta["intensity"], 40)
                    s["tags"] = {"hard": rep_meta["hard"], "finger": rep_meta["finger"], **({"test": True} if rep_meta.get("test") else {})}
                    s["explain"] = [f"gym_change: {sid} → {replacement}", reason]
                    s.pop("resolved", None)
                    change_warnings.append(f"{sid} → {replacement} ({reason})")
                else:
                    # Compatible — update gym_id/location, clear resolved to force re-resolution
                    s["location"] = new_location
                    s["gym_id"] = new_gym_id if new_location == "gym" else None
                    s.pop("resolved", None)

            # Finger compensation if we lost a finger session
            if lost_finger:
                snap_phase = (updated.get("profile_snapshot") or {}).get("phase_id", "base")
                _compensate_finger(updated, event["date"], snap_phase, new_location, new_gym_id)

            updated.setdefault("adaptations", []).append({
                "type": "change_gym",
                "date": event["date"],
                "new_location": new_location,
                "new_gym_id": new_gym_id,
                "warnings": change_warnings,
            })

        elif event_type == "set_availability":
            if availability is not None and event.get("availability"):
                av = event["availability"]
                if event.get("date"):
                    date_key = _parse_date(event["date"]).weekday()
                    weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[date_key]
                else:
                    weekday = av.get("weekday")
                    # Convert long-form weekday keys to short-form
                    _WEEKDAY_LONG = {
                        "monday": "mon", "tuesday": "tue", "wednesday": "wed",
                        "thursday": "thu", "friday": "fri", "saturday": "sat",
                        "sunday": "sun",
                    }
                    if weekday and weekday.lower() in _WEEKDAY_LONG:
                        weekday = _WEEKDAY_LONG[weekday.lower()]
                slot = av.get("slot")
                if weekday and slot and weekday in availability and slot in availability[weekday]:
                    for key in ("available", "locations", "preferred_location", "gym_id"):
                        if key in av:
                            availability[weekday][slot][key] = av[key]
                snapshot = updated.get("profile_snapshot") or {}
                phase_id = snapshot.get("phase_id", "base")
                discipline = snapshot.get("discipline")
                if not discipline:
                    logger.warning(
                        "set_availability: profile_snapshot missing 'discipline', defaulting to 'lead'"
                    )
                    discipline = "lead"
                from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _BASE_WEIGHTS_BOULDER, _build_session_pool, _adjust_domain_weights
                _weights_map = _BASE_WEIGHTS_BOULDER if discipline == "boulder" else _BASE_WEIGHTS
                base_weights = _weights_map.get(phase_id, _weights_map["base"])
                domain_weights = snapshot.get("domain_weights", base_weights)
                # B287/R-3: the pool must follow the discipline, exactly like
                # generate_macrocycle does (macrocycle_v1.py). Before this fix the
                # call defaulted to discipline="lead", so a boulder user got
                # boulder domain weights combined with a LEAD session pool.
                # A258: prefer the pool the week was BUILT with. Rebuilding it
                # from (phase_id, discipline) silently drops anything else the
                # pool depends on — it already did, in B287/R-3, and would now
                # make a profile-conditional session vanish from a replanned
                # week. `apply_events` has no user_state in scope, so the
                # snapshot is the only honest source. Fallback keeps weeks
                # planned before A258 working.
                session_pool = snapshot.get("session_pool") or _build_session_pool(
                    phase_id, discipline=discipline
                )
                regenerated = generate_phase_week(
                    phase_id=phase_id,
                    domain_weights=domain_weights,
                    session_pool=session_pool,
                    start_date=updated["start_date"],
                    availability=availability,
                    allowed_locations=snapshot.get("allowed_locations", ["home", "gym"]),
                    hard_cap_per_week=_safe_hard_cap(snapshot),
                    planning_prefs=planning_prefs,
                    default_gym_id=((planning_prefs or {}).get("default_gym_id")),
                    gyms=gyms,
                )
                # B287/R-1: NEVER replace weeks wholesale. Before this fix the
                # regenerated plan overwrote updated["weeks"] with no preserve
                # step, so every done/skipped session in the week was destroyed —
                # a direct violation of the past-session immutability pillar.
                # Route through the same helper every other regeneration path
                # uses, with the standard preserve floor.
                merged = regenerate_preserving_completed(
                    updated, regenerated, preserve_before=_preserve_floor(updated),
                )
                updated["weeks"] = merged["weeks"]
                updated["profile_snapshot"] = regenerated["profile_snapshot"]

        elif event_type == "add_custom_session":
            # A207: add a user-defined custom session to a day. Custom sessions
            # bypass the replanner entirely (no ripple, no spacing checks) and
            # never feed closed-loop / progression. The custom session pool is
            # passed as kwarg from the router (source of truth: user_state).
            cs_id = event.get("custom_session_id")
            target_date = event.get("target_date")
            slot = event.get("slot") or "evening"
            location = event.get("location") or "home"
            gym_id = event.get("gym_id")
            if not cs_id or not target_date:
                logger.warning(
                    "add_custom_session: missing custom_session_id or target_date — skipped"
                )
                continue
            cs = next(
                (s for s in (custom_sessions or []) if s.get("id") == cs_id),
                None,
            )
            if not cs:
                logger.warning(
                    "add_custom_session: custom_session_id %r not found — skipped", cs_id
                )
                continue
            try:
                day = _find_day(updated, target_date)
            except ValueError:
                logger.warning(
                    "add_custom_session: target_date %r not in plan — skipped", target_date
                )
                continue
            # Slot conflict check (consistent with apply_day_add behaviour)
            for existing in day.get("sessions", []):
                if existing.get("slot") == slot:
                    raise ValueError(
                        f"Slot '{slot}' already occupied on {target_date}"
                    )
            if slot in other_activity_slots(day):
                raise ValueError(
                    f"Slot '{slot}' already occupied by other activity on {target_date}"
                )

            new_session = {
                "slot": slot,
                "session_id": f"custom_{cs_id}",
                "custom_session_id": cs_id,
                "session_mode": "custom_build",
                "is_custom": True,
                "name": cs.get("name", "Custom session"),
                "location": location,
                "gym_id": gym_id if location == "gym" else None,
                "status": "planned",
                "intensity": "medium",
                "estimated_load_score": cs.get("estimated_load_score", 0),
                "target_duration_min": cs.get("estimated_duration_minutes", 0),
                "exercises": cs.get("exercises", []),
                "tags": {"hard": False, "finger": False},
                "constraints_applied": ["custom_add"],
                "explain": ["user-added custom session", f"custom_session_id={cs_id}"],
            }
            day.setdefault("sessions", []).append(new_session)
            day["sessions"].sort(
                key=lambda s: (
                    SLOTS.index(s.get("slot") if s.get("slot") in SLOTS else "evening"),
                    s.get("priority", 99),
                    s.get("session_id", ""),
                )
            )

        elif event_type == "add_generated_session":
            # A213: add a session generated inline (body-part picker, etc.).
            # Unlike add_custom_session, the payload IS the session — no
            # custom_sessions[] lookup. Sessions added this way still carry
            # session_mode="custom_build" + is_custom=True so the frontend
            # renders them via the existing custom-session UI, and the
            # closed-loop skips progression_v1.
            session_payload = event.get("session_payload") or {}
            target_date = event.get("target_date")
            slot = event.get("slot") or "evening"
            if not session_payload or not target_date:
                logger.warning(
                    "add_generated_session: missing session_payload or target_date — skipped"
                )
                continue
            try:
                day = _find_day(updated, target_date)
            except ValueError:
                logger.warning(
                    "add_generated_session: target_date %r not in plan — skipped",
                    target_date,
                )
                continue
            # B218 Bug 1: generated sessions (body-part picker etc.) stack on
            # top of any existing planned session, same as quick-add. We only
            # reject when the day is marked as a rest/other-activity slot.
            if slot in other_activity_slots(day):
                raise ValueError(
                    f"Slot '{slot}' already occupied by other activity on {target_date}"
                )

            # Stable, unique session_id for downstream feedback linking
            build_kind = session_payload.get("build_kind") or "generated"
            session_id = session_payload.get("session_id") or (
                f"generated_{build_kind}_{target_date}_{slot}"
            )

            new_session = {
                **session_payload,
                "session_id": session_id,
                "slot": slot,
                "session_mode": session_payload.get("session_mode", "custom_build"),
                "is_custom": True,
                "status": "planned",
                "location": event.get("location") or session_payload.get("location") or "home",
                "gym_id": event.get("gym_id") if (event.get("location") == "gym") else session_payload.get("gym_id"),
                "constraints_applied": ["generated_add"],
                "explain": [
                    f"user-added generated session ({build_kind})",
                    f"body_parts={session_payload.get('body_parts_selected')}",
                ],
                "target_duration_min": session_payload.get("estimated_duration_minutes", 0),
            }
            day.setdefault("sessions", []).append(new_session)
            day["sessions"].sort(
                key=lambda s: (
                    SLOTS.index(s.get("slot") if s.get("slot") in SLOTS else "evening"),
                    s.get("priority", 99),
                    s.get("session_id", ""),
                )
            )

        else:
            if event_type is not None:
                logger.warning("apply_events: unknown event_type %r — event ignored", event_type)

        updated["adaptations"].append({"type": "event", "event": event})

    _reconcile(updated)
    updated["plan_revision"] = int(updated.get("plan_revision") or 1) + 1
    return updated


def _compensate_finger(
    plan: Dict[str, Any],
    excluded_date: str,
    phase_id: str,
    location: str,
    gym_id: Optional[str],
) -> None:
    """Try to place a finger_maintenance session on a suitable day after losing one to override.

    Looks for future days (excluded_date+2 onwards) that have no finger session,
    have >= 48h gap from the nearest existing finger day, and have a replaceable
    complementary/recovery session. Mutates *plan* in place.
    """
    days = plan["weeks"][0]["days"]
    excluded_d = _parse_date(excluded_date)

    # Collect existing finger dates (after override has been applied)
    finger_dates: set = set()
    for day in days:
        if any((s.get("tags") or {}).get("finger") for s in day.get("sessions", [])):
            finger_dates.add(_parse_date(day["date"]))

    # Search from excluded_date onwards, respecting recovery gap (B165b)
    comp_session_id = "finger_maintenance_home"
    comp_meta = _meta_for(comp_session_id)
    gap = _recovery_gap(plan)

    for day in days:
        day_d = _parse_date(day["date"])
        if (day_d - excluded_d).days < gap + 1:
            continue

        # Check gap from ALL existing finger days (B165b: recovery_multiplier aware)
        too_close = False
        for fd in finger_dates:
            if abs((day_d - fd).days) <= gap:
                too_close = True
                break
        if too_close:
            continue

        # Already has finger — skip
        if any((s.get("tags") or {}).get("finger") for s in day.get("sessions", [])):
            continue

        # Find a replaceable session (complementary/recovery, non-hard, non-done)
        replaceable_idx = None
        for idx, s in enumerate(day.get("sessions", [])):
            if s.get("status") in ("done", "skipped"):
                continue
            if (s.get("tags") or {}).get("hard"):
                continue
            sid = s.get("session_id", "")
            if sid in ("complementary_conditioning", "regeneration_easy", "yoga_recovery",
                       "flexibility_full", "prehab_maintenance"):
                replaceable_idx = idx
                break

        if replaceable_idx is None:
            continue

        # Replace with finger_maintenance_home
        old = day["sessions"][replaceable_idx]
        day["sessions"][replaceable_idx] = {
            "slot": old.get("slot", "evening"),
            "session_id": comp_session_id,
            "location": "home",
            "gym_id": None,
            "phase_id": phase_id,
            "intensity": comp_meta["intensity"],
            "constraints_applied": ["finger_compensation"],
            "tags": {"hard": comp_meta["hard"], "finger": comp_meta["finger"], **({"test": True} if comp_meta.get("test") else {})},
            "explain": ["finger compensation after override", f"lost_date={excluded_date}"],
        }

        plan.setdefault("adaptations", []).append({
            "type": "finger_compensation",
            "compensated_date": day["date"],
            "lost_date": excluded_date,
        })
        return  # compensated — done

    # No suitable day found — emit warning
    plan.setdefault("adaptations", []).append({
        "type": "finger_compensation_warning",
        "lost_date": excluded_date,
        "message": "Could not find a suitable day to compensate lost finger session",
    })


def _resolve_intent_for_equipment(
    intent: str,
    gym_equipment: Optional[set],
) -> str:
    """B96: Resolve intent → session_id, respecting gym equipment constraints.

    If the primary session for the intent requires equipment the gym doesn't have,
    fall back to an alternative session for the same intent family.
    """
    session_id = INTENT_TO_SESSION.get(intent)
    if session_id is None:
        raise ValueError(f"Unsupported override intent: {intent}")
    if gym_equipment is None:
        return session_id

    # Check equipment compatibility
    req = _get_required_equipment(session_id)
    if not req or all(eq in gym_equipment for eq in req):
        return session_id

    # Intent-family fallbacks: try alternatives that serve the same training goal
    _INTENT_FALLBACKS: Dict[str, List[str]] = {
        "strength": ["strength_long", "finger_strength_home", "pulling_strength_gym"],
        "power": ["power_contact_gym", "boulder_circuit_gym"],
        "power_endurance": ["power_endurance_gym", "boulder_circuit_gym", "route_endurance_gym"],
        "endurance": ["endurance_aerobic_gym", "route_endurance_gym", "finger_aerobic_base"],
        "aerobic_endurance": ["endurance_aerobic_gym", "route_endurance_gym", "finger_aerobic_base"],
        "projecting": ["power_contact_gym", "boulder_circuit_gym"],
        # B262: degrade to a hard NON-climbing session (pulling strength) when no
        # wall/board/hangboard is available. Dropped boulder_circuit_gym — it is
        # hard=False (a medium session) and unreachable here (needs gym_boulder,
        # same as power_contact_gym which precedes it).
        "hard": ["strength_long", "power_contact_gym", "pulling_strength_gym"],
        "technique": ["technique_focus_gym", "easy_climbing_deload"],
    }

    fallbacks = _INTENT_FALLBACKS.get(intent, [])
    for fb_sid in fallbacks:
        if fb_sid == session_id:
            continue
        fb_meta = _SESSION_META.get(fb_sid)
        if fb_meta is None:
            continue
        fb_req = _get_required_equipment(fb_sid)
        if not fb_req or all(eq in gym_equipment for eq in fb_req):
            return fb_sid

    # No compatible fallback found — use original (will work with whatever equipment is there)
    logger.warning(
        "_resolve_intent_for_equipment: no equipment-compatible fallback for %r — returning original session unchanged",
        session_id,
    )
    return session_id


def apply_day_override(
    plan: Dict[str, Any],
    *,
    intent: str,
    location: str,
    reference_date: str,
    slot: str = "evening",
    phase_id: Optional[str] = None,
    target_date: Optional[str] = None,
    gym_id: Optional[str] = None,
    gyms: Optional[List[Dict[str, Any]]] = None,
    session_index: Optional[int] = None,
) -> Dict[str, Any]:
    updated = deepcopy(plan)

    # Resolve target day: explicit target_date or reference_date + 1
    if target_date:
        target = _parse_date(target_date)
    else:
        target = _parse_date(reference_date) + timedelta(days=1)
    target_key = target.isoformat()

    effective_phase = phase_id or (updated.get("profile_snapshot") or {}).get("phase_id", "base")

    # B97: outdoor override — mark day as outdoor, clear indoor sessions
    outdoor_discipline = OUTDOOR_INTENT_TO_DISCIPLINE.get(intent)
    if location == "outdoor" or outdoor_discipline is not None:
        if outdoor_discipline is None:
            outdoor_discipline = "both"
        target_day = _find_day(updated, target_key)
        # B120: refuse to clear completed/skipped sessions (immutability pillar)
        completed_in_target = [
            s for s in target_day.get("sessions", [])
            if s.get("status") in ("done", "skipped")
        ]
        if completed_in_target:
            raise ValueError(
                f"Cannot override day {target_key} with outdoor: "
                f"{len(completed_in_target)} session(s) already completed/skipped"
            )
        target_day["sessions"] = []
        target_day["outdoor_spot_name"] = intent.replace("outdoor_", "").replace("_", " ")
        target_day["outdoor_discipline"] = outdoor_discipline
        target_day["outdoor_session_status"] = "planned"
        target_day.pop("status", None)

        updated.setdefault("adaptations", []).append({
            "type": "day_override",
            "reference_date": reference_date,
            "target_date": target_key,
            "outdoor": True,
            "discipline": outdoor_discipline,
        })
        return updated

    # B96: resolve intent respecting gym equipment
    gym_equipment: Optional[set] = None
    if location == "gym" and gyms and gym_id:
        for g in gyms:
            if g.get("gym_id") == gym_id:
                gym_equipment = set(expand_equipment(g.get("equipment", [])))
                break
        else:
            logger.warning(
                "apply_day_override: gym_id %r not found in user gyms (%d total) — equipment check skipped",
                gym_id, len(gyms),
            )
    elif location == "gym" and gyms:
        # No specific gym_id — use first gym by priority
        sorted_g = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))
        if sorted_g:
            gym_equipment = set(expand_equipment(sorted_g[0].get("equipment", [])))

    session_id = _resolve_intent_for_equipment(intent, gym_equipment)
    meta = _meta_for(session_id)

    # B262: surface equipment-driven changes so the UI can tell the user why the
    # session differs. Only meaningful when we actually know the gym equipment
    # (gym_equipment is None for home/no-gym overrides → no equipment gating).
    equipment_notice = None
    if gym_equipment is not None:
        primary_sid = INTENT_TO_SESSION.get(intent)
        if session_id != primary_sid:
            # Intent fell back to an equipment-compatible alternative.
            equipment_notice = {
                "type": "equipment_downgrade",
                "intent": intent,
                "requested_session": primary_sid,
                "resolved_session": session_id,
                "reason": "no_climbing_equipment",
            }
        elif set(_get_required_equipment(session_id)) - set(gym_equipment):
            # Terminal case: no compatible fallback existed, so the primary was
            # kept even though its equipment is unavailable here.
            equipment_notice = {
                "type": "no_compatible_hard_session",
                "intent": intent,
                "session": session_id,
            }

    # NEW-F6: detect phase mismatch
    current_phase = (updated.get("profile_snapshot") or {}).get("phase_id", "base")
    phase_mismatch_warning = None
    if effective_phase != current_phase:
        phase_mismatch_warning = {
            "type": "phase_mismatch_warning",
            "requested_phase": effective_phase,
            "current_phase": current_phase,
            "message": f"Override session uses phase '{effective_phase}' but current plan phase is '{current_phase}'",
        }

    target_day = _find_day(updated, target_key)
    effective_gym_id = gym_id or (_default_gym_id_from_plan(updated) if location == "gym" else None)

    # NEW-F7: save original sessions before overwriting
    original_sessions = list(target_day.get("sessions") or [])

    # B120: refuse to overwrite completed/skipped sessions (immutability pillar)
    completed_in_target = [
        s for s in original_sessions
        if s.get("status") in ("done", "skipped")
    ]
    if session_index is not None:
        # Replacing a specific session — block only if THAT session is done/skipped
        if 0 <= session_index < len(original_sessions):
            s = original_sessions[session_index]
            if s.get("status") in ("done", "skipped"):
                raise ValueError(
                    f"Cannot override session at index {session_index}: "
                    f"status is '{s['status']}'"
                )
    elif completed_in_target:
        raise ValueError(
            f"Cannot override day {target_key}: "
            f"{len(completed_in_target)} session(s) already completed/skipped"
        )

    new_session = {
        "slot": slot,
        "session_id": session_id,
        "location": location,
        "gym_id": effective_gym_id,
        "phase_id": effective_phase,
        "intensity": meta["intensity"],
        "constraints_applied": ["manual_override"],
        "tags": {"hard": meta["hard"], "finger": meta["finger"], **({"test": True} if meta.get("test") else {})},
        "explain": ["user day override applied", f"override_intent={intent}"],
    }

    # B48: if session_index is provided, replace only that session
    if session_index is not None and len(original_sessions) > 1:
        if session_index < 0 or session_index >= len(original_sessions):
            raise ValueError(
                f"session_index {session_index} out of range "
                f"(day has {len(original_sessions)} sessions)"
            )
        target_day["sessions"] = list(original_sessions)
        target_day["sessions"][session_index] = new_session
    else:
        target_day["sessions"] = [new_session]

    if meta["hard"] or meta["finger"]:
        recovery_meta = _meta_for("regeneration_easy")
        comp_meta = _meta_for("complementary_conditioning")
        for delta in (1, 2):
            ripple_key = (target + timedelta(days=delta)).isoformat()
            try:
                ripple_day = _find_day(updated, ripple_key)
            except ValueError:
                logger.debug("Ripple target day %s not found in plan — skipping", ripple_key)
                continue
            if not ripple_day.get("sessions"):
                continue
            next_sessions = []
            for session in ripple_day.get("sessions", []):
                # B120: never replace completed/skipped sessions via ripple
                if session.get("status") in ("done", "skipped"):
                    next_sessions.append(session)
                    continue
                is_hard = session.get("tags", {}).get("hard")
                is_low = session.get("intensity") == "low"

                if delta == 1:
                    # Proportional: hard→medium, medium→low, low→keep
                    if is_hard:
                        next_sessions.append(
                            {
                                "slot": session.get("slot", "evening"),
                                "session_id": "complementary_conditioning",
                                "location": session.get("location", location),
                                "gym_id": session.get("gym_id", effective_gym_id),
                                "phase_id": effective_phase,
                                "intensity": comp_meta["intensity"],
                                "constraints_applied": ["recovery_ripple_proportional"],
                                "tags": {"hard": False, "finger": False},
                                "explain": ["hard→medium after hard override", f"source_day={target_key}"],
                            }
                        )
                    elif not is_low:
                        next_sessions.append(
                            {
                                "slot": session.get("slot", "evening"),
                                "session_id": "regeneration_easy",
                                "location": session.get("location", location),
                                "gym_id": session.get("gym_id", effective_gym_id),
                                "phase_id": effective_phase,
                                "intensity": recovery_meta["intensity"],
                                "constraints_applied": ["recovery_ripple_proportional"],
                                "tags": {"hard": False, "finger": False},
                                "explain": ["medium→low after hard override", f"source_day={target_key}"],
                            }
                        )
                    else:
                        next_sessions.append(session)
                else:
                    # Day+2: force recovery for anything non-low
                    if is_hard or not is_low:
                        next_sessions.append(
                            {
                                "slot": session.get("slot", "evening"),
                                "session_id": "regeneration_easy",
                                "location": session.get("location", location),
                                "gym_id": session.get("gym_id", effective_gym_id),
                                "phase_id": effective_phase,
                                "intensity": recovery_meta["intensity"],
                                "constraints_applied": ["recovery_ripple"],
                                "tags": {"hard": False, "finger": False},
                                "explain": ["forced recovery after hard override", f"source_day={target_key}"],
                            }
                        )
                    else:
                        next_sessions.append(session)
            ripple_day["sessions"] = next_sessions

    # NEW-F7: finger compensation — if override removed a finger session, try to place it elsewhere
    if session_index is not None and len(original_sessions) > 1:
        # B48: only check the replaced session, not all originals
        replaced = original_sessions[session_index]
        original_had_finger = (replaced.get("tags") or {}).get("finger", False)
    else:
        original_had_finger = any(
            (s.get("tags") or {}).get("finger") for s in original_sessions
        )
    new_has_finger = meta["finger"]
    if original_had_finger and not new_has_finger:
        _compensate_finger(updated, target_key, effective_phase, location, effective_gym_id)

    _reconcile(updated)

    updated.setdefault("adaptations", []).append(
        {
            "type": "day_override",
            "reference_date": reference_date,
            "target_date": target_key,
            "ripple_days": [
                (target + timedelta(days=1)).isoformat(),
                (target + timedelta(days=2)).isoformat(),
            ],
        }
    )

    # NEW-F6: append phase mismatch warning if detected
    if phase_mismatch_warning:
        updated["adaptations"].append(phase_mismatch_warning)

    # B262: append equipment downgrade / no-compatible-session notice
    if equipment_notice:
        updated["adaptations"].append(equipment_notice)

    return updated
