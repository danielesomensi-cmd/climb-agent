import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# IO helpers
# ---------------------------
def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_exercise_list(ex_data: Any) -> List[Dict[str, Any]]:
    """
    Supports shapes:
      - [ {exercise}, ... ]
      - { "exercises": [ ... ] }
      - { "items": [ ... ] }
      - { "data": [ ... ] }
    """
    if isinstance(ex_data, list):
        return ex_data
    if isinstance(ex_data, dict):
        for key in ("exercises", "items", "data"):
            if key in ex_data and isinstance(ex_data[key], list):
                return ex_data[key]
    raise ValueError("Unsupported exercises.json structure.")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------
# Normalization helpers
# ---------------------------
def norm_str(x: Any) -> str:
    return str(x).strip().lower()


def as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def norm_list_str(x: Any) -> List[str]:
    return [norm_str(v) for v in as_list(x) if norm_str(v)]


def get_ex_id(ex: Dict[str, Any]) -> str:
    return ex.get("exercise_id") or ex.get("id") or "unknown_exercise"


def get_ex_tags(ex: Dict[str, Any]) -> List[str]:
    # tags are simple strings; stress_tags may be dict or list
    tags = norm_list_str(ex.get("tags"))

    st = ex.get("stress_tags")
    if isinstance(st, dict):
        # allow { "fingers": "high", "cns": "low" } etc; convert to tokens
        for k, v in st.items():
            k2 = norm_str(k)
            v2 = norm_str(v)
            if v2 and v2 != "none":
                tags.append(f"stress:{k2}:{v2}")
    elif isinstance(st, list):
        tags += norm_list_str(st)

    return list(dict.fromkeys(tags))


def get_ex_equipment(ex: Dict[str, Any]) -> List[str]:
    # equipment as list of strings (e.g., ["hangboard", "pangullich"])
    return norm_list_str(ex.get("equipment"))


# ---------------------------
# Context (location/equipment/history)
# ---------------------------
def load_user_state(repo_root: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(repo_root, "data/user_state.json")
    if os.path.exists(p):
        return load_json(p)
    return None


def get_location_equipment(user_state: Optional[Dict[str, Any]], session: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Determines where the session happens and what equipment is available there.

    Priority:
    1) session["context"]["location"] (or "place") if present
    2) user_state default location: user_state["defaults"]["location"] (optional)
    3) fallback: "home"

    Equipment comes from user_state["equipment"]["home"] or matching gym.
    """
    location = "home"
    if isinstance(session.get("context"), dict):
        location = session["context"].get("location") or session["context"].get("place") or location

    if user_state and location == "home":
        defaults = user_state.get("defaults") or {}
        location = defaults.get("location") or location

    location = norm_str(location) or "home"

    equipment: List[str] = []
    if user_state:
        eq = user_state.get("equipment") or {}
        if location == "home":
            equipment = norm_list_str(eq.get("home"))
        else:
            gyms = eq.get("gyms") or []
            for g in gyms:
                if norm_str(g.get("gym_id")) == location or norm_str(g.get("name")) == location:
                    equipment = norm_list_str(g.get("equipment"))
                    break

    # Always-available "virtual equipment"
    if "floor" not in equipment:
        equipment.append("floor")

    return location, equipment


def load_recent_exercise_ids(repo_root: str, days_window: int = 5) -> List[str]:
    """
    MVP: looks into data/logs/sessions_*.jsonl and extracts recently used exercise_ids.
    We keep it simple: we read all lines and take last N entries; in the future filter by date properly.
    """
    logs_dir = os.path.join(repo_root, "data", "logs")
    if not os.path.isdir(logs_dir):
        return []

    paths = []
    for fn in os.listdir(logs_dir):
        if fn.startswith("sessions_") and fn.endswith(".jsonl"):
            paths.append(os.path.join(logs_dir, fn))

    recent: List[str] = []
    for p in sorted(paths):
        try:
            with open(p, "r", encoding="utf-8") as f:
                lines = f.readlines()[-200:]  # small rolling tail
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                # expected: obj["exercise_instances"] = [...]
                eis = obj.get("exercise_instances") or obj.get("resolved_session", {}).get("exercise_instances") or []
                for e in eis:
                    ex_id = e.get("exercise_id")
                    if ex_id:
                        recent.append(norm_str(ex_id))
        except Exception:
            continue

    # last ones are most recent
    return recent[-100:]


# ---------------------------
# Filtering + Scoring
# ---------------------------
def exercise_matches_filters(ex: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """
    Supported filters (MVP):
      - category: exact match
      - required_tags_any / required_tags_all / exclude_tags_any
      - required_equipment_any / required_equipment_all
    """
    ex_cat = norm_str(ex.get("category"))
    ex_tags = set(get_ex_tags(ex))
    ex_eq = set(get_ex_equipment(ex))

    # category
    if filters.get("category") is not None:
        if ex_cat != norm_str(filters.get("category")):
            return False

    # tags
    req_any = set(norm_list_str(filters.get("required_tags_any")))
    req_all = set(norm_list_str(filters.get("required_tags_all")))
    excl_any = set(norm_list_str(filters.get("exclude_tags_any")))

    if req_any and not (ex_tags & req_any):
        return False
    if req_all and not req_all.issubset(ex_tags):
        return False
    if excl_any and (ex_tags & excl_any):
        return False

    # equipment filters (optional)
    req_eq_any = set(norm_list_str(filters.get("required_equipment_any")))
    req_eq_all = set(norm_list_str(filters.get("required_equipment_all")))

    if req_eq_any and not (ex_eq & req_eq_any):
        return False
    if req_eq_all and not req_eq_all.issubset(ex_eq):
        return False

    return True


def compatible_with_location(ex: Dict[str, Any], available_equipment: List[str]) -> bool:
    """
    Hard constraint:
    - if exercise has equipment requirements, all must be present (conservative rule).
    If you want looser behavior later, switch to 'any' logic per exercise type.
    """
    req = get_ex_equipment(ex)
    if not req:
        return True
    avail = set(norm_list_str(available_equipment))
    return set(req).issubset(avail)


def score_exercise(
    ex: Dict[str, Any],
    prefs: Dict[str, Any],
    recent_ex_ids: List[str],
) -> float:
    """
    Simple scoring:
    + prefer edge_mm == preferred_edge
    + prefer grip == preferred_grip
    - penalize if used very recently
    """
    s = 0.0
    ex_id = norm_str(get_ex_id(ex))

    # recent penalty (coherence)
    # If it appears in the last K selections, penalize more
    if ex_id in recent_ex_ids[-5:]:
        s -= 100.0
    elif ex_id in recent_ex_ids[-15:]:
        s -= 25.0
    elif ex_id in recent_ex_ids:
        s -= 5.0

    # preference matching (strong preference but not mandatory)
    pref_edge = prefs.get("preferred_edge_mm")
    pref_grip = norm_str(prefs.get("preferred_grip"))

    # We only score if the exercise declares these attributes
    ex_attrs = ex.get("attributes") or {}
    ex_edge = ex_attrs.get("edge_mm")
    ex_grip = norm_str(ex_attrs.get("grip"))

    if pref_edge is not None and ex_edge is not None:
        if int(ex_edge) == int(pref_edge):
            s += 10.0

    if pref_grip and ex_grip:
        if ex_grip == pref_grip:
            s += 5.0

    return s


def pick_best_exercise(
    exercises: List[Dict[str, Any]],
    filters: Dict[str, Any],
    available_equipment: List[str],
    prefs: Dict[str, Any],
    recent_ex_ids: List[str],
) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for ex in exercises:
        if not exercise_matches_filters(ex, filters):
            continue
        if not compatible_with_location(ex, available_equipment):
            continue
        candidates.append(ex)

    if not candidates:
        return None

    scored = [(score_exercise(ex, prefs, recent_ex_ids), ex) for ex in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


# ---------------------------
# Resolve session (B + fallback)
# ---------------------------
def resolve_session(
    repo_root: str,
    session_path: str,
    templates_dir: str,
    exercises_path: str,
    out_path: str
) -> Dict[str, Any]:
    user_state = load_user_state(repo_root)

    session = load_json(os.path.join(repo_root, session_path))
    exercises_raw = load_json(os.path.join(repo_root, exercises_path))
    exercises = ensure_exercise_list(exercises_raw)

    # context: location/equipment
    location, available_equipment = get_location_equipment(user_state, session)

    # recent history (MVP)
    recent_ex_ids = load_recent_exercise_ids(repo_root)

    # preferences (baseline 20mm strong preference, overridable)
    prefs = {
        "preferred_edge_mm": 20,
        "preferred_grip": "half_crimp",
    }
    if user_state:
        # allow override from user_state if you want later
        pass

    # identity
    session_id = session.get("session_id") or session.get("id") or os.path.splitext(os.path.basename(session_path))[0]
    session_version = session.get("version") or session.get("session_version") or "v1"

    modules = session.get("modules") or session.get("templates") or session.get("components") or []
    if not isinstance(modules, list):
        raise ValueError("Session must contain a list field: modules/templates/components")

    resolved_modules: List[Dict[str, Any]] = []
    blocks_out: List[Dict[str, Any]] = []
    exercise_instances: List[Dict[str, Any]] = []

    instance_counter = 0

    for mod in modules:
        if isinstance(mod, str):
            template_id = mod
            template_version = "v1"
        elif isinstance(mod, dict):
            template_id = mod.get("template_id") or mod.get("id") or mod.get("name")
            template_version = mod.get("version") or mod.get("template_version") or "v1"
        else:
            continue

        if not template_id:
            continue

        template_file = os.path.join(repo_root, templates_dir, template_version, f"{template_id}.json")
        if not os.path.exists(template_file):
            alt = os.path.join(repo_root, templates_dir, f"{template_id}.json")
            if os.path.exists(alt):
                template_file = alt
            else:
                raise FileNotFoundError(f"Template not found: {template_file}")

        template = load_json(template_file)
        resolved_modules.append({"template_id": template_id, "version": template_version})

        blocks = template.get("blocks") or template.get("components") or template.get("steps") or []
        if not isinstance(blocks, list):
            continue

        for b in blocks:
            block_id = b.get("block_id") or b.get("id") or f"{template_id}_block_{len(blocks_out)+1}"
            block_uid = f"{template_id}.{block_id}"
            block_type = b.get("type") or b.get("category") or "main"
            mode = norm_str(b.get("mode") or "")

            # If block is instruction-only, do NOT select exercises
            if mode == "instruction_only":
                blocks_out.append({
                    "block_uid": block_uid,
                    "block_id": block_id,
                    "type": block_type,
                    "template_id": template_id,
                    "selected_exercises": []
                })
                continue




            explicit_ex_id = b.get("exercise_id")
            selection = b.get("selection") or {}

            selected_ex = None
            selected_list: List[Dict[str, Any]] = []
            chosen_by = None

            if explicit_ex_id:
                selected_ex = next(
                    (e for e in exercises if norm_str(get_ex_id(e)) == norm_str(explicit_ex_id)),
                    None
                )
                chosen_by = "explicit_exercise_id"
            else:
                # B-mode: selection can have primary + fallbacks
                # accepted shapes:
                # selection = { "filters": {...} }  (legacy)
                # selection = { "primary": { "filters": {...}, "preferences": {...} },
                #               "fallbacks": [ { "filters": {...} }, ... ] }
                primary = None
                fallbacks = []

                if isinstance(selection, dict) and "primary" in selection:
                    primary = selection.get("primary")
                    fallbacks = selection.get("fallbacks") or []
                else:
                    primary = selection  # legacy

                def extract_filters(sel_obj: Any) -> Dict[str, Any]:
                    if isinstance(sel_obj, dict):
                        f = sel_obj.get("filters") or sel_obj
                        return f if isinstance(f, dict) else {}
                    return {}

                # allow block-specific preferences override (optional)
                block_prefs = dict(prefs)
                if isinstance(primary, dict):
                    p2 = primary.get("preferences")
                    if isinstance(p2, dict):
                        # Example: {"preferred_edge_mm": 20, "preferred_grip": "half_crimp"}
                        block_prefs.update(p2)

                # try primary
                primary_filters = extract_filters(primary)
                selected_ex = pick_best_exercise(
                    exercises=exercises,
                    filters=primary_filters,
                    available_equipment=available_equipment,
                    prefs=block_prefs,
                    recent_ex_ids=recent_ex_ids
                )
                chosen_by = "primary" if selected_ex else None

                # try fallbacks in order
                if not selected_ex and isinstance(fallbacks, list):
                    for i, fb in enumerate(fallbacks, start=1):
                        fb_filters = extract_filters(fb)
                        selected_ex = pick_best_exercise(
                            exercises=exercises,
                            filters=fb_filters,
                            available_equipment=available_equipment,
                            prefs=block_prefs,
                            recent_ex_ids=recent_ex_ids
                        )
                        if selected_ex:
                            chosen_by = f"fallback_{i}"
                            break

            if selected_ex:
                instance_counter += 1
                instance_id = f"{block_id}_{instance_counter:02d}"
                ex_id = get_ex_id(selected_ex)

                variant = b.get("variant") or {}
                prescription = b.get("prescription") or b.get("params") or {}

                ex_defaults = selected_ex.get("defaults") or selected_ex.get("prescription_defaults") or {}
                merged: Dict[str, Any] = {}
                if isinstance(ex_defaults, dict):
                    merged.update(ex_defaults)
                if isinstance(prescription, dict):
                    merged.update(prescription)

                inst = {
                    "instance_id": instance_id,
                    "exercise_id": ex_id,
                    "variant": variant,
                    "prescription": merged,
                    "block_uid": block_uid,
                    "source": {
                        "picked_by": f"resolver_v0.2/{chosen_by or 'unknown'}",
                        "template_id": template_id,
                        "block_id": block_id
                    }
                }
                exercise_instances.append(inst)
                recent_ex_ids.append(norm_str(ex_id))  # update “recent” inside this resolution too

                selected_list.append({
                    "exercise_id": ex_id,
                    "variant": variant,
                    "prescription": merged
                })

            blocks_out.append({
                "block_uid": block_uid,
                "block_id": block_id,
                "type": block_type,
                "template_id": template_id,
                "selected_exercises": selected_list
            })

    session_instance = {
        "session_instance_version": "1.1",
        "generated_at": now_iso(),
        "context": {
            "location": location,
            "available_equipment": available_equipment
        },
        "session": {
            "session_id": session_id,
            "session_version": session_version,
            "source_path": session_path
        },
        "resolved_session": {
            "resolver_version": "0.2",
            "modules": resolved_modules,
            "blocks": blocks_out,
            "exercise_instances": exercise_instances
        }
    }

    out_full = os.path.join(repo_root, out_path)
    os.makedirs(os.path.dirname(out_full), exist_ok=True)
    with open(out_full, "w", encoding="utf-8") as f:
        json.dump(session_instance, f, ensure_ascii=False, indent=2)

    return session_instance


if __name__ == "__main__":
    REPO_ROOT = os.getcwd()

    session_instance = resolve_session(
        repo_root=REPO_ROOT,
        session_path="catalog/sessions/v1/strength_long.json",
        templates_dir="catalog/templates",
        exercises_path="catalog/exercises/v1/exercises.json",
        out_path="output/session_instance_strength_long.json"
    )

    print("Generated: output/session_instance_strength_long.json")
    print("Location:", session_instance.get("context", {}).get("location"))
    print("Equipment:", session_instance.get("context", {}).get("available_equipment"))
    print("Modules:", len(session_instance["resolved_session"]["modules"]))
    print("Blocks:", len(session_instance["resolved_session"]["blocks"]))
    print("Exercise instances:", len(session_instance["resolved_session"]["exercise_instances"]))
