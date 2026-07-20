"""A243 — LLM intent extraction for the adhoc session composer.

The ONLY place the LLM touches the adhoc flow: it extracts a small structured
slot-spec from the user's chat turn via a forced tool call. It never sees the
exercise catalog and never picks exercises or loads — the deterministic
``adhoc_builder`` composes from these slots.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.coach import llm_client
from backend.engine.adhoc_builder import ADHOC_ENERGY, ADHOC_EQUIPMENT_SETS, ADHOC_FOCUS

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
    "available. If the user asks for two focuses (e.g. 'core e tecnica'), put "
    "the dominant one in focus and the other in secondary_focus. Use sensible "
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
        },
        "required": ["is_adhoc_request"],
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
    """Return ``{equipment_set, focus, minutes, energy}`` or None if the message
    is not an adhoc-session request. Raises the same errors as llm_client.extract.
    """
    content = build_extraction_content(message, history)
    slots = llm_client.extract(_SYSTEM, content, _TOOL)
    if not slots.get("is_adhoc_request"):
        return None
    return {
        "equipment_set": slots.get("equipment_set"),
        "focus": slots.get("focus"),
        "secondary_focus": slots.get("secondary_focus"),
        "gym_name": slots.get("gym_name"),
        "minutes": slots.get("minutes"),
        "energy": slots.get("energy"),
    }
