from __future__ import annotations
from pathlib import Path
import sys

REQUIRED = [
    "catalog/engine/resolve_session.py",
    "scripts/audit_vocabulary.py",
    "scripts/run_baseline_session.py",
    "scripts/append_session_log.py",
    "scripts/generate_log_template.py",
    "scripts/generate_latest_log_template.py",
    "scripts/ui_day_view_gradio.py",
    "data/schemas/session_log_entry.v1.json",
    "data/schemas/exercise_outcome.v1.json",
    "data/user_state.json",
    "config/session_under_test.json",
]

def main() -> int:
    missing = [p for p in REQUIRED if not Path(p).exists()]
    if missing:
        print("INTEGRITY FAIL: missing required files:")
        for m in missing:
            print(" -", m)
        print("\nFix: `git status -sb` then `git pull --ff-only` (or restore deleted files).")
        return 2
    print("INTEGRITY OK: all required files present.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
