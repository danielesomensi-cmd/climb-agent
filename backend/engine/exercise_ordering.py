"""
A121 — Phase-aware intra-session exercise ordering.

Pure sort module: derives sort categories from existing exercise fields,
then reorders exercises based on macrocycle phase priorities.

P0 INVARIANT: sort NEVER loses exercises. If anything goes wrong,
returns the original unsorted list as safe fallback.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sort categories (13 + 1 fallback)
# ---------------------------------------------------------------------------
SORT_CATEGORIES = [
    "warmup",
    "activation",
    "aerobic_pure",
    "threshold",
    "strength_neural",
    "power",
    "pe_intervals",
    "finger_endurance",
    "pulling_supplementary",
    "technique",
    "core",
    "antagonist_prehab",
    "cooldown",
    "main_unclassified",
]

# ---------------------------------------------------------------------------
# Derivation: infer sort category from exercise fields
# ---------------------------------------------------------------------------

def _norm(x: Any) -> str:
    return str(x).strip().lower() if x else ""


def _roles(exercise: dict) -> List[str]:
    role = exercise.get("role", "")
    raw = role if isinstance(role, list) else [role]
    return [_norm(r) for r in raw if _norm(r)]


def _first_domain(exercise: dict) -> str:
    domain = exercise.get("domain", "")
    if isinstance(domain, list):
        return _norm(domain[0]) if domain else ""
    return _norm(domain)


def _first_pattern(exercise: dict) -> str:
    pattern = exercise.get("pattern", "")
    if isinstance(pattern, list):
        return _norm(pattern[0]) if pattern else ""
    return _norm(pattern)


def infer_sort_category(exercise: dict) -> str:
    """
    Derive sort category from existing exercise fields (role, domain, pattern).
    Returns one of SORT_CATEGORIES. NEVER returns None.
    """
    roles = _roles(exercise)
    domain = _first_domain(exercise)
    pattern = _first_pattern(exercise)

    # --- Priority 0: prehab role (before domain check!) ---
    # Fix for active_finger_curls: role=prehab must win over domain=finger_strength
    if "prehab" in roles and "main" not in roles:
        return "antagonist_prehab"

    # --- Priority 1: role-based (unambiguous) ---
    if "warmup" in roles and "main" not in roles:
        return "warmup"
    if "cooldown" in roles:
        return "cooldown"
    if "activation" in roles and "main" not in roles:
        return "activation"

    # --- Priority 2: technique (before domain) ---
    if "technique" in roles:
        return "technique"
    if domain.startswith("technique_"):
        return "technique"

    # --- Priority 3: domain-based ---

    # Aerobic pure
    if domain in ("aerobic_capacity", "regeneration", "finger_aerobic_endurance"):
        return "aerobic_pure"

    # Strength neural
    if domain == "finger_max_strength":
        return "strength_neural"
    if domain == "contact_strength":
        return "strength_neural"

    # Power
    if domain == "power":
        return "power"

    # PE intervals
    if domain in ("power_endurance", "anaerobic_capacity"):
        return "pe_intervals"

    # Finger endurance
    if domain == "finger_strength_endurance":
        return "finger_endurance"

    # finger_strength (legacy umbrella) — disambiguate by pattern
    if domain == "finger_strength":
        if pattern == "isometric_hang":
            return "strength_neural"
        if pattern == "repeater_hang":
            return "finger_endurance"
        return "finger_endurance"  # safe default for legacy

    # Lock-off endurance (discovered in audit)
    if domain == "lock_off_endurance":
        return "pulling_supplementary"

    # Threshold / climbing volume
    if domain in ("endurance", "climbing_routes"):
        return "threshold"

    # Core
    if domain == "core":
        return "core"

    # Antagonist / prehab domains
    if domain in ("prehab_elbow", "prehab_finger", "prehab_shoulder", "prehab_wrist"):
        return "antagonist_prehab"

    # strength_general — disambiguate by pattern
    if domain == "strength_general":
        if pattern in ("pull_vertical", "pull_horizontal"):
            return "pulling_supplementary"
        return "antagonist_prehab"

    # strength_pulling
    if domain == "strength_pulling":
        return "pulling_supplementary"

    # Mobility / flexibility
    if domain in ("mobility", "flexibility"):
        return "cooldown"

    # Handstand
    if domain == "handstand_skill":
        return "core"

    # FALLBACK — never lose the exercise
    return "main_unclassified"


# ---------------------------------------------------------------------------
# Phase sort order maps
# ---------------------------------------------------------------------------
PHASE_SORT_ORDER: Dict[str, Dict[str, int]] = {
    "endurance_base": {
        "warmup": 0,
        "activation": 1,
        "aerobic_pure": 2,
        "threshold": 3,
        "finger_endurance": 4,
        "technique": 5,
        "pe_intervals": 6,
        "strength_neural": 6,
        "power": 6,
        "pulling_supplementary": 7,
        "core": 8,
        "antagonist_prehab": 9,
        "cooldown": 10,
        "main_unclassified": 6,
    },
    "strength_power": {
        "warmup": 0,
        "activation": 1,
        "strength_neural": 2,
        "power": 3,
        "pulling_supplementary": 4,
        "finger_endurance": 5,
        "threshold": 6,
        "technique": 7,
        "aerobic_pure": 8,
        "pe_intervals": 8,
        "core": 9,
        "antagonist_prehab": 10,
        "cooldown": 11,
        "main_unclassified": 6,
    },
    "power_endurance": {
        "warmup": 0,
        "activation": 1,
        "pe_intervals": 2,
        "finger_endurance": 3,
        "pulling_supplementary": 4,
        "threshold": 5,
        "technique": 6,
        "strength_neural": 7,
        "power": 7,
        "aerobic_pure": 8,
        "core": 9,
        "antagonist_prehab": 10,
        "cooldown": 11,
        "main_unclassified": 6,
    },
    "performance": {
        "warmup": 0,
        "activation": 1,
        "power": 2,
        "strength_neural": 2,
        "threshold": 3,
        "pe_intervals": 4,
        "technique": 5,
        "finger_endurance": 6,
        "pulling_supplementary": 6,
        "aerobic_pure": 7,
        "core": 8,
        "antagonist_prehab": 9,
        "cooldown": 10,
        "main_unclassified": 6,
    },
    "deload": {
        "warmup": 0,
        "aerobic_pure": 1,
        "technique": 2,
        "threshold": 3,
        "core": 4,
        "antagonist_prehab": 5,
        "cooldown": 6,
        "main_unclassified": 6,
        "activation": 6,
        "strength_neural": 6,
        "power": 6,
        "pe_intervals": 6,
        "finger_endurance": 6,
        "pulling_supplementary": 6,
    },
}


# ---------------------------------------------------------------------------
# Sort function
# ---------------------------------------------------------------------------
def sort_exercises_by_phase(exercises: list, phase: str) -> list:
    """
    Sort exercises by phase-aware physiological priority.

    PURE REORDER — never filters, never drops exercises.
    Same exercises in, same exercises out, guaranteed.
    """
    if not exercises:
        return exercises

    ids_before = set(ex.get("exercise_id", id(ex)) for ex in exercises)

    sort_order = PHASE_SORT_ORDER.get(phase)
    if sort_order is None:
        logger.warning("Unknown phase '%s' for exercise ordering — returning unsorted", phase)
        return exercises

    def sort_key(ex):
        category = infer_sort_category(ex)
        priority = sort_order.get(category, 6)
        return (priority, ex.get("exercise_id", ""))

    result = sorted(exercises, key=sort_key)

    # P0 INVARIANT: never lose exercises
    ids_after = set(ex.get("exercise_id", id(ex)) for ex in result)
    if ids_before != ids_after:
        logger.error(
            "EXERCISE LOSS DETECTED in sort_exercises_by_phase! "
            "Before: %d, After: %d. Returning UNSORTED list as safe fallback.",
            len(ids_before), len(ids_after),
        )
        return exercises

    return result


# ---------------------------------------------------------------------------
# Hard constraint enforcement
# ---------------------------------------------------------------------------
def enforce_ordering_constraints(exercises: list, phase: str) -> list:
    """
    Validate and fix hard ordering constraints AFTER sort.

    PURE REORDER — never filters, never drops exercises.
    Logs warnings when constraints are violated and auto-fixes.
    """
    if len(exercises) <= 1:
        return exercises

    ids_before = set(ex.get("exercise_id", id(ex)) for ex in exercises)
    result = list(exercises)

    def _cat(ex):
        return infer_sort_category(ex)

    # --- Constraint 1: Warmup always first ---
    warmup_indices = [i for i, ex in enumerate(result) if _cat(ex) == "warmup"]
    non_warmup_indices = [i for i, ex in enumerate(result) if _cat(ex) != "warmup"]
    if warmup_indices and non_warmup_indices and warmup_indices[0] > non_warmup_indices[0]:
        logger.warning("Constraint violation: warmup not first — auto-reordering")
        warmups = [result[i] for i in warmup_indices]
        others = [result[i] for i in range(len(result)) if i not in set(warmup_indices)]
        result = warmups + others

    # --- Constraint 2: Cooldown always last ---
    cooldown_indices = [i for i, ex in enumerate(result) if _cat(ex) == "cooldown"]
    non_cooldown_indices = [i for i, ex in enumerate(result) if _cat(ex) != "cooldown"]
    if cooldown_indices and non_cooldown_indices and cooldown_indices[-1] < non_cooldown_indices[-1]:
        logger.warning("Constraint violation: cooldown not last — auto-reordering")
        cooldowns = [result[i] for i in cooldown_indices]
        others = [result[i] for i in range(len(result)) if i not in set(cooldown_indices)]
        result = others + cooldowns

    # --- Constraint 3: ARC before pump ---
    aerobic_indices = [i for i, ex in enumerate(result) if _cat(ex) == "aerobic_pure"]
    pump_indices = [i for i, ex in enumerate(result) if _cat(ex) in ("threshold", "pe_intervals")]
    if aerobic_indices and pump_indices and max(aerobic_indices) > min(pump_indices):
        logger.warning("Constraint violation: aerobic_pure after pump-causing exercise — auto-reordering")
        aerobics = [result[i] for i in aerobic_indices]
        others = [result[i] for i in range(len(result)) if i not in set(aerobic_indices)]
        first_pump = next(i for i, ex in enumerate(others) if _cat(ex) in ("threshold", "pe_intervals"))
        result = others[:first_pump] + aerobics + others[first_pump:]

    # --- Constraint 4: Max hangs before pulling volume ---
    neural_indices = [i for i, ex in enumerate(result) if _cat(ex) == "strength_neural"]
    pulling_indices = [i for i, ex in enumerate(result) if _cat(ex) == "pulling_supplementary"]
    if neural_indices and pulling_indices and max(neural_indices) > min(pulling_indices):
        logger.warning("Constraint violation: strength_neural after pulling_supplementary — auto-reordering")
        neurals = [result[i] for i in neural_indices]
        others = [result[i] for i in range(len(result)) if i not in set(neural_indices)]
        first_pull = next(i for i, ex in enumerate(others) if _cat(ex) == "pulling_supplementary")
        result = others[:first_pull] + neurals + others[first_pull:]

    # --- Constraint 5: Accessories after main work ---
    accessory_cats = {"core", "antagonist_prehab"}
    main_cats = {
        "aerobic_pure", "threshold", "strength_neural", "power", "pe_intervals",
        "finger_endurance", "pulling_supplementary", "technique",
    }
    accessory_indices = [i for i, ex in enumerate(result) if _cat(ex) in accessory_cats]
    main_indices = [i for i, ex in enumerate(result) if _cat(ex) in main_cats]
    if accessory_indices and main_indices and min(accessory_indices) < max(main_indices):
        logger.warning("Constraint violation: accessory before main work — auto-reordering")
        accessories = [result[i] for i in accessory_indices]
        others = [result[i] for i in range(len(result)) if i not in set(accessory_indices)]
        last_main = max(
            (i for i, ex in enumerate(others) if _cat(ex) in main_cats),
            default=len(others),
        )
        result = others[:last_main + 1] + accessories + others[last_main + 1:]

    # P0 INVARIANT: never lose exercises
    ids_after = set(ex.get("exercise_id", id(ex)) for ex in result)
    if ids_before != ids_after:
        logger.error(
            "EXERCISE LOSS DETECTED in enforce_ordering_constraints! "
            "Returning input list as safe fallback."
        )
        return exercises

    return result
