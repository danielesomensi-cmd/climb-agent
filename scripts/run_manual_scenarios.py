from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _load_json(p: Path) -> Any:
    return json.loads(_read_text(p))


def _safe_load_json(p: Path) -> Optional[Any]:
    try:
        return _load_json(p)
    except Exception:
        return None


def _is_session_like(data: Any) -> bool:
    # Heuristics: session templates usually have blocks or modules/steps
    if not isinstance(data, dict):
        return False
    if "blocks" in data and isinstance(data["blocks"], list):
        return True
    # sometimes "session" templates hold modules in another key
    for k in ("session", "session_template", "modules", "steps"):
        if k in data and isinstance(data.get(k), (list, dict)):
            return True
    return False


def discover_session_candidates() -> List[Tuple[str, str]]:
    # returns list of (path, id_or_name)
    candidates: List[Tuple[str, str]] = []
    for p in REPO_ROOT.joinpath("catalog").rglob("*.json"):
        data = _safe_load_json(p)
        if _is_session_like(data):
            sid = ""
            if isinstance(data, dict):
                sid = str(data.get("id") or data.get("name") or "")
            candidates.append((str(p.relative_to(REPO_ROOT)), sid))
    return candidates


def discover_exercise_catalog_files() -> List[Path]:
    files: List[Path] = []
    for p in REPO_ROOT.joinpath("catalog").rglob("*.json"):
        data = _safe_load_json(p)
        if isinstance(data, dict) and "exercises" in data and isinstance(data["exercises"], list):
            files.append(p)
    return files


def discover_vocab_from_exercises() -> Dict[str, List[str]]:
    locations, equipments, roles, domains = set(), set(), set(), set()
    for f in discover_exercise_catalog_files():
        data = _load_json(f)
        for ex in data.get("exercises", []):
            if not isinstance(ex, dict):
                continue
            loc = ex.get("location_allowed")
            if isinstance(loc, list):
                for x in loc:
                    if isinstance(x, str):
                        locations.add(x)
            eq = ex.get("equipment_required")
            if isinstance(eq, list):
                for x in eq:
                    if isinstance(x, str):
                        equipments.add(x)
            r = ex.get("role")
            if isinstance(r, list):
                for x in r:
                    if isinstance(x, str):
                        roles.add(x)
            d = ex.get("domain")
            if isinstance(d, list):
                for x in d:
                    if isinstance(x, str):
                        domains.add(x)
            elif isinstance(d, str):
                domains.add(d)

    return {
        "locations": sorted(locations),
        "equipment": sorted(equipments),
        "roles": sorted(roles),
        "domains": sorted(domains),
    }


def fuzzy_pick(options: List[str], preferred_substrings: List[str]) -> Optional[str]:
    low = [(o, o.lower()) for o in options]
    for sub in preferred_substrings:
        s = sub.lower()
        for orig, lo in low:
            if s in lo:
                return orig
    return None


def fuzzy_pick_many(options: List[str], substrings: List[str], limit: int = 50) -> List[str]:
    picked = []
    for o in options:
        lo = o.lower()
        if any(s.lower() in lo for s in substrings):
            picked.append(o)
    return picked[:limit]


def _extract_context_keys_from_resolver() -> List[str]:
    p = REPO_ROOT / "catalog" / "engine" / "resolve_session.py"
    txt = _read_text(p)
    keys = set()
    # context.get("x")
    keys.update(re.findall(r'context\.get\(\s*"([^"]+)"\s*\)', txt))
    # context['x'] or context["x"]
    keys.update(re.findall(r"context\[\s*'([^']+)'\s*\]", txt))
    keys.update(re.findall(r'context\[\s*"([^"]+)"\s*\]', txt))
    return sorted(keys)


def _load_module(path: str):
    # dynamic import to avoid assumptions
    import importlib
    return importlib.import_module(path)


def _call_resolver(session_template: Any, context: Dict[str, Any]) -> Any:
    rs = _load_module("catalog.engine.resolve_session")

    # Try common function names + kw patterns
    candidates = []
    for fn_name in ("resolve_session", "resolve_session_instance", "resolve", "run", "resolve_template"):
        if hasattr(rs, fn_name) and callable(getattr(rs, fn_name)):
            candidates.append(fn_name)

    if not candidates:
        raise RuntimeError("No callable resolver function found in catalog.engine.resolve_session")

    last_err = None
    for fn_name in candidates:
        fn = getattr(rs, fn_name)
        # Try kwargs
        for kwargs in (
            {"session_template": session_template, "context": context},
            {"session": session_template, "context": context},
            {"template": session_template, "context": context},
            {"session_template": session_template, "ctx": context},
            {"session": session_template, "ctx": context},
        ):
            try:
                return fn(**kwargs)
            except TypeError as e:
                last_err = e
            except Exception as e:
                # found function but runtime error inside -> raise (we want to see it)
                raise

        # Try positional (template, context)
        try:
            return fn(session_template, context)
        except TypeError as e:
            last_err = e

    raise RuntimeError(f"Unable to call resolver. Last TypeError: {last_err}")


def _extract_blocks(result: Any) -> List[Dict[str, Any]]:
    # Result could be dict with "blocks" or "block_instances" etc.
    if isinstance(result, dict):
        for k in ("blocks", "block_instances", "resolved_blocks", "block_results"):
            v = result.get(k)
            if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                return v
    return []


def _extract_selected_exercise_id(block: Dict[str, Any]) -> Optional[str]:
    # common nested shapes
    for k in ("exercise_instance", "selected_exercise", "exercise", "selection", "result"):
        v = block.get(k)
        if isinstance(v, dict):
            for idk in ("exercise_id", "id", "selected_exercise_id"):
                if isinstance(v.get(idk), str):
                    return v[idk]
    # sometimes directly on block
    for idk in ("exercise_id", "selected_exercise_id"):
        if isinstance(block.get(idk), str):
            return block[idk]
    return None


def _short_block_name(block: Dict[str, Any]) -> str:
    for k in ("block_id", "id", "name", "key"):
        if isinstance(block.get(k), str):
            return block[k]
    return "<block>"


@dataclass
class Scenario:
    name: str
    session_path: str
    context: Dict[str, Any]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session_finger", default="", help="Path to finger-strength session template JSON (relative to repo root). Auto-detect if empty.")
    ap.add_argument("--session_performance", default="", help="Path to performance/outdoor session template JSON (relative to repo root). Optional; auto-detect if empty.")
    ap.add_argument("--out_dir", default="out/manual_scenarios", help="Output directory for scenario JSON results.")
    args = ap.parse_args()

    out_dir = REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    vocab = discover_vocab_from_exercises()
    locations = vocab["locations"]
    equipment = vocab["equipment"]

    # Fuzzy choose locations
    loc_home = fuzzy_pick(locations, ["home"])
    loc_blocx = fuzzy_pick(locations, ["blocx"]) or fuzzy_pick(locations, ["gym"])
    loc_outdoor = fuzzy_pick(locations, ["outdoor", "crag", "rock"])

    # Fuzzy choose equipment sets (only include values that exist)
    eq_home_common = fuzzy_pick_many(equipment, ["dumbbell", "band", "pull", "bar", "mat", "kett", "weight"])
    eq_hangboard = fuzzy_pick_many(equipment, ["hangboard", "fingerboard", "beastmaker"])
    eq_gym_common = fuzzy_pick_many(equipment, ["kilter", "spray", "hangboard", "moon", "board", "campus", "bench", "barbell", "dumbbell", "weight"])
    eq_outdoor_common = fuzzy_pick_many(equipment, ["rope", "quick", "draw", "harness", "shoes", "helmet", "chalk"])

    # Auto-detect session templates if not provided
    sess_candidates = discover_session_candidates()

    def pick_session(subs: List[str]) -> Optional[str]:
        for rel, sid in sess_candidates:
            lo = (rel + " " + (sid or "")).lower()
            if all(s.lower() in lo for s in subs):
                return rel
        return None

    session_finger = args.session_finger.strip() or pick_session(["finger", "strength"]) or pick_session(["finger"])
    session_perf = args.session_performance.strip() or pick_session(["performance", "outdoor"]) or pick_session(["outdoor", "performance"]) or pick_session(["performance"]) or ""

    if not session_finger:
        print("ERROR: Could not auto-detect a finger-strength session template.")
        print("Candidates (path, id/name) that include 'finger':")
        for rel, sid in sess_candidates:
            if "finger" in (rel + " " + (sid or "")).lower():
                print(f"  - {rel}   (id/name={sid})")
        print("\nAll session-like candidates (first 60):")
        for rel, sid in sess_candidates[:60]:
            print(f"  - {rel}   (id/name={sid})")
        return 2

    if not loc_home or not loc_outdoor:
        print("WARNING: Fuzzy location pick incomplete.")
        print("Detected locations from exercises:")
        for x in locations:
            print("  -", x)

    # Context keys used by resolver (informative; we set conservative standard keys)
    ctx_keys = _extract_context_keys_from_resolver()
    # conservative context: provide both common key variants
    def mk_context(location: Optional[str], eq_list: List[str]) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}
        if location is not None:
            ctx["location"] = location
            # sometimes used
            ctx["current_location"] = location
        ctx["equipment_available"] = eq_list
        ctx["available_equipment"] = eq_list
        ctx["equipment"] = eq_list
        # include keys that resolver might read but are absent: leave unset unless known
        # (we do not want to guess business logic)
        return ctx

    scenarios: List[Scenario] = []

    # Finger session scenarios
    scenarios.append(Scenario(
        name="home_no_hangboard",
        session_path=session_finger,
        context=mk_context(loc_home, eq_home_common),
    ))
    scenarios.append(Scenario(
        name="home_with_hangboard",
        session_path=session_finger,
        context=mk_context(loc_home, sorted(set(eq_home_common + eq_hangboard))),
    ))
    scenarios.append(Scenario(
        name="gym_blocx",
        session_path=session_finger,
        context=mk_context(loc_blocx, sorted(set(eq_gym_common))),
    ))

    # Performance/outdoor scenario (if template exists, else reuse finger session with outdoor context)
    perf_path = session_perf or session_finger
    scenarios.append(Scenario(
        name="performance_outdoor",
        session_path=perf_path,
        context=mk_context(loc_outdoor, sorted(set(eq_outdoor_common))),
    ))

    print("\n=== Resolver context keys detected in code (informative) ===")
    print(ctx_keys)

    print("\n=== Session templates selected ===")
    print("finger:", session_finger)
    print("performance:", session_perf or "<not found; reusing finger>")

    print("\n=== Locations (fuzzy) ===")
    print("home:", loc_home)
    print("blocx/gym:", loc_blocx)
    print("outdoor:", loc_outdoor)

    print("\n=== Equipment picks (sample) ===")
    print("home_common:", eq_home_common)
    print("hangboard:", eq_hangboard)
    print("gym_common:", eq_gym_common[:25])
    print("outdoor_common:", eq_outdoor_common[:25])

    # Run scenarios
    for sc in scenarios:
        tpl_path = REPO_ROOT / sc.session_path
        tpl = _load_json(tpl_path)

        result = _call_resolver(tpl, sc.context)

        out_path = out_dir / f"{sc.name}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        # Summary
        blocks = _extract_blocks(result)
        print(f"\n\n================ SCENARIO: {sc.name} ================")
        print(f"session_path: {sc.session_path}")
        print(f"context: {json.dumps(sc.context, ensure_ascii=False)}")
        if isinstance(result, dict):
            rs = result.get("resolution_status")
            siv = result.get("session_instance_version")
            print(f"resolution_status={rs}  session_instance_version={siv}")
        print(f"blocks_found={len(blocks)}  output_json={out_path}")

        for b in blocks:
            bname = _short_block_name(b)
            status = b.get("status")
            msg = b.get("message")
            sel = _extract_selected_exercise_id(b)
            ft = b.get("filter_trace", {})
            p0t = b.get("p0_trace", None)

            # Normalize filter_trace view
            p_stage = ft.get("p_stage")
            counts = ft.get("counts")
            domain_applied = ft.get("domain_filter_applied")
            note = ft.get("note")

            print(f"\n- BLOCK {bname}")
            print(f"  status={status}  selected_exercise_id={sel}")
            if msg:
                print(f"  message={msg}")
            print(f"  filter_trace.p_stage={p_stage}")
            print(f"  filter_trace.counts={counts}")
            print(f"  filter_trace.domain_filter_applied={domain_applied}")
            if note:
                print(f"  filter_trace.note={note}")
            # keep p0_trace visible but compact
            if p0t is not None:
                try:
                    print(f"  p0_trace={json.dumps(p0t, ensure_ascii=False)}")
                except Exception:
                    print(f"  p0_trace=<non-serializable>")

    print("\n\nDONE. Review the summaries above. Full JSON outputs in:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
