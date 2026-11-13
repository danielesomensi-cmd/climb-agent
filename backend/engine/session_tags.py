"""Derive a week-plan slot's safety tags from the exercises it actually contains.

B345. A session placed in the week plan carries ``tags = {"hard": …, "finger": …}``
and an ``intensity``. For catalog sessions those come from ``planner_v2._SESSION_META``.
For **user-authored** sessions — custom builder, coach ad-hoc, body-part picker —
they used to be hardcoded to ``{"hard": False, "finger": False}`` / ``"medium"``
regardless of content (``replanner_v1.add_custom_session``), or to be absent
entirely when the payload did not supply them (``add_generated_session``).

That matters because all three of the planner's safety guards read nothing but
those tags: the 48h finger gap (``_seed_finger_date``,
``_enforce_no_consecutive_finger``) and the weekly hard cap (``_enforce_caps``).
A max hang inserted by the coach was therefore invisible to the gap protecting
the tendons from it. Observed in production: a custom session containing
``max_hang_7s`` (intensity ``max``, fatigue_cost 9) sitting in the plan tagged
``finger: False``.

**What is verified and what is a heuristic** — the distinction matters, because
the first draft of this module got it wrong:

* VERIFIED: inside ``_SESSION_META``, ``hard`` equals ``intensity in {"high",
  "max"}`` for every catalog session except ONE deliberate exception:
  ``treadmill_hiit_4x4`` (C274) is ``intensity: high, hard: False`` — HIIT is
  systemically hard but does not consume the weekly hard / finger cap
  (Daniele's decision, 2026-10-05). Do not "restore" the invariant on it.
  The allowlist is pinned by ``test_b345_custom_session_tags.py``. So whatever
  rule decides ``hard`` for user-authored sessions must keep the invariant, and
  this module does.
* ``_FINGER_LOAD_PATTERNS`` reproduces the catalog's ``finger`` flag on the
  exercises that define a session — true for hangboard, campus and
  limit-boulder work; false for circuits, route endurance, power endurance and
  technique. B414 checked it on the RESOLVED catalog sessions
  (``test_b414_session_tags_pe.py``): the derived tag matches
  ``_SESSION_META.finger`` except for an explicit allowlist (sessions whose
  secondary block can pick a sub-max hang — ``endurance_aerobic_gym``,
  ``regeneration_easy``, ``prehab_maintenance`` — derive True where the
  catalog says False, the conservative direction; ``route_projecting_gym``
  derives False where the catalog says True, since route climbing is not a
  finger pattern). ``power_endurance_gym`` matches everywhere: E2 rule below,
  and its finger block never goes above medium (no 7/3, B414 step 16).
* HEURISTIC: ``_HIGH_COUNT_FOR_HARD``. A session's intensity is **not** the max
  of its exercises' intensities — that was the first draft's mistake, and it
  marked a 15-minute core session "hard" on the strength of one
  ``front_lever_one_leg``, which would have eaten a slot of the weekly hard cap
  and pushed real training out of the week. The catalog's own ``core_training``
  and ``legs_strength`` are ``medium`` / not hard despite containing exercises
  like these. So: anything at ``max`` makes the session hard, and so do **two
  or more** exercises at ``high`` — one high-intensity accessory does not.
  Checked against 18 real sessions: it separates the finger/pulling work from
  the core-and-legs work the way a coach would. It remains a tunable threshold,
  not a measurement.
* B416 (D287 T1, Daniele 2026-11-07: «una sessione di solo core non è un giorno
  duro»): a ``high`` exercise counts toward ``_HIGH_COUNT_FOR_HARD`` only when it
  is climbing, pulling or pushing load. Core / conditioning / complementary /
  prehab / mobility exercises, handstand skill work and leg patterns (squat,
  lunge, hinge, calf raise, hip isolation) count as ``medium``: two core
  exercises at ``high`` (``toes_to_bar`` + ``half_windshield_wiper``, the
  02/11 custom that took the week to 5/5 hard days) no longer make a hard day.
  Exception: the heavy-pull ladder ids (``bw_ladders.heavy_pull_exercise_ids``:
  front lever and one-arm families, decision of 2026-10-04) keep counting —
  three front-lever holds are still a hard session. ``max`` is unchanged:
  any ``max`` exercise (``dragon_flag``, ``front_lever_full``) still makes the
  session hard.

B405: the finger-hard ids of ``stimulus`` (``FINGER_FATIGUE_EXTRA_IDS``: 10 s and
min-edge max hangs; ``FINGER_HARD_LIBRARY_IDS``: ``three_attempt_comp``) make
the session ``finger`` AND ``hard`` on their own, whatever their pattern or
intensity level. ``is_finger_hard_session`` already counted them, the stored
tags did not: a try-hard custom built on ``three_attempt_comp`` came out
``{hard: False, finger: False}`` and was invisible to the 48 h finger gap.

Deliberately EXCLUDED from the finger set: ``finger_extension``,
``tendon_glide``, ``grip_transition`` and the ``prehab_finger`` domain. The 48h
gap exists to space **flexor** loading; extensor bands and tendon glides are
antagonist/prehab work, which is why the catalog's own ``prehab_maintenance``
is ``finger: False``. Without the exclusion a prehab session would block the
following day for nothing.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.engine.stimulus import FINGER_FATIGUE_EXTRA_IDS, FINGER_HARD_LIBRARY_IDS

# Ordered weakest → strongest. Shared with planner_v2's intensity vocabulary.
INTENSITY_ORDER: List[str] = ["low", "medium", "high", "max"]
_INTENSITY_RANK = {name: i for i, name in enumerate(INTENSITY_ORDER)}

# How many `high` exercises make a session hard on their own. Anything at `max`
# is enough by itself. See the module docstring: this is the tunable heuristic,
# and lowering it to 1 is exactly the mistake this module documents.
_HIGH_COUNT_FOR_HARD = 2

# B416: `high` exercises outside these never count toward _HIGH_COUNT_FOR_HARD
# (see the module docstring); the heavy-pull ladder ids always count.
_NON_LOAD_CATEGORIES = frozenset({"core", "conditioning", "complementary", "prehab",
                                  "flexibility", "mobility"})
_NON_LOAD_DOMAINS = frozenset({"handstand_skill"})
_LEG_PATTERNS = frozenset({"squat", "lunge", "hinge", "calf_raise", "hip_isolation"})


def _heavy_pull_ids() -> frozenset:
    """Heavy-pull ladder ids (front lever & co.), cached by bw_ladders' loader."""
    from backend.engine.bw_ladders import heavy_pull_exercise_ids

    return heavy_pull_exercise_ids()


def _high_counts_for_hard(eid: str, entry: Dict[str, Any], heavy_pull: frozenset) -> bool:
    """B416: does this ``high`` exercise count toward ``_HIGH_COUNT_FOR_HARD``?"""
    if eid in heavy_pull:
        return True
    if str(entry.get("category") or "") in _NON_LOAD_CATEGORIES:
        return False
    if any(str(d) in _NON_LOAD_DOMAINS for d in (entry.get("domain") or [])):
        return False
    return not any(p in _LEG_PATTERNS for p in _patterns_of(entry))


# Exercise patterns that load the finger flexors hard enough to need the 48h gap.
_FINGER_LOAD_PATTERNS = frozenset({
    "isometric_hang",
    "repeater_hang",
    "campus_ladder",
    "hang",
    "climbing_limit_boulder",
})

# B405: exercises that are finger-hard by themselves (see the module docstring).
_FINGER_HARD_IDS = frozenset(FINGER_FATIGUE_EXTRA_IDS) | frozenset(FINGER_HARD_LIBRARY_IDS)

# Exercise domains that count as finger loading even if the pattern is unusual.
# `prehab_finger` is NOT here on purpose — see the module docstring.
_FINGER_LOAD_DOMAINS = frozenset({
    "finger_strength",
    "finger_max_strength",
    "finger_strength_endurance",
    "finger_aerobic_endurance",
})


# B414 (INBOX-2026-11-02-e, E2): the sub-max hangs after PE intervals. A hang
# pattern at intensity ≤ medium that is not finger-hard by itself is the
# "submaximal repeaters post-climbing" of power_endurance_gym — a session the
# catalog rates ``finger: False``. Inside a session with PE intervals (role
# main, pattern climbing_intervals, PE / anaerobic domain) and no other finger
# load they no longer make it ``finger``: the custom equals the catalog
# session. Alone (B392's case) or next to max hangs / limit boulders they
# still do.
_SUB_MAX_HANG_PATTERNS = frozenset({"repeater_hang", "isometric_hang", "hang"})
_SUB_MAX_LEVELS = frozenset({"low", "medium"})
_PE_DOMAINS = frozenset({"power_endurance", "anaerobic_capacity"})


def _is_sub_max_hang(eid: str, entry: Dict[str, Any]) -> bool:
    """B414: a hang at intensity ≤ medium that is not finger-hard by itself.

    B414 review: never a test (``test_repeater_7_3_to_failure`` is rated
    ``medium`` but is 7/3 repeaters to failure) and never a hang the catalog
    rates ``stress_tags.fingers: high`` — those are not sub-max work."""
    roles = entry.get("role") or []
    if isinstance(roles, str):
        roles = [roles]
    fingers = str((entry.get("stress_tags") or {}).get("fingers") or "low")
    return (
        eid not in _FINGER_HARD_IDS
        and "test" not in [str(r) for r in roles]
        and fingers != "high"
        and str(entry.get("intensity_level") or "low") in _SUB_MAX_LEVELS
        and any(p in _SUB_MAX_HANG_PATTERNS for p in _patterns_of(entry))
    )


def _is_pe_interval(entry: Dict[str, Any]) -> bool:
    """B414: a PE interval drill (4x4, linked boulders, route intervals…)."""
    roles = entry.get("role") or []
    if isinstance(roles, str):
        roles = [roles]
    return (
        "main" in [str(r) for r in roles]
        and "climbing_intervals" in _patterns_of(entry)
        and any(str(d) in _PE_DOMAINS for d in (entry.get("domain") or []))
    )


# B392: catalog roles that only prepare the session. A warm-up the catalog rates
# at low finger stress does not load the flexors, whatever its pattern says.
_WARMUP_ROLES = frozenset({"warmup", "activation"})
_LIGHT_FINGER_STRESS = frozenset({"none", "low"})


def _is_light_warmup(entry: Dict[str, Any]) -> bool:
    """True for a pure warm-up whose catalog finger stress is ``none``/``low``.

    B392. ``warmup_easy_boulders`` carries the ``climbing_limit_boulder``
    pattern, so every custom that opened with easy boulders came out
    ``finger: True`` — a technique day then blocked max finger work the next
    day (seen in prod: the 18/10 custom put «NO dita max» on 19/10). Same
    exclusion stimulus.py already makes for limit_power. Scoped to warm-ups on
    purpose: the sub-max hangboard work (``sub_max_capacity_hang`` & co.) is
    also rated ``low`` but is the session's main finger load and keeps the tag.
    """
    roles = entry.get("role") or []
    if isinstance(roles, str):
        roles = [roles]
    if not roles or not set(map(str, roles)) <= _WARMUP_ROLES:
        return False
    fingers = (entry.get("stress_tags") or {}).get("fingers")
    return str(fingers) in _LIGHT_FINGER_STRESS


def _rank(intensity: Optional[str]) -> int:
    return _INTENSITY_RANK.get(str(intensity or "low"), 0)


def _catalog() -> Dict[str, Dict[str, Any]]:
    """Exercise catalog keyed by id.

    Imported lazily: progression_v1 owns the cached loader, and importing it at
    module scope would add an engine-level import cycle for a helper that most
    call sites never reach.
    """
    from backend.engine.progression_v1 import _load_catalog_cache

    return _load_catalog_cache()


def _patterns_of(entry: Dict[str, Any]) -> List[str]:
    """Catalog `pattern` is a string for most exercises, a list for a few."""
    pattern = entry.get("pattern")
    if isinstance(pattern, list):
        return [str(p) for p in pattern]
    return [str(pattern)] if pattern else []


def derive_session_tags(
    exercises: Optional[Sequence[Dict[str, Any]]],
    *,
    catalog: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, bool], str]:
    """Return ``({"hard": …, "finger": …}, intensity)`` for a list of exercises.

    Unknown exercise ids contribute nothing rather than raising — a session
    referencing a retired exercise must still land in the plan, just without
    that exercise's contribution to the tags.

    Conservative by construction: ONE max-intensity exercise among ten easy ones
    makes the session hard. That is the correct direction for an injury guard —
    the tendons are loaded by the max hang regardless of what surrounds it.
    """
    cat = catalog if catalog is not None else _catalog()
    heavy_pull = _heavy_pull_ids()
    finger = False  # finger load other than a sub-max hang (B414)
    finger_sub_max = False
    has_pe_intervals = False
    finger_hard = False
    n_max = 0
    n_high = 0
    n_medium = 0

    for ex in exercises or []:
        if not isinstance(ex, dict):
            continue
        eid = str(ex.get("exercise_id") or "")
        entry = cat.get(eid)
        if not entry:
            continue
        if eid in _FINGER_HARD_IDS:
            finger = finger_hard = True
        patterns = _patterns_of(entry)
        domains = [str(d) for d in (entry.get("domain") or [])]
        if _is_pe_interval(entry):
            has_pe_intervals = True
        if not _is_light_warmup(entry) and (
            any(p in _FINGER_LOAD_PATTERNS for p in patterns)
            or any(d in _FINGER_LOAD_DOMAINS for d in domains)
        ):
            if _is_sub_max_hang(eid, entry):
                finger_sub_max = True
            else:
                finger = True
        level = str(entry.get("intensity_level") or "low")
        if level == "max":
            n_max += 1
        elif level == "high" and _high_counts_for_hard(eid, entry, heavy_pull):
            n_high += 1
        elif level in ("high", "medium"):
            n_medium += 1

    # B414 (E2): sub-max hangs count as finger load unless they follow PE
    # intervals in a session with no other finger load.
    finger = finger or (finger_sub_max and not has_pe_intervals)
    hard = finger_hard or n_max > 0 or n_high >= _HIGH_COUNT_FOR_HARD

    # Keep the catalog's invariant: hard ⇔ intensity in {high, max}. Reporting a
    # "high" intensity on a session the cap treats as easy (or the reverse)
    # would desynchronise the two fields for every consumer downstream.
    if hard:
        intensity = "max" if n_max else "high"
    else:
        intensity = "medium" if (n_high or n_medium) else "low"

    return {"hard": hard, "finger": finger}, intensity


def merge_declared_tags(
    declared_tags: Optional[Dict[str, Any]],
    declared_intensity: Optional[str],
    derived_tags: Dict[str, bool],
    derived_intensity: str,
) -> Tuple[Dict[str, bool], str]:
    """Combine what a payload declares with what its content implies.

    Only ever escalates. A caller that already worked out it is shipping finger
    work (``body_part_picker`` derives ``"finger": "fingers" in body_parts``)
    keeps that answer; a caller that under-declares gets corrected. Nothing here
    can talk a guard *out* of protecting the athlete.
    """
    declared = declared_tags or {}
    tags = {
        "hard": bool(declared.get("hard")) or bool(derived_tags.get("hard")),
        "finger": bool(declared.get("finger")) or bool(derived_tags.get("finger")),
    }
    intensity = (
        declared_intensity
        if _rank(declared_intensity) > _rank(derived_intensity)
        else derived_intensity
    )
    return tags, intensity
