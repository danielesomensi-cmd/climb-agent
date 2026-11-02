"""B412 — a second session at the same crag on the same day replaced the first.

Since B341 a day holds one ``outdoor_logs`` row per crag (key date +
spot_name) and every write upserted that row. A morning and an afternoon at
the same crag, or a live session reopened after «Undo completion» (B403), kept
only the last session's routes (B-OUTDOOR-EDIT-RESIDUALS point 3).

Fix: ``append_outdoor_session`` folds the new session into the crag's log —
what one session lasting both would have saved — and recognises a replayed
write (offline outbox, lost response) by its fingerprint, so a retry never adds
the routes twice.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from backend.engine import outdoor_log as ol
from backend.engine import storage_supabase
from backend.engine.outdoor_log import (
    SESSION_KEYS,
    compute_outdoor_load_score,
    merge_outdoor_sessions,
    outdoor_session_fingerprint,
)
from backend.tests.test_b341_multi_crag_outdoor import _mk_plan
from backend.tests.test_b401_outdoor_edit_keeps_other_crag import _FakeSupabase

DAY = "2026-11-01"
USER = "u-b412"


def _route(name, grade="7a", *results, style=None, at=None, role=None):
    attempts = []
    for i, r in enumerate(results or ("sent",)):
        a = {"result": r}
        if at:
            a["logged_at"] = f"{DAY}T{at[i]}:00.000Z"
        if role:
            a["rope_role"] = role
        attempts.append(a)
    route = {"name": name, "grade": grade, "attempts": attempts}
    if style:
        route["style"] = style
    return route


def _entry(routes, spot="Presles", day=DAY, minutes=120, **extra):
    e = {
        "log_version": "outdoor.v2",
        "date": day,
        "spot_name": spot,
        "discipline": "lead",
        "duration_minutes": minutes,
        "routes": routes,
    }
    e.update(extra)
    return e


# ── merge_outdoor_sessions (pure) ───────────────────────────────────────


class TestMerge:
    def test_new_routes_are_appended_and_durations_add_up(self):
        morning = _entry([_route("Cancer"), _route("Tabou", "6c")], minutes=180, notes="Mattina al sole")
        afternoon = _entry([_route("Les Barbares", "7b", "fell")], minutes=90, notes="Pomeriggio")
        merged = merge_outdoor_sessions(morning, afternoon)
        assert [r["name"] for r in merged["routes"]] == ["Cancer", "Tabou", "Les Barbares"]
        assert merged["duration_minutes"] == 270
        assert merged["notes"] == "Mattina al sole\n\nPomeriggio"

    def test_same_route_fall_then_send_is_one_redpoint_not_a_flash(self):
        # The afternoon logger saw the route fresh and tagged the send a flash.
        morning = _entry([_route("Cancer", "7b", "fell", "fell", style="project")])
        afternoon = _entry([_route("Cancer", "7b", "sent", style="flash")])
        merged = merge_outdoor_sessions(morning, afternoon)
        assert len(merged["routes"]) == 1
        route = merged["routes"][0]
        assert [a["result"] for a in route["attempts"]] == ["fell", "fell", "sent"]
        assert route["style"] == "project"  # the stored style wins, as in the live logger

        morning = _entry([_route("Cancer", "7b", "fell")])
        merged = merge_outdoor_sessions(morning, afternoon)
        assert merged["routes"][0]["style"] == "redpoint"

    def test_a_morning_flash_stays_and_the_later_go_is_a_repeat(self):
        # Review: folding the afternoon go into it made the flash a redpoint
        # with two attempts — and A292 evidence needs a single attempt.
        morning = _entry([_route("Cancer", "7b", "sent", style="flash")])
        afternoon = _entry([_route("Cancer", "7b", "sent", role="second")])
        routes = merge_outdoor_sessions(morning, afternoon)["routes"]
        assert len(routes) == 2
        assert routes[0]["style"] == "flash" and len(routes[0]["attempts"]) == 1
        assert routes[1]["style"] == "repeat"
        assert routes[1]["attempts"] == [{"result": "sent", "rope_role": "second"}]

    def test_an_inferred_first_go_stays_too(self):
        # One lead send with no style is inferred first-go evidence (A292).
        morning = _entry([_route("Cancer", "7b", "sent")])
        afternoon = _entry([_route("Cancer", "7b", "fell", "sent", style="redpoint")])
        routes = merge_outdoor_sessions(morning, afternoon)["routes"]
        assert [len(r["attempts"]) for r in routes] == [1, 2]
        assert "style" not in routes[0]
        assert routes[1]["style"] == "repeat"

    def test_a_later_flash_that_arrives_first_is_no_first_go(self):
        # The afternoon (logged as a flash) synced before the morning's fall.
        afternoon = _entry([_route("Cancer", "7b", "sent", style="flash", at=["15:10"])])
        morning = _entry([_route("Cancer", "7b", "fell", at=["09:30"])])
        routes = merge_outdoor_sessions(afternoon, morning)["routes"]
        assert len(routes) == 1
        assert [a["result"] for a in routes[0]["attempts"]] == ["fell", "sent"]
        assert routes[0]["style"] == "redpoint"

    def test_placeholder_names_never_fold(self):
        # The live logger names unnamed routes «problem 1», «problem 2»… from 1
        # in every session: two different boulders, not one.
        morning = _entry([_route("problem 1", "6a", style="flash"), _route("problem 2", "6b", "fell")],
                         discipline="boulder")
        afternoon = _entry([_route("problem 1", "6a"), _route("Problem 2", "6b", "sent")],
                           discipline="boulder")
        routes = merge_outdoor_sessions(morning, afternoon)["routes"]
        assert len(routes) == 4
        assert routes[0]["style"] == "flash" and len(routes[0]["attempts"]) == 1
        assert [a["result"] for a in routes[1]["attempts"]] == ["fell"]

    def test_clean_second_is_no_redpoint(self):
        # A324: a clean go on second is not a send — no redpoint style.
        morning = _entry([_route("Cancer", "7b", "fell", role="second")])
        afternoon = _entry([_route("Cancer", "7b", "sent", role="second")])
        route = merge_outdoor_sessions(morning, afternoon)["routes"][0]
        assert "style" not in route

    def test_attempts_follow_logged_at_when_the_afternoon_arrives_first(self):
        afternoon = _entry([_route("Cancer", "7b", "sent", at=["15:10"])])
        morning = _entry([_route("Cancer", "7b", "fell", "fell", at=["09:30", "10:05"])])
        route = merge_outdoor_sessions(afternoon, morning)["routes"][0]
        assert [a["result"] for a in route["attempts"]] == ["fell", "fell", "sent"]

    def test_same_name_other_grade_stays_a_separate_route(self):
        morning = _entry([_route("Cancer", "7b")])
        afternoon = _entry([_route("Cancer", "6a")])
        merged = merge_outdoor_sessions(morning, afternoon)
        assert [(r["name"], r["grade"]) for r in merged["routes"]] == [("Cancer", "7b"), ("Cancer", "6a")]

    def test_route_name_match_ignores_case_and_spaces(self):
        morning = _entry([_route("Cancer", "7b", "fell")])
        afternoon = _entry([_route(" cancer ", "7B", "sent")])
        merged = merge_outdoor_sessions(morning, afternoon)
        assert len(merged["routes"]) == 1
        assert merged["routes"][0]["name"] == "Cancer"

    def test_the_new_sessions_own_routes_are_not_folded_together(self):
        morning = _entry([_route("Tabou", "6c")])
        afternoon = _entry([_route("Bibi", "6a"), _route("Bibi", "6a", "fell")])
        merged = merge_outdoor_sessions(morning, afternoon)
        assert [r["name"] for r in merged["routes"]] == ["Tabou", "Bibi", "Bibi"]

    def test_stored_keys_stay_and_gaps_are_filled(self):
        morning = _entry(
            [_route("Cancer")], day_type="project", load_ref_grade="7c",
            conditions={"temperature": 12}, spot_id="presles",
        )
        afternoon = _entry(
            [_route("Tabou", "6c")], day_type="volume", load_ref_grade="8a",
            conditions={"temperature": 19}, overall_feeling="tired",
        )
        merged = merge_outdoor_sessions(morning, afternoon)
        assert merged["day_type"] == "project"
        assert merged["load_ref_grade"] == "7c"  # B394: the first stamp stays
        assert merged["conditions"] == {"temperature": 12}
        assert merged["spot_id"] == "presles"
        assert merged["overall_feeling"] == "tired"

    def test_two_disciplines_make_both(self):
        morning = _entry([_route("Cancer")])
        afternoon = _entry([_route("Bloc", "6a")], discipline="boulder")
        assert merge_outdoor_sessions(morning, afternoon)["discipline"] == "both"

    def test_same_notes_are_not_repeated(self):
        morning = _entry([_route("Cancer")], notes="Caldo")
        afternoon = _entry([_route("Tabou", "6c")], notes="Caldo")
        assert merge_outdoor_sessions(morning, afternoon)["notes"] == "Caldo"

    def test_replays_are_recognised(self):
        morning = _entry([_route("Cancer")])
        afternoon = _entry([_route("Tabou", "6c")], minutes=60)
        # The first session written again (its response was lost).
        assert merge_outdoor_sessions(morning, json.loads(json.dumps(morning))) is None
        merged = merge_outdoor_sessions(morning, afternoon)
        assert merged[SESSION_KEYS] == [
            outdoor_session_fingerprint(morning), outdoor_session_fingerprint(afternoon),
        ]
        # After the merge, either session replayed adds nothing.
        assert merge_outdoor_sessions(merged, afternoon) is None
        assert merge_outdoor_sessions(merged, morning) is None
        # A third, different session still joins.
        evening = _entry([_route("Bibi", "6a")], minutes=30)
        merged3 = merge_outdoor_sessions(merged, evening)
        assert len(merged3[SESSION_KEYS]) == 3
        assert merged3["duration_minutes"] == 210

    def test_fingerprint_ignores_server_stamps(self):
        a = _entry([_route("Cancer")])
        b = dict(a, log_version="outdoor.v1", load_ref_grade="7c")
        assert outdoor_session_fingerprint(a) == outdoor_session_fingerprint(b)

    def test_inputs_are_not_mutated(self):
        morning = _entry([_route("Cancer", "7b", "fell")])
        afternoon = _entry([_route("Cancer", "7b", "sent")])
        before = json.dumps([morning, afternoon], sort_keys=True)
        merge_outdoor_sessions(morning, afternoon)
        assert json.dumps([morning, afternoon], sort_keys=True) == before


# ── File backend ────────────────────────────────────────────────────────


class TestFileBackend:
    @pytest.fixture(autouse=True)
    def _storage(self, tmp_path, monkeypatch):
        from backend.engine import storage

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")

    def _day(self):
        return {s["spot_name"]: s for s in ol.load_outdoor_sessions(USER) if s["date"] == DAY}

    def test_second_session_same_crag_keeps_the_first_routes(self):
        ol.append_outdoor_session(_entry([_route("Cancer", "7b", "fell")], minutes=180), USER)
        ol.append_outdoor_session(_entry([_route("Tabou", "6c")], spot="Coquibus"), USER)
        saved = _entry([_route("Cancer", "7b", "sent"), _route("Bibi", "6a")], minutes=60)
        ol.append_outdoor_session(saved, USER)

        day = self._day()
        assert set(day) == {"Presles", "Coquibus"}
        presles = day["Presles"]
        assert [r["name"] for r in presles["routes"]] == ["Cancer", "Bibi"]
        assert [a["result"] for a in presles["routes"][0]["attempts"]] == ["fell", "sent"]
        assert presles["duration_minutes"] == 240
        # The caller's entry is now the crag's whole log (plan sync, load).
        assert saved == presles
        # The other crag of the day is untouched.
        assert [r["name"] for r in day["Coquibus"]["routes"]] == ["Tabou"]

    def test_replay_adds_nothing(self):
        first = _entry([_route("Cancer", "7b", "fell")])
        second = _entry([_route("Bibi", "6a")], minutes=45)
        ol.append_outdoor_session(json.loads(json.dumps(first)), USER)
        ol.append_outdoor_session(json.loads(json.dumps(second)), USER)
        once = self._day()["Presles"]
        ol.append_outdoor_session(json.loads(json.dumps(second)), USER)
        ol.append_outdoor_session(json.loads(json.dumps(first)), USER)
        assert self._day()["Presles"] == once

    def test_every_new_log_records_its_own_key(self):
        entry = _entry([_route("Cancer")])
        ol.append_outdoor_session(entry, USER)
        assert len(self._day()["Presles"][SESSION_KEYS]) == 1

    def test_replay_matches_even_if_the_names_were_aligned_differently(self, monkeypatch):
        # Review: the key was taken after canonicalize_route_names, whose
        # result depends on the other days (and on that read succeeding).
        ol.append_outdoor_session(_entry([_route("Cancer", "7b", "fell")], day="2026-10-31"), USER)
        body = _entry([_route("cancer", "7b", "fell", "fell")])
        with monkeypatch.context() as m:
            m.setattr(ol, "_history_for_names", lambda uid: [])
            ol.append_outdoor_session(json.loads(json.dumps(body)), USER)
        assert self._day()["Presles"]["routes"][0]["name"] == "cancer"
        ol.append_outdoor_session(json.loads(json.dumps(body)), USER)  # history read works now
        log = self._day()["Presles"]
        assert len(log["routes"]) == 1 and len(log["routes"][0]["attempts"]) == 2

    def test_unreadable_day_writes_nothing(self, monkeypatch):
        ol.append_outdoor_session(_entry([_route("Cancer")]), USER)
        before = self._day()

        def _down(*a, **k):
            raise RuntimeError("storage down")

        with monkeypatch.context() as m:
            m.setattr(ol, "outdoor_sessions_on", _down)
            with pytest.raises(OSError):
                ol.append_outdoor_session(_entry([_route("Bibi", "6a")]), USER)
        assert self._day() == before


# ── Supabase backend (fake client, same as B401) ────────────────────────


class TestSupabaseBackend:
    @pytest.fixture(autouse=True)
    def _storage(self, monkeypatch):
        self.db = _FakeSupabase()
        monkeypatch.setattr(storage_supabase, "_sb", lambda: self.db)
        monkeypatch.setattr(ol, "storage", storage_supabase)
        monkeypatch.setattr(storage_supabase, "_url", "")
        monkeypatch.setattr(storage_supabase.time, "sleep", lambda s: None)

    def test_second_session_updates_the_same_row_with_both(self):
        ol.append_outdoor_session(_entry([_route("Cancer", "7b", "fell")]), USER)
        row_id = self.db.rows[0]["id"]
        ol.append_outdoor_session(_entry([_route("Cancer", "7b", "sent")], minutes=60), USER)

        assert len(self.db.rows) == 1
        row = self.db.rows[0]
        assert row["id"] == row_id
        assert [a["result"] for a in row["entry"]["routes"][0]["attempts"]] == ["fell", "sent"]
        assert row["entry"]["duration_minutes"] == 180

    def test_replay_after_merge_keeps_the_row(self):
        second = _entry([_route("Bibi", "6a")], minutes=60)
        ol.append_outdoor_session(_entry([_route("Cancer")]), USER)
        ol.append_outdoor_session(json.loads(json.dumps(second)), USER)
        once = json.loads(json.dumps(self.db.rows[0]["entry"]))
        ol.append_outdoor_session(json.loads(json.dumps(second)), USER)
        assert self.db.rows[0]["entry"] == once


# ── API: live session reopened, manual log, outbox replay ───────────────


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class TestApi:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage

        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({"schema_version": "1.5", "outdoor_spots": []}))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)
        self.monday = _monday(date.today())
        self.day = self.monday.isoformat()

    def _with_plan(self):
        state = json.loads(self.state_path.read_text())
        state["week_plans"] = {self.day: _mk_plan(self.monday)}
        self.state_path.write_text(json.dumps(state))

    def _plan_day(self):
        state = json.loads(self.state_path.read_text())
        plan = state["week_plans"][self.day]
        return next(d for d in plan["weeks"][0]["days"] if d["date"] == self.day)

    def _live(self, routes, minutes):
        start = self.client.post("/api/outdoor/session/start", json={
            "date": self.day, "spot_name": "Presles", "discipline": "lead",
        })
        assert start.status_code == 200, start.text
        fin = self.client.post(f"/api/outdoor/session/{start.json()['session_id']}/finish", json={
            "spot_name": "Presles", "discipline": "lead", "routes": routes,
            "duration_minutes": minutes,
        })
        assert fin.status_code == 200, fin.text
        return fin.json()

    def _logs(self):
        r = self.client.get("/api/outdoor/sessions")
        assert r.status_code == 200
        return [s for s in r.json()["sessions"] if s["date"] == self.day]

    def test_live_session_reopened_keeps_the_morning(self):
        self._with_plan()
        self._live([_route("Cancer", "7b", "fell", "fell")], 150)
        res = self._live([_route("Cancer", "7b", "sent"), _route("Tabou", "6c")], 90)

        logs = self._logs()
        assert len(logs) == 1
        log = logs[0]
        assert [r["name"] for r in log["routes"]] == ["Cancer", "Tabou"]
        assert [a["result"] for a in log["routes"][0]["attempts"]] == ["fell", "fell", "sent"]
        assert log["routes"][0]["style"] == "redpoint"
        assert log["duration_minutes"] == 240
        # The finish reports the crag's load, and the plan day carries it.
        assert res["load_score"] == compute_outdoor_load_score(log)
        day = self._plan_day()
        assert day["outdoor_spot_name"] == "Presles"
        assert day["outdoor_load_score"] == compute_outdoor_load_score(log)

    def test_manual_log_replayed_by_the_outbox_adds_nothing(self):
        morning = _entry([_route("Cancer", "7b", "fell")], day=self.day, minutes=120)
        afternoon = _entry([_route("Tabou", "6c")], day=self.day, minutes=60)
        for body in (morning, afternoon):
            body.pop("log_version")
        for body in (morning, afternoon, afternoon, morning):
            r = self.client.post("/api/outdoor/log", json=body)
            assert r.status_code == 200, r.text

        logs = self._logs()
        assert len(logs) == 1
        assert [r["name"] for r in logs[0]["routes"]] == ["Cancer", "Tabou"]
        assert logs[0]["duration_minutes"] == 180

    def test_replay_after_a_pencil_edit_of_a_single_session_adds_nothing(self):
        # Review: a one-session log had no key of its own, so after an edit
        # the replay of its POST (response lost, outbox) doubled everything.
        morning = _entry([_route("Cancer", "7b", "fell")], day=self.day, notes="x")
        morning.pop("log_version")
        assert self.client.post("/api/outdoor/log", json=morning).status_code == 200
        edit = {k: v for k, v in self._logs()[0].items()
                if k in ("date", "spot_name", "discipline", "duration_minutes", "routes")}
        edit["notes"] = "x fixed"
        assert self.client.put("/api/outdoor/log", json=edit).status_code == 200

        assert self.client.post("/api/outdoor/log", json=morning).status_code == 200
        log = self._logs()[0]
        assert log["notes"] == "x fixed"
        assert log["duration_minutes"] == 120
        assert [a["result"] for a in log["routes"][0]["attempts"]] == ["fell"]

    def test_pencil_edit_keeps_the_merge_record(self):
        morning = _entry([_route("Cancer", "7b", "fell")], day=self.day)
        afternoon = _entry([_route("Tabou", "6c")], day=self.day, minutes=60)
        for body in (morning, afternoon):
            body.pop("log_version")
            assert self.client.post("/api/outdoor/log", json=body).status_code == 200
        keys = self._logs()[0][SESSION_KEYS]

        # The edit form sends routes and notes, never merged_session_keys.
        edit = {k: v for k, v in self._logs()[0].items()
                if k in ("date", "spot_name", "discipline", "duration_minutes", "routes")}
        edit["routes"][1]["grade"] = "7a"
        r = self.client.put("/api/outdoor/log", json=edit)
        assert r.status_code == 200, r.text
        assert self._logs()[0][SESSION_KEYS] == keys

        # A late replay of the afternoon still adds nothing.
        assert self.client.post("/api/outdoor/log", json=afternoon).status_code == 200
        log = self._logs()[0]
        assert [(r["name"], r["grade"]) for r in log["routes"]] == [("Cancer", "7b"), ("Tabou", "7a")]
