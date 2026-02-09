from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.resolve_session import resolve_session


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _find_day(plan: Dict[str, Any], date_value: str) -> Dict[str, Any]:
    for week in plan.get("weeks") or []:
        for day in week.get("days") or []:
            if day.get("date") == date_value:
                return day
    raise ValueError(f"No day found for date={date_value}")


def _session_file(session_id: str) -> Path:
    return Path("catalog/sessions/v1") / f"{session_id}.json"


def _resolve_single(session_entry: Dict[str, Any], date_value: str) -> Dict[str, Any]:
    sid = session_entry["session_id"]
    source = REPO_ROOT / _session_file(sid)
    if not source.exists():
        raise FileNotFoundError(f"Session file missing for session_id={sid}: {source}")

    payload = _read_json(source)
    context = payload.setdefault("context", {})
    context["location"] = session_entry.get("location")
    context["gym_id"] = session_entry.get("gym_id")
    context["target_date"] = date_value

    (REPO_ROOT / "out").mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=REPO_ROOT / "out", delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        temp_name = Path(fh.name).relative_to(REPO_ROOT)

    try:
        resolved = resolve_session(
            repo_root=str(REPO_ROOT),
            session_path=str(temp_name),
            templates_dir="catalog/templates",
            exercises_path="catalog/exercises/v1/exercises.json",
            out_path="out/tmp/ignore.json",
            write_output=False,
        )
    finally:
        (REPO_ROOT / temp_name).unlink(missing_ok=True)

    return {
        "session_id": sid,
        "slot": session_entry.get("slot"),
        "intent": session_entry.get("intent"),
        "priority": session_entry.get("priority"),
        "location": session_entry.get("location"),
        "gym_id": session_entry.get("gym_id"),
        "tags": session_entry.get("tags") or {},
        "plan_constraints": session_entry.get("constraints_applied") or [],
        "plan_explain": session_entry.get("explain") or [],
        "session_source_path": str(_session_file(sid)),
        "resolver_trace": {
            "selected_modules": [m.get("template_id") for m in (resolved.get("resolved_session") or {}).get("modules") or []],
            "constraints_influencing_selection": sorted(set((session_entry.get("constraints_applied") or []) + ["resolver_p0_hard_filters"])),
        },
        "resolved_blocks": (resolved.get("resolved_session") or {}).get("blocks") or [],
        "exercise_instances": (resolved.get("resolved_session") or {}).get("exercise_instances") or [],
        "resolution_status": resolved.get("resolution_status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a planned day from planner_v1 output")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    plan_path = Path(args.plan)
    plan = _read_json(plan_path)
    day = _find_day(plan, args.date)

    plan_name = plan_path.stem
    out_path = Path(args.out) if args.out else Path("out/plans") / f"{plan_name}__{args.date}__resolved.json"

    sessions: List[Dict[str, Any]] = [_resolve_single(s, args.date) for s in day.get("sessions") or []]
    artifact = {
        "resolved_day_version": "1.0",
        "resolved_ref": f"{plan_name}__{args.date}__resolved.json",
        "date": args.date,
        "plan": {
            "plan_version": plan.get("plan_version"),
            "start_date": plan.get("start_date"),
            "profile_snapshot": plan.get("profile_snapshot") or {},
        },
        "day": {
            "weekday": day.get("weekday"),
            "source": str(plan_path),
        },
        "sessions": sessions,
        "summary": {
            "planned_session_count": len(day.get("sessions") or []),
            "resolved_session_count": len(sessions),
        },
    }

    _write_json(out_path, artifact)
    print(f"Wrote resolved day: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
