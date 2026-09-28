"""B361 — una sessione creata da un override non portava il proprio carico.

`weekly_load_summary` si costruisce sommando `estimated_load_score` di ogni
sessione (`planner_v2.py` ~1944). Ogni costruttore di sessione del replanner lo
imposta — quick-add (`:226`), add_generated_session (`:360`), il dict di
`:430`, le sessioni di ripple (`:1280`, `:1293`), la custom (`:1546`) — tranne i
**quattro** costruiti da `apply_day_override`, che non lo impostavano affatto:
zero occorrenze in 290 righe di funzione.

Conseguenza, osservata in [[D270]]: su una settimana riplanificata il carico
smette di riflettere il contenuto reale — la settimana 12 mostrava 0 di carico
indoor con cinque sessioni pianificate. Non è un caso limite: è il percorso
normale, quello di chiunque tocchi "Change plan" su un giorno.

I default seguono i costruttori gemelli: 40 per una sessione ordinaria, **20 per
le sessioni di recupero** (`regeneration_easy`), come già fa il ripple a `:1293`
— un recupero che pesa come un allenamento non sarebbe un recupero.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.engine.planner_v2 import _INTENSITY_TO_LOAD

_SRC = (
    Path(__file__).resolve().parents[1] / "engine" / "replanner_v1.py"
).read_text()


def _apply_day_override_source() -> str:
    m = re.search(r"\ndef apply_day_override\(.*?\n(?=\ndef |\Z)", _SRC, re.S)
    assert m, "apply_day_override non trovata"
    return m.group(0)


def test_every_session_built_by_apply_day_override_carries_a_load_score():
    """Il difetto in forma diretta: tanti `intensity` quanti `estimated_load_score`.

    Ogni dict di sessione dichiara `intensity`; se il numero di
    `estimated_load_score` è inferiore, almeno un costruttore ha smesso di
    portare il carico e `weekly_load_summary` tornerà a sottostimare in silenzio.
    """
    body = _apply_day_override_source()
    intensities = len(re.findall(r'"intensity":', body))
    load_scores = len(re.findall(r'"estimated_load_score":', body))
    assert intensities > 0, "il test non sta più leggendo la funzione giusta"
    assert load_scores == intensities, (
        f"{intensities} sessioni costruite, solo {load_scores} con "
        "estimated_load_score: weekly_load_summary le conterà come zero"
    )


def test_recovery_sessions_use_the_recovery_default():
    """Il default dei recuperi è 20, come nel ripple: un recupero non pesa come un allenamento."""
    body = _apply_day_override_source()
    for m in re.finditer(
        r'"estimated_load_score": _INTENSITY_TO_LOAD\.get\(recovery_meta\["intensity"\], (\d+)\)',
        body,
    ):
        assert m.group(1) == "20", (
            f"default {m.group(1)} per una sessione di recupero: il gemello in "
            "_apply_ripple usa 20"
        )


@pytest.mark.parametrize("intensity", ["low", "medium", "high"])
def test_intensity_map_covers_the_values_the_catalog_uses(intensity):
    """I default non devono mai servire per le intensità reali del catalogo."""
    assert intensity in _INTENSITY_TO_LOAD, (
        f"'{intensity}' non è in _INTENSITY_TO_LOAD: il carico cadrebbe sul default"
    )


def test_load_map_values_are_ordered():
    """Un'intensità più alta deve pesare di più: è ciò che rende il totale leggibile."""
    low = _INTENSITY_TO_LOAD.get("low")
    medium = _INTENSITY_TO_LOAD.get("medium")
    high = _INTENSITY_TO_LOAD.get("high")
    assert low is not None and medium is not None and high is not None
    assert low < medium < high, f"scala non monotona: {low}, {medium}, {high}"
