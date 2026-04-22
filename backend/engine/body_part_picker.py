"""Body Part Picker (A213) — strength-focused session generator.

Maps catalog exercises to body-part categories, filters by equipment, and
generates a resolver-light session (warmup → body-part blocks → cooldown)
ready for inline insertion into a week plan.

Design notes:
- Resolver light: applies ``prescription_defaults`` + ``working_loads`` lookup
  + ``suggest_max_hang_load``. No closed-loop writes, no progression_v1.
- Sessions carry ``session_mode="custom_build"`` + ``build_kind="body_parts"``
  + ``is_custom=True`` so the Today/Week/session-card frontend renders them
  via the existing A207 custom path.
"""

from __future__ import annotations

import json
import logging
import random
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Set

from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS, expand_equipment
from backend.engine.resolve_session import (
    _apply_load_override,
    score_exercise,
    suggest_max_hang_load,
)

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────

OVERHEAD_MIN: Dict[str, int] = {"warmup": 10, "cooldown": 5, "transition": 1}
N_PER_BODY_PART: int = 2

# B218 Bug 4: inline warmup catalog IDs (data-driven — looked up at generation
# time, passed through the same resolver-light as the main block).
WARMUP_EXERCISE_IDS: List[str] = ["general_pulse_raise", "dynamic_mobility_flow"]


# Per-category definition: display metadata + classification rules.
# Classification rules are applied in priority order:
#   1. exclude_ids / exclude_patterns   → hard drop
#   2. include_ids                       → force include
#   3. domains / patterns match          → include
#   4. "push" pattern + name token match → include (triceps/chest only)
BODY_PART_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "fingers": {
        "label": "Fingers",
        "description": "Max hang, repeaters, grip work",
        "icon": "fingerprint",
        "stub_duration_min": 15,
        "enabled": True,
        "classification_rules": {
            "domains": [
                "finger_strength", "finger_max_strength",
                "finger_strength_endurance", "finger_aerobic_endurance",
                "contact_strength",
            ],
            "patterns": [
                "isometric_hang", "repeater_hang", "grip_transition",
                "isometric_lift", "repeater_lift", "isometric_explosive",
                "explosive_brief",
            ],
            "exclude_patterns": [],
            "include_ids": ["pinch_block_training", "power_slap_drill"],
            "exclude_ids": [],
        },
    },
    "forearms": {
        "label": "Forearms",
        "description": "Wrist prehab, pronation/supination, carry",
        "icon": "hand",
        "stub_duration_min": 8,
        "enabled": True,
        "classification_rules": {
            "domains": ["prehab_wrist", "prehab_finger"],
            "patterns": [
                "wrist_extension", "wrist_flexion",
                "forearm_pronation", "forearm_supination",
                "finger_extension", "tendon_glide",
            ],
            "exclude_patterns": [],
            "include_ids": ["farmers_carry"],
            "exclude_ids": [],
        },
    },
    "back_pulling": {
        "label": "Back / Pulling",
        "description": "Pull-up, row, lock-off",
        "icon": "biceps-flexed",
        "stub_duration_min": 12,
        "enabled": True,
        "classification_rules": {
            "domains": ["strength_pulling", "lock_off_endurance"],
            "patterns": ["pull_vertical", "pull_horizontal"],
            "exclude_patterns": [],
            "include_ids": ["chinup", "inverted_row", "barbell_row"],
            "exclude_ids": [],
        },
    },
    "biceps": {
        "label": "Biceps",
        "description": "Elbow flexion isolation",
        "icon": "biceps-flexed",
        "stub_duration_min": 8,
        "enabled": True,
        "classification_rules": {
            "domains": [],
            "patterns": ["elbow_flexion"],
            "exclude_patterns": [],
            "include_ids": ["chinup", "bicep_curl"],
            "exclude_ids": [],
        },
    },
    "triceps": {
        "label": "Triceps",
        "description": "Dips, press, overhead extension",
        "icon": "dumbbell",
        "stub_duration_min": 8,
        "enabled": True,
        "classification_rules": {
            "domains": [],
            "patterns": [],
            "exclude_patterns": [],
            "include_ids": [
                "dip", "pike_pushup", "handstand_pushup_wall",
                "overhead_press", "bench_press",
                "overhead_tricep_extension", "ring_pushup",
            ],
            "exclude_ids": [],
            "push_name_match": ["tricep", "extension", "dip", "pushdown"],
        },
    },
    "chest": {
        "label": "Chest",
        "description": "Push-up, bench press, fly",
        "icon": "dumbbell",
        "stub_duration_min": 10,
        "enabled": True,
        "classification_rules": {
            "domains": [],
            "patterns": [],
            "exclude_patterns": [],
            "include_ids": [
                "pushup", "dip", "bench_press", "dumbbell_bench_press",
                "ring_pushup", "dumbbell_fly", "incline_pushup",
            ],
            "exclude_ids": [],
            "push_name_match": ["push-up", "pushup", "press", "fly"],
        },
    },
    "shoulders": {
        "label": "Shoulders",
        "description": "Press, lateral raise, scap control",
        "icon": "dumbbell",
        "stub_duration_min": 10,
        "enabled": True,
        "classification_rules": {
            "domains": ["prehab_shoulder", "handstand_skill"],
            "patterns": ["scapular_control", "shoulder_isolation"],
            "exclude_patterns": [],
            "include_ids": ["overhead_press", "lateral_raise", "face_pull"],
            "exclude_ids": [],
        },
    },
    "core": {
        "label": "Core",
        "description": "Anti-extension, anti-rotation, compression",
        "icon": "flame",
        "stub_duration_min": 10,
        "enabled": True,
        "classification_rules": {
            "domains": ["core", "handstand_skill"],
            "patterns": [
                "anti_extension", "anti_rotation", "anti_lateral_flexion",
                "compression", "isometric_hold",
            ],
            "exclude_patterns": [],
            "include_ids": [],
            "exclude_ids": [],
        },
    },
    "glutes": {
        "label": "Glutes",
        "description": "Hinge, bridge, single-leg work",
        "icon": "dumbbell",
        "stub_duration_min": 10,
        "enabled": True,
        "classification_rules": {
            "domains": [],
            "patterns": ["hinge"],
            "exclude_patterns": [],
            "include_ids": [
                "glute_bridge", "romanian_deadlift", "split_squat",
                "pistol_squat_progression", "reverse_lunge", "nordic_curl",
                "single_leg_glute_bridge", "single_leg_rdl",
            ],
            "exclude_ids": [],
        },
    },
    "hips": {
        "label": "Hips",
        "description": "Abduction, adduction, flexor isolation",
        "icon": "circle-dot",
        "stub_duration_min": 8,
        "enabled": True,  # C208+C209 shipped the catalog support
        "classification_rules": {
            "domains": [],
            "patterns": ["hip_isolation"],
            "exclude_patterns": [],
            "include_ids": [
                "hip_flexor_strengthening", "copenhagen_adductor_plank",
                "hip_90_90_switch",
            ],
            "exclude_ids": [],
        },
    },
    "legs": {
        "label": "Legs",
        "description": "Squat, lunge, calf",
        "icon": "footprints",
        "stub_duration_min": 12,
        "enabled": True,
        "classification_rules": {
            "domains": [],
            "patterns": ["squat", "lunge", "calf_raise"],
            "exclude_patterns": [],
            "include_ids": [
                "step_ups", "goblet_squat", "nordic_curl",
                "cossack_squat", "bulgarian_split_squat",
            ],
            "exclude_ids": [],
        },
    },
}

# Ordered list for the frontend grid
BODY_PART_ORDER: List[str] = [
    "fingers", "forearms", "back_pulling", "biceps", "triceps",
    "chest", "shoulders", "core", "glutes", "hips", "legs",
]


# ── Catalog helpers ───────────────────────────────────────────────────────


def _ex_domains(ex: Dict[str, Any]) -> List[str]:
    d = ex.get("domain")
    if isinstance(d, str):
        return [d]
    return list(d or [])


def _ex_patterns(ex: Dict[str, Any]) -> List[str]:
    """A catalog exercise may have one pattern (str) or multiple."""
    p = ex.get("pattern")
    if isinstance(p, str):
        return [p]
    return list(p or [])


def _match_category_raw(exercise: Dict[str, Any], rules: Dict[str, Any]) -> bool:
    """Match a single exercise against a category's classification rules.

    Cross-category exclusions (e.g. biceps minus forearms) are applied
    afterwards by ``build_body_part_index()``.
    """
    ex_id = exercise.get("id")
    if ex_id in rules.get("exclude_ids", []):
        return False

    ex_patterns = _ex_patterns(exercise)
    exclude_patterns = rules.get("exclude_patterns", [])
    if any(p in exclude_patterns for p in ex_patterns):
        return False

    if ex_id in rules.get("include_ids", []):
        return True

    ex_domain_list = _ex_domains(exercise)
    if any(d in rules.get("domains", []) for d in ex_domain_list):
        return True

    if any(p in rules.get("patterns", []) for p in ex_patterns):
        return True

    push_tokens = rules.get("push_name_match") or []
    if push_tokens and "push" in ex_patterns:
        name_lower = (exercise.get("name") or "").lower()
        if any(tok.lower() in name_lower for tok in push_tokens):
            return True

    return False


def _is_climbing_surface_exercise(exercise: Dict[str, Any]) -> bool:
    """Exclude boulder/route problems from body-part classification."""
    req = exercise.get("equipment_required") or []
    if isinstance(req, str):
        req = [req]
    climbing = {"gym_boulder", "gym_routes", "spraywall", "homewall"}
    boards = {"board_kilter", "board_moonboard", "board_other", "campus_board"}
    return bool(set(req) & (climbing | boards))


def build_body_part_index(
    catalog: Sequence[Dict[str, Any]],
) -> Dict[str, Set[str]]:
    """Return ``{body_part_id: set(exercise_ids)}`` with cross-category rules.

    Exclusions applied (D217 noise fixes):
      - forearms drops anything already in fingers (hangboard overlap)
      - biceps drops anything in forearms (wrist-curl overlap)
    """
    index: Dict[str, Set[str]] = {cat: set() for cat in BODY_PART_CATEGORIES}
    for ex in catalog:
        if _is_climbing_surface_exercise(ex):
            continue
        ex_id = ex.get("id")
        if not ex_id:
            continue
        for cat, meta in BODY_PART_CATEGORIES.items():
            if _match_category_raw(ex, meta["classification_rules"]):
                index[cat].add(ex_id)

    index["forearms"] -= index["fingers"]
    index["biceps"] -= index["forearms"]
    return index


def classify_exercise_body_parts(
    exercise: Dict[str, Any],
    catalog: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[str]:
    """Return body-part category IDs this exercise belongs to.

    If ``catalog`` is provided, cross-category exclusions are applied
    (recommended for UI use). Without catalog, raw rule matches are returned.
    """
    if _is_climbing_surface_exercise(exercise):
        return []
    if catalog is not None:
        index = build_body_part_index(catalog)
        ex_id = exercise.get("id")
        return [cat for cat in BODY_PART_ORDER if ex_id in index.get(cat, set())]
    return [
        cat for cat in BODY_PART_ORDER
        if _match_category_raw(
            exercise, BODY_PART_CATEGORIES[cat]["classification_rules"]
        )
    ]


# ── Equipment mode resolution ─────────────────────────────────────────────


def resolve_equipment_mode(
    mode: str,
    user_state: Dict[str, Any],
    gym_id: Optional[str] = None,
) -> List[str]:
    """Expand equipment list per the chosen mode.

    Modes:
      bodyweight → ``[]``
      home       → expand(user_state.equipment.home)
      gym        → expand(gym[gym_id].equipment) — union of all gyms if None
      all        → sorted(KNOWN_EQUIPMENT_KEYS)
    """
    eq = user_state.get("equipment") or {}
    if mode == "bodyweight":
        return []
    if mode == "all":
        return sorted(KNOWN_EQUIPMENT_KEYS)
    if mode == "home":
        return expand_equipment(eq.get("home") or [])
    if mode == "gym":
        gyms = eq.get("gyms") or []
        if gym_id:
            target = next((g for g in gyms if g.get("gym_id") == gym_id), None)
            if target is not None:
                return expand_equipment(target.get("equipment") or [])
            logger.warning("resolve_equipment_mode: gym_id %r not found", gym_id)
            return []
        union: Set[str] = set()
        for g in gyms:
            union.update(g.get("equipment") or [])
        return expand_equipment(sorted(union))
    logger.warning("resolve_equipment_mode: unknown mode %r", mode)
    return []


def _exercise_fits_equipment(
    exercise: Dict[str, Any], equipment: Sequence[str]
) -> bool:
    req = exercise.get("equipment_required") or []
    if isinstance(req, str):
        req = [req]
    if not req:
        return True
    eq_set = set(equipment)
    return set(req).issubset(eq_set)


# ── Availability for /options endpoint ────────────────────────────────────


def get_available_body_parts(
    exercises_catalog: Sequence[Dict[str, Any]],
    equipment: Sequence[str],
) -> List[Dict[str, Any]]:
    """Return body-part categories enriched with per-equipment exercise counts."""
    index = build_body_part_index(exercises_catalog)
    by_id = {e["id"]: e for e in exercises_catalog if "id" in e}
    out: List[Dict[str, Any]] = []
    for cat in BODY_PART_ORDER:
        meta = BODY_PART_CATEGORIES[cat]
        compatible = [
            ex_id for ex_id in index[cat]
            if ex_id in by_id and _exercise_fits_equipment(by_id[ex_id], equipment)
        ]
        out.append({
            "id": cat,
            "label": meta["label"],
            "description": meta["description"],
            "icon": meta["icon"],
            "enabled": meta["enabled"] and len(compatible) > 0,
            "exercise_count": len(compatible),
            "stub_duration_min": meta["stub_duration_min"],
        })
    return out


# ── Selection ─────────────────────────────────────────────────────────────


def _recent_exercise_ids(user_state: Dict[str, Any]) -> List[str]:
    """Flatten recent_sessions[].exercises[*].exercise_id (last N sessions)."""
    out: List[str] = []
    for s in (user_state.get("recent_sessions") or [])[-8:]:
        for ex in (s.get("exercises") or []):
            eid = ex.get("exercise_id") or ex.get("id")
            if eid:
                out.append(eid)
    return out


def _recent_recency_groups(user_state: Dict[str, Any]) -> Set[str]:
    """Build a set of recency_group values used in recent sessions."""
    return set(
        (user_state.get("stimulus_recency") or {}).keys()
    )


def select_exercises_for_part(
    body_part: str,
    exercises_pool: Sequence[Dict[str, Any]],
    equipment: Sequence[str],
    already_selected: Set[str],
    user_state: Dict[str, Any],
    n: int = N_PER_BODY_PART,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Pick up to ``n`` exercises for ``body_part`` from ``exercises_pool``.

    Scoring combines ``score_exercise()`` (recency + preferences) with a small
    tiebreaker to keep selection deterministic given a seed.
    """
    if body_part not in BODY_PART_CATEGORIES:
        return []
    by_id = {e["id"]: e for e in exercises_pool if "id" in e}
    index = build_body_part_index(exercises_pool)
    candidate_ids = index.get(body_part, set()) - already_selected
    candidates = [by_id[i] for i in candidate_ids if i in by_id]
    candidates = [c for c in candidates if _exercise_fits_equipment(c, equipment)]
    if not candidates:
        return []

    prefs = (user_state.get("preferences") or {})
    recent_ids = _recent_exercise_ids(user_state)
    recent_groups = _recent_recency_groups(user_state)

    rng = random.Random(seed)
    scored = []
    for ex in candidates:
        base = score_exercise(ex, prefs, recent_ids, recent_groups)
        jitter = rng.random() * 0.1
        scored.append((base + jitter, ex))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [ex for _, ex in scored[:n]]


# ── Resolver light ─────────────────────────────────────────────────────────


def apply_resolver_light(
    exercise: Dict[str, Any],
    user_state: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an exercise instance with prescription + suggested loads.

    Mirrors resolve_session's A207 custom path (D217 §5):
      1. Copy prescription_defaults.
      2. Apply overrides.per_exercise (absolute / delta / multiplier).
      3. If working_loads has an entry → set suggested_external_load_kg.
      4. Else if total_load + hangboard baseline → suggest_max_hang_load.
      5. Else → leave load unset.

    B218 Bug 2: prescription fields are also promoted to top-level so the
    session-card `is_custom` branch (which mirrors CustomSessionExercise A206)
    renders sets/reps/rest correctly. ``prescription`` is kept as a sub-object
    for consumers that expect the resolver shape.
    """
    ex_id = exercise.get("id")
    defaults = deepcopy(exercise.get("prescription_defaults") or {})
    instance: Dict[str, Any] = {
        "exercise_id": ex_id,
        "name": exercise.get("name", ex_id),
        "category": exercise.get("category"),
        "pattern": exercise.get("pattern"),
        "load_model": exercise.get("load_model"),
        "prescription": defaults,
    }

    # Step 2 — overrides
    instance["prescription"] = _apply_load_override(
        instance["prescription"],
        user_state=user_state,
        exercise_id=ex_id or "",
    )

    # B218 Bug 2: promote to top-level (CustomSessionExercise shape).
    p = instance["prescription"] or {}
    instance["sets"] = int(p.get("sets") or 1)
    instance["reps"] = p.get("reps") if p.get("reps") is not None else None
    instance["work_seconds"] = p.get("work_seconds")
    instance["rest_between_sets_seconds"] = p.get("rest_between_sets_seconds")
    instance["rest_between_reps_seconds"] = p.get("rest_between_reps_seconds")
    instance["load_kg"] = p.get("load_kg") or 0
    instance["notes"] = p.get("notes") or ""

    # Step 3 — working_loads lookup
    wl_entries = (user_state.get("working_loads") or {}).get("entries") or []
    wl_match = next(
        (e for e in wl_entries if e.get("exercise_id") == ex_id),
        None,
    )
    if wl_match:
        next_ext = wl_match.get("next_external_load_kg")
        next_tot = wl_match.get("next_total_load_kg")
        if next_ext is not None:
            instance["suggested_external_load_kg"] = next_ext
        if next_tot is not None:
            instance["suggested_total_load_kg"] = next_tot
        instance["load_source"] = "working_loads"
        return instance

    # Step 4 — hangboard baseline for total_load
    if exercise.get("load_model") == "total_load":
        suggestion = suggest_max_hang_load(
            user_state,
            instance["prescription"],
            exercise_attrs=exercise.get("attributes"),
        )
        if suggestion:
            instance["max_hang_suggestion"] = suggestion
            instance["load_source"] = "hangboard_baseline"
            return instance

    # Step 5 — no load
    instance["load_source"] = "unset"
    return instance


# ── Duration estimate ─────────────────────────────────────────────────────


def estimate_duration_stub(
    body_parts: Sequence[str],
    include_cooldown: bool = True,
) -> int:
    """Live-counter duration estimate from stubs. No catalog lookup."""
    if not body_parts:
        return 0
    total = OVERHEAD_MIN["warmup"]
    total += sum(
        BODY_PART_CATEGORIES[p]["stub_duration_min"]
        for p in body_parts
        if p in BODY_PART_CATEGORIES
    )
    total += max(0, len(body_parts) - 1) * OVERHEAD_MIN["transition"]
    if include_cooldown:
        total += OVERHEAD_MIN["cooldown"]
    return total


def _estimate_exercise_minutes(
    exercise: Dict[str, Any], prescription: Dict[str, Any]
) -> float:
    """Rough per-exercise duration in minutes."""
    sets = int(prescription.get("sets") or 1)
    reps = prescription.get("reps")
    work_s = prescription.get("work_seconds")
    rest_sets = prescription.get("rest_between_sets_seconds") or 60
    rest_reps = prescription.get("rest_between_reps_seconds") or 0

    if work_s:
        if reps and isinstance(reps, int) and reps > 1:
            per_set = reps * float(work_s) + max(0, reps - 1) * float(rest_reps)
        else:
            per_set = float(work_s)
    elif reps and isinstance(reps, (int, float)):
        per_set = float(reps) * 4.0
    else:
        per_set = 30.0

    total = sets * per_set + max(0, sets - 1) * float(rest_sets)
    return total / 60.0


# ── Main entry point ──────────────────────────────────────────────────────


def generate_body_part_session(
    body_parts: Sequence[str],
    equipment_mode: str,
    gym_id: Optional[str],
    user_state: Dict[str, Any],
    exercises_catalog: Sequence[Dict[str, Any]],
    include_cooldown: bool = True,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Main entry point — generate a full session dict ready for week insertion.

    Returns a session with shape compatible with A207 custom sessions:
      session_mode="custom_build", is_custom=True, build_kind="body_parts",
      exercises=[...] already resolved (resolver-light),
      body_parts_selected=[...], equipment_mode, gym_id.
    """
    equipment = resolve_equipment_mode(equipment_mode, user_state, gym_id)

    # 1. Select exercises
    already: Set[str] = set()
    blocks: List[Dict[str, Any]] = []
    for part in body_parts:
        picks = select_exercises_for_part(
            part, exercises_catalog, equipment, already, user_state,
            n=N_PER_BODY_PART, seed=seed,
        )
        if not picks:
            continue
        for ex in picks:
            already.add(ex["id"])
        blocks.append({"body_part": part, "exercises": picks})

    # 2. Resolve to instances — prepend warmup (B218 Bug 4).
    by_id = {e["id"]: e for e in exercises_catalog if "id" in e}
    exercise_instances: List[Dict[str, Any]] = []
    for wid in WARMUP_EXERCISE_IDS:
        wex = by_id.get(wid)
        if wex is None:
            continue
        winst = apply_resolver_light(wex, user_state)
        winst["module_role"] = "warmup"
        winst["body_part"] = "warmup"
        exercise_instances.append(winst)

    for block in blocks:
        for ex in block["exercises"]:
            inst = apply_resolver_light(ex, user_state)
            inst["module_role"] = "main"
            inst["body_part"] = block["body_part"]
            exercise_instances.append(inst)

    # 3. Compute duration from resolved prescriptions (more accurate than stub).
    # B218 Bug 4: warmup exercises are now in exercise_instances — no flat
    # warmup baseline added anymore (was double-counting).
    core_minutes = sum(
        _estimate_exercise_minutes(
            {"id": i.get("exercise_id")}, i.get("prescription") or {},
        )
        for i in exercise_instances
    )
    duration = int(round(core_minutes))
    duration += max(0, len(body_parts) - 1) * OVERHEAD_MIN["transition"]
    if include_cooldown:
        duration += OVERHEAD_MIN["cooldown"]

    # 4. Compute load score (same fatigue_cost * 1.5 cap 85 formula)
    by_id = {e["id"]: e for e in exercises_catalog if "id" in e}
    raw_load = sum(
        (by_id.get(i["exercise_id"]) or {}).get("fatigue_cost", 0)
        for i in exercise_instances
    )
    load_score = int(round(min(85, raw_load * 1.5)))

    labels = [
        BODY_PART_CATEGORIES[p]["label"] for p in body_parts
        if p in BODY_PART_CATEGORIES
    ]
    session_name = "Body Part Training"
    if labels:
        session_name = f"Body Part Training — {', '.join(labels)}"

    return {
        "session_mode": "custom_build",
        "build_kind": "body_parts",
        "is_custom": True,
        "name": session_name,
        "body_parts_selected": list(body_parts),
        "equipment_mode": equipment_mode,
        "gym_id": gym_id,
        "include_cooldown": include_cooldown,
        "exercises": exercise_instances,
        "estimated_duration_minutes": duration,
        "estimated_load_score": load_score,
        "intensity": "medium",
        "tags": {"hard": False, "finger": "fingers" in body_parts},
    }
