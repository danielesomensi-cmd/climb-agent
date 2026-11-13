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

- free text (``notes``, ``cues``, ``description``...): kept out so a future
  wording fix does not churn the golden. C272 itself changes no note of an
  engine-selected exercise (the review reverted those rewrites; the A290
  golden, which hashes the full output, pins that);
- ``p0_trace`` / ``filter_trace``: their candidate counts (``start``, ``after_location``...) grow
  with the catalog by construction; they are debugging data, not output;
- ``generated_at``.

The golden ``fixtures/c272_resolver_golden.json`` was produced with
``python -m backend.tests.c272_golden_cases`` on origin/main @ 21aec98, BEFORE
any C272 catalog change. Time stability follows a290_untested_cases: the
phase is passed explicitly and ``week_plans`` holds only the past history
week, so the B267 recency window is the same whatever day the suite runs.

C276 changed 18 keys, each checked against a stripped export of origin/main @
e21e79d: 6 new ``lead_tryhard_gym`` keys (the home power-endurance day has no
rope routes, so its strict pins fail — pinned as a failed resolution);
``route_projecting_gym`` gains ``fall_practice`` right after the warm-up on the
3 gym keys and becomes a failed resolution (falls block failed, nothing else
changed) on the 3 home keys; ``strength_long`` / ``technique_focus_gym`` on the
3 gym keys change only in the ``equipment_required`` field of their
``fall_practice`` instance (``[]`` → ``["gym_routes"]``, the catalog moved the
requirement from ``equipment_required_any``) — same ids, same prescriptions.

C279 (2026-10-30) changed 30 keys, exactly the five lunch sessions
(``legs_maintenance_lunch``, ``upper_push_arms_lunch``,
``arms_shoulders_handstand_lunch``, ``treadmill_zone2_cardio``,
``treadmill_hiit_4x4``) on the 3 profiles × 2 dates, checked against a stripped
export of origin/main @ 31987c0: the lunches went from ~35' to ~55' (more sets,
new blocks); no other session moved.

A318 added 6 keys, one per profile × date, for the new session
``arms_shoulders_handstand_lunch``; no existing key changed (checked key by key
against the fixture of origin/main).

B380 changed 105 resolver keys and the 36 composer-pool digests, each checked
against a stripped export of origin/main @ a42e6ab under pytest. Selection
changes (9): ``upper_push_arms_lunch`` × 6 — ``bench_press`` now needs a real
barbell + bench, the profiles' gym/home have dumbbells only, so the chest-press
pin falls to P0 (``handstand_pushup_wall`` on 10-07, ``overhead_press`` on
10-21); ``heavy_conditioning_gym`` 10-07 × 3 — ``barbell_row`` needs a barbell,
``inverted_row`` instead (no bench → no ``dumbbell_row``). Value changes: curls
cold-start at 18 kg per dumbbell, ``overhead_press`` at 0.125 × BW (it is a
dumbbell press now) — 12 more keys. Every other key differs only by the additive
``suggested.load_unit`` (stripping it gives back the main digest). Pools: lose
``bench_press`` / ``barbell_row``; at the gym the two freed slots of the
truncated pool take ``v_up`` / ``wall_handstand_hold``.

A316 changed 6 keys, all ``treadmill_zone2_cardio`` (3 profiles × 2 dates), digest
only: ``treadmill_incline_walk`` gains the catalog ``hr_target`` band and its HR
cue drops the age formula. Same ids, same order, same prescriptions;
``other_engines`` unchanged. Checked by diffing ``compute()`` run under pytest on
origin/main @ 401bf63 against the A316 tree.

B381 changed 6 keys, all ``upper_push_arms_lunch`` (3 profiles x 2 dates): the
chest-press pin is ``dumbbell_bench_press`` now, so the dumbbell-only profiles
get it instead of the P0 fallback (``handstand_pushup_wall`` / ``overhead_press``).
Every other key and ``other_engines`` unchanged (isolated ``compute()`` under
pytest, origin/main vs the B381 tree).

B404 changed 2 resolver keys and 18 composer-pool entries (raw diff against
origin/main @ 7b77ee5). Resolver: ``lower_body_gym`` 10-07 × advanced /
intermediate — ``front_lever_one_leg`` loses ``alt_sides`` and goes 3 → 4 sets
(it was run as 3 × 2 sides; now 4 holds, alternating the extended leg). Pools:
the ad-hoc builder budgets on ``estimate_custom_session_duration``, which no
longer charges the full set rest between the two sides of an ``alt_sides`` set,
and ``campus_bumps`` is no longer doubled (it was billed 31 min for 14) — so
the same minutes fit more exercises (e.g. gym/general_strength gains
``heavy_reverse_wrist_curl`` and ``scapular_pullup``). Selection rules unchanged.

B405 changed 2 resolver keys (raw diff against origin/main @ 98d0f84):
``power_endurance_gym`` and ``route_endurance_gym`` 10-07 × advanced — the PE
drill's ``suggested_grade`` 7B → 7A and ``grade_anchor_from`` lead_max_rp →
lead_max_os (the PE anchor is the onsight now, never RP − 3 half grades when
there is one). Same ids, same order, same prescriptions; pools unchanged.

C283 changed 3 resolver keys (raw diff against origin/main @ bbe77a1, ladder
stage off as in the test): ``power_endurance_gym`` 10-07 × the 3 profiles —
``route_intervals`` is one ascent per set (``reps`` 1, ``work_seconds`` null,
``rest_between_sets_seconds`` 60 → 180) and ``category`` main_strength →
power_endurance. Same ids, same order; pools and ad-hoc unchanged.

B413 (step 4, A4: the re-entry factor on the anchored cap is gone) changed 6
resolver keys, all on the tested ``advanced`` profile: ``finger_strength_home``,
``pulling_strength_gym`` and ``strength_long`` × 10-07 / 10-21 (raw diff of the
stripped resolver output against the B413 step-3 tree @ fc71ca6, ladder stage
off). Every ``anchored.ramp`` loses ``factor`` and gains ``in_reentry``; the
n=1 re-entries lose the × 0.90: the max hang 7 s goes 93.5 → 104.0 total
(+15.5 → +26.0, cap 93.5 → 104.0) on both dates and the pull caps go 98.0 →
109.0 / 98.5 → 109.5 (the loads under them unchanged). Same ids, same order;
the untested and intermediate profiles, pools and ad-hoc unchanged.

B413 (step 5, D4) changed 6 resolver keys: ``legs_maintenance_lunch`` × the 3
profiles × 2 dates, digest only — the Bulgarian split squat rest 90 → 60 s
(the catalog change that keeps the lunch within 55' with the ladder core).
Checked by running this golden on the step-5 tree with that one value set
back to 90: every key identical, so the ``ladder_pin`` keys and the widened
core filters change nothing with the ladder stage off. The ladder-on side is
pinned by ``b413_lunch_golden_cases``.

B414 (step 6, REENTRY-MAX-HANG-SETS option B: the re-entry count and its
5-set max-hang cap are gone) changed the same 6 resolver keys as B413 step 4:
``finger_strength_home``, ``pulling_strength_gym`` and ``strength_long`` ×
10-07 / 10-21 on the tested ``advanced`` profile. Raw diff of the stripped
resolver output (ladder stage off) against the B414 step-5 tree @ d33cd9b:
the only change is ``suggested.anchored.ramp`` removed from every anchored
instance (10-07: n 3, not a re-entry; 10-21: n 1 after a 20-21 day gap, but
the hangs there are 3 sets, under the old cap of 5 — no set count moves).
Same ids, same order, same loads; pools and ad-hoc unchanged.

B414 (step 13, GOBLET) changed no resolver key and the 36 composer-pool
digests: ``back_squat`` needs a ``barbell`` now and no profile has one, so it
leaves every pool (home and gym); at the gym the freed slot of the truncated
pool takes ``wall_handstand_shrugs``. Checked by rebuilding the pools with the
old ``equipment_required: [weight]`` in memory: the old digests come back.
The legs lunch keeps ``goblet_squat`` here (the chain's fallback) — the
barbell side is pinned by ``b413_lunch_golden_cases`` (Daniele at Work).

B414 (step 14, INBOX-2026-11-02-b: the six sub-max hangs of domain
``finger_aerobic_endurance`` sort as ``finger_endurance``, no longer as
``aerobic_pure``) changed 8 resolver keys, order only:
``endurance_aerobic_gym`` 10-07 × the 3 profiles (``long_interval_repeaters``
before ``arc_training``: in strength_power finger endurance sorts before the
ARC), ``finger_maintenance_gym`` 10-21 × the 3 profiles (``bar_dead_hang``
before ``lopez_subhangs``) and ``power_endurance_gym`` 10-21 × advanced /
intermediate (home, no wall: ``intermittent_dead_hangs`` before the pulls —
in power_endurance finger endurance comes right after the PE intervals).
Re-resolved with the old category monkeypatched in: with the instances sorted
by ``instance_id`` the stripped outputs are identical. Pools and ad-hoc
unchanged.

B414 (step 16, one PE block in ``power_endurance_gym``; ``intensity_max:
medium`` on its finger block; a technique cue on the PE drills) changed the 6
``power_endurance_gym`` keys. Per-block diff against the step-15 session file
(ladder off and on): 10-07 at the board gym (routes) keeps ``route_intervals``
and loses the second PE drill (``linked_boulders_circuit`` /
``otm_bouldering``); 10-21 at home (no wall) the PE filters are soft, so the
single block takes what ``pe_routes`` used to take and the second, unrelated
pick of ``pe_boulder`` disappears (``rfd_explosive_pulls`` /
``one_arm_pullup_assisted`` — the untested pulling block then gets
``one_arm_pullup_assisted`` instead of ``pullup``). Finger blocks unchanged
here (already ≤ medium); the cue is free text (stripped). Every other key and
the pools unchanged.

D287 (handstand at the end of ``arms_shoulders_handstand_lunch``: the
``order: after_warmup`` flag moves from the handstand pair + the press to the
four lifts) changed the 6 keys of that session, order only. Raw diff of the
stripped output against the HEAD session file (ladder off and on, every
profile and slot): with the instances sorted by ``exercise_id``, and
``session_version`` / ``source.order`` set aside, the outputs are identical —
no id, dose, load or rest moved. Every other key and the pools unchanged.

B417 (``order: last`` on the handstand pair, ``after_warmup`` back on the
press only) changed the same keys of that session, order only: press,
floor core, arm lifts, toe pulls, wall hold. Every other key identical.

C286 (catalog: Z2 lunch with floor core, barbell bench on the push lunch,
one technique drill + finger ramp-up on the evening sessions) changed only
the keys of the seven sessions it touches; every other key identical.

A328 (D288 R3) added 6 keys, one per profile × date, for the new session
``deload_finger_touch`` (computed with ``compute()`` under the test's
conditions, ladder stage off); no existing key changed — the slots are not
deload dates, so the ``deload_sets: 0.5`` of the technique drills is dropped
unread (A312) and ``technique_focus_gym`` is byte-identical.
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

    The body-part picker is NOT in the static golden: C272 found its candidate
    list walked a ``set`` of string ids, so the pick changed with
    ``PYTHONHASHSEED`` from one process to the next. B414 sorted it (and seeds
    a request without seed from its day); cross-process determinism is pinned
    by ``test_b414_body_part_picker_determinism.py``, and the in-process
    differential test (full catalog vs catalog without the library-only
    entries) keeps covering the library filter."""
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
