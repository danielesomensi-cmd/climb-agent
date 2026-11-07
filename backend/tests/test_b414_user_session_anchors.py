"""B414 (step 19, B369-P6 point 1) — on a regeneration the engine's sessions
respect the finger gap, the hard gap and the hard cap around the user's own
sessions of the week.

Before B414 PASS 1 / 1.5 / 2 did not see the user's future sessions (custom,
quick-add, override, moved, key re-schedule, generated add): the merge put them
back byte-identical next to whatever the planner had generated, and only a
probe on a copy (``regeneration_guard_warnings``, read by nobody) said so. Repro
(Phase 1): a finger-hard custom on Saturday lunch, Thursday dropped from the
availability → the regeneration put power_contact_gym (hard, finger) on Friday
evening, and guards_v1 flagged finger_gap + hard_back_to_back on Saturday.

Decided by Daniele (2026-11-07): those three rules only — no slot is blocked,
the target days do not change; the probe is removed. Which sessions count:
user-owned (``is_user_owned``), not skipped, from today on, not done (a done
one is B390's lived day). Weeks without such sessions are byte-identical.

Synthetic fixtures only.
"""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from backend.engine import guards_v1
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.replanner_v1 import apply_events, regenerate_preserving_completed
from backend.engine.stimulus import session_flag

PHASE = "strength_power"
START = "2026-01-05"  # Monday
MON, TUE, WED, THU, FRI, SAT, SUN = ("2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
                                     "2026-01-09", "2026-01-10", "2026-01-11")
GYMS = [{"name": "Gym A", "gym_id": "gym_a",
         "equipment": ["gym_boulder", "hangboard", "pullup_bar", "gym_routes", "dumbbell", "barbell"]}]
ALL = ("mon", "tue", "wed", "thu", "fri", "sat")
NO_THU = ("mon", "tue", "wed", "fri", "sat")
CUSTOMS = [{"id": "cs_x", "name": "Hangs", "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}],
            "tags": {"hard": True, "finger": True}}]
PROFILE = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45, "technique": 50, "endurance": 40}


def gen(existing=None, days=ALL, today=None, cap=3):
    return generate_phase_week(
        phase_id=PHASE, domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[PHASE], PROFILE),
        session_pool=_build_session_pool(PHASE), start_date=START,
        availability={d: {"evening": {"available": True, "locations": ["gym"], "gym_id": "gym_a"}} for d in days},
        allowed_locations=["home", "gym"], hard_cap_per_week=cap,
        planning_prefs={"target_training_days_per_week": 5}, default_gym_id="gym_a", gyms=deepcopy(GYMS),
        existing_week_plan=deepcopy(existing) if existing is not None else None, today=today,
    )


def _fp(wp) -> str:
    p = json.loads(json.dumps(wp))
    p.pop("generated_at", None)
    return json.dumps(p, sort_keys=True)


def _day(wp, d_iso):
    return next(d for d in wp["weeks"][0]["days"] if d["date"] == d_iso)


def _engine(wp, d_iso):
    return [s for s in _day(wp, d_iso)["sessions"] if not s.get("is_custom")
            and not set(s.get("constraints_applied") or []) & {"quick_add", "user_forced", "user_moved",
                                                               "key_reschedule", "custom_add"}]


def _flag(wp, d_iso, flag, engine_only=True):
    pool = _engine(wp, d_iso) if engine_only else _day(wp, d_iso)["sessions"]
    return any(session_flag(s, flag) for s in pool)


def _with_custom(base, d_iso=SAT, slot="lunch"):
    return apply_events(base, [{"event_type": "add_custom_session", "custom_session_id": "cs_x",
                                "target_date": d_iso, "slot": slot, "location": "home"}], custom_sessions=CUSTOMS)


def _regen(old, days=NO_THU, today=None, cap=3):
    new = gen(existing=old, days=days, today=today, cap=cap)
    return new, regenerate_preserving_completed(deepcopy(old), deepcopy(new), preserve_before=today or START)


def _alerts(wp, *codes):
    return sorted({(w["code"], w["date"]) for w in guards_v1.evaluate(wp) if w["code"] in codes})


@pytest.fixture(scope="module")
def base():
    wp = gen()
    assert _day(wp, SAT)["sessions"] == [] and _flag(wp, THU, "finger")  # the shape the repro relies on
    return wp


class TestAnchors:
    def test_repro_no_finger_or_hard_engine_session_next_to_the_users(self, base):
        old = _with_custom(base)
        assert guards_v1.evaluate(old) == []
        new, merged = _regen(old)
        for d_iso in (FRI, SAT, SUN):
            assert not _flag(new, d_iso, "finger") and not _flag(new, d_iso, "hard"), d_iso
        assert _alerts(merged, guards_v1.CODE_FINGER_GAP, guards_v1.CODE_HARD_BACK_TO_BACK) == []
        # The user's session is back, byte-identical.
        assert [s for s in _day(merged, SAT)["sessions"] if s.get("is_custom")] == \
            [s for s in _day(old, SAT)["sessions"] if s.get("is_custom")]

    def test_non_vacuity_without_the_custom_friday_takes_the_hard_session(self, base):
        new = gen(existing=base, days=NO_THU)
        assert _flag(new, FRI, "finger") or _flag(new, FRI, "hard")

    def test_no_slot_is_blocked(self, base):
        # The user's day keeps its other slot for a session that is neither
        # finger nor hard.
        _new, merged = _regen(_with_custom(base))
        ev = [s for s in _engine(merged, SAT) if s["slot"] == "evening"]
        assert ev and not any(session_flag(s, "finger") or session_flag(s, "hard") for s in ev)

    def test_hard_cap_counts_the_users_hard_days(self, base):
        old = _with_custom(_with_custom(base, WED, "lunch"), SAT)
        _new, merged = _regen(old, days=ALL, cap=2)
        hard = [d["date"] for d in merged["weeks"][0]["days"] if any(session_flag(s, "hard") for s in d["sessions"])]
        assert len(hard) <= 2, hard
        assert {WED, SAT} <= set(hard)

    def test_user_days_are_not_counted_twice(self, base):
        # Today (Monday) is a lived hard day (B390: the engine's limit session
        # done) and holds the user's hard custom too: one hard day, so the
        # engine still gets the cap's other two.
        old = _with_custom(base, MON, "lunch")
        next(s for s in _day(old, MON)["sessions"] if not s.get("is_custom"))["status"] = "done"
        new, _m = _regen(old, days=ALL, today=MON, cap=3)
        engine_hard = [d["date"] for d in new["weeks"][0]["days"] if d["date"] > MON and _flag(new, d["date"], "hard")]
        assert len(engine_hard) == 2, engine_hard


class TestWhichSessionsCount:
    @pytest.mark.parametrize("marker", ["quick_add", "user_forced", "user_moved", "key_reschedule"])
    def test_user_markers_count(self, base, marker):
        old = deepcopy(base)
        _day(old, SAT)["sessions"] = [{"slot": "lunch", "session_id": "finger_strength_home", "status": "planned",
                                       "location": "home", "tags": {"hard": True, "finger": True},
                                       "constraints_applied": [marker]}]
        new = gen(existing=old, days=NO_THU)
        assert not _flag(new, FRI, "finger") and not _flag(new, FRI, "hard")

    def test_skipped_does_not_count(self, base):
        old = _with_custom(base)
        next(s for s in _day(old, SAT)["sessions"] if s.get("is_custom"))["status"] = "skipped"
        assert _fp(gen(existing=old, days=NO_THU)) == _fp(gen(existing=_without_user(old), days=NO_THU))

    def test_past_day_not_done_does_not_count(self, base):
        # B390: before today only what was done counts.
        old = _with_custom(base, TUE, "lunch")
        assert _fp(gen(existing=old, days=NO_THU, today=WED)) == \
            _fp(gen(existing=_without_user(old), days=NO_THU, today=WED))

    def test_engine_sessions_are_not_anchors(self, base):
        assert _fp(gen(existing=base, days=NO_THU)) == _fp(gen(days=NO_THU))


class TestInvariants:
    def test_week_without_user_sessions_is_identical(self, base):
        assert _fp(gen(existing=base)) == _fp(gen())

    def test_past_days_byte_identical(self, base):
        old = _with_custom(base, FRI, "lunch")
        _day(old, MON)["sessions"][0]["status"] = "done"
        _new, merged = _regen(old, days=ALL, today=WED)
        for d_iso in (MON, TUE):
            assert _day(merged, d_iso) == _day(old, d_iso)

    def test_no_regeneration_guard_record_is_written_and_a_legacy_one_is_dropped(self, base):
        old = _with_custom(base)
        old["adaptations"].append({"type": "regeneration_guard_warnings", "warnings": [{"date": FRI}]})
        _new, merged = _regen(old)
        assert not any(a.get("type") == "regeneration_guard_warnings" for a in merged["adaptations"])
        # The user's records are still carried.
        assert any(a.get("type") == "event" for a in merged["adaptations"])

    def test_summary_counts_the_engines_finger_days_only(self, base):
        new = gen(existing=_with_custom(base), days=NO_THU)
        engine_finger = sum(1 for d in new["weeks"][0]["days"] if _flag(new, d["date"], "finger"))
        assert new["weeks"][0]["targets"]["finger_days"] == engine_finger

    def test_deterministic(self, base):
        old = _with_custom(base)
        a, ma = _regen(old)
        b, mb = _regen(old)
        assert _fp(a) == _fp(b) and _fp(ma) == _fp(mb)


def _without_user(wp):
    out = deepcopy(wp)
    for d in out["weeks"][0]["days"]:
        d["sessions"] = [s for s in d["sessions"] if not s.get("is_custom")
                         and not set(s.get("constraints_applied") or []) & {"quick_add", "user_forced",
                                                                           "user_moved", "key_reschedule"}]
    return out
