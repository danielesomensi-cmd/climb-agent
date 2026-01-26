import json
import time
from copy import deepcopy
from pathlib import Path

# --- bootstrap repo root on sys.path ---
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# --- end bootstrap ---

from catalog.engine.resolve_session import resolve_session

REPO_ROOT = "/content/climb-agent"

def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def main():
    cfg = load_json(f"{REPO_ROOT}/config/session_under_test.json")
    session_path = cfg["session_path"]
    base_us = load_json(f"{REPO_ROOT}/data/user_state.json")

    scenarios = [
        ("home_hangboard", {"location": "home", "gym_id": None}),
        ("gym_blocx", {"location": "gym", "gym_id": "blocx"}),
    ]

    Path(f"{REPO_ROOT}/out/manual_sanity").mkdir(parents=True, exist_ok=True)

    for name, ctx in scenarios:
        us = deepcopy(base_us)
        us.setdefault("context", {})
        us["context"]["location"] = ctx["location"]
        us["context"]["gym_id"] = ctx["gym_id"]

        out_rel = f"out/manual_sanity/{name}_{int(time.time())}.json"
        out = resolve_session(
            repo_root=REPO_ROOT,
            session_path=session_path,
            templates_dir="catalog/templates",
            exercises_path="catalog/exercises/v1/exercises.json",
            out_path=out_rel,
            user_state_override=us,
            write_output=True,
        )

        print(f"\n== {name} ==")
        print("resolution_status:", out.get("resolution_status"))
        print("session_path:", session_path)
        print("location:", out.get("context", {}).get("location"))
        print("gym_id:", out.get("context", {}).get("gym_id"))
        print("exercise_instances:", len(out["resolved_session"].get("exercise_instances", [])))

        for b in out["resolved_session"]["blocks"]:
            uid = b.get("block_uid", "")
            if ("finger_max_strength" in uid) or ("core_short" in uid) or ("general_warmup" in uid):
                ex_ids = [x.get("exercise_id") for x in (b.get("selected_exercises") or [])]
                ft = b.get("filter_trace")
                print(f" - {uid:40s} status={b.get('status'):8s} ex={ex_ids}")
                if ft is not None:
                    print(f"   filter_trace={ft}")

if __name__ == "__main__":
    main()
