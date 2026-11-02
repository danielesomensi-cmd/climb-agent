"""Outdoor session logging — validation, stats, and thin wrappers over storage.

I/O is delegated to backend.engine.storage.
"""

from __future__ import annotations

import copy
import logging
import math
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from backend.engine import storage
from backend.engine.grade_evidence import (
    chronological,
    grade_rank,
    is_first_go_send,
    route_key,
)
from backend.engine.outdoor_attempt import (
    RESULTS,
    ROPE_ROLES,
    normalize_entry_attempts,
    result_of,
    route_lead_sent,
)
from backend.engine.outdoor_attempt import rope_role as attempt_rope_role

logger = logging.getLogger(__name__)


REQUIRED_FIELDS = {"log_version", "date", "spot_name", "discipline", "duration_minutes", "routes"}

# A225: accepted log schema versions. v1 logs predate the v2 optional fields
# (day_type, route_profile, conditions.temperature/condition_band) and stay valid.
VALID_LOG_VERSIONS = {"outdoor.v1", "outdoor.v2"}
CURRENT_LOG_VERSION = "outdoor.v2"

# outdoor.v2 optional-field vocabularies (mirror the C241 strategy catalog).
VALID_DAY_TYPES = {"project", "onsight_flash", "volume", "scout_easy"}
VALID_ROUTE_PROFILE = {
    "wall_angle": {"slab", "vertical", "overhang", "roof"},
    "route_length": {"short_power", "medium", "long_endurance"},
    "hold_style": {"crimp", "sloper_pinch", "mixed"},
    "target_grade_relative": {"within_limit", "at_or_above_limit"},
}
VALID_CONDITION_BANDS = {"prime", "ok", "poor_hot_humid", "poor_cold_dry"}

# ---------------------------------------------------------------------------
# Outdoor load score helpers
# ---------------------------------------------------------------------------

# Outdoor load weight per grade. Anchored to the PRE-B302 grade spacing so the
# ladder fix (which inserted 5a+/5b+/5c+ into GRADE_ORDER) does not perturb
# historical outdoor load: the new grade-5 half-steps share their base grade's
# weight, and every grade from 6a up keeps its original weight.
# NOTE: this weight is ABSOLUTE per grade, not relative to the climber's max —
# a 6a weighs the same for an 8a and a 6a climber. Making it relative to ability
# is tracked separately as B-OUTDOOR-RELATIVE-LOAD.
_OUTDOOR_WEIGHT_ANCHOR: List[str] = [
    "5a", "5b", "5c",
    "6a", "6a+", "6b", "6b+", "6c", "6c+",
    "7a", "7a+", "7b", "7b+", "7c", "7c+",
    "8a", "8a+", "8b", "8b+", "8c", "8c+",
    "9a", "9a+",
]
_GRADE_WEIGHT: Dict[str, int] = {g: i + 3 for i, g in enumerate(_OUTDOOR_WEIGHT_ANCHOR)}
# Fold the newly-added grade-5 half-steps onto their base grade's weight.
_GRADE_WEIGHT.update({
    "5a+": _GRADE_WEIGHT["5a"],
    "5b+": _GRADE_WEIGHT["5b"],
    "5c+": _GRADE_WEIGHT["5c"],
})
_UNKNOWN_GRADE_WEIGHT = 10

_STYLE_MODIFIER: Dict[str, float] = {
    "onsight": 1.2,
    "flash": 1.1,
    "redpoint": 1.0,
    "project": 0.7,
    "repeat": 0.5,
}

_LOAD_CAP = 85

# B327: an attempt that ended in a fall is real work — often the most intense
# burn of the day — but it stops short of the top, so it carries slightly less
# than a completed ascent. Any other/absent result counts as a full ascent.
# A324: ``aid`` (A0) weighs like ``topped_out`` — 1.0, not discounted
# (Daniele, 2026-11-02): the athlete still climbs the whole pitch.
_RESULT_MODIFIER: Dict[str, float] = {
    "sent": 1.0,
    "fell": 0.8,
    "topped_out": 1.0,
    "aid": 1.0,
}

# A324 — ENGINEERING CONSTANT (Daniele, 2026-11-02): a pitch climbed on second
# or top-rope carries less load than the same pitch on lead (no clipping, no
# run-out, no fall exposure). The direction is documented for intermediate
# climbers — higher blood lactate and heart rate on lead than on top-rope on the
# same route (Draper et al. 2010, Eur J Sport Sci 10:13-20), anxiety and plasma
# cortisol that change with the rope protocol (Hodgson et al. 2009, Br J Sports
# Med 43:531-535) — while in advanced climbers the gap shrinks (Fryer et al.
# 2012). The size is not documented: 0.85 is our number. Second and top-rope
# weigh the same. Applied per attempt in BOTH formulas (B327 and v2), times the
# result factor; an attempt without ``rope_role`` is lead (1.0), so every log
# written before A324 keeps its load.
ROPE_ROLE_LOAD_FACTOR: Dict[str, float] = {
    "lead": 1.0,
    "second": 0.85,
    "toprope": 0.85,
}


def _rope_role_factor(attempt: Any) -> float:
    return ROPE_ROLE_LOAD_FACTOR[attempt_rope_role(attempt)]


def _volume_factor(num_attempts: int) -> float:
    """Log-scaled volume factor over ATTEMPTS: 1=1.0, 3=2.0, 9=3.0, capped at 3.0.

    B327 widened this from the D151 version (base-5 log, capped at 2.0, counted
    over routes). Two reasons:

      * counting *routes* made repeats free — six burns on one project scored
        the same as touching it once;
      * the 2.0 cap was reached at five routes, so an eight-pitch volume day and
        a five-pitch day were indistinguishable.
    """
    if num_attempts <= 1:
        return 1.0
    return min(3.0, 1.0 + math.log(num_attempts, 3))


# ---------------------------------------------------------------------------
# B394 — load relative to the athlete's max (only for logs from 2026-10-17)
# ---------------------------------------------------------------------------
#
# The B327 formula below scored Daniele's 7c+ project days at ~22 and never
# reached the replanner's OUTDOOR_RIPPLE_THRESHOLD (65) in 58 logged days
# (max 33): a limit day at the crag never protected the day after. Three causes:
# the absolute grade weight, the `project` 0.7 / `fell` 0.8 discounts on the
# hardest burns, and the MEAN over all attempts (warm-ups dilute it).
#
# v2 (Daniele, 2026-10-17): grade weight relative to the athlete's lead max
# redpoint, intensity = mean of the two hardest attempts, no discount for
# `project` or falls. Applied ONLY to logs stamped with ``load_ref_grade`` —
# stamped at write time from OUTDOOR_LOAD_V2_FROM on. Older logs keep B327 for
# good (Daniele: «non ricalcolare il passato»), and a stamped log keeps the max
# it was logged against, so a later grade bump never rewrites past days.
OUTDOOR_LOAD_V2_FROM = "2026-10-17"
_V2_ANCHOR = 40.0          # attempt score at the athlete's max (before style)
_V2_DECAY = 0.12           # per grade step below the max
_V2_FLOOR = 0.15           # lowest relative weight (easy warm-up terrain)
_V2_CEIL = 1.1             # above the max
_V2_UNKNOWN_REL = 0.3      # ungraded pitch ("?") in a stamped log
_V2_TOP_K = 2              # intensity = mean of the K hardest attempts
_V2_STYLE_MODIFIER: Dict[str, float] = {
    "onsight": 1.2,
    "flash": 1.1,
    "redpoint": 1.0,
    "project": 1.0,
    "repeat": 0.5,
}


def outdoor_load_ref_grade(state: Optional[Dict[str, Any]]) -> Optional[str]:
    """The athlete's lead max redpoint on the outdoor ladder, or None."""
    grades = ((state or {}).get("assessment") or {}).get("grades") or {}
    g = str(grades.get("lead_max_rp") or "").strip().lower()
    return g if g in _OUTDOOR_WEIGHT_ANCHOR else None


def stamp_load_ref_grade(
    entry: Dict[str, Any],
    state: Optional[Dict[str, Any]],
    previous: Optional[Dict[str, Any]] = None,
) -> None:
    """Set ``entry["load_ref_grade"]`` in place when the v2 load applies (B394).

    An edit keeps the reference the log was first stamped with. Otherwise only a
    log dated on/after OUTDOOR_LOAD_V2_FROM, not a pure boulder day (the ladder
    is the lead one), with a known lead max, is stamped.
    """
    prev_ref = (previous or {}).get("load_ref_grade")
    if prev_ref:
        entry["load_ref_grade"] = prev_ref
        return
    if str(entry.get("date") or "") < OUTDOOR_LOAD_V2_FROM:
        return
    if entry.get("discipline") == "boulder":
        return
    ref = outdoor_load_ref_grade(state)
    if ref:
        entry["load_ref_grade"] = ref


def _compute_outdoor_load_v2(entry: Dict[str, Any], ref: str) -> int:
    ref_idx = _OUTDOOR_WEIGHT_ANCHOR.index(ref)
    scores: List[float] = []
    for route in entry.get("routes") or []:
        grade = str(route.get("grade") or "").strip().lower()
        if grade in _OUTDOOR_WEIGHT_ANCHOR:
            steps = ref_idx - _OUTDOOR_WEIGHT_ANCHOR.index(grade)
            rel = max(_V2_FLOOR, min(_V2_CEIL, 1.0 - _V2_DECAY * steps))
        else:
            rel = _V2_UNKNOWN_REL
        style = route.get("style")
        modifier = _V2_STYLE_MODIFIER.get(style, 1.0) if style else 1.0
        # Every attempt counts the same whatever its result: a fall at the
        # crux of the project is the hardest burn of the day, and A0 (aid)
        # weighs like a fall (A324). Only the rope role discounts it: second /
        # top-rope × ROPE_ROLE_LOAD_FACTOR (A324), so it also weighs less in
        # the choice of the two hardest attempts. The volume factor still
        # counts every attempt — a pitch on second is real volume.
        for attempt in route.get("attempts") or [{}]:
            scores.append(_V2_ANCHOR * rel * modifier * _rope_role_factor(attempt))
    if not scores:
        return 0
    top = sorted(scores, reverse=True)[:_V2_TOP_K]
    return round(min(_LOAD_CAP, sum(top) / len(top) * _volume_factor(len(scores))))


def compute_outdoor_load_score(entry: Dict[str, Any]) -> int:
    """Compute a deterministic load score for an outdoor session.

    B394: a log carrying ``load_ref_grade`` uses the v2 formula (see
    ``OUTDOOR_LOAD_V2_FROM``); every other log uses B327, described here.

    B327 formula: ``avg_intensity × volume_factor``, where both terms are
    computed over **attempts**, not routes:

        attempt_score  = grade_weight × style_modifier × result_modifier
                         × rope_role_factor (A324: lead 1.0, second/top-rope 0.85)
        avg_intensity  = mean(attempt_score)      → how hard the day was
        volume_factor  = 1 + log₃(n_attempts)     → how much of it there was

    Returns an int capped at 85, comparable to indoor ``session_load_score``.

    **Why duration is no longer a factor (B327).** The D151 formula multiplied
    by ``duration_minutes / 120``, which made a day with longer rests score
    *higher* than the same climbing done back-to-back — backwards, since rest is
    what removes stress. It also leaned on the least reliable field in the log:
    users log the climbs but rarely the rests, so the recorded duration is a
    lower bound of unknown tightness. Volume is already carried by the attempt
    count; duration added nothing but noise pointing the wrong way.
    """
    ref = str(entry.get("load_ref_grade") or "").strip().lower()
    if ref in _OUTDOOR_WEIGHT_ANCHOR:
        return _compute_outdoor_load_v2(entry, ref)

    attempt_scores: List[float] = []
    for route in entry.get("routes") or []:
        grade = route.get("grade", "")
        weight = _GRADE_WEIGHT.get(grade, _UNKNOWN_GRADE_WEIGHT)
        style = route.get("style")
        modifier = _STYLE_MODIFIER.get(style, 1.0) if style else 1.0

        # A route with no attempts array still counts as one ascent: older
        # outdoor.v1 logs and hand-written entries omit it.
        attempts = route.get("attempts") or [{}]
        for attempt in attempts:
            result = result_of(attempt)
            attempt_scores.append(
                weight * modifier * _RESULT_MODIFIER.get(result, 1.0)
                * _rope_role_factor(attempt)  # A324
            )

    if not attempt_scores:
        return 0

    avg_intensity = sum(attempt_scores) / len(attempt_scores)
    return round(min(_LOAD_CAP, avg_intensity * _volume_factor(len(attempt_scores))))
VALID_DISCIPLINES = {"lead", "boulder", "both"}


# ---------------------------------------------------------------------------
# Active outdoor session — duration derivation (A225)
# ---------------------------------------------------------------------------

# A real outdoor day rarely exceeds ~10 h. A timer left running ("Start" pressed
# then the session closed the next day) would otherwise derive an absurd
# duration. We cap derived durations here so a stale ``started_at`` can never
# silently overwrite a reasonable value.
OUTDOOR_SESSION_MAX_MINUTES = 600  # 10 hours


def derive_outdoor_duration(
    started_at_iso: Optional[str],
    now: datetime,
    manual_override: Optional[int] = None,
) -> Dict[str, Any]:
    """Resolve an outdoor session's ``duration_minutes`` at close time.

    Rules (deterministic):
      1. An explicit, valid ``manual_override`` (int ≥ 1) always wins — it is the
         user's typed value and must never be clobbered by a stale timer.
      2. Otherwise derive from ``started_at → now`` (floored at 1 min).
      3. If the derived value exceeds ``OUTDOOR_SESSION_MAX_MINUTES`` (stale /
         overnight timer), cap it and flag ``capped=True`` + ``raw_minutes`` so the
         caller can ask the user to confirm instead of writing an absurd number.
      4. If ``started_at`` is missing/invalid and no override is given → ``None``
         (the caller must supply a manual value).

    Returns ``{minutes, capped, raw_minutes, source}`` where ``source`` is one of
    ``manual | timer | timer_capped | none``.
    """
    if isinstance(manual_override, int) and not isinstance(manual_override, bool) and manual_override >= 1:
        return {"minutes": manual_override, "capped": False, "raw_minutes": None, "source": "manual"}

    try:
        started = datetime.fromisoformat(started_at_iso) if started_at_iso else None
    except (ValueError, TypeError):
        started = None
    if started is None:
        return {"minutes": None, "capped": False, "raw_minutes": None, "source": "none"}

    raw = round((now - started).total_seconds() / 60)
    if raw < 1:
        raw = 1

    if raw > OUTDOOR_SESSION_MAX_MINUTES:
        return {
            "minutes": OUTDOOR_SESSION_MAX_MINUTES,
            "capped": True,
            "raw_minutes": raw,
            "source": "timer_capped",
        }
    return {"minutes": raw, "capped": False, "raw_minutes": None, "source": "timer"}


def validate_outdoor_entry(entry: Dict[str, Any]) -> List[str]:
    """Validate an outdoor session entry. Returns list of error strings (empty = valid)."""
    errors: List[str] = []

    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")
        return errors

    if entry.get("log_version") not in VALID_LOG_VERSIONS:
        errors.append(
            f"Invalid log_version: {entry.get('log_version')} "
            f"(expected one of {sorted(VALID_LOG_VERSIONS)})"
        )

    if entry.get("discipline") not in VALID_DISCIPLINES:
        errors.append(f"Invalid discipline: {entry.get('discipline')}")

    # --- outdoor.v2 optional fields (A225) — only validated when present ----
    day_type = entry.get("day_type")
    if day_type is not None and day_type not in VALID_DAY_TYPES:
        errors.append(f"Invalid day_type: {day_type} (expected one of {sorted(VALID_DAY_TYPES)})")

    route_profile = entry.get("route_profile")
    if route_profile is not None:
        if not isinstance(route_profile, dict):
            errors.append("route_profile must be a dict")
        else:
            for key, value in route_profile.items():
                if key not in VALID_ROUTE_PROFILE:
                    errors.append(f"Unknown route_profile key: {key}")
                elif value is not None and value not in VALID_ROUTE_PROFILE[key]:
                    errors.append(
                        f"Invalid route_profile.{key}: {value} "
                        f"(expected one of {sorted(VALID_ROUTE_PROFILE[key])})"
                    )

    conditions = entry.get("conditions")
    if isinstance(conditions, dict):
        band = conditions.get("condition_band")
        if band is not None and band not in VALID_CONDITION_BANDS:
            errors.append(
                f"Invalid conditions.condition_band: {band} "
                f"(expected one of {sorted(VALID_CONDITION_BANDS)})"
            )
        temp = conditions.get("temperature")
        if temp is not None and not isinstance(temp, (int, float)):
            errors.append(f"Invalid conditions.temperature: {temp} (expected a number)")

    date_str = entry.get("date", "")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        errors.append(f"Invalid date format: {date_str} (expected YYYY-MM-DD)")

    duration = entry.get("duration_minutes")
    if not isinstance(duration, int) or duration < 1:
        errors.append(f"Invalid duration_minutes: {duration}")

    routes = entry.get("routes")
    if not isinstance(routes, list):
        errors.append("routes must be a list")
    else:
        for i, route in enumerate(routes):
            if not isinstance(route, dict):
                errors.append(f"routes[{i}] must be a dict")
                continue
            if not route.get("name"):
                errors.append(f"routes[{i}].name is required")
            if not route.get("grade"):
                errors.append(f"routes[{i}].grade is required")
            attempts = route.get("attempts")
            if not isinstance(attempts, list) or len(attempts) < 1:
                errors.append(f"routes[{i}].attempts must be a non-empty list")
                continue
            # A324: the outcome vocabulary, checked here too — a script import
            # bypasses the request models and could write any string.
            for j, attempt in enumerate(attempts):
                if not isinstance(attempt, dict):
                    errors.append(f"routes[{i}].attempts[{j}] must be a dict")
                    continue
                if attempt.get("result") not in RESULTS:
                    errors.append(
                        f"Invalid routes[{i}].attempts[{j}].result: {attempt.get('result')!r} "
                        f"(expected one of {list(RESULTS)})"
                    )
                role = attempt.get("rope_role")
                if role is not None and role not in ROPE_ROLES:
                    errors.append(
                        f"Invalid routes[{i}].attempts[{j}].rope_role: {role!r} "
                        f"(expected one of {list(ROPE_ROLES)})"
                    )

    return errors


def normalize_outdoor_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """A324: canonical attempts before an outdoor entry is written, in place.

    Explicit ``rope_role: "lead"`` is dropped (absent = lead); a boulder
    problem loses its rope role and ``aid`` becomes ``fell``. Normalised
    rather than rejected — a 422 makes the offline outbox discard the day.
    Every change is logged. Returns ``entry``.
    """
    changes = normalize_entry_attempts(entry)
    if changes:
        logger.info(
            "A324: outdoor %s %r normalised: %s",
            entry.get("date"), entry.get("spot_name"), "; ".join(changes),
        )
    return entry


# Keys a PUT never carries over from the replaced entry: the server sets them
# (``log_version``, ``load_ref_grade`` via stamp_load_ref_grade), they are
# read-time enrichments that must never be stored (``load_score``), or the edit
# form owns them (``routes``, ``notes``). Every form version shows and saves the
# routes and the notes, and a form older than A324 clears the notes by leaving
# the key out (``notes || undefined``): carrying them would undo that edit.
_NEVER_CARRIED = {
    "log_version", "load_ref_grade", "load_score", "original_spot_name", "routes", "notes",
}


def carry_over_unsent_keys(
    entry: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
    sent_keys: Iterable[str],
) -> List[str]:
    """A324 (B401 residual): a PUT keeps what it does not send, in place.

    PUT /api/outdoor/log replaces the whole entry, and the edit form never
    sends ``day_type``, ``route_profile``, ``conditions``, ``spot_id``,
    ``energy_level`` or ``overall_feeling`` — so a pencil edit stripped them.
    Every top-level key of the replaced entry that the request did not send
    (``sent_keys``: the request's fields set, explicit ``null`` included) is
    copied over, like B394 keeps ``load_ref_grade``. A key sent as ``null``
    stays cleared: that is the explicit way to remove a value.

    ``routes`` and ``notes`` are never carried (A324 review): the form owns
    them, and an absent ``notes`` is how a pre-A324 form clears the notes.

    ``spot_id`` belongs to the crag: it is not carried when the edit renames
    the crag (another ``spot_name``). Returns the keys carried over.
    """
    if not previous:
        return []
    sent = set(sent_keys or ())
    renamed = str(previous.get("spot_name") or "") != str(entry.get("spot_name") or "")
    carried: List[str] = []
    for key, value in previous.items():
        # Not sent = not chosen by the client, even when the request model
        # filled a default (``routes: []``): the stored value wins.
        if key in sent or key in _NEVER_CARRIED:
            continue
        if key == "spot_id" and renamed:
            continue
        entry[key] = copy.deepcopy(value)
        carried.append(key)
    return carried


# ---------------------------------------------------------------------------
# B362: one route, one name
# ---------------------------------------------------------------------------

def _route_key(name: Any) -> str:
    """Case- and whitespace-insensitive identity of a route name."""
    return " ".join(str(name or "").split()).casefold()


def _spot_key(entry: Dict[str, Any]) -> str:
    return " ".join(str(entry.get("spot_name") or "").split()).casefold()


def canonicalize_route_names(
    entry: Dict[str, Any], history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Align each route name with the spelling already logged at the same spot.

    "Cima nikita" and "Cima Nikita", or "Bibi " with a trailing space, used to
    become two routes in the outdoor report, so the history of one project was
    split in two. A name that matches an earlier route at the same crag
    case- and whitespace-insensitively takes the most frequent earlier spelling
    (ties: the most recent); anything else is only trimmed. Different names
    ("Jude" vs "Judd") are left alone — that is a judgement, not a typo.
    Mutates and returns ``entry``.
    """
    spot = _spot_key(entry)
    counts: Dict[str, Dict[str, List[Any]]] = {}
    for past in sorted(history, key=lambda e: str(e.get("date") or "")):
        if _spot_key(past) != spot or past.get("date") == entry.get("date"):
            continue
        for r in past.get("routes") or []:
            name = " ".join(str(r.get("name") or "").split())
            if not name:
                continue
            slot = counts.setdefault(_route_key(name), {}).setdefault(name, [0, ""])
            slot[0] += 1
            slot[1] = str(past.get("date") or "")
    for r in entry.get("routes") or []:
        if not isinstance(r, dict) or not isinstance(r.get("name"), str):
            continue
        name = " ".join(r["name"].split())
        spellings = counts.get(_route_key(name))
        if spellings:
            name = max(spellings.items(), key=lambda kv: (kv[1][0], kv[1][1]))[0]
        r["name"] = name
    return entry


def _history_for_names(user_id: Optional[str]) -> List[Dict[str, Any]]:
    """Past sessions for name alignment. Best-effort: a read failure must never
    block saving a session — the worst case is the old behaviour (trim only)."""
    try:
        return load_outdoor_sessions(user_id)
    except Exception:
        return []


def append_outdoor_session(entry: Dict[str, Any], user_id: Optional[str] = None) -> str:
    """Validate and append an outdoor session entry to the yearly JSONL log.

    Returns the path of the log file written to.
    Raises ValueError if validation fails.
    """
    normalize_outdoor_entry(entry)  # A324
    errors = validate_outdoor_entry(entry)
    if errors:
        raise ValueError(f"Invalid outdoor session entry: {'; '.join(errors)}")

    canonicalize_route_names(entry, _history_for_names(user_id))
    return storage.append_outdoor_log_line(user_id, entry)


# ---------------------------------------------------------------------------
# B401: edit / delete one crag of a day, never the others
# ---------------------------------------------------------------------------
#
# Since B341 a day holds one row per crag (key: date, spot_name). Edit and
# delete used to work on the whole date — editing Snake Valley on a Symplegades
# + Snake Valley day deleted Symplegades. Both now act on (date, crag) only,
# and the crag is always named by the request, never guessed (B401 review).

class OutdoorLogNotFound(ValueError):
    """No logged crag matches the (date[, crag]) asked for → HTTP 404."""


class OutdoorLogConflict(ValueError):
    """The request names no crag logged that day, or would land on another
    crag of the same day → HTTP 409. Nothing is written."""


def outdoor_sessions_on(user_id: Optional[str], date: str) -> List[Dict[str, Any]]:
    """Every crag logged on ``date`` (one entry per crag, in log order)."""
    return [s for s in load_outdoor_sessions(user_id, since_date=date) if s.get("date") == date]


def _spot_names(rows: List[Dict[str, Any]]) -> str:
    return ", ".join(repr(r.get("spot_name", "")) for r in rows)


def find_outdoor_session_to_replace(
    user_id: Optional[str],
    date: str,
    new_spot_name: str,
    original_spot_name: Optional[str] = None,
) -> Dict[str, Any]:
    """The logged entry an edit of ``date`` replaces (B401).

    The edited crag is the one the request names: ``original_spot_name`` when
    the edit renames it, otherwise ``new_spot_name`` — on a single-crag day too.

    * nothing logged that date, or ``original_spot_name`` not logged that date
      → :class:`OutdoorLogNotFound`;
    * no ``original_spot_name`` and ``new_spot_name`` not logged that date →
      :class:`OutdoorLogConflict`. A different name without
      ``original_spot_name`` is never read as a rename of the day's only crag:
      it is just as likely a second crag typed into the edit form (Today/Week
      «Log outdoor» and /outdoor «Quick log» open the day's crag in edit mode)
      or a date moved onto a day that holds another crag — replacing the only
      crag there would delete it, routes and all (B401 review);
    * a rename onto another crag already logged that day →
      :class:`OutdoorLogConflict`: its key would overwrite that crag's row.
    """
    rows = outdoor_sessions_on(user_id, date)
    if not rows:
        raise OutdoorLogNotFound(f"No outdoor session found for date {date}")

    edited = original_spot_name or new_spot_name
    target = next((r for r in rows if r.get("spot_name", "") == edited), None)
    if target is None:
        if original_spot_name:
            raise OutdoorLogNotFound(
                f"No outdoor session found for date {date} at {original_spot_name!r}"
            )
        raise OutdoorLogConflict(
            f"Nothing saved: {new_spot_name!r} is not logged on {date} "
            f"(logged: {_spot_names(rows)}). An edit replaces only the crag it names: "
            "to rename a crag send original_spot_name, to add another crag log a new session"
        )

    if new_spot_name != edited and any(r.get("spot_name", "") == new_spot_name for r in rows):
        raise OutdoorLogConflict(
            f"{new_spot_name!r} is already logged on {date} as another session: "
            "renaming onto it would overwrite it"
        )
    return target


def remove_outdoor_session(
    user_id: Optional[str], date: str, spot_name: Optional[str] = None
) -> int:
    """Remove the outdoor session of ``date`` — one crag of it when ``spot_name``
    is given (B401). Returns the number of entries removed.

    Without ``spot_name`` a single-crag day is removed as before; a multi-crag
    day raises :class:`OutdoorLogConflict` instead of deleting every crag.
    """
    if spot_name:
        return storage.remove_outdoor_log_by_date_spot(user_id, date, spot_name)
    rows = outdoor_sessions_on(user_id, date)
    if len(rows) > 1:
        raise OutdoorLogConflict(
            f"{len(rows)} crags are logged on {date} ({_spot_names(rows)}): "
            "send spot_name to say which one to delete"
        )
    if rows:
        # The crag just read, not the whole date: a crag finished between this
        # read and the delete (another device) must survive (B401 review).
        return storage.remove_outdoor_log_by_date_spot(user_id, date, rows[0].get("spot_name", ""))
    return storage.remove_outdoor_log_by_date(user_id, date)


def update_outdoor_session(
    user_id: Optional[str],
    date: str,
    new_entry: Dict[str, Any],
    original_spot_name: Optional[str] = None,
) -> str:
    """Replace one crag's outdoor session entry for a given date.

    The entry replaced is :func:`find_outdoor_session_to_replace`'s; only that
    row is rewritten (B401), the day's other crags stay byte-identical.
    The replacement is ONE storage write (``replace_outdoor_log_line``): a
    failure leaves the old entry in place, never the crag deleted with its
    replacement unwritten (B401 review — the delete-then-upsert pair could).
    Returns the JSONL log path.
    Raises ValueError (OutdoorLogNotFound / OutdoorLogConflict included) before
    writing anything if validation fails or no entry can be replaced.
    """
    if new_entry.get("date") != date:
        raise ValueError(
            f"Invalid outdoor session entry: date {new_entry.get('date')!r} is not {date}: "
            "an edit cannot move a session to another date"
        )
    target = find_outdoor_session_to_replace(
        user_id, date, str(new_entry.get("spot_name") or ""), original_spot_name
    )

    # Validate new entry before touching the file
    normalize_outdoor_entry(new_entry)  # A324
    errors = validate_outdoor_entry(new_entry)
    if errors:
        raise ValueError(f"Invalid outdoor session entry: {'; '.join(errors)}")

    canonicalize_route_names(new_entry, _history_for_names(user_id))

    # Rewrite the edited crag only, in a single write
    return storage.replace_outdoor_log_line(user_id, date, target.get("spot_name", ""), new_entry)


def load_outdoor_sessions(
    user_id: Optional[str] = None,
    since_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load outdoor sessions from JSONL logs, optionally filtered by date.

    Deduplicates by date (last entry wins). Sorted by date ascending.
    """
    return storage.read_outdoor_logs(user_id, since_date=since_date)


def compute_outdoor_stats(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregated statistics from outdoor sessions."""
    if not sessions:
        return {
            "total_sessions": 0,
            "total_routes": 0,
            "grade_histogram": {},
            "onsight_pct": 0.0,
            "flash_pct": 0.0,
            "sent_pct": 0.0,
            "top_grade_sent": None,
            "total_load": 0,
            "avg_load_per_session": 0.0,
        }

    total_routes = 0
    onsight_count = 0
    flash_count = 0
    sent_count = 0
    grade_counts: Dict[str, int] = {}
    grades_sent: List[str] = []

    # A292: chronological, so "first appearance" means the same thing here as
    # in grade_evidence (the shared predicate needs the routes seen so far).
    seen_routes: set = set()
    for session in chronological(sessions):
        for route in session.get("routes", []):
            route_id = route_key(session, route)
            first_go = is_first_go_send(route, route_id, seen_routes)
            seen_routes.add(route_id)
            total_routes += 1
            grade = route.get("grade", "unknown")
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

            # A324: a send is `sent` on lead — a clean second / top-rope is
            # not a send, nor an onsight (see outdoor_attempt).
            any_sent = route_lead_sent(route)

            if any_sent:
                sent_count += 1
                grades_sent.append(grade)

                # Onsight: first attempt is sent and style is onsight (or no style but first attempt sent)
                style = route.get("style")
                if style == "onsight":
                    onsight_count += 1
                elif style == "flash":
                    flash_count += 1
                elif style is None and first_go:
                    # Auto-detect: single sent attempt at the route's FIRST
                    # appearance = potential onsight. A292: the predicate is
                    # shared with grade_evidence; before, every repeat of a
                    # warm-up logged without a style counted as an onsight.
                    onsight_count += 1

    # A292: ranked on the grade ladder. max() on the strings was lexicographic
    # and put "7c" above "7c+". Font grades rank by their letters (7A ≡ 7a);
    # anything off the ladder ranks lowest, ties fall back to the string.
    top_grade = max(grades_sent, key=lambda g: (grade_rank(g), str(g))) if grades_sent else None

    total_load = sum(compute_outdoor_load_score(s) for s in sessions)
    avg_load = round(total_load / len(sessions), 1) if sessions else 0.0

    return {
        "total_sessions": len(sessions),
        "total_routes": total_routes,
        "grade_histogram": dict(sorted(grade_counts.items())),
        "onsight_pct": round(onsight_count / total_routes * 100, 1) if total_routes else 0.0,
        "flash_pct": round(flash_count / total_routes * 100, 1) if total_routes else 0.0,
        "sent_pct": round(sent_count / total_routes * 100, 1) if total_routes else 0.0,
        "top_grade_sent": top_grade,
        "total_load": total_load,
        "avg_load_per_session": avg_load,
    }
