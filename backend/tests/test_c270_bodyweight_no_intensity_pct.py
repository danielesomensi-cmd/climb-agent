"""C270 — a bodyweight-only exercise never carries a load-intensity attribute.

`attributes.intensity_pct` is what makes the resolver call
`suggest_max_hang_load()`, which turns a % of the athlete's max-hang total into
added weight. On `min_edge_hang` (Eva López MED: bodyweight only, intensity set
by the edge size, never by load) it produced "20 mm + 32 kg for 12 s" — 95% of a
7-second max held for 12 seconds, i.e. a hang to failure on the wrong protocol.
The exercise is `bodyweight_only`, so the attribute had no business there.
"""
import json
from pathlib import Path

from backend.engine.resolve_session import suggest_max_hang_load

EXERCISES = Path("backend/catalog/exercises/v1/exercises.json")


def _catalog():
    return {e["id"]: e for e in json.loads(EXERCISES.read_text())["exercises"]}


def test_no_bodyweight_only_exercise_has_intensity_pct():
    offenders = [
        ex_id for ex_id, e in _catalog().items()
        if e.get("load_model") == "bodyweight_only"
        and (e.get("attributes") or {}).get("intensity_pct") is not None
    ]
    assert offenders == [], f"bodyweight_only exercises with intensity_pct: {offenders}"


def test_min_edge_hang_gets_no_added_weight_suggestion():
    ex = _catalog()["min_edge_hang"]
    state = {
        "bodyweight_kg": 78.0,
        "baselines": {"hangboard": [{
            "edge_mm": 20, "grip": "half_crimp", "hang_seconds": 7,
            "max_total_load_kg": 116.0,
        }]},
    }
    # The block prescription of finger_max_strength carries only the *range*,
    # so the exercise attribute was the sole trigger.
    prescription = dict(ex["prescription_defaults"])
    prescription["intensity_pct_of_total_load_range"] = [0.85, 0.95]
    assert suggest_max_hang_load(state, prescription, exercise_attrs=ex["attributes"]) is None
