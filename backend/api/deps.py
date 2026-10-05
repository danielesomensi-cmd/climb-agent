"""Shared dependencies for the climb-agent API."""

from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
from uuid import uuid4
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request

from backend.engine import macro_position as _macro_position
from backend.engine import storage as _storage

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Re-export from storage for backwards compatibility with existing imports.
DATA_DIR = _storage.DATA_DIR
STATE_PATH = _storage.STATE_PATH
USERS_DIR = _storage.USERS_DIR

EMPTY_TEMPLATE: Dict[str, Any] = {
    "schema_version": "1.5",
    "user": {},
    "assessment": {},
    "goal": {},
    "availability": {},
    "equipment": {"home": [], "gyms": []},
    "planning_prefs": {},
    "preferences": {"finger_training_device": "hangboard"},
    "limitations": {"active_flags": [], "details": []},
    "trips": [],
    "macrocycle": None,
    "performance": {},
    "baselines": {},
    "stimulus_recency": {},
    "fatigue_proxy": {},
    "working_loads": {"entries": [], "rules": {}},
    "tests": {},
    "body": {},
    "current_week_plan": None,
    "week_plans": {},
    "outdoor_spots": [],
    "free_sessions": [],
    # A296: limit log — written only by apply_feedback / free-session finish.
    "limit_log": [],
    # A298: bodyweight ladder levels {family: entry, "technique": {...}}.
    "bw_progression": {},
    "quote_history": [],
    "history_index": {"outdoor_log_paths": []},
}


#: B369: a cached week plan that no longer reflects the user's settings
#: (availability, planning prefs, weekly override, new macrocycle, resume, test
#: request). The plan stays in the cache — it IS the user's plan, with their
#: custom / forced / moved sessions and their removals — and GET /api/week
#: regenerates it THROUGH the preserving merge on the next read. Deleting it
#: (the pre-B369 behaviour) left nothing to merge from.
STALE_KEY = "_stale"


def mark_weeks_stale(
    state: Dict[str, Any],
    *,
    from_monday: Optional[str] = None,
    only: Optional[str] = None,
    today: Optional[date] = None,
) -> list:
    """Flag the cached current and future weeks as stale (B369). Returns the
    flagged ``week_plans`` keys.

    Past weeks (key < this Monday) are never touched — they are immutable.
    *from_monday* raises the lower bound (a new cycle starting next week),
    *only* restricts the flag to one week (a weekly override). The legacy
    ``current_week_plan`` pointer is flagged with the same rule.
    """
    lower = this_monday(today or datetime.now().date())
    if from_monday and from_monday > lower:
        lower = from_monday
    marked = []
    # B371: flagging a week is a write — its revision moves forward, so a
    # client still holding the pre-change copy gets a 409 (and refetches the
    # regenerated week) instead of editing the old structure. Only on the
    # transition (flagging twice stays idempotent) and once per plan object:
    # current_week_plan is often the same dict as its week_plans entry.
    bumped: set = set()

    def _flag(plan: dict) -> None:
        was_stale = bool(plan.get(STALE_KEY))
        plan[STALE_KEY] = True
        if not was_stale and id(plan) not in bumped:
            bumped.add(id(plan))
            try:
                plan["plan_revision"] = max(1, int(plan.get("plan_revision") or 1)) + 1
            except (TypeError, ValueError):
                plan["plan_revision"] = 2

    for k, plan in (state.get("week_plans") or {}).items():
        if not isinstance(k, str) or not isinstance(plan, dict):
            continue
        if k < lower or (only is not None and k != only):
            continue
        _flag(plan)
        marked.append(k)
    cwp = state.get("current_week_plan")
    if isinstance(cwp, dict):
        k = cwp.get("start_date")
        if isinstance(k, str) and k >= lower and (only is None or k == only):
            hot = (state.get("week_plans") or {}).get(k)
            if isinstance(hot, dict) and hot is not cwp:
                # A separate copy of the same week: same flag, same revision.
                cwp[STALE_KEY] = True
                if hot.get("plan_revision") is not None:
                    cwp["plan_revision"] = hot["plan_revision"]
            else:
                _flag(cwp)
    return sorted(marked)


def invalidate_week_cache(state: Dict[str, Any]) -> None:
    """Mark the cached current and future weeks stale (B369).

    They used to be deleted (and ``current_week_plan`` stashed into
    ``_prev_week_plan``, which on any day but Monday was never merged back and
    could later be weekday-copied onto another week). Now they stay in the
    cache flagged ``_stale``: the next GET /api/week regenerates each one
    through the merge that keeps the user's sessions and removals. Past weeks
    are never touched.
    """
    mark_weeks_stale(state)


def _legacy_header_allowed() -> bool:
    """Whether the ``X-User-ID`` dev fallback is explicitly enabled (B285).

    Read at call time (not import) so tests can flip it. Default OFF — the
    fallback is a development convenience and must never be reachable in a
    production-like configuration without an explicit opt-in.
    """
    return os.environ.get("ALLOW_LEGACY_HEADER", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _auth_enforced() -> bool:
    """True when real authentication is mandatory (B285 — fail-closed).

    Production-like means: Clerk is configured OR the Supabase backend is in
    use. In that configuration an unauthenticated request must be rejected
    with 401 rather than silently resolving to ``None`` (which would read and
    write the shared ``__legacy__`` bucket) or trusting a client-supplied
    ``X-User-ID`` header (full IDOR).

    ``ALLOW_LEGACY_HEADER=1`` restores the pre-B285 behavior for local dev.
    pytest and local file-backend dev are unaffected: Clerk is unconfigured and
    STORAGE_BACKEND defaults to 'file'.
    """
    if _legacy_header_allowed():
        return False
    from backend.api.auth import is_clerk_configured
    if is_clerk_configured():
        return True
    return os.environ.get("STORAGE_BACKEND", "file") == "supabase"


def get_user_id(request: Request) -> Optional[str]:
    """Extract user_id from request, trying Clerk JWT first, then X-User-ID.

    Priority:
    1. Authorization: Bearer <clerk_jwt> → verify → lookup/create user_id
    2. X-User-ID header — dev/test only, rejected when _auth_enforced() (B285)
    3. None — dev only; 401 when _auth_enforced() (B285)

    A245 E-1 (B4): the resolved id is also stashed on `request.state` so the
    rate limiter can key per user instead of per (proxy) IP. Doing it here means
    every authenticated route gets it for free, with no extra dependency.
    """
    # 1. Try Clerk JWT
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        from backend.api.auth import get_clerk_user_id, is_clerk_configured, lookup_or_create_user
        if is_clerk_configured():
            try:
                token = auth_header.split(" ", 1)[1]
                clerk_id = get_clerk_user_id(token)
                user_id = lookup_or_create_user(clerk_id)
                request.state.user_id = user_id
                return user_id
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    enforced = _auth_enforced()

    # 2. Fallback: X-User-ID (dev/test only)
    header = request.headers.get("X-User-ID")
    if header is not None:
        if enforced:
            # SEC-1: accepting this header in production is a full IDOR —
            # any UUID would grant read/write/delete on that user's account.
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "authentication_required",
                    "message": "X-User-ID is not accepted; sign in to continue.",
                },
            )
        try:
            _uuid.UUID(header, version=4)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-User-ID: must be a valid UUID v4")
        request.state.user_id = header
        return header

    # 3. No credentials at all
    if enforced:
        # SEC-2/SEC-5: returning None here would let the request through on the
        # shared '__legacy__' bucket (and past the subscription guard).
        raise HTTPException(
            status_code=401,
            detail={
                "error": "authentication_required",
                "message": "Sign in to continue.",
            },
        )
    return None


def _user_state_path(user_id: Optional[str]) -> Path:
    """Return the state file path for a given user_id, or the legacy path."""
    return _storage._user_state_path(user_id)


def _migrate_gym_ids(state: Dict[str, Any]) -> bool:
    """Ensure every gym has a stable gym_id (B88 migration). Returns True if state was modified."""
    gyms = state.get("equipment", {}).get("gyms")
    if not gyms:
        return False
    changed = False
    for gym in gyms:
        if not gym.get("gym_id"):
            gym["gym_id"] = uuid4().hex[:8]
            changed = True
    return changed


def load_state(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Load user state from disk. Returns empty template if file missing.

    If user_id is provided, reads from the per-user directory.
    If the per-user file doesn't exist, copies the template and returns it.
    """
    state = _storage.read_state(user_id)
    if state is not None:
        # B88: gym IDs
        dirty = _migrate_gym_ids(state)
        # B253: tests_source sidecar backfill for pre-D214 users
        from backend.engine.migrations.m001_backfill_tests_source import migrate as _backfill_tests_source
        if _backfill_tests_source(state):
            dirty = True
        # A271: a value in assessment.tests was typed by a human, so it is
        # measured. Closes the gap m001 cannot reach — four production users had
        # a real finger number and an empty sidecar because they onboarded
        # before D214. Runs BEFORE m002, which derives axis provenance from it.
        from backend.engine.migrations.m003_backfill_tests_source_from_values import migrate as _backfill_source_from_values
        _tests_source_grew = _backfill_source_from_values(state)
        if _tests_source_grew:
            dirty = True
        # A269: profile_source sidecar. MUST run after m001 and m003 — it derives
        # axis provenance from tests_source, and reversed a measured axis would
        # be marked estimated. When m003 just widened the sidecar, the stored
        # profile_source was derived from a blind one: recompute rather than
        # keep it.
        from backend.engine.migrations.m002_backfill_profile_source import migrate as _backfill_profile_source
        if _backfill_profile_source(state, force=_tests_source_grew):
            dirty = True
        # A221: lazy-archive past week_plans into the cold store. Env-gated
        # (default OFF) so the rollout is: deploy code (flag off) → backup +
        # controlled migration run → flip flag on for ongoing rollover archiving.
        # The read path serves archived weeks regardless of this flag.
        if _lazy_archive_enabled() and user_id:
            try:
                if archive_past_weeks(state, user_id):
                    dirty = True
            except Exception:
                logger.exception("A221: lazy archive failed; serving hot state unchanged")
        if dirty:
            save_state(state, user_id)
        return state
    if user_id:
        # New user: bootstrap from template
        state = deepcopy(EMPTY_TEMPLATE)
        _storage.write_state(state, user_id)
        return state
    return deepcopy(EMPTY_TEMPLATE)


def _ensure_profile_fresh(state: Dict[str, Any]) -> None:
    """Recompute assessment profile if assessment inputs changed since last computation.

    B127: ensures profile always reflects current assessment.tests, grades,
    self_eval, and body data — regardless of which endpoint modified them.
    """
    assessment = state.get("assessment") or {}
    goal = state.get("goal") or {}

    # Need minimum data to compute a profile
    if not goal.get("target_grade"):
        return
    if not assessment.get("grades") and not assessment.get("tests"):
        return

    # Build a fingerprint of the inputs that affect the profile
    import hashlib
    inputs = json.dumps({
        "body": assessment.get("body") or {},
        "grades": assessment.get("grades") or {},
        "tests": assessment.get("tests") or {},
        # A269 deliberately does NOT add `tests_source` here, though the brief
        # proposed it. Doing so forces a one-time recompute for every user, and
        # on the production corpus that is not the no-op the brief assumed:
        # three loading-pin profiles were stored before A266 taught the finger
        # axis to read `lp_max_lift_*`, so a forced recompute would silently
        # move them (51→100, 51→69, 54→71). One of them is `e60d7a0c`, whose
        # recompute Daniele explicitly withheld pending verification (A266-P1).
        # A migration must not overturn a product decision.
        #
        # It is not needed either: `m002` runs on every read, immediately after
        # the `m001` backfill that populates `tests_source`, so provenance is
        # derived from the populated sidecar on the very first load. Any later
        # change to `tests_source` travels with a change to `tests`, which does
        # move the fingerprint.
        "self_eval": assessment.get("self_eval") or {},
        "experience": assessment.get("experience") or {},
        "target_grade": goal.get("target_grade"),
        "current_grade": goal.get("current_grade"),
    }, sort_keys=True)
    fingerprint = hashlib.md5(inputs.encode()).hexdigest()

    # Skip recomputation if inputs haven't changed
    if assessment.get("_profile_fingerprint") == fingerprint:
        return

    try:
        from backend.engine.assessment_v1 import (
            PROFILE_SCORING_VERSION,
            compute_assessment_profile_with_source,
        )
        profile, source = compute_assessment_profile_with_source(assessment, goal)
        assessment["profile"] = profile
        assessment["profile_source"] = source
        assessment["profile_scoring_version"] = PROFILE_SCORING_VERSION
        assessment["_profile_fingerprint"] = fingerprint
        state["assessment"] = assessment
    except Exception:
        pass  # Don't break save if recomputation fails


def save_state(state: Dict[str, Any], user_id: Optional[str] = None) -> None:
    """Write user state to disk.

    If user_id is provided, writes to the per-user directory.
    Automatically recomputes assessment profile if inputs changed (B127).
    """
    _ensure_profile_fresh(state)
    _storage.write_state(state, user_id)


def ensure_monday(d: str) -> str:
    """If *d* (YYYY-MM-DD) is not a Monday, round DOWN to the previous Monday."""
    try:
        dt = datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format: expected YYYY-MM-DD, got {d!r}")
    return (dt - timedelta(days=dt.weekday())).isoformat()


def next_monday(from_date: Optional[date] = None) -> str:
    """Return the next Monday as 'YYYY-MM-DD'. If from_date is already Monday, return it."""
    d = from_date or date.today()
    days_ahead = (7 - d.weekday()) % 7  # 0 = Monday
    if days_ahead == 0:
        return d.isoformat()
    return (d + timedelta(days=days_ahead)).isoformat()


def this_monday(from_date: Optional[date] = None) -> str:
    """Return the Monday of the current week as 'YYYY-MM-DD'.

    Unlike next_monday(), this goes backwards to find the Monday
    so that a macrocycle can start immediately (partial first week).
    """
    d = from_date or date.today()
    # weekday() returns 0 for Monday
    return (d - timedelta(days=d.weekday())).isoformat()


def is_past_week(week_start: str, from_date: Optional[date] = None) -> bool:
    """True iff *week_start* (a Monday "YYYY-MM-DD") is strictly before the
    current week's Monday.

    B257: canonical "is this an immutable past week?" check. Past weeks must
    never be regenerated by any path (cache-miss, force, device switch,
    equipment change, replan) — only explicit user edit may touch them. Reuses
    this_monday() so the boundary has a single definition (B216/B217 were caused
    by parallel date logic). Both operands are Monday-aligned ISO dates, so the
    string comparison is exact.
    """
    return week_start < this_monday(from_date)


# ---------------------------------------------------------------------------
# A221: lazy-archive of past week_plans (cold store)
#
# Hot window is C1 = {N-1, N, future}. Weeks with week_start < hot_floor()
# (= Monday of the previous week) are moved to the cold store and read on
# demand. The hot/cold boundary has a single definition (hot_floor) to avoid
# the parallel-date-logic class of bug (B216/B217).
# ---------------------------------------------------------------------------

def hot_floor(from_date: Optional[date] = None) -> str:
    """Monday of the *previous* week — the archiving boundary (A221, C1).

    Weeks with ``week_start < hot_floor()`` are archived; {N-1, N, future}
    stay hot. N-1 must stay hot: week.py cross-week spacing reads
    week_plans[N-1] directly, and the recency lookback expects it present.
    """
    monday = date.fromisoformat(this_monday(from_date))
    return (monday - timedelta(days=7)).isoformat()


def _lazy_archive_enabled() -> bool:
    """Whether the lazy archive *trigger* is active (env-gated, default OFF).

    Read at call time (not import) so the controlled migration run and tests
    can flip it without a restart. The READ path (serving archived weeks,
    recency, reports) works regardless of this flag — only the automatic
    hot→cold *move* in load_state is gated.
    """
    return os.environ.get("WEEKPLAN_ARCHIVE_LAZY", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


def archive_past_weeks(
    state: Dict[str, Any], user_id: Optional[str], from_date: Optional[date] = None
) -> int:
    """Move hot ``week_plans`` with ``week_start < hot_floor()`` into the cold
    store. Returns the number of weeks archived.

    Safety crux (A221): the archive write is verified *before* the hot copy is
    pruned. If the archive write/verify fails for a week, the hot copy is kept
    and that week is skipped (idempotent — retried next time). Pure move: the
    plan dict is copied unmodified, no planner/resolver ever runs. Mutates
    ``state['week_plans']`` in place; the caller is responsible for persisting.
    """
    if not user_id:
        return 0
    floor = hot_floor(from_date)
    week_plans = state.get("week_plans") or {}
    to_move = sorted(k for k in week_plans if isinstance(k, str) and k < floor)
    moved = 0
    for k in to_move:
        plan = week_plans[k]
        try:
            _storage.archive_week(user_id, k, plan)
            # Verify the archive landed before pruning the only other copy.
            if _storage.read_archived_week(user_id, k) is None:
                logger.error(
                    "A221: archive verify failed for user=%s week=%s — keeping hot copy",
                    user_id, k,
                )
                continue
        except Exception:
            logger.exception(
                "A221: archive write failed for user=%s week=%s — keeping hot copy",
                user_id, k,
            )
            continue
        del state["week_plans"][k]
        moved += 1
    return moved


def read_archived_week(user_id: Optional[str], week_start: str) -> Optional[Dict[str, Any]]:
    """Read a single week plan from the cold store (None if absent).

    Thin call-time delegate to the active storage backend so tests can
    monkeypatch ``backend.engine.storage``.
    """
    return _storage.read_archived_week(user_id, week_start)


def read_week_plan(
    state: Dict[str, Any], user_id: Optional[str], week_start: str
) -> Optional[Dict[str, Any]]:
    """Return the plan for *week_start* from hot state, falling back to the
    cold store. None if neither has it. Read-only — never regenerates."""
    week_plans = state.get("week_plans") or {}
    hit = week_plans.get(week_start)
    if hit is not None:
        return hit
    return _storage.read_archived_week(user_id, week_start)


# ---------------------------------------------------------------------------
# A223: Plan pause / resume (Option B from D246)
#
# start_date is IMMUTABLE. A cumulative, whole-week pause offset shifts the
# *effective* anchor read ONLY by the two forward consumers below
# (current_phase_and_week, week_num_to_phase_context) — the single source of
# truth for the offset math. The completion window [start_date, end_date] and
# every past-date derivation keep reading the raw start_date, so completed/
# archived sessions stay inside the cycle window (the failure mode that ruled
# out Option A). With no pause (offset 0, no active_since) both helpers reduce
# to the raw values → ZERO behavior change for non-paused users.
# ---------------------------------------------------------------------------

def compute_pause_offset(paused_at: str, resume_date: str) -> int:
    """Whole-week pause delta in days, Monday-to-Monday (A223).

    ``N = Monday(resume_date) - Monday(paused_at)`` in days — always a
    non-negative multiple of 7. A sub-week pause (resume in the same ISO week as
    the pause start) yields ``0`` → the plan does not shift (product decision
    "a", D246/A223). The intra-week partial is handled by the planner's existing
    ``today`` param, so the Monday-invariant holds by construction.
    """
    p = datetime.strptime(paused_at, "%Y-%m-%d").date()
    r = datetime.strptime(resume_date, "%Y-%m-%d").date()
    p_mon = p - timedelta(days=p.weekday())
    r_mon = r - timedelta(days=r.weekday())
    return max(0, (r_mon - p_mon).days)


def _effective_anchor(
    macrocycle: Dict[str, Any], today: Optional[date] = None
) -> Tuple[date, date]:
    """Return ``(effective_start, effective_today)`` accounting for pause (A223).

    - ``effective_start = start_date + pause.offset_days`` (cumulative completed
      pauses). Used so the forward position does not include paused time.
    - ``effective_today``: while a pause is active, frozen at ``active_since`` so
      the position stops advancing during the pause; otherwise ``today``
      (default ``date.today()``).

    No pause → ``(start_date, today)`` exactly.

    A288: the logic lives in ``backend.engine.macro_position.effective_anchor``
    (pure, date passed in); this wrapper only supplies ``date.today()``.
    """
    return _macro_position.effective_anchor(macrocycle, today or date.today())


def is_plan_paused(state: Dict[str, Any]) -> bool:
    """True iff the current macrocycle has an active (open) pause."""
    mc = state.get("macrocycle") or {}
    return bool((mc.get("pause") or {}).get("active_since"))


def assert_plan_not_paused(state: Dict[str, Any]) -> None:
    """Guard for plan-mutating endpoints (A223). Raises 409 while paused so
    replan/regenerate/availability-change paths are a no-op until the user
    resumes. Reads stay available. No-op when not paused (every existing,
    non-paused user)."""
    if is_plan_paused(state):
        raise HTTPException(
            status_code=409,
            detail={"paused": True, "message": "Resume your plan to continue"},
        )


def pause_intervals(macrocycle: Dict[str, Any], today_iso: Optional[str] = None) -> list:
    """Closed [from, to] pause intervals for display classification (A223).

    Includes the completed intervals from ``pause.log`` plus the currently-open
    interval (``active_since`` → today) if a pause is active. Read-only.
    """
    pause = macrocycle.get("pause") or {}
    out = [
        (e["from"], e["to"])
        for e in (pause.get("log") or [])
        if e.get("from") and e.get("to")
    ]
    active_since = pause.get("active_since")
    if active_since:
        out.append((active_since, today_iso or date.today().isoformat()))
    return out


def current_phase_and_week(
    macrocycle: Dict[str, Any], today: Optional[date] = None
) -> Tuple[int, int]:
    """Given a macrocycle dict, find which phase and week-within-phase today falls in.

    Returns (phase_index, week_within_phase) both 0-based.
    If today is before the macrocycle start, returns (0, 0).
    If today is past the end, returns last phase and its last week.

    A223: reads the *effective* anchor (start_date + pause offset) and a
    pause-frozen "today" so a paused plan holds its position. No pause →
    identical to the pre-A223 behavior.

    A288: delegates to ``backend.engine.macro_position.phase_and_week_on``;
    ``today`` defaults to ``date.today()`` (every existing caller).
    """
    return _macro_position.phase_and_week_on(macrocycle, today or date.today())


def week_num_to_phase_context(macrocycle: Dict[str, Any], week_num: int) -> Dict[str, Any]:
    """Convert a 1-based absolute week_num to phase context needed by generate_phase_week.

    week_num=0 means 'current week' (resolved from today's date).

    Returns dict with: phase_id, domain_weights, session_pool, start_date,
    intensity_cap, and the original phase dict.
    """
    phases = macrocycle.get("phases") or []
    if not phases:
        raise ValueError("Macrocycle has no phases")

    # A223: effective anchor (start_date + pause offset). current_phase_and_week
    # is already pause-aware, so week_num=0 resolution stays consistent.
    mc_start, _ = _effective_anchor(macrocycle)

    if week_num == 0:
        pi, wi = current_phase_and_week(macrocycle)
        cumulative = sum(p.get("duration_weeks", 1) for p in phases[:pi])
        week_num = cumulative + wi + 1  # convert to 1-based

    # Find phase for this week_num
    cumulative = 0
    for phase in phases:
        duration = phase.get("duration_weeks", 1)
        if week_num <= cumulative + duration:
            week_in_phase = week_num - cumulative - 1  # 0-based
            week_start = mc_start + timedelta(weeks=cumulative + week_in_phase)
            return {
                "phase_id": phase["phase_id"],
                "domain_weights": phase.get("domain_weights", {}),
                "session_pool": phase.get("session_pool", []),
                "start_date": week_start.isoformat(),
                "intensity_cap": phase.get("intensity_cap"),
                "phase": phase,
                "week_num": week_num,
                "is_first_week_of_phase": (week_in_phase == 0),
                "is_last_week_of_phase": (week_in_phase == duration - 1),
            }
        cumulative += duration

    raise ValueError(f"week_num {week_num} exceeds macrocycle total weeks ({cumulative})")


def build_current_level(grades: Dict[str, Any]) -> Dict[str, Any]:
    """Build performance.current_level from assessment grades.

    Shared by onboarding (initial build) and PUT /api/state (B272: rebuild on
    grade edits so progression benchmarks — e.g. the kilter fallback reading
    current_level.boulder.worked.grade — track Settings changes instead of
    staying frozen at the onboarding-era values).
    """
    level: Dict[str, Any] = {"updated_at": None}
    if grades.get("lead_max_rp") or grades.get("lead_max_os"):
        level["sport"] = {}
        if grades.get("lead_max_rp"):
            level["sport"]["worked"] = {"grade": grades["lead_max_rp"]}
        if grades.get("lead_max_os"):
            level["sport"]["onsight"] = {"grade": grades["lead_max_os"]}
    if grades.get("boulder_max_rp") or grades.get("boulder_max_os"):
        level["boulder"] = {}
        if grades.get("boulder_max_rp"):
            level["boulder"]["worked"] = {"grade": grades["boulder_max_rp"]}
        if grades.get("boulder_max_os"):
            level["boulder"]["onsight"] = {"grade": grades["boulder_max_os"]}
    return level


def refresh_current_level_from_grades(state: Dict[str, Any]) -> None:
    """Rebuild the grade-derived branches of ``performance.current_level``.

    B272 did this inline in PUT /api/state; A292's onsight confirmation needs
    the same rebuild, so it lives here. Only ``sport`` and ``boulder`` are
    replaced — ``gym_reference`` and the rest of current_level are kept.
    """
    grades = (state.get("assessment") or {}).get("grades") or {}
    rebuilt = build_current_level(grades)
    performance = state.get("performance") or {}
    current_level = performance.get("current_level") or {}
    for branch in ("sport", "boulder"):
        current_level.pop(branch, None)
        if branch in rebuilt:
            current_level[branch] = rebuilt[branch]
    current_level["updated_at"] = date.today().isoformat()
    performance["current_level"] = current_level
    state["performance"] = performance


# ---------------------------------------------------------------------------
# Subscription guard dependency
# ---------------------------------------------------------------------------

# B258: never-trialed statuses get a "start" message; ended-trial statuses get
# the "ended" message. Prevents the misleading "Your trial has ended" copy from
# reaching users who never started a trial (pending_checkout / no row → none).
_NEVER_STARTED_STATUSES = {"none", "pending_checkout"}


def _subscription_required_message(status: str) -> str:
    """User-facing 402 message, tailored to subscription status (B258)."""
    if status in _NEVER_STARTED_STATUSES:
        return "Subscribe to start training."
    return "Your trial has ended — subscribe to continue. Your training data is safe."


def require_active_subscription(user_id: Optional[str] = Depends(get_user_id)) -> None:
    """FastAPI dependency: raise 402 when the user cannot interact.

    No-op (allows the request) when:
    - STRIPE_SECRET_KEY is not set (dev/test)
    - STORAGE_BACKEND != 'supabase' (pytest uses file backend)
    - user_id is None (unauthenticated dev request)
    - user_id is in BYPASS_USER_IDS (founder / beta)
    - subscription status is trialing or active

    Fail-closed (raises 402) when Stripe is configured and the subscription is
    missing/pending_checkout/past_due/canceled/expired. The 402 message is
    status-aware so never-trialed users (pending_checkout / no row) are told to
    *start*, not that a trial *ended* (B258).
    """
    from backend.engine.subscription_guard import check_subscription
    result = check_subscription(user_id)
    if not result["can_interact"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "subscription_required",
                "status": result["status"],
                "message": _subscription_required_message(result["status"]),
            },
        )
