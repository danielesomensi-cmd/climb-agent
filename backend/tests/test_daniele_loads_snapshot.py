"""B-fix-CORE regression snapshot: pin the 7 audit-baseline values.

Audit D (Tyler Twist, 2026-05-04) captured Daniele's working_loads vs the
suggestions surfaced post-resolve. Pre-fix, target_date was missing from the
resolve context and every external_load exercise fell back to FIXED_KG / BW%.

This test pins the post-fix expectation directly at `inject_targets`: given a
fresh entry and a non-empty `out["date"]`, the suggestion must equal
working_loads.next_external_load_kg — never the fallback.

If a future regression silently re-introduces the same class of bug (e.g. a
new caller rebuilds the resolve context without a date, or `_is_fresh` is
loosened to accept empty target dates), this snapshot will catch it.

Numbers come from the audit verdict:
  https://(internal) D — Tyler Twist closed-loop audit, table "with_date" column
"""
from __future__ import annotations

from copy import deepcopy

from backend.engine.progression_v1 import inject_targets

# Audit baseline (Daniele, user 7ea9f0ee-…, snapshot 2026-05-04).
# Each row is (exercise_id, working_loads.next_external_load_kg, unilateral).
AUDIT_BASELINE = [
    ("elbow_eccentric_curl", 5.0, False),
    ("forearm_pronation_supination", 5.0, False),
    ("wrist_curl", 5.0, False),
    ("bench_press", 32.0, False),
    ("barbell_row", 34.5, False),
    ("face_pull", 14.0, False),
    # weighted_pullup is total_load (not external_load), exercised separately
    # via the total_load reader path; same target_date dependency, same fix.
]

UPDATED_AT = "2026-04-30"
TARGET_DATE = "2026-05-04"


def _user_state() -> dict:
    """Reconstructed from Daniele's working_loads at snapshot time."""
    entries = []
    for ex_id, next_kg, _ in AUDIT_BASELINE:
        entries.append(
            {
                "exercise_id": ex_id,
                "key": ex_id,
                "setup": {},
                "last_external_load_kg": next_kg,
                "next_external_load_kg": next_kg,
                "last_feedback_label": "ok",
                "last_completed": True,
                "updated_at": UPDATED_AT,
            }
        )
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 77.5,  # rough Daniele estimate; only matters for BW% fallback
        "baselines": {"hangboard": [{"max_total_load_kg": 110.0}]},
        "working_loads": {"entries": entries, "rules": {}},
    }


def _make_day(exercise_id: str, date: str) -> dict:
    return {
        "date": date,
        "sessions": [
            {
                "session_id": "snapshot",
                "intent": "strength",
                "location": "home",
                "exercise_instances": [
                    {
                        "exercise_id": exercise_id,
                        "load_model": "external_load",
                        "unilateral": False,
                        "prescription": {"sets": 3, "reps": 10},
                        "suggested": {},
                    }
                ],
            }
        ],
    }


def _suggested(out: dict) -> float | None:
    inst = out["sessions"][0]["exercise_instances"][0]
    return (inst.get("suggested") or {}).get("suggested_external_load_kg")


def test_audit_baseline_snapshot_post_fix():
    """All 6 audit-baseline exercises must surface working_loads, not fallback."""
    us = _user_state()

    failures: list[str] = []
    for ex_id, expected, _ in AUDIT_BASELINE:
        out = inject_targets(_make_day(ex_id, TARGET_DATE), deepcopy(us))
        actual = _suggested(out)
        if actual != expected:
            failures.append(f"{ex_id}: expected {expected}, got {actual}")

    assert not failures, (
        "Audit baseline regression — working_loads not honored:\n  "
        + "\n  ".join(failures)
    )


def test_empty_date_still_falls_back():
    """Direct evidence of the original bug surface: empty date → fallback values.

    Pinned so a future change to `_is_fresh` or `_best_entry` that accidentally
    accepts empty dates is caught — the freshness gate is a real guardrail,
    Patch B only routes a date when one exists, never invents one.
    """
    us = _user_state()
    # elbow_eccentric_curl is the most extreme delta in the audit (5.0 → 1.5).
    out = inject_targets(_make_day("elbow_eccentric_curl", ""), deepcopy(us))
    assert _suggested(out) == 1.5, (
        "Empty date must still fall back to FIXED_KG[elbow_eccentric_curl]=1.5; "
        "if this changes, the freshness gate has been relaxed and other code "
        "paths may now leak stale entries."
    )
