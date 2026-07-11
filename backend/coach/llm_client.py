"""Thin Anthropic SDK wrapper for the coach (A-COACH-V1a).

Single entry point: ``chat(system_blocks, messages) -> str``.

Provider abstraction: everything Anthropic-specific lives in this module, so
a future provider/model swap is config-only from the callers' perspective.

Prompt caching is MANDATORY (unit economics): the first system block (static
KB — L0+L1+L2+instructions, identical across all users/calls) carries a
``cache_control: ephemeral`` breakpoint; the second block (routed L3 + user
context) is dynamic and uncached. Usage — including cache read/creation
tokens — is logged on every call; a persistent 0 on both cache counters means
caching is broken and must be visible in the logs.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

# Re-exported so callers can catch provider errors without importing the SDK.
APIError = anthropic.APIError

_client: anthropic.Anthropic | None = None


class CoachConfigError(RuntimeError):
    """Raised when the coach LLM is not configured (missing API key)."""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            # Fail loud — never a silent fallback (fixed decision).
            raise CoachConfigError(
                "ANTHROPIC_API_KEY is not set — the coach cannot call the LLM"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _model() -> str:
    return os.environ.get("COACH_MODEL", DEFAULT_MODEL)


def chat(system_blocks: List[str], messages: List[Dict[str, Any]]) -> str:
    """Send one chat turn. Returns the assistant reply text.

    ``system_blocks``: [static_kb, dynamic] from prompt_builder.
    ``messages``: alternating user/assistant dicts, last one the new user msg.
    """
    client = _get_client()
    system: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": system_blocks[0],
            "cache_control": {"type": "ephemeral"},
        }
    ]
    for block in system_blocks[1:]:
        system.append({"type": "text", "text": block})

    response = client.messages.create(
        model=_model(),
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
    )

    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0
    logger.info(
        "coach llm usage: model=%s input=%s output=%s cache_read=%s cache_creation=%s",
        _model(), usage.input_tokens, usage.output_tokens,
        cache_read, cache_created,
    )
    if cache_read == 0 and cache_created == 0:
        logger.warning(
            "coach prompt cache INACTIVE (cache_read=0, cache_creation=0) — "
            "check static-block stability and minimum cacheable prefix size"
        )

    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
