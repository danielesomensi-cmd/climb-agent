"""C272 — resolver golden: the catalog additions must not change what the engine picks.

C272 adds ~70 library-only exercises (bodyweight ladders with ``role:
["ladder"]``, technique / try-hard drills with ``role: ["library"]``). No
template block asks for those roles, so ``resolve_session`` can never select
them — this module pins that claim on three profiles:

- ``untested``: onboarding baselines only (self-report, no test log);
- ``intermediate``: tested 2026-09-24, 70 kg, fingers 1.2×BW, 4 years;
- ``advanced``: Daniele-like, tested 2026-09-24, 78 kg, 8a+, 16 years.

Every non-test catalog session is resolved twice per profile (gym in strength
& power, home in power endurance). The snapshot keeps the SELECTION and the
PRESCRIPTION (exercise ids, sets/reps/seconds/rests, loads, grade targets) and
strips three things on purpose:

- free text (``notes``, ``cues``, ``description``...): C272 rewrites a few
  catalog notes (hanging_leg_raise, front_lever_tuck, lock_off_isometric,
  bear_crawl, core_standard) — that is the point of the note-only fixes;
- ``p0_trace`` / ``filter_trace``: their candidate counts (``start``, ``after_location``...) grow
  with the catalog by construction; they are debugging data, not output;
- ``generated_at``.

The golden ``fixtures/c272_resolver_golden.json`` was produced with
``python -m backend.tests.c272_golden_cases`` on origin/main @ 21aec98, BEFORE
any C272 catalog change. Time stability follows a290_untested_cases: the
phase is passed explicitly and ``week_plans`` holds only the past history
week, so the B267 recency window is the same whatever day the suite runs.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

from backend.tests.a290_untested_cases import REPO_ROOT, _base_state

EXERCISES = "backend/catalog/exercises/v1/exercises.json"
TEMPLATES = "backend/catalog/templates"

#: (date, location, gym_id, phase) — one gym day in S&P, one home day in PE.
_SLOTS = (
    ("2026-10-07", "gym", "g_board", "strength_power"),
    ("2026-10-21", "home", None, "power_endurance"),
)

#: Free-text keys stripped from the snapshot (see the module docstring).
_TEXT_KEYS = frozenset({
    "notes", "note", "cues", "description", "instructions", "name", "safety_notes",
    "explanation", "why", "title", "label", "message",
})
_TRACE_KEYS = frozenset({"p0_trace", "filter_trace", "generated_at", "trace"})


def profiles() -> Dict[str, Dict[str, Any]]:
    untested = _base_state()
    untested["baselines"] = {
        "hangboard": [{"max_total_load_kg": 105.0, "source": "test", "updated_at": "2026-09-07",
                       "hang_seconds": 7, "edge_mm": 20, "grip": "half_crimp"}],
        "pulling": {"weighted_pullup_2rm_total_kg": 110.0, "source": "test", "updated_at": "2026-09-07",
                    "bodyweight_kg": 70.0},
    }

    inter = _base_state()
    inter["assessment"] = {"experience": {"climbing_years": 4},
                           "grades": {"lead_max_rp": "7a", "lead_max_os": "6b+",
                                      "boulder_max_rp": "6B+", "boulder_max_os": "6A+"}}
    inter["tests"] = {
        "max_strength": [{"test_id": "max_hang_7s_total_load", "date": "2026-09-24",
                          "total_load_kg": 84.0, "bodyweight_kg": 70.0}],
        "pulling_strength": [{"test_id": "weighted_pullup_2rm", "date": "2026-09-24",
                              "total_load_2rm_kg": 90.0, "estimated_1rm_kg": 94.3, "bodyweight_kg": 70.0}],
    }

    adv = _base_state()
    adv["bodyweight_kg"] = 78.0
    adv["body"] = {"weight_kg": 78.0, "age": 40}
    adv["assessment"] = {"experience": {"climbing_years": 16},
                         "grades": {"lead_max_rp": "8a+", "lead_max_os": "7b",
                                    "boulder_max_rp": "7C", "boulder_max_os": "7A"},
                         "tests": {"l_sit_hold_seconds": 60}}
    adv["tests"] = {
        "max_strength": [{"test_id": "max_hang_7s_total_load", "date": "2026-09-24",
                          "total_load_kg": 116.0, "bodyweight_kg": 76.0}],
        "pulling_strength": [{"test_id": "weighted_pullup_2rm", "date": "2026-09-24",
                              "total_load_2rm_kg": 123.0, "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0}],
    }
    return {"untested": untested, "intermediate": inter, "advanced": adv}


def session_ids() -> List[str]:
    paths = sorted(glob.glob(os.path.join(REPO_ROOT, "backend/catalog/sessions/v1/*.json")))
    out = []
    for p in paths:
        sid = os.path.splitext(os.path.basename(p))[0]
        if not sid.startswith("test_"):
            out.append(sid)
    return out


def _strip(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in _TEXT_KEYS and k not in _TRACE_KEYS}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def compute(exercises_path: str = EXERCISES, *, only: Optional[List[str]] = None) -> Dict[str, Any]:
    """``{profile|date|session: {exercise_ids, digest}}`` — or ``{error}`` when
    the resolver raises (pinned too: a session that fails must keep failing)."""
    from backend.engine.resolve_session import resolve_session

    out: Dict[str, Any] = {}
    for name, state in profiles().items():
        for sid in (only or session_ids()):
            for d, loc, gid, ph in _SLOTS:
                st = deepcopy(state)
                st["context"] = {"location": loc, "gym_id": gid, "target_date": d, "date": d}
                key = f"{name}|{d}|{sid}"
                try:
                    r = resolve_session(
                        REPO_ROOT, f"backend/catalog/sessions/v1/{sid}.json", TEMPLATES, exercises_path, "",
                        user_state_override=st, write_output=False, phase=ph,
                    )
                except Exception as exc:  # pragma: no cover - pinned as data
                    out[key] = {"error": type(exc).__name__}
                    continue
                insts = (r.get("resolved_session") or {}).get("exercise_instances") or []
                out[key] = {
                    "exercise_ids": [i.get("exercise_id") for i in insts],
                    "digest": _digest(_strip(r)),
                }
    return out


#: Ad-hoc intents (focus, equipment set) exercised by the deterministic builder.
_ADHOC_FOCI = ("core", "general_strength", "technique", "pull", "fingers", "mobility")
_ADHOC_TODAY = "2026-10-07"


def _catalog_by_id(exercises_path: str = EXERCISES) -> Dict[str, Dict[str, Any]]:
    data = json.loads(open(os.path.join(REPO_ROOT, exercises_path), encoding="utf-8").read())
    items = data["exercises"] if isinstance(data, dict) else data
    return {e["id"]: e for e in items}


def compute_other_engines(exercises_path: str = EXERCISES, *, body_parts: bool = False) -> Dict[str, Any]:
    """The other catalog consumers: ad-hoc builder (``COACH_LLM_COMPOSER=0``
    path), the composer's pool and — only when ``body_parts`` — the body-part
    picker.

    The body-part picker is NOT in the static golden: its candidate list comes
    from a ``set`` of string ids, so its order (and with the seeded jitter, the
    pick) changes with ``PYTHONHASHSEED`` from one process to the next — a
    pre-existing non-determinism C272 found and reported, not one it caused.
    Inside one process the order is stable, so the in-process differential
    test (full catalog vs catalog without the library-only entries) still
    covers it."""
    from backend.coach.session_composer import build_pool
    from backend.engine.adhoc_builder import compose_adhoc_session
    from backend.engine.body_part_picker import BODY_PART_ORDER, generate_body_part_session

    by_id = _catalog_by_id(exercises_path)
    catalog_list = list(by_id.values())
    out: Dict[str, Any] = {}
    for name, state in profiles().items():
        for mode, gid in (("home", None), ("gym", "g_board")):
            for part in (BODY_PART_ORDER if body_parts else ()):
                try:
                    s = generate_body_part_session([part], mode, gid, deepcopy(state), catalog_list,
                                                   seed=7, today=_ADHOC_TODAY)
                    ids = [e.get("exercise_id") for e in s.get("exercises") or []]
                except Exception as exc:  # pragma: no cover - pinned as data
                    ids = [f"error:{type(exc).__name__}"]
                out[f"bodypart|{name}|{mode}|{part}"] = ids
            for focus in _ADHOC_FOCI:
                intent = {"equipment_set": mode, "focus": focus, "minutes": 45, "energy": "medium"}
                if gid:
                    intent["gym_name"] = "Board gym"
                try:
                    s = compose_adhoc_session(intent, deepcopy(state), by_id, today=_ADHOC_TODAY)
                    ids = [e.get("exercise_id") for e in s.get("exercises") or []]
                except Exception as exc:  # pragma: no cover - pinned as data
                    ids = [f"error:{type(exc).__name__}"]
                out[f"adhoc|{name}|{mode}|{focus}"] = ids
                pool = build_pool(intent, deepcopy(state), by_id)
                out[f"pool|{name}|{mode}|{focus}"] = _digest(sorted(str(e.get("id")) for e in pool))
    return out


if __name__ == "__main__":  # pragma: no cover - golden generator
    print(json.dumps({"resolver": compute(), "other_engines": compute_other_engines()},
                     sort_keys=True, indent=1))
