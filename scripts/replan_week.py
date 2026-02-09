from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.replanner_v1 import apply_events  # noqa: E402


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_events_jsonl(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def _planning_prefs(user_state: Dict[str, Any]) -> Dict[str, Any]:
    prefs = dict(user_state.get("planning_prefs") or {})
    nested = ((user_state.get("planning") or {}).get("planning_prefs") or {})
    if "default_gym_id" not in prefs and isinstance(nested.get("default_gym_id"), str):
        prefs["default_gym_id"] = nested["default_gym_id"]
    return prefs


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic week replanning from event stream")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--event")
    parser.add_argument("--events")
    parser.add_argument("--user-state", default="data/user_state.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if bool(args.event) == bool(args.events):
        raise ValueError("Provide exactly one of --event or --events")

    plan_path = REPO_ROOT / args.plan if not Path(args.plan).is_absolute() else Path(args.plan)
    plan = _read_json(plan_path)

    if args.event:
        event_path = REPO_ROOT / args.event if not Path(args.event).is_absolute() else Path(args.event)
        events = [_read_json(event_path)]
    else:
        events_path = REPO_ROOT / args.events if not Path(args.events).is_absolute() else Path(args.events)
        events = _read_events_jsonl(events_path)

    user_state_path = REPO_ROOT / args.user_state if not Path(args.user_state).is_absolute() else Path(args.user_state)
    user_state = _read_json(user_state_path) if user_state_path.exists() else {}

    availability = user_state.get("availability") or {}
    planning_prefs = _planning_prefs(user_state)
    gyms = ((user_state.get("equipment") or {}).get("gyms") or [])

    updated = apply_events(plan, events, availability=availability, planning_prefs=planning_prefs, gyms=gyms)

    out_path = REPO_ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote replanned week: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
