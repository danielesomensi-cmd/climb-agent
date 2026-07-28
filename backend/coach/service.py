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
MAX_SUGGESTIONS = 6


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

    # A237 — Adhoc Coach v0: always-relevant off-plan / commercial-gym chips.
    suggestions.append("I'm at a regular gym today — build me a session")
    suggestions.append("I don't feel like today's session — what are my alternatives?")

    suggestions.append("How is my training going so far?")
    return suggestions[:MAX_SUGGESTIONS]


def handle_adhoc_compose(
    user_id: Optional[str], message: str
) -> Optional[Dict[str, Any]]:
    """A243 — extract intent, deterministically compose an adhoc session preview.

    Returns ``{"adhoc": True, "session": <custom_session preview>}`` or None when
    the message is not an adhoc-session request (caller then falls back to chat).

    Composition does NOT persist the session (A243 decision — zero orphans);
    persistence happens on the user's CTA via the custom-session + replanner
    endpoints. On success we DO append the turn to coach history (so it counts
    toward the daily limit and keeps the conversation coherent).
    """
    from backend.api.deps import load_state
    from backend.coach import adhoc_intent
    from backend.engine.adaptive_replan import load_exercises_by_id
    from backend.engine.adhoc_builder import compose_adhoc_session

    # B281: give the extractor the recent conversation — short follow-ups like
    # "riprovi a crearla?" carry their place/focus/minutes in earlier turns.
    history = _load_history(user_id)
    intent = adhoc_intent.extract_intent(message, history=history)
    if intent is None:
        # Not an adhoc request — no history write, no rate-limit charge here.
        return None

    state = load_state(user_id)
    catalog = load_exercises_by_id()
    session = compose_adhoc_session(intent, state, catalog)

    storage.append_coach_message(user_id, "user", message)
    summary = build_adhoc_summary(session, intent)
    storage.append_coach_message(user_id, "assistant", summary)

    return {"adhoc": True, "session": session, "summary": summary}


def build_adhoc_summary(
    session: Dict[str, Any], intent: Dict[str, Any]
) -> str:
    """A243/A252 — the assistant's chat reply for a composed adhoc session.

    Pure + deterministic (no I/O) so it is unit-testable. When the user asked
    for MULTIPLE separate sessions (A252 / audit A1), the builder made only the
    sooner one — so we say so explicitly and invite them to ask again for the
    rest, rather than silently dropping the second session.
    """
    lang = intent.get("language") if intent.get("language") in ("en", "it") else "en"
    if lang == "it":
        # The explanation string stays English (it can carry A252 honesty notes
        # — e.g. a requested muscle with no equipment-compatible exercises —
        # that must not be dropped); the frame is localized.
        summary = (
            f"Ti ho preparato una sessione — {session['name']} "
            f"(~{session['estimated_duration_minutes']} min). "
            f"{session['explanation']} "
            f"La card è qui sotto: un tap su \"Add to today & run\" e parte."
        )
    else:
        summary = (
            f"I built you a session — {session['name']} "
            f"(~{session['estimated_duration_minutes']} min). {session['explanation']}"
        )
    if intent.get("multi_session_requested"):
        hint = (intent.get("deferred_session_hint") or "").strip()
        if lang == "it":
            summary += (
                " Occhio: hai chiesto più di una sessione — ne preparo una alla "
                "volta, questa è la prima."
            )
            if hint:
                summary += f" Per l'altra ({hint}), riscrivimi e te la preparo."
            else:
                summary += " Riscrivimi per l'altra e te la preparo."
        else:
            summary += (
                " Heads up: you asked for more than one session — I build one at a "
                "time, so this is just the first."
            )
            if hint:
                summary += f" For the other one ({hint}), message me again and I'll prepare it."
            else:
                summary += " Message me again for the other one and I'll prepare it."
    return summary


def handle_chat(
    user_id: Optional[str], message: str,
    lat: Optional[float] = None, lon: Optional[float] = None,
) -> str:
    """One chat turn. Returns the assistant reply (already persisted).

    ``lat``/``lon``: optional current location from the client — passed to the
    ``get_weather`` tool executor so "here" resolves to the user's GPS
    (A244; weather is now on-demand tool use, not a pre-fetch).
    """
    from backend.api.deps import load_state
    from backend.coach import weather_tool

    state = load_state(user_id)
    history = _load_history(user_id)
    system_blocks = prompt_builder.build_system_blocks(user_id, message, state=state)
    messages: List[Dict[str, Any]] = history + [
        {"role": "user", "content": message}
    ]

    def _tool_executor(name: str, tool_input: Dict[str, Any]) -> str:
        if name == weather_tool.WEATHER_TOOL["name"]:
            return weather_tool.execute_get_weather(tool_input, state, lat, lon)
        return f"Unknown tool: {name}"

    reply = llm_client.chat(
        system_blocks, messages,
        tools=[weather_tool.WEATHER_TOOL],
        tool_executor=_tool_executor,
    )
    storage.append_coach_message(user_id, "user", message)
    storage.append_coach_message(user_id, "assistant", reply)
    return reply
