"""A301 — the recovery guards as ALERTS: what a week plan, as it stands,
breaks. Nothing is rewritten.

Why this exists: until A301 every user action (quick-add, override, move,
custom / generated / planned session, change of gym, feedback, outdoor day)
ended with the replanner "fixing" the week — the reconcile downshifted the
engine's sessions next to the user's one, the ripples eased the following
days, ``_compensate_finger`` swapped a lunch for a hangboard session, the
neighbour guard downshifted the user's own session. Daniele's decision
(2026-10-05): "se voglio fare sovrallenamento lo faccio, decisione mia, tu
solo segnala alert". After a user action nothing moves; this module says
what the guards would have objected to.

Contract — pure and deterministic:

- ``evaluate(plan, prev_days=None, today=None, state=None)`` → a list of
  warnings, JSON-serialisable, in a stable order. Nothing is mutated, there is
  no clock (``today`` is always passed by the caller — the client-local day)
  and no I/O beyond the static catalogs the shared predicates already read.
- Computed at read time (``GET /api/week``, every replanner response) as a
  SIBLING of ``week_plan``, like ``key_status``: never stored in the plan.
- Only sessions that can still change are flagged: not done, not skipped, and
  not before ``today``. What already happened is history; it still COUNTS
  (a finger session done on Monday makes a Tuesday finger session a warning).

Codes (one warning per flagged session):

- ``finger_gap`` — a session tagged ``finger`` within the replanner's own
  spacing (``ceil(recovery_multiplier)`` days, i.e. the 48 h finger gap) of an
  earlier finger day. The rule ``_enforce_no_consecutive_finger`` enforced;
  the previous week's trailing days (``prev_days``) seed it.
- ``finger_test_72h`` — a finger-hard session (``stimulus.is_finger_hard_session``)
  within ``athlete_context.RETEST_BLOCK_H`` (72 h) before a finger max test.
- ``heavy_pull_7d`` — more than ``athlete_context.HEAVY_PULL_MAX_PER_7D``
  heavy-pull days (≥ 85 % 1RM weighted pulls, A294 definition) in a rolling
  7-day window.
- ``hiit_near_max`` — a HIIT session (``stimulus.is_hiit_like``) on the day of,
  or the day before, a max day (finger-hard, or pulling + hard) — the
  ``athlete_context`` ``hiit_ok`` rule.
- ``hard_cap`` — the week holds more hard days than its cap
  (``_counts_as_hard``: done counts, skipped does not). Flagged on the days
  past the cap, the ones ``_enforce_caps`` would downshift.
- ``pre_trip`` — a hard session on a pre-trip no-hard day
  (``macrocycle_v1.compute_taper_windows``, A281).
- ``post_outdoor`` — a hard or finger session the day after an outdoor day
  that counts (B372, ``stimulus.outdoor_fatigue_days``: planned, logged hard,
  load at/above ``OUTDOOR_RIPPLE_THRESHOLD``, or completed with no route log).
  Before B372 only a completed day whose load reached the threshold counted —
  and in 37 real sessions the load never did.
- ``hard_back_to_back`` — a hard session the day after a hard day, when at
  least one of the two is the user's (quick-add, override, custom, moved…):
  the old quick-add / override day+1 ripple and B366's "back-to-back hard
  days" warning, now an alert. A pair the planner made on its own is not
  flagged (the planner's spacing is its own business).

HIIT is not hard (C274 / A300: it never consumes the hard-day or finger cap),
so it never appears under ``hard_cap`` / ``pre_trip``.

Outdoor days (B372). An outdoor day that counts (``stimulus.outdoor_fatigue_days``)
is a hard, finger-loading day for every guard: ``finger_gap`` (both ways — the
session before a crag day is flagged too, since the crag day itself carries no
session to flag; the day right after is ``post_outdoor``'s), ``finger_test_72h``
(a crag day within 72 h before a finger test flags the test), ``hiit_near_max``
(HIIT on, or the day before, a crag day), ``hard_cap`` (the crag day is one of
the week's hard days) and ``post_outdoor``. An outdoor day is never flagged
itself — it has no session — it appears in ``with`` as
``{date, slot: None, session_id: None}``, and the warning names it in
``outdoor`` (``{date, reason, spot, load}``). Nothing is rewritten.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from backend.engine.stimulus import (
    is_finger_hard_session,
    is_hiit_like,
    is_test_session,
    session_flag,
)

VERSION = "b372.1"

CODE_FINGER_GAP = "finger_gap"
CODE_FINGER_TEST = "finger_test_72h"
CODE_HEAVY_PULL = "heavy_pull_7d"
CODE_HIIT_NEAR_MAX = "hiit_near_max"
CODE_HARD_CAP = "hard_cap"
CODE_PRE_TRIP = "pre_trip"
CODE_POST_OUTDOOR = "post_outdoor"
CODE_HARD_BACK_TO_BACK = "hard_back_to_back"

CODES = (
    CODE_FINGER_GAP, CODE_FINGER_TEST, CODE_HEAVY_PULL, CODE_HIIT_NEAR_MAX,
    CODE_HARD_CAP, CODE_PRE_TRIP, CODE_POST_OUTDOOR, CODE_HARD_BACK_TO_BACK,
)

#: Codes whose ``with`` lists every other day of a weekly / rolling count:
#: adding a session elsewhere changes ``with`` without changing the alert.
_COUNT_CODES = (CODE_HARD_CAP, CODE_HEAVY_PULL)

_SLOTS = ("morning", "lunch", "evening")


def _slot_index(slot: Any) -> int:
    return _SLOTS.index(slot) if slot in _SLOTS else len(_SLOTS)


def _parse(value: Any) -> Optional[date]:
    try:
        return datetime.strptime(str(value or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _ref(d: str, s: Mapping[str, Any]) -> Dict[str, Any]:
    return {"date": d, "slot": s.get("slot"), "session_id": s.get("session_id")}


def _days_of(plan: Optional[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []
    for wk in (plan or {}).get("weeks") or []:
        for day in (wk or {}).get("days") or []:
            if isinstance(day, Mapping) and _parse(day.get("date")) is not None:
                out.append(day)
    return out


def _live(s: Mapping[str, Any]) -> bool:
    """Counts for the guards: everything but a skipped session (a skip stub
    never happened)."""
    return isinstance(s, Mapping) and s.get("status") != "skipped"


class _Timeline:
    """The previous week's trailing days + the plan's days, by date."""

    def __init__(self, plan: Mapping[str, Any], prev_days: Optional[Sequence[Mapping[str, Any]]],
                 state: Optional[Mapping[str, Any]] = None,
                 outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
                 outdoor_load_threshold: Optional[float] = None):
        self.by_date: Dict[str, List[Mapping[str, Any]]] = {}
        self.day_by_date: Dict[str, Mapping[str, Any]] = {}
        self.plan_dates: List[str] = []
        for day in list(prev_days or []):
            if not isinstance(day, Mapping) or _parse(day.get("date")) is None:
                continue
            d = str(day["date"])[:10]
            self.day_by_date.setdefault(d, day)
            self.by_date.setdefault(d, []).extend(
                s for s in day.get("sessions") or [] if _live(s))
        for day in _days_of(plan):
            d = str(day["date"])[:10]
            # The plan wins over a stale copy of the same date in prev_days.
            self.day_by_date[d] = day
            self.by_date[d] = [s for s in day.get("sessions") or [] if _live(s)]
            self.plan_dates.append(d)
        self.plan_dates = sorted(set(self.plan_dates))
        # B372: the outdoor days that count as hard, finger-loading days.
        self.outdoor: Dict[str, Dict[str, Any]] = {}
        if outdoor_load_threshold is not None and self.day_by_date:
            from backend.engine.stimulus import outdoor_fatigue_days

            dates = sorted(self.day_by_date)
            self.outdoor = outdoor_fatigue_days(
                state or {}, [self.day_by_date[d] for d in dates],
                load_threshold=outdoor_load_threshold, outdoor_rows=outdoor_rows,
                since=dates[0], until=dates[-1])

    def outdoor_on(self, d: date) -> Optional[Dict[str, Any]]:
        return self.outdoor.get(d.isoformat())

    def on(self, d: date) -> List[Mapping[str, Any]]:
        return self.by_date.get(d.isoformat(), [])


class _Emitter:
    def __init__(self, plan_dates: Iterable[str], today: Optional[str]):
        self.plan_dates = set(plan_dates)
        self.today = str(today)[:10] if today else None
        self.out: List[Dict[str, Any]] = []
        self._seen: set = set()

    def flaggable(self, d: str, s: Mapping[str, Any]) -> bool:
        if d not in self.plan_dates:
            return False
        if s.get("status") in ("done", "skipped"):
            return False
        return not (self.today and d < self.today)

    def emit(self, code: str, d: str, s: Mapping[str, Any], with_: Sequence[Dict[str, Any]],
             message: str, **extra: Any) -> None:
        from backend.engine.user_owned import is_user_owned

        with_sorted = sorted(
            ({"date": w["date"], "slot": w.get("slot"), "session_id": w.get("session_id")} for w in with_),
            key=lambda w: (w["date"], _slot_index(w.get("slot")), str(w.get("session_id") or "")),
        )
        key = (code, d, s.get("slot"), s.get("session_id"),
               tuple((w["date"], w.get("slot"), w.get("session_id")) for w in with_sorted))
        if key in self._seen:
            return
        self._seen.add(key)
        self.out.append({
            "code": code,
            "severity": "warning",
            "date": d,
            "slot": s.get("slot"),
            "session_id": s.get("session_id"),
            "name": s.get("name"),
            "user_owned": bool(is_user_owned(s)),
            "with": with_sorted,
            "message": message,
            **extra,
        })


def _label(s: Mapping[str, Any]) -> str:
    return str(s.get("name") or s.get("session_id") or "session")


def _outdoor_ref(d: str) -> Dict[str, Any]:
    return {"date": d, "slot": None, "session_id": None}


def _outdoor_label(o: Mapping[str, Any], capital: bool = False) -> str:
    where = f" at {o['spot']}" if o.get("spot") else ""
    return f"{'The' if capital else 'the'} outdoor day{where} on {o['date']}"


_OUTDOOR_WHY = {
    "outdoor_planned": "planned",
    "outdoor_hard": "logged hard",
    "outdoor_load": "big load",
    "outdoor_unlogged": "no route log",
}


def _outdoor_info(o: Mapping[str, Any]) -> Dict[str, Any]:
    return {"date": o["date"], "reason": o.get("reason"), "spot": o.get("spot"), "load": o.get("load")}


def _finger_gap(tl: _Timeline, em: _Emitter, gap: int) -> None:
    for d_iso in tl.plan_dates:
        d = _parse(d_iso)
        here = [s for s in tl.on(d) if session_flag(s, "finger")]
        if not here:
            continue
        before: List[Dict[str, Any]] = []
        for k in range(1, gap + 1):
            prev = d - timedelta(days=k)
            before.extend(_ref(prev.isoformat(), x) for x in tl.on(prev) if session_flag(x, "finger"))
        if before:
            for s in here:
                if not em.flaggable(d_iso, s):
                    continue
                em.emit(CODE_FINGER_GAP, d_iso, s, before,
                        f"{_label(s)} on {d_iso} loads the fingers within {gap} day(s) of "
                        f"{before[0]['session_id']} on {before[0]['date']}: the finger gap asks for "
                        f"{24 * (gap + 1)} h between them.",
                        gap_days=gap)
        # B372: an outdoor day on either side. The day right after a crag day
        # is ``post_outdoor``'s (one alert per pair, not two).
        for k in range(-gap, gap + 1):
            if k in (0, 1):
                continue
            o = tl.outdoor_on(d - timedelta(days=k))
            if o is None:
                continue
            for s in here:
                if not em.flaggable(d_iso, s):
                    continue
                side = "before" if k < 0 else "of"
                em.emit(CODE_FINGER_GAP, d_iso, s, [_outdoor_ref(o["date"])],
                        f"{_label(s)} on {d_iso} loads the fingers within {gap} day(s) {side} "
                        f"{_outdoor_label(o)} ({_OUTDOOR_WHY.get(o.get('reason'), 'outdoor')}): "
                        f"the finger gap asks for {24 * (gap + 1)} h between them.",
                        gap_days=gap, outdoor=_outdoor_info(o))


def _is_finger_test(s: Mapping[str, Any]) -> bool:
    return is_test_session(s) and session_flag(s, "finger")


def _finger_test(tl: _Timeline, em: _Emitter, block_days: int) -> None:
    for t_iso in sorted(tl.by_date):
        td = _parse(t_iso)
        for t in tl.on(td):
            if not _is_finger_test(t) or t.get("status") == "done":
                continue
            for k in range(0, block_days + 1):
                sd = td - timedelta(days=k)
                for s in tl.on(sd):
                    if s is t or is_test_session(s) or not is_finger_hard_session(s):
                        continue
                    if k == 0 and _slot_index(s.get("slot")) >= _slot_index(t.get("slot")):
                        continue  # same day, after (or with) the test
                    s_iso = sd.isoformat()
                    msg = (f"{_label(s)} on {s_iso} loads the fingers hard within "
                           f"{block_days * 24} h before the {t.get('session_id')} on {t_iso}: "
                           "the test would measure fatigue.")
                    if em.flaggable(s_iso, s):
                        em.emit(CODE_FINGER_TEST, s_iso, s, [_ref(t_iso, t)], msg)
                    elif em.flaggable(t_iso, t):
                        em.emit(CODE_FINGER_TEST, t_iso, t, [_ref(s_iso, s)], msg)
            # B372: a crag day within the block before the test (the same day
            # included: the crag day starts in the morning). The crag day has
            # no session to flag: the test is flagged.
            if not em.flaggable(t_iso, t):
                continue
            for k in range(0, block_days + 1):
                o = tl.outdoor_on(td - timedelta(days=k))
                if o is None:
                    continue
                em.emit(CODE_FINGER_TEST, t_iso, t, [_outdoor_ref(o["date"])],
                        f"{_outdoor_label(o, capital=True)} loads the fingers within {block_days * 24} h before the "
                        f"{t.get('session_id')} on {t_iso}: the test would measure fatigue.",
                        outdoor=_outdoor_info(o))


def _heavy_pull(tl: _Timeline, em: _Emitter, state: Mapping[str, Any], max_per_7d: int) -> None:
    from backend.engine.key_sessions_v1 import _is_heavy_pull

    heavy: Dict[str, List[Mapping[str, Any]]] = {}
    for d_iso in sorted(tl.by_date):
        hs = [s for s in tl.by_date[d_iso] if _is_heavy_pull(state, s, d_iso)]
        if hs:
            heavy[d_iso] = hs
    for d_iso in tl.plan_dates:
        if d_iso not in heavy:
            continue
        d = _parse(d_iso)
        lo = (d - timedelta(days=6)).isoformat()
        window = sorted(x for x in heavy if lo <= x <= d_iso)
        if len(window) <= max_per_7d:
            continue
        others = [_ref(x, s) for x in window if x != d_iso for s in heavy[x]]
        for s in heavy[d_iso]:
            if not em.flaggable(d_iso, s):
                continue
            em.emit(CODE_HEAVY_PULL, d_iso, s, others,
                    f"{_label(s)} on {d_iso} is heavy pulling day {len(window)} in 7 days "
                    f"(the limit is {max_per_7d}).",
                    count=len(window), limit=max_per_7d)


def _is_max(s: Mapping[str, Any]) -> bool:
    return is_finger_hard_session(s) or (session_flag(s, "pulling") and session_flag(s, "hard"))


def _hiit_near_max(tl: _Timeline, em: _Emitter) -> None:
    for d_iso in tl.plan_dates:
        d = _parse(d_iso)
        for h in tl.on(d):
            if not is_hiit_like(h):
                continue
            maxes = [_ref(x.isoformat(), s) for x in (d, d + timedelta(days=1))
                     for s in tl.on(x) if s is not h and not is_hiit_like(s) and _is_max(s)]
            # B372: a crag day is a max day for HIIT (as in complementary_v1).
            crag = [o for o in (tl.outdoor_on(x) for x in (d, d + timedelta(days=1))) if o]
            if not maxes and not crag:
                continue
            if maxes:
                msg = (f"{_label(h)} on {d_iso} is HIIT on the day of, or the day before, a max session "
                       f"({maxes[0]['session_id']} on {maxes[0]['date']}).")
            else:
                msg = f"{_label(h)} on {d_iso} is HIIT on the day of, or the day before, {_outdoor_label(crag[0])}."
            extra = {"outdoor": _outdoor_info(crag[0])} if crag else {}
            if em.flaggable(d_iso, h):
                em.emit(CODE_HIIT_NEAR_MAX, d_iso, h, maxes + [_outdoor_ref(o["date"]) for o in crag], msg, **extra)
            else:
                for m in maxes:
                    ms = next((s for s in tl.by_date.get(m["date"], [])
                               if s.get("slot") == m["slot"] and s.get("session_id") == m["session_id"]), None)
                    if ms is not None and em.flaggable(m["date"], ms):
                        em.emit(CODE_HIIT_NEAR_MAX, m["date"], ms, [_ref(d_iso, h)], msg)


def _hard_cap(plan: Mapping[str, Any], em: _Emitter, outdoor: Optional[Mapping[str, Any]] = None) -> None:
    from backend.engine.replanner_v1 import _counts_as_hard, _safe_hard_cap

    outdoor = outdoor or {}
    snapshot = plan.get("profile_snapshot") or {}
    cap = _safe_hard_cap(snapshot)
    # B372: a counted outdoor day is one of the week's hard days.
    hard_days = [day for day in _days_of(plan)
                 if any(_counts_as_hard(s) for s in day.get("sessions") or [])
                 or str(day["date"])[:10] in outdoor]
    if len(hard_days) <= cap:
        return
    all_refs = [_ref(str(day["date"])[:10], s) for day in hard_days
                for s in day.get("sessions") or [] if _counts_as_hard(s)]
    all_refs += [_outdoor_ref(str(day["date"])[:10]) for day in hard_days
                 if str(day["date"])[:10] in outdoor]
    for day in hard_days[cap:]:
        d_iso = str(day["date"])[:10]
        for s in day.get("sessions") or []:
            if not _counts_as_hard(s) or not em.flaggable(d_iso, s):
                continue
            em.emit(CODE_HARD_CAP, d_iso, s, [r for r in all_refs if r["date"] != d_iso],
                    f"The week has {len(hard_days)} hard days, the cap is {cap}: "
                    f"{_label(s)} on {d_iso} is past it.",
                    count=len(hard_days), cap=cap)


def _pre_trip(plan: Mapping[str, Any], em: _Emitter, state: Mapping[str, Any]) -> None:
    trips = state.get("trips") or []
    days = _days_of(plan)
    if not trips or not days:
        return
    from backend.engine.macrocycle_v1 import compute_taper_windows

    ws = str(days[0]["date"])[:10]
    we = str(days[-1]["date"])[:10]
    try:
        no_hard = set(compute_taper_windows(trips, ws, we).get("no_hard") or [])
    except Exception:  # an alert never breaks the response
        return
    for day in days:
        d_iso = str(day["date"])[:10]
        if d_iso not in no_hard:
            continue
        for s in day.get("sessions") or []:
            if _live(s) and session_flag(s, "hard") and em.flaggable(d_iso, s):
                em.emit(CODE_PRE_TRIP, d_iso, s, [],
                        f"{_label(s)} on {d_iso} is a hard session in the days before a trip.")


def _post_outdoor(tl: _Timeline, em: _Emitter) -> None:
    """B372: every outdoor day that counts (``tl.outdoor``), not only a
    completed one past the load threshold."""
    for d_iso in tl.plan_dates:
        o = tl.outdoor_on(_parse(d_iso) - timedelta(days=1))
        if o is None:
            continue
        prev = o["date"]
        why = _OUTDOOR_WHY.get(o.get("reason"), "outdoor")
        if o.get("reason") == "outdoor_load" and o.get("load") is not None:
            why = f"load {o['load']}"
        elif o.get("reason") == "outdoor_hard" and o.get("grade"):
            why = f"logged hard, {o['grade']}"
        for s in tl.by_date.get(d_iso, []):
            if not (session_flag(s, "hard") or session_flag(s, "finger")) or not em.flaggable(d_iso, s):
                continue
            em.emit(CODE_POST_OUTDOOR, d_iso, s, [_outdoor_ref(prev)],
                    f"{_label(s)} on {d_iso} follows {_outdoor_label(o)} ({why}).",
                    outdoor_load=o.get("load"), outdoor=_outdoor_info(o))


def _is_hard(s: Mapping[str, Any]) -> bool:
    # HIIT is never hard (C274 / A300).
    return session_flag(s, "hard") and not is_hiit_like(s)


def _hard_back_to_back(tl: _Timeline, em: _Emitter) -> None:
    from backend.engine.user_owned import is_user_owned

    for d_iso in tl.plan_dates:
        d = _parse(d_iso)
        prev = (d - timedelta(days=1)).isoformat()
        earlier = [s for s in tl.by_date.get(prev, []) if _is_hard(s)]
        if not earlier:
            continue
        for s in tl.on(d):
            if not _is_hard(s):
                continue
            pair = [e for e in earlier if is_user_owned(s) or is_user_owned(e)]
            if not pair:
                continue
            msg = (f"{_label(s)} on {d_iso} is a hard session the day after "
                   f"{_label(pair[0])} on {prev}: back-to-back hard days.")
            if em.flaggable(d_iso, s):
                em.emit(CODE_HARD_BACK_TO_BACK, d_iso, s, [_ref(prev, e) for e in pair], msg)
            else:
                for e in pair:
                    if em.flaggable(prev, e):
                        em.emit(CODE_HARD_BACK_TO_BACK, prev, e, [_ref(d_iso, s)], msg)


def evaluate(
    plan: Optional[Mapping[str, Any]],
    prev_days: Optional[Sequence[Mapping[str, Any]]] = None,
    today: Optional[str] = None,
    state: Optional[Mapping[str, Any]] = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """What the guards object to in *plan* — alerts only, see the module doc.

    *prev_days*: the previous week's days (cross-week finger gap, heavy-pull
    window, a big outdoor Sunday). *today*: ISO client-local day — days before
    it are not flagged (``None`` flags every pending session). *state*: the
    user state, for the heavy-pull load reading (official 1RM, working loads)
    and the trips; ``None`` reads the labels only and skips ``pre_trip``.
    *outdoor_rows*: the ``outdoor_logs`` rows of the window (B372) — the route
    log that tells a hard crag day from an easy one; ``None`` reads
    ``state.outdoor_log`` only (a completed day without routes then counts).
    """
    if not isinstance(plan, Mapping) or not _days_of(plan):
        return []
    from backend.engine.athlete_context import HEAVY_PULL_MAX_PER_7D, RETEST_BLOCK_H
    from backend.engine.replanner_v1 import OUTDOOR_RIPPLE_THRESHOLD, _recovery_gap

    st: Mapping[str, Any] = state if isinstance(state, Mapping) else {}
    tl = _Timeline(plan, prev_days, st, outdoor_rows, OUTDOOR_RIPPLE_THRESHOLD)
    em = _Emitter(tl.plan_dates, today)
    gap = max(1, int(_recovery_gap(dict(plan))))

    _finger_gap(tl, em, gap)
    _finger_test(tl, em, RETEST_BLOCK_H // 24)
    _heavy_pull(tl, em, st, HEAVY_PULL_MAX_PER_7D)
    _hiit_near_max(tl, em)
    _hard_cap(plan, em, tl.outdoor)
    if st:
        _pre_trip(plan, em, st)
    _post_outdoor(tl, em)
    _hard_back_to_back(tl, em)

    order = {c: i for i, c in enumerate(CODES)}
    return sorted(em.out, key=lambda w: (w["date"], _slot_index(w.get("slot")),
                                         order.get(w["code"], 99), str(w.get("session_id") or "")))


def involves(warning: Mapping[str, Any], date_iso: str, slot: Optional[str] = None) -> bool:
    """Does *warning* name the session at ``date_iso`` (/``slot``) — flagged
    or as the other side (``with``)?"""
    def hit(d: Any, s: Any) -> bool:
        return str(d) == str(date_iso) and (slot is None or s is None or s == slot)

    if hit(warning.get("date"), warning.get("slot")):
        return True
    return any(hit(w.get("date"), w.get("slot")) for w in warning.get("with") or [])


def new_warnings(before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
                 ) -> List[Dict[str, Any]]:
    """The warnings of *after* that *before* did not have (same code, flagged
    session and other side). ``hard_cap`` / ``heavy_pull_7d`` are keyed on the
    flagged session only: their ``with`` is every other counted day, so an
    addition elsewhere would make every existing one look new."""
    def key(w: Mapping[str, Any]) -> Tuple:
        head = (w.get("code"), w.get("date"), w.get("slot"), w.get("session_id"))
        if w.get("code") in _COUNT_CODES:
            return head
        return head + (tuple((x.get("date"), x.get("slot"), x.get("session_id"))
                             for x in w.get("with") or []),)

    seen = {key(w) for w in before}
    return [dict(w) for w in after if key(w) not in seen]


__all__ = ["CODES", "VERSION", "evaluate", "involves", "new_warnings"]
