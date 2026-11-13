"""A329 (D288 R8-a) — an outdoor day counts for the technique key ONLY with a
logged measurable target.

``technique_target = {metric: foot_slips_per_go | sample_readjust, value: 0-30,
sample?: ≤ 80 chars}`` — optional, top level of the outdoor entry (one per
crag), written through the existing POST / PUT /api/outdoor/log and the guided
finish. One validator (``outdoor_log.technique_target_of``), read by
``validate_outdoor_entry`` and by ``key_sessions_v1``. Backend only: the app
field is a separate frontend step (R8-b).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.engine import key_sessions_v1 as ks
from backend.engine import outdoor_log as ol
from backend.tests.test_a294_key_sessions import _req, _state

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "backend" / "data" / "schemas" / "outdoor_session_entry.v1.json"
TARGET = {"metric": "foot_slips_per_go", "value": 2, "sample": "Isatis L1"}


def _entry(date="2026-10-03", spot="Berdorf", target=None, grade="6b"):
    e = {"date": date, "spot_name": spot, "discipline": "lead", "duration_minutes": 180,
         "routes": [{"name": "R", "grade": grade, "attempts": [{"result": "sent"}]}]}
    if target is not None:
        e["technique_target"] = copy.deepcopy(target)
    return e


def _rows(*entries):
    return [{"entry": e} for e in entries]


def _week_without_technique():
    st = _state()
    days = st["week_plans"]["2026-09-28"]["weeks"][0]["days"]
    for d in days:
        d["sessions"] = [s for s in d["sessions"] if s.get("session_id") != "technique_focus_gym"]
    return st


# ---------------------------------------------------------------------------
# 1. The validator
# ---------------------------------------------------------------------------

class TestValidator:
    def test_valid(self):
        assert ol.technique_target_of(_entry(target=TARGET)) == {"metric": "foot_slips_per_go", "value": 2.0,
                                                                 "sample": "Isatis L1"}
        assert ol.technique_target_of(_entry(target={"metric": "sample_readjust", "value": 0})) == \
            {"metric": "sample_readjust", "value": 0.0}
        assert ol.technique_target_of(_entry(target={"metric": "foot_slips_per_go", "value": 1.5})) == \
            {"metric": "foot_slips_per_go", "value": 1.5}

    @pytest.mark.parametrize("bad", [
        {"metric": "feet", "value": 2},
        {"metric": "foot_slips_per_go", "value": -1},
        {"metric": "foot_slips_per_go", "value": 31},
        {"metric": "foot_slips_per_go", "value": "2"},
        {"metric": "foot_slips_per_go", "value": True},
        {"metric": "foot_slips_per_go"},
        {"metric": "foot_slips_per_go", "value": 2, "sample": "x" * 81},
        {"metric": "foot_slips_per_go", "value": 2, "extra": 1},
        "2 slips",
    ])
    def test_invalid_never_counts_and_is_rejected(self, bad):
        e = _entry(target=bad)
        assert ol.technique_target_of(e) is None
        e["log_version"] = "outdoor.v2"
        assert any("technique_target" in err for err in ol.validate_outdoor_entry(e))

    def test_absent(self):
        e = dict(_entry(), log_version="outdoor.v2")
        assert ol.technique_target_of(e) is None and ol.validate_outdoor_entry(e) == []


# ---------------------------------------------------------------------------
# 2. The key status
# ---------------------------------------------------------------------------

class TestKeyStatus:
    def test_without_target_the_technique_key_stays_owed(self):
        s = ks.compute_key_status(_week_without_technique(), "2026-10-02", outdoor_rows=_rows(_entry()))
        assert _req(s, "technique")["status"] != "done"

    def test_with_target_the_technique_key_is_done(self):
        s = ks.compute_key_status(_week_without_technique(), "2026-10-04",
                                  outdoor_rows=_rows(_entry(target=TARGET)))
        tech = _req(s, "technique")
        assert tech["status"] == "done" and tech["debt"] == 0
        out = [d for d in tech["done"] if d["date"] == "2026-10-03"]
        assert len(out) == 1
        assert out[0]["evidence"] == "outdoor: 2 scivolate di piede/giro (Isatis L1)"
        assert out[0]["technique_target"] == {"metric": "foot_slips_per_go", "value": 2.0, "sample": "Isatis L1"}
        assert out[0]["name"] == "outdoor Berdorf"
        assert not s["topups"]  # A325: a closed key gets no top-up

    def test_invalid_target_does_not_count(self):
        s = ks.compute_key_status(_week_without_technique(), "2026-10-04",
                                  outdoor_rows=_rows(_entry(target={"metric": "foot_slips_per_go", "value": -3})))
        assert _req(s, "technique")["status"] != "done"

    def test_a_day_of_two_crags_counts_once(self):
        rows = _rows(_entry(spot="B", target={"metric": "sample_readjust", "value": 4}),
                     _entry(spot="A", target=TARGET))
        s = ks.compute_key_status(_week_without_technique(), "2026-10-04", outdoor_rows=rows)
        out = [d for d in _req(s, "technique")["done"] if d["date"] == "2026-10-03"]
        assert len(out) == 1 and out[0]["name"] == "outdoor A"

    def test_no_outdoor_rows_no_credit(self):
        st = _week_without_technique()
        st["outdoor_log"] = [{"date": "2026-10-03", "spot_name": "Berdorf", "load_score": 40}]  # B116 summary
        s = ks.compute_key_status(st, "2026-10-04", outdoor_rows=None)
        assert _req(s, "technique")["status"] != "done"

    def test_try_hard_unchanged(self):
        hard = _entry(target=TARGET, grade="8a")
        hard["routes"][0]["attempts"] = [{"result": "fell"}]
        a = ks.compute_key_status(_state(), "2026-10-02", outdoor_rows=_rows(hard))
        b = ks.compute_key_status(_state(), "2026-10-02", outdoor_rows=_rows(dict(hard, technique_target=None)))
        assert _req(a, "try_hard")["status"] == _req(b, "try_hard")["status"] == "done"

    def test_a_planned_outdoor_day_without_a_log_does_not_count(self):
        st = _week_without_technique()
        day = st["week_plans"]["2026-09-28"]["weeks"][0]["days"][5]
        day["outdoor_spot_name"] = "Berdorf"
        s = ks.compute_key_status(st, "2026-10-02", outdoor_rows=[])
        assert _req(s, "technique")["status"] != "done"

    def test_a_past_week_with_a_target_is_not_empty_for_the_escalation(self):
        req = next(r for r in ks.phase_requirements("strength_power") if r["key"] == "technique")
        assert req.get("outdoor_target_counts") is True
        st = _week_without_technique()
        pos = {"phase_start": "2026-09-21"}
        ws = ks._as_date("2026-10-05")
        cat = ks.load_exercise_catalog()
        without = ks._phase_history(st, req, ws, pos, None, cat, [])
        with_target = ks._phase_history(st, req, ws, pos, None, cat, _rows(_entry(target=TARGET)))
        assert with_target[0] == without[0] and with_target[1] == without[1] - 1

    def test_deterministic_and_pure(self):
        st = _week_without_technique()
        rows = _rows(_entry(target=TARGET))
        before = (copy.deepcopy(st), copy.deepcopy(rows))
        a = ks.compute_key_status(st, "2026-10-04", outdoor_rows=rows)
        b = ks.compute_key_status(st, "2026-10-04", outdoor_rows=rows)
        assert a == b and (st, rows) == before

    def test_catalog_flag(self):
        tech = ks.load_key_catalog()["stimuli"]["technique"]
        assert tech["outdoor_target_counts"] is True and "outdoor_counts" not in tech


class TestCheckInsertion:
    def test_no_key_removed_when_an_outdoor_target_closed_the_technique_key(self):
        st = _state()
        plan = st["week_plans"]["2026-09-28"]
        days = plan["weeks"][0]["days"]
        # The technique session moved to Thursday, still planned (removable).
        tech = days[0]["sessions"].pop(0)
        tech.pop("status", None)
        days[3]["sessions"].append(tech)
        ev = {"event_type": "remove_session", "date": days[3]["date"], "session_ref": "technique_focus_gym"}
        without = ks.check_insertion(st, "2026-09-28", plan=copy.deepcopy(plan), events=[ev], outdoor_rows=[])
        with_target = ks.check_insertion(st, "2026-09-28", plan=copy.deepcopy(plan), events=[ev],
                                         outdoor_rows=_rows(_entry(date="2026-09-29", target=TARGET)))
        removed = lambda r: [c for c in r["key_conflicts"] if c.get("code") == "key_removed"  # noqa: E731
                             and c.get("key") == "technique"]
        assert removed(without)
        assert not removed(with_target)


# ---------------------------------------------------------------------------
# 3. Schema and request models
# ---------------------------------------------------------------------------

class TestSchema:
    def test_models_and_schema_aligned(self):
        from backend.api.models import OutdoorSessionFinishRequest, OutdoorSessionLog, OutdoorTechniqueTarget

        schema = json.loads(SCHEMA_PATH.read_text())
        prop = schema["properties"]["technique_target"]
        assert prop["additionalProperties"] is False
        assert set(OutdoorTechniqueTarget.model_fields) == set(prop["properties"])
        assert tuple(prop["properties"]["metric"]["enum"]) == ol.TECHNIQUE_TARGET_METRICS
        assert prop["properties"]["value"]["maximum"] == ol.TECHNIQUE_TARGET_MAX
        assert prop["properties"]["sample"]["maxLength"] == ol.TECHNIQUE_TARGET_SAMPLE_MAX
        assert "technique_target" in OutdoorSessionLog.model_fields
        assert "technique_target" in OutdoorSessionFinishRequest.model_fields

    def test_jsonschema(self):
        jsonschema = pytest.importorskip("jsonschema")
        v = jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
        good = dict(_entry(target=TARGET), log_version="outdoor.v2")
        assert not list(v.iter_errors(good))
        assert not list(v.iter_errors(dict(_entry(), log_version="outdoor.v2")))
        for bad in ({"metric": "x", "value": 1}, {"metric": "sample_readjust", "value": 40},
                    {"metric": "sample_readjust"}, {"metric": "sample_readjust", "value": 1, "note": "x"}):
            assert list(v.iter_errors(dict(_entry(target=bad), log_version="outdoor.v2"))), bad

    def test_unknown_metric_is_422_at_the_model(self):
        from pydantic import ValidationError

        from backend.api.models import OutdoorSessionLog

        with pytest.raises(ValidationError):
            OutdoorSessionLog(**_entry(target={"metric": "feet", "value": 2}))
        with pytest.raises(ValidationError):
            OutdoorSessionLog(**_entry(target={"metric": "sample_readjust", "value": 2, "extra": 1}))


# ---------------------------------------------------------------------------
# 4. API (file storage) and the B412 merge
# ---------------------------------------------------------------------------

class TestApi:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage

        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({"schema_version": "1.5", "outdoor_spots": [],
                                               "assessment": {"grades": {"lead_max_rp": "8a+"}}}))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _stored(self, day, spot=None):
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        return [s for s in sessions if s["date"] == day and (spot is None or s["spot_name"] == spot)]

    def test_post_saves_it(self):
        res = self.client.post("/api/outdoor/log", json=_entry(target=TARGET))
        assert res.status_code == 200, res.text
        (s,) = self._stored("2026-10-03")
        assert s["technique_target"] == {"metric": "foot_slips_per_go", "value": 2, "sample": "Isatis L1"}

    def test_post_bad_target_is_422_nothing_written(self):
        res = self.client.post("/api/outdoor/log", json=_entry(target={"metric": "feet", "value": 2}))
        assert res.status_code == 422
        assert self._stored("2026-10-03") == []

    def test_put_without_the_field_keeps_it_and_null_clears_it(self):
        assert self.client.post("/api/outdoor/log", json=_entry(target=TARGET)).status_code == 200
        res = self.client.put("/api/outdoor/log", json=_entry())  # the edit form sends no target
        assert res.status_code == 200, res.text
        assert self._stored("2026-10-03")[0]["technique_target"]["value"] == 2
        new = {"metric": "sample_readjust", "value": 5}
        assert self.client.put("/api/outdoor/log", json=_entry(target=new)).status_code == 200
        assert self._stored("2026-10-03")[0]["technique_target"] == {"metric": "sample_readjust", "value": 5}
        assert self.client.put("/api/outdoor/log", json=dict(_entry(), technique_target=None)).status_code == 200
        assert "technique_target" not in self._stored("2026-10-03")[0]

    def test_put_adds_it_to_an_old_log(self):
        assert self.client.post("/api/outdoor/log", json=_entry()).status_code == 200
        assert self.client.put("/api/outdoor/log", json=_entry(target=TARGET)).status_code == 200
        assert self._stored("2026-10-03")[0]["technique_target"]["metric"] == "foot_slips_per_go"

    def test_guided_finish_saves_it(self):
        sid = self.client.post("/api/outdoor/session/start",
                               json={"date": "2026-11-01", "spot_name": "La Crique", "discipline": "lead"}
                               ).json()["session_id"]
        res = self.client.post(f"/api/outdoor/session/{sid}/finish",
                               json={"spot_name": "La Crique", "discipline": "lead", "duration_minutes": 120,
                                     "routes": [{"name": "R", "grade": "6b", "attempts": [{"result": "sent"}]}],
                                     "technique_target": {"metric": "sample_readjust", "value": 3}})
        assert res.status_code == 200, res.text
        assert self._stored("2026-11-01")[0]["technique_target"] == {"metric": "sample_readjust", "value": 3}

    def test_b412_second_session_keeps_the_stored_target_and_replay_changes_nothing(self):
        assert self.client.post("/api/outdoor/log", json=_entry(target=TARGET)).status_code == 200
        second = _entry(target={"metric": "sample_readjust", "value": 9})
        second["routes"] = [{"name": "Other", "grade": "6c", "attempts": [{"result": "sent"}]}]
        assert self.client.post("/api/outdoor/log", json=second).status_code == 200
        (s,) = self._stored("2026-10-03")
        assert s["technique_target"]["metric"] == "foot_slips_per_go"   # the stored one wins
        assert len(s["routes"]) == 2
        before = copy.deepcopy(s)
        assert self.client.post("/api/outdoor/log", json=second).status_code == 200  # replay
        assert self._stored("2026-10-03") == [before]

    def test_b412_merge_fills_a_missing_target(self):
        assert self.client.post("/api/outdoor/log", json=_entry()).status_code == 200
        second = _entry(target=TARGET)
        second["routes"] = [{"name": "Other", "grade": "6c", "attempts": [{"result": "sent"}]}]
        assert self.client.post("/api/outdoor/log", json=second).status_code == 200
        assert self._stored("2026-10-03")[0]["technique_target"]["sample"] == "Isatis L1"


class TestAthleteContext:
    def test_the_outdoor_evidence_shows_in_the_technique_line(self):
        from backend.engine import athlete_context as ac

        ctx = ac.build_athlete_context(_week_without_technique(), "2026-10-04",
                                       outdoor_rows=_rows(_entry(target=TARGET)),
                                       include_next_week=False, with_proposals=False)
        tech = next(r for r in ctx["key_sessions"]["requirements"] if r["key"] == "technique")
        assert tech["status"] == "done"
        assert "[outdoor: 2 scivolate di piede/giro (Isatis L1)]" in ac.render_text(ctx)
