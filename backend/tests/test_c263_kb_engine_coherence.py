"""C263 — the coach KB must state the engine's real phase durations.

Why this test exists: the KB declared "Base ≥6 wk (D44, hard floor)" and even
"Engine cannot generate a macrocycle with Base <6 weeks", while
`macrocycle_v1.py` has always shipped 4 weeks for lead and 2 for boulder. D44
was proposed and then deferred (`docs/research_kb/00_INDEX_v3.md`), but the KB
promoted it to an enforced rule. The coach, which sees both the KB and the
user's real plan, tried to reconcile them in chat and told a paying user their
plan violated a rule of the method (D265 regression scoring, Q-01/Q-02).

The guard is on the *number*, not on the prose: if someone changes the engine
floor, this fails until the KB says the same thing.
"""

import re
from pathlib import Path

from backend.engine.macrocycle_v1 import (
    _PHASE_FLOORS_BOULDER,
    _PHASE_FLOORS_LEAD,
)

KB = Path(__file__).resolve().parents[1] / "coach" / "knowledge"
PERIODIZATION = KB / "L3" / "01_periodization.md"

# The canonical line in the KB that states Base duration for both disciplines.
CANONICAL_RE = re.compile(
    r"\*\*Base: (?P<lead>\d+) weeks \(lead\), (?P<boulder>\d+) weeks \(boulder\)\.\*\*"
)


def test_kb_states_the_engine_base_duration():
    match = CANONICAL_RE.search(PERIODIZATION.read_text(encoding="utf-8"))
    assert match, (
        "canonical Base-duration line missing or reworded in "
        "01_periodization.md — the KB↔engine guard cannot read it"
    )
    assert int(match.group("lead")) == _PHASE_FLOORS_LEAD["base"]
    assert int(match.group("boulder")) == _PHASE_FLOORS_BOULDER["base"]


def test_kb_states_the_lead_base_default_not_just_the_floor():
    # A284: the floor and the default parted ways (2 vs 4). The canonical line
    # above carries the floor, which on its own would let the coach tell a lead
    # athlete their base is 2 weeks — true only if they asked for it. The KB
    # must state both numbers, or it misinforms in the common case.
    from backend.engine.macrocycle_v1 import _BASE_DURATIONS_LEAD

    text = PERIODIZATION.read_text(encoding="utf-8")
    default = _BASE_DURATIONS_LEAD["base"]
    assert f"default is still {default}" in text, (
        f"01_periodization.md must state that the lead base default is "
        f"{default} weeks, not only the floor — otherwise the coach reports "
        f"the floor as if it were what every athlete gets"
    )


def test_no_kb_file_claims_a_six_week_base_floor():
    # The exact claims that made the coach contradict the user's own plan.
    forbidden = (
        "Base phase is ≥6 weeks",
        "Base ≥6 weeks (D44",
        "≥6 wk (D44, hard floor)",
        "Base <6 weeks regardless",
        "won't generate a macrocycle with Base <6 weeks",
    )
    offenders = []
    for path in sorted(KB.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        offenders += [
            f"{path.name}: {claim!r}" for claim in forbidden if claim in text
        ]
    assert not offenders, "stale 6-week Base floor claims in the KB: " + "; ".join(offenders)
