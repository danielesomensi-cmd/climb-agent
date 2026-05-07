"""A218 / A-MACRO-CAPS — phase duration cap behaviour.

Covers the 21 scenarios specified in `docs/audit/A-MACRO-CAPS_design.md` §7
plus regression checks for D233 findings F1 (off-by-one), F4 (boulder
weakness self-cancel), F6/F7 (incremental drift).
"""

import unittest

from backend.engine.macrocycle_v1 import (
    PHASE_ORDER,
    _BASE_DURATIONS_LEAD,
    _BASE_DURATIONS_BOULDER,
    _MAX_TOTAL_WEEKS,
    _MIN_TOTAL_WEEKS_LEAD,
    _MIN_TOTAL_WEEKS_BOULDER,
    _PHASE_CAPS_LEAD,
    _PHASE_CAPS_BOULDER,
    _PHASE_FLOORS_LEAD,
    _PHASE_FLOORS_BOULDER,
    _compute_phase_durations,
)


def _profile(**overrides):
    """Profile with all axes neutral (50) unless overridden."""
    base = {
        "finger_strength": 50,
        "pulling_strength": 50,
        "power_endurance": 50,
        "technique": 50,
        "endurance": 50,
    }
    base.update(overrides)
    return base


def _profile_weak(axis):
    """Profile where `axis` is the unique weakest (score 30); others neutral."""
    p = _profile()
    p[axis] = 30
    return p


# ---------------------------------------------------------------------------
# Constants invariants
# ---------------------------------------------------------------------------

class TestConstantsInvariants(unittest.TestCase):

    def test_max_total_weeks_is_16(self):
        self.assertEqual(_MAX_TOTAL_WEEKS, 16)

    def test_lead_min_is_11(self):
        self.assertEqual(_MIN_TOTAL_WEEKS_LEAD, 11)

    def test_boulder_min_is_8(self):
        self.assertEqual(_MIN_TOTAL_WEEKS_BOULDER, 8)

    def test_lead_floors_sum_equals_min(self):
        self.assertEqual(sum(_PHASE_FLOORS_LEAD.values()), _MIN_TOTAL_WEEKS_LEAD)

    def test_boulder_floors_sum_equals_min(self):
        self.assertEqual(sum(_PHASE_FLOORS_BOULDER.values()), _MIN_TOTAL_WEEKS_BOULDER)

    def test_lead_caps_sum_equals_max(self):
        # Lead is engineered so caps saturate exactly at total=16.
        self.assertEqual(sum(_PHASE_CAPS_LEAD.values()), _MAX_TOTAL_WEEKS)

    def test_lead_base_locked(self):
        self.assertEqual(_PHASE_FLOORS_LEAD["base"], _PHASE_CAPS_LEAD["base"])
        self.assertEqual(_PHASE_FLOORS_LEAD["base"], 4)

    def test_lead_defaults_sum_12(self):
        self.assertEqual(sum(_BASE_DURATIONS_LEAD.values()), 12)

    def test_boulder_defaults_sum_10(self):
        self.assertEqual(sum(_BASE_DURATIONS_BOULDER.values()), 10)


# ---------------------------------------------------------------------------
# Lead — no weakness (scenarios 1–6)
# ---------------------------------------------------------------------------

class TestLeadNoWeakness(unittest.TestCase):
    """Scenarios 1–6 from the design doc."""

    def _expect(self, total, expected):
        d = _compute_phase_durations(_profile(), total, discipline="lead")
        actual = (d["base"], d["strength_power"], d["power_endurance"],
                  d["performance"], d["deload"])
        self.assertEqual(actual, expected,
                         f"lead total={total}: expected {expected}, got {actual}")
        self.assertEqual(sum(d.values()), total)

    def test_lead_total_11(self):  # scenario 1
        self._expect(11, (4, 2, 2, 2, 1))

    def test_lead_total_12(self):  # scenario 2 (default)
        self._expect(12, (4, 3, 2, 2, 1))

    def test_lead_total_13(self):  # scenario 3
        self._expect(13, (4, 3, 2, 3, 1))

    def test_lead_total_14(self):  # scenario 4
        self._expect(14, (4, 4, 2, 3, 1))

    def test_lead_total_15(self):  # scenario 5
        self._expect(15, (4, 4, 3, 3, 1))

    def test_lead_total_16(self):  # scenario 6 — KB option B
        self._expect(16, (4, 4, 3, 3, 2))


# ---------------------------------------------------------------------------
# Lead — with weakness (scenarios 7–10)
# ---------------------------------------------------------------------------

class TestLeadWithWeakness(unittest.TestCase):

    def test_lead_12_pe_weak(self):  # scenario 7 — only active lead shift
        d = _compute_phase_durations(_profile_weak("power_endurance"), 12, discipline="lead")
        self.assertEqual(d, {"base": 4, "strength_power": 2, "power_endurance": 3,
                             "performance": 2, "deload": 1})

    def test_lead_12_finger_weak_clean_noop(self):  # scenario 8 — base-locked
        d = _compute_phase_durations(_profile_weak("finger_strength"), 12, discipline="lead")
        self.assertEqual(d, {"base": 4, "strength_power": 3, "power_endurance": 2,
                             "performance": 2, "deload": 1})

    def test_lead_16_pe_weak_path_differs_result_same(self):  # scenario 9
        d = _compute_phase_durations(_profile_weak("power_endurance"), 16, discipline="lead")
        # Path: weakness 4/2/3/2/1, then surplus 4 distributed.
        self.assertEqual(d, {"base": 4, "strength_power": 4, "power_endurance": 3,
                             "performance": 3, "deload": 2})

    def test_lead_16_technique_weak_clean_noop(self):  # scenario 10
        d = _compute_phase_durations(_profile_weak("technique"), 16, discipline="lead")
        self.assertEqual(d, {"base": 4, "strength_power": 4, "power_endurance": 3,
                             "performance": 3, "deload": 2})


# ---------------------------------------------------------------------------
# Boulder — no weakness (scenarios 11–16)
# ---------------------------------------------------------------------------

class TestBoulderNoWeakness(unittest.TestCase):

    def _expect(self, total, expected):
        d = _compute_phase_durations(_profile(), total, discipline="boulder")
        actual = (d["base"], d["strength_power"], d["power_endurance"],
                  d["performance"], d["deload"])
        self.assertEqual(actual, expected,
                         f"boulder total={total}: expected {expected}, got {actual}")
        self.assertEqual(sum(d.values()), total)

    def test_boulder_total_8(self):   # scenario 11
        self._expect(8, (2, 2, 1, 2, 1))

    def test_boulder_total_10(self):  # scenario 12 (default)
        self._expect(10, (2, 4, 1, 2, 1))

    def test_boulder_total_12(self):  # scenario 13
        self._expect(12, (2, 5, 1, 3, 1))

    def test_boulder_total_13(self):  # scenario 14
        self._expect(13, (2, 5, 2, 3, 1))

    def test_boulder_total_14(self):  # scenario 15 — corrected from design doc
        # Design doc had an arithmetic slip: pe (1→3) saturates BEFORE base
        # gets any surplus, because pe is earlier in priority and has 2 weeks
        # of headroom (cap 3 − default 1).
        self._expect(14, (2, 5, 3, 3, 1))

    def test_boulder_total_15(self):  # scenario 15b (added)
        # surplus=5: perf 2→3 (1), sp 4→5 (1), pe 1→3 (2), base 2→3 (1).
        self._expect(15, (3, 5, 3, 3, 1))

    def test_boulder_total_16(self):  # scenario 16
        self._expect(16, (4, 5, 3, 3, 1))


# ---------------------------------------------------------------------------
# Boulder — with weakness (scenarios 17–19, F4 fix)
# ---------------------------------------------------------------------------

class TestBoulderWithWeakness(unittest.TestCase):

    def test_boulder_12_finger_weak_F4_fix(self):  # scenario 17
        # F4 fix: OLD code returned 2/6/1/2/1 (sp inflated by flex absorber after
        # silent self-cancel). NEW algorithm returns clean 2/5/1/3/1.
        d = _compute_phase_durations(_profile_weak("finger_strength"), 12, discipline="boulder")
        self.assertEqual(d, {"base": 2, "strength_power": 5, "power_endurance": 1,
                             "performance": 3, "deload": 1})

    def test_boulder_10_endurance_weak_fires(self):  # scenario 18
        d = _compute_phase_durations(_profile_weak("endurance"), 10, discipline="boulder")
        self.assertEqual(d, {"base": 3, "strength_power": 3, "power_endurance": 1,
                             "performance": 2, "deload": 1})

    def test_boulder_16_pe_weak_saturated(self):  # scenario 19
        d = _compute_phase_durations(_profile_weak("power_endurance"), 16, discipline="boulder")
        self.assertEqual(d, {"base": 4, "strength_power": 5, "power_endurance": 3,
                             "performance": 3, "deload": 1})


# ---------------------------------------------------------------------------
# Error cases (scenarios 20–21)
# ---------------------------------------------------------------------------

class TestRangeValidation(unittest.TestCase):

    def test_lead_total_10_raises(self):  # scenario 20
        with self.assertRaises(ValueError):
            _compute_phase_durations(_profile(), 10, discipline="lead")

    def test_lead_total_17_raises(self):  # scenario 21
        with self.assertRaises(ValueError):
            _compute_phase_durations(_profile(), 17, discipline="lead")

    def test_boulder_total_7_raises(self):
        with self.assertRaises(ValueError):
            _compute_phase_durations(_profile(), 7, discipline="boulder")

    def test_boulder_total_17_raises(self):
        with self.assertRaises(ValueError):
            _compute_phase_durations(_profile(), 17, discipline="boulder")


# ---------------------------------------------------------------------------
# Incremental regen (scope-limited) — scenarios 22–24 from design
# ---------------------------------------------------------------------------

class TestIncrementalRegen(unittest.TestCase):

    def test_lead_perf_deload_total_5(self):  # scenario 22
        d = _compute_phase_durations(
            _profile(), 5, discipline="lead",
            phases=["performance", "deload"],
        )
        # defaults [perf:2, deload:1]=3, surplus 2.
        # Priority [perf, sp, pe, deload] filtered → [perf, deload].
        # perf 2→3 (cap), surplus 1; deload 1→2 (cap).
        self.assertEqual(d, {"performance": 3, "deload": 2})

    def test_lead_perf_deload_total_4(self):  # scenario 23 corrected
        d = _compute_phase_durations(
            _profile(), 4, discipline="lead",
            phases=["performance", "deload"],
        )
        # defaults sum=3, surplus 1 → perf 2→3.
        self.assertEqual(d, {"performance": 3, "deload": 1})

    def test_boulder_pe_perf_deload_total_6(self):  # scenario 24
        d = _compute_phase_durations(
            _profile(), 6, discipline="boulder",
            phases=["power_endurance", "performance", "deload"],
        )
        # defaults [pe:1, perf:2, deload:1]=4, surplus 2.
        # Priority [perf, sp, pe, base, deload] filtered → [perf, pe, deload].
        # perf 2→3 (cap), surplus 1; pe 1→2.
        self.assertEqual(d, {"power_endurance": 2, "performance": 3, "deload": 1})


# ---------------------------------------------------------------------------
# Postcondition invariants — every valid (total, discipline) sums correctly
# ---------------------------------------------------------------------------

class TestSumInvariant(unittest.TestCase):
    """F1 fix: every valid total_weeks produces sum(durations) == total_weeks.
    OLD code returned 10 weeks for lead total=9 (off-by-one). NEW raises."""

    def test_lead_all_valid_totals_sum_correctly(self):
        for total in range(_MIN_TOTAL_WEEKS_LEAD, _MAX_TOTAL_WEEKS + 1):
            d = _compute_phase_durations(_profile(), total, discipline="lead")
            self.assertEqual(sum(d.values()), total, f"lead total={total} mismatch")

    def test_boulder_all_valid_totals_sum_correctly(self):
        for total in range(_MIN_TOTAL_WEEKS_BOULDER, _MAX_TOTAL_WEEKS + 1):
            d = _compute_phase_durations(_profile(), total, discipline="boulder")
            self.assertEqual(sum(d.values()), total, f"boulder total={total} mismatch")

    def test_lead_caps_floors_respected_for_all_totals(self):
        for total in range(_MIN_TOTAL_WEEKS_LEAD, _MAX_TOTAL_WEEKS + 1):
            d = _compute_phase_durations(_profile(), total, discipline="lead")
            for p, v in d.items():
                self.assertGreaterEqual(v, _PHASE_FLOORS_LEAD[p])
                self.assertLessEqual(v, _PHASE_CAPS_LEAD[p])

    def test_boulder_caps_floors_respected_for_all_totals(self):
        for total in range(_MIN_TOTAL_WEEKS_BOULDER, _MAX_TOTAL_WEEKS + 1):
            d = _compute_phase_durations(_profile(), total, discipline="boulder")
            for p, v in d.items():
                self.assertGreaterEqual(v, _PHASE_FLOORS_BOULDER[p])
                self.assertLessEqual(v, _PHASE_CAPS_BOULDER[p])


# ---------------------------------------------------------------------------
# Discipline alias: "both" / "all_round" → lead behaviour
# ---------------------------------------------------------------------------

class TestDisciplineAlias(unittest.TestCase):
    """A218 Q3: confirmed `both`/`all_round` alias to lead durations."""

    def test_both_alias_to_lead(self):
        d_lead = _compute_phase_durations(_profile(), 12, discipline="lead")
        d_both = _compute_phase_durations(_profile(), 12, discipline="both")
        self.assertEqual(d_lead, d_both)

    def test_all_round_alias_to_lead(self):
        d_lead = _compute_phase_durations(_profile(), 14, discipline="lead")
        d_ar = _compute_phase_durations(_profile(), 14, discipline="all_round")
        self.assertEqual(d_lead, d_ar)


if __name__ == "__main__":
    unittest.main()
