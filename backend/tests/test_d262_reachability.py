"""D262 — nessun esercizio del catalogo deve essere irraggiungibile.

L'audit di raggiungibilità (roadmap D262) ha trovato `regeneration_climbing`
selezionabile da nessun percorso: `role=["cooldown"]` + `domain=["regeneration"]`
mentre tutti i filtri su quel dominio chiedono `role=["main"]`. Più 8 esercizi
vivi nel planner ma invisibili al coach, perché il loro unico dominio non era
mappato da alcun focus adhoc.

Questi test bloccano la ricomparsa di entrambe le classi di problema.
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from backend.engine.adhoc_builder import (
    FOCUS_DOMAINS,
    MAX_BUMPABLE_WORK_SECONDS,
    compose_adhoc_session,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

# Percorsi di selezione che NON sono esprimibili come filtro di blocco.
PREHAB_ZONES = ("elbow", "finger", "shoulder", "wrist")


def _exercises() -> list:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["exercises"]


def _as_list(ex: dict, key: str) -> list:
    v = ex.get(key)
    return [v] if isinstance(v, str) else list(v or [])


def _planner_filters() -> list:
    """Tutti i filtri di selezione dichiarati da sessioni e template."""
    out = []
    for path in glob.glob(str(REPO_ROOT / "backend/catalog/sessions/v1/*.json")) + glob.glob(
        str(REPO_ROOT / "backend/catalog/templates/v1/*.json")
    ):
        if "_archive" in path:
            continue
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        label = os.path.basename(path)
        for m in d.get("modules") or []:
            p = (m.get("selection") or {}).get("primary") or {}
            if p.get("filters"):
                out.append((label, p["filters"]))
            if p.get("exercise_id"):
                out.append((label, {"exercise_id": p["exercise_id"]}))
        for b in d.get("blocks") or []:
            f = {k: b[k] for k in ("role", "domain", "pattern") if b.get(k)}
            if f:
                out.append((label, f))
            if b.get("exercise_id"):
                out.append((label, {"exercise_id": b["exercise_id"]}))
    return out


def _planner_reachable() -> set:
    reach = set()
    exs = _exercises()
    for _, flt in _planner_filters():
        if "exercise_id" in flt:
            reach.add(flt["exercise_id"])
            continue
        role = set(flt.get("role") or [])
        dom = set(flt.get("domain") or [])
        pat = set(flt.get("pattern") or [])
        for e in exs:
            if role and not (set(_as_list(e, "role")) & role):
                continue
            if dom and not (set(_as_list(e, "domain")) & dom):
                continue
            if pat and not (set(_as_list(e, "pattern")) & pat):
                continue
            reach.add(e["id"])
    # iniezione prehab da limitazioni (non è un filtro di blocco)
    prehab_domains = {f"prehab_{z}" for z in PREHAB_ZONES}
    for e in exs:
        if set(_as_list(e, "domain")) & prehab_domains:
            reach.add(e["id"])
    return reach


def _adhoc_reachable() -> set:
    """Esercizi che un percorso del composer adhoc può selezionare.

    Modella l'ammissibilità (dominio nel bucket di un focus, ruolo non escluso,
    warmup abbastanza corto, core finisher), non il ranking: la rotazione della
    recenza fa emergere nel tempo tutto il pool ammissibile.
    """
    all_focus_domains = {d for v in FOCUS_DOMAINS.values() for d in v}
    reach = set()
    for e in _exercises():
        roles = set(_as_list(e, "role"))
        blocked = {"warmup", "cooldown", "test"} & roles
        if set(_as_list(e, "domain")) & all_focus_domains and not blocked:
            reach.add(e["id"])
        if "warmup" in roles:
            ws = (e.get("prescription_defaults") or {}).get("work_seconds") or 0
            if int(ws or 0) <= 300:
                reach.add(e["id"])
        if str(e.get("category")) == "core" and not blocked:
            reach.add(e["id"])
    return reach


class TestNoDeadExercises:
    def test_every_exercise_has_at_least_one_path(self):
        reachable = _planner_reachable() | _adhoc_reachable()
        dead = sorted(e["id"] for e in _exercises() if e["id"] not in reachable)
        assert dead == [], dead

    def test_regeneration_climbing_is_selectable(self):
        """Il caso che ha originato l'audit: era l'unico dei 5 esercizi
        `domain=regeneration` con `role=cooldown`, mentre tutti i filtri su quel
        dominio chiedono `role=main`."""
        ex = next(e for e in _exercises() if e["id"] == "regeneration_climbing")
        assert "main" in _as_list(ex, "role")
        assert ex["id"] in _planner_reachable()

    def test_no_orphan_domain_on_coach_only_exercises(self):
        """Ogni dominio del catalogo che non appartiene a warmup/cooldown/test
        deve essere mappato da almeno un focus adhoc, altrimenti quegli
        esercizi sono invisibili al coach."""
        mapped = {d for v in FOCUS_DOMAINS.values() for d in v}
        orphans = {}
        for e in _exercises():
            roles = set(_as_list(e, "role"))
            if {"warmup", "cooldown", "test"} & roles:
                continue
            for d in _as_list(e, "domain"):
                if d not in mapped:
                    orphans.setdefault(d, []).append(e["id"])
        # `climbing_routes` resta fuori di proposito: è il tentativo di
        # redpoint su via, non un esercizio che il coach possa "comporre".
        orphans.pop("climbing_routes", None)
        assert orphans == {}, orphans


class TestHandstandProgression:
    def test_focus_exists_and_composes(self):
        assert FOCUS_DOMAINS["handstand"] == ["handstand_skill"]
        cat = {e["id"]: e for e in _exercises()}
        state = {
            "equipment": {"home": ["pullup_bar", "band", "resistance_band"], "gyms": []},
            "macrocycle": {"start_date": "2026-07-06", "phases": [{"phase_id": "base", "duration_weeks": 3}]},
            "recent_sessions": [],
        }
        s = compose_adhoc_session({"equipment_set": "home", "focus": "handstand", "minutes": 60}, state, cat)
        ids = {e["exercise_id"] for e in s["exercises"]}
        assert len(ids) >= 5, ids

    def test_progression_covers_the_whole_ladder(self):
        """Ingresso (low) → hold/equilibrio (medium) → spinta (high): prima di
        D262 il gradino più basso era `medium` e mancava il ponte muro→libera."""
        cat = {e["id"]: e for e in _exercises()}
        hs = [e for e in cat.values() if "handstand_skill" in _as_list(e, "domain")]
        levels = {e.get("intensity_level") for e in hs}
        assert {"low", "medium", "high"} <= levels, levels
        for eid in ("frog_stand", "handstand_kick_up_wall", "heel_pulls_chest_to_wall",
                    "wall_handstand_shrugs", "pike_pushup"):
            assert eid in cat, eid

    def test_new_drills_are_planner_selectable(self):
        """`handstand_practice` filtra domain=handstand_skill + role=accessory +
        pattern=handstand: i nuovi drill devono rispettare quella forma."""
        cat = {e["id"]: e for e in _exercises()}
        for eid in ("frog_stand", "handstand_kick_up_wall", "heel_pulls_chest_to_wall", "wall_handstand_shrugs"):
            ex = cat[eid]
            assert "accessory" in _as_list(ex, "role"), eid
            assert ex.get("pattern") == "handstand", eid
            assert "handstand_skill" in _as_list(ex, "domain"), eid


class TestLongBlockNotDoubled:
    def test_skill_practice_block_keeps_one_set(self):
        """Il riempimento di budget (B305) portava
        `freestanding_handstand_practice` a 2×600s = 20 min su 59."""
        cat = {e["id"]: e for e in _exercises()}
        state = {
            "equipment": {"home": ["pullup_bar", "band", "resistance_band", "dumbbell", "weight"], "gyms": []},
            "macrocycle": {"start_date": "2026-07-06", "phases": [{"phase_id": "base", "duration_weeks": 3}]},
            "recent_sessions": [],
        }
        s = compose_adhoc_session({"equipment_set": "home", "focus": "handstand", "minutes": 60}, state, cat)
        for e in s["exercises"]:
            if (e.get("work_seconds") or 0) >= MAX_BUMPABLE_WORK_SECONDS:
                assert e["sets"] == 1, (e["exercise_id"], e["sets"], e["work_seconds"])
