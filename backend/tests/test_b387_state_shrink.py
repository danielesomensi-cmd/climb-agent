"""B387 — smaller user_state: codec for current_week_plan, lean custom
exercises, lean GET /api/state.

Invariants under test:
- the codec is lossless, pure, idempotent and reads legacy blobs unchanged;
- after a load the two plan copies are equal and independent, as with JSON;
- past weeks survive a write/read cycle byte for byte;
- a lean custom exercise plays exactly like the stored original, and an
  exercise that would not (drifted cue, partial pre-B283 fields) is kept as is;
- GET /api/state omits only the heavy keys, says so, and ``?full=1`` restores them.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers import custom_session as cs_router
from backend.engine import state_codec
from backend.engine import storage_file

client = TestClient(app)


def _plan(start: str, status: str = "planned") -> dict:
    return {"start_date": start, "weeks": [{"days": [
        {"date": start, "sessions": [{"session_id": "strength_long", "slot": "evening", "status": status,
                                      "resolved": {"resolved_session": {"exercise_instances": [
                                          {"exercise_id": "max_hang_7s", "sets": 4}]}}}]},
    ]}]}


def _state() -> dict:
    past, cur = _plan("2026-10-05", "done"), _plan("2026-10-12")
    return {
        "schema_version": "1.6",
        "week_plans": {"2026-10-05": past, "2026-10-12": cur},
        "current_week_plan": deepcopy(cur),
        "goal": {"target_grade": "8b"},
    }


# ── (1) codec ───────────────────────────────────────────────────────────────


def test_pack_replaces_the_duplicate_with_a_pointer():
    state = _state()
    packed = state_codec.pack(state)
    assert "current_week_plan" not in packed
    assert packed["current_week_key"] == "2026-10-12"
    assert len(json.dumps(packed)) < len(json.dumps(state))


def test_pack_does_not_mutate_the_caller():
    state = _state()
    before = deepcopy(state)
    state_codec.pack(state)
    assert state == before


def test_round_trip_is_lossless_and_copies_are_independent():
    state = _state()
    back = state_codec.unpack(json.loads(json.dumps(state_codec.pack(state))))
    assert back == state
    assert "current_week_key" not in back
    # Same semantics as a JSON load: two equal, independent objects.
    assert back["current_week_plan"] is not back["week_plans"]["2026-10-12"]
    back["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]["status"] = "done"
    assert back["week_plans"]["2026-10-12"]["weeks"][0]["days"][0]["sessions"][0]["status"] == "planned"


def test_divergent_copies_are_stored_in_full():
    state = _state()
    state["current_week_plan"]["weeks"][0]["days"][0]["sessions"][0]["status"] = "done"
    packed = state_codec.pack(state)
    assert packed["current_week_plan"] == state["current_week_plan"]
    assert "current_week_key" not in packed
    assert state_codec.unpack(deepcopy(packed)) == state


def test_archived_or_missing_week_is_stored_in_full():
    state = _state()
    del state["week_plans"]["2026-10-12"]  # A221 moved it to the cold store
    packed = state_codec.pack(state)
    assert packed["current_week_plan"] == state["current_week_plan"]
    for cwp in (None, {"weeks": []}, {"start_date": "", "weeks": []}):
        s = _state()
        s["current_week_plan"] = cwp
        assert state_codec.pack(s)["current_week_plan"] == cwp


def test_legacy_blob_reads_unchanged_and_pack_is_idempotent():
    legacy = _state()
    assert state_codec.unpack(deepcopy(legacy)) == legacy
    once = state_codec.pack(legacy)
    assert state_codec.pack(state_codec.unpack(deepcopy(once))) == once


def test_stale_pointer_next_to_a_full_copy_loses_to_the_copy():
    state = _state()
    stored = dict(state, current_week_key="2026-10-05")
    assert state_codec.unpack(stored) == state


def test_kill_switch_writes_the_full_copy(monkeypatch):
    monkeypatch.setenv("STATE_CODEC_PACK", "0")
    state = _state()
    packed = state_codec.pack(state)
    assert packed == state
    monkeypatch.setenv("STATE_CODEC_PACK", "false")  # only the literal 0 disables
    assert "current_week_plan" not in state_codec.pack(state)


def test_file_backend_round_trip_keeps_past_weeks_byte_for_byte(tmp_path, monkeypatch):
    path = tmp_path / "user_state.json"
    monkeypatch.setattr(storage_file, "_user_state_path", lambda uid: path)
    state = _state()
    past_before = json.dumps(state["week_plans"]["2026-10-05"], sort_keys=True)
    storage_file.write_state(state, "u1")
    raw = json.loads(path.read_text())
    assert "current_week_plan" not in raw and raw["current_week_key"] == "2026-10-12"
    back = storage_file.read_state("u1")
    assert back == state
    assert json.dumps(back["week_plans"]["2026-10-05"], sort_keys=True) == past_before


def test_supabase_backend_upserts_the_packed_blob_and_unpacks_on_read(monkeypatch):
    from backend.engine import storage_supabase as sb

    rows = {}

    class _Q:
        def __init__(self):
            self._payload = None

        def upsert(self, payload):
            self._payload = payload
            return self

        def select(self, *_a):
            return self

        def eq(self, *_a):
            return self

        def execute(self):
            if self._payload is not None:
                rows["u1"] = json.loads(json.dumps(self._payload["state"]))
                return type("R", (), {"data": [self._payload]})()
            return type("R", (), {"data": [{"state": json.loads(json.dumps(rows["u1"]))}]})()

    class _C:
        def table(self, _name):
            return _Q()

    monkeypatch.setattr(sb, "_sb", lambda: _C())
    state = _state()
    sb.write_state(state, "u1")
    assert "current_week_plan" not in rows["u1"]
    assert sb.read_state("u1") == state


# ── (2) lean custom exercises ───────────────────────────────────────────────


def _catalog():
    return cs_router._load_exercises_catalog()


def _enriched(ex_id: str, **user) -> dict:
    ex = {"exercise_id": ex_id, "sets": 3, "reps": 8, **user}
    return cs_router._enrich_exercise_display(ex, _catalog())


def test_storage_form_drops_display_fields_and_plays_identically():
    full = _enriched("pallof_press")
    lean = cs_router.storage_form(dict(full))
    for k in cs_router.STORED_DISPLAY_KEYS:
        assert k not in lean
    assert lean["exercise_id"] == "pallof_press" and lean["sets"] == 3
    assert cs_router._play_exercise(lean) == cs_router._play_exercise(full)


def test_default_notes_are_dropped_user_notes_kept():
    cat = _catalog()
    ex_id = next(i for i, e in cat.items() if (e.get("prescription_defaults") or {}).get("notes") and e.get("cues"))
    assert "notes" not in cs_router.storage_form(_enriched(ex_id))
    mine = cs_router.storage_form(_enriched(ex_id, notes="gomiti stretti"))
    assert mine["notes"] == "gomiti stretti"


def test_drifted_cue_is_kept_so_the_athlete_sees_what_was_saved():
    full = _enriched("pallof_press")
    full["cues"] = ["a cue the catalog has since rewritten"]
    assert cs_router.storage_form(dict(full)) == full


def test_partial_pre_b283_entry_is_kept():
    partial = {"exercise_id": "pallof_press", "sets": 3, "reps": 8, "cues": ["old"]}
    assert cs_router.storage_form(dict(partial)) == partial


def test_api_stores_lean_and_serves_the_same_session():
    client.delete("/api/state")
    try:
        created = client.post("/api/custom-session", json={"name": "Core", "exercises": [
            {"exercise_id": "pallof_press", "sets": 3, "reps": 10},
            {"exercise_id": "weighted_pullup", "sets": 4, "reps": 3, "load_kg": 28.0},
        ]})
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["exercises"][0]["name"] and body["exercises"][0]["alt_sides"] is True  # response unchanged

        stored = client.get("/api/state?full=1").json()["custom_sessions"][0]
        for ex in stored["exercises"]:
            for k in cs_router.STORED_DISPLAY_KEYS:
                assert k not in ex
        assert stored["estimated_duration_minutes"] == body["estimated_duration_minutes"]

        sid = body["id"]
        lean_views = [client.get(f"/api/custom-session/{sid}{q}").json() for q in ("", "?date=2026-10-20")]

        # The same session stored the pre-B387 way (display fields included)
        # must serve exactly the same thing, with and without a date.
        from backend.api import deps

        state = deps.load_state(None)
        state["custom_sessions"][0] = dict(stored, exercises=[
            cs_router._enrich_exercise_display(dict(ex), cs_router._load_exercises_catalog())
            for ex in stored["exercises"]])
        deps.save_state(state, None)
        legacy_views = [client.get(f"/api/custom-session/{sid}{q}").json() for q in ("", "?date=2026-10-20")]
        assert lean_views == legacy_views
    finally:
        client.delete("/api/state")


# ── (3) lean GET /api/state ─────────────────────────────────────────────────


def test_get_state_is_lean_and_says_what_it_left_out():
    client.delete("/api/state")
    try:
        client.put("/api/state", json={"week_plans": {"2099-01-05": {"start_date": "2099-01-05", "weeks": []}}})
        lean = client.get("/api/state").json()
        for k in ("week_plans", "current_week_plan", "custom_sessions"):
            assert k not in lean
        assert "week_plans" in lean["_omitted"]
        assert "goal" in lean or "profile" in lean  # the rest is untouched
        full = client.get("/api/state?full=1").json()
        assert "2099-01-05" in full["week_plans"] and "_omitted" not in full
        put = client.put("/api/state", json={"preferences": {"x_b387": 1}}).json()
        assert "week_plans" not in put and "week_plans" in put["_omitted"]
        # The lean PUT response did not drop anything from the stored state.
        assert "2099-01-05" in client.get("/api/state?full=1").json()["week_plans"]
    finally:
        client.delete("/api/state")


def test_lean_response_keys_are_never_read_by_the_frontend():
    """Guard: if the app starts reading one of the omitted keys from getState(),
    this fails — move it to its own endpoint or out of _LEAN_OMIT."""
    import pathlib
    import re

    from backend.api.routers.state import _LEAN_OMIT

    root = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
    if not root.exists():
        pytest.skip("frontend not checked out")
    hits = []
    for p in root.rglob("*.ts*"):
        if "__tests__" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for k in _LEAN_OMIT:
            if re.search(rf"\b{k}\b", text):
                hits.append(f"{p.relative_to(root)}: {k}")
    assert hits == []
