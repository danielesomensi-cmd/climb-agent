"""B281 — Adhoc field-test fixes (follow-up to A243, from Daniele's live run).

Field findings:
  1. Coach text path denied being able to create sessions and apologised for a
     valid card ("Il messaggio precedente è stato un errore") — stale A237
     instruction block.
  2. "Riprovi a creare l'allenamento custom?" composed home/general_strength/45
     defaults because the intent extractor saw only the last message — the
     place/focus/minutes lived in earlier turns.
  3. Composed session was alphabetical soup: 5 pull-up variants, 8-minute
     unskippable mobility warmup, 9 exercises.
  4. Custom player had no way to skip a running timed exercise (frontend —
     covered by manual/preview testing, not here).
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.coach import prompt_builder
from backend.coach.adhoc_intent import CONTEXT_MESSAGES, build_extraction_content
from backend.engine.adhoc_builder import (
    MAX_EXERCISES,
    MAX_PER_PATTERN,
    MAX_WARMUP_WORK_SECONDS,
    compose_adhoc_session,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


def _catalog() -> dict:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("exercises") or list(raw.values()))
    return {ex["id"]: ex for ex in items if isinstance(ex, dict) and ex.get("id")}


def _state() -> dict:
    return {
        "equipment": {
            "home": ["pullup_bar", "weight", "hangboard", "resistance_band", "dumbbell"],
            "gyms": [{"gym_id": "g1", "equipment": ["weight", "pullup_bar", "bench", "cable_machine"]}],
        },
        "macrocycle": {
            "start_date": "2026-07-06",
            "phases": [{"phase_id": "performance", "duration_weeks": 3}],
        },
        "recent_sessions": [],
    }


def _pattern_of(catalog: dict, eid: str) -> str:
    p = catalog[eid].get("pattern")
    if isinstance(p, list):
        p = p[0] if p else None
    return str(p or catalog[eid].get("recency_group") or eid)


# ── Finding 3: composition quality ──────────────────────────────────────


class TestCompositionQuality:
    def test_pattern_diversity_cap(self):
        """No more than MAX_PER_PATTERN main picks per movement pattern (the
        field session had 5 pull_vertical variants)."""
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "home", "focus": "general_strength", "minutes": 60, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        mains = [e["exercise_id"] for e in s["exercises"]]
        # count patterns over the non-warmup portion (warmup is 1st pick)
        counts: dict = {}
        for eid in mains:
            if "warmup" in (cat[eid].get("role") or []):
                continue
            pat = _pattern_of(cat, eid)
            counts[pat] = counts.get(pat, 0) + 1
        offenders = {p: c for p, c in counts.items() if c > MAX_PER_PATTERN}
        assert not offenders, f"pattern over-representation: {offenders}"

    def test_exercise_count_cap(self):
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength", "minutes": 120, "energy": "high"},
            st, cat, today="2026-07-20",
        )
        assert len(s["exercises"]) <= MAX_EXERCISES

    def test_warmup_is_short(self):
        """The opener must never be a long timed block (field case: 480s
        mobility flow with no skip)."""
        cat, st = _catalog(), _state()
        for focus in ("general_strength", "core", "pull", "fingers"):
            s = compose_adhoc_session(
                {"equipment_set": "home", "focus": focus, "minutes": 45, "energy": "medium"},
                st, cat, today="2026-07-20",
            )
            first = s["exercises"][0]
            work = first.get("work_seconds") or 0
            assert work <= MAX_WARMUP_WORK_SECONDS, (
                f"{focus}: opener {first['exercise_id']} has work_seconds={work}"
            )

    def test_main_block_ordered_strength_first(self):
        """main_strength category exercises come before accessories (no more
        alphabetical soup)."""
        cat, st = _catalog(), _state()
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "pull", "minutes": 60, "energy": "medium"},
            st, cat, today="2026-07-20",
        )
        cats = [
            cat[e["exercise_id"]].get("category")
            for e in s["exercises"]
            if "warmup" not in (cat[e["exercise_id"]].get("role") or [])
            and cat[e["exercise_id"]].get("category") != "core"  # finisher at the end
        ]
        if "main_strength" in cats and "strength_accessory" in cats:
            assert cats.index("main_strength") < cats.index("strength_accessory")

    def test_energy_does_not_inflate_warmup(self):
        cat, st = _catalog(), _state()
        med = compose_adhoc_session({"equipment_set": "home", "focus": "core", "minutes": 45, "energy": "medium"}, st, cat, today="2026-07-20")
        high = compose_adhoc_session({"equipment_set": "home", "focus": "core", "minutes": 45, "energy": "high"}, st, cat, today="2026-07-20")
        # If both sessions open with the same warmup, its sets must not grow.
        if med["exercises"] and high["exercises"] and med["exercises"][0]["exercise_id"] == high["exercises"][0]["exercise_id"]:
            assert high["exercises"][0]["sets"] <= med["exercises"][0]["sets"]

    def test_determinism_still_holds(self):
        cat, st = _catalog(), _state()
        intent = {"equipment_set": "gym", "focus": "endurance", "minutes": 50, "energy": "medium"}
        a = compose_adhoc_session(intent, st, cat, today="2026-07-20")
        b = compose_adhoc_session(intent, st, cat, today="2026-07-20")
        assert [e["exercise_id"] for e in a["exercises"]] == [e["exercise_id"] for e in b["exercises"]]


# ── Finding 2: extraction context ───────────────────────────────────────


class TestExtractionContext:
    def test_history_included_and_capped(self):
        history = [
            {"role": "user", "content": f"msg {i}"} for i in range(10)
        ]
        content = build_extraction_content("riprovi a crearla?", history)
        assert "Latest message (classify THIS): riprovi a crearla?" in content
        # only the last CONTEXT_MESSAGES make it in
        assert f"msg {10 - CONTEXT_MESSAGES}" in content
        assert f"msg {10 - CONTEXT_MESSAGES - 1}" not in content

    def test_no_history_passthrough(self):
        assert build_extraction_content("build me a session", None) == "build me a session"
        assert build_extraction_content("build me a session", []) == "build me a session"

    def test_context_carries_earlier_specs(self):
        """The field failure: specs lived two turns earlier."""
        history = [
            {"role": "user", "content": "mi crei una sessione di addominali e tecnica al Bkl di 80 minuti?"},
            {"role": "assistant", "content": "Ecco una sessione tecnica + core: ..."},
        ]
        content = build_extraction_content("Riprovi a creare l'allenamento custom?", history)
        assert "Bkl" in content and "80 minuti" in content


# ── Finding 1: instruction block card-awareness ─────────────────────────


class TestInstructionBlock:
    def test_block_teaches_the_card_flow_and_never_denies(self):
        prompt_builder.build_static_block.cache_clear()
        block = prompt_builder.build_static_block()
        assert "Add to today & run" in block
        assert "NEVER say" in block or "never say" in block.lower()
        assert "never call it an error" in block.lower()
        # legacy guarantees still present (A237 assertions rely on these too)
        assert "RPE/RIR only" in block
        assert "NEVER absolute kilograms" in block
        assert "Session Builder" in block


# ── B283: catalog display enrichment for the real guided player ─────────


class TestCustomSessionEnrichment:
    def test_build_session_enriches_display_fields(self):
        from backend.api.models import CustomSessionExerciseEntry
        from backend.api.routers.custom_session import _build_session, _load_exercises_catalog

        catalog = _load_exercises_catalog()
        entry = CustomSessionExerciseEntry(
            exercise_id="bench_press", sets=3, reps=5,
            rest_between_sets_seconds=120, load_kg=40,
        )
        s = _build_session("cs_x", "Test", [], [entry], catalog, "2026-07-20T00:00:00Z")
        ex = s["exercises"][0]
        assert ex["name"] == "Bench Press"
        assert ex["cues"], "catalog cues missing"
        assert ex["load_model"] == "external_load"
        assert ex.get("video_url")
        # catalog technique notes fill empty user notes
        assert isinstance(ex.get("notes"), (str, type(None)))

    def test_user_notes_win_over_catalog_notes(self):
        from backend.api.models import CustomSessionExerciseEntry
        from backend.api.routers.custom_session import _build_session, _load_exercises_catalog

        catalog = _load_exercises_catalog()
        entry = CustomSessionExerciseEntry(
            exercise_id="elbow_wrist_extensor_eccentric", sets=3, reps=12, notes="my note",
        )
        s = _build_session("cs_y", "Test", [], [entry], catalog, "2026-07-20T00:00:00Z")
        assert s["exercises"][0]["notes"] == "my note"

    def test_read_path_backfills_legacy_sessions(self):
        from backend.api.routers.custom_session import enrich_custom_sessions_for_play

        legacy = [{
            "id": "cs_old", "name": "Old", "exercises": [
                {"exercise_id": "frenchies", "sets": 3, "reps": 5, "load_kg": 0, "notes": ""},
            ],
        }]
        out = enrich_custom_sessions_for_play(legacy)
        ex = out[0]["exercises"][0]
        assert ex.get("name") and ex["name"] != "frenchies"
        assert "cues" in ex
        # original objects untouched (read-path only)
        assert "cues" not in legacy[0]["exercises"][0]
