import json, os
from copy import deepcopy

REPO_ROOT = "/content/climb-agent"

def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

from catalog.engine.resolve_session import resolve_session

BASE_USER = load_json(os.path.join(REPO_ROOT, "data/user_state.json"))

def make_user_state(*, location, gym_id=None, home_equipment=None):
    us = deepcopy(BASE_USER)
    us.setdefault("context", {})
    us["context"]["location"] = location
    us["context"]["gym_id"] = gym_id
    if home_equipment is not None:
        us.setdefault("equipment", {})
        us["equipment"]["home"] = home_equipment
    return us

def make_session(*, sid, location, gym_id=None):
    return {
        "id": sid,
        "version": "1.0",
        "context": {"location": location, "gym_id": gym_id},
        "modules": [
            {"template_id": "finger_max_strength", "version": "v1", "required": True},
        ],
    }

def print_block(b):
    uid = b.get("block_uid")
    status = b.get("status")
    msg = b.get("message")
    sel = b.get("selected_exercises") or []
    print(f"- {uid} | {status} | selected={len(sel)} | msg={msg}")
    tr = b.get("p0_trace")
    if tr:
        print("  p0_trace:", tr)

def run_case(name, us, sess):
    rel_session_path = os.path.join("out", "manual_sanity", f"__session__{name}.json")
    abs_session_path = os.path.join(REPO_ROOT, rel_session_path)
    write_json(abs_session_path, sess)

    out = resolve_session(
        repo_root=REPO_ROOT,
        session_path=rel_session_path,
        templates_dir="catalog/templates",
        exercises_path="catalog/exercises/v1/exercises.json",
        out_path=os.path.join("out", "manual_sanity", f"{name}.out.json"),
        user_state_override=us,
        write_output=True,
    )

    print(f"\n=== {name} ===")
    print("resolution_status:", out.get("resolution_status"))
    ctx = out.get("context", {}) or {}
    print("context.location:", ctx.get("location"))
    print("context.gym_id:", ctx.get("gym_id"))
    print("context.available_equipment:", ctx.get("available_equipment"))

    blocks = out.get("resolved_session", {}).get("blocks", []) or []
    print("blocks:", len(blocks))
    for b in blocks:
        print_block(b)

if __name__ == "__main__":
    # 1) home NO hangboard
    us1 = make_user_state(location="home", gym_id=None, home_equipment=["pullup_bar", "band", "weight"])
    s1 = make_session(sid="finger_home_no_hb", location="home")
    run_case("home_no_hangboard", us1, s1)

    # 2) home WITH hangboard (default from user_state)
    us2 = make_user_state(location="home", gym_id=None)
    s2 = make_session(sid="finger_home_hb", location="home")
    run_case("home_hangboard", us2, s2)

    # 3) gym Blocx
    us3 = make_user_state(location="gym", gym_id="Blocx")
    s3 = make_session(sid="finger_gym_blocx", location="gym", gym_id="Blocx")
    run_case("gym_blocx", us3, s3)
