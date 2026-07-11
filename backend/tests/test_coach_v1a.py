"""A-COACH-V1a — LLM Coach v1 tests.

Covers:
- prompt_builder: L0/L1/L2 always present, L3 routing capped at 3, user
  context (phase/week/today), token-budget truncation, English + suggest-only
  instruction block;
- coach storage (file backend): append/read/count roundtrip, pagination;
- endpoints with a MOCKED Anthropic client (never real calls): happy path,
  missing API key → loud 500, rate limit → 429, fail-closed subscription
  block, history ordering + pagination.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.coach import llm_client, prompt_builder, service
from backend.engine import storage

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

L3_DIR = prompt_builder.KNOWLEDGE_DIR / "L3"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """B216 pattern: isolated state file + tmp DATA_DIR for logs."""
    tmp_state = tmp_path / "user_state.json"
    if FIXTURE_STATE.exists():
        shutil.copy2(FIXTURE_STATE, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage_file
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_state


@pytest.fixture()
def mock_llm(monkeypatch):
    """Replace the Anthropic call with a canned reply; capture inputs."""
    calls = {}

    def fake_chat(system_blocks, messages):
        calls["system_blocks"] = system_blocks
        calls["messages"] = messages
        return "Mocked coach reply."

    monkeypatch.setattr(llm_client, "chat", fake_chat)
    return calls


def _uid() -> str:
    return str(uuid.uuid4())


# ── prompt_builder ─────────────────────────────────────────────────────────

class TestPromptBuilder:
    def test_static_block_contains_l0_l1_l2_and_instructions(self):
        prompt_builder.build_static_block.cache_clear()
        block = prompt_builder.build_static_block()
        l0 = (prompt_builder.KNOWLEDGE_DIR / "L0_safety_hard_rules.md").read_text()
        l1 = (prompt_builder.KNOWLEDGE_DIR / "L1_coach_voice.md").read_text()
        l2 = (prompt_builder.KNOWLEDGE_DIR / "L2_decision_index.md").read_text()
        assert l0.strip() in block
        assert l1.strip() in block
        assert l2.strip() in block
        # Runtime contract: English-only + suggest-only.
        assert "Always respond in English" in block
        assert "Never claim to have changed" in block

    def test_dynamic_block_routes_l3_capped_at_three(self):
        state = deps.load_state(None)
        query = (
            "max hangs on the hangboard for finger strength, my pulley hurts, "
            "and how should I periodize my endurance ARC training?"
        )
        paths = prompt_builder.route_query(query)
        assert 1 <= len(paths) <= 3
        dynamic = prompt_builder.build_dynamic_block(state, None, query)
        for p in paths:
            # First heading line of each routed file must be present.
            first_line = p.read_text(encoding="utf-8").strip().splitlines()[0]
            assert first_line in dynamic

    def test_context_contains_phase_week_and_today(self):
        state = deps.load_state(None)
        ctx = prompt_builder.build_user_context(state, None)
        assert "## Goal & plan position" in ctx
        assert "Current position: week" in ctx
        assert "## Today's session detail" in ctx
        assert "## Equipment available" in ctx
        assert date.today().isoformat() in ctx

    def test_boulder_grades_are_fontainebleau_labelled(self):
        state = deps.load_state(None)
        ctx = prompt_builder.build_user_context(state, None)
        assert "Fontainebleau" in ctx

    def test_token_budget_truncation(self, monkeypatch, caplog):
        state = deps.load_state(None)
        monkeypatch.setattr(prompt_builder, "TOKEN_BUDGET", 1)
        with caplog.at_level("WARNING"):
            dynamic = prompt_builder.build_dynamic_block(state, None, "periodization")
        assert any("budget" in r.message for r in caplog.records)
        # Week-plan detail dropped in the final fallback.
        assert "## Current week plan" not in dynamic
        # But core context is still there.
        assert "## Goal & plan position" in dynamic

    def test_build_system_prompt_joins_blocks(self):
        prompt = prompt_builder.build_system_prompt(None, "periodization")
        assert "Always respond in English" in prompt
        assert "=== USER CONTEXT" in prompt


# ── storage (file backend) ─────────────────────────────────────────────────

class TestCoachStorage:
    def test_append_read_roundtrip_newest_first(self):
        uid = _uid()
        storage.append_coach_message(uid, "user", "first")
        storage.append_coach_message(uid, "assistant", "second")
        rows = storage.read_coach_messages(uid, limit=10)
        assert [r["content"] for r in rows] == ["second", "first"]
        assert all(r.get("created_at") for r in rows)

    def test_before_cursor_pagination(self):
        uid = _uid()
        for i in range(5):
            storage.append_coach_message(uid, "user", f"msg-{i}")
        newest = storage.read_coach_messages(uid, limit=2)
        assert [r["content"] for r in newest] == ["msg-4", "msg-3"]
        older = storage.read_coach_messages(
            uid, limit=10, before=newest[-1]["created_at"]
        )
        assert [r["content"] for r in older] == ["msg-2", "msg-1", "msg-0"]

    def test_count_user_messages_since_counts_only_user_role(self):
        uid = _uid()
        storage.append_coach_message(uid, "user", "q")
        storage.append_coach_message(uid, "assistant", "a")
        storage.append_coach_message(uid, "user", "q2")
        today = date.today().isoformat()
        assert storage.count_coach_user_messages_since(uid, today) == 2
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        assert storage.count_coach_user_messages_since(uid, tomorrow) == 0


# ── POST /api/coach/chat ───────────────────────────────────────────────────

class TestChatEndpoint:
    def test_happy_path_persists_both_messages(self, mock_llm):
        uid = _uid()
        r = client.post(
            "/api/coach/chat",
            json={"message": "Where am I in my plan?"},
            headers={"X-User-ID": uid},
        )
        assert r.status_code == 200
        assert r.json() == {"reply": "Mocked coach reply."}
        # System blocks: [static (cached), dynamic].
        assert len(mock_llm["system_blocks"]) == 2
        assert "Always respond in English" in mock_llm["system_blocks"][0]
        assert "=== USER CONTEXT" in mock_llm["system_blocks"][1]
        assert mock_llm["messages"][-1] == {
            "role": "user", "content": "Where am I in my plan?"
        }
        rows = storage.read_coach_messages(uid, limit=10)
        assert [(r["role"], r["content"]) for r in rows] == [
            ("assistant", "Mocked coach reply."),
            ("user", "Where am I in my plan?"),
        ]

    def test_history_window_enters_context(self, mock_llm):
        uid = _uid()
        storage.append_coach_message(uid, "user", "old question")
        storage.append_coach_message(uid, "assistant", "old answer")
        r = client.post(
            "/api/coach/chat",
            json={"message": "follow-up"},
            headers={"X-User-ID": uid},
        )
        assert r.status_code == 200
        roles = [m["role"] for m in mock_llm["messages"]]
        assert roles == ["user", "assistant", "user"]

    def test_missing_api_key_is_loud_500(self, monkeypatch):
        uid = _uid()
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(llm_client, "_client", None)
        r = client.post(
            "/api/coach/chat",
            json={"message": "hello"},
            headers={"X-User-ID": uid},
        )
        assert r.status_code == 500
        assert r.json()["detail"]["error"] == "coach_not_configured"

    def test_rate_limit_429_after_30_messages(self, mock_llm, monkeypatch):
        uid = _uid()
        for _ in range(service.DAILY_MESSAGE_LIMIT):
            storage.append_coach_message(uid, "user", "x")
        r = client.post(
            "/api/coach/chat",
            json={"message": "one more"},
            headers={"X-User-ID": uid},
        )
        assert r.status_code == 429
        assert r.json()["detail"]["error"] == "daily_limit"

    def test_subscription_fail_closed(self, mock_llm, monkeypatch):
        from backend.engine import subscription_guard

        monkeypatch.setattr(
            subscription_guard,
            "check_subscription",
            lambda user_id: {"can_interact": False, "status": "expired"},
        )
        r = client.post(
            "/api/coach/chat",
            json={"message": "hello"},
            headers={"X-User-ID": _uid()},
        )
        assert r.status_code == 402
        assert r.json()["detail"]["error"] == "subscription_required"

    def test_empty_and_oversized_message_rejected(self, mock_llm):
        uid = _uid()
        r = client.post(
            "/api/coach/chat", json={"message": ""}, headers={"X-User-ID": uid}
        )
        assert r.status_code == 422
        r = client.post(
            "/api/coach/chat",
            json={"message": "   "},
            headers={"X-User-ID": uid},
        )
        assert r.status_code == 422
        r = client.post(
            "/api/coach/chat",
            json={"message": "x" * 5000},
            headers={"X-User-ID": uid},
        )
        assert r.status_code == 422

    def test_invalid_user_id_rejected(self, mock_llm):
        r = client.post(
            "/api/coach/chat",
            json={"message": "hello"},
            headers={"X-User-ID": "not-a-uuid"},
        )
        assert r.status_code == 400


# ── GET /api/coach/history ─────────────────────────────────────────────────

class TestHistoryEndpoint:
    def test_ordering_oldest_first(self):
        uid = _uid()
        for i in range(3):
            storage.append_coach_message(uid, "user", f"m{i}")
        r = client.get("/api/coach/history", headers={"X-User-ID": uid})
        assert r.status_code == 200
        body = r.json()
        assert [m["content"] for m in body["messages"]] == ["m0", "m1", "m2"]
        assert body["has_more"] is False

    def test_pagination_with_before_cursor(self):
        uid = _uid()
        for i in range(5):
            storage.append_coach_message(uid, "user", f"m{i}")
        r = client.get(
            "/api/coach/history", params={"limit": 2}, headers={"X-User-ID": uid}
        )
        body = r.json()
        assert [m["content"] for m in body["messages"]] == ["m3", "m4"]
        assert body["has_more"] is True
        cursor = body["messages"][0]["created_at"]
        r2 = client.get(
            "/api/coach/history",
            params={"limit": 10, "before": cursor},
            headers={"X-User-ID": uid},
        )
        body2 = r2.json()
        assert [m["content"] for m in body2["messages"]] == ["m0", "m1", "m2"]
        assert body2["has_more"] is False

    def test_empty_history(self):
        r = client.get("/api/coach/history", headers={"X-User-ID": _uid()})
        assert r.status_code == 200
        assert r.json() == {"messages": [], "has_more": False}


# ── service window rules ───────────────────────────────────────────────────

class TestServiceWindow:
    def test_history_capped_at_40_messages(self, monkeypatch):
        uid = _uid()
        for i in range(50):
            role = "user" if i % 2 == 0 else "assistant"
            storage.append_coach_message(uid, role, f"m{i}")
        history = service._load_history(uid)
        assert len(history) <= service.HISTORY_MAX_MESSAGES
        assert history[0]["role"] == "user"

    def test_history_drops_leading_assistant(self):
        uid = _uid()
        storage.append_coach_message(uid, "assistant", "orphan")
        storage.append_coach_message(uid, "user", "q")
        history = service._load_history(uid)
        assert history[0]["role"] == "user"
