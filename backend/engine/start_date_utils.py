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
from typing import Optional


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
