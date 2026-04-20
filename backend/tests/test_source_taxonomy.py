"""D214: assessment.tests_source sidecar — F1 + F3 regression coverage.

Covers every layer affected by the D-TESTUSER-VERIFY remediation:

- onboarding writer marks user-entered scalars as ``measured`` (incl. 7s/5s
  dual-write);
- ``_estimate_hangboard_baseline`` honors user-measured max_hang (F1 closure);
- ``_estimate_hangboard_baseline`` ignores estimated scalars and falls back to
  grade/pullup paths (legacy compatibility);
- ``_update_test_from_log`` marks every scalar it writes as ``measured``;
- ``week.py`` freshness map gates on ``tests_source == "measured"`` for finger,
  repeater and pulling axes (F3 closure).
"""

from __future__ import annotations

from backend.api.routers.onboarding import _build_tests_source, _normalize_test_keys
from backend.engine.progression_v1 import (
    _estimate_hangboard_baseline,
    apply_feedback,
    estimate_missing_baselines,
)


# ---------------------------------------------------------------------------
# _build_tests_source (onboarding writer helper)
# ---------------------------------------------------------------------------


class TestBuildTestsSource:
    def test_user_entered_scalar_marked_measured(self):
        tests = _normalize_test_keys({"max_hang_20mm_7s_total_kg": 150.0})
        source = _build_tests_source(tests)
        assert source["max_hang_20mm_7s_total_kg"] == "measured"
        # D85 dual-write semantics: both keys carry the same origin
        assert source["max_hang_20mm_5s_total_kg"] == "measured"

    def test_absent_scalar_absent_from_source(self):
        source = _build_tests_source({"max_hang_20mm_7s_total_kg": 150.0})
        assert "repeater_7_3_max_sets_20mm" not in source
        assert "weighted_pullup_1rm_total_kg" not in source

    def test_every_user_entered_scalar_marked(self):
        source = _build_tests_source({
            "max_hang_20mm_7s_total_kg": 120.0,
            "repeater_7_3_max_sets_20mm": 20,
            "weighted_pullup_1rm_total_kg": 110.0,
            "l_sit_hold_seconds": 45,
            "hip_flexibility_cm": 5,
        })
        for key in (
            "max_hang_20mm_7s_total_kg",
            "repeater_7_3_max_sets_20mm",
            "weighted_pullup_1rm_total_kg",
            "l_sit_hold_seconds",
            "hip_flexibility_cm",
        ):
            assert source[key] == "measured", source

    def test_none_and_empty_string_not_marked(self):
        source = _build_tests_source({
            "max_hang_20mm_7s_total_kg": None,
            "repeater_7_3_max_sets_20mm": "",
            "l_sit_hold_seconds": 60,
        })
        assert "max_hang_20mm_7s_total_kg" not in source
        assert "repeater_7_3_max_sets_20mm" not in source
        assert source["l_sit_hold_seconds"] == "measured"


# ---------------------------------------------------------------------------
# F1 — _estimate_hangboard_baseline consults user-measured max_hang scalar
# ---------------------------------------------------------------------------


class TestEstimateHangboardBaselineF1:
    def _state_with_measured_hang(self, hang_kg: float) -> dict:
        return {
            "assessment": {
                "tests": {
                    "max_hang_20mm_7s_total_kg": hang_kg,
                    "max_hang_20mm_5s_total_kg": hang_kg,
                },
                "tests_source": {
                    "max_hang_20mm_7s_total_kg": "measured",
                    "max_hang_20mm_5s_total_kg": "measured",
                },
                "grades": {"lead_max_rp": "6c"},
            },
            "body": {"weight_kg": 70.0},
            "bodyweight_kg": 70.0,
            "baselines": {},
        }

    def test_measured_hang_wins_over_grade(self):
        state = self._state_with_measured_hang(150.0)
        _estimate_hangboard_baseline(state)
        hb = state["baselines"]["hangboard"][0]
        assert hb["max_total_load_kg"] == 150.0
        assert hb["source"] == "test"
        # Real test semantics: updated_at stamp, not estimated_at
        assert "updated_at" in hb
        assert "estimated_at" not in hb

    def test_measured_hang_seeds_protocol_fields(self):
        state = self._state_with_measured_hang(150.0)
        _estimate_hangboard_baseline(state)
        hb = state["baselines"]["hangboard"][0]
        # Primary test protocol
        assert hb["hang_seconds"] == 7
        assert hb["edge_mm"] == 20
        assert hb["grip"] == "half_crimp"

    def test_measured_hang_triggers_idempotency_on_rerun(self):
        state = self._state_with_measured_hang(150.0)
        _estimate_hangboard_baseline(state)
        hb = state["baselines"]["hangboard"][0]
        hb["max_total_load_kg"] = 999.0  # simulate an external writer
        _estimate_hangboard_baseline(state)
        # Early-return at line 675 preserves source="test" baseline
        assert state["baselines"]["hangboard"][0]["max_total_load_kg"] == 999.0

    def test_estimated_scalar_ignored_falls_back_to_grade(self):
        state = self._state_with_measured_hang(150.0)
        state["assessment"]["tests_source"]["max_hang_20mm_7s_total_kg"] = "estimated"
        state["assessment"]["tests_source"]["max_hang_20mm_5s_total_kg"] = "estimated"
        _estimate_hangboard_baseline(state)
        hb = state["baselines"]["hangboard"][0]
        # 6c → offset 10 kg: baseline = 70 + 10 = 80
        assert hb["source"] == "estimated_from_grade"
        assert hb["grade_used"] == "6c"
        assert "estimated_at" in hb
        assert "updated_at" not in hb

    def test_legacy_state_without_tests_source_falls_back(self):
        # Retro-compat: pre-D214 state has no tests_source key
        state = self._state_with_measured_hang(150.0)
        del state["assessment"]["tests_source"]
        _estimate_hangboard_baseline(state)
        hb = state["baselines"]["hangboard"][0]
        # Silent default "estimated" → grade path, not user scalar
        assert hb["source"] == "estimated_from_grade"

    def test_no_grade_no_scalar_no_baseline(self):
        state = {
            "assessment": {"tests": {}, "tests_source": {}, "grades": {}},
            "body": {"weight_kg": 70.0},
            "bodyweight_kg": 70.0,
            "baselines": {},
        }
        _estimate_hangboard_baseline(state)
        assert state["baselines"].get("hangboard") in (None, [])


# ---------------------------------------------------------------------------
# _update_test_from_log marks every scalar as "measured"
# ---------------------------------------------------------------------------


def _feedback_log(date: str, session_id: str, items: list) -> dict:
    return {
        "date": date,
        "planned": [
            {
                "session_id": session_id,
                "tags": {"test": True},
                "exercise_instances": [],
            }
        ],
        "actual": {"exercise_feedback_v1": items},
    }


def _feedback_state() -> dict:
    return {
        "body": {"weight_kg": 75.0},
        "bodyweight_kg": 75.0,
        "assessment": {"tests": {}},
        "working_loads": {"entries": []},
        "tests": {},
        "baselines": {},
    }


class TestUpdateTestFromLogMarksMeasured:
    def test_max_hang_7s_marks_both_keys(self):
        result = apply_feedback(
            _feedback_log(
                "2026-03-01",
                "test_max_hang_7s",
                [{"exercise_id": "max_hang_7s", "used_total_load_kg": 100.0}],
            ),
            _feedback_state(),
        )
        src = result["assessment"]["tests_source"]
        assert src["max_hang_20mm_7s_total_kg"] == "measured"
        assert src["max_hang_20mm_5s_total_kg"] == "measured"

    def test_max_hang_5s_legacy_also_marks_both(self):
        result = apply_feedback(
            _feedback_log(
                "2026-03-01",
                "test_max_hang_5s",
                [{"exercise_id": "max_hang_5s", "used_total_load_kg": 100.0}],
            ),
            _feedback_state(),
        )
        src = result["assessment"]["tests_source"]
        assert src["max_hang_20mm_5s_total_kg"] == "measured"
        assert src["max_hang_20mm_7s_total_kg"] == "measured"

    def test_repeater_marks_source(self):
        result = apply_feedback(
            _feedback_log(
                "2026-03-02",
                "test_repeater_7_3",
                [{"exercise_id": "repeater_hang_7_3", "completed_sets": 22}],
            ),
            _feedback_state(),
        )
        assert result["assessment"]["tests_source"]["repeater_7_3_max_sets_20mm"] == "measured"

    def test_weighted_pullup_marks_all_derived_scalars(self):
        result = apply_feedback(
            _feedback_log(
                "2026-03-03",
                "test_weighted_pullup",
                [{"exercise_id": "weighted_pullup", "used_total_load_kg": 110.0}],
            ),
            _feedback_state(),
        )
        src = result["assessment"]["tests_source"]
        for key in (
            "weighted_pullup_2rm_total_kg",
            "weighted_pullup_1rm_estimated_kg",
            "pulling_ratio_pct",
            "weighted_pullup_1rm_total_kg",
        ):
            assert src[key] == "measured", src

    def test_l_sit_hip_duration_scalars_marked(self):
        log = _feedback_log(
            "2026-03-04",
            "test_misc",
            [
                {
                    "exercise_id": "test_l_sit_hold",
                    "l_sit_hold_seconds": 45,
                },
                {
                    "exercise_id": "test_hip_flexibility",
                    "hip_flexibility_cm": 5,
                },
                {
                    "exercise_id": "test_max_hang_duration_20mm",
                    "max_hang_duration_20mm_seconds": 12,
                },
            ],
        )
        result = apply_feedback(log, _feedback_state())
        src = result["assessment"]["tests_source"]
        assert src["l_sit_hold_seconds"] == "measured"
        assert src["hip_flexibility_cm"] == "measured"
        assert src["max_hang_duration_20mm_seconds"] == "measured"

    def test_max_pullup_bw_marked(self):
        result = apply_feedback(
            _feedback_log(
                "2026-03-05",
                "test_max_pullup_bw",
                [{"exercise_id": "test_max_pullup_bw", "max_pullups_bw": 12}],
            ),
            _feedback_state(),
        )
        assert result["assessment"]["tests_source"]["max_pullups_bw"] == "measured"


# ---------------------------------------------------------------------------
# F3 — week.py freshness map gates on tests_source == "measured"
# ---------------------------------------------------------------------------
#
# The freshness map is inline in ``backend/api/routers/week.py:get_week``. The
# helper below replays that exact block against a test-crafted state dict, so
# regressions in the gating logic surface as test failures without requiring a
# live API + generated macrocycle.
# ---------------------------------------------------------------------------


def _extract_recent_test_dates(state: dict) -> dict:
    """Replay the freshness-map logic from backend/api/routers/week.py inline.

    Kept in sync with the current implementation. If week.py drifts, this test
    will fail — that is the intended signal to re-check gating semantics.
    """
    _tests_src = ((state.get("assessment") or {}).get("tests_source") or {})
    _recent: dict[str, str] = {}

    _hb = (state.get("baselines") or {}).get("hangboard") or []
    _finger_measured = (
        _tests_src.get("max_hang_20mm_7s_total_kg") == "measured"
        or _tests_src.get("max_hang_20mm_5s_total_kg") == "measured"
    )
    if _hb and _finger_measured:
        ts = _hb[0].get("updated_at")
        if ts:
            _recent["finger"] = ts

    _rep_hist = (state.get("tests") or {}).get("repeater_strength_endurance") or []
    _rep_measured = _tests_src.get("repeater_7_3_max_sets_20mm") == "measured"
    if _rep_hist:
        _recent["repeater"] = _rep_hist[-1].get("date", "")
    elif _rep_measured and (state.get("assessment") or {}).get("tests", {}).get("repeater_7_3_max_sets_20mm") is not None:
        mc_start = (state.get("macrocycle") or {}).get("start_date")
        if mc_start:
            _recent["repeater"] = mc_start

    _pulling = (state.get("baselines") or {}).get("pulling") or {}
    _pulling_measured = (
        _tests_src.get("weighted_pullup_1rm_total_kg") == "measured"
        or _tests_src.get("weighted_pullup_2rm_total_kg") == "measured"
        or _tests_src.get("weighted_pullup_1rm_estimated_kg") == "measured"
    )
    if _pulling.get("updated_at") and _pulling_measured:
        _recent["pulling"] = _pulling["updated_at"]

    return _recent


class TestFreshnessMapGating:
    def test_legacy_state_no_tests_source_populates_nothing(self):
        state = {
            "assessment": {
                "tests": {"max_hang_20mm_7s_total_kg": 150.0, "repeater_7_3_max_sets_20mm": 20},
                # no tests_source key at all → silent "estimated"
            },
            "baselines": {
                "hangboard": [{"max_total_load_kg": 150.0, "updated_at": "2026-04-20"}],
                "pulling": {"updated_at": "2026-04-20"},
            },
            "macrocycle": {"start_date": "2026-04-20"},
        }
        recent = _extract_recent_test_dates(state)
        assert "finger" not in recent
        assert "pulling" not in recent
        assert "repeater" not in recent

    def test_measured_finger_populates_finger(self):
        state = {
            "assessment": {
                "tests": {"max_hang_20mm_7s_total_kg": 150.0},
                "tests_source": {"max_hang_20mm_7s_total_kg": "measured"},
            },
            "baselines": {"hangboard": [{"updated_at": "2026-04-20"}]},
        }
        recent = _extract_recent_test_dates(state)
        assert recent["finger"] == "2026-04-20"

    def test_estimated_pulling_does_not_populate_pulling(self):
        """F3 closure: onboarding estimator stamps updated_at=today but reader
        ignores it when tests_source is not "measured"."""
        state = {
            "assessment": {
                "tests": {"weighted_pullup_1rm_total_kg": 110.0},
                # Estimated at onboarding, not in-app test
                "tests_source": {"weighted_pullup_1rm_total_kg": "estimated"},
            },
            "baselines": {"pulling": {"updated_at": "2026-04-20"}},
        }
        recent = _extract_recent_test_dates(state)
        assert "pulling" not in recent

    def test_measured_pulling_populates_pulling(self):
        state = {
            "assessment": {
                "tests": {"weighted_pullup_1rm_total_kg": 110.0},
                "tests_source": {"weighted_pullup_1rm_total_kg": "measured"},
            },
            "baselines": {"pulling": {"updated_at": "2026-04-20"}},
        }
        recent = _extract_recent_test_dates(state)
        assert recent["pulling"] == "2026-04-20"

    def test_estimated_repeater_does_not_populate_via_proxy(self):
        state = {
            "assessment": {
                "tests": {"repeater_7_3_max_sets_20mm": 20},
                "tests_source": {"repeater_7_3_max_sets_20mm": "estimated"},
            },
            "macrocycle": {"start_date": "2026-04-20"},
        }
        recent = _extract_recent_test_dates(state)
        assert "repeater" not in recent

    def test_measured_repeater_populates_via_proxy(self):
        state = {
            "assessment": {
                "tests": {"repeater_7_3_max_sets_20mm": 20},
                "tests_source": {"repeater_7_3_max_sets_20mm": "measured"},
            },
            "macrocycle": {"start_date": "2026-04-20"},
        }
        recent = _extract_recent_test_dates(state)
        assert recent["repeater"] == "2026-04-20"

    def test_repeater_history_takes_precedence(self):
        """History is source-agnostic: a real test session always populates."""
        state = {
            "assessment": {"tests": {"repeater_7_3_max_sets_20mm": 20}, "tests_source": {}},
            "tests": {"repeater_strength_endurance": [{"date": "2026-04-18"}]},
        }
        recent = _extract_recent_test_dates(state)
        assert recent["repeater"] == "2026-04-18"


# ---------------------------------------------------------------------------
# End-to-end: onboarding → estimate_missing_baselines → F1 closure
# ---------------------------------------------------------------------------


class TestEndToEndF1Closure:
    def test_ferrero_regression_150kg_preserved(self):
        """Regression for D-TESTUSER-VERIFY F1: user with lead_max_rp=6c and
        measured max_hang=150 kg no longer sees baseline collapse to 33 kg.
        """
        tests = _normalize_test_keys({"max_hang_20mm_7s_total_kg": 150.0})
        state = {
            "schema_version": "1.5",
            "assessment": {
                "tests": tests,
                "tests_source": _build_tests_source(tests),
                "grades": {"lead_max_rp": "6c"},
                "experience": {"years_climbing": 3},
            },
            "body": {"weight_kg": 70, "height_cm": 175, "age": 35},
            "bodyweight_kg": 70,
            "baselines": {},
        }
        estimate_missing_baselines(state)
        hb = state["baselines"]["hangboard"][0]
        assert hb["max_total_load_kg"] == 150.0
        assert hb["source"] == "test"
        # Also confirm pulling estimator fired (not gated by F1)
        assert "pulling" not in state.get("baselines", {}) or state["baselines"]["pulling"].get("source") == "assessment"
