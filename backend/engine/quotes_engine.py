"""Motivational quotes engine — deterministic, context-aware quote selection."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# Path to quotes catalog (relative to repo root)
_QUOTES_CATALOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "quotes", "v1", "quotes_catalog_v1.json"
)

_cached_quotes: Optional[List[Dict[str, Any]]] = None


def _load_quotes() -> List[Dict[str, Any]]:
    """Load and cache the quotes catalog."""
    global _cached_quotes
    if _cached_quotes is not None:
        return _cached_quotes

    path = os.path.normpath(_QUOTES_CATALOG_PATH)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _cached_quotes = data.get("quotes", [])
    return _cached_quotes


def detect_quote_context(
    session_ids: List[str],
    phase_id: Optional[str] = None,
    is_first_week: bool = False,
) -> str:
    """Detect the appropriate quote context from session/phase info.

    Priority:
    1. deload phase → "deload"
    2. hard session (fingerboard/max intensity) → "hard_day"
    3. first week of new phase → "new_phase"
    4. default → "general"
    """
    if phase_id == "deload":
        return "deload"

    hard_keywords = {"strength_long", "power_contact", "finger_strength"}
    if any(any(kw in sid for kw in hard_keywords) for sid in session_ids):
        return "hard_day"

    if is_first_week:
        return "new_phase"

    return "general"


def get_quote_for_session(
    context: str,
    recent_quote_ids: Optional[List[str]] = None,
    phase_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Select a deterministic quote for the given context.

    Algorithm:
    1. Filter quotes by context tag
    2. Exclude recently seen quote IDs
    3. Sort by id (deterministic)
    4. Return first match
    5. Fallback: if all context quotes exhausted, reset and return first

    Args:
        context: Quote context tag (hard_day, deload, general, etc.)
        recent_quote_ids: List of recently served quote IDs (max 30)
        phase_id: Optional phase for additional context matching

    Returns:
        Quote dict with id, text, author, source_type
    """
    quotes = _load_quotes()
    recent = set(recent_quote_ids or [])

    # Filter by context
    context_quotes = [
        q for q in quotes
        if context in (q.get("contexts") or [])
    ]

    if not context_quotes:
        # Fallback to "general" context
        context_quotes = [
            q for q in quotes
            if "general" in (q.get("contexts") or [])
        ]

    if not context_quotes:
        # Ultimate fallback: any quote
        context_quotes = list(quotes)

    if not context_quotes:
        return {
            "id": "fallback",
            "text": "Every day is a sending day.",
            "author": "Unknown",
            "source_type": "popular",
            "context": context,
        }

    # Sort by id for determinism
    context_quotes.sort(key=lambda q: q.get("id", ""))

    # Exclude recent
    fresh = [q for q in context_quotes if q.get("id") not in recent]

    if not fresh:
        # All exhausted — reset: take first from full context pool
        fresh = context_quotes

    selected = fresh[0]

    return {
        "id": selected.get("id"),
        "text": selected.get("text"),
        "author": selected.get("author"),
        "source_type": selected.get("source_type"),
        "context": context,
    }


def update_quote_history(
    state: Dict[str, Any],
    quote_id: str,
    max_history: int = 30,
) -> None:
    """Append a quote_id to user_state.quote_history and trim to max size."""
    history = state.setdefault("quote_history", [])
    history.append(quote_id)
    if len(history) > max_history:
        state["quote_history"] = history[-max_history:]
