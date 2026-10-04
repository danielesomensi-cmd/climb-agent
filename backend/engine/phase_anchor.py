"""A290 (R2) — phase-anchor rotation for the resolver.

Before A290 every block was picked by the same rule: P0 hard filters, then a
recency penalty and a weekly md5 tie-break. Good for variety, wrong for the
progressive stimulus: a tested athlete's main finger exercise changed every
session (min_edge_hang one week, horst the next), the weighted pull-up was
never chosen, and the core changed exercise at every session. Progress cannot
be read week on week when the exercise keeps changing.

The catalog now declares, per block, a ROTATION CLASS (the resolver never
infers it):

- ``phase_anchor`` — the progressive stimulus, FIXED for the phase. Order: the
  block's priority list (``anchor_priority`` / ``anchor_priority_by_phase``),
  ``tested`` or ``untested`` list by axis; ids outside the list follow, by
  md5(id | phase_id | effective_phase_start). No history dependence.
- ``ab`` — a stable A/B alternation: the pool is ordered by md5(id | phase |
  phase start | session | block), A = pool[0], B = pool[1], and the choice is
  ``(week_idx + occurrence_idx) % 2`` where ``occurrence_idx`` counts the
  structural occurrences of the same session earlier in the ISO week (status
  agnostic: marking Monday done never changes Thursday).
- no key — ``free``, the pre-A290 behaviour.

``heavy_slot: true`` (weighted-pull blocks): only the first N occurrences of a
heavy-slot session in the ISO week are heavy (``phase_anchor`` on the heavy
list), the others become ``ab`` without external load. A heavy occurrence is
also downgraded by the spacing guards (real, done fatigue): a weighted pull in
the last 48 h, two heavy-pull days in the last 7, or a limit / strength_long
session tomorrow (decision 2026-10-04: no ≥85 % pull or front lever within
24 h before limit/strength_long). Only occurrences that stayed heavy use a
slot. After a max-hang exposure in the last 72 h the finger block steps down
to its declared sub-maximal hangs (``spacing_step_down``), with a HARD
exclusion of every max-load finger exercise.

SCOPE (DECISIONS 2026-10-04): all of this applies ONLY to an athlete with a
TESTED baseline (``retest_policy.is_tested`` on the finger or the pulling
protocol: source test/test_session, < 90 days). For everyone else
``build_rotation_context`` returns ``None`` and the resolver is bit-for-bit
the pre-A290 one (regression test: ``test_a290_phase_anchor.py``).

Uses the F0 views (A288): ``macro_position`` for the pause-aware phase window,
``retest_policy.official_max`` / ``is_tested`` for the tested level,
``stimulus.exposure_dates`` / ``iter_plan_sessions`` for the dated stimuli.
Pure and deterministic: no ``date.today()``, no I/O except the cached catalog
scan of heavy-slot sessions.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from backend.engine import retest_policy as rp
from backend.engine.macro_position import effective_anchor
from backend.engine.stimulus import (
    EXERCISE_FAMILY,
    FAMILY_FINGER_MAX,
    FAMILY_PULLING_MAX,
    FINGER_FATIGUE_EXTRA_IDS,
    exposure_dates,
    iter_plan_sessions,
)

ROTATION_PHASE_ANCHOR = "phase_anchor"
ROTATION_AB = "ab"
ROTATION_CLASSES: Tuple[str, ...] = (ROTATION_PHASE_ANCHOR, ROTATION_AB)

#: Block-level catalog keys. They live at the top level of a template block or
#: of an inline session module — NEVER inside ``selection`` (pinned by a
#: catalog test).
ROTATION_KEYS: Tuple[str, ...] = (
    "rotation",
    "anchor_axis",
    "anchor_priority",
    "anchor_priority_by_phase",
    "anchor_exclude",
    "heavy_slot",
    "ab_pool",
    "unloaded_only",
    "rotation_exclude",
    "spacing_step_down",
)

AXIS_FINGER = "finger"
AXIS_PULLING = "pulling"

# ---------------------------------------------------------------------------
# Constants. Values without a published source are ENGINEERING CONSTANTS
# (decisions 2026-10-04).
# ---------------------------------------------------------------------------

#: ENGINEERING CONSTANT: tested level that opens the "tested" anchor list.
#: Fingers: total load / bodyweight on 20 mm, 7 s (a 5 s test is converted).
FINGER_TESTED_RATIO = 1.35
#: ENGINEERING CONSTANT: pulling: weighted pull-up 2RM total / bodyweight.
PULLING_TESTED_RATIO = 1.45
#: Edge of the reference hang test. A test on another edge is not compared.
REFERENCE_EDGE_MM = 20

#: Heavy-slot occurrences per ISO week (decision 2026-10-04: "SP heavy slot:
#: weighted_pullup in up to 2 sessions/week"; one elsewhere).
HEAVY_SLOTS_PER_WEEK: Dict[str, int] = {"strength_power": 2}
DEFAULT_HEAVY_SLOTS_PER_WEEK = 1

#: Spacing between heavy stimuli, in calendar days (the resolver works in whole
#: days, like the retest policy: "< 72 h" = fewer than 3 days apart). Shared
#: F0 constants, not new numbers.
MAX_HANG_SPACING_D = rp.RETEST_BLOCK_H // 24      # 72 h → 3 days
HEAVY_PULL_SPACING_D = rp.PULL_TEST_BLOCK_H // 24  # 48 h → 2 days
#: Decision 2026-10-04: at most 2 heavy-pull days in any 7 days (chin-up included).
HEAVY_PULL_MAX_PER_7D = 2

#: Sessions before which no heavy pull and no front lever (24 h rule).
PRE_LIMIT_SESSIONS: FrozenSet[str] = frozenset({"limit_boulder_gym", "power_contact_gym", "strength_long"})
FRONT_LEVER_IDS: FrozenSet[str] = frozenset({"front_lever_one_leg", "front_lever_straddle"})

#: Load models that make a pull "heavy" (external load on the body).
LOADED_MODELS: FrozenSet[str] = frozenset({"total_load", "external_load"})

#: Exercises that are NEVER a max-hang step-down: the whole finger_max exposure
#: family plus the finger-fatigue hangs kept out of it (min-edge, 10 s max
#: hangs). Single source: ``stimulus``.
FINGER_MAX_LOAD_IDS: FrozenSet[str] = frozenset(
    {eid for eid, fam in EXERCISE_FAMILY.items() if fam == FAMILY_FINGER_MAX}
) | frozenset(FINGER_FATIGUE_EXTRA_IDS)


def is_max_finger_load(ex: Mapping[str, Any]) -> bool:
    """A hang that loads the fingers maximally: excluded from the step-down."""
    eid = str(ex.get("id") or ex.get("exercise_id") or "")
    if eid in FINGER_MAX_LOAD_IDS:
        return True
    if str(ex.get("intensity_level") or "") == "max":
        return True
    return str((ex.get("stress_tags") or {}).get("fingers") or "") == "high"

# Session id prefixes whose done instances count as max-hang / heavy-pull
# exposure even when the family table has nothing (legacy test logs).
_FINGER_TEST_PREFIXES = ("test_max_hang", "test_lp_max")
_PULL_TEST_PREFIXES = ("test_max_weighted_pullup",)


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Phase window (pause-aware, A223) — from macro_position, never phases[].start_date
# ---------------------------------------------------------------------------

def phase_window(
    macrocycle: Optional[Mapping[str, Any]], phase_id: Optional[str], on: date
) -> Optional[Tuple[str, date]]:
    """``(phase_id, effective_phase_start)`` for the phase served on ``on``.

    ``phase_id`` is the resolver's ``phase`` kwarg (what week.py / replanner
    serve, pause-aware); ``None`` → the phase ``macro_position`` places ``on``
    in. The start is ``start_date + pause.offset_days + 7 × weeks of the
    earlier phases`` — the same arithmetic as ``deps.current_phase_and_week``
    (A288 parity), so ``phases[].start_date`` (not shifted by a pause) is never
    read. ``None`` when there is no usable macrocycle.
    """
    if not macrocycle or not macrocycle.get("start_date"):
        return None
    phases = macrocycle.get("phases") or []
    if not phases:
        return None
    try:
        eff_start, eff_on = effective_anchor(dict(macrocycle), on)
    except (KeyError, ValueError, TypeError):
        return None
    if phase_id is None:
        from backend.engine.macro_position import phase_and_week_on

        pi, _wi = phase_and_week_on(dict(macrocycle), on)
        phase_id = str(phases[pi].get("phase_id") or "")
    weeks_before = 0
    for p in phases:
        if p.get("phase_id") == phase_id:
            return phase_id, eff_start + timedelta(weeks=weeks_before)
        weeks_before += int(p.get("duration_weeks", 1))
    # Phase id not in this macrocycle (stale kwarg): anchor on the cycle start.
    return phase_id, eff_start


# ---------------------------------------------------------------------------
# Tested level (official max from tests.*, never the estimated baselines)
# ---------------------------------------------------------------------------

def tested_ratio(state: Mapping[str, Any], axis: str, on: date) -> Optional[float]:
    """Total load / bodyweight of the tested official max on ``on``, or ``None``.

    ``None`` when the axis has no TESTED official max (source test/test_session,
    < 90 days — ``retest_policy``), when the hang test is on an edge other than
    20 mm, or when no bodyweight is known. The test's own bodyweight wins.
    """
    protocol = rp.PROTOCOL_HANG_7S if axis == AXIS_FINGER else rp.PROTOCOL_PULLUP_2RM
    om = rp.official_max(state, protocol, on)
    if not om or not om.get("tested"):
        return None
    if axis == AXIS_FINGER:
        edge = om.get("edge_mm")
        if edge is not None:
            try:
                if int(edge) != REFERENCE_EDGE_MM:
                    return None
            except (TypeError, ValueError):
                return None
    bw = om.get("bodyweight_kg") or state.get("bodyweight_kg") or (state.get("body") or {}).get("weight_kg")
    try:
        bw_f = float(bw)
        total = float(om["total_kg"])
    except (TypeError, ValueError, KeyError):
        return None
    if bw_f <= 0:
        return None
    return round(total / bw_f, 3)


def is_tested_any(state: Mapping[str, Any], on: date) -> bool:
    """The A290 scope gate: a tested official max on the finger OR the pulling axis."""
    return rp.is_tested(state, rp.PROTOCOL_HANG_7S, on) or rp.is_tested(state, rp.PROTOCOL_PULLUP_2RM, on)


# ---------------------------------------------------------------------------
# Heavy-slot sessions (catalog scan, cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def heavy_slot_session_ids(sessions_dir: str, templates_dir: str) -> FrozenSet[str]:
    """Session ids carrying a ``heavy_slot`` block (inline module or template block)."""
    heavy_templates = set()
    tpl_root = os.path.join(templates_dir, "v1") if os.path.isdir(os.path.join(templates_dir, "v1")) else templates_dir
    if os.path.isdir(tpl_root):
        for fn in sorted(os.listdir(tpl_root)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(tpl_root, fn), "r", encoding="utf-8") as f:
                    tpl = json.load(f)
            except (OSError, ValueError):
                continue
            if any(isinstance(b, dict) and b.get("heavy_slot") for b in tpl.get("blocks") or []):
                heavy_templates.add(fn[:-5])
    out = set()
    if os.path.isdir(sessions_dir):
        for fn in sorted(os.listdir(sessions_dir)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(sessions_dir, fn), "r", encoding="utf-8") as f:
                    sess = json.load(f)
            except (OSError, ValueError):
                continue
            for mod in sess.get("modules") or []:
                if isinstance(mod, dict) and (mod.get("heavy_slot") or mod.get("template_id") in heavy_templates):
                    out.add(str(sess.get("session_id") or fn[:-5]))
                    break
    return frozenset(out)


# ---------------------------------------------------------------------------
# Rotation context (built once per resolution)
# ---------------------------------------------------------------------------

@dataclass
class RotationContext:
    target_date: date
    phase_id: str
    phase_start: date
    week_idx: int
    finger_ratio: Optional[float]
    pulling_ratio: Optional[float]
    #: (date_iso, slot_order, session_id) of the ISO week, status agnostic.
    week_sessions: List[Tuple[str, int, str]] = field(default_factory=list)
    #: session ids planned (not skipped) the day after target_date.
    tomorrow_session_ids: FrozenSet[str] = frozenset()
    #: dated real fatigue (done sessions, tests included), ≤ target_date.
    finger_max_days: List[date] = field(default_factory=list)
    pulling_max_days: List[date] = field(default_factory=list)
    heavy_slot_sessions: FrozenSet[str] = frozenset()
    #: heavy-slot occurrences earlier in the ISO week that WERE heavy (not
    #: downgraded by a spacing guard) — computed by ``build_rotation_context``.
    prior_heavy: int = 0
    #: where ``tomorrow_session_ids`` comes from: ``plan`` (a plan covers the
    #: day) or ``weekday_proxy`` (no plan yet: same weekday of the target week).
    tomorrow_source: str = "plan"

    @property
    def advanced(self) -> bool:
        """Above a tested threshold on at least one axis (core floor, decisions)."""
        return self.finger_tested or self.pulling_tested

    @property
    def finger_tested(self) -> bool:
        return self.finger_ratio is not None and self.finger_ratio >= FINGER_TESTED_RATIO

    @property
    def pulling_tested(self) -> bool:
        return self.pulling_ratio is not None and self.pulling_ratio >= PULLING_TESTED_RATIO

    @property
    def phase_seed(self) -> str:
        return f"{self.phase_id}|{self.phase_start.isoformat()}"

    def axis_tested(self, axis: Optional[str]) -> bool:
        if axis == AXIS_FINGER:
            return self.finger_tested
        if axis == AXIS_PULLING:
            return self.pulling_tested
        return True  # axis-free block: the scope gate already passed

    def occurrence_idx(self, session_id: str) -> int:
        """Structural occurrences of ``session_id`` earlier in the ISO week."""
        t = self.target_date.isoformat()
        return sum(1 for d, _o, sid in self.week_sessions if sid == session_id and d < t)

    def heavy_rank(self) -> int:
        """Heavy-slot occurrences earlier in the ISO week that were really heavy.

        Status agnostic (a skipped Monday still used its slot), but an
        occurrence a spacing guard turned light does NOT use one of the
        ``HEAVY_SLOTS_PER_WEEK``: the budget counts heavy pulls, not sessions.
        """
        return self.prior_heavy

    def heavy_slots(self) -> int:
        return HEAVY_SLOTS_PER_WEEK.get(self.phase_id, DEFAULT_HEAVY_SLOTS_PER_WEEK)


def _week_sessions_from_plan(plan: Mapping[str, Any], monday: date) -> List[Tuple[str, int, str]]:
    lo, hi = monday.isoformat(), (monday + timedelta(days=6)).isoformat()
    out: List[Tuple[str, int, str]] = []
    for week in plan.get("weeks") or []:
        for day in week.get("days") or []:
            d = str(day.get("date") or "")[:10]
            if not (lo <= d <= hi):
                continue
            for i, s in enumerate(day.get("sessions") or []):
                if isinstance(s, dict) and s.get("session_id"):
                    out.append((d, i, str(s["session_id"])))
    return sorted(out)


def _plan_covers(plan: Optional[Mapping[str, Any]], d: date) -> bool:
    if not isinstance(plan, Mapping):
        return False
    iso = d.isoformat()
    for week in plan.get("weeks") or []:
        for day in week.get("days") or []:
            if str(day.get("date") or "")[:10] == iso:
                return True
    return False


def _sessions_on(state: Mapping[str, Any], week_plan: Optional[Mapping[str, Any]], d: date) -> List[Mapping[str, Any]]:
    """Sessions of day ``d`` — from the plan being resolved when it covers the
    day, else from the state's hot week plans."""
    iso = d.isoformat()
    if _plan_covers(week_plan, d):
        out: List[Mapping[str, Any]] = []
        for week in week_plan.get("weeks") or []:  # type: ignore[union-attr]
            for day in week.get("days") or []:
                if str(day.get("date") or "")[:10] == iso:
                    out.extend(s for s in day.get("sessions") or [] if isinstance(s, dict))
        return out
    return [s for dd, s, _src in iter_plan_sessions(state) if dd == iso]


def _plan_range_covers(plan: Optional[Mapping[str, Any]], d: date) -> bool:
    """``d`` falls inside the plan's weeks (a rest day has no session but is
    still a known day), or the plan lists it explicitly."""
    if not isinstance(plan, Mapping):
        return False
    if _plan_covers(plan, d):
        return True
    start = _as_date(plan.get("start_date"))
    if start is None:
        return False
    n_weeks = max(1, len(plan.get("weeks") or []))
    return start <= d < start + timedelta(weeks=n_weeks)


def _day_covered(state: Mapping[str, Any], week_plan: Optional[Mapping[str, Any]], d: date) -> bool:
    if _plan_range_covers(week_plan, d):
        return True
    iso = d.isoformat()
    for p in (state.get("week_plans") or {}).values():
        if _plan_range_covers(p, d):
            return True
    return any(dd == iso for dd, _s, _src in iter_plan_sessions(state))


def _planned_ids_on(state: Mapping[str, Any], week_plan: Optional[Mapping[str, Any]], d: date) -> FrozenSet[str]:
    return frozenset(
        str(s.get("session_id") or "") for s in _sessions_on(state, week_plan, d)
        if s.get("status") != "skipped"
    )


def _done_test_days(state: Mapping[str, Any], prefixes: Sequence[str], since: date, until: date) -> List[date]:
    out = []
    for d, s, _src in iter_plan_sessions(state):
        if s.get("status") != "done":
            continue
        if not str(s.get("session_id") or "").startswith(tuple(prefixes)):
            continue
        dd = _as_date(d)
        if dd is not None and since <= dd <= until:
            out.append(dd)
    return out


def build_rotation_context(
    state: Optional[Mapping[str, Any]],
    target_date: Optional[date],
    phase: Optional[str],
    *,
    week_plan: Optional[Mapping[str, Any]] = None,
    heavy_slot_sessions: FrozenSet[str] = frozenset(),
) -> Optional[RotationContext]:
    """The rotation context, or ``None`` (→ pre-A290 resolver, bit for bit).

    ``None`` when: no state, no target date, no usable macrocycle, or no tested
    baseline on either axis (``is_tested_any``).
    """
    if not state or target_date is None:
        return None
    if not is_tested_any(state, target_date):
        return None
    win = phase_window(state.get("macrocycle"), phase, target_date)
    if win is None:
        return None
    phase_id, phase_start = win
    week_idx = max(0, (target_date - phase_start).days // 7)

    monday = target_date - timedelta(days=target_date.weekday())
    if _plan_covers(week_plan, target_date):
        week_sessions = _week_sessions_from_plan(week_plan, monday)  # type: ignore[arg-type]
    else:
        week_sessions = []
        lo, hi = monday.isoformat(), (monday + timedelta(days=6)).isoformat()
        seen_days: Dict[str, int] = {}
        for d, s, _src in iter_plan_sessions(state):
            if lo <= d <= hi and s.get("session_id"):
                idx = seen_days.get(d, 0)
                seen_days[d] = idx + 1
                week_sessions.append((d, idx, str(s["session_id"])))
        week_sessions.sort()

    tomorrow = target_date + timedelta(days=1)
    tomorrow_source = "plan"
    if _day_covered(state, week_plan, tomorrow):
        tomorrow_ids = _planned_ids_on(state, week_plan, tomorrow)
    else:
        # Sunday → Monday of a week not generated yet (and, once generated, the
        # Sunday session is past and immutable — the guard would never see it).
        # Proxy: the same weekday of the target's own ISO week. The planner
        # lays sessions out by weekday availability, so within a phase the
        # weeks repeat. Deterministic; reported in the trace.
        tomorrow_ids = _planned_ids_on(state, week_plan, tomorrow - timedelta(days=7))
        tomorrow_source = "weekday_proxy"

    since = target_date - timedelta(days=7)
    finger_days = {
        _as_date(d) for d in exposure_dates(state, FAMILY_FINGER_MAX, since=since, until=target_date)
    }
    finger_days.update(_done_test_days(state, _FINGER_TEST_PREFIXES, since, target_date))
    # Pull days reach back 14 days: the heavy-slot budget re-evaluates the
    # guards of the week's earlier occurrences (each looks back 7 days).
    pull_since = target_date - timedelta(days=14)
    pull_days = {
        _as_date(d) for d in exposure_dates(state, FAMILY_PULLING_MAX, since=pull_since, until=target_date)
    }
    pull_days.update(_done_test_days(state, _PULL_TEST_PREFIXES, pull_since, target_date))
    pull_sorted = sorted(d for d in pull_days if d is not None)

    # Heavy-slot budget: walk the week's earlier heavy-slot occurrences in
    # order and keep only those the guards left heavy. Each is judged on the
    # fatigue known BEFORE its day (strictly earlier pull days — its own
    # weighted pull, once done, must not reclassify it) and on its own
    # tomorrow.
    slots = HEAVY_SLOTS_PER_WEEK.get(phase_id, DEFAULT_HEAVY_SLOTS_PER_WEEK)
    t_iso = target_date.isoformat()
    prior_heavy = 0
    for d_iso, _o, sid in week_sessions:
        if d_iso >= t_iso or sid not in heavy_slot_sessions:
            continue
        d_i = _as_date(d_iso)
        if d_i is None:
            continue
        reason = _downgrade_reason(
            rank=prior_heavy, slots=slots, on=d_i,
            pull_days=[p for p in pull_sorted if p < d_i],
            tomorrow_ids=_planned_ids_on(state, week_plan, d_i + timedelta(days=1)),
        )
        if reason is None:
            prior_heavy += 1

    return RotationContext(
        target_date=target_date,
        phase_id=phase_id,
        phase_start=phase_start,
        week_idx=week_idx,
        finger_ratio=tested_ratio(state, AXIS_FINGER, target_date),
        pulling_ratio=tested_ratio(state, AXIS_PULLING, target_date),
        week_sessions=week_sessions,
        tomorrow_session_ids=tomorrow_ids,
        finger_max_days=sorted(d for d in finger_days if d is not None),
        pulling_max_days=pull_sorted,
        heavy_slot_sessions=heavy_slot_sessions,
        prior_heavy=prior_heavy,
        tomorrow_source=tomorrow_source,
    )


# ---------------------------------------------------------------------------
# Block plan: what the P0 selector must do for one block
# ---------------------------------------------------------------------------

def _lists_for_phase(cfg: Mapping[str, Any], phase_id: str) -> Dict[str, Any]:
    """Merge ``anchor_priority`` with ``anchor_priority_by_phase[phase_id]``."""
    base = cfg.get("anchor_priority")
    if isinstance(base, list):
        merged: Dict[str, Any] = {"tested": list(base), "untested": list(base)}
    elif isinstance(base, Mapping):
        merged = {k: v for k, v in base.items()}
    else:
        merged = {}
    excl = cfg.get("anchor_exclude")
    if isinstance(excl, Mapping):
        merged["exclude"] = {k: list(v) for k, v in excl.items()}
    by_phase = (cfg.get("anchor_priority_by_phase") or {}).get(phase_id)
    if isinstance(by_phase, Mapping):
        for k, v in by_phase.items():
            if k == "anchor_exclude":
                merged["exclude"] = {kk: list(vv) for kk, vv in (v or {}).items()}
            else:
                merged[k] = v
    return merged


def _days_since(days: Sequence[date], on: date) -> List[int]:
    return [(on - d).days for d in days if d <= on]


def _downgrade_reason(
    *, rank: int, slots: int, on: date, pull_days: Sequence[date], tomorrow_ids: FrozenSet[str]
) -> Optional[str]:
    if rank >= slots:
        return "not_heavy_occurrence"
    since = _days_since(pull_days, on)
    if any(0 <= n < HEAVY_PULL_SPACING_D for n in since):
        return "heavy_pull_48h"
    if len([n for n in since if 1 <= n <= 6]) >= HEAVY_PULL_MAX_PER_7D:
        return "heavy_pull_7d_cap"
    if tomorrow_ids & PRE_LIMIT_SESSIONS:
        return "pre_limit_24h"
    return None


def heavy_downgrade_reason(ctx: RotationContext, session_id: str) -> Optional[str]:
    """Why a heavy-slot occurrence is NOT heavy, or ``None`` (heavy)."""
    return _downgrade_reason(
        rank=ctx.heavy_rank(), slots=ctx.heavy_slots(), on=ctx.target_date,
        pull_days=ctx.pulling_max_days, tomorrow_ids=ctx.tomorrow_session_ids,
    )


def max_hang_spacing_violated(ctx: RotationContext) -> bool:
    return any(0 <= n < MAX_HANG_SPACING_D for n in _days_since(ctx.finger_max_days, ctx.target_date))


def plan_block(
    ctx: Optional[RotationContext],
    cfg: Mapping[str, Any],
    *,
    session_id: str,
    block_id: str,
) -> Optional[Dict[str, Any]]:
    """The rotation plan of a block, or ``None`` (free block / no context).

    Returned dict (consumed by ``resolve_session.pick_best_exercise_p0``)::

        {mode: phase_anchor|ab, order: [ids], exclude: [ids], pool: [ids],
         unloaded_only: bool, soft_exclude: [ids], seed: str, choice: int,
         prescription_overrides: {...}, trace: {...}}

    The max-hang step-down adds ``hard_exclude_max_finger``, ``domain_req`` /
    ``pattern_req`` (the resolver selects in that domain/pattern) and
    ``drop_block_prescription``.
    """
    if ctx is None:
        return None
    mode = cfg.get("rotation")
    heavy = bool(cfg.get("heavy_slot"))
    if mode not in ROTATION_CLASSES and not heavy:
        return None

    lists = _lists_for_phase(cfg, ctx.phase_id)
    by_phase = cfg.get("anchor_priority_by_phase") or {}
    if (mode == ROTATION_PHASE_ANCHOR and not heavy and "anchor_priority" not in cfg
            and by_phase and ctx.phase_id not in by_phase):
        # A block anchored only in some phases (SP campus) is free elsewhere.
        return None

    trace: Dict[str, Any] = {"phase_seed": ctx.phase_seed, "week_idx": ctx.week_idx}
    # Core intensity floor: advanced athletes only (above a tested threshold).
    soft_exclude: List[str] = list(cfg.get("rotation_exclude") or []) if ctx.advanced else []
    pre_limit = bool(ctx.tomorrow_session_ids & PRE_LIMIT_SESSIONS)
    if pre_limit:
        soft_exclude.extend(sorted(FRONT_LEVER_IDS))
        trace["pre_limit_source"] = ctx.tomorrow_source
    axis = cfg.get("anchor_axis") or (AXIS_PULLING if heavy else None)

    if heavy:
        reason = heavy_downgrade_reason(ctx, session_id)
        trace["heavy_slot"] = True
        trace["heavy_rank"] = ctx.heavy_rank()
        if reason is None:
            mode = ROTATION_PHASE_ANCHOR
        else:
            mode = ROTATION_AB
            trace["spacing_downgrade"] = reason
            if reason == "pre_limit_24h":
                trace["pre_limit_source"] = ctx.tomorrow_source

    occ = ctx.occurrence_idx(session_id)
    if mode == ROTATION_AB:
        unloaded = bool(cfg.get("unloaded_only")) or heavy
        trace.update({"rotation": ROTATION_AB, "occurrence_idx": occ,
                      "ab_slot": "AB"[(ctx.week_idx + occ) % 2]})
        return {
            "mode": ROTATION_AB,
            "order": [],
            "exclude": [],
            "pool": list(cfg.get("ab_pool") or []),
            "unloaded_only": unloaded,
            "soft_exclude": soft_exclude,
            "seed": f"{ctx.phase_seed}|{session_id}|{block_id}",
            "choice": (ctx.week_idx + occ) % 2,
            "prescription_overrides": {},
            "trace": trace,
        }

    # Max-hang spacing (< 72 h after a finger_max exposure): a real STEP-DOWN,
    # not another list of max hangs. The block switches to its declared
    # sub-maximal hangs (other domain/pattern), every max-load finger exercise
    # is a HARD exclusion (no candidate → the block is skipped, never a max
    # hang), and the block's max-intensity prescription is dropped.
    step = cfg.get("spacing_step_down")
    if isinstance(step, Mapping) and max_hang_spacing_violated(ctx):
        trace.update({"rotation": ROTATION_PHASE_ANCHOR, "anchor_list": "spacing",
                      "anchor_axis": axis, "spacing_downgrade": "max_hang_72h"})
        return {
            "mode": ROTATION_PHASE_ANCHOR,
            "order": list(step.get("priority") or []),
            "exclude": [],
            "hard_exclude_max_finger": True,
            "domain_req": list(step.get("domain") or []) or None,
            "pattern_req": list(step.get("pattern") or []) or None,
            "drop_block_prescription": True,
            "pool": [],
            "unloaded_only": False,
            "soft_exclude": soft_exclude,
            "seed": ctx.phase_seed,
            "choice": 0,
            "prescription_overrides": dict(step.get("prescription_overrides") or {}),
            "trace": trace,
        }

    # phase_anchor
    tested = ctx.axis_tested(axis)
    list_name = "tested" if tested else "untested"
    order = list(lists.get(list_name) or [])
    exclude = list(((lists.get("exclude") or {}).get(list_name)) or [])
    overrides = dict(lists.get(f"{list_name}_prescription_overrides") or {})
    trace.update({"rotation": ROTATION_PHASE_ANCHOR, "anchor_list": list_name,
                  "anchor_axis": axis})
    return {
        "mode": ROTATION_PHASE_ANCHOR,
        "order": order,
        "exclude": exclude,
        "pool": [],
        "unloaded_only": False,
        "soft_exclude": soft_exclude,
        "seed": ctx.phase_seed,
        "choice": 0,
        "prescription_overrides": overrides,
        "trace": trace,
    }


def select_from_pool(
    pool: List[Dict[str, Any]],
    plan: Mapping[str, Any],
    *,
    get_id,
    session_local_ids: Optional[set] = None,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Pick from a P0-filtered pool according to ``plan``. Deterministic.

    Every narrowing step is soft (applied only when something survives), so a
    rotation plan can never empty a block that the free path would fill.
    """
    local = session_local_ids or set()
    info: Dict[str, Any] = {}

    def _narrow(cands: List[Dict[str, Any]], keep) -> List[Dict[str, Any]]:
        kept = [e for e in cands if keep(e)]
        return kept if kept else cands

    cands = list(pool)
    if plan.get("hard_exclude_max_finger"):
        # HARD (not soft): a step-down that finds only max hangs skips the block.
        cands = [e for e in cands if not is_max_finger_load(e)]
        info["hard_excluded_max_finger"] = len(pool) - len(cands)
    if not cands:
        return None, info
    if plan.get("exclude"):
        ex = set(plan["exclude"])
        cands = _narrow(cands, lambda e: get_id(e) not in ex)
    if plan.get("soft_exclude"):
        sx = set(plan["soft_exclude"])
        cands = _narrow(cands, lambda e: get_id(e) not in sx)

    if plan["mode"] == ROTATION_AB:
        if plan.get("unloaded_only"):
            cands = _narrow(cands, lambda e: str(e.get("load_model") or "") not in LOADED_MODELS)
        if plan.get("pool"):
            allowed = set(plan["pool"])
            cands = _narrow(cands, lambda e: get_id(e) in allowed)
        seed = plan["seed"]
        cands.sort(key=lambda e: _md5(f"{get_id(e)}|{seed}"))
        pair = cands[:2]
        choice = int(plan.get("choice") or 0) % len(pair)
        sel = pair[choice]
        if get_id(sel) in local:
            alt = [e for e in pair if get_id(e) not in local] or [e for e in cands if get_id(e) not in local]
            if alt:
                sel = alt[0]
                info["local_swap"] = True
        info["ab_pair"] = [get_id(e) for e in pair]
        return sel, info

    # phase_anchor: session-local first (never the same exercise twice in a session)
    cands = _narrow(cands, lambda e: get_id(e) not in local)
    order = list(plan.get("order") or [])
    idx = {eid: i for i, eid in enumerate(order)}
    seed = plan["seed"]
    cands.sort(key=lambda e: (idx.get(get_id(e), len(order)), _md5(f"{get_id(e)}|{seed}")))
    sel = cands[0]
    info["anchor_rank"] = idx.get(get_id(sel))
    return sel, info
