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
  "max"}`` for all 34 catalog sessions, zero exceptions. So whatever rule
  decides ``hard`` must keep that invariant, and this module does.
* VERIFIED: ``_FINGER_LOAD_PATTERNS`` reproduces the catalog's ``finger`` flag —
  true for hangboard, campus and limit-boulder work; false for circuits, route
  endurance, power endurance and technique.
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

Deliberately EXCLUDED from the finger set: ``finger_extension``,
``tendon_glide``, ``grip_transition`` and the ``prehab_finger`` domain. The 48h
gap exists to space **flexor** loading; extensor bands and tendon glides are
antagonist/prehab work, which is why the catalog's own ``prehab_maintenance``
is ``finger: False``. Without the exclusion a prehab session would block the
following day for nothing.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Ordered weakest → strongest. Shared with planner_v2's intensity vocabulary.
INTENSITY_ORDER: List[str] = ["low", "medium", "high", "max"]
_INTENSITY_RANK = {name: i for i, name in enumerate(INTENSITY_ORDER)}

# How many `high` exercises make a session hard on their own. Anything at `max`
# is enough by itself. See the module docstring: this is the tunable heuristic,
# and lowering it to 1 is exactly the mistake this module documents.
_HIGH_COUNT_FOR_HARD = 2

# Exercise patterns that load the finger flexors hard enough to need the 48h gap.
_FINGER_LOAD_PATTERNS = frozenset({
    "isometric_hang",
    "repeater_hang",
    "campus_ladder",
    "hang",
    "climbing_limit_boulder",
})

# Exercise domains that count as finger loading even if the pattern is unusual.
# `prehab_finger` is NOT here on purpose — see the module docstring.
_FINGER_LOAD_DOMAINS = frozenset({
    "finger_strength",
    "finger_max_strength",
    "finger_strength_endurance",
    "finger_aerobic_endurance",
})


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
    finger = False
    n_max = 0
    n_high = 0
    n_medium = 0

    for ex in exercises or []:
        if not isinstance(ex, dict):
            continue
        entry = cat.get(str(ex.get("exercise_id") or ""))
        if not entry:
            continue
        patterns = _patterns_of(entry)
        domains = [str(d) for d in (entry.get("domain") or [])]
        if any(p in _FINGER_LOAD_PATTERNS for p in patterns) or any(
            d in _FINGER_LOAD_DOMAINS for d in domains
        ):
            finger = True
        level = str(entry.get("intensity_level") or "low")
        if level == "max":
            n_max += 1
        elif level == "high":
            n_high += 1
        elif level == "medium":
            n_medium += 1

    hard = n_max > 0 or n_high >= _HIGH_COUNT_FOR_HARD

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
