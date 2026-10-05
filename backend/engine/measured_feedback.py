"""A295 (R4) — measured feedback: a feedback that measures something.

Before A295 every client path pre-selected ``ok``: closing a session without
touching anything signed "ok" on every exercise (67 of Daniele's 69 labels),
``completed_reps`` was a copy of ``completed_sets`` and the real reps never
reached the engine. This module holds the pieces of the new contract that are
not specific to the four anchored exercises (those live in ``anchored_load``,
B364, which already consumes ``last_set_reps`` / ``hang_margin`` /
``hang_held_s`` and writes ``retest_signals``).

Contract (``log_entry.feedback_contract``):

- **2** — the client omits ``feedback_label`` when the user touched nothing;
  an exercise without a label is NOT RATED. Optional measures per item:
  ``last_set_reps`` (pull-ups, double-progression accessories),
  ``hang_margin`` (max hangs: failed | 0-2 | 3-5 | >5 seconds left),
  ``hang_held_s`` (guided player only, timed overhold of the last rep),
  ``target_reps`` (the double-progression target the client showed).
  Session level: ``pain {score 0..3, site}``.
- **absent (legacy)** — ``ok`` cannot be told apart from the old default, so a
  legacy ``ok`` is NOT RATED too (DECISIONS 2026-10-04). Other labels stay.

What "not rated" means: the working load is held at the load actually used,
and the exercise is left out of the session difficulty, the feedback log, the
fatigue labels and the endurance grade streak. Nothing pretends it was "ok".

Pure: no I/O except the catalog cache, never ``date.today()``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

FEEDBACK_CONTRACT_MEASURED = 2

VALID_LABELS = ("very_easy", "easy", "ok", "hard", "very_hard")
_LEGACY_MAP = {
    "too_easy": "very_easy",
    "easy": "easy",
    "ok": "ok",
    "hard": "hard",
    "too_hard": "very_hard",
    "fail": "very_hard",
}

HANG_MARGINS: Tuple[str, ...] = ("failed", "0-2", "3-5", ">5")
PAIN_SITES: Tuple[str, ...] = ("fingers", "elbow", "shoulder", "other")

#: Sanitisation bounds (router). Out of range → dropped with a warning.
LAST_SET_REPS_MAX = 20
TARGET_REPS_MAX = 50
#: Generous bound on a timed hang (the client caps the overhold at target+6 s).
HANG_HELD_MAX_S = 120.0


def log_contract(log_entry: Mapping[str, Any]) -> int:
    try:
        return int(log_entry.get("feedback_contract") or 0)
    except (TypeError, ValueError):
        return 0


def feedback_rating(item: Mapping[str, Any], contract: int) -> Optional[str]:
    """The label the athlete actually gave, or ``None`` (not rated).

    contract ≥ 2: a valid ``feedback_label`` (or the legacy too_hard/fail
    flags) is a rating; anything else is not rated.
    contract < 2 (legacy client): an ``ok`` is indistinguishable from the old
    default at zero input, so it is NOT RATED; other labels keep their meaning.
    """
    label = str(item.get("feedback_label") or "").strip().lower()
    rating: Optional[str] = label if label in VALID_LABELS else None
    if rating is None:
        legacy = str(item.get("difficulty") or item.get("difficulty_label") or "").strip().lower()
        rating = _LEGACY_MAP.get(legacy)
    if rating is None and (bool(item.get("too_hard")) or bool(item.get("fail"))):
        rating = "very_hard"
    if rating == "ok" and contract < FEEDBACK_CONTRACT_MEASURED:
        return None
    return rating


def has_measure(item: Mapping[str, Any]) -> bool:
    return any(item.get(k) is not None for k in ("last_set_reps", "hang_margin", "hang_held_s"))


# ---------------------------------------------------------------------------
# Measure kind: explicit allowlists, never a heuristic on the catalog
# ---------------------------------------------------------------------------

MEASURE_HANG_MARGIN = "hang_margin"
MEASURE_LAST_SET_REPS = "last_set_reps"
MEASURE_DP_REPS = "dp_reps"

#: Max hangs on which "how much longer could you have held" is meaningful
#: (a hang calibrated with ~3 s in reserve, López-Rivera / Hörst). Never in a
#: test session (B363 isolation: a test is a max, not a training load).
HANG_MARGIN_EXERCISES: frozenset = frozenset({"max_hang_5s", "max_hang_7s", "max_hang_10s", "horst_7_53"})
#: Pulls: reps on the last set (AMRAP stopping one before failure).
#: weighted_chinup is included (R4 excluded it as dead data; B364 gave the
#: chin-up its own anchored working entry, so the measure now has a consumer).
LAST_SET_REPS_EXERCISES: frozenset = frozenset({"weighted_pullup", "weighted_chinup"})
#: Never measured, whatever their load model says.
MEASURE_EXCLUDED: frozenset = frozenset({
    "pinch_block_training", "one_arm_hang_assisted", "max_hang_ladder",
})
_HANG_PATTERNS = frozenset({"isometric_hang", "repeater_hang", "isometric_lift", "repeater_lift"})


def _catalog() -> Dict[str, Dict[str, Any]]:
    from backend.engine.progression_v1 import _load_catalog_cache

    return _load_catalog_cache()


def _patterns(info: Mapping[str, Any]) -> Set[str]:
    raw = info.get("pattern")
    if isinstance(raw, (list, tuple)):
        return {str(p) for p in raw}
    return {str(raw)} if raw else set()


def measure_kind(exercise_id: str, *, is_test: bool = False) -> Optional[str]:
    """``hang_margin`` | ``last_set_reps`` | ``dp_reps`` | ``None``.

    dp_reps (double progression): a loaded exercise (external_load or
    total_load) prescribed in reps without a work time, not a hang, not a pull
    (those have their own measure), not loading-pin finger work, not a test.
    """
    eid = str(exercise_id or "")
    if not eid or eid in MEASURE_EXCLUDED or eid.startswith("test_"):
        return None
    info = _catalog().get(eid) or {}
    if str(info.get("category") or "") == "test":
        return None
    if eid in HANG_MARGIN_EXERCISES:
        return None if is_test else MEASURE_HANG_MARGIN
    if eid in LAST_SET_REPS_EXERCISES:
        return None if is_test else MEASURE_LAST_SET_REPS
    if info.get("load_model") not in ("external_load", "total_load"):
        return None
    if info.get("loading_pin"):
        return None
    if _patterns(info) & _HANG_PATTERNS:
        return None
    pd = info.get("prescription_defaults") or {}
    reps = pd.get("reps")
    work = pd.get("work_seconds") or pd.get("hang_seconds") or pd.get("duration_seconds")
    if not isinstance(reps, (int, float)) or reps <= 0 or work:
        return None
    return MEASURE_DP_REPS


# ---------------------------------------------------------------------------
# Double progression
# ---------------------------------------------------------------------------

#: ENGINEERING CONSTANTS (R4 §3c): rep range lo = prescribed reps,
#: hi = lo + max(2, round(0.25·lo)); at the top of the range the load rises by
#: 2.5 % (1.25 % on finger-loading exercises) and the target goes back to lo.
DP_MIN_SPAN = 2
DP_SPAN_PCT = 0.25
DP_LOAD_STEP_PCT = 0.025
DP_FINGER_LOAD_STEP_PCT = 0.0125
#: Accessories without a measure (DECISIONS 2026-10-04): easy +5 %,
#: very_easy +10 %. hard / very_hard keep the adjustment policy.
DP_LABEL_STEP_PCT: Dict[str, float] = {"very_easy": 0.10, "easy": 0.05}


def dp_range(lo: int) -> Tuple[int, int]:
    lo = max(1, int(lo))
    return lo, lo + max(DP_MIN_SPAN, int(round(DP_SPAN_PCT * lo)))


def prescribed_reps_of(exercise_id: str, *sources: Mapping[str, Any]) -> Optional[int]:
    """First positive integer reps among the sources, else the catalog default."""
    for src in sources:
        for key in ("prescribed_reps", "reps"):
            v = _int(src.get(key)) if isinstance(src, Mapping) else None
            if v:
                return v
        rr = src.get("reps_range") if isinstance(src, Mapping) else None
        if isinstance(rr, (list, tuple)) and rr and _int(rr[0]):
            return _int(rr[0])
    return _int(((_catalog().get(exercise_id) or {}).get("prescription_defaults") or {}).get("reps"))


def dp_target_for(entry: Optional[Mapping[str, Any]], lo: int) -> int:
    """The target reps to show for the next session (stored, else lo).

    A stored target from a different range (the prescription changed) is not
    trusted: back to lo.
    """
    lo, hi = dp_range(lo)
    if not entry:
        return lo
    rng = entry.get("dp_range")
    t = _int(entry.get("dp_target_reps"))
    if t is None or not (isinstance(rng, (list, tuple)) and len(rng) == 2 and int(rng[0]) == lo):
        return lo
    return max(lo, min(hi, t))


def is_finger_loading(exercise_id: str) -> bool:
    tags = (_catalog().get(exercise_id) or {}).get("stress_tags") or {}
    return str(tags.get("fingers") or "") in ("medium", "high")


# ---------------------------------------------------------------------------
# Pain
# ---------------------------------------------------------------------------

#: DECISIONS 2026-10-04: score 2 → 7 days, score 3 → 14 days. Score 1 is only
#: recorded. Not an RPE field.
PAIN_BLOCK_DAYS: Dict[int, int] = {2: 7, 3: 14}
#: Read-side effects on exercises outside the anchored four (anchored_load has
#: its own copy of the same rule): −10 % on the zone, hangs ≤ 85 % / 80 %.
PAIN_LOAD_MULT = 0.90
PAIN_HANG_CAP_SCORE2 = 0.85
PAIN_HANG_CAP_SCORE3 = 0.80
#: Pain site → limitations zone (B38) for the score-3 suggestion.
PAIN_SITE_TO_LIMITATION_ZONE: Dict[str, str] = {"fingers": "finger", "elbow": "elbow", "shoulder": "shoulder"}
_SHOULDER_EXERCISES = frozenset({"weighted_pullup", "weighted_chinup", "weighted_dip"})


def sanitize_pain(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return None
    score = _int(raw.get("score"), allow_zero=True)
    if score is None or not (0 <= score <= 3):
        return None
    site = raw.get("site")
    site = str(site) if site in PAIN_SITES else None
    return {"score": score, "site": site}


def exercise_pain_sites(exercise_id: str) -> Set[str]:
    """Pain sites whose block applies to this exercise."""
    info = _catalog().get(exercise_id) or {}
    tags = info.get("stress_tags") or {}
    sites: Set[str] = set()
    if str(tags.get("fingers") or "") in ("medium", "high"):
        sites.add("fingers")
    if str(tags.get("elbow") or "") in ("medium", "high"):
        sites.add("elbow")
    if "shoulder_sensitive" in (info.get("contraindications") or []) or exercise_id in _SHOULDER_EXERCISES:
        sites.add("shoulder")
    if info.get("load_model") in ("external_load", "total_load"):
        sites.add("other")
    return sites


def active_pain_block(state: Mapping[str, Any], sites: Iterable[str], on: Any) -> Optional[Dict[str, Any]]:
    """Worst active pain block (score ≥ 2) among ``sites`` on date ``on``."""
    day = _parse(on)
    if day is None:
        return None
    blocks = ((state.get("progression_counters") or {}).get("pain_blocks") or {})
    if not isinstance(blocks, Mapping):
        return None
    worst: Optional[Dict[str, Any]] = None
    for site in sites:
        b = blocks.get(site)
        if not isinstance(b, Mapping):
            continue
        start, until = _parse(b.get("from")), _parse(b.get("until"))
        score = _int(b.get("score"), allow_zero=True) or 0
        if start is None or until is None or score < 2 or not (start <= day <= until):
            continue
        if worst is None or score > worst["score"]:
            worst = {"site": site, "score": score, "from": start.isoformat(), "until": until.isoformat()}
    return worst


def _strip_source(block: Any, source: str) -> Optional[Dict[str, Any]]:
    """``block`` with every link written by ``source`` removed from its chain."""
    if not isinstance(block, Mapping):
        return None
    prev = _strip_source(block.get("prev"), source)
    if block.get("source") == source:
        return prev
    out = {k: v for k, v in block.items() if k != "prev"}
    if prev is not None:
        out["prev"] = prev
    return out


def pain_session_key(log_entry: Mapping[str, Any]) -> str:
    return f"{str(log_entry.get('date') or '')[:10]}|{str(log_entry.get('session_id') or '')}"


def record_pain(updated: Dict[str, Any], log_entry: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Write ``progression_counters.pain_blocks[site]`` from the log's pain.

    A block is never shortened by ANOTHER session's milder report: the stored
    block is replaced only when the new one ends later or scores higher, and
    the replaced block is kept under ``prev``.

    A295 review: a block remembers the session that wrote it (``source`` =
    ``date|session_id``). A resubmit of the SAME session that carries a pain
    (pencil edit, outbox retry) first removes what that session wrote — the
    applied/base_before pattern of the double progression — and then applies
    the new score: 3 → 0 by mistake is undone, a retry is idempotent. A
    resubmit WITHOUT ``pain`` (not answered) leaves the blocks untouched, like
    the completion log. Returns the block written, if any.
    """
    pain = sanitize_pain(log_entry.get("pain"))
    day = _parse(log_entry.get("date"))
    if pain is None or day is None:
        return None
    source = pain_session_key(log_entry)
    counters = updated.setdefault("progression_counters", {})
    blocks = counters.get("pain_blocks")
    if not isinstance(blocks, dict):
        blocks = {}
    for site in list(blocks):
        cleaned = _strip_source(blocks.get(site), source)
        if cleaned is None:
            blocks.pop(site, None)
        else:
            blocks[site] = cleaned
    if pain["score"] < 2:
        if blocks or "pain_blocks" in counters:
            counters["pain_blocks"] = blocks
        return None
    counters["pain_blocks"] = blocks
    site = pain["site"] or "other"
    days = PAIN_BLOCK_DAYS[3 if pain["score"] >= 3 else 2]
    block: Dict[str, Any] = {
        "score": pain["score"],
        "from": day.isoformat(),
        "until": (day + timedelta(days=days - 1)).isoformat(),
        "source": source,
    }
    cur = blocks.get(site)
    if isinstance(cur, Mapping):
        cur_until = str(cur.get("until") or "")
        cur_score = _int(cur.get("score"), allow_zero=True) or 0
        if cur_until >= block["until"] and cur_score >= block["score"]:
            return dict(cur)
        block["prev"] = dict(cur)
    blocks[site] = block
    return block


#: A295 review: during a pain block the read side prescribes −10 %. Writing
#: the reduced load back as the new working load made the cut compound every
#: session (−27 % after three sessions, permanent after the block). Under a
#: block the stored next_* is held at its pre-block value; only a DOWN step
#: (hard label, failed measure, structural clamp) moves it, applied to that
#: value. Same freshness as the read side.
PAIN_HOLD_FRESH_D = 60


def pain_hold_next(
    existing: Optional[Mapping[str, Any]],
    *,
    field: str,
    used: float,
    computed_next: float,
    session_key: str,
    date_value: str,
    reference_before: Optional[float] = None,
    reference_cut: Optional[float] = None,
) -> Tuple[float, Dict[str, Any]]:
    """(next value, ``pain_hold`` snapshot) for a write under a pain block.

    ``computed_next`` is what the normal rule produced from ``used``; its
    upward part is dropped (freeze) and the downward part is applied to the
    pre-block value instead of to the (pain-reduced) load used. The pre-block
    value is, in order:

    - the snapshot of this same session (replay → same result);
    - with the two deterministic reads of that date, ``reference_before``
      (without the block) and ``reference_cut`` (with it): the load used with
      exactly that cut undone, never below the load used and never above the
      unpained read. Following the prescription → the pre-block load; a
      session prescribed before the pain (cached plan, the session that
      reported it) → the load used, never inflated; an athlete lifting more
      than the engine → the load used;
    - the fresh ``existing[field]``;
    - else the load used.
    """
    snap = (existing or {}).get("pain_hold")
    before: Optional[float]
    if isinstance(snap, Mapping) and snap.get("key") == session_key:
        before = _num(snap.get("next_before"))
    elif _num(reference_before) is not None and (_num(reference_cut) or 0) > 0:
        ref, cut = float(_num(reference_before)), float(_num(reference_cut))
        before = max(float(used), min(ref, float(used) * ref / cut))
    else:
        before = _num((existing or {}).get(field))
        upd, now = _parse((existing or {}).get("updated_at")), _parse(date_value)
        if before is not None and (upd is None or now is None or (now - upd).days > PAIN_HOLD_FRESH_D):
            before = None
    delta = min(float(computed_next) - float(used), 0.0)
    base = float(used) if before is None else before
    return _round_half(base + delta), {"key": session_key, "next_before": before}


def state_without_pain(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Shallow copy of ``state`` with no pain blocks (for the unpained read)."""
    out = dict(state)
    counters = dict(out.get("progression_counters") or {})
    counters.pop("pain_blocks", None)
    out["progression_counters"] = counters
    return out


def _loading_pin_max(state: Mapping[str, Any], hand: str) -> Optional[float]:
    best = 0.0
    for bl in ((state.get("baselines") or {}).get("loading_pin") or []):
        if isinstance(bl, Mapping) and str(bl.get("hand") or "").lower() == hand:
            best = max(best, _num(bl.get("max_load_kg")) or 0.0)
    return best or None


def pain_adjust_suggested(
    suggested: Dict[str, Any],
    state: Mapping[str, Any],
    exercise_id: str,
    on: Any,
    *,
    load_model: Optional[str],
    bodyweight: float,
    official_hang_total: Optional[float] = None,
    flag_only: bool = False,
) -> Optional[Dict[str, Any]]:
    """Read-side pain block for a NON-anchored exercise (in place).

    −10 % on the suggested load of the zone; a finger hang is also capped at
    85 % (score 2) / 80 % (score 3) of the official hang max when one is known.
    Loading-pin exercises carry their load per hand (``right_hand`` /
    ``left_hand``): the same cut applies there, and a finger lift is capped at
    the same share of that hand's max. Sets ``pain_flag`` so the UI says "pain
    reported, keep it sub-max". ``flag_only`` (test sessions: a test is a max,
    never a cut load) sets the flag and the block without touching loads.
    Depends only on the date → deterministic.
    """
    block = active_pain_block(state, exercise_pain_sites(exercise_id), on)
    if block is None:
        return None
    suggested["pain_flag"] = True
    suggested["pain"] = dict(block)
    if flag_only:
        return block
    cap_share = PAIN_HANG_CAP_SCORE3 if block["score"] >= 3 else PAIN_HANG_CAP_SCORE2
    patterns = _patterns(_catalog().get(exercise_id) or {})
    finger_hang = "fingers" == block["site"] and bool(patterns & {"isometric_hang", "isometric_lift"})
    ext = suggested.get("suggested_external_load_kg")
    tot = suggested.get("suggested_total_load_kg")
    if load_model == "total_load" and isinstance(tot, (int, float)):
        new_total = float(tot) * PAIN_LOAD_MULT
        if official_hang_total and finger_hang:
            new_total = min(new_total, cap_share * float(official_hang_total))
        suggested["suggested_total_load_kg"] = _round_half(new_total)
        suggested["suggested_external_load_kg"] = _round_half(new_total - bodyweight)
    elif isinstance(ext, (int, float)) and ext > 0:
        suggested["suggested_external_load_kg"] = _round_half(float(ext) * PAIN_LOAD_MULT)
    for hand in ("right", "left"):
        hd = suggested.get(f"{hand}_hand")
        if not isinstance(hd, dict):
            continue
        h_ext = hd.get("suggested_external_load_kg")
        if not isinstance(h_ext, (int, float)) or isinstance(h_ext, bool) or h_ext <= 0:
            continue
        new_ext = float(h_ext) * PAIN_LOAD_MULT
        hand_max = _loading_pin_max(state, hand) if finger_hang else None
        if hand_max:
            new_ext = min(new_ext, cap_share * hand_max)
        hd["suggested_external_load_kg"] = _round_half(new_ext)
    return block


def limitation_suggestion_for_pain(log_entry: Mapping[str, Any], limitation_map: Mapping[str, str]) -> Optional[Dict[str, Any]]:
    """Pain 3 → suggest marking the zone as a limitation (B38 mechanism)."""
    pain = sanitize_pain(log_entry.get("pain"))
    if pain is None or pain["score"] < 3:
        return None
    zone = PAIN_SITE_TO_LIMITATION_ZONE.get(pain["site"] or "")
    if not zone:
        return None
    current = limitation_map.get(zone)
    if current in ("active", "severe"):
        return None
    return {
        "exercise_id": None,
        "zone": zone,
        "current_severity": current or "none",
        "suggested_severity": "active",
        "reason": f"pain 3/3 reported on {pain['site']} — consider marking it as a limitation",
        "source": "pain",
    }


# ---------------------------------------------------------------------------
# Session difficulty: only from what was rated, only with enough coverage
# ---------------------------------------------------------------------------

#: R4 §3e: the session difficulty is written only when the rated exercises
#: cover at least half of the session's fatigue cost. One very_hard tapped on a
#: warm-up does not make a very_hard session (and does not trigger rule 2 of
#: check_adaptive_replan).
DIFFICULTY_MIN_COVERAGE = 0.5

_LABEL_TO_SCORE = {"very_easy": 1, "easy": 2, "ok": 3, "hard": 4, "very_hard": 5}
_SCORE_THRESHOLDS = ((1.5, "very_easy"), (2.5, "easy"), (3.5, "ok"), (4.5, "hard"))


def _score_to_label(score: float) -> str:
    for threshold, label in _SCORE_THRESHOLDS:
        if score <= threshold:
            return label
    return "very_hard"


def derive_session_difficulty(
    log_entry: Mapping[str, Any],
    exercises_by_id: Mapping[str, Mapping[str, Any]],
) -> Optional[str]:
    """Fatigue-cost-weighted mean of the RATED labels, or ``None``.

    Skipped items (completed false) are outside both numerator and
    denominator. ``None`` when nothing is rated or the rated items cover less
    than DIFFICULTY_MIN_COVERAGE of the fatigue cost.
    """
    contract = log_contract(log_entry)
    items = ((log_entry.get("actual") or {}).get("exercise_feedback_v1") or [])
    total_w = rated_w = score_w = 0.0
    seen: Set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        eid = str(item.get("exercise_id") or "")
        if not eid or item.get("completed") is False:
            continue
        # Per-hand items of one exercise count once.
        key = eid
        if key in seen:
            continue
        seen.add(key)
        w = float((exercises_by_id.get(eid) or {}).get("fatigue_cost", 5) or 0)
        total_w += w
        label = feedback_rating(item, contract)
        if label is None:
            continue
        rated_w += w
        score_w += _LABEL_TO_SCORE[label] * w
    if rated_w <= 0 or total_w <= 0 or rated_w / total_w < DIFFICULTY_MIN_COVERAGE:
        return None
    return _score_to_label(score_w / rated_w)


def rated_exercise_feedback(log_entry: Mapping[str, Any]) -> Dict[str, str]:
    """{exercise_id: label} of the RATED items only (feedback_log display)."""
    contract = log_contract(log_entry)
    out: Dict[str, str] = {}
    for item in ((log_entry.get("actual") or {}).get("exercise_feedback_v1") or []):
        if not isinstance(item, Mapping):
            continue
        eid = str(item.get("exercise_id") or "")
        label = feedback_rating(item, contract)
        if eid and label is not None:
            out[eid] = label
    return out


# ---------------------------------------------------------------------------
# Router sanitisation (B156 style: drop + warn, never 4xx — an outbox retry
# must not get stuck on a bad field)
# ---------------------------------------------------------------------------

def sanitize_log_entry(log_entry: Dict[str, Any]) -> List[str]:
    """Clean the A295 fields of a feedback log entry in place; return warnings."""
    warnings: List[str] = []
    if "feedback_contract" in log_entry:
        c = _int(log_entry.get("feedback_contract"), allow_zero=True)
        if c is None:
            warnings.append("feedback_contract dropped (not an integer)")
            log_entry.pop("feedback_contract", None)
        else:
            log_entry["feedback_contract"] = c
    if "pain" in log_entry:
        clean = sanitize_pain(log_entry.get("pain"))
        if clean is None:
            if log_entry.get("pain") is not None:
                warnings.append("pain dropped (score must be 0..3)")
            log_entry.pop("pain", None)
        else:
            log_entry["pain"] = clean
    items = ((log_entry.get("actual") or {}).get("exercise_feedback_v1") or [])
    for item in items:
        if not isinstance(item, dict):
            continue
        eid = item.get("exercise_id")
        if "feedback_label" in item:
            raw = item.get("feedback_label")
            if raw is None or str(raw).strip().lower() not in VALID_LABELS + ("skipped",):
                if raw is not None:
                    warnings.append(f"{eid}: feedback_label {raw!r} dropped")
                item.pop("feedback_label", None)
        if "last_set_reps" in item:
            v = _int(item.get("last_set_reps"), allow_zero=True)
            if v is None or not (0 <= v <= LAST_SET_REPS_MAX):
                warnings.append(f"{eid}: last_set_reps {item.get('last_set_reps')!r} dropped")
                item.pop("last_set_reps", None)
            else:
                item["last_set_reps"] = v
        if "target_reps" in item:
            v = _int(item.get("target_reps"))
            if v is None or v > TARGET_REPS_MAX:
                warnings.append(f"{eid}: target_reps {item.get('target_reps')!r} dropped")
                item.pop("target_reps", None)
            else:
                item["target_reps"] = v
        if "hang_margin" in item:
            if item.get("hang_margin") not in HANG_MARGINS:
                warnings.append(f"{eid}: hang_margin {item.get('hang_margin')!r} dropped")
                item.pop("hang_margin", None)
        if "hang_held_s" in item:
            v = _num(item.get("hang_held_s"))
            if v is None or not (0 < v <= HANG_HELD_MAX_S):
                warnings.append(f"{eid}: hang_held_s {item.get('hang_held_s')!r} dropped")
                item.pop("hang_held_s", None)
            else:
                item["hang_held_s"] = v
        # A298: bodyweight hold / technique measures.
        from backend.engine.bw_progression import sanitize_item as _bw_sanitize

        _bw_sanitize(item, warnings)
        if "problems" in item:
            # A296: limit problem log — invalid rows dropped one by one.
            from backend.engine.limit_log import sanitize_problems

            clean, problem_warnings = sanitize_problems(item.get("problems"))
            warnings.extend(f"{eid}: {w}" for w in problem_warnings)
            if clean:
                item["problems"] = clean
            else:
                item.pop("problems", None)
    return warnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any, *, allow_zero: bool = False) -> Optional[int]:
    n = _num(value)
    if n is None or n != int(n):
        return None
    n_i = int(n)
    if n_i < 0 or (n_i == 0 and not allow_zero):
        return None
    return n_i


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


def _round_half(value: float) -> float:
    return round(float(value) / 0.5) * 0.5


__all__ = [
    "FEEDBACK_CONTRACT_MEASURED", "HANG_MARGINS", "PAIN_SITES",
    "MEASURE_HANG_MARGIN", "MEASURE_LAST_SET_REPS", "MEASURE_DP_REPS",
    "log_contract", "feedback_rating", "has_measure", "measure_kind",
    "dp_range", "dp_target_for", "prescribed_reps_of", "is_finger_loading",
    "record_pain", "pain_session_key", "pain_hold_next", "state_without_pain", "active_pain_block", "exercise_pain_sites", "pain_adjust_suggested",
    "limitation_suggestion_for_pain", "derive_session_difficulty", "rated_exercise_feedback",
    "sanitize_log_entry", "attach_measure_fields",
]


# ---------------------------------------------------------------------------
# Read side for custom / generated rows (flat CustomSessionExercise shape)
# ---------------------------------------------------------------------------

def attach_measure_fields(
    state: Mapping[str, Any], exercises: Sequence[Mapping[str, Any]], on: Any,
) -> List[Dict[str, Any]]:
    """Copies of flat exercise rows with ``measure`` (and, for double
    progression, ``target_reps`` + ``dp_range`` read from the working entry).
    Never mutates the input, never writes state."""
    from backend.engine.progression_v1 import EXTERNAL_LOAD_FRESHNESS_DAYS, _best_entry

    out: List[Dict[str, Any]] = []
    for ex in exercises or []:
        if not isinstance(ex, Mapping):
            continue
        copy = dict(ex)
        eid = str(copy.get("exercise_id") or "")
        kind = measure_kind(eid)
        if kind:
            copy["measure"] = kind
            if kind == MEASURE_DP_REPS:
                lo = _int(copy.get("reps")) or prescribed_reps_of(eid)
                if lo:
                    entry = _best_entry(
                        dict(state), eid, {}, str(on or ""), freshness_days=EXTERNAL_LOAD_FRESHNESS_DAYS,
                    ) if on else None
                    copy["target_reps"] = dp_target_for(entry, lo)
                    copy["dp_range"] = list(dp_range(lo))
        out.append(copy)
    return out
