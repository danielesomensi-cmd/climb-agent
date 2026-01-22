from __future__ import annotations

import sys
import json
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Colab-friendly: ensure repo root importable
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Stable templates (baseline)
TEMPLATE_FINGER = "catalog/templates/v1/finger_max_strength.json"
TEMPLATE_WARMUP = "catalog/templates/v1/general_warmup.json"
TEMPLATE_CORE   = "catalog/templates/v1/core_short.json"


def _read_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def load_json(rel_path: str) -> Any:
    p = REPO_ROOT / rel_path
    if not p.exists():
        raise FileNotFoundError(f"Missing JSON file: {p}")
    return _read_json(p)


def looks_like_ex_catalog(data: Any) -> bool:
    # dict with "exercises": [...]
    if isinstance(data, dict) and isinstance(data.get("exercises"), list) and len(data["exercises"]) > 0:
        return True
    # list of dict exercises
    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data[:5]) and "id" in data[0]:
        return True
    return False


def score_ex_catalog(path: Path, data: Any) -> int:
    s = 0
    name = path.name.lower()
    rel = str(path).lower()
    if "exercises" in name: s += 100
    if "exercise" in name: s += 60
    if "catalog" in rel: s += 10
    if isinstance(data, dict) and isinstance(data.get("exercises"), list):
        s += 80
        # bonus if exercise items look like your schema
        ex0 = data["exercises"][0] if data["exercises"] else {}
        if isinstance(ex0, dict):
            if "equipment_required" in ex0: s += 10
            if "location_allowed" in ex0: s += 10
            if "role" in ex0: s += 5
            if "domain" in ex0: s += 5
    if isinstance(data, list):
        s += 60
        ex0 = data[0] if data else {}
        if isinstance(ex0, dict):
            if "equipment_required" in ex0: s += 10
            if "location_allowed" in ex0: s += 10
            if "role" in ex0: s += 5
            if "domain" in ex0: s += 5
    return s


def find_exercises_catalog() -> Path:
    """
    Deterministic autodetect:
    1) try a small set of known conventional paths
    2) else scan catalog/**/*.json and pick best scored candidate
    """
    preferred = [
        REPO_ROOT / "catalog" / "exercises.json",
        REPO_ROOT / "catalog" / "exercises_v1.json",
        REPO_ROOT / "catalog" / "data" / "exercises.json",
        REPO_ROOT / "catalog" / "exercises" / "exercises.json",
        REPO_ROOT / "catalog" / "exercises" / "v1" / "exercises.json",
    ]

    best: Optional[Tuple[int, str, Path]] = None

    def consider(p: Path):
        nonlocal best
        if not p.exists():
            return
        try:
            data = _read_json(p)
        except Exception:
            return
        if not looks_like_ex_catalog(data):
            return
        sc = score_ex_catalog(p, data)
        key = (sc, str(p.relative_to(REPO_ROOT)))  # deterministic tie-break
        cand = (key[0], key[1], p)
        if best is None or cand[:2] > best[:2]:
            best = cand

    for p in preferred:
        consider(p)

    if best is None:
        # full scan (still fast; catalog is small)
        for p in (REPO_ROOT / "catalog").rglob("*.json"):
            consider(p)

    if best is None:
        raise RuntimeError(
            "Could not find an exercises catalog JSON in catalog/**/*.json.\n"
            "Expected a JSON with top-level {'exercises': [...]} or a list of exercise dicts.\n"
        )

    return best[2]


def extract_blocks(result: Any) -> List[Dict[str, Any]]:
    if isinstance(result, dict):
        for k in ("blocks", "block_instances", "resolved_blocks", "block_results"):
            v = result.get(k)
            if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                return v
    return []


def short_block_id(block: Dict[str, Any]) -> str:
    for k in ("block_id", "id", "name", "key"):
        v = block.get(k)
        if isinstance(v, str) and v:
            return v
    return "<block>"


def selected_exercise_id(block: Dict[str, Any]) -> Optional[str]:
    for k in ("exercise_instance", "selected_exercise", "exercise", "selection", "result"):
        v = block.get(k)
        if isinstance(v, dict):
            for idk in ("exercise_id", "id", "selected_exercise_id"):
                if isinstance(v.get(idk), str):
                    return v[idk]
    for idk in ("exercise_id", "selected_exercise_id"):
        if isinstance(block.get(idk), str):
            return block[idk]
    return None


def mk_context(location: str, equipment: List[str]) -> Dict[str, Any]:
    eq = list(equipment)
    return {
        "location": location,
        "current_location": location,
        "equipment_available": eq,
        "available_equipment": eq,
        "equipment": eq,
    }


def call_resolver(session_template: Any, context: Dict[str, Any], out_path: Path) -> Any:
    import importlib
    mod = importlib.import_module("catalog.engine.resolve_session")

    if not hasattr(mod, "resolve_session") or not callable(mod.resolve_session):
        raise RuntimeError("catalog.engine.resolve_session.resolve_session() not found")

    templates_dir = REPO_ROOT / "catalog" / "templates" / "v1"
    if not templates_dir.exists():
        raise RuntimeError(f"templates_dir not found: {templates_dir}")

    exercises_path = find_exercises_catalog()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Print once, but only if running from main (we print in main too)
    return mod.resolve_session(
        session_template,
        context,
        str(templates_dir),
        str(exercises_path),
        str(out_path),
    )


@dataclass
class Scenario:
    name: str
    template_path: str
    context: Dict[str, Any]


def run_one(sc: Scenario, out_dir: Path) -> None:
    tpl = load_json(sc.template_path)
    out_path = out_dir / f"{sc.name}.json"
    res = call_resolver(tpl, sc.context, out_path=out_path)

    out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    blocks = extract_blocks(res)
    print(f"\n================ SCENARIO: {sc.name} ================")
    print(f"template: {sc.template_path}")
    print(f"context: {json.dumps(sc.context, ensure_ascii=False)}")
    if isinstance(res, dict):
        print(f"resolution_status={res.get('resolution_status')}  session_instance_version={res.get('session_instance_version')}")
    print(f"blocks_found={len(blocks)}  json={out_path}")

    for b in blocks:
        bid = short_block_id(b)
        status = b.get("status")
        msg = b.get("message")
        sel = selected_exercise_id(b)

        ft = b.get("filter_trace", {}) if isinstance(b.get("filter_trace"), dict) else {}
        print(f"\n- BLOCK {bid}")
        print(f"  status={status}  selected_exercise_id={sel}")
        if msg:
            print(f"  message={msg}")
        print(f"  filter_trace.p_stage={ft.get('p_stage')}")
        print(f"  filter_trace.counts={ft.get('counts')}")
        print(f"  filter_trace.domain_filter_applied={ft.get('domain_filter_applied')}")
        if ft.get("note"):
            print(f"  filter_trace.note={ft.get('note')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", default="out/manual_scenarios", help="Output directory for JSON dumps")
    args = ap.parse_args()

    out_dir = REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve exercises catalog once and print it (for transparency)
    ex_path = find_exercises_catalog()
    print("=== Using exercises catalog ===")
    print(str(ex_path.relative_to(REPO_ROOT)))

    # Stable equipment sets (must match vocabulary)
    EQ_HOME_NO_HB = ["band", "dumbbell", "pullup_bar"]
    EQ_HOME_WITH_HB = ["band", "dumbbell", "pullup_bar", "hangboard"]
    EQ_GYM_MIN = ["dumbbell", "hangboard"]
    EQ_OUTDOOR = []  # intentionally empty

    scenarios: List[Scenario] = [
        Scenario("finger_home_no_hangboard", TEMPLATE_FINGER, mk_context("home", EQ_HOME_NO_HB)),
        Scenario("finger_home_with_hangboard", TEMPLATE_FINGER, mk_context("home", EQ_HOME_WITH_HB)),
        Scenario("finger_gym_min", TEMPLATE_FINGER, mk_context("gym", EQ_GYM_MIN)),
        Scenario("performance_outdoor_warmup", TEMPLATE_WARMUP, mk_context("outdoor", EQ_OUTDOOR)),
        Scenario("performance_outdoor_core", TEMPLATE_CORE, mk_context("outdoor", EQ_OUTDOOR)),
    ]

    for sc in scenarios:
        run_one(sc, out_dir)

    print("\nDONE. Full outputs in:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
