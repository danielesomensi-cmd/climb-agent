"""B414 step 6 — REENTRY-MAX-HANG-SETS, option B (Daniele, 2026-11-07 «togli il tetto»).

B413 removed the re-entry factor on the anchored load cap; the last rule left
was the 5-set cap on max hangs in the first 2 exposures after a 14-day gap
(``anchored_load.REENTRY_MAX_HANG_SETS``, guard ``reentry_sets``, copied in
``adhoc_builder`` and in ``resolve_custom_exercises`` as ``stored_sets``).
It is gone with everything that only fed it: ``retest_policy.reentry_step`` /
``REENTRY_GAP_D`` / ``REENTRY_EXPOSURES``, ``anchored_load.ramp_for`` and the
``ramp`` key of the anchored payload, of ``anchor_summary`` and of
athlete_context's anchor rows. Loads never depended on it: only ``sets``,
``rep_scheme`` and ``guards`` move, and only for a max hang above 5 sets.

Legacy prescriptions (``suggested.anchored.ramp`` with or without ``factor``,
a ``reentry_sets`` guard) are read as stored, without migration.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from backend.engine import adhoc_builder as ab
from backend.engine import anchored_load as al
from backend.engine import athlete_context as ac
from backend.engine import retest_policy as rp
from backend.tests.test_b364_official_max_vs_working_load import _daniele

REPO = Path(__file__).resolve().parents[2]
GAP_DAY = "2026-10-13"  # first hang after the 24/09 test: the old n=1 re-entry
_RUN = {"finger_max": [{"date": d, "exercise_id": "max_hang_7s"} for d in ("2026-10-06", "2026-10-08", "2026-10-10")],
        "pulling_max": []}


def _catalog() -> dict:
    data = json.loads((REPO / "backend/catalog/exercises/v1/exercises.json").read_text(encoding="utf-8"))
    items = data["exercises"] if isinstance(data, dict) else data
    return {e["id"]: e for e in items}


class TestRemoved:
    def test_names_are_gone(self):
        for name in ("REENTRY_MAX_HANG_SETS", "ramp_for"):
            assert not hasattr(al, name) and name not in al.__all__, name
        for name in ("reentry_step", "REENTRY_GAP_D", "REENTRY_EXPOSURES"):
            assert not hasattr(rp, name) and name not in rp.__all__, name
        assert not hasattr(ab, "REENTRY_MAX_HANG_SETS")

    def test_no_ramp_in_the_payload_nor_in_the_summary(self):
        anch = al.anchored_load(_daniele(), "max_hang_7s", date=GAP_DAY)
        assert "ramp" not in anch and "ramp" not in al.anchor_summary(anch)
        assert "ramp" not in al.anchored_suggested_fields(anch)["anchored"]


class TestSetsAfterAGap:
    def test_six_sets_stay_six_with_the_same_load(self):
        gap = al.anchored_load(_daniele(), "max_hang_7s", date=GAP_DAY, sets=6)
        five = al.anchored_load(_daniele(), "max_hang_7s", date=GAP_DAY, sets=5)
        run = al.anchored_load(_daniele(registry=_RUN), "max_hang_7s", date=GAP_DAY, sets=6)
        assert (gap["sets"], gap["rep_scheme"]) == (6, "6x7s")
        assert all(g.get("guard") != "reentry_sets" for g in gap["guards"])
        for k in ("total", "cap", "floor", "external"):
            assert gap[k] == five[k] == run[k], k
        assert (run["sets"], run["rep_scheme"], run["guards"]) == (gap["sets"], gap["rep_scheme"], gap["guards"])

    def test_no_date_keeps_the_sets_too(self):
        assert al.anchored_load(_daniele(), "max_hang_7s", date="", sets=8)["sets"] == 8

    def test_custom_keeps_its_stored_sets(self):
        ex = [{"exercise_id": "max_hang_7s", "sets": 6, "work_seconds": 7, "load_kg": 20.0}]
        before = deepcopy(ex)
        out = al.resolve_custom_exercises(_daniele(), ex, GAP_DAY)[0]
        assert out["sets"] == 6 and "stored_sets" not in out
        assert ex == before  # never mutates the input

    def test_adhoc_energy_high_gives_six_hang_sets_after_a_gap(self):
        by_id = _catalog()
        for state in (_daniele(), _daniele(registry=_RUN)):
            out = ab._to_custom_exercise(by_id["max_hang_7s"], by_id, state, "strength_power", "high", GAP_DAY)
            assert (out["sets"], out["load_mode"]) == (6, "anchored")
            assert "ramp" not in (out.get("anchored") or {})

    def test_pulls_unchanged(self):
        a = al.anchored_load(_daniele(), "weighted_pullup", date="2026-10-21", sets=6)
        assert a["sets"] == 6 and a["rep_scheme"].startswith("6x")


class TestAthleteContextAndLegacy:
    def test_anchor_rows_carry_no_ramp(self):
        ctx = ac.build_athlete_context(_daniele(), GAP_DAY, with_proposals=False, include_next_week=False)
        assert ctx["version"] == ac.VERSION == "b414.1"
        rows = [r for r in ((ctx.get("anchors") or {}).get("exercises") or {}).values() if r]
        assert rows and all("ramp" not in r for r in rows)
        assert "reentry_sets" not in ac.render_text(ctx) + ac.render_coach_block(ctx)

    def test_legacy_stored_prescription_is_read_as_stored(self):
        """A done session frozen before B414 (pre-B413 ``factor`` and B413
        ``in_reentry`` shapes, guard ``reentry_sets``): the context reads it
        without error and the state is never rewritten (past sessions are
        immutable)."""
        st = _daniele()
        legacy = {
            "session_id": "finger_strength_home", "slot": "evening", "status": "done",
            "resolved": {"exercise_instances": [
                {"exercise_id": "max_hang_7s", "prescription": {"sets": 5, "work_seconds": 7},
                 "suggested": {"load_source": "anchored", "suggested_total_load_kg": 93.5,
                               "anchored": {"ramp": {"n": 1, "factor": 0.9, "gap_days": 19, "source": "exposures"},
                                            "guards": [{"guard": "reentry_sets", "sets": 5}]}}},
                {"exercise_id": "weighted_pullup", "prescription": {"sets": 4, "reps": 3},
                 "suggested": {"load_source": "anchored",
                               "anchored": {"ramp": {"n": 2, "gap_days": 18, "in_reentry": True,
                                                     "source": "exposures"}, "guards": []}}},
            ]},
            "actual_exercises": [{"exercise_id": "max_hang_7s", "completed_sets": 5, "used_total_load_kg": 93.5}],
        }
        days = [{"date": f"2026-10-{d:02d}", "sessions": [deepcopy(legacy)] if d == 6 else []} for d in range(5, 12)]
        st["week_plans"] = {"2026-10-05": {"start_date": "2026-10-05", "weeks": [{"days": days}]}}
        snapshot = deepcopy(st)
        a = ac.build_athlete_context(st, GAP_DAY, with_proposals=False, include_next_week=False)
        b = ac.build_athlete_context(deepcopy(snapshot), GAP_DAY, with_proposals=False, include_next_week=False)
        assert st == snapshot  # byte for byte: the legacy fields stay as they were
        assert a == b  # deterministic


class TestWeekReadOfCustoms:
    def test_get_week_view_anchors_planned_customs_and_keeps_played_ones(self):
        """Review B414 step 6: the GET /api/week read path
        (``_with_custom_anchored_loads`` → ``resolve_custom_exercises``). A done
        custom stored before B414 (5 sets, legacy ``stored_sets`` / ``ramp`` /
        ``reentry_sets``) comes back byte for byte; a planned 6-set hang custom
        on the gap day keeps its 6 sets, with no ``stored_sets`` (the old code
        showed 5); the stored plan is never mutated."""
        from backend.api.routers.week import _with_custom_anchored_loads

        legacy = {"exercise_id": "max_hang_7s", "sets": 5, "stored_sets": 6, "work_seconds": 7, "load_kg": 20.0,
                  "anchored": {"ramp": {"n": 1, "gap_days": 19, "in_reentry": True, "source": "exposures"},
                               "guards": [{"guard": "reentry_sets", "sets": 5}]}}
        planned = {"exercise_id": "max_hang_7s", "sets": 6, "work_seconds": 7, "load_kg": 20.0}
        plan = {"start_date": "2026-10-12", "weeks": [{"days": [
            {"date": "2026-10-12", "sessions": [{"session_id": "custom_cs_old", "is_custom": True,
                                                 "slot": "evening", "status": "done", "exercises": [legacy]}]},
            {"date": GAP_DAY, "sessions": [{"session_id": "custom_cs_new", "is_custom": True,
                                           "slot": "evening", "status": "planned", "exercises": [planned]}]},
        ]}]}
        before = deepcopy(plan)
        out = _with_custom_anchored_loads(plan, _daniele())
        assert plan == before
        played, upcoming = out["weeks"][0]["days"]
        assert played == before["weeks"][0]["days"][0]  # byte for byte
        row = upcoming["sessions"][0]["exercises"][0]
        assert (row["sets"], row["load_source"]) == (6, "anchored")
        assert "stored_sets" not in row and "ramp" not in row["anchored"]
        assert all(g.get("guard") != "reentry_sets" for g in row["anchored"].get("guards") or [])
        assert out == _with_custom_anchored_loads(deepcopy(before), _daniele())  # deterministic
