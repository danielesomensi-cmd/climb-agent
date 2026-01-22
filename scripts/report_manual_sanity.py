from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_OUT_DIR = REPO_ROOT / "out" / "manual_sanity"
EX_PATH = REPO_ROOT / "catalog" / "exercises" / "v1" / "exercises.json"


def norm(x: Any) -> str:
    return str(x).strip().lower()


def as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def norm_list(x: Any) -> List[str]:
    return [norm(v) for v in as_list(x) if norm(v)]


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def ensure_ex_list(ex_data: Any) -> List[Dict[str, Any]]:
    if isinstance(ex_data, list):
        return [x for x in ex_data if isinstance(x, dict)]
    if isinstance(ex_data, dict):
        for k in ("exercises", "items", "data"):
            v = ex_data.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    raise ValueError("Unsupported exercises catalog shape")


def load_exercises_by_id() -> Dict[str, Dict[str, Any]]:
    data = load_json(EX_PATH)
    items = ensure_ex_list(data)
    out: Dict[str, Dict[str, Any]] = {}
    for ex in items:
        ex_id = ex.get("exercise_id") or ex.get("id")
        if isinstance(ex_id, str) and ex_id:
            out[norm(ex_id)] = ex
    return out


EX_BY_ID = load_exercises_by_id()


def get_blocks(res: Any) -> List[Dict[str, Any]]:
    if isinstance(res, dict):
        rs = res.get("resolved_session")
        if isinstance(rs, dict) and isinstance(rs.get("blocks"), list):
            return [b for b in rs["blocks"] if isinstance(b, dict)]
        for k in ("blocks", "block_instances", "resolved_blocks", "block_results"):
            v = res.get(k)
            if isinstance(v, list):
                return [b for b in v if isinstance(b, dict)]
    return []


def block_id(b: Dict[str, Any]) -> str:
    for k in ("block_id", "id", "name", "key"):
        v = b.get(k)
        if isinstance(v, str) and v:
            return v
    return "<block>"


def selected_ids(b: Dict[str, Any]) -> List[str]:
    out: List[str] = []

    se = b.get("selected_exercises")
    if isinstance(se, list):
        for item in se:
            if isinstance(item, dict):
                ex_id = item.get("exercise_id") or item.get("id")
                if isinstance(ex_id, str) and ex_id:
                    out.append(ex_id)
            elif isinstance(item, str):
                out.append(item)
    elif isinstance(se, dict):
        ex_id = se.get("exercise_id") or se.get("id")
        if isinstance(ex_id, str) and ex_id:
            out.append(ex_id)

    for k in ("selected_exercise_id", "exercise_id"):
        v = b.get(k)
        if isinstance(v, str) and v:
            out.append(v)

    # unique preserve order
    seen = set()
    uniq: List[str] = []
    for x in out:
        nx = norm(x)
        if nx not in seen:
            seen.add(nx)
            uniq.append(x)
    return uniq


def p0_check(ex: Dict[str, Any], *, location: str, avail_eq: List[str], role_req: Any, dom_req: Any):
    loc = norm(location)
    avail = set(norm_list(avail_eq))

    loc_allowed = set(norm_list(ex.get("location_allowed")))
    req_eq = set(norm_list(ex.get("equipment_required")))
    roles = set(norm_list(ex.get("role"))) | set(norm_list(ex.get("roles")))
    doms = set(norm_list(ex.get("domain")))

    role_set = set(norm_list(role_req))
    dom_set = set(norm_list(dom_req))

    ok_loc = loc in loc_allowed
    ok_eq = (not req_eq) or req_eq.issubset(avail)

    ok_role = True
    if role_set:
        ok_role = not roles.isdisjoint(role_set)

    dom_intersection = None
    if dom_set:
        dom_intersection = not doms.isdisjoint(dom_set)

    return ok_loc, ok_eq, ok_role, dom_intersection, {
        "location_allowed": sorted(loc_allowed),
        "equipment_required": sorted(req_eq),
        "roles": sorted(roles),
        "domains": sorted(doms),
    }


def report_one(path: Path) -> int:
    res = load_json(path)

    ctx = res.get("context", {}) if isinstance(res, dict) else {}
    location = ctx.get("location") or ctx.get("current_location") or "<unknown>"
    avail_eq = ctx.get("available_equipment") or ctx.get("equipment_available") or ctx.get("equipment") or []

    blocks = get_blocks(res)

    print("\n" + "=" * 110)
    print("FILE:", path)
    print("resolution_status:", res.get("resolution_status"))
    print("session_instance_version:", res.get("session_instance_version"))
    print("location:", location)
    print("available_equipment:", avail_eq)
    print("blocks_found:", len(blocks))

    for i, b in enumerate(blocks, 1):
        bid = block_id(b)
        status = b.get("status")
        msg = b.get("message")
        ft = b.get("filter_trace", {}) if isinstance(b.get("filter_trace"), dict) else {}
        counts = ft.get("counts")
        dom_applied = ft.get("domain_filter_applied")
        p_stage = ft.get("p_stage")
        note = ft.get("note")

        role_req = b.get("module_role") if "module_role" in b else b.get("role")
        dom_req = b.get("domain")
        sids = selected_ids(b)

        print(f"\n  --- BLOCK {i}: {bid} ---")
        print("  type:", b.get("type"))
        print("  status:", status)
        if msg:
            print("  message:", msg)
        print("  selected_exercises:", sids)
        print("  filter_trace.p_stage:", p_stage)
        print("  filter_trace.counts:", counts)
        print("  filter_trace.domain_filter_applied:", dom_applied)
        if note:
            print("  filter_trace.note:", note)

        for sid in sids:
            ex = EX_BY_ID.get(norm(sid))
            if not ex:
                print("  !! NOT FOUND in exercises catalog:", sid)
                continue
            ok_loc, ok_eq, ok_role, dom_inter, det = p0_check(
                ex, location=location, avail_eq=avail_eq, role_req=role_req, dom_req=dom_req
            )
            print(f"  P0 check for {sid}: location_ok={ok_loc} equipment_ok={ok_eq} role_ok={ok_role} domain_intersection={dom_inter}")
            print("    ex.location_allowed:", det["location_allowed"])
            print("    ex.equipment_required:", det["equipment_required"])
            print("    ex.roles:", det["roles"])
            print("    ex.domains:", det["domains"])

    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default=str(DEFAULT_OUT_DIR), help="Directory containing *.out.json files")
    ap.add_argument("--only", default=None, help="Substring filter, e.g. 'gym_blocx' or 'home_no_hangboard'")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    files = sorted(out_dir.glob("*.out.json"))
    if args.only:
        files = [p for p in files if args.only in p.name]

    if not files:
        print("No .out.json files found in:", out_dir)
        return 2

    for p in files:
        report_one(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
