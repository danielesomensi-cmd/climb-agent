"""B305 — adhoc composer field fixes (2026-07-28 coach conversation).

Invariants under test:
  1. `_exercise_fits_equipment` honours equipment_required_any (OR) — board-only
     exercises (equipment_required=[] + equipment_required_any=[boards]) must
     NOT leak into a home session (the "board limit boulder a casa" bug).
  2. Focus "pull" reaches the pullup/lock-off family at home — the catalog now
     tags it strength_pulling / lock_off_endurance (before B305 nearly every
     pulling exercise was strength_general-only and a "bloccaggi" request
     composed a session without any bloccaggi).
  3. The adhoc chat summary is localized (it/en) via the extractor's language
     slot, and the Italian frame still carries the explanation (A252 honesty
     notes must never be dropped).
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.coach.service import build_adhoc_summary
from backend.engine.adhoc_builder import compose_adhoc_session
from backend.engine.body_part_picker import _exercise_fits_equipment

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

HOME_EQUIPMENT = ["hangboard", "pullup_bar", "dumbbell", "band", "resistance_band", "loading_pin"]

# Exercises gated ONLY by equipment_required_any on boards/walls — none of which
# exist at home. The pre-B305 filter let all of these through.
BOARD_ONLY_IDS = {"board_limit_boulders", "system_board_limit", "spray_wall_limit", "limit_bouldering"}

LOCKOFF_FAMILY = {
    "lock_off_isometric", "archer_pullup", "typewriter_pullup",
    "one_arm_pullup_assisted", "uneven_grip_pullup",
}


def _catalog() -> dict:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("exercises") or list(raw.values()))
    return {ex["id"]: ex for ex in items if isinstance(ex, dict) and ex.get("id")}


def _state() -> dict:
    return {
        "equipment": {"home": list(HOME_EQUIPMENT), "gyms": []},
        "macrocycle": {
            "start_date": "2026-07-06",
            "phases": [{"phase_id": "performance", "duration_weeks": 3}],
        },
        "recent_sessions": [],
    }


# ── 1. equipment_required_any (OR) ──────────────────────────────────────


class TestEquipmentRequiredAny:
    def test_board_only_exercise_rejected_at_home(self):
        catalog = _catalog()
        for eid in BOARD_ONLY_IDS:
            ex = catalog[eid]
            assert not _exercise_fits_equipment(ex, HOME_EQUIPMENT), eid

    def test_board_only_exercise_accepted_with_board(self):
        catalog = _catalog()
        ex = catalog["board_limit_boulders"]
        assert _exercise_fits_equipment(ex, ["board_moonboard", "pullup_bar"])

    def test_any_is_or_not_and(self):
        ex = {"equipment_required": [], "equipment_required_any": ["a", "b", "c"]}
        assert _exercise_fits_equipment(ex, ["b"])
        assert not _exercise_fits_equipment(ex, ["z"])

    def test_required_and_any_combined(self):
        ex = {"equipment_required": ["pullup_bar"], "equipment_required_any": ["band", "rings"]}
        assert _exercise_fits_equipment(ex, ["pullup_bar", "band"])
        assert not _exercise_fits_equipment(ex, ["pullup_bar"])       # any unmet
        assert not _exercise_fits_equipment(ex, ["band", "rings"])    # required unmet

    def test_no_constraints_still_fits(self):
        assert _exercise_fits_equipment({}, [])


# ── 2. "bloccaggi + core" at home composes lock-offs, never boards ──────


class TestHomePullComposition:
    def test_no_board_exercise_in_home_session(self):
        intent = {"equipment_set": "home", "focus": "pull", "secondary_focus": "core", "minutes": 60}
        session = compose_adhoc_session(intent, _state(), _catalog())
        ids = {e["exercise_id"] for e in session["exercises"]}
        assert not (ids & BOARD_ONLY_IDS), ids

    def test_pull_focus_reaches_lockoff_family_at_home(self):
        intent = {"equipment_set": "home", "focus": "pull", "secondary_focus": "core", "minutes": 60}
        session = compose_adhoc_session(intent, _state(), _catalog())
        ids = {e["exercise_id"] for e in session["exercises"]}
        assert ids & LOCKOFF_FAMILY, ids

    def test_pull_plus_core_has_core_block(self):
        intent = {"equipment_set": "home", "focus": "pull", "secondary_focus": "core", "minutes": 60}
        catalog = _catalog()
        session = compose_adhoc_session(intent, _state(), catalog)
        domains = set()
        for e in session["exercises"]:
            d = catalog[e["exercise_id"]].get("domain")
            domains.update([d] if isinstance(d, str) else d or [])
        assert "core" in domains, domains

    def test_deterministic(self):
        intent = {"equipment_set": "home", "focus": "pull", "secondary_focus": "core", "minutes": 60}
        a = compose_adhoc_session(intent, _state(), _catalog())
        b = compose_adhoc_session(intent, _state(), _catalog())
        assert a == b


# ── 3. summary localization ─────────────────────────────────────────────


SESSION_STUB = {
    "name": "Adhoc core + pull (home)",
    "estimated_duration_minutes": 60,
    "explanation": "A ~60-min core + pull session for home.",
}


class TestSummaryLocalization:
    def test_english_default(self):
        s = build_adhoc_summary(SESSION_STUB, {})
        assert s.startswith("I built you a session")

    def test_italian(self):
        s = build_adhoc_summary(SESSION_STUB, {"language": "it"})
        assert s.startswith("Ti ho preparato una sessione")
        # A252: the explanation (honesty notes) must survive localization.
        assert SESSION_STUB["explanation"] in s

    def test_unknown_language_falls_back_to_english(self):
        s = build_adhoc_summary(SESSION_STUB, {"language": "de"})
        assert s.startswith("I built you a session")

    def test_italian_multi_session_hint(self):
        s = build_adhoc_summary(
            SESSION_STUB,
            {"language": "it", "multi_session_requested": True, "deferred_session_hint": "stasera a casa: core"},
        )
        assert "stasera a casa: core" in s
        assert "una alla volta" in s


# ── 4. honesty note for empty coarse-focus pools (B305 follow-up) ────────


class TestEmptyFocusHonesty:
    def test_technique_at_home_says_so(self):
        intent = {"equipment_set": "home", "focus": "technique", "minutes": 45}
        state = {
            "equipment": {"home": ["pullup_bar"], "gyms": []},
            "macrocycle": {"start_date": "2026-07-06", "phases": [{"phase_id": "base", "duration_weeks": 3}]},
            "recent_sessions": [],
        }
        session = compose_adhoc_session(intent, state, _catalog())
        assert "No equipment-compatible technique exercises" in session["explanation"]

    def test_populated_focus_has_no_note(self):
        intent = {"equipment_set": "home", "focus": "pull", "minutes": 45}
        session = compose_adhoc_session(intent, _state(), _catalog())
        assert "lighter than asked" not in session["explanation"]
