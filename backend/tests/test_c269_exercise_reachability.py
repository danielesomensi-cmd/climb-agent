"""C269 — ogni esercizio del catalogo deve poter finire in una sessione.

Un esercizio che nessuna sessione può selezionare è lavoro di catalogo che non
raggiunge mai un atleta: c'è, si può leggere, e non succede niente. Non è un bug
rumoroso — è silenzioso per definizione, ed è esattamente il motivo per cui va
tenuto da un test invece che da un audit periodico.

**Come si misura davvero** (tre trappole, tutte prese in faccia scrivendo questo
brief, e tutte capaci di produrre numeri allarmanti e falsi):

1. *La location.* `resolve_session` legge la posizione da
   `user_state["context"]["location"]` e il primo stadio di P0 filtra su
   `location_allowed`. Senza location valida il conteggio crolla a **0 su 263**
   al primo passo, e ogni blocco risulta «saltato». Misurando così sembrava che
   17 sessioni su 35 perdessero blocchi e che `prehab_maintenance` si risolvesse
   nel vuoto: falso, era l'harness.
2. *Le chiavi di attrezzatura.* Vanno prese da `KNOWN_EQUIPMENT_KEYS`. Passare
   nomi plausibili ma inesistenti (`bands`, `treadmill`) li fa ignorare e produce
   23 falsi irraggiungibili.
3. *La rotazione.* Il resolver sceglie **un** esercizio per blocco: una passata
   sola mostra solo i vincitori. Bisogna ririsolvere passando i già visti come
   `extra_recent_ex_ids` finché non emerge più nulla — senza, sembrano
   irraggiungibili 203 esercizi su 263.

Misurato correttamente: **262 su 263**, e l'unico fuori era
`approach_hike_loaded`, che dichiarava `location_allowed: ["outdoor"]` mentre
nessuna sessione indoor si risolve mai con location `outdoor`. Aggiunto `home`:
un avvicinamento con lo zaino parte da casa, non dalla palestra.

Nota su cosa questo test NON dice: che l'esercizio verrà *effettivamente*
pianificato. Dipende anche da quali sessioni entrano nei pool del macrociclo
(vedi B349a/B349b). Qui si verifica che il catalogo e i filtri delle sessioni si
parlino — il gradino prima.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import tempfile

import pytest

from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS
from backend.engine.resolve_session import resolve_session

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
TEMPLATES = "backend/catalog/templates/v1"
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")

# `approach_hike_loaded` resta anche `outdoor`: la giornata in falesia si logga,
# non si risolve, quindi l'unica via per cui un esercizio outdoor-only può finire
# in una sessione è avere anche una location indoor.
_FULL_EQUIPMENT = sorted(KNOWN_EQUIPMENT_KEYS)


def _load_exercises() -> list:
    raw = json.loads(open(os.path.join(REPO_ROOT, EXERCISES)).read())
    return raw if isinstance(raw, list) else raw["exercises"]


def _state(location: str, finger_device: str) -> dict:
    return {
        "preferences": {"finger_training_device": finger_device},
        # Trappola 1: senza questo, P0 azzera tutto al filtro location.
        "context": {"location": location, "equipment": _FULL_EQUIPMENT},
        "equipment": {
            "home": _FULL_EQUIPMENT,
            "gyms": [{"gym_id": "g", "name": "G", "equipment": _FULL_EQUIPMENT}],
        },
        "goal": {"discipline": "lead", "current_grade": "7a", "target_grade": "7c"},
        "working_loads": {},
    }


@pytest.fixture(scope="module")
def reachable_ids() -> set:
    """Tutti gli exercise_id che il motore riesce a produrre, con rotazione."""
    logging.disable(logging.WARNING)
    sessions = sorted(glob.glob(os.path.join(REPO_ROOT, "backend/catalog/sessions/v1/*.json")))
    assert sessions, "nessuna sessione di catalogo trovata"

    seen: set = set()
    for _ in range(12):  # trappola 3: si gira finché non emerge più nulla
        before = len(seen)
        for location in ("gym", "home"):
            for device in ("hangboard", "loading_pin"):
                state = _state(location, device)
                for session_path in sessions:
                    rel = os.path.relpath(session_path, REPO_ROOT)
                    for phase in PHASES:
                        try:
                            result = resolve_session(
                                REPO_ROOT, rel, TEMPLATES, EXERCISES,
                                tempfile.mktemp(suffix=".json"),
                                user_state_override=state,
                                write_output=False,
                                phase=phase,
                                equipment_override=_FULL_EQUIPMENT,
                                extra_recent_ex_ids=sorted(seen),
                            )
                        except Exception:
                            continue
                        instances = (result.get("resolved_session") or {}).get(
                            "exercise_instances"
                        ) or []
                        for inst in instances:
                            if inst.get("exercise_id"):
                                seen.add(str(inst["exercise_id"]))
        if len(seen) == before:
            break
    logging.disable(logging.NOTSET)
    return seen


def test_every_catalog_exercise_can_be_selected_by_some_session(reachable_ids):
    all_ids = {str(e["id"]) for e in _load_exercises()}
    unreachable = sorted(all_ids - reachable_ids)
    assert not unreachable, (
        f"{len(unreachable)} esercizi non selezionabili da nessuna sessione: "
        f"{unreachable}. Sono lavoro di catalogo che non raggiunge mai un atleta. "
        "Cause tipiche: `location_allowed` che non contiene nessuna location "
        "indoor, oppure una combinazione role/domain/pattern che nessun blocco filtra."
    )


def test_the_sweep_actually_ran(reachable_ids):
    """Controllo di sanità: un harness rotto produce insiemi vuoti o minuscoli.

    Senza questo, un errore nel setup (location mancante, equipment sbagliato)
    farebbe passare il test sopra per il motivo peggiore — cioè non avendo
    misurato niente.
    """
    total = len({str(e["id"]) for e in _load_exercises()})
    assert len(reachable_ids) > total * 0.9, (
        f"solo {len(reachable_ids)}/{total} esercizi raggiunti: l'harness è rotto, "
        "non il catalogo. Controlla context.location e KNOWN_EQUIPMENT_KEYS."
    )


def test_approach_hike_is_reachable_indoors_too(reachable_ids):
    """Il caso concreto che C269 ha corretto, pinnato per nome."""
    assert "approach_hike_loaded" in reachable_ids


def test_cardio_exercises_from_c266_are_selectable(reachable_ids):
    """C266 ha aggiunto i cardio: devono poter finire in una sessione.

    La roadmap sosteneva che nessuna sessione potesse selezionarli. Misurato:
    tre su quattro erano già raggiungibili; solo l'avvicinamento non lo era.
    """
    for ex_id in (
        "easy_run_zone2",
        "stationary_bike_zone2",
        "treadmill_incline_walk",
        "approach_hike_loaded",
    ):
        assert ex_id in reachable_ids, f"{ex_id} non selezionabile da nessuna sessione"
