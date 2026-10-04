"""A292 (R6b) — lead onsight evidence from the outdoor log + confirm endpoint.

The engine proposes, the athlete confirms route by route; only the confirm
endpoint writes the grade, and the outdoor log is never rewritten.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.api.routers import assessment as assessment_router
from backend.engine import grade_evidence as ge
from backend.engine.outdoor_log import compute_outdoor_stats


def _route(name, grade, results=("sent",), style=None, discipline=None):
    r = {"name": name, "grade": grade, "attempts": [{"result": x} for x in results]}
    if style is not None:
        r["style"] = style
    if discipline is not None:
        r["discipline"] = discipline
    return r


def _session(date, spot, routes, discipline="lead"):
    return {
        "log_version": "outdoor.v1", "date": date, "spot_name": spot,
        "discipline": discipline, "duration_minutes": 120, "routes": routes,
    }


# Daniele's log, the parts that matter (snapshot 2026-10-04).
DANIELE_LOG = [
    _session("2026-04-05", "Kronthal", [_route("Les cloportes du paradis", "7a+")]),
    _session("2026-06-20", "Berdorf", [_route("Heinz", "6c")]),
    _session("2026-06-28", "Berdorf", [_route("Heinz", "6c"), _route("Nishiki Alien", "7b+")]),
    _session("2026-07-27", "Paderno", [_route("Hale Hop", "7a", style="flash"),
                                       _route("Pubertà", "7b", results=("fell", "fell"))]),
    _session("2026-08-15", "Berdorf", [_route("Infernale", "7b", style="repeat")]),
    _session("2026-08-25", "Snake Valley (Kalymnos)", [_route("Rat Race", "7a+"), _route("Blue Moon", "7b")]),
    _session("2026-08-27", "Snake Valley (Kalymnos)", [_route("Ataraxia", "7b"), _route("Meraki", "7b"),
                                                       _route("Modern Slavery", "7a+", results=("fell",))]),
]
TRIPS = [{"name": "Kalymnos", "start_date": "2026-08-20", "end_date": "2026-09-06"}]


def _state(os_="7a+", rp="8a+", **assessment_extra):
    return {
        "assessment": {"grades": {"lead_max_os": os_, "lead_max_rp": rp,
                                  "boulder_max_os": "7A", "boulder_max_rp": "7C"},
                       **assessment_extra},
        "trips": deepcopy(TRIPS),
    }


# ---------------------------------------------------------------- predicate --

def test_predicate_excludes_repeat_redpoint_project_and_second_appearance():
    seen = set()
    entry = _session("2026-01-01", "Crag", [])
    assert ge.is_onsight_evidence(entry, _route("A", "7a"), seen)
    for style in ("repeat", "redpoint", "project"):
        assert not ge.is_onsight_evidence(entry, _route("B", "7a", style=style), seen)
    assert not ge.is_onsight_evidence(entry, _route("C", "7a", results=("fell", "sent")), seen)
    assert not ge.is_onsight_evidence(entry, _route("D", "7a", results=("topped_out",)), seen)
    seen.add(ge.route_key(entry, _route("A", "7a")))
    assert not ge.is_onsight_evidence(entry, _route(" a ", "7a"), seen)  # same route, B362 key


def test_predicate_lead_only_and_grade_on_ladder():
    seen = set()
    assert not ge.is_onsight_evidence(_session("2026-01-01", "X", [], discipline="boulder"),
                                      _route("A", "7A"), seen)
    # Route discipline wins over the session's.
    assert ge.is_onsight_evidence(_session("2026-01-01", "X", [], discipline="both"),
                                  _route("B", "7a", discipline="lead"), seen)
    assert not ge.is_onsight_evidence(_session("2026-01-01", "X", []), _route("C", "?"), seen)


def test_explicit_onsight_beats_a_generic_name_collision():
    """Review fix: 'Tiro 3' on two different multi-pitches at the same 'spot'.
    The first-appearance rule guards only the inferred case; an explicit
    onsight/flash is the athlete's declaration and still counts."""
    log = [
        _session("2026-08-12", "Montagna — vie lunghe", [_route("Tiro 3", "6b", style="onsight")]),
        _session("2026-09-12", "Montagna — vie lunghe", [_route("Tiro 3", "7b", style="onsight")]),
        _session("2026-09-20", "Other", [_route("X", "7b", style="onsight")]),
    ]
    evidence = ge.collect_onsight_evidence(log)
    keys = [r["key"] for r in evidence]
    assert len(keys) == 3 and len(set(keys)) == 3  # the repeat gets its own key
    assert keys[1] == "montagna — vie lunghe|tiro 3@2026-09-12"
    payload = ge.lead_os_evidence(_state(os_="7a", rp="8a"), log)
    assert payload["proposed"] == "7b"
    # Marking the repeat 'worked' removes only that one.
    left = ge.collect_onsight_evidence(log, worked_keys=[keys[1]])
    assert [r["grade"] for r in left] == ["6b", "7b"]


def test_inferred_repeat_of_a_name_still_does_not_count():
    log = [
        _session("2026-08-12", "Montagna", [_route("Tiro 3", "6b")]),
        _session("2026-09-12", "Montagna", [_route("Tiro 3", "7b")]),  # no style
    ]
    assert [r["grade"] for r in ge.collect_onsight_evidence(log)] == ["6b"]


def test_explicit_onsight_still_needs_one_sent_attempt():
    log = [_session("2026-08-12", "M", [_route("T", "7b", style="onsight")]),
           _session("2026-09-12", "M", [_route("T", "7b", style="flash", results=("fell", "sent"))])]
    assert len(ge.collect_onsight_evidence(log)) == 1


def test_first_appearance_is_chronological_not_file_order():
    log = [
        _session("2026-05-02", "Crag", [_route("Route", "7b")]),
        _session("2026-05-01", "Crag", [_route("Route", "7b", results=("fell",))]),
    ]
    assert ge.collect_onsight_evidence(log) == []


# ---------------------------------------------------------------- proposal --

def test_daniele_log_proposes_7b():
    payload = ge.lead_os_evidence(_state(), DANIELE_LOG)
    assert payload["proposed"] == "7b"
    names = [r["name"] for r in payload["routes"]]
    assert names == ["Nishiki Alien", "Blue Moon", "Ataraxia", "Meraki"]
    assert payload["all_in_trip"] is False  # Nishiki Alien is at home
    assert all(r["explicit"] is False for r in payload["routes"])


def test_one_route_at_a_grade_is_not_enough():
    log = [_session("2026-05-01", "A", [_route("R1", "7c")]),
           _session("2026-05-02", "B", [_route("R2", "7a")])]
    assert ge.supported_grade(ge.collect_onsight_evidence(log)) == "7a"


def test_two_routes_same_day_same_spot_are_not_enough():
    log = [_session("2026-05-01", "A", [_route("R1", "7b"), _route("R2", "7b")])]
    assert ge.supported_grade(ge.collect_onsight_evidence(log)) is None
    log.append(_session("2026-05-01", "B", [_route("R3", "6c")]))
    # Second spot only at 6c: 7b still unsupported, 6c supported by all three.
    assert ge.supported_grade(ge.collect_onsight_evidence(log)) == "6c"


def test_grades_compare_by_index_not_lexicographically():
    log = [_session("2026-05-01", "A", [_route("R1", "7c+")]),
           _session("2026-05-02", "A", [_route("R2", "7c+")]),
           _session("2026-05-03", "A", [_route("R3", "7c")])]
    assert ge.supported_grade(ge.collect_onsight_evidence(log)) == "7c+"


def test_never_downward_and_never_above_redpoint():
    evidence = ge.collect_onsight_evidence(DANIELE_LOG)
    assert ge.propose_grade(evidence, current="7b") is None
    assert ge.propose_grade(evidence, current="7c") is None
    assert ge.propose_grade(evidence, current="7a", redpoint="7a+") == "7a+"


def test_dismissal_blocks_that_grade_not_the_next():
    evidence = ge.collect_onsight_evidence(DANIELE_LOG)
    assert ge.propose_grade(evidence, current="7a+", dismissed="7b") is None
    more = DANIELE_LOG + [_session("2026-09-30", "Berdorf", [_route("New", "7b+")])]
    evidence = ge.collect_onsight_evidence(more)
    assert ge.propose_grade(evidence, current="7a+", dismissed="7b") == "7b+"


def test_worked_routes_leave_the_count():
    payload = ge.lead_os_evidence(
        _state(grade_evidence_worked_routes=["berdorf|nishiki alien"]), DANIELE_LOG,
    )
    assert payload["proposed"] == "7b"
    assert [r["name"] for r in payload["routes"]] == ["Blue Moon", "Ataraxia", "Meraki"]
    assert payload["all_in_trip"] is True  # reported, not enforced


def test_no_log_no_proposal():
    payload = ge.lead_os_evidence(_state(), [])
    assert payload["proposed"] is None and payload["routes"] == []


# ------------------------------------------------------------- outdoor stats --

def test_stats_autodetect_only_counts_first_appearance():
    log = [_session("2026-05-01", "Crag", [_route("Warmup", "6a")]),
           _session("2026-05-02", "Crag", [_route("Warmup", "6a")]),
           _session("2026-05-03", "Crag", [_route("Warmup", "6a")])]
    stats = compute_outdoor_stats(log)
    assert stats["total_routes"] == 3
    assert stats["onsight_pct"] == pytest.approx(33.3, abs=0.1)


def test_stats_top_grade_ranks_plus_above_base():
    log = [_session("2026-05-01", "Crag", [_route("A", "7c"), _route("B", "7c+"), _route("C", "6a")])]
    assert compute_outdoor_stats(log)["top_grade_sent"] == "7c+"


# ------------------------------------------------------------------- API ----

@pytest.fixture
def client(monkeypatch):
    log = deepcopy(DANIELE_LOG)
    monkeypatch.setattr(assessment_router, "load_outdoor_sessions", lambda user_id=None: deepcopy(log))
    state = {
        "assessment": {
            "body": {"weight_kg": 76, "height_cm": 182},
            "experience": {"climbing_years": 10},
            "grades": {"lead_max_os": "7a+", "lead_max_rp": "8a+",
                       "boulder_max_os": "7A", "boulder_max_rp": "7C"},
            "tests": {"max_hang_20mm_5s_total_kg": 110},
            "self_eval": {},
        },
        "goal": {"target_grade": "8b", "current_grade": "8a+", "discipline": "lead",
                 "goal_type": "lead_grade"},
        "performance": {"current_level": {"gym_reference": {"kilter": {"benchmark": {"grade": "7A"}}}}},
        "trips": deepcopy(TRIPS),
        "outdoor_log": [],
    }
    deps.save_state(state, None)
    return TestClient(app)


def _answers(**styles):
    return [{"key": k, "style": v} for k, v in styles.items()]


NISHIKI = "berdorf|nishiki alien"
BLUE = "snake valley (kalymnos)|blue moon"
ATARAXIA = "snake valley (kalymnos)|ataraxia"
MERAKI = "snake valley (kalymnos)|meraki"


def test_get_evidence_endpoint(client):
    r = client.get("/api/assessment/grade-evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["proposed"] == "7b" and body["current"] == "7a+"
    assert {x["key"] for x in body["routes"]} == {NISHIKI, BLUE, ATARAXIA, MERAKI}


def test_confirm_writes_grade_source_current_level_and_keeps_axes(client):
    before = deps.load_state(None)
    profile_before = deepcopy(before["assessment"].get("profile"))
    r = client.post("/api/assessment/confirm-grade", json={
        "decision": "confirm",
        "routes": [{"key": NISHIKI, "style": "worked"}, {"key": BLUE, "style": "onsight"},
                   {"key": ATARAXIA, "style": "onsight"}, {"key": MERAKI, "style": "flash"}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["grade"] == "7b" and body["previous"] == "7a+"
    state = deps.load_state(None)
    a = state["assessment"]
    assert a["grades"]["lead_max_os"] == "7b"
    assert a["grades"]["lead_max_rp"] == "8a+"  # untouched
    src = a["grades_source"]["lead_max_os"]
    assert src["source"] == "outdoor_confirmed" and src["previous"] == "7a+"
    assert {e["key"] for e in src["evidence"]} == {BLUE, ATARAXIA, MERAKI}
    assert a["grade_evidence_worked_routes"] == [NISHIKI]
    level = state["performance"]["current_level"]
    assert level["sport"]["onsight"]["grade"] == "7b"
    assert level["gym_reference"]["kilter"]["benchmark"]["grade"] == "7A"  # kept
    # A270: the OS/RP gap no longer drives any axis — the recompute is a no-op.
    assert a["profile"] == profile_before
    # Nothing left to propose.
    assert client.get("/api/assessment/grade-evidence").json()["proposed"] is None


def test_confirm_needs_two_confirmed_routes_on_two_days_or_spots(client):
    r = client.post("/api/assessment/confirm-grade", json={
        "decision": "confirm",
        "routes": _answers(**{NISHIKI: "worked", BLUE: "worked", ATARAXIA: "onsight", MERAKI: "onsight"}),
    })
    # Ataraxia + Meraki: same day, same crag.
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "insufficient_evidence"
    assert deps.load_state(None)["assessment"]["grades"]["lead_max_os"] == "7a+"


def test_confirm_rejects_grade_the_routes_do_not_support(client):
    r = client.post("/api/assessment/confirm-grade", json={
        "decision": "confirm", "grade": "7b+",
        "routes": _answers(**{BLUE: "onsight", ATARAXIA: "onsight"}),
    })
    assert r.status_code == 422 and r.json()["detail"]["code"] == "not_supported"


def test_confirm_rejects_unknown_route_and_not_above_current(client):
    r = client.post("/api/assessment/confirm-grade", json={
        "decision": "confirm", "routes": _answers(**{"berdorf|heinz x": "onsight"}),
    })
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_route"
    r = client.post("/api/assessment/confirm-grade", json={
        "decision": "confirm", "grade": "7a+",
        "routes": _answers(**{BLUE: "onsight", ATARAXIA: "onsight"}),
    })
    assert r.status_code == 422 and r.json()["detail"]["code"] == "not_above_current"


def test_dismiss_records_grade_and_hides_proposal(client):
    r = client.post("/api/assessment/confirm-grade", json={"decision": "dismiss"})
    assert r.status_code == 200 and r.json()["dismissed"] == "7b"
    state = deps.load_state(None)
    assert state["assessment"]["grade_evidence_dismissed"] == {"lead_max_os": "7b"}
    assert state["assessment"]["grades"]["lead_max_os"] == "7a+"
    assert client.get("/api/assessment/grade-evidence").json()["proposed"] is None
    r = client.post("/api/assessment/confirm-grade", json={"decision": "dismiss"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "no_proposal"


def test_confirm_never_writes_the_outdoor_log(client, monkeypatch):
    from backend.engine import storage

    def _boom(*a, **k):  # pragma: no cover - must not be called
        raise AssertionError("outdoor log written")

    for name in ("append_outdoor_log_line", "remove_outdoor_log_by_date", "delete_all_outdoor_logs"):
        monkeypatch.setattr(storage, name, _boom)
    r = client.post("/api/assessment/confirm-grade", json={
        "decision": "confirm", "routes": _answers(**{BLUE: "onsight", ATARAXIA: "onsight"}),
    })
    assert r.status_code == 200


def test_manual_put_marks_onsight_source_manual(client):
    client.post("/api/assessment/confirm-grade", json={
        "decision": "confirm", "routes": _answers(**{BLUE: "onsight", ATARAXIA: "onsight"}),
    })
    r = client.put("/api/state", json={"assessment": {"grades": {"lead_max_os": "7a"}}})
    assert r.status_code == 200
    src = deps.load_state(None)["assessment"]["grades_source"]["lead_max_os"]
    assert src["source"] == "manual" and src["previous"] == "7b"
