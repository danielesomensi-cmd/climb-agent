"""Adaptation engines for closed-loop adjustments.

A245 E-4: `compute_next_multiplier`, `apply_multiplier` and
`update_user_state_adjustments` were removed — see closed_loop.py for why.
"""

from backend.engine.adaptation.closed_loop import (  # noqa: F401
    COOLDOWN_DAYS_BY_DIFFICULTY,
    record_cluster_cooldown,
)
