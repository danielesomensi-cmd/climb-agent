"""A249 — Migrazione utenti Clerk dev → prod.

Flusso (vedi analisi A249):
1. Esporta gli utenti dall'istanza Clerk DEV (email, nome, metodo auth).
2. Legge la tabella `users` su Supabase (user_id ↔ clerk_id attuali = dev).
3. Join per clerk_id; per ogni utente crea l'omologo sull'istanza PROD
   (match per email se già esiste). Utenti password: creati con
   `skip_password_requirement` → al primo accesso fanno "Forgot password".
   Utenti Google OAuth: basta l'email — al primo login Google Clerk collega
   l'account automaticamente (stessa email verificata).
4. Salva il backup della mappatura vecchia (rollback) e aggiorna
   `users.clerk_id` su Supabase con i nuovi id PROD.

SICUREZZA: default = dry-run (nessuna scrittura). Serve --apply per scrivere.
Il remap va eseguito PRIMA di swappare le chiavi sul frontend: finché la
publishable key non cambia, nessun utente può raggiungere l'istanza prod,
quindi non esiste finestra in cui `lookup_or_create_user` possa creare
account orfani.

Env richieste (.env in repo root):
  CLERK_SECRET_KEY        istanza DEV (sk_test_...)
  CLERK_PROD_SECRET_KEY   istanza PROD (sk_live_...)  [solo per --apply / verifica prod]
  SUPABASE_URL            progetto Supabase
  SUPABASE_SERVICE_KEY    service role key (bypassa RLS)

Uso:
  python scripts/migrate_clerk_prod.py            # dry-run: report completo
  python scripts/migrate_clerk_prod.py --apply    # esegue creazioni + remap
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
CLERK_API = "https://api.clerk.com/v1"
BACKUP_PATH = REPO_ROOT / "scripts" / "clerk_migration_backup.json"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())
    env.update({k: v for k, v in os.environ.items()})
    return env


def _clerk_get_users(secret: str) -> list[dict]:
    users, offset = [], 0
    while True:
        r = requests.get(
            f"{CLERK_API}/users",
            headers={"Authorization": f"Bearer {secret}"},
            params={"limit": 100, "offset": offset},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        users.extend(batch)
        if len(batch) < 100:
            return users
        offset += 100


def _primary_email(u: dict) -> str | None:
    for e in u.get("email_addresses", []):
        if e["id"] == u.get("primary_email_address_id"):
            return e["email_address"].lower()
    if u.get("email_addresses"):
        return u["email_addresses"][0]["email_address"].lower()
    return None


def _create_prod_user(secret: str, dev_user: dict, email: str) -> dict:
    payload: dict = {
        "email_address": [email],
        "skip_password_requirement": True,
    }
    if dev_user.get("first_name"):
        payload["first_name"] = dev_user["first_name"]
    if dev_user.get("last_name"):
        payload["last_name"] = dev_user["last_name"]
    r = requests.post(
        f"{CLERK_API}/users",
        headers={"Authorization": f"Bearer {secret}"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="esegue le scritture (default: dry-run)")
    args = parser.parse_args()

    env = _load_env()
    dev_key = env.get("CLERK_SECRET_KEY", "")
    prod_key = env.get("CLERK_PROD_SECRET_KEY", "")
    sb_url = env.get("SUPABASE_URL", "")
    sb_service = env.get("SUPABASE_SERVICE_KEY", "")

    if not dev_key:
        print("ERRORE: CLERK_SECRET_KEY (dev) mancante in .env"); return 1
    if not (sb_url and sb_service):
        print("ERRORE: SUPABASE_URL / SUPABASE_SERVICE_KEY mancanti in .env"); return 1
    if args.apply and not prod_key:
        print("ERRORE: --apply richiede CLERK_PROD_SECRET_KEY in .env"); return 1
    if prod_key and not prod_key.startswith("sk_live"):
        print(f"ATTENZIONE: CLERK_PROD_SECRET_KEY non sembra una chiave live ({prod_key[:8]}...)")

    # 1. Utenti dev
    dev_users = _clerk_get_users(dev_key)
    print(f"Istanza DEV: {len(dev_users)} utenti Clerk")

    # 2. Mappatura Supabase (service role key → bypassa RLS)
    from supabase import create_client
    sb = create_client(sb_url, sb_service)
    rows = (
        sb.table("users").select("user_id, clerk_id").not_.is_("clerk_id", "null").execute().data
    )
    by_clerk = {r["clerk_id"]: r["user_id"] for r in rows}
    print(f"Supabase: {len(rows)} righe users con clerk_id")

    # 3. Utenti prod già esistenti (idempotenza: match per email)
    prod_by_email: dict[str, dict] = {}
    if prod_key:
        for u in _clerk_get_users(prod_key):
            email = _primary_email(u)
            if email:
                prod_by_email[email] = u
        print(f"Istanza PROD: {len(prod_by_email)} utenti già presenti")

    # 4. Piano di migrazione
    plan, skipped = [], []
    for u in dev_users:
        email = _primary_email(u)
        internal = by_clerk.get(u["id"])
        method = "google" if any(
            a["provider"] == "oauth_google" for a in u.get("external_accounts", [])
        ) else ("password" if u.get("password_enabled") else "altro")
        if not internal:
            skipped.append((u["id"], email, "nessuna riga Supabase (mai completato una chiamata API?)"))
            continue
        if not email:
            skipped.append((u["id"], email, "nessuna email — impossibile migrare"))
            continue
        plan.append({
            "email": email,
            "method": method,
            "dev_clerk_id": u["id"],
            "internal_user_id": internal,
            "prod_clerk_id": prod_by_email.get(email, {}).get("id"),  # già esistente?
            "dev_user": u,
        })

    print(f"\nPiano: {len(plan)} da migrare, {len(skipped)} scartati")
    for p in plan:
        status = "GIÀ IN PROD" if p["prod_clerk_id"] else "da creare"
        print(f"  {p['email']:40s} {p['method']:9s} {status}")
    for sid, email, reason in skipped:
        print(f"  SKIP {email or sid}: {reason}")

    if not args.apply:
        print("\nDry-run: nessuna scrittura. Rilancia con --apply per eseguire.")
        return 0

    # 5. Backup mappatura attuale (rollback: ri-applica old_clerk_id)
    backup = [{"user_id": p["internal_user_id"], "old_clerk_id": p["dev_clerk_id"], "email": p["email"]} for p in plan]
    BACKUP_PATH.write_text(json.dumps({"created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mapping": backup}, indent=2))
    print(f"\nBackup mappatura → {BACKUP_PATH}")

    # 6. Creazione utenti prod + remap
    remapped = 0
    for p in plan:
        new_id = p["prod_clerk_id"]
        if not new_id:
            created = _create_prod_user(prod_key, p["dev_user"], p["email"])
            new_id = created["id"]
            print(f"  creato in prod: {p['email']} → {new_id}")
        res = (
            sb.table("users")
            .update({"clerk_id": new_id})
            .eq("user_id", p["internal_user_id"])
            .eq("clerk_id", p["dev_clerk_id"])
            .execute()
        )
        if res.data:
            remapped += 1
        else:
            print(f"  ⚠️ remap NON applicato per {p['email']} (riga cambiata nel frattempo?)")

    print(f"\nFatto: {remapped}/{len(plan)} clerk_id rimappati su Supabase.")
    print("PROSSIMO PASSO: swap chiavi frontend (Vercel) + CLERK_JWKS_URL (Railway), poi redeploy.")
    print("NOTA: la cache in-memory clerk_id→user_id del backend (TTL 5 min) si svuota col redeploy Railway.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
