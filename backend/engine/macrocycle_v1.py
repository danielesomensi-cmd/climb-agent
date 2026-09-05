"""Macrocycle generator v1 — Hörst 4-3-2-1 adaptive periodization with DUP."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

from backend.engine.assessment_v1 import _GRADE_INDEX, grade_gap
from backend.engine.grade_mapping import BOULDER_TO_LEAD
from backend.engine.start_date_utils import strict_next_monday

# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

PHASE_ORDER: Tuple[str, ...] = ("base", "strength_power", "power_endurance", "performance", "deload")

PHASE_NAMES: Dict[str, str] = {
    "base": "Endurance Base",
    "strength_power": "Strength & Power",
    "power_endurance": "Power Endurance",
    "performance": "Performance",
    "deload": "Deload",
}

PHASE_NAMES_BOULDER: Dict[str, str] = {
    "base": "Movement & Volume Base",
    "strength_power": "Max Strength & Power",
    "power_endurance": "Work Capacity",
    "performance": "Projecting & Peak",
    "deload": "Deload",
}

PHASE_ENERGY: Dict[str, str] = {
    "base": "aerobic",
    "strength_power": "anaerobic_alactic",
    "power_endurance": "anaerobic_lactic",
    "performance": "specific",
    "deload": "recovery",
}

PHASE_INTENSITY_CAP: Dict[str, str] = {
    "base": "medium",
    "strength_power": "max",
    "power_endurance": "high",
    "performance": "max",
    "deload": "low",
}

# Base domain weights per phase (from design doc §4.3)
# Keys: finger_strength, pulling_strength, power_endurance, volume_climbing, technique, core_prehab
_BASE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "base": {
        "finger_strength": 0.20, "pulling_strength": 0.15, "power_endurance": 0.15,
        "volume_climbing": 0.25, "technique": 0.20, "core_prehab": 0.10,
    },
    "strength_power": {
        "finger_strength": 0.35, "pulling_strength": 0.25, "power_endurance": 0.10,
        "volume_climbing": 0.10, "technique": 0.10, "core_prehab": 0.10,
    },
    "power_endurance": {
        "finger_strength": 0.15, "pulling_strength": 0.10, "power_endurance": 0.35,
        "volume_climbing": 0.15, "technique": 0.15, "core_prehab": 0.10,
    },
    "performance": {
        "finger_strength": 0.10, "pulling_strength": 0.05, "power_endurance": 0.20,
        "volume_climbing": 0.25, "technique": 0.25, "core_prehab": 0.15,
    },
    "deload": {
        "finger_strength": 0.05, "pulling_strength": 0.05, "power_endurance": 0.05,
        "volume_climbing": 0.10, "technique": 0.05, "core_prehab": 0.10,
    },
}

# Session pool per phase: (★ = primary, ○ = available)
_SESSION_POOL: Dict[str, Dict[str, str]] = {
    "base": {
        "endurance_aerobic_gym": "primary",
        "technique_focus_gym": "primary",
        "finger_maintenance_home": "primary",
        "finger_maintenance_gym": "primary",
        "boulder_circuit_gym": "primary",
        "prehab_maintenance": "primary",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "complementary_conditioning": "available",
        "route_endurance_gym": "available",
        "finger_endurance_short": "available",
        "finger_aerobic_base": "available",
    },
    "strength_power": {
        "power_contact_gym": "primary",
        "limit_boulder_gym": "primary",
        "strength_long": "primary",
        "finger_strength_home": "primary",
        "prehab_maintenance": "primary",
        "technique_focus_gym": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "complementary_conditioning": "available",
        "finger_maintenance_gym": "available",
        "finger_endurance_short": "available",
        "route_endurance_gym": "available",
    },
    "power_endurance": {
        "power_endurance_gym": "primary",
        "prehab_maintenance": "primary",
        "technique_focus_gym": "available",
        "finger_strength_home": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "endurance_aerobic_gym": "available",
        "route_endurance_gym": "available",
    },
    "performance": {
        "technique_focus_gym": "primary",
        "route_projecting_gym": "primary",
        "prehab_maintenance": "primary",
        "power_endurance_gym": "available",
        "power_contact_gym": "available",
        "boulder_circuit_gym": "available",
        "route_endurance_gym": "available",
        "limit_boulder_gym": "available",
        "finger_strength_home": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
    },
    "deload": {
        "regeneration_easy": "primary",
        "flexibility_full": "primary",
        "yoga_recovery": "primary",
        "prehab_maintenance": "primary",
        "easy_climbing_deload": "available",
        "deload_recovery": "available",
        "finger_aerobic_base": "available",
    },
}

# ---------------------------------------------------------------------------
# Boulder-specific weights and session pools
# ---------------------------------------------------------------------------

_BASE_WEIGHTS_BOULDER: Dict[str, Dict[str, float]] = {
    "base": {
        "finger_strength": 0.20, "pulling_strength": 0.15, "power_endurance": 0.05,
        "volume_climbing": 0.35, "technique": 0.20, "core_prehab": 0.10,
    },
    "strength_power": {
        "finger_strength": 0.40, "pulling_strength": 0.25, "power_endurance": 0.10,
        "volume_climbing": 0.10, "technique": 0.10, "core_prehab": 0.10,
    },
    "power_endurance": {
        "finger_strength": 0.20, "pulling_strength": 0.15, "power_endurance": 0.30,
        "volume_climbing": 0.20, "technique": 0.10, "core_prehab": 0.10,
    },
    "performance": {
        "finger_strength": 0.15, "pulling_strength": 0.10, "power_endurance": 0.15,
        "volume_climbing": 0.30, "technique": 0.25, "core_prehab": 0.10,
    },
    "deload": {
        "finger_strength": 0.05, "pulling_strength": 0.05, "power_endurance": 0.05,
        "volume_climbing": 0.10, "technique": 0.05, "core_prehab": 0.10,
    },
}

_SESSION_POOL_BOULDER: Dict[str, Dict[str, str]] = {
    "base": {
        "boulder_circuit_gym": "primary",
        "technique_focus_gym": "primary",
        "finger_maintenance_home": "primary",
        "prehab_maintenance": "primary",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "complementary_conditioning": "available",
        "core_training": "available",
    },
    "strength_power": {
        "power_contact_gym": "primary",
        "limit_boulder_gym": "primary",
        "strength_long": "primary",
        "finger_strength_home": "primary",
        "prehab_maintenance": "primary",
        "technique_focus_gym": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "complementary_conditioning": "available",
        "core_training": "available",
    },
    "power_endurance": {
        "boulder_circuit_gym": "primary",
        "prehab_maintenance": "primary",
        "technique_focus_gym": "available",
        "finger_strength_home": "available",
        "flexibility_full": "available",
        "core_training": "available",
    },
    "performance": {
        "technique_focus_gym": "primary",
        "limit_boulder_gym": "primary",
        "prehab_maintenance": "primary",
        "power_contact_gym": "available",
        "boulder_circuit_gym": "available",
        "finger_strength_home": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "core_training": "available",
    },
    "deload": {
        "regeneration_easy": "primary",
        "flexibility_full": "primary",
        "yoga_recovery": "primary",
        "prehab_maintenance": "primary",
        "easy_climbing_deload": "available",
        "deload_recovery": "available",
        "finger_aerobic_base": "available",
    },
}

# ---------------------------------------------------------------------------
# Phase duration computation (A218 / A-MACRO-CAPS)
#
# Hard caps and floors per discipline. The new algorithm:
#   1. Initialize at defaults.
#   2. Apply weakness shift, clamped to floors and caps (no silent self-cancel).
#   3. Distribute surplus to caps in priority order, OR
#      reduce shortfall in INVERSE priority order (never below floor).
#
# A single function (`_compute_phase_durations`) handles both full and
# incremental regen via an optional `phases` scope parameter.
# ---------------------------------------------------------------------------

# Mapping from assessment profile axes to weakness adjustment phases.
# axis → (extend_phase, shrink_phase). Unchanged from earlier versions.
_WEAKNESS_ADJUSTMENTS: Dict[str, Tuple[str, str]] = {
    "power_endurance":  ("power_endurance",  "strength_power"),
    "endurance":        ("base",             "strength_power"),
    "finger_strength":  ("strength_power",   "base"),
    "pulling_strength": ("strength_power",   "base"),
    "technique":        ("base",             "performance"),
}

# Lead / all_round / both
_BASE_DURATIONS_LEAD: Dict[str, int] = {
    "base": 4, "strength_power": 3, "power_endurance": 2,
    "performance": 2, "deload": 1,
}  # sum 12
_PHASE_CAPS_LEAD: Dict[str, int] = {
    "base": 4, "strength_power": 4, "power_endurance": 3,
    "performance": 3, "deload": 2,
}  # sum 16 (== _MAX_TOTAL_WEEKS)
_PHASE_FLOORS_LEAD: Dict[str, int] = {
    "base": 2, "strength_power": 2, "power_endurance": 2,
    "performance": 2, "deload": 1,
}  # sum 9 — deliberately BELOW _MIN_TOTAL_WEEKS_LEAD, see below

# A284. Two different questions, two different floors:
#   _PHASE_FLOORS_*  — the absolute minimum a phase may ever be. Validates
#                      explicit athlete overrides, and backs the postcondition.
#   _AUTO_FLOORS_*   — the minimum the engine will go down to ON ITS OWN, i.e.
#                      through the weakness shift or shortfall reduction.
# They differ only for lead `base`: an athlete may ask for 2, but the engine
# must never take base below 4 by itself. Without this split, dropping the floor
# to 2 would silently un-block the finger/pulling weakness shift — which is a
# no-op today — and every lead athlete with weak fingers would get a different
# plan on their next regeneration. That is precisely what this brief must not do.
_AUTO_FLOORS_LEAD: Dict[str, int] = {**_PHASE_FLOORS_LEAD, "base": 4}
_SURPLUS_PRIORITY_LEAD: Tuple[str, ...] = (
    "performance", "strength_power", "power_endurance", "deload",
)
# A284: `base` is no longer locked at 4 (it used to have floor==cap==4), but it
# stays OUT of the priority list on purpose — surplus and shortfall must not
# touch it. The default is still 4: the only way to get a shorter base is to ask
# for it explicitly via `planning_prefs.phase_weeks`, so no existing plan moves.
#
# Why the floor dropped: 4 weeks is right for an athlete opening a cycle from
# rest, and wrong for one coming back from a climbing trip, where volume, finger
# aerobic capacity and technique are at their yearly peak and the only decayed
# quality is maximal strength. The engine cannot tell the two apart — it does not
# read `outdoor_log` (see A-DECLARED-VS-LOGGED-GRADE) — so the athlete says it.
#
# NOTE: the floors no longer sum to _MIN_TOTAL_WEEKS_LEAD, and that is
# intentional. They answer different questions: the floors are per-phase minima,
# _MIN_TOTAL_WEEKS_LEAD is a KB judgement about the shortest lead cycle worth
# running (A218). Before A284 the two coincided by construction; now they don't.
_MIN_TOTAL_WEEKS_LEAD = 11

# Boulder
_BASE_DURATIONS_BOULDER: Dict[str, int] = {
    "base": 2, "strength_power": 4, "power_endurance": 1,
    "performance": 2, "deload": 1,
}  # sum 10
_PHASE_CAPS_BOULDER: Dict[str, int] = {
    "base": 4, "strength_power": 5, "power_endurance": 3,
    "performance": 3, "deload": 2,
}  # sum 17 — intentionally above 16; surplus exhausts before all caps reached
_PHASE_FLOORS_BOULDER: Dict[str, int] = {
    "base": 2, "strength_power": 2, "power_endurance": 1,
    "performance": 2, "deload": 1,
}  # sum 8
# Boulder base was never locked, so the two floors coincide (A284).
_AUTO_FLOORS_BOULDER: Dict[str, int] = dict(_PHASE_FLOORS_BOULDER)
_SURPLUS_PRIORITY_BOULDER: Tuple[str, ...] = (
    "performance", "strength_power", "power_endurance", "base", "deload",
)
_MIN_TOTAL_WEEKS_BOULDER = 8

# Both disciplines
_MAX_TOTAL_WEEKS = 16

# Backward-compat alias (some callers still reference the old name).
_BASE_DURATIONS: Dict[str, int] = _BASE_DURATIONS_LEAD


def _find_weakest_axis(profile: Dict[str, int]) -> Tuple[Optional[str], int]:
    """Return (axis_name, score) for the lowest-scoring weakness-relevant axis.

    Returns (None, 101) if profile has no relevant axes (treated as "no
    weakness"). Missing axes default to 50 (neutral, never triggers shift).
    """
    weakest: Optional[str] = None
    score = 101
    # A270: `technique` is deliberately absent. Removing it from the profile is
    # NOT enough — `profile.get(axis, 50)` below turns a missing axis into a
    # phantom 50, and on the real production profiles that phantom *wins* the
    # weakest-axis title for two users. It scores exactly 50 so it never trips
    # the `< 50` duration shift, but it would be reported as the weakness to the
    # coach and to any future consumer. It has to come out of this tuple.
    for axis in ("power_endurance", "endurance", "finger_strength",
                 "pulling_strength"):
        v = profile.get(axis, 50)
        if v < score:
            score = v
            weakest = axis
    return weakest, score


def _compute_phase_durations(
    profile: Dict[str, int],
    total_weeks: int = 12,
    discipline: str = "lead",
    *,
    phases: Optional[List[str]] = None,
    phase_overrides: Optional[Dict[str, int]] = None,
) -> Dict[str, int]:
    """Allocate *total_weeks* across the phases listed in *phases*.

    *phases* defaults to the full PHASE_ORDER. The incremental-regen path
    passes a subset starting from `from_phase`, with *total_weeks* set to
    the remaining weeks of the cycle.

    Algorithm:
        1. Initialize at discipline defaults.
        2. Apply *phase_overrides* and LOCK those phases (A284).
        3. Apply ±1 weakness adjustment (clamped to floors and caps).
        4. Distribute surplus / reduce shortfall against caps and floors.

    Args:
        phase_overrides: A284. ``{phase_id: weeks}`` the athlete asked for
            explicitly. Each value must sit within that phase's [floor, cap];
            anything else raises. An overridden phase is **locked**: steps 3
            and 4 will not move it, so what was asked for is what comes out.
            Phases not listed behave exactly as before.

    Raises:
        ValueError if *total_weeks* is outside the legal range for the scope,
        or if an override is out of its phase's [floor, cap] range.
    """
    is_boulder = discipline == "boulder"
    if is_boulder:
        defaults = _BASE_DURATIONS_BOULDER
        caps = _PHASE_CAPS_BOULDER
        floors = _PHASE_FLOORS_BOULDER
        auto_floors = _AUTO_FLOORS_BOULDER
        priority = _SURPLUS_PRIORITY_BOULDER
        min_full = _MIN_TOTAL_WEEKS_BOULDER
    else:
        defaults = _BASE_DURATIONS_LEAD
        caps = _PHASE_CAPS_LEAD
        floors = _PHASE_FLOORS_LEAD
        auto_floors = _AUTO_FLOORS_LEAD
        priority = _SURPLUS_PRIORITY_LEAD
        min_full = _MIN_TOTAL_WEEKS_LEAD

    if phases is None:
        phases = list(PHASE_ORDER)

    if not phases:
        return {}

    # ── 0. Validate overrides FIRST — they narrow the legal range below ──
    overrides: Dict[str, int] = {}
    for p, wanted in (phase_overrides or {}).items():
        if p not in phases:
            continue
        if not isinstance(wanted, int) or isinstance(wanted, bool):
            raise ValueError(f"phase_overrides[{p!r}] must be an int, got {wanted!r}")
        if not (floors[p] <= wanted <= caps[p]):
            raise ValueError(
                f"phase_overrides[{p!r}] = {wanted} outside "
                f"[{floors[p]}, {caps[p]}] for discipline={discipline}"
            )
        overrides[p] = wanted

    # ── 1. Range validation (defense in depth — routers also clamp) ──────
    # A locked phase contributes its fixed size to both bounds, not its
    # floor/cap: pinning base to 2 genuinely lowers the longest cycle that can
    # be built, and the athlete deserves to hear that here rather than through
    # a "scope at cap" further down.
    is_full_cycle = set(phases) == set(PHASE_ORDER)
    scope_min = sum(overrides.get(p, floors[p]) for p in phases)
    scope_max = sum(overrides.get(p, caps[p]) for p in phases)
    full_min = max(min_full, scope_min) if is_full_cycle else scope_min
    if total_weeks < full_min:
        raise ValueError(
            f"total_weeks {total_weeks} below minimum {full_min} for "
            f"discipline={discipline}, phases={phases}"
        )
    if total_weeks > _MAX_TOTAL_WEEKS:
        raise ValueError(
            f"total_weeks {total_weeks} exceeds max {_MAX_TOTAL_WEEKS}"
        )
    if total_weeks > scope_max:
        _why = (f" (phase_overrides={overrides} pin {sum(overrides.values())} "
                f"of those weeks)") if overrides else ""
        raise ValueError(
            f"total_weeks {total_weeks} exceeds scope cap sum {scope_max} "
            f"for phases={phases}{_why}"
        )

    # ── 2. Initialize at defaults (only for phases in scope) ─────────────
    durations = {p: defaults[p] for p in phases}

    # ── 2b. Apply the overrides validated in step 0, and LOCK them ───────
    # Locking matters because otherwise steps 3-4 would quietly hand back the
    # weeks just removed, and the athlete would see the number they asked for
    # silently ignored.
    locked: Set[str] = set(overrides)
    durations.update(overrides)

    # ── 3. Weakness adjustment (clamped — no silent self-cancel) ─────────
    weakest_axis, weakest_score = _find_weakest_axis(profile)
    if (weakest_axis is not None
            and weakest_score < 50
            and weakest_axis in _WEAKNESS_ADJUSTMENTS):
        ext, shr = _WEAKNESS_ADJUSTMENTS[weakest_axis]
        if (ext in durations and shr in durations
                and ext not in locked and shr not in locked
                and durations[ext] + 1 <= caps[ext]
                and durations[shr] - 1 >= auto_floors[shr]):
            durations[ext] += 1
            durations[shr] -= 1
        # else: clean no-op (shift would violate floor or cap, touch a locked
        # phase, OR phases outside scope). No silent absorption anywhere.

    # ── 4. Surplus distribution OR shortfall reduction ───────────────────
    diff = total_weeks - sum(durations.values())
    if diff > 0:
        for p in priority:
            if p not in durations or p in locked:
                continue
            give = min(diff, caps[p] - durations[p])
            durations[p] += give
            diff -= give
            if diff == 0:
                break
        if diff != 0:
            raise ValueError(
                f"Cannot distribute surplus {diff}: scope at cap"
            )
    elif diff < 0:
        shortfall = -diff
        for p in reversed(priority):
            if p not in durations or p in locked:
                continue
            take = min(shortfall, durations[p] - auto_floors[p])
            durations[p] -= take
            shortfall -= take
            if shortfall == 0:
                break
        if shortfall != 0:
            raise ValueError(
                f"Cannot absorb shortfall {shortfall}: scope at floor"
            )

    # ── 5. Postcondition (defensive — should never trip) ─────────────────
    assert sum(durations.values()) == total_weeks, "duration math broke"
    for p in phases:
        assert floors[p] <= durations[p] <= caps[p], (
            f"{p} {durations[p]} out of [{floors[p]},{caps[p]}]"
        )
    return durations


def _adjust_domain_weights(
    base_weights: Dict[str, float],
    profile: Dict[str, int],
) -> Dict[str, float]:
    """Adjust domain weights based on profile weaknesses.

    - Axes with score < 50 → +0.05 to relevant weight
    - Axes with score > 75 → -0.03
    Then renormalize to sum = 1.0.
    """
    # Map profile axes to domain weight keys (5 axes → 5 domains)
    # core_prehab remains as a fixed domain weight per phase, no longer driven by an axis.
    # A270 / D266: `technique` is gone from this map. It was the single largest
    # plan-shaping lever in the engine — D260 §5 measured +7.5 pp of technique
    # weight in EVERY phase for the author — and after the gap demotion it is a
    # three-valued self-declaration (40/45/50). A subjective input must not
    # rewrite a macrocycle. The phase's base technique weight (.20 in base, .25
    # in performance) is untouched: technique is not de-prioritised, it simply
    # stops being corrected by an opinion.
    axis_to_weight = {
        "finger_strength": "finger_strength",
        "pulling_strength": "pulling_strength",
        "power_endurance": "power_endurance",
        "endurance": "volume_climbing",  # endurance maps to climbing volume
    }

    adjusted = dict(base_weights)

    for axis, weight_key in axis_to_weight.items():
        score = profile.get(axis, 50)
        if weight_key not in adjusted:
            continue
        if score < 35:
            adjusted[weight_key] += 0.10
        elif score < 50:
            adjusted[weight_key] += 0.05
        elif score > 75:
            adjusted[weight_key] = max(0.02, adjusted[weight_key] - 0.03)

    # Renormalize
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: round(v / total, 3) for k, v in adjusted.items()}

    return adjusted


# A258 — pool condizionati al profilo. Il peso di dominio si adatta già alle
# debolezze (`_adjust_domain_weights`), l'appartenenza al pool no: uno scalatore
# con la tirata a 20/100 riceveva la stessa dose quasi nulla di uno a 100/100
# (D263 punto 4, CRITICO). Qui la sessione dedicata entra SOLO per chi ne ha
# bisogno, e come `available` — compete per uno slot invece di aggiungersi al
# carico ("in sostituzione, non in aggiunta", raccomandazione KB).
#
# La soglia è la stessa che `_adjust_domain_weights` usa per "asse debole": una
# sola definizione di debolezza in tutto il motore.
WEAK_AXIS_THRESHOLD = 50

_PROFILE_CONDITIONAL_SESSIONS: Dict[str, Dict[str, Any]] = {
    "pulling_strength_gym": {
        "axis": "pulling_strength",
        # Solo `strength_power`. Il KB indicava anche `base`, ma la sessione è
        # `intensity: high` mentre `base` ha `PHASE_INTENSITY_CAP = medium`:
        # il planner la scarta prima ancora di considerarla, quindi metterla
        # nel pool di base sarebbe una dichiarazione senza effetto. In base la
        # tirata arriva comunque come MANTENIMENTO dal blocco C261. Il lavoro
        # di SVILUPPO in base richiederebbe di alzare il tetto d'intensità
        # della fase — decisione metodologica, non un dettaglio di pool
        # (tracciata come BASE-PULLING-INTENSITY-CAP in roadmap).
        "phases": ("strength_power",),
        # `primary`, non `available`: misurato, da `available` la sessione non
        # viene MAI collocata (perde contro le primarie e la settimana si
        # riempie prima). Da `primary` entra al posto di un'altra seduta dura —
        # che è esattamente il "in sostituzione, non in aggiunta" del KB: il
        # conteggio dei giorni duri resta invariato (verificato: 3/4 prima e
        # dopo, con `strength_long` che cede il posto).
        "role": "primary",
    },
}


def _profile_conditional_additions(
    phase_id: str, assessment_profile: Optional[Dict[str, Any]]
) -> Dict[str, str]:
    """Sessions unlocked by a weak axis in ``assessment_profile``.

    ``None`` (or a profile without the axis) → nothing added, i.e. exactly the
    behaviour before A258. That default keeps every caller that has no profile
    in scope — including the replanner fallbacks — working unchanged.
    """
    if not assessment_profile:
        return {}
    out: Dict[str, str] = {}
    for sid, rule in _PROFILE_CONDITIONAL_SESSIONS.items():
        if phase_id not in rule["phases"]:
            continue
        score = assessment_profile.get(rule["axis"])
        if isinstance(score, (int, float)) and score < WEAK_AXIS_THRESHOLD:
            out[sid] = rule["role"]
    return out


def _build_session_pool(
    phase_id: str,
    discipline: str = "lead",
    assessment_profile: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Return the ordered session pool for a phase.

    For ``all_round``, merge lead and boulder pools: a session that is
    "primary" in either pool stays primary; otherwise "available".

    ``assessment_profile`` (A258, optional): unlocks profile-conditional
    sessions for weak axes. Omitted → identical behaviour to before A258.
    """
    if discipline in ("both", "all_round"):
        lead_def = _SESSION_POOL.get(phase_id, {})
        boulder_def = _SESSION_POOL_BOULDER.get(phase_id, {})
        merged: Dict[str, str] = {}
        for sid, role in lead_def.items():
            merged[sid] = role
        for sid, role in boulder_def.items():
            if sid not in merged or role == "primary":
                merged[sid] = role
        pool_def = merged
    else:
        pool_map = _SESSION_POOL_BOULDER if discipline == "boulder" else _SESSION_POOL
        pool_def = pool_map.get(phase_id, {})
    # A258: additions apply to every discipline — il buco della tirata è
    # identico nel pool boulder e in `power_endurance` è pure più grave
    # (peso 0.15 vs 0.10 del lead), quindi limitarlo al lead lascerebbe
    # scoperto proprio il caso peggiore.
    extra = _profile_conditional_additions(phase_id, assessment_profile)
    if extra:
        pool_def = {**pool_def, **extra}
    # Primary sessions first, then available
    primary = sorted(k for k, v in pool_def.items() if v == "primary")
    available = sorted(k for k, v in pool_def.items() if v == "available")
    return primary + available


def _check_pretrip_overlap(
    trips: List[Dict[str, Any]],
    phase_start: str,
    phase_end: str,
) -> List[Dict[str, Any]]:
    """Find trips that overlap with a date range."""
    from datetime import date as date_type
    p_start = datetime.strptime(phase_start, "%Y-%m-%d").date()
    p_end = datetime.strptime(phase_end, "%Y-%m-%d").date()
    overlapping = []
    for trip in (trips or []):
        t_start_str = trip.get("start_date")
        if not t_start_str:
            continue
        t_start = datetime.strptime(t_start_str, "%Y-%m-%d").date()
        # Check if the 5-day pre-trip window falls within the phase
        pretrip_start = t_start - timedelta(days=5)
        if pretrip_start <= p_end and t_start >= p_start:
            overlapping.append(trip)
    return overlapping


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def _validate_goal(goal: Dict[str, Any]) -> List[str]:
    """Validate goal and return warnings."""
    warnings = []
    target = goal.get("target_grade")
    current = goal.get("current_grade")

    # B322: for a boulder goal the onboarding router converts target_grade to
    # its lead equivalent (BOULDER_TO_LEAD) but leaves current_grade in Font.
    # Comparing "9a" against "8A" fell through to the "Unknown current_grade"
    # branch, so the "target not harder" / "target too ambitious" checks never
    # ran for a single boulder user. Map current onto the same scale first.
    if current and current not in _GRADE_INDEX:
        mapped = BOULDER_TO_LEAD.get(current)
        if mapped:
            current = mapped

    if target and current and target in _GRADE_INDEX and current in _GRADE_INDEX:
        gap = grade_gap(target, current)
        if gap <= 0:
            warnings.append(
                f"target_grade ({target}) is not harder than current_grade ({current}). "
                "Consider setting a more ambitious target."
            )
        elif gap > 8:
            warnings.append(
                f"target_grade ({target}) is {gap} half-grades above current_grade ({current}). "
                "A single macrocycle may not be sufficient."
            )
    elif target and target not in _GRADE_INDEX:
        warnings.append(f"Unknown target_grade: {target}")
    elif current and current not in _GRADE_INDEX:
        warnings.append(f"Unknown current_grade: {current}")

    return warnings


def generate_macrocycle(
    goal: Dict[str, Any],
    assessment_profile: Dict[str, int],
    user_state: Dict[str, Any],
    start_date: str,
    total_weeks: int = 12,
    *,
    from_phase: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a complete macrocycle of *total_weeks* weeks.

    Args:
        goal: Goal dict from user_state.
        assessment_profile: 6-axis profile (0-100 each).
        user_state: Full user_state for trips and context.
        start_date: YYYY-MM-DD string for the Monday of week 1.
        total_weeks: Total weeks in the macrocycle (default 12).
        from_phase: If set, keep earlier phases from the existing
            macrocycle in *user_state* and regenerate from this phase
            onwards using the updated *assessment_profile*.
            Must be a valid phase_id from PHASE_ORDER.

    Returns:
        Macrocycle dict with phases, domain weights, session pools, etc.
    """
    # --- Input validation ---
    if not goal or not isinstance(goal, dict):
        raise ValueError("generate_macrocycle: goal must be a non-empty dict")
    if not assessment_profile or not isinstance(assessment_profile, dict):
        raise ValueError("generate_macrocycle: assessment_profile must be a non-empty dict")

    goal_warnings = _validate_goal(goal)
    trips = user_state.get("trips") or []

    # A284: per-phase week counts the athlete asked for explicitly. Read from
    # user_state rather than added to the signature, so the four production
    # call sites keep working untouched. Absent key → previous behaviour.
    _phase_overrides = (user_state.get("planning_prefs") or {}).get("phase_weeks") or None
    if _phase_overrides is not None and not isinstance(_phase_overrides, dict):
        raise ValueError("planning_prefs.phase_weeks must be a dict of {phase_id: weeks}")

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    # Invariant: start_date must be a Monday
    if start.weekday() != 0:
        start -= timedelta(days=start.weekday())
        start_date = start.isoformat()
    discipline = goal.get("discipline")
    if discipline is None:
        logger.warning("generate_macrocycle: 'discipline' not set in goal — defaulting to 'lead'")
        discipline = "lead"

    # --- decide which phases to keep vs regenerate ------------------------
    if from_phase:
        old_mc = user_state.get("macrocycle")
        if not old_mc or not old_mc.get("phases"):
            raise ValueError(
                "Cannot do incremental regen: no existing macrocycle in user_state"
            )
        if from_phase not in PHASE_ORDER:
            raise ValueError(f"Unknown phase_id: {from_phase}")

        from_idx = PHASE_ORDER.index(from_phase)

        kept_phases = [
            p for p in old_mc["phases"]
            if PHASE_ORDER.index(p["phase_id"]) < from_idx
        ]
        weeks_used = sum(p["duration_weeks"] for p in kept_phases)
        remaining_weeks = total_weeks - weeks_used
        phases_to_gen = [pid for pid in PHASE_ORDER
                         if PHASE_ORDER.index(pid) >= from_idx]
        durations = _compute_phase_durations(
            assessment_profile, remaining_weeks,
            discipline=discipline, phases=phases_to_gen,
            phase_overrides=_phase_overrides,
        )
        current_week = weeks_used + 1
    else:
        kept_phases = []
        durations = _compute_phase_durations(
            assessment_profile, total_weeks,
            discipline=discipline, phase_overrides=_phase_overrides,
        )
        phases_to_gen = list(PHASE_ORDER)
        current_week = 1

    # --- generate new phases ----------------------------------------------
    new_phases: List[Dict[str, Any]] = []
    for phase_id in phases_to_gen:
        duration = durations.get(phase_id, 0)
        if duration <= 0:
            continue

        phase_start_date = start + timedelta(weeks=current_week - 1)
        phase_end_date = phase_start_date + timedelta(weeks=duration) - timedelta(days=1)

        weights_map = _BASE_WEIGHTS_BOULDER if discipline == "boulder" else _BASE_WEIGHTS
        base_weights = weights_map[phase_id]
        domain_weights = _adjust_domain_weights(base_weights, assessment_profile)
        session_pool = _build_session_pool(
            phase_id, discipline=discipline, assessment_profile=assessment_profile
        )

        pretrip_trips = _check_pretrip_overlap(
            trips,
            phase_start_date.isoformat(),
            phase_end_date.isoformat(),
        )

        phase: Dict[str, Any] = {
            "phase_id": phase_id,
            "phase_name": (PHASE_NAMES_BOULDER if discipline in ("boulder", "all_round") else PHASE_NAMES)[phase_id],
            "start_week": current_week,
            "end_week": current_week + duration - 1,
            "duration_weeks": duration,
            "energy_system": PHASE_ENERGY[phase_id],
            "domain_weights": domain_weights,
            "session_pool": session_pool,
            "intensity_cap": PHASE_INTENSITY_CAP[phase_id],
            "notes": _phase_notes(phase_id),
        }

        if pretrip_trips:
            phase["pretrip_deload"] = [
                {
                    "trip_name": t.get("name"),
                    "trip_start": t.get("start_date"),
                    "deload_from": (datetime.strptime(t["start_date"], "%Y-%m-%d").date() - timedelta(days=5)).isoformat(),
                }
                for t in pretrip_trips
            ]

        new_phases.append(phase)
        current_week += duration

    # --- assemble result --------------------------------------------------
    phases = kept_phases + new_phases
    end_date = start + timedelta(weeks=total_weeks) - timedelta(days=1)

    result: Dict[str, Any] = {
        "macrocycle_version": "macrocycle.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "end_date": end_date.isoformat(),
        "goal_snapshot": {
            "goal_type": goal.get("goal_type"),
            "discipline": discipline,
            "target_grade": goal.get("target_grade"),
            "target_boulder_grade": goal.get("target_boulder_grade"),
            "current_grade": goal.get("current_grade"),
            "deadline": goal.get("deadline"),
        },
        "assessment_snapshot": dict(assessment_profile),
        "total_weeks": total_weeks,
        "phases": phases,
    }
    if goal_warnings:
        result["warnings"] = goal_warnings
    return result


def _phase_notes(phase_id: str) -> str:
    notes = {
        "base": "Build aerobic base. High volume, low intensity. Focus technique and movement quality.",
        "strength_power": "Max strength development. Max hangs, limit bouldering, general strength. High quality, full rest.",
        "power_endurance": "Anaerobic capacity. 4x4, intervals, threshold climbing. Tolerate pump, push volume.",
        "performance": "Peak performance. Limit climbing, projecting, outdoor. Reduce volume, maximize quality.",
        "deload": "Recovery. Volume -50%. No max/high intensity. Mobility, prehab, easy climbing only.",
    }
    return notes.get(phase_id, "")


# ---------------------------------------------------------------------------
# Deload functions (Task 5)
# ---------------------------------------------------------------------------

DELOAD_SESSION_POOL = ["regeneration_easy", "flexibility_full", "yoga_recovery", "prehab_maintenance", "easy_climbing_deload"]


def apply_deload_week(week_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a week plan into a deload week.

    - Remove sessions with max/high intensity
    - Keep max 5 sessions (B160c: raised from 3 — literature expects 4-6 light sessions)
    - Replace removed sessions with deload alternatives
    """
    if not week_plan or "weeks" not in week_plan:
        return week_plan

    deload_plan = dict(week_plan)
    for week in deload_plan.get("weeks", []):
        days = week.get("days", [])
        kept_sessions = 0
        for day in days:
            filtered = []
            for sess in day.get("sessions", []):
                # Keep low/medium intensity sessions, cap at 5 total
                tags = sess.get("tags", {})
                if kept_sessions >= 5:
                    continue
                if tags.get("hard"):
                    continue
                filtered.append(sess)
                kept_sessions += 1
            day["sessions"] = filtered

        week["phase"] = "deload"
        # B346: `deload_factor` removed — written here, in planner_v2 and in
        # legacy planner_v1, and read by nothing in engine, api or frontend.
        # It described an intent (halve the sets in a deload) that was never
        # implemented; the deload pool contains no set-based work to halve.
        week["targets"] = {"hard_days": 0, "finger_days": 0}

    return deload_plan


def check_pretrip_deload(
    macrocycle: Dict[str, Any],
    trips: List[Dict[str, Any]],
    current_date: str,
) -> Optional[Dict[str, Any]]:
    """Check if a trip starts within 5 days of current_date.

    Returns trip info for mini-deload activation, or None.
    """
    if not trips:
        return None

    current = datetime.strptime(current_date, "%Y-%m-%d").date()
    for trip in trips:
        trip_start_str = trip.get("start_date")
        if not trip_start_str:
            continue
        trip_start = datetime.strptime(trip_start_str, "%Y-%m-%d").date()
        days_until = (trip_start - current).days
        if 0 <= days_until <= 5:
            return {
                "trigger": "pretrip_deload",
                "trip_name": trip.get("name"),
                "trip_start": trip_start_str,
                "days_until_trip": days_until,
                "recommendation": "Reduce volume and intensity. No max/high sessions.",
            }
    return None


# ---------------------------------------------------------------------------
# A281 — trip taper
# ---------------------------------------------------------------------------
#
# Until A281 the only thing that happened before a trip was `compute_pretrip_dates`:
# a 6-day window in which the planner refused to place hard/max sessions. That
# is the OPPOSITE of what the evidence says. Bosquet et al. 2007 (meta-analysis,
# Med Sci Sports Exerc, 27 of 182 studies): an effective taper cuts VOLUME by
# 41-60% while holding intensity and frequency constant (ES 0.72 ± 0.36 for the
# 41-60% band). Dropping the intensity is how you arrive rested and detrained.
#
# So the taper is now two separate things:
#
#   * a VOLUME ramp over the two weeks before departure — the part with the
#     evidence behind it;
#   * a much shorter NO-HARD window immediately before the flight — the part
#     the old code was really about, kept because Bosquet studied endurance
#     athletes peaking for a race-day, not climbers about to spend two weeks
#     on rock. Loading the fingers maximally 48h before travelling is a
#     tendon risk the meta-analysis has nothing to say about.
#
# Decision (Daniele, 2026-09-05): keep both, and shorten the no-hard window
# from 6 days to 3.
TAPER_TOTAL_DAYS = 14          # two weeks, per Bosquet
TAPER_WEEK1_VOLUME = 0.6       # days T-14..T-8  → -40% volume
TAPER_WEEK2_VOLUME = 0.4       # days T-7..T-1   → -60% volume
TAPER_NO_HARD_DAYS = 3         # T-2..T inclusive: no hard/max sessions


def compute_taper_windows(
    trips: List[Dict[str, Any]],
    week_start: str,
    week_end: str,
) -> Dict[str, Any]:
    """Taper information for the dates of one week.

    Returns ``{"volume": {date: multiplier}, "no_hard": [dates]}``.

    ``volume`` scales the number of SETS of training work (never warmup,
    cooldown, prehab or test protocols — see ``week.py::_apply_taper_volume``).
    Intensity and the number of training days are deliberately untouched: that
    is the whole point of a taper.

    When two trips overlap the same date the STRONGER taper wins (the lower
    multiplier), because the athlete is tapering for the nearer one.
    """
    w_start = datetime.strptime(week_start, "%Y-%m-%d").date()
    w_end = datetime.strptime(week_end, "%Y-%m-%d").date()

    volume: Dict[str, float] = {}
    no_hard: set = set()

    for trip in (trips or []):
        t_start_str = trip.get("start_date")
        if not t_start_str:
            continue
        try:
            t_start = datetime.strptime(t_start_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue

        # Volume ramp: [T-14, T-1]. The trip day itself is not "training".
        d = max(t_start - timedelta(days=TAPER_TOTAL_DAYS), w_start)
        while d <= min(t_start - timedelta(days=1), w_end):
            days_out = (t_start - d).days
            mult = TAPER_WEEK2_VOLUME if days_out <= 7 else TAPER_WEEK1_VOLUME
            key = d.isoformat()
            volume[key] = min(volume.get(key, 1.0), mult)
            d += timedelta(days=1)

        # No-hard window: the last TAPER_NO_HARD_DAYS dates ending on departure.
        d = max(t_start - timedelta(days=TAPER_NO_HARD_DAYS - 1), w_start)
        while d <= min(t_start, w_end):
            no_hard.add(d.isoformat())
            d += timedelta(days=1)

    return {"volume": volume, "no_hard": sorted(no_hard)}


def compute_pretrip_dates(
    trips: List[Dict[str, Any]],
    week_start: str,
    week_end: str,
) -> List[str]:
    """Compute all dates in a week range that fall in a pre-trip deload window.

    The window covers the 5 days before a trip AND the trip start_date itself.
    """
    w_start = datetime.strptime(week_start, "%Y-%m-%d").date()
    w_end = datetime.strptime(week_end, "%Y-%m-%d").date()
    result: List[str] = []

    for trip in (trips or []):
        t_start_str = trip.get("start_date")
        if not t_start_str:
            continue
        t_start = datetime.strptime(t_start_str, "%Y-%m-%d").date()
        # Window: 5 days before trip + trip start day itself
        window_start = t_start - timedelta(days=5)
        window_end = t_start  # inclusive

        # Add each day in the window that falls within the week
        d = max(window_start, w_start)
        while d <= min(window_end, w_end):
            result.append(d.isoformat())
            d += timedelta(days=1)

    return sorted(set(result))


# ---------------------------------------------------------------------------
# Start-date computation for follow-on macrocycles (A-NEW-MACRO,
# B-NEWMACRO-STARTDATE-FIX)
# ---------------------------------------------------------------------------

def compute_new_macrocycle_start_date(
    state: Dict[str, Any],
    today: date,
) -> date:
    """Resolve the Monday that a *new* follow-on macrocycle should start.

    Used by ``POST /api/macrocycle/start-new-cycle``.

    Returns the Monday strictly after *today* — the new cycle never starts on
    a Monday that is also "today" (the user gets a clean week boundary to
    prepare). The current macrocycle's ``end_date`` is no longer consulted:
    "Start New Cycle" abandons the current cycle now and starts fresh next
    Monday, regardless of where the current cycle is in its timeline. The
    archive logic in the endpoint handles continuity.

    Args:
        state: User state dict. **Retained for signature stability — current
            macrocycle is no longer consulted (B-NEWMACRO-STARTDATE-FIX).**
        today: The reference date (caller passes ``date.today()`` in prod;
            tests pass a fixed value).

    Returns:
        A ``date`` whose ``weekday() == 0`` (Monday) and which is strictly
        greater than *today*.
    """
    del state  # explicitly unused; see docstring.
    return date.fromisoformat(strict_next_monday(today))
