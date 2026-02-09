from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.planner_v1 import generate_week_plan  # noqa: E402


DEFAULT_AVAILABILITY = {
    "mon": {"evening": {"available": True, "locations": ["gym"]}},
    "tue": {"morning": {"available": True, "locations": ["home"]}},
    "wed": {"evening": {"available": True, "locations": ["gym"]}},
    "thu": {"lunch": {"available": True, "locations": ["home"]}},
    "fri": {"evening": {"available": True, "locations": ["gym"]}},
    "sat": {"morning": {"available": True, "locations": ["outdoor", "gym"]}},
    "sun": {"available": False},
}


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _planning_prefs(user_state: Dict[str, Any]) -> Dict[str, Any]:
    prefs = dict(user_state.get("planning_prefs") or {})
    nested = ((user_state.get("planning") or {}).get("planning_prefs") or {})
    if "default_gym_id" not in prefs and isinstance(nested.get("default_gym_id"), str):
        prefs["default_gym_id"] = nested["default_gym_id"]
    return prefs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic 7-day plan (planner.v1)")
    parser.add_argument("--start-date", default=date.today().isoformat())
    parser.add_argument("--mode", default="balanced", choices=["balanced", "strength", "endurance", "maintenance"])
    parser.add_argument("--out", default="out/plans/plan_week.json")
    parser.add_argument("--user-state", default="data/user_state.json")
    args = parser.parse_args()

    user_state_path = REPO_ROOT / args.user_state
    user_state: Optional[Dict[str, Any]] = None
    if user_state_path.exists():
        user_state = _read_json(user_state_path)

    availability = (user_state or {}).get("availability") or DEFAULT_AVAILABILITY
    planning_prefs = _planning_prefs(user_state or {})

    plan = generate_week_plan(
        start_date=args.start_date,
        mode=args.mode,
        availability=availability,
        allowed_locations=["home", "gym", "outdoor"],
        hard_cap_per_week=int(planning_prefs.get("hard_day_cap_per_week") or 3),
        planning_prefs=planning_prefs,
        default_gym_id=planning_prefs.get("default_gym_id"),
        gyms=((user_state or {}).get("equipment") or {}).get("gyms") or [],
    )

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        printable = out_path.relative_to(REPO_ROOT)
    except ValueError:
        printable = out_path
    print(f"Wrote plan: {printable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
