"""B-fix-CORE: resolve_session must read target_date fallback from user_ctx.

Audit D (Tyler Twist) found that `_auto_resolve` in week.py / replanner.py
builds the resolve context with only `location` + `gym_id`, never injecting
`target_date`. Consequence: `inject_targets` ran with `out["date"]=""`, the
freshness check in `_best_entry` failed for every working_loads entry, and
all `external_load` exercises silently fell back to `FIXED_KG` / `BW%`.

The fix:
  1. Patch A — _auto_resolve injects target_date into resolve_state["context"].
  2. Patch B — resolve_session falls back to user_ctx.target_date when
     session_ctx.target_date is missing (mirrors the existing gym_id pattern).

These tests pin Patch B at the resolver level — independent of any caller.

B274 note: selection inside prehab blocks rotates weekly (variety tie-break),
so these tests no longer hardcode WHICH exercise gets picked. They resolve
once to discover the selected external_load exercise, then attach the
working_loads entry to that id (discover-then-assert) — the intent under test
is the freshness plumbing, not the tie-break winner.
"""
from __future__ import annotations

from pathlib import Path

from backend.engine.progression_v1 import EXTERNAL_LOAD_FALLBACK_FIXED_KG
from backend.engine.resolve_session import resolve_session

REPO_ROOT = str(Path(__file__).resolve().parents[2])

SESSION_PATH = "backend/catalog/sessions/v1/prehab_maintenance.json"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"
WL_NEXT_KG = 5.0


def _user_state(context: dict, wl_ex_id: str | None = None, updated_at: str = "2026-04-30") -> dict:
    """Minimal user_state; optionally with a working_loads entry for wl_ex_id."""
    entries = []
    if wl_ex_id:
        entries.append(
            {
                "exercise_id": wl_ex_id,
                "key": wl_ex_id,
                "setup": {},
                "last_external_load_kg": WL_NEXT_KG,
                "next_external_load_kg": WL_NEXT_KG,
                "last_feedback_label": "ok",
                "last_completed": True,
                "updated_at": updated_at,
            }
        )
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 70.0,
        "baselines": {"hangboard": [{"max_total_load_kg": 95.0}]},
        "assessment": {
            "grades": {
                "boulder_max_os": "6C",
                "boulder_max_rp": "7A",
                "lead_max_rp": "7a",
            },
        },
        "equipment": {"home": ["weight"], "gyms": []},
        "working_loads": {"entries": entries, "rules": {}},
        "context": context,
    }


def _resolve(us: dict) -> dict:
    return resolve_session(
        repo_root=REPO_ROOT,
        session_path=SESSION_PATH,
        templates_dir=TEMPLATES_DIR,
        exercises_path=EXERCISES_PATH,
        out_path="",
        user_state_override=us,
        write_output=False,
    )


def _suggested_load(resolved: dict, exercise_id: str) -> float | None:
    instances = resolved["resolved_session"]["exercise_instances"]
    for inst in instances:
        if inst.get("exercise_id") == exercise_id:
            return (inst.get("suggested") or {}).get("suggested_external_load_kg")
    return None


def _discover_loadable_ex(context: dict) -> str:
    """Resolve WITHOUT working_loads and return the selected exercise that has
    a FIXED_KG fallback (external_load). Selection is independent of
    working_loads, so a second resolve with the same context picks it again."""
    resolved = _resolve(_user_state(context))
    for inst in resolved["resolved_session"]["exercise_instances"]:
        eid = inst.get("exercise_id")
        if eid in EXTERNAL_LOAD_FALLBACK_FIXED_KG:
            return eid
    raise AssertionError(
        "prehab_maintenance selected no external_load exercise — fixture broken"
    )


def test_user_ctx_target_date_unlocks_working_loads():
    """user_ctx.target_date is honored when session_ctx has no date."""
    ctx = {"location": "home", "gym_id": None, "target_date": "2026-05-04"}
    ex_id = _discover_loadable_ex(ctx)

    # fresh: updated_at 4 days before target_date
    load = _suggested_load(_resolve(_user_state(ctx, ex_id, "2026-04-30")), ex_id)
    assert load == WL_NEXT_KG, (
        f"Expected working_loads value {WL_NEXT_KG} kg with fresh user_ctx.target_date, "
        f"got {load} (FIXED_KG fallback would be "
        f"{EXTERNAL_LOAD_FALLBACK_FIXED_KG[ex_id]})"
    )


def test_user_ctx_date_alias_also_works():
    """Resolver accepts user_ctx.date as an alias for target_date."""
    ctx = {"location": "home", "gym_id": None, "date": "2026-05-04"}
    ex_id = _discover_loadable_ex(ctx)

    load = _suggested_load(_resolve(_user_state(ctx, ex_id, "2026-04-30")), ex_id)
    assert load == WL_NEXT_KG


def test_no_date_anywhere_keeps_legacy_fallback():
    """Patch B is additive: no date provided anywhere → fallback path preserved.

    This is the pre-fix behavior. Existing tests rely on it (they assert
    presence of `suggested_external_load_kg`, never the value), so we must
    keep the fallback intact when the caller genuinely has no date to share.
    """
    ctx = {"location": "home", "gym_id": None}  # no date at all
    ex_id = _discover_loadable_ex(ctx)

    load = _suggested_load(_resolve(_user_state(ctx, ex_id, "2026-04-30")), ex_id)
    fallback = EXTERNAL_LOAD_FALLBACK_FIXED_KG[ex_id]
    assert load == fallback, (
        f"Without any date, resolver must fall back to FIXED_KG[{fallback}], got {load}"
    )


def test_stale_working_loads_falls_back():
    """Entry older than 60 days from target_date → still considered stale → fallback.

    The 60-day staleness gate in `_is_fresh` is the legitimate guard rail.
    Patch B unblocks reading the entry, but the stale entry must still be rejected.
    """
    ctx = {"location": "home", "gym_id": None, "target_date": "2026-05-04"}
    ex_id = _discover_loadable_ex(ctx)

    # 123 days before target_date — stale
    load = _suggested_load(_resolve(_user_state(ctx, ex_id, "2026-01-01")), ex_id)
    fallback = EXTERNAL_LOAD_FALLBACK_FIXED_KG[ex_id]
    assert load == fallback, (
        f"Stale entry (>60d) must trigger FIXED_KG[{fallback}] fallback, got {load}"
    )
