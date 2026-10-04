"""Feedback router — atomic session feedback + closed-loop state updates.

A194: This endpoint is atomic. In a single round-trip, the frontend can submit
feedback and have the backend:
  1. mark_done on current_week_plan (via apply_events)
  2. append to session_completion_log (with dedup guard)
  3. progression feedback update
  4. closed-loop state update (stimulus recency, fatigue proxy)
  5. actual_exercises persistence into the session slot
  6. adaptive replan check
  7. save state + return updated week_plan

The updated week_plan is returned in the response so the frontend can call
setQueryData(['week', 0], …) instead of issuing a separate refetch.

Scope note (A194 R6): only current_week_plan is updated inline. Past/future
sessions continue through the legacy flow.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.deps import (
    current_phase_and_week,
    get_user_id,
    load_state,
    require_active_subscription,
    save_state,
    week_num_to_phase_context,
)
from backend.api.rate_limit import limiter
from backend.api.models import FeedbackRequest
from backend.api.routers.replanner import persist_week_plan
from backend.engine.adaptive_replan import (
    append_feedback_log,
    apply_adaptive_replan,
    check_adaptive_replan,
    load_exercises_by_id,
)
from backend.engine.closed_loop_v1 import apply_day_result_to_user_state
from backend.engine.load_score import compute_actual_load_score, fatigue_map_by_id
from backend.engine.measured_feedback import (
    derive_session_difficulty,
    feedback_rating,
    limitation_suggestion_for_pain,
    log_contract,
    sanitize_log_entry,
    sanitize_pain,
)
from backend.engine.progression_v1 import apply_feedback
from backend.engine.replanner_v1 import apply_events
from backend.engine.resolve_session import normalize_limitations, _check_exercise_limitation

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def _monday_for_date(iso_date: str) -> Optional[str]:
    """Return the Monday (YYYY-MM-DD) of the ISO week containing *iso_date*."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return (d - timedelta(days=d.weekday())).isoformat()


def _is_current_macrocycle_monday(state: dict, candidate_monday: str) -> bool:
    """True iff *candidate_monday* is the Monday of the current macrocycle week.

    B287/R-6: computed through week_num_to_phase_context, which anchors on
    _effective_anchor (start_date + pause offset, A223). The previous inline
    arithmetic used the RAW start_date, so after a pause this never matched and
    current_week_plan was left stale for its readers.
    """
    mc = state.get("macrocycle") or {}
    if not mc.get("phases") or not mc.get("start_date"):
        return False
    try:
        current_start = week_num_to_phase_context(mc, 0)["start_date"]
    except (ValueError, KeyError):
        return False
    return candidate_monday == current_start


def _attach_prescribed_reps(log_entry: dict, state: dict, target_date, target_sid) -> None:
    """B363: copy the prescribed reps of each exercise onto its feedback item.

    Looks the session up in the stored week plan (planned, quick-added and
    custom sessions all live there as ``exercises``), falling back to the
    custom session definition. Best effort: an exercise not found keeps no
    ``prescribed_reps`` and progression uses the catalog default.
    """
    items = (log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
    if not items or not target_date or not target_sid:
        return

    reps_by_id: dict = {}
    # A295: the prescribed sets and work time travel with the reps (same three
    # sources): the double progression and the pull-up step need "all sets
    # done", the hang margin needs the prescribed seconds.
    sets_by_id: dict = {}
    work_by_id: dict = {}

    def _collect(exercises) -> None:
        for ex in exercises or []:
            if not isinstance(ex, dict):
                continue
            eid = ex.get("exercise_id")
            if not eid:
                continue
            presc = ex.get("prescription") or {}
            reps = ex.get("reps")
            if reps is None:
                reps = presc.get("reps")
            if isinstance(reps, (int, float)) and reps > 0 and eid not in reps_by_id:
                reps_by_id[eid] = reps
            sets = ex.get("sets") if ex.get("sets") is not None else presc.get("sets")
            if isinstance(sets, (int, float)) and sets > 0 and eid not in sets_by_id:
                sets_by_id[eid] = sets
            work = ex.get("work_seconds") if ex.get("work_seconds") is not None else presc.get("work_seconds")
            if isinstance(work, (int, float)) and work > 0 and eid not in work_by_id:
                work_by_id[eid] = work

    monday = _monday_for_date(target_date)
    plans = [(state.get("week_plans") or {}).get(monday) if monday else None, state.get("current_week_plan")]
    for plan in plans:
        for week in (plan or {}).get("weeks") or []:
            for day in week.get("days") or []:
                if day.get("date") != target_date:
                    continue
                for s in day.get("sessions") or []:
                    if s.get("session_id") == target_sid:
                        _collect(s.get("exercises"))
                        _collect(s.get("exercise_instances"))
                        # Planned (macrocycle) sessions keep them under resolved.
                        _collect(((s.get("resolved") or {}).get("resolved_session") or {}).get("exercise_instances"))
    if str(target_sid).startswith("custom_"):
        cs_id = str(target_sid)[len("custom_"):]
        for cs in state.get("custom_sessions") or []:
            if isinstance(cs, dict) and cs.get("id") == cs_id:
                _collect(cs.get("exercises"))

    for item in items:
        eid = item.get("exercise_id")
        if eid in reps_by_id and item.get("reps") is None and item.get("prescribed_reps") is None:
            item["prescribed_reps"] = reps_by_id[eid]
        if eid in sets_by_id and item.get("prescribed_sets") is None:
            item["prescribed_sets"] = sets_by_id[eid]
        if eid in work_by_id and item.get("prescribed_work_seconds") is None and item.get("work_seconds") is None:
            item["prescribed_work_seconds"] = work_by_id[eid]


@router.post("", dependencies=[Depends(require_active_subscription)])
@limiter.limit("30/minute")
def post_feedback(request: Request, req: FeedbackRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Apply session feedback atomically: mark_done + progression + closed-loop + persist."""
    state = load_state(user_id)

    target_date = req.log_entry.get("date")
    target_sid = req.log_entry.get("session_id")

    # 1. A194: Apply mark_done inline to current_week_plan (idempotent — safe if
    # frontend already called applyEvents separately, e.g. from /today).
    availability = state.get("availability")
    planning_prefs = state.get("planning_prefs")
    gyms = (state.get("equipment") or {}).get("gyms")
    week_plan = state.get("current_week_plan")
    if week_plan and target_date and target_sid:
        try:
            week_plan = apply_events(
                week_plan,
                [{
                    "event_type": "mark_done",
                    "date": target_date,
                    "session_ref": target_sid,
                }],
                availability=availability,
                planning_prefs=planning_prefs,
                gyms=gyms,
            )
            state["current_week_plan"] = week_plan
            # Sync to per-week cache so subsequent operations in this request
            # mutate the same object (B136b).
            start_key = week_plan.get("start_date", "")
            if start_key:
                state.setdefault("week_plans", {})[start_key] = week_plan
        except ValueError as e:
            # B216 Defect B: _find_day raises ValueError when target_date is
            # outside the plan window — typically when current_week_plan is
            # stale at the Monday rollover and the correct plan lives in
            # week_plans[target_monday]. Retry against the date-indexed cache
            # before giving up so mark_done isn't silently dropped.
            target_monday = _monday_for_date(target_date)
            alt_plan = (state.get("week_plans") or {}).get(target_monday) if target_monday else None
            if alt_plan:
                try:
                    alt_plan = apply_events(
                        alt_plan,
                        [{
                            "event_type": "mark_done",
                            "date": target_date,
                            "session_ref": target_sid,
                        }],
                        availability=availability,
                        planning_prefs=planning_prefs,
                        gyms=gyms,
                    )
                    state.setdefault("week_plans", {})[target_monday] = alt_plan
                    # If target_monday is the current macrocycle week, also
                    # refresh legacy current_week_plan so downstream readers
                    # (progression, adaptive_replan, persist) use it.
                    if _is_current_macrocycle_monday(state, target_monday):
                        state["current_week_plan"] = alt_plan
                        week_plan = alt_plan
                    logger.info(
                        "B216: mark_done landed in week_plans[%s] (current_week_plan was stale)",
                        target_monday,
                    )
                except ValueError as e2:
                    logger.warning(
                        "B216: mark_done skipped — date not in primary or alt plan: %s (date=%r, sid=%r)",
                        e2, target_date, target_sid,
                    )
            else:
                logger.warning(
                    "A194 mark_done inline skipped: %s (date=%r, sid=%r)",
                    e, target_date, target_sid,
                )
    elif not week_plan:
        logger.warning("post_feedback: no current_week_plan, skipping inline mark_done")
    elif not (target_date and target_sid):
        logger.warning(
            "post_feedback: log_entry missing date/session_id, skipping inline mark_done",
        )

    # 1b. A194: Append to session_completion_log with dedup guard (R3).
    # Skip if an entry with the same date+session_id+status already exists —
    # prevents duplicates when /today handleMarkDone also fired applyEvents.
    if target_date and target_sid:
        completion_log = state.setdefault("session_completion_log", [])
        already_logged = any(
            e.get("date") == target_date
            and e.get("session_id") == target_sid
            and e.get("status") == "done"
            for e in completion_log
        )
        if not already_logged:
            completion_log.append({
                "date": target_date,
                "session_id": target_sid,
                "status": "done",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })

    # A213: detect body-part sessions so they bypass macrocycle closed-loop.
    # apply_feedback still runs (it only updates working_loads.entries[] for
    # non-test exercises, which is exactly what we want). apply_day_result
    # (stimulus_recency / fatigue_proxy) is skipped — body-part sessions are
    # ad-hoc strength work outside the phase plan.
    _is_body_part_session = False
    if req.resolved_day:
        for _s in req.resolved_day.get("sessions", []):
            if _s.get("session_id") == target_sid and _s.get("build_kind") == "body_parts":
                _is_body_part_session = True
                break

    # A240: adhoc/custom sessions are off-plan support work. They DO write
    # working_loads (apply_feedback below runs unconditionally) but must NEVER
    # feed the macrocycle closed-loop (stimulus_recency / fatigue_proxy). The
    # custom player omits resolved_day, so the resolved_day gate at step 3
    # already skips the closed-loop; this explicit guard enforces the boundary
    # server-side even if a future caller passes resolved_day for a custom
    # session. Mirrors the _is_body_part_session pattern (A213).
    _is_custom_session = str(target_sid or "").startswith("custom_")
    if not _is_custom_session and req.resolved_day:
        for _s in req.resolved_day.get("sessions", []):
            if _s.get("session_id") == target_sid and _s.get("is_custom"):
                _is_custom_session = True
                break

    # B363: tell progression how many reps each set was prescribed — the
    # clients do not send them, and the weighted pull-up max is re-based from
    # (load, reps). Only fills items that carry no reps of their own.
    _attach_prescribed_reps(req.log_entry, state, target_date, target_sid)
    # A295: the measured-feedback fields are cleaned by hand (the router does
    # not validate the schema): an out-of-range value is dropped with a
    # warning and the request still succeeds, so an outbox retry never sticks.
    for _w in sanitize_log_entry(req.log_entry):
        logger.warning("post_feedback A295 sanitize (date=%r, sid=%r): %s", target_date, target_sid, _w)

    # 2. Apply progression feedback (updates working loads)
    try:
        state = apply_feedback(req.log_entry, state)
    except Exception as e:
        logger.error("Feedback application failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Feedback application failed. Please try again.")

    # 3. Apply closed-loop state update (stimulus recency, fatigue proxy)
    if req.resolved_day and not _is_body_part_session and not _is_custom_session:
        try:
            state = apply_day_result_to_user_state(
                state,
                resolved_day=req.resolved_day,
                status=req.status,
            )
        except Exception as e:
            logger.error("Closed-loop update failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Closed-loop update failed. Please try again.")

    # 4. Append to feedback log (B25)
    exercises_by_id = load_exercises_by_id()
    append_feedback_log(state, req.log_entry, req.resolved_day, exercises_by_id)

    # B156: sanitize exercise-level notes (max 500 chars)
    _fb_items = (req.log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
    for _item in _fb_items:
        _notes = _item.get("notes")
        if _notes is not None:
            _item["notes"] = str(_notes)[:500] if _notes else None

    # 4b. A139 / B217 / A240: Persist raw actual exercise data + the measured
    # session_duration_seconds onto the session slot. Applied to every plan
    # object that could hold the session: the legacy current_week_plan, its
    # week_plans cache entry (B136b, so GET /api/week/0 sees it), AND
    # week_plans[monday(target_date)] — the last covers A240 custom sessions
    # that live in a *future* week, where current_week_plan does not contain
    # them (the B216 mark_done retry already relies on the same cache).
    #
    # Persisting duration here also lets the POST response carry it directly, so
    # the frontend cache after setQueryData isn't forced back onto the hardcoded
    # slot-table (lunch:35/morning:60/evening:90) until the next GET /api/week.
    _dur_new = req.log_entry.get("session_duration_seconds")
    if (_fb_items or _dur_new is not None) and target_date and target_sid:

        _fatigue_map = fatigue_map_by_id(exercises_by_id)

        def _apply_actual_and_dur(plan: dict) -> None:
            for _week_block in plan.get("weeks", []):
                for _day_entry in _week_block.get("days", []):
                    if _day_entry.get("date") != target_date:
                        continue
                    for _sess in _day_entry.get("sessions", []):
                        if _sess.get("session_id") != target_sid:
                            continue
                        if _fb_items:
                            _sess["actual_exercises"] = _fb_items
                            # B312: the load the user actually earned. Skipped
                            # exercises (completed: false, sent by the guided
                            # player) no longer credit their fatigue_cost, so the
                            # weekly report and the heatmap stop showing a full
                            # load for a half-done session. None → no usable
                            # signal, leave the prescribed score alone.
                            _actual_load = compute_actual_load_score(
                                _fb_items,
                                (
                                    (_sess.get("resolved") or {}).get("resolved_session")
                                    or {}
                                ).get("exercise_instances"),
                                _fatigue_map,
                            )
                            if _actual_load is not None:
                                _sess["session_load_actual"] = _actual_load
                        if _dur_new is not None:
                            # B197-style guard: never regress a measured duration.
                            _prev = _sess.get("session_duration_seconds")
                            _sess["session_duration_seconds"] = (
                                max(_prev, _dur_new)
                                if isinstance(_prev, (int, float))
                                else _dur_new
                            )
                        return

        _plans_cache = state.get("week_plans") or {}
        _candidate_plans: list = []
        _seen_plan_ids: set = set()

        def _add_candidate(_p) -> None:
            if isinstance(_p, dict) and _p.get("weeks") and id(_p) not in _seen_plan_ids:
                _seen_plan_ids.add(id(_p))
                _candidate_plans.append(_p)

        _cwp = state.get("current_week_plan") or {}
        _add_candidate(_cwp)
        _cwp_start = _cwp.get("start_date", "")
        if _cwp_start:
            _add_candidate(_plans_cache.get(_cwp_start))
        _target_monday = _monday_for_date(target_date)
        if _target_monday:
            _add_candidate(_plans_cache.get(_target_monday))

        for _p in _candidate_plans:
            _apply_actual_and_dur(_p)

    # 4c. D172-04: Stale exercise guard — warn if feedback exercise_ids don't match
    # the resolved session (session removed from catalog or exercises changed)
    stale_exercise_warning: Optional[str] = None
    if _fb_items:
        _resolved_exercise_ids: set = set()
        _wp_for_guard = state.get("current_week_plan") or {}
        for _wk in _wp_for_guard.get("weeks", []):
            for _dy in _wk.get("days", []):
                if _dy.get("date") != target_date:
                    continue
                for _ss in _dy.get("sessions", []):
                    if _ss.get("session_id") != target_sid:
                        continue
                    _rs = (_ss.get("resolved") or {}).get("resolved_session", {})
                    for _ex in _rs.get("exercise_instances", []):
                        _ex_id = str(_ex.get("exercise_id") or "").strip()
                        if _ex_id:
                            _resolved_exercise_ids.add(_ex_id)
        if _resolved_exercise_ids:
            _fb_ids = {str(i.get("exercise_id") or "").strip() for i in _fb_items if i.get("exercise_id")}
            _stale_ids = _fb_ids - _resolved_exercise_ids
            if _stale_ids:
                logger.warning(
                    "post_feedback: exercise_ids %r not found in resolved session %r on %r — possible stale session reference",
                    _stale_ids, target_sid, target_date,
                )
                stale_exercise_warning = (
                    f"Exercise IDs not found in current session plan: {sorted(_stale_ids)}"
                )

    # 5. Check adaptive replanning (B25)
    plan = state.get("current_week_plan")
    if plan and plan.get("weeks"):
        current_date = target_date or date_type.today().isoformat()
        feedback_history = state.get("feedback_log", [])
        result = check_adaptive_replan(plan, feedback_history, current_date)
        if result["actions"]:
            updated_plan = apply_adaptive_replan(plan, result["actions"])
            state["current_week_plan"] = updated_plan
            # Sync to per-week cache so navigation doesn't lose the change
            start_key = updated_plan.get("start_date", "")
            if start_key:
                if "week_plans" not in state:
                    state["week_plans"] = {}
                state["week_plans"][start_key] = updated_plan

    # 6. Limitation severity suggestions (B38)
    limitation_suggestions = []
    limitation_map = normalize_limitations(state)
    if limitation_map:
        exercise_feedback = (req.log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
        _contract = log_contract(req.log_entry)
        for item in exercise_feedback:
            label = feedback_rating(item, _contract)
            if label not in ("hard", "very_hard"):
                continue
            ex_id = str(item.get("exercise_id") or "").strip()
            ex_data = exercises_by_id.get(ex_id, {})
            lim = _check_exercise_limitation(ex_data, limitation_map)
            if lim and lim["severity"] == "monitor":
                limitation_suggestions.append({
                    "exercise_id": ex_id,
                    "zone": lim["zone"],
                    "current_severity": "monitor",
                    "suggested_severity": "active",
                    "reason": f"{label} feedback on exercise with {lim['zone']} contraindication",
                })
    # A295: pain 3/3 → suggest the limitation even when none is set yet.
    _pain_suggestion = limitation_suggestion_for_pain(req.log_entry, limitation_map or {})
    if _pain_suggestion is not None:
        limitation_suggestions.append(_pain_suggestion)

    # 7. Attach feedback to session completion log (B117)
    if target_date and target_sid:
        for entry in reversed(state.get("session_completion_log", [])):
            if entry.get("date") == target_date and entry.get("session_id") == target_sid:
                # A295: the session difficulty comes only from what was
                # rated, and only with ≥ 50 % fatigue-cost coverage — the same
                # value the feedback log gets. A resubmit without a rating
                # never erases a rated one.
                fb_items = (req.log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
                _difficulty = derive_session_difficulty(req.log_entry, exercises_by_id)
                if _difficulty is not None:
                    entry["difficulty"] = _difficulty
                _pain = sanitize_pain(req.log_entry.get("pain"))
                if _pain is not None:
                    entry["pain"] = _pain
                entry["exercise_count"] = len(fb_items)
                # Garmin/health-vault export (2026-08): persist the REAL wall-clock
                # start the guided player already measures. Until now the client
                # computed `now - startedAt` and sent only the delta
                # (session_duration_seconds), throwing the start timestamp away —
                # so the completion log had a real finish (`completed_at`) but no
                # real start. Only guided/timed players send `started_at`; a quick
                # "mark done" has no real start and the field stays absent rather
                # than being faked. `completed_at` (set at append) is the real
                # finish, mirrored here as `finished_at` when we have a real start
                # so the export reads one coherent (start, finish) pair.
                _started_at = req.log_entry.get("started_at")
                if _started_at and not entry.get("started_at"):
                    entry["started_at"] = str(_started_at)
                    if entry.get("completed_at") and not entry.get("finished_at"):
                        entry["finished_at"] = entry["completed_at"]
                duration = req.log_entry.get("session_duration_seconds")
                if duration is not None:
                    # B197 Bug 1: on resubmit, keep the longest duration seen.
                    # Frontend re-runs (e.g. after a /today render race) reset
                    # `startedAt` and submit tiny durations (~30s); without max()
                    # they clobber the real training duration.
                    prev = entry.get("session_duration_seconds")
                    entry["session_duration_seconds"] = (
                        max(prev, duration) if isinstance(prev, (int, float)) else duration
                    )
                break

    # 8. A194: Persist via persist_week_plan when we have a current plan —
    # this handles both state["current_week_plan"] and week_plans[start_key]
    # plus save_state in one call. Otherwise, just save_state directly.
    final_plan = state.get("current_week_plan")
    if final_plan:
        persist_week_plan(final_plan, state, user_id)
    else:
        save_state(state, user_id)

    response: dict = {"status": "ok"}
    if final_plan:
        response["week_plan"] = final_plan
    if limitation_suggestions:
        response["limitation_suggestions"] = limitation_suggestions
    if stale_exercise_warning:
        response["warning"] = stale_exercise_warning
    return response
