"""B331 — One-off: sblocco del trial di `odlan3` (2026-08-13).

Chiude il finding **TRIAL-LOCKOUT** aperto da D274.

## Perché

`odlan3` (`5a98187c`) si è iscritto il **09/07**, cioè *prima* di A250 (21/07),
quando il trial non partiva da solo: per usare l'app bisognava passare dal
paywall. Ha aperto due sessioni di checkout (09/07 23:04 e 19/07 20:16) e le ha
abbandonate entrambe. `POST /api/subscription/checkout` gli ha scritto
`status: pending_checkout` sulla riga, e `deps.py` mette `pending_checkout` fra
gli `_NEVER_STARTED_STATUSES` → la guardia risponde **402 «Subscribe to start
training»**. Risultato: un utente che non ha mai consumato un trial è trattato
come se l'avesse finito.

Non è un caso di nicchia scelto a caso: è **l'utente esterno più coinvolto degli
ultimi tre mesi** (6 giorni distinti di apertura, 3 settimane pianificate, 2
archiviate) ed è **tornato il 28/07** — trovando il muro. La whitelist del
win-back A251 (9 utenti) non lo comprendeva.

## Decisioni esplicite di Daniele (2026-08-13)

- **Solo `odlan3`.** `pippin_91donkeys` (`7208f92f`) ha lo stesso stato per lo
  stesso motivo, ma 0 giorni di apertura e nessun ritorno: lasciato com'è.
- **Il paywall non si tocca.** Stripe resta LIVE e la guardia fail-closed resta
  attiva: questo script sana *un dato*, non cambia una regola.

## Garanzie

Stesso formato del local trial A250 (`trialing`, +15gg, niente carta, zero
oggetti Stripe). Idempotente e conservativo:

- whitelist **hardcoded per UUID**: nessun altro utente è raggiungibile;
- riga con `stripe_subscription_id` → **abort** (mai toccare righe Stripe-managed);
- già `trialing` locale → **non tocca** (non allunga il trial ri-lanciando);
- `trial_end` già valorizzato (trial storicamente consumato) → **abort**, perché
  concederne un secondo violerebbe la regola anti-abuso A232. Sul soggetto di
  questo script è NULL, ed è precisamente la prova che il trial non fu mai usato.

Uso:
  python scripts/oneoff_unlock_odlan3_trial.py            # dry-run
  python scripts/oneoff_unlock_odlan3_trial.py --apply
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timedelta, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# email → prefisso UUID interno (risolto in D274, 2026-08-10)
WHITELIST = {
    "odlan3@gmail.com": "5a98187c",
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

    plan: list[tuple[str, str, str | None]] = []
    for email, prefix in WHITELIST.items():
        uid = full_ids[prefix]
        row = subs.get(uid)
        if row and row.get("stripe_subscription_id"):
            print(f"ABORT {email}: ha oggetti Stripe ({row['stripe_subscription_id']}) — mai toccare")
            return 1
        if row and row.get("trial_end"):
            # A232: un trial_end (passato o futuro) significa trial già consumato.
            print(f"ABORT {email}: trial_end già valorizzato ({str(row['trial_end'])[:10]}) — trial già consumato")
            return 1
        if row and row.get("status") == "trialing":
            print(f"SKIP {email}: trial locale già attivo — nulla da fare")
            continue
        plan.append((email, uid, row.get("status") if row else None))

    print(f"Da sbloccare: {len(plan)} | trial_end = {trial_end[:19]}Z")
    for e, uid, old in plan:
        print(f"  {e:32s} {uid[:8]}  {old or '(nessuna riga)'} → trialing")

    if not plan:
        print("\nNiente da fare.")
        return 0

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
