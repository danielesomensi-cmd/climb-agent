"""A253 — genuine (max-derived) load anchors for adhoc sessions (D258 Phase 2).

Scoped, per the approved analysis, to fingers/hangboard + weighted-pull — the
only buckets where progression_v1 has a real max/grade anchor worth surfacing.
The crude planned fallbacks (PCT_BW 0.15, FIXED_KG) are deliberately NOT
surfaced: a plain barbell/dumbbell accessory the user never logged (Back Squat)
stays empty (B298), never gets a misleading ~12 kg.

Invariants under test:
  1. anchorable exercise (weighted_pullup / barbell_row / hangboard) pre-fills a
     plausible load with NO prior log, from a real TEST baseline;
  2. non-anchorable exercise (back_squat, bench_press w/o donor) stays 0;
  3. a grade-ESTIMATED baseline (source != test) does NOT anchor;
  4. remembered working_loads always wins over the anchor;
  5. anchoring is READ-ONLY — no mutation of user_state / baselines / working_loads;
  6. a negative (counterweight) anchor stays empty, not surfaced.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from backend.engine.adhoc_builder import compose_adhoc_session
from backend.engine.adhoc_prescription import anchor_adhoc_load

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


def _catalog() -> dict:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("exercises") or list(raw.values()))
    return {ex["id"]: ex for ex in items if isinstance(ex, dict) and ex.get("id")}


CAT = _catalog()


def _state(**overrides) -> dict:
    st = {
        "bodyweight_kg": 70,
        "equipment": {
            "home": ["pullup_bar", "weight", "hangboard", "rings"],
            "gyms": [{"gym_id": "g1", "equipment": ["weight", "pullup_bar", "cable_machine", "bench", "hangboard"]}],
        },
        "macrocycle": {"start_date": "2026-07-06", "phases": [{"phase_id": "strength_power", "duration_weeks": 3}]},
        "recent_sessions": [],
        "baselines": {
            "pulling": {"source": "test", "weighted_pullup_1rm_total_kg": 110.0, "max_external_load_kg": 30.0},
            "hangboard": [{"source": "test", "max_total_load_kg": 95.0}],
        },
    }
    st.update(overrides)
    return st


# ── Unit: the pure anchor function ───────────────────────────────────────


class TestAnchorFunction:
    def test_barbell_row_anchors_from_pulling_max(self):
        # 30 kg max-external × 0.60 scaling = 18 kg.
        assert anchor_adhoc_load(CAT["barbell_row"], _state(), "strength_power") == 18.0

    def test_weighted_pullup_anchors_from_pulling_1rm(self):
        v = anchor_adhoc_load(CAT["weighted_pullup"], _state(), "strength_power")
        assert v is not None and v > 0  # 110 × pct − 70 bw, positive for a strong puller

    def test_hangboard_anchors_from_test_baseline(self):
        v = anchor_adhoc_load(CAT["density_hangs"], _state(), "strength_power")
        assert v is not None and v > 0

    def test_back_squat_is_not_anchored(self):
        assert anchor_adhoc_load(CAT["back_squat"], _state(), "strength_power") is None

    def test_bench_press_without_donor_is_not_anchored(self):
        assert anchor_adhoc_load(CAT["bench_press"], _state(), "strength_power") is None

    def test_estimated_baseline_does_not_anchor(self):
        st = _state()
        st["baselines"]["pulling"]["source"] = "estimated_from_assessment"
        st["baselines"]["hangboard"][0]["source"] = "estimated_from_assessment"
        assert anchor_adhoc_load(CAT["barbell_row"], st, "strength_power") is None
        assert anchor_adhoc_load(CAT["density_hangs"], st, "strength_power") is None

    def test_no_baseline_does_not_anchor(self):
        st = _state(baselines={})
        assert anchor_adhoc_load(CAT["barbell_row"], st, "strength_power") is None
        assert anchor_adhoc_load(CAT["weighted_pullup"], st, "strength_power") is None
        assert anchor_adhoc_load(CAT["density_hangs"], st, "strength_power") is None

    def test_counterweight_negative_anchor_stays_empty(self):
        # Low max-hang vs bodyweight → submaximal external is negative → None.
        st = _state()
        st["baselines"]["hangboard"][0]["max_total_load_kg"] = 60.0  # < 70 bw
        assert anchor_adhoc_load(CAT["long_duration_hang"], st, "strength_power") is None


# ── Integration: it flows into the composed session's load_kg ────────────


class TestComposedSession:
    def test_barbell_row_prefilled_in_pull_session(self):
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength", "body_parts": ["back_pulling"],
             "minutes": 60, "energy": "medium"},
            _state(), CAT, today="2026-07-20",
        )
        row = next((e for e in s["exercises"] if e["exercise_id"] == "barbell_row"), None)
        assert row is not None and row["load_kg"] == 18.0

    def test_back_squat_stays_empty_in_general_session(self):
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength", "minutes": 60, "energy": "medium"},
            _state(), CAT, today="2026-07-20",
        )
        for e in s["exercises"]:
            if e["exercise_id"] == "back_squat":
                assert e["load_kg"] == 0

    def test_memory_wins_over_anchor(self):
        st = _state()
        st["working_loads"] = {"entries": [{
            "exercise_id": "barbell_row", "key": "barbell_row",
            "last_external_load_kg": 45.0, "next_external_load_kg": 45.0,
            "updated_at": "2026-07-19",
        }]}
        s = compose_adhoc_session(
            {"equipment_set": "gym", "focus": "general_strength", "body_parts": ["back_pulling"],
             "minutes": 60, "energy": "medium"},
            st, CAT, today="2026-07-20",
        )
        row = next((e for e in s["exercises"] if e["exercise_id"] == "barbell_row"), None)
        assert row is not None and row["load_kg"] == 45.0  # remembered, not the 18 anchor


# ── Immutability / no side effects ───────────────────────────────────────


def test_anchoring_does_not_mutate_state():
    st = _state()
    before = deepcopy(st)
    compose_adhoc_session(
        {"equipment_set": "home", "focus": "fingers", "minutes": 60, "energy": "medium"},
        st, CAT, today="2026-07-20",
    )
    compose_adhoc_session(
        {"equipment_set": "gym", "focus": "general_strength", "body_parts": ["back_pulling"],
         "minutes": 60, "energy": "medium"},
        st, CAT, today="2026-07-20",
    )
    # No baselines fabricated, no working_loads written, nothing touched.
    assert st == before
    assert "working_loads" not in st
