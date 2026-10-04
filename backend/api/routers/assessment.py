"""Assessment router — compute 6-axis profile; onsight evidence (A292)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import (
    get_user_id,
    load_state,
    refresh_current_level_from_grades,
    save_state,
)
from backend.api.models import AssessmentRequest, ConfirmGradeRequest
from backend.engine import grade_evidence as ge
from backend.engine.assessment_v1 import (
    PROFILE_SCORING_VERSION,
    compute_assessment_profile_with_source,
)
from backend.engine.outdoor_log import load_outdoor_sessions
from backend.engine.progression_v1 import estimate_missing_baselines

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.post("/compute")
def compute_assessment(req: AssessmentRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Compute 6-axis assessment profile and save into state."""
    state = load_state(user_id)

    assessment = req.assessment or state.get("assessment", {})
    goal = req.goal or state.get("goal", {})

    if not goal:
        raise HTTPException(status_code=422, detail="No goal provided and none in state")

    try:
        profile, profile_source = compute_assessment_profile_with_source(assessment, goal)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Assessment computation failed: {e}")

    # Save profile into state
    # A269: scores and their provenance are written together, never apart.
    state.setdefault("assessment", {})["profile"] = profile
    state["assessment"]["profile_source"] = profile_source
    state["assessment"]["profile_scoring_version"] = PROFILE_SCORING_VERSION
    estimate_missing_baselines(state)  # B121: re-estimate pulling baseline from test results
    save_state(state, user_id)

    return {"profile": profile}


# --------------------------------------------------------------------------- #
# A292 (R6b) — lead onsight evidence from the outdoor log
# --------------------------------------------------------------------------- #

# Cap on the remembered "worked" route keys (one per route, never pruned by
# date): a guard against an unbounded list, far above any real log.
_WORKED_KEYS_CAP = 500


@router.get("/grade-evidence")
def get_grade_evidence(user_id: Optional[str] = Depends(get_user_id)):
    """Read-only: does the outdoor log support a harder lead onsight than the
    declared one? ``proposed`` is null when it does not."""
    state = load_state(user_id)
    return ge.lead_os_evidence(state, load_outdoor_sessions(user_id))


def _remember_worked(assessment: Dict[str, Any], keys: List[str]) -> None:
    if not keys:
        return
    existing = [k for k in (assessment.get("grade_evidence_worked_routes") or []) if isinstance(k, str)]
    merged = existing + [k for k in keys if k not in existing]
    assessment["grade_evidence_worked_routes"] = merged[-_WORKED_KEYS_CAP:]


def _evidence_row(route: Dict[str, Any], style: str) -> Dict[str, Any]:
    return {
        "key": route["key"],
        "date": route["date"],
        "spot_name": route.get("spot_name"),
        "name": route.get("name"),
        "grade": route["grade"],
        "style": style,
    }


@router.post("/confirm-grade")
def confirm_grade(req: ConfirmGradeRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Confirm or decline the onsight proposal, route by route.

    Writes only ``assessment.grades.lead_max_os`` (confirm),
    ``assessment.grades_source``, ``assessment.grade_evidence_dismissed`` and
    ``assessment.grade_evidence_worked_routes``, then rebuilds
    ``performance.current_level`` as PUT /api/state does. The outdoor log is
    never rewritten: a style changes in the log only when the athlete edits it.
    """
    state = load_state(user_id)
    sessions = load_outdoor_sessions(user_id)
    field = req.field
    assessment = state.setdefault("assessment", {})
    grades = assessment.setdefault("grades", {})
    current = grades.get(field)
    redpoint = grades.get("lead_max_rp")

    evidence = ge.collect_onsight_evidence(
        sessions, worked_keys=ge.worked_route_keys(state), trips=state.get("trips") or [],
    )
    by_key = {r["key"]: r for r in evidence}
    unknown = [a.key for a in req.routes if a.key not in by_key]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_route", "message": "Route is not onsight evidence in your log.", "keys": unknown},
        )
    worked = [a.key for a in req.routes if a.style == "worked"]

    if req.decision == "dismiss":
        proposed = ge.propose_grade(
            evidence, current=current, redpoint=redpoint, dismissed=ge.dismissed_grade(state, field),
        )
        if proposed is None:
            raise HTTPException(status_code=422, detail={"code": "no_proposal", "message": "Nothing to dismiss."})
        _remember_worked(assessment, worked)
        dismissed = assessment.get("grade_evidence_dismissed")
        if not isinstance(dismissed, dict):
            dismissed = {}
        dismissed[field] = proposed
        assessment["grade_evidence_dismissed"] = dismissed
        save_state(state, user_id)
        return {"decision": "dismiss", "field": field, "dismissed": proposed}

    confirmed = [
        _evidence_row(by_key[a.key], a.style) for a in req.routes if a.style in {"onsight", "flash"}
    ]
    supported = ge.supported_grade(confirmed)
    if supported is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "insufficient_evidence",
                "message": (
                    f"Confirm at least {ge.MIN_ROUTES} onsight or flash routes, "
                    "on two different days or at two different crags."
                ),
            },
        )
    rp_rank = ge.grade_rank(redpoint)
    if req.grade is not None:
        grade = ge.normalize_lead_grade(req.grade)
        if grade is None:
            raise HTTPException(status_code=422, detail={"code": "unknown_grade", "message": f"Unknown grade {req.grade!r}."})
        if ge.grade_rank(grade) > ge.grade_rank(supported):
            raise HTTPException(
                status_code=422,
                detail={"code": "not_supported", "message": f"The confirmed routes support {supported}, not {grade}.",
                        "supported": supported},
            )
        if rp_rank >= 0 and ge.grade_rank(grade) > rp_rank:
            raise HTTPException(
                status_code=422,
                detail={"code": "above_redpoint", "message": "Onsight cannot be above your redpoint."},
            )
    else:
        grade = supported
        if rp_rank >= 0 and ge.grade_rank(grade) > rp_rank:
            grade = ge.normalize_lead_grade(redpoint)
    if ge.grade_rank(grade) <= ge.grade_rank(current):
        raise HTTPException(
            status_code=422,
            detail={"code": "not_above_current", "message": f"{grade} is not above your current onsight {current}.",
                    "supported": supported},
        )

    grades[field] = grade
    sources = assessment.get("grades_source")
    if not isinstance(sources, dict):
        sources = {}
    sources[field] = {
        "source": "outdoor_confirmed",
        "date": date.today().isoformat(),
        "previous": current,
        "evidence": [r for r in confirmed if ge.grade_rank(r["grade"]) >= ge.grade_rank(grade)],
    }
    assessment["grades_source"] = sources
    _remember_worked(assessment, worked)
    refresh_current_level_from_grades(state)
    save_state(state, user_id)  # B127: the profile fingerprint includes grades
    return {
        "decision": "confirm",
        "field": field,
        "grade": grade,
        "previous": current,
        "evidence": sources[field]["evidence"],
        "profile": (state.get("assessment") or {}).get("profile"),
    }
