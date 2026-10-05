"""A296 (R6c) — the limit log: what was climbed in a limit session, problem by problem.

Why this exists: a limit session used to leave one trace, a single
``used_grade`` plus a label. That cannot tell "two 7B sends" from "an hour on
one 7B without topping it", and the target either went up or down on a single
label. The limit log records each problem (grade, attempts, outcome) so that:

- the limit target moves on what was actually climbed (``classify_session``);
- one bad session never lowers it — it takes two in a row
  (``entry_made_progress`` on the previous entry);
- a limit done in a custom session, or in a free boulder session, counts as the
  week's limit stimulus (A294 reads it through ``stimulus.exposures`` and
  ``key_sessions_v1.session_dose``).

What it is (``user_state.limit_log``, top level, append-only, capped):

    {date, session_id, exercise_id, surface, target_grade, problems[],
     source: planned|custom|adhoc|free, + summary fields}

Written ONLY by ``progression_v1.apply_feedback`` (planned / custom / adhoc)
and by the free-session finish (``source: free``). It is NOT in the PUT
/api/state allowlist. A resubmitted (date, session_id, exercise_id) replaces
its entry (B197 idempotency).

Free sessions stay off-plan (A240/A213): their entry never moves the target
and never writes stimulus_recency — it only counts for "limit stimulus done"
and for the finger-hard-day view.

Everything here is pure and deterministic except the two writers
(``upsert_entry``, ``remove_free_entry``), which mutate the state passed in.

All thresholds below are ENGINEERING CONSTANTS (design choices of the
2026-10-04 programme, no published source), listed in vocabulary §2.10.3.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from backend.engine.free_session import FONT_GRADES as _FONT_GRADES

# ---------------------------------------------------------------------------
# Constants (ENGINEERING CONSTANTS)
# ---------------------------------------------------------------------------

#: Entries kept in ``user_state.limit_log`` (oldest dropped first).
LIMIT_LOG_CAP = 200
#: Problem rows accepted per exercise item (extra rows are dropped).
MAX_PROBLEMS = 8
#: Attempts accepted per problem. Honest data is never refused: 1-10 covers a
#: full limit session on one problem (the catalog guidance stays 3-4).
MAX_ATTEMPTS = 10
#: Above this many hard attempts (problems at ≥ target − 1 half grade) in one
#: session the target never goes up and the summary carries a warning: a lot
#: of hard pulling on small holds is a finger-safety signal, not a performance.
HARD_ATTEMPTS_GUARD = 20
#: A limit session in a custom / adhoc / free session counts as the week's
#: limit stimulus with at least this many problems at or above the target
#: (sent or high point).
QUALIFYING_PROBLEMS = 2

OUTCOME_SENT = "sent"
OUTCOME_HIGH_POINT = "high_point"
OUTCOME_NO_PROGRESS = "no_progress"
OUTCOMES: Tuple[str, ...] = (OUTCOME_SENT, OUTCOME_HIGH_POINT, OUTCOME_NO_PROGRESS)

SOURCE_PLANNED = "planned"
SOURCE_CUSTOM = "custom"
SOURCE_ADHOC = "adhoc"
SOURCE_FREE = "free"
SOURCES: Tuple[str, ...] = (SOURCE_PLANNED, SOURCE_CUSTOM, SOURCE_ADHOC, SOURCE_FREE)

#: Free-session surfaces that are boulder surfaces (the limit family is Font).
FREE_LIMIT_SURFACES = frozenset({"gym_boulder", "board_kilter", "board_moonboard", "board_other"})

_INDEX = {g: i for i, g in enumerate(_FONT_GRADES)}
_NAME_MAX = 80


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------

def norm_grade(grade: Any) -> Optional[str]:
    """Uppercase Font grade, or None when it is not a Font grade."""
    if grade is None:
        return None
    g = str(grade).strip().upper().replace(" ", "")
    return g if g in _INDEX else None


def grade_index(grade: Any) -> Optional[int]:
    g = norm_grade(grade)
    return _INDEX[g] if g is not None else None


def step_half(grade: Any, half_steps: int) -> Optional[str]:
    """Step a Font grade by half grades, clamped to the scale."""
    idx = grade_index(grade)
    if idx is None:
        return None
    return _FONT_GRADES[max(0, min(len(_FONT_GRADES) - 1, idx + int(half_steps)))]


def _at_or_above(grade: Any, reference: Any, offset: int = 0) -> bool:
    gi, ri = grade_index(grade), grade_index(reference)
    return gi is not None and ri is not None and gi >= ri + offset


# ---------------------------------------------------------------------------
# Sanitising
# ---------------------------------------------------------------------------

def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != int(f):
        return None
    return int(f)


def sanitize_problems(raw: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Clean a ``problems`` list; invalid rows are dropped ONE BY ONE.

    Row: ``{grade (Font), attempts 1-10, outcome sent|high_point|no_progress,
    surface?, sent_on_attempt?, crux_moves?, name?}``. Returns
    ``(clean_rows, warnings)``. At most ``MAX_PROBLEMS`` rows are kept.
    """
    warnings: List[str] = []
    if raw is None:
        return [], warnings
    if not isinstance(raw, list):
        return [], ["problems dropped (not a list)"]
    clean: List[Dict[str, Any]] = []
    for i, row in enumerate(raw):
        if len(clean) >= MAX_PROBLEMS:
            warnings.append(f"problems[{i}:] dropped (max {MAX_PROBLEMS} rows)")
            break
        if not isinstance(row, Mapping):
            warnings.append(f"problems[{i}] dropped (not an object)")
            continue
        grade = norm_grade(row.get("grade"))
        if grade is None:
            warnings.append(f"problems[{i}] dropped (grade {row.get('grade')!r} is not a Font grade)")
            continue
        attempts = _int(row.get("attempts"))
        if attempts is None or not (1 <= attempts <= MAX_ATTEMPTS):
            warnings.append(f"problems[{i}] dropped (attempts must be 1..{MAX_ATTEMPTS})")
            continue
        outcome = row.get("outcome")
        if outcome not in OUTCOMES:
            warnings.append(f"problems[{i}] dropped (outcome {outcome!r})")
            continue
        out: Dict[str, Any] = {"grade": grade, "attempts": attempts, "outcome": outcome}
        sent_on = _int(row.get("sent_on_attempt"))
        if outcome == OUTCOME_SENT and sent_on is not None and 1 <= sent_on <= attempts:
            out["sent_on_attempt"] = sent_on
        crux = _int(row.get("crux_moves"))
        if crux is not None and 0 <= crux <= 50:
            out["crux_moves"] = crux
        surface = row.get("surface")
        if isinstance(surface, str) and surface.strip():
            out["surface"] = surface.strip().lower()[:40]
        name = row.get("name")
        if isinstance(name, str) and name.strip():
            out["name"] = name.strip()[:_NAME_MAX]
        clean.append(out)
    return clean, warnings


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def hard_attempts(problems: Iterable[Mapping[str, Any]], reference: Any) -> int:
    """Attempts on problems at ≥ reference − 1 half grade."""
    return sum(int(p.get("attempts") or 0) for p in problems if _at_or_above(p.get("grade"), reference, -1))


def best_sent(problems: Iterable[Mapping[str, Any]]) -> Optional[str]:
    best: Optional[int] = None
    for p in problems:
        if p.get("outcome") != OUTCOME_SENT:
            continue
        idx = grade_index(p.get("grade"))
        if idx is not None and (best is None or idx > best):
            best = idx
    return _FONT_GRADES[best] if best is not None else None


def problems_made_progress(problems: Iterable[Mapping[str, Any]], reference: Any) -> bool:
    """A session "made progress" at ``reference`` when it has a send at ≥ R − 1
    half grade, a high point at ≥ R, or crux moves done on a problem at ≥ R.

    Its negation is the "no progress" of the two-sessions-in-a-row down rule.
    """
    for p in problems:
        outcome = p.get("outcome")
        g = p.get("grade")
        if outcome == OUTCOME_SENT and _at_or_above(g, reference, -1):
            return True
        if outcome == OUTCOME_HIGH_POINT and _at_or_above(g, reference):
            return True
        if int(p.get("crux_moves") or 0) > 0 and _at_or_above(g, reference):
            return True
    return False


def qualifying_count(problems: Iterable[Mapping[str, Any]], target: Any) -> int:
    """Problems at ≥ target that were sent or reached a high point."""
    return sum(
        1 for p in problems
        if p.get("outcome") in (OUTCOME_SENT, OUTCOME_HIGH_POINT) and _at_or_above(p.get("grade"), target)
    )


def qualifies(problems: Iterable[Mapping[str, Any]], target: Any) -> bool:
    """Whether a logged session counts as the week's limit stimulus."""
    return qualifying_count(list(problems), target) >= QUALIFYING_PROBLEMS


def entry_made_progress(entry: Optional[Mapping[str, Any]]) -> bool:
    """Was the logged session ``entry`` a session with progress?

    With problems: ``problems_made_progress`` at its own target. Without
    problems (a label-only session): hard/very_hard is no progress, anything
    else (including not rated) is read as progress — never lower a target on
    a missing signal. No entry at all → progress.
    """
    if not entry:
        return True
    problems = entry.get("problems") or []
    if problems:
        return problems_made_progress(problems, entry.get("target_grade"))
    return str(entry.get("feedback_label") or "") not in ("hard", "very_hard")


def classify_session(
    problems: List[Mapping[str, Any]],
    reference: str,
    previous: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """The target step a logged limit session earns, at ``reference`` (R).

    - up +1 half grade: ≥ 1 send at ≥ R + 1 half, or ≥ 2 sends at ≥ R;
    - hold: 1 send at ≥ R, a high point at ≥ R, crux moves at ≥ R — or any
      session with progress (``problems_made_progress``);
    - down −1 half grade ONLY when this session AND the previous one (read
      from the limit log) made no progress — one bad session never lowers it;
    - never more than one half grade per session;
    - more than ``HARD_ATTEMPTS_GUARD`` hard attempts → never up, warning.

    Returns ``{delta, reason, hard_attempts, guard, best_sent}``.
    """
    sends_at = sum(1 for p in problems if p.get("outcome") == OUTCOME_SENT and _at_or_above(p.get("grade"), reference))
    sends_above = sum(1 for p in problems if p.get("outcome") == OUTCOME_SENT and _at_or_above(p.get("grade"), reference, 1))
    progress = problems_made_progress(problems, reference)
    if sends_above >= 1 or sends_at >= 2:
        delta, reason = 1, "sent_above_target" if sends_above >= 1 else "two_sends_at_target"
    elif progress:
        delta, reason = 0, "progress_at_target"
    elif not entry_made_progress(previous):
        delta, reason = -1, "two_sessions_without_progress"
    else:
        delta, reason = 0, "first_session_without_progress"
    n_hard = hard_attempts(problems, reference)
    guard = n_hard > HARD_ATTEMPTS_GUARD
    if guard and delta > 0:
        delta, reason = 0, "hard_attempts_guard"
    return {
        "delta": delta,
        "reason": reason,
        "hard_attempts": n_hard,
        "guard": guard,
        "best_sent": best_sent(problems),
    }


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def entries(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Valid limit-log entries, oldest first (read-only)."""
    out = [e for e in (state.get("limit_log") or []) if isinstance(e, dict) and e.get("date")]
    return sorted(out, key=lambda e: (str(e.get("date")), str(e.get("session_id") or ""), str(e.get("exercise_id") or "")))


def previous_entry(
    state: Mapping[str, Any], surface: str, before_date: str, *, exclude_free: bool = True
) -> Optional[Dict[str, Any]]:
    """Newest entry on ``surface`` strictly before ``before_date``.

    Free entries are excluded by default: off-plan climbing never drives the
    target (A240/A213).
    """
    best: Optional[Dict[str, Any]] = None
    for e in entries(state):
        if str(e.get("surface") or "") != surface or str(e.get("date")) >= before_date:
            continue
        if exclude_free and e.get("source") == SOURCE_FREE:
            continue
        best = e
    return best


def find_entry(
    state: Mapping[str, Any], date: str, session_id: Optional[str], exercise_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    for e in state.get("limit_log") or []:
        if (
            isinstance(e, dict)
            and str(e.get("date")) == str(date)
            and (e.get("session_id") or None) == (session_id or None)
            and (e.get("exercise_id") or None) == (exercise_id or None)
        ):
            return e
    return None


def entries_for_session(state: Mapping[str, Any], date: str, session_id: Optional[str]) -> List[Dict[str, Any]]:
    return [
        e for e in entries(state)
        if str(e.get("date")) == str(date) and (e.get("session_id") or None) == (session_id or None)
    ]


def recent(state: Mapping[str, Any], n: int = 4) -> List[Dict[str, Any]]:
    """The ``n`` newest entries, newest first (for context consumers, A297)."""
    return list(reversed(entries(state)))[: max(0, int(n))]


def source_for_session(session_id: Any) -> str:
    sid = str(session_id or "")
    if sid.startswith("custom_"):
        return SOURCE_CUSTOM
    if sid.startswith("generated_"):
        return SOURCE_ADHOC
    return SOURCE_PLANNED


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def upsert_entry(state: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append ``entry`` (or replace the same (date, session_id, exercise_id)).

    Keeps the newest ``LIMIT_LOG_CAP`` entries by date. Mutates ``state``.
    """
    log = state.get("limit_log")
    if not isinstance(log, list):
        log = []
    key = (str(entry.get("date")), entry.get("session_id") or None, entry.get("exercise_id") or None)
    log = [
        e for e in log
        if not (
            isinstance(e, dict)
            and (str(e.get("date")), e.get("session_id") or None, e.get("exercise_id") or None) == key
        )
    ]
    log.append(entry)
    log.sort(key=lambda e: (str(e.get("date")), str(e.get("session_id") or ""), str(e.get("exercise_id") or "")))
    if len(log) > LIMIT_LOG_CAP:
        log = log[-LIMIT_LOG_CAP:]
    state["limit_log"] = log
    return entry


def remove_free_entry(state: Dict[str, Any], free_session_id: str) -> bool:
    """Drop the entry a free session wrote (the session was deleted)."""
    log = state.get("limit_log")
    if not isinstance(log, list):
        return False
    kept = [
        e for e in log
        if not (isinstance(e, dict) and e.get("source") == SOURCE_FREE and e.get("session_id") == free_session_id)
    ]
    changed = len(kept) != len(log)
    if changed:
        state["limit_log"] = kept
    return changed


# ---------------------------------------------------------------------------
# Free sessions
# ---------------------------------------------------------------------------

def free_climbs_as_problems(climbs: Iterable[Mapping[str, Any]], surface: str) -> List[Dict[str, Any]]:
    """Map free-session climbs to limit-log problem rows.

    flash/sent → sent; attempted → high_point (the free logger has no
    high-point field: a problem worked without topping it is read as limit
    work at that grade). Attempts are clamped to 1..MAX_ATTEMPTS.
    """
    out: List[Dict[str, Any]] = []
    for c in climbs:
        if not isinstance(c, Mapping):
            continue
        grade = norm_grade(c.get("grade"))
        if grade is None:
            continue
        status = c.get("status")
        attempts = _int(c.get("attempts")) or 1
        attempts = max(1, min(MAX_ATTEMPTS, attempts))
        row: Dict[str, Any] = {"grade": grade, "attempts": attempts, "surface": surface}
        if status in ("flash", "sent"):
            row["outcome"] = OUTCOME_SENT
            row["sent_on_attempt"] = attempts
        else:
            row["outcome"] = OUTCOME_HIGH_POINT
        out.append(row)
    return out


def free_session_decision(
    climbs: Iterable[Mapping[str, Any]],
    surface: str,
    target: Optional[str],
    *,
    toggled: bool,
) -> Dict[str, Any]:
    """Does a finished free boulder session count as a limit session?

    Yes with at least ``QUALIFYING_PROBLEMS`` climbs at ≥ the limit target of
    that surface (sent or worked), or when the athlete toggled "it was a limit
    session". Returns ``{counted, reason, target_grade, qualifying, problems}``.
    """
    problems = free_climbs_as_problems(climbs, surface)
    n = qualifying_count(problems, target) if target else 0
    if n >= QUALIFYING_PROBLEMS:
        counted, reason = True, "threshold"
    elif toggled:
        counted, reason = True, "toggle"
    else:
        counted, reason = False, "below_threshold" if target else "no_target"
    return {
        "counted": counted,
        "reason": reason,
        "target_grade": target,
        "qualifying": n,
        "problems": problems[:MAX_PROBLEMS * 4],
    }


# ---------------------------------------------------------------------------
# Weekly report (A299, R6c frontend §7)
# ---------------------------------------------------------------------------

#: Display order of the boulder surfaces in the report (boards first, as in
#: progression_v1.SURFACE_PRIORITY, then the wall). Unknown surfaces go last.
REPORT_SURFACE_ORDER: Tuple[str, ...] = (
    "board_kilter", "board_moonboard", "board_other", "spraywall", "gym_boulder",
)


def sends_by_surface(
    state: Mapping[str, Any],
    free_sessions: Iterable[Mapping[str, Any]],
    since: str,
    until: str,
) -> List[Dict[str, Any]]:
    """A299: the hardest boulder SENT per surface between ``since`` and ``until``.

    Read-only. Two sources, never counted twice:

    - the limit log, planned / custom / adhoc entries: every problem with
      outcome ``sent`` (the problem's own surface, else the entry's);
    - finished free sessions on a boulder surface: every climb ``flash`` /
      ``sent``. The ``free`` entries of the limit log are NOT read — they are
      a copy of these same climbs.

    Rows ``{surface, max_grade_sent, sends, sources, target_grade}`` in
    ``REPORT_SURFACE_ORDER``. ``target_grade`` is the limit target of the last
    logged (non-free) session of the week on that surface, None otherwise.
    A surface with no send in the window has no row.
    """
    rows: Dict[str, Dict[str, Any]] = {}
    targets: Dict[str, str] = {}

    def _row(surface: str) -> Dict[str, Any]:
        return rows.setdefault(surface, {
            "surface": surface, "max_grade_sent": None, "sends": 0,
            "sources": [], "target_grade": None,
        })

    def _add(surface: str, grade: str, source: str) -> None:
        row = _row(surface)
        row["sends"] += 1
        if row["max_grade_sent"] is None or _INDEX[grade] > _INDEX[row["max_grade_sent"]]:
            row["max_grade_sent"] = grade
        if source not in row["sources"]:
            row["sources"].append(source)

    for e in entries(state):
        if not (since <= str(e.get("date")) <= until) or e.get("source") == SOURCE_FREE:
            continue
        entry_surface = str(e.get("surface") or "").strip().lower()
        for p in e.get("problems") or []:
            if not isinstance(p, Mapping) or p.get("outcome") != OUTCOME_SENT:
                continue
            grade = norm_grade(p.get("grade"))
            surface = str(p.get("surface") or entry_surface).strip().lower()
            if grade is None or not surface:
                continue
            _add(surface, grade, str(e.get("source") or SOURCE_PLANNED))
        target = norm_grade(e.get("target_grade"))
        if target and entry_surface:
            targets[entry_surface] = target  # entries are oldest first: the last wins

    for fs in free_sessions:
        if not isinstance(fs, Mapping) or not fs.get("finished_at"):
            continue
        if not (since <= str(fs.get("date") or "") <= until):
            continue
        surface = str(fs.get("surface") or "").strip().lower()
        if surface not in FREE_LIMIT_SURFACES:
            continue
        for c in fs.get("climbs") or []:
            if not isinstance(c, Mapping) or c.get("status") not in ("flash", "sent"):
                continue
            grade = norm_grade(c.get("grade"))
            if grade is not None:
                _add(surface, grade, SOURCE_FREE)

    order = {s: i for i, s in enumerate(REPORT_SURFACE_ORDER)}
    out = [r for r in rows.values() if r["max_grade_sent"] is not None]
    out.sort(key=lambda r: (order.get(r["surface"], len(order)), r["surface"]))
    for r in out:
        r["sources"] = sorted(r["sources"])
        r["target_grade"] = targets.get(r["surface"])
    return out


__all__ = [
    "REPORT_SURFACE_ORDER", "sends_by_surface",
    "LIMIT_LOG_CAP", "MAX_PROBLEMS", "MAX_ATTEMPTS", "HARD_ATTEMPTS_GUARD", "QUALIFYING_PROBLEMS",
    "OUTCOMES", "SOURCES", "FREE_LIMIT_SURFACES",
    "norm_grade", "grade_index", "step_half", "sanitize_problems",
    "hard_attempts", "best_sent", "problems_made_progress", "qualifying_count", "qualifies",
    "entry_made_progress", "classify_session",
    "entries", "previous_entry", "find_entry", "entries_for_session", "recent", "source_for_session",
    "upsert_entry", "remove_free_entry", "free_climbs_as_problems", "free_session_decision",
]
