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

from backend.engine.progression_v1 import _best_entry

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

    return {
        "sets": defaults.get("sets", 1),
        "reps": defaults.get("reps"),
        "work_seconds": defaults.get("work_seconds"),
        "rest_between_sets_seconds": defaults.get("rest_between_sets_seconds"),
        "rest_between_reps_seconds": defaults.get("rest_between_reps_seconds"),
        "load_kg": load_kg,                       # remembered value or 0 — never invented
        "effort_band": effort_band_for_phase(phase),
        "last_logged": last_logged,               # {load_kg, feedback_label, date} | null
    }
