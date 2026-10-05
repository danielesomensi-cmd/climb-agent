"""C272 — catalog entries that exist for Claude Code and the custom builder only.

Two exercise roles mark a catalog entry the engine must never pick on its own:

- ``ladder`` — a level of a bodyweight ladder
  (``backend/catalog/progressions/v1/bw_ladders.json``). The ladder engine
  (a later A brief) will reach them only by swapping within a family.
- ``library`` — technique / positioning / try-hard / pocket drills and
  protocols: composed by hand (Claude Code ``/custom-session``, the custom
  session builder), never by a template.

``resolve_session`` already ignores them: every template block filters on a
role and no block asks for these two (pinned by test_catalog_validation and the
C272 golden). C274: the one way in is an explicit ``exercise_id`` pin written
in a catalog session (the foot-strength block of ``legs_maintenance_lunch``) —
composition by hand, in the catalog; no filter or pool ever picks them. The other deterministic consumers build pools by domain or
category instead, so they call :func:`is_library_only` explicitly — the
body-part picker, the ad-hoc builder and the coach composer's pool.
"""

from __future__ import annotations

from typing import Any, Mapping

#: Roles that keep an exercise out of every engine-built pool.
LIBRARY_ONLY_ROLES = frozenset({"ladder", "library"})


def is_library_only(ex: Mapping[str, Any]) -> bool:
    """True when the exercise carries a library-only role."""
    roles = ex.get("role") or []
    if isinstance(roles, str):
        roles = [roles]
    return any(str(r) in LIBRARY_ONLY_ROLES for r in roles)
