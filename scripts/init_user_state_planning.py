from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from catalog.engine.closed_loop_v1 import ensure_planning_defaults, load_user_state, save_user_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize user_state planning defaults (schema 1.4, work_gym, prefs, availability)")
    parser.add_argument("--user-state", default="data/user_state.json")
    args = parser.parse_args()

    user_state_path = Path(args.user_state)
    state = load_user_state(user_state_path)
    updated = ensure_planning_defaults(state)
    save_user_state(user_state_path, updated)
    print(f"Updated {user_state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
