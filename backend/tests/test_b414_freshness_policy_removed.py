"""B414 (B414-5, B-FRESHNESS-POLICY-INERT) — no more ``freshness_policy``.

``progression_v1._update_test_from_log`` wrote ``{"stale_after_days": 90}``
on every ``tests.*`` entry (4 places) and nothing ever read it. The 90-day
validity of a test lives in ONE place, ``retest_policy.official_max``
(``valid_until`` / ``expired`` / ``expiring``, B414 model A), computed from the
test date. The writes are gone; an entry stored before B414 keeps the field
(append-only history, no migration) and reads exactly the same.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from backend.engine import retest_policy as rp
from backend.engine.progression_v1 import apply_feedback


def _state() -> dict:
    return {"body": {"weight_kg": 75.0}, "bodyweight_kg": 75.0, "assessment": {"tests": {}},
            "working_loads": {"entries": []}, "tests": {}, "baselines": {}}


def _log(day: str, session_id: str, items: list) -> dict:
    return {"date": day, "planned": [{"session_id": session_id, "tags": {"test": True}, "exercise_instances": []}],
            "actual": {"exercise_feedback_v1": items}}


@pytest.mark.parametrize("session_id,item,key", [
    ("test_max_hang_7s", {"exercise_id": "max_hang_7s", "used_total_load_kg": 110.0}, "max_strength"),
    ("test_max_hang_5s", {"exercise_id": "max_hang_5s", "used_total_load_kg": 112.0}, "max_strength"),
    ("test_repeater_7_3", {"exercise_id": "repeater_hang_7_3", "completed_sets": 22},
     "repeater_strength_endurance"),
    ("test_max_weighted_pullup", {"exercise_id": "weighted_pullup", "used_total_load_kg": 110.0},
     "pulling_strength"),
])
def test_a_test_log_writes_no_freshness_policy(session_id, item, key):
    out = apply_feedback(_log("2026-11-07", session_id, [dict(item, feedback_label="ok")]), _state())
    rows = out["tests"][key]
    assert rows and all("freshness_policy" not in r for r in rows)
    assert "freshness_policy" not in json.dumps(out)


def test_a_stored_entry_with_the_field_reads_the_same():
    """Legacy entries keep the field: the official max, its validity and the
    retest status are identical with and without it."""
    base = {"tests": {
        "max_strength": [{"test_id": "max_hang_7s_total_load", "date": "2026-09-24", "total_load_kg": 116.0,
                          "bodyweight_kg": 76.0}],
        "pulling_strength": [{"test_id": "weighted_pullup_2rm", "date": "2026-09-24", "total_load_2rm_kg": 123.0,
                              "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0}],
    }}
    legacy = deepcopy(base)
    for rows in legacy["tests"].values():
        for r in rows:
            r["freshness_policy"] = {"stale_after_days": 90}
    for on in ("2026-11-07", "2026-12-22", "2026-12-23"):
        for proto in (rp.PROTOCOL_HANG_7S, rp.PROTOCOL_HANG_5S, rp.PROTOCOL_PULLUP_2RM):
            assert rp.official_max(legacy, proto, on) == rp.official_max(base, proto, on)
        assert rp.retest_status(legacy, on) == rp.retest_status(base, on)
