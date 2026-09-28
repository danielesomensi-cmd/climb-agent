"""B358 — l'override settimanale non deve più rispondere `ok` a ciò che poi scarta.

`PUT /api/weekly-override/{week}` accettava i giorni sia come `mon` sia come
`monday` e rispondeva `{"status": "ok"}` in entrambi i casi, ma
`merge_override_into_availability` mappa **solo** i nomi lunghi: le chiavi corte
cadono in `if short is None: continue` e vengono scartate in silenzio.

In [[D270]] è costato una generazione sbagliata della settimana in montagna —
l'API confermava un salvataggio che non aveva alcun effetto, e il piano è uscito
con sette sere piene invece di due.

Il rimedio scelto è validare al bordo (422) invece di accettare entrambe le forme
nel merge: un payload che il motore non sa leggere non deve ricevere `ok`. Il
frontend manda già i nomi lunghi (`weekly-checkin-sheet.tsx`, mappa `longNames`),
quindi nessun percorso dell'app cambia comportamento.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def _next_monday() -> str:
    """Un lunedì futuro, derivato da oggi — mai una data statica (vedi B357)."""
    today = date.today()
    return (today + timedelta(days=(7 - today.weekday()) or 7)).isoformat()


def test_long_day_names_are_accepted_and_actually_applied():
    """Il percorso buono resta intatto: `monday` passa e arriva al merge."""
    week = _next_monday()
    r = client.put(
        f"/api/weekly-override/{week}",
        json={"days": {"monday": {"available": False}}},
    )
    assert r.status_code == 200, r.text

    merged = client.get(f"/api/weekly-override/{week}").json()
    monday = next(d for d in merged["days"] if d["day"].lower().startswith("mon"))
    assert monday["available"] is False, (
        "Il giorno salvato con il nome lungo deve risultare non disponibile: "
        "se è ancora disponibile, il merge non ha applicato l'override."
    )


def test_short_day_key_is_rejected_instead_of_silently_dropped():
    """`mon` non deve più ricevere 200: il merge lo scarterebbe."""
    r = client.put(
        f"/api/weekly-override/{_next_monday()}",
        json={"days": {"mon": {"available": False}}},
    )
    assert r.status_code == 422, (
        f"Atteso 422 per una chiave che il motore scarta, ricevuto {r.status_code}. "
        "Questo è esattamente il silenzio che ha causato D270."
    )
    assert "mon" in r.text


def test_typo_in_day_name_is_rejected():
    """Un refuso è la forma più probabile di questo bug in un client nuovo."""
    r = client.put(
        f"/api/weekly-override/{_next_monday()}",
        json={"days": {"mondey": {"available": False}}},
    )
    assert r.status_code == 422


def test_unknown_slot_is_rejected():
    """Stesso ragionamento un livello più sotto: gli slot ignoti sparivano uguale."""
    r = client.put(
        f"/api/weekly-override/{_next_monday()}",
        json={
            "days": {
                "tuesday": {
                    "available": True,
                    "slots": {"afternoon": {"available": True, "location": "gym"}},
                }
            }
        },
    )
    assert r.status_code == 422
    assert "afternoon" in r.text


def test_day_name_casing_is_tolerated():
    """Il case non è un errore dell'utente: `Monday` va normalizzato, non rifiutato."""
    week = _next_monday()
    r = client.put(
        f"/api/weekly-override/{week}",
        json={"days": {"Monday": {"available": False}}},
    )
    assert r.status_code == 200, r.text

    merged = client.get(f"/api/weekly-override/{week}").json()
    monday = next(d for d in merged["days"] if d["day"].lower().startswith("mon"))
    assert monday["available"] is False, (
        "`Monday` deve essere normalizzato a `monday` e applicato davvero: "
        "accettarlo senza applicarlo sarebbe lo stesso bug con un altro nome."
    )
