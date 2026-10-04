"""A292 (R6b): lead onsight evidence from the outdoor log.

Pure functions, no I/O. The declared ``assessment.grades.lead_max_os`` is a
number typed at onboarding; the outdoor log often says more. This module reads
the log and, when it shows a harder onsight than the declared one, PROPOSES the
new grade. It never writes anything: the athlete confirms route by route
(``POST /api/assessment/confirm-grade``), and only that endpoint changes the
grade.

What counts as one piece of evidence (``is_onsight_evidence``):

- a lead route (the route's own ``discipline``, else the session's);
- its FIRST appearance in the log (spot name + route name, case- and
  whitespace-insensitive — the identity B362 already uses for route names);
- exactly one attempt, and that attempt is ``sent``;
- a style that does not exclude a first go: absent, ``onsight`` or ``flash``.
  ``redpoint``, ``repeat``, ``project`` and a ``topped_out`` result are out;
- a grade on the French ladder (``assessment_v1.GRADE_ORDER``).

A route with no style is only *inferred* evidence: a single sent attempt at a
first appearance is usually an onsight, but a route worked on a day that was
never logged looks exactly the same. That is why the card asks the athlete about
every route, and why a route marked "worked" leaves the count for good
(``assessment.grade_evidence_worked_routes``).

The proposal (``propose_grade``): the hardest grade G with at least
``MIN_ROUTES`` evidence routes at G or above, spread over at least two distinct
days or two distinct spots. Proposed only when G is above the current onsight,
above a grade the athlete already declined, and never above the redpoint.

ENGINEERING CONSTANTS (no published source): ``MIN_ROUTES`` = 2 and the
"two days or two spots" spread. They exist so one lucky route, or one day on
one wall, cannot rewrite the grade.

Trips: R6b proposed "at least one route outside a trip". It is reported as a
caveat (``all_in_trip``), not enforced: Daniele confirmed his three Kalymnos 7b
onsights (DECISIONS 2026-10-04) and the per-route confirmation is the stronger
check. A rule that makes a confirmed fact unconfirmable is the wrong rule.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from backend.engine.assessment_v1 import GRADE_ORDER

_GRADE_INDEX = {g: i for i, g in enumerate(GRADE_ORDER)}

MIN_ROUTES = 2  # ENGINEERING CONSTANT, see module docstring.
FIELD_LEAD_OS = "lead_max_os"
SUPPORTED_FIELDS = (FIELD_LEAD_OS,)

# Styles that still allow a first-go send. Anything else (redpoint, repeat,
# project) says the athlete had been on the route before.
_FIRST_GO_STYLES = {None, "", "onsight", "flash"}
# Answers the card accepts per route.
CONFIRM_STYLES = {"onsight", "flash", "worked"}


def _norm(text: Any) -> str:
    return " ".join(str(text or "").split()).casefold()


def normalize_lead_grade(grade: Any) -> Optional[str]:
    """Canonical lowercase French grade (``7b+``) or None when off the ladder."""
    cleaned = str(grade or "").strip().lower().replace(" ", "")
    return cleaned if cleaned in _GRADE_INDEX else None


def grade_rank(grade: Any) -> int:
    """Index on the French ladder; -1 for anything that is not on it."""
    norm = normalize_lead_grade(grade)
    return _GRADE_INDEX[norm] if norm is not None else -1


def route_key(entry: Dict[str, Any], route: Dict[str, Any]) -> str:
    """Identity of a route across sessions: ``spot|route`` (B362 normalisation).

    The spot NAME, not ``spot_id``: older logs have no id, and the same crag
    logged with and without one must stay one crag.
    """
    return f"{_norm(entry.get('spot_name'))}|{_norm(route.get('name'))}"


def is_first_go_send(route: Dict[str, Any], key: str, seen: Set[str]) -> bool:
    """Shared predicate (outdoor stats + evidence): a single sent attempt on a
    route never logged before, with a style that allows a first go."""
    if key in seen:
        return False
    attempts = route.get("attempts") or []
    if len(attempts) != 1 or not isinstance(attempts[0], dict):
        return False
    if attempts[0].get("result") != "sent":
        return False
    return route.get("style") in _FIRST_GO_STYLES


def _is_lead(entry: Dict[str, Any], route: Dict[str, Any]) -> bool:
    discipline = route.get("discipline") or entry.get("discipline")
    return discipline == "lead"


def is_onsight_evidence(entry: Dict[str, Any], route: Dict[str, Any], seen: Set[str]) -> bool:
    """A first-go send of a lead route on the French ladder."""
    if not _is_lead(entry, route):
        return False
    if normalize_lead_grade(route.get("grade")) is None:
        return False
    return is_first_go_send(route, route_key(entry, route), seen)


def chronological(sessions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sessions sorted by date (stable: same-day sessions keep their order)."""
    return sorted(
        (s for s in sessions if isinstance(s, dict)),
        key=lambda s: str(s.get("date") or ""),
    )


def _in_trip(date: str, trips: Iterable[Dict[str, Any]]) -> bool:
    for trip in trips or []:
        if not isinstance(trip, dict):
            continue
        start, end = str(trip.get("start_date") or ""), str(trip.get("end_date") or "")
        if start and end and start <= date <= end:
            return True
    return False


def collect_onsight_evidence(
    sessions: Iterable[Dict[str, Any]],
    *,
    worked_keys: Iterable[str] = (),
    trips: Iterable[Dict[str, Any]] = (),
) -> List[Dict[str, Any]]:
    """Every evidence route in the log, oldest first.

    ``worked_keys`` are routes the athlete already marked as worked: they never
    count again (the log itself is not rewritten).
    """
    excluded = set(worked_keys or ())
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for entry in chronological(sessions):
        date = str(entry.get("date") or "")
        for route in entry.get("routes") or []:
            if not isinstance(route, dict):
                continue
            key = route_key(entry, route)
            evidence = is_onsight_evidence(entry, route, seen)
            seen.add(key)
            if not evidence or key in excluded:
                continue
            style = route.get("style") or None
            out.append({
                "key": key,
                "date": date,
                "spot_name": entry.get("spot_name"),
                "name": route.get("name"),
                "grade": normalize_lead_grade(route.get("grade")),
                "style": style,
                # Declared by the athlete in the log, or inferred from one sent go.
                "explicit": style in {"onsight", "flash"},
                "in_trip": _in_trip(date, trips),
            })
    return out


def _spread_ok(routes: List[Dict[str, Any]]) -> bool:
    days = {r["date"] for r in routes}
    spots = {_norm(r.get("spot_name")) for r in routes}
    return len(days) >= 2 or len(spots) >= 2


def supported_grade(routes: List[Dict[str, Any]]) -> Optional[str]:
    """Hardest grade with ≥ MIN_ROUTES routes at or above it, spread over two
    days or two spots. None when the routes do not support any grade."""
    for grade in sorted({r["grade"] for r in routes}, key=grade_rank, reverse=True):
        support = [r for r in routes if grade_rank(r["grade"]) >= grade_rank(grade)]
        if len(support) >= MIN_ROUTES and _spread_ok(support):
            return grade
    return None


def propose_grade(
    evidence: List[Dict[str, Any]],
    *,
    current: Any,
    redpoint: Any = None,
    dismissed: Any = None,
) -> Optional[str]:
    """The grade to propose, or None. Never downward, never above the redpoint,
    never a grade already declined (a declined 7b does not block 7b+)."""
    grade = supported_grade(evidence)
    if grade is None:
        return None
    rp_rank = grade_rank(redpoint)
    if rp_rank >= 0 and grade_rank(grade) > rp_rank:
        grade = GRADE_ORDER[rp_rank]
    if grade_rank(grade) <= grade_rank(current):
        return None
    if grade_rank(dismissed) >= 0 and grade_rank(grade) <= grade_rank(dismissed):
        return None
    return grade


def _assessment(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.get("assessment") or {}


def worked_route_keys(state: Dict[str, Any]) -> List[str]:
    keys = _assessment(state).get("grade_evidence_worked_routes") or []
    return [k for k in keys if isinstance(k, str)]


def dismissed_grade(state: Dict[str, Any], field: str = FIELD_LEAD_OS) -> Optional[str]:
    dismissed = _assessment(state).get("grade_evidence_dismissed") or {}
    if not isinstance(dismissed, dict):
        return None
    return normalize_lead_grade(dismissed.get(field))


def lead_os_evidence(state: Dict[str, Any], sessions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Payload of ``GET /api/assessment/grade-evidence``.

    ``routes`` are the evidence routes at or above the proposed grade (the ones
    the card asks about); empty when there is no proposal.
    """
    grades = _assessment(state).get("grades") or {}
    current = grades.get(FIELD_LEAD_OS)
    redpoint = grades.get("lead_max_rp")
    dismissed = dismissed_grade(state)
    evidence = collect_onsight_evidence(
        sessions, worked_keys=worked_route_keys(state), trips=state.get("trips") or [],
    )
    proposed = propose_grade(evidence, current=current, redpoint=redpoint, dismissed=dismissed)
    routes: List[Dict[str, Any]] = []
    if proposed is not None:
        routes = [r for r in evidence if grade_rank(r["grade"]) >= grade_rank(proposed)]
        routes.sort(key=lambda r: (-grade_rank(r["grade"]), r["date"]))
    return {
        "field": FIELD_LEAD_OS,
        "current": current,
        "redpoint": redpoint,
        "proposed": proposed,
        "routes": routes,
        "distinct_days": len({r["date"] for r in routes}),
        "distinct_spots": len({_norm(r.get("spot_name")) for r in routes}),
        "all_in_trip": bool(routes) and all(r["in_trip"] for r in routes),
        "dismissed": dismissed,
        "min_routes": MIN_ROUTES,
    }
