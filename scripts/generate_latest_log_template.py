from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

def latest_resolved(glob_pat: str) -> Path | None:
    paths = sorted(Path(".").glob(glob_pat), key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[0] if paths else None

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolved_glob", default="out/manual_sanity/*_[0-9]*.json")
    ap.add_argument("--out_dir", default="out/log_templates")
    ap.add_argument("--user_state_path", default="data/user_state.json")
    args = ap.parse_args()

    resolved = latest_resolved(args.resolved_glob)
    if not resolved:
        raise SystemExit(f"No resolved session found with glob: {args.resolved_glob}. Run scripts/run_baseline_session.py first.")

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out_dir) / f"template_{int(time.time())}.json"

    cmd = [
        sys.executable,
        "scripts/generate_log_template.py",
        "--resolved_session_path", str(resolved),
        "--user_state_path", args.user_state_path,
        "--out_path", str(out_path),
        "--overwrite",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        raise SystemExit(p.returncode)

    print(str(out_path))

if __name__ == "__main__":
    main()
