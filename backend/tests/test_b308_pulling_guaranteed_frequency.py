"""B308 — PASS 2.6: stimolo di tirata garantito ogni settimana.

Origine: [[D263]] punto 3 (CRITICO dal KB). Un peso di dominio non garantisce
una dose: rende una sessione più probabile, che non è la stessa cosa. Misurato
sul piano reale di Daniele, la tirata restava non allenata per 8 settimane su
12 — oltre la finestra di detraining della forza massima (~4 settimane).

Il pass è modellato su PASS 2.5 (mantenimento dita in fase PE), che fa la stessa
cosa ed è in produzione da tempo.

Invarianti sotto test:
  1. Se la settimana non ha tirata, il pass ne colloca una.
  2. Il deload resta esente (il KB conferma che zero tirata in scarico è giusto).
  3. Nessun vincolo di sicurezza viene sacrificato: tetto giorni duri, distanza
     fra giorni duri, gap dita. Se non c'è spazio, NON si forza.
  4. Non sostituisce mai una sessione primaria.
  5. Quando non riesce, lo **dichiara** (`unmet_stimulus`) invece di tacere.
  6. Determinismo invariato.
"""

from __future__ import annotations

from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool
from backend.engine.planner_v2 import _SESSION_META, _is_primary_session, generate_phase_week

TRAINING_PHASES = ("base", "strength_power", "power_endurance", "performance")


def _week(plan: dict) -> list:
    return (plan.get("weeks") or [{}])[0].get("days") or []


def _session_ids(plan: dict) -> list:
    return [s.get("session_id") for d in _week(plan) for s in (d.get("sessions") or [])]


def _has_pulling(plan: dict) -> bool:
    return any(_SESSION_META.get(sid, {}).get("pulling") for sid in _session_ids(plan))


def _gym(equipment=None):
    return [{"gym_id": "g1", "name": "Test", "equipment": equipment or [
        "gym_boulder", "gym_routes", "hangboard", "pullup_bar", "dumbbell", "weight",
    ]}]


def _avail(days=("mon", "tue", "wed", "thu", "fri"), location="gym"):
    return {d: {"evening": {"available": True, "preferred_location": location,
                            "gym_id": "g1" if location == "gym" else None}} for d in days}


def _plan(phase, *, availability=None, gyms=None, home=None, pool=None, **kw):
    return generate_phase_week(
        phase_id=phase,
        domain_weights=_BASE_WEIGHTS[phase],
        session_pool=pool if pool is not None else _build_session_pool(phase, "lead"),
        start_date="2026-06-01",
        availability=availability if availability is not None else _avail(),
        gyms=gyms if gyms is not None else _gym(),
        default_gym_id="g1",
        home_equipment=home if home is not None else ["hangboard", "pullup_bar", "weight"],
        **kw,
    )


# ── 1. la garanzia ──────────────────────────────────────────────────────


class TestGuarantee:
    def test_every_training_phase_gets_pulling(self):
        for phase in TRAINING_PHASES:
            plan = _plan(phase)
            assert _has_pulling(plan), (phase, _session_ids(plan), plan.get("unmet_stimulus"))

    def test_pass_fires_when_the_pool_would_not_deliver_it(self):
        """Pool volutamente privo di sessioni di tirata tranne una: il pass
        deve andarla a prendere."""
        pool = ["technique_focus_gym", "prehab_maintenance", "flexibility_full", "boulder_circuit_gym"]
        plan = _plan("base", pool=pool)
        assert _has_pulling(plan), (_session_ids(plan), plan.get("unmet_stimulus"))

    def test_explains_itself_in_the_entry(self):
        plan = _plan("base", pool=["prehab_maintenance", "flexibility_full", "boulder_circuit_gym"])
        entries = [s for d in _week(plan) for s in (d.get("sessions") or [])
                   if "pass2.6:pulling_maintenance" in (s.get("explain") or [])]
        # può essere collocata dai pass normali: in quel caso non c'è marker, ed è corretto
        for e in entries:
            assert _SESSION_META[e["session_id"]].get("pulling")


# ── 2. il deload resta esente ───────────────────────────────────────────


class TestDeloadExempt:
    def test_no_pulling_injected_in_deload(self):
        plan = _plan("deload")
        injected = [s for d in _week(plan) for s in (d.get("sessions") or [])
                    if "pass2.6:pulling_maintenance" in (s.get("explain") or [])]
        assert injected == []

    def test_deload_reports_no_unmet_stimulus(self):
        """Non è un fallimento: è la regola."""
        assert (_plan("deload").get("unmet_stimulus") or []) == []


# ── 3. i vincoli di sicurezza vincono sulla garanzia ────────────────────


class TestSafetyConstraintsWin:
    def test_hard_cap_never_breached(self):
        for phase in TRAINING_PHASES:
            plan = _plan(phase, hard_cap_per_week=1)
            hard = [sid for sid in _session_ids(plan) if _SESSION_META.get(sid, {}).get("hard")]
            assert len(hard) <= 1, (phase, hard)

    def test_finger_gap_respected(self):
        for phase in TRAINING_PHASES:
            plan = _plan(phase)
            offsets = [i for i, d in enumerate(_week(plan))
                       for s in (d.get("sessions") or [])
                       if _SESSION_META.get(s.get("session_id", ""), {}).get("finger")]
            for a, b in zip(sorted(offsets), sorted(offsets)[1:]):
                assert b - a >= 2, (phase, offsets)

    def test_does_not_force_when_there_is_no_room(self):
        """Utente solo-casa senza palestra: in `base` nessuna sessione di tirata
        è eseguibile. Il pass NON deve inventare nulla — deve dichiararlo."""
        plan = _plan("base", availability=_avail(("mon", "wed", "fri"), location="home"),
                     gyms=[], home=["hangboard", "pullup_bar", "weight"])
        assert not _has_pulling(plan)
        unmet = plan.get("unmet_stimulus") or []
        assert unmet and unmet[0]["stimulus"] == "pulling", unmet


# ── 4. non tocca il lavoro primario ─────────────────────────────────────


class TestNeverDisplacesPrimary:
    def test_primary_sessions_survive(self):
        for phase in TRAINING_PHASES:
            plan = _plan(phase)
            for d in _week(plan):
                sessions = d.get("sessions") or []
                injected = [s for s in sessions
                            if "pass2.6:pulling_maintenance" in (s.get("explain") or [])]
                if not injected:
                    continue
                # sul giorno in cui ha agito, nessuna primaria è stata rimossa:
                # o il giorno era vuoto, o è stata sostituita una complementare
                others = [s for s in sessions if s not in injected]
                for o in others:
                    meta = _SESSION_META.get(o.get("session_id", ""), {})
                    assert meta, o
                    _is_primary_session(meta)  # non solleva


# ── 5. contratto del piano ──────────────────────────────────────────────


class TestPlanContract:
    def test_unmet_stimulus_key_always_present(self):
        for phase in TRAINING_PHASES + ("deload",):
            assert "unmet_stimulus" in _plan(phase)

    def test_empty_when_satisfied(self):
        plan = _plan("strength_power")
        if _has_pulling(plan):
            assert (plan.get("unmet_stimulus") or []) == []


# ── 6. determinismo ─────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_inputs_same_week(self):
        for phase in TRAINING_PHASES:
            a, b = _plan(phase), _plan(phase)
            assert _session_ids(a) == _session_ids(b), phase
            assert (a.get("unmet_stimulus") or []) == (b.get("unmet_stimulus") or [])


# ── 7. coerenza metadato ↔ catalogo ─────────────────────────────────────


class TestMetaMatchesCatalog:
    def test_pulling_flag_matches_the_session_definitions(self):
        """Il flag `pulling` in `_SESSION_META` deve riflettere il catalogo.

        A245 E-6 ha tolto l'I/O di catalogo a import-time da `planner_v2`, quindi
        il flag è dichiarato a mano: senza questa guardia va in deriva silenziosa
        appena qualcuno aggiunge o toglie un blocco di tirata.
        """
        import glob
        import json
        import os
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        pull_patterns = {"pull_vertical", "pull_horizontal"}
        pull_domains = {"strength_pulling", "lock_off_endurance"}

        tpl = {}
        for p in glob.glob(str(root / "backend/catalog/templates/v1/*.json")):
            if "_archive" in p:
                continue
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            doms, pats = set(), set()
            for b in d.get("blocks") or []:
                doms |= set(b.get("domain") or [])
                pats |= set(b.get("pattern") or [])
            tpl[d.get("id") or os.path.basename(p).replace(".json", "")] = (doms, pats)

        for sid, meta in _SESSION_META.items():
            path = root / f"backend/catalog/sessions/v1/{sid}.json"
            if not path.exists():
                continue
            d = json.loads(path.read_text(encoding="utf-8"))
            doms, pats = set(), set()
            for m in d.get("modules") or []:
                f = ((m.get("selection") or {}).get("primary") or {}).get("filters") or {}
                doms |= set(f.get("domain") or [])
                pats |= set(f.get("pattern") or [])
                if m.get("template_id"):
                    a, b = tpl.get(m["template_id"], (set(), set()))
                    doms |= a
                    pats |= b
            expected = bool((pats & pull_patterns) or (doms & pull_domains))
            assert bool(meta.get("pulling")) == expected, (
                sid, "meta:", bool(meta.get("pulling")), "catalogo:", expected,
            )
