"""Report engine — generates weekly and monthly training reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.engine import storage
from backend.engine.closed_loop_v1 import STIMULUS_CATEGORIES, _session_categories
from backend.engine.outdoor_log import compute_outdoor_load_score, load_outdoor_sessions

# Difficulty label→score mapping (mirrors adaptive_replan.py)
_LABEL_TO_SCORE: Dict[str, int] = {
    "very_easy": 1,
    "easy": 2,
    "ok": 3,
    "hard": 4,
    "very_hard": 5,
}

_SCORE_THRESHOLDS = [
    (1.5, "very_easy"),
    (2.5, "easy"),
    (3.5, "ok"),
    (4.5, "hard"),
]

_WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# ---------------------------------------------------------------------------
# Grade comparison helper (sport + boulder)
# ---------------------------------------------------------------------------

# Sport grades (French, lowercase)
_SPORT_GRADES = [
    "5a", "5b", "5c",
    "6a", "6a+", "6b", "6b+", "6c", "6c+",
    "7a", "7a+", "7b", "7b+", "7c", "7c+",
    "8a", "8a+", "8b", "8b+", "8c", "8c+",
    "9a", "9a+",
]
# Boulder grades (Fontainebleau, uppercase)
_BOULDER_GRADES = [
    "5A", "5B", "5C",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]
_GRADE_RANK = {g: i for i, g in enumerate(_SPORT_GRADES)}
_GRADE_RANK.update({g: i for i, g in enumerate(_BOULDER_GRADES)})


def _grade_rank(grade: str) -> int:
    """Return a numeric rank for a grade (sport or boulder). Unknown grades return -1."""
    return _GRADE_RANK.get(grade, -1)


def _higher_grade(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Return the harder of two grades, or whichever is not None."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _grade_rank(a) >= _grade_rank(b) else b


def _score_to_label(score: float) -> str:
    for threshold, label in _SCORE_THRESHOLDS:
        if score <= threshold:
            return label
    return "very_hard"


def _load_indoor_sessions(user_id: Optional[str], since: str, until: str) -> List[Dict[str, Any]]:
    """Load indoor session log entries within a date range."""
    return storage.read_session_logs(user_id, since=since, until=until)


# ---------------------------------------------------------------------------
# Context section
# ---------------------------------------------------------------------------


def _build_context(user_state: Dict[str, Any], week_start: str) -> Dict[str, Any]:
    """Build context section from macrocycle, goal, and assessment profile."""
    ctx: Dict[str, Any] = {
        "phase_id": None,
        "phase_week": None,
        "phase_total_weeks": None,
        "macrocycle_week": None,
        "macrocycle_total_weeks": None,
        "goal": None,
        "assessment_profile": None,
    }

    mc = user_state.get("macrocycle")
    if mc and mc.get("phases"):
        mc_start_str = mc.get("start_date", "")
        try:
            mc_start = datetime.strptime(mc_start_str, "%Y-%m-%d").date()
            ws = datetime.strptime(week_start, "%Y-%m-%d").date()
            weeks_offset = (ws - mc_start).days // 7
            cumulative = 0
            for phase in mc["phases"]:
                duration = phase.get("duration_weeks", 1)
                if weeks_offset < cumulative + duration:
                    ctx["phase_id"] = phase.get("phase_id")
                    ctx["phase_week"] = weeks_offset - cumulative + 1
                    ctx["phase_total_weeks"] = duration
                    break
                cumulative += duration
            ctx["macrocycle_week"] = weeks_offset + 1
            ctx["macrocycle_total_weeks"] = mc.get("total_weeks")
        except (ValueError, TypeError):
            pass

    goal = user_state.get("goal")
    if goal and isinstance(goal, dict) and goal:
        ctx["goal"] = goal

    profile = (user_state.get("assessment") or {}).get("profile")
    if profile and isinstance(profile, dict) and profile:
        ctx["assessment_profile"] = profile

    return ctx


# ---------------------------------------------------------------------------
# Adherence section
# ---------------------------------------------------------------------------


def _find_week_plan(user_state: Dict[str, Any], week_start: str) -> Optional[Dict[str, Any]]:
    """Find week plan from week_plans cache or current_week_plan."""
    # Try week_plans cache first
    week_plans = user_state.get("week_plans") or {}
    if week_start in week_plans:
        return week_plans[week_start]

    # Fallback to current_week_plan
    cwp = user_state.get("current_week_plan")
    if cwp:
        # Check if dates match
        for week in (cwp.get("weeks") or []):
            days = week.get("days") or []
            if days and days[0].get("date", "").startswith(week_start[:10]):
                return cwp
    return cwp  # return whatever we have, even if dates don't match


def _build_adherence(week_plan: Optional[Dict[str, Any]], week_start: str) -> Dict[str, Any]:
    """Build adherence section from week plan session statuses."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    planned = 0
    completed = 0
    skipped = 0
    added = 0
    skipped_sessions: List[Dict[str, str]] = []

    if week_plan:
        for week in week_plan.get("weeks") or []:
            for day in week.get("days") or []:
                d = day.get("date", "")
                if not (since <= d <= until):
                    continue
                for session in day.get("sessions") or []:
                    planned += 1
                    status = session.get("status", "planned")
                    if status == "done":
                        completed += 1
                    elif status == "skipped":
                        skipped += 1
                        skipped_sessions.append({
                            "date": d,
                            "session_id": session.get("session_id", ""),
                        })
                    if session.get("tags", {}).get("added"):
                        added += 1

                # Count outdoor planned/completed per day
                if day.get("outdoor_spot_name") or day.get("outdoor_slot"):
                    planned += 1
                    outdoor_status = day.get("outdoor_session_status")
                    if outdoor_status == "done":
                        completed += 1
                    elif outdoor_status == "skipped":
                        skipped += 1
                        skipped_sessions.append({
                            "date": d,
                            "session_id": "outdoor",
                        })

    pct = round(completed / planned * 100, 1) if planned else 0.0

    return {
        "planned": planned,
        "completed": completed,
        "skipped": skipped,
        "added": added,
        "pct": pct,
        "skipped_sessions": skipped_sessions,
    }


# ---------------------------------------------------------------------------
# Load section
# ---------------------------------------------------------------------------


def _build_load(
    week_plan: Optional[Dict[str, Any]],
    indoor_sessions: List[Dict[str, Any]],
    outdoor_sessions: List[Dict[str, Any]],
    free_sessions: List[Dict[str, Any]],
    week_start: str,
) -> Dict[str, Any]:
    """Build load section from planned/actual load scores and durations."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    actual_total = 0
    hard_days = 0
    recovery_days = 0

    # B164: planned_load is the frozen periodization target from weekly_load_summary
    summary = (week_plan or {}).get("weekly_load_summary") or {}
    planned_total = (
        summary.get("planned_load")
        or summary.get("total_load")  # backward compat for pre-B164 plans
        or 0
    )

    if week_plan:
        for week in week_plan.get("weeks") or []:
            for day in week.get("days") or []:
                d = day.get("date", "")
                if not (since <= d <= until):
                    continue
                sessions = day.get("sessions") or []
                day_load_actual = sum(
                    s.get("session_load_score") or s.get("estimated_load_score", 0)
                    for s in sessions
                    if s.get("status") == "done"
                )
                actual_total += day_load_actual
                # B164: include other_activity_load in actual
                actual_total += day.get("other_activity_load") or 0

                has_hard = any(s.get("tags", {}).get("hard") for s in sessions)
                if has_hard:
                    hard_days += 1
                elif not sessions:
                    recovery_days += 1

    # Add outdoor load to actual total
    outdoor_load = sum(compute_outdoor_load_score(s) for s in outdoor_sessions)
    actual_total += outdoor_load

    # Add free session load to actual total (A138)
    free_session_load = sum(
        fs.get("load_score", 0)
        for fs in free_sessions
        if fs.get("finished_at") and since <= fs.get("date", "") <= until
    )
    actual_total += free_session_load

    # Fallback: if no planned_load in summary, sum estimated_load_score (pre-B164)
    if not planned_total:
        if week_plan:
            for week in week_plan.get("weeks") or []:
                for day in week.get("days") or []:
                    d = day.get("date", "")
                    if not (since <= d <= until):
                        continue
                    planned_total += sum(
                        s.get("estimated_load_score", 0)
                        for s in (day.get("sessions") or [])
                    )

    load_ratio = round(actual_total / planned_total, 2) if planned_total else 0.0

    # Duration: prefer session_completion_log (has timer/user-reported data),
    # fall back to indoor JSONL duration_minutes
    indoor_minutes = sum(s.get("duration_minutes", 0) for s in indoor_sessions)
    outdoor_minutes = sum(s.get("duration_minutes", 0) for s in outdoor_sessions)

    return {
        "planned_total": planned_total,
        "actual_total": actual_total,
        "outdoor_load": outdoor_load,
        "free_session_load": free_session_load,
        "load_ratio": load_ratio,
        "hard_days": hard_days,
        "recovery_days": recovery_days,
        "indoor_minutes": indoor_minutes,
        "outdoor_minutes": outdoor_minutes,
    }


# ---------------------------------------------------------------------------
# Difficulty section
# ---------------------------------------------------------------------------


def _build_difficulty(
    feedback_log: List[Dict[str, Any]],
    week_start: str,
) -> Dict[str, Any]:
    """Build difficulty section from feedback_log entries in the week."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    distribution: Dict[str, int] = {}
    scores: List[float] = []
    hardest_session: Optional[Dict[str, str]] = None
    hardest_score = 0.0
    easiest_session: Optional[Dict[str, str]] = None
    easiest_score = 6.0

    for entry in feedback_log:
        d = entry.get("date", "")
        if not (since <= d <= until):
            continue
        label = entry.get("difficulty", "ok")
        distribution[label] = distribution.get(label, 0) + 1
        score = _LABEL_TO_SCORE.get(label, 3)
        scores.append(score)
        info = {"date": d, "session_id": entry.get("session_id", ""), "difficulty": label}
        if score >= hardest_score:
            hardest_score = score
            hardest_session = info
        if score <= easiest_score:
            easiest_score = score
            easiest_session = info

    avg_score = sum(scores) / len(scores) if scores else 3.0
    avg_label = _score_to_label(avg_score)

    return {
        "distribution": distribution,
        "avg_label": avg_label,
        "hardest_session": hardest_session,
        "easiest_session": easiest_session,
    }


# ---------------------------------------------------------------------------
# Stimulus balance section
# ---------------------------------------------------------------------------


def _build_stimulus_balance(
    week_plan: Optional[Dict[str, Any]],
    stimulus_recency: Dict[str, Any],
    week_start: str,
) -> Dict[str, Dict[str, Any]]:
    """Build stimulus balance section: sessions per category this week + days since last."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    counts: Dict[str, int] = {cat: 0 for cat in STIMULUS_CATEGORIES}

    if week_plan:
        for week in week_plan.get("weeks") or []:
            for day in week.get("days") or []:
                d = day.get("date", "")
                if not (since <= d <= until):
                    continue
                for session in day.get("sessions") or []:
                    if session.get("status") == "done":
                        for cat in _session_categories(session):
                            counts[cat] = counts.get(cat, 0) + 1

    result: Dict[str, Dict[str, Any]] = {}
    for cat in STIMULUS_CATEGORIES:
        rec = stimulus_recency.get(cat) or {}
        last_done = rec.get("last_done_date")
        if last_done:
            try:
                last_dt = datetime.strptime(last_done, "%Y-%m-%d").date()
                days_since = (start - last_dt).days
            except (ValueError, TypeError):
                days_since = None
        else:
            days_since = None
        result[cat] = {
            "sessions_this_week": counts.get(cat, 0),
            "days_since_last": days_since,
        }

    return result


# ---------------------------------------------------------------------------
# Progression section
# ---------------------------------------------------------------------------


def _build_progression(
    working_loads: Dict[str, Any],
    week_start: str,
) -> List[Dict[str, Any]]:
    """Build progression section from working_loads entries updated this week."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    entries = working_loads.get("entries") or []
    result: List[Dict[str, Any]] = []

    for entry in entries:
        updated = entry.get("updated_at", "")
        if not (since <= updated <= until):
            continue

        exercise_id = entry.get("exercise_id", "")

        # Determine load values — either kg-based or grade-based
        previous_load = entry.get("last_external_load_kg") or entry.get("last_total_load_kg")
        current_load = entry.get("next_external_load_kg") or entry.get("next_total_load_kg")

        if previous_load is not None and current_load is not None:
            try:
                prev = float(previous_load)
                curr = float(current_load)
                change_pct = round((curr - prev) / prev * 100, 1) if prev else 0.0
                direction = "up" if curr > prev else ("down" if curr < prev else "same")
                result.append({
                    "exercise_id": exercise_id,
                    "previous_load": prev,
                    "current_load": curr,
                    "change_pct": change_pct,
                    "direction": direction,
                })
            except (ValueError, TypeError):
                pass
        else:
            # Grade-based progression
            prev_grade = entry.get("last_used_grade")
            next_grade = entry.get("next_target_grade")
            if prev_grade and next_grade:
                result.append({
                    "exercise_id": exercise_id,
                    "previous_load": prev_grade,
                    "current_load": next_grade,
                    "change_pct": None,
                    "direction": "grade_change",
                })

    return result


# ---------------------------------------------------------------------------
# Outdoor section
# ---------------------------------------------------------------------------


def _build_outdoor(outdoor_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build outdoor section from outdoor session log entries."""
    if not outdoor_sessions:
        return {
            "sessions": 0,
            "routes_attempted": 0,
            "routes_sent": 0,
            "send_pct": 0.0,
            "top_grade_sent": None,
            "top_grade_attempted": None,
            "onsight_pct": 0.0,
            "spots": [],
            # Backward compat aliases
            "total_routes": 0,
            "sends": 0,
        }

    routes_attempted = 0
    routes_sent = 0
    onsights = 0
    spots_set: set = set()
    top_grade_sent: Optional[str] = None
    top_grade_attempted: Optional[str] = None

    for sess in outdoor_sessions:
        spot = sess.get("spot_name")
        if spot:
            spots_set.add(spot)
        for route in sess.get("routes") or []:
            routes_attempted += 1
            grade = route.get("grade")
            attempts = route.get("attempts") or []

            # Track highest grade attempted (any route with attempts)
            if grade and attempts:
                top_grade_attempted = _higher_grade(top_grade_attempted, grade)

            sent = any(a.get("result") == "sent" for a in attempts)
            if sent:
                routes_sent += 1
                if grade:
                    top_grade_sent = _higher_grade(top_grade_sent, grade)
                if route.get("style") == "onsight":
                    onsights += 1

    send_pct = round(routes_sent / routes_attempted * 100, 1) if routes_attempted else 0.0
    onsight_pct = round(onsights / routes_attempted * 100, 1) if routes_attempted else 0.0

    return {
        "sessions": len(outdoor_sessions),
        "routes_attempted": routes_attempted,
        "routes_sent": routes_sent,
        "send_pct": send_pct,
        "top_grade_sent": top_grade_sent,
        "top_grade_attempted": top_grade_attempted,
        "onsight_pct": onsight_pct,
        "spots": sorted(spots_set),
        # Backward compat aliases
        "total_routes": routes_attempted,
        "sends": routes_sent,
    }


# ---------------------------------------------------------------------------
# Days section
# ---------------------------------------------------------------------------


def _build_days(
    week_plan: Optional[Dict[str, Any]],
    outdoor_sessions: List[Dict[str, Any]],
    free_sessions: List[Dict[str, Any]],
    week_start: str,
) -> List[Dict[str, Any]]:
    """Build 7-day timeline with session details."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()

    # Index outdoor sessions by date
    outdoor_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for sess in outdoor_sessions:
        d = sess.get("date", "")
        outdoor_by_date.setdefault(d, []).append(sess)

    # Index free sessions by date (A138)
    free_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for fs in free_sessions:
        if fs.get("finished_at"):  # only finished sessions
            d = fs.get("date", "")
            free_by_date.setdefault(d, []).append(fs)

    # Index plan days by date
    plan_days: Dict[str, Dict[str, Any]] = {}
    if week_plan:
        for week in week_plan.get("weeks") or []:
            for day in week.get("days") or []:
                plan_days[day.get("date", "")] = day

    result: List[Dict[str, Any]] = []
    for i in range(7):
        d = start + timedelta(days=i)
        d_str = d.isoformat()
        weekday = _WEEKDAY_NAMES[d.weekday()]

        plan_day = plan_days.get(d_str, {})
        sessions_raw = plan_day.get("sessions") or []
        sessions = []
        for s in sessions_raw:
            sessions.append({
                "session_id": s.get("session_id", ""),
                "status": s.get("status", "planned"),
                "slot": s.get("slot", ""),
                "estimated_load_score": s.get("estimated_load_score"),
                "intensity": s.get("intensity"),
                "feedback_summary": s.get("feedback_summary"),
            })

        # Outdoor: prefer planned info, but merge actual outdoor_log data
        outdoor_info = None
        if plan_day.get("outdoor_slot"):
            outdoor_info = {
                "spot_name": plan_day.get("outdoor_spot_name"),
                "discipline": plan_day.get("outdoor_discipline"),
                "status": plan_day.get("outdoor_session_status", "planned"),
            }
        # Merge actual outdoor sessions from log (handles spontaneous outdoor)
        actual_outdoor = outdoor_by_date.get(d_str, [])
        if actual_outdoor and not outdoor_info:
            first = actual_outdoor[0]
            route_count = sum(len(s.get("routes") or []) for s in actual_outdoor)
            outdoor_info = {
                "spot_name": first.get("spot_name"),
                "discipline": first.get("discipline"),
                "status": "done",
                "route_count": route_count,
            }
        elif actual_outdoor and outdoor_info:
            route_count = sum(len(s.get("routes") or []) for s in actual_outdoor)
            outdoor_info["route_count"] = route_count

        other_activity = None
        if plan_day.get("other_activity"):
            other_activity = {
                "name": plan_day.get("other_activity_name"),
                "status": plan_day.get("other_activity_status"),
                "feedback": plan_day.get("other_activity_feedback"),
                "load": plan_day.get("other_activity_load"),
            }

        # Free sessions (A138)
        day_free = []
        for fs in free_by_date.get(d_str, []):
            summary = fs.get("summary") or {}
            surface = fs.get("surface", "")
            surface_label = {
                "gym_boulder": "Gym Boulder", "board_kilter": "Kilter",
                "board_moonboard": "Moon", "board_other": "Board",
                "gym_routes": "Lead", "circuit_core": "Core Circuit",
            }.get(surface, surface)
            day_free.append({
                "id": fs.get("id"),
                "surface": surface_label,
                "preset_name": fs.get("preset_id", "").replace("free_", "").replace("lead_", "").replace("_", " ").title() if fs.get("preset_id") else "Free",
                "context": fs.get("context", "standalone"),
                "total_climbs": summary.get("total_climbs", 0),
                "max_grade_sent": summary.get("max_grade_sent"),
                "send_rate": summary.get("send_rate", 0),
                "duration_minutes": fs.get("duration_minutes"),
                "load_score": fs.get("load_score", 0),
                "climb_type": "routes" if surface == "gym_routes" else "boulders",
            })

        is_rest_day = not sessions and not outdoor_info and not other_activity and not day_free

        result.append({
            "date": d_str,
            "weekday": weekday,
            "sessions": sessions,
            "outdoor": outdoor_info,
            "other_activity": other_activity,
            "free_sessions": day_free,
            "is_rest_day": is_rest_day,
        })

    return result


# ---------------------------------------------------------------------------
# Highlights section
# ---------------------------------------------------------------------------


def _build_highlights(
    adherence: Dict[str, Any],
    load: Dict[str, Any],
    difficulty: Dict[str, Any],
    stimulus_balance: Dict[str, Dict[str, Any]],
    progression: List[Dict[str, Any]],
    outdoor: Dict[str, Any],
    context: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build rule-based insight highlights."""
    highlights: List[Dict[str, str]] = []

    # 1. Adherence
    pct = adherence.get("pct", 0)
    if pct >= 90:
        highlights.append({
            "type": "positive",
            "key": "adherence_high",
            "text": f"Excellent adherence this week ({pct}%)!",
        })
    elif pct >= 70:
        highlights.append({
            "type": "info",
            "key": "adherence_good",
            "text": f"Good training consistency ({pct}%).",
        })
    elif adherence.get("planned", 0) > 0 and pct < 50:
        highlights.append({
            "type": "warning",
            "key": "adherence_low",
            "text": f"Low adherence ({pct}%). Consider adjusting your schedule.",
        })

    # 2. Load ratio
    ratio = load.get("load_ratio", 0)
    if ratio > 1.2:
        highlights.append({
            "type": "warning",
            "key": "load_high",
            "text": "Training load exceeded plan by 20%+. Watch for fatigue.",
        })
    elif 0.8 <= ratio <= 1.2 and load.get("actual_total", 0) > 0:
        highlights.append({
            "type": "positive",
            "key": "load_balanced",
            "text": "Training load is well-balanced with the plan.",
        })

    # 3. Progression detected
    up_count = sum(1 for p in progression if p.get("direction") == "up")
    if up_count > 0:
        highlights.append({
            "type": "progress",
            "key": "progression",
            "text": f"Load increased on {up_count} exercise(s) — keep it up!",
        })

    # 4. Stimulus gap
    for cat, data in stimulus_balance.items():
        days_since = data.get("days_since_last")
        if days_since is not None and days_since > 10 and data.get("sessions_this_week", 0) == 0:
            label = cat.replace("_", " ").title()
            highlights.append({
                "type": "warning",
                "key": f"stimulus_gap_{cat}",
                "text": f"No {label} training in {days_since} days.",
            })

    # 5. Difficulty balance
    avg = difficulty.get("avg_label", "ok")
    if avg in ("very_hard", "hard"):
        highlights.append({
            "type": "warning",
            "key": "difficulty_high",
            "text": f"Average difficulty was '{avg}' — consider more recovery.",
        })
    elif avg in ("very_easy", "easy") and adherence.get("completed", 0) >= 3:
        highlights.append({
            "type": "info",
            "key": "difficulty_low",
            "text": f"Sessions felt '{avg}' — you may be ready for more challenge.",
        })

    # 6. Phase context
    phase = context.get("phase_id")
    phase_week = context.get("phase_week")
    phase_total = context.get("phase_total_weeks")
    if phase and phase_week and phase_total:
        if phase_week == phase_total:
            highlights.append({
                "type": "info",
                "key": "phase_last_week",
                "text": f"Last week of {phase.replace('_', ' ')} phase — test week may follow.",
            })

    # 7. Outdoor summary
    if outdoor.get("sessions", 0) > 0:
        sent = outdoor.get("routes_sent", 0)
        attempted = outdoor.get("routes_attempted", 0)
        top_sent = outdoor.get("top_grade_sent")
        top_attempted = outdoor.get("top_grade_attempted")
        parts = [f"{outdoor['sessions']} outdoor session(s)"]
        if attempted:
            parts.append(f"{sent}/{attempted} sends")
        if top_attempted and top_attempted != top_sent:
            parts.append(f"top attempt {top_attempted}")
        if top_sent:
            parts.append(f"top send {top_sent}")
        highlights.append({
            "type": "positive",
            "key": "outdoor_summary",
            "text": " — ".join(parts) + ".",
        })

    return highlights


# ---------------------------------------------------------------------------
# Training time section (B126)
# ---------------------------------------------------------------------------


def _build_training_time(
    week_plan: Optional[Dict[str, Any]],
    completion_log: List[Dict[str, Any]],
    outdoor_sessions: List[Dict[str, Any]],
    free_sessions: List[Dict[str, Any]],
    week_start: str,
) -> Dict[str, Any]:
    """Aggregate training duration from all sources."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    total_seconds = 0
    estimated_seconds = 0
    sources: Dict[str, int] = {}  # source_type → seconds

    # Slot-based duration estimates (minutes)
    _SLOT_ESTIMATE: Dict[str, int] = {"lunch": 35, "morning": 60, "evening": 90}

    # Index completion log entries by (date, session_id) for quick lookup
    cl_by_key: Dict[tuple, Dict[str, Any]] = {}
    for entry in completion_log:
        d = entry.get("date", "")
        if since <= d <= until:
            key = (d, entry.get("session_id", ""))
            cl_by_key[key] = entry

    # 1. Engine sessions: real duration from completion_log, else template estimate
    # B217: dropped duration_source lookup — field was never written server-side
    # (Potemkin: sent by frontend, accepted by backend, never persisted). The
    # default "timer" was the only value this branch ever produced.
    sessions_with_duration: set = set()
    for key, entry in cl_by_key.items():
        dur = entry.get("session_duration_seconds")
        if dur is not None:
            dur = int(dur)
            total_seconds += dur
            sources["timer"] = sources.get("timer", 0) + dur
            sessions_with_duration.add(key)

    # 1b. Fallback: "done" sessions without real duration → template estimate
    if week_plan:
        for week in week_plan.get("weeks") or []:
            for day in week.get("days") or []:
                d = day.get("date", "")
                if not (since <= d <= until):
                    continue
                for session in day.get("sessions") or []:
                    if session.get("status") != "done":
                        continue
                    key = (d, session.get("session_id", ""))
                    if key in sessions_with_duration:
                        continue  # already counted from real data
                    # Check if completion_log has entry without duration
                    if key in cl_by_key and cl_by_key[key].get("session_duration_seconds") is not None:
                        continue
                    # Template estimate based on slot
                    slot = session.get("slot", "evening")
                    est_min = _SLOT_ESTIMATE.get(slot, 60)
                    est = est_min * 60
                    total_seconds += est
                    estimated_seconds += est
                    sources["estimated"] = sources.get("estimated", 0) + est

    # 2. Other activities: use stored duration or estimate 60 min
    if week_plan:
        for week in week_plan.get("weeks") or []:
            for day in week.get("days") or []:
                d = day.get("date", "")
                if not (since <= d <= until):
                    continue
                if day.get("other_activity") and day.get("other_activity_status") == "completed":
                    dur_min = day.get("other_activity_duration_minutes")
                    if dur_min is not None:
                        dur = int(dur_min) * 60
                        total_seconds += dur
                        sources["user_reported"] = sources.get("user_reported", 0) + dur
                    else:
                        est = 60 * 60
                        total_seconds += est
                        estimated_seconds += est
                        sources["estimated"] = sources.get("estimated", 0) + est

    # 3. Outdoor sessions
    for sess in outdoor_sessions:
        d = sess.get("date", "")
        if not (since <= d <= until):
            continue
        dur_min = sess.get("duration_minutes", 0)
        if dur_min:
            dur = int(dur_min) * 60
            total_seconds += dur
            sources["outdoor_log"] = sources.get("outdoor_log", 0) + dur

    # 4. Free climbing sessions (A138)
    for fs in free_sessions:
        d = fs.get("date", "")
        if not (since <= d <= until):
            continue
        if not fs.get("finished_at"):
            continue
        dur_min = fs.get("duration_minutes", 0)
        if dur_min:
            dur = int(dur_min) * 60
            total_seconds += dur
            sources["free_session"] = sources.get("free_session", 0) + dur

    total_minutes = total_seconds // 60
    estimated_minutes = estimated_seconds // 60
    has_estimates = estimated_seconds > 0

    return {
        "total_minutes": total_minutes,
        "total_seconds": total_seconds,
        "estimated_minutes": estimated_minutes,
        "has_estimates": has_estimates,
        "formatted": f"{total_minutes // 60}h {total_minutes % 60:02d}m",
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# Active days section (B126)
# ---------------------------------------------------------------------------


def _build_active_days(
    days: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Count days with at least one completed activity."""
    active = []
    for day in days:
        has_activity = False
        for s in day.get("sessions", []):
            if s.get("status") == "done":
                has_activity = True
                break
        if not has_activity and day.get("outdoor"):
            outdoor = day["outdoor"]
            if outdoor.get("status") == "done" or outdoor.get("route_count"):
                has_activity = True
        if not has_activity and day.get("other_activity"):
            oa = day["other_activity"]
            if oa.get("status") in ("completed", "done"):
                has_activity = True
        # Free sessions with at least 1 climb or circuit session (A138/A140)
        if not has_activity:
            for fs in day.get("free_sessions", []):
                if fs.get("total_climbs", 0) > 0 or fs.get("load_score", 0) > 0:
                    has_activity = True
                    break
        active.append(has_activity)

    return {
        "count": sum(active),
        "total": 7,
        "dots": active,  # [True, False, True, ...] for 7-dot visual
    }


# ---------------------------------------------------------------------------
# Main: generate_weekly_report
# ---------------------------------------------------------------------------


def generate_weekly_report(
    user_state: Dict[str, Any],
    user_id: Optional[str],
    week_start: str,
) -> Dict[str, Any]:
    """Generate a comprehensive weekly training report.

    Args:
        user_state: Current user state.
        user_id: User identifier (None for legacy/test).
        week_start: YYYY-MM-DD Monday of the week.

    Returns:
        Report dict with 9 sections: context, adherence, load, difficulty,
        stimulus_balance, progression, outdoor, days, highlights.
    """
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    # Load raw data
    indoor = _load_indoor_sessions(user_id, since, until)
    outdoor_raw = load_outdoor_sessions(user_id, since_date=since)
    outdoor_filtered = [s for s in outdoor_raw if s.get("date", "") <= until]
    completion_log = user_state.get("session_completion_log") or []
    free_sessions = [
        fs for fs in (user_state.get("free_sessions") or [])
        if since <= fs.get("date", "") <= until
    ]

    week_plan = _find_week_plan(user_state, week_start)

    # Build each section
    context = _build_context(user_state, week_start)
    adherence = _build_adherence(week_plan, week_start)
    load = _build_load(week_plan, indoor, outdoor_filtered, free_sessions, week_start)
    difficulty = _build_difficulty(
        user_state.get("feedback_log") or [], week_start
    )
    stimulus_balance = _build_stimulus_balance(
        week_plan,
        user_state.get("stimulus_recency") or {},
        week_start,
    )
    progression = _build_progression(
        user_state.get("working_loads") or {}, week_start
    )
    outdoor = _build_outdoor(outdoor_filtered)
    days = _build_days(week_plan, outdoor_filtered, free_sessions, week_start)
    training_time = _build_training_time(
        week_plan, completion_log, outdoor_filtered, free_sessions, week_start,
    )
    active_days = _build_active_days(days)
    highlights = _build_highlights(
        adherence, load, difficulty, stimulus_balance,
        progression, outdoor, context,
    )

    return {
        "report_type": "weekly",
        "week_start": week_start,
        "week_end": until,
        "context": context,
        "adherence": adherence,
        "load": load,
        "training_time": training_time,
        "active_days": active_days,
        "difficulty": difficulty,
        "stimulus_balance": stimulus_balance,
        "progression": progression,
        "outdoor": outdoor,
        "days": days,
        "highlights": highlights,
    }


# ---------------------------------------------------------------------------
# Monthly report (unchanged)
# ---------------------------------------------------------------------------


def generate_monthly_report(
    user_state: Dict[str, Any],
    user_id: Optional[str],
    month: str,
) -> Dict[str, Any]:
    """Generate a monthly training report.

    Args:
        user_state: Current user state.
        user_id: User identifier (None for legacy/test).
        month: YYYY-MM string.

    Returns:
        Report dict with aggregated stats and suggestions.
    """
    year, mon = month.split("-")
    start = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    # End of month
    if int(mon) == 12:
        end = datetime(int(year) + 1, 1, 1).date() - timedelta(days=1)
    else:
        end = datetime(int(year), int(mon) + 1, 1).date() - timedelta(days=1)

    since = start.isoformat()
    until = end.isoformat()

    indoor = _load_indoor_sessions(user_id, since, until)
    outdoor = load_outdoor_sessions(user_id, since_date=since)
    outdoor = [s for s in outdoor if s.get("date", "") <= until]

    # Weekly aggregation
    total_weeks = (end - start).days // 7 + 1
    weekly_counts: List[int] = [0] * total_weeks
    for s in indoor:
        entry_date = datetime.strptime(s.get("date", since), "%Y-%m-%d").date()
        week_idx = min((entry_date - start).days // 7, total_weeks - 1)
        weekly_counts[week_idx] += 1

    avg_sessions_per_week = round(sum(weekly_counts) / max(total_weeks, 1), 1)

    # Feedback summary
    feedback_labels: Dict[str, int] = {}
    for s in indoor:
        label = s.get("overall_feeling") or s.get("feedback_label", "ok")
        feedback_labels[label] = feedback_labels.get(label, 0) + 1

    # Total volume
    indoor_minutes = sum(s.get("duration_minutes", 0) for s in indoor)
    outdoor_minutes = sum(s.get("duration_minutes", 0) for s in outdoor)

    # Suggestions (max 3 rules)
    suggestions: List[str] = []
    overall_adherence = avg_sessions_per_week
    target = (user_state.get("planning_prefs") or {}).get("target_training_days_per_week", 4)

    if target > 0 and overall_adherence / target < 0.7:
        suggestions.append(
            "Training adherence is below 70%. Consider adjusting your availability or reducing target days."
        )

    if not outdoor:
        suggestions.append(
            "No outdoor sessions this month. Consider scheduling an outdoor day to apply gym gains."
        )

    # Check for technique sessions
    technique_count = sum(
        1 for s in indoor
        if "technique" in s.get("session_id", "")
    )
    if technique_count == 0 and len(indoor) >= 4:
        suggestions.append(
            "No technique-focused sessions detected. Adding movement quality work can accelerate progress."
        )

    return {
        "report_type": "monthly",
        "month": month,
        "period_start": since,
        "period_end": until,
        "total_indoor_sessions": len(indoor),
        "total_outdoor_sessions": len(outdoor),
        "avg_sessions_per_week": avg_sessions_per_week,
        "weekly_session_counts": weekly_counts,
        "total_indoor_minutes": indoor_minutes,
        "total_outdoor_minutes": outdoor_minutes,
        "feedback_summary": feedback_labels,
        "suggestions": suggestions[:3],
    }
