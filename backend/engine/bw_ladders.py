"""C272 — bodyweight / technique ladders: loader and a READ-ONLY level seed.

Data: ``backend/catalog/progressions/v1/bw_ladders.json`` (16 bodyweight
families, 3 technique ladders, the try-hard measures, the protocols). The
exercises those ladders introduce carry role ``ladder`` / ``library`` and are
never selected by the engine (``catalog_roles.is_library_only``).

What this module does today — and what it does NOT:

- ``load_ladders()`` / ``family_index()`` / ``family_of()`` — the inverse index
  exercise_id → (family, level_idx). The exercises carry no ladder field: the
  ladder file is the single source (BW spec, "catalog_schema").
- ``seed_levels(state, ref_date, archived_weeks=...)`` — where an athlete
  stands on each family, derived at read time from the history (done
  sessions of the last 120 days, 60 for the skill families) or, failing that,
  from the L-sit test. It is what Claude Code reads (athlete_context) before
  writing a custom session. It NEVER writes state: there is no
  ``bw_progression`` key yet — the closed loop (R0-R12 of the BW spec, label
  steps, promotions) is a later A brief behind the schema STOP gate. When
  that key exists, its entry wins and is reported as ``source: "state"``.

Pure and deterministic: no ``date.today()``, the only time input is
``ref_date``; the only file read is the static ladder file (cached).
"""

from __future__ import annotations

import copy
import json
import os
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from backend.engine import retest_policy as rp
from backend.engine.stimulus import counted_entries, is_finger_hard_session, is_test_session, iter_plan_sessions

DateLike = Union[date, str]
ArchivedWeeks = Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]]

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LADDERS_PATH = os.path.join(_REPO_ROOT, "backend", "catalog", "progressions", "v1", "bw_ladders.json")

#: Labels that disqualify a history entry as "completed cleanly" (BW seed rule).
_BAD_LABELS = frozenset({"hard", "very_hard", "skipped"})
#: The L-sit test exercise and the assessment field it writes.
L_SIT_TEST_ID = "test_l_sit_hold"
L_SIT_FIELD = "l_sit_hold_seconds"
#: A test log older than this does not seed (same window as the tested gate).
TEST_MAX_AGE_D = 90


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_file() -> Dict[str, Any]:
    with open(LADDERS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_ladders() -> Dict[str, Any]:
    """The ladder document (a deep copy: callers may not mutate the cache)."""
    return copy.deepcopy(_load_file())


def _families(ladders: Optional[Mapping[str, Any]] = None) -> List[Mapping[str, Any]]:
    doc = ladders if ladders is not None else _load_file()
    return list(doc.get("families") or [])


def family_index(ladders: Optional[Mapping[str, Any]] = None) -> Dict[str, Tuple[str, int]]:
    """``{exercise_id: (family, level_idx)}`` over the bodyweight levels."""
    out: Dict[str, Tuple[str, int]] = {}
    for fam in _families(ladders):
        for lvl in fam.get("levels") or []:
            out[str(lvl["exercise_id"])] = (str(fam["family"]), int(lvl["level_idx"]))
    return out


def heavy_pull_exercise_ids(ladders: Optional[Mapping[str, Any]] = None) -> frozenset:
    """Bodyweight exercises the ladder file declares a heavy pull (C272 review).

    A family with ``heavy_pull`` contributes its levels from
    ``heavy_pull_from_level`` on; a family heavy from level 0 also contributes
    its variants and its terminal ``then_exercise_ids`` (front lever: raise,
    row, negative). ``retest_policy.is_heavy_pulling_session`` does not read
    these (it is load-based and engine-wide); ``athlete_context`` adds them to
    the heavy-pull days of a TESTED athlete, which is what makes "conta come
    tirata pesante" true in the rendered context."""
    out = set()
    for fam in _families(ladders):
        if not fam.get("heavy_pull"):
            continue
        start = int(fam.get("heavy_pull_from_level") or 0)
        out.update(str(lv["exercise_id"]) for lv in fam.get("levels") or [] if int(lv["level_idx"]) >= start)
        if start == 0:
            out.update(str(v) for v in fam.get("variants") or [])
            out.update(str(v) for v in (fam.get("terminal") or {}).get("then_exercise_ids") or [])
    return frozenset(out)


def carries_heavy_bw_pull(session: Mapping[str, Any], ids: Optional[Iterable[str]] = None) -> bool:
    """True when the session (logged entries when done, else the plan — the
    ``stimulus.counted_entries`` rule) carries a ladder heavy-pull exercise."""
    want = frozenset(ids) if ids is not None else heavy_pull_exercise_ids()
    entries, _origin = counted_entries(session)
    return any(str(e.get("exercise_id") or "") in want for e in entries)


def _as_date(value: DateLike) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def family_of(exercise_id: Optional[str], as_of: Optional[DateLike] = None,
              ladders: Optional[Mapping[str, Any]] = None) -> Optional[Tuple[str, int]]:
    """The (family, level_idx) of an exercise logged on ``as_of``.

    History aliases map an exercise id onto a ladder level: ``hanging_leg_raise``
    counts as ``toes_to_bar``, because its catalog note says "straight legs to
    bar" (C272 review: that note is left unchanged for every user; the
    to-horizontal level is ``hanging_leg_raise_horizontal``). An alias without
    ``before`` holds for every log; one with ``before`` (ISO date) only for logs
    before that date, and only when ``as_of`` is given."""
    if not exercise_id:
        return None
    doc = ladders if ladders is not None else _load_file()
    eid = str(exercise_id)
    d = _as_date(as_of).isoformat() if as_of is not None else None
    for alias in doc.get("history_aliases") or []:
        if alias.get("exercise_id") != eid:
            continue
        before = alias.get("before")
        if before is None or (d is not None and d < str(before)):
            eid = str(alias["counts_as"])
            break
    return family_index(doc).get(eid)


# ---------------------------------------------------------------------------
# Dose helpers
# ---------------------------------------------------------------------------

def _int(value: Any) -> Optional[int]:
    """First integer of a dose value ("4-6" → 4, 8.0 → 8); ``None`` if absent."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    head = str(value).strip().split("-")[0].strip()
    try:
        n = int(float(head))
    except ValueError:
        return None
    return n if n > 0 else None


def _planned_twin(session: Mapping[str, Any], exercise_id: str) -> Mapping[str, Any]:
    """The planned row of ``exercise_id`` in a session (custom ``exercises`` or
    resolved instances) — the prescribed dose when the logged row lacks it."""
    for e in session.get("exercises") or []:
        if isinstance(e, Mapping) and str(e.get("exercise_id") or "") == exercise_id:
            return e
    resolved = (session.get("resolved") or {}).get("resolved_session") or {}
    for e in resolved.get("exercise_instances") or []:
        if isinstance(e, Mapping) and str(e.get("exercise_id") or "") == exercise_id:
            return e
    return {}


def _dose_of(entry: Mapping[str, Any], twin: Mapping[str, Any], axis: str) -> Optional[int]:
    """Reps or seconds of one set. Logged ``completed_reps`` is NOT used: the
    player writes the set count there (feedback-items.ts, BW spec)."""
    key = "work_seconds" if axis == "seconds" else "reps"
    for src in (entry, entry.get("prescription") or {}, twin, twin.get("prescription") or {}):
        if isinstance(src, Mapping):
            v = _int(src.get(key))
            if v is not None:
                return v
    return None


def _sets_of(entry: Mapping[str, Any], twin: Mapping[str, Any]) -> Optional[int]:
    for src in (entry, entry.get("prescription") or {}, twin, twin.get("prescription") or {}):
        if isinstance(src, Mapping):
            v = _int(src.get("sets"))
            if v is not None:
                return v
    return None


def _clamp_target(value: int, band: Mapping[str, Any]) -> int:
    return max(int(band["lo"]), min(int(band["hi"]), int(value)))


# ---------------------------------------------------------------------------
# Seed (read-only)
# ---------------------------------------------------------------------------

def tested_gate(state: Mapping[str, Any], ref_date: DateLike) -> bool:
    """The BW "tested athlete" gate: an official max with a test log < 90 days
    on the finger or the pulling protocol (``retest_policy.is_tested``)."""
    for proto in (rp.PROTOCOL_HANG_7S, rp.PROTOCOL_HANG_5S, rp.PROTOCOL_PULLUP_2RM):
        try:
            if rp.is_tested(state, proto, ref_date):
                return True
        except Exception:  # pragma: no cover - a malformed state is "untested"
            continue
    return False


def _l_sit_test(state: Mapping[str, Any], ref: date, archived_weeks: ArchivedWeeks) -> Optional[Dict[str, Any]]:
    """The L-sit value with the date of its test log (< 90 days), or None.

    ``assessment.tests.l_sit_hold_seconds`` carries no date
    (``tests_source`` says "measured"): the date comes from the done session
    that logged ``test_l_sit_hold``. No log in the window → no seed."""
    value = ((state.get("assessment") or {}).get("tests") or {}).get(L_SIT_FIELD)
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    if value is None:
        return None
    since = ref - timedelta(days=TEST_MAX_AGE_D)
    last: Optional[str] = None
    for d, s, _src in iter_plan_sessions(state, archived_weeks):
        if s.get("status") != "done":
            continue
        dd = _as_date(d)
        if not (since <= dd <= ref):
            continue
        entries, _origin = counted_entries(s)
        if any(str(e.get("exercise_id") or "") == L_SIT_TEST_ID for e in entries):
            last = max(filter(None, [last, d]))
    if last is None:
        return None
    return {"test": L_SIT_FIELD, "value": value, "log_date": last}


def _history(state: Mapping[str, Any], ref: date, archived_weeks: ArchivedWeeks,
             doc: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Per family: the highest level completed cleanly in the window, with
    the latest dose logged at that level."""
    seed = doc.get("seed_rules") or {}
    win = int(seed.get("history_window_days") or 120)
    win_skill = int(seed.get("skill_family_history_window_days") or 60)
    fams = {str(f["family"]): f for f in _families(doc)}
    best: Dict[str, Dict[str, Any]] = {}
    for d, s, _src in iter_plan_sessions(state, archived_weeks):
        if s.get("status") != "done" or is_test_session(s):
            continue
        dd = _as_date(d)
        if dd > ref:
            continue
        entries, origin = counted_entries(s)
        for e in entries:
            ex = str(e.get("exercise_id") or "")
            hit = family_of(ex, dd, doc)
            if not hit:
                continue
            family, idx = hit
            fam = fams[family]
            window = win_skill if fam.get("skill_family") else win
            if (ref - dd).days > window:
                continue
            label = str(e.get("feedback_label") or "")
            if label in _BAD_LABELS:
                continue
            lvl = fam["levels"][idx]
            twin = _planned_twin(s, ex)
            dose = _dose_of(e, twin, lvl["axis"])
            row = {"level_idx": idx, "date": d, "exercise_id": ex, "dose": dose,
                   "sets": _sets_of(e, twin), "label": label or None, "evidence": origin}
            cur = best.get(family)
            if cur is None or (idx, d) > (cur["level_idx"], cur["date"]):
                best[family] = row
    return best


def _row(fam: Mapping[str, Any], idx: Optional[int], *, source: str, target: Optional[int] = None,
         sets: Optional[int] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    levels = fam.get("levels") or []
    out: Dict[str, Any] = {
        "family": fam["family"],
        "label": fam.get("label"),
        "source": source,
        "n_levels": len(levels),
        "level_idx": idx,
        "exercise_id": None,
        "next_exercise_id": None,
        "axis": fam.get("axis_default"),
        "sets": None,
        "target": None,
        "band": None,
        "at_top_of_band": None,
        "heavy_pull": bool(fam.get("heavy_pull")) and (idx is None or idx >= int(fam.get("heavy_pull_from_level") or 0)),
        "hanging": bool(fam.get("hanging")) and (idx is None or idx >= int(fam.get("hanging_from_level") or 0)),
        "manual_only": False,
        "gate": None,
    }
    if idx is not None:
        lvl = levels[idx]
        band = lvl["band"]
        out.update({
            "exercise_id": lvl["exercise_id"],
            "next_exercise_id": levels[idx + 1]["exercise_id"] if idx + 1 < len(levels) else None,
            "axis": lvl["axis"],
            "sets": sets or lvl["sets"],
            "target": _clamp_target(target, band) if target is not None else int(band["lo"]),
            "band": dict(band),
        })
        lb = fam.get("lower_back_risk_from_level")
        out["manual_only"] = lb is not None and idx >= int(lb)
        for g in fam.get("gates") or []:
            if int(g.get("level", -1)) == idx:
                out["gate"] = g.get("requires_accessory_id") or g.get("requires_note")
    if extra:
        out.update(extra)
    return out


def seed_levels(state: Mapping[str, Any], ref_date: DateLike, *, archived_weeks: ArchivedWeeks = None,
                equipment: Optional[Iterable[str]] = None,
                ladders: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Where the athlete stands on each bodyweight family on ``ref_date``.

    Order (BW selection rules): persisted state → tested gate → history →
    L-sit test → none. Untested athletes get ``source: "catalog"`` on every
    family (no seed: the catalog dose applies, exactly as today).

    ``equipment`` (optional): keys available to the athlete; a test seed that
    needs equipment (the dragon flag needs a bench) is skipped without it.
    """
    doc = ladders if ladders is not None else _load_file()
    ref = _as_date(ref_date)
    persisted = state.get("bw_progression") if isinstance(state.get("bw_progression"), Mapping) else {}
    gate = tested_gate(state, ref)
    pulling_tested = False
    try:
        pulling_tested = rp.is_tested(state, rp.PROTOCOL_PULLUP_2RM, ref)
    except Exception:  # pragma: no cover
        pulling_tested = False
    eq = set(equipment) if equipment is not None else None
    hist = _history(state, ref, archived_weeks, doc) if gate else {}
    l_sit = _l_sit_test(state, ref, archived_weeks) if gate else None

    rows: List[Dict[str, Any]] = []
    for fam in _families(doc):
        name = str(fam["family"])
        if fam.get("eligibility") == "untested_pulling_only" and pulling_tested:
            rows.append(_row(fam, None, source="not_applicable",
                             extra={"why": "tested 2RM: the pull stays weighted_pullup with the anchored load"}))
            continue
        p = persisted.get(name) if isinstance(persisted, Mapping) else None
        if isinstance(p, Mapping) and p.get("level_idx") is not None:
            idx = int(p["level_idx"])
            if 0 <= idx < len(fam["levels"]):
                rows.append(_row(fam, idx, source="state", target=_int(p.get("target")), sets=_int(p.get("sets")),
                                 extra={"last_session_date": p.get("last_session_date")}))
                continue
        if not gate:
            rows.append(_row(fam, None, source="catalog"))
            continue
        h = hist.get(name)
        if h:
            lvl = fam["levels"][h["level_idx"]]
            step = int(lvl["band"]["step"])
            dose = h["dose"]
            target = (dose - step) if dose is not None else None
            rows.append(_row(fam, h["level_idx"], source="history", target=target, sets=h["sets"], extra={
                "evidence": {k: h[k] for k in ("date", "exercise_id", "dose", "sets", "label", "evidence")},
                "at_top_of_band": dose is not None and dose >= int(lvl["band"]["hi"]),
            }))
            continue
        seeded = None
        if l_sit is not None:
            for rule in fam.get("entry_seed") or []:
                if rule.get("test") != l_sit["test"]:
                    continue
                v = l_sit["value"]
                if v < float(rule.get("min", float("-inf"))):
                    continue
                if rule.get("max") is not None and v >= float(rule["max"]):
                    continue
                if rule.get("requires_equipment") and eq is not None and rule["requires_equipment"] not in eq:
                    continue
                tft = rule.get("target_from_test") or {}
                if tft.get("divisor"):
                    target = int(round(v / float(tft["divisor"])))
                elif tft.get("factor"):
                    target = int(round(v * float(tft["factor"])))
                else:
                    target = _int(rule.get("target"))
                extra = {"seeded_from": dict(l_sit)}
                if rule.get("ramp"):
                    extra["ramp"] = dict(rule["ramp"])
                seeded = _row(fam, int(rule["level"]), source="test", target=target, extra=extra)
                break
        rows.append(seeded or _row(fam, None, source="none"))
    return {
        "as_of": ref.isoformat(),
        "tested_gate": gate,
        "l_sit_test": l_sit,
        "families": rows,
        "note": ("read-only seed (C272): history = last clean dose − 1 step; the closed loop "
                 "(label steps, promotions) arrives with the bodyweight-progression A brief"),
    }


def technique_library(catalog: Mapping[str, Mapping[str, Any]],
                      ladders: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """The technique / positioning / try-hard / pocket drills (role ``library``)
    with their measure, plus the technique ladders and protocols."""
    doc = ladders if ladders is not None else _load_file()
    drills = []
    for eid in sorted(catalog):
        ex = catalog[eid]
        roles = ex.get("role") or []
        if isinstance(roles, str):
            roles = [roles]
        if "library" not in roles:
            continue
        drills.append({
            "exercise_id": eid,
            "name": ex.get("name"),
            "recency_group": ex.get("recency_group"),
            "measure": ex.get("measure"),
            # C272 review: the SAME definition the guards use, so the
            # "(dita-hard)" label never promises a guard the engine skips.
            "finger_hard": is_finger_hard_session({"exercises": [{"exercise_id": eid}]}),
            "equipment": sorted(set(ex.get("equipment_required") or []) | set(ex.get("equipment_required_any") or [])),
        })
    ladders_view = []
    for t in doc.get("technique_ladders") or []:
        ladders_view.append({
            "ladder": t.get("ladder"),
            "label": t.get("label"),
            "levels": [{"level": lv.get("level"), "drills": list(lv.get("drills") or [])} for lv in t.get("levels") or []],
            "advance": t.get("advance"),
            "regress": t.get("regress"),
            "measure": t.get("measure"),
        })
    return {
        "drills": drills,
        "technique_ladders": ladders_view,
        "protocols": sorted((doc.get("protocols") or {}).keys()),
        "try_hard": dict(doc.get("try_hard") or {}),
    }
