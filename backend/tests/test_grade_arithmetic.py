"""Tests for grade arithmetic — vocabulary §2.10.1 compliance."""
from __future__ import annotations

from backend.engine.progression_v1 import normalize_font_grade, step_grade


def test_step_grade_vocabulary_example_1():
    """lead_max_os=7c, offset=-2 → 7a (vocabulary §2.10.1)."""
    assert step_grade("7C", -2) == "7A"


def test_step_grade_vocabulary_example_2():
    """boulder_max_rp=6A, offset=-2 → 5B (vocabulary §2.10.1, corrected)."""
    assert step_grade("6A", -2) == "5B"


def test_step_grade_no_plus_in_output():
    """step_grade must never return grades with '+'."""
    for grade in ["5A", "6A", "7A", "7B", "7C", "8A", "8B", "8C"]:
        for offset in range(-6, 3):
            result = step_grade(grade, offset)
            assert "+" not in result, f"step_grade({grade}, {offset}) = {result}"


def test_step_grade_plus_input_handled():
    """Input with '+' is stripped without crash."""
    assert step_grade("7C+", -2) == "7A"
    assert step_grade("7c+", -2) == "7A"
    assert step_grade("6A+", 0) == "6A"
    assert step_grade("8B+", -1) == "8A"


def test_step_grade_integer_scale():
    """Whole-grade scale: 5A(0), 5B(1), 5C(2), 6A(3), 6B(4), ..."""
    assert step_grade("6A", 0) == "6A"
    assert step_grade("6A", 1) == "6B"
    assert step_grade("6A", 2) == "6C"
    assert step_grade("6A", 3) == "7A"
    assert step_grade("7C", -1) == "7B"
    assert step_grade("7C", -2) == "7A"
    assert step_grade("7C", -3) == "6C"


def test_step_grade_clamps():
    """Must not go out of scale bounds."""
    assert step_grade("5A", -10) == "5A"
    assert step_grade("8C", +10) == "8C"
    assert "+" not in step_grade("8C", +10)


def test_step_grade_case_insensitive():
    """Input is case-insensitive."""
    assert step_grade("7c", -2) == "7A"
    assert step_grade("7a", 1) == "7B"
    assert step_grade("6b", 0) == "6B"


def test_step_grade_fallback():
    """Invalid grades fall back to 6C."""
    assert step_grade("INVALID", 0) == "6C"
    assert step_grade("", 0) == "6C"
    assert step_grade("10A", 0) == "6C"


def test_normalize_font_grade_still_accepts_plus():
    """normalize_font_grade must still accept '+' grades for validation."""
    assert normalize_font_grade("7A+") == "7A+"
    assert normalize_font_grade("6C+") == "6C+"
    assert normalize_font_grade("7a") == "7A"
    assert normalize_font_grade("INVALID") is None
