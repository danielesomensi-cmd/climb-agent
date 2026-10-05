"""A297 (R7b) — the athlete context in the in-app coach and ad-hoc composer.

Pinned here:

- the engine renderers (``render_coach_block`` / ``render_composer_block``):
  English, neutral (no internal brief ids, no "fallback"), within budget, built
  only from computed data (official maxima with the COMPUTED confidence,
  anchored loads, pain, key sessions, guards, retest, limit log, variety);
- the deterministic guard of the session day (``composer_guard_view`` /
  ``drop_heavy_pulls``): finger-hard and front-lever lines leave the pool on a
  guarded day, a weighted pull ≥ 85 % 1RM at the model's reps is dropped with
  the reason, an untested athlete is not verifiable and keeps the line;
- the LLM composer: ``ATHLETE CONTEXT`` after the request, the context rules
  in the system prompt, ``intensity=`` / ``[ANCHOR]`` / ``[OVERUSED]`` pool
  markers, ``today`` reaching the anchored loads; with no context (flag off)
  the prompt is byte-identical to the pre-A297 one;
- the deterministic builder: recency from the variety collector only
  penalises, an anchor is held out only inside 48 h, deterministic;
- the coach chat prompt: ONE ``## Athlete context`` block replaces the A294 key
  block and the B364 lines of the baselines; flag off or a failed build → the
  pre-A297 sections;
- the service: ``COACH_ATHLETE_CONTEXT=0`` passes nothing new to either
  composer.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import date, timedelta
from unittest import mock

import pytest

from backend.coach import athlete_block, prompt_builder, service, session_composer
from backend.engine import adhoc_builder
from backend.engine import athlete_context as ac
from backend.engine.adhoc_prescription import effort_band_for, effort_band_for_phase
from backend.tests.test_a293_athlete_context import TODAY, _outdoor, _state

EQUIPMENT = {"home": ["pullup_bar", "hangboard", "dumbbell", "band", "weight"], "home_enabled": True}
GUARDED_DAY = TODAY            # Sunday 04/10: limit_boulder_gym on Monday → finger + pull guarded
FREE_DAY = "2026-10-21"        # power_endurance, no planned session around it

_ITALIAN = re.compile(r"\b(dita|settimana|giorno|tirata|sessione|massimale|pianificate|fatte)\b", re.IGNORECASE)


def _st(**over):
    st = _state(equipment=deepcopy(EQUIPMENT))
    st.update(over)
    return st


def _ctx(state=None, day=TODAY, **kw):
    kw.setdefault("outdoor_rows", _outdoor())
    kw.setdefault("include_next_week", False)
    return ac.build_athlete_context(state if state is not None else _st(), day, **kw)


@pytest.fixture(scope="module")
def catalog():
    return ac.load_exercise_catalog()


# ---------------------------------------------------------------------------
# Context additions
# ---------------------------------------------------------------------------

class TestContextAdditions:
    def test_version_and_new_sections(self):
        ctx = _ctx()
        assert ctx["version"] == ac.VERSION  # C272 bumped it (new read-only sections)
        assert "load_flags" in ctx and "limit_log" in ctx
        assert set(ctx["load_flags"]) == {"pain", "fatigue"}

    def test_guard_rows_carry_language_neutral_codes(self):
        row = ac.day_guard(_ctx(), GUARDED_DAY)
        assert row is not None and not row["finger_max_ok"] and not row["heavy_pull_ok"]
        codes = {c["code"] for c in row["finger_codes"]}
        assert "finger_hard_adjacent" in codes
        assert "pre_limit" in {c["code"] for c in row["pull_codes"]}
        # one code per Italian reason, never fewer
        assert len(row["finger_codes"]) == len(row["finger_reasons"])
        assert len(row["pull_codes"]) == len(row["pull_reasons"])

    def test_variety_exercise_last_date_uses_actual_exercises(self):
        v = _ctx()["variety"]
        # the 04/10 custom: actual_exercises (toes_to_bar), never the planned dead_bug
        assert v["exercise_last_date"]["toes_to_bar"] == "2026-10-04"
        assert "dead_bug" not in v["exercise_last_date"]
        assert v["exercise_last_date"]["weighted_pullup"] == "2026-10-04"

    def test_pain_block_is_read_from_the_a295_counters(self):
        st = _st(progression_counters={"pain_blocks": {
            "fingers": {"from": "2026-10-01", "until": "2026-10-08", "score": 2}}})
        lf = _ctx(st)["load_flags"]
        assert lf["pain"]["finger"]["score"] == 2 and lf["pain"]["finger"]["site"] == "fingers"
        assert "pulling" not in lf["pain"]

    def test_limit_log_view_newest_first_summarised(self):
        st = _st(limit_log=[
            {"date": "2026-09-28", "session_id": "limit_boulder_gym", "exercise_id": "limit_bouldering",
             "surface": "gym_boulder", "target_grade": "7A+", "source": "planned", "next_target_grade": "7A+",
             "problems": [{"grade": "7A+", "attempts": 4, "outcome": "high_point"}]},
            {"date": "2026-10-01", "session_id": "limit_boulder_gym", "exercise_id": "limit_bouldering",
             "surface": "gym_boulder", "target_grade": "7A+", "source": "planned", "next_target_grade": "7B",
             "problems": [{"grade": "7A+", "attempts": 3, "outcome": "sent"},
                          {"grade": "7A+", "attempts": 2, "outcome": "sent"}]},
        ])
        rows = _ctx(st)["limit_log"]
        assert [r["date"] for r in rows] == ["2026-10-01", "2026-09-28"]
        assert rows[0]["sent"] == 2 and rows[0]["best_sent"] == "7A+" and rows[0]["next_target_grade"] == "7B"
        assert "problems" in rows[0] and isinstance(rows[0]["problems"], int)

    def test_light_build_skips_proposals_and_next_week(self):
        ctx = _ctx(with_proposals=False, include_next_week=False)
        assert ctx["key_sessions_next_week"] is None
        assert ctx["key_sessions"].get("proposals") in ([], None)

    def test_default_build_unchanged_for_the_cli(self):
        ctx = ac.build_athlete_context(_st(), TODAY, outdoor_rows=_outdoor())
        assert ctx["key_sessions_next_week"] is not None


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

class TestCoachBlock:
    def test_english_neutral_within_budget(self):
        text = ac.render_coach_block(_ctx())
        assert text.startswith("## Athlete context")
        assert len(text) <= ac.COACH_BLOCK_MAX_CHARS
        assert not _ITALIAN.search(text), _ITALIAN.search(text)
        for internal in ("fallback", "A294", "B364", "R5", "A297", "source:"):
            assert internal not in text

    def test_official_max_with_computed_confidence_not_the_stored_one(self):
        text = ac.render_coach_block(_ctx())
        line = next(l for l in text.splitlines() if l.startswith("- max hang 7s"))
        assert "116 kg total" in line and "tested 2026-09-24" in line
        # stored "high" is ignored: no exposures in the 21 days before the test
        assert "confidence low" in line

    def test_anchored_loads_verbatim_from_anchored_load(self):
        from backend.engine.anchored_load import anchored_load

        st = _st()
        anch = anchored_load(st, "weighted_pullup", date=TODAY)
        text = ac.render_coach_block(_ctx(st))
        line = next(l for l in text.splitlines() if l.startswith("- weighted_pullup:"))
        assert f"{anch['rep_scheme']} at +{ac._fmt_kg(anch['external'])} kg" in line

    def test_key_sessions_and_guards_present(self):
        text = ac.render_coach_block(_ctx())
        assert "Key sessions this week" in text
        assert "Recovery guards for the next days" in text
        assert f"- {GUARDED_DAY} sun: no max finger work" in text

    def test_untested_athlete_has_no_maxima_or_loads(self):
        st = _st(tests={})
        text = ac.render_coach_block(_ctx(st))
        assert "Official maxima" not in text and "Training loads today" not in text

    def test_budget_cut_drops_whole_lines_from_the_end(self):
        full = ac.render_coach_block(_ctx())
        cut = ac.render_coach_block(_ctx(), max_chars=600)
        assert len(cut) <= 600
        assert full.startswith(cut)
        assert cut.splitlines()[0].startswith("## Athlete context")

    def test_no_macrocycle_does_not_crash(self):
        text = ac.render_coach_block(ac.build_athlete_context({}, TODAY))
        assert "No active macrocycle" in text


class TestComposerBlock:
    def test_guarded_day_says_what_and_why(self):
        st = _st()
        text = ac.render_composer_block(_ctx(st), state=st, day=GUARDED_DAY)
        assert text.startswith("ATHLETE CONTEXT")
        assert len(text) <= ac.COMPOSER_BLOCK_MAX_CHARS
        assert "NO max finger work" in text and "NO pulling at ≥85% 1RM" in text
        assert "Level:" not in text  # the fixture declares no grades: nothing is invented
        st["assessment"] = {"grades": {"lead_max_rp": "8a+", "boulder_max_rp": "7C"}}
        assert "- Level: lead RP 8a+, boulder RP (Font) 7C." in ac.render_composer_block(
            _ctx(st), state=st, day=GUARDED_DAY)
        assert not _ITALIAN.search(text)

    def test_free_day_has_no_restriction(self):
        st = _st()
        text = ac.render_composer_block(_ctx(st, FREE_DAY), state=st, day=FREE_DAY)
        assert "no finger / pulling restriction" in text

    def test_overused_and_anchor_hint(self):
        st = _st()
        ctx = _ctx(st)
        ctx["variety"]["overused"] = ["core_anti_rotation"]
        text = ac.render_composer_block(ctx, state=st, day=GUARDED_DAY)
        assert "[ANCHOR]" in text and "core_anti_rotation" in text


# ---------------------------------------------------------------------------
# Guard view
# ---------------------------------------------------------------------------

class TestGuardView:
    def test_guarded_day_excludes_finger_hard_and_front_lever(self, catalog):
        st = _st()
        v = ac.composer_guard_view(st, _ctx(st), GUARDED_DAY, catalog)
        assert not v["finger_max_ok"] and not v["heavy_pull_ok"]
        assert {"horst_7_53", "limit_bouldering", "campus_max_ladders"} <= set(v["exclude_ids"])
        assert {"front_lever_tuck", "front_lever_straddle"} <= set(v["exclude_ids"])
        assert v["heavy_pull_check"] is True
        assert any(d.startswith("guard: max finger work left out") for d in v["dropped"])
        assert any(d.startswith("guard: front lever left out") for d in v["dropped"])
        # weighted pulls stay in the LLM pool (checked at the model's reps)
        assert "weighted_pullup" not in v["exclude_ids"]

    def test_free_day_is_neutral(self, catalog):
        st = _st()
        v = ac.composer_guard_view(st, _ctx(st, FREE_DAY), FREE_DAY, catalog)
        assert v["finger_max_ok"] and v["heavy_pull_ok"]
        assert v["exclude_ids"] == [] and v["dropped"] == []

    def test_no_context_or_day_outside_horizon_is_neutral(self, catalog):
        st = _st()
        assert ac.composer_guard_view(st, None, TODAY, catalog)["exclude_ids"] == []
        far = (date.fromisoformat(TODAY) + timedelta(days=40)).isoformat()
        assert ac.composer_guard_view(st, _ctx(st), far, catalog)["day"] is None

    def test_builder_also_drops_a_weighted_pull_at_85_percent(self, catalog):
        st = _st()
        ctx = _ctx(st)
        v = ac.composer_guard_view(st, ctx, GUARDED_DAY, catalog)
        pct = ac.heavy_pull_pct(st, "weighted_pullup", GUARDED_DAY)
        assert ("weighted_pullup" in v["builder_exclude_ids"]) == (pct is not None and pct >= 0.85)

    def test_drop_heavy_pulls_at_the_models_reps(self, catalog):
        st = _st()
        v = ac.composer_guard_view(st, _ctx(st), GUARDED_DAY, catalog)
        heavy = ac.heavy_pull_pct(st, "weighted_pullup", GUARDED_DAY, sets=3, reps=1)
        assert heavy is not None and heavy >= 0.85  # fixture sanity: 1-rep sets are heavy
        exercises = [{"exercise_id": "weighted_pullup", "sets": 3, "reps": 1},
                     {"exercise_id": "pushup", "sets": 3, "reps": 10}]
        dropped = ac.drop_heavy_pulls(st, exercises, v)
        assert [e["exercise_id"] for e in exercises] == ["pushup"]
        assert dropped and "weighted_pullup: guard" in dropped[0] and "1RM" in dropped[0]

    def test_drop_heavy_pulls_keeps_moderate_and_untested(self, catalog):
        st = _st()
        v = ac.composer_guard_view(st, _ctx(st), GUARDED_DAY, catalog)
        moderate = [{"exercise_id": "weighted_pullup", "sets": 3, "reps": 8}]
        assert ac.heavy_pull_pct(st, "weighted_pullup", GUARDED_DAY, sets=3, reps=8) < 0.85
        assert ac.drop_heavy_pulls(st, moderate, v) == [] and len(moderate) == 1
        untested = _st(tests={})
        heavy = [{"exercise_id": "weighted_pullup", "sets": 3, "reps": 1}]
        assert ac.drop_heavy_pulls(untested, heavy, v) == [] and len(heavy) == 1

    def test_no_guard_uses_the_load_score(self):
        import inspect

        src = inspect.getsource(ac.composer_guard_view) + inspect.getsource(ac.drop_heavy_pulls)
        assert "load_score" not in src


# ---------------------------------------------------------------------------
# Effort band
# ---------------------------------------------------------------------------

class TestEffortBand:
    def test_unguarded_medium_energy_equals_phase_band(self):
        assert effort_band_for("strength_power", "medium", {"finger_max_ok": True, "heavy_pull_ok": True}) \
            == effort_band_for_phase("strength_power")

    def test_guard_and_low_energy_are_named(self):
        band = effort_band_for("strength_power", "low", {"finger_max_ok": False, "heavy_pull_ok": False})
        assert band.startswith(effort_band_for_phase("strength_power"))
        assert "fingers and heavy pulling submaximal today" in band and "low energy" in band

    def test_no_phase_no_band(self):
        assert effort_band_for(None, "low", {}) is None


# ---------------------------------------------------------------------------
# LLM composer
# ---------------------------------------------------------------------------

def _proposal(ids, reps=8):
    return {"name": "Test", "rationale": "ok",
            "exercises": [{"exercise_id": i, "sets": 3, "reps": reps, "rest_between_sets_seconds": 60}
                          for i in ids]}


class TestComposer:
    INTENT = {"equipment_set": "home", "focus": "pull", "minutes": 30, "energy": "medium"}

    def _run(self, state, catalog, proposal, **kw):
        calls = []

        def fake_extract(system, content, tool):
            calls.append((system, content))
            return proposal

        with mock.patch.object(session_composer, "ENABLED", True), \
                mock.patch.object(session_composer.llm_client, "extract", side_effect=fake_extract):
            out = session_composer.compose("pull session", dict(self.INTENT), state, catalog, **kw)
        return out, calls

    def _filler(self, state, catalog, n=4):
        pool = session_composer.build_pool(self.INTENT, state, catalog)
        return [e["id"] for e in pool if e["id"].startswith(("bicep", "pushup", "bench", "barbell"))][:n]

    def test_flag_off_prompt_is_pre_a297(self, catalog):
        st = _st()
        out, calls = self._run(st, catalog, _proposal(self._filler(st, catalog)))
        system, content = calls[0]
        assert system == session_composer._SYSTEM
        assert "ATHLETE CONTEXT" not in content and "intensity=" not in content and "[ANCHOR]" not in content
        assert "athlete_context_version" not in out and "athlete_guards" not in out

    def test_pool_line_without_markers_is_unchanged(self, catalog):
        ex = catalog["weighted_pullup"]
        assert session_composer._pool_line(ex) == session_composer._pool_line(ex, None)
        assert "intensity=" not in session_composer._pool_line(ex)

    def test_context_after_request_rules_and_markers(self, catalog):
        st = _st()
        ctx = _ctx(st, FREE_DAY)
        ctx["variety"]["overused"] = ["pullup_variants"]
        ctx["variety"]["groups"].append({"group": "pullup_variants", "count": 4})
        out, calls = self._run(st, catalog, _proposal(self._filler(st, catalog)), today=FREE_DAY, athlete_ctx=ctx)
        system, content = calls[0]
        assert ac.athlete_is_tested(ctx)
        assert system == (session_composer._SYSTEM + session_composer._SYSTEM_CONTEXT_RULES
                          + session_composer._SYSTEM_CONTEXT_INTENSITY_RULES)
        assert content.index("ATHLETE REQUEST") < content.index("ATHLETE CONTEXT") < content.index("EXERCISE POOL")
        wp = next(l for l in content.splitlines() if l.startswith("weighted_pullup |"))
        assert "intensity=" in wp and "[ANCHOR]" in wp
        assert any("[OVERUSED 4x]" in l for l in content.splitlines() if l.startswith("pullup |"))
        assert out["athlete_context_version"] == ac.VERSION  # C272 bumped it (new read-only sections)
        assert out["athlete_guards"]["finger_max_ok"] is True

    def test_guarded_day_pool_and_dropped(self, catalog):
        st = _st()
        ctx = _ctx(st, GUARDED_DAY)
        ids = ["weighted_pullup"] + self._filler(st, catalog)
        out, calls = self._run(st, catalog, _proposal(ids, reps=1), today=GUARDED_DAY, athlete_ctx=ctx)
        content = calls[0][1]
        pool_ids = {l.split(" | ")[0] for l in content.splitlines() if " | " in l}
        assert "horst_7_53" not in pool_ids and "front_lever_tuck" not in pool_ids
        assert "weighted_pullup" in pool_ids
        assert out is not None
        assert "weighted_pullup" not in [e["exercise_id"] for e in out["exercises"]]
        assert any(d.startswith("weighted_pullup: guard") for d in out["dropped"])
        assert any(d.startswith("guard: max finger work left out") for d in out["dropped"])
        assert out["athlete_guards"] == {"day": GUARDED_DAY, "finger_max_ok": False, "heavy_pull_ok": False,
                                         "hiit_ok": out["athlete_guards"]["hiit_ok"],
                                         "reasons": out["athlete_guards"]["reasons"]}
        assert "submaximal today" in out["effort_band"]

    def test_today_reaches_the_anchored_load(self, catalog):
        st = _st()
        ctx = _ctx(st, FREE_DAY)
        seen = []
        import backend.engine.anchored_load as al

        real = al.anchored_load

        def spy(state, exercise_id, **kw):
            seen.append((exercise_id, kw.get("date"), kw.get("session_exercise_ids")))
            return real(state, exercise_id, **kw)

        with mock.patch.object(al, "anchored_load", side_effect=spy):
            self._run(st, catalog, _proposal(["weighted_pullup"] + self._filler(st, catalog), reps=5),
                      today=FREE_DAY, athlete_ctx=ctx)
        deco = [s for s in seen if s[0] == "weighted_pullup" and s[2]]
        assert deco and deco[-1][1] == FREE_DAY
        assert "weighted_pullup" in deco[-1][2]


# ---------------------------------------------------------------------------
# Deterministic builder
# ---------------------------------------------------------------------------

class TestBuilder:
    INTENT = {"equipment_set": "home", "focus": "pull", "minutes": 45, "energy": "medium"}

    def test_no_context_unchanged(self, catalog):
        st = _st()
        a = adhoc_builder.compose_adhoc_session(dict(self.INTENT), st, catalog, today=FREE_DAY)
        b = adhoc_builder.compose_adhoc_session(dict(self.INTENT), st, catalog, today=FREE_DAY, athlete_ctx=None)
        assert a == b
        assert "athlete_guards" not in a and "dropped" not in a

    def test_deterministic_with_context(self, catalog):
        st = _st()
        ctx = _ctx(st, FREE_DAY)
        a = adhoc_builder.compose_adhoc_session(dict(self.INTENT), st, catalog, today=FREE_DAY, athlete_ctx=ctx)
        b = adhoc_builder.compose_adhoc_session(dict(self.INTENT), st, catalog, today=FREE_DAY, athlete_ctx=ctx)
        assert a == b and a["athlete_context_version"] == ac.VERSION  # C272 bumped it (new read-only sections)

    def test_anchor_held_out_only_inside_48h(self, catalog):
        st = _st()
        ctx = _ctx(st, FREE_DAY)
        intent = {**self.INTENT, "body_parts": [], "focus": "pull"}
        ctx["variety"]["exercise_last_date"] = {"weighted_pullup": "2026-10-20"}  # yesterday
        a = adhoc_builder.compose_adhoc_session(dict(intent), st, catalog, today=FREE_DAY, athlete_ctx=ctx)
        assert "weighted_pullup" not in [e["exercise_id"] for e in a["exercises"]]
        ctx["variety"]["exercise_last_date"] = {"weighted_pullup": "2026-10-18"}  # 3 days ago
        rank_old = adhoc_builder._rank_key_ctx(catalog["weighted_pullup"], "power_endurance", 3, 3)
        rank_never = adhoc_builder._rank_key_ctx(catalog["weighted_pullup"], "power_endurance", 3, 9999)
        assert rank_never < rank_old  # recency penalises, never excludes

    def test_recent_accessory_penalised_not_excluded(self, catalog):
        recent = {"id": "aaa", "intensity_level": "high"}
        fresh = {"id": "zzz", "intensity_level": "high"}
        ranked = sorted([recent, fresh], key=lambda e: adhoc_builder._rank_key_ctx(
            e, None, 3, 1 if e["id"] == "aaa" else adhoc_builder.NEVER_USED_DAYS))
        assert [e["id"] for e in ranked] == ["zzz", "aaa"]

    def test_intensity_gap_ranks_before_recency(self):
        low = {"id": "a_low", "intensity_level": "low"}
        high = {"id": "z_high", "intensity_level": "high"}
        target = adhoc_builder.target_intensity("strength_power", "medium")
        ranked = sorted([low, high], key=lambda e: adhoc_builder._rank_key_ctx(e, "strength_power", target, 9999))
        assert ranked[0]["id"] == "z_high"
        assert adhoc_builder.target_intensity("strength_power", "low") == 2
        assert adhoc_builder.target_intensity("deload", "low") == 0

    def test_guarded_day_builder_never_picks_finger_hard(self, catalog):
        st = _st()
        ctx = _ctx(st, GUARDED_DAY)
        intent = {**self.INTENT, "focus": "fingers"}
        out = adhoc_builder.compose_adhoc_session(dict(intent), st, catalog, today=GUARDED_DAY, athlete_ctx=ctx)
        ids = {e["exercise_id"] for e in out["exercises"]}
        assert not (ids & set(ac.composer_guard_view(st, ctx, GUARDED_DAY, catalog)["exclude_ids"]))
        assert out["athlete_guards"]["finger_max_ok"] is False
        assert any(d.startswith("guard: max finger work left out") for d in out["dropped"])


# ---------------------------------------------------------------------------
# Coach chat prompt
# ---------------------------------------------------------------------------

class TestChatPrompt:
    def _ctx_text(self, monkeypatch, state, flag="1"):
        monkeypatch.setenv("COACH_ATHLETE_CONTEXT", flag)
        monkeypatch.setattr(athlete_block, "_outdoor_rows", lambda uid, d: _outdoor())
        monkeypatch.setattr(athlete_block, "_archived_weeks", lambda st, uid, d: None)
        return prompt_builder.build_user_context(state, None)

    def test_single_block_replaces_key_section_and_b364_lines(self, monkeypatch):
        text = self._ctx_text(monkeypatch, _st())
        assert text.count("## Athlete context") == 1
        assert "## Key sessions this week" not in text
        assert "- Official max " not in text
        assert "training load today" not in text  # the anchored line of the baselines moved to the block

    def test_flag_off_pre_a297_sections(self, monkeypatch):
        called = []
        monkeypatch.setattr(athlete_block, "chat_block", lambda *a, **k: called.append(1) or "X")
        text = self._ctx_text(monkeypatch, _st(), flag="0")
        assert not called
        assert "## Athlete context" not in text and "## Key sessions this week" not in text
        assert "- Official max max hang 7s 20mm" in text

    def test_failed_build_falls_back_to_pre_a297_sections(self, monkeypatch):
        monkeypatch.setattr(athlete_block, "chat_block", lambda *a, **k: None)
        monkeypatch.setenv("COACH_ATHLETE_CONTEXT", "1")
        text = prompt_builder.build_user_context(_st(), None)
        assert "## Athlete context" not in text
        assert "- Official max max hang 7s 20mm" in text

    def test_only_literal_zero_disables(self, monkeypatch):
        for value, expected in (("0", False), ("false", True), ("", True), ("1", True)):
            monkeypatch.setenv("COACH_ATHLETE_CONTEXT", value)
            assert athlete_block.enabled() is expected
            assert prompt_builder.coach_athlete_context_enabled() is expected

    def test_build_failure_returns_none(self, monkeypatch):
        monkeypatch.setenv("COACH_ATHLETE_CONTEXT", "1")
        with mock.patch("backend.engine.athlete_context.build_athlete_context", side_effect=RuntimeError("x")):
            assert athlete_block.chat_block(_st(), None, TODAY) is None
            assert athlete_block.composer_context(_st(), None, TODAY) is None

    def test_archived_weeks_read_only_when_a_week_is_cold(self, monkeypatch):
        reads = []
        monkeypatch.setattr("backend.engine.storage.read_archived_weeks_in_range",
                            lambda uid, a, b: reads.append((a, b)) or {})
        st = _st()
        athlete_block._archived_weeks(st, None, date.fromisoformat(TODAY))
        assert reads  # weeks before 21/09 are not hot in the fixture
        # Look-back 90 + 21 + 7 = 118 d, Monday-aligned: 08/06 → 28/09 (17 weeks).
        hot = {(date(2026, 6, 8) + timedelta(days=7 * k)).isoformat(): {} for k in range(17)}
        reads.clear()
        athlete_block._archived_weeks({"week_plans": hot}, None, date.fromisoformat(TODAY))
        assert not reads


# ---------------------------------------------------------------------------
# Review fixes (2026-10-05)
# ---------------------------------------------------------------------------

def _stale_tests(st):
    """Every test of the fixture moved > TEST_FRESH_DAYS back."""
    import json as _json
    tests = _json.loads(_json.dumps(st.get("tests") or {}))
    for rows in tests.values():
        for t in rows if isinstance(rows, list) else []:
            if isinstance(t, dict) and t.get("date"):
                t["date"] = "2026-05-01"
    return tests


def _untested(st):
    st = deepcopy(st)
    st["tests"] = {}
    st["baselines"] = {}
    st["working_loads"] = {"entries": []}
    return st


class TestReviewFixes:
    INTENT = {"equipment_set": "home", "focus": "pull", "minutes": 60, "energy": "high"}

    def test_stale_max_stays_in_the_chat_block_flagged(self):
        st = _st()
        st["tests"] = _stale_tests(st)
        ctx = _ctx(st)
        assert any(m for m in ctx["maxima"].values()) and not ac.athlete_is_tested(ctx)
        text = ac.render_coach_block(ctx)
        assert "Official maxima" in text
        assert "stale or not a test" in text and "changes ONLY with a test" in text

    def test_pain_block_makes_the_day_no_max_and_is_named(self, catalog):
        st = _st(progression_counters={"pain_blocks": {
            "fingers": {"from": "2026-10-18", "until": "2026-11-01", "score": 3}}})
        ctx = _ctx(st, FREE_DAY)
        view = ac.composer_guard_view(st, ctx, FREE_DAY, catalog)
        assert view["finger_max_ok"] is False and view["pain_axes"] == ["finger"]
        assert {"max_hang_5s", "campus_bumps", "min_edge_hang"} <= set(view["exclude_ids"])
        assert "pain" in view["reasons"]["finger"]
        for focus, energy in (("pull", "low"), ("fingers", "high")):
            out = adhoc_builder.compose_adhoc_session(
                {**self.INTENT, "focus": focus, "energy": energy}, st, catalog, today=FREE_DAY, athlete_ctx=ctx)
            ids = {e["exercise_id"] for e in out["exercises"]}
            assert not (ids & set(view["exclude_ids"])), (focus, ids)
            assert "pain flag" in out["effort_band"]

    def test_pain_without_guard_row_still_applies(self, catalog):
        st = _st(progression_counters={"pain_blocks": {
            "fingers": {"from": "2026-10-01", "until": "2027-01-01", "score": 2}}})
        view = ac.composer_guard_view(st, {"guards": {"days": []}}, "2026-12-01", catalog)
        assert view["day"] == "2026-12-01" and view["finger_max_ok"] is False

    def test_no_heavy_pull_day_drops_max_bodyweight_pulls(self, catalog):
        st = _st()
        ctx = _ctx(st, GUARDED_DAY)
        view = ac.composer_guard_view(st, ctx, GUARDED_DAY, catalog)
        assert view["heavy_pull_ok"] is False
        assert "one_arm_pullup_assisted" in view["exclude_ids"]
        assert "pullup" not in view["exclude_ids"]  # moderate pulling stays
        out = adhoc_builder.compose_adhoc_session(dict(self.INTENT), st, catalog, today=GUARDED_DAY,
                                                  athlete_ctx=ctx)
        assert "one_arm_pullup_assisted" not in {e["exercise_id"] for e in out["exercises"]}

    @pytest.mark.parametrize("focus,energy", [("pull", "low"), ("pull", "high"),
                                              ("fingers", "high"), ("fingers", "low")])
    def test_finger_hard_capped_per_session(self, catalog, focus, energy):
        st = _st()
        ctx = _ctx(st, FREE_DAY)
        assert ac.athlete_is_tested(ctx)
        out = adhoc_builder.compose_adhoc_session({**self.INTENT, "focus": focus, "energy": energy},
                                                  st, catalog, today=FREE_DAY, athlete_ctx=ctx)
        hard = ac.finger_hard_session_ids(catalog)
        n = sum(1 for e in out["exercises"] if e["exercise_id"] in hard)
        cap = ac.MAX_FINGER_HARD_PER_SESSION_LOW_ENERGY if energy == "low" else ac.MAX_FINGER_HARD_PER_SESSION
        assert n <= cap

    def test_cap_finger_hard_llm_path(self, catalog):
        exs = [{"exercise_id": i} for i in ("campus_bumps", "max_hang_5s", "campus_touches", "pullup")]
        dropped = ac.cap_finger_hard(exs, catalog, "low")
        assert [e["exercise_id"] for e in exs] == ["campus_bumps", "pullup"]
        assert len(dropped) == 2

    def test_min_edge_hang_out_of_sp_for_hang_tested(self, catalog):
        st = _st()
        day = "2026-10-13"  # strength_power, no guard on the day
        ctx = _ctx(st, day)
        assert ctx["position"]["phase_id"] == "strength_power" and ac.day_guard(ctx, day)["finger_max_ok"]
        out = adhoc_builder.compose_adhoc_session({**self.INTENT, "focus": "fingers"}, st, catalog,
                                                  today=day, athlete_ctx=ctx)
        ids = [e["exercise_id"] for e in out["exercises"]]
        assert "min_edge_hang" not in ids
        assert sum(1 for i in ids if i in ac.finger_hard_session_ids(catalog)) <= ac.MAX_FINGER_HARD_PER_SESSION

    @pytest.mark.parametrize("focus,energy", [("pull", "high"), ("fingers", "high"),
                                              ("pull", "low"), ("general_strength", "medium")])
    def test_untested_builder_bit_for_bit(self, catalog, focus, energy):
        """DECISIONS (global): an untested athlete's ad-hoc selection is the
        pre-A297 one on a day without guards."""
        st = _untested(_st())
        ctx = _ctx(st, FREE_DAY)
        assert not ac.athlete_is_tested(ctx)
        assert ac.composer_guard_view(st, ctx, FREE_DAY, catalog)["exclude_ids"] == []
        intent = {**self.INTENT, "focus": focus, "energy": energy}
        on = adhoc_builder.compose_adhoc_session(dict(intent), st, catalog, today=FREE_DAY, athlete_ctx=ctx)
        off = adhoc_builder.compose_adhoc_session(dict(intent), st, catalog, today=FREE_DAY)
        assert on["exercises"] == off["exercises"]
        assert on["effort_band"] == off["effort_band"]
        assert on["explanation"] == off["explanation"]

    def test_untested_llm_prompt_has_no_intensity_rules(self, catalog):
        st = _untested(_st())
        ctx = _ctx(st, FREE_DAY)
        calls = []

        def fake_extract(system, content, tool):
            calls.append((system, content))
            return _proposal(["pullup", "bicep_curl", "pushup", "barbell_row"])

        with mock.patch.object(session_composer, "ENABLED", True), \
                mock.patch.object(session_composer.llm_client, "extract", side_effect=fake_extract):
            session_composer.compose("pull session", dict(TestComposer.INTENT), st, catalog,
                                     today=FREE_DAY, athlete_ctx=ctx)
        system, content = calls[0]
        assert system == session_composer._SYSTEM + session_composer._SYSTEM_CONTEXT_RULES
        assert "intensity=" not in content

    def test_archive_lookback_matches_week_and_cli(self, monkeypatch):
        from backend.api.routers import week as week_router

        assert athlete_block.ARCHIVE_LOOKBACK_D == week_router._RETEST_ARCHIVE_LOOKBACK_D
        reads = []
        monkeypatch.setattr("backend.engine.storage.read_archived_weeks_in_range",
                            lambda uid, a, b: reads.append((a, b)) or {})
        athlete_block._archived_weeks({"week_plans": {}}, None, date(2026, 10, 8))
        lo = date.fromisoformat(reads[0][0])
        assert lo.weekday() == 0 and (date(2026, 10, 8) - lo).days >= athlete_block.ARCHIVE_LOOKBACK_D


# ---------------------------------------------------------------------------
# Service wiring
# ---------------------------------------------------------------------------

class TestService:
    def _call(self, monkeypatch, flag):
        monkeypatch.setenv("COACH_ATHLETE_CONTEXT", flag)
        seen = {}

        def fake_compose(message, intent, state, catalog, **kw):
            seen["compose"] = kw
            return None

        def fake_builder(intent, state, catalog, **kw):
            seen["builder"] = kw
            return {"name": "S", "estimated_duration_minutes": 30, "explanation": "x", "exercises": []}

        monkeypatch.setattr(service, "_load_history", lambda uid: [])
        monkeypatch.setattr("backend.coach.adhoc_intent.extract_intent",
                            lambda msg, history=None: {"equipment_set": "home", "focus": "pull", "minutes": 30})
        monkeypatch.setattr("backend.api.deps.load_state", lambda uid: _st())
        monkeypatch.setattr("backend.coach.session_composer.compose", fake_compose)
        monkeypatch.setattr("backend.engine.adhoc_builder.compose_adhoc_session", fake_builder)
        monkeypatch.setattr(service, "_key_guard", lambda *a: {"exclude_ids": [], "warnings": []})
        monkeypatch.setattr(service.storage, "append_coach_message", lambda *a, **k: None)
        monkeypatch.setattr(athlete_block, "_outdoor_rows", lambda uid, d: [])
        monkeypatch.setattr(athlete_block, "_archived_weeks", lambda st, uid, d: None)
        service.handle_adhoc_compose(None, "pull session", target_date=GUARDED_DAY)
        return seen

    def test_flag_off_passes_nothing_new(self, monkeypatch):
        seen = self._call(monkeypatch, "0")
        assert seen["compose"] == {} and seen["builder"] == {}

    def test_flag_on_passes_the_day_and_the_context(self, monkeypatch):
        seen = self._call(monkeypatch, "1")
        for k in ("compose", "builder"):
            assert seen[k]["today"] == GUARDED_DAY
            assert seen[k]["athlete_ctx"]["as_of"] == GUARDED_DAY
            assert seen[k]["athlete_ctx"]["key_sessions"].get("proposals") in ([], None)
