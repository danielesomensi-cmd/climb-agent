"""B359 — nessun giorno può avere due sessioni nello stesso slot.

Trovato durante la Fase 1 di [[A283]], NON dalla roadmap: `PASS 3` (iniezione dei
test periodici) chiamava `_find_best_slot` **senza** `occupied_slots` e sceglieva
*dopo* quale sessione sostituire. Su un giorno con `evening=primary` +
`lunch=complementare` il risultato era l'entry di *lunch* rimpiazzata da una
piazzata su *evening*: due sessioni alle 19.

Riprodotto sul codice di produzione, senza alcuna patch, in tre fasi su quattro:

    base            evening -> finger_maintenance_gym + test_repeater_7_3
    strength_power  evening -> technique_focus_gym    + test_repeater_7_3
    performance     evening -> boulder_circuit_gym    + test_repeater_7_3

Il caso `base` è il peggiore: sono **due sessioni dita lo stesso giorno**. La
guardia di spaziatura a 48 h era scritta su `day_has_finger`, che guarda l'intero
giorno, quindi si disattivava ogni volta che il giorno conteneva *una qualsiasi*
sessione dita — anche quando `replace_idx` cadeva su un'altra. Ora è misurata
sulla sessione che si sostituisce davvero (`old_meta`), che è l'unica per cui lo
scambio è neutro.

Stessa costruzione corretta in altri due punti (quality floor A282, pass2.6
garanzia tirata B308): erano latenti, non li ho riprodotti, ma la forma è identica.

Oggi il difetto è raro perché i giorni a due sessioni sono rari. **Con A283 — che
riempie gli slot liberi — diventerebbe il caso normale**, ed è il motivo per cui
questo brief viene prima.
"""

from __future__ import annotations

import unittest

from backend.engine.planner_v2 import generate_phase_week
from backend.engine.macrocycle_v1 import (
    _BASE_WEIGHTS,
    _adjust_domain_weights,
    _build_session_pool,
)

_PROFILE = {
    "finger_strength": 60,
    "pulling_strength": 55,
    "power_endurance": 45,
    "technique": 50,
    "endurance": 40,
}

_GYMS = [{
    "gym_id": "blocx",
    "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder",
                  "gym_routes", "dumbbell", "pullup_bar"],
}]


def _multi_slot_availability():
    """La configurazione di B121: giovedì ha due slot (pranzo + sera)."""
    return {
        "mon": {"evening": {"available": True, "locations": ["home"]}},
        "tue": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
        "wed": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
        "thu": {
            "lunch": {"available": True, "locations": ["home"]},
            "evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"},
        },
    }


def _kwargs(phase_id, *, target_days=6, availability=None, inject_tests=False):
    return dict(
        phase_id=phase_id,
        domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase_id], _PROFILE),
        session_pool=_build_session_pool(phase_id),
        start_date="2026-03-02",
        availability=availability if availability is not None else _multi_slot_availability(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": target_days, "hard_day_cap_per_week": 3},
        default_gym_id="blocx",
        gyms=_GYMS,
        inject_tests=inject_tests,
    )


_PHASES = ["base", "strength_power", "power_endurance", "performance"]


class TestB359NoSlotCollision(unittest.TestCase):

    def test_no_two_sessions_share_a_slot_when_tests_are_injected(self):
        """Il difetto originale: PASS 3 piazzava un test su uno slot già occupato."""
        for phase in _PHASES:
            with self.subTest(phase=phase):
                plan = generate_phase_week(**_kwargs(phase, inject_tests=True))
                for day in plan["weeks"][0]["days"]:
                    slots = [s.get("slot") for s in (day.get("sessions") or [])]
                    self.assertEqual(
                        len(slots), len(set(slots)),
                        f"{phase} {day['date']}: due sessioni nello stesso slot -> "
                        f"{[(s.get('slot'), s.get('session_id')) for s in day['sessions']]}",
                    )

    def test_no_two_finger_sessions_on_the_same_day(self):
        """La guardia sul gap dita non deve essere aggirabile dallo scambio di PASS 3.

        In `base` uscivano `finger_maintenance_gym` + `test_repeater_7_3` lo stesso
        giorno: il gap di 48 h è l'invariante di recupero più importante del motore.
        """
        from backend.engine.planner_v2 import _SESSION_META

        for phase in _PHASES:
            with self.subTest(phase=phase):
                plan = generate_phase_week(**_kwargs(phase, inject_tests=True))
                for day in plan["weeks"][0]["days"]:
                    finger = [
                        s["session_id"] for s in (day.get("sessions") or [])
                        if _SESSION_META.get(s.get("session_id", ""), {}).get("finger")
                    ]
                    self.assertLessEqual(
                        len(finger), 1,
                        f"{phase} {day['date']}: due sessioni dita lo stesso giorno -> {finger}",
                    )

    def test_single_session_days_are_unchanged(self):
        """NON REGRESSIONE: su un giorno a una sola sessione nulla cambia.

        È la configurazione di ogni piano esistente: `occupied_slots` è vuoto e il
        comportamento deve restare quello di prima. Se questo test si rompe, il
        brief ha cambiato i piani degli altri utenti, che non è ciò che deve fare.
        """
        one_slot = {
            d: {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}}
            for d in ("mon", "tue", "wed", "thu", "fri")
        }
        for phase in _PHASES:
            with self.subTest(phase=phase):
                plan = generate_phase_week(
                    **_kwargs(phase, target_days=4, availability=one_slot, inject_tests=True)
                )
                for day in plan["weeks"][0]["days"]:
                    self.assertLessEqual(
                        len(day.get("sessions") or []), 1,
                        f"{phase} {day['date']}: un giorno a slot singolo non deve "
                        "ospitare più di una sessione",
                    )

    def test_tests_are_still_injected(self):
        """Il fix non deve aver semplicemente smesso di piazzare i test periodici.

        Un modo banale di far passare i due test sopra è non collocare più nulla:
        questo lo impedisce.
        """
        placed = 0
        for phase in _PHASES:
            plan = generate_phase_week(**_kwargs(phase, inject_tests=True))
            for day in plan["weeks"][0]["days"]:
                # `explain` è una LISTA di tag (["phase=base", "slot=evening",
                # "day=mon", "pass3:test_session"]), non una stringa.
                placed += sum(
                    1 for s in (day.get("sessions") or [])
                    if "pass3:test_session" in (s.get("explain") or [])
                )
        self.assertGreater(
            placed, 0,
            "Nessuna sessione di test collocata in quattro fasi: il fix ha spento PASS 3.",
        )


if __name__ == "__main__":
    unittest.main()
