#!/usr/bin/env python3
"""
admin_dashboard.py — Climb-Agent user overview for admins.

Usage:
    python scripts/admin_dashboard.py              # Terminal output
    python scripts/admin_dashboard.py --md         # Also save markdown to reports/
    python scripts/admin_dashboard.py --json       # JSON output
    python scripts/admin_dashboard.py --days 14   # Change lookback window (default: 7)

Requires in .env:
    CLERK_SECRET_KEY=...
    SUPABASE_URL=...
    SUPABASE_SERVICE_KEY=...
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

MISSING = [k for k, v in {
    "CLERK_SECRET_KEY": CLERK_SECRET_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY,
}.items() if not v]

if MISSING:
    print(f"❌ Missing env vars: {', '.join(MISSING)}")
    print("   Add them to .env in the repo root.")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("❌ supabase not installed. Run: pip install supabase")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Clerk helpers
# ---------------------------------------------------------------------------

def fetch_clerk_users() -> list[dict]:
    """Fetch all Clerk users (paginated at 100)."""
    users = []
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
        users.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return users


def parse_clerk_user(raw: dict) -> dict:
    """Extract relevant fields from a raw Clerk user object."""
    emails = raw.get("email_addresses") or []
    email = emails[0]["email_address"] if emails else "—"
    first = (raw.get("first_name") or "").strip()
    last = (raw.get("last_name") or "").strip()
    name = f"{first} {last}".strip() or "—"

    created_ms = raw.get("created_at")
    last_sign_ms = raw.get("last_sign_in_at")

    def ms_to_dt(ms):
        if not ms:
            return None
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

    return {
        "clerk_id": raw["id"],
        "name": name,
        "email": email,
        "created_at": ms_to_dt(created_ms),
        "last_sign_in_at": ms_to_dt(last_sign_ms),
    }


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def fetch_supabase_users() -> list[dict]:
    """Fetch all rows from the users table."""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    resp = client.table("users").select("user_id, clerk_id, state").execute()
    return resp.data or []


# ---------------------------------------------------------------------------
# Activity analysis
# ---------------------------------------------------------------------------

def _safe_str(val) -> str:
    """Convert to string safely."""
    return str(val) if val is not None else "—"


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def analyze_state(state: dict, days: int) -> dict:
    """
    Extract activity metrics from a user_state dict.

    Returns:
        dict with keys:
            onboarding_complete: bool
            discipline: str
            current_phase: str | None
            macrocycle_week: str  (e.g. "3/12")
            sessions_done_total: int
            sessions_done_recent: int
            sessions_skipped_recent: int
            feedback_count_recent: int
            free_sessions_recent: int
            outdoor_sessions_recent: int
            last_activity: date | None
            warnings: list[str]
            stale_plan: bool
            consecutive_very_hard: int
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    result: dict = {
        "onboarding_complete": False,
        "discipline": "—",
        "current_phase": None,
        "macrocycle_week": "—",
        "sessions_done_total": 0,
        "sessions_done_recent": 0,
        "sessions_skipped_recent": 0,
        "feedback_count_recent": 0,
        "free_sessions_recent": 0,
        "outdoor_sessions_recent": 0,
        "last_activity": None,
        "warnings": [],
        "stale_plan": False,
        "consecutive_very_hard": 0,
    }

    if not state:
        return result

    # Onboarding
    has_assessment = bool(state.get("assessment") and state["assessment"].get("profile"))
    has_macrocycle = bool(state.get("macrocycle") and state["macrocycle"].get("phases"))
    result["onboarding_complete"] = has_assessment and has_macrocycle

    # Discipline
    goal = state.get("goal") or {}
    result["discipline"] = goal.get("goal_type") or goal.get("discipline") or "—"

    # Macrocycle phase + week
    mc = state.get("macrocycle") or {}
    total_weeks = mc.get("total_weeks")
    start_date_str = mc.get("start_date")
    if start_date_str and total_weeks:
        try:
            start = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            today = datetime.now(tz=timezone.utc)
            current_week_num = max(1, (today - start).days // 7 + 1)
            result["macrocycle_week"] = f"{current_week_num}/{total_weeks}"

            if current_week_num > total_weeks:
                result["stale_plan"] = True

            # Find phase for current week
            phases = mc.get("phases") or []
            week_cursor = 1
            for ph in phases:
                ph_weeks = ph.get("weeks") or 1
                if week_cursor <= current_week_num < week_cursor + ph_weeks:
                    result["current_phase"] = ph.get("phase_id") or ph.get("phase")
                    break
                week_cursor += ph_weeks
        except Exception:
            pass

    # Session completion log
    completion_log = state.get("session_completion_log") or []
    for entry in completion_log:
        status = entry.get("status")
        if status == "done":
            result["sessions_done_total"] += 1
            ts = _parse_iso(entry.get("completed_at"))
            if ts and ts >= cutoff:
                result["sessions_done_recent"] += 1
        elif status == "skipped":
            ts = _parse_iso(entry.get("completed_at"))
            if ts and ts >= cutoff:
                result["sessions_skipped_recent"] += 1

    # Feedback log (trimmed to 7 — use for difficulty analysis and recent dates)
    feedback_log = state.get("feedback_log") or []
    for entry in feedback_log:
        date_str = entry.get("date")
        if date_str:
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if entry_date >= cutoff:
                    result["feedback_count_recent"] += 1
            except Exception:
                pass

    # Consecutive very_hard check (from feedback_log, most recent first)
    consec = 0
    for entry in sorted(feedback_log, key=lambda x: str(x.get("date") or ""), reverse=True):
        diff = entry.get("difficulty")
        if diff == "very_hard":
            consec += 1
        else:
            break
    result["consecutive_very_hard"] = consec

    # Free sessions
    free_sessions = state.get("free_sessions") or []
    for s in free_sessions:
        date_str = s.get("date") or s.get("started_at") or ""
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if d >= cutoff:
                result["free_sessions_recent"] += 1
        except Exception:
            pass

    # Outdoor sessions
    outdoor_log = state.get("outdoor_log") or []
    for s in outdoor_log:
        date_str = s.get("date") or ""
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if d >= cutoff:
                result["outdoor_sessions_recent"] += 1
        except Exception:
            pass

    # Last activity — most recent completion timestamp
    all_timestamps = []
    for entry in completion_log:
        ts = _parse_iso(entry.get("completed_at"))
        if ts:
            all_timestamps.append(ts)
    for entry in free_sessions:
        date_str = entry.get("date") or entry.get("started_at") or ""
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            all_timestamps.append(d)
        except Exception:
            pass
    for entry in outdoor_log:
        date_str = entry.get("date") or ""
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            all_timestamps.append(d)
        except Exception:
            pass
    if all_timestamps:
        result["last_activity"] = max(all_timestamps).date()

    return result


def detect_warnings(user: dict, activity: dict, days: int) -> list[str]:
    """Detect attention signals for a user."""
    warnings = []
    now = datetime.now(tz=timezone.utc)

    # Onboarding incomplete
    has_state = user.get("has_state", False)
    if has_state and not activity["onboarding_complete"]:
        warnings.append("🔴 Onboarding incompleto (stato presente ma senza assessment/macrocycle)")

    # Dormiente: logged in but inactive
    last_sign = user.get("last_sign_in_at")
    if last_sign and activity["onboarding_complete"]:
        days_since_login = (now - last_sign).days
        if days_since_login > days and activity["sessions_done_recent"] == 0:
            warnings.append(f"🟡 Dormiente: ultimo login {days_since_login}gg fa, 0 sessioni negli ultimi {days}gg")

    # Drop-off: onboarded but never trained
    created = user.get("created_at")
    if created and activity["onboarding_complete"] and activity["sessions_done_total"] == 0:
        days_since_signup = (now - created).days
        if days_since_signup > 3:
            warnings.append(f"🟡 Drop-off: onboarding completo {days_since_signup}gg fa, 0 sessioni mai completate")

    # Overtraining signal
    if activity["consecutive_very_hard"] >= 3:
        warnings.append(f"🟠 Segnale overtraining: {activity['consecutive_very_hard']} feedback 'very_hard' consecutivi")

    # All skipped
    done = activity["sessions_done_recent"]
    skipped = activity["sessions_skipped_recent"]
    if skipped >= 2 and skipped > done:
        warnings.append(f"🟡 Prevalenza skip: {skipped} saltate vs {done} completate negli ultimi {days}gg")

    # Stale plan
    if activity["stale_plan"]:
        warnings.append("🟡 Piano scaduto: macrocycle oltre le settimane totali")

    return warnings


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_date(dt) -> str:
    if dt is None:
        return "mai"
    if hasattr(dt, "strftime"):
        return dt.strftime("%d/%m/%y")
    return str(dt)


def fmt_dt(dt) -> str:
    if dt is None:
        return "mai"
    return dt.strftime("%d/%m/%y %H:%M")


def _col(text: str, width: int, align: str = "left") -> str:
    s = str(text)
    if len(s) > width:
        s = s[:width - 1] + "…"
    if align == "right":
        return s.rjust(width)
    return s.ljust(width)


def _hr(char: str = "─", width: int = 100) -> str:
    return char * width


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_report(users_data: list[dict], days: int) -> tuple[str, dict]:
    """
    Build the terminal report string and JSON data dict.

    users_data: list of merged user dicts (Clerk + Supabase + activity)
    Returns: (report_str, json_data)
    """
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=days)

    lines = []

    def section(title: str):
        lines.append("")
        lines.append(_hr("═"))
        lines.append(f"  {title}")
        lines.append(_hr("═"))

    def subsection(title: str):
        lines.append("")
        lines.append(f"  {title}")
        lines.append(_hr("─"))

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append("")
    lines.append("═" * 100)
    lines.append(f"  CLIMB-AGENT USERS REPORT  —  {now.strftime('%Y-%m-%d %H:%M')} UTC  (finestra: ultimi {days}gg)")
    lines.append("═" * 100)

    total = len(users_data)
    new_users = [u for u in users_data if u.get("created_at") and u["created_at"] >= cutoff]
    active = [u for u in users_data if u.get("activity", {}).get("sessions_done_recent", 0) > 0
              or u.get("activity", {}).get("free_sessions_recent", 0) > 0
              or u.get("activity", {}).get("outdoor_sessions_recent", 0) > 0]
    dormant = [u for u in users_data
               if u.get("activity", {}).get("onboarding_complete")
               and (u.get("last_sign_in_at") and (now - u["last_sign_in_at"]).days > days)
               and u.get("activity", {}).get("sessions_done_recent", 0) == 0]

    # ── Summary ──────────────────────────────────────────────────────────────
    section("📊 RIEPILOGO")
    lines.append(
        f"  Totale iscritti: {total}  |  Nuovi ({days}gg): {len(new_users)}"
        f"  |  Attivi ({days}gg): {len(active)}  |  Dormienti: {len(dormant)}"
    )

    # ── New users ─────────────────────────────────────────────────────────────
    section(f"👋 NUOVI ISCRITTI (ultimi {days}gg)")
    if new_users:
        header = (
            _col("Nome", 22) + _col("Email", 34) + _col("Iscritto", 12)
        )
        lines.append("  " + header)
        lines.append("  " + _hr("─", len(header)))
        for u in sorted(new_users, key=lambda x: x["created_at"], reverse=True):
            lines.append(
                "  "
                + _col(u["name"], 22)
                + _col(u["email"], 34)
                + _col(fmt_dt(u.get("created_at")), 12)
            )
    else:
        lines.append("  Nessun nuovo iscritto.")

    # ── All users ─────────────────────────────────────────────────────────────
    section("👥 TUTTI GLI ISCRITTI")
    hdr = (
        _col("Nome", 22)
        + _col("Email", 30)
        + _col("Iscritto", 10)
        + _col("Ultimo login", 12)
        + _col("Disciplina", 12)
        + _col("Fase", 20)
        + _col("Sett.", 7)
        + _col("Done", 6)
        + _col(f"Done {days}gg", 10)
        + _col("Stato", 10)
    )
    lines.append("  " + hdr)
    lines.append("  " + _hr("─", len(hdr)))

    for u in sorted(users_data, key=lambda x: x.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        act = u.get("activity") or {}
        disc = act.get("discipline", "—").replace("_grade", "").replace("all_round", "all")
        phase = (act.get("current_phase") or "—").replace("_", " ")
        state_flag = "✅" if u.get("has_state") else "no stato"
        if u.get("has_state") and not act.get("onboarding_complete"):
            state_flag = "⚠️ onb."
        lines.append(
            "  "
            + _col(u["name"], 22)
            + _col(u["email"], 30)
            + _col(fmt_date(u.get("created_at")), 10)
            + _col(fmt_date(u.get("last_sign_in_at")), 12)
            + _col(disc, 12)
            + _col(phase, 20)
            + _col(act.get("macrocycle_week", "—"), 7)
            + _col(act.get("sessions_done_total", "—"), 6)
            + _col(act.get("sessions_done_recent", "—"), 10)
            + _col(state_flag, 10)
        )

    # ── Activity last N days ──────────────────────────────────────────────────
    section(f"⚡ ATTIVITÀ ULTIMI {days}GG")
    active_users = [u for u in users_data if (
        u.get("activity", {}).get("sessions_done_recent", 0) > 0
        or u.get("activity", {}).get("sessions_skipped_recent", 0) > 0
        or u.get("activity", {}).get("free_sessions_recent", 0) > 0
        or u.get("activity", {}).get("outdoor_sessions_recent", 0) > 0
    )]
    if active_users:
        ahdr = (
            _col("Nome", 22)
            + _col("Done", 6)
            + _col("Skip", 6)
            + _col("Feedback", 9)
            + _col("Free", 6)
            + _col("Outdoor", 8)
            + _col("Ultimo allenamento", 20)
        )
        lines.append("  " + ahdr)
        lines.append("  " + _hr("─", len(ahdr)))
        for u in sorted(active_users, key=lambda x: x.get("activity", {}).get("last_activity") or datetime.min.date(), reverse=True):
            act = u.get("activity") or {}
            lines.append(
                "  "
                + _col(u["name"], 22)
                + _col(act.get("sessions_done_recent", 0), 6)
                + _col(act.get("sessions_skipped_recent", 0), 6)
                + _col(act.get("feedback_count_recent", 0), 9)
                + _col(act.get("free_sessions_recent", 0), 6)
                + _col(act.get("outdoor_sessions_recent", 0), 8)
                + _col(fmt_date(act.get("last_activity")), 20)
            )
        inactive = [u for u in users_data if u not in active_users and u.get("has_state")]
        if inactive:
            lines.append(f"\n  Nessuna attività negli ultimi {days}gg: " + ", ".join(u["name"] for u in inactive))
    else:
        lines.append(f"  Nessuna attività negli ultimi {days}gg.")

    # ── Warnings ─────────────────────────────────────────────────────────────
    section("⚠️  SEGNALI DI ATTENZIONE")
    any_warning = False
    for u in sorted(users_data, key=lambda x: x["name"]):
        w = u.get("warnings") or []
        if w:
            any_warning = True
            lines.append(f"  {u['name']} ({u['email']}):")
            for msg in w:
                lines.append(f"    {msg}")
    if not any_warning:
        lines.append("  Nessun problema rilevato ✅")

    lines.append("")
    lines.append("═" * 100)
    lines.append("")

    # ── JSON payload ──────────────────────────────────────────────────────────
    json_data = {
        "generated_at": now.isoformat(),
        "lookback_days": days,
        "summary": {
            "total_users": total,
            "new_users": len(new_users),
            "active_users": len(active),
            "dormant_users": len(dormant),
        },
        "users": [
            {
                "clerk_id": u.get("clerk_id"),
                "internal_id": u.get("internal_id"),
                "name": u["name"],
                "email": u["email"],
                "created_at": u["created_at"].isoformat() if u.get("created_at") else None,
                "last_sign_in_at": u["last_sign_in_at"].isoformat() if u.get("last_sign_in_at") else None,
                "has_state": u.get("has_state", False),
                "activity": u.get("activity") or {},
                "warnings": u.get("warnings") or [],
            }
            for u in users_data
        ],
    }

    return "\n".join(lines), json_data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Climb-Agent admin dashboard")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--md", action="store_true", help="Save markdown report to reports/")
    parser.add_argument("--json", action="store_true", dest="json_out", help="JSON output to stdout")
    args = parser.parse_args()

    days = args.days

    print("🔄 Fetching Clerk users…", flush=True)
    try:
        raw_clerk = fetch_clerk_users()
    except Exception as e:
        print(f"❌ Clerk API error: {e}")
        sys.exit(1)

    print(f"   {len(raw_clerk)} utenti Clerk trovati")
    clerk_users = {u["id"]: parse_clerk_user(u) for u in raw_clerk}

    print("🔄 Fetching Supabase rows…", flush=True)
    try:
        sb_rows = fetch_supabase_users()
    except Exception as e:
        print(f"❌ Supabase error: {e}")
        sys.exit(1)

    print(f"   {len(sb_rows)} righe Supabase trovate")

    # Build clerk_id → row map
    sb_by_clerk: dict[str, dict] = {}
    sb_orphans: list[dict] = []
    for row in sb_rows:
        cid = row.get("clerk_id")
        if cid and cid in clerk_users:
            sb_by_clerk[cid] = row
        else:
            sb_orphans.append(row)

    # Merge
    users_data: list[dict] = []
    for clerk_id, cu in clerk_users.items():
        sb_row = sb_by_clerk.get(clerk_id)
        state = (sb_row.get("state") or {}) if sb_row else {}
        has_state = bool(sb_row)

        activity = analyze_state(state, days)
        warnings = detect_warnings({**cu, "has_state": has_state}, activity, days)

        if warnings:
            activity["warnings"] = warnings

        users_data.append({
            **cu,
            "internal_id": sb_row["user_id"] if sb_row else None,
            "has_state": has_state,
            "activity": activity,
            "warnings": warnings,
        })

    if sb_orphans:
        print(f"\n⚠️  {len(sb_orphans)} righe Supabase senza Clerk user corrispondente (utenti eliminati?)")
        for row in sb_orphans:
            print(f"   internal_id={row.get('id')}  clerk_id={row.get('clerk_id')}")

    # Build report
    print("🔄 Generazione report…\n", flush=True)
    report_str, json_data = build_report(users_data, days)

    if args.json_out:
        print(json.dumps(json_data, indent=2, default=str))
        return

    print(report_str)

    # Verification line
    daniele = next(
        (u for u in users_data if "somensi" in u["name"].lower() or "daniele" in u["name"].lower()),
        None,
    )
    if daniele:
        act = daniele.get("activity") or {}
        total_done = act.get("sessions_done_total", 0)
        print(f"✅ Verified: {daniele['name']} found with {total_done} sessions")
    else:
        print("⚠️  Daniele Somensi non trovato nella lista utenti")

    if args.md:
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        md_path = reports_dir / f"users_report_{date_str}.md"
        md_content = f"```\n{report_str}\n```\n"
        md_path.write_text(md_content)
        print(f"\n📄 Report salvato in: {md_path}")


if __name__ == "__main__":
    main()
