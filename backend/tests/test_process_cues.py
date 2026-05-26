"""Tests for process cues (A141)."""

import json
import os

import pytest

from backend.engine.cues import get_session_cue, _load_cues

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUES_PATH = os.path.join(REPO_ROOT, "backend", "catalog", "cues", "v1", "process_cues.json")
SESSIONS_DIR = os.path.join(REPO_ROOT, "backend", "catalog", "sessions", "v1")


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the lru_cache between tests."""
    _load_cues.cache_clear()
    yield
    _load_cues.cache_clear()


def _load_cues_raw() -> list[dict]:
    with open(CUES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _session_template_ids() -> set[str]:
    """Get all session template IDs from the catalog."""
    ids = set()
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".json"):
            ids.add(fname.removesuffix(".json"))
    return ids


class TestProcessCuesDeterminism:
    """Same inputs → same cue, every time."""

    def test_same_inputs_same_cue(self):
        cue1 = get_session_cue("finger_strength_home", "2025-03-15", "user_abc", REPO_ROOT)
        cue2 = get_session_cue("finger_strength_home", "2025-03-15", "user_abc", REPO_ROOT)
        assert cue1 is not None
        assert cue1 == cue2

    def test_different_date_may_differ(self):
        cue1 = get_session_cue("boulder_circuit_gym", "2025-03-15", "user_abc", REPO_ROOT)
        cue2 = get_session_cue("boulder_circuit_gym", "2025-03-16", "user_abc", REPO_ROOT)
        assert cue1 is not None
        assert cue2 is not None
        # They can be the same by chance, but the mechanism uses different seeds

    def test_different_user_may_differ(self):
        cue1 = get_session_cue("boulder_circuit_gym", "2025-03-15", "user_a", REPO_ROOT)
        cue2 = get_session_cue("boulder_circuit_gym", "2025-03-15", "user_b", REPO_ROOT)
        assert cue1 is not None
        assert cue2 is not None


class TestProcessCuesSessionFilter:
    """Cues only match their declared session types."""

    def test_hangboard_cue_not_for_bouldering(self):
        """Cue about shoulder engagement (finger sessions) should not appear for boulder_circuit_gym."""
        cues = _load_cues_raw()
        hangboard_only_cues = {
            c["id"]
            for c in cues
            if all(
                st in ("finger_strength_home", "strength_long", "finger_maintenance_gym",
                        "finger_maintenance_home", "finger_aerobic_base", "finger_endurance_short")
                for st in c["session_types"]
            )
        }
        # Run many dates and verify no hangboard-only cue appears for bouldering
        for day in range(1, 100):
            cue = get_session_cue(
                "boulder_circuit_gym", f"2025-04-{day:02d}", "test_user", REPO_ROOT,
            )
            if cue:
                assert cue["id"] not in hangboard_only_cues, (
                    f"Hangboard-only cue {cue['id']} appeared for boulder_circuit_gym"
                )

    def test_no_cue_for_nonexistent_session(self):
        cue = get_session_cue("nonexistent_session_xyz", "2025-03-15", "user", REPO_ROOT)
        assert cue is None


class TestProcessCuesCatalogValid:
    """All cues have required fields and valid structure."""

    def test_all_cues_have_required_fields(self):
        cues = _load_cues_raw()
        assert len(cues) > 0
        for cue in cues:
            assert "id" in cue, f"Missing id in cue"
            assert "text" in cue, f"Missing text in cue {cue.get('id')}"
            assert "session_types" in cue, f"Missing session_types in cue {cue.get('id')}"
            assert isinstance(cue["session_types"], list), f"session_types not a list in {cue['id']}"
            assert len(cue["session_types"]) > 0, f"Empty session_types in {cue['id']}"
            assert len(cue["text"]) > 0, f"Empty text in {cue['id']}"

    def test_unique_ids(self):
        cues = _load_cues_raw()
        ids = [c["id"] for c in cues]
        assert len(ids) == len(set(ids)), "Duplicate cue IDs found"

    def test_session_types_reference_real_sessions(self):
        """Every session_type must reference an existing session template.

        Pseudo-tokens starting with '_' (e.g. '_any_last_session_before_rest')
        are control flags, not real session ids, so they're exempt.
        """
        cues = _load_cues_raw()
        template_ids = _session_template_ids()
        unknown: list[str] = []
        for cue in cues:
            for st in cue["session_types"]:
                if st.startswith("_"):
                    continue
                if st not in template_ids:
                    unknown.append(f"{cue['id']}:{st}")
        assert unknown == [], f"Cues referencing nonexistent sessions: {unknown}"

    def test_text_length_sanity(self):
        cues = _load_cues_raw()
        for cue in cues:
            n = len(cue["text"])
            assert 20 < n < 400, f"Cue {cue['id']} text length {n} out of range (20, 400)"


class TestProcessCuesSessionCoverage:
    """Every active (non-test) session template should match at least 1 cue."""

    def test_active_sessions_have_cues(self):
        cues = _load_cues_raw()
        all_cue_session_types = set()
        for cue in cues:
            all_cue_session_types.update(cue["session_types"])

        template_ids = _session_template_ids()

        # Exclude test sessions, archive, and niche sessions that don't need coaching cues
        excluded_prefixes = ("test_", "_archive")
        # Sessions that are purely recovery/flexibility and may not need a specific cue
        optional_sessions = {
            "flexibility_full", "yoga_recovery", "prehab_maintenance",
            "handstand_practice",
        }

        missing = []
        for tid in sorted(template_ids):
            if any(tid.startswith(p) for p in excluded_prefixes):
                continue
            if tid in optional_sessions:
                continue
            if tid not in all_cue_session_types:
                missing.append(tid)

        assert missing == [], f"Sessions without any matching cue: {missing}"


class TestProcessCuesLastSessionBeforeRest:
    """The _any_last_session_before_rest tag works when next_day_is_rest=True."""

    def test_rest_cue_appears_when_next_day_rest(self):
        # cue_013 has _any_last_session_before_rest — should match any session when next is rest
        found_rest_cue = False
        for day in range(1, 200):
            cue = get_session_cue(
                "flexibility_full", f"2025-05-{day:02d}", "test_user", REPO_ROOT,
                next_day_is_rest=True,
            )
            if cue and cue["id"] == "cue_013":
                found_rest_cue = True
                break
        assert found_rest_cue, "cue_013 (rest day reminder) should appear when next_day_is_rest=True"
