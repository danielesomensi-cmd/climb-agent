"""C262 — gli esercizi di estensori dita dichiarano l'elastico che richiedono.

Ultimo punto azionabile di [[C-EQUIPMENT-DECLARATIONS]] (da [[B305]]).
`finger_extensor_training` e `finger_extensor_band` avevano
`equipment_required=[]` pur richiedendo un elastico. Non erano stati corretti
subito per due timori, entrambi risolti:

  * **ambiguità della chiave** (`band` vs `resistance_band`, che
    `expand_equipment` non implica a vicenda) → risolta da
    `equipment_required_any`, la cui semantica OR funziona da [[B305]];
  * **togliere il prehab dita a chi non ha elastici** → verificato che non
    accade: esistono alternative senza attrezzo negli stessi domini.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.engine.body_part_picker import _exercise_fits_equipment

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

BAND_DEPENDENT = ("finger_extensor_training", "finger_extensor_band")
NO_BAND = ["hangboard", "pullup_bar", "weight", "dumbbell"]
WITH_BAND = NO_BAND + ["resistance_band"]


def _exercises() -> list:
    return json.loads(CATALOG.read_text(encoding="utf-8"))["exercises"]


def _domains(ex: dict) -> list:
    d = ex.get("domain")
    return [d] if isinstance(d, str) else list(d or [])


class TestBandRequirementDeclared:
    def test_both_declare_a_band(self):
        by_id = {e["id"]: e for e in _exercises()}
        for eid in BAND_DEPENDENT:
            any_ = by_id[eid].get("equipment_required_any") or []
            assert set(any_) == {"band", "resistance_band"}, (eid, any_)

    def test_either_band_key_satisfies_it(self):
        """L'ambiguità storica: `band` e `resistance_band` non si implicano a
        vicenda in `expand_equipment`, quindi la dichiarazione deve accettarli
        entrambi (semantica OR, disponibile da B305)."""
        by_id = {e["id"]: e for e in _exercises()}
        for eid in BAND_DEPENDENT:
            assert _exercise_fits_equipment(by_id[eid], ["band"]), eid
            assert _exercise_fits_equipment(by_id[eid], ["resistance_band"]), eid
            assert not _exercise_fits_equipment(by_id[eid], NO_BAND), eid


class TestNoCoverageLost:
    """Il timore che aveva bloccato il fix: togliere il prehab a chi non ha
    elastici. Verificato che entrambi i domini restano coperti."""

    def test_finger_prehab_survives_without_a_band(self):
        covered = [e["id"] for e in _exercises()
                   if "prehab_finger" in _domains(e) and _exercise_fits_equipment(e, NO_BAND)]
        assert covered, "nessun prehab dita senza elastico"

    def test_wrist_prehab_survives_without_a_band(self):
        covered = [e["id"] for e in _exercises()
                   if "prehab_wrist" in _domains(e) and _exercise_fits_equipment(e, NO_BAND)]
        assert covered, "nessun prehab polso senza elastico"

    def test_a_band_strictly_adds(self):
        for dom in ("prehab_finger", "prehab_wrist"):
            without = {e["id"] for e in _exercises()
                       if dom in _domains(e) and _exercise_fits_equipment(e, NO_BAND)}
            with_band = {e["id"] for e in _exercises()
                         if dom in _domains(e) and _exercise_fits_equipment(e, WITH_BAND)}
            assert without < with_band, dom


class TestJumpRopeStaysUnconstrained:
    """L'altro punto di C-EQUIPMENT-DECLARATIONS, chiuso come won't-fix.

    `jump_rope` non dichiara la corda perché **non esiste una chiave**
    `jump_rope`/`rope` in `KNOWN_EQUIPMENT_KEYS`, e non c'è modo per l'utente di
    dichiararla in onboarding. Introdurla renderebbe l'esercizio selezionabile
    solo da chi possiede una chiave che nessuno può possedere — cioè lo
    ucciderebbe, che è esattamente il difetto che [[D262]] ha appena bonificato.
    È un warmup `low` con sostituti equivalenti (corsa sul posto, jumping jack),
    quindi il costo di lasciarlo libero è trascurabile.
    """

    def test_no_phantom_equipment_key(self):
        from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS

        assert not [k for k in KNOWN_EQUIPMENT_KEYS if "rope" in k or "jump" in k]

    def test_jump_rope_remains_selectable_by_anyone(self):
        by_id = {e["id"]: e for e in _exercises()}
        assert _exercise_fits_equipment(by_id["jump_rope"], [])
