"""B400 — the retest tests are placed against the week AS THE B369 MERGE WILL SAVE IT.

Prod (climb-coach bug-inbox, 2026-10-18): Daniele's week 2026-10-19 held two
sessions he had put there himself (``add_planned_session``, marker
``key_reschedule``) in place of the policy tests — route_endurance_gym Thu 22
evening and route_projecting_gym Sat 24 evening (finger-hard). A forced or
stale regeneration of that week put ``test_max_hang_7s`` on Sun 25 morning,
less than 24 h after his finger-hard session: the policy's own 72 h block.
PASS 3a checked its blockers on the freshly generated sessions only, and the
merge then put the user's sessions back byte-identical.

Fix: PASS 3a reads the week through ``planner_v2._merge_preview`` (the real
``_merge_user_content``, as A305's ``_week_view``) for every rule — same day,
72 h before the hang test, 48 h finger gap, 48 h heavy pull before the pull-up
test, hard cap and hard spacing; before today only what was done counts
(B390), a skipped stub never does. Plus: ``_planned_axis_tests(exclude_week)``
keeps the tests the merge puts back (no duplicate test), no test on an
other-sport day, and ``retest_status`` keeps the real skip reason at the 90-day
expiry and exposes ``tested_until``. Review: "today" for the lived days is the
policy's ``as_of`` when the planner's is a later regeneration floor
("regenerate from tomorrow"), a test the merge keeps is already scheduled for
PASS 3a too, and the lone partner of a moved test keeps the hang first.

Fixture (A319-proof): the decision must stay due under the A289 rules AND the
next brief A319's (42-day gap for every test, no end-of-phase slip). Macrocycle
from 14/09 (base 2 weeks → the last strength_power week is 19-25/10), both
tests on 10/09 with a stored HIGH confidence (``confidence_basis``) → earliest
22/10, allowed 22-25/10, trigger end_of_phase under both rule sets. The week
itself is generated as Daniele's real one (power_endurance, a289's
``_pe_week``): the decision is an input of PASS 3a, the planner never reads the
macrocycle. Synthetic fixtures only (no real user state in the repo).
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, timedelta

from backend.engine import athlete_context as ac
from backend.engine import guards_v1, replanner_v1
from backend.engine import retest_policy as rp
from backend.engine.planner_v2 import _SESSION_META, _merge_preview, generate_phase_week
from backend.engine.replanner_v1 import apply_events, regenerate_preserving_completed
from backend.engine.stimulus import is_finger_hard_session, session_flag
from backend.tests.test_a289_retest_policy import (
    _avail,
    _daniele,
    _kwargs,
    _macrocycle,
    _pe_week,
    _strip_volatile,
)

WS = "2026-10-19"
MON, TUE, WED, THU, FRI, SAT, SUN = (
    (date.fromisoformat(WS) + timedelta(days=i)).isoformat() for i in range(7)
)
HANG, PULL = "test_max_hang_7s", "test_max_weighted_pullup"
ALLOWED = [THU, FRI, SAT, SUN]
POOL = ["technique_focus_gym", "route_endurance_gym", "endurance_aerobic_gym"]  # no finger-hard session


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _due_state(**over) -> dict:
    """Both axes due on 22-25/10 with trigger end_of_phase, under the A289 and
    the A319 rules alike (see the module docstring)."""
    st = _daniele(macrocycle=_macrocycle("2026-09-14"), **over)
    for key in ("max_strength", "pulling_strength"):
        st["tests"][key][-1].update(date="2026-09-10", confidence="high",
                                    confidence_basis={"exposures": 3, "min_required": 2})
    return st


def _cap(n: int) -> dict:
    return {"hard_cap_per_week": n,
            "planning_prefs": {"target_training_days_per_week": 6, "hard_day_cap_per_week": n}}


def _day(plan: dict, d_iso: str) -> dict:
    return next(d for d in plan["weeks"][0]["days"] if d["date"] == d_iso)


def _put(plan: dict, d_iso: str, session: dict) -> None:
    """The session takes its slot on the day (what was there leaves)."""
    day = _day(plan, d_iso)
    day["sessions"] = [s for s in day["sessions"] if s.get("slot") != session.get("slot")] + [session]


def _owned(sid: str, slot: str, marker: str = "key_reschedule", **extra) -> dict:
    """A catalog session the user put on the plan (A294 key re-schedule shape)."""
    meta = _SESSION_META[sid]
    out = {"slot": slot, "session_id": sid, "status": "planned", "intensity": meta["intensity"],
           "tags": {"hard": meta["hard"], "finger": meta["finger"]}, "constraints_applied": [marker]}
    out.update(extra)
    return out


def _done(sid: str, slot: str) -> dict:
    meta = _SESSION_META[sid]
    return {"slot": slot, "session_id": sid, "status": "done", "intensity": meta["intensity"],
            "tags": {"hard": meta["hard"], "finger": meta["finger"]},
            "feedback_summary": {"difficulty": "ok"}}


def _custom_pull(slot: str, status: str = "planned", hard: bool = True) -> dict:
    """A user custom with heavy weighted pull-ups (pulling_max, no pulling tag)."""
    return {"slot": slot, "session_id": "custom_cs_b400", "is_custom": True, "custom_session_id": "cs_b400",
            "status": status, "constraints_applied": ["custom_add"], "tags": {"hard": hard, "finger": False},
            "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3}]}


def _custom_finger(slot: str) -> dict:
    """A user custom tagged finger, not hard, no exercise: no ``_SESSION_META``
    entry, so only ``session_flag`` (the tags) sees it as a finger session."""
    return {"slot": slot, "session_id": "custom_cs_finger", "is_custom": True, "custom_session_id": "cs_finger",
            "status": "planned", "constraints_applied": ["custom_add"], "tags": {"hard": False, "finger": True}}


def _regen(old: dict, state: dict, *, today=None, floor=None, policy_today="2026-10-18",
           device="hangboard", allowed=None, **kw):
    """GET /api/week's force / stale path: the decisions on the state holding
    *old* (the server's today), the planner with ``existing_week_plan``, then
    the B369 merge. Planner ``today`` and merge ``preserve_before`` are the
    regeneration floor: *floor* ("regenerate from tomorrow / next Monday"),
    else today (``None`` for a future week)."""
    st = deepcopy(state)
    st["week_plans"] = {WS: deepcopy(old)}
    dec = rp.retest_decisions(st, WS, today=today or policy_today, finger_device=device)
    if allowed is not None:
        dec = deepcopy(dec)
        for r in dec["required_sessions"]:
            r["allowed_dates"] = list(allowed)
    floor = floor or today
    fresh = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old),
                                           today=floor, **kw))
    merged = regenerate_preserving_completed(deepcopy(old), deepcopy(fresh), preserve_before=floor)
    return dec, fresh, merged


def _hang_only() -> dict:
    """Only the finger axis is tested (no pull-up test): the hang test alone."""
    st = _due_state()
    st["tests"]["pulling_strength"] = []
    return st


def _engine_pair_on(d_iso: str, **kw) -> dict:
    """The week as a previous generation left it: the policy's pair on *d_iso*."""
    dec = deepcopy(rp.retest_decisions(_due_state(), WS, today="2026-10-18", finger_device="hangboard"))
    for r in dec["required_sessions"]:
        r["allowed_dates"] = [d_iso]
    old = generate_phase_week(**_pe_week(retest_decisions=dec, **kw))
    assert {d for d, _slot, _sid in _tests(old)} == {d_iso}
    return old


def _placement_failures(plan: dict) -> list:
    """What the SkippedTestsCard shows ("Couldn't schedule a test")."""
    return [s for s in plan.get("skipped_tests") or []
            if s.get("required") and s.get("reason") in ("no_placement_slot", "blocked:no_paired_slot")]


def _outcomes(plan: dict) -> dict:
    return {r["session_id"]: r for r in plan["profile_snapshot"]["retest_decisions"]["required_sessions"]}


def _placed(plan: dict) -> dict:
    return {sid: (r["placed_date"], r["placed_slot"]) for sid, r in _outcomes(plan).items()
            if r["status"] == "placed"}


def _skip_reasons(plan: dict) -> dict:
    return {sid: r["skip_reason"] for sid, r in _outcomes(plan).items() if r["status"] == "skipped"}


def _sessions(plan: dict):
    for d in plan["weeks"][0]["days"]:
        for s in d["sessions"]:
            yield d["date"], s


def _tests(plan: dict) -> list:
    return sorted((d, s["slot"], s["session_id"]) for d, s in _sessions(plan)
                  if str(s["session_id"]).startswith("test_"))


def _hard_days(plan: dict) -> list:
    return sorted({d for d, s in _sessions(plan) if session_flag(s, "hard") and s.get("status") != "skipped"})


def _policy_test_alerts(plan: dict, state: dict, code: str, today=None) -> list:
    """The guard alerts (``GET /api/week`` oracle) of *code* naming a policy test."""
    def names(w):
        return w.get("session_id") in (HANG, PULL) or any(
            x.get("session_id") in (HANG, PULL) for x in w.get("with") or [])
    return [w for w in guards_v1.evaluate(plan, None, today, state) if w["code"] == code and names(w)]


def _repro_old() -> dict:
    """Daniele's week as he left it on 18/10: the engine's week, with his two
    key re-schedules in place of the policy tests."""
    old = generate_phase_week(**_pe_week())
    _put(old, THU, _owned("route_endurance_gym", "evening"))
    _put(old, SAT, _owned("route_projecting_gym", "evening"))
    return old


# ---------------------------------------------------------------------------
# (a) The prod repro
# ---------------------------------------------------------------------------

class TestProdRepro:
    def test_fixture_is_due_under_both_rule_sets(self):
        dec = rp.retest_decisions(_due_state(), WS, today="2026-10-18", finger_device="hangboard")
        rows = dec["required_sessions"]
        assert [r["session_id"] for r in rows] == [HANG, PULL]
        for r in rows:
            assert r["trigger"] == rp.TRIGGER_END_OF_PHASE
            assert (r["confidence"], r["gap_days"]) == ("high", 42)
            assert r["allowed_dates"] == ALLOWED

    def test_no_hang_test_after_the_users_finger_hard_session(self):
        st = _due_state()
        _dec, fresh, merged = _regen(_repro_old(), st)
        # Sun 25 is inside the 72 h after his Saturday evening, Thu/Sat
        # evenings are his: no day left this week — reported, never silent.
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot", PULL: "no_placement_slot"}
        assert _tests(merged) == []
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_TEST) == []
        # The user's sessions are back, byte-identical.
        assert _day(merged, SAT)["sessions"] == [_owned("route_projecting_gym", "evening")]
        assert _day(merged, THU)["sessions"] == [_owned("route_endurance_gym", "evening")]

    def test_blind_planner_reproduces_the_prod_placement(self):
        """Non-vacuity of the oracle: the planner without the plan being
        regenerated (what PASS 3a saw before B400) puts the hang on Sun 25
        morning, and the merged week flags it."""
        st = _due_state()
        old = _repro_old()
        st["week_plans"] = {WS: deepcopy(old)}
        dec = rp.retest_decisions(st, WS, today="2026-10-18", finger_device="hangboard")
        blind = generate_phase_week(**_pe_week(retest_decisions=dec))
        assert _placed(blind)[HANG] == (SUN, "morning")
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(blind), preserve_before=None)
        alerts = _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_TEST)
        assert [(w["date"], w["session_id"]) for w in alerts] == [(SAT, "route_projecting_gym")]


# ---------------------------------------------------------------------------
# (b)-(f) Every rule reads the merged week
# ---------------------------------------------------------------------------

class TestRulesOnTheMergedWeek:
    """One rule per case: every other rule leaves the candidate day free, so
    the user's session the merge puts back is the only thing that blocks it
    (the clean week places the test there: non-vacuity)."""

    def test_users_finger_hard_session_blocks_the_hang_72h_after(self):
        # Thu evening → Sun morning: 3 calendar days, inside the inclusive
        # 72 h block; too far for the 48 h finger gap and the hard spacing,
        # and cap 4 leaves room.
        st = _hang_only()
        old = generate_phase_week(**_pe_week(**_cap(4)))
        _dec, fresh, _m = _regen(deepcopy(old), st, allowed=[SUN], **_cap(4))
        assert _placed(fresh) == {HANG: (SUN, "morning")}
        _put(old, THU, _owned("route_projecting_gym", "evening"))
        _dec, fresh, merged = _regen(old, st, allowed=[SUN], **_cap(4))
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_TEST) == []

    def test_users_finger_session_blocks_the_hang_48h_before_it(self):
        # finger_maintenance_gym: a finger session, neither hard nor
        # finger-hard — only the 48 h finger gap reaches Sunday.
        st = _hang_only()
        old = generate_phase_week(**_pe_week(**_cap(3)))
        _dec, fresh, _m = _regen(deepcopy(old), st, allowed=[SUN], **_cap(3))
        assert _placed(fresh) == {HANG: (SUN, "morning")}
        _put(old, SAT, _owned("finger_maintenance_gym", "evening"))
        _dec, fresh, merged = _regen(old, st, allowed=[SUN], **_cap(3))
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_GAP) == []

    def test_users_finger_session_blocks_the_hang_48h_after_it(self):
        # The other side of the gap, with the user's custom tagged finger: no
        # `_SESSION_META` entry, only `session_flag` reads its tags.
        st = _hang_only()
        old = generate_phase_week(**_pe_week(session_pool=POOL))
        _dec, fresh, _m = _regen(deepcopy(old), st, allowed=[WED], session_pool=POOL)
        assert _placed(fresh) == {HANG: (WED, "morning")}
        _put(old, THU, _custom_finger("evening"))
        _dec, fresh, merged = _regen(old, st, allowed=[WED], session_pool=POOL)
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_GAP) == []

    def test_users_heavy_pull_blocks_the_pull_test_the_day_after_not_two_days_after(self):
        # Loading pin: only the pulling axis is covered, the pull-up test alone.
        # The custom is not tagged hard (its weighted pull-ups are pulling_max):
        # the hard spacing does not see it, only the 48 h heavy-pull rule.
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        clean = deepcopy(old)
        _put(old, THU, _custom_pull("lunch", hard=False))
        _dec, fresh, _m = _regen(clean, st, device="loading_pin", allowed=[FRI])
        assert _placed(fresh) == {PULL: (FRI, "morning")}  # non-vacuity: Friday is free
        dec, fresh, merged = _regen(old, st, device="loading_pin", allowed=[FRI])
        assert dec["covered_axes"] == ["pulling"]
        assert _skip_reasons(fresh) == {PULL: "no_placement_slot"}  # 24 h after the user's heavy pull
        assert PULL not in {sid for _d, _s, sid in _tests(merged)}
        _dec, fresh, merged = _regen(old, st, device="loading_pin", allowed=[SAT])
        assert _placed(fresh) == {PULL: (SAT, "morning")}  # 48 h exactly: allowed
        assert (SAT, "morning", PULL) in _tests(merged)

    def test_users_heavy_pull_blocks_the_pull_test_on_its_day(self):
        # The user's power_endurance_gym (pulling + hard) on the only allowed
        # day: the day is already hard (no cap, no spacing), only the same-day
        # heavy-pull rule refuses it.
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _dec, fresh, _m = _regen(deepcopy(old), st, device="loading_pin", allowed=[SAT])
        assert _placed(fresh) == {PULL: (SAT, "morning")}
        _put(old, SAT, _owned("power_endurance_gym", "evening"))
        _dec, fresh, merged = _regen(old, st, device="loading_pin", allowed=[SAT])
        assert _skip_reasons(fresh) == {PULL: "no_placement_slot"}
        assert _tests(merged) == []

    def test_users_finger_hard_session_blocks_the_hang_on_its_day(self):
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _dec, fresh, _m = _regen(old, st, allowed=[SUN])
        assert _placed(fresh) == {HANG: (SUN, "morning"), PULL: (SUN, "lunch")}  # non-vacuity
        _put(old, SUN, _owned("route_projecting_gym", "evening"))
        _dec, fresh, merged = _regen(old, st, allowed=[SUN])
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot", PULL: "no_placement_slot"}
        assert _tests(merged) == []
        assert _day(merged, SUN)["sessions"] == [_owned("route_projecting_gym", "evening")]

    def test_users_finger_hard_session_blocks_the_hang_that_would_replace_an_engine_session(self):
        # The hang's preferred move is to replace the day's generated
        # finger-hard session (a victim): the day is then previewed alone,
        # without the victim — the user's lunch session is still on it.
        st = _hang_only()
        old = generate_phase_week(**_pe_week())
        _dec, fresh, _m = _regen(deepcopy(old), st, allowed=[WED])
        assert _placed(fresh) == {HANG: (WED, "evening")}
        assert [s["session_id"] for s in _day(fresh, WED)["sessions"]] == [HANG]  # finger_strength_home replaced
        _put(old, WED, _owned("route_projecting_gym", "lunch"))
        _dec, fresh, merged = _regen(old, st, allowed=[WED])
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_TEST) == []

    def test_skipped_sessions_never_block(self):
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _put(old, SAT, _owned("route_projecting_gym", "evening", status="skipped"))
        _put(old, SAT, _custom_pull("lunch", status="skipped"))
        _put(old, SUN, _owned("finger_strength_home", "evening", status="skipped"))
        _dec, fresh, merged = _regen(old, st, allowed=[SUN])
        assert _placed(fresh) == {HANG: (SUN, "morning"), PULL: (SUN, "lunch")}
        assert (SUN, "morning", HANG) in _tests(merged) and (SUN, "lunch", PULL) in _tests(merged)
        # The skip stubs are history: back in their slot, untouched.
        assert _owned("finger_strength_home", "evening", status="skipped") in _day(merged, SUN)["sessions"]
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_TEST) == []

    def test_lived_hard_days_count_toward_the_cap(self):
        """B390 residual: cap 2, Monday and Tuesday done hard, regeneration on
        Wednesday — the tests must not open a third hard day."""
        st = _due_state()
        for cap, placed in ((2, False), (3, True)):
            old = generate_phase_week(**_pe_week(**_cap(cap)))
            _day(old, MON)["sessions"] = [_done("power_endurance_gym", "evening")]
            _day(old, TUE)["sessions"] = [_done("pulling_strength_gym", "evening")]
            dec, fresh, merged = _regen(old, st, today=WED, **_cap(cap))
            assert [r["allowed_dates"] for r in dec["required_sessions"]] == [ALLOWED, ALLOWED]
            assert _policy_test_alerts(merged, st, guards_v1.CODE_HARD_CAP, today=WED) == []
            if placed:  # non-vacuity: with room left the pair goes in
                assert set(_placed(fresh)) == {HANG, PULL}
                assert len(_hard_days(merged)) == 3
            else:
                assert _skip_reasons(fresh) == {HANG: "no_placement_slot", PULL: "no_placement_slot"}
                assert _hard_days(merged) == [MON, TUE]

    def test_users_hard_sessions_count_toward_cap_and_spacing(self):
        st = _hang_only()
        for cap in (3, 4):  # non-vacuity: Sunday is free at both caps
            old = generate_phase_week(**_pe_week(**_cap(cap)))
            _dec, fresh, _m = _regen(old, st, allowed=[SUN], **_cap(cap))
            assert _placed(fresh) == {HANG: (SUN, "morning")}
        # Spacing: the user's hard session the day before (not finger-hard);
        # cap 4 leaves room (Mon, Wed, Sat = 3), only the spacing refuses Sunday.
        spaced = generate_phase_week(**_pe_week(**_cap(4)))
        _put(spaced, SAT, _owned("power_endurance_gym", "evening"))
        _dec, fresh, merged = _regen(spaced, st, allowed=[SUN], **_cap(4))
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_HARD_BACK_TO_BACK) == []
        # Cap: the user's hard Thursday is the third hard day of a cap-3 week
        # (three days from Sunday: no spacing).
        capped = generate_phase_week(**_pe_week(**_cap(3)))
        _put(capped, THU, _owned("power_endurance_gym", "evening"))
        _dec, fresh, merged = _regen(capped, st, allowed=[SUN], **_cap(3))
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert len(_hard_days(merged)) == 3

    def test_an_engine_session_the_merge_drops_neither_blocks_nor_makes_the_day_hard(self):
        # The user's technique session takes Wednesday evening: the merge drops
        # the finger_strength_home generated there. Wednesday is then neither a
        # finger-hard day (same-day rule) nor a hard day — with Monday's the
        # only other hard day the hang fits a cap-2 week; with the user's hard
        # Sunday too the cap is full and the test opens no third hard day.
        st = _hang_only()
        old = generate_phase_week(**_pe_week(**_cap(2)))
        _put(old, WED, _owned("technique_focus_gym", "evening"))
        _dec, fresh, merged = _regen(old, st, allowed=[WED], **_cap(2))
        assert _placed(fresh) == {HANG: (WED, "morning")}
        assert _hard_days(merged) == [MON, WED]
        _put(old, SUN, _owned("power_endurance_gym", "evening"))
        _dec, fresh, merged = _regen(old, st, allowed=[WED], **_cap(2))
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert _hard_days(merged) == [MON, SUN]

    def test_the_users_hard_session_makes_the_day_hard_for_the_cap(self):
        # Cap 2 full with Monday + Wednesday: Sunday is refused — unless the
        # user's own hard session already makes it a hard day (the test then
        # adds none; the third hard day is the user's choice, alert-only).
        st = _hang_only()
        old = generate_phase_week(**_pe_week(**_cap(2)))
        _dec, fresh, _m = _regen(deepcopy(old), st, allowed=[SUN], **_cap(2))
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        _put(old, SUN, _owned("power_endurance_gym", "evening"))
        _dec, fresh, merged = _regen(old, st, allowed=[SUN], **_cap(2))
        assert _placed(fresh) == {HANG: (SUN, "morning")}
        assert _hard_days(merged) == [MON, WED, SUN]

    def test_lived_hard_days_count_once(self):
        # Cap 4, Monday + Tuesday done hard, regeneration on Wednesday: two
        # hard days, room for the test (each lived day counted once, whether
        # the merge preview or the B390 list holds it).
        st = _hang_only()
        old = generate_phase_week(**_pe_week(session_pool=POOL, **_cap(4)))
        _day(old, MON)["sessions"] = [_done("power_endurance_gym", "evening")]
        _day(old, TUE)["sessions"] = [_done("pulling_strength_gym", "evening")]
        _dec, fresh, merged = _regen(old, st, today=WED, allowed=[THU], session_pool=POOL, **_cap(4))
        assert _placed(fresh) == {HANG: (THU, "morning")}
        assert len(_hard_days(merged)) <= 4
        assert _policy_test_alerts(merged, st, guards_v1.CODE_HARD_CAP, today=WED) == []

    def test_a_past_session_never_marked_does_not_block(self):
        # B390: before today only what was done counts. Tuesday's planned
        # finger_strength_home was never marked → Thursday is free; done, it
        # blocks (72 h). The guards (GET /api/week) still flag the unmarked
        # one: they count every non-skipped session — the placement is the
        # contract here, not the alerts.
        st = _hang_only()
        old = generate_phase_week(**_pe_week(session_pool=POOL))
        _day(old, MON)["sessions"] = [_done("technique_focus_gym", "evening")]
        unmarked = deepcopy(old)
        _day(unmarked, TUE)["sessions"] = [{"slot": "evening", "session_id": "finger_strength_home",
                                            "status": "planned", "intensity": "high",
                                            "tags": {"hard": True, "finger": True}}]
        _dec, fresh, _m = _regen(unmarked, st, today=WED, allowed=[THU], session_pool=POOL)
        assert _placed(fresh) == {HANG: (THU, "morning")}
        lived = deepcopy(old)
        _day(lived, TUE)["sessions"] = [_done("finger_strength_home", "evening")]
        _dec, fresh, _m = _regen(lived, st, today=WED, allowed=[THU], session_pool=POOL)
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}

    def test_a_split_pair_sees_the_hang_placed_first(self):
        # Evenings only: the pair cannot share a day. The hang goes first; the
        # pull-up's day is chosen on the week WITH that hang — never the day
        # after it (hard spacing), with or without a plan of the week.
        st = _due_state()
        kw = {"availability": _avail(slots=("evening",)), "session_pool": POOL}
        dec = rp.retest_decisions(st, WS, today="2026-10-18", finger_device="hangboard")
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, **kw))
        assert _placed(plan) == {HANG: (FRI, "evening"), PULL: (SUN, "evening")}
        _dec, fresh, merged = _regen(generate_phase_week(**_pe_week(**kw)), st, **kw)
        assert _placed(fresh) == {HANG: (FRI, "evening"), PULL: (SUN, "evening")}
        assert _tests(merged) == [(FRI, "evening", HANG), (SUN, "evening", PULL)]

    def test_no_test_on_an_other_sport_day(self):
        st = _due_state()
        av = _avail()
        av["sun"]["evening"] = {"available": True, "locations": ["gym", "home"],
                                "preferred_location": "other_sport", "other_activity_name": "football"}
        dec = deepcopy(rp.retest_decisions(st, WS, today="2026-10-18", finger_device="hangboard"))
        for r in dec["required_sessions"]:
            r["allowed_dates"] = [SUN]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        assert _placed(plan) == {HANG: (SUN, "morning"), PULL: (SUN, "lunch")}  # non-vacuity
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, availability=av))
        assert _skip_reasons(plan) == {HANG: "no_placement_slot", PULL: "no_placement_slot"}
        assert _day(plan, SUN)["prev_other_activity_reduce"] is True


# ---------------------------------------------------------------------------
# (g) Today with a done session is copied wholesale
# ---------------------------------------------------------------------------

class TestTodayCopiedWholesale:
    def _old(self):
        # Wednesday and Saturday the only training days left: the planner
        # puts its finger-hard session on Wednesday (today).
        kw = {"availability": _avail(days=("mon", "tue", "wed", "sat")),
              "session_pool": ["finger_strength_home", "technique_focus_gym", "route_endurance_gym"]}
        old = generate_phase_week(**_pe_week(**kw))
        _day(old, MON)["sessions"] = [_done("technique_focus_gym", "evening")]
        _day(old, TUE)["sessions"] = [_done("route_endurance_gym", "evening")]
        _day(old, WED)["sessions"] = [_done("technique_focus_gym", "morning")]
        return old, kw

    def test_phantom_generated_finger_hard_of_today_does_not_block(self):
        st = _due_state()
        old, kw = self._old()
        dec, fresh, merged = _regen(old, st, today=WED, **kw)
        assert dec["locked_dates"] == [WED]
        # The planner generated a finger-hard session for today; the merge
        # copies today back as it was, so it never reaches the week.
        assert any(is_finger_hard_session(s) for s in _day(fresh, WED)["sessions"])
        assert _day(merged, WED) == _day(old, WED)
        assert _placed(fresh) == {HANG: (SAT, "morning"), PULL: (SAT, "lunch")}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_TEST, today=WED) == []

    def test_old_planned_finger_hard_of_today_blocks(self):
        st = _due_state()
        old, kw = self._old()
        _day(old, WED)["sessions"].append({"slot": "evening", "session_id": "finger_strength_home",
                                           "status": "planned", "intensity": "high",
                                           "tags": {"hard": True, "finger": True}})
        _dec, fresh, merged = _regen(old, st, today=WED, **kw)
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot", PULL: "no_placement_slot"}
        assert _tests(merged) == []
        assert _day(merged, WED) == _day(old, WED)


# ---------------------------------------------------------------------------
# (h) Tests the merge keeps are already scheduled
# ---------------------------------------------------------------------------

class TestTestsTheMergeKeeps:
    def test_user_moved_pair_is_already_scheduled(self):
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _day(old, THU)["sessions"] = [
            _owned(HANG, "morning", marker="user_moved"),
            _owned(PULL, "evening", marker="user_moved"),
        ]
        dec, fresh, merged = _regen(old, st)
        assert dec["required_sessions"] == []
        assert {(r["axis"], r["date"]) for r in dec["already_scheduled"]} == {("finger", THU), ("pulling", THU)}
        assert _tests(merged) == [(THU, "evening", PULL), (THU, "morning", HANG)]

    def test_only_the_moved_test_counts(self):
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _day(old, THU)["sessions"] = [_owned(HANG, "morning", marker="user_moved")]
        dec, fresh, merged = _regen(old, st)
        assert [r["session_id"] for r in dec["required_sessions"]] == [PULL]
        assert [r["axis"] for r in dec["already_scheduled"]] == ["finger"]
        assert [sid for _d, _s, sid in _tests(merged)].count(HANG) == 1
        assert [sid for _d, _s, sid in _tests(merged)].count(PULL) <= 1

    def test_test_on_today_with_a_done_session_is_already_scheduled(self):
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _day(old, MON)["sessions"] = [_done("technique_focus_gym", "evening")]
        _day(old, THU)["sessions"] = [
            _done("technique_focus_gym", "morning"),
            {"slot": "lunch", "session_id": HANG, "status": "planned",
             "tags": {"hard": True, "finger": True, "test": True}},
            {"slot": "evening", "session_id": PULL, "status": "planned",
             "tags": {"hard": True, "finger": False, "test": True}},
        ]
        dec, _fresh, merged = _regen(old, st, today=THU)
        assert dec["required_sessions"] == []
        assert {r["axis"] for r in dec["already_scheduled"]} == {"finger", "pulling"}
        assert _tests(merged) == [(THU, "evening", PULL), (THU, "lunch", HANG)]

    def test_test_on_a_day_the_user_declared_outdoor_is_already_scheduled(self):
        # The engine's pair on Sunday, then the user puts a crag day there: the
        # merge copies the day back as it was (engine-free, B379), tests
        # included — the policy must see them.
        st = _due_state()
        old = apply_events(_engine_pair_on(SUN), [{"event_type": "add_outdoor", "date": SUN,
                                                   "spot_name": "Crag A", "discipline": "lead"}])
        dec, fresh, merged = _regen(old, st, today=TUE)
        assert dec["required_sessions"] == []
        assert {(r["axis"], r["date"]) for r in dec["already_scheduled"]} == {("finger", SUN), ("pulling", SUN)}
        assert _tests(merged) == _tests(old)
        assert _placement_failures(merged) == []

    def test_a_done_test_is_history_not_a_scheduled_one(self):
        # The hang test done on Tuesday with no result in the test log: the
        # policy still calls the axis due (it reads the log), and PASS 3a
        # reads the week the same way — a done test is not "already
        # scheduled". The pair goes on Sunday, after the 72 h block.
        st = _due_state()
        old = generate_phase_week(**_pe_week(session_pool=POOL))
        _day(old, TUE)["sessions"] = [_done(HANG, "evening")]
        dec, fresh, _m = _regen(old, st, today=WED, session_pool=POOL)
        assert [r["session_id"] for r in dec["required_sessions"]] == [HANG, PULL]
        assert fresh["profile_snapshot"]["retest_decisions"]["already_scheduled"] == []
        assert _placed(fresh) == {HANG: (SUN, "morning"), PULL: (SUN, "evening")}

    def test_the_lone_partner_keeps_the_hang_first_on_a_shared_day(self):
        """The partner of a test the user moved comes alone: never earlier on
        the same day than the moved hang, never later than the moved pull-up
        (a hang after a 2RM pull-up is measured tired, and it sets the finger
        loads for 90 days)."""
        st = _due_state()

        def moved(sid: str, slot: str) -> dict:
            return _owned(sid, slot, marker="user_moved", tags={"hard": True, "finger": sid == HANG, "test": True})

        old = generate_phase_week(**_pe_week())
        _put(old, FRI, moved(HANG, "evening"))
        _dec, fresh, merged = _regen(old, st)
        assert _placed(fresh) == {PULL: (SUN, "morning")}
        _dec, fresh, merged = _regen(old, st, allowed=[FRI])  # Friday: only slots before the hang
        assert _skip_reasons(fresh) == {PULL: "no_placement_slot"}
        assert _tests(merged) == [(FRI, "evening", HANG)]
        old = generate_phase_week(**_pe_week())
        _put(old, SUN, moved(PULL, "morning"))
        _dec, fresh, merged = _regen(old, st, allowed=[SUN])  # Sunday: only slots after the pull-up
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot"}
        assert _tests(merged) == [(SUN, "morning", PULL)]

    def test_engine_tests_of_the_regenerated_week_are_replaced(self):
        """The engine's own tests are not kept as "already scheduled": the
        regeneration replaces them — still exactly one pair after the merge."""
        st = _due_state()
        dec0 = rp.retest_decisions(st, WS, today="2026-10-18", finger_device="hangboard")
        old = generate_phase_week(**_pe_week(retest_decisions=dec0))
        assert [sid for _d, _s, sid in _tests(old)] == [PULL, HANG]
        dec, fresh, merged = _regen(old, st)
        assert [r["session_id"] for r in dec["required_sessions"]] == [HANG, PULL]
        assert dec["already_scheduled"] == []
        assert _tests(merged) == _tests(old)


# ---------------------------------------------------------------------------
# "Regenerate from tomorrow / next Monday": the floor is not today
# ---------------------------------------------------------------------------

class TestRegenerationFloor:
    """The regenerate sheet's options: GET /api/week gives the planner and the
    merge the floor (``preserve_before``: tomorrow — the recommended one — or
    next Monday) and the policy the server's today. The days in between are
    copied wholesale by the merge and are still ahead: PASS 3a counts them in
    full (lived only before the policy's ``as_of``)."""

    def test_tonights_finger_hard_session_blocks_tomorrows_hang(self):
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _put(old, SAT, _owned("route_projecting_gym", "evening"))  # the user's, tonight
        dec, fresh, merged = _regen(old, st, today=SAT, floor=SUN)
        assert dec["as_of"] == SAT
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot", PULL: "no_placement_slot"}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_FINGER_TEST, today=SAT) == []
        assert _day(merged, SAT) == _day(old, SAT)
        # Non-vacuity: with the floor taken for today (before B400 review),
        # Saturday counts as lived (done only) and the hang lands on Sunday.
        st2 = deepcopy(st)
        st2["week_plans"] = {WS: deepcopy(old)}
        dec = {**rp.retest_decisions(st2, WS, today=SAT, finger_device="hangboard"), "as_of": SUN}
        blind = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old), today=SUN))
        assert _placed(blind)[HANG] == (SUN, "morning")

    def test_todays_planned_hard_session_counts_toward_the_cap(self):
        # Cap 2: Monday done hard + tonight's planned hard session = full.
        st = _due_state()
        old = generate_phase_week(**_pe_week(**_cap(2)))
        _day(old, MON)["sessions"] = [_done("power_endurance_gym", "evening")]
        for d_iso in (TUE, WED, THU, FRI, SUN):
            _day(old, d_iso)["sessions"] = []
        _day(old, SAT)["sessions"] = [{"slot": "evening", "session_id": "power_endurance_gym",
                                       "status": "planned", "tags": {"hard": True, "finger": False}}]
        _dec, fresh, merged = _regen(old, st, today=SAT, floor=SUN, **_cap(2))
        assert _skip_reasons(fresh) == {HANG: "no_placement_slot", PULL: "no_placement_slot"}
        assert _policy_test_alerts(merged, st, guards_v1.CODE_HARD_CAP, today=SAT) == []

    def test_tests_planned_today_stay_the_only_ones(self):
        # The pair is today (Friday); "from tomorrow" copies today back as it
        # was — it used to get a second pair at the weekend.
        st = _due_state()
        old = _engine_pair_on(FRI, session_pool=POOL)
        dec, fresh, merged = _regen(old, st, today=FRI, floor=SAT, session_pool=POOL)
        assert [r["session_id"] for r in dec["required_sessions"]] == [HANG, PULL]  # the policy cannot tell
        snap = fresh["profile_snapshot"]["retest_decisions"]
        assert snap["required_sessions"] == []
        assert {(r["axis"], r["date"]) for r in snap["already_scheduled"]} == {("finger", FRI), ("pulling", FRI)}
        assert _tests(merged) == _tests(old)
        assert _placement_failures(merged) == []

    def test_one_kept_test_its_partner_comes_alone(self):
        # Evenings only: the pair was split, hang Friday, pull-up Sunday. From
        # tomorrow on Friday: the hang stays (Friday copied back), the merge
        # drops the engine's Sunday pull-up — the pull-up alone is placed
        # again, unpaired as the policy would do it.
        st = _due_state()
        kw = {"availability": _avail(slots=("evening",)), "session_pool": POOL}
        old = generate_phase_week(**_pe_week(retest_decisions=rp.retest_decisions(
            st, WS, today="2026-10-18", finger_device="hangboard"), **kw))
        assert _tests(old) == [(FRI, "evening", HANG), (SUN, "evening", PULL)]
        _dec, fresh, merged = _regen(old, st, today=FRI, floor=SAT, **kw)
        snap = fresh["profile_snapshot"]["retest_decisions"]
        assert [(r["axis"], r["date"]) for r in snap["already_scheduled"]] == [("finger", FRI)]
        assert [(r["session_id"], r["status"], r["placed_date"], r["paired_with"])
                for r in snap["required_sessions"]] == [(PULL, "placed", SUN, None)]
        assert _tests(merged) == [(FRI, "evening", HANG), (SUN, "evening", PULL)]

    def test_from_next_monday_the_kept_tests_are_no_placement_failure(self):
        # Every day of the week is copied back; the pair stays on Sunday.
        st = _due_state()
        old = _engine_pair_on(SUN)
        _dec, fresh, merged = _regen(old, st, today=TUE, floor="2026-10-26")
        snap = fresh["profile_snapshot"]["retest_decisions"]
        assert snap["required_sessions"] == []
        assert {(r["axis"], r["date"]) for r in snap["already_scheduled"]} == {("finger", SUN), ("pulling", SUN)}
        assert _placement_failures(merged) == []
        assert merged["weeks"][0]["days"] == old["weeks"][0]["days"]
        # The status card reads the kept tests as planned.
        st["week_plans"] = {WS: merged}
        status = rp.retest_status(st, TUE, finger_device="hangboard")
        assert {a: (r["next_test"] or {}).get("date") for a, r in status["axes"].items()} == {
            "finger": SUN, "pulling": SUN}


# ---------------------------------------------------------------------------
# (i) No plan of this week → nothing changes
# ---------------------------------------------------------------------------

class TestNoPlanNoChange:
    def test_merge_preview_is_the_generated_week_without_a_plan_of_this_week(self):
        week_iso = [MON, TUE, WED, THU, FRI, SAT, SUN]
        gen = [[{"slot": "evening", "session_id": "technique_focus_gym"}] if i % 2 else [] for i in range(7)]
        other = generate_phase_week(**_kwargs("power_endurance", "2026-10-12"))
        for plan in (None, other):
            assert _merge_preview(plan, WS, week_iso, gen, None) == gen

    def test_merge_preview_puts_the_users_session_back(self):
        old = _repro_old()
        week_iso = [MON, TUE, WED, THU, FRI, SAT, SUN]
        gen = [[{"slot": "evening", "session_id": "technique_focus_gym"}] for _ in range(7)]
        view = _merge_preview(old, WS, week_iso, gen, None)
        assert view[5] == [_owned("route_projecting_gym", "evening")]  # the user's slot wins
        assert view[0] == gen[0]
        assert _merge_preview(old, WS, [SAT], [gen[5]], None) == [view[5]]  # one day alone

    def test_same_output_without_a_plan_or_with_nothing_to_preserve(self):
        dec = rp.retest_decisions(_due_state(), WS, today="2026-10-18", finger_device="hangboard")
        base = _strip_volatile(generate_phase_week(**_pe_week(retest_decisions=dec)))
        assert _placed(base) == {HANG: (SUN, "morning"), PULL: (SUN, "lunch")}
        other = generate_phase_week(**_kwargs("power_endurance", "2026-10-12"))
        engine_only = generate_phase_week(**_pe_week())
        for plan in (other, engine_only):
            out = _strip_volatile(generate_phase_week(**_pe_week(retest_decisions=dec,
                                                                 existing_week_plan=deepcopy(plan))))
            assert out == base

    def test_none_with_a_plan_of_this_week_runs_no_pass_3a(self):
        out = _strip_volatile(generate_phase_week(**_pe_week(retest_decisions=None,
                                                             existing_week_plan=_repro_old())))
        assert "retest_decisions" not in out["profile_snapshot"]
        assert _tests(out) == []

    def test_deterministic(self):
        st = _due_state()
        _d1, fresh_a, merged_a = _regen(_repro_old(), st)
        _d2, fresh_b, merged_b = _regen(_repro_old(), st)
        assert _strip_volatile(fresh_a) == _strip_volatile(fresh_b)
        assert merged_a["weeks"] == merged_b["weeks"]

    def test_a_failed_merge_preview_falls_back_to_the_generated_week(self, monkeypatch, caplog):
        st = _due_state()
        old = _repro_old()
        st["week_plans"] = {WS: deepcopy(old)}
        dec = rp.retest_decisions(st, WS, today="2026-10-18", finger_device="hangboard")
        base = generate_phase_week(**_pe_week(retest_decisions=dec))

        def _boom(*_a, **_k):
            raise RuntimeError("merge failed")

        monkeypatch.setattr(replanner_v1, "_merge_user_content", _boom)
        with caplog.at_level(logging.WARNING, logger="backend.engine.planner_v2"):
            fresh = generate_phase_week(**_pe_week(retest_decisions=dec, existing_week_plan=deepcopy(old)))
        assert _placed(fresh) == _placed(base) == {HANG: (SUN, "morning"), PULL: (SUN, "lunch")}
        assert any("B400: merge preview failed" in r.getMessage() for r in caplog.records)

    def test_a_malformed_entry_in_a_lived_day_never_breaks_the_week(self):
        st = _due_state()
        old = generate_phase_week(**_pe_week())
        _day(old, MON)["sessions"] = [_done("technique_focus_gym", "evening"), None, "x"]
        _dec, fresh, merged = _regen(old, st, today=WED)
        assert set(_placed(fresh)) | set(_skip_reasons(fresh)) == {HANG, PULL}
        assert _day(merged, MON) == _day(old, MON)  # a lived day stays as it was


# ---------------------------------------------------------------------------
# (j) retest_status: the real reason at the 90-day expiry, tested_until
# ---------------------------------------------------------------------------

def _status_state() -> dict:
    """Week 19/10 generated without the tests (PASS 3a: no_placement_slot); the
    macrocycle ends after power_endurance (15/11), so no other week skips before
    the official max expires on 08/12."""
    st = _due_state()
    st["macrocycle"]["phases"] = st["macrocycle"]["phases"][:3]
    days = [{"date": d, "sessions": []} for d in (MON, TUE, WED, THU, FRI, SAT, SUN)]
    st["week_plans"] = {WS: {"start_date": WS, "weeks": [{"days": days}], "profile_snapshot": {
        "retest_decisions": {"required_sessions": [
            {"axis": "finger", "status": "skipped", "skip_reason": "no_placement_slot"},
            {"axis": "pulling", "status": "skipped", "skip_reason": "no_placement_slot"},
        ]}}}}
    return st


class TestStatus:
    def test_real_reason_survives_the_90_day_expiry(self):
        status = rp.retest_status(_status_state(), WS, finger_device="hangboard")
        for axis in ("finger", "pulling"):
            row = status["axes"][axis]
            assert row["next_test"] is None
            assert row["next_test_reason"] == "no_placement_slot"  # was "not_tested_recently"

    def test_expiry_without_a_real_skip_stays_not_tested_recently(self):
        st = _status_state()
        st["week_plans"] = {}
        st["macrocycle"]["phases"] = st["macrocycle"]["phases"][:2]  # ends 25/10: nothing due after
        status = rp.retest_status(st, "2026-10-26", finger_device="hangboard")
        assert {a: r["next_test_reason"] for a, r in status["axes"].items()} == {
            "finger": "not_tested_recently", "pulling": "not_tested_recently"}

    def test_tested_until(self):
        st = _due_state()
        for on, covered, until in (("2026-10-19", True, "2026-12-08"), ("2026-12-08", True, "2026-12-08"),
                                   ("2026-12-09", False, None)):
            for row in rp.retest_status(st, on, finger_device="hangboard")["axes"].values():
                assert (row["covered"], row["tested_until"]) == (covered, until), on
        # Uncovered axis: the reason is unchanged (A289 path).
        f = rp.retest_status(st, "2026-12-09", finger_device="hangboard")["axes"]["finger"]
        assert f["next_test_reason"] == "not_tested_recently"

    def test_athlete_context_shows_tested_until(self):
        ctx = ac.build_athlete_context(_status_state(), WS, with_proposals=False, include_next_week=False)
        assert ctx["version"] == ac.VERSION == "b400.1"
        text = ac.render_text(ctx)
        assert "finger: ufficiale 116 kg (2026-09-10), massimale valido fino al 2026-12-08," in text
        assert "nessun test in vista (no_placement_slot)" in text
        coach = ac.render_coach_block(ctx)
        assert "tested max valid until 2026-12-08" in coach
        assert "no test due yet (no placement slot)" in coach


# ---------------------------------------------------------------------------
# (k) Past sessions are immutable
# ---------------------------------------------------------------------------

def test_past_sessions_immutable_after_the_regeneration():
    st = _due_state()
    old = generate_phase_week(**_pe_week())
    mon = {**_done("finger_strength_home", "evening"),
           "actual_exercises": [{"exercise_id": "max_hang_7s", "used_total_load_kg": 104.5}]}
    tue = _owned("power_endurance_gym", "evening", marker="quick_add")  # past, never marked
    _day(old, MON)["sessions"] = [deepcopy(mon)]
    _day(old, TUE)["sessions"] = [deepcopy(tue)]
    _put(old, SAT, _owned("route_projecting_gym", "evening"))
    _dec, _fresh, merged = _regen(old, st, today=WED)
    assert _day(merged, MON) == _day(old, MON)
    assert _day(merged, TUE) == _day(old, TUE)
    assert _day(merged, MON)["sessions"] == [mon] and _day(merged, TUE)["sessions"] == [tue]
    assert _owned("route_projecting_gym", "evening") in _day(merged, SAT)["sessions"]
