"""Coach system-prompt assembly (A-COACH-V1a).

Builds the two system blocks sent to the LLM:

  Block 1 (STATIC — prompt-cached): L0 safety + L1 voice + L2 decision index
      + the runtime instruction block. Byte-identical across all users and
      calls, so the ``cache_control: ephemeral`` breakpoint in
      ``llm_client.chat`` amortises it across every request.
  Block 2 (DYNAMIC — uncached): up to 3 routed L3 topic files (routing varies
      per query) + the compact user-context block (profile, plan position,
      week plan, today's session, recent logs, equipment).

Token budget guard: total system prompt target ≤ 25K tokens (chars/4
estimate). On overflow, recent-logs lines are truncated first, then week-plan
detail. A warning is logged whenever truncation kicks in.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional

from backend.coach.routing import KNOWLEDGE_DIR, route_query

logger = logging.getLogger(__name__)

TOKEN_BUDGET = 25_000

_ALWAYS_LOADED = (
    KNOWLEDGE_DIR / "L0_safety_hard_rules.md",
    KNOWLEDGE_DIR / "L1_coach_voice.md",
    KNOWLEDGE_DIR / "L2_decision_index.md",
)

# Runtime behaviour contract — static, appended to Block 1 so it rides the
# prompt cache. Keep this string stable: any byte change invalidates the
# cache for every user.
INSTRUCTION_BLOCK = """\
# Runtime instructions (coach service)

- You are the climb-agent Coach: a conversational layer OVER a deterministic
  training engine. You can see the user's profile, plan and logs (provided
  below), but you have NO ability to modify anything. You suggest and explain
  only. Never claim to have changed, rescheduled, or updated the plan, a
  session, or any user data. When the user wants a change applied, point them
  to the app action that does it (e.g. the replan option on a day, logging a
  free session or mobility session, editing settings).
- Always respond in English, regardless of the language the user writes in.
- Cite sources (Author Year) only when the user asks "why" or for a source,
  or when a recommendation is genuinely counter-intuitive. Never invent a
  citation; if the knowledge base has no source, say so.
- Boulder grades are Fontainebleau (6A, 7B, 8A+). Use Fontainebleau in your
  answers unless the user uses another scale first.
- Keep answers practical and concise (a few short paragraphs or a short
  list). This is a chat on a phone, not an essay.
"""


@lru_cache(maxsize=1)
def build_static_block() -> str:
    """L0 + L1 + L2 + instruction block. Cached for the process lifetime."""
    parts: List[str] = []
    for path in _ALWAYS_LOADED:
        try:
            parts.append(path.read_text(encoding="utf-8").strip())
        except OSError:
            logger.error("Coach KB file missing: %s", path)
    parts.append(INSTRUCTION_BLOCK.strip())
    return "\n\n---\n\n".join(parts)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _fmt(value: Any) -> str:
    return str(value) if value not in (None, "", []) else "—"


# ---------------------------------------------------------------------------
# User context sections
# ---------------------------------------------------------------------------

def _profile_section(state: Dict[str, Any]) -> str:
    assessment = state.get("assessment") or {}
    grades = assessment.get("grades") or {}
    body = assessment.get("body") or state.get("body") or {}
    profile = assessment.get("profile") or {}
    lines = ["## Athlete profile"]
    lines.append(
        f"- Grades: lead RP {_fmt(grades.get('lead_max_rp'))}, "
        f"lead OS {_fmt(grades.get('lead_max_os'))}, "
        f"boulder RP {_fmt(grades.get('boulder_max_rp'))} (Fontainebleau), "
        f"boulder OS {_fmt(grades.get('boulder_max_os'))} (Fontainebleau)"
    )
    if body:
        lines.append(
            f"- Body: age {_fmt(body.get('age'))}, "
            f"height {_fmt(body.get('height_cm'))} cm, "
            f"weight {_fmt(body.get('weight_kg'))} kg"
        )
    if profile:
        axes = sorted(profile.items(), key=lambda kv: kv[1])
        axes_str = ", ".join(f"{k} {v}/100" for k, v in axes)
        weakest = ", ".join(k for k, _ in axes[:2])
        lines.append(f"- Assessment (5-axis): {axes_str}")
        lines.append(f"- Weakest axes: {weakest}")
    limitations = (state.get("limitations") or {}).get("active_flags") or []
    if limitations:
        lines.append(f"- Active limitations: {', '.join(map(str, limitations))}")
    return "\n".join(lines)


def _plan_section(state: Dict[str, Any]) -> str:
    goal = state.get("goal") or {}
    mc = state.get("macrocycle") or {}
    lines = ["## Goal & plan position"]
    lines.append(
        f"- Goal: {_fmt(goal.get('goal_type'))} — target "
        f"{_fmt(goal.get('target_grade') or goal.get('target_boulder_grade'))} "
        f"({_fmt(goal.get('target_style'))}), current {_fmt(goal.get('current_grade'))}, "
        f"discipline {_fmt(goal.get('discipline'))}, deadline {_fmt(goal.get('deadline'))}"
    )
    phases = mc.get("phases") or []
    if not phases:
        lines.append("- No active macrocycle (user has not generated a plan yet).")
        return "\n".join(lines)
    from backend.api.deps import current_phase_and_week, is_plan_paused

    pi, wi = current_phase_and_week(mc)
    abs_week = sum(p.get("duration_weeks", 1) for p in phases[:pi]) + wi + 1
    total = mc.get("total_weeks") or sum(p.get("duration_weeks", 1) for p in phases)
    phase = phases[pi] if pi < len(phases) else {}
    phase_seq = " → ".join(
        f"{p.get('phase_id')} ({p.get('duration_weeks')}w)" for p in phases
    )
    lines.append(
        f"- Macrocycle: {mc.get('start_date')} → {mc.get('end_date')}, "
        f"{total} weeks total. Phases: {phase_seq}"
    )
    lines.append(
        f"- Current position: week {abs_week} of {total}, phase "
        f"'{phase.get('phase_id')}' (week {wi + 1} of {phase.get('duration_weeks')})"
    )
    if is_plan_paused(state):
        lines.append("- The plan is currently PAUSED (user must resume it in the app).")
    return "\n".join(lines)


def _session_status(sess: Dict[str, Any]) -> str:
    return str(sess.get("status") or "planned")


def _plan_days(plan: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract the day list from a week plan.

    The planner stores days under ``plan["weeks"][0]["days"]``; some legacy /
    test fixtures use a flat ``plan["days"]``. Support both.
    """
    if not plan:
        return []
    if plan.get("days"):
        return plan["days"]
    weeks = plan.get("weeks") or []
    if weeks and isinstance(weeks[0], dict):
        return weeks[0].get("days") or []
    return []


def _week_section(
    state: Dict[str, Any], user_id: Optional[str], today_iso: str
) -> str:
    from backend.api.deps import read_week_plan, this_monday

    plan = read_week_plan(state, user_id, this_monday()) or state.get(
        "current_week_plan"
    )
    days = _plan_days(plan)
    lines = ["## Current week plan"]
    if not days:
        lines.append("- No week plan generated for the current week.")
        return "\n".join(lines)
    for day in days:
        d = day.get("date", "")
        marker = " (TODAY)" if d == today_iso else ""
        sessions = day.get("sessions") or []
        if not sessions:
            lines.append(f"- {d} {day.get('weekday', '')}{marker}: rest")
            continue
        descr = ", ".join(
            f"{s.get('session_id')} [{_session_status(s)}, {s.get('location', '?')}]"
            for s in sessions
        )
        lines.append(f"- {d} {day.get('weekday', '')}{marker}: {descr}")
    return "\n".join(lines)


def _today_section(
    state: Dict[str, Any], user_id: Optional[str], today_iso: str
) -> str:
    from backend.api.deps import read_week_plan, this_monday

    plan = read_week_plan(state, user_id, this_monday()) or state.get(
        "current_week_plan"
    )
    lines = ["## Today's session detail"]
    day = None
    for d in _plan_days(plan):
        if d.get("date") == today_iso:
            day = d
            break
    sessions = (day or {}).get("sessions") or []
    if not sessions:
        lines.append("- Nothing planned today (rest day or no plan).")
        return "\n".join(lines)
    for sess in sessions:
        lines.append(
            f"- {sess.get('session_id')} [{_session_status(sess)}, "
            f"{sess.get('location', '?')}]"
        )
        resolved = (sess.get("resolved") or {}).get("resolved_session") or {}
        for inst in resolved.get("exercise_instances") or []:
            rx = inst.get("prescription") or {}
            rx_bits = []
            for key in ("sets", "reps", "duration_seconds", "hold_seconds",
                        "rest_seconds", "load_kg", "load_pct", "intensity_pct"):
                if rx.get(key) not in (None, "", []):
                    rx_bits.append(f"{key}={rx[key]}")
            lines.append(
                f"    - {inst.get('name') or inst.get('exercise_id')}"
                + (f" ({', '.join(rx_bits)})" if rx_bits else "")
            )
    return "\n".join(lines)


def _logs_section(
    state: Dict[str, Any], user_id: Optional[str], today: date
) -> List[str]:
    """Last-14-days log summary, one line per entry (oldest first).

    Sources: state["session_completion_log"] (indoor done/skipped, enriched
    with feedback_log difficulty + duration), state["free_sessions"], and the
    outdoor logs from storage. Returned as a list so the budget guard can
    drop oldest lines first.
    """
    from backend.engine import storage

    since = (today - timedelta(days=14)).isoformat()
    lines: List[str] = []

    fb_index: Dict[Any, Dict[str, Any]] = {
        (e.get("date"), e.get("session_id")): e
        for e in state.get("feedback_log") or []
    }
    for entry in state.get("session_completion_log") or []:
        d = entry.get("date") or ""
        if d < since:
            continue
        sid = entry.get("session_id") or "session"
        bits = [f"{d}: {sid} ({entry.get('status') or 'done'})"]
        fb = fb_index.get((d, sid))
        if fb:
            if fb.get("difficulty"):
                bits.append(f"felt: {fb['difficulty']}")
            if fb.get("session_duration_seconds"):
                bits.append(
                    f"duration: {int(fb['session_duration_seconds']) // 60} min"
                )
        lines.append("- " + ", ".join(bits))

    for entry in state.get("free_sessions") or []:
        d = entry.get("date") or ""
        if d < since:
            continue
        climbs = entry.get("climbs") or []
        bits = [
            f"{d}: free session ({entry.get('session_mode') or 'free'}, "
            f"{entry.get('surface') or '?'})"
        ]
        if climbs:
            grades = [c.get("grade") for c in climbs
                      if isinstance(c, dict) and c.get("grade")]
            bits.append(f"{len(climbs)} climbs"
                        + (f": {', '.join(map(str, grades[:8]))}" if grades else ""))
        lines.append("- " + ", ".join(bits))
    try:
        for entry in storage.read_outdoor_logs(user_id, since_date=since):
            routes = entry.get("routes") or entry.get("climbs") or []
            sent = [r.get("grade") for r in routes if isinstance(r, dict)
                    and r.get("grade")]
            bits = [f"{entry.get('date')}: outdoor at "
                    f"{entry.get('spot_name') or entry.get('spot_id') or '?'}"]
            if sent:
                bits.append(f"climbs: {', '.join(map(str, sent[:8]))}")
            lines.append("- " + ", ".join(bits))
    except Exception:
        logger.exception("coach: failed to read outdoor logs")
    lines.sort()  # ISO-date prefix → chronological
    return lines


def _equipment_section(state: Dict[str, Any]) -> str:
    eq = state.get("equipment") or {}
    lines = ["## Equipment available"]
    home = eq.get("home") or []
    lines.append(f"- Home: {', '.join(home) if home else 'none'}")
    for gym in eq.get("gyms") or []:
        gear = gym.get("equipment") or []
        lines.append(
            f"- Gym '{gym.get('name', 'gym')}': "
            f"{', '.join(gear) if gear else 'unspecified'}"
        )
    prefs = state.get("preferences") or {}
    if prefs.get("finger_training_device"):
        lines.append(f"- Finger training device: {prefs['finger_training_device']}")
    return "\n".join(lines)


def build_user_context(
    state: Dict[str, Any], user_id: Optional[str], max_log_lines: Optional[int] = None,
    include_week_detail: bool = True,
) -> str:
    """Assemble the delimited user-context block."""
    today = date.today()
    today_iso = today.isoformat()
    sections = [
        "=== USER CONTEXT (read-only snapshot, generated "
        f"{today_iso}) ===",
        _profile_section(state),
        _plan_section(state),
    ]
    if include_week_detail:
        sections.append(_week_section(state, user_id, today_iso))
        sections.append(_today_section(state, user_id, today_iso))
    log_lines = _logs_section(state, user_id, today)
    if max_log_lines is not None and len(log_lines) > max_log_lines:
        log_lines = log_lines[-max_log_lines:]
    sections.append(
        "## Training logs (last 14 days)\n"
        + ("\n".join(log_lines) if log_lines else "- No logged sessions.")
    )
    sections.append(_equipment_section(state))
    sections.append("=== END USER CONTEXT ===")
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_dynamic_block(
    state: Dict[str, Any], user_id: Optional[str], query: str
) -> str:
    """Routed L3 files + user context, with token-budget truncation."""
    l3_parts: List[str] = []
    for path in route_query(query):
        try:
            l3_parts.append(path.read_text(encoding="utf-8").strip())
        except OSError:
            logger.error("Coach L3 file missing: %s", path)
    l3_text = "\n\n---\n\n".join(l3_parts)

    static_tokens = _estimate_tokens(build_static_block())

    def _assemble(max_log_lines: Optional[int], include_week_detail: bool) -> str:
        context = build_user_context(
            state, user_id,
            max_log_lines=max_log_lines,
            include_week_detail=include_week_detail,
        )
        return (
            "# Topic knowledge (routed for this question)\n\n"
            + l3_text
            + "\n\n"
            + context
        )

    dynamic = _assemble(None, True)
    if static_tokens + _estimate_tokens(dynamic) <= TOKEN_BUDGET:
        return dynamic

    # Over budget: truncate logs first, then drop week-plan detail.
    logger.warning(
        "coach prompt over %d-token budget — truncating logs", TOKEN_BUDGET
    )
    dynamic = _assemble(10, True)
    if static_tokens + _estimate_tokens(dynamic) <= TOKEN_BUDGET:
        return dynamic
    logger.warning(
        "coach prompt still over budget — dropping week plan detail"
    )
    return _assemble(10, False)


def build_system_blocks(user_id: Optional[str], query: str) -> List[str]:
    """Return [static_block, dynamic_block] for llm_client.chat."""
    from backend.api.deps import load_state

    state = load_state(user_id)
    return [build_static_block(), build_dynamic_block(state, user_id, query)]


def build_system_prompt(user_id: Optional[str], query: str) -> str:
    """Full system prompt as a single string (brief-spec convenience)."""
    return "\n\n".join(build_system_blocks(user_id, query))
