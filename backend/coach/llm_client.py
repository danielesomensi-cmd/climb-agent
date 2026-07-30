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
from typing import Any, Callable, Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"

# B311 — output cap. 1024 was set against the design's "300-800 tokens" target,
# which was measured in English; Italian costs roughly 2.3 chars/token, so a
# structured Italian answer with a table hits the cap at ~2,300 characters and
# stops mid-sentence (`stop_reason=max_tokens`). The D266 re-run found 10 of 28
# regression answers truncated that way. Env-overridable so the ceiling can be
# tuned without a deploy.
MAX_TOKENS = int(os.environ.get("COACH_MAX_TOKENS", "2048"))

# A244 — tool-use loop guards. MAX_TOOL_CALLS bounds provider/OWM cost per coach
# message; MAX_ITERATIONS is a hard backstop so a misbehaving model can never
# spin the loop forever (it always terminates in a text answer).
MAX_TOOL_CALLS = 2
MAX_ITERATIONS = 4

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


def _log_usage(response: Any) -> None:
    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0
    logger.info(
        "coach llm usage: model=%s input=%s output=%s cache_read=%s cache_creation=%s",
        _model(), usage.input_tokens, usage.output_tokens,
        cache_read, cache_created,
    )
    if getattr(response, "stop_reason", None) == "max_tokens":
        logger.warning(
            "coach answer hit MAX_TOKENS=%s (stop_reason=max_tokens) — the user "
            "saw a reply cut mid-sentence; raise COACH_MAX_TOKENS or tighten L1",
            MAX_TOKENS,
        )
    if cache_read == 0 and cache_created == 0:
        logger.warning(
            "coach prompt cache INACTIVE (cache_read=0, cache_creation=0) — "
            "check static-block stability and minimum cacheable prefix size"
        )


def _final_text(response: Any) -> str:
    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


def chat(
    system_blocks: List[str],
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_executor: Optional[Callable[[str, Dict[str, Any]], str]] = None,
) -> str:
    """Send one chat turn. Returns the assistant reply text.

    ``system_blocks``: [static_kb, dynamic] from prompt_builder.
    ``messages``: alternating user/assistant dicts, last one the new user msg.
    ``tools`` / ``tool_executor`` (A244): when both are given the call runs a
    native tool-use loop — if the model emits ``tool_use`` blocks they are
    executed via ``tool_executor(name, input) -> str`` and fed back as
    ``tool_result`` turns until the model returns text (bounded by
    MAX_TOOL_CALLS / MAX_ITERATIONS). Omitting them preserves the plain
    single-call behaviour (zero regression for non-weather turns: the tool
    definition rides the cached prefix, and no tool call fires unless needed).
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

    create_kwargs: Dict[str, Any] = {}
    if tools:
        create_kwargs["tools"] = tools

    convo: List[Dict[str, Any]] = list(messages)  # never mutate the caller's list
    tool_calls = 0

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=_model(),
            max_tokens=MAX_TOKENS,
            system=system,
            messages=convo,
            **create_kwargs,
        )
        _log_usage(response)

        if response.stop_reason != "tool_use" or tool_executor is None:
            return _final_text(response)

        # Echo the assistant tool_use turn, then answer each tool_use block.
        convo.append({"role": "assistant", "content": response.content})
        results: List[Dict[str, Any]] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if tool_calls >= MAX_TOOL_CALLS:
                result = "Weather lookup limit reached for this message."
            else:
                tool_calls += 1
                try:
                    result = tool_executor(block.name, dict(block.input or {}))
                except Exception:  # noqa: BLE001 — a tool must never break the loop
                    logger.exception("coach tool_executor failed for %s", block.name)
                    result = "That lookup is unavailable right now."
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )
        convo.append({"role": "user", "content": results})

    # Backstop: force one final, tool-free answer so we always return text.
    response = client.messages.create(
        model=_model(), max_tokens=MAX_TOKENS, system=system, messages=convo,
    )
    _log_usage(response)
    return _final_text(response)


def extract(system_text: str, message: str, tool: Dict[str, Any]) -> Dict[str, Any]:
    """Force-call a single extraction *tool* on one user *message*.

    Returns the tool's ``input`` dict (the structured slots). The model is given
    only the tool schema — never the exercise catalog — so it can extract intent
    but can never pick exercises or loads (A243). Raises CoachConfigError if the
    LLM is unconfigured and propagates anthropic.APIError on provider failure.
    """
    client = _get_client()
    response = client.messages.create(
        model=_model(),
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system_text}],
        messages=[{"role": "user", "content": message}],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == tool["name"]:
            return dict(block.input or {})
    return {}
