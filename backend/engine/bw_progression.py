"""A298 — bodyweight progression: the closed loop on the C272 ladders.

C272 shipped the ladders (``backend/catalog/progressions/v1/bw_ladders.json``)
and a READ-ONLY seed (``bw_ladders.seed_levels``). This module turns them into
a deterministic closed loop (BW spec, ``engine_rules`` R0-R12):

- **State** — ``user_state.bw_progression`` (top level, its own key: never
  ``working_loads.entries``, whose consumers would mistake a ladder level for a
  load). Shape: ``{<family>: entry, "technique": {<ladder>: tech_entry}}``.
  An entry::

      {exercise_id, level_idx, axis, sets, target, tempo_level, added_kg,
       top_streak, vh_streak, pending_promotion, ramp, last_session_date,
       source: seed_history|seed_test|feedback|user_edit, seeded_from,
       last_outcome, _prev}

  The official maxima are never written (R9).
- **Seed** — when a family has no entry, the entry is derived at read time by
  the same pure function (``bw_ladders.seed_levels``) in the resolver, in the
  custom read path and in ``apply_feedback``: tested athletes only (official
  max with a test log < 90 days). Untested athletes have no entry and every
  consumer is a no-op for them (bit-for-bit unchanged).
- **next_state** — label / measure steps, promotion after ``advance_sessions``
  sessions at the top of the band, terminal (tempo → load / handoff / cap),
  frozen in performance and deload, re-entry after a long gap, lower-back
  levels never assigned automatically.
- **dose_for** — the prescription a level carries (sets, reps or seconds,
  rest, tempo, added kg), written by the resolver into ``prescription`` with
  ``source: "bw_ladder"`` and by the custom read path into ladder rows.
- **Technique ladders** (feet, falls) — minimal, as TECH.json recommends while
  the logging is thin: one optional number per session (foot readjustments on
  the sample problem, max fear 0-10) moves the P/F level by the ladder's own
  criteria. Positions (hover x/5) are not tracked yet.

Pure and deterministic: the only time input is the session date
(``ref_date``), never ``date.today()``. The writers (``apply_bw_item``,
``apply_technique_measures``, ``set_level``, ``resolve_promotion``) mutate the
state passed in; everything else returns new objects.

Every numeric threshold without a published source is an ENGINEERING
CONSTANT (listed in docs/vocabulary_v1.md §4.9).
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from backend.engine import bw_ladders as bl

DateLike = Union[date, str]

STATE_KEY = "bw_progression"
TECHNIQUE_KEY = "technique"

#: Label → steps inside the band (BW spec R1-R5). very_easy is +2 steps and
#: never a level jump (R5: the spec removed the level skip, it has no source).
LABEL_STEPS: Dict[str, int] = {"very_easy": 2, "easy": 1, "ok": 0, "hard": -1, "very_hard": -2}
#: R-PHASE: no promotion, no tempo/load step, one set fewer (min 2).
FROZEN_PHASES = frozenset({"performance", "deload"})
FROZEN_MIN_SETS = 2
#: R0: a hold declared to failure (a test) counts at 80 % of the time held.
#: ENGINEERING CONSTANT.
TEST_HOLD_FACTOR = 0.80
#: R1: a very_hard on a loaded terminal removes 10 % of the added kg (min the
#: family's distal step, else 1 kg). ENGINEERING CONSTANT.
LOAD_DOWN_PCT = 0.10
#: R7: after a tempo / load step the target restarts two steps below the top
#: of the band (T2B 3x8 → 3x6 with a 3 s eccentric). ENGINEERING CONSTANT.
TERMINAL_RESTART_STEPS = 2
#: R1: consecutive very_hard sessions that drop one level.
VH_STREAK_LEVEL_DOWN = 2
#: Outcome kinds the client can render as a one-line message.
OUTCOME_KINDS = (
    "hold", "step_up", "step_down", "promoted", "promotion_proposed", "top_streak",
    "frozen", "manual_only", "tempo_up", "load_up", "tempo_down", "load_down",
    "level_down", "floor_warning", "handoff", "cap", "ramp", "reentry",
)

# Technique ladders (TECH.json, bw_ladders.json "technique_ladders").
#: Feet: ≤ this many readjustments on the sample problem is a good session.
FEET_GOOD_MAX = 1
#: Feet: ≥ this many readjustments is a bad session.
FEET_BAD_MIN = 3
#: Falls: fear ≤ this value is a good session (advance after 2).
FEAR_GOOD_MAX = 3
#: Falls: one fall at fear ≥ this value drops one step.
FEAR_BAD_MIN = 7
#: Sessions in a row needed to advance (both ladders) / to regress (feet).
TECH_STREAK = 2
#: Bounds of the two measures (router sanitisation).
SAMPLE_READJUST_MAX = 30
FEAR_MAX = 10
HELD_S_MAX = 120
#: Feet ladder drills that carry the readjustment measure; the falls drill.
FALL_DRILLS = frozenset({"fall_ladder"})

MEASURE_BW_REPS = "bw_reps"
MEASURE_BW_HOLD = "bw_hold"
MEASURE_FEET = "feet_readjust"
MEASURE_FEAR = "fear_max"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _as_date(value: DateLike) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _iso(value: Optional[DateLike]) -> Optional[str]:
    if value is None or value == "":
        return None
    try:
        return _as_date(value).isoformat()
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    n = _num(value)
    if n is None:
        head = str(value or "").strip().split("-")[0].strip()
        n = _num(head) if head else None
    if n is None or n <= 0:
        return None
    return int(n)


def _round_half(value: float) -> float:
    return round(float(value) * 2) / 2


def _families() -> Dict[str, Dict[str, Any]]:
    return {str(f["family"]): f for f in (bl._load_file().get("families") or [])}


def family_doc(family: str) -> Optional[Dict[str, Any]]:
    return _families().get(str(family))


def _levels(fam: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return list(fam.get("levels") or [])


def _catalog() -> Dict[str, Dict[str, Any]]:
    from backend.engine.progression_v1 import _load_catalog_cache

    return _load_catalog_cache()


def _exercise_name(exercise_id: Optional[str]) -> str:
    if not exercise_id:
        return ""
    info = _catalog().get(str(exercise_id)) or {}
    return str(info.get("name") or str(exercise_id).replace("_", " ").capitalize())


def _caps() -> Tuple[int, int]:
    caps = bl._load_file().get("caps") or {}
    return int(caps.get("max_reps") or 30), int(caps.get("max_seconds") or 60)


def _skill_window(fam: Mapping[str, Any]) -> int:
    seed = bl._load_file().get("seed_rules") or {}
    if fam.get("skill_family"):
        return int(seed.get("skill_family_history_window_days") or 60)
    return int(seed.get("history_window_days") or 120)


def is_frozen(phase: Optional[str]) -> bool:
    return str(phase or "") in FROZEN_PHASES


def phase_on(state: Mapping[str, Any], on: DateLike) -> str:
    """The macrocycle phase on ``on`` (progression_v1's own reading)."""
    from backend.engine.progression_v1 import _get_current_phase_id

    return _get_current_phase_id(dict(state), str(_iso(on) or ""))


def has_lower_back_zone(state: Mapping[str, Any]) -> bool:
    """R12: the lower-back limitation zone does not exist yet in the app
    (``resolve_session.ZONE_TO_CONTRAINDICATION`` has no lower_back), so the
    lower-back levels are manual only for everyone. Kept as a function so the
    day the zone exists only this line changes."""
    return False


def _lower_back_from(fam: Mapping[str, Any]) -> Optional[int]:
    lb = fam.get("lower_back_risk_from_level")
    return int(lb) if lb is not None else None


def auto_ceiling(fam: Mapping[str, Any], lower_back_zone: bool = False) -> int:
    """Highest level the ENGINE may assign or promote to on its own (R12)."""
    top = len(_levels(fam)) - 1
    lb = _lower_back_from(fam)
    if lb is not None and not lower_back_zone:
        return min(top, lb - 1)
    return top


# ---------------------------------------------------------------------------
# Entries: persisted state or read-time seed
# ---------------------------------------------------------------------------

def _persisted(state: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = state.get(STATE_KEY)
    return raw if isinstance(raw, Mapping) else {}


def _normalize(entry: Mapping[str, Any], fam: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    levels = _levels(fam)
    try:
        idx = int(entry.get("level_idx"))
    except (TypeError, ValueError):
        return None
    if not (0 <= idx < len(levels)):
        return None
    lv = levels[idx]
    band = lv["band"]
    target = _int(entry.get("target"))
    out = dict(entry)
    out.update({
        "family": fam["family"],
        "exercise_id": lv["exercise_id"],
        "level_idx": idx,
        "axis": lv["axis"],
        "sets": _int(entry.get("sets")) or int(lv["sets"]),
        "target": max(int(band["lo"]), min(int(band["hi"]), target)) if target else int(band["lo"]),
        "tempo_level": max(0, int(_num(entry.get("tempo_level")) or 0)),
        "added_kg": max(0.0, float(_num(entry.get("added_kg")) or 0.0)),
        "top_streak": max(0, int(_num(entry.get("top_streak")) or 0)),
        "vh_streak": max(0, int(_num(entry.get("vh_streak")) or 0)),
    })
    out.setdefault("pending_promotion", None)
    out.setdefault("last_session_date", None)
    return out


def _seed_entry(row: Mapping[str, Any], fam: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    src = row.get("source")
    if src not in ("history", "test") or row.get("level_idx") is None:
        return None
    entry: Dict[str, Any] = {
        "level_idx": int(row["level_idx"]),
        "sets": row.get("sets"),
        "target": row.get("target"),
        "source": "seed_history" if src == "history" else "seed_test",
        "seeded_from": copy.deepcopy(row.get("evidence") or row.get("seeded_from")),
        "last_session_date": (row.get("evidence") or {}).get("date") if src == "history" else None,
    }
    if row.get("ramp"):
        ramp = dict(row["ramp"])
        entry["ramp"] = {"sessions_left": int(ramp.get("sessions") or 0),
                         "then_level": ramp.get("then_level"), "then_target": ramp.get("then_target")}
    return _normalize(entry, fam)


def tested(state: Mapping[str, Any], ref_date: DateLike) -> bool:
    return bl.tested_gate(state, ref_date)


def entries_for(
    state: Mapping[str, Any], ref_date: DateLike, *,
    equipment: Optional[Iterable[str]] = None, require_tested: bool = True,
    archived_weeks: Any = None,
) -> Dict[str, Dict[str, Any]]:
    """``{family: entry}`` on ``ref_date``: the persisted entry when present,
    else the read-time seed (history / L-sit test). Empty for an untested
    athlete when ``require_tested`` (the default): no consumer changes."""
    if require_tested and not tested(state, ref_date):
        return {}
    fams = _families()
    out: Dict[str, Dict[str, Any]] = {}
    seed = bl.seed_levels(state, ref_date, equipment=equipment, archived_weeks=archived_weeks)
    persisted = _persisted(state)
    for row in seed.get("families") or []:
        name = str(row.get("family"))
        fam = fams.get(name)
        if fam is None or row.get("source") == "not_applicable":
            continue
        p = persisted.get(name)
        if isinstance(p, Mapping):
            e = _normalize(p, fam)
            if e is not None:
                out[name] = e
                continue
        e = _seed_entry(row, fam)
        if e is not None:
            out[name] = e
    return out


def effective_entry(entry: Mapping[str, Any], fam: Mapping[str, Any], ref_date: DateLike) -> Dict[str, Any]:
    """R11 re-entry: a gap above the family window (120 d, 60 d for skills)
    since the last session drops one level, at the bottom of its band."""
    out = dict(entry)
    last = _iso(entry.get("last_session_date"))
    ref = _iso(ref_date)
    if not last or not ref:
        return out
    gap = (_as_date(ref) - _as_date(last)).days
    if gap <= _skill_window(fam):
        return out
    idx = max(0, int(entry["level_idx"]) - 1)
    lv = _levels(fam)[idx]
    out.update({"level_idx": idx, "exercise_id": lv["exercise_id"], "axis": lv["axis"],
                "sets": int(lv["sets"]), "target": int(lv["band"]["lo"]), "tempo_level": 0,
                "added_kg": 0.0, "top_streak": 0, "vh_streak": 0, "reentry": {"gap_days": gap}})
    return out


# ---------------------------------------------------------------------------
# Dose
# ---------------------------------------------------------------------------

def dose_for(entry: Mapping[str, Any], fam: Mapping[str, Any], *, phase: Optional[str] = None,
             level_idx: Optional[int] = None) -> Dict[str, Any]:
    """The prescription of an entry (or, with ``level_idx`` below the entry's
    level, of a lower level the athlete has mastered: top of its band)."""
    levels = _levels(fam)
    idx = int(entry["level_idx"]) if level_idx is None else int(level_idx)
    lv = levels[idx]
    band = lv["band"]
    own = level_idx is None or int(level_idx) == int(entry["level_idx"])
    sets = int(entry.get("sets") or lv["sets"]) if own else int(lv["sets"])
    target = int(entry.get("target") or band["lo"]) if own else int(band["hi"])
    frozen = is_frozen(phase)
    if frozen:
        sets = max(FROZEN_MIN_SETS, sets - 1)
    out: Dict[str, Any] = {
        "family": fam["family"],
        "exercise_id": lv["exercise_id"],
        "level_idx": idx,
        "n_levels": len(levels),
        "axis": lv["axis"],
        "sets": sets,
        "target": target,
        "reps": target if lv["axis"] == "reps" else None,
        "work_seconds": target if lv["axis"] == "seconds" else None,
        "rest_s": int(lv.get("rest_s") or 60),
        "band": dict(band),
        "tempo_ecc_s": None,
        "added_kg": 0.0,
        "frozen": frozen,
        "mastered_level": not own,
        "next_exercise_id": levels[idx + 1]["exercise_id"] if idx + 1 < len(levels) else None,
    }
    if own:
        term = fam.get("terminal") or {}
        steps = term.get("tempo_steps") or []
        tl = int(entry.get("tempo_level") or 0)
        if tl > 0 and steps:
            out["tempo_ecc_s"] = int(steps[min(tl, len(steps)) - 1].get("ecc_s") or 0) or None
        out["added_kg"] = float(entry.get("added_kg") or 0.0)
    out["summary"] = dose_summary(out)
    return out


def dose_summary(dose: Mapping[str, Any]) -> str:
    unit = " s" if dose.get("axis") == "seconds" else ""
    s = f"{dose['sets']}x{dose['target']}{unit}"
    if dose.get("tempo_ecc_s"):
        s += f", {dose['tempo_ecc_s']} s eccentric"
    if dose.get("added_kg"):
        s += f", +{dose['added_kg']:g} kg"
    return s


def ladder_info(entry: Mapping[str, Any], fam: Mapping[str, Any], dose: Mapping[str, Any], *,
                row_level: Optional[int] = None, lower_back_zone: bool = False) -> Dict[str, Any]:
    """What the client renders next to a ladder row (badge + proposal)."""
    levels = _levels(fam)
    idx = int(dose["level_idx"])
    band = dose["band"]
    unit = " s" if dose["axis"] == "seconds" else ""
    info: Dict[str, Any] = {
        "family": fam["family"],
        "family_label": fam.get("label"),
        "level_idx": idx,
        "n_levels": len(levels),
        "level_name": _exercise_name(levels[idx]["exercise_id"]),
        "band": f"{band['lo']}–{band['hi']}{unit}",
        "dose": dose["summary"],
        "next_exercise_id": dose.get("next_exercise_id"),
        "next_name": _exercise_name(dose.get("next_exercise_id")) or None,
        "frozen": bool(dose.get("frozen")),
        "manual_only_next": False,
        "gate": None,
        "proposal": None,
        "entry_level_idx": int(entry["level_idx"]),
        "source": entry.get("source"),
    }
    nxt = idx + 1
    if nxt < len(levels):
        lb = _lower_back_from(fam)
        info["manual_only_next"] = lb is not None and nxt >= lb and not lower_back_zone
        for g in fam.get("gates") or []:
            if int(g.get("level", -1)) == nxt:
                info["gate"] = g.get("requires_accessory_id") or g.get("requires_note")
    # Proposal: the row sits below the athlete's level, or the state proposes
    # the next level (custom 'ladder' rows only promote on a tap).
    rl = idx if row_level is None else int(row_level)
    pend = entry.get("pending_promotion") if isinstance(entry.get("pending_promotion"), Mapping) else None
    if rl < int(entry["level_idx"]):
        to = int(entry["level_idx"])
        info["proposal"] = {"kind": "switch", "to_level_idx": to, "to_exercise_id": levels[to]["exercise_id"],
                            "to_name": _exercise_name(levels[to]["exercise_id"])}
    elif pend and rl == int(entry["level_idx"]):
        to = int(pend.get("to_level_idx"))
        if 0 <= to < len(levels):
            info["proposal"] = {"kind": "promotion", "to_level_idx": to,
                                "to_exercise_id": levels[to]["exercise_id"],
                                "to_name": _exercise_name(levels[to]["exercise_id"])}
    return info


def measure_for_axis(axis: str) -> str:
    return MEASURE_BW_HOLD if axis == "seconds" else MEASURE_BW_REPS


# ---------------------------------------------------------------------------
# next_state (R0-R12)
# ---------------------------------------------------------------------------

_MESSAGES = {
    "hold": "Not rated: the level stays as it is.",
    "frozen": "Performance phase: doses frozen.",
    "manual_only": "Next level is manual only (no lower-back zone configured).",
    "handoff": "Top of the ladder: move on to the loaded variant.",
    "cap": "Top of the ladder: hold the top of the band.",
    "floor_warning": "Two very hard sessions at your floor level: check recovery.",
}


def outcome_message(outcome: Mapping[str, Any], new: Mapping[str, Any], fam: Mapping[str, Any],
                    phase: Optional[str]) -> str:
    kind = outcome.get("kind")
    if kind in _MESSAGES:
        return _MESSAGES[kind]
    dose = dose_for(new, fam, phase=phase)
    if kind == "promoted":
        return f"Promoted: {_exercise_name(new['exercise_id'])} {dose['summary']}"
    if kind == "promotion_proposed":
        to = (new.get("pending_promotion") or {}).get("exercise_id")
        return f"Ready for {_exercise_name(to)}: confirm in the session"
    if kind == "top_streak":
        left = int(outcome.get("sessions_left") or 1)
        return f"{left} more session{'s' if left != 1 else ''} at the top to move up"
    if kind in ("tempo_up",):
        return f"Last level: {dose['summary']}"
    if kind == "level_down":
        return f"Back to {_exercise_name(new['exercise_id'])} {dose['summary']}"
    return f"Next time: {dose['summary']}"


def next_state(
    entry: Mapping[str, Any], fam: Mapping[str, Any], *,
    label: Optional[str], completed: Optional[bool] = True, measured: Optional[float] = None,
    test_hold: bool = False, phase: Optional[str] = None, ref_date: DateLike,
    custom: bool = False, lower_back_zone: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """One session of feedback on one family → (new entry, outcome).

    ``label`` None = not rated (A295); with no measure either, the state is
    returned UNCHANGED (R3: a legacy 'ok' is not an answer). ``measured``:
    min reps across the sets (reps axis) or min seconds held (seconds axis).
    """
    levels = _levels(fam)
    cur = effective_entry(entry, fam, ref_date)
    if label is None and measured is None:
        # Not rated (or skipped: completed false with nothing else) → no step.
        return dict(entry), {"kind": "hold"}
    new: Dict[str, Any] = dict(cur)
    new.pop("reentry", None)
    idx = int(cur["level_idx"])
    lv = levels[idx]
    band = lv["band"]
    lo, hi, step = int(band["lo"]), int(band["hi"]), int(band["step"])
    max_reps, max_s = _caps()
    cap = max_s if lv["axis"] == "seconds" else max_reps
    target = int(cur["target"])
    frozen = is_frozen(phase)
    delta = LABEL_STEPS.get(str(label or ""), 0)

    # R0: the measure is the base, the label only decides the delta.
    if measured is not None:
        m = float(measured)
        if lv["axis"] == "seconds":
            if test_hold:
                base = m * TEST_HOLD_FACTOR
            else:
                base = m if m < target else float(target)
        else:
            base = m
        raw = int(round(base)) + delta * step
    else:
        raw = target + delta * step

    failed = label == "very_hard" or (completed is False and (label is not None or measured is not None))
    outcome: Dict[str, Any] = {"kind": "hold"}
    if failed:
        vh = int(cur.get("vh_streak") or 0) + (1 if label == "very_hard" else 0)
        new["vh_streak"] = vh
        new["top_streak"] = 0
        term = fam.get("terminal") or {}
        if int(cur.get("tempo_level") or 0) > 0:
            new["tempo_level"] = int(cur["tempo_level"]) - 1
            outcome = {"kind": "tempo_down"}
        elif float(cur.get("added_kg") or 0) > 0:
            dist = _num(term.get("load_step_kg_distal")) or 1.0
            dec = max(dist, float(cur["added_kg"]) * LOAD_DOWN_PCT)
            new["added_kg"] = max(0.0, _round_half(float(cur["added_kg"]) - dec))
            outcome = {"kind": "load_down"}
        else:
            at_lo_before = target <= lo
            t = raw if measured is not None else target - 2 * step
            drop = vh >= VH_STREAK_LEVEL_DOWN or (completed is False and at_lo_before)
            floor = fam.get("floor_level_advanced")
            min_idx = int(floor) if floor is not None and idx >= int(floor) else 0
            if drop and idx - 1 >= min_idx:
                plv = levels[idx - 1]
                pb = plv["band"]
                new.update({"level_idx": idx - 1, "exercise_id": plv["exercise_id"], "axis": plv["axis"],
                            "sets": int(plv["sets"]), "target": max(int(pb["lo"]), int(pb["hi"]) - int(pb["step"])),
                            "vh_streak": 0, "pending_promotion": None})
                outcome = {"kind": "level_down"}
            elif drop:
                new["target"] = lo
                outcome = {"kind": "floor_warning"}
            else:
                new["target"] = max(lo, min(hi, t))
                outcome = {"kind": "step_down"}
    else:
        new["vh_streak"] = 0
        if frozen:
            # R-PHASE: regressions stay, nothing goes up.
            raw = min(raw, target)
        if raw > hi or raw > cap:
            new["target"] = hi
            top = int(cur.get("top_streak") or 0) + 1
            new["top_streak"] = top
            need = int(lv.get("advance_sessions") or 1)
            if top < need:
                outcome = {"kind": "top_streak", "sessions_left": need - top}
            else:
                new, outcome = _advance(new, fam, idx, frozen=frozen, custom=custom,
                                        lower_back_zone=lower_back_zone, ref_date=ref_date)
        else:
            new["top_streak"] = 0
            new["target"] = max(lo, min(hi, raw))
            if raw > target:
                outcome = {"kind": "step_up"}
            elif raw < target:
                outcome = {"kind": "step_down"}
            elif frozen:
                outcome = {"kind": "frozen"}
            else:
                outcome = {"kind": "hold"}
        # Seeded ramp (Copenhagen short → long): counts clean sessions.
        ramp = new.get("ramp") if isinstance(new.get("ramp"), Mapping) else None
        if ramp and label not in ("hard",) and outcome.get("kind") not in ("promoted", "promotion_proposed"):
            left = int(ramp.get("sessions_left") or 0) - 1
            if left > 0:
                new["ramp"] = {**ramp, "sessions_left": left}
            else:
                to = ramp.get("then_level")
                new.pop("ramp", None)
                if to is not None and not frozen and int(to) < len(levels):
                    new, outcome = _move_to(new, fam, int(to), ramp.get("then_target"),
                                            custom=custom, ref_date=ref_date, kind="ramp")
    new["last_session_date"] = _iso(ref_date)
    new["source"] = "feedback"
    return new, outcome


def _move_to(new: Dict[str, Any], fam: Mapping[str, Any], to: int, target: Any, *, custom: bool,
             ref_date: DateLike, kind: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    levels = _levels(fam)
    lv = levels[to]
    if custom:
        new["pending_promotion"] = {"to_level_idx": to, "exercise_id": lv["exercise_id"],
                                    "target": _int(target), "since": _iso(ref_date)}
        return new, {"kind": "promotion_proposed"}
    band = lv["band"]
    t = _int(target) or int(band["lo"])
    new.update({"level_idx": to, "exercise_id": lv["exercise_id"], "axis": lv["axis"], "sets": int(lv["sets"]),
                "target": max(int(band["lo"]), min(int(band["hi"]), t)), "tempo_level": 0, "added_kg": 0.0,
                "top_streak": 0, "vh_streak": 0, "pending_promotion": None})
    return new, {"kind": "promoted" if kind != "ramp" else "ramp"}


def _advance(new: Dict[str, Any], fam: Mapping[str, Any], idx: int, *, frozen: bool, custom: bool,
             lower_back_zone: bool, ref_date: DateLike) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """R6 promotion / R7 terminal, once ``advance_sessions`` are met."""
    levels = _levels(fam)
    if frozen:
        return new, {"kind": "frozen"}
    lv = levels[idx]
    band = lv["band"]
    lo, hi, step = int(band["lo"]), int(band["hi"]), int(band["step"])
    if idx + 1 < len(levels):
        if idx + 1 > auto_ceiling(fam, lower_back_zone):
            return new, {"kind": "manual_only"}
        return _move_to(new, fam, idx + 1, None, custom=custom, ref_date=ref_date, kind="promotion")
    # R7 terminal
    term = fam.get("terminal") or {}
    kind = term.get("kind")
    restart = max(lo, hi - TERMINAL_RESTART_STEPS * step)
    load_step = _num(term.get("load_step_kg_distal")) or _num(term.get("load_step_kg_upper")) or _num(term.get("load_step_kg_lower"))
    if kind == "tempo":
        steps = term.get("tempo_steps") or []
        tl = int(new.get("tempo_level") or 0)
        if tl < len(steps):
            new.update({"tempo_level": tl + 1, "target": restart, "top_streak": 0})
            return new, {"kind": "tempo_up"}
        if term.get("then") == "load" and load_step:
            new.update({"added_kg": _round_half(float(new.get("added_kg") or 0) + load_step),
                        "target": restart, "top_streak": 0})
            return new, {"kind": "load_up"}
        return new, {"kind": "cap"}
    if kind == "load" and load_step and not term.get("no_added_load"):
        new.update({"added_kg": _round_half(float(new.get("added_kg") or 0) + load_step),
                    "target": restart, "top_streak": 0})
        return new, {"kind": "load_up"}
    if kind == "handoff":
        return new, {"kind": "handoff", "handoff_exercise_id": term.get("handoff_exercise_id")}
    return new, {"kind": "cap", "then_exercise_ids": list(term.get("then_exercise_ids") or [])}


# ---------------------------------------------------------------------------
# Feedback (called by progression_v1.apply_feedback)
# ---------------------------------------------------------------------------

def _store(state: Dict[str, Any]) -> Dict[str, Any]:
    raw = state.get(STATE_KEY)
    if not isinstance(raw, dict):
        raw = {}
        state[STATE_KEY] = raw
    return raw


def _strip_private(entry: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in entry.items() if k != "_prev"}


def _dose_matches(item: Mapping[str, Any], dose: Mapping[str, Any]) -> bool:
    """A 'fixed' / unknown row moves the memory only when the dose it carried
    is the ladder's (sets and reps-or-seconds)."""
    sets = _int(item.get("prescribed_sets"))
    if dose["axis"] == "seconds":
        val = _int(item.get("prescribed_work_seconds")) or _int(item.get("work_seconds"))
    else:
        val = _int(item.get("prescribed_reps")) or _int(item.get("reps"))
    return sets == int(dose["sets"]) and val == int(dose["target"])


def item_measure(item: Mapping[str, Any], axis: str) -> Tuple[Optional[float], bool]:
    """(measured value, is_test_hold) of a ladder feedback item."""
    if axis == "seconds":
        v = _num(item.get("held_s"))
        return (v if v is not None and v > 0 else None), bool(item.get("held_to_failure"))
    v = _num(item.get("last_set_reps"))
    return (v if v is not None and v >= 0 else None), False


def apply_bw_item(
    updated: Dict[str, Any], item: Mapping[str, Any], *, rating: Optional[str], date_value: str,
    session_key: str, phase: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Move ``bw_progression`` for one ladder feedback item. Returns the
    outcome (with ``message``) when the item belongs to a ladder family the
    athlete has an entry for, ``None`` otherwise (the caller falls through).

    Rules (BW spec "DOVE NEL CODICE" b):
    - no entry (untested athlete, no persisted state) → no-op;
    - the item's level must be the entry's level (a mastered lower level, or a
      harder level the athlete chose, never moves the memory);
    - the row must carry the ladder dose (engine ``bw_ladder`` / custom
      'ladder' row, or a 'fixed' row whose dose equals the ladder's) or a
      measure; a 'fixed' row with another dose and no measure is ignored;
    - resubmitting the same session replays from the pre-session snapshot.
    """
    exercise_id = str(item.get("exercise_id") or "")
    hit = bl.family_of(exercise_id, date_value or None)
    if not hit:
        return None
    family, item_level = hit
    fam = family_doc(family)
    if fam is None or not date_value:
        return None
    store = _persisted(updated)
    persisted = store.get(family) if isinstance(store.get(family), Mapping) else None
    if persisted is not None:
        prev = persisted.get("_prev") if isinstance(persisted.get("_prev"), Mapping) else None
        if prev and prev.get("session_key") == session_key and isinstance(prev.get("entry"), Mapping):
            base = _normalize(prev["entry"], fam)  # B197: idempotent resubmission
        else:
            base = _normalize(persisted, fam)
    else:
        base = entries_for(updated, date_value).get(family)
    if base is None:
        return None
    eff = effective_entry(base, fam, date_value)
    if int(item_level) != int(eff["level_idx"]):
        return {"family": family, "kind": "other_level", "applied": False}
    measured, test_hold = item_measure(item, eff["axis"])
    ctx = str(item.get("bw_ladder") or "")
    dose = dose_for(eff, fam, phase=phase)
    if ctx not in ("engine", "ladder") and measured is None and not _dose_matches(item, dose):
        return {"family": family, "kind": "fixed_dose", "applied": False}
    completed = item.get("completed")
    completed = None if completed is None else bool(completed)
    new, outcome = next_state(
        base, fam, label=rating, completed=completed, measured=measured, test_hold=test_hold,
        phase=phase, ref_date=date_value, custom=(ctx == "ladder"),
        lower_back_zone=has_lower_back_zone(updated),
    )
    if outcome.get("kind") == "hold" and rating is None and measured is None:
        return {"family": family, "kind": "hold", "applied": False, "message": _MESSAGES["hold"]}
    outcome = dict(outcome)
    outcome["message"] = outcome_message(outcome, new, fam, phase)
    snap = _strip_private(base)
    new = _strip_private(new)
    new["last_outcome"] = {"kind": outcome["kind"], "message": outcome["message"], "date": _iso(date_value)}
    new["_prev"] = {"session_key": session_key, "entry": snap}
    _store(updated)[family] = new
    return {"family": family, "applied": True, **outcome}


# ---------------------------------------------------------------------------
# Router helpers
# ---------------------------------------------------------------------------

def attach_feedback_context(log_entry: Dict[str, Any], state: Mapping[str, Any],
                            target_date: Optional[str], target_sid: Optional[str]) -> None:
    """Tag each ladder feedback item with where its dose came from:
    ``engine`` (resolver wrote ``prescription.source == 'bw_ladder'``),
    ``ladder`` (custom row in progress_mode 'ladder') or ``fixed``.
    Looks the session up in the stored plan, then in the custom definition."""
    items = (log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
    if not items or not target_date or not target_sid:
        return
    tags: Dict[str, str] = {}

    def _scan(rows: Any, resolved: bool) -> None:
        for r in rows or []:
            if not isinstance(r, Mapping):
                continue
            eid = str(r.get("exercise_id") or "")
            if not eid or eid in tags:
                continue
            if resolved:
                if (r.get("prescription") or {}).get("source") == "bw_ladder":
                    tags[eid] = "engine"
            elif r.get("progress_mode") == "ladder":
                tags[eid] = "ladder"
            elif r.get("progress_mode") == "fixed":
                tags[eid] = "fixed"

    try:
        _d = _as_date(target_date)
        monday = date.fromordinal(_d.toordinal() - _d.weekday()).isoformat()
    except (TypeError, ValueError):
        monday = None
    plans = [(state.get("week_plans") or {}).get(monday) if monday else None, state.get("current_week_plan")]
    for plan in plans:
        for week in (plan or {}).get("weeks") or []:
            for day in week.get("days") or []:
                if day.get("date") != target_date:
                    continue
                for s in day.get("sessions") or []:
                    if s.get("session_id") != target_sid:
                        continue
                    _scan(s.get("exercises"), False)
                    _scan(s.get("exercise_instances"), True)
                    _scan(((s.get("resolved") or {}).get("resolved_session") or {}).get("exercise_instances"), True)
    if str(target_sid).startswith("custom_"):
        cs_id = str(target_sid)[len("custom_"):]
        for cs in state.get("custom_sessions") or []:
            if isinstance(cs, Mapping) and cs.get("id") == cs_id:
                _scan(cs.get("exercises"), False)
    for item in items:
        if not isinstance(item, dict):
            continue
        eid = str(item.get("exercise_id") or "")
        if eid in tags and not item.get("bw_ladder") and bl.family_of(eid, target_date):
            item["bw_ladder"] = tags[eid]


def resolve_custom_ladder_rows(state: Mapping[str, Any], exercises: Sequence[Mapping[str, Any]],
                               on: Any) -> List[Dict[str, Any]]:
    """Copies of custom rows; a row in ``progress_mode: 'ladder'`` on a ladder
    family the athlete has an entry for gets the ladder dose of ``on`` (the
    stored values move to ``stored_*``), ``progress_source: 'bw_ladder'``, the
    ``ladder`` badge / proposal and the bodyweight measure. The saved exercise
    is kept: only a tap on the proposal rewrites the row. Never mutates input."""
    rows = [dict(r) for r in exercises or [] if isinstance(r, Mapping)]
    if not on or not any(r.get("progress_mode") == "ladder" for r in rows):
        return rows
    entries = entries_for(state, on)
    if not entries:
        return rows
    phase = phase_on(state, on)
    lbz = has_lower_back_zone(state)
    seen: set = set()
    for r in rows:
        if r.get("progress_mode") != "ladder":
            continue
        hit = bl.family_of(str(r.get("exercise_id") or ""), on)
        if not hit:
            continue
        family, row_level = hit
        entry = entries.get(family)
        fam = family_doc(family)
        if entry is None or fam is None:
            continue
        eff = effective_entry(entry, fam, on)
        if row_level > int(eff["level_idx"]):
            # A harder level than the athlete's: the user's own dose stands.
            r["ladder"] = ladder_info(eff, fam, dose_for(eff, fam, phase=phase), row_level=row_level,
                                      lower_back_zone=lbz)
            r["ladder"]["above_level"] = True
            continue
        dose = dose_for(eff, fam, phase=phase, level_idx=None if row_level == int(eff["level_idx"]) else row_level)
        for k, v in (("sets", dose["sets"]), ("reps", dose["reps"]), ("work_seconds", dose["work_seconds"])):
            if r.get(k) != v:
                r[f"stored_{k}"] = r.get(k)
            r[k] = v
        r["rest_between_sets_seconds"] = r.get("rest_between_sets_seconds") or dose["rest_s"]
        r["progress_source"] = "bw_ladder"
        r["ladder"] = ladder_info(eff, fam, dose, row_level=row_level, lower_back_zone=lbz)
        if family in seen:
            r["ladder"]["proposal"] = None
        seen.add(family)
        if row_level == int(eff["level_idx"]):
            r["measure"] = measure_for_axis(dose["axis"])
    return rows


def attach_technique_measures(state: Mapping[str, Any], exercises: Sequence[Mapping[str, Any]],
                              on: Any) -> List[Dict[str, Any]]:
    """Tested athletes: the feet / falls drills carry their one-number measure
    (and the current technique level). Others: rows unchanged."""
    rows = [dict(r) for r in exercises or [] if isinstance(r, Mapping)]
    if not on or not tested(state, on):
        return rows
    for r in rows:
        kind = technique_measure_kind(str(r.get("exercise_id") or ""))
        if kind and not r.get("measure"):
            r["measure"] = kind
            r["technique_level"] = technique_level(state, "feet" if kind == MEASURE_FEET else "falls")
    return rows


# ---------------------------------------------------------------------------
# Manual edits: settings level and the custom promotion tap
# ---------------------------------------------------------------------------

def set_level(state: Dict[str, Any], family: str, level_idx: int, ref_date: DateLike, *,
              confirm: bool = False) -> Dict[str, Any]:
    """Settings 'down' / 'up' (source user_edit). More than one level above the
    current one needs ``confirm``. Lower-back levels are allowed here (manual).
    Raises ValueError on an unknown family / level."""
    fam = family_doc(family)
    if fam is None:
        raise ValueError(f"unknown family: {family}")
    levels = _levels(fam)
    if not (0 <= int(level_idx) < len(levels)):
        raise ValueError(f"level_idx out of range for {family}: {level_idx}")
    cur = entries_for(state, ref_date, require_tested=False).get(family)
    cur_idx = int(cur["level_idx"]) if cur else -1
    if int(level_idx) > cur_idx + 1 and not confirm:
        raise PermissionError("more than one level above the current one: confirm required")
    lv = levels[int(level_idx)]
    entry = {
        "level_idx": int(level_idx), "sets": int(lv["sets"]), "target": int(lv["band"]["lo"]),
        "tempo_level": 0, "added_kg": 0.0, "top_streak": 0, "vh_streak": 0,
        "pending_promotion": None, "last_session_date": (cur or {}).get("last_session_date"),
        "source": "user_edit", "edited_on": _iso(ref_date),
    }
    norm = _normalize(entry, fam)
    _store(state)[family] = norm
    return norm


def resolve_promotion(state: Dict[str, Any], family: str, *, accept: bool, ref_date: DateLike,
                      to_level_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """The custom proposal tap. ``accept`` with a pending promotion → the entry
    moves up (target at the bottom of the new band); a 'switch' proposal (row
    below the athlete's level) leaves the entry as it is. Decline clears the
    pending promotion and the top streak. Returns the new entry (or None)."""
    fam = family_doc(family)
    if fam is None:
        raise ValueError(f"unknown family: {family}")
    cur = entries_for(state, ref_date, require_tested=False).get(family)
    if cur is None:
        return None
    entry = _strip_private(cur)
    pend = entry.get("pending_promotion") if isinstance(entry.get("pending_promotion"), Mapping) else None
    if accept and pend and (to_level_idx is None or int(to_level_idx) == int(pend.get("to_level_idx"))):
        to = int(pend["to_level_idx"])
        lv = _levels(fam)[to]
        band = lv["band"]
        t = _int(pend.get("target")) or int(band["lo"])
        entry.update({"level_idx": to, "sets": int(lv["sets"]),
                      "target": max(int(band["lo"]), min(int(band["hi"]), t)),
                      "tempo_level": 0, "added_kg": 0.0, "top_streak": 0, "vh_streak": 0,
                      "pending_promotion": None, "source": "user_edit", "edited_on": _iso(ref_date)})
    elif not accept:
        entry.update({"pending_promotion": None, "top_streak": 0})
    norm = _normalize(entry, fam)
    _store(state)[family] = norm
    return norm


def rewrite_ladder_rows(rows: Any, family: str, to_level_idx: int, on: DateLike) -> int:
    """The promotion / switch tap rewrites, in place, the 'ladder' rows of
    ``family`` sitting BELOW ``to_level_idx`` to that level's exercise (the
    dose is read at play time). Returns how many rows changed."""
    fam = family_doc(family)
    if fam is None or not isinstance(rows, list):
        return 0
    lv = _levels(fam)[int(to_level_idx)]
    n = 0
    for r in rows:
        if not isinstance(r, dict) or r.get("progress_mode") != "ladder":
            continue
        hit = bl.family_of(str(r.get("exercise_id") or ""), on)
        if not hit or hit[0] != family or hit[1] >= int(to_level_idx):
            continue
        r["exercise_id"] = lv["exercise_id"]
        r["sets"] = int(lv["sets"])
        band = lv["band"]
        if lv["axis"] == "seconds":
            r["work_seconds"], r["reps"] = int(band["lo"]), None
        else:
            r["reps"], r["work_seconds"] = int(band["lo"]), None
        for k in ("name", "cues", "video_url", "notes", "category", "load_model", "alt_sides"):
            r.pop(k, None)
        n += 1
    return n


def ladder_view(state: Mapping[str, Any], ref_date: DateLike) -> Dict[str, Any]:
    """Settings / API view: every family with level, dose and flags."""
    entries = entries_for(state, ref_date, require_tested=False)
    gate = tested(state, ref_date)
    phase = phase_on(state, ref_date)
    lbz = has_lower_back_zone(state)
    rows = []
    for name, fam in _families().items():
        e = entries.get(name)
        if e is not None and (gate or e.get("source") in ("feedback", "user_edit")):
            eff = effective_entry(e, fam, ref_date)
            dose = dose_for(eff, fam, phase=phase)
            info = ladder_info(eff, fam, dose, lower_back_zone=lbz)
            rows.append({"family": name, "label": fam.get("label"), "active": True,
                         "exercise_id": eff["exercise_id"], "level_idx": eff["level_idx"],
                         "n_levels": len(_levels(fam)), "dose": dose["summary"], "source": e.get("source"),
                         "pending_promotion": e.get("pending_promotion"),
                         "last_outcome": e.get("last_outcome"), "ladder": info,
                         "levels": [{"level_idx": i, "exercise_id": lv["exercise_id"],
                                     "name": _exercise_name(lv["exercise_id"]),
                                     "manual_only": i > auto_ceiling(fam, lbz)}
                                    for i, lv in enumerate(_levels(fam))]})
        else:
            rows.append({"family": name, "label": fam.get("label"), "active": False, "level_idx": None,
                         "n_levels": len(_levels(fam))})
    return {"as_of": _iso(ref_date), "tested_gate": gate, "phase": phase, "frozen": is_frozen(phase),
            "families": rows, "technique": technique_view(state)}


# ---------------------------------------------------------------------------
# Resolver stage
# ---------------------------------------------------------------------------

def build_resolve_context(state: Optional[Mapping[str, Any]], target_date: Any,
                          phase: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """None (resolver unchanged, bit for bit) unless the athlete is tested on
    ``target_date``. ``entries`` may be empty (technique measures only)."""
    if not state or not target_date:
        return None
    try:
        on = _iso(target_date)
        if not on or not tested(state, on):
            return None
        entries = entries_for(state, on)
    except Exception:  # never let the ladder break a resolution
        return None
    return {"date": on, "entries": entries, "phase": phase or phase_on(state, on),
            "lower_back_zone": has_lower_back_zone(state), "used_families": set()}


def swap_plan(ctx: Optional[Mapping[str, Any]], exercise_id: str) -> Optional[Dict[str, Any]]:
    """For an engine pick on a ladder family: the levels to try, best first
    (the athlete's level, capped by R12, then downwards). None = no stage."""
    if not ctx:
        return None
    hit = bl.family_of(exercise_id, ctx["date"])
    if not hit:
        return None
    family, _lvl = hit
    if family in ctx["used_families"]:
        return None
    entry = ctx["entries"].get(family)
    fam = family_doc(family)
    if entry is None or fam is None:
        return None
    eff = effective_entry(entry, fam, ctx["date"])
    start = min(int(eff["level_idx"]), auto_ceiling(fam, ctx["lower_back_zone"]))
    order = list(range(start, -1, -1))
    return {"family": family, "entry": eff, "fam": fam, "order": order,
            "candidates": [_levels(fam)[i]["exercise_id"] for i in order]}


def stage_prescription(ctx: Mapping[str, Any], plan: Mapping[str, Any], level_idx: int,
                       merged: Dict[str, Any]) -> Dict[str, Any]:
    """Write the ladder dose into an instance prescription (in place) and
    return the audit block for ``suggested.bw_ladder``."""
    eff, fam = plan["entry"], plan["fam"]
    own = int(level_idx) == int(eff["level_idx"])
    dose = dose_for(eff, fam, phase=ctx["phase"], level_idx=None if own else level_idx)
    for k in ("sets_range", "reps_range", "work_seconds_range", "hold_seconds", "duration_seconds"):
        merged.pop(k, None)
    merged["sets"] = dose["sets"]
    merged["reps"] = dose["reps"]
    merged["work_seconds"] = dose["work_seconds"]
    merged["rest_between_sets_seconds"] = dose["rest_s"]
    if dose.get("tempo_ecc_s"):
        merged["tempo_eccentric_seconds"] = dose["tempo_ecc_s"]
        merged["tempo"] = f"{dose['tempo_ecc_s']} s eccentric"
    if dose.get("added_kg"):
        merged["added_load_kg"] = dose["added_kg"]
    merged["source"] = "bw_ladder"
    ctx["used_families"].add(plan["family"])
    info = ladder_info(eff, fam, dose, row_level=level_idx, lower_back_zone=ctx["lower_back_zone"])
    return {"ladder": info, "dose": {k: dose[k] for k in ("sets", "reps", "work_seconds", "rest_s",
                                                         "tempo_ecc_s", "added_kg", "frozen", "summary")},
            "measure": measure_for_axis(dose["axis"]) if own else None}


# ---------------------------------------------------------------------------
# Technique ladders (feet, falls) — minimal
# ---------------------------------------------------------------------------

def _tech_ladders() -> Dict[str, Dict[str, Any]]:
    return {str(t["ladder"]): t for t in (bl._load_file().get("technique_ladders") or [])}


def feet_drills() -> frozenset:
    t = _tech_ladders().get("feet") or {}
    out = set()
    for lv in t.get("levels") or []:
        out.update(str(d) for d in lv.get("drills") or [])
    return frozenset(out)


def technique_measure_kind(exercise_id: str) -> Optional[str]:
    if exercise_id in FALL_DRILLS:
        return MEASURE_FEAR
    if exercise_id in feet_drills():
        return MEASURE_FEET
    return None


def _tech_levels(ladder: str) -> List[str]:
    t = _tech_ladders().get(ladder) or {}
    return [str(lv["level"]) for lv in t.get("levels") or []]


def technique_level(state: Mapping[str, Any], ladder: str) -> Optional[str]:
    tech = _persisted(state).get(TECHNIQUE_KEY)
    if isinstance(tech, Mapping) and isinstance(tech.get(ladder), Mapping):
        return tech[ladder].get("level")
    return None


def technique_view(state: Mapping[str, Any]) -> Dict[str, Any]:
    tech = _persisted(state).get(TECHNIQUE_KEY)
    out = {}
    for name in ("feet", "falls"):
        e = tech.get(name) if isinstance(tech, Mapping) else None
        out[name] = dict(e) if isinstance(e, Mapping) else {"level": None, "tracked": False}
        out[name].pop("_prev", None)
    return out


def technique_next(entry: Optional[Mapping[str, Any]], ladder: str, value: float,
                   ref_date: DateLike) -> Tuple[Dict[str, Any], str]:
    """One session's number → (new technique entry, outcome kind)."""
    levels = _tech_levels(ladder)
    cur = dict(entry or {})
    if not cur.get("level") or cur.get("level") not in levels:
        cur.update({"level": levels[0], "good_streak": 0, "bad_streak": 0})
    i = levels.index(cur["level"])
    good = int(cur.get("good_streak") or 0)
    bad = int(cur.get("bad_streak") or 0)
    kind = "hold"
    if ladder == "feet":
        if value <= FEET_GOOD_MAX:
            good, bad = good + 1, 0
        elif value >= FEET_BAD_MIN:
            good, bad = 0, bad + 1
        else:
            good, bad = 0, 0
        if good >= TECH_STREAK and i + 1 < len(levels):
            i, good, kind = i + 1, 0, "promoted"
        elif bad >= TECH_STREAK and i > 0:
            i, bad, kind = i - 1, 0, "level_down"
    else:  # falls
        if value >= FEAR_BAD_MIN:
            good = 0
            if i > 0:
                i, kind = i - 1, "level_down"
        elif value <= FEAR_GOOD_MAX:
            good += 1
            if good >= TECH_STREAK and i + 1 < len(levels):
                i, good, kind = i + 1, 0, "promoted"
        else:
            good = 0
    cur.update({"level": levels[i], "good_streak": good, "bad_streak": bad,
                "last_value": value, "last_session_date": _iso(ref_date), "tracked": True})
    return cur, kind


def apply_technique_measures(updated: Dict[str, Any], items: Sequence[Mapping[str, Any]], *,
                             date_value: str, session_key: str) -> List[Dict[str, Any]]:
    """One number per ladder per session (the lowest readjustment count, the
    highest fear). Tested athletes only — the measure is only asked of them."""
    if not date_value or not tested(updated, date_value):
        return []
    feet_vals = [int(_num(i.get("sample_readjust"))) for i in items
                 if isinstance(i, Mapping) and _num(i.get("sample_readjust")) is not None
                 and str(i.get("exercise_id") or "") in feet_drills()]
    fear_vals = [int(_num(i.get("fear_max"))) for i in items
                 if isinstance(i, Mapping) and _num(i.get("fear_max")) is not None
                 and str(i.get("exercise_id") or "") in FALL_DRILLS]
    out = []
    store = _store(updated)
    tech = store.get(TECHNIQUE_KEY) if isinstance(store.get(TECHNIQUE_KEY), dict) else {}
    for ladder, vals, pick in (("feet", feet_vals, min), ("falls", fear_vals, max)):
        if not vals:
            continue
        cur = tech.get(ladder) if isinstance(tech.get(ladder), Mapping) else None
        prev = (cur or {}).get("_prev") if isinstance((cur or {}).get("_prev"), Mapping) else None
        base = prev.get("entry") if prev and prev.get("session_key") == session_key else cur
        base = {k: v for k, v in (base or {}).items() if k != "_prev"} or None
        new, kind = technique_next(base, ladder, float(pick(vals)), date_value)
        new["_prev"] = {"session_key": session_key, "entry": base}
        tech[ladder] = new
        out.append({"ladder": ladder, "kind": kind, "level": new["level"]})
    if out:
        store[TECHNIQUE_KEY] = tech
    return out


def session_outcomes(state: Mapping[str, Any], session_key: str) -> List[Dict[str, Any]]:
    """The ladder outcomes written by the feedback of ``session_key``
    (``date|session_id``) — what the client shows after the session."""
    out = []
    for name, e in sorted(_persisted(state).items()):
        if name == TECHNIQUE_KEY or not isinstance(e, Mapping):
            continue
        prev = e.get("_prev") if isinstance(e.get("_prev"), Mapping) else None
        if prev and prev.get("session_key") == session_key and isinstance(e.get("last_outcome"), Mapping):
            out.append({"family": name, "exercise_id": e.get("exercise_id"), **dict(e["last_outcome"])})
    tech = _persisted(state).get(TECHNIQUE_KEY)
    if isinstance(tech, Mapping):
        for name, e in sorted(tech.items()):
            prev = e.get("_prev") if isinstance(e, Mapping) and isinstance(e.get("_prev"), Mapping) else None
            if prev and prev.get("session_key") == session_key:
                out.append({"ladder": name, "kind": "technique", "level": e.get("level"),
                            "message": f"{name.capitalize()} ladder: level {e.get('level')}"})
    return out


def sanitize_item(item: Dict[str, Any], warnings: List[str]) -> None:
    """Router sanitisation of the A298 measures (drop + warn, never 4xx)."""
    eid = item.get("exercise_id")
    for key, hi, kind in (("held_s", HELD_S_MAX, float), ("sample_readjust", SAMPLE_READJUST_MAX, int),
                          ("fear_max", FEAR_MAX, int)):
        if key not in item:
            continue
        v = _num(item.get(key))
        ok = v is not None and 0 <= v <= hi and (kind is float or v == int(v))
        if key == "held_s" and v is not None and v <= 0:
            ok = False
        if not ok:
            warnings.append(f"{eid}: {key} {item.get(key)!r} dropped")
            item.pop(key, None)
        else:
            item[key] = kind(v)


__all__ = [
    "STATE_KEY", "LABEL_STEPS", "FROZEN_PHASES", "entries_for", "effective_entry", "dose_for",
    "next_state", "apply_bw_item", "attach_feedback_context", "resolve_custom_ladder_rows",
    "attach_technique_measures", "set_level", "resolve_promotion", "ladder_view",
    "build_resolve_context", "swap_plan", "stage_prescription", "technique_next",
    "apply_technique_measures", "technique_measure_kind", "sanitize_item", "auto_ceiling",
]
