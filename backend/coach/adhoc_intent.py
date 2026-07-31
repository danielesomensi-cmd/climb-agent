"""A243 — LLM intent extraction for the adhoc session composer.

The ONLY place the LLM touches the adhoc flow: it extracts a small structured
slot-spec from the user's chat turn via a forced tool call. It never sees the
exercise catalog and never picks exercises or loads — the deterministic
``adhoc_builder`` composes from these slots.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.coach import llm_client
from backend.engine.adhoc_builder import (
    ADHOC_BODY_PARTS,
    ADHOC_ENERGY,
    ADHOC_EQUIPMENT_SETS,
    ADHOC_EXCLUSIONS,
    ADHOC_FOCUS,
)

# B281: how many recent chat messages give the extractor context. Without this,
# a follow-up like "riprovi a crearla?" loses everything the user specified in
# earlier turns (place, focus, minutes) and composition falls back to defaults.
CONTEXT_MESSAGES = 6

_SYSTEM = (
    "You extract the intent behind a climber's request to build an ad-hoc "
    "training session (e.g. 'I'm at a commercial gym, build me a 45-min pulling "
    "session', 'quick core workout at home'). Call the tool once. Set "
    "is_adhoc_request=false if the LATEST message is NOT asking to compose/build "
    "a session (a question, a plan tweak, small talk). When true, infer the "
    "slots from the latest message AND the recent conversation — earlier turns "
    "often carry the place, focus or minutes a short follow-up like 'retry' or "
    "'crearla tu?' refers to. A named climbing/bouldering gym counts as "
    "equipment_set=gym AND its name goes in gym_name verbatim (e.g. 'al Bkl' → "
    "gym_name='Bkl') — this is critical: it selects which equipment is "
    "available. "
    "MUSCLE-LEVEL REQUESTS: when the user names specific muscles/body-parts "
    "(chest, triceps, biceps, back, lats, legs, quads, glutes, hips, calves, "
    "shoulders, delts, abs, core, forearms, fingers), list them in body_parts "
    "using these exact ids: chest, triceps, biceps, back_pulling (back/lats), "
    "legs, glutes, hips, shoulders, core (abs/core), forearms, fingers. "
    "body_parts is MORE specific than focus: prefer it whenever muscles are "
    "named, and leave focus at its default. But ONLY actual anatomy counts: "
    "exercise or MOVEMENT names (lock-offs/bloccaggi, pull-ups/trazioni, "
    "monobraccio, dips, plank, campus, sospensioni) are NOT body parts — map "
    "those to the closest focus instead and leave body_parts empty. Movement "
    "→ focus mapping: bloccaggi / lock-offs / blocchi / tenute isometriche / "
    "one-arm / monobraccio → 'lock_off'; trazioni / pull-ups / rematore → "
    "'pull'; sospensioni / hangboard / dita → 'fingers'; verticale / handstand "
    "/ equilibrio sulle mani / pike push-up → 'handstand'. "
    "REFUSALS: when the user rules something out ('niente trazioni', 'no "
    "stretching', 'senza pesi', 'evita le dita'), list the matching labels in "
    "`exclude`. This is not optional decoration — a refusal that does not reach "
    "`exclude` WILL be violated by the composition. Note that 'niente trazioni' "
    "means pull-ups only: lock-offs and isometric holds are a different thing "
    "and must NOT be excluded. "
    "TWO FOCUSES in ONE session (e.g. 'core e tecnica' at the same place/time): "
    "put the dominant one in focus and the other in secondary_focus. "
    "MULTIPLE SEPARATE SESSIONS (e.g. 'one at lunch at work AND another tonight "
    "at home'): the builder makes ONE session per request. Extract the slots for "
    "the session happening SOONER (earlier in the day, or first mentioned) into "
    "the main slots, set multi_session_requested=true, and put a short plain "
    "description of the OTHER session(s) NOT built in deferred_session_hint "
    "(e.g. 'tonight at home: core and biceps'). "
    "Always set language to the language the user writes in ('it' for "
    "Italian, otherwise 'en'). "
    "Use sensible "
    "defaults only when truly unstated (equipment_set=home, "
    "focus=general_strength, minutes=45, energy=medium). Never guess exercises "
    "or loads — only these slots."
)

_TOOL: Dict[str, Any] = {
    "name": "extract_adhoc_intent",
    "description": "Extract the structured intent for building an ad-hoc training session.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_adhoc_request": {
                "type": "boolean",
                "description": "True only if the user is asking to build/compose a training session now.",
            },
            "equipment_set": {
                "type": "string",
                "enum": list(ADHOC_EQUIPMENT_SETS),
                "description": "Where the climber is training: 'home' or a commercial 'gym'.",
            },
            "focus": {
                "type": "string",
                "enum": list(ADHOC_FOCUS),
                "description": "Primary training focus.",
            },
            "secondary_focus": {
                "type": "string",
                "enum": list(ADHOC_FOCUS),
                "description": "Second focus when the user asks for two (e.g. 'core e tecnica' → focus=technique, secondary_focus=core). Omit otherwise.",
            },
            "body_parts": {
                "type": "array",
                "items": {"type": "string", "enum": list(ADHOC_BODY_PARTS)},
                "description": "Specific muscles/body-parts named by the user (e.g. 'chest + abs + triceps' → ['chest','core','triceps']). More specific than focus — use whenever muscles are named. Omit when the user gave only a coarse focus.",
            },
            "exclude": {
                "type": "array",
                "items": {"type": "string", "enum": list(ADHOC_EXCLUSIONS)},
                "description": (
                    "What the athlete explicitly refused. 'niente trazioni' → "
                    "['pullups'] (pull-ups only — NOT lock-offs); 'no stretching' "
                    "→ ['stretching']; 'senza pesi' → ['weights']; 'niente dita/"
                    "sospensioni' → ['hangboard']; 'no gambe' → ['legs']. Omit "
                    "when nothing was ruled out."
                ),
            },
            "multi_session_requested": {
                "type": "boolean",
                "description": "True when the user asked for TWO OR MORE separate sessions (different place/time). The builder makes only the SOONER one; the rest go in deferred_session_hint.",
            },
            "deferred_session_hint": {
                "type": "string",
                "description": "Short plain description of the session(s) NOT built when multi_session_requested=true (e.g. 'tonight at home: core and biceps'). Omit otherwise.",
            },
            "gym_name": {
                "type": "string",
                "description": "The gym's name verbatim when the user names one (e.g. 'Bkl'). Selects which gym's equipment is available. Omit if no gym named.",
            },
            "minutes": {
                "type": "integer",
                "description": "Available time in minutes (20-120).",
            },
            "energy": {
                "type": "string",
                "enum": list(ADHOC_ENERGY),
                "description": "How fresh the climber feels.",
            },
            "language": {
                "type": "string",
                "enum": ["en", "it"],
                "description": "Language the user is writing in (closest match; default en). Drives the app's confirmation message language.",
            },
        },
        "required": ["is_adhoc_request", "language"],
    },
}


def build_extraction_content(
    message: str, history: Optional[List[Dict[str, str]]] = None
) -> str:
    """Latest message + a compact recent-transcript block (B281).

    ``history``: chronological ``{role, content}`` dicts; only the last
    ``CONTEXT_MESSAGES`` are included, truncated per message.
    """
    if not history:
        return message
    lines = []
    for m in history[-CONTEXT_MESSAGES:]:
        role = "User" if m.get("role") == "user" else "Coach"
        content = str(m.get("content") or "").strip().replace("\n", " ")
        if content:
            lines.append(f"{role}: {content[:400]}")
    if not lines:
        return message
    return (
        "Recent conversation (context for slot inference):\n"
        + "\n".join(lines)
        + f"\n\nLatest message (classify THIS): {message}"
    )


def extract_intent(
    message: str, history: Optional[List[Dict[str, str]]] = None
) -> Optional[Dict[str, Any]]:
    """Return the intent slots ``{equipment_set, focus, secondary_focus,
    body_parts, gym_name, minutes, energy, multi_session_requested,
    deferred_session_hint}`` or None if the message is not an adhoc-session
    request. Raises the same errors as llm_client.extract.
    """
    content = build_extraction_content(message, history)
    slots = llm_client.extract(_SYSTEM, content, _TOOL)
    if not slots.get("is_adhoc_request"):
        return None
    return {
        "equipment_set": slots.get("equipment_set"),
        "focus": slots.get("focus"),
        "secondary_focus": slots.get("secondary_focus"),
        "body_parts": slots.get("body_parts") or [],
        # A259: negative constraints — the composer removes these from the pool
        # before either path (LLM or deterministic) gets to choose.
        "exclude": slots.get("exclude") or [],
        "gym_name": slots.get("gym_name"),
        "minutes": slots.get("minutes"),
        "energy": slots.get("energy"),
        # A252: consumed by the coach response layer (service), not the builder.
        "multi_session_requested": bool(slots.get("multi_session_requested")),
        "deferred_session_hint": slots.get("deferred_session_hint"),
        # B305: drives the localized confirmation message (service layer).
        "language": slots.get("language"),
    }
