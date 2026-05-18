"""B253: backfill assessment.tests_source for pre-D214 legacy user_state.

D214 (commit 2559329, 2026-04-20) introduced the tests_source sidecar but
did not migrate existing user_state. Users onboarded earlier (Daniele
included) have empty/missing tests_source even when tests.* and
baselines.*.source carry authoritative measurement evidence.

This migration infers measurement status from append-only history that
exists only when a real test was completed:
- tests.max_strength      → max_hang_20mm_{5,7}s_total_kg
- tests.repeater_strength_endurance → repeater_7_3_max_sets_20mm
- tests.pulling_strength  → weighted_pullup_2rm_total_kg

Lazy on-read: invoked from deps.load_state. Idempotent. Never downgrades
an existing "measured" entry.

Out of scope (intentional):
- per-hand LP keys (lp_max_lift_5s_R_kg etc.): legacy users predate LP,
  no migration source available.
- bodyweight-only tests (hip_flexibility, l_sit_hold, max_hang_duration,
  max_pullups_bw): no append-only history exists for these in legacy
  state. Future test completion will populate tests_source the normal
  way via progression_v1._mark_measured.
"""
from typing import Any, Dict


def migrate(state: Dict[str, Any]) -> bool:
    """Infer tests_source from tests.* history. Returns True if mutated."""
    if not isinstance(state, dict):
        return False

    assessment = state.get("assessment")
    if not isinstance(assessment, dict):
        return False

    tests_history = state.get("tests")
    if not isinstance(tests_history, dict):
        return False

    # Build the marks we'd add, without mutating state yet.
    inferred: Dict[str, str] = {}

    max_strength = tests_history.get("max_strength") or []
    if any(
        str(e.get("exercise_id") or "") in ("max_hang_5s", "max_hang_7s")
        for e in max_strength
        if isinstance(e, dict)
    ):
        inferred["max_hang_20mm_7s_total_kg"] = "measured"
        inferred["max_hang_20mm_5s_total_kg"] = "measured"

    repeater = tests_history.get("repeater_strength_endurance") or []
    if any(isinstance(e, dict) for e in repeater):
        inferred["repeater_7_3_max_sets_20mm"] = "measured"

    pulling = tests_history.get("pulling_strength") or []
    if any(isinstance(e, dict) for e in pulling):
        inferred["weighted_pullup_2rm_total_kg"] = "measured"

    if not inferred:
        return False  # nothing to backfill — no-op, no side effects

    existing = assessment.get("tests_source")
    if not isinstance(existing, dict):
        existing = {}

    # Only apply marks that aren't already "measured".
    new_marks = {k: v for k, v in inferred.items() if existing.get(k) != "measured"}
    if not new_marks:
        return False

    src = assessment.setdefault("tests_source", {})
    if not isinstance(src, dict):
        return False
    src.update(new_marks)
    return True
