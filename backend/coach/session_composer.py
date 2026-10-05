"""A259 — LLM session composer: the model picks, the engine decides and checks.

Why this exists. Until now the LLM only filled a small slot-spec (`focus`,
`body_parts`, `minutes`…) and `adhoc_builder` composed deterministically from
it. That is robust and completely inexpressive: a request like *"cardio, then
lock-offs but NO pull-ups, various push-ups, handstand work, no stretching"*
carries five positive asks and two refusals, and a closed vocabulary can only
ever represent the two or three we thought of in advance. Each missing nuance
costs a new enum field, forever.

The design here is **not** "let the model write the session". It is a whitelist:

    1. the engine builds the pool of admissible exercises — equipment actually
       available, active, spine-safe, minus the user's refusals;
    2. the model picks from that pool and assigns sets/reps/rest/order/notes;
    3. the engine validates every line before anything reaches the user, and
       drops what does not hold up;
    4. too little survives → the deterministic builder composes instead.

What the model can therefore never do: invent an exercise, reach equipment the
user does not have, bypass the P0 filters, or exceed the bounds the custom
session schema enforces. What it gains: composing freely inside those walls.

Blast radius, deliberately small — this path only ever produces an **ad-hoc
custom session**, which A207/A240 already keep out of the closed loop and the
macrocycle, and which the user must confirm with a tap (suggest-only).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from backend.coach import llm_client
from backend.engine.adhoc_builder import (
    ADHOC_ENERGY,
    ADHOC_EQUIPMENT_SETS,
    MAX_MINUTES,
    MIN_MINUTES,
    _current_phase,
    _domains_of,
    _equipment_of,
    _is_active,
    _is_spine_safe,
    _pattern_str,
    _roles_of,
    effort_band_for_phase,
    excluded_ids,
    match_gym,
)
from backend.engine.body_part_picker import (
    _exercise_fits_equipment,
    resolve_equipment_mode,
)
from backend.engine.custom_session import (
    compute_custom_session_load,
    estimate_custom_session_duration,
)

logger = logging.getLogger(__name__)

# Kill switch: set COACH_LLM_COMPOSER=0 to fall back to the deterministic
# builder everywhere, without a deploy.
ENABLED = os.environ.get("COACH_LLM_COMPOSER", "1") != "0"

# Bounds mirrored from CustomSessionExerciseEntry — a proposal that violates
# them would be rejected later by the persistence endpoint anyway, so it is
# rejected here where we can still drop just the offending line.
MAX_SETS, MAX_REPS = 20, 100
MAX_WORK_SECONDS, MAX_REST_SECONDS = 3600, 600

# A composed session must be recognisably the session that was asked for.
MIN_EXERCISES = 4
DURATION_TOLERANCE = 1.15  # trim the tail beyond this multiple of the ask

# The deterministic builder caps at 8 because it picks blindly and more would be
# padding. A composed session is different: an hour asking for cardio +
# lock-offs + push + handstand + core is five blocks by construction, and at 8
# the tail — the push work — was silently cut after the rationale had already
# promised it. Still well under the schema's 30.
MAX_COMPOSER_EXERCISES = 16

# A model asked for 60 minutes routinely returns 30. One corrective round is
# worth it: it is told what it actually filled and composes again. Beyond one
# retry the returns vanish and the cost doubles.
MIN_FILL_RATIO = 0.8

# Pool size ceiling — a backstop against an unbounded prompt, NOT a selection
# policy.
#
# B333: it had been one. At 120 the cap bit in every equipment mode — 162
# admissible at home, 139 at the gym — and because the pool is sorted by id
# before the cut, the 42 exercises it removed were not a sample but always the
# same tail of the alphabet: side_plank, v_up, toes_to_bar, weighted_pullup,
# wall_handstand_hold, treadmill_incline_walk, stationary_bike_zone2… So "core
# at home" could not return the core, and C266's cardio — added to the catalog
# precisely because it was missing — was unreachable for the composer.
#
# The comment here used to call 120 "generous". Nobody had measured it. The
# full home pool is ~5.1k tokens against ~3.8k for the truncated one: the whole
# catalog costs ~1.3k more input tokens, which is nothing against a 2048-token
# reply, and buys back a third of the exercises.
#
# 220 leaves room for ~60 new catalog entries before this matters again, and
# _log_pool_truncation below makes sure that day is noticed instead of guessed
# at. The sort stays: identical state must produce an identical pool.
MAX_POOL = 220


_SYSTEM = (
    "You compose ONE training session for a climber, choosing ONLY from the "
    "EXERCISE POOL given below. The pool has already been filtered for the "
    "equipment the athlete actually has and for what they refused — never "
    "invent an exercise id, never assume equipment.\n\n"
    "Honour the request literally, in the order the athlete describes it. If "
    "they ask for cardio first, the session starts with cardio. If they refuse "
    "something (no pull-ups, no stretching), nothing resembling it appears — "
    "not even as a warm-up. If they name several kinds of work (lock-offs, "
    "push-ups, handstand, core), every one of them gets its own block.\n\n"
    "Prescriptions are yours to set: sets, and either reps or work_seconds, "
    "plus rest. Respect training logic — skill work (handstand, technique) "
    "goes early while fresh; maximal-effort strength before endurance; core "
    "and accessories late. Give heavy isometrics and near-limit sets long rests "
    "(90-180s), light accessory work short ones (30-60s).\n\n"
    "The total must fit the available minutes: estimate roughly as sum over "
    "exercises of sets x (work + rest). Aim for 85-100% of the time budget — "
    "an athlete who asks for 60 minutes should not get 35.\n\n"
    "Fill that time with VOLUME AND REST, never with redundancy. At most two "
    "near-limit protocols per session: an hour of 'heavy fingers' means two "
    "maximal protocols with full recovery plus warm-up and antagonist work, NOT "
    "four different max-hang variations stacked on each other. When the plan is "
    "already full and minutes remain, lengthen the rests — that is training, "
    "not padding.\n\n"
    "Write `notes` for an exercise only when it carries a real instruction "
    "(a cue, an angle, a caution). Leave it empty otherwise — do not narrate.\n\n"
    "`rationale` is one or two sentences to the athlete, in their language, "
    "explaining the shape of the session. No preamble, no bullet lists."
)

# A297 (R7b): appended to _SYSTEM only when an ATHLETE CONTEXT is present
# (COACH_ATHLETE_CONTEXT on and the context built). With the flag off the
# system prompt is byte-identical to the pre-A297 one.
_SYSTEM_CONTEXT_RULES = (
    "\n\nAn ATHLETE CONTEXT follows the request. The request decides WHAT is "
    "trained; the context constrains HOW. Respect its guards — the engine removes "
    "the lines they forbid anyway, so picking them only shortens the session. "
    "Never swap an [ANCHOR] exercise for a variant to change its load, "
    "and prefer alternatives to exercises marked [OVERUSED]. Loads are never yours "
    "to set: the engine sets them from the athlete's tested maxima and history."
)
# A297 review — DECISIONS (global): the intensity rules apply ONLY to an athlete
# with a tested max. An untested athlete gets neither these sentences nor the
# ``intensity=`` pool markers, so the model is not pushed toward harder work.
_SYSTEM_CONTEXT_INTENSITY_RULES = (
    " For an athlete at the level the context shows, exercises with intensity=low "
    "or very_low are activation or warm-up only, never the main work. 'Harder' "
    "means intensity first (a harder variation, fewer reps in reserve), then "
    "density, then volume. Never stack more than two finger-hard or campus "
    "exercises in one session (one on a low-energy day)."
)

_TOOL: Dict[str, Any] = {
    "name": "compose_session",
    "description": "Compose the session from the given exercise pool.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short session name in the athlete's language (max 80 chars).",
            },
            "rationale": {
                "type": "string",
                "description": "One or two sentences explaining the session to the athlete.",
            },
            "exercises": {
                "type": "array",
                "description": "Exercises in the order they should be performed.",
                "items": {
                    "type": "object",
                    "properties": {
                        "exercise_id": {
                            "type": "string",
                            "description": "MUST be an id from the pool, verbatim.",
                        },
                        "sets": {"type": "integer", "description": "1-20."},
                        "reps": {
                            "type": "integer",
                            "description": "Repetitions per set. Use for rep-based work; omit for timed work.",
                        },
                        "work_seconds": {
                            "type": "integer",
                            "description": "Seconds of work per set. Use for holds/timed work; omit for rep-based work.",
                        },
                        "rest_between_sets_seconds": {
                            "type": "integer",
                            "description": "Rest after each set, in seconds (0-600).",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Cue or caution, in the athlete's language. Omit when there is nothing to say.",
                        },
                    },
                    "required": ["exercise_id", "sets"],
                },
            },
        },
        "required": ["name", "rationale", "exercises"],
    },
}


def _pool_line(ex: Dict[str, Any], markers: Optional[Dict[str, Any]] = None) -> str:
    """One compact catalog line for the prompt.

    ``markers`` (A297, only with an athlete context): adds ``intensity=`` and
    the ``[ANCHOR]`` / ``[OVERUSED n×]`` markers. None → the pre-A297 line."""
    p = ex.get("prescription_defaults") or {}
    bits = [f"{ex.get('id')}", f"\"{ex.get('name')}\""]
    doms = ",".join(_domains_of(ex)[:3])
    if doms:
        bits.append(doms)
    pat = _pattern_str(ex)
    if pat:
        bits.append(pat)
    eq = ",".join(_equipment_of(ex)) or "bodyweight"
    bits.append(eq)
    bits.append(f"fatigue={ex.get('fatigue_cost')}")
    default = []
    if p.get("sets"):
        default.append(f"{p['sets']}x")
    if p.get("reps"):
        default.append(f"{p['reps']}reps")
    elif p.get("work_seconds"):
        default.append(f"{p['work_seconds']}s")
    if default:
        bits.append("default:" + "".join(default))
    if markers is not None:
        eid = str(ex.get("id"))
        if markers.get("intensity"):
            bits.append(f"intensity={ex.get('intensity_level') or '?'}")
        if eid in (markers.get("anchors") or set()):
            bits.append("[ANCHOR]")
        over = (markers.get("overused") or {}).get(str(ex.get("recency_group") or eid))
        if over:
            bits.append(f"[OVERUSED {over}x]")
    return " | ".join(str(b) for b in bits)


def _pool_markers(athlete_ctx: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """A297: the pool markers derived from the athlete context, or None."""
    if not athlete_ctx:
        return None
    anchors = {ex for ex, a in ((athlete_ctx.get("anchors") or {}).get("exercises") or {}).items() if a}
    variety = athlete_ctx.get("variety") or {}
    overused = set(variety.get("overused") or [])
    counts = {g["group"]: g["count"] for g in variety.get("groups") or [] if g.get("group") in overused}
    from backend.engine.athlete_context import athlete_is_tested

    return {"anchors": anchors, "overused": counts, "intensity": athlete_is_tested(athlete_ctx)}


def build_pool(
    intent: Dict[str, Any],
    user_state: Dict[str, Any],
    catalog_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """The admissible exercises, decided by the engine alone.

    Warm-up roles are kept (a request may open with cardio or activation) but
    tests never are: a test session is a measurement protocol with its own
    scheduling rules, not something to drop into an ad-hoc workout.
    """
    equipment_set = (
        intent.get("equipment_set")
        if intent.get("equipment_set") in ADHOC_EQUIPMENT_SETS
        else "home"
    )
    gym = match_gym(user_state, intent.get("gym_name")) if equipment_set == "gym" else None
    if gym is not None:
        equipment = resolve_equipment_mode("gym", user_state, gym_id=gym.get("gym_id"))
    else:
        equipment = resolve_equipment_mode(equipment_set, user_state)

    banned = excluded_ids(catalog_by_id, intent.get("exclude") or [])
    # A294 (A259 extension, decision 2026-10-04): near a finger key session or
    # before a max test the engine drops the finger-hard / heavy-pull lines.
    banned |= {str(x) for x in (intent.get("key_guard_exclude_ids") or [])}
    # A297: the athlete-context guards of the session day (finger gap, heavy
    # pulling window, pre-limit, deload, hard cap) — same exclusion channel.
    banned |= {str(x) for x in (intent.get("athlete_guard_exclude_ids") or [])}

    pool = [
        ex
        for eid, ex in catalog_by_id.items()
        if eid not in banned
        and _is_active(ex)
        and _is_spine_safe(ex)
        and _exercise_fits_equipment(ex, equipment)
        and not ({"test"} & set(_roles_of(ex)))
    ]
    pool.sort(key=lambda e: str(e.get("id")))
    if len(pool) > MAX_POOL:
        # B333: never cut in silence. The composer already warns when the pool
        # is too SMALL; it had no symmetric branch, so a pool impoverished by
        # the ceiling was indistinguishable in the logs from a healthy one —
        # and the deterministic fallback never fires, because the pool stays
        # far above MIN_EXERCISES. Same rule B328 applied to the outdoor log,
        # which announces its own truncation to the model.
        logger.warning(
            "composer: pool truncated to %d of %d admissible (equipment_set=%s) — "
            "the %d dropped are the tail of the id sort, not a sample; raise MAX_POOL",
            MAX_POOL, len(pool), equipment_set, len(pool) - MAX_POOL,
        )
    return pool[:MAX_POOL]


def _clamp(value: Any, lo: int, hi: int) -> Optional[int]:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, v))


def validate(
    proposal: Dict[str, Any],
    pool: List[Dict[str, Any]],
    minutes: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Keep what holds up, report what did not — never silently repair.

    Returns ``(exercises, dropped)`` where ``dropped`` holds human-readable
    reasons; the caller logs them so a bad composition is diagnosable instead
    of merely disappointing.
    """
    pool_ids = {str(e.get("id")) for e in pool}
    # B324: laterality per pool id. Set on the entry here, not only in
    # _decorate_engine_fields, because the time-budget trim below measures the
    # session with estimate_custom_session_duration — which counts both sides.
    alt_sides_by_id = {str(e.get("id")): bool(e.get("alt_sides")) for e in pool}
    exercises: List[Dict[str, Any]] = []
    dropped: List[str] = []
    seen: set = set()

    for item in proposal.get("exercises") or []:
        if not isinstance(item, dict):
            continue
        eid = str(item.get("exercise_id") or "").strip()
        if eid not in pool_ids:
            dropped.append(f"{eid or '?'}: not in pool")
            continue
        if eid in seen:
            dropped.append(f"{eid}: duplicate")
            continue
        sets = _clamp(item.get("sets"), 1, MAX_SETS)
        if sets is None:
            dropped.append(f"{eid}: unusable sets")
            continue
        reps = _clamp(item.get("reps"), 1, MAX_REPS) if item.get("reps") is not None else None
        work = (
            _clamp(item.get("work_seconds"), 1, MAX_WORK_SECONDS)
            if item.get("work_seconds") is not None
            else None
        )
        if reps is None and work is None:
            dropped.append(f"{eid}: neither reps nor work_seconds")
            continue
        rest = _clamp(item.get("rest_between_sets_seconds"), 0, MAX_REST_SECONDS)
        entry: Dict[str, Any] = {
            "exercise_id": eid,
            "sets": sets,
            "alt_sides": alt_sides_by_id.get(eid, False),
        }
        if reps is not None:
            entry["reps"] = reps
        if work is not None:
            entry["work_seconds"] = work
        entry["rest_between_sets_seconds"] = 60 if rest is None else rest
        note = str(item.get("notes") or "").strip()
        if note:
            entry["notes"] = note[:1000]
        exercises.append(entry)
        seen.add(eid)
        if len(exercises) >= MAX_COMPOSER_EXERCISES:
            dropped.append("truncated at MAX_COMPOSER_EXERCISES")
            break

    # Time budget: trim from the tail rather than rescale everything — the
    # opening blocks are the ones the athlete asked for most explicitly.
    while exercises and estimate_custom_session_duration(exercises) > minutes * DURATION_TOLERANCE:
        cut = exercises.pop()
        dropped.append(f"{cut['exercise_id']}: over time budget")

    return exercises, dropped


def _scale_load_for_reps(load: float, ex: Dict[str, Any], reps: Any, bodyweight: float = 0.0) -> float:
    """B363: the remembered load belongs to the catalog rep scheme. When the
    model asks for MORE reps, scale it DOWN (Epley, ~2 in reserve); never up —
    fewer reps keep the remembered load, the safe side. Loads ≤ 0 (assisted or
    unknown) are left alone."""
    # Only rep-counted lifts: a hang's "reps" are hangs, not a rep max.
    if ex.get("load_model") != "external_load" and ex.get("id") not in ("weighted_pullup", "weighted_chinup"):
        return load
    ref = (ex.get("prescription_defaults") or {}).get("reps")
    if not load or load <= 0 or not isinstance(ref, (int, float)) or not isinstance(reps, (int, float)):
        return load
    if reps <= ref:
        return load
    factor = (1 + (ref + 2) / 30) / (1 + (reps + 2) / 30)
    if ex.get("load_model") == "total_load":
        # Rep-max scaling holds on the TOTAL load (bodyweight + added).
        scaled = max(0.0, (load + bodyweight) * factor - bodyweight)
    else:
        scaled = load * factor
    return round(scaled * 2) / 2


def _decorate_engine_fields(
    exercises: List[Dict[str, Any]],
    catalog_by_id: Dict[str, Dict[str, Any]],
    user_state: Dict[str, Any],
    phase: Optional[str],
    today: Optional[str] = None,
    session_exercise_ids: Optional[List[str]] = None,
) -> None:
    """Add display name, load_model and the remembered load, in place.

    The model chose the exercise and the dose; the weight on the bar is read
    from the athlete's history — `propose_exercise_prescription` first (their
    own logged load), then the A253 max-derived anchor. Never invented, and left
    at 0 when nothing is known, which is what the runner renders as an empty
    kg field (B298).
    """
    from datetime import date as _date

    from backend.engine.adhoc_prescription import (
        anchor_adhoc_load,
        propose_exercise_prescription,
    )
    from backend.engine.anchored_load import ANCHORED_EXERCISES, CUSTOM_INTENSITY, anchored_load

    today = today or _date.today().isoformat()
    for entry in exercises:
        ex = catalog_by_id.get(entry["exercise_id"]) or {}
        entry["name"] = ex.get("name") or entry["exercise_id"].replace("_", " ").title()
        entry["load_model"] = ex.get("load_model")
        # B324: laterality comes from the catalog, never from the model — same
        # rule as the load. Without it a composed Copenhagen plank ran one-sided.
        entry["alt_sides"] = bool(ex.get("alt_sides"))
        load_val = 0.0
        # B364: anchored exercises of a tested athlete take the load of the
        # single anchored_load AT THE COMPOSED REPS — no _scale_load_for_reps on
        # top (that would scale twice). Saved with load_mode 'anchored' so the
        # custom player recomputes it on the day the session is played.
        if entry["exercise_id"] in ANCHORED_EXERCISES:
            try:
                anch = anchored_load(
                    user_state, entry["exercise_id"], date=today, phase_id=phase,
                    intensity=CUSTOM_INTENSITY, sets=entry.get("sets"), reps=entry.get("reps"),
                    work_seconds=entry.get("work_seconds"),
                    catalog_intensity=(ex.get("attributes") or {}).get("intensity_pct"),
                    # A297: the same-session guards of anchored_load (a weighted
                    # pull next to a max hang is capped) — only with a context.
                    session_exercise_ids=session_exercise_ids,
                )
            except Exception:
                logger.exception("composer: anchored load failed for %s", entry["exercise_id"])
                anch = None
            if anch is not None:
                entry["load_kg"] = max(0.0, float(anch["external"]))
                entry["load_mode"] = "anchored"
                continue
        try:
            p = propose_exercise_prescription(
                entry["exercise_id"], catalog_by_id, user_state, phase, today=today
            )
            remembered = p.get("load_kg")
            if isinstance(remembered, (int, float)):
                load_val = float(remembered)
            gt = p.get("grade_target")
            if gt:
                # A296: limit-family preview target (display only, re-read
                # by the custom player on the day it is played).
                entry["target_grade"] = gt.get("target_grade")
                entry["target_grade_low"] = gt.get("target_grade_low")
                entry["surface_selected"] = gt.get("surface_selected")
            if not load_val:
                load_val = float(anchor_adhoc_load(ex, user_state, phase, today=today) or 0)
            load_val = _scale_load_for_reps(
                load_val, ex, entry.get("reps"),
                float(user_state.get("bodyweight_kg") or ((user_state.get("body") or {}).get("weight_kg") or 0.0)),
            )
        except Exception:
            logger.exception("composer: load lookup failed for %s", entry["exercise_id"])
        entry["load_kg"] = load_val


def compose(
    message: str,
    intent: Dict[str, Any],
    user_state: Dict[str, Any],
    catalog_by_id: Dict[str, Dict[str, Any]],
    *,
    today: Optional[str] = None,
    athlete_ctx: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Compose via the LLM, or return None so the caller falls back.

    ``today`` (A297): the session day — loads and guards are read on it.
    ``athlete_ctx`` (A297): the engine's athlete context of that day
    (``backend.coach.athlete_block.composer_context``). None — flag off or not
    buildable — composes exactly as before A297.

    None means "this did not produce a session worth showing" — never a partial
    or a guess. Every provider error is caught here for the same reason: the
    deterministic builder is always able to answer, so a coach outage must
    degrade the *quality* of the session, not its existence.
    """
    if not ENABLED:
        return None

    minutes = _clamp(intent.get("minutes"), MIN_MINUTES, MAX_MINUTES) or 45
    energy = intent.get("energy") if intent.get("energy") in ADHOC_ENERGY else "medium"
    phase = _current_phase(user_state)
    guard_view: Optional[Dict[str, Any]] = None
    if athlete_ctx:
        from backend.engine.athlete_context import composer_guard_view

        guard_view = composer_guard_view(user_state, athlete_ctx, today, catalog_by_id)
        if guard_view.get("exclude_ids"):
            intent = {**intent, "athlete_guard_exclude_ids": list(guard_view["exclude_ids"])}
    pool = build_pool(intent, user_state, catalog_by_id)
    if len(pool) < MIN_EXERCISES:
        logger.warning("composer: pool too small (%d) — falling back", len(pool))
        return None

    context = [
        f"ATHLETE REQUEST (verbatim): {message}",
        "",
        f"Time available: {minutes} minutes.",
        f"Energy: {energy}. Training phase: {phase or 'no active plan'}.",
    ]
    if intent.get("exclude"):
        context.append(
            "Refused by the athlete (already removed from the pool): "
            + ", ".join(intent["exclude"])
        )
    markers = _pool_markers(athlete_ctx)
    system = _SYSTEM
    if athlete_ctx:
        from backend.engine.athlete_context import render_composer_block

        block = render_composer_block(athlete_ctx, state=user_state, day=today)
        if block:
            context += ["", block]
            system = _SYSTEM + _SYSTEM_CONTEXT_RULES
            if markers and markers.get("intensity"):
                system += _SYSTEM_CONTEXT_INTENSITY_RULES
    context += ["", f"EXERCISE POOL ({len(pool)} options):"]
    context += [_pool_line(ex, markers) for ex in pool]

    base_content = "\n".join(context)
    try:
        proposal = llm_client.extract(system, base_content, _TOOL)
        exercises, dropped = validate(proposal, pool, minutes)

        # One corrective round when the session is well short of the ask. The
        # model is told the measured duration — the engine's own estimate, not
        # its guess — and composes again from the same pool.
        filled = estimate_custom_session_duration(exercises) if exercises else 0
        if filled < minutes * MIN_FILL_RATIO:
            logger.info("composer: only %d/%d min filled — one corrective round", filled, minutes)
            retry_content = (
                f"{base_content}\n\n"
                f"YOUR PREVIOUS ATTEMPT filled only {filled} of the {minutes} minutes "
                f"available — too short. It contained: "
                + ", ".join(e["exercise_id"] for e in exercises)
                + ".\nCompose the session again, fuller: add sets to the blocks that "
                "deserve them, lengthen rests where the effort is near-limit, and add "
                "the blocks the athlete asked for that are missing. Keep the same "
                "priorities and the same refusals. Target 85-100% of "
                f"{minutes} minutes."
            )
            retry = llm_client.extract(system, retry_content, _TOOL)
            retry_ex, retry_dropped = validate(retry, pool, minutes)
            if estimate_custom_session_duration(retry_ex) > filled:
                proposal, exercises, dropped = retry, retry_ex, retry_dropped
    except llm_client.CoachConfigError:
        raise
    except Exception:
        logger.exception("composer: LLM call failed — falling back")
        return None

    if guard_view is not None:
        # A297: deterministic post-validation guard. The pool already lost the
        # finger-hard / front-lever lines of a guarded day; what is left to
        # check is the weighted pull at the reps the MODEL chose.
        from backend.engine.athlete_context import drop_heavy_pulls

        dropped = list(guard_view.get("dropped") or []) + dropped
        dropped += drop_heavy_pulls(user_state, exercises, guard_view)
        from backend.engine.athlete_context import athlete_is_tested, cap_finger_hard

        if athlete_is_tested(athlete_ctx):
            dropped += cap_finger_hard(exercises, catalog_by_id, energy)

    logger.info(
        "composer: proposed=%d kept=%d dropped=%s",
        len(proposal.get("exercises") or []), len(exercises), dropped or "none",
    )
    if len(exercises) < MIN_EXERCISES:
        logger.warning("composer: only %d valid exercises — falling back", len(exercises))
        return None

    # Loads are the engine's business, never the model's: they come from the
    # athlete's own logged history (`working_loads`) or a max-derived anchor
    # (A253), exactly as the deterministic path builds them. A composed max-hang
    # session without kilos would be useless, and a composed one with INVENTED
    # kilos would be worse — this is the line between the two.
    if athlete_ctx:
        _decorate_engine_fields(exercises, catalog_by_id, user_state, phase, today=today,
                                session_exercise_ids=[e["exercise_id"] for e in exercises])
    else:
        _decorate_engine_fields(exercises, catalog_by_id, user_state, phase)

    ids = [e["exercise_id"] for e in exercises]
    name = str(proposal.get("name") or "").strip()[:80] or "Ad-hoc session"
    rationale = str(proposal.get("rationale") or "").strip()
    if not rationale:
        # The card and the chat summary are built on this string; an empty one
        # ships a mute session. Deterministic stand-in rather than a blank.
        minutes_est = estimate_custom_session_duration(exercises)
        rationale = (
            f"{len(exercises)} esercizi, ~{minutes_est} min"
            + (f", fase {phase}." if phase else ".")
        )

    effort_band = effort_band_for_phase(phase)
    if guard_view is not None:
        from backend.engine.adhoc_prescription import effort_band_for

        from backend.engine.athlete_context import athlete_is_tested

        effort_band = effort_band_for(phase, energy if athlete_is_tested(athlete_ctx) else None, guard_view)
    session: Dict[str, Any] = {
        "adhoc": True,
        "name": name,
        "tags": [t for t in [intent.get("focus"), intent.get("equipment_set")] if t],
        "exercises": exercises,
        "estimated_load_score": compute_custom_session_load(ids, catalog_by_id),
        "estimated_duration_minutes": estimate_custom_session_duration(exercises),
        "explanation": rationale,
        "effort_band": effort_band,
        "phase": phase,
        # Audit trail (A259): which path composed this, and what the validator
        # threw away. Without it a bad session is only ever "the AI got it
        # wrong" instead of a diagnosable event.
        "composed_by": "llm",
        "dropped": dropped,
        "intent": {
            "equipment_set": intent.get("equipment_set"),
            "focus": intent.get("focus"),
            "secondary_focus": intent.get("secondary_focus"),
            "body_parts": intent.get("body_parts") or [],
            "exclude": intent.get("exclude") or [],
            "gym_name": intent.get("gym_name"),
            "minutes": minutes,
            "energy": energy,
        },
    }
    if athlete_ctx:
        session["athlete_context_version"] = athlete_ctx.get("version")
    if guard_view is not None and guard_view.get("day"):
        session["athlete_guards"] = _guards_payload(guard_view)
    return session


def _guards_payload(view: Dict[str, Any]) -> Dict[str, Any]:
    """A297: the guard verdict of the session day for the preview (additive,
    optional; old clients ignore it)."""
    return {
        "day": view.get("day"),
        "finger_max_ok": bool(view.get("finger_max_ok")),
        "heavy_pull_ok": bool(view.get("heavy_pull_ok")),
        "hiit_ok": bool(view.get("hiit_ok")),
        "reasons": dict(view.get("reasons") or {}),
    }
