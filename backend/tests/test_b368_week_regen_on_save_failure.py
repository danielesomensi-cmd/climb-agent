"""B368: a failed self-heal save must not regenerate the cached week.

2026-10-05 in production: a Supabase statement timeout hit the B216 resync
save inside the cache-read ``try`` of GET /api/week. The except branch read it
as "cache unreadable", regenerated the week from scratch (no old plan to
preserve from) and saved it over the user's custom and forced sessions.
"""

from __future__ import annotations

from backend.api import deps
from backend.api.routers import week as week_router
from backend.tests.test_week_rollover_B216 import (  # noqa: F401 (fixture)
    _make_week_plan,
    _prev_monday,
    _seed_rollover_state,
    _this_monday,
    client,
    isolate_state,
)


def test_failed_resync_save_serves_cached_plan(monkeypatch):
    this_mon = _this_monday()
    prev_mon = _prev_monday()
    cached = _make_week_plan(this_mon, session_id="custom_cs_forced")
    cached["weeks"][0]["days"][0]["sessions"][0]["is_custom"] = True
    _seed_rollover_state(
        legacy_start=prev_mon,  # stale legacy slot → the resync save fires
        week_plans={prev_mon: _make_week_plan(prev_mon, status="done"), this_mon: cached},
        mc_start=prev_mon,
    )

    calls = []
    orig_save = week_router.save_state

    def flaky_save(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("canceling statement due to statement timeout")
        return orig_save(*args, **kwargs)

    monkeypatch.setattr(week_router, "save_state", flaky_save)
    gen_calls = []
    orig_gen = week_router.generate_phase_week
    monkeypatch.setattr(
        week_router, "generate_phase_week",
        lambda *a, **k: gen_calls.append(True) or orig_gen(*a, **k),
    )

    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text
    assert gen_calls == [], "a failed resync save must not regenerate the week"
    served = r.json()["week_plan"]["weeks"][0]["days"][0]["sessions"]
    assert [s["session_id"] for s in served] == ["custom_cs_forced"]

    stored = deps.load_state(None)["week_plans"][this_mon]["weeks"][0]["days"][0]["sessions"]
    assert [s["session_id"] for s in stored] == ["custom_cs_forced"]
