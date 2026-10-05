"""B371 — optimistic concurrency on the week plan.

Every endpoint that edits a week (``/api/replanner/events``, ``/override``,
``/quick-add``, ``/api/session/add-exercise``, ``/remove-exercise``,
``/surface-override``) receives the WHOLE ``week_plan`` from the client and
saves it. Before B371 nothing told an old copy from a fresh one: a phone that
had been asleep with Monday's plan could overwrite, with one tap, everything
another device (or a B369 regeneration) had written since.

Three pieces, one module:

- :func:`check_base_revision` — the client says which ``plan_revision`` it is
  editing (``base_revision``); a mismatch with the stored week raises
  :class:`StalePlanError` → **409** ``{detail, current_revision, week_start,
  week_plan}``. No ``base_revision`` at all is an installed PWA from before
  B371: the write is **accepted and logged** (refusing it would break every
  installed app until its service worker updates — the risk B371 closes is
  real but rare, a broken app for every user is certain).
- :func:`stamp_revision` — the one rule that makes the revision monotonic on
  every write path: the saved plan's revision is strictly greater than the
  stored one's. Called by ``persist_week_plan`` (every edit path) and by the
  GET regeneration.
- :func:`strip_derived` — what ``GET /api/week`` computes at read on a copy
  (B364 anchored loads of custom sessions, A141 process cues, the sibling
  alerts) must not come back in a client plan and be saved as if it were the
  plan. The stored version wins.

Two response-side helpers close the loop:

- :func:`read_view` — every write endpoint that returns a plan returns the
  same read-time view ``GET /api/week`` serves (the stored plan stays raw, the
  client's cache never loses the anchored loads of its customs after a tap);
- :func:`freeze_played_customs` — when a custom session goes done/skipped, the
  prescription the athlete actually saw (the read-time view of that moment) is
  what the history keeps, exactly as before B371 when the client sent it back.

Concurrency: :func:`serialized_by_user` serialises the write endpoints of one
user inside the process (one lock per user), so two writes in flight cannot
both pass the revision check against N and both save N+1. **Residual race**:
the lock is per process — with more than one uvicorn worker / replica, or for
writers that do not take it (``GET /api/week`` regeneration, ``PUT
/api/state``), a lost update is still possible in a narrow window. Production
runs one process today (``Procfile``); a conditional save on the stored
revision is the follow-up if that ever changes (B369-P6-residui).

Deterministic: no clock, no randomness — the revision is a counter.
"""
from __future__ import annotations

import functools
import logging
import threading
from copy import deepcopy
from typing import Any, Callable, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

REVISION_KEY = "plan_revision"

STALE_PLAN_DETAIL = "The plan was updated since you loaded it — reload it and try again."

#: Response siblings of ``week_plan`` (GET /api/week, replanner responses). A
#: client that spread a response into its plan would send them back — they are
#: never plan keys.
_SIBLING_KEYS = (
    "guard_warnings",
    "added_guard_warnings",
    "key_status",
    "key_conflicts",
    "retest_status",
    "test_reminder",
    "regeneration_failed",
    "past_week_unavailable",
    "dry_run",
)

#: Session fields computed at read (A141). Re-attached on every GET.
_SESSION_READ_KEYS = ("process_cue",)

_PLAYED = ("done", "skipped")


class StalePlanError(Exception):
    """The client edited an older revision of the week than the stored one."""

    def __init__(self, current_revision: int, week_start: Optional[str], current_plan: Optional[dict]):
        super().__init__(STALE_PLAN_DETAIL)
        self.current_revision = current_revision
        self.week_start = week_start
        self.current_plan = current_plan

    def payload(self) -> Dict[str, Any]:
        return {
            "detail": STALE_PLAN_DETAIL,
            "code": "stale_plan",
            "current_revision": self.current_revision,
            "week_start": self.week_start,
            # The stored plan, so a client can retry an idempotent action
            # without a second round trip (the retry's response is resolved).
            "week_plan": self.current_plan,
        }


def revision_of(plan: Optional[Mapping[str, Any]]) -> int:
    """The revision of *plan*; a plan from before B369 has none → 1 (the
    same default ``apply_events`` has always used)."""
    if not isinstance(plan, Mapping):
        return 0
    try:
        return max(1, int(plan.get(REVISION_KEY) or 1))
    except (TypeError, ValueError):
        return 1


def stored_plan_for(state: Mapping[str, Any], week_start: Optional[str]) -> Optional[dict]:
    """The stored plan of *week_start*: the per-week cache, else the legacy
    ``current_week_plan`` when it is that week. ``None`` when nothing is stored
    (hot state only — an archived past week cannot be edited concurrently in
    any way that matters, and reading the cold store on every write is not
    worth it)."""
    if not week_start:
        return None
    plan = (state.get("week_plans") or {}).get(week_start)
    if isinstance(plan, dict):
        return plan
    cwp = state.get("current_week_plan")
    if isinstance(cwp, dict) and cwp.get("start_date") == week_start:
        return cwp
    return None


def check_base_revision(
    state: Mapping[str, Any],
    client_plan: Optional[Mapping[str, Any]],
    base_revision: Optional[int],
    *,
    endpoint: str,
    user_id: Optional[str] = None,
) -> None:
    """Raise :class:`StalePlanError` when *base_revision* is not the stored
    week's revision. ``None`` (legacy client) is accepted and logged."""
    if not isinstance(client_plan, Mapping):
        return
    week_start = client_plan.get("start_date")
    if base_revision is None:
        logger.info(
            "B371: %s without base_revision (pre-B371 client) — accepted (user=%s week=%s)",
            endpoint, user_id, week_start,
        )
        return
    stored = stored_plan_for(state, week_start)
    if stored is None:
        return  # nothing stored to conflict with
    current = revision_of(stored)
    try:
        base = int(base_revision)
    except (TypeError, ValueError):
        base = -1
    if base != current:
        logger.warning(
            "B371: stale week plan on %s — client rev %s, stored rev %s (user=%s week=%s) → 409",
            endpoint, base_revision, current, user_id, week_start,
        )
        raise StalePlanError(current, week_start, deepcopy(stored))


def stamp_revision(updated: Dict[str, Any], stored: Optional[Mapping[str, Any]]) -> int:
    """Set ``updated[plan_revision]`` so it is strictly greater than the stored
    plan's, and never lower than what the edit already set (``apply_events``
    increments by itself). Returns the new revision."""
    own = revision_of(updated)
    if stored is None:
        new = own
    elif stored is updated:
        # The caller already wrote the plan into the cache (feedback): the
        # stored revision IS the edited one — one more step.
        new = own + 1
    else:
        new = max(revision_of(stored) + 1, own)
    updated[REVISION_KEY] = new
    return new


def _session_key(day_date: Any, session: Mapping[str, Any]) -> tuple:
    return (day_date, session.get("slot"), session.get("session_id"))


def _is_custom(session: Mapping[str, Any]) -> bool:
    return bool(session.get("is_custom") or str(session.get("session_id") or "").startswith("custom_"))


def strip_derived(client_plan: Optional[Dict[str, Any]], stored: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Remove from *client_plan*, in place, what GET /api/week computed at read.

    - response siblings (guard/key alerts…) and the ``_stale`` flag
      (``persist_week_plan`` re-derives it from the stored plan; a client
      cannot set or clear it);
    - A141 ``process_cue`` on sessions not yet played;
    - B364/A295/A298/A299/B370: the ``exercises`` of a not-yet-played custom
      session are replaced by the stored ones (the anchored loads, ladder
      doses, measures and limit targets of the day are a read-time view —
      saving them froze a load the athlete never set). A custom with no
      stored twin (an old client whose plan diverged) is left as sent.

    Done / skipped sessions are never touched (immutability). Returns the plan.
    """
    if not isinstance(client_plan, dict):
        return client_plan
    for k in _SIBLING_KEYS:
        client_plan.pop(k, None)
    client_plan.pop("_stale", None)

    stored_customs: Dict[tuple, list] = {}
    if isinstance(stored, Mapping):
        for wb in stored.get("weeks") or []:
            for d in wb.get("days") or []:
                for s in d.get("sessions") or []:
                    if isinstance(s, Mapping) and _is_custom(s) and s.get("status") not in _PLAYED:
                        stored_customs.setdefault(_session_key(d.get("date"), s), []).append(s)

    for wb in client_plan.get("weeks") or []:
        for d in wb.get("days") or []:
            for s in d.get("sessions") or []:
                if not isinstance(s, dict) or s.get("status") in _PLAYED:
                    continue
                for k in _SESSION_READ_KEYS:
                    s.pop(k, None)
                if not _is_custom(s):
                    continue
                twins = stored_customs.get(_session_key(d.get("date"), s))
                if not twins:
                    continue
                twin = twins.pop(0)
                if "exercises" in twin:
                    s["exercises"] = deepcopy(twin["exercises"])
                else:
                    s.pop("exercises", None)
    return client_plan


def guard_client_plan(
    state: Mapping[str, Any],
    client_plan: Optional[Dict[str, Any]],
    base_revision: Optional[int],
    *,
    endpoint: str,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """The two input steps of every write endpoint that receives a client
    plan: revision check (may raise :class:`StalePlanError`), then
    :func:`strip_derived` against the stored week."""
    check_base_revision(state, client_plan, base_revision, endpoint=endpoint, user_id=user_id)
    if isinstance(client_plan, dict):
        strip_derived(client_plan, stored_plan_for(state, client_plan.get("start_date")))
    return client_plan


# --------------------------------------------------------------------------- #
# Response side
# --------------------------------------------------------------------------- #

def read_view(plan: Optional[Dict[str, Any]], state: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The plan as ``GET /api/week`` serves it: a COPY where every not-yet-played
    custom session carries the read-time values of its day (B364 anchored
    loads, A298 ladder doses, A295 measures, A299 limit targets, B370 rest
    default), plus a ``plan_revision`` the client can send back. The stored
    plan is untouched. Done/skipped sessions are returned as stored."""
    if not isinstance(plan, dict):
        return plan
    from backend.api.routers.week import _with_custom_anchored_loads

    try:
        out = _with_custom_anchored_loads(plan, dict(state))
    except Exception:
        # A read-time view must never fail a write that already succeeded.
        logger.warning("B371: read_view failed — returning the stored plan", exc_info=True)
        out = deepcopy(plan)
    out.setdefault(REVISION_KEY, 1)
    return out


def freeze_played_customs(
    after: Optional[Dict[str, Any]],
    before: Optional[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> int:
    """Custom sessions pending in *before* and done/skipped in *after* keep, in
    *after*, the exercises of the read-time view of *before* — the prescription
    the athlete saw when they played it (GET never re-derives a played
    session, so this is the only moment to record it). Matched on (date, slot,
    session_id); a session moved and marked in the same call keeps its raw
    rows. Returns how many were frozen."""
    if not isinstance(after, dict) or not isinstance(before, Mapping):
        return 0
    pending: Dict[tuple, int] = {}
    for wb in before.get("weeks") or []:
        for d in wb.get("days") or []:
            for s in d.get("sessions") or []:
                if isinstance(s, Mapping) and _is_custom(s) and s.get("status") not in _PLAYED and s.get("exercises"):
                    k = _session_key(d.get("date"), s)
                    pending[k] = pending.get(k, 0) + 1
    if not pending:
        return 0
    targets = []
    for wb in after.get("weeks") or []:
        for d in wb.get("days") or []:
            for s in d.get("sessions") or []:
                if not (isinstance(s, dict) and _is_custom(s) and s.get("status") in _PLAYED):
                    continue
                k = _session_key(d.get("date"), s)
                if pending.get(k):
                    targets.append((k, s))
    if not targets:
        return 0
    view = read_view(dict(before), state) or {}
    shown: Dict[tuple, list] = {}
    for wb in view.get("weeks") or []:
        for d in wb.get("days") or []:
            for s in d.get("sessions") or []:
                if isinstance(s, Mapping) and _is_custom(s) and s.get("status") not in _PLAYED and s.get("exercises"):
                    shown.setdefault(_session_key(d.get("date"), s), []).append(s)
    n = 0
    for k, s in targets:
        twins = shown.get(k)
        if not twins:
            continue
        s["exercises"] = deepcopy(twins.pop(0)["exercises"])
        n += 1
    return n


# --------------------------------------------------------------------------- #
# Per-user serialisation of the write endpoints
# --------------------------------------------------------------------------- #

_LOCKS_GUARD = threading.Lock()
_USER_LOCKS: Dict[str, threading.RLock] = {}


def user_write_lock(user_id: Optional[str]) -> threading.RLock:
    """The (re-entrant) lock of *user_id*'s writes in this process."""
    key = str(user_id or "")
    with _LOCKS_GUARD:
        lock = _USER_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _USER_LOCKS[key] = lock
        return lock


def serialized_by_user(fn: Callable) -> Callable:
    """Decorator for a sync endpoint taking ``user_id`` as a keyword (FastAPI
    always passes dependencies by keyword): load → check revision → apply →
    save runs under the user's lock, so the check and the save are atomic with
    respect to the other locked writers of that user in this process."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with user_write_lock(kwargs.get("user_id")):
            return fn(*args, **kwargs)

    return wrapper
