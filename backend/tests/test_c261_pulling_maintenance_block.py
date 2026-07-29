"""C261 — blocco di mantenimento della tirata in `base` e `power_endurance`.

Origine: [[D263]] + risposta del KB. Il motore lasciava 3 fasi su 5 **senza
alcun** lavoro di tirata pesante, oltre la finestra di detraining della forza
massima (~4 settimane) e in contraddizione col modello DUP dichiarato in
`04_periodization.md` (*"phase weights shift gradually, not binary on/off"*).

Questo brief è l'azione 2 della raccomandazione KB ed è il **prerequisito** di
[[B308]] (frequenza garantita): senza una sessione che copra la tirata in quelle
fasi, il pass di garanzia non avrebbe nulla da collocare.

Invarianti sotto test:
  1. Le due sessioni scelte portano il blocco, e la scelta copre tutte e quattro
     le combinazioni fase × disciplina.
  2. Il blocco sta **dopo** lo specifico di arrampicata e **prima** di core e
     antagonisti (il KB è esplicito: eseguito affaticato, l'intensità reale
     scende, ed è l'unica variabile non comprimibile per la forza massima).
  3. La dose è di **mantenimento** (volume ridotto, intensità invariata), non
     di sviluppo.
  4. Il blocco non può rompere una sessione: `required: false`.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from backend.engine.macrocycle_v1 import _SESSION_POOL, _SESSION_POOL_BOULDER
from backend.engine.resolve_session import resolve_session

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSIONS = REPO_ROOT / "backend" / "catalog" / "sessions" / "v1"

CARRIERS = ("boulder_circuit_gym", "power_endurance_gym")
BLOCK_ID = "pulling_maintenance"

# domini che contano come "tirata" per la copertura di fase
PULL_DOMAINS = {"strength_pulling", "strength_general", "lock_off_endurance", "power"}


def _session(sid: str) -> dict:
    return json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))


def _block(sid: str) -> dict:
    mods = _session(sid)["modules"]
    return next(m for m in mods if m.get("block_id") == BLOCK_ID)


def _state() -> dict:
    return {
        "equipment": {
            "home": ["hangboard", "pullup_bar", "dumbbell", "weight"],
            "gyms": [{"gym_id": "g1", "name": "Test", "equipment": [
                "gym_boulder", "gym_routes", "hangboard", "pullup_bar", "dumbbell", "weight", "bench",
            ]}],
        },
        "macrocycle": {"start_date": "2026-06-01", "phases": [{"phase_id": "base", "duration_weeks": 3}]},
        "bodyweight_kg": 77.0,
        "context": {"location": "gym", "gym_id": "g1", "date": "2026-06-03"},
    }


# ── 1. presenza e copertura ─────────────────────────────────────────────


class TestPresenceAndCoverage:
    def test_both_carriers_have_the_block(self):
        for sid in CARRIERS:
            assert _block(sid), sid

    def test_covers_every_phase_discipline_combination(self):
        """base e power_endurance devono avere copertura in lead E boulder.

        `boulder_circuit_gym` è primary in base (entrambe le discipline) e in
        power_endurance/boulder; `power_endurance_gym` è primary in
        power_endurance/lead. Le due insieme chiudono tutte e quattro.
        """
        for phase in ("base", "power_endurance"):
            for pool_map, disc in ((_SESSION_POOL, "lead"), (_SESSION_POOL_BOULDER, "boulder")):
                pool = pool_map.get(phase, {})
                carriers = [s for s in CARRIERS if s in pool]
                assert carriers, (phase, disc, sorted(pool))

    def test_carriers_are_primary_not_optional(self):
        """Un portatore solo `available` non garantirebbe nulla."""
        assert _SESSION_POOL["base"]["boulder_circuit_gym"] == "primary"
        assert _SESSION_POOL_BOULDER["base"]["boulder_circuit_gym"] == "primary"
        assert _SESSION_POOL["power_endurance"]["power_endurance_gym"] == "primary"
        assert _SESSION_POOL_BOULDER["power_endurance"]["boulder_circuit_gym"] == "primary"


# ── 2. posizionamento ───────────────────────────────────────────────────


class TestPlacement:
    def test_after_climbing_before_accessories(self):
        for sid in CARRIERS:
            mods = _session(sid)["modules"]
            prio = {m.get("block_id") or m.get("template_id"): m.get("priority") for m in mods}
            p = prio[BLOCK_ID]
            climbing = [v for k, v in prio.items() if k in
                        ("boulder_circuit_main", "pe_boulder", "pe_routes", "finger_endurance")]
            accessories = [v for k, v in prio.items() if k in
                           ("core_standard", "antagonist_prehab", "cooldown_stretch")]
            assert climbing and all(p < c for c in climbing), (sid, p, climbing)
            assert accessories and all(p > a for a in accessories), (sid, p, accessories)

    def test_never_the_last_working_block(self):
        """Non deve essere un riempitivo di fine seduta."""
        for sid in CARRIERS:
            mods = _session(sid)["modules"]
            ids = [m.get("block_id") or m.get("template_id") for m in mods]
            assert ids.index(BLOCK_ID) < len(ids) - 1, sid


# ── 3. dose di mantenimento ─────────────────────────────────────────────


class TestMaintenanceDose:
    def test_low_volume_declared(self):
        for sid in CARRIERS:
            pres = _block(sid)["prescription"]
            assert pres["sets"] == 2, (sid, pres)          # sviluppo = 4-5 serie
            assert pres["rest_between_sets_seconds"] >= 180  # intensità alta ⇒ recupero pieno

    def test_prescription_overrides_the_exercise_default(self):
        """La dose del blocco deve vincere sui default dell'esercizio,
        altrimenti il 'mantenimento' diventa una seduta di sviluppo."""
        out = resolve_session(
            str(REPO_ROOT), "backend/catalog/sessions/v1/boulder_circuit_gym.json",
            "backend/catalog/templates/v1", "backend/catalog/exercises/v1/exercises.json", "",
            user_state_override=copy.deepcopy(_state()), write_output=False, phase="base",
        )
        blocks = (out.get("resolved_session") or {}).get("blocks") or []
        blk = next(b for b in blocks if b.get("block_id") == BLOCK_ID)
        sel = blk.get("selected_exercises") or []
        assert sel, blk.get("message")
        assert sel[0]["prescription"]["sets"] == 2, sel[0]["prescription"]


# ── 4. non può rompere la sessione ──────────────────────────────────────


class TestNonBreaking:
    def test_block_is_optional(self):
        for sid in CARRIERS:
            assert _block(sid)["required"] is False, sid

    def test_session_still_resolves_without_a_pullup_bar(self):
        """Senza sbarra il blocco salta, la sessione regge."""
        st = copy.deepcopy(_state())
        st["equipment"]["gyms"][0]["equipment"] = ["gym_boulder", "gym_routes"]
        out = resolve_session(
            str(REPO_ROOT), "backend/catalog/sessions/v1/boulder_circuit_gym.json",
            "backend/catalog/templates/v1", "backend/catalog/exercises/v1/exercises.json", "",
            user_state_override=st, write_output=False, phase="base",
        )
        blocks = (out.get("resolved_session") or {}).get("blocks") or []
        assert any((b.get("selected_exercises") or []) for b in blocks), "sessione vuota"
