"""A262 — public, unauthenticated 5-axis assessment.

The acquisition surface for the engine: a cold visitor answers six questions and
gets their profile, with no account and nothing persisted. It exists so the link
can be posted somewhere like r/climbharder and give something before asking for
anything.

Deliberately a separate router from ``assessment.py``: that one loads state,
writes ``assessment.profile`` and re-estimates baselines, and must stay
authenticated. Sharing a module would make it one careless ``Depends`` away from
exposing a write path.

Three rules hold here and are enforced by tests:

1. **No state.** No ``get_user_id``, no ``load_state``, no ``save_state``. The
   handler is a pure function of its request body.
2. **No implicit defaults.** ``compute_assessment_profile`` falls back to
   ``current_grade="7a"`` / ``target_grade="7c+"`` when they are missing — fine
   for an onboarded user whose state is validated upstream, dishonest here: it
   would return a stranger's profile to someone who left the field blank. Both
   are required.
3. **Grades validated against the catalog.** ``grade_index()`` answers 0 for an
   unknown grade, which silently produces a plausible, wrong score. Unknown
   grade → 422, never a quiet zero.
"""

from __future__ import annotations

from typing import Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.api.rate_limit import limiter
from backend.engine.assessment_v1 import (
    GRADE_ORDER,
    compute_assessment_profile,
    grade_index,
)
from backend.engine.grade_mapping import BOULDER_TO_LEAD

router = APIRouter(prefix="/api/public", tags=["public"])

# Ordered worst-first so ties resolve to the axis the engine treats as most
# foundational — telling someone their weakness is "technique" when finger
# strength scores the same is the less actionable of the two answers.
#
# A270: `technique` is no longer eligible at all. It used to be last only in a
# TIE, so it could still win outright — and after the gap demotion it is a
# single self-declared weakness. That path would tell a stranger "your weakest
# link is technique" on the strength of the dropdown they just filled in. It
# stays on the radar and in `profile`; it stops being able to be the answer.
_AXIS_PRIORITY = (
    "finger_strength",
    "pulling_strength",
    "power_endurance",
    "endurance",
)

_AXIS_LABELS: Dict[str, str] = {
    "finger_strength": "Finger strength",
    "pulling_strength": "Pulling strength",
    "power_endurance": "Power endurance",
    "technique": "Technique",
    "endurance": "Endurance",
}


class PublicAssessmentRequest(BaseModel):
    """Six required answers, plus the optional numbers that turn two of the five
    axes from inferred into measured (A263)."""

    discipline: Literal["lead", "boulder"] = "lead"
    current_grade: str = Field(min_length=1, max_length=8)
    target_grade: str = Field(min_length=1, max_length=8)
    max_rp: str = Field(min_length=1, max_length=8)
    max_os: str = Field(min_length=1, max_length=8)
    climbing_years: float = Field(ge=0, le=70)
    primary_weakness: Optional[str] = Field(default=None, max_length=40)

    # A263 — optional test numbers. Without them the finger and pulling axes are
    # derived from declared grades, which is the weakest part of the estimate and
    # the one this audience is most likely to call out: a climber who trains
    # knows their max hang. Both are entered as ADDED weight, the way people
    # actually record them (negative = assisted); the engine wants totals, and
    # converting here keeps that convention in one place.
    bodyweight_kg: Optional[float] = Field(default=None, gt=25, le=200)
    max_hang_added_kg: Optional[float] = Field(default=None, ge=-100, le=150)
    weighted_pullup_added_kg: Optional[float] = Field(default=None, ge=-100, le=150)


def _to_lead(grade: str, discipline: str) -> str:
    """Normalise a grade to the lead scale the engine reasons in.

    Boulder input arrives in Fontainebleau (the engine's internal convention)
    and is mapped through the same table the onboarding and the mid-cycle
    discipline switch use, so a boulderer's profile is computed against the same
    benchmarks as everyone else's rather than against a second set that could
    drift.
    """
    if discipline == "boulder":
        mapped = BOULDER_TO_LEAD.get(grade.upper())
        if mapped is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown boulder grade: {grade!r}",
            )
        return mapped
    if grade not in GRADE_ORDER:
        raise HTTPException(status_code=422, detail=f"Unknown lead grade: {grade!r}")
    return grade


@router.post("/assessment")
@limiter.limit("20/minute")
def public_assessment(request: Request, body: PublicAssessmentRequest):
    """Compute the 5-axis profile from six answers. Nothing is stored."""
    current = _to_lead(body.current_grade, body.discipline)
    target = _to_lead(body.target_grade, body.discipline)
    rp = _to_lead(body.max_rp, body.discipline)
    os_ = _to_lead(body.max_os, body.discipline)

    # An onsight harder than a redpoint is not a scale we can reason about: the
    # gap drives both technique and power-endurance, and a negative gap would
    # land in the "gap <= 2" bucket and read as elite. Reject it instead.
    if grade_index(os_) > grade_index(rp):
        raise HTTPException(
            status_code=422,
            detail="Onsight/flash grade cannot be harder than redpoint grade.",
        )

    # A263 — the engine scores hangboard and pull-up numbers as ratios against
    # bodyweight, and falls back to 70 kg when it is missing. A stranger's 70 kg
    # default would silently rescale their own numbers, so tests without a
    # bodyweight are refused rather than scored against a stand-in.
    tests: Dict[str, float] = {}
    measured: list[str] = []
    has_numbers = (
        body.max_hang_added_kg is not None or body.weighted_pullup_added_kg is not None
    )
    if has_numbers and body.bodyweight_kg is None:
        raise HTTPException(
            status_code=422,
            detail="Bodyweight is required to score hangboard or pull-up numbers.",
        )

    bw = body.bodyweight_kg
    if bw is not None and body.max_hang_added_kg is not None:
        tests["max_hang_20mm_7s_total_kg"] = bw + body.max_hang_added_kg
        measured.append("finger_strength")
    if bw is not None and body.weighted_pullup_added_kg is not None:
        tests["weighted_pullup_1rm_total_kg"] = bw + body.weighted_pullup_added_kg
        measured.append("pulling_strength")

    assessment = {
        "grades": {"lead_max_rp": rp, "lead_max_os": os_},
        "experience": {"climbing_years": body.climbing_years},
        "self_eval": {"primary_weakness": body.primary_weakness},
        "body": {"weight_kg": bw} if bw is not None else {},
        "tests": tests,
    }
    goal = {"current_grade": current, "target_grade": target}

    try:
        profile = compute_assessment_profile(assessment, goal)
    except Exception as exc:  # noqa: BLE001 — surfaced as 422, never a 500
        raise HTTPException(status_code=422, detail=f"Assessment failed: {exc}")

    weakest = min(_AXIS_PRIORITY, key=lambda axis: (profile[axis], _AXIS_PRIORITY.index(axis)))

    return {
        "profile": profile,
        "weakest_axis": weakest,
        "weakest_axis_label": _AXIS_LABELS[weakest],
        # Echoed so the client can render the radar against the same target the
        # engine scored against — for a boulderer that is the converted grade,
        # not what they typed.
        "target_grade_lead": target,
        # A262/A263: said out loud in the payload, not only in the page copy.
        # `measured_axes` names the axes backed by a number the user supplied;
        # everything else is derived from declared grades and self-report —
        # useful, not a measurement, and pretending otherwise is how a tool like
        # this loses credibility with the audience it is aimed at.
        "measured_axes": measured,
        "estimated": not measured,
    }
