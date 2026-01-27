from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List, Tuple

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out

def pick_log_path() -> Path:
    # prefer canonical if present
    p1 = Path("data/logs/sessions_2026.jsonl")
    p2 = Path("data/logs/session_logs.jsonl")
    return p1 if p1.exists() else p2

def status_counts(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    c = {"planned": 0, "done": 0, "skipped": 0, "modified": 0, "unknown": 0}
    for e in entries:
        outs = e.get("exercise_outcomes")
        if not isinstance(outs, list):
            continue
        for o in outs:
            if not isinstance(o, dict):
                continue
            a = o.get("actual") or {}
            st = a.get("status", "planned")
            if st not in c:
                c["unknown"] += 1
            else:
                c[st] += 1
    return c

def max_hang_trend(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pts = []
    for e in entries:
        logged_at = e.get("logged_at") or e.get("logged_date") or ""
        outs = e.get("exercise_outcomes")
        if not isinstance(outs, list):
            continue
        for o in outs:
            if not isinstance(o, dict):
                continue
            if o.get("exercise_id") != "max_hang_5s":
                continue
            a = o.get("actual") or {}
            st = a.get("status", "planned")
            total = a.get("used_total_load_kg")
            if st == "done" and isinstance(total, (int, float)):
                pts.append({"logged_at": logged_at, "used_total_load_kg": float(total)})
    return pts[-50:]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log_path", default=None)
    ap.add_argument("--last_n", type=int, default=50)
    args = ap.parse_args()

    log_path = Path(args.log_path) if args.log_path else pick_log_path()
    entries = read_jsonl(log_path)[-args.last_n:]

    out = {
        "log_path": str(log_path),
        "entries_considered": len(entries),
        "status_counts": status_counts(entries),
        "max_hang_5s_trend": max_hang_trend(entries),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
