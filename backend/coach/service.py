"""Coach chat orchestration (A-COACH-V1a).

Flow per turn: load rolling history (30 days AND max 40 messages) → build
system blocks (prompt_builder) → call the LLM (llm_client) → persist both the
user message and the assistant reply. Full history is stored permanently;
only the rolling window enters the API-call context.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.coach import llm_client, prompt_builder
from backend.engine import storage

logger = logging.getLogger(__name__)

HISTORY_MAX_MESSAGES = 40
HISTORY_MAX_DAYS = 30
DAILY_MESSAGE_LIMIT = 30


def messages_sent_today(user_id: Optional[str]) -> int:
    """User messages sent since UTC midnight (rate-limit counter)."""
    today_start = datetime.now(timezone.utc).date().isoformat()
    return storage.count_coach_user_messages_since(user_id, today_start)


def _load_history(user_id: Optional[str]) -> List[Dict[str, str]]:
    """Rolling context window, chronological, starting with a user message."""
    since = (
        datetime.now(timezone.utc) - timedelta(days=HISTORY_MAX_DAYS)
    ).isoformat()
    rows = storage.read_coach_messages(
        user_id, limit=HISTORY_MAX_MESSAGES, since=since
    )
    history = [
        {"role": r["role"], "content": r["content"]}
        for r in reversed(rows)
        if r.get("role") in ("user", "assistant") and r.get("content")
    ]
    # The Messages API requires the first message to be a user turn.
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


def handle_chat(user_id: Optional[str], message: str) -> str:
    """One chat turn. Returns the assistant reply (already persisted)."""
    history = _load_history(user_id)
    system_blocks = prompt_builder.build_system_blocks(user_id, message)
    messages: List[Dict[str, Any]] = history + [
        {"role": "user", "content": message}
    ]
    reply = llm_client.chat(system_blocks, messages)
    storage.append_coach_message(user_id, "user", message)
    storage.append_coach_message(user_id, "assistant", reply)
    return reply
