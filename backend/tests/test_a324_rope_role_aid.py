"""A324 — who was on the sharp end (lead / second / top-rope) and the A0 result.

Real case (Daniele, 31/10 and 01/11/2026). Cancer at Presles is an 8-pitch
multi-pitch climbed on alternate leads: the pitches seconded clean had to be
logged ``fell`` with a note, because the app had no «clean on second» outcome,
and the pitches pulled on the gear (A0) had to be ``fell`` too. On 01/11 the
second burn on Cernes couleurs myrtille was on top-rope.

Two additions, no migration:

- ``attempts[].rope_role``: ``lead`` | ``second`` | ``toprope``; absent = lead,
  so every older log is unchanged (byte-identical, same load);
- ``attempts[].result: "aid"`` (A0, rope only).

One rule for every reader (``backend/engine/outdoor_attempt.py``): a send is
``sent`` on lead. A clean second / top-rope ascent is shown apart («Second
clean» / «TR clean»), never a send, a milestone or grade evidence.

Load (Daniele, 2026-11-02): attempt factor = rope-role factor (lead 1.0,
second / top-rope 0.85) × result factor, ``aid`` = 1.0 in both formulas.
31/10 Cancer 39 → 37, 01/11 La Crique 47 → 44.

Also here (B401 residual): PUT /api/outdoor/log keeps every top-level key of
the replaced entry that the request does not send — except ``routes`` and
``notes``, which the edit form owns (review: a pre-A324 form clears the notes
by leaving the key out). And (review) a rename or a per-crag delete re-syncs
the plan day: the gone crag leaves the label, the load is the remaining total.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.coach.prompt_builder import INSTRUCTION_BLOCK, _outdoor_log_line
from backend.engine import athlete_context as ac
from backend.engine import grade_evidence as ge
from backend.engine import key_sessions_v1 as ks
from backend.engine import milestones_v1
from backend.engine import outdoor_attempt as oa
from backend.engine import stimulus
from backend.engine.outdoor_log import (
    ROPE_ROLE_LOAD_FACTOR,
    carry_over_unsent_keys,
    compute_outdoor_load_score,
    compute_outdoor_stats,
    validate_outdoor_entry,
)
from backend.engine.report_engine import _build_highlights, _build_outdoor
from backend.tests.test_a293_athlete_context import TODAY, _state

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "backend" / "data" / "schemas" / "outdoor_session_entry.v1.json"

STATE = {"assessment": {"grades": {"lead_max_rp": "8a+", "boulder_max_rp": "7C"}}}

# --------------------------------------------------------------------------- #
# The real logs (Daniele, prod copy of 01/11, notes shortened)
# --------------------------------------------------------------------------- #

CANCER = "Cancer (Presles) – L"


def _pitch(n: int, grade: str, result: str, role: str | None = None, note: str = "") -> dict:
    attempt = {"result": result}
    if role:
        attempt["rope_role"] = role
    if note:
        attempt["notes"] = note
    return {"name": f"{CANCER}{n}", "grade": grade, "attempts": [attempt], "discipline": "lead"}


def cancer_today() -> dict:
    """31/10 as stored today: every pitch not led clean is `fell` with a note."""
    return {
        "date": "2026-10-31", "spot_name": "Presles – Chrysanthèmes (Vercors)",
        "discipline": "lead", "day_type": "volume", "log_version": "outdoor.v2",
        "load_ref_grade": "8a+", "duration_minutes": 480,
        "routes": [
            _pitch(1, "6a+", "fell", note="NON da primo: da secondo, pulito"),
            _pitch(2, "6c+", "fell", note="da primo, NON in libera"),
            _pitch(3, "6b+", "fell", note="NON da primo: da secondo, pulito"),
            _pitch(4, "6c", "sent", note="da primo, pulito"),
            _pitch(5, "7a+", "fell", note="NON da primo: da secondo, NON in libera"),
            _pitch(6, "6b", "sent", note="da primo, pulito"),
            _pitch(7, "6b+", "fell", note="NON da primo: da secondo, pulito"),
            _pitch(8, "7b", "fell", note="da primo, NON in libera (7b>6b A0)"),
        ],
    }


def cancer_rewritten() -> dict:
    """31/10 as it will be rewritten (analysis §1 table)."""
    e = cancer_today()
    e["routes"] = [
        _pitch(1, "6a+", "sent", "second"),
        _pitch(2, "6c+", "aid"),
        _pitch(3, "6b+", "sent", "second"),
        _pitch(4, "6c", "sent"),
        _pitch(5, "7a+", "aid", "second"),
        _pitch(6, "6b", "sent"),
        _pitch(7, "6b+", "sent", "second"),
        _pitch(8, "7b", "aid"),
    ]
    return e


def crique(rewritten: bool) -> dict:
    """01/11 La Crique: the second burn on Cernes was on top-rope (a real fall)."""
    second_burn = {"result": "fell", "notes": "top-rope, cadute corte",
                   "logged_at": "2026-11-01T13:55:53.376Z", "climb_seconds": 1566}
    if rewritten:
        second_burn["rope_role"] = "toprope"
    return {
        "date": "2026-11-01", "spot_name": "La Crique (Gorges de la Bourne, Vercors)",
        "discipline": "lead", "log_version": "outdoor.v2", "load_ref_grade": "8a+",
        "duration_minutes": 288,
        "routes": [
            {"name": "Throw away your TV", "grade": "6b+", "discipline": "lead",
             "attempts": [{"result": "sent", "logged_at": "2026-11-01T10:21:10.724Z", "climb_seconds": 1108}]},
            {"name": "J'en peux plus de moi-même L1", "grade": "6c", "discipline": "lead",
             "attempts": [{"result": "sent", "logged_at": "2026-11-01T11:26:30.038Z", "climb_seconds": 894}]},
            {"name": "Cernes couleurs myrtille", "grade": "7b+", "discipline": "lead",
             "attempts": [{"result": "fell", "logged_at": "2026-11-01T12:29:27.459Z", "climb_seconds": 1141},
                          second_burn]},
        ],
    }


def _isatis_day(**extra) -> dict:
    """Copy of the B394 fixture (no rope_role)."""
    entry = {
        "date": "2026-10-17", "spot_name": "Berdorf", "discipline": "lead", "duration_minutes": 240,
        "routes": [
            {"name": "Heinz", "grade": "6c", "attempts": [{"result": "sent"}]},
            {"name": "Bibi", "grade": "6b+", "attempts": [{"result": "sent"}]},
            {"name": "Isatis", "grade": "7c+", "style": "project",
             "attempts": [{"result": "fell"}, {"result": "fell"}]},
        ],
    }
    entry.update(extra)
    return entry


def _one(grade: str, *attempts: dict, **route) -> dict:
    return {"name": route.pop("name", f"R {grade}"), "grade": grade, "attempts": list(attempts), **route}


def _day(*routes: dict, **extra) -> dict:
    e = {"date": "2026-10-20", "spot_name": "X", "discipline": "lead", "duration_minutes": 60,
         "routes": list(routes)}
    e.update(extra)
    return e


# --------------------------------------------------------------------------- #
# 1. the shared predicates
# --------------------------------------------------------------------------- #

class TestPredicates:
    def test_absent_or_unknown_role_is_lead(self):
        assert oa.rope_role({"result": "sent"}) == "lead"
        assert oa.rope_role({"result": "sent", "rope_role": "tr"}) == "lead"
        assert oa.rope_role(None) == "lead"

    @pytest.mark.parametrize("attempt,send,clean", [
        ({"result": "sent"}, True, False),
        ({"result": "sent", "rope_role": "lead"}, True, False),
        ({"result": "sent", "rope_role": "second"}, False, True),
        ({"result": "sent", "rope_role": "toprope"}, False, True),
        ({"result": "fell", "rope_role": "second"}, False, False),
        ({"result": "aid"}, False, False),
        ({"result": "topped_out"}, False, False),
        ("sent", False, False),
    ])
    def test_send_and_clean(self, attempt, send, clean):
        assert oa.is_lead_send(attempt) is send
        assert oa.is_clean_non_lead(attempt) is clean

    def test_route_classes_are_exclusive(self):
        lead_and_second = {"attempts": [{"result": "sent", "rope_role": "second"}, {"result": "sent"}]}
        assert oa.route_lead_sent(lead_and_second)
        assert not oa.route_clean_non_lead(lead_and_second)
        assert not oa.route_aid(lead_and_second)
        second_then_aid = {"attempts": [{"result": "aid"}, {"result": "sent", "rope_role": "toprope"}]}
        assert oa.route_clean_non_lead(second_then_aid) and not oa.route_aid(second_then_aid)
        only_aid = {"attempts": [{"result": "fell"}, {"result": "aid", "rope_role": "second"}]}
        assert oa.route_aid(only_aid) and not oa.route_lead_sent(only_aid)

    def test_cancer_rewritten_reads_2_lead_3_clean_3_aid(self):
        routes = cancer_rewritten()["routes"]
        assert sum(oa.route_lead_sent(r) for r in routes) == 2
        assert sum(oa.route_clean_non_lead(r) for r in routes) == 3
        assert sum(oa.route_aid(r) for r in routes) == 3


# --------------------------------------------------------------------------- #
# 2. normalisation + validation (engine)
# --------------------------------------------------------------------------- #

class TestNormaliseAndValidate:
    def test_explicit_lead_is_stored_as_absent(self):
        e = _day(_one("7a", {"result": "sent", "rope_role": "lead"}))
        assert oa.normalize_entry_attempts(e) == []
        assert e["routes"][0]["attempts"] == [{"result": "sent"}]

    def test_boulder_session_loses_role_and_aid(self):
        e = _day(_one("7A", {"result": "aid", "rope_role": "toprope"}, {"result": "sent", "rope_role": "second"}),
                 discipline="boulder")
        changes = oa.normalize_entry_attempts(e)
        assert e["routes"][0]["attempts"] == [{"result": "fell"}, {"result": "sent"}]
        assert len(changes) == 3

    def test_boulder_route_in_a_lead_session(self):
        e = _day(_one("7A", {"result": "aid"}, discipline="boulder"),
                 _one("7a", {"result": "aid", "rope_role": "second"}))
        oa.normalize_entry_attempts(e)
        assert e["routes"][0]["attempts"] == [{"result": "fell"}]
        assert e["routes"][1]["attempts"] == [{"result": "aid", "rope_role": "second"}]

    def test_both_session_untagged_route_is_not_guessed(self):
        e = _day(_one("7A", {"result": "aid", "rope_role": "second"}), discipline="both")
        oa.normalize_entry_attempts(e)
        assert e["routes"][0]["attempts"] == [{"result": "aid", "rope_role": "second"}]

    def test_unknown_spellings_fail_validation(self):
        e = _day(_one("7a", {"result": "A0"}), _one("7a", {"result": "sent", "rope_role": "top_rope"}))
        e["log_version"] = "outdoor.v2"
        errors = validate_outdoor_entry(e)
        assert any("result" in x and "'A0'" in x for x in errors)
        assert any("rope_role" in x and "'top_rope'" in x for x in errors)

    def test_missing_result_fails_validation(self):
        e = _day(_one("7a", {"notes": "?"}), log_version="outdoor.v2")
        assert any("result" in x for x in validate_outdoor_entry(e))

    def test_new_vocabulary_is_valid(self):
        e = cancer_rewritten()
        assert validate_outdoor_entry(e) == []


# --------------------------------------------------------------------------- #
# 3. load (B327 + B394 v2)
# --------------------------------------------------------------------------- #

class TestLoad:
    def test_constants(self):
        assert ROPE_ROLE_LOAD_FACTOR == {"lead": 1.0, "second": 0.85, "toprope": 0.85}

    def test_real_fixtures_today(self):
        assert compute_outdoor_load_score(cancer_today()) == 39
        assert compute_outdoor_load_score(crique(rewritten=False)) == 47

    def test_real_fixtures_rewritten(self):
        assert compute_outdoor_load_score(cancer_rewritten()) == 37
        assert compute_outdoor_load_score(crique(rewritten=True)) == 44

    def test_logs_without_role_keep_their_numbers(self):
        assert compute_outdoor_load_score(_isatis_day()) == 22
        assert compute_outdoor_load_score(_isatis_day(load_ref_grade="8a+")) == 69
        multipitch = {"date": "2026-10-20", "load_ref_grade": "8a+", "routes": [
            {"grade": g, "attempts": [{"result": "sent"}]} for g in ("6a", "6a+", "6b", "6a", "6b", "6a+", "6a")]}
        assert compute_outdoor_load_score(multipitch) == 17

    def test_explicit_lead_equals_absent(self):
        day = _isatis_day(load_ref_grade="8a+")
        lead = copy.deepcopy(day)
        for r in lead["routes"]:
            for a in r["attempts"]:
                a["rope_role"] = "lead"
        assert compute_outdoor_load_score(lead) == compute_outdoor_load_score(day)

    @pytest.mark.parametrize("ref", [None, "8a+"])
    def test_role_x_result_matrix_single_attempt(self, ref):
        """One attempt, so the score is the attempt score: ratios are exact."""
        def score(result, role=None, grade="8a"):
            e = _day(_one(grade, {"result": result, **({"rope_role": role} if role else {})}))
            if ref:
                e["load_ref_grade"] = ref
            return compute_outdoor_load_score(e)

        lead_sent = score("sent")
        assert score("sent", "second") == round(lead_sent * 0.85)
        assert score("sent", "toprope") == round(lead_sent * 0.85)
        assert score("aid") == lead_sent                      # A0 is not discounted
        assert score("topped_out") == lead_sent
        assert score("aid", "second") == round(lead_sent * 0.85)
        if ref:  # v2: falls count like sends
            assert score("fell") == lead_sent
            assert score("fell", "toprope") == round(lead_sent * 0.85)
        else:    # B327: a fall is 0.8, second + fall 0.68
            assert score("fell") == round(lead_sent * 0.8)
            assert score("fell", "second") == round(lead_sent * 0.8 * 0.85)

    def test_volume_counts_non_lead_attempts(self):
        one = _day(_one("6a", {"result": "sent"}), load_ref_grade="8a+")
        with_second = _day(_one("6a", {"result": "sent"}), _one("5c", {"result": "sent", "rope_role": "second"}),
                           load_ref_grade="8a+")
        assert compute_outdoor_load_score(with_second) > compute_outdoor_load_score(one)

    def test_role_discount_enters_the_top_two_choice(self):
        """v2 intensity = mean of the two hardest attempts AFTER the role factor."""
        e = _day(_one("7b", {"result": "sent", "rope_role": "toprope"}), _one("7a+", {"result": "sent"}),
                 _one("7a+", {"result": "sent"}), load_ref_grade="8a+")
        # 7b TR = 16 × 0.85 = 13.6 > 7a+ lead 11.2: still in the top two;
        # volume over 3 attempts = 1 + log3(3) = 2
        assert compute_outdoor_load_score(e) == round((13.6 + 11.2) / 2 * 2.0)


# --------------------------------------------------------------------------- #
# 4. grade evidence (A292) + outdoor stats
# --------------------------------------------------------------------------- #

class TestEvidenceAndStats:
    @pytest.mark.parametrize("role", ["second", "toprope"])
    @pytest.mark.parametrize("style", [None, "onsight", "flash"])
    def test_clean_non_lead_is_never_evidence(self, role, style):
        route = _one("7b", {"result": "sent", "rope_role": role}, **({"style": style} if style else {}))
        assert ge.is_onsight_evidence({"spot_name": "X", "discipline": "lead"}, route, set()) is False

    def test_lead_send_still_is(self):
        route = _one("7b", {"result": "sent"})
        assert ge.is_onsight_evidence({"spot_name": "X", "discipline": "lead"}, route, set()) is True

    def test_seconded_first_then_led_is_not_a_first_go(self):
        day1 = _day(_one("7b", {"result": "sent", "rope_role": "second"}, name="Tiro"), date="2026-10-01")
        day2 = _day(_one("7b", {"result": "sent"}, name="Tiro"), date="2026-10-08")
        assert ge.collect_onsight_evidence([day1, day2]) == []

    def test_cancer_rewritten_evidence_is_only_the_lead_pitches(self):
        keys = {r["name"] for r in ge.collect_onsight_evidence([cancer_rewritten()])}
        assert keys == {f"{CANCER}4", f"{CANCER}6"}

    def test_stats_count_only_lead_sends(self):
        stats = compute_outdoor_stats([cancer_rewritten()])
        assert stats["total_routes"] == 8
        assert stats["sent_pct"] == 25.0               # L4, L6
        assert stats["top_grade_sent"] == "6c"         # not L1/L3/L7 nor the A0 7b
        assert stats["onsight_pct"] == 25.0            # inferred from the lead pitches only

    def test_explicit_onsight_on_top_rope_is_not_counted(self):
        stats = compute_outdoor_stats([_day(_one("7c", {"result": "sent", "rope_role": "toprope"},
                                                 style="onsight"))])
        assert stats["onsight_pct"] == 0.0 and stats["sent_pct"] == 0.0
        assert stats["top_grade_sent"] is None


# --------------------------------------------------------------------------- #
# 5. milestones
# --------------------------------------------------------------------------- #

class TestMilestones:
    @pytest.mark.parametrize("attempt", [
        {"result": "sent", "rope_role": "second"},
        {"result": "sent", "rope_role": "toprope"},
        {"result": "aid"},
        {"result": "aid", "rope_role": "second"},
    ])
    def test_not_a_sent_route(self, attempt):
        assert milestones_v1._route_sent({"attempts": [attempt]}) is False

    def test_lead_send_still_is(self):
        assert milestones_v1._route_sent({"attempts": [{"result": "sent"}]}) is True

    def test_scan_ignores_non_lead_and_aid(self, monkeypatch):
        day = _day(_one("6b", {"result": "sent"}),
                   _one("8a", {"result": "sent", "rope_role": "toprope"}, style="onsight"),
                   _one("7c", {"result": "aid"}))
        monkeypatch.setattr(milestones_v1, "load_outdoor_sessions", lambda uid: [day])
        facts = milestones_v1._scan_outdoor(None)
        assert facts["any_session"] is True               # first outdoor day still unlocks
        assert facts["pb_sent"]["lead"][1] == "6b"
        assert facts["any_onsight"] is False and facts["pb_onsight"] == {}


# --------------------------------------------------------------------------- #
# 6. athlete_context
# --------------------------------------------------------------------------- #

def _rows(*entries):
    return [{"entry": e} for e in entries]


def _section(text: str, title: str) -> str:
    start = text.index(title)
    nxt = text.find("\n## ", start + 1)
    return text[start: nxt if nxt != -1 else len(text)]


class TestAthleteContext:
    def test_version(self):
        assert ac.VERSION == "b414.2"

    def test_recent_outdoor_counts(self):
        cancer = cancer_rewritten()
        cancer["date"] = "2026-10-03"
        ctx = ac.build_athlete_context(_state(), TODAY, outdoor_rows=_rows(cancer))
        o = next(x for x in ctx["recent"]["outdoor"] if x["date"] == "2026-10-03")
        assert (o["routes"], o["sent"], o["clean_non_lead"], o["aid"]) == (8, 2, 3, 3)
        txt = ac.render_text(ctx, state=_state(), outdoor_rows=_rows(cancer))
        assert "8 vie, 2 chiuse da primo, 3 pulite da secondo/TR, 3 in A0" in txt

    def test_lead_only_day_line_unchanged(self):
        day = _day(_one("6b", {"result": "sent"}), _one("6c", {"result": "fell"}), date="2026-10-03")
        ctx = ac.build_athlete_context(_state(), TODAY, outdoor_rows=_rows(day))
        txt = ac.render_text(ctx, state=_state(), outdoor_rows=_rows(day))
        assert "2026-10-03 outdoor X: 2 vie, 1 chiuse\n" in txt + "\n"

    def test_tryhard_counts_lead_only_and_aid(self):
        day = _day(
            _one("8a", {"result": "fell"}, {"result": "aid"}, {"result": "sent", "rope_role": "toprope"},
                 {"result": "fell", "rope_role": "second"}, name="Proj"),
            _one("6b", {"result": "aid"}, name="Easy"),   # below RP−2 (7c+)
            date="2026-10-03")
        out = ac.tryhard_from_results(_state(), TODAY, _rows(day))
        assert out["counts"] == {"SEND": 0, "FALL": 1, "TOPPED_OUT": 0, "AID": 1}
        assert out["attempts"] == 2
        assert out["fall_pct_of_non_send"] == 50.0
        assert out["non_lead_excluded"] == 2
        assert out["routes"] == ["10-03 Proj 8a ×2"] and out["non_lead_routes"] == ["10-03 Proj 8a ×2"]

    def test_tryhard_cli_lines(self):
        day = _day(_one("8a", {"result": "aid"}, {"result": "sent", "rope_role": "second"}, name="Proj"),
                   date="2026-10-03")
        ctx = ac.build_athlete_context(_state(), TODAY, outdoor_rows=_rows(day))
        sec = _section(ac.render_text(ctx, state=_state(), outdoor_rows=_rows(day)), "## Try-hard")
        assert "SEND 0 · FALL 0 · TOPPED_OUT 0 · AID 1" in sec
        assert "Esclusi dal conteggio (da secondo / top-rope, non sono try-hard): 1 tentativi — 10-03 Proj 8a ×1" in sec

    def test_tryhard_only_non_lead_says_no_lead_attempt(self):
        day = _day(_one("8a", {"result": "sent", "rope_role": "toprope"}, name="Proj"), date="2026-10-03")
        out = ac.tryhard_from_results(_state(), TODAY, _rows(day))
        assert out["attempts"] == 0 and out["non_lead_excluded"] == 1


# --------------------------------------------------------------------------- #
# 7. weekly report
# --------------------------------------------------------------------------- #

class TestReport:
    def test_build_outdoor_lead_only(self):
        out = _build_outdoor([cancer_rewritten()])
        assert out["routes_attempted"] == 8
        assert out["routes_sent"] == out["sends"] == 2
        assert out["routes_clean_non_lead"] == 3
        assert out["top_grade_sent"] == "6c"
        assert out["top_grade_attempted"] == "7b"

    def test_onsight_only_with_a_lead_send(self):
        out = _build_outdoor([_day(_one("7c", {"result": "sent", "rope_role": "second"}, style="onsight"))])
        assert out["onsight_pct"] == 0.0 and out["routes_sent"] == 0

    def test_empty_has_the_new_field(self):
        assert _build_outdoor([])["routes_clean_non_lead"] == 0

    def test_highlight_mentions_clean_seconds(self):
        out = _build_outdoor([cancer_rewritten()])
        hl = _build_highlights({}, {}, {}, {}, [], out, {})
        text = next(h["text"] for h in hl if h["key"] == "outdoor_summary")
        assert text == "1 outdoor session(s) — 2/8 sends — 3 clean on second/top-rope — top attempt 7b — top send 6c."

    def test_highlight_of_a_lead_only_week_unchanged(self):
        out = _build_outdoor([_isatis_day()])
        text = next(h["text"] for h in _build_highlights({}, {}, {}, {}, [], out, {})
                    if h["key"] == "outdoor_summary")
        assert text == "1 outdoor session(s) — 2/3 sends — top attempt 7c+ — top send 6c."


# --------------------------------------------------------------------------- #
# 8. coach prompt
# --------------------------------------------------------------------------- #

class TestCoachLine:
    def test_cancer_line(self):
        line = _outdoor_log_line(cancer_rewritten())
        assert f"{CANCER}1 6a+ second clean" in line
        assert f"{CANCER}2 6c+ A0," in line
        assert f"{CANCER}4 6c sent" in line
        assert f"{CANCER}5 7a+ A0 (second)" in line
        assert f"{CANCER}8 7b A0" in line

    def test_crique_top_rope_fall(self):
        line = _outdoor_log_line(crique(rewritten=True))
        assert "Cernes couleurs myrtille 7b+ fell + fell (top-rope)" in line

    def test_b328_groups_kept_and_role_groups_after(self):
        route = _one("7c", {"result": "sent", "rope_role": "toprope"}, {"result": "fell"}, {"result": "sent"},
                     {"result": "fell"}, {"result": "topped_out"}, name="P")
        line = _outdoor_log_line(_day(route))
        assert "P 7c sent + fell x2 + top w/ rests + top-rope clean" in line

    def test_send_style_only_with_a_lead_send(self):
        tr = _outdoor_log_line(_day(_one("7a", {"result": "sent", "rope_role": "toprope"}, style="onsight", name="X1")))
        assert "(onsight)" not in tr and "X1 7a top-rope clean" in tr
        lead = _outdoor_log_line(_day(_one("7a", {"result": "sent"}, style="onsight", name="X1")))
        assert "X1 7a (onsight) sent" in lead
        project = _outdoor_log_line(_day(_one("8a", {"result": "fell"}, style="project", name="X2")))
        assert "X2 8a (project) fell" in project

    def test_instruction_block(self):
        assert "never upgrade a fall into a send" in INSTRUCTION_BLOCK
        assert "a \"second clean\" or \"top-rope clean\" ascent is not a send" in INSTRUCTION_BLOCK
        assert "\"A0\" (pulled on the gear) is not a free ascent" in INSTRUCTION_BLOCK


# --------------------------------------------------------------------------- #
# 9. unchanged on purpose: outdoor-hard days, finger-hard days, key sessions
# --------------------------------------------------------------------------- #

def _hard_rows(role: str | None):
    a = {"result": "sent"}
    b = {"result": "fell"}
    if role:
        a["rope_role"] = role
        b["rope_role"] = role
    return _rows({"date": "2026-10-03", "spot_name": "Berdorf", "discipline": "lead", "routes": [
        {"name": "Warmup", "grade": "6b", "attempts": [{"result": "sent"}]},
        {"name": "Isatis", "grade": "7c+", "attempts": [a, b]},
    ]})


class TestHardDaysUnchanged:
    @pytest.mark.parametrize("role", ["second", "toprope"])
    def test_hard_route_on_second_is_still_an_outdoor_hard_day(self, role):
        st = _state()
        base = stimulus.outdoor_hard_days(st, since="2026-09-27", until=TODAY, outdoor_rows=_hard_rows(None))
        assert [d["date"] for d in base] == ["2026-10-03"]
        assert stimulus.outdoor_hard_days(st, since="2026-09-27", until=TODAY,
                                          outdoor_rows=_hard_rows(role)) == base
        assert stimulus.finger_hard_days(st, since="2026-09-27", until=TODAY, outdoor_rows=_hard_rows(role)) == \
            stimulus.finger_hard_days(st, since="2026-09-27", until=TODAY, outdoor_rows=_hard_rows(None))

    def test_key_status_identical_with_or_without_role(self):
        st = _state()
        a = ks.compute_key_status(st, TODAY, outdoor_rows=_hard_rows(None))
        b = ks.compute_key_status(st, TODAY, outdoor_rows=_hard_rows("toprope"))
        assert a == b


# --------------------------------------------------------------------------- #
# 10. static scans + the JSON schema contract
# --------------------------------------------------------------------------- #

_SENT_CMP = re.compile(r"""(==|!=)\s*["']sent["']|["']sent["']\s*(==|!=)""")
_SENT_IN = re.compile(r"""\bin\s*[\(\[\{][^)\]\}]*["']sent["']""")


def test_no_inline_sent_comparison_outside_outdoor_attempt():
    """Every reader of an outdoor attempt's outcome goes through
    outdoor_attempt (a `result == "sent"` elsewhere would count a clean second
    as a send). Lines about other fields (free-session `status`, limit-log
    `outcome`) do not mention `result` and are not flagged."""
    offenders = []
    for path in sorted((REPO_ROOT / "backend").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("backend/tests/") or rel == "backend/engine/outdoor_attempt.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "result" not in line:
                continue
            if _SENT_CMP.search(line) or _SENT_IN.search(line) or '.count("sent")' in line:
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert offenders == []


def test_scan_catches_the_old_patterns():
    for bad in ('any(a.get("result") == "sent" for a in attempts)',
                "return attempts[0].get('result') == 'sent'",
                'if a.get("result") in ("sent", "topped_out"):'):
        assert _SENT_CMP.search(bad) or _SENT_IN.search(bad)


def _schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _attempt_schema(schema):
    return schema["properties"]["routes"]["items"]["properties"]["attempts"]["items"]


class TestSchemaContract:
    def test_enums_match_engine_and_models(self):
        from typing import get_args

        from backend.api.models import OutdoorAttempt

        att = _attempt_schema(_schema())["properties"]
        assert tuple(att["result"]["enum"]) == oa.RESULTS
        assert tuple(att["rope_role"]["enum"]) == oa.ROPE_ROLES
        assert get_args(OutdoorAttempt.model_fields["result"].annotation) == oa.RESULTS
        role_ann = OutdoorAttempt.model_fields["rope_role"].annotation
        assert next(get_args(t) for t in get_args(role_ann) if get_args(t)) == oa.ROPE_ROLES

    def test_attempt_fields_cover_the_model(self):
        from backend.api.models import OutdoorAttempt, OutdoorRoute, OutdoorSessionLog

        schema = _schema()
        assert set(OutdoorAttempt.model_fields) <= set(_attempt_schema(schema)["properties"])
        route_props = schema["properties"]["routes"]["items"]["properties"]
        assert set(OutdoorRoute.model_fields) <= set(route_props)
        assert set(OutdoorSessionLog.model_fields) <= set(schema["properties"])

    def test_real_shapes_validate(self):
        jsonschema = pytest.importorskip("jsonschema")
        v = jsonschema.Draft202012Validator(_schema())
        weather = {"wind": 6.7, "humidity": 22, "wind_deg": 326, "dew_point": 8.3, "feels_like": 30.9,
                   "wind_label": "light", "cloud_cover": 61, "precip_prob": 0, "temperature": 32.8,
                   "condition_band": "poor_hot_humid", "weather_band_raw": "poor"}
        shaped = _isatis_day(log_version="outdoor.v2", spot_id="spot_1", day_type="project",
                             conditions=weather, energy_level="medium",
                             route_profile={"route_length": "long_endurance"})
        shaped["routes"][0]["rest_seconds"] = 300
        shaped["routes"][1]["discipline"] = "both"
        for entry in (cancer_today(), cancer_rewritten(), crique(True), shaped):
            assert list(v.iter_errors(entry)) == [], entry["date"]

    def test_schema_rejects_other_spellings(self):
        jsonschema = pytest.importorskip("jsonschema")
        v = jsonschema.Draft202012Validator(_schema())
        bad = cancer_rewritten()
        bad["routes"][0]["attempts"][0]["rope_role"] = "top_rope"
        assert list(v.iter_errors(bad))


# --------------------------------------------------------------------------- #
# 11. PUT carry-over (engine)
# --------------------------------------------------------------------------- #

class TestCarryOver:
    PREV = {"date": "2026-10-31", "spot_name": "Presles", "spot_id": "spot_p", "discipline": "lead",
            "duration_minutes": 480, "day_type": "volume", "conditions": {"temperature": 12},
            "route_profile": {"route_length": "long_endurance"}, "energy_level": "medium",
            "overall_feeling": "ok", "notes": "old", "log_version": "outdoor.v2", "load_ref_grade": "8a+",
            "load_score": 39, "routes": [{"name": "L1", "grade": "6a", "attempts": [{"result": "sent"}]}]}

    def test_unsent_keys_are_kept(self):
        new = {"date": "2026-10-31", "spot_name": "Presles", "discipline": "lead", "duration_minutes": 480,
               "routes": [], "log_version": "outdoor.v2"}
        sent = {"date", "spot_name", "discipline", "duration_minutes", "routes"}
        carried = carry_over_unsent_keys(new, self.PREV, sent)
        assert set(carried) == {"spot_id", "day_type", "conditions", "route_profile", "energy_level",
                                "overall_feeling"}
        assert new["day_type"] == "volume" and new["spot_id"] == "spot_p"
        assert "load_score" not in new and "load_ref_grade" not in new   # never carried
        assert "notes" not in new                                       # the form's: absent = cleared
        assert new["routes"] == []                                     # sent → the request wins

    def test_null_clears_a_carried_key(self):
        new = {"date": "2026-10-31", "spot_name": "Presles", "discipline": "lead", "duration_minutes": 480,
               "routes": []}
        carry_over_unsent_keys(new, self.PREV, {"date", "spot_name", "discipline", "duration_minutes",
                                                "notes", "day_type"})
        assert "notes" not in new and "day_type" not in new            # sent as null → cleared

    def test_routes_and_notes_are_never_carried(self):
        """Review: the form owns them. Not sent = empty, never the old value."""
        new = {"date": "2026-10-31", "spot_name": "Presles", "discipline": "lead", "duration_minutes": 480,
               "routes": []}
        carried = carry_over_unsent_keys(new, self.PREV, {"date", "spot_name", "discipline", "duration_minutes"})
        assert "routes" not in carried and "notes" not in carried
        assert new["routes"] == [] and "notes" not in new

    def test_rename_does_not_carry_the_spot_id(self):
        new = {"date": "2026-10-31", "spot_name": "Other crag", "discipline": "lead"}
        carry_over_unsent_keys(new, self.PREV, {"date", "spot_name", "discipline"})
        assert "spot_id" not in new and new["day_type"] == "volume"


# --------------------------------------------------------------------------- #
# 12. API (file storage)
# --------------------------------------------------------------------------- #

class TestApi:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage

        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({"schema_version": "1.5", "outdoor_spots": [], **STATE}))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    _KEYS = ("date", "spot_name", "discipline", "duration_minutes", "routes")

    def _body(self, entry: dict, *extra: str) -> dict:
        return {k: copy.deepcopy(entry[k]) for k in self._KEYS + extra if k in entry}

    def _stored(self, day: str, spot: str | None = None) -> dict:
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        s = next(s for s in sessions if s["date"] == day and (spot is None or s["spot_name"] == spot))
        s.pop("load_score", None)
        return s

    def test_post_keeps_roles_and_aid(self):
        res = self.client.post("/api/outdoor/log", json=self._body(cancer_rewritten(), "day_type"))
        assert res.status_code == 200, res.text
        stored = self._stored("2026-10-31")
        assert stored["routes"] == cancer_rewritten()["routes"]
        assert stored["load_ref_grade"] == "8a+"
        assert compute_outdoor_load_score(stored) == 37

    def test_post_without_role_is_identical_to_before(self):
        body = self._body(_isatis_day())
        assert self.client.post("/api/outdoor/log", json=body).status_code == 200
        stored = self._stored("2026-10-17")
        # B412: every log written records its session's fingerprint.
        assert len(stored.pop("session_keys")) == 1
        assert stored == {**body, "log_version": "outdoor.v2", "load_ref_grade": "8a+"}

    def test_explicit_lead_is_stored_as_absent(self):
        body = self._body(_isatis_day())
        for r in body["routes"]:
            for a in r["attempts"]:
                a["rope_role"] = "lead"
        assert self.client.post("/api/outdoor/log", json=body).status_code == 200
        assert self._stored("2026-10-17")["routes"] == _isatis_day()["routes"]

    @pytest.mark.parametrize("attempt", [{"result": "A0"}, {"result": "sent", "rope_role": "top_rope"},
                                         {"result": "sent", "rope_role": "tr"}])
    def test_unknown_spelling_is_422(self, attempt):
        body = self._body(_isatis_day())
        body["routes"][0]["attempts"] = [attempt]
        assert self.client.post("/api/outdoor/log", json=body).status_code == 422

    def test_boulder_with_role_or_aid_is_normalised_not_rejected(self):
        body = {"date": "2026-10-18", "spot_name": "Font", "discipline": "boulder", "duration_minutes": 90,
                "routes": [{"name": "B1", "grade": "7A", "attempts": [
                    {"result": "aid", "rope_role": "toprope"}, {"result": "sent", "rope_role": "second"}]}]}
        res = self.client.post("/api/outdoor/log", json=body)
        assert res.status_code == 200, res.text
        assert self._stored("2026-10-18")["routes"][0]["attempts"] == [{"result": "fell"}, {"result": "sent"}]

    def test_put_keeps_roles_and_what_it_does_not_send(self):
        full = cancer_today()
        full["spot_id"] = "spot_presles"
        full["conditions"] = {"temperature": 14, "condition_band": "prime"}
        post = self._body(full, "day_type", "spot_id", "conditions")
        assert self.client.post("/api/outdoor/log", json=post).status_code == 200

        put = self._body(cancer_rewritten())   # what the edit form sends: no day_type / spot_id / conditions
        res = self.client.put("/api/outdoor/log", json=put)
        assert res.status_code == 200, res.text
        assert res.json()["load_score"] == 37
        stored = self._stored("2026-10-31")
        assert stored["routes"] == cancer_rewritten()["routes"]
        assert stored["day_type"] == "volume"
        assert stored["spot_id"] == "spot_presles"
        assert stored["conditions"] == {"temperature": 14, "condition_band": "prime"}
        assert stored["load_ref_grade"] == "8a+"

    def test_put_null_clears_a_key(self):
        post = self._body(cancer_today(), "day_type")
        post["notes"] = "old note"
        self.client.post("/api/outdoor/log", json=post)
        put = {**self._body(cancer_today()), "notes": None, "day_type": None}
        assert self.client.put("/api/outdoor/log", json=put).status_code == 200
        stored = self._stored("2026-10-31")
        assert "notes" not in stored and "day_type" not in stored

    def test_put_from_a_pre_a324_form_clears_emptied_notes(self):
        """Review: the old form sends ``notes: notes || undefined`` — emptied
        notes leave the key out. The edit must not bring «old» back."""
        post = self._body(cancer_today(), "day_type")
        post["notes"] = "old"
        self.client.post("/api/outdoor/log", json=post)
        put = self._body(cancer_today())            # no notes key at all
        assert "notes" not in put
        assert self.client.put("/api/outdoor/log", json=put).status_code == 200
        stored = self._stored("2026-10-31")
        assert "notes" not in stored
        assert stored["day_type"] == "volume"      # the keys the form never sends are still kept

    def test_put_rename_does_not_carry_the_spot_id(self):
        post = {**self._body(cancer_today(), "day_type"), "spot_id": "spot_presles"}
        self.client.post("/api/outdoor/log", json=post)
        put = {**self._body(cancer_today()), "spot_name": "Presles (renamed)",
               "original_spot_name": cancer_today()["spot_name"]}
        assert self.client.put("/api/outdoor/log", json=put).status_code == 200
        stored = self._stored("2026-10-31")
        assert stored["spot_name"] == "Presles (renamed)"
        assert "spot_id" not in stored and stored["day_type"] == "volume"

    def test_live_session_keeps_roles_to_the_final_log(self):
        start = self.client.post("/api/outdoor/session/start",
                                 json={"date": "2026-11-01", "spot_name": "La Crique", "discipline": "lead"})
        sid = start.json()["session_id"]
        climb = {"name": "Cernes", "grade": "7b+", "attempts": [{"result": "fell", "rope_role": "lead"},
                                                                {"result": "fell", "rope_role": "toprope"}]}
        res = self.client.post(f"/api/outdoor/session/{sid}/log-climb", json=climb)
        assert res.status_code == 200
        assert res.json()["routes"][0]["attempts"] == [{"result": "fell"}, {"result": "fell", "rope_role": "toprope"}]

        routes = [climb, {"name": "L1", "grade": "6a+", "attempts": [{"result": "sent", "rope_role": "second"}]},
                  {"name": "L2", "grade": "6c+", "attempts": [{"result": "aid"}]}]
        res = self.client.put(f"/api/outdoor/session/{sid}/routes", json={"routes": routes})
        assert res.status_code == 200
        res = self.client.post(f"/api/outdoor/session/{sid}/finish",
                               json={"spot_name": "La Crique", "discipline": "lead", "duration_minutes": 120})
        assert res.status_code == 200, res.text
        stored = self._stored("2026-11-01")
        assert [r["attempts"] for r in stored["routes"]] == [
            [{"result": "fell"}, {"result": "fell", "rope_role": "toprope"}],
            [{"result": "sent", "rope_role": "second"}],
            [{"result": "aid"}],
        ]

    def test_live_boulder_session_finishes_with_aid_normalised(self):
        """No 422 at the end of the day: the live path never validated the role."""
        sid = self.client.post("/api/outdoor/session/start",
                               json={"date": "2026-11-01", "spot_name": "Bloc", "discipline": "boulder"}
                               ).json()["session_id"]
        self.client.post(f"/api/outdoor/session/{sid}/log-climb",
                         json={"name": "P", "grade": "7A", "attempts": [{"result": "aid", "rope_role": "second"}]})
        state = json.loads(self.state_path.read_text())
        live = next(s for s in state["outdoor_active_sessions"] if s["session_id"] == sid)
        assert live["routes"][0]["attempts"] == [{"result": "fell"}]
        res = self.client.post(f"/api/outdoor/session/{sid}/finish",
                               json={"spot_name": "Bloc", "discipline": "boulder", "duration_minutes": 60})
        assert res.status_code == 200, res.text
        assert self._stored("2026-11-01")["routes"][0]["attempts"] == [{"result": "fell"}]


# --------------------------------------------------------------------------- #
# 13. plan sync after a PUT: the day takes the new load, nothing else moves
# --------------------------------------------------------------------------- #

def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class _PlanSyncBase:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage

        self.monday = _monday(date.today()) - timedelta(weeks=1)
        self.day = (self.monday + timedelta(days=5)).isoformat()   # last Saturday
        days = []
        for i, wd in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun")):
            d = {"date": (self.monday + timedelta(days=i)).isoformat(), "weekday": wd, "sessions": []}
            if wd == "sat":
                d.update({"outdoor_spot_name": "Presles", "outdoor_discipline": "lead",
                          "outdoor_session_status": "planned"})
            if wd == "tue":
                d["sessions"] = [{"slot": "evening", "session_id": "strength_long", "status": "done"}]
            days.append(d)
        plan = {"start_date": self.monday.isoformat(), "weeks": [{"week_index": 0, "days": days}]}
        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({"schema_version": "1.5", "outdoor_spots": [], **STATE,
                                               "week_plans": {self.monday.isoformat(): plan}}))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _plan(self) -> dict:
        return json.loads(self.state_path.read_text())["week_plans"][self.monday.isoformat()]

    def _sat(self) -> dict:
        return next(d for w in self._plan()["weeks"] for d in w["days"] if d["date"] == self.day)

    def _book(self) -> list:
        return [e for e in json.loads(self.state_path.read_text()).get("outdoor_log", [])
                if e["date"] == self.day]

    def _crag(self, spot: str, *routes: dict) -> dict:
        return {"date": self.day, "spot_name": spot, "discipline": "lead", "duration_minutes": 120,
                "routes": list(routes) or [_one("6b", {"result": "sent"}, name=f"{spot} R")]}


class TestPlanSyncAfterPut(_PlanSyncBase):
    def test_only_the_day_load_changes(self):
        today_body = {k: v for k, v in cancer_today().items()
                      if k in ("spot_name", "discipline", "duration_minutes", "routes")}
        today_body["spot_name"] = "Presles"
        today_body["date"] = self.day
        res = self.client.post("/api/outdoor/log", json=today_body)
        assert res.status_code == 200 and res.json()["plan_synced"] is True
        before = self._plan()

        rewritten = {**today_body, "routes": cancer_rewritten()["routes"]}
        res = self.client.put("/api/outdoor/log", json=rewritten)
        assert res.status_code == 200, res.text
        after = self._plan()

        sat = lambda p: next(d for w in p["weeks"] for d in w["days"] if d["date"] == self.day)  # noqa: E731
        assert sat(before)["outdoor_load_score"] == 39
        assert sat(after)["outdoor_load_score"] == 37
        strip = lambda p: [{k: v for k, v in d.items() if k != "outdoor_load_score"}  # noqa: E731
                           for w in p["weeks"] for d in w["days"]]
        assert strip(after) == strip(before)
        book = [e for e in json.loads(self.state_path.read_text())["outdoor_log"] if e["date"] == self.day]
        assert len(book) == 1 and book[0]["load_score"] == 37


# --------------------------------------------------------------------------- #
# 14. review: a rename and a per-crag delete re-sync the plan day
# --------------------------------------------------------------------------- #

class TestPlanSyncAfterRenameAndDelete(_PlanSyncBase):
    """A324 exposes both from the UI (rename dialog, per-crag trash). Before
    the review the plan day kept «Presles - Freyr» after a plain rename, and
    kept the deleted crag's load in its total (stimulus reads max(plan, log),
    so the ≥65 outdoor-load guard could still fire)."""

    def test_rename_leaves_no_ghost_crag_in_the_label(self):
        assert self.client.post("/api/outdoor/log", json=self._crag("Presles")).status_code == 200
        assert self._sat()["outdoor_spot_name"] == "Presles"

        put = {**self._crag("Freyr"), "original_spot_name": "Presles"}
        res = self.client.put("/api/outdoor/log", json=put)
        assert res.status_code == 200, res.text
        assert res.json()["plan_synced"] is True

        sat = self._sat()
        assert sat["outdoor_spot_name"] == "Freyr"
        assert sat["outdoor_session_status"] == "done"
        assert sat["outdoor_load_score"] == res.json()["load_score"]
        book = self._book()
        assert len(book) == 1 and book[0]["spot_name"] == "Freyr"

    def test_edit_without_rename_keeps_a_two_crag_label(self):
        self.client.post("/api/outdoor/log", json=self._crag("Presles"))
        self.client.post("/api/outdoor/log", json=self._crag("Freyr"))
        put = {**self._crag("Freyr", _one("7a", {"result": "fell"}, name="X")), "original_spot_name": "Freyr"}
        assert self.client.put("/api/outdoor/log", json=put).status_code == 200
        assert self._sat()["outdoor_spot_name"] == "Presles - Freyr"

    def test_rename_of_one_crag_of_two_keeps_the_other(self):
        self.client.post("/api/outdoor/log", json=self._crag("Presles"))
        self.client.post("/api/outdoor/log", json=self._crag("Freyr"))
        put = {**self._crag("Freyr Sector B"), "original_spot_name": "Freyr"}
        assert self.client.put("/api/outdoor/log", json=put).status_code == 200
        assert self._sat()["outdoor_spot_name"] == "Presles - Freyr Sector B"

    def test_per_crag_delete_resyncs_the_day_load_and_label(self):
        heavy = _one("7a", {"result": "fell"}, {"result": "fell"}, {"result": "sent"}, name="Big")
        self.client.post("/api/outdoor/log", json=self._crag("Presles"))
        self.client.post("/api/outdoor/log", json=self._crag("Freyr", heavy))
        sessions = {s["spot_name"]: s["load_score"]
                    for s in self.client.get("/api/outdoor/sessions").json()["sessions"]
                    if s["date"] == self.day}
        assert self._sat()["outdoor_load_score"] == sessions["Presles"] + sessions["Freyr"]
        assert self._sat()["outdoor_spot_name"] == "Presles - Freyr"

        res = self.client.delete(f"/api/outdoor/log/{self.day}", params={"spot_name": "Freyr"})
        assert res.status_code == 200, res.text

        sat = self._sat()
        assert sat["outdoor_load_score"] == sessions["Presles"]
        assert sat["outdoor_spot_name"] == "Presles"
        assert sat["outdoor_session_status"] == "done"
        book = self._book()
        assert len(book) == 1
        assert book[0]["load_score"] == sessions["Presles"] and book[0]["spot_name"] == "Presles"

    def test_deleting_the_last_crag_leaves_the_plan_as_before(self):
        self.client.post("/api/outdoor/log", json=self._crag("Presles"))
        before = self._plan()
        res = self.client.delete(f"/api/outdoor/log/{self.day}", params={"spot_name": "Presles"})
        assert res.status_code == 200, res.text
        assert self._plan() == before
        assert self._book() == []

    def test_per_crag_delete_without_plan_fixes_the_bookkeeping_label(self, monkeypatch):
        import backend.api.routers.outdoor as outdoor_router

        self.client.post("/api/outdoor/log", json=self._crag("Presles"))
        self.client.post("/api/outdoor/log", json=self._crag("Freyr"))
        monkeypatch.setattr(outdoor_router, "_sync_plan_after_outdoor_log", lambda *a, **k: False)
        res = self.client.delete(f"/api/outdoor/log/{self.day}", params={"spot_name": "Freyr"})
        assert res.status_code == 200, res.text
        book = self._book()
        assert len(book) == 1 and book[0]["spot_name"] == "Presles"


@pytest.mark.parametrize("label, dropped, logged, expected", [
    ("Berdorf - Freyr", "Berdorf", ["Freyr"], "Freyr"),
    ("Berdorf - Freyr", "Freyr", ["Berdorf"], "Berdorf"),
    ("berdorf - Berdorf", "berdorf", ["Berdorf"], "Berdorf"),   # case-only rename
    ("Berdorf", "Berdorf", [], "Berdorf"),                       # never empties the label
    ("Berdorf - Freyr", "Freyr", ["Berdorf", "Freyr"], "Berdorf - Freyr"),  # still logged
    ("Berdorf - Freyr", "Ourania", ["Berdorf"], "Berdorf - Freyr"),
    ("Berdorf - Freyr", None, ["Berdorf"], "Berdorf - Freyr"),
])
def test_drop_crag_from_label(label, dropped, logged, expected):
    from backend.api.routers.outdoor import _drop_crag_from_label

    assert _drop_crag_from_label(label, dropped, logged) == expected
