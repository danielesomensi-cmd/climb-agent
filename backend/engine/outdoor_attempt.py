"""A324: one reading of an outdoor attempt — who was on the sharp end, and how.

Pure module, no I/O, no engine imports. Every backend reader of an outdoor
attempt's outcome goes through it (outdoor_log, grade_evidence, milestones_v1,
athlete_context, report_engine, coach/prompt_builder); the frontend twin is
``frontend/src/lib/outdoor-result.ts``. A static scan
(``test_a324_rope_role_aid.py``) forbids ``result == "sent"`` comparisons
anywhere else in the backend, so a new reader cannot silently count a clean
second as a send.

An attempt (``routes[].attempts[]`` of an outdoor log) carries:

- ``result``: ``sent`` | ``fell`` | ``topped_out`` | ``aid``.
  ``topped_out`` (B393) = reached the top with rests on the rope (hangdog);
  ``aid`` (A324) = reached the top pulling on the gear (A0). Neither is a free
  ascent. ``aid`` exists only on a rope: a boulder has no gear to pull on.
- ``rope_role`` (optional): ``lead`` | ``second`` | ``toprope``. Absent means
  ``lead`` — every log written before A324 is a lead log and stays byte-identical
  (no migration). The backend stores ``lead`` as absent (see
  :func:`normalize_route_attempts`). A boulder has no rope role.

The single rule every reader applies:

- a **send** is ``sent`` on lead (:func:`is_lead_send`). Only a send counts as a
  send in the stats, the report, the milestones, the onsight evidence (A292) and
  the try-hard count;
- a **clean ascent not on lead** is ``sent`` on second or top-rope
  (:func:`is_clean_non_lead`): shown as «Second clean» / «TR clean», never as a
  send, never a milestone, never grade evidence.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

#: Attempt results (``attempts[].result``).
RESULT_SENT = "sent"
RESULT_FELL = "fell"
RESULT_TOPPED_OUT = "topped_out"
RESULT_AID = "aid"
RESULTS = (RESULT_SENT, RESULT_FELL, RESULT_TOPPED_OUT, RESULT_AID)

#: Rope roles (``attempts[].rope_role``). Absent = ``lead``.
ROPE_LEAD = "lead"
ROPE_SECOND = "second"
ROPE_TOPROPE = "toprope"
ROPE_ROLES = (ROPE_LEAD, ROPE_SECOND, ROPE_TOPROPE)
DEFAULT_ROPE_ROLE = ROPE_LEAD


def result_of(attempt: Any) -> Optional[str]:
    """The attempt's ``result`` string, or None (not a dict / no result)."""
    if not isinstance(attempt, Mapping):
        return None
    res = attempt.get("result")
    return str(res) if res else None


def rope_role(attempt: Any) -> str:
    """The attempt's rope role. Absent or unknown → ``lead`` (pre-A324 logs)."""
    if not isinstance(attempt, Mapping):
        return DEFAULT_ROPE_ROLE
    role = attempt.get("rope_role")
    return role if role in ROPE_ROLES else DEFAULT_ROPE_ROLE


def is_lead(attempt: Any) -> bool:
    return rope_role(attempt) == ROPE_LEAD


def is_lead_send(attempt: Any) -> bool:
    """A send: ``sent`` on lead. The only result that counts as a send."""
    return result_of(attempt) == RESULT_SENT and is_lead(attempt)


def is_clean_non_lead(attempt: Any) -> bool:
    """``sent`` on second or top-rope: clean, but not a send."""
    return result_of(attempt) == RESULT_SENT and not is_lead(attempt)


def is_aid(attempt: Any) -> bool:
    """A0: reached the top pulling on the gear (any rope role)."""
    return result_of(attempt) == RESULT_AID


def _attempts(route: Any) -> List[Any]:
    if not isinstance(route, Mapping):
        return []
    return list(route.get("attempts") or [])


def route_lead_sent(route: Any) -> bool:
    """The route has at least one send (``sent`` on lead)."""
    return any(is_lead_send(a) for a in _attempts(route))


def route_clean_non_lead(route: Any) -> bool:
    """No send, but at least one clean ascent on second / top-rope.

    Exclusive with :func:`route_lead_sent`, so counts never overlap.
    """
    attempts = _attempts(route)
    return not any(is_lead_send(a) for a in attempts) and any(is_clean_non_lead(a) for a in attempts)


def route_aid(route: Any) -> bool:
    """No send and no clean ascent, but at least one A0 attempt.

    Exclusive with :func:`route_lead_sent` and :func:`route_clean_non_lead`.
    """
    attempts = _attempts(route)
    if any(result_of(a) == RESULT_SENT for a in attempts):
        return False
    return any(is_aid(a) for a in attempts)


def is_boulder_route(route: Mapping[str, Any], session_discipline: Any) -> bool:
    """A boulder problem: its own discipline, else the session's when the route
    carries none. A ``both`` session with an untagged route is not guessed."""
    disc = route.get("discipline")
    if disc:
        return disc == "boulder"
    return session_discipline == "boulder"


def normalize_route_attempts(route: Any, session_discipline: Any) -> List[str]:
    """Canonical attempts of one route, in place. Returns what was changed.

    - an explicit ``rope_role: "lead"`` is dropped: absent already means lead,
      so a lead log written by any client stays byte-identical to a pre-A324 one;
    - on a boulder problem every ``rope_role`` is dropped and ``aid`` becomes
      ``fell`` (no rope, no gear to pull on: the problem was not topped free).

    Normalised, not rejected: a 422 would make the offline outbox discard the
    whole day (``outbox.ts`` drops 4xx) and fail the live session's finish.
    Unknown spellings are not touched here — the request models and
    ``validate_outdoor_entry`` reject them.
    """
    changes: List[str] = []
    if not isinstance(route, dict):
        return changes
    boulder = is_boulder_route(route, session_discipline)
    name = route.get("name") or "?"
    for i, attempt in enumerate(route.get("attempts") or []):
        if not isinstance(attempt, dict):
            continue
        if "rope_role" in attempt:
            role = attempt.get("rope_role")
            if role is None or role == ROPE_LEAD:
                del attempt["rope_role"]
            elif boulder and role in ROPE_ROLES:
                del attempt["rope_role"]
                changes.append(f"{name}[{i}]: rope_role {role!r} dropped (boulder)")
        if boulder and attempt.get("result") == RESULT_AID:
            attempt["result"] = RESULT_FELL
            changes.append(f"{name}[{i}]: aid → fell (boulder)")
    return changes


def normalize_entry_attempts(entry: Any) -> List[str]:
    """:func:`normalize_route_attempts` over every route of an outdoor entry."""
    changes: List[str] = []
    if not isinstance(entry, dict):
        return changes
    for route in entry.get("routes") or []:
        changes.extend(normalize_route_attempts(route, entry.get("discipline")))
    return changes

