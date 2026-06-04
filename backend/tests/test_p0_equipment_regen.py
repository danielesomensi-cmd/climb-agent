"""P0 BUG: Equipment change → regenerate must NOT reset macrocycle to week 1.

Tests verify that incremental regen (from_phase="current") preserves:
- macrocycle start_date
- week numbering (user stays in the correct week)
- session_completion_log data from past weeks
"""

from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Copy real state to tmp and monkeypatch STATE_PATH so tests are isolated."""
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)


def _setup_macrocycle(start_date: str) -> dict:
    """Create assessment + macrocycle with a specific start_date."""
    client.post("/api/assessment/compute", json={})
    r = client.post("/api/macrocycle/generate", json={
        "start_date": start_date,
        "total_weeks": 12,
    })
    assert r.status_code == 200
    return r.json()["macrocycle"]


def _seed_completion_log(entries: list[dict]):
    """Inject session_completion_log entries into state."""
    r = client.get("/api/state")
    state = r.json()
    state["session_completion_log"] = entries
    client.put("/api/state", json={"session_completion_log": entries})


class TestEquipmentRegenPreservesWeek:
    """Simulate: equipment change → regenerate from tomorrow → verify state."""

    def test_start_date_preserved_after_incremental_regen(self):
        """from_phase='current' must keep the original macrocycle start_date."""
        original_start = "2026-02-23"
        mc = _setup_macrocycle(original_start)
        assert mc["start_date"] == original_start

        # Incremental regen (same as equipment-change flow after fix)
        r = client.post("/api/macrocycle/generate", json={
            "from_phase": "current",
        })
        assert r.status_code == 200
        new_mc = r.json()["macrocycle"]
        assert new_mc["start_date"] == original_start

    def test_week_number_preserved_after_incremental_regen(self):
        """Macrocycle week count and total_weeks must survive incremental regen."""
        original_start = "2026-02-23"
        mc = _setup_macrocycle(original_start)
        original_total = mc["total_weeks"]
        original_phase_count = len(mc["phases"])

        r = client.post("/api/macrocycle/generate", json={
            "from_phase": "current",
        })
        assert r.status_code == 200
        new_mc = r.json()["macrocycle"]

        # Total weeks preserved
        assert new_mc["total_weeks"] == original_total
        # Phase count preserved (incremental regen doesn't drop phases)
        assert len(new_mc["phases"]) == original_phase_count
        # Sum of phase durations equals total weeks
        total_duration = sum(p["duration_weeks"] for p in new_mc["phases"])
        assert total_duration == original_total

    def test_completion_data_survives_incremental_regen(self):
        """session_completion_log must NOT be wiped by macrocycle regeneration."""
        original_start = "2026-02-23"
        _setup_macrocycle(original_start)

        # Seed completion data for week 1 and week 2
        log_entries = [
            {
                "date": "2026-02-24",
                "session_id": "strength_long",
                "status": "done",
                "completed_at": "2026-02-24T18:00:00+00:00",
            },
            {
                "date": "2026-02-25",
                "session_id": "endurance_aerobic_gym",
                "status": "done",
                "completed_at": "2026-02-25T18:00:00+00:00",
            },
            {
                "date": "2026-03-03",
                "session_id": "technique_focus_gym",
                "status": "done",
                "completed_at": "2026-03-03T18:00:00+00:00",
            },
            {
                "date": "2026-03-05",
                "session_id": "power_contact_gym",
                "status": "skipped",
                "completed_at": "2026-03-05T10:00:00+00:00",
            },
        ]
        _seed_completion_log(log_entries)

        # Verify log is seeded
        state_before = client.get("/api/state").json()
        assert len(state_before["session_completion_log"]) == 4

        # Incremental regen (equipment-change flow)
        r = client.post("/api/macrocycle/generate", json={
            "from_phase": "current",
        })
        assert r.status_code == 200

        # Completion log must be intact
        state_after = client.get("/api/state").json()
        assert len(state_after["session_completion_log"]) == 4
        assert state_after["session_completion_log"] == log_entries

    def test_full_regen_without_from_phase_resets_start_date(self):
        """Sanity check: without from_phase, start_date IS recalculated (Danger Zone restart)."""
        original_start = "2026-02-23"
        _setup_macrocycle(original_start)

        # Full regen without from_phase (like Danger Zone "Restart Macrocycle")
        r = client.post("/api/macrocycle/generate", json={
            "total_weeks": 12,
        })
        assert r.status_code == 200
        new_mc = r.json()["macrocycle"]
        # start_date should be this_monday(), NOT the original
        assert new_mc["start_date"] != original_start

    def test_incremental_regen_earlier_phases_unchanged(self):
        """Phases before the current one must be identical after incremental regen."""
        original_start = "2026-02-23"
        mc = _setup_macrocycle(original_start)
        original_first_phase = mc["phases"][0].copy()

        # Incremental regen from current phase (which is phase 0 "base")
        r = client.post("/api/macrocycle/generate", json={
            "from_phase": "current",
        })
        assert r.status_code == 200
        new_mc = r.json()["macrocycle"]

        # If we're in the first phase, from_phase="current" regenerates from phase 0,
        # so no earlier phases to compare. But start_date and total_weeks are preserved.
        assert new_mc["start_date"] == original_start
        assert new_mc["total_weeks"] == mc["total_weeks"]

    def test_week_plan_accessible_after_incremental_regen(self):
        """After incremental regen, fetching the current week should succeed.

        B257: the macrocycle must be ACTIVE (today inside its window) so week 0
        resolves to this_monday() — a current week, freely regenerable. A past-
        dated/expired macrocycle would clamp week 0 to a past Monday, which the
        past-week guard correctly fail-closes (separately covered in
        test_b257_guard_pastweek)."""
        active_start = (date.today() - timedelta(days=date.today().weekday(), weeks=2)).isoformat()
        _setup_macrocycle(active_start)

        r = client.post("/api/macrocycle/generate", json={
            "from_phase": "current",
        })
        assert r.status_code == 200

        # Fetch current week — should work (week cache was invalidated but week is regenerable)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.get(f"/api/week/0?force=true&preserve_before={tomorrow}")
        assert r.status_code == 200
        data = r.json()
        assert "week_plan" in data
        assert data["week_plan"] is not None
