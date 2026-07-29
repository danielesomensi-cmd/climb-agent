"""A257 — `phase_affinity` popolata sul catalogo (causa radice di [[D261]]).

Prima di questo brief il campo esisteva su 1 esercizio su 255: il primo criterio
di `_rank_key` non discriminava mai, il secondo era codice morto, e la selezione
del composer adhoc collassava sull'**ordine alfabetico dell'id** — in ogni
sessione e per ogni focus.

Invarianti sotto test:
  1. Copertura: il catalogo dichiara l'affinità di fase, con le sole eccezioni
     motivate (esercizi `very_low`, phase-agnostici).
  2. Coerenza metodologica: l'affinità rispetta la banda d'intensità della fase
     (Hörst 4-3-2-1 come codificato in `macrocycle_v1`), quindi un max-hang non
     è "adatto" a un deload e la mobilità non è "adatta" a una fase di forza.
  3. Effetto: il composer preferisce esercizi appropriati alla fase corrente, e
     la stessa richiesta in fasi diverse produce sessioni diverse.
  4. `_rank_key` non ha più il termine morto.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from backend.engine import adhoc_builder
from backend.engine.adhoc_builder import _rank_key, compose_adhoc_session

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

PHASES = {"base", "strength_power", "power_endurance", "performance", "deload"}

# Banda d'intensità target per fase — deve restare allineata a
# PHASE_INTENSITY_CAP di macrocycle_v1 (vedi docs/catalog/phase_affinity_v1.md).
PHASE_BAND = {
    "base": {"low", "medium"},
    "strength_power": {"high", "max"},
    "power_endurance": {"medium", "high"},
    "performance": {"high", "max"},
    "deload": {"very_low", "low"},
}


def _exercises() -> list:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else (raw.get("exercises") or list(raw.values()))


def _catalog() -> dict:
    return {ex["id"]: ex for ex in _exercises() if isinstance(ex, dict) and ex.get("id")}


def _state(phase: str) -> dict:
    return {
        "equipment": {
            "home": ["hangboard", "pullup_bar", "dumbbell", "weight", "band", "resistance_band", "loading_pin"],
            "gyms": [],
        },
        "macrocycle": {"start_date": "2026-07-06", "phases": [{"phase_id": phase, "duration_weeks": 3}]},
        "recent_sessions": [],
    }


# ── 1. copertura ────────────────────────────────────────────────────────


class TestCoverage:
    def test_every_exercise_declares_affinity(self):
        missing = [e["id"] for e in _exercises() if not e.get("phase_affinity")]
        assert missing == [], missing

    def test_values_are_valid_phase_ids(self):
        for e in _exercises():
            aff = e.get("phase_affinity") or []
            aff = [aff] if isinstance(aff, str) else aff
            assert set(aff) <= PHASES, (e["id"], aff)
            assert len(aff) == len(set(aff)), (e["id"], aff)  # nessun duplicato


# ── 2. coerenza metodologica ────────────────────────────────────────────


class TestMethodologicalConsistency:
    def test_affinity_respects_phase_intensity_band(self):
        """Un esercizio non può essere 'adatto' a una fase la cui banda
        d'intensità non lo contempla (un max-hang in deload, ecc.).

        Vale in entrambe le direzioni: l'affinità al deload è concessa sulla
        sola intensità (una settimana di scarico non enfatizza un asse, chiede
        lavoro leggero), ma resta comunque dentro la banda.
        """
        for e in _exercises():
            if e["id"] == "fall_practice":
                continue  # unico valore curato a mano, precedente ad A257
            aff = e.get("phase_affinity") or []
            aff = [aff] if isinstance(aff, str) else aff
            inten = e.get("intensity_level")
            for p in aff:
                assert inten in PHASE_BAND[p], (e["id"], inten, p)

    def test_max_intensity_never_in_deload(self):
        for e in _exercises():
            aff = e.get("phase_affinity") or []
            if e.get("intensity_level") in ("high", "max"):
                assert "deload" not in aff, e["id"]

    def test_known_anchors(self):
        """Campioni di controllo verificabili a mano contro Hörst 4-3-2-1."""
        cat = _catalog()
        assert cat["max_hang_5s"]["phase_affinity"] == ["strength_power"]
        assert cat["board_limit_boulders"]["phase_affinity"] == ["strength_power"]
        assert "deload" in cat["cooldown_hip_pigeon"]["phase_affinity"]
        assert "power_endurance" in cat["repeater_15_15"]["phase_affinity"]


# ── 3. effetto sulla composizione ───────────────────────────────────────


class TestCompositionEffect:
    def test_picks_are_phase_appropriate(self):
        cat = _catalog()
        intent = {"equipment_set": "home", "focus": "fingers", "minutes": 60}
        session = compose_adhoc_session(intent, _state("strength_power"), cat)
        mains = [
            e for e in session["exercises"]
            if "warmup" not in (cat[e["exercise_id"]].get("role") or [])
        ]
        matching = [
            e for e in mains
            if "strength_power" in (cat[e["exercise_id"]].get("phase_affinity") or [])
        ]
        assert matching, [e["exercise_id"] for e in mains]

    def test_same_request_differs_across_phases(self):
        """Il senso stesso della periodizzazione: chiedere 'dita' in fase di
        forza non deve dare la stessa roba che in deload."""
        cat = _catalog()
        intent = {"equipment_set": "home", "focus": "fingers", "minutes": 60}
        sp = compose_adhoc_session(intent, _state("strength_power"), cat)
        dl = compose_adhoc_session(intent, _state("deload"), cat)
        assert {e["exercise_id"] for e in sp["exercises"]} != {
            e["exercise_id"] for e in dl["exercises"]
        }

    def test_deload_session_is_mostly_light(self):
        """`phase_affinity` è una PREFERENZA nel ranking, non un filtro: la
        maggioranza dei main deve risultare adatta al deload, non la totalità.
        (I cap di diversità possono spingere la coda della selezione su
        candidati non adatti quando le famiglie leggere si esauriscono —
        vedi A-ADHOC-DELOAD-CAP in roadmap.)

        Nota: NON si può asserire sulla posizione in lista — l'ordinamento
        finale dei main è per categoria (`_CATEGORY_ORDER`), non per ranking.
        """
        cat = _catalog()
        intent = {"equipment_set": "home", "focus": "fingers", "minutes": 60}
        session = compose_adhoc_session(intent, _state("deload"), cat)
        mains = [
            e for e in session["exercises"]
            if "warmup" not in (cat[e["exercise_id"]].get("role") or [])
        ]
        light = [
            e for e in mains
            if "deload" in (cat[e["exercise_id"]].get("phase_affinity") or [])
        ]
        assert len(light) > len(mains) / 2, [e["exercise_id"] for e in mains]

    def test_still_deterministic(self):
        cat = _catalog()
        intent = {"equipment_set": "home", "focus": "pull", "minutes": 60}
        a = compose_adhoc_session(intent, _state("strength_power"), cat)
        b = compose_adhoc_session(intent, _state("strength_power"), cat)
        assert a == b


# ── 4. il termine morto è sparito ───────────────────────────────────────


class TestRankKey:
    def test_signature_has_no_recent_arg(self):
        params = list(inspect.signature(_rank_key).parameters)
        assert params == ["ex", "phase"], params

    def test_phase_match_ranks_first(self):
        matching = {"id": "zzz_last_alphabetically", "phase_affinity": ["base"]}
        other = {"id": "aaa_first_alphabetically", "phase_affinity": ["deload"]}
        ranked = sorted([other, matching], key=lambda e: _rank_key(e, "base"))
        # prima di A257 avrebbe vinto "aaa" per ordine alfabetico
        assert ranked[0]["id"] == "zzz_last_alphabetically"

    def test_no_recent_leakage_in_module(self):
        src = inspect.getsource(adhoc_builder._rank_key)
        assert "recent" not in src.split('"""')[-1]
