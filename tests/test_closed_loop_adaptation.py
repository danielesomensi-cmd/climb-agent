import pytest

from catalog.engine.adaptation.closed_loop import (
    apply_multiplier,
    compute_next_multiplier,
)


@pytest.mark.parametrize(
    ("difficulty", "expected"),
    [
        ("too_easy", 1.025),
        ("easy", 1.01),
        ("ok", 1.0),
        ("hard", 0.975),
        ("too_hard", 0.95),
        ("fail", 0.95),
    ],
)
def test_multiplier_moves_by_difficulty(difficulty, expected):
    assert compute_next_multiplier(1.0, difficulty, streak=0) == pytest.approx(expected)


def test_multiplier_clamps_to_bounds():
    high = compute_next_multiplier(1.14, "too_easy", streak=0)
    low = compute_next_multiplier(0.86, "too_hard", streak=0)

    assert high == pytest.approx(1.15)
    assert low == pytest.approx(0.85)


def test_deterministic_application():
    first = compute_next_multiplier(1.0, "easy", streak=1)
    second = compute_next_multiplier(1.0, "easy", streak=1)

    assert first == second
    assert apply_multiplier(40.0, first, 0.5) == apply_multiplier(40.0, second, 0.5)
