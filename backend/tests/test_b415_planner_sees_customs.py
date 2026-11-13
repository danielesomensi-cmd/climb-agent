"""B415 (D287 C1-C3) — the weekly planner sees custom sessions and the sessions
already done.

C1 — the B161 seed (the previous week's trailing days → negative offsets of the
finger / hard gaps) dropped every session with no ``_SESSION_META`` entry
(custom, coach ad-hoc, generated add). After a Sunday max-hang custom,
strength_power put limit_boulder_gym (hard + finger) on Monday and guards_v1
flagged it (finger_gap + hard_back_to_back). A meta-less session now seeds with
its own tags (``stimulus.session_flag``, the reading of guards_v1, B390 and
B414), unless skipped; catalog sessions keep their reading (meta AND tags).

C2 — the finger floor (PASS 2.5) and the pulling floor (PASS 2.6) asked "does
the week already carry it?" of this run's placements only: the user's finger
custom got a second finger dose, and a week whose finger / pulling work was
already done said "didn't fit" (``unmet_stimulus`` → UnmetStimulusCard, and
key_sessions_v1 turns the finger key unplaceable). They now read the week as
the merge saves it: placements + lived done sessions (B390) + the user's own
sessions (B414). Pulling of a meta-less session: a pulling tag or a pulling_max
stimulus (weighted pull-ups); with neither it stays unseen, as before.

C3 — a hard session placed by the finger floor was not booked as a hard day,
so the passes after it (PASS 2.6, the tests) could open a hard day next to it
or past the weekly cap.

Approved by Daniele on 2026-11-13 (Phase 1 in docs/audit/D287_verification_appendix.md).
Synthetic fixtures only.
"""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from backend.engine import guards_v1
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.replanner_v1 import apply_events, regenerate_preserving_completed
from backend.engine.stimulus import session_flag
from backend.engine.user_owned import is_user_owned

START = "2026-01-05"  # Monday
PREV_START = "2025-12-29"
MON, TUE, WED, THU, FRI, SAT, SUN = ("2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
                                     "2026-01-09", "2026-01-10", "2026-01-11")
PREV_SUN = "2026-01-04"
GYMS = [{"name": "Gym A", "gym_id": "gym_a",
         "equipment": ["gym_boulder", "hangboard", "pullup_bar", "gym_routes", "dumbbell", "barbell"]}]
SIX = ("mon", "tue", "wed", "thu", "fri", "sat")
PROFILE = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45, "technique": 50, "endurance": 40}
CUSTOMS = [
    # hard + finger (derive_session_tags), no pulling stimulus
    {"id": "cs_hang", "name": "Max hangs", "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}]},
    # hard + finger + a pulling_max stimulus (weighted pull-ups)
    {"id": "cs_hang_pull", "name": "Hangs + weighted pulls",
     "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}, {"exercise_id": "weighted_pullup", "sets": 4}]},
]


def gen(phase="strength_power", *, start=START, days=SIX, target=5, cap=3, existing=None, prev=None, today=None):
    return generate_phase_week(
        phase_id=phase, domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase], PROFILE),
        session_pool=_build_session_pool(phase), start_date=start,
        availability={d: {"evening": {"available": True, "locations": ["gym"], "gym_id": "gym_a"}} for d in days},
        allowed_locations=["home", "gym"], hard_cap_per_week=cap,
        planning_prefs={"target_training_days_per_week": target}, default_gym_id="gym_a", gyms=deepcopy(GYMS),
        existing_week_plan=deepcopy(existing) if existing is not None else None,
        prev_week_plan=deepcopy(prev) if prev is not None else None, today=today,
    )


def _fp(wp) -> str:
    p = json.loads(json.dumps(wp))
    p.pop("generated_at", None)
    return json.dumps(p, sort_keys=True)


def _day(wp, d_iso):
    return next(d for d in wp["weeks"][0]["days"] if d["date"] == d_iso)


def _flag(wp, d_iso, flag):
    """The engine's sessions of the day carry *flag* (the user's are not the engine's)."""
    return any(session_flag(s, flag) for s in _day(wp, d_iso)["sessions"] if not is_user_owned(s))


def _engine_carries(wp, flag):
    """Some session the planner generated this week carries *flag* (pulling: the catalog flag)."""
    if flag == "pulling":
        return any(_SESSION_META.get(s["session_id"], {}).get("pulling")
                   for d in wp["weeks"][0]["days"] for s in d["sessions"])
    return any(_flag(wp, d["date"], flag) for d in wp["weeks"][0]["days"])


def _with_custom(plan, d_iso, cs="cs_hang", slot="lunch", status=None):
    out = apply_events(plan, [{"event_type": "add_custom_session", "custom_session_id": cs, "target_date": d_iso,
                               "slot": slot, "location": "gym", "gym_id": "gym_a"}], custom_sessions=CUSTOMS)
    if status is not None:
        next(s for s in _day(out, d_iso)["sessions"] if s.get("custom_session_id") == cs)["status"] = status
    return out


def _labelled(wp, label):
    return [(d["date"], s["session_id"]) for d in wp["weeks"][0]["days"] for s in d["sessions"]
            if label in (s.get("explain") or [])]


def _unmet(wp):
    return [u.get("stimulus") for u in wp.get("unmet_stimulus") or []]


def _mark_done(plan, d_iso):
    for s in _day(plan, d_iso)["sessions"]:
        s["status"] = "done"
    return plan


# ─── C1: the previous week's customs seed the gaps ──────────────────────────

@pytest.fixture(scope="module")
def prev_week():
    """The previous week as the planner left it (no custom yet)."""
    return gen(start=PREV_START)


class TestPrevWeekSeed:
    def test_baseline_monday_takes_limit_without_a_sunday_custom(self, prev_week):
        # Non-vacuity: the shape C1 relies on — Monday gets the hard finger session.
        wp = gen(prev=prev_week)
        assert [s["session_id"] for s in _day(wp, MON)["sessions"]] == ["limit_boulder_gym"]

    def test_sunday_hard_finger_custom_keeps_monday_free(self, prev_week):
        prev = _with_custom(prev_week, PREV_SUN, status="done")
        sunday = next(s for s in _day(prev, PREV_SUN)["sessions"] if s.get("is_custom"))
        assert sunday["session_id"] == "custom_cs_hang" and sunday["tags"] == {
            "hard": True, "finger": True, "finger_load": "high"}  # A327: the tier is stored too
        wp = gen(prev=prev)
        assert not _flag(wp, MON, "finger") and not _flag(wp, MON, "hard")
        # The engine's own Monday no longer raises the alerts it used to.
        prev_days = prev["weeks"][0]["days"]
        codes = {(w["code"], w["date"]) for w in guards_v1.evaluate(wp, prev_days)}
        assert (guards_v1.CODE_FINGER_GAP, MON) not in codes
        assert (guards_v1.CODE_HARD_BACK_TO_BACK, MON) not in codes
        # The hard / finger work still lands in the week, further on.
        assert any(_flag(wp, d, "finger") for d in (WED, THU, FRI, SAT))

    def test_a_planned_custom_counts_too(self, prev_week):
        # Like the catalog sessions and guards_v1: not done is not "did not happen".
        wp = gen(prev=_with_custom(prev_week, PREV_SUN))
        assert not _flag(wp, MON, "finger") and not _flag(wp, MON, "hard")

    def test_a_skipped_custom_is_ignored(self, prev_week):
        skipped = _with_custom(prev_week, PREV_SUN, status="skipped")
        assert _fp(gen(prev=skipped)) == _fp(gen(prev=prev_week))

    def test_catalog_branch_keeps_its_reading(self, prev_week):
        # A catalog session seeds with meta AND tags, as before B415: a stale
        # "hard / finger" tag on a session the catalog rates neither seeds nothing.
        prev = deepcopy(prev_week)
        _day(prev, PREV_SUN)["sessions"] = [{"slot": "evening", "session_id": "technique_focus_gym",
                                             "status": "done", "tags": {"hard": True, "finger": True}}]
        assert _fp(gen(prev=prev)) == _fp(gen(prev=prev_week))


# ─── C2: the floors read the week as the merge saves it ─────────────────────

class TestFingerFloorSeesTheUsersCustom:
    def test_no_second_finger_dose_next_to_the_users_custom(self):
        base = gen("power_endurance")
        # Non-vacuity: without the custom the floor places its maintenance dose.
        assert _labelled(base, "pass2.5:finger_floor") == [(SAT, "finger_maintenance_gym")]
        old = _with_custom(base, WED)
        for today in (None, MON):
            wp = gen("power_endurance", existing=old, today=today)
            assert _labelled(wp, "pass2.5:finger_floor") == []
            assert "finger_strength" not in _unmet(wp)

    def test_no_false_finger_row_when_the_custom_is_the_only_finger_work(self):
        # Base, four evenings: B414 keeps the engine's finger sessions away from
        # the user's Wednesday custom, so the custom is the week's only finger
        # work. Before B415 the floor did not see it, found no room for a dose
        # of its own and reported the finger stimulus as missing.
        days = ("mon", "tue", "wed", "thu")
        old = _with_custom(gen("base", days=days, target=4), WED)
        wp = gen("base", days=days, target=4, existing=old)
        assert not _engine_carries(wp, "finger")  # non-vacuity: the floor had to look
        assert "finger_strength" not in _unmet(wp)
        assert _labelled(wp, "pass2.5:finger_floor") == []


class TestFloorsSeeTheDoneSessions:
    @staticmethod
    def _three_customs(cs, status):
        days = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        old = gen(days=days, target=6)
        for d_iso in (MON, WED, FRI):
            _day(old, d_iso)["sessions"] = []
            old = _with_custom(old, d_iso, cs=cs, slot="evening", status=status)
        return gen(days=days, target=6, existing=old, today=SAT)

    def test_finger_customs_done_mon_wed_fri_regen_saturday(self):
        wp = self._three_customs("cs_hang", "done")
        # The three done customs are the week's finger work (they took the cap
        # and the gap): the engine adds none, and the week is not "missing" it.
        assert not _engine_carries(wp, "finger")
        assert "finger_strength" not in _unmet(wp)
        # A custom with no pulling information stays unseen by the pulling floor.
        assert "pulling" in _unmet(wp)

    def test_customs_never_marked_done_are_not_lived(self):
        # B390 unchanged: a past session never marked did not happen — the
        # engine plans its own finger work for the rest of the week.
        wp = self._three_customs("cs_hang", "planned")
        assert _engine_carries(wp, "finger")

    def test_a_custom_with_weighted_pulls_is_a_pulling_session(self):
        wp = self._three_customs("cs_hang_pull", "done")
        assert not _engine_carries(wp, "pulling")
        assert "finger_strength" not in _unmet(wp) and "pulling" not in _unmet(wp)

    @pytest.mark.parametrize("today", [THU, FRI, SAT])
    def test_done_catalog_limit_boulder_is_pulling(self, today):
        old = gen()
        _day(old, WED)["sessions"] = [{"slot": "evening", "session_id": "limit_boulder_gym", "status": "done",
                                       "location": "gym", "gym_id": "gym_a", "intensity": "max",
                                       "tags": {"hard": True, "finger": True},
                                       "constraints_applied": ["pass1:primary"]}]
        wp = gen(existing=old, today=today)
        assert not _engine_carries(wp, "pulling")  # the done session is the week's pulling work
        assert "pulling" not in _unmet(wp)


# ─── Invariant: past and user-owned sessions are never rewritten ────────────

class TestInvariants:
    def test_past_and_user_owned_sessions_identical_after_regeneration(self):
        old = gen("power_endurance")
        _mark_done(old, MON)
        old = _with_custom(old, TUE, status="done")                 # lived custom
        old = _with_custom(old, THU)                                 # the user's, planned
        old = _with_custom(old, SAT, cs="cs_hang_pull", status="skipped")
        new = gen("power_endurance", existing=old, today=WED)
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(new), preserve_before=WED)
        for d_iso in (MON, TUE):
            assert _day(merged, d_iso) == _day(old, d_iso)
        for d in old["weeks"][0]["days"]:
            kept = [s for s in d["sessions"] if is_user_owned(s) or s.get("status") in ("done", "skipped")]
            assert all(s in _day(merged, d["date"])["sessions"] for s in kept), d["date"]
        # The floors saw the user's work: no finger dose stacked next to it.
        assert _labelled(new, "pass2.5:finger_floor") == []

    def test_the_plans_it_reads_are_not_touched(self):
        # week.py passes the stored plans as they are (no copy): the planner
        # only reads the previous week and the week being regenerated.
        prev = _with_custom(gen(start=PREV_START), PREV_SUN, status="done")
        old = _with_custom(_mark_done(gen(), MON), WED)
        before = (json.dumps(prev, sort_keys=True), json.dumps(old, sort_keys=True))
        generate_phase_week(
            phase_id="strength_power", domain_weights=_adjust_domain_weights(_BASE_WEIGHTS["strength_power"], PROFILE),
            session_pool=_build_session_pool("strength_power"), start_date=START,
            availability={d: {"evening": {"available": True, "locations": ["gym"], "gym_id": "gym_a"}} for d in SIX},
            allowed_locations=["home", "gym"], hard_cap_per_week=3,
            planning_prefs={"target_training_days_per_week": 5}, default_gym_id="gym_a", gyms=deepcopy(GYMS),
            existing_week_plan=old, prev_week_plan=prev, today=TUE,
        )
        assert (json.dumps(prev, sort_keys=True), json.dumps(old, sort_keys=True)) == before

    def test_deterministic(self):
        old = _with_custom(gen("power_endurance"), WED)
        assert _fp(gen("power_endurance", existing=old, today=MON)) == \
            _fp(gen("power_endurance", existing=old, today=MON))

    def test_without_customs_or_lived_days_the_week_is_unchanged(self):
        # No plan of this week, no previous week → nothing for B415 to read.
        assert _fp(gen(existing=gen())) == _fp(gen())


# ─── C3: a hard session the finger floor places is a hard day ───────────────

def _floor_hard_kwargs(days, cap):
    """A week where the finger floor can only place a hard session: no
    hangboard (no maintenance dose), PASS 1 hands the kept days to technique
    and route endurance, PASS 2.2 puts a complementary session in each lunch,
    and the floor replaces one with power_contact_gym. The week has no pulling
    session, so PASS 2.6 then looks for a hard one (pulling_strength_gym)."""
    return dict(
        phase_id="strength_power",
        domain_weights={"finger_strength": 0.3, "pulling_strength": 0.2, "power_endurance": 0.1,
                        "volume_climbing": 0.1, "technique": 0.2, "core_prehab": 0.1},
        session_pool=["technique_focus_gym", "route_endurance_gym", "power_contact_gym",
                      "pulling_strength_gym", "core_training", "flexibility_full"],
        start_date=START,
        availability={d: {sl: {"available": True, "locations": ["gym"], "gym_id": "g1"} for sl in ("lunch", "evening")}
                      for d in days},
        allowed_locations=["gym"], hard_cap_per_week=cap,
        planning_prefs={"target_training_days_per_week": len(days), "hard_day_cap_per_week": cap,
                        "target_sessions_per_week": 4},
        default_gym_id="g1", gyms=[{"gym_id": "g1", "equipment": ["gym_boulder", "gym_routes", "pullup_bar"]}],
    )


def _hard_days(wp):
    return [d["date"] for d in wp["weeks"][0]["days"] if any(session_flag(s, "hard") for s in d["sessions"])]


class TestFloorBooksItsHardDay:
    def test_no_hard_session_the_day_after_the_floors(self):
        wp = generate_phase_week(**_floor_hard_kwargs(("tue", "wed"), cap=3))
        assert _labelled(wp, "pass2.5:finger_floor") == [(TUE, "power_contact_gym")]
        # Before B415 PASS 2.6 put pulling_strength_gym (hard) on Wednesday.
        assert _hard_days(wp) == [TUE]
        assert _labelled(wp, "pass2.6:pulling_maintenance") == []
        assert "pulling" in _unmet(wp)  # said, not silently skipped

    def test_the_floors_hard_day_counts_in_the_cap(self):
        wp = generate_phase_week(**_floor_hard_kwargs(("tue", "thu"), cap=1))
        assert _labelled(wp, "pass2.5:finger_floor") == [(TUE, "power_contact_gym")]
        # Before B415 Thursday got pulling_strength_gym too: 2 hard days, cap 1.
        assert _hard_days(wp) == [TUE]
        assert wp["weekly_load_summary"]["hard_days_count"] == 1
