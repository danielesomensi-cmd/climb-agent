"""Tests for motivational quotes engine."""

from __future__ import annotations

import pytest

from backend.engine.quotes_engine import (
    detect_quote_context,
    get_quote_for_session,
    update_quote_history,
)


class TestDetectContext:
    def test_deload_phase(self):
        assert detect_quote_context([], phase_id="deload") == "deload"

    def test_hard_session(self):
        ctx = detect_quote_context(["strength_long", "prehab_maintenance"])
        assert ctx == "hard_day"

    def test_finger_strength_session(self):
        ctx = detect_quote_context(["finger_strength_home"])
        assert ctx == "hard_day"

    def test_first_week(self):
        ctx = detect_quote_context(["technique_focus_gym"], is_first_week=True)
        assert ctx == "new_phase"

    def test_general_fallback(self):
        ctx = detect_quote_context(["technique_focus_gym"])
        assert ctx == "general"

    def test_deload_overrides_first_week(self):
        """Deload takes priority over first_week."""
        ctx = detect_quote_context([], phase_id="deload", is_first_week=True)
        assert ctx == "deload"


class TestGetQuoteForSession:
    def test_valid_context(self):
        quote = get_quote_for_session("general")
        assert "id" in quote
        assert "text" in quote
        assert "author" in quote
        assert quote["context"] == "general"

    def test_hard_day_context(self):
        quote = get_quote_for_session("hard_day")
        assert quote["context"] == "hard_day"
        assert len(quote["text"]) > 0

    def test_deload_context(self):
        quote = get_quote_for_session("deload")
        assert quote["context"] == "deload"

    def test_30_day_rotation(self):
        """Seen quotes should not be re-selected until pool exhausted."""
        seen: list = []
        for _ in range(30):
            quote = get_quote_for_session("general", recent_quote_ids=seen)
            assert quote["id"] not in seen or len(seen) >= 50  # pool may be < 30 for a context
            seen.append(quote["id"])

        # All IDs should be unique (up to pool size)
        unique = set(seen)
        assert len(unique) == len(seen) or len(unique) >= 20  # at least 20 unique quotes

    def test_determinism(self):
        """Same history always produces same quote."""
        results = set()
        for _ in range(5):
            quote = get_quote_for_session("general", recent_quote_ids=["q001", "q002"])
            results.add(quote["id"])
        assert len(results) == 1

    def test_fallback_when_all_exhausted(self):
        """When all context quotes are seen, reset and return first."""
        # Use a very long seen list to exhaust the pool
        huge_seen = [f"q{i:03d}" for i in range(1, 300)]
        quote = get_quote_for_session("general", recent_quote_ids=huge_seen)
        assert "id" in quote
        assert "text" in quote

    def test_unknown_context_falls_back_to_general(self):
        quote = get_quote_for_session("nonexistent_context_xyz")
        assert "id" in quote
        # Should fall back to "general" context quotes


class TestUpdateQuoteHistory:
    def test_append_to_history(self):
        state = {"quote_history": []}
        update_quote_history(state, "q001")
        assert state["quote_history"] == ["q001"]

    def test_trim_at_max(self):
        state = {"quote_history": [f"q{i:03d}" for i in range(30)]}
        update_quote_history(state, "q999")
        assert len(state["quote_history"]) == 30
        assert state["quote_history"][-1] == "q999"
        assert state["quote_history"][0] == "q001"

    def test_creates_history_if_missing(self):
        state = {}
        update_quote_history(state, "q001")
        assert state["quote_history"] == ["q001"]


class TestQuotesAPI:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        import json
        from backend.api import deps

        state_path = tmp_path / "user_state.json"
        state_path.write_text(json.dumps({
            "schema_version": "1.5",
            "quote_history": [],
        }))
        from backend.engine import storage
        monkeypatch.setattr(storage, "STATE_PATH", state_path)
        monkeypatch.setattr(deps, "STATE_PATH", state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def test_get_daily_quote(self):
        r = self.client.get("/api/quotes/daily")
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert "text" in data
        assert data["context"] == "general"

    def test_get_quote_with_context(self):
        r = self.client.get("/api/quotes/daily?context=hard_day")
        assert r.status_code == 200
        data = r.json()
        assert data["context"] == "hard_day"

    def test_quote_history_updated(self):
        import json
        from backend.api import deps

        r = self.client.get("/api/quotes/daily")
        assert r.status_code == 200
        quote_id = r.json()["id"]

        # Read state and verify history
        state = json.loads(deps.STATE_PATH.read_text())
        assert quote_id in state.get("quote_history", [])


# --------------------------------------------------------------------------- #
# B384 — GET /api/quotes/daily must not rewrite the whole state on every call
# --------------------------------------------------------------------------- #

class TestQuoteOfTheDay:
    def test_same_day_same_quote(self):
        from datetime import date
        from backend.engine.quotes_engine import get_quote_of_the_day
        d = date(2026, 10, 17)
        assert get_quote_of_the_day("general", d, "u1") == get_quote_of_the_day("general", d, "u1")

    def test_walks_whole_pool_before_repeating(self):
        from datetime import date, timedelta
        from backend.engine.quotes_engine import _context_pool, get_quote_of_the_day
        pool = _context_pool("hard_day")
        start = date(2026, 1, 1)
        ids = [get_quote_of_the_day("hard_day", start + timedelta(days=i), "u1")["id"] for i in range(len(pool))]
        assert len(set(ids)) == len(pool)

    def test_payload_shape_unchanged(self):
        from datetime import date
        from backend.engine.quotes_engine import get_quote_of_the_day
        q = get_quote_of_the_day("deload", date(2026, 10, 17), "u1")
        assert set(q) == {"id", "text", "author", "source_type", "context"}
        assert q["context"] == "deload"

    def test_unknown_context_falls_back(self):
        from datetime import date
        from backend.engine.quotes_engine import get_quote_of_the_day
        q = get_quote_of_the_day("nope_xyz", date(2026, 10, 17), "u1")
        assert q["id"] and q["context"] == "nope_xyz"


class TestQuotesAPINoRewrite:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        import json
        from backend.api import deps
        from backend.engine import storage

        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({"schema_version": "1.5", "quote_history": []}))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        self.writes = 0
        real_write = storage.write_state

        def counting_write(state, user_id=None):
            self.writes += 1
            return real_write(state, user_id)

        monkeypatch.setattr(storage, "write_state", counting_write)
        monkeypatch.setattr(deps._storage, "write_state", counting_write, raising=False)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _read(self):
        import json
        return json.loads(self.state_path.read_text())

    def test_repeated_calls_same_day_write_once(self):
        first = self.client.get("/api/quotes/daily?date=2026-10-17")
        assert first.status_code == 200
        assert self.writes == 1
        for _ in range(5):
            r = self.client.get("/api/quotes/daily?date=2026-10-17")
            assert r.status_code == 200
            assert r.json() == first.json()
        assert self.writes == 1, "same-day calls must not write the state again"
        assert self._read()["quote_history"] == [first.json()["id"]]

    def test_new_day_records_one_id(self):
        a = self.client.get("/api/quotes/daily?date=2026-10-17").json()
        b = self.client.get("/api/quotes/daily?date=2026-10-18").json()
        assert a["id"] != b["id"]
        assert self._read()["quote_history"] == [a["id"], b["id"]]
        assert self.writes == 2

    def test_response_shape_unchanged(self):
        data = self.client.get("/api/quotes/daily?context=hard_day").json()
        assert set(data) == {"id", "text", "author", "source_type", "context"}
        assert data["context"] == "hard_day"

    def test_invalid_date_is_422(self):
        assert self.client.get("/api/quotes/daily?date=17-10-2026").status_code == 422

    def test_concurrent_write_is_not_lost(self, monkeypatch):
        """A write landing between the router's first read and its save survives:
        the save happens on a state reloaded under the user lock."""
        import json
        from backend.api.routers import quotes as quotes_router

        real_load = quotes_router.load_state
        calls = {"n": 0}

        def racing_load(user_id=None):
            state = real_load(user_id)
            calls["n"] += 1
            if calls["n"] == 1:  # another writer commits right after our first read
                other = json.loads(self.state_path.read_text())
                other["concurrent_marker"] = "kept"
                self.state_path.write_text(json.dumps(other))
            return state

        monkeypatch.setattr(quotes_router, "load_state", racing_load)
        r = self.client.get("/api/quotes/daily?date=2026-10-17")
        assert r.status_code == 200
        on_disk = self._read()
        assert on_disk.get("concurrent_marker") == "kept"
        assert on_disk["quote_history"] == [r.json()["id"]]
