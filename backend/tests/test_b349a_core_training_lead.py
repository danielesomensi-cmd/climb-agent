"""B349a — `core_training` mancava dal pool lead: una svista, non una decisione.

`planner_v2._SESSION_META` la dichiara (`max_per_week: 3`), il JSON di catalogo
esiste, e `_SESSION_POOL_BOULDER` la porta come `available` in tutte e quattro le
fasi non-deload. Il pool lead non ce l'aveva in nessuna. Non esiste una ragione
metodologica per cui il core serva a chi fa boulder e non a chi fa vie.

Ruolo `available` e non `primary`, misurato in Fase 1: `available` sposta 13
configurazioni sintetiche su 675 e non tocca mai `prehab_maintenance`;
`primary` ne sposta 88 su 675 e nella maggioranza dei casi scalza proprio la
prevenzione infortuni — cioè scambierebbe prevenzione per core, che è un baratto
che nessuno ha chiesto.

Fuori da `deload` di proposito, come nel pool boulder: `PHASE_INTENSITY_CAP` per
deload è `low` e `core_training` è `medium`, quindi il planner la scarterebbe
comunque. Dichiararla lì sarebbe una riga senza effetto.

**Cosa questo brief NON promette:** per 5 degli 8 utenti lead con
`target_days <= 4` non cambia nulla, nemmeno dopo una rigenerazione, perché il
PASS che colloca le sessioni `available` non gira. Chiude l'asimmetria e prepara
[[A283]]; non chiude da solo il sintomo "a pranzo esce sempre la stessa cosa".
"""

from __future__ import annotations

import pytest

from backend.engine.macrocycle_v1 import _SESSION_POOL, _SESSION_POOL_BOULDER, _build_session_pool

_NON_DELOAD = ["base", "strength_power", "power_endurance", "performance"]


@pytest.mark.parametrize("phase", _NON_DELOAD)
def test_core_training_is_available_in_lead(phase):
    assert _SESSION_POOL[phase].get("core_training") == "available", (
        f"core_training deve essere 'available' nella fase lead {phase}"
    )


@pytest.mark.parametrize("phase", _NON_DELOAD)
def test_lead_mirrors_boulder_role(phase):
    """Il ruolo deve essere lo stesso delle due discipline: è il senso del fix."""
    assert _SESSION_POOL[phase].get("core_training") == _SESSION_POOL_BOULDER[phase].get(
        "core_training"
    )


def test_not_in_deload_in_either_discipline():
    """Il cap di intensità del deload la scarterebbe: dichiararla sarebbe un no-op."""
    assert "core_training" not in _SESSION_POOL["deload"]
    assert "core_training" not in _SESSION_POOL_BOULDER["deload"]


@pytest.mark.parametrize("phase", _NON_DELOAD)
def test_reachable_from_the_built_lead_pool(phase):
    """Non basta la dichiarazione: deve sopravvivere a `_build_session_pool`."""
    assert "core_training" in _build_session_pool(phase, discipline="lead")


@pytest.mark.parametrize("phase", _NON_DELOAD)
def test_prehab_maintenance_is_not_displaced(phase):
    """La ragione per cui il ruolo è `available`: la prevenzione resta dov'era.

    Se qualcuno promuovesse `core_training` a `primary`, questo test cadrebbe
    nelle fasi dove `prehab_maintenance` è primary — ed è esattamente il baratto
    che B349a ha deciso di non fare.
    """
    lead = _SESSION_POOL[phase]
    if "prehab_maintenance" in lead:
        assert lead["prehab_maintenance"] == "primary"
