"""A243 — LLM intent extraction for the adhoc session composer.

The ONLY place the LLM touches the adhoc flow: it extracts a small structured
slot-spec from the user's chat turn via a forced tool call. It never sees the
exercise catalog and never picks exercises or loads — the deterministic
``adhoc_builder`` composes from these slots.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.coach import llm_client
from backend.engine.adhoc_builder import ADHOC_ENERGY, ADHOC_EQUIPMENT_SETS, ADHOC_FOCUS

_SYSTEM = (
    "You extract the intent behind a climber's request to build an ad-hoc "
    "training session (e.g. 'I'm at a commercial gym, build me a 45-min pulling "
    "session', 'quick core workout at home'). Call the tool once. Set "
    "is_adhoc_request=false if the message is NOT asking you to compose/build a "
    "session (a question, a plan tweak, small talk). When true, infer the slots "
    "from the message; use sensible defaults when unstated (equipment_set=home, "
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


def extract_intent(message: str) -> Optional[Dict[str, Any]]:
    """Return ``{equipment_set, focus, minutes, energy}`` or None if the message
    is not an adhoc-session request. Raises the same errors as llm_client.extract.
    """
    slots = llm_client.extract(_SYSTEM, message, _TOOL)
    if not slots.get("is_adhoc_request"):
        return None
    return {
        "equipment_set": slots.get("equipment_set"),
        "focus": slots.get("focus"),
        "minutes": slots.get("minutes"),
        "energy": slots.get("energy"),
    }
