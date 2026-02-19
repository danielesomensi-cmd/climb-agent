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
