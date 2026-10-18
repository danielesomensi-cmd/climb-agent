"""B395 — athlete_context flags planned customs whose stored tags are stale.

``add_custom_session`` derives a custom's tags once, at insertion. The 18/10
custom was added 34 min before B392 fixed the warm-up rule and kept
``finger: True`` («Finger gap», «NO dita max» on 19/10) until it was removed
and re-added by hand. Rule changes are rare, so nothing re-derives the tags:
the context makes the drift visible where a session is composed.
"""

from __future__ import annotations

from copy import deepcopy

from backend.engine import athlete_context as ac
from backend.tests.test_a293_athlete_context import TODAY, _outdoor, _sess, _state

_TECHNIQUE = [{"exercise_id": "warmup_easy_boulders"}, {"exercise_id": "small_feet_press_hold"},
              {"exercise_id": "no_readjust_drill"}, {"exercise_id": "dip"},
              {"exercise_id": "half_windshield_wiper"}]  # the 18/10 prod shape: hard from dip + wiper
_STALE = {"hard": True, "finger": True}     # what the replanner stored before B392
_CURRENT = {"hard": True, "finger": False}  # what derive_session_tags says now


def _with(*sessions_by_date) -> dict:
    st = deepcopy(_state())
    days = {d["date"]: d for wp in st["week_plans"].values() for w in wp["weeks"] for d in w["days"]}
    for date_iso, sess in sessions_by_date:
        days[date_iso]["sessions"].append(sess)
    return st


def _custom(status="planned", tags=None, exercises=_TECHNIQUE, sid="custom_cs_tech", **kw):
    if exercises is not None:
        kw["exercises"] = exercises
    return _sess("evening", sid, status, is_custom=True, name="Tecnica piedi", session_mode="custom_build",
                 tags=dict(tags if tags is not None else _STALE), **kw)


def _ctx(state):
    return ac.build_athlete_context(state, TODAY, outdoor_rows=_outdoor())


def _codes(ctx):
    return [w for w in ctx["warnings"] if w["code"] == "STALE_CUSTOM_TAGS"]


def test_planned_custom_with_stale_finger_tag_is_flagged():
    ctx = _ctx(_with(("2026-10-06", _custom())))
    rows = [r for r in ctx["stale_custom_tags"] if r["session_id"] == "custom_cs_tech"]
    assert rows == [{"date": "2026-10-06", "slot": "evening", "session_id": "custom_cs_tech",
                     "name": "Tecnica piedi", "status": "planned", "stored": _STALE, "current": _CURRENT}]
    [w] = _codes(ctx)
    assert "finger True→False" in w["message"] and "hard" not in w["message"].split("(")[1].split(")")[0]


def test_render_shows_the_warning_by_name():
    st = _with(("2026-10-06", _custom()))
    st["custom_sessions"] = [{"id": "cs_tech", "name": "Tecnica piedi", "exercises": _TECHNIQUE}]
    txt = ac.render_text(_ctx(st), state=st, outdoor_rows=_outdoor())
    avvisi = txt[txt.index("## Avvisi"):]
    assert "[STALE_CUSTOM_TAGS]" in avvisi and "Tecnica piedi" in avvisi and "custom_cs_tech" not in avvisi


def test_matching_tags_are_not_flagged():
    assert _ctx(_with(("2026-10-06", _custom(tags=_CURRENT))))["stale_custom_tags"] == []


def test_baseline_fixture_has_no_stale_custom():
    assert _ctx(_state())["stale_custom_tags"] == []


def test_done_and_skipped_customs_are_ignored():
    """Past sessions are immutable: nothing to realign there."""
    st = _with(("2026-10-04", _custom(status="done", sid="custom_cs_done")),
               ("2026-10-06", _custom(status="skipped", sid="custom_cs_skip")))
    assert _ctx(st)["stale_custom_tags"] == []


def test_exercises_fall_back_to_the_custom_sessions_pool():
    st = _with(("2026-10-06", _custom(exercises=None)))
    st["custom_sessions"] = [{"id": "cs_tech", "name": "Tecnica piedi", "exercises": _TECHNIQUE}]
    assert [r["current"] for r in _ctx(st)["stale_custom_tags"]] == [_CURRENT]


def test_custom_without_exercises_anywhere_is_not_judged():
    assert _ctx(_with(("2026-10-06", _custom(exercises=None))))["stale_custom_tags"] == []


def test_generated_sessions_are_out_of_scope():
    """add_planned_session / generated: declared tags merge upward, more is legitimate."""
    gen = _sess("evening", "generated_body_part_2026-10-06_evening", "planned", is_custom=True,
                tags=dict(_STALE), exercises=_TECHNIQUE)
    assert _ctx(_with(("2026-10-06", gen)))["stale_custom_tags"] == []


def test_window_is_the_upcoming_fourteen_days():
    st = _with(("2026-10-03", _custom(sid="custom_cs_yesterday")))
    assert _ctx(st)["stale_custom_tags"] == []


def test_state_is_not_mutated():
    st = _with(("2026-10-06", _custom()))
    before = deepcopy(st)
    _ctx(st)
    assert st == before
