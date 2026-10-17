"""B380 — what a load number means: per dumbbell, one implement, or total.

The catalog field ``load_unit`` says what the kg of an external-load exercise
counts:

- ``per_dumbbell`` — a PAIR of dumbbells, the number is ONE dumbbell
  (dumbbell bench press, curls, lateral raises, dumbbell row, overhead press);
- ``implement``    — ONE dumbbell / kettlebell / plate, the number is that
  implement (goblet squat, overhead triceps extension, wrist curls...);
- ``total``        — barbell, cable, machine: the number is the whole load
  (bench press, barbell row, deadlifts...).

A missing field means ``total`` — the pre-B380 reading, so nothing changes for
cable / machine / anything not annotated.

Progression is percentage-based and never needs the unit. The unit matters in
two places only: the display ("34 kg per dumbbell"), and the conversion
between the barbell and dumbbell variants of the same movement, which is a
plain ÷2 / ×2 on the total, rounded to 0.5 kg (decision Daniele, B380).
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

PER_DUMBBELL = "per_dumbbell"
IMPLEMENT = "implement"
TOTAL = "total"
LOAD_UNITS = (PER_DUMBBELL, IMPLEMENT, TOTAL)
DEFAULT_LOAD_UNIT = TOTAL

#: Barbell ↔ dumbbell variants of the same movement (both directions).
BARBELL_DUMBBELL_PAIRS: Dict[str, str] = {
    "bench_press": "dumbbell_bench_press",
    "barbell_row": "dumbbell_row",
}
BARBELL_DUMBBELL_PAIRS.update({v: k for k, v in list(BARBELL_DUMBBELL_PAIRS.items())})


def normalize_load_unit(value: Any) -> str:
    """A valid unit, or ``total`` for anything missing / unknown."""
    return value if value in LOAD_UNITS else DEFAULT_LOAD_UNIT


def load_unit_of(exercise: Optional[Mapping[str, Any]]) -> str:
    """The unit of a catalog exercise dict (missing → ``total``)."""
    return normalize_load_unit((exercise or {}).get("load_unit"))


def _round_half(value: float) -> float:
    return round(value / 0.5) * 0.5


def to_total(kg: float, unit: str) -> float:
    """The whole load lifted: a pair of dumbbells counts twice."""
    return float(kg) * 2.0 if unit == PER_DUMBBELL else float(kg)


def from_total(kg: float, unit: str) -> float:
    """The number to show / log for ``unit`` given the whole load."""
    return float(kg) / 2.0 if unit == PER_DUMBBELL else float(kg)


def convert_load(kg: float, from_unit: str, to_unit: str) -> float:
    """``kg`` expressed in ``from_unit`` → ``to_unit``, rounded to 0.5 kg.

    ``total`` 70 → ``per_dumbbell`` 35; ``per_dumbbell`` 34 → ``total`` 68.
    """
    return _round_half(from_total(to_total(kg, from_unit), to_unit))
