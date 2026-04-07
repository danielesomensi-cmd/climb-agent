"""One-off migration: add hang_seconds/edge_mm/grip to Daniele's hangboard baseline.

Usage:
    python scripts/migrate_baseline_fields.py --dry-run     # preview
    python scripts/migrate_baseline_fields.py --apply       # execute

Part of B-HORST-INTENSITY. Reads state via GET /api/state, mutates the first
hangboard baseline to include the missing protocol fields (only if missing),
backs up the original state to /tmp, and writes back via PUT /api/state.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

API_BASE = "https://web-production-fb1e9.up.railway.app"
USER_ID = "7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e"  # Daniele's internal UUID

# Fields to inject (confirmed by Daniele for the 2026-03-17 test)
PROTOCOL_FIELDS = {
    "hang_seconds": 7,
    "edge_mm": 20,
    "grip": "half_crimp",
}


def _load_admin_secret() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("ADMIN_SECRET="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("ADMIN_SECRET not found in .env")


def _headers(admin_secret: str) -> dict:
    return {
        "X-User-Id": USER_ID,
        "X-Admin-Key": admin_secret,
        "Content-Type": "application/json",
    }


def _get_state(admin_secret: str) -> dict:
    req = urllib.request.Request(f"{API_BASE}/api/state", headers=_headers(admin_secret))
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _put_state(admin_secret: str, patch: dict) -> dict:
    data = json.dumps(patch).encode()
    req = urllib.request.Request(
        f"{API_BASE}/api/state",
        data=data,
        headers=_headers(admin_secret),
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no PUT")
    parser.add_argument("--apply", action="store_true", help="Execute the migration")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

    admin_secret = _load_admin_secret()

    print(f"[1/5] GET /api/state for user {USER_ID}")
    state = _get_state(admin_secret)

    # Name guard — bail if not Daniele
    user_name = (state.get("user") or {}).get("name", "").strip().lower()
    if not user_name.startswith("daniele"):
        raise SystemExit(f"SAFETY ABORT: expected user.name starting with 'daniele', got {user_name!r}")
    print(f"       user.name = {state['user']['name']!r}  OK")

    # Backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"/tmp/user_state_backup_{ts}.json")
    backup_path.write_text(json.dumps(state, indent=2))
    print(f"[2/5] Backup saved to {backup_path}")

    hb = state.get("baselines", {}).get("hangboard", [])
    if not hb:
        raise SystemExit("SAFETY ABORT: baselines.hangboard is empty")
    if not isinstance(hb, list):
        raise SystemExit(f"SAFETY ABORT: baselines.hangboard is not a list ({type(hb).__name__})")

    print(f"[3/5] Current baselines.hangboard ({len(hb)} entries):")
    for i, entry in enumerate(hb):
        print(f"       [{i}] {json.dumps(entry)}")

    # Build new list: mutate [0] if fields missing, preserve all others
    entry0 = dict(hb[0])
    changes = {}
    for k, v in PROTOCOL_FIELDS.items():
        if k not in entry0:
            entry0[k] = v
            changes[k] = v

    if not changes:
        print("[4/5] No changes needed — all protocol fields already present.")
        return 0

    print(f"[4/5] Will inject into hangboard[0]: {json.dumps(changes)}")
    new_hb = [entry0] + hb[1:]
    print(f"       New hangboard[0] = {json.dumps(entry0)}")

    patch = {"baselines": {"hangboard": new_hb}}
    print(f"\n       Patch to PUT:\n       {json.dumps(patch, indent=2)}")

    if args.dry_run:
        print("\n[5/5] DRY RUN — skipping PUT. Re-run with --apply to execute.")
        return 0

    print("\n[5/5] PUT /api/state ...")
    result = _put_state(admin_secret, patch)
    result_hb = result.get("baselines", {}).get("hangboard", [])
    print(f"       Response baselines.hangboard[0] = {json.dumps(result_hb[0] if result_hb else None)}")

    # Verify
    for k, v in PROTOCOL_FIELDS.items():
        if result_hb[0].get(k) != v:
            print(f"       WARNING: {k} did not land ({result_hb[0].get(k)!r} != {v!r})")
            return 1
    print("       ✅ All protocol fields confirmed in response.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
