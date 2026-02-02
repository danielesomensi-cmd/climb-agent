from __future__ import annotations

import argparse
import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.adaptation.closed_loop import (  # noqa: E402
    apply_multiplier,
    update_user_state_adjustments,
)
from catalog.engine.resolve_session import (  # noqa: E402
    ensure_exercise_list,
    get_ex_id,
    load_json,
    load_user_state,
    resolve_session,
)

DIFFICULTIES = ("too_easy", "easy", "ok", "hard", "too_hard", "fail")
DEFAULT_BASELINE_KG = 20.0


def load_user_state_data(repo_root: Path, user_state_path: Optional[Path]) -> Dict[str, Any]:
    if user_state_path is not None:
        return load_json(str(user_state_path))
    user_state = load_user_state(str(repo_root))
    if user_state is None:
        raise SystemExit("No user_state.json found. Provide --user_state.")
    return user_state


def pick_baseline_for_exercise(user_state: Dict[str, Any], exercise_id: str) -> Dict[str, Any]:
    tests = (user_state.get("tests") or {}).get("max_strength") or []
    for test in tests:
        if test.get("exercise_id") != exercise_id:
            continue
        if test.get("external_load_kg") is not None:
            return {
                "exercise_id": exercise_id,
                "load_kg": float(test["external_load_kg"]),
                "source": "tests.max_strength.external_load_kg",
                "test_id": test.get("test_id"),
                "date": test.get("date"),
            }
        if test.get("total_load_kg") is not None:
            return {
                "exercise_id": exercise_id,
                "load_kg": float(test["total_load_kg"]),
                "source": "tests.max_strength.total_load_kg",
                "test_id": test.get("test_id"),
                "date": test.get("date"),
            }

    baselines = (user_state.get("baselines") or {}).get("hangboard") or []
    if exercise_id == "max_hang_5s" and baselines:
        baseline = baselines[0]
        if baseline.get("max_total_load_kg") is not None:
            return {
                "exercise_id": exercise_id,
                "load_kg": float(baseline["max_total_load_kg"]),
                "source": "baselines.hangboard.max_total_load_kg",
                "baseline_id": baseline.get("baseline_id"),
                "edge_mm": baseline.get("edge_mm"),
                "grip": baseline.get("grip"),
                "hang_seconds": baseline.get("hang_seconds"),
                "date": baseline.get("last_tested_date"),
            }

    return {
        "exercise_id": exercise_id,
        "load_kg": DEFAULT_BASELINE_KG,
        "source": "default",
    }


def get_adjustment_state(user_state: Dict[str, Any], exercise_id: str) -> Dict[str, Any]:
    adjustments = user_state.get("adjustments") or {}
    per_exercise = adjustments.get("per_exercise") or {}
    state = per_exercise.get(exercise_id, {})
    return {
        "multiplier": float(state.get("multiplier", 1.0)),
        "streak": int(state.get("streak", 0)),
    }


def resolve_prescription_defaults(
    *,
    repo_root: Path,
    exercise_id: str,
    exercises_path: Optional[Path],
    user_state: Dict[str, Any],
) -> Dict[str, Any]:
    exercises_file = exercises_path or repo_root / "catalog" / "exercises" / "v1" / "exercises.json"
    exercises_raw = load_json(str(exercises_file))
    exercises = ensure_exercise_list(exercises_raw)

    if not any(get_ex_id(ex) == exercise_id for ex in exercises):
        exercises = exercises + [{"id": exercise_id, "name": exercise_id, "prescription_defaults": {}}]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates" / "v1"
        template_dir.mkdir(parents=True, exist_ok=True)

        template_id = "closed_loop_trace"
        template = {
            "template_id": template_id,
            "blocks": [
                {
                    "block_id": "main",
                    "type": "main",
                    "exercise_id": exercise_id,
                    "prescription": {},
                }
            ],
        }
        template_path = template_dir / f"{template_id}.json"
        template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")

        session = {
            "session_id": "closed_loop_trace",
            "modules": [{"template_id": template_id, "version": "v1"}],
            "context": {},
        }
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

        exercises_path_tmp = tmp_path / "exercises.json"
        exercises_path_tmp.write_text(
            json.dumps({"exercises": exercises}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        resolved = resolve_session(
            repo_root=str(tmp_path),
            session_path=str(session_path),
            templates_dir=str(tmp_path / "templates"),
            exercises_path=str(exercises_path_tmp),
            out_path=str(tmp_path / "output.json"),
            user_state_override=user_state,
            write_output=False,
        )

    instances = resolved.get("resolved_session", {}).get("exercise_instances", [])
    for instance in instances:
        if instance.get("exercise_id") == exercise_id:
            return instance.get("prescription") or {}
    return {}


def merge_prescription(
    base_prescription: Dict[str, Any],
    baseline_load_kg: float,
    multiplier: float,
    rounding_step: float,
) -> Dict[str, Any]:
    merged = dict(base_prescription)
    merged["load_kg"] = apply_multiplier(baseline_load_kg, multiplier, rounding_step)
    return merged


def render_json_block(data: Dict[str, Any]) -> str:
    return "\n".join([
        "```json",
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
    ])


def build_report(
    *,
    date: str,
    exercise_id: str,
    feedback: str,
    baseline: Dict[str, Any],
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
    prescription_before: Dict[str, Any],
    prescription_after: Dict[str, Any],
    rounding_step: float,
) -> str:
    lines = [
        "# Closed-loop trace",
        "",
        "## Run metadata",
        f"- date: {date}",
        f"- exercise_id: {exercise_id}",
        f"- feedback: {feedback}",
        f"- rounding_step_kg: {rounding_step}",
        "",
        "## INPUT",
        "### baseline",
        render_json_block(baseline),
        f"- multiplier: {state_before['multiplier']}",
        f"- streak: {state_before['streak']}",
        "",
        "### prescription_before",
        render_json_block(prescription_before),
        "",
        "## FEEDBACK",
        f"- difficulty: {feedback}",
        "",
        "## OUTPUT",
        f"- multiplier_before: {state_before['multiplier']}",
        f"- multiplier_after: {state_after['multiplier']}",
        f"- streak_before: {state_before['streak']}",
        f"- streak_after: {state_after['streak']}",
        "",
        "### prescription_after",
        render_json_block(prescription_after),
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Closed-loop trace report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--exercise_id", default="weighted_pullup")
    parser.add_argument("--feedback", choices=DIFFICULTIES, required=True)
    parser.add_argument("--rounding_step", type=float, default=0.5)
    parser.add_argument("--user_state", type=Path)
    parser.add_argument("--exercises_path", type=Path)
    parser.add_argument(
        "--output_path",
        type=Path,
        default=REPO_ROOT / "out" / "closed_loop_trace_latest.md",
    )
    args = parser.parse_args()

    user_state = load_user_state_data(REPO_ROOT, args.user_state)

    baseline = pick_baseline_for_exercise(user_state, args.exercise_id)
    state_before = get_adjustment_state(user_state, args.exercise_id)

    prescription_defaults = resolve_prescription_defaults(
        repo_root=REPO_ROOT,
        exercise_id=args.exercise_id,
        exercises_path=args.exercises_path,
        user_state=user_state,
    )

    prescription_before = merge_prescription(
        prescription_defaults,
        baseline_load_kg=baseline["load_kg"],
        multiplier=state_before["multiplier"],
        rounding_step=args.rounding_step,
    )

    user_state_after = deepcopy(user_state)
    update_user_state_adjustments(user_state_after, args.exercise_id, {"difficulty": args.feedback})
    state_after = get_adjustment_state(user_state_after, args.exercise_id)

    prescription_after = merge_prescription(
        prescription_defaults,
        baseline_load_kg=baseline["load_kg"],
        multiplier=state_after["multiplier"],
        rounding_step=args.rounding_step,
    )

    report = build_report(
        date=args.date,
        exercise_id=args.exercise_id,
        feedback=args.feedback,
        baseline=baseline,
        state_before=state_before,
        state_after=state_after,
        prescription_before=prescription_before,
        prescription_after=prescription_after,
        rounding_step=args.rounding_step,
    )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(report, encoding="utf-8")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
