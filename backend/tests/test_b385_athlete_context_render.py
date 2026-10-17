"""B385 — athlete_context CLI render fixes (render side only).

1. custom sessions by name, never the opaque ``custom_cs_*`` id;
2. planned outdoor days (spot + pitch ladder) in «Prossimi 14 giorni», and the
   window really is 14 days (was 15: ``range(UPCOMING_DAYS + 1)``);
3. a «Limit log» section (the ctx carried it, the text did not);
4. a try-hard count derived from the outdoor attempt results, labelled and
   kept apart from the formal note-format count.
``build_athlete_context`` (every coach turn in prod) gains no new work.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.engine import athlete_context as ac
from backend.tests.test_a293_athlete_context import TODAY, _outdoor, _sess, _state, _week

REPO_ROOT = Path(__file__).resolve().parents[2]


def _with_crag_days(state: dict) -> dict:
    """Next week gets a planned crag weekend (no sessions on those days)."""
    st = deepcopy(state)
    days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
    for d in days:
        if d["date"] == "2026-10-10":
            d.update({"outdoor_spot_name": "Berdorf", "outdoor_spot_id": "spot_0_berdorf",
                      "outdoor_session_status": "planned", "outdoor_discipline": "lead",
                      "outdoor_plan": {"discipline": "lead", "day_type": "project", "generated": False,
                                       "pitches": [
                                           {"index": 2, "grade": "6c+", "role": "build", "attempts": 1},
                                           {"index": 1, "grade": "6a", "role": "warmup", "attempts": 1},
                                           {"index": 3, "grade": "7c+", "role": "main", "attempts": 2,
                                            "note": "Isatis: commit al crux"},
                                       ]}})
        if d["date"] == "2026-10-11":
            d.update({"outdoor_spot_name": "Berdorf", "outdoor_session_status": "planned"})
    st["custom_sessions"] = [{"id": "cs_hiit", "name": "Work — HIIT 4x4 (VO2max)", "exercises": []},
                             {"id": "cs_pull", "name": "Trazioni", "exercises": []},
                             {"id": "cs_nameless_in_plan", "name": "Dal catalogo custom", "exercises": []}]
    return st


def _render(state=None, rows=None, today=TODAY, **kw):
    st = state if state is not None else _with_crag_days(_state())
    rows = rows if rows is not None else _outdoor()
    ctx = ac.build_athlete_context(st, today, outdoor_rows=rows)
    return ctx, ac.render_text(ctx, state=st, outdoor_rows=rows, **kw)


def _section(text: str, title: str) -> str:
    start = text.index(title)
    nxt = text.find("\n## ", start + 1)
    return text[start: nxt if nxt != -1 else len(text)]


# --------------------------------------------------------------------------- #
# 1. custom names
# --------------------------------------------------------------------------- #

class TestCustomNames:
    def test_no_opaque_custom_id_anywhere(self):
        _ctx, txt = _render()
        assert "custom_cs_" not in txt
        assert "custom «Work — HIIT 4x4 (VO2max)»" in txt
        assert "custom «Trazioni»" in txt

    def test_name_from_state_when_plan_copy_has_none(self):
        st = _with_crag_days(_state())
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        next(d for d in days if d["date"] == "2026-10-06")["sessions"].append(
            _sess("evening", "custom_cs_nameless_in_plan", "planned", is_custom=True))
        _ctx, txt = _render(st)
        assert "custom «Dal catalogo custom»" in _section(txt, "## Prossimi 14 giorni")

    def test_unknown_custom_is_labelled_not_printed_raw(self):
        st = _with_crag_days(_state())
        st["custom_sessions"] = []
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        next(d for d in days if d["date"] == "2026-10-06")["sessions"].append(
            _sess("evening", "custom_cs_deadbeef", "planned", is_custom=True))
        _ctx, txt = _render(st)
        assert "custom_cs_" not in txt
        assert "custom senza nome (cs_deadbeef)" in txt

    def test_json_keeps_the_ids(self):
        ctx, _txt = _render()
        assert any(s["session_id"] == "custom_cs_hiit" for s in ctx["upcoming"])


# --------------------------------------------------------------------------- #
# 2. planned outdoor days + 14-day window
# --------------------------------------------------------------------------- #

class TestUpcomingOutdoor:
    def test_planned_crag_days_rendered_with_pitches(self):
        _ctx, txt = _render()
        sec = _section(txt, "## Prossimi 14 giorni")
        assert ("2026-10-10 outdoor   Berdorf (lead, giornata project) [planned] tiri: "
                "6a riscaldamento, 6c+ avvicinamento, 7c+ main ×2") in sec
        assert "2026-10-11 outdoor   Berdorf (disciplina ?) [planned] nessun piano dei tiri" in sec

    def test_route_names_from_notes_are_not_printed(self):
        _ctx, txt = _render()
        assert "Isatis" not in _section(txt, "## Prossimi 14 giorni")

    def test_outdoor_lines_sorted_with_sessions(self):
        _ctx, txt = _render()
        lines = [l for l in _section(txt, "## Prossimi 14 giorni").splitlines()[1:] if l.strip()]
        dates = [l.split()[0] for l in lines]
        assert dates == sorted(dates)

    def test_bare_planner_outdoor_slot_is_not_a_crag_day(self):
        st = _with_crag_days(_state())
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        next(d for d in days if d["date"] == "2026-10-08")["outdoor_slot"] = True
        assert all(o["date"] != "2026-10-08" for o in ac.planned_outdoor_days(st, TODAY))

    def test_window_is_exactly_14_days(self):
        st = _with_crag_days(_state())
        last = (date.fromisoformat(TODAY) + timedelta(days=13)).isoformat()
        beyond = (date.fromisoformat(TODAY) + timedelta(days=14)).isoformat()
        st["week_plans"]["2026-10-12"] = _week("2026-10-12", {
            last: [_sess("evening", "technique_focus_gym")],
            beyond: [_sess("evening", "strength_long")],
        })
        ctx = ac.build_athlete_context(st, TODAY, outdoor_rows=_outdoor())
        dates = {s["date"] for s in ctx["upcoming"]}
        assert last in dates and beyond not in dates
        assert max(o["date"] for o in ac.planned_outdoor_days(st, TODAY)) <= last

    def test_without_state_render_is_ctx_only(self):
        ctx = ac.build_athlete_context(_with_crag_days(_state()), TODAY, outdoor_rows=_outdoor())
        txt = ac.render_text(ctx)
        assert "outdoor   Berdorf" not in txt
        assert "Derivato dagli esiti" not in txt
        assert "custom_cs_" not in txt  # names still come from the plan copies in ctx


# --------------------------------------------------------------------------- #
# 3. limit log
# --------------------------------------------------------------------------- #

class TestLimitLog:
    def test_section_present_when_empty(self):
        _ctx, txt = _render()
        assert "## Limit log" in txt
        assert "nessuna sessione al limite registrata" in _section(txt, "## Limit log")

    def test_entries_rendered(self):
        st = _with_crag_days(_state())
        st["limit_log"] = [{
            "date": "2026-10-01", "source": "planned", "surface": "board_kilter", "session_id": "power_contact_gym",
            "exercise_id": "system_board_limit", "target_grade": "7A+", "next_target_grade": "7B", "step": 0,
            "step_reason": "progress_at_target", "qualifies": False,
            "problems": [{"name": "A", "grade": "7B", "outcome": "sent", "attempts": 4},
                         {"name": "B", "grade": "7B", "outcome": "no_progress", "attempts": 3}],
        }]
        _ctx, txt = _render(st)
        sec = _section(txt, "## Limit log")
        assert "2026-10-01 planned board_kilter system_board_limit: obiettivo 7A+ → 2 problemi, 1 chiusi" in sec
        assert "prossimo obiettivo 7B" in sec and "non qualifica" in sec


# --------------------------------------------------------------------------- #
# 4. try-hard fallback from attempt results
# --------------------------------------------------------------------------- #

def _isatis_rows():
    return [{"entry": {"date": "2026-10-03", "spot_name": "Berdorf", "discipline": "lead", "routes": [
        {"name": "Warmup", "grade": "6b", "attempts": [{"result": "sent"}]},
        {"name": "Isatis", "grade": "8a", "style": "project",
         "attempts": [{"result": "topped_out"}, {"result": "fell"}]},
    ]}}]


class TestTryHardFallback:
    def test_formal_count_zero_but_derived_line_present(self):
        ctx, txt = _render(rows=_isatis_rows())
        assert ctx["try_hard"]["logged_attempts"] == 0          # the formal count is untouched
        sec = _section(txt, "## Try-hard")
        assert "nessun tentativo loggato nel formato" in sec
        assert "Derivato dagli esiti (non nel formato)" in sec
        assert "SEND 0 · FALL 1 · TOPPED_OUT 1" in sec and "50.0%" in sec
        assert "Isatis 8a ×2" in sec
        assert "Warmup" not in sec                              # below RP−2

    def test_formal_and_derived_kept_separate(self):
        ctx, txt = _render()  # _outdoor() has the note format AND a fell result
        assert ctx["try_hard"]["logged_attempts"] == 3
        sec = _section(txt, "## Try-hard")
        assert "SEND 0 · FALL 1 · TAKE 1 · LET_GO 1" in sec
        assert "Derivato dagli esiti" in sec

    def test_no_redpoint_no_fallback(self):
        st = _with_crag_days(_state())
        st["goal"] = {**st["goal"], "current_grade": None}
        assert ac.tryhard_from_results(st, TODAY, _isatis_rows()) is None

    def test_outside_window_not_counted(self):
        rows = _isatis_rows()
        rows[0]["entry"]["date"] = "2026-08-01"
        out = ac.tryhard_from_results(_state(), TODAY, rows)
        assert out is not None and out["attempts"] == 0


# --------------------------------------------------------------------------- #
# build stays as it was (no new heavy code per coach turn)
# --------------------------------------------------------------------------- #

def test_build_ctx_has_no_render_only_views():
    ctx = ac.build_athlete_context(_with_crag_days(_state()), TODAY, outdoor_rows=_outdoor())
    assert "planned_outdoor" not in ctx and "try_hard_derived" not in ctx
    assert set(ctx["try_hard"]) == {"source", "window_start", "counts", "logged_attempts", "fall_pct_of_non_send"}


def test_cli_text_passes_state_to_render(tmp_path, capsys):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import athlete_context as cli  # noqa: E402

    st = tmp_path / "state.json"
    st.write_text(json.dumps({"state": _with_crag_days(_state())}), encoding="utf-8")
    od = tmp_path / "outdoor.json"
    od.write_text(json.dumps(_isatis_rows()), encoding="utf-8")
    rc = cli.main(["--state-file", str(st), "--outdoor-file", str(od), "--date", TODAY])
    out = capsys.readouterr().out
    assert rc == cli.EXIT_OK
    assert "custom_cs_" not in out
    assert "2026-10-10 outdoor   Berdorf" in out
    assert "## Limit log" in out
    assert "Derivato dagli esiti (non nel formato)" in out
