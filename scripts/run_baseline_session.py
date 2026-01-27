from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
import os
import sys

# repo_root = parent of scripts/
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog.engine.resolve_session import resolve_session  # noqa: E402

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    cfg = load_json(REPO_ROOT / "config" / "session_under_test.json")
    base_session_path = cfg["session_path"]  # e.g. catalog/sessions/v1/strength_long.json
    base_session = load_json(REPO_ROOT / base_session_path)

    base_us = load_json(REPO_ROOT / "data" / "user_state.json")

    scenarios = [
        ("home_hangboard", {"location": "home", "gym_id": None}),
        ("gym_blocx", {"location": "gym", "gym_id": "blocx"}),
    ]

    out_manual = REPO_ROOT / "out" / "manual_sanity"
    out_tmp_sessions = REPO_ROOT / "out" / "tmp_sessions"
    out_manual.mkdir(parents=True, exist_ok=True)
    out_tmp_sessions.mkdir(parents=True, exist_ok=True)

    for name, ctx in scenarios:
        # IMPORTANT: resolver location comes from SESSION context, not user_state context.
        sess = deepcopy(base_session)
        sess.setdefault("context", {})
        sess["context"]["location"] = ctx["location"]
        sess["context"]["gym_id"] = ctx["gym_id"]

        tmp_session_rel = f"out/tmp_sessions/session_under_test__{name}.json"
        write_json(REPO_ROOT / tmp_session_rel, sess)

        out_rel = f"out/manual_sanity/{name}_{int(time.time())}.json"

        out = resolve_session(
            repo_root=str(REPO_ROOT),
            session_path=tmp_session_rel,  # scenario-specific session
            templates_dir="catalog/templates",
            exercises_path="catalog/exercises/v1/exercises.json",
            out_path=out_rel,
            user_state_override=base_us,
            write_output=True,
        )

        print(f"\n== {name} ==")
        print("resolution_status:", out.get("resolution_status"))
        print("base_session_path:", base_session_path)
        print("scenario_session_path:", tmp_session_rel)
        print("context.location:", out.get("context", {}).get("location"))
        print("context.gym_id:", out.get("context", {}).get("gym_id"))
        print("exercise_instances:", len(out.get("resolved_session", {}).get("exercise_instances", [])))

if __name__ == "__main__":
    main()
