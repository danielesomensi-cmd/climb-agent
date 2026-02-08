from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.replanner_v1 import apply_day_override  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic day override to planner.v1 output")
    parser.add_argument("--plan", default="out/plans/plan_week.json")
    parser.add_argument("--intent", default="recovery")
    parser.add_argument("--location", default="home")
    parser.add_argument("--reference-date", default=date.today().isoformat())
    parser.add_argument("--out", default="out/plans/plan_week_override.json")
    args = parser.parse_args()

    plan_path = REPO_ROOT / args.plan
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    updated = apply_day_override(
        plan,
        intent=args.intent,
        location=args.location,
        reference_date=args.reference_date,
    )

    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote override plan: {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
