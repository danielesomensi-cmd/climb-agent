"""B401 — editing one crag of a multi-crag day deleted the other crags.

Since B341 a day can hold one ``outdoor_logs`` row per crag (key
``user_id, session_date, spot_name``). ``update_outdoor_session`` — behind
``PUT /api/outdoor/log``, the pencil — still removed *every* row of the date
and re-appended only the edited one: Symplegades + Snake Valley on 25/08, edit
Snake Valley → Symplegades was gone, routes and all. Same on Supabase
(``delete … eq session_date``). ``DELETE /api/outdoor/log/{date}`` did the same
from the per-crag trash icon of Outdoor History («Delete this session?»).

Fix: an edit rewrites only the row it replaces — (date, crag) — on both
storage backends. ``PUT`` accepts an optional ``original_spot_name`` for a
rename; without it the edit replaces the crag with the same name, never
another one: no match, or a rename onto another crag of the day → 409,
nothing written (single-crag days included since the review, see 2).
``DELETE`` accepts ``?spot_name=``; without it a multi-crag day → 409 instead
of deleting every crag.

Review fixes:

1. The edit was a delete followed by an upsert — on Supabase two requests with
   nothing between them. A failed upsert left the day without the edited crag;
   the retry of the same form then found a single-crag day and «renamed» the
   other crag, deleting it too. The edit is now ONE write: an UPDATE of the
   crag's row on Supabase (keeps its id and ``created_at``), one atomic
   rewrite of the yearly file on disk.
2. Without ``original_spot_name`` a single-crag day replaced its only crag
   whatever name was sent: a second crag typed into the edit form that Today /
   Week «Log outdoor» open on the day's crag, or a date moved onto a day with
   another crag, deleted that crag. The edited crag is now always the one the
   request names — a rename needs ``original_spot_name``, on every day — and a
   name not logged that day is a 409, nothing written.
"""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import httpx

from backend.engine import outdoor_log as ol
from backend.engine import storage_file
from backend.engine import storage_supabase

DAY = "2026-08-25"
USER = "u-b401"


def _entry(spot: str, day: str = DAY, grade: str = "6b", n_routes: int = 1, **extra):
    e = {
        "log_version": "outdoor.v2",
        "date": day,
        "spot_name": spot,
        "discipline": "lead",
        "duration_minutes": 120,
        "routes": [
            {"name": f"{spot} R{i}", "grade": grade, "attempts": [{"result": "sent"}]}
            for i in range(n_routes)
        ],
    }
    e.update(extra)
    return e


def _day_spots(user_id, day: str = DAY):
    return sorted(s["spot_name"] for s in ol.load_outdoor_sessions(user_id) if s["date"] == day)


def _by_spot(user_id, spot: str, day: str = DAY):
    return next(s for s in ol.load_outdoor_sessions(user_id) if s["date"] == day and s["spot_name"] == spot)


# ── File backend (engine level) ─────────────────────────────────────────


class TestFileBackend:
    @pytest.fixture(autouse=True)
    def _storage(self, tmp_path, monkeypatch):
        from backend.engine import storage

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
        self.log_path = tmp_path / "users" / USER / "logs" / "outdoor_sessions_2026.jsonl"

    def _two_crags(self):
        ol.append_outdoor_session(_entry("Symplegades"), USER)
        ol.append_outdoor_session(_entry("Snake Valley"), USER)

    def _lines(self):
        return [ln for ln in self.log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def _line_of(self, spot: str) -> str:
        return next(ln for ln in self._lines() if json.loads(ln)["spot_name"] == spot)

    def test_edit_last_crag_keeps_the_other_byte_identical(self):
        self._two_crags()
        before = self._line_of("Symplegades")

        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a", n_routes=3))

        assert _day_spots(USER) == ["Snake Valley", "Symplegades"]
        assert self._line_of("Symplegades") == before
        edited = _by_spot(USER, "Snake Valley")
        assert [r["grade"] for r in edited["routes"]] == ["7a"] * 3

    def test_edit_first_crag_keeps_the_last_byte_identical(self):
        self._two_crags()
        before = self._line_of("Snake Valley")

        ol.update_outdoor_session(USER, DAY, _entry("Symplegades", grade="6c"))

        assert _day_spots(USER) == ["Snake Valley", "Symplegades"]
        assert self._line_of("Snake Valley") == before
        assert _by_spot(USER, "Symplegades")["routes"][0]["grade"] == "6c"

    def test_rename_with_original_spot_name(self):
        self._two_crags()
        before = self._line_of("Symplegades")

        ol.update_outdoor_session(
            USER, DAY, _entry("Snake Valley Sector B"), original_spot_name="Snake Valley",
        )

        assert _day_spots(USER) == ["Snake Valley Sector B", "Symplegades"]
        assert self._line_of("Symplegades") == before

    def test_rename_without_original_on_multi_crag_day_writes_nothing(self):
        self._two_crags()
        before = self.log_path.read_bytes()

        with pytest.raises(ol.OutdoorLogConflict):
            ol.update_outdoor_session(USER, DAY, _entry("Ourania"))

        assert self.log_path.read_bytes() == before

    def test_rename_onto_another_crag_of_the_day_writes_nothing(self):
        # Renaming Snake Valley to "Symplegades" would land on the other
        # crag's key and overwrite it (Supabase upsert, file read dedup).
        self._two_crags()
        before = self.log_path.read_bytes()

        with pytest.raises(ol.OutdoorLogConflict):
            ol.update_outdoor_session(
                USER, DAY, _entry("Symplegades"), original_spot_name="Snake Valley",
            )

        assert self.log_path.read_bytes() == before

    def test_original_spot_name_not_logged_that_day_is_not_found(self):
        self._two_crags()
        before = self.log_path.read_bytes()

        with pytest.raises(ValueError, match="No outdoor session found"):
            ol.update_outdoor_session(USER, DAY, _entry("Ourania"), original_spot_name="Ourania")

        assert self.log_path.read_bytes() == before

    def test_invalid_entry_on_multi_crag_day_writes_nothing(self):
        self._two_crags()
        before = self.log_path.read_bytes()

        with pytest.raises(ValueError, match="Invalid"):
            ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", discipline="trad"))

        assert self.log_path.read_bytes() == before

    def test_second_crag_typed_into_the_edit_form_writes_nothing(self):
        """Review #2: Today/Week «Log outdoor» on a day that already has a crag
        opens the edit form on it. Typing the day's SECOND crag there used to
        «rename» the only crag — Symplegades gone, routes and all."""
        ol.append_outdoor_session(_entry("Symplegades", n_routes=3), USER)
        before = self.log_path.read_bytes()

        with pytest.raises(ol.OutdoorLogConflict, match="Nothing saved"):
            ol.update_outdoor_session(USER, DAY, _entry("Ourania", n_routes=2))

        assert self.log_path.read_bytes() == before

    def test_single_crag_day_rename_needs_original_spot_name(self):
        ol.append_outdoor_session(_entry("Berdorf"), USER)

        ol.update_outdoor_session(USER, DAY, _entry("Freyr"), original_spot_name="Berdorf")

        assert _day_spots(USER) == ["Freyr"]
        assert len(self._lines()) == 1

    def test_date_moved_onto_a_day_with_another_crag_writes_nothing(self):
        """Review #2: the edit form lets the date change. Berdorf opened on
        24/08 and saved on 25/08, where Freyr is logged, used to replace Freyr."""
        ol.append_outdoor_session(_entry("Berdorf", day="2026-08-24"), USER)
        ol.append_outdoor_session(_entry("Freyr", grade="7b"), USER)
        before = self.log_path.read_bytes()

        with pytest.raises(ol.OutdoorLogConflict):  # today's frontend
            ol.update_outdoor_session(USER, DAY, _entry("Berdorf"))
        with pytest.raises(ol.OutdoorLogNotFound):  # once it sends the crag it opened
            ol.update_outdoor_session(USER, DAY, _entry("Berdorf"), original_spot_name="Berdorf")

        assert self.log_path.read_bytes() == before

    def test_entry_dated_another_day_writes_nothing(self):
        self._two_crags()
        before = self.log_path.read_bytes()

        with pytest.raises(ValueError, match="cannot move a session to another date"):
            ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", day="2026-08-26"))

        assert self.log_path.read_bytes() == before

    def test_failed_write_leaves_the_file_as_it_was(self, monkeypatch):
        """Review #1: the edit is one atomic rewrite — before, the crag's lines
        were removed in one write and the replacement appended in another."""
        self._two_crags()
        before = self.log_path.read_bytes()

        def _disk_full(*a, **k):
            raise OSError("No space left on device")

        with monkeypatch.context() as m:
            m.setattr(storage_file.os, "replace", _disk_full)
            with pytest.raises(OSError):
                ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a"))

        assert self.log_path.read_bytes() == before
        assert [p.name for p in self.log_path.parent.iterdir()] == [self.log_path.name]

    def test_legacy_duplicate_lines_of_one_crag_are_all_replaced(self):
        """Pre-B341 files can carry several raw lines for one (date, crag) —
        the read dedup shows the last. An edit leaves exactly one line."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        old = [_entry("Berdorf", grade="6a"), _entry("Berdorf", grade="6a+"),
               _entry("Berdorf", day="2026-08-24")]
        self.log_path.write_text(
            "".join(json.dumps(e) + "\n" for e in old), encoding="utf-8",
        )
        other_day = self._lines()[2]

        ol.update_outdoor_session(USER, DAY, _entry("Berdorf", grade="7a"))

        day_lines = [ln for ln in self._lines() if json.loads(ln)["date"] == DAY]
        assert len(day_lines) == 1
        assert json.loads(day_lines[0])["routes"][0]["grade"] == "7a"
        assert other_day in self._lines()

    def test_delete_one_crag_keeps_the_other(self):
        self._two_crags()
        before = self._line_of("Symplegades")

        assert ol.remove_outdoor_session(USER, DAY, spot_name="Snake Valley") == 1

        assert _day_spots(USER) == ["Symplegades"]
        assert self._line_of("Symplegades") == before

    def test_delete_without_spot_on_multi_crag_day_deletes_nothing(self):
        self._two_crags()
        before = self.log_path.read_bytes()

        with pytest.raises(ol.OutdoorLogConflict):
            ol.remove_outdoor_session(USER, DAY)

        assert self.log_path.read_bytes() == before

    def test_delete_without_spot_on_single_crag_day_still_works(self):
        ol.append_outdoor_session(_entry("Berdorf"), USER)
        assert ol.remove_outdoor_session(USER, DAY) == 1
        assert _day_spots(USER) == []

    def test_delete_unknown_spot_removes_nothing(self):
        self._two_crags()
        assert ol.remove_outdoor_session(USER, DAY, spot_name="Ourania") == 0
        assert _day_spots(USER) == ["Snake Valley", "Symplegades"]


# ── Supabase backend (engine level, in-memory PostgREST double) ──────────


class _R:
    def __init__(self, data):
        self.data = data


def _col(row, col):
    # spot_name is the generated column entry->>'spot_name' (B341).
    if col == "spot_name":
        return (row.get("entry") or {}).get("spot_name")
    return row.get(col)


class _FakeQuery:
    def __init__(self, db):
        self.db = db
        self.op = "select"
        self.filters = []
        self.payload = None
        self.on_conflict = None
        self.n = None

    def select(self, *a, **k):
        self.op = "select"
        return self

    def delete(self):
        self.op = "delete"
        return self

    def upsert(self, payload, on_conflict=None):
        self.op, self.payload, self.on_conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def eq(self, col, val):
        self.filters.append((col, "eq", val))
        return self

    def gte(self, col, val):
        self.filters.append((col, "gte", val))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, n):
        self.n = n
        return self

    def _match(self, row):
        for col, op, val in self.filters:
            v = _col(row, col)
            if op == "eq" and v != val:
                return False
            if op == "gte" and not (v is not None and v >= val):
                return False
        return True

    def execute(self):
        db = self.db
        if self.op != "select":
            db.writes.append((self.op, list(self.filters)))
            if self.op in ("upsert", "update") and db.fail_entry_writes:
                db.fail_entry_writes -= 1
                raise httpx.ReadTimeout("simulated: the request writing the entry timed out")
        if self.op == "update":
            matched = [r for r in db.rows if self._match(r)]
            for row in matched:
                new = {**row, **copy.deepcopy(self.payload)}
                for other in db.rows:  # UNIQUE (user_id, session_date, spot_name)
                    if other is not row and all(
                        _col(other, k) == _col(new, k) for k in ("user_id", "session_date", "spot_name")
                    ):
                        raise RuntimeError("23505 duplicate key value violates unique constraint")
                row.update(copy.deepcopy(self.payload))
            return _R([copy.deepcopy(r) for r in matched])
        if self.op == "upsert":
            keys = self.on_conflict.split(",")
            new = {"user_id": self.payload["user_id"],
                   "session_date": self.payload["session_date"],
                   "entry": copy.deepcopy(self.payload["entry"])}
            for row in db.rows:
                if all(_col(row, k) == _col(new, k) for k in keys):
                    row["entry"] = new["entry"]
                    return _R([copy.deepcopy(row)])
            new["id"] = db.next_id
            new["created_at"] = f"2026-08-25T18:00:{db.next_id:02d}+00:00"  # DEFAULT now()
            db.next_id += 1
            db.rows.append(new)
            return _R([copy.deepcopy(new)])
        matched = [r for r in db.rows if self._match(r)]
        if self.op == "delete":
            db.deletes.append(list(self.filters))
            ids = {r["id"] for r in matched}
            db.rows = [r for r in db.rows if r["id"] not in ids]
            return _R([copy.deepcopy(r) for r in matched])
        matched = sorted(matched, key=lambda r: r["session_date"])
        if self.n:
            matched = matched[: self.n]
        return _R([copy.deepcopy(r) for r in matched])


class _FakeSupabase:
    def __init__(self):
        self.rows = []
        self.deletes = []
        self.writes = []  # (op, filters) of every write request, failed ones included
        # The next N requests that write an entry (upsert / update) raise a
        # transient error; deletes go through — the review's failure point.
        self.fail_entry_writes = 0
        self.next_id = 1

    def table(self, name):
        assert name == "outdoor_logs"
        return _FakeQuery(self)


class TestSupabaseBackend:
    @pytest.fixture(autouse=True)
    def _storage(self, monkeypatch):
        self.db = _FakeSupabase()
        monkeypatch.setattr(storage_supabase, "_sb", lambda: self.db)
        monkeypatch.setattr(ol, "storage", storage_supabase)
        # B353 retry: no real client to rebuild, no back-off wait.
        monkeypatch.setattr(storage_supabase, "_url", "")
        monkeypatch.setattr(storage_supabase.time, "sleep", lambda s: None)

    def _two_crags(self):
        ol.append_outdoor_session(_entry("Symplegades"), USER)
        ol.append_outdoor_session(_entry("Snake Valley"), USER)

    def _row(self, spot):
        return next(r for r in self.db.rows if r["entry"]["spot_name"] == spot)

    def test_edit_one_crag_keeps_the_other_row_untouched(self):
        self._two_crags()
        before = copy.deepcopy(self._row("Symplegades"))

        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a"))

        assert sorted(r["entry"]["spot_name"] for r in self.db.rows) == ["Snake Valley", "Symplegades"]
        after = self._row("Symplegades")
        assert after == before  # same id, same entry
        assert json.dumps(after["entry"], sort_keys=True) == json.dumps(before["entry"], sort_keys=True)
        assert self._row("Snake Valley")["entry"]["routes"][0]["grade"] == "7a"

    def test_edit_is_one_update_of_the_crags_row(self):
        """Review #1: one statement keyed (date, crag) — never a delete."""
        self._two_crags()
        self.db.writes.clear()

        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a"))

        assert self.db.writes == [("update", [
            ("user_id", "eq", USER), ("session_date", "eq", DAY), ("spot_name", "eq", "Snake Valley"),
        ])]
        assert self.db.deletes == []

    def test_edit_keeps_the_rows_id_and_created_at(self):
        """created_at is the save-time anchor of export_training_log: an edit,
        a rename included, is the same session and keeps it."""
        self._two_crags()
        before = copy.deepcopy(self._row("Snake Valley"))

        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a"))
        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley B"), original_spot_name="Snake Valley")

        after = self._row("Snake Valley B")
        assert (after["id"], after["created_at"]) == (before["id"], before["created_at"])

    def test_failed_write_keeps_the_crag_and_the_retry_keeps_both(self):
        """Review #1, the reported sequence: the write fails (every attempt),
        the form stays open, the athlete taps Save again with the same payload.
        Before: the first try deleted Snake Valley, the second found a
        single-crag day and replaced Symplegades with it."""
        self._two_crags()
        before = copy.deepcopy(self.db.rows)

        self.db.fail_entry_writes = 99
        with pytest.raises(httpx.ReadTimeout):
            ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a"))
        assert self.db.rows == before

        self.db.fail_entry_writes = 0
        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a"))

        assert sorted(r["entry"]["spot_name"] for r in self.db.rows) == ["Snake Valley", "Symplegades"]
        assert self._row("Symplegades") == before[0]
        assert self._row("Snake Valley")["entry"]["routes"][0]["grade"] == "7a"

    def test_transient_error_on_an_edit_is_retried(self):
        self._two_crags()
        self.db.writes.clear()
        self.db.fail_entry_writes = 1

        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley", grade="7a"))

        assert [op for op, _ in self.db.writes] == ["update", "update"]
        assert self._row("Snake Valley")["entry"]["routes"][0]["grade"] == "7a"

    def test_rename_is_not_retried_and_a_failure_keeps_the_old_row(self):
        """A retried rename that did commit would find no row under the old
        name: one attempt, and a failure leaves the crag as it was."""
        self._two_crags()
        before = copy.deepcopy(self.db.rows)
        self.db.writes.clear()
        self.db.fail_entry_writes = 1

        with pytest.raises(httpx.ReadTimeout):
            ol.update_outdoor_session(USER, DAY, _entry("Snake Valley B"), original_spot_name="Snake Valley")

        assert [op for op, _ in self.db.writes] == ["update"]
        assert self.db.rows == before

    def test_rename_with_original_spot_name(self):
        self._two_crags()
        before = copy.deepcopy(self._row("Symplegades"))

        ol.update_outdoor_session(USER, DAY, _entry("Snake Valley B"), original_spot_name="Snake Valley")

        assert sorted(r["entry"]["spot_name"] for r in self.db.rows) == ["Snake Valley B", "Symplegades"]
        assert self._row("Symplegades") == before

    def test_ambiguous_edit_writes_nothing(self):
        self._two_crags()
        before = copy.deepcopy(self.db.rows)
        with pytest.raises(ol.OutdoorLogConflict):
            ol.update_outdoor_session(USER, DAY, _entry("Ourania"))
        assert self.db.rows == before
        assert self.db.deletes == []

    def test_single_crag_day_other_name_without_original_writes_nothing(self):
        """Review #2: the second crag typed into the edit form of the first."""
        ol.append_outdoor_session(_entry("Symplegades", n_routes=3), USER)
        before = copy.deepcopy(self.db.rows)
        self.db.writes.clear()

        with pytest.raises(ol.OutdoorLogConflict):
            ol.update_outdoor_session(USER, DAY, _entry("Ourania"))

        assert self.db.rows == before
        assert self.db.writes == []

    def test_single_crag_day_rename_with_original(self):
        ol.append_outdoor_session(_entry("Berdorf"), USER)
        row_id = self.db.rows[0]["id"]
        ol.update_outdoor_session(USER, DAY, _entry("Freyr"), original_spot_name="Berdorf")
        assert [(r["id"], r["entry"]["spot_name"]) for r in self.db.rows] == [(row_id, "Freyr")]

    def test_delete_one_crag_keeps_the_other(self):
        self._two_crags()
        before = copy.deepcopy(self._row("Symplegades"))

        assert ol.remove_outdoor_session(USER, DAY, spot_name="Snake Valley") == 1

        assert self.db.rows == [before]

    def test_delete_without_spot_on_multi_crag_day_deletes_nothing(self):
        self._two_crags()
        before = copy.deepcopy(self.db.rows)
        with pytest.raises(ol.OutdoorLogConflict):
            ol.remove_outdoor_session(USER, DAY)
        assert self.db.rows == before


# ── API (file backend) ───────────────────────────────────────────────────


THIS_MONDAY = date.today() - timedelta(days=date.today().weekday())
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _mk_plan(monday: date) -> dict:
    days = [{"date": (monday + timedelta(days=i)).isoformat(), "weekday": wd, "sessions": []}
            for i, wd in enumerate(WEEKDAYS)]
    return {"start_date": monday.isoformat(), "weeks": [{"week_index": 0, "days": days}]}


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
        self.log_dir: Path = tmp_path / "logs"

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _body(self, spot, day=DAY, grade="6b", n_routes=1, **extra):
        e = _entry(spot, day=day, grade=grade, n_routes=n_routes, **extra)
        e.pop("log_version")
        return e

    def _post(self, spot, day=DAY, **kw):
        r = self.client.post("/api/outdoor/log", json=self._body(spot, day=day, **kw))
        assert r.status_code == 200, r.text

    def _sessions(self, day=DAY):
        r = self.client.get("/api/outdoor/sessions")
        assert r.status_code == 200
        return {s["spot_name"]: s for s in r.json()["sessions"] if s["date"] == day}

    def _raw(self) -> bytes:
        return b"".join(p.read_bytes() for p in sorted(self.log_dir.glob("outdoor_sessions_*.jsonl")))

    def _state(self):
        return json.loads(self.state_path.read_text())

    def test_put_on_multi_crag_day_keeps_the_other_crag(self):
        self._post("Symplegades")
        self._post("Snake Valley")
        before = self._sessions()["Symplegades"]

        r = self.client.put("/api/outdoor/log", json=self._body("Snake Valley", grade="7a"))

        assert r.status_code == 200, r.text
        after = self._sessions()
        assert set(after) == {"Symplegades", "Snake Valley"}
        assert after["Symplegades"] == before
        assert after["Snake Valley"]["routes"][0]["grade"] == "7a"

    def test_put_rename_with_original_spot_name(self):
        self._post("Symplegades")
        self._post("Snake Valley")
        before = self._sessions()["Symplegades"]

        body = self._body("Snake Valley B")
        body["original_spot_name"] = "Snake Valley"
        r = self.client.put("/api/outdoor/log", json=body)

        assert r.status_code == 200, r.text
        after = self._sessions()
        assert set(after) == {"Symplegades", "Snake Valley B"}
        assert after["Symplegades"] == before
        # The request-only field never lands in the immutable log.
        assert "original_spot_name" not in after["Snake Valley B"]

    def test_put_rename_without_original_on_multi_crag_day_is_409(self):
        self._post("Symplegades")
        self._post("Snake Valley")
        raw = self._raw()

        r = self.client.put("/api/outdoor/log", json=self._body("Ourania"))

        assert r.status_code == 409, r.text
        assert "original_spot_name" in r.json()["detail"]
        assert self._raw() == raw

    def test_put_rename_onto_another_crag_is_409(self):
        self._post("Symplegades")
        self._post("Snake Valley")
        raw = self._raw()

        body = self._body("Symplegades")
        body["original_spot_name"] = "Snake Valley"
        r = self.client.put("/api/outdoor/log", json=body)

        assert r.status_code == 409, r.text
        assert self._raw() == raw

    def test_put_unknown_original_spot_is_404(self):
        self._post("Symplegades")
        body = self._body("Ourania")
        body["original_spot_name"] = "Ourania"
        r = self.client.put("/api/outdoor/log", json=body)
        assert r.status_code == 404, r.text

    def test_put_second_crag_into_the_edit_form_is_409(self):
        """Review #2: «Log outdoor» on Symplegades' day opens its edit form;
        saving Ourania there must not delete Symplegades."""
        self._post("Symplegades", n_routes=3)
        before = self._sessions()
        raw = self._raw()

        r = self.client.put("/api/outdoor/log", json=self._body("Ourania", n_routes=2))

        assert r.status_code == 409, r.text
        assert "Nothing saved" in r.json()["detail"]
        assert self._raw() == raw
        assert self._sessions() == before

    def test_put_date_moved_onto_another_crags_day_is_409(self):
        self._post("Berdorf", day="2026-08-24")
        self._post("Freyr", grade="7b")
        raw = self._raw()

        r = self.client.put("/api/outdoor/log", json=self._body("Berdorf"))

        assert r.status_code == 409, r.text
        assert self._raw() == raw

    def test_put_single_crag_rename_with_original_spot_name(self):
        self._post("Berdorf")
        body = self._body("Freyr")
        body["original_spot_name"] = "Berdorf"
        r = self.client.put("/api/outdoor/log", json=body)
        assert r.status_code == 200, r.text
        assert set(self._sessions()) == {"Freyr"}

    def test_put_keeps_the_edited_crags_own_load_reference(self):
        """B394: the edit keeps the load_ref_grade of the crag it edits — it
        used to read it off the day's LAST row, i.e. maybe another crag."""
        from backend.engine import storage

        storage.append_outdoor_log_line(None, _entry("Symplegades", load_ref_grade="7c"))
        storage.append_outdoor_log_line(None, _entry("Snake Valley", load_ref_grade="8a"))

        r = self.client.put("/api/outdoor/log", json=self._body("Symplegades", grade="6c"))

        assert r.status_code == 200, r.text
        after = self._sessions()
        assert after["Symplegades"]["load_ref_grade"] == "7c"
        assert after["Snake Valley"]["load_ref_grade"] == "8a"

    def test_get_by_date_lists_every_crag(self):
        self._post("Symplegades")
        self._post("Snake Valley")

        r = self.client.get(f"/api/outdoor/log/{DAY}")

        assert r.status_code == 200
        body = r.json()
        assert body["session"]["spot_name"] == "Snake Valley"  # unchanged: last logged
        assert [s["spot_name"] for s in body["sessions"]] == ["Symplegades", "Snake Valley"]
        assert all("load_score" in s for s in body["sessions"])

    def test_delete_one_crag_keeps_the_other(self):
        self._post("Symplegades")
        self._post("Snake Valley")
        before = self._sessions()["Symplegades"]

        r = self.client.delete(f"/api/outdoor/log/{DAY}", params={"spot_name": "Snake Valley"})

        assert r.status_code == 200, r.text
        assert self._sessions() == {"Symplegades": before}

    def test_delete_without_spot_on_multi_crag_day_is_409(self):
        self._post("Symplegades")
        self._post("Snake Valley")
        raw = self._raw()

        r = self.client.delete(f"/api/outdoor/log/{DAY}")

        assert r.status_code == 409, r.text
        assert self._raw() == raw

    def test_delete_without_spot_on_single_crag_day_still_works(self):
        self._post("Berdorf")
        r = self.client.delete(f"/api/outdoor/log/{DAY}")
        assert r.status_code == 200, r.text
        assert self._sessions() == {}

    def test_delete_unknown_spot_is_404(self):
        self._post("Berdorf")
        r = self.client.delete(f"/api/outdoor/log/{DAY}", params={"spot_name": "Ourania"})
        assert r.status_code == 404, r.text
        assert set(self._sessions()) == {"Berdorf"}

    def test_edit_syncs_the_day_total_of_every_crag(self):
        """The plan day and the bookkeeping carry the day's TOTAL load (B341),
        computed after the edit over both crags."""
        target = THIS_MONDAY.isoformat()
        state = self._state()
        state["week_plans"] = {target: _mk_plan(THIS_MONDAY)}
        self.state_path.write_text(json.dumps(state))
        self._post("Symplegades", day=target)
        self._post("Snake Valley", day=target)

        r = self.client.put("/api/outdoor/log",
                            json=self._body("Snake Valley", day=target, grade="7c", n_routes=4))
        assert r.status_code == 200, r.text
        assert r.json()["plan_synced"] is True

        sessions = self._sessions(day=target)
        assert set(sessions) == {"Symplegades", "Snake Valley"}
        total = sum(ol.compute_outdoor_load_score(s) for s in sessions.values())
        st = self._state()
        day = next(d for w in st["week_plans"][target]["weeks"] for d in w["days"] if d["date"] == target)
        assert day["outdoor_load_score"] == total
        assert day["outdoor_spot_name"] == "Symplegades - Snake Valley"
        rows = [e for e in st["outdoor_log"] if e["date"] == target]
        assert len(rows) == 1 and rows[0]["load_score"] == total

    def test_edit_without_plan_keeps_bookkeeping_at_the_day_total(self):
        """No plan → no sync: the PUT's own bookkeeping update must still be
        the day's total, not the edited crag's alone."""
        self._post("Symplegades")
        self._post("Snake Valley")
        state = self._state()
        state["outdoor_log"] = [{"date": DAY, "spot_name": "Symplegades - Snake Valley",
                                 "discipline": "lead", "load_score": 1}]
        self.state_path.write_text(json.dumps(state))

        r = self.client.put("/api/outdoor/log", json=self._body("Snake Valley", grade="7c", n_routes=4))
        assert r.status_code == 200, r.text
        assert r.json()["plan_synced"] is False

        total = sum(ol.compute_outdoor_load_score(s) for s in self._sessions().values())
        rows = [e for e in self._state()["outdoor_log"] if e["date"] == DAY]
        assert len(rows) == 1
        assert rows[0]["load_score"] == total
        assert rows[0]["spot_name"] == "Symplegades - Snake Valley"

    def test_delete_one_crag_keeps_bookkeeping_for_the_rest_of_the_day(self):
        self._post("Symplegades")
        self._post("Snake Valley")
        state = self._state()
        state["outdoor_log"] = [{"date": DAY, "spot_name": "Symplegades - Snake Valley",
                                 "discipline": "lead", "load_score": 99}]
        self.state_path.write_text(json.dumps(state))

        r = self.client.delete(f"/api/outdoor/log/{DAY}", params={"spot_name": "Snake Valley"})
        assert r.status_code == 200, r.text

        remaining = self._sessions()
        rows = [e for e in self._state()["outdoor_log"] if e["date"] == DAY]
        assert len(rows) == 1
        assert rows[0]["load_score"] == ol.compute_outdoor_load_score(remaining["Symplegades"])


def test_delete_without_spot_removes_the_crag_it_read_not_the_date(monkeypatch):
    """B401 review: DELETE without spot_name on a single-crag day deletes that
    crag by (date, crag). A crag finished between the read and the delete
    (another device) is not wiped with it."""
    from backend.engine import outdoor_log as ol

    calls = []
    monkeypatch.setattr(ol, "outdoor_sessions_on", lambda uid, d: [{"date": d, "spot_name": "Berdorf"}])
    monkeypatch.setattr(ol.storage, "remove_outdoor_log_by_date_spot", lambda uid, d, s: calls.append(("spot", d, s)) or 1)
    monkeypatch.setattr(ol.storage, "remove_outdoor_log_by_date", lambda uid, d: calls.append(("date", d)) or 2)

    assert ol.remove_outdoor_session("u1", "2026-08-24") == 1
    assert calls == [("spot", "2026-08-24", "Berdorf")]
