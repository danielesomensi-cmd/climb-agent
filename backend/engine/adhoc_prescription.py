"""A242 — deterministic per-exercise prescription proposal for the custom-session
builder (and, from Phase 3, the adhoc composer).

Custom-only and read-only: this never touches ``resolve_session`` / planned-
session resolution. It is pure and deterministic — given the same catalog entry,
user_state and phase, it always returns the same proposal.

The proposal overlays three deterministic layers:
  1. structure   — the exercise's ``prescription_defaults`` (sets/reps/rest);
  2. load memory — the user's last logged ``working_loads`` value for that
     exercise (Phase 1 writes it), surfaced as ``last_logged`` + prefilled into
     ``load_kg``. **Never an invented absolute** — 0 when nothing is remembered;
  3. effort band — a coarse phase → effort cue (see PHASE_EFFORT_BAND).

The app has no RPE/RIR in its data model (catalog defaults carry only
sets/reps/work/rest; the engine uses %-of-max and grade-relative loads). The
effort band is therefore a *display-only* human-facing guidance string — it is
never persisted, never a number, and never fed to the engine.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any, Dict, Optional

from backend.engine.anchored_load import (
    ANCHORED_EXERCISES,
    CUSTOM_INTENSITY,
    anchor_summary,
    anchored_load,
)
from backend.engine.progression_v1 import (
    PULLING_EXTERNAL_SCALING,
    _best_entry,
    _get_bodyweight,
    _get_pulling_baseline,
    _hangboard_suggested,
    _round_half_step,
    limit_grade_target,
    NOT_FINGER_MAX_TOTAL_LOAD,
    weighted_pullup_target,
)

# A253 — genuine (max-derived) load anchor for the adhoc path, SCOPED to
# fingers/hangboard + weighted-pull. Baseline sources that count as a real test.
_TEST_BASELINE_SOURCES = ("test", "test_session")
# total_load ids that are NOT hangboard hangs (they'd wrongly read the finger
# baseline) — excluded from the hangboard anchor branch.
# B363: plus every total_load exercise that is not a two-arm edge hang.
_NON_HANGBOARD_TOTAL_LOAD = ("weighted_pullup",) + NOT_FINGER_MAX_TOTAL_LOAD

# Coarse macrocycle-phase → effort-band cue. Display-only, custom-only, never
# persisted. Keys are the canonical phase ids (macrocycle_v1.PHASE_ORDER).
PHASE_EFFORT_BAND: Dict[str, str] = {
    "base": "Moderate — build volume, keep 3-4 reps in reserve",
    "strength_power": "Hard — heavy, low reps, 1-2 in reserve",
    "power_endurance": "Sustained hard — pump-tolerant, 2-3 in reserve",
    "performance": "High — near-limit quality efforts",
    "deload": "Easy — recover, well short of failure",
}


def effort_band_for_phase(phase: Optional[str]) -> Optional[str]:
    """Return the display-only effort cue for *phase* (None if unknown/absent)."""
    if not phase:
        return None
    return PHASE_EFFORT_BAND.get(phase)


def propose_exercise_prescription(
    exercise_id: str,
    catalog: Dict[str, Any],
    user_state: Dict[str, Any],
    phase: Optional[str] = None,
    *,
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministic starting prescription for *exercise_id*.

    ``load_kg`` is the user's remembered load (freshness disabled — a human
    reviews and edits it) or 0 when none is logged; it is never invented.
    ``last_logged`` carries the raw memory (value + perceived effort + date) so
    the UI can render "last time: X · N ago". ``effort_band`` is display-only.
    """
    ex = catalog.get(exercise_id) or {}
    defaults = ex.get("prescription_defaults") or {}
    today = today or _date.today().isoformat()

    # Remembered load — non-mutating read, freshness DISABLED (stale is safe
    # when dated; the builder is human-in-the-loop, unlike autonomous
    # progression which keeps the 60-day gate).
    entry = _best_entry(user_state, exercise_id, {}, today, freshness_days=None)

    load_kg: float = 0.0
    last_logged: Optional[Dict[str, Any]] = None
    if entry:
        kg = entry.get("last_external_load_kg")
        last_logged = {
            "load_kg": kg if isinstance(kg, (int, float)) else None,
            "feedback_label": entry.get("last_feedback_label"),
            "date": entry.get("updated_at"),
        }
        if isinstance(kg, (int, float)) and kg > 0:
            load_kg = float(kg)

    # B364: the four anchored exercises of a TESTED athlete are prefilled by
    # the single anchored_load on ``today`` — the same number the plan, the
    # picker and the custom player show. ``last_logged`` keeps the true last
    # value. An assisted hang (negative external) proposes 0 kg.
    anchored: Optional[Dict[str, Any]] = None
    if exercise_id in ANCHORED_EXERCISES:
        anchored = anchored_load(
            user_state, exercise_id, date=today, phase_id=phase, intensity=CUSTOM_INTENSITY,
            sets=defaults.get("sets"), reps=defaults.get("reps"), work_seconds=defaults.get("work_seconds"),
            catalog_intensity=(ex.get("attributes") or {}).get("intensity_pct"),
        )
        if anchored is not None:
            load_kg = max(0.0, float(anchored["external"]))

    # B363: the weighted pull-up is prefilled from the 2RM reference as a % for
    # the phase, never from the raw memory — the last logged load may come from
    # a set with a different rep count, or be the 2RM test itself (+45 kg
    # proposed for a 4x3). ``last_logged`` still shows the true last value.
    # Without memory it fires only on a TESTED baseline (A253 boundary: a
    # grade-estimate is never surfaced as a number).
    if exercise_id == "weighted_pullup" and anchored is None:
        tested = str((_get_pulling_baseline(user_state) or {}).get("source") or "") in _TEST_BASELINE_SOURCES
        target = weighted_pullup_target(user_state, phase, "hard") if (load_kg > 0 or tested) else None
        if target is not None:
            load_kg = target["external"]

    # A296: a limit-family exercise carries the plan's limit target for
    # ``today`` (display only: the custom player re-reads it on the day).
    grade_target = limit_grade_target(user_state, exercise_id, today)

    return {
        **({"grade_target": grade_target} if grade_target is not None else {}),
        "sets": defaults.get("sets", 1),
        "reps": defaults.get("reps"),
        "work_seconds": defaults.get("work_seconds"),
        "rest_between_sets_seconds": defaults.get("rest_between_sets_seconds"),
        "rest_between_reps_seconds": defaults.get("rest_between_reps_seconds"),
        "load_kg": load_kg,                       # remembered value or 0 — never invented
        "effort_band": effort_band_for_phase(phase),
        "last_logged": last_logged,               # {load_kg, feedback_label, date} | null
        **({"load_mode": "anchored", "anchored": anchor_summary(anchored)} if anchored is not None else {}),
    }


def anchor_adhoc_load(
    exercise: Dict[str, Any],
    user_state: Dict[str, Any],
    phase: Optional[str],
    *,
    today: Optional[str] = None,
    reps: Optional[int] = None,
    sets: Optional[int] = None,
) -> Optional[float]:
    """A253 — a *genuine* (max-derived) starting external load for an adhoc
    exercise the user has never logged, or None.

    This is the smart layer above B298's guaranteed-empty field, SCOPED to the
    only buckets where progression_v1 has a real max/grade anchor that the audit
    (D258) judged worth surfacing:

      * hangboard ``total_load`` — % of the user's max-hang test baseline;
      * ``weighted_pullup`` — % of the pulling 1RM test baseline;
      * ``barbell_row`` / ``face_pull`` — scaled off the pulling max-external test.

    Boundary (D258 corrections): a %-of-a-real-**test**-max is *computed*, not
    invented — so we require the underlying baseline's ``source`` to be a real
    test (``test``/``test_session``), never a grade-estimate. The crude planned
    fallbacks (``PCT_BW`` 0.15, ``FIXED_KG``) are deliberately NOT surfaced —
    they would put a misleading ~12 kg under a Back Squat; those stay empty.

    Read-only and pure: reads ``user_state.baselines``/bodyweight via
    progression_v1's pure helpers, never mutates state, never calls
    ``estimate_missing_baselines``. Returns a positive kg or None.
    """
    eid = str(exercise.get("id") or "")
    load_model = exercise.get("load_model")

    # ── B364: anchored exercises of a tested athlete → anchored_load ────────
    if eid in ANCHORED_EXERCISES:
        defaults = exercise.get("prescription_defaults") or {}
        anch = anchored_load(
            user_state, eid, date=today or _date.today().isoformat(), phase_id=phase,
            intensity=CUSTOM_INTENSITY, sets=sets or defaults.get("sets"),
            reps=reps or defaults.get("reps"), work_seconds=defaults.get("work_seconds"),
            catalog_intensity=(exercise.get("attributes") or {}).get("intensity_pct"),
        )
        if anch is not None:
            return float(anch["external"]) if anch["external"] > 0 else None

    # ── weighted-pull from the pulling test baseline ────────────────────────
    if eid == "weighted_pullup":
        pulling = _get_pulling_baseline(user_state)
        if not pulling or str(pulling.get("source") or "") not in _TEST_BASELINE_SOURCES:
            return None
        # B363: same 2RM-reference rule as the planned path.
        target = weighted_pullup_target(user_state, phase, "medium")
        if target is None:
            return None
        return target["external"] if target["external"] > 0 else None

    if eid in PULLING_EXTERNAL_SCALING:  # barbell_row, face_pull
        pulling = _get_pulling_baseline(user_state)
        if not pulling or str(pulling.get("source") or "") not in _TEST_BASELINE_SOURCES:
            return None
        max_ext = pulling.get("max_external_load_kg")
        if not isinstance(max_ext, (int, float)) or max_ext <= 0:
            return None
        external = _round_half_step(float(max_ext) * PULLING_EXTERNAL_SCALING[eid])
        return external if external > 0 else None

    # ── hangboard total_load from the finger max-hang test baseline ─────────
    if load_model == "total_load" and eid not in _NON_HANGBOARD_TOTAL_LOAD:
        hb = ((user_state.get("baselines") or {}).get("hangboard") or [])
        if not hb:
            return None
        baseline = hb[0]
        if str(baseline.get("source") or "") not in _TEST_BASELINE_SOURCES:
            return None
        if not isinstance(baseline.get("max_total_load_kg"), (int, float)):
            return None
        suggestion = _hangboard_suggested(
            user_state, eid, exercise.get("prescription_defaults") or {},
            exercise_attrs=exercise.get("attributes"),
        )
        # Defense in depth: a grade-estimate slipped through would be tagged.
        if suggestion.get("load_source") == "estimated":
            return None
        external = suggestion.get("suggested_external_load_kg")
        if isinstance(external, (int, float)) and external > 0:
            return float(external)
        return None

    return None
