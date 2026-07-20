"""Coach system-prompt assembly (A-COACH-V1a).

Builds the two system blocks sent to the LLM:

  Block 1 (STATIC — prompt-cached): L0 safety + L1 voice + L2 decision index
      + the runtime instruction block. Byte-identical across all users and
      calls, so the ``cache_control: ephemeral`` breakpoint in
      ``llm_client.chat`` amortises it across every request.
  Block 2 (DYNAMIC — uncached): up to 3 routed L3 topic files (routing varies
      per query) + the compact user-context block (profile, baselines &
      working loads, plan position + trips, week plan incl. outdoor/other-
      activity days, today's session, recent logs, equipment).

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
- Respond in the language the user writes in (Italian message → Italian
  reply, English → English). Use exactly ONE language per reply — never mix
  languages within a response. Keep exercise/session IDs and grades as-is.
- Cite sources (Author Year) only when the user asks "why" or for a source,
  or when a recommendation is genuinely counter-intuitive. Never invent a
  citation; if the knowledge base has no source, say so.
- Boulder grades are Fontainebleau (6A, 7B, 8A+). Use Fontainebleau in your
  answers unless the user uses another scale first.
- Keep answers practical and concise (a few short paragraphs or a short
  list). This is a chat on a phone, not an essay.
- When asked to build/compose a session (e.g. at a commercial gym, or an
  off-plan alternative), output a clearly structured textual block: warm-up →
  2-4 main blocks → optional core/prehab finisher, with sets/reps and load as
  RPE/RIR only — NEVER absolute kilograms. Use only real catalog exercises.
  This is a suggestion, not a plan change: never state or imply the session was
  added, scheduled, or logged by YOU.
- The APP can turn a build request into a real, runnable session (A243): when
  the user phrases a direct build request ("creami una sessione di core di 60
  minuti in palestra", "build me a 45-min pulling session"), the app composes
  it deterministically and shows a card with an "Add to today & run" button —
  one tap adds it to today as an off-plan session and opens the guided player.
  So when the user asks you to create/save/add a session for them, NEVER say
  it is impossible and NEVER apologize for a previously created session: tell
  them to send the request as a single direct message with place, focus and
  minutes (so the app builds the card), or to use the Session Builder manually.
  If the conversation shows a session was already built ("I built you a
  session — …"), that session is real and valid — never call it an error.
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
    if assessment.get("last_assessed"):
        lines.append(f"- Last assessed: {assessment['last_assessed']}")
    limitations = (state.get("limitations") or {}).get("active_flags") or []
    if limitations:
        lines.append(f"- Active limitations: {', '.join(map(str, limitations))}")
    return "\n".join(lines)


def _baselines_section(state: Dict[str, Any]) -> str:
    """Test maximals + current working loads (B-COACH-CONTEXT-FIX).

    Sources: baselines.hangboard / baselines.pulling, assessment.tests,
    working_loads.entries (capped at 15, most recently updated first).
    """
    lines = ["## Baselines & working loads"]
    baselines = state.get("baselines") or {}
    for hb in baselines.get("hangboard") or []:
        setup_bits = []
        if hb.get("edge_mm"):
            setup_bits.append(f"{hb['edge_mm']}mm edge")
        if hb.get("grip"):
            setup_bits.append(str(hb["grip"]))
        if hb.get("hang_seconds"):
            setup_bits.append(f"{hb['hang_seconds']}s hang")
        lines.append(
            f"- Hangboard max: {_fmt(hb.get('max_total_load_kg'))} kg total"
            + (f" ({', '.join(setup_bits)})" if setup_bits else "")
            + f" — source: {_fmt(hb.get('source'))}, {_fmt(hb.get('estimated_at'))}"
        )
    pulling = baselines.get("pulling") or {}
    if pulling:
        pull_bits = ", ".join(f"{k}={v}" for k, v in pulling.items()
                              if v not in (None, "", []))
        lines.append(f"- Pulling baseline: {pull_bits}")
    tests = (state.get("assessment") or {}).get("tests") or {}
    for key, value in tests.items():
        if value not in (None, "", []):
            lines.append(f"- Test {key}: {value}")
    entries = (state.get("working_loads") or {}).get("entries") or []
    entries = sorted(entries, key=lambda e: str(e.get("updated_at") or ""),
                     reverse=True)[:15]
    for entry in entries:
        setup = entry.get("setup") or {}
        setup_bits = ", ".join(f"{k}={v}" for k, v in setup.items()
                               if v not in (None, "", []))
        load_bits = []
        for key, label in (("next_external_load_kg", "next external load"),
                           ("next_total_load_kg", "next total load")):
            if entry.get(key) is not None:
                load_bits.append(f"{label} {entry[key]} kg")
        if entry.get("next_target_grade"):
            load_bits.append(f"next target grade {entry['next_target_grade']}")
        if not load_bits:
            continue
        lines.append(
            f"- Working load: {entry.get('exercise_id', '?')}"
            + (f" ({setup_bits})" if setup_bits else "")
            + f": {', '.join(load_bits)}"
            + (f" (updated {entry['updated_at']})" if entry.get("updated_at") else "")
        )
    if len(lines) == 1:
        lines.append(
            "- No recorded test maximals or working loads yet. Do NOT invent "
            "numbers — suggest running the assessment tests instead."
        )
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
    trips = state.get("trips") or []
    for trip in trips:
        lines.append(
            f"- Planned trip: {_fmt(trip.get('name'))} "
            f"{_fmt(trip.get('start_date'))} → {_fmt(trip.get('end_date'))} "
            f"({_fmt(trip.get('discipline'))}, priority {_fmt(trip.get('priority'))})"
        )
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


def _day_extras(day: Dict[str, Any]) -> List[str]:
    """Day-level items that live OUTSIDE day["sessions"] (B-COACH-CONTEXT-FIX).

    Planned outdoor days, reserved outdoor slots, other activities and
    pre-trip deload markers are stored as flat fields on the day dict —
    without this, an outdoor day with no guided session reads as "rest".
    """
    extras: List[str] = []
    if day.get("outdoor_spot_name"):
        extras.append(
            f"OUTDOOR climbing at {day['outdoor_spot_name']} "
            f"[{day.get('outdoor_session_status') or 'planned'}, "
            f"{day.get('outdoor_discipline') or 'both'}]"
        )
    elif day.get("outdoor_slot"):
        extras.append("outdoor day reserved (no crag chosen yet)")
    if day.get("other_activity"):
        extras.append(
            f"other activity: {day.get('other_activity_name') or 'unspecified'}"
        )
    if day.get("pretrip_deload"):
        extras.append("pre-trip deload day")
    return extras


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
        parts = _day_extras(day) + [
            f"{s.get('session_id')} [{_session_status(s)}, {s.get('location', '?')}]"
            for s in sessions
        ]
        descr = ", ".join(parts) if parts else "rest"
        lines.append(f"- {d} {day.get('weekday', '')}{marker}: {descr}")
    planned_load = ((plan or {}).get("weekly_load_summary") or {}).get(
        "planned_load"
    )
    if planned_load is not None:
        lines.append(
            f"- Planned training load this week: {planned_load} "
            "(engine load units)"
        )
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
    extras = _day_extras(day or {})
    for extra in extras:
        lines.append(f"- {extra}")
    if day and day.get("outdoor_spot_name"):
        lines.append(
            "  (This planned outdoor day IS today's main session — never "
            "tell the user today is a rest day.)"
        )
    if not sessions:
        if not extras:
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


MAX_COACH_NOTES_CHARS = 500
FORECAST_WINDOW_DAYS = 5  # OWM free forecast horizon (5 days / 3h steps)
MAX_WEATHER_DAYS = 3


def _notes_section(state: Dict[str, Any]) -> Optional[str]:
    """Free-text personal notes the athlete wrote for the coach (A-COACH-V1b).

    Capped at MAX_COACH_NOTES_CHARS to bound prompt size regardless of what
    the client sends.
    """
    notes = (state.get("preferences") or {}).get("coach_notes")
    if not notes or not str(notes).strip():
        return None
    text = str(notes).strip()[:MAX_COACH_NOTES_CHARS]
    return (
        "## Personal notes from the athlete\n"
        "(Written by the user for you — factor them into every answer.)\n"
        f"{text}"
    )


def _fmt_conditions(w: Dict[str, Any]) -> str:
    bits = [f"{w['temp']}°C", f"humidity {w['humidity']}%"]
    if w.get("dew_point") is not None:
        bits.append(f"dew point {w['dew_point']}°C")
    bits.append(f"wind {w['wind']} km/h ({w.get('wind_label', '?')})")
    if w.get("precip_prob") is not None:
        bits.append(f"precip {w['precip_prob']}%")
    if w.get("condition_text"):
        bits.append(str(w["condition_text"]).lower())
    band_bit = f"friction band: {w.get('condition_band', '?')}"
    if w.get("friction_score") is not None:  # A238
        band_bit += f" ({w['friction_score']}/100)"
    bits.append(band_bit)
    return ", ".join(bits)


def _weather_section(
    state: Dict[str, Any], user_id: Optional[str], today: date,
    lat: Optional[float], lon: Optional[float],
) -> Optional[str]:
    """Live/forecast weather for the athlete's location and planned outdoor
    days (A-COACH-V1b).

    Best-effort by design: any provider failure, missing key, or unresolvable
    spot name silently drops the affected line (or the whole section). The
    chat must never fail or stall because of weather.
    """
    from backend.api.deps import read_week_plan, this_monday
    from backend.api.routers.weather import cached_conditions, geocode_place

    lines: List[str] = []
    today_iso = today.isoformat()
    if lat is not None and lon is not None:
        try:
            w = cached_conditions(lat, lon)
            lines.append(f"- Now at the athlete's location: {_fmt_conditions(w)}")
        except Exception:
            logger.info("coach: current-location weather unavailable")

    plan = read_week_plan(state, user_id, this_monday()) or state.get(
        "current_week_plan"
    )
    horizon = (today + timedelta(days=FORECAST_WINDOW_DAYS - 1)).isoformat()
    outdoor_days = [
        d for d in _plan_days(plan)
        if d.get("outdoor_spot_name")
        and d.get("outdoor_session_status") != "done"
        and today_iso <= d.get("date", "") <= horizon
    ][:MAX_WEATHER_DAYS]
    for d in outdoor_days:
        spot = d["outdoor_spot_name"]
        coords = geocode_place(spot)
        if not coords:
            continue
        try:
            w = cached_conditions(coords[0], coords[1], d["date"])
        except Exception:
            continue
        label = "today" if d["date"] == today_iso else d["date"]
        lines.append(f"- Forecast for {spot} ({label}, midday): {_fmt_conditions(w)}")

    if not lines:
        return None
    return (
        "## Weather (real measurements — OpenWeatherMap)\n"
        + "\n".join(lines)
        + "\n(Use these numbers for conditions/friction advice. If asked "
        "about weather not listed here, say you don't have that data — "
        "never invent conditions.)"
    )


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


_COMPUTE_WEATHER = object()  # sentinel: build_user_context fetches it itself


def build_user_context(
    state: Dict[str, Any], user_id: Optional[str], max_log_lines: Optional[int] = None,
    include_week_detail: bool = True,
    lat: Optional[float] = None, lon: Optional[float] = None,
    weather_text: Any = _COMPUTE_WEATHER,
) -> str:
    """Assemble the delimited user-context block.

    ``weather_text``: pass a precomputed section (or None) to skip fetching —
    build_dynamic_block does this so budget-guard reassembly never refetches.
    """
    today = date.today()
    today_iso = today.isoformat()
    if weather_text is _COMPUTE_WEATHER:
        weather_text = _weather_section(state, user_id, today, lat, lon)
    sections = [
        "=== USER CONTEXT (read-only snapshot, generated "
        f"{today_iso}) ===",
        _profile_section(state),
        _baselines_section(state),
        _plan_section(state),
    ]
    notes = _notes_section(state)
    if notes:
        sections.append(notes)
    if include_week_detail:
        sections.append(_week_section(state, user_id, today_iso))
        sections.append(_today_section(state, user_id, today_iso))
    if weather_text:
        sections.append(weather_text)
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
    state: Dict[str, Any], user_id: Optional[str], query: str,
    lat: Optional[float] = None, lon: Optional[float] = None,
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
    # Fetched once — budget-guard reassembly below must not refetch.
    weather_text = _weather_section(state, user_id, date.today(), lat, lon)

    def _assemble(max_log_lines: Optional[int], include_week_detail: bool) -> str:
        context = build_user_context(
            state, user_id,
            max_log_lines=max_log_lines,
            include_week_detail=include_week_detail,
            weather_text=weather_text,
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


def build_system_blocks(
    user_id: Optional[str], query: str,
    lat: Optional[float] = None, lon: Optional[float] = None,
) -> List[str]:
    """Return [static_block, dynamic_block] for llm_client.chat."""
    from backend.api.deps import load_state

    state = load_state(user_id)
    return [
        build_static_block(),
        build_dynamic_block(state, user_id, query, lat=lat, lon=lon),
    ]


def build_system_prompt(user_id: Optional[str], query: str) -> str:
    """Full system prompt as a single string (brief-spec convenience)."""
    return "\n\n".join(build_system_blocks(user_id, query))
