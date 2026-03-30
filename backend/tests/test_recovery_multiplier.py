"""Tests for B165b: recovery_multiplier age thresholds."""

from backend.api.routers.onboarding import _recovery_multiplier_for_age


class TestRecoveryMultiplierForAge:
    def test_none_age(self):
        assert _recovery_multiplier_for_age(None) == 1.0

    def test_age_25(self):
        assert _recovery_multiplier_for_age(25) == 1.0

    def test_age_40(self):
        """40-year-old must get 1.0 (B165b: threshold is 50, not 40)."""
        assert _recovery_multiplier_for_age(40) == 1.0

    def test_age_49(self):
        assert _recovery_multiplier_for_age(49) == 1.0

    def test_age_50(self):
        assert _recovery_multiplier_for_age(50) == 1.25

    def test_age_55(self):
        assert _recovery_multiplier_for_age(55) == 1.25

    def test_age_59(self):
        assert _recovery_multiplier_for_age(59) == 1.25

    def test_age_60(self):
        assert _recovery_multiplier_for_age(60) == 1.5

    def test_age_70(self):
        assert _recovery_multiplier_for_age(70) == 1.5
