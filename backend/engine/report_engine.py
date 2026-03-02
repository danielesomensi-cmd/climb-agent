"""Report engine — generates weekly and monthly training reports."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.engine.closed_loop_v1 import STIMULUS_CATEGORIES, _session_categories
from backend.engine.outdoor_log import load_outdoor_sessions

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


def _score_to_label(score: float) -> str:
    for threshold, label in _SCORE_THRESHOLDS:
        if score <= threshold:
            return label
    return "very_hard"


def _load_indoor_sessions(log_dir: str, since: str, until: str) -> List[Dict[str, Any]]:
    """Load indoor session log entries within a date range."""
    sessions: List[Dict[str, Any]] = []
    if not os.path.isdir(log_dir):
        return sessions

    for fn in sorted(os.listdir(log_dir)):
        if not fn.startswith("sessions_") or not fn.endswith(".jsonl"):
            continue
        path = os.path.join(log_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    entry_date = entry.get("date", "")
                    if since <= entry_date <= until:
                        sessions.append(entry)
        except OSError:
            continue

    return sessions


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
    week_start: str,
) -> Dict[str, Any]:
    """Build load section from planned/actual load scores and durations."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    planned_total = 0
    actual_total = 0
    hard_days = 0
    recovery_days = 0

    if week_plan:
        for week in week_plan.get("weeks") or []:
            for day in week.get("days") or []:
                d = day.get("date", "")
                if not (since <= d <= until):
                    continue
                sessions = day.get("sessions") or []
                day_load_planned = sum(s.get("estimated_load_score", 0) for s in sessions)
                day_load_actual = sum(
                    s.get("estimated_load_score", 0)
                    for s in sessions
                    if s.get("status") == "done"
                )
                planned_total += day_load_planned
                actual_total += day_load_actual

                has_hard = any(s.get("tags", {}).get("hard") for s in sessions)
                if has_hard:
                    hard_days += 1
                elif not sessions:
                    recovery_days += 1

    load_ratio = round(actual_total / planned_total, 2) if planned_total else 0.0

    indoor_minutes = sum(s.get("duration_minutes", 0) for s in indoor_sessions)
    outdoor_minutes = sum(s.get("duration_minutes", 0) for s in outdoor_sessions)

    return {
        "planned_total": planned_total,
        "actual_total": actual_total,
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
            "total_routes": 0,
            "sends": 0,
            "send_pct": 0.0,
            "top_grade_sent": None,
            "onsight_pct": 0.0,
            "spots": [],
        }

    total_routes = 0
    sends = 0
    onsights = 0
    spots_set: set = set()
    top_grade: Optional[str] = None

    for sess in outdoor_sessions:
        spot = sess.get("spot_name")
        if spot:
            spots_set.add(spot)
        for route in sess.get("routes") or []:
            total_routes += 1
            attempts = route.get("attempts") or []
            sent = any(a.get("result") == "sent" for a in attempts)
            if sent:
                sends += 1
                grade = route.get("grade")
                if grade:
                    if top_grade is None or grade > top_grade:
                        top_grade = grade
                if route.get("style") == "onsight":
                    onsights += 1

    send_pct = round(sends / total_routes * 100, 1) if total_routes else 0.0
    onsight_pct = round(onsights / total_routes * 100, 1) if total_routes else 0.0

    return {
        "sessions": len(outdoor_sessions),
        "total_routes": total_routes,
        "sends": sends,
        "send_pct": send_pct,
        "top_grade_sent": top_grade,
        "onsight_pct": onsight_pct,
        "spots": sorted(spots_set),
    }


# ---------------------------------------------------------------------------
# Days section
# ---------------------------------------------------------------------------


def _build_days(
    week_plan: Optional[Dict[str, Any]],
    outdoor_sessions: List[Dict[str, Any]],
    week_start: str,
) -> List[Dict[str, Any]]:
    """Build 7-day timeline with session details."""
    start = datetime.strptime(week_start, "%Y-%m-%d").date()

    # Index outdoor sessions by date
    outdoor_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for sess in outdoor_sessions:
        d = sess.get("date", "")
        outdoor_by_date.setdefault(d, []).append(sess)

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

        outdoor_info = None
        if plan_day.get("outdoor_slot"):
            outdoor_info = {
                "spot_name": plan_day.get("outdoor_spot_name"),
                "discipline": plan_day.get("outdoor_discipline"),
                "status": plan_day.get("outdoor_session_status", "planned"),
            }

        other_activity = None
        if plan_day.get("other_activity"):
            other_activity = {
                "name": plan_day.get("other_activity_name"),
                "status": plan_day.get("other_activity_status"),
                "feedback": plan_day.get("other_activity_feedback"),
            }

        is_rest_day = not sessions and not outdoor_info and not other_activity

        result.append({
            "date": d_str,
            "weekday": weekday,
            "sessions": sessions,
            "outdoor": outdoor_info,
            "other_activity": other_activity,
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
        sends = outdoor.get("sends", 0)
        total = outdoor.get("total_routes", 0)
        top = outdoor.get("top_grade_sent")
        parts = [f"{outdoor['sessions']} outdoor session(s)"]
        if total:
            parts.append(f"{sends}/{total} sends")
        if top:
            parts.append(f"top grade {top}")
        highlights.append({
            "type": "positive",
            "key": "outdoor_summary",
            "text": " — ".join(parts) + ".",
        })

    return highlights


# ---------------------------------------------------------------------------
# Main: generate_weekly_report
# ---------------------------------------------------------------------------


def generate_weekly_report(
    user_state: Dict[str, Any],
    log_dir: str,
    week_start: str,
) -> Dict[str, Any]:
    """Generate a comprehensive weekly training report.

    Args:
        user_state: Current user state.
        log_dir: Directory containing session JSONL logs.
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
    indoor = _load_indoor_sessions(log_dir, since, until)
    outdoor_raw = load_outdoor_sessions(log_dir, since_date=since)
    outdoor_filtered = [s for s in outdoor_raw if s.get("date", "") <= until]

    week_plan = _find_week_plan(user_state, week_start)

    # Build each section
    context = _build_context(user_state, week_start)
    adherence = _build_adherence(week_plan, week_start)
    load = _build_load(week_plan, indoor, outdoor_filtered, week_start)
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
    days = _build_days(week_plan, outdoor_filtered, week_start)
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
    log_dir: str,
    month: str,
) -> Dict[str, Any]:
    """Generate a monthly training report.

    Args:
        user_state: Current user state.
        log_dir: Directory containing session JSONL logs.
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

    indoor = _load_indoor_sessions(log_dir, since, until)
    outdoor = load_outdoor_sessions(log_dir, since_date=since)
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
