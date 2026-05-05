"""Cross-discipline grade mapping (Fontainebleau ↔ French lead).

Engine always stores Fontainebleau for boulder grades and lowercase French
for lead grades. The conversion table here is calibrated to the same
benchmark used by ``assessment_v1`` so a discipline switch keeps the user
at a comparable level.

Source: Wikipedia "Grade (climbing)" + Mountain Project conversion (international
consensus). The forward direction (BOULDER_TO_LEAD) was previously inlined in
``backend/api/routers/onboarding.py`` as ``_BOULDER_TO_LEAD``; extracted here in
A-NEW-MACRO so ``PUT /api/state`` can apply the same mapping when the user
flips ``goal.discipline`` mid-cycle.

Ties policy for the inverse direction:

- ``BOULDER_TO_LEAD`` is many-to-one (e.g. both ``4C`` and ``5A`` map to ``6a+``).
- ``LEAD_TO_BOULDER`` picks the **highest** boulder grade per lead bucket so
  that ``lead → boulder → lead`` round-trips never downgrade the user.
"""

from __future__ import annotations

from typing import Dict


# Forward: Fontainebleau boulder → lowercase French lead.
BOULDER_TO_LEAD: Dict[str, str] = {
    "4A": "5c", "4B": "6a", "4C": "6a+",
    "5A": "6a+", "5A+": "6b", "5B": "6b", "5B+": "6b+", "5C": "6c", "5C+": "6c+",
    "6A": "6c+", "6A+": "7a", "6B": "7a", "6B+": "7a+", "6C": "7b", "6C+": "7b+",
    "7A": "7b+", "7A+": "7c", "7B": "7c+", "7B+": "8a",
    "7C": "8a", "7C+": "8a+",
    "8A": "8b", "8A+": "8b+", "8B": "8c", "8B+": "8c+",
    "8C": "9a", "8C+": "9a+",
}


# Inverse: French lead → Fontainebleau boulder (highest boulder per lead bucket).
# Derived from BOULDER_TO_LEAD on first import — verified by the round-trip test
# in test_grade_mapping.py.
def _build_lead_to_boulder() -> Dict[str, str]:
    """Pick the highest boulder grade for each lead bucket."""
    boulder_order = list(BOULDER_TO_LEAD.keys())
    pos = {b: i for i, b in enumerate(boulder_order)}
    inverse: Dict[str, str] = {}
    for boulder, lead in BOULDER_TO_LEAD.items():
        prev = inverse.get(lead)
        if prev is None or pos[boulder] > pos[prev]:
            inverse[lead] = boulder
    return inverse


LEAD_TO_BOULDER: Dict[str, str] = _build_lead_to_boulder()


def map_grade_for_discipline_change(
    current_grade: str,
    current_discipline: str,
    new_discipline: str,
) -> str:
    """Map a grade across disciplines when ``goal.discipline`` flips.

    Identity if the discipline does not actually change (or if either side is
    ``"both"`` / ``"all_round"`` — those keep the lead representation as the
    canonical form). For an unknown grade, returns the input unchanged so
    callers can decide whether to surface a validation error.

    Args:
        current_grade: The user's current target_grade (Font for boulder,
            lowercase French for lead).
        current_discipline: ``"lead"`` / ``"boulder"`` / ``"both"`` / ``"all_round"``.
        new_discipline: same value space.

    Returns:
        The grade re-expressed in the storage convention of *new_discipline*.
        ``lead → boulder``: lead grade looked up in ``LEAD_TO_BOULDER``.
        ``boulder → lead``: boulder grade looked up in ``BOULDER_TO_LEAD``.
        Same-discipline transitions and the lead-canonical disciplines
        (``both`` / ``all_round``) round-trip the input.
    """
    if not current_grade:
        return current_grade
    if current_discipline == new_discipline:
        return current_grade

    # "both" / "all_round" keep the lead representation as canonical.
    boulder_only = {"boulder"}
    lead_canonical = {"lead", "both", "all_round"}

    if current_discipline in lead_canonical and new_discipline in boulder_only:
        return LEAD_TO_BOULDER.get(current_grade, current_grade)
    if current_discipline in boulder_only and new_discipline in lead_canonical:
        return BOULDER_TO_LEAD.get(current_grade, current_grade)

    return current_grade
