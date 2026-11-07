"""B414 (step 20) — BODY-PART-PICKER-NONDETERMINISM.

The body-part generator was not deterministic:
  - across processes: the candidate list walked a ``set`` of string ids, whose
    order follows ``PYTHONHASHSEED``, and the seeded jitter was drawn in that
    order — same seed, same catalog, a different pick in every process;
  - in prod, between preview and start: the app never sends a ``seed``, so
    ``random.Random(None)`` drew system entropy and /start inserted a session
    other than the one the preview showed;
  - and the index kept ``active: false`` exercises (``max_hang_10s``).

Now the candidates are walked sorted, a request without seed is seeded from
its day + body parts + equipment mode + gym (the day comes from the router,
never from a clock in the engine), and inactive exercises leave the index.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.engine.body_part_picker import (
    BODY_PART_ORDER,
    build_body_part_index,
    generate_body_part_session,
    request_seed,
    select_exercises_for_part,
)

REPO = Path(__file__).resolve().parents[2]
EXERCISES = REPO / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
DAY = "2026-11-09"


def _catalog():
    return json.loads(EXERCISES.read_text(encoding="utf-8"))["exercises"]


def _state():
    """A state with one done session in a past week, so the recency source is
    the plan (never the legacy log fallback) and a real penalty applies."""
    return {
        "equipment": {
            "home": ["dumbbell", "pullup_bar", "hangboard", "resistance_band"],
            "gyms": [{"gym_id": "g1", "name": "Gym", "equipment": ["barbell", "dumbbell", "pullup_bar",
                                                                    "hangboard", "cable_machine", "bench"]}],
        },
        "week_plans": {
            "2026-11-02": {"weeks": [{"days": [{"date": "2026-11-03", "sessions": [{
                "session_id": "strength_long", "status": "done",
                "resolved": {"resolved_session": {"exercise_instances": [
                    {"exercise_id": "hollow_body_hold"}, {"exercise_id": "pullup"}]}},
            }]}]}]},
        },
    }


_SNIPPET = r"""
import json, sys
from backend.engine.body_part_picker import BODY_PART_ORDER, generate_body_part_session, select_exercises_for_part
from backend.tests.test_b414_body_part_picker_determinism import _catalog, _state, DAY
cat = _catalog()
out = {}
for part in BODY_PART_ORDER:
    for mode, gid in (("all", None), ("home", None), ("gym", "g1"), ("bodyweight", None)):
        for seed in (42, None):
            s = generate_body_part_session([part], mode, gid, _state(), cat, seed=seed, today=DAY)
            out[f"gen|{part}|{mode}|{seed}"] = [e["exercise_id"] for e in s["exercises"]]
    picks = select_exercises_for_part(part, cat, ["dumbbell", "pullup_bar", "hangboard", "barbell"],
                                      set(), _state(), seed=7, today=DAY)
    out[f"sel|{part}"] = [e["id"] for e in picks]
s = generate_body_part_session(["core", "legs", "fingers"], "all", None, _state(), cat, today=DAY)
out["gen|multi"] = [e["exercise_id"] for e in s["exercises"]]
json.dump(out, sys.stdout, sort_keys=True)
"""


def _run(hashseed: str) -> dict:
    env = dict(os.environ, PYTHONHASHSEED=hashseed, STORAGE_BACKEND="file", PYTHONPATH=str(REPO))
    r = subprocess.run([sys.executable, "-c", _SNIPPET], cwd=str(REPO), env=env,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_same_pick_whatever_the_hash_seed():
    """The bug: PYTHONHASHSEED 0/1/2/3 gave 4 different outputs on all 11 body
    parts. Now two processes with different hash seeds agree on every pick —
    with an explicit seed, without one, and for the bare selection."""
    a = _run("0")
    b = _run("1")
    assert a.keys() == b.keys()
    diff = [k for k in a if a[k] != b[k]]
    assert diff == [], f"pick changed with PYTHONHASHSEED: {diff[:10]}"
    assert any(a[k] for k in a if k.startswith("sel|"))


def test_no_seed_is_stable_and_follows_the_day():
    cat = _catalog()
    one = generate_body_part_session(["core", "back_pulling"], "all", None, _state(), cat, today=DAY)
    two = generate_body_part_session(["core", "back_pulling"], "all", None, _state(), cat, today=DAY)
    assert [e["exercise_id"] for e in one["exercises"]] == [e["exercise_id"] for e in two["exercises"]]
    # The seed is the request's: same day + parts + mode + gym → same seed,
    # a different day (or different parts / mode / gym) → a different one.
    base = request_seed(DAY, ["core"], "all", None)
    assert base == request_seed(DAY, ["core"], "all", None)
    assert base != request_seed("2026-11-10", ["core"], "all", None)
    assert base != request_seed(DAY, ["legs"], "all", None)
    assert base != request_seed(DAY, ["core"], "gym", "g1")
    # A missing seed behaves exactly as passing the derived one.
    explicit = generate_body_part_session(["core", "back_pulling"], "all", None, _state(), cat,
                                          seed=request_seed(DAY, ["core", "back_pulling"], "all", None),
                                          today=DAY)
    assert [e["exercise_id"] for e in explicit["exercises"]] == [e["exercise_id"] for e in one["exercises"]]


def test_inactive_exercise_never_indexed_nor_picked():
    cat = _catalog()
    inactive = {e["id"] for e in cat if e.get("active") is False}
    assert "max_hang_10s" in inactive
    idx = build_body_part_index(cat)
    assert not (set().union(*idx.values()) & inactive)
    # 300 seeds on fingers with a hangboard: max_hang_10s used to come out ~49 times.
    for seed in range(300):
        picks = select_exercises_for_part("fingers", cat, ["hangboard", "pullup_bar"], set(), {}, seed=seed,
                                          today=DAY)
        assert not ({p["id"] for p in picks} & inactive)
    # Synthetic: the same exercise flipped to inactive leaves the index.
    flipped = [dict(e, active=False) if e["id"] == "bicep_curl" else e for e in cat]
    assert "bicep_curl" in set().union(*build_body_part_index(cat).values())
    assert "bicep_curl" not in set().union(*build_body_part_index(flipped).values())


# ── API: the preview is the session /start inserts ───────────────────────


@pytest.fixture()
def client():
    from backend.api.main import app

    c = TestClient(app)
    c.delete("/api/state")
    yield c
    c.delete("/api/state")


def _seed_week(c):
    days = [f"2026-11-{9 + i:02d}" for i in range(7)]
    wd = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    plan = {"start_date": "2026-11-09",
            "weeks": [{"days": [{"date": days[i], "weekday": wd[i], "sessions": []} for i in range(7)]}]}
    c.put("/api/state", json={"current_week_plan": plan,
                              "equipment": {"home": ["dumbbell", "pullup_bar", "hangboard"], "gyms": []}})


def test_preview_equals_start_without_seed(client):
    """The app sends no seed: preview twice and start, same day → the same
    exercises every time (before, each call drew system entropy)."""
    _seed_week(client)
    body = {"body_parts": ["core", "back_pulling", "fingers"], "equipment_mode": "home",
            "target_date": "2026-11-11"}
    p1 = client.post("/api/body-part-picker/preview", json=body)
    p2 = client.post("/api/body-part-picker/preview", json=body)
    assert p1.status_code == 200 and p2.status_code == 200
    ids1 = [e["exercise_id"] for e in p1.json()["exercises"]]
    assert ids1 == [e["exercise_id"] for e in p2.json()["exercises"]]
    st = client.post("/api/body-part-picker/start", json=dict(body, slot="evening", location="home"))
    assert st.status_code == 200, st.text
    assert [e["exercise_id"] for e in st.json()["session"]["exercises"]] == ids1


def test_preview_without_target_date_is_still_stable(client):
    """A client that omits target_date gets the server date from the router —
    still one seed per request, no entropy."""
    body = {"body_parts": ["core"], "equipment_mode": "bodyweight"}
    a = client.post("/api/body-part-picker/preview", json=body).json()
    b = client.post("/api/body-part-picker/preview", json=body).json()
    assert [e["exercise_id"] for e in a["exercises"]] == [e["exercise_id"] for e in b["exercises"]]
