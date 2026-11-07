"""B413 (D4) — resolver golden with the ladder stage ON (tested athletes).

The C272 golden (``c272_golden_cases``) runs with the ladder stage OFF: it pins
that catalog changes alone move no selection. This one pins the other half —
what a TESTED athlete is prescribed with the stage on — so the D4 change
(``ladder_pin`` on the floor-core blocks of the four lunches) is visible key by
key, and any later change to it is too.

Profiles:

- ``advanced`` / ``intermediate``: the C272 profiles (tested 2026-09-24), every
  non-test catalog session on the two C272 slots — the ladder levels come from
  the read-time history seed of the profiles' past week (the advanced L-sit
  value has no ``test_l_sit_hold`` log in the window: it seeds nothing);
- ``daniele``: the advanced profile with Daniele's persisted levels of
  2026-11-04 (rollout L0 3x10, L-sit L2 4x10 s, Copenhagen dynamic L3 3x6,
  hollow L2 3x30 s), the four ladder-pin lunches at his lunch gym "Work", on
  the six (date, phase) slots of :data:`DANIELE_SLOTS`.

Same snapshot rules as C272 (``_strip``: free text, traces and the clock out).

The fixture ``fixtures/b413_lunch_ladder_golden.json`` was produced with
``python -m backend.tests.b413_lunch_golden_cases`` on the B413 step-5 tree.
The same ``compute()`` run on the step-4 tree (61b5e66, before D4) differs in
exactly the 40 keys of :data:`CHANGED_BY_D4`, all of them a ladder-pin lunch —
no other session of the two C272 profiles moved (raw diff of the stripped
output, key by key):

- ``advanced`` / ``intermediate`` × the four lunches × 2 slots (16 keys): no
  entry in the anti-extension families (L-sit, rollout) nor in the lateral
  one, but a history seed of the hollow ladder (the profiles' past week) — so
  the hollow block follows the hollow ladder: same exercise, ladder dose with
  the pin floor (3x30 s, ``pin_floor``), ladder rest 60 s instead of 45, the
  ``bw_ladder`` audit, ``picked_by`` ``ladder_pin``. Same ids, same order.
  The side plank (no lateral entry) is untouched. ``legs_maintenance_lunch``
  also gets the Bulgarian split squat rest 90 → 60 s (every profile, C272
  golden too);
- ``daniele`` × the four lunches × the six slots (24 keys): hollow hold →
  L-sit 4x10 s (arms, push) or ab-wheel rollout 3x10 (HIIT, legs); side
  plank → Copenhagen dynamic 3x6 (arms) and Copenhagen plank 3x20 s, one
  level below at the top of its band (HIIT, A2); the split-squat rest on the
  legs lunch. In deload one set fewer (ladder dose), the athlete's level kept
  (the pin level is exempt from the phase affinity).

B414 (step 6, REENTRY-MAX-HANG-SETS option B) changed 6 keys, the same as in
the C272 golden: ``advanced`` × ``finger_strength_home`` /
``pulling_strength_gym`` / ``strength_long`` × the two slots. Raw diff of the
stripped output against the step-5 tree @ d33cd9b (``git archive``): only
``suggested.anchored.ramp`` is removed from the anchored instances; no set
count, load, id or order moves. Every other key identical.

B414 (step 13, INBOX-2026-11-04-GOBLET) changed 6 keys: ``daniele`` ×
``legs_maintenance_lunch`` × the six slots. Work has a barbell, so the
``squat_main`` pin chain [back_squat → goblet_squat] takes ``back_squat``
(now ``equipment_required: [barbell]``): same dose 5 x 6 at 120", 4 sets in
deload, ``picked_by`` still ``explicit_exercise_id``; its load is the
progression cold start (11.5 kg, the profile has no back-squat working load —
the cold start is out of B414); the id sort puts it before the split squat.
Diff of the stripped output against the step-12 tree, key by key: only those 6
keys. ``advanced`` / ``intermediate`` (no barbell) identical, like every C272
key and ``PRE_B413_LEGS_DIGESTS``.

B414 (step 14, sub-max hangs sort as ``finger_endurance``) changed 6 keys,
order only — the same sessions as in the C272 golden on the two tested
profiles: ``endurance_aerobic_gym`` 10-07, ``finger_maintenance_gym`` 10-21,
``power_endurance_gym`` 10-21 × ``advanced`` / ``intermediate`` (same check:
instances sorted by ``instance_id``, stripped output identical). The lunches
(``daniele`` keys) have no sub-max hang: unchanged.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

from backend.tests import c272_golden_cases as golden

LUNCHES = ("arms_shoulders_handstand_lunch", "treadmill_hiit_4x4", "legs_maintenance_lunch",
           "upper_push_arms_lunch")

#: Daniele's lunch gym "Work" (gym_id 3c7f08e0 in production).
WORK = ["barbell", "cable_machine", "leg_press", "bench", "dumbbell", "pullup_bar", "weight",
        "resistance_band", "rings", "ab_wheel", "foam_roller", "treadmill"]

#: (date, phase) — one date per phase, inside that phase of the profiles'
#: macrocycle (base predates the test: the date is a strength one, the
#: ``phase`` argument is what the ladder reads). Two consecutive weeks in
#: performance so both A/B core rotations appear.
DANIELE_SLOTS = (
    ("2026-10-13", "base"),
    ("2026-10-13", "strength_power"),
    ("2026-10-27", "power_endurance"),
    ("2026-11-10", "performance"),
    ("2026-11-17", "performance"),
    ("2026-12-01", "deload"),
)

#: Daniele's persisted levels (production, 2026-11-04 after the realignment).
DANIELE_LEVELS = {
    "rollout": {"level_idx": 0, "sets": 3, "target": 10, "source": "user_edit"},
    "compression_floor": {"level_idx": 2, "sets": 4, "target": 10, "source": "user_edit"},
    "lateral": {"level_idx": 3, "sets": 3, "target": 6, "source": "feedback"},
    "hollow_plank": {"level_idx": 2, "sets": 3, "target": 30, "source": "user_edit"},
}


def daniele_state(date: str, levels: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    st = deepcopy(golden.profiles()["advanced"])
    st["equipment"]["gyms"].append({"gym_id": "work", "name": "Work", "priority": 2, "equipment": list(WORK)})
    st["context"] = {"location": "gym", "gym_id": "work", "target_date": date, "date": date}
    st["bw_progression"] = {
        fam: dict(entry, last_session_date="2026-10-01")
        for fam, entry in (DANIELE_LEVELS if levels is None else levels).items()
    }
    return st


def _resolve(sid: str, state: Dict[str, Any], phase: str) -> Dict[str, Any]:
    from backend.engine.resolve_session import resolve_session

    return resolve_session(
        golden.REPO_ROOT, f"backend/catalog/sessions/v1/{sid}.json", golden.TEMPLATES, golden.EXERCISES, "",
        user_state_override=state, write_output=False, phase=phase,
    )


def _snap(r: Dict[str, Any]) -> Dict[str, Any]:
    insts = (r.get("resolved_session") or {}).get("exercise_instances") or []
    return {"exercise_ids": [i.get("exercise_id") for i in insts], "digest": golden._digest(golden._strip(r))}


def compute(*, only: Optional[List[str]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    profiles = golden.profiles()
    for name in ("advanced", "intermediate"):
        for sid in (only or golden.session_ids()):
            for d, loc, gid, ph in golden._SLOTS:
                st = deepcopy(profiles[name])
                st["context"] = {"location": loc, "gym_id": gid, "target_date": d, "date": d}
                key = f"{name}|{d}|{sid}"
                try:
                    out[key] = _snap(_resolve(sid, st, ph))
                except Exception as exc:  # pragma: no cover - pinned as data
                    out[key] = {"error": type(exc).__name__}
    for sid in LUNCHES:
        if only and sid not in only:
            continue
        for d, ph in DANIELE_SLOTS:
            out[f"daniele|{d}|{ph}|{sid}"] = _snap(_resolve(sid, daniele_state(d), ph))
    return out


#: Keys whose output differs from the step-4 tree (61b5e66) — see the module
#: docstring. Sorted.
CHANGED_BY_D4: List[str] = [
    "advanced|2026-10-07|arms_shoulders_handstand_lunch",
    "advanced|2026-10-07|legs_maintenance_lunch",
    "advanced|2026-10-07|treadmill_hiit_4x4",
    "advanced|2026-10-07|upper_push_arms_lunch",
    "advanced|2026-10-21|arms_shoulders_handstand_lunch",
    "advanced|2026-10-21|legs_maintenance_lunch",
    "advanced|2026-10-21|treadmill_hiit_4x4",
    "advanced|2026-10-21|upper_push_arms_lunch",
    "daniele|2026-10-13|base|arms_shoulders_handstand_lunch",
    "daniele|2026-10-13|base|legs_maintenance_lunch",
    "daniele|2026-10-13|base|treadmill_hiit_4x4",
    "daniele|2026-10-13|base|upper_push_arms_lunch",
    "daniele|2026-10-13|strength_power|arms_shoulders_handstand_lunch",
    "daniele|2026-10-13|strength_power|legs_maintenance_lunch",
    "daniele|2026-10-13|strength_power|treadmill_hiit_4x4",
    "daniele|2026-10-13|strength_power|upper_push_arms_lunch",
    "daniele|2026-10-27|power_endurance|arms_shoulders_handstand_lunch",
    "daniele|2026-10-27|power_endurance|legs_maintenance_lunch",
    "daniele|2026-10-27|power_endurance|treadmill_hiit_4x4",
    "daniele|2026-10-27|power_endurance|upper_push_arms_lunch",
    "daniele|2026-11-10|performance|arms_shoulders_handstand_lunch",
    "daniele|2026-11-10|performance|legs_maintenance_lunch",
    "daniele|2026-11-10|performance|treadmill_hiit_4x4",
    "daniele|2026-11-10|performance|upper_push_arms_lunch",
    "daniele|2026-11-17|performance|arms_shoulders_handstand_lunch",
    "daniele|2026-11-17|performance|legs_maintenance_lunch",
    "daniele|2026-11-17|performance|treadmill_hiit_4x4",
    "daniele|2026-11-17|performance|upper_push_arms_lunch",
    "daniele|2026-12-01|deload|arms_shoulders_handstand_lunch",
    "daniele|2026-12-01|deload|legs_maintenance_lunch",
    "daniele|2026-12-01|deload|treadmill_hiit_4x4",
    "daniele|2026-12-01|deload|upper_push_arms_lunch",
    "intermediate|2026-10-07|arms_shoulders_handstand_lunch",
    "intermediate|2026-10-07|legs_maintenance_lunch",
    "intermediate|2026-10-07|treadmill_hiit_4x4",
    "intermediate|2026-10-07|upper_push_arms_lunch",
    "intermediate|2026-10-21|arms_shoulders_handstand_lunch",
    "intermediate|2026-10-21|legs_maintenance_lunch",
    "intermediate|2026-10-21|treadmill_hiit_4x4",
    "intermediate|2026-10-21|upper_push_arms_lunch",
]


if __name__ == "__main__":  # pragma: no cover - golden generator
    print(json.dumps(compute(), sort_keys=True, indent=1))
