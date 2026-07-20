"""Milestones engine — one-time achievement unlocks (A239 / A-GAMIFY-02).

Design contract (docs/design_gamification.md §P3):
- Unlocks are APPEND-ONLY and never revoked — deleting a climb or undoing a
  session does not re-lock anything.
- Evaluation is lazy and read-driven: ``evaluate_milestones`` derives
  everything from data that already exists (hot week_plans, outdoor logs,
  free sessions, macrocycle/history) — no hooks in any write path, no
  high-risk module touched.
- Deterministic given the same state/logs and evaluation date.

State shape (additive key ``state["milestones"]``):
    {
      "unlocked": [{"id", "unlocked_at", "seen", "context"?}],
      "counters": {"exercise_ids": [...], "drill_ids": [...]},
      "counted_weeks": ["YYYY-MM-DD", ...]   # fully-past weeks folded into counters
    }

Counters only ever absorb FULLY-PAST weeks (immutable by invariant), so an
undo in the current week can never leave phantom counts. Historical weeks
archived before this feature shipped are not scanned — cumulative counts
start at launch (documented deviation; unlock timestamps are discovery
dates for retroactive facts like grade PBs).
"""

from __future__ import annotations

import functools
import json
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.engine.assessment_v1 import GRADE_ORDER
from backend.engine.free_session import FONT_GRADES
from backend.engine.outdoor_log import load_outdoor_sessions

_MILESTONES_CATALOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "milestones", "v1", "milestones.json"
)

_GRADE_INDEX = {g: i for i, g in enumerate(GRADE_ORDER)}
_FONT_INDEX = {g: i for i, g in enumerate(FONT_GRADES)}


@functools.lru_cache(maxsize=1)
def load_milestones_catalog() -> List[Dict[str, Any]]:
    path = os.path.normpath(_MILESTONES_CATALOG_PATH)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("milestones", [])


@functools.lru_cache(maxsize=1)
def _exercise_families() -> Dict[str, Set[str]]:
    """Classify catalog exercises into milestone families (strict equipment)."""
    import glob

    fams: Dict[str, Set[str]] = {"hangboard": set(), "campus": set(), "tech": set()}
    pattern = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "catalog", "exercises", "v1", "*.json")
    )
    for p in glob.glob(pattern):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        exercises = data.get("exercises", data if isinstance(data, list) else [])
        for ex in exercises:
            eid = ex.get("id") or ex.get("exercise_id") or ""
            if not eid:
                continue
            required = set(ex.get("equipment_required") or [])
            if "hangboard" in required:
                fams["hangboard"].add(eid)
            if "campus_board" in required:
                fams["campus"].add(eid)
            if eid.startswith("tech_"):
                fams["tech"].add(eid)
    return fams


# ---------------------------------------------------------------------------
# Week-plan scanning
# ---------------------------------------------------------------------------

def _done_exercise_ids(session: Dict[str, Any]) -> Set[str]:
    """Exercise ids touched by a done session (actuals ∪ resolved blocks)."""
    ids: Set[str] = set()
    for a in session.get("actual_exercises") or []:
        if a.get("exercise_id"):
            ids.add(a["exercise_id"])
    resolved = session.get("resolved") or {}
    for block in resolved.get("blocks") or []:
        for ex in block.get("exercises") or []:
            if ex.get("exercise_id"):
                ids.add(ex["exercise_id"])
    return ids


def _scan_week(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Facts about one week plan needed by milestone conditions."""
    facts = {
        "exercise_ids": set(),
        "any_done": False,
        "any_guided": False,
        "any_body_part": False,
        "any_test": False,
        "sessions_total": 0,
        "sessions_done": 0,
        "sessions_skipped": 0,
        "empty_days": 0,
    }
    for wk in plan.get("weeks") or []:
        for day in wk.get("days") or []:
            sessions = day.get("sessions") or []
            if not sessions:
                facts["empty_days"] += 1
            for s in sessions:
                facts["sessions_total"] += 1
                status = s.get("status")
                if status == "skipped":
                    facts["sessions_skipped"] += 1
                if status != "done":
                    continue
                facts["sessions_done"] += 1
                facts["any_done"] = True
                if s.get("session_duration_seconds"):
                    facts["any_guided"] = True
                if s.get("build_kind") == "body_parts":
                    facts["any_body_part"] = True
                sid = s.get("session_id") or ""
                if s.get("tags", {}).get("test") or "test" in sid:
                    facts["any_test"] = True
                facts["exercise_ids"] |= _done_exercise_ids(s)
    return facts


def _phase_for_week(macrocycle: Dict[str, Any], week_num: int) -> Optional[str]:
    """phase_id containing 1-based macrocycle week (None if out of range)."""
    cursor = 1
    for phase in macrocycle.get("phases") or []:
        dur = phase.get("duration_weeks") or 0
        if week_num < cursor + dur:
            return phase.get("phase_id")
        cursor += dur
    return None


def _macro_week_of(macrocycle: Dict[str, Any], monday_iso: str) -> Optional[int]:
    try:
        start = date.fromisoformat(macrocycle.get("start_date", ""))
        monday = date.fromisoformat(monday_iso)
    except ValueError:
        return None
    offset_days = (macrocycle.get("pause") or {}).get("offset_days") or 0
    return (monday - start - timedelta(days=offset_days)).days // 7 + 1


# ---------------------------------------------------------------------------
# Outdoor scanning
# ---------------------------------------------------------------------------

def _grade_rank(grade: str, discipline: str) -> Optional[int]:
    g = (grade or "").strip()
    if discipline == "boulder":
        return _FONT_INDEX.get(g.upper())
    return _GRADE_INDEX.get(g.lower())


def _route_sent(route: Dict[str, Any]) -> bool:
    return any(a.get("result") in ("sent", "topped_out") for a in route.get("attempts") or [])


def _scan_outdoor(user_id: Optional[str]) -> Dict[str, Any]:
    """Facts from the full outdoor log (single storage read, dedup by date)."""
    sessions = load_outdoor_sessions(user_id)
    facts: Dict[str, Any] = {
        "any_session": bool(sessions),
        "spots": set(),
        "any_onsight": False,
        # discipline -> (best sent rank, grade); onsight tracked separately
        "pb_sent": {},
        "pb_onsight": {},
    }
    for s in sessions:
        spot = s.get("spot_id") or (s.get("spot_name") or "").strip().lower()
        if spot:
            facts["spots"].add(spot)
        for route in s.get("routes") or []:
            if not _route_sent(route):
                continue
            discipline = route.get("discipline") or s.get("discipline") or "lead"
            if discipline == "both":
                discipline = "lead"
            rank = _grade_rank(route.get("grade", ""), discipline)
            if rank is None:
                continue
            best = facts["pb_sent"].get(discipline)
            if best is None or rank > best[0]:
                facts["pb_sent"][discipline] = (rank, route.get("grade"))
            if route.get("style") == "onsight":
                facts["any_onsight"] = True
                best_os = facts["pb_onsight"].get(discipline)
                if best_os is None or rank > best_os[0]:
                    facts["pb_onsight"][discipline] = (rank, route.get("grade"))
    return facts


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def evaluate_milestones(
    state: Dict[str, Any],
    user_id: Optional[str],
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Evaluate all milestone conditions; mutate state['milestones'] in place.

    Returns the list of NEWLY unlocked entries (empty most of the time).
    Caller persists state if the return is non-empty.
    """
    today = today or date.today()
    ms = state.setdefault("milestones", {})
    unlocked: List[Dict[str, Any]] = ms.setdefault("unlocked", [])
    counters: Dict[str, List[str]] = ms.setdefault("counters", {})
    counted_weeks: List[str] = ms.setdefault("counted_weeks", [])
    unlocked_ids = {u["id"] for u in unlocked}
    newly: List[Dict[str, Any]] = []

    def unlock(mid: str, context: Optional[Dict[str, Any]] = None) -> None:
        if mid in unlocked_ids:
            return
        entry: Dict[str, Any] = {
            "id": mid,
            "unlocked_at": today.isoformat(),
            "seen": False,
        }
        if context:
            entry["context"] = context
        unlocked.append(entry)
        unlocked_ids.add(mid)
        newly.append(entry)

    # --- Week-plan facts (hot store only). Persisted counters absorb ONLY
    # fully-past weeks (immutable by invariant) so they survive A221
    # archiving; the in-progress week is counted transiently each run — an
    # undo there can never leave phantom persisted counts.
    current_monday = _monday_of(today).isoformat()
    persisted_ids: Set[str] = set(counters.get("exercise_ids") or [])
    live_ids: Set[str] = set()
    flags = {
        "any_done": False, "any_guided": False, "any_body_part": False,
        "any_test": False,
    }
    perfect_week_found = False
    deload_completed = False
    macrocycle = state.get("macrocycle") or {}

    for monday_iso, plan in sorted((state.get("week_plans") or {}).items()):
        if not isinstance(plan, dict) or monday_iso > current_monday:
            continue
        facts = _scan_week(plan)
        for key in flags:
            flags[key] = flags[key] or facts[key]
        fully_past = monday_iso < current_monday
        if fully_past:
            persisted_ids |= facts["exercise_ids"]
            if monday_iso not in counted_weeks:
                counted_weeks.append(monday_iso)
            if (
                facts["sessions_total"] > 0
                and facts["sessions_done"] == facts["sessions_total"]
                and facts["empty_days"] > 0
            ):
                perfect_week_found = True
                if macrocycle:
                    week_num = _macro_week_of(macrocycle, monday_iso)
                    if week_num and _phase_for_week(macrocycle, week_num) == "deload":
                        deload_completed = True
        else:
            live_ids |= facts["exercise_ids"]

    counters["exercise_ids"] = sorted(persisted_ids)
    exercise_ids = persisted_ids | live_ids
    fams = _exercise_families()
    drills_tried = exercise_ids & fams["tech"]

    if flags["any_done"]:
        unlock("first_session_done")
    if flags["any_guided"]:
        unlock("first_guided_session")
    if flags["any_body_part"]:
        unlock("first_body_part_session")
    if flags["any_test"]:
        unlock("first_test_done")
    if exercise_ids & fams["hangboard"]:
        unlock("first_hangboard_session")
    if exercise_ids & fams["campus"]:
        unlock("first_campus_session")
    if drills_tried:
        unlock("first_technique_drill")
    if len(drills_tried) >= 10:
        unlock("drill_collector_10")
    if len(exercise_ids) >= 25:
        unlock("explorer_25")
    if len(exercise_ids) >= 50:
        unlock("explorer_50")
    if perfect_week_found:
        unlock("perfect_week")
    if deload_completed:
        unlock("first_deload_completed")

    # --- Free / custom sessions (state-resident)
    if any(fs.get("finished_at") for fs in state.get("free_sessions") or []):
        unlock("first_free_session")
    if state.get("custom_sessions"):
        unlock("first_custom_session")

    # --- Outdoor (single log read)
    outdoor = _scan_outdoor(user_id)
    if outdoor["any_session"]:
        unlock("first_outdoor_session")
    if outdoor["any_onsight"]:
        unlock("first_onsight_outdoor")
    if len(outdoor["spots"]) >= 3:
        unlock("crag_explorer_3")
    if len(outdoor["spots"]) >= 5:
        unlock("crag_explorer_5")
    for discipline, (_rank, grade) in outdoor["pb_sent"].items():
        unlock(
            f"grade_first_redpoint:{discipline}:{grade}",
            context={"rule": "grade_first_redpoint", "discipline": discipline, "grade": grade},
        )
    for discipline, (_rank, grade) in outdoor["pb_onsight"].items():
        unlock(
            f"grade_first_onsight:{discipline}:{grade}",
            context={"rule": "grade_first_onsight", "discipline": discipline, "grade": grade},
        )

    # --- Macrocycle / process
    if state.get("macrocycle_history"):
        unlock("first_cycle_completed")
        for h in state["macrocycle_history"]:
            phases = (h.get("completion_summary") or {}).get("phases_completed") or []
            if "performance" in phases:
                unlock("reached_performance")
    if macrocycle:
        week_num = _macro_week_of(macrocycle, current_monday)
        total = macrocycle.get("total_weeks") or 0
        if week_num and 1 <= week_num <= total:
            phase = _phase_for_week(macrocycle, week_num)
            if phase in ("performance", "deload"):
                unlock("reached_performance")

    return newly


def mark_seen(state: Dict[str, Any], milestone_id: str) -> bool:
    """Mark one unlocked milestone as seen. Returns True if found."""
    for entry in (state.get("milestones") or {}).get("unlocked", []):
        if entry.get("id") == milestone_id:
            entry["seen"] = True
            return True
    return False
