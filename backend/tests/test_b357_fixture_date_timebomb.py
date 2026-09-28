"""B357 — la fixture condivisa non deve portare una data che scade.

`backend/data/user_state.json` è la fixture che `conftest.isolate_storage_write_dirs`
copia nel tmp di OGNI test. Portava `goal.deadline: 2026-09-01`, e
`POST /api/macrocycle/generate` rifiuta con **400** un goal la cui deadline è nel
passato (`macrocycle.py`, "Goal deadline is in the past"). Siccome `PUT /api/state`
fa deep-merge, un test che scriveva un goal *senza* deadline ereditava quella della
fixture: dal 2026-09-02 in poi qualunque test che arrivava a `generate` per quella
strada prendeva un 400 che non c'entrava nulla con ciò che stava verificando.

È già successo: [[B347]] ha trovato `test_b119_start_date_monday` rotto non da una
regressione ma dal calendario.

Perché al momento della scrittura di questo brief NESSUN test falliva, pur con la
data già scaduta da 27 giorni — cioè perché la trappola era invisibile:

  * `test_a223_plan_pause` e `test_p0_equipment_regen` seminano da
    `backend/tests/fixtures/test_user_state.json`, che ha `deadline: 2030-12-31`;
  * `test_a230_mobility_pool` chiama `_reset()` → `DELETE /api/state`, che azzera
    lo stato e con esso la deadline stantia, così il ramo `if deadline:` del router
    non viene nemmeno valutato;
  * gli altri seminano una deadline propria, come vuole la regola di B347.

Tre vie di fuga diverse, nessuna dichiarata: il prossimo test scritto senza
conoscerle prende il 400. La bomba era armata, non disinnescata.

**Rimedio scelto: togliere del tutto `deadline` dalla fixture condivisa**, invece di
spostarla in avanti — bumpare la data sposta solo la bomba più in là, ed è
esattamente ciò che B347 aveva sconsigliato. Senza il campo, il guard del router
non scatta e ogni test che ha bisogno di una deadline se la semina, derivata da
`date.today()`.

Questo test impedisce che una data statica ci torni dentro.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_FIXTURE = REPO_ROOT / "backend" / "data" / "user_state.json"


def _goal() -> dict:
    return json.loads(SHARED_FIXTURE.read_text()).get("goal") or {}


def test_shared_fixture_carries_no_goal_deadline():
    """Nessuna deadline nella fixture condivisa: niente da ereditare, niente da scadere."""
    deadline = _goal().get("deadline")
    assert deadline is None, (
        "backend/data/user_state.json ha di nuovo una goal.deadline "
        f"({deadline!r}). PUT /api/state fa deep-merge, quindi ogni test che scrive "
        "un goal senza deadline eredita questa, e il giorno in cui scade "
        "/api/macrocycle/generate inizia a rispondere 400 a test che non c'entrano. "
        "Semina la deadline nel singolo test, derivandola da date.today()."
    )


def test_no_static_past_dates_among_fixture_goal_dates():
    """Guardia più larga: nessun campo data del goal è già scaduto.

    Copre il caso in cui qualcuno aggiunga un campo data diverso da `deadline`
    (es. `target_date`) ricadendo nella stessa trappola.
    """
    today = date.today()
    stale = []
    for key, value in _goal().items():
        if not isinstance(value, str) or len(value) != 10:
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            continue
        if parsed < today:
            stale.append(f"{key}={value}")
    assert not stale, (
        "La fixture condivisa porta date già passate: "
        + ", ".join(stale)
        + ". Una data statica in una fixture condivisa è una bomba a tempo: "
        "derivala nel test che ne ha bisogno."
    )
