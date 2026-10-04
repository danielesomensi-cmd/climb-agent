"""B364 — untested athletes: inputs of the bit-for-bit regression.

DECISIONS 2026-10-04: higher intensities and anchor rules apply ONLY to a
tested baseline (test/test_session, < 90 days). For everyone else the
prescription must stay exactly what it was before B364. The golden output in
``fixtures/b364_untested_golden.json`` was produced by running ``compute()``
on origin/main @ 61ecfd4 (the commit B364 starts from); the regression test
re-runs it on the current code and compares.

One INTENDED exception, decided 2026-10-04 and tested separately: an untested
athlete with a pre-B363 weighted pull-up memory used to have that memory read
as a max (``pullup_reference_2rm`` legacy branch). The branch is removed — a
remembered load is never a max — so that case is not in the golden. The B363
``e2rm_total_kg`` re-base is NOT an exception: it is the untested athlete's
only pull-up progression and stays bit for bit (``progression`` leg below).

Review B364: ``onboarding_measured_persisted`` is the shape onboarding really
saves (``estimate_missing_baselines`` stamps the self-reported max as
``source='test'`` with the onboarding day). A self-report is not a test log,
so the athlete stays untested.

Regenerating the golden: copy this file into a checkout of origin/main @ 61ecfd4
and dump ``json.dumps(compute(), sort_keys=True, indent=1)``.

Pure data + one function, importable by the generator without pytest.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date as _date, timedelta as _td
from typing import Any, Dict, List, Tuple

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


def _instances() -> List[Dict[str, Any]]:
    return [
        {"exercise_id": "weighted_pullup", "load_model": "total_load", "prescription": {"sets": 4, "reps": 3}},
        {"exercise_id": "weighted_chinup", "load_model": "total_load", "prescription": {"sets": 4, "reps": 5}},
        {"exercise_id": "max_hang_7s", "load_model": "total_load", "prescription": {"sets": 5, "work_seconds": 7},
         "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.9}},
        {"exercise_id": "max_hang_5s", "load_model": "total_load", "prescription": {"sets": 5, "work_seconds": 5},
         "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.92}},
        {"exercise_id": "horst_7_53", "load_model": "total_load", "prescription": {"sets": 3, "work_seconds": 7}},
    ]


def _day(day: str, intent: str = "strength") -> Dict[str, Any]:
    return {"date": day, "sessions": [{
        "session_id": "strength_long", "intent": intent, "tags": {},
        "exercise_instances": _instances(),
    }]}


def cases() -> List[Tuple[str, Dict[str, Any], str]]:
    """(name, persisted state, date) — every state is UNTESTED on its date."""
    estimated = {
        "bodyweight_kg": 75.0,
        "macrocycle": deepcopy(_MACRO),
        "baselines": {
            "pulling": {"weighted_pullup_1rm_total_kg": 120.0, "bodyweight_kg": 75.0,
                        "max_external_load_kg": 45.0, "source": "estimated_from_assessment",
                        "estimated_at": "2026-09-01"},
            "hangboard": [{"max_total_load_kg": 110.0, "source": "estimated_from_grade",
                           "hang_seconds": 7, "edge_mm": 20, "grip": "half_crimp", "estimated_at": "2026-09-01"}],
        },
        "working_loads": {"entries": [
            {"exercise_id": "max_hang_7s", "key": "max_hang_7s", "setup": {}, "next_external_load_kg": 25.0,
             "next_total_load_kg": 100.0, "updated_at": "2026-10-01"},
            {"exercise_id": "weighted_chinup", "key": "weighted_chinup", "setup": {}, "next_external_load_kg": 20.0,
             "next_total_load_kg": 95.0, "updated_at": "2026-10-01"},
        ], "rules": {}},
    }
    stale = {
        "bodyweight_kg": 77.0,
        "macrocycle": deepcopy(_MACRO),
        "tests": {
            "max_strength": [{"test_id": "max_hang_7s_total_load", "date": "2026-05-19", "total_load_kg": 122.0,
                              "bodyweight_kg": 77.0}],
            "pulling_strength": [{"test_id": "weighted_pullup_2rm", "date": "2026-05-22", "total_load_2rm_kg": 122.0,
                                  "estimated_1rm_kg": 127.8, "bodyweight_kg": 77.0}],
        },
        "baselines": {
            "pulling": {"weighted_pullup_2rm_total_kg": 122.0, "weighted_pullup_1rm_estimated_kg": 127.8,
                        "weighted_pullup_1rm_total_kg": 127.8, "source": "test_session", "updated_at": "2026-05-22",
                        "max_external_load_kg": 50.5, "bodyweight_kg": 77.0},
            "hangboard": [{"max_total_load_kg": 122.0, "source": "test", "updated_at": "2026-05-19",
                           "hang_seconds": 7, "edge_mm": 20, "grip": "half_crimp"}],
        },
        "working_loads": {"entries": [], "rules": {}},
    }
    no_baselines = {
        "bodyweight_kg": 70.0,
        "macrocycle": deepcopy(_MACRO),
        "assessment": {"grades": {"lead_max_rp": "7c", "redpoint_french": "7c"}},
        "working_loads": {"entries": [], "rules": {}},
    }
    onboarding_measured = {
        "bodyweight_kg": 72.0,
        "macrocycle": deepcopy(_MACRO),
        "assessment": {
            "tests": {"max_hang_20mm_7s_total_kg": 105.0, "weighted_pullup_1rm_total_kg": 110.0},
            "tests_source": {"max_hang_20mm_7s_total_kg": "measured", "weighted_pullup_1rm_total_kg": "measured"},
        },
        "working_loads": {"entries": [], "rules": {}},
    }
    # What onboarding.py:431 / assessment.py:41 really persist for the same
    # answers (estimate_missing_baselines on the saved state), with a fixed day.
    onboarding_persisted = deepcopy(onboarding_measured)
    onboarding_persisted["baselines"] = {
        "hangboard": [{"max_total_load_kg": 105.0, "source": "test", "hang_seconds": 7, "edge_mm": 20,
                       "grip": "half_crimp", "updated_at": "2026-10-01"}],
        "pulling": {"weighted_pullup_1rm_total_kg": 110.0, "bodyweight_kg": 72.0, "max_external_load_kg": 38.0,
                    "source": "test", "updated_at": "2026-10-01"},
    }
    return [
        ("estimated_baselines_sp", estimated, "2026-10-09"),
        ("estimated_baselines_pe", estimated, "2026-10-21"),
        ("stale_tests", stale, "2026-10-09"),
        ("no_baselines", no_baselines, "2026-10-09"),
        ("onboarding_measured", onboarding_measured, "2026-10-09"),
        ("onboarding_measured_persisted", onboarding_persisted, "2026-10-09"),
    ]


def _strip(sug: Dict[str, Any]) -> Dict[str, Any]:
    # Fields every version writes; nothing date-of-today dependent.
    return {k: sug.get(k) for k in sorted(sug) if k != "schema_version"}


def compute() -> Dict[str, Any]:
    """Prescriptions + untested feedback memory for every case."""
    from backend.engine.adhoc_prescription import propose_exercise_prescription
    from backend.engine.body_part_picker import apply_resolver_light
    from backend.engine.progression_v1 import apply_feedback, inject_targets

    catalog = {
        "weighted_pullup": {"id": "weighted_pullup", "load_model": "total_load",
                            "prescription_defaults": {"sets": 4, "reps": 3}},
        "weighted_chinup": {"id": "weighted_chinup", "load_model": "total_load",
                            "prescription_defaults": {"sets": 4, "reps": 5}},
        "max_hang_7s": {"id": "max_hang_7s", "load_model": "total_load",
                        "prescription_defaults": {"sets": 5, "work_seconds": 7},
                        "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.9}},
    }
    out: Dict[str, Any] = {}
    for name, state, day in cases():
        res: Dict[str, Any] = {}
        injected = inject_targets(_day(day), deepcopy(state))
        res["inject"] = {
            inst["exercise_id"]: _strip(inst.get("suggested") or {})
            for inst in injected["sessions"][0]["exercise_instances"]
        }
        res["picker"] = {}
        for eid, ex in catalog.items():
            inst = apply_resolver_light(deepcopy(ex), deepcopy(state), day)
            res["picker"][eid] = {k: inst.get(k) for k in
                                  ("suggested_external_load_kg", "suggested_total_load_kg", "load_source")}
        res["propose"] = {
            eid: propose_exercise_prescription(eid, catalog, deepcopy(state), "strength_power", today=day)["load_kg"]
            for eid in catalog
        }
        # Untested hang / chin-up feedback keeps the pre-B364 % policy memory.
        log = {"date": day, "session_id": "strength_long", "actual": {"exercise_feedback_v1": [
            {"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "easy", "used_total_load_kg": 100.0},
            {"exercise_id": "weighted_chinup", "completed": True, "feedback_label": "hard", "used_external_load_kg": 20.0},
        ]}}
        updated = apply_feedback(log, deepcopy(state))
        res["feedback_entries"] = sorted(
            (
                {k: v for k, v in e.items() if k in (
                    "exercise_id", "key", "next_total_load_kg", "next_external_load_kg",
                    "last_total_load_kg", "last_external_load_kg", "last_feedback_label", "updated_at")}
                for e in updated["working_loads"]["entries"]
                if e.get("exercise_id") in ("max_hang_7s", "weighted_chinup")
            ),
            key=lambda e: str(e.get("key")),
        )
        # Review B364: feedback must keep moving the untested prescription —
        # three pull-up logs (easy / very_easy / easy at +30 x3), a very_easy
        # hang and an ok chin-up over the week before, then the day's targets.
        state_p = deepcopy(state)
        d0 = _date.fromisoformat(day)
        bw = float(state_p.get("bodyweight_kg") or 0.0)
        for offset, label in ((7, "easy"), (5, "very_easy"), (3, "easy")):
            log_p = {"date": (d0 - _td(days=offset)).isoformat(), "session_id": "strength_long",
                     "planned": [{"session_id": "strength_long", "tags": {}, "exercise_instances": _instances()}],
                     "actual": {"exercise_feedback_v1": [
                         {"exercise_id": "weighted_pullup", "completed": True, "feedback_label": label,
                          "used_external_load_kg": 30.0, "reps": 3},
                         {"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "very_easy",
                          "used_total_load_kg": round(bw + 22.5, 1)},
                         {"exercise_id": "weighted_chinup", "completed": True, "feedback_label": "ok",
                          "used_external_load_kg": 20.0},
                     ]}}
            state_p = apply_feedback(log_p, state_p)
        injected_p = inject_targets(_day(day), deepcopy(state_p))
        res["progression"] = {
            inst["exercise_id"]: _strip(inst.get("suggested") or {})
            for inst in injected_p["sessions"][0]["exercise_instances"]
            if inst["exercise_id"] in ("weighted_pullup", "weighted_chinup", "max_hang_7s")
        }
        out[name] = res
    return out
