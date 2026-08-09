"""A-COACH-V1a — LLM Coach v1 tests.

Covers:
- prompt_builder: L0/L1/L2 always present, L3 routing capped at 3, user
  context (phase/week/today), token-budget truncation, match-user-language +
  suggest-only instruction block, outdoor/other-activity day visibility and
  baselines/working-loads section (B-COACH-CONTEXT-FIX);
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

    def fake_chat(system_blocks, messages, tools=None, tool_executor=None):
        calls["system_blocks"] = system_blocks
        calls["messages"] = messages
        calls["tools"] = tools
        calls["tool_executor"] = tool_executor
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
        # Runtime contract: match-user-language + suggest-only
        # (B-COACH-CONTEXT-FIX: English-only replaced by language matching).
        assert "Respond in the language the user writes in" in block
        assert "ONE language per reply" in block
        assert "Always respond in English" not in block
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

    def test_plan_days_supports_both_week_plan_shapes(self):
        flat = {"days": [{"date": "2026-07-06"}]}
        nested = {"weeks": [{"days": [{"date": "2026-07-06"}]}]}
        assert prompt_builder._plan_days(flat) == [{"date": "2026-07-06"}]
        assert prompt_builder._plan_days(nested) == [{"date": "2026-07-06"}]
        assert prompt_builder._plan_days(None) == []
        assert prompt_builder._plan_days({}) == []

    def test_week_section_renders_planner_shape(self):
        from datetime import date as _date
        from backend.api.deps import this_monday
        monday = this_monday()
        state = deps.load_state(None)
        state["week_plans"] = {
            monday: {
                "weeks": [{
                    "days": [{
                        "date": _date.today().isoformat(),
                        "weekday": "fri",
                        "sessions": [{
                            "session_id": "power_endurance_short",
                            "status": "planned",
                            "location": "gym",
                        }],
                    }],
                }],
            }
        }
        ctx = prompt_builder.build_user_context(state, None)
        assert "power_endurance_short [planned, gym]" in ctx
        assert "(TODAY)" in ctx

    def _state_with_day(self, day_fields):
        """Week plan with a single day (today) carrying *day_fields*."""
        from backend.api.deps import this_monday
        state = deps.load_state(None)
        day = {"date": date.today().isoformat(), "weekday": "sun",
               "sessions": []}
        day.update(day_fields)
        state["week_plans"] = {this_monday(): {"weeks": [{"days": [day]}]}}
        return state

    def test_outdoor_planned_today_visible_not_rest(self):
        """BUG-1 regression: planned outdoor day must never read as rest."""
        state = self._state_with_day({
            "outdoor_spot_name": "Berdorf",
            "outdoor_discipline": "lead",
            "outdoor_session_status": "planned",
        })
        ctx = prompt_builder.build_user_context(state, None)
        assert "OUTDOOR climbing at Berdorf [planned, lead]" in ctx
        assert "never" in ctx and "rest day" in ctx  # anti-rest instruction
        assert "Nothing planned today" not in ctx
        # Week section line must not say rest either.
        week = ctx.split("## Current week plan")[1].split("##")[0]
        assert "rest" not in week.splitlines()[1]

    def test_outdoor_slot_reserved_visible(self):
        state = self._state_with_day({"outdoor_slot": True})
        ctx = prompt_builder.build_user_context(state, None)
        assert "outdoor day reserved" in ctx
        assert "Nothing planned today" not in ctx

    def test_other_activity_and_pretrip_visible(self):
        state = self._state_with_day({
            "other_activity": True,
            "other_activity_name": "yoga",
            "pretrip_deload": True,
        })
        ctx = prompt_builder.build_user_context(state, None)
        assert "other activity: yoga" in ctx
        assert "pre-trip deload day" in ctx

    def test_outdoor_log_in_14d_logs(self):
        uid = _uid()
        storage.append_outdoor_log_line(uid, {
            "date": date.today().isoformat(),
            "spot_name": "Berdorf",
            "discipline": "lead",
            "routes": [{"grade": "6b"}, {"grade": "6c+"}],
        })
        state = deps.load_state(uid)
        ctx = prompt_builder.build_user_context(state, uid)
        # B328 enriched this line (discipline, attempt count, outcomes) — see
        # test_b328_coach_outdoor_context.py for the full rendering contract.
        assert "outdoor lead at Berdorf" in ctx
        assert "6b, 6c+" in ctx

    def test_baselines_and_working_loads_section(self):
        state = deps.load_state(None)
        state["baselines"] = {"hangboard": [{
            "edge_mm": 20, "grip": "half_crimp", "hang_seconds": 7,
            "max_total_load_kg": 75.0, "source": "estimated_from_grade",
            "estimated_at": "2026-07-12",
        }]}
        state["working_loads"] = {"entries": [{
            "exercise_id": "max_hang_7s",
            "setup": {"edge_mm": 20, "grip": "half_crimp"},
            "next_external_load_kg": 12.5,
            "updated_at": "2026-07-10",
        }]}
        ctx = prompt_builder.build_user_context(state, None)
        assert "## Baselines & working loads" in ctx
        assert "Hangboard max: 75.0 kg total (20mm edge, half_crimp, 7s hang)" in ctx
        assert "max_hang_7s (edge_mm=20, grip=half_crimp): next external load 12.5 kg" in ctx

    def test_baselines_empty_says_no_numbers(self):
        state = deps.load_state(None)
        state["baselines"] = {}
        state["working_loads"] = {}
        state.setdefault("assessment", {})["tests"] = {}
        ctx = prompt_builder.build_user_context(state, None)
        assert "Do NOT invent" in ctx

    def test_trips_and_planned_load_and_last_assessed(self):
        from backend.api.deps import this_monday
        state = deps.load_state(None)
        state["trips"] = [{"name": "Arco primavera", "start_date": "2026-08-01",
                           "end_date": "2026-08-05", "discipline": "lead",
                           "priority": "alta"}]
        state.setdefault("assessment", {})["last_assessed"] = "2026-07-01"
        state["week_plans"] = {this_monday(): {
            "weekly_load_summary": {"planned_load": 42},
            "weeks": [{"days": [{"date": date.today().isoformat(),
                                 "weekday": "sun", "sessions": []}]}],
        }}
        ctx = prompt_builder.build_user_context(state, None)
        assert "Planned trip: Arco primavera 2026-08-01 → 2026-08-05" in ctx
        assert "Planned training load this week: 42" in ctx
        assert "Last assessed: 2026-07-01" in ctx

    def test_build_system_prompt_joins_blocks(self):
        prompt = prompt_builder.build_system_prompt(None, "periodization")
        assert "Respond in the language the user writes in" in prompt
        assert "=== USER CONTEXT" in prompt


# ── A-COACH-V1b: weather, notes, suggestions ───────────────────────────────

OWM_CURRENT = {
    "main": {"temp": 31.0, "feels_like": 33.0, "humidity": 55},
    "wind": {"speed": 2.0, "deg": 180},
    "clouds": {"all": 20},
    "weather": [{"id": 800, "description": "clear sky"}],
}


def _owm_forecast_for(date_iso: str):
    return {
        "list": [{
            "dt_txt": f"{date_iso} 12:00:00",
            "main": {"temp": 18.0, "feels_like": 18.0, "humidity": 50},
            "wind": {"speed": 3.0, "deg": 90},
            "clouds": {"all": 10},
            "weather": [{"id": 801, "description": "few clouds"}],
            "pop": 0.1,
        }]
    }


class TestCoachV1b:
    @pytest.fixture(autouse=True)
    def clear_weather_caches(self):
        from backend.api.routers import weather
        weather._cache.clear()
        weather._geo_cache.clear()
        yield
        weather._cache.clear()
        weather._geo_cache.clear()

    def _state_with_outdoor(self, date_iso):
        from backend.api.deps import this_monday
        state = deps.load_state(None)
        state["week_plans"] = {this_monday(): {"weeks": [{"days": [{
            "date": date_iso, "weekday": "sun", "sessions": [],
            "outdoor_spot_name": "Berdorf",
            "outdoor_discipline": "lead",
            "outdoor_session_status": "planned",
        }]}]}}
        return state

    def test_weather_never_prefetched_into_context(self, monkeypatch):
        # A244: weather is on-demand tool use, never injected into the prompt.
        from backend.api.routers import weather

        def boom(*a, **kw):
            raise AssertionError("weather must NOT be fetched at prompt-build time")

        monkeypatch.setattr(weather, "_owm_get", boom)
        monkeypatch.setattr(weather, "_owm_geocode_get", boom)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        state = self._state_with_outdoor(tomorrow)
        dynamic = prompt_builder.build_dynamic_block(state, None, "meteo")
        assert "## Weather" not in dynamic
        assert "=== USER CONTEXT" in dynamic  # context intact

    def test_geocode_does_not_cache_transient_failure(self, monkeypatch):
        from backend.api.routers import weather

        def boom(q):
            raise weather.WeatherUnavailable("down")

        monkeypatch.setattr(weather, "_owm_geocode_get", boom)
        assert weather.geocode_place("Berdorf") is None
        monkeypatch.setattr(
            weather, "_owm_geocode_get", lambda q: [{"lat": 1.0, "lon": 2.0}]
        )
        assert weather.geocode_place("Berdorf") == (1.0, 2.0)
        assert weather.geocode_place("BERDORF") == (1.0, 2.0)  # cached, case-insensitive

    def test_coach_notes_in_context_capped(self):
        state = deps.load_state(None)
        state.setdefault("preferences", {})["coach_notes"] = (
            "Ho paura di volare su lead. " + "x" * 600
        )
        ctx = prompt_builder.build_user_context(state, None)
        assert "## Personal notes from the athlete" in ctx
        assert "Ho paura di volare su lead." in ctx
        start = ctx.index("## Personal notes")
        section = ctx[start:].split("\n\n")[0]
        notes_body = section.splitlines()[-1]
        assert len(notes_body) <= prompt_builder.MAX_COACH_NOTES_CHARS

    def test_no_notes_no_section(self):
        state = deps.load_state(None)
        (state.setdefault("preferences", {}))["coach_notes"] = "   "
        ctx = prompt_builder.build_user_context(state, None)
        assert "## Personal notes" not in ctx

    def test_chat_endpoint_passes_weather_tool_and_executor(self, mock_llm):
        # A244: the chat turn wires the get_weather tool + an executor; coords
        # are handed to the executor (not pre-fetched into the prompt).
        uid = _uid()
        r = client.post(
            "/api/coach/chat",
            json={"message": "che tempo fa?", "lat": 49.6, "lon": 6.1},
            headers={"X-User-ID": uid},
        )
        assert r.status_code == 200
        tool_names = [t["name"] for t in (mock_llm["tools"] or [])]
        assert "get_weather" in tool_names
        assert callable(mock_llm["tool_executor"])
        # Unknown tools are handled gracefully (never raise into the loop).
        assert "Unknown tool" in mock_llm["tool_executor"]("nope", {})

    def test_chat_endpoint_rejects_bad_coords(self, mock_llm):
        r = client.post(
            "/api/coach/chat",
            json={"message": "hi", "lat": 123.0, "lon": 6.1},
            headers={"X-User-ID": _uid()},
        )
        assert r.status_code == 422

    def test_suggestions_endpoint_outdoor_and_session(self):
        from backend.api.deps import this_monday
        uid = _uid()
        today_iso = date.today().isoformat()
        state = deps.load_state(uid)
        state["week_plans"] = {this_monday(): {"weeks": [{"days": [
            {
                "date": today_iso, "weekday": "sun",
                "sessions": [{"session_id": "strength_long",
                              "status": "planned", "location": "gym"}],
                "outdoor_spot_name": "Berdorf",
                "outdoor_discipline": "lead",
                "outdoor_session_status": "planned",
            },
        ]}]}}
        deps.save_state(state, uid)
        r = client.get("/api/coach/suggestions", headers={"X-User-ID": uid})
        assert r.status_code == 200
        sugg = r.json()["suggestions"]
        assert any("Berdorf today" in s for s in sugg)
        assert any("today's session" in s for s in sugg)
        assert 1 <= len(sugg) <= service.MAX_SUGGESTIONS

    def test_suggestions_fallback_always_present(self):
        r = client.get("/api/coach/suggestions", headers={"X-User-ID": _uid()})
        assert r.status_code == 200
        sugg = r.json()["suggestions"]
        assert "How is my training going so far?" in sugg


# ── A244: on-demand weather tool ───────────────────────────────────────────

from types import SimpleNamespace  # noqa: E402


def _fake_usage():
    return SimpleNamespace(
        input_tokens=10, output_tokens=5,
        cache_read_input_tokens=1, cache_creation_input_tokens=0,
    )


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(name, tid, tool_input):
    return SimpleNamespace(type="tool_use", name=name, id=tid, input=tool_input)


class _FakeMessages:
    """Serves a scripted list of responses on successive .create() calls."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


class TestWeatherTool:
    @pytest.fixture(autouse=True)
    def clear_weather_caches(self, monkeypatch):
        from backend.api.routers import weather
        weather._cache.clear()
        weather._geo_cache.clear()
        yield
        weather._cache.clear()
        weather._geo_cache.clear()

    # ---- executor -----------------------------------------------------------

    def test_here_uses_client_gps(self, monkeypatch):
        from backend.api.routers import weather
        from backend.coach import weather_tool
        monkeypatch.setattr(weather, "_owm_get", lambda p, lat, lon: OWM_CURRENT)
        out = weather_tool.execute_get_weather(
            {"location": "here", "days_ahead": 0}, {}, lat=49.6, lon=6.1
        )
        assert "your current location" in out
        assert "31.0°C" in out and "friction band" in out

    def test_here_without_gps_is_unavailable(self):
        from backend.coach import weather_tool
        out = weather_tool.execute_get_weather(
            {"location": "here"}, {}, lat=None, lon=None
        )
        assert "unavailable" in out.lower() and "here" in out.lower()

    def test_named_place_forecast(self, monkeypatch):
        from backend.api.routers import weather
        from backend.coach import weather_tool
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        monkeypatch.setattr(
            weather, "_owm_geocode_get", lambda q: [{"lat": 49.82, "lon": 6.35}]
        )
        monkeypatch.setattr(
            weather, "_owm_get", lambda p, lat, lon: _owm_forecast_for(tomorrow)
        )
        out = weather_tool.execute_get_weather(
            {"location": "Berdorf", "days_ahead": 1}, {}
        )
        assert "Berdorf" in out and "1 day(s)" in out and "friction band" in out

    def test_unresolvable_place_is_unavailable(self, monkeypatch):
        from backend.api.routers import weather
        from backend.coach import weather_tool
        monkeypatch.setattr(weather, "_owm_geocode_get", lambda q: [])
        out = weather_tool.execute_get_weather({"location": "Nowheresville"}, {})
        assert "unavailable" in out.lower()

    def test_provider_failure_never_raises(self, monkeypatch):
        from backend.api.routers import weather
        from backend.coach import weather_tool

        def boom(*a, **kw):
            raise weather.WeatherUnavailable("down")

        monkeypatch.setattr(weather, "_owm_get", boom)
        out = weather_tool.execute_get_weather(
            {"location": "here"}, {}, lat=1.0, lon=2.0
        )
        assert "unavailable" in out.lower()

    def test_days_ahead_clamped(self):
        from backend.coach import weather_tool
        # 99 → clamped to the 5-day OWM horizon; bad type → 0. Neither raises.
        assert weather_tool.execute_get_weather(
            {"location": "here", "days_ahead": 99}, {}, lat=None, lon=None
        )
        assert weather_tool.execute_get_weather(
            {"location": "here", "days_ahead": "oops"}, {}, lat=None, lon=None
        )

    # ---- llm_client tool-use loop ------------------------------------------

    def test_chat_runs_tool_loop_and_returns_text(self, monkeypatch):
        from backend.coach import llm_client
        calls = {"exec": []}

        def executor(name, tool_input):
            calls["exec"].append((name, tool_input))
            return "Weather at Berdorf (now): 18.0°C, friction band: prime (85/100)"

        responses = [
            SimpleNamespace(
                stop_reason="tool_use",
                content=[_tool_use_block("get_weather", "t1", {"location": "Berdorf"})],
                usage=_fake_usage(),
            ),
            SimpleNamespace(
                stop_reason="end_turn",
                content=[_text_block("Conditions at Berdorf look prime today.")],
                usage=_fake_usage(),
            ),
        ]
        fake = _FakeClient(responses)
        monkeypatch.setattr(llm_client, "_get_client", lambda: fake)

        reply = llm_client.chat(
            ["static", "dynamic"],
            [{"role": "user", "content": "conditions at Berdorf?"}],
            tools=[{"name": "get_weather"}],
            tool_executor=executor,
        )
        assert reply == "Conditions at Berdorf look prime today."
        assert calls["exec"] == [("get_weather", {"location": "Berdorf"})]
        # Second create() carried the tool_result turn back to the model.
        assert len(fake.messages.create_calls) == 2
        last_msgs = fake.messages.create_calls[1]["messages"]
        assert any(
            m["role"] == "user" and isinstance(m["content"], list)
            and m["content"][0].get("type") == "tool_result"
            for m in last_msgs
        )

    def test_chat_without_tools_is_single_call(self, monkeypatch):
        from backend.coach import llm_client
        fake = _FakeClient([
            SimpleNamespace(
                stop_reason="end_turn",
                content=[_text_block("Plain answer.")],
                usage=_fake_usage(),
            )
        ])
        monkeypatch.setattr(llm_client, "_get_client", lambda: fake)
        reply = llm_client.chat(["static", "dynamic"], [{"role": "user", "content": "hi"}])
        assert reply == "Plain answer."
        assert len(fake.messages.create_calls) == 1
        assert "tools" not in fake.messages.create_calls[0]

    def test_tool_loop_respects_call_cap(self, monkeypatch):
        from backend.coach import llm_client
        n_exec = {"n": 0}

        def executor(name, tool_input):
            n_exec["n"] += 1
            return "some weather"

        # Model keeps asking for a tool every turn; the loop must terminate and
        # never execute more than MAX_TOOL_CALLS real lookups.
        def tool_resp(i):
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[_tool_use_block("get_weather", f"t{i}", {"location": "x"})],
                usage=_fake_usage(),
            )

        text_resp = SimpleNamespace(
            stop_reason="end_turn", content=[_text_block("done")], usage=_fake_usage()
        )
        # Enough tool responses to exceed the iteration cap, then a text answer.
        fake = _FakeClient([tool_resp(i) for i in range(10)] + [text_resp])
        monkeypatch.setattr(llm_client, "_get_client", lambda: fake)
        reply = llm_client.chat(
            ["s", "d"], [{"role": "user", "content": "weather?"}],
            tools=[{"name": "get_weather"}], tool_executor=executor,
        )
        assert isinstance(reply, str)
        assert n_exec["n"] <= llm_client.MAX_TOOL_CALLS


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
        assert "Respond in the language the user writes in" in mock_llm["system_blocks"][0]
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
