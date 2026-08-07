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

# Pool size ceiling. The whole point is that the model sees real options, so
# this is generous; at ~25 tokens per line even the full pool stays ~2-3k.
MAX_POOL = 120


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


def _pool_line(ex: Dict[str, Any]) -> str:
    """One compact catalog line for the prompt."""
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
    return " | ".join(str(b) for b in bits)


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


def _decorate_engine_fields(
    exercises: List[Dict[str, Any]],
    catalog_by_id: Dict[str, Dict[str, Any]],
    user_state: Dict[str, Any],
    phase: Optional[str],
    today: Optional[str] = None,
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

    today = today or _date.today().isoformat()
    for entry in exercises:
        ex = catalog_by_id.get(entry["exercise_id"]) or {}
        entry["name"] = ex.get("name") or entry["exercise_id"].replace("_", " ").title()
        entry["load_model"] = ex.get("load_model")
        # B324: laterality comes from the catalog, never from the model — same
        # rule as the load. Without it a composed Copenhagen plank ran one-sided.
        entry["alt_sides"] = bool(ex.get("alt_sides"))
        load_val = 0.0
        try:
            p = propose_exercise_prescription(
                entry["exercise_id"], catalog_by_id, user_state, phase, today=today
            )
            remembered = p.get("load_kg")
            if isinstance(remembered, (int, float)):
                load_val = float(remembered)
            if not load_val:
                load_val = float(anchor_adhoc_load(ex, user_state, phase) or 0)
        except Exception:
            logger.exception("composer: load lookup failed for %s", entry["exercise_id"])
        entry["load_kg"] = load_val


def compose(
    message: str,
    intent: Dict[str, Any],
    user_state: Dict[str, Any],
    catalog_by_id: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Compose via the LLM, or return None so the caller falls back.

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
    context += ["", f"EXERCISE POOL ({len(pool)} options):"]
    context += [_pool_line(ex) for ex in pool]

    base_content = "\n".join(context)
    try:
        proposal = llm_client.extract(_SYSTEM, base_content, _TOOL)
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
            retry = llm_client.extract(_SYSTEM, retry_content, _TOOL)
            retry_ex, retry_dropped = validate(retry, pool, minutes)
            if estimate_custom_session_duration(retry_ex) > filled:
                proposal, exercises, dropped = retry, retry_ex, retry_dropped
    except llm_client.CoachConfigError:
        raise
    except Exception:
        logger.exception("composer: LLM call failed — falling back")
        return None

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

    return {
        "adhoc": True,
        "name": name,
        "tags": [t for t in [intent.get("focus"), intent.get("equipment_set")] if t],
        "exercises": exercises,
        "estimated_load_score": compute_custom_session_load(ids, catalog_by_id),
        "estimated_duration_minutes": estimate_custom_session_duration(exercises),
        "explanation": rationale,
        "effort_band": effort_band_for_phase(phase),
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
