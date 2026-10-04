"""B364 — official max vs working load: the single ``anchored_load``.

The athlete's MAX (official) and the load they TRAIN with (working load) are
two different numbers:

- **Official max** = ``tests.*`` / ``baselines``, written ONLY by test logs
  (``progression_v1._update_test_from_log``). Read through
  ``retest_policy.official_max`` — the freshest test, hang durations converted.
- **Working load** = ``working_loads.entries[]``, written by feedback. It moves
  in kg steps from the load actually used; it never touches the max and never
  schedules a test.

``anchored_load`` turns both into the prescription for the four anchored
exercises (weighted_pullup, weighted_chinup, max_hang_5s, max_hang_7s). Every
consumer — planned sessions (``inject_targets``), the body-part picker, the
custom-session builder proposal, custom sessions resolved at read time, the
coach composer, the deterministic ad-hoc builder, the coach prompt — calls this
one function, so the same date gives the same number on every screen.

Scope (DECISIONS 2026-10-04): the anchor rules apply ONLY to a TESTED baseline
(``retest_policy.is_tested``: source test/test_session, < 90 days). For anyone
else ``anchored_load`` returns ``None`` and the caller keeps its pre-B364 path,
bit for bit.

Clamp order (one place, documented because R4's pain hook depends on it):
  starting point (working load normalised, or phase target)
  → structural cap (Prilepin band + (r+2)RM for pulls, 3 s of reserve + phase
    cap for hangs) × re-entry factor
  → pain (−10 %, pain cap)            [read-only hook, R4 writes pain_blocks]
  → guards (heavy-pull week, same-session finger work, finger-hard yesterday)
  → floor_eff = min(phase floor, cap_eff)   (the floor never lifts the cap)
  → fatigue (3 hard in 14 days → floor)
Rounding: cap DOWN, floor UP, load to the nearest half kilo.

Pure and deterministic: never writes state, never calls ``date.today()``.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from backend.engine import retest_policy as rp
from backend.engine.stimulus import (
    FAMILY_FINGER_MAX,
    FAMILY_PULLING_MAX,
    exposures,
    finger_hard_days,
    logged_entry_counts,
    stimulus_of,
)

# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

ANCHORED_EXERCISES: Tuple[str, ...] = ("weighted_pullup", "weighted_chinup", "max_hang_5s", "max_hang_7s")
PULL_EXERCISES: Tuple[str, ...] = ("weighted_pullup", "weighted_chinup")
HANG_SECONDS: Dict[str, int] = {"max_hang_7s": 7, "max_hang_5s": 5}
# R3: max hang sets during the re-entry ramp. ENGINEERING CONSTANT.
REENTRY_MAX_HANG_SETS = 5
#: Catalog rep scheme each pull is calibrated on (prescription_defaults.reps).
CATALOG_REPS: Dict[str, int] = {"weighted_pullup": 3, "weighted_chinup": 5}
#: Catalog intensity of the cold-start hang target (attributes.intensity_pct).
CATALOG_HANG_INTENSITY: Dict[str, float] = {"max_hang_7s": 0.90, "max_hang_5s": 0.92}
CATALOG_SETS: Dict[str, int] = {"weighted_pullup": 4, "weighted_chinup": 4, "max_hang_7s": 5, "max_hang_5s": 5}

EXERCISE_PROTOCOL: Dict[str, str] = {
    "weighted_pullup": rp.PROTOCOL_PULLUP_2RM,
    "weighted_chinup": rp.PROTOCOL_PULLUP_2RM,
    "max_hang_7s": rp.PROTOCOL_HANG_7S,
    "max_hang_5s": rp.PROTOCOL_HANG_5S,
}
_PROTOCOL_SECONDS: Dict[str, int] = {rp.PROTOCOL_HANG_7S: 7, rp.PROTOCOL_HANG_5S: 5}

AXIS_PULLING = "pulling"
AXIS_FINGER = "finger"


def axis_of(exercise_id: str) -> str:
    return AXIS_PULLING if exercise_id in PULL_EXERCISES else AXIS_FINGER


def family_of(exercise_id: str) -> str:
    return FAMILY_PULLING_MAX if exercise_id in PULL_EXERCISES else FAMILY_FINGER_MAX


# ---------------------------------------------------------------------------
# Constants. Values without a published source are ENGINEERING CONSTANTS
# (decisions 2026-10-04) and are labelled as such.
# ---------------------------------------------------------------------------

#: ENGINEERING CONSTANT (conservative): a chin-up is prescribed off the
#: pull-up 2RM at ratio 1.0 — no transfer bonus is assumed.
CHINUP_TO_PULLUP_RATIO = 1.0

#: ENGINEERING CONSTANT: a mapping of Prilepin's chart bands to a cap on the
#: share of 1RM, by total reps of the session and reps per set. To train at
#: 90 % the SCHEME changes (3-4x2); the cap of a 4x3 never rises.
PRILEPIN_BANDS: Tuple[Tuple[int, int, float], ...] = (
    (10, 2, 0.90),   # ≤ 10 total reps, ≤ 2 per set
    (20, 4, 0.85),   # ≤ 20 total reps, ≤ 4 per set
    (24, 6, 0.80),   # ≤ 24 total reps, ≤ 6 per set
)
PRILEPIN_DEFAULT = 0.75

#: ENGINEERING CONSTANT: a hang is capped at the load holdable for
#: (prescribed seconds + RESERVE_S) — three seconds left in the tank.
RESERVE_S = 3

#: ENGINEERING CONSTANTS: hang cap / floor / reference intensity by phase, as a
#: share of the official max at the prescribed duration. 100 % appears only in
#: test sessions.
HANG_PHASE_CAP: Dict[str, float] = {
    "strength_power": 0.95, "performance": 0.95, "power_endurance": 0.90,
    "base": 0.85, "deload": 0.70,
}
HANG_PHASE_FLOOR: Dict[str, float] = {
    "base": 0.75, "strength_power": 0.80, "power_endurance": 0.75,
    "performance": 0.80, "deload": 0.60,
}
HANG_PHASE_PCT: Dict[Tuple[str, str], float] = {
    ("strength_power", "hard"): 0.90, ("strength_power", "medium"): 0.85, ("strength_power", "easy"): 0.80,
    ("power_endurance", "hard"): 0.85, ("power_endurance", "medium"): 0.80, ("power_endurance", "easy"): 0.75,
    ("base", "hard"): 0.80, ("base", "medium"): 0.75, ("base", "easy"): 0.70,
    ("performance", "hard"): 0.90, ("performance", "medium"): 0.85, ("performance", "easy"): 0.80,
    ("deload", "hard"): 0.65, ("deload", "medium"): 0.65, ("deload", "easy"): 0.65,
}
HANG_PHASE_DEFAULT_CAP = 0.85
HANG_PHASE_DEFAULT_FLOOR = 0.75
HANG_PHASE_DEFAULT_PCT = 0.80

#: A working entry is trusted for this many days (same gate the planned path
#: has always used for maxes and hangs). Older → phase target.
WORKING_ENTRY_MAX_AGE_D = 60

#: Custom / ad-hoc / picker sessions have no session intent: they are read as
#: hard sessions (the athlete chose the exercise to train it).
CUSTOM_INTENSITY = "hard"

#: Heavy pulling (decision 2026-10-04): at most HEAVY_PULL_WEEKLY_MAX sessions at
#: ≥ HEAVY_PULL_PCT_1RM in 7 days (chin-up included). The next one is capped at
#: HEAVY_PULL_GUARD_CAP_PCT (ENGINEERING CONSTANT, R3 "guardia gomito").
HEAVY_PULL_WEEKLY_MAX = 2
HEAVY_PULL_GUARD_CAP_PCT = 0.80
#: ENGINEERING CONSTANT (R3): with a max-finger exercise in the same session the
#: pull stays at or below this share of 1RM.
SAME_SESSION_PULL_CAP_PCT = 0.875
#: ENGINEERING CONSTANT (R3): a finger-hard day in the previous N calendar days
#: freezes the hang at the last load used (no rise; never a cut).
FINGER_FREEZE_WINDOW_D = 2

#: Fatigue (decision 2026-10-04): FATIGUE_HARD_COUNT hard/very_hard days on an
#: axis within FATIGUE_WINDOW_D days → the load goes to the phase floor + flag.
FATIGUE_HARD_COUNT = 3
FATIGUE_WINDOW_D = 14
#: hard_labels dates are kept this long (2 windows).
HARD_LABELS_KEEP_D = 28

#: Label steps on the working load (decision 2026-10-04, revised by Daniele:
#: he does exactly the prescribed reps, so an easy label IS the signal).
PULL_LABEL_STEP_KG: Dict[str, float] = {"very_easy": 5.0, "easy": 2.5, "ok": 0.0}
PULL_LABEL_STEP_PCT: Dict[str, float] = {"hard": -0.025, "very_hard": -0.075}
HANG_LABEL_STEP_KG: Dict[str, float] = {
    "very_easy": 4.0, "easy": 2.0, "ok": 0.0, "hard": -2.0, "very_hard": -4.0,
}
#: Escalation limits: pulls ≤ +5 kg per session; fingers ≤ +5 % of the official
#: max per 7 days (ENGINEERING CONSTANTS, decision 2026-10-04).
PULL_MAX_STEP_KG = 5.0
FINGER_MAX_RISE_PCT = 0.05
FINGER_RISE_WINDOW_D = 7

#: Early retest evidence (decision 2026-10-04), measured only:
#: pull-up last set (AMRAP, stop one before failure) e1RM > official 1RM;
#: hang held > target + RETEST_HANG_OVERHOLD_S (timed overhold, capped at
#: target + RETEST_HANG_OVERHOLD_CAP_S) at ≥ RETEST_HANG_MIN_PCT of the max.
RETEST_HANG_OVERHOLD_S = 5.0
RETEST_HANG_OVERHOLD_CAP_S = 6.0
RETEST_HANG_MIN_PCT = 0.90

#: R3 §8: a hang tested less than this many days ago is not "stale": an
#: assisted (negative external) hang shows the assistance, not "re-test".
TESTED_NO_WARNING_D = 30

#: Pain (decision 2026-10-04; written by R4 into progression_counters.pain_blocks,
#: read here): score 2 → −10 % (+ hang ≤ 85 %); score 3 → −10 % and cap 80 %.
#: A295: a pain reported on "other" (site not given) covers every loaded
#: exercise, the anchored four included.
PAIN_SITES: Dict[str, Tuple[str, ...]] = {
    AXIS_FINGER: ("fingers", "other"), AXIS_PULLING: ("elbow", "shoulder", "other"),
}
PAIN_MULT = 0.90
PAIN_CAP_SCORE2_HANG = 0.85
PAIN_CAP_SCORE3 = 0.80

#: Registry of exposures: entries older than this are pruned.
REGISTRY_KEEP_D = 120

_NO_DATE_AS_OF = "9999-12-31"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def round_half(value: float) -> float:
    return round(float(value) / 0.5) * 0.5


def floor_half(value: float) -> float:
    return math.floor(float(value) * 2 + 1e-9) / 2


def ceil_half(value: float) -> float:
    return math.ceil(float(value) * 2 - 1e-9) / 2


def rep_factor(reps: float) -> float:
    """NON-rounded Epley/Brzycki mean: 1RM = load × rep_factor(reps).

    Not ``estimate_1rm_from_reps``: that one rounds to 0.1 kg, which makes
    f(3) = f(4) = f(5) on small numbers and the rep conversion vanish (R4).
    Reps clamped to [1, 12].
    """
    r = max(1.0, min(12.0, float(reps)))
    if r <= 1.0:
        return 1.0
    return ((1 + r / 30.0) + 36.0 / (37.0 - r)) / 2.0


def prilepin_cap(sets: int, reps: int) -> float:
    total = int(sets) * int(reps)
    for max_total, max_reps, pct in PRILEPIN_BANDS:
        if total <= max_total and int(reps) <= max_reps:
            return pct
    return PRILEPIN_DEFAULT


def _bodyweight(state: Mapping[str, Any]) -> float:
    return float(state.get("bodyweight_kg") or ((state.get("body") or {}).get("weight_kg") or 0.0))


def phase_on(state: Mapping[str, Any], on: Optional[date]) -> str:
    """Phase id on ``on``, pause-aware (A223) via macro_position."""
    if on is None:
        return "base"
    from backend.engine.macro_position import position_on

    pos = position_on(state.get("macrocycle"), on)
    if pos and pos.get("phase_id"):
        return str(pos["phase_id"])
    phases = (state.get("macrocycle") or {}).get("phases") or []
    return str(phases[0].get("phase_id", "base")) if phases else "base"


def _pulling_pct(phase: str, intensity: str) -> float:
    from backend.engine.progression_v1 import PULLING_1RM_PCT, PULLING_1RM_PCT_DEFAULT

    return PULLING_1RM_PCT.get((phase, intensity), PULLING_1RM_PCT_DEFAULT)


def _hang_pct(phase: str, intensity: str) -> float:
    return HANG_PHASE_PCT.get((phase, intensity), HANG_PHASE_DEFAULT_PCT)


# ---------------------------------------------------------------------------
# Official max, tested gate, ramp
# ---------------------------------------------------------------------------

def official_for(state: Mapping[str, Any], exercise_id: str, on: Optional[date]) -> Optional[Dict[str, Any]]:
    """``retest_policy.official_max`` for the exercise's protocol.

    Without a date (B364 §2e) the freshest test is used with no freshness
    check: ``tested`` then only means "comes from a test".
    """
    protocol = EXERCISE_PROTOCOL.get(exercise_id)
    if protocol is None:
        return None
    if on is None:
        om = rp.official_max(state, protocol, _NO_DATE_AS_OF)
        if om is None:
            return None
        om = dict(om)
        om["tested"] = rp._cand_tested(om)
        om["age_days"] = None
        om["fresh"] = None
        return om
    return rp.official_max(state, protocol, on)


def is_anchored_and_tested(state: Mapping[str, Any], exercise_id: str, as_of: Any) -> bool:
    if exercise_id not in ANCHORED_EXERCISES:
        return False
    on = _parse(as_of)
    if on is None:
        return False
    om = official_for(state, exercise_id, on)
    return bool(om and om.get("tested"))


def _test_dates(state: Mapping[str, Any], family: str) -> List[str]:
    """Days of ``tests.*`` entries of a family (a test is an exposure)."""
    out: List[str] = []
    tests = state.get("tests") or {}
    if family == FAMILY_FINGER_MAX:
        for t in tests.get("max_strength") or []:
            if isinstance(t, Mapping) and str(t.get("test_id") or "") in _PROTOCOL_SECONDS and t.get("date"):
                out.append(str(t["date"])[:10])
        for b in ((state.get("baselines") or {}).get("loading_pin") or []):
            if isinstance(b, Mapping) and b.get("source") == "test" and b.get("updated_at"):
                out.append(str(b["updated_at"])[:10])
        hb = (state.get("baselines") or {}).get("hangboard") or []
        # Baselines only when a test log wrote them (an onboarding self-report
        # is persisted as source='test' with the onboarding day — not a test).
        if hb and isinstance(hb[0], Mapping) and hb[0].get("source") in rp._BASELINE_TESTED_SOURCES and hb[0].get("updated_at"):
            out.append(str(hb[0]["updated_at"])[:10])
    elif family == FAMILY_PULLING_MAX:
        for t in tests.get("pulling_strength") or []:
            if isinstance(t, Mapping) and t.get("test_id") == rp.PROTOCOL_PULLUP_2RM and t.get("date"):
                out.append(str(t["date"])[:10])
        pb = (state.get("baselines") or {}).get("pulling") or {}
        if isinstance(pb, Mapping) and pb.get("source") in rp._BASELINE_TESTED_SOURCES and pb.get("updated_at"):
            out.append(str(pb["updated_at"])[:10])
    return sorted(set(out))


def _family_exercises(family: str) -> Tuple[str, ...]:
    return PULL_EXERCISES if family == FAMILY_PULLING_MAX else tuple(HANG_SECONDS)


def ramp_for(
    state: Mapping[str, Any], family: str, on: Optional[date], official_date: Optional[str] = None,
) -> Dict[str, Any]:
    """The re-entry ramp (``retest_policy.reentry_step``) + B364's deploy rule.

    Deploy rule (B364 §2c): with an EMPTY registry for the family (existing
    users before the migration seeds it), a working entry of the family updated
    less than ``REENTRY_GAP_D`` days ago means the athlete is training it: n = 3.
    Only an entry FRESHER than the official test counts (an entry dated on the
    test day is the pre-B363 copy of the test itself, not training).
    """
    if on is None:
        return {"family": family, "n": 1, "factor": rp.reentry_factor(1), "gap_days": None,
                "in_reentry": True, "source": "no_date"}
    info = dict(rp.reentry_step(state, family, on, extra_dates=_test_dates(state, family)))
    info["source"] = "exposures"
    registry = ((state.get("progression_counters") or {}).get("stimulus_exposures") or {})
    if info["n"] < 3 and not (isinstance(registry, Mapping) and registry.get(family)):
        for e in ((state.get("working_loads") or {}).get("entries") or []):
            if not isinstance(e, Mapping) or e.get("exercise_id") not in _family_exercises(family):
                continue
            upd = _parse(e.get("updated_at"))
            if official_date and str(e.get("updated_at") or "")[:10] <= str(official_date)[:10]:
                continue
            if upd is not None and 0 <= (on - upd).days < rp.REENTRY_GAP_D:
                info.update({"n": 3, "factor": rp.REENTRY_FULL_FACTOR, "in_reentry": False,
                             "source": "fresh_working_entry"})
                break
    return info


# ---------------------------------------------------------------------------
# Working entry, pain, fatigue, guards
# ---------------------------------------------------------------------------

def working_entry(
    state: Mapping[str, Any], exercise_id: str, on: Optional[date],
    official_date: Optional[str], setup: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """The valid working entry: fresher than the official test (strictly),
    ≤ WORKING_ENTRY_MAX_AGE_D days old, with a ``next_total_load_kg``."""
    if on is None:
        return None
    from backend.engine.progression_v1 import _best_entry

    entry = _best_entry(dict(state), exercise_id, dict(setup or {}), on.isoformat(),
                        freshness_days=WORKING_ENTRY_MAX_AGE_D)
    if not entry or _num(entry.get("next_total_load_kg")) is None:
        return None
    upd = str(entry.get("updated_at") or "")[:10]
    if official_date and upd <= str(official_date)[:10]:
        return None
    return entry


def pain_for(state: Mapping[str, Any], axis: str, on: Optional[date]) -> Optional[Dict[str, Any]]:
    """Active pain block for the axis on ``on`` (R4 writes them; read-only here)."""
    if on is None:
        return None
    blocks = ((state.get("progression_counters") or {}).get("pain_blocks") or {})
    if not isinstance(blocks, Mapping):
        return None
    worst: Optional[Dict[str, Any]] = None
    for site in PAIN_SITES[axis]:
        b = blocks.get(site)
        if not isinstance(b, Mapping):
            continue
        start, until = _parse(b.get("from")), _parse(b.get("until"))
        score = int(_num(b.get("score")) or 0)
        if start is None or until is None or not (start <= on <= until) or score < 2:
            continue
        if worst is None or score > worst["score"]:
            worst = {"site": site, "score": score, "from": start.isoformat(), "until": until.isoformat()}
    return worst


def fatigue_for(state: Mapping[str, Any], axis: str, on: Optional[date]) -> Optional[Dict[str, Any]]:
    """3 hard/very_hard days on the axis in the 14 days before ``on``."""
    if on is None:
        return None
    days = ((state.get("progression_counters") or {}).get("hard_labels") or {}).get(axis) or []
    start = on - timedelta(days=FATIGUE_WINDOW_D)
    hits = sorted({str(d)[:10] for d in days
                   if (_parse(d) is not None and start <= _parse(d) < on)})
    if len(hits) >= FATIGUE_HARD_COUNT:
        return {"axis": axis, "hard_days": hits, "since": hits[FATIGUE_HARD_COUNT - 1]}
    return None


def _heavy_pull_days(state: Mapping[str, Any], on: date, one_rm: float, bw: float) -> List[str]:
    """Days in the 7 before ``on`` with a weighted pull ≥ 85 % of 1RM (measured
    load only) or a 2RM test."""
    since, until = on - timedelta(days=7), on - timedelta(days=1)
    days = set()
    for r in exposures(state, since=since, until=until, families=[FAMILY_PULLING_MAX]):
        total = r.get("used_total_load_kg")
        if total is None and r.get("used_external_load_kg") is not None:
            total = bw + float(r["used_external_load_kg"])
        if r.get("is_test") or (total is not None and total >= rp.HEAVY_PULL_PCT_1RM * one_rm):
            days.add(r["date"])
    for d in _test_dates(state, FAMILY_PULLING_MAX):
        pd = _parse(d)
        if pd is not None and since <= pd <= until:
            days.add(d)
    return sorted(days)


# ---------------------------------------------------------------------------
# anchored_load
# ---------------------------------------------------------------------------

def anchored_load(
    state: Mapping[str, Any],
    exercise_id: str,
    *,
    date: Any,
    phase_id: Optional[str] = None,
    intensity: str = CUSTOM_INTENSITY,
    sets: Optional[int] = None,
    reps: Optional[int] = None,
    work_seconds: Optional[float] = None,
    session_exercise_ids: Optional[Iterable[str]] = None,
    setup: Optional[Mapping[str, Any]] = None,
    catalog_intensity: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """The prescription of an anchored exercise on ``date``, or ``None``.

    ``None`` = not an anchored exercise, no official max, or not tested: the
    caller keeps its pre-B364 path. ``state`` must be the PERSISTED state
    (never the output of ``estimate_missing_baselines``).

    Returns::

        {exercise_id, axis, total, external, source: working_load|phase_target,
         phase_id, intensity, sets, reps | work_seconds, rep_scheme,
         official: {protocol, total, one_rm?, date, source, age_days,
                    confidence, converted},
         floor, cap, ramp: {n, factor, gap_days, source}, clamped,
         pct_of_official, guards: [...], pain?, fatigue?, ceiling_note?,
         no_date: bool}
    """
    if exercise_id not in ANCHORED_EXERCISES:
        return None
    on = _parse(date)
    om = official_for(state, exercise_id, on)
    if not om or not om.get("tested"):
        return None

    bw = _bodyweight(state)
    phase = (phase_id or phase_on(state, on)) if on is not None else "base"
    if intensity not in ("easy", "medium", "hard"):
        intensity = CUSTOM_INTENSITY
    axis = axis_of(exercise_id)
    family = family_of(exercise_id)
    ramp = ramp_for(state, family, on, om.get("date"))
    entry = working_entry(state, exercise_id, on, om.get("date"), setup)
    guards: List[Dict[str, Any]] = []
    n_sets = int(sets or CATALOG_SETS[exercise_id])

    official_out: Dict[str, Any] = {
        "protocol": om.get("protocol"),
        "total": om.get("total_kg"),
        "date": om.get("date"),
        "source": om.get("source"),
        "age_days": om.get("age_days"),
        "confidence": om.get("stored_confidence"),
        "converted": bool(om.get("converted")),
    }

    if axis == AXIS_PULLING:
        r = int(reps or CATALOG_REPS[exercise_id])
        ratio = CHINUP_TO_PULLUP_RATIO if exercise_id == "weighted_chinup" else 1.0
        one_rm = float(om["one_rm_kg"]) * ratio
        official_out["one_rm"] = round(one_rm, 1)
        ref = one_rm
        cap = min(prilepin_cap(n_sets, r) * one_rm, one_rm / rep_factor(r + 2))
        floor = _pulling_pct(phase, "easy") * one_rm
        if entry is not None:
            last_r = _num(entry.get("last_reps")) or CATALOG_REPS[exercise_id]
            total0 = float(entry["next_total_load_kg"]) * rep_factor(last_r) / rep_factor(r)
            lp, li = entry.get("phase_id_at_log"), entry.get("intensity_at_log")
            if lp and li:
                total0 *= _pulling_pct(phase, intensity) / _pulling_pct(str(lp), str(li))
            source = "working_load"
        else:
            total0 = (_pulling_pct(phase, intensity) * one_rm
                      * rep_factor(CATALOG_REPS[exercise_id]) / rep_factor(r))
            source = "phase_target"
        rep_scheme = f"{n_sets}x{r}"
        dose: Dict[str, Any] = {"reps": r}
    else:
        t = float(work_seconds or HANG_SECONDS[exercise_id])
        proto_s = _PROTOCOL_SECONDS[om["protocol"]]
        official_t = float(om["total_kg"])
        if t != proto_s:
            official_t = rp.convert_hang_seconds(official_t, proto_s, t)
        official_out["total_at_duration"] = round(official_t, 1)
        ref = official_t
        hold_cap = official_t / (1 + rp.HANG_PCT_PER_S * RESERVE_S)
        cap = min(hold_cap, HANG_PHASE_CAP.get(phase, HANG_PHASE_DEFAULT_CAP) * official_t)
        floor = HANG_PHASE_FLOOR.get(phase, HANG_PHASE_DEFAULT_FLOOR) * official_t
        if entry is not None:
            last_t = _num(entry.get("last_work_seconds")) or float(HANG_SECONDS[exercise_id])
            total0 = float(entry["next_total_load_kg"]) * (1 + rp.HANG_PCT_PER_S * (last_t - t))
            lp, li = entry.get("phase_id_at_log"), entry.get("intensity_at_log")
            if lp and li:
                total0 *= _hang_pct(phase, intensity) / _hang_pct(str(lp), str(li))
            source = "working_load"
        else:
            # Cold target unchanged (B364 §2): catalog intensity × the 7 s max,
            # exactly what _max_hang_suggested has always done — the 5 s does
            # not count the seconds twice.
            om7 = rp.official_max(state, rp.PROTOCOL_HANG_7S, on or _NO_DATE_AS_OF) or om
            intensity_pct = catalog_intensity or CATALOG_HANG_INTENSITY[exercise_id]
            total0 = float(intensity_pct) * float(om7["total_kg"])
            source = "phase_target"
        # R3: 5 sets in re-entry, never more.
        if ramp["factor"] < 1.0 and n_sets > REENTRY_MAX_HANG_SETS:
            n_sets = REENTRY_MAX_HANG_SETS
            guards.append({"guard": "reentry_sets", "sets": REENTRY_MAX_HANG_SETS})
        rep_scheme = f"{n_sets}x{int(t) if float(t).is_integer() else t}s"
        dose = {"work_seconds": t}

    cap_eff = cap * float(ramp["factor"])

    pain = pain_for(state, axis, on)
    if pain is not None:
        cap_eff *= PAIN_MULT
        total0 *= PAIN_MULT
        # B364 review: the phase floor moves down with the pain cut. Otherwise
        # floor_eff = min(floor, cap after pain) stays at the phase floor
        # whenever the cap is above it, and a working load near the floor is
        # lifted straight back up: score 2 → −2 % instead of −10 %.
        floor *= PAIN_MULT
        pain_cap = PAIN_CAP_SCORE3 if pain["score"] >= 3 else (PAIN_CAP_SCORE2_HANG if axis == AXIS_FINGER else None)
        if pain_cap is not None:
            cap_eff = min(cap_eff, pain_cap * ref)

    if axis == AXIS_PULLING and on is not None:
        heavy = _heavy_pull_days(state, on, ref, bw)
        if len(heavy) >= HEAVY_PULL_WEEKLY_MAX:
            guard_cap = HEAVY_PULL_GUARD_CAP_PCT * ref
            if guard_cap < cap_eff:
                cap_eff = guard_cap
                guards.append({"guard": "heavy_pull_week", "heavy_days": heavy})
        ids = [str(i) for i in (session_exercise_ids or [])]
        if any(stimulus_of(i) == FAMILY_FINGER_MAX for i in ids):
            same_cap = SAME_SESSION_PULL_CAP_PCT * ref
            if same_cap < cap_eff:
                cap_eff = same_cap
                guards.append({"guard": "same_session_finger"})
    if axis == AXIS_FINGER and on is not None and entry is not None:
        last_total = _num(entry.get("last_total_load_kg"))
        hard_days = finger_hard_days(state, since=on - timedelta(days=FINGER_FREEZE_WINDOW_D),
                                     until=on - timedelta(days=1))
        if last_total is not None and hard_days:
            last_t = _num(entry.get("last_work_seconds")) or float(HANG_SECONDS[exercise_id])
            frozen = last_total * (1 + rp.HANG_PCT_PER_S * (last_t - float(dose["work_seconds"])))
            if frozen < cap_eff:
                cap_eff = frozen
                guards.append({"guard": "finger_hard_recent", "days": sorted({d["date"] for d in hard_days})})

    cap_r = floor_half(cap_eff)
    floor_eff = min(floor, cap_eff)
    floor_r = min(ceil_half(floor_eff), cap_r)
    total = round_half(total0)
    clamped: Optional[str] = None
    if total > cap_r:
        total, clamped = cap_r, "cap"
    elif total < floor_r:
        total, clamped = floor_r, "floor"

    fatigue = fatigue_for(state, axis, on)
    if fatigue is not None and total > floor_r:
        total, clamped = floor_r, "fatigue_floor"

    external = round_half(total - bw)
    out: Dict[str, Any] = {
        "exercise_id": exercise_id,
        "axis": axis,
        "total": total,
        "external": external,
        "source": source,
        "phase_id": phase,
        "intensity": intensity,
        "sets": n_sets,
        **dose,
        "rep_scheme": rep_scheme,
        "official": official_out,
        "floor": floor_r,
        "cap": cap_r,
        "ramp": {"n": int(ramp["n"]), "factor": float(ramp["factor"]),
                 "gap_days": ramp.get("gap_days"), "source": ramp.get("source")},
        "clamped": clamped,
        "pct_of_official": round(total / ref, 3) if ref else None,
        "guards": guards,
        "no_date": on is None,
    }
    if pain is not None:
        out["pain"] = pain
    if fatigue is not None:
        out["fatigue"] = fatigue
    if clamped == "cap" and entry is not None and str(entry.get("last_feedback_label") or "") in ("easy", "very_easy"):
        out["ceiling_note"] = (
            "You are at the ceiling of your tested max — the next scheduled retest will raise it."
        )
    return out


def anchored_suggested_fields(anch: Mapping[str, Any]) -> Dict[str, Any]:
    """Fields to merge into an instance's ``suggested`` (resolver shape included:
    ``target_total_load_kg`` / ``added_weight_kg`` / ``assistance_kg`` are
    overwritten so no field of the instance disagrees with the prescription)."""
    total, external = float(anch["total"]), float(anch["external"])
    fields: Dict[str, Any] = {
        "schema_version": "progression_targets.v1",
        "suggested_total_load_kg": total,
        "suggested_external_load_kg": external,
        "suggested_rep_scheme": anch["rep_scheme"],
        "load_source": "anchored",
        "anchored": anchor_summary(anch),
        "target_total_load_kg": total,
        "added_weight_kg": external if external >= 0 else 0.0,
        "assistance_kg": -external if external < 0 else 0.0,
    }
    if anch["exercise_id"] == "weighted_pullup" or anch["exercise_id"] == "weighted_chinup":
        fields["reference_2rm_total_kg"] = anch["official"]["total"]
    if anch.get("ceiling_note"):
        fields["ceiling_note"] = anch["ceiling_note"]
    return fields


def anchor_summary(anch: Mapping[str, Any]) -> Dict[str, Any]:
    """Compact, UI/coach-safe description of an anchored prescription."""
    keys = ("source", "phase_id", "intensity", "floor", "cap", "clamped", "pct_of_official",
            "ramp", "official", "guards", "pain", "fatigue", "no_date")
    return {k: anch[k] for k in keys if k in anch}


# ---------------------------------------------------------------------------
# Custom sessions resolved at read time
# ---------------------------------------------------------------------------

LOAD_MODES = ("anchored", "fixed")


def effective_load_mode(exercise: Mapping[str, Any]) -> Optional[str]:
    """'anchored' | 'fixed' for an anchored exercise (missing → 'anchored'), None otherwise."""
    if str(exercise.get("exercise_id") or "") not in ANCHORED_EXERCISES:
        return None
    mode = exercise.get("load_mode")
    return mode if mode in LOAD_MODES else "anchored"


def resolve_custom_exercises(
    state: Mapping[str, Any], exercises: Sequence[Mapping[str, Any]], on: Any,
) -> List[Dict[str, Any]]:
    """Copies of a custom session's exercises with the anchored loads of ``on``.

    - anchored exercise, mode 'anchored', tested athlete → ``load_kg`` is the
      external load of ``anchored_load`` on that date (≥ 0; an assisted hang
      shows 0 + ``suggested_external_load_kg`` < 0), the stored kg moves to
      ``stored_load_kg``; when the re-entry ramp caps the sets (max hangs, 5),
      ``sets`` is lowered too and the stored count moves to ``stored_sets``;
    - mode 'fixed' → the user's kg, untouched, ``load_source: 'user_fixed'``;
    - untested athlete → stored kg untouched (pre-B364 behaviour).
    Never mutates the input.
    """
    out: List[Dict[str, Any]] = []
    for ex in exercises or []:
        if not isinstance(ex, Mapping):
            continue
        copy = dict(ex)
        mode = effective_load_mode(copy)
        if mode is None:
            out.append(copy)
            continue
        copy["load_mode"] = mode
        if mode == "fixed":
            copy["load_source"] = "user_fixed"
            out.append(copy)
            continue
        anch = anchored_load(
            state, str(copy["exercise_id"]), date=on, intensity=CUSTOM_INTENSITY,
            sets=_int(copy.get("sets")), reps=_int(copy.get("reps")),
            work_seconds=_num(copy.get("work_seconds")),
        )
        if anch is not None:
            copy["stored_load_kg"] = ex.get("load_kg")
            copy["load_kg"] = max(0.0, float(anch["external"]))
            copy["suggested_external_load_kg"] = anch["external"]
            copy["suggested_total_load_kg"] = anch["total"]
            copy["load_source"] = "anchored"
            copy["anchored"] = anchor_summary(anch)
            if anch.get("ceiling_note"):
                copy["ceiling_note"] = anch["ceiling_note"]
            # Re-entry: anchored_load caps max hangs at 5 sets (guard
            # reentry_sets) — the set count is part of the prescription, not
            # only the load (B364 review: a 6-set ad-hoc hang kept 6 sets).
            stored_sets = _int(copy.get("sets"))
            if stored_sets is not None and int(anch["sets"]) < stored_sets:
                copy["stored_sets"] = stored_sets
                copy["sets"] = int(anch["sets"])
        out.append(copy)
    return out


def _int(value: Any) -> Optional[int]:
    n = _num(value)
    return int(n) if n is not None and n > 0 else None


# ---------------------------------------------------------------------------
# Feedback: working-load progression, fatigue labels, retest signals, registry
# ---------------------------------------------------------------------------

def _used_total(item: Mapping[str, Any], bw: float) -> Optional[float]:
    total = _num(item.get("used_total_load_kg"))
    if total is not None:
        return total
    ext = _num(item.get("used_external_load_kg"))
    if ext is not None:
        return ext + bw
    return None


def _hang_measured_step(item: Mapping[str, Any], target_s: float) -> Optional[float]:
    held = _num(item.get("hang_held_s"))
    if held is not None:
        over = held - target_s
        if over >= 5:
            return 4.0
        if over >= 3:
            return 2.0
        if over >= 0:
            return 0.0
        return -4.0 if over < -2 else -2.0
    margin = str(item.get("hang_margin") or "")
    return {">5": 4.0, "3-5": 2.0, "0-2": 0.0, "failed": -2.0}.get(margin)


def _pull_measured_step(item: Mapping[str, Any], reps: int, used_total: float) -> Optional[float]:
    last = _num(item.get("last_set_reps"))
    if last is None:
        return None
    if last >= reps + 3:
        return 5.0
    if last >= reps + 1:
        return 2.5
    if last >= reps:
        return 0.0
    return round_half(used_total * -0.025) or -0.5


def _record_hard_label(counters: Dict[str, Any], axis: str, date_value: str) -> None:
    hl = counters.setdefault("hard_labels", {})
    if not isinstance(hl, dict):
        hl = {}
        counters["hard_labels"] = hl
    days = sorted({str(d)[:10] for d in (hl.get(axis) or [])} | {date_value})
    newest = _parse(days[-1])
    if newest is not None:
        floor_d = (newest - timedelta(days=HARD_LABELS_KEEP_D)).isoformat()
        days = [d for d in days if d >= floor_d]
    hl[axis] = days


def _record_retest_signal(counters: Dict[str, Any], exercise_id: str, date_value: str, official_date: str) -> None:
    sig = counters.setdefault("retest_signals", {})
    if not isinstance(sig, dict):
        sig = {}
        counters["retest_signals"] = sig
    cur = sig.get(exercise_id) if isinstance(sig.get(exercise_id), dict) else {}
    if str(cur.get("official_date") or "") != str(official_date):
        cur = {"official_date": str(official_date), "dates": []}
    dates = sorted({str(d)[:10] for d in (cur.get("dates") or [])} | {date_value})
    sig[exercise_id] = {
        "count": len(dates),
        "last_date": dates[-1],
        "dates": dates,
        "official_date": str(official_date),
    }


def apply_anchored_feedback(
    updated: Dict[str, Any],
    item: Mapping[str, Any],
    *,
    feedback_label: Optional[str],
    date_value: str,
    planned_session: Optional[Mapping[str, Any]],
    planned_prescription: Mapping[str, Any],
    setup_source: Mapping[str, Any],
) -> bool:
    """Working-load progression of an anchored exercise for a TESTED athlete.

    Returns False when it does not apply (not anchored, no date, not tested on
    that date) so the caller keeps the pre-B364 branch. Returns True when it
    handled the item — even if nothing was written (no load, a log older than
    the official test or than the stored entry).

    Never touches tests/baselines. Idempotent: next = used + step, so the same
    log applied twice writes the same entry.
    """
    from backend.engine.progression_v1 import (
        _find_working_load_entry,
        _intensity_label,
        _progression_setup_and_key,
    )

    exercise_id = str(item.get("exercise_id") or "")
    if exercise_id not in ANCHORED_EXERCISES:
        return False
    on = _parse(date_value)
    if on is None:
        return False
    om = rp.official_max(updated, EXERCISE_PROTOCOL[exercise_id], on)
    if not om or not om.get("tested"):
        return False

    bw = _bodyweight(updated)
    used_total = _used_total(item, bw)
    if used_total is None:
        return True
    if date_value < str(om["date"]):
        return True  # older than the test: the test supersedes it

    setup, key = _progression_setup_and_key(exercise_id, dict(setup_source))
    existing = next(
        (e for e in ((updated.get("working_loads") or {}).get("entries") or [])
         if isinstance(e, dict) and str(e.get("key") or "") == key),
        None,
    )
    if existing is not None and str(existing.get("updated_at") or "") > date_value:
        return True  # a newer log already moved the working load

    axis = axis_of(exercise_id)
    # A295: ``feedback_label`` None = not rated → hold (same as 'ok').
    label = feedback_label if feedback_label in HANG_LABEL_STEP_KG else "ok"
    completed = item.get("completed") is not False and str(item.get("feedback_label") or "") != "skipped"
    # A295 (R4 §3a): fewer sets than prescribed may be a skipped set — never a
    # reason to go up (a hard label can still bring the load down).
    sets_done, sets_presc = _num(item.get("completed_sets")), (
        _num(item.get("prescribed_sets")) or _num(planned_prescription.get("sets")))
    all_sets = not (sets_done is not None and sets_presc is not None and sets_done < sets_presc)
    # A295: a pain block on this axis freezes upward steps and retest signals.
    pain_now = pain_for(updated, axis, on)
    phase = phase_on(updated, on)
    intensity = _intensity_label(dict(planned_session)) if planned_session else CUSTOM_INTENSITY
    counters = updated.setdefault("progression_counters", {})
    fields: Dict[str, Any] = {}

    if axis == AXIS_PULLING:
        reps_raw = (item.get("reps") if item.get("reps") is not None else
                    item.get("prescribed_reps") if item.get("prescribed_reps") is not None else
                    planned_prescription.get("reps"))
        reps = int(_num(reps_raw) or CATALOG_REPS[exercise_id]) or CATALOG_REPS[exercise_id]
        if label in PULL_LABEL_STEP_KG:
            step = PULL_LABEL_STEP_KG[label]
        else:
            step = round_half(used_total * PULL_LABEL_STEP_PCT[label])
        measured = _pull_measured_step(item, reps, used_total)
        if measured is not None:
            step = measured
        step = min(step, PULL_MAX_STEP_KG)
        if not completed or not all_sets or pain_now is not None:
            step = min(step, 0.0)
        next_total = round_half(used_total + step)
        ratio = CHINUP_TO_PULLUP_RATIO if exercise_id == "weighted_chinup" else 1.0
        one_rm = float(om["one_rm_kg"]) * ratio
        # Structural clamp at write: never above the (r+2)RM of the 1RM.
        next_total = min(next_total, floor_half(one_rm / rep_factor(reps + 2)))
        fields["last_reps"] = reps
        last_set = _num(item.get("last_set_reps"))
        if last_set is not None:
            fields["last_set_reps"] = int(last_set)
            if used_total * rep_factor(last_set + 1) > one_rm and pain_now is None and all_sets:
                _record_retest_signal(counters, exercise_id, date_value, str(om["date"]))
    else:
        t = float(_num(planned_prescription.get("work_seconds")) or _num(item.get("work_seconds"))
                  or _num(item.get("prescribed_work_seconds")) or HANG_SECONDS[exercise_id])
        official_t = float(om["total_kg"])
        proto_s = _PROTOCOL_SECONDS[om["protocol"]]
        if t != proto_s:
            official_t = rp.convert_hang_seconds(official_t, proto_s, t)
        step = HANG_LABEL_STEP_KG[label]
        measured = _hang_measured_step(item, t)
        if measured is not None:
            step = measured
        if not completed or not all_sets or pain_now is not None:
            step = min(step, 0.0)
        next_total = round_half(used_total + step)
        # Escalation: ≤ +5 % of the official max per rolling 7-day window.
        anchor = (existing or {}).get("escalation_anchor") if existing else None
        anchor_d = _parse((anchor or {}).get("date"))
        if anchor is None or anchor_d is None or (on - anchor_d).days >= FINGER_RISE_WINDOW_D:
            anchor = {"date": date_value, "total_kg": round_half(used_total)}
        rise_cap = floor_half(float(anchor["total_kg"]) + FINGER_MAX_RISE_PCT * official_t)
        next_total = min(next_total, rise_cap)
        # Structural clamp at write: never above the 3-s-reserve load.
        next_total = min(next_total, floor_half(official_t / (1 + rp.HANG_PCT_PER_S * RESERVE_S)))
        fields["last_work_seconds"] = t
        fields["escalation_anchor"] = anchor
        held = _num(item.get("hang_held_s"))
        if held is not None:
            fields["last_hang_held_s"] = held
            held_c = min(held, t + RETEST_HANG_OVERHOLD_CAP_S)
            if (held_c > t + RETEST_HANG_OVERHOLD_S and used_total >= RETEST_HANG_MIN_PCT * official_t
                    and pain_now is None):
                _record_retest_signal(counters, exercise_id, date_value, str(om["date"]))

    if feedback_label in ("hard", "very_hard"):
        _record_hard_label(counters, axis, date_value)

    entry = _find_working_load_entry(updated, exercise_id, setup)
    for stale in ("e2rm_total_kg", "next_external_load_kg_legacy"):
        entry.pop(stale, None)
    entry.update({
        "exercise_id": exercise_id,
        "key": key,
        "setup": setup,
        "last_completed": bool(completed),
        "last_feedback_label": feedback_label,
        "last_rated": feedback_label is not None or any(
            item.get(k) is not None for k in ("last_set_reps", "hang_margin", "hang_held_s")),
        "last_total_load_kg": round_half(used_total),
        "last_external_load_kg": round_half(used_total - bw),
        "next_total_load_kg": next_total,
        "next_external_load_kg": round_half(next_total - bw),
        "phase_id_at_log": phase,
        "intensity_at_log": intensity,
        "anchored": True,
        "updated_at": date_value,
        **fields,
    })
    return True


def record_exposures(updated: Dict[str, Any], log_entry: Mapping[str, Any]) -> None:
    """Append the log's stimulus exposures to the persisted registry
    ``progression_counters.stimulus_exposures`` (the ONE registry, A288 view
    reads it). One row per (date, exercise_id); the "was it done" rule is
    ``stimulus.logged_entry_counts``. Pruned to REGISTRY_KEEP_D days."""
    from backend.engine.progression_v1 import _is_test_log

    date_value = str(log_entry.get("date") or "")[:10]
    if _parse(date_value) is None:
        return
    sid = str(log_entry.get("session_id") or "")
    player = sid.startswith("custom_") or sid.startswith("generated_")
    session_is_test = _is_test_log(dict(log_entry))
    bw = _bodyweight(updated)
    planned_sets: Dict[str, Any] = {}
    for s in log_entry.get("planned") or []:
        for inst in (s or {}).get("exercise_instances") or []:
            eid = str(inst.get("exercise_id") or "")
            if eid and eid not in planned_sets:
                planned_sets[eid] = (inst.get("prescription") or {}).get("sets")
    items = ((log_entry.get("actual") or {}).get("exercise_feedback_v1") or [])
    rows: List[Tuple[str, Dict[str, Any]]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        eid = str(item.get("exercise_id") or "")
        fam = stimulus_of(eid)
        if not fam or not logged_entry_counts(item, player_session=player):
            continue
        sets_done = _num(item.get("completed_sets"))
        sets_presc = _num(item.get("prescribed_sets")) or _num(planned_sets.get(eid))
        total = _used_total(item, bw)
        rows.append((fam, {
            "date": date_value,
            "exercise_id": eid,
            "session_id": sid or None,
            "total_kg": round_half(total) if total is not None else None,
            "sets_done": int(sets_done) if sets_done is not None else None,
            "sets_prescribed": int(sets_presc) if sets_presc is not None else None,
            "is_test": bool(session_is_test or eid.startswith("test_")),
            "evidence": "measured",
        }))
    if not rows:
        return
    counters = updated.setdefault("progression_counters", {})
    reg = counters.setdefault("stimulus_exposures", {})
    if not isinstance(reg, dict):
        reg = {}
        counters["stimulus_exposures"] = reg
    for fam, row in rows:
        lst = [r for r in (reg.get(fam) or []) if isinstance(r, dict)
               and not (str(r.get("date"))[:10] == row["date"] and r.get("exercise_id") == row["exercise_id"])]
        lst.append(row)
        reg[fam] = lst
    newest = max(str(r.get("date"))[:10] for lst in reg.values() if isinstance(lst, list) for r in lst if isinstance(r, dict))
    floor_d = (_parse(newest) - timedelta(days=REGISTRY_KEEP_D)).isoformat()
    for fam in list(reg):
        if not isinstance(reg[fam], list):
            continue
        reg[fam] = sorted(
            (r for r in reg[fam] if isinstance(r, dict) and str(r.get("date"))[:10] >= floor_d),
            key=lambda r: (str(r.get("date")), str(r.get("exercise_id") or "")),
        )


__all__ = [
    "ANCHORED_EXERCISES", "PULL_EXERCISES", "CHINUP_TO_PULLUP_RATIO", "PRILEPIN_BANDS",
    "RESERVE_S", "REENTRY_MAX_HANG_SETS", "HANG_PHASE_CAP", "HANG_PHASE_FLOOR", "HANG_PHASE_PCT", "CUSTOM_INTENSITY",
    "rep_factor", "prilepin_cap", "phase_on", "official_for", "is_anchored_and_tested",
    "ramp_for", "working_entry", "anchored_load", "anchored_suggested_fields", "anchor_summary",
    "effective_load_mode", "resolve_custom_exercises", "apply_anchored_feedback",
    "record_exposures", "fatigue_for", "pain_for",
]
