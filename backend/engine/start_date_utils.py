"""Start-date helpers for macrocycle generation.

Introduced by A-ACTIVATION-TIMING Day 1 (simulation-only scope).
Engine-layer equivalents of the same helpers in backend.api.deps, so that
scripts and (eventually) the onboarding router can import Monday-math
without going through the API layer.

Not yet wired into production callers — Day 2 will promote `this_monday()`
to be the default onboarding start_date.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional


def this_monday(from_date: Optional[date] = None) -> str:
    """Return the Monday of the current week as 'YYYY-MM-DD'.

    Goes BACKWARDS to find the Monday, so a macrocycle can start immediately
    with a partial first week (some past days skipped via planner's B95 guard).
    If from_date is already a Monday, returns from_date.
    """
    d = from_date or date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def next_monday(from_date: Optional[date] = None) -> str:
    """Return the next Monday as 'YYYY-MM-DD'.

    If from_date is already a Monday, returns from_date (same-day semantics
    matching backend.api.deps.next_monday). Use `strict_next_monday` when
    you need to force +7 for Mondays.
    """
    d = from_date or date.today()
    days_ahead = (7 - d.weekday()) % 7
    if days_ahead == 0:
        return d.isoformat()
    return (d + timedelta(days=days_ahead)).isoformat()


def strict_next_monday(from_date: Optional[date] = None) -> str:
    """Return the next Monday strictly after from_date (never same-day).

    Used when the user explicitly chooses "start next Monday" — if they
    onboard on a Monday, they want Week 1 to start the FOLLOWING Monday,
    not today.
    """
    d = from_date or date.today()
    days_ahead = (7 - d.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (d + timedelta(days=days_ahead)).isoformat()


def is_week_one_empty(
    state: Dict[str, Any],
    macrocycle: Dict[str, Any],
    today: date,
) -> bool:
    """Probe Week 1 via the real planner and return True iff it would have
    zero sessions placed.

    Used by the onboarding router to decide whether `this_monday()` produces
    a useful first week for this user, or whether to fall back to strict
    next Monday. Threshold T=1 was chosen empirically from stress simulation
    (see _archive/docs/briefs/A-ACTIVATION-timing_simulation.md §stress).

    Deterministic: same inputs → same output. No mutation of `state`.
    """
    # Local import to avoid a top-level cycle: planner_v2 imports from
    # macrocycle_v1, which is fine, but start_date_utils should not appear
    # as a transitive import at module-load time for the engine.
    from backend.engine.planner_v2 import generate_phase_week

    phases = (macrocycle or {}).get("phases") or []
    if not phases:
        return True  # no phases = degenerate, treat as empty
    phase1 = phases[0]

    equipment = state.get("equipment") or {}
    gyms = equipment.get("gyms") or []
    default_gym_id = gyms[0].get("gym_id") if gyms else None
    home_equipment = equipment.get("home") or []
    prefs = state.get("planning_prefs") or {}

    probe = generate_phase_week(
        phase_id=phase1["phase_id"],
        domain_weights=phase1.get("domain_weights") or {},
        session_pool=phase1.get("session_pool") or [],
        start_date=phase1.get("start_date") or macrocycle["start_date"],
        availability=state.get("availability"),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=prefs.get("hard_day_cap_per_week", 3),
        planning_prefs=prefs,
        default_gym_id=default_gym_id,
        gyms=gyms,
        intensity_cap=phase1.get("intensity_cap"),
        home_equipment=home_equipment,
        today=today.isoformat(),
        inject_tests=False,
        finger_device=(state.get("preferences") or {}).get("finger_training_device"),
        user_age=(state.get("body") or {}).get("age"),
    )
    days = (probe.get("weeks") or [{}])[0].get("days", [])
    total = sum(len(d.get("sessions") or []) for d in days)
    return total == 0


def resolve_start_date(
    onboarding_date: date,
    user_choice: str,
) -> str:
    """Resolve macrocycle start_date from onboarding date + user choice.

    Choices (Phase 0 / A-ACTIVATION-TIMING):
    - "today": start the week containing today → this_monday()
    - "tomorrow": start the week containing tomorrow → this_monday(today+1)
      (normally same Monday as "today", except when onboarding on Sunday)
    - "next_monday": skip the current partial week → strict_next_monday()

    Returns an ISO Monday string. Callers must still pass this through
    ensure_monday() as the final gatekeeper (defense in depth).
    """
    if user_choice == "today":
        return this_monday(onboarding_date)
    if user_choice == "tomorrow":
        return this_monday(onboarding_date + timedelta(days=1))
    if user_choice == "next_monday":
        return strict_next_monday(onboarding_date)
    raise ValueError(
        f"resolve_start_date: unknown user_choice {user_choice!r} "
        "— expected 'today', 'tomorrow', or 'next_monday'"
    )
