"""A230 — Mobility & Stretching free-session pool tests.

Covers: catalog validation (counts, flags, schema), region sort order,
GATE-2 soft warning, resolver isolation, free-session lifecycle wiring
(mode guards, zero load, history passthrough), immutability regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine.mobility import (
    GATE2_WARNING,
    MOBILITY_CATALOG_PATH,
    REGION_IDS,
    REGION_ORDER,
    load_mobility_catalog,
    sort_entries,
)

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

EXPECTED_REGION_COUNTS = {
    "forearms_wrists": 5,
    "hips_glutes": 4,
    "chest_anterior_shoulder": 3,
    "thoracic_spine": 3,
    "hip_flexors_quads": 2,
    "adductors_groin": 3,
    "lats": 3,
    "shoulders_scapula": 3,
    "hamstrings": 3,
    "calves_ankles": 3,
    "spine_rotation_obliques": 3,
}
EXPECTED_TOTAL = sum(EXPECTED_REGION_COUNTS.values())  # 35

REQUIRED_FIELDS = {
    "id", "name", "body_region", "type", "mode", "unilateral",
    "hold_seconds_editable", "pnf_capable", "pre_performance_blocked",
    "ux_flow", "kb_validated", "equipment_required", "priority",
    "fatigue_cost", "stress_tags", "recency_group", "image",
    "prescription_defaults", "description",
}

PRESCRIPTION_FIELDS = {
    "sets", "reps", "work_seconds", "rest_between_reps_seconds",
    "rest_between_sets_seconds", "notes",
}


@pytest.fixture(scope="module")
def entries():
    return load_mobility_catalog()


@pytest.fixture(scope="module")
def by_region(entries):
    out = {}
    for e in entries:
        out.setdefault(e["body_region"], []).append(e)
    return out


def _reset():
    client.delete("/api/state")


def _seed_week_plan(sessions_by_date=None, start_date="2026-07-06"):
    """Seed a minimal one-week plan (Mon 2026-07-06 … Sun 2026-07-12)."""
    sessions_by_date = sessions_by_date or {}
    dates = [f"2026-07-{6 + i:02d}" for i in range(7)]
    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    week_plan = {
        "start_date": start_date,
        "weeks": [{
            "days": [
                {
                    "date": dates[i],
                    "weekday": weekdays[i],
                    "sessions": sessions_by_date.get(dates[i], []),
                }
                for i in range(7)
            ],
        }],
    }
    client.put("/api/state", json={"current_week_plan": week_plan})
    return week_plan


# ── Catalog validation ────────────────────────────────────────────────────


class TestCatalog:
    def test_catalog_loads_with_expected_total(self, entries):
        assert len(entries) == EXPECTED_TOTAL

    def test_all_regions_present_with_expected_counts(self, entries):
        counts = {}
        for e in entries:
            counts[e["body_region"]] = counts.get(e["body_region"], 0) + 1
        assert counts == EXPECTED_REGION_COUNTS

    def test_region_order_covers_all_regions(self):
        assert len(REGION_ORDER) == 11
        assert set(REGION_IDS) == set(EXPECTED_REGION_COUNTS)

    def test_schema_all_required_fields(self, entries):
        for e in entries:
            missing = REQUIRED_FIELDS - set(e.keys())
            assert not missing, f"{e.get('id')}: missing {missing}"
            pd_missing = PRESCRIPTION_FIELDS - set(e["prescription_defaults"].keys())
            assert not pd_missing, f"{e['id']}: prescription missing {pd_missing}"

    def test_no_duplicate_ids(self, entries):
        ids = [e["id"] for e in entries]
        assert len(ids) == len(set(ids))

    def test_mode_values(self, entries):
        for e in entries:
            assert e["mode"] in ("timed_hold", "untimed_release"), e["id"]

    def test_priority_values(self, entries):
        for e in entries:
            assert e["priority"] in ("high", "medium", "low"), e["id"]

    def test_timed_hold_have_work_seconds(self, entries):
        for e in entries:
            ws = e["prescription_defaults"]["work_seconds"]
            if e["mode"] == "timed_hold":
                assert isinstance(ws, int) and ws > 0, e["id"]
            else:
                assert ws is None, e["id"]

    def test_unilateral_entries_have_transition_rest(self, entries):
        """Every unilateral (per-side) entry has the mandatory 10s L→R rest."""
        for e in entries:
            if e["unilateral"]:
                assert e["prescription_defaults"]["rest_between_reps_seconds"] == 10, e["id"]

    def test_flag_counts(self, entries):
        blocked = [e["id"] for e in entries if e["pre_performance_blocked"]]
        assert sorted(blocked) == ["stretch_finger_flexor", "stretch_finger_isolation"]

        kb_pending = [e["id"] for e in entries if not e["kb_validated"]]
        assert sorted(kb_pending) == [
            "release_ankle_dorsiflexion_mob",
            "stretch_bar_lat_hang",
            "stretch_thread_the_needle",
        ]

        flow = [e["id"] for e in entries if e["ux_flow"]]
        assert flow == ["stretch_cat_cow_flow"]

    def test_fatigue_cost_zero_except_deep_holds(self, entries):
        heavy = {e["id"] for e in entries if e["fatigue_cost"] == 1}
        assert heavy == {"stretch_adductor_wall", "stretch_pigeon"}
        for e in entries:
            assert e["fatigue_cost"] in (0, 1), e["id"]

    def test_every_region_has_a_no_equipment_entry(self, by_region):
        for region, region_entries in by_region.items():
            assert any(not e["equipment_required"] for e in region_entries), region

    def test_recency_group_follows_mobility_convention(self, entries):
        for e in entries:
            assert e["recency_group"] == f"mobility_{e['body_region']}", e["id"]

    def test_descriptions_are_coaching_copy(self, entries):
        """Descriptions must be substantial and carry the pain-stop cue."""
        for e in entries:
            desc = e["description"]
            assert len(desc) > 100, e["id"]
            lowered = desc.lower()
            assert "stop" in lowered or "ease off" in lowered, e["id"]


# ── Sort order ────────────────────────────────────────────────────────────


class TestSortOrder:
    def test_releases_before_holds_then_priority(self, by_region):
        rank = {"high": 0, "medium": 1, "low": 2}
        for region, region_entries in by_region.items():
            ordered = sort_entries(region_entries)
            keys = [
                (0 if e["mode"] == "untimed_release" else 1, rank[e["priority"]])
                for e in ordered
            ]
            assert keys == sorted(keys), region

    def test_sort_is_deterministic(self, entries):
        once = [e["id"] for e in sort_entries(entries)]
        twice = [e["id"] for e in sort_entries(list(reversed(entries)))]
        assert once == twice


# ── Resolver isolation ────────────────────────────────────────────────────


class TestResolverIsolation:
    def test_mobility_ids_disjoint_from_exercises_catalog(self, entries):
        """Mobility IDs must never leak into the climbing-session resolver.

        The resolver's only exercise source is exercises.json — disjoint ID
        sets guarantee no mobility entry is selectable in planned sessions.
        """
        with open(EXERCISES_PATH, encoding="utf-8") as f:
            exercise_ids = {e["id"] for e in json.load(f)["exercises"]}
        mobility_ids = {e["id"] for e in entries}
        assert not (mobility_ids & exercise_ids)

    def test_mobility_catalog_is_a_separate_file(self):
        assert MOBILITY_CATALOG_PATH.name == "mobility.json"
        assert MOBILITY_CATALOG_PATH.exists()
        assert MOBILITY_CATALOG_PATH != EXERCISES_PATH

    def test_resolver_module_does_not_reference_mobility_catalog(self):
        src = (REPO_ROOT / "backend" / "engine" / "resolve_session.py").read_text()
        assert "mobility.json" not in src
        assert "catalog/mobility" not in src


# ── /api/mobility/pool endpoint ───────────────────────────────────────────


class TestPoolEndpoint:
    def setup_method(self):
        _reset()

    def test_pool_shape_and_order(self):
        r = client.get("/api/mobility/pool")
        assert r.status_code == 200
        data = r.json()
        assert [reg["id"] for reg in data["regions"]] == REGION_IDS
        for reg in data["regions"]:
            assert reg["count"] == EXPECTED_REGION_COUNTS[reg["id"]]
            assert len(reg["entries"]) == reg["count"]
            assert reg["label"]
        assert data["gate2_active"] is False

    def test_invalid_date_422(self):
        r = client.get("/api/mobility/pool", params={"date": "not-a-date"})
        assert r.status_code == 422

    def test_no_warning_without_planned_session(self):
        _seed_week_plan()  # empty days
        r = client.get("/api/mobility/pool", params={"date": "2026-07-08"})
        data = r.json()
        assert data["gate2_active"] is False
        for reg in data["regions"]:
            for e in reg["entries"]:
                assert "warning" not in e


# ── GATE-2 soft warning ───────────────────────────────────────────────────


class TestGate2:
    def setup_method(self):
        _reset()
        _seed_week_plan({
            "2026-07-08": [{
                "session_id": "strength_long",
                "slot": "evening",
                "status": "planned",
            }],
        })

    def test_warning_on_blocked_entries_when_climbing_later(self):
        r = client.get("/api/mobility/pool", params={"date": "2026-07-08"})
        data = r.json()
        assert data["gate2_active"] is True
        forearms = next(reg for reg in data["regions"] if reg["id"] == "forearms_wrists")
        warned = {e["id"] for e in forearms["entries"] if e.get("warning")}
        assert warned == {"stretch_finger_flexor", "stretch_finger_isolation"}
        assert all(e.get("warning") == GATE2_WARNING for e in forearms["entries"] if e.get("warning"))

    def test_soft_never_suppresses_entries(self):
        r = client.get("/api/mobility/pool", params={"date": "2026-07-08"})
        data = r.json()
        total = sum(len(reg["entries"]) for reg in data["regions"])
        assert total == EXPECTED_TOTAL

    def test_no_warning_on_other_regions(self):
        r = client.get("/api/mobility/pool", params={"date": "2026-07-08"})
        data = r.json()
        for reg in data["regions"]:
            if reg["id"] == "forearms_wrists":
                continue
            assert all("warning" not in e for e in reg["entries"]), reg["id"]

    def test_no_warning_on_a_different_day(self):
        r = client.get("/api/mobility/pool", params={"date": "2026-07-09"})
        assert r.json()["gate2_active"] is False

    def test_done_session_does_not_trigger_warning(self):
        _reset()
        _seed_week_plan({
            "2026-07-08": [{
                "session_id": "strength_long",
                "slot": "evening",
                "status": "done",
            }],
        })
        r = client.get("/api/mobility/pool", params={"date": "2026-07-08"})
        assert r.json()["gate2_active"] is False


# ── Free-session lifecycle (surface + mode wiring) ────────────────────────


def _start_mobility(date="2026-07-08"):
    return client.post("/api/free-session/start", json={
        "date": date,
        "surface": "mobility_stretching",
        "session_mode": "mobility",
        "context": "standalone",
    })


class TestFreeSessionLifecycle:
    def setup_method(self):
        _reset()

    def test_start_finish_mobility_session(self):
        r = _start_mobility()
        assert r.status_code == 200
        session_id = r.json()["session_id"]

        payload = {
            "overall_feel": "good",
            "mobility": {
                "completed_entries": [
                    {"id": "stretch_piriformis", "hold_seconds": 60},
                    {"id": "release_pronator_pin"},
                ],
                "completed_count": 2,
            },
        }
        r = client.post(f"/api/free-session/{session_id}/finish", json=payload)
        assert r.status_code == 200
        assert r.json()["load_score"] == 0.0

    def test_mobility_mode_requires_mobility_surface(self):
        r = client.post("/api/free-session/start", json={
            "date": "2026-07-08",
            "surface": "gym_boulder",
            "session_mode": "mobility",
            "context": "standalone",
        })
        assert r.status_code == 400

    def test_mobility_surface_requires_mobility_mode(self):
        r = client.post("/api/free-session/start", json={
            "date": "2026-07-08",
            "surface": "mobility_stretching",
            "session_mode": "free",
            "context": "standalone",
        })
        assert r.status_code == 400

    def test_history_includes_mobility_payload(self):
        session_id = _start_mobility().json()["session_id"]
        client.post(f"/api/free-session/{session_id}/finish", json={
            "mobility": {"completed_count": 3, "completed_entries": []},
        })
        r = client.get("/api/free-session/history", params={"date": "2026-07-08"})
        sessions = r.json()["sessions"]
        mob = next(s for s in sessions if s["id"] == session_id)
        assert mob["session_mode"] == "mobility"
        assert mob["mobility"]["completed_count"] == 3
        assert mob["load_score"] == 0.0

    def test_mobility_session_never_inflates_load(self):
        session_id = _start_mobility().json()["session_id"]
        r = client.post(f"/api/free-session/{session_id}/finish", json={
            "mobility": {"completed_count": 10, "completed_entries": []},
        })
        assert r.json()["load_score"] == 0.0


# ── Immutability regression ───────────────────────────────────────────────


class TestImmutability:
    def setup_method(self):
        _reset()

    def _seed_done_session(self):
        done_session = {
            "session_id": "strength_long",
            "slot": "evening",
            "status": "done",
            "resolved_exercises": [
                {"exercise_id": "max_hangs", "load_kg": 20},
            ],
            "feedback": {"rpe": 8},
        }
        _seed_week_plan({"2026-07-06": [done_session]})
        return done_session

    def _get_done_session(self):
        state = client.get("/api/state").json()
        for week in state["current_week_plan"]["weeks"]:
            for day in week["days"]:
                if day["date"] == "2026-07-06":
                    return day["sessions"][0]
        return None

    def test_mobility_session_plus_replan_leaves_past_sessions_untouched(self):
        expected = self._seed_done_session()

        # Complete a mobility free session
        session_id = _start_mobility(date="2026-07-08").json()["session_id"]
        client.post(f"/api/free-session/{session_id}/finish", json={
            "mobility": {"completed_count": 2, "completed_entries": []},
        })

        # Trigger a replanner ripple on another day
        client.post("/api/replanner/events", json={
            "events": [{
                "event_type": "session_skipped",
                "date": "2026-07-09",
                "slot": "evening",
            }],
        })

        after = self._get_done_session()
        assert after == expected

    def test_free_session_log_survives_macrocycle_regeneration(self):
        session_id = _start_mobility(date="2026-07-08").json()["session_id"]
        client.post(f"/api/free-session/{session_id}/finish", json={
            "mobility": {"completed_count": 1, "completed_entries": []},
        })

        # Minimal goal + profile so macrocycle/generate succeeds
        client.put("/api/state", json={
            "goal": {
                "target_grade": "8a",
                "current_grade": "7c",
                "discipline": "lead",
            },
            "assessment": {
                "self_eval": {
                    "primary_weakness": "pump_too_early",
                    "secondary_weakness": "cant_hold_hard_moves",
                },
                "tests": {},
                "experience": {"climbing_years": 5, "structured_training_years": 2},
            },
        })
        client.post("/api/assessment/compute", json={})
        r = client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        assert r.status_code == 200

        r = client.get("/api/free-session/history", params={"date": "2026-07-08"})
        sessions = r.json()["sessions"]
        assert any(s["id"] == session_id for s in sessions)
        mob = next(s for s in sessions if s["id"] == session_id)
        assert mob["finished_at"] is not None
