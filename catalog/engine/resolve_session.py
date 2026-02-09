import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from catalog.engine.cluster_utils import cluster_key_for_exercise, parse_date


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


# ---------------------------
# P0.5: Load parameterization (deterministic, explainable)
# ---------------------------
def _round_to_step(x: float, step: float = 0.5) -> float:
    return round(x / step) * step

def _apply_load_override(
    prescription: Dict[str, Any],
    *,
    user_state: Optional[Dict[str, Any]],
    exercise_id: str,
    rounding_step: float = 0.5,
) -> Dict[str, Any]:
    if not user_state:
        return prescription
    if "load_kg" not in prescription:
        return prescription

    overrides = user_state.setdefault("overrides", {})
    per_exercise = overrides.setdefault("per_exercise", {})
    override = per_exercise.get(exercise_id)
    if not isinstance(override, dict):
        return prescription

    mode = override.get("mode")
    if mode not in {"absolute_load_kg", "delta_kg", "multiplier"}:
        return prescription

    value = override.get("value")
    if value is None:
        return prescription

    base_load = float(prescription["load_kg"])
    if mode == "absolute_load_kg":
        adjusted = float(value)
    elif mode == "delta_kg":
        adjusted = base_load + float(value)
    else:
        adjusted = base_load * float(value)

    updated = dict(prescription)
    updated["load_kg"] = _round_to_step(adjusted, rounding_step)

    expires = override.get("expires") or {}
    if expires.get("type") == "occurrences":
        try:
            remaining = int(expires.get("n", 0))
        except (TypeError, ValueError):
            remaining = 0
        remaining -= 1
        if remaining <= 0:
            per_exercise.pop(exercise_id, None)
        else:
            override["expires"] = {**expires, "n": remaining}

    return updated

def _pick_hangboard_baseline(user_state: Dict[str, Any], edge_mm: int, grip: str, hang_seconds: int) -> Optional[Dict[str, Any]]:
    baselines = ((user_state.get("baselines") or {}).get("hangboard") or [])
    for b in baselines:
        if int(b.get("edge_mm", -1)) == int(edge_mm) and str(b.get("grip","")).strip().lower() == str(grip).strip().lower() and int(b.get("hang_seconds",-1)) == int(hang_seconds):
            return b
    return baselines[0] if baselines else None

def suggest_max_hang_load(user_state: Optional[Dict[str, Any]], prescription: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    '''
    Given user_state baselines (max_total_load_kg) and prescription intensity,
    return suggested target_total_load_kg and added_weight_kg / assistance_kg.
    '''
    if not user_state:
        return None
    bw = user_state.get("bodyweight_kg")
    if bw is None:
        return None

    intensity = prescription.get("intensity_pct_of_total_load")
    if intensity is None:
        return None

    # Defaults (deterministic)
    edge_mm = 20
    grip = "half_crimp"
    hang_seconds = int(prescription.get("hang_seconds") or prescription.get("hang_seconds_range", [5])[0] or 5)

    b = _pick_hangboard_baseline(user_state, edge_mm=edge_mm, grip=grip, hang_seconds=hang_seconds)
    if not b:
        return None

    max_total = b.get("max_total_load_kg")
    if max_total is None:
        return None

    target_total = float(intensity) * float(max_total)
    added = target_total - float(bw)

    out = {
        "baseline_id": b.get("baseline_id"),
        "protocol_version": b.get("protocol_version", "max_hang_5s.v1"),
        "based_on": {"max_total_load_kg": float(max_total), "bodyweight_kg": float(bw)},
        "setup": {"edge_mm": int(b.get("edge_mm", edge_mm)), "grip": b.get("grip", grip), "load_method": b.get("load_method", "added_weight")},
        "intensity_pct_of_total_load": float(intensity),
        "target_total_load_kg": _round_to_step(target_total, 0.5),
        "added_weight_kg": 0.0,
        "assistance_kg": 0.0,
        "rationale": "target_total_load = intensity_pct * max_total_load; added = target_total - bodyweight; rounded to 0.5kg"
    }

    if added >= 0:
        out["added_weight_kg"] = _round_to_step(added, 0.5)
        out["assistance_kg"] = 0.0
    else:
        out["added_weight_kg"] = 0.0
        out["assistance_kg"] = _round_to_step(-added, 0.5)

    return out

def as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def norm_list_str(x: Any) -> List[str]:
    return [norm_str(v) for v in as_list(x) if norm_str(v)]


def ex_patterns(ex: Dict[str, Any]) -> List[str]:
    if "pattern" in ex:
        return norm_list_str(ex.get("pattern"))
    return norm_list_str(ex.get("movement"))


def get_ex_id(ex: Dict[str, Any]) -> str:
    return ex.get("exercise_id") or ex.get("id") or "unknown_exercise"


def ex_roles(ex: Dict[str, Any]) -> List[str]:
    out = []
    out += norm_list_str(ex.get("role"))
    out += norm_list_str(ex.get("roles"))  # legacy support
    # dedup preservando ordine
    seen = set()
    res = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


def ex_domains(ex: Dict[str, Any]) -> List[str]:
    return norm_list_str(ex.get("domain"))

def ex_location_allowed(ex: Dict[str, Any]) -> List[str]:
    return norm_list_str(ex.get("location_allowed"))

def ex_equipment_required(ex: Dict[str, Any]) -> List[str]:
    return norm_list_str(ex.get("equipment_required"))

def ex_equipment_required_any(ex: Dict[str, Any]) -> List[str]:
    return norm_list_str(ex.get("equipment_required_any"))

def pick_best_exercise_p0(
    *,
    exercises: List[Dict[str, Any]],
    location: str,
    available_equipment: List[str],
    role_req: Any,
    domain_req: Any,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    P0: hard filters only:
      - location_allowed includes location
      - equipment_required subset of available_equipment
      - equipment_required_any has at least one available item
      - role matches (ANY)
      - domain matches only if it doesn't zero candidates (ANY)
    Deterministic tie-break: exercise_id
    """
    loc = norm_str(location)
    avail = set(norm_list_str(available_equipment))

    role_set = set(norm_list_str(role_req))
    dom_set = set(norm_list_str(domain_req))

    trace = {"counts": {}}

    # Stage 0
    base0 = exercises[:]
    trace["counts"]["start"] = len(base0)

    # Stage 1: location_allowed
    base1 = [e for e in base0 if loc in set(ex_location_allowed(e))]
    trace["counts"]["after_location"] = len(base1)

    # Stage 2: equipment hard constraints
    base2 = []
    for e in base1:
        req = set(ex_equipment_required(e))
        if req and not req.issubset(avail):
            continue
        req_any = ex_equipment_required_any(e)
        if req_any and set(req_any).isdisjoint(avail):
            continue
        base2.append(e)
    trace["counts"]["after_equipment"] = len(base2)

    # Stage 3: role (ANY match)
    base3 = base2
    if role_set:
        base3 = []
        for e in base2:
            if not set(ex_roles(e)).isdisjoint(role_set):
                base3.append(e)
    trace["counts"]["after_role"] = len(base3)

    if not base3:
        trace["domain_filter_applied"] = False
        return None, trace

    # Stage 4: domain only if it doesn't zero
    trace["domain_filter_applied"] = False

    # Default: if domain is not applied, after_domain == len(base3)
    trace["counts"]["after_domain"] = len(base3)

    if dom_set:
        base4 = []
        for e in base3:
            if not set(ex_domains(e)).isdisjoint(dom_set):
                base4.append(e)

        # Apply domain only if it doesn't zero (P0 rule)
        if base4:
            trace["domain_filter_applied"] = True
            trace["counts"]["after_domain"] = len(base4)
            base3 = base4
        else:
            # domain would zero, so keep base3 unchanged
            trace["domain_filter_applied"] = False
            trace["counts"]["after_domain"] = len(base3)




    # Deterministic pick
    base3.sort(key=lambda e: norm_str(get_ex_id(e)))
    return (base3[0] if base3 else None), trace





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
             
        elif location == "gym":
            # gym_id drives gym equipment (NOT location)
            gym_id = None
            if isinstance(session.get("context"), dict):
                gym_id = session["context"].get("gym_id")
            if user_state and not gym_id:
                gym_id = (user_state.get("context") or {}).get("gym_id")
            gym_id = norm_str(gym_id) if gym_id else None

            gyms = eq.get("gyms") or []
            for g in gyms:
                if gym_id and norm_str(g.get("gym_id")) == gym_id:
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


def _cooldown_until_date(user_state: Optional[Dict[str, Any]], cluster_key: str) -> Optional[str]:
    if not user_state:
        return None
    cooldowns = user_state.get("cooldowns") or {}
    per_cluster = cooldowns.get("per_cluster") or {}
    entry = per_cluster.get(cluster_key) or {}
    return entry.get("until_date")


def _find_cooldown_fallback(
    exercises: List[Dict[str, Any]],
    current_ex: Dict[str, Any],
    available_equipment: List[str],
) -> Optional[Dict[str, Any]]:
    current_domain = sorted(norm_list_str(current_ex.get("domain")))
    current_eq = sorted(norm_list_str(current_ex.get("equipment_required")))
    current_eq_any = sorted(norm_list_str(current_ex.get("equipment_required_any")))
    current_pattern = sorted(ex_patterns(current_ex))

    avail = set(norm_list_str(available_equipment))

    def same_domain_equipment(ex: Dict[str, Any]) -> bool:
        if sorted(norm_list_str(ex.get("domain"))) != current_domain:
            return False
        if sorted(norm_list_str(ex.get("equipment_required"))) != current_eq:
            return False
        if sorted(norm_list_str(ex.get("equipment_required_any"))) != current_eq_any:
            return False
        req = set(ex_equipment_required(ex))
        if req and not req.issubset(avail):
            return False
        req_any = ex_equipment_required_any(ex)
        return not req_any or not set(req_any).isdisjoint(avail)

    def same_cluster(ex: Dict[str, Any]) -> bool:
        if not same_domain_equipment(ex):
            return False
        return sorted(ex_patterns(ex)) == current_pattern

    candidates = [
        ex for ex in exercises
        if same_cluster(ex) and "main" not in set(ex_roles(ex))
    ]
    if not candidates:
        candidates = [
            ex for ex in exercises
            if same_domain_equipment(ex) and set(ex_roles(ex)) & {"assistant", "secondary"}
        ]

    if not candidates:
        return None

    candidates.sort(key=lambda e: norm_str(get_ex_id(e)))
    return candidates[0]


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
    out_path: str,
    *,
    user_state_override: Optional[Dict[str, Any]] = None,
    write_output: bool = True
) -> Dict[str, Any]:
    user_state = user_state_override if user_state_override is not None else load_user_state(repo_root)

    session = load_json(os.path.join(repo_root, session_path))
    session_ctx = session.get("context") if isinstance(session.get("context"), dict) else {}
    user_ctx = user_state.get("context") if isinstance(user_state.get("context"), dict) else {}
    gym_id = session_ctx.get("gym_id") or user_ctx.get("gym_id")
    target_date = parse_date(session_ctx.get("target_date") or session_ctx.get("date"))

    exercises_raw = load_json(os.path.join(repo_root, exercises_path))
    exercises = ensure_exercise_list(exercises_raw)

    # context: location/equipment
    location, available_equipment = get_location_equipment(user_state, session)
    # Remove implicit/obvious equipment
    available_equipment = [e for e in available_equipment if norm_str(e) != "floor"]

    # Equipment implications (v1): if any weight subtype is present, expose canonical 'weight'.
    weight_subtypes = {"dumbbell", "kettlebell", "barbell"}
    if any(w in available_equipment for w in weight_subtypes) and "weight" not in available_equipment:
        available_equipment.append("weight")


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



            trace = {"counts": {}, "domain_filter_applied": None}

            # If block is instruction-only, do NOT select exercises
            if mode == "instruction_only":
                instructions = {k: b[k] for k in ("duration_min_range", "options", "focus", "notes", "prescription") if k in b}
                blocks_out.append({
                    "block_uid": block_uid,
                    "block_id": block_id,
                    "type": block_type,
                    "template_id": template_id,
                    "status": "selected",
                    "message": "Instruction-only block (no exercise selection).",
                    "instructions": instructions,
                    "p0_trace": trace,
                    "filter_trace": {"p_stage": "P0", **trace, "note": "instruction_only: no selection performed"},
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
                trace = {"counts": {}, "domain_filter_applied": None, "note": "explicit_exercise_id: bypassed P0 filters"}

           
            else:
                # P0: hard-filter only selection based on v1 schema (role/domain)
                role_req = b.get("role")   # P0 requires explicit block.role; block.type is NOT a selector input
                domain_req = b.get("domain")

                trace = {}
                if role_req is None:
                    selected_ex = None
                    chosen_by = "p0_missing_role"
                    trace = {"counts": {}, "domain_filter_applied": None, "error": "Missing block.role (P0 requires role for selection)."}
                else:
                    selected_ex, trace = pick_best_exercise_p0(
                        exercises=exercises,
                        location=location,
                        available_equipment=available_equipment,
                        role_req=role_req,
                        domain_req=domain_req,
                    )
                    chosen_by = "p0_hard_filters"


            replanner_note = None
            if selected_ex and norm_str(block_type) == "main" and target_date:
                cluster_key = cluster_key_for_exercise(selected_ex)
                until_date_value = _cooldown_until_date(user_state, cluster_key)
                until_date = parse_date(until_date_value)
                if until_date and target_date <= until_date:
                    fallback_ex = _find_cooldown_fallback(
                        exercises=exercises,
                        current_ex=selected_ex,
                        available_equipment=available_equipment,
                    )
                    if fallback_ex:
                        replanner_note = {
                            "cooldown_cluster": cluster_key,
                            "until_date": until_date.isoformat(),
                            "fallback_exercise_id": get_ex_id(fallback_ex),
                            "reason": "cluster_cooldown_fallback",
                        }
                        selected_ex = fallback_ex
                    else:
                        replanner_note = {
                            "cooldown_cluster": cluster_key,
                            "until_date": until_date.isoformat(),
                            "reason": "cluster_cooldown_downshift",
                            "multiplier": 0.9,
                        }

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

                if replanner_note and replanner_note.get("reason") == "cluster_cooldown_downshift":
                    merged.setdefault("multiplier", 1.0)
                    merged["multiplier"] = float(merged["multiplier"]) * 0.9

                merged = _apply_load_override(
                    merged,
                    user_state=user_state,
                    exercise_id=ex_id,
                )

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
                if replanner_note:
                    inst["replanner"] = replanner_note
                if ex_id == "max_hang_5s":
                    sug = suggest_max_hang_load(user_state, merged)
                    if sug:
                        inst["suggested"] = sug
                exercise_instances.append(inst)
                recent_ex_ids.append(norm_str(ex_id))  # update “recent” inside this resolution too

                selected_list.append({
                    "exercise_id": ex_id,
                    "variant": variant,
                    "prescription": merged
                })

            status = "selected" if selected_list else "skipped"
            message = None if selected_list else "No candidates after hard filters (P0)."

            blocks_out.append({
                "block_uid": block_uid,
                "block_id": block_id,
                "type": block_type,
                "template_id": template_id,
                "status": status,
                "message": message,
                "p0_trace": trace,
                "filter_trace": {"p_stage": "P0", **(trace or {"counts": {}, "domain_filter_applied": None})},
                "selected_exercises": selected_list
            })

    session_instance = {
        "session_instance_version": "1.1",
        "generated_at": now_iso(),
        "context": {
            "location": location,
            "gym_id": gym_id,
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

    # ---------------------------
    # P0 contract: resolution_status
    # ---------------------------
    blocks = session_instance.get("resolved_session", {}).get("blocks", [])
    session_instance["resolution_status"] = "failed" if any(
        b.get("status") == "failed" for b in blocks
    ) else "success"

    # ---------------------------
    # P0 contract: no silent blocks (central normalization)
    # ---------------------------
    for b in session_instance.get("resolved_session", {}).get("blocks", []):
        # If status not set, infer deterministically from selection
        if b.get("status") is None:
            sel = b.get("selected_exercises") or []
            b["status"] = "selected" if sel else "skipped"
            if "message" not in b:
                b["message"] = None if sel else "No candidates after hard filters (P0)."


    out_full = os.path.join(repo_root, out_path)
    if write_output:
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
