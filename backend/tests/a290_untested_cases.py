"""A290 — untested athletes: inputs of the bit-for-bit resolver regression.

DECISIONS 2026-10-04: the anchor rules (phase anchors, A/B, heavy slot,
spacing, the tested-only recency / P0 fixes) apply ONLY to an athlete with a
tested baseline (``retest_policy.is_tested`` on the finger or the pulling
protocol). For everyone else the resolver output must stay exactly what it was
before A290.

The golden output in ``fixtures/a290_untested_golden.json`` was produced by
running ``compute()`` on origin/main @ 3fdfdd1 (the commit A290 starts from,
before any catalog or resolver change); the regression test re-runs it on the
current code — with and without the new ``week_plan`` kwarg — and compares.

Cases:
- ``no_tests_onboarding_baselines``: no ``tests.*``; baselines persisted by
  onboarding (``source='test'`` stamped by ``estimate_missing_baselines``).
  A self-report is not a test log → untested.
- ``stale_tests``: real tests, but older than 90 days on every resolved date.

Both carry a done history in the previous week (catalog session, custom
session with logged entries, a done test session) so that the tested-only
recency rules (custom sessions, test instances, no cap) would show up in the
output if the scope gate leaked.

Regenerating the golden: copy this file into a checkout of origin/main @
3fdfdd1 and dump ``json.dumps(compute(), sort_keys=True, indent=1)``.

A292 (R6-PE) re-anchored four lead PE exercises in the CATALOG (grade_ref
``lead_max_os`` → ``lead_pe_anchor`` plus their texts). The two
``power_endurance_gym`` digests were regenerated after checking that, with the
pre-A292 catalog and the A292 code, the whole golden still matched bit for bit:
the change is catalog data, not resolver behaviour (exercise_ids unchanged).

C272 added 73 library-only exercises (role ``ladder`` / ``library``). All 22
digests were regenerated after diffing the raw resolver output (with and
without ``week_plan``) against a clean export of origin/main @ 21aec98: the
only differences are the candidate counts in ``p0_trace`` / ``filter_trace``
(the catalog grew) — exercise_ids, prescriptions, loads and every note text
identical (the C272 review reverted the note rewrites on engine-selected
exercises). ``c272_golden_cases`` pins the same claim with traces and free text
stripped, so the next catalog addition does not need this dance there.

C273 rewrote catalog free text with Daniele's OK (notes of lock_off_isometric,
front_lever_tuck, bear_crawl, the core_standard block note, the cues of
hanging_leg_raise). The 16 digests that carry bear_crawl or the core_standard
note were regenerated after diffing the raw resolver output (both week_plan
modes) against origin/main @ 155f4f6 with the same text substitutions applied:
zero other differences, exercise_ids unchanged.

Pure data + one function, importable by the generator without pytest.
"""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_MACRO = {
    "start_date": "2026-09-07",
    "phases": [
        {"phase_id": "base", "duration_weeks": 2},
        {"phase_id": "strength_power", "duration_weeks": 4},
        {"phase_id": "power_endurance", "duration_weeks": 3},
        {"phase_id": "performance", "duration_weeks": 3},
        {"phase_id": "deload", "duration_weeks": 1},
    ],
}

_EQUIPMENT = {
    "home": ["hangboard", "pullup_bar", "dumbbell", "band", "resistance_band"],
    "home_enabled": True,
    "gyms": [
        {"gym_id": "g_board", "name": "Board gym", "priority": 1,
         "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard", "campus_board", "pullup_bar",
                       "gym_boulder", "dumbbell", "weight", "resistance_band", "ab_wheel"]},
    ],
}

# (date, session_id, location, gym_id, phase) — two weeks of strength_power +
# one of power_endurance; the week of 2026-09-28 holds the done history.
#
# Time stability: the resolver still reads ``date.today()`` in two places
# (B267 recency window, A121 phase when ``phase`` is None). The phase is
# passed explicitly, and ``week_plans`` holds ONLY the past history week, so
# the recency window is the same whatever day the suite runs. The future
# weeks are handed to the resolver through the ``week_plan`` kwarg only.
_SCHEDULE: List[Tuple[str, str, str, Any, str]] = [
    ("2026-10-05", "limit_boulder_gym", "gym", "g_board", "strength_power"),
    ("2026-10-06", "pulling_strength_gym", "gym", "g_board", "strength_power"),
    ("2026-10-07", "power_contact_gym", "gym", "g_board", "strength_power"),
    ("2026-10-09", "strength_long", "home", None, "strength_power"),
    ("2026-10-11", "finger_maintenance_home", "home", None, "strength_power"),
    ("2026-10-13", "finger_strength_home", "home", None, "strength_power"),
    ("2026-10-15", "limit_boulder_gym", "gym", "g_board", "strength_power"),
    ("2026-10-17", "boulder_circuit_gym", "gym", "g_board", "strength_power"),
    ("2026-10-20", "finger_strength_home", "home", None, "power_endurance"),
    ("2026-10-22", "power_endurance_gym", "gym", "g_board", "power_endurance"),
    ("2026-10-24", "strength_long", "home", None, "power_endurance"),
]


def _monday(d: str) -> str:
    from datetime import date as _date, timedelta as _td

    dd = _date.fromisoformat(d)
    return (dd - _td(days=dd.weekday())).isoformat()


def future_plans() -> Dict[str, Dict[str, Any]]:
    """The planned weeks of ``_SCHEDULE``, keyed by Monday (NOT in the state)."""
    weeks: Dict[str, List[Dict[str, Any]]] = {}
    for d, sid, loc, gid, _ph in _SCHEDULE:
        weeks.setdefault(_monday(d), []).append(
            {"date": d, "sessions": [{"session_id": sid, "location": loc, "gym_id": gid, "status": "planned"}]}
        )
    return {m: {"start_date": m, "weeks": [{"days": days}]} for m, days in weeks.items()}


def _history_week() -> Dict[str, Any]:
    return {
        "start_date": "2026-09-28",
        "weeks": [{"days": [
            {"date": "2026-09-29", "sessions": [{
                "session_id": "strength_long", "status": "done", "location": "home",
                "resolved": {"resolved_session": {"exercise_instances": [
                    {"exercise_id": "min_edge_hang", "source": {"template_id": "finger_max_strength"}},
                    {"exercise_id": "lock_off_isometric", "source": {"template_id": None}},
                    {"exercise_id": "front_lever_one_leg", "source": {"template_id": "core_standard"}},
                    {"exercise_id": "band_pull_apart", "source": {"template_id": "warmup_climbing"}},
                ]}},
            }]},
            {"date": "2026-09-30", "sessions": [{
                "session_id": "custom_cs_hist", "is_custom": True, "status": "done", "location": "gym",
                "actual_exercises": [
                    {"exercise_id": "weighted_pullup", "completed": True, "completed_sets": 4},
                    {"exercise_id": "core_hollow_hold", "completed": True, "completed_sets": 3},
                ],
            }]},
            {"date": "2026-10-01", "sessions": [{
                "session_id": "test_max_hang_7s", "status": "done", "location": "home", "tags": {"test": True},
                "resolved": {"resolved_session": {"exercise_instances": [
                    {"exercise_id": "max_hang_7s", "source": {"template_id": "finger_max_strength_test"}},
                    {"exercise_id": "general_warmup_jog", "source": {"template_id": "general_warmup"}},
                ]}},
            }]},
        ]}],
    }


def _base_state() -> Dict[str, Any]:
    plans = {"2026-09-28": _history_week()}
    return {
        "bodyweight_kg": 70.0,
        "body": {"weight_kg": 70.0, "age": 34},
        "assessment": {"experience": {"climbing_years": 6}},
        "preferences": {"finger_training_device": "hangboard"},
        "equipment": deepcopy(_EQUIPMENT),
        "macrocycle": deepcopy(_MACRO),
        "week_plans": plans,
        "working_loads": {"entries": [], "rules": {}},
    }


def cases() -> Dict[str, Dict[str, Any]]:
    onboarding = _base_state()
    onboarding["baselines"] = {
        "hangboard": [{"max_total_load_kg": 105.0, "source": "test", "updated_at": "2026-09-07",
                       "hang_seconds": 7, "edge_mm": 20, "grip": "half_crimp"}],
        "pulling": {"weighted_pullup_2rm_total_kg": 110.0, "source": "test", "updated_at": "2026-09-07",
                    "bodyweight_kg": 70.0},
    }

    stale = _base_state()
    stale["tests"] = {
        "max_strength": [{"test_id": "max_hang_7s_total_load", "date": "2026-05-19",
                          "total_load_kg": 110.0, "bodyweight_kg": 70.0}],
        "pulling_strength": [{"test_id": "weighted_pullup_2rm", "date": "2026-05-22",
                              "total_load_2rm_kg": 112.0, "estimated_1rm_kg": 117.0, "bodyweight_kg": 70.0}],
    }
    return {"no_tests_onboarding_baselines": onboarding, "stale_tests": stale}


_A295_KEYS = ("measure", "target_reps", "dp_range")


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def compute(*, pass_week_plan: bool = False) -> Dict[str, Any]:
    """Resolve every scheduled session of every case. ``pass_week_plan`` uses
    the A290 kwarg (not available on the pre-A290 code that made the golden)."""
    from backend.engine.resolve_session import resolve_session

    out: Dict[str, Any] = {}
    plans = future_plans()
    for name, state in cases().items():
        for d, sid, loc, gid, ph in _SCHEDULE:
            st = deepcopy(state)
            st["context"] = {"location": loc, "gym_id": gid, "target_date": d, "date": d}
            kw: Dict[str, Any] = {"phase": ph}
            if pass_week_plan:
                kw["week_plan"] = plans[_monday(d)]
            r = resolve_session(
                REPO_ROOT, f"backend/catalog/sessions/v1/{sid}.json", "backend/catalog/templates",
                "backend/catalog/exercises/v1/exercises.json", "", user_state_override=st,
                write_output=False, **kw,
            )
            r.pop("generated_at", None)
            insts = r["resolved_session"]["exercise_instances"]
            # A295 adds measure metadata (measure, target_reps, dp_range) to
            # every athlete's instances: additive, never a load. Stripped so
            # the golden keeps pinning the prescription bit for bit.
            for i in insts:
                for k in _A295_KEYS:
                    (i.get("suggested") or {}).pop(k, None)
                # A296 adds the additive display flag ``log_problems`` on the
                # limit boulder target (the players log problem by problem):
                # never a grade, stripped like the A295 metadata.
                ((i.get("suggested") or {}).get("suggested_boulder_target") or {}).pop("log_problems", None)
                if i.get("suggested") == {}:
                    i.pop("suggested")  # it held only A295 metadata
            out[f"{name}|{d}|{sid}"] = {
                "exercise_ids": [i["exercise_id"] for i in insts],
                "digest": _digest(r),
            }
    return out


if __name__ == "__main__":  # pragma: no cover - golden generator
    print(json.dumps(compute(), sort_keys=True, indent=1))
