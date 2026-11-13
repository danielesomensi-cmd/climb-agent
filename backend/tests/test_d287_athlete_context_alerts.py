"""D287 — athlete_context says what really happens.

A1 — finger spacing is an ALERT. The ``finger_spacing`` reason still told the
coach that a finger session next to another one «la declasserebbe a
regeneration_easy». Since A301 the guards are alerts (``guards_v1``): nothing
is moved or downgraded, and ``replanner_v1._reconcile`` has no engine caller
left. The reason now names the real consequence — the ``finger_gap`` alert.
Verdict (``finger_max_ok``), codes and structure are unchanged.

A2 — a stale week is named. ``deps.mark_weeks_stale`` (B369) flags a cached
current / future week ``_stale`` when a setting changes, and only the next
``GET /api/week/{n}`` regenerates it. Until then the context showed the OLD
copy without saying so, and the coach re-checked 14 days by hand.
``stale_weeks`` + the ``STALE_WEEK`` warning name those weeks. Read-only: the
flag is not cleared and nothing is regenerated.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import date

import pytest

from backend.api import deps
from backend.engine import athlete_context as ac
from backend.engine import retest_policy as rp
from backend.tests.test_a293_athlete_context import TODAY, _day, _outdoor, _sess, _set_day, _state, _week
from backend.tests.test_a293_athlete_context_script import DRAFT, _boom, cli

_FINGER_NOT_HARD = {"hard": False, "finger": True}
_CURRENT, _NEXT, _THIRD, _PAST = "2026-09-28", "2026-10-05", "2026-10-12", "2026-09-21"


def _ctx(state):
    return ac.build_athlete_context(state, TODAY, outdoor_rows=_outdoor())


def _stale_warnings(ctx):
    return [w for w in ctx["warnings"] if w["code"] == "STALE_WEEK"]


def _flag(state, *weeks):
    for wk in weeks:
        state["week_plans"][wk][deps.STALE_KEY] = True
    return state


# ---------------------------------------------------------------------------
# A1 — the finger spacing reason states an alert, never a downgrade
# ---------------------------------------------------------------------------

class TestFingerSpacingIsAnAlert:
    def test_premise_the_enforcers_have_no_engine_caller(self):
        """What makes the old text false: only ``_reconcile`` calls the finger
        enforcer, and nothing in the engine or the API calls ``_reconcile``."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        callers = []
        for path in sorted(root.rglob("*.py")):
            if "tests" in path.parts:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]
                if "_reconcile(" in code and not code.lstrip().startswith("def "):
                    callers.append(f"{path.relative_to(root)}:{n}")
        assert callers == []

    def test_later_finger_session_is_an_alert_not_a_downgrade(self):
        st = _state()
        _set_day(st, _NEXT, "2026-10-09", [])  # no strength_long
        sat = _day(_ctx(st), "2026-10-10")
        [reason] = [r for r in sat["finger_reasons"] if "finger_maintenance_gym" in r]
        assert reason.startswith("sessione con tag dita il 2026-10-11 (finger_maintenance_gym)")
        assert "alert finger_gap" in reason and "nulla viene spostato né declassato" in reason
        # Verdict and language-neutral code are what they were.
        assert sat["finger_max_ok"] is False
        assert {"code": "finger_spacing", "detail": "2026-10-11 finger_maintenance_gym (1 d)"} in sat["finger_codes"]

    def test_earlier_finger_session_reads_the_same(self):
        st = _state()
        _set_day(st, _NEXT, "2026-10-08", [_sess("evening", "finger_maintenance_gym", tags=dict(_FINGER_NOT_HARD))])
        fri = _day(_ctx(st), "2026-10-09")
        [reason] = [r for r in fri["finger_reasons"] if "2026-10-08" in r]
        assert reason.startswith("sessione con tag dita il 2026-10-08 (finger_maintenance_gym)")
        assert "alert finger_gap" in reason and "nulla viene spostato né declassato" in reason
        assert fri["finger_max_ok"] is False
        assert {"code": "finger_spacing", "detail": "2026-10-08 finger_maintenance_gym (1 d)"} in fri["finger_codes"]

    def test_no_finger_reason_promises_a_downgrade(self):
        wide = _state()
        _set_day(wide, _NEXT, "2026-10-09", [])
        wide["week_plans"][_NEXT]["profile_snapshot"]["recovery_multiplier"] = 1.5  # 2-day spacing, both sides
        for st in (_state(), wide):
            ctx = _ctx(st)
            reasons = [r for d in ctx["guards"]["days"] for r in d["finger_reasons"]]
            assert any("spacing dita" in r for r in reasons)
            for r in reasons:
                assert "declasser" not in r and "regeneration_easy" not in r and "spacing del replanner" not in r
            txt = ac.render_text(ctx, state=st, outdoor_rows=_outdoor())
            guards = txt[txt.index("## Guardie"):txt.index("## Prossimi")]
            assert "declasserebbe" not in guards and "regeneration_easy" not in guards

    def test_english_coach_code_is_untouched(self):
        assert ac._GUARD_EN["finger_spacing"] == "finger session {detail} inside the plan's finger spacing"


# ---------------------------------------------------------------------------
# A2 — STALE_WEEK
# ---------------------------------------------------------------------------

class TestStaleWeek:
    def test_engine_reads_the_flag_the_api_sets(self):
        """The engine never imports the API layer: its copy of the key must be deps'."""
        assert rp._STALE_KEY == deps.STALE_KEY == "_stale"

    def test_baseline_fixture_has_none(self):
        ctx = _ctx(_state())
        assert ctx["stale_weeks"] == [] and _stale_warnings(ctx) == []

    def test_week_flagged_by_mark_weeks_stale_is_named(self):
        st = _state()
        marked = deps.mark_weeks_stale(st, today=date.fromisoformat(TODAY))
        assert sorted(marked) == [_CURRENT, _NEXT]  # the real flagger: current + future, never the past
        ctx = _ctx(st)
        assert ctx["stale_weeks"] == [{"week_start": _CURRENT, "week_end": "2026-10-04"},
                                      {"week_start": _NEXT, "week_end": "2026-10-11"}]
        warns = _stale_warnings(ctx)
        assert [w["week_start"] for w in warns] == [_CURRENT, _NEXT]
        for w in warns:
            assert set(w) == {"code", "week_start", "message"}
            assert w["week_start"] in w["message"] and "GET /api/week" in w["message"]
            assert "può cambiare" in w["message"] and "\n" not in w["message"]

    def test_only_the_flagged_week_is_named(self):
        ctx = _ctx(_flag(_state(), _NEXT))
        assert [r["week_start"] for r in ctx["stale_weeks"]] == [_NEXT]
        [w] = _stale_warnings(ctx)
        assert "2026-10-05 → 2026-10-11" in w["message"]

    def test_past_week_is_never_reported(self):
        """GET /api/week never regenerates a past week: a leftover flag there changes nothing."""
        assert _ctx(_flag(_state(), _PAST))["stale_weeks"] == []

    def test_window_is_the_weeks_of_the_upcoming_fourteen_days(self):
        st = _state()
        st["week_plans"][_THIRD] = _week(_THIRD, {})        # holds 2026-10-12 .. 10-17, inside today+13
        st["week_plans"]["2026-10-19"] = _week("2026-10-19", {})  # beyond the window
        ctx = _ctx(_flag(st, _THIRD, "2026-10-19"))
        assert [r["week_start"] for r in ctx["stale_weeks"]] == [_THIRD]
        # From a Monday the window is exactly two weeks.
        monday = ac.build_athlete_context(_flag(st, _NEXT), "2026-10-05", outdoor_rows=_outdoor())
        assert [r["week_start"] for r in monday["stale_weeks"]] == [_NEXT, _THIRD]

    def test_legacy_current_week_plan_is_read_when_it_is_the_only_copy(self):
        st = _state()
        st["current_week_plan"] = st["week_plans"].pop(_CURRENT)
        st["current_week_plan"][deps.STALE_KEY] = True
        assert [r["week_start"] for r in _ctx(st)["stale_weeks"]] == [_CURRENT]

    def test_week_plans_copy_wins_over_the_legacy_pointer(self):
        """Same precedence as ``stimulus.iter_plan_days`` and GET /api/week: the
        per-week cache is the plan shown; a flag only on the legacy copy is not."""
        st = _state()
        st["current_week_plan"] = dict(deepcopy(st["week_plans"][_CURRENT]), **{deps.STALE_KEY: True})
        assert _ctx(st)["stale_weeks"] == []

    def test_render_lists_it_under_avvisi(self):
        st = _flag(_state(), _NEXT)
        txt = ac.render_text(_ctx(st), state=st, outdoor_rows=_outdoor())
        avvisi = txt[txt.index("## Avvisi"):]
        [line] = [ln for ln in avvisi.splitlines() if "[STALE_WEEK]" in ln]
        assert "2026-10-05 → 2026-10-11" in line and "GET /api/week" in line and "può cambiare" in line

    def test_read_only_the_old_copy_is_shown_and_the_flag_stays(self):
        st = _flag(_state(), _CURRENT, _NEXT)
        before = deepcopy(st)
        ctx = _ctx(st)
        assert st == before  # nothing regenerated, flag not cleared, past sessions untouched
        assert st["week_plans"][_NEXT][deps.STALE_KEY] is True
        shown = [(s["date"], s["session_id"]) for s in ctx["upcoming"] if s["date"] >= _NEXT]
        stored = [(d["date"], s["session_id"]) for d in before["week_plans"][_NEXT]["weeks"][0]["days"]
                  for s in d["sessions"]]
        assert shown == stored

    def test_version_moved_with_the_new_section(self):
        assert ac.VERSION == "d287.1" and _ctx(_state())["version"] == "d287.1"


# ---------------------------------------------------------------------------
# CLI — read-only, and --simulate says when it ran on a stale copy
# ---------------------------------------------------------------------------

@pytest.fixture
def no_writes(monkeypatch):
    from backend.engine import storage_file

    monkeypatch.setattr(deps, "save_state", _boom)
    monkeypatch.setattr(storage_file, "write_state", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)


@pytest.fixture
def stale_files(tmp_path):
    st = tmp_path / "state.json"
    st.write_text(json.dumps([{"state": _flag(_state(), _NEXT)}]), encoding="utf-8")  # Supabase row shape
    dr = tmp_path / "draft.json"
    dr.write_text(json.dumps(DRAFT), encoding="utf-8")
    return {"state": st, "draft": dr}


def _sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class TestCli:
    def test_text_and_json_report_the_stale_week_without_writing(self, stale_files, no_writes, capsys):
        before = _sha(stale_files["state"])
        assert cli.main(["--state-file", str(stale_files["state"]), "--date", TODAY]) == cli.EXIT_OK
        out = capsys.readouterr().out
        assert "[STALE_WEEK] settimana 2026-10-05 → 2026-10-11" in out
        assert cli.main(["--state-file", str(stale_files["state"]), "--date", TODAY, "--json"]) == cli.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["context"]["stale_weeks"] == [{"week_start": _NEXT, "week_end": "2026-10-11"}]
        assert [w["week_start"] for w in payload["context"]["warnings"] if w["code"] == "STALE_WEEK"] == [_NEXT]
        assert _sha(stale_files["state"]) == before  # no regeneration, no write, no network (no_writes)

    def test_simulate_on_a_stale_week_says_so(self, stale_files, no_writes, capsys):
        before = _sha(stale_files["state"])
        rc = cli.main(["--state-file", str(stale_files["state"]), "--date", TODAY, "--simulate",
                       str(stale_files["draft"]), "--target-date", "2026-10-06", "--slot", "evening"])
        out = capsys.readouterr().out
        assert rc == cli.EXIT_OK
        sim_txt = out[out.index("=== Simulazione"):]
        assert "avviso: settimana 2026-10-05 marcata _stale" in sim_txt and "GET /api/week" in sim_txt
        assert _sha(stale_files["state"]) == before

    def test_simulate_payload_carries_the_stale_warning_only_when_stale(self):
        fresh = cli.simulate(_state(), DRAFT, "2026-10-06", "evening")
        assert not any("_stale" in w for w in fresh["warnings"])
        stale = cli.simulate(_flag(_state(), _NEXT), DRAFT, "2026-10-06", "evening")
        assert stale["ok"] is True  # the simulation still runs, on the stored copy
        assert [w for w in stale["warnings"] if "_stale" in w] != []
        # Same result as on the fresh copy: the flag changes no decision here.
        assert stale["downgrades"] == fresh["downgrades"] and stale["guard_alerts"] == fresh["guard_alerts"]

    def test_simulate_slot_collision_on_a_stale_week_still_says_so(self):
        sim = cli.simulate(_flag(_state(), _NEXT), DRAFT, "2026-10-06", "lunch")
        assert sim["ok"] is False and "occupato da prehab_maintenance" in sim["error"]
        assert any("_stale" in w for w in sim["warnings"])
