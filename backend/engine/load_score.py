"""Session load score — single source of truth (B4 / D151 / B312).

Two distinct numbers live here, and keeping them apart is the whole point:

- **prescribed** (`session_load_score`): what the resolved session asks for.
  `round(min(85, Σ fatigue_cost × 1.5))` over every resolved exercise instance.
  Written at resolve time and on user add/remove of an exercise. Frozen once the
  session starts — it is the denominator of `load_ratio`.
- **actual** (`session_load_actual`): what the user really did, derived at
  feedback time from the per-exercise `completed` flags the guided player already
  sends (`exercise_feedback_v1`). Before B312 nothing consumed those flags for
  load: skipping six exercises out of eight and marking the session done still
  credited the full prescribed load to the weekly report and the heatmap.

The formula lived inline in three places (resolve_session, session router ×2)
and drifted from the two report consumers, which read `session_load_score` off
the *session slot* — where it never exists, since `resolve_session` writes it on
the resolved payload that the week router attaches under `slot["resolved"]`. So
the reports had been silently falling back to `estimated_load_score` (the coarse
intensity bucket) for every session. `effective_session_load()` is the one
reader every consumer must go through.
"""

from typing import Any, Dict, Iterable, List, Optional

# D151: raw fatigue_cost sums are rescaled and capped so a session load score is
# comparable to compute_outdoor_load_score().
LOAD_SCALE = 1.5
LOAD_CAP = 85


def load_score_from_ids(
    exercise_ids: Iterable[Optional[str]],
    fatigue_map: Dict[str, float],
) -> int:
    """Prescribed load for a list of exercise ids (duplicates count twice)."""
    raw = sum(fatigue_map.get(ex_id, 0) for ex_id in exercise_ids)
    return round(min(LOAD_CAP, raw * LOAD_SCALE))


def fatigue_map_from_catalog(exercises: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """Build {exercise_id: fatigue_cost} from a catalog list (each dict has "id")."""
    return {e.get("id"): e.get("fatigue_cost", 0) for e in exercises}


def fatigue_map_by_id(exercises_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """Build {exercise_id: fatigue_cost} from a catalog already keyed by id."""
    return {
        ex_id: (ex or {}).get("fatigue_cost", 0)
        for ex_id, ex in exercises_by_id.items()
    }


def compute_actual_load_score(
    actual_items: Optional[List[Dict[str, Any]]],
    exercise_instances: Optional[List[Dict[str, Any]]],
    fatigue_map: Dict[str, float],
) -> Optional[int]:
    """Load the user actually earned, or None when there is no signal to use.

    Returns None (→ callers keep the prescribed value) when:
      - there are no feedback items, or no resolved exercise instances;
      - no item carries a `completed` key. Older payloads and the post-session
        dialog on /today and /week report every exercise as completed anyway, so
        a missing flag must never be read as "skipped".

    The denominator is `exercise_instances`, not the feedback items, so that a
    fully completed session lands exactly on its prescribed score. Two cases
    depend on that choice:
      - instruction-only steps never appear in the feedback payload (the guided
        player skips them) but do carry fatigue_cost in the catalog;
      - an exercise the client simply forgot to report gets counted as done,
        which is the conservative reading — we only ever subtract load on an
        explicit `completed: false`.

    Unilateral exercises arrive as two items (right/left) sharing one
    exercise_id; the id counts as done if *either* hand was done, and its
    fatigue_cost is counted once per resolved instance either way.
    """
    if not actual_items or not exercise_instances:
        return None

    reported: Dict[str, bool] = {}
    saw_flag = False
    for item in actual_items:
        ex_id = str(item.get("exercise_id") or "").strip()
        if not ex_id:
            continue
        if "completed" not in item:
            continue
        saw_flag = True
        done = bool(item.get("completed"))
        # OR across hands / repeated entries for the same exercise.
        reported[ex_id] = reported.get(ex_id, False) or done

    if not saw_flag:
        return None

    counted_ids: List[Optional[str]] = []
    for inst in exercise_instances:
        ex_id = str(inst.get("exercise_id") or "").strip()
        if not ex_id:
            continue
        # Unreported → assumed done (see docstring).
        if reported.get(ex_id, True):
            counted_ids.append(ex_id)

    return load_score_from_ids(counted_ids, fatigue_map)


def effective_session_load(session: Optional[Dict[str, Any]]) -> float:
    """The load a session contributed — the only reader reports should use.

    Cascade, most to least specific:
      1. `session_load_actual` (B312: what was really done)
      2. `session_load_score`  (B4/D151: prescribed, from fatigue_cost)
      3. `estimated_load_score` (planner's intensity bucket)

    Each key is looked up on the session slot first and then on the resolved
    payload, because the prescribed score is written on the resolved payload
    while the actual one is written on the slot next to `actual_exercises`.

    Zero counts as an answer for `session_load_actual` only: a user who skipped
    every exercise earned 0, and falling back to the prescribed value there would
    defeat the whole mechanism. A *prescribed* zero means the resolver produced no
    exercise instances at all (failed resolution), which is not the same claim as
    "no load" — D151 deliberately falls through to the intensity bucket there, and
    that behaviour is preserved.
    """
    if not session:
        return 0.0
    resolved = session.get("resolved") or {}
    if not isinstance(resolved, dict):
        resolved = {}
    for key, zero_is_meaningful in (
        ("session_load_actual", True),
        ("session_load_score", False),
        ("estimated_load_score", False),
    ):
        for holder in (session, resolved):
            value = holder.get(key)
            if isinstance(value, (int, float)) and (zero_is_meaningful or value):
                return float(value)
    return 0.0
