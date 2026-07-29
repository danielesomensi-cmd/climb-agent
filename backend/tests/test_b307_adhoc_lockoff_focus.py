"""B307 — chiude le opzioni 2 e 3 di [[D261]] (sintomo: "bloccaggi" non produceva bloccaggi).

Invarianti sotto test:
  1. Focus dedicato `lock_off`: una richiesta di bloccaggi compone davvero
     esercizi di lock-off, non l'ennesima variante di trazione (prima la
     richiesta finiva nel bucket `pull`, 33 candidati, e perdeva).
  2. L'asse di diversità di MAX_PER_PATTERN è `recency_group`, non `pattern`:
     12 dei 14 esercizi pulling sono `pull_vertical`, quindi il cap scartava un
     bloccaggio come se fosse una quinta trazione.
  3. Le etichette `recency_group` quasi-duplicate sono normalizzate (D261 §3),
     altrimenti il cap si aggira da solo.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.engine.adhoc_builder import (
    FOCUS_DOMAINS,
    MAX_PER_PATTERN,
    compose_adhoc_session,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

LOCKOFF_IDS = {
    "lock_off_isometric", "frenchies", "one_arm_pullup_assisted",
    "archer_pullup", "typewriter_pullup", "uneven_grip_pullup",
}


def _catalog() -> dict:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("exercises") or list(raw.values()))
    return {ex["id"]: ex for ex in items if isinstance(ex, dict) and ex.get("id")}


def _state() -> dict:
    return {
        "equipment": {
            "home": ["hangboard", "pullup_bar", "dumbbell", "band", "resistance_band", "loading_pin"],
            "gyms": [],
        },
        "macrocycle": {
            "start_date": "2026-07-06",
            "phases": [{"phase_id": "performance", "duration_weeks": 3}],
        },
        "recent_sessions": [],
    }


# ── 1. focus dedicato lock_off (D261 opzione 3) ─────────────────────────


class TestLockOffFocus:
    def test_focus_is_registered(self):
        assert "lock_off" in FOCUS_DOMAINS
        assert FOCUS_DOMAINS["lock_off"] == ["lock_off_endurance"]

    def test_composes_actual_lockoffs(self):
        intent = {"equipment_set": "home", "focus": "lock_off", "minutes": 60}
        session = compose_adhoc_session(intent, _state(), _catalog())
        ids = {e["exercise_id"] for e in session["exercises"]}
        # il sintomo originale: la sessione DEVE contenere il bloccaggio puro
        assert "lock_off_isometric" in ids, ids
        assert len(ids & LOCKOFF_IDS) >= 3, ids

    def test_no_generic_pulling_dilutes_the_block(self):
        """Il bucket lock_off non deve annacquarsi con trazioni generiche.

        Warmup e core finisher sono attesi (il composer li aggiunge per
        struttura, non per focus); ciò che NON deve entrare è un esercizio di
        tirata privo di `lock_off_endurance` — il sintomo originale.
        """
        catalog = _catalog()
        intent = {"equipment_set": "home", "focus": "lock_off", "minutes": 60}
        session = compose_adhoc_session(intent, _state(), catalog)
        for e in session["exercises"]:
            dom = catalog[e["exercise_id"]].get("domain")
            dom = [dom] if isinstance(dom, str) else (dom or [])
            if "strength_pulling" in dom:
                assert "lock_off_endurance" in dom, (e["exercise_id"], dom)

    def test_deterministic(self):
        intent = {"equipment_set": "home", "focus": "lock_off", "minutes": 60}
        a = compose_adhoc_session(intent, _state(), _catalog())
        b = compose_adhoc_session(intent, _state(), _catalog())
        assert a == b


# ── 2. asse di diversità = recency_group (D261 opzione 2) ───────────────


class TestDiversityAxis:
    def test_cap_applies_per_recency_group(self):
        catalog = _catalog()
        intent = {"equipment_set": "home", "focus": "pull", "minutes": 90}
        session = compose_adhoc_session(intent, _state(), catalog)
        counts: dict = {}
        for e in session["exercises"]:
            rg = catalog[e["exercise_id"]].get("recency_group")
            if rg:
                counts[rg] = counts.get(rg, 0) + 1
        assert counts, "nessun esercizio con recency_group — test inefficace"
        for rg, n in counts.items():
            assert n <= MAX_PER_PATTERN, (rg, n, counts)

    def test_pull_session_spans_multiple_families(self):
        """Prima del fix il cap su `pattern` collassava la varietà reale."""
        catalog = _catalog()
        intent = {"equipment_set": "home", "focus": "pull", "minutes": 60}
        session = compose_adhoc_session(intent, _state(), catalog)
        groups = {
            catalog[e["exercise_id"]].get("recency_group")
            for e in session["exercises"]
        }
        assert len(groups - {None}) >= 3, groups


# ── 3. igiene delle etichette recency_group (D261 §3) ───────────────────


class TestRecencyGroupHygiene:
    def test_no_duplicate_vertical_pull_labels(self):
        """`vertical_pull` e `pulling_vertical` erano sinonimi di
        `pullup_variants`: con tre etichette il cap si aggira da solo."""
        catalog = _catalog()
        labels = {ex.get("recency_group") for ex in catalog.values()}
        assert "vertical_pull" not in labels
        assert "pulling_vertical" not in labels

    def test_lockoff_family_is_grouped(self):
        catalog = _catalog()
        assert catalog["frenchies"]["recency_group"] == "pullup_lock_off"
        assert catalog["lock_off_isometric"]["recency_group"] == "pullup_lock_off"
        assert catalog["uneven_grip_pullup"]["recency_group"] == "pullup_one_arm"
        assert catalog["eccentric_pullup"]["recency_group"] == "pullup_variants"
