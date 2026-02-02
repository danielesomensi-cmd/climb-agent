from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.adaptation.closed_loop import (  # noqa: E402
    apply_multiplier,
    update_user_state_adjustments,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pick_baseline_load(user_state: dict, exercise_id: str) -> float:
    tests = (user_state.get("tests") or {}).get("max_strength") or []
    for test in tests:
        if test.get("exercise_id") != exercise_id:
            continue
        external = test.get("external_load_kg")
        if external is not None:
            return float(external)
        total = test.get("total_load_kg")
        if total is not None:
            return float(total)
    return 20.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Closed-loop adaptation demo.")
    parser.add_argument("--difficulty", default="ok")
    parser.add_argument("--exercise_id", default="weighted_pullup")
    parser.add_argument("--rounding_step", type=float, default=0.5)
    args = parser.parse_args()

    user_state = load_json(REPO_ROOT / "data" / "user_state.json")
    baseline_load = pick_baseline_load(user_state, args.exercise_id)

    adjustments = user_state.get("adjustments") or {}
    per_exercise = adjustments.get("per_exercise") or {}
    state_before = per_exercise.get(args.exercise_id, {})
    multiplier_before = float(state_before.get("multiplier", 1.0))

    proposed_before = apply_multiplier(baseline_load, multiplier_before, args.rounding_step)

    outcome = {"difficulty": args.difficulty}
    update_user_state_adjustments(user_state, args.exercise_id, outcome)

    state_after = user_state.get("adjustments", {}).get("per_exercise", {}).get(args.exercise_id, {})
    multiplier_after = float(state_after.get("multiplier", 1.0))
    proposed_after = apply_multiplier(baseline_load, multiplier_after, args.rounding_step)

    print("exercise_id:", args.exercise_id)
    print("baseline_load_kg:", baseline_load)
    print("multiplier_before:", multiplier_before)
    print("proposed_load_before:", proposed_before)
    print("difficulty:", args.difficulty)
    print("multiplier_after:", multiplier_after)
    print("proposed_load_after:", proposed_after)


if __name__ == "__main__":
    main()
