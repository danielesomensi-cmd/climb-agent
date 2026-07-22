#!/usr/bin/env python
"""GTM funnel snapshot — one command instead of three manual queries.

Joins Supabase `subscriptions` + `users`, Clerk (email + last_active), and Stripe
(paid conversions) into a single activation/conversion picture:

  - trial cohort: engaged (logged in) vs dormant (never opened the app)
  - pending_checkout: reached the paywall, never paid (hot leads)
  - paid conversions (Stripe active subs) + canceled history

Read-only. Reads keys from `.env` at repo root (CLERK_SECRET_KEY, SUPABASE_URL,
SUPABASE_SERVICE_KEY, STRIPE_SECRET_KEY). No writes anywhere.

Usage:
    source .venv/bin/activate
    python scripts/gtm_funnel.py            # full snapshot
    python scripts/gtm_funnel.py --days 7   # flag movements in the last 7 days
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
    ap.add_argument("--days", type=int, default=2, help="highlight movement within N days")
    args = ap.parse_args()

    url, service_key = env("SUPABASE_URL"), env("SUPABASE_SERVICE_KEY")
    if not url or not service_key:
        print("✗ SUPABASE_URL / SUPABASE_SERVICE_KEY not in .env", file=sys.stderr)
        return 1

    from supabase import create_client

    sb = create_client(url, service_key)
    subs = sb.table("subscriptions").select("*").execute().data
    uid2clerk = {u["user_id"]: u.get("clerk_id") for u in sb.table("users").select("user_id,clerk_id").execute().data}
    clerk = clerk_users()

    def email_of(uid: str) -> str:
        info = clerk.get(uid2clerk.get(uid) or "")
        return info["email"] if info else "(no clerk map)"

    def last_login(uid: str) -> dt.datetime | None:
        info = clerk.get(uid2clerk.get(uid) or "")
        return info["last_active"] if info else None

    # Cohorts.
    trialing = [s for s in subs if s["status"] == "trialing"]
    pending = [s for s in subs if s["status"] == "pending_checkout"]
    engaged = [s for s in trialing if last_login(s["user_id"])]
    dormant = [s for s in trialing if not last_login(s["user_id"])]
    active_paid, canceled = stripe_paid()

    print("═" * 68)
    print(f"  GTM FUNNEL — {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * 68)
    print(f"  Trial attivi:        {len(trialing):3d}   (engaged {len(engaged)} · dormienti {len(dormant)})")
    print(f"  Pending checkout:    {len(pending):3d}   (arrivati al paywall, non pagato)")
    print(f"  Paganti attivi:      {active_paid:3d}   (Stripe active/trialing)")
    print(f"  Canceled (storico):  {len(canceled):3d}")

    print("\n  ── Trial ENGAGED (loggati) ──")
    for s in sorted(engaged, key=lambda s: last_login(s["user_id"]) or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True):
        te = (s.get("trial_end") or "—")[:10]
        print(f"    {email_of(s['user_id']):34s} last_login={_fmt(last_login(s['user_id']))}  trial_end={te}")

    print("\n  ── Trial DORMIENTI (mai loggati) ──")
    for s in dormant:
        print(f"    {email_of(s['user_id']):34s} trial_end={(s.get('trial_end') or '—')[:10]}")

    print("\n  ── PENDING CHECKOUT (lead caldi / stuck) ──")
    for s in sorted(pending, key=lambda s: s["updated_at"], reverse=True):
        print(f"    {email_of(s['user_id']):34s} updated={s['updated_at'][:16]}  last_login={_fmt(last_login(s['user_id']))}")

    if canceled:
        print("\n  ── Canceled (storico) ──")
        for e in canceled:
            print(f"    {e}")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
