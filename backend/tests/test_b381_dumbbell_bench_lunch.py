"""B381 — the push lunch pins the dumbbell bench press.

``upper_push_arms_lunch`` pinned ``bench_press``. Since B380 the barbell bench
needs a real barbell + bench, so a dumbbell-only gym lost the chest press (the
pin fell to the generic pick: handstand push-up, overhead press, fly), and at a
gym with a barbell the lunch prescribed the barbell while Daniele benches with
dumbbells (34 per hand). Decision (Daniele, 2026-10-17, option 4): pin
``dumbbell_bench_press`` for everyone. Its equipment stays ``dumbbell`` only —
adding ``bench`` would drop it again at every gym or home that lists dumbbells
without declaring a bench. A per-block ``fallback_exercise_ids`` is postponed.
"""

from __future__ import annotations

from backend.tests.test_b380_load_units import _entry, _state, _suggested
from backend.tests.test_c275_lunch_harder import _by_block, _resolve, _untested_state

SID = "upper_push_arms_lunch"
DATE = "2026-10-16"
WORK = ["barbell", "cable_machine", "dumbbell", "bench", "pullup_bar", "weight", "treadmill"]


def _chest(equipment):
    return _by_block(_resolve(SID, _untested_state(equipment, DATE), "strength_power")).get("chest_press")


class TestPin:
    def test_gym_with_barbell_prescribes_the_dumbbell_bench(self):
        chest = _chest(WORK)
        assert chest["exercise_id"] == "dumbbell_bench_press"
        assert (chest["prescription"]["sets"], chest["prescription"]["reps"]) == (4, 6)

    def test_dumbbells_without_a_declared_bench_still_get_it(self):
        assert _chest(["dumbbell", "pullup_bar", "rings"])["exercise_id"] == "dumbbell_bench_press"

    def test_no_free_weights_falls_back_to_another_push(self):
        # A barbell counts as dumbbells too (equipment_utils.expand_equipment),
        # so the fallback only shows without any free weight.
        chest = _chest(["bench", "pullup_bar", "rings"])
        assert chest is None or chest["exercise_id"] not in {"dumbbell_bench_press", "bench_press"}


class TestLoad:
    def test_own_dumbbell_number_wins(self):
        sug = _suggested(_state([_entry("bench_press", 70.0), _entry("dumbbell_bench_press", 34.0)]),
                         "dumbbell_bench_press")
        assert sug["suggested_external_load_kg"] == 34.0
        assert sug["load_unit"] == "per_dumbbell"

    def test_barbell_number_alone_converts_to_35_per_dumbbell(self):
        sug = _suggested(_state([_entry("bench_press", 70.0)]), "dumbbell_bench_press")
        assert sug["suggested_external_load_kg"] == 35.0
        assert sug["load_unit"] == "per_dumbbell"
