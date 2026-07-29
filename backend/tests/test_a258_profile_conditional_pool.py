"""A258 — pool di fase condizionato al profilo + copertura tirata a casa.

Origine: [[D263]] punto 4 (CRITICO dal KB). I pesi di dominio si adattavano già
al profilo (`_adjust_domain_weights`), l'appartenenza al pool no: uno scalatore
con la tirata a 20/100 riceveva la stessa dose quasi nulla di uno a 100/100.

Invarianti sotto test:
  1. La sessione dedicata entra solo per chi ha l'asse debole, solo nelle fasi
     giuste, e in SOSTITUZIONE di una seduta dura, non in aggiunta.
  2. Retrocompatibilità totale: senza profilo il pool è identico a prima.
  3. Vale per ogni disciplina — il buco nel pool boulder è identico e in
     `power_endurance` pure più grave.
  4. La soglia è la stessa di `_adjust_domain_weights`: una sola definizione di
     "asse debole" in tutto il motore.
  5. Il pool viaggia nello snapshot, così un replan non fa sparire la sessione.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.engine.macrocycle_v1 import (
    WEAK_AXIS_THRESHOLD,
    _adjust_domain_weights,
    _BASE_WEIGHTS,
    _build_session_pool,
)

CONDITIONAL = "pulling_strength_gym"
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")
DISCIPLINES = ("lead", "boulder", "both")

WEAK = {"pulling_strength": 20, "finger_strength": 70, "technique": 60,
        "power_endurance": 55, "endurance": 50}
STRONG = {"pulling_strength": 100, "finger_strength": 100, "technique": 30,
          "power_endurance": 54, "endurance": 52}


# ── 1. la condizione ────────────────────────────────────────────────────


class TestConditionalUnlock:
    def test_weak_axis_unlocks_it_in_strength_power(self):
        for disc in DISCIPLINES:
            assert CONDITIONAL in _build_session_pool("strength_power", disc, WEAK), disc

    def test_not_unlocked_in_the_other_phases(self):
        for disc in DISCIPLINES:
            for phase in ("base", "power_endurance", "performance", "deload"):
                assert CONDITIONAL not in _build_session_pool(phase, disc, WEAK), (disc, phase)

    def test_base_is_excluded_because_of_its_intensity_cap(self):
        """Il KB indicava anche `base`, ma la sessione è `high` e base ha tetto
        `medium`: il planner la scarterebbe comunque. Dichiararla nel pool di
        base sarebbe una promessa senza effetto."""
        from backend.engine.planner_v2 import _SESSION_META, _intensity_allowed
        from backend.engine.macrocycle_v1 import PHASE_INTENSITY_CAP

        assert not _intensity_allowed(
            _SESSION_META[CONDITIONAL]["intensity"], PHASE_INTENSITY_CAP["base"]
        )

    def test_strong_axis_never_unlocks_it(self):
        for disc in DISCIPLINES:
            for phase in PHASES:
                assert CONDITIONAL not in _build_session_pool(phase, disc, STRONG), (disc, phase)

    @staticmethod
    def _week(profile, target_days):
        from backend.engine.planner_v2 import _SESSION_META, generate_phase_week

        plan = generate_phase_week(
            phase_id="strength_power", domain_weights=_BASE_WEIGHTS["strength_power"],
            session_pool=_build_session_pool("strength_power", "lead", profile),
            start_date="2026-06-01",
            availability={d: {"evening": {"available": True, "preferred_location": "gym", "gym_id": "g1"}}
                          for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
            gyms=[{"gym_id": "g1", "name": "T", "equipment": [
                "gym_boulder", "gym_routes", "hangboard", "pullup_bar", "weight", "dumbbell"]}],
            default_gym_id="g1", home_equipment=["hangboard", "pullup_bar", "weight"],
            hard_cap_per_week=4,
            planning_prefs={"target_training_days_per_week": target_days, "hard_day_cap_per_week": 4},
        )
        days = (plan.get("weeks") or [{}])[0].get("days") or []
        sids = [s.get("session_id") for d in days for s in (d.get("sessions") or [])]
        hard = sum(1 for s in sids if _SESSION_META.get(s, {}).get("hard"))
        return sids, hard

    def test_placed_in_substitution_never_in_addition(self):
        """"In sostituzione di un giorno duro, non in aggiunta" (KB).

        Misurato: da `available` la sessione non veniva MAI collocata (perde
        contro le primarie), quindi il ruolo è `primary`. Da `primary` entra al
        posto di un'altra seduta dura — il conteggio dei giorni duri resta
        identico fra profilo debole e profilo forte.
        """
        weak_sids, weak_hard = self._week(WEAK, 6)
        strong_sids, strong_hard = self._week(STRONG, 6)
        assert CONDITIONAL in weak_sids, weak_sids
        assert CONDITIONAL not in strong_sids, strong_sids
        assert weak_hard == strong_hard, (weak_hard, strong_hard)

    def test_eligibility_is_not_placement_below_six_days(self):
        """Onestà sul limite: sotto le 6 sedute/settimana la settimana si riempie
        di primarie e la sessione condizionata resta nel pool senza essere
        collocata. Non è un difetto di A258 — è la capienza settimanale — e per
        quegli utenti la tirata arriva comunque dalla garanzia di [[B308]]."""
        sids, _ = self._week(WEAK, 4)
        assert CONDITIONAL not in sids
        assert CONDITIONAL in _build_session_pool("strength_power", "lead", WEAK)

    def test_threshold_is_the_boundary(self):
        below = dict(WEAK, pulling_strength=WEAK_AXIS_THRESHOLD - 1)
        at = dict(WEAK, pulling_strength=WEAK_AXIS_THRESHOLD)
        assert CONDITIONAL in _build_session_pool("strength_power", "lead", below)
        assert CONDITIONAL not in _build_session_pool("strength_power", "lead", at)

    def test_threshold_matches_the_weak_axis_rule_used_for_weights(self):
        """Una sola definizione di "debole": alla stessa soglia il peso deve
        salire, altrimenti pool e pesi divergono in silenzio."""
        below = dict(WEAK, pulling_strength=WEAK_AXIS_THRESHOLD - 1)
        base = _BASE_WEIGHTS["base"]
        adjusted = _adjust_domain_weights(base, below)
        assert adjusted["pulling_strength"] > base["pulling_strength"]


# ── 2. retrocompatibilità ───────────────────────────────────────────────


class TestBackwardCompatible:
    def test_no_profile_means_unchanged_pool(self):
        for phase in PHASES:
            for disc in DISCIPLINES:
                assert _build_session_pool(phase, disc) == _build_session_pool(phase, disc, None), (phase, disc)

    def test_profile_without_the_axis_changes_nothing(self):
        partial = {"technique": 10}
        for phase in PHASES:
            assert _build_session_pool(phase, "lead", partial) == _build_session_pool(phase, "lead")

    def test_non_numeric_score_is_ignored(self):
        for bad in ({"pulling_strength": None}, {"pulling_strength": "low"}, {}):
            assert CONDITIONAL not in _build_session_pool("base", "lead", bad), bad

    def test_deterministic(self):
        assert _build_session_pool("base", "lead", WEAK) == _build_session_pool("base", "lead", WEAK)


# ── 3. lo snapshot porta il pool (divergenza del replanner) ─────────────


class TestSnapshotCarriesThePool:
    def test_generated_week_records_its_pool(self):
        from backend.engine.planner_v2 import generate_phase_week

        pool = _build_session_pool("base", "lead", WEAK)
        plan = generate_phase_week(
            phase_id="base", domain_weights=_BASE_WEIGHTS["base"], session_pool=pool,
            start_date="2026-06-01",
            availability={d: {"evening": {"available": True, "preferred_location": "gym", "gym_id": "g1"}}
                          for d in ("mon", "wed", "fri")},
            gyms=[{"gym_id": "g1", "name": "T", "equipment": ["gym_boulder", "pullup_bar", "hangboard", "weight"]}],
            default_gym_id="g1", home_equipment=["hangboard", "pullup_bar"],
        )
        assert plan["profile_snapshot"]["session_pool"] == pool

    def test_replanner_prefers_the_snapshot_pool(self):
        """Il replanner ricostruiva il pool da (phase_id, discipline): con A258
        avrebbe fatto sparire la sessione condizionata da una settimana
        replanificata."""
        src = Path(__file__).resolve().parents[1] / "engine" / "replanner_v1.py"
        text = src.read_text(encoding="utf-8")
        assert 'snapshot.get("session_pool")' in text


# ── 4. copertura della tirata a casa (HOME-ONLY-PULLING-GAP) ────────────


class TestHomePullingCoverage:
    SESSIONS = ("finger_maintenance_home", "finger_strength_home")

    def _session(self, sid):
        p = Path(__file__).resolve().parents[1] / "catalog" / "sessions" / "v1" / f"{sid}.json"
        return json.loads(p.read_text(encoding="utf-8"))

    def test_home_finger_sessions_carry_a_pulling_block(self):
        for sid in self.SESSIONS:
            mods = self._session(sid)["modules"]
            assert any(m.get("block_id") == "pulling_maintenance" for m in mods), sid

    def test_hangboard_implies_the_bar_so_the_block_is_always_doable(self):
        """Le due sessioni richiedono hangboard; `PULLUP_BAR_IMPLIERS` fa sì che
        l'hangboard implichi la sbarra — quindi il blocco non può mai essere
        irraggiungibile dove la sessione lo è."""
        from backend.engine.equipment_utils import expand_equipment

        for sid in self.SESSIONS:
            assert self._session(sid)["required_equipment"] == ["hangboard"], sid
        assert "pullup_bar" in expand_equipment(["hangboard"])

    def test_block_is_optional_and_placed_before_accessories(self):
        for sid in self.SESSIONS:
            mods = self._session(sid)["modules"]
            prio = {m.get("block_id") or m.get("template_id"): m.get("priority") for m in mods}
            blk = next(m for m in mods if m.get("block_id") == "pulling_maintenance")
            assert blk["required"] is False, sid
            assert prio["pulling_maintenance"] < prio.get("finger_strength_endurance",
                                                          prio.get("finger_max_strength")), sid
            assert prio["pulling_maintenance"] > prio["core_short"], sid
