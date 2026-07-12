"""Coach chat orchestration (A-COACH-V1a).

Flow per turn: load rolling history (30 days AND max 40 messages) → build
system blocks (prompt_builder) → call the LLM (llm_client) → persist both the
user message and the assistant reply. Full history is stored permanently;
only the rolling window enters the API-call context.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.coach import llm_client, prompt_builder
from backend.engine import storage

logger = logging.getLogger(__name__)

HISTORY_MAX_MESSAGES = 40
HISTORY_MAX_DAYS = 30
DAILY_MESSAGE_LIMIT = 30
MAX_SUGGESTIONS = 4


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


def suggested_questions(user_id: Optional[str]) -> List[str]:
    """Deterministic, context-aware question chips for the chat UI
    (A-COACH-V1b). No LLM call, no persistence — same inputs, same chips.
    """
    from backend.api.deps import (
        current_phase_and_week, load_state, read_week_plan, this_monday,
    )

    state = load_state(user_id)
    today_iso = date.today().isoformat()
    suggestions: List[str] = []

    try:
        plan = read_week_plan(state, user_id, this_monday()) or state.get(
            "current_week_plan"
        )
        days = prompt_builder._plan_days(plan)
    except Exception:
        logger.exception("coach suggestions: week plan unavailable")
        days = []

    outdoor = next(
        (d for d in days
         if d.get("outdoor_spot_name")
         and d.get("outdoor_session_status") != "done"
         and d.get("date", "") >= today_iso),
        None,
    )
    if outdoor:
        spot = outdoor["outdoor_spot_name"]
        if outdoor.get("date") == today_iso:
            suggestions.append(
                f"How should I approach my outdoor day at {spot} today?"
            )
        else:
            weekday = (outdoor.get("weekday") or outdoor.get("date", "")).capitalize()
            suggestions.append(f"How should I prepare for {spot} on {weekday}?")

    today_day = next((d for d in days if d.get("date") == today_iso), None)
    planned_today = [
        s for s in (today_day or {}).get("sessions") or []
        if (s.get("status") or "planned") == "planned"
    ]
    if planned_today:
        suggestions.append(
            "Walk me through today's session — what should I focus on?"
        )

    mc = state.get("macrocycle") or {}
    phases = mc.get("phases") or []
    if phases:
        try:
            pi, _ = current_phase_and_week(mc)
            phase_id = str((phases[pi] if pi < len(phases) else {}).get("phase_id", ""))
            if phase_id == "deload":
                suggestions.append("Why is this week a deload — what should I avoid?")
            elif phase_id:
                pretty = phase_id.replace("_", " ")
                suggestions.append(f"What matters most in the {pretty} phase?")
        except Exception:
            logger.exception("coach suggestions: phase lookup failed")

    suggestions.append("How is my training going so far?")
    return suggestions[:MAX_SUGGESTIONS]


def handle_chat(
    user_id: Optional[str], message: str,
    lat: Optional[float] = None, lon: Optional[float] = None,
) -> str:
    """One chat turn. Returns the assistant reply (already persisted).

    ``lat``/``lon``: optional current location from the client — enables the
    weather section in the context block (A-COACH-V1b).
    """
    history = _load_history(user_id)
    system_blocks = prompt_builder.build_system_blocks(
        user_id, message, lat=lat, lon=lon
    )
    messages: List[Dict[str, Any]] = history + [
        {"role": "user", "content": message}
    ]
    reply = llm_client.chat(system_blocks, messages)
    storage.append_coach_message(user_id, "user", message)
    storage.append_coach_message(user_id, "assistant", reply)
    return reply
