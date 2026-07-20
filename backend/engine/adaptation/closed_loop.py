"""Per-cluster cooldown after a hard/failed exercise.

STATUS — read this before using anything here (A245 E-4, decision (c)):

`record_cluster_cooldown` writes `user_state.cooldowns.per_cluster`, which IS
read in production by `resolve_session._cooldown_until_date` and drives two real
behaviours (`cluster_cooldown_fallback`, `cluster_cooldown_downshift`). But
nothing calls this function yet — the feedback path never invokes it — so the
dictionary is always empty and neither behaviour has ever fired for a user.

That is a deliberate, tracked state, not an oversight: wiring it in is a change
to engine behaviour for every active user and interacts with `progression_v1`,
which already lowers loads on the same feedback (risk of double penalty). See
`A-CLOSED-LOOP-ACTIVATION` in the roadmap for the decision brief.

A245 E-4 also REMOVED the `adjustments.per_exercise` multiplier branch that used
to live here, along with `compute_next_multiplier` / `apply_multiplier`. It had
zero readers anywhere in production — the live per-exercise adaptation is
`progression_v1.apply_feedback` working on `working_loads`. Worse, the key it
wrote (`adjustments`) collides by name with the `adjustments[]` list that B287
returns from the replanner: two unrelated things, one word, so a reader grepping
for `adjustments` found live code and concluded this was wired in. It wasn't.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from backend.engine.cluster_utils import cluster_key_for_exercise, parse_date


#: Days of cooldown applied to an exercise's cluster, by reported difficulty.
COOLDOWN_DAYS_BY_DIFFICULTY = {
    "fail": 2,
    "too_hard": 2,
    "hard": 1,
}


def record_cluster_cooldown(
    user_state: Dict[str, Any],
    exercise_id: str,
    outcome: Dict[str, Any],
    *,
    exercises_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    feedback_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a cooldown for the exercise's cluster when the session went badly.

    Returns *user_state* (mutated in place). A no-op when the outcome carries no
    difficulty, when the difficulty is not a hard one, or when the caller did not
    supply the catalog needed to resolve the exercise's cluster.
    """
    difficulty = outcome.get("difficulty")
    if difficulty is None:
        difficulty = (outcome.get("actual") or {}).get("difficulty")
    if difficulty is None:
        return user_state

    cooldown_days = COOLDOWN_DAYS_BY_DIFFICULTY.get(difficulty, 0)
    if not cooldown_days or not exercises_by_id:
        return user_state

    date_value = feedback_date or outcome.get("date") or outcome.get("target_date")
    if date_value is None:
        date_value = (outcome.get("actual") or {}).get("date")
    base_date = parse_date(date_value)
    exercise = exercises_by_id.get(exercise_id)
    if not base_date or not exercise:
        return user_state

    until_date = base_date + timedelta(days=cooldown_days)
    cooldowns = user_state.setdefault("cooldowns", {})
    per_cluster = cooldowns.setdefault("per_cluster", {})
    per_cluster[cluster_key_for_exercise(exercise)] = {
        "until_date": until_date.isoformat(),
        "reason": f"difficulty:{difficulty}",
        "last_updated": base_date.isoformat(),
    }
    return user_state
