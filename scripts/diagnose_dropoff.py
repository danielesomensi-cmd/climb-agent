#!/usr/bin/env python3
"""
diagnose_dropoff.py — D-ANALYTICS-DROPOFF funnel diagnosis.

READ-ONLY audit: classifies every registered user into a funnel stage to see
where the 7 inactive users stopped. Zero writes to Supabase or Clerk.

Usage:
    source .venv/bin/activate
    python scripts/diagnose_dropoff.py

Requires in .env (already present, do not modify):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    CLERK_SECRET_KEY   (optional: used to resolve name/email; script degrades gracefully)
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Preflight 1: cwd check
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
if not (REPO_ROOT / "backend").is_dir() or not (REPO_ROOT / "frontend").is_dir():
    print(f"STOP: not in climb-agent repo (missing backend/ or frontend/ under {REPO_ROOT})")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Preflight 2: env vars
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # env vars may be exported externally

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

# ---------------------------------------------------------------------------
# Imports after env check
# ---------------------------------------------------------------------------

try:
    from supabase import create_client
except ImportError:
    print("STOP: supabase-py not installed. Run: pip install supabase")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("STOP: requests not installed. Run: pip install requests")
    sys.exit(1)


sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Known founder UUID (CLAUDE.md memory)
DANIELE_UUID = "7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e"
DANIELE_EMAIL = "daniele.somensi@gmail.com"
CHRISTIE_EMAIL = "ckb.palmer@gmail.com"

TODAY = datetime.now(tz=timezone.utc).date()


# ---------------------------------------------------------------------------
# Phase 0 — Schema autodiscovery
# ---------------------------------------------------------------------------

def probe_schema(table: str) -> tuple[list[str], int]:
    """
    Probe a table by selecting the first row and returning its column names
    + total row count. PostgREST does not expose information_schema directly,
    so this is the portable read-only approach.
    """
    # Get a single row to inspect column names
    row_resp = sb.table(table).select("*").limit(1).execute()
    columns = sorted(row_resp.data[0].keys()) if row_resp.data else []

    # Get count via head=True (no data transferred, count='exact')
    count_resp = sb.table(table).select("user_id", count="exact").execute() \
        if columns and "user_id" in columns else sb.table(table).select("*", count="exact").execute()
    total = count_resp.count if count_resp.count is not None else len(count_resp.data or [])

    return columns, total


def print_schemas() -> dict[str, list[str]]:
    """Print schemas and return {table: [columns]}."""
    print("=" * 70)
    print("PHASE 0 — SCHEMA AUTODISCOVERY")
    print("=" * 70)
    schemas: dict[str, list[str]] = {}
    for table in ("users", "session_logs", "subscriptions"):
        try:
            cols, cnt = probe_schema(table)
            schemas[table] = cols
            print(f"\n{table}  (rows={cnt})")
            if cols:
                for c in cols:
                    print(f"  - {c}")
            else:
                print("  (empty — column list unknown)")
        except Exception as e:
            print(f"\n{table}  ERROR: {e}")
            schemas[table] = []
    print()
    return schemas


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def fetch_all_users() -> list[dict]:
    """Fetch every row from public.users."""
    # Paginate defensively in case of >1000 users (currently ~9, trivial)
    resp = sb.table("users").select("*").execute()
    return resp.data or []


def fetch_session_counts_from_logs() -> dict[str, tuple[int, str | None]]:
    """
    Legacy path: aggregate from public.session_logs.
    In current production this table appears to be empty — sessions live in
    users.state.session_completion_log. Kept for completeness/diagnostic.
    """
    resp = sb.table("session_logs").select("user_id, log_date").execute()
    rows = resp.data or []
    by_user: dict[str, list[str]] = {}
    for r in rows:
        uid = r.get("user_id") or ""
        dt = r.get("log_date")
        by_user.setdefault(uid, []).append(dt)
    out: dict[str, tuple[int, str | None]] = {}
    for uid, dates in by_user.items():
        clean = [d for d in dates if d]
        out[uid] = (len(clean) or len(dates), max(clean) if clean else None)
    return out


def session_counts_from_state(state: dict | None) -> tuple[int, str | None]:
    """
    Authoritative count: number of entries in state.session_completion_log
    with status=='done'. Returns (count, last_iso_date_or_None).
    """
    if not isinstance(state, dict):
        return (0, None)
    log = state.get("session_completion_log") or []
    if not isinstance(log, list):
        return (0, None)
    dates: list[str] = []
    count = 0
    for entry in log:
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "done":
            continue
        count += 1
        # Prefer explicit date field, fall back to completed_at
        d = entry.get("date") or entry.get("completed_at") or ""
        if isinstance(d, str) and d:
            dates.append(d[:10])
    last = max(dates) if dates else None
    return (count, last)


def fetch_subscriptions() -> dict[str, dict]:
    """Returns {user_id: subscription_row}."""
    resp = sb.table("subscriptions").select("*").execute()
    return {r["user_id"]: r for r in (resp.data or []) if r.get("user_id")}


def fetch_clerk_users() -> dict[str, dict]:
    """
    Returns {clerk_id: {email, name}} or {} if CLERK_SECRET_KEY missing.
    """
    if not CLERK_SECRET_KEY:
        return {}
    users: dict[str, dict] = {}
    offset = 0
    limit = 100
    while True:
        try:
            resp = requests.get(
                "https://api.clerk.com/v1/users",
                headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
                params={"limit": limit, "offset": offset},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"WARN: Clerk fetch failed ({e}); continuing without name/email")
            return users
        batch = resp.json()
        if not batch:
            break
        for u in batch:
            emails = u.get("email_addresses") or []
            email = emails[0]["email_address"] if emails else ""
            first = (u.get("first_name") or "").strip()
            last = (u.get("last_name") or "").strip()
            name = f"{first} {last}".strip() or "—"
            users[u["id"]] = {"email": email, "name": name}
        if len(batch) < limit:
            break
        offset += limit
    return users


# ---------------------------------------------------------------------------
# Phase 1 — Staging
# ---------------------------------------------------------------------------

def compute_stage(state: dict | None, has_sub: bool, n_sessions: int) -> str:
    """Return the highest stage reached by a user."""
    if n_sessions >= 1:
        return "6_ACTIVE"
    if has_sub:
        return "5_HAS_SUB"
    if not state:
        return "1_SIGNUP_ONLY"
    week_plans = state.get("week_plans")
    if isinstance(week_plans, dict) and week_plans:
        return "4_HAS_WEEK_PLANS"
    mc = state.get("macrocycle") or {}
    phases = mc.get("phases") if isinstance(mc, dict) else None
    if isinstance(phases, list) and phases:
        return "3_HAS_MACROCYCLE"
    assessment = state.get("assessment") or {}
    profile = assessment.get("profile") if isinstance(assessment, dict) else None
    if profile:
        return "2_HAS_ASSESSMENT"
    return "1_SIGNUP_ONLY"


def parse_iso_date(ts: str | None):
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        try:
            return datetime.strptime(ts[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None


def stage_users(
    users: list[dict],
    session_logs_counts: dict[str, tuple[int, str | None]],
    subs: dict[str, dict],
    clerk: dict[str, dict],
) -> list[dict]:
    """Produce one row per user with all staging fields.

    n_sessions is computed from state.session_completion_log (authoritative),
    NOT from public.session_logs (which is empty in prod — see diagnostic).
    """
    rows: list[dict] = []
    for u in users:
        uid = u.get("user_id") or ""
        if not uid or uid == "__legacy__":
            continue
        clerk_id = u.get("clerk_id") or ""
        state = u.get("state") or {}
        clerk_info = clerk.get(clerk_id, {})
        email = clerk_info.get("email", "")
        clerk_name = clerk_info.get("name", "")
        name_in_state = ""
        if isinstance(state, dict):
            profile = state.get("profile") or {}
            if isinstance(profile, dict):
                name_in_state = profile.get("name") or ""

        # Authoritative session count from JSONB state
        n_sessions, last_log = session_counts_from_state(state if isinstance(state, dict) else None)
        # Shadow count from session_logs table (for divergence diagnostic)
        n_logs_table, _ = session_logs_counts.get(uid, (0, None))
        sub = subs.get(uid)
        stage = compute_stage(state if isinstance(state, dict) else None, sub is not None, n_sessions)

        created_raw = u.get("created_at")
        created_dt = parse_iso_date(created_raw)
        signup_date = created_dt.date().isoformat() if created_dt else "—"
        days_since_signup = (TODAY - created_dt.date()).days if created_dt else None

        rows.append({
            "user_id": uid,
            "clerk_id": clerk_id,
            "email": email or "—",
            "name": clerk_name or name_in_state or "—",
            "name_in_state": name_in_state,
            "stage": stage,
            "n_sessions": n_sessions,
            "n_session_logs_table": n_logs_table,
            "last_session_date": last_log or "—",
            "sub_status": sub.get("status") if sub else "—",
            "trial_end": sub.get("trial_end") if sub else "—",
            "signup_date": signup_date,
            "days_since_signup": days_since_signup if days_since_signup is not None else "—",
        })
    return rows


# ---------------------------------------------------------------------------
# Validation gate
# ---------------------------------------------------------------------------

def validate_join(rows: list[dict]) -> bool:
    """
    Confirm Daniele ~30 sessions and Christie ~9 sessions.
    Returns True if both within ±3 of expected; prints diagnostics either way.
    """
    print("=" * 70)
    print("VALIDATION GATE — expected: Daniele≈30, Christie≈9 sessions")
    print("=" * 70)

    daniele = next((r for r in rows if r["user_id"] == DANIELE_UUID), None)
    if not daniele:
        daniele = next((r for r in rows if r["email"] == DANIELE_EMAIL), None)
    christie = next((r for r in rows if r["email"] == CHRISTIE_EMAIL), None)

    ok = True
    if not daniele:
        print(f"✗ Daniele NOT FOUND (searched uuid={DANIELE_UUID}, email={DANIELE_EMAIL})")
        ok = False
    else:
        delta_d = abs(daniele["n_sessions"] - 30)
        status = "✓" if delta_d <= 3 else "✗"
        print(f"{status} Daniele: n_sessions={daniele['n_sessions']} (expected 30, Δ={delta_d})")
        if delta_d > 3:
            ok = False

    if not christie:
        print(f"✗ Christie NOT FOUND (email={CHRISTIE_EMAIL})")
        ok = False
    else:
        delta_c = abs(christie["n_sessions"] - 9)
        status = "✓" if delta_c <= 3 else "✗"
        print(f"{status} Christie: n_sessions={christie['n_sessions']} (expected 9, Δ={delta_c})")
        if delta_c > 3:
            ok = False

    print()
    return ok


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

STAGE_ORDER = [
    "1_SIGNUP_ONLY",
    "2_HAS_ASSESSMENT",
    "3_HAS_MACROCYCLE",
    "4_HAS_WEEK_PLANS",
    "5_HAS_SUB",
    "6_ACTIVE",
]


def print_detail_table(rows: list[dict]) -> None:
    # Exclude Daniele (founder) from drop-off table
    filtered = [r for r in rows if r["user_id"] != DANIELE_UUID and r["email"] != DANIELE_EMAIL]

    def sort_key(r):
        stage_idx = STAGE_ORDER.index(r["stage"]) if r["stage"] in STAGE_ORDER else 99
        # Days DESC: negate so higher days appear first after ascending sort
        days = r["days_since_signup"]
        days_val = -days if isinstance(days, int) else 0
        return (stage_idx, days_val)

    filtered.sort(key=sort_key)

    print("=" * 70)
    print("DETAIL TABLE (excluding founder)")
    print("=" * 70)
    print()
    print("| Email | Name | Stage | Sessions (state) | Sessions (logs) | Last Session | Sub Status | Days Since Signup |")
    print("|-------|------|-------|------------------|-----------------|--------------|------------|-------------------|")
    for r in filtered:
        print(
            f"| {r['email']} | {r['name']} | {r['stage']} | {r['n_sessions']} "
            f"| {r['n_session_logs_table']} | {r['last_session_date']} "
            f"| {r['sub_status']} | {r['days_since_signup']} |"
        )
    print()


def print_summary(rows: list[dict]) -> Counter:
    filtered = [r for r in rows if r["user_id"] != DANIELE_UUID and r["email"] != DANIELE_EMAIL]
    dist = Counter(r["stage"] for r in filtered)
    print("=" * 70)
    print("STAGE DISTRIBUTION  (excluding founder)")
    print("=" * 70)
    for s in STAGE_ORDER:
        print(f"  {s:20s} {dist.get(s, 0)} users")
    print(f"  {'-'*18}")
    print(f"  {'TOTAL':20s} {sum(dist.values())} users")
    print()
    return dist


def print_diagnostic(dist: Counter) -> None:
    total = sum(dist.values())
    if total == 0:
        print("DIAGNOSTIC: no non-founder users to analyze.")
        return

    def pct(s: str) -> float:
        return 100.0 * dist.get(s, 0) / total if total else 0.0

    # Classify buckets
    pre_plan = dist.get("1_SIGNUP_ONLY", 0) + dist.get("2_HAS_ASSESSMENT", 0)
    post_plan_no_sub = dist.get("3_HAS_MACROCYCLE", 0) + dist.get("4_HAS_WEEK_PLANS", 0)
    paywalled = dist.get("5_HAS_SUB", 0)
    active = dist.get("6_ACTIVE", 0)

    print("=" * 70)
    print("DIAGNOSTIC INTERPRETATION")
    print("=" * 70)
    print()
    print(f"Pre-plan drop-off (stages 1-2):       {pre_plan} users ({pct('1_SIGNUP_ONLY')+pct('2_HAS_ASSESSMENT'):.0f}%)")
    print(f"Post-plan no-session (stages 3-4):    {post_plan_no_sub} users ({pct('3_HAS_MACROCYCLE')+pct('4_HAS_WEEK_PLANS'):.0f}%)")
    print(f"Has subscription, never logged (5):   {paywalled} users ({pct('5_HAS_SUB'):.0f}%)")
    print(f"Active (stage 6):                     {active} users ({pct('6_ACTIVE'):.0f}%)")
    print()

    dominant_modes: list[str] = []
    if pre_plan >= post_plan_no_sub and pre_plan >= paywalled and pre_plan > 0:
        dominant_modes.append(
            "• Onboarding abandonment — users sign up but never finish assessment/macrocycle. "
            "Investigate onboarding funnel (step-by-step completion telemetry)."
        )
    if post_plan_no_sub >= pre_plan and post_plan_no_sub >= paywalled and post_plan_no_sub > 0:
        dominant_modes.append(
            "• Post-plan confusion — users reach a generated plan but never open a session. "
            "Suggests the 'what do I do next' moment is unclear or the first session feels too heavy."
        )
    if paywalled > 0 and paywalled >= max(pre_plan, post_plan_no_sub):
        dominant_modes.append(
            "• Paywall shock — users subscribed (or entered trial) but never logged. "
            "Could indicate trial starts before real usage, creating friction before habit forms."
        )
    if not dominant_modes:
        dominant_modes.append("• No dominant drop-off mode detected — investigate individual users.")

    print("Dominant drop-off modes:")
    for mode in dominant_modes:
        print(mode)
    print()
    print("NOTE: this is diagnosis only. Solution lives in a separate A-brief after review.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    schemas = print_schemas()

    # Basic sanity: users table must have user_id + state
    user_cols = schemas.get("users", [])
    if user_cols and "user_id" not in user_cols:
        print(f"STOP: users table has no user_id column. Columns: {user_cols}")
        return 2

    print("Fetching data…")
    users = fetch_all_users()
    session_logs_counts = fetch_session_counts_from_logs()
    subs = fetch_subscriptions()
    clerk = fetch_clerk_users()
    print(f"  users={len(users)}  session_logs_user_groups={len(session_logs_counts)}  "
          f"subscriptions={len(subs)}  clerk_users={len(clerk)}")
    if not session_logs_counts:
        print("  NOTE: public.session_logs is empty — counts derive from "
              "users.state.session_completion_log (authoritative in current prod).")
    print()

    rows = stage_users(users, session_logs_counts, subs, clerk)

    if not validate_join(rows):
        print("STOP: validation gate failed. Inspect join key / session count mismatch above.")
        return 3

    print_detail_table(rows)
    dist = print_summary(rows)
    print_diagnostic(dist)

    return 0


if __name__ == "__main__":
    sys.exit(main())
