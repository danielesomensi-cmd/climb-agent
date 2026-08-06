"""A269: backfill assessment.profile_source / profile_scoring_version.

A269 records, per axis, whether a score came from a measured test
(`measured`), from a mix of measured and derived inputs (`partial`), or from
nothing measured at all (`estimated`). Existing users have a stored `profile`
and no provenance beside it.

The recompute path in `deps._recompute_profile_if_needed` would eventually fill
it, but only for users whose assessment inputs change — a user who onboarded in
March and has not edited anything since would keep a profile with no record of
where it came from, indefinitely. That is precisely the population the field
exists for.

Lazy on-read: invoked from `deps.load_state`, **after** m001. The order is not
cosmetic: provenance is derived from `assessment.tests_source`, which m001 is
what populates for pre-D214 users. Running this first would read an empty
sidecar and mark a genuinely measured axis `estimated`.

Idempotent. Never downgrades an existing entry: the recompute path is the
authority once it has run, this only fills a gap.

Out of scope (intentional): users with no `assessment.profile` at all. There is
nothing to describe the provenance of, and writing a source for an absent
profile would be the same class of fabrication the field was added to prevent.
"""
from typing import Any, Dict

from backend.engine.assessment_v1 import (
    PROFILE_SCORING_VERSION,
    compute_profile_source,
)


def migrate(state: Dict[str, Any]) -> bool:
    """Fill profile_source / profile_scoring_version. Returns True if mutated."""
    if not isinstance(state, dict):
        return False

    assessment = state.get("assessment")
    if not isinstance(assessment, dict):
        return False

    profile = assessment.get("profile")
    if not isinstance(profile, dict) or not profile:
        return False

    mutated = False

    existing = assessment.get("profile_source")
    if not isinstance(existing, dict) or not existing:
        assessment["profile_source"] = compute_profile_source(assessment)
        mutated = True

    if not assessment.get("profile_scoring_version"):
        # Everything stored before A270 was produced by the v1 rules. Stamping
        # it is what makes "which rules produced this radar" answerable later,
        # and what keeps a future version from being applied retroactively.
        assessment["profile_scoring_version"] = PROFILE_SCORING_VERSION
        mutated = True

    return mutated
