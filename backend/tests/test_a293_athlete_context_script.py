"""A293 — scripts/athlete_context.py is READ-ONLY and its --simulate is faithful.

- ``main(--state-file)`` works with every write path patched to explode
  (``deps.save_state``, ``storage_file.write_state``) and no subprocess
  (no network): exit 0, text and ``--json`` output.
- The live reader issues ONLY explicit ``curl -X GET`` requests with no body
  flag, and refuses anything else; the right tables/filters are read.
- No state → exit 3; bad arguments → exit 1.
- ``--simulate`` (max hang custom on Tue 06/10 evening) reports the downgrade
  of the KEY power_contact_gym on Wed 07/10 that ``apply_events`` performs
  silently, detects slot collisions, marks a key removed by ``--replace``, and
  never modifies the state file.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("a293_athlete_context_cli", REPO_ROOT / "scripts" / "athlete_context.py")
cli = importlib.util.module_from_spec(_spec)
sys.modules["a293_athlete_context_cli"] = cli
_spec.loader.exec_module(cli)  # type: ignore[union-attr]

from backend.tests.test_a293_athlete_context import _outdoor, _state  # noqa: E402

TODAY = "2026-10-04"
DRAFT = {"name": "Hang test", "exercises": [{"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7,
                                              "load_kg": 20}]}


def _boom(*a, **k):
    raise AssertionError("write/network path called by a read-only script")


@pytest.fixture
def no_writes(monkeypatch):
    from backend.api import deps
    from backend.engine import storage_file

    monkeypatch.setattr(deps, "save_state", _boom)
    monkeypatch.setattr(storage_file, "write_state", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)


@pytest.fixture
def files(tmp_path):
    st = tmp_path / "state.json"
    st.write_text(json.dumps([{"state": _state()}]), encoding="utf-8")  # Supabase row shape
    od = tmp_path / "outdoor.json"
    od.write_text(json.dumps(_outdoor()), encoding="utf-8")
    dr = tmp_path / "draft.json"
    dr.write_text(json.dumps(DRAFT), encoding="utf-8")
    return {"state": st, "outdoor": od, "draft": dr}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class TestReadOnlyMain:
    def test_text_output(self, files, no_writes, capsys):
        rc = cli.main(["--state-file", str(files["state"]), "--outdoor-file", str(files["outdoor"]),
                       "--date", TODAY])
        out = capsys.readouterr().out
        assert rc == cli.EXIT_OK
        assert "## Carichi ancorati oggi" in out and "Fonte: file locale" in out
        assert "## Note atleta" in out  # the docs/training/athlete_plan.md block

    def test_json_output(self, files, no_writes, capsys):
        rc = cli.main(["--state-file", str(files["state"]), "--date", TODAY, "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0 and payload["context"]["as_of"] == TODAY
        assert payload["context"]["key_sessions"]["source"] == "a294"

    def test_no_state_exit_3(self, tmp_path, no_writes):
        empty = tmp_path / "empty.json"
        empty.write_text("{}", encoding="utf-8")
        assert cli.main(["--state-file", str(empty), "--date", TODAY]) == cli.EXIT_NO_STATE

    def test_bad_args(self, files, no_writes):
        assert cli.main(["--state-file", str(files["state"]), "--date", "04/10/2026"]) == cli.EXIT_ERROR
        assert cli.main(["--state-file", str(files["state"]), "--simulate", str(files["draft"])]) == cli.EXIT_ERROR


class TestLiveReaderIsGetOnly:
    def test_command_is_explicit_get_without_body(self):
        cmd = cli.build_get_command("https://x.supabase.co", "KEY", "users",
                                    [("select", "state"), ("user_id", "eq.u1")])
        assert cmd[0] == "curl" and cmd[cmd.index("-X") + 1] == "GET"
        assert not cli._FORBIDDEN_CURL_FLAGS.intersection(cmd)
        assert cmd[cmd.index("GET") + 1].startswith("https://x.supabase.co/rest/v1/users?")

    def test_refuses_non_get(self, monkeypatch):
        monkeypatch.setattr(cli, "build_get_command",
                            lambda *a, **k: ["curl", "-X", "POST", "u", "-d", "{}"])
        monkeypatch.setattr(subprocess, "run", _boom)
        with pytest.raises(RuntimeError, match="non-GET"):
            cli.rest_get("https://x", "k", "users", [])

    def test_fetch_live_reads_the_three_tables(self, monkeypatch):
        calls = []

        def fake_get(base, key, table, params):
            calls.append((table, dict(params) if table == "users" else params))
            if table == "users":
                return [{"state": {"goal": {}}, "updated_at": "2026-10-04T10:00:00+00:00"}]
            return []

        monkeypatch.setattr(cli, "load_credentials", lambda: ("https://x", "k"))
        monkeypatch.setattr(cli, "rest_get", fake_get)
        from datetime import date

        data = cli.fetch_live("u1", date(2026, 10, 4))
        assert [c[0] for c in calls] == ["users", "week_archive", "outdoor_logs"]
        assert calls[0][1]["user_id"] == "eq.u1"
        assert ("week_start", "gte.2026-06-08") in calls[1][1]
        assert data["state"] == {"goal": {}} and data["archived_weeks"] == []

    def test_fetch_live_no_user(self, monkeypatch):
        monkeypatch.setattr(cli, "load_credentials", lambda: ("https://x", "k"))
        monkeypatch.setattr(cli, "rest_get", lambda *a, **k: [])
        from datetime import date

        assert cli.fetch_live("u1", date(2026, 10, 4))["state"] is None

    def test_age_line(self):
        from datetime import datetime, timezone

        now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
        assert "30 min fa" in cli._age_line("2026-10-04T11:30:00+00:00", now)
        assert cli._age_line(None) == "Fonte: file locale"


class TestSimulate:
    def test_key_downgrade_reported_and_file_untouched(self, files, no_writes, capsys):
        before = _sha(files["state"])
        rc = cli.main(["--state-file", str(files["state"]), "--date", TODAY, "--simulate", str(files["draft"]),
                       "--target-date", "2026-10-06", "--slot", "evening"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "2026-10-07 evening: power_contact_gym → regeneration_easy — CHIAVE limit_power" in out
        assert "una sessione CHIAVE verrebbe declassata" in out
        assert _sha(files["state"]) == before

    def test_simulate_payload(self):
        sim = cli.simulate(_state(), DRAFT, "2026-10-06", "evening")
        assert sim["ok"] is True
        assert sim["custom_tags"] == {"hard": True, "finger": True}
        dg = sim["downgrades"]
        assert dg == [{"date": "2026-10-07", "slot": "evening", "from": "power_contact_gym",
                       "to": "regeneration_easy", "key": ["limit_power"]}]
        # The player would get the anchored load of that day, not the draft's 20 kg.
        hang = next(e for e in sim["resolved_exercises"] if e["exercise_id"] == "max_hang_7s")
        assert hang["load_source"] == "anchored" and hang["stored_load_kg"] == 20

    def test_harmless_custom_changes_nothing(self):
        draft = {"name": "Core", "exercises": [{"exercise_id": "toes_to_bar", "sets": 3, "reps": 6}]}
        sim = cli.simulate(_state(), draft, "2026-10-06", "evening")
        assert sim["ok"] is True and sim["downgrades"] == []

    def test_slot_collision(self):
        sim = cli.simulate(_state(), DRAFT, "2026-10-06", "lunch")
        assert sim["ok"] is False and "occupato da prehab_maintenance" in sim["error"]

    def test_replace_of_a_key_is_flagged(self):
        draft = {"name": "Core", "exercises": [{"exercise_id": "toes_to_bar", "sets": 3, "reps": 6}]}
        sim = cli.simulate(_state(), draft, "2026-10-07", "evening", replace=True)
        assert sim["removed"][0]["session_id"] == "power_contact_gym"
        assert sim["removed"][0]["key"] == ["limit_power"]
        assert any("toglierebbe una sessione CHIAVE" in w for w in sim["warnings"])

    def test_week_not_generated(self):
        sim = cli.simulate(_state(), DRAFT, "2026-12-01", "evening")
        assert sim["ok"] is False and "settimana non generata" in sim["error"]

    def test_passes_the_router_kwargs(self, monkeypatch):
        seen = {}
        import backend.engine.replanner_v1 as rv

        real = rv.apply_events

        def spy(plan, events, **kw):
            seen.update(kw)
            return real(plan, events, **kw)

        monkeypatch.setattr(rv, "apply_events", spy)
        st = _state(availability={"mon": {"evening": {"available": True}}},
                    equipment={"gyms": [{"gym_id": "g1", "equipment": ["gym_boulder"]}]})
        cli.simulate(st, DRAFT, "2026-10-06", "evening")
        assert set(seen) == {"availability", "planning_prefs", "gyms", "custom_sessions", "prev_days"}  # A294
        assert seen["gyms"] == [{"gym_id": "g1", "equipment": ["gym_boulder"]}]
        assert any(c["id"] == cli.SIM_SESSION_ID for c in seen["custom_sessions"])

    def test_simulation_does_not_mutate_state(self):
        st = _state()
        snap = json.dumps(st, sort_keys=True)
        cli.simulate(st, DRAFT, "2026-10-06", "evening", replace=False)
        assert json.dumps(st, sort_keys=True) == snap


class TestPlayLine:
    def test_play_line_carries_the_scheme_specific_calculation_note(self):
        draft = {"name": "Trazioni 3x5", "exercises": [
            {"exercise_id": "weighted_pullup", "sets": 3, "reps": 5, "load_kg": 28.5}]}
        sim = cli.simulate(_state(), draft, "2026-10-06", "lunch", replace=True)
        e = next(x for x in sim["resolved_exercises"] if x["exercise_id"] == "weighted_pullup")
        from backend.engine.anchored_load import anchored_load
        anch = anchored_load(_state(), "weighted_pullup", date="2026-10-06", sets=3, reps=5)
        assert e["suggested_external_load_kg"] == anch["external"]
        out = cli.render_simulation(sim)
        assert "carico al play: weighted_pullup 3×5" in out and "→ nota: «" in out
        assert f"{round(anch['pct_of_official'] * 100)}% di" in out
