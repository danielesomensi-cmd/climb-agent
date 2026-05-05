"""Tests for backend.engine.grade_mapping (A-NEW-MACRO).

Pins both the forward Boulder→Lead table (extracted from onboarding.py) and the
derived Lead→Boulder inverse against an explicit, hand-verified reference.
"""

from __future__ import annotations

import pytest

from backend.engine.grade_mapping import (
    BOULDER_TO_LEAD,
    LEAD_TO_BOULDER,
    map_grade_for_discipline_change,
)


# ── Canonical reference ────────────────────────────────────────────────────

# Hand-verified inverse: highest boulder per lead bucket.
# Derived by sorting BOULDER_TO_LEAD by boulder order, then picking the last
# boulder grade for each lead. Read top→bottom for visual diff.
EXPECTED_LEAD_TO_BOULDER = {
    "5c": "4A",
    "6a": "4B",
    "6a+": "5A",   # tie with 4C → pick higher
    "6b": "5B",    # tie with 5A+ → pick higher
    "6b+": "5B+",
    "6c": "5C",
    "6c+": "6A",   # tie with 5C+ → pick higher
    "7a": "6B",    # tie with 6A+ → pick higher
    "7a+": "6B+",
    "7b": "6C",
    "7b+": "7A",   # tie with 6C+ → pick higher
    "7c": "7A+",
    "7c+": "7B",
    "8a": "7C",    # tie with 7B+ → pick higher
    "8a+": "7C+",
    "8b": "8A",
    "8b+": "8A+",
    "8c": "8B",
    "8c+": "8B+",
    "9a": "8C",
    "9a+": "8C+",
}


# ── Forward table ──────────────────────────────────────────────────────────


class TestBoulderToLead:
    def test_low_end(self):
        assert BOULDER_TO_LEAD["4A"] == "5c"
        assert BOULDER_TO_LEAD["4C"] == "6a+"

    def test_high_end(self):
        assert BOULDER_TO_LEAD["8C"] == "9a"
        assert BOULDER_TO_LEAD["8C+"] == "9a+"

    def test_known_ties_share_lead_bucket(self):
        # 4C and 5A both → 6a+
        assert BOULDER_TO_LEAD["4C"] == BOULDER_TO_LEAD["5A"] == "6a+"
        # 6A+ and 6B both → 7a
        assert BOULDER_TO_LEAD["6A+"] == BOULDER_TO_LEAD["6B"] == "7a"
        # 7B+ and 7C both → 8a
        assert BOULDER_TO_LEAD["7B+"] == BOULDER_TO_LEAD["7C"] == "8a"


# ── Inverse table ──────────────────────────────────────────────────────────


class TestLeadToBoulder:
    def test_pins_full_table(self):
        assert LEAD_TO_BOULDER == EXPECTED_LEAD_TO_BOULDER

    def test_inverse_picks_highest_on_ties(self):
        # 4C → 6a+ ; 5A → 6a+ ; pick 5A as inverse for 6a+
        assert LEAD_TO_BOULDER["6a+"] == "5A"
        # 5A+ → 6b ; 5B → 6b ; pick 5B
        assert LEAD_TO_BOULDER["6b"] == "5B"

    def test_inverse_unique_lead_buckets(self):
        # Lead grades with only one boulder pre-image should round-trip exactly.
        for lead, boulder in LEAD_TO_BOULDER.items():
            assert BOULDER_TO_LEAD[boulder] == lead, (
                f"Round-trip broke for lead {lead}: stored {boulder} → {BOULDER_TO_LEAD[boulder]}"
            )


# ── map_grade_for_discipline_change ────────────────────────────────────────


class TestMapGradeForDisciplineChange:
    def test_identity_when_discipline_unchanged(self):
        assert map_grade_for_discipline_change("7a", "lead", "lead") == "7a"
        assert map_grade_for_discipline_change("7B", "boulder", "boulder") == "7B"

    def test_lead_to_boulder(self):
        assert map_grade_for_discipline_change("8a", "lead", "boulder") == "7C"
        assert map_grade_for_discipline_change("6c+", "lead", "boulder") == "6A"

    def test_boulder_to_lead(self):
        assert map_grade_for_discipline_change("7B", "boulder", "lead") == "7c+"
        assert map_grade_for_discipline_change("4A", "boulder", "lead") == "5c"

    def test_both_treated_as_lead_canonical(self):
        # both → boulder remaps via LEAD_TO_BOULDER
        assert map_grade_for_discipline_change("8a", "both", "boulder") == "7C"
        # boulder → both remaps to lead canonical
        assert map_grade_for_discipline_change("7B", "boulder", "both") == "7c+"
        # both → all_round is a no-op (both lead-canonical)
        assert map_grade_for_discipline_change("8a", "both", "all_round") == "8a"

    def test_unknown_grade_returns_input(self):
        # Unknown lead grade — fall back to identity.
        assert map_grade_for_discipline_change("11z", "lead", "boulder") == "11z"
        # Unknown boulder grade — fall back to identity.
        assert map_grade_for_discipline_change("9X", "boulder", "lead") == "9X"

    def test_empty_grade_returns_input(self):
        assert map_grade_for_discipline_change("", "lead", "boulder") == ""
        assert map_grade_for_discipline_change(None, "lead", "boulder") is None  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "boulder",
        list(BOULDER_TO_LEAD.keys()),
    )
    def test_boulder_round_trip_via_canonical_inverse(self, boulder):
        """boulder → lead → boulder should land on the canonical (highest-tied) inverse."""
        lead = map_grade_for_discipline_change(boulder, "boulder", "lead")
        back_to_boulder = map_grade_for_discipline_change(lead, "lead", "boulder")
        # Round-trip lands on the canonical highest-tied inverse — not necessarily
        # the original (e.g. 4C → 6a+ → 5A, not 4C). Verify it matches the
        # canonical inverse map.
        assert back_to_boulder == LEAD_TO_BOULDER[lead]
