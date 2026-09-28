"""A283 — il numero di sessioni non deve più essere cappato al numero di giorni.

`planner_v2` usava `target_training_days_per_week` (GIORNI) come budget di
`session_target` (SESSIONI). Sul piano reale di Daniele — 7 sere in palestra + 4
pranzi a casa, 11 slot, `target_days: 7` — uscivano **7** sessioni e i 4 pranzi
restavano vuoti: `session_target = min(7, 11) = 7`, quindi la guardia di PASS 2.2
(`if total_sessions_placed < session_target`) era già falsa e il PASS che B121
aveva scritto proprio per riempire gli slot extra non girava mai.

L'allenamento spezzato — complementari a pranzo, arrampicata la sera — è il modo
in cui un adulto che lavora accumula volume senza sedute da tre ore. Finché il
budget era in giorni, l'app non sapeva esprimerlo e quei pranzi andavano scritti
a mano, cioè fuori dal motore e quindi fuori dal closed-loop.

**Preferenza esplicita, non derivata dagli slot.** Derivarla avrebbe cambiato in
silenzio il piano di chiunque abbia anche un solo giorno a due fasce, senza che
l'avesse chiesto: contro il principio deterministico. Chiave assente, `None`,
non-int o fuori range ⇒ comportamento identico a prima.
"""

from __future__ import annotations

import json
import unittest

from backend.engine.planner_v2 import generate_phase_week
from backend.engine.macrocycle_v1 import (
    _BASE_WEIGHTS,
    _adjust_domain_weights,
    _build_session_pool,
)

_PROFILE = {
    "finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
    "technique": 50, "endurance": 40,
}
_GYMS = [{
    "gym_id": "blocx",
    "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder",
                  "gym_routes", "dumbbell", "pullup_bar"],
}]
_PHASES = ["base", "strength_power", "power_endurance", "performance", "deload"]


def _split_availability():
    """Il caso reale: 7 sere in palestra + 4 pranzi a casa = 11 slot su 7 giorni."""
    av = {}
    for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        av[day] = {"evening": {"available": True, "locations": ["gym"],
                               "preferred_location": "gym"}}
        if day in ("mon", "tue", "wed", "thu"):
            av[day]["lunch"] = {"available": True, "locations": ["home"]}
    return av


def _plan(phase, prefs, availability=None, **extra):
    return generate_phase_week(
        phase_id=phase,
        domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase], _PROFILE),
        session_pool=_build_session_pool(phase),
        start_date="2026-03-02",
        availability=availability if availability is not None else _split_availability(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs=prefs,
        default_gym_id="blocx",
        gyms=_GYMS,
        **extra,
    )


def _count(plan):
    return sum(len(d.get("sessions") or []) for d in plan["weeks"][0]["days"])


def _fingerprint(plan):
    """Il piano senza `generated_at`, che è un timestamp e cambia a ogni run."""
    p = json.loads(json.dumps(plan))
    p.pop("generated_at", None)
    return json.dumps(p, sort_keys=True)


_BASE_PREFS = {"target_training_days_per_week": 7, "hard_day_cap_per_week": 3}


class TestA283TargetSessions(unittest.TestCase):

    def test_split_training_fills_the_lunch_slots(self):
        """Il sintomo: 11 slot disponibili, 7 sessioni piazzate."""
        for phase in ["base", "strength_power", "power_endurance", "performance"]:
            with self.subTest(phase=phase):
                without = _count(_plan(phase, dict(_BASE_PREFS)))
                with_pref = _count(_plan(phase, {**_BASE_PREFS, "target_sessions_per_week": 11}))
                self.assertEqual(without, 7, f"{phase}: atteso il sintomo (7 sessioni)")
                self.assertGreater(
                    with_pref, without,
                    f"{phase}: con target_sessions_per_week=11 devono esserci più sessioni",
                )

    def test_no_two_sessions_in_the_same_slot_when_split(self):
        """B359 vale anche qui: riempire gli slot non deve sovrapporre nulla."""
        for phase in _PHASES:
            with self.subTest(phase=phase):
                plan = _plan(phase, {**_BASE_PREFS, "target_sessions_per_week": 11})
                for day in plan["weeks"][0]["days"]:
                    slots = [s.get("slot") for s in (day.get("sessions") or [])]
                    self.assertEqual(len(slots), len(set(slots)), f"{phase} {day['date']}")

    def test_hard_day_cap_is_not_breached_by_extra_sessions(self):
        """Il cap dei giorni hard protegge il recupero: le extra devono restare non-hard."""
        for phase in _PHASES:
            with self.subTest(phase=phase):
                plan = _plan(phase, {**_BASE_PREFS, "target_sessions_per_week": 11})
                hard_days = sum(
                    1 for d in plan["weeks"][0]["days"]
                    if any(s.get("is_hard") for s in (d.get("sessions") or []))
                )
                self.assertLessEqual(hard_days, 3, f"{phase}: cap giorni hard sforato")

    def test_never_more_than_two_sessions_per_day(self):
        """Il `break` di PASS 2.2 è stato lasciato di proposito: max una extra al giorno."""
        for phase in _PHASES:
            with self.subTest(phase=phase):
                plan = _plan(phase, {**_BASE_PREFS, "target_sessions_per_week": 21})
                for day in plan["weeks"][0]["days"]:
                    self.assertLessEqual(len(day.get("sessions") or []), 2, day["date"])

    # ── Retrocompatibilità ────────────────────────────────────────────────

    def test_plan_is_identical_without_the_new_key(self):
        """NON REGRESSIONE, il test che conta: senza la chiave nulla cambia.

        Misurato su 25 configurazioni (5 target_days × 5 fasi): zero differenze,
        escluso `generated_at`. Se questo cade, il brief ha mosso i piani di
        utenti che non hanno chiesto niente.
        """
        for target_days in (3, 4, 5, 6, 7):
            for phase in _PHASES:
                with self.subTest(td=target_days, phase=phase):
                    prefs = {"target_training_days_per_week": target_days,
                             "hard_day_cap_per_week": 3}
                    a = _fingerprint(_plan(phase, dict(prefs)))
                    b = _fingerprint(_plan(phase, {**prefs, "target_sessions_per_week": None}))
                    self.assertEqual(a, b, "None deve valere come chiave assente")

    def test_invalid_values_fall_back_to_today_behaviour(self):
        """Un valore non valido non deve né rompere né cambiare il piano."""
        prefs = dict(_BASE_PREFS)
        baseline = _fingerprint(_plan("base", prefs))
        for bad in ("11", 11.5, 0, -3, 22, True, [], {}):
            with self.subTest(value=repr(bad)):
                got = _fingerprint(_plan("base", {**prefs, "target_sessions_per_week": bad}))
                self.assertEqual(got, baseline, f"{bad!r} doveva essere ignorato")

    def test_target_below_target_days_is_raised_not_honoured(self):
        """Meno sessioni che giorni è una contraddizione, non una richiesta."""
        low = _fingerprint(_plan("base", {**_BASE_PREFS, "target_sessions_per_week": 2}))
        none = _fingerprint(_plan("base", dict(_BASE_PREFS)))
        self.assertEqual(low, none, "target_sessions < target_days deve alzarsi a target_days")

    def test_youth_cap_survives_the_split(self):
        """D81 — il cap giovanile è sui giorni: lo split non deve aggirarlo.

        Senza la guardia, un under-18 con target_sessions alto impilerebbe
        sessioni sui 4 giorni concessi, che è esattamente ciò che il cap vieta.
        """
        prefs = {**_BASE_PREFS, "target_sessions_per_week": 14}
        adult = _count(_plan("base", prefs, user_age=30))
        minor = _count(_plan("base", prefs, user_age=16))
        self.assertLess(minor, adult, "l'under-18 non deve ottenere lo split")
        minor_plain = _count(_plan("base", dict(_BASE_PREFS), user_age=16))
        self.assertEqual(minor, minor_plain, "per l'under-18 la chiave deve essere inerte")


if __name__ == "__main__":
    unittest.main()
