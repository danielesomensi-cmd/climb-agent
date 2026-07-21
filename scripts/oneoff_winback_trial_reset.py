"""A251 — One-off: win-back trial reset (founder override, 2026-07-21).

Crea/aggiorna la riga subscriptions per il cohort win-back qui sotto, nello
STESSO formato del local trial A250 (trialing, +15gg, niente carta, zero
oggetti Stripe). Decisione esplicita di Daniele per il re-lancio su
climbagent.app; NON modifica la regola A232 per i nuovi iscritti.

Dal pre-check (Fase 1): nessuno dei 9 aveva mai consumato un trial (nessun
trial_end in DB) e nessuno ha oggetti Stripe — di fatto è la prima creazione
del loro trial, non un vero override.

Idempotente:
- utente già `trialing` locale → non tocca (non allunga il trial ri-lanciando)
- utente con stripe_subscription_id → ABORT su quell'utente (mai toccare
  righe Stripe-managed)
- whitelist hardcoded per UUID: nessun altro utente può essere toccato

Uso:
  python scripts/oneoff_winback_trial_reset.py            # dry-run
  python scripts/oneoff_winback_trial_reset.py --apply
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timedelta, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# email → UUID interno (risolti nel pre-check A251, 2026-07-21)
WHITELIST = {
    "ckb.palmer@gmail.com":       "79fadc50",
    "cesar.e.meric@gmail.com":    "9e4154d4",
    "romitodavid@gmail.com":      "22080848",
    "tabithamann90@gmail.com":    "6cf99c0d",
    "paul.cample@gmail.com":      "d7f6083e",
    "pewen.outdoors@gmail.com":   "f49678eb",
    "arthur.pepin11@gmail.com":   "ce8914f0",
    "woween@gmail.com":           "611e0369",
    "edoardoborghini91@gmail.com": "3fc2a699",
}

TRIAL_DAYS = 15


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    env: dict[str, str] = {}
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip())

    from supabase import create_client
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_KEY"])

    users = sb.table("users").select("user_id").execute().data
    full_ids = {}
    for prefix in WHITELIST.values():
        matches = [u["user_id"] for u in users if u["user_id"].startswith(prefix)]
        if len(matches) != 1:
            print(f"ERRORE: prefix {prefix} → {len(matches)} match, abort totale")
            return 1
        full_ids[prefix] = matches[0]

    subs = {r["user_id"]: r for r in sb.table("subscriptions").select("*").execute().data}
    now = datetime.now(timezone.utc)
    trial_end = (now + timedelta(days=TRIAL_DAYS)).isoformat()

    plan, skip = [], []
    for email, prefix in WHITELIST.items():
        uid = full_ids[prefix]
        row = subs.get(uid)
        if row and row.get("stripe_subscription_id"):
            skip.append((email, "HA OGGETTI STRIPE — non toccato"))
            continue
        if row and row.get("status") == "trialing" and not row.get("stripe_subscription_id"):
            skip.append((email, f"trial locale già attivo (end {str(row.get('trial_end'))[:10]}) — non toccato"))
            continue
        plan.append((email, uid, row.get("status") if row else None))

    print(f"Da resettare: {len(plan)} | Skip: {len(skip)} | trial_end = {trial_end[:19]}Z")
    for e, uid, old in plan:
        print(f"  {e:32s} {uid[:8]}  {old or '(nessuna riga)'} → trialing")
    for e, why in skip:
        print(f"  SKIP {e}: {why}")

    if not args.apply:
        print("\nDry-run. --apply per eseguire.")
        return 0

    for email, uid, _ in plan:
        sb.table("subscriptions").upsert({
            "user_id": uid,
            "status": "trialing",
            "trial_start": now.isoformat(),
            "trial_end": trial_end,
            "has_payment_method": False,
            "stripe_subscription_id": None,
        }, on_conflict="user_id").execute()
        print(f"  ✅ {email}")

    print(f"\nFatto: {len(plan)} trial impostati, scadenza {trial_end[:10]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
