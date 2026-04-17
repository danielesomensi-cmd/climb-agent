#!/usr/bin/env python3
"""
retrofit_coldstart_users.py — A-ACTIVATION-TIMING Day 4.

One-shot script that retrofits the `macrocycle.start_date` of every cold-start
user (= users with zero entries in `state.session_completion_log`) to the new
`this_monday()` semantics + T=1 fallback introduced in Day 2.

Why this exists
---------------
Users who signed up before 2026-04-17 had their macrocycle generated with
`next_monday()` — which parks them in a 3-7 day limbo before the first session
can happen. D-ANALYTICS-DROPOFF attributes the 75% stage-4 drop-off to this
limbo. The Day 2 backend fix only applies to new signups; this script brings
existing cold-start users onto the same fresh start.

Non-negotiables (from the brief, do not soften)
-----------------------------------------------
1. HARDCODED_EXCLUDE whitelist protects Daniele + Christie unconditionally.
2. Filter uses `state.session_completion_log`, NOT `public.session_logs`
   (that table is empty in prod — using it would match every user).
3. Operator must type "yes" at the start. Script is not idempotent.
4. Before any write, the full retrofit plan is printed with a 3-second
   countdown — last chance to CTRL-C.
5. Runs AFTER merge to main (backend must be redeployed so the new engine
   modules are committed upstream — we still import locally, but keeping
   the runtime & code in sync matters if anything fails).
6. No transaction / bulk rollback: each user is an independent write. A
   partial failure is acceptable; the remaining users are still correctly
   retrofitted and the failed one can be re-examined by hand.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Repo root + env -------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
if not (REPO_ROOT / "backend").is_dir():
    print(f"STOP: not in climb-agent repo (missing backend/ under {REPO_ROOT})")
    sys.exit(1)

sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")

_missing = [k for k, v in {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY,
}.items() if not v]
if _missing:
    print(f"STOP: missing env vars: {', '.join(_missing)}")
    sys.exit(1)

# --- Imports that depend on env being loaded -------------------------------

from supabase import create_client  # noqa: E402
import requests  # noqa: E402

from backend.api.deps import ensure_monday  # noqa: E402
from backend.engine.macrocycle_v1 import generate_macrocycle  # noqa: E402
from backend.engine.planner_v2 import generate_phase_week  # noqa: E402
from backend.engine.start_date_utils import (  # noqa: E402
    is_week_one_empty,
    strict_next_monday,
    this_monday,
)

# --- Hardcoded safety whitelist (non-negotiable) ---------------------------

HARDCODED_EXCLUDE = {
    "daniele.somensi@gmail.com",  # founder, active user
    "ckb.palmer@gmail.com",       # Christie, active beta
}

TODAY = date.today()

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# --- Clerk helpers ---------------------------------------------------------

def fetch_clerk_email_map() -> Dict[str, str]:
    """Return {clerk_id: email}. Empty dict if CLERK_SECRET_KEY is missing."""
    if not CLERK_SECRET_KEY:
        print("WARN: CLERK_SECRET_KEY missing — cannot resolve emails for the "
              "hardcoded whitelist. ABORTING to avoid retrofitting users whose "
              "email we can't verify.")
        sys.exit(1)
    out: Dict[str, str] = {}
    offset = 0
    limit = 100
    while True:
        resp = requests.get(
            "https://api.clerk.com/v1/users",
            headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
            params={"limit": limit, "offset": offset},
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for u in batch:
            emails = u.get("email_addresses") or []
            email = emails[0]["email_address"] if emails else ""
            out[u["id"]] = email.lower().strip()
        if len(batch) < limit:
            break
        offset += limit
    return out


# --- Cold-start detection --------------------------------------------------

def has_any_session_log(state: Dict[str, Any]) -> bool:
    """True iff state.session_completion_log is non-empty (any entry)."""
    log = state.get("session_completion_log")
    return isinstance(log, list) and len(log) > 0


def macrocycle_is_valid(state: Dict[str, Any]) -> bool:
    mc = state.get("macrocycle")
    if not isinstance(mc, dict):
        return False
    phases = mc.get("phases")
    if not isinstance(phases, list) or not phases:
        return False
    if not mc.get("start_date"):
        return False
    return True


def availability_is_usable(state: Dict[str, Any]) -> bool:
    avail = state.get("availability")
    if not isinstance(avail, dict) or not avail:
        return False
    # Must have at least one slot with "available": True somewhere.
    for day_obj in avail.values():
        if not isinstance(day_obj, dict):
            continue
        for slot in day_obj.values():
            if isinstance(slot, dict) and slot.get("available"):
                return True
    return False


# --- Core retrofit logic ---------------------------------------------------

def compute_new_start_date(state: Dict[str, Any]) -> Tuple[str, str]:
    """Run the Day 2 logic: this_monday(today), fallback to strict_next_monday
    if the planner would place zero sessions in Week 1.

    Returns (new_start_date, reason). reason is 'this_monday' or 'fallback'.
    """
    candidate = ensure_monday(this_monday(TODAY))
    # Regenerate probe macrocycle to test emptiness.
    probe_mc = _regen_macrocycle(state, candidate)
    if is_week_one_empty(state, probe_mc, TODAY):
        fallback = ensure_monday(strict_next_monday(TODAY))
        return fallback, "fallback"
    return candidate, "this_monday"


def _regen_macrocycle(state: Dict[str, Any], start_date: str) -> Dict[str, Any]:
    """Regenerate the macrocycle with the given start_date, preserving the
    original goal / profile / total_weeks from state."""
    goal = state.get("goal") or {}
    profile = (state.get("assessment") or {}).get("profile") or {}
    old_mc = state.get("macrocycle") or {}
    total_weeks = old_mc.get("total_weeks")
    if not isinstance(total_weeks, int) or total_weeks <= 0:
        discipline = goal.get("discipline", "lead")
        total_weeks = 10 if discipline == "boulder" else 12
    return generate_macrocycle(goal, profile, state, start_date, total_weeks)


def _regen_week_one(state: Dict[str, Any], mc: Dict[str, Any]) -> Dict[str, Any]:
    """Produce the week_plan for Week 1 of the newly-regenerated macrocycle.

    Does NOT mutate state.
    """
    phase1 = mc["phases"][0]
    equipment = state.get("equipment") or {}
    gyms = equipment.get("gyms") or []
    default_gym_id = gyms[0].get("gym_id") if gyms else None
    home_equipment = equipment.get("home") or []
    prefs = state.get("planning_prefs") or {}

    return generate_phase_week(
        phase_id=phase1["phase_id"],
        domain_weights=phase1.get("domain_weights") or {},
        session_pool=phase1.get("session_pool") or [],
        start_date=phase1.get("start_date") or mc["start_date"],
        availability=state.get("availability"),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=prefs.get("hard_day_cap_per_week", 3),
        planning_prefs=prefs,
        default_gym_id=default_gym_id,
        gyms=gyms,
        intensity_cap=phase1.get("intensity_cap"),
        home_equipment=home_equipment,
        today=TODAY.isoformat(),
        inject_tests=False,
        finger_device=(state.get("preferences") or {}).get("finger_training_device"),
        user_age=(state.get("body") or {}).get("age"),
    )


def retrofit_state(state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Apply the retrofit in-memory. Returns (new_state, audit_row).

    audit_row: {old_start, new_start, reason, delta_days, week1_session_count}
    """
    old_start = state["macrocycle"]["start_date"]
    new_start, reason = compute_new_start_date(state)

    new_mc = _regen_macrocycle(state, new_start)
    week1_plan = _regen_week_one(state, new_mc)

    new_state = dict(state)
    new_state["macrocycle"] = new_mc
    # Replace week_plans entirely: old cached plans reference a stale start_date.
    new_state["week_plans"] = {new_start: week1_plan}

    days = (week1_plan.get("weeks") or [{}])[0].get("days", [])
    n_sessions = sum(len(d.get("sessions") or []) for d in days)

    delta_days = (
        date.fromisoformat(new_start) - date.fromisoformat(old_start)
    ).days

    audit = {
        "old_start": old_start,
        "new_start": new_start,
        "reason": reason,
        "delta_days": delta_days,
        "week1_session_count": n_sessions,
    }
    return new_state, audit


# --- Main ------------------------------------------------------------------

def main() -> int:
    # Confirm gate (non-idempotent script)
    print("=" * 70)
    print("A-ACTIVATION-TIMING — cold-start user retrofit")
    print("=" * 70)
    print()
    print("This script mutates Supabase production data.")
    print("It is NOT idempotent: running it twice produces different week_plans.")
    print("There is no backup. Hardcoded whitelist protects Daniele + Christie.")
    print()
    confirm = input('Type "yes" to proceed: ').strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return 1
    print()

    print("Fetching Clerk email map…")
    clerk_emails = fetch_clerk_email_map()
    print(f"  {len(clerk_emails)} Clerk users fetched.")
    print()

    print("Fetching users from Supabase…")
    resp = sb.table("users").select("*").execute()
    all_users = resp.data or []
    print(f"  {len(all_users)} user rows fetched.")
    print()

    # Classify every user and build the retrofit plan.
    retrofit_plan: List[Dict[str, Any]] = []
    skipped: List[Tuple[str, str]] = []

    for u in all_users:
        uid = u.get("user_id") or ""
        if not uid or uid == "__legacy__":
            skipped.append((uid or "(none)", "synthetic/legacy row"))
            continue

        state = u.get("state") or {}
        if not isinstance(state, dict):
            skipped.append((uid, "state not a dict"))
            continue

        clerk_id = u.get("clerk_id") or ""
        email = clerk_emails.get(clerk_id, "") if clerk_id else ""

        # Gate 1: hardcoded whitelist
        if email in HARDCODED_EXCLUDE:
            skipped.append((f"{email} ({uid[:8]})", "whitelist"))
            continue

        # Gate 2: has any session completion log entry
        if has_any_session_log(state):
            n = len(state.get("session_completion_log") or [])
            skipped.append((f"{email or uid[:8]}", f"has {n} session_completion_log entries"))
            continue

        # Gate 3: macrocycle present & well-formed
        if not macrocycle_is_valid(state):
            skipped.append((f"{email or uid[:8]}", "macrocycle missing or malformed"))
            continue

        # Gate 4: availability usable
        if not availability_is_usable(state):
            skipped.append((f"{email or uid[:8]}", "availability empty/unusable"))
            continue

        # Candidate — compute the new start_date (probe only, no write yet).
        try:
            new_start, reason = compute_new_start_date(state)
        except Exception as e:
            skipped.append((f"{email or uid[:8]}", f"compute_new_start_date failed: {e}"))
            continue

        old_start = state["macrocycle"]["start_date"]
        delta_days = (date.fromisoformat(new_start) - date.fromisoformat(old_start)).days

        retrofit_plan.append({
            "uid": uid,
            "email": email or "(no email)",
            "old_start": old_start,
            "new_start": new_start,
            "reason": reason,
            "delta_days": delta_days,
            "state": state,  # keep ref for the write pass
        })

    # Print the plan.
    print("=" * 70)
    print(f"RETROFIT PLAN — {len(retrofit_plan)} user(s) will be modified")
    print("=" * 70)
    if not retrofit_plan:
        print("  (nothing to retrofit — all users skipped)")
    else:
        print(f"  {'Email':35s} {'UID':12s} {'Old':12s} {'New':12s} {'Δ':>4s}  Reason")
        for row in retrofit_plan:
            print(
                f"  {row['email']:35s} {row['uid'][:8]:12s} "
                f"{row['old_start']:12s} {row['new_start']:12s} "
                f"{row['delta_days']:+4d}  {row['reason']}"
            )
    print()

    print(f"SKIPPED — {len(skipped)} user(s)")
    for who, why in skipped:
        print(f"  - {who}: {why}")
    print()

    if not retrofit_plan:
        print("Nothing to do. Exiting.")
        return 0

    # Last-chance countdown.
    print(f"Retrofitting {len(retrofit_plan)} user(s) in 3...", flush=True)
    time.sleep(1)
    print("2...", flush=True)
    time.sleep(1)
    print("1...", flush=True)
    time.sleep(1)
    print("applying now.")
    print()

    # Apply.
    success = 0
    failed: List[Tuple[str, str]] = []
    for row in retrofit_plan:
        uid = row["uid"]
        email = row["email"]
        try:
            new_state, audit = retrofit_state(row["state"])
            sb.table("users").update({"state": new_state}).eq("user_id", uid).execute()
            success += 1
            print(
                f"  ✓ {email:35s} {row['old_start']} → {audit['new_start']} "
                f"({audit['reason']}, Δ{audit['delta_days']:+d}d, "
                f"week1={audit['week1_session_count']} sessions)"
            )
        except Exception as e:
            failed.append((email, str(e)))
            print(f"  ✗ {email}: {e}")

    print()
    print("=" * 70)
    print(f"DONE — {success} retrofitted, {len(failed)} failed, {len(skipped)} skipped")
    print("=" * 70)
    if failed:
        print("Failed users — inspect by hand:")
        for who, why in failed:
            print(f"  - {who}: {why}")
    print()
    print("Next: run `python scripts/diagnose_dropoff.py` to verify stage "
          "distribution and updated start dates.")
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
