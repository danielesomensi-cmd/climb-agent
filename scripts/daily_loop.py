from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.daily_loop import apply_day_feedback, preview_day


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic daily loop: preview day and apply feedback")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_preview = sub.add_parser("preview", help="Resolve planned day and inject deterministic working targets")
    p_preview.add_argument("--plan", required=True)
    p_preview.add_argument("--date", required=True)
    p_preview.add_argument("--user-state", required=True)
    p_preview.add_argument("--out", required=True)

    p_apply = sub.add_parser("apply", help="Apply exercise feedback, append closed_loop.v1 log, and update user state")
    p_apply.add_argument("--resolved", required=True)
    p_apply.add_argument("--feedback", required=True)
    p_apply.add_argument("--user-state", required=True)
    p_apply.add_argument("--log", required=True)
    p_apply.add_argument("--out-user-state", default=None)

    args = parser.parse_args()

    if args.cmd == "preview":
        out = preview_day(plan_path=args.plan, date=args.date, user_state_path=args.user_state, out_path=args.out)
        print(json.dumps({"resolved_ref": out.get("resolved_ref"), "sessions": len(out.get("sessions") or [])}, ensure_ascii=False, sort_keys=True))
        return 0

    result = apply_day_feedback(
        resolved_day_path=args.resolved,
        feedback_json_path=args.feedback,
        user_state_path=args.user_state,
        log_path=args.log,
        out_user_state_path=args.out_user_state,
    )
    print(json.dumps({"date": result["log_entry"].get("date"), "status": result["log_entry"].get("status")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
