"""B360: l'override outdoor non scrive più l'intent come nome della falesia.

Il bug: `apply_day_override` derivava il nome della falesia dall'intent
(`intent.replace("outdoor_", "")`), quindi una giornata replanificata come
"outdoor_projecting" finiva con `outdoor_spot_name = "projecting"`. Non è solo
estetica: `geocode_place("projecting")` torna None, quindi il coach non riesce
a dare il meteo per quella giornata. In produzione il trip di Kalymnos porta
falesie che si chiamano "projecting", "volume", "easy".

Il fix: la falesia diventa un input (`spot_name`/`spot_id`, opzionali). Senza
falesia si scrive il placeholder neutro "Outdoor" — la stessa etichetta che
`outdoor.py::_sync_plan_after_outdoor_log` usa già — e mai un intent.

NESSUNA MIGRAZIONE: le giornate già sporche stanno in settimane archiviate,
9 su 10 con status "done". Le sessioni passate sono immutabili.
"""
from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine.macrocycle_v1 import (
    _BASE_WEIGHTS,
    _adjust_domain_weights,
    _build_session_pool,
)
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.replanner_v1 import (
    OUTDOOR_INTENT_TO_DISCIPLINE,
    OUTDOOR_SPOT_PLACEHOLDER,
    apply_day_override,
    apply_events,
)

REF_DATE = "2026-01-05"
TARGET_DATE = "2026-01-06"

# Le etichette che il vecchio codice scriveva al posto della falesia.
INTENT_LABELS = {"easy", "projecting", "volume", "boulder", "rest"}


def _availability():
    return {
        "mon": {
            "morning": {"available": True, "locations": ["home"]},
            "evening": {"available": True, "locations": ["gym"], "gym_id": "cocque"},
        },
        "tue": {"evening": {"available": True, "locations": ["gym"], "gym_id": "cocque"}},
        "wed": {"evening": {"available": True, "locations": ["gym"], "gym_id": "cocque"}},
        "thu": {"lunch": {"available": True, "locations": ["home"]}},
        "fri": {"evening": {"available": True, "locations": ["gym"], "gym_id": "cocque"}},
        "sat": {"morning": {"available": True, "locations": ["outdoor", "gym"], "gym_id": "cocque"}},
        "sun": {"available": False},
    }


def _make_plan():
    """Piano v2 reale (stesso stampo dei test B96/B97)."""
    profile = {
        "finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
        "technique": 50, "endurance": 40,
    }
    domain_weights = _adjust_domain_weights(_BASE_WEIGHTS["base"], profile)
    return generate_phase_week(
        phase_id="base",
        domain_weights=domain_weights,
        session_pool=_build_session_pool("base"),
        start_date=REF_DATE,
        availability=_availability(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
        default_gym_id="cocque",
        gyms=[{"gym_id": "cocque", "equipment": ["gym_boulder", "gym_routes", "hangboard"]}],
    )


def _day(plan, date_iso=TARGET_DATE):
    return next(d for d in plan["weeks"][0]["days"] if d["date"] == date_iso)


# ── 1. Il nome non viene mai più dall'intent ────────────────────────────────

@pytest.mark.parametrize("intent", sorted(OUTDOOR_INTENT_TO_DISCIPLINE) + ["rest"])
def test_b360_outdoor_override_never_writes_intent_as_spot(intent):
    """Senza falesia scelta: placeholder neutro, mai un'etichetta-intent."""
    updated = apply_day_override(
        _make_plan(),
        intent=intent,
        location="outdoor",
        reference_date=REF_DATE,
        target_date=TARGET_DATE,
    )
    name = _day(updated)["outdoor_spot_name"]
    assert name == OUTDOOR_SPOT_PLACEHOLDER
    assert name.lower() not in INTENT_LABELS, (
        f"intent {intent!r} è finito nel nome della falesia: il geocoder non lo risolve"
    )


# ── 2. La falesia scelta dall'utente vince ──────────────────────────────────

def test_b360_outdoor_override_uses_supplied_spot():
    updated = apply_day_override(
        _make_plan(),
        intent="outdoor_projecting",
        location="outdoor",
        reference_date=REF_DATE,
        target_date=TARGET_DATE,
        spot_name="Grande Grotta",
        spot_id="spot_abc",
    )
    day = _day(updated)
    assert day["outdoor_spot_name"] == "Grande Grotta"
    assert day["outdoor_spot_id"] == "spot_abc"
    assert day["outdoor_discipline"] == "both"


def test_b360_outdoor_override_strips_whitespace_only_spot_name():
    """Un nome fatto di soli spazi non è una falesia → placeholder."""
    updated = apply_day_override(
        _make_plan(),
        intent="outdoor_volume",
        location="outdoor",
        reference_date=REF_DATE,
        target_date=TARGET_DATE,
        spot_name="   ",
    )
    assert _day(updated)["outdoor_spot_name"] == OUTDOOR_SPOT_PLACEHOLDER


# ── 3. Cambiare tipo di giornata non cancella dove vai ──────────────────────

def test_b360_outdoor_override_preserves_existing_crag():
    plan = _make_plan()
    day = _day(plan)
    day["sessions"] = []
    day["outdoor_spot_name"] = "Telendos"
    day["outdoor_spot_id"] = "spot_telendos"
    day["outdoor_discipline"] = "both"

    updated = apply_day_override(
        plan,
        intent="outdoor_volume",
        location="outdoor",
        reference_date=REF_DATE,
        target_date=TARGET_DATE,
    )
    day_after = _day(updated)
    assert day_after["outdoor_spot_name"] == "Telendos", "la falesia esistente va preservata"
    assert day_after["outdoor_spot_id"] == "spot_telendos"
    assert day_after["outdoor_discipline"] == "lead", "l'intent conserva il suo unico ruolo"


# ── 4. Niente puntatore stantio ─────────────────────────────────────────────

def test_b360_outdoor_override_clears_stale_spot_id():
    plan = _make_plan()
    day = _day(plan)
    day["sessions"] = []
    day["outdoor_spot_name"] = "Vecchia Falesia"
    day["outdoor_spot_id"] = "spot_vecchio"

    updated = apply_day_override(
        plan,
        intent="outdoor_easy",
        location="outdoor",
        reference_date=REF_DATE,
        target_date=TARGET_DATE,
        spot_name="Nuova Falesia",
    )
    day_after = _day(updated)
    assert day_after["outdoor_spot_name"] == "Nuova Falesia"
    assert "outdoor_spot_id" not in day_after, (
        "un id stantio dirotterebbe meteo e pitch-ladder sulla falesia sbagliata"
    )


# ── 5/6. add_outdoor: il placeholder si sostituisce, le falesie vere si sommano

def _plan_with_outdoor_day(spot_name, spot_id=None, discipline=None):
    plan = _make_plan()
    day = _day(plan)
    day["sessions"] = []
    day["outdoor_spot_name"] = spot_name
    if spot_id:
        day["outdoor_spot_id"] = spot_id
    if discipline:
        day["outdoor_discipline"] = discipline
    return plan


def test_b360_add_outdoor_replaces_placeholder_instead_of_joining():
    plan = _plan_with_outdoor_day(OUTDOOR_SPOT_PLACEHOLDER)
    updated = apply_events(plan, [{
        "event_type": "add_outdoor", "date": TARGET_DATE,
        "spot_name": "Grande Grotta", "spot_id": "spot_gg", "discipline": "lead",
    }])
    day = _day(updated)
    assert day["outdoor_spot_name"] == "Grande Grotta", (
        "il placeholder non è una falesia: va sostituito, non accodato"
    )
    assert day["outdoor_spot_id"] == "spot_gg"


def test_b360_add_outdoor_keeps_a_crag_actually_named_outdoor():
    """Chi salva davvero uno spot chiamato 'Outdoor' non viene filtrato via."""
    plan = _plan_with_outdoor_day(OUTDOOR_SPOT_PLACEHOLDER)
    updated = apply_events(plan, [{
        "event_type": "add_outdoor", "date": TARGET_DATE,
        "spot_name": OUTDOOR_SPOT_PLACEHOLDER, "discipline": "lead",
    }])
    assert _day(updated)["outdoor_spot_name"] == OUTDOOR_SPOT_PLACEHOLDER


def test_b360_add_outdoor_still_joins_two_real_crags():
    """NON REGRESSIONE B341: due falesie vere restano composte."""
    plan = _plan_with_outdoor_day("Symplegades", spot_id="spot_sym", discipline="lead")
    updated = apply_events(plan, [{
        "event_type": "add_outdoor", "date": TARGET_DATE,
        "spot_name": "Ourania", "spot_id": "spot_our", "discipline": "boulder",
    }])
    day = _day(updated)
    assert day["outdoor_spot_name"] == "Symplegades - Ourania"
    assert day["outdoor_spot_id"] == "spot_sym", "lo spot_id resta quello della prima falesia"
    assert day["outdoor_discipline"] == "both", "discipline diverse → both"

    # idempotenza: ri-aggiungere la prima non la duplica
    again = apply_events(updated, [{
        "event_type": "add_outdoor", "date": TARGET_DATE,
        "spot_name": "Symplegades", "discipline": "lead",
    }])
    assert _day(again)["outdoor_spot_name"] == "Symplegades - Ourania"


# ── 7. Il ramo indoor non si accorge di niente ──────────────────────────────

@pytest.mark.parametrize("kwargs", [
    {"intent": "strength", "location": "gym", "gym_id": "cocque"},
    {"intent": "rest", "location": "home"},
    {"intent": "endurance", "location": "gym", "gym_id": "cocque", "session_index": 0},
])
def test_b360_indoor_override_plan_is_byte_identical(kwargs):
    """I nuovi kwargs non devono cambiare una virgola del percorso indoor."""
    gyms = [{"gym_id": "cocque", "equipment": ["gym_boulder", "gym_routes", "hangboard"]}]
    base = apply_day_override(
        _make_plan(), reference_date=REF_DATE, target_date=TARGET_DATE,
        gyms=gyms, **kwargs,
    )
    with_spot = apply_day_override(
        _make_plan(), reference_date=REF_DATE, target_date=TARGET_DATE,
        gyms=gyms, spot_id="spot_abc", spot_name="Grande Grotta", **kwargs,
    )
    assert json.dumps(base, sort_keys=True) == json.dumps(with_spot, sort_keys=True)
    assert "outdoor_spot_name" not in _day(base), "un override indoor non crea campi outdoor"


# ── 8. L'intent conserva il suo unico ruolo legittimo: la disciplina ────────

@pytest.mark.parametrize("intent,discipline", sorted(OUTDOOR_INTENT_TO_DISCIPLINE.items()))
def test_b360_b97_discipline_mapping_unchanged(intent, discipline):
    plan = _make_plan()
    day_after_before = deepcopy(_day(plan, "2026-01-07"))
    updated = apply_day_override(
        plan, intent=intent, location="outdoor",
        reference_date=REF_DATE, target_date=TARGET_DATE,
        spot_name="Grande Grotta",
    )
    assert _day(updated)["outdoor_discipline"] == discipline
    assert _day(updated, "2026-01-07") == day_after_before, "nessun ripple sul giorno dopo"


# ── 10. La guardia dell'immutabilità sta PRIMA del nuovo ramo di scrittura ──

def test_b360_completed_day_override_still_refused():
    plan = _make_plan()
    day = next(d for d in plan["weeks"][0]["days"] if d.get("sessions"))
    day["sessions"][0]["status"] = "done"
    before = deepcopy(day)

    with pytest.raises(ValueError):
        apply_day_override(
            plan, intent="outdoor_projecting", location="outdoor",
            reference_date=REF_DATE, target_date=day["date"],
            spot_name="Grande Grotta", spot_id="spot_gg",
        )
    assert "outdoor_spot_name" not in day
    assert day == before, "una giornata completata non si tocca, nemmeno col nuovo input"


# ── 9. Router: il nuovo input non apre porte laterali sul passato ───────────

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _past_monday() -> str:
    d = date.today() - timedelta(weeks=2)
    return (d - timedelta(days=d.weekday())).isoformat()


def test_b360_override_past_week_still_422(isolate_state):
    past = _past_monday()
    week_plan = {
        "start_date": past,
        "weeks": [{"phase": "base", "days": [
            {"date": (date.fromisoformat(past) + timedelta(days=i)).isoformat(),
             "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][i],
             "sessions": []}
            for i in range(7)
        ]}],
    }
    r = client.post("/api/replanner/override", json={
        "intent": "outdoor_projecting", "location": "outdoor",
        "reference_date": past, "target_date": past,
        "week_plan": week_plan,
        "spot_name": "Grande Grotta", "spot_id": "spot_gg",
    })
    assert r.status_code == 422, r.text
    assert "past" in r.json()["detail"].lower()
