"""A243 — deterministic adhoc session composer (Adhoc Coach v1, Phase 3).

Given a structured intent ``{equipment_set, focus, minutes, energy}`` this
composes a ``custom_session`` dict (flagged ``adhoc: True``) from the catalog:
warmup → focus blocks → core finisher (the A237 structure), equipment- and
phase-aware, spine-safe, with per-exercise prescriptions from
``adhoc_prescription`` (loads are remembered-or-0, never invented).

Design invariants:
  * **The LLM never enters this module.** It only extracts the intent
    (``backend.coach.adhoc_intent``); composition is 100% deterministic here,
    so the "deterministic engine" product claim holds.
  * **Compose does NOT persist** (A243 decision). It returns a preview; the
    caller persists on the user's CTA tap — zero orphan custom_sessions.
  * Deterministic: same intent + user_state ⇒ identical session (stable sort,
    no randomness).
  * Reuses ``body_part_picker`` (equipment resolution/fit, recency) and
    ``adhoc_prescription`` (Phase 2) — no new load logic.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any, Dict, List, Optional, Sequence

from backend.engine.adhoc_prescription import (
    effort_band_for_phase,
    propose_exercise_prescription,
)
from backend.engine.body_part_picker import (
    BODY_PART_CATEGORIES,
    BODY_PART_ORDER,
    _exercise_fits_equipment,
    _recent_exercise_ids,
    build_body_part_index,
    resolve_equipment_mode,
)
from backend.engine.custom_session import (
    compute_custom_session_load,
    estimate_custom_session_duration,
)

# ── Intent vocabulary (mirrored by the LLM extraction tool schema) ──────────

# focus → catalog domains. Keys are the ONLY values the extraction tool may emit.
FOCUS_DOMAINS: Dict[str, List[str]] = {
    "fingers": ["finger_strength", "finger_max_strength", "finger_strength_endurance", "finger_aerobic_endurance"],
    "pull": ["strength_pulling", "contact_strength", "power", "lock_off_endurance"],
    "power": ["power", "contact_strength"],
    "endurance": ["power_endurance", "aerobic_capacity", "anaerobic_capacity"],
    "core": ["core"],
    "general_strength": ["strength_general"],
    "technique": ["technique_footwork", "technique_movement", "technique_body_position", "technique_boulder", "technique_lead"],
    "mobility": ["mobility", "flexibility", "regeneration"],
    "prehab": ["prehab_shoulder", "prehab_elbow", "prehab_wrist", "prehab_finger"],
}
ADHOC_FOCUS = sorted(FOCUS_DOMAINS.keys())
ADHOC_EQUIPMENT_SETS = ("home", "gym")
ADHOC_ENERGY = ("low", "medium", "high")

# A252: muscle-level targeting axis. Reuses the existing closed body-part
# taxonomy (body_part_picker) instead of inventing a parallel one — so "chest +
# abs + triceps" composes chest/abs/triceps work, not the coarse
# general_strength soup (squat/row). The LLM emits a subset of these ids; the
# builder constrains the main block to their catalog membership.
ADHOC_BODY_PARTS = tuple(BODY_PART_ORDER)

# Bounds — the composer never trusts an out-of-range minutes value.
MIN_MINUTES = 20
MAX_MINUTES = 120

# B281 quality guards: cap total exercises (a 45-min session with 9+ moves is
# noise), cap same-movement-pattern picks (5 pull-up variants is not a session),
# and keep the single warmup short (an 8-minute unskippable mobility timer was
# the worst offender in field testing).
MAX_EXERCISES = 8
MAX_PER_PATTERN = 2
MAX_WARMUP_WORK_SECONDS = 300

# Deterministic ordering of the main block: heavy compound work first, then
# accessories, then everything else (technique/endurance drills).
_CATEGORY_ORDER = {"main_strength": 0, "power_endurance": 1, "endurance": 1, "strength_accessory": 2}

# Spine-safe defense-in-depth: the catalog is already curated (D55 —
# test_catalog_safety forbids loaded spinal-flexion ids), this is belt-and-
# suspenders against future additions.
_SPINE_UNSAFE_ID_MARKERS = ("crunch", "situp", "sit_up", "russian_twist")


def _domains_of(ex: Dict[str, Any]) -> List[str]:
    d = ex.get("domain")
    if isinstance(d, str):
        return [d]
    return list(d or [])


def _roles_of(ex: Dict[str, Any]) -> List[str]:
    r = ex.get("role")
    if isinstance(r, str):
        return [r]
    return list(r or [])


def _is_active(ex: Dict[str, Any]) -> bool:
    # Default True when the flag is absent (most exercises omit it).
    return ex.get("active") is not False


def _is_spine_safe(ex: Dict[str, Any]) -> bool:
    eid = str(ex.get("id") or "").lower()
    if any(m in eid for m in _SPINE_UNSAFE_ID_MARKERS):
        return False
    contra = " ".join(str(c) for c in (ex.get("contraindications") or [])).lower()
    stress = " ".join(str(s) for s in (ex.get("stress_tags") or [])).lower()
    return "spinal_flexion" not in contra and "spinal_flexion" not in stress


def _phase_match(ex: Dict[str, Any], phase: Optional[str]) -> bool:
    if not phase:
        return False
    aff = ex.get("phase_affinity")
    if isinstance(aff, str):
        aff = [aff]
    return phase in (aff or [])


def _rank_key(ex: Dict[str, Any], phase: Optional[str], recent: set) -> tuple:
    """Deterministic ranking: phase-affinity first, then not-recent, then id.

    All booleans are negated so Python's ascending sort puts preferred first.
    """
    return (
        not _phase_match(ex, phase),      # phase-affinity matches rank first
        str(ex.get("id") or "") in recent,  # unseen-recently ranks before recent
        str(ex.get("id") or ""),           # stable tie-break → determinism
    )


def _candidates(
    catalog_by_id: Dict[str, Dict[str, Any]],
    *,
    domains: Optional[Sequence[str]] = None,
    categories: Optional[Sequence[str]] = None,
    role: Optional[str] = None,
    equipment: Sequence[str],
    exclude: set,
) -> List[Dict[str, Any]]:
    dom_set = set(domains or [])
    cat_set = set(categories or [])
    out: List[Dict[str, Any]] = []
    for ex in catalog_by_id.values():
        eid = str(ex.get("id") or "")
        if not eid or eid in exclude:
            continue
        if not _is_active(ex) or not _is_spine_safe(ex):
            continue
        if not _exercise_fits_equipment(ex, equipment):
            continue
        if dom_set and not (set(_domains_of(ex)) & dom_set):
            continue
        if cat_set and str(ex.get("category") or "") not in cat_set:
            continue
        if role and role not in _roles_of(ex):
            continue
        out.append(ex)
    return out


def _int_or_none(value: Any) -> Optional[int]:
    """Coerce a catalog numeric to int (or None) — some defaults are strings."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_custom_exercise(
    ex: Dict[str, Any],
    catalog_by_id: Dict[str, Dict[str, Any]],
    user_state: Dict[str, Any],
    phase: Optional[str],
    energy: str,
    today: str,
) -> Dict[str, Any]:
    """Build a CustomSessionExercise dict from the deterministic proposal."""
    eid = str(ex.get("id"))
    p = propose_exercise_prescription(eid, catalog_by_id, user_state, phase, today=today)
    sets = _int_or_none(p.get("sets")) or 1
    # Energy modulates volume by ±1 set (bounded); never below 1. Warmups are
    # exempt (B281) — feeling fresh doesn't mean warming up twice as long.
    is_warmup = "warmup" in _roles_of(ex)
    if energy == "low" and not is_warmup:
        sets = max(1, sets - 1)
    elif energy == "high" and not is_warmup:
        sets = min(6, sets + 1)
    load = p.get("load_kg")
    return {
        "exercise_id": eid,
        # Display name for the coach card; dropped by CustomSessionExerciseEntry
        # (pydantic ignores it) when the session is persisted on the CTA tap.
        "name": ex.get("name") or eid.replace("_", " ").title(),
        "sets": sets,
        "reps": _int_or_none(p.get("reps")),
        "work_seconds": _int_or_none(p.get("work_seconds")),
        "rest_between_sets_seconds": _int_or_none(p.get("rest_between_sets_seconds")),
        "rest_between_reps_seconds": _int_or_none(p.get("rest_between_reps_seconds")),
        "load_kg": float(load) if isinstance(load, (int, float)) else 0,
        "notes": "",
    }


def match_gym(user_state: Dict[str, Any], gym_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """B284: resolve a user-mentioned gym name ("bkl", "al Bkl") to the user's
    gym entry, case-insensitive, substring-tolerant. None when no match."""
    gyms = (user_state.get("equipment") or {}).get("gyms") or []
    if not gym_name:
        # Single-gym users: "gym" can only mean that one.
        return gyms[0] if len(gyms) == 1 else None
    needle = str(gym_name).strip().lower()
    if not needle:
        return None
    for g in gyms:
        name = str(g.get("name") or "").strip().lower()
        if name and (name == needle or needle in name or name in needle):
            return g
    return None


def _current_phase(user_state: Dict[str, Any]) -> Optional[str]:
    from backend.api.deps import current_phase_and_week

    mc = user_state.get("macrocycle") or {}
    phases = mc.get("phases") or []
    if not phases:
        return None
    pi, _ = current_phase_and_week(mc)
    if 0 <= pi < len(phases):
        return phases[pi].get("phase_id") or phases[pi].get("id")
    return None


def _harmonization_note(user_state: Dict[str, Any], today: str) -> Optional[str]:
    """Deterministic 'yesterday was hard-fingers, keep it light' style note, or
    None. Reads recent session labels — never mutates state."""
    recent = (user_state.get("recent_sessions") or [])[-3:]
    finger_recent = any(
        "finger" in str(s.get("session_id") or "").lower()
        or (s.get("tags") or {}).get("finger")
        for s in recent
    )
    if finger_recent:
        return "You trained fingers recently — this keeps finger load low."
    return None


def compose_adhoc_session(
    intent: Dict[str, Any],
    user_state: Dict[str, Any],
    catalog: Dict[str, Any],
    *,
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose an adhoc custom_session preview (NOT persisted, no id).

    ``intent``: {equipment_set, focus, secondary_focus?, body_parts?, minutes,
    energy}. When ``body_parts`` (a subset of the closed body-part taxonomy) is
    present it drives the main block and supersedes the coarse focus path (A252).
    ``catalog``: id→exercise dict (as ``_load_exercises_catalog`` returns).
    Returns a custom_session-shaped dict plus ``adhoc: True``, ``explanation``,
    and display metadata.
    """
    today = today or _date.today().isoformat()
    catalog_by_id = {
        str(ex.get("id")): ex
        for ex in catalog.values()
        if isinstance(ex, dict) and ex.get("id")
    }

    equipment_set = intent.get("equipment_set") if intent.get("equipment_set") in ADHOC_EQUIPMENT_SETS else "home"
    focus = intent.get("focus") if intent.get("focus") in FOCUS_DOMAINS else "general_strength"
    # B284: optional secondary focus — "core e tecnica" gets a guaranteed block
    # for the second ask instead of losing it to the dominant-focus pick.
    secondary_focus = intent.get("secondary_focus")
    if secondary_focus not in FOCUS_DOMAINS or secondary_focus == focus:
        secondary_focus = None
    # A252: muscle-level targeting. When present it drives the main block and
    # supersedes the coarse focus/secondary_focus path (a muscle request is more
    # specific than "general_strength"). Validated against the closed taxonomy,
    # de-duplicated, order preserved.
    raw_parts = intent.get("body_parts") or []
    if isinstance(raw_parts, str):
        raw_parts = [raw_parts]
    body_parts: List[str] = []
    for p in raw_parts:
        if p in BODY_PART_ORDER and p not in body_parts:
            body_parts.append(p)
    use_body_parts = bool(body_parts)
    energy = intent.get("energy") if intent.get("energy") in ADHOC_ENERGY else "medium"
    try:
        minutes = int(intent.get("minutes") or 45)
    except (TypeError, ValueError):
        minutes = 45
    minutes = max(MIN_MINUTES, min(MAX_MINUTES, minutes))

    # B284: a named gym ("al Bkl") restricts equipment to THAT gym. Without it,
    # multi-gym users got the union of all their gyms — the composer believed a
    # bench existed at the bouldering gym. No name + single gym → that gym.
    gym = match_gym(user_state, intent.get("gym_name")) if equipment_set == "gym" else None
    if gym is not None:
        equipment = resolve_equipment_mode("gym", user_state, gym_id=gym.get("gym_id"))
    else:
        equipment = resolve_equipment_mode(equipment_set, user_state)
    phase = _current_phase(user_state)
    recent = set(_recent_exercise_ids(user_state))

    chosen: List[Dict[str, Any]] = []
    used: set = set(recent)  # avoid recents AND avoid duplicates within the session

    # 1. Warmup (1) — phase-agnostic; equipment-fit; role=warmup. Keep it SHORT
    # (B281): a long mobility flow as the opener kills the session — prefer the
    # briefest warmup, and never one above MAX_WARMUP_WORK_SECONDS.
    warmups = _candidates(catalog_by_id, role="warmup", equipment=equipment, exclude=used)
    warmups = [
        w for w in warmups
        if (_int_or_none((w.get("prescription_defaults") or {}).get("work_seconds")) or 0)
        <= MAX_WARMUP_WORK_SECONDS
    ]
    warmups.sort(
        key=lambda e: (
            _int_or_none((e.get("prescription_defaults") or {}).get("work_seconds")) or 0,
            str(e.get("id") or ""),
        )
    )
    if warmups:
        chosen.append(warmups[0])
        used.add(str(warmups[0].get("id")))

    def _pattern_of(ex: Dict[str, Any]) -> str:
        p = ex.get("pattern")
        if isinstance(p, list):
            p = p[0] if p else None
        return str(p or ex.get("recency_group") or ex.get("id") or "")

    def _pool(focus_key: str) -> List[Dict[str, Any]]:
        pool = _candidates(
            catalog_by_id, domains=FOCUS_DOMAINS[focus_key], equipment=equipment, exclude=used
        )
        pool = [e for e in pool if not ({"warmup", "cooldown", "test"} & set(_roles_of(e)))]
        pool.sort(key=lambda e: _rank_key(e, phase, recent))
        return pool

    def _estimate(exs: List[Dict[str, Any]]) -> int:
        return estimate_custom_session_duration(
            [_to_custom_exercise(e, catalog_by_id, user_state, phase, energy, today) for e in exs]
        )

    secondary_picks: List[Dict[str, Any]] = []
    reserved_minutes = 0
    pattern_counts: Dict[str, int] = {}
    main_picks: List[Dict[str, Any]] = []
    parts_with_picks: set = set()  # A252: which requested body-parts contributed

    def _append_within_budget(candidate: Dict[str, Any]) -> bool:
        return _estimate(chosen + [candidate]) + reserved_minutes <= minutes

    if use_body_parts:
        # A252: muscle-level main block. Constrain to the requested body-parts'
        # catalog membership (reusing body_part_picker's classification) and
        # round-robin across parts so each requested muscle gets representation —
        # "chest + abs + triceps" yields chest AND abs AND triceps, never three
        # chest picks nor unrelated squat/row padding. Same budget + pattern caps.
        index = build_body_part_index(list(catalog_by_id.values()))

        def _bodypart_candidates(part: str) -> List[Dict[str, Any]]:
            pool = [
                catalog_by_id[eid]
                for eid in index.get(part, set())
                if eid in catalog_by_id
            ]
            pool = [
                e for e in pool
                if str(e.get("id")) not in used
                and _is_active(e) and _is_spine_safe(e)
                and _exercise_fits_equipment(e, equipment)
                and not ({"warmup", "cooldown", "test"} & set(_roles_of(e)))
            ]
            pool.sort(key=lambda e: _rank_key(e, phase, recent))
            return pool

        part_pools = {p: _bodypart_candidates(p) for p in body_parts}
        # No MAX_PER_PATTERN cap here (unlike the coarse-focus path): a
        # muscle-isolation ask is inherently single-pattern — every triceps move
        # is tagged "push", every biceps move "elbow_flexion" — so the catalog's
        # coarse pattern field can't distinguish isolation variants, and a
        # pattern cap would starve a dedicated triceps/biceps session down to 2
        # moves. Monotony is what the user asked for. `used` prevents exact
        # dupes; the round-robin keeps requested muscles balanced; MAX_EXERCISES
        # and the time budget bound the total.
        progressed = True
        while progressed and len(chosen) < MAX_EXERCISES:
            progressed = False
            for p in body_parts:
                if len(chosen) >= MAX_EXERCISES:
                    break
                pool = part_pools[p]
                while pool:
                    cand = pool.pop(0)
                    cid = str(cand.get("id"))
                    if cid in used:
                        continue
                    # Guarantee at least one main even on a tiny budget; after
                    # that, respect the time budget. Never pad unrelated muscles.
                    if main_picks and not _append_within_budget(cand):
                        continue
                    chosen.append(cand)
                    main_picks.append(cand)
                    used.add(cid)
                    parts_with_picks.add(p)
                    progressed = True
                    break
    else:
        # 2a. B284: secondary-focus block reserved FIRST — "core e tecnica" keeps
        # a guaranteed 2-3 exercise block for the second ask instead of losing it.
        if secondary_focus:
            sec_counts: Dict[str, int] = {}
            for c in _pool(secondary_focus):
                if len(secondary_picks) >= 3:
                    break
                pat = _pattern_of(c)
                if sec_counts.get(pat, 0) >= MAX_PER_PATTERN:
                    continue
                secondary_picks.append(c)
                used.add(str(c.get("id")))
                sec_counts[pat] = sec_counts.get(pat, 0) + 1
        reserved_minutes = _estimate(secondary_picks) if secondary_picks else 0
        max_primary_total = MAX_EXERCISES - len(secondary_picks)

        # 2b. Primary focus blocks — as many as the remaining budget allows
        # (min 1), with movement-pattern diversity (B281: max MAX_PER_PATTERN).
        mains = _pool(focus)
        for m in mains:
            if len(chosen) >= max_primary_total:
                break
            mid = str(m.get("id"))
            if mid in used:
                continue
            pat = _pattern_of(m)
            if pattern_counts.get(pat, 0) >= MAX_PER_PATTERN:
                continue
            if _append_within_budget(m):
                chosen.append(m)
                main_picks.append(m)
                used.add(mid)
                pattern_counts[pat] = pattern_counts.get(pat, 0) + 1
            # keep scanning — a later, shorter exercise may still fit
        # Guarantee at least one main even if the budget is tiny.
        if not main_picks and mains:
            first_main = next((m for m in mains if str(m.get("id")) not in used), None)
            if first_main:
                chosen.append(first_main)
                main_picks.append(first_main)
                used.add(str(first_main.get("id")))

    # Order the main block deterministically: compound strength first, then
    # accessories, then drills — instead of the alphabetical soup (B281).
    main_picks.sort(
        key=lambda e: (
            _CATEGORY_ORDER.get(str(e.get("category") or ""), 3),
            str(e.get("id") or ""),
        )
    )
    warm_part = [c for c in chosen if c not in main_picks]
    chosen = warm_part + main_picks + secondary_picks

    # 3. Core finisher (1) — spine-safe core, distinct from mains. Skipped when
    # core already exists as primary/secondary block, AND skipped entirely in
    # muscle-level mode (A252) — appending core to a "chest + triceps" request
    # would be padding an unrequested muscle group.
    finishers = _candidates(catalog_by_id, categories=["core"], equipment=equipment, exclude=used)
    finishers.sort(key=lambda e: _rank_key(e, phase, recent))
    if (
        not use_body_parts
        and focus != "core"
        and secondary_focus != "core"
        and finishers
        and len(chosen) < MAX_EXERCISES
        and _estimate(chosen + [finishers[0]]) <= minutes
    ):
        chosen.append(finishers[0])
        used.add(str(finishers[0].get("id")))

    exercises = [
        _to_custom_exercise(e, catalog_by_id, user_state, phase, energy, today)
        for e in chosen
    ]
    exercise_ids = [e["exercise_id"] for e in exercises]

    harmonization = _harmonization_note(user_state, today)
    phase_label = (phase or "off-plan").replace("_", " ")
    gym_label = str(gym.get("name")) if gym and gym.get("name") else None
    place_label = gym_label or equipment_set
    if use_body_parts:
        # A252: label off the requested muscles, using the taxonomy's display
        # labels ("Back / Pulling", "Core", …).
        combo_label = " + ".join(BODY_PART_CATEGORIES[p]["label"] for p in body_parts)
        tags = [*body_parts, equipment_set]
    else:
        focus_label = focus.replace("_", " ")
        combo_label = (
            f"{focus_label} + {secondary_focus.replace('_', ' ')}" if secondary_focus else focus_label
        )
        tags = [t for t in [focus, secondary_focus, equipment_set] if t]
    explanation_parts = [
        f"A ~{minutes}-min {combo_label} session for {place_label}",
        f"tuned to your {phase_label} phase" if phase else "off-plan support work",
    ]
    explanation = ", ".join(explanation_parts) + "."
    if gym_label:
        explanation += f" Only exercises doable with {gym_label}'s equipment."
    # A252: be honest when a requested muscle had no equipment-compatible work.
    if use_body_parts:
        missing = [p for p in body_parts if p not in parts_with_picks]
        if missing:
            miss_labels = ", ".join(BODY_PART_CATEGORIES[p]["label"] for p in missing)
            explanation += (
                f" No equipment-compatible {miss_labels} exercises were available, "
                "so that was skipped."
            )
    if harmonization:
        explanation += " " + harmonization

    return {
        "adhoc": True,
        "name": f"Adhoc {combo_label} @ {place_label}" if gym_label else f"Adhoc {combo_label} ({equipment_set})",
        "tags": tags,
        "exercises": exercises,
        "estimated_load_score": compute_custom_session_load(exercise_ids, catalog_by_id),
        "estimated_duration_minutes": estimate_custom_session_duration(exercises),
        # Display metadata for the coach card (not part of the stored session).
        "explanation": explanation,
        "effort_band": effort_band_for_phase(phase),
        "phase": phase,
        "intent": {
            "equipment_set": equipment_set,
            "focus": focus,
            "secondary_focus": secondary_focus,
            "body_parts": body_parts,
            "gym_name": gym_label,
            "minutes": minutes,
            "energy": energy,
        },
    }
