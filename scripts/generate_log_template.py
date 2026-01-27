from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_user(user_state: Dict[str, Any]) -> Dict[str, Any]:
    u = user_state.get("user") or {}
    user_id = u.get("id") or u.get("user_id") or "unknown_user"
    name = u.get("preferred_name") or u.get("name") or None
    out = {"id": str(user_id), "name": name}
    # optional: carry BW for autofill total load downstream (append_session_log can use it)
    bw = user_state.get("bodyweight_kg")
    if isinstance(bw, (int, float)):
        out["bodyweight_kg"] = float(bw)
    return out


def build_outcomes(resolved: Dict[str, Any]) -> List[Dict[str, Any]]:
    eis = (
        resolved.get("resolved_session", {}).get("exercise_instances")
        or resolved.get("exercise_instances")
        or []
    )
    if not isinstance(eis, list) or not eis:
        raise SystemExit("Resolved session has no exercise_instances.")

    outs: List[Dict[str, Any]] = []
    for inst in eis:
        if not isinstance(inst, dict):
            continue
        ex_id = inst.get("exercise_id")
        if not ex_id:
            continue

        planned: Dict[str, Any] = {"prescription": inst.get("prescription")}
        if "suggested" in inst:
            planned["suggested"] = inst.get("suggested")

        outs.append(
            {
                "exercise_id": ex_id,
                "instance_id": inst.get("instance_id"),
                "block_uid": inst.get("block_uid"),
                "planned": planned,
                "actual": {"status": "planned"},
            }
        )

    if not outs:
        raise SystemExit("No outcomes built from exercise_instances.")
    return outs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolved_session_path", required=True)
    ap.add_argument("--user_state_path", default="data/user_state.json")
    ap.add_argument("--out_path", required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    resolved_path = Path(args.resolved_session_path)
    user_state_path = Path(args.user_state_path)
    out_path = Path(args.out_path)

    if out_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing file: {out_path} (use --overwrite)")

    resolved = load_json(resolved_path)
    user_state = load_json(user_state_path)

    session = resolved.get("session") or {}
    session_id = session.get("session_id") or session.get("id") or "unknown_session"

    entry: Dict[str, Any] = {
        "schema_version": "session_log_entry.v1",
        "created_at": now_iso(),
        "logged_at": now_iso(),
        "user": pick_user(user_state),
        "session_id": str(session_id),
        "session": session,
        "context": resolved.get("context") or {},
        "exercise_outcomes": build_outcomes(resolved),
        "source": {
            "resolved_session_path": str(resolved_path),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
