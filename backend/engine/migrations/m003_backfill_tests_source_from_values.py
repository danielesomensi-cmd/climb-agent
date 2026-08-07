"""A271: a value present in ``assessment.tests`` was typed by a human.

A269 made axis provenance a real field; A271 makes a planning decision depend
on it. That raises the bar on ``assessment.tests_source``, and today it is not
met: only 7 of the 18 production profiles have a non-empty sidecar, and **four
of them have a real finger number on file with no provenance at all**
(``f49678eb``, ``d7f6083e``, ``79fadc50``, ``22080848``). They onboarded before
D214 introduced ``_build_tests_source``. Left alone, a provenance-gated rule
would penalise them for a bookkeeping gap rather than for missing data.

``m001`` cannot help: it infers provenance from the append-only history
(``tests.max_strength`` and friends), which only exists once a test has been
completed *inside the app*. Someone who typed their numbers into the wizard has
no history to infer from.

**The rule.** Nothing in the codebase writes a derived estimate into
``assessment.tests``. Verified writer by writer:

  * ``onboarding._build_user_state_from_onboarding`` — what the user typed, and
    since D214 it stamps ``tests_source`` itself.
  * ``progression_v1`` (~line 1290) — the test-completion path, which writes the
    value and ``_mark_measured`` together.
  * ``PUT /api/state`` deep-merge — the settings editor, i.e. a human typing.
    (A271 also stamps the sidecar at that boundary, so new edits no longer rely
    on this migration; it stays as the net for everything already written.)

Grade-derived estimates live in ``baselines`` (``estimate_missing_baselines``),
never here. So: a value in ``assessment.tests`` came from a person, and
``measured`` is the honest label for it.

Lazy on-read from ``deps.load_state``, ordered **m001 → m003 → m002**: m002
derives axis provenance from the sidecar, so it has to run last, on a complete
one. Idempotent. Never downgrades an existing entry.
"""
from typing import Any, Dict

# Keys that are genuine test scalars. Deliberately explicit rather than "every
# key in tests": an unknown future key should not be silently promoted to
# `measured` by a migration nobody revisited.
_TEST_KEYS = (
    "max_hang_20mm_7s_total_kg",
    "max_hang_20mm_5s_total_kg",
    "lp_max_lift_5s_left_kg",
    "lp_max_lift_5s_right_kg",
    "weighted_pullup_1rm_total_kg",
    "weighted_pullup_2rm_total_kg",
    "pullup_submaximal_reps",
    "pullup_submaximal_load_kg",
    "max_pullups_bw",
    "repeater_7_3_max_sets_20mm",
    "max_hang_duration_20mm_seconds",
    "l_sit_hold_seconds",
    "hip_flexibility_cm",
)


def migrate(state: Dict[str, Any]) -> bool:
    """Stamp `measured` for every test scalar that has a value. True if mutated."""
    if not isinstance(state, dict):
        return False

    assessment = state.get("assessment")
    if not isinstance(assessment, dict):
        return False

    tests = assessment.get("tests")
    if not isinstance(tests, dict) or not tests:
        return False

    source = assessment.get("tests_source")
    if not isinstance(source, dict):
        source = {}

    mutated = False
    for key in _TEST_KEYS:
        value = tests.get(key)
        if value is None or value == "":
            continue
        if source.get(key) == "measured":
            continue
        source[key] = "measured"
        mutated = True

    if mutated:
        assessment["tests_source"] = source
    return mutated
