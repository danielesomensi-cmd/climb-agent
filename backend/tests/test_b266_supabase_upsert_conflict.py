"""B266 — Supabase upserts must target their (user_id, X) unique constraint.

Regression guard for the outdoor-session "Load failed" bug: `append_outdoor_log_line`
and `archive_week` called `.upsert(...)` WITHOUT `on_conflict`, so postgrest
defaulted to the serial primary key and the write degraded to a plain INSERT.
A second finish for the same (user_id, session_date) then violated the
`outdoor_logs_user_id_session_date_key` unique constraint (Postgres 23505),
surfacing as an HTTP 500 → Safari "Load failed" on the client.

These tests mock the Supabase client and assert the upsert carries the correct
`on_conflict` target, so re-writing the same key UPDATEs instead of erroring.
"""

import pytest

from backend.engine import storage_supabase as ss


class _FakeQuery:
    """Captures the table name and the kwargs of the upsert/select chain."""

    def __init__(self, table, calls):
        self._table = table
        self._calls = calls

    def upsert(self, payload, **kwargs):
        self._calls.append({"table": self._table, "payload": payload, "kwargs": kwargs})
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        # Mimic a successful write + read-after-write verify.
        class _R:
            data = [{"ok": True}]

        return _R()


class _FakeClient:
    def __init__(self, calls):
        self._calls = calls

    def table(self, name):
        return _FakeQuery(name, self._calls)


@pytest.fixture
def captured(monkeypatch):
    calls = []
    monkeypatch.setattr(ss, "_sb", lambda: _FakeClient(calls))
    return calls


def test_outdoor_log_upsert_targets_unique_constraint(captured):
    ss.append_outdoor_log_line("user-123", {"date": "2026-06-20", "spot_name": "Berdorf"})
    upserts = [c for c in captured if c["payload"].get("session_date") is not None]
    assert len(upserts) == 1
    assert upserts[0]["table"] == "outdoor_logs"
    # The crux: conflict target must be the composite unique key, not the PK.
    # B341: the key widened to (user_id, session_date, spot_name) — a second
    # crag finished the same day used to silently overwrite the first one's
    # log row via this same upsert.
    assert upserts[0]["kwargs"].get("on_conflict") == "user_id,session_date,spot_name"


def test_week_archive_upsert_targets_unique_constraint(captured):
    ss.archive_week("user-123", "2026-06-15", {"week_num": 1})
    upserts = [c for c in captured if c["table"] == "week_archive"]
    assert len(upserts) == 1
    assert upserts[0]["kwargs"].get("on_conflict") == "user_id,week_start"
