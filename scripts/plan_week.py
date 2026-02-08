from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic 7-day plan (planner.v1)")
    parser.add_argument("--start-date", default=date.today().isoformat())
    parser.add_argument("--mode", default="balanced", choices=["balanced", "strength", "endurance", "maintenance"])
    parser.add_argument("--out", default="out/plans/plan_week.json")
    args = parser.parse_args()

    plan = generate_week_plan(
        start_date=args.start_date,
        mode=args.mode,
        availability=DEFAULT_AVAILABILITY,
        allowed_locations=["home", "gym", "outdoor"],
    )

    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote plan: {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
