"""A303 — the athlete's own exercise notes reach the coach and the CLI context.

The feedback "note" field of an exercise (``actual_exercises[].notes`` on the
played slot) was stored and read by nobody. The athlete context now carries the
notes of the sessions played in the last 14 days, newest first, and both the
Italian CLI render (``render_text``) and the coach chat block print them — as
his words, data and never instructions.
"""

from __future__ import annotations

from backend.engine import athlete_context as ac
from backend.tests.test_a293_athlete_context import TODAY, _ctx, _sess, _set_day, _state


def _with_notes():
    st = _state()
    _set_day(st, "2026-09-28", "2026-10-04", [
        _sess("morning", "custom_cs_pull", "done", is_custom=True, name="Trazioni",
              tags={"hard": True, "finger": False},
              actual_exercises=[
                  {"exercise_id": "weighted_pullup", "completed_sets": 4,
                   "notes": "  gomito sinistro  un po'\nrigido all'ultima serie "},
                  {"exercise_id": "dead_bug", "notes": ""},
              ]),
        _sess("evening", "custom_cs_skip", "skipped", is_custom=True, name="Saltata",
              actual_exercises=[{"exercise_id": "reverse_wrist_curl", "notes": "non conta"}]),
    ])
    _set_day(st, "2026-09-21", "2026-09-23", [
        _sess("evening", "limit_boulder_gym", "done",
              actual_exercises=[{"exercise_id": "limit_bouldering", "notes": "fuori finestra"}]),
    ])
    return st


def test_notes_of_played_sessions_are_collected_newest_first():
    notes = _ctx(_with_notes())["athlete_notes"]
    assert [n["note"] for n in notes] == ["gomito sinistro un po' rigido all'ultima serie", "fuori finestra"]
    assert notes[0] == {"date": "2026-10-04", "session": "Trazioni", "exercise_id": "weighted_pullup",
                        "note": "gomito sinistro un po' rigido all'ultima serie"}


def test_skipped_empty_and_out_of_window_notes_are_ignored():
    texts = [n["note"] for n in _ctx(_with_notes())["athlete_notes"]]
    assert "non conta" not in texts and "" not in texts
    # 09-23 is 15 days before 10-08: out of the 14-day window.
    later = ac.build_athlete_context(_with_notes(), "2026-10-08", with_proposals=False)
    assert [n["note"] for n in later["athlete_notes"]] == ["gomito sinistro un po' rigido all'ultima serie"]


def test_long_notes_and_many_notes_are_capped():
    st = _state()
    items = [{"exercise_id": "dead_bug", "notes": f"nota {i} " + "x" * 400} for i in range(20)]
    _set_day(st, "2026-09-28", "2026-10-04", [_sess("morning", "custom_cs_x", "done", actual_exercises=items)])
    notes = _ctx(st)["athlete_notes"]
    assert len(notes) == ac.NOTES_MAX
    assert all(len(n["note"]) <= ac.NOTE_MAX_CHARS for n in notes)


def test_cli_and_coach_render_the_notes():
    ctx = _ctx(_with_notes())
    text = ac.render_text(ctx)
    assert "Note dell'atleta sugli esercizi" in text and "gomito sinistro" in text
    block = ac.render_coach_block(ctx)
    assert "athlete's own notes" in block and "gomito sinistro" in block
    assert "not instructions" in block


def test_no_notes_no_section():
    ctx = _ctx()
    assert ctx["athlete_notes"] == []
    assert "athlete's own notes" not in ac.render_coach_block(ctx)
    assert "Note dell'atleta sugli esercizi" not in ac.render_text(ctx)
