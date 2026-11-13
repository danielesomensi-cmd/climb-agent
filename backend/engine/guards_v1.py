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

- ``finger_gap`` — a finger-HIGH session (A327: ``stimulus.finger_load_of``)
  within the replanner's own spacing (``ceil(recovery_multiplier)`` days, i.e.
  the 48 h finger gap) of an earlier finger-high day. The rule
  ``_enforce_no_consecutive_finger`` enforced; the previous week's trailing
  days (``prev_days``) seed it. A327: high–high only, the calendar rule as
  before; a low session is ``finger_low_gap``'s.
- ``finger_low_gap`` (A327, D288 R1) — a finger session less than
  ``retest_policy.FINGER_LOW_GAP_H`` (6 h) × ``recovery_multiplier`` from
  another one when at least one of the two is LOW (low–high either way,
  low–low), on the ``complementary_v1.SLOT_HOUR`` clock (no slot = 19:00; a
  crag day that counts is high from 08:00 to 18:00) — the later one is
  flagged; or a low session past ``FINGER_LOW_MAX_PER_DAY`` (2) on its day.
  With three slots only morning + lunch (5 h) breaks it; lunch → evening (6 h)
  is fine. ``detail`` ∈ ``gap`` | ``per_day``, ``gap_h``, ``low_count``.
- ``finger_test_72h`` — a finger-hard session (``stimulus.is_finger_hard_session``)
  within ``athlete_context.RETEST_BLOCK_H`` (72 h) before a finger max test.
- ``heavy_pull_7d`` — more than ``athlete_context.HEAVY_PULL_MAX_PER_7D``
  heavy-pull days (≥ 85 % 1RM weighted pulls, A294 definition) in a rolling
  7-day window.
- ``hiit_near_max`` — a HIIT session (``stimulus.is_hiit_like``) less than 24 h
  before a max session (``stimulus.is_max_for_hiit``: finger-hard or pulling
  max — power endurance is not one) or on / within 24 h before a crag day
  (B405, ``complementary_v1.hiit_too_close``) — the ``athlete_context``
  ``hiit_ok`` rule.
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

- ``finger_hard_cap`` (A327, D288 R1) — the week holds more finger-hard days
  than ``retest_policy.FINGER_HARD_WEEKLY_MAX`` (3): the finger-hard
  exposures (``stimulus.is_finger_hard_exposure``: max / test hangs, limit /
  board / campus, ``three_attempt_comp``, indoor redpoint attempts; a planned
  catalog slot by its finger + hard flags) plus the crag days that count
  (B372). Repeaters at 60-80 % are not in it (Daniele, answer 2).
  Flagged like ``hard_cap``: the latest finger-hard sessions past the cap (a
  crag day has no session to flag); ``count``, ``cap``.
- ``max_hang_cap`` (A327, D288 R1) — more than
  ``retest_policy.MAX_HANG_WEEKLY_MAX`` (2) max-hang days in the week
  (``stimulus.is_max_hang_session``: the finger_max family, tests included);
  the latest ones past the cap are flagged; ``count``, ``cap``.
- ``crag_block`` (A327, D288 R2) — after a run of at least
  ``retest_policy.CRAG_BLOCK_MIN_DAYS`` (2) consecutive crag days that count
  (B372 ``outdoor_fatigue_days``, the same reading as every outdoor alert;
  across the week boundary): the day after the last one (c+1) is a true rest
  day (``is_rest_day_session``: a complementary lunch, HIIT and legs included,
  or recovery / prehab do not break it — Daniele, decision 2); the day after
  (c+2) holds no hard session; no finger session starts before
  ``CRAG_BLOCK_FINGER_H`` (72 h) after the last crag day ends
  (``complementary_v1.OUTDOOR_END_HOUR``, 18:00): after a Saturday-Sunday
  block, Wednesday evening is fine, Wednesday lunch is not. One alert per
  session, ``detail`` ∈ ``rest_day`` | ``no_hard`` | ``finger_72h`` (in that
  order of precedence), ``crag_days``, ``finger_ok_from``. ``post_outdoor``
  leaves c+1 to it. Alert only: after a crag weekend the following week is
  never regenerated nor rewritten (Daniele, answer 3).

- ``low_rest_days`` (A305) — WEEK-level: fewer than ``MIN_REST_DAYS`` true
  rest days in the week (a day with only a complementary lunch or recovery /
  prehab counts as rest; an outdoor or other-sport day does not). One warning,
  ``scope: "week"``, dated on the week's first day, ``slot`` / ``session_id``
  None, ``rest_days`` / ``rest_dates`` attached. Planner-generated weeks carry
  it too: the planner fills the days the athlete declared, this only says it.
  Returned only by ``evaluate(..., include_week=True)`` / ``evaluate_week``
  (API: ``week_guard_warnings``), never in the session-level list.

HIIT is not hard (C274 / A300: it never consumes the hard-day or finger cap),
so it never appears under ``hard_cap`` / ``pre_trip``.

Outdoor days (B372). An outdoor day that counts (``stimulus.outdoor_fatigue_days``)
is a hard, finger-loading day for every guard: ``finger_gap`` (both ways — the
session before a crag day is flagged too, since the crag day itself carries no
session to flag; the day right after is ``post_outdoor``'s), ``finger_test_72h``
(a crag day within 72 h before a finger test flags the test; the test the day
after is ``post_outdoor``'s), ``hiit_near_max`` (HIIT on, or within 24 h before, a
crag day), ``hard_cap`` (the crag day is one of the week's hard days; when it
is past the cap the latest hard session is flagged), ``hard_back_to_back`` (a
hard non-finger session the day before a crag day) and ``post_outdoor``. A
declared crag day on the next week's Monday is read through ``next_days``. The
planner's bare ``outdoor_slot`` is availability, not a crag day (it counts only
through its route log / load), so planner-generated weeks get no outdoor alert. An outdoor day is never flagged
itself — it has no session — it appears in ``with`` as
``{date, slot: None, session_id: None}``, and the warning names it in
``outdoor`` (``{date, reason, spot, load}``). Nothing is rewritten.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from backend.engine.stimulus import (
    FINGER_LOAD_LOW,
    finger_load_of,
    is_finger_hard_exposure,
    is_finger_hard_session,
    is_finger_high,
    is_hiit_like,
    is_max_for_hiit,
    is_max_hang_session,
    is_test_session,
    session_flag,
)

VERSION = "a327.1"

CODE_FINGER_GAP = "finger_gap"
CODE_FINGER_LOW_GAP = "finger_low_gap"
CODE_FINGER_TEST = "finger_test_72h"
CODE_HEAVY_PULL = "heavy_pull_7d"
CODE_HIIT_NEAR_MAX = "hiit_near_max"
CODE_HARD_CAP = "hard_cap"
CODE_PRE_TRIP = "pre_trip"
CODE_POST_OUTDOOR = "post_outdoor"
CODE_HARD_BACK_TO_BACK = "hard_back_to_back"
CODE_LOW_REST_DAYS = "low_rest_days"
CODE_FINGER_HARD_CAP = "finger_hard_cap"
CODE_MAX_HANG_CAP = "max_hang_cap"
CODE_CRAG_BLOCK = "crag_block"

CODES = (
    CODE_FINGER_GAP, CODE_FINGER_LOW_GAP, CODE_FINGER_TEST, CODE_HEAVY_PULL, CODE_HIIT_NEAR_MAX,
    CODE_HARD_CAP, CODE_FINGER_HARD_CAP, CODE_MAX_HANG_CAP, CODE_PRE_TRIP,
    CODE_POST_OUTDOOR, CODE_CRAG_BLOCK, CODE_HARD_BACK_TO_BACK,
    CODE_LOW_REST_DAYS,
)

#: A327: ``crag_block`` details, in order of precedence (one alert per session).
CRAG_DETAIL_REST_DAY = "rest_day"
CRAG_DETAIL_NO_HARD = "no_hard"
CRAG_DETAIL_FINGER_72H = "finger_72h"

#: A305 — the density alert (decision 6, 2026-10-06; athlete_plan §5 "≥ 2 true
#: rest days"): a week with fewer true rest days than this raises one
#: week-level ``low_rest_days`` warning.
MIN_REST_DAYS = 2

#: A305 — sessions that leave a day a rest day: recovery / prehab work. A
#: complementary lunch (A300 ``slot_role`` or a C274 focus-family session)
#: counts too ("il pranzo vale poco").
REST_DAY_SESSION_IDS = frozenset({
    "prehab_maintenance", "flexibility_full", "yoga_recovery", "deload_recovery", "regeneration_easy",
})

#: Codes whose ``with`` lists every other day of a weekly / rolling count:
#: adding a session elsewhere changes ``with`` without changing the alert.
_COUNT_CODES = (CODE_HARD_CAP, CODE_HEAVY_PULL, CODE_FINGER_HARD_CAP, CODE_MAX_HANG_CAP)

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
                 outdoor_load_threshold: Optional[float] = None,
                 today: Optional[str] = None,
                 next_days: Optional[Sequence[Mapping[str, Any]]] = None):
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
        # The next week's leading days (``next_days``) are read for their
        # outdoor block only — a Monday crag day after this week's Sunday
        # session — never for their sessions.
        if outdoor_load_threshold is not None and self.day_by_date:
            from backend.engine.stimulus import outdoor_fatigue_days

            days_for_outdoor = dict(self.day_by_date)
            for day in list(next_days or []):
                if isinstance(day, Mapping) and _parse(day.get("date")) is not None:
                    days_for_outdoor.setdefault(str(day["date"])[:10], day)
            dates = sorted(days_for_outdoor)
            self.outdoor = outdoor_fatigue_days(
                state or {}, [days_for_outdoor[d] for d in dates],
                load_threshold=outdoor_load_threshold, outdoor_rows=outdoor_rows,
                since=dates[0], until=dates[-1], today=today)

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
    # A327: high–high only (the calendar rule, unchanged); low is finger_low_gap's.
    for d_iso in tl.plan_dates:
        d = _parse(d_iso)
        here = [s for s in tl.on(d) if is_finger_high(s)]
        if not here:
            continue
        before: List[Dict[str, Any]] = []
        for k in range(1, gap + 1):
            prev = d - timedelta(days=k)
            before.extend(_ref(prev.isoformat(), x) for x in tl.on(prev) if is_finger_high(x))
        # B372: an outdoor day on either side. The day right after a crag day
        # is ``post_outdoor``'s. One alert per session: sessions and crag days
        # all go in ``with``.
        crags: List[Tuple[int, Dict[str, Any]]] = []
        for k in range(-gap, gap + 1):
            if k in (0, 1):
                continue
            o = tl.outdoor_on(d - timedelta(days=k))
            if o is not None:
                crags.append((k, o))
        if not before and not crags:
            continue
        with_ = before + [_outdoor_ref(o["date"]) for _k, o in crags]
        if before:
            side = "of"
            msg_tail = f"{before[0]['session_id']} on {before[0]['date']}"
            if crags:
                msg_tail += f" and {_outdoor_label(crags[0][1])}"
        else:
            k0, o0 = crags[0]
            side = "before" if k0 < 0 else "of"
            msg_tail = f"{_outdoor_label(o0)} ({_OUTDOOR_WHY.get(o0.get('reason'), 'outdoor')})"
        extra = {"outdoor": _outdoor_info(crags[0][1])} if crags else {}
        for s in here:
            if not em.flaggable(d_iso, s):
                continue
            em.emit(CODE_FINGER_GAP, d_iso, s, with_,
                    f"{_label(s)} on {d_iso} loads the fingers within {gap} day(s) {side} {msg_tail}: "
                    f"the finger gap asks for {24 * (gap + 1)} h between them.",
                    gap_days=gap, **extra)


def _recovery_mult(plan: Mapping[str, Any]) -> float:
    raw = (plan.get("profile_snapshot") or {}).get("recovery_multiplier", 1.0)
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return 1.0


def _finger_low_gap(tl: _Timeline, em: _Emitter, mult: float) -> None:
    """A327 (D288 R1) — ``finger_low_gap``: the 6 h rule around a LOW finger
    session and the 2-low-a-day cap. Sessions on the slot clock, a crag day
    that counts as high on [OUTDOOR_START_HOUR, OUTDOOR_END_HOUR]."""
    from backend.engine.complementary_v1 import OUTDOOR_END_HOUR, OUTDOOR_START_HOUR
    from backend.engine.retest_policy import FINGER_LOW_GAP_H, FINGER_LOW_MAX_PER_DAY

    gap_h = FINGER_LOW_GAP_H * mult
    # (start, end, order, tier, date, session | None)
    events: List[Tuple[int, int, int, str, str, Optional[Mapping[str, Any]]]] = []
    n = 0
    for d_iso in sorted(tl.by_date):
        d = _parse(d_iso)
        for s in sorted(tl.on(d), key=lambda x: _slot_index(x.get("slot"))):
            tier = finger_load_of(s)
            if tier is None:
                continue
            t = _clock(d, s.get("slot"), 19)
            events.append((t, t, n, tier, d_iso, s))
            n += 1
    for o_iso in sorted(tl.outdoor):
        o = _parse(o_iso)
        if o is None:
            continue
        events.append((o.toordinal() * 24 + OUTDOOR_START_HOUR, o.toordinal() * 24 + OUTDOOR_END_HOUR,
                       -1, "high", o_iso, None))
    for b in events:
        b_start, _b_end, b_order, b_tier, b_iso, b_s = b
        if b_s is None or b_iso not in tl.plan_dates:
            continue
        partners = []
        for a in events:
            a_start, a_end, a_order, a_tier, a_iso, a_s = a
            if a is b or FINGER_LOAD_LOW not in (a_tier, b_tier):
                continue
            if (a_start, a_order) > (b_start, b_order):
                continue  # the later of the pair is flagged
            if max(0, b_start - a_end) < gap_h:
                partners.append(a)
        lows_today = [x for x in events if x[4] == b_iso and x[5] is not None and x[3] == FINGER_LOAD_LOW]
        over = b_tier == FINGER_LOAD_LOW and lows_today.index(b) >= FINGER_LOW_MAX_PER_DAY
        if not partners and not over:
            continue
        if not em.flaggable(b_iso, b_s):
            continue
        with_ = [_ref(a[4], a[5]) if a[5] is not None else _outdoor_ref(a[4]) for a in partners]
        if over:
            with_ += [_ref(x[4], x[5]) for x in lows_today if x is not b and _ref(x[4], x[5]) not in with_]
        what = "light" if b_tier == FINGER_LOAD_LOW else "finger-high"
        if partners:
            p = partners[-1]
            other = (f"{p[5].get('session_id')} on {p[4]}" if p[5] is not None
                     else f"the outdoor day on {p[4]}")
            msg = (f"{_label(b_s)} on {b_iso} is a {what} finger session less than {gap_h:g} h after {other}: "
                   f"a light finger session needs {gap_h:g} h from any other finger session.")
        else:
            msg = (f"{_label(b_s)} on {b_iso} is light finger session {lows_today.index(b) + 1} of the day: "
                   f"at most {FINGER_LOW_MAX_PER_DAY}.")
        em.emit(CODE_FINGER_LOW_GAP, b_iso, b_s, with_, msg,
                detail="gap" if partners else "per_day", gap_h=gap_h, low_count=len(lows_today))


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
                if k == 1:
                    continue  # the test the day right after is ``post_outdoor``'s
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
    return is_max_for_hiit(s)


def _clock(d: date, slot: Any, default_hour: int) -> int:
    from backend.engine.complementary_v1 import SLOT_HOUR

    return d.toordinal() * 24 + SLOT_HOUR.get(str(slot), default_hour)


def _hiit_near_max(tl: _Timeline, em: _Emitter) -> None:
    from backend.engine.complementary_v1 import OUTDOOR_START_HOUR, hiit_too_close

    for d_iso in tl.plan_dates:
        d = _parse(d_iso)
        for h in tl.on(d):
            if not is_hiit_like(h):
                continue
            # B405: a max session starting less than 24 h after the HIIT.
            t = _clock(d, h.get("slot"), 13)
            maxes = [_ref(x.isoformat(), s) for x in (d, d + timedelta(days=1))
                     for s in tl.on(x) if s is not h and not is_hiit_like(s) and _is_max(s)
                     and hiit_too_close(t, _clock(x, s.get("slot"), 19))]
            # B372: a crag day is a max day for HIIT (as in complementary_v1).
            crag = [tl.outdoor_on(x) for x in (d, d + timedelta(days=1))
                    if tl.outdoor_on(x) and hiit_too_close(t, x.toordinal() * 24 + OUTDOOR_START_HOUR, outdoor=True)]
            if not maxes and not crag:
                continue
            if maxes:
                msg = (f"{_label(h)} on {d_iso} is HIIT less than 24 h before a max session "
                       f"({maxes[0]['session_id']} on {maxes[0]['date']}).")
            else:
                msg = f"{_label(h)} on {d_iso} is HIIT on, or less than 24 h before, {_outdoor_label(crag[0])}."
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
    # A crag day carries no session to flag: the excess is taken, latest
    # first, from the hard days that hold a hard session (a weekend crag day
    # past the cap flags the latest hard session instead).
    excess = len(hard_days) - cap
    with_session = [day for day in hard_days if any(_counts_as_hard(s) for s in day.get("sessions") or [])]
    for day in with_session[max(0, len(with_session) - excess):]:
        d_iso = str(day["date"])[:10]
        for s in day.get("sessions") or []:
            if not _counts_as_hard(s) or not em.flaggable(d_iso, s):
                continue
            em.emit(CODE_HARD_CAP, d_iso, s, [r for r in all_refs if r["date"] != d_iso],
                    f"The week has {len(hard_days)} hard days, the cap is {cap}: "
                    f"{_label(s)} on {d_iso} is past it.",
                    count=len(hard_days), cap=cap)


def _week_count_cap(plan: Mapping[str, Any], tl: _Timeline, em: _Emitter, code: str, cap: int,
                    counts: Any, with_crag: bool, noun: str) -> None:
    """A327: a weekly count cap on the plan's days (``finger_hard_cap`` /
    ``max_hang_cap``), flagged like ``_hard_cap``: the days with a counted
    session, latest first, past the cap. A crag day (``with_crag``) counts but
    has no session to flag."""
    counted: List[Tuple[str, List[Mapping[str, Any]], bool]] = []
    for day in _days_of(plan):
        d_iso = str(day["date"])[:10]
        ss = [s for s in tl.by_date.get(d_iso, []) if counts(s)]
        crag = with_crag and d_iso in tl.outdoor
        if ss or crag:
            counted.append((d_iso, ss, crag))
    if len(counted) <= cap:
        return
    all_refs = [_ref(d, s) for d, ss, _c in counted for s in ss]
    all_refs += [_outdoor_ref(d) for d, _ss, c in counted if c]
    with_session = [(d, ss) for d, ss, _c in counted if ss]
    excess = len(counted) - cap
    for d_iso, ss in with_session[max(0, len(with_session) - excess):]:
        for s in ss:
            if not em.flaggable(d_iso, s):
                continue
            em.emit(code, d_iso, s, [r for r in all_refs if r["date"] != d_iso],
                    f"The week has {len(counted)} {noun}, the cap is {cap}: {_label(s)} on {d_iso} is past it.",
                    count=len(counted), cap=cap)


def _finger_caps(plan: Mapping[str, Any], tl: _Timeline, em: _Emitter) -> None:
    """A327 (D288 R1): ``finger_hard_cap`` (finger-hard days + crag days that
    count) and ``max_hang_cap`` (max-hang days)."""
    from backend.engine.retest_policy import FINGER_HARD_WEEKLY_MAX, MAX_HANG_WEEKLY_MAX

    _week_count_cap(plan, tl, em, CODE_FINGER_HARD_CAP, FINGER_HARD_WEEKLY_MAX, is_finger_hard_exposure,
                    True, "finger-hard days (crag days included)")
    _week_count_cap(plan, tl, em, CODE_MAX_HANG_CAP, MAX_HANG_WEEKLY_MAX, is_max_hang_session,
                    False, "max-hang days")


def _finger_high(s: Mapping[str, Any]) -> bool:
    """A327: the sessions the crag-block 72 h reads as finger load — the
    finger-HIGH ones (a low session waits 6 h only, ``finger_low_gap``)."""
    return is_finger_high(s)


def crag_runs(outdoor: Mapping[str, Any]) -> List[List[str]]:
    """A327 (D288 R2): the runs of at least ``CRAG_BLOCK_MIN_DAYS``
    consecutive crag days among *outdoor* (``{date: …}``, the B372 days that
    count), each a sorted list of ISO dates."""
    from backend.engine.retest_policy import CRAG_BLOCK_MIN_DAYS

    runs: List[List[str]] = []
    cur: List[str] = []
    for d_iso in sorted(outdoor):
        d = _parse(d_iso)
        if d is None:
            continue
        if cur and d - _parse(cur[-1]) == timedelta(days=1):
            cur.append(d_iso)
            continue
        if len(cur) >= CRAG_BLOCK_MIN_DAYS:
            runs.append(cur)
        cur = [d_iso]
    if len(cur) >= CRAG_BLOCK_MIN_DAYS:
        runs.append(cur)
    return runs


def crag_finger_ok_hour(last_crag_day: date) -> int:
    """A327: the clock hour (``day * 24 + hour``) from which a finger session
    may start after a crag block ending on *last_crag_day*."""
    from backend.engine.complementary_v1 import OUTDOOR_END_HOUR
    from backend.engine.retest_policy import CRAG_BLOCK_FINGER_H

    return last_crag_day.toordinal() * 24 + OUTDOOR_END_HOUR + CRAG_BLOCK_FINGER_H


def _crag_block(tl: _Timeline, em: _Emitter) -> set:
    """A327 (D288 R2) — ``crag_block``. Returns the c+1 days, which
    ``post_outdoor`` leaves to this alert."""
    rest_after: set = set()
    for run in crag_runs(tl.outdoor):
        c = _parse(run[-1])
        ok_t = crag_finger_ok_hour(c)
        ok_day = date.fromordinal(ok_t // 24)
        ok_from = f"{ok_day.isoformat()}T{ok_t % 24:02d}:00"
        span = f"{run[0]}..{run[-1]}"
        with_ = [_outdoor_ref(x) for x in run]
        info = {"crag_days": list(run), "finger_ok_from": ok_from, "outdoor": _outdoor_info(tl.outdoor[run[-1]])}
        rest_after.add((c + timedelta(days=1)).isoformat())
        for k in range(1, (ok_day - c).days + 1):
            d = c + timedelta(days=k)
            d_iso = d.isoformat()
            for s in tl.on(d):
                if k == 1 and not is_rest_day_session(s):
                    detail = CRAG_DETAIL_REST_DAY
                    msg = (f"{_label(s)} on {d_iso} is the day after a {len(run)}-day crag block ({span}): "
                           "after two or more hard days out, the next day is a true rest day.")
                elif k == 2 and _is_hard(s):
                    detail = CRAG_DETAIL_NO_HARD
                    msg = (f"{_label(s)} on {d_iso} is a hard session two days after a {len(run)}-day crag "
                           f"block ({span}): that day should not be hard.")
                elif _finger_high(s) and _clock(d, s.get("slot"), 19) < ok_t:
                    detail = CRAG_DETAIL_FINGER_72H
                    msg = (f"{_label(s)} on {d_iso} loads the fingers less than 72 h after a {len(run)}-day crag "
                           f"block ({span}): the next finger session waits until {ok_day.isoformat()} evening.")
                else:
                    continue
                if not em.flaggable(d_iso, s):
                    continue
                em.emit(CODE_CRAG_BLOCK, d_iso, s, with_, msg, detail=detail, **info)
    return rest_after


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


def _post_outdoor(tl: _Timeline, em: _Emitter, skip: Iterable[str] = ()) -> None:
    """B372: every outdoor day that counts (``tl.outdoor``), not only a
    completed one past the load threshold. A327: the day after a crag block
    (*skip*) is ``crag_block``'s — one alert per session."""
    skip = set(skip)
    for d_iso in tl.plan_dates:
        if d_iso in skip:
            continue
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
            # A327: hard or finger-HIGH (a light finger session the day after a
            # crag day is fine: 14 h from its end).
            if not (session_flag(s, "hard") or is_finger_high(s)) or not em.flaggable(d_iso, s):
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
    # B372: a hard session the day BEFORE a crag day that counts. The crag day
    # is the user's (declared or logged), so the pair is always flagged.
    # Finger-tagged sessions are ``finger_gap``'s (one alert per pair); the day
    # after a crag day is ``post_outdoor``'s.
    for d_iso in tl.plan_dates:
        d = _parse(d_iso)
        o = tl.outdoor_on(d + timedelta(days=1))
        if o is None:
            continue
        for s in tl.on(d):
            # A327: a finger-HIGH session is finger_gap's; a hard one with light
            # finger work is flagged here (finger_gap no longer sees it).
            if not _is_hard(s) or is_finger_high(s) or not em.flaggable(d_iso, s):
                continue
            em.emit(CODE_HARD_BACK_TO_BACK, d_iso, s, [_outdoor_ref(o["date"])],
                    f"{_label(s)} on {d_iso} is a hard session the day before {_outdoor_label(o)} "
                    f"({_OUTDOOR_WHY.get(o.get('reason'), 'outdoor')}): back-to-back hard days.",
                    outdoor=_outdoor_info(o))


def is_rest_day_session(s: Mapping[str, Any]) -> bool:
    """A305: a session that does not stop a day from being a true rest day —
    recovery / prehab (``REST_DAY_SESSION_IDS``) or a complementary lunch.
    Tests never are."""
    from backend.engine.complementary_v1 import _is_complementary_like

    if is_test_session(s):
        return False
    if _is_complementary_like(s):
        return True
    return str(s.get("session_id") or "") in REST_DAY_SESSION_IDS


def _low_rest_days(plan: Mapping[str, Any], tl: _Timeline, em: _Emitter) -> None:
    """A305 — ``low_rest_days``: fewer than ``MIN_REST_DAYS`` true rest days in
    the week (decision 6). Week-level: one warning, ``scope: "week"``, dated on
    the plan's first day, no session (``slot`` / ``session_id`` are None). A
    rest day holds no live session but recovery / prehab or a complementary
    lunch; an outdoor day or an other-sport day is not a rest day. What already
    happened counts; the alert is dropped once the week is over."""
    from backend.engine.stimulus import is_declared_outdoor_day

    days = _days_of(plan)
    if len(days) != 7:
        return
    dates = sorted(str(d["date"])[:10] for d in days)
    if em.today and dates[-1] < em.today:
        return
    rest: List[str] = []
    for day in days:
        d_iso = str(day["date"])[:10]
        if is_declared_outdoor_day(day) or d_iso in tl.outdoor or day.get("other_activities"):
            continue
        if all(is_rest_day_session(s) for s in day.get("sessions") or [] if _live(s)):
            rest.append(d_iso)
    if len(rest) >= MIN_REST_DAYS:
        return
    em.out.append({
        "code": CODE_LOW_REST_DAYS,
        "severity": "warning",
        "scope": "week",
        "date": dates[0],
        "slot": None,
        "session_id": None,
        "name": None,
        "user_owned": False,
        "with": [],
        "rest_days": len(rest),
        "min_rest_days": MIN_REST_DAYS,
        "rest_dates": sorted(rest),
        "message": (f"The week of {dates[0]} has {len(rest)} true rest day"
                    f"{'' if len(rest) == 1 else 's'} (fewer than {MIN_REST_DAYS}): "
                    "a day with only a complementary lunch or recovery work counts as rest."),
    })


def evaluate(
    plan: Optional[Mapping[str, Any]],
    prev_days: Optional[Sequence[Mapping[str, Any]]] = None,
    today: Optional[str] = None,
    state: Optional[Mapping[str, Any]] = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    next_days: Optional[Sequence[Mapping[str, Any]]] = None,
    *,
    include_week: bool = False,
) -> List[Dict[str, Any]]:
    """What the guards object to in *plan* — alerts only, see the module doc.

    *include_week* (A305): also return the WEEK-level alerts
    (``low_rest_days``, ``scope: "week"``). Off by default: the session-level
    ``guard_warnings`` contract read by the client (badges per session, toasts
    on an action) predates them and treats a null slot / session as a
    wildcard — week alerts travel apart, in ``evaluate_week`` /
    ``week_guard_warnings``.

    *prev_days*: the previous week's days (cross-week finger gap, heavy-pull
    window, a big outdoor Sunday). *today*: ISO client-local day — days before
    it are not flagged (``None`` flags every pending session). *state*: the
    user state, for the heavy-pull load reading (official 1RM, working loads)
    and the trips; ``None`` reads the labels only and skips ``pre_trip``.
    *outdoor_rows*: the ``outdoor_logs`` rows of the window (B372) — the route
    log that tells a hard crag day from an easy one; ``None`` reads
    ``state.outdoor_log`` only (a completed day without routes then counts).
    *next_days*: the next week's days, read ONLY for a declared outdoor day at
    the start of the next week (a Sunday finger session before a Monday crag
    day); their sessions are ignored.
    """
    if not isinstance(plan, Mapping) or not _days_of(plan):
        return []
    from backend.engine.athlete_context import HEAVY_PULL_MAX_PER_7D, RETEST_BLOCK_H
    from backend.engine.replanner_v1 import OUTDOOR_RIPPLE_THRESHOLD, _recovery_gap

    st: Mapping[str, Any] = state if isinstance(state, Mapping) else {}
    tl = _Timeline(plan, prev_days, st, outdoor_rows, OUTDOOR_RIPPLE_THRESHOLD,
                   today=str(today)[:10] if today else None, next_days=next_days)
    em = _Emitter(tl.plan_dates, today)
    gap = max(1, int(_recovery_gap(dict(plan))))

    _finger_gap(tl, em, gap)
    _finger_low_gap(tl, em, _recovery_mult(plan))
    _finger_test(tl, em, RETEST_BLOCK_H // 24)
    _heavy_pull(tl, em, st, HEAVY_PULL_MAX_PER_7D)
    _hiit_near_max(tl, em)
    _hard_cap(plan, em, tl.outdoor)
    _finger_caps(plan, tl, em)
    if st:
        _pre_trip(plan, em, st)
    rest_after_crag = _crag_block(tl, em)
    _post_outdoor(tl, em, rest_after_crag)
    _hard_back_to_back(tl, em)
    if include_week:
        _low_rest_days(plan, tl, em)

    order = {c: i for i, c in enumerate(CODES)}
    return sorted(em.out, key=lambda w: (w["date"], _slot_index(w.get("slot")),
                                         order.get(w["code"], 99), str(w.get("session_id") or "")))


def evaluate_week(
    plan: Optional[Mapping[str, Any]],
    prev_days: Optional[Sequence[Mapping[str, Any]]] = None,
    today: Optional[str] = None,
    state: Optional[Mapping[str, Any]] = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    next_days: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """A305: only the WEEK-level alerts of *plan* (``scope: "week"`` —
    ``low_rest_days``). Returned to the client as ``week_guard_warnings``,
    never mixed into the session-level ``guard_warnings``."""
    return [w for w in evaluate(plan, prev_days, today, state, outdoor_rows, next_days, include_week=True)
            if w.get("scope") == "week"]


def involves(warning: Mapping[str, Any], date_iso: str, slot: Optional[str] = None) -> bool:
    """Does *warning* name the session at ``date_iso`` (/``slot``) — flagged
    or as the other side (``with``)? A week-level warning (A305
    ``low_rest_days``, ``scope: "week"``) names no session: never."""
    if warning.get("scope") == "week":
        return False
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


__all__ = ["CODES", "MIN_REST_DAYS", "VERSION", "crag_finger_ok_hour", "crag_runs", "evaluate", "evaluate_week",
           "involves", "is_rest_day_session", "new_warnings"]
