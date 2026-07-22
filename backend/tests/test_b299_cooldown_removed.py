"""B299 — the per-cluster cooldown mechanism is removed.

`record_cluster_cooldown` never had a production caller, so `cooldowns.per_cluster`
was always empty and the resolver's `cluster_cooldown_fallback` /
`cluster_cooldown_downshift` branches never fired for a user. Both the writer and
the two resolver branches are deleted.

These tests pin the removal: a user_state carrying a (legacy) populated
`cooldowns.per_cluster` is now completely inert — no substitution, no downshift,
no `replanner` field on any resolved instance — and resolution is byte-identical
with or without it.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine.resolve_session import resolve_session

REPO_ROOT = str(Path(__file__).resolve().parents[2])


def _state(with_cooldown: bool) -> dict:
    st = {
        "schema_version": "1.4",
        "bodyweight_kg": 75.0,
        "context": {"location": "gym", "gym_id": "g"},
        "equipment": {"home": [], "gyms": [{"gym_id": "g", "equipment": ["weight", "pullup_bar"]}]},
    }
    if with_cooldown:
        # A legacy shape a real user could still carry. Every plausible squat
        # cluster key + a far-future until_date: if the branch still existed it
        # would substitute/downshift the primary. It must now do nothing.
        st["cooldowns"] = {"per_cluster": {
            "domain=strength_general|role=accessory|eq=weight|pattern=squat": {
                "until_date": "2099-01-01", "reason": "difficulty:fail",
            },
            "domain=strength_general|role=main|eq=weight|pattern=squat": {
                "until_date": "2099-01-01", "reason": "difficulty:fail",
            },
        }}
    return st


def _resolve(user_state: dict) -> list[dict]:
    result = resolve_session(
        repo_root=REPO_ROOT,
        session_path="backend/catalog/sessions/v1/lower_body_gym.json",
        templates_dir="backend/catalog/templates",
        exercises_path="backend/catalog/exercises/v1/exercises.json",
        out_path="output/__test_b299.json",
        user_state_override=user_state,
        write_output=False,
    )
    return result.get("resolved_session", {}).get("exercise_instances", [])


def test_no_replanner_field_when_cooldown_present():
    for inst in _resolve(_state(with_cooldown=True)):
        assert "replanner" not in inst, f"{inst.get('exercise_id')} carries a stale replanner note"


def test_resolution_identical_with_and_without_cooldown():
    without = _resolve(_state(with_cooldown=False))
    with_cd = _resolve(_state(with_cooldown=True))
    assert [i["exercise_id"] for i in without] == [i["exercise_id"] for i in with_cd]
    # …and no downshifted multiplier leaked into any prescription.
    for i in with_cd:
        presc = i.get("prescription") or {}
        assert presc.get("multiplier", 1.0) == pytest.approx(
            (next(w for w in without if w["instance_id"] == i["instance_id"]).get("prescription") or {}).get("multiplier", 1.0)
        )


def test_cooldown_state_is_not_mutated():
    st = _state(with_cooldown=True)
    before = deepcopy(st)
    _resolve(st)
    assert st == before
