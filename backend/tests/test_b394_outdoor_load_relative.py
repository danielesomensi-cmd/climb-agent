"""B394 — outdoor load relative to the athlete's max, only for logs from 2026-10-17.

Real case (Berdorf, 17/10): 6c sent, 6b+ sent, Isatis 7c+ project fell ×2 scored
22 with B327 — under the warm-up 6c, and nowhere near the replanner's ripple
threshold (65). Daniele's decisions: relative weights, mean of the two hardest
attempts, falls count fully, and no recalculation of the past.
"""

from __future__ import annotations

import json

import pytest

from backend.engine.outdoor_log import (
    OUTDOOR_LOAD_V2_FROM,
    compute_outdoor_load_score,
    outdoor_load_ref_grade,
    stamp_load_ref_grade,
)
from backend.engine.replanner_v1 import OUTDOOR_RIPPLE_THRESHOLD

STATE = {"assessment": {"grades": {"lead_max_rp": "8a+", "boulder_max_rp": "7C"}}}


def _isatis_day(date: str = "2026-10-17", **extra) -> dict:
    entry = {
        "date": date, "spot_name": "Berdorf", "discipline": "lead", "duration_minutes": 240,
        "routes": [
            {"name": "Heinz", "grade": "6c", "attempts": [{"result": "sent"}]},
            {"name": "Bibi", "grade": "6b+", "attempts": [{"result": "sent"}]},
            {"name": "Isatis", "grade": "7c+", "style": "project",
             "attempts": [{"result": "fell"}, {"result": "fell"}]},
        ],
    }
    entry.update(extra)
    return entry


# ─── formula ────────────────────────────────────────────────────────────────

def test_unstamped_log_keeps_b327():
    assert compute_outdoor_load_score(_isatis_day()) == 22


def test_project_day_near_max_crosses_the_ripple_threshold():
    score = compute_outdoor_load_score(_isatis_day(load_ref_grade="8a+"))
    assert score == 69
    assert score >= OUTDOOR_RIPPLE_THRESHOLD


def test_falls_count_like_sends():
    sent = _isatis_day(load_ref_grade="8a+")
    sent["routes"][2]["attempts"] = [{"result": "sent"}, {"result": "sent"}]
    assert compute_outdoor_load_score(sent) == compute_outdoor_load_score(_isatis_day(load_ref_grade="8a+"))


def test_warmups_do_not_dilute_the_intensity():
    base = compute_outdoor_load_score(_isatis_day(load_ref_grade="8a+"))
    more = _isatis_day(load_ref_grade="8a+")
    more["routes"].insert(0, {"name": "w", "grade": "6a", "attempts": [{"result": "sent"}]})
    assert compute_outdoor_load_score(more) >= base


def test_easy_day_stays_low_and_single_route_is_tiny():
    multipitch = {"date": "2026-10-20", "load_ref_grade": "8a+", "routes": [
        {"grade": g, "attempts": [{"result": "sent"}]} for g in ("6a", "6a+", "6b", "6a", "6b", "6a+", "6a")]}
    assert compute_outdoor_load_score(multipitch) == 17  # 20 in the 12-14/08 logs, tagged onsight
    single = {"date": "2026-10-20", "load_ref_grade": "8a+",
              "routes": [{"grade": "6b+", "attempts": [{"result": "sent"}]}]}
    assert compute_outdoor_load_score(single) == 6


def test_reference_is_frozen_in_the_log():
    """A higher max later does not rewrite a stamped day: the log carries its own reference."""
    day = _isatis_day(load_ref_grade="8a+")
    assert compute_outdoor_load_score(day) == compute_outdoor_load_score(json.loads(json.dumps(day)))
    assert compute_outdoor_load_score(_isatis_day(load_ref_grade="8b")) < compute_outdoor_load_score(day)


def test_capped_at_85_and_unknown_grade_is_safe():
    day = {"load_ref_grade": "8a+", "routes": [
        {"grade": "8a", "attempts": [{"result": "fell"}] * 9}, {"grade": "?", "attempts": [{}]}]}
    assert compute_outdoor_load_score(day) == 85


# ─── stamping ───────────────────────────────────────────────────────────────

def test_ref_grade_comes_from_lead_max_rp():
    assert outdoor_load_ref_grade(STATE) == "8a+"
    assert outdoor_load_ref_grade({}) is None
    assert outdoor_load_ref_grade({"assessment": {"grades": {"lead_max_rp": "V5"}}}) is None


@pytest.mark.parametrize("entry,expected", [
    (_isatis_day(OUTDOOR_LOAD_V2_FROM), "8a+"),
    (_isatis_day("2026-11-01"), "8a+"),
    (_isatis_day("2026-10-16"), None),               # the past is not recalculated
    (_isatis_day(discipline="boulder"), None),       # lead ladder only
])
def test_stamp_rules(entry, expected):
    e = dict(entry)
    stamp_load_ref_grade(e, STATE)
    assert e.get("load_ref_grade") == expected


def test_stamp_without_a_max_leaves_the_log_on_b327():
    e = _isatis_day()
    stamp_load_ref_grade(e, {})
    assert "load_ref_grade" not in e


def test_an_edit_keeps_the_first_reference():
    e = _isatis_day()
    stamp_load_ref_grade(e, {"assessment": {"grades": {"lead_max_rp": "8b"}}}, previous={"load_ref_grade": "8a+"})
    assert e["load_ref_grade"] == "8a+"


# ─── API ────────────────────────────────────────────────────────────────────

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

    def _body(self, date: str) -> dict:
        e = _isatis_day(date)
        return {k: e[k] for k in ("date", "spot_name", "discipline", "duration_minutes", "routes")}

    def _stored(self, date: str) -> dict:
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        return next(s for s in sessions if s["date"] == date)

    def test_post_from_cutover_is_stamped_and_scored_v2(self):
        assert self.client.post("/api/outdoor/log", json=self._body("2026-10-17")).status_code == 200
        stored = self._stored("2026-10-17")
        assert stored["load_ref_grade"] == "8a+"
        assert compute_outdoor_load_score(stored) == 69

    def test_post_before_cutover_stays_b327(self):
        assert self.client.post("/api/outdoor/log", json=self._body("2026-10-10")).status_code == 200
        stored = self._stored("2026-10-10")
        assert "load_ref_grade" not in stored
        assert compute_outdoor_load_score(stored) == 22

    def test_put_keeps_the_stamp_even_after_a_grade_bump(self):
        self.client.post("/api/outdoor/log", json=self._body("2026-10-17"))
        state = json.loads(self.state_path.read_text())
        state["assessment"]["grades"]["lead_max_rp"] = "8b"
        self.state_path.write_text(json.dumps(state))
        res = self.client.put("/api/outdoor/log", json=self._body("2026-10-17"))
        assert res.status_code == 200, res.text
        assert self._stored("2026-10-17")["load_ref_grade"] == "8a+"
        assert res.json()["load_score"] == 69

    def test_put_on_a_past_log_does_not_stamp_it(self):
        self.client.post("/api/outdoor/log", json=self._body("2026-10-10"))
        res = self.client.put("/api/outdoor/log", json=self._body("2026-10-10"))
        assert res.status_code == 200
        assert "load_ref_grade" not in self._stored("2026-10-10")
        assert res.json()["load_score"] == 22
