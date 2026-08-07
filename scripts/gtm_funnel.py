#!/usr/bin/env python
"""GTM funnel snapshot — one command instead of three manual queries.

Joins Supabase `subscriptions` + `users`, Clerk (email + last_active), and Stripe
(paid conversions) into a single activation/conversion picture:

  - trial cohort: LIVE (trial_end still in the future) vs EXPIRED-but-unreconciled
  - activation: who actually completed a session, not just who logged in once
  - pending_checkout: reached the paywall, never paid (hot leads)
  - paid conversions (Stripe active subs) + canceled history

Two things this script got wrong before B326, both of which inflated the picture:

  1. `trialing` was counted verbatim from the DB. Trial expiry is **lazy** — the
     status flips only when the user hits the subscription guard again, so a
     trial that ended weeks ago still reads `trialing` forever if its owner
     never comes back. Those rows are now a separate, explicitly-labelled bucket.
  2. "engaged" meant "has a Clerk last_active", which is true for *everyone* who
     ever signed up (signing up creates a session). It measured nothing. The
     activation signal is now sessions actually completed, read from the user
     state: `session_completion_log` + `free_sessions` + `outdoor_log`.
     NB: `public.session_logs` is empty for every user — completed sessions live
     in the state JSONB, not in that table. Do not "fix" this by querying it.

`giorni_app` is a proxy: one daily quote id is appended per day the app is
opened, and that history is a ring buffer capped at 30 (`quotes_engine`), so the
column saturates — it renders `30+`, never a real total beyond a month.

Read-only. Reads keys from `.env` at repo root (CLERK_SECRET_KEY, SUPABASE_URL,
SUPABASE_SERVICE_KEY, STRIPE_SECRET_KEY). No writes anywhere.

Usage:
    source .venv/bin/activate
    python scripts/gtm_funnel.py            # full snapshot
    python scripts/gtm_funnel.py --days 30  # widen the "new signups" window
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"

# `quotes_engine.update_quote_history` trims to the last 30 ids — see test_quotes.py.
QUOTE_HISTORY_CAP = 30


def env(key: str) -> str | None:
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return None


def _ts(ms: int | None) -> dt.datetime | None:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc) if ms else None


def _fmt(d: dt.datetime | None) -> str:
    return d.strftime("%m-%d %H:%M") if d else "—"


def _iso(value: str | None) -> dt.datetime | None:
    """Parse a Supabase timestamp into an aware UTC datetime (None if unusable)."""
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def clerk_users() -> dict[str, dict]:
    """clerk_id -> {email, last_active, created}. Empty dict if Clerk unset."""
    key = env("CLERK_SECRET_KEY")
    if not key:
        return {}
    req = urllib.request.Request(
        "https://api.clerk.com/v1/users?limit=200&order_by=-created_at",
        # A plain python-urllib User-Agent gets a 403 from Clerk; spoof a browser.
        headers={"Authorization": f"Bearer {key}", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        users = json.load(resp)
    out = {}
    for u in users:
        email = u["email_addresses"][0]["email_address"] if u.get("email_addresses") else "—"
        out[u["id"]] = {
            "email": email,
            "last_active": _ts(u.get("last_active_at")),
            "created": _ts(u.get("created_at")),
        }
    return out


def stripe_paid() -> tuple[int, list[str]]:
    """(active_count, [canceled emails]) — the real revenue picture."""
    key = env("STRIPE_SECRET_KEY")
    if not key:
        return 0, []
    import stripe

    stripe.api_key = key
    active = 0
    canceled: list[str] = []
    for s in stripe.Subscription.list(status="all", limit=100).auto_paging_iter():
        status = s["status"]
        if status in ("active", "trialing"):
            active += 1
        elif status == "canceled":
            try:
                cust = stripe.Customer.retrieve(s["customer"])
                canceled.append(cust["email"] or s["customer"])
            except Exception:
                canceled.append(s["customer"])
    return active, canceled


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="window for the new-signups section")
    args = ap.parse_args()

    url, service_key = env("SUPABASE_URL"), env("SUPABASE_SERVICE_KEY")
    if not url or not service_key:
        print("✗ SUPABASE_URL / SUPABASE_SERVICE_KEY not in .env", file=sys.stderr)
        return 1

    from supabase import create_client

    now = dt.datetime.now(dt.timezone.utc)
    sb = create_client(url, service_key)
    subs = sb.table("subscriptions").select("*").execute().data

    # Pull only the state slices we need — the full JSONB blob is megabytes.
    users = sb.table("users").select(
        "user_id,clerk_id,created_at,"
        "completions:state->session_completion_log,"
        "free_sessions:state->free_sessions,"
        "outdoor:state->outdoor_log,"
        "quotes:state->quote_history"
    ).execute().data
    by_uid = {u["user_id"]: u for u in users}
    clerk = clerk_users()

    def email_of(uid: str) -> str:
        info = clerk.get((by_uid.get(uid) or {}).get("clerk_id") or "")
        return info["email"] if info else "(no clerk map)"

    def last_login(uid: str) -> dt.datetime | None:
        info = clerk.get((by_uid.get(uid) or {}).get("clerk_id") or "")
        return info["last_active"] if info else None

    def _n(row: dict, key: str) -> int:
        value = row.get(key)
        return len(value) if isinstance(value, list) else 0

    def sessions_done(uid: str) -> int:
        """Completed sessions of any kind — the only honest activation signal."""
        row = by_uid.get(uid) or {}
        return _n(row, "completions") + _n(row, "free_sessions") + _n(row, "outdoor")

    def last_session(uid: str) -> str:
        """Date of the most recent completed session. A lifetime count without
        this is misleading: 20 sessions that all ended in April is a churned user."""
        row = by_uid.get(uid) or {}
        dates = []
        for key in ("completions", "free_sessions", "outdoor"):
            for entry in row.get(key) or []:
                if not isinstance(entry, dict):
                    continue
                # Each log type names its date differently; take the first that sticks.
                for field in ("date", "session_date", "completed_at", "started_at", "finished_at"):
                    value = entry.get(field)
                    if isinstance(value, str) and value[:4].isdigit():
                        dates.append(value[:10])
                        break
        return max(dates) if dates else "—"

    def days_opened(uid: str) -> str:
        """Days the app was opened — one quote id per day, ring buffer capped at 30."""
        count = _n(by_uid.get(uid) or {}, "quotes")
        return "30+" if count >= QUOTE_HISTORY_CAP else str(count)

    def activity(uid: str) -> str:
        return (f"sessioni={sessions_done(uid):<3d} ultima={last_session(uid):10s} "
                f"giorni_app={days_opened(uid):<3s}")

    # Cohorts. A trial is live only if its trial_end is still ahead of us: the
    # DB keeps `trialing` indefinitely for users who never came back (lazy expiry).
    trialing = [s for s in subs if s["status"] == "trialing"]
    live, expired = [], []
    for s in trialing:
        end = _iso(s.get("trial_end"))
        (expired if end and end < now else live).append(s)
    pending = [s for s in subs if s["status"] == "pending_checkout"]
    active_paid, canceled = stripe_paid()

    activated = [u["user_id"] for u in users if sessions_done(u["user_id"]) > 0]
    live_activated = sum(1 for s in live if sessions_done(s["user_id"]) > 0)
    never_logged = sum(1 for s in trialing if not last_login(s["user_id"]))
    cutoff = now - dt.timedelta(days=args.days)
    new_signups = sorted(
        (u for u in users if (_iso(u.get("created_at")) or now) >= cutoff),
        key=lambda u: u.get("created_at") or "",
        reverse=True,
    )

    print("═" * 72)
    print(f"  GTM FUNNEL — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * 72)
    print(f"  Trial ATTIVI:        {len(live):3d}   (trial_end futuro · attivati {live_activated})")
    print(f"  Trial SCADUTI:       {len(expired):3d}   (status 'trialing' non riconciliato — scadenza lazy)")
    print(f"  Pending checkout:    {len(pending):3d}   (arrivati al paywall, non pagato)")
    print(f"  Paganti attivi:      {active_paid:3d}   (Stripe active/trialing)")
    print(f"  Canceled (storico):  {len(canceled):3d}")
    print("  " + "─" * 68)
    print(f"  Attivazione:         {len(activated):3d}/{len(users)} utenti con ≥1 sessione completata")
    print(f"  Mai loggati:         {never_logged:3d}   (su {len(trialing)} trial, live + scaduti)")

    def _rows(title: str, rows: list[dict], extra) -> None:
        print(f"\n  ── {title} ──")
        if not rows:
            print("    (nessuno)")
            return
        for s in rows:
            uid = s["user_id"]
            print(f"    {email_of(uid):34s} {extra(s)}  {activity(uid)}")

    def _login_col(uid: str) -> str:
        return f"last_login={_fmt(last_login(uid)):11s}"

    _rows(
        f"TRIAL ATTIVI ({len(live)})",
        sorted(live, key=lambda s: s.get("trial_end") or ""),
        lambda s: f"trial_end={(s.get('trial_end') or '—')[:10]}  {_login_col(s['user_id'])}",
    )
    _rows(
        f"TRIAL SCADUTI — da riconciliare ({len(expired)})",
        sorted(expired, key=lambda s: s.get("trial_end") or "", reverse=True),
        lambda s: f"scaduto={(s.get('trial_end') or '—')[:10]}    {_login_col(s['user_id'])}",
    )
    _rows(
        f"PENDING CHECKOUT — lead caldi / stuck ({len(pending)})",
        sorted(pending, key=lambda s: s["updated_at"], reverse=True),
        lambda s: f"updated={s['updated_at'][:10]}    {_login_col(s['user_id'])}",
    )

    print(f"\n  ── NUOVI ISCRITTI (ultimi {args.days} giorni: {len(new_signups)}) ──")
    if not new_signups:
        print("    (nessuno)")
    for u in new_signups:
        uid = u["user_id"]
        print(f"    {email_of(uid):34s} reg={(u.get('created_at') or '—')[:10]}          {activity(uid)}")

    if canceled:
        print("\n  ── Canceled (storico) ──")
        for e in canceled:
            print(f"    {e}")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
