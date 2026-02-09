from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from typing import Any, Dict

from catalog.engine.closed_loop_v1 import (
    append_jsonl,
    apply_day_result_to_user_state,
    build_log_entry,
    canonical_sessions_log_path,
    ensure_planning_defaults,
    load_user_state,
    save_user_state,
)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Log resolved day and update user state deterministically")
    parser.add_argument("--resolved", required=True)
    parser.add_argument("--status", required=True, choices=["done", "skipped"])
    parser.add_argument("--notes", default="")
    parser.add_argument("--outcome-json", default=None)
    parser.add_argument("--user-state", default="data/user_state.json")
    args = parser.parse_args()

    resolved_path = Path(args.resolved)
    resolved_day = _read_json(resolved_path)
    outcomes: Dict[str, Any] = json.loads(args.outcome_json) if args.outcome_json else {}

    user_state_path = Path(args.user_state)
    state = ensure_planning_defaults(load_user_state(user_state_path))

    log_entry = build_log_entry(resolved_day=resolved_day, status=args.status, notes=args.notes, outcomes=outcomes)
    log_path = canonical_sessions_log_path(state)
    append_jsonl(log_path, log_entry)

    updated = apply_day_result_to_user_state(state, resolved_day=resolved_day, status=args.status)
    save_user_state(user_state_path, updated)

    print(f"Appended log: {log_path}")
    print(f"Updated user state: {user_state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
