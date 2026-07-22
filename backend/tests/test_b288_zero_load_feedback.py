"""B288: a logged load of 0 kg is a real answer, not a missing value.

`apply_feedback` read the used load with `a or b`, so 0.0 was falsy and the
item was dropped by the `if used_load is None: continue` guard — the memory
silently kept the previous (heavier) load, and the next session proposed it
again. "I did it with no added weight" must be recorded like any other value.

Covers both external_load branches: bilateral and unilateral (per hand).
"""
from __future__ import annotations

from backend.engine.progression_v1 import apply_feedback


def _state() -> dict:
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 70.0,
        "working_loads": {
            "entries": [
                {
                    "exercise_id": "wrist_curl",
                    "key": "wrist_curl",
                    "setup": {},
                    "last_external_load_kg": 5.0,
                    "next_external_load_kg": 5.0,
                    "last_feedback_label": "ok",
                    "updated_at": "2026-07-01",
                }
            ],
            "rules": {},
        },
    }


def _entry(state: dict, key: str) -> dict | None:
    for e in (state.get("working_loads") or {}).get("entries") or []:
        if e.get("key") == key:
            return e
    return None


def _log(items: list[dict]) -> dict:
    return {
        "date": "2026-07-20",
        "session_id": "prehab_maintenance",
        "actual": {"exercise_feedback_v1": items},
    }


def test_zero_load_is_recorded_not_discarded():
    """0 kg overwrites the remembered 5 kg instead of being read as 'absent'."""
    updated = apply_feedback(
        _log([
            {
                "exercise_id": "wrist_curl",
                "feedback_label": "ok",
                "completed": True,
                "used_external_load_kg": 0,
                "load_model": "external_load",
            }
        ]),
        _state(),
    )
    entry = _entry(updated, "wrist_curl")
    assert entry is not None
    assert entry["last_external_load_kg"] == 0.0, (
        f"0 kg must be recorded, got {entry['last_external_load_kg']} — the "
        "falsy-0 bug is back and the item was dropped"
    )
    assert entry["updated_at"] == "2026-07-20"


def test_zero_load_legacy_key_is_recorded():
    """Same through the legacy `used_load_kg` key."""
    updated = apply_feedback(
        _log([
            {
                "exercise_id": "wrist_curl",
                "feedback_label": "ok",
                "completed": True,
                "used_load_kg": 0.0,
                "load_model": "external_load",
            }
        ]),
        _state(),
    )
    assert _entry(updated, "wrist_curl")["last_external_load_kg"] == 0.0


def test_zero_load_unilateral_is_recorded():
    """Per-hand branch had the same `or` chain — one entry per hand.

    C-LOADMODEL-MISTAG: the per-hand write path is gated on genuine finger
    loading-pin equipment (not raw unilaterality), so this uses a real
    loading-pin exercise id (``lp_max_lift_5s``) rather than a synthetic one.
    """
    updated = apply_feedback(
        _log([
            {
                "exercise_id": "lp_max_lift_5s",
                "feedback_label": "ok",
                "completed": True,
                "hand": hand,
                "used_external_load_kg": 0,
                "load_model": "external_load",
                "unilateral": True,
            }
            for hand in ("right", "left")
        ]),
        _state(),
    )
    for hand in ("right", "left"):
        entry = _entry(updated, f"lp_max_lift_5s:{hand}")
        assert entry is not None, f"{hand} hand entry missing — 0 kg was dropped"
        assert entry["last_external_load_kg"] == 0.0


def test_missing_load_still_skipped():
    """The guard itself stays: no load at all must NOT touch the memory."""
    updated = apply_feedback(
        _log([
            {
                "exercise_id": "wrist_curl",
                "feedback_label": "ok",
                "completed": True,
                "load_model": "external_load",
            }
        ]),
        _state(),
    )
    entry = _entry(updated, "wrist_curl")
    assert entry["last_external_load_kg"] == 5.0
    assert entry["updated_at"] == "2026-07-01", (
        "An item with no load must leave the remembered value untouched"
    )
