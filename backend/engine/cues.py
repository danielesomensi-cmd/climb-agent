"""Process cues — deterministic coaching cue selection per session (A141).

One cue per session, selected based on session type. Deterministic: same
user + date + session → same cue. No persisted state needed — the seed is
computed from (user_id, date_str) so different days naturally rotate cues.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

_CUES_PATH = os.path.join("backend", "catalog", "cues", "v1", "process_cues.json")


@lru_cache(maxsize=1)
def _load_cues(repo_root: str) -> list[dict]:
    path = Path(repo_root) / _CUES_PATH
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_session_cue(
    session_template_id: str,
    date_str: str,
    user_id: str,
    repo_root: str,
    *,
    next_day_is_rest: bool = False,
) -> Optional[dict]:
    """Return a deterministic cue for the given session + date + user.

    Args:
        session_template_id: The session template id (e.g. "finger_strength_home").
        date_str: ISO date string (YYYY-MM-DD).
        user_id: User identifier for seed uniqueness.
        repo_root: Repository root path.
        next_day_is_rest: If True, enables the "_any_last_session_before_rest" tag.

    Returns:
        Dict with "id" and "text", or None if no cues match.
    """
    all_cues = _load_cues(repo_root)
    if not all_cues:
        return None

    # Filter cues matching session type
    matching = []
    for cue in all_cues:
        types = cue.get("session_types", [])
        if session_template_id in types:
            matching.append(cue)
        elif "_any_last_session_before_rest" in types and next_day_is_rest:
            matching.append(cue)

    if not matching:
        return None

    # Deterministic selection via hash
    seed_str = f"{user_id}:{date_str}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    idx = seed % len(matching)
    cue = matching[idx]

    return {"id": cue["id"], "text": cue["text"]}
