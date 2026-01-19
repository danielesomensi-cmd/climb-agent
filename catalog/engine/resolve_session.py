import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------
# IO helpers
# ---------------------------
def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_exercise_list(ex_data: Any) -> List[Dict[str, Any]]:
    """
    Supports common shapes:
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
    raise ValueError("Unsupported exercises.json structure. Expected list or dict with exercises/items/data list.")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------
# Matching helpers (MVP)
# ---------------------------
def normalize_tags(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(t).strip().lower() for t in x if str(t).strip()]
    if isinstance(x, str):
        return [t.strip().lower() for t in x.split(",") if t.strip()]
    return []


def exercise_matches_filters(ex: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """
    Minimal filter support (MVP):
      - required_tags_any: at least one tag must match
      - required_tags_all: all tags must match
      - exclude_tags_any: none of these tags can be present
      - category: exact match if present on exercise
    """
    ex_tags = set(normalize_tags(ex.get("tags")) + normalize_tags(ex.get("stress_tags")))

    req_any = set(normalize_tags(filters.get("required_tags_any")))
    req_all = set(normalize_tags(filters.get("required_tags_all")))
    excl_any = set(normalize_tags(filters.get("exclude_tags_any")))

    if req_any and not (ex_tags & req_any):
        return False
    if req_all and not req_all.issubset(ex_tags):
        return False
    if excl_any and (ex_tags & excl_any):
        return False

    if "category" in filters and filters["category"] is not None:
        if str(ex.get("category", "")).strip().lower() != str(filters["category"]).strip().lower():
            return False

    return True


def pick_exercise(exercises: List[Dict[str, Any]], filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Deterministic MVP: pick the first matching exercise.
    for ex in exercises:
        if exercise_matches_filters(ex, filters):
            return ex
    return None


# ---------------------------
# Resolver
# ---------------------------
def resolve_session(
    repo_root: str,
    session_path: str,
    templates_dir: str,
    exercises_path: str,
    out_path: str
) -> Dict[str, Any]:
    session = load_json(os.path.join(repo_root, session_path))
    exercises_raw = load_json(os.path.join(repo_root, exercises_path))
    exercises = ensure_exercise_list(exercises_raw)

    # Session identity (tolerant)
    session_id = session.get("session_id") or session.get("id") or os.path.splitext(os.path.basename(session_path))[0]
    session_version = session.get("version") or session.get("session_version") or "v1"

    # Modules list (tolerant)
    modules = session.get("modules") or session.get("templates") or session.get("components") or []
    if not isinstance(modules, list):
        raise ValueError("Session must contain a list field: modules/templates/components")

    resolved_modules: List[Dict[str, Any]] = []
    blocks_out: List[Dict[str, Any]] = []
    exercise_instances: List[Dict[str, Any]] = []

    instance_counter = 0

    for mod in modules:
        # Module can be string or dict
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
            # fallback without version subfolder
            template_file_alt = os.path.join(repo_root, templates_dir, f"{template_id}.json")
            if os.path.exists(template_file_alt):
                template_file = template_file_alt
            else:
                raise FileNotFoundError(f"Template not found: {template_file}")

        template = load_json(template_file)
        resolved_modules.append({"template_id": template_id, "version": template_version})

        # Blocks (tolerant)
        blocks = template.get("blocks") or template.get("components") or template.get("steps") or []
        if not isinstance(blocks, list):
            continue

        for b in blocks:
            block_id = b.get("block_id") or b.get("id") or f"{template_id}_block_{len(blocks_out)+1}"
            block_type = b.get("type") or b.get("category") or "main"

            # Selection logic:
            # - explicit exercise_id in block
            # - OR selection.filters
            selection = b.get("selection") or {}
            explicit_ex_id = b.get("exercise_id")

            filters = {}
            if isinstance(selection, dict):
                filters = selection.get("filters") or {}
            if not isinstance(filters, dict):
                filters = {}

            selected_ex = None

            if explicit_ex_id:
                selected_ex = next(
                    (e for e in exercises if (e.get("exercise_id") == explicit_ex_id or e.get("id") == explicit_ex_id)),
                    None
                )
            else:
                selected_ex = pick_exercise(exercises, filters)

            selected_list: List[Dict[str, Any]] = []

            if selected_ex:
                instance_counter += 1
                instance_id = f"{block_id}_{instance_counter:02d}"

                ex_id = selected_ex.get("exercise_id") or selected_ex.get("id") or "unknown_exercise"

                variant = b.get("variant") or {}
                prescription = b.get("prescription") or b.get("params") or {}

                # Merge exercise defaults (lowest priority) + block prescription (highest)
                ex_defaults = selected_ex.get("defaults") or selected_ex.get("prescription_defaults") or {}
                merged_prescription: Dict[str, Any] = {}
                if isinstance(ex_defaults, dict):
                    merged_prescription.update(ex_defaults)
                if isinstance(prescription, dict):
                    merged_prescription.update(prescription)

                inst = {
                    "instance_id": instance_id,
                    "exercise_id": ex_id,
                    "variant": variant,
                    "prescription": merged_prescription,
                    "source": {
                        "picked_by": "resolver_v0.1",
                        "template_id": template_id,
                        "block_id": block_id
                    }
                }
                exercise_instances.append(inst)

                selected_list.append({
                    "exercise_id": ex_id,
                    "variant": variant,
                    "prescription": merged_prescription
                })

            blocks_out.append({
                "block_id": block_id,
                "type": block_type,
                "template_id": template_id,
                "selected_exercises": selected_list
            })

    session_instance = {
        "session_instance_version": "1.0",
        "generated_at": now_iso(),
        "session": {
            "session_id": session_id,
            "session_version": session_version,
            "source_path": session_path
        },
        "resolved_session": {
            "resolver_version": "0.1",
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
    print("Modules:", len(session_instance["resolved_session"]["modules"]))
    print("Blocks:", len(session_instance["resolved_session"]["blocks"]))
    print("Exercise instances:", len(session_instance["resolved_session"]["exercise_instances"]))
