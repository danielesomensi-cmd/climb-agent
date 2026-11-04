"""B413 — end to end: four simulated weeks of an athlete like Daniele.

Every B413 piece in one run, through the real API (TestClient, file storage in
a temp dir) and in calendar order:

- **archive (D1)** — the rollout ladder has no persisted entry: its only
  history (3x10 "ok") sits in an archived week five weeks before the first
  simulated one, and the lunches seed from it. A221 moves the simulated weeks
  to the cold store as they age (``deps.archive_past_weeks`` with the
  simulated date — the lazy trigger is off in tests);
- **seed and steps (D5, A1)** — "ok" +1 step, "easy" +2, a done row with no
  rating counts as "ok", the deload freezes the doses with one set fewer;
- **ladder_pin (D4, A2)** — the floor core of the four catalog lunches is the
  athlete's ladder level, the Tuesday HIIT lateral row one level below;
- **freeze (D2)** — a played engine session keeps the prescription it was
  shown, on /feedback (guided player) and on /events (mark done);
- **done without feedback (D3)** — the Tuesday HIIT is only marked done.

Week schedule (W0 power endurance, W1-W2 performance, W3 deload):

| day | session | flow |
|---|---|---|
| Mon | arms lunch | guided feedback, labels by week |
| Tue | HIIT lunch | mark done only (no feedback) |
| Tue | key session of the phase (evening) | mark done, then the dialog ("ok") |
| Wed | legs lunch | guided feedback, no rating |
| Fri | push lunch | guided feedback, labels by week |
| Sat | finger maintenance (W0-W2) | guided feedback "ok" |

What is checked: every played session stays byte for byte through every later
request (hot and archived); the record of a played lunch is the prescription
the GET showed; the ladders only go up, and not at all in the deload; the HIIT
lateral row is one level below; every lunch view fits 55'; at most one archive
read per request; and the key-session status and the guard alerts of every
response are identical to a baseline run where the ladders never move and the
lunches keep their catalog core (B413 changes no guard and no key session).

The simulated weeks are the four weeks before the current one (the API is on
the real clock: past weeks are served read-only and marking a session in them
is the explicit retroactive tick the replanner allows).
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import bw_ladders as bl
from backend.engine import bw_progression as bp
from backend.engine import resolve_session as rs
from backend.engine import storage
from backend.engine.custom_session import estimate_custom_session_duration
from backend.engine.planner_v2 import _SESSION_META
from backend.tests import b413_lunch_golden_cases as lg
from backend.tests import c272_golden_cases as golden

client = TestClient(app)

UID = str(uuid.UUID(int=0xB413E2E, version=4))
HDR = {"X-User-ID": UID}

ARMS, HIIT, LEGS, PUSH = lg.LUNCHES
WEEKS = 4
#: Absolute week number of W0 in the macrocycle below (start = W0 - 8 weeks).
W0_NUM = 9
PHASES = ("power_endurance", "performance", "performance", "deload")
#: The key session of the phase (Tuesday evening).
KEY_SESSION = {"power_endurance": "power_endurance_gym", "performance": "route_projecting_gym",
               "deload": "technique_focus_gym"}
#: Labels of the guided feedback on the arms (Mon) and push (Fri) lunches, by
#: week. None = no rating (the athlete did not tap a label).
ARMS_LABELS = ("ok", "easy", None, "ok")
PUSH_LABELS = ("easy", "ok", None, "easy")

#: Daniele's persisted levels (2026-11-04) without the rollout: that family
#: seeds from the archive.
LEVELS = {fam: dict(e) for fam, e in lg.DANIELE_LEVELS.items() if fam != "rollout"}

DOSE_KEYS = ("exercise_id", "level_idx", "target", "sets")


def _monday() -> date:
    d = date.today()
    return d - timedelta(days=d.weekday())


W = [_monday() - timedelta(weeks=WEEKS - k) for k in range(WEEKS)]
HISTORY_WEEK = W[0] - timedelta(weeks=5)


def _entry(sid: str, slot: str, location: str, gym_id: Optional[str], phase: str) -> dict:
    meta = _SESSION_META[sid]
    return {"slot": slot, "session_id": sid, "location": location, "gym_id": gym_id, "phase_id": phase,
            "intensity": meta["intensity"], "tags": {"hard": meta["hard"], "finger": meta["finger"]}}


def _week_plan(k: int) -> dict:
    ph = PHASES[k]
    days: Dict[int, List[dict]] = {
        0: [_entry(ARMS, "lunch", "gym", "work", ph)],
        1: [_entry(HIIT, "lunch", "gym", "work", ph), _entry(KEY_SESSION[ph], "evening", "gym", "g_board", ph)],
        2: [_entry(LEGS, "lunch", "gym", "work", ph)],
        4: [_entry(PUSH, "lunch", "gym", "work", ph)],
    }
    if ph != "deload":
        days[5] = [_entry("finger_maintenance_home", "evening", "home", None, ph)]
    start = W[k]
    return {
        "start_date": start.isoformat(),
        "profile_snapshot": {"phase_id": ph},
        "weeks": [{"week_index": 1, "days": [
            {"date": (start + timedelta(days=i)).isoformat(), "sessions": days.get(i, [])} for i in range(7)]}],
    }


def _history_week() -> dict:
    """The only rollout history: a custom 3x10 "ok", five weeks before W0."""
    start = HISTORY_WEEK
    return {"start_date": start.isoformat(), "profile_snapshot": {"phase_id": "power_endurance"},
            "weeks": [{"week_index": 1, "days": [
                {"date": (start + timedelta(days=i)).isoformat(), "sessions": [] if i != 2 else [{
                    "slot": "lunch", "session_id": "custom_cs_core", "is_custom": True, "status": "done",
                    "exercises": [{"exercise_id": "ab_wheel_rollout", "sets": 3, "reps": 10}],
                    "actual_exercises": [{"exercise_id": "ab_wheel_rollout", "completed": True,
                                          "completed_sets": 3, "feedback_label": "ok"}]}]}
                for i in range(7)]}]}


def _state() -> dict:
    st = copy.deepcopy(golden.profiles()["advanced"])
    test_day = (W[0] - timedelta(days=7)).isoformat()
    for rows in st["tests"].values():
        for r in rows:
            r["date"] = test_day
    st["equipment"]["gyms"].append({"gym_id": "work", "name": "Work", "priority": 2, "equipment": list(lg.WORK)})
    st["bw_progression"] = {fam: dict(e, last_session_date=(W[0] - timedelta(days=10)).isoformat())
                            for fam, e in LEVELS.items()}
    st["macrocycle"] = {
        "start_date": (W[0] - timedelta(weeks=W0_NUM - 1)).isoformat(),
        "total_weeks": 14,
        "phases": [
            {"phase_id": "base", "duration_weeks": 2},
            {"phase_id": "strength_power", "duration_weeks": 4},
            {"phase_id": "power_endurance", "duration_weeks": 3},
            {"phase_id": "performance", "duration_weeks": 2},
            # Long enough that the cycle still runs on the real today.
            {"phase_id": "deload", "duration_weeks": 3},
        ],
    }
    st["week_plans"] = {W[k].isoformat(): _week_plan(k) for k in range(WEEKS)}
    # The real current week (empty): the simulated weeks are all past for the
    # server clock, so /feedback finds them in week_plans (the B216 path).
    now = _monday()
    st["week_plans"][now.isoformat()] = {"start_date": now.isoformat(), "weeks": [{"week_index": 1, "days": [
        {"date": (now + timedelta(days=i)).isoformat(), "sessions": []} for i in range(7)]}]}
    st["current_week_plan"] = st["week_plans"][now.isoformat()]
    st["session_completion_log"] = []
    st["custom_sessions"] = []
    return st


# ---------------------------------------------------------------------------
# The simulation
# ---------------------------------------------------------------------------

def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True)


#: What GET /week attaches to a played session at read (A141 cue, B32
#: feedback summary). A client that posts the plan back to /events echoes
#: them, and B371 keeps a played session as the client sent it — a copy of
#: data that lives elsewhere (feedback_log), not part of the record, and
#: older than B413 (see test_b413_freeze_prescription).
READ_TIME_KEYS = ("process_cue", "feedback_summary", "exercise_feedback", "session_duration_seconds")


def _played(session: dict) -> str:
    """A played session as stored, every field of the record compared."""
    return _canon({k: v for k, v in session.items() if k not in READ_TIME_KEYS})


def _stored_plan(week: str) -> Optional[dict]:
    plan = (deps.load_state(UID).get("week_plans") or {}).get(week)
    return plan if plan is not None else storage.read_archived_week(UID, week)


def _find(plan: dict, day: str, sid: str) -> dict:
    for d in plan["weeks"][0]["days"]:
        if d["date"] == day:
            for s in d["sessions"]:
                if s.get("session_id") == sid:
                    return s
    raise AssertionError(f"{sid} not found on {day}")


def _insts(session: dict) -> list:
    return ((session.get("resolved") or {}).get("resolved_session") or {}).get("exercise_instances") or []


def _ladder_rows(session: dict) -> list:
    return [(i["exercise_id"], i["prescription"].get("sets"), i["prescription"].get("work_seconds"),
             i["prescription"].get("reps"))
            for i in _insts(session) if (i.get("prescription") or {}).get("source") == "bw_ladder"]


def _block(session: dict, block_id: str) -> Optional[dict]:
    return next((i for i in _insts(session) if (i.get("source") or {}).get("block_id") == block_id), None)


def _items(session: dict, label: Optional[str], *, guided: bool = True) -> list:
    """The feedback items a client builds from the resolved session: every row
    done (the guided player counts its sets), the ladder rows tagged."""
    out = []
    for inst in _insts(session):
        rx = inst.get("prescription") or {}
        item: Dict[str, Any] = {"exercise_id": inst["exercise_id"], "completed": True}
        if guided:
            item["completed_sets"] = int(rx.get("sets") or 1)
        if rx.get("source") == "bw_ladder":
            item["bw_ladder"] = "engine"
        if label:
            item["feedback_label"] = label
        out.append(item)
    return out


class Sim:
    """Runs the four weeks and records what each request returned."""

    def __init__(self, catalog: dict, range_calls: list):
        self.catalog = catalog
        self.range_calls = range_calls
        self.played: Dict[tuple, str] = {}  # (week, day, sid) → stored record
        self.shown: Dict[tuple, list] = {}  # (day, sid) → ladder rows of the GET view
        self.frozen: Dict[tuple, list] = {}  # (day, sid) → ladder rows of the stored record
        self.status: List[dict] = []  # key status / guard alerts, request by request
        self.levels: List[tuple] = []  # (day, bw_progression doses) after each played session
        self.lunches: List[dict] = []  # each played lunch: shown rows, label, doses before / after
        self.hiit_lateral: List[tuple] = []  # (lateral entry, HIIT lateral row)
        self.durations: List[tuple] = []  # (session day, lunch, minutes) of every lunch of every view
        self.view_durations: List[List[tuple]] = []  # the same, view by view
        self.reads_per_request: List[int] = []
        self.violations: List[str] = []

    # -- plumbing ---------------------------------------------------------

    def _request(self, fn, *args, **kwargs):
        before = len(self.range_calls)
        r = fn(*args, **kwargs)
        assert r.status_code == 200, r.text
        self.reads_per_request.append(len(self.range_calls) - before)
        self._check_played()
        return r.json()

    def _check_played(self) -> None:
        for (week, day, sid), want in self.played.items():
            got = _played(_find(_stored_plan(week), day, sid))
            if got != want:
                self.violations.append(f"{day} {sid} changed after it was played")

    def _record_played(self, week: str, day: str, sid: str) -> None:
        stored = _find(_stored_plan(week), day, sid)
        assert stored["status"] == "done"
        self.played[(week, day, sid)] = _played(stored)
        self.frozen[(day, sid)] = _ladder_rows(stored)

    @staticmethod
    def _doses() -> dict:
        bwp = deps.load_state(UID).get("bw_progression") or {}
        return {f: {k: e.get(k) for k in DOSE_KEYS} for f, e in bwp.items()
                if isinstance(e, dict) and "level_idx" in e}

    def get(self, k: int, day: str) -> dict:
        res = self._request(client.get, f"/api/week/{W0_NUM + k}", headers=HDR, params={"today": day})
        self.status.append({"req": f"GET {day}", "key_status": res.get("key_status"),
                            "guard_warnings": res.get("guard_warnings"),
                            "week_guard_warnings": res.get("week_guard_warnings")})
        plan = res["week_plan"]
        self.view_durations.append([])
        for d in plan["weeks"][0]["days"]:
            for s in d["sessions"]:
                if s.get("session_id") in lg.LUNCHES and s.get("resolved"):
                    rows = []
                    for inst in _insts(s):
                        rx = dict(inst["prescription"])
                        rx["alt_sides"] = bool(self.catalog[inst["exercise_id"]].get("alt_sides"))
                        rows.append(rx)
                    minutes = estimate_custom_session_duration(rows)
                    self.durations.append((d["date"], s["session_id"], minutes))
                    self.view_durations[-1].append((d["date"], s["session_id"], minutes))
        return plan

    def events_done(self, plan: dict, day: str, sid: str) -> dict:
        res = self._request(client.post, "/api/replanner/events", headers=HDR, json={
            "week_plan": plan, "today": day, "base_revision": plan.get("plan_revision"),
            "events": [{"event_type": "mark_done", "date": day, "session_ref": sid}]})
        self.status.append({"req": f"events {day} {sid}", "key_status": res.get("key_status"),
                            "guard_warnings": res.get("guard_warnings"),
                            "adjustments": res.get("adjustments"), "warnings": res.get("warnings"),
                            "auto_reschedules": res.get("auto_reschedules")})
        return res["week_plan"]

    def feedback(self, day: str, sid: str, items: list) -> None:
        self._request(client.post, "/api/feedback", headers=HDR, json={"log_entry": {
            "date": day, "session_id": sid, "feedback_contract": 2,
            "actual": {"exercise_feedback_v1": items}}})

    # -- the four weeks ---------------------------------------------------

    def run(self) -> None:
        deps.save_state(_state(), UID)
        storage.archive_week(UID, HISTORY_WEEK.isoformat(), _history_week())
        for k in range(WEEKS):
            week = W[k].isoformat()
            # The rollover: A221 moves what is older than the previous Monday
            # of the simulated date to the cold store.
            st = deps.load_state(UID)
            deps.archive_past_weeks(st, UID, from_date=W[k])
            deps.save_state(st, UID)
            for offset, sid, flow in (
                (0, ARMS, "guided:arms"), (1, HIIT, "mark_done"), (1, KEY_SESSION[PHASES[k]], "dialog"),
                (2, LEGS, "guided:none"), (4, PUSH, "guided:push"), (5, "finger_maintenance_home", "guided:ok"),
            ):
                if sid == "finger_maintenance_home" and PHASES[k] == "deload":
                    continue
                day = (W[k] + timedelta(days=offset)).isoformat()
                view = self.get(k, day)
                session = _find(view, day, sid)
                self.shown[(day, sid)] = _ladder_rows(session)
                before = self._doses()
                label = {"guided:arms": ARMS_LABELS[k], "guided:push": PUSH_LABELS[k],
                         "guided:ok": "ok"}.get(flow)
                if sid == HIIT:
                    lateral = (deps.load_state(UID).get("bw_progression") or {}).get("lateral")
                    self.hiit_lateral.append((dict(lateral or {}), _block(session, "core_lateral")))
                if flow == "mark_done":
                    self.events_done(view, day, sid)
                elif flow == "dialog":
                    after = self.events_done(view, day, sid)
                    self.feedback(day, sid, _items(_find(after, day, sid), "ok", guided=False))
                else:
                    self.feedback(day, sid, _items(session, label))
                self._record_played(week, day, sid)
                after = self._doses()
                self.levels.append((day, after))
                if sid in lg.LUNCHES:
                    self.lunches.append({"day": day, "sid": sid, "phase": PHASES[k], "label": label,
                                         "rows": self.shown[(day, sid)], "before": before, "after": after})
        # The whole span read once more: archived weeks served read-only.
        for k in range(WEEKS):
            self.get(k, (W[k] + timedelta(days=6)).isoformat())


@pytest.fixture(scope="module")
def catalog() -> dict:
    path = Path(golden.REPO_ROOT) / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


def _simulate(tmp_path_factory, catalog, *, baseline: bool) -> Sim:
    from backend.engine import storage_file

    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("b413_e2e_baseline" if baseline else "b413_e2e")
    mp.setattr(storage_file, "DATA_DIR", root)
    mp.setattr(storage_file, "USERS_DIR", root / "users")
    mp.delenv("STORAGE_REQUEST_MEMO", raising=False)
    mp.delenv("WEEKPLAN_ARCHIVE_LAZY", raising=False)
    calls: list = []
    wrapper = storage.read_archived_weeks_in_range
    real = wrapper.__wrapped__

    def counting(user_id, start, end, __real=real):
        calls.append(end)
        return __real(user_id, start, end)

    mp.setattr(wrapper, "__wrapped__", counting)
    if baseline:
        # Before B413 for the ladders: they never move, and the lunches keep
        # their catalog core.
        mp.setattr(bp, "apply_bw_item", lambda *a, **k: None)
        mp.setattr(rs, "_bw_ladder_pin_stage", lambda *a, **k: None)
    try:
        sim = Sim(catalog, calls)
        sim.run()
        sim.final_state = deps.load_state(UID)
        sim.archived = {wk: storage.read_archived_week(UID, wk)
                        for wk in storage.list_archived_keys(UID)}
    finally:
        mp.undo()
    return sim


@pytest.fixture(scope="module")
def sim(tmp_path_factory, catalog) -> Sim:
    return _simulate(tmp_path_factory, catalog, baseline=False)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory, catalog) -> Sim:
    return _simulate(tmp_path_factory, catalog, baseline=True)


def _day(k: int, offset: int) -> str:
    return (W[k] + timedelta(days=offset)).isoformat()


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def test_past_sessions_never_change(sim):
    """Every played session, hot or archived, byte for byte through every
    later request (GETs of every week, /events, /feedback, the A221 moves)."""
    assert sim.violations == []
    assert len(sim.played) == 6 * 3 + 5


def test_archived_weeks_are_the_played_weeks(sim):
    """A221 moved W0 and W1 (older than the previous Monday at W2 / W3) with
    their records untouched; W2 and W3 are hot."""
    assert set(sim.archived) == {HISTORY_WEEK.isoformat(), W[0].isoformat(), W[1].isoformat()}
    hot = set(sim.final_state["week_plans"])
    assert {W[2].isoformat(), W[3].isoformat()} <= hot and W[0].isoformat() not in hot


def test_the_record_is_the_prescription_shown(sim):
    """D2: the stored record of every played lunch is the ladder dose the GET
    showed — not the dose after the feedback moved the ladder."""
    lunches = [key for key in sim.frozen if key[1] in lg.LUNCHES]
    assert len(lunches) == 4 * WEEKS
    for key in lunches:
        assert sim.frozen[key] == sim.shown[key], key
        assert sim.frozen[key], key  # every lunch carries a ladder row


def test_rollout_seeds_from_the_archive_then_steps(sim):
    """D1 + D5: the rollout exists only in the archive (3x10 "ok" five weeks
    before): the HIIT of W0 shows the dose after it (3x11); marking it done
    without feedback counts as "ok" (A1) → 12, which the legs lunch shows."""
    assert ("ab_wheel_rollout", 3, None, 11) in sim.shown[(_day(0, 1), HIIT)]
    hiit = next(rec for rec in sim.lunches if rec["day"] == _day(0, 1))
    assert "rollout" not in hiit["before"]
    assert (hiit["after"]["rollout"]["exercise_id"], hiit["after"]["rollout"]["target"]) == ("ab_wheel_rollout", 12)
    assert ("ab_wheel_rollout", 3, None, 12) in sim.shown[(_day(0, 2), LEGS)]


def test_first_monday_follows_the_persisted_levels(sim):
    """W0 Monday, the arms lunch: his L-sit 4x10 s and Copenhagen dynamic 3x6
    (persisted levels, not the catalog hollow / side plank); "ok" adds one
    step to each — 4x15 s and 3x7."""
    assert sorted(sim.shown[(_day(0, 0), ARMS)]) == [("copenhagen_dynamic", 3, None, 6), ("core_l_sit", 4, 10, None)]
    after = sim.lunches[0]["after"]
    assert (after["compression_floor"]["target"], after["lateral"]["target"]) == (15, 7)


#: Steps of a done row by label (D5; None = no rating, counted as "ok", A1).
STEPS = {None: 1, "ok": 1, "easy": 2, "very_easy": 3}


def test_every_ladder_row_steps_from_the_dose_shown(sim):
    """Every ladder row of every played lunch, against the dose it showed:

    - a row at the athlete's own level, inside the band: the entry moves to
      shown + steps(label) × step (capped at the top), nothing else — "ok"
      +1, "easy" +2, no rating +1 (A1);
    - at the top of the band: it counts toward (or fires) the promotion —
      the level never goes down;
    - deload: nothing moves;
    - a row on another level (the HIIT lateral one level below, a walk-down
      on a block that cannot take the athlete's level): never moves the
      ladder."""
    checked = {"step": 0, "top": 0, "other": 0, "deload": 0}
    for rec in sim.lunches:
        for ex, _sets, secs, reps in rec["rows"]:
            fam, idx = bl.family_of(ex)
            before, after = rec["before"].get(fam), rec["after"][fam]
            if before is None:  # a seed (the rollout's first session): step-checked below
                continue
            value = secs if secs is not None else reps
            band = bp.family_doc(fam)["levels"][idx]["band"]
            if idx != before["level_idx"]:
                assert after == before, (rec["day"], rec["sid"], ex)
                checked["other"] += 1
            elif rec["phase"] == "deload":
                assert (after["level_idx"], after["target"]) == (before["level_idx"], before["target"]), rec["day"]
                checked["deload"] += 1
            elif value < band["hi"]:
                want = min(band["hi"], value + STEPS[rec["label"]] * band["step"])
                assert (after["level_idx"], after["target"]) == (idx, want), (rec["day"], rec["sid"], ex, rec["label"])
                checked["step"] += 1
            else:
                assert after["level_idx"] >= idx, (rec["day"], rec["sid"], ex)
                checked["top"] += 1
    assert checked["step"] >= 6 and checked["other"] >= WEEKS and checked["deload"] >= 2, checked


def test_promotions_fire_in_performance(sim):
    """D5: performance no longer freezes the ladders — a family promoted
    during W1-W2 (the L-sit at the top of its band after "easy" / no rating)."""
    perf = [rec for rec in sim.lunches if rec["phase"] == "performance"]
    assert any(rec["after"][f]["level_idx"] > rec["before"][f]["level_idx"]
               for rec in perf for f in rec["before"] if f in rec["after"])


def test_ladders_never_go_down_and_freeze_in_deload(sim):
    """No hard rating anywhere: no family ever loses a level or a step; in the
    deload week nothing goes up (the doses are frozen, one set fewer)."""
    prev: Dict[str, dict] = {}
    deload_start = W[3].isoformat()
    for day, doses in sim.levels:
        for fam, d in doses.items():
            p = prev.get(fam)
            if p is None:
                continue
            assert (d["level_idx"], d["target"] if d["level_idx"] == p["level_idx"] else 10**6) >= \
                (p["level_idx"], p["target"] if d["level_idx"] == p["level_idx"] else 0), (day, fam, p, d)
            if day >= deload_start:
                assert (d["level_idx"], d["target"]) == (p["level_idx"], p["target"]), (day, fam, p, d)
        prev = doses
    first, last = sim.levels[0][1], sim.levels[-1][1]
    assert any((last[f]["level_idx"], last[f]["target"]) != (first[f]["level_idx"], first[f]["target"])
               for f in first), "the ladders moved over the four weeks"
    # The deload lunches show one set fewer than the ladder dose.
    deload_arms = sim.shown[(_day(3, 0), ARMS)]
    lsit = last["compression_floor"]
    assert any(ex == lsit["exercise_id"] and sets == lsit["sets"] - 1 for ex, sets, _, _ in deload_arms), \
        deload_arms


def test_hiit_lateral_is_one_level_below(sim):
    """A2: on the Tuesday HIIT the lateral row is one level below the
    athlete's lateral level, at the top of that level's band, and it never
    moves the ladder (the Monday arms lunch moves it)."""
    fam = bp.family_doc("lateral")
    for entry, row in sim.hiit_lateral:
        below = max(0, int(entry["level_idx"]) - 1)
        level = fam["levels"][below]
        assert row["exercise_id"] == level["exercise_id"], (entry, row["exercise_id"])
        rx = row["prescription"]
        assert (rx.get("work_seconds") or rx.get("reps")) == level["band"]["hi"]
    # The lateral entry moves only on Mondays (the arms lunch).
    levels = sim.levels
    for (day, doses), (_, before) in zip(levels[1:], levels[:-1]):
        if date.fromisoformat(day).weekday() == 1:
            assert doses["lateral"] == before["lateral"], day


def test_lunches_fit_the_lunch_slot_at_the_starting_levels(sim):
    """The first view of the four weeks (W0 Monday: the persisted levels of
    2026-11-04 and the archive seed) — every lunch within 55'."""
    first = sim.view_durations[0]
    assert sorted(s for _, s, _ in first) == sorted(lg.LUNCHES)
    assert [(d, s, m) for d, s, m in first if m > 55] == []


def test_lunches_fit_the_lunch_slot_over_four_weeks(sim):
    """B413-LUNCH-55, Daniele 2026-11-04: with the ladders climbing the
    lunches reach 56-57' within two weeks, and a few minutes past 55' is
    accepted ("se scavalla di qualche minuto fa nulla"). The bound is 60'."""
    over = sorted({(d, s, m) for d, s, m in sim.durations if m > 60})
    assert over == []


def test_at_most_one_archive_read_per_request(sim):
    assert sim.reads_per_request and max(sim.reads_per_request) <= 1
    assert sum(sim.reads_per_request) > 0  # the archive was needed and read


def test_key_sessions_and_guards_unchanged(sim, baseline):
    """The key-session status and the guard alerts of every response are the
    same as in a run where the ladders never move and the lunches keep their
    catalog core: B413 touches no key session and no guard."""
    assert baseline.violations == []
    assert [s["req"] for s in sim.status] == [s["req"] for s in baseline.status]
    for got, want in zip(sim.status, baseline.status):
        assert _canon(got) == _canon(want), got["req"]
    assert any(s.get("key_status") for s in sim.status)


def test_loads_and_logs_unchanged_by_the_ladders(sim, baseline):
    """Working loads, the completion log and the limit log: the same as the
    baseline — the ladder pieces write only ``bw_progression``."""
    for key in ("working_loads", "limit_log", "test_queue"):
        assert _canon(sim.final_state.get(key)) == _canon(baseline.final_state.get(key)), key

    def log(st):  # completed_at is the server clock of the request
        return [{k: v for k, v in e.items() if k != "completed_at"} for e in st.get("session_completion_log") or []]

    assert log(sim.final_state) == log(baseline.final_state)
